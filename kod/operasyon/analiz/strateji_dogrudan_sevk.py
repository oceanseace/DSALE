# -*- coding: utf-8 -*-
"""STRATEJİ "DOĞRUDAN SEVK + İSTİSNA RANDEVU" (DSİR) - kullanıcının kendi fikrinin titiz hali.

Fikir: gelen mevcut-müşteri işi aranmadan doğrudan teknisyen rotasına girer; teknisyen
sıradaki işi yola çıkmadan önce kendisi arar (bu arama aynı zamanda 'düzeldi mi' filtresi);
ulaşamadığı işler operasyonun istisna kuyruğuna düşer, operasyon 3 zaman bandında arar ve
bunları 2 saatlik randevuya bağlar. BTK işleri Turkcell hedef saatine göre kuyruğun önüne geçer.

Bu betik:
  1) BOSS açık iş export'undan (kullanıcının eklediği dosya) yalnız TOPLU kalibrasyon sayıları çıkarır,
  2) is_emri_analizi.json'daki parametrelerle stratejiyi olay-tabanlı (dakika çözünürlüklü)
     simüle eder: 28 gün, mevcut birikimle başlar, 5 tekrar, kapasite ve ulaşılabilirlik duyarlılığı,
  3) sonuçları cikti/strateji_dogrudan_sevk.json'a yazar.
Kişisel veri çıktıya yazılmaz; ağ çağrısı yoktur.
"""
import heapq
import zlib
import json
import math
import os
import random
import sys
from collections import defaultdict

import numpy as np

BURADA = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BURADA)
CIKTI = os.path.join(BURADA, "cikti")
BOSS = r"C:\Users\EXT03426951\Desktop\TeknikTaskDetayRaporu.xlsx"

# ------------------------------------------------------------------ parametreler
AN = json.load(open(os.path.join(CIKTI, "is_emri_analizi.json"), encoding="utf-8"))
P = AN["parametreler"]

GUN_ORT = {0: 323.5, 1: 332.0, 2: 417.0, 3: 319.5, 4: 299.5, 5: 384.0, 6: 182.0}  # Pzt..Paz (ANLATILAN)
SAAT_PROFIL = {int(k): v for k, v in P["varis_saat_profili_mevcut"].items()}
for h in range(24):
    SAAT_PROFIL.setdefault(h, 0.004)
_s = sum(SAAT_PROFIL.values())
SAAT_PROFIL = {h: v / _s for h, v in SAAT_PROFIL.items()}

# tip: (günlük ort, şerit, btk, fox_hedef_saat, p_duzeldi_telefonda, p_sebeke, döngü_dk)
TIP = {
    "BAGLANTI":          (142.0, "saha", True, 12, 0.286, 0.112, 30),
    "TV_ARIZA":          (29.2,  "saha", True, 6,  0.341, 0.143, 30),
    "DOPING_ARIZA":      (8.6,   "saha", True, 24, 0.337, 0.151, 30),
    "ARAMA":             (0.8,   "saha", True, 12, 0.25,  0.125, 30),
    "MODEM_DEGISIKLIGI": (31.9,  "saha", False, None, 0.01, 0.0, 35),
    "UCRETLENDIRME":     (11.1,  "saha", False, None, 0.01, 0.0, 35),
    "IKINCI_DONANIM":    (5.4,   "saha", False, None, 0.0,  0.0, 55),
    "EVRAK_SOSYAL":      (4.8,   "saha", False, None, 0.0,  0.0, 25),
    "SUPERBOX_MODEM":    (2.4,   "saha", False, None, 0.0,  0.0, 40),
    "STB_DEGISIKLIGI":   (2.0,   "saha", False, None, 0.0,  0.0, 35),
    "CIHAZ_GERI_ALIM":   (1.9,   "saha", False, 48,   0.0,  0.0, 25),
    "EVRAK_TURKSAT":     (0.8,   "saha", False, None, 0.0,  0.0, 25),
    "KANAL_SIKAYETI":    (49.2,  "masa", True, 24, 0.98, 0.0, 0),
    "SORU_CEVAP":        (1.9,   "masa", False, None, 1.0, 0.0, 0),
    "CIHAZ_IADE":        (34.6,  "lojistik", False, 24, 0.0, 0.0, 15),  # toplama = dolgu durağı (<=300 m sapma)
}
TIPLER = list(TIP)
TIP_W = np.array([TIP[k][0] for k in TIPLER]) / sum(TIP[k][0] for k in TIPLER)

# müşteri ulaşılabilirlik sınıfları (deneme başına açma olasılığı). Kalibrasyon: tek operasyon
# aramasında ~%50-60 ulaşma (BOSS: son 6 saatte açılan saha işlerinin %62'sine 'ulaşılamadı' notu
# düşülmüş, bunların bir kısmı da kapanmış işlerin dışında kalmış), kullanıcının "250-300 işte ~50
# ulaşılamayan" gözlemi (teknisyen 2 denemesinden sonra ~%17-22).
ULASIM = {
    "baz":    [(0.60, 0.80), (0.25, 0.45), (0.15, 0.12)],
    "dusuk":  [(0.50, 0.75), (0.30, 0.40), (0.20, 0.10)],
    "yuksek": [(0.70, 0.85), (0.20, 0.50), (0.10, 0.15)],
}
AKSAM_CARPAN = 1.5          # 17:30-20:00 bandında orta/zor sınıf açma olasılığı çarpanı
KAPI_UYGUN = 0.35           # ulaşılamayan BTK işinin aynı bina/<=150 m komşu durakta olma olasılığı
KAPI_EVDE = 0.35            # kapı çalındığında evde bulunma
KAPI_DK = 15
ARAMA_DK_TEK = 1.5          # teknisyen arama başına EK süre: sıradaki müşteri mevcut işin son 10 dk'sında (senkron/test beklerken) aranır; gözlenen 29 dk/kapanış döngüsü bugünkü aramaları zaten içeriyor
MUSAIT_DEGIL = 0.12         # ulaşılan müşterinin 'şimdi değil, şu saatte' demesi -> teknisyen kendisi randevu yazar
NO_SHOW = 0.08              # randevulu işte kapıda yok (30 dk önce teyit aramasına rağmen)
SEBEKE_YAKALAMA = 0.40      # küme alarmı (nöbetçi iş) ile şebeke kaynaklı işin ziyaretsiz yakalanma oranı
SMS_GERI_DONUS = 0.25       # 3 başarısız denemeden sonra SMS'e 24 s içinde geri dönüş
OPS_DENEME_DK = 5           # operasyon arama + BOSS kaydı
TEKRAR_ARIZA = 0.35         # 15 günde tekrar arıza (kıdemli teknisyen kuralı; simülasyonda süre +%10)


def gun_saat(t):
    return int(t // 1440), (t % 1440) / 60.0


class Is:
    __slots__ = ("id", "tip", "serit", "btk", "t0", "fox", "sinif", "durum", "kapanis", "kapanis_turu",
                 "ops_deneme", "randevu", "birikim", "ziyaret", "bosa")

    def __init__(self, i, tip, t0, sinif, birikim=False):
        self.id = i; self.tip = tip; self.t0 = t0; self.sinif = sinif; self.birikim = birikim
        self.serit = TIP[tip][1]; self.btk = TIP[tip][2]; self.fox = TIP[tip][3]
        self.durum = "havuz"; self.kapanis = None; self.kapanis_turu = None
        self.ops_deneme = 0; self.randevu = None; self.ziyaret = 0; self.bosa = 0

    def son24(self):
        return self.t0 + 1440

    def hedef(self):
        if self.tip == "CIHAZ_IADE":
            return self.t0 + 48 * 60  # dolgu: rota planında 48 s ufukla, yakından geçerken
        h = self.fox if (self.fox and self.btk) else 24
        return self.t0 + min(h, 24) * 60


class Sim:
    def __init__(self, seed, n_gunduz=11, n_aksam=2, n_pazar=6, ops_arayici=2, masa_arayici=2,
                 kurtarma_arayici=3, kurtarma_gun=10, ulasim="baz", gun=28, varyant="DSIR",
                 birikim=True):
        self.r = random.Random(seed); self.np = np.random.default_rng(seed)
        self.n_gunduz = n_gunduz; self.n_aksam = n_aksam; self.n_pazar = n_pazar
        self.ops_arayici = ops_arayici; self.masa_arayici = masa_arayici
        self.kurtarma_arayici = kurtarma_arayici; self.kurtarma_gun = kurtarma_gun
        self.ul = ULASIM[ulasim]; self.gun = gun; self.varyant = varyant
        self.isler = []; self.havuz = set(); self.randevu_havuz = set()
        self.ops_q = []  # (zaman, oncelik, sayac, is)
        self.masa_q = []
        self.sayac = 0
        self.say = defaultdict(float)
        self.gunluk = defaultdict(lambda: defaultdict(float))
        self.bas_dow = 2  # 30 Eylül 2026 Çarşamba
        self.birikim = birikim

    # ---------------------------------------------------------- yardımcılar
    def sinif_sec(self):
        x = self.r.random(); c = 0
        for i, (w, _) in enumerate(self.ul):
            c += w
            if x < c:
                return i
        return len(self.ul) - 1

    def acar_mi(self, j, t):
        p = self.ul[j.sinif][1]
        _, h = gun_saat(t)
        if j.sinif > 0 and 17.5 <= h < 20.0:
            p = min(0.9, p * AKSAM_CARPAN)
        return self.r.random() < p

    def kapat(self, j, t, tur):
        if j.kapanis is not None:
            return
        j.kapanis = t; j.kapanis_turu = tur; j.durum = "kapandi"
        self.havuz.discard(j); self.randevu_havuz.discard(j)
        d, _ = gun_saat(t)
        self.gunluk[d]["kapanan"] += 1
        self.gunluk[d]["kapanan_" + tur] += 1

    def ops_ekle(self, j, t, q=None):
        q = self.ops_q if q is None else q
        self.sayac += 1
        pr = 0 if j.btk else 1
        if j.birikim:
            pr += 2
        heapq.heappush(q, (t, pr, self.sayac, j))
        j.durum = "ops"

    def sonraki_band(self, t, n):
        """n. operasyon denemesinin en erken zamanı: 1 -> hemen, 2 -> +60 dk, 3 -> akşam bandı 17:30,
        4 -> ertesi sabah 08:30, 5 -> ertesi akşam (yalnız BTK), sonra askı uyanma +2 gün."""
        d, h = gun_saat(t)
        if n == 1:
            return t
        if n == 2:
            return t + 60
        if n == 3:
            return d * 1440 + 17.5 * 60 if h < 17.5 else (d + 1) * 1440 + 8.5 * 60
        if n == 4:
            return (d + 1) * 1440 + 8.5 * 60 if h >= 12 else d * 1440 + 17.5 * 60
        return (d + 1) * 1440 + 17.5 * 60

    def randevu_ver(self, j, t, aksam_tercih):
        """Operasyon/teknisyen ulaşınca: aynı gün (+3 s, 18:00'e kadar) ya da akşam bandı ya da ertesi gün."""
        d, h = gun_saat(t)
        dow = (self.bas_dow + d) % 7
        if aksam_tercih and self.n_aksam > 0 and h < 17 and dow != 6:
            s = d * 1440 + 18 * 60
        elif h + 3 <= 17 and dow != 6:
            s = t + 180
        else:
            nd = d + 1
            if (self.bas_dow + nd) % 7 == 6 and not j.btk:
                nd += 1
            s = nd * 1440 + (9 + self.r.random() * 7) * 60
        j.randevu = s; j.durum = "randevu"
        self.randevu_havuz.add(j)
        self.gunluk[d]["randevu_verilen"] += 1

    # ---------------------------------------------------------- iş üretimi
    def uret(self):
        i = 0
        if self.birikim:
            # 29.09 anlık birikim (mevcut müşteri, toplu sayımlardan): saha 556, kanal 179, iade 218
            yas_kov = [(0, 24, 254), (24, 48, 107), (48, 72, 156), (72, 168, 170), (168, 720, 244), (720, 1440, 22)]
            w = np.array([k[2] for k in yas_kov], float); w /= w.sum()
            bir = ([("BAGLANTI", 234, 212), ("TV_ARIZA", 58, 53), ("MODEM_DEGISIKLIGI", 58, 53),
                    ("IKINCI_DONANIM", 125, 8), ("UCRETLENDIRME", 24, 20), ("DOPING_ARIZA", 19, 19),
                    ("EVRAK_SOSYAL", 14, 9), ("SUPERBOX_MODEM", 12, 4), ("STB_DEGISIKLIGI", 12, 3),
                    ("KANAL_SIKAYETI", 179, 158), ("CIHAZ_IADE", 218, 12)])
            for tip, n, n_ul in bir:
                for k in range(n):
                    kv = yas_kov[self.np.choice(len(yas_kov), p=w)]
                    yas = self.r.uniform(kv[0], kv[1]) * 60
                    j = Is(i, tip, -yas, self.sinif_sec(), birikim=True); i += 1
                    # 'ulaşılamadı' notlular zor/orta sınıfa kayık
                    if k < n_ul:
                        j.sinif = max(j.sinif, 1 if self.r.random() < 0.6 else 2)
                    self.isler.append(j)
                    if j.serit == "masa" or j.serit == "lojistik":
                        self.ops_ekle(j, 0, self.masa_q)
                    elif k < n_ul:
                        self.ops_ekle(j, 0)
                    else:
                        self.havuz.add(j); j.durum = "havuz"
        self.gelis = []
        saatler = np.array([SAAT_PROFIL[h] for h in range(24)])
        for d in range(self.gun):
            dow = (self.bas_dow + d) % 7
            n = max(0, int(round(self.np.normal(GUN_ORT[dow], 0.15 * GUN_ORT[dow]))))
            hs = self.np.choice(24, size=n, p=saatler)
            tips = self.np.choice(len(TIPLER), size=n, p=TIP_W)
            for h, ti in zip(hs, tips):
                t = d * 1440 + h * 60 + self.r.random() * 60
                j = Is(i, TIPLER[ti], t, self.sinif_sec()); i += 1
                self.isler.append(j); self.gelis.append((t, j))
        self.gelis.sort(key=lambda x: x[0])

    def giris(self, j, t):
        """Giriş kuralı (aramasız): masa/lojistik -> masa kuyruğu; saha -> teknisyen havuzu."""
        if j.serit in ("masa", "lojistik"):
            self.ops_ekle(j, t, self.masa_q)
            return
        # küme alarmı: şebeke kaynaklı işlerin bir kısmı nöbetçi iş ile ziyaretsiz yakalanır
        if self.varyant == "DSIR" and self.r.random() < TIP[j.tip][5] * SEBEKE_YAKALAMA:
            j.durum = "sebeke_bekle"
            self.sayac += 1
            heapq.heappush(self.bekleyen, (t + 180 + self.r.random() * 300, self.sayac, j))
            return
        self.havuz.add(j); j.durum = "havuz"

    # ---------------------------------------------------------- teknisyen seçimi
    def oncelik(self, j, t):
        if j.durum == "randevu":
            return (0, j.randevu)
        yeni = (t - j.t0) < (2880 if j.tip == "CIHAZ_IADE" else 1440)
        if yeni:
            return (1, j.hedef(), 0 if j.btk else 1)
        return (3, 0 if j.btk else 1, j.t0)

    @staticmethod
    def _eski_btk(j, t):
        return j.btk and (t - j.t0) >= 1440

    def sec(self, t, tek, pazar):
        # 1) penceresi açılmış randevu
        ad = [j for j in self.randevu_havuz if j.randevu - 30 <= t]
        if ad:
            return min(ad, key=lambda j: j.randevu)
        if tek["aksam"] and self.randevu_havuz:
            yakin = [j for j in self.randevu_havuz if j.randevu - 30 <= t + 60]
            if yakin:
                return None  # akşamcı randevu için boşta bekler (dolgu yapmaz)
        if not self.havuz:
            return None
        aday = self.havuz
        if pazar:
            aday = [j for j in aday if j.btk]
            if not aday:
                return None
        # kurtarma kotası: her 3. seçim 24 s'i geçmiş BTK'dan (en eski önce); diğer birikim yalnız
        # 6 saat içinde 24 s'i dolacak yeni iş yokken (koruma kuralı: 'önce musluğu kapat')
        tek["secim"] += 1
        if tek["secim"] % 3 == 0:
            eb = [j for j in aday if self._eski_btk(j, t)]
            if eb:
                return min(eb, key=lambda j: j.t0)
        yeniler = [j for j in aday if (t - j.t0) < (2880 if j.tip == "CIHAZ_IADE" else 1440)]
        if yeniler:
            return min(yeniler, key=lambda j: self.oncelik(j, t))
        return min(aday, key=lambda j: self.oncelik(j, t))

    def ziyaret_sure(self, j, rand):
        m = TIP[j.tip][6]
        yog = len(self.havuz)
        if rand:
            m *= 1.25
        elif yog < 60:
            m *= 1.2
        if j.btk and self.r.random() < TEKRAR_ARIZA * 0.3:
            m *= 1.1
        return max(8.0, self.np.lognormal(math.log(m) - 0.125, 0.5))

    def teknisyen_is(self, t, tek, pazar):
        """Teknisyen boşaldığında: sonraki işi seç, ara, sonuca göre süre döndür (dk)."""
        j = self.sec(t, tek, pazar)
        if j is None:
            return None, 10.0
        d, _ = gun_saat(t)
        rand = j.durum == "randevu"
        self.havuz.discard(j); self.randevu_havuz.discard(j)
        if self.varyant == "HAM":
            # ham fikir: aramadan gider; evde değilse boşa ziyaret
            evde = self.r.random() < [0.85, 0.5, 0.2][j.sinif] if not rand else self.r.random() > NO_SHOW
            self.gunluk[d]["ziyaret"] += 1
            if not evde:
                j.bosa += 1; self.gunluk[d]["bosa_ziyaret"] += 1
                self.ops_ekle(j, t + 25, None)
                return j, 25.0
            if self.r.random() < TIP[j.tip][4]:
                sure = 20.0  # gitti, düzelmiş buldu
                self.kapat(j, t + sure, "saha_duzelmis")
                return j, sure
            sure = self.ziyaret_sure(j, rand)
            self.kapat(j, t + sure, "saha")
            return j, sure
        # DSİR: yola çıkmadan teyit/teşhis araması (randevuluda 30 dk önce teyit)
        self.gunluk[d]["tek_arama"] += 1
        sure = ARAMA_DK_TEK
        if rand:
            if self.r.random() < NO_SHOW:
                self.gunluk[d]["no_show"] += 1
                j.ops_deneme = max(j.ops_deneme, 1)
                self.ops_ekle(j, t + sure, None)
                return j, sure
            v = self.ziyaret_sure(j, True)
            self.gunluk[d]["ziyaret"] += 1
            self.kapat(j, t + sure + v, "saha_randevu")
            return j, sure + v
        ulasti = self.acar_mi(j, t)
        if not ulasti:
            self.gunluk[d]["tek_arama"] += 1
            sure += ARAMA_DK_TEK
            ulasti = self.acar_mi(j, t + 10)
        if not ulasti:
            if j.btk and self.r.random() < KAPI_UYGUN:
                sure += KAPI_DK
                self.gunluk[d]["kapi_calma"] += 1
                if self.r.random() < KAPI_EVDE:
                    v = self.ziyaret_sure(j, False)
                    self.gunluk[d]["ziyaret"] += 1
                    self.kapat(j, t + sure + v, "saha_kapi")
                    return j, sure + v
                self.gunluk[d]["bosa_ziyaret"] += 1
            self.gunluk[d]["teknisyen_ulasamadi"] += 1
            self.ops_ekle(j, t + sure, None)
            return j, sure
        if self.r.random() < TIP[j.tip][4]:
            self.kapat(j, t + sure + 2, "telefonda_duzeldi")
            return j, sure + 2
        if self.r.random() < MUSAIT_DEGIL:
            self.randevu_ver(j, t, aksam_tercih=j.sinif > 0)
            self.gunluk[d]["tek_randevu"] += 1
            return j, sure + 1
        v = self.ziyaret_sure(j, False)
        self.gunluk[d]["ziyaret"] += 1
        tur = "saha_sebeke" if self.r.random() < TIP[j.tip][5] * (1 - SEBEKE_YAKALAMA) else "saha"
        self.kapat(j, t + sure + v, tur)
        return j, sure + v

    # ---------------------------------------------------------- operasyon araması
    def ops_islem(self, t, q, kapasite, masa):
        d, h = gun_saat(t)
        yapilan = 0
        ertele = []
        hz = self.hazir[id(q)]
        while q and q[0][0] <= t:  # vadesi gelenler öncelik yığınına (BTK önce, sonra yeni, sonra birikim)
            tt, pr, sc, j = heapq.heappop(q)
            heapq.heappush(hz, (pr, tt, sc, j))
        while hz and yapilan < kapasite:
            pr, _, _, j = heapq.heappop(hz)
            if j.kapanis is not None or j.durum not in ("ops", "askida"):
                continue
            # masa kuyruğunda birikim, yeni iş kalmadıysa ya da kurtarma arayıcısı varsa
            yapilan += 1
            j.ops_deneme += 1
            self.gunluk[d]["masa_deneme" if masa else "ops_deneme"] += 1
            if j.serit == "lojistik":
                # cihaz iade: ulaşılırsa %50 'kendisi teslim/kargo' -> ofiste kapanır, kalanı teknisyen toplama durağı;
                # 2 denemede ulaşılamazsa aramadan toplama durağı (dolgu)
                if self.acar_mi(j, t):
                    if self.r.random() < 0.5:
                        self.kapat(j, t, "ofis_lojistik")
                    else:
                        j.serit = "saha"; self.havuz.add(j); j.durum = "havuz"
                elif j.ops_deneme >= 2:
                    j.serit = "saha"; self.havuz.add(j); j.durum = "havuz"
                else:
                    ertele.append((self.sonraki_band(t, 3), pr, j))
                continue
            if self.acar_mi(j, t):
                if self.r.random() < TIP[j.tip][4]:
                    self.kapat(j, t, "ofis_telefon")
                elif j.serit == "masa":
                    self.kapat(j, t, "ofis_telefon")
                else:
                    self.randevu_ver(j, t, aksam_tercih=j.sinif > 0)
                continue
            limit = 5 if j.btk else 3
            if j.ops_deneme >= limit + (2 if j.durum == "askida" else 0):
                self.kapat(j, t, "ulasilamadi_kapatildi")
                continue
            if j.ops_deneme == 3:
                # SMS + geri dönüş şansı
                self.gunluk[d]["sms"] += 1
                if self.r.random() < SMS_GERI_DONUS:
                    tt = t + self.r.uniform(60, 1200)
                    self.sayac += 1
                    heapq.heappush(self.geri_donus, (tt, self.sayac, j))
                if not j.btk:
                    j.durum = "askida"
                    ertele.append((t + 2 * 1440, pr, j))
                    continue
            ertele.append((self.sonraki_band(t, j.ops_deneme + 1), pr, j))
        for tt, pr, j in ertele:
            if j.kapanis is None and j.durum != "randevu":
                self.sayac += 1
                heapq.heappush(q, (tt, pr, self.sayac, j))
        return yapilan

    # ---------------------------------------------------------- ana döngü
    def calis(self):
        self.uret()
        self.bekleyen = []; self.geri_donus = []
        self.hazir = {id(self.ops_q): [], id(self.masa_q): []}
        gi = 0
        tekler = []
        for k in range(self.n_gunduz):
            tekler.append(dict(ad=f"g{k}", aksam=False, serbest=0.0, secim=0))
        for k in range(self.n_aksam):
            tekler.append(dict(ad=f"a{k}", aksam=True, serbest=0.0, secim=0))
        ADIM = 5.0
        t = 0.0
        son = self.gun * 1440
        while t < son:
            d, h = gun_saat(t)
            dow = (self.bas_dow + d) % 7
            pazar = dow == 6
            while gi < len(self.gelis) and self.gelis[gi][0] <= t:
                self.giris(self.gelis[gi][1], self.gelis[gi][0]); gi += 1
            while self.bekleyen and self.bekleyen[0][0] <= t:
                _, _, j = heapq.heappop(self.bekleyen)
                if j.kapanis is None:
                    self.kapat(j, t, "sebeke_toplu")
            while self.geri_donus and self.geri_donus[0][0] <= t:
                _, _, j = heapq.heappop(self.geri_donus)
                if j.kapanis is None and j.durum != "randevu":
                    if j.serit != "saha" or self.r.random() < TIP[j.tip][4]:
                        self.kapat(j, t, "ofis_telefon")  # geri arayan müşteri: masa işi/düzeldi -> kapanır
                    else:
                        self.randevu_ver(j, t, aksam_tercih=True)
            # teknisyenler
            n_pazar_aktif = 0
            for i_t, tek in enumerate(tekler):
                if tek["aksam"]:
                    vardiya = 12.0 <= h < 21.0 and not (16.0 <= h < 16.5)
                else:
                    vardiya = 8.5 <= h < 18.5 and not (12.5 <= h < 13.5)
                if pazar:
                    if tek["aksam"] or n_pazar_aktif >= self.n_pazar:
                        continue
                    n_pazar_aktif += 1
                elif dow == 5 and i_t % 10 == 9:
                    continue  # cumartesi ~%10 izin
                if not vardiya or tek["serbest"] > t:
                    continue
                # günlük müsaitlik: gündüzcülerin ~%10'u rastgele gün izinli
                if not tek["aksam"] and (zlib.crc32(f"{tek['ad']}-{d}".encode()) % 10 == 0):
                    continue
                j, sure = self.teknisyen_is(t, tek, pazar)
                tek["serbest"] = t + sure
                if j is not None:
                    self.gunluk[d]["tek_dk"] += sure
            # operasyon (istisna kuyruğu) ve masa
            if not pazar and 8.5 <= h < 19.5:
                kap_ops = self.ops_arayici * ADIM / OPS_DENEME_DK
                kap_masa = self.masa_arayici * ADIM / OPS_DENEME_DK
                if d < self.kurtarma_gun:
                    kap_ops += self.kurtarma_arayici * ADIM / OPS_DENEME_DK * 0.6
                    kap_masa += self.kurtarma_arayici * ADIM / OPS_DENEME_DK * 0.4
                self._ops_art = getattr(self, "_ops_art", 0) + kap_ops
                self._masa_art = getattr(self, "_masa_art", 0) + kap_masa
                n1 = int(self._ops_art); self._ops_art -= n1
                n2 = int(self._masa_art); self._masa_art -= n2
                y1 = self.ops_islem(t, self.ops_q, n1, False)
                y2 = self.ops_islem(t, self.masa_q, n2, True)
                if y2 < n2:  # masa boşsa istisna kuyruğuna yardım
                    self.ops_islem(t, self.ops_q, n2 - y2, False)
            # gün sonu anlık sayım (23:55)
            if abs((t % 1440) - (1440 - ADIM)) < 1e-6:
                acik = [j for j in self.isler if j.kapanis is None and j.t0 <= t]
                self.gunluk[d]["acik"] = len(acik)
                self.gunluk[d]["acik_24s_ustu"] = sum(1 for j in acik if t - j.t0 >= 1440)
                self.gunluk[d]["acik_btk_24s_ustu"] = sum(1 for j in acik if j.btk and t - j.t0 >= 1440)
                self.gunluk[d]["ops_kuyruk"] = sum(1 for x in self.ops_q + self.hazir[id(self.ops_q)] if x[3].kapanis is None)
            t += ADIM
        return self.ozet()

    def ozet(self, bas=7, bit=21):
        """Kararlı dönem: bas..bit günlerinde GELEN yeni işler (birikim hariç)."""
        J = [j for j in self.isler if not j.birikim and bas * 1440 <= j.t0 < bit * 1440]
        R = {}

        def oran(js, saat):
            if not js:
                return None
            return round(sum(1 for j in js if j.kapanis is not None and j.kapanis - j.t0 <= saat * 60) / len(js), 3)
        R["n_yeni"] = len(J)
        R["uyum_24s_tum"] = oran(J, 24)
        R["uyum_12s_tum"] = oran(J, 12)
        R["uyum_48s_tum"] = oran(J, 48)
        saha = [j for j in J if TIP[j.tip][1] == "saha"]
        R["uyum_24s_saha"] = oran(saha, 24)
        btk = [j for j in J if j.btk and TIP[j.tip][1] == "saha"]
        R["uyum_24s_btk_saha"] = oran(btk, 24)
        R["uyum_fox_hedef_btk"] = round(sum(1 for j in btk if j.kapanis is not None and j.kapanis <= j.hedef()) / max(1, len(btk)), 3)
        R["tip_24s"] = {k: oran([j for j in J if j.tip == k], 24) for k in
                        ["BAGLANTI", "TV_ARIZA", "MODEM_DEGISIKLIGI", "KANAL_SIKAYETI", "CIHAZ_IADE", "UCRETLENDIRME"]}
        tv = [j for j in J if j.tip == "TV_ARIZA"]
        R["tv_6s"] = oran(tv, 6)
        bg = [j for j in J if j.tip == "BAGLANTI"]
        R["baglanti_12s"] = oran(bg, 12)
        kt = defaultdict(int)
        for j in J:
            kt[j.kapanis_turu or "acik"] += 1
        R["kapanis_turu_pay"] = {k: round(v / len(J), 3) for k, v in sorted(kt.items(), key=lambda x: -x[1])}
        gun = range(bas, bit)
        dow_ok = [d for d in gun if (self.bas_dow + d) % 7 != 6]

        def gort(k, g=dow_ok):
            return round(float(np.mean([self.gunluk[d][k] for d in g])), 1)
        R["gunluk_is_gunu"] = {k: gort(k) for k in ["ops_deneme", "masa_deneme", "tek_arama", "teknisyen_ulasamadi",
                                                     "randevu_verilen", "tek_randevu", "ziyaret", "bosa_ziyaret",
                                                     "kapi_calma", "no_show", "sms", "kapanan", "tek_dk"]}
        tek_sayisi = self.n_gunduz * 0.9 + self.n_aksam
        R["teknisyen_dk_kullanim"] = round(R["gunluk_is_gunu"]["tek_dk"] / (tek_sayisi * 540), 3)
        R["bosa_ziyaret_orani"] = round(R["gunluk_is_gunu"]["bosa_ziyaret"] /
                                        max(1, R["gunluk_is_gunu"]["ziyaret"] + R["gunluk_is_gunu"]["bosa_ziyaret"]), 3)
        R["acik_24s_ustu_gun"] = {d: int(self.gunluk[d]["acik_24s_ustu"]) for d in range(self.gun)}
        R["acik_btk_24s_ustu_gun"] = {d: int(self.gunluk[d]["acik_btk_24s_ustu"]) for d in range(self.gun)}
        R["acik_gun"] = {d: int(self.gunluk[d]["acik"]) for d in range(self.gun)}
        ilk100 = [d for d in range(self.gun) if self.gunluk[d]["acik_24s_ustu"] < 100]
        R["24s_ustu_100_alti_ilk_gun"] = ilk100[0] if ilk100 else None
        B = [j for j in self.isler if j.birikim]
        R["birikim_kapanan_14g"] = round(sum(1 for j in B if j.kapanis is not None and j.kapanis < 14 * 1440) / len(B), 3) if B else None
        return R


def kalibrasyon():
    """BOSS açık export'undan yalnız toplu sayılar (kişisel veri yok)."""
    import pandas as pd
    import taksonomi as TX
    b = pd.read_excel(BOSS, sheet_name="Task Detail Report")  # kullanıcı dosyaya Sayfa1 ekledi
    ref = b["Task Başlangıç Tarihi"].max().ceil("min")
    b["kod"] = b["Task Adı"].map(TX.boss_kod)
    b["sahip"] = b["kod"].map(lambda k: TX.KOD[k]["sahip"] if k in TX.KOD else "bilinmeyen")
    b["saha"] = b["kod"].map(lambda k: TX.KOD[k]["saha"] if k in TX.KOD else "?")
    b["yas"] = (ref - b["Task Başlangıç Tarihi"]).dt.total_seconds() / 3600
    b["ul"] = b["Son Açıklama"].map(lambda s: isinstance(s, str) and "ULASILAMA" in TX.norm(s))
    kul = b["En Son İşlem Yapan Kullanıcı"].astype(str).map(TX.norm)
    tekn = set(b["Ekip"].dropna().astype(str).map(TX.norm)) | set(b["Teknisyen"].dropna().astype(str).map(TX.norm))
    m = b[(b.sahip == "mevcut_musteri") & (b.saha != "hayir") & (b.kod != "CIHAZ_IADE")]
    mm = b[b.sahip == "mevcut_musteri"]
    r = m[m["Randevu Başlangıç Tarihi"].notna()]
    ac2r = (r["Randevu Başlangıç Tarihi"] - r["Task Başlangıç Tarihi"]).dt.total_seconds() / 3600
    ul_kul = kul[mm.index][mm.ul]
    ek = b.loc[b.sahip == "mevcut_musteri", "Ekip"].dropna().value_counts()
    out = dict(
        export_satir=int(len(b)), export_an=str(ref),
        mevcut_saha_acik=int(len(m)),
        ekip_basina_acik_is={"ekip_sayisi": int(len(ek)), "p25": float(ek.quantile(.25)), "p50": float(ek.median()),
                             "p75": float(ek.quantile(.75)), "max": int(ek.max()), "atanmis_toplam": int(ek.sum()),
                             "atanmamis": int(b.loc[b.sahip == "mevcut_musteri", "Ekip"].isna().sum())},
        yas_0_6s={"n": int((m.yas < 6).sum()), "ulasilamadi_notlu": int(((m.yas < 6) & m.ul).sum()),
                  "ekip_atanmis": int(((m.yas < 6) & m.Ekip.notna()).sum())},
        yas_6_24s={"n": int(((m.yas >= 6) & (m.yas < 24)).sum()),
                   "ulasilamadi_notlu": int(((m.yas >= 6) & (m.yas < 24) & m.ul).sum())},
        ulasilamadi_notu_mevcut=int(mm.ul.sum()),
        ulasilamadi_notu_kalip="'BOSS üzerinden arama sağlandı, ulaşılamadı' (hazır metin)",
        ulasilamadi_notu_tek_kullanici_payi=round(float(ul_kul.value_counts().iloc[0] / len(ul_kul)), 2),
        ulasilamadi_notu_teknisyen_yazdi=int((mm.ul & kul[mm.index].isin(tekn)).sum()),
        ulasilamadi_notlu_randevulu=int((mm.ul & (mm["Randevu Durumu"].astype(str).str.strip() == "Randevulu")).sum()),
        ulasilamadi_notlu_dilimi_gecmis=int((mm.ul & (mm["Randevu Bitiş Tarihi"] < ref)).sum()),
        acilis_randevu_saat_mevcut_saha={str(k): round(float(v), 1) for k, v in ac2r.quantile([.25, .5, .75, .9]).items()},
        randevu_baslangic_saati_mevcut_saha={int(k): int(v) for k, v in
                                             r["Randevu Başlangıç Tarihi"].dt.hour.value_counts().sort_index().items()},
        yorum=("Bugünkü fiili süreç 'önce bir kez ara, ulaşamazsan yine de ekibe yaz' şeklinde: hazır 'ulaşılamadı' notlarının "
               "~%90'ı tek bir ofis kullanıcısından; son 6 saatte açılan saha işlerinin ~%60'ında bu not var, yani tek "
               "ofis aramasının ulaşma oranı ~%40-55. Not düşülen işler 11:00 gibi varsayılan dilimle ekibe yazılıyor, "
               "dilim geçiyor ve iş açık kalıyor (ulaşılamadı notlu işlerin çoğunun dilimi geçmiş)."),
    )
    return out


ILK_EXPORT_KALIBRASYON = dict(
    kaynak="TeknikTaskDetayRaporu.xlsx ilk hali (2.567 satır, 29.09 16:45) - bu betiğin ilk çalıştırmasında ölçüldü",
    mevcut_saha_acik_0_6s=77, bunlarin_ulasilamadi_notlu=48, bunlarin_ekip_atanmis=60,
    mevcut_saha_acik_6_24s=100, bunlarin_ulasilamadi_notlu_6_24s=95,
    ulasilamadi_notu_mevcut=530, not_kalibi="BOSS üzerinden arama sağlandı, ulaşılamadı (hazır metin, iki yazımı)",
    notun_tek_ofis_kullanicisi_payi=0.90, notu_teknisyen_yazan=40,
    ulasilamadi_notlu_randevulu=302, ulasilamadi_notlu_dilimi_gecmis=266,
    acilis_randevu_saat_mevcut_saha={"p25": 1.1, "p50": 2.6, "p75": 16.6, "p90": 69.5},
    randevu_dilim_baslangici_mevcut={"11:00": 189, "15:00": 38, "18:00": 30, "12:00": 25, "diger": 73},
    ayni_lokasyonda_2plus_acik_btk=13,
)


def main():
    try:
        kal = kalibrasyon()
    except Exception as e:  # dosya yeniden dışa aktarılmış/açık olabilir
        kal = {"hata": str(e)}
    senaryolar = {
        "S0_bugunku_kapasite_DSIR": dict(n_gunduz=11, n_aksam=0, n_pazar=5, kurtarma_arayici=0),
        "S1_onerilen_DSIR": dict(n_gunduz=11, n_aksam=2, n_pazar=6, kurtarma_arayici=3),
        "S2_onerilen_DSIR_ulasim_dusuk": dict(n_gunduz=11, n_aksam=2, n_pazar=6, kurtarma_arayici=3, ulasim="dusuk"),
        "S3_onerilen_DSIR_ulasim_yuksek": dict(n_gunduz=11, n_aksam=2, n_pazar=6, kurtarma_arayici=3, ulasim="yuksek"),
        "S4_genis_DSIR_13+2": dict(n_gunduz=13, n_aksam=2, n_pazar=6, kurtarma_arayici=3),
        "S6_genis_DSIR_15+2": dict(n_gunduz=15, n_aksam=2, n_pazar=7, kurtarma_arayici=3),
        "S7_genis_DSIR_15+2_ulasim_dusuk": dict(n_gunduz=15, n_aksam=2, n_pazar=7, kurtarma_arayici=3, ulasim="dusuk"),
        "S8_ham_fikir_aramasiz_15+2": dict(n_gunduz=15, n_aksam=2, n_pazar=7, kurtarma_arayici=3, varyant="HAM"),
        "S9_hedef_DSIR_17+2": dict(n_gunduz=17, n_aksam=2, n_pazar=8, kurtarma_arayici=3),
        "S10_hedef_DSIR_17+2_ulasim_dusuk": dict(n_gunduz=17, n_aksam=2, n_pazar=8, kurtarma_arayici=3, ulasim="dusuk"),
        "S11_DSIR_19+2": dict(n_gunduz=19, n_aksam=2, n_pazar=9, kurtarma_arayici=3),
        "S12_DSIR_15+2_birikimsiz_kararli_durum": dict(n_gunduz=15, n_aksam=2, n_pazar=7, kurtarma_arayici=0, birikim=False),
        "S5_ham_fikir_aramasiz_11+2": dict(n_gunduz=11, n_aksam=2, n_pazar=6, kurtarma_arayici=3, varyant="HAM"),
    }
    sonuc = {}
    for ad, kw in senaryolar.items():
        R = [Sim(seed=s, **kw).calis() for s in range(5)]
        agg = {}
        for k in R[0]:
            v0 = R[0][k]
            if isinstance(v0, (int, float)) and v0 is not None:
                vals = [r[k] for r in R if r[k] is not None]
                agg[k] = round(float(np.mean(vals)), 3) if vals else None
            elif isinstance(v0, dict) and all(isinstance(x, (int, float)) or x is None for x in v0.values()):
                agg[k] = {kk: (round(float(np.mean([r[k][kk] for r in R if r[k].get(kk) is not None])), 3)
                               if any(r[k].get(kk) is not None for r in R) else None) for kk in v0}
            else:
                agg[k] = v0
        agg["parametre"] = kw
        seri = agg["acik_24s_ustu_gun"]
        alti = [d for d in sorted(seri) if seri[d] is not None and seri[d] < 100]
        agg["ort_24s_ustu_100_alti_ilk_gun"] = alti[0] if alti else None
        agg["ort_24s_ustu_son_hafta_ort"] = round(float(np.mean([seri[d] for d in range(21, 28)])), 1)
        sonuc[ad] = agg
        print(ad, "24s tum", agg["uyum_24s_tum"], "saha", agg["uyum_24s_saha"], "btk", agg["uyum_24s_btk_saha"],
              "fox", agg["uyum_fox_hedef_btk"], "ops/gun", agg["gunluk_is_gunu"]["ops_deneme"],
              "masa/gun", agg["gunluk_is_gunu"]["masa_deneme"],
              "randevu/gun", agg["gunluk_is_gunu"]["randevu_verilen"], "ulasamadi/gun", agg["gunluk_is_gunu"]["teknisyen_ulasamadi"],
              "bosa", agg["bosa_ziyaret_orani"], "kullanim", agg["teknisyen_dk_kullanim"],
              "100alti", agg["ort_24s_ustu_100_alti_ilk_gun"], "son_hafta", agg["ort_24s_ustu_son_hafta_ort"], "24s_ustu_g27", agg["acik_24s_ustu_gun"].get(27))
    out = dict(
        strateji="DSİR - Doğrudan Sevk + İstisna Randevu (kullanıcı fikrinin titiz hali)",
        referans_an="2026-09-29T16:45", simulasyon=dict(gun=28, tekrar=5, kararlı_donem="gün 7-20'de gelen yeni işler",
                                                         adim_dk=5, baslangic="30.09.2026 Çarşamba, 29.09 birikimiyle"),
        kalibrasyon_boss_ilk_export=ILK_EXPORT_KALIBRASYON,
        kalibrasyon_boss_guncel_export=kal,
        varsayimlar=dict(ulasim_siniflari=ULASIM, aksam_carpan=AKSAM_CARPAN, kapi_uygun=KAPI_UYGUN, kapi_evde=KAPI_EVDE,
                         musait_degil=MUSAIT_DEGIL, no_show=NO_SHOW, sebeke_yakalama=SEBEKE_YAKALAMA,
                         sms_geri_donus=SMS_GERI_DONUS, ops_deneme_dk=OPS_DENEME_DK, teknisyen_arama_dk=ARAMA_DK_TEK,
                         vardiya=dict(gunduz="08:30-18:30 (12:30-13:30 mola)", aksam="12:00-21:00 (16:00-16:30 mola)",
                                      ops="08:30-19:30"),
                         tip=dict((k, dict(gunluk=v[0], serit=v[1], btk=v[2], fox_hedef_s=v[3], p_duzeldi=v[4],
                                           p_sebeke=v[5], dongu_dk=v[6])) for k, v in TIP.items())),
        senaryolar=sonuc,
    )
    with open(os.path.join(CIKTI, "strateji_dogrudan_sevk.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)


if __name__ == "__main__":
    main()
