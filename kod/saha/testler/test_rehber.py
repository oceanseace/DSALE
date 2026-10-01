"""Personel rehberi içe aktarımı (Ek-2): önizleme, uygula, iki kez uygula = çift kayıt yok,
unvan → görev eşlemesi, eşlenmeyen unvanlar alınmaz, mevcut kişinin yalnız unvanı yazılır.

Adlar uydurmadır.
"""
from __future__ import annotations

from saha import api, sema_v2

REHBER = """Çalışanlar
AY
Ahmet Yılmaztepe
Teknik - Sorumlu
Burcu Kalemoğlu
Satış Destek - Uzman
Cem Doğrusöz
Stok Sorumlusu
Deniz Ağaçlı
Teknik - Müdür
Ece Tunalıoğlu
Yeni Müşteri - Sorumlu
Ferhat Işıkçı
İnsan Kaynakları Uzmanı
Gül Özbağ
Hizmet Danışmanı
"""


def test_satirlari_ciftlere_ayirir():
    kisiler, okunamayan = api.rehber_coz(REHBER, sema_v2.UNVAN_GOREV_ESLEME)
    assert [k["ad"] for k in kisiler] == ["Ahmet Yılmaztepe", "Burcu Kalemoğlu", "Cem Doğrusöz", "Deniz Ağaçlı",
                                          "Ece Tunalıoğlu", "Ferhat Işıkçı", "Gül Özbağ"]
    assert kisiler[3]["unvan"] == "Teknik - Müdür"
    assert okunamayan == 0


def test_unvan_gorev_eslemesi():
    e = sema_v2.UNVAN_GOREV_ESLEME
    assert api._unvan_gorevleri(e, "Teknik - Müdür") == ["teknik", "yonetici"]
    assert api._unvan_gorevleri(e, "TEKNİK - SORUMLU") == ["teknik"]
    assert api._unvan_gorevleri(e, "Satış Destek - Takım Lideri") == ["operasyon", "yonetici"]
    assert api._unvan_gorevleri(e, "Yeni Müşteri - Sorumlu") == ["satisci"]
    assert api._unvan_gorevleri(e, "Genel Koordinatör") == ["yonetici"]
    assert api._unvan_gorevleri(e, "Stok Sorumlusu") is None
    assert api._unvan_gorevleri(e, "Fiber Yayılım Uzmanı") is None


def test_onizleme_yazmaz_uygula_yazar_ikinci_kez_etkisiz(istemci, yonetici, conn):
    once = conn.execute("SELECT COUNT(*) FROM kullanici").fetchone()[0]
    on = istemci.post("/api/kullanici/rehber", headers=yonetici, json={"metin": REHBER}).json()
    assert on["uygulandi"] is False
    assert on["sayilar"] == {"eklenecek": 5, "guncellenecek": 0, "atlanacak": 2, "ayni": 0}
    assert {a["neden"] for a in on["atlanacak"]} == {"gorev_yok"}
    assert conn.execute("SELECT COUNT(*) FROM kullanici").fetchone()[0] == once

    y = istemci.post("/api/kullanici/rehber", headers=yonetici, json={"metin": REHBER, "uygula": True}).json()
    assert y["uygulandi"] is True
    assert conn.execute("SELECT COUNT(*) FROM kullanici").fetchone()[0] == once + 5
    deniz = conn.execute("SELECT * FROM kullanici WHERE ad='Deniz Ağaçlı'").fetchone()
    assert deniz["telefon"] is None and deniz["kaynak"] == "rehber" and deniz["rol"] == "teknik"
    assert deniz["aktif"] == 1 and deniz["pin_hash"] is None and deniz["davet_kodu"] is None
    kume = {r[0] for r in conn.execute("SELECT rol FROM kullanici_gorev WHERE kullanici_id=?", (deniz["id"],))}
    assert kume == {"teknik", "yonetici"}
    ece = conn.execute("SELECT rol, bolge FROM kullanici WHERE ad='Ece Tunalıoğlu'").fetchone()
    assert ece["rol"] == "satisci" and ece["bolge"] is None          # bölge Ekip'te verilir

    ikinci = istemci.post("/api/kullanici/rehber", headers=yonetici, json={"metin": REHBER, "uygula": True}).json()
    assert ikinci["sayilar"]["eklenecek"] == 0 and ikinci["sayilar"]["ayni"] == 5
    assert conn.execute("SELECT COUNT(*) FROM kullanici").fetchone()[0] == once + 5
    assert conn.execute("SELECT COUNT(*) FROM yonetim_kaydi WHERE eylem='rehber_aktar'").fetchone()[0] == 2

    # Girişsiz kişiler listede telefonsuz görünür.
    liste = istemci.get("/api/kullanici", headers=yonetici).json()["kullanicilar"]
    kart = next(k for k in liste if k["id"] == deniz["id"])
    assert kart["giris_var"] is False and kart["telefon_goster"] == "—" and kart["kaynak"] == "rehber"
    assert kart["gorev_etiketi"] == "Teknik · Yönetici"


def test_mevcut_kisiye_yalniz_unvan_yazilir(istemci, yonetici, kisi, conn):
    kid, _ = kisi("operasyon", ad="Hale Çınaroğlu")
    metin = "HALE ÇINAROĞLU\nTeknik - Müdür\n"
    on = istemci.post("/api/kullanici/rehber", headers=yonetici, json={"metin": metin}).json()
    assert on["sayilar"]["guncellenecek"] == 1 and on["guncellenecek"][0]["id"] == kid
    istemci.post("/api/kullanici/rehber", headers=yonetici, json={"metin": metin, "uygula": True})
    satir = conn.execute("SELECT rol, unvan FROM kullanici WHERE id=?", (kid,)).fetchone()
    assert satir["rol"] == "operasyon" and satir["unvan"] == "Teknik - Müdür"
    assert {r[0] for r in conn.execute("SELECT rol FROM kullanici_gorev WHERE kullanici_id=?", (kid,))} == {"operasyon"}


def test_esleme_duzenlenir(istemci, yonetici, satisci1):
    e = istemci.get("/api/kullanici/rehber/esleme", headers=yonetici).json()
    assert e["esleme"][0]["desen"] == "Teknik - Müdür"
    y = istemci.put("/api/kullanici/rehber/esleme", headers=yonetici, json={"esleme": [
        {"desen": "Stok Sorumlusu", "gorevler": ["operasyon"]}]})
    assert y.status_code == 200
    on = istemci.post("/api/kullanici/rehber", headers=yonetici, json={"metin": REHBER}).json()
    assert [k["ad"] for k in on["eklenecek"]] == ["Cem Doğrusöz"]
    kotu = istemci.put("/api/kullanici/rehber/esleme", headers=yonetici, json={"esleme": [
        {"desen": "X Y", "gorevler": ["hacker"]}]})
    assert kotu.status_code == 400
    assert istemci.post("/api/kullanici/rehber", headers=satisci1, json={"metin": REHBER}).status_code == 403
