"""Her yerden arama (GET /api/ara): izin süzgeci, Türkçe harf duyarsızlığı, Location ID tam/önek, kısa sorgu.

Müşteri verisi testte uydurmadır; gerçek veri kullanılmaz.
"""
from __future__ import annotations

import time

import pytest

from saha import arama_uclari


@pytest.fixture(autouse=True)
def _bos_onbellek():
    arama_uclari.onbellegi_bosalt()
    yield
    arama_uclari.onbellegi_bosalt()


def _is_ekle(conn, is_no: str, task_no: str, musteri_adi: str, musteri_no: str, atanan_id=None,
             durum: str = "atandi", bina_serial=None) -> None:
    z = "2026-09-30 10:00:00"
    conn.execute(
        "INSERT INTO is_emri (is_no, boss_task_no, kaynak, task_adi, serit, musteri_no, musteri_adi, durum, "
        "durum_zamani, atanan_id, bina_serial, acilis, son24, ilk_gorulme, gorulme_zamani, guncelleme, mahalle, ilce) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (is_no, task_no, "boss", "Arıza", "Arıza", musteri_no, musteri_adi, durum, z, atanan_id, bina_serial,
         z, z, z, z, z, "Deneme", "Nilüfer"))
    conn.commit()
    arama_uclari.onbellegi_bosalt()


def _gruplar(yanit) -> dict:
    assert yanit.status_code == 200, yanit.text
    return {g["tur"]: g for g in yanit.json()["gruplar"]}


def _locid_binasi(conn, bolge: int):
    r = conn.execute("SELECT bina_serial, location_id FROM bina WHERE bolge=? AND location_id IS NOT NULL "
                     "AND length(location_id) >= 5 ORDER BY bina_serial LIMIT 1", (bolge,)).fetchone()
    if not r:
        pytest.skip("tohum verisinde Location ID'li bina yok")
    return r["bina_serial"], str(r["location_id"]).strip()


# ============================================================================= temel
def test_jetonsuz_401(istemci):
    assert istemci.get("/api/ara", params={"q": "abc"}).status_code == 401


@pytest.mark.parametrize("q", ["", " ", "a", "-", "İ"])
def test_bos_ve_kisa_sorgu_bos_doner(istemci, yonetici, q):
    j = istemci.get("/api/ara", params={"q": q}, headers=yonetici).json()
    assert j["gruplar"] == [] and j["toplam"] == 0


def test_bilinmeyen_tur_reddedilir(istemci, yonetici):
    assert istemci.get("/api/ara", params={"q": "abc", "tur": "musteri"}, headers=yonetici).status_code == 422


# ============================================================================= Location ID
def test_locid_tam_eslesme_ilk_sirada(istemci, yonetici, conn):
    serial, loc = _locid_binasi(conn, 2)
    g = _gruplar(istemci.get("/api/ara", params={"q": loc}, headers=yonetici))
    ilk = g["bina"]["sonuclar"][0]
    assert ilk["serial"] == serial and ilk["location_id"] == loc
    assert ilk["lat"] is not None and ilk["lon"] is not None
    # en iyi eşleşmenin grubu önde
    assert istemci.get("/api/ara", params={"q": loc}, headers=yonetici).json()["gruplar"][0]["tur"] == "bina"


def test_locid_onek_ve_grup_siniri(istemci, yonetici, conn):
    serial, loc = _locid_binasi(conn, 2)
    onek = loc[: max(2, len(loc) - 2)]
    g = _gruplar(istemci.get("/api/ara", params={"q": onek}, headers=yonetici))
    b = g["bina"]
    assert len(b["sonuclar"]) <= arama_uclari.GRUP_SINIRI
    assert b["toplam"] >= len(b["sonuclar"])
    tum = _gruplar(istemci.get("/api/ara", params={"q": onek, "tur": "bina"}, headers=yonetici))["bina"]
    assert len(tum["sonuclar"]) <= arama_uclari.TUR_SINIRI
    assert any(s["serial"] == serial for s in tum["sonuclar"]) or tum["toplam"] > arama_uclari.TUR_SINIRI


def test_satisci_baska_bolgenin_binasini_bulamaz(istemci, satisci1, yonetici, conn):
    _, loc2 = _locid_binasi(conn, 2)
    g = _gruplar(istemci.get("/api/ara", params={"q": loc2}, headers=satisci1))
    assert all(s["bolge"] == 1 for s in g.get("bina", {"sonuclar": []})["sonuclar"])
    serial1, loc1 = _locid_binasi(conn, 1)
    g1 = _gruplar(istemci.get("/api/ara", params={"q": loc1}, headers=satisci1))
    assert g1["bina"]["sonuclar"][0]["serial"] == serial1


def test_satisci_is_ve_kisi_aramaz(istemci, satisci1, conn):
    _is_ekle(conn, "B-SAT-1", "9100000001", "Deneme Müşteri", "8800000001")
    g = _gruplar(istemci.get("/api/ara", params={"q": "9100000001"}, headers=satisci1))
    assert "is" not in g
    ad = conn.execute("SELECT ad FROM kullanici WHERE rol='yonetici' LIMIT 1").fetchone()["ad"]
    assert "kisi" not in _gruplar(istemci.get("/api/ara", params={"q": ad}, headers=satisci1))


# ============================================================================= Türkçe harf
def test_turkce_buyuk_kucuk_harf_duyarsiz(istemci, yonetici, conn):
    r = conn.execute("SELECT bina_serial, site_adi FROM bina WHERE site_adi LIKE '%İ%' OR site_adi LIKE '%Ş%' "
                     "OR site_adi LIKE '%Ğ%' OR site_adi LIKE '%Ü%' LIMIT 1").fetchone()
    if not r:
        pytest.skip("tohum verisinde Türkçe harfli site adı yok")
    kucuk = r["site_adi"].replace("İ", "i").replace("I", "ı").lower()
    sonuc = _gruplar(istemci.get("/api/ara", params={"q": kucuk, "tur": "bina"}, headers=yonetici))["bina"]
    assert sonuc["toplam"] >= 1
    assert arama_uclari.sade(kucuk) == arama_uclari.sade(r["site_adi"])
    assert arama_uclari.sade("şükrü ılıca İnönü") == "SUKRU ILICA INONU"


def test_musteri_adi_turkce_ve_erisim_kaydi(istemci, kisi, conn):
    _, op = kisi("operasyon")
    _is_ekle(conn, "B-OP-1", "9100000002", "ŞÜKRÜ IŞIKÇI", "8800000002")
    g = _gruplar(istemci.get("/api/ara", params={"q": "şükrü ışıkçı"}, headers=op))
    s = g["is"]["sonuclar"][0]
    assert s["is_no"] == "B-OP-1" and s["musteri_adi"] == "ŞÜKRÜ IŞIKÇI"
    # müşteri no tam eşleşme
    g2 = _gruplar(istemci.get("/api/ara", params={"q": "8800000002"}, headers=op))
    assert g2["is"]["sonuclar"][0]["is_no"] == "B-OP-1"
    assert conn.execute("SELECT COALESCE(SUM(adet),0) FROM erisim_kaydi WHERE eylem='arama'").fetchone()[0] >= 2


# ============================================================================= teknik
def test_teknik_musteri_adini_goremez_yalniz_kendi_isi(istemci, kisi, conn):
    tid, tek = kisi("teknik")
    diger_id, _ = kisi("teknik")
    _is_ekle(conn, "B-T-1", "9100000003", "Deneme Kendi", "8800000003", atanan_id=tid)
    _is_ekle(conn, "B-T-2", "9100000004", "Deneme Baska", "8800000004", atanan_id=diger_id)
    # müşteri adıyla ve müşteri no ile arayamaz
    assert "is" not in _gruplar(istemci.get("/api/ara", params={"q": "Deneme Kendi"}, headers=tek))
    assert "is" not in _gruplar(istemci.get("/api/ara", params={"q": "8800000003"}, headers=tek))
    # kendi task no'su bulunur, müşteri alanı yok
    s = _gruplar(istemci.get("/api/ara", params={"q": "9100000003"}, headers=tek))["is"]["sonuclar"][0]
    assert s["is_no"] == "B-T-1" and "musteri_adi" not in s and "musteri_no" not in s
    # başkasının işi bulunmaz
    assert "is" not in _gruplar(istemci.get("/api/ara", params={"q": "9100000004"}, headers=tek))


def test_teknik_yalniz_acik_isinin_binasini_bulur(istemci, kisi, conn):
    tid, tek = kisi("teknik")
    serial, loc = _locid_binasi(conn, 3)
    assert "bina" not in _gruplar(istemci.get("/api/ara", params={"q": loc}, headers=tek))
    _is_ekle(conn, "B-T-3", "9100000005", "X", "8800000005", atanan_id=tid, bina_serial=serial)
    assert _gruplar(istemci.get("/api/ara", params={"q": loc}, headers=tek))["bina"]["sonuclar"][0]["serial"] == serial


# ============================================================================= kişiler
def test_kisi_aramasi_yalniz_ekip_yetkisiyle_ve_telefonsuz(istemci, yonetici, kisi, conn):
    _, op = kisi("operasyon")
    kisi("teknik", ad="Çağrı Teknikçi")
    kisi("satisci", ad="Çağrı Satışçı", bolge=1)
    g = _gruplar(istemci.get("/api/ara", params={"q": "cagri", "tur": "kisi"}, headers=yonetici))["kisi"]
    assert {s["baslik"] for s in g["sonuclar"]} >= {"Çağrı Teknikçi", "Çağrı Satışçı"}
    assert all("telefon" not in s for s in g["sonuclar"])
    # operasyon (ekip.teknikler) yalnız teknikleri bulur
    g2 = _gruplar(istemci.get("/api/ara", params={"q": "çağrı"}, headers=op))["kisi"]
    assert {s["baslik"] for s in g2["sonuclar"]} == {"Çağrı Teknikçi"}


def test_yonetici_telefonla_kisi_bulur(istemci, yonetici, kisi):
    kisi("teknik", ad="Telefonlu Deneme", telefon="5559876543")
    g = _gruplar(istemci.get("/api/ara", params={"q": "0555 987 6543"}, headers=yonetici))
    assert any(s["baslik"] == "Telefonlu Deneme" for s in g["kisi"]["sonuclar"])


# ============================================================================= hız
def test_tipik_sorgu_hizli(istemci, yonetici, conn):
    _, loc = _locid_binasi(conn, 2)
    istemci.get("/api/ara", params={"q": loc}, headers=yonetici)        # önbelleği ısıt
    sureler = []
    for q in (loc, loc[:4], "sitesi", "nilüfer"):
        bas = time.perf_counter()
        j = istemci.get("/api/ara", params={"q": q}, headers=yonetici).json()
        sureler.append(j["sure_ms"])
        assert (time.perf_counter() - bas) < 2
    assert min(sureler) < 50
