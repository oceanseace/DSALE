"""EK-3 · BTK saati abone kaynaklı askıda durur (+ EK-12.3 geçerlilik). Saat dondurulur (30.09.2026 10:00)."""
from __future__ import annotations

import datetime as dt
import json

from operasyon.testler import yardim as y
from operasyon.v2 import akis, aski, gorunum, kurallar

NO = "400000001"


def _ayar(conn, anahtar, deger):
    conn.execute("INSERT INTO ayar(anahtar, deger) VALUES(?,?) ON CONFLICT(anahtar) DO UPDATE SET deger=excluded.deger",
                 (anahtar, json.dumps(deger) if not isinstance(deger, str) else deger))
    conn.commit()


def _ek12(conn):
    _ayar(conn, "btk_durduran_aski", kurallar.VARSAYILAN["btk_durduran_aski"])


def test_rapordan_aralik_acilir_kapanir_net_saat(v2db, conn, kim, saat):
    """Rapor 'Askıya alındı' → aralık (yaklaşık, raporun indirildiği an); askıdan çıkınca kapanır; net BTK saati."""
    s = [y.satir(1, task="Bağlantı Problemi", baslangic="2026-09-30 08:00:00", durum="Askıya alındı",
                 aski="Abone kaynaklı")]
    y.aktar(v2db, s, dosya_zamani="2026-09-30T06:58:00Z")                 # 09:58 TR'de indirilmiş
    r = conn.execute("SELECT * FROM is_aski").fetchone()
    assert (r["baslama"], r["bitis"], r["kaynak"], r["durdurur"]) == ("2026-09-30 09:58:00", None, "boss", 1)
    saat.ilerlet(hours=3, minutes=20)                                      # 13:20
    s[0]["Task Durumu"] = "Açık"
    y.aktar(v2db, s, dosya_zamani="2026-09-30T10:18:00Z")                 # 13:18 TR
    r = conn.execute("SELECT * FROM is_aski").fetchone()
    assert r["bitis"] == "2026-09-30 13:18:00"
    a = gorunum.ayrinti(conn, NO, kim("operasyon"))
    assert a["aski_durdu_dk"] == 200 and a["aski"][0]["yaklasik"] and a["aski"][0]["sure_dk"] == 200
    # BTK hedefi 08:00 + 12 s = 20:00 → net 23:20; geçen net = 5 s 20 dk − 3 s 20 dk = 2 s
    assert a["btk_hedef"] == "2026-09-30 20:00:00" and a["btk_hedef_net"] == "2026-09-30 23:20:00"
    assert a["btk_net_gecen_dk"] == 120 and not a["btk_durdu"]
    assert a["son24"] == "2026-10-01 08:00:00"                             # 24 s söz takvim saatidir (varsayılan)


def test_iki_aralik_ve_surerken_net(v2db, conn, kim, saat):
    y.aktar(v2db, [y.satir(1, baslangic="2026-09-30 06:00:00")])
    op = kim("operasyon")
    akis.gecis(conn, NO, "askida", op, neden="abone", uyanma="2026-09-30 12:00:00")
    # abone askısı arama kaydı olmadan GEÇERSİZ (EK-12.3): saat durmaz → yalnız kuralı kapatarak iki aralığı ölçeriz
    _ayar(conn, "aski_gecerlilik", {"acik": False})
    aski.kurali_yeniden_uygula(conn)
    conn.commit()
    saat.ilerlet(hours=1)                                                  # 11:00 → uyandır
    akis.gecis(conn, NO, "bekliyor", op)
    saat.ilerlet(hours=1)                                                  # 12:00 → yine askı
    akis.gecis(conn, NO, "askida", op, neden="abone", uyanma="2026-09-30 18:00:00")
    saat.ilerlet(minutes=30)                                               # 12:30, ikinci aralık sürüyor
    a = gorunum.ayrinti(conn, NO, op)
    assert [x["sure_dk"] for x in a["aski"]] == [60, 30] and a["aski_durdu_dk"] == 90
    assert a["btk_durdu"] is True and a["btk_net_gecen_dk"] == 6 * 60 + 30 - 90
    satir = next(x for x in gorunum.isler_yaniti(conn, op)["isler"] if x["is_no"] == NO)
    assert satir["btk_durdu"] and satir["btk_hedef_net"] == "2026-09-30 19:30:00"
    saat.ilerlet(hours=2)                                                  # askı sürerken net geçen donar
    assert gorunum.ayrinti(conn, NO, op)["btk_net_gecen_dk"] == 6 * 60 + 30 - 90


def test_durdurmayan_nedenler_ve_ayar(v2db, conn, kim, saat):
    y.aktar(v2db, [y.satir(1, durum="Askıya alındı", aski="TT kaynaklı"),
                   y.satir(2, durum="Askıya alındı", aski="Abone kaynaklı (akşam araması)")])
    d = {r["is_no"][-1]: r["durdurur"] for r in conn.execute("SELECT is_no, durdurur FROM is_aski")}
    assert d == {"1": 0, "2": 1}                                           # TT kaynaklı teyit bekliyor → durdurmaz
    _ayar(conn, "btk_durduran_aski", ["abone", "tt kaynakli"])
    aski.kurali_yeniden_uygula(conn)
    conn.commit()
    d = {r["is_no"][-1]: r["durdurur"] for r in conn.execute("SELECT is_no, durdurur FROM is_aski")}
    assert d == {"1": 1, "2": 1}


def test_son24_ayari(v2db, conn, kim, saat):
    y.aktar(v2db, [y.satir(1, baslangic="2026-09-30 09:00:00", durum="Askıya alındı", aski="Abone kaynaklı")],
            dosya_zamani="2026-09-30T07:00:00Z")
    saat.ilerlet(hours=2)
    op = kim("operasyon")
    assert gorunum.ayrinti(conn, NO, op)["son24"] == "2026-10-01 09:00:00"
    _ayar(conn, "son24_askida_durur", "true")
    assert gorunum.ayrinti(conn, NO, op)["son24"] == "2026-10-01 11:00:00"


def test_elle_abone_askisi_gecerlilik(v2db, conn, kim, saat):
    """EK-12.3: elle abone askısı Webphone + SMS + 2 farklı gün aranmadıkça saati durdurmaz; uyarı çıkar."""
    y.aktar(v2db, [y.satir(1, baslangic="2026-09-30 09:00:00")])
    op = kim("operasyon")
    a = akis.gecis(conn, NO, "askida", op, neden="abone", uyanma="2026-10-01 11:00:00")
    assert a["aski"][-1]["durdurur"] is False and a["aski_uyari"].startswith("Geçersiz askı")
    akis.arama_kaydet(conn, NO, op, "ulasilamadi", sms=True)               # 1. gün
    saat.ayarla("2026-10-01 10:30:00")
    a = akis.arama_kaydet(conn, NO, op, "mesgul_kapali", sms=True)         # 2. gün → geçerli
    assert a["aski"][-1]["durdurur"] is True and a["aski_uyari"] is None
    # Webphone dışı arama askı hakkı vermez
    assert kurallar.abone_aski_gecerli([{"zaman": "2026-09-30 10:00:00", "sms": True, "webphone": False},
                                        {"zaman": "2026-10-01 10:00:00", "sms": True, "webphone": False}],
                                       kurallar.VARSAYILAN["aski_gecerlilik"])[0] is False


def test_boss_askisina_guven_kapali(v2db, conn):
    _ayar(conn, "aski_gecerlilik", {"boss_askisina_guven": False})
    y.aktar(v2db, [y.satir(1, durum="Askıya alındı", aski="Abone kaynaklı"),
                   y.satir(2, durum="Askıya alındı", aski="Genel arıza")])
    _ek12(conn)
    aski.kurali_yeniden_uygula(conn)
    d = {r["is_no"][-1]: r["durdurur"] for r in conn.execute("SELECT is_no, durdurur FROM is_aski")}
    assert d == {"1": 0, "2": 1}                                            # genel arıza abone değil → durdurur


def test_hesap_acilistan_once_baslayan_aralik():
    an = dt.datetime(2026, 9, 30, 12, 0)
    h = aski.hesap([{"baslama": "2026-09-30 07:00:00", "bitis": "2026-09-30 09:00:00", "durdurur": 1}],
                   "2026-09-30 08:00:00", "2026-09-30 20:00:00", an)
    assert h["durdu_dk"] == 60 and h["btk_net_gecen_dk"] == 180 and h["btk_hedef_net"] == "2026-09-30 21:00:00"
