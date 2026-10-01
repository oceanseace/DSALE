"""Veri kalitesi motoru (GEREKSINIMLER B1) ve eski veritabanının güvenli göçü.

Sayılar gerçek veriden gelir (19.706 bina); kural değişirse bu testler neyin
değiştiğini açıkça söyler.
"""
from __future__ import annotations

import json
import sqlite3

import pytest

from saha import db, veri_kalitesi

from .conftest import SATISCI_TEL


def _ozet(istemci, yonetici, **p):
    yanit = istemci.get("/api/kalite/ozet", headers=yonetici, params=p)
    assert yanit.status_code == 200, yanit.text
    return {k["kural"]: k for k in yanit.json()["kurallar"]}, yanit.json()


def test_kalite_ozeti_gercek_veride_beklenen_sayilar(istemci, yonetici):
    kurallar, genel = _ozet(istemci, yonetici)
    assert genel["toplam_bina"] == 19706
    assert genel["hesaplanmamis"] == 0
    # Aktif abone > RES HP olan 303 bina iki kurala AYRIŞIR (her bina tek kurala girer)
    assert kurallar["abone_hp_asiyor"]["adet"] == 181
    assert kurallar["hp_sifir_abone_var"]["adet"] == 122
    assert kurallar["abone_hp_asiyor"]["adet"] + kurallar["hp_sifir_abone_var"]["adet"] == 303
    assert kurallar["hp_sifir"]["adet"] == 44
    # Sıfırı düşen Location Id'lerin hepsi OneMap ile doğrulanıp düzeltildi
    assert kurallar["location_sifir"]["adet"] == kurallar["location_sifir"]["duzeltilen"] == 2335
    assert kurallar["tellcordia_bozuk"]["duzeltilen"] == 2
    assert kurallar["kat_tahmini"]["adet"] == 9835
    assert kurallar["tekrar_satir"]["adet"] == 1
    assert kurallar["ilce_uyusmazligi"]["adet"] == 1
    # Her kuralın sade Türkçe bir açıklaması var
    assert all(k["aciklama"] and k["ad"] for k in kurallar.values())


def test_kalite_uclari_satisciya_kapali(istemci, satisci1):
    for yol in ("/api/kalite/ozet", "/api/kalite/liste"):
        assert istemci.get(yol, headers=satisci1).status_code == 403
    assert istemci.post("/api/kalite/yenile", headers=satisci1).status_code == 403


def test_kalite_listesi_kural_bolge_ve_sayfa(istemci, yonetici):
    y = istemci.get("/api/kalite/liste", headers=yonetici,
                    params={"kural": "abone_hp_asiyor", "limit": 20}).json()
    assert y["toplam"] == 181 and len(y["binalar"]) == 20
    assert all(any(f["kural"] == "abone_hp_asiyor" for f in b["kalite"]) for b in y["binalar"])
    assert all(b["baslik"] for b in y["binalar"])
    ikinci = istemci.get("/api/kalite/liste", headers=yonetici,
                         params={"kural": "abone_hp_asiyor", "limit": 20, "offset": 20}).json()
    assert {b["bina_serial"] for b in y["binalar"]}.isdisjoint({b["bina_serial"] for b in ikinci["binalar"]})
    b3 = istemci.get("/api/kalite/liste", headers=yonetici, params={"kural": "abone_hp_asiyor", "bolge": 3}).json()
    assert 0 < b3["toplam"] < 181 and all(b["bolge"] == 3 for b in b3["binalar"])
    assert istemci.get("/api/kalite/liste", headers=yonetici, params={"kural": "yok_boyle"}).status_code == 400


def test_bina_kartinda_kalite_ve_duzeltilmis_kimlik(istemci, yonetici):
    kart = istemci.get("/api/bina/BN-0000219347", headers=yonetici).json()["bina"]
    # Excel "1,61623150353E+011" yazıyordu; OneMap ile doğrulanıp düzeltildi
    assert kart["kimlik"]["tellcordia_id"] == "161623150353"
    bayrak = next(f for f in kart["kalite"] if f["kural"] == "tellcordia_bozuk")
    assert bayrak["duzeltme"] == {"alan": "tellcordia_id", "eski": "1,61623150353E+011", "yeni": "161623150353"}
    assert "OneMap ile doğrulandı" in bayrak["mesaj"]


def test_sifiri_dusen_location_id_boss_bicimine_tamamlanir(conn):
    # Excel'de 113680 görünen kimlik OneMap ENTEGRASYON_ID ve BOSS'ta 00113680
    satir = conn.execute("SELECT bina_serial, location_id, kalite FROM bina WHERE location_id='00113680'").fetchone()
    assert satir is not None
    bayrak = next(f for f in json.loads(satir["kalite"]) if f["kural"] == "location_sifir")
    assert bayrak["duzeltme"]["eski"] == "113680"
    rakamli_kisa = conn.execute(
        "SELECT COUNT(*) FROM bina WHERE location_id GLOB '[0-9]*' AND length(location_id) < 8").fetchone()[0]
    assert rakamli_kisa == 0


def test_null_ad_kart_basligina_cikmaz(istemci, yonetici):
    kart = istemci.get("/api/bina/BN0001001039", headers=yonetici).json()["bina"]
    assert kart["baslik"].lower() != "null"
    assert kart["baslik"] == "SELAM REZİDANCE"
    # CRM site adındaki "Null " öneki de ticket metnine gitmesin
    assert not kart["crm_site_adi"].lower().startswith("null")


def test_bariz_hatali_kat_duzeltilir_orijinali_saklanir(conn):
    satir = conn.execute("SELECT kat, daire, kalite FROM bina WHERE bina_serial='BN-00001691-196'").fetchone()
    bayrak = next(f for f in json.loads(satir["kalite"]) if f["kural"] == "kat_daire_celiski")
    assert bayrak["duzeltme"]["eski"] == 1 and satir["kat"] == bayrak["duzeltme"]["yeni"] > 1
    assert satir["daire"] == 38


def test_kalite_yeniden_hesaplamak_bir_sey_degistirmez(conn):
    once = conn.execute("SELECT bina_serial, location_id, tellcordia_id, kat, ad, kalite FROM bina "
                        "ORDER BY bina_serial").fetchall()
    sonuc = veri_kalitesi.yenile(conn)
    conn.commit()
    assert sonuc["yazilan"] == 0 and sonuc["alan_degisikligi"] == 0
    sonra = conn.execute("SELECT bina_serial, location_id, tellcordia_id, kat, ad, kalite FROM bina "
                         "ORDER BY bina_serial").fetchall()
    assert [tuple(r) for r in once] == [tuple(r) for r in sonra]


def test_hp_degisince_bayrak_yeniden_hesaplanir(conn):
    serial = conn.execute("SELECT bina_serial FROM bina WHERE res_hp>10 AND aktif_res<res_hp LIMIT 1").fetchone()[0]
    conn.execute("UPDATE bina SET aktif_res=res_hp+5, firsat=0 WHERE bina_serial=?", (serial,))
    veri_kalitesi.yenile(conn, [serial])
    conn.commit()
    bayraklar = json.loads(conn.execute("SELECT kalite FROM bina WHERE bina_serial=?", (serial,)).fetchone()[0])
    assert any(f["kural"] == "abone_hp_asiyor" for f in bayraklar)


# ============================================================ göç
ESKI_SEMA = """
CREATE TABLE kullanici (id INTEGER PRIMARY KEY AUTOINCREMENT, ad TEXT NOT NULL, telefon TEXT NOT NULL UNIQUE,
  pin_hash TEXT, davet_kodu TEXT, rol TEXT NOT NULL, bolge INTEGER, aktif INTEGER NOT NULL DEFAULT 1,
  oturum_no INTEGER NOT NULL DEFAULT 1, olusturma TEXT NOT NULL);
CREATE TABLE bina (bina_serial TEXT PRIMARY KEY, ad TEXT, site_adi TEXT, mahalle TEXT, ilce TEXT, il TEXT,
  cadde TEXT, sokak TEXT, kapi_no TEXT, lat REAL NOT NULL, lon REAL NOT NULL, kat INTEGER, daire INTEGER,
  res_hp INTEGER NOT NULL DEFAULT 0, aktif_res INTEGER NOT NULL DEFAULT 0, firsat INTEGER NOT NULL DEFAULT 0,
  sales_ready TEXT, bolge INTEGER, obek TEXT, site_grup TEXT, location_id TEXT, tellcordia_id TEXT,
  uavt_bina_kodu TEXT, blok_adi TEXT, bina_turu TEXT, toplam_hp INTEGER, soho_hp INTEGER, altyapi TEXT,
  teknoloji TEXT, protokol_segment TEXT, crm_site_adi TEXT);
CREATE TABLE bina_durum (bina_serial TEXT PRIMARY KEY, durum TEXT NOT NULL DEFAULT 'bekliyor', son_ziyaret TEXT,
  son_kullanici_id INTEGER, son_sonuc TEXT, tekrar_tarih TEXT, toplam_satis INTEGER NOT NULL DEFAULT 0,
  ziyaret_sayisi INTEGER NOT NULL DEFAULT 0, notu TEXT);
CREATE TABLE ziyaret (id INTEGER PRIMARY KEY AUTOINCREMENT, offline_id TEXT NOT NULL, bina_serial TEXT NOT NULL,
  kullanici_id INTEGER NOT NULL, zaman TEXT NOT NULL, sonuc TEXT NOT NULL, satis_adedi INTEGER NOT NULL DEFAULT 0,
  konusulan_daire INTEGER NOT NULL DEFAULT 0, notu TEXT, lat REAL, lon REAL, cihaz TEXT, kayit_zamani TEXT NOT NULL,
  iptal INTEGER NOT NULL DEFAULT 0, iptal_eden_id INTEGER, iptal_zamani TEXT, UNIQUE (kullanici_id, offline_id));
CREATE TABLE ayar (anahtar TEXT PRIMARY KEY, deger TEXT);
CREATE TABLE giris_denemesi (id INTEGER PRIMARY KEY AUTOINCREMENT, telefon TEXT NOT NULL, zaman TEXT NOT NULL,
  basarili INTEGER NOT NULL DEFAULT 0, ip TEXT, tur TEXT NOT NULL DEFAULT 'giris');
"""


def test_eski_veritabani_yalniz_eklenerek_tasinir(tmp_path):
    """Canlı veritabanı (faz 1 şeması) açılışta taşınır: tablo/sütun EKLENİR, hiçbir satır kaybolmaz."""
    yol = tmp_path / "eski.db"
    c = sqlite3.connect(yol)
    c.executescript(ESKI_SEMA)
    c.execute("INSERT INTO kullanici (ad, telefon, rol, bolge, olusturma) VALUES ('A','5550000001','satisci',1,'x')")
    c.execute("INSERT INTO bina (bina_serial, ad, lat, lon, res_hp, bolge, location_id) "
              "VALUES ('BN1','Null',40.2,29.0,10,1,'113680')")
    c.execute("INSERT INTO bina_durum (bina_serial) VALUES ('BN1')")
    c.execute("INSERT INTO ziyaret (offline_id, bina_serial, kullanici_id, zaman, sonuc, kayit_zamani) "
              "VALUES ('z1','BN1',1,'2026-09-20 10:00:00','satis','2026-09-20 10:00:00')")
    c.commit()
    c.close()

    conn = db.baglan(yol)
    yapilan = db.gocler(conn)
    assert "bina.kalite" in yapilan and "bina.pasif" in yapilan
    assert {"tablo:ticket", "tablo:bolge_plani", "tablo:tur_raporu", "tablo:bina_bekleyen"} <= set(yapilan)
    assert db.gocler(conn) == []                       # ikinci kez: yapacak iş yok
    assert conn.execute("SELECT COUNT(*) FROM ziyaret").fetchone()[0] == 1
    assert conn.execute("SELECT pasif FROM bina WHERE bina_serial='BN1'").fetchone()[0] == 0
    # Kanıtı olmayan eski bina: yalnız satırdan anlaşılan kurallar çalışır, 'Null' ad temizlenir
    veri_kalitesi.yenile(conn)
    conn.commit()
    ad, kalite = conn.execute("SELECT ad, kalite FROM bina WHERE bina_serial='BN1'").fetchone()
    assert ad == "" and any(f["kural"] == "bos_ad" for f in json.loads(kalite))
    conn.close()


@pytest.mark.parametrize("telefon", [SATISCI_TEL[1]])
def test_satisci_kartinda_kalite_listesi_bos_da_olsa_var(istemci, basliklar, conn, telefon):
    h = basliklar(telefon)
    serial = conn.execute("SELECT bina_serial FROM bina WHERE bolge=1 LIMIT 1").fetchone()[0]
    kart = istemci.get(f"/api/bina/{serial}", headers=h).json()
    assert isinstance(kart["bina"]["kalite"], list)
    assert kart["bina"]["pasif"] is False
    assert isinstance(kart["ticketlar"], list)
