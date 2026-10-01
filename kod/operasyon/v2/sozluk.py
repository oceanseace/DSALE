"""İlçe/mahalle sözlüğü: Bursa (17) + Yalova (6) ilçe, rapordan bağımsız bütün mahalleler (spec §1.6, F2).

Kaynak önceliği (INSERT OR IGNORE): resmî liste (varsa) → BursaStateList (621) → bina tablosu → öbek tanımları →
raporda görülen → elle eklenen. Yazım farkları ``mahalle_esad`` ile asıl mahalleye bağlanır ("Taşliman" → Taşlimanı).
Anahtarlar ``operasyon.is_emri.anahtar()`` / ``ilce_anahtari()``: Türkçe harf ve boşluk duyarsız.
"""
from __future__ import annotations

import difflib
import json
import os
import re
import sqlite3
import threading
from pathlib import Path

import pandas as pd

import yollar
from operasyon import is_emri as ie

from .hatalar import Catisma, Gecersiz

ILCELER: dict[str, list[str]] = {
    "Bursa": ["Büyükorhan", "Gemlik", "Gürsu", "Harmancık", "İnegöl", "İznik", "Karacabey", "Keles", "Kestel",
              "Mudanya", "Mustafakemalpaşa", "Nilüfer", "Orhaneli", "Orhangazi", "Osmangazi", "Yenişehir", "Yıldırım"],
    "Yalova": ["Altınova", "Armutlu", "Çınarcık", "Çiftlikköy", "Merkez", "Termal"],
}
BOLGE_ILLERI = tuple(ILCELER)
# Raporlarda görülen ilçe yazımları → asıl ilçe
ILCE_ESAD: list[tuple[str, str, str]] = [
    ("Bursa", "M.Kemalpaşa", "Mustafakemalpaşa"),
    ("Bursa", "MKemalpaşa", "Mustafakemalpaşa"),
    ("Bursa", "M. Kemal Paşa", "Mustafakemalpaşa"),
    ("Yalova", "Yalova Merkez", "Merkez"),
]
RESMI_LISTE = yollar.VERI / "ref" / "mahalle_resmi.json"
KAYNAK_ONCELIK = ("resmi", "liste", "bina", "obek", "rapor", "elle")


def obek_dosyasi() -> Path:
    """Öbek tanım dosyası: ``OPERASYON_OBEK`` (testler kopyayı gösterir), yoksa çalışma klasöründe ``operasyon/obekler.json``."""
    return Path(os.environ.get("OPERASYON_OBEK") or ie.OBEK_DOSYASI)


def veri_dizini() -> Path:
    return Path(os.environ.get("OPERASYON_VERI") or ie.VERI_DIZINI)


# ----------------------------------------------------------------------------- ilçe
def _ilce_merkezleri() -> dict[str, tuple[float, float]]:
    """osm_ilce.geojson ağırlık merkezleri; anahtar(ad) → (lat, lon). Dosya/shapely yoksa boş."""
    out: dict[str, tuple[float, float]] = {}
    if not ie.ILCE_SINIRLARI.exists():
        return out
    try:
        from shapely.geometry import shape
        for f in json.loads(ie.ILCE_SINIRLARI.read_text(encoding="utf-8"))["features"]:
            p = shape(f["geometry"]).centroid
            out[ie.anahtar(f["properties"]["ad"])] = (round(p.y, 6), round(p.x, 6))
    except Exception:          # noqa: BLE001 — koordinat yalnız kolaylık; yoksa NULL kalır
        return {}
    return out


def ilce_haritasi(conn: sqlite3.Connection) -> dict[tuple[str, str], tuple[str, str, str]]:
    """(il_k, yazım anahtarı) → (ilce_k, il, ilçe). Asıl ad, ilçe_anahtari biçimi ve eşadlar dahil."""
    h: dict[tuple[str, str], tuple[str, str, str]] = {}
    for r in conn.execute("SELECT il_k, ilce_k, il, ad FROM ilce"):
        deger = (r[1], r[2], r[3])
        h[(r[0], r[1])] = deger
        h[(r[0], ie.anahtar(r[3]))] = deger
    for r in conn.execute("SELECT e.il_k, e.esad_k, i.ilce_k, i.il, i.ad FROM ilce_esad e "
                          "JOIN ilce i ON i.il_k = e.il_k AND i.ilce_k = e.ilce_k"):
        h[(r[0], r[1])] = (r[2], r[3], r[4])
    return h


def ilce_coz(harita: dict, il, ilce) -> tuple[str, str, str, str] | None:
    """Raporun (il, ilçe) yazımı → (il_k, ilce_k, il, ilçe) asıl biçimde; tanınmazsa None."""
    if not il and not ilce:
        return None
    il_k = ie.anahtar(il or "")
    for anahtar in (ie.ilce_anahtari(il or "", ilce or "")[1], ie.anahtar(ilce or "")):
        d = harita.get((il_k, anahtar))
        if d:
            return il_k, d[0], d[1], d[2]
    if not il_k:                                    # il yazılmamış: ilçe adı tek ilde geçiyorsa
        adaylar = {v for (ik, k), v in harita.items() if k == ie.anahtar(ilce or "")}
        if len(adaylar) == 1:
            ck, il_ad, ilce_ad = adaylar.pop()
            return ie.anahtar(il_ad), ck, il_ad, ilce_ad
    return None


# ----------------------------------------------------------------------------- tohum
def _liste_satirlari() -> tuple[list, list]:
    """(resmî, liste) satırları: [(il, ilçe, mahalle, lat, lon)]. JSON önbelleği okunur; Excel'e dokunulmaz."""
    resmi = []
    if RESMI_LISTE.exists():
        try:
            resmi = [tuple(r) for r in json.loads(RESMI_LISTE.read_text(encoding="utf-8"))["mahalleler"]]
        except (ValueError, KeyError):
            resmi = []
    if ie.MAHALLE_ONBELLEK.exists():
        liste = [tuple(r) for r in json.loads(ie.MAHALLE_ONBELLEK.read_text(encoding="utf-8"))["mahalleler"]]
    else:
        liste = ie._mahalle_listesi(ie.MAHALLE_LISTESI)
    return resmi, liste


def _obek_refleri(yol: Path) -> list[str]:
    if not yol.exists():
        return []
    try:
        veri = json.loads(yol.read_text(encoding="utf-8"))
    except ValueError:
        return []
    return [r for t in veri.get("obekler", []) for r in t.get("mahalleler", [])]


def _mahalle_ekle(conn, harita, il, ilce, ad, lat, lon, kaynak, zaman, ekleyen_id=None, ekleyen_ad=None) -> int:
    ilc = ilce_coz(harita, il, ilce)
    if ilc is None:
        return 0
    il_k, ilce_k, il_ad, ilce_ad = ilc
    ad = ie.mahalle_eki_sil(str(ad or "")).strip()
    mk = ie.anahtar(ad)
    if not mk or ad in ("*", "Bilinmiyor"):
        return 0
    lat = None if lat is None or (isinstance(lat, float) and pd.isna(lat)) else float(lat)
    lon = None if lon is None or (isinstance(lon, float) and pd.isna(lon)) else float(lon)
    return conn.execute(
        "INSERT OR IGNORE INTO mahalle (il, ilce, ad, il_k, ilce_k, mahalle_k, lat, lon, kaynak, ekleyen_id, "
        "ekleyen_ad, eklenme) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (il_ad, ilce_ad, ad, il_k, ilce_k, mk, lat, lon, kaynak, ekleyen_id, ekleyen_ad, zaman)).rowcount


def tohumla(conn: sqlite3.Connection, zaman: str) -> dict:
    """ilçe (23) + ilçe eşadları + mahalle sözlüğü. Göç v3'ün ve taze kurulumun işlemi içinde çağrılır.

    Hiçbir dosyaya yazmaz; ``INSERT OR IGNORE`` ile iki kez koşmak zararsızdır. Dönüş yalnız sayıdır.
    """
    sayi = {"ilce": 0, "ilce_esad": 0, "resmi": 0, "liste": 0, "bina": 0, "obek": 0}
    merkez = _ilce_merkezleri()
    for il, ilceler in ILCELER.items():
        for ad in ilceler:
            il_k, ilce_k = ie.ilce_anahtari(il, ad)
            konum = merkez.get(ie.anahtar(ad)) or merkez.get(ie.anahtar(f"{il} {ad}"))
            sayi["ilce"] += conn.execute(
                "INSERT OR IGNORE INTO ilce (il_k, ilce_k, il, ad, lat, lon) VALUES (?,?,?,?,?,?)",
                (il_k, ilce_k, il, ad, *(konum or (None, None)))).rowcount
    for il, esad, asil in ILCE_ESAD:
        sayi["ilce_esad"] += conn.execute(
            "INSERT OR IGNORE INTO ilce_esad (il_k, esad_k, ilce_k) VALUES (?,?,?)",
            (ie.anahtar(il), ie.anahtar(esad), ie.ilce_anahtari(il, asil)[1])).rowcount
    harita = ilce_haritasi(conn)
    resmi, liste = _liste_satirlari()
    for il, ilce, ad, lat, lon in resmi:
        sayi["resmi"] += _mahalle_ekle(conn, harita, il, ilce, ad, lat, lon, "resmi", zaman)
    for il, ilce, ad, lat, lon in liste:
        sayi["liste"] += _mahalle_ekle(conn, harita, il, ilce, ad, lat, lon, "liste", zaman)
    for r in conn.execute(
            "SELECT il, ilce, mahalle, AVG(lat), AVG(lon) FROM bina WHERE mahalle IS NOT NULL AND TRIM(mahalle) <> '' "
            "AND mahalle <> 'Bilinmiyor' GROUP BY il, ilce, mahalle ORDER BY il, ilce, mahalle").fetchall():
        sayi["bina"] += _mahalle_ekle(conn, harita, r[0], r[1], r[2], r[3], r[4], "bina", zaman)
    for ref in _obek_refleri(obek_dosyasi()):
        p = [x.strip() for x in str(ref).split("/")]
        if len(p) == 2:
            p = ["", *p]
        if len(p) != 3 or p[2] == "*":
            continue
        sayi["obek"] += _mahalle_ekle(conn, harita, p[0], p[1], p[2], None, None, "obek", zaman)
    sayi["mahalle"] = conn.execute("SELECT COUNT(*) FROM mahalle").fetchone()[0]
    return sayi


# ----------------------------------------------------------------------------- sözlük (ie.Sozluk)
_ONBELLEK: dict = {}
_BINA_ONBELLEK: dict = {}          # bina imzası → (Sozluk tabanı, bina mahalleleri); mahalle eklemek bunu bozmaz
_ONBELLEK_KILIT = threading.Lock()


def _imza(conn: sqlite3.Connection) -> tuple:
    def tek(sql):
        try:
            return conn.execute(sql).fetchone()[0]
        except sqlite3.Error:
            return None
    yol = next((r[2] for r in conn.execute("PRAGMA database_list") if r[1] == "main"), "")
    return (yol, tek("SELECT deger FROM ayar WHERE anahtar='bina_surumu'"), tek("SELECT COUNT(*) FROM bina"),
            tek("SELECT MAX(rowid) FROM bina"), tek("SELECT COUNT(*) || ':' || IFNULL(MAX(id),0) FROM mahalle"),
            tek("SELECT COUNT(*) FROM mahalle_esad"), tek("SELECT COUNT(*) FROM ilce_esad"))


def sozluk_db(conn: sqlite3.Connection) -> ie.Sozluk:
    """Veritabanından ``ie.Sozluk``: bina (Lokasyon/BN/site aramaları) + mahalle + eşadlar + ilçe merkezleri.

    Bina ve mahalle tabloları değişmedikçe bellekten döner (imza: bina_surumu, sayılar, en büyük kimlikler).
    Aynı location_id'de pasif olmayan bina kazanır (spec §4-4: "pasif olmayan önce; tur raporuyla eklenenler dahil").
    """
    imza = _imza(conn)
    with _ONBELLEK_KILIT:
        if _ONBELLEK.get("imza") == imza and "sozluk" in _ONBELLEK:
            return _ONBELLEK["sozluk"]
        bina = _BINA_ONBELLEK.get("taban") if _BINA_ONBELLEK.get("imza") == imza[:4] else None
    if bina is None:
        # Pahalı yarı (19.706 bina ≈ 0,6 sn işlemci): yalnız bina tablosu değişince (tur raporu) yeniden kurulur.
        # Her aktarım rapordan mahalle ekleyebildiği için mahalle yarısı ayrı ve ucuzdur.
        m = pd.read_sql_query(
            "SELECT bina_serial, location_id, COALESCE(NULLIF(crm_site_adi,''), site_adi) AS site_adi_crm, "
            "blok_adi AS blok_adi_crm, ad, kapi_no, mahalle, ilce, il, lat, lon, site_grup "
            "FROM bina ORDER BY pasif DESC, bina_serial DESC", conn, dtype=str)
        bina = ie.Sozluk.bina_kur(m)
        with _ONBELLEK_KILIT:
            _BINA_ONBELLEK.clear()
            _BINA_ONBELLEK.update(imza=imza[:4], taban=bina)
    liste, ek = [], []
    for r in conn.execute("SELECT il, ilce, ad, lat, lon, kaynak FROM mahalle ORDER BY id"):
        (liste if r[5] in ("resmi", "liste") else ek).append((r[0], r[1], r[2], r[3], r[4]))
    s = bina[0].mahalleleri_kur(liste, bina[1], ek)
    # Eşadlar: yazım farkı aynı Mahalle nesnesine bağlanır (sonraki raporlarda doğru mahalleye düşer)
    for il, ilce, mk, esad_k in conn.execute(
            "SELECT m.il, m.ilce, m.mahalle_k, e.esad_k FROM mahalle_esad e JOIN mahalle m ON m.id = e.mahalle_id"):
        d = s.mah.setdefault(ie.ilce_anahtari(il, ilce), {})
        if mk in d and esad_k not in d:
            d[esad_k] = d[mk]
    for il_k, ilce_k, il, ad, lat, lon in conn.execute("SELECT il_k, ilce_k, il, ad, lat, lon FROM ilce"):
        if lat is not None:
            s.ilce_merkez[il_k + ilce_k] = (lat, lon)
            s.ilce_merkez.setdefault(ilce_k, (lat, lon))
    with _ONBELLEK_KILIT:
        _ONBELLEK.clear()
        _ONBELLEK.update(imza=imza, sozluk=s)
    return s


def onbellegi_bosalt(bina: bool = False) -> None:
    """Mahalle/eşad değişince sözlük yeniden kurulur; ``bina=True`` (testler, bina tablosu değişimi) tabanı da atar."""
    with _ONBELLEK_KILIT:
        _ONBELLEK.clear()
        if bina:
            _BINA_ONBELLEK.clear()


def isit(conn: sqlite3.Connection) -> None:
    """Sunucu açılışında (klasör izleyicisinin iş parçacığında) sözlüğü önceden kurar: ilk rapor aktarımı
    19.706 binayı işlerken aynı anda gelen istekler beklemesin."""
    try:
        sozluk_db(conn)
    except Exception:          # noqa: BLE001 — ısınma yalnız kolaylık
        pass


# ----------------------------------------------------------------------------- köy biçimleri
_KOY_BBK = re.compile(r"([^\s()]+(?:\s+[^\s()]+)?)\s+Bbk\.?\s*Mah\.?\s*\(\s*([^)]+?)\s*\)", re.I)
_KOY_PARANTEZ = re.compile(r"([^\s()]+(?:\s+[^\s()]+)?)\s*\(\s*([^)]+?)\s*\)\s*(?:Mh|Mah|Mahallesi)\b\.?", re.I)
_KOY_KOYU = re.compile(r"([^\s()./,]+(?:\s+[^\s()./,]+)?)\s+K[öo]y[üu]\b", re.I)


def koy_bicimi_ayrinti(adres: str) -> tuple[str, str | None] | None:
    """Yalova/köy adres biçimleri → (köy ya da mahalle, alt yer adı).

    "Özden Bbk.Mah.(Kadıköy) Mah." → ("Kadıköy", "Özden") · "Altı (Çavuşçiftliği) Mh." → ("Çavuşçiftliği", "Altı")
    · "Taşköprü Köyü" → ("Taşköprü", None).
    """
    s = str(adres or "")
    for desen in (_KOY_BBK, _KOY_PARANTEZ):
        m = desen.search(s)
        if m:
            y = m.group(2).strip()
            if re.search(r"\d", y) or not ie.anahtar(y):        # "(426 ADA)" gibi site/ada kodları köy değildir
                continue
            x = m.group(1).strip()
            return ie.baslik(ie.mahalle_eki_sil(y)), (ie.baslik(x) if ie.anahtar(x) != ie.anahtar(y) else None)
    m = _KOY_KOYU.search(s)
    if m and ie.anahtar(m.group(1)):
        return ie.baslik(m.group(1).strip()), None
    return None


def koy_bicimi(adres: str) -> str | None:
    a = koy_bicimi_ayrinti(adres)
    return a[0] if a else None


def mahalle_coz(szl: ie.Sozluk, adres: str, il: str, ilce: str) -> ie.MahalleSonucu:
    """v2 mahalle çözümü: bugünkü ``ie.mahalle_coz`` + köy biçimleri.

    Bugünkü ayrıştırmanın bulduğu ad sözlükte (ya da kullanıcının öbeklerinde) VARSA o kalır — kullanıcı öbeklerini
    bu adlarla kurdu ("Özden", "Devletyolu Altı"); aynı rapor bugünkü motorla aynı öbeğe düşer. Bulunan ad sözlükte
    YOKSA ve adres köy biçimindeyse ("X Bbk.Mah.(Y)", "X (Y) Mh.", "Y Köyü") köy/mahalle adı Y alınır, X nota yazılır.
    """
    eski = ie.mahalle_coz(szl, adres, il, ilce)
    a = koy_bicimi_ayrinti(adres)
    if not a:
        return eski
    d = szl.ilce_mahalleleri(il, ilce)
    if eski.ad and ie.anahtar(eski.ad) in d:
        return eski
    koy, alt = a
    notu = f"alt yer: {alt}" if alt else ""
    mh = d.get(ie.anahtar(koy))
    if mh is not None:
        return ie.MahalleSonucu(mh.ad, "koy", notu, mahalle=mh)
    return ie.MahalleSonucu(koy, "koy", notu)


# ----------------------------------------------------------------------------- benzerlik
def _lev(a: str, b: str, sinir: int = 3) -> int:
    if abs(len(a) - len(b)) >= sinir:
        return sinir
    onceki = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        simdi = [i]
        for j, cb in enumerate(b, 1):
            simdi.append(min(onceki[j] + 1, simdi[j - 1] + 1, onceki[j - 1] + (ca != cb)))
        onceki = simdi
        if min(onceki) >= sinir:
            return sinir
    return onceki[-1]


def benzer_mi(a: str, b: str) -> bool:
    """Spec §4-4: Levenshtein ≤ 2 ya da biri diğerinin öneki (kısa adlarda gürültü olmasın diye alt sınırlı)."""
    if not a or not b or a == b:
        return False
    kisa = min(len(a), len(b))
    if kisa >= 4 and (a.startswith(b) or b.startswith(a)):
        return True
    return kisa >= 5 and _lev(a, b) <= 2


def benzerler(anahtarlar, mk: str) -> list[str]:
    return [k for k in anahtarlar if benzer_mi(k, mk)]


# ----------------------------------------------------------------------------- arama / ekleme
def _obek_eslemesi(conn) -> dict[tuple[str, str, str], tuple[int, str]]:
    return {(r[0], r[1], r[2]): (r[3], r[4]) for r in conn.execute(
        "SELECT om.il_k, om.ilce_k, om.mahalle_k, o.id, o.ad FROM obek_mahalle om JOIN obek o ON o.id = om.obek_id "
        "WHERE o.aktif = 1")}


def _acik_sayilari(conn) -> dict[tuple[str, str, str], int]:
    return {(r[0], r[1], r[2]): r[3] for r in conn.execute(
        "SELECT il_k, ilce_k, mahalle_k, COUNT(*) FROM is_emri WHERE durum NOT IN ('cozuldu','kapandi') "
        "GROUP BY il_k, ilce_k, mahalle_k")}


def mahalle_kaydi(conn, r, obekler=None, acik=None) -> dict:
    obekler = obekler if obekler is not None else _obek_eslemesi(conn)
    acik = acik if acik is not None else _acik_sayilari(conn)
    anah = (r["il_k"], r["ilce_k"], r["mahalle_k"])
    o = obekler.get(anah) or obekler.get((r["il_k"], r["ilce_k"], "*"))
    return {"id": r["id"], "il": r["il"], "ilce": r["ilce"], "ad": r["ad"], "ref": f"{r['il']}/{r['ilce']}/{r['ad']}",
            "kaynak": r["kaynak"], "obek": {"id": o[0], "ad": o[1]} if o else None, "acik": int(acik.get(anah, 0))}


def ilceler(conn: sqlite3.Connection) -> list[dict]:
    obekler = _obek_eslemesi(conn)
    sayilar = {(r[0], r[1]): r[2] for r in conn.execute(
        "SELECT il_k, ilce_k, COUNT(*) FROM mahalle GROUP BY il_k, ilce_k")}
    out = []
    for il, ilce_listesi in ILCELER.items():
        for ad in ilce_listesi:
            il_k, ilce_k = ie.ilce_anahtari(il, ad)
            o = obekler.get((il_k, ilce_k, "*"))
            out.append({"il": il, "ilce": ad, "il_k": il_k, "ilce_k": ilce_k,
                        "mahalle_sayisi": int(sayilar.get((il_k, ilce_k), 0)),
                        "tum_ilce_obek": {"id": o[0], "ad": o[1]} if o else None})
    return out


def ara(conn: sqlite3.Connection, q: str | None = None, il: str | None = None, ilce: str | None = None,
        limit: int = 50) -> dict:
    """Mahalle seçici (F2): 23 ilçe + Türkçe harf duyarsız arama ("gursu", "gocmen"); her satırda öbek ve açık iş."""
    k = ie.anahtar(q or "")
    limit = max(1, min(int(limit or 50), 500))
    butun_ilceler = ilceler(conn)
    il_k = ie.anahtar(il) if il else None
    ilce_k = None
    if ilce:
        c = ilce_coz(ilce_haritasi(conn), il or "", ilce)
        ilce_k = c[1] if c else ie.anahtar(ilce)
    kosul, param = [], []
    if il_k:
        kosul.append("il_k = ?")
        param.append(il_k)
    if ilce_k:
        kosul.append("ilce_k = ?")
        param.append(ilce_k)
    eslesen_ilceler = {(i["il_k"], i["ilce_k"]) for i in butun_ilceler if k and k in ie.anahtar(i["ilce"])}
    satirlar = conn.execute("SELECT * FROM mahalle" + (" WHERE " + " AND ".join(kosul) if kosul else "")
                            + " ORDER BY il, ilce, ad", param).fetchall()
    if k:
        satirlar = [r for r in satirlar if k in r["mahalle_k"] or (r["il_k"], r["ilce_k"]) in eslesen_ilceler]
        satirlar.sort(key=lambda r: (not r["mahalle_k"].startswith(k), (r["il_k"], r["ilce_k"]) in eslesen_ilceler,
                                     r["il"], r["ilce"], r["ad"]))
    obekler, acik = _obek_eslemesi(conn), _acik_sayilari(conn)
    mahalleler = [mahalle_kaydi(conn, r, obekler, acik) for r in satirlar[:limit]]
    gorunen_ilceler = {(m["il"], m["ilce"]) for m in mahalleler}
    ilce_listesi = [i for i in butun_ilceler
                    if (not k or (i["il_k"], i["ilce_k"]) in eslesen_ilceler or (i["il"], i["ilce"]) in gorunen_ilceler)
                    and (not il_k or i["il_k"] == il_k) and (not ilce_k or i["ilce_k"] == ilce_k)]
    oneriler = []
    if k and len(k) >= 3 and not any(m for m in satirlar if m["mahalle_k"] == k):
        adaylar = conn.execute("SELECT id, ad, ilce, mahalle_k FROM mahalle" + (" WHERE " + " AND ".join(kosul) if kosul else ""),
                               param).fetchall()
        puan = sorted(((difflib.SequenceMatcher(None, k, r["mahalle_k"]).ratio(), r) for r in adaylar),
                      key=lambda x: -x[0])
        oneriler = [{"id": r["id"], "ad": r["ad"], "ilce": r["ilce"], "benzerlik": round(p, 2)}
                    for p, r in puan[:5] if p >= 0.72 and r["mahalle_k"] != k]
    return {"ilceler": ilce_listesi, "mahalleler": mahalleler, "oneriler": oneriler}


def getir(conn: sqlite3.Connection, mahalle_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM mahalle WHERE id = ?", (mahalle_id,)).fetchone()


def ekle(conn: sqlite3.Connection, il: str, ilce: str, ad: str, k: dict | None,
         benzerine_ragmen: bool = False, zaman: str | None = None) -> dict:
    """Elle mahalle ekler (kaynak 'elle'). 422 ilce_yok · 409 var · 409 benzer_var (benzerine_ragmen ile geçilir)."""
    from . import zaman as z
    ilc = ilce_coz(ilce_haritasi(conn), il, ilce)
    if ilc is None:
        raise Gecersiz("Bu ilçe Bursa ya da Yalova'da değil.", kod="ilce_yok")
    il_k, ilce_k, il_ad, ilce_ad = ilc
    ad = ie.mahalle_eki_sil(str(ad or "")).strip()
    mk = ie.anahtar(ad)
    if not mk:
        raise Gecersiz("Mahalle adını yazın.", kod="alan_eksik")
    var = conn.execute("SELECT * FROM mahalle WHERE il_k=? AND ilce_k=? AND mahalle_k=?", (il_k, ilce_k, mk)).fetchone()
    if var is None:
        e = conn.execute("SELECT m.* FROM mahalle_esad e JOIN mahalle m ON m.id = e.mahalle_id "
                         "WHERE e.il_k=? AND e.ilce_k=? AND e.esad_k=?", (il_k, ilce_k, mk)).fetchone()
        var = e
    if var is not None:
        raise Catisma(f"{var['ad']} zaten listede.", kod="var", mahalle=mahalle_kaydi(conn, var))
    if not benzerine_ragmen:
        adaylar = conn.execute("SELECT * FROM mahalle WHERE il_k=? AND ilce_k=?", (il_k, ilce_k)).fetchall()
        benzer = [r for r in adaylar if benzer_mi(r["mahalle_k"], mk)]
        if benzer:
            raise Catisma(f"Benzer bir mahalle var: {benzer[0]['ad']}. Aynı yer mi?", kod="benzer_var",
                          oneriler=[{"id": r["id"], "ad": r["ad"], "ilce": r["ilce"],
                                     "benzerlik": round(difflib.SequenceMatcher(None, mk, r["mahalle_k"]).ratio(), 2)}
                                    for r in benzer[:5]])
    konum = conn.execute("SELECT lat, lon FROM ilce WHERE il_k=? AND ilce_k=?", (il_k, ilce_k)).fetchone()
    conn.execute(
        "INSERT INTO mahalle (il, ilce, ad, il_k, ilce_k, mahalle_k, lat, lon, kaynak, ekleyen_id, ekleyen_ad, eklenme) "
        "VALUES (?,?,?,?,?,?,?,?,'elle',?,?,?)",
        (il_ad, ilce_ad, ie.baslik(ad) if ad.isupper() else ad, il_k, ilce_k, mk,
         konum[0] if konum else None, konum[1] if konum else None,
         (k or {}).get("id"), (k or {}).get("ad"), zaman or z.metin()))
    onbellegi_bosalt()
    r = conn.execute("SELECT * FROM mahalle WHERE il_k=? AND ilce_k=? AND mahalle_k=?", (il_k, ilce_k, mk)).fetchone()
    return mahalle_kaydi(conn, r)


def esad_ekle(conn: sqlite3.Connection, il: str, ilce: str, esad: str, mahalle_id: int, k: dict | None,
              zaman: str | None = None) -> dict:
    """Yazım farkı → asıl mahalle. Sonraki raporlarda o yazım doğru mahalleye düşer."""
    from . import zaman as z
    hedef = getir(conn, mahalle_id)
    if hedef is None:
        raise Gecersiz("Mahalle bulunamadı.", kod="alan_eksik")
    ilc = ilce_coz(ilce_haritasi(conn), il or hedef["il"], ilce or hedef["ilce"])
    if ilc is None:
        raise Gecersiz("Bu ilçe Bursa ya da Yalova'da değil.", kod="ilce_yok")
    il_k, ilce_k = ilc[0], ilc[1]
    ek = ie.anahtar(ie.mahalle_eki_sil(esad))
    if not ek:
        raise Gecersiz("Yazımı girin.", kod="alan_eksik")
    if ek != hedef["mahalle_k"]:
        conn.execute("INSERT OR REPLACE INTO mahalle_esad (il_k, ilce_k, esad_k, mahalle_id, ekleyen_id, eklenme) "
                     "VALUES (?,?,?,?,?,?)", (il_k, ilce_k, ek, mahalle_id, (k or {}).get("id"), zaman or z.metin()))
    onbellegi_bosalt()
    return {"il_k": il_k, "ilce_k": ilce_k, "esad_k": ek, "mahalle": mahalle_kaydi(conn, hedef)}


def asil_mahalle(conn: sqlite3.Connection, il_k: str, ilce_k: str, mk: str) -> sqlite3.Row | None:
    r = conn.execute("SELECT * FROM mahalle WHERE il_k=? AND ilce_k=? AND mahalle_k=?", (il_k, ilce_k, mk)).fetchone()
    if r is None:
        r = conn.execute("SELECT m.* FROM mahalle_esad e JOIN mahalle m ON m.id = e.mahalle_id "
                         "WHERE e.il_k=? AND e.ilce_k=? AND e.esad_k=?", (il_k, ilce_k, mk)).fetchone()
    return r


def yukle(conn: sqlite3.Connection, df: pd.DataFrame, k: dict | None, zaman: str | None = None) -> dict:
    """Resmî liste (xlsx/csv: il, ilce, mahalle[, lat, lon]) → kaynak 'resmi'. Var olanlar ezilmez."""
    from . import zaman as z
    kolon = {ie.anahtar(c): c for c in df.columns}
    gerek = [kolon.get(x) for x in ("IL", "ILCE", "MAHALLE")]
    if not all(gerek):
        raise Gecersiz("Dosyada il, ilce ve mahalle sütunları olmalı.", kod="alan_eksik")
    harita = ilce_haritasi(conn)
    eklenen = var_olan = 0
    hatali: list[int] = []
    for i, r in enumerate(df.to_dict("records"), start=2):
        il, ilce, ad = (r.get(gerek[0]), r.get(gerek[1]), r.get(gerek[2]))
        if not isinstance(ad, str) or not ad.strip() or ilce_coz(harita, il, ilce) is None:
            hatali.append(i)
            continue
        lat = pd.to_numeric(r.get(kolon.get("LAT")), errors="coerce") if kolon.get("LAT") else None
        lon = pd.to_numeric(r.get(kolon.get("LON")), errors="coerce") if kolon.get("LON") else None
        n = _mahalle_ekle(conn, harita, il, ilce, ad, lat, lon, "resmi", zaman or z.metin(),
                          (k or {}).get("id"), (k or {}).get("ad"))
        eklenen += n
        var_olan += 1 - n
    onbellegi_bosalt()
    return {"eklenen": eklenen, "var_olan": var_olan, "hatali": hatali}
