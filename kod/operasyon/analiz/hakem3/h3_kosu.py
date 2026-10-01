# -*- coding: utf-8 -*-
"""
h3_kosu.py - HAKEM 3 (veri/simülasyon denetçisi): simulasyon.py'nin denetim koşuları.

simulasyon_h3.py = operasyon/analiz/simulasyon.py'nin birebir kopyası; yalnız dosya yolları hakem3/'e göre
düzeltildi. Özgün dosyaya dokunulmadı. Düzeltme ve varyantlar bu betikte, kopyanın üstüne yama olarak uygulanır.

DENETİMDE BULUNANLAR VE BURADA SINANANLAR
  H1 (hata, yalnız KARMA'yı etkiler): KARMA'nın paralel masa teşhisinde müşteri 'şimdi müsait' derse iş havuzda
     PENCERESİZ kalır ama teyit='teyitli' olur. kapida_basari() teyitli işe ne zaman gidilirse gidilsin %95 kapı
     başarısı verir (evde/işte gizli durumuna bakmaz). Teknisyen saatler, hatta bir gün sonra gelse de müşteri
     'evde' sayılıyor. Diğer stratejilerde teyitli işaret teknisyen yola çıkarken konur (hemen gidilir), bu
     yüzden onlarda etkisi yok. Düzeltme: pencereli randevudaki 180 dk kuralıyla tutarlı olarak, penceresiz teyit
     180 dk sonra bayatlar; sonra gizli 'evde mi' durumu (habersiz ziyaret kuralı) geçerlidir.
       KARMA_F  = KARMA + H1 düzeltmesi
       KARMA_F2 = KARMA_F'nin KARMA lehine alternatifi: masa, müsait müşteriye '3 saat içinde' penceresi verir
                  (iş P0 randevu olarak rotaya girer; geç kalınırsa normal geç-varış kuralı)
  H2 (karışıklık): KARMA = HAM'ın aramasız sevki + 'yetişir' sıralaması (simülatörde tohum 1-3 ile ayarlandı)
     + BTK masa teşhisi + NOC küme bekletmesi + farklı merdiven/randevu tavanı. Hangi parçanın kazandırdığı:
       HAM_Y     = HAM + KARMA'nın 'yetişir' sıralaması (başka hiçbir şey değişmez)
       KARMA_T0  = KARMA_F - masa teşhisi - NOC bekletmesi
  H3 (ölçüt): 24 s uyumu kapasite kıtken 'geciken işi bırak' sıralamasını ödüllendirir. N<=16'da bütün
     stratejilerde 24 s üstü açık stok doğrusal büyüyor (kararsız sistem). Ek ölçütler: 48/72 s, günlük kapanış
     (verim), dönem sonu 24 s üstü stok ve son 14 gündeki büyüme hızı, dönem sonunda hâlâ açık yeni iş payı,
     ortalama sistemde kalma (sansürlü, alt sınır).
  H4 (adillik, küçük): DSİR'e randevu_pay=0,6 verilmiş (bölge x 2 saatlik blokta 1 randevu; HAM/RPHT'de 2).
       DSIR_R = DSİR, randevu_pay=0,7.

Gizlilik: yalnız toplu sayılar yazılır. Ağ çağrısı yok.
Çalıştırma: python h3_kosu.py [--isci 6]      Çıktı: hakem3/cikti/h3_sonuc.json (+ h3_kosular.json)
"""
from __future__ import annotations

import argparse
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
import simulasyon_h3 as S  # noqa: E402

GUN = S.GUN

# ================================================================== H1: teyit ömrü (ölçüm + düzeltme)
_orig_kapida = S.Motor.kapida_basari


def _kapida_basari(self, j, t):
    tt = self.__dict__.setdefault("_teyit_t", {}).pop(j.id, None)
    if tt is not None and j.teyit == "teyitli" and j.pencere is None:
        yas = t - tt
        self.g["teyitli_penceresiz_ziyaret"] += 1
        if yas > 180:
            self.g["teyit_bayat_ziyaret"] += 1
            self.g["teyit_bayat_evde_yok"] += 0 if self.evde(j, t) else 1
            if self.P.get("teyit_omur"):
                j.teyit = "habersiz"          # düzeltme: bayat teyit -> gizli evde durumu
    return _orig_kapida(self, j, t)


S.Motor.kapida_basari = _kapida_basari


def _karma_masa_sonuc_kayitli(cls):
    orig = cls.masa_sonuc

    def masa_sonuc(self, g, sonuc, t):
        j = g.j
        r = orig(self, g, sonuc, t)
        if g.amac == "teshis" and j.teyit == "teyitli" and j.pencere is None and j.state == "SAHA":
            self.m.__dict__.setdefault("_teyit_t", {})[j.id] = t
            self.m.g["teshis_teyitli"] += 1
        return r
    cls.masa_sonuc = masa_sonuc


_karma_masa_sonuc_kayitli(S.Karma)   # KARMA (özgün davranış) yalnız ÖLÇÜLÜR; teyit_omur=None -> değişmez


class KarmaF(S.Karma):
    kod = "KARMA_F"
    ad = "KARMA + teyit ömrü düzeltmesi (180 dk)"


class KarmaF2(S.Karma):
    kod = "KARMA_F2"
    ad = "KARMA_F alternatifi: müsait müşteriye 3 saatlik pencere"

    def masa_sonuc(self, g, sonuc, t):
        j = g.j
        r = S.Karma.masa_sonuc(self, g, sonuc, t)
        if g.amac == "teshis" and j.teyit == "teyitli" and j.pencere is None and j.state == "SAHA":
            self.m.__dict__.setdefault("_teyit_t", {}).pop(j.id, None)
            self.m.havuza(j, "teyitli", (t, t + 180))
        return r


class HamY(S.Ham):
    """HAM + KARMA'nın 'yetişir' sıralaması. Arama/merdiven/masa/randevu tavanı tamamen HAM."""
    kod = "HAM_Y"
    ad = "HAM + yetişir sıralaması"
    siralama = "yetisir"
    asiri_yuk_esigi = 15
    gec_kota = 4
    gec_btk_avans = 720
    _sec1 = S.Karma._sec1


class KarmaT0(KarmaF):
    kod = "KARMA_T0"
    ad = "KARMA_F - masa teşhisi - NOC"
    masa_teshis = False
    kume_nok = False


class DsirR(S.Dsir):
    kod = "DSIR_R"
    ad = "DSİR (randevu tavanı HAM ile eşit)"
    randevu_pay = 0.7


# kod -> (sınıf, parametre değişikliği)
VARYANT = {
    "HAM": (S.Ham, {}), "KARMA": (S.Karma, {}), "KARMA_F": (KarmaF, dict(teyit_omur=180)),
    "KARMA_F2": (KarmaF2, dict(teyit_omur=180)), "HAM_Y": (HamY, {}), "KARMA_T0": (KarmaT0, dict(teyit_omur=180)),
    "DSIR": (S.Dsir, {}), "DSIR_R": (DsirR, {}), "RPHT": (S.Rpht, {}), "U1H": (S.U1h, {}), "BOLGE": (S.Bolge, {}),
    "BUGUN": (S.Bugun, {}),
}


# ================================================================== H3: ek ölçütler
def ozet_ek(M):
    H = M.H
    son = H - GUN
    yeni = [j for j in M.isler if not j.birikim and S.REF_DK <= j.t0 < son]
    s = np.array([((j.t_kapat if j.t_kapat is not None else H) - j.t0) / 60.0 for j in yeni])
    acik = np.array([j.t_kapat is None for j in yeni])
    btk = np.array([bool(j.btk and j.tip in S.BTK_TIP) for j in yeni])

    def u(h, m=None):
        mm = np.ones(len(s), bool) if m is None else m
        return float(((~acik) & (s <= h) & mm).sum() / max(1, mm.sum()))

    G = [g for g in M.gunluk if g["gun"] >= 1]
    a24 = [g["acik_24s_ustu"] for g in M.gunluk]
    ng = max(1, len(G))
    top = lambda k: sum(g.get(k, 0.0) for g in G)
    return dict(
        u24=u(24), u48=u(48), u72=u(72), u7g=u(168), btk24=u(24, btk), btk48=u(48, btk), btk72=u(72, btk),
        acik_kalan=float(acik.mean()),
        ort_sure_saat=float(s.mean()),                         # sansürlü alt sınır
        ort_asim_saat=float(np.maximum(0, s - 24).mean()),     # sansürlü alt sınır
        kapanis_gun=top("kapanis") / ng,
        stok24_son=float(a24[-1]), stok24_ort=float(np.mean(a24[1:])),
        stok24_egim_son14=float((a24[-1] - a24[-15]) / 14.0),
        teyitli_penceresiz_ziyaret_gun=top("teyitli_penceresiz_ziyaret") / ng,
        teyit_bayat_ziyaret_gun=top("teyit_bayat_ziyaret") / ng,
        teyit_bayat_evde_yok_gun=top("teyit_bayat_evde_yok") / ng,
        teshis_teyitli_gun=top("teshis_teyitli") / ng,
        n_yeni=len(yeni),
    )


def gorev(args):
    deney, kod, N, seed, deg = args
    cls, ek = VARYANT[kod]
    P = S.varsayilan()
    P["N"] = N
    P.update(ek)
    P.update(deg or {})
    M = S.Motor(S._VERI, P, cls, seed)
    M.calis()
    r = S.duz(S.ozet(M))
    for k in ("birikim_seri", "acik24_seri", "tip_24s", "kapanis_turu"):
        r.pop(k, None)
    r.update(ozet_ek(M))
    r.update(deney=deney, kod=kod, N=N, seed=seed)
    return r


# ================================================================== deney planı
T10 = list(range(101, 111))      # tasarımda kullanılmayan tohumlar (101-105 özgün ana yarışla aynı)
T5 = list(range(101, 106))


def plan(hizli=False):
    L = []
    t10 = T10[:2] if hizli else T10
    t5 = T5[:2] if hizli else T5
    # A) karışıklık ayrıştırma + H1 düzeltmesi: 10 tohum, 5 kadro
    for N in (10, 12, 14, 16, 20):
        for k in ("HAM", "HAM_Y", "KARMA", "KARMA_F", "KARMA_F2", "KARMA_T0"):
            for s in t10:
                L.append(("A", k, N, s, None))
    # B) diğer yarışanlar: çok ölçütlü tablo
    for N in (10, 16, 20):
        for k in ("DSIR", "DSIR_R", "RPHT", "U1H", "BOLGE"):
            for s in t5:
                L.append(("B", k, N, s, None))
    # C) KARMA'nın HAM'ı geçtiği / geçmediği duyarlılıklar (N=16)
    DUY = {"giris_+15%": dict(giris_carpan=1.15), "evde_yok_%45": dict(evdeyok_hedef=0.45),
           "uzaktan_cozum_dusuk": dict(q_teshis=0.6, q_kontrol=0.3), "elle_3_aktarim": dict(senkron="3x")}
    for ad, deg in DUY.items():
        for k in ("HAM", "HAM_Y", "KARMA", "KARMA_F"):
            for s in t5:
                L.append(("C:" + ad, k, 16, s, deg))
    return L


OLC = ["uyum_24s", "u24", "u48", "u72", "btk24", "btk48", "btk72", "tv_6s", "baglanti_12s", "saha_24s",
       "uyum_24s_kararli", "acik_kalan", "ort_sure_saat", "ort_asim_saat", "kapanis_gun", "stok24_son", "stok24_ort",
       "stok24_egim_son14", "erime_gun", "ziyaret", "bosa_ziyaret_orani", "km_teknisyen_gun", "ops_saat",
       "gunluk_arama", "teyitli_penceresiz_ziyaret_gun", "teyit_bayat_ziyaret_gun", "teyit_bayat_evde_yok_gun",
       "teshis_teyitli_gun", "ulasilamadi_kapanis"]


def _ci(v):
    v = np.asarray(v, float)
    if len(v) < 2:
        return float(v.mean()), 0.0
    return float(v.mean()), float(1.96 * v.std(ddof=1) / math.sqrt(len(v)))


def topla(R):
    grup = defaultdict(list)
    for r in R:
        grup[(r["deney"], r["kod"], r["N"])].append(r)
    ort = {}
    for (dn, k, N), rs in grup.items():
        d = {}
        for m in OLC:
            v = [x[m] for x in rs if x.get(m) is not None]
            d[m] = round(float(np.mean(v)), 4) if v else None
        d["n"] = len(rs)
        ort.setdefault(dn, {}).setdefault(str(N), {})[k] = d
    ciftler = [("KARMA", "HAM"), ("KARMA_F", "HAM"), ("KARMA_F2", "HAM"), ("KARMA", "KARMA_F"),
               ("HAM_Y", "HAM"), ("KARMA_F", "HAM_Y"), ("KARMA_F2", "HAM_Y"), ("KARMA_F", "KARMA_T0"),
               ("KARMA_T0", "HAM_Y"), ("DSIR_R", "DSIR")]
    esl = {}
    for dn, N in sorted({(dn, N) for (dn, k, N) in grup}):
        for a, b in ciftler:
            ra = {r["seed"]: r for r in grup.get((dn, a, N), [])}
            rb = {r["seed"]: r for r in grup.get((dn, b, N), [])}
            ortak = sorted(set(ra) & set(rb))
            if not ortak:
                continue
            d = {"n": len(ortak)}
            for m in ("u24", "btk24", "u48", "u72", "kapanis_gun", "stok24_son", "stok24_egim_son14", "ort_sure_saat"):
                mu, ci = _ci([ra[s][m] - rb[s][m] for s in ortak])
                d[m] = [round(mu, 4), round(ci, 4)]
            esl.setdefault(dn, {}).setdefault(str(N), {})[f"{a}-{b}"] = d
    return dict(ortalama=ort, eslestirilmis_fark=esl)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--isci", type=int, default=int(os.environ.get("HAKEM_ISCI", "6")))
    ap.add_argument("--hizli", action="store_true")
    ap.add_argument("--tek", nargs=3, metavar=("KOD", "N", "TOHUM"))
    a = ap.parse_args()
    V = S.veri_yukle()
    if a.tek:
        S._init(V)
        t1 = time.time()
        r = gorev(("tek", a.tek[0], int(a.tek[1]), int(a.tek[2]), None))
        print(json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items() if k in OLC or k in ("kod", "N", "seed")},
                         ensure_ascii=False, indent=0), f"\n{time.time() - t1:.1f} s")
        return
    L = plan(a.hizli)
    os.makedirs(os.path.join(BURADA, "cikti"), exist_ok=True)
    ara = os.path.join(BURADA, "cikti", "h3_kosular.json")
    t1 = time.time()
    R = []
    with ProcessPoolExecutor(a.isci, initializer=S._init, initargs=(V,)) as ex:
        for i, r in enumerate(ex.map(gorev, L, chunksize=1)):
            R.append(r)
            if (i + 1) % 20 == 0:
                print(f"  {i + 1}/{len(L)}  {time.time() - t1:.0f} s", flush=True)
                json.dump(R, open(ara, "w", encoding="utf-8"), ensure_ascii=False)
    json.dump(R, open(ara, "w", encoding="utf-8"), ensure_ascii=False)
    T = topla(R)
    T["meta"] = dict(kosu=len(R), sure_s=round(time.time() - t1, 1), tohum_A=T10, tohum_BC=T5,
                     kaynak="hakem3/simulasyon_h3.py (özgün simulasyon.py, yalnız yol düzeltmesi) + h3_kosu.py yamaları",
                     birikim=len(V["birikim"]), not_="Açık kalan işler dönem sonunda sansürlü: ort_sure/ort_asim alt sınır. "
                     "Çıktıda yalnız toplu sayılar var.")
    json.dump(T, open(os.path.join(BURADA, "cikti", "h3_sonuc.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("bitti", len(R), "koşu", round(time.time() - t1), "s")


if __name__ == "__main__":
    main()
