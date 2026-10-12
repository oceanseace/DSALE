"""Canlı verinin devri: eski düzen (``canli/surum``) → Turkcell.exe'nin çalışma klasörü (``veri/canli``).

İlk açılışta, sunucu başlamadan BİR KEZ çalışır (``turkcell.py``). Kural: kaynağa (``canli/``) yalnız OKUNUR
dokunulur; hiçbir dosyası değişmez, taşınmaz, silinmez.

    eski: <kaynak>/saha/{saha.db, gizli.key, kayit/, raporlar/, yedek/, gorev/}
          <kaynak>/operasyon/{obekler.json, veri/}
    yeni: <hedef>/saha/...   <hedef>/operasyon/...   (geliştirme klasörüyle aynı düzen; kod/yollar.py)

Adımlar: önce ``<hedef>/.devir-yarim/`` içine kopyalanır (veritabanı SQLite yedekleme API'siyle; kaynak klasörde
``-shm``/``-wal`` bile oluşmaz, işlenmemiş bir WAL da alınır — ``_db_kopyala``), sonra doğrulanır (``PRAGMA integrity_check`` = ok, her tablonun satır
sayısı kaynakla aynı, ``gizli.key`` bayt bayt aynı), en son yerine konur: veritabanı EN SON, ardından
``devir.json``. Yarıda kalan bir devir (``.devir-yarim`` duruyor, ``saha.db`` yok) bir sonraki açılışta temizlenip
baştan yapılır. ``devir.json``'a kişi verisi yazılmaz: tarih, kaynak yolu, tablo satır sayıları.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

YARIM = ".devir-yarim"
NOT_DOSYASI = "devir.json"
SAHA_KLASORLERI = ("kayit", "raporlar", "yedek", "gorev")
ESKI_PORT = 8080


class DevirHatasi(Exception):
    """Devir doğrulanamadı; hedefte yarım bir şey bırakılmadı, kaynak değişmedi."""


@dataclass
class DevirSonucu:
    durum: str                       # "yapildi" | "gerek_yok" | "kaynak_yok" | "eski_surum_acik"
    mesaj: str = ""
    tablolar: dict[str, int] = field(default_factory=dict)


def _db_kopyala(kaynak: Path, hedef: Path) -> dict[str, int]:
    """Yedekleme API'siyle kopya; sayımlar kopyayla AYNI okuma işleminde alınır. Kaynak klasörde HİÇBİR dosya
    oluşmaz/değişmez:

    * ``-wal`` yok ya da boş: ``immutable=1`` ile açılır (kilit yok, ``-shm``/``-wal`` oluşturulmaz). Eski sunucu
      kapalıdır (8080 boş; ``devral`` denetler), dosya o an değişmiyor.
    * ``-wal`` dolu (eski sunucu düzgün kapanmamış): salt ``mode=ro`` bile ``-shm`` yazar. Önce veritabanı ve
      ``-wal`` hazırlık klasörüne bayt bayt alınır, yedekleme API'si o kopyadan çalışır (WAL orada işlenir).
    """
    wal = Path(str(kaynak) + "-wal")
    if wal.is_file() and wal.stat().st_size > 0:
        ara = hedef.parent / "kaynak-kopya"
        ara.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(kaynak, ara / kaynak.name)
        shutil.copyfile(wal, ara / wal.name)
        try:
            return _yedekle_dogrula(sqlite3.connect(ara / kaynak.name, timeout=10), hedef)   # kendi kopyamız
        finally:
            shutil.rmtree(ara, ignore_errors=True)
    uri = kaynak.resolve().as_uri() + "?mode=ro&immutable=1"
    return _yedekle_dogrula(sqlite3.connect(uri, uri=True, timeout=10), hedef)


def _yedekle_dogrula(k: sqlite3.Connection, hedef: Path) -> dict[str, int]:
    try:
        k.execute("BEGIN")
        tablolar = [r[0] for r in k.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        sayilar = {t: k.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in tablolar}
        h = sqlite3.connect(hedef)
        try:
            k.backup(h)
        finally:
            h.close()
        k.execute("COMMIT")
    finally:
        k.close()
    h = sqlite3.connect(hedef)
    try:
        butunluk = h.execute("PRAGMA integrity_check").fetchone()[0]
        yeni = {t: h.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in sayilar}
    finally:
        h.close()
    if butunluk != "ok":
        raise DevirHatasi(f"Kopyanın bütünlük denetimi geçmedi: {butunluk}")
    if yeni != sayilar:
        farkli = sorted(t for t in sayilar if yeni.get(t) != sayilar[t])
        raise DevirHatasi(f"Satır sayıları tutmadı: {', '.join(farkli)}")
    return sayilar


def _kopyala(kaynak: Path, hedef: Path) -> None:
    if kaynak.is_dir():
        shutil.copytree(kaynak, hedef, dirs_exist_ok=True)
    elif kaynak.is_file():
        hedef.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(kaynak, hedef)


def _yerine_koy(kaynak: Path, hedef: Path) -> None:
    """Hazırlık klasöründen yerine: klasörler birleştirilir, dosyalar değiştirilir (aynı birimde, os.replace)."""
    if kaynak.is_dir():
        hedef.mkdir(parents=True, exist_ok=True)
        for alt in kaynak.iterdir():
            _yerine_koy(alt, hedef / alt.name)
    else:
        hedef.parent.mkdir(parents=True, exist_ok=True)
        os.replace(kaynak, hedef)


def gerekli_mi(kaynak: Path, hedef: Path) -> bool:
    return not (hedef / "saha" / "saha.db").exists() and (kaynak / "saha" / "saha.db").is_file()


def devral(kaynak: Path, hedef: Path, port_dolu: Callable[[int], bool],
           simdi: Callable[[], dt.datetime] = dt.datetime.now) -> DevirSonucu:
    """Eski düzenden (``kaynak`` = ``canli/surum``) yeni çalışma klasörüne (``hedef``) devir.

    ``port_dolu(8080)`` doğruysa eski sürüm açıktır: o hâlâ yazıyor olabilir, devir YAPILMAZ.
    """
    kaynak, hedef = Path(kaynak), Path(hedef)
    yarim = hedef / YARIM
    if (hedef / "saha" / "saha.db").exists():
        if yarim.exists():                               # yerleştirme bitmiş, yalnız temizlik kalmış
            shutil.rmtree(yarim, ignore_errors=True)
        return DevirSonucu("gerek_yok")
    if not (kaynak / "saha" / "saha.db").is_file():
        return DevirSonucu("kaynak_yok")
    if port_dolu(ESKI_PORT):
        return DevirSonucu("eski_surum_acik",
                           "Eski sürüm açık (8080). Eski sunucuyu kapatıp Turkcell'i yeniden açın; "
                           "veriniz o zaman taşınır.")

    if yarim.exists():                                   # önceki deneme yarıda kalmış: baştan
        shutil.rmtree(yarim)
    (yarim / "saha").mkdir(parents=True)
    try:
        tablolar = _db_kopyala(kaynak / "saha" / "saha.db", yarim / "saha" / "saha.db")
        anahtar = kaynak / "saha" / "gizli.key"
        if anahtar.is_file():
            shutil.copy2(anahtar, yarim / "saha" / "gizli.key")
            if (yarim / "saha" / "gizli.key").read_bytes() != anahtar.read_bytes():
                raise DevirHatasi("gizli.key kopyası kaynakla aynı değil.")
        for ad in SAHA_KLASORLERI:
            _kopyala(kaynak / "saha" / ad, yarim / "saha" / ad)
        _kopyala(kaynak / "operasyon" / "obekler.json", yarim / "operasyon" / "obekler.json")
        _kopyala(kaynak / "operasyon" / "veri", yarim / "operasyon" / "veri")
    except Exception:
        shutil.rmtree(yarim, ignore_errors=True)
        raise

    # Yerleştirme: önce her şey, veritabanı EN SON (saha.db varsa devir bitmiş sayılır).
    db = yarim / "saha" / "saha.db"
    gecici_db = yarim / "saha.db.son"
    os.replace(db, gecici_db)
    _yerine_koy(yarim / "saha", hedef / "saha")
    if (yarim / "operasyon").exists():
        _yerine_koy(yarim / "operasyon", hedef / "operasyon")
    os.replace(gecici_db, hedef / "saha" / "saha.db")
    not_ = {
        "tarih": simdi().isoformat(timespec="seconds"),
        "kaynak": str(kaynak),
        "hedef": str(hedef),
        "dogrulama": "integrity_check=ok; satır sayıları eşit; gizli.key bayt bayt aynı",
        "tablo_sayisi": len(tablolar),
        "tablolar": tablolar,
    }
    (hedef / NOT_DOSYASI).write_text(json.dumps(not_, ensure_ascii=False, indent=1), encoding="utf-8")
    shutil.rmtree(yarim, ignore_errors=True)
    return DevirSonucu("yapildi", f"Eski sürümün verisi taşındı ({len(tablolar)} tablo).", tablolar)
