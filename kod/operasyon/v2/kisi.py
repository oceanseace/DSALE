"""Kişiler ve görev kümesi (EK-1, EK-2) — iş motorunun ihtiyacı kadarı.

Yetki görev KÜMESİNDEN gelir (``kullanici_gorev``); tablo yoksa ana görev (``kullanici.rol``). Rota düzeyindeki
izin ``saha/yetki.py``'nindir (WP-A); burada yalnız motorun kendi ince ayrımları vardır: müşteri alanı kime,
teknik yalnız kendi işini görür, atanabilir kişi kimdir.
"""
from __future__ import annotations

import json
import sqlite3

from operasyon import is_emri as ie

# Spec §2.2 tablosunun iş motoruyla ilgili satırları (varsayılan YASAK). saha/yetki.py ile aynı olmalı.
IZINLER: dict[str, frozenset[str]] = {
    "is.liste": frozenset({"operasyon", "teknik", "yonetici"}),
    "is.musteri": frozenset({"operasyon", "teknik", "yonetici"}),
    "is.yukle": frozenset({"operasyon", "yonetici"}),
    "is.ata": frozenset({"operasyon", "yonetici"}),
    "is.duzenle": frozenset({"operasyon", "yonetici"}),
    "is.saha": frozenset({"operasyon", "teknik", "yonetici"}),
    "is.olustur": frozenset({"operasyon", "yonetici"}),
    "is.excel": frozenset({"operasyon", "yonetici"}),
    "obek.oku": frozenset({"operasyon", "yonetici"}),
    "obek.duzenle": frozenset({"operasyon", "yonetici"}),
    "mahalle.ekle": frozenset({"operasyon", "yonetici"}),
    "mahalle.yukle": frozenset({"yonetici"}),
    "takip.oku": frozenset({"operasyon", "yonetici"}),
    "takip.tam": frozenset({"yonetici"}),
    "kapasite.yaz": frozenset({"operasyon", "yonetici"}),
    "ekip.teknikler": frozenset({"operasyon", "yonetici"}),
    "ekip.yonet": frozenset({"yonetici"}),
    "veri.yonet": frozenset({"yonetici"}),
}
OFIS = frozenset({"operasyon", "yonetici"})


def _tablo_var(conn: sqlite3.Connection, ad: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (ad,)).fetchone() is not None


def sutunlar(conn: sqlite3.Connection, tablo: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({tablo})").fetchall()}


def gorevler(conn: sqlite3.Connection | None, k: dict | None) -> set[str]:
    """Kişinin görev kümesi (ana görev her zaman içindedir)."""
    if not k:
        return set()
    if k.get("gorevler"):
        return set(k["gorevler"]) | ({k["rol"]} if k.get("rol") else set())
    kume = {k["rol"]} if k.get("rol") else set()
    if conn is not None and k.get("id") is not None and _tablo_var(conn, "kullanici_gorev"):
        kume |= {r[0] for r in conn.execute("SELECT rol FROM kullanici_gorev WHERE kullanici_id=?", (k["id"],))}
    return kume


def izinli(conn: sqlite3.Connection | None, k: dict | None, eylem: str) -> bool:
    return bool(gorevler(conn, k) & IZINLER.get(eylem, frozenset()))


def ofis_mu(conn, k) -> bool:
    """Operasyon ya da yönetici görevi var mı (bütün işler, tam müşteri bilgisi)."""
    return bool(gorevler(conn, k) & OFIS)


def teknik_mi(conn, k) -> bool:
    return "teknik" in gorevler(conn, k)


def kapsam_teknik(conn, k) -> bool:
    """İş listesinde yalnız kendi işlerini mi görür (teknik olup ofis görevi olmayan)."""
    return teknik_mi(conn, k) and not ofis_mu(conn, k)


def _satir_gorevleri(conn: sqlite3.Connection, ids) -> dict[int, list[str]]:
    ids = [i for i in set(ids) if i is not None]
    if not ids or not _tablo_var(conn, "kullanici_gorev"):
        return {}
    out: dict[int, list[str]] = {}
    for kid, rol in conn.execute(f"SELECT kullanici_id, rol FROM kullanici_gorev WHERE kullanici_id IN "
                                 f"({','.join('?' * len(ids))})", ids):
        out.setdefault(kid, []).append(rol)
    return out


def kisiler(conn: sqlite3.Connection, ids=None) -> dict[int, dict]:
    """id → {id, ad, rol, aktif, gorevler, unvan, giris_var, boss_ekip, kapasite, etiket}. Eksik sütunlar None."""
    s = sutunlar(conn, "kullanici")
    ek = [c for c in ("unvan", "boss_ekip", "kapasite", "etiket", "kaynak") if c in s]
    sql = "SELECT id, ad, rol, aktif, telefon" + "".join(f", {c}" for c in ek) + " FROM kullanici"
    param: list = []
    if ids is not None:
        ids = [i for i in set(ids) if i is not None]
        if not ids:
            return {}
        sql += f" WHERE id IN ({','.join('?' * len(ids))})"
        param = ids
    satirlar = conn.execute(sql, param).fetchall()
    gorev = _satir_gorevleri(conn, [r[0] for r in satirlar])
    out = {}
    for r in satirlar:
        d = dict(zip(["id", "ad", "rol", "aktif", "telefon", *ek], r))
        kume = sorted(set(gorev.get(d["id"], [])) | {d["rol"]})
        try:
            etiket = json.loads(d.get("etiket") or "[]")
        except ValueError:
            etiket = []
        out[d["id"]] = {"id": d["id"], "ad": d["ad"], "rol": d["rol"], "aktif": bool(d["aktif"]), "gorevler": kume,
                        "unvan": d.get("unvan"), "giris_var": bool(d.get("telefon")), "boss_ekip": d.get("boss_ekip"),
                        "kapasite": d.get("kapasite"), "etiket": etiket if isinstance(etiket, list) else []}
    return out


def ozet(kisi: dict | None) -> dict | None:
    """Arayüze giden ``Kisi``: {id, ad, gorevler, unvan, giris_var}."""
    if not kisi:
        return None
    return {"id": kisi["id"], "ad": kisi["ad"], "gorevler": kisi.get("gorevler") or [kisi.get("rol")],
            "unvan": kisi.get("unvan"), "giris_var": bool(kisi.get("giris_var", True))}


def teknikler(conn: sqlite3.Connection, yalniz_aktif: bool = True) -> dict[int, dict]:
    return {i: k for i, k in kisiler(conn).items()
            if "teknik" in k["gorevler"] and (k["aktif"] or not yalniz_aktif)}


def kisa_ad(ad: str | None) -> str:
    """"Ayşe Kaya" → "Ayşe K." (teknikte müşteri, bildirimde kişi)."""
    p = str(ad or "").split()
    if len(p) < 2:
        return str(ad or "")
    son = p[-1]
    bas = son[:1].replace("i", "İ").replace("ı", "I").upper()
    return f"{ie.baslik(p[0]) if p[0].isupper() else p[0]} {bas}."


def boss_ekip_haritasi(conn: sqlite3.Connection) -> dict[str, int]:
    """anahtar(BOSS "Ekip") → aktif teknik kişi. Önce ``boss_ekip`` alanı; sonra (EK-2) kişinin adı, tekse."""
    h: dict[str, int] = {}
    adlar: dict[str, list[int]] = {}
    for kid, k in teknikler(conn).items():
        if k.get("boss_ekip"):
            h.setdefault(ie.anahtar(k["boss_ekip"]), kid)
        adlar.setdefault(ie.anahtar(k["ad"]), []).append(kid)
    for anahtar, ids in adlar.items():
        if len(ids) == 1:
            h.setdefault(anahtar, ids[0])
    return h
