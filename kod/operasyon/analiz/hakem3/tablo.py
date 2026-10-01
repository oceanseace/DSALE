# -*- coding: utf-8 -*-
"""hakem_sim.json -> konsol tabloları (yalnız toplu sayılar)."""
import json
import os

B = os.path.dirname(os.path.abspath(__file__))
J = json.load(open(os.path.join(B, "cikti", "hakem_sim.json"), encoding="utf-8"))
O = J["ortalama"]
E = J["eslestirilmis_fark"]
M = ["u24", "btk24", "saha24", "u48", "u72", "u7g", "acik_kalan", "ort_asim_saat", "p90_saat", "kapanis", "ziyaret",
     "bosa_ziyaret_orani", "ops_saat", "acik_24s_ustu_son_hafta", "km_teknisyen_gun", "tv_6s", "baglanti_12s",
     "erime_gun", "bos_dk_tek"]


def satir(k, d):
    return k.ljust(10) + " ".join(f"{d[m]:>8.3f}" if d[m] is not None and abs(d[m]) < 10 else f"{d[m]:>8.1f}" for m in M)


for dn in sorted(O):
    for N in sorted(O[dn], key=int):
        print(f"\n== {dn} N={N}")
        print(" " * 10 + " ".join(m[:8].rjust(8) for m in M))
        for k, d in sorted(O[dn][N].items(), key=lambda x: -x[1]["u24"]):
            print(satir(k, d))
print("\n=== eşleştirilmiş farklar (ort ± %95 GA)")
for dn in sorted(E):
    for N in sorted(E[dn], key=int):
        for c, d in E[dn][N].items():
            print(f"{dn:18s} N={N:>2} {c:20s} " + "  ".join(f"{m}={v[0]:+.3f}±{v[1]:.3f}" for m, v in d.items() if m != "n"))
