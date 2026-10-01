"""3B dijital ikiz geometrisi (A9) ve harita altlığı ayarı (A8)."""
from __future__ import annotations

import json


def test_geometri_sikistirilmis_etagli_ve_dogru(istemci, yonetici, conn):
    y = istemci.get("/api/binalar/geometri", headers={**yonetici, "Accept-Encoding": "gzip"})
    assert y.status_code == 200
    assert y.headers["content-encoding"] == "gzip" and y.headers["etag"]
    g = y.json()                                     # istemci gzip'i kendisi açar
    assert g["adet"] == 19706 == len(g["serial"]) == len(g["kat"]) == len(g["lat"])
    assert len(g["ofs"]) == g["adet"] + 1 and len(g["fark"]) == 2 * g["ofs"][-1]
    assert g["poligonsuz"] < 50
    # İlk binanın poligonu merkezinin ~100 m yakınında
    i = 0
    for k in range(g["ofs"][i], g["ofs"][i + 1]):
        assert abs(g["fark"][2 * k] * g["olcek"]) < 0.002 and abs(g["fark"][2 * k + 1] * g["olcek"]) < 0.002
    # Aynı sürümde tekrar: 304
    y2 = istemci.get("/api/binalar/geometri", headers={**yonetici, "If-None-Match": y.headers["etag"]})
    assert y2.status_code == 304
    # Kat düzeltmesi 3B'ye yansır (1 katlı 38 daireli bina)
    j = g["serial"].index("BN-00001691-196")
    assert g["kat"][j] > 1


def test_geometri_ham_yanit_gzip_istenmezse(yonetici, db_yolu):
    from fastapi.testclient import TestClient

    from saha import api

    with TestClient(api.uygulama) as c:
        y = c.get("/api/binalar/geometri", headers={**yonetici, "Accept-Encoding": "identity"})
        assert y.status_code == 200 and "content-encoding" not in y.headers
        assert json.loads(y.content)["adet"] == 19706


def test_geometri_satisci_yalniz_kendi_bolgesi(istemci, satisci1, conn):
    g = istemci.get("/api/binalar/geometri", headers=satisci1).json()
    bolge1 = conn.execute("SELECT COUNT(*) FROM bina WHERE bolge=1").fetchone()[0]
    assert g["adet"] == bolge1 and g["bolge"] == 1
    assert istemci.get("/api/binalar/geometri?bolge=4", headers=satisci1).status_code == 403


def test_altlik_varsayilanlari_ve_csp(istemci, satisci1):
    a = istemci.get("/api/ayar/altlik", headers=satisci1)
    assert a.status_code == 200
    v = a.json()
    assert v["sokak_url"].startswith("https://tile.openstreetmap.org/")
    assert "World_Imagery" in v["uydu_url"] and v["varsayilan"] is True
    assert "OpenStreetMap" in v["atif"] and v["lisans_notu"]
    csp = a.headers["content-security-policy"]
    assert "https://tile.openstreetmap.org" in csp and "https://server.arcgisonline.com" in csp
    assert "connect-src 'self' https://tile.openstreetmap.org" in csp
    assert a.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert istemci.get("/api/ayar/altlik").status_code == 401


def test_altlik_yonetici_degistirir_csp_hemen_guncellenir(istemci, yonetici, satisci1):
    assert istemci.put("/api/ayar/altlik", headers=satisci1, json={"sokak_url": "x"}).status_code == 403
    kotu = istemci.put("/api/ayar/altlik", headers=yonetici, json={"sokak_url": "http://evil.example/{z}/{x}/{y}"})
    assert kotu.status_code == 400
    kotu = istemci.put("/api/ayar/altlik", headers=yonetici, json={"sokak_url": "https://a.b/{z}/{x}"})
    assert kotu.status_code == 400
    y = istemci.put("/api/ayar/altlik", headers=yonetici, json={
        "sokak_url": "https://{s}.harita.turkcell.com.tr/karo/{z}/{x}/{y}.png", "atif": "© Turkcell"})
    assert y.status_code == 200, y.text
    assert y.json()["sokak_atif"] == "© Turkcell" and y.json()["varsayilan"] is False
    csp = istemci.get("/api/saglik").headers["content-security-policy"]
    assert "https://*.harita.turkcell.com.tr" in csp and "tile.openstreetmap.org" not in csp
    y = istemci.put("/api/ayar/altlik", headers=yonetici, json={"varsayilana_don": True})
    assert y.json()["varsayilan"] is True
    assert "tile.openstreetmap.org" in istemci.get("/api/saglik").headers["content-security-policy"]
