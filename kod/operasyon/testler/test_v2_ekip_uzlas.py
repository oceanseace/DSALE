"""Ekip ataması BOSS kesin kaynak (ekip_uzlas.py): BOSS'ta ekibi boş iş (askı/merkeze) uygulamada da ekipten alınır;
BOSS ekibi dolu iş o ekibe eşli teknisyende görünür; sonucu gelmemiş uygulama atama yazması geri alınmaz;
açılış uzlaşması yedekli ve tek seferliktir."""
from __future__ import annotations

from operasyon.testler import yardim as y
from operasyon.v2 import akis, boss, boss_yazma, ekip_uzlas, gorunum

EKIP_A = "TEST EKİP A"
NO = "400000001"


def _gorev(i: int = 1, *, durum="Randevu alındı", ekip=None, **ek) -> dict:
    no = f"{400000000 + i}"
    g = {"task_no": no, "task_adi": "Bağlantı Problemi", "durum": durum, "musteri_no": f"9{no[-8:]}",
         "musteri_adi": "Deneme", "adres": f"DENEME APT. Görükle Mh. Test Sk. No:{no[-3:]} Nilüfer", "il": "Bursa",
         "ilce": "Nilüfer", "acilis": "2026-09-30 09:00:00", "satis_kanali": "GLOBAL CC", "ekip": ekip}
    g.update(ek)
    return g


def _esitle(v2db, *gorevler, mod=None):
    govde = {"gorevler": list(gorevler), "tam": False}
    if mod:
        govde["mod"] = mod
    return boss.esitle(y.fabrika(v2db), govde)


def _hazirla(conn, kisi):
    """teknik1 = BOSS ekibi A (kaynak='boss' → harita yalnız BOSS ekiplerinden), teknik2 = BOSS ekibi B."""
    conn.execute("UPDATE kullanici SET boss_ekip=?, kaynak='boss' WHERE id=?", (EKIP_A, kisi["teknik1"]))
    conn.execute("UPDATE kullanici SET boss_ekip='TEST EKİP B', kaynak='boss' WHERE id=?", (kisi["teknik2"],))
    conn.commit()


def _is(conn, no=NO):
    return conn.execute("SELECT * FROM is_emri WHERE is_no=?", (no,)).fetchone()


def _son_not(conn, no=NO):
    return conn.execute("SELECT notu FROM is_emri_olay WHERE is_no=? ORDER BY id DESC LIMIT 1", (no,)).fetchone()[0]


def _yazma_sonucu(conn, durum, no=NO):
    ids = [r[0] for r in conn.execute("SELECT id FROM boss_yazma WHERE is_no=? AND tur='atama' AND durum IN "
                                      "('bekliyor','gonderiliyor')", (no,))]
    assert ids, "atama yazması kuyrukta olmalı"
    boss_yazma.sonuc_al(conn, {"kayitlar": ids, "durum": durum, "http": 200 if durum == "gonderildi" else 500})
    conn.commit()


def test_askiya_alinan_bos_ekip_atamayi_kaldirir(v2db, conn, kisi, kim):
    _hazirla(conn, kisi)
    _esitle(v2db, _gorev(ekip=EKIP_A))
    assert _is(conn)["atanan_id"] == kisi["teknik1"], "BOSS ekibi eşli teknisyende"
    _esitle(v2db, _gorev(durum="Askıya alındı", ekip=None))
    r = _is(conn)
    assert r["atanan_id"] is None and r["sira"] is None and r["durum"] == "askida"
    notlar = [n for (n,) in conn.execute("SELECT notu FROM is_emri_olay WHERE is_no=?", (NO,)) if n]
    assert any("BOSS'ta ekipten alındı (Askıya alındı)" in n for n in notlar)
    # TASKS Ekip sütunu (atanan?.ad || boss_ekip) boş
    s = next(x for x in gorunum.isler_yaniti(conn, kim("operasyon"))["isler"] if x["is_no"] == NO)
    assert s["atanan"] is None and not s.get("boss_ekip")


def test_uygulama_atamasi_yazma_hatasi_sonrasi_merkeze_kaldirir(v2db, conn, kisi, kim):
    """Canlıdaki hata: uygulamadan atanmış (yazması sonuçlanmış) iş BOSS'ta merkeze gönderildi, ekip boş."""
    _hazirla(conn, kisi)
    _esitle(v2db, _gorev(durum="Açık"))
    akis.ata(conn, NO, kisi["teknik2"], kim("operasyon"))
    _yazma_sonucu(conn, "hata")
    _esitle(v2db, _gorev(durum="Merkeze gönderildi"))
    r = _is(conn)
    assert r["atanan_id"] is None and r["durum"] == "merkeze"
    assert "ekipten alındı (Merkeze gönderildi)" in _son_not(conn)
    assert "önceki: Veli Deneme" in _son_not(conn)


def test_randevulu_ekip_esli_teknisyene_uyar(v2db, conn, kisi, kim):
    _hazirla(conn, kisi)
    _esitle(v2db, _gorev(durum="Açık"))
    akis.ata(conn, NO, kisi["teknik2"], kim("operasyon"))
    _yazma_sonucu(conn, "hata")                              # BOSS'a gitmedi; BOSS'ta başka ekip randevu verdi
    _esitle(v2db, _gorev(ekip=EKIP_A, randevu_bas="2026-10-10 10:00:00", randevu_bit="2026-10-10 12:00:00"))
    r = _is(conn)
    assert r["atanan_id"] == kisi["teknik1"] and r["atama_kaynagi"] == "boss" and r["durum"] == "atandi"
    # eşli kişi olmayan BOSS ekibi: atama kalkar, Ekip sütunu BOSS adını gösterir
    _esitle(v2db, _gorev(ekip="BİLİNMEYEN EKİP", randevu_bas="2026-10-10 10:00:00",
                         randevu_bit="2026-10-10 12:00:00"))
    r = _is(conn)
    assert r["atanan_id"] is None and r["boss_ekip"] == "BİLİNMEYEN EKİP"
    assert "eşli kişi yok" in _son_not(conn)


def test_bekleyen_uygulama_yazmasi_geri_alinmaz(v2db, conn, kisi, kim):
    _hazirla(conn, kisi)
    _esitle(v2db, _gorev(durum="Askıya alındı"))
    akis.ata(conn, NO, kisi["teknik2"], kim("operasyon"))     # askıdan atama → BOSS'a yazma 'bekliyor'
    _esitle(v2db, _gorev(durum="Askıya alındı", guncelleme="x"))      # BOSS görüntüsü yazmadan önce
    assert _is(conn)["atanan_id"] == kisi["teknik2"], "bekleyen yazma bozulmaz"
    conn.execute("UPDATE boss_yazma SET durum='gonderiliyor' WHERE is_no=?", (NO,))
    conn.commit()
    _esitle(v2db, mod="fark")                                # değişmeyen işte de uzlaşma koşar
    assert _is(conn)["atanan_id"] == kisi["teknik2"], "gönderiliyor: sonucu beklenir"
    # başarılı sonuç, BOSS görüntüsü henüz eski: korunur; BOSS ekibi gelince eşli kişi aynı → değişiklik yok
    _yazma_sonucu(conn, "gonderildi")
    _esitle(v2db, mod="fark")
    assert _is(conn)["atanan_id"] == kisi["teknik2"]
    _esitle(v2db, _gorev(ekip="TEST EKİP B", randevu_bas="2026-10-10 10:00:00", randevu_bit="2026-10-10 12:00:00"))
    assert _is(conn)["atanan_id"] == kisi["teknik2"]
    # yeni atama, BOSS hata döndü → sonuç gelince uzlaşır (BOSS ekip B'de kalır)
    akis.ata(conn, NO, kisi["teknik1"], kim("operasyon"))
    _esitle(v2db, mod="fark")
    assert _is(conn)["atanan_id"] == kisi["teknik1"]
    _yazma_sonucu(conn, "hata")
    _esitle(v2db, mod="fark")
    assert _is(conn)["atanan_id"] == kisi["teknik2"]


def test_toplu_atama_bekleyen_yazmayla_korunur(v2db, conn, kisi, kim):
    _hazirla(conn, kisi)
    _esitle(v2db, _gorev(1, durum="Merkeze gönderildi"), _gorev(2, durum="Askıya alındı"))
    s = akis.toplu_ata(conn, [{"is_no": "400000001", "teknik_id": kisi["teknik1"]},
                              {"is_no": "400000002", "teknik_id": kisi["teknik1"]}], kim("operasyon"))
    assert s
    _esitle(v2db, mod="fark")
    assert {r[0] for r in conn.execute("SELECT atanan_id FROM is_emri WHERE is_no IN ('400000001','400000002')")} \
        == {kisi["teknik1"]}
    assert conn.execute("SELECT COUNT(*) FROM boss_yazma WHERE tur='atama' AND durum='bekliyor'").fetchone()[0] == 2


def test_acilis_uzlasmasi_yedekli_ve_tek_seferlik(v2db, conn, kisi, kim, tmp_path):
    _hazirla(conn, kisi)
    _esitle(v2db, _gorev(1, durum="Askıya alındı"), _gorev(2, durum="Merkeze gönderildi"),
            _gorev(3, ekip=EKIP_A), _gorev(4, durum="Açık"))
    # eski veri: uygulama ataması BOSS'la çelişiyor (yazma kaydı yok / sonuçlanmış)
    conn.execute("UPDATE is_emri SET atanan_id=?, atama_kaynagi='toplu', atama_zamani='2026-10-01 10:00:00', sira=3 "
                 "WHERE is_no IN ('400000001','400000002')", (kisi["teknik2"],))
    conn.execute("UPDATE is_emri SET atanan_id=?, atama_kaynagi='toplu', atama_zamani='2026-10-01 10:00:00', "
                 "durum='atandi' WHERE is_no='400000003'", (kisi["teknik2"],))
    conn.commit()
    olay_once = conn.execute("SELECT COUNT(*) FROM is_emri_olay").fetchone()[0]
    s = ekip_uzlas.calistir(conn, v2db)
    assert s is not None and s["toplam"] == 3 and s["alinan"] == 2 and s["atanan"] == 1
    assert s["yedek"] and __import__("pathlib").Path(s["yedek"]).exists()
    assert _is(conn, "400000001")["atanan_id"] is None and _is(conn, "400000001")["sira"] is None
    assert _is(conn, "400000002")["atanan_id"] is None
    assert _is(conn, "400000003")["atanan_id"] == kisi["teknik1"]
    assert _is(conn, "400000004")["atanan_id"] is None
    assert conn.execute("SELECT COUNT(*) FROM is_emri_olay").fetchone()[0] == olay_once + 3
    # idempotent: ikinci açılış hiçbir şey yapmaz; uzlaşma yeniden koşsa da değişiklik yok
    assert ekip_uzlas.yapildi_mi(conn)
    assert ekip_uzlas.calistir(conn, v2db) is None
    assert ekip_uzlas.uzlas(conn)["toplam"] == 0
    assert conn.execute("SELECT COUNT(*) FROM is_emri_olay").fetchone()[0] == olay_once + 3
