"""Kimlik doğrulama: PIN özeti, oturum jetonu, hatalı giriş kilidi.

PIN hiçbir yerde açık saklanmaz (stdlib ``hashlib.scrypt``). Jeton imzası için
gereken gizli anahtar ilk çalıştırmada ``saha/gizli.key`` dosyasına üretilir;
dosya sürüm kontrolüne girmez.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import stat
import subprocess

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from . import ayarlar

# scrypt parametreleri: 16 MiB bellek, ~50 ms — telefondan giriş için fazlasıyla hızlı,
# kaba kuvvet için fazlasıyla yavaş.
_N, _R, _P, _DK = 2 ** 14, 8, 1, 32

_TELEFON = re.compile(r"\D+")


# ----------------------------------------------------------------------------- telefon
def telefon_duzelt(ham: str) -> str | None:
    """'0 532 111 22 33', '+90532...', '532...' → '5321112233'. Geçersizse None."""
    if not ham:
        return None
    s = _TELEFON.sub("", str(ham))
    if s.startswith("0090"):
        s = s[4:]
    if s.startswith("90") and len(s) == 12:
        s = s[2:]
    if s.startswith("0") and len(s) == 11:
        s = s[1:]
    if len(s) == 10 and s.startswith("5"):
        return s
    return None


def telefon_goster(telefon: str | None) -> str:
    """5321112233 → 0532 111 22 33 · telefonu olmayan (girişsiz) kişi → "—"."""
    if not telefon:
        return "—"
    if len(telefon) == 10:
        return f"0{telefon[:3]} {telefon[3:6]} {telefon[6:8]} {telefon[8:]}"
    return telefon


def telefon_maskeli(telefon: str | None) -> str:
    """Listelerde: 5321112233 → 0532 ••• •• 33 (tam hâli yalnız tek kişi yanıtında)."""
    if not telefon:
        return "—"
    if len(telefon) == 10:
        return f"0{telefon[:3]} ••• •• {telefon[8:]}"
    return "•" * max(0, len(telefon) - 2) + telefon[-2:]


# ----------------------------------------------------------------------------- PIN
def pin_gecerli_mi(pin: str) -> bool:
    return bool(pin) and len(pin) == ayarlar.PIN_UZUNLUK and pin.isdigit()


def pin_zayif_mi(pin: str) -> bool:
    """0000, 1111, 1234, 4321 gibi tahmin edilmesi kolay PIN'ler."""
    if len(set(pin)) == 1:
        return True
    rakamlar = [int(x) for x in pin]
    artan = all(b - a == 1 for a, b in zip(rakamlar, rakamlar[1:]))
    azalan = all(a - b == 1 for a, b in zip(rakamlar, rakamlar[1:]))
    return artan or azalan


def pin_hashle(pin: str) -> str:
    tuz = secrets.token_bytes(16)
    ozet = hashlib.scrypt(pin.encode("utf-8"), salt=tuz, n=_N, r=_R, p=_P, dklen=_DK)
    return f"scrypt${_N}${_R}${_P}${tuz.hex()}${ozet.hex()}"


def pin_dogrula(pin: str, saklanan: str | None) -> bool:
    if not saklanan or not pin:
        return False
    try:
        tur, n, r, p, tuz_hex, ozet_hex = saklanan.split("$")
        if tur != "scrypt":
            return False
        ozet = hashlib.scrypt(
            pin.encode("utf-8"), salt=bytes.fromhex(tuz_hex),
            n=int(n), r=int(r), p=int(p), dklen=len(ozet_hex) // 2,
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(ozet.hex(), ozet_hex)


def davet_kodu_uret() -> str:
    """Yöneticinin satışçıya sözlü olarak vereceği 6 haneli kod."""
    return f"{secrets.randbelow(1_000_000):06d}"


# ----------------------------------------------------------------------------- gizli anahtar
def gizli_anahtar() -> str:
    """Jeton imzalama anahtarı; yoksa üretilip ``saha/gizli.key`` dosyasına yazılır."""
    ortam = os.environ.get("SAHA_GIZLI")
    if ortam:
        return ortam
    yol = ayarlar.GIZLI_ANAHTAR
    if yol.exists():
        mevcut = yol.read_text(encoding="utf-8").strip()
        if mevcut:
            return mevcut
    yeni = secrets.token_urlsafe(48)
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text(yeni + "\n", encoding="utf-8")
    _sadece_sahibi(yol)
    return yeni


def _sadece_sahibi(yol) -> None:
    """Dosyayı yalnız bu kullanıcıya açar.

    ``chmod`` Windows'ta etkisizdir; orada NTFS izinleri ``icacls`` ile
    daraltılır. Bu anahtarı okuyabilen herkes YÖNETİCİ jetonu üretebilir.
    """
    try:
        yol.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass
    if os.name != "nt":
        return
    kullanici = os.environ.get("USERNAME")
    if not kullanici:
        return
    try:
        subprocess.run(
            ["icacls", str(yol), "/inheritance:r", "/grant:r", f"{kullanici}:F"],
            check=False, capture_output=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        pass


def _imzalayici() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(gizli_anahtar(), salt="saha-oturum-v1")


# ----------------------------------------------------------------------------- jeton
def jeton_uret(kullanici: sqlite3.Row | dict) -> str:
    k = dict(kullanici)
    return _imzalayici().dumps(
        {"kid": k["id"], "rol": k["rol"], "bolge": k.get("bolge"), "otr": k.get("oturum_no", 1)}
    )


def jeton_coz(jeton: str) -> dict | None:
    """Geçerliyse yükü, süresi dolmuş veya imzası bozuksa None döndürür."""
    try:
        return _imzalayici().loads(jeton, max_age=ayarlar.TOKEN_GUN * 86400)
    except (SignatureExpired, BadSignature, TypeError, ValueError):
        return None


# ----------------------------------------------------------------------------- kaba kuvvet
# Eski davranış: telefon başına 15 dakikada 5 hatalı denemeden sonra SERT KİLİT.
# Sorun: ağdaki herhangi biri bir satışçının numarasına 5 yanlış PIN yollayıp
# onu gün boyu sahada dışarıda bırakabiliyordu — doğru PIN de reddediliyordu.
#
# Yeni davranış:
#   · doğru PIN HER ZAMAN kabul edilir (meşru satışçı sahada kilitli kalmaz),
#   · yanlış PIN yavaşlatılır (üstel değil, doğrusal: 0,5 sn → 3 sn),
#   · asıl duvar IP başınadır: 15 dakikada 30 hatalı deneme sonrası 429.
# scrypt'in 50 ms'i + bu gecikme ile 10.000 PIN denemek tek IP'den imkânsızdır.


def _pencere_basi(an: dt.datetime | None = None) -> str:
    an = an or ayarlar.simdi()
    return (an - dt.timedelta(minutes=ayarlar.KILIT_DAKIKA)).isoformat(sep=" ", timespec="seconds")


def hatali_sayisi(conn: sqlite3.Connection, telefon: str, simdi: dt.datetime | None = None) -> int:
    """Son 15 dakikada bu numaraya yapılan hatalı deneme sayısı."""
    return conn.execute(
        "SELECT COUNT(*) FROM giris_denemesi "
        "WHERE telefon=? AND basarili=0 AND tur='giris' AND zaman>?",
        (telefon, _pencere_basi(simdi)),
    ).fetchone()[0]


def gecikme_saniye(hatali: int) -> float:
    """Yanlış PIN'e verilecek cezalı bekleme (saniye)."""
    if hatali < ayarlar.YAVASLATMA_ESIGI:
        return 0.0
    adim = (hatali - ayarlar.YAVASLATMA_ESIGI + 1) * ayarlar.YAVASLATMA_ADIM_SN
    return min(ayarlar.YAVASLATMA_EN_COK_SN, adim)


def ip_asildi_mi(
    conn: sqlite3.Connection,
    ip: str | None,
    tur: str = "giris",
    simdi: dt.datetime | None = None,
) -> int:
    """IP sınırı aşıldıysa kalan saniye, aşılmadıysa 0."""
    if not ip:
        return 0
    sinir = ayarlar.IP_DENEME if tur == "giris" else ayarlar.IP_YOKLAMA
    satirlar = conn.execute(
        "SELECT zaman FROM giris_denemesi "
        "WHERE ip=? AND basarili=0 AND tur=? AND zaman>? ORDER BY zaman DESC LIMIT ?",
        (ip, tur, _pencere_basi(simdi), sinir),
    ).fetchall()
    if len(satirlar) < sinir:
        return 0
    an = simdi or ayarlar.simdi()
    en_eski = dt.datetime.fromisoformat(satirlar[-1]["zaman"])
    return max(0, int((en_eski + dt.timedelta(minutes=ayarlar.KILIT_DAKIKA) - an).total_seconds()))


def deneme_yaz(
    conn: sqlite3.Connection,
    telefon: str,
    basarili: bool,
    ip: str | None = None,
    tur: str = "giris",
) -> None:
    conn.execute(
        "INSERT INTO giris_denemesi(telefon, zaman, basarili, ip, tur) VALUES(?,?,?,?,?)",
        (telefon, ayarlar.zaman_metni(), 1 if basarili else 0, ip, tur),
    )
    if basarili:  # başarılı girişten sonra o numaranın sayacı sıfırlanır
        conn.execute(
            "DELETE FROM giris_denemesi WHERE telefon=? AND basarili=0 AND tur='giris'", (telefon,)
        )
    # eski kayıtlar birikmesin
    sinir = (ayarlar.simdi() - dt.timedelta(days=7)).isoformat(sep=" ", timespec="seconds")
    conn.execute("DELETE FROM giris_denemesi WHERE zaman<?", (sinir,))
