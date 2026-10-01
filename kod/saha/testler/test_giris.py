"""Giriş akışı, PIN belirleme ve hatalı deneme kilidi."""
from __future__ import annotations

from .conftest import PIN, SATISCI_TEL, YONETICI_TEL, davet_kodu


def test_saglik_acik(istemci):
    yanit = istemci.get("/api/saglik")
    assert yanit.status_code == 200
    veri = yanit.json()
    assert veri["ok"] is True
    assert veri["bina"] == 19706
    assert veri["kullanici"] == 9


def test_ilk_giriste_pin_belirle_istenir(istemci):
    yanit = istemci.post("/api/giris", json={"telefon": SATISCI_TEL[1], "pin": "1234"})
    assert yanit.status_code == 200
    assert yanit.json()["pin_belirle"] is True


def test_telefon_bicimi_esnek(istemci, db_yolu):
    kod = davet_kodu(db_yolu, SATISCI_TEL[3])
    yanit = istemci.post("/api/pin", json={"telefon": "0 500 000 00 03", "pin": PIN, "davet_kodu": kod})
    assert yanit.status_code == 200, yanit.text
    assert istemci.post("/api/giris", json={"telefon": "+90 500 000 00 03", "pin": PIN}).status_code == 200


def test_gecersiz_telefon_turkce_hata(istemci):
    yanit = istemci.post("/api/giris", json={"telefon": "123", "pin": PIN})
    assert yanit.status_code == 400
    assert yanit.json()["kod"] == "telefon_gecersiz"
    assert "Telefon" in yanit.json()["hata"]


def test_yanlis_davet_kodu_reddedilir(istemci):
    yanit = istemci.post("/api/pin", json={"telefon": SATISCI_TEL[1], "pin": PIN, "davet_kodu": "000000"})
    assert yanit.status_code == 401
    assert yanit.json()["kod"] == "kimlik_hatali"


def test_zayif_pin_reddedilir(istemci, db_yolu):
    kod = davet_kodu(db_yolu, SATISCI_TEL[1])
    for zayif in ("1111", "1234", "4321"):
        yanit = istemci.post("/api/pin", json={"telefon": SATISCI_TEL[1], "pin": zayif, "davet_kodu": kod})
        assert yanit.status_code == 400
        assert yanit.json()["kod"] == "pin_zayif"
    yanit = istemci.post("/api/pin", json={"telefon": SATISCI_TEL[1], "pin": "12", "davet_kodu": kod})
    assert yanit.json()["kod"] == "pin_gecersiz"


def test_pin_belirle_ve_giris(istemci, db_yolu):
    kod = davet_kodu(db_yolu, SATISCI_TEL[1])
    yanit = istemci.post("/api/pin", json={"telefon": SATISCI_TEL[1], "pin": PIN, "davet_kodu": kod})
    assert yanit.status_code == 200
    jeton = yanit.json()["token"]
    assert yanit.json()["kullanici"]["bolge"] == 1

    # Kod tek kullanımlık. PIN belirlenince davet_kodu silindiği için ikinci
    # deneme "kimlik_hatali" alır: "bu hesabın PIN'i var" bilgisi davet kodu
    # DOĞRULANMADAN verilmez (kimliksiz hesap taramasını engeller).
    ikinci = istemci.post(
        "/api/pin", json={"telefon": SATISCI_TEL[1], "pin": "9182", "davet_kodu": kod}
    )
    assert ikinci.status_code == 401 and ikinci.json()["kod"] == "kimlik_hatali"

    ben = istemci.get("/api/ben", headers={"Authorization": f"Bearer {jeton}"})
    assert ben.status_code == 200
    assert ben.json()["kullanici"]["rol"] == "satisci"
    assert ben.json()["bugun"]["kalan"] == 0


def test_jetonsuz_ve_bozuk_jeton_401(istemci):
    assert istemci.get("/api/ben").status_code == 401
    assert istemci.get("/api/ben", headers={"Authorization": "Bearer sahte.jeton"}).status_code == 401
    assert istemci.get("/api/ben", headers={"Authorization": "Basic abc"}).status_code == 401


def test_hatali_denemeler_dogru_pini_engellemez(istemci, giris):
    """Sert kilit kaldırıldı: ağdaki biri satışçıyı sahada kilitleyemesin.

    Eskiden 5 yanlış PIN o numarayı 15 dakika kapatıyordu — DOĞRU PIN dahil.
    Yani herhangi biri bir satışçının numarasına 5 kez yanlış deneme yollayıp
    onu gün boyu dışarıda bırakabiliyordu. Artık yanlış deneme yavaşlatılır,
    doğru PIN her zaman kabul edilir; kaba kuvveti IP sınırı durdurur.
    """
    giris(SATISCI_TEL[1])  # PIN belirlensin
    for _ in range(6):
        yanit = istemci.post("/api/giris", json={"telefon": SATISCI_TEL[1], "pin": "0000"})
        assert yanit.status_code == 401
        assert yanit.json()["kod"] == "kimlik_hatali"

    dogru = istemci.post("/api/giris", json={"telefon": SATISCI_TEL[1], "pin": PIN})
    assert dogru.status_code == 200, dogru.text
    assert dogru.json()["token"]


def test_yanlis_pin_mesaji_oturum_bitti_demez(istemci, giris):
    """Kullanıcı ne olduğunu anlamalı: "Oturum süresi doldu" değil "PIN hatalı"."""
    giris(SATISCI_TEL[1])
    yanit = istemci.post("/api/giris", json={"telefon": SATISCI_TEL[1], "pin": "0000"})
    assert yanit.status_code == 401
    govde = yanit.json()
    assert govde["kod"] == "kimlik_hatali"
    assert "PIN" in govde["hata"]
    assert "Oturum" not in govde["hata"]


def test_pin_yoklamasi_ilk_girisi_bildirir(istemci):
    """Uygulama PIN sormadan önce "bu hesap ilk giriş mi?" diye sorabilmeli.

    Aksi halde yeni satışçı, PIN'i olmadığı halde "Şifren" ekranına düşüp
    rastgele deniyor ve kendi hesabını kilitliyordu.
    """
    yanit = istemci.post("/api/giris", json={"telefon": SATISCI_TEL[4], "pin": ""})
    assert yanit.status_code == 200
    govde = yanit.json()
    assert govde["pin_belirle"] is True
    assert govde["mesaj"]
    # Yoklama çalışanın ADINI SIZDIRMAZ (kimliksiz hesap taraması).
    assert "ad" not in govde


def test_yoklama_var_olmayan_numarayi_ayirt_ettirmez(istemci):
    yok = istemci.post("/api/giris", json={"telefon": "5999999999", "pin": ""})
    assert yok.status_code == 200
    assert yok.json()["pin_belirle"] is False
    assert "ad" not in yok.json()


def test_kilit_baska_kullaniciyi_etkilemez(istemci, giris):
    giris(SATISCI_TEL[1])
    for _ in range(6):
        istemci.post("/api/giris", json={"telefon": SATISCI_TEL[1], "pin": "0000"})
    assert giris(SATISCI_TEL[2], "8264")


def test_pin_sifirlama_eski_jetonu_dusurur(istemci, satisci1, yonetici, conn):
    assert istemci.get("/api/ben", headers=satisci1).status_code == 200
    kid = conn.execute("SELECT id FROM kullanici WHERE telefon=?", (SATISCI_TEL[1],)).fetchone()["id"]

    yanit = istemci.post(f"/api/kullanici/{kid}/pin-sifirla", headers=yonetici)
    assert yanit.status_code == 200
    assert len(yanit.json()["davet_kodu"]) == 6

    dusuk = istemci.get("/api/ben", headers=satisci1)
    assert dusuk.status_code == 401
    assert dusuk.json()["kod"] in ("oturum_bitti", "hesap_kapali")


def test_kapali_hesap_giremez(istemci, yonetici, conn, db_yolu):
    kid = conn.execute("SELECT id FROM kullanici WHERE telefon=?", (SATISCI_TEL[4],)).fetchone()["id"]
    kod = davet_kodu(db_yolu, SATISCI_TEL[4])
    istemci.post("/api/pin", json={"telefon": SATISCI_TEL[4], "pin": PIN, "davet_kodu": kod})

    istemci.post("/api/kullanici", headers=yonetici, json={
        "id": kid, "ad": "Pasif Satışçı", "telefon": SATISCI_TEL[4],
        "rol": "satisci", "bolge": 4, "aktif": False,
    })
    yanit = istemci.post("/api/giris", json={"telefon": SATISCI_TEL[4], "pin": PIN})
    assert yanit.status_code == 403
    assert yanit.json()["kod"] == "hesap_kapali"


def test_pin_veritabaninda_acik_durmaz(istemci, giris, conn):
    giris(YONETICI_TEL)
    satir = conn.execute("SELECT pin_hash FROM kullanici WHERE telefon=?", (YONETICI_TEL,)).fetchone()
    assert satir["pin_hash"].startswith("scrypt$")
    assert PIN not in satir["pin_hash"]
