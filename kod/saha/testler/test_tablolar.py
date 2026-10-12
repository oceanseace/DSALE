"""Tablolar ekranının uçları (Ek-8, Ek-9): sekmeler, tek biçim, görevle süzülen kişisel veri, altyapı bekleyen
satırını uygulamada ilerletme. PS26 aktarımı ve Güzergah sekmesi 2026-10'da kaldırıldı.

Bütün müşteri numaraları ve satıcılar UYDURMADIR (9000xxxx).
"""
from __future__ import annotations

import datetime as dt
import time

import pytest

from saha import ayarlar, ticket, yetki


def _gun(n: int) -> str:
    return (ayarlar.bugun() - dt.timedelta(days=n)).isoformat()


@pytest.fixture
def dolu(conn):
    """Uygulamada girilmiş 3 ticket + 3 altyapı bekleyen satır."""
    b = [dict(r) for r in conn.execute(
        "SELECT bina_serial, location_id FROM bina WHERE location_id IS NOT NULL AND location_id <> '' AND pasif=0 "
        "AND bolge=1 ORDER BY bina_serial LIMIT 3")]
    for i, (konu, durum, musteri) in enumerate((("SİNYAL", "ÇÖZÜLDÜ", "90000001"), ("EK SP", "AÇIK", "90000002"),
                                                ("SİNYAL", "HATA", "90000004"))):
        ticket.olustur(conn, {"konu": konu, "durum": durum, "bina_serial": b[i]["bina_serial"], "musteri": musteri,
                              "acilis": _gun(20 - i * 5)}, None)
    simdi = ayarlar.zaman_metni()
    for musteri, kanal, gun, satici in (("90000021", "GLOBAL", 40, "Deneme Satıcı Bir"),
                                        ("90000022", "DEHA", 12, "Deneme Satıcı Bir"),
                                        ("90000023", "TOPTAN", 2, "Deneme Satıcı İki")):
        conn.execute(
            "INSERT INTO altyapi_bekleyen (musteri_no, kanal, baslangic, satici_ad, bolge, bina_serial, durum, notu, "
            "aktarim_anahtari, olusturma, guncelleme) VALUES (?,?,?,?,NULL,NULL,'bekliyor',NULL,NULL,?,?)",
            (musteri, kanal, _gun(gun), satici, simdi, simdi))
    conn.commit()
    return {"ticket": 3, "acik": 2, "altyapi": 3}


def _satirlar(v: dict) -> list[dict]:
    adlar = [s["anahtar"] for s in v["sutunlar"]]
    return [dict(zip(adlar, r)) for r in v["satirlar"]]


def test_sekmeler_ve_ozet(istemci, kisi, dolu):
    _, op = kisi("operasyon")
    v = istemci.get("/api/tablolar", headers=op).json()
    sekmeler = {s["anahtar"]: s for s in v["sekmeler"]}
    assert list(sekmeler) == ["ticketlar", "altyapi", "binalar", "isler"]          # Güzergah yok
    assert sekmeler["ticketlar"]["satir"] == dolu["ticket"] and sekmeler["altyapi"]["satir"] == dolu["altyapi"]
    assert sekmeler["binalar"]["satir"] > 19000
    o = v["ozet"]
    assert o["ticket_takipte"] == dolu["acik"]
    assert o["altyapi_bekliyor"] == dolu["altyapi"] and o["altyapi_en_eski_gun"] == 40
    assert "ps26_son_aktarim" not in o and "guzergah_acik" not in o


def test_ticket_sekmesi_bicimi(istemci, kisi, dolu, conn):
    _, op = kisi("operasyon")
    v = istemci.get("/api/tablolar/ticketlar", headers=op).json()
    assert v["kimlik"] == "id" and v["sutunlar"][0] == {"anahtar": "id", "baslik": "Kimlik", "tur": "sayi", "gizli": True}
    assert [s["baslik"] for s in v["sutunlar"][1:8]] == ["Ticket", "Başlangıç", "Lokasyon", "Site", "Konu", "Durum",
                                                          "Müşteri"]
    assert all(len(r) == len(v["sutunlar"]) for r in v["satirlar"]) and v["toplam"] == dolu["ticket"]
    satirlar = _satirlar(v)
    assert {r["kaynak"] for r in satirlar} == {"Uygulama"}
    assert all(len(r["acilis"]) == 10 for r in satirlar)
    assert istemci.get("/api/tablolar/guzergah", headers=op).json()["kod"] == "tablo_yok"
    kayit = conn.execute("SELECT eylem, adet FROM erisim_kaydi WHERE eylem LIKE 'tablo_%' ORDER BY id").fetchall()
    assert [(r[0], r[1]) for r in kayit] == [("tablo_ticketlar", dolu["ticket"])]


def test_musteri_izni_yoksa_sutun_hic_yok(istemci, kisi, dolu, conn, monkeypatch):
    """Kişisel veri görevle süzülür: ``is.musteri`` izni olmayan görevde müşteri sütunu hiç gelmez."""
    monkeypatch.setitem(yetki.IZINLER, "is.musteri", frozenset({"teknik"}))
    _, op = kisi("operasyon")
    for sekme in ("ticketlar", "altyapi"):
        y = istemci.get(f"/api/tablolar/{sekme}", headers=op)
        assert y.status_code == 200
        assert not {"musteri", "musteri_no"} & {s["anahtar"] for s in y.json()["sutunlar"]}, sekme
        for no in ("90000001", "90000002", "90000021", "90000023"):
            assert no not in y.text, sekme
    assert conn.execute("SELECT COUNT(*) FROM erisim_kaydi WHERE eylem LIKE 'tablo_%'").fetchone()[0] == 0


def test_satis_ve_teknik_tablolari_goremez(istemci, kisi, dolu):
    for rol, bolge in (("satisci", 1), ("teknik", None)):
        _, h = kisi(rol, bolge=bolge)
        for yol in ("/api/tablolar", "/api/tablolar/ticketlar", "/api/tablolar/binalar"):
            y = istemci.get(yol, headers=h)
            assert y.status_code == 403 and y.json()["kod"] == "yasak", (rol, yol)
    _, yon = kisi("yonetici")
    assert istemci.get("/api/tablolar/boyle", headers=yon).json()["kod"] == "tablo_yok"


def test_ps26_uclari_kaldirildi(istemci, kisi):
    _, yon = kisi("yonetici")
    assert istemci.get("/api/ps26", headers=yon).status_code == 404
    assert istemci.post("/api/ps26/aktar", headers=yon, content=b"x").status_code in (404, 405)
    assert not [a for a in yetki.ROTA_IZNI if "/api/ps26" in a[1]]


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
    assert istemci.get("/api/tablolar/altyapi", headers=op).json()["ozet"]["bekliyor"] == dolu["altyapi"] - 1


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
    assert sure < 3.0, sure
