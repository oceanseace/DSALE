"""Lisans sahibinin aracı: anahtar çifti · lisans ver · yenile · yenilemeyi durdur · liste · göster.

Bu dosya UYGULAMAYLA GİTMEZ. Özel anahtar yalnız "kasa" klasöründe durur ve hiçbir zaman depoya ya
da uygulamaya girmez. Kasa: ``--kasa`` > ``SAHA_LISANS_KASA`` > ``%USERPROFILE%\\.saha-lisans``.

    .venv\\Scripts\\python.exe -m lisans.uret anahtar-olustur                 (bir kez)
    .venv\\Scripts\\python.exe -m lisans.uret ver --musteri "ÖRNEK BAYİ" --bayi-kodu 00000.00000 --ay 12 \\
                                                --cihaz XXXX-XXXX-XXXX-XXXX-XXXX
    .venv\\Scripts\\python.exe -m lisans.uret yenile SL-2026-ABC123 --ay 12
    .venv\\Scripts\\python.exe -m lisans.uret durdur SL-2026-ABC123            (yenilenmeyecek)
    .venv\\Scripts\\python.exe -m lisans.uret liste
    .venv\\Scripts\\python.exe -m lisans.uret goster lisans.json

Uzaktan kapatma YOKTUR: verilmiş bir lisans bitiş tarihine kadar geçerlidir. "Durdurmak" =
yenilememek; o zaman müşterinin sistemi bitişten sonra 14 gün ek süreyle çalışır, ardından salt
okunur olur (veri silinmez, dışa aktarma sürer). Ayrıntı: belgeler/LISANS.md.

Kasa parolası: etkileşimli pencerede sorulur; otomasyon için ``SAHA_LISANS_PAROLA`` ortam değişkeni.
"""
from __future__ import annotations

import argparse
import calendar
import datetime as dt
import getpass
import json
import os
import secrets
import sys
from pathlib import Path

if __package__ in (None, ""):  # "python kod\lisans\uret.py" ile çalıştırıldıysa: kod/ içe aktarma yoluna
    sys.path[0] = str(Path(__file__).resolve().parent.parent)

from lisans import lisans as L  # noqa: E402

OZEL_ADI = "ozel_anahtar.pem"
GENEL_ADI = "genel_anahtar.pem"
KAYIT_ADI = "verilenler.jsonl"
LISANS_DIZINI = "lisanslar"
DEPO_GENEL_ANAHTAR = L.VARSAYILAN_GENEL_ANAHTAR

_OKUBENI = """SAHA SİSTEMİ — LİSANS KASASI
============================
Bu klasör lisans sahibinindir. İçindekiler:
  ozel_anahtar.pem   İMZA ANAHTARI. Kimseyle paylaşmayın, depoya/uygulamaya koymayın, e-postayla
                     göndermeyin. Kaybolursa yeni lisans verilemez (yeni anahtar + uygulama güncellemesi
                     gerekir); ele geçirilirse herkes lisans üretebilir.
  genel_anahtar.pem  Doğrulama anahtarı. Uygulamaya bu gider (lisans/genel_anahtar.pem). Paylaşılabilir.
  verilenler.jsonl   Verilen lisansların defteri (yalnız eklenir).
  lisanslar/         Verilen lisans dosyalarının kopyaları.

YEDEK: Bu klasörü şifreli bir USB belleğe ya da güvenli bir yere düzenli yedekleyin.
"""


class Hata(SystemExit):
    """Kullanıcıya düz Türkçe cümle, çıkış kodu 2."""

    def __init__(self, mesaj: str):
        print(f"HATA: {mesaj}", file=sys.stderr, flush=True)
        super().__init__(2)


# ============================================================================= yardımcılar
def kasa_yolu(arg: str | None = None) -> Path:
    return Path(arg or os.environ.get("SAHA_LISANS_KASA") or (Path.home() / ".saha-lisans"))


def ay_ekle(gun: dt.date, ay: int) -> dt.date:
    """Takvim ayı ekler; ayın son gününü aşarsa son güne çeker (31 Ocak + 1 ay = 28/29 Şubat)."""
    yil, ay0 = divmod(gun.month - 1 + ay, 12)
    yil += gun.year
    return dt.date(yil, ay0 + 1, min(gun.day, calendar.monthrange(yil, ay0 + 1)[1]))


def sure_sonu(baslangic: dt.date, *, ay: int | None = None, gun: int | None = None) -> dt.date:
    """"12 ay" → 1 Ekim 2026'dan 30 Eylül 2027'ye (bitiş günü dahil)."""
    if ay:
        return ay_ekle(baslangic, ay) - dt.timedelta(days=1)
    return baslangic + dt.timedelta(days=gun - 1)


def _tarih(metin: str, ad: str) -> dt.date:
    try:
        return L.tarih_coz(metin)
    except ValueError:
        raise Hata(f"{ad} YYYY-AA-GG biçiminde olmalı (ör. 2026-10-01): {metin!r}") from None


def _cihazlar(liste) -> list[str]:
    cikti = []
    for ham in liste or ():
        normal = L.cihaz_normalle(ham)
        if normal is None:
            raise Hata(f"Cihaz kimliği XXXX-XXXX-XXXX-XXXX-XXXX biçiminde olmalı: {ham!r}")
        if normal not in cikti:
            cikti.append(normal)
    return cikti


def _ozellikler(temel: dict[str, bool], degisiklikler) -> dict[str, bool]:
    sonuc = dict(temel)
    for ham in degisiklikler or ():
        ad, _, deger = ham.partition("=")
        deger = deger.strip().lower()
        if deger not in ("evet", "hayir", "hayır", "acik", "açık", "kapali", "kapalı", "true", "false", "1", "0"):
            raise Hata(f"--ozellik ad=evet|hayir biçiminde olmalı: {ham!r}")
        sonuc[ad.strip()] = deger in ("evet", "acik", "açık", "true", "1")
    return sonuc


# ============================================================================= kasa ve anahtar
def _etkilesimli() -> bool:
    """Parola sorulabilecek gerçek bir konsol var mı?

    Windows'ta NUL aygıtı için ``isatty()`` True döner; getpass o zaman konsolda sonsuza dek bekler.
    Bu yüzden Windows'ta konsol kipi de sorulur (NUL ve borular için başarısız olur).
    """
    try:
        if not (sys.stdin and sys.stdin.isatty()):
            return False
        if sys.platform != "win32":
            return True
        import ctypes
        import msvcrt

        kip = ctypes.c_uint32()
        tutamac = msvcrt.get_osfhandle(sys.stdin.fileno())
        return bool(ctypes.windll.kernel32.GetConsoleMode(ctypes.c_void_p(tutamac), ctypes.byref(kip)))
    except (AttributeError, OSError, ValueError):
        return False


def _parola(yeni: bool) -> bytes:
    ortam = os.environ.get("SAHA_LISANS_PAROLA")
    if ortam:
        return ortam.encode("utf-8")
    if not _etkilesimli():
        raise Hata("Kasa parolası gerekiyor. Bu komutu bir komut penceresinde çalıştırın ya da "
                   "SAHA_LISANS_PAROLA ortam değişkenini verin.")
    p1 = getpass.getpass("Kasa parolası: ")
    if yeni:
        if len(p1) < 8:
            raise Hata("Parola en az 8 karakter olmalı.")
        if getpass.getpass("Parola (tekrar): ") != p1:
            raise Hata("Parolalar aynı değil.")
    return p1.encode("utf-8")


def anahtar_olustur(kasa: Path, *, parolasiz: bool = False, depoya_yaz: bool = False) -> tuple[str, Path]:
    """Ed25519 anahtar çifti üretir. Kasada anahtar varsa ASLA üzerine yazmaz."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    ozel_yol = kasa / OZEL_ADI
    if ozel_yol.exists():
        raise Hata(f"Kasada zaten bir anahtar var: {ozel_yol}\n"
                   "Yeni anahtar üretmek VERİLMİŞ BÜTÜN LİSANSLARI geçersiz kılar (uygulamadaki genel anahtar "
                   "değişir). Gerçekten istiyorsanız eski kasayı önce başka bir yere taşıyın.")
    sifreleme = serialization.NoEncryption() if parolasiz else \
        serialization.BestAvailableEncryption(_parola(yeni=True))
    ozel = Ed25519PrivateKey.generate()
    kasa.mkdir(parents=True, exist_ok=True)
    (kasa / LISANS_DIZINI).mkdir(exist_ok=True)
    ozel_pem = ozel.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, sifreleme)
    genel_pem = ozel.public_key().public_bytes(serialization.Encoding.PEM,
                                               serialization.PublicFormat.SubjectPublicKeyInfo)
    # 'x' kipi: yarışta bile var olan dosyanın üzerine yazılmaz
    with open(ozel_yol, "xb") as f:
        f.write(ozel_pem)
    try:
        os.chmod(ozel_yol, 0o600)
    except OSError:
        pass
    (kasa / GENEL_ADI).write_bytes(genel_pem)
    okubeni = kasa / "OKUBENI.txt"
    if not okubeni.exists():
        okubeni.write_text(_OKUBENI, encoding="utf-8")
    if depoya_yaz:
        DEPO_GENEL_ANAHTAR.write_bytes(genel_pem)
    return L.anahtar_kimligi(ozel.public_key()), kasa / GENEL_ADI


def ozel_anahtar_yukle(kasa: Path):
    from cryptography.hazmat.primitives import serialization

    yol = kasa / OZEL_ADI
    if not yol.is_file():
        raise Hata(f"Kasada özel anahtar yok ({yol}). Önce:  python -m lisans.uret anahtar-olustur")
    veri = yol.read_bytes()
    try:
        return serialization.load_pem_private_key(veri, password=None)
    except TypeError:  # şifreli
        pass
    try:
        return serialization.load_pem_private_key(veri, password=_parola(yeni=False))
    except ValueError:
        raise Hata("Kasa parolası yanlış.") from None


def imzala(yuk: dict, ozel) -> tuple[bytes, str]:
    """İçeriği denetler ve imzalar → (imza, anahtar kimliği)."""
    hatalar = L.yuk_denetle(yuk)
    if hatalar:
        raise L.LisansHatasi("Lisans içeriği geçersiz: " + "; ".join(hatalar))
    return ozel.sign(L.IMZA_ONEKI + L.kanonik(yuk)), L.anahtar_kimligi(ozel.public_key())


def yuk_kur(*, musteri: str, bayi_kodu: str, baslangic: dt.date, bitis: dt.date, cihaz_siniri: int = 1,
            izinli_cihazlar=(), ozellikler: dict | None = None, kullanici_siniri: int | None = None,
            ek_sure_gun: int = L.VARSAYILAN_EK_SURE_GUN, not_: str | None = None,
            onceki_lisans_no: str | None = None, lisans_no: str | None = None,
            duzenleme: dt.date | None = None) -> dict:
    """Lisans içeriği (imzasız). Denetimden geçmezse ``LisansHatasi``."""
    duzenleme = duzenleme or L.turkiye_bugun()
    yuk = {
        "surum": L.BICIM_SURUMU,
        "urun": L.URUN,
        "lisans_no": lisans_no or f"SL-{duzenleme.year}-{secrets.token_hex(3).upper()}",
        "musteri": musteri.strip(),
        "bayi_kodu": (bayi_kodu or "").strip(),
        "baslangic": baslangic.isoformat(),
        "bitis": bitis.isoformat(),
        "ek_sure_gun": ek_sure_gun,
        "cihaz_siniri": cihaz_siniri,
        "izinli_cihazlar": list(izinli_cihazlar),
        "kullanici_siniri": kullanici_siniri,
        "ozellikler": ozellikler if ozellikler is not None else {ad: v for ad, (_, v) in L.OZELLIKLER.items()},
        "duzenleme_tarihi": duzenleme.isoformat(),
    }
    if onceki_lisans_no:
        yuk["onceki_lisans_no"] = onceki_lisans_no
    if not_:
        yuk["not"] = not_.strip()
    hatalar = L.yuk_denetle(yuk)
    if hatalar:
        raise L.LisansHatasi("Lisans içeriği geçersiz: " + "; ".join(hatalar))
    return L._normalle(yuk)


# ============================================================================= defter
def kayitlar(kasa: Path) -> list[dict]:
    yol = kasa / KAYIT_ADI
    if not yol.is_file():
        return []
    cikti = []
    for satir in yol.read_text(encoding="utf-8").splitlines():
        if satir.strip():
            try:
                cikti.append(json.loads(satir))
            except ValueError:
                continue
    return cikti


def kayit_ekle(kasa: Path, olay: dict) -> None:
    olay = {"zaman": dt.datetime.now(L.TR).isoformat(timespec="seconds"), **olay}
    with open(kasa / KAYIT_ADI, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(olay, ensure_ascii=False) + "\n")


def lisans_tablosu(kasa: Path) -> dict[str, dict]:
    """lisans_no → {lisans, dosya, durduruldu, yerine}."""
    tablo: dict[str, dict] = {}
    for olay in kayitlar(kasa):
        if olay.get("olay") == "verildi" and isinstance(olay.get("lisans"), dict):
            yuk = olay["lisans"]
            tablo[yuk["lisans_no"]] = {"lisans": yuk, "dosya": olay.get("dosya"), "durduruldu": None,
                                       "yerine": None}
            onceki = yuk.get("onceki_lisans_no")
            if onceki in tablo:
                tablo[onceki]["yerine"] = yuk["lisans_no"]
        elif olay.get("olay") == "durduruldu" and olay.get("lisans_no") in tablo:
            tablo[olay["lisans_no"]]["durduruldu"] = olay.get("neden") or "—"
        elif olay.get("olay") == "durdurma_geri_alindi" and olay.get("lisans_no") in tablo:
            tablo[olay["lisans_no"]]["durduruldu"] = None
    return tablo


def lisans_ver(kasa: Path, yuk: dict, cikti: Path | None = None) -> tuple[Path, str]:
    """İmzalar, kasaya (ve istenirse ``cikti``ya) yazar, deftere işler → (dosya, lisans metni)."""
    if yuk["lisans_no"] in lisans_tablosu(kasa):
        raise Hata(f"{yuk['lisans_no']} numaralı lisans zaten verilmiş.")
    ozel = ozel_anahtar_yukle(kasa)
    imza, kimlik = imzala(yuk, ozel)
    metin = L.dosya_metni(yuk, imza, kimlik)
    # kendi kendini denetle: kasadaki genel anahtarla doğrulanmalı
    denetim = L.dogrula_metin(metin, kasa / GENEL_ADI,
                              cihaz=(yuk["izinli_cihazlar"] or [L.cihaz_kimligi()])[0],
                              bugun=L.tarih_coz(yuk["baslangic"]))
    if denetim.durum not in (L.GECERLI, L.SURESI_YAKIN):
        raise Hata(f"İmzalanan lisans doğrulanamadı ({denetim.durum}: {denetim.ayrinti}). Kasadaki genel "
                   "anahtar özel anahtarla eşleşmiyor olabilir.")
    dosya = kasa / LISANS_DIZINI / f"{yuk['lisans_no']}.lisans.json"
    dosya.parent.mkdir(parents=True, exist_ok=True)
    dosya.write_text(metin, encoding="utf-8", newline="\n")
    if cikti:
        cikti = Path(cikti)
        if cikti.is_dir():
            cikti = cikti / dosya.name
        cikti.write_text(metin, encoding="utf-8", newline="\n")
    kayit_ekle(kasa, {"olay": "verildi", "lisans": yuk, "dosya": str(dosya.relative_to(kasa)),
                      "anahtar_kimligi": kimlik})
    return (cikti or dosya), L.anahtar_metni(yuk, imza)


# ============================================================================= çıktı
def _ozet_yaz(yuk: dict, dosya: Path, metin: str) -> None:
    bas, bit = L.tarih_coz(yuk["baslangic"]), L.tarih_coz(yuk["bitis"])
    cihaz = f"en çok {yuk['cihaz_siniri']}"
    cihaz += f" · bağlı: {', '.join(yuk['izinli_cihazlar'])}" if yuk["izinli_cihazlar"] else " · her bilgisayar"
    acik = [ad for ad, v in yuk["ozellikler"].items() if v]
    print(f"Lisans verildi: {yuk['lisans_no']}")
    print(f"  Müşteri     : {yuk['musteri']}")
    print(f"  Bayi kodu   : {yuk['bayi_kodu'] or '—'}")
    print(f"  Süre        : {L.tarih_metni(bas)} – {L.tarih_metni(bit)} ({(bit - bas).days + 1} gün) "
          f"+ {yuk['ek_sure_gun']} gün ek süre")
    print(f"  Cihaz       : {cihaz}")
    print(f"  Kullanıcı   : {yuk.get('kullanici_siniri') or 'sınırsız'}")
    print(f"  Özellikler  : {', '.join(acik) or '—'}")
    if yuk.get("onceki_lisans_no"):
        print(f"  Önceki      : {yuk['onceki_lisans_no']}")
    print(f"  Dosya       : {dosya}")
    print("\nLisans metni (e-postayla gönderilebilir; Ayarlar › Lisans'a yapıştırılır):")
    print(metin)


def _durum_metni(kayit: dict, bugun: dt.date) -> str:
    yuk = kayit["lisans"]
    if kayit["yerine"]:
        return f"yenilendi → {kayit['yerine']}"
    bitis = L.tarih_coz(yuk["bitis"])
    kalan = (bitis - bugun).days
    ek_son = bitis + dt.timedelta(days=yuk.get("ek_sure_gun", L.VARSAYILAN_EK_SURE_GUN))
    if bugun < L.tarih_coz(yuk["baslangic"]):
        metin = "henüz başlamadı"
    elif kalan > L.UYARI_GUN:
        metin = f"geçerli ({kalan} gün)"
    elif kalan >= 0:
        metin = f"süresi yakın ({kalan} gün)"
    elif bugun <= ek_son:
        metin = f"doldu · ek süre (son gün {L.tarih_metni(ek_son)})"
    else:
        metin = "doldu · müşteride salt okunur"
    if kayit["durduruldu"]:
        metin += " · YENİLENMEYECEK"
    return metin


def _tablo_yaz(satirlar: list[list[str]], basliklar: list[str]) -> None:
    genislik = [max(len(str(x)) for x in sutun) for sutun in zip(basliklar, *satirlar)]
    print("  ".join(b.ljust(g) for b, g in zip(basliklar, genislik)))
    print("  ".join("-" * g for g in genislik))
    for s in satirlar:
        print("  ".join(str(x).ljust(g) for x, g in zip(s, genislik)))


# ============================================================================= komutlar
def _k_anahtar(a) -> int:
    kasa = kasa_yolu(a.kasa)
    kimlik, genel = anahtar_olustur(kasa, parolasiz=a.parolasiz, depoya_yaz=a.depoya_yaz)
    print("Anahtar çifti oluşturuldu.")
    print(f"  Kasa            : {kasa}")
    print(f"  Özel anahtar    : {kasa / OZEL_ADI}   (YALNIZ SİZDE KALIR — yedekleyin, paylaşmayın)")
    print(f"  Genel anahtar   : {genel}")
    print(f"  Anahtar kimliği : {kimlik}")
    if a.parolasiz:
        print("  UYARI: özel anahtar parolasız saklandı. Bu bilgisayara erişen herkes lisans üretebilir.")
    if a.depoya_yaz:
        print(f"\nGenel anahtar depoya yazıldı: {DEPO_GENEL_ANAHTAR}")
        print("Bir sonraki sürümle birlikte lisans denetimi AÇILIR. Önce müşteriye lisansını verin.")
    else:
        print("\nLisans denetimini uygulamada açmak için (önce müşteriye lisansını verin!):")
        print(f'  copy "{genel}" "{DEPO_GENEL_ANAHTAR}"')
    return 0


def _k_ver(a) -> int:
    kasa = kasa_yolu(a.kasa)
    bugun = L.turkiye_bugun()
    baslangic = _tarih(a.baslangic, "--baslangic") if a.baslangic else bugun
    if a.bitis:
        bitis = _tarih(a.bitis, "--bitis")
    elif a.ay or a.gun:
        bitis = sure_sonu(baslangic, ay=a.ay, gun=a.gun)
    else:
        raise Hata("Süre gerekli: --ay 12, --gun 30 ya da --bitis YYYY-AA-GG")
    cihazlar = _cihazlar(a.cihaz)
    try:
        yuk = yuk_kur(musteri=a.musteri, bayi_kodu=a.bayi_kodu, baslangic=baslangic, bitis=bitis,
                      cihaz_siniri=a.cihaz_siniri or max(1, len(cihazlar)), izinli_cihazlar=cihazlar,
                      ozellikler=_ozellikler({ad: v for ad, (_, v) in L.OZELLIKLER.items()}, a.ozellik),
                      kullanici_siniri=a.kullanici_siniri, ek_sure_gun=a.ek_sure_gun, not_=a.not_,
                      duzenleme=bugun)
    except L.LisansHatasi as exc:
        raise Hata(exc.mesaj) from None
    dosya, metin = lisans_ver(kasa, yuk, a.cikti)
    _ozet_yaz(yuk, dosya, metin)
    return 0


def _k_yenile(a) -> int:
    kasa = kasa_yolu(a.kasa)
    tablo = lisans_tablosu(kasa)
    if a.lisans_no not in tablo:
        raise Hata(f"{a.lisans_no} defterde yok. 'liste' ile bakın.")
    kayit = tablo[a.lisans_no]
    if kayit["yerine"]:
        raise Hata(f"{a.lisans_no} zaten {kayit['yerine']} ile yenilenmiş; onu yenileyin.")
    eski = kayit["lisans"]
    bugun = L.turkiye_bugun()
    baslangic = _tarih(a.baslangic, "--baslangic") if a.baslangic else bugun
    if a.bitis:
        bitis = _tarih(a.bitis, "--bitis")
    elif a.ay or a.gun:
        # Kesintisiz uzatma: eski bitişin ertesinden (bitiş geçmişse bugünden) itibaren
        temel = max(L.tarih_coz(eski["bitis"]) + dt.timedelta(days=1), baslangic)
        bitis = sure_sonu(temel, ay=a.ay, gun=a.gun)
    else:
        raise Hata("Süre gerekli: --ay 12, --gun 30 ya da --bitis YYYY-AA-GG")
    cihazlar = _cihazlar(a.cihaz) if a.cihaz else list(eski["izinli_cihazlar"])
    for c in _cihazlar(a.cihaz_ekle):
        if c not in cihazlar:
            cihazlar.append(c)
    cikar = set(_cihazlar(a.cihaz_cikar))
    cihazlar = [c for c in cihazlar if c not in cikar]
    try:
        yuk = yuk_kur(musteri=a.musteri or eski["musteri"],
                      bayi_kodu=a.bayi_kodu if a.bayi_kodu is not None else eski["bayi_kodu"],
                      baslangic=baslangic, bitis=bitis,
                      cihaz_siniri=a.cihaz_siniri or max(eski["cihaz_siniri"], len(cihazlar), 1),
                      izinli_cihazlar=cihazlar, ozellikler=_ozellikler(eski["ozellikler"], a.ozellik),
                      kullanici_siniri=a.kullanici_siniri if a.kullanici_siniri is not None
                      else eski.get("kullanici_siniri"),
                      ek_sure_gun=a.ek_sure_gun if a.ek_sure_gun is not None else eski["ek_sure_gun"],
                      not_=a.not_ if a.not_ is not None else eski.get("not"),
                      onceki_lisans_no=eski["lisans_no"], duzenleme=bugun)
    except L.LisansHatasi as exc:
        raise Hata(exc.mesaj) from None
    dosya, metin = lisans_ver(kasa, yuk, a.cikti)
    _ozet_yaz(yuk, dosya, metin)
    return 0


def _k_durdur(a) -> int:
    kasa = kasa_yolu(a.kasa)
    tablo = lisans_tablosu(kasa)
    if a.lisans_no not in tablo:
        raise Hata(f"{a.lisans_no} defterde yok. 'liste' ile bakın.")
    yuk = tablo[a.lisans_no]["lisans"]
    if a.geri_al:
        kayit_ekle(kasa, {"olay": "durdurma_geri_alindi", "lisans_no": a.lisans_no})
        print(f"{a.lisans_no}: 'yenilenmeyecek' işareti kaldırıldı. Yenilemek için:  yenile {a.lisans_no} --ay 12")
        return 0
    kayit_ekle(kasa, {"olay": "durduruldu", "lisans_no": a.lisans_no, "neden": a.neden})
    bitis = L.tarih_coz(yuk["bitis"])
    ek_son = bitis + dt.timedelta(days=yuk.get("ek_sure_gun", L.VARSAYILAN_EK_SURE_GUN))
    print(f"{a.lisans_no} 'yenilenmeyecek' olarak işaretlendi ({yuk['musteri']}).")
    print(f"  Verilmiş bir lisans geri alınamaz: {L.tarih_metni(bitis)} tarihine kadar geçerli kalır.")
    print(f"  Ardından ek süre; {L.tarih_metni(ek_son)} tarihinden sonra müşterinin sistemi SALT OKUNUR olur.")
    print("  Veriler silinmez; müşteri görüntüleme ve dışa aktarmaya devam eder.")
    print("  Müşteriye bu tarihleri yazılı olarak bildirin (sözleşme: lisans/SOZLESME_TASLAGI.md).")
    return 0


def _k_liste(a) -> int:
    kasa = kasa_yolu(a.kasa)
    tablo = lisans_tablosu(kasa)
    if not tablo:
        print(f"Kasada verilmiş lisans yok ({kasa}).")
        return 0
    bugun = L.turkiye_bugun()
    satirlar = []
    for no, k in sorted(tablo.items(), key=lambda x: (x[1]["lisans"]["musteri"], x[1]["lisans"]["bitis"])):
        if k["yerine"] and not a.hepsi:
            continue
        y = k["lisans"]
        cihaz = f"{len(y['izinli_cihazlar'])}/{y['cihaz_siniri']}" if y["izinli_cihazlar"] else f"-/{y['cihaz_siniri']}"
        satirlar.append([no, y["musteri"][:32], y["bayi_kodu"] or "—", y["baslangic"], y["bitis"], cihaz,
                         _durum_metni(k, bugun)])
    _tablo_yaz(satirlar, ["Lisans no", "Müşteri", "Bayi kodu", "Başlangıç", "Bitiş", "Cihaz", "Durum"])
    if not a.hepsi and any(k["yerine"] for k in tablo.values()):
        print("\n(Yenilenmiş eski lisanslar gizli; hepsi için: liste --hepsi)")
    return 0


def _k_goster(a) -> int:
    kasa = kasa_yolu(a.kasa)
    kaynak = Path(a.lisans)
    metin = kaynak.read_text(encoding="utf-8-sig") if kaynak.is_file() else a.lisans
    anahtar = a.anahtar or (kasa / GENEL_ADI if (kasa / GENEL_ADI).is_file() else None)
    if anahtar is None:
        raise Hata("Genel anahtar bulunamadı: --anahtar verin ya da --kasa gösterin.")
    try:
        yuk, _, _ = L.coz(metin)
        izinli = yuk.get("izinli_cihazlar") if isinstance(yuk, dict) else None
    except L.LisansHatasi:
        izinli = None
    cihaz = (izinli[0] if isinstance(izinli, list) and izinli and L.cihaz_normalle(izinli[0]) else None)
    s = L.dogrula_metin(metin, anahtar, cihaz=cihaz)
    print(f"Durum : {s.durum} · kip {s.mod}")
    print(f"İmza  : {'geçerli (anahtar ' + s.anahtar_kimligi + ')' if s.anahtar_kimligi else 'GEÇERSİZ'}")
    if s.lisans:
        print(json.dumps(s.lisans, ensure_ascii=False, indent=2))
    print(f"Mesaj : {s.mesaj}")
    if s.ayrinti:
        print(f"Ayrıntı: {s.ayrinti}")
    if cihaz is None and s.lisans:
        print("(Cihaz bağı yok: her bilgisayarda geçerli.)")
    return 0 if s.anahtar_kimligi else 1


def main(argv: list[str] | None = None) -> int:
    L._konsol()
    ayrac = argparse.ArgumentParser(prog="python -m lisans.uret",
                                    description="Saha Sistemi lisans sahibinin aracı (uygulamayla gitmez)")
    ayrac.add_argument("--kasa", help="kasa klasörü (varsayılan: SAHA_LISANS_KASA ya da ~/.saha-lisans)")
    alt = ayrac.add_subparsers(dest="komut", required=True)

    k = alt.add_parser("anahtar-olustur", help="Ed25519 anahtar çifti (bir kez)")
    k.add_argument("--parolasiz", action="store_true", help="özel anahtarı parolasız sakla (önerilmez)")
    k.add_argument("--depoya-yaz", action="store_true",
                   help=f"genel anahtarı {DEPO_GENEL_ANAHTAR} yoluna da yaz (denetimi açar)")
    k.set_defaults(is_=_k_anahtar)

    def ortak(p, yeni: bool):
        p.add_argument("--baslangic", help="YYYY-AA-GG (varsayılan: bugün)")
        p.add_argument("--bitis", help="YYYY-AA-GG (bitiş günü dahil)")
        p.add_argument("--ay", type=int, help="süre, ay")
        p.add_argument("--gun", type=int, help="süre, gün")
        p.add_argument("--cihaz", action="append", help="izinli cihaz kimliği (tekrarlanabilir)")
        p.add_argument("--cihaz-siniri", type=int)
        p.add_argument("--ozellik", action="append", help="ad=evet|hayir (tekrarlanabilir)")
        p.add_argument("--kullanici-siniri", type=int, help="aktif kullanıcı sınırı (yok = sınırsız)")
        p.add_argument("--ek-sure-gun", type=int, default=L.VARSAYILAN_EK_SURE_GUN if yeni else None)
        p.add_argument("--not", dest="not_")
        p.add_argument("--cikti", help="lisans dosyasının bir kopyası (dosya ya da klasör)")

    v = alt.add_parser("ver", help="yeni lisans")
    v.add_argument("--musteri", required=True, help="müşteri/bayi unvanı")
    v.add_argument("--bayi-kodu", required=True)
    ortak(v, yeni=True)
    v.set_defaults(is_=_k_ver)

    y = alt.add_parser("yenile", help="lisansı uzat (aynı koşullar; değişiklik verilebilir)")
    y.add_argument("lisans_no")
    y.add_argument("--musteri")
    y.add_argument("--bayi-kodu")
    y.add_argument("--cihaz-ekle", action="append")
    y.add_argument("--cihaz-cikar", action="append")
    ortak(y, yeni=False)
    y.set_defaults(is_=_k_yenile)

    d = alt.add_parser("durdur", help="yenilenmeyecek olarak işaretle (uzaktan kapatma YOK)")
    d.add_argument("lisans_no")
    d.add_argument("--neden", default="")
    d.add_argument("--geri-al", action="store_true", help="işareti kaldır")
    d.set_defaults(is_=_k_durdur)

    li = alt.add_parser("liste", help="verilen lisanslar")
    li.add_argument("--hepsi", action="store_true", help="yenilenmiş eski lisansları da göster")
    li.set_defaults(is_=_k_liste)

    g = alt.add_parser("goster", help="bir lisans dosyasını/metnini doğrula ve göster")
    g.add_argument("lisans", help="dosya yolu ya da SAHA1. metni")
    g.add_argument("--anahtar", help="genel anahtar PEM (varsayılan: kasadaki)")
    g.set_defaults(is_=_k_goster)

    c = alt.add_parser("cihaz", help="bu bilgisayarın cihaz kimliği")
    c.set_defaults(is_=lambda _a: print(f"Cihaz kimliği: {L.cihaz_kimligi()}") or 0)

    a = ayrac.parse_args(argv)
    return a.is_(a)


if __name__ == "__main__":
    sys.exit(main())
