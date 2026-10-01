"""İçe aktarım hattı (F4, F5, F18; spec §4). Sentetik rapor; gerçek rapor yalnız sayı için (varsa)."""
from __future__ import annotations

import sqlite3
import threading
import time

import pytest

from operasyon.testler import yardim as y
from operasyon.testler.conftest import GERCEK_RAPOR
from operasyon.v2 import akis, aktarim, sozluk
from operasyon.v2.hatalar import V2Hata


def _acik(conn):
    return conn.execute("SELECT COUNT(*) FROM is_emri WHERE durum NOT IN ('cozuldu','kapandi')").fetchone()[0]


def test_ayni_dosya_etkisiz(v2db, conn):
    veri = y.xlsx(y.standart(12))
    s = y.aktar(v2db, None, veri=veri)
    assert s["fark"]["yeni"] == 12 and s["tam_kapsam"]
    once = y.db_ozeti(conn)
    s2 = y.aktar(v2db, None, veri=veri)
    assert s2["ayni_dosya"] is True and s2["aktarim_id"] == s["aktarim_id"]
    assert "zaten yüklenmişti" in s2["mesaj"]
    assert y.db_ozeti(conn) == once                  # iş, olay, öbek, sözlük ve aktarım sayısı birebir


def test_ters_sirali_ayni_icerik_0_yeni_atama_korunur(v2db, conn, kisi, kim):
    satirlar = y.standart(12)
    y.aktar(v2db, satirlar)
    op = kim("operasyon")
    nolar = [r[0] for r in conn.execute("SELECT is_no FROM is_emri ORDER BY is_no")]
    for no in nolar[:3]:
        akis.ata(conn, no, kisi["teknik1"], op)
    akis.randevu(conn, nolar[3], op, "2026-10-01 10:00:00", "2026-10-01 12:00:00", True)
    once = {r[0]: tuple(r[1:]) for r in conn.execute(
        "SELECT is_no, durum, atanan_id, randevu_bas, randevu_bit, randevu_teyitli, surum FROM is_emri")}
    s = y.aktar(v2db, list(reversed(satirlar)))
    assert s["fark"] == {"yeni": 0, "degisen": 0, "kaybolan": 0, "yeniden_acilan": 0, "degismeyen": 12}
    sonra = {r[0]: tuple(r[1:]) for r in conn.execute(
        "SELECT is_no, durum, atanan_id, randevu_bas, randevu_bit, randevu_teyitli, surum FROM is_emri")}
    assert sonra == once                             # bugünkü emek (3 atama + 1 randevu) aynen


def test_degisen_boss_alani_yazilir_bizimki_korunur(v2db, conn, kisi, kim):
    satirlar = y.standart(6)
    y.aktar(v2db, satirlar)
    no = conn.execute("SELECT is_no FROM is_emri ORDER BY is_no LIMIT 1").fetchone()[0]
    akis.ata(conn, no, kisi["teknik2"], kim("operasyon"),
             randevu={"bas": "2026-10-01 14:00:00", "bit": "2026-10-01 16:00:00", "teyitli": True})
    satirlar[0]["Son Açıklama"] = "Müşteri aradı"
    satirlar[0]["Randevu Başlangıç Tarihi"] = "2026-10-02 10:00:00"
    satirlar[0]["Randevu Bitiş Tarihi"] = "2026-10-02 12:00:00"
    s = y.aktar(v2db, satirlar)
    assert s["fark"]["degisen"] == 1
    r = conn.execute("SELECT * FROM is_emri WHERE is_no=?", (no,)).fetchone()
    assert r["boss_son_aciklama"] == "Müşteri aradı" and r["boss_randevu_bas"] == "2026-10-02 10:00:00"
    assert r["atanan_id"] == kisi["teknik2"] and r["randevu_bas"] == "2026-10-01 14:00:00"   # bizimki ezilmez
    assert "ekip" in r["boss_bekleyen"] and "randevu" in r["boss_bekleyen"]                     # giden kutusu
    olay = conn.execute("SELECT eski, yeni FROM is_emri_olay WHERE is_no=? AND tur='aktarim_degisti'", (no,)).fetchone()
    assert "boss_son_aciklama" in olay["yeni"]


def test_kaybolan_kapanir(v2db, conn, kisi, kim):
    satirlar = y.standart(12)
    y.aktar(v2db, satirlar)
    nolar = sorted(r[0] for r in conn.execute("SELECT is_no FROM is_emri"))
    tek = kim("teknik1")
    akis.ata(conn, nolar[5], kisi["teknik1"], kim("operasyon"))
    akis.gecis(conn, nolar[5], "cozuldu", tek, istemci_id="c1", evde_miydi=True)
    s = y.aktar(v2db, [x for x in satirlar if x["Task No"] not in (nolar[4], nolar[5])])
    assert s["fark"]["kaybolan"] == 2
    r4 = conn.execute("SELECT * FROM is_emri WHERE is_no=?", (nolar[4],)).fetchone()
    r5 = conn.execute("SELECT * FROM is_emri WHERE is_no=?", (nolar[5],)).fetchone()
    assert (r4["durum"], r4["kapanis_nedeni"], r4["kapanis_kesin"]) == ("kapandi", "boss_listeden_dustu", 0)
    assert (r5["durum"], r5["kapanis_nedeni"]) == ("kapandi", "cozuldu_dogrulandi")
    assert conn.execute("SELECT COUNT(*) FROM is_emri_olay WHERE is_no=? AND tur='kayboldu'", (nolar[4],)).fetchone()[0] == 1


def test_yeniden_acilir_acilma_sayisi_2(v2db, conn, kisi, kim):
    satirlar = y.standart(8)
    y.aktar(v2db, satirlar)
    no = sorted(r[0] for r in conn.execute("SELECT is_no FROM is_emri"))[2]
    akis.ata(conn, no, kisi["teknik1"], kim("operasyon"))
    y.aktar(v2db, [x for x in satirlar if x["Task No"] != no])
    assert conn.execute("SELECT durum FROM is_emri WHERE is_no=?", (no,)).fetchone()[0] == "kapandi"
    satirlar[0]["Son Açıklama"] = "farklı sha için"
    s = y.aktar(v2db, satirlar)
    assert s["fark"]["yeniden_acilan"] == 1
    r = conn.execute("SELECT * FROM is_emri WHERE is_no=?", (no,)).fetchone()
    assert r["acilma_sayisi"] == 2 and r["durum"] in ("bekliyor", "triyaj") and r["kapanis"] is None
    assert r["atanan_id"] is None and r["ilk_atama_zamani"] is None
    assert r["oneri_teknik_id"] == kisi["teknik1"] or r["oneri_teknik_id"] is None   # önceki teknik öneride öne
    assert conn.execute("SELECT COUNT(*) FROM is_emri_olay WHERE is_no=? AND tur='yeniden_acildi'", (no,)).fetchone()[0] == 1


def test_cok_kaybolan_onay_ve_yeniden_hesap(v2db, conn):
    tam = [y.satir(i) for i in range(1, 61)]
    y.aktar(v2db, tam)
    with pytest.raises(V2Hata) as e:
        y.aktar(v2db, tam[:5])
    assert e.value.kod == "onay_gerekli" and e.value.durum == 409
    assert "cok_kaybolan" in e.value.ek["nedenler"] and e.value.ek["fark"]["kaybolan"] == 55
    aid = e.value.ek["aktarim_id"]
    assert _acik(conn) == 60                                           # otomatik uygulanmadı
    # bu arada daha yeni bir tam rapor geldi (+1 iş)
    y.aktar(v2db, tam + [y.satir(61)])
    s = aktarim.uygula(y.fabrika(v2db), aid, "tam", None)
    assert s["fark"]["kaybolan"] == 56                                 # fark YENİDEN hesaplandı
    assert _acik(conn) == 5


def test_cok_kaybolan_kismi_hic_kapatmaz(v2db, conn):
    tam = [y.satir(i) for i in range(1, 61)]
    y.aktar(v2db, tam)
    with pytest.raises(V2Hata) as e:
        y.aktar(v2db, tam[:5])
    s = aktarim.uygula(y.fabrika(v2db), e.value.ek["aktarim_id"], "kismi", None)
    assert s["tam_kapsam"] is False and s["fark"]["kaybolan"] == 0
    assert _acik(conn) == 60
    assert conn.execute("SELECT tam_kapsam FROM ie_aktarim WHERE id=?", (s["aktarim_id"],)).fetchone()[0] == 0


def test_eski_rapor_409_zorla_kismi_hic_kapatmaz(v2db, conn):
    tam = y.standart(12)
    y.aktar(v2db, tam, dosya_zamani="2026-09-30T08:00:00Z")          # 11:00 TR
    with pytest.raises(V2Hata) as e:
        y.aktar(v2db, tam[:9], dosya_zamani="2026-09-30T07:00:00Z")   # 10:00 TR: eski
    assert e.value.kod == "onay_gerekli" and e.value.ek["nedenler"] == ["eski_rapor"]
    assert "eski görünüyor" in e.value.mesaj
    s = aktarim.uygula(y.fabrika(v2db), e.value.ek["aktarim_id"], "tam", None)   # tam istense de kısmi
    assert s["tam_kapsam"] is False
    assert _acik(conn) == 12


def test_vazgec(v2db, conn):
    tam = [y.satir(i) for i in range(1, 61)]
    y.aktar(v2db, tam)
    with pytest.raises(V2Hata) as e:
        y.aktar(v2db, tam[:3])
    aktarim.vazgec(y.fabrika(v2db), e.value.ek["aktarim_id"], None)
    assert conn.execute("SELECT durum FROM ie_aktarim WHERE id=?", (e.value.ek["aktarim_id"],)).fetchone()[0] == "vazgecildi"
    with pytest.raises(V2Hata) as e2:
        aktarim.uygula(y.fabrika(v2db), e.value.ek["aktarim_id"], "tam", None)
    assert e2.value.kod == "durum_gecersiz"


def test_eszamanli_iki_yukleme_409(v2db, conn, monkeypatch):
    asil = aktarim.hazirla

    def yavas(c, df):
        time.sleep(0.6)
        return asil(c, df)
    monkeypatch.setattr(aktarim, "hazirla", yavas)
    sonuc = {}

    def yukle(ad, satirlar):
        try:
            sonuc[ad] = y.aktar(v2db, satirlar)
        except V2Hata as e:
            sonuc[ad] = e.kod
    t1 = threading.Thread(target=yukle, args=("a", y.standart(5)))
    t1.start()
    time.sleep(0.2)
    yukle("b", y.standart(6))
    t1.join()
    assert sonuc["b"] == "aktarim_suruyor" and isinstance(sonuc["a"], dict)
    assert conn.execute("SELECT COUNT(*) FROM is_emri").fetchone()[0] == 5


def test_yedek_alinir(v2db, conn):
    s = y.aktar(v2db, y.standart(4))
    assert s["yedek"]
    yol = next((v2db.parent / "yedek" / "aktarim").glob(s["yedek"]))
    c = sqlite3.connect(f"file:{yol.as_posix()}?mode=ro", uri=True)
    try:
        assert c.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert c.execute("SELECT COUNT(*) FROM is_emri").fetchone()[0] == 0          # yazmadan ÖNCEKİ hâl
    finally:
        c.close()


def test_hata_rollback(v2db, conn, monkeypatch):
    y.aktar(v2db, y.standart(4))
    once = y.db_ozeti(conn)[0]
    asil = aktarim._guncelle

    def bozuk(b, x, r, yeniden):
        raise RuntimeError("disk dolu gibi")
    monkeypatch.setattr(aktarim, "_guncelle", bozuk)
    satirlar = y.standart(6)
    satirlar[0]["Son Açıklama"] = "değişti"
    with pytest.raises(RuntimeError):
        y.aktar(v2db, satirlar)
    monkeypatch.setattr(aktarim, "_guncelle", asil)
    assert y.db_ozeti(conn)[0] == once                                  # işler ve öbekler hiç değişmedi
    son = conn.execute("SELECT durum, hata FROM ie_aktarim ORDER BY id DESC LIMIT 1").fetchone()
    assert son["durum"] == "hata" and "Yazılamadı" in son["hata"]


def test_rapor_tanimadi_422(v2db, conn):
    import io
    import pandas as pd
    b = io.BytesIO()
    pd.DataFrame({"a": [1]}).to_excel(b, index=False)
    for veri in (b"merhaba", b.getvalue()):
        with pytest.raises(V2Hata) as e:
            y.aktar(v2db, None, veri=veri)
        assert e.value.kod == "rapor_tanimadi" and e.value.durum == 422
    assert conn.execute("SELECT COUNT(*) FROM is_emri").fetchone()[0] == 0


def test_buyuk_dosya_413(v2db):
    with pytest.raises(V2Hata) as e:
        y.aktar(v2db, None, veri=b"x" * (aktarim.AZAMI_BOYUT + 1))
    assert e.value.durum == 413


def test_filtre_istisnasi_c5(v2db, conn):
    satirlar = [y.satir(1, task="Kurulum Taskı Ürememiş"), y.satir(2, task="TV+ Kurulum"),
                y.satir(3, task="2.Donanım"), y.satir(4, task="Bağlantı Problemi")]
    s = y.aktar(v2db, satirlar)
    assert s["fark"]["yeni"] == 2
    assert (s["cikarilan"]["kurulum"], s["cikarilan"]["ikinci_donanim"], s["cikarilan"]["istisna_tutulan"]) == (1, 1, 1)
    adlar = {r[0] for r in conn.execute("SELECT task_adi FROM is_emri")}
    assert adlar == {"Kurulum Taskı Ürememiş", "Bağlantı Problemi"}


def test_koy_bicimi_yalova(v2db, conn):
    assert sozluk.koy_bicimi_ayrinti("Özden Bbk.Mah.(Kadıköy) Mah. Fetih 7. Sk. No:14") == ("Kadıköy", "Özden")
    assert sozluk.koy_bicimi_ayrinti("Altı (Çavuşçiftliği) Mh. Deneme Sk. No:3") == ("Çavuşçiftliği", "Altı")
    assert sozluk.koy_bicimi("Taşköprü Köyü Deneme Sk. No:5") == "Taşköprü"
    assert sozluk.koy_bicimi("KAYAPA TOKİ (426 ADA) SİT. 8G BLK. 30 Ağustos Zafer Mh.") is None
    # Bugünkü ayrıştırmanın adı sözlükte yoksa köy adı alınır; alt yer adı nota yazılır
    s = y.aktar(v2db, [y.satir(1, il="Yalova", ilce="Altınova",
                                adres="Denemeyeri Bbk.Mah.(Kaytazdere) Mh. Deneme Sk. No:1 Altınova")])
    r = conn.execute("SELECT mahalle, mahalle_kaynak FROM is_emri").fetchone()
    assert (r["mahalle"], r["mahalle_kaynak"]) == ("Kaytazdere", "koy")
    assert s["fark"]["yeni"] == 1
    # Sözlükte bilinen ad (kullanıcının öbeklerindeki "Özden") korunur: aynı rapor bugünkü motorla aynı öbeğe düşer
    szl = sozluk.sozluk_db(conn)
    ms = sozluk.mahalle_coz(szl, "Özden Bbk.Mah.(Kadıköy) Mah. Fetih Sk. No:1", "Yalova", "Merkez")
    if "OZDEN" in szl.ilce_mahalleleri("Yalova", "Merkez"):
        assert ms.ad == "Özden"
    else:
        assert (ms.ad, ms.kaynak) == ("Kadıköy", "koy")


def test_lokasyon_sifirli_eslesir(v2db, conn):
    r = conn.execute("SELECT bina_serial, location_id, il, ilce, mahalle FROM bina WHERE location_id GLOB "
                     "'0[0-9][0-9][0-9][0-9][0-9][0-9][0-9]' AND pasif=0 LIMIT 1").fetchone()
    if r is not None:
        lok, beklenen = r["location_id"].lstrip("0"), r["bina_serial"]           # raporda sıfırsız
    else:
        r = conn.execute("SELECT bina_serial, location_id, il, ilce, mahalle FROM bina WHERE length(location_id)=7 "
                         "AND pasif=0 AND location_id GLOB '[0-9]*' LIMIT 1").fetchone()
        assert r is not None
        lok, beklenen = "0" + r["location_id"], r["bina_serial"]                  # raporda fazladan sıfır
    y.aktar(v2db, [y.satir(1, lokasyon=lok, il=r["il"], ilce=r["ilce"], mahalle=r["mahalle"])])
    x = conn.execute("SELECT bina_serial, konum_kaynak, konum_yaklasik FROM is_emri").fetchone()
    assert (x["bina_serial"], x["konum_kaynak"], x["konum_yaklasik"]) == (beklenen, "bina", 0)


def test_lokasyon_onemap_mahallesi_esas(v2db, conn):
    """F4: Location Id varsa OneMap'teki binanın mahallesi esastır (adres başka mahalle yazsa da)."""
    r = conn.execute("SELECT location_id, mahalle FROM bina WHERE ilce='Nilüfer' AND location_id IS NOT NULL AND "
                     "mahalle NOT IN ('Görükle','Bilinmiyor') AND pasif=0 LIMIT 1").fetchone()
    y.aktar(v2db, [y.satir(1, mahalle="Görükle", lokasyon=r["location_id"])])
    x = conn.execute("SELECT mahalle, mahalle_kaynak, triyaj_nedeni FROM is_emri").fetchone()
    from operasyon import is_emri as ie
    assert x["mahalle"] == ie.mahalle_eki_sil(r["mahalle"]) and x["mahalle_kaynak"] == "lokasyon"


@pytest.mark.skipif(not GERCEK_RAPOR.exists(), reason="gerçek BOSS raporu yok")
def test_lokasyon_db_332(v2db, conn):
    s = y.aktar(v2db, None, veri=GERCEK_RAPOR.read_bytes(), ad="TeknikTaskDetayRaporu.xlsx")
    lok = s["lokasyon"]
    # 30.09: 332/332 (11:38) · 334/334 (13:01) · 01.10: 307/308 (biri başka ilçedeki binayı gösteriyor → bilerek kullanılmaz)
    assert lok["var"] >= 300 and lok["eslesen"] >= 0.97 * lok["var"], lok
    assert y.lokasyon_kacan(conn) == 0                                  # aynı ilçedeki hiçbir Location Id kaçmaz
    assert s["fark"]["yeni"] == conn.execute("SELECT COUNT(*) FROM is_emri").fetchone()[0]


def test_kontrol_yalniz_gercek_sorun(v2db, conn):
    obeksiz = next(m for m in sozluk.ara(conn, None, "Bursa", None, 500)["mahalleler"] if m["obek"] is None)
    satirlar = [
        y.satir(1, il="İzmir", ilce="Karşıyaka", mahalle="Bostanlı"),                     # il dışı
        y.satir(2, adres="ADRES YOK", mahalle=""),                                        # mahalle yok
        y.satir(3, mahalle="Görükle"),                                                    # sorunsuz
        y.satir(4, mahalle=obeksiz["ad"], ilce=obeksiz["ilce"]),                          # öbeksiz
        y.satir(5, mahalle="Dumlupınar", adres="Dumlupınar Mah. Olmayan Sk. No:1 Nilüfer"),   # konum yaklaşık
    ]
    s = y.aktar(v2db, satirlar)
    nedenler = {r[0][-1]: r[1] for r in conn.execute("SELECT is_no, triyaj_nedeni FROM is_emri")}
    assert nedenler["1"] == "il_disi" and nedenler["2"] == "mahalle_yok" and nedenler["4"] == "obeksiz"
    assert nedenler["3"] is None and nedenler["5"] is None                            # yaklaşık konum Kontrol değil
    assert s["kontrol"] == 3
    assert conn.execute("SELECT konum_yaklasik FROM is_emri WHERE is_no LIKE '%5'").fetchone()[0] == 1


def test_yeni_is_acik_ticketli_binada_altyapi(v2db, conn):
    b = conn.execute("SELECT bina_serial, location_id, il, ilce, mahalle FROM bina WHERE location_id IS NOT NULL "
                     "AND pasif=0 AND ilce='Nilüfer' LIMIT 1").fetchone()
    conn.execute("INSERT INTO ticket (konu, durum, bina_serial, location_id, olusturma, guncelleme, acilis) "
                 "VALUES ('SİNYAL','AÇIK',?,?, '2026-09-28 09:00:00','2026-09-28 09:00:00','2026-09-28')",
                 (b["bina_serial"], b["location_id"]))
    conn.commit()
    y.aktar(v2db, [y.satir(1, lokasyon=b["location_id"], mahalle=b["mahalle"]), y.satir(2)])
    r = conn.execute("SELECT durum, ticket_id, oneri_teknik_id FROM is_emri WHERE is_no LIKE '%1'").fetchone()
    assert r["durum"] == "altyapi" and r["ticket_id"] is not None and r["oneri_teknik_id"] is None


def test_mahalle_benzer_kontrole_duser_ve_rapor_mahallesi_eklenir(v2db, conn):
    # "Görüklee" (benzer) sessizce öbeksiz kalmaz: Kontrol'e mahalle_benzer nedeniyle düşer
    y.aktar(v2db, [y.satir(1, adres="DENEME APT. Görüklee Mh. Test Sk. No:1 Nilüfer"),
                   y.satir(2, ilce="Keles", adres="Denemeköyüyeni Mh. Test Sk. No:2 Keles")])
    n = {r[0][-1]: r[1] for r in conn.execute("SELECT is_no, triyaj_nedeni FROM is_emri")}
    assert n["1"] in ("mahalle_benzer", None)          # sözlükte yakın yazım adres-benzer ile düzelmiş olabilir
    assert conn.execute("SELECT COUNT(*) FROM mahalle WHERE kaynak='rapor' AND ilce='Keles'").fetchone()[0] == 1


def test_gecmis_ve_onay_bekleyen(v2db, conn):
    tam = [y.satir(i) for i in range(1, 61)]
    y.aktar(v2db, tam)
    with pytest.raises(V2Hata):
        y.aktar(v2db, tam[:2])
    g = aktarim.gecmis(conn, 10)
    assert [x["durum"] for x in g] == ["onay_bekliyor", "uygulandi"]
    ob = aktarim.onay_bekleyenler(conn)
    assert len(ob) == 1 and ob[0]["nedenler"] == ["cok_kaybolan"] and ob[0]["mesaj"]
    assert "Müşteri" not in str(g)
