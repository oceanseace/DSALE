"""İş satırının rengi ("işaret"): kullanıcının Excel'deki gibi satıra boyadığı dolgu rengi.

Giriş: ``yaz`` (POST /api/isler/{is_no}/isaret, api.py) · ``hepsi`` (gorunum.Baglam; satırdaki ``isaret`` alanı).
Hücre düzeyi (Excel gibi, 08.10): ``hucre_yaz`` (POST /api/isler/hucre-renk) · ``hucreler`` (satırdaki ``hucre_renk``
= {sütun kimliği: renk | 'yok'}). Eski satır rengi (``isaret``) satırın bütün hücrelerine uygulanır; hücre rengi
onun üstüne yazar, 'yok' o hücrede satır rengini kaldırır. Arayüzde etkin renk: ``hucreRengi`` (sutunlar.ts).
Renk iş akışını değiştirmez; yalnız göz içindir. Her değişiklik iş olayına da yazılır ("isaret") ki
/api/isler/degisim öteki ekranlara taşısın.
"""
from __future__ import annotations

import sqlite3

from . import akis, ek_sema, zaman
from .hatalar import Gecersiz
from .islem import islem

RENKLER = ("sari", "kirmizi", "yesil", "mavi", "mor", "turuncu")
YOK = "yok"                 # hücre: satır rengini bu hücrede kaldır
EN_COK_HUCRE = 20000        # tek istekte (≈ 1.000 satır × 20 sütun)
_AD = {"sari": "sarı", "kirmizi": "kırmızı", "yesil": "yeşil", "mavi": "mavi", "mor": "mor", "turuncu": "turuncu"}


def hepsi(conn: sqlite3.Connection) -> dict[str, str]:
    """is_no → renk (tablo henüz kurulmadıysa boş)."""
    if not ek_sema.var_mi(conn, "is_isaret"):
        return {}
    return {r[0]: r[1] for r in conn.execute("SELECT is_no, renk FROM is_isaret")}


def yaz(conn: sqlite3.Connection, is_no: str, renk: str | None, k: dict | None) -> dict:
    """Renk koyar (``None`` → temizler). Kapsam dışı iş 404 (teknikte başkasının işi)."""
    if renk is not None and renk not in RENKLER:
        raise Gecersiz("Renk tanınmadı.", kod="alan_eksik", secenekler=list(RENKLER))
    r = akis.is_getir(conn, is_no)
    akis.kapsam_denetle(conn, k, r)
    ek_sema.hazirla(conn)
    with islem(conn):
        eski = conn.execute("SELECT renk FROM is_isaret WHERE is_no=?", (is_no,)).fetchone()
        eski = eski[0] if eski else None
        if eski == renk:
            return {"ok": True, "isaret": renk}
        if renk is None:
            conn.execute("DELETE FROM is_isaret WHERE is_no=?", (is_no,))
        else:
            conn.execute("INSERT INTO is_isaret(is_no, renk, zaman, kullanici_id, kullanici_ad) VALUES(?,?,?,?,?) "
                         "ON CONFLICT(is_no) DO UPDATE SET renk=excluded.renk, zaman=excluded.zaman, "
                         "kullanici_id=excluded.kullanici_id, kullanici_ad=excluded.kullanici_ad",
                         (is_no, renk, zaman.metin(), (k or {}).get("id"), (k or {}).get("ad")))
        akis.olay_yaz(conn, is_no, "isaret", k, eski={"isaret": eski}, yeni={"isaret": renk},
                      notu=f"Renk: {_AD[renk]}" if renk else "Renk kaldırıldı")
    return {"ok": True, "isaret": renk}


def hucreler(conn: sqlite3.Connection) -> dict[str, dict[str, str]]:
    """is_no → {sütun: renk | 'yok'} (tablo henüz kurulmadıysa boş)."""
    if not ek_sema.var_mi(conn, "is_hucre_renk"):
        return {}
    out: dict[str, dict[str, str]] = {}
    for no, sutun, renk in conn.execute("SELECT is_no, sutun, renk FROM is_hucre_renk"):
        out.setdefault(no, {})[sutun] = renk
    return out


def hucre_yaz(conn: sqlite3.Connection, hucre_listesi: list[dict], renk: str | None, k: dict | None) -> dict:
    """Seçili hücrelere dolgu (``None`` → dolgu yok). Satırın eski rengi varsa "dolgu yok" o hücreye 'yok' yazar;
    satır rengiyle aynı renk hücre kaydını siler (satırdan gelir). Dönüş: değişen her işin yeni ``hucre_renk``'i."""
    if renk is not None and renk not in RENKLER:
        raise Gecersiz("Renk tanınmadı.", kod="alan_eksik", secenekler=list(RENKLER))
    if not hucre_listesi:
        raise Gecersiz("Hücre seçilmedi.", kod="alan_eksik")
    if len(hucre_listesi) > EN_COK_HUCRE:
        raise Gecersiz(f"Tek seferde en çok {EN_COK_HUCRE:,} hücre boyanır.".replace(",", "."), kod="alan_eksik")
    is_sutun: dict[str, list[str]] = {}
    for h in hucre_listesi:
        no, sutun = str(h.get("is_no") or ""), str(h.get("sutun") or "")[:160]
        if not no or not sutun:
            raise Gecersiz("Hücre eksik (is_no, sutun).", kod="alan_eksik")
        l = is_sutun.setdefault(no, [])
        if sutun not in l:
            l.append(sutun)
    for no in is_sutun:                 # yetki: hepsi kapsamdaysa yaz (teknikte başkasının işi 404)
        akis.kapsam_denetle(conn, k, akis.is_getir(conn, no))
    ek_sema.hazirla(conn)
    simdi = zaman.metin()
    sonuc: dict[str, dict[str, str]] = {}
    with islem(conn):
        for no, sutunlar in is_sutun.items():
            satir = conn.execute("SELECT renk FROM is_isaret WHERE is_no=?", (no,)).fetchone()
            satir_rengi = satir[0] if satir else None
            for sutun in sutunlar:
                hedef = renk if renk is not None else (YOK if satir_rengi else None)
                if hedef is None or hedef == satir_rengi:
                    conn.execute("DELETE FROM is_hucre_renk WHERE is_no=? AND sutun=?", (no, sutun))
                else:
                    conn.execute("INSERT INTO is_hucre_renk(is_no, sutun, renk, zaman, kullanici_id, kullanici_ad) "
                                 "VALUES(?,?,?,?,?,?) ON CONFLICT(is_no, sutun) DO UPDATE SET renk=excluded.renk, "
                                 "zaman=excluded.zaman, kullanici_id=excluded.kullanici_id, "
                                 "kullanici_ad=excluded.kullanici_ad",
                                 (no, sutun, hedef, simdi, (k or {}).get("id"), (k or {}).get("ad")))
            sonuc[no] = {s_: r_ for s_, r_ in conn.execute(
                "SELECT sutun, renk FROM is_hucre_renk WHERE is_no=?", (no,))}
            n = len(sutunlar)
            akis.olay_yaz(conn, no, "isaret", k, eski=None, yeni={"hucre": sutunlar[:20], "renk": renk},
                          notu=(f"Hücre rengi: {_AD[renk]}" if renk else "Hücre rengi kaldırıldı")
                          + (f" ({n} hücre)" if n > 1 else ""))
    return {"ok": True, "renk": renk, "isler": sonuc}
