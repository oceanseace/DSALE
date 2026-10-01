"""EK-12 · Turkcell süreç kuralları ayarla değişen varsayılanlardır (belgeler/TURKCELL_SUREC_BILGISI.md).

Hedef saatleri, öncelik, arama merdiveni + BOSS "Talep Ulaşamama SMS" giden kutusu, ulaşılamadı kapanışı, ATA havuzu,
BTK şikâyet sayacı (iş günü) + TÇS, iptal yasağı, kesintiye duyarlı sevk. Saat dondurulur: 30.09.2026 (Çarşamba) 10:00.
"""
from __future__ import annotations

import datetime as dt
import json

import pytest

from operasyon.testler import yardim as y
from operasyon.v2 import akis, gorunum, kesinti, kurallar
from operasyon.v2.hatalar import V2Hata

NO = "400000001"
BULTEN = ("TCELL SOC - NT ARIZA No: 734512 Durum: Devam Ediyor. ARIZA Başladı 09.40 – BURSA-NİLÜFER GPON KESİNTİSİ "
          "ETKİ: 3 SWITCH – 420 MÜŞTERİ – 12 ŞİKAYET")


def _ayar(conn, anahtar, deger):
    conn.execute("INSERT INTO ayar(anahtar, deger) VALUES(?,?) ON CONFLICT(anahtar) DO UPDATE SET deger=excluded.deger",
                 (anahtar, json.dumps(deger)))
    conn.commit()


def test_hedef_saatleri_ve_serit_rapordan(v2db, conn, saat):
    y.aktar(v2db, [y.satir(1, task="Modem Değişikliği"), y.satir(2, task="Superbox Modem Değişikliği"),
                   y.satir(3, task="TV+ Arıza"), y.satir(4, task="Bağlantı Problemi"),
                   y.satir(5, task="Teknik Servis Ücretlendirme")])
    r = {x["is_no"][-1]: x for x in conn.execute("SELECT is_no, son24, serit, btk_hedef FROM is_emri")}
    assert r["1"]["son24"] == r["2"]["son24"] == "2026-10-07 09:00:00"      # modem değişim SL 7 gün
    assert (r["3"]["serit"], r["3"]["btk_hedef"]) == ("BTK", "2026-09-30 15:00:00")
    assert r["4"]["son24"] == r["5"]["son24"] == "2026-10-01 09:00:00"      # eşleşmeyen 24 s
    s = gorunum.satir(conn, conn.execute(gorunum._SATIR_SQL + " WHERE e.is_no=?", ("400000001",)).fetchone(), None)
    assert s["renk"] == "yesil" and not s["gecikti"]                         # 25 saatlik iş 7 günlükte gecikmiş değil
    # kural ayarla değişir, koda gömülü değildir
    _ayar(conn, "serit_kurallari", [{"desen": "TV ARIZA", "serit": "BTK", "btk_saat": 24}])
    akis.hedefleri_yeniden_hesapla(conn)
    conn.commit()
    r = {x["is_no"][-1]: x for x in conn.execute("SELECT is_no, serit, btk_hedef FROM is_emri")}
    assert r["3"]["btk_hedef"] == "2026-10-01 09:00:00" and r["4"]["serit"] == "SAHA"


def test_oncelikli_kanal_sikayeti_en_ustte(v2db, conn, kim):
    y.aktar(v2db, [y.satir(1, task="TV+ Arıza"), y.satir(2, task="Kanal Şikayeti", baslangic="2026-09-30 09:30:00"),
                   y.satir(3, il="İzmir", ilce="Karşıyaka", mahalle="Bostanlı")])
    d = gorunum.isler_yaniti(conn, kim("operasyon"))
    assert [x["is_no"][-1] for x in d["isler"]][:2] == ["2", "3"]           # öncelikli › Kontrol gerekli › BTK
    x = d["isler"][0]
    assert x["serit"] == "MASA" and x["oncelik"].startswith("Kanal şikâyeti")
    assert all(i["oncelik"] is None for i in d["isler"][1:])


def test_arama_merdiveni_ve_sms_giden_kutusu(v2db, conn, kisi, kim, saat):
    y.aktar(v2db, [y.satir(1, mahalle="Görükle")])
    op = kim("operasyon")
    akis.ata(conn, NO, kisi["teknik1"], op)
    akis.gecis(conn, NO, "ulasilamadi", kim("teknik1"), istemci_id="e1")     # evde yok
    a = akis.arama_kaydet(conn, NO, op, "ulasilamadi", sure_sn=35)           # A1 10:00, SMS henüz yok
    assert a["uyanma"] == "2026-09-30 13:00:00" and a["merdiven"]["sonraki"] == "2026-09-30 13:00:00"
    assert a["boss_giden"]["alanlar"]["talep_ulasamama_sms"] is True and "sms" in a["boss_giden"]["neden"]
    assert "boss_islenecek" in a["rozetler"] and a["merdiven"]["sms_eksik"] == 1
    with pytest.raises(V2Hata) as e:
        akis.arama_kaydet(conn, NO, op, "ulasilamadi", sure_sn=12)          # 30 sn çaldırılmadı
    assert e.value.kod == "arama_kisa"
    a = akis.boss_islendi(conn, NO, True, op)                                # SMS BOSS'tan gönderildi
    assert a["merdiven"]["sms_eksik"] == 0 and a["boss_giden"] is None
    saat.ayarla("2026-09-30 22:05:00")
    with pytest.raises(V2Hata) as e:
        akis.arama_kaydet(conn, NO, op, "ulasilamadi")
    assert e.value.kod == "arama_saati" and "22:00" in e.value.mesaj
    saat.ayarla("2026-10-01 09:20:00")
    with pytest.raises(V2Hata) as e:
        akis.arama_kaydet(conn, NO, op, "ulasilamadi")
    assert e.value.kod == "arama_saati"


def test_ulasilamadi_kapanisi_merdiven_ister(v2db, conn, kim, saat):
    y.aktar(v2db, [y.satir(1)])
    op = kim("operasyon")
    with pytest.raises(V2Hata) as e:
        akis.gecis(conn, NO, "cozuldu", op, neden="musteriye_ulasilamadi")
    assert e.value.kod == "merdiven_eksik" and "4 arama daha" in e.value.mesaj
    for an in ("2026-09-30 10:00:00", "2026-09-30 13:05:00", "2026-10-01 10:00:00", "2026-10-01 13:10:00"):
        saat.ayarla(an)
        m = akis.arama_kaydet(conn, NO, op, "mesgul_kapali", sms=True)["merdiven"]
    assert m["tamam"] and m["gunler"] == [2, 2]
    a = akis.gecis(conn, NO, "cozuldu", op, neden="musteriye_ulasilamadi")
    assert (a["durum"], a["kapanis_nedeni"]) == ("cozuldu", "musteriye_ulasilamadi")


def test_ayni_gun_erken_arama_adim_sayilmaz():
    k = kurallar.VARSAYILAN["arama_merdiveni"]
    A = lambda z: {"zaman": z, "sonuc": "ulasilamadi", "webphone": True, "sms": True}   # noqa: E731
    m = kurallar.merdiven_durumu([A("2026-09-30 10:00:00"), A("2026-09-30 11:00:00")], k, dt.datetime(2026, 9, 30, 11, 5))
    assert (m["deneme"], m["gecerli"], m["sonraki"]) == (2, 1, "2026-09-30 13:00:00")   # 3 saat kuralı
    m = kurallar.merdiven_durumu([A("2026-09-30 17:40:00")], k, dt.datetime(2026, 9, 30, 17, 45))
    assert m["sonraki"] == "2026-10-01 10:00:00"                                 # 20:40 pencere dışı → ertesi sabah


def test_yanlis_no_ata_havuzu_ve_yeni_numara(v2db, conn, kim):
    y.aktar(v2db, [y.satir(1)])
    op = kim("operasyon")
    with pytest.raises(V2Hata) as e:
        akis.arama_kaydet(conn, NO, op, "yanlis_no")
    assert e.value.kod == "alan_eksik"
    a = akis.arama_kaydet(conn, NO, op, "yanlis_no", notu="Numara başka birine ait")
    assert a["durum"] == "askida" and a["askida_neden"] == "İrtibat hatalı (ATA havuzu)"
    assert a["aski"][-1]["durdurur"] is False and a["merdiven"]["ata_havuzu"]
    a = akis.arama_kaydet(conn, NO, op, "ulasilamadi", yeni_numara=True, sms=True)
    assert a["merdiven"]["deneme"] == 1 and not a["merdiven"]["ata_havuzu"]    # yeni numarada merdiven sıfırdan


def test_btk_sikayet_sayaci_is_gunu(v2db, conn, kim, saat):
    y.aktar(v2db, [y.satir(1), y.satir(2)])
    op = kim("operasyon")
    a = akis.btk_sikayet_kaydet(conn, NO, op, tarih="2026-09-17 10:00:00")    # Perşembe
    b = a["btk_sikayet"]
    assert (b["sure_is_gunu"], b["gecen_is_gunu"], b["kalan_is_gunu"], b["alarm"]) == (10, 9, 1, "8. iş günü")
    assert b["son_gun"] == "2026-10-01 23:59:59" and not b["gecikti"] and not b["btk_kapali"]
    saat.ayarla("2026-10-02 09:00:00")
    b = gorunum.ayrinti(conn, NO, op)["btk_sikayet"]
    assert b["alarm"] == "10. iş günü" and b["gecikti"]
    # reopen 5 iş günü; 29 Ekim resmî tatil atlanır
    saat.ayarla("2026-10-26 10:00:00")
    b = akis.btk_sikayet_kaydet(conn, "400000002", op, tarih="2026-10-26 10:00:00", reopen=True)["btk_sikayet"]
    assert (b["sure_is_gunu"], b["son_gun"]) == (5, "2026-11-03 23:59:59")
    a = akis.btk_sikayet_kaydet(conn, "400000002", op, kaldir=True)
    assert a["btk_sikayet"] is None


def test_tcs_bir_kez_ve_sure_disi(v2db, conn, kim, saat):
    y.aktar(v2db, [y.satir(1)])
    op = kim("operasyon")
    with pytest.raises(V2Hata) as e:
        akis.tcs_gir(conn, NO, op, "2026-10-20 10:00:00", True)
    assert e.value.kod == "btk_sikayet_yok"
    akis.btk_sikayet_kaydet(conn, NO, op, tarih="2026-09-28 10:00:00")        # son gün 12.10
    with pytest.raises(V2Hata) as e:
        akis.tcs_gir(conn, NO, op, "2026-10-20 10:00:00", False)
    assert e.value.kod == "alan_eksik" and "teyitli" in e.value.mesaj
    with pytest.raises(V2Hata) as e:
        akis.tcs_gir(conn, NO, op, "2026-10-09 10:00:00", True)               # süre içinde
    assert e.value.kod == "tcs_gecersiz"
    a = akis.tcs_gir(conn, NO, op, "2026-10-20 10:00:00", True)
    assert a["btk_sikayet"]["btk_kapali"] and a["btk_sikayet"]["tcs"] == "2026-10-20 10:00:00"
    with pytest.raises(V2Hata) as e:
        akis.tcs_gir(conn, NO, op, "2026-10-25 10:00:00", True)
    assert e.value.kod == "tcs_var"


def test_btk_bildirilmis_is_iptal_edilmez(v2db, conn, kim):
    y.aktar(v2db, [y.satir(1)])
    op = kim("operasyon")
    akis.btk_sikayet_kaydet(conn, NO, op)
    with pytest.raises(V2Hata) as e:
        akis.gecis(conn, NO, "cozuldu", op, neden="iptal")
    assert e.value.kod == "btk_iptal_yasak"
    assert akis.gecis(conn, NO, "cozuldu", op, neden="mukerrer")["durum"] == "cozuldu"


def test_abone_askisi_en_cok_4_gun(v2db, conn, kim, saat):
    saat.ayarla("2026-10-01 09:00:00")                      # sınır: 2026-10-05 09:00 (+1 dk pay)
    y.aktar(v2db, [y.satir(1, task="Modem Değişikliği")])
    op = kim("operasyon")
    with pytest.raises(V2Hata) as e:
        akis.gecis(conn, NO, "askida", op, neden="abone", uyanma="2026-10-05 10:00:00")
    assert e.value.kod == "uyanma_gecersiz" and "4 gün" in e.value.mesaj
    assert akis.gecis(conn, NO, "askida", op, neden="abone", uyanma="2026-10-04 09:00:00")["durum"] == "askida"


def test_kesinti_bulteni_sevki_durdurur(v2db, conn, kisi, kim, saat):
    _ayar(conn, "btk_durduran_aski", kurallar.VARSAYILAN["btk_durduran_aski"])
    y.aktar(v2db, [y.satir(1, task="Bağlantı Problemi", mahalle="Görükle"),
                   y.satir(2, task="TV+ Arıza", mahalle="Görükle"),
                   y.satir(3, task="Modem Değişikliği", mahalle="Görükle"),                   # etkilenmez
                   y.satir(4, task="Bağlantı Problemi", ilce="Osmangazi", mahalle="Hamitler")])  # başka ilçe
    op = kim("operasyon")
    akis.ata(conn, "400000002", kisi["teknik1"], op)
    s = kesinti.ekle(conn, BULTEN, op)
    assert s["kesinti"]["ilce_metni"] == "Bursa/Nilüfer" and s["kesinti"]["tur"] == "GPON" and s["kesinti"]["no"] == "734512"
    assert sorted(s["askiya_alinan"]) == ["400000001", "400000002"]
    d = {r[0][-1]: r[1] for r in conn.execute("SELECT is_no, durum FROM is_emri")}
    assert d == {"1": "askida", "2": "askida", "3": "bekliyor", "4": d["4"]} and d["4"] != "askida"
    a = gorunum.ayrinti(conn, "400000001", op)
    assert a["genel_ariza"] and a["btk_durdu"] and a["askida_neden"].startswith("Genel arıza (SOL kaynaklı)")
    with pytest.raises(V2Hata) as e:
        kesinti.ekle(conn, BULTEN, op)
    assert e.value.kod == "var"
    # bülten sürerken gelen yeni Nilüfer bağlantı işi doğrudan askıya düşer
    saat.ilerlet(minutes=30)
    y.aktar(v2db, [y.satir(i, task="Bağlantı Problemi", mahalle="Görükle") for i in (1, 2, 3)]
            + [y.satir(5, task="Bağlantı Problemi", mahalle="Görükle")])
    r = conn.execute("SELECT durum, askida_neden, uyanma FROM is_emri WHERE is_no='400000005'").fetchone()
    assert r["durum"] == "askida" and r["askida_neden"] == kesinti.neden_metni(s["kesinti"]) and r["uyanma"]
    assert conn.execute("SELECT durdurur, kaynak FROM is_aski WHERE is_no='400000005'").fetchone()[:] == (1, "elle")
    b = kesinti.bitir(conn, s["kesinti"]["id"], op)
    assert sorted(b["uyanan"]) == ["400000001", "400000002", "400000005"]
    assert conn.execute("SELECT durum FROM is_emri WHERE is_no='400000001'").fetchone()[0] == "bekliyor"
    assert conn.execute("SELECT COUNT(*) FROM is_aski WHERE bitis IS NULL").fetchone()[0] == 0
    with pytest.raises(V2Hata):
        kesinti.ekle(conn, "Bülten: İstanbul Kadıköy GPON kesintisi", op)


def test_kesinti_adaylari_verimlilik_paketi(v2db, conn, kim, saat):
    y.aktar(v2db, [y.satir(i, task="Bağlantı Problemi", ilce="Yıldırım", mahalle="Yiğitler",
                           baslangic="2026-09-30 07:00:00") for i in range(1, 7)]
            + [y.satir(7, task="Bağlantı Problemi", mahalle="Görükle", baslangic="2026-09-30 07:00:00")])
    a = kesinti.adaylar(conn, saat.an)
    assert [(g["ilce"], g["adet"]) for g in a["gruplar"]] == [("Yıldırım", 6)]
    assert "Müşteri No" in a["gruplar"][0]["paket"] and "Hizmet ID" in a["gruplar"][0]["paket"]
    gizli = kesinti.adaylar(conn, saat.an, musteri=False)["gruplar"][0]["paket"]
    assert "Müşteri No" not in gizli


def test_kural_dogrulama_ve_varsayilan():
    with pytest.raises(ValueError):
        kurallar.dogrula("serit_kurallari", [{"desen": "TV", "serit": "UZAY"}])
    with pytest.raises(ValueError):
        kurallar.dogrula("hedef_saatleri", {"varsayilan": 0, "kurallar": []})
    with pytest.raises(ValueError):
        kurallar.dogrula("resmi_tatiller", ["29 Ekim"])
    with pytest.raises(ValueError):
        kurallar.dogrula("yok_boyle", 1)
    assert kurallar.dogrula("kesinti_ornek_esigi", 7.0) == 7
    assert kurallar.oku(None, "arama_merdiveni")["gun2"] == 2
    assert kurallar.eslesir("ATA", "ATA Araması") and not kurallar.eslesir("ATA", "Satış Talebi")


def test_ek12_uclari_http(istemci, jeton, v2db, conn, kisi, saat):
    y.aktar(v2db, [y.satir(1), y.satir(2, task="TV+ Arıza")])
    h, ht = jeton(kisi["operasyon"]), jeton(kisi["teknik1"])
    r = istemci.post(f"/api/isler/{NO}/arama", headers=h, json={"sonuc": "ulasilamadi", "sure_sn": 40})
    assert r.status_code == 200 and r.json()["merdiven"]["deneme"] == 1
    assert istemci.post(f"/api/isler/{NO}/arama", headers=ht, json={"sonuc": "ulasildi"}).status_code == 403
    r = istemci.post(f"/api/isler/{NO}/arama", headers=h, json={"sonuc": "bilinmiyor"})
    assert r.status_code == 422 and r.json()["kod"] == "alan_eksik"
    r = istemci.post(f"/api/isler/{NO}/tcs", headers=h, json={"tarih": "2026-10-30 10:00:00", "teyitli": True})
    assert r.status_code == 409 and r.json()["kod"] == "btk_sikayet_yok"
    r = istemci.post(f"/api/isler/{NO}/btk-sikayet", headers=h, json={"tarih": "2026-09-29 10:00:00"})
    assert r.status_code == 200 and r.json()["btk_sikayet"]["sure_is_gunu"] == 10
    r = istemci.post("/api/kesinti", headers=h, json={"metin": BULTEN})
    assert r.status_code == 201 and len(r.json()["askiya_alinan"]) == 2
    liste = istemci.get("/api/kesinti", headers=h).json()["kesintiler"]
    assert liste[0]["askida_is"] == 2 and liste[0]["durum_metni"] == "Devam ediyor"
    assert istemci.get("/api/kesinti/aday", headers=h).status_code == 200
    r = istemci.post(f"/api/kesinti/{liste[0]['id']}/bitti", headers=h)
    assert r.status_code == 200 and len(r.json()["uyanan"]) == 2
    assert istemci.post("/api/kesinti", headers=ht, json={"metin": BULTEN}).status_code == 403
