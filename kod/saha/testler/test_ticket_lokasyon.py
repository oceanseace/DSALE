"""Loc ID ile yeni ticket: bina/site/ilçe ve binadaki açık işlerin müşteri no'ları kendiliğinden dolar;
açık ticket'lı lokasyonlar (TASKS uyarısı) ve Tablolar özetinin boş altyapıda çökmemesi."""
from __future__ import annotations

from saha import ticket

BINA, LOC = "BN-0000362608", "O25265408"        # tohum verisindeki bina (test_ticket.py ile aynı)


def _is_ekle(conn, is_no: str, musteri_no: str, durum: str = "atandi", bina_serial=BINA, lokasyon=None) -> None:
    z = "2026-09-30 10:00:00"
    conn.execute(
        "INSERT INTO is_emri (is_no, boss_task_no, kaynak, task_adi, serit, musteri_no, durum, durum_zamani, "
        "bina_serial, lokasyon, acilis, son24, ilk_gorulme, gorulme_zamani, guncelleme) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (is_no, f"T{is_no}", "boss", "Arıza", "Arıza", musteri_no, durum, z, bina_serial, lokasyon, z, z, z, z, z))
    conn.commit()


def test_lokasyon_anahtari():
    assert ticket.lokasyon_anahtari(" o25265408 ") == "O25265408"
    assert ticket.lokasyon_anahtari("O27592861-1") == "O27592861"
    assert ticket.lokasyon_anahtari("00113680") == ticket.lokasyon_anahtari("113680") == "113680"
    assert ticket.lokasyon_anahtari(None) == ""


def test_lokasyon_bilgisi_bina_ve_acik_is_musterileri(conn):
    _is_ekle(conn, "L1", "11111111")
    _is_ekle(conn, "L2", "22222222", lokasyon=LOC, bina_serial=None)     # binaya bağlanmamış ama aynı Loc ID
    _is_ekle(conn, "L3", "33333333", durum="kapandi")                       # kapalı iş sayılmaz
    _is_ekle(conn, "L4", "11111111")                                         # tekrar eden no bir kez
    b = ticket.lokasyon_bilgisi(conn, LOC.lower() + "-1")
    assert b["bulundu"] and b["bina_serial"] == BINA and b["location_id"] == LOC
    assert b["site"] == "MERSA SİT. D BLK. MERSA D"
    assert b["musteriler"] == ["11111111", "22222222"]
    assert ticket.lokasyon_bilgisi(conn, bina_serial=BINA)["location_id"] == LOC
    yok = ticket.lokasyon_bilgisi(conn, "X999")
    assert yok["bulundu"] is False and yok["musteriler"] == [] and yok["location_id"] == "X999"


def test_yalniz_loc_id_ve_konuyla_ticket_acilir(istemci, yonetici, conn):
    _is_ekle(conn, "L5", "44444444")
    y = istemci.post("/api/ticket", headers=yonetici, json={"location_id": LOC, "konu": "EK SP"})
    assert y.status_code == 201, y.text
    t = y.json()["ticket"]
    assert t["durum"] == "AÇIK" and t["bina_serial"] == BINA and t["site"] == "MERSA SİT. D BLK. MERSA D"
    assert t["musteri"] == "44444444" and t["ticket_no"] == "" and t["metin"]
    # Elle yazılan müşteri ezilmez
    y = istemci.post("/api/ticket", headers=yonetici, json={"location_id": LOC, "konu": "SİNYAL", "musteri": "1, 2"})
    assert y.json()["ticket"]["musteri"] == "1, 2"
    # Binası olmayan Loc ID de kaydedilir
    y = istemci.post("/api/ticket", headers=yonetici, json={"location_id": "X999", "konu": "SİNYAL"})
    assert y.status_code == 201 and y.json()["ticket"]["bina_serial"] is None
    assert y.json()["ticket"]["location_id"] == "X999"


def test_acik_lokasyonlar(istemci, yonetici, conn):
    assert ticket.acik_lokasyonlar(conn) == set()
    tid = istemci.post("/api/ticket", headers=yonetici, json={"bina_serial": BINA, "konu": "SİNYAL"}).json()["ticket"]["id"]
    istemci.post("/api/ticket", headers=yonetici, json={"location_id": "00113680", "konu": "SİNYAL"})
    assert ticket.acik_lokasyonlar(conn) == {LOC, "113680"}
    istemci.patch(f"/api/ticket/{tid}", headers=yonetici, json={"durum": "ÇÖZÜLDÜ"})
    assert ticket.acik_lokasyonlar(conn) == {"113680"}


def test_tablolar_ozeti_bekleyen_altyapi_yokken_acilir(istemci, yonetici):
    """Bekleyen altyapı satırı yokken MIN(baslangic) NULL döner; özet 500 vermemeli (ekranda hata kutusu)."""
    y = istemci.get("/api/tablolar", headers=yonetici)
    assert y.status_code == 200, y.text
    assert y.json()["ozet"]["altyapi_en_eski_gun"] is None


def test_lokasyon_ucu_ticket_idden_once_yakalanir(istemci, yonetici, conn):
    """GET /api/ticket/lokasyon (yeni ticket penceresi): {ticket_id} yolu yakalamaz; boş sorgu 400."""
    _is_ekle(conn, "L9", "99999999")
    y = istemci.get(f"/api/ticket/lokasyon?loc={LOC}", headers=yonetici)
    assert y.status_code == 200, y.text
    assert y.json()["bina_serial"] == BINA and y.json()["musteriler"] == ["99999999"]
    assert istemci.get(f"/api/ticket/lokasyon?bina_serial={BINA}", headers=yonetici).json()["location_id"] == LOC
    assert istemci.get("/api/ticket/lokasyon", headers=yonetici).status_code == 400


def test_lokasyon_musterileri_yalniz_musteri_izniyle_ve_kayitli(istemci, yonetici, conn, monkeypatch):
    """ticket.defter tek başına müşteri no'su vermez (is.musteri gerekir); verilen yanıt KVKK kaydına yazılır."""
    from saha import yonetim_uclari

    _is_ekle(conn, "L10", "10101010")
    y = istemci.get(f"/api/ticket/lokasyon?loc={LOC}", headers=yonetici).json()
    assert y["musteriler"] == ["10101010"]
    assert conn.execute("SELECT adet FROM erisim_kaydi WHERE eylem='ticket_lokasyon'").fetchone()[0] == 1
    asil = yonetim_uclari.izinli
    monkeypatch.setattr(yonetim_uclari, "izinli", lambda k, e: False if e == "is.musteri" else asil(k, e))
    y = istemci.get(f"/api/ticket/lokasyon?loc={LOC}", headers=yonetici).json()
    assert y["musteriler"] == [] and y["bina_serial"] == BINA
    assert conn.execute("SELECT COUNT(*) FROM erisim_kaydi WHERE eylem='ticket_lokasyon'").fetchone()[0] == 1
