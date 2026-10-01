"""Takip paneli ölçüleri (F11, F15, F17; spec §3.5, §3.6, §5.3.6). Saat dondurulur; kişisel veri yok."""
from __future__ import annotations

import datetime as dt

from operasyon.testler import yardim as y
from operasyon.v2 import akis, siralama, takip


def _adim(t, ad):
    return next(a for a in t["hiz_hatti"] if a["adim"] == ad)


def test_atama_suresi_dondurulmus_saat(v2db, conn, kisi, kim, saat):
    """F17: 10:00 aktarım, 10:09 atama → 9 dk; BOSS'ta atanmış iş ölçüye girmez; yeniden açılan iş saati sıfırlar."""
    op = kim("operasyon")
    satirlar = [y.satir(1, baslangic="2026-09-30 10:00:00"),
                y.satir(2, baslangic="2026-09-30 10:00:00", ekip="Ali Deneme Ekibi"),     # BOSS ataması
                y.satir(3, baslangic="2026-09-30 08:00:00")]                             # devralınan birikim
    y.aktar(v2db, satirlar)
    saat.ilerlet(minutes=9)
    akis.ata(conn, "400000001", kisi["teknik2"], op)
    akis.ata(conn, "400000003", kisi["teknik2"], op)
    a = _adim(takip.takip(conn, saat.an), "atama")
    assert (a["n"], a["medyan_dk"], a["hedefte_oran"], a["hedef_dk"]) == (1, 9.0, 1.0, 15)
    # yeniden açılan iş: saat raporda yeniden göründüğü andan başlar
    saat.ilerlet(minutes=11)                                                          # 10:20 — listeden düştü
    y.aktar(v2db, satirlar[1:])
    saat.ilerlet(minutes=20)                                                          # 10:40 — yeniden açıldı
    satirlar[0]["Son Açıklama"] = "yeniden"
    y.aktar(v2db, satirlar)
    saat.ilerlet(minutes=12)
    akis.ata(conn, "400000001", kisi["teknik2"], op)
    a = _adim(takip.takip(conn, saat.an), "atama")
    assert (a["n"], a["medyan_dk"]) == (1, 12.0)
    assert takip.takip(conn, saat.an)["manset"]["atanmamis"] == 0


def test_hiz_hatti_adimlari(v2db, conn, kisi, kim, saat):
    y.aktar(v2db, [y.satir(1, baslangic="2026-09-30 09:40:00")])
    tek = kim("teknik1")
    saat.ilerlet(minutes=5)
    akis.ata(conn, "400000001", kisi["teknik1"], kim("operasyon"))
    saat.ilerlet(minutes=3)
    akis.teknik_gordu(conn, tek, ["400000001"])
    saat.ilerlet(minutes=20)
    akis.gecis(conn, "400000001", "yolda", tek, istemci_id="y1")
    saat.ilerlet(minutes=30)
    akis.gecis(conn, "400000001", "sahada", tek, istemci_id="s1")
    saat.ilerlet(minutes=50)
    akis.gecis(conn, "400000001", "cozuldu", tek, istemci_id="c1", evde_miydi=True)
    t = takip.takip(conn, saat.an)
    adimlar = [a["adim"] for a in t["hiz_hatti"]]
    assert adimlar == ["boss_sistem", "atama", "teknik_gordu", "boss_islendi", "yola_cikis", "yol", "saha",
                       "kapanis_dogrulama", "uctan_uca"]
    assert _adim(t, "boss_sistem")["medyan_dk"] == 20.0                   # BOSS'ta açılış 09:40 → sistemde 10:00
    assert _adim(t, "teknik_gordu")["medyan_dk"] == 3.0
    assert _adim(t, "yol")["medyan_dk"] == 30.0 and _adim(t, "yol")["hedef_dk"] == 60
    assert _adim(t, "saha")["medyan_dk"] == 50.0
    assert _adim(t, "uctan_uca")["medyan_dk"] == 128.0
    assert t["uyum24"]["n"] == 1 and t["uyum24"]["oran"] == 1.0


def test_kapasite_modu(v2db, conn, kisi, kim, saat):
    y.aktar(v2db, [y.satir(i, mahalle="Görükle") for i in range(1, 21)])
    m = siralama.mod(conn, saat.an)
    assert m["aktif"] == 0 and m["mod"] == "asiri_yuk" and m["talep"] == 20 and m["esnek_oneri"] == 2
    akis.ata(conn, "400000001", kisi["teknik1"], kim("operasyon"))            # bugün işi olan 1 teknik → 15
    m = siralama.mod(conn, saat.an)
    assert (m["aktif"], m["kapasite"], m["mod"], m["esnek_oneri"]) == (1, 15, "asiri_yuk", 1)
    conn.execute("INSERT INTO ayar(anahtar, deger) VALUES (?, '2')", (f"kapasite_{saat.an:%Y-%m-%d}",))
    conn.commit()
    m = siralama.mod(conn, saat.an)
    assert (m["aktif"], m["kapasite"], m["mod"], m["elle"]) == (2, 30, "normal", True)


def test_siralama_asiri_yuk_deterministik():
    simdi = dt.datetime(2026, 9, 30, 12, 0, 0)

    def is_(no, serit, son24, acilis, durum="bekliyor", **ek):
        return {"is_no": no, "serit": serit, "son24": son24, "acilis": acilis, "durum": durum,
                "btk_hedef": None, "btk_hedef_saat": 12 if serit == "BTK" else None, **ek}
    isler = [
        is_("T1", "BTK", "2026-09-30 20:00:00", "2026-09-29 20:00:00"),
        is_("T2", "BTK", "2026-09-30 13:00:00", "2026-09-29 13:00:00"),             # bolluk < 90 dk → önce
        is_("Gb1", "BTK", "2026-09-30 08:00:00", "2026-09-29 08:00:00"),
        is_("Gd1", "SAHA", "2026-09-30 07:00:00", "2026-09-29 07:00:00"),
        is_("Y1", "SAHA", "2026-10-01 09:00:00", "2026-09-30 09:00:00"),
        is_("K1", "SAHA", "2026-10-01 11:00:00", "2026-09-30 11:00:00", durum="triyaj"),
        is_("O1", "MASA", "2026-10-01 10:00:00", "2026-09-30 10:00:00", oncelik="Kanal şikâyeti"),
    ]
    s1 = siralama.sirala(list(isler), "asiri_yuk", simdi)
    s2 = siralama.sirala(list(reversed(isler)), "asiri_yuk", simdi)
    assert s1 == s2                                                           # deterministik
    assert s1[:3] == ["O1", "K1", "T2"]                                       # öncelikli › Kontrol › sıkışan
    assert s1.index("Gb1") < s1.index("Y1")                                   # gecikmiş BTK gömülmez
    assert siralama.sirala(list(isler), "normal", simdi)[:2] == ["O1", "K1"]


def test_uyum_is_tipinin_hedefine_gore(v2db, conn, kisi, kim, saat):
    """EK-12.1: modem değişimi 7 gün hedeflidir; 30 saatte kapanan modem işi hedefinde sayılır."""
    y.aktar(v2db, [y.satir(1, task="Modem Değişikliği", baslangic="2026-09-29 04:00:00"),
                   y.satir(2, task="Bağlantı Problemi", baslangic="2026-09-29 04:00:00")])
    op = kim("operasyon")
    for no in ("400000001", "400000002"):
        akis.gecis(conn, no, "cozuldu", op, neden="mukerrer")
    t = takip.takip(conn, saat.an)
    assert t["uyum24"]["n"] == 2 and t["uyum24"]["oran"] == 0.5


def test_takip_ek12_hijyen(v2db, conn, kim, saat):
    y.aktar(v2db, [y.satir(1), y.satir(2, task="Kanal Şikayeti"), y.satir(3)])
    op = kim("operasyon")
    akis.btk_sikayet_kaydet(conn, "400000001", op, tarih="2026-09-17 10:00:00")     # 9 iş günü önce → 8. gün alarmı
    h = takip.takip(conn, saat.an)["hijyen"]
    assert (h["btk_alarm"], h["oncelikli"], h["genel_ariza"]) == (1, 1, 0)


def test_satis_ozet_gun_ile_ayni(v2db, conn):
    """F15: Takip satış bölümü /api/ozet/gun ile aynı sayıları verir (iptal edilen ziyaret sayılmaz)."""
    from saha import api as saha_api
    r = conn.execute("SELECT substr(zaman,1,10), COUNT(*) FROM ziyaret WHERE iptal=0 GROUP BY 1 ORDER BY 2 DESC "
                     "LIMIT 1").fetchone()
    gun = r[0] if r else "2026-09-30"
    simdi = dt.datetime.fromisoformat(gun + " 20:00:00")
    s = takip.satis(conn, simdi, 7)
    o = saha_api.ozet_gun(tarih=gun, k={}, conn=conn)
    assert (s["bugun"]["ziyaret"], s["bugun"]["satis"]) == (o["toplam"]["ziyaret"], o["toplam"]["satis"])
    assert s["bugun"]["toplam_satisci"] == len(o["satiscilar"])
    assert all(x["hafta_ziyaret"] >= x["bugun_ziyaret"] for x in s["satiscilar"])
