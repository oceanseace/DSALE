"""Ticket izinleri ikiye ayrıldı: ``ticket.oku`` (liste, ayrıntı, fotoğraf, harita) · ``ticket.defter`` (aç, düzenle,
durum, sil, iş bağla). Satış Destek unvanları varsayılan olarak yalnız "Ticket izleme" (salt okunur) alır; v11 göçü
canlı veritabanında Ticket defteri → Ticket izleme yapar. Numaralar uydurmadır.
"""
from __future__ import annotations

import sqlite3

from saha import ayarlar, goc, sema_v2, yetki

from .test_administrator import yeni_kisi  # noqa: F401 — fixture


def _ticket(conn) -> int:
    tid = conn.execute(
        "INSERT INTO ticket (konu, durum, musteri, olusturma, guncelleme) VALUES ('SİNYAL','AÇIK','70000001',?,?)",
        (ayarlar.zaman_metni(), ayarlar.zaman_metni())).lastrowid
    conn.commit()
    return int(tid)


def test_ticket_izleme_salt_okunur(istemci, conn, yeni_kisi):  # noqa: F811
    tid = _ticket(conn)
    _kid, kb = yeni_kisi(ek=["ticket_izleme"])
    assert istemci.get("/api/ticket", headers=kb).status_code == 200
    assert istemci.get(f"/api/ticket/{tid}", headers=kb).status_code == 200
    assert istemci.get("/api/ticket/harita", headers=kb).status_code == 200
    assert istemci.get(f"/api/ticket/{tid}/ek", headers=kb).status_code == 200
    # yazma: hepsi 403
    assert istemci.patch(f"/api/ticket/{tid}", json={"durum": "ÇÖZÜLDÜ"}, headers=kb).status_code == 403
    assert istemci.post("/api/ticket", json={"konu": "SİNYAL", "musteri": "70000002"}, headers=kb).status_code == 403
    assert istemci.post(f"/api/ticket/{tid}/sil", headers=kb).status_code == 403
    assert istemci.post(f"/api/ticket/{tid}/isler", json={"isler": ["1"]}, headers=kb).status_code == 403
    assert istemci.post(f"/api/ticket/{tid}/isler/cikar", json={"isler": ["1"]},
                        headers=kb).status_code == 403
    assert istemci.get("/api/ticket/isler", params={"q": "1"}, headers=kb).status_code == 403
    assert istemci.get("/api/ticket/temizlik", headers=kb).status_code == 403
    assert conn.execute("SELECT durum FROM ticket WHERE id=?", (tid,)).fetchone()[0] == "AÇIK"


def test_ticket_defteri_okur_ve_yazar(istemci, conn, yeni_kisi):  # noqa: F811
    tid = _ticket(conn)
    _kid, kb = yeni_kisi(ek=["ticket_defteri"])
    assert istemci.get(f"/api/ticket/{tid}", headers=kb).status_code == 200
    assert istemci.patch(f"/api/ticket/{tid}", json={"durum": "HATA"}, headers=kb).status_code == 200


def test_ticket_izleme_paketi():
    assert yetki.paket_izinleri(["ticket_izleme"]) >= {"ticket.oku"}
    assert "ticket.defter" not in yetki.paket_izinleri(["ticket_izleme"])
    assert {"ticket.oku", "ticket.defter"} <= yetki.paket_izinleri(["ticket_defteri"])


def test_satis_destek_varsayilani_salt_okunur():
    tohum = dict(sema_v2.UNVAN_TOHUM)
    for ad, paketler in tohum.items():
        if "Satış Destek" in ad:
            assert "ticket_izleme" in paketler and "ticket_defteri" not in paketler, ad


def test_goc_11_satis_destek_defterini_izlemeye_cevirir():
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        "CREATE TABLE unvan (id INTEGER PRIMARY KEY, ad TEXT, ad_k TEXT);"
        "CREATE TABLE unvan_yetkinlik (unvan_id INTEGER, yetkinlik TEXT, PRIMARY KEY (unvan_id, yetkinlik));"
        "CREATE TABLE kullanici (id INTEGER PRIMARY KEY, unvan_id INTEGER, yetki_modeli INTEGER);")
    for uid, ad in ((1, "EÇM-Fiber- Satış Destek - Sorumlu"), (2, "EÇM-Fiber-Hizmet Danışmanı - Sorumlu")):
        conn.execute("INSERT INTO unvan VALUES (?,?,?)", (uid, ad, yetki.unvan_anahtari(ad)))
        conn.execute("INSERT INTO unvan_yetkinlik VALUES (?, 'ticket_defteri')", (uid,))
    ozet = goc.goc_11_ticket_salt_okunur(conn, {})
    assert ozet == {"unvan": 1}
    assert {r[0] for r in conn.execute("SELECT yetkinlik FROM unvan_yetkinlik WHERE unvan_id=1")} == {"ticket_izleme"}
    assert {r[0] for r in conn.execute("SELECT yetkinlik FROM unvan_yetkinlik WHERE unvan_id=2")} == {"ticket_defteri"}
    assert goc.goc_11_ticket_salt_okunur(conn, {}) == {"unvan": 0}    # ikinci kez etkisiz
