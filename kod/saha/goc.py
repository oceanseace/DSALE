"""Şema göçü: v0 → v8 (belgeler/OPERASYON_V2_SPEC.md §1.2–§1.14 + belgeler/OPERASYON_V2_EK.md).

    .venv/Scripts/python.exe -m saha.goc --db <yol>          # göç (prova ve elle kullanım)
    .venv/Scripts/python.exe -m saha.goc --db <yol> --kuru   # yalnız bekleyen adımları yazar

Canlıda göçün çağrıldığı TEK yer ``saha/sunucu.py:main``: port denetiminden SONRA, uvicorn
açılmadan ÖNCE. Komut satırı araçları göç yapmaz, yalnız ``surum_dogrula`` ile sürümü denetler.

``hazirla(yol)`` sırası SÖZLEŞMEDİR:
    1. dosya kilidi (``<db>.goc.kilit``; 10 dakikadan eskiyse ya da sahibi süreç ölmüşse bayat)
    2. bağlantı (``isolation_level=None``, busy_timeout 30 sn)
    3. bekleyen var mı? (``db.bekleyen_gocler`` ∪ ``user_version`` < HEDEF) — yoksa yedek bile alınmaz
    4. disk (boş yer ≥ 2,5 × (db + wal))
    5. DOĞRULANMIŞ yedek (``yedekle.goc_yedegi``) — alınamazsa göç BAŞLAMAZ
    6. ``db.gocler`` (faz 2'nin yalnız-ekleyen adımları; yedekten SONRA)
    7. sürüm adımları: her biri tek ``BEGIN IMMEDIATE … COMMIT``, ``sema_goc`` satırı ve
       ``PRAGMA user_version = N`` işlemin İÇİNDE (ROLLBACK'te geri alınır)
    8. son denetim: ``integrity_check = ok``, yeni FK ihlali yok, ``foreign_keys = ON``
    9. ``ayar('son_goc')`` (yalnız toplamlar), kilit bırakılır

Rapor ve hata metinleri yalnız SAYI içerir; kişi adı / telefon yazılmaz.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import yollar

from . import ayarlar, db, sema_v2, yedekle

HEDEF = sema_v2.HEDEF
KILIT_BAYAT_SN = 600            # 10 dakika
DISK_KATSAYI = 2.5


# ----------------------------------------------------------------------------- hatalar, rapor
class GocHatasi(Exception):
    """Göç durdu. ``mesaj`` Türkçedir; ``yedek_yolu`` alınan göç yedeği (varsa);
    ``durdugu_surum`` hatadan sonra veritabanının sürümü (başlangıçla aynıysa hiçbir şey değişmedi)."""

    def __init__(self, mesaj: str, yedek_yolu: str | None = None, durdugu_surum: int | None = None,
                 baslangic_surum: int | None = None):
        super().__init__(mesaj)
        self.mesaj = mesaj
        self.yedek_yolu = yedek_yolu
        self.durdugu_surum = durdugu_surum
        self.baslangic_surum = baslangic_surum
        self.eklenenler: list[str] = []        # hatadan önce uygulanan yalnız-ekleyen adımlar

    @property
    def degismedi(self) -> bool:
        surum_ayni = self.durdugu_surum is None or self.durdugu_surum == self.baslangic_surum
        return surum_ayni and not self.eklenenler


class SurumUyumsuz(GocHatasi):
    """Veritabanının sürümü bu kodun beklediği ``HEDEF`` değil (eski ya da yeni)."""

    def __init__(self, mesaj: str, surum: int):
        super().__init__(mesaj)
        self.surum = surum


@dataclass
class GocRaporu:
    bos: bool                                   # yapılacak iş yoktu (ikinci açılış)
    eski_surum: int
    yeni_surum: int
    yedek_yolu: str | None = None
    sayilar: dict[str, int] = field(default_factory=dict)   # yalnız toplamlar
    satirlar: list[str] = field(default_factory=list)       # konsola yazılacak Türkçe satırlar
    adimlar: list[str] = field(default_factory=list)
    tohum: dict = field(default_factory=dict)
    sure_sn: float = 0.0

    def json(self) -> str:
        return json.dumps({"eski_surum": self.eski_surum, "yeni_surum": self.yeni_surum,
                           "yedek_yolu": self.yedek_yolu, "sayilar": self.sayilar,
                           "adimlar": self.adimlar, "sure_sn": self.sure_sn,
                           "zaman": ayarlar.zaman_metni()}, ensure_ascii=False)


# Testlerin çökme enjeksiyonu için kanca: ``goc._kanca = lambda ad: ...`` (spec §10-8).
# Noktalar: 'v1:insert', 'v1:drop', 'v1:rename', 'adim:<n>:commit'.
def _kanca(ad: str) -> None:  # noqa: ARG001
    return None


def _zaman() -> str:
    return ayarlar.zaman_metni()


def _n(sayi: int) -> str:
    return f"{int(sayi):,}".replace(",", ".")


def _de(sayi: int) -> str:
    """Rakamdan sonra bulunma eki: 2'de, 3'te, 6'da (ünlü uyumu ve sert ünsüz)."""
    return {0: "'da", 1: "'de", 2: "'de", 3: "'te", 4: "'te", 5: "'te", 6: "'da", 7: "'de",
            8: "'de", 9: "'da"}[abs(int(sayi)) % 10]


def gorunen_yol(yol: str | Path | None) -> str:
    """Konsolda gösterilecek yol: proje içindeyse göreli (``saha/yedek/goc/…``), değilse tam yol."""
    if not yol:
        return ""
    try:
        goreli = os.path.relpath(yol, yollar.KOK)
    except ValueError:
        return str(yol)
    return str(yol) if goreli.startswith("..") else goreli


def user_version(conn: sqlite3.Connection) -> int:
    return int(conn.execute("PRAGMA user_version").fetchone()[0])


# ----------------------------------------------------------------------------- kilit
def _kilit_yolu(yol: Path) -> Path:
    return yol.with_name(yol.name + ".goc.kilit")


def _surec_yasiyor(pid: int) -> bool:
    """``pid`` numaralı süreç yaşıyor mu? (Windows'ta ``os.kill`` süreci ÖLDÜRÜR; kullanılmaz.)"""
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.OpenProcess.restype = wintypes.HANDLE
        tutamac = k32.OpenProcess(0x1000, False, pid)        # PROCESS_QUERY_LIMITED_INFORMATION
        if not tutamac:
            return ctypes.get_last_error() == 5                 # erişim reddi: süreç var
        try:
            kod = wintypes.DWORD()
            if not k32.GetExitCodeProcess(tutamac, ctypes.byref(kod)):
                return True
            return kod.value == 259                             # STILL_ACTIVE
        finally:
            k32.CloseHandle(tutamac)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _kilit_bayat(kilit: Path) -> bool:
    try:
        yas = time.time() - kilit.stat().st_mtime
    except OSError:
        return True
    if yas > KILIT_BAYAT_SN:
        return True
    try:
        pid = int(json.loads(kilit.read_text(encoding="utf-8")).get("pid"))
    except (OSError, ValueError, TypeError):
        return False                            # yazılıyor olabilir: bayat sayma
    return not _surec_yasiyor(pid)


def _kilit_al(yol: Path) -> Path:
    kilit = _kilit_yolu(yol)
    for deneme in range(2):
        try:
            fd = os.open(kilit, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if deneme == 0 and _kilit_bayat(kilit):
                kilit.unlink(missing_ok=True)
                continue
            raise GocHatasi("Başka bir güncelleme sürüyor. Bir dakika sonra yeniden deneyin.")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps({"pid": os.getpid(), "zaman": _zaman()}))
        return kilit
    raise GocHatasi("Başka bir güncelleme sürüyor. Bir dakika sonra yeniden deneyin.")


# ----------------------------------------------------------------------------- sürüm denetimi
def surum_dogrula(conn: sqlite3.Connection) -> None:
    """``user_version != HEDEF`` ise ``SurumUyumsuz`` (Türkçe). Komut satırı araçları ve API bunu kullanır."""
    v = user_version(conn)
    if v < HEDEF:
        raise SurumUyumsuz(
            f"Veritabanı eski sürümde (v{v}). Önce sunucuyu yeni sürümle açın (BASLAT.bat); "
            "güncelleme orada yapılır.", v)
    if v > HEDEF:
        raise SurumUyumsuz(
            f"Bu araç veritabanından eski (araç v{HEDEF}, veritabanı v{v}). "
            "Yeni sürüm klasöründen çalıştırın.", v)


def obek_dosyasi() -> Path:
    """Öbek tanımlarının JSON'u (yalnız OKUNUR): ``OPERASYON_OBEK`` ya da çalışma klasöründe ``operasyon/obekler.json``."""
    ortam = os.environ.get("OPERASYON_OBEK")
    return Path(ortam) if ortam else yollar.CALISMA_OPERASYON / "obekler.json"


# ----------------------------------------------------------------------------- tohum (WP-B'nin işlevleri)
_tohum_hatasi: str | None = None      # modül yüklenemediyse nedeni (rapora ve günlüğe yazılır)


def _tohum_fonksiyonlari():
    """``operasyon.v2.sozluk.tohumla`` ve ``operasyon.v2.obek.json_aktar``; yoksa None.

    İş emri modülü yoksa ya da yüklenemiyorsa (içindeki bir hata dahil) göç DURMAZ: tablolar
    kurulur, tohum ertelenir (``tohum_bekliyor``) ve neden günlüğe yazılır. Satış uygulaması
    iş emri modülündeki bir hatanın yüzünden açılmaz hâle gelmemeli.
    """
    global _tohum_hatasi
    try:
        from operasyon.v2 import obek, sozluk
    except ImportError as exc:
        _tohum_hatasi = f"{type(exc).__name__}: {exc}"
        import logging

        logging.getLogger("saha.goc").warning("İş emri modülü yüklenemedi, tohum ertelendi: %s", exc)
        return None
    _tohum_hatasi = None
    tohumla = getattr(sozluk, "tohumla", None)
    json_aktar = getattr(obek, "json_aktar", None)
    if not callable(tohumla) or not callable(json_aktar):
        return None
    return tohumla, json_aktar


def _tohum(conn: sqlite3.Connection, zaman: str, obek_json: bool = True) -> dict:
    """İlçe/mahalle sözlüğü + ``obekler.json`` aktarımı (spec §1.6), açık işlemin İÇİNDE.

    İşlevler henüz yoksa (ya da saplama ``NotImplementedError`` veriyorsa) ``ayar.tohum_bekliyor=1``
    yazılır; tablo kurulur, tohum bir sonraki sunucu açılışında tamamlanır (``bekleyen``).
    """
    fonksiyonlar = _tohum_fonksiyonlari()
    if fonksiyonlar is None:
        db.ayar_yaz(conn, "tohum_bekliyor", "1")
        return {"durum": "bekliyor"}
    tohumla, json_aktar = fonksiyonlar
    conn.execute("SAVEPOINT tohum")
    try:
        sozluk_ozet = tohumla(conn, zaman) or {}
        obek_ozet = json_aktar(conn, obek_dosyasi(), zaman) if obek_json else {}
    except NotImplementedError:
        conn.execute("ROLLBACK TO tohum")
        conn.execute("RELEASE tohum")
        db.ayar_yaz(conn, "tohum_bekliyor", "1")
        return {"durum": "bekliyor"}
    except BaseException:
        conn.execute("ROLLBACK TO tohum")
        conn.execute("RELEASE tohum")
        raise
    conn.execute("RELEASE tohum")
    conn.execute("DELETE FROM ayar WHERE anahtar='tohum_bekliyor'")
    return {"durum": "tamam", "sozluk": _yalniz_sayilar(sozluk_ozet), "obek": _yalniz_sayilar(obek_ozet or {})}


def _yalniz_sayilar(ozet) -> dict:
    """Rapora yalnız sayı ve kısa metin girer (öbek/mahalle adları kişisel veri değil ama rapor sade kalsın)."""
    if not isinstance(ozet, dict):
        return {}
    # Listeler (ör. öbek çakışmaları) yalnız SAYI olarak girer: "0 çakışma" raporda görünsün.
    return {k: (len(v) if isinstance(v, (list, tuple)) else v) for k, v in ozet.items()
            if isinstance(v, (int, float, bool, list, tuple)) or v is None}


def _tohum_bekliyor(conn: sqlite3.Connection) -> bool:
    try:
        satir = conn.execute("SELECT deger FROM ayar WHERE anahtar='tohum_bekliyor'").fetchone()
    except sqlite3.Error:
        return False
    return bool(satir) and satir[0] == "1"


def tohum_tazele(conn: sqlite3.Connection) -> dict:
    """Taze kurulumdan sonra binalar yüklenince sözlüğü binalardan tamamlar (``saha.kur``)."""
    if conn.in_transaction:
        conn.commit()
    conn.execute("BEGIN IMMEDIATE")
    try:
        sonuc = _tohum(conn, _zaman())
        conn.execute("COMMIT")
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    return sonuc


# ----------------------------------------------------------------------------- sürüm adımları
def _ifadeler(conn: sqlite3.Connection, metin: str) -> None:
    for ifade in sema_v2.ifadeler(metin):
        conn.execute(ifade)


def _fk_ihlalleri(conn: sqlite3.Connection) -> set[tuple]:
    return {tuple(r) for r in conn.execute("PRAGMA foreign_key_check").fetchall()}


def _sayimlar_haric(conn: sqlite3.Connection, haric: str) -> dict[str, int]:
    return {t: n for t, n in yedekle.satir_sayilari(conn).items() if t != haric}


def goc_1_rol(conn: sqlite3.Connection, baglam: dict) -> dict:
    """v1: ``kullanici`` rol CHECK'i dört göreve genişler (spec §1.4, doğrulanmış SQL; Ek-2 telefon NULL olabilir).

    ÖNCE yeni tablo kurulur, SONRA eski düşürülür. YASAK desen (önce eskiyi RENAME etmek)
    kullanici'ye bakan alt tabloların REFERENCES metnini ``kullanici_eski``'ye yeniden yazar.
    """
    sql = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='kullanici'").fetchone()[0] or ""
    bilgi = {r[1]: r for r in conn.execute("PRAGMA table_info(kullanici)").fetchall()}
    telefon_zorunlu = bool(bilgi.get("telefon") and bilgi["telefon"][3])
    if "'operasyon'" in sql and not telefon_zorunlu:
        return {"yeniden_kuruldu": False}
    fazla = sorted(set(bilgi) - set(sema_v2.KULLANICI_SUTUNLARI_10))
    if fazla:
        raise GocHatasi(f"Kullanıcı tablosunda beklenmeyen sütunlar var ({', '.join(fazla)}).")

    roller = ",".join(f"'{r}'" for r in sema_v2.ROLLER)
    bilinmeyen = conn.execute(
        f"SELECT rol, COUNT(*) FROM kullanici WHERE rol IS NULL OR rol NOT IN ({roller}) GROUP BY rol").fetchall()
    if bilinmeyen:
        rol, adet = bilinmeyen[0]
        raise GocHatasi(f"kullanıcı tablosunda tanınmayan görev '{rol}' ({adet} kişi).")

    # ÖNCE (spec §1.4): sayı, 10 sütun özeti, sıra sayacı, diğer tabloların sayıları, index/trigger.
    n0 = conn.execute("SELECT COUNT(*) FROM kullanici").fetchone()[0]
    h0 = yedekle.kullanici_ozeti(conn)
    s0_satir = conn.execute("SELECT seq FROM sqlite_sequence WHERE name='kullanici'").fetchone()
    s0 = s0_satir[0] if s0_satir else None
    d0 = _sayimlar_haric(conn, "kullanici")
    x0 = conn.execute(
        "SELECT type, name, sql FROM sqlite_master WHERE tbl_name='kullanici' "
        "AND name NOT LIKE 'sqlite_autoindex%' AND type IN ('index','trigger') AND sql IS NOT NULL").fetchall()
    fk0 = _fk_ihlalleri(conn)

    alanlar = ",".join(sema_v2.KULLANICI_SUTUNLARI_10)
    conn.execute("DROP TABLE IF EXISTS kullanici_yeni")
    conn.execute(sema_v2.KULLANICI_TANIMI_10)
    try:
        conn.execute(f"INSERT INTO kullanici_yeni ({alanlar}) SELECT {alanlar} FROM kullanici")
    except sqlite3.IntegrityError as exc:
        raise GocHatasi(f"Kullanıcı kayıtları yeni tabloya taşınamadı ({exc}).") from exc
    _kanca("v1:insert")
    conn.execute("DROP TABLE kullanici")
    _kanca("v1:drop")
    conn.execute("ALTER TABLE kullanici_yeni RENAME TO kullanici")
    _kanca("v1:rename")
    for _tur, _ad, nesne_sql in x0:
        conn.execute(nesne_sql)
    if s0 is not None:
        degisen = conn.execute(
            "UPDATE sqlite_sequence SET seq = MAX(seq, ?) WHERE name='kullanici'", (s0,)).rowcount
        if degisen == 0:
            conn.execute("INSERT INTO sqlite_sequence(name, seq) VALUES ('kullanici', ?)", (s0,))

    # DOĞRULAMA (biri tutmazsa istisna → ROLLBACK)
    if conn.execute("SELECT COUNT(*) FROM kullanici").fetchone()[0] != n0:
        raise GocHatasi("Kullanıcı sayısı göçte değişti; güncelleme geri alındı.")
    if yedekle.kullanici_ozeti(conn) != h0:
        raise GocHatasi("Kullanıcı kayıtları göçte değişti; güncelleme geri alındı.")
    s1 = conn.execute("SELECT seq FROM sqlite_sequence WHERE name='kullanici'").fetchone()
    if s0 is not None and (not s1 or s1[0] < s0):
        raise GocHatasi("Kullanıcı sıra sayacı geriledi; güncelleme geri alındı.")
    if _sayimlar_haric(conn, "kullanici") != d0:
        raise GocHatasi("Başka bir tablonun satır sayısı değişti; güncelleme geri alındı.")
    if _fk_ihlalleri(conn) - fk0:
        raise GocHatasi("Yabancı anahtar denetimi tutmadı; güncelleme geri alındı.")
    if conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE sql LIKE '%kullanici_eski%' "
                    "OR sql LIKE '%kullanici_yeni%'").fetchone()[0]:
        raise GocHatasi("Şemada eski tablo adına başvuru kaldı; güncelleme geri alındı.")
    if conn.execute(
            "SELECT COUNT(*) FROM sqlite_master m, pragma_foreign_key_list(m.name) p "
            "WHERE m.type='table' AND p.\"table\" NOT IN (SELECT name FROM sqlite_master WHERE type='table')"
    ).fetchone()[0]:
        raise GocHatasi("Bir yabancı anahtarın hedef tablosu yok; güncelleme geri alındı.")
    pin = conn.execute("SELECT COUNT(*) FROM kullanici WHERE pin_hash IS NOT NULL").fetchone()[0]
    return {"yeniden_kuruldu": True, "kisi": n0, "pin": pin, "seq": s0}


def goc_2_ek_sutun(conn: sqlite3.Connection, baglam: dict) -> dict:
    """v2: ``kullanici`` ek sütunları — yalnız ALTER ADD, yalnız sütun yoksa (spec §1.5 + Ek-2)."""
    var = {r[1] for r in conn.execute("PRAGMA table_info(kullanici)").fetchall()}
    eklenen = []
    for sutun, tanim in sema_v2.KULLANICI_EK_SUTUNLAR:
        if sutun not in var:
            conn.execute(f"ALTER TABLE kullanici ADD COLUMN {sutun} {tanim}")
            eklenen.append(sutun)
    return {"eklenen": eklenen}


def goc_3_obek(conn: sqlite3.Connection, baglam: dict) -> dict:
    """v3: ilçe/mahalle sözlüğü ve öbek tabloları + tohum (spec §1.6). ``obekler.json`` yalnız okunur."""
    _ifadeler(conn, sema_v2.V3)
    tohum = _tohum(conn, baglam["zaman"])
    baglam["tohum"] = tohum
    return {"tohum": tohum.get("durum")}


def goc_4_is_emri(conn: sqlite3.Connection, baglam: dict) -> dict:
    """v4: iş emri tabloları, değer tetikleyicileri, ayar varsayılanları (spec §1.7, §1.10)."""
    _ifadeler(conn, sema_v2.V4)
    for ifade in sema_v2.is_emri_tetikleyicileri():
        conn.execute(ifade)
    return {"ayar_eklenen": sema_v2.ayar_varsayilanlari(conn, sema_v2.AYAR_V4)}


def goc_5_indeks(conn: sqlite3.Connection, baglam: dict) -> dict:
    """v5: eski göçte kaybolan ziyaret indeksleri (canlıda vardır; IF NOT EXISTS etkisiz)."""
    _ifadeler(conn, sema_v2.V5)
    return {}


_EK_ANAHTARLARI = {
    6: ("unvan_gorev_esleme",),
    7: ("btk_durduran_aski", "son24_askida_durur"),
}


def goc_6_gorev(conn: sqlite3.Connection, baglam: dict) -> dict:
    """v6 (Ek-1): görev kümesi tablosu; herkes bugünkü göreviyle kümeye girer."""
    _ifadeler(conn, sema_v2.V6)
    eklenen = conn.execute(sema_v2.V6_TOHUM).rowcount
    sema_v2.ayar_varsayilanlari(conn, {k: sema_v2.AYAR_EK[k] for k in _EK_ANAHTARLARI[6]})
    return {"kume_satiri": eklenen}


def goc_7_aski(conn: sqlite3.Connection, baglam: dict) -> dict:
    """v7 (Ek-3): askı aralıkları tablosu (BTK saati abone kaynaklı askıda durur). Dolduran WP-B."""
    _ifadeler(conn, sema_v2.V7)
    sema_v2.ayar_varsayilanlari(conn, {k: sema_v2.AYAR_EK[k] for k in _EK_ANAHTARLARI[7]})
    return {}


def goc_8_ek(conn: sqlite3.Connection, baglam: dict) -> dict:
    """v8 (Ek-5, Ek-8): ticket ekibi/başlığı/türü sütunları, PS26 tabloları, kalan Ek ayarları."""
    var = {r[1] for r in conn.execute("PRAGMA table_info(ticket)").fetchall()}
    eklenen = []
    for sutun, tanim in sema_v2.TICKET_EK_SUTUNLAR:
        if sutun not in var:
            conn.execute(f"ALTER TABLE ticket ADD COLUMN {sutun} {tanim}")
            eklenen.append(sutun)
    _ifadeler(conn, sema_v2.V8)
    sema_v2.ayar_varsayilanlari(conn, sema_v2.AYAR_EK)
    return {"ticket_eklenen": eklenen}


ADIMLAR = [   # (sürüm, ad, fonksiyon) — her fonksiyon _adim içinde kendi BEGIN IMMEDIATE…COMMIT'inde koşar
    (1, "kullanici_rol_dort", goc_1_rol),
    (2, "kullanici_ek_sutunlar", goc_2_ek_sutun),
    (3, "obek_ve_mahalle", goc_3_obek),
    (4, "is_emri_tablolari", goc_4_is_emri),
    (5, "indeks_onarim", goc_5_indeks),
    (6, "kullanici_gorev", goc_6_gorev),
    (7, "is_aski", goc_7_aski),
    (8, "ticket_ek_ve_ps26", goc_8_ek),
]
assert ADIMLAR[-1][0] == HEDEF, "ADIMLAR ile sema_v2.HEDEF uyuşmuyor"


def _adim(conn: sqlite3.Connection, surum: int, ad: str, govde, baglam: dict) -> dict:
    """Tek sürüm adımı: tek işlem; ``sema_goc`` satırı ve ``user_version`` işlemin İÇİNDE."""
    baslama = _zaman()
    fk_kapat = surum == 1
    if fk_kapat:
        conn.execute("PRAGMA foreign_keys=OFF")          # işlem DIŞINDA (içinde etkisiz)
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            ozet = govde(conn, baglam) or {}
            conn.execute(sema_v2.SEMA_GOC)
            conn.execute("INSERT OR REPLACE INTO sema_goc VALUES (?,?,?,?,?,?)",
                         (surum, ad, baslama, _zaman(), baglam.get("yedek_yolu"),
                          json.dumps(ozet, ensure_ascii=False, default=str)))
            conn.execute(f"PRAGMA user_version = {int(surum)}")
            _kanca(f"adim:{surum}:commit")
            conn.execute("COMMIT")
        except BaseException:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
    finally:
        if fk_kapat:
            conn.execute("PRAGMA foreign_keys=ON")
    return ozet


def _tohum_tamamla(conn: sqlite3.Connection, baglam: dict) -> dict:
    """v3'te bekletilen tohum (modül sonradan geldi): tek işlem, sürüm değişmez."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        sonuc = _tohum(conn, baglam["zaman"])
        conn.execute("COMMIT")
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    return sonuc


# ----------------------------------------------------------------------------- dışa açık işlevler
def bekleyen(conn: sqlite3.Connection) -> list[str]:
    """Yapılacak işler: ``db.bekleyen_gocler`` ∪ ``user_version`` < HEDEF adımları ∪ bekleyen tohum."""
    liste = list(db.bekleyen_gocler(conn))
    v = user_version(conn)
    liste += [f"v{s}:{ad}" for s, ad, _ in ADIMLAR if s > v]
    if v >= 3 and _tohum_bekliyor(conn) and _tohum_fonksiyonlari() is not None:
        liste.append("tohum")
    return liste


def sayilar(conn: sqlite3.Connection) -> dict[str, int]:
    """Rapor için yalnız toplamlar."""
    s: dict[str, int] = {}
    for anahtar, sorgu in (
        ("kullanici", "SELECT COUNT(*) FROM kullanici"),
        ("pin", "SELECT COUNT(*) FROM kullanici WHERE pin_hash IS NOT NULL"),
        ("ziyaret", "SELECT COUNT(*) FROM ziyaret"),
        ("bina", "SELECT COUNT(*) FROM bina"),
        ("obek", "SELECT COUNT(*) FROM obek WHERE aktif=1"),
        ("obek_mahalle", "SELECT COUNT(*) FROM obek_mahalle"),
        ("mahalle", "SELECT COUNT(*) FROM mahalle"),
        ("ilce", "SELECT COUNT(*) FROM ilce"),
    ):
        try:
            s[anahtar] = int(conn.execute(sorgu).fetchone()[0])
        except sqlite3.Error:
            pass
    return s


def _disk_denetle(yol: Path) -> None:
    boyut = yol.stat().st_size
    wal = Path(str(yol) + "-wal")
    if wal.exists():
        boyut += wal.stat().st_size
    gerekli = DISK_KATSAYI * boyut
    try:
        bos = shutil.disk_usage(yol.parent).free
    except OSError:
        return
    if bos < gerekli:
        raise GocHatasi(f"Diskte yer yok: {max(1, round(gerekli / 1024 / 1024))} MB gerekli. "
                        "Veritabanına dokunulmadı.")


def _son_denetim(conn: sqlite3.Connection, fk_once: set[tuple]) -> None:
    butunluk = conn.execute("PRAGMA integrity_check").fetchone()[0]
    if butunluk != "ok":
        raise GocHatasi(f"Güncellemeden sonra bütünlük denetimi tutmadı ({butunluk}).")
    if _fk_ihlalleri(conn) - fk_once:
        raise GocHatasi("Güncellemeden sonra yabancı anahtar denetimi tutmadı.")
    conn.execute("PRAGMA foreign_keys=ON")


def _rapor_satirlari(rapor: GocRaporu) -> list[str]:
    s = rapor.sayilar
    parca = [f"GÜNCELLEME TAMAM (v{rapor.eski_surum} → v{rapor.yeni_surum})"]
    if "kullanici" in s:
        parca.append(f"{_n(s['kullanici'])} kişi ({_n(s.get('pin', 0))} PIN)")
    if "ziyaret" in s:
        parca.append(f"{_n(s['ziyaret'])} ziyaret")
    if "bina" in s:
        parca.append(f"{_n(s['bina'])} bina aynen korundu")
    if rapor.tohum.get("durum") == "tamam":
        parca.append(f"{_n(s.get('obek', 0))} öbek / {_n(s.get('obek_mahalle', 0))} mahalle aktarıldı")
    elif rapor.tohum.get("durum") == "bekliyor":
        parca.append("öbek aktarımı ertelendi (iş emri modülü hazır değil)")
    if rapor.yedek_yolu:
        parca.append(f"yedek: {gorunen_yol(rapor.yedek_yolu)}")
    return [" · ".join(parca)]


def hazirla(yol: Path, *, yedek: bool = True) -> GocRaporu:
    """Veritabanını ``HEDEF`` sürüme taşır (sıra: modül başındaki açıklama). Hata → ``GocHatasi``."""
    yol = Path(yol)
    if not yol.exists():
        raise GocHatasi(f"Veritabanı bulunamadı: {yol}")
    kilit = _kilit_al(yol)
    try:
        conn = sqlite3.connect(yol, isolation_level=None, timeout=30.0)
        try:
            conn.execute("PRAGMA busy_timeout=30000")
            conn.execute("PRAGMA foreign_keys=ON")
            return _hazirla(conn, yol, yedek)
        finally:
            conn.close()
    finally:
        kilit.unlink(missing_ok=True)


def _hazirla(conn: sqlite3.Connection, yol: Path, yedek: bool) -> GocRaporu:
    t0 = time.monotonic()
    eski = user_version(conn)
    if eski > HEDEF:
        raise SurumUyumsuz(
            f"Veritabanı bu programdan yeni (program v{HEDEF}, veritabanı v{eski}). "
            "Yeni sürüm klasöründen çalıştırın.", eski)
    if not db.tablo_var(conn, "kullanici"):
        raise GocHatasi("Veritabanı kurulmamış (kullanıcı tablosu yok). Önce: python -m saha.kur")

    gocler_bekleyen = db.bekleyen_gocler(conn)
    adimlar = [a for a in ADIMLAR if a[0] > eski]
    tohum = eski >= 3 and _tohum_bekliyor(conn) and _tohum_fonksiyonlari() is not None
    if not gocler_bekleyen and not adimlar and not tohum:
        return GocRaporu(bos=True, eski_surum=eski, yeni_surum=eski, sayilar=sayilar(conn))

    _disk_denetle(yol)
    yedek_yolu = None
    if yedek:
        try:
            yedek_yolu = str(yedekle.goc_yedegi(yol, eski=eski, yeni=HEDEF))
        except yedekle.YedekHatasi as exc:
            raise GocHatasi(f"Güvenlik yedeği alınamadı: {exc.mesaj} Veritabanına dokunulmadı.",
                            durdugu_surum=eski, baslangic_surum=eski) from exc

    baglam = {"yedek_yolu": yedek_yolu, "zaman": _zaman(), "tohum": {}}
    yapilan: list[str] = []
    fk_once = _fk_ihlalleri(conn)
    try:
        yapilan += db.gocler(conn)
        for surum, ad, govde in adimlar:
            _adim(conn, surum, ad, govde, baglam)
            yapilan.append(f"v{surum}:{ad}")
        if tohum:
            baglam["tohum"] = _tohum_tamamla(conn, baglam)
            yapilan.append("tohum")
        _son_denetim(conn, fk_once)
    except GocHatasi as exc:
        exc.yedek_yolu = exc.yedek_yolu or yedek_yolu
        exc.baslangic_surum = eski
        exc.durdugu_surum = user_version(conn)
        exc.eklenenler = list(yapilan)
        raise
    except Exception as exc:
        hata = GocHatasi(f"Güncelleme sırasında hata: {exc}", yedek_yolu=yedek_yolu,
                         durdugu_surum=user_version(conn), baslangic_surum=eski)
        hata.eklenenler = list(yapilan)
        raise hata from exc

    rapor = GocRaporu(bos=False, eski_surum=eski, yeni_surum=user_version(conn), yedek_yolu=yedek_yolu,
                      sayilar=sayilar(conn), adimlar=yapilan, tohum=baglam.get("tohum") or {},
                      sure_sn=round(time.monotonic() - t0, 2))
    rapor.satirlar = _rapor_satirlari(rapor)
    conn.execute("BEGIN IMMEDIATE")
    try:
        db.ayar_yaz(conn, "son_goc", rapor.json())
        conn.execute("COMMIT")
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    return rapor


def taze_kur(conn: sqlite3.Connection) -> None:
    """Boş dosyaya SEMA + v2 şeması kurar; ``user_version = HEDEF``; ayar varsayılanları; tohum.

    ``db.semayi_kur`` çağırır (``kullanici`` tablosu yokken). Tek işlem: yarım kurulum kalmaz.
    """
    if conn.in_transaction:
        conn.commit()
    conn.execute("BEGIN IMMEDIATE")
    try:
        zaman = _zaman()
        _ifadeler(conn, db.SEMA)
        conn.execute(sema_v2.SEMA_GOC)
        for ifade in sema_v2.tum_v2_ifadeleri():
            conn.execute(ifade)
        sema_v2.ayar_varsayilanlari(conn, sema_v2.AYAR_V4)
        sema_v2.ayar_varsayilanlari(conn, sema_v2.AYAR_EK)
        tohum = _tohum(conn, zaman)
        conn.execute("INSERT OR REPLACE INTO sema_goc VALUES (?,?,?,?,?,?)",
                     (HEDEF, "taze_kurulum", zaman, _zaman(), None,
                      json.dumps({"tohum": tohum.get("durum")}, ensure_ascii=False)))
        conn.execute(f"PRAGMA user_version = {HEDEF}")
        conn.execute("COMMIT")
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise


# ----------------------------------------------------------------------------- komut satırı
def _cerceve(satirlar: list[str]) -> str:
    cizgi = "=" * 62
    return "\n".join([cizgi, *[f"  {s}" for s in satirlar], cizgi])


def hata_metni(exc: GocHatasi) -> str:
    """Konsola çerçeveli Türkçe hata (sunucu ve komut satırı aynı metni yazar)."""
    if exc.degismedi:
        bas = "GÜNCELLEME DURDU — veritabanı DEĞİŞMEDİ."
    elif exc.durdugu_surum == exc.baslangic_surum:
        bas = ("GÜNCELLEME DURDU — yalnız eksik tablo/sütunlar eklendi (veri değişmedi); "
               "bir sonraki açılışta kaldığı yerden sürer.")
    else:
        bas = (f"GÜNCELLEME v{exc.durdugu_surum}{_de(exc.durdugu_surum)} DURDU — tamamlanan adımlar "
               "kalıcı, veri kaybı yok; bir sonraki açılışta kaldığı yerden sürer.")
    satirlar = [bas, f"Neden: {exc.mesaj}"]
    if exc.yedek_yolu:
        satirlar.append(f"Yedek: {gorunen_yol(exc.yedek_yolu)}")
    satirlar += ["Eski sürümle devam etmek için önceki klasörü çalıştırın ya da",
                 "bu ekranın fotoğrafını BT'ye gönderin."]
    return _cerceve(satirlar)


def _canli_mi(yol: Path) -> bool:
    try:
        return Path(yol).resolve() == (ayarlar.CALISMA / "saha.db").resolve()
    except OSError:
        return False


def main(argv: list[str] | None = None) -> int:
    ayrac = argparse.ArgumentParser(description="Saha Sistemi veritabanı göçü (v0 → v%d)" % HEDEF)
    ayrac.add_argument("--db", required=True, help="Veritabanı dosyası")
    ayrac.add_argument("--kuru", action="store_true", help="Yalnız bekleyen adımları yaz, dokunma")
    ayrac.add_argument("--yedeksiz", action="store_true", help="Göç yedeği alma (yalnız karalama kopyalarında)")
    a = ayrac.parse_args(argv)
    ayarlar.konsolu_hazirla()
    yol = Path(a.db)
    if not yol.exists():
        print(f"Veritabanı bulunamadı: {yol}")
        return 1
    if _canli_mi(yol):
        from .sunucu import port_dolu_mu

        if port_dolu_mu(8080):
            print("Sunucu açıkken canlı veritabanı güncellenmez. Önce DURDUR.bat, sonra BASLAT.bat.")
            return 2
        if a.yedeksiz:
            print("Canlı veritabanı yedeksiz güncellenmez.")
            return 2
    if a.kuru:
        conn = sqlite3.connect(Path(yol).resolve().as_uri() + "?mode=ro", uri=True)
        try:
            liste = bekleyen(conn)
            print(f"Sürüm v{user_version(conn)} · hedef v{HEDEF}")
        finally:
            conn.close()
        print("Bekleyen: " + (", ".join(liste) if liste else "yok"))
        return 0
    try:
        rapor = hazirla(yol, yedek=not a.yedeksiz)
    except GocHatasi as exc:
        print(hata_metni(exc))
        return 3
    if rapor.bos:
        print(f"Veritabanı güncel (v{rapor.eski_surum}); yapılacak iş yok, yedek alınmadı.")
    else:
        for s in rapor.satirlar:
            print(s)
    return 0


if __name__ == "__main__":
    sys.exit(main())
