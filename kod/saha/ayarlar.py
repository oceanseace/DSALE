"""Saha Sistemi ayarları: dosya yolları, sabitler, ofis konumu.

Hiçbir değer internete açılmaz; sunucu ofis ağında çalışır.
"""
from __future__ import annotations

import datetime as dt
import os
import sys
from pathlib import Path

import yollar


def konsolu_hazirla() -> None:
    """Windows konsolunda Türkçe karakterler hata vermesin (cp1254/cp857).

    Ofis bilgisayarında komut istemi hangi kod sayfasında olursa olsun sunucu
    açılış metni yüzünden çökmemeli.
    """
    for akis in (sys.stdout, sys.stderr):
        try:
            akis.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError, ValueError):
            pass


# ----------------------------------------------------------------------------- yollar
# Bütün yollar kod/yollar.py'den gelir (tek kaynak). Salt okunur girdiler depodadır (veri/, cikti/,
# kod/arayuz/dist); sunucunun YAZDIĞI her şey çalışma klasöründedir (yollar.CALISMA_SAHA):
#   geliştirme: gelistirme/veri/saha/   ·   canlı: SAHA_VERI_DIZINI=canli\veri → canli/veri/saha/
# TODO(YAYINLA): canlıya yayınlarken sunucu SAHA_VERI_DIZINI=canli\veri ile başlatılmalı; ayrıntı KORUNAN.txt.
CALISMA = yollar.CALISMA_SAHA                  # yazılabilir kök: saha.db, gizli.key, yedek/, kayit/, ek/, raporlar/

VERI_BINA = yollar.VERI / "master" / "bina_master.csv"
VERI_ATAMA = yollar.CIKTI / "N08_res_hp" / "atama.csv"
VERI_YOLLAR = yollar.VERI / "ref" / "osm_yollar.geojson"   # harita arka planı (isteğe bağlı)

# Testler SAHA_DB ile geçici bir dosyaya yönlendirir.
DB_YOLU = Path(os.environ.get("SAHA_DB") or (CALISMA / "saha.db"))
GIZLI_ANAHTAR = CALISMA / "gizli.key"
KAYIT_DIZINI = CALISMA / "kayit"
PWA_DIZINI = yollar.ARAYUZ_DIST
VERI_GEOMETRI = yollar.VERI / "master" / "bina_geometri.json"   # bina taban poligonları (3B ikiz)
ONEMAP_ARACI = yollar.KOD / "saha" / "araclar" / "onemap_cek.js"


def gelen_dizini() -> Path:
    """Yüklenen tur raporları ve OneMap dökümleri (çalışma klasöründe ``gelen/``). Testler ``SAHA_GELEN`` ile yönlendirir."""
    return Path(os.environ.get("SAHA_GELEN") or (yollar.CALISMA / "gelen"))


def cikti_dizini() -> Path:
    """Sunucunun ürettiği dosyalar (plan önbelleği, bölgeleme Excel'i; çalışma klasöründe ``cikti/``).
    Testler ``SAHA_CIKTI`` ile yönlendirir."""
    return Path(os.environ.get("SAHA_CIKTI") or (yollar.CALISMA / "cikti"))

# ----------------------------------------------------------------------------- saat
# Türkiye tüm yıl UTC+3; yaz saati uygulaması yok.
TR = dt.timezone(dt.timedelta(hours=3), "TRT")


def simdi() -> dt.datetime:
    """Türkiye saatiyle şu an (saniye hassasiyetinde, saat dilimi bilgisi olmadan)."""
    return dt.datetime.now(TR).replace(tzinfo=None, microsecond=0)


def bugun() -> dt.date:
    """Türkiye saatiyle bugünün tarihi."""
    return simdi().date()


def zaman_metni(an: dt.datetime | None = None) -> str:
    return (an or simdi()).isoformat(sep=" ", timespec="seconds")


# ----------------------------------------------------------------------------- ofis
# dsale/config.py ile aynı nokta: Dehanet EÇM, Nilüfer / Bursa.
OFIS = {"ad": "Dehanet EÇM Ofis", "lat": 40.22043814320989, "lon": 28.953528321918512}

# ----------------------------------------------------------------------------- iş kuralları
BOLGE_SAYISI = 8
VARSAYILAN_ADET = 25            # bir günlük tura kaç bina konur
EN_FAZLA_ADET = 60
ADAY_HAVUZU = 200               # rota kurulurken bakılan en öncelikli bina sayısı
SOGUMA_GUN = 30                 # ziyaret edilen bina kaç gün listeye girmez
RANDEVU_GUN = 3                 # "randevu" sonucunda varsayılan tekrar aralığı
EVDE_YOK_GUN = 7                # "evde yok" sonucunda varsayılan tekrar aralığı

# Hiç dokunulmamış bina, fırsatı sıfır bile olsa listeye girebilmeli: kapsama
# tavanı %100 olmalı. Öncelik puanı bu tabanın altına inmez.
TABAN_ONCELIK = 0.01
# Site bütünlüğü için günlük liste en çok bu kadar bina aşabilir (bir siteye
# girip bir bloğunu bırakıp gitmek sahada en çok vakit kaybettiren şey).
LISTE_TASMA = 5
# Öncelik seçiminde yakınlık terimi: bu kadar km uzaklık, adayın puanını
# yarıya indirir. Olmadığında algoritma bölgenin dört bir yanından bina seçip
# bir günde gezilemeyecek 78 km'lik turlar kuruyordu.
YAKINLIK_KM = 2.0
# Günlük tur bunu aşarsa satışçıya da yöneticiye de uyarı gösterilir.
UZUN_TUR_KM = 25.0
# Sahadan gelen zaman damgası bu pencerenin dışındaysa sunucu saatine çekilir:
# bozuk saatli tek bir telefon binaları kalıcı olarak kapsamadan düşürmesin.
ZAMAN_ILERI_DK = 5
ZAMAN_GERI_GUN = 14

# ----------------------------------------------------------------------------- güvenlik
TOKEN_GUN = 30                  # saha ekibi gün ortasında sistemden atılmamalı
KILIT_DAKIKA = 15               # hatalı deneme sayacının penceresi
# Telefon numarası başına SERT KİLİT YOK: doğru PIN her zaman kabul edilir,
# yanlış PIN yavaşlatılır. Aksi halde ağdaki herhangi biri bir satışçının
# numarasına 5 yanlış PIN yollayıp onu gün boyu sahada kilitli bırakabiliyordu.
YAVASLATMA_ESIGI = 3            # bu kadar hatadan sonra yanıt geciktirilmeye başlar
YAVASLATMA_ADIM_SN = 0.5        # her ek hata için eklenen gecikme
YAVASLATMA_EN_COK_SN = 3.0
IP_DENEME = 30                  # tek IP'den 15 dakikada en çok bu kadar hatalı deneme
IP_YOKLAMA = 60                 # tek IP'den 15 dakikada en çok bu kadar "PIN var mı" yoklaması
PIN_UZUNLUK = 4
# Swagger arayüzü ve OpenAPI şeması yalnız geliştirmede açılır: üretimde ağdaki
# herkese iç API yüzeyini göstermemeli ve harici CDN'den dosya çekmemeli.
GELISTIRME = os.environ.get("SAHA_GELISTIRME") == "1"

# ----------------------------------------------------------------------------- sözlükler
# Dört görev (spec §2.1). ``satisci`` ve ``yonetici`` SQL'e gömülü: yeniden adlandırılmaz.
ROLLER = ("satisci", "operasyon", "teknik", "yonetici")
DAVET_GECERLILIK_SAAT = 48      # yeni davet kodu (davet_zamani dolu) bu kadar saat geçerli

BINA_DURUMLARI = (
    "bekliyor",         # hiç dokunulmadı
    "planli",           # bugünün listesinde
    "ziyaret_edildi",
    "tekrar_gel",
    "girilemedi",       # yönetici/kapıcı izin vermedi
    "altyapi_sorunu",
)

ZIYARET_SONUCLARI = (
    "satis",
    "ilgilenmedi",
    "evde_yok",
    "randevu",
    "altyapi_sorunu",
    "girilemedi",
    "yanlis_adres",
)

# Bir ziyaret sonucunun binayı hangi duruma taşıdığı.
SONUC_DURUM = {
    "satis": "ziyaret_edildi",
    "ilgilenmedi": "ziyaret_edildi",
    "evde_yok": "tekrar_gel",
    "randevu": "tekrar_gel",
    "altyapi_sorunu": "altyapi_sorunu",
    "girilemedi": "girilemedi",
    "yanlis_adres": "ziyaret_edildi",
}

# Resmî etiketler: yönetici konsolu, Excel raporu, bina geçmişi.
SONUC_ETIKET = {
    "satis": "Satış",
    "ilgilenmedi": "İlgilenmedi",
    "evde_yok": "Evde yok",
    "randevu": "Randevu",
    "altyapi_sorunu": "Altyapı sorunu",
    "girilemedi": "Girilemedi",
    # "Bina burada değil" hem satışçıya hem yöneticiye aynı şeyi anlatır;
    # "Yanlış adres" kimin yanlış yazdığı belirsiz bırakıyordu.
    "yanlis_adres": "Bina burada değil",
}

# Satışçı ekranı ile rapor AYNI KELİMEYİ kullanır. Eskiden aynı sonuç telefonda
# "Giremedim", raporda "Girilemedi" yazıyor; iki ekranı yan yana koyan yönetici
# farklı bir şey sanıyordu. Tek sözlük, tek kaynak: uygulama bunu /api/ben ile
# alır, istemcideki liste yalnız çevrimdışı yedektir.
SONUC_ETIKET_SAHA = dict(SONUC_ETIKET)

# Kapsama ölçüsünde "temas" sayılan sonuçlar: kapı açıldı, biriyle konuşuldu.
# 'girilemedi' ve 'altyapi_sorunu' binaya GİDİLDİ ama kimseyle konuşulmadı.
TEMAS_SONUCLARI = ("satis", "ilgilenmedi", "evde_yok", "randevu")

DURUM_ETIKET = {
    "bekliyor": "Bekliyor",
    "planli": "Planlı",
    "ziyaret_edildi": "Ziyaret edildi",
    "tekrar_gel": "Tekrar gel",
    "girilemedi": "Girilemedi",
    "altyapi_sorunu": "Altyapı sorunu",
}
