"""Turkcell süreç kuralları (EK-12; kaynak belgeler/TURKCELL_SUREC_BILGISI.md) — HEPSİ ayar anahtarıdır.

Koddaki değerler yalnız VARSAYILANDIR: ``ayar`` tablosunda aynı anahtar varsa o geçerlidir (``PUT /api/isler/kurallar``
ile değişir; yönetim kaydına yazılır). Belgede kesin olmayan değerler (6/12 s BTK hedefi, "TT kaynaklı" askı, ulaşılamadı
kapanışının kimde olduğu) kullanıcı teyidine kadar varsayılanla çalışır; ``BELIRSIZ`` sözlüğü bunları ekranda işaretler.

Buradaki fonksiyonlar saf hesaptır (veritabanına yazmaz): eşleşme, hedef saat, askı sınırı, iş günü, BTK şikâyet
sayacı, arama merdiveni, kesinti bülteni ayrıştırma. Yazan taraf ``akis`` / ``kesinti`` modülleridir.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import re
import sqlite3

from operasyon import is_emri as ie

# ============================================================================= varsayılanlar
VARSAYILAN: dict[str, object] = {
    # 1 · Hedef (SL) saatleri: Task Adı'nda (sade) SÖZCÜK olarak geçen desen → saat. Eşleşmeyen: varsayılan 24 s.
    #     FOX dışa aktarımı gelince iş başına FOX "Hedef SL" bunun önüne geçer (sonraki faz).
    "hedef_saatleri": {"varsayilan": 24, "kurallar": [
        {"desen": "MODEM DEGISIKLIGI", "saat": 168, "not": "Modem değişim SL 7 gün"},
        {"desen": "CIHAZ IADE BEKLENIYOR", "saat": 360, "not": "Cihaz İade Bekleniyor 15 gün"},
        {"desen": "TT FIBER", "saat": 48, "not": "TT fiber saha bağlantı problemi 48 s"},
        {"desen": "ATA", "saat": 168, "not": "ATA 7 gün"},
    ]},
    # 2 · Şerit ve BTK hedefi (ilk eşleşen kazanır; eşleşmeyen SAHA). 6/12 s kullanıcının FOX "Hedef SL" değerleridir;
    #     belgede bulunamadı → teyit bekliyor (BELIRSIZ). 24 s yapmak için yalnız bu ayar değişir.
    "serit_kurallari": [
        {"desen": "TV ARIZA", "serit": "BTK", "btk_saat": 6},
        {"desen": "BAGLANTI PROBLEM", "serit": "BTK", "btk_saat": 12},
        {"desen": "ARAMA PROBLEM", "serit": "BTK", "btk_saat": 12},
        {"desen": "DOPING", "serit": "BTK", "btk_saat": 24},
        {"desen": "KANAL SIKAYET", "serit": "MASA", "btk_saat": None},
        {"desen": "SORU CEVAP", "serit": "MASA", "btk_saat": None},
        {"desen": "IADE", "serit": "LOJISTIK", "btk_saat": None},
        {"desen": "GERI ALIM", "serit": "LOJISTIK", "btk_saat": None},
    ],
    # 3 · En üst öncelik: "SL içinde kanal şikâyeti açılmaz" → bayiye düşmüş 40 Kanal Şikâyeti SL'i zaten kaçırmıştır.
    "oncelikli_isler": [
        {"desen": "KANAL SIKAYET", "neden": "Kanal şikâyeti: süre zaten kaçmış — önce bu"},
    ],
    # 4 · BTK saatini durduran askı nedenleri (sade() içinde geçen parça). TT kaynaklı BİLEREK yok (teyit bekliyor).
    "btk_durduran_aski": ["abone", "bilgi belge", "btk sureci", "genel ariza"],
    # 5 · Askı üst sınırları (saat). Fiber teknikte abone kaynaklı en çok 4 gün; sınıra 24 s kala uyarı.
    "aski_sinirlari": {"abone": 96, "abone_uyari": 72, "malzeme": 8, "malzeme_btk": 2, "genel_ariza": 168,
                       "bilgi_belge": 240, "diger": 72, "diger_btk": 24},
    # 6 · Abone kaynaklı askının geçerliliği: Webphone ile aranmış + ilk aramadan sonra SMS + 2 farklı günde arama.
    #     Geçersizse askı süresi saate EKLENMEZ ve "geçersiz askı" uyarısı çıkar. BOSS'tan gelen askının aramaları
    #     bizde görünmez: ``boss_askisina_guven`` açıkken rapordaki abone askısı geçerli sayılır.
    "aski_gecerlilik": {"acik": True, "webphone": True, "sms": True, "farkli_gun": 2, "boss_askisina_guven": True},
    # 7 · Ulaşılamayan müşteri merdiveni (EÇM Müşteri Arama Kuralları, 29.04.2026)
    "arama_merdiveni": {"pencere": "10:00-18:00", "son_saat": "22:00", "ara_saat": 3, "gun1": 2, "gun2": 2,
                        "min_sure_sn": 30, "sms_zorunlu": True},
    # 8 · BTK şikâyet sayacı (şikâyeti bildirilmiş işte): ilk 10 iş günü, reopen 5; alarmlar 8./10. (3./5.) iş günü
    "btk_sikayet": {"ilk_is_gunu": 10, "reopen_is_gunu": 5, "alarm_ilk": [8, 10], "alarm_reopen": [3, 5]},
    # İş günü hesabında atlanan günler: "AA-GG" her yıl; "AAAA-AA-GG" o gün. Dini bayramlar yıl yıl eklenir.
    "resmi_tatiller": ["01-01", "04-23", "05-01", "05-19", "07-15", "08-30", "10-29",
                       "2026-03-20", "2026-03-21", "2026-03-22", "2026-05-27", "2026-05-28", "2026-05-29",
                       "2026-05-30"],
    # 9 · Kesintiye duyarlı sevk: bültendeki ilçede bu iş tipleri "Genel arıza — sevk etme" olur
    "kesinti_etkilenen": ["BAGLANTI PROBLEM", "TV ARIZA", "ARAMA PROBLEM", "DOPING"],
    "kesinti_ornek_esigi": 5,
    "kesinti_ornek_saat": 12,
}

# Kullanıcı teyidi bekleyen varsayılanlar (ekranda "teyit bekliyor" işareti; belgeler/TURKCELL_SUREC_BILGISI.md sorular)
BELIRSIZ: dict[str, str] = {
    "serit_kurallari": "TV 6 s / Bağlantı 12 s belgede bulunamadı; FOX 'Hedef SL' değerinden geliyor.",
    "btk_durduran_aski": "TT kaynaklı askının BTK saatini durdurup durdurmadığı belirsiz (varsayılan: durdurmaz).",
    "hedef_saatleri": "BOSS 'Modem Değişikliği' işinin 7 günlük modem değişim SL'ine girdiği teyit edilmeli.",
}

ACIKLAMA: dict[str, str] = {
    "hedef_saatleri": "İş tipine göre hedef süre (saat). Eşleşmeyen iş 24 saat.",
    "serit_kurallari": "İş tipine göre şerit ve BTK hedefi.",
    "oncelikli_isler": "Listede en üste çıkan iş tipleri.",
    "btk_durduran_aski": "Nedeninde bu sözcükler geçen askı BTK saatini durdurur.",
    "aski_sinirlari": "Askının en uzun süresi (saat).",
    "aski_gecerlilik": "Abone kaynaklı askının saati durdurması için gereken aramalar.",
    "arama_merdiveni": "Ulaşılamayan müşteriyi arama kuralları.",
    "btk_sikayet": "BTK şikâyet süresi (iş günü) ve alarm günleri.",
    "resmi_tatiller": "İş günü hesabında atlanan günler.",
    "kesinti_etkilenen": "Genel arızada sevk edilmeyen iş tipleri.",
    "kesinti_ornek_esigi": "Bülten yokken verimlilik ekibine gönderilecek en az örnek.",
    "kesinti_ornek_saat": "Örnek toplarken bakılan son saat.",
}


def _ham(conn: sqlite3.Connection | None, anahtar: str):
    if conn is None:
        return None
    try:
        r = conn.execute("SELECT deger FROM ayar WHERE anahtar=?", (anahtar,)).fetchone()
    except sqlite3.Error:
        return None
    if not r or r[0] in (None, ""):
        return None
    try:
        return json.loads(r[0])
    except (TypeError, ValueError):
        return None


def oku(conn: sqlite3.Connection | None, anahtar: str):
    """Kural: ayar (JSON) varsa ve biçimi varsayılanla uyumluysa o; yoksa varsayılan."""
    v = VARSAYILAN[anahtar]
    a = _ham(conn, anahtar)
    if a is None or type(a) is not type(v):
        if isinstance(v, int) and isinstance(a, (int, float)) and not isinstance(a, bool):
            return int(a)
        return json.loads(json.dumps(v))
    if isinstance(v, dict):
        return {**json.loads(json.dumps(v)), **a}
    return a


def hepsi(conn: sqlite3.Connection | None) -> dict:
    """``GET /api/isler/kurallar``: her kuralın güncel değeri + varsayılanı + açıklaması + teyit notu."""
    return {k: {"deger": oku(conn, k), "varsayilan": VARSAYILAN[k], "aciklama": ACIKLAMA.get(k, ""),
                "teyit_bekliyor": BELIRSIZ.get(k), "degisti": _ham(conn, k) is not None}
            for k in VARSAYILAN}


def dogrula(anahtar: str, deger) -> object:
    """Yazılacak değerin biçimini denetler (bozuk ayar sunucuyu düşürmesin). Hata → ValueError (Türkçe)."""
    if anahtar not in VARSAYILAN:
        raise ValueError(f"Tanınmayan kural: {anahtar}")
    v = VARSAYILAN[anahtar]
    if type(deger) is not type(v):
        if isinstance(v, int) and isinstance(deger, (int, float)) and not isinstance(deger, bool):
            deger = int(deger)
        else:
            raise ValueError(f"'{anahtar}' için biçim uygun değil.")
    if anahtar in ("hedef_saatleri",):
        for k in deger.get("kurallar", []):
            if not isinstance(k, dict) or not ie.sade(k.get("desen") or "") or not 1 <= float(k.get("saat") or 0) <= 24 * 60:
                raise ValueError("Her hedef kuralında desen ve 1–1440 arası saat olmalı.")
        if not 1 <= float(deger.get("varsayilan") or 0) <= 24 * 60:
            raise ValueError("Varsayılan hedef 1–1440 saat olmalı.")
    if anahtar == "serit_kurallari":
        for k in deger:
            if not isinstance(k, dict) or k.get("serit") not in ("BTK", "SAHA", "MASA", "LOJISTIK") \
                    or not ie.sade(k.get("desen") or ""):
                raise ValueError("Her şerit kuralında desen ve şerit (BTK/SAHA/MASA/LOJISTIK) olmalı.")
            if k["serit"] == "BTK" and not 1 <= float(k.get("btk_saat") or 0) <= 240:
                raise ValueError("BTK kuralında 1–240 arası saat olmalı.")
    if anahtar in ("btk_durduran_aski", "kesinti_etkilenen"):
        deger = [str(x) for x in deger if ie.sade(str(x))]
    if anahtar == "resmi_tatiller":
        for x in deger:
            if not re.fullmatch(r"(\d{4}-)?\d{2}-\d{2}", str(x)):
                raise ValueError("Tatil günü 'AA-GG' ya da 'AAAA-AA-GG' olmalı.")
    return deger


# ============================================================================= eşleşme
def eslesir(desen: str, metin: str) -> bool:
    """Desen, metnin (sade) içinde SÖZCÜK sınırıyla geçiyor mu ("ATA" 'SATAŞ'ta değil, 'ATA ARAMASI'nda eşleşir)."""
    d, m = ie.sade(desen or ""), ie.sade(metin or "")
    if not d or not m:
        return False
    return re.search(rf"(?<![A-Z0-9]){re.escape(d)}", m) is not None


def serit(kural: list[dict], task_adi: str) -> tuple[str, int | None]:
    for k in kural or ():
        if eslesir(k.get("desen", ""), task_adi):
            s = k.get("serit") or "SAHA"
            return s, (int(k["btk_saat"]) if s == "BTK" and k.get("btk_saat") else None)
    return "SAHA", None


def hedef_saat(kural: dict, task_adi: str) -> int:
    for k in (kural or {}).get("kurallar", ()):
        if eslesir(k.get("desen", ""), task_adi):
            return int(k.get("saat") or 24)
    return int((kural or {}).get("varsayilan") or 24)


def oncelik(kural: list[dict], task_adi: str) -> str | None:
    for k in kural or ():
        if eslesir(k.get("desen", ""), task_adi):
            return k.get("neden") or "Öncelikli iş"
    return None


def yukle(conn: sqlite3.Connection | None) -> dict:
    """Bir aktarım/yanıt boyunca bir kez okunan kurallar."""
    return {"serit": oku(conn, "serit_kurallari"), "hedef": oku(conn, "hedef_saatleri"),
            "oncelik": oku(conn, "oncelikli_isler")}


# ============================================================================= askı
def aski_turu(neden: str | None) -> str:
    s = ie.sade(neden or "")
    if "MALZEME" in s:
        return "malzeme"
    if "GENEL ARIZA" in s:
        return "genel_ariza"
    if ("BILGI" in s and "BELGE" in s) or "BTK SURECI" in s:
        return "bilgi_belge"
    if "ABONE" in s or "MUSTERI" in s:
        return "abone"
    return "diger"


def aski_siniri(conn, neden: str | None, serit_: str | None) -> dt.timedelta:
    """Uyanma üst sınırı (spec §3.1 + EK-12.3): abone kaynaklı 4 g, malzeme 8 s (BTK 2 s), diğer 3 g (BTK 1 g)."""
    s = oku(conn, "aski_sinirlari")
    tur = aski_turu(neden)
    btk = serit_ == "BTK"
    saat = s.get(f"{tur}_btk") if btk and s.get(f"{tur}_btk") else s.get(tur)
    if saat is None:
        saat = s.get("diger_btk" if btk else "diger", 72)
    return dt.timedelta(hours=float(saat))


def abone_aski_gecerli(aramalar: list[dict], kural: dict) -> tuple[bool, str | None]:
    """EK-12.3: Webphone ile aranmış + ilk aramadan sonra SMS + ``farkli_gun`` farklı günde arama.

    ``aramalar``: [{zaman, sonuc, webphone, sms}] (eskiden yeniye). Dönüş: (geçerli, eksik olanın Türkçe cümlesi).
    """
    if not kural.get("acik", True):
        return True, None
    wp = [a for a in aramalar if a.get("webphone", True) or not kural.get("webphone", True)]
    if not wp:
        return False, "Webphone ile arama kaydı yok"
    if kural.get("sms", True) and not any(a.get("sms") for a in wp):
        return False, "Ulaşılamadı SMS'i gönderilmemiş"
    gunler = {str(a["zaman"])[:10] for a in wp}
    gerek = int(kural.get("farkli_gun") or 2)
    if len(gunler) < gerek:
        return False, f"{gerek} farklı günde arama yok ({len(gunler)} gün)"
    return True, None


# ============================================================================= iş günü
def _tatil_mi(gun: dt.date, tatiller: list[str]) -> bool:
    return gun.strftime("%m-%d") in tatiller or gun.isoformat() in tatiller


def is_gunu_mu(gun: dt.date, tatiller: list[str]) -> bool:
    return gun.weekday() < 5 and not _tatil_mi(gun, tatiller)


def is_gunu_ekle(bas: dt.datetime, n: int, tatiller: list[str]) -> dt.datetime:
    """``bas``tan sonraki n'inci iş gününün sonu (23:59:59). Başlangıç günü sayılmaz."""
    gun = bas.date()
    kalan = int(n)
    while kalan > 0:
        gun += dt.timedelta(days=1)
        if is_gunu_mu(gun, tatiller):
            kalan -= 1
    return dt.datetime.combine(gun, dt.time(23, 59, 59))


def gecen_is_gunu(bas: dt.datetime, simdi: dt.datetime, tatiller: list[str]) -> int:
    """Başlangıçtan bu yana biten + içinde bulunulan iş günü sayısı (başlangıç günü 0; ertesi iş günü 1…)."""
    n = 0
    gun = bas.date()
    while gun < simdi.date():
        gun += dt.timedelta(days=1)
        if is_gunu_mu(gun, tatiller):
            n += 1
    return n


def btk_sikayet_durumu(sikayet: dict | None, tcs: str | None, simdi: dt.datetime, kural: dict,
                       tatiller: list[str]) -> dict | None:
    """``sikayet``: {tarih, reopen}. Dönüş: {baslama, reopen, sure_is_gunu, gecen_is_gunu, son_gun, kalan_is_gunu,
    alarm (None | '8. iş günü' …), gecikti, tcs, btk_kapali}."""
    if not sikayet or not sikayet.get("tarih"):
        return None
    from . import zaman
    bas = zaman.oku(sikayet["tarih"])
    if bas is None:
        return None
    reopen = bool(sikayet.get("reopen"))
    sure = int(kural.get("reopen_is_gunu" if reopen else "ilk_is_gunu") or (5 if reopen else 10))
    alarmlar = [int(x) for x in (kural.get("alarm_reopen" if reopen else "alarm_ilk") or [])]
    gecen = gecen_is_gunu(bas, simdi, tatiller)
    son = is_gunu_ekle(bas, sure, tatiller)
    alarm = None
    for a in sorted(alarmlar):
        if gecen >= a:
            alarm = f"{a}. iş günü"
    return {"baslama": zaman.metin(bas), "reopen": reopen, "sure_is_gunu": sure, "gecen_is_gunu": gecen,
            "son_gun": zaman.metin(son), "kalan_is_gunu": max(0, sure - gecen), "alarm": alarm,
            "gecikti": simdi > son, "tcs": tcs, "btk_kapali": bool(tcs)}


# ============================================================================= arama merdiveni
ULASILAMADI_SONUCLARI = ("ulasilamadi", "mesgul_kapali", "dit")
ARAMA_SONUCLARI = ("ulasildi", *ULASILAMADI_SONUCLARI, "yanlis_no")


def _saat(metin: str, varsayilan: dt.time) -> dt.time:
    try:
        s, d = (int(x) for x in str(metin).strip().split(":")[:2])
        return dt.time(s % 24, d % 60)
    except (ValueError, TypeError):
        return varsayilan


def pencere(kural: dict) -> tuple[dt.time, dt.time, dt.time]:
    p = str(kural.get("pencere") or "10:00-18:00").split("-")
    bas = _saat(p[0], dt.time(10))
    bit = _saat(p[1] if len(p) > 1 else "18:00", dt.time(18))
    son = _saat(kural.get("son_saat") or "22:00", dt.time(22))
    return bas, bit, son


def aranabilir_mi(an: dt.datetime, kural: dict) -> tuple[bool, str | None]:
    """22:00 sonrası ve pencere başlangıcından önce arama yok (EK-12.4). Pencere sonrası (18–22) müşteri isterse olur."""
    bas, _bit, son = pencere(kural)
    if an.time() >= son:
        return False, f"{son:%H:%M}'den sonra müşteri aranmaz."
    if an.time() < bas:
        return False, f"Müşteri {bas:%H:%M}'dan önce aranmaz."
    return True, None


def _sonraki_pencere(an: dt.datetime, kural: dict) -> dt.datetime:
    bas, bit, _son = pencere(kural)
    if an.time() < bas:
        return an.replace(hour=bas.hour, minute=bas.minute, second=0)
    if an.time() >= bit:
        ert = an + dt.timedelta(days=1)
        return ert.replace(hour=bas.hour, minute=bas.minute, second=0)
    return an


def merdiven_durumu(aramalar: list[dict], kural: dict, simdi: dt.datetime) -> dict:
    """Ulaşılamayan müşteri merdiveni (EK-12.4): Gün 1 A1 → (≥3 s) A2; Gün 2 A3 (zorunlu) → (≥3 s) A4. Her ulaşılamayan
    aramadan sonra BOSS "Talep Ulaşamama SMS". Yanlış numara → ATA havuzu; yeni numarada merdiven sıfırlanır.

    ``aramalar``: [{zaman, sonuc, webphone, sms, yeni_numara}] eskiden yeniye. Yalnız son "yeni numara"dan sonrası ve
    Webphone ile yapılanlar sayılır; aynı gün içinde öncekinden ``ara_saat``ten erken yapılan arama adım sayılmaz.
    Tamam = en az ``gun1 + gun2`` geçerli arama, en az iki farklı günde (ilk arama akşama denk gelirse 2. arama ertesi
    güne kayabilir; kural toplamı ve iki günü arar).
    Dönüş: {deneme, gecerli, gunler, son, sonraki, tamam, eksik, sms_eksik, ulasildi, ata_havuzu}
    """
    from . import zaman
    son_sifir = max((i for i, a in enumerate(aramalar) if a.get("yeni_numara")), default=0)
    liste = list(aramalar[son_sifir:])                  # yeni numarayla yapılan arama merdivenin ilk adımıdır
    ulasildi = any(a.get("sonuc") == "ulasildi" for a in liste)
    ata = bool(liste) and liste[-1].get("sonuc") == "yanlis_no"
    basarisiz = [a for a in liste if a.get("sonuc") in ULASILAMADI_SONUCLARI and a.get("webphone", True)]
    ara = dt.timedelta(hours=float(kural.get("ara_saat") or 3))
    gun1_gerek = int(kural.get("gun1") or 2)
    gerek = gun1_gerek + int(kural.get("gun2") or 1)
    gunler: dict[str, list[dt.datetime]] = {}
    for a in basarisiz:
        t = zaman.oku(a["zaman"])
        if t is None:
            continue
        g = gunler.setdefault(t.date().isoformat(), [])
        if not g or t - g[-1] >= ara:
            g.append(t)
    gun_sirasi = sorted(gunler)
    gecerli = sum(len(v) for v in gunler.values())
    tamam = not ulasildi and gecerli >= gerek and len(gun_sirasi) >= 2
    sms_eksik = sum(1 for a in basarisiz if not a.get("sms")) if kural.get("sms_zorunlu", True) else 0
    # sonraki arama son GEÇERLİ adımdan ``ara_saat`` sonra (erken yapılan arama saati ileri itmez)
    son = max((t for g in gunler.values() for t in g), default=None)
    eksik = sonraki = None
    if not ulasildi and not tamam and not ata:
        if gecerli < gerek:
            eksik = f"{gerek - gecerli} arama daha gerekli ({gecerli}/{gerek})"
        else:
            eksik = "İkinci bir günde arama gerekli"
        if son is None:
            aday = simdi
        elif len(gun_sirasi) == 1 and len(gunler[gun_sirasi[0]]) >= gun1_gerek:
            aday = dt.datetime.combine(son.date() + dt.timedelta(days=1), dt.time(0))     # 1. gün doldu → ertesi gün
        else:
            aday = son + ara
        sonraki = zaman.metin(_sonraki_pencere(max(aday, simdi), kural))
    return {"deneme": len(basarisiz), "gecerli": gecerli, "gerekli": gerek, "gunler": [len(gunler[g]) for g in gun_sirasi],
            "son": zaman.metin(son) if son else None, "sonraki": sonraki, "tamam": tamam, "eksik": eksik,
            "sms_eksik": sms_eksik, "ulasildi": ulasildi, "ata_havuzu": ata}


# ============================================================================= kesinti bülteni
_DURUMLAR = (("DEVAM EDIYOR", "devam"), ("PLANLANDI", "planli"), ("BITTI", "bitti"))


def kesinti_ayristir(metin: str, ilceler: list[tuple[str, str, str, str]]) -> dict:
    """"Santral Arıza" bülten metni → {ilceler:[(il_k, ilce_k, il, ilce)], tur, durum, no, baslama_saat, etki_musteri}.

    ``ilceler``: ``ilce`` tablosunun (il_k, ilce_k, il, ad) satırları. İlçe metinde "BURSA-NİLÜFER", "Bursa/Nilüfer" ya da
    yalnız adıyla geçebilir; yalnız Bursa/Yalova ilçeleri tanınır ("Merkez" yalnız metinde Yalova geçiyorsa).
    Tür GPON/FTTX; durum Devam ediyor/Planlandı/Bitti (yazmıyorsa 'devam').
    """
    s = ie.sade(metin or "")
    bulunan = []
    for il_k, ilce_k, il, ad in ilceler:
        a = ie.sade(ad)
        if not a or (ie.anahtar(ad) == "MERKEZ" and "YALOVA" not in s):
            continue
        if re.search(rf"(?<![A-Z]){re.escape(a)}(?![A-Z])", s):
            bulunan.append((il_k, ilce_k, il, ad))
    tur = "GPON" if "GPON" in s else "FTTX" if ("FTTX" in s or "FTTB" in s) else None
    durum = next((k for d, k in _DURUMLAR if d in s), "devam")
    no = re.search(r"(?:BULTEN\s*NO|NO)\s*(\d{3,})", s)
    saat = re.search(r"BASLADI\s*(\d{1,2})\s(\d{2})", s)
    musteri = re.search(r"(\d+)\s*MUSTERI", s)
    return {"ilceler": bulunan, "tur": tur, "durum": durum, "no": no.group(1) if no else None,
            "baslama_saat": f"{int(saat.group(1)):02d}:{saat.group(2)}" if saat else None,
            "etki_musteri": int(musteri.group(1)) if musteri else None}


def yuvarla_yukari(x: float) -> int:
    return int(math.ceil(x))
