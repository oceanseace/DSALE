"""TASKS/MAP kişisel tercihleri SUNUCUDA (kişiyi bilgisayardan bilgisayara izler) + unvan başına varsayılan düzen.

Giriş: ``oku(conn, k)`` (GET /api/isler/tercih) · ``yaz(conn, k, girdi)`` (PUT /api/isler/tercih) ·
``unvan_yaz(conn, k, unvan_id, duzen)`` (PUT /api/isler/tercih/unvan, yalnız Administrator).

Kişi başına üç kayıt (``kisi_tercih``; anahtar → JSON):
  * ``etkin``    — şu an kullanılan Excel düzeni: görünen sütunlar + sıra, genişlikler, yakınlaştırma, harf satırı,
                   sıralama ve hangi adlı düzenden geldiği (``ad``).
  * ``duzenler`` — adlandırılmış düzenler ("TV ekibi", "Superbox" …): [{ad, duzen}], en çok 30.
  * ``suzgec``   — TASKS ile MAP'in ORTAK süzgeci: sütun süzgeçleri, arama, Özel filtre, Gizli/Yalnız tür, geliş tarihi.
Unvan varsayılanı (``unvan_duzen``): o unvandaki kişinin ``etkin`` kaydı yoksa başladığı düzen.
Düzenin içeriğini arayüz tanımlar (sutunDuzeni.ts); burada yalnız biçim ve boyut denetlenir. Müşteri verisi yok.
"""
from __future__ import annotations

import json
import sqlite3

from . import ek_sema, zaman
from .hatalar import AlanEksik, Gecersiz, Yasak
from .islem import islem

ANAHTARLAR = ("etkin", "duzenler", "suzgec", "ayarlar")
# Kişisel Ayarlar paneli (Kabuk ▸ Ayarlar): MAP durum çubuğu, lejant, otomatik tazeleme aralığı (sn);
# süzgeç değer listesinde diğer süzgeçlerle gizlenen değerler soluk mu gösterilsin (kapalı → listede yok).
AYAR_VARSAYILAN = {"map_durum_cubugu": True, "map_lejant": True, "map_tazeleme_sn": 15, "suzgec_soluk_goster": False}
TAZELEME_SECENEK = (0, 15, 30, 60, 120, 300)
EN_COK_DUZEN = 30
EN_COK_BAYT = 64_000
AD_EN_UZUN = 60

# Fabrika düzenleri (herkes görür, değiştirilemez). "TV ekibi": TV/FOX kurulum takip Excel'inin başlıklarından
# (ŞEF, TASK NO, MÜŞTERİ NO, ADI SOYADI, İRTİBAT NO, KURULUM, ADRES, İL, İLÇE, BÖLGE, SATIŞ TARİHİ, KAMPANYA,
# SATIŞ KANALI, TASK GELİŞ/KAPANIŞ, RANDEVU, AÇIKLAMA) BOSS'taki karşılıklarına eşlendi. Süzgeç: Task adı "TV" içerir.
FABRIKA: list[dict] = [
    {"ad": "TV ekibi", "duzen": {
        "gorunen": ["ekip", "task", "musteri_no", "ad", "tel", "tur", "adres", "ek:city", "ilce", "mahalle",
                    "ek:createDate", "ek:productInfo", "kanal", "ek:dealer", "gelis", "ek:taskEndDate", "randevu",
                    "boss", "bizim", "uyari"],
        "gen": {}, "yakinlik": 100, "harfler": True, "sira": None,
        "suzgec": {"sutunlar": {"tur": {"degerler": None, "metin": "TV"}}},
    }},
]


def _hazir(conn) -> None:
    if not (ek_sema.var_mi(conn, "kisi_tercih") and ek_sema.var_mi(conn, "unvan_duzen")):
        ek_sema.hazirla(conn)


def _json(v, ne: str) -> str:
    if v is None:
        return "null"
    if not isinstance(v, (dict, list)):
        raise AlanEksik(f"{ne} biçimi tanınmadı.")
    s = json.dumps(v, ensure_ascii=False, separators=(",", ":"))
    if len(s.encode("utf-8")) > EN_COK_BAYT:
        raise Gecersiz(f"{ne} çok büyük.", kod="cok_buyuk")
    return s


def _oku_json(s):
    try:
        return json.loads(s) if s else None
    except ValueError:
        return None


def _duzen_denetle(d, ne: str) -> dict | None:
    """Düzen: sözlük; ``gorunen`` (varsa) metin listesi, ``gen`` (varsa) sözlük. Bilinmeyen anahtarlar kalır."""
    if d is None:
        return None
    if not isinstance(d, dict):
        raise AlanEksik(f"{ne} biçimi tanınmadı.")
    if "gorunen" in d and not (isinstance(d["gorunen"], list) and all(isinstance(x, str) for x in d["gorunen"])
                               and len(d["gorunen"]) <= 400):
        raise AlanEksik(f"{ne}: sütun listesi tanınmadı.")
    if "gen" in d and not isinstance(d["gen"], dict):
        raise AlanEksik(f"{ne}: genişlikler tanınmadı.")
    _json(d, ne)
    return d


def _duzenler_denetle(liste) -> list[dict]:
    if not isinstance(liste, list):
        raise AlanEksik("Kayıtlı düzenler bir liste olmalı.")
    if len(liste) > EN_COK_DUZEN:
        raise Gecersiz(f"En çok {EN_COK_DUZEN} düzen kaydedilebilir.", kod="cok_buyuk")
    out, adlar = [], set()
    fabrika = {f["ad"].casefold() for f in FABRIKA}
    for i, x in enumerate(liste):
        if not isinstance(x, dict):
            raise AlanEksik("Düzen biçimi tanınmadı.")
        ad = str(x.get("ad") or "").strip()[:AD_EN_UZUN]
        if not ad:
            raise AlanEksik(f"{i + 1}. düzenin adı boş.")
        if ad.casefold() in adlar:
            raise Gecersiz(f"“{ad}” adı iki kez kullanılmış.", kod="ad_var")
        if ad.casefold() in fabrika:
            raise Gecersiz(f"“{ad}” hazır bir düzenin adı; başka ad verin.", kod="ad_var")
        adlar.add(ad.casefold())
        out.append({"ad": ad, "duzen": _duzen_denetle(x.get("duzen"), f"“{ad}” düzeni") or {}})
    return out


def _unvan_id(conn, k: dict | None) -> int | None:
    if not k or not k.get("id"):
        return None
    if k.get("unvan_id") is not None:
        return k.get("unvan_id")
    try:
        r = conn.execute("SELECT unvan_id FROM kullanici WHERE id=?", (k["id"],)).fetchone()
    except sqlite3.Error:
        return None
    return r[0] if r else None


def _unvanlar(conn) -> list[dict]:
    try:
        rows = conn.execute("SELECT id, ad FROM unvan WHERE aktif=1 ORDER BY sira, ad").fetchall()
    except sqlite3.Error:
        return []
    return [{"id": r[0], "ad": r[1]} for r in rows]


def _ayar_denetle(a) -> dict:
    """Yalnız bilinen ayarlar, doğru tipte (bilinmeyen anahtar atılır)."""
    if not isinstance(a, dict):
        return {}
    out: dict = {}
    for ad in ("map_durum_cubugu", "map_lejant", "suzgec_soluk_goster"):
        if isinstance(a.get(ad), bool):
            out[ad] = a[ad]
    sn = a.get("map_tazeleme_sn")
    if isinstance(sn, int) and not isinstance(sn, bool) and sn in TAZELEME_SECENEK:
        out["map_tazeleme_sn"] = sn
    return out


def oku(conn: sqlite3.Connection, k: dict | None) -> dict:
    uid = (k or {}).get("id")
    kayit: dict = {}
    if uid and ek_sema.var_mi(conn, "kisi_tercih"):
        for a, d in conn.execute("SELECT anahtar, deger FROM kisi_tercih WHERE kullanici_id=?", (uid,)):
            if a in ANAHTARLAR:
                kayit[a] = _oku_json(d)
    varsayilanlar: dict[int, dict] = {}
    if ek_sema.var_mi(conn, "unvan_duzen"):
        for uv, d in conn.execute("SELECT unvan_id, veri FROM unvan_duzen"):
            v = _oku_json(d)
            if isinstance(v, dict):
                varsayilanlar[uv] = v
    uvid = _unvan_id(conn, k)
    unvan_ad = next((u["ad"] for u in _unvanlar(conn) if u["id"] == uvid), None) if uvid else None
    out = {"etkin": kayit.get("etkin") if isinstance(kayit.get("etkin"), dict) else None,
           "duzenler": kayit.get("duzenler") if isinstance(kayit.get("duzenler"), list) else [],
           "suzgec": kayit.get("suzgec") if isinstance(kayit.get("suzgec"), dict) else None,
           "ayarlar": {**AYAR_VARSAYILAN, **_ayar_denetle(kayit.get("ayarlar"))},
           "fabrika": FABRIKA,
           "unvan": {"id": uvid, "ad": unvan_ad, "duzen": varsayilanlar.get(uvid)} if uvid else None,
           "administrator": bool((k or {}).get("administrator"))}
    if out["administrator"]:
        out["unvanlar"] = [{**u, "duzen": varsayilanlar.get(u["id"])} for u in _unvanlar(conn)]
    return out


def yaz(conn: sqlite3.Connection, k: dict | None, girdi: dict) -> dict:
    """Verilen anahtarlar yazılır (``null`` → silinir); verilmeyenler değişmez."""
    uid = (k or {}).get("id")
    if not uid:
        raise Yasak("Oturum gerekli.")
    if not isinstance(girdi, dict):
        raise AlanEksik("Tercih biçimi tanınmadı.")
    yazilacak: dict[str, str | None] = {}
    if "etkin" in girdi:
        d = _duzen_denetle(girdi["etkin"], "Düzen")
        yazilacak["etkin"] = None if d is None else _json(d, "Düzen")
    if "duzenler" in girdi:
        yazilacak["duzenler"] = None if girdi["duzenler"] is None else _json(_duzenler_denetle(girdi["duzenler"]),
                                                                             "Kayıtlı düzenler")
    if "suzgec" in girdi:
        s = girdi["suzgec"]
        if s is not None and not isinstance(s, dict):
            raise AlanEksik("Süzgeç biçimi tanınmadı.")
        yazilacak["suzgec"] = None if s is None else _json(s, "Süzgeç")
    if "ayarlar" in girdi:
        a = girdi["ayarlar"]
        if a is not None and not isinstance(a, dict):
            raise AlanEksik("Ayar biçimi tanınmadı.")
        yazilacak["ayarlar"] = None if a is None else _json(_ayar_denetle(a), "Ayarlar")
    if not yazilacak:
        return oku(conn, k)
    _hazir(conn)
    simdi = zaman.metin()
    with islem(conn):
        for a, d in yazilacak.items():
            if d is None:
                conn.execute("DELETE FROM kisi_tercih WHERE kullanici_id=? AND anahtar=?", (uid, a))
            else:
                conn.execute("INSERT INTO kisi_tercih (kullanici_id, anahtar, deger, guncelleme) VALUES (?,?,?,?) "
                             "ON CONFLICT(kullanici_id, anahtar) DO UPDATE SET deger=excluded.deger, "
                             "guncelleme=excluded.guncelleme", (uid, a, d, simdi))
    return oku(conn, k)


def unvan_yaz(conn: sqlite3.Connection, k: dict | None, unvan_id, duzen) -> dict:
    """Administrator: unvanın varsayılan düzeni (``duzen=None`` → kaldır)."""
    if not (k or {}).get("administrator"):
        raise Yasak("Unvan varsayılanını yalnız Administrator değiştirir.")
    try:
        uv = int(unvan_id)
    except (TypeError, ValueError):
        raise AlanEksik("Unvan seçin.")
    if uv not in {u["id"] for u in _unvanlar(conn)}:
        raise Gecersiz("Unvan bulunamadı.", kod="unvan_yok")
    d = _duzen_denetle(duzen, "Düzen")
    _hazir(conn)
    with islem(conn):
        if d is None:
            conn.execute("DELETE FROM unvan_duzen WHERE unvan_id=?", (uv,))
        else:
            conn.execute("INSERT INTO unvan_duzen (unvan_id, veri, guncelleme, kullanici_id) VALUES (?,?,?,?) "
                         "ON CONFLICT(unvan_id) DO UPDATE SET veri=excluded.veri, guncelleme=excluded.guncelleme, "
                         "kullanici_id=excluded.kullanici_id", (uv, _json(d, "Düzen"), zaman.metin(), k.get("id")))
    return oku(conn, k)
