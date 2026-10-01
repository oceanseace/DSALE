"""KVKK saklama süreleri (spec §1.12). Sunucu açılışında, her aktarımdan sonra ve 19:30 yedeğinden sonra koşar.

| Veri                                   | Süre                               |
| müşteri adı, adres, telefon            | kapanış + ``pii_saklama_gun`` (30) → NULL |
| müşteri no                             | kapanış + 30 gün → NULL; HMAC özeti kalır (tekrar arıza bozulmaz) |
| ham BOSS dosyası (veri/gelen/<sha>.xlsx) | ``ham_saklama_gun`` (7) → silinir |
| fark dosyaları (veri/gelen/<id>.fark.json) | karar verilince ya da 1 gün → silinir |
Olay defterleri kişisel veri DEĞERİ içermez; süresiz kalır. ``son_yukleme.pkl`` açılmaz, silinmez.
"""
from __future__ import annotations

import datetime as dt
import sqlite3
import time

from . import sozluk, zaman
from .islem import islem


def _gun(conn, anahtar, varsayilan) -> int:
    r = conn.execute("SELECT deger FROM ayar WHERE anahtar=?", (anahtar,)).fetchone()
    try:
        return max(1, int(r[0])) if r and r[0] else varsayilan
    except ValueError:
        return varsayilan


def uygula(conn: sqlite3.Connection, simdi: dt.datetime | None = None) -> dict:
    simdi = simdi or zaman.simdi()
    pii = _gun(conn, "pii_saklama_gun", 30)
    ham = _gun(conn, "ham_saklama_gun", 7)
    sinir = zaman.metin(simdi - dt.timedelta(days=pii))
    with islem(conn):
        n = conn.execute(
            "UPDATE is_emri SET musteri_adi=NULL, adres=NULL, musteri_tel=NULL, musteri_no=NULL "
            "WHERE durum='kapandi' AND kapanis IS NOT NULL AND kapanis < ? AND "
            "(musteri_adi IS NOT NULL OR adres IS NOT NULL OR musteri_tel IS NOT NULL OR musteri_no IS NOT NULL)",
            (sinir,)).rowcount
    silinen_ham = silinen_fark = 0
    gelen = sozluk.veri_dizini() / "gelen"
    if gelen.exists():
        esik = time.time() - ham * 86400
        bir_gun = time.time() - 86400
        karar = {str(r[0]) for r in conn.execute("SELECT id FROM ie_aktarim WHERE durum IN ('uygulandi','vazgecildi','hata')")}
        bekleyen_sha = {r[0] for r in conn.execute("SELECT dosya_sha256 FROM ie_aktarim WHERE durum='onay_bekliyor'")}
        for p in gelen.iterdir():
            try:
                if p.name.endswith(".fark.json"):
                    aid = p.name.split(".", 1)[0]
                    if aid in karar or p.stat().st_mtime < bir_gun:
                        p.unlink()
                        silinen_fark += 1
                elif p.suffix == ".xlsx" and p.stem not in bekleyen_sha and p.stat().st_mtime < esik:
                    p.unlink()
                    silinen_ham += 1
            except OSError:
                continue
    return {"musteri_temizlenen": n, "ham_silinen": silinen_ham, "fark_silinen": silinen_fark}


def metin(conn: sqlite3.Connection) -> str:
    """Takip → Sistem kartındaki tek satır."""
    pii = _gun(conn, "pii_saklama_gun", 30)
    ham = _gun(conn, "ham_saklama_gun", 7)
    return (f"Müşteri bilgisi kapanıştan {pii} gün sonra silinir (numaranın yalnız özeti kalır); "
            f"ham rapor {ham} gün, günlük yedekler 30 gün tutulur.")
