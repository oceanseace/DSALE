"""Her yerden arama (Ctrl+F / Ctrl+K komut paleti, haritada "Location ID ile git").

    GET /api/ara?q=<metin>&tur=<bina|is|kisi|mahalle|obek>

Yanıt gruplu döner, grup başına en çok ``GRUP_SINIRI`` sonuç (``tur`` verilirse o grup ``TUR_SINIRI``) ve
grubun TOPLAM eşleşme sayısı::

    {"q": "...", "gruplar": [{"tur": "bina", "baslik": "Binalar", "toplam": 37, "sonuclar": [...]}, ...],
     "toplam": 41, "sure_ms": 3.2}

İzin süzgeci SUNUCUDADIR (arayüz yalnız gelen sonucu çizer); izin ADLARI ``yetki.IZINLER``'dendir:

* Binalar  — ``bina_gorebilir`` ile aynı kapsam: operasyon/yönetici hepsi; satış kendi bölgesi + son
  günlerdeki listesi (``listesinde_mi`` penceresi); teknik yalnız kendisine atanmış açık işin binası.
* İşler    — ``is.liste``. Teknik (ofis görevi yoksa) yalnız kendisine atanmış işleri bulur ve yalnız iş/task
  no ile; müşteri adı/no ile arama ve sonuçta müşteri adı yalnız ofis görevlerinde (``is.musteri`` +
  operasyon/yönetici; ``operasyon.v2.gorunum.musteri_izni`` 'tam' ile aynı kural). Müşteri alanı dönen her
  yanıt ``erisim_kaydi``'na adetle yazılır (spec §2.5).
* Kişiler  — ``ekip.yonet`` herkes (ad ya da telefon); ``ekip.teknikler`` yalnız teknikler (ad). Sonuçta
  telefon numarası DÖNMEZ.
* Mahalle  — ``geometri.oku``;  Öbek — ``obek.oku``.

Müşteri adları veritabanında düz metindir (``gizli.key`` yalnız jeton imza anahtarıdır, alan şifrelemesi
yok); yine de müşteri adı araması yalnız tam yetkili görevlere açıktır.

Hız: binalar (≈20 bin) bellekte normalleştirilmiş anahtar listesi olarak tutulur (veritabanı yolu +
bina sayısı + ``bina_degisim`` son kimliği değişince ya da ``ONBELLEK_SN`` dolunca yeniden kurulur);
işler kısa ömürlü (``IS_ONBELLEK_SN``) önbellekte. Tablo/indeks eklenmez (göç gerekmez).
"""
from __future__ import annotations

import datetime as dt
import re
import sqlite3
import threading
import time

from fastapi import APIRouter, Depends, Query

from . import ayarlar
from .api_ortak import erisim_yaz
from .yetki import ETIKET, KAPALI_IS_DURUMLARI, O, S, T, Y, baglanti, gorevler, izin, izinli

ROTA_IZNI: dict[tuple[str, str], str] = {
    ("GET", "/api/ara"): "oturum",          # herkes arar; ne bulacağı aşağıda görev ve kapsamla süzülür
}

yonlendirici = APIRouter(tags=["arama"])

GRUP_SINIRI = 8
TUR_SINIRI = 40
EN_KISA = 2
ONBELLEK_SN = 300.0
IS_ONBELLEK_SN = 15.0
TURLER = ("bina", "is", "kisi", "mahalle", "obek")
BASLIK = {"bina": "Binalar", "is": "Aboneler / işler", "kisi": "Kişiler", "mahalle": "Mahalleler",
          "obek": "Öbekler"}

# ============================================================================= Türkçe normalleştirme
# operasyon.is_emri.sade ile birebir aynı kural (o modül pandas yükler; açılışı yavaşlatmamak için kopya).
_TR = str.maketrans("ÇĞİÖŞÜÂÎÛ", "CGIOSUAIU")


def sade(s) -> str:
    """'Şükrü Paşa Sitesi' → 'SUKRU PASA SITESI'; harf/rakam dışı her şey tek boşluk."""
    if s is None:
        return ""
    buyuk = str(s).replace("̇", "").replace("i", "İ").replace("ı", "I").upper()
    return re.sub(r"[^A-Z0-9]+", " ", buyuk.translate(_TR)).strip()


def _bitisik(s: str) -> str:
    return s.replace(" ", "")


def _alanlar(*cifter: tuple[str, int]) -> tuple[tuple[str, str, int], ...]:
    """[(sade metin, ağırlık)] → [(metin, boşluksuz metin, ağırlık)] (önbellekte bir kez hesaplanır)."""
    return tuple((m, _bitisik(m), a) for m, a in cifter if m)


def _samanlik(alanlar) -> str:
    """Hızlı ön süzgeç: bütün alanlar (boşluklu + boşluksuz) tek metinde; ``q in`` C hızında elenir."""
    return "|".join(m + "|" + b for m, b, _ in alanlar)


def _puan(alanlar, q: str, qb: str) -> int:
    """Eşleşme puanı (0 = yok). ``alanlar`` = [(metin, boşluksuz, ağırlık)]; tam > önek > kelime başı > içerir."""
    en = 0
    for metin, bitisik, agirlik in alanlar:
        if metin == q or bitisik == qb:
            p = 400
        elif metin.startswith(q) or bitisik.startswith(qb):
            p = 300
        elif (" " + q) in (" " + metin):
            p = 200
        elif q in metin or (len(qb) >= 3 and qb in bitisik):
            p = 100
        else:
            continue
        en = max(en, p + agirlik)
    return en


def _bul(alanlar, q: str, qb: str) -> int:
    return _puan(_alanlar(*alanlar), q, qb)


# ============================================================================= önbellekler
_kilit = threading.Lock()
_bina_onbellek: dict[str, tuple[tuple, float, list]] = {}
_is_onbellek: dict[str, tuple[float, list]] = {}


def _db_anahtari(conn: sqlite3.Connection) -> str:
    try:
        return str(conn.execute("PRAGMA database_list").fetchone()[2] or "bellek")
    except sqlite3.Error:
        return "bellek"


def _bina_damgasi(conn: sqlite3.Connection) -> tuple:
    n = conn.execute("SELECT COUNT(*) FROM bina").fetchone()[0]
    try:
        d = conn.execute("SELECT COALESCE(MAX(id),0) FROM bina_degisim").fetchone()[0]
    except sqlite3.OperationalError:
        d = 0
    return (n, d)


def _binalar(conn: sqlite3.Connection) -> list[dict]:
    anahtar = _db_anahtari(conn)
    damga = _bina_damgasi(conn)
    simdi = time.monotonic()
    with _kilit:
        kayit = _bina_onbellek.get(anahtar)
        if kayit and kayit[0] == damga and simdi - kayit[1] < ONBELLEK_SN:
            return kayit[2]
    liste = []
    for r in conn.execute(
            "SELECT bina_serial, ad, site_adi, crm_site_adi, blok_adi, mahalle, ilce, cadde, sokak, kapi_no, "
            "lat, lon, bolge, location_id, pasif FROM bina"):
        parcalar: list[str] = []
        for x in (r["cadde"], r["sokak"], r["kapi_no"]):        # cadde = sokak tekrarını at
            x = str(x or "").strip()
            if x and x not in parcalar:
                parcalar.append(x)
        adres = " ".join(parcalar)
        liste.append({
            "serial": r["bina_serial"], "ad": r["ad"], "site": r["site_adi"] or r["crm_site_adi"],
            "mahalle": r["mahalle"], "ilce": r["ilce"], "lat": r["lat"], "lon": r["lon"], "bolge": r["bolge"],
            "loc": str(r["location_id"] or "").strip(), "pasif": bool(r["pasif"]), "adres": adres,
        })
        b = liste[-1]
        b["alanlar"] = _alanlar(
            (sade(r["location_id"]), 60), (sade(r["bina_serial"]), 50),
            (sade(" ".join(str(x) for x in (r["site_adi"], r["crm_site_adi"]) if x)), 30),
            (sade(" ".join(str(x) for x in (r["ad"], r["blok_adi"]) if x)), 30),
            (sade(" ".join(str(x) for x in (adres, r["mahalle"], r["ilce"]) if x)), 0))
        b["samanlik"] = _samanlik(b["alanlar"])
    with _kilit:
        _bina_onbellek[anahtar] = (damga, simdi, liste)
    return liste


def _isler(conn: sqlite3.Connection) -> list[dict]:
    anahtar = _db_anahtari(conn)
    simdi = time.monotonic()
    with _kilit:
        kayit = _is_onbellek.get(anahtar)
        if kayit and simdi - kayit[0] < IS_ONBELLEK_SN:
            return kayit[1]
    liste = []
    try:
        satirlar = conn.execute(
            "SELECT e.is_no, e.boss_task_no, e.task_adi, e.durum, e.atanan_id, e.musteri_no, e.musteri_adi, "
            "e.lokasyon, e.mahalle, e.ilce, e.bina_serial, e.lat, e.lon, e.acilis FROM is_emri e").fetchall()
    except sqlite3.OperationalError:          # göç öncesi: is_emri yok
        satirlar = []
    for r in satirlar:
        liste.append({
            "is_no": r["is_no"], "task": r["boss_task_no"], "task_adi": r["task_adi"], "durum": r["durum"],
            "atanan_id": r["atanan_id"], "musteri_no": str(r["musteri_no"] or "").strip(),
            "musteri_adi": r["musteri_adi"], "lokasyon": str(r["lokasyon"] or "").strip(),
            "mahalle": r["mahalle"], "ilce": r["ilce"], "bina_serial": r["bina_serial"],
            "lat": r["lat"], "lon": r["lon"], "acilis": r["acilis"],
            "a_is": _alanlar((sade(r["is_no"]), 60), (sade(r["boss_task_no"]), 60), (sade(r["lokasyon"]), 20)),
            "a_musteri": _alanlar((sade(r["musteri_no"]), 50), (sade(r["musteri_adi"]), 10)),
        })
    with _kilit:
        _is_onbellek[anahtar] = (simdi, liste)
    return liste


def onbellegi_bosalt() -> None:
    with _kilit:
        _bina_onbellek.clear()
        _is_onbellek.clear()


# ============================================================================= gruplar
def _ofis(k: dict) -> bool:
    return bool(gorevler(k) & {O, Y})


def _kapsam_binalari(conn: sqlite3.Connection, k: dict) -> tuple[int | None, set[str]] | None:
    """None = hepsi; değilse (bölge ya da None, ek bina kümesi). ``yetki.bina_gorebilir`` ile aynı kural."""
    kume = gorevler(k)
    if kume & {Y, O}:
        return None
    bolge = None
    ek: set[str] = set()
    if S in kume:
        bolge = int(k.get("bolge") or 0) or None
        sinir = (ayarlar.bugun() - dt.timedelta(days=ayarlar.ZAMAN_GERI_GUN)).isoformat()
        ek |= {r[0] for r in conn.execute(
            "SELECT gb.bina_serial FROM gorev_bina gb JOIN gorev g ON g.id=gb.gorev_id "
            "WHERE g.kullanici_id=? AND g.tarih>=?", (k["id"], sinir))}
    if T in kume:
        try:
            ek |= {r[0] for r in conn.execute(
                "SELECT bina_serial FROM is_emri WHERE atanan_id=? AND bina_serial IS NOT NULL "
                f"AND durum NOT IN ({','.join('?' * len(KAPALI_IS_DURUMLARI))})",
                (k["id"], *KAPALI_IS_DURUMLARI))}
        except sqlite3.OperationalError:
            pass
    return bolge, ek


def _bina_grubu(conn, k, q, qb, sinir) -> tuple[int, list[dict]]:
    if not izinli(k, "bina.oku"):
        return 0, []
    kapsam = _kapsam_binalari(conn, k)
    if kapsam is not None and kapsam[0] is None and not kapsam[1]:
        return 0, []
    bulunan = []
    for b in _binalar(conn):
        if q not in b["samanlik"] and qb not in b["samanlik"]:
            continue
        if kapsam is not None:
            bolge, ek = kapsam
            if not ((bolge is not None and b["bolge"] == bolge) or b["serial"] in ek):
                continue
        p = _puan(b["alanlar"], q, qb)
        if p:
            bulunan.append((p - (5 if b["pasif"] else 0), b))
    bulunan.sort(key=lambda x: (-x[0], x[1]["site"] or x[1]["ad"] or "", x[1]["serial"]))
    sonuc = []
    for p, b in bulunan[:sinir]:
        baslik = b["site"] or b["ad"] or b["serial"]
        alt = " · ".join(x for x in (b["adres"], b["mahalle"], b["ilce"]) if x)
        sonuc.append({"tur": "bina", "id": b["serial"], "baslik": baslik, "alt": alt,
                      "location_id": b["loc"] or None, "serial": b["serial"], "lat": b["lat"], "lon": b["lon"],
                      "bolge": b["bolge"], "pasif": b["pasif"], "puan": p})
    return len(bulunan), sonuc


def _is_grubu(conn, k, q, qb, sinir) -> tuple[int, list[dict], int]:
    """(toplam, sonuçlar, müşteri alanı dönen adet)."""
    if not izinli(k, "is.liste"):
        return 0, [], 0
    ofis = _ofis(k)
    tam_musteri = ofis and izinli(k, "is.musteri")
    if not ofis and T not in gorevler(k):
        return 0, [], 0
    bulunan = []
    for e in _isler(conn):
        if not ofis and e["atanan_id"] != k["id"]:
            continue
        p = _puan(e["a_is"] + e["a_musteri"] if tam_musteri else e["a_is"], q, qb)
        if p:
            bulunan.append((p + (5 if e["durum"] not in KAPALI_IS_DURUMLARI else 0), e))
    bulunan.sort(key=lambda x: (-x[0], str(x[1]["acilis"] or "")))
    sonuc = []
    musteri_adet = 0
    for p, e in bulunan[:sinir]:
        s = {"tur": "is", "id": e["is_no"], "baslik": e["task_adi"] or e["is_no"],
             "alt": " · ".join(x for x in (e["task"] or e["is_no"], e["mahalle"], e["ilce"]) if x),
             "is_no": e["is_no"], "task_no": e["task"], "durum": e["durum"], "acik": e["durum"] not in KAPALI_IS_DURUMLARI,
             "location_id": e["lokasyon"] or None, "bina_serial": e["bina_serial"], "lat": e["lat"], "lon": e["lon"],
             "puan": p}
        if tam_musteri:
            s["musteri_adi"] = e["musteri_adi"]
            s["musteri_no"] = e["musteri_no"] or None
            if e["musteri_adi"]:
                s["baslik"] = e["musteri_adi"]
                s["alt"] = " · ".join(x for x in (e["task_adi"], e["task"] or e["is_no"], e["mahalle"]) if x)
            musteri_adet += 1
        sonuc.append(s)
    return len(bulunan), sonuc, musteri_adet


def _kisi_grubu(conn, k, q, qb, sinir) -> tuple[int, list[dict]]:
    # UI ile aynı: kişi sonucu ekip ekranına (ekip.yonet / yetkinlik.yonet) ya da
    # teknisyen süzgeçli iş listesine (ekip.teknikler) götürür.
    tam = izinli(k, "ekip.yonet") or izinli(k, "yetkinlik.yonet")
    if not tam and not izinli(k, "ekip.teknikler"):
        return 0, []
    rakam = qb.lstrip("0") if qb.isdigit() else ""
    bulunan = []
    teknikler: set[int] = set()
    if not tam:
        try:
            teknikler = {x[0] for x in conn.execute("SELECT kullanici_id FROM kullanici_gorev WHERE rol=?", (T,))}
        except sqlite3.OperationalError:
            pass
    for r in conn.execute("SELECT id, ad, telefon, rol, bolge, aktif, unvan FROM kullanici"):
        if not tam:
            if not r["aktif"] or (r["rol"] != T and r["id"] not in teknikler):
                continue
        p = _bul([(sade(r["ad"]), 20), (sade(r["unvan"]), 0)], q, qb)
        if not p and tam and len(rakam) >= 4 and rakam in str(r["telefon"] or ""):
            p = 250
        if p:
            bulunan.append((p + (5 if r["aktif"] else 0), r))
    bulunan.sort(key=lambda x: (-x[0], x[1]["ad"]))
    sonuc = []
    for p, r in bulunan[:sinir]:
        alt = " · ".join(x for x in (ETIKET.get(r["rol"], r["rol"]), r["unvan"],
                                       f"Bölge {r['bolge']}" if r["bolge"] else None,
                                       None if r["aktif"] else "pasif") if x)
        sonuc.append({"tur": "kisi", "id": r["id"], "baslik": r["ad"], "alt": alt, "rol": r["rol"],
                      "aktif": bool(r["aktif"]), "puan": p})
    return len(bulunan), sonuc


def _mahalle_grubu(conn, k, q, qb, sinir) -> tuple[int, list[dict]]:
    if not izinli(k, "geometri.oku"):
        return 0, []
    try:
        satirlar = conn.execute("SELECT id, ad, ilce, il, lat, lon FROM mahalle").fetchall()
    except sqlite3.OperationalError:
        return 0, []
    bulunan = []
    for r in satirlar:
        p = _bul([(sade(r["ad"]), 20), (sade(f"{r['ad']} {r['ilce']}"), 10)], q, qb)
        if p:
            bulunan.append((p, r))
    bulunan.sort(key=lambda x: (-x[0], x[1]["ad"]))
    return len(bulunan), [{"tur": "mahalle", "id": r["id"], "baslik": r["ad"],
                           "alt": " · ".join(x for x in (r["ilce"], r["il"]) if x),
                           "lat": r["lat"], "lon": r["lon"], "puan": p} for p, r in bulunan[:sinir]]


def _obek_grubu(conn, k, q, qb, sinir) -> tuple[int, list[dict]]:
    if not izinli(k, "obek.oku"):
        return 0, []
    try:
        satirlar = conn.execute("SELECT id, ad, aktif FROM obek").fetchall()
    except sqlite3.OperationalError:
        return 0, []
    bulunan = [(p, r) for r in satirlar if (p := _bul([(sade(r["ad"]), 0)], q, qb))]
    bulunan.sort(key=lambda x: (-x[0], x[1]["ad"]))
    return len(bulunan), [{"tur": "obek", "id": r["id"], "baslik": r["ad"],
                           "alt": "Öbek" + ("" if r["aktif"] else " · pasif"), "puan": p}
                          for p, r in bulunan[:sinir]]


def ara(conn: sqlite3.Connection, k: dict, q: str, tur: str | None = None) -> dict:
    bas = time.perf_counter()
    qs = sade(q)
    qb = _bitisik(qs)
    gruplar = []
    if len(qb) >= EN_KISA:
        sinir = TUR_SINIRI if tur else GRUP_SINIRI
        musteri_adet = 0
        for t in (tur,) if tur else TURLER:
            if t == "bina":
                toplam, sonuc = _bina_grubu(conn, k, qs, qb, sinir)
            elif t == "is":
                toplam, sonuc, musteri_adet = _is_grubu(conn, k, qs, qb, sinir)
            elif t == "kisi":
                toplam, sonuc = _kisi_grubu(conn, k, qs, qb, sinir)
            elif t == "mahalle":
                toplam, sonuc = _mahalle_grubu(conn, k, qs, qb, sinir)
            else:
                toplam, sonuc = _obek_grubu(conn, k, qs, qb, sinir)
            if toplam:
                gruplar.append({"tur": t, "baslik": BASLIK[t], "toplam": toplam, "sonuclar": sonuc})
        erisim_yaz(conn, k, "arama", musteri_adet)
        # en iyi eşleşmesi en yüksek grup önce (locid yazana bina, task no yazana iş)
        gruplar.sort(key=lambda g: -max(s["puan"] for s in g["sonuclar"]))
    return {"q": q, "gruplar": gruplar, "toplam": sum(g["toplam"] for g in gruplar),
            "sure_ms": round((time.perf_counter() - bas) * 1000, 1)}


@yonlendirici.get("/api/ara")
def ara_ucu(q: str = Query("", max_length=120), tur: str | None = Query(None, pattern="^(bina|is|kisi|mahalle|obek)$"),
            k: dict = Depends(izin("oturum")), conn: sqlite3.Connection = Depends(baglanti)):
    return ara(conn, k, q, tur)


__all__ = ["ROTA_IZNI", "yonlendirici", "ara", "sade", "onbellegi_bosalt"]
