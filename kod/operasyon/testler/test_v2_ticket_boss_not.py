"""Altyapı ticket'ı → işlere kendiliğinden BOSS notu (``saha/ticket_boss_not.py``), sahte BOSS (eklenti yoklaması).

Not, doğrulanmış not yolundan (``akis.not_ekle`` → ``boss_yazma`` 'not' → task/note) gider; burada eklentiye verilen
'not' istekleri sayılır. Perakende müşteride müşterinin BÜTÜN açık işleri, toptanda yalnız bağlı iş; numarasız ticket'ta
not yok, numara girilince gider; HATA'da "Ek kapasite talebi açılamadı: <son not>"; tekrar yok. Numaralar uydurmadır.
"""
from __future__ import annotations

import pytest

from operasyon.v2 import akis, boss, boss_yazma
from saha import ticket as tk
from saha import ticket_boss_not as tbn

U = "0b1c2d3e-1111-2222-3333-{:012d}".format
LOC = "ZZ91000001"


@pytest.fixture(autouse=True)
def _temiz():
    boss_yazma.sifirla()
    yield
    boss_yazma.sifirla()


def _gorev(i: int, musteri: str, task_adi: str = "Fiber Kurulum", kanal: str = "DEHANET ECM", **ham) -> dict:
    no = f"{410000000 + i}"
    return {"task_no": no, "task_adi": task_adi, "durum": "Randevusuz", "musteri_no": musteri,
            "musteri_adi": "Deneme Müşteri", "adres": f"DENEME APT. Görükle Mh. Test Sk. No:{i} Nilüfer", "il": "Bursa",
            "ilce": "Nilüfer", "acilis": "2026-09-30 09:00:00", "boss_uuid": U(i), "satis_kanali": kanal, "lokasyon": LOC,
            "ham": {"crmTaskId": no, "taskStatus": "SEND_TO_CENTER", "type": "TECH", "customerNo": musteri,
                    "taskCategory": task_adi, "locationId": LOC, "saleChannel": kanal, **ham}}


@pytest.fixture
def istemci(v2db):
    """v2 yönlendiricileri + ticket defteri uçları (saha.yonetim_uclari)."""
    from fastapi.testclient import TestClient

    from operasyon.testler.conftest import uygulama
    from saha import yonetim_uclari

    app = uygulama()
    app.include_router(yonetim_uclari.yonlendirici)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def ortam(istemci, v2db, conn, jeton, kisi):
    ek = {"X-Eslesme-Kodu": boss.eslesme_kodu()}

    def esitle(gorevler):
        r = istemci.post("/api/boss/esitle", headers=ek, json={"gorevler": gorevler, "tam": False})
        assert r.status_code == 200, r.text
    return {"ek": ek, "op": jeton(kisi["operasyon"]), "admin": jeton(kisi["yonetici"]), "esitle": esitle}


def _kuyruk(conn, task_nolar=None) -> list[tuple[str, str]]:
    """boss_yazma 'not' kayıtları: (task no, metin) — kesin sayım için kuyruğun kendisi."""
    import json
    satirlar = conn.execute("SELECT task_no, girdi FROM boss_yazma WHERE tur='not' ORDER BY id").fetchall()
    out = [(r[0], json.loads(r[1])["metin"]) for r in satirlar]
    return [x for x in out if task_nolar is None or x[0] in task_nolar]


def _no(i):
    return f"{410000000 + i}"


def test_toptan_mi_kurallari():
    perakende = [{"task_no": "1", "satis_kanali": "DEHANET ECM"}, {"task_no": "2", "satis_kanali": "GLOBAL CC"}]
    assert tbn.toptan_mi(perakende) is False
    assert tbn.toptan_mi(perakende, {"1": {"segment": "Residential", "productInfo": "Evde TV+ Keyfi"}}) is False
    assert tbn.toptan_mi([{"task_no": "1", "satis_kanali": "VODAFONE NET İLETİŞİM HİZMETLERİ A.Ş."}])
    assert tbn.toptan_mi([{"task_no": "1", "satis_kanali": "MİLLENİCOM TELEKOMİNİKASYON"}])
    assert tbn.toptan_mi([{"task_no": "1", "satis_kanali": "GÖKNET"}])
    assert tbn.toptan_mi([{"task_no": "1", "satis_kanali": "D-Smart"}])
    assert tbn.toptan_mi([{"task_no": "1", "satis_kanali": ""}], {"1": {"segment": "TOPTAN"}})
    assert tbn.toptan_mi([{"task_no": "1"}], {"1": {"productInfo": "12 Ay Taahhütlü Vodafone Toptan Fiber"}})
    assert tbn.toptan_mi([{"task_no": "1"}], {"1": {"saleChannel": "VODAFONE NET"}})
    assert tbn.toptan_mi([{"task_no": str(i), "satis_kanali": "TURKCELL MERKEZ OFIS"} for i in range(21)])
    assert not tbn.toptan_mi([{"task_no": str(i), "satis_kanali": "TURKCELL MERKEZ OFIS"} for i in range(20)])


def test_metinler():
    assert tbn.not_metni({"durum": "AÇIK", "ticket_no": ""}) is None
    assert tbn.not_metni({"durum": "AÇIK", "ticket_no": " 2610091234 "}) == \
        "2610091234 ticket id ile altyapıdan çözüm bekler."
    assert tbn.not_metni({"durum": "ÇÖZÜLDÜ", "ticket_no": "1"}) is None
    assert tbn.not_metni({"durum": "HATA"}) == "Ek kapasite talebi açılamadı (hata), altyapıdan çözüm bekler."
    assert tbn.not_metni({"durum": "HATA"}, "HP 29, Sistemsel 32") == "Ek kapasite talebi açılamadı: HP 29, Sistemsel 32"
    uzun = tbn.hata_metni("x" * 5000)
    assert len(uzun) <= tbn.HATA_NOT_EN_COK and uzun.endswith("…")


def test_perakende_kurulum_ve_kanal_sikayeti_ikisi_de_not_alir(istemci, conn, ortam):
    ortam["esitle"]([_gorev(1, "91000001"), _gorev(2, "91000001", "Kanal Şikayeti")])
    r = istemci.post("/api/ticket", headers=ortam["op"], json={
        "konu": "EK SP", "location_id": LOC, "ticket_no": "TK-1001", "musteri": "91000001", "isler": [_no(1)]})
    assert r.status_code == 201, r.text
    metin = "TK-1001 ticket id ile altyapıdan çözüm bekler."
    assert sorted(_kuyruk(conn)) == [(_no(1), metin), (_no(2), metin)]
    # sahte BOSS: eklentiye iki not isteği gerçek (yaz) olarak verilir, gövde doğrulanmış not şablonu
    istekler = [i for i in istemci.get("/api/boss/yazilacaklar", headers=ortam["ek"]).json()["istekler"]
                if i["tur"] == "not"]
    assert len(istekler) == 2 and all(i["yaz"] for i in istekler)
    assert {i["govde"]["description"] for i in istekler} == {metin}
    assert all(i["yol"] == "/boss-gateway-service/task-service/api/v1/task/note" for i in istekler)
    # iş çekmecesinin not listesinde "olağan" not olarak durur
    olaylar = istemci.get(f"/api/isler/{_no(2)}", headers=ortam["op"]).json()
    notlar = [o for o in olaylar["olaylar"] if o["tur"] == "not"]
    assert notlar and notlar[0]["notu"] == metin and notlar[0]["boss"]["durum"] == "gonderiliyor"
    # ticket çekmecesi: iş başına durum
    t = istemci.get(f"/api/ticket/{r.json()['ticket']['id']}", headers=ortam["op"]).json()["ticket"]
    assert sorted((x["task_no"], x["durum"]) for x in t["boss_notlari"]) == [(_no(1), "gonderiliyor"),
                                                                             (_no(2), "gonderiliyor")]


def test_toptan_elli_is_yalniz_bagli_olan(istemci, conn, ortam):
    ortam["esitle"]([_gorev(100 + i, "23700000", kanal="TURKCELL MERKEZ OFIS") for i in range(50)])
    r = istemci.post("/api/ticket", headers=ortam["op"], json={
        "konu": "EK SP", "location_id": LOC, "ticket_no": "TK-2002", "musteri": "23700000", "isler": [_no(107)]})
    assert r.status_code == 201, r.text
    assert _kuyruk(conn) == [(_no(107), "TK-2002 ticket id ile altyapıdan çözüm bekler.")]
    # "+ abone ekle": yalnız eklenen iş
    istemci.post(f"/api/ticket/{r.json()['ticket']['id']}/isler", headers=ortam["op"], json={"isler": [_no(120)]})
    assert [x[0] for x in _kuyruk(conn)] == [_no(107), _no(120)]


def test_numarasiz_once_sifir_numara_girilince_bir(istemci, conn, ortam):
    ortam["esitle"]([_gorev(1, "91000002")])
    r = istemci.post("/api/ticket", headers=ortam["op"], json={
        "konu": "EK SP", "location_id": LOC, "musteri": "91000002", "isler": [_no(1)]})
    tid = r.json()["ticket"]["id"]
    assert _kuyruk(conn) == []
    istemci.patch(f"/api/ticket/{tid}", headers=ortam["op"], json={"detay": "beklemede"})
    assert _kuyruk(conn) == []
    istemci.patch(f"/api/ticket/{tid}", headers=ortam["op"], json={"ticket_no": "TK-3003"})
    assert _kuyruk(conn) == [(_no(1), "TK-3003 ticket id ile altyapıdan çözüm bekler.")]
    # tekrar yok: başka alan değişse de, ilişkili uçlar yeniden çağrılsa da
    istemci.patch(f"/api/ticket/{tid}", headers=ortam["op"], json={"detay": "x", "notu": "arandı"})
    istemci.post(f"/api/ticket/{tid}/isler", headers=ortam["op"], json={"isler": [_no(1)]})
    tbn.esitle(conn, tid, None)
    conn.commit()
    assert len(_kuyruk(conn)) == 1
    # numara DEĞİŞİRSE metin değişir → yeni metin bir kez
    istemci.patch(f"/api/ticket/{tid}", headers=ortam["op"], json={"ticket_no": "TK-3004"})
    istemci.patch(f"/api/ticket/{tid}", headers=ortam["op"], json={"detay": "y"})
    assert [x[1] for x in _kuyruk(conn)] == ["TK-3003 ticket id ile altyapıdan çözüm bekler.",
                                             "TK-3004 ticket id ile altyapıdan çözüm bekler."]


def test_hata_bir_kez_ve_son_kullanici_notu(istemci, conn, ortam):
    ortam["esitle"]([_gorev(1, "91000003")])
    r = istemci.post("/api/ticket", headers=ortam["op"], json={
        "konu": "EK SP", "location_id": LOC, "musteri": "91000003", "isler": [_no(1)], "durum": "HATA"})
    tid = r.json()["ticket"]["id"]
    assert _kuyruk(conn) == [(_no(1), tbn.NOT_HATA)]
    istemci.patch(f"/api/ticket/{tid}", headers=ortam["op"], json={"detay": "x"})
    assert len(_kuyruk(conn)) == 1, "HATA notu bir kez"
    gercek = ("HP 29, Sistemsel 32, Atanan 9, Fiziki 16/16, Bina HP sayısı kadar sistemsel port bulunduğu için, port "
              "talebi oluşturulamaz. | Binada sistemsel port sayısı 32, boşta port sayısı 23 olduğu için %25 kuralına "
              "göre port talebi oluşturulamaz.")
    istemci.patch(f"/api/ticket/{tid}", headers=ortam["op"], json={"notu": gercek})
    assert _kuyruk(conn)[-1] == (_no(1), "Ek kapasite talebi açılamadı: " + gercek)
    istemci.patch(f"/api/ticket/{tid}", headers=ortam["op"], json={"notu": gercek})      # aynı not yeniden
    istemci.patch(f"/api/ticket/{tid}", headers=ortam["op"], json={"detay": "z"})
    assert len(_kuyruk(conn)) == 2, "aynı metin tekrar gitmez"
    # sistem notu (iş eklendi) baz alınmaz
    assert tbn.son_kullanici_notu(conn, tid) == gercek


def test_hata_durumu_notla_ayni_anda(istemci, conn, ortam):
    ortam["esitle"]([_gorev(1, "91000004")])
    r = istemci.post("/api/ticket", headers=ortam["op"], json={
        "konu": "EK SP", "location_id": LOC, "musteri": "91000004", "isler": [_no(1)]})
    tid = r.json()["ticket"]["id"]
    istemci.patch(f"/api/ticket/{tid}", headers=ortam["op"], json={"durum": "HATA", "notu": "Port talebi oluşturulamaz."})
    assert _kuyruk(conn) == [(_no(1), "Ek kapasite talebi açılamadı: Port talebi oluşturulamaz.")]


def test_engel_ticketi_numara_girilince_not(istemci, conn, ortam, kim):
    ortam["esitle"]([_gorev(1, "91000005"), _gorev(2, "91000005", "Kanal Şikayeti")])
    op = kim("operasyon")
    akis.bizim_durum_yaz(conn, _no(1), op, "Port yok")
    tid = conn.execute("SELECT ticket_id FROM is_emri WHERE is_no=?", (_no(1),)).fetchone()[0]
    assert tid and _kuyruk(conn) == [], "numarasız engel ticket'ı: not yok"
    istemci.patch(f"/api/ticket/{tid}", headers=ortam["op"], json={"ticket_no": "TK-5005"})
    assert sorted(x[0] for x in _kuyruk(conn)) == [_no(1), _no(2)], "perakende: kurulum + kanal şikâyeti"
    # aynı engelde ikinci müşteri (numaralı ticket'a bağlanır) → o an not
    ortam["esitle"]([_gorev(3, "91000006")])
    akis.bizim_durum_yaz(conn, _no(3), op, "Kıl yok")
    assert conn.execute("SELECT ticket_id FROM is_emri WHERE is_no=?", (_no(3),)).fetchone()[0] == tid
    assert sorted(x[0] for x in _kuyruk(conn)) == [_no(1), _no(2), _no(3)]
    akis.bizim_durum_yaz(conn, _no(3), op, "Kıl yok")                         # etkisiz
    assert len(_kuyruk(conn)) == 3


def test_not_anahtari_kapaliyken_gitmez(istemci, conn, ortam):
    conn.execute("INSERT INTO ayar(anahtar, deger) VALUES('boss_yazma_not','kapali') "
                 "ON CONFLICT(anahtar) DO UPDATE SET deger='kapali'")
    conn.commit()
    ortam["esitle"]([_gorev(1, "91000007")])
    r = istemci.post("/api/ticket", headers=ortam["op"], json={
        "konu": "EK SP", "location_id": LOC, "ticket_no": "TK-7007", "musteri": "91000007", "isler": [_no(1)]})
    assert r.status_code == 201 and _kuyruk(conn) == []
    assert conn.execute("SELECT COUNT(*) FROM ticket_boss_not").fetchone()[0] == 0


def test_kapali_ve_silinen_tickete_not_yok(istemci, conn, ortam):
    ortam["esitle"]([_gorev(1, "91000008")])
    r = istemci.post("/api/ticket", headers=ortam["op"], json={
        "konu": "EK SP", "location_id": LOC, "musteri": "91000008", "isler": [_no(1)], "durum": "ÇÖZÜLDÜ",
        "ticket_no": "TK-8008"})
    assert r.status_code == 201 and _kuyruk(conn) == []
    assert tk.getir(conn, r.json()["ticket"]["id"])["boss_notlari"] == []
