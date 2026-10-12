"""Tek seferlik temizlikler (sahibin kararları, 2026-10). Sunucu açılışında (``operasyon/v2/api.py`` → ``_yasam``)
sırayla koşar; her biri kendi ``ayar`` anahtarı yazılınca bir daha koşmaz (idempotent; sonradan uygulamada girilen
ticket'lara asla dokunmaz).

1. ``calistir`` — ticket defterini sıfırlar (``ayar.temizlik_ticket_sifir``). Defterdeki ticket'lar Excel TICKET
   sayfasından aktarılmıştı; operasyon hepsini uygulamada baştan girer. Kapsam: ``tur`` boş olan ticket'lar.
2. ``ps26_calistir`` — PS26'dan aktarılmış her şeyi siler (``ayar.temizlik_ps26_sil``); PS26 aktarımı kaldırıldı.
   Kapsam: GÜZERGAH satırları (``tur='guzergah'``), Excel/PS26'dan gelen bütün ticket'lar (``kaynak='excel'`` ya da
   ``aktarim_anahtari`` dolu), PS26 ALTYAPI satırları (``altyapi_bekleyen.aktarim_anahtari LIKE 'ps26:%'``) ve
   ``ayar.ps26_*``. Bu ticket'lara bağlı "Altyapı bekliyor" işler bekliyor'a (öbeksizse Kontrol'e) döner.
3. ``silinenler_calistir`` — eski YUMUŞAK silmeden kalanlar (``ticket_silme``): o ticket'lar şimdiki silmeyle aynı
   biçimde KALICI silinir (``ticket.toplu_sil`` gibi: işler ayrılır, bütün ticket satırları + fotoğraflar gider) ve
   ``ticket_silme`` tablosu kaldırılır. Tablo yoksa yapılmıştır (ayar anahtarı yok, iz yok); canlı/geliştirme her
   veride koşar. Yedek kuralı aşağıdakiyle aynı; fotoğraflar TAŞINMAZ, silinir (sahibin kararı: iz kalmasın).

Her birinin sırası:
1. Doğrulanmış tam yedek ``<db klasörü>/yedek/temizlik/<ad>-<zaman>.db`` (saklama kuralı bu klasörü silmez).
   Yedek alınamazsa HİÇBİR ŞEY silinmez (istisna yukarı çıkar, bir sonraki açılışta yeniden dener).
2. Tek işlemde (hata → ROLLBACK): işlerin ``ticket_id`` bağı boşalır · ``ticket_ek`` · ``ticket_gecmis`` · ``ticket``.
   Kimlikler AUTOINCREMENT'tir: yeni ticket eski numarayı (ve eski fotoğraf klasörünü) almaz.
3. Fotoğraf klasörleri ``ek/ticket/<id>`` yedek klasörüne TAŞINIR (silinmez).
"""
from __future__ import annotations

import json
import logging
import shutil
import sqlite3
from pathlib import Path

from . import ayarlar

ANAHTAR = "temizlik_ticket_sifir"
_KOSUL = "COALESCE(tur,'') <> 'guzergah'"
ANAHTAR_PS26 = "temizlik_ps26_sil"
_KOSUL_PS26 = "(COALESCE(tur,'') = 'guzergah' OR kaynak = 'excel' OR aktarim_anahtari IS NOT NULL)"
_log = logging.getLogger("saha.ticket_temizlik")


def _tablo(conn: sqlite3.Connection, ad: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (ad,)).fetchone() is not None


def _yapildi(conn: sqlite3.Connection, anahtar: str) -> bool:
    return _tablo(conn, "ayar") and conn.execute("SELECT 1 FROM ayar WHERE anahtar=?", (anahtar,)).fetchone() is not None


def yapildi_mi(conn: sqlite3.Connection) -> bool:
    return _yapildi(conn, ANAHTAR)


def ps26_yapildi_mi(conn: sqlite3.Connection) -> bool:
    return _yapildi(conn, ANAHTAR_PS26)


def _yedek(db_yolu: Path, ad: str = "saha-ticket-sifirlama") -> Path:
    from . import yedekle

    hedef = Path(db_yolu).parent / "yedek" / "temizlik" / f"{ad}-{yedekle._damga()}.db"
    return yedekle._dogrulanmis_kopya(Path(db_yolu), hedef, tam=True)


def _fotolari_tasi(ek_kok: Path | None, db_yolu: Path | None, idler: list[int]) -> int:
    if ek_kok is None or not idler:
        return 0
    kaynak = Path(ek_kok) / "ticket"
    tasinan = 0
    if kaynak.is_dir():
        hedef = Path(db_yolu or ek_kok).parent / "yedek" / "temizlik" / "ticket_ek"
        for tid in idler:
            d = kaynak / str(tid)
            if d.is_dir():
                hedef.mkdir(parents=True, exist_ok=True)
                yeni = hedef / str(tid)
                if yeni.exists():
                    yeni = hedef / f"{tid}-{ayarlar.simdi():%Y%m%d%H%M%S}"
                shutil.move(str(d), str(yeni))
                tasinan += 1
    return tasinan


def _sil(conn: sqlite3.Connection, db_yolu: Path | None, ek_kok: Path | None, *, anahtar: str, kosul: str,
         yedek_adi: str, ps26: bool = False) -> dict | None:
    if not _tablo(conn, "ayar") or not _tablo(conn, "ticket") or _yapildi(conn, anahtar):
        return None
    idler = [int(r[0]) for r in conn.execute(f"SELECT id FROM ticket WHERE {kosul}")]
    altyapi = (conn.execute("SELECT COUNT(*) FROM altyapi_bekleyen WHERE aktarim_anahtari LIKE 'ps26:%'").fetchone()[0]
               if ps26 and _tablo(conn, "altyapi_bekleyen") else 0)
    s: dict = {"yedek": None, "ticket": len(idler)}
    if (idler or altyapi) and db_yolu is not None:
        s["yedek"] = str(_yedek(db_yolu, yedek_adi))       # YedekHatasi → yukarı; hiçbir şey silinmez
    alt = f"SELECT id FROM ticket WHERE {kosul}"
    if conn.in_transaction:
        conn.commit()
    conn.execute("BEGIN IMMEDIATE")
    try:
        if _tablo(conn, "is_emri"):
            if ps26:
                # Silinen ticket'ı bekleyen işler havuza döner (öbeksiz iş Kontrol'e: triyaj nedeni duruyorsa).
                s["altyapidan_donen_is"] = conn.execute(
                    "UPDATE is_emri SET durum=CASE WHEN triyaj_nedeni IS NOT NULL THEN 'triyaj' ELSE 'bekliyor' END, "
                    f"durum_zamani=?, surum=surum+1 WHERE durum='altyapi' AND ticket_id IN ({alt})",
                    (ayarlar.zaman_metni(),)).rowcount
            s["is_bagi_bosalan"] = conn.execute(
                f"UPDATE is_emri SET ticket_id=NULL WHERE ticket_id IN ({alt})").rowcount
        for t in ("ticket_ek", "ticket_gecmis"):
            if _tablo(conn, t):
                s[t] = conn.execute(f"DELETE FROM {t} WHERE ticket_id IN ({alt})").rowcount
        conn.execute(f"DELETE FROM ticket WHERE {kosul}")
        if ps26:
            if _tablo(conn, "altyapi_bekleyen"):
                s["altyapi_bekleyen"] = conn.execute(
                    "DELETE FROM altyapi_bekleyen WHERE aktarim_anahtari LIKE 'ps26:%'").rowcount
            conn.execute("DELETE FROM ayar WHERE anahtar IN ('ps26_klasoru', 'ps26_son_aktarim')")
        conn.execute("INSERT INTO ayar(anahtar, deger) VALUES(?, ?) ON CONFLICT(anahtar) DO UPDATE SET "
                     "deger=excluded.deger",
                     (anahtar, json.dumps({"zaman": ayarlar.zaman_metni(), **s}, ensure_ascii=False)))
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    if ek_kok is not None and idler:
        s["foto_klasoru_tasinan"] = _fotolari_tasi(ek_kok, db_yolu, idler)
    return s


def calistir(conn: sqlite3.Connection, db_yolu: Path | None, ek_kok: Path | None = None) -> dict | None:
    """Defteri sıfırlar; yapılmışsa (ya da tablolar yoksa) None. Dönüş: sayılar + yedek yolu (kişisel veri yok)."""
    s = _sil(conn, db_yolu, ek_kok, anahtar=ANAHTAR, kosul=_KOSUL, yedek_adi="saha-ticket-sifirlama")
    if s is not None:
        _log.warning("Ticket defteri sıfırlandı: %s", s)
    return s


def ps26_calistir(conn: sqlite3.Connection, db_yolu: Path | None, ek_kok: Path | None = None) -> dict | None:
    """PS26'dan aktarılmış her şeyi siler; yapılmışsa (ya da tablolar yoksa) None. Dönüş: sayılar + yedek yolu."""
    s = _sil(conn, db_yolu, ek_kok, anahtar=ANAHTAR_PS26, kosul=_KOSUL_PS26, yedek_adi="saha-ps26-silme", ps26=True)
    if s is not None:
        _log.warning("PS26 verisi silindi: %s", s)
    return s


def silinenler_calistir(conn: sqlite3.Connection, db_yolu: Path | None, ek_kok: Path | None = None) -> dict | None:
    """Eski yumuşak silinmiş ticket'ları kalıcı siler, ``ticket_silme``'yi kaldırır; tablo yoksa None."""
    from . import ticket as tk

    if not _tablo(conn, "ticket_silme"):
        return None
    idler = [int(r[0]) for r in conn.execute(
        "SELECT s.ticket_id FROM ticket_silme s JOIN ticket t ON t.id=s.ticket_id ORDER BY s.ticket_id")]         if _tablo(conn, "ticket") else []
    s: dict = {"yedek": None, "ticket": len(idler)}
    if idler and db_yolu is not None:
        s["yedek"] = str(_yedek(db_yolu, "saha-ticket-silinenler"))   # YedekHatasi → yukarı; hiçbir şey silinmez
    if conn.in_transaction:
        conn.commit()
    conn.execute("BEGIN IMMEDIATE")
    try:
        ayrilan = 0
        for tid in idler:
            ayrilan += len(tk._ayir(conn, tid, None))
            tk._satirlari_sil(conn, tid)
        conn.execute("DROP TABLE ticket_silme")
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    s["ayrilan_is"] = ayrilan
    s["foto_klasoru_silinen"] = tk.fotolari_sil(idler, ek_kok) if ek_kok is not None else 0
    return s


def acilista_calistir() -> dict | None:
    """Sunucu açılışı: yalnız canlı veride (ya da ``SAHA_TICKET_SIFIRLAMA=1``); ``=0`` kapatır.

    Önce defter sıfırlama, sonra PS26 silme. Dönüş: yapılanların sayıları (``{"ps26": {...}}`` iç içe) ya da None.
    """
    import os
    import sys

    secim = (os.environ.get("SAHA_TICKET_SIFIRLAMA") or "").strip()
    if secim == "0":
        return None
    ana = sys.modules.get("saha.api")
    if ana is not None and getattr(ana, "GUNCELLEME_BEKLIYOR", False):
        return None
    from . import db, ek_dosya
    yol = db.db_yolu()
    if not yol.exists():
        return None
    import yollar
    canli = secim == "1" or yollar.canli_veri_mi()
    conn = db.baglan(yol)
    try:
        sonuc = calistir(conn, yol, ek_dosya.ek_kok()) if canli else None
        ps26 = ps26_calistir(conn, yol, ek_dosya.ek_kok()) if canli else None
        silinen = silinenler_calistir(conn, yol, ek_dosya.ek_kok())   # her veride (eski yumuşak silme kalıntısı)
    finally:
        conn.close()
    if silinen is not None:
        _log.warning("Yumuşak silinmiş ticket'lar kalıcı silindi: %s", silinen)
    if ps26 is None and silinen is None:
        return sonuc
    out = dict(sonuc or {})
    if ps26 is not None:
        out["ps26"] = ps26
    if silinen is not None:
        out["silinenler"] = silinen
    return out
