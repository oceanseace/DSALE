"""Sonradan eklenen operasyon tabloları ve ilk kullanımda YEDEKLİ kurulumları (göçün tek yeri).

Giriş: ``hazirla(conn)`` — eksik tablo varsa önce doğrulanmış güvenlik yedeği (``aktarim.aktarim_yedegi``: salt
okunur kaynak + backup API + bütünlük denetimi), sonra tek işlemde kurulum; yedek alınamazsa hiçbir şey kurulmaz.
Çağıranlar: yalnız YAZAN yollar (isaret.yaz, boss_ham.yaz, boss_yazma.kuyruga_ekle …); okuyanlar ``var_mi`` ile bakar.
``dagitim.hazirla`` da aynı ``yedekli_kur``'u kullanır.
"""
from __future__ import annotations

import sqlite3

from .islem import islem

SURUM = "2"

# is_isaret  : kullanıcının satıra boyadığı renk (eski, satır düzeyi dolgu); iş başına tek satır. Hâlâ geçerli:
#              satırın BÜTÜN hücreleri bu rengi alır, hücre rengi (is_hucre_renk) üstüne yazar.
# is_hucre_renk: hücre düzeyi dolgu (Excel gibi; iş no + sütun kimliği). renk 'yok' = satır rengini bu hücrede kaldır.
# boss_ham   : BOSS Teknik Havuz listesinin bir görevdeki BÜTÜN alanları (düzleştirilmiş JSON); yalnız açık işler.
# boss_yazma : BOSS'a yazılacaklar kuyruğunun kalıcı kaydı (girdi + durum; gövde her seferinde şablondan kurulur).
# boss_detay : BOSS iş ayrıntısı (sekmeler + ham, zlib'li JSON; kişisel veri) — yalnız açık işler, iş kapanınca silinir.
# kisi_tercih: TASKS/MAP kişisel tercihleri (düzen, kayıtlı düzenler, ortak süzgeç; tasks_tercih.py) — müşteri verisi yok.
# unvan_duzen: Administrator'ın unvan başına varsayılan TASKS düzeni.
TABLOLAR: dict[str, list[str]] = {
    "is_isaret": [
        "CREATE TABLE IF NOT EXISTS is_isaret (is_no TEXT PRIMARY KEY, renk TEXT NOT NULL, zaman TEXT NOT NULL, "
        "kullanici_id INTEGER, kullanici_ad TEXT)",
    ],
    "is_hucre_renk": [
        "CREATE TABLE IF NOT EXISTS is_hucre_renk (is_no TEXT NOT NULL, sutun TEXT NOT NULL, renk TEXT NOT NULL, "
        "zaman TEXT NOT NULL, kullanici_id INTEGER, kullanici_ad TEXT, PRIMARY KEY (is_no, sutun))",
    ],
    "boss_ham": [
        "CREATE TABLE IF NOT EXISTS boss_ham (task_no TEXT PRIMARY KEY, veri TEXT NOT NULL, guncelleme TEXT NOT NULL)",
    ],
    "boss_yazma": [
        "CREATE TABLE IF NOT EXISTS boss_yazma (id INTEGER PRIMARY KEY AUTOINCREMENT, tur TEXT NOT NULL, "
        "is_no TEXT NOT NULL, task_no TEXT, girdi TEXT NOT NULL, durum TEXT NOT NULL DEFAULT 'bekliyor', "
        "olusturma TEXT NOT NULL, guncelleme TEXT NOT NULL, kullanici_id INTEGER, kullanici_ad TEXT, sonuc TEXT)",
        "CREATE INDEX IF NOT EXISTS ix_boss_yazma_durum ON boss_yazma(durum, id)",
        "CREATE INDEX IF NOT EXISTS ix_boss_yazma_is ON boss_yazma(is_no, id)",
    ],
    "boss_detay": [
        "CREATE TABLE IF NOT EXISTS boss_detay (task_no TEXT PRIMARY KEY, uuid TEXT, iz TEXT, zaman TEXT NOT NULL, "
        "zaman_sn REAL NOT NULL, veri BLOB NOT NULL)",
    ],
    "kisi_tercih": [
        "CREATE TABLE IF NOT EXISTS kisi_tercih (kullanici_id INTEGER NOT NULL, anahtar TEXT NOT NULL, "
        "deger TEXT NOT NULL, guncelleme TEXT NOT NULL, PRIMARY KEY (kullanici_id, anahtar))",
    ],
    "unvan_duzen": [
        "CREATE TABLE IF NOT EXISTS unvan_duzen (unvan_id INTEGER PRIMARY KEY, veri TEXT NOT NULL, "
        "guncelleme TEXT NOT NULL, kullanici_id INTEGER)",
    ],
}


def var_mi(conn: sqlite3.Connection, tablo: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (tablo,)).fetchone() is not None


def _yedek_al(conn: sqlite3.Connection) -> None:
    from . import aktarim
    try:
        yol = aktarim._db_yolu(conn)
    except Exception:      # noqa: BLE001 — bellek içi veritabanı: yedek yok
        yol = None
    if yol and str(yol):
        aktarim.aktarim_yedegi(yol)        # hata → kurulum yapılmaz (yukarı fırlar)


def yedekli_kur(conn: sqlite3.Connection, ad: str, ifadeler: list[str], tablolar: tuple[str, ...],
                yedek: bool = True) -> bool:
    """``tablolar``dan biri eksikse: yedek → tek işlemde ``ifadeler`` → ``ayar('<ad>_sema')``. Kurduysa True."""
    if all(var_mi(conn, t) for t in tablolar):
        return False
    if yedek:
        _yedek_al(conn)
    with islem(conn):
        for sql in ifadeler:
            conn.execute(sql)
        conn.execute("INSERT INTO ayar(anahtar, deger) VALUES(?, ?) ON CONFLICT(anahtar) DO UPDATE SET "
                     "deger = excluded.deger", (f"{ad}_sema", SURUM))
    return True


def hazirla(conn: sqlite3.Connection, yedek: bool = True) -> bool:
    """Bu dosyadaki bütün tablolar (eksikse tek yedekle birlikte kurulur)."""
    return yedekli_kur(conn, "ek", [s for liste in TABLOLAR.values() for s in liste], tuple(TABLOLAR), yedek)
