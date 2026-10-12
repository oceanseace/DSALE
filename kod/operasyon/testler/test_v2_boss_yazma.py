"""BOSS'a yazma: Ata / Askıya al / Not → kuyruk → eklentinin yoklaması → önizleme / gerçek istek (yalnız iki yoldan).

Biçimler 07.10'da BOSS'ta elle yapılmış BAŞARILI isteklerden (returnCode 0) alındı; burada gövdeler BİREBİR sınanır.
Eklenti tarafı (kanca yürütücüsü, sahte fetch) kod/eklenti/test.mjs'dedir. BOSS'a hiçbir istek gönderilmez (sunucu
zaten göndermez; "gerçek istek" burada yalnız eklentiye verilen yaz=true talimatıdır).
"""
from __future__ import annotations

import json

import pytest

from operasyon.v2 import akis, api, boss, boss_yazma

U = "0a1b2c3d-1111-2222-3333-{:012d}".format
EKIP_ID = "edf28c9d-0000-4000-8000-000000000077"
KAT, URUN = "106", "Tell_FiberInternetProduct"
NEDEN_YOLU = (f"/boss-gateway-service/task-service/api/v1/task/reasons/task-category/{KAT}/record-type/"
              f"SUSPEND_REASONS/product-code/{URUN}")
ABONE = "26CDE1BE-1B03-8A0A-5384-F0273F623CE7"
ALT = "6f1c2d3e-4b5a-4c6d-8e7f-0123456789ab"
ADMIN_TEL = "5009990001"                     # conftest'teki "yonetici"nin telefonu


@pytest.fixture(autouse=True)
def _temiz():
    boss_yazma.sifirla()
    api._FARKLAR.clear()
    yield
    boss_yazma.sifirla()


def _gorev(i: int, **ek) -> dict:
    no = f"{400000000 + i}"
    g = {"task_no": no, "task_adi": "Bağlantı Problemi", "durum": "Randevusuz", "musteri_no": f"9{no[-7:]}",
         "musteri_adi": "Deneme Müşteri", "adres": f"DENEME APT. Görükle Mh. Test Sk. No:{i} Nilüfer", "il": "Bursa",
         "ilce": "Nilüfer", "acilis": "2026-09-30 09:00:00", "boss_uuid": U(i),
         "ham": {"crmTaskId": no, "taskStatus": "SEND_TO_CENTER", "type": "TECH", "isComplaint": None,
                 "customerName": "Deneme Müşteri", "customerNo": f"9{no[-7:]}", "taskCategory": "Bağlantı Problemi",
                 "taskCategoryType": int(KAT), "productCode": URUN}}
    g.update(ek)
    return g


@pytest.fixture
def ortam(istemci, v2db, conn, jeton, kisi, monkeypatch):
    """3 BOSS işi + BOSS'tan gelen bir teknik ekip; yönetici aynı zamanda Administrator."""
    monkeypatch.setenv("TURKCELL_ADMIN_TELEFON", ADMIN_TEL)
    ek = {"X-Eslesme-Kodu": boss.eslesme_kodu()}
    kanal = _gorev(4)
    kanal["ham"] = {**kanal["ham"], "taskCategory": "Kanal Şikayeti", "isComplaint": None}
    r = istemci.post("/api/boss/esitle", headers=ek, json={
        "gorevler": [_gorev(1), _gorev(2), _gorev(3, boss_uuid=None), kanal], "tam": False,
        "ekipler": [{"ad": "DENEME EKIBI", "id": EKIP_ID, "aktif": True}]})
    assert r.status_code == 200, r.text
    ekip = conn.execute("SELECT id FROM kullanici WHERE boss_ekip_id=?", (EKIP_ID,)).fetchone()[0]
    return {"ek": ek, "op": jeton(kisi["operasyon"]), "admin": jeton(kisi["yonetici"]), "ekip": ekip}


def _h(r) -> dict:
    j = r.json()
    return j.get("detail") if isinstance(j.get("detail"), dict) else j


def _yazilacaklar(istemci, ek):
    r = istemci.get("/api/boss/yazilacaklar", headers=ek)
    assert r.status_code == 200, r.text
    return r.json()


def _ata(istemci, ortam, no="400000001", notu="Müşteri öğleden sonra evde"):
    r = istemci.post(f"/api/isler/{no}/ata", headers=ortam["op"], json={
        "teknik_id": ortam["ekip"], "notu": notu,
        "randevu": {"bas": "2026-10-01 14:00:00", "bit": "2026-10-01 16:00:00", "teyitli": True}})
    assert r.status_code == 200, r.text


def _atama_anahtari(istemci, ortam, deger: str) -> None:
    r = istemci.put("/api/isler/ayarlar", headers=ortam["admin"], json={"boss_yazma_atama": deger})
    assert r.status_code == 200 and r.json()["boss_yazma_atama"] == deger, r.text


def _katalog(istemci, ek, alt: bool = False):
    """Kanca BOSS'un işe özgü askı nedeni kataloğunu (gerçek biçim) tanı olayıyla getirir."""
    r = istemci.post("/api/boss/gunluk", headers=ek, json={"adim": "aski_nedenleri", "yol": NEDEN_YOLU, "ek": {"veri": {
        "content": [{"reasonId": ABONE, "code": "ABONE", "description": "Abone kaynaklı"},
                    {"reasonId": "469061C8-3B17-90F4-3AE2-9254F43B7C28", "code": "DIGER", "description": "Diğer"}]}}})
    assert r.status_code == 200
    if alt:
        r = istemci.post("/api/boss/gunluk", headers=ek, json={
            "adim": "aski_alt_nedenleri", "yol": f"/boss-gateway-service/task-service/api/v1/task/sub-reasons/{ABONE}",
            "ek": {"veri": {"content": [{"subReasonId": ALT, "description": "Malzeme bekleniyor"}]}}})
        assert r.status_code == 200


# ----------------------------------------------------------------------------- gövde biçimleri (birebir)
def test_atama_govdesi_birebir_ve_anahtar_kapaliyken_yalniz_onizleme(istemci, conn, ortam):
    ek, op = ortam["ek"], ortam["op"]
    _atama_anahtari(istemci, ortam, "kapali")
    _ata(istemci, ortam)
    y = _yazilacaklar(istemci, ek)
    assert y["yazma"] == "kapali" and len(y["istekler"]) == 1
    i = y["istekler"][0]
    assert (i["tur"], i["yontem"], i["yol"]) == ("atama", "POST", "/boss-gateway-service/appointment-service/api/v1/appointment")
    assert i["dogrulandi"] is True and i["yaz"] is False, "şablon doğrulandı ama anahtar kapalı: gönderilmez"
    assert "deneme" not in i
    assert isinstance(i["govde"], list) and len(i["govde"]) == 1                 # BOSS gövdesi DİZİ
    g = i["govde"][0]
    assert list(g) == ["taskStatus", "customerFullName", "customerNo", "taskId", "start", "end", "description",
                       "autoId", "isComplaint", "type", "isRetailerTask", "resourceId", "appointmentDate"]
    assert {a: g[a] for a in g if a not in ("customerFullName", "customerNo")} == {
        "taskStatus": "SEND_TO_CENTER", "taskId": U(1), "start": "2026-10-01 14:00:00", "end": "2026-10-01 16:00:00",
        "description": "Müşteri öğleden sonra evde", "autoId": "400000001", "isComplaint": False, "type": "TECH",
        "isRetailerTask": True, "resourceId": EKIP_ID, "appointmentDate": "2001-02-01 00:00:00"}
    assert g["customerFullName"] == "•••(14)" and g["customerNo"] == "•••(8)", "gönderilmeyecek istek maskeli"
    assert _yazilacaklar(istemci, ek)["istekler"] == [], "verilen istek hemen yeniden verilmez"

    s = istemci.post("/api/boss/yazma-sonucu", headers=ek, json={"istek_id": i["istek_id"], "kayitlar": i["kayitlar"],
                                                                   "durum": "onizleme", "hazir": True})
    assert s.json() == {"ok": True, "guncellenen": 1}
    o = istemci.get("/api/isler/400000001/boss-yazma-onizleme", headers=op).json()
    assert o["yazma"] == "kapali" and len(o["kayitlar"]) == 1
    k = o["kayitlar"][0]
    assert k["durum"] == "onizleme" and k["eklenti"]["hazir"] is True and k["eksik"] == []
    assert k["govde"][0]["customerFullName"] == "•••(14)" and k["govde"][0]["start"] == "2026-10-01 14:00:00"
    assert k["tahmini"] == [] and k["dogrulandi"] is True
    boss_yazma.sifirla()
    assert _yazilacaklar(istemci, ek)["istekler"] == [], "önizlemesi alınan kayıt yeniden verilmez"


def test_kanal_sikayeti_iscomplaint_true(istemci, conn, ortam, kim):
    akis.ata(conn, "400000004", ortam["ekip"], kim("operasyon"))
    g, eksik = boss_yazma.govde_kur(conn, conn.execute("SELECT * FROM boss_yazma WHERE is_no='400000004'").fetchone())
    assert g["isComplaint"] is True and eksik == []


def test_not_govdesi_birebir(istemci, conn, ortam):
    r = istemci.post("/api/isler/400000002/not", headers=ortam["op"], json={"metin": "Müşteri aradı"})
    assert r.status_code == 201
    i = _yazilacaklar(istemci, ortam["ek"])["istekler"][0]
    assert (i["tur"], i["yol"], i["dogrulandi"]) == ("not", "/boss-gateway-service/task-service/api/v1/task/note", True)
    assert list(i["govde"].items()) == [("description", "Müşteri aradı"), ("taskId", U(2))]


def _not_olaylari(istemci, ortam, no="400000002"):
    r = istemci.get(f"/api/isler/{no}", headers=ortam["op"])
    assert r.status_code == 200, r.text
    return [o for o in r.json()["olaylar"] if o["tur"] == "not"]


def test_not_ve_atama_kendi_anahtariyla_varsayilan_acik(istemci, conn, ortam):
    """Not ve atama şablonları gerçek yazmayla doğrulandı: genel anahtar KAPALIYKEN de ikisi gerçekten gönderilir
    (yaz=true, eylem_acik). Notun BOSS durumu işin olayında görünür."""
    ek, op, admin = ortam["ek"], ortam["op"], ortam["admin"]
    assert istemci.get("/api/isler/ayarlar", headers=op).json()["boss_yazma_not"] == "acik"
    oz = istemci.get("/api/boss/durum", headers=op).json()["yazma"]
    assert oz["ayar"] == "kapali" and oz["sablonlar"]["not"]["acik"] is True and oz["sablonlar"]["atama"]["acik"] is True
    # askının kendi anahtarı da varsayılan açık, ama alt neden kaynağı bilinene dek şablon doğrulanmamış (önizleme)
    assert oz["sablonlar"]["aski"]["acik"] is True and oz["sablonlar"]["aski"]["dogrulandi"] is False
    olay_id = istemci.post("/api/isler/400000002/not", headers=op, json={"metin": "Müşteri aradı"}).json()["olay_id"]
    _ata(istemci, ortam)
    y = _yazilacaklar(istemci, ek)
    assert y["yazma"] == "kapali"
    tur = {i["tur"]: i for i in y["istekler"]}
    assert (tur["not"]["yaz"], tur["not"]["eylem_acik"]) == (True, True)
    assert tur["not"]["govde"] == {"description": "Müşteri aradı", "taskId": U(2)}, "gönderilecek gövde maskesiz"
    assert (tur["atama"]["yaz"], tur["atama"]["eylem_acik"]) == (True, True)
    assert tur["atama"]["govde"][0]["customerFullName"] == "Deneme Müşteri", "gönderilecek atama maskesiz"
    kayit = conn.execute("SELECT durum, girdi FROM boss_yazma WHERE id=?", (tur["not"]["kayitlar"][0],)).fetchone()
    assert kayit[0] == "gonderiliyor" and json.loads(kayit[1])["olay_id"] == olay_id
    o = _not_olaylari(istemci, ortam)
    assert o[0]["id"] == olay_id and o[0]["boss"]["durum"] == "gonderiliyor"
    assert not any(i["tur"] == "not" for i in _yazilacaklar(istemci, ek)["istekler"]), "not iki kez verilmez"

    istemci.post("/api/boss/yazma-sonucu", headers=ek, json={"istek_id": tur["not"]["istek_id"],
                 "kayitlar": tur["not"]["kayitlar"], "durum": "gonderildi", "http": 200, "return_kodu": 0,
                 "return_mesaji": "Success"})
    assert _not_olaylari(istemci, ortam)[0]["boss"]["durum"] == "gonderildi"

    # BOSS hata döndü → hata (mesajıyla)
    istemci.post("/api/isler/400000002/not", headers=op, json={"metin": "İkinci not"})
    t2 = next(i for i in _yazilacaklar(istemci, ek)["istekler"] if i["tur"] == "not")
    istemci.post("/api/boss/yazma-sonucu", headers=ek, json={"istek_id": t2["istek_id"], "kayitlar": t2["kayitlar"],
                 "durum": "hata", "http": 200, "return_kodu": 12, "return_mesaji": "Görev kapalı", "hata": "boss_12"})
    b = _not_olaylari(istemci, ortam)[0]["boss"]
    assert b["durum"] == "hata" and b["hata"] == "Görev kapalı"

    # not anahtarını yalnız Administrator kapatır; kapalıyken not yalnız önizleme
    assert istemci.put("/api/isler/ayarlar", headers=op, json={"boss_yazma_not": "kapali"}).status_code == 403
    r = istemci.put("/api/isler/ayarlar", headers=admin, json={"boss_yazma_not": "kapali"})
    assert r.status_code == 200 and r.json()["boss_yazma_not"] == "kapali", r.text
    istemci.post("/api/isler/400000002/not", headers=op, json={"metin": "Üçüncü not"})
    assert _not_olaylari(istemci, ortam)[0]["boss"]["durum"] == "kapali"
    t3 = next(i for i in _yazilacaklar(istemci, ek)["istekler"] if i["tur"] == "not")
    assert t3["yaz"] is False and t3["govde"]["description"] == "Üçüncü not"


def test_eksik_alanli_kayit_verilmez_onizlemede_gorunur(istemci, conn, ortam, kisi, kim):
    akis.ata(conn, "400000003", ortam["ekip"], kim("operasyon"))          # BOSS kimliği (uuid) henüz yok
    akis.ata(conn, "400000002", kisi["teknik1"], kim("operasyon"))        # BOSS ekibi değil (resourceId yok)
    assert _yazilacaklar(istemci, ortam["ek"])["istekler"] == []
    o3 = istemci.get("/api/isler/400000003/boss-yazma-onizleme", headers=ortam["op"]).json()["kayitlar"][0]
    o2 = istemci.get("/api/isler/400000002/boss-yazma-onizleme", headers=ortam["op"]).json()["kayitlar"][0]
    assert o3["durum"] == "bekliyor" and "taskId" in o3["eksik"]
    assert "resourceId" in o2["eksik"]


RV = {"bas": "2026-10-01 14:00:00", "bit": "2026-10-01 16:00:00", "teyitli": False}


def test_toplu_atama_tek_dizi_istekte(istemci, conn, ortam):
    r = istemci.post("/api/isler/toplu-ata", headers=ortam["op"], json={"atamalar": [
        {"is_no": "400000001", "teknik_id": ortam["ekip"], "randevu": RV},
        {"is_no": "400000002", "teknik_id": ortam["ekip"], "randevu": RV}]})
    assert r.status_code == 200 and len(r.json()["atanan"]) == 2
    y = _yazilacaklar(istemci, ortam["ek"])
    assert len(y["istekler"]) == 1 and len(y["istekler"][0]["govde"]) == 2 and len(y["istekler"][0]["kayitlar"]) == 2


def test_toplu_atama_ekip_ve_dilim_basina_ayri_istek(istemci, conn, ortam):
    """BOSS isteği ekip + randevu dilimi başına: farklı ekip ya da farklı saat ayrı dizi gövdede gider."""
    ikinci = "edf28c9d-0000-4000-8000-000000000088"
    r = istemci.post("/api/boss/esitle", headers=ortam["ek"], json={
        "gorevler": [], "tam": False, "ekipler": [{"ad": "DENEME EKIBI", "id": EKIP_ID, "aktif": True},
                                                  {"ad": "IKINCI EKIP", "id": ikinci, "aktif": True}]})
    assert r.status_code == 200, r.text
    ekip2 = conn.execute("SELECT id FROM kullanici WHERE boss_ekip_id=?", (ikinci,)).fetchone()[0]
    rv2 = {"bas": "2026-10-01 16:00:00", "bit": "2026-10-01 18:00:00", "teyitli": False}
    r = istemci.post("/api/isler/toplu-ata", headers=ortam["op"], json={"atamalar": [
        {"is_no": "400000001", "teknik_id": ortam["ekip"], "randevu": RV},
        {"is_no": "400000002", "teknik_id": ortam["ekip"], "randevu": rv2},
        {"is_no": "400000004", "teknik_id": ekip2, "randevu": RV}]})
    assert r.status_code == 200 and len(r.json()["atanan"]) == 3, r.text
    istekler = [i for i in _yazilacaklar(istemci, ortam["ek"])["istekler"] if i["tur"] == "atama"]
    assert sorted((g["resourceId"], g["start"]) for i in istekler for g in i["govde"]) == sorted(
        [(EKIP_ID, "2026-10-01 14:00:00"), (EKIP_ID, "2026-10-01 16:00:00"), (ikinci, "2026-10-01 14:00:00")])
    assert len(istekler) == 3
    for i in istekler:
        assert len({(g["resourceId"], g["start"], g["end"]) for g in i["govde"]}) == 1


def test_atama_gruplari_en_cok_on_durum_ve_tekli_ayri():
    ogeler = [({"id": n}, {"resourceId": "A", "start": "s", "end": "e", "taskStatus": "OPEN"}) for n in range(45)]
    ogeler += [({"id": 100}, {"resourceId": "B", "start": "s", "end": "e", "taskStatus": "OPEN"})]
    gruplar = boss_yazma.atama_gruplari(ogeler)
    assert [len(g) for g in gruplar] == [10, 10, 10, 10, 5, 1]
    assert [kk["id"] for kk, _ in gruplar[0]] == list(range(10)), "en eski önce"
    # askıdaki iş açık işlerle aynı isteğe girmez; "Yeniden dene" kaydı tek başına gider
    karisik = [({"id": 1}, {"resourceId": "A", "start": "s", "end": "e", "taskStatus": "OPEN"}),
               ({"id": 2}, {"resourceId": "A", "start": "s", "end": "e", "taskStatus": "SUSPENDED"}),
               ({"id": 3, "girdi": json.dumps({"tekli": True})}, {"resourceId": "A", "start": "s", "end": "e", "taskStatus": "OPEN"}),
               ({"id": 4}, {"resourceId": "A", "start": "s", "end": "e", "taskStatus": "OPEN"})]
    assert [[kk["id"] for kk, _ in g] for g in boss_yazma.atama_gruplari(karisik)] == [[1, 4], [2], [3]]


def test_toplu_atama_ozeti_boss_hali(istemci, conn, ortam):
    """TASKS/MAP "Ata…" özeti: atanan / atlanan (nedeniyle) ve her işin BOSS hâli (gidiyor → ✓ / hata)."""
    op, ek = ortam["op"], ortam["ek"]
    r = istemci.post("/api/isler/toplu-ata", headers=op, json={"atamalar": [
        {"is_no": n, "teknik_id": ortam["ekip"], "randevu": RV} for n in ("400000001", "400000002", "400000003", "999999999")]})
    assert r.status_code == 200, r.text
    j = r.json()
    assert sorted(j["atanan"]) == ["400000001", "400000002", "400000003"]
    assert [a["is_no"] for a in j["atlanan"]] == ["999999999"] and j["atlanan"][0]["hata"]
    nolar = ["400000001", "400000002", "400000003", "400000004"]
    d = istemci.post("/api/boss/atama-durumlari", headers=op, json={"is_nolar": nolar}).json()["durumlar"]
    assert d["400000001"] == {"durum": "gidiyor"} and d["400000002"] == {"durum": "gidiyor"}
    assert d["400000003"]["durum"] == "hata" and "BOSS kimliği" in d["400000003"]["hata"]
    assert d["400000004"] == {"durum": "yok"}
    i = next(x for x in _yazilacaklar(istemci, ek)["istekler"] if x["tur"] == "atama")
    assert sorted(i["kayitlar"]) == i["kayitlar"] and len(i["kayitlar"]) == 2
    k1, k2 = i["kayitlar"]
    istemci.post("/api/boss/yazma-sonucu", headers=ek, json={"istek_id": i["istek_id"], "kayitlar": [k1],
                 "durum": "gonderildi", "http": 200, "return_kodu": 0, "return_mesaji": "Success"})
    istemci.post("/api/boss/yazma-sonucu", headers=ek, json={"istek_id": i["istek_id"], "kayitlar": [k2],
                 "durum": "hata", "http": 200, "return_kodu": 7, "return_mesaji": "Ekip uygun değil"})
    d = istemci.post("/api/boss/atama-durumlari", headers=op, json={"is_nolar": nolar}).json()["durumlar"]
    assert d["400000001"] == {"durum": "tamam"}
    assert d["400000002"] == {"durum": "hata", "hata": "Ekip uygun değil", "yeniden": True}
    _atama_anahtari(istemci, ortam, "kapali")
    istemci.post("/api/isler/400000004/ata", headers=op, json={"teknik_id": ortam["ekip"], "randevu": RV})
    d = istemci.post("/api/boss/atama-durumlari", headers=op, json={"is_nolar": ["400000004"]}).json()["durumlar"]
    assert d["400000004"]["durum"] == "kapali"
    assert istemci.post("/api/boss/atama-durumlari", headers=ek, json={"is_nolar": nolar}).status_code in (401, 403)


def test_yeniden_atama_eskisinin_yerine_gecer(istemci, conn, ortam):
    for _ in range(2):
        r = istemci.post("/api/isler/400000001/ata", headers=ortam["op"], json={"teknik_id": ortam["ekip"]})
        assert r.status_code == 200, r.text
    durumlar = [r[0] for r in conn.execute("SELECT durum FROM boss_yazma WHERE is_no='400000001' ORDER BY id")]
    assert durumlar == ["yerine_yeni", "bekliyor"]


# ----------------------------------------------------------------------------- askı: işe özgü katalog
def test_aski_katalogu_ise_gore_istenir_ve_govde_birebir(istemci, conn, ortam):
    ek, op = ortam["ek"], ortam["op"]
    n = istemci.get("/api/isler/400000002/boss-aski-nedenleri", headers=op).json()
    assert n["bekleniyor"] is True and n["yol"] == NEDEN_YOLU and n["anahtar"] == f"{KAT}|{URUN}"
    assert _yazilacaklar(istemci, ek)["okunacaklar"] == [NEDEN_YOLU], "eklentiden işin kataloğu istenir"
    assert _yazilacaklar(istemci, ek)["okunacaklar"] == [], "aynı katalog hemen yeniden istenmez"

    r = istemci.post("/api/isler/400000002/durum", headers=op, json={"yeni": "askida", "neden": "Malzeme bekleniyor",
                                                                      "uyanma": "2026-10-01 12:00:00"})
    assert r.status_code == 200, r.text
    _katalog(istemci, ek)
    n = istemci.get("/api/isler/400000002/boss-aski-nedenleri", headers=op).json()
    assert n["bekleniyor"] is False and n["nedenler"][0] == {"id": ABONE, "ad": "Abone kaynaklı", "kod": "ABONE", "alt": []}
    assert n["alt_dogrulandi"] is False
    assert [o for o in api._AKIS if o.get("adim") == "aski_nedenleri"][-1]["sayi"] == 2
    assert istemci.get("/api/boss/aski-nedenleri", headers=ek).status_code in (401, 403)   # eşleme kodu değil
    o = istemci.get("/api/isler/400000002/boss-yazma-onizleme", headers=op).json()["kayitlar"][0]
    assert "suspendSubReasonId" in o["eksik"], "alt neden kaynağı yok: gönderilmez"

    _katalog(istemci, ek, alt=True)                    # askı üst nedeninin alt listesi yakalandı: kaynak biliniyor
    n = istemci.get("/api/isler/400000002/boss-aski-nedenleri", headers=op).json()
    assert n["alt_dogrulandi"] is True and n["nedenler"][0]["alt"][0]["id"] == ALT
    boss_yazma.sifirla()
    i = next(x for x in _yazilacaklar(istemci, ek)["istekler"] if x["tur"] == "aski")
    assert i["yol"] == "/boss-gateway-service/task-service/api/v1/task/suspend"
    assert list(i["govde"].items()) == [("taskId", U(2)), ("suspendStatusEndDate", "01.10.2026 12:00"),
                                        ("suspendReasonId", ABONE), ("suspendSubReasonId", ALT),
                                        ("description", boss_yazma.VARSAYILAN_ACIKLAMA)]
    assert i["dogrulandi"] is True and i["yaz"] is True, "alt neden kaynağı bilinince askı kendi anahtarıyla gider"


# ----------------------------------------------------------------------------- genel anahtar (yalnız Administrator)
def test_genel_anahtar_yalniz_administrator_ve_dogrulanmis_sablon(istemci, conn, ortam):
    ek, op, admin = ortam["ek"], ortam["op"], ortam["admin"]
    assert istemci.put("/api/boss/yazma-anahtari", headers=op, json={"acik": True}).status_code == 403
    assert istemci.put("/api/isler/ayarlar", headers=op, json={"boss_yazma": "acik"}).status_code == 403
    r = istemci.put("/api/boss/yazma-anahtari", headers=admin, json={"acik": True})
    assert r.status_code == 200 and r.json()["ayar"] == "acik", r.text
    assert conn.execute("SELECT ozet FROM yonetim_kaydi WHERE eylem='boss_yazma_anahtari' ORDER BY id DESC").fetchone()[0] \
        == json.dumps({"acik": True})

    _ata(istemci, ortam)
    istemci.post("/api/isler/400000002/durum", headers=op, json={"yeni": "askida", "neden": "Malzeme bekleniyor",
                                                                  "uyanma": "2026-10-01 12:00:00"})
    _katalog(istemci, ek, alt=True)
    y = _yazilacaklar(istemci, ek)
    tur = {i["tur"]: i for i in y["istekler"]}
    assert tur["atama"]["yaz"] is True and tur["atama"]["govde"][0]["customerFullName"] == "Deneme Müşteri"
    assert tur["aski"]["yaz"] is True, "alt neden kaynağı bilinen askı şablonu gönderilir"
    assert conn.execute("SELECT durum FROM boss_yazma WHERE id=?", (tur["atama"]["kayitlar"][0],)).fetchone()[0] \
        == "gonderiliyor"
    boss_yazma.sifirla()
    assert not any(i["tur"] == "atama" for i in _yazilacaklar(istemci, ek)["istekler"]), \
        "gerçek istek sonucu gelmese de kendiliğinden yeniden verilmez (çift yazma yok)"
    s = istemci.post("/api/boss/yazma-sonucu", headers=ek, json={
        "istek_id": tur["atama"]["istek_id"], "kayitlar": tur["atama"]["kayitlar"], "durum": "gonderildi", "http": 200,
        "return_kodu": 0, "return_mesaji": "Success"})
    assert s.json()["guncellenen"] == 1
    k = istemci.get("/api/isler/400000001/boss-yazma-onizleme", headers=op).json()["kayitlar"][0]
    assert k["durum"] == "gonderildi" and (k["eklenti"]["return_kodu"], k["eklenti"]["return_mesaji"]) == (0, "Success")

    assert istemci.put("/api/boss/yazma-anahtari", headers=admin, json={"acik": False}).json()["ayar"] == "kapali"


def test_sonucu_gelmeyen_gercek_istek_belirsiz_hata_olur(istemci, conn, ortam):
    istemci.put("/api/boss/yazma-anahtari", headers=ortam["admin"], json={"acik": True})
    istemci.post("/api/isler/400000001/not", headers=ortam["op"], json={"metin": "x"})
    i = _yazilacaklar(istemci, ortam["ek"])["istekler"][0]
    assert i["yaz"] is True
    conn.execute("UPDATE boss_yazma SET guncelleme='2020-01-01 00:00:00' WHERE id=?", (i["kayitlar"][0],))
    conn.commit()
    _yazilacaklar(istemci, ortam["ek"])
    durum, sonuc = conn.execute("SELECT durum, sonuc FROM boss_yazma WHERE id=?", (i["kayitlar"][0],)).fetchone()
    assert durum == "hata" and json.loads(sonuc)["belirsiz"] is True
    # geç gelen gerçek sonuç belirsiz hatanın yerine geçer (eşitleme sürerken bekleyen yazma, 08.10)
    r = istemci.post("/api/boss/yazma-sonucu", headers=ortam["ek"], json={
        "istek_id": i["istek_id"], "kayitlar": i["kayitlar"], "durum": "gonderildi", "http": 200, "return_kodu": 0,
        "return_mesaji": "The operation succeeded."})
    assert r.status_code == 200 and r.json()["guncellenen"] == 1
    durum, sonuc = conn.execute("SELECT durum, sonuc FROM boss_yazma WHERE id=?", (i["kayitlar"][0],)).fetchone()
    assert durum == "gonderildi" and json.loads(sonuc)["return_kodu"] == 0
    # gerçek sonuçlu kayıt ikinci (eski) sonuçla bozulmaz
    r = istemci.post("/api/boss/yazma-sonucu", headers=ortam["ek"], json={
        "istek_id": i["istek_id"], "kayitlar": i["kayitlar"], "durum": "hata", "hata": "x"})
    assert r.json()["guncellenen"] == 0


# ----------------------------------------------------------------------------- tek iş denemesi
def test_tek_is_denemesi_anahtar_kapaliyken_yalniz_bir_istek(istemci, conn, ortam):
    ek, op, admin = ortam["ek"], ortam["op"], ortam["admin"]
    _atama_anahtari(istemci, ortam, "kapali")
    istemci.post("/api/isler/400000001/not", headers=op, json={"metin": "Deneme notu"})
    _ata(istemci, ortam, no="400000002")
    assert istemci.post("/api/boss/yazma-dene", headers=op, json={"is_no": "400000001", "eylem": "not"}).status_code == 403
    r = istemci.post("/api/boss/yazma-dene", headers=admin, json={"is_no": "400000001", "eylem": "atama"})
    assert r.status_code == 422 and _h(r)["kod"] == "kayit_yok"
    r = istemci.post("/api/boss/yazma-dene", headers=admin, json={"is_no": "400000001", "eylem": "not"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["govde"] == {"description": "Deneme notu", "taskId": U(1)} and d["dogrulandi"] is True
    assert conn.execute("SELECT 1 FROM yonetim_kaydi WHERE eylem='boss_yazma_dene' AND hedef='400000001'").fetchone()
    assert istemci.post("/api/boss/yazma-dene", headers=admin,
                        json={"is_no": "400000001", "eylem": "not"}).status_code == 409, "aynı anda tek deneme"

    y = _yazilacaklar(istemci, ek)
    assert y["yazma"] == "kapali"
    gercek = [i for i in y["istekler"] if i["yaz"]]
    assert len(gercek) == 1, "anahtar kapalı: yalnız deneme gerçek"
    i = gercek[0]
    assert (i["deneme"], i["tur"], i["kayitlar"], i["govde"]) == (True, "not", [d["kayit_id"]],
                                                                   {"description": "Deneme notu", "taskId": U(1)})
    assert all(x["yaz"] is False for x in y["istekler"] if x is not i)
    boss_yazma.sifirla()
    assert not any(x["yaz"] for x in _yazilacaklar(istemci, ek)["istekler"]), "deneme bir kez verilir"

    istemci.post("/api/boss/yazma-sonucu", headers=ek, json={"istek_id": i["istek_id"], "kayitlar": i["kayitlar"],
                                                              "durum": "gonderildi", "http": 200, "return_kodu": 0,
                                                              "return_mesaji": "Success"})
    oz = istemci.get("/api/boss/durum", headers=op).json()["yazma"]
    assert oz["deneme"] is None and oz["son_deneme"]["sonuc"]["return_kodu"] == 0
    assert oz["ayar"] == "kapali" and oz["sablonlar"]["not"]["dogrulandi"] is True
    assert oz["sablonlar"]["aski"]["dogrulandi"] is False


def test_deneme_ertelenirse_tekrar_verilir_eksikse_baslamaz(istemci, conn, ortam, kim):
    ek, admin = ortam["ek"], ortam["admin"]
    akis.ata(conn, "400000003", ortam["ekip"], kim("operasyon"))               # uuid yok → eksik
    r = istemci.post("/api/boss/yazma-dene", headers=admin, json={"is_no": "400000003", "eylem": "atama"})
    assert r.status_code == 422 and "taskId" in _h(r)["eksik"]
    istemci.post("/api/isler/400000001/not", headers=ortam["op"], json={"metin": "x"})
    assert istemci.post("/api/boss/yazma-dene", headers=admin, json={"is_no": "400000001", "eylem": "not"}).status_code == 200
    i = next(x for x in _yazilacaklar(istemci, ek)["istekler"] if x.get("deneme"))
    # BOSS başlıkları henüz yakalanmamış: hiçbir şey gönderilmedi → kayıt bekliyor, deneme sürer
    istemci.post("/api/boss/yazma-sonucu", headers=ek, json={"istek_id": i["istek_id"], "kayitlar": i["kayitlar"],
                                                              "durum": "ertelendi", "hata": "istek_yok"})
    assert conn.execute("SELECT durum FROM boss_yazma WHERE id=?", (i["kayitlar"][0],)).fetchone()[0] == "bekliyor"
    assert not any(x.get("deneme") for x in _yazilacaklar(istemci, ek)["istekler"]), "bir dakika beklenir"
    boss_yazma.sifirla()
    assert any(x.get("deneme") for x in _yazilacaklar(istemci, ek)["istekler"])


def test_aski_denemesinde_neden_elle_secilir(istemci, conn, ortam):
    op = ortam["op"]
    istemci.post("/api/isler/400000002/durum", headers=op, json={"yeni": "askida", "neden": "uydurma neden",
                                                                  "uyanma": "2026-10-01 12:00:00"})
    r = istemci.post("/api/boss/yazma-dene", headers=ortam["admin"], json={
        "is_no": "400000002", "eylem": "aski", "aski_neden_id": ABONE, "aski_alt_neden_id": ALT})
    assert r.status_code == 200, r.text
    assert r.json()["govde"]["suspendReasonId"] == ABONE and r.json()["dogrulandi"] is False
    i = next(x for x in _yazilacaklar(istemci, ortam["ek"])["istekler"] if x.get("deneme"))
    assert i["govde"]["suspendSubReasonId"] == ALT and i["yaz"] is True


# ----------------------------------------------------------------------------- değişiklik akışı + izinler
def test_esitleme_farklari(istemci, conn, ortam):
    f = istemci.get("/api/boss/farklar", headers=ortam["op"]).json()["farklar"]
    assert f[0]["yeni"] == ["400000001", "400000002", "400000003", "400000004"]
    g = _gorev(1, durum="Randevu alındı", randevu_bas="2026-10-02 10:00:00")
    r = istemci.post("/api/boss/esitle", headers=ortam["ek"], json={"gorevler": [g, _gorev(5)], "mod": "fark",
                                                                     "kaldirilan": ["400000002"], "tam": True})
    assert r.status_code == 200, r.text
    son = istemci.get("/api/boss/farklar", headers=ortam["op"]).json()["farklar"][0]
    assert (son["yeni"], son["degisen"], son["kapanan"]) == (["400000005"], ["400000001"], ["400000002"])
    assert istemci.get("/api/boss/farklar", headers=ortam["ek"]).status_code in (401, 403)


def test_bayi_isi_ve_hatali_sonuc(istemci, conn, ortam):
    assert boss_yazma.kuyruga_ekle(conn, "not", "yok-boyle-is", {"metin": "x"}, None) is None
    assert boss_yazma.kuyruga_ekle(conn, "uydurma", "400000001", {}, None) is None      # hata fırlatmaz
    r = istemci.post("/api/boss/yazma-sonucu", headers=ortam["ek"], json={"kayitlar": [1], "durum": "gonder"})
    assert r.status_code == 422
    assert istemci.post("/api/boss/yazma-sonucu", json={"kayitlar": [], "durum": "onizleme"}).status_code == 401
    assert istemci.get("/api/boss/yazilacaklar").status_code == 401
    d = istemci.get("/api/boss/durum", headers=ortam["op"]).json()
    assert d["yazma"]["ayar"] == "kapali"
    a = istemci.get("/api/isler/ayarlar", headers=ortam["op"]).json()
    assert a["boss_yazma"] == "kapali"
    for anahtar, izin in {("GET", "/api/boss/yazilacaklar"): "is.yukle", ("POST", "/api/boss/yazma-sonucu"): "is.yukle",
                          ("GET", "/api/isler/{is_no}/boss-yazma-onizleme"): "is.liste",
                          ("GET", "/api/boss/aski-nedenleri"): "is.duzenle",
                          ("GET", "/api/isler/{is_no}/boss-aski-nedenleri"): "is.duzenle",
                          ("PUT", "/api/boss/yazma-anahtari"): "yetkinlik.yonet",
                          ("POST", "/api/boss/yazma-dene"): "yetkinlik.yonet",
                          ("GET", "/api/boss/farklar"): "is.liste"}.items():
        assert api.ROTA_IZNI[anahtar] == izin


def test_teknik_baskasinin_onizlemesini_goremez(istemci, conn, ortam, jeton, kisi):
    assert istemci.get("/api/isler/400000001/boss-yazma-onizleme", headers=jeton(kisi["teknik1"])).status_code == 404


# ----------------------------------------------------------------------------- atama: kendiliğinden BOSS'a
def test_atama_kendiliginden_boss_a_ve_cekmece_hali(istemci, conn, ortam, kim):
    """Uygulamada teknisyen + saat seçilince randevu BOSS'a kendiliğinden gider: resourceId = BOSS ekibi, autoId =
    9 haneli task no. Elle "BOSS'a işlenecek" kutusuna ekip/randevu düşmez. Atanmış işte dilim değişince yeni kayıt
    eskisinin yerine geçer. Önizleme eylem hâlini (eylemler.atama) verir; sonuç çekmecede okunur."""
    ek, op = ortam["ek"], ortam["op"]
    assert istemci.get("/api/isler/ayarlar", headers=op).json()["boss_yazma_atama"] == "acik"
    _ata(istemci, ortam)
    assert conn.execute("SELECT boss_bekleyen FROM is_emri WHERE is_no='400000001'").fetchone()[0] is None
    o = istemci.get("/api/isler/400000001/boss-yazma-onizleme", headers=op).json()
    assert o["eylemler"] == {"atama": "acik", "aski": "kapali", "not": "acik"}
    assert o["kayitlar"][0]["durum"] == "bekliyor"
    i = next(x for x in _yazilacaklar(istemci, ek)["istekler"] if x["tur"] == "atama")
    g = i["govde"][0]
    assert i["yaz"] is True and g["resourceId"] == EKIP_ID and g["autoId"] == "400000001"
    assert (g["start"], g["end"]) == ("2026-10-01 14:00:00", "2026-10-01 16:00:00")
    istemci.post("/api/boss/yazma-sonucu", headers=ek, json={"istek_id": i["istek_id"], "kayitlar": i["kayitlar"],
                 "durum": "gonderildi", "http": 200, "return_kodu": 0, "return_mesaji": "Success"})
    k = istemci.get("/api/isler/400000001/boss-yazma-onizleme", headers=op).json()["kayitlar"][0]
    assert k["durum"] == "gonderildi" and k["eklenti"]["return_kodu"] == 0

    # dilim değişti → yeni atama kaydı (aynı ekip, yeni saat)
    r = istemci.post("/api/isler/400000001/randevu", headers=op, json={
        "bas": "2026-10-02 10:00:00", "bit": "2026-10-02 12:00:00", "teyitli": True})
    assert r.status_code == 200, r.text
    i2 = next(x for x in _yazilacaklar(istemci, ek)["istekler"] if x["tur"] == "atama")
    assert (i2["govde"][0]["start"], i2["govde"][0]["resourceId"]) == ("2026-10-02 10:00:00", EKIP_ID)

    # BOSS hata → hâl ve mesaj önizlemede
    istemci.post("/api/boss/yazma-sonucu", headers=ek, json={"istek_id": i2["istek_id"], "kayitlar": i2["kayitlar"],
                 "durum": "hata", "http": 200, "return_kodu": 7, "return_mesaji": "Ekip uygun değil", "hata": "boss_7"})
    k = istemci.get("/api/isler/400000001/boss-yazma-onizleme", headers=op).json()["kayitlar"][0]
    assert k["durum"] == "hata" and k["eklenti"]["return_mesaji"] == "Ekip uygun değil"


def test_autoid_dokuz_haneli_degilse_gonderilmez(istemci, conn, ortam, kim):
    akis.ata(conn, "400000002", ortam["ekip"], kim("operasyon"))
    kayit = conn.execute("SELECT * FROM boss_yazma WHERE is_no='400000002' AND tur='atama'").fetchone()
    g, eksik = boss_yazma.govde_kur(conn, kayit)
    assert g["autoId"] == "400000002" and eksik == []
    conn.execute("UPDATE boss_yazma SET task_no='12345' WHERE id=?", (kayit["id"],))
    conn.commit()
    ham = boss_yazma.boss_ham.oku(conn, ["12345"])
    assert not ham
    g, eksik = boss_yazma.govde_kur(conn, conn.execute("SELECT * FROM boss_yazma WHERE id=?", (kayit["id"],)).fetchone())
    assert g["autoId"] is None and "autoId" in eksik


def test_atama_anahtari_kapaliyken_elle_kutusu_doner(istemci, conn, ortam):
    _atama_anahtari(istemci, ortam, "kapali")
    assert istemci.put("/api/isler/ayarlar", headers=ortam["op"], json={"boss_yazma_atama": "acik"}).status_code == 403
    _ata(istemci, ortam)
    assert "ekip" in (conn.execute("SELECT boss_bekleyen FROM is_emri WHERE is_no='400000001'").fetchone()[0] or "")
    i = next(x for x in _yazilacaklar(istemci, ortam["ek"])["istekler"] if x["tur"] == "atama")
    assert i["yaz"] is False and i["eylem_acik"] is False


# ----------------------------------------------------------------------------- 07.10: toplu atama 38/38 HTTP 500
def test_atama_gercek_boss_durumu_ve_varsayilan_aciklama(istemci, conn, ortam):
    """taskStatus işin BOSS'taki gerçek durumu (askıdaki işe OPEN gönderilince 500 alındı); açıklama boş gitmez."""
    ek = ortam["ek"]
    g5 = _gorev(5)
    g5["ham"] = {**g5["ham"], "taskStatus": "SUSPENDED"}
    istemci.post("/api/boss/esitle", headers=ek, json={"gorevler": [g5], "tam": False})
    istemci.post("/api/isler/toplu-ata", headers=ortam["op"], json={"atamalar": [
        {"is_no": n, "teknik_id": ortam["ekip"], "randevu": RV} for n in ("400000001", "400000005")]})
    istekler = [x for x in _yazilacaklar(istemci, ek)["istekler"] if x["tur"] == "atama"]
    durumlar = sorted(x["govde"][0]["taskStatus"] for x in istekler)
    assert durumlar == ["SEND_TO_CENTER", "SUSPENDED"], "farklı BOSS durumundaki işler ayrı istekte"
    assert all(x["govde"][0]["description"] == boss_yazma.VARSAYILAN_ACIKLAMA for x in istekler)


def test_hata_yanit_metni_maskeli_ve_yeniden_dene(istemci, conn, ortam):
    ek, op = ortam["ek"], ortam["op"]
    istemci.post("/api/isler/toplu-ata", headers=op, json={"atamalar": [
        {"is_no": n, "teknik_id": ortam["ekip"], "randevu": RV} for n in ("400000001", "400000002")]})
    i = next(x for x in _yazilacaklar(istemci, ek)["istekler"] if x["tur"] == "atama")
    assert len(i["kayitlar"]) == 2
    istemci.post("/api/boss/yazma-sonucu", headers=ek, json={
        "istek_id": i["istek_id"], "kayitlar": i["kayitlar"], "durum": "hata", "http": 500, "hata": "http_500",
        "yanit_metni": json.dumps({"message": "Appointment slot invalid", "customerName": "Ali Veli",
                                   "detail": "tel 05321234567"})})
    s = json.loads(conn.execute("SELECT sonuc FROM boss_yazma WHERE id=?", (i["kayitlar"][0],)).fetchone()[0])
    assert "Ali Veli" not in s["yanit"] and "05321234567" not in s["yanit"]
    d = istemci.post("/api/boss/atama-durumlari", headers=op, json={"is_nolar": ["400000001"]}).json()["durumlar"]
    assert d["400000001"]["durum"] == "hata" and d["400000001"]["hata"].startswith("Appointment slot invalid")
    assert d["400000001"]["yeniden"] is True and "BOSS durumu" in d["400000001"]["hata"]
    # hiçbir şey kendiliğinden yeniden verilmez
    boss_yazma.sifirla()
    assert not [x for x in _yazilacaklar(istemci, ek)["istekler"] if x["tur"] == "atama"]
    r = istemci.post("/api/boss/atama-yeniden", headers=op, json={"is_nolar": ["400000001", "400000002", "400000003"]})
    assert r.status_code == 200, r.text
    assert sorted(r.json()["yeniden"]) == ["400000001", "400000002"]
    assert r.json()["atlanan"][0]["is_no"] == "400000003"
    istekler = [x for x in _yazilacaklar(istemci, ek)["istekler"] if x["tur"] == "atama"]
    assert [len(x["kayitlar"]) for x in istekler] == [1, 1], "yeniden denenen her iş tek başına"
    d = istemci.post("/api/boss/atama-durumlari", headers=op, json={"is_nolar": ["400000001"]}).json()["durumlar"]
    assert d["400000001"] == {"durum": "gidiyor"}
    assert istemci.post("/api/boss/atama-yeniden", headers=ek, json={"is_nolar": ["1"]}).status_code in (401, 403)


# ----------------------------------------------------------------------------- toplu askı
def test_toplu_aski_alt_neden_bekleniyor_sonra_gider(istemci, conn, ortam, saat):
    ek, op = ortam["ek"], ortam["op"]
    saat.ayarla("2026-10-07 10:00:00")
    _katalog(istemci, ek)
    n = istemci.post("/api/isler/toplu-aski/nedenler", headers=op, json={"is_nolar": ["400000001", "400000002"]}).json()
    abone = next(x for x in n["nedenler"] if x["kod"] == "ABONE")
    # varsayılan çift (kullanıcı kararı 09.10) liste gelmeden de seçilebilir; başka alt nedenler liste gelince
    assert abone["alt"] == ["Ulaşılamadı"] and n["alt_biliniyor"] is False and "bekleniyor" in n["aciklama"]
    assert n["varsayilan"] == {"neden": "ABONE", "alt": "Ulaşılamadı"} and n["bekleniyor"] is False
    # 7 günden ileri bitiş reddedilir
    r = istemci.post("/api/isler/toplu-aski", headers=op, json={"is_nolar": ["400000001"], "neden": "ABONE",
                     "alt": "Ulaşılamadı", "bitis": "2026-10-15 10:00:00"})
    assert r.status_code == 422 or r.status_code == 400, r.text
    # alt neden listesi BOSS'tan yakalanır (kalıp öğrenilir)
    r = istemci.post("/api/boss/gunluk", headers=ek, json={
        "adim": "aski_alt_nedenleri", "yol": f"/boss-gateway-service/task-service/api/v1/task/suspend/reason/id/{ABONE}/sub/reasons",
        "ek": {"veri": {"content": [{"id": ALT, "code": "ULASILAMADI", "description": "Ulaşılamadı"}]}}})
    assert r.status_code == 200
    n = istemci.post("/api/isler/toplu-aski/nedenler", headers=op, json={"is_nolar": ["400000001"]}).json()
    assert next(x for x in n["nedenler"] if x["kod"] == "ABONE")["alt"] == ["Ulaşılamadı"]
    assert n["gonderilir"] is True
    r = istemci.post("/api/isler/toplu-aski", headers=op, json={"is_nolar": ["400000001", "400000002", "999999999"],
                     "neden": "ABONE", "alt": "Ulaşılamadı", "bitis": "2026-10-13 18:00:00", "aciklama": "3 kez arandı"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert sorted(j["atanan"]) == ["400000001", "400000002"] and j["atlanan"][0]["is_no"] == "999999999"
    r1 = conn.execute("SELECT durum, uyanma FROM is_emri WHERE is_no='400000001'").fetchone()
    assert r1[0] == "askida" and r1[1] <= "2026-10-13 18:00:00"
    boss_yazma.sifirla()
    aski = [x for x in _yazilacaklar(istemci, ek)["istekler"] if x["tur"] == "aski"]
    assert len(aski) == 2 and all(x["yaz"] for x in aski)
    g = aski[0]["govde"]
    assert (g["suspendReasonId"], g["suspendSubReasonId"], g["suspendStatusEndDate"], g["description"]) == \
        (ABONE, ALT, "13.10.2026 18:00", "3 kez arandı")
    durum = istemci.get("/api/boss/aski-nedenleri", headers=op).json()
    assert durum["alt"]["sablon"].endswith("/suspend/reason/id/{id}/sub/reasons") and f"{KAT}|{URUN}" in durum["kataloglar"]


def test_aski_ornegi_kayit_modundan_bitis_bicimi(istemci, conn, ortam):
    ek = ortam["ek"]
    r = istemci.post("/api/boss/gunluk", headers=ek, json={
        "adim": "deger_ornegi", "yol": "/boss-gateway-service/task-service/api/v1/task/suspend", "ileti": "POST",
        "ek": {"govde": {"taskId": U(1), "suspendStatusEndDate": "2026-10-09 18:00:00", "suspendReasonId": ABONE,
                         "suspendSubReasonId": ALT, "description": "•••(12)"}}})
    assert r.status_code == 200
    o = boss_yazma.aski_alt_durumu(conn)["ornek"]
    assert (o["neden_id"], o["alt_id"], o["bitis_bicimi"]) == (ABONE, ALT, "%Y-%m-%d %H:%M:%S")
    assert boss_yazma.aski_bitis_bicimi(conn) == "%Y-%m-%d %H:%M:%S"


def _alt_liste(istemci, ek):
    r = istemci.post("/api/boss/gunluk", headers=ek, json={
        "adim": "aski_alt_nedenleri", "yol": f"/boss-gateway-service/task-service/api/v1/task/suspend/reason/id/{ABONE}/sub/reasons",
        "ek": {"veri": {"content": [{"id": ALT, "code": "ULASILAMADI", "description": "Ulaşılamadı"}]}}})
    assert r.status_code == 200


def test_tek_is_askisi_cekmeceden_toplu_yolla_boss_a_gider(istemci, conn, ortam, saat):
    """İş çekmecesinin tek iş askısı toplu askıyla AYNI yoldan (POST /api/isler/toplu-aski, tek iş) gider: BOSS ana/alt
    neden kimlikleri işin kataloğundan; iç BTK geçerlilik notu ("Webphone ile arama kaydı yok") BOSS kaydını
    engellemez; "1 hafta sonra" (7 gün sınırı içinde) kabul; askıdaki işte bitiş değişince BOSS'a yeniden yazılır."""
    ek, op = ortam["ek"], ortam["op"]
    saat.ayarla("2026-10-07 10:00:00")
    _katalog(istemci, ek)
    _alt_liste(istemci, ek)
    r = istemci.post("/api/isler/toplu-aski", headers=op, json={"is_nolar": ["400000002"], "neden": "ABONE",
                     "alt": "Ulaşılamadı", "bitis": "2026-10-14 09:55:00", "aciklama": None})
    assert r.status_code == 200, r.text
    assert r.json()["atanan"] == ["400000002"] and r.json()["boss"]["gonderilir"] is True
    a = istemci.get("/api/isler/400000002", headers=op).json()
    assert a["durum"] == "askida"
    boss_yazma.sifirla()
    i = [x for x in _yazilacaklar(istemci, ek)["istekler"] if x["tur"] == "aski"]
    assert len(i) == 1 and i[0]["yaz"] is True
    assert list(i[0]["govde"].items()) == [("taskId", U(2)), ("suspendStatusEndDate", "14.10.2026 09:55"),
                                           ("suspendReasonId", ABONE), ("suspendSubReasonId", ALT),
                                           ("description", boss_yazma.VARSAYILAN_ACIKLAMA)]
    # askıdaki işte bitişi değiştir: eski bekleyen kayıt yerine yenisi
    conn.execute("UPDATE boss_yazma SET durum='bekliyor' WHERE tur='aski'")
    conn.commit()
    r = istemci.post("/api/isler/toplu-aski", headers=op, json={"is_nolar": ["400000002"], "neden": "ABONE",
                     "alt": "Ulaşılamadı", "bitis": "2026-10-08 18:00:00", "aciklama": "Tekrar aranacak"})
    assert r.status_code == 200 and r.json()["atanan"] == ["400000002"], r.text
    bekleyen = conn.execute("SELECT girdi FROM boss_yazma WHERE tur='aski' AND is_no='400000002' AND durum='bekliyor'").fetchall()
    assert len(bekleyen) == 1 and json.loads(bekleyen[0][0])["boss_bitis"].startswith("2026-10-08 18:00")
    o = istemci.get("/api/isler/400000002/boss-yazma-onizleme", headers=op).json()
    assert any(k["tur"] == "aski" for k in o["kayitlar"]), "çekmecedeki BOSS askı hâli bu kayıttan okunur"


def test_tek_is_atamasi_cekmeceden_toplu_yolla_boss_a_gider(istemci, conn, ortam):
    """İş çekmecesinin tek iş ataması toplu atamayla AYNI uçtan (POST /api/isler/toplu-ata, tek öğe + sürüm) gider:
    BOSS'a aynı dizi gövde; toplu panelin gönderdiği biçim (yine_de yok) değişmeden çalışır; eski sürüm atlanır."""
    op, ek = ortam["op"], ortam["ek"]
    surum = istemci.get("/api/isler/400000001", headers=op).json()["surum"]
    r = istemci.post("/api/isler/toplu-ata", headers=op, json={"atamalar": [
        {"is_no": "400000001", "teknik_id": ortam["ekip"], "randevu": RV, "surum": surum}]})
    assert r.status_code == 200 and r.json()["atanan"] == ["400000001"], r.text
    istekler = [i for i in _yazilacaklar(istemci, ek)["istekler"] if i["tur"] == "atama"]
    assert len(istekler) == 1 and len(istekler[0]["govde"]) == 1
    g = istekler[0]["govde"][0]
    assert (g["resourceId"], g["start"], g["end"]) == (EKIP_ID, "2026-10-01 14:00:00", "2026-10-01 16:00:00")
    # eski sürümle ikinci tek atama: çakışma atlanan olarak döner (toplu yolun kısmi başarı kuralı)
    r = istemci.post("/api/isler/toplu-ata", headers=op, json={"atamalar": [
        {"is_no": "400000001", "teknik_id": ortam["ekip"], "randevu": RV, "surum": surum}]})
    assert r.status_code == 200 and r.json()["atanan"] == [] and r.json()["atlanan"][0]["kod"] == "guncel_degil"
    # toplu panelin biçimi (surum / yine_de yok) aynen çalışır
    r = istemci.post("/api/isler/toplu-ata", headers=op, json={"atamalar": [
        {"is_no": "400000002", "teknik_id": ortam["ekip"], "randevu": RV}]})
    assert r.status_code == 200 and r.json()["atanan"] == ["400000002"], r.text


def test_harita_tazele_eklentiden_esitleme_ister(istemci, conn, ortam):
    """MAP ⟳: POST /api/boss/esitle-iste → eklentinin yoklamasına bir kez "esitle": true (art arda basış 20 sn'de bir)."""
    from operasyon.v2 import boss_detay
    boss_detay._ESITLE.update(istendi=0.0, verildi=0.0)
    r = istemci.post("/api/boss/esitle-iste", headers=ortam["op"])
    assert r.status_code == 200 and r.json()["istendi"] is True
    assert istemci.post("/api/boss/esitle-iste", headers=ortam["op"]).json()["istendi"] is False
    assert istemci.get("/api/boss/istekler", headers=ortam["ek"]).json().get("esitle") is True
    assert "esitle" not in istemci.get("/api/boss/istekler", headers=ortam["ek"]).json()


# ----------------------------------------------------------------------------- varsayılan askı: alt neden kategoriye göre
# Kullanıcı kararı (09.10): bütün askılar Abone Kaynaklı (ABONE) > "Ulaşılamadı", not "Teknik ekibe iletildi". ABONE
# kimliği her katalogda aynı; ALT NEDEN KİMLİĞİ KATEGORİYE GÖRE DEĞİŞİR (canlı: kategori 40 → "Ulaşılamadı" 9d1770dd…,
# başka kategoride "Aboneye Ulaşılamadı"). Eskiden sabit 7d5df9a2… her işe gidiyordu.
ALT_40 = "9d1770dd-ee6a-407f-ae3c-07276adfa3ff"        # kategori 40 (ürün kodu yok): "Ulaşılamadı"
ALT_106 = "7d5df9a2-6512-47e2-84de-20871862a531"       # kategori 106: yalnız "Aboneye Ulaşılamadı" (kod ULASILAMADI)
ALT_560 = "5a5a5a5a-0000-4000-8000-000000000560"


def _alt_yolu(guid, kat, urun):
    return (f"/boss-gateway-service/task-service/api/v1/task/reason/id/{guid}/sub/reasons/task-category/{kat}/"
            f"product-code/{urun}")


def _katalog_yolu(kat, urun):
    return (f"/boss-gateway-service/task-service/api/v1/task/reasons/task-category/{kat}/record-type/SUSPEND_REASONS/"
            f"product-code/{urun}")


def _kategorili_isler(istemci, ortam):
    """400000005: kategori 40, ürün kodu yok (Kanal Şikayeti) · 400000006: kategori 560."""
    g40, g560 = _gorev(5), _gorev(6)
    g40["ham"] = {**g40["ham"], "taskCategoryType": 40, "productCode": None, "taskCategory": "Kanal Şikayeti"}
    g560["ham"] = {**g560["ham"], "taskCategoryType": 560}
    r = istemci.post("/api/boss/esitle", headers=ortam["ek"], json={"gorevler": [g40, g560], "tam": False})
    assert r.status_code == 200, r.text


def _alt_listeleri(conn):
    """Canlıdaki gibi: kategori 40'ta "Ulaşılamadı", 106'da yalnız "Aboneye Ulaşılamadı" (560 bilinmiyor)."""
    for kat, urun in (("40", "null"), (KAT, URUN)):
        boss_yazma.nedenleri_yaz(conn, _katalog_yolu(kat, urun), {"content": [
            {"reasonId": ABONE, "code": "ABONE", "description": "Abone Kaynaklı"}]})
    boss_yazma.nedenleri_yaz(conn, _alt_yolu(ABONE, 40, "null"), {"content": [
        {"id": "573F8909-3BD5-6214-731B-313C60A76073", "code": "COZULDU", "description": "Çözüldü"},
        {"id": ALT_40, "code": "ULASILAMADI", "description": "Ulaşılamadı"}]})
    boss_yazma.nedenleri_yaz(conn, _alt_yolu(ABONE, KAT, URUN), {"content": [
        {"id": "8FF0692F-7D52-2687-4FF7-FA423A7263FA", "code": "SOZLESME", "description": "Sözleşme bekleniyor"},
        {"id": ALT_106, "code": "ULASILAMADI", "description": "Aboneye Ulaşılamadı"}]})
    conn.commit()


def _varsayilan_aski(conn, is_no):
    """Ticket askısıyla aynı girdi biçimi (varsayılan çift adlarla; kimlik gönderimde çözülür)."""
    v = boss_yazma.VARSAYILAN_ASKI
    kid = boss_yazma.kuyruga_ekle(conn, "aski", is_no, {"boss_neden_ad": v["neden_kod"], "boss_alt_ad": v["alt_ad"],
                                                        "boss_bitis": "2026-10-12 18:00:00", "notu": "x"}, None)
    conn.commit()
    return conn.execute("SELECT * FROM boss_yazma WHERE id=?", (kid,)).fetchone()


def _basarili_gecmis(conn, task_no, alt_id):
    conn.execute("INSERT INTO boss_yazma(tur, is_no, task_no, girdi, durum, olusturma, guncelleme, sonuc) VALUES "
                 "('aski', ?, ?, ?, 'gonderildi', '2026-10-08 10:00:00', '2026-10-08 10:00:00', ?)",
                 (task_no, task_no, json.dumps({"boss_neden_ad": "ABONE", "boss_alt_ad": "Aboneye Ulaşılamadı",
                                                "boss_alt_neden_id": alt_id}),
                  json.dumps({"durum": "gonderildi", "http": 200, "return_kodu": 0})))
    conn.commit()


def test_varsayilan_cift_ve_ulasilamadi_secimi():
    v = boss_yazma.varsayilan_aski()
    assert (v["neden_kod"], v["neden_id"], v["alt_ad"]) == ("ABONE", ABONE, "Ulaşılamadı")
    assert v["etiket"] == "Abone Kaynaklı > Ulaşılamadı" and v["aciklama"] == "Teknik ekibe iletildi"
    assert "alt_id" not in boss_yazma.VARSAYILAN_ASKI, "sabit alt neden kimliği yok (kategoriye göre değişir)"
    assert boss_yazma.varsayilan_mi("Abone kaynaklı", "ULAŞILAMADI")
    assert boss_yazma.varsayilan_mi("ABONE", "Aboneye Ulaşılamadı"), "eski kayıtların adı da varsayılan sayılır"
    assert not boss_yazma.varsayilan_mi("ABONE", "Sözleşme bekleniyor")
    sec = boss_yazma.ulasilamadi_sec
    assert sec([{"id": "a", "ad": "Aboneye Ulaşılamadı", "kod": "ULASILAMADI"}])["id"] == "a"
    assert sec([{"id": "a", "ad": "Aboneye Ulaşılamadı", "kod": "ULASILAMADI"},
                {"id": "b", "ad": "ULAŞILAMADI", "kod": "X"}])["id"] == "b", "adı tam Ulaşılamadı olan önce"
    assert sec([{"id": "c", "ad": "Sözleşme bekleniyor", "kod": "SOZLESME"}]) is None


def test_varsayilan_alt_neden_isin_kendi_kategorisinden(istemci, conn, ortam, saat):
    """Kategori 40 → adı tam "Ulaşılamadı" olan 9d1770dd; katalogda yalnız "Aboneye Ulaşılamadı" varsa o."""
    saat.ayarla("2026-10-09 10:00:00")
    _kategorili_isler(istemci, ortam)
    _alt_listeleri(conn)
    g, eksik = boss_yazma.govde_kur(conn, _varsayilan_aski(conn, "400000005"))
    assert eksik == [] and (g["suspendReasonId"], g["suspendSubReasonId"]) == (ABONE, ALT_40)
    g, eksik = boss_yazma.govde_kur(conn, _varsayilan_aski(conn, "400000001"))
    assert eksik == [] and g["suspendSubReasonId"] == ALT_106
    # formdan (tek / toplu askı) gelen seçim de aynı: kimlik her iş için kendi kategorisinden
    r = istemci.post("/api/isler/toplu-aski", headers=ortam["op"], json={"is_nolar": ["400000005", "400000002"],
                     "neden": "ABONE", "alt": "Ulaşılamadı", "bitis": "2026-10-12 18:00:00"})
    assert r.status_code == 200 and sorted(r.json()["atanan"]) == ["400000002", "400000005"], r.text
    boss_yazma.sifirla()
    aski = {x["govde"]["taskId"]: x for x in _yazilacaklar(istemci, ortam["ek"])["istekler"] if x["tur"] == "aski"}
    assert aski[U(5)]["govde"]["suspendSubReasonId"] == ALT_40 and aski[U(2)]["govde"]["suspendSubReasonId"] == ALT_106
    assert aski[U(5)]["govde"]["description"] == boss_yazma.VARSAYILAN_ACIKLAMA and aski[U(5)]["yaz"] is True


def test_varsayilan_alt_liste_yoksa_bekler_istenir_baska_kategorininki_kullanilmaz(istemci, conn, ortam, saat):
    """Kategori 560'ın alt listesi yok: kayıt BEKLER (hata değil), liste eklentiden istenir; başka kategorinin
    kimliği (son okunan liste, başka kategorinin başarılı geçmişi) hiçbir zaman gönderilmez. En son çare (≥ 15 dk
    bekledikten sonra): AYNI kategoride daha önce başarılı gitmiş kimlik."""
    saat.ayarla("2026-10-09 10:00:00")
    _kategorili_isler(istemci, ortam)
    _alt_listeleri(conn)
    _basarili_gecmis(conn, "400000001", ALT_106)          # 106'da başarılı geçmiş: 560 için kullanılmaz
    kayit = _varsayilan_aski(conn, "400000006")
    g, eksik = boss_yazma.govde_kur(conn, kayit)
    assert eksik == ["suspendSubReasonId"] and g["suspendReasonId"] == ABONE
    boss_yazma.sifirla()
    y = _yazilacaklar(istemci, ortam["ek"])
    assert not [x for x in y["istekler"] if x["tur"] == "aski"], "alt neden listesi gelmeden gönderilmez"
    assert _alt_yolu(ABONE, 560, URUN) in y["okunacaklar"], "işin KENDİ kategorisinin alt listesi istenir"
    assert not any("task-category/40/" in o or f"task-category/{KAT}/" in o for o in y["okunacaklar"])
    assert conn.execute("SELECT durum FROM boss_yazma WHERE id=?", (kayit["id"],)).fetchone()[0] == "bekliyor"
    saat.ilerlet(minutes=20)
    g, eksik = boss_yazma.govde_kur(conn, kayit)
    assert eksik == ["suspendSubReasonId"], "uzun beklemede bile başka kategorinin kimliği kullanılmaz"
    assert boss_yazma.aski_kimlikleri(conn, "400000006", "ABONE", "Ulaşılamadı")[1] is None
    # en son çare: aynı kategoride (560) başarılı geçmiş → yalnız uzun bekleyen kayıtta
    _basarili_gecmis(conn, "400000006", ALT_560)
    assert boss_yazma.govde_kur(conn, kayit)[0]["suspendSubReasonId"] == ALT_560
    taze = _varsayilan_aski(conn, "400000006")
    assert boss_yazma.govde_kur(conn, taze)[1] == ["suspendSubReasonId"], "yeni kayıt önce listeyi bekler"


def test_varsayilan_alt_liste_gelince_gider_ve_basari_kategoriye_yazilir(istemci, conn, ortam, saat):
    saat.ayarla("2026-10-09 10:00:00")
    _kategorili_isler(istemci, ortam)
    _alt_listeleri(conn)
    _varsayilan_aski(conn, "400000006")
    boss_yazma.sifirla()
    assert not [x for x in _yazilacaklar(istemci, ortam["ek"])["istekler"] if x["tur"] == "aski"]
    r = istemci.post("/api/boss/gunluk", headers=ortam["ek"], json={
        "adim": "aski_alt_nedenleri", "yol": _alt_yolu(ABONE, 560, URUN),
        "ek": {"veri": {"content": [{"id": ALT_560, "code": "ULASILAMADI", "description": "Ulaşılamadı"}]}}})
    assert r.status_code == 200
    aski = [x for x in _yazilacaklar(istemci, ortam["ek"])["istekler"] if x["tur"] == "aski"]
    assert len(aski) == 1 and aski[0]["yaz"] is True and aski[0]["govde"]["suspendSubReasonId"] == ALT_560, \
        "liste gelince bekleyen kayıt hemen verilir"
    s = istemci.post("/api/boss/yazma-sonucu", headers=ortam["ek"], json={
        "istek_id": aski[0]["istek_id"], "kayitlar": aski[0]["kayitlar"], "durum": "gonderildi", "http": 200,
        "return_kodu": 0})
    assert s.json()["guncellenen"] == 1
    m = json.loads(conn.execute("SELECT deger FROM ayar WHERE anahtar='boss_aski_alt_basarili'").fetchone()[0])
    assert m == {f"560|{URUN}": {"alt_id": ALT_560, "zaman": m[f"560|{URUN}"]["zaman"]}}


# ----------------------------------------------------------------------------- yazma kuyruğu (hata ayıklama ekranı)
def test_yazma_kuyrugu_listesi_suzgec_kisisel_veri_yok_ve_yeniden(istemci, conn, ortam, saat, jeton, kisi):
    ek, op = ortam["ek"], ortam["op"]
    _ata(istemci, ortam, "400000001")                                    # atama → gider (saat: 30.09 10:00)
    r = istemci.post("/api/isler/400000002/durum", headers=op, json={"yeni": "askida", "neden": "Malzeme bekleniyor",
                                                                      "uyanma": "2026-09-30 11:30:00"})
    assert r.status_code == 200, r.text                              # askı → katalog yok: eksik alan
    i = next(x for x in _yazilacaklar(istemci, ek)["istekler"] if x["tur"] == "atama")
    s = istemci.post("/api/boss/yazma-sonucu", headers=ek, json={
        "istek_id": i["istek_id"], "kayitlar": i["kayitlar"], "durum": "hata", "http": 500,
        "return_mesaji": "Task is suspended"})
    assert s.json()["guncellenen"] == 1

    y = istemci.get("/api/boss/yazmalar", headers=op)
    assert y.status_code == 200, y.text
    j = y.json()
    k = {x["tur"]: x for x in j["kayitlar"]}
    assert k["atama"]["durum"] == "hata" and k["atama"]["mesaj"].startswith("Task is suspended")
    assert k["atama"]["task_no"] == "400000001" and k["atama"]["yeniden"] is True
    assert k["aski"]["durum"] == "eksik" and any("alt neden" in e or "askı nedeni" in e for e in k["aski"]["eksik"])
    assert j["sayilar"]["hata"] >= 1 and j["sayilar"]["eksik"] == 1
    metin = json.dumps(j, ensure_ascii=False)
    assert "Deneme Müşteri" not in metin and "Görükle" not in metin and "Müşteri öğleden" not in metin, \
        "kişisel veri / not metni dönmez"
    # süzgeç ve arama
    assert {x["tur"] for x in istemci.get("/api/boss/yazmalar?tur=aski", headers=op).json()["kayitlar"]} == {"aski"}
    assert all(x["durum"] == "hata" for x in istemci.get("/api/boss/yazmalar?durum=hata", headers=op).json()["kayitlar"])
    assert {x["task_no"] for x in istemci.get("/api/boss/yazmalar?ara=400000002", headers=op).json()["kayitlar"]} == \
        {"400000002"}
    # tek kayıt yeniden dene: hatalı atama yeniden kuyruğa, eksik askı yalnız yeniden değerlendirilir
    r = istemci.post(f"/api/boss/yazmalar/{k['atama']['id']}/yeniden", headers=op)
    assert r.status_code == 200 and r.json()["yeni_id"], r.text
    yeni = conn.execute("SELECT durum, girdi FROM boss_yazma WHERE id=?", (r.json()["yeni_id"],)).fetchone()
    assert yeni[0] == "bekliyor" and json.loads(yeni[1])["yeniden_of"] == k["atama"]["id"]
    assert istemci.post(f"/api/boss/yazmalar/{k['atama']['id']}/yeniden", headers=op).status_code == 409, \
        "eski kayıt: yenisi geçerli"
    r = istemci.post(f"/api/boss/yazmalar/{k['aski']['id']}/yeniden", headers=op)
    assert r.status_code == 200 and r.json()["durum"] == "eksik" and r.json()["yeni_id"] is None
    # izin: is.ata (teknik göremez)
    assert istemci.get("/api/boss/yazmalar", headers=jeton(kisi["teknik1"])).status_code == 403
    assert api.ROTA_IZNI[("GET", "/api/boss/yazmalar")] == "is.ata"
    assert api.ROTA_IZNI[("POST", "/api/boss/yazmalar/{kayit_id}/yeniden")] == "is.ata"
