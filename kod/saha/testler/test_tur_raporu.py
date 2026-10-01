"""Tur raporu ve OneMap yenileme (GEREKSINIMLER B2).

Söz: önizleme hiçbir şey yazmaz; uygulama bölgeleri bozmaz, geçmişi silmez, iki kez
uygulanamaz; kısmi bir rapor binaları sessizce pasife alamaz; yeni bina ancak OneMap
konumu gelince haritaya girer ve en yakın bölgeye verilir.
"""
from __future__ import annotations

import json
from io import BytesIO

import pandas as pd
import pytest

from saha import ayarlar, tur_raporu


def _xlsx(satirlar: list[dict], sayfa: str = "ORIGN") -> bytes:
    tampon = BytesIO()
    pd.DataFrame(satirlar).to_excel(tampon, sheet_name=sayfa, index=False)
    return tampon.getvalue()


def _orign(conn, adet: int | None = None) -> list[dict]:
    """Veritabanındaki binalardan tur raporu satırları (ORIGN sütun adlarıyla)."""
    sorgu = ("SELECT bina_serial, tellcordia_id, location_id, ad, crm_site_adi, ilce, il, obek, res_hp, aktif_res, "
             "toplam_hp, soho_hp FROM bina ORDER BY bina_serial")
    if adet:
        sorgu += f" LIMIT {int(adet)}"
    return [{
        "Bina Serial Number": r["bina_serial"], "Tellcordia ID": r["tellcordia_id"], "Location Id": r["location_id"],
        "Adı": r["ad"], "Site Adı": r["crm_site_adi"], "Ilçe": r["ilce"], "IL": r["il"], "Obek Adı": r["obek"],
        "Toplam HP": r["toplam_hp"], "Soho Op": r["soho_hp"], "RES HP": r["res_hp"],
        "Aktif Abone Residential Segment": r["aktif_res"],
    } for r in conn.execute(sorgu).fetchall()]


def _kayitlar(conn) -> list[dict]:
    """``raporu_oku`` biçiminde (normalize edilmiş) bütün binalar."""
    return [{
        "bina_serial": r["bina_serial"], "tellcordia_id": r["tellcordia_id"] or "", "location_id": r["location_id"] or "",
        "ad": r["ad"] or "", "site_adi_crm": r["crm_site_adi"] or "", "blok_adi_crm": "", "kapi_no_crm": "",
        "ilce_crm": r["ilce"] or "", "il": r["il"] or "", "obek": r["obek"] or "", "altyapi": "",
        "protokol_segment": "", "sales_ready": "", "res_hp": int(r["res_hp"] or 0), "aktif_res": int(r["aktif_res"] or 0),
        "toplam_hp": int(r["toplam_hp"] or 0), "soho_hp": int(r["soho_hp"] or 0),
        "firsat": max(int(r["res_hp"] or 0) - int(r["aktif_res"] or 0), 0),
    } for r in conn.execute(
        "SELECT bina_serial, tellcordia_id, location_id, ad, crm_site_adi, ilce, il, obek, res_hp, aktif_res, "
        "toplam_hp, soho_hp FROM bina ORDER BY bina_serial").fetchall()]


def _yeni(serial: str, tell: str, il: str = "Bursa") -> dict:
    return {"bina_serial": serial, "tellcordia_id": tell, "location_id": "O99" + tell[-6:], "ad": f"YENİ {serial}",
            "site_adi_crm": f"YENİ SİTE {serial}", "blok_adi_crm": "", "kapi_no_crm": "", "ilce_crm": "Nilüfer",
            "il": il, "obek": "BRS-ATAEVLER", "altyapi": "", "protokol_segment": "", "sales_ready": "2026-09-01",
            "res_hp": 20, "aktif_res": 5, "toplam_hp": 22, "soho_hp": 2, "firsat": 15}


def _yukle(istemci, yonetici, icerik: bytes, ad: str = "tur.xlsx"):
    return istemci.post("/api/veri/tur-raporu", headers=yonetici, files={"dosya": (ad, icerik)})


# ============================================================ yetki ve doğrulama
@pytest.mark.parametrize("yontem,yol", [
    ("post", "/api/veri/tur-raporu"), ("get", "/api/veri/tur-raporu"), ("post", "/api/veri/tur-raporu/uygula"),
    ("get", "/api/veri/bekleyen"), ("get", "/api/veri/bekleyen.txt"), ("post", "/api/veri/onemap"),
    ("get", "/api/veri/onemap-araci.js"),
])
def test_veri_uclari_satisciya_kapali(istemci, satisci1, yontem, yol):
    ek = {"json": {"tur_id": 1}} if yol.endswith("uygula") else {}
    assert getattr(istemci, yontem)(yol, headers=satisci1, **ek).status_code == 403


def test_excel_olmayan_dosya_ve_eksik_sutun_reddedilir(istemci, yonetici):
    y = _yukle(istemci, yonetici, b"merhaba", "tur.txt")
    assert y.status_code == 400 and y.json()["kod"] == "dosya_gecersiz"
    y = _yukle(istemci, yonetici, _xlsx([{"Bina": "x", "Başka": 1}]))
    assert y.status_code == 400 and y.json()["kod"] == "sutun_eksik"
    # Okunamayan dosya saklanmaz
    assert not list(ayarlar.gelen_dizini().glob("*.xlsx"))


# ============================================================ gerçek Excel: kısmi rapor
def test_kismi_rapor_okunur_onizlenir_ve_pasife_alma_onay_ister(istemci, yonetici, conn):
    satirlar = _orign(conn, 30)
    satirlar[0]["Tellcordia ID"] = "1,61623150353E+011"        # Excel'in bozduğu yazım
    satirlar.append(dict(satirlar[1], **{"Toplam HP": 0}))      # aynı bina iki kez
    once = {r[0]: r[1] for r in conn.execute("SELECT bina_serial, res_hp FROM bina")}

    y = _yukle(istemci, yonetici, _xlsx(satirlar))
    assert y.status_code == 200, y.text
    p = y.json()
    assert p["okuma"]["sayfa"] == "ORIGN" and p["okuma"]["tekil_bina"] == 30
    assert p["okuma"]["tekrar"] == 1 and p["okuma"]["bozuk_tellcordia"] == 1
    assert p["fark"]["cikan_bina"] == 19706 - 30
    assert p["fark"]["pasif_onay_gerekli"] is True
    assert any("KISMİ" in u for u in p["fark"]["uyarilar"])
    assert (ayarlar.gelen_dizini() / p["dosya"]).exists()          # dosya saklandı
    assert {r[0]: r[1] for r in conn.execute("SELECT bina_serial, res_hp FROM bina")} == once   # yazmadı

    y = istemci.post("/api/veri/tur-raporu/uygula", headers=yonetici, json={"tur_id": p["tur_id"]})
    assert y.status_code == 409 and y.json()["kod"] == "pasif_onay_gerekli"
    assert conn.execute("SELECT COUNT(*) FROM bina WHERE pasif=1").fetchone()[0] == 0


# ============================================================ tam akış
def test_tur_raporu_uygula_sonra_onemap_ile_yeni_bina_haritaya(istemci, yonetici, conn, monkeypatch):
    kayit = _kayitlar(conn)
    degisen = [kayit[10], kayit[20], kayit[30]]
    for r in degisen:
        r["res_hp"] += 10
        r["firsat"] = max(r["res_hp"] - r["aktif_res"], 0)
    cikan = [kayit.pop(100)["bina_serial"], kayit.pop(200)["bina_serial"]]
    kayit += [_yeni("BN-TEST-0001", "999000001"), _yeni("BN-TEST-0002", "999000002"),
              _yeni("BN-TEST-0003", "999000003", il="İstanbul")]
    monkeypatch.setattr(tur_raporu, "raporu_oku", lambda _yol: (kayit, {"sayfa": "ORIGN", "satir": len(kayit),
                                                                      "tekil_bina": len(kayit)}))
    bolge_once = {r[0]: r[1] for r in conn.execute("SELECT bina_serial, bolge FROM bina")}

    p = _yukle(istemci, yonetici, _xlsx([{"Bina Serial Number": "x"}])).json()
    f = p["fark"]
    assert (f["yeni_bina"], f["yeni_bina_il_disi"], f["cikan_bina"], f["degisen_bina"]) == (2, 1, 2, 3)
    assert f["pasif_onay_gerekli"] is False
    assert f["sonra"]["bina"] == 19706 - 2 + 2

    u = istemci.post("/api/veri/tur-raporu/uygula", headers=yonetici, json={"tur_id": p["tur_id"]})
    assert u.status_code == 200, u.text
    u = u.json()
    assert (u["guncellenen_bina"], u["pasife_alinan_bina"], u["konum_bekleyen_bina"]) == (3, 2, 2)
    # HP güncellendi, izi kaldı; bölgeler sabit
    r = conn.execute("SELECT res_hp, firsat, tur_tarihi FROM bina WHERE bina_serial=?",
                     (degisen[0]["bina_serial"],)).fetchone()
    assert r["res_hp"] == degisen[0]["res_hp"] and r["firsat"] == degisen[0]["firsat"] and r["tur_tarihi"]
    iz = istemci.get(f"/api/bina/{degisen[0]['bina_serial']}/degisim", headers=yonetici).json()["degisimler"]
    assert any(d["alan"] == "res_hp" and d["kaynak"] == f"tur:{p['tur_id']}" for d in iz)
    assert {r[0]: r[1] for r in conn.execute("SELECT bina_serial, bolge FROM bina")} == bolge_once
    # Rapordan çıkan bina pasif: silinmedi, kapsamaya ve haritaya girmez
    assert conn.execute("SELECT COUNT(*) FROM bina WHERE pasif=1").fetchone()[0] == 2
    assert istemci.get("/api/ozet/kapsama", headers=yonetici).json()["toplam"] == 19704
    assert istemci.get("/api/harita", headers=yonetici).json()["adet"] == 19704
    assert istemci.get(f"/api/bina/{cikan[0]}", headers=yonetici).json()["bina"]["pasif"] is True
    # İkinci kez uygulamak hiçbir şeyi iki kez yazmaz
    y2 = istemci.post("/api/veri/tur-raporu/uygula", headers=yonetici, json={"tur_id": p["tur_id"]}).json()
    assert y2["zaten_uygulandi"] is True

    # --- yeni binalar konum bekliyor; il dışı bina eklenmedi
    bek = istemci.get("/api/veri/bekleyen", headers=yonetici).json()
    assert {b["bina_serial"] for b in bek["binalar"]} == {"BN-TEST-0001", "BN-TEST-0002"}
    kimlikler = istemci.get("/api/veri/bekleyen.txt", headers=yonetici).text.split()
    assert sorted(kimlikler) == ["999000001", "999000002"]
    arac = istemci.get("/api/veri/onemap-araci.js", headers=yonetici)
    assert arac.status_code == 200 and "ONEMAP/BINA/MapServer/0" in arac.text

    # --- OneMap dökümü: biri poligonlu (ID ile), biri yalnız LAT/LON (LOCATION_ID ile), biri alakasız
    komsu = conn.execute("SELECT bina_serial, lat, lon, bolge FROM bina WHERE pasif=0 AND bolge=3 "
                         "ORDER BY bina_serial LIMIT 1").fetchone()
    la, lo = komsu["lat"] + 0.0003, komsu["lon"] + 0.0003
    halka = [[lo, la], [lo + 0.0002, la], [lo + 0.0002, la + 0.0002], [lo, la + 0.0002], [lo, la]]
    dokum = {"features": [
        {"a": {"ID": 999000001, "LOCATION_ID": "BN-TEST-0001", "MAHALLE": "İhsaniye Mh.", "ILCE": "Nilüfer",
               "KAT_ADEDI": 6, "KONUT_SAYISI": 18, "SITE_ADI": "YENİ SİTE", "TURU": "SİTE",
               "LAT": str(la + 0.0001), "LON": str(lo + 0.0001), "ENTEGRASYON_ID": "O99000001"}, "g": [halka]},
        {"attributes": {"ID": 5555, "LOCATION_ID": "BN-TEST-0002", "LAT": str(la + 0.001), "LON": str(lo),
                        "KONUT_SAYISI": 8}, "geometry": None},
        {"a": {"ID": 123, "LOCATION_ID": "BN-BASKA"}, "g": []},
    ]}
    y = istemci.post("/api/veri/onemap", headers=yonetici,
                     files={"dosya": ("onemap_yeni.json", json.dumps(dokum).encode())})
    assert y.status_code == 200, y.text
    s = y.json()
    assert (s["eklenen"], s["eslesmeyen"], s["hala_bekleyen"]) == (2, 1, 0)
    b1 = conn.execute("SELECT * FROM bina WHERE bina_serial='BN-TEST-0001'").fetchone()
    assert abs(b1["lat"] - (la + 0.0001)) < 1e-5 and abs(b1["lon"] - (lo + 0.0001)) < 1e-5   # poligon merkezi
    assert b1["bolge"] == komsu["bolge"] and b1["kat"] == 6 and b1["mahalle"] == "İhsaniye"
    assert b1["ekleme_kaynagi"] == "tur" and b1["kalite"] is not None
    assert conn.execute("SELECT durum FROM bina_durum WHERE bina_serial='BN-TEST-0001'").fetchone()[0] == "bekliyor"
    assert conn.execute("SELECT COUNT(*) FROM bina_geometri_ek").fetchone()[0] == 1
    b2 = conn.execute("SELECT lat, lon, kat FROM bina WHERE bina_serial='BN-TEST-0002'").fetchone()
    assert abs(b2["lat"] - (la + 0.001)) < 1e-9 and b2["kat"] >= 1                          # LAT/LON'dan
    assert istemci.get("/api/harita", headers=yonetici).json()["adet"] == 19706
    # 3B geometride yeni binanın poligonu var
    geo = istemci.get("/api/binalar/geometri", headers=yonetici).json()
    i = geo["serial"].index("BN-TEST-0001")
    assert geo["ofs"][i + 1] - geo["ofs"][i] == 5
    # Aynı döküm ikinci kez: hiçbir şey iki kez eklenmez
    y = istemci.post("/api/veri/onemap", headers=yonetici,
                     files={"dosya": ("onemap_yeni.json", json.dumps(dokum).encode())}).json()
    assert y["eklenen"] == 0 and y["zaten_haritada"] == 2


def test_eski_tur_raporu_yenisinden_sonra_uygulanamaz(istemci, yonetici, conn, monkeypatch):
    kayit = _kayitlar(conn)
    monkeypatch.setattr(tur_raporu, "raporu_oku", lambda _yol: (kayit, {"sayfa": "ORIGN", "satir": len(kayit)}))
    t1 = _yukle(istemci, yonetici, _xlsx([{"a": 1}])).json()["tur_id"]
    t2 = _yukle(istemci, yonetici, _xlsx([{"a": 2}])).json()["tur_id"]
    assert istemci.post("/api/veri/tur-raporu/uygula", headers=yonetici, json={"tur_id": t2}).status_code == 200
    y = istemci.post("/api/veri/tur-raporu/uygula", headers=yonetici, json={"tur_id": t1})
    assert y.status_code == 409 and y.json()["kod"] == "daha_yeni_var"
    liste = istemci.get("/api/veri/tur-raporu", headers=yonetici).json()
    assert [r["durum"] for r in liste["raporlar"]] == ["uygulandi", "eskidi"]
    assert liste["son_uygulanan"]["tur_id"] == t2


def test_onemap_bos_ya_da_bozuk_dosya(istemci, yonetici):
    y = istemci.post("/api/veri/onemap", headers=yonetici, files={"dosya": ("x.json", b"{bozuk")})
    assert y.status_code == 400
    y = istemci.post("/api/veri/onemap", headers=yonetici, files={"dosya": ("x.json", b'{"features": []}')})
    assert y.status_code == 400 and y.json()["kod"] == "onemap_bos"


def test_kurulum_yeniden_calisinca_tur_ve_plan_geri_donmez(yonetici, istemci, db_yolu, conn, monkeypatch):
    """``python -m saha.kur`` tekrar çalışırsa tur raporuyla gelen HP'ler ve plan bölgeleri korunur."""
    from saha import kur

    kayit = _kayitlar(conn)
    kayit[5]["res_hp"] += 7
    kayit[5]["firsat"] = max(kayit[5]["res_hp"] - kayit[5]["aktif_res"], 0)
    monkeypatch.setattr(tur_raporu, "raporu_oku", lambda _yol: (kayit, {"sayfa": "ORIGN"}))
    t = _yukle(istemci, yonetici, _xlsx([{"a": 1}])).json()["tur_id"]
    istemci.post("/api/veri/tur-raporu/uygula", headers=yonetici, json={"tur_id": t})
    p = istemci.get("/api/bolgeleme/onizleme", headers=yonetici, params={"n": 10}).json()
    assert istemci.post("/api/bolgeleme/uygula", headers=yonetici,
                        json={"n": 10, "plan_ref": p["plan_ref"]}).status_code == 200
    bolge = {r[0]: r[1] for r in conn.execute("SELECT bina_serial, bolge FROM bina")}

    kur.kur(yol=db_yolu, sessiz=True)

    assert conn.execute("SELECT res_hp FROM bina WHERE bina_serial=?",
                        (kayit[5]["bina_serial"],)).fetchone()[0] == kayit[5]["res_hp"]
    assert {r[0]: r[1] for r in conn.execute("SELECT bina_serial, bolge FROM bina")} == bolge
