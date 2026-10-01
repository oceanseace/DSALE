"""Kişi silme (F13, spec §5.3.7 + Ek-1): kaydı olmayan silinir, kaydı olan silinmez (409 + sayılar),
yalnız öbek sahipliği onayla bırakılır, kendini / son yöneticiyi silemez, FK hatası 503 değil 409."""
from __future__ import annotations

from saha import ayarlar

from .conftest import SATISCI_TEL, YONETICI_TEL


def _id(conn, telefon: str) -> int:
    return conn.execute("SELECT id FROM kullanici WHERE telefon=?", (telefon,)).fetchone()["id"]


def test_kaydi_yok_silinir_id_yeniden_kullanilmaz(istemci, yonetici, kisi, conn):
    kid, _h = kisi("teknik", gorevler=["teknik", "operasyon"])
    il = istemci.get(f"/api/kullanici/{kid}/iliskiler", headers=yonetici).json()
    assert il["silinebilir"] is True and il["engeller"] == [] and il["sayilar"] == {}
    y = istemci.delete(f"/api/kullanici/{kid}", headers=yonetici)
    assert y.status_code == 204, y.text
    assert conn.execute("SELECT COUNT(*) FROM kullanici WHERE id=?", (kid,)).fetchone()[0] == 0
    # Görev kümesi engel sayılmaz ve kişiyle birlikte gider.
    assert conn.execute("SELECT COUNT(*) FROM kullanici_gorev WHERE kullanici_id=?", (kid,)).fetchone()[0] == 0
    yeni, _ = kisi("teknik")
    assert yeni > kid
    kayit = conn.execute("SELECT eylem FROM yonetim_kaydi WHERE hedef=?", (f"kullanici:{kid}",)).fetchall()
    assert [r[0] for r in kayit] == ["kisi_sil"]


def test_ziyareti_olan_silinmez_sayilarla(istemci, yonetici, satisci1, conn):
    kid = _id(conn, SATISCI_TEL[1])
    gorev = istemci.post("/api/gorev/olustur", headers=satisci1, json={"adet": 3}).json()
    istemci.post("/api/ziyaret", headers=satisci1, json={
        "offline_id": "sil-1", "bina_serial": gorev["binalar"][0]["bina_serial"], "sonuc": "ilgilenmedi"})
    il = istemci.get(f"/api/kullanici/{kid}/iliskiler", headers=yonetici).json()
    assert il["silinebilir"] is False and "iliskili_kayit" in il["engeller"]
    assert il["sayilar"]["ziyaret.kullanici_id"] == 1 and il["sayilar"]["gorev.kullanici_id"] >= 1
    assert {"metin": "ziyaret", "sayi": 1} in il["etiketler"]
    y = istemci.delete(f"/api/kullanici/{kid}", headers=yonetici)
    assert y.status_code == 409 and y.json()["kod"] == "iliskili_kayit"
    assert "1 ziyaret" in y.json()["hata"] and "Pasife alabilirsiniz" in y.json()["hata"]
    assert y.json()["sayilar"]["ziyaret.kullanici_id"] == 1
    assert conn.execute("SELECT COUNT(*) FROM kullanici WHERE id=?", (kid,)).fetchone()[0] == 1


def test_isi_olan_silinmez(istemci, yonetici, kisi, conn):
    kid, _h = kisi("teknik")
    z = ayarlar.zaman_metni()
    conn.execute(
        "INSERT INTO is_emri (is_no, kaynak, task_adi, serit, durum, durum_zamani, atanan_id, acilis, son24, "
        "ilk_gorulme, gorulme_zamani, guncelleme) VALUES ('487654321','boss','Arıza','SAHA','atandi',?,?,?,?,?,?,?)",
        (z, kid, z, z, z, z, z))
    conn.commit()
    y = istemci.delete(f"/api/kullanici/{kid}", headers=yonetici)
    assert y.status_code == 409 and y.json()["kod"] == "iliskili_kayit" and y.json()["acik_is"] == 1
    assert y.json()["sayilar"] == {"is_emri.atanan_id": 1}


def test_yalniz_obek_sahipligi_obekleri_birak(istemci, yonetici, kisi, conn):
    kid, _h = kisi("teknik")
    z = ayarlar.zaman_metni()
    conn.execute("INSERT INTO obek (ad, ad_k, sahip_id, olusturma, guncelleme) VALUES ('Deneme Öbek','DENEMEOBEKX',?,?,?)",
                 (kid, z, z))
    conn.commit()
    il = istemci.get(f"/api/kullanici/{kid}/iliskiler", headers=yonetici).json()
    assert il["silinebilir"] is True and il["obek_sahipligi"] == 1 and il["obekleri_birak_gerekli"] is True
    y = istemci.delete(f"/api/kullanici/{kid}", headers=yonetici)
    assert y.status_code == 409 and y.json()["kod"] == "iliskili_kayit" and y.json()["obek_sahipligi"] == 1
    y = istemci.delete(f"/api/kullanici/{kid}?obekleri_birak=1", headers=yonetici)
    assert y.status_code == 204, y.text
    assert conn.execute("SELECT sahip_id FROM obek WHERE ad_k='DENEMEOBEKX'").fetchone()[0] is None


def test_kendini_silemez(istemci, yonetici, conn):
    kid = _id(conn, YONETICI_TEL)
    y = istemci.delete(f"/api/kullanici/{kid}", headers=yonetici)
    assert y.status_code == 409 and y.json()["kod"] == "kendini_silemez"


def test_son_yonetici_silinemez(istemci, yonetici, kisi, conn, monkeypatch):
    """Silme denetimi 'son_yonetici' engelini de uygular (ilişki sayımı sahte olsa bile)."""
    from saha import api

    hedef, _ = kisi("yonetici")
    # Çağıran yönetici pasifleşmiş gibi: hedef tek aktif yönetici olur.
    conn.execute("UPDATE kullanici SET aktif=0 WHERE telefon=?", (YONETICI_TEL,))
    conn.commit()
    satir = dict(conn.execute("SELECT * FROM kullanici WHERE id=?", (hedef,)).fetchone())
    assert api._son_yonetici_mi(conn, satir, ["yonetici"]) is True
    conn.execute("UPDATE kullanici SET aktif=1 WHERE telefon=?", (YONETICI_TEL,))
    conn.commit()
    assert api._son_yonetici_mi(conn, satir, ["yonetici"]) is False


def test_fk_hatasi_503_degil_409(istemci, yonetici, satisci1, conn, monkeypatch):
    """İlişki sayımı bir bağı kaçırsa bile veritabanı silmeyi durdurur ve yanıt 409 olur."""
    from saha import api

    kid = _id(conn, SATISCI_TEL[1])
    gorev = istemci.post("/api/gorev/olustur", headers=satisci1, json={"adet": 2}).json()
    istemci.post("/api/ziyaret", headers=satisci1, json={
        "offline_id": "fk-1", "bina_serial": gorev["binalar"][0]["bina_serial"], "sonuc": "ilgilenmedi"})
    bos = {"silinebilir": True, "engeller": [], "sayilar": {}, "acik_is": 0, "obek_sahipligi": 0,
           "obekleri_birak_gerekli": False, "demo": 0, "hepsi_demo": False, "etiketler": []}
    monkeypatch.setattr(api, "_iliskiler", lambda *_a, **_k: bos)
    y = istemci.delete(f"/api/kullanici/{kid}", headers=yonetici)
    assert y.status_code == 409 and y.json()["kod"] == "iliskili_kayit"
    assert conn.execute("SELECT COUNT(*) FROM kullanici WHERE id=?", (kid,)).fetchone()[0] == 1


def test_gosterim_verisi_isaretlenir(istemci, yonetici, db_yolu, conn):
    from saha import demo

    kid = _id(conn, SATISCI_TEL[1])
    demo.kur(gun_sayisi=1, sessiz=True)      # yer tutucunun ad/telefonunu gösterim değeriyle değiştirir; id aynı
    il = istemci.get(f"/api/kullanici/{kid}/iliskiler", headers=yonetici).json()
    assert il["demo"] > 0 and il["hepsi_demo"] is True and "iliskili_kayit" in il["engeller"]


def test_is_aktar_teknik_olmayana_422(istemci, yonetici, kisi):
    kaynak, _ = kisi("teknik")
    hedef, _ = kisi("operasyon")
    y = istemci.post(f"/api/kullanici/{kaynak}/is-aktar", headers=yonetici, json={"hedef_id": hedef})
    assert y.status_code == 422 and y.json()["kod"] == "teknik_gecersiz"


def test_yeni_tablonun_bagi_kendiliginden_sayilir(istemci, yonetici, kisi, conn):
    """İlişki sayımı ``pragma_foreign_key_list`` ile dinamiktir: sonradan eklenen tablo listeye elle
    yazılmadan engel olur (ör. WP-G'nin ek tabloları); ``kullanici_gorev`` hiçbir zaman engel değildir."""
    kid, _h = kisi("teknik", gorevler=["teknik", "yonetici"])
    conn.execute("CREATE TABLE deneme_bag (id INTEGER PRIMARY KEY, kisi_id INTEGER REFERENCES kullanici(id))")
    conn.execute("INSERT INTO deneme_bag (kisi_id) VALUES (?)", (kid,))
    conn.commit()
    il = istemci.get(f"/api/kullanici/{kid}/iliskiler", headers=yonetici).json()
    assert il["sayilar"] == {"deneme_bag.kisi_id": 1} and "iliskili_kayit" in il["engeller"]
    assert istemci.delete(f"/api/kullanici/{kid}", headers=yonetici).status_code == 409
    conn.execute("DELETE FROM deneme_bag")
    conn.commit()
    assert istemci.delete(f"/api/kullanici/{kid}", headers=yonetici).status_code == 204
