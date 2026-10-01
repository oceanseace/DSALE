"""Uygulama ile sunucu arasındaki sözleşmeyi koruyan testler.

Buradaki her test, uçtan uca denemede GERÇEKTEN çıkmış bir hatayı bir daha
çıkmasın diye bekçiye çevirir. Üçü sahada kayıt kaybettirecek cinstendi:

  1. `cihaz` alanı 80 karakterden uzun gelince sunucu bütün ziyareti 422 ile
     reddediyordu — satışçının kaydı telefonda sonsuza dek kuyrukta kalıyordu.
  2. Bina kartındaki `durum` bina durumunu (`planli`), `gorev_durum` ise görev
     durumunu (`bekliyor`) taşır. Uygulama ikisini karıştırınca günün listesi
     ilk açılışta "25/25 bitti" görünüyordu.
  3. `POST /api/pin` davet kodu ister; uygulama kodu sormazsa hiçbir satışçı
     sisteme ilk girişini yapamaz.
"""
from __future__ import annotations

from .conftest import SATISCI_TEL, YONETICI_TEL, davet_kodu


# ============================================================ ziyaret toleransı
def test_uzun_cihaz_kunyesi_ziyareti_dusurmez(istemci, satisci1, conn):
    """Tarayıcı künyesi uzun diye kayıt kaybolmamalı — kırpılıp kabul edilir."""
    bina = conn.execute(
        "SELECT bina_serial FROM bina WHERE bolge=1 ORDER BY bina_serial LIMIT 1"
    ).fetchone()["bina_serial"]
    uzun = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 " * 3

    yanit = istemci.post(
        "/api/ziyaret",
        json={"offline_id": "uzun-cihaz-1", "bina_serial": bina, "sonuc": "satis",
              "satis_adedi": 1, "cihaz": uzun},
        headers=satisci1,
    )
    assert yanit.status_code == 200, yanit.text
    kayitli = conn.execute(
        "SELECT cihaz FROM ziyaret WHERE offline_id='uzun-cihaz-1'"
    ).fetchone()["cihaz"]
    assert len(kayitli) == 80


def test_daire_serbest_metin_kabul_edilir(istemci, satisci1, conn):
    """Satışçı "3. kat" yazsa bile ziyaret kaydedilir; sayı çıkarılır."""
    binalar = [
        s["bina_serial"]
        for s in conn.execute(
            "SELECT bina_serial FROM bina WHERE bolge=1 ORDER BY bina_serial LIMIT 4"
        ).fetchall()
    ]
    for i, (girdi, beklenen) in enumerate(
        [("3", 3), ("3. kat", 3), ("", 0), ("bilmiyorum", 0)]
    ):
        yanit = istemci.post(
            "/api/ziyaret",
            json={"offline_id": f"daire-{i}", "bina_serial": binalar[i],
                  "sonuc": "ilgilenmedi", "konusulan_daire": girdi},
            headers=satisci1,
        )
        assert yanit.status_code == 200, f"{girdi!r} → {yanit.text}"
        assert conn.execute(
            "SELECT konusulan_daire FROM ziyaret WHERE offline_id=?", (f"daire-{i}",)
        ).fetchone()["konusulan_daire"] == beklenen


def test_uzun_not_kirpilir_reddedilmez(istemci, satisci1, conn):
    bina = conn.execute(
        "SELECT bina_serial FROM bina WHERE bolge=1 ORDER BY bina_serial LIMIT 1"
    ).fetchone()["bina_serial"]
    yanit = istemci.post(
        "/api/ziyaret",
        json={"offline_id": "uzun-not-1", "bina_serial": bina, "sonuc": "randevu",
              "not": "a" * 3000},
        headers=satisci1,
    )
    assert yanit.status_code == 200, yanit.text
    assert len(conn.execute(
        "SELECT notu FROM ziyaret WHERE offline_id='uzun-not-1'"
    ).fetchone()["notu"]) == 1000


# ============================================================ bina kartı
def test_bina_kartinda_iki_durum_ayri_gelir(istemci, satisci1):
    """`durum` binanın hâli, `gorev_durum` bugünün listesindeki hâli."""
    yanit = istemci.post("/api/gorev/olustur", json={"adet": 5}, headers=satisci1)
    assert yanit.status_code == 200, yanit.text
    binalar = yanit.json()["binalar"]
    assert binalar, "liste boş geldi"
    for b in binalar:
        assert b["durum"] == "planli", "listeye giren bina 'planli' olmalı"
        assert b["gorev_durum"] == "bekliyor", "henüz gezilmedi"

    istemci.post(
        "/api/ziyaret",
        json={"offline_id": "durum-ayrimi-1", "bina_serial": binalar[0]["bina_serial"],
              "sonuc": "satis", "satis_adedi": 1},
        headers=satisci1,
    )
    sonra = istemci.get("/api/gorev/bugun", headers=satisci1).json()["binalar"]
    ilk = next(b for b in sonra if b["bina_serial"] == binalar[0]["bina_serial"])
    assert ilk["durum"] == "ziyaret_edildi"
    assert ilk["gorev_durum"] == "tamam"


def test_bina_kartinda_ad_alani_dolu(istemci, satisci1):
    """Uygulama `ad` alanını okuyor; boş gelirse kartta "Bina" yazar."""
    binalar = istemci.post("/api/gorev/olustur", json={"adet": 25}, headers=satisci1).json()["binalar"]
    for b in binalar:
        assert b["ad"], b["bina_serial"]
        assert b["ad"] == b["baslik"]
        assert b["ad"] != "Bina"


# ============================================================ ilk giriş
def test_pin_davet_kodu_olmadan_belirlenemez(istemci):
    yanit = istemci.post("/api/pin", json={"telefon": SATISCI_TEL[3], "pin": "7391"})
    assert yanit.status_code in (401, 422)
    if yanit.status_code == 401:
        assert yanit.json()["kod"] == "kimlik_hatali"


def test_ilk_giris_akisi(istemci, db_yolu):
    """Uygulamanın yaptığı sıra: giriş → pin_belirle → davet kodu → jeton."""
    yanit = istemci.post("/api/giris", json={"telefon": SATISCI_TEL[4], "pin": "1379"})
    assert yanit.status_code == 200
    assert yanit.json().get("pin_belirle") is True

    kod = davet_kodu(db_yolu, SATISCI_TEL[4])
    yanit = istemci.post(
        "/api/pin", json={"telefon": SATISCI_TEL[4], "pin": "1379", "davet_kodu": kod}
    )
    assert yanit.status_code == 200, yanit.text
    assert yanit.json()["token"]


# ============================================================ /api/ben
def test_ben_hafta_ve_bolge_dondurur(istemci, satisci1):
    """"Ben" ekranındaki hafta ve bölge kartları bu alanlara bakıyor."""
    veri = istemci.get("/api/ben", headers=satisci1).json()
    for alan in ("kullanici", "bugun", "hafta", "bolge", "tarih"):
        assert alan in veri, alan
    # "satis" = satışla biten bina, "satis_adedi" = satılan abonelik,
    # "donusum" sunucudan gelir (istemci artık kendi bölmesini yapmıyor).
    assert set(veri["hafta"]) == {"ziyaret", "satis", "satis_adedi", "randevu", "donusum"}
    b = veri["bolge"]
    assert b["toplam"] > 0
    assert b["dokunulan"] + b["kalan"] == b["toplam"]
    assert veri["demo"] is False


# ============================================================ harita
def test_harita_ad_dizisi_ve_onbellek_tazelenir(istemci, satisci1, conn):
    ilk = istemci.get("/api/harita", headers=satisci1).json()
    uzunluk = ilk["adet"]
    for alan in ("serial", "ad", "lat", "lon", "durum", "firsat", "bolge"):
        assert len(ilk[alan]) == uzunluk, alan
    assert all(ilk["ad"]), "boş bina adı var"

    # Aynı yanıt önbellekten gelmeli ama bir ziyaretten sonra tazelenmeli.
    hedef = ilk["serial"][0]
    assert ilk["durum"][0] == "bekliyor"
    istemci.post(
        "/api/ziyaret",
        json={"offline_id": "harita-onbellek-1", "bina_serial": hedef, "sonuc": "satis",
              "satis_adedi": 1},
        headers=satisci1,
    )
    sonra = istemci.get("/api/harita", headers=satisci1).json()
    assert sonra["durum"][0] == "ziyaret_edildi", "harita önbelleği tazelenmedi"
    assert sonra["serial"][0] == hedef


def test_yollar_ucu_geojson_dondurur(istemci, satisci1):
    yanit = istemci.get("/api/yollar", headers=satisci1)
    assert yanit.status_code in (200, 404)
    if yanit.status_code == 200:
        veri = yanit.json()
        assert veri["type"] == "FeatureCollection"
        assert isinstance(veri["features"], list)


def test_bolge_yollari_daha_kucuk(istemci, satisci1, yonetici):
    """Bölge verilince yol ağı o bölgenin kutusuna kırpılır."""
    hepsi = istemci.get("/api/yollar", headers=yonetici)
    if hepsi.status_code != 200:
        return
    bolge = istemci.get("/api/yollar?bolge=1", headers=satisci1)
    assert bolge.status_code == 200
    assert len(bolge.json()["features"]) < len(hepsi.json()["features"])


# ============================================================ PWA servisi
def test_kok_adres_uygulamayi_sunar(istemci):
    """`kod/arayuz/dist` derlenmişse `/` uygulamayı verir, değilse Türkçe uyarı."""
    yanit = istemci.get("/")
    assert yanit.status_code in (200, 503)
    if yanit.status_code == 200:
        assert "text/html" in yanit.headers["content-type"]
    else:
        assert yanit.json()["kod"] == "pwa_yok"


def test_derin_yol_uygulamaya_duser(istemci):
    """"http://<ip>:8080/bugun" yazan biri 404 degil uygulamayi gormeli."""
    yanit = istemci.get("/bugun")
    assert yanit.status_code in (200, 503)
    if yanit.status_code == 200:
        assert "text/html" in yanit.headers["content-type"]
        assert "<div id=" in yanit.text or "<script" in yanit.text


def test_bilinmeyen_api_ucu_json_hata_verir(istemci, yonetici):
    yanit = istemci.get("/api/boyle-bir-sey-yok", headers=yonetici)
    assert yanit.status_code == 404
    assert yanit.json()["kod"] == "bulunamadi"


# ============================================================ gösterim verisi
def test_demo_bayragi_saglikta_gorunur(istemci):
    veri = istemci.get("/api/saglik").json()
    assert veri["demo"] is False, "test veritabanında gösterim verisi olmamalı"


def test_demo_kur_ve_temizle_geri_alir(db_yolu, conn):
    """Gösterim verisi tek komutla kurulur ve tek komutla TAMAMEN silinir."""
    from saha import demo, demo_temizle

    once = conn.execute("SELECT COUNT(*) FROM bina_durum WHERE son_ziyaret IS NOT NULL").fetchone()[0]
    assert once == 0

    demo.kur(gun_sayisi=2, sessiz=True)
    dokunulan = conn.execute(
        "SELECT COUNT(*) FROM bina_durum WHERE son_ziyaret IS NOT NULL"
    ).fetchone()[0]
    assert dokunulan > 0
    assert conn.execute(
        "SELECT COUNT(*) FROM ziyaret WHERE offline_id LIKE 'demo-%'"
    ).fetchone()[0] > 0

    demo_temizle.temizle(sor=False)
    assert conn.execute("SELECT COUNT(*) FROM ziyaret").fetchone()[0] == 0
    assert conn.execute(
        "SELECT COUNT(*) FROM bina_durum WHERE son_ziyaret IS NOT NULL"
    ).fetchone()[0] == 0
    assert conn.execute(
        "SELECT COUNT(*) FROM bina_durum WHERE durum<>'bekliyor'"
    ).fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM gorev").fetchone()[0] == 0


def test_demo_temizle_gercek_ziyareti_korur(istemci, satisci1, db_yolu, conn):
    """Sahadan gelmiş gerçek bir kayıt, gösterim temizliğinde silinmemeli."""
    from saha import demo, demo_temizle

    demo.kur(gun_sayisi=2, sessiz=True)
    bina = conn.execute(
        "SELECT bina_serial FROM bina b JOIN bina_durum d USING(bina_serial) "
        "WHERE b.bolge=1 AND d.son_ziyaret IS NULL LIMIT 1"
    ).fetchone()["bina_serial"]
    yanit = istemci.post(
        "/api/ziyaret",
        json={"offline_id": "gercek-saha-kaydi", "bina_serial": bina, "sonuc": "satis",
              "satis_adedi": 2},
        headers=satisci1,
    )
    assert yanit.status_code == 200, yanit.text

    demo_temizle.temizle(sor=False)
    kalan = conn.execute("SELECT * FROM ziyaret").fetchall()
    assert len(kalan) == 1
    assert kalan[0]["offline_id"] == "gercek-saha-kaydi"
    durum = conn.execute("SELECT * FROM bina_durum WHERE bina_serial=?", (bina,)).fetchone()
    assert durum["durum"] == "ziyaret_edildi"
    assert durum["toplam_satis"] == 2
    assert durum["ziyaret_sayisi"] == 1
