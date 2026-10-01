"""Saha Sistemi lisansı — DOĞRULAMA tarafı (uygulamayla birlikte gider).

Bu modül YALNIZ doğrular. İçinde özel anahtar yükleyen ya da imza atan kod yoktur; imzalama
``lisans/uret.py``'dedir ve yalnız lisans sahibinin bilgisayarında çalışır. Özel anahtar hiçbir
zaman uygulamaya ya da depoya girmez.

İlkeler (ayrıntı: belgeler/LISANS.md)
  * Şeffaf: lisansın bütün koşulları dosyada düz metin durur ve uygulamada gösterilir.
    İmza yalnız "bu metni lisans sahibi yazdı, kimse değiştirmedi" der.
  * Gizli kapatma YOK: uzaktan kapatma, veri silme, veriyi kilitleme ya da şifreleme yoktur.
  * Süre dolunca ``ek_sure_gun`` (varsayılan 14) gün EK SÜRE: her şey çalışır, açık uyarı görünür.
    Sonra SALT OKUNUR: görüntüleme ve dışa aktarma sürer, yalnız yeni kayıt yapılamaz. Geçerli
    lisans yüklendiği anda her şey kaldığı yerden devam eder.
  * Aynı ek süre "imza bozuk", "cihaz dışı", "lisans yok", "henüz başlamadı" durumlarında da
    vardır ve sorunun İLK görüldüğü günden sayılır; sorunu değiştirerek süre uzatılamaz.
  * Genel anahtar dosyası (``lisans/genel_anahtar.pem``) yoksa denetim KAPALIDIR ("denetlenmiyor"):
    lisans kurulmadan önce hiçbir kurulum kazara salt okunur olmaz.

Sunucuda kullanım
    from lisans import lisans
    denetci = lisans.Denetci("saha/lisans.json")      # durum dosyası: saha/lisans_durum.json
    s = denetci.sonuc()                               # önbellekli; dosya/tarih değişince yeniler
    s.mod                                             # "tam" | "salt_okunur"
    s.sozluk(yonetici=True)                           # GET /api/lisans gövdesi
    lisans.yazma_serbest_mi("POST", "/api/giris")     # salt okunur modda serbest yazma uçları
    denetci.yukle(metin)                              # POST /api/lisans: doğrula + güvenle kur

Komut satırı
    python -m lisans.lisans cihaz                     # bu bilgisayarın cihaz kimliği
    python -m lisans.lisans denetle saha/lisans.json  # lisansın durumu
"""
from __future__ import annotations

import argparse
import base64
import binascii
import dataclasses
import datetime as dt
import functools
import hashlib
import json
import os
import re
import sys
import tempfile
import threading
import time
import unicodedata
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import yollar

# ============================================================================= sabitler
BICIM = "saha-lisans/1"                 # dosya biçimi
BICIM_SURUMU = 1                        # lisans içeriğindeki "surum"
URUN = "saha-sistemi"
ANAHTAR_ONEKI = "SAHA1"                 # tek satırlık lisans metni: SAHA1.<içerik>.<imza>
IMZA_ONEKI = b"saha-lisans/1\n"         # imzalanan bayt dizisinin başı (başka amaçlı imzayla karışmasın)

UYARI_GUN = 30                          # bitişe bu kadar gün kala yöneticiye bilgi şeridi
YAKIN_UYARI_GUN = 7                     # bu kadar gün kala sarı (uyarı)
VARSAYILAN_EK_SURE_GUN = 14
EN_COK_EK_SURE_GUN = 90
KRITIK_GUN = 3                          # ek sürenin son bu kadar günü kırmızı; ekip de görür
ONBELLEK_SN = 600                       # Denetci sonucu en çok bu kadar saniye önbellekte kalır
SAAT_SICRAMA_SINIRI_GUN = 400           # bundan büyük ileri sıçrama "son görülen tarih" olarak yazılmaz
EN_BUYUK_METIN = 64 * 1024

TR = dt.timezone(dt.timedelta(hours=3), "TRT")   # Türkiye tüm yıl UTC+3
VARSAYILAN_GENEL_ANAHTAR = yollar.KOD / "lisans" / "genel_anahtar.pem"

# Durumlar
GECERLI = "gecerli"
SURESI_YAKIN = "suresi_yakin"
SURESI_DOLDU = "suresi_doldu"
IMZA_BOZUK = "imza_bozuk"               # okunamadı / imza tutmuyor / başka anahtar / içerik geçersiz
CIHAZ_DISI = "cihaz_disi"
LISANS_YOK = "lisans_yok"
HENUZ_BASLAMADI = "henuz_baslamadi"
DENETLENMIYOR = "denetlenmiyor"         # genel anahtar yapılandırılmamış: denetim kapalı
SORUNSUZ = frozenset({GECERLI, SURESI_YAKIN, DENETLENMIYOR})

# Çalışma kipleri
TAM = "tam"
SALT_OKUNUR = "salt_okunur"

# Özellik bayrakları: ad → (etiket, lisansta hiç yazmıyorsa varsayılan). Listede olmayan bir
# bayrak (ileride satılacak ek modül) lisansta açıkça ``true`` değilse KAPALIDIR.
OZELLIKLER: dict[str, tuple[str, bool]] = {
    "satis": ("Satış: bina listesi, rota, ziyaret", True),
    "is_emri": ("İş emirleri: operasyon ve teknik", True),
}

AYLAR = ("Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül",
         "Ekim", "Kasım", "Aralık")

_TARIH_DESENI = re.compile(r"\d{4}-\d{2}-\d{2}")
_LISANS_NO_DESENI = re.compile(r"[A-Z0-9][A-Z0-9-]{3,39}")
_CIHAZ_DESENI = re.compile(r"[0-9A-F]{4}(?:-[0-9A-F]{4}){4}")
_OZELLIK_DESENI = re.compile(r"[a-z][a-z0-9_]{0,31}")
_PEM_DESENI = re.compile(rb"-----BEGIN PUBLIC KEY-----.+?-----END PUBLIC KEY-----", re.S)
_B64_DESENI = re.compile(r"[A-Za-z0-9_-]*")


class LisansHatasi(Exception):
    """Kullanıcıya gösterilebilir Türkçe hata (``kod`` API yanıtındaki ``kod`` alanıdır)."""

    def __init__(self, mesaj: str, kod: str = "lisans_gecersiz"):
        super().__init__(mesaj)
        self.mesaj = mesaj
        self.kod = kod


# ============================================================================= tarih
def turkiye_bugun() -> dt.date:
    return dt.datetime.now(TR).date()


def tarih_coz(metin: Any) -> dt.date:
    """Katı ISO tarih (YYYY-AA-GG); başka her şey ``ValueError``."""
    if not isinstance(metin, str) or not _TARIH_DESENI.fullmatch(metin):
        raise ValueError(f"tarih YYYY-AA-GG olmalı: {metin!r}")
    return dt.date.fromisoformat(metin)


def buyuk_harf(metin: str) -> str:
    """Türkçe büyük harf: ``str.upper()`` 'i'yi 'I' yapar ("SISTEM"); doğrusu 'İ' ("SİSTEM")."""
    return metin.replace("i", "İ").upper()


def tarih_metni(gun: dt.date | None) -> str:
    """``31 Ekim 2026`` — arayüzde ve mesajlarda kullanılan biçim."""
    if gun is None:
        return ""
    return f"{gun.day} {AYLAR[gun.month - 1]} {gun.year}"


# ============================================================================= base64url
def b64e(veri: bytes) -> str:
    return base64.urlsafe_b64encode(veri).rstrip(b"=").decode("ascii")


def b64d(metin: str) -> bytes:
    if not isinstance(metin, str) or not _B64_DESENI.fullmatch(metin):
        raise LisansHatasi("Lisans metni bozuk (geçersiz karakter).")
    try:
        return base64.urlsafe_b64decode(metin + "=" * (-len(metin) % 4))
    except (binascii.Error, ValueError) as exc:
        raise LisansHatasi(f"Lisans metni bozuk ({exc}).") from None


# ============================================================================= kanonik JSON
def _normalle(deger: Any, yol: str = "lisans") -> Any:
    """İmzalanabilir değer: str (NFC) · int · bool · None · liste · sözlük (str anahtar). Kesirli sayı YOK."""
    if deger is None or isinstance(deger, bool):
        return deger
    if isinstance(deger, int):
        return deger
    if isinstance(deger, str):
        return unicodedata.normalize("NFC", deger)
    if isinstance(deger, list):
        return [_normalle(x, f"{yol}[{i}]") for i, x in enumerate(deger)]
    if isinstance(deger, dict):
        cikti = {}
        for k, v in deger.items():
            if not isinstance(k, str):
                raise LisansHatasi(f"Lisans içeriğinde metin olmayan anahtar: {yol}")
            cikti[unicodedata.normalize("NFC", k)] = _normalle(v, f"{yol}.{k}")
        return cikti
    raise LisansHatasi(f"Lisans içeriğinde desteklenmeyen değer türü ({type(deger).__name__}): {yol}")


def kanonik(yuk: dict) -> bytes:
    """İmzalanan baytlar: sıralı anahtar, boşluksuz, UTF-8, NFC.

    Aynı içerik hangi dosyada, hangi girintiyle, hangi Unicode biçimiyle kaydedilirse kaydedilsin
    aynı baytları verir; Not Defteri'nin BOM'u ya da NFD'ye çeviren bir düzenleyici lisansı bozmaz.
    """
    return json.dumps(_normalle(yuk), ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


# ============================================================================= cihaz kimliği
@functools.lru_cache(maxsize=1)
def cihaz_bilgisi() -> dict:
    """Bu bilgisayarın cihaz kimliği ve kaynağı.

    Windows'ta ``HKLM\\SOFTWARE\\Microsoft\\Cryptography\\MachineGuid`` okunur ve ürüne özgü bir
    tuzla SHA-256 özeti alınır: ham GUID hiçbir yere yazılmaz, başka yazılımların kimliğiyle
    eşleştirilemez, kişisel veri içermez. Windows yeniden kurulursa (ya da sanal makine
    kopyalanırsa) kimlik değişir/aynı kalır — bkz. belgeler/LISANS.md §6.
    """
    ham, kaynak = None, None
    if sys.platform == "win32":
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography", 0,
                                winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as anahtar:
                ham = str(winreg.QueryValueEx(anahtar, "MachineGuid")[0]).strip()
                kaynak = "windows_machine_guid"
        except OSError:
            ham = None
    if not ham:
        for yol in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
            try:
                ham = Path(yol).read_text(encoding="ascii").strip()
                kaynak = "machine_id"
                break
            except OSError:
                continue
    if not ham:  # son çare: ağ kartı adresi (kart değişirse kimlik değişir)
        ham, kaynak = f"{uuid.getnode():012x}", "mac_adresi"
    ozet = hashlib.sha256(("saha-cihaz/1|" + ham.lower()).encode("utf-8")).hexdigest().upper()[:20]
    return {"kimlik": "-".join(ozet[i:i + 4] for i in range(0, 20, 4)), "kaynak": kaynak}


def cihaz_kimligi() -> str:
    """``XXXX-XXXX-XXXX-XXXX-XXXX`` (20 onaltılık hane; telefonda okunabilir)."""
    return cihaz_bilgisi()["kimlik"]


def cihaz_normalle(metin: Any) -> str | None:
    """Küçük harf, boşluk, tire farkını siler; 20 onaltılık hane değilse ``None``."""
    if not isinstance(metin, str):
        return None
    temiz = re.sub(r"[^0-9A-Fa-f]", "", metin).upper()
    if len(temiz) != 20 or len(re.sub(r"[\s-]", "", metin)) != 20:
        return None
    return "-".join(temiz[i:i + 4] for i in range(0, 20, 4))


# ============================================================================= anahtarlar
def _kripto():
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError:  # pragma: no cover - kurulum hatası
        raise LisansHatasi("Lisans doğrulanamıyor: 'cryptography' paketi kurulu değil "
                           "(.venv\\Scripts\\python.exe -m pip install cryptography).",
                           "kurulum_eksik") from None
    return InvalidSignature, serialization, Ed25519PublicKey


def anahtar_kimligi(genel_anahtar) -> str:
    """Genel anahtarın kısa kimliği: ham 32 baytın SHA-256'sının ilk 16 hanesi."""
    _, serialization, _ = _kripto()
    ham = genel_anahtar.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return hashlib.sha256(ham).hexdigest()[:16]


def genel_anahtarlari_yukle(kaynak: Any = None) -> list:
    """Genel anahtar(lar). Boş liste = denetim kapalı (dosya yok).

    ``kaynak``: None (varsayılan dosya) · dosya yolu · PEM metni/baytı · ham 32 bayt ·
    Ed25519PublicKey · bunların listesi. Bir PEM dosyasında birden çok anahtar olabilir
    (anahtar yenilemede eski ve yeni birlikte kabul edilir).
    """
    _, serialization, Ed25519PublicKey = _kripto()
    if kaynak is None:
        kaynak = VARSAYILAN_GENEL_ANAHTAR
    if isinstance(kaynak, (list, tuple)):
        return [a for k in kaynak for a in genel_anahtarlari_yukle(k)]
    if isinstance(kaynak, Ed25519PublicKey):
        return [kaynak]
    if isinstance(kaynak, str) and "-----BEGIN" in kaynak:
        kaynak = kaynak.encode("ascii", "ignore")
    if isinstance(kaynak, (str, os.PathLike)):
        yol = Path(kaynak)
        if not yol.is_file():
            return []
        try:
            kaynak = yol.read_bytes()
        except OSError as exc:
            raise LisansHatasi(f"Genel anahtar dosyası okunamadı ({exc}).", "anahtar_okunamadi") from None
    if isinstance(kaynak, bytes) and len(kaynak) == 32 and b"-----" not in kaynak:
        return [Ed25519PublicKey.from_public_bytes(kaynak)]
    if isinstance(kaynak, bytes):
        bloklar = _PEM_DESENI.findall(kaynak)
        if not bloklar:
            raise LisansHatasi("Genel anahtar dosyası okunamadı (PEM bloğu yok).", "anahtar_okunamadi")
        anahtarlar = []
        for blok in bloklar:
            try:
                anahtar = serialization.load_pem_public_key(blok)
            except ValueError as exc:
                raise LisansHatasi(f"Genel anahtar bozuk ({exc}).", "anahtar_okunamadi") from None
            if not isinstance(anahtar, Ed25519PublicKey):
                raise LisansHatasi("Genel anahtar Ed25519 değil.", "anahtar_okunamadi")
            anahtarlar.append(anahtar)
        return anahtarlar
    raise LisansHatasi(f"Genel anahtar tanınmadı ({type(kaynak).__name__}).", "anahtar_okunamadi")


# ============================================================================= içerik denetimi
def yuk_denetle(yuk: Any) -> list[str]:
    """Lisans içeriğinin kurallara uyup uymadığı; boş liste = uygun.

    Hem ``uret.py`` (imzalamadan önce) hem doğrulama (imza tuttuktan sonra) kullanır.
    """
    if not isinstance(yuk, dict):
        return ["lisans içeriği bir sözlük değil"]
    h: list[str] = []

    def metin(ad, en_az=1, en_cok=200, zorunlu=True):
        d = yuk.get(ad)
        if d is None and not zorunlu:
            return
        if not isinstance(d, str) or not (en_az <= len(d.strip()) <= en_cok) or \
                any(unicodedata.category(c) == "Cc" for c in d):
            h.append(f"{ad}: {en_az}–{en_cok} karakterlik düz metin olmalı")

    def tamsayi(ad, en_az, en_cok, zorunlu=True):
        d = yuk.get(ad)
        if d is None and not zorunlu:
            return
        if not isinstance(d, int) or isinstance(d, bool) or not (en_az <= d <= en_cok):
            h.append(f"{ad}: {en_az}–{en_cok} arası tam sayı olmalı")

    s = yuk.get("surum")
    if not isinstance(s, int) or isinstance(s, bool):
        h.append("surum: tam sayı olmalı")
    elif s > BICIM_SURUMU:
        h.append(f"surum {s}: bu lisans daha yeni bir biçimde; uygulamayı güncelleyin")
    elif s < 1:
        h.append("surum: geçersiz")
    if yuk.get("urun") != URUN:
        h.append(f"urun: bu lisans '{URUN}' için değil")
    if not isinstance(yuk.get("lisans_no"), str) or not _LISANS_NO_DESENI.fullmatch(yuk["lisans_no"]):
        h.append("lisans_no: büyük harf, rakam ve tire (4–40)")
    metin("musteri", 1, 200)
    metin("bayi_kodu", 0, 40)
    metin("not", 0, 300, zorunlu=False)
    if yuk.get("onceki_lisans_no") is not None and (
            not isinstance(yuk["onceki_lisans_no"], str)
            or not _LISANS_NO_DESENI.fullmatch(yuk["onceki_lisans_no"])):
        h.append("onceki_lisans_no: geçersiz")
    tarihler = {}
    for ad in ("baslangic", "bitis", "duzenleme_tarihi"):
        try:
            tarihler[ad] = tarih_coz(yuk.get(ad))
        except ValueError:
            h.append(f"{ad}: YYYY-AA-GG biçiminde tarih olmalı")
    if "baslangic" in tarihler and "bitis" in tarihler and tarihler["bitis"] < tarihler["baslangic"]:
        h.append("bitis başlangıçtan önce olamaz")
    tamsayi("cihaz_siniri", 1, 1000)
    tamsayi("ek_sure_gun", 0, EN_COK_EK_SURE_GUN)
    tamsayi("kullanici_siniri", 1, 100000, zorunlu=False)
    cihazlar = yuk.get("izinli_cihazlar")
    if not isinstance(cihazlar, list):
        h.append("izinli_cihazlar: liste olmalı (boş liste = her bilgisayar)")
    else:
        if any(not isinstance(c, str) or not _CIHAZ_DESENI.fullmatch(c) for c in cihazlar):
            h.append("izinli_cihazlar: her kimlik XXXX-XXXX-XXXX-XXXX-XXXX biçiminde olmalı")
        if len(set(map(str, cihazlar))) != len(cihazlar):
            h.append("izinli_cihazlar: aynı kimlik iki kez yazılmış")
        sinir = yuk.get("cihaz_siniri")
        if isinstance(sinir, int) and len(cihazlar) > sinir:
            h.append(f"izinli_cihazlar: {len(cihazlar)} kimlik var, cihaz sınırı {sinir}")
    ozellikler = yuk.get("ozellikler")
    if not isinstance(ozellikler, dict) or any(
            not isinstance(k, str) or not _OZELLIK_DESENI.fullmatch(k) or not isinstance(v, bool)
            for k, v in ozellikler.items()):
        h.append("ozellikler: {ad: true/false} olmalı (ad: küçük harf, rakam, _)")
    for ad, deger in yuk.items():
        if isinstance(deger, float):
            h.append(f"{ad}: kesirli sayı kullanılamaz")
    return h


# ============================================================================= dosya biçimleri
_SIRA = ("surum", "urun", "lisans_no", "musteri", "bayi_kodu", "baslangic", "bitis", "ek_sure_gun",
         "cihaz_siniri", "izinli_cihazlar", "kullanici_siniri", "ozellikler", "duzenleme_tarihi",
         "onceki_lisans_no", "not")


def dosya_metni(yuk: dict, imza: bytes, kimlik: str | None = None) -> str:
    """Okunabilir lisans dosyası (``saha/lisans.json``). İmza kanonik içeriğe atılır; girinti önemsiz."""
    yuk = _normalle(yuk)
    sirali = {k: yuk[k] for k in _SIRA if k in yuk}
    sirali.update({k: v for k, v in yuk.items() if k not in sirali})
    govde = {
        "bicim": BICIM,
        "aciklama": "Saha Sistemi lisansı. İçerik okunabilir; tek bir harf bile değişirse imza "
                    "tutmaz ve lisans geçersiz sayılır. Ayrıntı: belgeler/LISANS.md",
        "lisans": sirali,
        "anahtar_kimligi": kimlik,
        "imza": b64e(imza),
    }
    return json.dumps(govde, ensure_ascii=False, indent=2) + "\n"


def anahtar_metni(yuk: dict, imza: bytes) -> str:
    """Tek satırlık lisans metni (e-postayla gönderilir, Ayarlar › Lisans'a yapıştırılır)."""
    return f"{ANAHTAR_ONEKI}.{b64e(kanonik(yuk))}.{b64e(imza)}"


def coz(metin: str) -> tuple[dict, bytes, str | None]:
    """Lisans dosyası ya da lisans metni → (içerik, imza, anahtar kimliği ipucu). İmzayı DENETLEMEZ."""
    if not isinstance(metin, str):
        raise LisansHatasi("Lisans metin olarak okunamadı.")
    if len(metin) > EN_BUYUK_METIN:
        raise LisansHatasi("Lisans dosyası beklenenden çok büyük.")
    metin = metin.lstrip("﻿").strip()
    if not metin:
        raise LisansHatasi("Lisans dosyası boş.")
    if metin.startswith("{"):
        try:
            govde = json.loads(metin)
        except ValueError as exc:
            raise LisansHatasi(f"Lisans dosyası okunamadı (JSON bozuk: {exc.args[0] if exc.args else exc}).") \
                from None
        if not isinstance(govde, dict) or not isinstance(govde.get("lisans"), dict) \
                or not isinstance(govde.get("imza"), str):
            raise LisansHatasi("Lisans dosyasında 'lisans' ya da 'imza' alanı yok.")
        if govde.get("bicim", BICIM) != BICIM:
            raise LisansHatasi(f"Desteklenmeyen lisans biçimi: {str(govde.get('bicim'))[:40]}")
        kimlik = govde.get("anahtar_kimligi")
        return govde["lisans"], b64d(govde["imza"]), kimlik if isinstance(kimlik, str) else None
    tek = re.sub(r"\s+", "", metin)
    parcalar = tek.split(".")
    if len(parcalar) != 3 or parcalar[0] != ANAHTAR_ONEKI:
        raise LisansHatasi("Lisans tanınmadı: dosya '{' ile, lisans metni 'SAHA1.' ile başlamalı.")
    try:
        yuk = json.loads(b64d(parcalar[1]).decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise LisansHatasi("Lisans metninin içeriği okunamadı.") from None
    if not isinstance(yuk, dict):
        raise LisansHatasi("Lisans metninin içeriği okunamadı.")
    return yuk, b64d(parcalar[2]), None


def imza_dogrula(yuk: dict, imza: bytes, anahtarlar: list) -> str | None:
    """İmza tutuyorsa imzalayan anahtarın kimliği, tutmuyorsa ``None``."""
    InvalidSignature, _, _ = _kripto()
    if len(imza) != 64:
        return None
    try:
        veri = IMZA_ONEKI + kanonik(yuk)
    except LisansHatasi:
        return None
    for anahtar in anahtarlar:
        try:
            anahtar.verify(imza, veri)
            return anahtar_kimligi(anahtar)
        except InvalidSignature:
            continue
    return None


# ============================================================================= sonuç
_YUKLE = "Yeni lisans dosyasını Ayarlar › Lisans bölümünden yükleyin."
_SALT_ACIKLAMA = "veriler silinmez, görüntüleme ve dışa aktarma sürer, yalnız yeni kayıt yapılamaz"
_SALT_CUMLE = ("Sistem salt okunur: veriler yerinde duruyor, görüntüleme ve dışa aktarma çalışıyor; "
               "yeni kayıt yapılamıyor. Geçerli lisans yüklendiği anda her şey kaldığı yerden devam eder.")
_EKIP_SALT = ("Kayıtlar görüntülenebilir ama yeni kayıt yapılamıyor. Sahada işlediğiniz ziyaretler "
              "telefonunuzda bekler, lisans yenilenince kendiliğinden gönderilir. Yöneticinize haber verin.")
_SEVIYE_SIRA = {"yok": 0, "bilgi": 1, "uyari": 2, "kritik": 3}


@dataclass(frozen=True)
class Sonuc:
    """Bir lisans denetiminin sonucu. ``lisans`` yalnız imza tuttuysa doludur."""

    durum: str
    mod: str                                  # "tam" | "salt_okunur"
    seviye: str                               # "yok" | "bilgi" | "uyari" | "kritik"
    baslik: str                               # yönetici şeridi başlığı
    mesaj: str                                # yönetici şeridi metni (ne olacak + ne yapmalı)
    baslik_ekip: str | None                   # ekip şeridi (yalnız kritikte dolu)
    mesaj_ekip: str | None
    bugun: dt.date                            # hesapta kullanılan tarih
    cihaz_kimligi: str
    lisans: dict | None = None
    kalan_gun: int | None = None              # bitişe kalan gün: 0 = bugün son gün, eksi = geçti
    ek_sure_baslangic: dt.date | None = None
    ek_sure_son: dt.date | None = None        # tam çalışmanın son günü (sorun varsa)
    ayrinti: str = ""                         # teknik neden (günlük için; kişisel veri yok)
    anahtar_kimligi: str | None = None
    saat_uyarisi: bool = False

    # ---- türetilmiş
    @property
    def salt_okunur(self) -> bool:
        return self.mod == SALT_OKUNUR

    @property
    def ekibe_goster(self) -> bool:
        return self.seviye == "kritik"

    @property
    def ek_sure_kalan_gun(self) -> int | None:
        """Ek sürenin bitişine kalan gün: 0 = bugün son gün, eksi = salt okunur."""
        return (self.ek_sure_son - self.bugun).days if self.ek_sure_son else None

    @property
    def cihaz_izinli(self) -> bool | None:
        if not self.lisans:
            return None
        izinli = self.lisans.get("izinli_cihazlar") or []
        return (not izinli) or self.cihaz_kimligi in izinli

    def ozellik_acik(self, ad: str) -> bool:
        """Özellik bayrağı. Lisansta yazmıyorsa ``OZELLIKLER`` varsayılanı; bilinmeyen ek modül kapalı."""
        varsayilan = OZELLIKLER.get(ad, ("", False))[1]
        if not self.lisans:
            return varsayilan
        return bool(self.lisans.get("ozellikler", {}).get(ad, varsayilan))

    def kullanici_eklenebilir(self, aktif_sayi: int) -> bool:
        """Aktif kullanıcı sınırı (lisansta yoksa sınırsız). Var olan kişiler asla kapatılmaz."""
        sinir = (self.lisans or {}).get("kullanici_siniri")
        return sinir is None or aktif_sayi < sinir

    def sozluk(self, yonetici: bool = False) -> dict:
        """``GET /api/lisans`` gövdesi. Ekip görünümünde müşteri/bayi/lisans ayrıntısı YOKTUR."""
        if not yonetici:
            return {"durum": self.durum, "mod": self.mod,
                    "seviye": self.seviye if self.ekibe_goster else "yok",
                    "goster": self.ekibe_goster, "baslik": self.baslik_ekip, "mesaj": self.mesaj_ekip,
                    "ek_sure_son": self.ek_sure_son.isoformat() if self.ek_sure_son else None}
        lis = self.lisans
        ozellik_adlari = list(OZELLIKLER) + sorted(set((lis or {}).get("ozellikler", {})) - set(OZELLIKLER))
        return {
            "durum": self.durum, "mod": self.mod, "seviye": self.seviye,
            "goster": self.seviye != "yok", "ekibe_goster": self.ekibe_goster,
            "baslik": self.baslik, "mesaj": self.mesaj,
            "baslik_ekip": self.baslik_ekip, "mesaj_ekip": self.mesaj_ekip,
            "tarih": self.bugun.isoformat(),
            "kalan_gun": self.kalan_gun,
            "bitis": lis["bitis"] if lis else None,
            "bitis_metni": tarih_metni(tarih_coz(lis["bitis"])) if lis else None,
            "ek_sure_son": self.ek_sure_son.isoformat() if self.ek_sure_son else None,
            "ek_sure_son_metni": tarih_metni(self.ek_sure_son) if self.ek_sure_son else None,
            "ek_sure_kalan_gun": self.ek_sure_kalan_gun,
            "saat_uyarisi": self.saat_uyarisi,
            "ayrinti": self.ayrinti or None,
            "cihaz_kimligi": self.cihaz_kimligi,
            "cihaz_izinli": self.cihaz_izinli,
            "anahtar_kimligi": self.anahtar_kimligi,
            "lisans": None if not lis else {
                k: lis.get(k) for k in ("lisans_no", "musteri", "bayi_kodu", "baslangic", "bitis",
                                        "ek_sure_gun", "cihaz_siniri", "izinli_cihazlar",
                                        "kullanici_siniri", "duzenleme_tarihi", "onceki_lisans_no", "not")},
            "ozellikler": {ad: {"etiket": OZELLIKLER.get(ad, (ad, False))[0], "acik": self.ozellik_acik(ad)}
                           for ad in ozellik_adlari},
        }


def _ek_sure_cumlesi(ek_son: dt.date, bugun: dt.date) -> str:
    kalan = (ek_son - bugun).days
    if kalan <= 0:
        return f"Bugün ek sürenin son günü; yarından itibaren sistem salt okunur olur ({_SALT_ACIKLAMA})."
    return (f"{tarih_metni(ek_son)} tarihine kadar her şey çalışır ({kalan + 1} gün); sonra sistem "
            f"salt okunur olur ({_SALT_ACIKLAMA}).")


def _sonuc_kur(durum: str, bugun: dt.date, cihaz: str, *, yuk: dict | None = None,
               sorun_ilk: dt.date | None = None, ayrinti: str = "", kimlik: str | None = None) -> Sonuc:
    """Durumdan kipi, seviyeyi ve metinleri üretir (bütün kurallar tek yerde)."""
    bitis = tarih_coz(yuk["bitis"]) if yuk else None
    kalan = (bitis - bugun).days if bitis else None
    ek_gun = yuk.get("ek_sure_gun", VARSAYILAN_EK_SURE_GUN) if yuk else VARSAYILAN_EK_SURE_GUN
    ortak = dict(bugun=bugun, cihaz_kimligi=cihaz, lisans=yuk, kalan_gun=kalan, ayrinti=ayrinti,
                 anahtar_kimligi=kimlik)

    if durum == DENETLENMIYOR:
        return Sonuc(durum, TAM, "yok", "Lisans denetimi kapalı",
                     "Bu kurulumda lisans denetimi yapılandırılmamış; sistem süre sınırı olmadan çalışır.",
                     None, None, **ortak)
    if durum == GECERLI:
        return Sonuc(durum, TAM, "yok", "Lisans geçerli",
                     f"Lisans {tarih_metni(bitis)} tarihine kadar geçerli ({kalan} gün kaldı).",
                     None, None, **ortak)
    if durum == SURESI_YAKIN:
        seviye = "bilgi" if kalan > YAKIN_UYARI_GUN else "uyari"
        if kalan == 0:
            sonra = (f"Yarından itibaren {ek_gun} günlük ek süre başlar; bu sürede her şey çalışır."
                     if ek_gun else f"Yarından itibaren sistem salt okunur olur ({_SALT_ACIKLAMA}).")
            return Sonuc(durum, TAM, "uyari", "Lisansın son günü bugün",
                         f"Lisans bugün ({tarih_metni(bitis)}) bitiyor. {sonra} Kesinti olmaması için "
                         f"lisans sahibinden yenisini isteyin. {_YUKLE}", None, None, **ortak)
        return Sonuc(durum, TAM, seviye, f"Lisansın bitmesine {kalan} gün kaldı",
                     f"Lisans {tarih_metni(bitis)} tarihinde bitiyor. Kesinti olmaması için lisans "
                     f"sahibinden yenisini isteyin. {_YUKLE}", None, None, **ortak)

    # ---- sorunlu durumlar: ek süre + salt okunur
    if durum == SURESI_DOLDU:
        ek_bas = bitis + dt.timedelta(days=1)
        if sorun_ilk:
            ek_bas = min(ek_bas, sorun_ilk)
    else:
        ek_bas = sorun_ilk or bugun
    ek_son = ek_bas + dt.timedelta(days=ek_gun - 1)
    ek_kalan = (ek_son - bugun).days
    mod = TAM if ek_kalan >= 0 else SALT_OKUNUR
    seviye = "kritik" if (mod == SALT_OKUNUR or ek_kalan < KRITIK_GUN) else "uyari"
    ek = _ek_sure_cumlesi(ek_son, bugun) if mod == TAM else ""
    kimlik_cumle = f"Bu bilgisayarın kimliği: {cihaz}."

    if durum == SURESI_DOLDU:
        baslik = ("Lisansın süresi doldu · ek süre" if mod == TAM
                  else "Sistem salt okunur · lisansın süresi doldu")
        mesaj = (f"Lisans {tarih_metni(bitis)} tarihinde bitti. {ek} {_YUKLE}" if mod == TAM
                 else f"Lisans {tarih_metni(bitis)} tarihinde bitti ve ek süre de doldu. {_SALT_CUMLE} {_YUKLE}")
    elif durum == IMZA_BOZUK:
        baslik = "Lisans dosyası doğrulanamadı" if mod == TAM else "Sistem salt okunur · lisans doğrulanamadı"
        mesaj = (f"Yüklü lisans doğrulanamadı: dosya bozulmuş ya da değiştirilmiş olabilir. {ek} "
                 f"Lisans sahibinden dosyanın aslını isteyin. {_YUKLE}" if mod == TAM
                 else f"Yüklü lisans doğrulanamadı ve ek süre doldu. {_SALT_CUMLE} {_YUKLE}")
    elif durum == CIHAZ_DISI:
        baslik = ("Lisans bu bilgisayar için verilmemiş" if mod == TAM
                  else "Sistem salt okunur · lisans bu bilgisayar için değil")
        mesaj = (f"Yüklü lisans başka bir bilgisayara bağlı. {kimlik_cumle} Bilgisayar değiştiyse bu "
                 f"kimliği lisans sahibine iletin. {ek}" if mod == TAM
                 else f"Yüklü lisans başka bir bilgisayara bağlı ve ek süre doldu. {kimlik_cumle} {_SALT_CUMLE}")
    elif durum == LISANS_YOK:
        baslik = "Lisans yüklenmemiş" if mod == TAM else "Sistem salt okunur · lisans yok"
        mesaj = (f"Bu kurulumda lisans dosyası yok. {ek} {_YUKLE} {kimlik_cumle}" if mod == TAM
                 else f"Lisans dosyası yüklenmedi ve ek süre doldu. {_SALT_CUMLE} {_YUKLE} {kimlik_cumle}")
    elif durum == HENUZ_BASLAMADI:
        bas = tarih_metni(tarih_coz(yuk["baslangic"]))
        baslik = "Lisans henüz başlamadı" if mod == TAM else "Sistem salt okunur · lisans henüz başlamadı"
        mesaj = (f"Yüklü lisans {bas} tarihinde başlıyor. {ek} Tarih yanlışsa lisans sahibine başvurun."
                 if mod == TAM else f"Yüklü lisans {bas} tarihinde başlıyor ve ek süre doldu. {_SALT_CUMLE}")
    else:  # pragma: no cover - programlama hatası
        raise ValueError(durum)

    if seviye != "kritik":
        baslik_ekip = mesaj_ekip = None
    elif mod == SALT_OKUNUR:
        baslik_ekip, mesaj_ekip = "Sistem salt okunur", _EKIP_SALT
    else:
        ne_zaman = "yarından itibaren" if ek_kalan == 0 else f"{tarih_metni(ek_son)} tarihinden sonra"
        baslik_ekip = "Lisans güncellenmeli"
        mesaj_ekip = f"Sistemin lisansı güncellenmeli: {ne_zaman} yeni kayıt yapılamayacak. Yöneticinize haber verin."
    return Sonuc(durum, mod, seviye, baslik, re.sub(r"\s+", " ", mesaj).strip(), baslik_ekip, mesaj_ekip,
                 ek_sure_baslangic=ek_bas, ek_sure_son=ek_son, **ortak)


# ============================================================================= doğrulama
def dogrula_metin(metin: str | None, genel_anahtar: Any = None, *, cihaz: str | None = None,
                  bugun: dt.date | None = None, sorun_ilk: dt.date | None = None) -> Sonuc:
    """Lisans metnini (dosya içeriği ya da ``SAHA1.`` metni) doğrular. ``metin=None`` → lisans yok.

    ``sorun_ilk``: sorunun ilk görüldüğü gün (``Denetci`` tutar); verilmezse ek süre bugünden sayılır.
    Süresi dolan lisansta ek süre bitişin ertesi gününden sayılır (sorun_ilk daha erkense o gün).
    """
    bugun = bugun or turkiye_bugun()
    if cihaz is None:
        cihaz = cihaz_kimligi()
    else:
        normal = cihaz_normalle(cihaz)
        if normal is None:
            raise ValueError(f"cihaz kimliği XXXX-XXXX-XXXX-XXXX-XXXX biçiminde olmalı: {cihaz!r}")
        cihaz = normal

    def kur(durum, **ek):
        return _sonuc_kur(durum, bugun, cihaz, sorun_ilk=sorun_ilk, **ek)

    try:
        anahtarlar = genel_anahtarlari_yukle(genel_anahtar)
    except LisansHatasi as exc:
        return kur(IMZA_BOZUK, ayrinti=exc.mesaj)
    if not anahtarlar:
        return kur(DENETLENMIYOR)
    if metin is None:
        return kur(LISANS_YOK)
    try:
        yuk, imza, _ = coz(metin)
    except LisansHatasi as exc:
        return kur(IMZA_BOZUK, ayrinti=exc.mesaj)
    kimlik = imza_dogrula(yuk, imza, anahtarlar)
    if kimlik is None:
        return kur(IMZA_BOZUK, ayrinti="İmza tutmuyor: dosya değiştirilmiş ya da başka bir anahtarla imzalanmış.")
    hatalar = yuk_denetle(yuk)
    if hatalar:
        return kur(IMZA_BOZUK, ayrinti="İmzalı içerik geçersiz: " + "; ".join(hatalar[:3]))
    yuk = _normalle(yuk)
    izinli = yuk["izinli_cihazlar"]
    if izinli and cihaz not in izinli:
        return kur(CIHAZ_DISI, yuk=yuk, kimlik=kimlik, ayrinti="Bu bilgisayarın kimliği lisansın cihaz listesinde yok.")
    if bugun < tarih_coz(yuk["baslangic"]):
        return kur(HENUZ_BASLAMADI, yuk=yuk, kimlik=kimlik)
    kalan = (tarih_coz(yuk["bitis"]) - bugun).days
    if kalan < 0:
        return kur(SURESI_DOLDU, yuk=yuk, kimlik=kimlik)
    return kur(SURESI_YAKIN if kalan <= UYARI_GUN else GECERLI, yuk=yuk, kimlik=kimlik)


def dogrula(dosya: str | os.PathLike, genel_anahtar: Any = None, *, cihaz: str | None = None,
            bugun: dt.date | None = None, sorun_ilk: dt.date | None = None) -> Sonuc:
    """Lisans dosyasını doğrular. Dosya yoksa ``lisans_yok``; genel anahtar yoksa ``denetlenmiyor``.

    Dönen ``Sonuc.durum``: gecerli · suresi_yakin · suresi_doldu · imza_bozuk · cihaz_disi ·
    lisans_yok · henuz_baslamadi · denetlenmiyor; ``kalan_gun`` bitişe kalan gün.
    """
    yol = Path(dosya)
    metin: str | None
    ayrinti = ""
    try:
        metin = yol.read_bytes().decode("utf-8") if yol.is_file() else None
    except (OSError, UnicodeDecodeError) as exc:
        metin, ayrinti = "", f"Lisans dosyası okunamadı ({type(exc).__name__})."
    sonuc = dogrula_metin(metin, genel_anahtar, cihaz=cihaz, bugun=bugun, sorun_ilk=sorun_ilk)
    if ayrinti and sonuc.durum == IMZA_BOZUK:
        sonuc = dataclasses.replace(sonuc, ayrinti=ayrinti)
    return sonuc


# ============================================================================= salt okunur kapısı
# Salt okunur kipte YAZMA isteklerinden yalnız bunlar geçer (varsayılan YASAK, yetki.py gibi).
# Okuma (GET/HEAD/OPTIONS) her zaman serbesttir: görüntüleme ve dışa aktarma hiç durmaz.
SALT_OKUNUR_SERBEST: tuple[tuple[str, str, str], ...] = (
    ("POST", r"/api/giris", "giriş: oturum açılmadan veri görülemez"),
    ("POST", r"/api/pin", "ilk PIN: var olan kişi verisini görebilsin"),
    ("POST", r"/api/lisans", "yeni lisans yükleme: salt okunurdan çıkmanın yolu"),
    ("POST", r"/api/kullanici/\d+/cihaz-cikis", "kayıp telefonun oturumunu kapatma (güvenlik)"),
    ("POST", r"/api/isler/[^/]+/kopya", "müşteri bilgisini kopyalama: okuma + erişim kaydı"),
)
_SERBEST = tuple((y, re.compile(d)) for y, d, _ in SALT_OKUNUR_SERBEST)
OKUMA_YONTEMLERI = frozenset({"GET", "HEAD", "OPTIONS"})


def yazma_serbest_mi(yontem: str, yol: str) -> bool:
    """Salt okunur kipte bu istek geçebilir mi? Okuma her zaman; yazma yalnız izin listesindeyse."""
    y = (yontem or "").upper()
    if y in OKUMA_YONTEMLERI:
        return True
    return any(y == izinli and desen.fullmatch(yol or "") for izinli, desen in _SERBEST)


def salt_okunur_yaniti(sonuc: Sonuc) -> tuple[int, dict, dict]:
    """Engellenen yazma isteğinin yanıtı: (HTTP 503, gövde, başlıklar).

    503 BİLİNÇLİ: saha uygulaması 5xx'i "sunucu şu an yazamıyor" sayar ve ziyareti kuyrukta tutup
    sonra yeniden dener (kod/arayuz/src/api/istemci.ts ``agHatasi``). 4xx dönülürse kayıt "reddedildi"
    işaretlenir — lisans yüzünden sahadaki bir ziyaret kaybolmamalı.
    """
    govde = {"hata": "Sistem şu an yalnız okuma modunda (lisans güncellenmeli); bu kayıt yazılmadı. "
                     "Sahadan gönderilen ziyaretler telefonda bekler, lisans yenilenince kendiliğinden gönderilir.",
             "kod": "salt_okunur",
             "lisans": {"durum": sonuc.durum, "mod": sonuc.mod}}
    return 503, govde, {"Retry-After": "3600"}


# ============================================================================= denetçi (durumlu)
class Denetci:
    """Sunucunun lisans denetçisi: önbellek + ek süre sayacı + saat geri alma koruması + yükleme.

    Durum dosyası (``lisans_durum.json``) iki şey tutar:
      * ``sorun_ilk``: sorunlu bir durumun İLK görüldüğü gün. Sorunsuz duruma dönünce silinir;
        sorun türü değişse bile (lisans yok → bozuk dosya) sıfırlanmaz: ek süre uzatılamaz.
      * ``son_tarih``: görülen en ileri tarih. Bilgisayarın tarihi bundan geri alınırsa lisans
        hesabı ``son_tarih`` ile yapılır ve yöneticiye açıkça söylenir. 400 günden büyük ileri
        sıçramalar yazılmaz (yanlış BIOS saati kurulumu kalıcı olarak kilitlemesin).
    Durum dosyası silinirse ikisi de sıfırlanır (destek işlemi; belgeler/LISANS.md §9).
    """

    def __init__(self, lisans_yolu: str | os.PathLike, durum_yolu: str | os.PathLike | None = None,
                 genel_anahtar: Any = None, *, cihaz: str | None = None,
                 bugun: Callable[[], dt.date] | None = None, yedek_dizini: str | os.PathLike | None = None,
                 onbellek_sn: float = ONBELLEK_SN):
        self.lisans_yolu = Path(lisans_yolu)
        self.durum_yolu = Path(durum_yolu) if durum_yolu else \
            self.lisans_yolu.with_name(self.lisans_yolu.stem + "_durum.json")
        self.yedek_dizini = Path(yedek_dizini) if yedek_dizini else self.lisans_yolu.parent / "yedek"
        self.genel_anahtar = genel_anahtar
        self._cihaz = cihaz
        self._bugun = bugun or turkiye_bugun
        self._onbellek_sn = onbellek_sn
        self._kilit = threading.RLock()
        self._sonuc: Sonuc | None = None
        self._iz: tuple | None = None
        self._zaman = 0.0

    # ---- dışa açık
    def sonuc(self, zorla: bool = False) -> Sonuc:
        """Güncel sonuç. Dosya, genel anahtar ya da tarih değişince ya da 10 dakikada bir yeniden hesaplar."""
        with self._kilit:
            iz = (self._dosya_izi(self.lisans_yolu), self._dosya_izi(self._anahtar_yolu()), self._bugun())
            if (not zorla and self._sonuc is not None and iz == self._iz
                    and time.monotonic() - self._zaman < self._onbellek_sn):
                return self._sonuc
            self._sonuc, self._iz, self._zaman = self._hesapla(), iz, time.monotonic()
            return self._sonuc

    def yukle(self, metin: str) -> Sonuc:
        """Yeni lisansı doğrular ve GÜVENLE kurar (eskisi yedeklenir, yazma atomik).

        Reddedilir (``LisansHatasi``, kod API yanıtına gider): imza bozuk · başka bilgisayar ·
        henüz başlamamış · süresi dolmuş · yüklü lisanstan daha kısa süreli.
        """
        with self._kilit:
            etkin, _ = self._etkin_tarih(self._durum_oku())
            yeni = dogrula_metin(metin, self.genel_anahtar, cihaz=self._cihaz, bugun=etkin)
            if yeni.durum == DENETLENMIYOR:
                raise LisansHatasi("Bu kurulumda lisans denetimi kapalı; yüklenecek bir şey yok.", "denetim_kapali")
            if yeni.durum == IMZA_BOZUK:
                raise LisansHatasi(f"Lisans doğrulanamadı. {yeni.ayrinti} Lisans sahibinden dosyanın aslını "
                                   "isteyin.", "imza_bozuk")
            if yeni.durum == CIHAZ_DISI:
                raise LisansHatasi(f"Bu lisans başka bir bilgisayar için verilmiş. Bu bilgisayarın kimliği: "
                                   f"{yeni.cihaz_kimligi}. Lisans sahibine bu kimliği iletin.", "cihaz_disi")
            if yeni.durum == HENUZ_BASLAMADI:
                raise LisansHatasi(f"Bu lisans {tarih_metni(tarih_coz(yeni.lisans['baslangic']))} tarihinde "
                                   "başlıyor; o gün ya da sonra yükleyin.", "henuz_baslamadi")
            if yeni.durum == SURESI_DOLDU:
                raise LisansHatasi(f"Bu lisansın süresi {tarih_metni(tarih_coz(yeni.lisans['bitis']))} tarihinde "
                                   "dolmuş. Lisans sahibinden güncel lisansı isteyin.", "suresi_doldu")
            simdiki = self.sonuc(zorla=True)
            if (simdiki.durum in (GECERLI, SURESI_YAKIN) and simdiki.lisans
                    and simdiki.lisans["bitis"] > yeni.lisans["bitis"]):
                raise LisansHatasi(f"Yüklü lisans ({tarih_metni(tarih_coz(simdiki.lisans['bitis']))} tarihine kadar) "
                                   "bu dosyadan daha uzun süreli; değiştirilmedi.", "daha_kisa")
            yuk, imza, _ = coz(metin)
            icerik = dosya_metni(yuk, imza, yeni.anahtar_kimligi)
            try:
                if self.lisans_yolu.is_file():
                    self.yedek_dizini.mkdir(parents=True, exist_ok=True)
                    damga = dt.datetime.now(TR).strftime("%Y%m%d-%H%M%S")
                    (self.yedek_dizini / f"lisans-{damga}.json").write_bytes(self.lisans_yolu.read_bytes())
                _atomik_yaz(self.lisans_yolu, icerik)
            except OSError as exc:
                raise LisansHatasi(f"Lisans doğru ama diske yazılamadı ({type(exc).__name__}). Disk dolu ya da "
                                   "klasör salt okunur olabilir; BT'ye haber verin.", "yazilamadi") from None
            return self.sonuc(zorla=True)

    # ---- iç
    def _anahtar_yolu(self) -> Path | None:
        if self.genel_anahtar is None:
            return VARSAYILAN_GENEL_ANAHTAR
        if isinstance(self.genel_anahtar, (str, os.PathLike)) and "-----BEGIN" not in str(self.genel_anahtar):
            return Path(self.genel_anahtar)
        return None

    @staticmethod
    def _dosya_izi(yol: Path | None) -> tuple:
        if yol is None:
            return ()
        try:
            st = yol.stat()
            return (st.st_mtime_ns, st.st_size)
        except OSError:
            return (None,)

    def _durum_oku(self) -> dict:
        try:
            veri = json.loads(self.durum_yolu.read_text(encoding="utf-8"))
            return veri if isinstance(veri, dict) else {}
        except (OSError, ValueError):
            return {}

    def _etkin_tarih(self, durum: dict) -> tuple[dt.date, bool]:
        sistem = self._bugun()
        try:
            son = tarih_coz(durum.get("son_tarih"))
        except ValueError:
            return sistem, False
        if sistem < son - dt.timedelta(days=1):
            return son, True
        return sistem, False

    def _hesapla(self) -> Sonuc:
        durum = self._durum_oku()
        sistem = self._bugun()
        etkin, saat_geri = self._etkin_tarih(durum)
        try:
            sorun_ilk = tarih_coz(durum.get("sorun_ilk"))
        except ValueError:
            sorun_ilk = None
        s = dogrula(self.lisans_yolu, self.genel_anahtar, cihaz=self._cihaz, bugun=etkin, sorun_ilk=sorun_ilk)

        yeni = dict(durum)
        yeni["surum"] = 1
        try:
            son = tarih_coz(durum.get("son_tarih"))
            if son < sistem and (sistem - son).days <= SAAT_SICRAMA_SINIRI_GUN:
                yeni["son_tarih"] = sistem.isoformat()
        except ValueError:
            yeni["son_tarih"] = sistem.isoformat()
        if s.durum in SORUNSUZ:
            yeni["sorun_ilk"] = None
        elif sorun_ilk is None and s.ek_sure_baslangic is not None:
            yeni["sorun_ilk"] = s.ek_sure_baslangic.isoformat()
        if yeni != durum:
            try:
                _atomik_yaz(self.durum_yolu, json.dumps(yeni, ensure_ascii=False, indent=2) + "\n")
            except OSError:
                pass  # yazılamazsa denetim yine çalışır; yalnız ek süre sayacı kalıcı olmaz

        if saat_geri:
            ek = (f"Bilgisayarın tarihi geri alınmış görünüyor: lisans hesabında en son görülen tarih "
                  f"({tarih_metni(etkin)}) kullanılıyor. Saat yanlışsa düzeltin.")
            s = dataclasses.replace(
                s, saat_uyarisi=True, mesaj=f"{s.mesaj} {ek}",
                seviye=s.seviye if _SEVIYE_SIRA[s.seviye] >= _SEVIYE_SIRA["uyari"] else "uyari",
                baslik=s.baslik if s.seviye != "yok" else "Bilgisayarın tarihi geri alınmış")
        return s


def _atomik_yaz(yol: Path, icerik: str) -> None:
    """Geçici dosyaya yazar, diske işler, sonra tek hamlede yerine koyar (yarım dosya kalmaz)."""
    yol.parent.mkdir(parents=True, exist_ok=True)
    fd, gecici = tempfile.mkstemp(dir=yol.parent, prefix=f".{yol.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(icerik)
            f.flush()
            os.fsync(f.fileno())
        os.replace(gecici, yol)
    except BaseException:
        try:
            os.unlink(gecici)
        except OSError:
            pass
        raise


# ============================================================================= komut satırı
def _konsol():
    for akis in (sys.stdout, sys.stderr):
        try:
            akis.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError, ValueError):
            pass


def main(argv: list[str] | None = None) -> int:
    _konsol()
    ayrac = argparse.ArgumentParser(prog="python -m lisans.lisans", description="Saha Sistemi lisans denetimi")
    alt = ayrac.add_subparsers(dest="komut", required=True)
    alt.add_parser("cihaz", help="bu bilgisayarın cihaz kimliği (lisans sahibine iletilir)")
    d = alt.add_parser("denetle", help="bir lisans dosyasının durumu")
    d.add_argument("dosya", nargs="?", default="saha/lisans.json")
    d.add_argument("--anahtar", help="genel anahtar PEM (varsayılan lisans/genel_anahtar.pem)")
    a = ayrac.parse_args(argv)
    if a.komut == "cihaz":
        bilgi = cihaz_bilgisi()
        print(f"Cihaz kimliği: {bilgi['kimlik']}   (kaynak: {bilgi['kaynak']})")
        return 0
    s = dogrula(a.dosya, a.anahtar)
    print(f"Durum : {s.durum}   Kip: {s.mod}   Seviye: {s.seviye}")
    print(f"Başlık: {s.baslik}")
    print(f"Mesaj : {s.mesaj}")
    if s.lisans:
        print(f"Lisans: {s.lisans['lisans_no']} · {s.lisans['baslangic']} → {s.lisans['bitis']} · "
              f"kalan {s.kalan_gun} gün")
    if s.ayrinti:
        print(f"Ayrıntı: {s.ayrinti}")
    return 0 if s.mod == TAM else 1


if __name__ == "__main__":
    sys.exit(main())
