"""İş türüne göre ayır + kuralla ofis çalışanına dağıt (dagitim_is / dagitim_kural)."""
from __future__ import annotations

import pytest

from operasyon.testler import yardim as y
from operasyon.v2 import dagitim
from operasyon.v2.hatalar import V2Hata


def _rapor(v2db):
    return y.aktar(v2db, [
        y.satir(1, task="TV+ Arıza", kanal="GLOBAL CC"),
        y.satir(2, task="Fiber Kurulum", kanal="GLOBAL CC"),
        y.satir(3, task="Bağlantı Problemi", kanal="DEHA TEL. INS.TEKS.NAK.PET.TUK.LTD.STI."),
        y.satir(4, task="Kanal Şikayeti", kanal="GLOBAL CC"),
    ])


def _no(i):
    return f"{400000000 + i}"


def _sorumlu(conn, i):
    return conn.execute("SELECT sorumlu_id FROM dagitim_is WHERE task_no=?", (_no(i),)).fetchone()[0]


def test_eslesme_turkce_harf_duyarsiz():
    veri = {"Task Adı": "TV+ Arıza", "Satış Kanalı": "DEHA TEL. İNŞ.", "İl": "İSTANBUL"}
    assert dagitim.eslesir([{"sutun": "Task Adı", "degerler": ["tv+ ariza"]}], veri)
    assert dagitim.eslesir([{"sutun": "Satış Kanalı", "icerir": "deha"}], veri)
    assert dagitim.eslesir([{"sutun": "İl", "degerler": ["istanbul"]}], veri)
    assert not dagitim.eslesir([{"sutun": "Satış Kanalı", "icerir": "deha"},
                                {"sutun": "Task Adı", "degerler": ["Kanal Şikayeti"]}], veri)   # VE
    assert dagitim.eslesir([{"sutun": "Yok", "degerler": [""]}], veri)                          # (Boş)


@pytest.mark.skip(reason="Tek iş havuzu (2026-10): kurulum/2. donanım çıkarma ve öbeksiz→Kontrol kuralı kaldırıldı")
def test_kurulum_yeni_musteri_ve_ariza_akisi_bozulmaz(v2db, conn):
    _rapor(v2db)
    assert conn.execute("SELECT COUNT(*) FROM is_emri").fetchone()[0] == 3      # kurulum arıza hattına girmez
    turler = dict(conn.execute("SELECT task_no, tur FROM dagitim_is"))
    assert len(turler) == 4 and turler[_no(2)] == "yeni" and turler[_no(1)] == "mevcut"
    y_ = dagitim.liste(conn)
    assert y_["sutunlar"][0] == dagitim.TUR_SUTUNU and "Task Adı" in y_["sutunlar"]
    assert y_["dagitilmamis"] == 4


def test_siralama_ilk_eslesen_ve_otomatik_uygulama(v2db, conn, kisi, kim):
    op, yon = kisi["operasyon"], kisi["yonetici"]
    _rapor(v2db)
    dagitim.kurallari_yaz(conn, [
        {"ad": "Deha", "kosullar": [{"sutun": "Satış Kanalı", "icerir": "deha"}], "kisi_id": yon},
        {"ad": "Arızalar", "kosullar": [{"sutun": "Müşteri Türü", "degerler": ["Mevcut Müşteri"]}], "kisi_id": op},
        {"ad": "TV", "kosullar": [{"sutun": "Task Adı", "degerler": ["TV+ ARIZA"]}], "kisi_id": yon},
    ], kim("operasyon"))
    s = dagitim.uygula(conn)
    assert s["atanan"] == 3 and s["dagitilmamis"] == 1
    assert _sorumlu(conn, 3) == yon          # Deha ilk sırada
    assert _sorumlu(conn, 1) == op           # TV kuralı daha aşağıda: "Arızalar" kazanır
    assert _sorumlu(conn, 2) is None         # kurulum: Dağıtılmamış
    # elle verilen sorumlu kuralla ezilmez; yeni rapordaki yeni iş kendiliğinden dağıtılır
    dagitim.elle_ata(conn, [_no(4)], yon, kim("operasyon"))
    y.aktar(v2db, [y.satir(1, task="TV+ Arıza"), y.satir(2, task="Fiber Kurulum"),
                   y.satir(3, task="Bağlantı Problemi", kanal="DEHA TEL."), y.satir(4, task="Kanal Şikayeti"),
                   y.satir(5, task="Modem Değişikliği", kanal="Deha Tel")])
    assert _sorumlu(conn, 5) == yon and _sorumlu(conn, 4) == yon
    # sıra değişince yeni işlerde yeni sıra geçerli
    ks = [k for k in dagitim.liste(conn)["kurallar"]]
    dagitim.kurallari_yaz(conn, [ks[2], ks[1], ks[0]], kim("operasyon"))
    assert [k["ad"] for k in dagitim.liste(conn)["kurallar"]] == ["TV", "Arızalar", "Deha"]
    dagitim.elle_ata(conn, [_no(1)], None, kim("operasyon"))
    dagitim.uygula(conn)
    assert _sorumlu(conn, 1) == yon


def test_kapanan_is_dagitilmaz(v2db, conn, kisi, kim):
    y.aktar(v2db, [y.satir(1, task="TV+ Arıza", durum="Bitirildi"), y.satir(2, task="TV+ Arıza")])
    dagitim.kurallari_yaz(conn, [{"ad": "TV", "kosullar": [{"sutun": "Task Adı", "degerler": ["TV+ Arıza"]}],
                                  "kisi_id": kisi["operasyon"]}], kim("operasyon"))
    assert dagitim.uygula(conn)["atanan"] == 1 and _sorumlu(conn, 1) is None


def test_kural_dogrulama(v2db, conn, kisi, kim):
    with pytest.raises(V2Hata):
        dagitim.kurallari_yaz(conn, [{"ad": "Boş", "kosullar": [], "kisi_id": kisi["operasyon"]}], kim("operasyon"))
    with pytest.raises(V2Hata) as e:
        dagitim.kurallari_yaz(conn, [{"ad": "Teknik", "kosullar": [{"sutun": "Task Adı", "icerir": "tv"}],
                                      "kisi_id": kisi["teknik1"]}], kim("operasyon"))
    assert e.value.kod == "kisi_gecersiz"


def test_goc_once_yedek_alir(v2db, conn):
    conn.execute("DROP TABLE IF EXISTS dagitim_is")
    conn.execute("DROP TABLE IF EXISTS dagitim_kural")
    conn.commit()
    dizin = v2db.parent / "yedek" / "aktarim"
    once = set(dizin.glob("*.db")) if dizin.exists() else set()
    assert dagitim.hazirla(conn) is True
    assert set(dizin.glob("*.db")) - once
    assert dagitim.hazirla(conn) is False


def test_uclar_izin(istemci, jeton, v2db, conn, kisi):
    _rapor(v2db)
    for kim_ in ("satis", "teknik1"):
        h = jeton(kisi[kim_])
        assert istemci.get("/api/dagitim", headers=h).status_code == 403
        assert istemci.post("/api/dagitim/uygula", headers=h).status_code == 403
        assert istemci.put("/api/dagitim/kurallar", headers=h, json={"kurallar": []}).status_code == 403
    h = jeton(kisi["operasyon"])
    g = istemci.get("/api/dagitim", headers=h)
    assert g.status_code == 200 and len(g.json()["satirlar"]) == 4
    assert any(k["id"] == kisi["operasyon"] for k in g.json()["kisiler"])
    r = istemci.put("/api/dagitim/kurallar", headers=h, json={"kurallar": [
        {"ad": "Kurulum", "kosullar": [{"sutun": "Müşteri Türü", "degerler": ["yeni müşteri"]}],
         "kisi_id": kisi["operasyon"]}]})
    assert r.status_code == 200 and r.json()["kurallar"][0]["ad"] == "Kurulum"
    u = istemci.post("/api/dagitim/uygula", headers=h).json()
    assert u["atanan"] == 1 and _sorumlu(conn, 2) == kisi["operasyon"]
    a = istemci.post("/api/dagitim/ata", headers=h, json={"task_nolar": [_no(1)], "kisi_id": kisi["yonetici"]})
    assert a.status_code == 200 and _sorumlu(conn, 1) == kisi["yonetici"]
    from operasyon.v2.api import ROTA_IZNI
    assert ROTA_IZNI[("POST", "/api/dagitim/uygula")] == "is.ata"
