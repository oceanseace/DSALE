"""BOSS iş ayrıntısı (istek kuyruğu → eklenti → önbellek), görev uuid'si ve BOSS ekip listesi."""
from __future__ import annotations

import pytest

from operasyon.testler import yardim as y
from operasyon.v2 import boss, boss_detay

U1 = "0a1b2c3d-1111-2222-3333-444455556666"


@pytest.fixture(autouse=True)
def _temiz():
    boss_detay.sifirla()
    yield
    boss_detay.sifirla()


def _gorev(i, **ek):
    no = f"{400000000 + i}"
    g = {"task_no": no, "task_adi": "Bağlantı Problemi", "durum": "Randevusuz", "musteri_no": f"9{no[-8:]}",
         "musteri_adi": "Deneme", "adres": f"DENEME APT. Görükle Mh. Test Sk. No:{i} Nilüfer", "il": "Bursa",
         "ilce": "Nilüfer", "acilis": "2026-09-30 09:00:00"}
    g.update(ek)
    return g


SEKMELER = {
    "urunler": {"veri": {"content": [{"productName": "Fiber 100", "productCode": "F100", "status": {"name": "Aktif"}}]}},
    "iletisim": {"veri": [{"name": "Deneme Kişi", "type": "Asıl", "gsm": "0532 111 22 33"}]},
    "aciklama": {"veri": [{"description": "Modem yanmıyor 0532 111 22 33", "createDate": "2026-10-01 09:00",
                           "createdBy": "OPR", "type": "Not"}]},
    "fotograflar": {"veri": {"data": [{"url": "https://boss.turkcell.com.tr/x/1.jpg", "fileName": "1.jpg"}]}},
    "tarihce": {"veri": [{"actionDate": "2026-10-01", "actionName": "Açıldı", "userName": "SİSTEM"}]},
    "ariza_nedeni": {"veri": {"troubleReasonName": "Modem", "code": "M1"}},
    "cihaz": {"hata": "http_404"},
    "evraklar": {"veri": "beklenmedik"},
}


def test_uuid_istek_kuyrugu_onbellek_ve_telefon(istemci, v2db, jeton, kisi):
    kod = boss.eslesme_kodu()
    ek = {"X-Eslesme-Kodu": kod}
    govde = {"gorevler": [_gorev(1, boss_uuid=U1), _gorev(2)], "tam": False,
             "ekipler": [{"ad": "ALI EKIBI", "id": 5, "aktif": True}, {"ad": "ESKI", "id": 6, "aktif": False}, {"x": 1}]}
    s = istemci.post("/api/boss/esitle", json=govde, headers=ek).json()
    assert s["uuid"] == 1 and s["ekip"] == 2
    op = jeton(kisi["operasyon"])
    assert istemci.get("/api/boss/ekipler", headers=op).json()["ekipler"][0] == {"id": "5", "ad": "ALI EKIBI", "aktif": True}
    assert istemci.get("/api/boss/ekipler", headers=jeton(kisi["teknik1"])).status_code == 403

    # uuid'si olmayan iş
    j = istemci.post("/api/isler/400000002/boss-detay", headers=op).json()
    assert j.get("detail", j)["kod"] == "boss_kimlik_yok", j
    assert istemci.get("/api/isler/400000001/boss-detay", headers=op).json()["durum"] != "hazir"
    r = istemci.post("/api/isler/400000001/boss-detay", headers=op).json()
    assert r["durum"] == "bekliyor"
    assert istemci.post("/api/isler/400000001/boss-detay", headers=op).json()["istek_id"] == r["istek_id"]
    assert istemci.get("/api/isler/400000001/boss-detay", headers=op).json()["durum"] == "bekliyor"

    assert istemci.get("/api/boss/istekler").status_code == 401
    ist = istemci.get("/api/boss/istekler", headers=ek).json()["istekler"]
    assert ist == [{"istek_id": r["istek_id"], "is_no": "400000001", "uuid": U1}]
    assert istemci.get("/api/boss/istekler", headers=ek).json()["istekler"] == []    # bir kez verilir

    assert istemci.post("/api/boss/detay", headers=ek, json={"istek_id": "yanlis", "is_no": "400000001"}).status_code == 404
    y_ = istemci.post("/api/boss/detay", headers=ek, json={"istek_id": r["istek_id"], "is_no": "400000001",
                                                           "uuid": U1, "sekmeler": SEKMELER})
    assert y_.status_code == 200 and y_.json()["durum"] == "hazir"

    d = istemci.get("/api/isler/400000001/boss-detay", headers=op).json()
    assert d["durum"] == "hazir" and d["uuid"] == U1 and not d["telefon_gizli"]
    sk = d["sekmeler"]
    assert set(sk) == set(boss_detay.SEKMELER)
    assert sk["urunler"][0]["ad"] == "Fiber 100" and sk["urunler"][0]["kod"] == "F100"
    assert sk["iletisim"][0]["telefonlar"] == ["0532 111 22 33"]
    assert sk["aciklama"][0]["metin"].startswith("Modem") and sk["notlar"][0]["tur"] == "Not"
    assert sk["fotograflar"][0]["url"].endswith("1.jpg")
    assert sk["tarihce"][0]["olay"] == "Açıldı"
    assert sk["ariza_nedeni"]["neden"] == "Modem"
    assert sk["cihaz"] is None and d["hatalar"]["cihaz"] == "http_404"
    assert sk["evraklar"] == [{"deger": "beklenmedik"}]
    assert d["ham"]["iletisim"][0]["gsm"] == "0532 111 22 33"

    # is.musteri izni olmayan: telefonlar gizli
    boss_detay_oku = boss_detay.oku("400000001", musteri=False)
    assert boss_detay_oku["sekmeler"]["iletisim"] is None and "iletisim" not in boss_detay_oku["ham"]
    assert "0532" not in str(boss_detay_oku)

    # önbellekte varken yeni istek açılmaz; yenile=true açar
    assert istemci.post("/api/isler/400000001/boss-detay", headers=op).json()["durum"] == "hazir"
    assert istemci.post("/api/isler/400000001/boss-detay?yenile=true", headers=op).json()["durum"] == "bekliyor"


def test_hata_ve_zaman_asimi(v2db, conn, monkeypatch):
    boss_detay.uuid_yaz(conn, [{"task_no": "400000009", "boss_uuid": U1}, {"task_no": "1", "boss_uuid": "x"}])
    assert boss_detay.uuid_bul(conn, "400000009") == U1
    r = boss_detay.iste(conn, "400000009")
    boss_detay.istekler_ver()
    assert boss_detay.yanit_al({"istek_id": r["istek_id"], "is_no": "400000009", "hata": "istek_yok"})["durum"] == "hata"
    assert boss_detay.oku("400000009", True) == {"durum": "yok", "is_no": "400000009", "hata": "istek_yok"}
    boss_detay.iste(conn, "400000009")
    import time as t
    gercek = t.time
    monkeypatch.setattr(boss_detay.time, "time", lambda: gercek() + 1000)
    assert boss_detay.oku("400000009", True)["hata"] == "zaman_asimi"


def _onden(istemci, ek, sonuclar):
    r = istemci.post("/api/boss/detay-onden", headers=ek, json={"sonuclar": sonuclar})
    assert r.status_code == 200, r.text
    return r.json()


def test_onden_okuma_kalici_depo_parmak_izi_ve_saklama(istemci, v2db, conn, jeton, kisi, monkeypatch):
    """Eşitleme yanıtı yeni/değişen açık işleri verir; eklentinin okuduğu ayrıntı kalıcı yazılır (süreç yeniden
    başlasa da GET hemen döner); parmak izi değişince iş yeniden verilir; iş kapanınca kayıt silinir."""
    ek = {"X-Eslesme-Kodu": boss.eslesme_kodu()}
    op = jeton(kisi["operasyon"])
    U2 = "0a1b2c3d-1111-2222-3333-444455556667"
    s = istemci.post("/api/boss/esitle", headers=ek, json={"gorevler": [
        _gorev(1, boss_uuid=U1, acilis="2026-09-30 09:00:00"), _gorev(2, boss_uuid=U2, acilis="2026-10-01 09:00:00"),
        _gorev(3)], "tam": False}).json()
    assert s["detay_onden"] == [{"task_no": "400000002", "uuid": U2}, {"task_no": "400000001", "uuid": U1}], \
        "uuid'si bilinen açık işler, en yeni önce"
    assert (s["detay_tamam"], s["detay_toplam"]) == (0, 3)
    d0 = istemci.get("/api/boss/durum", headers=op).json()
    assert (d0["detay_tamam"], d0["detay_toplam"]) == (0, 3) and d0["detay_kalan_dk"] >= 0

    assert istemci.post("/api/boss/detay-onden", json={"sonuclar": []}).status_code == 401
    y = _onden(istemci, ek, [{"task_no": "400000001", "uuid": U1, "sekmeler": SEKMELER},
                             {"task_no": "400000002", "uuid": U2, "hata": "http_500"},
                             {"task_no": "499999999", "uuid": U1, "sekmeler": SEKMELER}])     # bilinmeyen iş saklanmaz
    assert (y["okunan"], y["hata"], y["detay_tamam"], y["detay_toplam"]) == (1, 1, 1, 3)
    assert y["detay_onden"] == [], "okunan iş ve az önce okunamayan iş yeniden verilmez"
    assert conn.execute("SELECT COUNT(*) FROM boss_detay").fetchone()[0] == 1
    assert conn.execute("SELECT musteri_tel FROM is_emri WHERE is_no='400000001'").fetchone()[0] == "5321112233", \
        "iletişim sekmesi telefonu da doldurur"
    assert conn.execute("SELECT telefon FROM boss_iletisim WHERE task_no='400000001'").fetchone()[0] == 1

    boss_detay.sifirla()                              # süreç yeniden başladı: bellek boş, depo dolu
    d = istemci.get("/api/isler/400000001/boss-detay", headers=op).json()
    assert d["durum"] == "hazir" and d["taze"] and d["zaman"] and not d["yenileniyor"]
    assert d["sekmeler"]["urunler"][0]["ad"] == "Fiber 100" and d["ham"]["iletisim"][0]["gsm"] == "0532 111 22 33"
    assert istemci.post("/api/isler/400000001/boss-detay", headers=op).json()["durum"] == "hazir"
    assert boss_detay.istekler_ver() == [], "taze kayıtta BOSS'a yeniden gidilmez"

    # 10 dk'dan eski: kayıt HEMEN döner, arkada tazelenir (tek istek)
    import time as t
    gercek = t.time
    monkeypatch.setattr(boss_detay.time, "time", lambda: gercek() + boss_detay.DETAY_TAZE_SN + 5)
    d = istemci.get("/api/isler/400000001/boss-detay", headers=op).json()
    assert d["durum"] == "hazir" and not d["taze"] and d["yenileniyor"] and d["sekmeler"]["urunler"]
    p = istemci.post("/api/isler/400000001/boss-detay", headers=op).json()
    assert p["durum"] == "hazir" and p["yenileniyor"]
    assert [i["is_no"] for i in boss_detay.istekler_ver()] == ["400000001"]
    monkeypatch.setattr(boss_detay.time, "time", gercek)

    # parmak izi değişti (BOSS'ta güncellendi) → yeniden verilir
    s = istemci.post("/api/boss/esitle", headers=ek, json={"gorevler": [
        _gorev(1, boss_uuid=U1, durum="Randevu alındı", guncelleme="2026-10-02 10:00:00")], "mod": "fark",
        "kaldirilan": [], "tam": False}).json()
    assert {"task_no": "400000001", "uuid": U1} in s["detay_onden"]

    # iş kapandı → saklama ayrıntıyı (kişisel veri) siler
    istemci.post("/api/boss/esitle", headers=ek, json={"gorevler": [_gorev(1, boss_uuid=U1, durum="Tamamlandı")],
                                                        "mod": "fark", "kaldirilan": [], "tam": False})
    from operasyon.v2 import saklama
    saklama.uygula(conn)
    assert conn.execute("SELECT COUNT(*) FROM boss_detay").fetchone()[0] == 0
    assert istemci.get("/api/isler/400000001/boss-detay", headers=op).json()["durum"] != "hazir"


def test_kullanici_istegi_kalici_yazilir(istemci, v2db, conn, jeton, kisi):
    ek = {"X-Eslesme-Kodu": boss.eslesme_kodu()}
    op = jeton(kisi["operasyon"])
    istemci.post("/api/boss/esitle", headers=ek, json={"gorevler": [_gorev(1, boss_uuid=U1)], "tam": False})
    r = istemci.post("/api/isler/400000001/boss-detay", headers=op).json()
    assert r["durum"] == "bekliyor"
    boss_detay.istekler_ver()
    istemci.post("/api/boss/detay", headers=ek, json={"istek_id": r["istek_id"], "is_no": "400000001", "uuid": U1,
                                                      "sekmeler": SEKMELER})
    assert conn.execute("SELECT COUNT(*) FROM boss_detay WHERE task_no='400000001'").fetchone()[0] == 1
    s = istemci.post("/api/boss/esitle", headers=ek, json={"gorevler": [_gorev(1, boss_uuid=U1)], "tam": False}).json()
    assert s["detay_onden"] == [] and s["detay_tamam"] == 1, "kullanıcının açtığı iş önden okumada tekrar okunmaz"


def test_onden_sirasi_kullanicinin_acacagi_isler_once_ve_kaldigi_yerden(istemci, v2db, conn, jeton, kisi, kim):
    """Sıra: TASKS'ın ekranda gösterdiği işler → bugün atanan/randevulu → randevulu → en yeni. Süreç yeniden başlasa
    da (bellek boş) sunucu okunmamış işleri bilir: boş gövdeli soru kalanları verir (kesintiden sonra sürer)."""
    from operasyon.v2 import akis, zaman
    ek = {"X-Eslesme-Kodu": boss.eslesme_kodu()}
    uu = lambda i: f"0a1b2c3d-1111-2222-3333-{i:012d}"     # noqa: E731
    istemci.post("/api/boss/esitle", headers=ek, json={"gorevler": [
        _gorev(i, boss_uuid=uu(i), acilis=f"2026-09-{10 + i:02d} 09:00:00") for i in range(1, 6)], "tam": False})
    assert [x["task_no"] for x in boss_detay.detay_gerekli(conn)] == \
        ["400000005", "400000004", "400000003", "400000002", "400000001"], "en yeni önce"
    yarin = zaman.metin(zaman.simdi() + __import__("datetime").timedelta(days=2))[:10]
    akis.randevu(conn, "400000001", kim("operasyon"), f"{yarin} 10:00:00", f"{yarin} 12:00:00", True)
    akis.ata(conn, "400000002", kisi["teknik1"], kim("operasyon"))      # bugün atandı
    assert [x["task_no"] for x in boss_detay.detay_gerekli(conn)][:2] == ["400000002", "400000001"]

    op = jeton(kisi["operasyon"])
    assert istemci.post("/api/boss/detay-oncelik", headers=op, json={"is_nolar": ["400000003", "x/../y"]}).json() \
        == {"ok": True, "sayi": 1}
    assert istemci.post("/api/boss/detay-oncelik", headers=ek, json={"is_nolar": []}).status_code in (401, 403)
    assert [x["task_no"] for x in boss_detay.detay_gerekli(conn)][:3] == ["400000003", "400000002", "400000001"]

    y = _onden(istemci, ek, [{"task_no": "400000003", "uuid": uu(3), "sekmeler": SEKMELER}])
    assert y["detay_tamam"] == 1 and y["detay_onden"][0]["task_no"] == "400000002"
    boss_detay.sifirla()                               # uygulama / bilgisayar yeniden başladı
    y = _onden(istemci, ek, [])
    assert (y["detay_tamam"], y["detay_toplam"]) == (1, 5)
    assert sorted(x["task_no"] for x in y["detay_onden"]) == ["400000001", "400000002", "400000004", "400000005"]


def test_istekler_uzun_yoklama_hemen_doner(istemci, v2db, jeton, kisi):
    import threading
    import time as t
    ek = {"X-Eslesme-Kodu": boss.eslesme_kodu()}
    istemci.post("/api/boss/esitle", headers=ek, json={"gorevler": [_gorev(1, boss_uuid=U1)], "tam": False})
    t0 = t.monotonic()
    assert istemci.get("/api/boss/istekler?bekle=0.3", headers=ek).json()["istekler"] == []
    assert t.monotonic() - t0 >= 0.25, "istek yokken bekletir"
    op = jeton(kisi["operasyon"])
    threading.Timer(0.3, lambda: istemci.post("/api/isler/400000001/boss-detay", headers=op)).start()
    t0 = t.monotonic()
    ist = istemci.get("/api/boss/istekler?bekle=10", headers=ek).json()["istekler"]
    assert [i["is_no"] for i in ist] == ["400000001"] and t.monotonic() - t0 < 3, "istek gelince hemen döner"
