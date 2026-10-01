"""Bölge planlayıcı (GEREKSINIMLER B3, B5): "8 ekipten 14 ekibe çıkınca bölgeler dinamik bölünsün".

Her testte ana söz aynı: ziyaret geçmişi HİÇ değişmez, hiçbir hesap silinmez,
geri almak birebir eski hâle döndürür, yarıda kalan işlem hiçbir iz bırakmaz.
"""
from __future__ import annotations

import time
import zipfile
from io import BytesIO

import pytest

from saha import bolgeleme

from .conftest import SATISCI_TEL


def _atama(conn) -> dict[str, int]:
    return {r[0]: r[1] for r in conn.execute("SELECT bina_serial, bolge FROM bina")}


def _satiscilar(conn) -> list[tuple]:
    return [tuple(r) for r in conn.execute(
        "SELECT id, ad, telefon, bolge, aktif FROM kullanici WHERE rol='satisci' ORDER BY id")]


def _onizle(istemci, yonetici, n: int, **p) -> dict:
    y = istemci.get("/api/bolgeleme/onizleme", headers=yonetici, params={"n": n, **p})
    assert y.status_code == 200, y.text
    return y.json()


def _ziyaret_yaz(conn, adet: int = 5) -> int:
    """Birkaç gerçek ziyaret: plan değişince geçmişin DOKUNULMADIĞINI görmek için."""
    kid = conn.execute("SELECT id FROM kullanici WHERE rol='satisci' AND bolge=1").fetchone()[0]
    seriler = [r[0] for r in conn.execute("SELECT bina_serial FROM bina WHERE bolge=1 LIMIT ?", (adet,))]
    for i, s in enumerate(seriler):
        conn.execute("INSERT INTO ziyaret (offline_id, bina_serial, kullanici_id, zaman, sonuc, kayit_zamani) "
                     "VALUES (?,?,?,?, 'ilgilenmedi', ?)", (f"plan-{i}", s, kid, "2026-09-20 10:00:00",
                                                          "2026-09-20 10:00:00"))
        conn.execute("UPDATE bina_durum SET ziyaret_sayisi=1, son_ziyaret='2026-09-20 10:00:00', "
                     "son_sonuc='ilgilenmedi', durum='ziyaret_edildi' WHERE bina_serial=?", (s,))
    conn.commit()
    return len(seriler)


# ============================================================ yetki
@pytest.mark.parametrize("yontem,yol", [
    ("get", "/api/bolgeleme/durum"), ("get", "/api/bolgeleme/onizleme?n=14"),
    ("post", "/api/bolgeleme/uygula"), ("post", "/api/bolgeleme/geri-al"), ("get", "/api/bolgeleme/excel"),
])
def test_bolgeleme_satisciya_kapali(istemci, satisci1, yontem, yol):
    govde = {"json": {"n": 14, "plan_ref": "hazir:14:res_hp:x"}} if yontem == "post" else {}
    assert getattr(istemci, yontem)(yol, headers=satisci1, **govde).status_code == 403


# ============================================================ durum ve önizleme
def test_durum_bugunku_8_bolge_ve_satiscilari(istemci, yonetici):
    d = istemci.get("/api/bolgeleme/durum", headers=yonetici).json()
    assert d["n"] == 8 and len(d["bolgeler"]) == 8
    assert d["toplam"]["bina"] == 19706
    assert all(len(b["satiscilar"]) == 1 for b in d["bolgeler"])
    assert d["geri_alinabilir"] is False and d["plan"] is None
    assert 14 in d["hazir_nler"]
    assert istemci.get("/api/saglik").json()["bolge_sayisi"] == 8


def test_onizleme_14_hazir_plan_farki_gosterir_yazmaz(istemci, yonetici, conn):
    once = _atama(conn)
    p = _onizle(istemci, yonetici, 14)
    assert p["hazir"] is True and p["kaynak"] == "hazir" and p["n"] == 14
    assert [b["bolge"] for b in p["bolgeler"]] == list(range(1, 15))
    # 1-8 kendi satışçısıyla kalır, 9-14 için yer tutucu hesap açılacak
    assert p["fark"]["yeni_satisci_acilacak_bolgeler"] == list(range(9, 15))
    assert all(len(b["satiscilar"]) == 1 for b in p["bolgeler"][:8])
    assert p["fark"]["bolgesiz_kalacak_satiscilar"] == []
    assert abs(p["denge"]["sapma_maks"]) < 0.01 and abs(p["denge"]["sapma_min"]) < 0.01
    assert sum(b["bina"] for b in p["bolgeler"]) == 19706
    assert 0 < p["fark"]["el_degistiren_bina"] < 19706
    assert len(p["bina_bolge"]) == 19706 and set(p["bina_bolge"]) == set(range(1, 15))
    assert all(b["poligon"] for b in p["bolgeler"])
    assert _atama(conn) == once                     # önizleme hiçbir şey yazmaz


def test_onizleme_bugunku_planla_ayni_ise_soyler(istemci, yonetici):
    p = _onizle(istemci, yonetici, 8)
    assert p["fark"]["el_degistiren_bina"] == 0
    assert any("aynı" in u for u in p["uyarilar"])


def test_onizleme_gecersiz_girdiler(istemci, yonetici):
    assert istemci.get("/api/bolgeleme/onizleme", headers=yonetici, params={"n": 1}).status_code == 422
    assert istemci.get("/api/bolgeleme/onizleme", headers=yonetici,
                       params={"n": 14, "olcu": "uydurma"}).status_code == 400


# ============================================================ uygula / geri al
def test_8den_14e_uygula_sonra_geri_al_birebir_eski_hal(istemci, yonetici, conn):
    ziyaret = _ziyaret_yaz(conn)
    once_atama, once_satisci = _atama(conn), _satiscilar(conn)
    ziyaret_once = [tuple(r) for r in conn.execute("SELECT * FROM ziyaret ORDER BY id")]
    p = _onizle(istemci, yonetici, 14)

    y = istemci.post("/api/bolgeleme/uygula", headers=yonetici,
                     json={"n": 14, "plan_ref": p["plan_ref"], "notu": "14 ekip"})
    assert y.status_code == 200, y.text
    u = y.json()
    assert len(u["yeni_satiscilar"]) == 6
    assert all(len(h["davet_kodu"]) == 6 for h in u["yeni_satiscilar"])
    assert {h["bolge"] for h in u["yeni_satiscilar"]} == set(range(9, 15))

    sonra = _atama(conn)
    assert set(sonra.values()) == set(range(1, 15))
    assert [tuple(r) for r in conn.execute("SELECT * FROM ziyaret ORDER BY id")] == ziyaret_once
    assert conn.execute("SELECT COUNT(*) FROM ziyaret").fetchone()[0] == ziyaret
    assert istemci.get("/api/saglik").json()["bolge_sayisi"] == 14
    d = istemci.get("/api/bolgeleme/durum", headers=yonetici).json()
    assert d["n"] == 14 and d["geri_alinabilir"] is True
    assert all(b["satiscilar"] for b in d["bolgeler"])
    # Harita önbelleği yeni bölgeleri görür (sunucu yeniden başlamadan)
    h = istemci.get("/api/harita", headers=yonetici).json()
    assert max(h["bolge"]) == 14
    # Yönetici artık 14. bölgeye satışçı kaydedebilir
    yeni = istemci.post("/api/kullanici", headers=yonetici,
                        json={"ad": "Deneme Kişi", "telefon": "05321112299", "rol": "satisci", "bolge": 14})
    assert yeni.status_code == 200, yeni.text

    g = istemci.post("/api/bolgeleme/geri-al", headers=yonetici)
    assert g.status_code == 200, g.text
    assert _atama(conn) == once_atama
    # Eski satışçılar eski bölgelerinde; yer tutucular SİLİNMEDİ, kapatıldı
    geri = {r[0]: r for r in _satiscilar(conn)}
    for s in once_satisci:
        assert geri[s[0]][3] == s[3] and geri[s[0]][4] == s[4]
    for h in u["yeni_satiscilar"]:
        assert geri[h["id"]][4] == 0
    assert {k["id"] for k in g.json()["kapatilan_yer_tutucular"]} == {h["id"] for h in u["yeni_satiscilar"]}
    assert [tuple(r) for r in conn.execute("SELECT * FROM ziyaret ORDER BY id")] == ziyaret_once
    assert istemci.get("/api/saglik").json()["bolge_sayisi"] == 8
    # Geçmişte iki plan + başlangıç kaydı var, hiçbiri silinmedi
    plan = conn.execute("SELECT kaynak, aktif, geri_alindi FROM bolge_plani ORDER BY id").fetchall()
    assert [tuple(r) for r in plan] == [("baslangic", 1, 0), ("hazir", 0, 1)]
    # Başlangıçtan daha geriye gidilemez
    assert istemci.post("/api/bolgeleme/geri-al", headers=yonetici).status_code == 409


def test_onizlemeden_sonra_degisen_plan_uygulanmaz(istemci, yonetici):
    p = _onizle(istemci, yonetici, 14)
    sahte = p["plan_ref"].rsplit(":", 1)[0] + ":000000000000"
    y = istemci.post("/api/bolgeleme/uygula", headers=yonetici, json={"n": 14, "plan_ref": sahte})
    assert y.status_code == 409 and y.json()["kod"] == "plan_degisti"
    y = istemci.post("/api/bolgeleme/uygula", headers=yonetici, json={"n": 12, "plan_ref": p["plan_ref"]})
    assert y.status_code == 400


def test_uygulama_yarida_kalirsa_hicbir_sey_degismez(istemci, yonetici, conn, monkeypatch):
    once_atama, once_satisci = _atama(conn), _satiscilar(conn)
    p = _onizle(istemci, yonetici, 14)

    def patla(_conn):
        raise RuntimeError("disk dolu (deneme)")

    monkeypatch.setattr(bolgeleme.db, "bina_surumu_arttir", patla)
    # Test istemcisi sunucu hatasını yükseltir (gerçek sunucuda 500 + Türkçe mesaj döner)
    with pytest.raises(RuntimeError):
        istemci.post("/api/bolgeleme/uygula", headers=yonetici, json={"n": 14, "plan_ref": p["plan_ref"]})
    assert _atama(conn) == once_atama
    assert _satiscilar(conn) == once_satisci
    assert conn.execute("SELECT COUNT(*) FROM bolge_plani").fetchone()[0] == 0


def test_14ten_8e_inince_satisci_bolgesiz_kalir_onayla_pasif_olur(istemci, yonetici, conn):
    p14 = _onizle(istemci, yonetici, 14)
    u = istemci.post("/api/bolgeleme/uygula", headers=yonetici,
                     json={"n": 14, "plan_ref": p14["plan_ref"]}).json()
    yer_tutucular = {h["id"] for h in u["yeni_satiscilar"]}

    p8 = _onizle(istemci, yonetici, 8)
    bolgesiz = {s["id"] for s in p8["fark"]["bolgesiz_kalacak_satiscilar"]}
    assert len(bolgesiz) == 6
    # Onaysız: bölgesiz (0) kalırlar ama hesapları açık
    y = istemci.post("/api/bolgeleme/uygula", headers=yonetici, json={"n": 8, "plan_ref": p8["plan_ref"]})
    assert y.status_code == 200, y.text
    assert {s["id"] for s in y.json()["bolgesiz_kalan"]} == bolgesiz
    for kid in bolgesiz:
        bolge, aktif = conn.execute("SELECT bolge, aktif FROM kullanici WHERE id=?", (kid,)).fetchone()
        assert bolge == 0 and aktif == 1
    assert set(_atama(conn).values()) == set(range(1, 9))
    # 8'lik plan bugünkü bölgelerle aynı olduğu için asıl 8 satışçı bölgesinde kalır;
    # bölgesiz kalanlar tam olarak 9-14 için açılmış yer tutuculardır.
    assert bolgesiz == yer_tutucular

    # 8 → 14 → 8 → 14 onaylı: bölgesi kalmayanlar pasife alınır, silinmez
    istemci.post("/api/bolgeleme/geri-al", headers=yonetici)
    p8 = _onizle(istemci, yonetici, 8)
    y = istemci.post("/api/bolgeleme/uygula", headers=yonetici,
                     json={"n": 8, "plan_ref": p8["plan_ref"], "pasiflestir": True})
    assert y.status_code == 200
    assert len(y.json()["pasife_alinan"]) == 6
    assert conn.execute("SELECT COUNT(*) FROM kullanici").fetchone()[0] == 9 + 6


def test_bolgesiz_satisci_sehri_goremez(istemci, basliklar, yonetici, conn):
    kid = conn.execute("SELECT id FROM kullanici WHERE telefon=?", (SATISCI_TEL[3],)).fetchone()[0]
    h = basliklar(SATISCI_TEL[3])
    conn.execute("UPDATE kullanici SET bolge=0 WHERE id=?", (kid,))
    conn.commit()
    liste = istemci.get("/api/bina?limit=5", headers=h).json()
    assert liste["toplam"] == 0
    assert istemci.get("/api/harita", headers=h).json()["adet"] == 0


def test_bolgesi_degisen_binaya_listedeki_satisci_ziyaret_yazabilir(istemci, satisci1, conn):
    """Plan gün içinde uygulanırsa çevrimdışı kuyruk 'başka bölge' diye takılmasın."""
    liste = istemci.post("/api/gorev/olustur", headers=satisci1, json={"adet": 3}).json()
    hedef = liste["binalar"][0]["bina_serial"]
    conn.execute("UPDATE bina SET bolge=5 WHERE bina_serial=?", (hedef,))
    conn.commit()
    y = istemci.post("/api/ziyaret", headers=satisci1,
                     json={"offline_id": "plan-kuyruk-1", "bina_serial": hedef, "sonuc": "evde_yok"})
    assert y.status_code == 200, y.text
    assert istemci.get(f"/api/bina/{hedef}", headers=satisci1).status_code == 200
    # Listede OLMAYAN başka bölge binası hâlâ yasak
    yabanci = conn.execute("SELECT bina_serial FROM bina WHERE bolge=6 LIMIT 1").fetchone()[0]
    y = istemci.post("/api/ziyaret", headers=satisci1,
                     json={"offline_id": "plan-kuyruk-2", "bina_serial": yabanci, "sonuc": "evde_yok"})
    assert y.status_code == 403


# ============================================================ arka plan hesabı ve Excel
def test_hazir_plan_yoksa_arka_planda_hesaplanir(istemci, yonetici):
    y = istemci.get("/api/bolgeleme/onizleme", headers=yonetici, params={"n": 3, "hesapla": True})
    assert y.status_code == 202, y.text
    is_ = y.json()["is"]
    son = None
    for _ in range(240):
        son = istemci.get(f"/api/bolgeleme/is/{is_['is_id']}", headers=yonetici).json()
        if son["durum"] in ("bitti", "hata"):
            break
        assert 0 <= son["ilerleme"] <= 1
        time.sleep(0.5)
    assert son["durum"] == "bitti", son
    p = _onizle(istemci, yonetici, 3)
    assert p["kaynak"] == "hesap" and len(p["bolgeler"]) == 3
    assert abs(p["denge"]["sapma_maks"]) < 0.02
    assert istemci.get("/api/bolgeleme/is/yok", headers=yonetici).status_code == 404


def test_excel_etkin_plan_icin_uretilir_ve_onbellekten_verilir(istemci, yonetici):
    t0 = time.time()
    y = istemci.get("/api/bolgeleme/excel", headers=yonetici)
    assert y.status_code == 200, y.text[:300]
    assert "Bursa_8_Satisci_Bolgeleme.xlsx" in y.headers.get("content-disposition", "")
    arsiv = zipfile.ZipFile(BytesIO(y.content))
    assert any(ad.startswith("xl/worksheets/") for ad in arsiv.namelist())
    ilk = time.time() - t0
    t1 = time.time()
    assert istemci.get("/api/bolgeleme/excel", headers=yonetici).status_code == 200
    assert time.time() - t1 < max(ilk / 3, 2.0)       # ikinci istek önbellekten
    # Personel ataması satışçı adlarıyla dolu gelir
    import openpyxl

    wb = openpyxl.load_workbook(BytesIO(y.content), read_only=True)
    ws = wb["PERSONEL_ATAMA"]
    adlar = [ws[f"H{r}"].value for r in range(10, 18)]
    assert all(adlar), adlar
