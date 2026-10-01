"""Ticket defteri (GEREKSINIMLER C11) — OneDesk ticket'larının Excel yerine takibi."""
from __future__ import annotations

from pathlib import Path

import pytest

from saha import ticket, ticket_aktar

# Kullanıcının kendi ticket'ından birebir (sekme ayrımlı; boş hücreler dahil)
KULLANICI_ORNEGI = (
    "*BTK ÇAĞRISI ACİL MÜDAHALE* Merhaba, bilgisi olan lokasyonda boş kılda/kıllarda sinyal zayıftır, "
    "düzeltilmesi konusunda desteğinizi rica ederim.\tBina Serial Number\tBN-0000362608\tTellcordia ID\t"
    "16014745208\t\tLocation Id\tO25265408\t\t\tObek Adı\tBRS-ATAEVLER\tSite Adı\tMERSA SİT. D BLK. MERSA D\t"
    "Ekip: +905551234567"
)


def test_ticket_metni_kullanici_ornegiyle_birebir(istemci, yonetici):
    y = istemci.get("/api/ticket/sablon", headers=yonetici,
                    params={"bina_serial": "BN-0000362608", "konu": "sinyal", "ekip": "+905551234567"})
    assert y.status_code == 200, y.text
    assert y.json()["metin"] == KULLANICI_ORNEGI
    assert y.json()["sablon_taslak"] is False
    assert y.json()["alanlar"]["location_id"] == "O25265408"


def test_binadan_ticket_acilir_kimlikler_dolar(istemci, yonetici):
    y = istemci.post("/api/ticket", headers=yonetici, json={
        "bina_serial": "BN-0000362608", "konu": "SİNYAL", "ekip": "+905551234567",
        "musteri": "24954671, 56696369", "kanal": "deha"})
    assert y.status_code == 201, y.text
    t = y.json()["ticket"]
    assert t["durum"] == "AÇIK" and t["acik"] is True
    assert t["location_id"] == "O25265408" and t["site"] == "MERSA SİT. D BLK. MERSA D"
    assert t["metin"] == KULLANICI_ORNEGI and t["kanal"] == "DEHA"
    assert t["bina"]["bolge"] == 5
    # Bina kartında görünür
    kart = istemci.get("/api/bina/BN-0000362608", headers=yonetici).json()
    assert [x["id"] for x in kart["ticketlar"]] == [t["id"]]


def test_durum_degisikligi_notuyla_iz_birakir(istemci, yonetici):
    tid = istemci.post("/api/ticket", headers=yonetici, json={
        "bina_serial": "BN-0000362608", "konu": "EK SP"}).json()["ticket"]["id"]
    y = istemci.patch(f"/api/ticket/{tid}", headers=yonetici,
                      json={"ticket_no": "10131790029", "notu": "OneDesk'te açıldı"})
    assert y.status_code == 200 and y.json()["ticket"]["ticket_no"] == "10131790029"
    y = istemci.patch(f"/api/ticket/{tid}", headers=yonetici, json={"durum": "çözüldü", "notu": "Mail geldi"})
    t = y.json()["ticket"]
    assert t["durum"] == "ÇÖZÜLDÜ" and t["kapanis"] and t["acik"] is False
    y = istemci.patch(f"/api/ticket/{tid}", headers=yonetici, json={"durum": "AÇIK", "notu": "Tekrar açıldı"})
    assert y.json()["ticket"]["kapanis"] is None
    gecmis = istemci.get(f"/api/ticket/{tid}", headers=yonetici).json()["gecmis"]
    assert [g["yeni_durum"] for g in gecmis] == ["AÇIK", "AÇIK", "ÇÖZÜLDÜ", "AÇIK"]
    assert [g["notu"] for g in gecmis][1:] == ["OneDesk'te açıldı", "Mail geldi", "Tekrar açıldı"]
    assert gecmis[1]["alanlar"] == {"ticket_no": [None, "10131790029"]}
    # Değişiklik yoksa iz de yok
    assert istemci.patch(f"/api/ticket/{tid}", headers=yonetici, json={"durum": "AÇIK"}).json()["degisti"] is False


def test_liste_suzgec_arama_ve_sayilar(istemci, yonetici):
    for konu, durum in (("SİNYAL", "AÇIK"), ("EK SP", "HATA"), ("SİNYAL", "KAPATILDI")):
        istemci.post("/api/ticket", headers=yonetici, json={"bina_serial": "BN-0000362608", "konu": konu,
                                                            "durum": durum, "detay": f"deneme {konu}"})
    l = istemci.get("/api/ticket", headers=yonetici).json()
    assert l["toplam"] == 3 and l["acik_toplam"] == 2
    assert l["sayilar"]["KAPATILDI"] == 1 and l["acik_konu"]["SİNYAL"] == 1
    assert l["ticketlar"][-1]["durum"] == "KAPATILDI"          # açıklar önce
    assert istemci.get("/api/ticket", headers=yonetici, params={"konu": "ek sp"}).json()["toplam"] == 1
    assert istemci.get("/api/ticket", headers=yonetici, params={"acik": "true"}).json()["toplam"] == 2
    assert istemci.get("/api/ticket", headers=yonetici, params={"q": "O25265408"}).json()["toplam"] == 3
    assert istemci.get("/api/ticket", headers=yonetici, params={"bolge": 5}).json()["toplam"] == 3
    assert istemci.get("/api/ticket", headers=yonetici, params={"durum": "uydurma"}).status_code == 400
    h = istemci.get("/api/ticket/harita", headers=yonetici).json()
    assert h == {"serial": ["BN-0000362608"], "acik": [2]}


def test_gecersiz_konu_ve_olmayan_bina(istemci, yonetici):
    assert istemci.post("/api/ticket", headers=yonetici, json={"konu": "kahve"}).status_code == 400
    y = istemci.post("/api/ticket", headers=yonetici, json={"konu": "SİNYAL", "bina_serial": "BN-YOK"})
    assert y.status_code == 404
    assert istemci.patch("/api/ticket/9999", headers=yonetici, json={"durum": "AÇIK"}).status_code == 404


def test_ticket_yetkileri(istemci, satisci1, yonetici, conn):
    tid = istemci.post("/api/ticket", headers=yonetici, json={
        "bina_serial": "BN-0000362608", "konu": "SİNYAL"}).json()["ticket"]["id"]
    assert istemci.get("/api/ticket", headers=satisci1).status_code == 403
    assert istemci.post("/api/ticket", headers=satisci1, json={"konu": "SİNYAL"}).status_code == 403
    assert istemci.patch(f"/api/ticket/{tid}", headers=satisci1, json={"durum": "İPTAL"}).status_code == 403
    # BN-0000362608 5. bölgede: 1. bölgenin satışçısı göremez
    assert istemci.get("/api/bina/BN-0000362608/ticket", headers=satisci1).status_code == 403
    assert istemci.get("/api/ticket/sablon", headers=satisci1,
                       params={"bina_serial": "BN-0000362608"}).status_code == 403
    kendi = conn.execute("SELECT bina_serial FROM bina WHERE bolge=1 LIMIT 1").fetchone()[0]
    y = istemci.get(f"/api/bina/{kendi}/ticket", headers=satisci1)
    assert y.status_code == 200 and y.json()["ticketlar"] == []
    assert istemci.get("/api/ticket/sablon", headers=satisci1, params={"bina_serial": kendi}).status_code == 200


def test_lokasyon_eslestirme_sifirli_ve_ekli_yazimlar(conn):
    assert ticket.lokasyondan_bina(conn, "00113680")["location_id"] == "00113680"
    assert ticket.lokasyondan_bina(conn, "113680")["location_id"] == "00113680"
    assert ticket.lokasyondan_bina(conn, "O27592861-1")["bina_serial"] == "BN0001010222"
    assert ticket.lokasyondan_bina(conn, "YOK-123") is None


PS26 = ticket_aktar.VARSAYILAN_DOSYA


@pytest.mark.skipif(not Path(PS26).exists(), reason="PS26/data.xlsx bu bilgisayarda yok")
def test_excel_ticket_aktarimi_bir_kez_yazar(conn):
    satirlar = ticket_aktar.satirlari_oku(PS26)
    ilk = ticket_aktar.aktar(conn, satirlar)
    assert ilk["okunan"] == len(satirlar) >= 190
    assert ilk["eklenen"] == len(satirlar) and ilk.get("zaten_var", 0) == 0
    assert ilk["binaya_baglanan"] >= len(satirlar) - 2
    ikinci = ticket_aktar.aktar(conn, satirlar)
    assert ikinci.get("eklenen", 0) == 0 and ikinci["zaten_var"] == len(satirlar)
    assert conn.execute("SELECT COUNT(*) FROM ticket").fetchone()[0] == len(satirlar)
    assert conn.execute("SELECT COUNT(*) FROM ticket_gecmis").fetchone()[0] == len(satirlar)
    # Excel'deki sıfırlı Lokasyon ('00145672') binaya bağlandı
    r = conn.execute("SELECT bina_serial, location_id FROM ticket WHERE location_id='00145672'").fetchone()
    assert r and r["bina_serial"]


@pytest.mark.skipif(not Path(PS26).exists(), reason="PS26/data.xlsx bu bilgisayarda yok")
def test_excel_kullanilmaya_devam_ederken_numara_ve_durum_esitlenir(istemci, yonetici, conn):
    """Excel'de sonradan yazılan OneDesk numarası / durum yeni ticket açmaz, var olanı günceller;
    uygulamada elle değiştirilmiş ticket'ı Excel EZMEZ."""
    satirlar = ticket_aktar.satirlari_oku(PS26)
    ticket_aktar.aktar(conn, satirlar)
    toplam = conn.execute("SELECT COUNT(*) FROM ticket").fetchone()[0]
    i = next(i for i, r in enumerate(satirlar) if not r["Ticket"] and r["Lokasyon"])
    j = next(j for j, r in enumerate(satirlar) if j != i and r["Durum"].upper() in ("AÇIK", "ACIK") and r["Lokasyon"])
    tid_j = conn.execute("SELECT id FROM ticket WHERE aktarim_anahtari LIKE ? ORDER BY id",
                         (f"excel:{ticket_aktar._anahtar(satirlar[j])}:%",)).fetchone()[0]
    # j. ticket uygulamada elle kapatıldı
    istemci.patch(f"/api/ticket/{tid_j}", headers=yonetici, json={"durum": "ÇÖZÜLDÜ", "notu": "mail geldi"})

    satirlar[i] = {**satirlar[i], "Ticket": "10199999999", "Durum": "ÇÖZÜLDÜ"}
    satirlar[j] = {**satirlar[j], "Durum": "HATA"}
    s = ticket_aktar.aktar(conn, satirlar)
    assert s.get("eklenen", 0) == 0 and s["guncellenen"] == 1 and s["uygulamada_degismis"] == 1
    assert conn.execute("SELECT COUNT(*) FROM ticket").fetchone()[0] == toplam
    t = conn.execute("SELECT ticket_no, durum, kapanis FROM ticket WHERE ticket_no='10199999999'").fetchone()
    assert t["durum"] == "ÇÖZÜLDÜ" and t["kapanis"]
    assert conn.execute("SELECT durum FROM ticket WHERE id=?", (tid_j,)).fetchone()[0] == "ÇÖZÜLDÜ"
