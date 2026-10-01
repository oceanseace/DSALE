# -*- coding: utf-8 -*-
"""
hakem_sim.py - HAKEM 3 (veri/simülasyon denetçisi) için yeniden koşum.

simulasyon_kopya.py = operasyon/analiz/simulasyon.py'nin birebir kopyası (yalnız dosya yolları hakem3/ klasörüne
göre düzeltildi). Özgün dosyaya dokunulmadı. Bu betik kopyayı modül olarak yükler ve:

  1) EK ÖLÇÜTLER: 24 s uyumu tek başına 'eski işi bırakan' sıralamayı ödüllendirir. Bu yüzden 48 s / 72 s / 7 gün
     uyumu, dönem sonunda hâlâ açık kalan yeni iş payı, ortalama 24 s aşımı (açık iş dönem sonunda sansürlü,
     yani alt sınır), günlük kapanış ve dönem sonu 24 s üstü açık iş stoku eklenir.
  2) KARIŞIKLIK (confound) AYRIŞTIRMA: KARMA = HAM'ın arama politikası + 'yetişir' sıralaması (tohum 1-3 ile
     modelde ayarlanmış) + BTK masa teşhisi + NOC küme bekletmesi + farklı Kanal merdiveni. Hangi parçanın
     kazandırdığını görmek için:
        HAM_Y     = HAM + KARMA'nın 'yetişir' sıralaması (başka hiçbir şey değişmez)
        KARMA_T0  = KARMA - masa teşhisi - NOC bekletmesi (yani HAM + yetişir + KARMA merdivenleri)
        KARMA_NOK = KARMA - NOC bekletmesi
  3) ADİLLİK: DSİR'e simülasyon yazarı randevu_pay=0,6 vermiş; bu, bölge x 2 saatlik blokta en çok 1 randevu
     demek (HAM/RPHT/U1H'de 2). DSİR tasarımında böyle bir tavan yok. DSIR_R = DSİR, randevu_pay=0,7 (HAM ile eşit).
  4) KALİBRASYON: BUGÜN modeli 'ulaşılamayan işe teknisyen hiç gitmez' diye kurulmuş; oysa veride ulaşılamayan iş
     çoğunlukla yine varsayılan 11:00 dilimine yazılıp ekibe veriliyor (DSİR kalibrasyonu: 302 notlu+randevulu,
     189 dilim 11:00'de). BUGUN_R = ulaşılamayan iş notlanır ve varsayılan 11:00 dilimine habersiz yazılır.
  5) Eşleştirilmiş (aynı tohum = aynı dünya) farklar ve %95 güven aralığı.

Gizlilik: yalnız toplu sayılar yazılır. Ağ çağrısı yok.
Çalıştırma: python hakem_sim.py   (16 çekirdekte ~3-4 dk)
Çıktı: hakem3/cikti/hakem_sim.json
"""
from __future__ import annotations

import json
import math
import os
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

import numpy as np

BURADA = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BURADA)
import simulasyon_kopya as S  # noqa: E402

GUN = S.GUN


# ================================================================== ek stratejiler (ayrıştırma / adillik)
class HamY(S.Ham):
    """HAM + KARMA'nın 'yetişir' sıralaması. Arama/merdiven/masa tamamen HAM."""
    kod = "HAM_Y"
    ad = "HAM + yetişir sıralaması"
    siralama = "yetisir"
    asiri_yuk_esigi = 15
    gec_kota = 4
    gec_btk_avans = 720
    _sec1 = S.Karma._sec1


class KarmaT0(S.Karma):
    kod = "KARMA_T0"
    ad = "KARMA - masa teşhisi - NOC"
    masa_teshis = False
    kume_nok = False


class KarmaNok(S.Karma):
    kod = "KARMA_NOK"
    ad = "KARMA - NOC bekletmesi"
    kume_nok = False


class DsirR(S.Dsir):
    kod = "DSIR_R"
    ad = "DSİR (randevu tavanı HAM ile eşit)"
    randevu_pay = 0.7


class BugunR(S.Bugun):
    """Bugünkü sürecin veriye daha yakın hali: ofis bir kez arar; ulaşamazsa not düşer ama iş yine varsayılan
    11:00 dilimine (bugün yetişmiyorsa ertesi gün) HABERSİZ yazılır ve teknisyen gider."""
    kod = "BUGUN_R"
    ad = "BUGÜN (ulaşılamayan da 11:00 dilimine)"

    def masa_sonuc(self, g, sonuc, t):
        if sonuc == "ulasildi":
            return super().masa_sonuc(g, sonuc, t)
        j = g.j
        m = self.m
        j.notlu = True
        j.deneme += 1
        if j.deneme >= 7:
            m.kapat(j, t, "ulasilamadi")
            return None
        d = S.gun(t)
        ws = d * GUN + 660
        if ws < t + 60:
            d += 1
            ws = d * GUN + 660
        m.havuza(j, "habersiz", (ws, ws + 120))
        return None


EK = {"HAM_Y": HamY, "KARMA_T0": KarmaT0, "KARMA_NOK": KarmaNok, "DSIR_R": DsirR, "BUGUN_R": BugunR}
TUM = dict(S.TUM_STRATEJI, **EK)


# ================================================================== ek ölçütler
def ozet_ek(M):
    son = M.H - GUN
    yeni = [j for j in M.isler if not j.birikim and S.REF_DK <= j.t0 < son]
    H = M.H

    def sure(j):  # saat; açık iş dönem sonunda sansürlü (alt sınır)
        return ((j.t_kapat if j.t_kapat is not None else H) - j.t0) / 60.0

    s = np.array([sure(j) for j in yeni])
    acik = np.array([j.t_kapat is None for j in yeni])
    btk = np.array([j.btk and j.tip in S.BTK_TIP for j in yeni])
    saha = np.array([j.kanal == "SAHA" for j in yeni])

    def u(h, m=None):
        mm = np.ones(len(s), bool) if m is None else m
        k = (~acik) & (s <= h) & mm
        return float(k.sum() / max(1, mm.sum()))

    bir = [j for j in M.isler if j.birikim]
    sb = np.array([sure(j) - (S.REF_DK - j.t0) / 60.0 for j in bir])  # birikimin simülasyondaki bekleme süresi
    return dict(
        u24=u(24), u48=u(48), u72=u(72), u7g=u(168), btk24=u(24, btk), btk48=u(48, btk), saha24=u(24, saha),
        saha72=u(72, saha),
        acik_kalan=float(acik.mean()), btk_acik_kalan=float(acik[btk].mean()),
        ort_asim_saat=float(np.maximum(0, s - 24).mean()),        # ort. 24 s aşımı (sansürlü alt sınır)
        btk_ort_asim_saat=float(np.maximum(0, s[btk] - 24).mean()),
        p90_saat=float(np.percentile(s, 90)), p95_saat=float(np.percentile(s, 95)),
        birikim_ort_bekleme_saat=float(sb.mean()) if len(sb) else None,
        n_yeni=len(yeni),
    )


def gorev(args):
    # makinede başka bir hakemin simülasyonu da koşuyor: bellek yetmezse bekleyip yeniden dene
    import gc
    for deneme in range(6):
        try:
            return _gorev(args)
        except MemoryError:
            gc.collect()
            time.sleep(20 * (deneme + 1))
    return _gorev(args)


def _gorev(args):
    deney, kod, N, seed, deg = args
    P = S.varsayilan()
    P["N"] = N
    for k, v in (deg or {}).items():
        P[k] = v
    M = S.Motor(S._VERI, P, TUM[kod], seed)
    M.calis()
    r = S.duz(S.ozet(M))
    r.update(ozet_ek(M))
    for k in ("birikim_seri", "acik24_seri", "tip_24s", "kapanis_turu"):
        r.pop(k, None)
    r.update(deney=deney, kod=kod, N=N, seed=seed)
    return r


# ================================================================== deney planı
TOH10 = list(range(101, 111))
TOH5 = list(range(101, 106))


def plan():
    L = []
    # A) ayrıştırma: aynı 10 tohum, 5 kadro düzeyi
    for N in (10, 12, 14, 16, 20):
        for k in ("HAM", "KARMA", "HAM_Y", "KARMA_T0", "KARMA_NOK"):
            for s in TOH10:
                L.append(("A", k, N, s, None))
    # B) diğer stratejiler, çok ölçütlü tablo için
    for N in (10, 16, 20):
        for k in ("DSIR", "DSIR_R", "RPHT", "U1H", "BOLGE", "BUGUN", "BUGUN_R"):
            for s in TOH5:
                L.append(("B", k, N, s, None))
    for N in (24,):
        for k in ("BUGUN", "BUGUN_R"):
            for s in TOH5:
                L.append(("B", k, N, s, None))
    # C) KARMA'nın büyük fark attığı duyarlılıklar: fark sıralamadan mı geliyor?
    DUY = {"giris_+15%": dict(giris_carpan=1.15), "evde_yok_%45": dict(evdeyok_hedef=0.45),
           "tel_x0.6": dict(tel_carpan=0.6), "elle_3_aktarim": dict(senkron="3x")}
    for ad, deg in DUY.items():
        for k in ("HAM", "KARMA", "HAM_Y", "KARMA_T0"):
            for s in TOH5:
                L.append(("C:" + ad, k, 16, s, deg))
    return L


def _ci(v):
    v = np.asarray(v, float)
    if len(v) < 2:
        return float(v.mean()), 0.0
    return float(v.mean()), float(1.96 * v.std(ddof=1) / math.sqrt(len(v)))


OLC = ["u24", "btk24", "saha24", "u48", "u72", "u7g", "acik_kalan", "btk_acik_kalan", "ort_asim_saat",
       "btk_ort_asim_saat", "p90_saat", "kapanis", "ziyaret", "bosa_ziyaret_orani", "ops_saat",
       "acik_24s_ustu_son_hafta", "km_teknisyen_gun", "tv_6s", "baglanti_12s", "erime_gun", "birikim_ort_bekleme_saat",
       "gunluk_arama", "bos_dk_tek"]


def topla(R):
    grup = defaultdict(list)
    for r in R:
        grup[(r["deney"], r["kod"], r["N"])].append(r)
    ort = {}
    for (dn, k, N), rs in grup.items():
        ort.setdefault(dn, {}).setdefault(str(N), {})[k] = {
            m: round(float(np.mean([x[m] for x in rs if x.get(m) is not None])), 4) for m in OLC} | {"n": len(rs)}
    # eşleştirilmiş farklar (aynı tohum)
    esl = {}
    ciftler = [("KARMA", "HAM"), ("HAM_Y", "HAM"), ("KARMA", "HAM_Y"), ("KARMA", "KARMA_T0"), ("KARMA", "KARMA_NOK"),
               ("KARMA_T0", "HAM_Y"), ("DSIR_R", "DSIR"), ("BUGUN_R", "BUGUN")]
    for (dn, k, N), rs in grup.items():
        pass
    anahtarlar = {(dn, N) for (dn, k, N) in grup}
    for dn, N in sorted(anahtarlar, key=lambda x: (x[0], x[1])):
        for a, b in ciftler:
            ra = {r["seed"]: r for r in grup.get((dn, a, N), [])}
            rb = {r["seed"]: r for r in grup.get((dn, b, N), [])}
            ortak = sorted(set(ra) & set(rb))
            if not ortak:
                continue
            d = {}
            for m in ("u24", "btk24", "u48", "u72", "acik_kalan", "ort_asim_saat", "kapanis", "acik_24s_ustu_son_hafta"):
                mu, ci = _ci([ra[s][m] - rb[s][m] for s in ortak])
                d[m] = [round(mu, 4), round(ci, 4)]
            d["n"] = len(ortak)
            esl.setdefault(dn, {}).setdefault(str(N), {})[f"{a}-{b}"] = d
    return dict(ortalama=ort, eslestirilmis_fark=esl)


def main():
    V = S.veri_yukle()
    L = plan()
    t1 = time.time()
    R = []
    isci = int(os.environ.get("HAKEM_ISCI", "6"))
    ara = os.path.join(BURADA, "cikti", "hakem_sim_ara.json")
    with ProcessPoolExecutor(isci, initializer=S._init, initargs=(V,)) as ex:
        for i, r in enumerate(ex.map(gorev, L, chunksize=1)):
            R.append(r)
            if (i + 1) % 25 == 0:
                print(f"  {i + 1}/{len(L)}  {time.time() - t1:.0f} s", flush=True)
                json.dump(R, open(ara, "w", encoding="utf-8"), ensure_ascii=False)
    T = topla(R)
    T["meta"] = dict(kosu=len(R), sure_s=round(time.time() - t1, 1), tohum_A=TOH10, tohum_BC=TOH5,
                     kaynak="hakem3/simulasyon_kopya.py (özgün simulasyon.py kopyası, yalnız yol düzeltmesi)",
                     birikim=len(V["birikim"]), not_="Açık kalan işler dönem sonunda sansürlü: ort_asim_saat ve p90 alt sınır.")
    os.makedirs(os.path.join(BURADA, "cikti"), exist_ok=True)
    json.dump(T, open(os.path.join(BURADA, "cikti", "hakem_sim.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(R, open(os.path.join(BURADA, "cikti", "hakem_sim_ham_kosular.json"), "w", encoding="utf-8"), ensure_ascii=False)
    print("bitti", len(R), "koşu", round(time.time() - t1), "s")


if __name__ == "__main__":
    main()
