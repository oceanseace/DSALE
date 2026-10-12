"""Tek seferlik temizlik: "tek iş havuzu" düzenine geçiş (sahibin kararı, 2026-10).

Sunucu açılışında (``api._yasam``) bir kez koşar; ``ayar.temizlik_tek_havuz`` yazılınca bir daha koşmaz
(idempotent). Sonuç canlı olay akışına (``/api/boss/akis``, ``adim='temizlik'``) yazılır.

Sıra:
1. Doğrulanmış güvenlik yedeği (``aktarim.aktarim_yedegi``: salt okunur kaynak + backup API + bütünlük denetimi).
   Yedek alınamazsa HİÇBİR ŞEY silinmez.
2. Tek işlemde (hata → ROLLBACK):
   - bütün öbekler (``obek_mahalle``, ``obek``; işlerin öbek bağları boşalır; öbeksiz iş Kontrol'den çıkar).
     ``obek_olay`` değiştirilemez denetim kaydıdır, kalır.
   - Administrator DIŞINDAKİ bütün kullanıcılar (görev/yetkinlik bağlarıyla); işlerdeki atamaları boşalır.
     Teknisyenler bundan sonra yalnız BOSS ekip listesinden gelir (``kisi.boss_ekipleri_esitle``).
   - eski dağıtım kuralları ve dağıtım tablosu, eski Excel (Teknik Task Detay Raporu) aktarım geçmişi.
   - BOSS iç kimliğinden türetilmiş (9 haneli olmayan) açık iş numaraları kapanır; ``boss_iz`` boşalır → sonraki
     eşitleme TAM gönderilir ve işler gerçek 9 haneli BOSS task no'suyla yeniden gelir.
3. ``obekler.json`` (varsa) yedek klasörüne TAŞINIR (silinmez).
Administrator hesabı bulunamazsa temizlik koşmaz (kimse dışarıda kalmasın).
"""
from __future__ import annotations

import json
import logging
import shutil
import sqlite3
from pathlib import Path

from . import zaman
from .islem import islem

ANAHTAR = "temizlik_tek_havuz"
_log = logging.getLogger("operasyon.temizlik")


def _tablo(conn, ad: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (ad,)).fetchone() is not None


def yapildi_mi(conn: sqlite3.Connection) -> bool:
    return conn.execute("SELECT 1 FROM ayar WHERE anahtar=?", (ANAHTAR,)).fetchone() is not None


def _administrator_id(conn) -> int | None:
    from saha import guvenlik, yetki
    tel = guvenlik.telefon_duzelt(str(yetki.administrator_ayari().get("telefon") or ""))
    if not tel:
        return None
    r = conn.execute("SELECT id FROM kullanici WHERE telefon=?", (tel,)).fetchone()
    return int(r[0]) if r else None


def calistir(conn: sqlite3.Connection, db_yolu: Path | None, obek_dosyasi: Path | None = None) -> dict | None:
    """Temizliği yapar; yapılmışsa None. Dönüş: sayılar + yedek yolu."""
    if not _tablo(conn, "ayar") or not _tablo(conn, "kullanici") or yapildi_mi(conn):
        return None
    admin = _administrator_id(conn)
    if admin is None:
        _log.warning("Tek havuz temizliği atlandı: Administrator hesabı bulunamadı.")
        return {"atlandi": "administrator_yok"}
    yedek = None
    if db_yolu is not None:
        from . import aktarim
        yedek = str(aktarim.aktarim_yedegi(Path(db_yolu)))      # hata → yukarı fırlar, hiçbir şey silinmez
    s: dict = {"yedek": yedek, "administrator_id": admin}
    with islem(conn):
        if _tablo(conn, "is_emri"):
            s["obeksiz_kontrolden_cikan"] = conn.execute(
                "UPDATE is_emri SET triyaj_nedeni=NULL, durum='bekliyor' WHERE durum='triyaj' "
                "AND triyaj_nedeni='obeksiz'").rowcount
            conn.execute("UPDATE is_emri SET triyaj_nedeni=NULL WHERE triyaj_nedeni='obeksiz'")
            conn.execute("UPDATE is_emri SET obek_id=NULL, obek_elle_id=NULL "
                         "WHERE obek_id IS NOT NULL OR obek_elle_id IS NOT NULL")
            s["atama_bosalan"] = conn.execute(
                "UPDATE is_emri SET atanan_id=NULL, atama_kaynagi=NULL, oneri_teknik_id=NULL "
                "WHERE atanan_id IS NOT NULL AND atanan_id<>?", (admin,)).rowcount
            # BOSS iç kimliğinden türetilmiş geçici numaralar: açık olanlar kapanır (gerçek numarayla yeniden gelir)
            s["gecici_no_kapanan"] = conn.execute(
                "UPDATE is_emri SET durum='kapandi', durum_zamani=?, kapanis=?, kapanis_nedeni='yeniden_numaralandi' "
                "WHERE kaynak='boss' AND durum NOT IN ('kapandi','cozuldu') AND length(is_no) <> 9",
                (zaman.metin(), zaman.metin())).rowcount
        for t in ("obek_mahalle", "obek"):
            if _tablo(conn, t):
                s[t] = conn.execute(f"DELETE FROM {t}").rowcount
        for t in ("kullanici_gorev", "kullanici_yetkinlik"):
            if _tablo(conn, t):
                conn.execute(f"DELETE FROM {t} WHERE kullanici_id<>?", (admin,))
        s["kullanici_silinen"] = conn.execute("DELETE FROM kullanici WHERE id<>?", (admin,)).rowcount
        conn.execute("UPDATE kullanici SET boss_ekip=NULL WHERE id=?", (admin,))
        for t in ("dagitim_kural", "dagitim_is", "boss_iz"):
            if _tablo(conn, t):
                s[t] = conn.execute(f"DELETE FROM {t}").rowcount
        if _tablo(conn, "ie_aktarim"):
            # değiştirilemez denetim kayıtlarının (is_emri_olay …) gösterdiği aktarımlar kalır; gerisi silinir
            atif = []
            for (t,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
                for fk in conn.execute(f"PRAGMA foreign_key_list({t})").fetchall():
                    if fk[2] == "ie_aktarim":
                        atif.append(f"SELECT {fk[3]} FROM {t} WHERE {fk[3]} IS NOT NULL")
            haric = f" AND id NOT IN ({' UNION '.join(atif)})" if atif else ""
            s["excel_aktarim"] = conn.execute(f"DELETE FROM ie_aktarim WHERE kaynak<>'boss_canli'{haric}").rowcount
        conn.execute("DELETE FROM ayar WHERE anahtar IN ('filtre_istisnalari','dagitim_sutunlar')")
        conn.execute("INSERT INTO ayar(anahtar, deger) VALUES(?, ?) ON CONFLICT(anahtar) DO UPDATE SET "
                     "deger=excluded.deger", (ANAHTAR, json.dumps({"zaman": zaman.metin(), **s}, ensure_ascii=False)))
    if obek_dosyasi is not None and Path(obek_dosyasi).exists():
        hedef = Path(obek_dosyasi).parent / "veri" / "obek_yedek"
        hedef.mkdir(parents=True, exist_ok=True)
        yeni = hedef / f"obekler-temizlik-{zaman.simdi():%Y%m%d-%H%M%S}.json"
        shutil.move(str(obek_dosyasi), str(yeni))
        s["obekler_json"] = str(yeni)
    _log.warning("Tek havuz temizliği yapıldı: %s", s)
    return s
