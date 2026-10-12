"""TASKS tablosu sözleşmesi: satır uyarıları (altyapı ticket'ı, kanal şikâyeti), satır rengi (işaret) ve BOSS'un
bütün liste alanları (GET /api/isler?ek=1). Görevler eklentinin /api/boss/esitle biçimindedir (adlar uydurma)."""
from __future__ import annotations

from operasyon.v2 import api, boss, boss_ham, ek_sema, isaret, kisi as kisi_mod


def _gorev(i: int, *, task="Bağlantı Problemi", musteri_no=None, durum="Randevusuz", lokasyon=None, ham=None, **ek):
    no = f"{400000000 + i}"
    g = {"task_no": no, "task_adi": task, "durum": durum, "musteri_no": musteri_no or f"9{no[-8:]}",
         "musteri_adi": "Deneme", "adres": f"DENEME APT. Görükle Mh. Test Sk. No:{i} Nilüfer", "il": "Bursa",
         "ilce": "Nilüfer", "acilis": "2026-09-30 09:00:00", "satis_kanali": "GLOBAL CC"}
    if lokasyon:
        g["lokasyon"] = lokasyon
    if ham is not None:
        g["ham"] = ham
    g.update(ek)
    return g


def _esitle(istemci, gorevler, **ek):
    r = istemci.post("/api/boss/esitle", headers={"X-Eslesme-Kodu": boss.eslesme_kodu()},
                     json={"gorevler": gorevler, "tam": False, **ek})
    assert r.status_code == 200, r.text
    return r.json()


def _satir(istemci, h, i, **q):
    d = istemci.get("/api/isler", headers=h, params=q).json()
    return next(x for x in d["isler"] if x["boss_task_no"] == f"{400000000 + i}"), d


def test_kanal_sikayeti_uyarisi_sikayet_disindaki_islerde(istemci, v2db, jeton, kisi):
    _esitle(istemci, [_gorev(1, task="Kanal Şikayeti", musteri_no="11112222"),
                      _gorev(2, task="TV+ Kurulum", musteri_no="11112222"),
                      _gorev(3, task="Kanal Şikayeti", musteri_no="33334444"),
                      _gorev(4, task="Bağlantı Problemi", musteri_no="55556666"),
                      _gorev(5, task="Kanal Şikayeti", musteri_no="55556666")])
    op = jeton(kisi["operasyon"])
    s1, _ = _satir(istemci, op, 1)
    s2, _ = _satir(istemci, op, 2)
    assert s1["uyarilar"] == [], "kanal şikâyeti satırının kendisinde ⚠ yok"
    assert s2["uyarilar"] == [{"tur": "kanal_sikayeti", "metin": "Bu müşterinin kanal şikâyeti var"}]
    assert _satir(istemci, op, 3)[0]["uyarilar"] == []                     # tek işi olan müşteri
    assert _satir(istemci, op, 4)[0]["uyarilar"][0]["metin"] == "Bu müşterinin kanal şikâyeti var"
    assert _satir(istemci, op, 5)[0]["uyarilar"] == []
    # şikâyet kapanınca uyarı kalkar
    _esitle(istemci, [_gorev(1, task="Kanal Şikayeti", musteri_no="11112222", durum="Tamamlandı")])
    assert _satir(istemci, op, 2)[0]["uyarilar"] == []


def test_altyapi_uyarisi_lokasyondaki_acik_ticket(istemci, v2db, conn, jeton, kisi):
    _esitle(istemci, [_gorev(1, lokasyon="99999901"), _gorev(2, lokasyon="99999902")])
    z = "2026-10-01 09:00:00"
    conn.execute("INSERT INTO ticket (konu, durum, location_id, olusturma, guncelleme) VALUES "
                 "('SİNYAL','AÇIK','99999901',?,?), ('ALTYAPI','ÇÖZÜLDÜ','99999902',?,?)", (z, z, z, z))
    conn.commit()
    op = jeton(kisi["operasyon"])
    assert _satir(istemci, op, 1)[0]["uyarilar"] == [{"tur": "altyapi", "metin": "Bu lokasyonda açık altyapı ticket'ı var"}]
    assert _satir(istemci, op, 2)[0]["uyarilar"] == []                     # çözülmüş ticket uyarmaz


def test_isaret_yaz_satirda_ve_degisimde(istemci, v2db, conn, jeton, kisi):
    _esitle(istemci, [_gorev(1), _gorev(2)])
    op = jeton(kisi["operasyon"])
    s, d = _satir(istemci, op, 1)
    assert s["isaret"] is None and "ek" not in s and "ek_etiketler" not in d
    imlec = d["imlec"]
    no = s["is_no"]
    once = list((v2db.parent / "yedek" / "aktarim").glob("*.db")) if (v2db.parent / "yedek" / "aktarim").exists() else []
    r = istemci.post(f"/api/isler/{no}/isaret", headers=op, json={"renk": "sari"})
    assert r.status_code == 200 and r.json() == {"ok": True, "isaret": "sari"}
    assert ek_sema.var_mi(conn, "is_isaret")
    assert len(list((v2db.parent / "yedek" / "aktarim").glob("*.db"))) > len(once), "tablo kurulmadan önce yedek alınır"
    assert _satir(istemci, op, 1)[0]["isaret"] == "sari"
    dg = istemci.get("/api/isler/degisim", headers=op, params={"imlec": imlec}).json()
    assert [x["isaret"] for x in dg["isler"] if x["is_no"] == no] == ["sari"]
    olay = istemci.get(f"/api/isler/{no}", headers=op).json()["olaylar"][0]
    assert olay["tur"] == "isaret" and olay["ozet"] == "Renk: sarı"
    assert istemci.post(f"/api/isler/{no}/isaret", headers=op, json={"renk": "pembe"}).status_code == 422
    assert istemci.post(f"/api/isler/{no}/isaret", headers=jeton(kisi["teknik1"]), json={"renk": "mor"}).status_code == 403
    assert istemci.post(f"/api/isler/{no}/isaret", headers=op, json={"renk": None}).json() == {"ok": True, "isaret": None}
    assert _satir(istemci, op, 1)[0]["isaret"] is None
    assert istemci.post("/api/isler/000000000/isaret", headers=op, json={"renk": "sari"}).status_code == 404
    assert api.ROTA_IZNI[("POST", "/api/isler/{is_no}/isaret")] == "is.duzenle"
    assert isaret.RENKLER == ("sari", "kirmizi", "yesil", "mavi", "mor", "turuncu")   # arayüz IsaretRengi ile aynı


# eslem.js'in müşteri alanı saydığı adlar; eklenti/test.mjs maske bölümü de aynı listeyi sınar.
KISISEL_ORNEKLER = ("customerName", "customerNo", "fullName", "nameSurname", "firstName", "subscriberNo", "contactNo",
                    "mobileNo", "gsm", "msisdn", "address", "tckn", "identityNo", "birthDate")

HAM = {"crmTaskId": "400000001", "customerName": "Deneme Müşteri", "customerNo": "12345678", "saleChannel": "DEHANET",
       "team.name": "EKIP A", "taskStatus": "OPEN", "address": "DENEME APT.", "yeniAlan": 5, "liste": [1, 2],
       "fullName": "Deneme Müşteri", "subscriberNo": "7001234"}


def test_ek_alanlar_ve_etiketler_kisisel_izinle(istemci, v2db, conn, jeton, kisi, monkeypatch):
    _esitle(istemci, [_gorev(1, satis_kanali=None, ham=HAM), _gorev(2)])
    op = jeton(kisi["operasyon"])
    s, d = _satir(istemci, op, 1, ek=1)
    assert s["ek"]["saleChannel"] == "DEHANET" and s["ek"]["customerName"] == "Deneme Müşteri"
    assert s["ek"]["liste"] == "[1, 2]"                                    # sade olmayan değer metne çevrilir
    assert list(d["ek_etiketler"])[:3] == ["crmTaskId", "customerName", "customerNo"]   # BOSS sırası
    assert d["ek_etiketler"]["saleChannel"] == "Satış Kanalı" and d["ek_etiketler"]["yeniAlan"] == "yeniAlan"
    assert _satir(istemci, op, 2, ek=1)[0]["ek"] == {}
    # satış kanalı boş geldi: BOSS'un saleChannel alanından doldurulur
    assert conn.execute("SELECT satis_kanali FROM is_emri WHERE boss_task_no='400000001'").fetchone()[0] == "DEHANET"
    # değişim de aynı alanları taşır
    dg = istemci.get("/api/isler/degisim", headers=op, params={"imlec": 0, "ek": 1}).json()
    assert next(x for x in dg["isler"] if x["boss_task_no"] == "400000001")["ek"]["taskStatus"] == "OPEN"
    assert "saleChannel" in dg["ek_etiketler"]
    # müşteri izni yoksa kişisel alanlar yok
    asil = kisi_mod.izinli
    monkeypatch.setattr(kisi_mod, "izinli", lambda c, k, e: False if e == "is.musteri" else asil(c, k, e))
    s, d = _satir(istemci, op, 1, ek=1)
    assert {"customerName", "customerNo", "address", "fullName", "subscriberNo"}.isdisjoint(s["ek"])
    assert s["ek"]["saleChannel"] == "DEHANET"
    assert "customerName" not in d["ek_etiketler"]


def test_ham_yalniz_acik_islerde(istemci, v2db, conn):
    h2 = {**HAM, "crmTaskId": "400000002"}
    _esitle(istemci, [_gorev(1, ham=HAM), _gorev(2, ham=h2), _gorev(3, ham={"x": 1})])
    say = lambda: {r[0] for r in conn.execute("SELECT task_no FROM boss_ham")}
    assert say() == {"400000001", "400000002", "400000003"}
    _esitle(istemci, [_gorev(1, ham=HAM, durum="Tamamlandı")])            # kapandı → silinir
    assert say() == {"400000002", "400000003"}
    _esitle(istemci, [], mod="fark", kaldirilan=["400000003"])            # BOSS'tan düştü → silinir
    assert say() == {"400000002"}
    _esitle(istemci, [_gorev(4, ham={"y": 2})], tam=True)                 # eksiksiz görüntüde görülmeyen silinir
    assert say() == {"400000004"}
    # saklama: işi kapanmış ham satırı kalmaz
    conn.execute("UPDATE is_emri SET durum='kapandi' WHERE boss_task_no='400000004'")
    conn.commit()
    from operasyon.v2 import saklama
    assert saklama.uygula(conn)["boss_ham_silinen"] == 1 and say() == set()


def test_ham_temizle_sinirlar():
    assert boss_ham.temizle(None) is None and boss_ham.temizle({}) is None
    t = boss_ham.temizle({f"a{i}": "x" * 3000 for i in range(200)})
    assert len(t) == boss_ham.EN_COK_ALAN and len(t["a0"]) == boss_ham.EN_UZUN_DEGER
    assert boss_ham.kisisel_mi("customerName") and boss_ham.kisisel_mi("team.phone")
    assert not boss_ham.kisisel_mi("saleChannel") and not boss_ham.kisisel_mi("customerChurn")
    assert all(boss_ham.kisisel_mi(a) for a in KISISEL_ORNEKLER), [a for a in KISISEL_ORNEKLER if not boss_ham.kisisel_mi(a)]
    assert not any(boss_ham.kisisel_mi(a) for a in ("lastApproval", "taskCategory", "buildingName", "team.name"))


def test_teknik_kendi_isinde_uyari_ve_isaret_alani(istemci, v2db, conn, jeton, kisi, kim):
    _esitle(istemci, [_gorev(1)])
    from operasyon.v2 import akis
    akis.ata(conn, "400000001", kisi["teknik1"], kim("operasyon"))
    x = istemci.get("/api/isler", headers=jeton(kisi["teknik1"])).json()["isler"][0]
    assert x["uyarilar"] == [] and x["isaret"] is None


def test_iliskili_akis_sutunu(istemci, v2db, jeton, kisi):
    """Aynı müşterinin diğer açık işleri: konu başta kısa metin + ilişkili task noları (tek sorgu, satır başına)."""
    from operasyon.v2 import iliskili
    _esitle(istemci, [_gorev(1, task="Kanal Şikayeti", musteri_no="11112222"),
                      _gorev(2, task="Fiber Kurulum", musteri_no="11112222"),
                      _gorev(3, task="TV+ Kurulum", musteri_no="11112222"),
                      _gorev(4, task="Fiber Kurulum(Dönüşüm)", musteri_no="33334444"),
                      _gorev(5, task="Kanal Şikayeti", musteri_no="33334444"),
                      _gorev(6, task="Bağlantı Problemi", musteri_no="33334444"),
                      _gorev(7, task="Bağlantı Problemi", musteri_no="77778888")])
    op = jeton(kisi["operasyon"])
    s1, d = _satir(istemci, op, 1)
    assert s1["iliskili_akis"] == "Yeni Fiber Kurulum + TV+ Kurulum", "şikâyet satırında Yeni/Mevcut önekli"
    assert sorted(s1["iliskili_isler"]) == ["400000002", "400000003"]
    assert _satir(istemci, op, 2)[0]["iliskili_akis"] == "TV+ Kurulum", "kanal şikâyeti hariç (o ⚠)"
    assert _satir(istemci, op, 3)[0]["iliskili_akis"] == "Fiber Kurulum"
    assert _satir(istemci, op, 5)[0]["iliskili_akis"] == "Yeni Fiber Kurulum (Dönüşüm) + Mevcut Bağlantı Problemi"
    assert _satir(istemci, op, 6)[0]["iliskili_akis"] == "Fiber Kurulum (Dönüşüm)"
    assert _satir(istemci, op, 4)[0]["iliskili_akis"] == "Bağlantı Problemi"
    s7 = _satir(istemci, op, 7)[0]
    assert (s7["iliskili_akis"], s7["iliskili_isler"]) == (None, [])
    assert not any("kaydı var" in (x["iliskili_akis"] or "") for x in d["isler"])
    assert iliskili.kategori("TV+ Kurulum(Nakil)") == "yeni" and iliskili.kategori("Modem Değişikliği") == "mevcut"
    assert iliskili.metin("TV+ Arıza", ["Superbox Kurulum", "Cihaz İade Bekleniyor", "TV+ Kurulum(Nakil)", "Kanal Şikayeti"]) ==         "Superbox Kurulum + TV+ Kurulum (Nakil) + Cihaz İade Bekleniyor"
    assert iliskili.metin("Fiber Kurulum", ["Kanal Şikayeti"]) is None
    # ilişkili iş kapanınca kalkar
    _esitle(istemci, [_gorev(2, task="Fiber Kurulum", musteri_no="11112222", durum="Tamamlandı")])
    assert _satir(istemci, op, 1)[0]["iliskili_akis"] == "Yeni TV+ Kurulum"


def test_map_rengi_boss_acik_ama_randevulu(istemci, v2db, jeton, kisi):
    """BOSS listesinde randevulu iş hâlâ 'Açık' görünebilir: satır randevuyu ve BOSS randevu durumunu taşır
    (MAP noktalar.ts katOf bunu SARI boyar; canlı 08.10: 817 / 1.856 'Açık' işte boss_randevu_bas dolu)."""
    _esitle(istemci, [_gorev(1, durum="Açık", randevu_bas="2026-10-09 10:00:00", randevu_bit="2026-10-09 12:00:00"),
                      _gorev(2, durum="Açık")])
    op = jeton(kisi["operasyon"])
    s1, _ = _satir(istemci, op, 1)
    s2, _ = _satir(istemci, op, 2)
    assert s1["boss_durum"] == "Açık"
    assert s1["randevu"] and s1["randevu"]["bas"].startswith("2026-10-09 10:00")
    assert s1["boss_randevu_durumu"] == "Randevulu"
    assert s2["randevu"] is None and s2["boss_randevu_durumu"] == "Randevusuz"


def test_hucre_rengi_yalniz_secili_hucreler_ve_eski_satir_rengi(istemci, v2db, conn, jeton, kisi):
    """Dolgu rengi Excel gibi hücre düzeyinde; eski satır rengi bütün hücrelere uygulanmaya devam eder."""
    _esitle(istemci, [_gorev(1), _gorev(2)])
    op = jeton(kisi["operasyon"])
    s1, d = _satir(istemci, op, 1)
    s2, _ = _satir(istemci, op, 2)
    assert s1["hucre_renk"] == {} and s1["isaret"] is None
    imlec = d["imlec"]
    # iki işin iki hücresi sarı: yalnız o hücreler
    r = istemci.post("/api/isler/hucre-renk", headers=op, json={"renk": "sari", "hucreler": [
        {"is_no": s1["is_no"], "sutun": "ad"}, {"is_no": s1["is_no"], "sutun": "tel"}, {"is_no": s2["is_no"], "sutun": "ad"}]})
    assert r.status_code == 200, r.text
    assert r.json()["isler"] == {s1["is_no"]: {"ad": "sari", "tel": "sari"}, s2["is_no"]: {"ad": "sari"}}
    assert ek_sema.var_mi(conn, "is_hucre_renk")
    y1 = _satir(istemci, op, 1)[0]
    assert y1["hucre_renk"] == {"ad": "sari", "tel": "sari"} and y1["isaret"] is None, "satır rengi değişmez"
    dg = istemci.get("/api/isler/degisim", headers=op, params={"imlec": imlec}).json()
    assert {x["is_no"]: x["hucre_renk"] for x in dg["isler"]}[s2["is_no"]] == {"ad": "sari"}
    # dolgu yok → kayıt silinir
    istemci.post("/api/isler/hucre-renk", headers=op, json={"renk": None, "hucreler": [{"is_no": s1["is_no"], "sutun": "tel"}]})
    assert _satir(istemci, op, 1)[0]["hucre_renk"] == {"ad": "sari"}

    # eski satır rengi (is_isaret) olan iş: bütün hücreler o renkte; "dolgu yok" o hücrede 'yok' olarak kalır
    assert istemci.post(f"/api/isler/{s2['is_no']}/isaret", headers=op, json={"renk": "mavi"}).status_code == 200
    istemci.post("/api/isler/hucre-renk", headers=op, json={"renk": None, "hucreler": [{"is_no": s2["is_no"], "sutun": "tel"}]})
    istemci.post("/api/isler/hucre-renk", headers=op, json={"renk": "mavi", "hucreler": [{"is_no": s2["is_no"], "sutun": "ad"}]})
    y2 = _satir(istemci, op, 2)[0]
    assert y2["isaret"] == "mavi" and y2["hucre_renk"] == {"tel": isaret.YOK}, "satır rengiyle aynı hücre kaydı tutulmaz"

    assert istemci.post("/api/isler/hucre-renk", headers=op, json={"renk": "pembe", "hucreler": [
        {"is_no": s1["is_no"], "sutun": "ad"}]}).status_code == 422
    assert istemci.post("/api/isler/hucre-renk", headers=op, json={"renk": "sari", "hucreler": []}).status_code == 422
    assert istemci.post("/api/isler/hucre-renk", headers=op, json={"renk": "sari", "hucreler": [
        {"is_no": "000000000", "sutun": "ad"}]}).status_code == 404
    assert istemci.post("/api/isler/hucre-renk", headers=jeton(kisi["teknik1"]), json={"renk": "sari", "hucreler": [
        {"is_no": s1["is_no"], "sutun": "ad"}]}).status_code == 403
    assert api.ROTA_IZNI[("POST", "/api/isler/hucre-renk")] == "is.duzenle"


def test_durum_renkleri_varsayilan_ve_yalniz_administrator(istemci, v2db, jeton, kisi, monkeypatch):
    """MAP durum → renk eşlemesi: varsayılan kullanıcının istediği; yalnız Administrator değiştirir."""
    monkeypatch.setenv("TURKCELL_ADMIN_TELEFON", "5009990001")       # conftest'teki "yonetici"
    op = jeton(kisi["operasyon"])
    a = istemci.get("/api/isler/ayarlar", headers=op).json()["durum_renkleri"]
    assert a == api.DURUM_RENK_VARSAYILAN
    assert a["askiya_alindi"] == "mor" and a["ertelendi"] == "kirmizi" and a["merkeze_gonderildi"] == "kirmizi"
    assert a["randevu_alindi"] == "sari" and a["acik_randevulu"] == "sari" and a["acik"] == "gri"
    assert a["basladi"] == "mavi" and a["konum_paylasildi"] == "mavi"
    assert istemci.put("/api/isler/ayarlar", headers=op, json={"durum_renkleri": {"ertelendi": "mor"}}).status_code == 403
    admin = jeton(kisi["yonetici"])
    r = istemci.put("/api/isler/ayarlar", headers=admin, json={"durum_renkleri": {"ertelendi": "mor"}})
    assert r.status_code == 200, r.text
    assert r.json()["durum_renkleri"] == {**api.DURUM_RENK_VARSAYILAN, "ertelendi": "mor"}
    assert istemci.get("/api/isler/ayarlar", headers=op).json()["durum_renkleri"]["ertelendi"] == "mor"
    assert istemci.put("/api/isler/ayarlar", headers=admin, json={"durum_renkleri": {"ertelendi": "pembe"}}).status_code == 422
    assert istemci.put("/api/isler/ayarlar", headers=admin, json={"durum_renkleri": {"uydurma": "mor"}}).status_code == 422
