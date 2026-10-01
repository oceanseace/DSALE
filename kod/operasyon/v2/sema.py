"""v2 tablolarının SQL'i — spec §1.6 (v3), §1.7 (v4), EK-3 (v7) birebir.

Göç çerçevesi (``saha/goc.py``, WP-A) bu listeleri kendi ``BEGIN IMMEDIATE … COMMIT``'i içinde tek tek
``execute`` eder (``executescript`` kullanılmaz: kendiliğinden commit eder). Hepsi ``IF NOT EXISTS``:
iki kez koşmak zararsızdır. Tetikleyici değer listeleri ``akis.trigger_sql()``'dan gelir.

``kur(conn)`` yalnız testler ve taze kurulum yardımcısıdır; canlı veritabanında göç dışında çağrılmaz.
"""
from __future__ import annotations

import json
import sqlite3

from . import akis

V3: list[str] = [
    """CREATE TABLE IF NOT EXISTS ilce (
    il_k TEXT NOT NULL, ilce_k TEXT NOT NULL, il TEXT NOT NULL, ad TEXT NOT NULL,
    lat REAL, lon REAL, PRIMARY KEY (il_k, ilce_k))""",
    """CREATE TABLE IF NOT EXISTS ilce_esad (
    il_k TEXT NOT NULL, esad_k TEXT NOT NULL, ilce_k TEXT NOT NULL, PRIMARY KEY (il_k, esad_k))""",
    """CREATE TABLE IF NOT EXISTS mahalle (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    il TEXT NOT NULL, ilce TEXT NOT NULL, ad TEXT NOT NULL,
    il_k TEXT NOT NULL, ilce_k TEXT NOT NULL, mahalle_k TEXT NOT NULL,
    lat REAL, lon REAL,
    kaynak TEXT NOT NULL,
    ekleyen_id INTEGER, ekleyen_ad TEXT,
    eklenme TEXT NOT NULL,
    UNIQUE (il_k, ilce_k, mahalle_k))""",
    """CREATE TABLE IF NOT EXISTS mahalle_esad (
    il_k TEXT NOT NULL, ilce_k TEXT NOT NULL, esad_k TEXT NOT NULL,
    mahalle_id INTEGER NOT NULL REFERENCES mahalle(id),
    ekleyen_id INTEGER, eklenme TEXT NOT NULL,
    PRIMARY KEY (il_k, ilce_k, esad_k))""",
    """CREATE TABLE IF NOT EXISTS obek (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ad TEXT NOT NULL,
    ad_k TEXT NOT NULL UNIQUE,
    renk INTEGER NOT NULL DEFAULT 0,
    sahip_id INTEGER REFERENCES kullanici(id),
    yedek_id INTEGER REFERENCES kullanici(id),
    aktif INTEGER NOT NULL DEFAULT 1,
    olusturma TEXT NOT NULL, guncelleme TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS obek_mahalle (
    il_k TEXT NOT NULL, ilce_k TEXT NOT NULL, mahalle_k TEXT NOT NULL,
    obek_id INTEGER NOT NULL REFERENCES obek(id),
    ref TEXT NOT NULL,
    ekleyen_id INTEGER, eklenme TEXT NOT NULL,
    PRIMARY KEY (il_k, ilce_k, mahalle_k))""",
    "CREATE INDEX IF NOT EXISTS ix_obek_mahalle_obek ON obek_mahalle(obek_id)",
    """CREATE TABLE IF NOT EXISTS obek_olay (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    zaman TEXT NOT NULL,
    kullanici_id INTEGER, kullanici_ad TEXT,
    tur TEXT NOT NULL,
    obek_id INTEGER,
    veri TEXT NOT NULL,
    surum INTEGER NOT NULL,
    toplu_id TEXT)""",
    """CREATE TRIGGER IF NOT EXISTS trg_obek_olay_degismez BEFORE UPDATE ON obek_olay
BEGIN SELECT RAISE(ABORT, 'obek_olay degistirilemez'); END""",
    """CREATE TRIGGER IF NOT EXISTS trg_obek_olay_silinmez BEFORE DELETE ON obek_olay
BEGIN SELECT RAISE(ABORT, 'obek_olay silinemez'); END""",
]

V4: list[str] = [
    """CREATE TABLE IF NOT EXISTS ie_aktarim (
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
    hata TEXT)""",
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_aktarim_sha ON ie_aktarim(dosya_sha256) WHERE durum = 'uygulandi'",
    "CREATE INDEX IF NOT EXISTS ix_aktarim_zaman ON ie_aktarim(baslama)",
    """CREATE TABLE IF NOT EXISTS is_emri (
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
    guncelleme TEXT NOT NULL)""",
    "CREATE INDEX IF NOT EXISTS ix_is_durum     ON is_emri(durum, son24)",
    "CREATE INDEX IF NOT EXISTS ix_is_obek      ON is_emri(obek_id, durum)",
    "CREATE INDEX IF NOT EXISTS ix_is_obek_elle ON is_emri(obek_elle_id)",
    "CREATE INDEX IF NOT EXISTS ix_is_atanan    ON is_emri(atanan_id, durum)",
    "CREATE INDEX IF NOT EXISTS ix_is_mahalle   ON is_emri(il_k, ilce_k, mahalle_k)",
    "CREATE INDEX IF NOT EXISTS ix_is_bina      ON is_emri(bina_serial)",
    "CREATE INDEX IF NOT EXISTS ix_is_musteri   ON is_emri(musteri_ozet, task_adi)",
    "CREATE INDEX IF NOT EXISTS ix_is_ticket    ON is_emri(ticket_id)",
    *akis.trigger_sql(),
    """CREATE TABLE IF NOT EXISTS is_emri_olay (
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
    istemci_id TEXT)""",
    "CREATE INDEX IF NOT EXISTS ix_olay_is ON is_emri_olay(is_no, id)",
    "CREATE INDEX IF NOT EXISTS ix_olay_toplu ON is_emri_olay(toplu_id) WHERE toplu_id IS NOT NULL",
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_olay_istemci ON is_emri_olay(kullanici_id, istemci_id) WHERE istemci_id IS NOT NULL",
    """CREATE TRIGGER IF NOT EXISTS trg_is_olay_degismez BEFORE UPDATE ON is_emri_olay
BEGIN SELECT RAISE(ABORT, 'is_emri_olay degistirilemez'); END""",
    """CREATE TRIGGER IF NOT EXISTS trg_is_olay_silinmez BEFORE DELETE ON is_emri_olay
BEGIN SELECT RAISE(ABORT, 'is_emri_olay silinemez'); END""",
    """CREATE TABLE IF NOT EXISTS erisim_kaydi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    zaman TEXT NOT NULL, gun TEXT NOT NULL,
    kullanici_id INTEGER NOT NULL, kullanici_ad TEXT,
    eylem TEXT NOT NULL,
    is_no TEXT, adet INTEGER, ip TEXT)""",
    "CREATE INDEX IF NOT EXISTS ix_erisim ON erisim_kaydi(kullanici_id, zaman)",
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_erisim_gun ON erisim_kaydi(gun, kullanici_id, eylem, is_no) WHERE is_no IS NOT NULL",
    """CREATE TRIGGER IF NOT EXISTS trg_erisim_degismez BEFORE UPDATE ON erisim_kaydi
BEGIN SELECT RAISE(ABORT, 'erisim_kaydi degistirilemez'); END""",
    """CREATE TABLE IF NOT EXISTS takip_anlik (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    zaman TEXT NOT NULL, aktarim_id INTEGER,
    acik INTEGER, asan24 INTEGER, btk_asan48 INTEGER, atanmamis INTEGER, altyapi INTEGER)""",
    """CREATE TABLE IF NOT EXISTS yonetim_kaydi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    zaman TEXT NOT NULL,
    kullanici_id INTEGER, kullanici_ad TEXT,
    eylem TEXT NOT NULL,
    hedef TEXT,
    ozet TEXT)""",
    """CREATE TRIGGER IF NOT EXISTS trg_yonetim_kaydi_degismez BEFORE UPDATE ON yonetim_kaydi
BEGIN SELECT RAISE(ABORT, 'yonetim_kaydi degistirilemez'); END""",
    """CREATE TRIGGER IF NOT EXISTS trg_yonetim_kaydi_silinmez BEFORE DELETE ON yonetim_kaydi
BEGIN SELECT RAISE(ABORT, 'yonetim_kaydi silinemez'); END""",
]

# EK-3 · v7 — askı aralıkları (BTK saati abone kaynaklı askıda durur).
V7: list[str] = [
    """CREATE TABLE IF NOT EXISTS is_aski (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    is_no TEXT NOT NULL,
    baslama TEXT NOT NULL, bitis TEXT,
    neden TEXT, kaynak TEXT NOT NULL CHECK (kaynak IN ('boss','elle')),
    durdurur INTEGER NOT NULL DEFAULT 0)""",
    "CREATE INDEX IF NOT EXISTS ix_is_aski_is ON is_aski(is_no)",
]

# §1.10 + ek anahtarlar (EK-3, EK-6, EK-10). v4'te INSERT OR IGNORE; kullanıcı değiştirirse ezilmez.
# izlenen_klasorler BİLEREK yok: yoksa sunucuyu çalıştıran kullanıcının İndirilenler + Masaüstü'dür
# (izleme.varsayilan_klasorler) — makine değişince yol kendiliğinden doğru kalsın.
AYAR_VARSAYILAN: dict[str, str] = {
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
    # EK-3 + EK-12.3 (kurallar.VARSAYILAN ile aynı; TT kaynaklı teyit bekliyor → yok)
    "btk_durduran_aski": json.dumps(["abone", "bilgi belge", "btk sureci", "genel ariza"]),
    "son24_askida_durur": "false",
    # EK-6
    "kutlamalar": "acik",
    # EK-10
    "klasor_izleme": "acik",
    "izlenen_desenler": json.dumps(["TeknikTaskDetayRaporu*.xlsx"]),
}
# ilk_aktarim: ilk uygulanan aktarımda yazılır (15 dk ölçüsünün başlangıcı).


def ayar_varsayilanlari(conn: sqlite3.Connection) -> int:
    n = 0
    for k, v in AYAR_VARSAYILAN.items():
        n += conn.execute("INSERT OR IGNORE INTO ayar(anahtar, deger) VALUES (?, ?)", (k, v)).rowcount
    return n


def ifadeler() -> list[str]:
    """Kurulacak bütün ifadeler: göçün kendi listesi (``saha.sema_v2``, WP-A) varsa o; yoksa bu dosyanınki."""
    try:
        from saha import sema_v2
        return list(sema_v2.tum_v2_ifadeleri())
    except (ImportError, AttributeError):
        return [*V3, *V4, *V7]


def kur(conn: sqlite3.Connection) -> None:
    """Testler ve taze kurulum: v3 + v4 + v7 tablolarını ve ayar varsayılanlarını kurar (tek işlem)."""
    eski = conn.isolation_level
    conn.isolation_level = None
    try:
        conn.execute("BEGIN IMMEDIATE")
        for sql in ifadeler():
            conn.execute(sql)
        ayar_varsayilanlari(conn)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.isolation_level = eski
