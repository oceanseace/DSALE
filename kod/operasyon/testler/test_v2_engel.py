"""Kurulum engeli: Bizim durum Port yok · Kıl yok · Sinyal yok · Güzergah yok → iş ertelenir ('altyapi') ve aynı
Loc ID + konu için altyapı ticket'ı açılır ya da açık olana bağlanır; ticket çözülünce işler "Aranacak"a döner;
"İptal" edilen iş takip edilmez; her adım etkisizdir. Loc ID ve numaralar uydurmadır."""
from __future__ import annotations

import pytest

from operasyon.testler import yardim as y
from operasyon.v2 import akis, gorunum
from saha import ticket as tk

LOC = "ZZ90000001"            # bina tablosunda olmayan uydurma Loc ID (kopyadaki ticket'larla karışmasın)


def _isler(v2db, conn, n=3, lokasyon=LOC):
    y.aktar(v2db, [y.satir(i, lokasyon=lokasyon, mahalle="Görükle") for i in range(1, n + 1)])
    return sorted(r[0] for r in conn.execute("SELECT is_no FROM is_emri WHERE lokasyon=?", (lokasyon,)))


def _is(conn, no):
    return conn.execute("SELECT * FROM is_emri WHERE is_no=?", (no,)).fetchone()


def _engel_ticketlari(conn):
    return conn.execute("SELECT * FROM ticket WHERE location_id=? ORDER BY id", (LOC,)).fetchall()


def test_bizim_durumlarda_kil_yok_var():
    assert "Kıl yok" in akis.BIZIM_DURUMLAR
    assert akis.ENGEL_KONU == {"Port yok": "EK SP", "Kıl yok": "EK SP", "Sinyal yok": "SİNYAL",
                               "Güzergah yok": "GÜZERGAH"}
    assert set(akis.ENGEL_KONU.values()) <= set(tk.KONULAR)


def test_engel_ticket_acar_isi_erteler(v2db, conn, kim):
    n1, *_ = _isler(v2db, conn)
    op = kim("operasyon")
    r0 = _is(conn, n1)
    a = akis.bizim_durum_yaz(conn, n1, op, "Port yok", surum=r0["surum"])
    assert a["bizim_durum"] == "Port yok" and a["durum"] == "altyapi" and a["ticket"]["konu"] == "EK SP"
    t = _engel_ticketlari(conn)
    assert len(t) == 1 and t[0]["konu"] == "EK SP" and t[0]["durum"] == "AÇIK"
    assert t[0]["musteri"] == r0["musteri_no"] and "Port yok" in t[0]["detay"] and r0["boss_task_no"] in t[0]["detay"]
    kart = tk.getir(conn, t[0]["id"])
    assert kart["task_no"] == r0["boss_task_no"] and kart["task_adi"] == r0["task_adi"] and kart["bekleyen_is"] == 1
    notlar = [x[0] for x in conn.execute("SELECT notu FROM is_emri_olay WHERE is_no=? ORDER BY id", (n1,))]
    assert any(n.startswith("Ertelendi (kurulum engeli: Port yok)") for n in notlar if n)
    # TASKS uyarısı aynı açık-ticket kaynağından
    assert any(u["tur"] == "altyapi" for u in gorunum.ayrinti(conn, n1, op)["uyarilar"])


def test_ayni_loc_ve_konu_acik_ticketa_baglanir(v2db, conn, kim):
    n1, n2, n3 = _isler(v2db, conn)
    op = kim("operasyon")
    akis.bizim_durum_yaz(conn, n1, op, "Port yok")
    akis.bizim_durum_yaz(conn, n2, op, "Kıl yok")                 # aynı konu (EK SP): aynı ticket
    akis.bizim_durum_yaz(conn, n3, op, "Sinyal yok")              # başka konu: yeni ticket
    t = _engel_ticketlari(conn)
    assert [x["konu"] for x in t] == ["EK SP", "SİNYAL"]
    assert _is(conn, n1)["ticket_id"] == _is(conn, n2)["ticket_id"] == t[0]["id"]
    assert _is(conn, n3)["ticket_id"] == t[1]["id"]
    assert tk.musteri_nolari(t[0]["musteri"]) == [_is(conn, n1)["musteri_no"], _is(conn, n2)["musteri_no"]]
    assert tk.bekleyen_isler(conn, [t[0]["id"], t[1]["id"]]) == {t[0]["id"]: 2, t[1]["id"]: 1}
    liste = {x["id"]: x for x in tk.liste(conn, acik=True, q=LOC)["ticketlar"]}
    assert liste[t[0]["id"]]["bekleyen_is"] == 2


def test_etkisiz_ayni_deger_yeniden(v2db, conn, kim):
    n1, *_ = _isler(v2db, conn, n=1)
    op = kim("operasyon")
    akis.bizim_durum_yaz(conn, n1, op, "Güzergah yok")
    ozet = (conn.execute("SELECT COUNT(*) FROM ticket").fetchone()[0],
            conn.execute("SELECT COUNT(*) FROM is_emri_olay WHERE is_no=?", (n1,)).fetchone()[0],
            conn.execute("SELECT COUNT(*) FROM ticket_gecmis").fetchone()[0], _is(conn, n1)["surum"])
    akis.bizim_durum_yaz(conn, n1, op, "Güzergah yok")
    assert ozet == (conn.execute("SELECT COUNT(*) FROM ticket").fetchone()[0],
                    conn.execute("SELECT COUNT(*) FROM is_emri_olay WHERE is_no=?", (n1,)).fetchone()[0],
                    conn.execute("SELECT COUNT(*) FROM ticket_gecmis").fetchone()[0], _is(conn, n1)["surum"])
    assert _engel_ticketlari(conn)[0]["konu"] == "GÜZERGAH"


def test_cozulunce_aranacak_iptal_takip_edilmez(v2db, conn, kim):
    n1, n2, n3 = _isler(v2db, conn)
    op = kim("operasyon")
    for no in (n1, n2):
        akis.bizim_durum_yaz(conn, no, op, "Port yok")
    akis.bizim_durum_yaz(conn, n2, op, "İptal")                   # müşteri vazgeçti
    tid = _is(conn, n1)["ticket_id"]
    assert tk.bekleyen_isler(conn, [tid]) == {tid: 1}             # iptal sayılmaz
    tk.guncelle(conn, tid, {"durum": "ÇÖZÜLDÜ"}, op["id"])
    conn.commit()
    assert akis.ticket_degisti(conn, tid, op) == [n1, n2]         # iki iş de havuza döner …
    r1, r2 = _is(conn, n1), _is(conn, n2)
    assert (r1["durum"], r1["bizim_durum"]) == ("bekliyor", "Aranacak")
    assert (r2["durum"], r2["bizim_durum"]) == ("bekliyor", "İptal")  # … ama iptal edilen aranmaz
    son = conn.execute("SELECT notu FROM is_emri_olay WHERE is_no=? ORDER BY id DESC LIMIT 1", (n1,)).fetchone()[0]
    assert son == "Altyapı çözüldü, yeniden aranacak"
    assert akis.ticket_degisti(conn, tid, op) == []               # etkisiz
    assert akis.ticket_denetimi(conn) == []
    # çözülmüş ticket'a yeniden bağlanmaz: aynı engel yeni ticket açar
    akis.bizim_durum_yaz(conn, n3, op, "Port yok")
    assert _is(conn, n3)["ticket_id"] != tid and len(_engel_ticketlari(conn)) == 2


def test_ticket_iptal_edilirse_etiket_kalir(v2db, conn, kim):
    n1, *_ = _isler(v2db, conn, n=1)
    op = kim("operasyon")
    akis.bizim_durum_yaz(conn, n1, op, "Sinyal yok")
    tid = _is(conn, n1)["ticket_id"]
    tk.guncelle(conn, tid, {"durum": "İPTAL"}, op["id"])
    conn.commit()
    assert akis.ticket_degisti(conn, tid, op) == [n1]
    assert (_is(conn, n1)["durum"], _is(conn, n1)["bizim_durum"]) == ("bekliyor", "Sinyal yok")


def test_kapanmis_iste_yalniz_etiket(v2db, conn, kim):
    n1, *_ = _isler(v2db, conn, n=1)
    conn.execute("UPDATE is_emri SET durum='cozuldu' WHERE is_no=?", (n1,))
    conn.commit()
    a = akis.bizim_durum_yaz(conn, n1, kim("operasyon"), "Port yok")
    assert a["bizim_durum"] == "Port yok" and a["durum"] == "cozuldu" and not _engel_ticketlari(conn)


@pytest.fixture
def tam_istemci(v2db):
    """v2 yönlendiricileri + ticket defteri uçları (saha.yonetim_uclari) — PATCH /api/ticket ile uçtan uca."""
    from fastapi.testclient import TestClient

    from operasyon.testler.conftest import uygulama
    from saha import yonetim_uclari

    app = uygulama()
    app.include_router(yonetim_uclari.yonlendirici)
    with TestClient(app) as c:
        yield c


def test_uclar_uctan_uca(tam_istemci, jeton, v2db, conn, kisi):
    istemci = tam_istemci
    n1, *_ = _isler(v2db, conn, n=1)
    h = jeton(kisi["operasyon"])
    r = istemci.post(f"/api/isler/{n1}/bizim-durum", headers=h, json={"deger": "Kıl yok", "surum": _is(conn, n1)["surum"]})
    assert r.status_code == 200, r.text
    assert r.json()["durum"] == "altyapi" and r.json()["ticket"]["konu"] == "EK SP"
    tid = r.json()["ticket"]["id"]
    v = istemci.get("/api/ticket", headers=h, params={"acik": "true", "q": LOC}).json()
    assert [(t["id"], t["bekleyen_is"]) for t in v["ticketlar"]] == [(tid, 1)], v
    x = next(i for i in istemci.get("/api/isler", headers=h).json()["isler"] if i["is_no"] == n1)
    assert any(u["tur"] == "altyapi" for u in x["uyarilar"])
    d = istemci.patch(f"/api/ticket/{tid}", headers=h, json={"durum": "ÇÖZÜLDÜ"})
    assert d.status_code == 200 and d.json()["bekliyora_donen_is"] == 1
    assert (_is(conn, n1)["durum"], _is(conn, n1)["bizim_durum"]) == ("bekliyor", "Aranacak")
    x = next(i for i in istemci.get("/api/isler", headers=h).json()["isler"] if i["is_no"] == n1)
    assert not any(u["tur"] == "altyapi" for u in x["uyarilar"])     # çözülen ticket uyarı üretmez


@pytest.mark.parametrize("deger", ["Aranacak", "Randevulu", "Kuruldu"])
def test_engel_olmayan_deger_akisa_dokunmaz(v2db, conn, kim, deger):
    n1, *_ = _isler(v2db, conn, n=1)
    once = _is(conn, n1)["durum"]
    a = akis.bizim_durum_yaz(conn, n1, kim("operasyon"), deger)
    assert a["durum"] == once and not _engel_ticketlari(conn)
