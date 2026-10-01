"""Ekip (F12, spec §5.3.7) ve bir kişiye birden çok görev (Ek-1).

Dört görev, bölge yalnız satışta, görev değişince oturum düşer ama PIN aynı kalır, son yönetici ve
kişinin kendi görevi korunur, davet kodu bir kez ve 48 saat, her değişiklik yönetim kaydında.
"""
from __future__ import annotations

import datetime as dt
import json

import pytest

from saha import ayarlar, guvenlik

from .conftest import PIN, SATISCI_TEL, YONETICI_TEL


def _id(conn, telefon: str) -> int:
    return conn.execute("SELECT id FROM kullanici WHERE telefon=?", (telefon,)).fetchone()["id"]


def _kaydet(istemci, h, **alan):
    return istemci.post("/api/kullanici", headers=h, json=alan)


# ============================================================ dört görev
def test_dort_gorev_kaydedilir(istemci, yonetici):
    for i, rol in enumerate(("satisci", "operasyon", "teknik", "yonetici")):
        y = _kaydet(istemci, yonetici, ad=f"Deneme {rol}", telefon=f"555000{i:04d}", rol=rol,
                    bolge=2 if rol == "satisci" else None)
        assert y.status_code == 200, y.text
        k = y.json()["kullanici"]
        assert k["rol"] == rol and k["gorevler"] == [rol]
        assert len(y.json()["davet_kodu"]) == 6
    y = _kaydet(istemci, yonetici, ad="Kötü", telefon="5550009999", rol="hacker")
    assert y.status_code == 400 and y.json()["kod"] == "rol_hatali"


def test_bolge_yalniz_satista(istemci, yonetici, conn):
    y = _kaydet(istemci, yonetici, ad="Operasyoncu", telefon="5550000101", rol="operasyon", bolge=3)
    assert y.status_code == 200 and y.json()["kullanici"]["bolge"] is None
    y = _kaydet(istemci, yonetici, ad="Bölgesiz satış", telefon="5550000102", rol="satisci")
    assert y.status_code == 400 and y.json()["kod"] == "bolge_gecersiz"
    # Kümede satış varsa bölge zorunludur (ana görev operasyon olsa da).
    y = _kaydet(istemci, yonetici, ad="İki görev", telefon="5550000103", rol="operasyon",
                gorevler=["operasyon", "satisci"])
    assert y.status_code == 400 and y.json()["kod"] == "bolge_gecersiz"


def test_rol_degisince_gorev_degisti_401_pin_ayni(istemci, yonetici, satisci1, conn):
    kid = _id(conn, SATISCI_TEL[1])
    once = conn.execute("SELECT pin_hash FROM kullanici WHERE id=?", (kid,)).fetchone()[0]
    assert istemci.get("/api/ben", headers=satisci1).status_code == 200
    y = _kaydet(istemci, yonetici, id=kid, ad="Satışçı Bir", telefon=SATISCI_TEL[1], rol="teknik")
    assert y.status_code == 200 and y.json()["oturum_dustu"] is True
    dusen = istemci.get("/api/ben", headers=satisci1)
    assert dusen.status_code == 401 and dusen.json()["kod"] == "gorev_degisti"
    assert "Göreviniz değişti" in dusen.json()["hata"]
    giris = istemci.post("/api/giris", json={"telefon": SATISCI_TEL[1], "pin": PIN})
    assert giris.status_code == 200 and giris.json()["ana_ekran"] == "islerim"
    ben = istemci.get("/api/ben", headers={"Authorization": f"Bearer {giris.json()['token']}"}).json()
    assert ben["ana_ekran"] == "islerim" and ben["kullanici"]["bolge"] is None
    assert conn.execute("SELECT pin_hash FROM kullanici WHERE id=?", (kid,)).fetchone()[0] == once


def test_son_yonetici(istemci, yonetici, conn):
    """Tek aktif yönetici kendisi: ilişki denetimi 'son_yonetici' engeli gösterir, kendi görevi düşürülemez."""
    kid = _id(conn, YONETICI_TEL)
    il = istemci.get(f"/api/kullanici/{kid}/iliskiler", headers=yonetici).json()
    assert {"kendini_silemez", "son_yonetici"} <= set(il["engeller"]) and il["silinebilir"] is False
    # Yönetici toplu kartta tek yöneticiyi (kendisi dahil değil) düşüremez: son yönetici kalmalı.
    from saha import api

    satir = dict(conn.execute("SELECT * FROM kullanici WHERE id=?", (kid,)).fetchone())
    assert api._son_yonetici_mi(conn, satir, ["yonetici"]) is True
    # İkinci bir aktif yönetici eklenince artık son değildir.
    y = _kaydet(istemci, yonetici, ad="İkinci Yönetici", telefon="5550000201", rol="yonetici")
    assert y.status_code == 200
    assert api._son_yonetici_mi(conn, satir, ["yonetici"]) is False


def test_kendi_rolu(istemci, yonetici, conn):
    kid = _id(conn, YONETICI_TEL)
    y = _kaydet(istemci, yonetici, id=kid, ad="Yönetici", telefon=YONETICI_TEL, rol="operasyon")
    assert y.status_code == 409 and y.json()["kod"] == "kendi_rolu"
    y = _kaydet(istemci, yonetici, id=kid, ad="Yönetici", telefon=YONETICI_TEL, rol="yonetici",
                gorevler=["yonetici", "teknik"])
    assert y.status_code == 409 and y.json()["kod"] == "kendi_rolu"
    y = _kaydet(istemci, yonetici, id=kid, ad="Yönetici", telefon=YONETICI_TEL, rol="yonetici", aktif=False)
    assert y.status_code == 409 and y.json()["kod"] == "kendini_silemez"
    # Adını değiştirmek serbest; oturum düşmez.
    y = _kaydet(istemci, yonetici, id=kid, ad="Ofis Yöneticisi", telefon=YONETICI_TEL, rol="yonetici")
    assert y.status_code == 200 and y.json()["oturum_dustu"] is False
    assert istemci.get("/api/ben", headers=yonetici).status_code == 200


def test_davet_bir_kez_48s(istemci, yonetici, conn):
    y = _kaydet(istemci, yonetici, ad="Yeni Kişi", telefon="5550000301", rol="operasyon")
    kid, kod = y.json()["kullanici"]["id"], y.json()["davet_kodu"]
    assert y.json()["davet_gecerlilik_saat"] == 48
    liste = istemci.get("/api/kullanici", headers=yonetici).json()["kullanicilar"]
    kart = next(k for k in liste if k["id"] == kid)
    assert kart["davet_bekliyor"] is True and "davet_kodu" not in kart
    # Yeni kod: yalnız bu yanıtta; eskisi geçersiz olur.
    yeni = istemci.post(f"/api/kullanici/{kid}/davet", headers=yonetici).json()
    assert len(yeni["davet_kodu"]) == 6 and yeni["gecerlilik"] == "48 saat"
    assert istemci.post("/api/pin", json={"telefon": "5550000301", "pin": PIN,
                                          "davet_kodu": kod}).status_code == 401 or kod == yeni["davet_kodu"]
    # 49 saat önce üretilmiş kod: 410
    eski = (ayarlar.simdi() - dt.timedelta(hours=49)).isoformat(sep=" ", timespec="seconds")
    conn.execute("UPDATE kullanici SET davet_zamani=? WHERE id=?", (eski, kid))
    conn.commit()
    y = istemci.post("/api/pin", json={"telefon": "5550000301", "pin": PIN, "davet_kodu": yeni["davet_kodu"]})
    assert y.status_code == 410 and y.json()["kod"] == "davet_suresi_doldu"
    kart = next(k for k in istemci.get("/api/kullanici", headers=yonetici).json()["kullanicilar"] if k["id"] == kid)
    assert kart["davet_suresi_doldu"] is True
    # Taze kodla PIN belirlenir ve operasyon ana ekranı açılır.
    taze = istemci.post(f"/api/kullanici/{kid}/davet", headers=yonetici).json()["davet_kodu"]
    y = istemci.post("/api/pin", json={"telefon": "5550000301", "pin": PIN, "davet_kodu": taze})
    assert y.status_code == 200 and y.json()["ana_ekran"] == "isler"
    assert istemci.post(f"/api/kullanici/{kid}/davet", headers=yonetici).json()["kod"] == "pin_var"


def test_eski_davet_kodu_gecerli(istemci, db_yolu, conn):
    """Göç öncesi üretilmiş kodlar (davet_zamani yok) süresizdir: PIN'i olmayan kişi kilitlenmez."""
    from .conftest import davet_kodu

    assert conn.execute("SELECT davet_zamani FROM kullanici WHERE telefon=?",
                        (SATISCI_TEL[5],)).fetchone()[0] is None
    y = istemci.post("/api/pin", json={"telefon": SATISCI_TEL[5], "pin": PIN,
                                       "davet_kodu": davet_kodu(db_yolu, SATISCI_TEL[5])})
    assert y.status_code == 200, y.text


def test_gorevler_toplu(istemci, yonetici, conn):
    a, b = _id(conn, SATISCI_TEL[1]), _id(conn, SATISCI_TEL[2])
    ben = istemci.get("/api/ben", headers=yonetici).json()
    assert "gorev_gozden_gecir" in ben
    y = istemci.post("/api/kullanici/gorevler", headers=yonetici, json={"degisiklikler": [
        {"id": a, "rol": "operasyon", "gorevler": ["operasyon", "yonetici"]},
        {"id": b, "rol": "teknik"}], "tamam": True})
    assert y.status_code == 200 and y.json()["degisen"] == 2
    kumeler = {r[0]: r[1] for r in conn.execute(
        "SELECT kullanici_id, group_concat(rol) FROM (SELECT * FROM kullanici_gorev ORDER BY rol) "
        "WHERE kullanici_id IN (?,?) GROUP BY kullanici_id", (a, b))}
    assert set(kumeler[a].split(",")) == {"operasyon", "yonetici"} and kumeler[b] == "teknik"
    assert conn.execute("SELECT bolge FROM kullanici WHERE id=?", (b,)).fetchone()[0] is None
    assert istemci.get("/api/ben", headers=yonetici).json()["gorev_gozden_gecir"] is False
    # Kendi görevi içeren toplu değişiklik bütünüyle reddedilir (tek işlem).
    kendi = _id(conn, YONETICI_TEL)
    c = _id(conn, SATISCI_TEL[3])
    y = istemci.post("/api/kullanici/gorevler", headers=yonetici, json={"degisiklikler": [
        {"id": c, "rol": "teknik"}, {"id": kendi, "rol": "operasyon"}]})
    assert y.status_code == 409 and y.json()["kod"] == "kendi_rolu"
    assert conn.execute("SELECT rol FROM kullanici WHERE id=?", (c,)).fetchone()[0] == "satisci"


def test_yonetim_kaydi_yazilir(istemci, yonetici, conn):
    y = _kaydet(istemci, yonetici, ad="Kayıt Denemesi", telefon="5550000401", rol="teknik")
    kid = y.json()["kullanici"]["id"]
    _kaydet(istemci, yonetici, id=kid, ad="Kayıt Denemesi", telefon="5550000402", rol="operasyon")
    istemci.post(f"/api/kullanici/{kid}/cihaz-cikis", headers=yonetici)
    istemci.post(f"/api/kullanici/{kid}/pin-sifirla", headers=yonetici)
    satirlar = conn.execute("SELECT eylem, hedef, ozet FROM yonetim_kaydi WHERE hedef=? ORDER BY id",
                            (f"kullanici:{kid}",)).fetchall()
    assert [r["eylem"] for r in satirlar] == ["kisi_ekle", "gorev", "cihaz_cikis", "pin_sifirla"]
    metin = json.dumps([dict(r) for r in satirlar], ensure_ascii=False)
    assert "5550000401" not in metin and "5550000402" not in metin       # telefon değeri yazılmaz
    ozet = json.loads(satirlar[1]["ozet"])
    assert "telefon" in ozet["alanlar"] and ozet["gorev"]["sonra"] == ["operasyon"]


def test_liste_davet_kodu_dondurmez(istemci, yonetici):
    y = istemci.get("/api/kullanici", headers=yonetici)
    assert y.status_code == 200
    govde = y.text
    assert "davet_kodu" not in govde
    for k in y.json()["kullanicilar"]:
        assert "telefon" not in k and "•••" in k["telefon_goster"]
    assert len(y.json()["gorevler"]) == 4


def test_tek_kisi_yaniti_tam_telefon(istemci, yonetici, conn):
    kid = _id(conn, SATISCI_TEL[4])
    k = istemci.get(f"/api/kullanici/{kid}", headers=yonetici).json()["kullanici"]
    assert k["telefon"] == SATISCI_TEL[4] and k["giris_var"] is True


# ============================================================ Ek-1: görev kümesi
def test_operasyon_yonetici_birlesimi_gorur(istemci, kisi):
    _kid, h = kisi("operasyon", gorevler=["operasyon", "yonetici"])
    ben = istemci.get("/api/ben", headers=h).json()
    assert ben["ana_ekran"] == "isler" and ben["gorev_etiketi"] == "Operasyon · Yönetici"
    assert "ekip.yonet" in ben["izinler"] and "is.ata" in ben["izinler"]
    assert istemci.get("/api/kullanici", headers=h).status_code == 200      # yöneticiden
    assert istemci.get("/api/ticket", headers=h).status_code == 200         # operasyondan
    assert istemci.get("/api/ozet/gun", headers=h).status_code == 200       # yöneticiden (satis.izle)


def test_satisci_is_emirlerine_kapali(istemci, kisi):
    _kid, h = kisi("satisci", bolge=1)
    assert istemci.get("/api/ticket", headers=h).status_code == 403
    y = istemci.get("/api/isler", headers=h)
    assert y.status_code in (403, 404)          # v2 uçları bağlıysa 403 'yasak'
    if y.status_code == 403:
        assert y.json()["kod"] == "yasak"


def test_satis_yonetici_ana_ekran_satis(istemci, kisi):
    _kid, h = kisi("satisci", gorevler=["satisci", "yonetici"], bolge=2)
    ben = istemci.get("/api/ben", headers=h).json()
    assert ben["ana_ekran"] == "bugun" and "bolge" in ben and "gorev_gozden_gecir" in ben
    # Yönetici olduğu için her bölgeyi görür; satışçı olduğu için rotası kurulur.
    assert istemci.get("/api/bina?bolge=5&limit=1", headers=h).status_code == 200
    assert istemci.post("/api/gorev/olustur", headers=h, json={"adet": 3}).status_code == 200


def test_gorev_cikarilinca_eski_jeton_401(istemci, yonetici, kisi):
    kid, h = kisi("operasyon", gorevler=["operasyon", "yonetici"])
    assert istemci.get("/api/kullanici", headers=h).status_code == 200
    y = istemci.post("/api/kullanici", headers=yonetici, json={
        "id": kid, "ad": "Deneme", "telefon": "", "rol": "operasyon", "gorevler": ["operasyon"]})
    assert y.status_code == 200 and y.json()["oturum_dustu"] is True
    y = istemci.get("/api/kullanici", headers=h)
    assert y.status_code == 401 and y.json()["kod"] == "gorev_degisti"


def test_ana_gorev_kumeye_eklenir(istemci, yonetici, conn):
    y = _kaydet(istemci, yonetici, ad="Ana Görev", telefon="5550000501", rol="teknik", gorevler=["operasyon"])
    assert y.status_code == 200
    assert y.json()["kullanici"]["gorevler"] == ["operasyon", "teknik"]
    assert y.json()["kullanici"]["gorev_etiketi"] == "Teknik · Operasyon"


def test_teknik_alanlari_kaydedilir(istemci, yonetici):
    y = _kaydet(istemci, yonetici, ad="Teknisyen", telefon="5550000601", rol="teknik",
                etiket=["lider"], boss_ekip="EKIP ORNEK", kapasite=12, unvan="Teknik - Sorumlu")
    k = y.json()["kullanici"]
    assert k["etiket"] == ["lider"] and k["boss_ekip"] == "EKIP ORNEK" and k["kapasite"] == 12
    # Alan gönderilmezse değer korunur.
    y = _kaydet(istemci, yonetici, id=k["id"], ad="Teknisyen", telefon="5550000601", rol="teknik")
    k2 = y.json()["kullanici"]
    assert k2["boss_ekip"] == "EKIP ORNEK" and k2["kapasite"] == 12 and k2["unvan"] == "Teknik - Sorumlu"


def test_telefonu_olmayan_kisi(istemci, yonetici, conn):
    """Ek-2: girişsiz kişi (BOSS Mobil) kaydedilir; telefon eklenince davet akışı başlar."""
    y = _kaydet(istemci, yonetici, ad="Girişsiz Teknisyen", telefon="", rol="teknik")
    assert y.status_code == 200, y.text
    k = y.json()["kullanici"]
    assert k["giris_var"] is False and k["telefon_goster"] == "—" and y.json()["davet_kodu"] is None
    assert istemci.post(f"/api/kullanici/{k['id']}/davet", headers=yonetici).json()["kod"] == "telefon_yok"
    assert istemci.post(f"/api/kullanici/{k['id']}/pin-sifirla", headers=yonetici).json()["kod"] == "telefon_yok"
    y = _kaydet(istemci, yonetici, id=k["id"], ad="Girişsiz Teknisyen", telefon="5550000701", rol="teknik")
    assert y.status_code == 200 and len(y.json()["davet_kodu"]) == 6
    assert guvenlik.telefon_goster(None) == "—"


def test_telefonu_silinen_kisinin_oturumu_kapanir(istemci, yonetici, kisi):
    """Ek-2: telefonu silinen kişi girişsiz olur; elindeki jeton da geçersizleşir (giriş telefonla)."""
    kid, h = kisi("teknik", ad="Telefonu Silinecek")
    assert istemci.get("/api/ben", headers=h).status_code == 200
    y = _kaydet(istemci, yonetici, id=kid, ad="Telefonu Silinecek", telefon="", rol="teknik")
    assert y.status_code == 200 and y.json()["oturum_dustu"] is True
    assert y.json()["kullanici"]["giris_var"] is False
    assert istemci.get("/api/ben", headers=h).status_code == 401
