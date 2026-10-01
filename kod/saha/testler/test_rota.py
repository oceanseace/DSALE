"""Öncelik puanı ve rota kurucu: doğruluk, belirlenimcilik, hız."""
from __future__ import annotations

import datetime as dt
import time

from saha import ayarlar, rota

BUGUN = dt.date(2026, 9, 21)


# ----------------------------------------------------------------------------- çarpanlar
def test_yeni_site_carpani():
    assert rota.yeni_site_carpani((BUGUN - dt.timedelta(days=30)).isoformat(), BUGUN) == 1.6
    assert rota.yeni_site_carpani((BUGUN - dt.timedelta(days=400)).isoformat(), BUGUN) == 1.3
    assert rota.yeni_site_carpani((BUGUN - dt.timedelta(days=900)).isoformat(), BUGUN) == 1.0
    assert rota.yeni_site_carpani(None, BUGUN) == 1.0
    assert rota.yeni_site_carpani("", BUGUN) == 1.0


def test_tekrar_carpani():
    assert rota.tekrar_carpani("tekrar_gel", BUGUN.isoformat(), BUGUN) == 1.4
    assert rota.tekrar_carpani("tekrar_gel", (BUGUN + dt.timedelta(days=5)).isoformat(), BUGUN) == 1.0
    assert rota.tekrar_carpani("girilemedi", None, BUGUN) == 0.4
    assert rota.tekrar_carpani("altyapi_sorunu", None, BUGUN) == 0.2
    assert rota.tekrar_carpani("bekliyor", None, BUGUN) == 1.0


def test_doygunluk_carpani():
    assert rota.doygunluk_carpani(80, 100) == 0.7      # %80 doygun
    assert rota.doygunluk_carpani(10, 100) == 1.2      # %10 bakir
    assert rota.doygunluk_carpani(45, 100) == 1.0
    assert rota.doygunluk_carpani(0, 0) == 1.0


def test_oncelik_carpanlarin_carpimi():
    b = {"firsat": 20, "sales_ready": (BUGUN - dt.timedelta(days=10)).isoformat(),
         "durum": "bekliyor", "tekrar_tarih": None, "aktif_res": 5, "res_hp": 100}
    assert rota.oncelik_puani(b, BUGUN) == 20 * 1.6 * 1.0 * 1.2


def test_uygun_mu_soguma():
    taze = (BUGUN - dt.timedelta(days=5)).isoformat()
    eski = (BUGUN - dt.timedelta(days=40)).isoformat()
    assert rota.uygun_mu({"durum": "bekliyor"}, BUGUN)
    assert not rota.uygun_mu({"durum": "planli"}, BUGUN)
    assert not rota.uygun_mu({"durum": "ziyaret_edildi", "son_ziyaret": taze}, BUGUN)
    assert rota.uygun_mu({"durum": "ziyaret_edildi", "son_ziyaret": eski}, BUGUN)
    # tekrar_gel soğuma kuralından muaf
    assert rota.uygun_mu({"durum": "tekrar_gel", "son_ziyaret": taze, "tekrar_tarih": BUGUN.isoformat()}, BUGUN)
    assert not rota.uygun_mu(
        {"durum": "tekrar_gel", "son_ziyaret": taze,
         "tekrar_tarih": (BUGUN + dt.timedelta(days=3)).isoformat()}, BUGUN)


# ----------------------------------------------------------------------------- tur
def test_rota_25_bina_ve_sirali(conn):
    r = rota.gunluk_rota(conn, 3, None, 25)
    # Site bütünlüğü için liste birkaç bina taşabilir: bir siteye girip bir
    # bloğunu bırakıp gitmek sahada en çok vakit kaybettiren şey.
    assert 25 <= len(r) <= 25 + ayarlar.LISTE_TASMA
    assert [b["sira"] for b in r] == list(range(1, len(r) + 1))
    assert all(b["bolge"] == 3 for b in r)
    assert all(isinstance(b["mesafe_m"], int) and b["mesafe_m"] >= 0 for b in r)
    assert r[0]["mesafe_m"] > 0          # ofisten ilk binaya mesafe


def test_rota_belirlenimci(conn):
    a = rota.gunluk_rota(conn, 5, None, 25)
    b = rota.gunluk_rota(conn, 5, None, 25)
    assert [x["bina_serial"] for x in a] == [x["bina_serial"] for x in b]
    assert [x["mesafe_m"] for x in a] == [x["mesafe_m"] for x in b]


def test_rota_hizli(conn):
    baslangic = time.perf_counter()
    for bolge in range(1, 9):
        assert 25 <= len(rota.gunluk_rota(conn, bolge, None, 25)) <= 25 + ayarlar.LISTE_TASMA
    sure = time.perf_counter() - baslangic
    assert sure < 8 * 0.5, f"8 bölge rotası {sure:.2f} sn sürdü"
    # tek bir rota saniyenin çok altında olmalı
    tek = time.perf_counter()
    rota.gunluk_rota(conn, 7, None, 25)
    assert time.perf_counter() - tek < 0.5


def test_ayni_site_pes_pese(conn):
    r = rota.gunluk_rota(conn, 2, None, 40)
    gorulen: dict[str, list[int]] = {}
    for b in r:
        grup = b.get("site_grup") or b["bina_serial"]
        gorulen.setdefault(grup, []).append(b["sira"])
    for grup, siralar in gorulen.items():
        assert siralar == list(range(siralar[0], siralar[0] + len(siralar))), f"{grup} bölünmüş"


def test_iki_opt_en_yakin_komsudan_kotu_degil(conn):
    """2-opt, en yakın komşunun bulduğu turu asla uzatmamalı."""
    bas = (ayarlar.OFIS["lat"], ayarlar.OFIS["lon"])
    for bolge in (2, 4, 7):
        adaylar = rota.adaylari_getir(conn, bolge, havuz=200)
        gruplar = rota._grupla(adaylar[:60])
        merkezler = [rota._merkez(u) for u in gruplar.values()]
        ham = rota._en_yakin_komsu(merkezler, bas)
        iyilesmis = rota._iki_opt(merkezler, bas, list(ham))

        def maliyet(duzen):
            toplam, konum = 0.0, bas
            for i in duzen:
                toplam += rota.mesafe_m(*konum, *merkezler[i])
                konum = merkezler[i]
            return toplam

        assert maliyet(iyilesmis) <= maliyet(ham) + 1e-6
        assert sorted(iyilesmis) == sorted(ham)   # hiçbir durak kaybolmadı

    tur = rota.tur_kur(rota.adaylari_getir(conn, 2, havuz=200), bas, 25)
    assert rota.toplam_mesafe_m(tur) > 0


def test_haric_tutulan_binalar_gelmez(conn):
    ilk = rota.gunluk_rota(conn, 6, None, 10)
    haric = {b["bina_serial"] for b in ilk}
    ikinci = rota.gunluk_rota(conn, 6, None, 10, haric=haric)
    assert haric.isdisjoint({b["bina_serial"] for b in ikinci})


def test_adaylar_oncelik_sirali(conn):
    adaylar = rota.adaylari_getir(conn, 1, havuz=50)
    puanlar = [a["oncelik"] for a in adaylar]
    assert puanlar == sorted(puanlar, reverse=True)
    assert all(p > 0 for p in puanlar)


def test_mesafe_hesabi():
    # Bursa ofis ile yaklaşık 1 km kuzeyi
    d = rota.mesafe_m(40.2204, 28.9535, 40.2294, 28.9535)
    assert 980 < d < 1020
    assert rota.mesafe_m(40.0, 29.0, 40.0, 29.0) == 0.0
