"""lisans/sunucu.py: salt okunur kapısı + /api/lisans uçları, sahte (atılacak) bir FastAPI uygulamasında.

Saha sunucusuna ve canlı veritabanına dokunulmaz; kimlik ``X-Kim`` başlığıyla taklit edilir.
"""
from __future__ import annotations

import datetime as dt
import json

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI, Header, HTTPException
from fastapi.testclient import TestClient

from lisans import lisans as L
from lisans import uret as U
from lisans.sunucu import LisansKapisi, acilis_metni, lisans_yonlendirici

CIHAZ = "AAAA-1111-BBBB-2222-CCCC"
BAS, BIT = dt.date(2026, 10, 1), dt.date(2027, 9, 30)


class Saat:
    def __init__(self, gun):
        self.gun = gun

    def __call__(self):
        return self.gun


def _oturum(x_kim: str | None = Header(default=None)) -> dict:
    if x_kim not in ("yonetici", "satisci"):
        raise HTTPException(401, detail={"hata": "Oturum gerekli.", "kod": "yetkisiz"})
    return {"id": 1 if x_kim == "yonetici" else 2, "rol": x_kim}


def _yonetici(x_kim: str | None = Header(default=None)) -> dict:
    k = _oturum(x_kim)
    if k["rol"] != "yonetici":
        raise HTTPException(403, detail={"hata": "Bu bölüm görevinize kapalı.", "kod": "yasak"})
    return k


@pytest.fixture
def ortam(tmp_path):
    ozel = Ed25519PrivateKey.generate()
    pem = tmp_path / "genel.pem"
    pem.write_bytes(ozel.public_key().public_bytes(serialization.Encoding.PEM,
                                                   serialization.PublicFormat.SubjectPublicKeyInfo))
    saat = Saat(BAS)
    denetci = L.Denetci(tmp_path / "saha" / "lisans.json", genel_anahtar=pem, cihaz=CIHAZ, bugun=saat)
    kayitlar = []

    app = FastAPI()
    app.add_middleware(LisansKapisi, denetci=denetci)
    app.include_router(lisans_yonlendirici(denetci, oturum=_oturum, yukleme_izni=_yonetici,
                                           yonetici_mi=lambda k: k["rol"] == "yonetici",
                                           kayit=lambda k, s: kayitlar.append((k["id"], s.lisans["lisans_no"]))))

    @app.post("/api/ziyaret")
    def ziyaret():
        return {"ok": True}

    @app.post("/api/giris")
    def giris():
        return {"token": "t"}

    @app.get("/api/isler")
    def isler():
        return {"isler": []}

    @app.get("/api/dosya/rapor.xlsx")
    def rapor():
        return {"dosya": "var"}

    def lisans_metni(**kw):
        alan = dict(musteri="ÖRNEK BAYİ", bayi_kodu="00000.00000", baslangic=BAS, bitis=BIT,
                    lisans_no="SL-2026-SUNUCU", duzenleme=BAS)
        alan.update(kw)
        y = U.yuk_kur(**alan)
        imza, kimlik = U.imzala(y, ozel)
        return L.dosya_metni(y, imza, kimlik)

    return TestClient(app), denetci, saat, lisans_metni, kayitlar


Y = {"X-Kim": "yonetici"}
S = {"X-Kim": "satisci"}


def test_tam_calisma_salt_okunur_ve_yeni_lisansla_kaldigi_yerden_devam(ortam):
    istemci, denetci, saat, lisans_metni, kayitlar = ortam
    # 1) lisans yok: ek süre → her şey çalışır
    assert istemci.post("/api/ziyaret").status_code == 200
    durum = istemci.get("/api/lisans", headers=Y).json()
    assert durum["durum"] == L.LISANS_YOK and durum["mod"] == L.TAM and durum["cihaz_kimligi"] == CIHAZ

    # 2) 14 gün geçti: salt okunur
    saat.gun = BAS + dt.timedelta(days=14)
    y = istemci.post("/api/ziyaret", json={"offline_id": "x"})
    assert y.status_code == 503 and y.json()["kod"] == "salt_okunur" and y.headers["retry-after"] == "3600"
    assert istemci.get("/api/isler").status_code == 200                 # okuma sürer
    assert istemci.get("/api/dosya/rapor.xlsx").status_code == 200      # dışa aktarma sürer
    assert istemci.post("/api/giris").status_code == 200                # giriş sürer
    assert istemci.get("/api/lisans", headers=S).json()["goster"] is True

    # 3) yönetici yeni lisansı yükler (salt okunurken de serbest) → yazma geri gelir
    y = istemci.post("/api/lisans", headers=Y, json={"metin": lisans_metni(bitis=dt.date(2027, 10, 14))})
    assert y.status_code == 200, y.text
    assert y.json()["durum"] == L.GECERLI and y.json()["mod"] == L.TAM
    assert kayitlar == [(1, "SL-2026-SUNUCU")]
    assert istemci.post("/api/ziyaret").status_code == 200


def test_get_lisans_ekibe_kisa_yoneticiye_tam(ortam):
    istemci, denetci, saat, lisans_metni, _ = ortam
    denetci.yukle(lisans_metni())
    ekip = istemci.get("/api/lisans", headers=S).json()
    assert set(ekip) == {"durum", "mod", "seviye", "goster", "baslik", "mesaj", "ek_sure_son"}
    assert "ÖRNEK" not in json.dumps(ekip, ensure_ascii=False)
    tam = istemci.get("/api/lisans", headers=Y).json()
    assert tam["lisans"]["musteri"] == "ÖRNEK BAYİ" and tam["kalan_gun"] == (BIT - BAS).days
    assert istemci.get("/api/lisans").status_code == 401


def test_post_lisans_yetki_ve_hatalar(ortam):
    istemci, denetci, saat, lisans_metni, kayitlar = ortam
    metin = lisans_metni()
    assert istemci.post("/api/lisans", headers=S, json={"metin": metin}).status_code == 403
    kurcali = metin.replace("2027-09-30", "2099-09-30")
    y = istemci.post("/api/lisans", headers=Y, json={"metin": kurcali})
    assert y.status_code == 422 and y.json()["detail"]["kod"] == "imza_bozuk"
    y = istemci.post("/api/lisans", headers=Y, json={"metin": lisans_metni(izinli_cihazlar=["DDDD-3333-EEEE-4444-FFFF"])})
    assert y.status_code == 422 and y.json()["detail"]["kod"] == "cihaz_disi" and CIHAZ in y.json()["detail"]["hata"]
    assert istemci.post("/api/lisans", headers=Y, json={"metin": ""}).status_code == 422
    assert not denetci.lisans_yolu.exists() and kayitlar == []


def test_denetim_kapaliyken_kapi_hic_kapanmaz_ve_yukleme_409(tmp_path):
    denetci = L.Denetci(tmp_path / "lisans.json", genel_anahtar=tmp_path / "yok.pem", cihaz=CIHAZ,
                        bugun=Saat(dt.date(2040, 1, 1)))
    app = FastAPI()
    app.add_middleware(LisansKapisi, denetci=denetci)
    app.include_router(lisans_yonlendirici(denetci, oturum=_oturum, yukleme_izni=_yonetici,
                                           yonetici_mi=lambda k: True))

    @app.post("/api/ziyaret")
    def ziyaret():
        return {"ok": True}

    istemci = TestClient(app)
    assert istemci.post("/api/ziyaret").status_code == 200
    assert istemci.get("/api/lisans", headers=Y).json()["durum"] == L.DENETLENMIYOR
    assert istemci.post("/api/lisans", headers=Y, json={"metin": "SAHA1.a.b"}).status_code == 409


def test_denetim_hata_verirse_istek_gecer(tmp_path):
    class Bozuk:
        def sonuc(self):
            raise RuntimeError("disk")

    app = FastAPI()
    app.add_middleware(LisansKapisi, denetci=Bozuk())

    @app.post("/api/ziyaret")
    def ziyaret():
        return {"ok": True}

    assert TestClient(app).post("/api/ziyaret").status_code == 200


def test_acilis_metni(ortam):
    _, denetci, saat, lisans_metni, _ = ortam
    denetci.yukle(lisans_metni())
    assert acilis_metni(denetci.sonuc()) == []
    saat.gun = BIT + dt.timedelta(days=20)
    satirlar = acilis_metni(denetci.sonuc())
    assert satirlar[1] == "  LİSANS: SİSTEM SALT OKUNUR · LİSANSIN SÜRESİ DOLDU"   # Türkçe büyük İ
    assert all(len(s) <= 64 for s in satirlar)
    assert L.buyuk_harf("ılık işçi") == "ILIK İŞÇİ"
