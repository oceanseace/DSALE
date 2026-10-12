"""kod/masaustu/devir.py: eski düzenden (canli/surum) yeni çalışma klasörüne devir — sahte eski düzenle."""
from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from pathlib import Path

import pytest

from masaustu import devir


def _ozet(kok: Path) -> dict[str, str]:
    return {p.relative_to(kok).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(kok.rglob("*")) if p.is_file()}


@pytest.fixture
def eski(tmp_path: Path) -> Path:
    kok = tmp_path / "canli" / "surum"
    saha = kok / "saha"
    saha.mkdir(parents=True)
    c = sqlite3.connect(saha / "saha.db")
    c.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE bina (id INTEGER PRIMARY KEY, ad TEXT);
        CREATE TABLE kullanici (id INTEGER PRIMARY KEY, ad TEXT);
        CREATE TABLE bos (x);
    """)
    c.executemany("INSERT INTO bina(ad) VALUES (?)", [(f"b{i}",) for i in range(500)])
    c.executemany("INSERT INTO kullanici(ad) VALUES (?)", [(f"k{i}",) for i in range(7)])
    c.commit()
    c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    c.execute("PRAGMA journal_mode=DELETE")
    c.close()
    (saha / "gizli.key").write_bytes(bytes(range(256)) * 2)
    for ad in ("kayit", "raporlar", "yedek", "gorev"):
        (saha / ad).mkdir()
        (saha / ad / f"{ad}.txt").write_text(ad, encoding="utf-8")
    (saha / "yedek" / "goc").mkdir()
    (saha / "yedek" / "goc" / "saha-oncesi.db").write_bytes(b"x" * 10)
    (saha / "api.py").write_text("# kod; taşınmaz", encoding="utf-8")
    op = kok / "operasyon"
    (op / "veri").mkdir(parents=True)
    (op / "obekler.json").write_text('{"obek": []}', encoding="utf-8")
    (op / "veri" / "rapor.xlsx").write_bytes(b"PK..")
    return kok


def _bos(_port: int) -> bool:
    return False


def test_basarili_devir(eski, tmp_path):
    once = _ozet(eski.parent)
    hedef = tmp_path / "veri" / "canli"
    s = devir.devral(eski, hedef, _bos)
    assert s.durum == "yapildi"
    assert s.tablolar == {"bina": 500, "bos": 0, "kullanici": 7}
    c = sqlite3.connect(hedef / "saha" / "saha.db")
    assert c.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert c.execute("SELECT COUNT(*) FROM bina").fetchone()[0] == 500
    c.close()
    assert (hedef / "saha" / "gizli.key").read_bytes() == (eski / "saha" / "gizli.key").read_bytes()
    for ad in ("kayit", "raporlar", "yedek", "gorev"):
        assert (hedef / "saha" / ad / f"{ad}.txt").read_text(encoding="utf-8") == ad
    assert (hedef / "saha" / "yedek" / "goc" / "saha-oncesi.db").exists()
    assert not (hedef / "saha" / "api.py").exists()                     # kod taşınmaz
    assert (hedef / "operasyon" / "obekler.json").exists()
    assert (hedef / "operasyon" / "veri" / "rapor.xlsx").exists()
    assert not (hedef / devir.YARIM).exists()
    not_ = json.loads((hedef / devir.NOT_DOSYASI).read_text(encoding="utf-8"))
    assert not_["tablolar"] == {"bina": 500, "bos": 0, "kullanici": 7} and not_["tablo_sayisi"] == 3
    assert _ozet(eski.parent) == once                                    # kaynak bayt bayt aynı


def test_eski_surum_acikken_devir_yok(eski, tmp_path):
    hedef = tmp_path / "veri" / "canli"
    sorulan = []
    s = devir.devral(eski, hedef, lambda p: sorulan.append(p) or True)
    assert s.durum == "eski_surum_acik" and "Eski sürüm açık" in s.mesaj
    assert sorulan == [8080]
    assert not (hedef / "saha" / "saha.db").exists() and not (hedef / devir.YARIM).exists()


def test_ikinci_acilista_tekrar_devir_yok(eski, tmp_path):
    hedef = tmp_path / "veri" / "canli"
    assert devir.devral(eski, hedef, _bos).durum == "yapildi"
    c = sqlite3.connect(hedef / "saha" / "saha.db")
    c.execute("INSERT INTO bina(ad) VALUES ('yeni')")                      # yeni sürümde iş yapıldı
    c.commit()
    c.close()
    assert not devir.gerekli_mi(eski, hedef)
    assert devir.devral(eski, hedef, _bos).durum == "gerek_yok"
    c = sqlite3.connect(hedef / "saha" / "saha.db")
    assert c.execute("SELECT COUNT(*) FROM bina").fetchone()[0] == 501     # üzerine yazılmadı
    c.close()


def test_yarim_kalan_devir_temizlenip_yeniden_yapilir(eski, tmp_path):
    hedef = tmp_path / "veri" / "canli"
    yarim = hedef / devir.YARIM / "saha"
    yarim.mkdir(parents=True)
    (yarim / "saha.db").write_bytes(b"yarim kalmis bozuk dosya")
    (yarim / "artik.tmp").write_text("x", encoding="utf-8")
    (hedef / "saha").mkdir(parents=True)
    (hedef / "saha" / "gizli.key").write_bytes(b"yarim")                  # yerleştirme yarıda kalmış
    s = devir.devral(eski, hedef, _bos)
    assert s.durum == "yapildi"
    assert not (hedef / devir.YARIM).exists()
    assert not (hedef / "saha" / "artik.tmp").exists()
    assert (hedef / "saha" / "gizli.key").read_bytes() == (eski / "saha" / "gizli.key").read_bytes()
    c = sqlite3.connect(hedef / "saha" / "saha.db")
    assert c.execute("SELECT COUNT(*) FROM kullanici").fetchone()[0] == 7
    c.close()


def test_kaynak_yoksa_bir_sey_yapilmaz(tmp_path):
    hedef = tmp_path / "veri" / "canli"
    assert devir.devral(tmp_path / "yok", hedef, _bos).durum == "kaynak_yok"
    assert not hedef.exists()


def _wal_kaynak(saha: Path) -> int:
    """Kaynağı WAL kipine çevirir; işlenmemiş satırlar ``-wal``'da kalır (eski sunucu düzgün kapanmamış gibi)."""
    tasi = saha.parent / "wal-hazirlik"
    tasi.mkdir()
    shutil.copyfile(saha / "saha.db", tasi / "saha.db")
    c = sqlite3.connect(tasi / "saha.db")
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA wal_autocheckpoint=0")
    c.executemany("INSERT INTO bina(ad) VALUES (?)", [(f"w{i}",) for i in range(25)])
    c.commit()
    shutil.copyfile(tasi / "saha.db", saha / "saha.db")              # bağlantı açıkken: -wal dolu
    shutil.copyfile(tasi / "saha.db-wal", saha / "saha.db-wal")
    c.close()
    shutil.rmtree(tasi)
    return 525


@pytest.mark.parametrize("wal_dolu", [False, True])
def test_kaynak_klasorunde_dosya_olusmaz_wal_dahil(eski, tmp_path, wal_dolu):
    saha = eski / "saha"
    if wal_dolu:
        beklenen = _wal_kaynak(saha)
    else:
        c = sqlite3.connect(saha / "saha.db")
        c.execute("PRAGMA journal_mode=WAL")                               # canlı sunucu WAL kullanır
        c.close()
        beklenen = 500
    once = _ozet(eski.parent)
    s = devir.devral(eski, tmp_path / "veri" / "canli", _bos)
    assert s.durum == "yapildi" and s.tablolar["bina"] == beklenen
    assert _ozet(eski.parent) == once                                    # -shm/-wal oluşmadı, hiçbir şey değişmedi
    assert not (tmp_path / "veri" / "canli" / devir.YARIM).exists()


def test_dogrulama_hatasinda_yarim_birakilmaz(eski, tmp_path, monkeypatch):
    hedef = tmp_path / "veri" / "canli"

    def bozuk(_k, _h):
        raise devir.DevirHatasi("Satır sayıları tutmadı: bina")

    monkeypatch.setattr(devir, "_db_kopyala", bozuk)
    with pytest.raises(devir.DevirHatasi):
        devir.devral(eski, hedef, _bos)
    assert not (hedef / devir.YARIM).exists() and not (hedef / "saha" / "saha.db").exists()
