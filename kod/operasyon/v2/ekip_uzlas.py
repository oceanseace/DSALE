"""Ekip ataması: BOSS kesin kaynak (09.10).

BOSS'ta bir ekip yalnız randevulu türü durumlarda iş tutar; askı / merkeze / ertelendi ekibi işten alır. Uygulama ise
kendi atamasını (``atanan_id``; geçmiş BOSS atama yazmalarından) tutuyordu — TASKS "Ekip" sütunu ve MAP, BOSS'ta
ekibi boş olan işleri eski kişide gösteriyordu. Kural (her BOSS işinde):
- ``boss_ekip`` boş → uygulama ataması kalkar (``atanan_id``, ``sira``; BOSS'ta randevu yoksa bizim randevu da),
  olay notu "BOSS'ta ekipten alındı (<BOSS durumu>)";
- ``boss_ekip`` dolu → atama = o BOSS ekibine eşli teknisyen (``kisi.boss_ekip_haritasi``); eşli kişi yoksa atama
  kalkar ve "Ekip" sütunu BOSS ekip adını gösterir (arayüz: ``atanan?.ad || boss_ekip``).
İstisna (``korunanlar``): uygulamadan yapılmış ve sonucu henüz gelmemiş atama yazması (boss_yazma 'bekliyor' /
'gonderiliyor' / 'eksik'; sonucu geç gelebilecek 'hata(sonuc_gelmedi)'; BOSS görüntüsünden yeni 'gonderildi') ve
az önce yapılmış atama (kuyruğa yazılmadan önceki an) BOZULMAZ — sonucu gelince bir sonraki eşitlemede uzlaşır.

Çağrılar: her eşitlemenin sonunda ``boss.esitle`` → ``uzlas`` (bütün açık BOSS işleri; idempotent) ve sunucu
açılışında bir kez ``acilista_calistir`` (doğrulanmış yedekle; ``ayar.boss_ekip_uzlasma``).
"""
from __future__ import annotations

import datetime as dt
import json
import sqlite3
from pathlib import Path

from operasyon import is_emri as ie

from . import akis, kisi, zaman
from .islem import islem

AYAR = "boss_ekip_uzlasma"             # tek seferlik açılış uzlaşmasının kaydı
KORUMA_SN = 30 * 60                    # sonucu gelmiş/gelmemiş yazma en çok bu kadar korunur
YENI_ATAMA_SN = 90                     # ata() işlendi ama yazma henüz kuyrukta değil (aynı an yarışı)
_ILERI = ("atandi", "yolda", "sahada")


def _tablo_var(conn, ad: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (ad,)).fetchone() is not None


def korunanlar(conn: sqlite3.Connection, simdi: str | None = None) -> set[str]:
    """Uygulamadan yapılmış, BOSS sonucu henüz kesinleşmemiş atamaların is_no'ları (bunlar geri alınmaz)."""
    an = zaman.oku(simdi) if simdi else zaman.simdi()
    sinir = zaman.metin(an - dt.timedelta(seconds=KORUMA_SN))
    out: set[str] = set()
    son_yazma: dict[str, str] = {}                        # is_no → son atama yazmasının oluşturulma anı
    if _tablo_var(conn, "boss_yazma"):
        iz = {}
        if _tablo_var(conn, "boss_iz"):
            iz = {r[0]: r[1] for r in conn.execute("SELECT task_no, gorulme FROM boss_iz")}
        for r in conn.execute(
                "SELECT y.is_no, y.task_no, y.durum, y.olusturma, y.guncelleme, y.sonuc FROM boss_yazma y JOIN "
                "(SELECT is_no, MAX(id) AS id FROM boss_yazma WHERE tur='atama' GROUP BY is_no) s ON s.id=y.id"):
            d = r["durum"]
            son_yazma[r["is_no"]] = r["olusturma"] or ""
            if d in ("bekliyor", "gonderiliyor", "eksik"):
                out.add(r["is_no"])
            elif d == "hata" and "sonuc_gelmedi" in (r["sonuc"] or "") and (r["guncelleme"] or "") >= sinir:
                out.add(r["is_no"])                       # sonucu geç gelebilir (boss_yazma.sonuc_al)
            elif d == "gonderildi" and (r["guncelleme"] or "") >= sinir \
                    and (r["guncelleme"] or "") >= (iz.get(r["task_no"]) or ""):
                out.add(r["is_no"])                       # BOSS görüntüsü yazmadan eski: BOSS henüz göstermedi
    yeni = zaman.metin(an - dt.timedelta(seconds=YENI_ATAMA_SN))
    for no, an_ in conn.execute("SELECT is_no, atama_zamani FROM is_emri WHERE atanan_id IS NOT NULL AND "
                                "atama_zamani >= ? AND COALESCE(atama_kaynagi,'') <> 'boss'", (yeni,)):
        if son_yazma.get(no, "") < an_:                   # atama yazıldı, yazması henüz kuyrukta değil
            out.add(no)
    return out


def _bekleyen_ayikla(deger, cikar) -> str | None:
    parca = [p for p in (deger or "").split(",") if p and p not in cikar]
    return ",".join(parca) or None


def adaylar(conn: sqlite3.Connection, simdi: str | None = None) -> list[tuple[sqlite3.Row, int | None]]:
    """(satır, hedef teknisyen) — uygulama ataması BOSS ekibinden farklı ve korunmayan açık BOSS işleri."""
    h = kisi.boss_ekip_haritasi(conn)
    koru = korunanlar(conn, simdi)
    out = []
    for r in conn.execute("SELECT * FROM is_emri WHERE kaynak='boss' AND boss_task_no IS NOT NULL "
                          "AND durum NOT IN ('cozuldu','kapandi')"):
        ekip = str(r["boss_ekip"] or "").strip()
        hedef = h.get(ie.anahtar(ekip)) if ekip else None
        if hedef == r["atanan_id"] or r["is_no"] in koru:
            continue
        if hedef is not None and r["durum"] == "altyapi":
            continue                                       # altyapı engeli: teknisyen gönderilmez
        out.append((r, hedef))
    return out


def uzlas(conn: sqlite3.Connection, simdi: str | None = None, aktarim_id: int | None = None) -> dict:
    """Bütün açık BOSS işlerinde atamayı BOSS ekibine uydurur. Tek işlem; idempotent. Dönüş: sayılar."""
    simdi = simdi or zaman.metin()
    kisiler = kisi.kisiler(conn)
    sayi = {"alinan": 0, "atanan": 0, "eslesmeyen": 0}
    with islem(conn):
        for r, hedef in adaylar(conn, simdi):
            ekip = str(r["boss_ekip"] or "").strip()
            onceki = (kisiler.get(r["atanan_id"]) or {}).get("ad") if r["atanan_id"] else None
            durum = r["durum"]
            a: dict = {}
            if hedef is None:
                a.update(atanan_id=None, atama_kaynagi=None, sira=None, teknik_gordu=None)
                if not r["boss_randevu_bas"]:
                    a.update(randevu_bas=None, randevu_bit=None, randevu_teyitli=0)
                if durum in _ILERI:
                    kalan = a.get("randevu_bas", r["randevu_bas"])
                    durum = "randevulu" if kalan else ("triyaj" if r["triyaj_nedeni"] else "bekliyor")
                    a.update(yolda_zamani=None, sahada_zamani=None)
                a["boss_bekleyen"] = _bekleyen_ayikla(r["boss_bekleyen"], ("ekip", "randevu"))
                if ekip:
                    notu = f"BOSS'ta ekip: {ekip} (uygulamada eşli kişi yok)"
                    sayi["eslesmeyen"] += 1
                else:
                    notu = f"BOSS'ta ekipten alındı ({r['boss_durum'] or '—'})"
                    sayi["alinan"] += 1
            else:
                a.update(atanan_id=hedef, atama_kaynagi="boss", atama_zamani=simdi,
                         ilk_atama_zamani=r["ilk_atama_zamani"] or simdi, teknik_gordu=None, sira=None,
                         oneri_teknik_id=None, oneri_bas=None, oneri_bit=None, oneri_neden=None)
                if durum in akis.ATANMADI:
                    durum = "atandi"
                a["boss_bekleyen"] = _bekleyen_ayikla(r["boss_bekleyen"], ("ekip",))
                notu = f"BOSS'ta ekip: {ekip}"
                sayi["atanan"] += 1
            if onceki:
                notu += f" · önceki: {onceki}"
            a["durum"] = durum
            if durum != r["durum"]:
                a["durum_zamani"] = simdi
            a["guncelleme"] = simdi
            set_ = ", ".join(f"{k}=?" for k in a)
            conn.execute(f"UPDATE is_emri SET {set_}, surum=surum+1 WHERE is_no=?", (*a.values(), r["is_no"]))
            eski = {k: r[k] for k in a if k not in ("guncelleme", "durum_zamani") and r[k] != a[k]}
            yeni = {k: a[k] for k in eski}
            yeni["_surum"] = r["surum"] + 1
            conn.execute("INSERT INTO is_emri_olay (is_no, zaman, kayit_zamani, kullanici_id, kullanici_ad, tur, eski, "
                         "yeni, notu, aktarim_id) VALUES (?,?,?,NULL,NULL,'aktarim_degisti',?,?,?,?)",
                         (r["is_no"], simdi, simdi, json.dumps(eski, ensure_ascii=False),
                          json.dumps(yeni, ensure_ascii=False), notu, aktarim_id))
    sayi["toplam"] = sayi["alinan"] + sayi["atanan"] + sayi["eslesmeyen"]
    return sayi


def yapildi_mi(conn: sqlite3.Connection) -> bool:
    return conn.execute("SELECT 1 FROM ayar WHERE anahtar=?", (AYAR,)).fetchone() is not None


def calistir(conn: sqlite3.Connection, db_yolu: Path | None) -> dict | None:
    """Tek seferlik açılış uzlaşması; yapılmışsa None. Değişecek satır varsa ÖNCE doğrulanmış yedek alınır
    (``aktarim.aktarim_yedegi``: bütünlük + satır sayısı); yedek alınamazsa hiçbir şey değişmez (hata yukarı)."""
    from . import aktarim
    if yapildi_mi(conn):
        return None
    simdi = zaman.metin()
    yedek = None
    if adaylar(conn, simdi) and db_yolu is not None:
        yedek = str(aktarim.aktarim_yedegi(Path(db_yolu)))
    if not aktarim._KILIT.acquire(timeout=60):
        raise RuntimeError("aktarım sürüyor")
    try:
        s = uzlas(conn, simdi)
        with islem(conn):
            conn.execute("INSERT INTO ayar(anahtar, deger) VALUES(?,?) ON CONFLICT(anahtar) DO UPDATE SET "
                         "deger=excluded.deger", (AYAR, json.dumps({"zaman": simdi, **s, "yedek": yedek},
                                                                   ensure_ascii=False)))
    finally:
        aktarim._KILIT.release()
    return {**s, "yedek": yedek}
