# -*- coding: utf-8 -*-
"""h3_tablo.py - h3_kosular.json + h3_ek_kosular.json -> konsol tabloları + cikti/h3_ozet.json (yalnız toplu sayılar)."""
import json
import math
import os
from collections import defaultdict

import numpy as np

B = os.path.dirname(os.path.abspath(__file__))
C = os.path.join(B, "cikti")
R = json.load(open(os.path.join(C, "h3_kosular.json"), encoding="utf-8"))
for _f in ("h3_ek_kosular.json", "h3_ek2_kosular.json"):
    ek = os.path.join(C, _f)
    if os.path.exists(ek):
        R += json.load(open(ek, encoding="utf-8"))

G = defaultdict(dict)   # (deney, N, kod) -> seed -> r
for r in R:
    G[(r["deney"], r["N"], r["kod"])][r["seed"]] = r

M = ["u24", "btk24", "tv_6s", "baglanti_12s", "u48", "u72", "acik_kalan", "kapanis_gun", "stok24_son",
     "stok24_egim_son14", "ort_sure_saat", "bosa_ziyaret_orani", "km_teknisyen_gun", "ops_saat", "gunluk_arama",
     "teyit_bayat_ziyaret_gun", "teyit_bayat_evde_yok_gun"]
KISA = ["u24", "btk24", "tv6", "bag12", "u48", "u72", "acik%", "kap/g", "stok24", "egim", "ortsa", "bosa", "km", "opsSa",
        "arama", "bayat", "bayEY"]


def ort(d, m):
    v = [x[m] for x in d.values() if x.get(m) is not None]
    return float(np.mean(v)) if v else None


def fmt(v, m):
    if v is None:
        return "     -"
    if m in ("u24", "btk24", "tv_6s", "baglanti_12s", "u48", "u72", "acik_kalan", "bosa_ziyaret_orani"):
        return f"{100 * v:6.1f}"
    return f"{v:6.1f}"


OZ = {"ortalama": {}, "fark": {}}
for dn in sorted({k[0] for k in G}):
    for N in sorted({k[1] for k in G if k[0] == dn}):
        kods = [k[2] for k in G if k[0] == dn and k[1] == N]
        print(f"\n== {dn}  N={N}")
        print("kod        " + " ".join(f"{x:>6s}" for x in KISA) + "   n  u24[min-max]")
        rows = sorted(kods, key=lambda k: -ort(G[(dn, N, k)], "u24"))
        for k in rows:
            d = G[(dn, N, k)]
            uu = [x["u24"] for x in d.values()]
            print(f"{k:10s} " + " ".join(fmt(ort(d, m), m) for m in M) + f" {len(d):3d}  [{100 * min(uu):.1f}-{100 * max(uu):.1f}]")
            OZ["ortalama"].setdefault(dn, {}).setdefault(str(N), {})[k] = {m: (round(ort(d, m), 4) if ort(d, m) is not None else None) for m in M} | {
                "n": len(d), "u24_min": round(min(uu), 4), "u24_max": round(max(uu), 4)}

CIFT = [("KARMA", "HAM"), ("KARMA_F", "HAM"), ("KARMA", "KARMA_F"), ("KARMA_F2", "KARMA_F"), ("HAM_Y", "HAM"),
        ("KARMA_F", "HAM_Y"), ("KARMA_T0", "HAM_Y"), ("KARMA_F", "KARMA_T0"), ("HAM_Y5", "HAM"), ("HAM_Y5", "KARMA_F"),
        ("KARMA_Y5", "KARMA_F"), ("KARMA_Y5", "HAM_Y5"), ("KARMA_Y5", "HAM"), ("HAM_Y5", "HAM_Y"), ("DSIR_R", "DSIR"),
        ("DSIR_L", "DSIR"), ("KARMA_Y5F2", "HAM"), ("KARMA_Y5F2", "KARMA"), ("KARMA_Y5F2", "KARMA_Y5")]
FM = ["u24", "btk24", "u48", "kapanis_gun", "stok24_son", "stok24_egim_son14"]
print("\n=== eşleştirilmiş farklar (aynı tohum), ort ± %95 GA; oranlar puan")
for dn in sorted({k[0] for k in G}):
    for N in sorted({k[1] for k in G if k[0] == dn}):
        for a, b in CIFT:
            ra, rb = G.get((dn, N, a), {}), G.get((dn, N, b), {})
            ortak = sorted(set(ra) & set(rb))
            if len(ortak) < 2:
                continue
            parca = []
            dd = {"n": len(ortak)}
            for m in FM:
                v = np.array([ra[s][m] - rb[s][m] for s in ortak], float)
                mu, ci = v.mean(), 1.96 * v.std(ddof=1) / math.sqrt(len(v))
                k = 100 if m in ("u24", "btk24", "u48") else 1
                parca.append(f"{m}={k * mu:+.1f}±{k * ci:.1f}")
                dd[m] = [round(float(mu), 4), round(float(ci), 4)]
            OZ["fark"].setdefault(dn, {}).setdefault(str(N), {})[f"{a}-{b}"] = dd
            print(f"{dn:24s} N={N:>2} {a + '-' + b:18s} " + "  ".join(parca))

json.dump(OZ, open(os.path.join(C, "h3_ozet.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("\nyazıldı:", os.path.join(C, "h3_ozet.json"))
