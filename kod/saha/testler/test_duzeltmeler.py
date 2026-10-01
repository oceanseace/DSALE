"""Denetimde çıkan hataların regresyon testleri.

Buradaki her test, üç bağımsız denetçinin raporladığı GERÇEK bir kusuru bir
daha çıkmayacak şekilde çiviler. Test adı bulgunun ne olduğunu söyler.
"""
from __future__ import annotations

import datetime as dt

from saha import ayarlar, rota

from .conftest import PIN, SATISCI_TEL, YONETICI_TEL


def _gorev(istemci, basliklar, adet=5):
    return istemci.post("/api/gorev/olustur", headers=basliklar, json={"adet": adet}).json()


# ============================================================ zaman dilimi
def test_uygulamanin_utc_damgasi_uc_saat_geriye_yazilmaz(istemci, satisci1, conn):
    """Uygulama ``new Date().toISOString()`` ile UTC gönderiyor.

    Sunucu eskiden "Z"yi kırpıp Türkiye saati sanıyordu: her ziyaret 3 saat
    geriye yazılıyor, gece 00:00-03:00 arası kayıtlar DÜNE düşüyordu.
    """
    veri = _gorev(istemci, satisci1)
    hedef = veri["binalar"][0]["bina_serial"]
    utc = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    yanit = istemci.post("/api/ziyaret", headers=satisci1, json={
        "offline_id": "tz-0001", "bina_serial": hedef, "sonuc": "ilgilenmedi",
        "zaman": utc.isoformat().replace("+00:00", "Z"),
    })
    assert yanit.status_code == 200, yanit.text
    kayit = conn.execute("SELECT zaman, kayit_zamani FROM ziyaret WHERE offline_id='tz-0001'").fetchone()
    fark = abs(
        dt.datetime.fromisoformat(kayit["zaman"]) - dt.datetime.fromisoformat(kayit["kayit_zamani"])
    ).total_seconds()
    assert fark < 90, f"zaman {kayit['zaman']} · kayıt {kayit['kayit_zamani']}"
    assert kayit["zaman"][:10] == ayarlar.bugun().isoformat()


def test_utc_damgali_yeni_ziyaret_bina_durumunu_gunceller(istemci, satisci1, conn):
    """3 saat geri yazılan kayıt "daha eski" görünüp durumu güncellemiyordu."""
    veri = _gorev(istemci, satisci1)
    hedef = veri["binalar"][0]["bina_serial"]
    istemci.post("/api/ziyaret", headers=satisci1, json={
        "offline_id": "tz-a", "bina_serial": hedef, "sonuc": "evde_yok"})
    utc = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    istemci.post("/api/ziyaret", headers=satisci1, json={
        "offline_id": "tz-b", "bina_serial": hedef, "sonuc": "satis", "satis_adedi": 1,
        "zaman": utc.isoformat().replace("+00:00", "Z")})
    d = conn.execute("SELECT * FROM bina_durum WHERE bina_serial=?", (hedef,)).fetchone()
    assert d["son_sonuc"] == "satis" and d["durum"] == "ziyaret_edildi"
    assert d["toplam_satis"] == 1


def test_ileri_tarihli_kayit_binayi_havuzdan_dusuremez(istemci, satisci1, conn):
    """2031 damgalı tek bir 'girilemedi' binayı kalıcı olarak iş dışı bırakıyordu."""
    veri = _gorev(istemci, satisci1)
    hedef = veri["binalar"][0]["bina_serial"]
    istemci.post("/api/ziyaret", headers=satisci1, json={
        "offline_id": "gelecek-1", "bina_serial": hedef, "sonuc": "girilemedi",
        "zaman": "2031-01-01 08:00:00"})
    kayit = conn.execute("SELECT zaman FROM ziyaret WHERE offline_id='gelecek-1'").fetchone()
    assert kayit["zaman"][:4] != "2031"
    assert kayit["zaman"][:10] == ayarlar.bugun().isoformat()


# ============================================================ ziyaret düzeltme
def test_yanlis_islenen_ziyaret_iptal_edilebilir(istemci, satisci1, conn):
    """Sahada en sık yapılan hata (yanlış düğme) geri alınabilmeli."""
    veri = _gorev(istemci, satisci1)
    hedef = veri["binalar"][0]["bina_serial"]
    yanit = istemci.post("/api/ziyaret", headers=satisci1, json={
        "offline_id": "iptal-1", "bina_serial": hedef, "sonuc": "satis", "satis_adedi": 3})
    zid = yanit.json()["ziyaret_id"]
    assert conn.execute(
        "SELECT toplam_satis FROM bina_durum WHERE bina_serial=?", (hedef,)
    ).fetchone()[0] == 3

    geri = istemci.post(f"/api/ziyaret/{zid}/iptal", headers=satisci1, json={"neden": "yanlış bina"})
    assert geri.status_code == 200, geri.text
    d = conn.execute("SELECT * FROM bina_durum WHERE bina_serial=?", (hedef,)).fetchone()
    assert d["toplam_satis"] == 0 and d["ziyaret_sayisi"] == 0
    assert d["durum"] == "bekliyor" and d["son_ziyaret"] is None


def test_duzeltme_eski_kaydi_sayaclardan_duser(istemci, satisci1, conn):
    """"Evde yok" yerine "Satış" işlendiğinde iki kayıt da sayılmamalı."""
    veri = _gorev(istemci, satisci1)
    hedef = veri["binalar"][0]["bina_serial"]
    istemci.post("/api/ziyaret", headers=satisci1, json={
        "offline_id": "duz-1", "bina_serial": hedef, "sonuc": "evde_yok"})
    yanit = istemci.post("/api/ziyaret", headers=satisci1, json={
        "offline_id": "duz-2", "bina_serial": hedef, "sonuc": "satis", "satis_adedi": 2,
        "duzeltilen_offline_id": "duz-1"})
    assert yanit.status_code == 200, yanit.text
    assert yanit.json()["duzeltildi"] is True
    d = conn.execute("SELECT * FROM bina_durum WHERE bina_serial=?", (hedef,)).fetchone()
    assert d["ziyaret_sayisi"] == 1 and d["toplam_satis"] == 2 and d["son_sonuc"] == "satis"

    gun = istemci.get("/api/ozet/gun", headers={"Authorization": satisci1["Authorization"]})
    # satışçı gün özetini göremez; sayıyı doğrudan tablodan doğrulayalım
    assert gun.status_code == 403
    gecerli = conn.execute(
        "SELECT COUNT(*) FROM ziyaret WHERE bina_serial=? AND iptal=0", (hedef,)
    ).fetchone()[0]
    assert gecerli == 1


def test_baskasinin_kaydi_iptal_edilemez(istemci, satisci1, satisci2, conn):
    veri = _gorev(istemci, satisci1)
    hedef = veri["binalar"][0]["bina_serial"]
    zid = istemci.post("/api/ziyaret", headers=satisci1, json={
        "offline_id": "iptal-yetki", "bina_serial": hedef, "sonuc": "satis", "satis_adedi": 1,
    }).json()["ziyaret_id"]
    assert istemci.post(f"/api/ziyaret/{zid}/iptal", headers=satisci2).status_code == 403


def test_satis_adedi_bina_kapasitesini_asamaz(istemci, satisci1, conn):
    """Kayan bir parmak 500 satış yazıp bütün kapsamayı bozmasın."""
    veri = _gorev(istemci, satisci1)
    hedef = veri["binalar"][0]["bina_serial"]
    yanit = istemci.post("/api/ziyaret", headers=satisci1, json={
        "offline_id": "cok-satis", "bina_serial": hedef, "sonuc": "satis", "satis_adedi": 500})
    assert yanit.status_code == 400
    assert yanit.json()["kod"] == "satis_adedi_yuksek"


# ============================================================ rota / kapsama
def test_firsati_sifir_bina_da_rotaya_girebilir(conn):
    """666 bina (firsat=0) hiçbir rotaya giremiyordu; kapsama %96,6'da takılıyordu."""
    sifirlar = [r[0] for r in conn.execute(
        "SELECT bina_serial FROM bina WHERE bolge=1 AND firsat<=0").fetchall()]
    assert sifirlar, "bölge 1'de fırsatı sıfır bina yok — fikstür değişmiş"
    # Bölgedeki fırsatlı binaların hepsi taze ziyaret edilmiş olsun.
    conn.execute(
        "UPDATE bina_durum SET durum='ziyaret_edildi', son_ziyaret=?, son_sonuc='ilgilenmedi' "
        "WHERE bina_serial IN (SELECT bina_serial FROM bina WHERE bolge=1 AND firsat>0)",
        (ayarlar.zaman_metni(),),
    )
    conn.commit()
    r = rota.gunluk_rota(conn, 1, None, 25)
    assert r, "fırsatı sıfır binalar için rota kurulmadı"
    assert all(b["firsat"] == 0 for b in r)


def test_dokunulmamis_bina_tekrar_ziyaretten_once_gelir(conn):
    """Sistemin ana vaadi: bölge bitmeden aynı binaya ikinci kez gidilmez."""
    eski = (ayarlar.bugun() - dt.timedelta(days=60)).isoformat() + " 10:00:00"
    seriler = [r[0] for r in conn.execute(
        "SELECT bina_serial FROM bina WHERE bolge=2 ORDER BY firsat DESC LIMIT 40").fetchall()]
    isaret = ",".join("?" * len(seriler))
    conn.execute(
        f"UPDATE bina_durum SET durum='ziyaret_edildi', son_ziyaret=?, son_sonuc='ilgilenmedi' "
        f"WHERE bina_serial IN ({isaret})", (eski, *seriler))
    conn.commit()
    adaylar = rota.adaylari_getir(conn, 2, en_az=25)
    assert all(a["sinif"] <= 1 for a in adaylar)
    assert not any(a["bina_serial"] in set(seriler) for a in adaylar)


def test_gunluk_tur_bir_gunde_gezilebilir_uzunlukta(conn):
    """Öncelikte yakınlık terimi yokken 8. bölge turu 78 km çıkıyordu."""
    for bolge in range(1, 9):
        r = rota.gunluk_rota(conn, bolge, None, 25)
        ic_km = sum(b["mesafe_m"] for b in r[1:]) / 1000
        assert ic_km < 20, f"bölge {bolge}: tur içi {ic_km:.1f} km"


def test_ayni_bina_iki_satisciya_atanamaz(istemci, yonetici, basliklar, conn):
    """`or adaylar` geri dönüşü filtreyi iptal edip aynı kapıyı iki kişiye veriyordu."""
    kid = conn.execute(
        "SELECT id FROM kullanici WHERE telefon=?", (SATISCI_TEL[6],)).fetchone()["id"]
    seriler = [r[0] for r in conn.execute(
        "SELECT b.bina_serial FROM bina b JOIN bina_durum d USING(bina_serial) "
        "WHERE b.bolge=6 AND d.durum='bekliyor' ORDER BY b.firsat DESC LIMIT 4").fetchall()]
    ilk = istemci.post("/api/gorev/ata", headers=yonetici,
                       json={"kullanici_id": kid, "bina_serial": seriler})
    assert ilk.status_code == 200, ilk.text

    ikinci_kid = conn.execute(
        "INSERT INTO kullanici (ad, telefon, pin_hash, davet_kodu, rol, bolge, aktif, olusturma) "
        "VALUES ('İkinci Satışçı','5550009999',NULL,'123456','satisci',6,1,?)",
        (ayarlar.zaman_metni(),)).lastrowid
    conn.commit()
    ikinci = istemci.post("/api/gorev/ata", headers=yonetici,
                          json={"kullanici_id": ikinci_kid, "bina_serial": seriler})
    assert ikinci.status_code == 400
    assert ikinci.json()["kod"] == "bina_yok"


def test_kapsama_mahalle_kirilimi_ilceyi_ayirir(istemci, yonetici):
    """Bursa'da "Yeni" mahallesi dört ayrı ilçede var; tek satırda toplanmamalı."""
    veri = istemci.get("/api/ozet/kapsama?kirilim=mahalle", headers=yonetici).json()
    adlar = [s["ad"] for s in veri["satirlar"]]
    assert len(adlar) == len(set(adlar))
    yeniler = [s for s in veri["satirlar"] if s["mahalle"] == "Yeni"]
    assert len(yeniler) > 1, "aynı adlı mahalleler hâlâ tek satırda"
    assert all(s["ilce"] for s in yeniler)


def test_dunun_raporu_bugunku_ziyaretle_degismez(istemci, yonetici, basliklar, conn):
    """gorev_bina kapatılırken tarih süzgeci yoktu: dünün "kalan"ı geriye dönük düşüyordu."""
    dun = (ayarlar.bugun() - dt.timedelta(days=1)).isoformat()
    kid = conn.execute(
        "SELECT id FROM kullanici WHERE telefon=?", (SATISCI_TEL[5],)).fetchone()["id"]
    seriler = [r[0] for r in conn.execute(
        "SELECT b.bina_serial FROM bina b JOIN bina_durum d USING(bina_serial) "
        "WHERE b.bolge=5 AND d.durum='bekliyor' ORDER BY b.firsat DESC LIMIT 4").fetchall()]
    istemci.post("/api/gorev/ata", headers=yonetici,
                 json={"kullanici_id": kid, "tarih": dun, "bina_serial": seriler})
    once = istemci.get(f"/api/ozet/gun?tarih={dun}", headers=yonetici).json()
    dun_kalan = next(s for s in once["satiscilar"] if s["kullanici_id"] == kid)["kalan"]
    assert dun_kalan == len(seriler)

    s5 = basliklar(SATISCI_TEL[5], "4917")
    istemci.post("/api/ziyaret", headers=s5, json={
        "offline_id": "dun-bugun", "bina_serial": seriler[0], "sonuc": "ilgilenmedi"})

    sonra = istemci.get(f"/api/ozet/gun?tarih={dun}", headers=yonetici).json()
    assert next(s for s in sonra["satiscilar"] if s["kullanici_id"] == kid)["kalan"] == dun_kalan


# ============================================================ güvenlik
def test_yinelenen_kayit_baska_kullanicinin_binasini_sizdirmaz(istemci, satisci1, satisci2, conn):
    """offline_id küresel tekildi: çakışmada gerçek ziyaret yutulup seri sızıyordu."""
    v1 = _gorev(istemci, satisci1)
    v2 = _gorev(istemci, satisci2)
    istemci.post("/api/ziyaret", headers=satisci1, json={
        "offline_id": "ayni-kimlik", "bina_serial": v1["binalar"][0]["bina_serial"],
        "sonuc": "ilgilenmedi"})
    yanit = istemci.post("/api/ziyaret", headers=satisci2, json={
        "offline_id": "ayni-kimlik", "bina_serial": v2["binalar"][0]["bina_serial"],
        "sonuc": "satis", "satis_adedi": 1})
    assert yanit.status_code == 200, yanit.text
    assert yanit.json()["yinelenen"] is False
    assert yanit.json()["bina_serial"] == v2["binalar"][0]["bina_serial"]


def test_yinelenen_yanit_durum_etiketi_dondurur(istemci, satisci1):
    veri = _gorev(istemci, satisci1)
    hedef = veri["binalar"][0]["bina_serial"]
    govde = {"offline_id": "yin-1", "bina_serial": hedef, "sonuc": "ilgilenmedi"}
    istemci.post("/api/ziyaret", headers=satisci1, json=govde)
    ikinci = istemci.post("/api/ziyaret", headers=satisci1, json=govde).json()
    assert ikinci["yinelenen"] is True
    assert ikinci["durum"] and ikinci["durum_etiket"]


def test_hesap_pasife_alininca_eski_jeton_duser(istemci, satisci1, yonetici, conn):
    """Pasife al → tekrar aktif et, eski jeton yeniden geçerli oluyordu."""
    assert istemci.get("/api/ben", headers=satisci1).status_code == 200
    k = conn.execute("SELECT * FROM kullanici WHERE telefon=?", (SATISCI_TEL[1],)).fetchone()
    istemci.post("/api/kullanici", headers=yonetici, json={
        "id": k["id"], "ad": k["ad"], "telefon": k["telefon"], "rol": "satisci",
        "bolge": k["bolge"], "aktif": False})
    assert istemci.get("/api/ben", headers=satisci1).status_code == 401
    istemci.post("/api/kullanici", headers=yonetici, json={
        "id": k["id"], "ad": k["ad"], "telefon": k["telefon"], "rol": "satisci",
        "bolge": k["bolge"], "aktif": True})
    assert istemci.get("/api/ben", headers=satisci1).status_code == 401


def test_swagger_ve_openapi_kapali(istemci):
    """İç API yüzeyi ağdaki herkese açık olmamalı; Swagger CDN'den dosya çekiyordu."""
    assert istemci.get("/api/belge").status_code in (404, 503)
    assert istemci.get("/api/openapi.json").status_code in (404, 503)


def test_guvenlik_basliklari_var(istemci):
    yanit = istemci.get("/api/saglik")
    for baslik in ("Content-Security-Policy", "X-Frame-Options", "X-Content-Type-Options",
                   "Referrer-Policy"):
        assert baslik in yanit.headers, baslik
    assert "no-store" in yanit.headers.get("Cache-Control", "")


def test_saglik_yazma_denemesi_yapar(istemci):
    veri = istemci.get("/api/saglik").json()
    assert veri["yazilabilir"] is True
    assert veri["ok"] is True
    assert veri["etiketler"]["sonuc"]["girilemedi"]


# ============================================================ ölçü tanımları
def test_donusum_her_ekranda_ayni_tanim(istemci, satisci1, yonetici):
    """Satışçıda "abonelik/bina", yöneticide "satış/ziyaret" iki farklı sayı veriyordu."""
    veri = _gorev(istemci, satisci1)
    for i, b in enumerate(veri["binalar"][:3]):
        istemci.post("/api/ziyaret", headers=satisci1, json={
            "offline_id": f"don-{i}", "bina_serial": b["bina_serial"],
            "sonuc": "satis" if i == 0 else "ilgilenmedi",
            "satis_adedi": 3 if i == 0 else 0})
    ben = istemci.get("/api/ben", headers=satisci1).json()
    gun = istemci.get("/api/ozet/gun", headers=yonetici).json()
    satir = next(s for s in gun["satiscilar"] if s["bolge"] == 1)
    assert ben["bugun"]["donusum"] == satir["donusum"]
    assert ben["bugun"]["satis_bina"] == satir["satis"] == 1
    assert ben["bugun"]["satis"] == satir["satis_adedi"] == 3


def test_penetrasyon_olculemiyorsa_veri_yok_der(istemci, yonetici, conn):
    """res_hp=0 olan 165 binada kart "%0 doluluk, 14 daire" diyordu — kendi
    içinde çelişen bir bilgi. Artık daire sayısı tabana girer; hiçbir taban
    yoksa yüzde değil "veri yok" (None) döner. 303 binada aktif_res > res_hp
    olduğu için oran %100'ü de aşamamalı."""
    olculebilir = conn.execute(
        "SELECT bina_serial FROM bina WHERE res_hp=0 AND daire>0 LIMIT 1").fetchone()
    if olculebilir:
        veri = istemci.get(f"/api/bina/{olculebilir[0]}", headers=yonetici).json()
        oran = veri["bina"]["penetrasyon"]
        assert oran is not None and 0.0 <= oran <= 1.0

    yok = conn.execute(
        "SELECT bina_serial FROM bina WHERE res_hp=0 AND (daire IS NULL OR daire=0) LIMIT 1"
    ).fetchone()
    if yok:
        veri = istemci.get(f"/api/bina/{yok[0]}", headers=yonetici).json()
        assert veri["bina"]["penetrasyon"] is None

    asan = conn.execute(
        "SELECT bina_serial FROM bina WHERE res_hp>0 AND aktif_res>res_hp LIMIT 1").fetchone()
    if asan:
        veri = istemci.get(f"/api/bina/{asan[0]}", headers=yonetici).json()
        assert veri["bina"]["penetrasyon"] <= 1.0


def test_uzun_tur_uyarisi_alanlari_var(istemci, satisci1):
    veri = _gorev(istemci, satisci1, 25)
    assert "uyari" in veri
    bugun = istemci.get("/api/gorev/bugun", headers=satisci1).json()
    assert "uyari" in bugun


# ============================================================ toplu senkron
def test_toplu_senkron_kabul_edilenleri_tek_tek_bildirir(istemci, satisci1):
    """Kuyruk yalnız sunucunun KABUL ETTİĞİ kayıtları silebilmeli.

    Eskiden yanıt sadece sayı döndürüyordu, uygulama da kuyruğun tamamını
    siliyordu: sunucunun reddettiği kayıt (ör. yönetici gün içinde bölgeyi
    değiştirdiyse) sessizce ve kalıcı olarak kayboluyordu.
    """
    veri = _gorev(istemci, satisci1)
    iyi = veri["binalar"][0]["bina_serial"]
    baska_bolge = istemci.get("/api/bina?bolge=1", headers=satisci1)  # kendi bölgesi
    assert baska_bolge.status_code == 200

    yanit = istemci.post("/api/ziyaret/toplu", headers=satisci1, json=[
        {"offline_id": "toplu-iyi", "bina_serial": iyi, "sonuc": "ilgilenmedi"},
        {"offline_id": "toplu-kotu-sonuc", "bina_serial": iyi, "sonuc": "olmayan_sonuc"},
        {"offline_id": "toplu-kotu-bina", "bina_serial": "BN-YOK-0000", "sonuc": "satis"},
    ])
    assert yanit.status_code == 200, yanit.text
    govde = yanit.json()

    assert govde["kabul"] == ["toplu-iyi"]
    reddedilen = {h["offline_id"] for h in govde["hatali"]}
    assert reddedilen == {"toplu-kotu-sonuc", "toplu-kotu-bina"}
    # Reddedilen hiçbir offline_id kabul listesine sızmamalı.
    assert not (reddedilen & set(govde["kabul"]))
    assert all(h.get("hata") and h.get("kod") for h in govde["hatali"])


def test_toplu_senkron_yinelenen_kaydi_kabul_sayar(istemci, satisci1):
    """Yeniden gönderilen kayıt "zaten alındı"dır: kuyrukta tutulmamalı."""
    veri = _gorev(istemci, satisci1)
    hedef = veri["binalar"][0]["bina_serial"]
    govde = [{"offline_id": "toplu-tekrar", "bina_serial": hedef, "sonuc": "evde_yok"}]
    istemci.post("/api/ziyaret/toplu", headers=satisci1, json=govde)
    ikinci = istemci.post("/api/ziyaret/toplu", headers=satisci1, json=govde).json()
    assert ikinci["yinelenen"] == 1 and ikinci["kaydedilen"] == 0
    assert ikinci["kabul"] == ["toplu-tekrar"]
    assert ikinci["hatali"] == []


# ============================================================ cihaz çıkışı
def test_cihaz_cikisi_jetonu_dusurur_pini_degistirmez(istemci, satisci1, yonetici, conn):
    """Telefon kaybolduğunda: kayıp cihaz düşer, kişi kendi PIN'iyle girer."""
    assert istemci.get("/api/ben", headers=satisci1).status_code == 200
    kid = conn.execute("SELECT id FROM kullanici WHERE telefon=?", (SATISCI_TEL[1],)).fetchone()["id"]

    yanit = istemci.post(f"/api/kullanici/{kid}/cihaz-cikis", headers=yonetici)
    assert yanit.status_code == 200, yanit.text
    assert yanit.json()["pin_degismedi"] is True

    assert istemci.get("/api/ben", headers=satisci1).status_code == 401
    # PIN duruyor: kişi yeni telefonundan davet kodu beklemeden girebilir.
    yeni = istemci.post("/api/giris", json={"telefon": SATISCI_TEL[1], "pin": PIN})
    assert yeni.status_code == 200 and yeni.json().get("token")


def test_cihaz_cikisini_satisci_yapamaz(istemci, satisci1, conn):
    kid = conn.execute("SELECT id FROM kullanici WHERE telefon=?", (SATISCI_TEL[2],)).fetchone()["id"]
    assert istemci.post(f"/api/kullanici/{kid}/cihaz-cikis", headers=satisci1).status_code == 403


def test_iptal_edilen_ziyaret_gunun_listesini_de_acar(istemci, satisci1, conn):
    """İptal sonrası bina günün listesinde yeşil tikli kalmamalı.

    `bina_durum` "bekliyor" derken `gorev_bina` "tamam" kalıyordu: satışçı
    yanlış kaydı geri alıyor ama binayı bugün yeniden gezemiyordu.
    """
    veri = _gorev(istemci, satisci1)
    hedef = veri["binalar"][0]["bina_serial"]
    once = veri["ozet"]["kalan"]

    zid = istemci.post("/api/ziyaret", headers=satisci1, json={
        "offline_id": "iptal-liste", "bina_serial": hedef, "sonuc": "satis", "satis_adedi": 1,
    }).json()["ziyaret_id"]
    assert istemci.get("/api/gorev/bugun", headers=satisci1).json()["ozet"]["kalan"] == once - 1

    geri = istemci.post(f"/api/ziyaret/{zid}/iptal", headers=satisci1)
    assert geri.status_code == 200, geri.text
    assert geri.json()["ozet"]["kalan"] == once

    bugun = istemci.get("/api/gorev/bugun", headers=satisci1).json()
    satir = next(b for b in bugun["binalar"] if b["bina_serial"] == hedef)
    assert satir["gorev_durum"] == "bekliyor"
    assert satir["durum"] == "bekliyor"


def test_iptal_ayni_binanin_diger_ziyaretini_silmez(istemci, satisci1, conn):
    """Aynı binada iki kayıt varsa birini iptal etmek listeyi açmamalı."""
    veri = _gorev(istemci, satisci1)
    hedef = veri["binalar"][0]["bina_serial"]
    ilk = istemci.post("/api/ziyaret", headers=satisci1, json={
        "offline_id": "iki-a", "bina_serial": hedef, "sonuc": "evde_yok"}).json()["ziyaret_id"]
    istemci.post("/api/ziyaret", headers=satisci1, json={
        "offline_id": "iki-b", "bina_serial": hedef, "sonuc": "satis", "satis_adedi": 1})

    istemci.post(f"/api/ziyaret/{ilk}/iptal", headers=satisci1)
    bugun = istemci.get("/api/gorev/bugun", headers=satisci1).json()
    satir = next(b for b in bugun["binalar"] if b["bina_serial"] == hedef)
    assert satir["gorev_durum"] == "tamam"      # hâlâ geçerli bir ziyaret var
