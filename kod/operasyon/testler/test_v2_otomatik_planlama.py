"""Otomatik planlama, 1. evre (09.10): ilişkili işler birlikte · ticket → BOSS askısı (varsayılan çift Abone Kaynaklı >
Ulaşılamadı, alt neden kimliği işin kendi kategorisinden; eskiden NETWORK) · çözümde önceki
ekibe geri atama · Ayarlar anahtarları. Sahte BOSS (eklenti yoklaması); BOSS'a hiçbir istek gönderilmez. Numaralar
uydurmadır.

Kilitlenen eski davranışlar: ticket notu (test_v2_ticket_boss_not.py), toplu atama/askı gövdeleri
(test_v2_boss_yazma.py), ekip uzlaşması (test_v2_ekip_uzlas.py) — bu dosya onlara dokunmaz.
"""
from __future__ import annotations

import datetime as dt
import json

import pytest

from operasyon.testler.test_v2_ticket_boss_not import LOC, U, istemci  # noqa: F401
from operasyon.v2 import boss, boss_yazma, iliskili
from saha import ticket_boss_aski as tba

KAT, URUN = "560", "Tell_FiberInternetProduct"
NEDEN_YOLU = (f"/boss-gateway-service/task-service/api/v1/task/reasons/task-category/{KAT}/record-type/"
              f"SUSPEND_REASONS/product-code/{URUN}")
ABONE = "26CDE1BE-1B03-8A0A-5384-F0273F623CE7"
NETWORK = "4697B3FA-0000-4000-8000-000000000001"
ALT_ABONE = "6f1c2d3e-4b5a-4c6d-8e7f-0123456789ab"
ALT_KAPASITE = "7a1c2d3e-4b5a-4c6d-8e7f-0123456789ac"
ALT_DIGER = "8b1c2d3e-4b5a-4c6d-8e7f-0123456789ad"
EKIP_ID = "edf28c9d-0000-4000-8000-000000000088"
ADMIN_TEL = "5009990001"


def _alt_yolu(guid: str) -> str:
    return (f"/boss-gateway-service/task-service/api/v1/task/reason/id/{guid}/sub/reasons/task-category/{KAT}/"
            f"product-code/{URUN}")


@pytest.fixture(autouse=True)
def _temiz():
    boss_yazma.sifirla()
    tba.sifirla()
    yield
    boss_yazma.sifirla()
    tba.sifirla()


def _no(i: int) -> str:
    return f"{420000000 + i}"


def _gorev(i: int, musteri: str, task_adi: str = "Fiber Kurulum", kanal: str = "DEHANET ECM", **ek) -> dict:
    no = _no(i)
    g = {"task_no": no, "task_adi": task_adi, "durum": "Randevusuz", "musteri_no": musteri,
         "musteri_adi": "Deneme Müşteri", "adres": f"DENEME APT. Test Sk. No:{i} Nilüfer", "il": "Bursa",
         "ilce": "Nilüfer", "acilis": "2026-09-30 09:00:00", "boss_uuid": U(i + 500), "satis_kanali": kanal,
         "lokasyon": LOC,
         "ham": {"crmTaskId": no, "taskStatus": "OPEN", "type": "TECH", "customerNo": musteri,
                 "customerName": "Deneme Müşteri", "taskCategory": task_adi, "locationId": LOC, "saleChannel": kanal,
                 "taskCategoryType": int(KAT), "productCode": URUN}}
    g.update(ek)
    return g


@pytest.fixture
def ortam(istemci, v2db, conn, jeton, kisi, monkeypatch, saat):  # noqa: F811
    monkeypatch.setenv("TURKCELL_ADMIN_TELEFON", ADMIN_TEL)
    saat.ayarla("2026-10-09 11:00:00")                        # Cuma: bir sonraki iş günü Pazartesi 12.10
    ek = {"X-Eslesme-Kodu": boss.eslesme_kodu()}

    def esitle(gorevler, ekipler=None):
        govde = {"gorevler": gorevler, "tam": False}
        if ekipler:
            govde["ekipler"] = ekipler
        r = istemci.post("/api/boss/esitle", headers=ek, json=govde)
        assert r.status_code == 200, r.text

    esitle([_gorev(900, "99999999")], [{"ad": "DENEME EKIBI", "id": EKIP_ID, "aktif": True}])
    ekip = conn.execute("SELECT id FROM kullanici WHERE boss_ekip_id=?", (EKIP_ID,)).fetchone()[0]
    return {"ek": ek, "op": jeton(kisi["operasyon"]), "admin": jeton(kisi["yonetici"]), "esitle": esitle,
            "ekip": ekip}


def _katalog(conn, network_alt: bool = True) -> None:
    """Askı kataloğu: ABONE (alt listesi bilinir → askı şablonu doğrulanmış) + NETWORK (alt listesi isteğe bağlı)."""
    boss_yazma.nedenleri_yaz(conn, NEDEN_YOLU, {"content": [
        {"reasonId": ABONE, "code": "ABONE", "description": "Abone Kaynaklı"},
        {"reasonId": NETWORK, "code": "NETWORK", "description": "Network Kaynaklı"}]})
    boss_yazma.nedenleri_yaz(conn, _alt_yolu(ABONE), {"content": [{"id": ALT_ABONE, "name": "Ulaşılamadı"}]})
    if network_alt:
        boss_yazma.nedenleri_yaz(conn, _alt_yolu(NETWORK), {"content": [
            {"id": ALT_DIGER, "name": "Diğer"}, {"id": ALT_KAPASITE, "name": "Ek Kapasite İhtiyacı"}]})
    conn.commit()


def _ata(istemci, ortam, no, bas="2026-10-09 14:00:00", bit="2026-10-09 16:00:00"):
    r = istemci.post(f"/api/isler/{no}/ata", headers=ortam["op"], json={
        "teknik_id": ortam["ekip"], "randevu": {"bas": bas, "bit": bit, "teyitli": True}})
    assert r.status_code == 200, r.text


def _kayitlar(conn, tur: str) -> list[tuple[str, str, dict]]:
    return [(r[0], r[1], json.loads(r[2])) for r in conn.execute(
        "SELECT task_no, durum, girdi FROM boss_yazma WHERE tur=? ORDER BY id", (tur,))]


# ============================================================================= 1. ilişkili işler birlikte
def test_iliskili_isler_perakende_genisler_toptan_genislemez(istemci, conn, ortam):
    ortam["esitle"]([_gorev(1, "91000001"), _gorev(2, "91000001", "Kanal Şikayeti"),
                     _gorev(3, "91000001", "Bağlantı Problemi"), _gorev(4, "91000002"),
                     _gorev(5, "23700001", kanal="VODAFONE NET"), _gorev(6, "23700001", kanal="VODAFONE NET")])
    r = istemci.post("/api/isler/iliskili/isler", headers=ortam["op"], json={"is_nolar": [_no(1)]})
    assert r.status_code == 200, r.text
    j = r.json()
    assert sorted(x["task_no"] for x in j["isler"]) == [_no(2), _no(3)]
    assert {x["kaynak"] for x in j["isler"]} == {_no(1)} and j["varsayilan"] is True
    assert all("musteri" not in a for x in j["isler"] for a in x), "kişisel veri dönmez"
    # seçimde olan iş tekrar eklenmez; tek işli müşteride ilişki yok
    j = istemci.post("/api/isler/iliskili/isler", headers=ortam["op"],
                     json={"is_nolar": [_no(1), _no(2), _no(4)]}).json()
    assert [x["task_no"] for x in j["isler"]] == [_no(3)]
    # toptan: genişletilmez
    j = istemci.post("/api/isler/iliskili/isler", headers=ortam["op"], json={"is_nolar": [_no(5)]}).json()
    assert j["isler"] == [] and j["toptan_atlanan"] == 1


def test_iliskili_dahil_ayari_yalniz_administrator(istemci, conn, ortam):
    r = istemci.put("/api/isler/ayarlar", headers=ortam["op"], json={"iliskili_dahil": False})
    assert r.status_code == 403
    r = istemci.put("/api/isler/ayarlar", headers=ortam["admin"], json={"iliskili_dahil": False})
    assert r.status_code == 200 and r.json()["iliskili_dahil"] is False
    assert iliskili.dahil_varsayilan(conn) is False
    a = istemci.get("/api/isler/ayarlar", headers=ortam["op"]).json()
    assert a["iliskili_dahil"] is False and a["ticket_otomatik_aski"] is True and a["ticket_cozum_yeniden_ata"] is True
    assert a["ticket_cozum_slot"] == "08:00-10:00"


def test_uyumsuz_iliskili_isler_hepsi_ayni_ekibe(istemci, conn, ortam):
    ortam["esitle"]([_gorev(1, "91000003"), _gorev(2, "91000003", "Kanal Şikayeti"),
                     _gorev(3, "91000004"), _gorev(4, "91000004", "TV+ Kurulum")])
    _ata(istemci, ortam, _no(1))
    _ata(istemci, ortam, _no(3))
    _ata(istemci, ortam, _no(4))                                     # 91000004: hepsi aynı ekipte
    j = istemci.get("/api/isler/iliskili/uyumsuz", headers=ortam["op"]).json()
    assert j["is_sayisi"] == 1 and [x["task_no"] for x in j["gruplar"][0]["isler"]] == [_no(2)]
    assert j["gruplar"][0]["hedef"]["teknik_id"] == ortam["ekip"]
    assert j["gruplar"][0]["hedef"]["randevu_bas"] == "2026-10-09 14:00:00"
    r = istemci.post("/api/isler/iliskili/hizala", headers=ortam["op"], json={})
    assert r.status_code == 200 and r.json()["atanan"] == [_no(2)], r.text
    a, rb = conn.execute("SELECT atanan_id, randevu_bas FROM is_emri WHERE is_no=?", (_no(2),)).fetchone()
    assert a == ortam["ekip"] and rb == "2026-10-09 14:00:00", "çapanın ekibi ve dilimi"
    assert [x[0] for x in _kayitlar(conn, "atama")][-1] == _no(2), "atama BOSS'a da yazılır"
    assert istemci.get("/api/isler/iliskili/uyumsuz", headers=ortam["op"]).json()["is_sayisi"] == 0


def test_uyumsuz_askidaki_ve_toptan_hizalanmaz(istemci, conn, ortam):
    ortam["esitle"]([_gorev(1, "91000005"), _gorev(2, "91000005", "Kanal Şikayeti"),
                     _gorev(5, "23700002", kanal="VODAFONE NET"), _gorev(6, "23700002", kanal="VODAFONE NET")])
    _ata(istemci, ortam, _no(1))
    _ata(istemci, ortam, _no(5))
    conn.execute("UPDATE is_emri SET durum='askida' WHERE is_no=?", (_no(2),))
    conn.commit()
    assert istemci.get("/api/isler/iliskili/uyumsuz", headers=ortam["op"]).json()["is_sayisi"] == 0


# ============================================================================= 2. ticket → BOSS askısı (NETWORK)
def _ticket(istemci, ortam, musteri, isler, **ek):
    r = istemci.post("/api/ticket", headers=ortam["op"], json={
        "konu": "EK SP", "location_id": LOC, "ticket_no": "TK-9001", "musteri": musteri, "isler": isler, **ek})
    assert r.status_code == 201, r.text
    return r.json()["ticket"]["id"]


V_ALT = ALT_ABONE          # varsayılan alt neden: işin kategorisinin (560) listesindeki "Ulaşılamadı"


def test_ticket_isleri_varsayilan_askiya_alinir(istemci, conn, ortam):
    """Kullanıcı kararı (09.10): ticket askısı da Abone Kaynaklı > Ulaşılamadı (NETWORK alt nedeni beklenmez)."""
    _katalog(conn)
    ortam["esitle"]([_gorev(1, "91000010"), _gorev(2, "91000010", "Kanal Şikayeti")])
    _ata(istemci, ortam, _no(1))
    tid = _ticket(istemci, ortam, "91000010", [_no(1)])
    k = _kayitlar(conn, "aski")
    assert sorted(x[0] for x in k) == [_no(1), _no(2)], "perakende: bağlı iş + müşterinin öbür açık işi"
    metin = "TK-9001 ticket id ile altyapıdan çözüm bekler."
    assert all(x[2]["notu"] == metin and x[2]["boss_neden_ad"] == "ABONE"
               and x[2]["boss_alt_ad"] == "Ulaşılamadı" for x in k)
    # sahte BOSS: gövde = askı şablonu, ABONE + kategorinin "Ulaşılamadı"sı, açıklama = ticket notu, 7 gün
    ist = [i for i in istemci.get("/api/boss/yazilacaklar", headers=ortam["ek"]).json()["istekler"] if i["tur"] == "aski"]
    assert len(ist) == 2 and all(i["yaz"] for i in ist)
    g = ist[0]["govde"]
    assert g["suspendReasonId"] == ABONE and g["suspendSubReasonId"] == V_ALT
    assert g["description"] == metin and g["suspendStatusEndDate"] == "16.10.2026 10:55"
    assert ist[0]["yol"] == "/boss-gateway-service/task-service/api/v1/task/suspend"
    # askıdan önce BOSS ekibi saklandı; çekmecede iş başına hâl
    onceki = dict(conn.execute("SELECT is_no, onceki_teknik_id FROM ticket_boss_aski WHERE ticket_id=?", (tid,)).fetchall())
    assert onceki == {_no(1): ortam["ekip"], _no(2): None}
    t = istemci.get(f"/api/ticket/{tid}", headers=ortam["op"]).json()["ticket"]
    assert sorted((x["task_no"], x["durum"], x["boss"]) for x in t["boss_askilar"]) == [
        (_no(1), "askida", "gidiyor"), (_no(2), "askida", "gidiyor")]
    # tekrar yok
    istemci.patch(f"/api/ticket/{tid}", headers=ortam["op"], json={"detay": "x"})
    assert len(_kayitlar(conn, "aski")) == 2


def test_ticket_askisi_kategori_listesi_yoksa_bekler_ve_ister(istemci, conn, ortam):
    """Hiç katalog / alt liste okunmamışsa ticket askısı BEKLER (hata değil; çekmecede alt_neden_bekleniyor) ve işin
    kataloğu eklentiden istenir; sabit / başka kategorinin alt neden kimliği gönderilmez. Liste gelince gider."""
    ortam["esitle"]([_gorev(1, "91000011")])
    tid = _ticket(istemci, ortam, "91000011", [_no(1)])
    kayit = conn.execute("SELECT * FROM boss_yazma WHERE tur='aski'").fetchone()
    g, eksik = boss_yazma.govde_kur(conn, kayit)
    assert eksik == ["suspendSubReasonId"] and g["suspendReasonId"] == ABONE
    assert g["description"] == "TK-9001 ticket id ile altyapıdan çözüm bekler.", "açıklama ticket notu"
    t = istemci.get(f"/api/ticket/{tid}", headers=ortam["op"]).json()["ticket"]
    assert t["boss_askilar"][0]["boss"] == "alt_neden_bekleniyor"
    y = istemci.get("/api/boss/yazilacaklar", headers=ortam["ek"]).json()
    assert not [i for i in y["istekler"] if i["tur"] == "aski"] and NEDEN_YOLU in y["okunacaklar"]
    assert conn.execute("SELECT durum FROM boss_yazma WHERE id=?", (kayit["id"],)).fetchone()[0] == "bekliyor"
    _katalog(conn, network_alt=False)                       # kategori 560 kataloğu + ABONE alt listesi geldi
    boss_yazma.sifirla()
    ist = [i for i in istemci.get("/api/boss/yazilacaklar", headers=ortam["ek"]).json()["istekler"] if i["tur"] == "aski"]
    assert len(ist) == 1 and ist[0]["yaz"] is True and ist[0]["govde"]["suspendSubReasonId"] == V_ALT


def test_eski_network_ticket_kaydi_varsayilan_ciftle_gider(istemci, conn, ortam):
    """Kuyrukta kalmış eski ticket kaydı (NETWORK, boss_alt_otomatik) artık beklemez: varsayılan çiftle gider."""
    _katalog(conn, network_alt=False)
    ortam["esitle"]([_gorev(1, "91000012")])
    from operasyon.v2 import ek_sema
    ek_sema.hazirla(conn)
    conn.execute("INSERT INTO boss_yazma(tur, is_no, task_no, girdi, durum, olusturma, guncelleme) VALUES "
                 "('aski', ?, ?, ?, 'bekliyor', '2026-10-09 10:00:00', '2026-10-09 10:00:00')",
                 (_no(1), _no(1), json.dumps({"boss_neden_ad": "NETWORK", "boss_alt_otomatik": "EK SP",
                                              "boss_bitis": "2026-10-15 10:00:00", "notu": "x"})))
    conn.commit()
    ist = [i for i in istemci.get("/api/boss/yazilacaklar", headers=ortam["ek"]).json()["istekler"] if i["tur"] == "aski"]
    assert len(ist) == 1 and (ist[0]["govde"]["suspendReasonId"], ist[0]["govde"]["suspendSubReasonId"]) == (ABONE, V_ALT)


def test_ayarlar_varsayilan_aski_ve_paralel_yazma(istemci, conn, ortam):
    a = istemci.get("/api/isler/ayarlar", headers=ortam["op"]).json()
    assert a["varsayilan_aski"]["etiket"] == "Abone Kaynaklı > Ulaşılamadı"
    assert a["varsayilan_aski"]["aciklama"] == "Teknik ekibe iletildi"
    assert "ticket_aski_alt_nedenler" not in a and a["boss_yazma_paralel"] == 6
    assert istemci.get("/api/boss/yazilacaklar", headers=ortam["ek"]).json()["paralel"] == 6
    assert istemci.put("/api/isler/ayarlar", headers=ortam["op"], json={"boss_yazma_paralel": 8}).status_code == 403
    r = istemci.put("/api/isler/ayarlar", headers=ortam["admin"], json={"boss_yazma_paralel": 8})
    assert r.status_code == 200 and r.json()["boss_yazma_paralel"] == 8
    assert istemci.get("/api/boss/yazilacaklar", headers=ortam["ek"]).json()["paralel"] == 8
    for kotu in (0, 11, 100):                          # asla 10'dan fazla (BOSS hız sınırı)
        assert istemci.put("/api/isler/ayarlar", headers=ortam["admin"], json={"boss_yazma_paralel": kotu}).status_code == 422
    conn.execute("UPDATE ayar SET deger='50' WHERE anahtar='boss_yazma_paralel'")
    conn.commit()
    assert boss_yazma.paralel(conn) == 10, "elle yazılmış büyük değer de 10'a kırpılır"


def test_toptan_yalniz_bagli_is_ve_anahtar_kapali(istemci, conn, ortam):
    _katalog(conn)
    ortam["esitle"]([_gorev(5, "23700003", kanal="VODAFONE NET"), _gorev(6, "23700003", kanal="VODAFONE NET")])
    _ticket(istemci, ortam, "23700003", [_no(5)])
    assert [x[0] for x in _kayitlar(conn, "aski")] == [_no(5)]
    r = istemci.put("/api/isler/ayarlar", headers=ortam["admin"], json={"ticket_otomatik_aski": False})
    assert r.status_code == 200
    ortam["esitle"]([_gorev(7, "91000014")])
    _ticket(istemci, ortam, "91000014", [_no(7)], ticket_no="TK-9002")
    assert [x[0] for x in _kayitlar(conn, "aski")] == [_no(5)], "anahtar kapalı: askı yok"
    assert len([x for x in _kayitlar(conn, "not") if x[0] == _no(7)]) == 1, "not yine gider"


def test_numarasiz_tickette_aski_numara_girilince(istemci, conn, ortam):
    _katalog(conn)
    ortam["esitle"]([_gorev(1, "91000015")])
    r = istemci.post("/api/ticket", headers=ortam["op"], json={
        "konu": "EK SP", "location_id": LOC, "musteri": "91000015", "isler": [_no(1)]})
    tid = r.json()["ticket"]["id"]
    assert _kayitlar(conn, "aski") == []
    istemci.patch(f"/api/ticket/{tid}", headers=ortam["op"], json={"ticket_no": "TK-9003"})
    assert [x[0] for x in _kayitlar(conn, "aski")] == [_no(1)]


def test_sure_dolmadan_yeniden_aski(istemci, conn, ortam, saat):
    _katalog(conn)
    ortam["esitle"]([_gorev(1, "91000016")])
    tid = _ticket(istemci, ortam, "91000016", [_no(1)])
    assert len(_kayitlar(conn, "aski")) == 1
    assert tba.yenile(conn, zorla=True)["yenilenen"] == 0, "bitişe çok var"
    saat.ilerlet(days=6)
    assert tba.yenile(conn, zorla=True)["yenilenen"] == 1
    k = _kayitlar(conn, "aski")
    assert len(k) == 2 and k[-1][2]["boss_bitis"] == "2026-10-22 10:55:00"
    assert conn.execute("SELECT bitis FROM ticket_boss_aski WHERE ticket_id=?", (tid,)).fetchone()[0] == \
        "2026-10-22 10:55:00"


# ============================================================================= 3. çözümde önceki ekibe geri atama
def test_cozuldu_onceki_ekibe_sonraki_is_gunu_atanir(istemci, conn, ortam):
    _katalog(conn)
    ortam["esitle"]([_gorev(1, "91000020"), _gorev(2, "91000020", "Kanal Şikayeti")])
    _ata(istemci, ortam, _no(1))
    tid = _ticket(istemci, ortam, "91000020", [_no(1)])
    # BOSS askıyı uyguladı: ekip işten alındı (ekip uzlaşması atamayı kaldırır)
    conn.execute("UPDATE is_emri SET atanan_id=NULL, randevu_bas=NULL, randevu_bit=NULL, durum='askida' "
                 "WHERE is_no IN (?,?)", (_no(1), _no(2)))
    conn.commit()
    atama_once = len(_kayitlar(conn, "atama"))
    r = istemci.patch(f"/api/ticket/{tid}", headers=ortam["op"], json={"durum": "ÇÖZÜLDÜ"})
    assert r.status_code == 200, r.text
    a, bas, bit = conn.execute("SELECT atanan_id, randevu_bas, randevu_bit FROM is_emri WHERE is_no=?",
                               (_no(1),)).fetchone()
    assert (a, bas, bit) == (ortam["ekip"], "2026-10-12 08:00:00", "2026-10-12 10:00:00"), "Pazartesi 08–10"
    yeni = _kayitlar(conn, "atama")[atama_once:]
    assert [x[0] for x in yeni] == [_no(1)] and yeni[0][2]["randevu_bas"] == "2026-10-12 08:00:00"
    assert conn.execute("SELECT atanan_id FROM is_emri WHERE is_no=?", (_no(2),)).fetchone()[0] is None
    t = r.json()["ticket"]
    assert sorted((x["task_no"], x["durum"]) for x in t["boss_askilar"]) == [(_no(1), "atandi"), (_no(2), "ekipsiz")]
    # tekrar yok: yeniden kaydetmek yeniden atamaz
    istemci.patch(f"/api/ticket/{tid}", headers=ortam["op"], json={"detay": "y"})
    assert len(_kayitlar(conn, "atama")) == atama_once + 1


def test_cozum_dilimi_ayari_ve_geri_atama_kapali(istemci, conn, ortam):
    _katalog(conn)
    r = istemci.put("/api/isler/ayarlar", headers=ortam["admin"], json={"ticket_cozum_slot": "10:00-12:00"})
    assert r.status_code == 200 and r.json()["ticket_cozum_slot"] == "10:00-12:00"
    assert istemci.put("/api/isler/ayarlar", headers=ortam["admin"],
                       json={"ticket_cozum_slot": "25:00-26:00"}).status_code == 422
    ortam["esitle"]([_gorev(1, "91000021"), _gorev(3, "91000022")])
    _ata(istemci, ortam, _no(1))
    _ata(istemci, ortam, _no(3))
    t1 = _ticket(istemci, ortam, "91000021", [_no(1)])
    t2 = _ticket(istemci, ortam, "91000022", [_no(3)], ticket_no="TK-9004")
    conn.execute("UPDATE is_emri SET atanan_id=NULL, durum='askida' WHERE is_no IN (?,?)", (_no(1), _no(3)))
    conn.commit()
    istemci.patch(f"/api/ticket/{t1}", headers=ortam["op"], json={"durum": "ÇÖZÜLDÜ"})
    assert conn.execute("SELECT randevu_bas FROM is_emri WHERE is_no=?", (_no(1),)).fetchone()[0] == \
        "2026-10-12 10:00:00"
    istemci.put("/api/isler/ayarlar", headers=ortam["admin"], json={"ticket_cozum_yeniden_ata": False})
    istemci.patch(f"/api/ticket/{t2}", headers=ortam["op"], json={"durum": "ÇÖZÜLDÜ"})
    assert conn.execute("SELECT atanan_id FROM is_emri WHERE is_no=?", (_no(3),)).fetchone()[0] is None
    assert conn.execute("SELECT durum FROM ticket_boss_aski WHERE ticket_id=?", (t2,)).fetchone()[0] == "birakildi"


def test_iptal_edilen_tickette_geri_atama_yok_yenile_cozer(istemci, conn, ortam):
    _katalog(conn)
    ortam["esitle"]([_gorev(1, "91000023"), _gorev(3, "91000024")])
    _ata(istemci, ortam, _no(1))
    _ata(istemci, ortam, _no(3))
    t1 = _ticket(istemci, ortam, "91000023", [_no(1)])
    t2 = _ticket(istemci, ortam, "91000024", [_no(3)], ticket_no="TK-9005")
    conn.execute("UPDATE is_emri SET atanan_id=NULL, durum='askida' WHERE is_no IN (?,?)", (_no(1), _no(3)))
    conn.commit()
    istemci.patch(f"/api/ticket/{t1}", headers=ortam["op"], json={"durum": "İPTAL"})
    assert conn.execute("SELECT atanan_id FROM is_emri WHERE is_no=?", (_no(1),)).fetchone()[0] is None
    # Excel'den kapanan ticket (uç çağrılmadı): eşitleme sonundaki yenileme çözer
    conn.execute("UPDATE ticket SET durum='ÇÖZÜLDÜ' WHERE id=?", (t2,))
    conn.commit()
    assert tba.yenile(conn, zorla=True)["cozulen"] == 1
    assert conn.execute("SELECT atanan_id FROM is_emri WHERE is_no=?", (_no(3),)).fetchone()[0] == ortam["ekip"]


def test_cozum_dilimi_hafta_sonu_ve_tatil(conn, saat):
    saat.ayarla("2026-10-28 15:00:00")                       # Çarşamba; 29.10 resmî tatil
    assert tba.cozum_dilimi(conn, dt.datetime(2026, 10, 28, 15)) == ("2026-10-30 08:00:00", "2026-10-30 10:00:00")
    assert tba.slot_coz("8:00-10:00") == ("08:00", "10:00")
    assert tba.slot_coz("10:00-08:00") is None


def test_elle_askida_anlik_goruntu_yoksa_son_bilinen_ekibe_atanir(istemci, conn, ortam):
    """Canlı örnek (09.10): iş, ticket açıldıktan sonra otomatik askıdan ÖNCE elle askıya alındı; BOSS ekibi işten
    düştü, ticket_boss_aski satırı (önceki ekip anlık görüntüsü) yok. Ticket çözülünce son bilinen ekip (iş olay
    geçmişindeki son atama) kullanılır; hiçbir iz yoksa çekmecede "Önceki ekip bilinmiyor — elle atayın"."""
    _katalog(conn)
    r = istemci.put("/api/isler/ayarlar", headers=ortam["admin"], json={"ticket_otomatik_aski": False})
    assert r.status_code == 200
    ortam["esitle"]([_gorev(1, "91000030"), _gorev(2, "91000030", "Kanal Şikayeti")])
    _ata(istemci, ortam, _no(1))
    tid = _ticket(istemci, ortam, "91000030", [_no(1)])
    conn.execute("UPDATE ticket SET olusturma='2026-10-09 10:30:00' WHERE id=?", (tid,))
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM ticket_boss_aski").fetchone()[0] == 0, "anlık görüntü yok"
    for no in (_no(1), _no(2)):                                  # elle askı (uygulamadan; olay geçmişine düşer)
        r = istemci.post(f"/api/isler/{no}/durum", headers=ortam["op"], json={
            "yeni": "askida", "neden": "Abone Kaynaklı / Ulaşılamadı", "uyanma": "2026-10-12 12:00:00"})
        assert r.status_code == 200, r.text
    # BOSS askıyı uyguladı: ekip işten düştü
    conn.execute("UPDATE is_emri SET atanan_id=NULL, boss_ekip=NULL, randevu_bas=NULL, randevu_bit=NULL "
                 "WHERE is_no IN (?,?)", (_no(1), _no(2)))
    conn.commit()
    assert tba.son_bilinen_ekip(conn, _no(1))[0] == ortam["ekip"]
    assert tba.son_bilinen_ekip(conn, _no(2)) == (None, None)
    r = istemci.patch(f"/api/ticket/{tid}", headers=ortam["op"], json={"durum": "ÇÖZÜLDÜ"})
    assert r.status_code == 200, r.text
    a = conn.execute("SELECT atanan_id, randevu_bas FROM is_emri WHERE is_no=?", (_no(1),)).fetchone()
    assert tuple(a) == (ortam["ekip"], "2026-10-12 08:00:00"), "son bilinen ekibe sonraki iş günü"
    t = {x["task_no"]: x for x in r.json()["ticket"]["boss_askilar"]}
    assert t[_no(1)]["durum"] == "atandi" and "uyari" not in t[_no(1)]
    assert t[_no(2)]["durum"] == "ekipsiz" and t[_no(2)]["uyari"] == "Önceki ekip bilinmiyor — elle atayın"


def test_cozumde_bos_anlik_goruntu_son_basarili_atama_yazmasindan(istemci, conn, ortam):
    """Satır var ama önceki ekip boş (askı anında ekip yoktu): çözümde BOSS'a başarılı gitmiş son atama yazmasının
    teknisyeni kullanılır."""
    _katalog(conn)
    ortam["esitle"]([_gorev(1, "91000031")])
    tid = _ticket(istemci, ortam, "91000031", [_no(1)])
    assert conn.execute("SELECT onceki_teknik_id FROM ticket_boss_aski WHERE ticket_id=?", (tid,)).fetchone()[0] is None
    conn.execute("INSERT INTO boss_yazma(tur, is_no, task_no, girdi, durum, olusturma, guncelleme, sonuc) VALUES "
                 "('atama', ?, ?, ?, 'gonderildi', '2026-10-08 10:00:00', '2026-10-08 10:00:00', ?)",
                 (_no(1), _no(1), json.dumps({"teknik_id": ortam["ekip"]}),
                  json.dumps({"durum": "gonderildi", "http": 200, "return_kodu": 0})))
    conn.execute("UPDATE is_emri SET durum='askida' WHERE is_no=?", (_no(1),))
    conn.commit()
    r = istemci.patch(f"/api/ticket/{tid}", headers=ortam["op"], json={"durum": "ÇÖZÜLDÜ"})
    assert r.status_code == 200, r.text
    assert conn.execute("SELECT atanan_id FROM is_emri WHERE is_no=?", (_no(1),)).fetchone()[0] == ortam["ekip"]
    assert r.json()["ticket"]["boss_askilar"][0]["durum"] == "atandi"
