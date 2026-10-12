"""OneMap canlı bina eşitlemesi — bina listesi (``bina``) OneMap'le kendiliğinden güncel kalır.

Neden: bina listesi bir kez (tur raporu + Eylül OneMap dökümü) kuruldu; sonradan açılan binalar (ör. Location ID
O53762030) BOSS'ta iş olarak gelir ama listede olmadığından işin binası/konumu yoktur.

Akış (BOSS Yardımcısı eklentisi, OneMap sekmesi açıkken; ``kod/eklenti/onemap_arka.js``):
    1. ``GET  /api/onemap/gorev``   (eşleme kodu) → ne sorgulanacak: bilinmeyen lokasyonlar (``ENTEGRASYON_ID IN``),
       konum bekleyen tur binaları (``LOCATION_ID IN``), artımlı tarama (OBJECTID > en büyük) ya da günde en çok bir
       tam tarama (kaldığı OBJECTID'den sürer). Sorgu metnini SUNUCU kurar; eklenti körü körüne çalıştırır.
    2. Eklenti sayfanın kendi oturumuyla ArcGIS'e sorar (oturum bilgisi buraya hiç gelmez), satırları sade biçime
       çevirir → ``POST /api/onemap/binalar``.
    3. ``yukle``: tek işlemde bina ekler/günceller (ASLA silmez), kaynağı ``onemap_bina``'ya yazar, değişikliği
       ``bina_degisim``'e (kaynak 'onemap'), sonra lokasyonu artık eşleşen AÇIK işleri binaya bağlar (bina_serial,
       lat/lon, konum_kaynak='bina'; olay 'aktarim_degisti').
    4. ``GET /api/onemap/durum`` → BOSS bağlantısı ekranındaki OneMap kartı.

Kimlik eşlemesi (``dsale/enrich.py``, canlı veride 19.706/19.706 doğrulandı):
    OneMap ``LOCATION_ID`` (BN-…) = ``bina.bina_serial`` · ``ENTEGRASYON_ID`` (O…) = ``bina.location_id`` (BOSS
    "Lokasyon") · ``ID`` = ``bina.tellcordia_id``.

Kurallar:
  * Yeni bina: OneMap'te ``PROTOKOL_FIRMA`` DEHANET… ise etkin; değilse (yalnız bir işin lokasyonu diye arandıysa)
    ``pasif=1`` eklenir — satış listesine girmez, yalnız işi konumlandırır. HP/abone sayıları tur raporundan gelir.
  * Var olan bina: alan ancak OneMap'teki değer bir önceki OneMap değerinden DEĞİŞTİYSE güncellenir (CRM'den gelen
    ad/site adı OneMap adıyla ezilmez). Konum 15 m'den çok kaydıysa güncellenir; ilk karşılaştırma tabanı ilk
    kurulumdaki OneMap LAT/LON'udur (``kalite_kaynak.om_lat/om_lon``). Bölge ve site grubu değişmez.
  * Tur raporunun "konum bekliyor" binaları ``tur_raporu.onemap_yukle`` ile eklenir (HP/abone o satırdan).
Tablolar ilk yazışta ``ek_sema.yedekli_kur`` ile (doğrulanmış yedekten sonra) kurulur.
"""
from __future__ import annotations

import json
import logging
import math
import re
import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from . import ayarlar, db
from .yetki import baglanti, izin

_gunluk = logging.getLogger("saha.onemap")

yonlendirici = APIRouter()

SERVIS = "https://arcgis.turkcell.com.tr/arcgis/rest/services/ONEMAP/BINA/MapServer/0"
# Toplu taramanın tabanı: bizim binalarımız (ilk döküm de PROTOKOL_FIRMA='DEHANET ECM' idi). Bütün Bursa'yı çekmek
# satış listesini başka bayilerin binalarıyla doldururdu. Değiştirmek için ayar 'onemap_taban_suzgec'.
TABAN_VARSAYILAN = "IL IN ('Bursa','Yalova','BURSA','YALOVA') AND PROTOKOL_FIRMA LIKE 'DEHANET%'"
ALANLAR = ("OBJECTID", "ID", "LOCATION_ID", "ENTEGRASYON_ID", "ADI", "SITE_ADI", "BLOK_ADI", "KAPI_NO", "TURU",
           "BLOK_TIPI", "MAHALLE", "ILCE", "IL", "CADDE", "SOKAK", "LAT", "LON", "KAT_ADEDI", "KONUT_SAYISI",
           "ISYERI_SAYISI", "FTTX_HP", "PROTOKOL_FIRMA", "OBEK_ADI", "UAVT_BINA_KODU", "TEKNOLOJI",
           "LAST_EDITED_DATE", "ISDELETED")
SAYFA = 500                 # tek sorguda en çok satır
BEKLEME_MS = 800            # sorgular arası (OneMap'i yormamak için)
ARAMA_PARTI = 50            # IN (...) başına kimlik
TAM_ARALIK_SN = 24 * 3600   # tam tarama günde en çok bir
ARAMA_TEKRAR_SN = 6 * 3600  # bulunamayan kimlik bu kadar sonra yeniden aranır
ARAMA_EN_COK = 5            # bu kadar denemede bulunamazsa 'bulunamadi'
TEMAS_SN = 15 * 60          # bu süre içinde eklenti yokladıysa "bağlı"
KAYMA_M = 15.0              # konum bundan çok kaydıysa güncellenir
DURUM_ANAHTARI = "onemap_durum"
KIMLIK_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{1,39}$")
IZLENEN = ("ad", "site_adi", "blok_adi", "kapi_no", "mahalle", "ilce", "cadde", "sokak")

SEMA = [
    # Binanın OneMap kaynağı: son görülen OneMap değerleri (değişiklik tabanı) ve ne zaman
    "CREATE TABLE IF NOT EXISTS onemap_bina (bina_serial TEXT PRIMARY KEY, objectid INTEGER, om_id TEXT, "
    "entegrasyon_id TEXT, om_lat REAL, om_lon REAL, alanlar TEXT NOT NULL DEFAULT '{}', "
    "kaynak TEXT NOT NULL DEFAULT 'onemap', eklendi INTEGER NOT NULL DEFAULT 0, ilk_gorulme TEXT NOT NULL, "
    "son_gorulme TEXT NOT NULL, guncelleme TEXT)",
    "CREATE INDEX IF NOT EXISTS ix_onemap_bina_obj ON onemap_bina(objectid)",
    # İsteğe bağlı arama kuyruğu: bilinmeyen iş lokasyonları ve konum bekleyen tur binaları
    "CREATE TABLE IF NOT EXISTS onemap_arama (alan TEXT NOT NULL, deger TEXT NOT NULL, neden TEXT, "
    "durum TEXT NOT NULL DEFAULT 'bekliyor', deneme INTEGER NOT NULL DEFAULT 0, son_deneme TEXT, "
    "eklenme TEXT NOT NULL, PRIMARY KEY (alan, deger))",
]
TABLOLAR = ("onemap_bina", "onemap_arama")

ROTA_IZNI: dict[tuple[str, str], str | tuple[str, ...]] = {
    ("GET", "/api/onemap/gorev"): "is.yukle",
    ("POST", "/api/onemap/binalar"): "is.yukle",
    ("GET", "/api/onemap/durum"): ("is.yukle", "is.ata"),
}


# ============================================================================= tablolar, durum
def hazirla(conn: sqlite3.Connection, yedek: bool = True) -> bool:
    from operasyon.v2 import ek_sema
    return ek_sema.yedekli_kur(conn, "onemap", SEMA, TABLOLAR, yedek)


def _hazir(conn: sqlite3.Connection) -> bool:
    return all(db.tablo_var(conn, t) for t in TABLOLAR)


def durum_oku(conn: sqlite3.Connection) -> dict:
    try:
        d = json.loads(db.ayar_oku(conn, DURUM_ANAHTARI, "") or "{}")
        return d if isinstance(d, dict) else {}
    except ValueError:
        return {}


def _durum_yaz(conn: sqlite3.Connection, **ek) -> dict:
    d = durum_oku(conn)
    d.update(ek)
    db.ayar_yaz(conn, DURUM_ANAHTARI, json.dumps(d, ensure_ascii=False))
    return d


def _sn_once(metin: str | None) -> float | None:
    if not metin:
        return None
    try:
        import datetime as dt
        return (ayarlar.simdi() - dt.datetime.fromisoformat(str(metin))).total_seconds()
    except ValueError:
        return None


# ============================================================================= bilinmeyen lokasyonlar
def _bina_lokasyonlari(conn: sqlite3.Connection) -> set[str]:
    return {str(r[0]).strip().upper() for r in conn.execute(
        "SELECT location_id FROM bina WHERE location_id IS NOT NULL AND location_id <> ''")}


def _adaylar(lok: str) -> list[str]:
    from operasyon import is_emri as ie
    return [a.upper() for a in ie.lokasyon_adaylari(lok)]


def bilinmeyen_lokasyonlar(conn: sqlite3.Connection) -> list[str]:
    """Açık işlerin bina listesinde OLMAYAN lokasyonları (ilk aday biçimiyle, tekil)."""
    if not db.tablo_var(conn, "is_emri"):
        return []
    bilinen = _bina_lokasyonlari(conn)
    sonuc: dict[str, None] = {}
    for (lok,) in conn.execute(
            "SELECT DISTINCT lokasyon FROM is_emri WHERE kapanis IS NULL AND durum NOT IN ('cozuldu','kapandi') "
            "AND lokasyon IS NOT NULL AND TRIM(lokasyon) <> ''"):
        adaylar = _adaylar(str(lok))
        if adaylar and not any(a in bilinen for a in adaylar) and KIMLIK_RE.match(adaylar[0]):
            sonuc[adaylar[0]] = None
    return list(sonuc)


def _kuyrugu_doldur(conn: sqlite3.Connection, simdi: str) -> None:
    satirlar = [("ENTEGRASYON_ID", d, "is_lokasyonu", simdi) for d in bilinmeyen_lokasyonlar(conn)]
    if db.tablo_var(conn, "bina_bekleyen"):
        satirlar += [("LOCATION_ID", r[0], "tur_bekleyen", simdi) for r in conn.execute(
            "SELECT bina_serial FROM bina_bekleyen WHERE durum='konum_bekliyor'") if KIMLIK_RE.match(str(r[0]))]
    conn.executemany("INSERT INTO onemap_arama (alan, deger, neden, eklenme) VALUES (?,?,?,?) "
                     "ON CONFLICT(alan, deger) DO NOTHING", satirlar)


def _aranacaklar(conn: sqlite3.Connection) -> list[dict]:
    gruplar: dict[str, list[str]] = {}
    for r in conn.execute("SELECT alan, deger, son_deneme FROM onemap_arama WHERE durum='bekliyor' "
                          "ORDER BY deneme, eklenme LIMIT 400"):
        gecen = _sn_once(r["son_deneme"])
        if gecen is not None and gecen < ARAMA_TEKRAR_SN:
            continue
        gruplar.setdefault(r["alan"], []).append(r["deger"])
    cikti = []
    for alan, degerler in gruplar.items():
        for i in range(0, len(degerler), ARAMA_PARTI):
            parca = degerler[i:i + ARAMA_PARTI]
            cikti.append({"alan": alan, "degerler": parca,
                          "where": f"{alan} IN (" + ",".join(f"'{d}'" for d in parca) + ")"})
    return cikti


# ============================================================================= görev (eklenti ne sorgulasın)
def gorev(conn: sqlite3.Connection) -> dict:
    hazirla(conn)
    simdi = ayarlar.zaman_metni()
    conn.commit()
    conn.execute("BEGIN IMMEDIATE")
    try:
        _kuyrugu_doldur(conn, simdi)
        d = _durum_yaz(conn, son_temas=simdi)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    taban = db.ayar_oku(conn, "onemap_taban_suzgec", "") or TABAN_VARSAYILAN
    tam_gecen = _sn_once(d.get("son_tam"))
    tam = tam_gecen is None or tam_gecen >= TAM_ARALIK_SN
    en_buyuk = int(d.get("en_buyuk_objectid") or 0)
    if not en_buyuk:
        r = conn.execute("SELECT MAX(objectid) FROM onemap_bina").fetchone()
        en_buyuk = int(r[0] or 0)
    tarama = None
    if tam:
        tarama = {"tur": "tam", "basla": int(d.get("tam_imlec") or 0)}
    elif en_buyuk:
        tarama = {"tur": "artimli", "basla": en_buyuk}
    return {"servis": SERVIS, "taban": taban, "alanlar": list(ALANLAR), "sayfa": SAYFA, "bekleme_ms": BEKLEME_MS,
            "arama": _aranacaklar(conn), "tarama": tarama}


# ============================================================================= gelen satır
class BinaSatiri(BaseModel):
    """Eklentinin sade biçimi (``onemap_arka.js sadeSatir``)."""
    model_config = ConfigDict(extra="ignore")
    objectid: int | None = None
    om_id: str | None = Field(default=None, max_length=40)
    bina_serial: str | None = Field(default=None, max_length=60)        # LOCATION_ID
    location_id: str | None = Field(default=None, max_length=60)        # ENTEGRASYON_ID
    ad: str | None = Field(default=None, max_length=300)
    site_adi: str | None = Field(default=None, max_length=300)
    blok_adi: str | None = Field(default=None, max_length=120)
    kapi_no: str | None = Field(default=None, max_length=60)
    turu: str | None = Field(default=None, max_length=60)
    blok_tipi: str | None = Field(default=None, max_length=60)
    mahalle: str | None = Field(default=None, max_length=120)
    ilce: str | None = Field(default=None, max_length=120)
    il: str | None = Field(default=None, max_length=60)
    cadde: str | None = Field(default=None, max_length=200)
    sokak: str | None = Field(default=None, max_length=200)
    lat: float | None = None
    lon: float | None = None
    kat: int | None = None
    konut: int | None = None
    isyeri: int | None = None
    hp: int | None = None
    firma: str | None = Field(default=None, max_length=120)
    obek: str | None = Field(default=None, max_length=120)
    uavt: str | None = Field(default=None, max_length=40)
    teknoloji: str | None = Field(default=None, max_length=60)
    duzenleme: int | None = None
    silindi: bool = False
    halka: list[list[float]] | None = Field(default=None, max_length=5000)


class BinalarGirdi(BaseModel):
    model_config = ConfigDict(extra="ignore")
    tur: str = Field(default="artimli", pattern="^(tam|artimli|arama)$")
    binalar: list[BinaSatiri] = Field(default_factory=list, max_length=5000)
    aranan: dict | None = None          # {alan, degerler}
    bitti: bool = False                 # tam tarama sona erdi
    imlec: int | None = None            # tam taramada son OBJECTID
    hata: str | None = Field(default=None, max_length=300)


def _metin(x) -> str:
    return re.sub(r"\s+", " ", str(x or "")).strip()


def _mesafe_m(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6_371_000.0 * math.asin(math.sqrt(a))


def _konum_gecerli(lat, lon) -> bool:
    return lat is not None and lon is not None and 35.0 <= lat <= 43.0 and 25.0 <= lon <= 45.0


def _merkez(s: BinaSatiri) -> tuple[float | None, float | None, list | None]:
    """Poligon varsa merkezi (ilk kurulumla aynı), yoksa OneMap LAT/LON."""
    if s.halka and len(s.halka) >= 3:
        try:
            from dsale.enrich import _poligon
            lon, lat, _alan, dis = _poligon([s.halka])
            if _konum_gecerli(lat, lon):
                return float(lat), float(lon), dis
        except Exception:  # noqa: BLE001 — bozuk poligon: noktaya düş
            pass
    if _konum_gecerli(s.lat, s.lon):
        return float(s.lat), float(s.lon), None
    return None, None, None


def _izlenen(s: BinaSatiri) -> dict:
    from dsale.enrich import mahalle_norm
    ilce = _metin(s.ilce)
    if (s.il or "").strip().lower() == "yalova" and ilce in ("Merkez", "Yalova Merkez"):
        ilce = "Yalova Merkez"
    return {"ad": _metin(s.ad), "site_adi": _metin(s.site_adi), "blok_adi": _metin(s.blok_adi),
            "kapi_no": _metin(s.kapi_no), "mahalle": mahalle_norm(s.mahalle) if _metin(s.mahalle) else "",
            "ilce": ilce, "cadde": _metin(s.cadde), "sokak": _metin(s.sokak)}


def _arcgis_bicimi(s: BinaSatiri) -> dict:
    """Sade satır → ArcGIS öznitelik adları (``tur_raporu.onemap_yukle`` bunu okur)."""
    return {"OBJECTID": s.objectid, "ID": s.om_id, "LOCATION_ID": s.bina_serial, "ENTEGRASYON_ID": s.location_id,
            "ADI": s.ad, "SITE_ADI": s.site_adi, "BLOK_ADI": s.blok_adi, "KAPI_NO": s.kapi_no, "TURU": s.turu,
            "MAHALLE": s.mahalle, "ILCE": s.ilce, "IL": s.il, "CADDE": s.cadde, "SOKAK": s.sokak,
            "LAT": s.lat, "LON": s.lon, "KAT_ADEDI": s.kat, "KONUT_SAYISI": s.konut, "ISYERI_SAYISI": s.isyeri,
            "OBEK_ADI": s.obek, "UAVT_BINA_KODU": s.uavt, "TEKNOLOJI": s.teknoloji}


def _bizim_mi(s: BinaSatiri) -> bool:
    return (s.firma or "").strip().upper().startswith("DEHANET")


def _ilk_konum(kalite_kaynak: str | None) -> tuple[float | None, float | None]:
    try:
        k = json.loads(kalite_kaynak or "{}")
        return (float(k["om_lat"]), float(k["om_lon"])) if k.get("om_lat") is not None else (None, None)
    except (ValueError, TypeError, KeyError):
        return None, None


# ============================================================================= yükleme
def _tur_bekleyenleri(conn: sqlite3.Connection, satirlar: list[BinaSatiri]) -> tuple[list[BinaSatiri], set[str]]:
    """Tur raporunun konum bekleyen binaları ``tur_raporu.onemap_yukle``'ye gider (HP/abone o satırdan)."""
    if not db.tablo_var(conn, "bina_bekleyen"):
        return [], set()
    bekleyen = {r[0]: r[1] for r in conn.execute(
        "SELECT bina_serial, tellcordia_id FROM bina_bekleyen WHERE durum='konum_bekliyor'")}
    if not bekleyen:
        return [], set()
    tell = {t: s for s, t in bekleyen.items() if t}
    secilen = [s for s in satirlar if (s.bina_serial in bekleyen) or (s.om_id and s.om_id in tell)]
    if not secilen:
        return [], set()
    from . import tur_raporu
    once = {r[0] for r in conn.execute("SELECT bina_serial FROM bina")}
    tur_raporu.onemap_yukle(conn, {"features": [{"a": _arcgis_bicimi(s), "g": [s.halka] if s.halka else []}
                                                for s in secilen]}, yapan_id=0)
    sonra = {r[0] for r in conn.execute("SELECT bina_serial FROM bina")}
    return secilen, sonra - once


def _ekle(conn: sqlite3.Connection, s: BinaSatiri, izl: dict, lat: float, lon: float, dis, simdi: str) -> None:
    from dsale import kalite
    from . import tur_raporu

    bizim = _bizim_mi(s)
    serial = s.bina_serial
    kat_om = int(s.kat or 0)
    daire = s.konut
    kat_kaynagi = "OneMap" if 1 <= kat_om <= 60 else "Tahmin"
    kat_tahmin = kalite.kat_tahmini_tek(daire)
    kat = kat_om if kat_kaynagi == "OneMap" else kat_tahmin
    grup = tur_raporu._site_grubu(conn, serial, izl["ilce"], izl["mahalle"], izl["site_adi"], s.turu or "", lat, lon)
    bolge = tur_raporu._bolge_bul(conn, grup, lat, lon) if bizim else None
    kanit = kalite.kanit_onemap(_arcgis_bicimi(s), daire=daire, kat_kaynagi=kat_kaynagi, kat_tahmin=kat_tahmin,
                                ham={"location_id": s.location_id or "", "tellcordia_id": s.om_id or "", "kat": kat,
                                     "ad": izl["ad"], "site_adi": izl["site_adi"], "crm_site_adi": ""})
    conn.execute(
        "INSERT INTO bina (bina_serial, ad, site_adi, mahalle, ilce, il, cadde, sokak, kapi_no, lat, lon, kat, daire, "
        "  res_hp, aktif_res, firsat, bolge, obek, site_grup, location_id, tellcordia_id, uavt_bina_kodu, blok_adi, "
        "  bina_turu, toplam_hp, soho_hp, teknoloji, crm_site_adi, kalite_kaynak, pasif, pasif_tarih, ekleme_kaynagi) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,0,0,0,?,?,?,?,?,?,?,?,?,0,?,'',?,?,?,?)",
        (serial, izl["ad"], izl["site_adi"], izl["mahalle"] or "Bilinmiyor", izl["ilce"], _metin(s.il), izl["cadde"],
         izl["sokak"], izl["kapi_no"], lat, lon, int(kat), int(daire or 0), bolge, _metin(s.obek), grup,
         _metin(s.location_id), _metin(s.om_id), _metin(s.uavt), izl["blok_adi"], _metin(s.turu), int(s.hp or 0),
         _metin(s.teknoloji), json.dumps(kanit, ensure_ascii=False, separators=(",", ":")),
         0 if bizim else 1, None if bizim else simdi, "onemap" if bizim else "onemap-is"))
    if bizim:
        conn.execute("INSERT INTO bina_durum (bina_serial, durum) VALUES (?, 'bekliyor') "
                     "ON CONFLICT(bina_serial) DO NOTHING", (serial,))
    if dis and db.tablo_var(conn, "bina_geometri_ek"):
        conn.execute("INSERT INTO bina_geometri_ek (bina_serial, halka, zaman) VALUES (?,?,?) "
                     "ON CONFLICT(bina_serial) DO UPDATE SET halka=excluded.halka, zaman=excluded.zaman",
                     (serial, json.dumps(dis, separators=(",", ":")), simdi))
    conn.execute("INSERT INTO bina_degisim (bina_serial, kaynak, alan, eski, yeni, zaman) "
                 "VALUES (?, 'onemap', 'eklendi', NULL, ?, ?)",
                 (serial, f"bölge {bolge}" if bizim else "pasif (iş lokasyonu)", simdi))


def _guncelle(conn: sqlite3.Connection, b: sqlite3.Row, onc: sqlite3.Row | None, s: BinaSatiri, izl: dict,
              lat: float | None, lon: float | None, simdi: str) -> list[tuple]:
    """Var olan bina: yalnız OneMap'te DEĞİŞEN alanlar. Değişim satırları döner (yazılmış olarak)."""
    serial = b["bina_serial"]
    degisim: list[tuple] = []
    ek: dict[str, Any] = {}
    # konum: taban = son görülen OneMap LAT/LON, yoksa ilk kurulumdaki
    if onc is not None and onc["om_lat"] is not None:
        t_lat, t_lon = onc["om_lat"], onc["om_lon"]
    else:
        t_lat, t_lon = _ilk_konum(b["kalite_kaynak"])
    if (_konum_gecerli(s.lat, s.lon) and t_lat is not None and lat is not None
            and _mesafe_m(s.lat, s.lon, t_lat, t_lon) > KAYMA_M
            and _mesafe_m(lat, lon, b["lat"], b["lon"]) > KAYMA_M):
        ek["lat"], ek["lon"] = lat, lon
        degisim.append((serial, "onemap", "konum", f"{b['lat']:.6f},{b['lon']:.6f}", f"{lat:.6f},{lon:.6f}", simdi))
    # alanlar: önceki OneMap değeri biliniyorsa ve değiştiyse
    if onc is not None:
        try:
            eski_om = json.loads(onc["alanlar"] or "{}")
        except ValueError:
            eski_om = {}
        onemap_binasi = str(b["ekleme_kaynagi"] or "").startswith("onemap")
        for a in IZLENEN:
            yeni = izl.get(a) or ""
            if not yeni or a not in eski_om or eski_om.get(a) == yeni:
                continue
            if a == "ad" and not onemap_binasi:
                continue                      # CRM adı OneMap adıyla ezilmez
            if (b[a] or "") != yeni:
                ek[a] = yeni
                degisim.append((serial, "onemap", a, b[a], yeni, simdi))
    if not _metin(b["location_id"]) and s.location_id:
        ek["location_id"] = _metin(s.location_id)
        degisim.append((serial, "onemap", "location_id", None, ek["location_id"], simdi))
    if ek:
        conn.execute(f"UPDATE bina SET {', '.join(f'{k}=?' for k in ek)} WHERE bina_serial=?", (*ek.values(), serial))
        conn.executemany("INSERT INTO bina_degisim (bina_serial, kaynak, alan, eski, yeni, zaman) "
                         "VALUES (?,?,?,?,?,?)", degisim)
    return degisim


def _kaynak_yaz(conn: sqlite3.Connection, s: BinaSatiri, serial: str, izl: dict, eklendi: bool, degisti: bool,
                simdi: str) -> None:
    conn.execute(
        "INSERT INTO onemap_bina (bina_serial, objectid, om_id, entegrasyon_id, om_lat, om_lon, alanlar, kaynak, "
        "  eklendi, ilk_gorulme, son_gorulme, guncelleme) VALUES (?,?,?,?,?,?,?,'onemap',?,?,?,?) "
        "ON CONFLICT(bina_serial) DO UPDATE SET objectid=excluded.objectid, om_id=excluded.om_id, "
        "  entegrasyon_id=excluded.entegrasyon_id, om_lat=COALESCE(excluded.om_lat, onemap_bina.om_lat), "
        "  om_lon=COALESCE(excluded.om_lon, onemap_bina.om_lon), alanlar=excluded.alanlar, "
        "  eklendi=MAX(onemap_bina.eklendi, excluded.eklendi), son_gorulme=excluded.son_gorulme, "
        "  guncelleme=COALESCE(excluded.guncelleme, onemap_bina.guncelleme)",
        (serial, s.objectid, _metin(s.om_id) or None, _metin(s.location_id) or None,
         s.lat if _konum_gecerli(s.lat, s.lon) else None, s.lon if _konum_gecerli(s.lat, s.lon) else None,
         json.dumps(izl, ensure_ascii=False, separators=(",", ":")), 1 if eklendi else 0, simdi, simdi,
         simdi if (eklendi or degisti) else None))


def isleri_bagla(conn: sqlite3.Connection, seriler: set[str]) -> int:
    """Lokasyonu bu binalardan birine eşleşen AÇIK işleri binaya bağlar (elle mahalle verilmiş işe dokunmaz)."""
    if not seriler or not db.tablo_var(conn, "is_emri"):
        return 0
    from operasyon.v2 import zaman
    binalar: dict[str, sqlite3.Row] = {}
    liste = list(seriler)
    for i in range(0, len(liste), 500):
        parca = liste[i:i + 500]
        for r in conn.execute(f"SELECT bina_serial, location_id, lat, lon, pasif FROM bina WHERE bina_serial IN "
                              f"({','.join('?' * len(parca))})", parca):
            if _metin(r["location_id"]):
                binalar[_metin(r["location_id"]).upper()] = r
    if not binalar:
        return 0
    simdi = zaman.metin()
    bagli = 0
    for e in conn.execute(
            "SELECT is_no, lokasyon, bina_serial, lat, lon, konum_kaynak, mahalle_elle FROM is_emri "
            "WHERE kapanis IS NULL AND durum NOT IN ('cozuldu','kapandi') AND lokasyon IS NOT NULL "
            "AND TRIM(lokasyon) <> ''").fetchall():
        if e["mahalle_elle"]:
            continue
        b = next((binalar[a] for a in _adaylar(str(e["lokasyon"])) if a in binalar), None)
        if b is None:
            continue
        ayni = (e["bina_serial"] == b["bina_serial"] and e["konum_kaynak"] == "bina" and e["lat"] is not None
                and _mesafe_m(e["lat"], e["lon"], b["lat"], b["lon"]) < 1.0)
        if ayni:
            continue
        eski = {"bina_serial": e["bina_serial"], "lat": e["lat"], "lon": e["lon"], "konum_kaynak": e["konum_kaynak"]}
        yeni = {"bina_serial": b["bina_serial"], "lat": b["lat"], "lon": b["lon"], "konum_kaynak": "bina"}
        conn.execute("UPDATE is_emri SET bina_serial=?, lat=?, lon=?, konum_kaynak='bina', konum_yaklasik=0, "
                     "surum=surum+1, guncelleme=? WHERE is_no=?", (b["bina_serial"], b["lat"], b["lon"], simdi,
                                                                   e["is_no"]))
        conn.execute(
            "INSERT INTO is_emri_olay (is_no, zaman, kayit_zamani, kullanici_id, kullanici_ad, tur, eski, yeni, notu) "
            "VALUES (?,?,?,NULL,'OneMap','aktarim_degisti',?,?,?)",
            (e["is_no"], simdi, simdi, json.dumps(eski, ensure_ascii=False), json.dumps(yeni, ensure_ascii=False),
             "OneMap: lokasyonun binası bulundu"))
        bagli += 1
    return bagli


def yukle(conn: sqlite3.Connection, girdi: BinalarGirdi) -> dict:
    """Eklentiden gelen OneMap satırlarını işler (bkz. modül başı). Hiçbir bina silinmez."""
    from . import veri_kalitesi

    hazirla(conn)
    simdi = ayarlar.zaman_metni()
    satirlar = [s for s in girdi.binalar if _metin(s.bina_serial) and KIMLIK_RE.match(_metin(s.bina_serial))]
    for s in satirlar:
        s.bina_serial = _metin(s.bina_serial)
        s.location_id = _metin(s.location_id) or None
        s.om_id = _metin(s.om_id) or None

    tur_secilen, tur_eklenen = _tur_bekleyenleri(conn, [s for s in satirlar if not s.silindi])
    tur_seri = {s.bina_serial for s in tur_secilen}

    eklenen: list[str] = []
    guncellenen: list[str] = []
    konumsuz = 0
    conn.commit()
    conn.execute("BEGIN IMMEDIATE")
    try:
        lok_index = {_metin(r[0]).upper(): r[1] for r in conn.execute(
            "SELECT location_id, bina_serial FROM bina WHERE location_id IS NOT NULL AND location_id <> '' "
            "ORDER BY pasif DESC")}
        islenen: set[str] = set()
        for s in satirlar:
            if s.bina_serial in islenen:
                continue
            islenen.add(s.bina_serial)
            izl = _izlenen(s)
            lat, lon, dis = _merkez(s)
            b = conn.execute("SELECT * FROM bina WHERE bina_serial=?", (s.bina_serial,)).fetchone()
            if b is None and s.location_id and s.location_id.upper() in lok_index:
                b = conn.execute("SELECT * FROM bina WHERE bina_serial=?",
                                 (lok_index[s.location_id.upper()],)).fetchone()
            if b is None:
                if s.bina_serial in tur_seri or s.silindi:
                    continue
                if lat is None:
                    konumsuz += 1
                    continue
                _ekle(conn, s, izl, lat, lon, dis, simdi)
                eklenen.append(s.bina_serial)
                _kaynak_yaz(conn, s, s.bina_serial, izl, True, True, simdi)
                if s.location_id:
                    lok_index[s.location_id.upper()] = s.bina_serial
                continue
            serial = b["bina_serial"]
            onc = conn.execute("SELECT * FROM onemap_bina WHERE bina_serial=?", (serial,)).fetchone()
            degisim = [] if s.silindi else _guncelle(conn, b, onc, s, izl, lat, lon, simdi)
            if degisim and serial not in tur_eklenen:
                guncellenen.append(serial)
            _kaynak_yaz(conn, s, serial, izl, serial in tur_eklenen, bool(degisim), simdi)
        dokunulan = list(dict.fromkeys(eklenen + guncellenen))
        if dokunulan:
            veri_kalitesi.yenile(conn, dokunulan)
            db.bina_surumu_arttir(conn)
        bagli = isleri_bagla(conn, set(dokunulan) | tur_eklenen)

        # arama kuyruğu: bulunanlar düşer, bulunamayanların denemesi artar
        if girdi.tur == "arama" and isinstance(girdi.aranan, dict):
            alan = str(girdi.aranan.get("alan") or "")
            degerler = [str(d) for d in (girdi.aranan.get("degerler") or [])][:ARAMA_PARTI * 4]
            if alan == "ENTEGRASYON_ID":
                bulunan = {(s.location_id or "").upper() for s in satirlar}
            else:
                bulunan = {s.bina_serial.upper() for s in satirlar}
            for d in degerler:
                if d.upper() in bulunan:
                    conn.execute("UPDATE onemap_arama SET durum='bulundu', deneme=deneme+1, son_deneme=? "
                                 "WHERE alan=? AND deger=?", (simdi, alan, d))
                else:
                    conn.execute("UPDATE onemap_arama SET deneme=deneme+1, son_deneme=?, durum=CASE WHEN deneme+1>=? "
                                 "THEN 'bulunamadi' ELSE durum END WHERE alan=? AND deger=?",
                                 (simdi, ARAMA_EN_COK, alan, d))

        d = durum_oku(conn)
        objler = [s.objectid for s in satirlar if s.objectid]
        ek: dict[str, Any] = {"son_temas": simdi, "son_esitleme": simdi, "son_hata": girdi.hata or None,
                              "eklenen_toplam": int(d.get("eklenen_toplam") or 0) + len(eklenen) + len(tur_eklenen),
                              "guncellenen_toplam": int(d.get("guncellenen_toplam") or 0) + len(guncellenen),
                              "baglanan_is_toplam": int(d.get("baglanan_is_toplam") or 0) + bagli}
        if eklenen or tur_eklenen or guncellenen:
            ek["son_degisim"] = {"zaman": simdi, "eklenen": len(eklenen) + len(tur_eklenen),
                                 "guncellenen": len(guncellenen), "baglanan_is": bagli}
        if objler and girdi.tur in ("tam", "artimli"):
            ek["en_buyuk_objectid"] = max(int(d.get("en_buyuk_objectid") or 0), max(objler))
        if girdi.tur == "tam":
            if girdi.bitti:
                ek["tam_imlec"] = 0
            elif girdi.imlec or objler:                 # hata bildirimi (boş sayfa) ilerlemeyi sıfırlamaz
                ek["tam_imlec"] = int(girdi.imlec or max(objler))
            if girdi.bitti and not girdi.hata:
                ek["son_tam"] = simdi
        _durum_yaz(conn, **ek)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    if eklenen or guncellenen or tur_eklenen:
        _gunluk.info("OneMap: %d bina eklendi, %d güncellendi, %d iş binaya bağlandı.",
                     len(eklenen) + len(tur_eklenen), len(guncellenen), bagli)
    return {"alinan": len(girdi.binalar), "eklenen": len(eklenen) + len(tur_eklenen), "guncellenen": len(guncellenen),
            "baglanan_is": bagli, "konumsuz": konumsuz, "eklenen_binalar": (eklenen + sorted(tur_eklenen))[:50]}


def durum(conn: sqlite3.Connection) -> dict:
    d = durum_oku(conn)
    temas = _sn_once(d.get("son_temas"))
    hazir = _hazir(conn)
    onemap_eklenen = 0
    if hazir:
        onemap_eklenen = int(conn.execute("SELECT COUNT(*) FROM onemap_bina WHERE eklendi=1").fetchone()[0])
    bulunamayan = 0
    if hazir:
        bulunamayan = int(conn.execute(
            "SELECT COUNT(*) FROM onemap_arama WHERE durum='bulunamadi' AND alan='ENTEGRASYON_ID'").fetchone()[0])
    return {"bagli": temas is not None and temas < TEMAS_SN, "son_temas": d.get("son_temas"),
            "son_esitleme": d.get("son_esitleme"), "son_tam": d.get("son_tam"),
            "yeni_bina": onemap_eklenen, "guncellenen_toplam": int(d.get("guncellenen_toplam") or 0),
            "baglanan_is_toplam": int(d.get("baglanan_is_toplam") or 0), "son_degisim": d.get("son_degisim"),
            "bilinmeyen_lokasyon": len(bilinmeyen_lokasyonlar(conn)), "bulunamayan": bulunamayan,
            "son_hata": d.get("son_hata")}


# ============================================================================= uçlar
def _eklenti_kimligi(conn: sqlite3.Connection = Depends(baglanti),
                     authorization: str | None = Header(default=None),
                     x_eslesme_kodu: str | None = Header(default=None)) -> dict:
    """Eklenti: ``X-Eslesme-Kodu`` (BOSS bağlantısı ekranındaki); yoksa ``is.yukle`` izinli oturum."""
    from . import yetki
    if x_eslesme_kodu:
        try:
            from operasyon.v2 import boss
        except Exception:  # noqa: BLE001
            raise HTTPException(503, {"hata": "BOSS bağlantısı bu kurulumda yok.", "kod": "boss_yok"})
        if boss.kod_dogru(x_eslesme_kodu):
            return {"id": None, "ad": "BOSS Yardımcısı", "eklenti": True}
        raise HTTPException(401, {"hata": "Eşleme kodu yanlış. Uygulamadaki BOSS bağlantısı ekranındaki kodu girin.",
                                  "kod": "eslesme_yanlis"})
    k = yetki.mevcut_kullanici(conn=conn, authorization=authorization)
    if not yetki.izinli(k, "is.yukle"):
        raise yetki.hata(403, yetki.YASAK_METNI, "yasak")
    return k


_eklenti_kimligi.eylemler = ("is.yukle",)


@yonlendirici.get("/api/onemap/gorev")
def onemap_gorev(k: dict = Depends(_eklenti_kimligi), conn: sqlite3.Connection = Depends(baglanti)):
    return gorev(conn)


@yonlendirici.post("/api/onemap/binalar")
def onemap_binalar(girdi: BinalarGirdi, k: dict = Depends(_eklenti_kimligi),
                   conn: sqlite3.Connection = Depends(baglanti)):
    return yukle(conn, girdi)


@yonlendirici.get("/api/onemap/durum")
def onemap_durum(k: dict = Depends(izin("is.yukle", "is.ata")), conn: sqlite3.Connection = Depends(baglanti)):
    return durum(conn)
