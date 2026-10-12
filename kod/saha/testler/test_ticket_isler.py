"""Ticket'ın işleri: iş seçicisi (müşteri no / Loc ID → açık işler, varsayılan kurulum işi, kanal şikâyeti ⚠),
çok abone + "+ abone ekle", Task No · Task adı · Satış kanalı · Müşteri No özeti, aynı lokasyonda ticket uyarısı,
kalıcı silme + toplu temizlik (iz bırakmaz, bağlı işler yalnız ayrılır), çözülünce seçilen işler "Aranacak".
Numaralar uydurmadır."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from saha import ayarlar, ticket, ticket_boss_not, ticket_temizlik

BINA, LOC = "BN-0000362608", "O25265408"        # tohum verisindeki bina (test_ticket.py ile aynı)


def _is_ekle(conn, is_no: str, musteri_no: str, task_adi: str = "Fiber Kurulum", kanal: str | None = "DEHANET ECM",
             durum: str = "atandi", lokasyon=LOC, bina_serial=BINA, acilis: str = "2026-09-30 10:00:00",
             bizim: str | None = None) -> str:
    conn.execute(
        "INSERT INTO is_emri (is_no, boss_task_no, kaynak, task_adi, satis_kanali, serit, musteri_no, durum, "
        "durum_zamani, bina_serial, lokasyon, adres, boss_durum, acilis, son24, ilk_gorulme, gorulme_zamani, "
        "guncelleme, bizim_durum) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (is_no, f"2{is_no.zfill(8)}", "boss", task_adi, kanal, "Kurulum", musteri_no, durum, acilis, bina_serial,
         lokasyon, "Örnek Mah. 1. Sok. No 2", "Atandı", acilis, acilis, acilis, acilis, acilis, bizim))
    conn.commit()
    return f"2{is_no.zfill(8)}"


def test_secici_toptan_musteri_kurulum_varsayilan_ve_uyari(istemci, yonetici, conn):
    sikayet = _is_ekle(conn, "11", "23722338", task_adi="Kanal Şikayeti", kanal=None, acilis="2026-10-01 09:00:00")
    kurulum = _is_ekle(conn, "12", "23722338", task_adi="Fiber Kurulum", acilis="2026-09-20 09:00:00")
    ariza = _is_ekle(conn, "13", "23722338", task_adi="Bağlantı Problemi", kanal="GLOBAL CC")
    y = istemci.get("/api/ticket/isler", params={"musteri": "23722338"}, headers=yonetici)
    assert y.status_code == 200, y.text
    v = y.json()
    assert [x["task_no"] for x in v["isler"]][0] == kurulum            # kurulum önce
    assert {x["task_no"] for x in v["isler"]} == {sikayet, kurulum, ariza}
    assert v["varsayilan"] == [kurulum]                                 # kanal şikâyeti asla varsayılan değil
    k = next(x for x in v["isler"] if x["task_no"] == kurulum)
    assert k["satis_kanali"] == "DEHANET ECM" and k["boss_durum"] == "Atandı" and k["adres"]
    assert k["uyari"] == "Bu müşterinin kanal şikâyeti var"            # TASKS'la aynı ⚠
    assert next(x for x in v["isler"] if x["task_no"] == sikayet)["uyari"] == ""
    assert istemci.get("/api/ticket/isler", headers=yonetici).status_code == 400


def test_secici_loc_id_hepsi_ve_cok_aboneli_ticket(istemci, yonetici, conn):
    a = _is_ekle(conn, "21", "73874320")
    b = _is_ekle(conn, "22", "73874321", task_adi="TV+ Kurulum", kanal="GLOBAL CC")
    c = _is_ekle(conn, "23", "73874322", task_adi="Bağlantı Problemi")
    v = istemci.get("/api/ticket/isler", params={"loc": LOC}, headers=yonetici).json()
    assert {a, b, c} <= {x["task_no"] for x in v["isler"]} and v["bina_serial"] == BINA
    y = istemci.post("/api/ticket", headers=yonetici, json={"konu": "EK SP", "location_id": LOC, "isler": [a, b]})
    assert y.status_code == 201, y.text
    t = y.json()["ticket"]
    assert t["task_no"] == f"{a}, {b}" and t["task_adi"] == "Fiber Kurulum +1"
    assert t["satis_kanali"] == "DEHANET ECM, GLOBAL CC"
    assert t["musteriler"] == ["73874320", "73874321"] and t["musteri"] == "73874320, 73874321"
    # "+ abone ekle": sonradan üçüncü abone; tekrar eklemek etkisiz
    e = istemci.post(f"/api/ticket/{t['id']}/isler", headers=yonetici, json={"isler": [c, a, "999"]})
    assert e.status_code == 200 and e.json()["eklenen"] == [c] and e.json()["bulunmayan"] == ["999"]
    t2 = e.json()["ticket"]
    assert t2["musteriler"] == ["73874320", "73874321", "73874322"] and len(t2["isler"]) == 3
    satir = next(x for x in istemci.get("/api/ticket", headers=yonetici).json()["ticketlar"] if x["id"] == t["id"])
    assert satir["task_no"] == f"{a}, {b}, {c}"
    # çıkar
    cik = istemci.post(f"/api/ticket/{t['id']}/isler/cikar", headers=yonetici, json={"isler": [c]})
    assert cik.status_code == 200 and len(cik.json()["ticket"]["isler"]) == 2
    # yeni ticket'ta aynı lokasyon uyarısı (engellemez)
    v = istemci.get("/api/ticket/isler", params={"loc": LOC}, headers=yonetici).json()
    assert any(x["id"] == t["id"] and x["acik"] for x in v["benzer"])


def test_engel_bagli_isler_ayni_listede(istemci, yonetici, conn):
    a = _is_ekle(conn, "31", "70000031")
    t = istemci.post("/api/ticket", headers=yonetici, json={"konu": "SİNYAL", "location_id": LOC}).json()["ticket"]
    conn.execute("UPDATE is_emri SET ticket_id=?, durum='altyapi' WHERE is_no='31'", (t["id"],))
    conn.commit()
    k = istemci.get(f"/api/ticket/{t['id']}", headers=yonetici).json()["ticket"]
    assert [x["task_no"] for x in k["isler"]] == [a] and k["isler"][0]["bagli"] and not k["isler"][0]["secildi"]


def test_cozulunce_secilen_isler_aranacak_iptal_dokunulmaz(istemci, yonetici, conn):
    a = _is_ekle(conn, "41", "70000041")
    b = _is_ekle(conn, "42", "70000042", bizim="İptal")
    c = _is_ekle(conn, "43", "70000043", bizim="Port yok")
    t = istemci.post("/api/ticket", headers=yonetici,
                     json={"konu": "EK SP", "location_id": LOC, "isler": [a, b, c]}).json()["ticket"]
    y = istemci.patch(f"/api/ticket/{t['id']}", headers=yonetici, json={"durum": "ÇÖZÜLDÜ"})
    assert y.status_code == 200, y.text
    assert sorted(y.json()["donen_tasklar"]) == sorted([a, c])
    bizim = {r[0]: r[1] for r in conn.execute("SELECT is_no, bizim_durum FROM is_emri WHERE is_no IN ('41','42','43')")}
    assert bizim == {"41": "Aranacak", "42": "İptal", "43": "Aranacak"}


TICKET_TABLOLARI = ("ticket_is", "ticket_gecmis", "ticket_ek", "ticket_boss_not")


def _iz_yok(conn, tid: int) -> None:
    """Silinen ticket'tan hiçbir tabloda satır kalmaz; yonetim_kaydi'na da yazılmaz."""
    assert conn.execute("SELECT COUNT(*) FROM ticket WHERE id=?", (tid,)).fetchone()[0] == 0
    for tablo in TICKET_TABLOLARI:
        assert conn.execute(f"SELECT COUNT(*) FROM {tablo} WHERE ticket_id=?", (tid,)).fetchone()[0] == 0, tablo
    assert conn.execute("SELECT name FROM sqlite_master WHERE name='ticket_silme'").fetchone() is None
    assert conn.execute("SELECT COUNT(*) FROM is_emri WHERE ticket_id=?", (tid,)).fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM yonetim_kaydi WHERE hedef=? AND eylem LIKE 'ticket%'",
                        (str(tid),)).fetchone()[0] == 0


def _foto_ekle(conn, tid: int) -> Path:
    from saha import ek_dosya
    d = ek_dosya.ticket_dizini(tid)
    (d / "kucuk").mkdir(parents=True, exist_ok=True)
    (d / "abc.jpg").write_bytes(b"x")
    (d / "kucuk" / "abc.jpg").write_bytes(b"y")
    conn.execute("INSERT INTO ticket_ek (ticket_id, dosya_adi, boyut, sha256, olusturma) VALUES (?,?,?,?,?)",
                 (tid, "foto.jpg", 1, "abc", "2026-10-01 10:00:00"))
    conn.commit()
    return d


def test_silme_kalici_iz_birakmaz_isler_yalniz_ayrilir(istemci, yonetici, conn):
    a = _is_ekle(conn, "51", "70000051")                                      # bağlı, açık (altyapı bekliyor)
    _is_ekle(conn, "52", "70000052", durum="kapandi")                         # bağlı, kapanmış
    secilen = _is_ekle(conn, "53", "70000053")                                # yalnız seçilen (ticket_is)
    t = istemci.post("/api/ticket", headers=yonetici,
                     json={"konu": "SİNYAL", "location_id": LOC, "isler": [secilen]}).json()["ticket"]
    tid = t["id"]
    conn.execute("UPDATE is_emri SET ticket_id=?, durum='altyapi' WHERE is_no='51'", (tid,))
    conn.execute("UPDATE is_emri SET ticket_id=? WHERE is_no='52'", (tid,))
    ticket_boss_not.sema(conn)
    conn.execute("INSERT INTO ticket_boss_not (ticket_id, is_no, task_no, metin, olay_id, zaman) "
                 "VALUES (?,?,?,?,?,?)", (tid, "51", a, "X ticket id ile altyapıdan çözüm bekler.", None, "2026-10-01"))
    conn.commit()
    foto = _foto_ekle(conn, tid)
    for tablo in TICKET_TABLOLARI:
        assert conn.execute(f"SELECT COUNT(*) FROM {tablo} WHERE ticket_id=?", (tid,)).fetchone()[0] > 0, tablo
    once = {r["is_no"]: dict(r) for r in conn.execute("SELECT * FROM is_emri WHERE is_no IN ('51','52','53')")}
    olay_once = {n: conn.execute("SELECT COUNT(*) FROM is_emri_olay WHERE is_no=?", (n,)).fetchone()[0]
                 for n in ("51", "52", "53")}

    y = istemci.post(f"/api/ticket/{tid}/sil", headers=yonetici)
    assert y.status_code == 200, y.text
    assert y.json()["silindi"] and y.json()["ayrilan_is"] == 1

    _iz_yok(conn, tid)
    assert not foto.exists()
    assert istemci.get(f"/api/ticket/{tid}", headers=yonetici).status_code == 404
    assert all(x["id"] != tid for x in istemci.get("/api/ticket", headers=yonetici).json()["ticketlar"])
    # İşler: yalnız bağ (açık iş 'altyapi'dan bekliyor'a, geçmişine nötr bir satır); başka hiçbir şey değişmez
    sonra = {r["is_no"]: dict(r) for r in conn.execute("SELECT * FROM is_emri WHERE is_no IN ('51','52','53')")}
    assert sonra["51"]["ticket_id"] is None and sonra["51"]["durum"] == "bekliyor"
    assert sonra["52"]["ticket_id"] is None and sonra["52"]["durum"] == "kapandi"
    oynar = {"ticket_id", "durum", "durum_zamani", "surum", "guncelleme", "oneri_sira", "oneri_neden"}
    for n in ("51", "52"):
        assert {c: v for c, v in sonra[n].items() if c not in oynar} == \
            {c: v for c, v in once[n].items() if c not in oynar}, n
    assert sonra["53"] == once["53"]
    olaylar = conn.execute("SELECT notu FROM is_emri_olay WHERE is_no='51' ORDER BY id").fetchall()
    assert len(olaylar) == olay_once["51"] + 1 and olaylar[-1]["notu"] == "Ticket'tan ayrıldı"
    for n in ("52", "53"):
        assert conn.execute("SELECT COUNT(*) FROM is_emri_olay WHERE is_no=?", (n,)).fetchone()[0] == olay_once[n]
    # İkinci silme / olmayan ticket: 404
    assert istemci.post(f"/api/ticket/{tid}/sil", headers=yonetici).status_code == 404
    assert istemci.post("/api/ticket/999999/sil", headers=yonetici).status_code == 404
    # Yeni ticket eski numarayı almaz (AUTOINCREMENT)
    yeni = istemci.post("/api/ticket", headers=yonetici, json={"konu": "SİNYAL", "location_id": LOC}).json()["ticket"]
    assert yeni["id"] > tid and not yeni["isler"]


def test_silme_tek_islem_hata_olursa_hicbir_sey_silinmez(istemci, yonetici, conn, monkeypatch):
    _is_ekle(conn, "54", "70000054")
    t = istemci.post("/api/ticket", headers=yonetici, json={"konu": "SİNYAL", "location_id": LOC}).json()["ticket"]
    conn.execute("UPDATE is_emri SET ticket_id=?, durum='altyapi' WHERE is_no='54'", (t["id"],))
    conn.commit()
    foto = _foto_ekle(conn, t["id"])

    def bozuk(c, tid):
        c.execute("DELETE FROM ticket_gecmis WHERE ticket_id=?", (tid,))
        raise RuntimeError("yarıda")
    monkeypatch.setattr(ticket, "_satirlari_sil", bozuk)
    with pytest.raises(RuntimeError):
        ticket.sil(conn, t["id"], None)
    r = conn.execute("SELECT ticket_id, durum FROM is_emri WHERE is_no='54'").fetchone()
    assert r["ticket_id"] == t["id"] and r["durum"] == "altyapi"
    assert conn.execute("SELECT COUNT(*) FROM ticket_gecmis WHERE ticket_id=?", (t["id"],)).fetchone()[0] > 0
    assert conn.execute("SELECT COUNT(*) FROM ticket WHERE id=?", (t["id"],)).fetchone()[0] == 1
    assert foto.exists()


def test_toplu_temizlik_yalniz_cozulmus_ve_90_gunden_eski(istemci, yonetici, conn):
    def yeni(loc):
        return istemci.post("/api/ticket", headers=yonetici,
                            json={"konu": "SİNYAL", "location_id": loc}).json()["ticket"]
    eski, yakin, acik, kapali_eski, iptal_eski = (yeni(f"X{i}") for i in range(1, 6))
    for t, d in ((eski, "ÇÖZÜLDÜ"), (yakin, "ÇÖZÜLDÜ"), (kapali_eski, "KAPATILDI"), (iptal_eski, "İPTAL")):
        istemci.patch(f"/api/ticket/{t['id']}", headers=yonetici, json={"durum": d})
    for t in (eski, acik, kapali_eski, iptal_eski):
        conn.execute("UPDATE ticket SET kapanis='2026-01-01 10:00:00', guncelleme='2026-01-01 10:00:00', "
                     "acilis='2025-12-01' WHERE id=?", (t["id"],))
    sinirda = (ayarlar.bugun() - dt.timedelta(days=89)).isoformat() + " 10:00:00"   # 89 gün: kalır
    conn.execute("UPDATE ticket SET kapanis=? WHERE id=?", (sinirda, yakin["id"]))
    conn.commit()
    foto = _foto_ekle(conn, eski["id"])
    assert istemci.get("/api/ticket/temizlik", headers=yonetici).json()["sayi"] == 1
    y = istemci.post("/api/ticket/temizlik", headers=yonetici, json={"gun": 90})
    assert y.status_code == 200 and y.json()["silinen"] == 1
    _iz_yok(conn, eski["id"])
    assert not foto.exists()
    kalan = {r[0] for r in conn.execute("SELECT id FROM ticket")}
    assert {yakin["id"], acik["id"], kapali_eski["id"], iptal_eski["id"]} <= kalan
    assert conn.execute("SELECT COUNT(*) FROM yonetim_kaydi WHERE eylem LIKE 'ticket_%'").fetchone()[0] == 0
    assert istemci.get("/api/ticket/temizlik", headers=yonetici).json()["sayi"] == 0


def test_eski_yumusak_silinenler_bir_kez_kalici_silinir(istemci, yonetici, conn, db_yolu, tmp_path):
    _is_ekle(conn, "55", "70000055", durum="kapandi")
    sil = istemci.post("/api/ticket", headers=yonetici, json={"konu": "SİNYAL", "location_id": "Y1"}).json()["ticket"]
    kal = istemci.post("/api/ticket", headers=yonetici, json={"konu": "SİNYAL", "location_id": "Y2"}).json()["ticket"]
    conn.execute("UPDATE is_emri SET ticket_id=? WHERE is_no='55'", (sil["id"],))
    conn.execute("CREATE TABLE ticket_silme (ticket_id INTEGER PRIMARY KEY, zaman TEXT NOT NULL, "
                 "kullanici_id INTEGER, neden TEXT)")
    conn.execute("INSERT INTO ticket_silme VALUES (?, '2026-10-01', NULL, 'elle')", (sil["id"],))
    conn.commit()
    ek = tmp_path / "ek"
    (ek / "ticket" / str(sil["id"])).mkdir(parents=True)
    (ek / "ticket" / str(sil["id"]) / "a.jpg").write_bytes(b"x")
    s = ticket_temizlik.silinenler_calistir(conn, db_yolu, ek)
    assert s and s["ticket"] == 1 and Path(s["yedek"]).exists() and s["foto_klasoru_silinen"] == 1
    _iz_yok(conn, sil["id"])
    assert not (ek / "ticket" / str(sil["id"])).exists()
    assert conn.execute("SELECT COUNT(*) FROM ticket WHERE id=?", (kal["id"],)).fetchone()[0] == 1
    assert ticket_temizlik.silinenler_calistir(conn, db_yolu, ek) is None          # tablo yok: yapılmış


def test_secici_yetkisi(istemci, yonetici, conn, kisi, monkeypatch):
    _is_ekle(conn, "61", "70000061")
    from saha import yonetim_uclari
    gercek = yonetim_uclari.izinli
    monkeypatch.setattr(yonetim_uclari, "izinli", lambda k, e: e != "is.musteri" and gercek(k, e))
    assert istemci.get("/api/ticket/isler", params={"musteri": "70000061"}, headers=yonetici).status_code == 403
    v = istemci.get("/api/ticket/isler", params={"loc": LOC}, headers=yonetici).json()
    assert v["isler"] and all(x["adres"] == "" and x["musteri_no"] == "" for x in v["isler"])
    monkeypatch.setattr(yonetim_uclari, "izinli", gercek)
    _, teknik = kisi("teknik")
    assert istemci.get("/api/ticket/isler", params={"loc": LOC}, headers=teknik).status_code == 403
    assert istemci.post("/api/ticket/1/sil", headers=teknik).status_code == 403
