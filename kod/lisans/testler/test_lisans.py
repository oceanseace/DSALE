"""Lisans testleri: kurcalama, süre, ek süre, cihaz bağı, durumlu denetçi, yükleme, salt okunur kapısı, CLI.

    .venv\\Scripts\\python.exe -m pytest lisans/testler -q

Her test kendi geçici anahtarını üretir; gerçek kasaya, gerçek lisansa, canlı sunucuya dokunulmaz.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import yollar
from lisans import lisans as L
from lisans import uret as U

KOK = yollar.KOD          # kod/: lisans paketi burada; "-m lisans.uret" buradan çalışır
PYTHON = sys.executable
CIHAZ_A = "AAAA-1111-BBBB-2222-CCCC"
CIHAZ_B = "DDDD-3333-EEEE-4444-FFFF"
BAS = dt.date(2026, 10, 1)
BIT = dt.date(2027, 9, 30)


# ============================================================================= yardımcılar
@pytest.fixture
def ozel():
    return Ed25519PrivateKey.generate()


@pytest.fixture
def genel_pem(tmp_path, ozel) -> Path:
    yol = tmp_path / "genel_anahtar.pem"
    yol.write_bytes(ozel.public_key().public_bytes(serialization.Encoding.PEM,
                                                   serialization.PublicFormat.SubjectPublicKeyInfo))
    return yol


def yuk(**degisiklik) -> dict:
    alanlar = dict(musteri="ÖRNEK BAYİ İLETİŞİM LTD. ŞTİ.", bayi_kodu="00000.00000", baslangic=BAS, bitis=BIT,
                   cihaz_siniri=2, izinli_cihazlar=[], lisans_no="SL-2026-TEST01", duzenleme=BAS)
    alanlar.update(degisiklik)
    return U.yuk_kur(**alanlar)


def imzali(ozel, **degisiklik) -> tuple[dict, str]:
    y = yuk(**degisiklik)
    imza, kimlik = U.imzala(y, ozel)
    return y, L.dosya_metni(y, imza, kimlik)


def dogrula(metin, genel, gun=BAS + dt.timedelta(days=10), cihaz=CIHAZ_A, **kw) -> L.Sonuc:
    return L.dogrula_metin(metin, genel, cihaz=cihaz, bugun=gun, **kw)


# ============================================================================= geçerli lisans
def test_gecerli_lisans_dogrulanir_ve_kalan_gun_dogru(ozel, genel_pem):
    y, metin = imzali(ozel)
    s = dogrula(metin, genel_pem, gun=dt.date(2026, 10, 11))
    assert s.durum == L.GECERLI and s.mod == L.TAM and s.seviye == "yok"
    assert s.kalan_gun == (BIT - dt.date(2026, 10, 11)).days == 354
    assert s.lisans["musteri"] == y["musteri"] and s.anahtar_kimligi == L.anahtar_kimligi(ozel.public_key())
    assert "30 Eylül 2027" in s.mesaj
    assert s.ek_sure_son is None and s.mesaj_ekip is None


def test_dosya_uzerinden_dogrula_ve_varsayilan_ozellikler(ozel, genel_pem, tmp_path):
    _, metin = imzali(ozel)
    dosya = tmp_path / "lisans.json"
    dosya.write_text(metin, encoding="utf-8")
    s = L.dogrula(dosya, genel_pem, cihaz=CIHAZ_A, bugun=BAS)
    assert s.durum == L.GECERLI
    assert s.ozellik_acik("satis") and s.ozellik_acik("is_emri")
    assert not s.ozellik_acik("boss_eklentisi")          # bilinmeyen ek modül varsayılan kapalı


# ============================================================================= kurcalama
@pytest.mark.parametrize("alan,yeni", [
    ("bitis", "2099-12-31"),
    ("musteri", "BAŞKA BAYİ"),
    ("cihaz_siniri", 50),
    ("izinli_cihazlar", [CIHAZ_B]),
    ("ozellikler", {"satis": True, "is_emri": True, "boss_eklentisi": True}),
    ("ek_sure_gun", 90),
    ("kullanici_siniri", 999),
])
def test_dosyada_herhangi_bir_alan_degisirse_imza_bozuk(ozel, genel_pem, alan, yeni):
    _, metin = imzali(ozel)
    govde = json.loads(metin)
    govde["lisans"][alan] = yeni
    s = dogrula(json.dumps(govde, ensure_ascii=False, indent=2), genel_pem)
    assert s.durum == L.IMZA_BOZUK
    assert s.lisans is None                               # doğrulanmamış içerik asla gösterilmez
    assert s.mod == L.TAM and s.ek_sure_son == BAS + dt.timedelta(days=10 + 13)   # ek süre bugünden
    assert "İmza tutmuyor" in s.ayrinti


def test_alan_eklenirse_ya_da_silinirse_imza_bozuk(ozel, genel_pem):
    _, metin = imzali(ozel)
    govde = json.loads(metin)
    govde["lisans"]["sinirsiz"] = True
    assert dogrula(json.dumps(govde), genel_pem).durum == L.IMZA_BOZUK
    govde = json.loads(metin)
    del govde["lisans"]["izinli_cihazlar"]
    assert dogrula(json.dumps(govde), genel_pem).durum == L.IMZA_BOZUK


def test_imzanin_tek_biti_degisirse_imza_bozuk(ozel, genel_pem):
    _, metin = imzali(ozel)
    govde = json.loads(metin)
    ham = bytearray(L.b64d(govde["imza"]))
    ham[5] ^= 0x01
    govde["imza"] = L.b64e(bytes(ham))
    assert dogrula(json.dumps(govde), genel_pem).durum == L.IMZA_BOZUK


def test_baska_anahtarla_imzalanan_lisans_reddedilir(ozel, genel_pem):
    sahte = Ed25519PrivateKey.generate()
    _, metin = imzali(sahte)                            # içerik birebir aynı, imzalayan başka
    s = dogrula(metin, genel_pem)
    assert s.durum == L.IMZA_BOZUK and s.lisans is None


def test_anahtar_yenilemede_iki_genel_anahtar_birlikte_kabul_edilir(ozel, genel_pem, tmp_path):
    yeni = Ed25519PrivateKey.generate()
    iki = tmp_path / "iki.pem"
    iki.write_bytes(genel_pem.read_bytes() + yeni.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
    assert dogrula(imzali(ozel)[1], iki).durum == L.GECERLI
    assert dogrula(imzali(yeni)[1], iki).durum == L.GECERLI


def test_anahtar_metni_dosyayla_ayni_lisans_ve_kurcalanamaz(ozel, genel_pem):
    y, metin = imzali(ozel)
    imza = L.b64d(json.loads(metin)["imza"])
    tek = L.anahtar_metni(y, imza)
    assert tek.startswith("SAHA1.") and "\n" not in tek
    assert dogrula(tek, genel_pem).durum == L.GECERLI
    # e-postada satır kırılsa da okunur
    assert dogrula("\n".join(tek[i:i + 64] for i in range(0, len(tek), 64)), genel_pem).durum == L.GECERLI
    # içerik parçası başka bir lisansınkiyle değiştirilirse
    y2 = dict(y, bitis="2099-12-31")
    sahte = f"SAHA1.{L.b64e(L.kanonik(y2))}.{tek.split('.')[2]}"
    assert dogrula(sahte, genel_pem).durum == L.IMZA_BOZUK


@pytest.mark.parametrize("metin", ["", "   ", "merhaba", "{bozuk json", '{"lisans": {}}', "SAHA1.abc",
                                   "SAHA1.!!!.???", "SAHA2.e30.AAAA", '{"bicim":"baska/9","lisans":{},"imza":""}'])
def test_bozuk_ya_da_bos_dosya_imza_bozuk_olur_cokmez(genel_pem, metin):
    s = dogrula(metin, genel_pem)
    assert s.durum == L.IMZA_BOZUK and s.mod == L.TAM and s.ayrinti


def test_bom_ve_nfd_turkce_karakter_lisansi_bozmaz(ozel, genel_pem, tmp_path):
    _, metin = imzali(ozel)
    govde = json.loads(metin)
    govde["lisans"]["musteri"] = unicodedata.normalize("NFD", govde["lisans"]["musteri"])
    assert govde["lisans"]["musteri"] != unicodedata.normalize("NFC", govde["lisans"]["musteri"])
    dosya = tmp_path / "lisans.json"
    dosya.write_bytes("﻿".encode("utf-8") + json.dumps(govde, ensure_ascii=False).encode("utf-8"))
    assert L.dogrula(dosya, genel_pem, cihaz=CIHAZ_A, bugun=BAS).durum == L.GECERLI


def test_imzali_ama_kurala_uymayan_icerik_imza_bozuk(ozel, genel_pem):
    y = yuk()
    y["urun"] = "baska-urun"                            # imzala() bunu engeller; elle imzalayalım
    imza = ozel.sign(L.IMZA_ONEKI + L.kanonik(y))
    s = dogrula(L.dosya_metni(y, imza), genel_pem)
    assert s.durum == L.IMZA_BOZUK and "urun" in s.ayrinti


# ============================================================================= süre ve ek süre
@pytest.mark.parametrize("gun_farki,durum,mod,seviye,ekip", [
    (31, L.GECERLI, L.TAM, "yok", False),
    (30, L.SURESI_YAKIN, L.TAM, "bilgi", False),
    (8, L.SURESI_YAKIN, L.TAM, "bilgi", False),
    (7, L.SURESI_YAKIN, L.TAM, "uyari", False),
    (0, L.SURESI_YAKIN, L.TAM, "uyari", False),          # bitiş günü: son gün
    (-1, L.SURESI_DOLDU, L.TAM, "uyari", False),         # ek sürenin 1. günü
    (-11, L.SURESI_DOLDU, L.TAM, "uyari", False),        # ek süre: 4 gün kaldı
    (-12, L.SURESI_DOLDU, L.TAM, "kritik", True),        # son 3 gün: ekip de görür
    (-14, L.SURESI_DOLDU, L.TAM, "kritik", True),        # ek sürenin 14. (son) günü
    (-15, L.SURESI_DOLDU, L.SALT_OKUNUR, "kritik", True),
    (-400, L.SURESI_DOLDU, L.SALT_OKUNUR, "kritik", True),
])
def test_sure_esikleri_ve_ek_sure(ozel, genel_pem, gun_farki, durum, mod, seviye, ekip):
    _, metin = imzali(ozel)
    gun = BIT - dt.timedelta(days=gun_farki)
    s = dogrula(metin, genel_pem, gun=gun)
    assert (s.durum, s.mod, s.seviye, s.ekibe_goster) == (durum, mod, seviye, ekip)
    assert s.kalan_gun == gun_farki
    if durum == L.SURESI_DOLDU:
        assert s.ek_sure_son == BIT + dt.timedelta(days=14)
        assert "silinmez" in s.mesaj or "silinmez" in (s.mesaj_ekip or "") or "duruyor" in s.mesaj
    if ekip:
        assert s.mesaj_ekip and "Yöneticinize" in s.mesaj_ekip


def test_mesajlar_acik_ve_turkce(ozel, genel_pem):
    _, metin = imzali(ozel)
    son_gun = dogrula(metin, genel_pem, gun=BIT)
    assert son_gun.baslik == "Lisansın son günü bugün" and "14 günlük ek süre" in son_gun.mesaj
    ek1 = dogrula(metin, genel_pem, gun=BIT + dt.timedelta(days=1))
    assert "14 Ekim 2027 tarihine kadar her şey çalışır (14 gün)" in ek1.mesaj
    son = dogrula(metin, genel_pem, gun=BIT + dt.timedelta(days=14))
    assert "Bugün ek sürenin son günü" in son.mesaj and "yarından itibaren" in son.mesaj_ekip
    salt = dogrula(metin, genel_pem, gun=BIT + dt.timedelta(days=15))
    assert salt.baslik.startswith("Sistem salt okunur") and "dışa aktarma çalışıyor" in salt.mesaj
    assert "telefonunuzda bekler" in salt.mesaj_ekip
    assert "  " not in salt.mesaj


def test_ek_sure_lisanstaki_degerden_gelir(ozel, genel_pem):
    _, sifir = imzali(ozel, ek_sure_gun=0)
    assert dogrula(sifir, genel_pem, gun=BIT).mod == L.TAM
    assert dogrula(sifir, genel_pem, gun=BIT + dt.timedelta(days=1)).mod == L.SALT_OKUNUR
    _, otuz = imzali(ozel, ek_sure_gun=30)
    assert dogrula(otuz, genel_pem, gun=BIT + dt.timedelta(days=30)).mod == L.TAM
    assert dogrula(otuz, genel_pem, gun=BIT + dt.timedelta(days=31)).mod == L.SALT_OKUNUR


def test_henuz_baslamamis_lisans(ozel, genel_pem):
    _, metin = imzali(ozel)
    s = dogrula(metin, genel_pem, gun=BAS - dt.timedelta(days=3))
    assert s.durum == L.HENUZ_BASLAMADI and s.mod == L.TAM and "1 Ekim 2026" in s.mesaj


# ============================================================================= cihaz bağı
def test_cihaz_listesi_varsa_yalniz_o_bilgisayarda_gecerli(ozel, genel_pem):
    _, metin = imzali(ozel, izinli_cihazlar=[CIHAZ_A])
    assert dogrula(metin, genel_pem, cihaz=CIHAZ_A).durum == L.GECERLI
    assert dogrula(metin, genel_pem, cihaz=CIHAZ_A.lower().replace("-", "")).durum == L.GECERLI
    disi = dogrula(metin, genel_pem, cihaz=CIHAZ_B)
    assert disi.durum == L.CIHAZ_DISI and disi.mod == L.TAM
    assert CIHAZ_B in disi.mesaj and disi.cihaz_izinli is False
    assert disi.lisans is not None                         # imza geçerli: koşullar gösterilebilir
    # sorun 20 gün önce ilk kez görüldüyse ek süre bitmiştir
    gun = BAS + dt.timedelta(days=30)
    eski = dogrula(metin, genel_pem, cihaz=CIHAZ_B, gun=gun, sorun_ilk=gun - dt.timedelta(days=20))
    assert eski.mod == L.SALT_OKUNUR and eski.durum == L.CIHAZ_DISI


def test_cihaz_listesi_bossa_her_bilgisayarda_gecerli(ozel, genel_pem):
    _, metin = imzali(ozel, izinli_cihazlar=[])
    assert dogrula(metin, genel_pem, cihaz=CIHAZ_B).durum == L.GECERLI


def test_cihaz_listesi_siniri_asamaz(ozel):
    with pytest.raises(L.LisansHatasi, match="cihaz sınırı"):
        yuk(cihaz_siniri=1, izinli_cihazlar=[CIHAZ_A, CIHAZ_B])


def test_cihaz_kimligi_bicimi_kararli_ve_ham_guid_degil():
    k = L.cihaz_kimligi()
    assert re.fullmatch(r"[0-9A-F]{4}(-[0-9A-F]{4}){4}", k)
    assert L.cihaz_kimligi() == k and L.cihaz_normalle(k.lower()) == k
    if sys.platform == "win32":
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography", 0,
                            winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as a:
            guid = winreg.QueryValueEx(a, "MachineGuid")[0]
        assert L.cihaz_bilgisi()["kaynak"] == "windows_machine_guid"
        assert guid.replace("-", "").upper()[:20] not in k.replace("-", "")   # tuzlu özet, GUID sızmaz
    assert L.cihaz_normalle("AAAA-1111-BBBB-2222-CCC") is None
    assert L.cihaz_normalle("AAAA-1111-BBBB-2222-CCCCX") is None


# ============================================================================= lisans yok / denetim kapalı
def test_lisans_dosyasi_yoksa_lisans_yok_ek_sureyle(genel_pem, tmp_path):
    s = L.dogrula(tmp_path / "yok.json", genel_pem, cihaz=CIHAZ_A, bugun=BAS)
    assert s.durum == L.LISANS_YOK and s.mod == L.TAM and s.ek_sure_son == BAS + dt.timedelta(days=13)
    assert CIHAZ_A in s.mesaj                              # yönetici kimliği lisans sahibine iletebilsin


def test_genel_anahtar_yoksa_denetim_kapali_ve_hicbir_sey_kilitlenmez(tmp_path):
    s = L.dogrula(tmp_path / "yok.json", tmp_path / "anahtar_yok.pem", cihaz=CIHAZ_A, bugun=BAS)
    assert s.durum == L.DENETLENMIYOR and s.mod == L.TAM and s.seviye == "yok"


def test_bozuk_genel_anahtar_dosyasi_imza_bozuk_ek_sureyle(tmp_path, ozel):
    bozuk = tmp_path / "bozuk.pem"
    bozuk.write_text("bu bir anahtar değil", encoding="utf-8")
    s = dogrula(imzali(ozel)[1], bozuk)
    assert s.durum == L.IMZA_BOZUK and s.mod == L.TAM and "PEM" in s.ayrinti


# ============================================================================= durumlu denetçi
class Saat:
    def __init__(self, gun):
        self.gun = gun

    def __call__(self):
        return self.gun


def denetci(tmp_path, genel_pem, saat, cihaz=CIHAZ_A):
    return L.Denetci(tmp_path / "saha" / "lisans.json", genel_anahtar=genel_pem, cihaz=cihaz, bugun=saat,
                     onbellek_sn=0)


def test_denetci_ek_sureyi_ilk_gorulen_gunden_sayar_sorun_degisince_uzatmaz(ozel, genel_pem, tmp_path):
    saat = Saat(BAS)
    d = denetci(tmp_path, genel_pem, saat)
    s0 = d.sonuc()
    assert s0.durum == L.LISANS_YOK and s0.ek_sure_son == BAS + dt.timedelta(days=13)
    durum = json.loads(d.durum_yolu.read_text(encoding="utf-8"))
    assert durum["sorun_ilk"] == BAS.isoformat()
    # 5 gün sonra biri bozuk bir dosya koyar: sorun türü değişti ama ek süre YENİDEN BAŞLAMAZ
    saat.gun = BAS + dt.timedelta(days=5)
    d.lisans_yolu.parent.mkdir(parents=True, exist_ok=True)
    d.lisans_yolu.write_text("{bozuk", encoding="utf-8")
    s5 = d.sonuc()
    assert s5.durum == L.IMZA_BOZUK and s5.ek_sure_son == BAS + dt.timedelta(days=13)
    saat.gun = BAS + dt.timedelta(days=14)
    assert d.sonuc().mod == L.SALT_OKUNUR
    # geçerli lisans yüklenince her şey kaldığı yerden devam eder, sayaç silinir
    _, metin = imzali(ozel)
    s = d.yukle(metin)
    assert s.durum == L.GECERLI and s.mod == L.TAM
    assert json.loads(d.durum_yolu.read_text(encoding="utf-8"))["sorun_ilk"] is None


def test_denetci_suresi_dolan_lisansi_silmek_ek_sureyi_uzatmaz(ozel, genel_pem, tmp_path):
    saat = Saat(BIT + dt.timedelta(days=10))              # sunucu ilk kez bitişten 10 gün sonra açıldı
    d = denetci(tmp_path, genel_pem, saat)
    d.lisans_yolu.parent.mkdir(parents=True, exist_ok=True)
    d.lisans_yolu.write_text(imzali(ozel)[1], encoding="utf-8")
    s = d.sonuc()
    assert s.durum == L.SURESI_DOLDU and s.ek_sure_son == BIT + dt.timedelta(days=14)
    d.lisans_yolu.unlink()                                # dosyayı silmek yeni 14 gün vermez
    s2 = d.sonuc()
    assert s2.durum == L.LISANS_YOK and s2.ek_sure_son == BIT + dt.timedelta(days=14)


def test_denetci_saat_geri_alinirsa_son_gorulen_tarih_kullanilir(ozel, genel_pem, tmp_path):
    saat = Saat(BIT + dt.timedelta(days=20))
    d = denetci(tmp_path, genel_pem, saat)
    d.lisans_yolu.parent.mkdir(parents=True, exist_ok=True)
    d.lisans_yolu.write_text(imzali(ozel)[1], encoding="utf-8")
    assert d.sonuc().mod == L.SALT_OKUNUR
    saat.gun = BIT - dt.timedelta(days=100)               # Windows tarihi geri alındı
    s = d.sonuc()
    assert s.mod == L.SALT_OKUNUR and s.saat_uyarisi and "geri alınmış" in s.mesaj
    assert s.bugun == BIT + dt.timedelta(days=20)


def test_denetci_asiri_ileri_sicrama_kalici_kilit_yapmaz(ozel, genel_pem, tmp_path):
    saat = Saat(BAS + dt.timedelta(days=5))
    d = denetci(tmp_path, genel_pem, saat)
    d.lisans_yolu.parent.mkdir(parents=True, exist_ok=True)
    d.lisans_yolu.write_text(imzali(ozel)[1], encoding="utf-8")
    assert d.sonuc().durum == L.GECERLI
    saat.gun = dt.date(2035, 1, 1)                        # BIOS saati bozuldu
    assert d.sonuc().mod == L.SALT_OKUNUR
    saat.gun = BAS + dt.timedelta(days=6)                 # saat düzeltildi
    s = d.sonuc()
    assert s.durum == L.GECERLI and not s.saat_uyarisi


def test_denetci_onbellegi_dosya_degisince_yenilenir(ozel, genel_pem, tmp_path):
    d = L.Denetci(tmp_path / "lisans.json", genel_anahtar=genel_pem, cihaz=CIHAZ_A, bugun=Saat(BAS))
    assert d.sonuc().durum == L.LISANS_YOK
    d.lisans_yolu.write_text(imzali(ozel)[1], encoding="utf-8")
    assert d.sonuc().durum == L.GECERLI                    # 10 dk beklemeden: dosya izi değişti


# ============================================================================= yükleme
def test_yukle_bozuk_baska_cihaz_suresi_dolmus_ve_kisa_lisansi_reddeder(ozel, genel_pem, tmp_path):
    saat = Saat(BAS + dt.timedelta(days=1))
    d = denetci(tmp_path, genel_pem, saat)
    with pytest.raises(L.LisansHatasi) as h:
        d.yukle("{bozuk")
    assert h.value.kod == "imza_bozuk"
    with pytest.raises(L.LisansHatasi) as h:
        d.yukle(imzali(ozel, izinli_cihazlar=[CIHAZ_B])[1])
    assert h.value.kod == "cihaz_disi" and CIHAZ_A in h.value.mesaj
    with pytest.raises(L.LisansHatasi) as h:
        d.yukle(imzali(ozel, baslangic=dt.date(2025, 1, 1), bitis=dt.date(2025, 12, 31))[1])
    assert h.value.kod == "suresi_doldu"
    with pytest.raises(L.LisansHatasi) as h:
        d.yukle(imzali(ozel, baslangic=dt.date(2027, 1, 1))[1])
    assert h.value.kod == "henuz_baslamadi"
    assert not d.lisans_yolu.exists()                      # hiçbiri diske yazılmadı

    assert d.yukle(imzali(ozel)[1]).durum == L.GECERLI
    with pytest.raises(L.LisansHatasi) as h:               # daha kısa lisans uzununun yerine geçmez
        d.yukle(imzali(ozel, lisans_no="SL-2026-KISA01", bitis=dt.date(2027, 3, 31))[1])
    assert h.value.kod == "daha_kisa"


def test_yukle_eskisini_yedekler_ve_metni_de_kabul_eder(ozel, genel_pem, tmp_path):
    d = denetci(tmp_path, genel_pem, Saat(BAS))
    ilk_y, ilk = imzali(ozel)
    d.yukle(ilk)
    yeni_y = yuk(lisans_no="SL-2027-TEST02", bitis=dt.date(2028, 9, 30), onceki_lisans_no="SL-2026-TEST01")
    imza, _ = U.imzala(yeni_y, ozel)
    s = d.yukle(L.anahtar_metni(yeni_y, imza))             # tek satırlık metin yapıştırıldı
    assert s.durum == L.GECERLI and s.lisans["lisans_no"] == "SL-2027-TEST02"
    yedekler = list((d.lisans_yolu.parent / "yedek").glob("lisans-*.json"))
    assert len(yedekler) == 1 and "SL-2026-TEST01" in yedekler[0].read_text(encoding="utf-8")
    kurulu = json.loads(d.lisans_yolu.read_text(encoding="utf-8"))
    assert kurulu["bicim"] == L.BICIM and kurulu["lisans"]["bitis"] == "2028-09-30"   # okunur dosya
    assert not list(d.lisans_yolu.parent.glob(".lisans.json.*.tmp"))                  # yarım dosya yok


def test_yukleme_diske_yazilamazsa_anlasilir_hata(ozel, genel_pem, tmp_path):
    engel = tmp_path / "engel"
    engel.write_text("klasör değil", encoding="utf-8")        # lisansın klasörü aslında bir dosya
    d = L.Denetci(engel / "lisans.json", genel_anahtar=genel_pem, cihaz=CIHAZ_A, bugun=Saat(BAS))
    with pytest.raises(L.LisansHatasi) as h:
        d.yukle(imzali(ozel)[1])
    assert h.value.kod == "yazilamadi" and "BT" in h.value.mesaj
    assert d.sonuc().durum == L.LISANS_YOK                     # durum dosyası yazılamasa da denetim çalışır


def test_denetim_kapaliyken_yukleme_anlamli_hata_verir(tmp_path, ozel):
    d = L.Denetci(tmp_path / "lisans.json", genel_anahtar=tmp_path / "yok.pem", cihaz=CIHAZ_A, bugun=Saat(BAS))
    with pytest.raises(L.LisansHatasi) as h:
        d.yukle(imzali(ozel)[1])
    assert h.value.kod == "denetim_kapali"


# ============================================================================= salt okunur kapısı
@pytest.mark.parametrize("yontem,yol,serbest", [
    ("GET", "/api/isler", True),
    ("GET", "/api/dosya/rapor.xlsx", True),
    ("HEAD", "/", True),
    ("OPTIONS", "/api/ziyaret", True),
    ("POST", "/api/giris", True),
    ("POST", "/api/pin", True),
    ("POST", "/api/lisans", True),
    ("POST", "/api/kullanici/12/cihaz-cikis", True),
    ("POST", "/api/isler/WO-123/kopya", True),
    ("POST", "/api/ziyaret", False),
    ("POST", "/api/ziyaret/toplu", False),
    ("POST", "/api/kullanici", False),
    ("DELETE", "/api/kullanici/12", False),
    ("PATCH", "/api/ticket/5", False),
    ("PUT", "/api/ayar/altlik", False),
    ("POST", "/api/giris/", False),
    ("POST", "/api/giris/../ziyaret", False),
    ("POST", "/api/kullanici/abc/cihaz-cikis", False),
    ("POST", "/api/isler/a/b/kopya", False),
    ("PUT", "/api/lisans", False),
    ("POST", "/baska", False),                           # varsayılan YASAK: /api dışı da
])
def test_salt_okunur_kapisi(yontem, yol, serbest):
    assert L.yazma_serbest_mi(yontem, yol) is serbest


def test_salt_okunur_yaniti_503_ve_kuyrugu_korur(ozel, genel_pem):
    s = dogrula(imzali(ozel)[1], genel_pem, gun=BIT + dt.timedelta(days=15))
    kod, govde, basliklar = L.salt_okunur_yaniti(s)
    assert kod == 503                                      # 5xx: telefon kaydı kuyrukta tutar
    assert govde["kod"] == "salt_okunur" and govde["lisans"]["mod"] == L.SALT_OKUNUR
    assert "telefonda bekler" in govde["hata"] and basliklar["Retry-After"]


# ============================================================================= API görünümü, sınırlar
def test_ekip_gorunumunde_musteri_ve_lisans_ayrintisi_yok(ozel, genel_pem):
    s = dogrula(imzali(ozel, izinli_cihazlar=[CIHAZ_A])[1], genel_pem)
    ekip = s.sozluk(yonetici=False)
    assert set(ekip) == {"durum", "mod", "seviye", "goster", "baslik", "mesaj", "ek_sure_son"}
    assert "ÖRNEK" not in json.dumps(ekip, ensure_ascii=False) and CIHAZ_A not in json.dumps(ekip)
    yon = s.sozluk(yonetici=True)
    assert yon["lisans"]["musteri"].startswith("ÖRNEK") and yon["cihaz_kimligi"] == CIHAZ_A
    assert yon["cihaz_izinli"] is True and yon["ozellikler"]["satis"]["acik"] is True
    json.dumps(yon)                                        # JSON'a çevrilebilir


def test_ozellik_bayraklari_ve_kullanici_siniri(ozel, genel_pem):
    s = dogrula(imzali(ozel, ozellikler={"satis": True, "is_emri": False, "boss_eklentisi": True},
                       kullanici_siniri=10)[1], genel_pem)
    assert s.ozellik_acik("satis") and not s.ozellik_acik("is_emri") and s.ozellik_acik("boss_eklentisi")
    assert s.kullanici_eklenebilir(9) and not s.kullanici_eklenebilir(10)
    assert dogrula(imzali(ozel)[1], genel_pem).kullanici_eklenebilir(10 ** 6)   # sınır yoksa sınırsız


@pytest.mark.parametrize("degisiklik,parca", [
    (dict(bitis=dt.date(2026, 9, 1)), "bitis"),
    (dict(cihaz_siniri=0), "cihaz_siniri"),
    (dict(ek_sure_gun=91), "ek_sure_gun"),
    (dict(musteri=""), "musteri"),
    (dict(musteri="a\x00b"), "musteri"),
    (dict(izinli_cihazlar=["1234"]), "izinli_cihazlar"),
    (dict(ozellikler={"Büyük": True}), "ozellikler"),
    (dict(lisans_no="küçük"), "lisans_no"),
])
def test_icerik_denetimi(degisiklik, parca):
    with pytest.raises(L.LisansHatasi, match=parca):
        yuk(**degisiklik)


def test_icerik_denetimi_kesirli_sayi_ve_yeni_bicim():
    y = yuk()
    assert any("kesirli" in h for h in L.yuk_denetle(dict(y, cihaz_siniri=1.5)))
    assert any("daha yeni" in h for h in L.yuk_denetle(dict(y, surum=2)))
    with pytest.raises(L.LisansHatasi):
        L.kanonik({"x": 1.5})


def test_uygulama_modulu_imzalayamaz():
    """Uygulamayla giden modüllerde özel anahtar yükleyen/imzalayan kod yok (özel anahtar sahibinde kalır)."""
    for ad in ("lisans.py", "sunucu.py"):
        kaynak = (KOK / "lisans" / ad).read_text(encoding="utf-8")
        for yasak in ("Ed25519PrivateKey", "load_pem_private_key", "private_bytes", ".sign("):
            assert yasak not in kaynak, (ad, yasak)


def test_ay_ekle_ve_sure_sonu():
    assert U.sure_sonu(dt.date(2026, 10, 1), ay=12) == dt.date(2027, 9, 30)
    assert U.ay_ekle(dt.date(2027, 1, 31), 1) == dt.date(2027, 2, 28)
    assert U.sure_sonu(dt.date(2026, 10, 1), gun=30) == dt.date(2026, 10, 30)


# ============================================================================= komut satırı (uçtan uca)
def calistir(kasa: Path, *arg, parola: str | None = None, modul="lisans.uret") -> subprocess.CompletedProcess:
    ortam = {k: v for k, v in os.environ.items() if k not in ("SAHA_LISANS_PAROLA", "SAHA_LISANS_KASA")}
    ortam.update(PYTHONIOENCODING="utf-8", SAHA_LISANS_KASA=str(kasa))
    if parola:
        ortam["SAHA_LISANS_PAROLA"] = parola
    return subprocess.run([PYTHON, "-m", modul, *arg], cwd=KOK, env=ortam, capture_output=True,
                          text=True, encoding="utf-8", stdin=subprocess.DEVNULL, timeout=60)


def test_komut_satiri_uctan_uca(tmp_path):
    kasa = tmp_path / "kasa"
    depo_anahtari = KOK / "lisans" / "genel_anahtar.pem"
    once = depo_anahtari.read_bytes() if depo_anahtari.exists() else None
    r = calistir(kasa, "anahtar-olustur", "--parolasiz")
    assert r.returncode == 0, r.stderr
    ozel_ilk = (kasa / "ozel_anahtar.pem").read_bytes()
    assert b"PRIVATE KEY" in ozel_ilk and (kasa / "OKUBENI.txt").is_file()
    # --depoya-yaz verilmeden depodaki genel anahtara (denetimi açan dosyaya) dokunulmaz
    assert (depo_anahtari.read_bytes() if depo_anahtari.exists() else None) == once
    # ikinci kez: asla üzerine yazmaz
    r = calistir(kasa, "anahtar-olustur", "--parolasiz")
    assert r.returncode == 2 and "zaten bir anahtar var" in r.stderr
    assert (kasa / "ozel_anahtar.pem").read_bytes() == ozel_ilk

    r = calistir(kasa, "ver", "--musteri", "ÖRNEK BAYİ LTD. ŞTİ.", "--bayi-kodu", "00000.00000",
                 "--baslangic", "2026-10-01", "--ay", "12", "--cihaz", CIHAZ_A.lower(),
                 "--ozellik", "is_emri=hayir", "--kullanici-siniri", "25")
    assert r.returncode == 0, r.stderr
    no = re.search(r"Lisans verildi: (SL-\d{4}-[0-9A-F]{6})", r.stdout).group(1)
    assert "30 Eylül 2027" in r.stdout and "SAHA1." in r.stdout
    dosya = kasa / "lisanslar" / f"{no}.lisans.json"
    s = L.dogrula(dosya, kasa / "genel_anahtar.pem", cihaz=CIHAZ_A, bugun=dt.date(2026, 10, 2))
    assert s.durum == L.GECERLI and s.lisans["izinli_cihazlar"] == [CIHAZ_A]
    assert s.lisans["kullanici_siniri"] == 25 and not s.ozellik_acik("is_emri")

    r = calistir(kasa, "yenile", no, "--ay", "12", "--cihaz-ekle", CIHAZ_B)
    assert r.returncode == 0, r.stderr
    yeni_no = re.search(r"Lisans verildi: (SL-\d{4}-[0-9A-F]{6})", r.stdout).group(1)
    yeni = json.loads((kasa / "lisanslar" / f"{yeni_no}.lisans.json").read_text(encoding="utf-8"))["lisans"]
    assert yeni["bitis"] == "2028-09-30" and yeni["onceki_lisans_no"] == no      # kesintisiz uzatma
    assert yeni["izinli_cihazlar"] == [CIHAZ_A, CIHAZ_B] and yeni["cihaz_siniri"] == 2
    assert yeni["kullanici_siniri"] == 25 and yeni["ozellikler"]["is_emri"] is False

    r = calistir(kasa, "durdur", yeni_no, "--neden", "sözleşme bitti")
    assert r.returncode == 0 and "geri alınamaz" in r.stdout and "SALT OKUNUR" in r.stdout
    r = calistir(kasa, "liste")
    assert r.returncode == 0 and yeni_no in r.stdout and "YENİLENMEYECEK" in r.stdout
    assert no not in r.stdout                               # yenilenen eski lisans varsayılan olarak gizli
    assert no in calistir(kasa, "liste", "--hepsi").stdout

    r = calistir(kasa, "goster", str(dosya))
    assert r.returncode == 0 and "geçerli (anahtar" in r.stdout
    kurcali = tmp_path / "kurcali.json"
    kurcali.write_text(dosya.read_text(encoding="utf-8").replace("2027-09-30", "2099-09-30"), encoding="utf-8")
    r = calistir(kasa, "goster", str(kurcali))
    assert r.returncode == 1 and "GEÇERSİZ" in r.stdout

    r = calistir(kasa, "cihaz", modul="lisans.lisans")
    assert r.returncode == 0 and re.search(r"[0-9A-F]{4}(-[0-9A-F]{4}){4}", r.stdout)


def test_parolali_kasa(tmp_path):
    kasa = tmp_path / "kasa"
    r = calistir(kasa, "anahtar-olustur", parola="deneme-parolasi-123")
    assert r.returncode == 0, r.stderr
    assert b"ENCRYPTED PRIVATE KEY" in (kasa / "ozel_anahtar.pem").read_bytes()
    arg = ("ver", "--musteri", "ÖRNEK", "--bayi-kodu", "", "--gun", "30")
    r = calistir(kasa, *arg)                                # parola yok, pencere yok
    assert r.returncode == 2 and "parola" in r.stderr.lower()
    assert calistir(kasa, *arg, parola="yanlis-parola").returncode == 2
    assert calistir(kasa, *arg, parola="deneme-parolasi-123").returncode == 0


def test_komut_satiri_betik_olarak_da_calisir(tmp_path):
    ortam = dict(os.environ, PYTHONIOENCODING="utf-8", SAHA_LISANS_KASA=str(tmp_path / "k"))
    r = subprocess.run([PYTHON, str(KOK / "lisans" / "uret.py"), "liste"], cwd=tmp_path, env=ortam,
                       capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0 and "verilmiş lisans yok" in r.stdout
