"""Bölge paletinin ayrışma denetimi (CIELAB ΔE76).

    python scripts/renk_denetimi.py

Kurallar
  1. İlk 8 bölge rengi birbirinden en az ΔE 45 uzakta olmalı (koyu zeminde net ayrışma).
  2. Hiçbir bölge rengi marka sarısına (#FFC400) ΔE 30'dan yakın olmamalı — sarı ofis
     işaretçisine ve marka vurgusuna ayrılmıştır.
  3. N ≤ 12 için kullanılan 12 rengin tamamı en az ΔE 30 uzakta olmalı.
"""
from __future__ import annotations

import sys
from itertools import combinations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402

from dsale.metrics import MARKA_SARI, TEMEL_RENKLER, _srgb_lab, renkler  # noqa: E402


def de(a: str, b: str) -> float:
    return float(np.sqrt(((_srgb_lab(a) - _srgb_lab(b)) ** 2).sum()))


def main() -> int:
    hata = []
    ilk8 = TEMEL_RENKLER[:8]
    en_az = min(de(a, b) for a, b in combinations(ilk8, 2))
    print(f"ilk 8 bölge rengi · en küçük ΔE76 = {en_az:.1f}")
    for a, b in combinations(ilk8, 2):
        if de(a, b) < 45:
            hata.append(f"{a} ↔ {b}: ΔE {de(a, b):.1f} < 45")
    for r in TEMEL_RENKLER:
        d = de(r, MARKA_SARI)
        if d < 30:
            hata.append(f"{r} marka sarısına çok yakın: ΔE {d:.1f} < 30")
    print(f"marka sarısı (#FFC400) · en küçük ΔE76 = {min(de(r, MARKA_SARI) for r in TEMEL_RENKLER):.1f}")

    on2 = renkler(12)
    en_az12 = min(de(a, b) for a, b in combinations(on2, 2))
    print(f"12 renk · en küçük ΔE76 = {en_az12:.1f}")
    if en_az12 < 30:
        for a, b in combinations(on2, 2):
            if de(a, b) < 30:
                hata.append(f"12'li palet {a} ↔ {b}: ΔE {de(a, b):.1f} < 30")

    # 4. Üretilen tam döngü (N = 13..50) da marka sarısından uzak durmalı.
    en_yakin = (999.0, "", 0)
    for n in range(13, 51):
        for i, r in enumerate(renkler(n), 1):
            d = de(r, MARKA_SARI)
            if d < en_yakin[0]:
                en_yakin = (d, r, n)
            if d < 30:
                hata.append(f"N={n} B{i} {r} marka sarısına çok yakın: ΔE {d:.1f} < 30")
    print(f"üretilen palet (N=13..50) · marka sarısına en küçük ΔE76 = {en_yakin[0]:.1f} "
          f"({en_yakin[1]}, N={en_yakin[2]})")

    for i, r in enumerate(TEMEL_RENKLER, 1):
        lab = _srgb_lab(r)
        print(f"  B{i:<2} {r}  L*={lab[0]:5.1f}  sarıya ΔE={de(r, MARKA_SARI):5.1f}")

    if hata:
        print("\nHATA:")
        for h in hata:
            print("  ·", h)
        return 1
    print("\n✓ palet denetimi geçti")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
