"""Tablolar ekranının uçları (Ek-8, Ek-9): PS26 sayfaları gibi sekmeler, tek biçim, görevle süzülen kişisel veri,
altyapı bekleyen satırını uygulamada ilerletme (PS26'yı kaldırabilmek için).
"""
from __future__ import annotations

import time

import pytest

from saha import ps26_aktar, yetki

from .test_ps26_yardim import sentetik


@pytest.fixture
def dolu(conn, tmp_path):
    """Sentetik PS26 aktarılmış veritabanı."""
    b = sentetik(conn, tmp_path / "PS26")
    ps26_aktar.aktar(conn, ps26_aktar.oku(tmp_path / "PS26" / "data.xlsx", imgs=tmp_path / "PS26" / "imgs"), kuru=False)
    return b


def _satirlar(v: dict) -> list[dict]:
    """Dizi satırları sütun adlarıyla sözlüğe çevirir (testte okunaklı olsun)."""
    adlar = [s["anahtar"] for s in v["sutunlar"]]
    return [dict(zip(adlar, r)) for r in v["satirlar"]]


def test_sekmeler_ve_ozet(istemci, kisi, dolu):
    _, op = kisi("operasyon")
    v = istemci.get("/api/tablolar", headers=op).json()
    sekmeler = {s["anahtar"]: s for s in v["sekmeler"]}
    assert list(sekmeler) == ["ticketlar", "guzergah", "altyapi", "binalar", "isler"]
    assert sekmeler["ticketlar"]["ad"] == "Ticketlar" and sekmeler["altyapi"]["ad"] == "Altyapı bekleyen"
    assert sekmeler["ticketlar"]["satir"] == dolu["ticket"] and sekmeler["guzergah"]["satir"] == dolu["guzergah"]
    assert sekmeler["altyapi"]["satir"] == dolu["altyapi"] and sekmeler["binalar"]["satir"] > 19000
    o = v["ozet"]
    assert o["altyapi_bekliyor"] == dolu["altyapi"] and o["altyapi_en_eski_gun"] == 40
    assert o["foto"] == dolu["foto"] and o["ps26_son_aktarim"]
    assert o["guzergah_acik"] == dolu["guzergah"]


def test_ticket_ve_guzergah_sekmesi_bicimi(istemci, kisi, dolu, conn):
    _, op = kisi("operasyon")
    v = istemci.get("/api/tablolar/ticketlar", headers=op).json()
    assert v["kimlik"] == "id" and v["sutunlar"][0] == {"anahtar": "id", "baslik": "Kimlik", "tur": "sayi", "gizli": True}
    assert [s["baslik"] for s in v["sutunlar"][1:8]] == ["Ticket", "Başlangıç", "Lokasyon", "Site", "Konu", "Durum",
                                                          "Müşteri"]                     # PS26'daki sıra
    assert all(len(r) == len(v["sutunlar"]) for r in v["satirlar"]) and v["toplam"] == dolu["ticket"]
    satirlar = _satirlar(v)
    assert sum(r["foto"] or 0 for r in satirlar) == 4                 # güzergahtaki 1 fotoğraf kendi sekmesinde
    assert {r["kaynak"] for r in satirlar} == {"Excel"}
    assert all(len(r["acilis"]) == 10 for r in satirlar)               # tarih ISO gün (sıralanabilir)
    g = istemci.get("/api/tablolar/guzergah", headers=op).json()
    assert g["toplam"] == dolu["guzergah"] and "ticket_no" not in [s["anahtar"] for s in g["sutunlar"]]
    assert {r["durum"] for r in _satirlar(g)} == {"AÇIK"}
    # Müşteri sütunu döndüğü için erişim kaydı (adetle).
    kayit = conn.execute("SELECT eylem, adet FROM erisim_kaydi WHERE eylem LIKE 'tablo_%' ORDER BY id").fetchall()
    assert [(r[0], r[1]) for r in kayit] == [("tablo_ticketlar", dolu["ticket"]), ("tablo_guzergah", dolu["guzergah"])]


def test_musteri_izni_yoksa_sutun_hic_yok(istemci, kisi, dolu, conn, monkeypatch):
    """Kişisel veri görevle süzülür: ``is.musteri`` izni olmayan görevde müşteri sütunu hiç gelmez."""
    monkeypatch.setitem(yetki.IZINLER, "is.musteri", frozenset({"teknik"}))
    _, op = kisi("operasyon")
    for sekme in ("ticketlar", "guzergah", "altyapi"):
        y = istemci.get(f"/api/tablolar/{sekme}", headers=op)
        assert y.status_code == 200
        v = y.json()
        assert not {"musteri", "musteri_no"} & {s["anahtar"] for s in v["sutunlar"]}, sekme
        for no in ("90000001", "90000003", "90000011", "90000021", "90000023"):     # sentetik müşteri numaraları
            assert no not in y.text, sekme
    assert conn.execute("SELECT COUNT(*) FROM erisim_kaydi WHERE eylem LIKE 'tablo_%'").fetchone()[0] == 0


def test_satis_ve_teknik_tablolari_goremez(istemci, kisi, dolu):
    for rol, bolge in (("satisci", 1), ("teknik", None)):
        _, h = kisi(rol, bolge=bolge)
        for yol in ("/api/tablolar", "/api/tablolar/ticketlar", "/api/tablolar/binalar", "/api/ps26"):
            y = istemci.get(yol, headers=h)
            assert y.status_code == 403 and y.json()["kod"] == "yasak", (rol, yol)
    _, yon = kisi("yonetici")
    assert istemci.get("/api/tablolar/boyle", headers=yon).json()["kod"] == "tablo_yok"


def test_altyapi_sekmesi_pivot_ve_durum_ilerletme(istemci, kisi, dolu, conn):
    _, op = kisi("operasyon")
    v = istemci.get("/api/tablolar/altyapi", headers=op).json()
    satirlar = _satirlar(v)
    assert len(satirlar) == dolu["altyapi"] and {r["durum"] for r in satirlar} == {"Bekliyor"}
    assert max(r["bekleme_gun"] for r in satirlar) == 40
    pivot = [dict(zip([s["anahtar"] for s in v["pivot"]["sutunlar"]], r)) for r in v["pivot"]["satirlar"]]
    assert pivot[0] == {"satici": "Deneme Satıcı Bir", "bekliyor": 2, "kuruldu": 0, "iptal": 0, "toplam": 2}

    kid = satirlar[0]["id"]
    y = istemci.patch(f"/api/tablolar/altyapi/{kid}", headers=op, json={"durum": "kuruldu", "notu": "port açıldı"})
    assert y.status_code == 200 and y.json()["kayit"]["durum"] == "Kuruldu" and y.json()["degisti"] is True
    assert y.json()["kayit"]["bekleme_gun"] is None
    assert istemci.patch(f"/api/tablolar/altyapi/{kid}", headers=op, json={"durum": "kuruldu"}).json()["degisti"] is False
    assert istemci.patch(f"/api/tablolar/altyapi/{kid}", headers=op, json={"durum": "bitti"}).status_code == 422
    assert istemci.patch(f"/api/tablolar/altyapi/{kid}", headers=op, json={"bina_serial": "BN-YOK"}).status_code == 404
    bina = conn.execute("SELECT bina_serial FROM bina LIMIT 1").fetchone()[0]
    assert istemci.patch(f"/api/tablolar/altyapi/{kid}", headers=op, json={"bina_serial": bina}).json()["kayit"]["bina_serial"] == bina
    assert istemci.patch("/api/tablolar/altyapi/999999", headers=op, json={"durum": "iptal"}).status_code == 404
    r = conn.execute("SELECT ozet FROM yonetim_kaydi WHERE eylem='altyapi_guncelle' ORDER BY id LIMIT 1").fetchone()[0]
    assert "port açıldı" not in r                                      # not metni kayda yazılmaz
    ozet = istemci.get("/api/tablolar/altyapi", headers=op).json()["ozet"]
    assert ozet["bekliyor"] == dolu["altyapi"] - 1


def test_altyapi_yeni_satir(istemci, kisi, dolu):
    _, op = kisi("operasyon")
    y = istemci.post("/api/tablolar/altyapi", headers=op,
                     json={"musteri_no": "90000099", "kanal": "deha", "satici_ad": "Deneme Satıcı Dört", "bolge": "Balat"})
    assert y.status_code == 201, y.text
    k = y.json()["kayit"]
    assert k["kanal"] == "DEHA" and k["durum"] == "Bekliyor" and k["kaynak"] == "Uygulama" and len(k["baslangic"]) == 10
    assert istemci.post("/api/tablolar/altyapi", headers=op, json={"kanal": "DEHA"}).status_code == 422
    assert istemci.post("/api/tablolar/altyapi", headers=op,
                        json={"satici_ad": "X", "baslangic": "31.02.2026"}).status_code == 422
    _, satis = kisi("satisci", bolge=1)
    assert istemci.post("/api/tablolar/altyapi", headers=satis, json={"satici_ad": "X"}).status_code == 403
    # Uygulamada eklenen satır Excel'in bir sonraki aktarımında "Excel'de yok" sayılmaz (anahtarı yok).
    assert istemci.get("/api/tablolar", headers=op).json()["ozet"]["altyapi_bekliyor"] == dolu["altyapi"] + 1


def test_binalar_sekmesi_butun_binalar_hizli(istemci, kisi, conn):
    _, op = kisi("operasyon")
    t = time.perf_counter()
    y = istemci.get("/api/tablolar/binalar", headers={**op, "Accept-Encoding": "gzip"})
    sure = time.perf_counter() - t
    assert y.status_code == 200 and y.headers.get("content-encoding") == "gzip"
    v = y.json()
    assert v["kimlik"] == "bina_serial" and v["toplam"] == conn.execute("SELECT COUNT(*) FROM bina").fetchone()[0]
    assert v["sutunlar"][0]["anahtar"] == "bina_serial"
    assert sure < 3.0, sure                                            # 19.706 satır, makine yüküne göre ≈0,3–1 sn
