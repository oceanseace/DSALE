"""Kimlik ve yetki: Administrator, unvan + YETKİNLİK paketleri, görev KÜMESİ, varsayılan YASAK.

Etkin izinler (``erisim``):
  * Administrator (veri klasöründeki ``turkcell.json``'daki ``administrator_telefon``; testte
    ``TURKCELL_ADMIN_TELEFON``) → bütün izinler, yalnız ona ait ``yetkinlik.yonet`` dahil. Arayüzden verilemez.
  * ``kullanici.yetki_modeli = 1`` (v9 göçünden geçen ve yeni açılan herkes) → TEMEL ∪ unvanın yetkinlikleri
    ∪ kişinin ek yetkinlikleri (∪ takım lideriyse ayar ``takim_lideri_yetkinlikleri``). Görev kümesi bu
    yetkinliklerden TÜRETİLİR (``gorevler_turet``): bölge kapsamı, teknisyenin kendi işleri, ana ekran onu kullanır.
  * ``yetki_modeli = 0`` (göç öncesi kayıt, SQL ile eklenen satır) → eski kural: görev kümesinin izinleri.

Yetki GÖREVDEN gelir, etiketten asla. Bir kişinin görev kümesi ``kullanici_gorev`` satırları
∪ ana görev (``kullanici.rol``); izinler kümedeki görevlerin izinlerinin BİRLEŞİMİdir.
Tabloda olmayan eylem herkes için 403 ``yasak``.

Her uç ``Depends(izin("eylem"))`` ile kendi eylemini ister; ``ROTA_IZNI`` bütün uçların
sözleşmedeki eylemini tutar ve ``saha/testler/test_yetki_matrisi.py`` ikisinin aynı olduğunu,
listede olmayan rota kalmadığını denetler.

Bu modül ``saha.api``'yi içe aktarmaz (döngü yok): ``baglanti``, ``mevcut_kullanici`` ve ``hata``
burada tanımlıdır, uç modülleri (``saha/*_uclari.py``) bunları buradan alır. v2 yönlendiricileri de bağımlılıklarını
``Bagimliliklar`` ile buradan alır.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import os
import sqlite3
from pathlib import Path
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
    "ticket.oku": frozenset({O, Y}),            # ticket listesi/ayrıntı/fotoğraf/Excel — salt okunur
    "ticket.defter": frozenset({O, Y}),         # ticket aç/düzenle/durum/sil/iş bağla (yazma)
    "takip.oku": frozenset({O, Y}),
    "takip.tam": frozenset({Y}),
    "kapasite.yaz": frozenset({O, Y}),
    "ekip.teknikler": frozenset({O, Y}),
    "ekip.yonet": frozenset({Y}),
    "veri.yonet": frozenset({Y}),
    "tablolar.oku": frozenset({O, Y}),          # Ek-8: "Tablolar" ekranı (Excel alışkanlığı)
    "is.randevu": frozenset({O, Y}),            # randevu ver (Hizmet Danışmanı iş atamadan randevu verir)
    # Görevden GELMEYEN izinler: yalnız yetkinlikle (depo) ya da yalnız Administrator'a (yetkinlik.yonet).
    "depo.yonet": frozenset(),
    "yetkinlik.yonet": frozenset(),
}

# Herkese (giriş yapmış her kişiye) açık izinler; hiçbir pakete gerek yok.
TEMEL_IZINLER = frozenset({"oturum", "bina.oku", "altlik.oku", "ticket.sablon"})
# Yalnız Administrator: hiçbir yetkinliğe konmaz, arayüzden kimseye verilemez.
ADMIN_IZINLERI = frozenset({"yetkinlik.yonet"})

# Yetkinlik = mevcut izinlerin adlandırılmış paketi (kodda tanımlı; hangi unvana/kişiye verileceğini Administrator
# seçer). Sıra arayüzdeki sıradır.
YETKINLIKLER: dict[str, dict] = {
    "saha_satis": {"ad": "Saha satış", "aciklama": "Kendi bölgesinin bina listesi, haritası ve ziyaret kaydı.",
                   "izinler": ("satis.kendi", "geometri.oku")},
    "satis_izleme": {"ad": "Satış ekibi izleme", "aciklama": "Takım lideri: ekibin gününü izler, listeleri dağıtır, "
                                                             "satış raporunu alır.",
                     "izinler": ("satis.izle", "satis.kendi", "geometri.oku")},
    "randevu_arama": {"ad": "Randevu ve arama", "aciklama": "İşleri görür, müşteriyi arar, randevu verir ve not düşer.",
                      "izinler": ("is.liste", "is.musteri", "is.duzenle", "is.randevu", "obek.oku", "geometri.oku")},
    "operasyon_planlama": {"ad": "Operasyon planlama", "aciklama": "BOSS raporunu yükler, işleri teknisyenlere "
                                                                   "atar, öbek ve kapasiteyi düzenler.",
                           "izinler": ("is.liste", "is.musteri", "is.yukle", "is.ata", "is.randevu", "is.duzenle",
                                       "is.saha", "is.olustur", "is.excel", "obek.oku", "obek.duzenle",
                                       "mahalle.ekle", "takip.oku", "kapasite.yaz", "ekip.teknikler",
                                       "tablolar.oku", "geometri.oku")},
    "teknik_saha": {"ad": "Teknik saha", "aciklama": "Yalnız kendisine atanan işleri görür ve durumunu işler.",
                    "izinler": ("is.liste", "is.musteri", "is.saha")},
    "ticket_defteri": {"ad": "Ticket defteri", "aciklama": "OneDesk ticket kayıtlarını açar, izler ve günceller.",
                       "izinler": ("ticket.oku", "ticket.defter")},
    "ticket_izleme": {"ad": "Ticket izleme", "aciklama": "Ticket listesini, ayrıntısını ve fotoğraflarını salt okunur "
                                                         "görür, Excel'e indirir; açamaz, değiştiremez, silemez.",
                      "izinler": ("ticket.oku",)},
    "depo_stok": {"ad": "Depo ve stok", "aciklama": "Depo bölümünü açar (stok ekranları bu yetkinliğe bağlanır).",
                  "izinler": ("depo.yonet",)},
    "pano": {"ad": "Pano", "aciklama": "Bütün birimlerin durumunu salt okunur izler; iş atamaz, plan yapmaz.",
             "izinler": ("takip.oku", "takip.tam", "tablolar.oku")},
    "kisi_yonetimi": {"ad": "Kişi yönetimi", "aciklama": "İK: kişi ekler/çıkarır, unvan ve takım lideri atar, "
                                                         "PIN sıfırlar, davet kodu verir.",
                      "izinler": ("ekip.yonet",)},
    "veri_yonetimi": {"ad": "Veri yönetimi", "aciklama": "Bina verisi, bölgeleme, veri kalitesi ve uygulama ayarları.",
                      "izinler": ("veri.yonet", "mahalle.yukle")},
}
# Eski görev → aynı erişimi veren paketler (göç ve eski uçların "görev" girdisi bununla çevrilir).
GOREV_PAKETLERI: dict[str, tuple[str, ...]] = {
    "satisci": ("saha_satis",),
    "operasyon": ("randevu_arama", "operasyon_planlama", "ticket_defteri"),
    "teknik": ("teknik_saha",),
    # Saha satış ve Teknik saha BİLEREK yok: izinleri İzleme/Planlama'nın içinde; olsaydı yönetici türetilen kümede
    # satışçı ve teknisyen de olur, atanabilir teknisyen listesine düşerdi.
    "yonetici": ("satis_izleme", "randevu_arama", "operasyon_planlama", "ticket_defteri", "pano",
                 "kisi_yonetimi", "veri_yonetimi"),
}
# Yetkinlik → türetilen görev (bölge kapsamı, ana ekran, atanabilir teknisyen listesi bunu kullanır).
_PAKET_GOREVI = {"saha_satis": "satisci", "satis_izleme": "yonetici", "randevu_arama": "operasyon",
                 "operasyon_planlama": "operasyon", "ticket_defteri": "operasyon", "ticket_izleme": "operasyon",
                 "teknik_saha": "teknik",
                 "pano": "yonetici", "kisi_yonetimi": "yonetici", "veri_yonetimi": "yonetici"}
# Müdür/koordinatörlerden v9 göçünde düşen "iş" yetkinlikleri (iş atama, planlama, teknik ekran, saha).
OPERASYONEL_YETKINLIKLER = frozenset({"saha_satis", "satis_izleme", "randevu_arama", "operasyon_planlama",
                                      "teknik_saha", "ticket_defteri", "ticket_izleme"})

# (yöntem, yol şablonu) → eylem. None = herkese açık (giriş gerekmez). Birden çok eylem
# "herhangi biri yeter" demektir. v2 uçları (operasyon/v2, WP-B) da sözleşmeden buraya yazıldı:
# matris testi var olan her rotayı buna göre dener.
ROTA_IZNI: dict[tuple[str, str], str | tuple[str, ...] | None] = {
    # ---- oturum
    ("GET", "/api/saglik"): None,
    ("POST", "/api/giris"): None,
    ("POST", "/api/pin"): None,
    # BOSS ile giriş (boss_giris.py): pencere başlatır/yoklar (yalnız bu bilgisayar), eklenti eşleme koduyla bildirir
    ("POST", "/api/giris/boss/baslat"): None,
    ("GET", "/boss-giris/{istek_id}"): None,
    ("POST", "/api/giris/boss/durum"): None,
    ("POST", "/api/giris/boss/kimlik"): None,
    ("POST", "/api/giris/boss/bitti"): None,
    ("GET", "/api/oturum/boss"): "oturum",
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
    ("GET", "/api/ticket"): ("ticket.oku", "ticket.defter"),
    ("POST", "/api/ticket"): "ticket.defter",
    ("GET", "/api/ticket/sablon"): "ticket.sablon",
    ("GET", "/api/ticket/lokasyon"): "ticket.defter",
    ("GET", "/api/ticket/kategoriler"): "ticket.sablon",
    ("GET", "/api/ticket/harita"): ("ticket.oku", "ticket.defter"),
    ("GET", "/api/ticket/musteri"): "ticket.defter",          # + is.musteri (uçta denetlenir)
    ("GET", "/api/ticket/{ticket_id}"): ("ticket.oku", "ticket.defter"),
    ("PATCH", "/api/ticket/{ticket_id}"): "ticket.defter",
    ("POST", "/api/ticket/{ticket_id}/sil"): "ticket.defter",      # kalıcı silme (ticket.sil)
    ("GET", "/api/ticket/isler"): "ticket.defter",                # + is.musteri müşteri no ile (uçta)
    ("GET", "/api/ticket/temizlik"): "ticket.defter",
    ("POST", "/api/ticket/temizlik"): "ticket.defter",
    ("POST", "/api/ticket/{ticket_id}/isler"): "ticket.defter",
    ("POST", "/api/ticket/{ticket_id}/isler/cikar"): "ticket.defter",
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
    ("POST", "/api/isler/{is_no}/randevu"): ("is.ata", "is.randevu"),
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
    if yuk.get("bg"):                          # BOSS ile giriş: BOSS oturumu bitince uygulama oturumu da biter
        from . import boss_giris
        if not boss_giris.oturum_acik(conn, yuk["bg"], k["id"]):
            raise hata(401, "BOSS oturumunuz kapandı. Yeniden “BOSS ile giriş yap”a basın.", "boss_oturumu_bitti")
    if k.get("rol") not in ROLLER:
        raise hata(403, YASAK_METNI, "yasak")
    kisi_erisimini_yukle(conn, k)
    return k


# ============================================================================= Administrator
_gunluk = logging.getLogger("saha.yetki")
_ADMIN_ONBELLEK: dict = {"anahtar": None, "deger": {}}


def _admin_dosyasi() -> Path:
    """Veri (çalışma) klasöründeki ``turkcell.json``: önce çalışma kökü (``veri\\canli\\turkcell.json``,
    saha.db'nin bir üstü), yoksa saha.db ile aynı klasör."""
    saha = db.db_yolu().parent
    kok = saha.parent / "turkcell.json"
    return kok if kok.exists() else saha / "turkcell.json"


def administrator_ayari() -> dict:
    """{"telefon": "5XXXXXXXXX" | None, "ad": str | None}. Telefon KAYNAKTA YOK: ortam ya da turkcell.json.

    ``TURKCELL_ADMIN_TELEFON`` (ve ``TURKCELL_ADMIN_AD``) verilirse dosyaya bakılmaz (testler).
    Dosya değişikliği tarih damgasıyla izlenir; her istekte yeniden okunmaz.
    """
    ortam = os.environ.get("TURKCELL_ADMIN_TELEFON")
    if ortam is not None:
        return {"telefon": guvenlik.telefon_duzelt(ortam), "ad": os.environ.get("TURKCELL_ADMIN_AD")}
    yol = _admin_dosyasi()
    try:
        anahtar = (str(yol), yol.stat().st_mtime_ns)
    except OSError:
        return {"telefon": None, "ad": None}
    if _ADMIN_ONBELLEK["anahtar"] != anahtar:
        try:
            veri = json.loads(yol.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            veri = {}
        veri = veri if isinstance(veri, dict) else {}
        _ADMIN_ONBELLEK["anahtar"] = anahtar
        _ADMIN_ONBELLEK["deger"] = {
            "telefon": guvenlik.telefon_duzelt(str(veri.get("administrator_telefon") or "")),
            "ad": (str(veri.get("administrator_ad") or "").strip() or None)}
    return dict(_ADMIN_ONBELLEK["deger"])


def _alan(k, ad: str, varsayilan=None):
    try:
        deger = k[ad]
    except (KeyError, IndexError):
        return varsayilan
    return varsayilan if deger is None else deger


def administrator_mi(k) -> bool:
    if not k:
        return False
    tel = administrator_ayari()["telefon"]
    return bool(tel) and _alan(k, "telefon") == tel


def administrator_hesabi_hazirla(conn: sqlite3.Connection) -> int | None:
    """Ayarlı telefonla hesap yoksa açar (davet kodu YALNIZ sunucu günlüğüne); varsa PIN'siz ve davet süresi
    dolmuşsa yeni kod üretir. Hesabın id'si döner (ayar yoksa None). Çağıran commit eder."""
    ayar = administrator_ayari()
    tel = ayar["telefon"]
    if not tel:
        return None
    sutunlar = {r[1] for r in conn.execute("PRAGMA table_info(kullanici)").fetchall()}
    satir = conn.execute("SELECT id, pin_hash, davet_kodu, aktif FROM kullanici WHERE telefon=?",
                         (tel,)).fetchone()
    simdi = ayarlar.zaman_metni()
    if satir is None:
        kod = guvenlik.davet_kodu_uret()
        alan = {"ad": ayar["ad"] or "Administrator", "telefon": tel, "davet_kodu": kod, "rol": "yonetici",
                "aktif": 1, "olusturma": simdi}
        for sutun, deger in (("davet_zamani", simdi), ("yetki_modeli", 1), ("kaynak", "elle")):
            if sutun in sutunlar:
                alan[sutun] = deger
        kid = int(conn.execute(f"INSERT INTO kullanici ({','.join(alan)}) VALUES ({','.join('?' * len(alan))})",
                               tuple(alan.values())).lastrowid)
        try:
            conn.execute("INSERT OR IGNORE INTO kullanici_gorev (kullanici_id, rol) VALUES (?, 'yonetici')", (kid,))
        except sqlite3.OperationalError:
            pass
        _gunluk.warning("Administrator hesabı açıldı. İlk giriş davet kodu: %s (48 saat geçerli)", kod)
        return kid
    kid = int(satir[0])
    if not satir[3]:
        conn.execute("UPDATE kullanici SET aktif=1 WHERE id=?", (kid,))
    if "yetki_modeli" in sutunlar:
        conn.execute("UPDATE kullanici SET yetki_modeli=1 WHERE id=? AND yetki_modeli=0", (kid,))
    if not satir[1]:
        doldu = True
        if satir[2] and "davet_zamani" in sutunlar:
            z = conn.execute("SELECT davet_zamani FROM kullanici WHERE id=?", (kid,)).fetchone()[0]
            try:
                doldu = bool(z) and (ayarlar.simdi() - dt.datetime.fromisoformat(str(z)).replace(tzinfo=None)
                                     > dt.timedelta(hours=ayarlar.DAVET_GECERLILIK_SAAT))
            except (TypeError, ValueError):
                doldu = True
        elif satir[2]:
            doldu = False
        if doldu:
            kod = guvenlik.davet_kodu_uret()
            if "davet_zamani" in sutunlar:
                conn.execute("UPDATE kullanici SET davet_kodu=?, davet_zamani=? WHERE id=?", (kod, simdi, kid))
            else:
                conn.execute("UPDATE kullanici SET davet_kodu=? WHERE id=?", (kod, kid))
            _gunluk.warning("Administrator ilk giriş davet kodu: %s (48 saat geçerli)", kod)
    return kid


# ============================================================================= unvan + yetkinlik → etkin erişim
def unvan_anahtari(metin: str | None) -> str:
    """Türkçe harf, boşluk ve tire duyarsız karşılaştırma anahtarı ("EÇM-Fiber- Teknik - Sorumlu")."""
    tablo = str.maketrans("ÇĞİIÖŞÜçğıiöşüÂâÎîÛû", "CGIIOSUCGIIOSUAAIIUU")
    return "".join(ch for ch in str(metin or "").translate(tablo).upper() if ch.isalnum())


def yetkinlik_sirala(kodlar) -> list[str]:
    kume = set(kodlar or ())
    return [y for y in YETKINLIKLER if y in kume]


def paket_izinleri(kodlar) -> frozenset[str]:
    izinler = set(TEMEL_IZINLER)
    for y in kodlar or ():
        izinler.update(YETKINLIKLER.get(y, {}).get("izinler", ()))
    return frozenset(izinler)


def gorevler_turet(kodlar) -> list[str]:
    kume = {_PAKET_GOREVI[y] for y in kodlar or () if y in _PAKET_GOREVI}
    return [r for r in ROLLER if r in kume]


def gorev_paketleri(gorevler_) -> list[str]:
    kume: set[str] = set()
    for r in gorevler_ or ():
        kume.update(GOREV_PAKETLERI.get(r, ()))
    return yetkinlik_sirala(kume)


def eski_izinler(gorevler_) -> frozenset[str]:
    """Eski (görev kümesi) modelin izinleri."""
    kume = frozenset(gorevler_ or ())
    return frozenset(e for e, roller in IZINLER.items() if kume & roller)


def takim_lideri_yetkinlikleri(conn: sqlite3.Connection) -> list[str]:
    try:
        satir = conn.execute("SELECT deger FROM ayar WHERE anahtar='takim_lideri_yetkinlikleri'").fetchone()
        liste = json.loads(satir[0]) if satir and satir[0] else []
    except (sqlite3.Error, ValueError, TypeError):
        liste = []
    return yetkinlik_sirala(x for x in liste if isinstance(x, str)) if isinstance(liste, list) else []


def unvan_yetkinlikleri(conn: sqlite3.Connection, unvan_id: int | None) -> list[str]:
    if not unvan_id:
        return []
    try:
        return yetkinlik_sirala(r[0] for r in conn.execute(
            "SELECT yetkinlik FROM unvan_yetkinlik WHERE unvan_id=?", (unvan_id,)).fetchall())
    except sqlite3.OperationalError:
        return []


def ek_yetkinlikler(conn: sqlite3.Connection, kullanici_id: int) -> list[str]:
    try:
        return yetkinlik_sirala(r[0] for r in conn.execute(
            "SELECT yetkinlik FROM kullanici_yetkinlik WHERE kullanici_id=?", (kullanici_id,)).fetchall())
    except sqlite3.OperationalError:
        return []


def _sozluk(conn: sqlite3.Connection, satir) -> dict:
    if isinstance(satir, dict):
        return satir
    if hasattr(satir, "keys"):
        return {a: satir[a] for a in satir.keys()}
    adlar = [r[1] for r in conn.execute("PRAGMA table_info(kullanici)").fetchall()]
    return dict(zip(adlar, satir))


def erisim(conn: sqlite3.Connection, k) -> dict:
    """Kişinin etkin erişimi: {administrator, yetki_modeli, yetkinlikler, ek, unvan_yetkinlikleri,
    izinler (frozenset), gorevler (liste)}."""
    k = _sozluk(conn, k)
    if administrator_mi(k):
        return {"administrator": True, "yetki_modeli": True, "yetkinlikler": list(YETKINLIKLER),
                "unvan_yetkinlikleri": [], "ek": [], "izinler": frozenset(IZINLER), "gorevler": list(ROLLER)}
    if int(_alan(k, "yetki_modeli", 0) or 0):
        unvandan = unvan_yetkinlikleri(conn, _alan(k, "unvan_id"))
        ek = ek_yetkinlikler(conn, k["id"])
        kodlar = set(unvandan) | set(ek)
        if int(_alan(k, "takim_lideri", 0) or 0):
            kodlar |= set(takim_lideri_yetkinlikleri(conn))
        kodlar = yetkinlik_sirala(kodlar)
        return {"administrator": False, "yetki_modeli": True, "yetkinlikler": kodlar,
                "unvan_yetkinlikleri": unvandan, "ek": ek,
                "izinler": paket_izinleri(kodlar), "gorevler": gorevler_turet(kodlar)}
    kume = gorev_kumesi_oku(conn, k)
    return {"administrator": False, "yetki_modeli": False, "yetkinlikler": gorev_paketleri(kume),
            "unvan_yetkinlikleri": [], "ek": [], "izinler": eski_izinler(kume), "gorevler": kume}


def kisi_erisimini_yukle(conn: sqlite3.Connection, k: dict) -> dict:
    """``mevcut_kullanici`` sözlüğüne etkin erişimi yazar (izinli/gorevler/kisi.izinli bunu okur)."""
    e = erisim(conn, k)
    k["gorevler"] = list(e["gorevler"])
    k["izinler"] = e["izinler"]
    k["yetkinlikler"] = e["yetkinlikler"]
    k["administrator"] = e["administrator"]
    if e["yetki_modeli"]:
        k["_turetildi"] = True
        # Ana görev (girişte açılan ekran, /api/ben dalı) türetilmiş kümede değilse kümenin ilkine döner.
        if e["gorevler"] and k.get("rol") not in e["gorevler"]:
            k["rol"] = e["gorevler"][0]
    return k


def gorev_onbellegi_yaz(conn: sqlite3.Connection, kid: int) -> dict:
    """Yetki modelindeki kişinin ``rol`` + ``kullanici_gorev`` satırlarını yetkinliklerden yeniden yazar.

    Atanabilir teknisyen listesi, Ekip kartları ve eski raporlar bu tabloyu okur. Türetilmiş küme boşsa
    (ör. yalnız Depo) ana görev olduğu gibi kalır. Döner: {once, sonra}. Çağıran commit eder.
    """
    satir = conn.execute("SELECT * FROM kullanici WHERE id=?", (kid,)).fetchone()
    if satir is None:
        return {"once": [], "sonra": []}
    k = _sozluk(conn, satir)
    once = gorev_kumesi_oku(conn, k)
    sonra = list(erisim(conn, k)["gorevler"])
    rol = k["rol"] if (not sonra or k["rol"] in sonra) else sonra[0]
    if rol != k["rol"]:
        conn.execute("UPDATE kullanici SET rol=? WHERE id=?", (rol, kid))
    yeni = [r for r in ROLLER if r in (set(sonra) | {rol})]
    conn.execute(f"DELETE FROM kullanici_gorev WHERE kullanici_id=? AND rol NOT IN ({','.join('?' * len(yeni))})",
                 (kid, *yeni))
    conn.executemany("INSERT OR IGNORE INTO kullanici_gorev (kullanici_id, rol) VALUES (?,?)",
                     [(kid, r) for r in yeni])
    return {"once": once, "sonra": yeni}


# ============================================================================= izinler
def gorevler(k: dict) -> frozenset[str]:
    """Kişinin görev kümesi (``mevcut_kullanici`` doldurur; yoksa yalnız ana görev).

    Yetki modelinde (``_turetildi``) küme yetkinliklerden türetilmiştir; ana görev ayrıca eklenmez.
    """
    if k.get("_turetildi"):
        return frozenset(r for r in (k.get("gorevler") or ()) if r in ROLLER)
    kume = set(k.get("gorevler") or ())
    kume.add(k.get("rol"))
    return frozenset(r for r in kume if r in ROLLER)


def izinli(k: dict, eylem: str) -> bool:
    """Varsayılan YASAK: tabloda olmayan eylem hiç kimseye verilmez.

    ``mevcut_kullanici``'dan gelen kişide etkin izinler (``k["izinler"]``) esastır; yoksa görev kümesi.
    """
    if "izinler" in k:
        return eylem in IZINLER and eylem in k["izinler"]
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
    if isinstance(kisi, dict) and "izinler" in kisi:
        return sorted(e for e in kisi["izinler"] if e != "oturum" and e in IZINLER)
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


def ana_ekran_kisi(k: dict) -> str:
    """Etkin izinlere göre ana ekran: 'bugun' | 'isler' | 'islerim' | 'takip' | 'ekip' | 'depo'.

    Görevi olan kişide eski kural (ana göreve göre); yalnız Pano / Kişi yönetimi / Depo yetkinliği olan
    (müdür, İK, stok) kişide açabildiği ilk ekran.
    """
    izinler = k.get("izinler")
    if izinler is None:
        return ana_ekran(k.get("rol"))
    rol = k.get("rol")
    aday = ana_ekran(rol)
    gerekli = {"bugun": "satis.kendi", "isler": "is.liste", "islerim": "is.saha"}
    if rol in gorevler(k) and gerekli.get(aday) in izinler:
        if aday == "isler" and not ({"is.ata", "is.randevu", "takip.oku"} & izinler) and "is.saha" in izinler:
            return "islerim"
        return aday
    for ekran, izin_adi in (("isler", "is.ata"), ("isler", "is.randevu"), ("bugun", "satis.kendi"),
                            ("islerim", "is.saha"), ("takip", "takip.oku"), ("ekip", "ekip.yonet"),
                            ("depo", "depo.yonet")):
        if izin_adi in izinler:
            return ekran
    return "bugun"


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
