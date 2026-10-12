"""BOSS raporu hazırlama: filtre, mahalle çözümü, öbek, bölme, API.

Adresler uydurmadır (gerçek müşteri verisi yok); mahalle adları gerçek listeden.
    .venv/Scripts/python -m pytest operasyon/testler -q
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from operasyon import is_emri as ie
from operasyon import yakinlik


@pytest.fixture(scope="module")
def szl():
    return ie.sozluk()


def rapor(satirlar: list[tuple]) -> pd.DataFrame:
    """(task, adres, il, ilçe[, lokasyon]) → BOSS sütun düzeninde tablo."""
    kol = ["Bayi", "Müşteri No", "Müşteri Adı", "Task No", "Task Adı", "Ekip", "Adres", "H", "I", "J", "K", "L",
           "İl", "İlçe", "Task Başlangıç Tarihi", "Task Durumu", "Lokasyon"]
    out = []
    for n, s in enumerate(satirlar):
        task, adres, il, ilce, *lok = s
        out.append(["DEHANET", str(n), "X", f"T{n}", task, "EKIP", adres, "", "", "", "", "", il, ilce,
                    "2026-09-29 10:00", "Açık", lok[0] if lok else None])
    return pd.DataFrame(out, columns=kol)


# ---------------------------------------------------------------- 1) filtre
@pytest.mark.parametrize("ad,beklenen", [
    ("TV+ Kurulum", "KURULUM"), ("Fiber Kurulum(Dönüşüm)", "KURULUM"), ("KURULUM VE CİHAZ GÖNDERİM", "KURULUM"),
    ("Kurulum ve Cihaz Gönderim", "KURULUM"), ("2.Donanım", "2 DONANIM"), ("2. DONANIM", "2 DONANIM"),
    ("2 donanım", "2 DONANIM"), ("İkinci Donanım Kurulum", "KURULUM"),
    ("Bağlantı Problemi", None), ("Kanal Şikayeti", None), ("TV+ Arıza", None), ("Modem Değişikliği", None),
    ("12.Donanım Kontrol", None),
])
def test_cikarma_kurali(ad, beklenen):
    assert ie.cikarilacak_mi(ad) == beklenen


# ---------------------------------------------------------------- 2) mahalle
@pytest.mark.parametrize("adres,il,ilce,beklenen", [
    ("CEYLAN TEST SİT. B BLK. Görükle Mh. Gülveren Cd. No:1B D:22 Nilüfer", "Bursa", "Nilüfer", "Görükle"),
    ("DENEME APT. İhsaniye Mah. Dörtyıldız Sk. No:1A D:11 Nilüfer Bursa", "Bursa", "Nilüfer", "İhsaniye"),
    ("İDEAL SİT. A BLOK YÜZÜNCÜYILMH. 517. SK. , -/DAİRE : 7, NİLÜFER", "Bursa", "Nilüfer", "Yüzüncüyıl"),
    ("KAYAPA TOKİ (426 ADA) SİT. 8G BLK. KAYAPA TOKİ 8G 30 Ağustos Zafer Mh. Fatih Cd. No:1", "Bursa", "Nilüfer",
     "30 Ağustos Zafer"),
    ("HİLAL SİT. A BLOK HİLAL A Siteler Mh. Kanuni Cd. HİLAL A Blok No:94 D:7 Yıldırım", "Bursa", "Yıldırım",
     "Siteler"),
    ("ABC APT. Dumlupınar Mah. Selçuk Sk. No:5 D:21 Nilüfer Bursa", "Bursa", "Nilüfer", "Dumlupınar"),
    # aynı ad Osmangazi'de: ilçe N sütunundan → Osmangazi'nin Dumlupınar'ı
    ("ABC APT. Dumlupınar Mah. 5. Sk. No:3 Osmangazi Bursa", "Bursa", "Osmangazi", "Demirtaş Dumlupınar"),
    ("CUMHURİYET MAH.1211.SOK. , -/APT.NO.80, DEMİRTAŞ OSMANGAZİ BURSA", "Bursa", "Osmangazi",
     "Demirtaş Cumhuriyet"),
    ("Özden Bbk.Mah.(Kadıköy) Mah. Fetih 7. Sk. No:14 D:7 Merkez Yalova", "Yalova", "Merkez", "Özden"),
    ("Samanlı (Samanlı) Mh. Yeşilyurt Sk. No:10 D:44 Merkez", "Yalova", "Merkez", "Samanlı"),
    ("TOKİ ABA10-A2 ADNAN MENDERESMH. ŞEHİT CD. No:3", "Yalova", "Merkez", "Adnan Menderes"),
    ("Sırabademler Mah. 82. Sk. No:42 D:5 Karacabey Bursa", "Bursa", "Karacabey", "Sırabademler"),
    ("YENİ KARAMAN DEĞİRMEN SK , -/NO:16, OSMANGAZİ", "Bursa", "Osmangazi", "Yenikaraman"),
])
def test_mahalle_adresten(szl, adres, il, ilce, beklenen):
    assert ie.mahalle_coz(szl, adres, il, ilce).ad == beklenen


def test_ayni_ad_farkli_ilce_ayri_obek():
    o = ie.Obekler()
    o.ata("Nilüfer Dumlupınar", ["Bursa/Nilüfer/Dumlupınar"])
    assert o.bul("Bursa", "Nilüfer", "Dumlupınar") == "Nilüfer Dumlupınar"
    assert o.bul("Bursa", "Nilüfer", "DUMLUPINAR") == "Nilüfer Dumlupınar"
    assert o.bul("Bursa", "Osmangazi", "Dumlupınar") is None
    o.ata("Mudanya", ["Bursa/Mudanya/*"])          # ilçenin tamamı
    assert o.bul("Bursa", "Mudanya", "Güzelyalı") == "Mudanya"
    o.ata("Görükle", ["Nilüfer/Görükle"])          # il yazmadan
    assert o.bul("Bursa", "Nilüfer", "Görükle") == "Görükle"


def test_obek_tasima_ve_ad(tmp_path):
    o = ie.Obekler()
    o.ata("A", ["Bursa/Nilüfer/Görükle", "Bursa/Nilüfer/Dumlupınar"])
    o.ata("B", ["Bursa/Nilüfer/Dumlupınar"])       # A'dan B'ye taşınır
    assert o.bul("Bursa", "Nilüfer", "Dumlupınar") == "B" and o.bul("Bursa", "Nilüfer", "Görükle") == "A"
    o.yeniden_adlandir("B", "A")                   # aynı ada birleşir
    assert [t["ad"] for t in o.tanimlar] == ["A"] and len(o.tanimlar[0]["mahalleler"]) == 2
    o.cikar(["Bursa/Nilüfer/Görükle"])
    assert o.bul("Bursa", "Nilüfer", "Görükle") is None
    yol = tmp_path / "obek.json"
    o.kaydet(yol)
    assert ie.Obekler.yukle(yol).bul("Bursa", "Nilüfer", "Dumlupınar") == "A"


# ---------------------------------------------------------------- 3) uçtan uca hazırlama
def test_hazirla_uctan_uca(szl):
    df = rapor([
        ("TV+ Kurulum", "X APT. Görükle Mh. No:1 Nilüfer", "Bursa", "Nilüfer"),
        ("2.Donanım", "X APT. Görükle Mh. No:1 Nilüfer", "Bursa", "Nilüfer"),
        ("Bağlantı Problemi", "X APT. Görükle Mh. No:1 Nilüfer", "Bursa", "Nilüfer"),
        ("Kanal Şikayeti", "Y APT. Dumlupınar Mah. No:2 Osmangazi", "Bursa", "Osmangazi"),
        ("TV+ Arıza", "Çiftlik Mah. Duman Sk. No:10 D:4 Çiftlikköy Yalova", "Yalova", "Çiftlikköy"),
        ("Modem Değişikliği", "ÇİFTLİK KAHRAMAN SK. , -/9 1, ÇİFTLİKKÖY", "Yalova", "Çiftlikköy"),
    ])
    o = ie.Obekler()
    o.ata("Görükle", ["Bursa/Nilüfer/Görükle"])
    s = ie.hazirla(df, o, szl)
    assert s.ozet["cikarilan"] == 2 and s.ozet["kalan"] == 4
    assert set(s.cikarilan["Çıkarılma Nedeni"]) == {"KURULUM", "2 DONANIM"}
    d = s.isler
    assert list(d.columns[list(d.columns).index("İlçe") + 1:][:2]) == ["Mahalle", "Öbek"]   # N'nin sağında
    assert d["Mahalle"].tolist() == ["Görükle", "Demirtaş Dumlupınar", "Çiftlik", "Çiftlik"]
    assert d["Öbek"].tolist() == ["Görükle", "", "", ""]
    assert d["Enlem"].notna().all()                                   # hepsinin en az kaba konumu var
    assert d.iloc[3]["Mahalle Kaynağı"] == "adres-isaretsiz"          # aynı rapordan öğrenildi


def test_lokasyon_binaya_baglar(szl):
    m = szl.bina
    r = m[(m["ilce"] == "Nilüfer") & m["location_id"].notna()].iloc[0]
    df = rapor([("Bağlantı Problemi", "ADSIZ ADRES", "Bursa", "Nilüfer", r["location_id"])])
    s = ie.hazirla(df, ie.Obekler(), szl)
    x = s.isler.iloc[0]
    assert x["Konum Kaynağı"] == "bina (Lokasyon)" and x["Bina Serial"] == r["bina_serial"]
    assert x["Mahalle"] == ie.mahalle_eki_sil(r["mahalle"])


def test_hiz_bin_is(szl):
    adresler = ["X APT. Görükle Mh. No:1 Nilüfer", "Y SİT. A BLK. Siteler Mh. No:3 Yıldırım",
                "Çiftlik Mah. Duman Sk. No:10 Çiftlikköy", "Z APT. Hamitler Mah. No:4 Osmangazi"]
    ilceler = [("Bursa", "Nilüfer"), ("Bursa", "Yıldırım"), ("Yalova", "Çiftlikköy"), ("Bursa", "Osmangazi")]
    df = rapor([("Bağlantı Problemi", adresler[i % 4], *ilceler[i % 4]) for i in range(1000)])
    s = ie.hazirla(df, ie.Obekler(), szl)
    assert s.ozet["mahalle_bulunan"] == 1000
    assert s.sure_sn < 3.0


def test_rapor_sayfasi_bulunur(tmp_path):
    yol = tmp_path / "r.xlsx"
    with pd.ExcelWriter(yol) as w:
        pd.DataFrame({"Satır Etiketleri": ["A"], "Say": [1]}).to_excel(w, sheet_name="Sayfa1", index=False)
        rapor([("Bağlantı Problemi", "X APT. Görükle Mh.", "Bursa", "Nilüfer")]).to_excel(
            w, sheet_name="Task Detail Report", index=False, startrow=2)
    df = ie.raporu_oku(yol)
    assert len(df) == 1 and df["Task Adı"].iloc[0] == "Bağlantı Problemi"


# ---------------------------------------------------------------- 4) yakınlık
def test_mesafe_ve_dengeli_bolme():
    assert yakinlik.mesafe_km(40.0, 29.0, 40.0, 29.0) == pytest.approx(0)
    assert yakinlik.mesafe_km(40.0, 29.0, 41.0, 29.0) == pytest.approx(111.2, abs=0.3)
    rng = np.random.default_rng(1)
    lat = np.r_[40.20 + rng.normal(0, .004, 30), 40.25 + rng.normal(0, .004, 30)]
    lon = np.r_[28.90 + rng.normal(0, .004, 30), 29.05 + rng.normal(0, .004, 30)]
    et = yakinlik.dengeli_bol(lat, lon, 2)
    assert sorted(np.bincount(et)[1:]) == [30, 30]
    assert len(set(et[:30])) == 1 and len(set(et[30:])) == 1     # iki küme ayrı parçalarda
    # aynı gruptakiler bölünmez; konumsuz nokta 0 alır
    grup = np.r_[["a"] * 5, np.arange(55).astype(str)]
    lat2 = lat.copy(); lat2[-1] = np.nan
    et2 = yakinlik.dengeli_bol(lat2, lon, 3, grup=grup)
    assert len(set(et2[:5])) == 1 and et2[-1] == 0


# ---------------------------------------------------------------- 6) Location Id önce (kullanıcı kuralı, 30.09)
def test_lokasyon_onemap_mahallesi_esas(szl):
    """Raporda Location Id varsa OneMap'teki binanın mahallesi esastır; kontrol listesine düşmez."""
    m = szl.bina
    r = m[(m["ilce"] == "Nilüfer") & m["location_id"].notna() & (m["mahalle"] != "Görükle")].iloc[0]
    df = rapor([("Bağlantı Problemi", "X APT. Görükle Mh. No:1 Nilüfer", "Bursa", "Nilüfer", r["location_id"])])
    x = ie.hazirla(df, ie.Obekler(), szl).isler.iloc[0]
    assert x["Mahalle"] == ie.mahalle_eki_sil(r["mahalle"]) and x["Mahalle Kaynağı"] == "lokasyon"
    assert x["Kontrol Notu"] == "" and "Görükle" in x["Bilgi"]


def test_kontrol_yalniz_gercek_sorunlar(szl):
    df = rapor([
        ("Bağlantı Problemi", "X APT. Konak Mah. No:1 Karşıyaka İzmir", "İzmir", "Karşıyaka"),   # il bölge dışı
        ("Bağlantı Problemi", "ADRES YOK", "Bursa", "Nilüfer"),                                  # mahalle yok
        ("Bağlantı Problemi", "Y APT. Görükle Mh. No:2 Nilüfer", "Bursa", "Nilüfer"),           # sorunsuz
        ("Bağlantı Problemi", "Y APT. Dumlupınar Mah. No:2 Osmangazi", "Bursa", "Osmangazi"),   # benzer ad: sorunsuz
    ])
    s = ie.hazirla(df, ie.Obekler(), szl)
    notlar = s.isler["Kontrol Notu"].tolist()
    assert "il bölge dışı" in notlar[0]
    assert "mahalle bulunamadı" in notlar[1]
    assert notlar[2] == "" and notlar[3] == ""
