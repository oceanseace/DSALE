"""3B dijital ikiz için bina tabanları — sıkı, önbellekli, sıkıştırılmış.

Biçim ``dsale/bundle.py`` → ``binalar()`` ile aynı: her binanın taban halkası,
binanın merkezine (lat/lon) göre MİKRO-DERECE farkları olarak tek bir tamsayı
dizisinde durur; ``ofs[i]..ofs[i+1]`` i. binanın noktalarıdır (nokta = 2 tamsayı).

    lon_nokta = lon[i] + fark[2k]   * olcek
    lat_nokta = lat[i] + fark[2k+1] * olcek      (k = ofs[i] .. ofs[i+1]-1)

Kaynak: ilk kurulumdaki binalar ``veri/master/bina_geometri.json``, sonradan eklenenler
``bina_geometri_ek`` tablosu. Poligonu olmayan binada ofs[i]==ofs[i+1] (istemci kare çizer).
Yanıt, bina künyesi değişmedikçe (``bina_surumu``) bellekteki hazır gzip baytlarından verilir.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import sqlite3

from . import ayarlar, db

KAT_YUKSEKLIGI_M = 3.0
OLCEK = 1e-6

_dosya: dict = {}
# {anahtar: (imza, ham_bayt, gzip_bayt, etag)}
_onbellek: dict[str, tuple[tuple, bytes, bytes, str]] = {}


def _dosya_geometrisi() -> dict[str, list]:
    yol = ayarlar.VERI_GEOMETRI
    if not yol.exists():
        return {}
    imza = (yol.stat().st_size, int(yol.stat().st_mtime))
    if _dosya.get("imza") != imza:
        _dosya["veri"] = json.load(open(yol, encoding="utf-8"))
        _dosya["imza"] = imza
    return _dosya["veri"]


def paket(conn: sqlite3.Connection, bolge: int | None) -> tuple[bytes, bytes, str]:
    """(ham JSON, gzip'li JSON, ETag). Bölge verilirse yalnız o bölge."""
    anahtar = "hepsi" if bolge is None else str(int(bolge))
    yol = ayarlar.VERI_GEOMETRI
    dosya_imza = (yol.stat().st_size, int(yol.stat().st_mtime)) if yol.exists() else None
    imza = (db.bina_surum_oku(conn), dosya_imza)
    saklanan = _onbellek.get(anahtar)
    if saklanan and saklanan[0] == imza:
        return saklanan[1], saklanan[2], saklanan[3]

    if bolge is None:
        satirlar = conn.execute("SELECT bina_serial, lat, lon, kat FROM bina WHERE pasif=0 "
                                "ORDER BY bina_serial").fetchall()
    else:
        satirlar = conn.execute("SELECT bina_serial, lat, lon, kat FROM bina WHERE pasif=0 AND bolge=? "
                                "ORDER BY bina_serial", (int(bolge),)).fetchall()
    dosya = _dosya_geometrisi()
    ek = {r[0]: r[1] for r in conn.execute("SELECT bina_serial, halka FROM bina_geometri_ek")}
    seriler, lat, lon, kat, ofs, fark = [], [], [], [], [0], []
    for s in satirlar:
        serial, la, lo = s["bina_serial"], float(s["lat"]), float(s["lon"])
        halka = None
        if serial in ek:
            try:
                halka = json.loads(ek[serial])
            except ValueError:
                halka = None
        if halka is None:
            halka = dosya.get(serial) or []
        for x, y in halka:
            fark.append(int(round((x - lo) / OLCEK)))
            fark.append(int(round((y - la) / OLCEK)))
        ofs.append(len(fark) // 2)
        seriler.append(serial)
        lat.append(round(la, 6))
        lon.append(round(lo, 6))
        kat.append(int(s["kat"] or 1))
    govde = json.dumps({
        "surum": 1, "adet": len(seriler), "bolge": bolge,
        "serial": seriler, "lat": lat, "lon": lon, "kat": kat,
        "ofs": ofs, "fark": fark, "olcek": OLCEK, "kat_yuksekligi_m": KAT_YUKSEKLIGI_M,
        "poligonsuz": sum(1 for i in range(len(seriler)) if ofs[i] == ofs[i + 1]),
    }, separators=(",", ":")).encode("utf-8")
    sikisik = gzip.compress(govde, compresslevel=6)
    etag = f'"geo-{anahtar}-{imza[0]}-{hashlib.sha1(govde).hexdigest()[:12]}"'
    _onbellek[anahtar] = (imza, govde, sikisik, etag)
    return govde, sikisik, etag
