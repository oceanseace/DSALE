"""OneMap canlı bina eşitlemesi (saha/onemap_esitle.py): sahte ArcGIS satırlarıyla.

Ağ yok: eklentinin ArcGIS'ten okuyup sade biçime çevirdiği satırlar doğrudan uca verilir.
"""
from __future__ import annotations

import json

import pytest

from saha import onemap_esitle as om

BINA, LOC = "BN-0000362608", "O25265408"        # tohum verisindeki bina (test_ticket_lokasyon.py ile aynı)


@pytest.fixture
def ek(istemci):
    from operasyon.v2 import boss
    return {"X-Eslesme-Kodu": boss.eslesme_kodu()}


def _is_ekle(conn, is_no: str, lokasyon: str, durum: str = "bekliyor", bina_serial=None, lat=None, lon=None) -> None:
    z = "2026-10-08 10:00:00"
    conn.execute(
        "INSERT INTO is_emri (is_no, boss_task_no, kaynak, task_adi, serit, durum, durum_zamani, bina_serial, lokasyon, "
        "lat, lon, konum_kaynak, acilis, son24, ilk_gorulme, gorulme_zamani, guncelleme) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (is_no, f"T{is_no}", "boss", "Arıza", "Arıza", durum, z, bina_serial, lokasyon, lat, lon,
         "mahalle_merkezi" if lat else None, z, z, z, z, z))
    conn.commit()


def _satir(serial="BN-0099000001-1", loc="O99000001", objectid=5_000_001, firma="DEHANET ECM", lat=40.2001,
           lon=28.9501, **ek) -> dict:
    s = {"objectid": objectid, "om_id": "9900001", "bina_serial": serial, "location_id": loc, "ad": "İSİMSİZ NO 51",
         "site_adi": "", "blok_adi": "", "kapi_no": "51", "turu": "TEK BİNA", "mahalle": "Demirtaş Mh.",
         "ilce": "Osmangazi", "il": "Bursa", "cadde": "", "sokak": "Deneme Sk.", "lat": lat, "lon": lon, "kat": 4,
         "konut": 8, "isyeri": 0, "hp": 8, "firma": firma, "obek": "", "uavt": "123", "teknoloji": "",
         "duzenleme": 1789768678000, "silindi": False}
    s.update(ek)
    return s


def _gonder(istemci, ek, binalar, tur="arama", **govde):
    y = istemci.post("/api/onemap/binalar", headers=ek, json={"tur": tur, "binalar": binalar, **govde})
    assert y.status_code == 200, y.text
    return y.json()


def test_eslesme_kodu_yoksa_401_durum_oturum_ister(istemci):
    assert istemci.get("/api/onemap/gorev", headers={"X-Eslesme-Kodu": "0000-0000"}).status_code == 401
    assert istemci.post("/api/onemap/binalar", json={"binalar": []}).status_code == 401
    assert istemci.get("/api/onemap/durum").status_code == 401


def test_gorev_bilinmeyen_lokasyonu_arar_ilk_seferde_tam_tarama(istemci, ek, conn):
    _is_ekle(conn, "OM1", "O53762030")
    _is_ekle(conn, "OM2", LOC)                       # bilinen lokasyon aranmaz
    _is_ekle(conn, "OM3", "O11111111", durum="kapandi")   # kapalı iş aranmaz
    g = istemci.get("/api/onemap/gorev", headers=ek).json()
    assert g["servis"].endswith("/ONEMAP/BINA/MapServer/0")
    assert "PROTOKOL_FIRMA" in g["taban"] and "IL IN" in g["taban"]
    assert {"OBJECTID", "LOCATION_ID", "ENTEGRASYON_ID", "LAT", "LON"} <= set(g["alanlar"])
    aramalar = [a for a in g["arama"] if a["alan"] == "ENTEGRASYON_ID"]
    assert aramalar and aramalar[0]["degerler"] == ["O53762030"]
    assert aramalar[0]["where"] == "ENTEGRASYON_ID IN ('O53762030')"
    assert g["tarama"] == {"tur": "tam", "basla": 0}
    assert om.bilinmeyen_lokasyonlar(conn) == ["O53762030"]


def test_bilinmeyen_lokasyonun_binasi_eklenir_is_baglanir(istemci, ek, conn):
    _is_ekle(conn, "OM1", "O99000001", lat=40.1, lon=29.0)
    istemci.get("/api/onemap/gorev", headers=ek)
    once = conn.execute("SELECT COUNT(*) FROM bina").fetchone()[0]
    s = _gonder(istemci, ek, [_satir()], aranan={"alan": "ENTEGRASYON_ID", "degerler": ["O99000001"]})
    assert s["eklenen"] == 1 and s["baglanan_is"] == 1
    assert conn.execute("SELECT COUNT(*) FROM bina").fetchone()[0] == once + 1
    b = conn.execute("SELECT * FROM bina WHERE bina_serial='BN-0099000001-1'").fetchone()
    assert b["location_id"] == "O99000001" and b["tellcordia_id"] == "9900001"
    assert b["mahalle"] == "Demirtaş" and b["ilce"] == "Osmangazi" and b["pasif"] == 0
    assert b["ekleme_kaynagi"] == "onemap" and b["bolge"] is not None
    assert abs(b["lat"] - 40.2001) < 1e-9
    k = conn.execute("SELECT * FROM onemap_bina WHERE bina_serial='BN-0099000001-1'").fetchone()
    assert k["kaynak"] == "onemap" and k["eklendi"] == 1 and k["objectid"] == 5_000_001
    e = conn.execute("SELECT * FROM is_emri WHERE is_no='OM1'").fetchone()
    assert e["bina_serial"] == "BN-0099000001-1" and e["konum_kaynak"] == "bina" and abs(e["lat"] - 40.2001) < 1e-9
    o = conn.execute("SELECT * FROM is_emri_olay WHERE is_no='OM1' ORDER BY id DESC").fetchone()
    assert o["tur"] == "aktarim_degisti" and json.loads(o["yeni"])["konum_kaynak"] == "bina"
    assert conn.execute("SELECT durum FROM onemap_arama WHERE deger='O99000001'").fetchone()[0] == "bulundu"
    assert conn.execute("SELECT COUNT(*) FROM bina_degisim WHERE bina_serial='BN-0099000001-1' AND kaynak='onemap'"
                        ).fetchone()[0] == 1
    # ikinci kez aynı satır: hiçbir şey eklenmez, iş yeniden bağlanmaz
    s2 = _gonder(istemci, ek, [_satir()], tur="artimli")
    assert s2["eklenen"] == 0 and s2["baglanan_is"] == 0 and s2["guncellenen"] == 0


def test_baska_bayinin_binasi_pasif_eklenir(istemci, ek, conn):
    _is_ekle(conn, "OM1", "O99000002")
    s = _gonder(istemci, ek, [_satir("BN-0099000002-1", "O99000002", firma="BAŞKA FİRMA")])
    assert s["eklenen"] == 1 and s["baglanan_is"] == 1
    b = conn.execute("SELECT pasif, ekleme_kaynagi, bolge FROM bina WHERE bina_serial='BN-0099000002-1'").fetchone()
    assert b["pasif"] == 1 and b["ekleme_kaynagi"] == "onemap-is" and b["bolge"] is None


def test_bulunamayan_kimlik_denemesi_artar(istemci, ek, conn):
    _is_ekle(conn, "OM1", "O77777777")
    istemci.get("/api/onemap/gorev", headers=ek)
    for _ in range(om.ARAMA_EN_COK):
        _gonder(istemci, ek, [], aranan={"alan": "ENTEGRASYON_ID", "degerler": ["O77777777"]})
    r = conn.execute("SELECT durum, deneme FROM onemap_arama WHERE deger='O77777777'").fetchone()
    assert r["durum"] == "bulunamadi" and r["deneme"] == om.ARAMA_EN_COK
    # yeni denenmiş kimlik 6 saat dolmadan yeniden istenmez
    _is_ekle(conn, "OM2", "O66666666")
    istemci.get("/api/onemap/gorev", headers=ek)
    _gonder(istemci, ek, [], aranan={"alan": "ENTEGRASYON_ID", "degerler": ["O66666666"]})
    g = istemci.get("/api/onemap/gorev", headers=ek).json()
    assert not any("O66666666" in a["degerler"] for a in g["arama"])


def _var_olan(conn) -> dict:
    b = conn.execute("SELECT * FROM bina WHERE bina_serial=?", (BINA,)).fetchone()
    k = json.loads(b["kalite_kaynak"] or "{}")
    return {"b": b, "om_lat": k.get("om_lat"), "om_lon": k.get("om_lon")}


def test_var_olan_bina_yalniz_onemapte_degisince_guncellenir_silinmez(istemci, ek, conn):
    v = _var_olan(conn)
    b = v["b"]
    assert v["om_lat"] is not None
    taban = _satir(BINA, LOC, objectid=42, lat=v["om_lat"], lon=v["om_lon"], ad="ONEMAP ADI", site_adi="OM SİTE",
                   mahalle=b["mahalle"], ilce=b["ilce"], firma="DEHANET ECM")
    s = _gonder(istemci, ek, [taban], tur="tam")
    assert s["guncellenen"] == 0 and s["eklenen"] == 0           # ilk görüş: yalnız taban kaydı
    b1 = conn.execute("SELECT * FROM bina WHERE bina_serial=?", (BINA,)).fetchone()
    assert dict(b1) == dict(b)
    # OneMap'te site adı ve ad değişti, konum 100 m kaydı
    yeni = dict(taban, site_adi="YENİ SİTE", ad="BAŞKA AD", lat=v["om_lat"] + 0.0009)
    s = _gonder(istemci, ek, [yeni], tur="artimli")
    assert s["guncellenen"] == 1
    b2 = conn.execute("SELECT * FROM bina WHERE bina_serial=?", (BINA,)).fetchone()
    assert b2["site_adi"] == "YENİ SİTE"
    assert b2["ad"] == b["ad"]                                      # CRM adı ezilmez
    assert abs(b2["lat"] - (v["om_lat"] + 0.0009)) < 1e-9
    assert b2["bolge"] == b["bolge"] and b2["site_grup"] == b["site_grup"]
    alanlar = {r[0] for r in conn.execute("SELECT alan FROM bina_degisim WHERE bina_serial=? AND kaynak='onemap'",
                                          (BINA,))}
    assert alanlar == {"site_adi", "konum"}
    # silinmiş görünen satır: bina silinmez, değişmez
    once = conn.execute("SELECT COUNT(*) FROM bina").fetchone()[0]
    _gonder(istemci, ek, [dict(yeni, silindi=True, site_adi="X")], tur="artimli")
    assert conn.execute("SELECT COUNT(*) FROM bina").fetchone()[0] == once
    assert conn.execute("SELECT site_adi FROM bina WHERE bina_serial=?", (BINA,)).fetchone()[0] == "YENİ SİTE"


def test_tam_tarama_kaldigi_yerden_surer_bitince_artimliya_gecer(istemci, ek, conn):
    _gonder(istemci, ek, [_satir(objectid=100)], tur="tam", imlec=100)
    g = istemci.get("/api/onemap/gorev", headers=ek).json()
    assert g["tarama"] == {"tur": "tam", "basla": 100}
    _gonder(istemci, ek, [_satir("BN-0099000003-1", "O99000003", objectid=250)], tur="tam", bitti=True)
    g = istemci.get("/api/onemap/gorev", headers=ek).json()
    assert g["tarama"] == {"tur": "artimli", "basla": 250}
    d = om.durum_oku(conn)
    assert d["son_tam"] and d["tam_imlec"] == 0


def test_tur_raporu_konum_bekleyen_bina_eklenir(istemci, ek, conn):
    serial = "BN-0099000009-1"
    veri = {"bina_serial": serial, "tellcordia_id": "9900009", "location_id": "O99000009", "ad": "TUR BİNASI",
            "site_adi_crm": "", "ilce_crm": "Osmangazi", "il": "Bursa", "res_hp": 12, "aktif_res": 3, "firsat": 9,
            "toplam_hp": 12, "soho_hp": 0}
    conn.execute("INSERT INTO bina_bekleyen (bina_serial, tellcordia_id, location_id, veri, durum, eklenme) "
                 "VALUES (?,?,?,?,'konum_bekliyor','2026-10-01 10:00:00')",
                 (serial, "9900009", "O99000009", json.dumps(veri, ensure_ascii=False)))
    conn.commit()
    g = istemci.get("/api/onemap/gorev", headers=ek).json()
    assert any(a["alan"] == "LOCATION_ID" and serial in a["degerler"] for a in g["arama"])
    s = _gonder(istemci, ek, [_satir(serial, "O99000009", om_id="9900009")],
                aranan={"alan": "LOCATION_ID", "degerler": [serial]})
    assert s["eklenen"] == 1
    b = conn.execute("SELECT * FROM bina WHERE bina_serial=?", (serial,)).fetchone()
    assert b["ekleme_kaynagi"] == "tur" and b["res_hp"] == 12 and b["firsat"] == 9
    assert conn.execute("SELECT durum FROM bina_bekleyen WHERE bina_serial=?", (serial,)).fetchone()[0] == "eklendi"
    assert conn.execute("SELECT eklendi FROM onemap_bina WHERE bina_serial=?", (serial,)).fetchone()[0] == 1


def test_durum_ucu(istemci, ek, conn, yonetici):
    _is_ekle(conn, "OM1", "O53762030")
    d = istemci.get("/api/onemap/durum", headers=yonetici).json()
    assert d["bagli"] is False and d["bilinmeyen_lokasyon"] == 1 and d["yeni_bina"] == 0
    istemci.get("/api/onemap/gorev", headers=ek)
    _gonder(istemci, ek, [_satir("BN-0099000004-1", "O53762030")])
    d = istemci.get("/api/onemap/durum", headers=yonetici).json()
    assert d["bagli"] is True and d["son_esitleme"] and d["yeni_bina"] == 1 and d["bilinmeyen_lokasyon"] == 0
    assert d["baglanan_is_toplam"] == 1


def test_gecersiz_kimlik_ve_konumsuz_satir_yok_sayilir(istemci, ek, conn):
    once = conn.execute("SELECT COUNT(*) FROM bina").fetchone()[0]
    s = _gonder(istemci, ek, [_satir("BN x'; DROP", "O1"), _satir("BN-0099000005-1", "O99000005", lat=None, lon=None),
                              _satir("BN-0099000006-1", "O99000006", lat=0.0, lon=0.0)])
    assert s["eklenen"] == 0 and s["konumsuz"] == 2
    assert conn.execute("SELECT COUNT(*) FROM bina").fetchone()[0] == once
