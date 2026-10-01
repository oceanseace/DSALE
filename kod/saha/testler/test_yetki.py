"""Yetkiler: satışçı başka bölgeye dokunamaz, görev atamayı yalnız yönetici yapar."""
from __future__ import annotations

import pytest

from .conftest import SATISCI_TEL


def _baska_bolge_binasi(conn, bolge: int) -> str:
    return conn.execute(
        "SELECT bina_serial FROM bina WHERE bolge=? ORDER BY bina_serial LIMIT 1", (bolge,)
    ).fetchone()["bina_serial"]


def test_satisci_baska_bolgenin_binasini_goremez(istemci, satisci1, conn):
    yabanci = _baska_bolge_binasi(conn, 5)
    yanit = istemci.get(f"/api/bina/{yabanci}", headers=satisci1)
    assert yanit.status_code == 403
    assert yanit.json()["kod"] == "baska_bolge"

    kendi = _baska_bolge_binasi(conn, 1)
    assert istemci.get(f"/api/bina/{kendi}", headers=satisci1).status_code == 200


def test_satisci_baska_bolge_listesi_isteyemez(istemci, satisci1):
    assert istemci.get("/api/bina?bolge=4", headers=satisci1).status_code == 403
    assert istemci.get("/api/harita?bolge=4", headers=satisci1).status_code == 403
    kendi = istemci.get("/api/bina?bolge=1&limit=5", headers=satisci1)
    assert kendi.status_code == 200
    assert all(b["bolge"] == 1 for b in kendi.json()["binalar"])


def test_satisci_bolgesiz_istekte_kendi_bolgesini_alir(istemci, satisci1):
    veri = istemci.get("/api/bina?limit=200", headers=satisci1).json()
    assert veri["toplam"] < 19706
    assert {b["bolge"] for b in veri["binalar"]} == {1}


def test_satisci_baska_bolgeye_ziyaret_isleyemez(istemci, satisci1, conn):
    yabanci = _baska_bolge_binasi(conn, 6)
    yanit = istemci.post("/api/ziyaret", headers=satisci1, json={
        "offline_id": "yetki-1", "bina_serial": yabanci, "sonuc": "satis", "satis_adedi": 1,
    })
    assert yanit.status_code == 403
    assert yanit.json()["kod"] == "baska_bolge"
    assert conn.execute("SELECT COUNT(*) FROM ziyaret").fetchone()[0] == 0


def test_satisci_baskasinin_listesini_goremez(istemci, satisci1, conn):
    baska = conn.execute("SELECT id FROM kullanici WHERE telefon=?", (SATISCI_TEL[2],)).fetchone()["id"]
    yanit = istemci.get(f"/api/gorev/bugun?kullanici_id={baska}", headers=satisci1)
    assert yanit.status_code == 403


@pytest.mark.parametrize("yol", ["/api/ozet/gun", "/api/kullanici"])
def test_yonetici_ekranlari_satisciya_kapali(istemci, satisci1, yol):
    yanit = istemci.get(yol, headers=satisci1)
    assert yanit.status_code == 403
    assert yanit.json()["kod"] == "yasak"


def test_rapor_satisciya_kapali(istemci, satisci1):
    assert istemci.get("/api/dosya/rapor.xlsx", headers=satisci1).status_code == 403


def test_gorev_atamayi_yalniz_yonetici_yapar(istemci, satisci1, yonetici, conn):
    kid = conn.execute("SELECT id FROM kullanici WHERE telefon=?", (SATISCI_TEL[2],)).fetchone()["id"]
    seriler = [r["bina_serial"] for r in conn.execute(
        "SELECT bina_serial FROM bina WHERE bolge=2 ORDER BY firsat DESC LIMIT 4").fetchall()]

    assert istemci.post("/api/gorev/ata", headers=satisci1,
                        json={"kullanici_id": kid, "bina_serial": seriler}).status_code == 403

    yanit = istemci.post("/api/gorev/ata", headers=yonetici,
                         json={"kullanici_id": kid, "bina_serial": seriler, "not": "Acil"})
    assert yanit.status_code == 200, yanit.text
    assert yanit.json()["eklenen"] == 4
    assert {b["bina_serial"] for b in yanit.json()["binalar"]} == set(seriler)


def test_yonetici_baska_bolgenin_binasini_atayamaz(istemci, yonetici, conn):
    kid = conn.execute("SELECT id FROM kullanici WHERE telefon=?", (SATISCI_TEL[2],)).fetchone()["id"]
    yabanci = _baska_bolge_binasi(conn, 5)
    yanit = istemci.post("/api/gorev/ata", headers=yonetici,
                         json={"kullanici_id": kid, "bina_serial": [yabanci]})
    assert yanit.status_code == 400
    assert yanit.json()["kod"] == "baska_bolge"


def test_atanan_gorev_satisciya_dusar(istemci, yonetici, basliklar, conn):
    """Trendyol Go kuryesine paket düşmesi gibi: yönetici atar, telefonda belirir."""
    s2 = basliklar(SATISCI_TEL[2], "8264")
    kid = conn.execute("SELECT id FROM kullanici WHERE telefon=?", (SATISCI_TEL[2],)).fetchone()["id"]
    mahalle = conn.execute(
        "SELECT mahalle FROM bina WHERE bolge=2 GROUP BY mahalle ORDER BY COUNT(*) DESC LIMIT 1"
    ).fetchone()["mahalle"]

    atama = istemci.post("/api/gorev/ata", headers=yonetici,
                         json={"kullanici_id": kid, "mahalle": mahalle, "adet": 6, "not": mahalle})
    assert atama.status_code == 200, atama.text
    assert atama.json()["eklenen"] == 6

    bugun = istemci.get("/api/gorev/bugun", headers=s2).json()
    assert bugun["kaynak"] == "yonetici"
    assert bugun["notu"] == mahalle
    assert len(bugun["binalar"]) == 6
    assert all(b["mahalle"] == mahalle for b in bugun["binalar"])


def test_yonetici_atamasi_acik_goreve_eklenir(istemci, yonetici, basliklar, conn):
    s3 = basliklar(SATISCI_TEL[3], "5837")
    kid = conn.execute("SELECT id FROM kullanici WHERE telefon=?", (SATISCI_TEL[3],)).fetchone()["id"]
    kendi = istemci.post("/api/gorev/olustur", headers=s3, json={"adet": 5}).json()

    seriler = [r["bina_serial"] for r in conn.execute(
        "SELECT b.bina_serial FROM bina b JOIN bina_durum d USING(bina_serial) "
        "WHERE b.bolge=3 AND d.durum='bekliyor' ORDER BY b.firsat DESC LIMIT 3").fetchall()]
    atama = istemci.post("/api/gorev/ata", headers=yonetici,
                         json={"kullanici_id": kid, "bina_serial": seriler})
    assert atama.json()["gorev_id"] == kendi["gorev_id"]

    bugun = istemci.get("/api/gorev/bugun", headers=s3).json()
    # Kendi listesi (site bütünlüğü için 5'i biraz aşabilir) + atanan 3 bina.
    assert len(bugun["binalar"]) == len(kendi["binalar"]) + 3
    assert [b["sira"] for b in bugun["binalar"]] == sorted(b["sira"] for b in bugun["binalar"])


def test_yonetici_icin_rota_kurulmaz(istemci, yonetici):
    yanit = istemci.post("/api/gorev/olustur", headers=yonetici, json={"adet": 5})
    assert yanit.status_code == 400
    assert yanit.json()["kod"] == "bolge_yok"


def test_yonetici_satisci_listesini_ve_kaydini_yonetir(istemci, yonetici):
    liste = istemci.get("/api/kullanici", headers=yonetici).json()["kullanicilar"]
    assert len(liste) == 9
    assert sum(1 for k in liste if k["rol"] == "satisci") == 8

    yeni = istemci.post("/api/kullanici", headers=yonetici, json={
        "ad": "Yeni Satışçı", "telefon": "0532 111 22 33", "rol": "satisci", "bolge": 4,
    })
    assert yeni.status_code == 200
    assert yeni.json()["kullanici"]["telefon"] == "5321112233"
    assert len(yeni.json()["davet_kodu"]) == 6

    cakisma = istemci.post("/api/kullanici", headers=yonetici, json={
        "ad": "Kopya", "telefon": "5321112233", "rol": "satisci", "bolge": 5,
    })
    assert cakisma.status_code == 409 and cakisma.json()["kod"] == "telefon_var"

    bolgesiz = istemci.post("/api/kullanici", headers=yonetici, json={
        "ad": "Bölgesiz", "telefon": "5329998877", "rol": "satisci",
    })
    assert bolgesiz.status_code == 400 and bolgesiz.json()["kod"] == "bolge_gecersiz"


def test_bilinmeyen_uc_turkce_json_dondurur(istemci, yonetici):
    yanit = istemci.get("/api/yok-boyle-bir-sey", headers=yonetici)
    assert yanit.status_code == 404
    assert yanit.json()["kod"] == "bulunamadi"
    assert "bulunamadı" in yanit.json()["hata"]
