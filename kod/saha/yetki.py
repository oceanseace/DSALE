"""Kimlik ve yetki: dört görev, görev KÜMESİ, varsayılan YASAK (spec §2 + Ek-1).

Yetki GÖREVDEN gelir, etiketten asla. Bir kişinin görev kümesi ``kullanici_gorev`` satırları
∪ ana görev (``kullanici.rol``); izinler kümedeki görevlerin izinlerinin BİRLEŞİMİdir.
Tabloda olmayan eylem herkes için 403 ``yasak``.

Her uç ``Depends(izin("eylem"))`` ile kendi eylemini ister; ``ROTA_IZNI`` bütün uçların
sözleşmedeki eylemini tutar ve ``saha/testler/test_yetki_matrisi.py`` ikisinin aynı olduğunu,
listede olmayan rota kalmadığını denetler.

Bu modül ``saha.api``'yi içe aktarmaz (döngü yok): ``baglanti``, ``mevcut_kullanici`` ve ``hata``
burada tanımlıdır, ``saha.api`` bunları yeniden dışa açar. v2 yönlendiricileri de bağımlılıklarını
``Bagimliliklar`` ile buradan alır.
"""
from __future__ import annotations

import datetime as dt
import sqlite3
from dataclasses import dataclass, field
from typing import Callable

from fastapi import Depends, Header, HTTPException

from . import ayarlar, db, guvenlik, sema_v2

ROLLER = sema_v2.ROLLER
ETIKET = {"satisci": "Satış", "operasyon": "Operasyon", "teknik": "Teknik", "yonetici": "Yönetici"}
ACIKLAMA = {
    "satisci": "Bina listesi ve satış ziyaretleri. Kendi bölgesini görür.",
    "operasyon": "İş emirlerini dağıtır, randevu verir, müşteri bilgisini görür.",
    "teknik": "Yalnız kendisine atanan işleri görür ve durumunu işler.",
    "yonetici": "Her şeyi görür; ekip ve ayarları yönetir.",
}
_ANA_EKRAN = {"satisci": "bugun", "operasyon": "isler", "teknik": "islerim", "yonetici": "isler"}

S, O, T, Y = "satisci", "operasyon", "teknik", "yonetici"
_HERKES = frozenset(ROLLER)

# Eylem → bu eylemi veren görevler (spec §2.2). Kapsam (bölge, kendi işi) ayrıca denetlenir.
IZINLER: dict[str, frozenset[str]] = {
    "oturum": _HERKES,                          # yalnız giriş yapmış olmak (ör. /api/ben)
    "satis.kendi": frozenset({S, Y}),           # Bugün, bina listesi, harita, yollar, görev, ziyaret
    "satis.izle": frozenset({Y}),               # gün özeti, rapor.xlsx, görev ata, başkasının listesi
    "bina.oku": _HERKES,                        # bina kartı (kapsam: bina_gorebilir)
    "geometri.oku": frozenset({S, O, Y}),
    "altlik.oku": _HERKES,
    "ticket.sablon": _HERKES,
    "is.liste": frozenset({O, T, Y}),           # teknikte yalnız kendi işleri (WP-B kapsamı)
    "is.musteri": frozenset({O, T, Y}),
    "is.yukle": frozenset({O, Y}),
    "is.ata": frozenset({O, Y}),
    "is.duzenle": frozenset({O, Y}),
    "is.saha": frozenset({O, T, Y}),
    "is.olustur": frozenset({O, Y}),
    "is.excel": frozenset({O, Y}),
    "obek.oku": frozenset({O, Y}),
    "obek.duzenle": frozenset({O, Y}),
    "mahalle.ekle": frozenset({O, Y}),
    "mahalle.yukle": frozenset({Y}),
    "ticket.defter": frozenset({O, Y}),
    "takip.oku": frozenset({O, Y}),
    "takip.tam": frozenset({Y}),
    "kapasite.yaz": frozenset({O, Y}),
    "ekip.teknikler": frozenset({O, Y}),
    "ekip.yonet": frozenset({Y}),
    "veri.yonet": frozenset({Y}),
    "tablolar.oku": frozenset({O, Y}),          # Ek-8: "Tablolar" ekranı (Excel alışkanlığı)
}

# (yöntem, yol şablonu) → eylem. None = herkese açık (giriş gerekmez). Birden çok eylem
# "herhangi biri yeter" demektir. v2 uçları (operasyon/v2, WP-B) da sözleşmeden buraya yazıldı:
# matris testi var olan her rotayı buna göre dener.
ROTA_IZNI: dict[tuple[str, str], str | tuple[str, ...] | None] = {
    # ---- oturum
    ("GET", "/api/saglik"): None,
    ("POST", "/api/giris"): None,
    ("POST", "/api/pin"): None,
    ("GET", "/api/ben"): "oturum",
    # ---- satış
    ("GET", "/api/gorev/bugun"): ("satis.kendi", "satis.izle"),
    ("POST", "/api/gorev/olustur"): "satis.kendi",
    ("POST", "/api/gorev/ata"): "satis.izle",
    ("POST", "/api/ziyaret"): "satis.kendi",
    ("POST", "/api/ziyaret/toplu"): "satis.kendi",
    ("POST", "/api/ziyaret/{ziyaret_id}/iptal"): "satis.kendi",
    ("GET", "/api/bina"): "satis.kendi",
    ("GET", "/api/bina/{bina_serial}"): "bina.oku",
    ("GET", "/api/harita"): "satis.kendi",
    ("GET", "/api/yollar"): "satis.kendi",
    ("GET", "/api/ozet/gun"): "satis.izle",
    # Spec §2.3 satis.izle der; bugünkü test_satisci_kendi_kapsamasini_gorur satışçıya kendi
    # bölgesini açık tutar (beklentiler gevşetilmez): satış kendi bölgesi, yönetici hepsi.
    ("GET", "/api/ozet/kapsama"): ("satis.kendi", "satis.izle"),
    ("GET", "/api/dosya/rapor.xlsx"): "satis.izle",
    # ---- ekip
    ("GET", "/api/kullanici"): "ekip.yonet",
    ("POST", "/api/kullanici"): "ekip.yonet",
    ("GET", "/api/kullanici/{kullanici_id}"): "ekip.yonet",
    ("DELETE", "/api/kullanici/{kullanici_id}"): "ekip.yonet",
    ("POST", "/api/kullanici/gorevler"): "ekip.yonet",
    ("POST", "/api/kullanici/rehber"): "ekip.yonet",
    ("GET", "/api/kullanici/rehber/esleme"): "ekip.yonet",
    ("PUT", "/api/kullanici/rehber/esleme"): "ekip.yonet",
    ("POST", "/api/kullanici/{kullanici_id}/davet"): "ekip.yonet",
    ("GET", "/api/kullanici/{kullanici_id}/iliskiler"): "ekip.yonet",
    ("POST", "/api/kullanici/{kullanici_id}/is-aktar"): "ekip.yonet",
    ("POST", "/api/kullanici/{kullanici_id}/pin-sifirla"): "ekip.yonet",
    ("POST", "/api/kullanici/{kullanici_id}/cihaz-cikis"): "ekip.yonet",
    # ---- ayar
    ("GET", "/api/ayar"): "oturum",
    ("POST", "/api/ayar"): "veri.yonet",
    ("GET", "/api/ayar/altlik"): "altlik.oku",
    ("PUT", "/api/ayar/altlik"): "veri.yonet",
    # ---- veri yönetimi
    ("GET", "/api/kalite/ozet"): "veri.yonet",
    ("GET", "/api/kalite/liste"): "veri.yonet",
    ("POST", "/api/kalite/yenile"): "veri.yonet",
    ("GET", "/api/bolgeleme/durum"): "veri.yonet",
    ("GET", "/api/bolgeleme/onizleme"): "veri.yonet",
    ("GET", "/api/bolgeleme/is/{is_id}"): "veri.yonet",
    ("POST", "/api/bolgeleme/uygula"): "veri.yonet",
    ("POST", "/api/bolgeleme/geri-al"): "veri.yonet",
    ("GET", "/api/bolgeleme/excel"): "veri.yonet",
    ("POST", "/api/veri/tur-raporu"): "veri.yonet",
    ("GET", "/api/veri/tur-raporu"): "veri.yonet",
    ("GET", "/api/veri/tur-raporu/{tur_id}"): "veri.yonet",
    ("POST", "/api/veri/tur-raporu/uygula"): "veri.yonet",
    ("GET", "/api/veri/bekleyen"): "veri.yonet",
    ("GET", "/api/veri/bekleyen.txt"): "veri.yonet",
    ("GET", "/api/veri/onemap-araci.js"): "veri.yonet",
    ("POST", "/api/veri/onemap"): "veri.yonet",
    ("GET", "/api/bina/{bina_serial}/degisim"): "veri.yonet",
    # ---- ticket
    ("GET", "/api/ticket"): "ticket.defter",
    ("POST", "/api/ticket"): "ticket.defter",
    ("GET", "/api/ticket/sablon"): "ticket.sablon",
    ("GET", "/api/ticket/kategoriler"): "ticket.sablon",
    ("GET", "/api/ticket/harita"): "ticket.defter",
    ("POST", "/api/ticket/aktar"): "ticket.defter",
    ("GET", "/api/ticket/{ticket_id}"): "ticket.defter",
    ("PATCH", "/api/ticket/{ticket_id}"): "ticket.defter",
    ("GET", "/api/bina/{bina_serial}/ticket"): "bina.oku",
    ("GET", "/api/binalar/geometri"): "geometri.oku",
    # ---- v2 iş emri (operasyon/v2/api.py, WP-B) — spec §5.3.2–§5.3.6, Ek-4
    ("GET", "/api/isler"): "is.liste",
    ("GET", "/api/isler/degisim"): "is.liste",
    ("GET", "/api/isler/excel"): "is.excel",
    ("GET", "/api/isler/boss-ekip"): "is.ata",
    ("POST", "/api/isler/boss-ekip/esle"): "is.ata",
    ("GET", "/api/isler/teknikler"): "ekip.teknikler",
    ("POST", "/api/isler/oneri-onayla"): "is.ata",
    ("POST", "/api/isler/toplu-ata"): "is.ata",
    ("POST", "/api/isler/toplu/{toplu_id}/geri-al"): "is.ata",
    ("POST", "/api/isler/dagit/onizle"): "is.ata",
    ("POST", "/api/isler/dagit/uygula"): "is.ata",
    ("POST", "/api/isler"): "is.olustur",
    ("GET", "/api/isler/{is_no}"): "is.liste",
    ("POST", "/api/isler/{is_no}/ata"): "is.ata",
    ("POST", "/api/isler/{is_no}/randevu"): "is.ata",
    ("POST", "/api/isler/{is_no}/durum"): ("is.saha", "is.duzenle"),
    ("POST", "/api/isler/{is_no}/teshis"): "is.duzenle",
    ("POST", "/api/isler/{is_no}/ticket"): "is.duzenle",
    ("DELETE", "/api/isler/{is_no}/ticket"): "is.duzenle",
    ("POST", "/api/isler/{is_no}/obek"): "is.duzenle",
    ("POST", "/api/isler/{is_no}/mahalle"): "is.duzenle",
    ("POST", "/api/isler/{is_no}/not"): ("is.duzenle", "is.saha"),
    ("PATCH", "/api/isler/{is_no}/iletisim"): "is.duzenle",
    ("POST", "/api/isler/{is_no}/kopya"): "is.musteri",
    ("POST", "/api/isler/{is_no}/boss-islendi"): "is.ata",
    ("POST", "/api/isler/{is_no}/boss-bagla"): "is.ata",
    ("POST", "/api/isler/{is_no}/geri-al"): ("is.ata", "is.duzenle", "is.saha"),
    ("GET", "/api/aranacaklar"): "is.duzenle",
    ("GET", "/api/islerim"): "is.saha",
    ("POST", "/api/islerim/gordu"): "is.saha",
    ("POST", "/api/islerim/sira"): "is.saha",
    ("POST", "/api/aktarim"): "is.yukle",
    ("GET", "/api/aktarim"): "is.yukle",
    ("POST", "/api/aktarim/{aktarim_id}/uygula"): "is.yukle",
    ("POST", "/api/aktarim/{aktarim_id}/vazgec"): "is.yukle",
    ("GET", "/api/obekler"): "obek.oku",
    ("POST", "/api/obekler"): "obek.duzenle",
    ("PATCH", "/api/obekler/{obek_id}"): "obek.duzenle",
    ("DELETE", "/api/obekler/{obek_id}"): "obek.duzenle",
    ("POST", "/api/obekler/{obek_id}/mahalle"): "obek.duzenle",
    ("POST", "/api/obekler/{obek_id}/mahalle/cikar"): "obek.duzenle",
    ("POST", "/api/obekler/{obek_id}/bol"): "obek.duzenle",
    ("POST", "/api/obekler/geri-al"): "obek.duzenle",
    ("GET", "/api/mahalleler"): "obek.oku",
    ("GET", "/api/ilceler"): "obek.oku",
    ("POST", "/api/mahalleler"): "mahalle.ekle",
    ("POST", "/api/mahalleler/esad"): "mahalle.ekle",
    ("POST", "/api/mahalleler/yukle"): "mahalle.yukle",
    ("GET", "/api/takip"): "takip.oku",
    ("GET", "/api/takip/satis"): "takip.tam",
    ("GET", "/api/takip/erisim"): "takip.tam",
    ("GET", "/api/takip/yonetim"): "takip.tam",
    ("PUT", "/api/takip/kapasite"): "kapasite.yaz",
    ("GET", "/api/boss/giden"): "is.ata",
    ("POST", "/api/boss/giden/{is_no}/islendi"): "is.ata",
    # WP-B'nin sözleşme dışı ek uçları (iş emri ayarları, Ek-10 klasör izleme)
    ("GET", "/api/isler/ayarlar"): "is.liste",
    ("PUT", "/api/isler/ayarlar"): "veri.yonet",
    ("GET", "/api/aktarim/izleme"): "is.yukle",
    ("PUT", "/api/aktarim/izleme"): "is.yukle",
}

# Eski iş emri uçları (pickle'lı tek yükleme): her yöntemde 410 ``yenilendi``, kimlik gerekmez (§5.3.9).
for _yontem in ("GET", "POST", "PUT", "PATCH", "DELETE"):
    ROTA_IZNI[(_yontem, "/api/is-emri")] = None
    ROTA_IZNI[(_yontem, "/api/is-emri/{yol:path}")] = None

# Açık iş = kapandı ve çözüldü dışındaki her durum (spec §3.1).
KAPALI_IS_DURUMLARI = ("cozuldu", "kapandi")


def hata(durum: int, mesaj: str, kod: str) -> HTTPException:
    return HTTPException(status_code=durum, detail={"hata": mesaj, "kod": kod})


YASAK_METNI = "Bu bölüm görevinize kapalı."


# ============================================================================= bağlantı, kimlik
def baglanti():
    conn = db.baglan()
    try:
        yield conn
    finally:
        conn.close()


def _jeton_al(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parca = authorization.split(None, 1)
    if len(parca) == 2 and parca[0].lower() == "bearer":
        return parca[1].strip()
    return None


# oturum_no artışının nedenine göre 401 metni (spec §5.3.1). Kod 'gorev_degisti' yalnız görevde.
_OTURUM_METNI = {
    "gorev": ("Göreviniz değişti. PIN'inizle yeniden girin.", "gorev_degisti"),
    "cihaz": ("Bu cihazın oturumu kapatıldı. PIN'inizle yeniden girin.", "oturum_bitti"),
    "bolge": ("Bölgeniz değişti. PIN'inizle yeniden girin.", "oturum_bitti"),
}


def gorev_kumesi_oku(conn: sqlite3.Connection, kisi: dict) -> list[str]:
    """``kullanici_gorev`` satırları ∪ ana görev; tanınan görevler, sabit sırada."""
    kume = {kisi.get("rol")}
    try:
        kume |= {r[0] for r in conn.execute(
            "SELECT rol FROM kullanici_gorev WHERE kullanici_id=?", (kisi["id"],)).fetchall()}
    except sqlite3.OperationalError:           # göç öncesi veritabanı: yalnız ana görev
        pass
    return [r for r in ROLLER if r in kume]


def mevcut_kullanici(
    conn: sqlite3.Connection = Depends(baglanti),
    authorization: str | None = Header(default=None),
) -> dict:
    jeton = _jeton_al(authorization)
    if not jeton:
        raise hata(401, "Oturum gerekli. Lütfen tekrar giriş yapın.", "yetkisiz")
    yuk = guvenlik.jeton_coz(jeton)
    if not yuk:
        raise hata(401, "Oturumunuzun süresi doldu. Lütfen tekrar giriş yapın.", "oturum_bitti")
    satir = conn.execute("SELECT * FROM kullanici WHERE id=?", (yuk.get("kid"),)).fetchone()
    if not satir or not satir["aktif"]:
        raise hata(401, "Hesabınız kapalı. Yöneticinize başvurun.", "hesap_kapali")
    k = dict(satir)
    if int(yuk.get("otr", 1)) != int(k["oturum_no"]):
        mesaj, kod = _OTURUM_METNI.get(k.get("oturum_neden") or "",
                                       ("PIN'iniz değişti. Lütfen tekrar giriş yapın.", "oturum_bitti"))
        raise hata(401, mesaj, kod)
    if k.get("rol") not in ROLLER:
        raise hata(403, YASAK_METNI, "yasak")
    k["gorevler"] = gorev_kumesi_oku(conn, k)
    return k


# ============================================================================= izinler
def gorevler(k: dict) -> frozenset[str]:
    """Kişinin görev kümesi (``mevcut_kullanici`` doldurur; yoksa yalnız ana görev)."""
    kume = set(k.get("gorevler") or ())
    kume.add(k.get("rol"))
    return frozenset(r for r in kume if r in ROLLER)


def izinli(k: dict, eylem: str) -> bool:
    """Varsayılan YASAK: tabloda olmayan eylem hiç kimseye verilmez."""
    roller = IZINLER.get(eylem)
    return bool(roller) and bool(gorevler(k) & roller)


def izin(*eylemler: str) -> Callable[..., dict]:
    """FastAPI bağımlılığı: eylemlerden HERHANGİ biri yeterli; yoksa 403 ``yasak``.

    Bilinmeyen eylem adı uç tanımlanırken hata verir (yazım hatası sessizce kapı açmasın).
    """
    bilinmeyen = [e for e in eylemler if e not in IZINLER]
    if not eylemler or bilinmeyen:
        raise ValueError(f"Bilinmeyen yetki eylemi: {', '.join(bilinmeyen) or '(boş)'}")

    def _izin_denetimi(k: dict = Depends(mevcut_kullanici)) -> dict:
        if not any(izinli(k, e) for e in eylemler):
            raise hata(403, YASAK_METNI, "yasak")
        return k

    _izin_denetimi.eylemler = tuple(eylemler)          # matris testi okur
    _izin_denetimi.__name__ = "izin__" + "__".join(e.replace(".", "_") for e in eylemler)
    return _izin_denetimi


def izin_listesi(kisi: dict | str | tuple | list | frozenset | set) -> list[str]:
    """/api/ben.izinler — arayüz menüsü bundan çizilir. Görev adı ya da kişi (küme) alır."""
    if isinstance(kisi, str):
        kume = frozenset({kisi})
    elif isinstance(kisi, dict):
        kume = gorevler(kisi)
    else:
        kume = frozenset(kisi)
    return sorted(e for e, roller in IZINLER.items() if e != "oturum" and kume & roller)


def ana_ekran(rol: str) -> str:
    """'bugun' | 'isler' | 'islerim' — girişte açılan ekran ANA göreve göredir."""
    return _ANA_EKRAN.get(rol, "bugun")


def gorev_etiketi(k: dict) -> str:
    """"Operasyon · Yönetici" — ana görev önce."""
    kume = gorevler(k)
    sira = [k.get("rol")] + [r for r in ROLLER if r != k.get("rol")]
    return " · ".join(ETIKET[r] for r in sira if r in kume)


# ============================================================================= kapsam
def bolge_kapsami(k: dict, istenen: int | None) -> int | None:
    """Satış uçlarının bölge kapsamı (spec §2.4-1; bugünkü ``_bolge_kontrol``'ün yerine).

    * yönetici, operasyon → istenen (None = hepsi)
    * satış → kendi bölgesi; başka bölge 403 ``baska_bolge``; bölgesi NULL/0 ise 0 (liste boş)
    * teknik ve bilinmeyen → 403 ``yasak``
    """
    kume = gorevler(k)
    if kume & {Y, O}:
        return istenen
    if S in kume:
        kendi = int(k.get("bolge") or 0)
        if istenen is not None and int(istenen) != kendi:
            raise hata(403, "Yalnızca kendi bölgenizi görebilirsiniz.", "baska_bolge")
        return kendi
    raise hata(403, YASAK_METNI, "yasak")


def listesinde_mi(conn: sqlite3.Connection, kullanici_id: int, bina_serial: str) -> bool:
    """Bina bu satışçının son günlerdeki bir listesinde mi?

    Bölge planı gün içinde değişirse (8 → 14 ekip) satışçının elindeki liste ve
    telefondaki çevrimdışı kuyruk eski bölgenin binalarını taşır. Bu kayıtlar
    "başka bölge" diye reddedilirse telefonda takılı kalır; oysa binaya o gün
    gerçekten o gitti. Kuyruk en çok ``ZAMAN_GERI_GUN`` gün eski olabilir.
    """
    sinir = (ayarlar.bugun() - dt.timedelta(days=ayarlar.ZAMAN_GERI_GUN)).isoformat()
    return conn.execute(
        "SELECT 1 FROM gorev_bina gb JOIN gorev g ON g.id=gb.gorev_id "
        "WHERE g.kullanici_id=? AND gb.bina_serial=? AND g.tarih>=? LIMIT 1",
        (kullanici_id, bina_serial, sinir),
    ).fetchone() is not None


def _kendi_bolgesinde(conn: sqlite3.Connection, k: dict, bina_serial: str) -> bool:
    kendi = int(k.get("bolge") or 0)
    if kendi:
        satir = conn.execute("SELECT bolge FROM bina WHERE bina_serial=?", (bina_serial,)).fetchone()
        if satir and satir[0] == kendi:
            return True
    return listesinde_mi(conn, k["id"], bina_serial)


def teknik_acik_isi_var(conn: sqlite3.Connection, k: dict, bina_serial: str) -> bool:
    """Teknik: bu binada KENDİSİNE atanmış AÇIK bir işi var mı?"""
    try:
        return conn.execute(
            "SELECT 1 FROM is_emri WHERE atanan_id=? AND bina_serial=? "
            f"AND durum NOT IN ({','.join('?' * len(KAPALI_IS_DURUMLARI))}) LIMIT 1",
            (k["id"], bina_serial, *KAPALI_IS_DURUMLARI)).fetchone() is not None
    except sqlite3.OperationalError:            # is_emri tablosu yok (göç öncesi)
        return False


def bina_gorebilir(conn: sqlite3.Connection, k: dict, bina_serial: str) -> bool:
    """Bina kartı: satış kendi bölgesi (ya da listesi), operasyon/yönetici hepsi,
    teknik yalnız kendisine atanmış açık işin binası. Varsayılan: hayır."""
    kume = gorevler(k)
    if kume & {Y, O}:
        return True
    if S in kume and _kendi_bolgesinde(conn, k, bina_serial):
        return True
    if T in kume and teknik_acik_isi_var(conn, k, bina_serial):
        return True
    return False


def ziyaret_yazabilir(conn: sqlite3.Connection, k: dict, bina_serial: str) -> bool:
    """Ziyaret yalnız satış (kendi bölgesi ya da listesi) ve yönetici yazar (spec §2.4-2)."""
    kume = gorevler(k)
    if Y in kume:
        return True
    return S in kume and _kendi_bolgesinde(conn, k, bina_serial)


# ============================================================================= v2 yönlendiricilerine bağımlılıklar
@dataclass
class Bagimliliklar:
    """``saha/api.py`` oluşturur, ``operasyon.v2.api.yonlendiriciler(b)``'ye verir (döngüsel içe aktarma yok)."""
    izin: Callable[..., Callable] = izin
    kullanici: Callable = mevcut_kullanici
    baglanti: Callable = baglanti
    hata: Callable[..., HTTPException] = hata
    yonetim_kaydi: Callable = db.yonetim_kaydi
    izinli: Callable[[dict, str], bool] = izinli
    ek: dict = field(default_factory=dict)
