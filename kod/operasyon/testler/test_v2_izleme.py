"""EK-10 · Rapor klasörü izleme: yoklama (15 sn), 5 sn sabitlik, §4 hattından aynen geçer (sha, bekçi, yedek).

Testler iş parçacığı AÇMAZ ve kullanıcının gerçek İndirilenler/Masaüstü klasörüne asla bakmaz: izlenen klasör geçici
bir klasördür; ``Izleyici.tara(an)`` yoklama turunu elle ve dondurulmuş saniyeyle yürütür.
"""
from __future__ import annotations

import json
import os
import time

import pytest

from operasyon.testler import yardim as y
from operasyon.v2 import izleme

# Dosya zamanları (mtime) gerçek saattir; aktarım zamanı da gerçek saat olmalı (conftest.sabit_saat kapalı).
pytestmark = pytest.mark.gercek_saat

AD = "TeknikTaskDetayRaporu.xlsx"


def _kur(conn, klasor):
    izleme.ayar_yaz(conn, acik=True, klasorler=[str(klasor)])
    conn.commit()
    return izleme.Izleyici(y.fabrika(conn.execute("PRAGMA database_list").fetchone()[2]))


def _yaz(yol, satirlar, gecmis_sn=0):
    yol.write_bytes(y.xlsx(satirlar))
    if gecmis_sn:
        t = time.time() - gecmis_sn
        os.utime(yol, (t, t))


def test_yeni_rapor_sabitlenince_alinir(v2db, conn, tmp_path):
    klasor = tmp_path / "indirilenler"
    klasor.mkdir()
    iz = _kur(conn, klasor)
    assert iz.tara(0) == []                                              # taban: klasör boş
    _yaz(klasor / AD, [y.satir(i) for i in range(1, 7)])
    (klasor / "baska.xlsx").write_bytes(b"desene uymaz")
    assert iz.tara(1) == []                                              # ilk görüş: aday
    assert iz.tara(4) == []                                              # 5 sn dolmadı
    s = iz.tara(7)
    assert [x["kod"] for x in s] == ["uygulandi"] and s[0]["sonuc"].startswith("Yeni rapor alındı")
    assert "6 yeni iş" in s[0]["sonuc"]
    assert conn.execute("SELECT COUNT(*) FROM is_emri").fetchone()[0] == 6
    r = conn.execute("SELECT yontem, yukleyen_id, dosya_zamani FROM ie_aktarim").fetchone()
    assert r["yontem"] == "klasor" and r["yukleyen_id"] is None and r["dosya_zamani"]
    assert iz.tara(30) == []                                             # aynı dosya: tekrar işlenmez
    d = izleme.durum(conn)
    assert d["acik"] and d["klasorler"] == [str(klasor)] and d["son_alinan"] is None   # modül izleyicisi açık değil


def test_yazilirken_bekler_ayni_icerik_etkisiz(v2db, conn, tmp_path):
    klasor = tmp_path / "masaustu"
    klasor.mkdir()
    iz = _kur(conn, klasor)
    iz.tara(0)
    yol = klasor / AD
    _yaz(yol, [y.satir(1)])
    iz.tara(1)
    _yaz(yol, [y.satir(1), y.satir(2)])                                  # hâlâ yazılıyor: boyut/zaman değişti
    assert iz.tara(6) == []                                              # sabitlik baştan
    assert [x["kod"] for x in iz.tara(12)] == ["uygulandi"]
    # aynı içerik başka adla (tarayıcı "(1)" ekler): sha aynı → hiçbir şey yazılmaz
    (klasor / "TeknikTaskDetayRaporu (1).xlsx").write_bytes(yol.read_bytes())
    iz.tara(20)
    s = iz.tara(26)
    assert [x["kod"] for x in s] == ["ayni_dosya"]
    assert conn.execute("SELECT COUNT(*) FROM ie_aktarim").fetchone()[0] == 1


def test_bekci_takilinca_onay_bekler(v2db, conn, tmp_path):
    klasor = tmp_path / "k"
    klasor.mkdir()
    tam = [y.satir(i) for i in range(1, 61)]
    y.aktar(v2db, tam)
    iz = _kur(conn, klasor)
    iz.tara(0)
    _yaz(klasor / AD, tam[:4])                                           # süzgeçli rapor
    iz.tara(1)
    s = iz.tara(7)
    assert [x["kod"] for x in s] == ["onay_gerekli"] and "Onay bekleyen rapor" in s[0]["sonuc"]
    assert conn.execute("SELECT COUNT(*) FROM is_emri WHERE durum NOT IN ('cozuldu','kapandi')").fetchone()[0] == 60
    ob = izleme.durum(conn)["onay_bekleyen"]
    assert len(ob) == 1 and ob[0]["yontem"] == "klasor" and ob[0]["nedenler"] == ["cok_kaybolan"]
    assert iz.tara(40) == []                                             # aynı dosya tekrar denenmez


def test_kapaliyken_bakmaz_ve_taban(v2db, conn, tmp_path):
    klasor = tmp_path / "k"
    klasor.mkdir()
    y.aktar(v2db, [y.satir(1)])
    _yaz(klasor / "TeknikTaskDetayRaporu (3).xlsx", [y.satir(1), y.satir(2)], gecmis_sn=3600)   # aktarımdan eski
    iz = _kur(conn, klasor)
    iz.tara(0)
    assert iz.tara(10) == []                                             # açılıştaki eski rapor yeniden işlenmez
    izleme.ayar_yaz(conn, acik=False)
    conn.commit()
    _yaz(klasor / AD, [y.satir(5)])
    assert iz.tara(20) == [] and iz.tara(30) == []
    assert conn.execute("SELECT COUNT(*) FROM ie_aktarim").fetchone()[0] == 1


def test_ayar_desen_guvenligi_ve_uclar(v2db, conn, istemci, jeton, kisi, tmp_path):
    a = izleme.ayar_yaz(conn, desenler=["../*.xlsx", "C:\\x\\*.xlsx", "Rapor*.xlsx"])
    assert a["desenler"] == ["Rapor*.xlsx"]
    r = istemci.put("/api/aktarim/izleme", headers=jeton(kisi["operasyon"]), json={"klasorler": [str(tmp_path)]})
    assert r.status_code == 403                                          # klasörü yalnız yönetici değiştirir
    r = istemci.put("/api/aktarim/izleme", headers=jeton(kisi["operasyon"]), json={"acik": False})
    assert r.status_code == 200 and r.json()["acik"] is False
    r = istemci.put("/api/aktarim/izleme", headers=jeton(kisi["yonetici"]), json={"klasorler": [str(tmp_path)]})
    assert r.status_code == 200 and r.json()["klasorler"] == [str(tmp_path)]
    assert istemci.get("/api/aktarim/izleme", headers=jeton(kisi["teknik1"])).status_code == 403
    assert json.loads(conn.execute("SELECT ozet FROM yonetim_kaydi WHERE hedef='klasor_izleme' ORDER BY id DESC"
                                   ).fetchone()[0])["klasor_degisti"] is True


def test_testte_is_parcacigi_acilmaz():
    assert izleme.baslat() is None                                        # pytest yüklü → izleyici başlamaz


def test_sunucu_acilisinda_baslar_kapanista_durur(v2db, monkeypatch):
    """İzleyiciyi v2 yönlendiricisinin yaşam döngüsü açar (saha/api.py'ye dokunmadan); iş tabloları yoksa açmaz."""
    from fastapi.testclient import TestClient

    from operasyon.testler.conftest import uygulama
    cagri = []
    monkeypatch.setattr(izleme, "baslat", lambda *a, **k: cagri.append("baslat") or object())
    monkeypatch.setattr(izleme, "durdur", lambda: cagri.append("durdur"))
    with TestClient(uygulama()):
        assert cagri == ["baslat"]
    assert cagri == ["baslat", "durdur"]
    bos = v2db.parent / "bos.db"                                         # iş tabloları kurulmamış veritabanı
    import sqlite3
    sqlite3.connect(bos).close()
    monkeypatch.setenv("SAHA_DB", str(bos))
    cagri.clear()
    with TestClient(uygulama()):
        pass
    assert cagri == []
