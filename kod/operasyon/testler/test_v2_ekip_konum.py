"""BOSS ekip GPS konumları: hoşgörülü çözümleme (yanıt biçimi bilinmiyor), uçların yetkisi, kalıcılık."""
from __future__ import annotations

import datetime as dt

import pytest

from operasyon.v2 import boss, ekip_konum


@pytest.fixture(autouse=True)
def _temiz():
    ekip_konum.sifirla()
    yield
    ekip_konum.sifirla()


# 2026-10-01 07:25:00 UTC = 10:25 Türkiye (testlerin sabit "şimdi"si 10:30)
EPOCH_MS = int(dt.datetime(2026, 10, 1, 7, 25, tzinfo=dt.timezone.utc).timestamp() * 1000)


def _ozet(konumlar):
    return [(k["ekip_id"], k["ad"], k["lat"], k["lon"], k["zaman"] and k["zaman"].strftime("%H:%M")) for k in konumlar]


def test_duz_liste():
    k = ekip_konum.cozumle([{"teamId": 5, "teamName": "ALI EKIBI", "latitude": 40.19, "longitude": 29.06,
                             "lastUpdateDate": "2026-10-01T10:20:00"}])
    assert _ozet(k) == [("5", "ALI EKIBI", 40.19, 29.06, "10:20")]


def test_data_sarmali_ic_ice_konum_ve_epoch_ms():
    veri = {"returnCode": 0, "data": [
        {"user": {"userName": "AYILMAZ", "fullName": "Ayşe Yılmaz"}, "team": {"id": 9, "name": "EKIP B"},
         "location": {"lat": 40.21, "lng": 28.98, "locationDate": EPOCH_MS}},
        {"teamName": "EKIP C", "position": {"latitude": 40.3, "longitude": 29.1, "time": EPOCH_MS // 1000}},
    ]}
    assert _ozet(ekip_konum.cozumle(veri)) == [("9", "EKIP B", 40.21, 28.98, "10:25"),
                                              (None, "EKIP C", 40.3, 29.1, "10:25")]


def test_metin_koordinat_virgul_ve_iso_z():
    veri = {"content": {"items": [{"name": "VELI EKIBI", "enlem": "40,1834", "boylam": "29,0612",
                                   "date": "2026-10-01T07:00:00Z"}]}}
    assert _ozet(ekip_konum.cozumle(veri)) == [(None, "VELI EKIBI", 40.1834, 29.0612, "10:00")]


def test_gecersiz_ve_sifir_koordinat_atlanir_geojson_okunur():
    veri = [{"teamName": "A", "latitude": 0, "longitude": 0}, {"teamName": "B", "latitude": 200, "longitude": 29},
            {"teamName": "C", "lat": None, "lon": 29}, {"teamName": "D", "geometry": {"coordinates": [29.05, 40.2]}}]
    assert _ozet(ekip_konum.cozumle(veri)) == [(None, "D", 40.2, 29.05, None)]


def test_zaman_coz():
    assert ekip_konum.zaman_coz(EPOCH_MS) == dt.datetime(2026, 10, 1, 10, 25)
    assert ekip_konum.zaman_coz(str(EPOCH_MS)) == dt.datetime(2026, 10, 1, 10, 25)
    assert ekip_konum.zaman_coz("01.10.2026 09:15") == dt.datetime(2026, 10, 1, 9, 15)
    assert ekip_konum.zaman_coz("2026-10-01T09:15:00+03:00") == dt.datetime(2026, 10, 1, 9, 15)
    assert ekip_konum.zaman_coz("yarın") is None and ekip_konum.zaman_coz(12) is None


def test_uclar_yetki_kalicilik_ve_eskiyi_ezmeme(istemci, v2db, conn, jeton, kisi):
    ek = {"X-Eslesme-Kodu": boss.eslesme_kodu()}
    op = jeton(kisi["operasyon"])
    # henüz yakalama yok
    j = istemci.get("/api/isler/ekip-konumlari", headers=op).json()
    assert j == {"ekipler": [], "kaynak_goruldu": False, "son_alim": None, "son_bulunan": None}
    # yetki: eşleme kodu yok / yanlış → 401; jetonsuz GET → 401
    assert istemci.post("/api/boss/ekip-konum", json={"veri": []}).status_code == 401
    assert istemci.post("/api/boss/ekip-konum", json={"veri": []}, headers={"X-Eslesme-Kodu": "yanlis"}).status_code == 401
    assert istemci.get("/api/isler/ekip-konumlari").status_code == 401

    govde = {"kaynak": "komut", "yol": "/boss-gateway-service/account-service/api/v1/user/location/TECH",
             "veri": {"data": [{"teamId": 5, "teamName": "ALI EKIBI", "location": {"latitude": "40.19", "longitude": "29.06",
                                                                                 "locationDate": EPOCH_MS}},
                               {"teamId": 6, "teamName": "ESKI", "latitude": 40.0, "longitude": 29.0,
                                "lastUpdate": "2026-09-27 08:00:00"}]}}
    r = istemci.post("/api/boss/ekip-konum", json=govde, headers=ek)
    assert r.status_code == 200, r.text
    assert r.json() == {"bulunan": 2, "guncellenen": 2, "toplam": 2}
    j = istemci.get("/api/isler/ekip-konumlari", headers=op).json()
    assert j["kaynak_goruldu"] is True and j["son_alim"] == "2026-10-01 10:30:00"
    assert [(e["ekip"], e["ad"], e["lat"], e["lon"], e["zaman"], e["yas_dk"]) for e in j["ekipler"]] == \
        [("5", "ALI EKIBI", 40.19, 29.06, "2026-10-01 10:25:00", 5)], "72 saatten eski konum gösterilmez"

    # sayfanın daha eski yanıtı yeni konumu ezmez; daha yenisi ezer
    eski = {"kaynak": "sayfa", "veri": [{"teamId": 5, "teamName": "ALI EKIBI", "latitude": 41, "longitude": 30,
                                         "lastUpdate": "2026-10-01 09:00:00"}]}
    assert istemci.post("/api/boss/ekip-konum", json=eski, headers=ek).json()["guncellenen"] == 0
    yeni = {"kaynak": "sayfa", "veri": [{"teamId": 5, "teamName": "ALI EKIBI", "latitude": 40.2, "longitude": 29.07,
                                         "lastUpdate": "2026-10-01 10:29:00"}]}
    assert istemci.post("/api/boss/ekip-konum", json=yeni, headers=ek).json()["guncellenen"] == 1

    # yalnız hata (kanca 'konum_yok'): veri ve kaynak bilgisi değişmez
    h = istemci.post("/api/boss/ekip-konum", json={"kaynak": "komut", "hata": "konum_yok"}, headers=ek).json()
    assert h["bulunan"] == 0 and h["hata"] == "konum_yok"

    # kalıcı: bellek silinince veritabanından gelir
    assert conn.execute("SELECT COUNT(*) FROM boss_ekip_konum").fetchone()[0] == 2
    ekip_konum.sifirla()
    j = istemci.get("/api/isler/ekip-konumlari", headers=op).json()
    assert j["kaynak_goruldu"] is True
    assert [(e["ad"], e["lat"], e["yas_dk"]) for e in j["ekipler"]] == [("ALI EKIBI", 40.2, 1)]


def test_bos_yanit_kaynak_goruldu_sayilir(istemci, v2db, jeton, kisi):
    ek = {"X-Eslesme-Kodu": boss.eslesme_kodu()}
    assert istemci.post("/api/boss/ekip-konum", json={"kaynak": "sayfa", "veri": {"data": []}}, headers=ek).json() == \
        {"bulunan": 0, "guncellenen": 0, "toplam": 0}
    j = istemci.get("/api/isler/ekip-konumlari", headers=jeton(kisi["operasyon"])).json()
    assert j["kaynak_goruldu"] is True and j["son_bulunan"] == 0 and j["ekipler"] == []
