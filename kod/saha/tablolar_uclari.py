"""Tablolar (Ek-8, Ek-9): PS26'nın sayfa sekmeli görüntüleyicisinin yerini alan uçlar + PS26 içe aktarımı.

PS26 bugün ``data.xlsx`` → JSON → GitHub Pages (herkese açık!) yoluyla sekme sekme okunuyordu. Burada aynı
sayfalar veritabanından, girişle ve görevle süzülerek gelir:

    GET  /api/tablolar                 sekmeler ve satır sayıları + ekranın hikâye cümlesi için birkaç sayı
    GET  /api/tablolar/{sekme}         ticketlar · guzergah · altyapi · binalar  (İşler sekmesi /api/isler'i kullanır)
    POST /api/tablolar/altyapi         altyapı bekleyen satışa yeni satır (PS26'da elle eklenen satırın yerine)
    PATCH /api/tablolar/altyapi/{id}   durum (bekliyor · kuruldu · iptal), not, bina
    GET  /api/ps26                     PS26 klasörü bulundu mu, son aktarım ne zaman
    POST /api/ps26/aktar?kuru=1        önce önizleme (varsayılan), ``kuru=0`` uygular (önce doğrulanmış yedek)

Yanıt biçimi her sekmede aynıdır (arayüz tek bileşenle çizer): ``{sutunlar:[{anahtar, baslik, tur, …}],
satirlar:[[…], …]}`` — satır dizi, sütun sırası ``sutunlar`` ile aynı; ilk sütun gizli kimliktir.

Kişisel veri: müşteri numarası yalnız ``is.musteri`` izniyle döner (izinsizde sütun HİÇ yoktur) ve döndüğü her
liste ``erisim_kaydi``'na adetle yazılır (spec §2.5). Satıcı adları çalışan adıdır; tabloyu açan görevler görür.
"""
from __future__ import annotations

import datetime as dt
import json
import sqlite3
import tempfile
import threading
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from . import ayarlar, db, ek_dosya, ps26_aktar, ticket
from .yetki import KAPALI_IS_DURUMLARI, baglanti, hata, izin, izinli

# Bu modülün uçlarının izinleri (``saha/api.py`` → ``rota_izni_ekle``). Okuma ``tablolar.oku``; yazan uçlar
# ticket defterini tutan görevlerin (``ticket.defter``: operasyon + yönetici; ``POST /api/ticket/aktar`` ile aynı).
ROTA_IZNI: dict[tuple[str, str], str] = {
    ("GET", "/api/tablolar"): "tablolar.oku",
    ("GET", "/api/tablolar/{sekme}"): "tablolar.oku",
    ("POST", "/api/tablolar/altyapi"): "ticket.defter",
    ("PATCH", "/api/tablolar/altyapi/{kayit_id}"): "ticket.defter",
    ("GET", "/api/ps26"): "ticket.defter",
    ("POST", "/api/ps26/aktar"): "ticket.defter",
}

SEKMELER = {
    "ticketlar": "Ticketlar",
    "guzergah": "Güzergah",
    "altyapi": "Altyapı bekleyen",
    "binalar": "Binalar",
    "isler": "İşler",
}
ALTYAPI_ETIKET = {"bekliyor": "Bekliyor", "kuruldu": "Kuruldu", "iptal": "İptal"}
EN_BUYUK_XLSX = 80 * 1024 * 1024
EN_BUYUK_ZIP = 60 * 1024 * 1024
EN_BUYUK_TOPLAM = 250 * 1024 * 1024

_aktarim_kilidi = threading.Lock()        # aynı anda tek PS26 aktarımı (tek uvicorn süreci; spec §5.5)


class _JSON(Response):
    """Büyük tablolar (19.706 bina) doğrudan ``json.dumps``: ``jsonable_encoder`` her hücrede dolaşmasın."""
    media_type = "application/json"

    def render(self, content) -> bytes:
        return json.dumps(content, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")


# ============================================================================= yardımcılar
def _sutun(anahtar: str, baslik: str, tur: str = "metin", genislik: int | None = None,
           kartta: str | None = None, gizli: bool = False) -> dict:
    s = {"anahtar": anahtar, "baslik": baslik, "tur": tur}
    if genislik:
        s["genislik"] = genislik
    if kartta:
        s["kartta"] = kartta
    if gizli:
        s["gizli"] = True
    return s


def _gun_farki(tarih: str | None) -> int | None:
    if not tarih:
        return None
    try:
        return (ayarlar.bugun() - dt.date.fromisoformat(str(tarih)[:10])).days
    except ValueError:
        return None


def _erisim(conn: sqlite3.Connection, k: dict, eylem: str, adet: int) -> None:
    """KVKK erişim kaydı (spec §2.5): müşteri alanı döndüren liste, adetle. Yazılamazsa yanıt yine döner."""
    if not adet:
        return
    try:
        simdi = ayarlar.zaman_metni()
        conn.execute("INSERT INTO erisim_kaydi (zaman, gun, kullanici_id, kullanici_ad, eylem, is_no, adet, ip) "
                     "VALUES (?,?,?,?,?,NULL,?,NULL)", (simdi, simdi[:10], k["id"], k.get("ad"), eylem, adet))
        conn.commit()
    except sqlite3.Error:
        pass


def _musteri_gorur(k: dict) -> bool:
    return izinli(k, "is.musteri")


def _yanit(sekme: str, sutunlar: list[dict], satirlar: list[list], kimlik: str = "id", **ek) -> _JSON:
    """``kimlik``: satırı açarken kullanılan sütun (ticket/altyapı 'id' — gizli; bina 'bina_serial')."""
    return _JSON({"sekme": sekme, "ad": SEKMELER.get(sekme, sekme), "sutunlar": sutunlar, "satirlar": satirlar,
                  "kimlik": kimlik, "toplam": len(satirlar), "sunucu_zamani": ayarlar.zaman_metni(), **ek})


# ============================================================================= sekmeler
def _ticket_sekmesi(conn: sqlite3.Connection, k: dict, guzergah: bool) -> _JSON:
    musteri = _musteri_gorur(k)
    fotolar = ek_dosya.sayilar(conn)
    kosul = "COALESCE(t.tur,'') = 'guzergah'" if guzergah else "COALESCE(t.tur,'') <> 'guzergah'"
    satirlar = conn.execute(
        "SELECT t.id, t.ticket_no, t.acilis, t.location_id, t.site, t.konu, t.durum, t.musteri, t.kanal, t.detay, "
        "t.bina_serial, b.bolge, b.ilce, b.mahalle, t.onedesk_ekip, t.kategori, t.kaynak, t.olusturma "
        f"FROM ticket t LEFT JOIN bina b ON b.bina_serial=t.bina_serial WHERE {kosul} "
        "ORDER BY COALESCE(t.acilis, substr(t.olusturma,1,10)) DESC, t.id DESC").fetchall()
    # PS26'daki sütun sırası önce (Ticket, Baslangic, Lokasyon, Site, Konu, Durum, Musteri, Kanal, Detay), bizim
    # eklediklerimiz sonra. Güzergah'ta ticket no ve konu hep aynı/boş olduğu için yok.
    sutunlar = [_sutun("id", "Kimlik", "sayi", gizli=True)]
    if not guzergah:
        sutunlar.append(_sutun("ticket_no", "Ticket", genislik=128))
    sutunlar += [_sutun("acilis", "Başlangıç", "tarih", 104),
                 _sutun("location_id", "Lokasyon", genislik=120),
                 _sutun("site", "Site", genislik=220, kartta="baslik")]
    if not guzergah:
        sutunlar.append(_sutun("konu", "Konu", genislik=96))
    sutunlar.append(_sutun("durum", "Durum", "durum", 112, kartta="alt"))
    if musteri:
        sutunlar.append(_sutun("musteri", "Müşteri", genislik=150))
    sutunlar += [_sutun("kanal", "Kanal", genislik=92),
                 _sutun("detay", "Detay", genislik=260),
                 _sutun("acik_gun", "Açık gün", "sayi", 84),
                 _sutun("bina_serial", "Bina Serial", genislik=140),
                 _sutun("bolge", "Bölge", "sayi", 72),
                 _sutun("ilce", "İlçe", genislik=110),
                 _sutun("mahalle", "Mahalle", genislik=140)]
    if not guzergah:
        sutunlar += [_sutun("onedesk_ekip", "OneDesk ekibi", genislik=128),
                     _sutun("kategori", "Başlık", genislik=220)]
    sutunlar += [_sutun("foto", "Foto", "sayi", 64),
                 _sutun("kaynak", "Kaynak", genislik=96)]
    veri = []
    for r in satirlar:
        acik = r["durum"] in ticket.ACIK_DURUMLAR
        deger = {
            "id": r["id"], "ticket_no": r["ticket_no"] or "", "acilis": r["acilis"] or (r["olusturma"] or "")[:10],
            "location_id": r["location_id"] or "", "site": r["site"] or "", "konu": r["konu"], "durum": r["durum"],
            "musteri": r["musteri"] or "", "kanal": r["kanal"] or "", "detay": (r["detay"] or "").replace("\n", " "),
            "acik_gun": _gun_farki(r["acilis"]) if acik else None, "bina_serial": r["bina_serial"] or "",
            "bolge": r["bolge"], "ilce": r["ilce"] or "", "mahalle": r["mahalle"] or "",
            "onedesk_ekip": r["onedesk_ekip"] or "", "kategori": r["kategori"] or "",
            "foto": fotolar.get(int(r["id"])) or None,
            "kaynak": "Excel" if r["kaynak"] == "excel" else "Uygulama",
        }
        veri.append([deger[s["anahtar"]] for s in sutunlar])
    sekme = "guzergah" if guzergah else "ticketlar"
    if musteri:
        _erisim(conn, k, f"tablo_{sekme}", len(veri))
    acik = sum(1 for r in satirlar if r["durum"] in ticket.ACIK_DURUMLAR)
    return _yanit(sekme, sutunlar, veri, ozet={"acik": acik, "foto": sum(fotolar.values())})


def _altyapi_satiri(r: sqlite3.Row | dict, musteri: bool) -> dict:
    r = dict(r)
    d = {"id": r["id"], "baslangic": r["baslangic"] or "", "kanal": r["kanal"] or "", "satici_ad": r["satici_ad"] or "",
         "bolge": r["bolge"] or "", "durum": ALTYAPI_ETIKET.get(r["durum"], r["durum"]), "durum_kod": r["durum"],
         "bekleme_gun": _gun_farki(r["baslangic"]) if r["durum"] == "bekliyor" else None,
         "bina_serial": r["bina_serial"] or "", "notu": r["notu"] or "", "guncelleme": r["guncelleme"] or "",
         "kaynak": "Excel" if (r.get("aktarim_anahtari") or "").startswith("ps26:") else "Uygulama"}
    if musteri:
        d["musteri_no"] = r["musteri_no"] or ""
    return d


def _altyapi_sutunlari(musteri: bool) -> list[dict]:
    s = [_sutun("id", "Kimlik", "sayi", gizli=True),
         _sutun("baslangic", "Başlangıç", "tarih", 104)]
    if musteri:
        s.append(_sutun("musteri_no", "Müşteri", genislik=120, kartta="baslik"))
    s += [_sutun("kanal", "Kanal", genislik=92),
          _sutun("satici_ad", "Satıcı", genislik=170, kartta=None if musteri else "baslik"),
          _sutun("bolge", "Bölge", genislik=150),
          _sutun("durum", "Durum", "durum", 104, kartta="alt"),
          _sutun("bekleme_gun", "Bekleyen gün", "sayi", 100),
          _sutun("bina_serial", "Bina", genislik=140),
          _sutun("notu", "Not", genislik=240),
          _sutun("kaynak", "Kaynak", genislik=92),
          _sutun("guncelleme", "Son değişiklik", "tarih", 132)]
    return s


def _altyapi_sekmesi(conn: sqlite3.Connection, k: dict) -> _JSON:
    musteri = _musteri_gorur(k)
    satirlar = conn.execute(
        "SELECT * FROM altyapi_bekleyen ORDER BY CASE durum WHEN 'bekliyor' THEN 0 ELSE 1 END, "
        "COALESCE(baslangic, substr(olusturma,1,10)), id").fetchall()
    sutunlar = _altyapi_sutunlari(musteri)
    veri = []
    for r in satirlar:
        d = _altyapi_satiri(r, musteri)
        veri.append([d[s["anahtar"]] for s in sutunlar])
    if musteri:
        _erisim(conn, k, "tablo_altyapi", len(veri))
    # PVT'nin yerine (türetilir, saklanmaz): satıcı başına bekleyen / kurulan / iptal.
    pivot = ps26_aktar.satici_ozeti(conn)
    pivot_sutun = [_sutun("satici", "Satıcı", genislik=200, kartta="baslik"),
                   _sutun("bekliyor", "Bekliyor", "sayi", 96), _sutun("kuruldu", "Kuruldu", "sayi", 96),
                   _sutun("iptal", "İptal", "sayi", 84), _sutun("toplam", "Toplam", "sayi", 84)]
    bekleyen = [r for r in satirlar if r["durum"] == "bekliyor"]
    en_eski = max((_gun_farki(r["baslangic"]) or 0 for r in bekleyen), default=None)
    return _yanit("altyapi", sutunlar, veri,
                  pivot={"sutunlar": pivot_sutun, "satirlar": [[p[s["anahtar"]] for s in pivot_sutun] for p in pivot]},
                  ozet={"bekliyor": len(bekleyen), "en_eski_gun": en_eski, "satici": len(pivot)})


def _bina_sekmesi(conn: sqlite3.Connection) -> _JSON:
    acik = {r[0]: int(r[1]) for r in conn.execute(
        "SELECT bina_serial, COUNT(*) FROM ticket WHERE bina_serial IS NOT NULL "
        "AND durum IN ('AÇIK','HATA','TRANSFER') GROUP BY bina_serial")}
    sutunlar = [_sutun("bina_serial", "Bina Serial", genislik=140),
                _sutun("tellcordia_id", "Tellcordia ID", genislik=132),
                _sutun("location_id", "Location Id", genislik=116),
                _sutun("obek", "Öbek Adı", genislik=160),
                _sutun("site", "Site Adı", genislik=220, kartta="baslik"),
                _sutun("ad", "Adı", genislik=200),
                _sutun("ilce", "İlçe", genislik=110, kartta="alt"),
                _sutun("mahalle", "Mahalle", genislik=140),
                _sutun("bolge", "Bölge", "sayi", 72),
                _sutun("toplam_hp", "Toplam HP", "sayi", 92),
                _sutun("res_hp", "RES HP", "sayi", 84),
                _sutun("aktif_res", "Aktif abone", "sayi", 96),
                _sutun("firsat", "Fırsat", "sayi", 80),
                _sutun("sales_ready", "Sales Ready", "tarih", 108),
                _sutun("teknoloji", "Teknoloji", genislik=100),
                _sutun("protokol_segment", "Protokol Segment", genislik=150),
                _sutun("acik_ticket", "Açık ticket", "sayi", 96),
                _sutun("durum", "Durum", genislik=84)]
    veri = []
    for r in conn.execute(
            "SELECT bina_serial, tellcordia_id, location_id, obek, crm_site_adi, site_adi, ad, ilce, mahalle, bolge, "
            "toplam_hp, res_hp, aktif_res, firsat, sales_ready, teknoloji, protokol_segment, pasif "
            "FROM bina ORDER BY bina_serial"):
        veri.append([r[0], r[1] or "", r[2] or "", r[3] or "", (r[4] or r[5] or ""), r[6] or "", r[7] or "",
                     r[8] or "", r[9], r[10], r[11], r[12], r[13], (r[14] or "")[:10], r[15] or "", r[16] or "",
                     acik.get(r[0]) or None, "Pasif" if r[17] else "Aktif"])
    return _yanit("binalar", sutunlar, veri, kimlik="bina_serial")


# ============================================================================= uçlar
yonlendirici = APIRouter()


def _say(conn: sqlite3.Connection, sql: str, *deger) -> int | None:
    try:
        return int(conn.execute(sql, deger).fetchone()[0])
    except sqlite3.Error:
        return None


@yonlendirici.get("/api/tablolar")
def tablolar_ozet(k: dict = Depends(izin("tablolar.oku")), conn: sqlite3.Connection = Depends(baglanti)):
    kapali = ",".join(f"'{d}'" for d in KAPALI_IS_DURUMLARI)
    sayilar = {
        "ticketlar": _say(conn, "SELECT COUNT(*) FROM ticket WHERE COALESCE(tur,'') <> 'guzergah'"),
        "guzergah": _say(conn, "SELECT COUNT(*) FROM ticket WHERE tur='guzergah'"),
        "altyapi": _say(conn, "SELECT COUNT(*) FROM altyapi_bekleyen"),
        "binalar": _say(conn, "SELECT COUNT(*) FROM bina"),
        "isler": _say(conn, f"SELECT COUNT(*) FROM is_emri WHERE durum NOT IN ({kapali})") if izinli(k, "is.liste") else None,
    }
    sekmeler = [{"anahtar": a, "ad": ad, "satir": sayilar[a]} for a, ad in SEKMELER.items()
                if a != "isler" or izinli(k, "is.liste")]
    en_eski = _say(conn, "SELECT CAST(julianday(?) - julianday(MIN(baslangic)) AS INTEGER) FROM altyapi_bekleyen "
                   "WHERE durum='bekliyor' AND baslangic IS NOT NULL", ayarlar.bugun().isoformat())
    return {
        "sunucu_zamani": ayarlar.zaman_metni(), "sekmeler": sekmeler,
        "ozet": {
            "ticket_takipte": _say(conn, "SELECT COUNT(*) FROM ticket WHERE COALESCE(tur,'') <> 'guzergah' "
                                         "AND durum IN ('AÇIK','HATA','TRANSFER')"),
            "guzergah_acik": _say(conn, "SELECT COUNT(*) FROM ticket WHERE tur='guzergah' "
                                        "AND durum IN ('AÇIK','HATA','TRANSFER')"),
            "altyapi_bekliyor": _say(conn, "SELECT COUNT(*) FROM altyapi_bekleyen WHERE durum='bekliyor'"),
            "altyapi_en_eski_gun": en_eski,
            "foto": _say(conn, "SELECT COUNT(*) FROM ticket_ek"),
            "ps26_son_aktarim": db.ayar_oku(conn, "ps26_son_aktarim"),
        },
    }


@yonlendirici.get("/api/tablolar/{sekme}")
def tablo(sekme: str, k: dict = Depends(izin("tablolar.oku")), conn: sqlite3.Connection = Depends(baglanti)):
    if sekme == "ticketlar":
        return _ticket_sekmesi(conn, k, guzergah=False)
    if sekme == "guzergah":
        return _ticket_sekmesi(conn, k, guzergah=True)
    if sekme == "altyapi":
        return _altyapi_sekmesi(conn, k)
    if sekme == "binalar":
        return _bina_sekmesi(conn)
    raise hata(404, "Böyle bir tablo yok.", "tablo_yok")


# ----------------------------------------------------------------------------- altyapı bekleyen: yazma
class AltyapiGirdi(BaseModel):
    model_config = ConfigDict(extra="ignore")
    musteri_no: str | None = Field(default=None, max_length=60)
    kanal: str | None = Field(default=None, max_length=40)
    baslangic: str | None = Field(default=None, max_length=20)
    satici_ad: str | None = Field(default=None, max_length=120)
    bolge: str | None = Field(default=None, max_length=120)
    bina_serial: str | None = Field(default=None, max_length=40)
    notu: str | None = Field(default=None, max_length=1000)


class AltyapiGuncelle(BaseModel):
    model_config = ConfigDict(extra="ignore")
    durum: str | None = None
    notu: str | None = Field(default=None, max_length=1000)
    bina_serial: str | None = Field(default=None, max_length=40)


def _bina_denetle(conn: sqlite3.Connection, serial: str | None) -> str | None:
    serial = (serial or "").strip() or None
    if serial and not conn.execute("SELECT 1 FROM bina WHERE bina_serial=?", (serial,)).fetchone():
        raise hata(404, "Bina bulunamadı.", "bina_yok")
    return serial


@yonlendirici.post("/api/tablolar/altyapi", status_code=201)
def altyapi_ekle(girdi: AltyapiGirdi, k: dict = Depends(izin("ticket.defter")),
                 conn: sqlite3.Connection = Depends(baglanti)):
    v = {a: (str(d).strip() or None) if d is not None else None for a, d in girdi.model_dump().items()}
    if not (v["musteri_no"] or v["satici_ad"] or v["bina_serial"]):
        raise hata(422, "Müşteri no, satıcı ya da bina gerekli.", "alan_eksik")
    baslangic = ticket._tarih(v["baslangic"]) if v["baslangic"] else ayarlar.bugun().isoformat()
    if v["baslangic"] and not baslangic:
        raise hata(422, "Başlangıç tarihi GG.AA.YYYY ya da YYYY-AA-GG olmalı.", "alan_eksik")
    serial = _bina_denetle(conn, v["bina_serial"])
    simdi = ayarlar.zaman_metni()
    imlec = conn.execute(
        "INSERT INTO altyapi_bekleyen (musteri_no, kanal, baslangic, satici_ad, bolge, bina_serial, durum, notu, "
        "aktarim_anahtari, olusturma, guncelleme) VALUES (?,?,?,?,?,?,'bekliyor',?,NULL,?,?)",
        (v["musteri_no"], ticket._tr_ust(v["kanal"] or "") or None, baslangic, v["satici_ad"], v["bolge"], serial,
         v["notu"], simdi, simdi))
    db.yonetim_kaydi(conn, k, "altyapi_ekle", str(imlec.lastrowid), None)
    conn.commit()
    r = conn.execute("SELECT * FROM altyapi_bekleyen WHERE id=?", (imlec.lastrowid,)).fetchone()
    return {"kayit": _altyapi_satiri(r, _musteri_gorur(k)), "mesaj": "Kayıt eklendi."}


@yonlendirici.patch("/api/tablolar/altyapi/{kayit_id}")
def altyapi_guncelle(kayit_id: int, girdi: AltyapiGuncelle, k: dict = Depends(izin("ticket.defter")),
                     conn: sqlite3.Connection = Depends(baglanti)):
    eski = conn.execute("SELECT * FROM altyapi_bekleyen WHERE id=?", (kayit_id,)).fetchone()
    if not eski:
        raise hata(404, "Kayıt bulunamadı.", "kayit_yok")
    alanlar = girdi.model_dump(exclude_unset=True)
    yeni: dict = {}
    if "durum" in alanlar and alanlar["durum"] is not None:
        durum = str(alanlar["durum"]).strip().lower()
        if durum not in ps26_aktar.ALTYAPI_DURUMLARI:
            raise hata(422, "Durum 'bekliyor', 'kuruldu' ya da 'iptal' olmalı.", "durum_gecersiz")
        yeni["durum"] = durum
    if "notu" in alanlar:
        yeni["notu"] = (alanlar["notu"] or "").strip() or None
    if "bina_serial" in alanlar:
        yeni["bina_serial"] = _bina_denetle(conn, alanlar["bina_serial"])
    yeni = {a: d for a, d in yeni.items() if d != eski[a]}
    if yeni:
        atama = ", ".join(f"{a}=?" for a in yeni)
        conn.execute(f"UPDATE altyapi_bekleyen SET {atama}, guncelleme=? WHERE id=?",
                     (*yeni.values(), ayarlar.zaman_metni(), kayit_id))
        # Yönetim kaydına değer değil yalnız alan adları ve durum (not metni kişisel bilgi içerebilir).
        db.yonetim_kaydi(conn, k, "altyapi_guncelle", str(kayit_id),
                         {"alanlar": sorted(yeni), **({"durum": yeni["durum"]} if "durum" in yeni else {})})
        conn.commit()
    r = conn.execute("SELECT * FROM altyapi_bekleyen WHERE id=?", (kayit_id,)).fetchone()
    return {"kayit": _altyapi_satiri(r, _musteri_gorur(k)), "degisti": bool(yeni)}


# ----------------------------------------------------------------------------- PS26 aktarımı
def _klasor_bilgisi(conn: sqlite3.Connection) -> dict:
    klasor = ps26_aktar.klasor_bul(conn)
    if klasor is None:
        return {"bulundu": False}
    xlsx = klasor / "data.xlsx"
    zipler = ps26_aktar.arsivler(klasor / "imgs")
    bilgi = xlsx.stat()
    return {
        "bulundu": True,
        # Tam yol kullanıcı adını içerir; ekranda son iki parça yeter.
        "yer": "\\".join(klasor.parts[-2:]),
        "dosya": {"ad": xlsx.name, "boyut": bilgi.st_size,
                  "degisme": ayarlar.zaman_metni(dt.datetime.fromtimestamp(bilgi.st_mtime))[:16]},
        "zip": len(zipler) if zipler is not None else None,
    }


@yonlendirici.get("/api/ps26")
def ps26_durum(k: dict = Depends(izin("ticket.defter")), conn: sqlite3.Connection = Depends(baglanti)):
    return {"klasor": _klasor_bilgisi(conn), "son_aktarim": db.ayar_oku(conn, "ps26_son_aktarim"),
            "en_buyuk_bayt": EN_BUYUK_XLSX}


async def _yuklenenleri_kaydet(istek: Request, dizin: Path) -> tuple[Path | None, list[Path]]:
    """Multipart: ``dosya`` (data.xlsx) + istenen kadar ``zip``. Ham gövde: yalnız xlsx (``X-Dosya-Adi``)."""
    uzunluk = int(istek.headers.get("content-length") or 0)
    if uzunluk > EN_BUYUK_TOPLAM:
        raise hata(413, "Gönderilen dosyalar çok büyük (en çok 250 MB).", "dosya_buyuk")
    tur = (istek.headers.get("content-type") or "").lower()
    xlsx: Path | None = None
    zipler: list[Path] = []
    if tur.startswith("multipart/form-data"):
        form = await istek.form(max_files=500)
        for i, (alan, deger) in enumerate(form.multi_items()):
            if not hasattr(deger, "read"):
                continue
            ad = Path(getattr(deger, "filename", "") or f"dosya{i}").name
            icerik = await deger.read()
            if alan == "zip" or ad.lower().endswith(".zip"):
                if len(icerik) > EN_BUYUK_ZIP:
                    raise hata(413, f"{ad} çok büyük (en çok 60 MB).", "dosya_buyuk")
                # Arşivin adı eşleşme anahtarıdır (müşteri/ticket no): ad korunur, çakışırsa sıra eklenir.
                hedef = dizin / "imgs" / ad
                hedef.parent.mkdir(parents=True, exist_ok=True)
                hedef.write_bytes(icerik)
                zipler.append(hedef)
            else:
                if len(icerik) > EN_BUYUK_XLSX:
                    raise hata(413, "data.xlsx çok büyük (en çok 80 MB).", "dosya_buyuk")
                xlsx = dizin / "data.xlsx"
                xlsx.write_bytes(icerik)
        return xlsx, zipler
    govde = await istek.body()
    if govde:
        if len(govde) > EN_BUYUK_XLSX:
            raise hata(413, "data.xlsx çok büyük (en çok 80 MB).", "dosya_buyuk")
        xlsx = dizin / "data.xlsx"
        xlsx.write_bytes(govde)
    return xlsx, zipler


@yonlendirici.post("/api/ps26/aktar")
async def ps26_aktar_ucu(istek: Request, kuru: bool = Query(default=True), klasor: bool = Query(default=False),
                         k: dict = Depends(izin("ticket.defter")), conn: sqlite3.Connection = Depends(baglanti)):
    """Önce önizleme (``kuru=1``, varsayılan): hiçbir şey yazılmaz. ``kuru=0`` → doğrulanmış yedek, sonra aktarım.

    ``klasor=1``: sunucunun bilgisayarındaki PS26 klasöründen (data.xlsx + imgs/*.zip) okunur, dosya gönderilmez.
    """
    if not _aktarim_kilidi.acquire(blocking=False):
        raise hata(409, "Şu an başka bir PS26 aktarımı sürüyor. Bir dakika sonra deneyin.", "aktarim_suruyor")
    try:
        with tempfile.TemporaryDirectory(prefix="saha-ps26-") as gecici:
            dizin = Path(gecici)
            if klasor:
                bulunan = ps26_aktar.klasor_bul(conn)
                if bulunan is None:
                    raise hata(404, "PS26 klasörü bu bilgisayarda bulunamadı. data.xlsx'i seçip gönderin.",
                               "klasor_yok")
                xlsx, imgs, zipler = bulunan / "data.xlsx", bulunan / "imgs", None
            else:
                xlsx, zipler = await _yuklenenleri_kaydet(istek, dizin)
                imgs = None
                if xlsx is None:
                    raise hata(400, "data.xlsx gönderilmedi.", "dosya_yok")
            return await run_in_threadpool(_aktar, conn, xlsx, imgs, zipler or None, kuru, k)
    finally:
        _aktarim_kilidi.release()


def _aktar(conn: sqlite3.Connection, xlsx: Path, imgs: Path | None, zipler: list[Path] | None, kuru: bool,
           k: dict) -> dict:
    from . import yedekle

    try:
        okuma = ps26_aktar.oku(xlsx, imgs=imgs, zipler=zipler)
    except ps26_aktar.Ps26Hatasi as exc:
        raise hata(422, exc.mesaj, exc.kod) from exc
    yedek = None
    if not kuru:
        try:
            yedek = str(yedekle.aktarim_yedegi(db.db_yolu()))
        except yedekle.YedekHatasi as exc:
            raise hata(503, "Güvenlik yedeği alınamadı; hiçbir şey değiştirilmedi. Diskte yer var mı?",
                       "yedek_alinamadi") from exc
    sonuc = ps26_aktar.aktar(conn, okuma, kuru=kuru, k=k)
    sonuc["yedek"] = Path(yedek).name if yedek else None
    return sonuc
