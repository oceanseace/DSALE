"""Durum makinesi, atama, randevu, ticket bağı, bayi işi, BOSS uzlaşması (F5, F7–F10, F16; spec §3)."""
from __future__ import annotations

import pytest

from operasyon.testler import yardim as y
from operasyon.v2 import akis, gorunum
from operasyon.v2.hatalar import V2Hata


def _isler(v2db, conn, satirlar=None, n=6):
    y.aktar(v2db, satirlar or y.standart(n))
    return sorted(r[0] for r in conn.execute("SELECT is_no FROM is_emri"))


def _durum(conn, no):
    return conn.execute("SELECT durum FROM is_emri WHERE is_no=?", (no,)).fetchone()[0]


def _surum(conn, no):
    return conn.execute("SELECT surum FROM is_emri WHERE is_no=?", (no,)).fetchone()[0]


def test_uctan_uca_durum_makinesi(v2db, conn, kisi, kim, saat):
    satirlar = y.standart(4)
    y.aktar(v2db, satirlar)
    no = sorted(r[0] for r in conn.execute("SELECT is_no FROM is_emri"))[0]
    op, tek = kim("operasyon"), kim("teknik1")
    saat.ilerlet(minutes=5)
    a = akis.randevu(conn, no, op, "2026-09-30 14:00:00", "2026-09-30 16:00:00", False, surum=_surum(conn, no))
    assert a["durum"] == "randevulu" and a["atanan"] is None
    saat.ilerlet(minutes=4)
    a = akis.ata(conn, no, kisi["teknik1"], op, surum=a["surum"])
    assert a["durum"] == "atandi" and a["atanan"]["id"] == kisi["teknik1"]
    assert a["randevu"]["bas"] == "2026-09-30 14:00:00"                   # verilen randevu korunur
    a = akis.gecis(conn, no, "yolda", tek, istemci_id="u1")
    a = akis.gecis(conn, no, "sahada", tek, istemci_id="u2")
    with pytest.raises(V2Hata) as e:
        akis.gecis(conn, no, "cozuldu", tek, istemci_id="u3")            # "Müşteri evde miydi?" zorunlu
    assert e.value.kod == "alan_eksik"
    a = akis.gecis(conn, no, "cozuldu", tek, istemci_id="u4", evde_miydi=True, sonuc_kodu="cozuldu")
    assert a["durum"] == "cozuldu" and a["kova"] == "biten"
    y.aktar(v2db, [x for x in satirlar if x["Task No"] != no])           # rapordan düştü
    r = conn.execute("SELECT * FROM is_emri WHERE is_no=?", (no,)).fetchone()
    assert (r["durum"], r["kapanis_nedeni"]) == ("kapandi", "cozuldu_dogrulandi")
    assert r["ilk_atama_zamani"] == "2026-09-30 10:09:00"                # ilk karar: randevu (10:05) değil, atama anı
    olaylar = conn.execute("SELECT tur, kullanici_ad FROM is_emri_olay WHERE is_no=? ORDER BY id", (no,)).fetchall()
    turler = [o["tur"] for o in olaylar]
    assert turler == ["olustu", "randevu", "atama", "durum", "durum", "durum", "kayboldu"]
    kisiler = [o["kullanici_ad"] for o in olaylar]
    assert kisiler[1:3] == [op["ad"], op["ad"]] and kisiler[3:6] == [tek["ad"]] * 3 and kisiler[-1] is None


def test_gecersiz_gecis_tum_ciftler_409(v2db, conn, kim):
    no = _isler(v2db, conn, n=1)[0]
    op = kim("operasyon")
    denenen = 0
    for eski in akis.DURUMLAR:
        for yeni in akis.DURUMLAR:
            if (eski, yeni) in akis.GECISLER:
                continue
            conn.execute("UPDATE is_emri SET durum=? WHERE is_no=?", (eski, no))
            conn.commit()
            with pytest.raises(V2Hata) as e:
                akis.gecis(conn, no, yeni, op, teknik_id=1, neden="iptal", randevu={"bas": None})
            assert e.value.kod == "gecersiz_gecis" and e.value.durum == 409, (eski, yeni)
            assert f"'{akis.ETIKET[eski]}' durumunda" in e.value.mesaj
            denenen += 1
    assert denenen > 60
    # yalnız sistemin yaptığı geçiş (her durum → kapandı) operasyona kapalı (bayi işi hariç)
    conn.execute("UPDATE is_emri SET durum='bekliyor' WHERE is_no=?", (no,))
    conn.commit()
    with pytest.raises(V2Hata) as e:
        akis.gecis(conn, no, "kapandi", op, neden="iptal")
    assert e.value.kod == "gecersiz_gecis"


def test_il_disi_elle_obek_kalici(v2db, conn, kim):
    satirlar = [y.satir(1, il="İzmir", ilce="Karşıyaka", mahalle="Bostanlı")]
    y.aktar(v2db, satirlar)
    no = conn.execute("SELECT is_no FROM is_emri").fetchone()[0]
    r = conn.execute("SELECT durum, triyaj_nedeni FROM is_emri").fetchone()
    assert tuple(r) == ("triyaj", "il_disi")
    obek_id = conn.execute("SELECT id FROM obek WHERE aktif=1 ORDER BY id LIMIT 1").fetchone()[0]
    a = akis.obek_ata(conn, no, obek_id, kim("operasyon"), _surum(conn, no))
    assert a["durum"] == "bekliyor" and a["obek_elle"] and "elle" in a["rozetler"] and a["obek"]["id"] == obek_id
    satirlar[0]["Son Açıklama"] = "yeniden yüklendi"
    y.aktar(v2db, satirlar)
    r = conn.execute("SELECT durum, obek_elle_id, triyaj_nedeni FROM is_emri").fetchone()
    assert tuple(r) == ("bekliyor", obek_id, None)                            # raporla ezilmedi


def test_randevu_kurallari_ve_teknik_sirasi(v2db, conn, kisi, kim, saat):
    nolar = _isler(v2db, conn, n=4)
    op = kim("operasyon")
    for bas, bit, kod in [("2026-09-30 14:00:00", "2026-09-30 13:00:00", "Bitiş başlangıçtan sonra"),
                          ("2026-09-30 10:00:00", "2026-09-30 15:00:00", "4 saatlik"),
                          ("2026-10-09 10:00:00", "2026-10-09 12:00:00", "7 gün"),
                          ("2026-09-29 10:00:00", "2026-09-29 12:00:00", "geçmişte")]:
        with pytest.raises(V2Hata) as e:
            akis.randevu(conn, nolar[0], op, bas, bit, False)
        assert e.value.kod == "randevu_gecersiz" and e.value.durum == 422 and kod in e.value.mesaj
    dilimler = [("2026-09-30 16:00:00", "2026-09-30 18:00:00"), ("2026-09-30 12:00:00", "2026-09-30 14:00:00"),
                ("2026-10-01 08:00:00", "2026-10-01 10:00:00")]
    for no, (bas, bit) in zip(nolar[:3], dilimler):
        akis.ata(conn, no, kisi["teknik1"], op, randevu={"bas": bas, "bit": bit, "teyitli": True})
    liste = gorunum.islerim(conn, kim("teknik1"))["isler"]
    assert [x["randevu"]["bas"] for x in liste] == sorted(b for b, _ in dilimler)   # İşlerim randevuya göre


def test_teknisyensiz_randevu(v2db, conn, kim):
    no = _isler(v2db, conn, n=2)[0]
    a = akis.randevu(conn, no, kim("operasyon"), "2026-10-01 10:00:00", "2026-10-01 12:00:00", True)
    assert (a["durum"], a["atanan"], a["kova"]) == ("randevulu", None, "atanmadi")
    assert a["randevu"] == {"bas": "2026-10-01 10:00:00", "bit": "2026-10-01 12:00:00", "teyitli": True, "kaynak": "biz"}
    a = akis.randevu(conn, no, kim("operasyon"), None, None, False)              # kaldır
    assert a["durum"] == "bekliyor" and a["randevu"] is None


def test_evde_yok_teyit_zorunlu(v2db, conn, kisi, kim):
    no = _isler(v2db, conn, n=2)[0]
    op = kim("operasyon")
    akis.ata(conn, no, kisi["teknik1"], op)
    a = akis.gecis(conn, no, "ulasilamadi", kim("teknik1"), istemci_id="e1")
    assert a["durum"] == "ulasilamadi" and a["evde_yok_sayisi"] == 1
    with pytest.raises(V2Hata) as e:
        akis.ata(conn, no, kisi["teknik1"], op)
    assert e.value.kod == "teyit_gerekli"
    a = akis.ata(conn, no, kisi["teknik1"], op,
                 randevu={"bas": "2026-10-01 10:00:00", "bit": "2026-10-01 12:00:00", "teyitli": True})
    assert a["durum"] == "atandi" and a["randevu"]["teyitli"]


def _ticket(conn, bina, durum="AÇIK", konu="SİNYAL"):
    cur = conn.execute("INSERT INTO ticket (konu, durum, bina_serial, olusturma, guncelleme, acilis) "
                       "VALUES (?,?,?, '2026-09-27 09:00:00','2026-09-27 09:00:00','2026-09-27')", (konu, durum, bina))
    conn.commit()
    return cur.lastrowid


def test_ticket_bagla_altyapi_cozulunce_doner(v2db, conn, kim):
    from saha import ticket as ticket_mod
    nolar = _isler(v2db, conn, satirlar=[y.satir(i, mahalle="Görükle") for i in (1, 2)])   # ikisi de öbekte
    op = kim("operasyon")
    a = akis.ticket_bagla(conn, nolar[0], op, yeni={"konu": "SİNYAL", "detay": "sinyal yok"})
    assert a["durum"] == "altyapi" and a["ticket"]["konu"] == "SİNYAL" and a["birincil"] == "ticketi_ac"
    tid = a["ticket"]["id"]
    ticket_mod.guncelle(conn, tid, {"durum": "ÇÖZÜLDÜ"}, op["id"])
    conn.commit()
    assert akis.ticket_degisti(conn, tid, op) == [nolar[0]]
    assert _durum(conn, nolar[0]) == "bekliyor"
    olay = conn.execute("SELECT notu FROM is_emri_olay WHERE is_no=? ORDER BY id DESC LIMIT 1", (nolar[0],)).fetchone()[0]
    assert "Ticket çözüldü" in olay
    # ticket'tan ayır
    a = akis.ticket_bagla(conn, nolar[1], op, ticket_id=_ticket(conn, None))
    a = akis.ticket_ayir(conn, nolar[1], op, a["surum"])
    assert a["durum"] == "bekliyor" and a["ticket"] is None
    # öbeksiz iş (Kontrol) ticket'tan ayrılınca Kontrol'e döner, 'bekliyor'a atlamaz
    y.aktar(v2db, [y.satir(i, mahalle="Görükle") for i in (1, 2)] + [y.satir(3, mahalle="Özlüce")])
    no3 = "400000003"
    assert _durum(conn, no3) == "triyaj"
    akis.ticket_bagla(conn, no3, op, ticket_id=_ticket(conn, None))
    assert akis.ticket_ayir(conn, no3, op)["durum"] == "triyaj"


def test_altyapi_engeli_409(v2db, conn, kisi, kim):
    b = conn.execute("SELECT bina_serial, location_id, mahalle FROM bina WHERE ilce='Nilüfer' AND location_id IS NOT NULL "
                     "AND pasif=0 LIMIT 1").fetchone()
    y.aktar(v2db, [y.satir(1, lokasyon=b["location_id"], mahalle=b["mahalle"])])
    no = conn.execute("SELECT is_no FROM is_emri").fetchone()[0]
    _ticket(conn, b["bina_serial"])
    op = kim("operasyon")
    with pytest.raises(V2Hata) as e:
        akis.ata(conn, no, kisi["teknik1"], op)
    assert e.value.kod == "altyapi_engeli" and "Teknisyen gönderilmez" in e.value.mesaj and "SİNYAL" in e.value.mesaj
    a = gorunum.ayrinti(conn, no, op)
    assert a["birincil"] == "ticketa_bagla" and a["binada_acik_ticket"] == 1 and "ticket" in a["rozetler"]
    a = akis.ata(conn, no, kisi["teknik1"], op, yine_de=True)
    assert a["durum"] == "atandi"


def test_telefonda_cozuldu_tekrar_yasak(v2db, conn, kim, saat):
    ilk = [y.satir(1, musteri_no="911111111")]
    y.aktar(v2db, ilk)
    no1 = conn.execute("SELECT is_no FROM is_emri").fetchone()[0]
    op = kim("operasyon")
    akis.gecis(conn, no1, "cozuldu", op, neden="telefonda_cozuldu", canli_test=True)
    saat.ilerlet(days=2)
    y.aktar(v2db, ilk + [y.satir(2, musteri_no="911111111")])          # aynı müşteri, aynı iş tipi
    no2 = conn.execute("SELECT is_no FROM is_emri WHERE is_no<>?", (no1,)).fetchone()[0]
    a = gorunum.ayrinti(conn, no2, op)
    assert "tekrar" in a["rozetler"]
    with pytest.raises(V2Hata) as e:
        akis.gecis(conn, no2, "cozuldu", op, neden="telefonda_cozuldu", canli_test=True)
    assert e.value.kod == "tekrar_ariza"
    with pytest.raises(V2Hata) as e:
        akis.teshis(conn, no2, op, "duzeldi", canli_test=True)
    assert e.value.kod == "tekrar_ariza"


def test_ofisten_kapat_neden_ve_canli_test(v2db, conn, kim):
    no = _isler(v2db, conn, n=1)[0]
    op = kim("operasyon")
    with pytest.raises(V2Hata) as e:
        akis.gecis(conn, no, "cozuldu", op)
    assert e.value.kod == "alan_eksik"
    with pytest.raises(V2Hata) as e:
        akis.gecis(conn, no, "cozuldu", op, neden="telefonda_cozuldu")
    assert "Canlı test" in e.value.mesaj
    a = akis.gecis(conn, no, "cozuldu", op, neden="mukerrer")
    assert a["durum"] == "cozuldu" and a["birincil"] is None


def test_bayi_isi_ve_boss_bagla_toplam_artmaz(v2db, conn, kim, saat):
    op = kim("operasyon")
    b = conn.execute("SELECT bina_serial FROM bina WHERE ilce='Nilüfer' AND mahalle='Görükle' AND pasif=0 LIMIT 1").fetchone()
    s = akis.bayi_olustur(conn, {"task_adi": "Bağlantı Problemi", "bina_serial": b[0], "musteri_no": "977777777",
                                 "musteri_adi": "Deneme Bayi Müşteri", "istemci_id": "b1"}, op)
    assert s["is_no"] == "B-260930-001" and s["is"]["kaynak"] == "bayi" and "bayi" in s["is"]["rozetler"]
    assert s["is"]["son24"] == "2026-10-01 10:00:00"                     # 24 s açılıştan
    assert akis.bayi_olustur(conn, {"task_adi": "Bağlantı Problemi", "bina_serial": b[0], "istemci_id": "b1"},
                             op)["is_no"] == "B-260930-001"               # aynı istemci_id: tek iş
    s2 = akis.bayi_olustur(conn, {"task_adi": "Modem Değişikliği", "adres": "Deneme Sk. 5",
                                  "mahalle_id": conn.execute("SELECT id FROM mahalle LIMIT 1").fetchone()[0]}, op)
    assert s2["is_no"] == "B-260930-002"
    with pytest.raises(V2Hata) as e:
        akis.bayi_olustur(conn, {"task_adi": "Modem Değişikliği"}, op)
    assert e.value.kod == "alan_eksik" and "Bina ya da adres" in e.value.mesaj
    with pytest.raises(V2Hata) as e:
        akis.boss_bagla(conn, "B-260930-001", "12345", op, None)
    assert e.value.kod == "task_no_gecersiz"
    akis.boss_bagla(conn, "B-260930-001", "412345678", op, None)
    toplam = conn.execute("SELECT COUNT(*) FROM is_emri").fetchone()[0]
    y.aktar(v2db, [y.satir("412345678", musteri_no="977777777"), y.satir(5)])
    assert conn.execute("SELECT COUNT(*) FROM is_emri").fetchone()[0] == toplam + 1       # yalnız y.satir(5) yeni
    r = conn.execute("SELECT boss_durum, kaynak FROM is_emri WHERE is_no='B-260930-001'").fetchone()
    assert tuple(r) == ("Açık", "bayi")                                                     # aynı satır güncellendi
    with pytest.raises(V2Hata) as e:
        akis.boss_bagla(conn, "B-260930-002", "412345678", op, None)
    assert e.value.kod == "boss_no_kullanilmis"


def test_bayi_bagsiz_ofisten_kapaninca_kapandi(v2db, conn, kim):
    op = kim("operasyon")
    b = conn.execute("SELECT bina_serial FROM bina WHERE pasif=0 LIMIT 1").fetchone()
    no = akis.bayi_olustur(conn, {"task_adi": "Modem Değişikliği", "bina_serial": b[0]}, op)["is_no"]
    a = akis.gecis(conn, no, "cozuldu", op, neden="musteri_vazgecti")
    assert a["durum"] == "kapandi" and a["kapanis_nedeni"] == "musteri_vazgecti"


def test_kanal_grubu_5_ornek():
    assert [akis.kanal_grubu(x) for x in ("GLOBAL CC", "DEHANET ECM", "DEHA TEL INS", "TURKCELL KURUMSAL", None,
                                           "GUNEYNET ECM")] == ["global", "dehanet", "dehanet", "kurumsal", "bos",
                                                                "diger_bayi"]
    assert akis.serit_bul("TV+ Arıza") == ("BTK", 6) and akis.serit_bul("Bağlantı Problemi") == ("BTK", 12)
    assert akis.serit_bul("Doping Arıza Bildirimi") == ("BTK", 24) and akis.serit_bul("Modem Değişikliği") == ("SAHA", None)
    assert akis.serit_bul("Turksat Cihaz İade - Yerinde Hizmet")[0] == "LOJISTIK"


def test_boss_ileri_kurali(v2db, conn, kisi):
    satirlar = [y.satir(1, ekip="Ali Deneme Ekibi")]                    # teknik1'in boss_ekip'i
    y.aktar(v2db, satirlar)
    r = conn.execute("SELECT durum, atanan_id, atama_kaynagi FROM is_emri").fetchone()
    assert tuple(r) == ("atandi", kisi["teknik1"], "boss")
    satirlar[0]["Task Durumu"] = "Konum Paylaşıldı"
    y.aktar(v2db, satirlar)
    assert conn.execute("SELECT durum FROM is_emri").fetchone()[0] == "yolda"
    satirlar[0]["Task Durumu"] = "Açık"
    y.aktar(v2db, satirlar)
    assert conn.execute("SELECT durum FROM is_emri").fetchone()[0] == "yolda"          # geri gitmez
    satirlar[0]["Task Durumu"] = "Başlandı"
    y.aktar(v2db, satirlar)
    assert conn.execute("SELECT durum FROM is_emri").fetchone()[0] == "sahada"


def test_boss_istisnalari_askida_merkeze(v2db, conn):
    y.aktar(v2db, [y.satir(1, durum="Askıya alındı", aski="Abone kaynaklı"),
                   y.satir(2, durum="Merkeze gönderildi", **{"Merkeze Gönder Statüsü": "SİNYAL YOK"})])
    d = {r[0][-1]: (r[1], r[2]) for r in conn.execute("SELECT is_no, durum, askida_neden FROM is_emri")}
    assert d["1"] == ("askida", "Abone kaynaklı") and d["2"] == ("merkeze", "SİNYAL YOK")


def test_boss_ekip_eslesme_ve_esle_ucu(v2db, conn, kisi, kim):
    from operasyon.v2 import api
    y.aktar(v2db, [y.satir(i, ekip="MERKEZ EKIP 3") for i in range(1, 4)] + [y.satir(4)])
    liste = api.boss_ekip_listesi(conn)
    assert liste["eslesmemis"] == [{"boss_ekip": "MERKEZ EKIP 3", "is": 3}]
    s = akis.boss_ekip_esle(conn, "MERKEZ EKIP 3", kisi["teknik2"], kim("operasyon"))
    assert s["atanan"] == 3
    assert conn.execute("SELECT COUNT(*) FROM is_emri WHERE atanan_id=? AND atama_kaynagi='boss'",
                        (kisi["teknik2"],)).fetchone()[0] == 3
    assert conn.execute("SELECT boss_ekip FROM kullanici WHERE id=?", (kisi["teknik2"],)).fetchone()[0] == "MERKEZ EKIP 3"
    assert api.boss_ekip_listesi(conn)["eslesmemis"] == []
    assert conn.execute("SELECT COUNT(*) FROM yonetim_kaydi WHERE eylem='boss_ekip'").fetchone()[0] == 1


def test_surum_409(v2db, conn, kisi, kim):
    no = _isler(v2db, conn, n=2)[0]
    op, yon = kim("operasyon"), kim("yonetici")
    eski = _surum(conn, no)
    akis.ata(conn, no, kisi["teknik1"], yon, surum=eski)
    with pytest.raises(V2Hata) as e:
        akis.randevu(conn, no, op, "2026-10-01 10:00:00", "2026-10-01 12:00:00", True, surum=eski)
    assert e.value.kod == "guncel_degil" and e.value.durum == 409
    assert e.value.ek["degistiren"] == yon["ad"] and e.value.ek["guncel"]["atanan"]["id"] == kisi["teknik1"]
    assert "siz bakarken değişti" in e.value.mesaj


def test_toplu_ata_geri_al(v2db, conn, kisi, kim):
    from operasyon.v2 import obek
    op = kim("operasyon")
    nolar = _isler(v2db, conn, satirlar=[y.satir(i, mahalle="Görükle") for i in range(1, 5)])
    oid = conn.execute("SELECT obek_id FROM is_emri LIMIT 1").fetchone()[0]
    obek.guncelle(conn, oid, op, obek.surum(conn), sahip_id=kisi["teknik1"])
    satirlar = [r for r in conn.execute("SELECT is_no, surum, oneri_teknik_id, oneri_bas FROM is_emri")]
    assert all(r["oneri_teknik_id"] == kisi["teknik1"] and r["oneri_bas"] for r in satirlar)
    s = akis.oneri_onayla(conn, {r["is_no"]: r["surum"] for r in satirlar}, op)
    assert sorted(s["atanan"]) == nolar and s["atlanan"] == []
    # biri bu arada değişti: geri alınmaz
    akis.not_ekle(conn, nolar[0], "not", op)
    akis.randevu(conn, nolar[0], op, "2026-10-01 10:00:00", "2026-10-01 12:00:00", True)
    g = akis.toplu_geri_al(conn, s["toplu_id"], op)
    assert sorted(g["geri_alinan"]) == nolar[1:] and g["atlanan"] == [{"is_no": nolar[0], "kod": "guncel_degil"}]
    assert [_durum(conn, n) for n in nolar[1:]] == ["bekliyor"] * 3
    with pytest.raises(V2Hata) as e:
        akis.toplu_geri_al(conn, s["toplu_id"], kim("yonetici"))        # başkası geri alamaz
    assert e.value.kod == "geri_alinamaz"


def test_toplu_geri_al_10dk(v2db, conn, kisi, kim, saat):
    op = kim("operasyon")
    nolar = _isler(v2db, conn, satirlar=[y.satir(i, mahalle="Görükle") for i in range(1, 3)])
    s = akis.toplu_ata(conn, [{"is_no": n, "teknik_id": kisi["teknik1"]} for n in nolar], op)
    assert sorted(s["atanan"]) == nolar
    saat.ilerlet(minutes=11)
    with pytest.raises(V2Hata) as e:
        akis.toplu_geri_al(conn, s["toplu_id"], op)
    assert e.value.kod == "sure_doldu"
    assert [_durum(conn, n) for n in nolar] == ["atandi", "atandi"]


def test_tek_geri_al_10dk(v2db, conn, kisi, kim, saat):
    no = _isler(v2db, conn, n=1)[0]
    op = kim("operasyon")
    a = akis.ata(conn, no, kisi["teknik1"], op)
    olay = a["olaylar"][0]["id"]
    with pytest.raises(V2Hata):
        akis.geri_al(conn, no, olay, kim("yonetici"))                  # başkası geri alamaz
    saat.ilerlet(minutes=11)
    with pytest.raises(V2Hata) as e:
        akis.geri_al(conn, no, olay, op)
    assert e.value.kod == "sure_doldu"
    saat.ilerlet(minutes=-10)
    a = akis.geri_al(conn, no, olay, op)
    assert a["durum"] == "bekliyor" and a["atanan"] is None


def test_istemci_id_idempotent(v2db, conn, kisi, kim):
    no = _isler(v2db, conn, n=1)[0]
    akis.ata(conn, no, kisi["teknik1"], kim("operasyon"))
    tek = kim("teknik1")
    akis.gecis(conn, no, "yolda", tek, istemci_id="ayni", zaman_="2026-09-30 10:20:00")
    akis.gecis(conn, no, "yolda", tek, istemci_id="ayni")
    assert conn.execute("SELECT COUNT(*) FROM is_emri_olay WHERE is_no=? AND istemci_id='ayni'", (no,)).fetchone()[0] == 1
    akis.gecis(conn, no, "sahada", tek, istemci_id="s1")
    a = akis.gecis(conn, no, "yolda", tek, istemci_id="gec-gelen")     # çevrimdışı kuyruktan geç gelen
    assert a["durum"] == "sahada"                                       # durum geri gitmez, yalnız olay
    assert conn.execute("SELECT COUNT(*) FROM is_emri_olay WHERE istemci_id='gec-gelen'").fetchone()[0] == 1
    # sahadaki iş aynı tekniğe "yeniden atanamaz" (geri gitmek olurdu); başkasına verilebilir
    with pytest.raises(V2Hata) as e:
        akis.ata(conn, no, kisi["teknik1"], kim("operasyon"))
    assert e.value.kod == "gecersiz_gecis"
    a = akis.ata(conn, no, kisi["teknik2"], kim("operasyon"))
    assert a["durum"] == "atandi" and a["atanan"]["id"] == kisi["teknik2"]
    r = conn.execute("SELECT yolda_zamani, sahada_zamani FROM is_emri WHERE is_no=?", (no,)).fetchone()
    assert tuple(r) == (None, None)                                     # yeni teknisyenin yolu kendi basışıyla
    # başkasına geçen iş: 404
    with pytest.raises(V2Hata) as e:
        akis.gecis(conn, no, "cozuldu", tek, istemci_id="x9", evde_miydi=True)
    assert e.value.kod == "is_yok" and e.value.durum == 404


def test_teknik_bitti_secenekleri(v2db, conn, kisi, kim):
    nolar = _isler(v2db, conn, n=3)
    op, tek = kim("operasyon"), kim("teknik1")
    for no in nolar:
        akis.ata(conn, no, kisi["teknik1"], op)
    a = akis.gecis(conn, nolar[0], "askida", tek, istemci_id="m1", evde_miydi=True)            # malzeme
    assert a["durum"] == "askida" and a["askida_neden"] == "Malzeme bekleniyor" and a["uyanma"]
    a = akis.gecis(conn, nolar[1], "triyaj", tek, istemci_id="t1", evde_miydi=False)           # altyapı sorunu
    assert a["durum"] == "triyaj" and a["triyaj_nedeni"] == "altyapi_supheli"
    assert "musteri_adi" not in a and "musteri_no" not in a and not a["izinler"]["durumlar"]    # yanıt kırpılmış
    with pytest.raises(V2Hata):
        gorunum.ayrinti(conn, nolar[1], tek)                                                  # artık onun değil
    a = akis.gecis(conn, nolar[2], "atandi", tek, istemci_id="b1",
                   randevu={"bas": "2026-10-01 10:00:00", "bit": "2026-10-01 12:00:00"})      # başka gün
    assert a["durum"] == "atandi" and a["randevu"]["teyitli"] and a["randevu"]["bas"] == "2026-10-01 10:00:00"


def test_askiya_al_uyandir_ve_ust_sinir(v2db, conn, kim, saat):
    no = _isler(v2db, conn, n=1)[0]
    op = kim("operasyon")
    with pytest.raises(V2Hata) as e:
        akis.gecis(conn, no, "askida", op, neden="malzeme", uyanma="2026-10-02 10:00:00")    # malzeme ≤ 2 s (BTK)
    assert e.value.kod == "uyanma_gecersiz"
    with pytest.raises(V2Hata) as e:
        akis.gecis(conn, no, "askida", op, neden="abone")
    assert "Uyanma zamanı gerekli" in e.value.mesaj
    a = akis.gecis(conn, no, "askida", op, neden="abone", uyanma="2026-10-02 10:00:00")
    assert a["durum"] == "askida" and a["birincil"] == "uyandir"
    saat.ayarla("2026-10-02 10:05:00")
    assert akis.uyananlari_isle(conn, saat.an) == [no]
    r = conn.execute("SELECT durum, uyanma FROM is_emri").fetchone()
    assert tuple(r) == ("bekliyor", None)
    assert conn.execute("SELECT tur FROM is_emri_olay ORDER BY id DESC LIMIT 1").fetchone()[0] == "uyandi"


def test_teshis_merdiveni(v2db, conn, kisi, kim, saat):
    no = _isler(v2db, conn, n=1)[0]
    op = kim("operasyon")
    akis.ata(conn, no, kisi["teknik1"], op)
    akis.gecis(conn, no, "ulasilamadi", kim("teknik1"), istemci_id="u1")
    bantlar = {b["bant"]: [x["is_no"] for x in b["isler"]] for b in gorunum.aranacak_bantlari(conn, saat.an, op)}
    assert no in bantlar["ulasilamadi"]
    # EK-12.4 merdiveni (KARMA-2'nin +2 s / 17:30 bantlarının yerine): A1 → ≥3 s → A2 → ertesi gün A3 …
    a = akis.teshis(conn, no, op, "cevapsiz")
    assert a["uyanma"] == "2026-09-30 13:00:00"                         # A1 10:00 → A2 en erken 13:00
    assert a["boss_giden"]["alanlar"]["talep_ulasamama_sms"] is True    # her ulaşılamayanda BOSS SMS'i zorunlu
    assert a["merdiven"]["gecerli"] == 1 and not a["merdiven"]["tamam"]
    saat.ilerlet(hours=3)
    a = akis.teshis(conn, no, op, "kapali")
    assert a["uyanma"] == "2026-10-01 10:00:00"                         # 1. gün doldu → ertesi gün pencere başı
    a = akis.teshis(conn, no, op, "simdi_evde")
    assert a["durum"] == "randevulu" and a["randevu"]["teyitli"] and a["randevu"]["bas"] == "2026-09-30 13:00:00"
    assert a["merdiven"]["ulasildi"]


def test_trigger_listesi_akis_ile_ayni(v2db, conn):
    try:
        from saha import sema_v2
        assert akis.trigger_sql() == list(sema_v2.is_emri_tetikleyicileri(akis.DURUMLAR, akis.KAYNAKLAR))
        assert tuple(akis.DURUMLAR) == tuple(sema_v2.IS_DURUMLARI)
    except ImportError:
        pass
    y.aktar(v2db, y.standart(1))
    import sqlite3
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE is_emri SET durum='hacker'")
    assert set(akis.KOVALAR) == set(akis.DURUMLAR)
