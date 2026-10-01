"""v2 şeması: iş emri akışı, dört görev, öbek/mahalle sözlüğü (belgeler/OPERASYON_V2_SPEC.md §1 + Ek A2).

Tek kaynak burasıdır: hem göç adımları (``saha/goc.py``) hem taze kurulum (``db.semayi_kur``)
aynı sabitleri kullanır; ``test_goc.py::test_sutun_kumesi_taze_ile_ayni`` ikisinin aynı
şemayı ürettiğini denetler.

Kurallar (spec §1.1):
  * Göçler yalnız EKLER. Tek istisna ``kullanici`` rol CHECK'i (v1, doğrulanmış yeniden kurma).
  * Yeni tablolarda dar CHECK yok; değer listeleri Python sabitinden üretilen, düşürülüp yeniden
    kurulabilen tetikleyicilerle korunur (``is_emri_tetikleyicileri``).
  * İz tabloları kişiye FK taşımaz (``kullanici_id`` + ``kullanici_ad`` anlık görüntüsü); iş tutan
    bağlar (``is_emri.atanan_id``, ``obek.sahip_id``, ``obek.yedek_id``) FK'lıdır.
  * ``executescript`` kullanılmaz (kendiliğinden commit eder): metinler ``ifadeler()`` ile tek tek
    ifadelere bölünür, her biri çağıranın açtığı işlemin içinde ``execute`` edilir.
"""
from __future__ import annotations

import json
import sqlite3

# ----------------------------------------------------------------------------- sürüm
# 1 kullanici_rol_dort · 2 kullanici_ek_sutunlar · 3 obek_ve_mahalle · 4 is_emri_tablolari ·
# 5 indeks_onarim · 6 kullanici_gorev (Ek-1) · 7 is_aski (Ek-3) · 8 ticket_ek_ve_ps26 (Ek-5, Ek-8)
HEDEF = 8

ROLLER = ("satisci", "operasyon", "teknik", "yonetici")

# ----------------------------------------------------------------------------- kullanıcı (v1, v2)
# Göç öncesi ve sonrası birebir karşılaştırılan 10 sütun (spec §1.4 özet h0).
KULLANICI_SUTUNLARI_10 = ("id", "ad", "telefon", "pin_hash", "davet_kodu", "rol", "bolge",
                          "aktif", "oturum_no", "olusturma")

# v1'de kurulan tanım. Spec §1.4'ün doğrulanmış SQL'i; TEK DEĞİŞİKLİK Ek-2: telefon NOT NULL
# değil (SQLite UNIQUE birden çok NULL'a izin verir) — BOSS Mobil'le çalışan girişsiz kişiler.
# Eski SQL'in metin değişimiyle ÜRETİLMEZ.
KULLANICI_TANIMI_10 = """CREATE TABLE kullanici_yeni (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ad TEXT NOT NULL,
    telefon TEXT UNIQUE,
    pin_hash TEXT,
    davet_kodu TEXT,
    rol TEXT NOT NULL CHECK (rol IN ('satisci','operasyon','teknik','yonetici')),
    bolge INTEGER,
    aktif INTEGER NOT NULL DEFAULT 1,
    oturum_no INTEGER NOT NULL DEFAULT 1,
    olusturma TEXT NOT NULL
)"""

# v2: yalnız ALTER ADD (her biri yalnız sütun yoksa yazılır).
KULLANICI_EK_SUTUNLAR = (
    ("etiket", "TEXT"),          # JSON liste: ["lider"] / ["btk","arama"]; YETKİ VERMEZ
    ("boss_ekip", "TEXT"),       # teknik: BOSS "Ekip" sütunundaki ad (eşleşme anahtarı)
    ("kapasite", "INTEGER"),     # teknik: günlük iş; NULL → ayar teknik_kapasite
    ("davet_zamani", "TEXT"),    # yeni davet kodunun üretildiği an (48 s geçerlilik)
    ("oturum_neden", "TEXT"),    # son oturum_no artışının nedeni: pin|gorev|bolge|pasif|cihaz
    ("unvan", "TEXT"),           # Ek-2: Turkcell unvanı (personel rehberinden)
    ("kaynak", "TEXT"),          # Ek-2: 'elle' | 'rehber'
)

# Taze kurulumdaki tanım: v1 tanımı + v2 sütunları, aynı sırayla. db.SEMA bunu kullanır.
KULLANICI_TAZE = """CREATE TABLE IF NOT EXISTS kullanici (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ad          TEXT    NOT NULL,
    telefon     TEXT    UNIQUE,                   -- 5XXXXXXXXX; NULL = girişsiz kişi (BOSS Mobil)
    pin_hash    TEXT,                             -- NULL ise PIN ilk girişte belirlenir
    davet_kodu  TEXT,                             -- yöneticinin verdiği tek kullanımlık kod
    rol         TEXT    NOT NULL CHECK (rol IN ('satisci','operasyon','teknik','yonetici')),
    bolge       INTEGER,                          -- satışta 1..N, diğerlerinde NULL
    aktif       INTEGER NOT NULL DEFAULT 1,
    oturum_no   INTEGER NOT NULL DEFAULT 1,       -- PIN/görev/bölge değişince artar, eski jetonlar düşer
    olusturma   TEXT    NOT NULL,
    etiket      TEXT,
    boss_ekip   TEXT,
    kapasite    INTEGER,
    davet_zamani TEXT,
    oturum_neden TEXT,
    unvan       TEXT,
    kaynak      TEXT
);
"""

# ----------------------------------------------------------------------------- v3 öbek + mahalle
V3 = """
CREATE TABLE IF NOT EXISTS ilce (
    il_k TEXT NOT NULL, ilce_k TEXT NOT NULL, il TEXT NOT NULL, ad TEXT NOT NULL,
    lat REAL, lon REAL, PRIMARY KEY (il_k, ilce_k));
CREATE TABLE IF NOT EXISTS ilce_esad (
    il_k TEXT NOT NULL, esad_k TEXT NOT NULL, ilce_k TEXT NOT NULL, PRIMARY KEY (il_k, esad_k));
CREATE TABLE IF NOT EXISTS mahalle (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    il TEXT NOT NULL, ilce TEXT NOT NULL, ad TEXT NOT NULL,
    il_k TEXT NOT NULL, ilce_k TEXT NOT NULL, mahalle_k TEXT NOT NULL,
    lat REAL, lon REAL,
    kaynak TEXT NOT NULL,
    ekleyen_id INTEGER, ekleyen_ad TEXT,
    eklenme TEXT NOT NULL,
    UNIQUE (il_k, ilce_k, mahalle_k));
CREATE TABLE IF NOT EXISTS mahalle_esad (
    il_k TEXT NOT NULL, ilce_k TEXT NOT NULL, esad_k TEXT NOT NULL,
    mahalle_id INTEGER NOT NULL REFERENCES mahalle(id),
    ekleyen_id INTEGER, eklenme TEXT NOT NULL,
    PRIMARY KEY (il_k, ilce_k, esad_k));
CREATE TABLE IF NOT EXISTS obek (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ad TEXT NOT NULL,
    ad_k TEXT NOT NULL UNIQUE,
    renk INTEGER NOT NULL DEFAULT 0,
    sahip_id INTEGER REFERENCES kullanici(id),
    yedek_id INTEGER REFERENCES kullanici(id),
    aktif INTEGER NOT NULL DEFAULT 1,
    olusturma TEXT NOT NULL, guncelleme TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS obek_mahalle (
    il_k TEXT NOT NULL, ilce_k TEXT NOT NULL, mahalle_k TEXT NOT NULL,
    obek_id INTEGER NOT NULL REFERENCES obek(id),
    ref TEXT NOT NULL,
    ekleyen_id INTEGER, eklenme TEXT NOT NULL,
    PRIMARY KEY (il_k, ilce_k, mahalle_k));
CREATE INDEX IF NOT EXISTS ix_obek_mahalle_obek ON obek_mahalle(obek_id);
CREATE TABLE IF NOT EXISTS obek_olay (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    zaman TEXT NOT NULL,
    kullanici_id INTEGER, kullanici_ad TEXT,
    tur TEXT NOT NULL,
    obek_id INTEGER,
    veri TEXT NOT NULL,
    surum INTEGER NOT NULL,
    toplu_id TEXT);
CREATE TRIGGER IF NOT EXISTS trg_obek_olay_degismez BEFORE UPDATE ON obek_olay
BEGIN SELECT RAISE(ABORT, 'obek_olay degistirilemez'); END;
CREATE TRIGGER IF NOT EXISTS trg_obek_olay_silinmez BEFORE DELETE ON obek_olay
BEGIN SELECT RAISE(ABORT, 'obek_olay silinemez'); END;
"""

# ----------------------------------------------------------------------------- v4 iş emri
IS_DURUMLARI = ("triyaj", "bekliyor", "randevulu", "atandi", "yolda", "sahada",
                "ulasilamadi", "askida", "altyapi", "merkeze", "cozuldu", "kapandi")
IS_KAYNAKLARI = ("boss", "bayi")

V4 = """
CREATE TABLE IF NOT EXISTS ie_aktarim (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kaynak TEXT NOT NULL DEFAULT 'boss_teknik_task',
    yontem TEXT NOT NULL DEFAULT 'surukle',
    dosya_adi TEXT NOT NULL,
    dosya_sha256 TEXT NOT NULL,
    dosya_zamani TEXT,
    rapor_en_yeni TEXT,
    yukleyen_id INTEGER, yukleyen_ad TEXT,
    baslama TEXT NOT NULL, bitis TEXT,
    durum TEXT NOT NULL DEFAULT 'isleniyor',
    tam_kapsam INTEGER NOT NULL DEFAULT 1,
    satir INTEGER, cikarilan INTEGER, is_sayisi INTEGER,
    yeni INTEGER, degisen INTEGER, kaybolan INTEGER, yeniden_acilan INTEGER, degismeyen INTEGER,
    kontrol INTEGER, boss_atamasi INTEGER,
    onay_nedeni TEXT,
    ozet TEXT,
    yedek_yolu TEXT,
    hata TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS ux_aktarim_sha ON ie_aktarim(dosya_sha256) WHERE durum = 'uygulandi';
CREATE INDEX IF NOT EXISTS ix_aktarim_zaman ON ie_aktarim(baslama);

CREATE TABLE IF NOT EXISTS is_emri (
    is_no TEXT PRIMARY KEY,
    boss_task_no TEXT UNIQUE,
    kaynak TEXT NOT NULL,
    satis_kanali TEXT,
    kanal_grubu TEXT,
    task_adi TEXT NOT NULL,
    serit TEXT NOT NULL,
    btk_hedef_saat INTEGER,
    musteri_no TEXT,
    musteri_ozet TEXT,
    musteri_adi TEXT,
    musteri_tel TEXT,
    adres TEXT,
    il TEXT, ilce TEXT, mahalle TEXT,
    il_k TEXT, ilce_k TEXT, mahalle_k TEXT,
    mahalle_kaynak TEXT,
    mahalle_elle INTEGER NOT NULL DEFAULT 0,
    lokasyon TEXT,
    bina_serial TEXT,
    lat REAL, lon REAL,
    konum_kaynak TEXT,
    konum_yaklasik INTEGER NOT NULL DEFAULT 0,
    obek_id INTEGER REFERENCES obek(id),
    obek_elle_id INTEGER REFERENCES obek(id),
    parca TEXT, parca_tarih TEXT,
    triyaj_nedeni TEXT,
    boss_durum TEXT, boss_randevu_durumu TEXT, boss_randevu_bas TEXT, boss_randevu_bit TEXT,
    boss_ekip TEXT, boss_aski_nedeni TEXT, boss_sl TEXT, boss_sl_saat REAL, boss_son_aciklama TEXT,
    boss_ozet TEXT,
    boss_bekleyen TEXT,
    boss_islendi TEXT,
    boss_kapanmadi INTEGER NOT NULL DEFAULT 0,
    durum TEXT NOT NULL,
    durum_zamani TEXT NOT NULL,
    atanan_id INTEGER REFERENCES kullanici(id),
    atama_kaynagi TEXT,
    randevu_bas TEXT, randevu_bit TEXT,
    randevu_teyitli INTEGER NOT NULL DEFAULT 0,
    oneri_teknik_id INTEGER, oneri_bas TEXT, oneri_bit TEXT, oneri_neden TEXT,
    sira INTEGER,
    ticket_id INTEGER REFERENCES ticket(id),
    uyanma TEXT, askida_neden TEXT,
    evde_yok_sayisi INTEGER NOT NULL DEFAULT 0,
    masa_vade TEXT,
    teshis_sonucu TEXT,
    kotu_gecmis INTEGER NOT NULL DEFAULT 0,
    sonuc_kodu TEXT, evde_miydi INTEGER,
    kapanis_nedeni TEXT,
    tekrar7g INTEGER NOT NULL DEFAULT 0,
    acilis TEXT NOT NULL,
    son24 TEXT NOT NULL,
    btk_hedef TEXT,
    ilk_gorulme TEXT NOT NULL,
    gorulme_zamani TEXT NOT NULL,
    ilk_atama_zamani TEXT,
    atama_zamani TEXT, teknik_gordu TEXT,
    yolda_zamani TEXT, sahada_zamani TEXT, cozum_zamani TEXT,
    son_gorulme TEXT,
    kapanis TEXT,
    kapanis_kesin INTEGER NOT NULL DEFAULT 1,
    acilma_sayisi INTEGER NOT NULL DEFAULT 1,
    son_aktarim_id INTEGER REFERENCES ie_aktarim(id),
    olusturan_id INTEGER, olusturan_ad TEXT,
    surum INTEGER NOT NULL DEFAULT 1,
    guncelleme TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_is_durum     ON is_emri(durum, son24);
CREATE INDEX IF NOT EXISTS ix_is_obek      ON is_emri(obek_id, durum);
CREATE INDEX IF NOT EXISTS ix_is_obek_elle ON is_emri(obek_elle_id);
CREATE INDEX IF NOT EXISTS ix_is_atanan    ON is_emri(atanan_id, durum);
CREATE INDEX IF NOT EXISTS ix_is_mahalle   ON is_emri(il_k, ilce_k, mahalle_k);
CREATE INDEX IF NOT EXISTS ix_is_bina      ON is_emri(bina_serial);
CREATE INDEX IF NOT EXISTS ix_is_musteri   ON is_emri(musteri_ozet, task_adi);
CREATE INDEX IF NOT EXISTS ix_is_ticket    ON is_emri(ticket_id);

CREATE TABLE IF NOT EXISTS is_emri_olay (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    is_no TEXT NOT NULL REFERENCES is_emri(is_no),
    zaman TEXT NOT NULL,
    kayit_zamani TEXT NOT NULL,
    kullanici_id INTEGER, kullanici_ad TEXT,
    tur TEXT NOT NULL,
    eski TEXT, yeni TEXT,
    notu TEXT,
    aktarim_id INTEGER,
    toplu_id TEXT,
    istemci_id TEXT);
CREATE INDEX IF NOT EXISTS ix_olay_is ON is_emri_olay(is_no, id);
CREATE INDEX IF NOT EXISTS ix_olay_toplu ON is_emri_olay(toplu_id) WHERE toplu_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ux_olay_istemci ON is_emri_olay(kullanici_id, istemci_id) WHERE istemci_id IS NOT NULL;
CREATE TRIGGER IF NOT EXISTS trg_is_olay_degismez BEFORE UPDATE ON is_emri_olay
BEGIN SELECT RAISE(ABORT, 'is_emri_olay degistirilemez'); END;
CREATE TRIGGER IF NOT EXISTS trg_is_olay_silinmez BEFORE DELETE ON is_emri_olay
BEGIN SELECT RAISE(ABORT, 'is_emri_olay silinemez'); END;

CREATE TABLE IF NOT EXISTS erisim_kaydi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    zaman TEXT NOT NULL, gun TEXT NOT NULL,
    kullanici_id INTEGER NOT NULL, kullanici_ad TEXT,
    eylem TEXT NOT NULL,
    is_no TEXT, adet INTEGER, ip TEXT);
CREATE INDEX IF NOT EXISTS ix_erisim ON erisim_kaydi(kullanici_id, zaman);
CREATE UNIQUE INDEX IF NOT EXISTS ux_erisim_gun ON erisim_kaydi(gun, kullanici_id, eylem, is_no) WHERE is_no IS NOT NULL;
CREATE TRIGGER IF NOT EXISTS trg_erisim_degismez BEFORE UPDATE ON erisim_kaydi
BEGIN SELECT RAISE(ABORT, 'erisim_kaydi degistirilemez'); END;

CREATE TABLE IF NOT EXISTS takip_anlik (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    zaman TEXT NOT NULL, aktarim_id INTEGER,
    acik INTEGER, asan24 INTEGER, btk_asan48 INTEGER, atanmamis INTEGER, altyapi INTEGER);

CREATE TABLE IF NOT EXISTS yonetim_kaydi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    zaman TEXT NOT NULL,
    kullanici_id INTEGER, kullanici_ad TEXT,
    eylem TEXT NOT NULL,
    hedef TEXT,
    ozet TEXT);
CREATE TRIGGER IF NOT EXISTS trg_yonetim_kaydi_degismez BEFORE UPDATE ON yonetim_kaydi
BEGIN SELECT RAISE(ABORT, 'yonetim_kaydi degistirilemez'); END;
CREATE TRIGGER IF NOT EXISTS trg_yonetim_kaydi_silinmez BEFORE DELETE ON yonetim_kaydi
BEGIN SELECT RAISE(ABORT, 'yonetim_kaydi silinemez'); END;
"""


def is_emri_tetikleyicileri(durumlar=IS_DURUMLARI, kaynaklar=IS_KAYNAKLARI) -> list[str]:
    """``is_emri`` değer tetikleyicileri (dar CHECK yerine; düşürülüp yeniden kurulabilir).

    ``operasyon.v2.akis.trigger_sql()`` bunu ``akis.DURUMLAR`` ile çağırır; test ikisinin
    aynı metni ürettiğini denetler. Liste değişirse göç gerekmez: tetikleyici yeniden kurulur.
    """
    d = ",".join(f"'{x}'" for x in durumlar)
    k = ",".join(f"'{x}'" for x in kaynaklar)
    kosul = f"NEW.durum NOT IN ({d}) OR NEW.kaynak NOT IN ({k})"
    govde = "BEGIN SELECT RAISE(ABORT, 'is_emri: gecersiz durum/kaynak'); END"
    return [
        "DROP TRIGGER IF EXISTS trg_is_deger_ekle",
        f"CREATE TRIGGER trg_is_deger_ekle BEFORE INSERT ON is_emri WHEN {kosul} {govde}",
        "DROP TRIGGER IF EXISTS trg_is_deger_guncelle",
        f"CREATE TRIGGER trg_is_deger_guncelle BEFORE UPDATE OF durum, kaynak ON is_emri WHEN {kosul} {govde}",
    ]


# ----------------------------------------------------------------------------- v5 indeks onarımı
V5 = """
CREATE INDEX IF NOT EXISTS ix_ziyaret_bina      ON ziyaret(bina_serial);
CREATE INDEX IF NOT EXISTS ix_ziyaret_kullanici ON ziyaret(kullanici_id, zaman);
"""

# ----------------------------------------------------------------------------- v6 görev kümesi (Ek-1)
# kullanici.rol = ANA görev (girişte açılan ekran); yetki kümedeki görevlerin BİRLEŞİMİdir.
# Silme ilişki sayımı bu tabloyu engel saymaz (CASCADE ile birlikte silinir).
V6 = """
CREATE TABLE IF NOT EXISTS kullanici_gorev (
    kullanici_id INTEGER NOT NULL REFERENCES kullanici(id) ON DELETE CASCADE,
    rol TEXT NOT NULL CHECK (rol IN ('satisci','operasyon','teknik','yonetici')),
    PRIMARY KEY (kullanici_id, rol)
);
"""
V6_TOHUM = "INSERT OR IGNORE INTO kullanici_gorev (kullanici_id, rol) SELECT id, rol FROM kullanici"

# ----------------------------------------------------------------------------- v7 askı aralıkları (Ek-3)
V7 = """
CREATE TABLE IF NOT EXISTS is_aski (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    is_no TEXT NOT NULL,
    baslama TEXT NOT NULL, bitis TEXT,
    neden TEXT, kaynak TEXT NOT NULL CHECK (kaynak IN ('boss','elle')),
    durdurur INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_is_aski_is ON is_aski(is_no);
"""

# ----------------------------------------------------------------------------- v8 ticket eki + PS26 (Ek-5, Ek-8)
TICKET_EK_SUTUNLAR = (
    ("onedesk_ekip", "TEXT"),    # Ek-5: ticket'ın açıldığı OneDesk ekibi (TEAM-TAS1BRS)
    ("kategori", "TEXT"),        # Ek-5: OneDesk başlığı (NETWORK / GPON / ...)
    ("tur", "TEXT"),             # Ek-8: NULL = ticket · 'guzergah' = PS26 GUZERGAH sayfasından
)

V8 = """
CREATE TABLE IF NOT EXISTS altyapi_bekleyen (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    musteri_no TEXT,
    kanal TEXT,
    baslangic TEXT,
    satici_ad TEXT,
    bolge TEXT,
    bina_serial TEXT,
    durum TEXT NOT NULL DEFAULT 'bekliyor',
    notu TEXT,
    aktarim_anahtari TEXT UNIQUE,
    olusturma TEXT NOT NULL,
    guncelleme TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_altyapi_bekleyen_bina ON altyapi_bekleyen(bina_serial);
CREATE TABLE IF NOT EXISTS ticket_ek (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL REFERENCES ticket(id),
    dosya_adi TEXT NOT NULL,
    boyut INTEGER,
    sha256 TEXT NOT NULL,
    olusturma TEXT NOT NULL,
    UNIQUE (ticket_id, sha256));
CREATE INDEX IF NOT EXISTS ix_ticket_ek_ticket ON ticket_ek(ticket_id);
"""

# ----------------------------------------------------------------------------- göç defteri
SEMA_GOC = """CREATE TABLE IF NOT EXISTS sema_goc (surum INTEGER PRIMARY KEY, ad TEXT NOT NULL, baslama TEXT NOT NULL,
                                     bitis TEXT NOT NULL, yedek_yolu TEXT, ozet TEXT)"""

# ----------------------------------------------------------------------------- ayar varsayılanları
# INSERT OR IGNORE: var olan (kullanıcının değiştirdiği) değerlere dokunulmaz.
AYAR_V4 = {
    "obek_surumu": "1",
    "musteri_tel": "kapali",
    "boss_task_url": "",
    "aktarim_esik": json.dumps({"kaybolan_oran": 0.25, "kaybolan_min": 50}),
    "rapor_bayat_dk": json.dumps({"amber": 30, "kirmizi": 60}),
    "mesai": "08:00-20:00",
    "dilimler": "08-10,10-12,12-14,14-16,16-18,18-20",
    "gun_baslangic": "08:30",
    "teknik_kapasite": "15",
    "filtre_istisnalari": json.dumps(["KURULUM TASKI UREMEMIS"]),
    "pii_saklama_gun": "30",
    "ham_saklama_gun": "7",
    "haftalik_satis_hedefi": "",
    "gorev_gozden_gecirildi": "0",
}

# Ek-2: unvan (içinde geçen metin, büyük/küçük ve Türkçe harf duyarsız) → görev kümesi.
# Sıra önemlidir: ilk eşleşen kural kazanır (özel olan önce). Ekip ekranından düzenlenir.
UNVAN_GOREV_ESLEME = [
    {"desen": "Teknik - Müdür", "gorevler": ["teknik", "yonetici"]},
    {"desen": "Teknik - Sorumlu", "gorevler": ["teknik"]},
    {"desen": "Yeni Müşteri - Takım Lideri", "gorevler": ["satisci", "yonetici"]},
    {"desen": "Yeni Müşteri - Sorumlu", "gorevler": ["satisci"]},
    {"desen": "Satış Destek - Takım Lideri", "gorevler": ["operasyon", "yonetici"]},
    {"desen": "Satış Destek - Sorumlu", "gorevler": ["operasyon"]},
    {"desen": "Satış Destek - Uzman", "gorevler": ["operasyon"]},
    {"desen": "Hizmet Danışmanı", "gorevler": ["operasyon"]},
    {"desen": "Satış-Müdür", "gorevler": ["yonetici"]},
    {"desen": "Genel Koordinatör", "gorevler": ["yonetici"]},
]

# Ek-5: ticket ekibi ve başlıkları (G10). Ek-12/7: varsayılan TEAM-TAS1BRS (BÇO Bursa); Yalova'nın bağlı olduğu
# BÇO belirsiz olduğu için TEAM-TAS1KOC (Kocaeli) da listede. Hepsi ayardır; Ekip/Ticket ekranından değişir.
TICKET_EKIPLERI = ["TEAM-TAS1BRS", "TEAM-TAS1KOC"]
TICKET_KATEGORILERI = [
    "NETWORK / FTTB / SW ARIZA",
    "NETWORK / GPON / SINYAL VAR / IP ALAMIYOR",
    "NETWORK / GPON / SINYAL YOK / MEVCUT BINA",
    "NETWORK / GPON / SINYAL YOK / YENI BINA",
    "NETWORK \\ IMALAT REVIZYON TALEBI",
    "NETWORK \\ GPON \\ ONT_SABITLEME_SORUNU",
    "NETWORK \\ HATALI NW READY BILDIRIMI",
    "NETWORK \\ BASK \\ SW YER DEGISIMI",
    "NETWORK \\ KABIN HASAR BILDIRIMI",
    "NETWORK \\ EK SWITCH VE SPLITER TALEBI",
    "NETWORK \\ SWITCH UPS - FAN SES PROBLEMI",
]

# Ek-12/7 (belgeler/TURKCELL_SUREC_BILGISI.md §D): OneDesk ticket'ında bulunması gereken bilgiler. Arayüz bunları
# "Yeni ticket" formunda denetim listesi olarak gösterir; sunucu zorlamaz (ticket OneDesk'te açılır).
TICKET_ZORUNLU_ALANLAR = [
    {"anahtar": "musteri_no", "etiket": "Müşteri no"},
    {"anahtar": "hizmet_id", "etiket": "Hizmet ID"},
    {"anahtar": "seri_no", "etiket": "Modem/ONT/STB seri no (değişimde eski ve yeni)"},
    {"anahtar": "port", "etiket": "SW ip/port ya da OLT ip/port"},
    {"anahtar": "tv_ip", "etiket": "100'lü IP (TV arızasında)"},
    {"anahtar": "kontroller", "etiket": "Yapılan kontroller"},
    {"anahtar": "aranma_saati", "etiket": "Müşterinin aranmak istediği saat (en geç 22:00)"},
    {"anahtar": "ekran_goruntusu", "etiket": "Tarih-saatli ekran görüntüsü (ek dosya)"},
]

AYAR_EK = {
    # Ek-2
    "unvan_gorev_esleme": json.dumps(UNVAN_GOREV_ESLEME, ensure_ascii=False),
    # Ek-3 + Ek-12/3: nedeninde bu sözcüklerden biri geçen askı BTK saatini durdurur (sade() biçiminde karşılaştırılır).
    # 'btk sureci' = BOSS'taki "BTK Süreci Kaynaklı" (Bilgi & Belge). TT kaynaklı BİLEREK yok (kullanıcı onayı bekler).
    # operasyon/v2/sema.py, kurallar.VARSAYILAN ve aski.VARSAYILAN_KURAL ile aynı (test_goc kilitler).
    "btk_durduran_aski": json.dumps(["abone", "bilgi belge", "btk sureci", "genel ariza"], ensure_ascii=False),
    "son24_askida_durur": "false",
    # Ek-5
    "ticket_ekipleri": json.dumps(TICKET_EKIPLERI, ensure_ascii=False),
    "ticket_varsayilan_ekip": TICKET_EKIPLERI[0],
    "ticket_kategorileri": json.dumps(TICKET_KATEGORILERI, ensure_ascii=False),
    # Ek-12/7: ticket şablonu, BÇO'da bekleme hatırlatması, kırmızı hat mail konusu
    "ticket_zorunlu_alanlar": json.dumps(TICKET_ZORUNLU_ALANLAR, ensure_ascii=False),
    "ticket_bco_hatirlatma_saat": "24",     # BÇO'da bu kadar saati geçen ticket → "TL'ye mail" hatırlatması
    "kirmizi_hat_konu_sablonu": "{task_no} / {task_adi} / Kırmızı Hat",
    # Ek-6: küçük sevinçler (kapatılabilir). Değer biçimi operasyon/v2/sema.py ile aynı: 'acik' | 'kapali'.
    "kutlamalar": "acik",
    # Ek-10: rapor klasör izleme (yoklama tabanlı, kapatılabilir). ``izlenen_klasorler`` BİLEREK yazılmaz:
    # yoksa sunucuyu çalıştıran kullanıcının İndirilenler + Masaüstü'dür (operasyon/v2 izleme modülü).
    "klasor_izleme": "acik",
    "izlenen_desenler": json.dumps(["TeknikTaskDetayRaporu*.xlsx"], ensure_ascii=False),
}


# ----------------------------------------------------------------------------- yardımcılar
def ifadeler(metin: str) -> list[str]:
    """SQL metnini tek tek ifadelere böler (tetikleyici gövdesindeki ';' ifadeyi bölmez).

    ``executescript`` kullanmamak için: her ifade çağıranın açtığı işlemin içinde koşar.
    """
    sonuc: list[str] = []
    tampon = ""
    for satir in metin.splitlines(keepends=True):
        tampon += satir
        if sqlite3.complete_statement(tampon):
            # Baştaki açıklama satırları atılır: ifade "CREATE ..." ile başlasın.
            satirlar = tampon.strip().splitlines()
            while satirlar and (not satirlar[0].strip() or satirlar[0].lstrip().startswith("--")):
                satirlar.pop(0)
            ifade = "\n".join(satirlar).strip()
            if ifade and ifade != ";":
                sonuc.append(ifade.rstrip(";").strip())
            tampon = ""
    if tampon.strip():
        raise ValueError(f"Tamamlanmamış SQL ifadesi: {tampon.strip()[:80]}")
    return sonuc


def ayar_varsayilanlari(conn: sqlite3.Connection, anahtarlar: dict[str, str]) -> int:
    """``INSERT OR IGNORE``: yalnız olmayan anahtarları yazar; eklenen sayısını döndürür."""
    eklenen = 0
    for anahtar, deger in anahtarlar.items():
        eklenen += conn.execute("INSERT OR IGNORE INTO ayar(anahtar, deger) VALUES(?,?)",
                                (anahtar, deger)).rowcount
    return eklenen


def tum_v2_ifadeleri() -> list[str]:
    """Taze kurulum için v3–v8'in bütün CREATE ifadeleri (sıra: göç sırası)."""
    return (ifadeler(V3) + ifadeler(V4) + is_emri_tetikleyicileri() + ifadeler(V5)
            + ifadeler(V6) + ifadeler(V7) + ifadeler(V8))
