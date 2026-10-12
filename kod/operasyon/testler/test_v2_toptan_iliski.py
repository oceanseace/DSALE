"""Toptan müşteride ilişki ABONE düzeyinde (10.10) · ↻ tekrar gelen iş · ticket BÖLGE durumu · "Bağlı iş kapandı".

Toptan müşteri (tek müşteri no yüzlerce abone; ör. 23722338 Doping Arıza Bildirimi): işler müşteri no ile DEĞİL, BOSS
``locationUnitId`` (yoksa Lokasyon ID + adres) ile ilişkilenir; anahtar yoksa ilişki yok. Kural tek yerde
(``operasyon/v2/iliskili.py Iliski``): İlişkili akış sütunu, ⚠ kanal şikâyeti, ↻ tekrar, ilişkili işlerin atama/askıya
dahil edilmesi, ticket iş seçicisinin varsayılanı. Numaralar uydurmadır; BOSS'a istek gönderilmez.
"""
from __future__ import annotations

from operasyon.testler.test_v2_otomatik_planlama import _gorev, _no, _temiz, ortam  # noqa: F401
from operasyon.testler.test_v2_ticket_boss_not import istemci  # noqa: F401
from operasyon.v2 import iliskili
from saha import ticket as tk

TOPTAN = "23700009"


def _toptan(i: int, unit: str | None, task: str = "Doping Arıza Bildirimi", adres: str | None = None) -> dict:
    g = _gorev(i, TOPTAN, task, kanal="VODAFONE NET")
    if unit:
        g["ham"]["locationUnitId"] = unit
    if adres:
        g["adres"] = adres
    return g


def _satirlar(istemci, h) -> dict[str, dict]:
    return {x["boss_task_no"]: x for x in istemci.get("/api/isler", headers=h).json()["isler"]}


def test_toptan_iliskili_akis_yalniz_ayni_abonede(istemci, conn, ortam):  # noqa: F811
    ortam["esitle"]([_toptan(1, "O100"), _toptan(2, "O100", "Fiber Kurulum"), _toptan(3, "O200"),
                     _toptan(4, "O300", "Kanal Şikayeti"),
                     _gorev(7, "91000077"), _gorev(8, "91000077", "TV+ Kurulum")])
    s = _satirlar(istemci, ortam["op"])
    assert s[_no(1)]["iliskili_akis"] == "Fiber Kurulum" and s[_no(1)]["iliskili_isler"] == [_no(2)]
    assert s[_no(3)]["iliskili_akis"] is None, "aynı müşteri no, başka abone: ilişki yok"
    # 4'ün kanal şikâyeti yalnız kendi abonesini uyarır (müşteri no'su aynı olan 1/2/3'ü değil)
    assert not any(u["tur"] == "kanal_sikayeti" for i in (1, 2, 3) for u in s[_no(i)]["uyarilar"])
    # perakende müşteri no ile ilişkili kalır
    assert s[_no(7)]["iliskili_isler"] == [_no(8)]


def test_toptan_abone_anahtari_yoksa_lokasyon_adres(istemci, conn, ortam):  # noqa: F811
    ortam["esitle"]([_toptan(1, None, adres="A Sk. No:1 D:3"), _toptan(2, None, "Fiber Kurulum", adres="A Sk. No:1 D:3"),
                     _toptan(3, None, adres="A Sk. No:1 D:4")])
    s = _satirlar(istemci, ortam["op"])
    assert s[_no(1)]["iliskili_isler"] == [_no(2)]
    assert s[_no(3)]["iliskili_isler"] == []


def test_toptan_iliskili_isler_atamaya_abone_duzeyinde(istemci, conn, ortam):  # noqa: F811
    ortam["esitle"]([_toptan(1, "O100"), _toptan(2, "O100", "Fiber Kurulum"), _toptan(3, "O200")])
    j = istemci.post("/api/isler/iliskili/isler", headers=ortam["op"], json={"is_nolar": [_no(1)]}).json()
    assert [x["task_no"] for x in j["isler"]] == [_no(2)] and j["toptan_atlanan"] == 1
    j = istemci.post("/api/isler/iliskili/isler", headers=ortam["op"], json={"is_nolar": [_no(3)]}).json()
    assert j["isler"] == []


def test_is_anahtarlari():
    assert iliskili.is_anahtarlari("1", False, "U1") == ["m:1"]
    assert iliskili.is_anahtarlari("1", True, "U1") == ["u:U1"]
    assert iliskili.is_anahtarlari("1", True, None, "O5", "No:1") == ["l:O5|NO1"]
    assert iliskili.is_anahtarlari("1", True) == []
    assert iliskili.is_anahtarlari("", False) == []


def test_ticket_secici_toptanda_varsayilan_secmez(istemci, conn, ortam):  # noqa: F811
    ortam["esitle"]([_toptan(1, "O100", "Fiber Kurulum"), _toptan(2, "O200", "Fiber Kurulum"),
                     _gorev(7, "91000077")])
    s = tk.is_secenekleri(conn, musteri=TOPTAN)
    assert s["toptan"] is True and s["varsayilan"] == []
    s = tk.is_secenekleri(conn, musteri="91000077")
    assert s["toptan"] is False and s["varsayilan"] == [_no(7)]


# ============================================================================= ↻ tekrar gelen iş
def _kapat(conn, i: int, kapanis: str) -> None:
    conn.execute("UPDATE is_emri SET durum='kapandi', kapanis=? WHERE is_no=?", (kapanis, _no(i)))
    conn.commit()


def test_tekrar_gelen_ariza(istemci, conn, ortam):  # noqa: F811
    eski = _gorev(1, "91000088", "Bağlantı Problemi")
    eski["acilis"] = "2026-09-01 09:00:00"
    yeni = _gorev(2, "91000088", "Bağlantı Problemi")              # açılış 30.09
    kurulum = _gorev(3, "91000088", "TV+ Kurulum")                  # arıza değil: ↻ yok
    cok_eski = _gorev(4, "91000089", "TV+ Arıza")
    cok_eski["acilis"] = "2026-07-01 09:00:00"
    yeni2 = _gorev(5, "91000089", "TV+ Arıza")
    ortam["esitle"]([eski, yeni, kurulum, cok_eski, yeni2])
    _kapat(conn, 1, "2026-09-20 10:00:00")
    _kapat(conn, 4, "2026-08-01 10:00:00")                          # 30 günden eski
    s = _satirlar(istemci, ortam["op"])
    t = [u for u in s[_no(2)]["uyarilar"] if u["tur"] == "tekrar"]
    assert t and t[0]["metin"] == f"30 gün içinde tekrar · önceki {_no(1)} kapanış 20.09" and t[0]["onceki"] == _no(1)
    assert not [u for u in s[_no(3)]["uyarilar"] if u["tur"] == "tekrar"]
    assert not [u for u in s[_no(5)]["uyarilar"] if u["tur"] == "tekrar"]


def test_tekrar_toptanda_abone_duzeyinde(istemci, conn, ortam):  # noqa: F811
    eski = _toptan(1, "O100", adres="B Sk. 1")
    eski["acilis"] = "2026-09-20 09:00:00"
    ortam["esitle"]([eski, _toptan(2, "O100", adres="B Sk. 1"), _toptan(3, "O200", adres="B Sk. 2")])
    _kapat(conn, 1, "2026-09-25 10:00:00")
    s = _satirlar(istemci, ortam["op"])
    assert [u["tur"] for u in s[_no(2)]["uyarilar"]].count("tekrar") == 1
    assert "tekrar" not in [u["tur"] for u in s[_no(3)]["uyarilar"]], "aynı toptan no, başka abone"


# ============================================================================= ticket: BÖLGE + bağlı iş kapandı
def test_ticket_bolge_durumu_ve_kapanan_is(istemci, conn, ortam):  # noqa: F811
    ortam["esitle"]([_gorev(1, "91000099"), _gorev(2, "91000099", "TV+ Kurulum")])
    r = istemci.post("/api/ticket", headers=ortam["op"], json={
        "konu": "EK SP", "location_id": "O999", "musteri": "91000099", "isler": [_no(1), _no(2)]})
    assert r.status_code == 201, r.text
    tid = r.json()["ticket"]["id"]
    r = istemci.patch(f"/api/ticket/{tid}", headers=ortam["admin"], json={"durum": "BÖLGE"})
    assert r.status_code == 200, r.text
    t = r.json()["ticket"]
    assert t["durum"] == "BÖLGE" and t["acik"] is True, "Bölge çözülmedi sayılır (askı sürer)"
    assert t["isi_kapandi"] is False
    assert tk.durum_coz("Bölgeye iletildi") == "BÖLGE"
    _kapat(conn, 1, "2026-10-08 10:00:00")
    assert istemci.get(f"/api/ticket/{tid}", headers=ortam["op"]).json()["ticket"]["isi_kapandi"] is False
    conn.execute("UPDATE is_emri SET boss_durum='Tamamlandı' WHERE is_no=?", (_no(2),))
    conn.commit()
    t = istemci.get(f"/api/ticket/{tid}", headers=ortam["op"]).json()["ticket"]
    assert t["isi_kapandi"] is True
    liste = istemci.get("/api/ticket", headers=ortam["op"]).json()
    assert liste["sayilar"]["BÖLGE"] == 1 and liste["ticketlar"][0]["isi_kapandi"] is True


def test_bolge_notu_numarasiz():
    from saha import ticket_boss_not as tbn
    assert tbn.not_metni({"durum": "BÖLGE", "ticket_no": ""}) == tbn.NOT_BOLGE
    assert tbn.not_metni({"durum": "BÖLGE", "ticket_no": "77"}) == tbn.NOT_NUMARALI.format(ticket_no="77")
    assert tbn.not_metni({"durum": "ÇÖZÜLDÜ", "ticket_no": "77"}) is None
