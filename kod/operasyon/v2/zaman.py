"""Saat: bütün v2 kodu şimdiyi buradan alır; testler ``zaman.simdi``'yi dondurur.

Zamanlar metin olarak saklanır (``ayarlar.zaman_metni()``: Türkiye saati, "AAAA-AA-GG SS:DD:ss").
"""
from __future__ import annotations

import datetime as dt

from saha import ayarlar


def simdi() -> dt.datetime:
    return ayarlar.simdi()


def metin(an: dt.datetime | None = None) -> str:
    return (an or simdi()).isoformat(sep=" ", timespec="seconds")


def oku(deger) -> dt.datetime | None:
    """Metin/Timestamp → datetime (saniye). Okunamazsa None."""
    if deger is None:
        return None
    if isinstance(deger, dt.datetime):
        return deger.replace(tzinfo=None, microsecond=0)
    s = str(deger).strip()
    if not s or s.lower() in ("nan", "nat", "none"):
        return None
    s = s.replace("T", " ")
    try:
        return dt.datetime.fromisoformat(s[:19]).replace(microsecond=0)
    except ValueError:
        pass
    for bicim in ("%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M", "%d.%m.%Y", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M"):
        try:
            return dt.datetime.strptime(s, bicim)
        except ValueError:
            continue
    return None


def dakika(a: dt.datetime | str | None, b: dt.datetime | str | None) -> float | None:
    """b − a dakika cinsinden (ikisinden biri yoksa None)."""
    a, b = oku(a), oku(b)
    if a is None or b is None:
        return None
    return (b - a).total_seconds() / 60.0


def saat_dk(an: dt.datetime | str | None) -> str:
    """"14:05" biçimi."""
    t = oku(an)
    return t.strftime("%H:%M") if t else ""
