"""RUT (günlük ekip rotası): rota is_emri'den kendiliğinden kurulur, elle hücreler (tarih, task no) başına saklanır,
özet mesai içi/dışı ve iptal-erteleme sayar; izinler ve müşteri alanı kırpması. Adlar/numaralar uydurma."""
from __future__ import annotations

import pytest

from operasyon.v2 import boss, ek_sema, rut, rut_api

from .conftest import uygulama

GUN = "2026-10-01"


@pytest.fixture
def istemci(v2db):
    """conftest'in küçük uygulaması + RUT uçları (gerçek sunucuda ``saha/api.py _v2_bagla`` bağlar)."""
    from fastapi.testclient import TestClient
    from saha import yetki
    app = uygulama()
    for r in rut_api.yonlendiriciler(yetki.Bagimliliklar()):
        app.include_router(r)
    with TestClient(app) as c:
        yield c


def test_sunucu_rut_uclarini_baglar():
    from saha import api, yetki

    def gez(liste):            # dahil edilen yönlendiriciler iç içe durabilir (test_yetki_matrisi.rotalar gibi)
        for r in liste:
            yield getattr(r, "path", None)
            alt = getattr(r, "original_router", None)
            if alt is not None:
                yield from gez(alt.routes)
    yollar = set(gez(api.uygulama.routes))
    assert {"/api/rut", "/api/rut/hucre", "/api/rut/ayar"} <= yollar
    assert all(yetki.ROTA_IZNI.get(a) == e for a, e in rut_api.ROTA_IZNI.items())


def _gorev(i: int, *, ekip="EKIP ALFA", randevu=("2026-10-01 10:00:00", "2026-10-01 12:00:00"),
           task="Fiber Kurulum", ham=None, **ek):
    no = f"{400000000 + i}"
    g = {"task_no": no, "task_adi": task, "durum": "Randevulu", "musteri_no": f"9{no[-8:]}", "musteri_adi": "Deneme",
         "adres": f"DENEME APT. Görükle Mh. Test Sk. No:{i} Nilüfer", "il": "Bursa", "ilce": "Nilüfer",
         "acilis": "2026-09-30 09:00:00", "satis_kanali": "GLOBAL CC", "ekip": ekip}
    if randevu:
        g["randevu_bas"], g["randevu_bit"] = randevu
    if ham is not None:
        g["ham"] = ham
    g.update(ek)
    return g


def _esitle(istemci, gorevler):
    r = istemci.post("/api/boss/esitle", headers={"X-Eslesme-Kodu": boss.eslesme_kodu()},
                     json={"gorevler": gorevler, "tam": False})
    assert r.status_code == 200, r.text


def _gun(istemci, h, tarih=GUN):
    r = istemci.get("/api/rut", headers=h, params={"tarih": tarih})
    assert r.status_code == 200, r.text
    return r.json()


def _yaz(istemci, h, no, alan, deger, tarih=GUN):
    return istemci.put("/api/rut/hucre", headers=h,
                       json={"tarih": tarih, "task_no": f"{400000000 + no}", "alan": alan, "deger": deger})


def test_saat_ve_tur_yardimcilari():
    assert rut.saat_duzelt("9.30") == "09:30"
    assert rut.saat_duzelt("0930") == "09:30"
    assert rut.saat_duzelt(" ") is None
    assert rut.is_turu("Fiber Kurulum") == "kurulum"
    assert rut.is_turu("TV+ Kurulum") == "yan"
    assert rut.is_turu("Modem Değişikliği") == "yan"
    assert rut.durum_sinifi("kuruldu") == "tamam"
    assert rut.durum_sinifi("İPTAL") == "iptal"
    assert rut.durum_sinifi("ERTELEME") == "erteleme"


def test_rota_ekiplere_ayrilir_ve_saate_gore_siralanir(istemci, v2db, jeton, kisi):
    _esitle(istemci, [
        _gorev(1, randevu=("2026-10-01 14:00:00", "2026-10-01 16:00:00")),
        _gorev(2, randevu=("2026-10-01 09:00:00", "2026-10-01 11:00:00"),
               ham={"crmTaskId": "400000002", "campaignName": "DENEME KAMPANYA", "speed": "100 Mbps"}),
        _gorev(3, ekip="EKIP BETA"),
        _gorev(4, randevu=("2026-10-02 10:00:00", "2026-10-02 12:00:00")),     # başka gün
    ])
    d = _gun(istemci, jeton(kisi["operasyon"]))
    assert d["tarih"] == GUN and d["adet"] == 3
    adlar = [e["ad"] for e in d["ekipler"]]
    assert adlar == ["EKIP ALFA", "EKIP BETA"]
    alfa = d["ekipler"][0]["satirlar"]
    assert [s["task_no"] for s in alfa] == ["400000002", "400000001"]
    assert alfa[0]["randevu"] == "09:00–11:00"
    assert alfa[0]["kampanya"] == "DENEME KAMPANYA" and alfa[0]["hiz"] == "100 Mbps"
    assert alfa[0]["sef"] == "EKIP ALFA" and alfa[0]["adi_soyadi"] == "Deneme"
    assert [o["sef"] for o in d["ozet"]] == ["EKIP ALFA", "EKIP BETA"]
    assert [c["baslik"] for c in d["sutunlar"]][:6] == ["RANDEVU", "GİRİŞ", "ÇIKIŞ", "ŞEF", "YARDIMCI", "TASK NO"]


def test_ekip_boss_atamasindan_gelir(istemci, v2db, conn, jeton, kisi):
    """BOSS'ta atanmış iş BOSS ekibinde görünür (uygulamada başka kişi atanmış olsa da); BOSS'ta ekibi yoksa
    uygulamada atanan kişi; ikisi de yoksa "Ekipsiz". Rota yalnız is_emri/BOSS verisinden kurulur."""
    _esitle(istemci, [_gorev(1), _gorev(2, ekip=None), _gorev(3, ekip=None)])
    conn.execute("UPDATE is_emri SET atanan_id=? WHERE boss_task_no IN ('400000001','400000002')", (kisi["teknik1"],))
    conn.commit()
    ad = conn.execute("SELECT ad FROM kullanici WHERE id=?", (kisi["teknik1"],)).fetchone()[0]
    d = _gun(istemci, jeton(kisi["operasyon"]))
    gruplar = {e["ad"]: [s["task_no"] for s in e["satirlar"]] for e in d["ekipler"]}
    assert gruplar == {"EKIP ALFA": ["400000001"], ad: ["400000002"], rut.EKIPSIZ: ["400000003"]}
    assert all(s["sef"] == e["ad"] for e in d["ekipler"] for s in e["satirlar"])


def test_elle_hucreler_saklanir_ve_ozet_hesaplanir(istemci, v2db, conn, jeton, kisi):
    _esitle(istemci, [_gorev(1, randevu=("2026-10-01 09:00:00", "2026-10-01 10:00:00")),
                      _gorev(2, randevu=("2026-10-01 17:00:00", "2026-10-01 18:00:00")),
                      _gorev(3, randevu=("2026-10-01 11:00:00", "2026-10-01 12:00:00")),
                      _gorev(4, task="TV+ Kurulum", randevu=("2026-10-01 13:00:00", "2026-10-01 14:00:00"))])
    h = jeton(kisi["operasyon"])
    assert not ek_sema.var_mi(conn, "rut_satir")
    for no, giris, cikis, durum in ((1, "8.45", "10:05", "kuruldu"), (2, "17:30", "18:40", "KURULDU"),
                                    (3, "11:00", "11:10", "İPTAL"), (4, "13:00", "14:00", "KURULDU")):
        for alan, deger in (("giris", giris), ("cikis", cikis), ("durum", durum)):
            r = _yaz(istemci, h, no, alan, deger)
            assert r.status_code == 200, r.text
    assert _yaz(istemci, h, 1, "yardimci", "Deneme Yardımcı").status_code == 200
    assert ek_sema.var_mi(conn, "rut_satir")

    d = _gun(istemci, h)
    s1 = d["ekipler"][0]["satirlar"][0]
    assert (s1["giris"], s1["cikis"], s1["durum"], s1["yardimci"]) == ("08:45", "10:05", "KURULDU", "Deneme Yardımcı")
    assert set(s1["elle"]) == {"giris", "cikis", "durum", "yardimci"}
    o = d["ozet"][0]
    assert (o["ilk_giris"], o["son_cikis"], o["mesai_dk"]) == ("08:45", "18:40", 18 * 60 + 40 - (8 * 60 + 45))
    assert (o["mesai_ici"], o["mesai_disi"], o["iptal_erteleme"], o["yan_is"]) == (1, 1, 1, 1)
    assert o["yardimci"] == "Deneme Yardımcı"

    # mesai ayarı: 19:00'a uzayınca 18:40 çıkışı mesai içi olur
    r = istemci.put("/api/rut/ayar", headers=h, json={"mesai_bas": "08:00", "mesai_bit": "19:00"})
    assert r.status_code == 200 and r.json()["mesai"] == {"bas": "08:00", "bit": "19:00"}
    o = _gun(istemci, h)["ozet"][0]
    assert (o["mesai_ici"], o["mesai_disi"]) == (2, 0)

    # boş değer öneriye döner; elle listesinden düşer
    assert _yaz(istemci, h, 1, "yardimci", "").status_code == 200
    s1 = _gun(istemci, h)["ekipler"][0]["satirlar"][0]
    assert s1["yardimci"] is None and "yardimci" not in s1["elle"]


def test_gecersiz_girdiler(istemci, v2db, jeton, kisi):
    _esitle(istemci, [_gorev(1)])
    h = jeton(kisi["operasyon"])
    assert _yaz(istemci, h, 1, "giris", "25:00").status_code == 422
    assert _yaz(istemci, h, 1, "adres", "x").status_code == 422           # elle değişmez sütun
    assert _yaz(istemci, h, 99, "durum", "KURULDU").status_code == 404
    assert istemci.get("/api/rut", headers=h, params={"tarih": "01.10.2026"}).status_code == 422
    assert istemci.put("/api/rut/ayar", headers=h, json={"mesai_bas": "18:00", "mesai_bit": "08:00"}).status_code == 422


def test_ertelenen_is_eski_gunun_rotasinda_kalir(istemci, v2db, conn, jeton, kisi):
    _esitle(istemci, [_gorev(1)])
    h = jeton(kisi["operasyon"])
    assert _yaz(istemci, h, 1, "durum", "ERTELEME").status_code == 200
    # randevu 3 Ekim'e alındı (uygulamadaki randevu BOSS'takinden önce gelir)
    conn.execute("UPDATE is_emri SET randevu_bas='2026-10-03 10:00:00', randevu_bit='2026-10-03 12:00:00' "
                 "WHERE boss_task_no='400000001'")
    conn.commit()
    d = _gun(istemci, h)
    assert [s["task_no"] for e in d["ekipler"] for s in e["satirlar"]] == ["400000001"]
    assert d["ozet"][0]["iptal_erteleme"] == 1
    assert _gun(istemci, h, "2026-10-03")["adet"] == 1


def test_izinler(istemci, v2db, jeton, kisi):
    _esitle(istemci, [_gorev(1)])
    for ad in ("teknik1", "satis"):
        h = jeton(kisi[ad])
        assert istemci.get("/api/rut", headers=h, params={"tarih": GUN}).status_code == 403
        assert _yaz(istemci, h, 1, "durum", "KURULDU").status_code == 403
    assert istemci.get("/api/rut", params={"tarih": GUN}).status_code == 401
