"""BOSS canlı eşitleme (eklenti → /api/boss/esitle): eşleme kodu, durum eşlemesi, kapanış kuralları."""
from __future__ import annotations
import pytest

from operasyon.testler import yardim as y
from operasyon.v2 import boss


def _gorev(i: int, *, durum="Randevusuz", task="Bağlantı Problemi", mahalle="Görükle", ilce="Nilüfer", **ek) -> dict:
    no = f"{400000000 + i}"
    g = {"task_no": no, "task_adi": task, "durum": durum, "musteri_no": f"9{no[-8:]}", "musteri_adi": "Deneme",
         "adres": f"DENEME APT. {mahalle} Mh. Test Sk. No:{no[-3:]} {ilce}", "il": "Bursa", "ilce": ilce,
         "acilis": "2026-09-30 09:00:00", "satis_kanali": "GLOBAL CC", "telefonlar": ["0532 111 22 33"]}
    g.update(ek)
    return g


def _durumlar(conn) -> dict:
    return {r[0]: r[1] for r in conn.execute("SELECT is_no, durum FROM is_emri")}


def test_eslesme_kodu_kalici_ve_dogrulanir(v2db):
    kod = boss.eslesme_kodu()
    assert len(kod) == 9 and kod[4] == "-"
    assert boss.eslesme_kodu() == kod
    assert boss.kod_dogru(kod) and boss.kod_dogru(kod.replace("-", " "))
    assert not boss.kod_dogru("0000-0000") or kod == "0000-0000"
    yeni = boss.eslesme_kodu(yenile=True)
    assert boss.kod_dogru(yeni) and (yeni == kod or not boss.kod_dogru(kod))


@pytest.mark.skip(reason="Tek iş havuzu (2026-10): kurulum/2. donanım çıkarma ve öbeksiz→Kontrol kuralı kaldırıldı")
def test_esitle_durum_eslemesi_ve_kapanis(v2db, conn):
    gorevler = [_gorev(1), _gorev(2, durum="Randevu alındı", randevu_bas="2026-10-01 10:00:00",
                                  randevu_bit="2026-10-01 12:00:00"),
                _gorev(3, durum="Ertelendi"), _gorev(4, durum="Merkeze gönderildi"),
                _gorev(5, task="Fiber Kurulum"), _gorev(6, durum="Açık", mahalle="Dumlupınar")]
    s = boss.esitle(y.fabrika(v2db), {"gorevler": gorevler, "tam": True})
    assert s["acik_gelen"] == 6 and s["fark"]["yeni"] == 5 and s["cikarilan"]["kurulum"] == 1
    d = _durumlar(conn)
    assert d["400000001"] == "bekliyor"
    assert d["400000002"] == "randevulu"
    assert d["400000003"] == "askida"
    assert d["400000004"] == "merkeze"
    assert "400000005" not in d                                    # kurulum → Yeni Müşteri (dağıtım), iş değil
    assert conn.execute("SELECT tur FROM dagitim_is WHERE task_no='400000005'").fetchone()[0] == "yeni"
    assert conn.execute("SELECT musteri_tel FROM is_emri WHERE is_no='400000001'").fetchone()[0] == "5321112233"  # tel varsayılan açık (sahibin kararı)

    # Aynı görüntü: değişiklik yok, aktarım kaydı açılmaz
    n = conn.execute("SELECT COUNT(*) FROM ie_aktarim").fetchone()[0]
    s2 = boss.esitle(y.fabrika(v2db), {"gorevler": gorevler, "tam": True})
    assert s2["fark"]["yeni"] == 0 and "aktarim_id" not in s2
    assert conn.execute("SELECT COUNT(*) FROM ie_aktarim").fetchone()[0] == n

    # Kapalı durum her zaman kapatır; eksik görüntüde listeden düşen iş KAPANMAZ
    eksik = [_gorev(1, durum="Tamamlandı"), _gorev(2, durum="Randevu alındı", randevu_bas="2026-10-01 10:00:00",
                                                   randevu_bit="2026-10-01 12:00:00")]
    boss.esitle(y.fabrika(v2db), {"gorevler": eksik, "tam": False})
    d = _durumlar(conn)
    assert d["400000001"] == "kapandi" and d["400000003"] == "askida" and d["400000006"] == "bekliyor"
    # Tam görüntüde düşen iş kapanır
    boss.esitle(y.fabrika(v2db), {"gorevler": eksik, "tam": True})
    d = _durumlar(conn)
    assert d["400000003"] == "kapandi" and d["400000006"] == "kapandi" and d["400000002"] == "randevulu"

    durum = boss.durum(conn)
    assert durum["bagli"] is True and durum["acik_sayisi"] == 1 and durum["durum_sayilari"] == {"randevulu": 1}


def test_telefon_yalniz_ayar_acikken(v2db, conn):
    conn.execute("INSERT INTO ayar(anahtar, deger) VALUES('musteri_tel','acik') "
                 "ON CONFLICT(anahtar) DO UPDATE SET deger='acik'")
    conn.commit()
    boss.esitle(y.fabrika(v2db), {"gorevler": [_gorev(1)], "tam": False})
    assert conn.execute("SELECT musteri_tel FROM is_emri WHERE is_no='400000001'").fetchone()[0] == "5321112233"


def test_il_ilce_adresten(v2db, conn):
    g = _gorev(1, il=None, ilce=None, adres="DENEME APT. Görükle Mh. Test Sk. No:1 NİLÜFER/BURSA")
    boss.esitle(y.fabrika(v2db), {"gorevler": [g], "tam": False})
    r = conn.execute("SELECT il, ilce, durum FROM is_emri WHERE is_no='400000001'").fetchone()
    assert (r["il"], r["ilce"]) == ("Bursa", "Nilüfer") and r["durum"] == "bekliyor"


def test_uc_kod_ile_ve_kodsuz(istemci, v2db, jeton, kisi):
    kod = boss.eslesme_kodu()
    govde = {"gorevler": [_gorev(1)], "tam": False}
    assert istemci.post("/api/boss/esitle", json=govde).status_code == 401
    y_ = istemci.post("/api/boss/esitle", json=govde, headers={"X-Eslesme-Kodu": "1111-2222"})
    assert y_.status_code == 401 and y_.json()["detail"]["kod"] == "eslesme_yanlis" if "detail" in y_.json() \
        else y_.json()["kod"] == "eslesme_yanlis"
    y_ = istemci.post("/api/boss/esitle", json=govde, headers={"X-Eslesme-Kodu": kod})
    assert y_.status_code == 200, y_.text
    assert y_.json()["fark"]["yeni"] == 1
    op = jeton(kisi["operasyon"])
    d = istemci.get("/api/boss/durum", headers=op).json()
    assert d["bagli"] and d["acik_sayisi"] == 1
    assert istemci.get("/api/boss/eslesme-kodu", headers=op).json()["kod"] == kod
    assert istemci.get("/api/boss/eslesme-kodu", headers=jeton(kisi["teknik1"])).status_code == 403


def test_boss_durumu_kesin_kaynak_ic_durum_uzlasir(v2db, conn, kisi, kim):
    """BOSS'un son statüsü iç durumu geçersiz kılar (ör. uygulamada "yolda" kalmış iş BOSS'ta askıya alındı → askıda);
    BOSS geri giderse iç durum da geri alınır (olay notuyla). BOSS statüsü değişmeden uygulamada ileri giden iş
    (teknisyen "yoldayım" dedi) eşitlemede geri alınmaz."""
    from operasyon.v2 import akis
    f = y.fabrika(v2db)
    boss.esitle(f, {"gorevler": [_gorev(1, durum="Randevu alındı")], "tam": False})
    akis.ata(conn, "400000001", kisi["teknik1"], kim("operasyon"))
    conn.execute("UPDATE is_emri SET durum='yolda' WHERE is_no='400000001'")       # uygulamada teknisyen yola çıktı
    conn.commit()

    def esitle(durum):
        boss.esitle(y.fabrika(v2db), {"gorevler": [_gorev(1, durum=durum)], "tam": False})
        return _durumlar(conn)["400000001"]

    def son_not():
        return conn.execute("SELECT notu FROM is_emri_olay WHERE is_no='400000001' ORDER BY id DESC LIMIT 1").fetchone()[0]

    assert esitle("Randevu alındı") == "yolda", "BOSS değişmedi: uygulamanın ileri durumu korunur"
    assert esitle("Askıya alındı") == "askida" and "askıya alındı" in son_not()
    assert esitle("Randevu alındı") == "atandi" and "askıdan çıktı" in son_not()
    assert esitle("Başlandı") == "sahada"
    assert esitle("Konum paylaşıldı") == "yolda" and "geri gitti" in son_not()
    assert esitle("Açık") == "atandi" and "geri gitti" in son_not()
    assert esitle("Ertelendi") == "askida" and "ertelendi" in son_not()
    assert esitle("Merkeze gönderildi") == "askida", "askıdaki iş merkeze geçmez (askı korunur)"
    assert esitle("Başlandı") == "sahada"
    assert esitle("Merkeze gönderildi") == "merkeze"
