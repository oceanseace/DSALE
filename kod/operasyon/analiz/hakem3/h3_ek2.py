# -*- coding: utf-8 -*-
"""
h3_ek2.py - HAKEM 3 önerilen birleşimin sayısı: KARMA_Y5F2 = KARMA + yerel 'yetişir' (h3_ek) + masa teşhisinde
müsait müşteriye 3 saatlik pencere (h3_kosu KARMA_F2). Aynı tohumlar (101-110), eşleştirilmiş karşılaştırma
h3_tablo.py ile (h3_ek2_kosular.json da okunur).
Çıktı: hakem3/cikti/h3_ek2_kosular.json
"""
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

BURADA = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BURADA)
import h3_ek as E  # noqa: E402

H, S = E.H, E.S


class KarmaY5F2(H.KarmaF2):
    kod = "KARMA_Y5F2"
    ad = "KARMA + yerel yetişir + 3 s teyit penceresi"
    _sec1 = E._sec1_yerel


H.VARYANT["KARMA_Y5F2"] = (KarmaY5F2, dict(teyit_omur=180))


def plan():
    L = [("A", "KARMA_Y5F2", N, s, None) for N in (10, 12, 14, 16, 20) for s in H.T10]
    L += [("C:giris_+15%", "KARMA_Y5F2", 16, s, dict(giris_carpan=1.15)) for s in H.T5]
    L += [("C:uzaktan_cozum_dusuk", "KARMA_Y5F2", 16, s, dict(q_teshis=0.6, q_kontrol=0.3)) for s in H.T5]
    return L


def main():
    V = S.veri_yukle()
    L = plan()
    t1 = time.time()
    with ProcessPoolExecutor(8, initializer=S._init, initargs=(V,)) as ex:
        R = list(ex.map(H.gorev, L, chunksize=1))
    json.dump(R, open(os.path.join(BURADA, "cikti", "h3_ek2_kosular.json"), "w", encoding="utf-8"), ensure_ascii=False)
    print("bitti", len(R), round(time.time() - t1), "s")


if __name__ == "__main__":
    main()
