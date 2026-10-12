"""Administrator, unvan kataloğu ve yetkinlikler (v9).

* Administrator yalnız ``TURKCELL_ADMIN_TELEFON`` / turkcell.json telefonudur; her izne sahiptir, kimse kendini
  ya da başkasını Administrator yapamaz, İK onu düzenleyemez/silemez.
* İK (Kişi yönetimi) kişi ekler, unvan ve takım lideri atar; unvan/matris/ek yetkinlik DEĞİŞTİREMEZ.
* Müdür/koordinatör yalnız Pano: iş atamaz, plan yapmaz, teknik ekranı açılmaz.
* v9 göçü her kişinin etkin erişimini korur (tek bilinçli istisna müdürler).
* Yetkinlik-modeli profilleriyle HTTP matrisi: paketin vermediği her uç 403 ``yasak``.

Numaralar uydurmadır (555… / 599…).
"""
from __future__ import annotations


import pytest

from saha import ayarlar, goc, guvenlik, yetki

from .conftest import PIN
from .test_yetki_matrisi import _beklenen, _doldur, _uc_listesi

ADMIN_TEL = "5990000001"


@pytest.fixture
def admin_env(monkeypatch):
    monkeypatch.setenv("TURKCELL_ADMIN_TELEFON", ADMIN_TEL)
    monkeypatch.setenv("TURKCELL_ADMIN_AD", "Deneme Administrator")


def _unvan_id(conn, ad: str) -> int:
    satir = conn.execute("SELECT id FROM unvan WHERE ad_k=?", (yetki.unvan_anahtari(ad),)).fetchone()
    assert satir, ad
    return int(satir["id"])


@pytest.fixture
def yeni_kisi(conn):
    """Yetki modelinde kişi: ``yeni_kisi(unvan='EÇM - Genel Koordinatör', ek=[...], bolge=None)`` → (id, başlık)."""
    sayac = iter(range(1, 10_000))

    def _yeni(unvan: str | None = None, ek: list[str] | None = None, bolge: int | None = None,
              telefon: str | None = None, takim_lideri: int = 0) -> tuple[int, dict]:
        n = next(sayac)
        uid = _unvan_id(conn, unvan) if unvan else None
        kid = conn.execute(
            "INSERT INTO kullanici (ad, telefon, pin_hash, rol, bolge, aktif, olusturma, unvan, unvan_id, "
            "takim_lideri, yetki_modeli) VALUES (?,?,?,?,?,1,?,?,?,?,1)",
            (f"Deneme Kişi {n}", telefon or f"556{n:07d}", guvenlik.pin_hashle(PIN), "satisci", bolge,
             ayarlar.zaman_metni(), unvan, uid, takim_lideri)).lastrowid
        conn.executemany("INSERT INTO kullanici_yetkinlik (kullanici_id, yetkinlik) VALUES (?,?)",
                         [(kid, y) for y in ek or []])
        yetki.gorev_onbellegi_yaz(conn, kid)
        conn.commit()
        satir = dict(conn.execute("SELECT * FROM kullanici WHERE id=?", (kid,)).fetchone())
        return int(kid), {"Authorization": f"Bearer {guvenlik.jeton_uret(satir)}"}

    return _yeni


@pytest.fixture
def admin(admin_env, conn, istemci):
    """Administrator hesabı ilk girişte açılır (davet kodu yalnız günlükte); PIN belirlenip jeton döner."""
    y = istemci.post("/api/giris", json={"telefon": ADMIN_TEL, "pin": ""})
    assert y.status_code == 200 and y.json()["pin_belirle"] is True
    kod = conn.execute("SELECT davet_kodu FROM kullanici WHERE telefon=?", (ADMIN_TEL,)).fetchone()[0]
    y = istemci.post("/api/pin", json={"telefon": ADMIN_TEL, "pin": PIN, "davet_kodu": kod})
    assert y.status_code == 200, y.text
    kid = conn.execute("SELECT id FROM kullanici WHERE telefon=?", (ADMIN_TEL,)).fetchone()[0]
    return int(kid), {"Authorization": f"Bearer {y.json()['token']}"}


# ============================================================ katalog
def test_katalog_her_izni_kapsar_ve_eski_gorevleri_ifade_eder():
    kapsanan = set(yetki.TEMEL_IZINLER) | set(yetki.ADMIN_IZINLERI)
    for y in yetki.YETKINLIKLER.values():
        assert y["ad"] and y["aciklama"]
        assert set(y["izinler"]) <= set(yetki.IZINLER)
        assert not set(y["izinler"]) & yetki.ADMIN_IZINLERI          # yalnız-Administrator izni pakete girmez
        kapsanan |= set(y["izinler"])
    assert kapsanan == set(yetki.IZINLER)
    for gorev in yetki.ROLLER:
        assert yetki.paket_izinleri(yetki.GOREV_PAKETLERI[gorev]) == yetki.eski_izinler([gorev]), gorev
        assert gorev in yetki.gorevler_turet(yetki.GOREV_PAKETLERI[gorev])


def test_unvan_tohumu_listeyi_aynen_alir(conn):
    adlar = [r["ad"] for r in conn.execute("SELECT ad FROM unvan ORDER BY sira")]
    beklenen = [ad for ad, _ in goc.sema_v2.UNVAN_TOHUM]
    assert adlar[:len(beklenen)] == beklenen
    assert len(beklenen) == 16                                   # "EÇM - Finans - Sorumlu" iki kez verilmişti
    mudur = _unvan_id(conn, "EÇM-Fiber-Satış-Müdür")
    assert yetki.unvan_yetkinlikleri(conn, mudur) == ["pano"]


# ============================================================ Administrator
def test_administrator_hesabi_acilir_her_izne_sahip(admin, istemci, conn):
    _kid, baslik = admin
    ben = istemci.get("/api/ben", headers=baslik).json()
    assert ben["administrator"] is True and ben["kullanici"]["administrator"] is True
    assert set(ben["izinler"]) == set(yetki.IZINLER) - {"oturum"}
    assert "yetkinlik.yonet" in ben["izinler"]
    assert [y["kod"] for y in ben["yetkinlikler"]] == list(yetki.YETKINLIKLER)


def test_telefon_ayari_yoksa_kimse_administrator_degil(istemci, yonetici):
    ben = istemci.get("/api/ben", headers=yonetici).json()
    assert ben["administrator"] is False and "yetkinlik.yonet" not in ben["izinler"]
    assert istemci.post("/api/admin/unvanlar", json={"ad": "EÇM - Finans - Takım Lideri"},
                        headers=yonetici).status_code == 403


def test_administrator_unvan_acar_adini_degistirir_matrisi_yazar(admin, istemci, conn, yeni_kisi):
    _kid, baslik = admin
    y = istemci.post("/api/admin/unvanlar", json={"ad": "EÇM - Finans - Takım Lideri", "yetkinlikler": ["pano"]},
                     headers=baslik)
    assert y.status_code == 200, y.text
    uid = y.json()["unvan"]["id"]
    assert istemci.post("/api/admin/unvanlar", json={"ad": "EÇM-Finans-Takım Lideri"},
                        headers=baslik).json()["kod"] == "unvan_var"
    kid, kb = yeni_kisi(unvan="EÇM - Finans - Takım Lideri")
    assert istemci.get("/api/takip/yonetim", headers=kb).status_code != 403
    # Ad değişir, kişi id ile bağlı kalır
    y = istemci.patch(f"/api/admin/unvanlar/{uid}", json={"ad": "EÇM - Finans - Lider"}, headers=baslik)
    assert y.status_code == 200 and y.json()["unvan"]["kisi_sayisi"] == 1
    assert conn.execute("SELECT unvan FROM kullanici WHERE id=?", (kid,)).fetchone()[0] == "EÇM - Finans - Lider"
    # Matris: Pano kaldırılır → erişim düşer
    y = istemci.put("/api/admin/matris", json={"unvanlar": {str(uid): ["ticket_defteri"]}}, headers=baslik)
    assert y.status_code == 200 and y.json()["degisen_unvan"] == 1
    assert istemci.get("/api/takip/yonetim", headers=kb).status_code == 403
    assert istemci.get("/api/ticket", headers=kb).status_code == 200
    # Pasif unvan yeni kişiye atanamaz
    istemci.patch(f"/api/admin/unvanlar/{uid}", json={"aktif": False}, headers=baslik)
    diger, _ = yeni_kisi()
    y = istemci.patch(f"/api/admin/kisiler/{diger}", json={"unvan_id": uid}, headers=baslik)
    assert y.status_code == 400 and y.json()["kod"] == "unvan_pasif"


def test_administrator_ek_yetkinlik_verir(admin, istemci, yeni_kisi):
    _kid, baslik = admin
    kid, kb = yeni_kisi(unvan="EÇM - Finans - Sorumlu")
    assert istemci.get("/api/ticket", headers=kb).status_code == 403
    y = istemci.patch(f"/api/admin/kisiler/{kid}", json={"ek_yetkinlikler": ["ticket_defteri"]}, headers=baslik)
    assert y.status_code == 200, y.text
    assert y.json()["kisi"]["ek_yetkinlikler"] == ["ticket_defteri"]
    # Görev kümesi değişti → eski jeton düşer; yeni girişte izin gelir
    assert istemci.get("/api/ticket", headers=kb).status_code == 401


def test_administrator_duzenlenemez_silinemez(admin, istemci, conn, yeni_kisi):
    admin_id, _ = admin
    _ik, ik = yeni_kisi(unvan="EÇM-Çalışan Deneyimi ve İnsan Kaynakları-Müdür")
    assert istemci.patch(f"/api/admin/kisiler/{admin_id}", json={"takim_lideri": True},
                         headers=ik).json()["kod"] == "administrator_korumali"
    assert istemci.delete(f"/api/kullanici/{admin_id}", headers=ik).json()["kod"] == "administrator_korumali"
    assert istemci.post(f"/api/kullanici/{admin_id}/pin-sifirla", headers=ik).status_code == 403
    assert istemci.post(f"/api/kullanici/{admin_id}/cihaz-cikis", headers=ik).status_code == 403
    y = istemci.post("/api/kullanici", json={"id": admin_id, "ad": "Başka Ad", "telefon": ADMIN_TEL}, headers=ik)
    assert y.status_code == 403 and y.json()["kod"] == "administrator_korumali"


# ============================================================ İK (Kişi yönetimi)
def test_ik_unvan_ve_matrisi_degistiremez_ek_yetkinlik_veremez(admin_env, istemci, conn, yeni_kisi):
    _ik, ik = yeni_kisi(unvan="EÇM-Çalışan Deneyimi ve İnsan Kaynakları-Müdür")
    hedef, _ = yeni_kisi(unvan="EÇM - Finans - Sorumlu")
    mudur = _unvan_id(conn, "EÇM-Fiber-Satış-Müdür")
    assert istemci.get("/api/admin/matris", headers=ik).status_code == 200          # okur
    assert istemci.post("/api/admin/unvanlar", json={"ad": "EÇM - Yeni"}, headers=ik).status_code == 403
    assert istemci.patch(f"/api/admin/unvanlar/{mudur}", json={"ad": "X Y"}, headers=ik).status_code == 403
    assert istemci.put("/api/admin/matris", json={"unvanlar": {str(mudur): ["kisi_yonetimi"]}},
                       headers=ik).status_code == 403
    y = istemci.patch(f"/api/admin/kisiler/{hedef}", json={"ek_yetkinlikler": ["veri_yonetimi"]}, headers=ik)
    assert y.status_code == 403 and y.json()["kod"] == "yetkinlik_admin"
    assert istemci.put("/api/kullanici/rehber/esleme", json={"esleme": []}, headers=ik).status_code == 403
    # Kendi unvanını değiştiremez (yükselme yok)
    destek_tl = _unvan_id(conn, "EÇM-Fiber- Satış Destek - Takım Lideri")
    y = istemci.patch(f"/api/admin/kisiler/{_ik}", json={"unvan_id": destek_tl}, headers=ik)
    assert y.status_code == 409 and y.json()["kod"] == "kendi_rolu"
    # Eski uçla görev değiştirmek de yetkinlik vermektir: yasak
    y = istemci.post("/api/kullanici/gorevler", json={"degisiklikler": [{"id": hedef, "rol": "yonetici"}]},
                     headers=ik)
    assert y.status_code == 403 and y.json()["kod"] == "yetkinlik_admin"


def test_ik_kisi_ekler_unvan_ve_takim_lideri_atar(admin_env, istemci, conn, yeni_kisi):
    _ik, ik = yeni_kisi(unvan="EÇM-Çalışan Deneyimi ve İnsan Kaynakları-Müdür")
    teknik = _unvan_id(conn, "EÇM-Fiber- Teknik - Sorumlu")
    y = istemci.post("/api/kullanici", json={"ad": "Yeni Teknisyen", "telefon": "5990000777", "unvan_id": teknik},
                     headers=ik)
    assert y.status_code == 200, y.text
    kid = y.json()["kullanici"]["id"]
    assert y.json()["kullanici"]["gorevler"] == ["teknik"] and y.json()["davet_kodu"]
    satir = conn.execute("SELECT yetki_modeli, unvan_id FROM kullanici WHERE id=?", (kid,)).fetchone()
    assert tuple(satir) == (1, teknik)
    y = istemci.patch(f"/api/admin/kisiler/{kid}", json={"takim_lideri": True}, headers=ik)
    assert y.status_code == 200 and y.json()["kisi"]["takim_lideri"] is True
    # Görevi unvanın vermediği bir göreve çekmek yasak
    y = istemci.post("/api/kullanici", json={"ad": "Başka", "telefon": "5990000778", "unvan_id": teknik,
                                              "rol": "yonetici"}, headers=ik)
    assert y.status_code == 403
    # Katalogda olmayan unvan metni reddedilir
    y = istemci.post("/api/kullanici", json={"ad": "Üçüncü", "unvan": "Uydurma Unvan"}, headers=ik)
    assert y.status_code == 400 and y.json()["kod"] == "unvan_yok"
    # Kimse Administrator telefonunu alamaz
    y = istemci.post("/api/kullanici", json={"ad": "Taklit", "telefon": ADMIN_TEL}, headers=ik)
    assert y.status_code == 403 and y.json()["kod"] == "administrator_korumali"


# ============================================================ müdür / koordinatör
@pytest.mark.parametrize("unvan", ["EÇM-Fiber-Satış-Müdür", "EÇM-Fiber- Teknik - Müdür", "EÇM - Genel Koordinatör"])
def test_mudur_yalniz_pano(istemci, yeni_kisi, unvan):
    _kid, b = yeni_kisi(unvan=unvan)
    ben = istemci.get("/api/ben", headers=b).json()
    assert [y["kod"] for y in ben["yetkinlikler"]] == ["pano"]
    assert ben["ana_ekran"] == "takip"
    assert istemci.get("/api/takip/yonetim", headers=b).status_code == 200
    for m, yol in (("POST", "/api/isler/000000000/ata"), ("POST", "/api/isler/toplu-ata"),
                   ("POST", "/api/gorev/ata"), ("GET", "/api/islerim"), ("POST", "/api/aktarim"),
                   ("POST", "/api/isler/dagit/uygula"), ("POST", "/api/ziyaret")):
        y = istemci.request(m, yol, headers=b, json={})
        assert y.status_code == 403 and y.json()["kod"] == "yasak", (m, yol, y.status_code)


def test_hizmet_danismani_randevu_verir_atama_yapamaz(istemci, yeni_kisi):
    _kid, b = yeni_kisi(unvan="EÇM-Fiber-Hizmet Danışmanı - Sorumlu")
    assert istemci.post("/api/isler/000000000/randevu", headers=b, json={}).status_code != 403
    assert istemci.post("/api/isler/000000000/ata", headers=b, json={}).status_code == 403


# ============================================================ göç (v9) — erişim korunur
def test_goc_erisimi_korur_mudurleri_daraltir(conn, kisi):
    sade, _ = kisi("satisci", bolge=1)
    op, _ = kisi("operasyon", gorevler=["yonetici"])
    tek, _ = kisi("teknik")
    mudur, _ = kisi("teknik", gorevler=["yonetici"])
    conn.execute("UPDATE kullanici SET unvan='EÇM-Fiber- Teknik - Müdür' WHERE id=?", (mudur,))
    hd, _ = kisi("operasyon")
    conn.execute("UPDATE kullanici SET unvan='EÇM-Fiber-Hizmet Danışmanı - Sorumlu' WHERE id=?", (hd,))
    tl, _ = kisi("satisci", gorevler=["yonetici"], bolge=2)
    conn.execute("UPDATE kullanici SET unvan='EÇM-Fiber- Yeni Müşteri - Takım Lideri', etiket='[\"lider\"]' "
                 "WHERE id=?", (tl,))
    garip, _ = kisi("operasyon")
    conn.execute("UPDATE kullanici SET unvan='EÇM - Uydurma Birim - Uzman' WHERE id=?", (garip,))
    conn.commit()
    once = {i: yetki.erisim(conn, dict(conn.execute("SELECT * FROM kullanici WHERE id=?", (i,)).fetchone()))
            for i in (sade, op, tek, mudur, hd, tl, garip)}
    conn.execute("BEGIN IMMEDIATE")
    goc.unvan_tohumla(conn, ayarlar.zaman_metni())
    sonuc = goc.kisi_yetkinlik_gocu(conn)
    conn.execute("COMMIT")
    farklar = {f["kullanici_id"]: f for f in sonuc["fark"]}
    for i in (sade, tek, hd, tl, garip):
        assert i not in farklar, (i, farklar.get(i))
        sonra = yetki.erisim(conn, dict(conn.execute("SELECT * FROM kullanici WHERE id=?", (i,)).fetchone()))
        assert sonra["yetki_modeli"] and sonra["izinler"] == once[i]["izinler"]
        assert set(sonra["gorevler"]) >= set(once[i]["gorevler"])
    # Müdür: iş/plan/teknik düştü, Pano kaldı; atanabilir teknisyen listesinden çıktı
    f = farklar[mudur]
    assert f["mudur"] and not f["eklenen"]
    assert {"is.ata", "is.saha", "is.yukle", "satis.izle"} <= set(f["dusen"])
    m = yetki.erisim(conn, dict(conn.execute("SELECT * FROM kullanici WHERE id=?", (mudur,)).fetchone()))
    assert {"takip.tam", "takip.oku"} <= m["izinler"] and "teknik" not in m["gorevler"]
    assert "teknik" not in {r[0] for r in conn.execute("SELECT rol FROM kullanici_gorev WHERE kullanici_id=?",
                                                        (mudur,))}
    # Unvansız eski yönetici (Administrator değil): iş/plan/teknik VE kişi/veri yönetimi düşer
    assert farklar[op]["mudur"] and "is.ata" in farklar[op]["dusen"]
    o = yetki.erisim(conn, dict(conn.execute("SELECT * FROM kullanici WHERE id=?", (op,)).fetchone()))
    assert "is.ata" not in o["izinler"]
    assert not ({"kisi_yonetimi", "veri_yonetimi"} | yetki.OPERASYONEL_YETKINLIKLER) & set(o["yetkinlikler"])
    assert conn.execute("SELECT takim_lideri FROM kullanici WHERE id=?", (tl,)).fetchone()[0] == 1
    # Kişide yazılı katalog dışı unvan kataloğa girdi; kişi ona bağlandı
    assert conn.execute("SELECT u.ad FROM kullanici k JOIN unvan u ON u.id=k.unvan_id WHERE k.id=?",
                        (garip,)).fetchone()[0] == "EÇM - Uydurma Birim - Uzman"
    # İdempotent: ikinci kez kimse taşınmaz
    conn.execute("BEGIN IMMEDIATE")
    assert goc.kisi_yetkinlik_gocu(conn)["tasinan"] == 0
    conn.execute("COMMIT")


# ============================================================ HTTP matrisi — yetkinlik profilleri
def test_matris_yetkinlik_profilleri(istemci, yeni_kisi):
    """Her yetkinlik tek başına: paketin vermediği her uç 403 'yasak'. ``yetkinlik.yonet`` hiçbir pakette yok."""
    profiller = {kod: yeni_kisi(ek=[kod], bolge=1 if kod in ("saha_satis", "satis_izleme") else None)
                 for kod in yetki.YETKINLIKLER}
    profiller["bos"] = yeni_kisi()
    hatalar = []
    for m, yol, _r in _uc_listesi():
        beklenen = _beklenen((m, yol))
        if beklenen is None:
            continue
        adres = _doldur(yol)
        for ad, (_kid, baslik) in profiller.items():
            izinler = yetki.paket_izinleri([] if ad == "bos" else [ad])
            if any(e in izinler for e in beklenen):
                continue
            y = istemci.request(m, adres, headers=baslik, json={} if m in ("POST", "PUT", "PATCH") else None)
            if y.status_code != 403 or y.json().get("kod") != "yasak":
                hatalar.append(f"{ad} {m} {yol} → {y.status_code} {y.text[:80]}")
    assert not hatalar, "\n".join(hatalar)
    admin_rotalari = [k for k, v in yetki.ROTA_IZNI.items() if v == "yetkinlik.yonet"]
    # unvan aç, unvan düzenle, matris yaz + BOSS'a yazma genel anahtarı ve tek iş denemesi
    assert sorted(admin_rotalari) == sorted([("POST", "/api/admin/unvanlar"), ("PATCH", "/api/admin/unvanlar/{unvan_id}"),
                                             ("PUT", "/api/admin/matris"), ("PUT", "/api/boss/yazma-anahtari"),
                                             ("POST", "/api/boss/yazma-dene")])
