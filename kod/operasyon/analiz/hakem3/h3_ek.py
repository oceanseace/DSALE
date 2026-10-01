# -*- coding: utf-8 -*-
"""
h3_ek.py - HAKEM 3 ek deney: 'yetişir' sıralamasına HAM'ın yakınlık kuralını eklemek.

Gözlem (h3_kosu): KARMA'nın 'yetişir' sıralaması işi son tarihe göre seçer, yolu neredeyse hiç tartmaz.
Teknisyen başına günde ~10 km (≈25 dk) fazla yol, günde ~10 daha az kapanış demek. N<=16'da sistem kararsız
olduğu için bu kayıp, 24 s üstü açık stoğun HAM'dan daha hızlı büyümesine yol açıyor.

Varyant: aynı 'yetişir' mantığı (aşırı yükte: 24 saatine yetişebilecek iş önce, her 4. seçimde gecikmiş kota,
yoksa HAM sırası) ama her kademede 'en acil 5 aday içinden en yakını' seçilir (HAM'ın yerellik kuralı).
Kalan bolluğu 90 dk'nın altına düşmüş en acil iş varsa yakınlığa bakılmadan o alınır.
    HAM_Y5   = HAM + yerel 'yetişir'
    KARMA_Y5 = KARMA_F (teyit düzeltmeli) + yerel 'yetişir'

Çalıştırma: python h3_ek.py [--isci 7]     Çıktı: hakem3/cikti/h3_ek_kosular.json
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
import h3_kosu as H  # noqa: E402  (yamaları da uygular)

S = H.S
GUN = S.GUN


def _sec1_yerel(self, tkn, t, pool, d):
    m = self.m
    j = m.pencere_sec(tkn, t, pool, d)
    if j is not None:
        return j
    idx = [i for i, x in enumerate(pool) if x.pencere is None]
    if not idx:
        return None
    tr = m.yol_dk_vec(d)

    def ham(ix):
        order = sorted(ix, key=lambda i: (not pool[i].btk, pool[i].t0))[:5]
        return pool[min(order, key=lambda i: d[i])]

    n_gec = sum(1 for i in idx if t - pool[i].t0 >= GUN)
    if n_gec < self.asiri_yuk_esigi:
        return ham(idx)
    tkn.sayac += 1
    if tkn.sayac % self.gec_kota == 0:
        gec = [i for i in idx if t + tr[i] + 30 >= pool[i].t0 + GUN]
        if gec:
            order = sorted(gec, key=lambda i: pool[i].t0 - (self.gec_btk_avans if pool[i].btk else 0))[:5]
            return pool[min(order, key=lambda i: d[i])]
    yet = [i for i in idx if t + tr[i] + 30 < pool[i].t0 + GUN]
    if yet:
        son = lambda i: pool[i].t0 + GUN - (360 if pool[i].btk else 0) - (120 if pool[i].tip == "TV_ARIZA" else 0)
        order = sorted(yet, key=son)[:5]
        acil = order[0]
        if pool[acil].t0 + GUN - t - tr[acil] - 30 < 90:
            return pool[acil]
        return pool[min(order, key=lambda i: d[i])]
    return ham(idx)


class HamY5(H.HamY):
    kod = "HAM_Y5"
    ad = "HAM + yerel yetişir"
    _sec1 = _sec1_yerel


class KarmaY5(H.KarmaF):
    kod = "KARMA_Y5"
    ad = "KARMA_F + yerel yetişir"
    _sec1 = _sec1_yerel


class DsirL(S.Dsir):
    """Uygulama artefaktı kontrolü: Dsir.sec 6 ardışık arama/atlama sonrası None döner ve teknisyen iş varken
    10 dk boş bekler. Burada seçim, havuzda aday kaldıkça sürer (tasarımda böyle bir bekleme yok)."""
    kod = "DSIR_L"

    def sec(self, tkn, t):
        for _ in range(5):
            j = S.Dsir.sec(self, tkn, tkn.free)
            if j is not None:
                return j
            if tkn.free >= tkn.bit - 15:
                break
        return None


H.VARYANT["HAM_Y5"] = (HamY5, {})
H.VARYANT["KARMA_Y5"] = (KarmaY5, dict(teyit_omur=180))
H.VARYANT["DSIR_L"] = (DsirL, {})


def plan():
    L = []
    for N in (10, 12, 14, 16, 20):
        for k in ("HAM_Y5", "KARMA_Y5"):
            for s in H.T10:
                L.append(("A", k, N, s, None))
    DUY = {"giris_+15%": dict(giris_carpan=1.15), "evde_yok_%45": dict(evdeyok_hedef=0.45),
           "uzaktan_cozum_dusuk": dict(q_teshis=0.6, q_kontrol=0.3), "elle_3_aktarim": dict(senkron="3x")}
    for ad, deg in DUY.items():
        for k in ("HAM_Y5", "KARMA_Y5"):
            for s in H.T5:
                L.append(("C:" + ad, k, 16, s, deg))
    for N in (10, 16, 20):
        for s in H.T5:
            L.append(("B", "DSIR_L", N, s, None))
    return L


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--isci", type=int, default=7)
    a = ap.parse_args()
    V = S.veri_yukle()
    L = plan()
    t1 = time.time()
    R = []
    with ProcessPoolExecutor(a.isci, initializer=S._init, initargs=(V,)) as ex:
        for i, r in enumerate(ex.map(H.gorev, L, chunksize=1)):
            R.append(r)
            if (i + 1) % 20 == 0:
                print(f"  {i + 1}/{len(L)}  {time.time() - t1:.0f} s", flush=True)
    json.dump(R, open(os.path.join(BURADA, "cikti", "h3_ek_kosular.json"), "w", encoding="utf-8"), ensure_ascii=False)
    print("bitti", len(R), round(time.time() - t1), "s")


if __name__ == "__main__":
    main()
