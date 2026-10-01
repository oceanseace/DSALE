# -*- coding: utf-8 -*-
"""
hakem_kosu.py - HAKEM2 (saha teknik ekip lideri gözüyle) yeniden koşu.

simulasyon_hakem.py, operasyon/analiz/simulasyon.py'nin kopyasıdır. Bayraklar kapalıyken orijinalle birebir aynı
sonucu verir (KARMA/HAM N=16 tohum 101 ile doğrulandı: uyum, BTK, ziyaret, 24 s üstü açık aynı).

A) ORİJİNAL MODEL (bayrak yok): 7 strateji + ablasyonlar, kuyruk ölçüleriyle.
     HAM_Y     = HAM + KARMA'nın aşırı-yük 'yetişir' sıralaması (masa teşhisi yok)  -> kazanç sıralamadan mı?
     KARMA_NT  = KARMA - BTK paralel masa teşhisi                                  -> kazanç masadan mı?
     KARMA_Y   = KARMA + teknisyen 'yoldayım' araması, ulaşamazsa yine gider (arama 1,5/2,5 dk, sıralı)
     KARMA_Y05 = aynı, arama iş bitirirken / araçta eller serbest (0,5 dk)
     DSIR_C    = DSİR, teknisyen araması tasarımdaki gibi mevcut işin son dakikalarında (0,5 dk)
B) DÜZELTİLMİŞ MODEL (üç saha gerçekliği düzeltmesi):
     (1) teyit_gecerlilik_dk=180 : telefonda pencere verilmeden alınan 'evdeyim' teyidi 3 saat geçerli. Orijinalde
         masa teyidinden saatler/gün sonra gidilse de %95 başarı sayılıyor (KARMA masa teşhisi, RPHT/U1H/DSİR lehine).
     (2) habersiz_evde_basari=0.92: habersiz gidilen ve evde olan müşterinin %8'ine erişilemez (site/apartman kapısı,
         zil, 'beklemiyordum', çocuk/yaşlı yalnız). Orijinalde %100; teyitli ziyarette %95 -> teyitli < habersiz çelişkisi.
     (3) habersiz_tercih2_kabul=0.5: telefonda 'başka gün gelin' diyecek müşteri (tercih=2, %10-15) habersiz gelen
         teknisyeni evdeyse yalnız %50 kabul eder. Orijinalde %100; aynı müşteri telefonlu stratejilerde 1-3 gün
         ileriye randevulanıyor -> aramasız stratejiler lehine asimetri.
C) Düzeltilmiş modelde duyarlılık (N=12 ve 16): evde yok %30 / %45, kapı başarısı 0,85.

Ek ölçüler (orijinalde yok): iş başına 24 s üstü ortalama gecikme saati, p90 kapanış süresi, BTK'da 72 s üstü pay,
bayat teyit sayısı. Çıktı: hakem2/cikti/hakem_kosu.json (yalnız toplu sayılar; kişisel veri yok). Ağ çağrısı yok.
Çalıştırma: python hakem_kosu.py [--isci 6]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

import numpy as np

BURADA = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BURADA)
import simulasyon_hakem as sh  # noqa: E402

DUZ = dict(teyit_gecerlilik_dk=180, habersiz_evde_basari=0.92, habersiz_tercih2_kabul=0.5)
CAK = dict(tek_arama_dk=(0.5, 0.5))
T5 = [101, 102, 103, 104, 105]
T3 = [201, 202, 203]
NLER = (10, 12, 16, 20)
# etiket -> (strateji kodu, ek parametre)
VARYANT = {
    "BUGUN": ("BUGUN", {}), "HAM": ("HAM", {}), "DSIR": ("DSIR", {}), "RPHT": ("RPHT", {}), "BOLGE": ("BOLGE", {}),
    "U1H": ("U1H", {}), "KARMA": ("KARMA", {}),
    "HAM_Y": ("HAM_Y", {}), "KARMA_NT": ("KARMA_NT", {}),
    "KARMA_Y": ("KARMA_Y", {}), "KARMA_Y05": ("KARMA_Y", CAK), "DSIR_C": ("DSIR", CAK),
}
ANA7 = ["KARMA", "HAM", "DSIR", "RPHT", "U1H", "BOLGE", "BUGUN"]
DUY = {"evdeyok_30": dict(evdeyok_hedef=0.30), "evdeyok_45": dict(evdeyok_hedef=0.45),
       "kapi_085": dict(habersiz_evde_basari=0.85)}
DUY_VAR = ["HAM", "KARMA", "HAM_Y", "KARMA_Y05", "DSIR", "DSIR_C", "RPHT"]


ONCELIK = ["KARMA", "HAM", "HAM_Y", "KARMA_NT", "KARMA_Y05", "DSIR", "DSIR_C", "RPHT", "U1H", "BOLGE", "BUGUN",
           "KARMA_Y"]


def liste():
    """Öncelik sırası: önce kilit karşılaştırmalar (her iki model, tüm N), sonra geri kalanlar, sonra duyarlılık."""
    L = []
    for grup in (ONCELIK[:5], ONCELIK[5:]):
        for s in T5:
            for N in NLER:
                for deney, taban in (("B", DUZ), ("A", {})):
                    for et in grup:
                        kod, ek = VARYANT[et]
                        L.append((deney, et, kod, N, s, dict(taban, **ek) or None))
    for ad, deg in DUY.items():
        for N in (12, 16):
            for et in DUY_VAR:
                kod, ek = VARYANT[et]
                for s in T3:
                    L.append(("C:" + ad, et, kod, N, s, dict(DUZ, **deg, **ek)))
    return L


def gorev(a):
    deney, etiket, kod, N, seed, deg = a
    r = sh.gorev((deney, kod, N, seed, deg))
    r["etiket"] = etiket
    r["deney"] = deney
    for k in ("birikim_seri", "acik24_seri", "tip_24s", "kapanis_turu"):
        r.pop(k, None)
    return r


METRIK = ["uyum_24s", "uyum_24s_kararli", "uyum_48s", "btk_24s", "uyum_24s_kararli_btk", "tv_6s", "baglanti_12s",
          "gecikme_saat_ort", "btk_gecikme_saat_ort", "sure_p90_saat", "btk_sure_p90_saat", "btk_72s_ustu",
          "kapanis_saat_p50", "acik_24s_ustu_son_hafta", "erime_gun", "ziyaret", "ziyaret_tek", "bos_dk_tek",
          "bosa_ziyaret_orani", "ops_saat", "ops_cagri", "tek_cagri", "km_teknisyen_gun", "telefon_kapanis",
          "teyit_bayat", "randevu", "kapanis", "ulasilamadi_kapanis", "erteleme_haric_24s"]


def ozetle(rs):
    o = {}
    for m in METRIK:
        v = [r[m] for r in rs if r.get(m) is not None]
        if not v:
            continue
        o[m] = float(np.median(v)) if m == "erime_gun" else float(np.mean(v))
    o["uyum_24s_min"] = float(min(r["uyum_24s"] for r in rs))
    o["uyum_24s_max"] = float(max(r["uyum_24s"] for r in rs))
    o["n"] = len(rs)
    return o


ESL_METRIK = ("uyum_24s", "btk_24s", "uyum_48s", "gecikme_saat_ort", "btk_gecikme_saat_ort", "sure_p90_saat",
              "acik_24s_ustu_son_hafta", "bosa_ziyaret_orani", "ziyaret_tek")
CIFTLER = (("KARMA", "HAM"), ("HAM_Y", "HAM"), ("KARMA_NT", "KARMA"), ("HAM_Y", "KARMA"), ("KARMA_Y", "KARMA"),
           ("KARMA_Y05", "KARMA"), ("KARMA_Y05", "HAM_Y"), ("DSIR_C", "DSIR"), ("KARMA", "DSIR_C"),
           ("KARMA_Y05", "HAM"))


def eslesmis(ga, gb):
    ra = {r["seed"]: r for r in ga}
    rb = {r["seed"]: r for r in gb}
    ort = sorted(set(ra) & set(rb))
    out = {}
    for m in ESL_METRIK:
        d = np.array([ra[s][m] - rb[s][m] for s in ort], float)
        if len(d) == 0:
            continue
        out[m] = dict(ort=round(float(d.mean()), 4),
                      se=round(float(d.std(ddof=1) / np.sqrt(len(d))), 4) if len(d) > 1 else None,
                      pozitif=int((d > 0).sum()), n=len(d))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--isci", type=int, default=6)
    ap.add_argument("--yalniz_topla", action="store_true", help="koşmadan, mevcut jsonl'dan topla")
    a = ap.parse_args()
    V = sh.veri_yukle()
    L = liste()
    t1 = time.time()
    os.makedirs(os.path.join(BURADA, "cikti"), exist_ok=True)
    jl = os.path.join(BURADA, "cikti", "hakem_kosu.jsonl")
    sonuc = []
    if os.path.exists(jl):     # kaldığı yerden devam (bellek taşması / kesinti)
        for satir in open(jl, encoding="utf-8"):
            if satir.strip():
                sonuc.append(json.loads(satir))
    bitti = {(r["deney"], r["etiket"], r["N"], r["seed"]) for r in sonuc}
    L = [x for x in L if (x[0], x[1], x[3], x[4]) not in bitti]
    print(f"{len(L)} koşu kaldı ({len(sonuc)} hazır), {a.isci} işçi", flush=True)
    if L and not a.yalniz_topla:
        with ProcessPoolExecutor(a.isci, initializer=sh._init, initargs=(V,)) as ex, open(jl, "a", encoding="utf-8") as fo:
            for i, r in enumerate(ex.map(gorev, L, chunksize=1)):
                sonuc.append(r)
                fo.write(json.dumps(r, ensure_ascii=False, default=float) + "\n")
                fo.flush()
                if (i + 1) % 20 == 0:
                    print(f"  {i + 1}/{len(L)} koşu, {time.time() - t1:.0f} s", flush=True)
    grup = defaultdict(list)
    for r in sonuc:
        grup[(r["deney"], r["etiket"], r["N"])].append(r)
    tablo = defaultdict(dict)
    for (d, e, N), rs in sorted(grup.items(), key=lambda x: (x[0][0], x[0][2], x[0][1])):
        tablo[f"{d}|N={N}"][e] = ozetle(rs)
    esl = {}
    deneyler = sorted({k[0] for k in grup})
    for d in deneyler:
        for N in NLER:
            for x, y in CIFTLER:
                if grup.get((d, x, N)) and grup.get((d, y, N)):
                    esl[f"{d}|N={N}|{x}-{y}"] = eslesmis(grup[(d, x, N)], grup[(d, y, N)])
    # sıralama: A ve B'de her N için 7 ana strateji (24 s ve BTK 24 s)
    sira = {}
    for d in ("A", "B"):
        for N in NLER:
            t = tablo.get(f"{d}|N={N}", {})
            if not all(k in t for k in ANA7):
                continue
            sira[f"{d}|N={N}|24s"] = sorted(ANA7, key=lambda k: -t[k]["uyum_24s"])
            sira[f"{d}|N={N}|btk24s"] = sorted(ANA7, key=lambda k: -t[k]["btk_24s"])
            sira[f"{d}|N={N}|48s"] = sorted(ANA7, key=lambda k: -t[k]["uyum_48s"])
            sira[f"{d}|N={N}|gecikme_saat"] = sorted(ANA7, key=lambda k: t[k]["gecikme_saat_ort"])
    J = dict(meta=dict(olusturma="operasyon/analiz/hakem2/hakem_kosu.py", kopya="operasyon/analiz/hakem2/simulasyon_hakem.py",
                       kosu=len(sonuc), sure_s=round(time.time() - t1, 1), birikim_baslangic=len(V["birikim"]),
                       duzeltme=DUZ, cakisik_arama=CAK, tohum_ana=T5, tohum_duy=T3,
                       gizlilik="Yalnız toplu sayılar; kişi/müşteri/task/lokasyon kimliği yok."),
             tablo=tablo, eslesmis=esl, sira=sira,
             ham=[{k: (round(v, 5) if isinstance(v, float) else v) for k, v in r.items()} for r in sonuc])
    os.makedirs(os.path.join(BURADA, "cikti"), exist_ok=True)
    yol = os.path.join(BURADA, "cikti", "hakem_kosu.json")
    with open(yol, "w", encoding="utf-8") as f:
        json.dump(J, f, ensure_ascii=False, indent=1, default=float)
    print("yazıldı:", yol, len(sonuc), "koşu", round(time.time() - t1), "s", flush=True)


if __name__ == "__main__":
    main()
