"""Veritabanının günlük yedeğini alır — 30 gün saklar.

    .venv/Scripts/python.exe -m saha.yedekle           # yedek al
    .venv/Scripts/python.exe -m saha.yedekle --liste   # yedekleri göster
    .venv/Scripts/python.exe -m saha.yedekle --gun 60  # daha uzun saklasın

Yedek ``saha/yedek/saha-YYYY-AA-GG.db`` olarak yazılır. Kopyalama SQLite'ın
kendi ``backup()`` işleviyle yapılır: sunucu ÇALIŞIRKEN de güvenlidir, yarım
yazılmış bir dosya oluşmaz (düz dosya kopyası WAL yüzünden bozuk çıkabilir).

Aynı gün ikinci kez çalıştırılırsa o günün yedeğinin üzerine yazar. 30 günden
eski dosyalar silinir; kaç dosya kalırsa kalsın en yeni 7 tanesi asla silinmez
(bilgisayar uzun süre kapalı kaldıysa elde hiç yedek kalmasın istemeyiz).

Windows Görev Zamanlayıcı ile her gün çalıştırmak için: saha/YEDEK.bat

v2 (spec §1.3, §1.12): göç öncesi ve rapor aktarımı öncesi DOĞRULANMIŞ yedekler
(``goc_yedegi``, ``aktarim_yedegi``) veritabanının yanındaki ``yedek/goc/`` ve
``yedek/aktarim/`` alt klasörlerine yazılır; günlük yedeklere ve ``eskileri_sil``'e
karışmaz. Saklama kuralları ``saklama_uygula``'dadır.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import sqlite3
import stat
import sys
from pathlib import Path

from . import ayarlar, db

YEDEK_DIZINI = ayarlar.CALISMA / "yedek"
SAKLAMA_GUN = 30
EN_AZ_DOSYA = 7
GOC_SAKLA = 5                # göç yedeklerinden en yeni 5'i hep kalır
GOC_EN_ESKI_GUN = 90         # 90 günden eskisi yalnız daha yeni doğrulanmış göç yedeği varsa silinir
AKTARIM_SAKLA = 10           # aktarım öncesi yedeklerden son 10'u


class YedekHatasi(Exception):
    """Doğrulanmış yedek alınamadı. ``mesaj`` Türkçedir; yarım dosya bırakılmaz."""

    def __init__(self, mesaj: str):
        super().__init__(mesaj)
        self.mesaj = mesaj


def _uri(yol: Path, ek: str = "mode=ro") -> str:
    return Path(yol).resolve().as_uri() + "?" + ek


def _tablolar(conn: sqlite3.Connection) -> list[str]:
    return [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]


def satir_sayilari(conn: sqlite3.Connection) -> dict[str, int]:
    """Her tablonun satır sayısı (``sqlite_sequence`` dahil değil)."""
    return {t: conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in _tablolar(conn)}


def kullanici_ozeti(conn: sqlite3.Connection) -> str | None:
    """``kullanici`` tablosunun 10 sütunluk özeti (spec §1.4 h0). Tablo yoksa None."""
    from .sema_v2 import KULLANICI_SUTUNLARI_10

    try:
        satirlar = conn.execute(
            f"SELECT {','.join(KULLANICI_SUTUNLARI_10)} FROM kullanici ORDER BY id").fetchall()
    except sqlite3.Error:
        return None
    metin = json.dumps([list(r) for r in satirlar], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(metin.encode("utf-8")).hexdigest()


def _damga() -> str:
    return ayarlar.simdi().strftime("%Y%m%d-%H%M%S")


def _dogrulanmis_kopya(kaynak: Path, hedef: Path, tam: bool) -> Path:
    """Kaynağı salt okunur açıp backup API ile ``hedef``e kopyalar ve doğrular.

    Sayımlar kopyayla AYNI anlık görüntüden alınır (okuma işlemi yedek boyunca açık kalır),
    böylece sunucu açıkken araya giren bir yazma yanlış "tutmadı" hatası üretmez.
    Doğrulama tutmazsa geçici dosya silinir, istisna fırlar; asıl ada hiçbir şey yazılmaz.
    """
    hedef.parent.mkdir(parents=True, exist_ok=True)
    gecici = hedef.with_name(hedef.name + ".yaziliyor")
    for ek in ("", "-wal", "-shm", "-journal"):
        Path(str(gecici) + ek).unlink(missing_ok=True)
    try:
        k = sqlite3.connect(_uri(kaynak), uri=True, timeout=30.0)
        try:
            k.execute("BEGIN")
            kaynak_sayilari = satir_sayilari(k)
            kaynak_ozet = kullanici_ozeti(k) if tam else None
            h = sqlite3.connect(gecici)
            try:
                k.backup(h)
            finally:
                h.close()
            k.execute("COMMIT")
        finally:
            k.close()

        h = sqlite3.connect(gecici, isolation_level=None)
        try:
            butunluk = h.execute("PRAGMA integrity_check").fetchone()[0]
            if butunluk != "ok":
                raise YedekHatasi(f"Yedek bütünlük denetiminden geçmedi ({butunluk}).")
            if satir_sayilari(h) != kaynak_sayilari:
                raise YedekHatasi("Yedekteki satır sayıları kaynakla aynı değil.")
            if tam and kullanici_ozeti(h) != kaynak_ozet:
                raise YedekHatasi("Yedekteki kişi kayıtları kaynakla aynı değil.")
            # Kapanınca -wal/-shm kalmasın: yedek tek dosya olsun.
            h.execute("PRAGMA journal_mode=DELETE")
        finally:
            h.close()
        os.replace(gecici, hedef)
    except YedekHatasi:
        Path(gecici).unlink(missing_ok=True)
        raise
    except (sqlite3.Error, OSError) as exc:
        Path(gecici).unlink(missing_ok=True)
        raise YedekHatasi(f"Yedek alınamadı: {exc}") from exc
    try:
        os.chmod(hedef, stat.S_IREAD)             # salt okunur: yanlışlıkla üzerine yazılmasın
    except OSError:
        pass
    return hedef


def goc_yedegi(kaynak: Path, eski: int, yeni: int, etiket: str = "oncesi") -> Path:
    """Göç (ya da sıfırlama / gösterim temizliği) öncesi doğrulanmış yedek (spec §1.3).

    ``<db klasörü>/yedek/goc/saha-{etiket}-v{eski}-v{yeni}-{AAAAAGG-SSDDss}.db``: günlük
    ``saha-AAAA-AA-GG.db`` dosyasının üzerine yazmaz. Doğrulama: ``integrity_check``, her
    tablonun satır sayısı ve ``kullanici`` 10 sütun özeti. Tutmazsa ``YedekHatasi``.
    """
    kaynak = Path(kaynak)
    hedef = kaynak.parent / "yedek" / "goc" / f"saha-{etiket}-v{eski}-v{yeni}-{_damga()}.db"
    sayac = 1
    while hedef.exists():                      # aynı saniyede ikinci yedek üzerine yazmasın
        sayac += 1
        hedef = hedef.with_name(f"saha-{etiket}-v{eski}-v{yeni}-{_damga()}-{sayac}.db")
    return _dogrulanmis_kopya(kaynak, hedef, tam=True)


def aktarim_yedegi(kaynak: Path) -> Path:
    """Rapor aktarımı öncesi yedek: ``yedek/aktarim/saha-aktarim-{zaman}.db`` (son 10 tutulur)."""
    kaynak = Path(kaynak)
    hedef = kaynak.parent / "yedek" / "aktarim" / f"saha-aktarim-{_damga()}.db"
    sayac = 1
    while hedef.exists():
        sayac += 1
        hedef = hedef.with_name(f"saha-aktarim-{_damga()}-{sayac}.db")
    return _dogrulanmis_kopya(kaynak, hedef, tam=False)


def _sil(yol: Path) -> bool:
    try:
        os.chmod(yol, stat.S_IREAD | stat.S_IWRITE)
        yol.unlink()
        return True
    except OSError:
        return False


def saklama_uygula(kaynak: Path | None = None, simdi: dt.datetime | None = None) -> dict:
    """Yedek saklama kuralları (spec §1.12). Günlük yedeklere dokunmaz (onlar ``eskileri_sil``).

    * ``yedek/aktarim/``: en yeni 10 dosya kalır.
    * ``yedek/goc/``: en yeni 5 dosya hep kalır; daha eskisi 90 günden eskiyse ve kendisinden
      daha yeni doğrulanmış bir göç yedeği varsa silinir.
    """
    kaynak = Path(kaynak or db.db_yolu())
    an = simdi or ayarlar.simdi()
    sonuc = {"aktarim_silinen": 0, "goc_silinen": 0}

    aktarim = kaynak.parent / "yedek" / "aktarim"
    if aktarim.is_dir():
        dosyalar = sorted(aktarim.glob("saha-aktarim-*.db"), key=lambda p: p.name, reverse=True)
        for d in dosyalar[AKTARIM_SAKLA:]:
            sonuc["aktarim_silinen"] += _sil(d)

    goc = kaynak.parent / "yedek" / "goc"
    if goc.is_dir():
        dosyalar = sorted(goc.glob("saha-*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
        sinir = (an - dt.timedelta(days=GOC_EN_ESKI_GUN)).timestamp()
        for d in dosyalar[GOC_SAKLA:]:
            # Listede kendisinden yeni en az 5 doğrulanmış yedek var (sıralama gereği).
            if d.stat().st_mtime < sinir:
                sonuc["goc_silinen"] += _sil(d)
    return sonuc


def _boyut(bayt: int) -> str:
    return f"{bayt / 1024 / 1024:.1f} MB".replace(".", ",")


def yedek_al(hedef_dizin: Path | None = None) -> Path:
    """Veritabanını güvenli biçimde kopyalar ve yolunu döndürür."""
    kaynak = db.db_yolu()
    if not kaynak.exists():
        raise SystemExit(f"Veritabanı bulunamadı: {kaynak}")

    dizin = hedef_dizin or YEDEK_DIZINI
    dizin.mkdir(parents=True, exist_ok=True)
    hedef = dizin / f"saha-{ayarlar.bugun():%Y-%m-%d}.db"
    gecici = hedef.with_suffix(".db.yaziliyor")

    kaynak_conn = sqlite3.connect(f"file:{kaynak}?mode=ro", uri=True, timeout=30.0)
    try:
        hedef_conn = sqlite3.connect(gecici)
        try:
            with hedef_conn:
                kaynak_conn.backup(hedef_conn)
        finally:
            hedef_conn.close()
    finally:
        kaynak_conn.close()

    # Kopya tamamlanmadan eski yedeğin üzerine yazılmaz.
    if hedef.exists():
        hedef.unlink()
    gecici.replace(hedef)
    return hedef


def eskileri_sil(gun: int = SAKLAMA_GUN, dizin: Path | None = None) -> list[Path]:
    """``gun`` günden eski yedekleri siler; en yeni birkaç tanesine dokunmaz."""
    dizin = dizin or YEDEK_DIZINI
    if not dizin.is_dir():
        return []
    dosyalar = sorted(dizin.glob("saha-*.db"), key=lambda p: p.name, reverse=True)
    sinir = ayarlar.bugun() - dt.timedelta(days=gun)
    silinen: list[Path] = []
    for i, dosya in enumerate(dosyalar):
        if i < EN_AZ_DOSYA:
            continue
        try:
            tarih = dt.date.fromisoformat(dosya.stem.removeprefix("saha-"))
        except ValueError:
            continue
        if tarih < sinir:
            dosya.unlink(missing_ok=True)
            silinen.append(dosya)
    return silinen


def geri_yukleme_adaylari(kaynak: Path | None = None) -> list[Path]:
    """Göç yedekleri (``yedek/goc/``) ve günlük yedekler (``yedek/``), en yenisi önce."""
    kaynak = Path(kaynak or db.db_yolu())
    adaylar = list((kaynak.parent / "yedek" / "goc").glob("saha-*.db"))
    adaylar += list((kaynak.parent / "yedek").glob("saha-*.db"))
    return sorted(adaylar, key=lambda p: p.stat().st_mtime, reverse=True)


def geri_yukle(secilen: Path, kaynak: Path | None = None) -> dict:
    """Seçilen yedeği canlı dosyanın yerine koyar (spec §1.13 GERI_YUKLE.bat).

    Mevcut dosya SİLİNMEZ: ``saha-hatali-<zaman>.db`` (ve -wal/-shm) adıyla kenara konur.
    Kopya yazılabilir yapılır ve ``integrity_check`` çalıştırılır. Sunucu kapalıyken çağrılır.
    """
    kaynak = Path(kaynak or db.db_yolu())
    secilen = Path(secilen)
    if not secilen.exists():
        raise YedekHatasi(f"Yedek bulunamadı: {secilen}")
    kenar = None
    damga = _damga()
    if kaynak.exists():
        kenar = kaynak.with_name(f"saha-hatali-{damga}.db")
        os.replace(kaynak, kenar)
        for ek in ("-wal", "-shm"):
            yan = Path(str(kaynak) + ek)
            if yan.exists():
                os.replace(yan, Path(str(kenar) + ek))
    gecici = kaynak.with_name(kaynak.name + ".geri-yukleniyor")
    shutil.copyfile(secilen, gecici)
    os.chmod(gecici, stat.S_IREAD | stat.S_IWRITE)
    c = sqlite3.connect(gecici)
    try:
        butunluk = c.execute("PRAGMA integrity_check").fetchone()[0]
        surum = int(c.execute("PRAGMA user_version").fetchone()[0])
    finally:
        c.close()
    if butunluk != "ok":
        gecici.unlink(missing_ok=True)
        if kenar is not None:          # bozuk yedek yerine eski dosyayı geri koy
            os.replace(kenar, kaynak)
        raise YedekHatasi(f"Seçilen yedek bütünlük denetiminden geçmedi ({butunluk}); hiçbir şey değişmedi.")
    os.replace(gecici, kaynak)
    return {"yuklenen": str(secilen), "kenara_konan": str(kenar) if kenar else None, "surum": surum}


def geri_yukle_etkilesimli() -> int:
    """GERI_YUKLE.bat: listeler, sorar, geri yükler. Sunucu açıksa hiçbir şey yapmaz."""
    from .sunucu import port_dolu_mu

    if port_dolu_mu(8080):
        print("Sunucu açık. Önce saha\\DURDUR.bat, sonra yeniden GERI_YUKLE.bat.")
        return 2
    adaylar = geri_yukleme_adaylari()
    if not adaylar:
        print("Geri yüklenecek yedek bulunamadı (saha\\yedek\\ ve saha\\yedek\\goc\\ boş).")
        return 1
    print("\nYedekler (en yenisi önce):\n")
    for i, d in enumerate(adaylar[:30], 1):
        zaman = dt.datetime.fromtimestamp(d.stat().st_mtime).strftime("%d.%m.%Y %H:%M")
        tur = "göç öncesi" if d.parent.name == "goc" else "günlük"
        print(f"  {i:>2}. {zaman}  {tur:<10}  {d.name:<44} {_boyut(d.stat().st_size):>9}")
    try:
        cevap = input("\nHangi yedek geri yüklensin? Numara yazın (boş = vazgeç): ").strip()
    except EOFError:
        cevap = ""
    if not cevap:
        print("Vazgeçildi — hiçbir şey değişmedi.")
        return 0
    if not cevap.isdigit() or not 1 <= int(cevap) <= min(30, len(adaylar)):
        print("Geçersiz numara — hiçbir şey değişmedi.")
        return 1
    try:
        sonuc = geri_yukle(adaylar[int(cevap) - 1])
    except YedekHatasi as exc:
        print(exc.mesaj)
        return 1
    if sonuc["kenara_konan"]:
        print(f"Eski dosya silinmedi, kenara kondu: {Path(sonuc['kenara_konan']).name}")
    print(f"Geri yüklendi (şema v{sonuc['surum']}). Bütünlük denetimi: tamam.")
    print("Önceki sürüm klasöründen BASLAT.bat ile açın.")
    return 0


def listele(dizin: Path | None = None) -> None:
    dizin = dizin or YEDEK_DIZINI
    dosyalar = sorted(dizin.glob("saha-*.db"), reverse=True) if dizin.is_dir() else []
    if not dosyalar:
        print(f"Henüz yedek yok. Klasör: {dizin}")
        return
    toplam = sum(d.stat().st_size for d in dosyalar)
    print(f"{dizin}  —  {len(dosyalar)} yedek, toplam {_boyut(toplam)}\n")
    for d in dosyalar:
        print(f"  {d.name:<24} {_boyut(d.stat().st_size):>10}")


def main(argv: list[str] | None = None) -> int:
    ayarlar.konsolu_hazirla()
    ayrac = argparse.ArgumentParser(description="Saha Sistemi veritabanı yedeği")
    ayrac.add_argument("--gun", type=int, default=SAKLAMA_GUN, help="Kaç gün saklansın (varsayılan 30)")
    ayrac.add_argument("--liste", action="store_true", help="Yedekleri listeler, yedek almaz")
    ayrac.add_argument("--dizin", help="Yedek klasörü (varsayılan saha/yedek)")
    ayrac.add_argument("--geri-yukle", action="store_true", dest="geri_yukle",
                       help="Yedeklerden birini geri yükler (sunucu kapalıyken; GERI_YUKLE.bat)")
    a = ayrac.parse_args(argv)
    dizin = Path(a.dizin) if a.dizin else None

    if a.geri_yukle:
        return geri_yukle_etkilesimli()
    if a.liste:
        listele(dizin)
        return 0

    hedef = yedek_al(dizin)
    silinen = eskileri_sil(max(1, a.gun), dizin)
    print(f"Yedek alındı: {hedef}  ({_boyut(hedef.stat().st_size)})")
    if silinen:
        print(f"{len(silinen)} eski yedek silindi (en eski: {silinen[-1].name}).")
    # v2 saklama: göç/aktarım yedekleri ve (sürüm uyuyorsa) kapanmış işlerin müşteri alanları.
    saklama = saklama_uygula(db.db_yolu())
    if saklama["aktarim_silinen"] or saklama["goc_silinen"]:
        print(f"Saklama: {saklama['aktarim_silinen']} aktarım, {saklama['goc_silinen']} göç yedeği silindi.")
    _is_saklamasi()
    return 0


def _is_saklamasi() -> None:
    """``operasyon.v2.saklama.uygula`` (19:30 görevi, spec §1.12). Sürüm uymuyorsa DOKUNMAZ."""
    try:
        from operasyon.v2 import saklama
    except ImportError:
        return
    from . import goc

    conn = db.baglan()
    try:
        try:
            goc.surum_dogrula(conn)
        except goc.SurumUyumsuz:
            return
        sonuc = saklama.uygula(conn, ayarlar.simdi())
        conn.commit()
        if sonuc:
            print("Müşteri bilgisi saklaması uygulandı: " + ", ".join(f"{k} {v}" for k, v in sonuc.items()))
    except Exception as exc:  # yedek alındı; saklama hatası yedeği geçersiz kılmaz
        print(f"UYARI: saklama kuralı uygulanamadı ({exc}).")
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
