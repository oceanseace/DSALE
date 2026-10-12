"""BOSS ile giriş (saha/boss_giris.py): bekleyen istek 2 dk, tek kullanımlık, isteyen pencereye bağlı (gizli);
eklenti kimliği eşleme koduyla bildirir; BOSS oturumu bitince yalnız BOSS'la açılan uygulama oturumu biter.
Şifre/kod hiçbir uçtan geçmez: eklentiden yalnız ad / kullanıcı kodu / unvan gelir."""
from __future__ import annotations

import pytest

from saha import boss_giris

from .conftest import PIN


@pytest.fixture(autouse=True)
def _temiz(monkeypatch):
    boss_giris.sifirla()
    monkeypatch.setenv("TURKCELL_ADMIN_TELEFON", "5009990001")
    monkeypatch.setenv("TURKCELL_ADMIN_AD", "Ahmet Emirhan Korkmaz")
    yield
    boss_giris.sifirla()


@pytest.fixture
def ek():
    from operasyon.v2 import boss

    return {"X-Eslesme-Kodu": boss.eslesme_kodu()}


def _baslat(istemci) -> dict:
    r = istemci.post("/api/giris/boss/baslat")
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["ac_yolu"] == f"/boss-giris/{j['istek_id']}" and j["sure_sn"] == 120
    return j


def _durum(istemci, b, gizli=None):
    return istemci.post("/api/giris/boss/durum", json={"istek_id": b["istek_id"], "gizli": gizli or b["gizli"]})


def test_boss_kimligiyle_giris_tek_kullanimlik_ve_pencereye_bagli(istemci, kisi, ek):
    kid, _ = kisi("operasyon", ad="Ayşe Yılmaz")
    b = _baslat(istemci)
    s = istemci.get(b["ac_yolu"])
    assert s.status_code == 200 and 'http-equiv="refresh"' in s.text and "boss.turkcell.com.tr" in s.text
    d = _durum(istemci, b).json()
    assert (d["durum"], d["tarayicida"]) == ("bekliyor", True) and 115 <= d["kalan_sn"] <= 120
    # BOSS'ta büyük harf ve Türkçe harfsiz görünen ad aynı kişidir
    r = istemci.post("/api/giris/boss/kimlik", headers=ek, json={"istek_id": b["istek_id"], "ad": "AYSE YILMAZ",
                                                                  "kod": "AYILMAZ"})
    assert r.json() == {"ok": True, "durum": "onaylandi"}
    assert _durum(istemci, b, gizli="baska-pencere").status_code == 410, "gizlisi olmayan pencere alamaz"
    t = _durum(istemci, b)
    assert t.status_code == 200 and t.json()["durum"] == "tamam" and t.json()["kullanici"]["id"] == kid
    jeton = {"Authorization": f"Bearer {t.json()['token']}"}
    assert istemci.get("/api/ben", headers=jeton).status_code == 200
    assert istemci.get("/api/oturum/boss", headers=jeton).status_code == 200
    assert _durum(istemci, b).status_code == 410, "jeton bir kez verilir"
    # eklentinin ikinci bildirimi (aynı istek) bir şey açmaz
    assert istemci.post("/api/giris/boss/kimlik", headers=ek, json={"istek_id": b["istek_id"], "ad": "AYSE YILMAZ"}
                        ).json()["ok"] is False


def test_boss_cikisinda_yalniz_boss_oturumu_biter(istemci, kisi, ek):
    _kid, pin_jetonu = kisi("operasyon", ad="Ayşe Yılmaz")
    b = _baslat(istemci)
    istemci.post("/api/giris/boss/kimlik", headers=ek, json={"istek_id": b["istek_id"], "ad": "Ayşe Yılmaz"})
    jeton = {"Authorization": f"Bearer {_durum(istemci, b).json()['token']}"}
    assert istemci.get("/api/ben", headers=jeton).status_code == 200
    assert istemci.post("/api/giris/boss/bitti", json={"ad": "Ayşe Yılmaz"}).status_code == 401, "eşleme kodu şart"
    r = istemci.post("/api/giris/boss/bitti", headers=ek, json={"ad": "AYSE YILMAZ", "neden": "cikis"})
    assert r.json() == {"ok": True, "biten": 1}
    y = istemci.get("/api/ben", headers=jeton)
    assert y.status_code == 401 and y.json()["kod"] == "boss_oturumu_bitti"
    assert istemci.get("/api/oturum/boss", headers=jeton).status_code == 401
    assert istemci.get("/api/ben", headers=pin_jetonu).status_code == 200, "telefon + PIN oturumu sürer"


def test_kimliksiz_bitti_butun_boss_oturumlarini_ve_baska_kullanici_eskisini_bitirir(istemci, kisi, ek):
    kisi("operasyon", ad="Ayşe Yılmaz")
    kisi("operasyon", ad="Mehmet Kaya")
    jetonlar = []
    for ad in ("Ayşe Yılmaz", "Mehmet Kaya"):
        b = _baslat(istemci)
        istemci.post("/api/giris/boss/kimlik", headers=ek, json={"istek_id": b["istek_id"], "ad": ad})
        jetonlar.append({"Authorization": f"Bearer {_durum(istemci, b).json()['token']}"})
    # Mehmet BOSS'ta oturum açınca Ayşe'nin BOSS'la açılmış oturumu biter (BOSS'ta tek kullanıcı)
    assert istemci.get("/api/ben", headers=jetonlar[0]).status_code == 401
    assert istemci.get("/api/ben", headers=jetonlar[1]).status_code == 200
    assert istemci.post("/api/giris/boss/bitti", headers=ek, json={"neden": "401"}).json()["biten"] == 1
    assert istemci.get("/api/ben", headers=jetonlar[1]).status_code == 401


def test_administrator_ayarli_adla_eslesir(istemci, ek):
    b = _baslat(istemci)
    istemci.post("/api/giris/boss/kimlik", headers=ek, json={"istek_id": b["istek_id"], "ad": "KORKMAZ AHMET EMIRHAN"})
    t = _durum(istemci, b).json()
    assert t["durum"] == "tamam"
    ben = istemci.get("/api/ben", headers={"Authorization": f"Bearer {t['token']}"}).json()
    assert ben["administrator"] is True


def test_eslesmeyen_ve_ayni_adli_iki_kisi_reddedilir_unvanla_ayrilir(istemci, kisi, conn, ek):
    b = _baslat(istemci)
    istemci.post("/api/giris/boss/kimlik", headers=ek, json={"istek_id": b["istek_id"], "ad": "Olmayan Kişi"})
    r = _durum(istemci, b)
    assert r.status_code == 403 and r.json()["kod"] == "boss_eslesmedi" and "Olmayan Kişi" in r.json()["hata"]
    assert _durum(istemci, b).status_code == 410, "red de tek kullanımlık"

    k1, _ = kisi("operasyon", ad="Ali Demir")
    k2, _ = kisi("teknik", ad="Ali Demir")
    conn.execute("UPDATE kullanici SET unvan='Saha Teknisyeni' WHERE id=?", (k2,))
    conn.commit()
    b = _baslat(istemci)
    istemci.post("/api/giris/boss/kimlik", headers=ek, json={"istek_id": b["istek_id"], "ad": "Ali Demir"})
    assert _durum(istemci, b).json()["kod"] == "boss_eslesmedi"
    b = _baslat(istemci)
    istemci.post("/api/giris/boss/kimlik", headers=ek, json={"istek_id": b["istek_id"], "ad": "Ali Demir",
                                                              "unvan": "SAHA TEKNISYENI"})
    assert _durum(istemci, b).json()["kullanici"]["id"] == k2


def test_bekleyen_istek_iki_dakikada_duser(istemci, kisi, ek, monkeypatch):
    kisi("operasyon", ad="Ayşe Yılmaz")
    b = _baslat(istemci)
    simdi = boss_giris.time.time()
    monkeypatch.setattr(boss_giris.time, "time", lambda: simdi + 121)
    assert istemci.post("/api/giris/boss/kimlik", headers=ek, json={"istek_id": b["istek_id"], "ad": "Ayşe Yılmaz"}
                        ).json()["ok"] is False
    assert _durum(istemci, b).status_code == 410
    assert istemci.get(b["ac_yolu"]).status_code == 410


def test_yalniz_bu_bilgisayardan_ve_eslesme_koduyla(istemci, ek, monkeypatch):
    b = _baslat(istemci)
    assert istemci.post("/api/giris/boss/kimlik", json={"istek_id": b["istek_id"], "ad": "X Y"}).status_code == 401
    assert istemci.post("/api/giris/boss/kimlik", headers={"X-Eslesme-Kodu": "0000-0000"},
                        json={"istek_id": b["istek_id"], "ad": "X Y"}).status_code == 401
    monkeypatch.setattr(boss_giris, "_YEREL", {"127.0.0.1"})          # TestClient'ın adresi artık yerel değil
    r = istemci.post("/api/giris/boss/baslat")
    assert r.status_code == 403 and r.json()["kod"] == "yalniz_yerel"
    assert _durum(istemci, b).status_code == 403


def test_pin_girisi_bozulmadi(istemci, giris):
    from .conftest import SATISCI_TEL

    assert giris(SATISCI_TEL[1], PIN)
