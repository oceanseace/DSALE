# -*- coding: utf-8 -*-
"""
hakem_ek.py - HAKEM2 ek deney: önerilen aşıların sınanması (hakem_kosu.py ile aynı dünya, aynı tohumlar).

  KARMA_K3  : aşırı-yük modunda gecikmiş kota her 3. seçim, kota önce gecikmiş BTK'ya (BTK kuyruk koruması)
  KARMA_K2  : aynı, her 2. seçim
  KARMA_H   : KARMA'nın masası (BTK paralel teşhis, Kanal akşam denemesi, NOC) + HAM'ın saha sırası (her zaman)
  KARMA_YK3 : KARMA_K3 + teknisyenin çakışık 'yoldayım' araması (0,5 dk; ulaşamazsa yine gider)
  KARMA_E40 / KARMA_E80 : aşırı-yük anahtarı eşiği 15 yerine 40 / 80 gecikmiş iş (2. tur, tohum 101-103)
  KARMA_YH  : KARMA_H + çakışık 'yoldayım' araması (2. tur)

A = orijinal model, B = düzeltilmiş model (hakem_kosu.DUZ). Çıktı: cikti/hakem_ek.jsonl (kaldığı yerden devam eder).
Yalnız toplu sayılar; kişisel veri yok; ağ çağrısı yok.  Çalıştırma: python hakem_ek.py [--isci 3]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

BURADA = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BURADA)
import simulasyon_hakem as sh  # noqa: E402
from hakem_kosu import DUZ, CAK, T5, NLER, gorev  # noqa: E402

VAR = {"KARMA_K3": ("KARMA_K3", {}), "KARMA_H": ("KARMA_H", {}), "KARMA_YK3": ("KARMA_YK3", CAK),
       "KARMA_K2": ("KARMA_K2", {})}
# 2. tur: aşırı-yük eşiği ayarı ve KARMA-H + yoldayım (tohum 101-103)
VAR2 = {"KARMA_E40": ("KARMA_E40", {}), "KARMA_E80": ("KARMA_E80", {}), "KARMA_YH": ("KARMA_YH", CAK)}


def liste():
    L = []
    for s in T5:
        for N in NLER:
            for deney, taban in (("B", DUZ), ("A", {})):
                for et, (kod, ek) in VAR.items():
                    L.append((deney, et, kod, N, s, dict(taban, **ek) or None))
    for s in T5[:3]:
        for N in NLER:
            for deney, taban in (("B", DUZ), ("A", {})):
                for et, (kod, ek) in VAR2.items():
                    L.append((deney, et, kod, N, s, dict(taban, **ek) or None))
    return L


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--isci", type=int, default=3)
    a = ap.parse_args()
    V = sh.veri_yukle()
    jl = os.path.join(BURADA, "cikti", "hakem_ek.jsonl")
    bitti = set()
    if os.path.exists(jl):
        for satir in open(jl, encoding="utf-8"):
            if satir.strip():
                r = json.loads(satir)
                bitti.add((r["deney"], r["etiket"], r["N"], r["seed"]))
    L = [x for x in liste() if (x[0], x[1], x[3], x[4]) not in bitti]
    t1 = time.time()
    print(f"{len(L)} koşu kaldı, {a.isci} işçi", flush=True)
    with ProcessPoolExecutor(a.isci, initializer=sh._init, initargs=(V,)) as ex, open(jl, "a", encoding="utf-8") as fo:
        for i, r in enumerate(ex.map(gorev, L, chunksize=1)):
            fo.write(json.dumps(r, ensure_ascii=False, default=float) + "\n")
            fo.flush()
            if (i + 1) % 20 == 0:
                print(f"  {i + 1}/{len(L)} koşu, {time.time() - t1:.0f} s", flush=True)
    print("bitti", round(time.time() - t1), "s", flush=True)


if __name__ == "__main__":
    main()
