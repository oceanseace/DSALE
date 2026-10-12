"""BOSS ekip GPS konumları (MAP ▸ "Ekipler" katmanı).

Kaynak: BOSS "GPS Takip / teknik" sayfasının (``/operations/gps-tracking/technical``) kullandığı uç — büyük
olasılıkla ``GET /boss-gateway-service/account-service/api/v1/user/location/TECH``. Eklenti (kanca.js) bu ucu sayfa
çağırınca yakalar (yol + başlıklar yalnız sayfanın belleğinde), sayfanın kendi yanıtını iletir ve arka.js 2 dk'da bir
aynı ucu yeniden okutur. Ham JSON ``POST /api/boss/ekip-konum`` ile buraya gelir.

Yanıtın biçimi BİLİNMİYOR (09.10): ``cozumle`` JSON'u gezer, enlem/boylam benzeri anahtarı olan her nesneyi (düz, ``data``
/``content`` altında, iç içe ``location``/``position`` nesnesinde, metin sayılar, epoch ms ya da ISO zaman) bir konum
sayar. Gerçek alan adları eklentinin ``konum_yapisi`` tanısıyla canlı akışta görünür (değersiz).

Saklama: ekip başına SON konum (bellek + ``boss_ekip_konum`` tablosu; ilk yazımda ``ek_sema.yedekli_kur`` ile yedekli
kurulur). Müşteri verisi yok; teknisyen/ekip adı ve konumu iç veridir.
Giriş: ``yaz(conn, govde)`` (uç), ``liste(conn)`` (``GET /api/isler/ekip-konumlari``).
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sqlite3
import threading
from typing import Any

from saha import ayarlar

from . import ek_sema, zaman

TABLO = "boss_ekip_konum"
SEMA = [
    f"CREATE TABLE IF NOT EXISTS {TABLO} (anahtar TEXT PRIMARY KEY, ekip_id TEXT, ad TEXT NOT NULL, lat REAL NOT NULL, "
    "lon REAL NOT NULL, zaman TEXT NOT NULL, zaman_kesin INTEGER NOT NULL DEFAULT 1, alim TEXT NOT NULL)",
]
AYAR = "boss_ekip_konum_kaynak"        # {zaman, yol, kaynak, bulunan} — son yakalama (kaynak_goruldu için)
EN_COK_KONUM = 5000
EN_COK_DUGUM = 200000
ESKI_SAAT = 72                          # bundan eski konumlar GET'te gösterilmez

_KILIT = threading.Lock()
_SON: dict[str, dict] = {}              # anahtar → {anahtar, ekip_id, ad, lat, lon, zaman, zaman_kesin, alim}
_DURUM: dict[str, Any] = {"yuklendi": False, "kaynak": None}


def sifirla() -> None:
    """Bellek önbelleği (testler ve veritabanı değişince)."""
    with _KILIT:
        _SON.clear()
        _DURUM.update(yuklendi=False, kaynak=None)


# ----------------------------------------------------------------------------- çözümleme
_LAT = re.compile(r"^(lat|latitude|enlem|y_?coord(inate)?|gps_?lat(itude)?|location_?lat(itude)?|last_?lat(itude)?)$", re.I)
_LON = re.compile(r"^(lon|lng|long|longitude|boylam|x_?coord(inate)?|gps_?(lon|lng|longitude)|location_?(lon|lng|longitude)|"
                  r"last_?(lon|lng|longitude))$", re.I)
_KONUM_ICI = re.compile(r"^(location|position|konum|coords?|coordinates?|gps|geo|point|last_?location|last_?position|"
                        r"current_?location|son_?konum|lat_?lng|geometry)$", re.I)
_EKIP_AD = ("teamName", "team_name", "teamDescription", "ekip", "ekipAdi", "ekip_adi")
_KISI_AD = ("fullName", "full_name", "userFullName", "nameSurname", "displayName", "technicianName", "name",
            "adSoyad", "ad", "userName", "username", "user_name", "description")
_EKIP_ID = ("teamId", "team_id", "ekipId", "ekip_id")
_KISI_ID = ("userId", "user_id", "userCode", "user_code", "technicianId", "employeeId", "sicil", "id", "code")
_ALT_KIMLIK = re.compile(r"^(team|ekip|user|kullanici|technician|teknisyen|employee|personel|owner)$", re.I)
_ZAMAN_ONCELIK = re.compile(r"^(location_?(date|time)|last_?location_?(date|time)|gps_?(date|time)|last_?(update|updated|seen)"
                            r"(_?(date|time|at))?|update(d)?_?(date|time|at)|signal_?(date|time)|timestamp|time_?stamp|"
                            r"report_?(date|time)|record_?(date|time)|konum_?zaman(i)?|zaman|date|time|datetime|tarih)$", re.I)
_ZAMAN_GENEL = re.compile(r"(date|time|zaman|tarih|stamp|seen|update)", re.I)


def _sayi(v) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.strip().replace(",", ".")
        if re.fullmatch(r"-?\d{1,3}(\.\d+)?", s):
            return float(s)
    return None


def _gecerli(lat: float | None, lon: float | None) -> bool:
    if lat is None or lon is None:
        return False
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return False
    return not (abs(lat) < 1e-6 and abs(lon) < 1e-6)


def _dogrudan_koord(o: dict) -> tuple[float, float] | None:
    lat = lon = None
    for k, v in o.items():
        if lat is None and _LAT.match(k):
            lat = _sayi(v)
        elif lon is None and _LON.match(k):
            lon = _sayi(v)
    if _gecerli(lat, lon):
        return lat, lon            # type: ignore[return-value]
    # GeoJSON: coordinates [lon, lat]
    c = o.get("coordinates")
    if isinstance(c, list) and len(c) == 2:
        lo, la = _sayi(c[0]), _sayi(c[1])
        if _gecerli(la, lo):
            return la, lo          # type: ignore[return-value]
    return None


def _koord(o: dict) -> tuple[tuple[float, float], dict | None, str | None] | None:
    """(enlem, boylam), koordinatın bulunduğu iç nesne (varsa) ve onun anahtarı."""
    d = _dogrudan_koord(o)
    if d:
        return d, None, None
    for k, v in o.items():
        if isinstance(v, dict) and _KONUM_ICI.match(k):
            d = _dogrudan_koord(v)
            if d:
                return d, v, k
            for k2, v2 in v.items():               # location.coordinates / position.point
                if isinstance(v2, dict) and _KONUM_ICI.match(k2):
                    d = _dogrudan_koord(v2)
                    if d:
                        return d, v, k
    return None


def _metin(v, sinir: int = 120) -> str | None:
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return str(int(v)) if float(v).is_integer() else str(v)
    if isinstance(v, str) and v.strip():
        return re.sub(r"\s+", " ", v.strip())[:sinir]
    return None


def _ilk(o: dict, adlar: tuple[str, ...]) -> str | None:
    kucuk = {k.lower(): k for k in o}
    for a in adlar:
        k = kucuk.get(a.lower())
        if k is not None and not isinstance(o[k], (dict, list)):
            m = _metin(o[k])
            if m:
                return m
    return None


def _kimlik(o: dict) -> tuple[str | None, str | None]:
    """(ekip/kişi kimliği, ad). Önce ekip alanları, sonra iç ``team``/``user`` nesnesi, sonra kişi alanları."""
    ad = _ilk(o, _EKIP_AD)
    kid = _ilk(o, _EKIP_ID)
    alt = [(k, v) for k, v in o.items() if isinstance(v, dict) and _ALT_KIMLIK.match(k)]
    alt.sort(key=lambda kv: 0 if re.match(r"^(team|ekip)$", kv[0], re.I) else 1)
    for _k, v in alt:
        if not ad:
            ad = _ilk(v, _EKIP_AD + _KISI_AD)
        if not kid:
            kid = _ilk(v, _EKIP_ID + _KISI_ID)
    if not ad:
        ad = _ilk(o, _KISI_AD)
    if not kid:
        kid = _ilk(o, _KISI_ID)
    return kid, ad


def zaman_coz(v) -> dt.datetime | None:
    """Epoch (ms ya da sn; sayı ya da metin), ISO (Z/+03:00 → Türkiye saati) ya da yerel metin → saf datetime (TR)."""
    if isinstance(v, bool) or v is None:
        return None
    n = None
    if isinstance(v, (int, float)):
        n = float(v)
    elif isinstance(v, str) and re.fullmatch(r"\s*\d{10,13}(\.\d+)?\s*", v):
        n = float(v)
    if n is not None:
        if n > 1e12:
            n /= 1000.0
        if not (1e9 <= n <= 4e9):
            return None
        return dt.datetime.fromtimestamp(n, ayarlar.TR).replace(tzinfo=None, microsecond=0)
    if not isinstance(v, str) or not v.strip():
        return None
    s = v.strip()
    try:
        an = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        if an.tzinfo is not None:
            an = an.astimezone(ayarlar.TR).replace(tzinfo=None)
        return an.replace(microsecond=0)
    except ValueError:
        pass
    an = zaman.oku(s)
    return an if an and an.year >= 2000 else None


def _zaman(o: dict, ic: dict | None) -> dt.datetime | None:
    """Önce bilinen adlar (locationDate, lastUpdate, timestamp …), sonra adında tarih/zaman geçen alan; önce konumun
    iç nesnesi, sonra kaydın kendisi. Oluşturma/doğum/başlangıç tarihleri sayılmaz."""
    kaynaklar = ([ic] if ic else []) + [o]
    for kaynak in kaynaklar:
        for k, v in kaynak.items():
            if _ZAMAN_ONCELIK.match(k):
                an = zaman_coz(v)
                if an:
                    return an
    for kaynak in kaynaklar:
        for k, v in kaynak.items():
            if _ZAMAN_GENEL.search(k) and not re.search(r"(create|birth|dogum|start|end|bas|bit)", k, re.I):
                an = zaman_coz(v)
                if an:
                    return an
    return None


def cozumle(veri) -> list[dict]:
    """Ham BOSS yanıtındaki konumlar: [{ekip_id, ad, lat, lon, zaman (datetime|None)}]. Biçim bilinmediği için hoşgörülü."""
    out: list[dict] = []
    sayac = [0]

    def gez(o, d: int, ust: dict | None) -> None:
        sayac[0] += 1
        if d > 8 or sayac[0] > EN_COK_DUGUM or len(out) >= EN_COK_KONUM:
            return
        if isinstance(o, list):
            for x in o:
                gez(x, d + 1, ust)
            return
        if not isinstance(o, dict):
            return
        k = _koord(o)
        if k:
            (lat, lon), ic, ic_ad = k
            kid, ad = _kimlik(o)
            if not (kid or ad) and ust is not None:       # {team:{..}, location:{lat,lon}} gibi: üst nesnenin kimliği
                kid, ad = _kimlik(ust)
            out.append({"ekip_id": kid, "ad": ad or (f"#{kid}" if kid else None), "lat": round(lat, 6),
                        "lon": round(lon, 6), "zaman": _zaman(o, ic)})
            # aynı nesnenin başka (konum dışı) iç dizileri de gezilir (ör. ekip → üyeler)
            for kk, v in o.items():
                if kk != ic_ad and isinstance(v, (list, dict)) and not _KONUM_ICI.match(kk):
                    gez(v, d + 1, o)
            return
        for v in o.values():
            if isinstance(v, (list, dict)):
                gez(v, d + 1, o)

    gez(veri, 0, None)
    return out


def _anahtar(k: dict) -> str | None:
    if k.get("ekip_id"):
        return f"id:{k['ekip_id']}"
    if k.get("ad"):
        return "ad:" + re.sub(r"\s+", " ", str(k["ad"])).strip().upper()
    return None


# ----------------------------------------------------------------------------- saklama
def _yukle(conn: sqlite3.Connection) -> None:
    if _DURUM["yuklendi"]:
        return
    try:
        if ek_sema.var_mi(conn, TABLO):
            for r in conn.execute(f"SELECT anahtar, ekip_id, ad, lat, lon, zaman, zaman_kesin, alim FROM {TABLO}"):
                _SON[r[0]] = {"anahtar": r[0], "ekip_id": r[1], "ad": r[2], "lat": r[3], "lon": r[4], "zaman": r[5],
                              "zaman_kesin": bool(r[6]), "alim": r[7]}
        r = conn.execute("SELECT deger FROM ayar WHERE anahtar=?", (AYAR,)).fetchone()
        if r and r[0]:
            _DURUM["kaynak"] = json.loads(r[0])
    except (sqlite3.Error, ValueError):
        pass
    _DURUM["yuklendi"] = True


def yaz(conn: sqlite3.Connection, govde: dict) -> dict:
    """Eklentinin gönderdiği ham yanıt → ekip başına son konum. Dönüş yalnız sayılar."""
    govde = govde if isinstance(govde, dict) else {}
    kaynak = str(govde.get("kaynak") or "")[:20] or None
    yol = str(govde.get("yol") or "")[:300] or None
    if "veri" not in govde:
        if govde.get("hata"):
            return {"bulunan": 0, "guncellenen": 0, "toplam": None, "hata": str(govde.get("hata"))[:60]}
        veri = {k: v for k, v in govde.items() if k not in ("kaynak", "yol", "surum")}
    else:
        veri = govde.get("veri")
    konumlar = cozumle(veri)
    simdi = zaman.metin()
    guncellenen = []
    with _KILIT:
        _yukle(conn)
        for k in konumlar:
            a = _anahtar(k)
            if not a:
                continue
            z = zaman.metin(k["zaman"]) if k["zaman"] else simdi
            eski = _SON.get(a)
            if eski and eski.get("zaman_kesin") and k["zaman"] and str(eski["zaman"]) > z:
                continue                                   # sayfanın eski yanıtı yeniyi ezmez
            yeni = {"anahtar": a, "ekip_id": k["ekip_id"], "ad": str(k["ad"] or a)[:120], "lat": k["lat"],
                    "lon": k["lon"], "zaman": z, "zaman_kesin": bool(k["zaman"]), "alim": simdi}
            _SON[a] = yeni
            guncellenen.append(yeni)
        _DURUM["kaynak"] = {"zaman": simdi, "yol": yol, "kaynak": kaynak, "bulunan": len(konumlar)}
        toplam = len(_SON)
    _kalici_yaz(conn, guncellenen)
    return {"bulunan": len(konumlar), "guncellenen": len(guncellenen), "toplam": toplam}


def _kalici_yaz(conn: sqlite3.Connection, satirlar: list[dict]) -> None:
    try:
        ek_sema.yedekli_kur(conn, "ekip_konum", SEMA, (TABLO,))
        conn.executemany(
            f"INSERT INTO {TABLO}(anahtar, ekip_id, ad, lat, lon, zaman, zaman_kesin, alim) VALUES(?,?,?,?,?,?,?,?) "
            "ON CONFLICT(anahtar) DO UPDATE SET ekip_id=excluded.ekip_id, ad=excluded.ad, lat=excluded.lat, "
            "lon=excluded.lon, zaman=excluded.zaman, zaman_kesin=excluded.zaman_kesin, alim=excluded.alim",
            [(s["anahtar"], s["ekip_id"], s["ad"], s["lat"], s["lon"], s["zaman"], int(s["zaman_kesin"]), s["alim"])
             for s in satirlar])
        conn.execute("INSERT INTO ayar(anahtar, deger) VALUES(?,?) ON CONFLICT(anahtar) DO UPDATE SET deger=excluded.deger",
                     (AYAR, json.dumps(_DURUM["kaynak"], ensure_ascii=False)))
        conn.commit()
    except Exception:          # noqa: BLE001 — kalıcı yazılamasa da bellekteki konum geçerli
        import logging
        logging.getLogger("operasyon.ekip_konum").exception("Ekip konumu kalıcı yazılamadı")


def _eslesme(conn: sqlite3.Connection) -> dict[str, tuple[int, str]]:
    """BOSS ekip adı anahtarı → (teknisyen kimliği, ad). Ucuz; olmazsa boş."""
    try:
        from . import kisi
        tek = kisi.teknikler(conn)
        return {a: (kid, tek[kid]["ad"]) for a, kid in kisi.boss_ekip_haritasi(conn).items() if kid in tek}
    except Exception:          # noqa: BLE001
        return {}


def liste(conn: sqlite3.Connection) -> dict:
    with _KILIT:
        _yukle(conn)
        satirlar = [dict(s) for s in _SON.values()]
        kaynak = dict(_DURUM["kaynak"]) if _DURUM["kaynak"] else None
    simdi = zaman.simdi()
    harita = _eslesme(conn) if satirlar else {}
    try:
        from operasyon import is_emri as ie
        anahtar_f = ie.anahtar
    except Exception:          # noqa: BLE001
        anahtar_f = lambda s: str(s or "").upper().replace(" ", "")   # noqa: E731
    out = []
    for s in satirlar:
        yas = zaman.dakika(s["zaman"], simdi)
        if yas is not None and yas > ESKI_SAAT * 60:
            continue
        es = harita.get(anahtar_f(s["ad"])) if s.get("ad") else None
        out.append({"ekip": s["ekip_id"] or s["anahtar"], "ad": s["ad"], "lat": s["lat"], "lon": s["lon"],
                    "zaman": s["zaman"], "zaman_kesin": bool(s.get("zaman_kesin")),
                    "yas_dk": None if yas is None else max(0, round(yas)),
                    "teknik_id": es[0] if es else None, "teknik_ad": es[1] if es else None})
    out.sort(key=lambda x: (x["ad"] or "").upper())
    return {"ekipler": out, "kaynak_goruldu": kaynak is not None, "son_alim": kaynak["zaman"] if kaynak else None,
            "son_bulunan": kaynak.get("bulunan") if kaynak else None}
