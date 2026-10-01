# -*- coding: utf-8 -*-
"""
hakem_ozet.py - HAKEM2 koşularını (cikti/hakem_kosu.jsonl + cikti/hakem_ek.jsonl) toplar.
Çıktı: cikti/hakem_ozet.json (yalnız toplu sayılar) + konsol tabloları.

Ek bileşik ölçü (saha ekip lideri gözüyle):
  skor = 24 s uyumu (%) - 0,5 x BTK'da 72 s üstü pay (%) - 0,25 x ortalama gecikme (24 s üstü saat, iş başına)
  Gerekçe: 24 s oranı tek başına 'geç kalmışı bırak' davranışını ödüllendiriyor; 72 s'i aşan BTK işi BTK şikâyeti,
  tekrar çağrı ve Turkcell eskalasyonu doğurur. Ağırlıklar yargısaldır; sıralama ham ölçülerle de verilir.
"""
from __future__ import annotations

import json
import os
from collections import defaultdict

import numpy as np

BURADA = os.path.dirname(os.path.abspath(__file__))
C = os.path.join(BURADA, "cikti")
R = []
for ad in ("hakem_kosu.jsonl", "hakem_ek.jsonl"):
    yol = os.path.join(C, ad)
    if os.path.exists(yol):
        R += [json.loads(s) for s in open(yol, encoding="utf-8") if s.strip()]

METRIK = ["uyum_24s", "btk_24s", "uyum_48s", "tv_6s", "baglanti_12s", "gecikme_saat_ort", "btk_gecikme_saat_ort",
          "sure_p90_saat", "btk_72s_ustu", "acik_24s_ustu_son_hafta", "erime_gun", "ziyaret_tek", "bosa_ziyaret_orani",
          "ops_saat", "ops_cagri", "tek_cagri", "km_teknisyen_gun", "telefon_kapanis", "teyit_bayat",
          "ulasilamadi_kapanis", "kapanis_saat_p50"]
SIRA = ["KARMA", "KARMA_E40", "KARMA_E80", "KARMA_H", "KARMA_YH", "KARMA_K3", "KARMA_K2", "KARMA_YK3", "KARMA_Y05", "KARMA_Y", "KARMA_NT", "HAM", "HAM_Y",
        "DSIR", "DSIR_C", "RPHT", "U1H", "BOLGE", "BUGUN"]
ANA7 = ["KARMA", "HAM", "DSIR", "RPHT", "U1H", "BOLGE", "BUGUN"]


def skor(r):
    return 100 * r["uyum_24s"] - 50 * r["btk_72s_ustu"] - 0.25 * r["gecikme_saat_ort"]


g = defaultdict(list)
for r in R:
    r["skor"] = skor(r)
    g[(r["deney"], r["N"], r["etiket"])].append(r)

tablo = defaultdict(dict)
for (d, N, e), rs in g.items():
    o = {}
    for m in METRIK + ["skor"]:
        v = [x[m] for x in rs if x.get(m) is not None]
        if v:
            o[m] = round(float(np.median(v) if m == "erime_gun" else np.mean(v)), 4)
    o["uyum_24s_min"] = round(min(x["uyum_24s"] for x in rs), 4)
    o["uyum_24s_max"] = round(max(x["uyum_24s"] for x in rs), 4)
    o["n"] = len(rs)
    tablo[f"{d}|N={N}"][e] = o


def fark(d, N, a, b, m):
    ra = {x["seed"]: x for x in g.get((d, N, a), [])}
    rb = {x["seed"]: x for x in g.get((d, N, b), [])}
    s = sorted(set(ra) & set(rb))
    if len(s) < 2:
        return None
    v = np.array([ra[k][m] - rb[k][m] for k in s], float)
    return dict(ort=round(float(v.mean()), 4), se=round(float(v.std(ddof=1) / np.sqrt(len(v))), 4),
                pozitif=int((v > 0).sum()), n=len(v))


CIFT = [("KARMA", "HAM"), ("HAM_Y", "HAM"), ("KARMA", "KARMA_NT"), ("KARMA_K3", "KARMA"), ("KARMA_K2", "KARMA"),
        ("KARMA_K3", "HAM"), ("KARMA_YK3", "KARMA_K3"), ("KARMA_YK3", "HAM"), ("KARMA_H", "HAM"),
        ("KARMA_H", "KARMA"), ("KARMA_Y05", "KARMA"), ("DSIR_C", "DSIR"), ("KARMA", "DSIR"),
        ("KARMA_E40", "KARMA"), ("KARMA_E80", "KARMA"), ("KARMA_YH", "KARMA_H"), ("KARMA_E40", "HAM"),
        ("KARMA_E80", "HAM")]
esl = {}
for d in ("A", "B"):
    for N in (10, 12, 16, 20):
        for a, b in CIFT:
            e = {m: fark(d, N, a, b, m) for m in ("uyum_24s", "btk_24s", "uyum_48s", "btk_72s_ustu",
                                                  "gecikme_saat_ort", "skor")}
            if any(e.values()):
                esl[f"{d}|N={N}|{a}-{b}"] = e

sira = {}
for k, t in tablo.items():
    if not k.startswith(("A|", "B|")):
        continue
    ana = [s for s in ANA7 if s in t]
    if len(ana) == len(ANA7):
        sira[k + "|24s"] = sorted(ana, key=lambda s: -t[s]["uyum_24s"])
        sira[k + "|skor"] = sorted(ana, key=lambda s: -t[s]["skor"])
    tum = [s for s in SIRA if s in t]
    sira[k + "|skor_tum_varyant"] = sorted(tum, key=lambda s: -t[s]["skor"])

J = dict(meta=dict(olusturma="operasyon/analiz/hakem2/hakem_ozet.py", kosu=len(R),
                   skor="100*uyum_24s - 50*btk_72s_ustu - 0.25*gecikme_saat_ort",
                   model_A="orijinal simulasyon.py (birebir kopya, bayrak kapalı)",
                   model_B="düzeltilmiş: teyit 180 dk geçerli, habersiz kapı başarısı 0,92, tercih-2 habersiz kabul 0,5",
                   gizlilik="Yalnız toplu sayılar; kişi/müşteri/task/lokasyon kimliği yok."),
         tablo=tablo, eslesmis=esl, sira=sira)
with open(os.path.join(C, "hakem_ozet.json"), "w", encoding="utf-8") as f:
    json.dump(J, f, ensure_ascii=False, indent=1)


def p(x):
    return "   -" if x is None else f"{100 * x:4.0f}"


def fl(x, nd=0):
    return "    -" if x is None else f"{x:5.{nd}f}"


for k in sorted(tablo, key=lambda s: (s.split("|")[0], int(s.split("=")[1]) if s[0] in "AB" else 0, s)):
    t = tablo[k]
    print(f"\n=== {k} ===")
    print("strateji    n  24s  btk  48s  tv6 bg12 | gec_s btkgec  p90 btk72 acik24 erime | ziy/tk bosa ops_s tekcg | skor")
    for s in SIRA:
        v = t.get(s)
        if not v:
            continue
        print(f"{s:10s} {v['n']:2d} {p(v['uyum_24s'])} {p(v['btk_24s'])} {p(v['uyum_48s'])} {p(v.get('tv_6s'))} "
              f"{p(v.get('baglanti_12s'))} | {fl(v['gecikme_saat_ort'],1)} {fl(v['btk_gecikme_saat_ort'],1)} "
              f"{fl(v['sure_p90_saat'])} {p(v['btk_72s_ustu'])} {fl(v['acik_24s_ustu_son_hafta'])} {fl(v['erime_gun'])} | "
              f"{fl(v['ziyaret_tek'],1)} {p(v['bosa_ziyaret_orani'])} {fl(v['ops_saat'])} {fl(v['tek_cagri'])} | {v['skor']:6.1f}")
print("\n=== eşleştirilmiş farklar (aynı tohum; ort ± se [pozitif/n]) ===")
for k, e in esl.items():
    s = "  ".join(f"{m}={e[m]['ort']:+.3f}±{e[m]['se']:.3f}[{e[m]['pozitif']}/{e[m]['n']}]"
                  for m in ("uyum_24s", "btk_24s", "btk_72s_ustu", "skor") if e.get(m))
    print(f"{k:30s} {s}")
print("\n=== sıralar ===")
for k, v in sira.items():
    print(f"{k:32s} {' > '.join(v)}")
