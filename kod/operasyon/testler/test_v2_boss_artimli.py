"""BOSS artımlı eşitleme (parmak izi), telefon önden okuma, eski Excel kalıntısı temizliği, listede telefon."""
from __future__ import annotations

import pytest

from operasyon.testler import yardim as y
from operasyon.v2 import boss, boss_detay, kisi as kisi_mod


def U(i: int) -> str:
    return f"0a1b2c3d-1111-2222-3333-{i:012d}"


@pytest.fixture(autouse=True)
def _temiz():
    boss._ILETISIM_HATA.clear()
    boss_detay.sifirla()
    yield
    boss._ILETISIM_HATA.clear()


def _gorev(i: int, durum="Randevusuz", **ek) -> dict:
    no = f"{400000000 + i}"
    g = {"task_no": no, "task_adi": "Bağlantı Problemi", "durum": durum, "musteri_no": f"9{no[-8:]}",
         "musteri_adi": "Deneme", "adres": f"DENEME APT. Görükle Mh. Test Sk. No:{i} Nilüfer", "il": "Bursa",
         "ilce": "Nilüfer", "acilis": "2026-09-30 09:00:00", "boss_uuid": U(i)}
    g.update(ek)
    g["iz"] = boss.iz_hesapla(g)
    return g


def _durum(conn, i):
    r = conn.execute("SELECT durum, kapanis_nedeni FROM is_emri WHERE boss_task_no=?", (f"{400000000 + i}",)).fetchone()
    return tuple(r) if r else None


def test_fark_modu_yalniz_degisenler_ve_kaldirilan(v2db, conn):
    f = y.fabrika(v2db)
    ilk = [_gorev(i) for i in range(1, 6)]
    s = boss.esitle(f, {"gorevler": ilk, "tam": True})
    assert s["mod"] == "tam" and s["ozet"] == {"yeni": 5, "degisen": 0, "kapanan": 0}
    iz = boss.izler(conn)
    assert not iz["tam_gerekli"] and iz["izler"]["400000001"] == ilk[0]["iz"] and len(iz["izler"]) == 5

    # 2 randevu aldı, 6 yeni, 5 BOSS'tan düştü, 3 tamamlandı
    degisen = [_gorev(2, durum="Randevu alındı", randevu_bas="2026-10-01 10:00:00", randevu_bit="2026-10-01 12:00:00"),
               _gorev(6), _gorev(3, durum="Tamamlandı")]
    s = boss.esitle(f, {"mod": "fark", "gorevler": degisen, "kaldirilan": ["400000005"], "tam": True})
    assert s["mod"] == "fark" and s["tam"] is True
    assert s["ozet"] == {"yeni": 1, "degisen": 1, "kapanan": 2}, s
    assert _durum(conn, 2)[0] == "randevulu" and _durum(conn, 6)[0] in ("bekliyor", "triyaj")
    assert _durum(conn, 3)[0] == "kapandi" and _durum(conn, 5) == ("kapandi", "boss_listeden_dustu")
    assert _durum(conn, 1)[0] != "kapandi" and _durum(conn, 4)[0] != "kapandi"
    iz = boss.izler(conn)["izler"]
    assert "400000005" not in iz and "400000003" not in iz and iz["400000002"] == degisen[0]["iz"]

    # eksik görüntüde kaldirilan kapatmaz
    boss.esitle(f, {"mod": "fark", "gorevler": [], "kaldirilan": ["400000004"], "tam": False})
    assert _durum(conn, 4)[0] != "kapandi"
    d = boss.durum(conn)
    assert d["mod"] == "fark" and "iletisim_toplam" in d


def test_eski_rapor_kalintisi_yedekle_kapanir(v2db, conn):
    # Excel raporundan gelen (BOSS kimliği/izi olmayan) iki iş
    y.aktar(v2db, y.standart(2))
    eski = [r[0] for r in conn.execute("SELECT boss_task_no FROM is_emri WHERE durum NOT IN ('kapandi','cozuldu')")]
    assert len(eski) == 2
    conn.execute("INSERT OR IGNORE INTO dagitim_is (task_no, tur, veri, acik, ilk_gorulme, son_gorulme) "
                 "VALUES (?, 'mevcut', '{}', 1, '2026-09-30 09:00:00', '2026-09-30 09:00:00')", (eski[0],))
    conn.commit()
    yedekler = lambda: list((v2db.parent / "yedek" / "aktarim").glob("*.db")) if (v2db.parent / "yedek" / "aktarim").exists() else []
    once = len(yedekler())
    f = y.fabrika(v2db)
    # eksik görüntü dokunmaz
    boss.esitle(f, {"gorevler": [_gorev(101)], "tam": False})
    assert conn.execute("SELECT COUNT(*) FROM is_emri WHERE kapanis_nedeni='rapor_kalintisi'").fetchone()[0] == 0
    # izler eski işleri "" ile gösterir → eklenti kaldirilan'a koyar
    iz = boss.izler(conn)["izler"]
    assert all(iz[no] == "" for no in eski)
    s = boss.esitle(f, {"mod": "fark", "gorevler": [], "kaldirilan": eski, "tam": True})
    assert s["rapor_temizligi"]["is"] == 2 and s["rapor_temizligi"]["dagitim"] == 2
    assert len(yedekler()) > once
    rows = conn.execute("SELECT durum, kapanis_nedeni, musteri_adi, adres FROM is_emri WHERE boss_task_no IN (?,?)",
                        eski).fetchall()
    assert all(tuple(r) == ("kapandi", "rapor_kalintisi", None, None) for r in rows)
    assert conn.execute("SELECT COUNT(*) FROM dagitim_is WHERE task_no IN (?,?)", eski).fetchone()[0] == 0
    assert _durum(conn, 101)[0] != "kapandi"
    assert boss.durum(conn)["rapor_temizligi"]["is"] == 2


def test_tam_bicimde_kalinti_temizligi_bekciye_takilmaz(v2db, conn):
    y.aktar(v2db, y.standart(60))           # 60 eski iş: hepsi bir anda "kaybolur" (bekçi sınırı 50)
    s = boss.esitle(y.fabrika(v2db), {"gorevler": [_gorev(101)], "tam": True})
    assert s["rapor_temizligi"]["is"] == 60 and s["tam"] is True and not s["uyari"]
    assert conn.execute("SELECT COUNT(*) FROM is_emri WHERE durum NOT IN ('kapandi','cozuldu')").fetchone()[0] == 1


def test_iletisim_onden_okuma_ve_ilerleme(istemci, v2db, conn, jeton, kisi):
    kod = boss.eslesme_kodu()
    ek = {"X-Eslesme-Kodu": kod}
    s = istemci.post("/api/boss/esitle", headers=ek, json={"gorevler": [_gorev(1), _gorev(2)], "tam": True}).json()
    assert {x["task_no"] for x in s["iletisim"]} == {"400000001", "400000002"}
    assert conn.execute("SELECT deger FROM ayar WHERE anahtar='musteri_tel'").fetchone()[0] == "acik"
    op = jeton(kisi["operasyon"])
    d = istemci.get("/api/boss/durum", headers=op).json()
    assert (d["iletisim_tamam"], d["iletisim_toplam"]) == (0, 2)

    assert istemci.post("/api/boss/iletisim", json={"sonuclar": []}).status_code == 401
    r = istemci.post("/api/boss/iletisim", headers=ek, json={"sonuclar": [
        {"task_no": "400000001", "veri": {"content": [{"name": "X", "gsm": "0533 222 33 44"}]}},
        {"task_no": "400000002", "hata": "http_500"}]}).json()
    assert r["okunan"] == 1 and r["telefon"] == 1 and r["hata"] == 1
    assert r["iletisim"] == []                       # 2 hata verdi: bir süre yeniden istenmez
    assert conn.execute("SELECT musteri_tel FROM is_emri WHERE boss_task_no='400000001'").fetchone()[0] == "5332223344"
    d = istemci.get("/api/boss/durum", headers=op).json()
    assert (d["iletisim_tamam"], d["iletisim_toplam"]) == (1, 2)

    # iz değişince yeniden istenir
    g = _gorev(1, durum="Başlandı")
    s = istemci.post("/api/boss/esitle", headers=ek, json={"mod": "fark", "gorevler": [g], "tam": False}).json()
    assert [x["task_no"] for x in s["iletisim"]] == ["400000001"]

    # sahip sonradan kapatırsa ezilmez ve istenmez
    conn.execute("UPDATE ayar SET deger='kapali' WHERE anahtar='musteri_tel'")
    conn.commit()
    s = istemci.post("/api/boss/esitle", headers=ek, json={"mod": "fark", "gorevler": [], "tam": False}).json()
    assert s["iletisim"] == []
    assert conn.execute("SELECT deger FROM ayar WHERE anahtar='musteri_tel'").fetchone()[0] == "kapali"


def test_izler_ucu(istemci, v2db):
    ek = {"X-Eslesme-Kodu": boss.eslesme_kodu()}
    assert istemci.get("/api/boss/izler").status_code == 401
    assert istemci.get("/api/boss/izler", headers=ek).json() == {"izler": {}, "tam_gerekli": True}
    istemci.post("/api/boss/esitle", headers=ek, json={"gorevler": [_gorev(1)], "tam": False})
    j = istemci.get("/api/boss/izler", headers=ek).json()
    assert j["izler"] == {"400000001": _gorev(1)["iz"]} and not j["tam_gerekli"]


def test_liste_satirinda_telefon_yalniz_izinle(istemci, v2db, conn, jeton, kisi, monkeypatch):
    ek = {"X-Eslesme-Kodu": boss.eslesme_kodu()}
    istemci.post("/api/boss/esitle", headers=ek, json={"gorevler": [_gorev(1)], "tam": False})
    istemci.post("/api/boss/iletisim", headers=ek, json={"sonuclar": [
        {"task_no": "400000001", "veri": [{"gsm": "0533 222 33 44"}]}]})
    op = jeton(kisi["operasyon"])
    satir = next(x for x in istemci.get("/api/isler", headers=op).json()["isler"] if x["boss_task_no"] == "400000001")
    assert satir["musteri_tel"] == "5332223344"

    asil = kisi_mod.izinli
    monkeypatch.setattr(kisi_mod, "izinli", lambda c, k, e: False if e == "is.musteri" else asil(c, k, e))
    satir = next(x for x in istemci.get("/api/isler", headers=op).json()["isler"] if x["boss_task_no"] == "400000001")
    assert "musteri_tel" not in satir


def test_yeniden_acilan_sayisi_ve_telefon_yeniden(istemci, v2db, conn, jeton, kisi):
    """İptal edilip satış kanalınca geri gönderilen iş task no ile eşleşip yeniden açılır: eşitleme olayında ve
    /api/boss/durum'da sayılır; parmak izi aynı kalsa da telefonu yeniden indirilir."""
    ek = {"X-Eslesme-Kodu": boss.eslesme_kodu()}
    g = _gorev(1)
    istemci.post("/api/boss/esitle", headers=ek, json={"gorevler": [g, _gorev(2)], "tam": True})
    istemci.post("/api/boss/iletisim", headers=ek, json={"sonuclar": [
        {"task_no": "400000001", "veri": [{"gsm": "0533 222 33 44"}]}]})
    istemci.post("/api/boss/esitle", headers=ek, json={"mod": "fark", "gorevler": [], "kaldirilan": ["400000001"],
                                                       "tam": True})
    assert _durum(conn, 1) == ("kapandi", "boss_listeden_dustu")
    s = istemci.post("/api/boss/esitle", headers=ek, json={"mod": "fark", "gorevler": [g], "tam": False}).json()
    assert _durum(conn, 1)[0] != "kapandi"
    assert s["fark"]["yeniden_acilan"] == 1
    assert "400000001" in [x["task_no"] for x in s["iletisim"]]
    d = istemci.get("/api/boss/durum", headers=jeton(kisi["operasyon"])).json()
    assert d["yeniden_acilan"] == 1
    from operasyon.v2 import api
    son = [o for o in api._AKIS if o.get("adim") == "esitle"][-1]
    assert son["yeniden_acilan"] == 1


def test_numarasiz_is_saatte_bir_yeniden_okunur(istemci, v2db, conn, saat):
    """Telefonu çıkmayan açık iş (iletişim listesi boş): hemen yeniden istenmez, 1 saat sonra yeniden istenir.
    Telefonu bulunan iş bir daha istenmez (izi değişmedikçe)."""
    saat.ayarla("2026-10-01 10:00:00")
    ek = {"X-Eslesme-Kodu": boss.eslesme_kodu()}
    istemci.post("/api/boss/esitle", headers=ek, json={"gorevler": [_gorev(1), _gorev(2)], "tam": True})
    r = istemci.post("/api/boss/iletisim", headers=ek, json={"sonuclar": [
        {"task_no": "400000001", "veri": {"content": []}},
        {"task_no": "400000002", "veri": [{"gsm": "0533 222 33 44"}]}]}).json()
    assert r["telefon"] == 1 and r["iletisim"] == []
    saat.ilerlet(minutes=59)
    assert boss.iletisim_gerekli(conn) == []
    saat.ilerlet(minutes=2)
    assert [x["task_no"] for x in boss.iletisim_gerekli(conn)] == ["400000001"]
    # numara elle girildiyse artık sorulmaz
    conn.execute("UPDATE is_emri SET musteri_tel='5321112233' WHERE boss_task_no='400000001'")
    conn.commit()
    assert boss.iletisim_gerekli(conn) == []


def test_yalniz_kapanan_gorev_gelen_fark_esitlemesi(v2db, conn):
    """Artımlı eşitlemede yalnız kapanan görev gelirse (açık görev yok) aktarım hattı boş tabloyla çökmez."""
    f = y.fabrika(v2db)
    boss.esitle(f, {"gorevler": [_gorev(1), _gorev(2)], "tam": True})
    s = boss.esitle(f, {"mod": "fark", "gorevler": [_gorev(1, durum="Tamamlandı")], "kaldirilan": [], "tam": True})
    assert s["ozet"]["kapanan"] == 1 and _durum(conn, 1)[0] == "kapandi" and _durum(conn, 2)[0] != "kapandi"
