"""Yakınlık / uzaklık — bir kez yazılır, her yerde kullanılır.

- mesafe_km(...)        : kuş uçuşu km (haversine); diziyle de çalışır.
- yol_km_tahmini(...)   : şehir içi yol ≈ 1,3 × kuş uçuşu (çevrimdışı kaba tahmin).
- en_yakinlar(...)      : bir noktaya en yakın k nokta.
- dengeli_bol(...)      : noktaları k parçaya böler; parçalar yük olarak eşit, coğrafi olarak derli
                          toplu. Satış bölgelemesindeki algoritmanın (CCPD, dsale/partition.py) aynısı;
                          aynı yerdeki (bina / site / mahalle) noktalar hiç bölünmez.
- parca_ozeti(...)      : her parçanın yükü, merkezi ve yarıçapı.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

DUNYA_YARICAP_KM = 6371.0088
YOL_KATSAYISI = 1.3


def mesafe_km(lat1, lon1, lat2, lon2):
    """Kuş uçuşu mesafe (km). Sayı ya da numpy dizisi alır (yayınlanır)."""
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp = p2 - p1
    dl = np.radians(np.asarray(lon2) - np.asarray(lon1))
    h = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * DUNYA_YARICAP_KM * np.arcsin(np.sqrt(np.clip(h, 0, 1)))


def yol_km_tahmini(lat1, lon1, lat2, lon2):
    return YOL_KATSAYISI * mesafe_km(lat1, lon1, lat2, lon2)


def en_yakinlar(lat: float, lon: float, lats, lons, k: int = 5) -> tuple[np.ndarray, np.ndarray]:
    """(sıra numaraları, km) — en yakından uzağa."""
    d = mesafe_km(lat, lon, np.asarray(lats, float), np.asarray(lons, float))
    sira = np.argsort(d)[:k]
    return sira, d[sira]


def dengeli_bol(lat, lon, k: int, agirlik=None, grup=None, seed: int = 20260929) -> np.ndarray:
    """Noktaları k parçaya böler → parça no (1..k); konumu olmayan nokta 0.

    agirlik: noktanın yükü (varsayılan 1 = iş sayısı). grup: aynı gruptaki noktalar aynı parçaya
    düşer (ör. aynı bina ya da aynı mahalle). Parça numaraları batıdan doğuya sıralıdır.
    """
    lat = np.asarray(lat, float)
    lon = np.asarray(lon, float)
    n = len(lat)
    w = np.ones(n) if agirlik is None else np.asarray(agirlik, float)
    g = np.arange(n).astype(str) if grup is None else np.asarray(grup, dtype=object).astype(str)
    etiket = np.zeros(n, int)
    var = ~(np.isnan(lat) | np.isnan(lon))
    if k <= 1 or var.sum() == 0:
        etiket[var] = 1
        return etiket
    df = pd.DataFrame({"lat": lat[var], "lon": lon[var], "yuk": w[var], "site_grup": g[var],
                       "bina_serial": np.flatnonzero(var).astype(str), "il": ""})
    birim = df.groupby("site_grup").agg(lat=("lat", "mean"), lon=("lon", "mean"), yuk=("yuk", "sum"))
    if len(birim) <= k:
        # birim sayısı parça sayısından az: her birim kendi parçası (batıdan doğuya)
        sira = birim.sort_values("lon").index
        no = {b: i + 1 for i, b in enumerate(sira)}
        etiket[var] = df["site_grup"].map(no).to_numpy()
        return etiket
    from dsale.partition import bolgele
    sonuc = bolgele(df, k, olcu="yuk", tohum_sayisi=3, dis_iter=15, seed=seed)
    etiket[var] = sonuc.atama.reindex(df["bina_serial"]).to_numpy()
    return etiket


def parca_ozeti(lat, lon, etiket, agirlik=None) -> list[dict]:
    """Her parça: yük, merkez, en uzak noktanın merkeze uzaklığı (km)."""
    lat = np.asarray(lat, float)
    lon = np.asarray(lon, float)
    etiket = np.asarray(etiket)
    w = np.ones(len(lat)) if agirlik is None else np.asarray(agirlik, float)
    out = []
    for p in sorted(set(etiket.tolist()) - {0}):
        s = (etiket == p) & ~np.isnan(lat)
        if not s.any():
            continue
        mlat, mlon = float(np.average(lat[s], weights=w[s])), float(np.average(lon[s], weights=w[s]))
        d = mesafe_km(mlat, mlon, lat[s], lon[s])
        out.append({"parca": int(p), "yuk": float(w[etiket == p].sum()), "nokta": int((etiket == p).sum()),
                    "merkez": [round(mlat, 6), round(mlon, 6)], "yaricap_km": round(float(d.max()), 2),
                    "ort_km": round(float(d.mean()), 2)})
    return out
