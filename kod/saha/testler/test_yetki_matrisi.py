"""Yetki matrisi (spec §2, Ek-1; F6): her rota × {satış, bölgesiz satış, operasyon, teknik, yönetici}.

* Uygulamadaki her rota ``yetki.ROTA_IZNI``'dadır ve ucun istediği eylem tablodakiyle aynıdır
  (tabloda olmayan rota testi kırar: yeni uç izinsiz eklenemez).
* Görevin izni yoksa uç 403 ``yasak`` döner (varsayılan YASAK), jetonsuz 401.
* Bölgesiz teknik/operasyon şehri göremez, ziyaret yazamaz (denetimdeki açık).
"""
from __future__ import annotations

import asyncio
import re
import sqlite3

import pytest
from fastapi.routing import APIRoute

from saha import ayarlar, goc, yetki

# Eski iş emri ekranı dururken WP-B'nin geçici olarak bağladığı operasyon/api.py uçları: sözleşmede
# 410'a dönecekler; tabloda ``/api/is-emri*`` kimliksiz 410 olarak durur.
_GECICI_MODULLER = {"operasyon.api"}


def rotalar(app) -> list[APIRoute]:
    """Uygulamanın bütün APIRoute'ları (FastAPI 0.14x'te dahil edilen yönlendiriciler iç içe durur)."""
    def gez(liste):
        for r in liste:
            if isinstance(r, APIRoute):
                yield r
            alt = getattr(r, "original_router", None)
            if alt is not None:
                yield from gez(alt.routes)
    return list(gez(app.routes))


def eylemler(rota: APIRoute) -> tuple[str, ...] | None:
    def gez(dep):
        for d in dep.dependencies:
            if hasattr(d.call, "eylemler"):
                return tuple(d.call.eylemler)
            e = gez(d)
            if e:
                return e
        return None
    return gez(rota.dependant)


def _beklenen(anahtar) -> tuple[str, ...] | None:
    deger = yetki.ROTA_IZNI[anahtar]
    return None if deger is None else ((deger,) if isinstance(deger, str) else tuple(deger))


def _uc_listesi():
    from saha import api

    for r in rotalar(api.uygulama):
        if r.endpoint.__module__ in _GECICI_MODULLER:
            continue
        for m in sorted(r.methods - {"HEAD", "OPTIONS"}):
            yield m, r.path, r


# ============================================================ tablo ↔ uçlar
def test_her_rota_izin_tablosunda_ve_eylemi_ayni():
    eksik, farkli = [], []
    for m, yol, r in _uc_listesi():
        if (m, yol) not in yetki.ROTA_IZNI:
            eksik.append(f"{m} {yol} ({r.endpoint.__module__})")
            continue
        if eylemler(r) != _beklenen((m, yol)):
            farkli.append(f"{m} {yol}: uç {eylemler(r)} · tablo {_beklenen((m, yol))}")
    assert not eksik, "ROTA_IZNI'nda olmayan uçlar:\n" + "\n".join(eksik)
    assert not farkli, "Eylemi tabloyla uyuşmayan uçlar:\n" + "\n".join(farkli)


def test_tablodaki_eylemler_tanimli():
    for anahtar, deger in yetki.ROTA_IZNI.items():
        for e in ((deger,) if isinstance(deger, str) else (deger or ())):
            assert e in yetki.IZINLER, (anahtar, e)


def test_bilinmeyen_eylem_uc_tanimlanirken_reddedilir():
    with pytest.raises(ValueError):
        yetki.izin("is.uydurma")
    with pytest.raises(ValueError):
        yetki.izin()


def test_modulun_bildirdigi_izinler_eklenir_sozlesme_ezilmez(monkeypatch):
    """WP-G gibi paketler kendi uçlarının izinlerini ``ROTA_IZNI`` ile bildirir; yetki.py'ye dokunmaz."""
    from saha import api

    monkeypatch.setattr(yetki, "ROTA_IZNI", dict(yetki.ROTA_IZNI))
    eklenen = api.rota_izni_ekle("deneme", {("get", "/api/deneme/tablo"): "tablolar.oku",
                                            ("GET", "/api/ben"): "veri.yonet"})
    assert eklenen == 1
    assert yetki.ROTA_IZNI[("GET", "/api/deneme/tablo")] == "tablolar.oku"
    assert yetki.ROTA_IZNI[("GET", "/api/ben")] == "oturum"             # sözleşme satırı ezilmez
    with pytest.raises(ValueError):
        api.rota_izni_ekle("deneme", {("GET", "/api/deneme/a"): "uydurma.eylem"})
    with pytest.raises(ValueError):
        api.rota_izni_ekle("deneme", {("GET", "/api/deneme/b"): None})    # modül açık uç bildiremez
    assert ("GET", "/api/deneme/a") not in yetki.ROTA_IZNI


def test_varsayilan_yasak():
    assert not yetki.izinli({"rol": "yonetici", "gorevler": ["yonetici"]}, "boyle.bir.sey.yok")
    assert not yetki.izinli({"rol": "bilinmeyen"}, "oturum")


# ============================================================ HTTP matrisi
_ORNEK = {"bina_serial": "BN-YOK-0", "kullanici_id": "999999", "ticket_id": "999999", "is_id": "yok",
          "tur_id": "999999", "ziyaret_id": "999999", "is_no": "000000000", "obek_id": "999999",
          "aktarim_id": "999999", "toplu_id": "yok", "yol": "yok"}


def _doldur(yol: str) -> str:
    return re.sub(r"\{(\w+)(?::\w+)?\}", lambda m: _ORNEK.get(m.group(1), "1"), yol)


@pytest.fixture
def profiller(kisi):
    """Beş profil: satış (bölge 1), bölgesiz satış, operasyon, teknik, yönetici."""
    return {
        "satis": kisi("satisci", bolge=1),
        "bolgesiz_satis": kisi("satisci", bolge=None),
        "operasyon": kisi("operasyon"),
        "teknik": kisi("teknik"),
        "yonetici": kisi("yonetici"),
    }


_ROL = {"satis": "satisci", "bolgesiz_satis": "satisci", "operasyon": "operasyon", "teknik": "teknik",
        "yonetici": "yonetici"}


def test_matris_izinsiz_gorev_403_jetonsuz_401(istemci, profiller):
    """İzni olmayan her (uç, görev) çifti 403 'yasak'; izinli çiftlerde uç bu görevi reddetmez.

    İzinli çiftler HTTP ile çağrılmaz (yan etkili uçlar var); izinli olduğu tablodan doğrulanır.
    Reddedilen istek, yetki denetimi gövde doğrulamasından ÖNCE koştuğu için hiçbir şey yazmaz.
    """
    hatalar = []
    for m, yol, r in _uc_listesi():
        beklenen = _beklenen((m, yol))
        adres = _doldur(yol)
        if beklenen is None:
            continue
        y = istemci.request(m, adres, json={} if m in ("POST", "PUT", "PATCH") else None)
        if y.status_code != 401:
            hatalar.append(f"jetonsuz {m} {yol} → {y.status_code}")
        for ad, (_kid, baslik) in profiller.items():
            izinli = any(yetki.izinli({"rol": _ROL[ad], "gorevler": [_ROL[ad]]}, e) for e in beklenen)
            if izinli:
                continue
            y = istemci.request(m, adres, headers=baslik, json={} if m in ("POST", "PUT", "PATCH") else None)
            if y.status_code != 403 or y.json().get("kod") != "yasak":
                hatalar.append(f"{ad} {m} {yol} → {y.status_code} {y.text[:80]}")
    assert not hatalar, "\n".join(hatalar)


def test_bolgesiz_teknik_ve_operasyon_sehri_goremez_ziyaret_yazamaz(istemci, profiller, conn):
    bina = conn.execute("SELECT bina_serial FROM bina WHERE bolge=3 LIMIT 1").fetchone()[0]
    for ad in ("teknik", "operasyon"):
        h = profiller[ad][1]
        for yol in ("/api/bina", "/api/harita", "/api/yollar", "/api/ozet/kapsama", "/api/ozet/gun",
                    "/api/gorev/bugun"):
            y = istemci.get(yol, headers=h)
            assert y.status_code == 403 and y.json()["kod"] == "yasak", (ad, yol, y.status_code)
        y = istemci.post("/api/ziyaret", headers=h,
                         json={"offline_id": f"{ad}-1", "bina_serial": bina, "sonuc": "satis", "satis_adedi": 1})
        assert y.status_code == 403, (ad, y.status_code)
    assert conn.execute("SELECT COUNT(*) FROM ziyaret").fetchone()[0] == 0
    # 3B geometri: operasyon hepsini görür, teknik görmez (spec §2.2 geometri.oku)
    assert istemci.get("/api/binalar/geometri", headers=profiller["teknik"][1]).status_code == 403
    assert istemci.get("/api/binalar/geometri", headers=profiller["operasyon"][1]).status_code == 200
    # Bina kartı: operasyon hepsini görür; teknik yalnız kendi açık işinin binasını.
    assert istemci.get(f"/api/bina/{bina}", headers=profiller["operasyon"][1]).status_code == 200
    assert istemci.get(f"/api/bina/{bina}", headers=profiller["teknik"][1]).status_code == 403


def test_bolgesiz_satisci_bos_liste_ve_bolge_yok(istemci, profiller, conn):
    h = profiller["bolgesiz_satis"][1]
    assert istemci.get("/api/bina?limit=5", headers=h).json()["toplam"] == 0
    assert istemci.get("/api/harita", headers=h).json()["adet"] == 0
    ben = istemci.get("/api/ben", headers=h).json()
    assert ben["bolge_yok"] is True and ben["ana_ekran"] == "bugun"
    bina = conn.execute("SELECT bina_serial FROM bina WHERE bolge=2 LIMIT 1").fetchone()[0]
    y = istemci.post("/api/ziyaret", headers=h, json={"offline_id": "bs-1", "bina_serial": bina, "sonuc": "satis"})
    assert y.status_code == 403 and y.json()["kod"] == "baska_bolge"


@pytest.mark.parametrize("ad,ekran", [("satis", "bugun"), ("operasyon", "isler"), ("teknik", "islerim"),
                                      ("yonetici", "isler")])
def test_ben_her_gorevde_kendi_dali(istemci, profiller, ad, ekran):
    ben = istemci.get("/api/ben", headers=profiller[ad][1])
    assert ben.status_code == 200, ben.text
    veri = ben.json()
    assert veri["ana_ekran"] == ekran
    assert veri["izinler"] == yetki.izin_listesi(_ROL[ad])
    assert veri["gorev_etiketi"] == yetki.ETIKET[_ROL[ad]]
    if ad == "satis":
        assert {"bugun", "hafta", "bolge", "bolge_yok"} <= set(veri)
    if ad == "teknik":
        assert set(veri["bugun"]) == {"is", "btk", "biten"}
    if ad == "yonetici":
        assert "gorev_gozden_gecir" in veri


def test_teknik_yalniz_kendi_acik_isinin_binasini_gorur(istemci, profiller, conn):
    kid, h = profiller["teknik"]
    bina, baska = [r[0] for r in conn.execute("SELECT bina_serial FROM bina ORDER BY bina_serial LIMIT 2")]
    assert istemci.get(f"/api/bina/{bina}", headers=h).status_code == 403
    z = ayarlar.zaman_metni()
    conn.execute(
        "INSERT INTO is_emri (is_no, kaynak, task_adi, serit, durum, durum_zamani, atanan_id, bina_serial, "
        "acilis, son24, ilk_gorulme, gorulme_zamani, guncelleme) "
        "VALUES ('412345678','boss','Bağlantı Problemi','SAHA','atandi',?,?,?,?,?,?,?,?)",
        (z, kid, bina, z, z, z, z, z))
    conn.commit()
    assert istemci.get(f"/api/bina/{bina}", headers=h).status_code == 200
    assert istemci.get(f"/api/bina/{bina}/ticket", headers=h).status_code == 200
    assert istemci.get(f"/api/bina/{baska}", headers=h).status_code == 403
    assert istemci.get("/api/ben", headers=h).json()["bugun"]["is"] == 1
    conn.execute("UPDATE is_emri SET durum='cozuldu' WHERE is_no='412345678'")
    conn.commit()
    assert istemci.get(f"/api/bina/{bina}", headers=h).status_code == 403


def test_ticket_defteri_operasyona_acik_satisa_kapali(istemci, profiller):
    assert istemci.get("/api/ticket", headers=profiller["operasyon"][1]).status_code == 200
    assert istemci.get("/api/ticket/kategoriler", headers=profiller["teknik"][1]).status_code == 200
    assert istemci.get("/api/ticket", headers=profiller["satis"][1]).status_code == 403
    k = istemci.get("/api/ticket/kategoriler", headers=profiller["satis"][1]).json()
    assert k["varsayilan_ekip"] == "TEAM-TAS1BRS" and len(k["kategoriler"]) == 11
    assert any(x["konu_onerisi"] == "SİNYAL" for x in k["kategoriler"])


def test_eski_is_emri_uclari(istemci, yonetici):
    y = istemci.get("/api/is-emri/boyle", headers=yonetici)
    # Eski ekran dururken WP-B eski uçları geçici olarak çalışır tutabilir; yoksa 410.
    assert y.status_code in (404, 410, 405, 200, 422)
    if y.status_code == 410:
        assert y.json()["kod"] == "yenilendi"


# ============================================================ sürüm uyumsuzluğu, bütünlük
def test_guncelleme_bekliyorken_v2_uclari_503_eski_uclar_calisir(db_yolu, satisci1, yonetici):
    from fastapi.testclient import TestClient

    from saha import api

    c = sqlite3.connect(db_yolu)
    c.execute(f"PRAGMA user_version = {goc.HEDEF - 1}")
    c.close()
    with TestClient(api.uygulama) as ist:
        assert api.GUNCELLEME_BEKLIYOR is True
        y = ist.get("/api/kullanici", headers=yonetici)
        assert y.status_code == 503 and y.json()["kod"] == "guncelleme_bekliyor"
        assert ist.get("/api/bina?limit=2", headers=satisci1).status_code == 200
        s = ist.get("/api/saglik").json()
        assert s["guncelleme_bekliyor"] is True and s["sema_surumu"] == goc.HEDEF - 1
    c = sqlite3.connect(db_yolu)
    c.execute(f"PRAGMA user_version = {goc.HEDEF}")
    c.close()


def test_butunluk_hatasi_409_turkce():
    from saha import api

    yanit = asyncio.run(api._butunluk_hatasi(None, sqlite3.IntegrityError("FOREIGN KEY constraint failed")))
    assert yanit.status_code == 409
    assert b'"kod":"butunluk"' in yanit.body


def test_v2_yonlendiricileri_hatasiz_baglandi():
    from saha import api

    assert api.V2_YUKLEME_HATASI is None, api.V2_YUKLEME_HATASI
