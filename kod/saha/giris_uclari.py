"""Giriş uçları (çekirdek — bütün görevler): oturum açma, davet koduyla ilk PIN ve "ben" ana ekran özeti.

URL'ler: POST /api/giris · POST /api/pin · GET /api/ben
"""
from __future__ import annotations

import datetime as dt
import hmac
import sqlite3
import time

from fastapi import APIRouter, Depends, Request
from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from . import ayarlar, db, guvenlik, yetki
from .api_ortak import (_acik_gorev, _davet_suresi_doldu, _demo_kurulu, _gorev_ozet, _kullanici_kart,
                        _telefon_veya_hata)
from .yetki import baglanti, hata, izin

yonlendirici = APIRouter()


# ============================================================================= giriş
class GirisGirdi(BaseModel):
    model_config = ConfigDict(extra="ignore")
    telefon: str
    pin: str = ""


class PinGirdi(BaseModel):
    model_config = ConfigDict(extra="ignore")
    telefon: str
    pin: str
    davet_kodu: str = Field(default="", validation_alias=AliasChoices("davet_kodu", "davet"))


def _ip(istek: Request) -> str | None:
    return istek.client.host if istek.client else None


def _ip_kontrol(conn: sqlite3.Connection, ip: str | None, tur: str = "giris") -> None:
    """IP başına sınır. Telefon başına SERT KİLİT YOK (bkz. guvenlik.py)."""
    kalan = guvenlik.ip_asildi_mi(conn, ip, tur)
    if kalan:
        dakika = max(1, round(kalan / 60))
        raise hata(429, f"Bu cihazdan çok fazla deneme yapıldı. {dakika} dakika sonra "
                        "tekrar deneyin.", "kilitli")


def _yanlis_pin(conn: sqlite3.Connection, telefon: str, ip: str | None, mesaj: str) -> None:
    """Hatalı denemeyi yazar, cezalı bekleme uygular ve hatayı fırlatır.

    Doğru PIN hiçbir zaman reddedilmez: meşru satışçı sahadayken kilitli kalmaz.
    Kaba kuvveti durduran şey artan gecikme ve IP sınırıdır.
    """
    guvenlik.deneme_yaz(conn, telefon, False, ip)
    conn.commit()
    bekle = guvenlik.gecikme_saniye(guvenlik.hatali_sayisi(conn, telefon))
    if bekle:
        time.sleep(bekle)
    raise hata(401, mesaj, "kimlik_hatali")


@yonlendirici.post("/api/giris")
def giris(girdi: GirisGirdi, istek: Request, conn: sqlite3.Connection = Depends(baglanti)):
    """Giriş — ve PIN girilmeden yapılan "ilk kez mi?" yoklaması.

    Uygulama önce boş PIN ile sorar. Yanıt ``pin_belirle`` ise ekran doğrudan
    davet kodu adımına geçer; yoksa PIN sorar. Böylece hesabı yeni açılan
    satışçı, PIN'i olmadığı halde "Şifren" ekranına düşüp rastgele denemez.

    Yoklama hesabın ADINI DÖNDÜRMEZ ve hatalı deneme sayılmaz; kimliksiz birinin
    05xx aralığını tarayıp "hangi numara Turkcell saha ekibinde, kim" listesi
    çıkarmasını engellemek için. IP başına sınır yine de işler.
    """
    telefon = _telefon_veya_hata(girdi.telefon)
    ip = _ip(istek)
    _administrator_hazirla(conn, telefon)
    k = conn.execute("SELECT * FROM kullanici WHERE telefon=?", (telefon,)).fetchone()

    if not (girdi.pin or "").strip():
        _ip_kontrol(conn, ip, "yoklama")
        pin_belirle_gerek = bool(k and k["aktif"] and not k["pin_hash"])
        guvenlik.deneme_yaz(conn, telefon, False, ip, tur="yoklama")
        conn.commit()
        return {
            "pin_belirle": pin_belirle_gerek,
            "telefon": telefon,
            "mesaj": ("İlk giriş. Yöneticinizden aldığınız 6 haneli davet koduyla "
                      "kendi PIN'inizi belirleyeceksiniz.") if pin_belirle_gerek else None,
        }

    _ip_kontrol(conn, ip)
    if not k:
        _yanlis_pin(conn, telefon, ip, "Telefon veya PIN hatalı.")
    if not k["aktif"]:
        raise hata(403, "Hesabınız kapalı. Yöneticinize başvurun.", "hesap_kapali")
    if not k["pin_hash"]:
        return {"pin_belirle": True, "telefon": telefon,
                "mesaj": "İlk giriş. Yöneticinizden aldığınız davet koduyla PIN belirleyin."}
    if not guvenlik.pin_dogrula(girdi.pin, k["pin_hash"]):
        _yanlis_pin(conn, telefon, ip, "PIN hatalı. Tekrar deneyin.")

    guvenlik.deneme_yaz(conn, telefon, True, ip)
    conn.commit()
    return _oturum_yaniti(conn, k)


def _administrator_hazirla(conn: sqlite3.Connection, telefon: str) -> None:
    """Administrator telefonu ilk kez girildiğinde hesap yoksa açılır (davet kodu yalnız sunucu günlüğünde).

    Açılışta da çağrılır (``saha.api``); burada, sunucu açıkken ``turkcell.json`` sonradan yazıldıysa diye.
    """
    if not telefon or telefon != yetki.administrator_ayari()["telefon"]:
        return
    try:
        yetki.administrator_hesabi_hazirla(conn)
        conn.commit()
    except sqlite3.Error:
        if conn.in_transaction:
            conn.rollback()


def _oturum_yaniti(conn: sqlite3.Connection, k) -> dict:
    """Giriş / PIN yanıtı: jeton + kişi kartı + girişte açılacak ekran (spec §2.1)."""
    k = dict(k)
    yetki.kisi_erisimini_yukle(conn, k)
    return {"token": guvenlik.jeton_uret(k), "kullanici": _kullanici_kart(k),
            "ana_ekran": yetki.ana_ekran_kisi(k)}


@yonlendirici.post("/api/pin")
def pin_belirle(girdi: PinGirdi, istek: Request, conn: sqlite3.Connection = Depends(baglanti)):
    telefon = _telefon_veya_hata(girdi.telefon)
    ip = _ip(istek)
    _ip_kontrol(conn, ip)
    k = conn.execute("SELECT * FROM kullanici WHERE telefon=?", (telefon,)).fetchone()
    if not k or not k["aktif"]:
        _yanlis_pin(conn, telefon, ip, "Telefon veya davet kodu hatalı.")
    # Davet kodu DOĞRULANMADAN "bu hesabın PIN'i var" bilgisi verilmez; yoksa
    # kimliksiz biri hangi hesapların açık olduğunu öğrenebiliyordu.
    kayitli_kod = (k["davet_kodu"] or "").strip()
    if not kayitli_kod or not hmac.compare_digest(girdi.davet_kodu.strip(), kayitli_kod):
        _yanlis_pin(conn, telefon, ip, "Telefon veya davet kodu hatalı.")
    if k["pin_hash"]:
        raise hata(409, "PIN zaten belirlenmiş. Unuttuysanız yöneticiden sıfırlatın.", "pin_var")
    if _davet_suresi_doldu(k):
        raise hata(410, "Kodun süresi doldu. Yöneticinizden yeni kod isteyin.", "davet_suresi_doldu")
    if not guvenlik.pin_gecerli_mi(girdi.pin):
        raise hata(400, "PIN 4 rakamdan oluşmalı.", "pin_gecersiz")
    if guvenlik.pin_zayif_mi(girdi.pin):
        raise hata(400, "Bu PIN çok kolay tahmin ediliyor (1111, 1234 gibi). "
                        "Başka bir 4 hane seçin.", "pin_zayif")

    conn.execute(
        "UPDATE kullanici SET pin_hash=?, davet_kodu=NULL WHERE id=?",
        (guvenlik.pin_hashle(girdi.pin), k["id"]),
    )
    guvenlik.deneme_yaz(conn, telefon, True, ip)
    conn.commit()
    k = conn.execute("SELECT * FROM kullanici WHERE id=?", (k["id"],)).fetchone()
    return _oturum_yaniti(conn, k)


def _gorev_gozden_gecir(conn: sqlite3.Connection) -> dict:
    """Göçten sonra yöneticiye sakin şerit: "8 kişi 'Yönetici' görünüyor" (spec §1.11-2)."""
    try:
        bitti = db.ayar_oku(conn, "gorev_gozden_gecirildi", "0") == "1"
    except sqlite3.Error:
        bitti = True
    yalniz_yonetici = conn.execute(
        "SELECT COUNT(*) FROM kullanici k WHERE k.rol='yonetici' AND k.aktif=1"
    ).fetchone()[0]
    return {"gorev_gozden_gecir": (not bitti) and yalniz_yonetici > 1, "yonetici_sayisi": int(yalniz_yonetici)}


def _teknik_bugun(conn: sqlite3.Connection, k: dict) -> dict:
    """Teknik ana ekranının üst satırı: bugün açık iş, BTK, biten (is_emri yoksa sıfır)."""
    try:
        s = conn.execute(
            "SELECT SUM(CASE WHEN durum NOT IN ('cozuldu','kapandi') THEN 1 ELSE 0 END), "
            "       SUM(CASE WHEN durum NOT IN ('cozuldu','kapandi') AND serit='BTK' THEN 1 ELSE 0 END), "
            "       SUM(CASE WHEN durum IN ('cozuldu','kapandi') AND substr(COALESCE(cozum_zamani, kapanis, ''),1,10)=? "
            "                THEN 1 ELSE 0 END) "
            "FROM is_emri WHERE atanan_id=?", (ayarlar.bugun().isoformat(), k["id"])).fetchone()
    except sqlite3.OperationalError:
        return {"is": 0, "btk": 0, "biten": 0}
    return {"is": int(s[0] or 0), "btk": int(s[1] or 0), "biten": int(s[2] or 0)}


@yonlendirici.get("/api/ben")
def ben(k: dict = Depends(izin("oturum")), conn: sqlite3.Connection = Depends(baglanti)):
    """Her görev kendi dalını alır (spec §5.3.1); dal ANA göreve göredir, izinler kümenin birleşimi."""
    from . import api  # bayrak api.py'de, açılışta değişir: çağrı anında okunur

    ortak = {"kullanici": _kullanici_kart(k), "ana_ekran": yetki.ana_ekran_kisi(k),
             "izinler": yetki.izin_listesi(k), "gorev_etiketi": yetki.gorev_etiketi(k),
             # v9: etkin yetkinlikler, unvan, Administrator bayrağı (arayüz menüsü ve rozet bundan çizilir)
             "yetkinlikler": [{"kod": y, "ad": yetki.YETKINLIKLER[y]["ad"]} for y in k.get("yetkinlikler") or ()],
             "unvan": _unvan_karti(conn, k), "administrator": bool(k.get("administrator")),
             "takim_lideri": bool(k.get("takim_lideri")),
             "yetki_modeli": bool(k.get("_turetildi")),
             "demo": _demo_kurulu(conn), "tarih": ayarlar.bugun().isoformat(),
             "guncelleme_bekliyor": api.GUNCELLEME_BEKLIYOR,
             # EK-6: küçük sevinçler sunucudan kapatılabilir (ayar 'acik' | 'kapali'); arayüz buradan okur.
             "kutlamalar": (db.ayar_oku(conn, "kutlamalar", "acik") or "acik") != "kapali"}
    kume = yetki.gorevler(k)
    if "yonetici" in kume:
        ortak.update(_gorev_gozden_gecir(conn))
    if "operasyon" in kume or "teknik" in kume:
        ortak["yardim"] = {"telefon": db.ayar_oku(conn, "yardim_telefon"), "ad": db.ayar_oku(conn, "yardim_ad")}
    if k["rol"] == "satisci":
        return {**ortak, **_ben_satis(conn, k)}
    if k["rol"] == "teknik":
        return {**ortak, "bugun": _teknik_bugun(conn, k)}
    if k["rol"] == "operasyon":
        return {**ortak, "bugun": _teknik_bugun_ekip(conn)}
    return {**ortak, "bugun": _ben_yonetici_ozeti(conn)}


def _unvan_karti(conn: sqlite3.Connection, k: dict) -> dict | None:
    uid = k.get("unvan_id")
    if uid:
        try:
            satir = conn.execute("SELECT id, ad, aktif FROM unvan WHERE id=?", (uid,)).fetchone()
        except sqlite3.OperationalError:
            satir = None
        if satir:
            return {"id": satir["id"], "ad": satir["ad"], "aktif": bool(satir["aktif"])}
    return {"id": None, "ad": k.get("unvan"), "aktif": True} if k.get("unvan") else None


def _teknik_bugun_ekip(conn: sqlite3.Connection) -> dict:
    """Operasyon ana ekranının üst satırı için kaba sayılar (ayrıntı İşler panosunda)."""
    try:
        s = conn.execute(
            "SELECT SUM(CASE WHEN durum NOT IN ('cozuldu','kapandi') THEN 1 ELSE 0 END), "
            "       SUM(CASE WHEN durum IN ('triyaj','bekliyor','randevulu') THEN 1 ELSE 0 END) "
            "FROM is_emri").fetchone()
    except sqlite3.OperationalError:
        return {"acik": 0, "atanmamis": 0}
    return {"acik": int(s[0] or 0), "atanmamis": int(s[1] or 0)}


def _ben_satis(conn: sqlite3.Connection, k: dict) -> dict:
    """Satış dalı: bugünkü alanlar değişmez (+ ``bolge_yok``)."""
    gun = ayarlar.bugun()
    gorev = _acik_gorev(conn, k["id"], gun)
    ozet = _gorev_ozet(conn, gorev["id"] if gorev else None)
    b = conn.execute(
        "SELECT COUNT(*) AS toplam, "
        "       SUM(CASE WHEN d.son_ziyaret IS NULL THEN 0 ELSE 1 END) AS dokunulan, "
        # "Kalan boş kapı" = HENÜZ SATILMAMIŞ kapı. Eski hesap binaya bir kez
        # dokunulduğu anda o binanın BÜTÜN boş kapılarını "halledilmiş"
        # sayıyor, 753 satışla ~38.000 kapıyı bitmiş gösteriyordu.
        "       SUM(MAX(b.firsat - d.toplam_satis, 0)) AS kalan_firsat "
        "FROM bina b JOIN bina_durum d USING(bina_serial) WHERE b.bolge=? AND b.pasif=0",
        (k["bolge"],),
    ).fetchone()
    toplam, dokunulan = int(b["toplam"] or 0), int(b["dokunulan"] or 0)
    ozet["bolge_bina"] = toplam
    ozet["bolge_dokunulmayan"] = toplam - dokunulan
    # "Ben" ekranındaki hafta ve bölge kartları (sözleşme §4.5).
    hafta_basi = (gun - dt.timedelta(days=gun.weekday())).isoformat()
    # "Satış" hem bugün hem bu hafta AYNI şeyi saymalı: satılan abonelik adedi.
    # (Bugünkü kart `_gorev_ozet` üzerinden satis_adedi topluyor.) Aynı ekranda
    # iki farklı tanım olursa satışçı ilk gün "sayılar tutmuyor" der.
    h = conn.execute(
        "SELECT COUNT(*) AS ziyaret, "
        "       COALESCE(SUM(satis_adedi),0) AS satis, "
        "       SUM(CASE WHEN sonuc='satis' THEN 1 ELSE 0 END) AS satis_bina, "
        "       SUM(CASE WHEN sonuc='randevu' THEN 1 ELSE 0 END) AS randevu "
        "FROM ziyaret WHERE kullanici_id=? AND iptal=0 AND substr(zaman,1,10)>=?",
        (k["id"], hafta_basi),
    ).fetchone()
    ziyaret_h = int(h["ziyaret"] or 0)
    return {
        # Etiketler TEK KAYNAKTAN gelir (ayarlar.py). Aksi halde aynı sonuç
        # telefonda başka, raporda başka yazıyor.
        "etiketler": {"sonuc": ayarlar.SONUC_ETIKET_SAHA, "durum": ayarlar.DURUM_ETIKET},
        "bugun": ozet,
        # DÖNÜŞÜM TEK TANIM: satışla biten bina / gezilen bina. Yüzde 100'ü
        # aşamaz. Abonelik adedi ayrı bir sayıdır ("satis_adedi"), ikisi
        # karıştırılmasın diye ikisi de burada.
        "hafta": {"ziyaret": ziyaret_h, "satis": int(h["satis_bina"] or 0),
                  "satis_adedi": int(h["satis"] or 0), "randevu": int(h["randevu"] or 0),
                  "donusum": round(int(h["satis_bina"] or 0) / ziyaret_h, 4) if ziyaret_h else 0.0},
        "bolge": {"toplam": toplam, "dokunulan": dokunulan, "kalan": toplam - dokunulan,
                  "kalan_firsat": int(b["kalan_firsat"] or 0)},
        # Bölgesi NULL/0 satışçı: listeler boş döner, ekranda "Size henüz bölge atanmadı" (spec §2.4-1).
        "bolge_yok": not int(k.get("bolge") or 0),
    }


def _ben_yonetici_ozeti(conn: sqlite3.Connection) -> dict:
    """Yönetici dalının bugünkü satış özeti (değişmez)."""
    gun = ayarlar.bugun()
    # Yönetici özeti de BİNA sayar, ziyaret değil: aynı binaya iki kez
    # gidilince ya da listede olmayan binaya ziyaret yazılınca ilerleme
    # çubuğu şişip "28 / 28 bina" gibi imkânsız sayılar çıkıyordu.
    g = conn.execute(
        "SELECT COUNT(*) AS toplam, "
        "SUM(CASE WHEN gb.durum='tamam' THEN 1 ELSE 0 END) AS tamam, "
        "SUM(CASE WHEN gb.durum='bekliyor' THEN 1 ELSE 0 END) AS kalan "
        "FROM gorev_bina gb JOIN gorev g ON g.id=gb.gorev_id WHERE g.tarih=?",
        (gun.isoformat(),),
    ).fetchone()
    z = conn.execute(
        "SELECT COALESCE(SUM(satis_adedi),0) AS satis "
        "FROM ziyaret WHERE iptal=0 AND substr(zaman,1,10)=?",
        (gun.isoformat(),),
    ).fetchone()
    return {"gorev_id": None, "toplam": int(g["toplam"] or 0), "tamam": int(g["tamam"] or 0),
            "kalan": int(g["kalan"] or 0), "satis": int(z["satis"])}
