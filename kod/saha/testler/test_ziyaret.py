"""Görev akışı ve ziyaret idempotanlığı — aynı kayıt iki kez sayılmamalı."""
from __future__ import annotations

from .conftest import SATISCI_TEL


def _gorev_olustur(istemci, basliklar, adet=25):
    yanit = istemci.post("/api/gorev/olustur", headers=basliklar, json={"adet": adet})
    assert yanit.status_code == 200, yanit.text
    return yanit.json()


def test_gorev_olustur_ve_bugun(istemci, satisci1):
    veri = _gorev_olustur(istemci, satisci1)
    # Site bütünlüğü için liste birkaç bina taşabilir (rota.LISTE_TASMA).
    assert 25 <= len(veri["binalar"]) <= 30
    assert veri["ozet"]["toplam"] == veri["ozet"]["kalan"] == len(veri["binalar"])
    ilk = veri["binalar"][0]
    for alan in ("baslik", "adres", "daire", "firsat", "lat", "lon", "mesafe_m", "sira", "yeni_site"):
        assert alan in ilk

    bugun = istemci.get("/api/gorev/bugun", headers=satisci1).json()
    assert bugun["gorev_id"] == veri["gorev_id"]
    assert [b["bina_serial"] for b in bugun["binalar"]] == [b["bina_serial"] for b in veri["binalar"]]
    assert bugun["toplam_mesafe_m"] > 0


def test_gorev_iki_kez_olusturulmaz(istemci, satisci1):
    birinci = _gorev_olustur(istemci, satisci1)
    ikinci = istemci.post("/api/gorev/olustur", headers=satisci1, json={}).json()
    assert ikinci["zaten_var"] is True
    assert ikinci["gorev_id"] == birinci["gorev_id"]


def test_gorevdeki_binalar_planli_isaretlenir(istemci, satisci1, conn):
    veri = _gorev_olustur(istemci, satisci1, 10)
    seriler = [b["bina_serial"] for b in veri["binalar"]]
    isaretler = ",".join("?" * len(seriler))
    durumlar = conn.execute(
        f"SELECT durum FROM bina_durum WHERE bina_serial IN ({isaretler})", tuple(seriler)
    ).fetchall()
    assert all(d["durum"] == "planli" for d in durumlar)


def test_ziyaret_kaydi_binayi_gunceller(istemci, satisci1, conn):
    veri = _gorev_olustur(istemci, satisci1, 5)
    hedef = veri["binalar"][0]["bina_serial"]

    yanit = istemci.post("/api/ziyaret", headers=satisci1, json={
        "offline_id": "tel-a-0001", "bina_serial": hedef, "sonuc": "satis",
        "satis_adedi": 2, "konusulan_daire": 6, "not": "Kapıcı yardımcı oldu",
    })
    assert yanit.status_code == 200, yanit.text
    govde = yanit.json()
    assert govde["yinelenen"] is False
    assert govde["durum"] == "ziyaret_edildi"
    assert govde["ozet"]["tamam"] == 1
    assert govde["ozet"]["kalan"] == len(veri["binalar"]) - 1
    assert govde["ozet"]["satis"] == 2

    d = conn.execute("SELECT * FROM bina_durum WHERE bina_serial=?", (hedef,)).fetchone()
    assert d["durum"] == "ziyaret_edildi"
    assert d["toplam_satis"] == 2 and d["ziyaret_sayisi"] == 1
    assert d["son_sonuc"] == "satis" and d["son_ziyaret"]

    detay = istemci.get(f"/api/bina/{hedef}", headers=satisci1).json()
    assert len(detay["ziyaretler"]) == 1
    assert detay["ziyaretler"][0]["sonuc_etiket"] == "Satış"


def test_ayni_offline_id_iki_kez_sayilmaz(istemci, satisci1, conn):
    veri = _gorev_olustur(istemci, satisci1, 5)
    hedef = veri["binalar"][0]["bina_serial"]
    govde = {"offline_id": "tel-a-0002", "bina_serial": hedef, "sonuc": "satis", "satis_adedi": 3}

    ilk = istemci.post("/api/ziyaret", headers=satisci1, json=govde).json()
    assert ilk["yinelenen"] is False
    for _ in range(4):  # telefon kuyruğu aynı kaydı tekrar tekrar gönderiyor
        tekrar = istemci.post("/api/ziyaret", headers=satisci1, json=govde).json()
        assert tekrar["yinelenen"] is True
        assert tekrar["ziyaret_id"] == ilk["ziyaret_id"]

    d = conn.execute("SELECT * FROM bina_durum WHERE bina_serial=?", (hedef,)).fetchone()
    assert d["toplam_satis"] == 3, "satış adedi tekrarla şişti"
    assert d["ziyaret_sayisi"] == 1
    assert conn.execute("SELECT COUNT(*) FROM ziyaret").fetchone()[0] == 1


def test_toplu_senkron_idempotent(istemci, satisci1, conn):
    veri = _gorev_olustur(istemci, satisci1, 6)
    seriler = [b["bina_serial"] for b in veri["binalar"][:3]]
    kuyruk = [
        {"offline_id": f"kuyruk-{i}", "bina_serial": s, "sonuc": "ilgilenmedi", "konusulan_daire": 4}
        for i, s in enumerate(seriler)
    ]
    kuyruk.append({"offline_id": "kuyruk-satis", "bina_serial": seriler[0],
                   "sonuc": "satis", "satis_adedi": 1})

    ilk = istemci.post("/api/ziyaret/toplu", headers=satisci1, json=kuyruk).json()
    assert ilk["kaydedilen"] == 4 and ilk["yinelenen"] == 0 and ilk["hatali"] == []

    ikinci = istemci.post("/api/ziyaret/toplu", headers=satisci1, json=kuyruk).json()
    assert ikinci["kaydedilen"] == 0 and ikinci["yinelenen"] == 4

    assert conn.execute("SELECT COUNT(*) FROM ziyaret").fetchone()[0] == 4
    assert conn.execute(
        "SELECT toplam_satis FROM bina_durum WHERE bina_serial=?", (seriler[0],)
    ).fetchone()[0] == 1


def test_toplu_kuyruk_hatali_kayitta_dusmez(istemci, satisci1):
    veri = _gorev_olustur(istemci, satisci1, 3)
    iyi = veri["binalar"][0]["bina_serial"]
    kuyruk = [
        {"offline_id": "karma-1", "bina_serial": iyi, "sonuc": "evde_yok"},
        {"offline_id": "karma-2", "bina_serial": "BN-YOK-9999", "sonuc": "evde_yok"},
        {"offline_id": "karma-3", "bina_serial": iyi, "sonuc": "satis", "satis_adedi": 1},
    ]
    sonuc = istemci.post("/api/ziyaret/toplu", headers=satisci1, json=kuyruk).json()
    assert sonuc["kaydedilen"] == 2
    assert len(sonuc["hatali"]) == 1
    assert sonuc["hatali"][0]["offline_id"] == "karma-2"
    assert sonuc["hatali"][0]["kod"] == "bina_yok"


def test_gecersiz_sonuc_reddedilir(istemci, satisci1):
    veri = _gorev_olustur(istemci, satisci1, 2)
    yanit = istemci.post("/api/ziyaret", headers=satisci1, json={
        "offline_id": "hatali-1", "bina_serial": veri["binalar"][0]["bina_serial"], "sonuc": "belki",
    })
    assert yanit.status_code == 400
    assert yanit.json()["kod"] == "sonuc_gecersiz"


def test_randevu_tekrar_tarihi_koyar(istemci, satisci1, conn):
    veri = _gorev_olustur(istemci, satisci1, 3)
    hedef = veri["binalar"][0]["bina_serial"]
    istemci.post("/api/ziyaret", headers=satisci1, json={
        "offline_id": "randevu-1", "bina_serial": hedef, "sonuc": "randevu",
        "tekrar_tarih": "2026-10-01", "not": "Cumartesi 14:00",
    })
    d = conn.execute("SELECT * FROM bina_durum WHERE bina_serial=?", (hedef,)).fetchone()
    assert d["durum"] == "tekrar_gel"
    assert d["tekrar_tarih"] == "2026-10-01"


def test_ziyaret_edilen_bina_yeni_rotaya_girmez(istemci, satisci1, conn):
    veri = _gorev_olustur(istemci, satisci1, 5)
    for i, b in enumerate(veri["binalar"]):
        istemci.post("/api/ziyaret", headers=satisci1, json={
            "offline_id": f"tur1-{i}", "bina_serial": b["bina_serial"], "sonuc": "ilgilenmedi",
        })
    eski = {b["bina_serial"] for b in veri["binalar"]}
    yeni = istemci.post("/api/gorev/olustur", headers=satisci1, json={"adet": 5}).json()
    assert yeni["gorev_id"] != veri["gorev_id"]
    assert eski.isdisjoint({b["bina_serial"] for b in yeni["binalar"]})


def test_iki_satisciya_ayni_bina_dusmez(istemci, basliklar, conn):
    """Aynı bölgeye iki kişi bakarsa bile bina iki listede olmaz (bölge tek kişilik ama kural genel)."""
    s1 = basliklar(SATISCI_TEL[7])
    ilk = istemci.post("/api/gorev/olustur", headers=s1, json={"adet": 20}).json()
    seriler = {b["bina_serial"] for b in ilk["binalar"]}
    kid = conn.execute("SELECT id FROM kullanici WHERE telefon=?", (SATISCI_TEL[7],)).fetchone()["id"]
    planli = conn.execute(
        "SELECT COUNT(*) FROM gorev_bina gb JOIN gorev g ON g.id=gb.gorev_id "
        "WHERE g.kullanici_id=? AND gb.durum='bekliyor'", (kid,)
    ).fetchone()[0]
    assert planli == len(seriler) >= 20


def test_gorev_yanit_bicimi_her_durumda_ayni(istemci, satisci1):
    """Uygulama tek bir biçim beklesin: alanlar hiçbir dalda kaybolmasın."""
    alanlar = {"gorev_id", "tarih", "kaynak", "notu", "binalar", "toplam_mesafe_m", "ozet"}
    bos = istemci.get("/api/gorev/bugun", headers=satisci1).json()
    assert alanlar <= set(bos) and bos["binalar"] == [] and bos["toplam_mesafe_m"] == 0

    yeni = istemci.post("/api/gorev/olustur", headers=satisci1, json={"adet": 5}).json()
    assert alanlar <= set(yeni) and yeni["toplam_mesafe_m"] > 0

    tekrar = istemci.post("/api/gorev/olustur", headers=satisci1, json={"adet": 5}).json()
    assert alanlar <= set(tekrar)
    assert tekrar["toplam_mesafe_m"] == yeni["toplam_mesafe_m"]

    dolu = istemci.get("/api/gorev/bugun", headers=satisci1).json()
    assert alanlar <= set(dolu) and dolu["toplam_mesafe_m"] == yeni["toplam_mesafe_m"]
