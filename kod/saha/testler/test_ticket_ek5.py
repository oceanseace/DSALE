"""Ticket ekibi ve başlıkları (Ek-5, G10) + Ek-12/7 süreç ayarları: hepsi ayar, koda gömülü değil."""
from __future__ import annotations

import json

from saha import db, sema_v2


def test_kategoriler_varsayilanlari(istemci, yonetici):
    y = istemci.get("/api/ticket/kategoriler", headers=yonetici)
    assert y.status_code == 200
    v = y.json()
    assert v["varsayilan_ekip"] == "TEAM-TAS1BRS"
    assert v["ekipler"] == ["TEAM-TAS1BRS", "TEAM-TAS1KOC"]        # Yalova'nın BÇO'su belirsiz (Ek-12/7)
    assert [k["ad"] for k in v["kategoriler"]] == sema_v2.TICKET_KATEGORILERI
    oneriler = {k["ad"]: k["konu_onerisi"] for k in v["kategoriler"]}
    assert oneriler["NETWORK / GPON / SINYAL YOK / MEVCUT BINA"] == "SİNYAL"       # sinyal şablonu önerilir
    assert oneriler["NETWORK / GPON / SINYAL VAR / IP ALAMIYOR"] is None
    assert oneriler["NETWORK \\ EK SWITCH VE SPLITER TALEBI"] == "EK SP"
    assert {a["anahtar"] for a in v["zorunlu_alanlar"]} >= {"musteri_no", "hizmet_id", "seri_no", "ekran_goruntusu"}
    assert v["bco_hatirlatma_saat"] == 24
    assert v["kirmizi_hat_konu_sablonu"] == "{task_no} / {task_adi} / Kırmızı Hat"


def test_kategoriler_ayardan_gelir(istemci, yonetici, conn):
    db.ayar_yaz(conn, "ticket_kategorileri", json.dumps(["NETWORK / DENEME"]))
    db.ayar_yaz(conn, "ticket_ekipleri", json.dumps(["TEAM-X", "TEAM-Y"]))
    db.ayar_yaz(conn, "ticket_varsayilan_ekip", "TEAM-Y")
    db.ayar_yaz(conn, "ticket_bco_hatirlatma_saat", "36")
    conn.commit()
    v = istemci.get("/api/ticket/kategoriler", headers=yonetici).json()
    assert [k["ad"] for k in v["kategoriler"]] == ["NETWORK / DENEME"]
    assert v["ekipler"] == ["TEAM-X", "TEAM-Y"] and v["varsayilan_ekip"] == "TEAM-Y"
    assert v["bco_hatirlatma_saat"] == 36
    # Ayar silinmiş/bozuksa varsayılana düşer (v8'den sonra eklenen anahtarlar eski kurulumda yoktur).
    conn.execute("DELETE FROM ayar WHERE anahtar IN ('ticket_kategorileri','ticket_zorunlu_alanlar')")
    db.ayar_yaz(conn, "ticket_bco_hatirlatma_saat", "yirmi")
    conn.commit()
    v = istemci.get("/api/ticket/kategoriler", headers=yonetici).json()
    assert len(v["kategoriler"]) == len(sema_v2.TICKET_KATEGORILERI)
    assert v["zorunlu_alanlar"] and v["bco_hatirlatma_saat"] == 24


def test_kategoriler_herkese_acik_ticket_defteri_degil(istemci, satisci1, kisi):
    """Başlık listesi ticket şablonu gibi herkese açıktır (satış binadan şablon üretir); defter değil."""
    assert istemci.get("/api/ticket/kategoriler", headers=satisci1).status_code == 200
    _, teknik = kisi("teknik")
    assert istemci.get("/api/ticket/kategoriler", headers=teknik).status_code == 200
    assert istemci.get("/api/ticket", headers=teknik).status_code == 403


def test_yeni_ticket_ekip_ve_baslik_saklanir(istemci, yonetici):
    y = istemci.post("/api/ticket", headers=yonetici, json={
        "bina_serial": "BN-0000362608", "konu": "SİNYAL",
        "onedesk_ekip": "TEAM-TAS1KOC", "kategori": "NETWORK / GPON / SINYAL YOK / MEVCUT BINA"})
    assert y.status_code == 201
    t = y.json()["ticket"]
    assert t["onedesk_ekip"] == "TEAM-TAS1KOC"
    assert t["kategori"] == "NETWORK / GPON / SINYAL YOK / MEVCUT BINA"
    # Başlık sonradan değişir; geçmişe alan olarak düşer.
    y = istemci.patch(f"/api/ticket/{t['id']}", headers=yonetici,
                      json={"kategori": "NETWORK / FTTB / SW ARIZA", "onedesk_ekip": "TEAM-TAS1BRS"})
    assert y.status_code == 200
    t2 = y.json()["ticket"]
    assert t2["kategori"] == "NETWORK / FTTB / SW ARIZA" and t2["onedesk_ekip"] == "TEAM-TAS1BRS"
    gecmis = istemci.get(f"/api/ticket/{t['id']}", headers=yonetici).json()["gecmis"]
    assert set(gecmis[-1]["alanlar"]) == {"kategori", "onedesk_ekip"}


def test_ekip_secilmezse_varsayilan_ekip(istemci, yonetici, conn):
    t = istemci.post("/api/ticket", headers=yonetici,
                     json={"bina_serial": "BN-0000362608", "konu": "EK SP"}).json()["ticket"]
    assert t["onedesk_ekip"] == "TEAM-TAS1BRS"
    db.ayar_yaz(conn, "ticket_varsayilan_ekip", "TEAM-TAS1KOC")
    conn.commit()
    t = istemci.post("/api/ticket", headers=yonetici,
                     json={"bina_serial": "BN-0000362608", "konu": "EK SP"}).json()["ticket"]
    assert t["onedesk_ekip"] == "TEAM-TAS1KOC"


def test_excel_aktarimi_ekip_uydurmaz(conn):
    """Excel'den (PS26 TICKET sayfası) gelen satırda ekip yoksa boş kalır: bilmediğimizi yazmayız."""
    from saha import ticket

    tid, _ = ticket.olustur(conn, {"konu": "SİNYAL", "bina_serial": "BN-0000362608"}, None, kaynak="excel",
                            aktarim_anahtari="deneme-1")
    conn.commit()
    assert ticket.getir(conn, tid)["onedesk_ekip"] == ""
