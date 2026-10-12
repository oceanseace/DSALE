"""Tablolar (Ek-8, Ek-9): sayfa sekmeli tablo görüntüleyicisinin uçları (Excel alışkanlığı).

Sayfalar veritabanından, girişle ve görevle süzülerek gelir. PS26 içe aktarımı ve Güzergah sayfası 2026-10'da
kaldırıldı (aktarılmış veri ``ticket_temizlik.ps26_calistir`` ile yedekli silinir):

    GET  /api/tablolar                 sekmeler ve satır sayıları + ekranın hikâye cümlesi için birkaç sayı
    GET  /api/tablolar/{sekme}         ticketlar · altyapi · binalar  (İşler sekmesi /api/isler'i kullanır)
    POST /api/tablolar/altyapi         altyapı bekleyen satışa yeni satır
    PATCH /api/tablolar/altyapi/{id}   durum (bekliyor · kuruldu · iptal), not, bina

Yanıt biçimi her sekmede aynıdır (arayüz tek bileşenle çizer): ``{sutunlar:[{anahtar, baslik, tur, …}],
satirlar:[[…], …]}`` — satır dizi, sütun sırası ``sutunlar`` ile aynı; ilk sütun gizli kimliktir.

Kişisel veri: müşteri numarası yalnız ``is.musteri`` izniyle döner (izinsizde sütun HİÇ yoktur) ve döndüğü her
liste ``erisim_kaydi``'na adetle yazılır (spec §2.5). Satıcı adları çalışan adıdır; tabloyu açan görevler görür.
"""
from __future__ import annotations

import datetime as dt
import json
import sqlite3

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from . import ayarlar, db, ek_dosya, ticket
from .api_ortak import erisim_yaz
from .yetki import KAPALI_IS_DURUMLARI, baglanti, hata, izin, izinli

# Bu modülün uçlarının izinleri (``saha/api.py`` → ``rota_izni_ekle``). Okuma ``tablolar.oku``; yazan uçlar
# ticket defterini tutan görevlerin (``ticket.defter``: operasyon + yönetici).
ROTA_IZNI: dict[tuple[str, str], str] = {
    ("GET", "/api/tablolar"): "tablolar.oku",
    ("GET", "/api/tablolar/{sekme}"): "tablolar.oku",
    ("POST", "/api/tablolar/altyapi"): "ticket.defter",
    ("PATCH", "/api/tablolar/altyapi/{kayit_id}"): "ticket.defter",
}

SEKMELER = {
    "ticketlar": "Ticketlar",
    "altyapi": "Altyapı bekleyen",
    "binalar": "Binalar",
    "isler": "İşler",
}
ALTYAPI_DURUMLARI = ("bekliyor", "kuruldu", "iptal")
ALTYAPI_ETIKET = {"bekliyor": "Bekliyor", "kuruldu": "Kuruldu", "iptal": "İptal"}


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


def _musteri_gorur(k: dict) -> bool:
    return izinli(k, "is.musteri")


def _yanit(sekme: str, sutunlar: list[dict], satirlar: list[list], kimlik: str = "id", **ek) -> _JSON:
    """``kimlik``: satırı açarken kullanılan sütun (ticket/altyapı 'id' — gizli; bina 'bina_serial')."""
    return _JSON({"sekme": sekme, "ad": SEKMELER.get(sekme, sekme), "sutunlar": sutunlar, "satirlar": satirlar,
                  "kimlik": kimlik, "toplam": len(satirlar), "sunucu_zamani": ayarlar.zaman_metni(), **ek})


# ============================================================================= sekmeler
def _ticket_sekmesi(conn: sqlite3.Connection, k: dict) -> _JSON:
    musteri = _musteri_gorur(k)
    fotolar = ek_dosya.sayilar(conn)
    satirlar = conn.execute(
        "SELECT t.id, t.ticket_no, t.acilis, t.location_id, t.site, t.konu, t.durum, t.musteri, t.kanal, t.detay, "
        "t.bina_serial, b.bolge, b.ilce, b.mahalle, t.onedesk_ekip, t.kategori, t.kaynak, t.olusturma "
        "FROM ticket t LEFT JOIN bina b ON b.bina_serial=t.bina_serial "
        "ORDER BY COALESCE(t.acilis, substr(t.olusturma,1,10)) DESC, t.id DESC").fetchall()
    # Excel TICKET sayfasının sütun sırası önce (Ticket, Baslangic, Lokasyon, Site, Konu, Durum, Musteri, Kanal,
    # Detay), bizim eklediklerimiz sonra.
    sutunlar = [_sutun("id", "Kimlik", "sayi", gizli=True),
                _sutun("ticket_no", "Ticket", genislik=128),
                _sutun("acilis", "Başlangıç", "tarih", 104),
                _sutun("location_id", "Lokasyon", genislik=120),
                _sutun("site", "Site", genislik=220, kartta="baslik"),
                _sutun("konu", "Konu", genislik=96),
                _sutun("durum", "Durum", "durum", 112, kartta="alt")]
    if musteri:
        sutunlar.append(_sutun("musteri", "Müşteri", genislik=150))
    sutunlar += [_sutun("kanal", "Kanal", genislik=92),
                 _sutun("detay", "Detay", genislik=260),
                 _sutun("acik_gun", "Açık gün", "sayi", 84),
                 _sutun("bina_serial", "Bina Serial", genislik=140),
                 _sutun("bolge", "Bölge", "sayi", 72),
                 _sutun("ilce", "İlçe", genislik=110),
                 _sutun("mahalle", "Mahalle", genislik=140),
                 _sutun("onedesk_ekip", "OneDesk ekibi", genislik=128),
                 _sutun("kategori", "Başlık", genislik=220),
                 _sutun("foto", "Foto", "sayi", 64),
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
    if musteri:
        erisim_yaz(conn, k, "tablo_ticketlar", len(veri))
    acik = sum(1 for r in satirlar if r["durum"] in ticket.ACIK_DURUMLAR)
    return _yanit("ticketlar", sutunlar, veri, ozet={"acik": acik, "foto": sum(fotolar.values())})


def _altyapi_satiri(r: sqlite3.Row | dict, musteri: bool) -> dict:
    r = dict(r)
    d = {"id": r["id"], "baslangic": r["baslangic"] or "", "kanal": r["kanal"] or "", "satici_ad": r["satici_ad"] or "",
         "bolge": r["bolge"] or "", "durum": ALTYAPI_ETIKET.get(r["durum"], r["durum"]), "durum_kod": r["durum"],
         "bekleme_gun": _gun_farki(r["baslangic"]) if r["durum"] == "bekliyor" else None,
         "bina_serial": r["bina_serial"] or "", "notu": r["notu"] or "", "guncelleme": r["guncelleme"] or "",
         "kaynak": "Excel" if r.get("aktarim_anahtari") else "Uygulama"}
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
        erisim_yaz(conn, k, "tablo_altyapi", len(veri))
    # Satıcı başına bekleyen / kurulan / iptal (türetilir, saklanmaz).
    pivot = satici_ozeti(conn)
    pivot_sutun = [_sutun("satici", "Satıcı", genislik=200, kartta="baslik"),
                   _sutun("bekliyor", "Bekliyor", "sayi", 96), _sutun("kuruldu", "Kuruldu", "sayi", 96),
                   _sutun("iptal", "İptal", "sayi", 84), _sutun("toplam", "Toplam", "sayi", 84)]
    bekleyen = [r for r in satirlar if r["durum"] == "bekliyor"]
    en_eski = max((_gun_farki(r["baslangic"]) or 0 for r in bekleyen), default=None)
    return _yanit("altyapi", sutunlar, veri,
                  pivot={"sutunlar": pivot_sutun, "satirlar": [[p[s["anahtar"]] for s in pivot_sutun] for p in pivot]},
                  ozet={"bekliyor": len(bekleyen), "en_eski_gun": en_eski, "satici": len(pivot)})


def satici_ozeti(conn: sqlite3.Connection) -> list[dict]:
    """Satıcı başına bekleyen / kurulan / iptal sayısı (türetilir, saklanmaz)."""
    try:
        satirlar = conn.execute(
            "SELECT COALESCE(NULLIF(TRIM(satici_ad),''), '(Satıcı yok)') AS satici, "
            "SUM(durum='bekliyor') AS bekliyor, SUM(durum='kuruldu') AS kuruldu, SUM(durum='iptal') AS iptal, "
            "COUNT(*) AS toplam FROM altyapi_bekleyen GROUP BY 1 ORDER BY 2 DESC, 5 DESC, 1").fetchall()
    except sqlite3.OperationalError:
        return []
    return [dict(r) for r in satirlar]


def _bina_sekmesi(conn: sqlite3.Connection) -> _JSON:
    acik = {r[0]: int(r[1]) for r in conn.execute(
        "SELECT bina_serial, COUNT(*) FROM ticket WHERE bina_serial IS NOT NULL "
        "AND durum IN ('AÇIK','HATA','TRANSFER','BÖLGE') GROUP BY bina_serial")}
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
    """Tek sayı; tablo yoksa ya da sonuç NULL ise (ör. bekleyen yokken MIN) None — ekran hata kutusu göstermesin."""
    try:
        r = conn.execute(sql, deger).fetchone()
    except sqlite3.Error:
        return None
    return int(r[0]) if r and r[0] is not None else None


@yonlendirici.get("/api/tablolar")
def tablolar_ozet(k: dict = Depends(izin("tablolar.oku")), conn: sqlite3.Connection = Depends(baglanti)):
    kapali = ",".join(f"'{d}'" for d in KAPALI_IS_DURUMLARI)
    sayilar = {
        "ticketlar": _say(conn, "SELECT COUNT(*) FROM ticket"),
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
            "ticket_takipte": _say(conn, "SELECT COUNT(*) FROM ticket WHERE durum IN ('AÇIK','HATA','TRANSFER','BÖLGE')"),
            "altyapi_bekliyor": _say(conn, "SELECT COUNT(*) FROM altyapi_bekleyen WHERE durum='bekliyor'"),
            "altyapi_en_eski_gun": en_eski,
            "foto": _say(conn, "SELECT COUNT(*) FROM ticket_ek"),
        },
    }


@yonlendirici.get("/api/tablolar/{sekme}")
def tablo(sekme: str, k: dict = Depends(izin("tablolar.oku")), conn: sqlite3.Connection = Depends(baglanti)):
    if sekme == "ticketlar":
        return _ticket_sekmesi(conn, k)
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
        if durum not in ALTYAPI_DURUMLARI:
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
