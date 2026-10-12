"""RUT: kurulum ekiplerinin GÜNLÜK rotası (Excel'deki "rut" dosyasının yerine) — ekip başına bir sayfa + Özet.

Giriş: ``gun(conn, k, tarih)`` (GET /api/rut) · ``hucre_yaz`` (PUT /api/rut/hucre) · ``mesai_yaz`` (PUT /api/rut/ayar).
Uçlar: ``rut_api.py``. Arayüz: ``kod/arayuz/src/birimler/operasyon/rut/``.

- VERİ KAYNAĞI YALNIZ uygulama + BOSS: ``is_emri`` (BOSS eşitlemesi), ``boss_ham`` (BOSS liste alanları) ve elle
  yazılan ``rut_satir``. Kullanıcının Excel dosyalarından hiçbir veri okunmaz/gömülmez; Excel'den alınan yalnız
  sütun BAŞLIKLARI ve sırasıdır (``SUTUNLAR``).
- Rota KENDİLİĞİNDEN kurulur: o gün randevusu olan işler (``is_emri``: uygulama randevusu ``randevu_bas``, yoksa
  BOSS randevusu ``boss_randevu_bas``). Ekip (``_ekip``): iş BOSS'ta bir ekibe atanmışsa (``boss_ekip``; BOSS'taki
  atama/randevu = appointment) O EKİP; değilse uygulamada atanan kişi; o da yoksa elle kaydedilen ekip.
  Satırlar randevu saatine göre sıralanır.
- Sütunlar Excel'deki sırayla (``SUTUNLAR``); ``is_emri`` ve BOSS ham alanlarından (``boss_ham``) doldurulur,
  bulunamayan boş kalır. Ham alan adları ``HAM_ADAYLARI``'ndaki düzenli ifadelerle aranır (ilk eşleşen).
- Elle doldurulanlar (GİRİŞ, ÇIKIŞ, YARDIMCI, CİHAZ, SWITCH ID, DURUM) ``rut_satir`` tablosunda (tarih, task no)
  başına saklanır; tablo ilk yazışta ``ek_sema.yedekli_kur`` ile (doğrulanmış yedekten SONRA) kurulur.
  Elle değer yoksa GİRİŞ/ÇIKIŞ teknisyenin uygulamadaki saatlerinden (sahada/çözüm), DURUM iş durumundan önerilir.
- Özet: ilk giriş, son çıkış, mesai dk, mesai içi/dışı kurulan kurulum, iptal-erteleme, yan iş (TV-donanım-arıza).
  Mesai saatleri ``ayar.rut_mesai`` (varsayılan 08:00–18:00).
- Müşteri alanları (no, ad, irtibat, adres) yalnız ``is.musteri`` izni olan ofis görevlerine çıkar.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sqlite3
from collections import Counter

from operasyon import is_emri as ie

from . import boss_ham, ek_sema, kisi, zaman
from .hatalar import V2Hata
from .islem import islem

TABLO = "rut_satir"
SEMA = [
    "CREATE TABLE IF NOT EXISTS rut_satir (tarih TEXT NOT NULL, task_no TEXT NOT NULL, ekip TEXT, giris TEXT, "
    "cikis TEXT, yardimci TEXT, cihaz TEXT, switch_id TEXT, durum TEXT, guncelleme TEXT NOT NULL, "
    "kullanici_id INTEGER, kullanici_ad TEXT, PRIMARY KEY (tarih, task_no))",
]

# (anahtar, Excel başlığı, elle düzenlenir mi) — Excel'deki sütun sırası
SUTUNLAR: list[tuple[str, str, bool]] = [
    ("randevu", "RANDEVU", False), ("giris", "GİRİŞ", True), ("cikis", "ÇIKIŞ", True), ("sef", "ŞEF", False),
    ("yardimci", "YARDIMCI", True), ("task_no", "TASK NO", False), ("musteri_no", "MÜŞTERİ NO", False),
    ("adi_soyadi", "ADI SOYADI", False), ("irtibat", "İRTİBAT NO", False), ("urun", "ÜRÜN", False),
    ("adres", "ADRES", False), ("il", "İL", False), ("ilce", "İLÇE", False), ("bolge", "BÖLGE", False),
    ("satis_tarihi", "SATIŞ TARİHİ", False), ("kampanya", "KAMPANYA BİLGİLERİ", False), ("hiz", "HIZ", False),
    ("kampanya_statu", "KAMPANYA STATÜ", False), ("paket", "PAKET", False), ("altyapi", "ALT YAPI TİPİ", False),
    ("satis_kanali", "SATIŞ KANALI", False), ("temsilci", "SATIŞ TEMSİLCİSİ", False), ("kisa_kod", "KISA KOD", False),
    ("task_gelis", "TASK GELİŞ", False), ("task_kapanis", "TASK KAPANIŞ", False), ("cihaz", "CİHAZ", True),
    ("switch_id", "SWITCH ID", True), ("durum", "DURUM", True),
]
DUZENLENIR = tuple(a for a, _, d in SUTUNLAR if d)
MUSTERI_ALANLARI = ("musteri_no", "adi_soyadi", "irtibat", "adres")
OZET_SUTUNLARI: list[tuple[str, str]] = [
    ("n", "N"), ("sef", "EKİP ŞEFİ"), ("yardimci", "YARDIMCI"), ("ilk_giris", "İLK İŞE GİRİŞ"),
    ("son_cikis", "SON İŞTEN ÇIKIŞ"), ("mesai_dk", "MESAİ DK"), ("mesai_ici", "MESAİ İÇİ ADET (FİBER K)"),
    ("iptal_erteleme", "İPTAL - ERTELEME"), ("mesai_disi", "MESAİ DIŞI ADET FİBER K"),
    ("yan_is", "YAN İŞ (TV-DONANIM-ARIZA)"),
]
# DURUM hücresinin seçenekleri (iş akışı sözlüğü; Excel'den veri değil) ve mesai (ayarla değişir: PUT /api/rut/ayar)
DURUM_SECENEKLERI = ["KURULDU", "İPTAL", "ERTELEME", "MÜŞTERİ EVDE YOK", "ALTYAPI YOK", "TAMAMLANDI"]
VARSAYILAN_MESAI = {"bas": "08:00", "bit": "18:00"}
EKIPSIZ = "Ekipsiz"
EN_UZUN = 200

# BOSS ham alanı adayları (alan ADINA bakar; ilk eşleşen, değeri dolu olan). Gerçek adlar canlı akışla netleşince
# en başa eklenir; bulunamayan sütun boş kalır.
HAM_ADAYLARI: dict[str, list[str]] = {
    "urun": [r"^product.?info$", r"^product(.?name)?$", r"^offer.?name$"],
    "satis_tarihi": [r"^(sale|sales|order|contract|subscription).?(date|time)$", r"^satis.?tarih"],
    "kampanya_statu": [r"^campaign.?(status|state)", r"^kampanya.?stat"],
    "kampanya": [r"^campaign(?!.*(status|state|id$))", r"^kampanya(?!.*stat)", r"\.campaign(.?name)?$"],
    "hiz": [r"speed", r"bandwidth", r"^hiz$", r"^(download|dl).?rate"],
    "paket": [r"^(package|tariff|offer|bundle)(.?name)?$", r"^paket"],
    "altyapi": [r"infra", r"^alt.?yapi", r"^(access|connection).?(type|technology)$", r"^technology$"],
    "temsilci": [r"sales?.?(rep|representative|person|user|agent|owner)", r"temsilci", r"^dealer.?(user|person)"],
    "kisa_kod": [r"short.?code", r"^kisa.?kod"],
    "cihaz": [r"^(device|modem|cpe|ont)(.?(name|type|model|info))?$"],
    "switch_id": [r"switch"],
    "irtibat": [r"^(contact|customer|gsm|mobile)?.?phone(.?number)?$", r"^gsm(.?no)?$", r"^msisdn$",
                r"^contact.?(no|number|gsm)$"],
}
_HAM_RE = {k: [re.compile(p, re.I) for p in v] for k, v in HAM_ADAYLARI.items()}

# Yan iş: TV, donanım (modem/cihaz değişikliği), arıza. Geri kalanı kurulum (fiber K) sayılır.
_YAN_IS = ("TV", "DONANIM", "MODEM", "CIHAZ", "ARIZA", "DEGISIKLIK", "DEGISIM", "BAGLANTI PROBLEMI")
_SAAT = re.compile(r"^\s*(\d{1,2})\s*[:.,]?\s*(\d{2})\s*$")


# ============================================================================= yardımcılar
def _tarih(tarih: str | None) -> str:
    t = (tarih or "").strip() or zaman.simdi().strftime("%Y-%m-%d")
    try:
        return dt.date.fromisoformat(t).isoformat()
    except ValueError:
        raise V2Hata("Tarih AAAA-AA-GG olmalı.", kod="alan_eksik", durum=422)


def saat_duzelt(deger) -> str | None:
    """'9.30' · '0930' · '9:30' → '09:30'. Boş → None. Geçersiz → V2Hata."""
    s = str(deger or "").strip()
    if not s:
        return None
    m = _SAAT.match(s)
    if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
        raise V2Hata("Saati SS:DD biçiminde yazın (ör. 09:30).", kod="alan_gecersiz", durum=422)
    return f"{int(m.group(1)):02d}:{m.group(2)}"


def _dk(saat: str | None) -> int | None:
    if not saat:
        return None
    m = _SAAT.match(str(saat))
    return int(m.group(1)) * 60 + int(m.group(2)) if m else None


def _hhmm(zaman_metni, gun: str | None = None) -> str | None:
    """'2026-10-07 09:15:00' → '09:15' (``gun`` verilirse yalnız o günse)."""
    z = zaman.oku(zaman_metni)
    if z is None or (gun and z.date().isoformat() != gun):
        return None
    return z.strftime("%H:%M")


def _gun_saat(zaman_metni) -> str | None:
    z = zaman.oku(zaman_metni)
    return z.strftime("%d.%m.%Y %H:%M") if z else None


def _ham_bul(ham: dict, alan: str, musteri: bool):
    for kalip in _HAM_RE.get(alan, ()):
        for k, v in ham.items():
            if v in (None, "") or (not musteri and boss_ham.kisisel_mi(k)):
                continue
            if kalip.search(k) or ("." in k and kalip.search(k.rsplit(".", 1)[1])):
                return v if isinstance(v, (int, float)) and not isinstance(v, bool) else str(v)
    return None


def is_turu(*metinler) -> str:
    """'yan' (TV · donanım · arıza) ya da 'kurulum' (fiber K)."""
    s = " " + " ".join(ie.sade(m) for m in metinler if m) + " "
    return "yan" if any(f" {y}" in s for y in _YAN_IS) else "kurulum"


def durum_sinifi(durum: str | None) -> str | None:
    s = ie.sade(durum)
    if not s:
        return None
    if s.startswith(("KURUL", "TAMAM", "BITTI")):
        return "tamam"
    if "IPTAL" in s:
        return "iptal"
    if "ERTELE" in s:
        return "erteleme"
    return "diger"


def _durum_onerisi(r: sqlite3.Row, tur: str) -> str | None:
    bd = ie.sade(r["boss_durum"])
    if "IPTAL" in bd or r["kapanis_nedeni"] in ("iptal", "musteri_vazgecti"):
        return "İPTAL"
    if r["durum"] in ("cozuldu", "kapandi"):
        return "KURULDU" if tur == "kurulum" else "TAMAMLANDI"
    if r["durum"] == "askida":
        return "ERTELEME"
    return None


def mesai(conn: sqlite3.Connection) -> dict:
    r = conn.execute("SELECT deger FROM ayar WHERE anahtar='rut_mesai'").fetchone()
    try:
        m = json.loads(r[0]) if r and r[0] else {}
        bas, bit = saat_duzelt(m.get("bas")), saat_duzelt(m.get("bit"))
        if bas and bit and _dk(bas) < _dk(bit):
            return {"bas": bas, "bit": bit}
    except (ValueError, TypeError, AttributeError, V2Hata):
        pass
    return dict(VARSAYILAN_MESAI)


def mesai_yaz(conn: sqlite3.Connection, bas, bit) -> dict:
    b, s = saat_duzelt(bas), saat_duzelt(bit)
    if not b or not s or _dk(b) >= _dk(s):
        raise V2Hata("Mesai başlangıcı bitişten önce olmalı.", kod="alan_gecersiz", durum=422)
    with islem(conn):
        conn.execute("INSERT INTO ayar(anahtar, deger) VALUES('rut_mesai', ?) ON CONFLICT(anahtar) DO UPDATE SET "
                     "deger=excluded.deger", (json.dumps({"bas": b, "bit": s}),))
    return {"bas": b, "bit": s}


def _ekip(r: sqlite3.Row, atanan: dict | None, kayit: dict | None, boss_kisi: dict[str, int]) -> tuple[str, int | None]:
    """(ekip adı, kişi id). BOSS'ta atanmış iş → BOSS ekibi (``boss_ekip``; BOSS ekip kişisi varsa onun id'si);
    değilse uygulamada atanan kişi; o da yoksa elle kaydedilen ekip ya da "Ekipsiz"."""
    be = str(r["boss_ekip"] or "").strip()
    if be:
        kid = boss_kisi.get(ie.anahtar(be))
        if kid is None and atanan and ie.anahtar(atanan.get("ad")) == ie.anahtar(be):
            kid = atanan.get("id")
        return be, kid
    if atanan and atanan.get("ad"):
        return atanan["ad"], atanan.get("id")
    return (kayit or {}).get("ekip") or EKIPSIZ, None


def musteri_izni(conn: sqlite3.Connection, k: dict | None) -> bool:
    return kisi.izinli(conn, k, "is.musteri") and kisi.ofis_mu(conn, k)


def _kayitlar(conn: sqlite3.Connection, tarih: str) -> dict[str, dict]:
    if not ek_sema.var_mi(conn, TABLO):
        return {}
    conn.row_factory = sqlite3.Row
    return {r["task_no"]: dict(r) for r in conn.execute("SELECT * FROM rut_satir WHERE tarih=?", (tarih,))}


# ============================================================================= gün
def _satir(r: sqlite3.Row, tarih: str, ekip: str, ham: dict, kayit: dict | None, musteri: bool, tel: bool,
           obekler: dict[int, str]) -> dict:
    randevu_bas = r["randevu_bas"] or r["boss_randevu_bas"]
    randevu_bit = r["randevu_bit"] if r["randevu_bas"] else r["boss_randevu_bit"]
    rb, rs = _hhmm(randevu_bas), _hhmm(randevu_bit)
    urun = _ham_bul(ham, "urun", musteri) or r["task_adi"]
    tur = is_turu(r["task_adi"] or urun)
    oneri = {"giris": _hhmm(r["sahada_zamani"], tarih), "cikis": _hhmm(r["cozum_zamani"], tarih),
             "durum": _durum_onerisi(r, tur), "cihaz": _ham_bul(ham, "cihaz", musteri),
             "switch_id": _ham_bul(ham, "switch_id", musteri)}
    obek_id = r["obek_elle_id"] or r["obek_id"]
    s = {
        "is_no": r["is_no"], "task_no": r["boss_task_no"] or r["is_no"], "tur": tur,
        "randevu": f"{rb}–{rs}" if rb and rs and rs != rb else rb,
        "randevu_tarih": str(randevu_bas or "")[:10] or None,
        "sef": ekip, "urun": urun, "il": r["il"], "ilce": r["ilce"],
        "bolge": obekler.get(obek_id) if obek_id else None,
        "satis_tarihi": _ham_bul(ham, "satis_tarihi", musteri), "kampanya": _ham_bul(ham, "kampanya", musteri),
        "hiz": _ham_bul(ham, "hiz", musteri), "kampanya_statu": _ham_bul(ham, "kampanya_statu", musteri),
        "paket": _ham_bul(ham, "paket", musteri), "altyapi": _ham_bul(ham, "altyapi", musteri),
        "satis_kanali": r["satis_kanali"], "temsilci": _ham_bul(ham, "temsilci", musteri),
        "kisa_kod": _ham_bul(ham, "kisa_kod", musteri), "task_gelis": _gun_saat(r["acilis"]),
        "task_kapanis": _gun_saat(r["kapanis"] or r["cozum_zamani"]),
        "is_durumu": r["durum"],
    }
    if not s["bolge"]:
        s["bolge"] = r["mahalle"]
    if musteri:
        s.update(musteri_no=r["musteri_no"], adi_soyadi=r["musteri_adi"], adres=r["adres"],
                 irtibat=(r["musteri_tel"] if tel else None) or _ham_bul(ham, "irtibat", True))
    _uygula(s, kayit, oneri)
    return s


def _uygula(s: dict, kayit: dict | None, oneri: dict) -> None:
    """Elle değer varsa o, yoksa öneri. ``elle``: elle yazılan alanlar; ``oneri``: önerilen değerler."""
    s["elle"] = []
    s["oneri"] = {k: v for k, v in oneri.items() if v not in (None, "")}
    for a in DUZENLENIR:
        v = (kayit or {}).get(a)
        if v not in (None, ""):
            s[a] = v
            s["elle"].append(a)
        else:
            s[a] = oneri.get(a)


def _ozet(ekipler: list[dict], m: dict) -> list[dict]:
    bas, bit = _dk(m["bas"]), _dk(m["bit"])
    out = []
    for n, e in enumerate(ekipler, start=1):
        satirlar = e["satirlar"]
        girisler = [g for g in (_dk(x.get("giris")) for x in satirlar) if g is not None]
        cikislar = [c for c in (_dk(x.get("cikis")) for x in satirlar) if c is not None]
        ilk = min(girisler) if girisler else None
        son = max(cikislar) if cikislar else None
        ici = disi = iptal = yan = 0
        for x in satirlar:
            sinif = durum_sinifi(x.get("durum"))
            if sinif in ("iptal", "erteleme"):
                iptal += 1
            if sinif != "tamam":
                continue
            if x["tur"] == "yan":
                yan += 1
                continue
            an = _dk(x.get("cikis")) or _dk(x.get("giris")) or _dk((x.get("randevu") or "")[:5])
            if an is not None and not (bas <= an <= bit):
                disi += 1
            else:
                ici += 1
        yardimci = Counter(str(x["yardimci"]).strip() for x in satirlar if str(x.get("yardimci") or "").strip())
        out.append({"n": n, "sef": e["ad"], "yardimci": ", ".join(a for a, _ in yardimci.most_common(2)) or None,
                    "ilk_giris": f"{ilk // 60:02d}:{ilk % 60:02d}" if ilk is not None else None,
                    "son_cikis": f"{son // 60:02d}:{son % 60:02d}" if son is not None else None,
                    "mesai_dk": (son - ilk) if ilk is not None and son is not None and son >= ilk else None,
                    "mesai_ici": ici, "iptal_erteleme": iptal, "mesai_disi": disi, "yan_is": yan,
                    "adet": len(satirlar)})
    return out


def gun(conn: sqlite3.Connection, k: dict | None, tarih: str | None = None) -> dict:
    """Bir günün rotası: {tarih, mesai, sutunlar, ozet_sutunlari, durumlar, musteri, ekipler[], ozet[], adet}."""
    tarih = _tarih(tarih)
    conn.row_factory = sqlite3.Row
    musteri = musteri_izni(conn, k)
    tel = musteri and (conn.execute("SELECT deger FROM ayar WHERE anahtar='musteri_tel'").fetchone() or [None])[0] \
        == "acik"
    kayitlar = _kayitlar(conn, tarih)
    satirlar = conn.execute(
        "SELECT * FROM is_emri WHERE substr(COALESCE(randevu_bas, boss_randevu_bas), 1, 10) = ?", (tarih,)).fetchall()
    gorulen = {r["boss_task_no"] or r["is_no"] for r in satirlar}
    eksik = [no for no in kayitlar if no not in gorulen]
    if eksik:   # elle kaydı olan ama randevusu başka güne kaymış işler: o günün rotasında kalır (erteleme izi)
        for i in range(0, len(eksik), 900):
            parca = eksik[i:i + 900]
            soru = ",".join("?" * len(parca))
            satirlar += conn.execute(f"SELECT * FROM is_emri WHERE boss_task_no IN ({soru}) OR "
                                     f"(boss_task_no IS NULL AND is_no IN ({soru}))", parca + parca).fetchall()
    ham = boss_ham.oku(conn, [r["boss_task_no"] for r in satirlar if r["boss_task_no"]])
    kisiler = kisi.kisiler(conn, [r["atanan_id"] for r in satirlar if r["atanan_id"]])
    boss_kisi = kisi.boss_ekip_haritasi(conn) if any(r["boss_ekip"] for r in satirlar) else {}
    obekler = {i: a for i, a in conn.execute("SELECT id, ad FROM obek")}

    gruplar: dict[str, dict] = {}
    bulunan = set()
    for r in satirlar:
        no = r["boss_task_no"] or r["is_no"]
        if no in bulunan:
            continue
        bulunan.add(no)
        kayit = kayitlar.get(no)
        atanan = kisiler.get(r["atanan_id"]) if r["atanan_id"] else None
        ekip, kisi_id = _ekip(r, atanan, kayit, boss_kisi)
        g = gruplar.setdefault(ie.anahtar(ekip) or EKIPSIZ, {"ad": ekip, "kisi_id": kisi_id, "satirlar": []})
        g["satirlar"].append(_satir(r, tarih, g["ad"], ham.get(r["boss_task_no"] or "") or {}, kayit, musteri, tel,
                                    obekler))
    for no, kayit in kayitlar.items():          # iş tablodan tamamen düşmüş (saklama): yalnız elle yazılanlar
        if no in bulunan:
            continue
        ekip = kayit.get("ekip") or EKIPSIZ
        g = gruplar.setdefault(ie.anahtar(ekip) or EKIPSIZ, {"ad": ekip, "kisi_id": None, "satirlar": []})
        s = {"is_no": None, "task_no": no, "tur": "kurulum", "sef": g["ad"], "randevu": None, "is_durumu": None}
        _uygula(s, kayit, {})
        g["satirlar"].append(s)

    for g in gruplar.values():
        g["satirlar"].sort(key=lambda x: ((x.get("randevu") or "99:99")[:5], str(x["task_no"])))
    ekipler = sorted(gruplar.values(), key=lambda g: (g["ad"] == EKIPSIZ, ie.sade(g["ad"])))
    m = mesai(conn)
    return {"tarih": tarih, "mesai": m, "musteri": musteri, "durumlar": DURUM_SECENEKLERI,
            "sutunlar": [{"id": a, "baslik": b, "duzenlenir": d} for a, b, d in SUTUNLAR
                         if musteri or a not in MUSTERI_ALANLARI],
            "ozet_sutunlari": [{"id": a, "baslik": b} for a, b in OZET_SUTUNLARI],
            "ekipler": ekipler, "ozet": _ozet(ekipler, m), "adet": sum(len(g["satirlar"]) for g in ekipler)}


def hucre_yaz(conn: sqlite3.Connection, k: dict | None, tarih: str | None, task_no: str, alan: str, deger) -> dict:
    """Elle düzenlenen hücre: (tarih, task no) satırına yazar; boş değer öneriye döndürür. Dönüş: günün rotası."""
    tarih = _tarih(tarih)
    task_no = str(task_no or "").strip()
    if not task_no:
        raise V2Hata("Task no eksik.", kod="alan_eksik", durum=422)
    if alan not in DUZENLENIR:
        raise V2Hata("Bu sütun elle değiştirilemez.", kod="alan_gecersiz", durum=422)
    if alan in ("giris", "cikis"):
        deger = saat_duzelt(deger)
    else:
        deger = re.sub(r"\s+", " ", str(deger or "")).strip()[:EN_UZUN] or None
        if deger and alan == "durum":
            deger = deger.replace("i", "İ").replace("ı", "I").upper()
    conn.row_factory = sqlite3.Row
    r = conn.execute("SELECT is_no, boss_task_no, atanan_id, boss_ekip FROM is_emri WHERE boss_task_no=? OR "
                     "(boss_task_no IS NULL AND is_no=?)", (task_no, task_no)).fetchone()
    var = _kayitlar(conn, tarih).get(task_no)
    if r is None and var is None:
        raise V2Hata("Bu iş bulunamadı.", kod="bulunamadi", durum=404)
    ekip = (var or {}).get("ekip")
    if not ekip and r is not None:
        atanan = kisi.kisiler(conn, [r["atanan_id"]]).get(r["atanan_id"]) if r["atanan_id"] else None
        ekip = _ekip(r, atanan, None, {})[0]
        ekip = None if ekip == EKIPSIZ else ekip
    ek_sema.yedekli_kur(conn, "rut", SEMA, (TABLO,))
    with islem(conn):
        conn.execute(f"INSERT INTO rut_satir (tarih, task_no, ekip, {alan}, guncelleme, kullanici_id, kullanici_ad) "
                     f"VALUES (?,?,?,?,?,?,?) ON CONFLICT(tarih, task_no) DO UPDATE SET {alan}=excluded.{alan}, "
                     "ekip=COALESCE(rut_satir.ekip, excluded.ekip), guncelleme=excluded.guncelleme, "
                     "kullanici_id=excluded.kullanici_id, kullanici_ad=excluded.kullanici_ad",
                     (tarih, task_no, ekip, deger, zaman.metin(), (k or {}).get("id"), (k or {}).get("ad")))
    return gun(conn, k, tarih)
