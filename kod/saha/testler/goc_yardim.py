"""Göç testlerinin ortak yardımcıları: v0 (faz 2) şemalı sentetik veritabanı ve anlık görüntü.

Kişisel veri YOK: adlar ve numaralar uydurmadır (5550000xxx gibi gerçek olmayan numaralar).
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path

from saha import db, sema_v2

# Canlıdaki (30.09) kullanici tanımı: iki rollü CHECK, telefon NOT NULL.
ESKI_KULLANICI = """CREATE TABLE IF NOT EXISTS kullanici (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ad          TEXT    NOT NULL,
    telefon     TEXT    NOT NULL UNIQUE,          -- 5XXXXXXXXX
    pin_hash    TEXT,
    davet_kodu  TEXT,
    rol         TEXT    NOT NULL CHECK (rol IN ('satisci','yonetici')),
    bolge       INTEGER,
    aktif       INTEGER NOT NULL DEFAULT 1,
    oturum_no   INTEGER NOT NULL DEFAULT 1,
    olusturma   TEXT    NOT NULL
);
"""

# SEMA'daki ticket tanımının v8 sütunları (onedesk_ekip, kategori, tur) ve öncesindeki virgül.
_V8_TICKET = re.compile(
    r"(aktarim_anahtari TEXT UNIQUE),([^\n]*)\n\s*-- v8[^\n]*\n\s*onedesk_ekip[^\n]*\n\s*kategori[^\n]*\n"
    r"\s*tur [^\n]*\n")


def eski_sema(kullanici: str = ESKI_KULLANICI) -> str:
    """Göç öncesi (v0) şema: bugünkü SEMA'nın kullanici ve ticket'ı eski hâliyle."""
    metin = db.SEMA.replace(sema_v2.KULLANICI_TAZE, kullanici)
    assert metin != db.SEMA, "SEMA'da kullanici tanımı bulunamadı"
    metin, n = _V8_TICKET.subn(r"\1\2\n", metin)
    assert n == 1, "SEMA'da v8 ticket sütunları bulunamadı"
    return metin


def eski_db_kur(yol: Path, kisi: int = 6, kullanici: str = ESKI_KULLANICI,
                roller: tuple[str, ...] = ("yonetici", "satisci")) -> Path:
    """Sentetik v0 veritabanı: kişiler (2'si PIN'li, biri silinmiş → sıra boşluklu), binalar,
    ziyaretler, görevler, bir ticket. ``user_version = 0``."""
    c = sqlite3.connect(yol)
    try:
        for ifade in sema_v2.ifadeler(eski_sema(kullanici)):
            c.execute(ifade)
        for i in range(1, kisi + 2):
            rol = roller[0] if i == 1 else roller[1 % len(roller)]
            c.execute("INSERT INTO kullanici (ad, telefon, pin_hash, davet_kodu, rol, bolge, olusturma) "
                      "VALUES (?,?,?,?,?,?,?)",
                      (f"Deneme Kişi {i}", f"555000{i:04d}", "scrypt$x$y$z$aa$bb" if i <= 2 else None,
                       None if i <= 2 else f"{100000 + i}", rol, None if rol == "yonetici" else (i % 8) + 1,
                       "2026-09-01 10:00:00"))
        c.execute("DELETE FROM kullanici WHERE id=?", (kisi + 1,))     # sıra sayacı > en büyük id
        for b in range(1, 41):
            c.execute("INSERT INTO bina (bina_serial, ad, mahalle, ilce, il, lat, lon, res_hp, firsat, bolge, location_id) "
                      "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                      (f"BN-T{b:04d}", f"Deneme Sitesi {b}", "Görükle", "Nilüfer", "Bursa",
                       40.2 + b / 1000, 28.9 + b / 1000, 10, 5, (b % 8) + 1, str(900000 + b)))
            c.execute("INSERT INTO bina_durum (bina_serial) VALUES (?)", (f"BN-T{b:04d}",))
        for z in range(1, 16):
            c.execute("INSERT INTO ziyaret (offline_id, bina_serial, kullanici_id, zaman, sonuc, kayit_zamani) "
                      "VALUES (?,?,?,?,?,?)",
                      (f"z-{z}", f"BN-T{z:04d}", 2 + z % 3, "2026-09-20 10:00:00", "ilgilenmedi",
                       "2026-09-20 10:00:00"))
        c.execute("INSERT INTO gorev (kullanici_id, tarih, olusturan_id, kaynak, olusturma) "
                  "VALUES (2, '2026-09-20', 1, 'yonetici', '2026-09-20 08:00:00')")
        c.execute("INSERT INTO gorev_bina (gorev_id, bina_serial, sira) VALUES (1, 'BN-T0001', 1)")
        c.execute("INSERT INTO ticket (konu, bina_serial, olusturan_id, olusturma, guncelleme) "
                  "VALUES ('SİNYAL', 'BN-T0002', 1, '2026-09-21 09:00:00', '2026-09-21 09:00:00')")
        c.execute("INSERT INTO ayar (anahtar, deger) VALUES ('kurulum', '2026-09-01 10:00:00')")
        c.commit()
    finally:
        c.close()
    return yol


def surum(yol: Path) -> int:
    c = sqlite3.connect(yol)
    try:
        return int(c.execute("PRAGMA user_version").fetchone()[0])
    finally:
        c.close()


def anlik_goruntu(yol: Path, sutunlar: dict[str, list[str]] | None = None) -> dict:
    """Şema metni + her tablonun sayısı ve rowid sıralı özeti + kullanici 10 sütun özeti + sıra sayacı.

    ``sutunlar`` verilirse satır özeti yalnız o sütunlardan alınır (göç sütun eklediği tablolar için).
    """
    c = sqlite3.connect(Path(yol).resolve().as_uri() + "?mode=ro", uri=True)
    try:
        tablolar = [r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        tablo_ozet = {}
        for t in tablolar:
            alanlar = (sutunlar or {}).get(t) or [r[1] for r in c.execute(f'PRAGMA table_info("{t}")')]
            satirlar = c.execute(f'SELECT {",".join(chr(34) + a + chr(34) for a in alanlar)} FROM "{t}" '
                                 f'ORDER BY rowid').fetchall()
            metin = json.dumps(satirlar, ensure_ascii=False, default=str)
            tablo_ozet[t] = (len(satirlar), hashlib.sha256(metin.encode("utf-8")).hexdigest())
        return {
            "sema": sorted(tuple(r) for r in c.execute("SELECT type, name, sql FROM sqlite_master")),
            "tablolar": tablo_ozet,
            "kullanici10": _kullanici10(c),
            "seq": dict(c.execute("SELECT name, seq FROM sqlite_sequence").fetchall()),
            "user_version": int(c.execute("PRAGMA user_version").fetchone()[0]),
        }
    finally:
        c.close()


def sutun_haritasi(yol: Path) -> dict[str, list[str]]:
    c = sqlite3.connect(Path(yol).resolve().as_uri() + "?mode=ro", uri=True)
    try:
        return {t: [r[1] for r in c.execute(f'PRAGMA table_info("{t}")')]
                for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' "
                                      "AND name NOT LIKE 'sqlite_%'").fetchall()}
    finally:
        c.close()


def _kullanici10(c: sqlite3.Connection) -> str:
    satirlar = c.execute(f"SELECT {','.join(sema_v2.KULLANICI_SUTUNLARI_10)} FROM kullanici ORDER BY id").fetchall()
    return hashlib.sha256(json.dumps([list(r) for r in satirlar], ensure_ascii=False).encode()).hexdigest()


def fk_hedefleri(yol: Path) -> list[tuple[str, str, str]]:
    c = sqlite3.connect(Path(yol).resolve().as_uri() + "?mode=ro", uri=True)
    try:
        return sorted((m, p[3], p[2]) for (m,) in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            for p in c.execute(f'PRAGMA foreign_key_list("{m}")').fetchall())
    finally:
        c.close()
