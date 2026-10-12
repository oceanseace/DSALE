"""Excel satırı gibi yeni ticket: Müşteri No → Loc ID · bina adı · Task adı · Task No (müşterinin açık işinden);
birden çok müşteri no; ``/api/ticket/musteri`` yetkisi (ticket.defter + is.musteri); tek seferlik defter sıfırlama
(yedekli, etkisiz, güzergah satırları kalır). Numaralar uydurmadır."""
from __future__ import annotations

from pathlib import Path

from saha import ticket, ticket_temizlik

BINA, LOC = "BN-0000362608", "O25265408"        # tohum verisindeki bina (test_ticket.py ile aynı)
SITE = "MERSA SİT. D BLK. MERSA D"


def _is_ekle(conn, is_no: str, musteri_no: str, durum: str = "atandi", bina_serial=BINA, lokasyon=LOC,
             task_adi: str = "Yeni Bağlantı Kurulum", acilis: str = "2026-09-30 10:00:00") -> None:
    conn.execute(
        "INSERT INTO is_emri (is_no, boss_task_no, kaynak, task_adi, serit, musteri_no, durum, durum_zamani, "
        "bina_serial, lokasyon, acilis, son24, ilk_gorulme, gorulme_zamani, guncelleme) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (is_no, f"9{is_no.zfill(8)}", "boss", task_adi, "Arıza", musteri_no, durum, acilis, bina_serial, lokasyon,
         acilis, acilis, acilis, acilis, acilis))
    conn.commit()


def test_musteri_nolari_ayrilir():
    assert ticket.musteri_nolari(" 111, 222 ;333  111\n444 ") == ["111", "222", "333", "444"]
    assert ticket.musteri_nolari("") == [] and ticket.musteri_nolari(None) == []


def test_musteri_bilgisi_acik_isi_tercih_eder(conn):
    _is_ekle(conn, "1", "70000001", durum="kapandi", task_adi="Eski Arıza", acilis="2026-09-01 09:00:00")
    _is_ekle(conn, "2", "70000001", task_adi="Yeni Bağlantı Kurulum", acilis="2026-08-01 09:00:00")
    b = ticket.musteri_bilgisi(conn, " 70000001 ")
    assert b["bulundu"] and b["acik"]
    assert (b["lokasyon"], b["bina_serial"], b["bina_adi"]) == (LOC, BINA, SITE)
    assert (b["task_adi"], b["task_no"]) == ("Yeni Bağlantı Kurulum", "900000002")


def test_musteri_bilgisi_binasiz_is_ve_bulunmayan(conn):
    _is_ekle(conn, "3", "70000003", bina_serial=None, lokasyon=LOC.lower())   # bina Loc ID'den bulunur
    b = ticket.musteri_bilgisi(conn, "70000003")
    assert b["bina_serial"] == BINA and b["lokasyon"] == LOC and b["bina_adi"] == SITE
    _is_ekle(conn, "4", "70000004", durum="kapandi", bina_serial=None, lokasyon="X999")
    b = ticket.musteri_bilgisi(conn, "70000004")
    assert b["bulundu"] and not b["acik"] and b["lokasyon"] == "X999" and b["bina_adi"] == ""
    yok = ticket.musteri_bilgisi(conn, "123")
    assert yok["bulundu"] is False and yok["lokasyon"] == "" and yok["task_adi"] == ""


def test_musteri_ucu_ve_yetki(istemci, yonetici, conn, kisi, monkeypatch):
    _is_ekle(conn, "5", "70000005")
    y = istemci.get("/api/ticket/musteri", params={"no": "123, 70000005"}, headers=yonetici)
    assert y.status_code == 200, y.text
    v = y.json()
    assert v["musteri_no"] == "70000005" and v["lokasyon"] == LOC and v["task_adi"] == "Yeni Bağlantı Kurulum"
    assert [x["bulundu"] for x in v["sonuclar"]] == [False, True]
    assert istemci.get("/api/ticket/musteri", params={"no": " , "}, headers=yonetici).status_code == 400
    # ticket defteri var, müşteri bilgisi izni yok → 403
    from saha import yonetim_uclari
    gercek = yonetim_uclari.izinli
    monkeypatch.setattr(yonetim_uclari, "izinli", lambda k, e: e != "is.musteri" and gercek(k, e))
    assert istemci.get("/api/ticket/musteri", params={"no": "70000005"}, headers=yonetici).status_code == 403
    monkeypatch.setattr(yonetim_uclari, "izinli", gercek)
    _, teknik = kisi("teknik")
    assert istemci.get("/api/ticket/musteri", params={"no": "70000005"}, headers=teknik).status_code == 403
    # Excel'den ticket aktarım ucu kaldırıldı
    assert istemci.post("/api/ticket/aktar", headers=yonetici, content=b"x").status_code in (404, 405)


def test_cok_musterili_ticket_ve_listede_task_adi(istemci, yonetici, conn):
    _is_ekle(conn, "6", "70000006", task_adi="Arıza Giderme")
    y = istemci.post("/api/ticket", headers=yonetici, json={
        "location_id": LOC, "konu": "EK SP", "musteri": "70000006, 70000007", "site": SITE, "durum": "AÇIK"})
    assert y.status_code == 201, y.text
    t = y.json()["ticket"]
    assert t["musteri"] == "70000006, 70000007" and t["bina_serial"] == BINA
    assert (t["task_adi"], t["task_no"]) == ("Arıza Giderme", "900000006")
    satir = next(x for x in istemci.get("/api/ticket", headers=yonetici).json()["ticketlar"] if x["id"] == t["id"])
    assert satir["task_adi"] == "Arıza Giderme"
    d = istemci.patch(f"/api/ticket/{t['id']}", headers=yonetici, json={"durum": "HATA"})
    assert d.status_code == 200 and d.json()["ticket"]["durum"] == "HATA"


def test_ticket_sifirlama_yedekli_ve_bir_kez(istemci, yonetici, conn, db_yolu: Path, tmp_path: Path):
    _is_ekle(conn, "7", "70000008")
    t1 = istemci.post("/api/ticket", headers=yonetici, json={"location_id": LOC, "konu": "SİNYAL"}).json()["ticket"]
    istemci.patch(f"/api/ticket/{t1['id']}", headers=yonetici, json={"durum": "ÇÖZÜLDÜ"})
    conn.execute("UPDATE is_emri SET ticket_id=? WHERE is_no='7'", (t1["id"],))
    conn.execute("INSERT INTO ticket (konu, durum, olusturma, guncelleme, tur, kaynak) "
                 "VALUES ('GÜZERGAH','AÇIK','2026-01-01','2026-01-01','guzergah','excel')")
    conn.commit()
    ek = tmp_path / "ek"
    (ek / "ticket" / str(t1["id"])).mkdir(parents=True)
    (ek / "ticket" / str(t1["id"]) / "a.jpg").write_bytes(b"x")

    s = ticket_temizlik.calistir(conn, db_yolu, ek)
    assert s and s["ticket"] == 1 and s["is_bagi_bosalan"] == 1 and s["ticket_gecmis"] >= 2
    assert Path(s["yedek"]).exists() and s["foto_klasoru_tasinan"] == 1
    assert not (ek / "ticket" / str(t1["id"])).exists()
    assert conn.execute("SELECT COUNT(*) FROM ticket WHERE tur IS NULL").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM ticket WHERE tur='guzergah'").fetchone()[0] == 1   # güzergah kalır
    assert conn.execute("SELECT ticket_id FROM is_emri WHERE is_no='7'").fetchone()[0] is None
    assert ticket_temizlik.yapildi_mi(conn)
    assert istemci.get("/api/ticket", headers=yonetici).json()["toplam"] == 1             # güzergah: PS26 silmesine kadar

    # Sonradan girilen ticket'a ikinci açılışta dokunulmaz; yeni kimlik eski numarayı almaz
    t2 = istemci.post("/api/ticket", headers=yonetici, json={"location_id": LOC, "konu": "SİNYAL"}).json()["ticket"]
    assert t2["id"] > t1["id"]
    assert ticket_temizlik.calistir(conn, db_yolu, ek) is None
    assert conn.execute("SELECT COUNT(*) FROM ticket WHERE id=?", (t2["id"],)).fetchone()[0] == 1


def test_ticket_sifirlama_bos_defterde_yedeksiz_isaretlenir(conn, db_yolu: Path):
    s = ticket_temizlik.calistir(conn, db_yolu)
    assert s == {"yedek": None, "ticket": 0, "is_bagi_bosalan": 0, "ticket_ek": 0, "ticket_gecmis": 0}
    assert ticket_temizlik.calistir(conn, db_yolu) is None


def test_ps26_silme_yedekli_bir_kez_uygulama_ticketina_dokunmaz(istemci, yonetici, conn, db_yolu: Path, tmp_path: Path):
    """PS26'dan gelen her şey (güzergah, Excel ticket'ı, ALTYAPI satırı, ayarlar) yedekli ve bir kez silinir."""
    _is_ekle(conn, "8", "70000009", durum="altyapi")
    _is_ekle(conn, "9", "70000010")
    uyg = istemci.post("/api/ticket", headers=yonetici, json={"location_id": LOC, "konu": "SİNYAL"}).json()["ticket"]
    g = conn.execute("INSERT INTO ticket (konu, durum, olusturma, guncelleme, tur, kaynak, aktarim_anahtari) "
                     "VALUES ('GÜZERGAH','AÇIK','2026-01-01','2026-01-01','guzergah','excel','guzergah:x:1')").lastrowid
    e = conn.execute("INSERT INTO ticket (konu, durum, olusturma, guncelleme, kaynak, aktarim_anahtari) "
                     "VALUES ('EK SP','AÇIK','2026-01-01','2026-01-01','excel','excel:y:1')").lastrowid
    conn.execute("UPDATE is_emri SET ticket_id=? WHERE is_no='8'", (g,))
    conn.execute("UPDATE is_emri SET ticket_id=? WHERE is_no='9'", (uyg["id"],))
    for anahtar in ("ps26:abc:1", None):
        conn.execute("INSERT INTO altyapi_bekleyen (musteri_no, durum, aktarim_anahtari, olusturma, guncelleme) "
                     "VALUES ('90000021','bekliyor',?,'2026-01-01','2026-01-01')", (anahtar,))
    conn.execute("INSERT INTO ayar(anahtar, deger) VALUES ('ps26_son_aktarim','2026-10-01 10:00:00') "
                 "ON CONFLICT(anahtar) DO UPDATE SET deger=excluded.deger")
    conn.commit()
    ek = tmp_path / "ek"
    (ek / "ticket" / str(g)).mkdir(parents=True)
    (ek / "ticket" / str(g) / "g.jpg").write_bytes(b"x")

    s = ticket_temizlik.ps26_calistir(conn, db_yolu, ek)
    assert s and s["ticket"] == 2 and s["altyapi_bekleyen"] == 1 and s["altyapidan_donen_is"] == 1
    assert Path(s["yedek"]).exists() and "ps26" in Path(s["yedek"]).name and s["foto_klasoru_tasinan"] == 1
    assert [r[0] for r in conn.execute("SELECT id FROM ticket")] == [uyg["id"]]                # uygulamadaki kalır
    assert conn.execute("SELECT durum, ticket_id FROM is_emri WHERE is_no='8'").fetchone()[:] == ("bekliyor", None)
    assert conn.execute("SELECT ticket_id FROM is_emri WHERE is_no='9'").fetchone()[0] == uyg["id"]
    assert conn.execute("SELECT COUNT(*) FROM altyapi_bekleyen").fetchone()[0] == 1           # uygulamada eklenen kalır
    assert conn.execute("SELECT COUNT(*) FROM ayar WHERE anahtar LIKE 'ps26_%'").fetchone()[0] == 0
    assert ticket_temizlik.ps26_yapildi_mi(conn)
    # ikinci kez: hiçbir şey
    conn.execute("INSERT INTO ticket (konu, durum, olusturma, guncelleme, tur) "
                 "VALUES ('GÜZERGAH','AÇIK','2026-01-02','2026-01-02','guzergah')")
    conn.commit()
    assert ticket_temizlik.ps26_calistir(conn, db_yolu, ek) is None
    assert conn.execute("SELECT COUNT(*) FROM ticket").fetchone()[0] == 2
