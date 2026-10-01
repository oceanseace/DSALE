"""SQLite bağlantısı ve şema.

Tek dosyalık veritabanı (``saha/saha.db``), WAL kipinde: sahadan gelen yazmalar
yöneticinin okumalarını kilitlemez. Sütun adı ``not`` hem SQL hem Python'da
ayrılmış sözcük olduğu için her yerde ``notu`` kullanılır.

Şema sürümü (``PRAGMA user_version``) ``saha/goc.py`` ile yönetilir; göç YALNIZ sunucu
açılışında (``saha/sunucu.py``) ve ``python -m saha.goc`` ile koşar. Komut satırı araçları
``semayi_kur`` üzerinden yalnız sürümü denetler (spec §1.2).
"""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

from . import ayarlar, sema_v2

# Ziyaret tablosunun tanımı: hem taze şemada hem eski veritabanının güvenli yeniden
# kurulmasında (``_ziyaret_yeniden_kur``) aynı metin kullanılır.
_ZIYARET_TANIMI = """CREATE TABLE {kosul}{ad} (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    offline_id      TEXT NOT NULL,                -- telefonun ürettiği kimlik: idempotanlık anahtarı
    bina_serial     TEXT NOT NULL REFERENCES bina(bina_serial),
    kullanici_id    INTEGER NOT NULL REFERENCES kullanici(id),
    zaman           TEXT NOT NULL,                -- sahada olup bittiği an
    sonuc           TEXT NOT NULL,
    satis_adedi     INTEGER NOT NULL DEFAULT 0,
    konusulan_daire INTEGER NOT NULL DEFAULT 0,
    notu            TEXT,
    lat             REAL,
    lon             REAL,
    cihaz           TEXT,
    kayit_zamani    TEXT NOT NULL,                -- sunucuya düştüğü an
    -- Yanlış işlenen ziyaret silinmez, iptal edilir: sayaçlar geri alınır ama
    -- sahada ne olduğunun izi kalır. Bütün toplamlar iptal=0 ile okunur.
    iptal           INTEGER NOT NULL DEFAULT 0,
    iptal_eden_id   INTEGER REFERENCES kullanici(id),
    iptal_zamani    TEXT,
    -- Idempotans anahtarı KULLANICI BAZINDA tekil: iki telefonun aynı kimliği
    -- üretmesi halinde gerçek bir ziyaret sessizce yutulmasın ve yanıt başka
    -- satışçının binasını sızdırmasın.
    UNIQUE (kullanici_id, offline_id)
)"""
ZIYARET_INDEKSLERI = (
    "CREATE INDEX IF NOT EXISTS ix_ziyaret_bina     ON ziyaret(bina_serial)",
    "CREATE INDEX IF NOT EXISTS ix_ziyaret_kullanici ON ziyaret(kullanici_id, zaman)",
    "CREATE INDEX IF NOT EXISTS ix_ziyaret_gun      ON ziyaret(zaman)",
)

SEMA = sema_v2.KULLANICI_TAZE + """
CREATE TABLE IF NOT EXISTS bina (
    bina_serial TEXT PRIMARY KEY,
    ad          TEXT,
    site_adi    TEXT,
    mahalle     TEXT,
    ilce        TEXT,
    il          TEXT,
    cadde       TEXT,
    sokak       TEXT,
    kapi_no     TEXT,
    lat         REAL NOT NULL,
    lon         REAL NOT NULL,
    kat         INTEGER,
    daire       INTEGER,
    res_hp      INTEGER NOT NULL DEFAULT 0,
    aktif_res   INTEGER NOT NULL DEFAULT 0,
    firsat      INTEGER NOT NULL DEFAULT 0,
    sales_ready TEXT,
    bolge       INTEGER,
    obek        TEXT,
    site_grup   TEXT,
    -- Kimlikler ve teknik bilgiler (yönetici haritasındaki "Ayrıntılar" ve
    -- BOSS/Fox iş emirlerini binaya bağlamak için; BOSS "Lokasyon" = location_id)
    location_id      TEXT,
    tellcordia_id    TEXT,
    uavt_bina_kodu   TEXT,
    blok_adi         TEXT,
    bina_turu        TEXT,
    toplam_hp        INTEGER,
    soho_hp          INTEGER,
    altyapi          TEXT,
    teknoloji        TEXT,
    protokol_segment TEXT,
    crm_site_adi     TEXT,  -- data.xlsx 'Site Adı' (ticket metninde bu yazılır)
    -- Faz 2 (veri kalitesi, tur raporu). Hepsi sonradan eklenebilir sütunlar.
    kalite           TEXT,  -- JSON: [{kural, mesaj, seviye, duzeltme?}] (dsale/kalite.py)
    kalite_kaynak    TEXT,  -- JSON: kuralların kanıtı (OneMap LAT/LON, ham kimlikler ...)
    pasif            INTEGER NOT NULL DEFAULT 0,   -- son tur raporunda yok: listeye girmez, geçmişi durur
    pasif_tarih      TEXT,
    tur_tarihi       TEXT,  -- HP/abone en son hangi tur raporundan güncellendi
    ekleme_kaynagi   TEXT   -- NULL = ilk kurulum · 'tur' = tur raporuyla gelen yeni bina
);
CREATE INDEX IF NOT EXISTS ix_bina_bolge   ON bina(bolge);
CREATE INDEX IF NOT EXISTS ix_bina_location ON bina(location_id);
CREATE INDEX IF NOT EXISTS ix_bina_mahalle ON bina(mahalle);
CREATE INDEX IF NOT EXISTS ix_bina_grup    ON bina(site_grup);

CREATE TABLE IF NOT EXISTS bina_durum (
    bina_serial      TEXT PRIMARY KEY REFERENCES bina(bina_serial),
    durum            TEXT NOT NULL DEFAULT 'bekliyor',
    son_ziyaret      TEXT,
    son_kullanici_id INTEGER REFERENCES kullanici(id),
    son_sonuc        TEXT,
    tekrar_tarih     TEXT,
    toplam_satis     INTEGER NOT NULL DEFAULT 0,
    ziyaret_sayisi   INTEGER NOT NULL DEFAULT 0,
    notu             TEXT
);
CREATE INDEX IF NOT EXISTS ix_durum_durum ON bina_durum(durum);

__ZIYARET__;
CREATE INDEX IF NOT EXISTS ix_ziyaret_bina     ON ziyaret(bina_serial);
CREATE INDEX IF NOT EXISTS ix_ziyaret_kullanici ON ziyaret(kullanici_id, zaman);
CREATE INDEX IF NOT EXISTS ix_ziyaret_gun      ON ziyaret(zaman);

CREATE TABLE IF NOT EXISTS gorev (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    kullanici_id INTEGER NOT NULL REFERENCES kullanici(id),
    tarih        TEXT NOT NULL,                   -- YYYY-AA-GG
    durum        TEXT NOT NULL DEFAULT 'acik' CHECK (durum IN ('acik','tamam')),
    olusturan_id INTEGER REFERENCES kullanici(id),
    kaynak       TEXT NOT NULL CHECK (kaynak IN ('algoritma','yonetici')),
    notu         TEXT,
    olusturma    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_gorev_gun ON gorev(kullanici_id, tarih);

CREATE TABLE IF NOT EXISTS gorev_bina (
    gorev_id    INTEGER NOT NULL REFERENCES gorev(id) ON DELETE CASCADE,
    bina_serial TEXT    NOT NULL REFERENCES bina(bina_serial),
    sira        INTEGER NOT NULL,
    durum       TEXT    NOT NULL DEFAULT 'bekliyor'
                CHECK (durum IN ('bekliyor','tamam','atlandi')),
    mesafe_m    INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (gorev_id, bina_serial)
);
CREATE INDEX IF NOT EXISTS ix_gorev_bina_serial ON gorev_bina(bina_serial);

CREATE TABLE IF NOT EXISTS ayar (
    anahtar TEXT PRIMARY KEY,
    deger   TEXT
);

-- Hatalı giriş denemeleri: 15 dakikada 5 deneme kuralı buradan okunur.
CREATE TABLE IF NOT EXISTS giris_denemesi (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    telefon  TEXT NOT NULL,
    zaman    TEXT NOT NULL,
    basarili INTEGER NOT NULL DEFAULT 0,
    ip       TEXT,                                -- IP başına sınır için
    tur      TEXT NOT NULL DEFAULT 'giris'        -- 'giris' | 'yoklama'
);
CREATE INDEX IF NOT EXISTS ix_deneme    ON giris_denemesi(telefon, zaman);
CREATE INDEX IF NOT EXISTS ix_deneme_ip ON giris_denemesi(ip, zaman);
"""

# Faz 2 tabloları. Ayrı tutulur ki eski bir veritabanında da ``gocler`` bunları
# kurabilsin (sunucu açılırken yalnız ``gocler`` çalışır). Hepsi yalnız EKLER:
# hiçbir eski tabloya, satıra dokunmaz.
SEMA_FAZ2 = """
-- Bölge planlarının geçmişi. Her uygulama yeni bir satırdır; geri almak bir
-- önceki satırın atamasını geri yazmaktır. Ziyaret geçmişine DOKUNULMAZ.
CREATE TABLE IF NOT EXISTS bolge_plani (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    n             INTEGER NOT NULL,
    olcu          TEXT    NOT NULL DEFAULT 'res_hp',
    kaynak        TEXT    NOT NULL,       -- 'baslangic' | 'hazir' | 'onbellek' | 'hesap' | 'geri_al'
    plan_ref      TEXT,
    imza          TEXT,                   -- atamanın özeti: önizlenen ile uygulanan aynı mı
    atama         TEXT    NOT NULL,       -- JSON {bina_serial: bolge}
    bolgeler      TEXT,                   -- JSON [{bolge, ad, kisa_ad, renk, poligon?}]
    kullanicilar  TEXT,                   -- JSON: uygulamadan ÖNCEKİ satışçı bölgeleri (geri alma için)
    ozet          TEXT,                   -- JSON: fark özeti (el değiştiren bina/ziyaret)
    olusturan_id  INTEGER REFERENCES kullanici(id),
    zaman         TEXT    NOT NULL,
    aktif         INTEGER NOT NULL DEFAULT 0,
    geri_alindi   INTEGER NOT NULL DEFAULT 0,
    onceki_id     INTEGER,                -- bu plan uygulanırken etkin olan plan (geri alınca ona dönülür)
    notu          TEXT
);

-- Tur raporu yüklemeleri: önce önizleme, sonra (isteğe bağlı) uygulama.
CREATE TABLE IF NOT EXISTS tur_raporu (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    dosya         TEXT    NOT NULL,       -- data/raw/gelen/tur_<zaman>.xlsx
    ozet_imza     TEXT,                   -- dosyanın sha256'sı
    yukleme       TEXT    NOT NULL,
    yukleyen_id   INTEGER REFERENCES kullanici(id),
    durum         TEXT    NOT NULL DEFAULT 'onizleme',   -- 'onizleme' | 'uygulandi' | 'eskidi'
    ozet          TEXT,                   -- JSON: fark özeti
    uygulama      TEXT,
    uygulayan_id  INTEGER REFERENCES kullanici(id)
);

-- Tur raporunda olup bizde olmayan binalar: koordinatı gelene kadar burada bekler.
CREATE TABLE IF NOT EXISTS bina_bekleyen (
    bina_serial   TEXT PRIMARY KEY,
    tellcordia_id TEXT,
    location_id   TEXT,
    veri          TEXT NOT NULL,          -- JSON: rapordaki satır (ad, ilçe, HP, abone ...)
    durum         TEXT NOT NULL DEFAULT 'konum_bekliyor',  -- 'konum_bekliyor' | 'eklendi' | 'rapordan_cikti'
    tur_id        INTEGER REFERENCES tur_raporu(id),
    eklenme       TEXT NOT NULL,
    guncelleme    TEXT
);

-- Bina künyesindeki her değişikliğin izi (tur raporu, kalite düzeltmesi).
CREATE TABLE IF NOT EXISTS bina_degisim (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    bina_serial  TEXT NOT NULL,
    kaynak       TEXT NOT NULL,           -- 'tur:<id>' | 'onemap' | 'plan:<id>'
    alan         TEXT NOT NULL,
    eski         TEXT,
    yeni         TEXT,
    zaman        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_degisim_bina ON bina_degisim(bina_serial);

-- Sonradan eklenen binaların taban poligonu (ilk kurulumdakiler
-- data/master/bina_geometri.json dosyasında).
CREATE TABLE IF NOT EXISTS bina_geometri_ek (
    bina_serial  TEXT PRIMARY KEY,
    halka        TEXT NOT NULL,           -- JSON [[lon,lat], ...]
    zaman        TEXT NOT NULL
);

-- Ticket defteri (OneDesk). Excel'deki TICKET sayfasının yerine geçer.
CREATE TABLE IF NOT EXISTS ticket (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_no        TEXT,                -- OneDesk numarası; açılana kadar boş olabilir
    acilis           TEXT,                -- YYYY-AA-GG
    konu             TEXT NOT NULL,       -- SİNYAL | EK SP | GÜZERGAH | ALTYAPI | DİĞER
    durum            TEXT NOT NULL DEFAULT 'AÇIK',  -- AÇIK | ÇÖZÜLDÜ | HATA | KAPATILDI | İPTAL | TRANSFER
    bina_serial      TEXT,
    location_id      TEXT,
    site             TEXT,
    musteri          TEXT,                -- müşteri numaraları (serbest metin)
    kanal            TEXT,                -- DEHA | GLOBAL | ARIZA | TOPTAN ...
    detay            TEXT,
    metin            TEXT,                -- OneDesk'e yapıştırılan ticket metni
    olusturan_id     INTEGER REFERENCES kullanici(id),
    olusturma        TEXT NOT NULL,
    guncelleme       TEXT NOT NULL,
    kapanis          TEXT,
    kaynak           TEXT NOT NULL DEFAULT 'uygulama',   -- 'uygulama' | 'excel'
    aktarim_anahtari TEXT UNIQUE,         -- Excel'den aktarımda tekrar yazmayı önler
    -- v8 (Ek-5, Ek-8): eski veritabanında ALTER ADD ile aynı sırayla eklenir
    onedesk_ekip     TEXT,                -- ticket'ın açıldığı OneDesk ekibi (TEAM-TAS1BRS)
    kategori         TEXT,                -- OneDesk başlığı (NETWORK / GPON / ...)
    tur              TEXT                 -- NULL = ticket · 'guzergah' = PS26 GUZERGAH sayfası
);
CREATE INDEX IF NOT EXISTS ix_ticket_bina  ON ticket(bina_serial);
CREATE INDEX IF NOT EXISTS ix_ticket_durum ON ticket(durum);
CREATE INDEX IF NOT EXISTS ix_ticket_loc   ON ticket(location_id);

CREATE TABLE IF NOT EXISTS ticket_gecmis (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id    INTEGER NOT NULL REFERENCES ticket(id),
    zaman        TEXT NOT NULL,
    kullanici_id INTEGER REFERENCES kullanici(id),
    eski_durum   TEXT,
    yeni_durum   TEXT,
    notu         TEXT,
    alanlar      TEXT                     -- JSON {alan: [eski, yeni]}
);
CREATE INDEX IF NOT EXISTS ix_ticket_gecmis ON ticket_gecmis(ticket_id);
"""

SEMA = SEMA.replace("__ZIYARET__", _ZIYARET_TANIMI.format(kosul="IF NOT EXISTS ", ad="ziyaret")) + SEMA_FAZ2
FAZ2_TABLOLARI = ("bolge_plani", "tur_raporu", "bina_bekleyen", "bina_degisim",
                  "bina_geometri_ek", "ticket", "ticket_gecmis")


def db_yolu() -> Path:
    """Veritabanı dosyasının yolu. ``SAHA_DB`` ortam değişkeni her çağrıda okunur."""
    ortam = os.environ.get("SAHA_DB")
    return Path(ortam) if ortam else ayarlar.DB_YOLU


def baglan(yol: Path | None = None) -> sqlite3.Connection:
    """Ayarları yapılmış bir bağlantı döndürür (WAL, yabancı anahtar, satır sözlüğü)."""
    hedef = Path(yol) if yol else db_yolu()
    hedef.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(hedef, timeout=15.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # WAL kalıcıdır (dosyaya yazılır): zaten WAL ise yeniden kurmak her istekte boşuna kilit yoklar.
    if str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower() != "wal":
        conn.execute("PRAGMA journal_mode=WAL")
    # FULL: "Kaydedildi" dedikten sonra elektrik kesilse bile kayıt yerinde kalır.
    # Günde birkaç yüz ziyaret yazan bir sistemde commit başına bir fsync'in
    # maliyeti ölçülemez; karşılığı "asla veri kaybetmez" sözünün tutulmasıdır.
    conn.execute("PRAGMA synchronous=FULL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=15000")
    return conn


def _sutunlar(conn: sqlite3.Connection, tablo: str) -> set[str]:
    try:
        return {s[1] for s in conn.execute(f"PRAGMA table_info({tablo})").fetchall()}
    except sqlite3.Error:
        return set()


BINA_EK_SUTUNLAR = (
    ("location_id", "TEXT"), ("tellcordia_id", "TEXT"), ("uavt_bina_kodu", "TEXT"),
    ("blok_adi", "TEXT"), ("bina_turu", "TEXT"), ("toplam_hp", "INTEGER"), ("soho_hp", "INTEGER"),
    ("altyapi", "TEXT"), ("teknoloji", "TEXT"), ("protokol_segment", "TEXT"), ("crm_site_adi", "TEXT"),
    # Faz 2
    ("kalite", "TEXT"), ("kalite_kaynak", "TEXT"), ("pasif", "INTEGER NOT NULL DEFAULT 0"),
    ("pasif_tarih", "TEXT"), ("tur_tarihi", "TEXT"), ("ekleme_kaynagi", "TEXT"),
)


def tablo_var(conn: sqlite3.Connection, ad: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (ad,)).fetchone() is not None


def _sema_parcalari() -> tuple[dict[str, str], dict[str, list[str]]]:
    """SEMA'yı tablo tanımlarına ve tablo başına indekslerine ayırır (eksik tabloyu kurmak için)."""
    tablolar: dict[str, str] = {}
    indeksler: dict[str, list[str]] = {}
    for ifade in sema_v2.ifadeler(SEMA):
        kelimeler = ifade.split()
        if ifade.upper().startswith("CREATE TABLE"):
            # CREATE TABLE IF NOT EXISTS <ad> (
            tablolar[kelimeler[5]] = ifade
        elif ifade.upper().startswith("CREATE INDEX"):
            # CREATE INDEX IF NOT EXISTS ix ON <tablo>(...)
            tablo = ifade.split(" ON ", 1)[1].split("(", 1)[0].strip()
            indeksler.setdefault(tablo, []).append(ifade)
    return tablolar, indeksler


def _ziyaret_yeniden_kur(conn: sqlite3.Connection) -> None:
    """``offline_id`` tek başına UNIQUE olan eski ziyaret tablosunu güvenli desenle yeniden kurar.

    Spec §1.9: ÖNCE yeni tablo kurulur, SONRA eskisi düşürülür (eskiyi RENAME etmek başka
    tabloların REFERENCES metnini bozar); tek ``BEGIN IMMEDIATE`` işlemi, üç indeks yeniden
    kurulur, satır sayısı ve FK denetlenir. Yalnız çok eski veritabanlarında koşar.
    """
    if conn.in_transaction:
        conn.commit()
    conn.execute("PRAGMA foreign_keys=OFF")          # işlem DIŞINDA (içinde etkisiz)
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            once = conn.execute("SELECT COUNT(*) FROM ziyaret").fetchone()[0]
            conn.execute("DROP TABLE IF EXISTS ziyaret_yeni")
            conn.execute(_ZIYARET_TANIMI.format(kosul="", ad="ziyaret_yeni"))
            ortak = sorted(_sutunlar(conn, "ziyaret_yeni") & _sutunlar(conn, "ziyaret"))
            alanlar = ", ".join(ortak)
            conn.execute(f"INSERT INTO ziyaret_yeni ({alanlar}) SELECT {alanlar} FROM ziyaret")
            conn.execute("DROP TABLE ziyaret")
            conn.execute("ALTER TABLE ziyaret_yeni RENAME TO ziyaret")
            for ifade in ZIYARET_INDEKSLERI:
                conn.execute(ifade)
            sonra = conn.execute("SELECT COUNT(*) FROM ziyaret").fetchone()[0]
            if sonra != once:
                raise sqlite3.IntegrityError(
                    f"ziyaret yeniden kurulurken satır sayısı değişti ({once} → {sonra})")
            if conn.execute("PRAGMA foreign_key_check(ziyaret)").fetchall():
                raise sqlite3.IntegrityError("ziyaret yeniden kurulurken yabancı anahtar hatası")
            conn.execute("COMMIT")
        except BaseException:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
    finally:
        conn.execute("PRAGMA foreign_keys=ON")


def _goc_plani(conn: sqlite3.Connection) -> list[tuple[str, object]]:
    """``gocler``'in yapacağı yalnız-ekleyen adımlar: [(ad, uygula)]. Tespit YAN ETKİSİZDİR."""
    plan: list[tuple[str, object]] = []

    def alter(tablo: str, sutun: str, tanim: str):
        return lambda: conn.execute(f"ALTER TABLE {tablo} ADD COLUMN {sutun} {tanim}")

    # Sıra önemli: yeni sütunlar ÖNCE eklenir; ziyaret yeniden kurulurken kesişen sütunlar taşınır.
    deneme = _sutunlar(conn, "giris_denemesi")
    if deneme:
        if "ip" not in deneme:
            plan.append(("giris_denemesi.ip", alter("giris_denemesi", "ip", "TEXT")))
        if "tur" not in deneme:
            plan.append(("giris_denemesi.tur",
                         alter("giris_denemesi", "tur", "TEXT NOT NULL DEFAULT 'giris'")))

    bina = _sutunlar(conn, "bina")
    if bina:
        for sutun, tanim in BINA_EK_SUTUNLAR:
            if sutun not in bina:
                plan.append((f"bina.{sutun}", alter("bina", sutun, tanim)))
        if not conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='index' AND name='ix_bina_location'").fetchone():
            plan.append(("indeks:ix_bina_location",
                         lambda: conn.execute("CREATE INDEX IF NOT EXISTS ix_bina_location ON bina(location_id)")))

    ziyaret = _sutunlar(conn, "ziyaret")
    if ziyaret:
        for sutun, tanim in (
            ("iptal", "INTEGER NOT NULL DEFAULT 0"),
            ("iptal_eden_id", "INTEGER"),
            ("iptal_zamani", "TEXT"),
        ):
            if sutun not in ziyaret:
                plan.append((f"ziyaret.{sutun}", alter("ziyaret", sutun, tanim)))
        # offline_id tek başına UNIQUE ise tablo (kullanici_id, offline_id) anahtarıyla yeniden kurulur.
        tanim = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='ziyaret'"
        ).fetchone()
        if tanim and "UNIQUE (kullanici_id, offline_id)" not in (tanim[0] or ""):
            plan.append(("ziyaret.UNIQUE(kullanici_id, offline_id)", lambda: _ziyaret_yeniden_kur(conn)))

    # Eksik temel ve faz 2 tabloları: yalnız ana şema kuruluysa (boş dosyayı taze kurulum kurar).
    # ``kullanici`` burada kurulmaz: onun tanımı v1 göçünün işidir.
    if bina:
        mevcut = {s[0] for s in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        tablolar, indeksler = _sema_parcalari()
        for ad, ifade in tablolar.items():
            if ad == "kullanici" or ad in mevcut:
                continue

            def kur(ifade=ifade, ad=ad):
                conn.execute(ifade)
                for ix in indeksler.get(ad, []):
                    conn.execute(ix)

            plan.append((f"tablo:{ad}", kur))
    return plan


def bekleyen_gocler(conn: sqlite3.Connection) -> list[str]:
    """``gocler``'in yapacağı adımların adları — veritabanına HİÇ dokunmadan (spec §1.2-3)."""
    return [ad for ad, _ in _goc_plani(conn)]


def gocler(conn: sqlite3.Connection) -> list[str]:
    """Eski bir veritabanını yalnız EKLEYEREK faz 2 şemasına taşır. Her adım kendi başına güvenlidir.

    v2 sürüm adımları (rol CHECK'i, iş emri tabloları ...) ``saha/goc.py``'dadır ve yalnız
    sunucu açılışında, doğrulanmış yedekten SONRA koşar; bu işlev de oradan çağrılır.
    """
    yapilan: list[str] = []
    for ad, uygula in _goc_plani(conn):
        uygula()
        yapilan.append(ad)
    if yapilan and conn.in_transaction:
        conn.commit()
    return yapilan


def semayi_kur(conn: sqlite3.Connection) -> None:
    """Komut satırı araçlarının şema kapısı (spec §1.2).

    * Boş dosya (``kullanici`` tablosu yok): SEMA + v2 şeması kurulur, ``user_version = HEDEF``,
      ilçe/mahalle/öbek tohumu yapılır.
    * Dolu dosya: YALNIZ sürüm denetlenir. Eskiyse ya da yeniyse ``goc.SurumUyumsuz`` (Türkçe)
      fırlar; göç burada ASLA yapılmaz — yalnız sunucu açılışında, yedekten sonra.
    """
    from . import goc

    if not tablo_var(conn, "kullanici"):
        goc.taze_kur(conn)
        return
    goc.surum_dogrula(conn)


def yonetim_kaydi(conn: sqlite3.Connection, k: dict | None, eylem: str, hedef: str | None = None,
                  ozet: dict | None = None) -> None:
    """Ekip ve veri yönetimi izi (spec §1.11-5). İşlemi çağıran commit eder.

    ``ozet``'e kişisel veri DEĞERİ yazılmaz (telefon, PIN, davet kodu yok). Göç öncesi bir
    veritabanında tablo yoksa sessizce atlanır (eski uçlar çalışmaya devam etsin).
    """
    try:
        conn.execute(
            "INSERT INTO yonetim_kaydi (zaman, kullanici_id, kullanici_ad, eylem, hedef, ozet) "
            "VALUES (?,?,?,?,?,?)",
            (ayarlar.zaman_metni(), (k or {}).get("id"), (k or {}).get("ad"), eylem, hedef,
             json.dumps(ozet, ensure_ascii=False, separators=(",", ":")) if ozet is not None else None))
    except sqlite3.OperationalError as exc:
        if "no such table" not in str(exc):
            raise


def ayar_oku(conn: sqlite3.Connection, anahtar: str, varsayilan: str | None = None) -> str | None:
    satir = conn.execute("SELECT deger FROM ayar WHERE anahtar=?", (anahtar,)).fetchone()
    return satir["deger"] if satir else varsayilan


def ayar_yaz(conn: sqlite3.Connection, anahtar: str, deger: str) -> None:
    conn.execute(
        "INSERT INTO ayar(anahtar,deger) VALUES(?,?) "
        "ON CONFLICT(anahtar) DO UPDATE SET deger=excluded.deger",
        (anahtar, deger),
    )


def sozluk(satir: sqlite3.Row | None) -> dict | None:
    return dict(satir) if satir is not None else None


def sozlukler(satirlar) -> list[dict]:
    return [dict(s) for s in satirlar]


VERI_SURUMU = "veri_surumu"


def surum_oku(conn: sqlite3.Connection) -> int:
    """Bina durumlarının kaçıncı sürümde olduğu.

    Harita gibi pahalı yanıtları önbelleğe almak için: sayı değişmediyse veri
    de değişmemiştir. ``ayar`` tablosunda durduğu için ayrı süreçlerden yapılan
    değişiklikler (ör. gösterim verisinin silinmesi) de görülür.
    """
    try:
        return int(ayar_oku(conn, VERI_SURUMU, "0") or 0)
    except (TypeError, ValueError):
        return 0


def surumu_arttir(conn: sqlite3.Connection) -> None:
    """Bina durumunu değiştiren her yazmada çağrılır (aynı işlem içinde)."""
    conn.execute(
        "INSERT INTO ayar(anahtar,deger) VALUES(?,'1') "
        "ON CONFLICT(anahtar) DO UPDATE SET deger = CAST(CAST(deger AS INTEGER) + 1 AS TEXT)",
        (VERI_SURUMU,),
    )


# Binanın KÜNYESİ (bölge, konum, HP, ad) değiştiğinde artar. Harita yanıtının
# "hiç değişmez" diye bellekte tutulan yarısı buna bakar: bölge planı
# uygulanınca ya da tur raporu işlenince sunucuyu yeniden başlatmadan tazelenir.
BINA_SURUMU = "bina_surumu"


def bina_surum_oku(conn: sqlite3.Connection) -> int:
    try:
        return int(ayar_oku(conn, BINA_SURUMU, "0") or 0)
    except (TypeError, ValueError):
        return 0


def bina_surumu_arttir(conn: sqlite3.Connection) -> None:
    """Künye değiştiren her yazmada (aynı işlem içinde) çağrılır; durum sürümünü de arttırır."""
    conn.execute(
        "INSERT INTO ayar(anahtar,deger) VALUES(?,'1') "
        "ON CONFLICT(anahtar) DO UPDATE SET deger = CAST(CAST(deger AS INTEGER) + 1 AS TEXT)",
        (BINA_SURUMU,),
    )
    surumu_arttir(conn)


def bolge_sayisi(conn: sqlite3.Connection) -> int:
    """Şu an kaç satış bölgesi var (etkin bölge planının N'i).

    Plan geçmişi yoksa binalardaki en büyük bölge numarası, o da yoksa
    ``ayarlar.BOLGE_SAYISI`` (8). Sabit 8 varsayan her yer bunu okumalı:
    8 ekipten 14 ekibe çıkıldığında 9-14. bölgelerin satışçısı eklenebilmeli.
    """
    try:
        satir = conn.execute(
            "SELECT n FROM bolge_plani WHERE aktif=1 ORDER BY id DESC LIMIT 1").fetchone()
        if satir:
            return int(satir[0])
    except sqlite3.Error:
        pass
    try:
        satir = conn.execute("SELECT MAX(bolge) FROM bina").fetchone()
        if satir and satir[0]:
            return int(satir[0])
    except sqlite3.Error:
        pass
    return ayarlar.BOLGE_SAYISI
