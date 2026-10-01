# -*- coding: utf-8 -*-
"""STRATEJİ: BÖLGE DALGALARI / ÖNCE KAPASİTE — bölge üretimi + gün içi (dakika) simülasyonu.

Fikir: mevcut-müşteri saha işleri sabit bölgelere (zone) bölünür; her bölgenin her gün 5 dilimlik
takvimi vardır (S1 09-11, S2 11-13 = SABAH dalgası; S3 14-16, S4 16-18 = ÖĞLE dalgası; S5 18-20 =
AKŞAM, yalnız akşam nöbetçisi). İş, içe aktarımda (intake) ARAMADAN bölge takviminde en erken uygun
2 saatlik dilime yazılır, müşteriye mevcut Turkcell/BOSS kanalından SMS gider. Teknisyen yalnız
yola çıkarken tek 'teyit + ön-teşhis' çağrısı yapar. Operasyon yalnız istisnalara bakar.
Birikim (backlog) ayrı Kurtarma Timi + bölge dolgu kapasitesiyle erir (musluk koruması).

Girdi: is_emri_analizi.yukle() (BOSS/FOX/TAMAMLANDI/bina_master) — yalnız toplu sayım kullanılır.
Çıktı: cikti/strateji_bolge_dalga.json (kişisel veri yok: bölge = ilçe/mahalle adı + sayılar).
Ağ çağrısı yok.
"""
import json
import math
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).parent))
import is_emri_analizi as A  # noqa: E402
import taksonomi as TX  # noqa: E402

OUT = Path(__file__).parent / "cikti"

# BOSS dışa aktarımına 18:11'de kullanıcı tarafından bir özet sayfası ('Sayfa1', ekip pivotu) eklendi;
# veri 'Task Detail Report' sayfasında. Kaynak dosyaya dokunmadan okuma yönlendirilir.
_read_excel_orj = pd.read_excel


def _read_excel(path, *a, **k):
    if str(path).endswith("TeknikTaskDetayRaporu.xlsx") and "sheet_name" not in k and not a:
        k["sheet_name"] = "Task Detail Report"
    return _read_excel_orj(path, *a, **k)


pd.read_excel = _read_excel

# ------------------------------------------------------------------ parametreler (analizden)
# günlük giriş (mevcut müşteri, ANLATILAN 1-15 Eylül, sansürsüz) ve tip hızları (is/gün, takvim ort.)
LAMBDA_GUN = {0: 337.7, 1: 337.7, 2: 337.7, 3: 337.7, 4: 337.7, 5: 384.0, 6: 182.0}  # Pzt=0
GUN_SAPMA_SIGMA = 0.15   # günlük aşırı dağılım (lognormal); std 77/338 ~ %23'ün Poisson dışı kısmı
SAAT_PROFIL = {0: 0.014, 1: 0.003, 2: 0.002, 3: 0.001, 4: 0.0, 5: 0.001, 6: 0.002, 7: 0.005, 8: 0.015,
               9: 0.129, 10: 0.079, 11: 0.066, 12: 0.081, 13: 0.081, 14: 0.074, 15: 0.07, 16: 0.066,
               17: 0.074, 18: 0.062, 19: 0.063, 20: 0.043, 21: 0.033, 22: 0.022, 23: 0.015}
# kod: (gunluk, btk, serit, fox_hedef_saat, saha_birim)
TIPLER = {
    "BAGLANTI": (142.0, True, "SAHA", 12, 1.0),
    "TV_ARIZA": (29.2, True, "SAHA", 6, 1.0),
    "DOPING_ARIZA": (8.6, True, "SAHA", 24, 1.0),
    "ARAMA": (0.8, True, "SAHA", 12, 1.0),
    "MODEM_DEGISIKLIGI": (31.9, False, "SAHA", None, 1.0),
    "UCRETLENDIRME": (11.1, False, "SAHA", None, 1.0),
    "EVRAK_SOSYAL": (4.8, False, "SAHA", None, 0.5),
    "EVRAK_TURKSAT": (0.8, False, "SAHA", None, 0.5),
    "SUPERBOX_MODEM": (2.4, False, "SAHA", None, 1.0),
    "STB_DEGISIKLIGI": (2.0, False, "SAHA", None, 1.0),
    "CIHAZ_GERI_ALIM": (1.9, False, "SAHA", 48, 0.5),
    "TV_KURULUM": (1.6, False, "SAHA", None, 1.0),
    "IKINCI_DONANIM": (5.4, False, "SAHA", None, 1.0),
    "KANAL_SIKAYETI": (49.2, False, "MASA", 24, 0.0),
    "SORU_CEVAP": (1.9, False, "MASA", None, 0.0),
    "CIHAZ_IADE": (34.6, False, "LOJ", 24, 0.5),
}
SAHA_TIP = [k for k, v in TIPLER.items() if v[2] == "SAHA"]

# dilim takvimi (dakika) ve dalgalar
# ASİMETRİK DALGA (seçilen): SABAH dalgası 3 dilim (dün 12:45 sonrası + gece gelenler = girişin ~%65'i),
# ÖĞLE dalgası 1 dilim (bugün 07:45-13:45 gelenler), AKŞAM 1 dilim (geç vardiya).
SLOTLAR = [("S1", 510, 630, "SABAH"), ("S2", 630, 750, "SABAH"), ("S3", 750, 870, "SABAH"),
           ("S4", 900, 1020, "OGLE"), ("S5", 1020, 1140, "AKSAM")]
DALGA_KILIT = {"SABAH": 465, "OGLE": 825, "AKSAM": 945}   # liste yayını 07:45 / 13:45 / 15:45
# SİMETRİK DALGA (karşılaştırma): 09-11, 11-13 | 14-16, 16-18 | 18-20; kilit 07:45 / 12:45 / 16:45
SLOTLAR_SIMETRIK = [("S1", 540, 660, "SABAH"), ("S2", 660, 780, "SABAH"),
                    ("S3", 840, 960, "OGLE"), ("S4", 960, 1080, "OGLE"), ("S5", 1080, 1200, "AKSAM")]
DALGA_KILIT_SIMETRIK = {"SABAH": 465, "OGLE": 765, "AKSAM": 1005}
ONCELIK_SURESI = {"normal": 60, "btk": 45}                  # dilim başlangıcına en az kalan süre (dk)
BIRIM_DK = 40            # 1 ziyaret birimi = 40 dk (yol + iş), 2 saatlik dilim = 3 birim
Q_DILIM = 3.0            # teknisyen başına dilim kapasitesi (birim)
BTK_REZERV = 1.0         # her teknisyen-dilimde BTK'ya ayrılan birim; dilim başlangıcı -45 dk'da serbest
MALIYET = dict(ziyaret=1.0, telefon=0.15, atla=0.10, bosa=0.60, erteleme=0.10, dolgu_arama=0.10)

# davranış olasılıkları (kalibrasyon gerektirir; ilk hafta ölçülür)
P = dict(
    cevap=0.65,            # SMS'li yeni işte teknisyenin yola çıkış çağrısına cevap
    cevap_teyitli=0.92,    # müşteriyle konuşularak alınmış (teyitli) randevuda
    btk_telefon_cozum=0.45,  # cevap veren BTK müşterisinde 'düzeldi / uzaktan çözüldü' (=> BTK'nın ~%29'u)
    erteleme=0.10,         # cevap veren müşteri dilimi değiştirir
    yakin=0.70,            # cevapsızda bir sonraki durağa <=1 km ise yine de gidilir
    evde_cevapsiz=0.45,    # cevap vermeyen ama gidilen müşteri evde
    evde_teyitli=0.95,
    ilk_seferde_cozum=0.92,
    ops_cevap=0.50,        # operasyon istisna çağrısı başına cevap
    masa_cevap=0.70,       # Kanal Şikayeti vb. masa çağrısında cevap
    masa_cozum=0.98,
    loj_masada_kapanis=0.60,  # Cihaz İade: cihaz geldi / sistem kapanışı
    birikim_cevap=0.45,    # birikimdeki (çoğu 'ulaşılamadı' notlu) müşteriye cevap
    birikim_duzelmis=0.35,  # birikimde cevap verenin 'zaten düzeldi' oranı
    birikim_evde_cevapsiz=0.35,
    altyapi_bayrak=0.02,   # binada açık altyapı bayrağı -> sahaya gönderilmez (E3)
)
ZON_HEDEF = 11.0         # bölge başına hafta içi ortalama saha birimi (1 sahip teknisyen)
MASA_KAP_SAAT = 7.0      # operasyon kişi başı saatte arama/işlem
MASA_SAATLER = list(range(8 * 60 + 30, 19 * 60 + 30, 60))


# ------------------------------------------------------------------ 1) BÖLGE ÜRETİMİ
ILCE_GRUP = {
    "METRO": ["Nilüfer", "Osmangazi", "Yıldırım", "Gürsu", "Kestel", "Mudanya"],
    "YALOVA": ["Yalova Merkez", "Çiftlikköy", "Altınova", "Armutlu", "Çınarcık", "Termal"],
    "GEMLIK_ORHANGAZI": ["Gemlik", "Orhangazi", "İznik"],
    "INEGOL_YENISEHIR": ["İnegöl", "Yenişehir"],
    "KARACABEY_MKP": ["Karacabey", "Mustafakemalpaşa"],
    "GUNEY": ["Orhaneli", "Keles", "Büyükorhan"],
}
# master'da bina konumu olmayan ilçeler için yaklaşık ilçe merkezi (genel bilgi; ağ çağrısı yok)
ILCE_MERKEZ = {"Çiftlikköy": (40.662, 29.321), "Altınova": (40.694, 29.508), "Armutlu": (40.520, 28.830),
               "Çınarcık": (40.644, 29.120), "Termal": (40.607, 29.172), "Karacabey": (40.214, 28.360),
               "Mustafakemalpaşa": (40.037, 28.408), "İznik": (40.429, 29.720), "Orhaneli": (39.903, 28.990),
               "Keles": (39.913, 29.228), "Büyükorhan": (39.767, 28.891), "Yalova Merkez": (40.655, 29.275)}
BOSS_ILCE_DUZELT = {"Merkez": "Yalova Merkez"}


def xy_km(lat, lon):
    return np.c_[(np.asarray(lon) - 29.0) * math.cos(math.radians(40.2)) * 111.32,
                 (np.asarray(lat) - 40.2) * 110.54]


def kapasiteli_kmeans(X, w, K, iters=40, slack=1.12, seed=0):
    """Ağırlıklı, kapasite sınırlı k-ortalama (pişmanlık sıralı atama). X: km, w: iş/gün."""
    n = len(X)
    if K <= 1 or n <= 1:
        return np.zeros(n, int)
    rng = np.random.default_rng(seed)
    # ağırlıklı k-means++ başlangıç
    C = [X[rng.choice(n, p=w / w.sum())]]
    for _ in range(1, K):
        d2 = np.min(((X[:, None, :] - np.array(C)[None]) ** 2).sum(-1), 1) * w
        C.append(X[rng.choice(n, p=d2 / d2.sum())] if d2.sum() > 0 else X[rng.integers(n)])
    C = np.array(C)
    cap = slack * w.sum() / K
    lab = np.zeros(n, int)
    for _ in range(iters):
        D = np.sqrt(((X[:, None, :] - C[None]) ** 2).sum(-1))
        srt = np.sort(D, 1)
        pis = srt[:, 1] - srt[:, 0] if K > 1 else srt[:, 0]
        yuk = np.zeros(K)
        for i in np.argsort(-pis * np.sqrt(w)):
            sira = np.argsort(D[i])
            for k in sira:
                if yuk[k] + w[i] <= cap:
                    lab[i] = k
                    break
            else:
                k = min(sira[:3], key=lambda j: yuk[j])
                lab[i] = k
            yuk[lab[i]] += w[i]
        Cn = np.array([np.average(X[lab == k], 0, w[lab == k]) if (lab == k).any() else C[k] for k in range(K)])
        if np.allclose(Cn, C, atol=1e-3):
            break
        C = Cn
    return lab


def bolge_uret(b, t, m, V_haftaici, zon_hedef):
    """Bina düzeyinde (location_id) mevcut-müşteri saha iş yoğunluğu -> ilçe grubu bazında dengeli bölgeler.

    - Bina ağırlığı: TAMAMLANDI (1-15 Eylül, akış) + BOSS açık işlerden son 72 saatte açılanlar.
    - İlçe payı: yalnız son 72 saatte açılan BOSS işleri (akış). Tüm açık işler birikim-yanlı
      (Yalova açık işte %11, akışta ~%1,5).
    - Grup yükü < 0,5 x zon_hedef ise HİBRİT bölge (o ilçedeki kurulum teknisyeni S1+S3'te bakar).
    - METRO bölgeleri 4-5'li SEKTÖR'lere ayrılır; sektörün yüzen teknisyeni taşmayı alır.
    - Her OneMap binası en yakın bölge merkezine (aynı ilçe grubunda) bağlanır = bina.bolge_op.
    """
    saha_kod = set(SAHA_TIP)
    son72 = b[(b.sahip == "mevcut_musteri") & b.kod.isin(saha_kod) & (b.yas_h < 72)]
    tl = A.lokasyon_bagla(t[t.kod.isin(saha_kod)].copy(), m)
    bl = A.lokasyon_bagla(son72.copy(), m)
    kol = ["_k", "lat", "lon", "ilce", "mahalle"]
    lok = pd.concat([tl[kol], bl[kol]]).dropna(subset=["lat"])
    grup_of = {i: g for g, L in ILCE_GRUP.items() for i in L}
    rec = son72["İlçe"].replace(BOSS_ILCE_DUZELT)
    rec = rec[rec.isin(grup_of)]
    ilce_pay = rec.value_counts(normalize=True)
    bina = (lok.groupby("_k").agg(n=("lat", "size"), lat=("lat", "first"), lon=("lon", "first"),
                                  ilce=("ilce", "first"), mahalle=("mahalle", "first")).reset_index())
    satir = []
    for ilce, pay in ilce_pay.items():
        bi = bina[bina.ilce == ilce]
        if len(bi) == 0:
            la, lo = ILCE_MERKEZ.get(ilce, (40.2, 29.0))
            satir.append(dict(ilce=ilce, mahalle="(ilçe geneli)", lat=la, lon=lo, w=pay * V_haftaici))
        else:
            for r in bi.itertuples():
                satir.append(dict(ilce=ilce, mahalle=r.mahalle, lat=r.lat, lon=r.lon, w=pay * V_haftaici * r.n / bi.n.sum()))
    M = pd.DataFrame(satir)
    M["grup"] = M.ilce.map(grup_of)
    mm = m.dropna(subset=["lat", "lon"]).copy()
    mm["grup"] = mm.ilce.map(grup_of)
    zonlar, zid = [], 0
    for g, Mg in M.groupby("grup"):
        yuk = Mg.w.sum()
        K = max(1, int(round(yuk / zon_hedef)))
        X = xy_km(Mg.lat, Mg.lon)
        lab = kapasiteli_kmeans(X, Mg.w.values, K, seed=zid + 7)
        merkezler = []
        for k in range(K):
            sel = Mg[lab == k]
            if sel.empty:
                continue
            Xs = xy_km(sel.lat, sel.lon)
            c = np.average(Xs, 0, sel.w.values)
            r = np.sqrt(((Xs - c) ** 2).sum(1))
            mah_w = sel.groupby(["ilce", "mahalle"]).w.sum().sort_values(ascending=False)
            (i0, m0) = mah_w.index[0]
            zonlar.append(dict(
                id=zid, ad=f"Z{zid + 1:02d} {i0}/{str(m0).title()}", grup=g,
                ilceler=sorted(sel.ilce.unique().tolist()),
                mahalle_sayisi=int(len(mah_w)), mahalleler=[str(x[1]) for x in mah_w.index[:8]],
                gunluk_saha_birim_haftaici=round(float(sel.w.sum()), 1),
                merkez_km=[round(float(c[0]), 2), round(float(c[1]), 2)],
                yaricap_km_agirlikli_p90=round(float(np.quantile(np.repeat(r, np.maximum(1, (sel.w.values * 50).astype(int))), 0.9)), 1),
                hibrit=bool(yuk < 0.5 * zon_hedef)))
            merkezler.append((zid, c))
            zid += 1
        # bina -> bölge (Voronoi, aynı ilçe grubu)
        mg = mm[mm.grup == g]
        if len(mg) and merkezler:
            Xb = xy_km(mg.lat.values, mg.lon.values)
            Cz = np.array([c for _, c in merkezler])
            en = np.argmin(((Xb[:, None, :] - Cz[None]) ** 2).sum(-1), 1)
            for j, (z, _) in enumerate(merkezler):
                zonlar[z]["bina_sayisi"] = int((en == j).sum())
    for z in zonlar:
        z.setdefault("bina_sayisi", 0)
    # sektörler: METRO bölgeleri 4-5'li kümeler; diğer gruplar kendi sektörü
    metro = [z for z in zonlar if z["grup"] == "METRO"]
    if len(metro) > 1:
        from scipy.cluster.vq import kmeans2
        ks = max(1, int(round(len(metro) / 4.5)))
        Cm = np.array([z["merkez_km"] for z in metro], float)
        best = None
        for sd in range(20):
            cen, lab = kmeans2(Cm, ks, seed=sd, minit="++")
            sz = np.bincount(lab, minlength=ks)
            sk = sz.max() - sz.min()
            if sz.min() > 0 and (best is None or sk < best[0]):
                best = (sk, lab)
        for z, l in zip(metro, best[1]):
            z["sektor"] = f"METRO-{int(l) + 1}"
    for z in zonlar:
        z.setdefault("sektor", z["grup"])
    return zonlar, M


# ------------------------------------------------------------------ 2) SİMÜLASYON
class Is:
    __slots__ = ("id", "gelis", "kod", "btk", "serit", "fox", "birim", "zon", "durum", "kapanis", "neden",
                 "basarisiz", "teyitli", "birikim", "rezerv", "gecikmis_bayrak", "ops_deneme", "masa_deneme",
                 "rez_birim", "e3")

    def __init__(self, i, gelis, kod, zon, birikim=False):
        g, btk, serit, fox, birim = TIPLER[kod]
        self.id, self.gelis, self.kod, self.btk, self.serit = i, gelis, kod, btk, serit
        self.fox, self.birim, self.zon = fox, birim, zon
        self.durum, self.kapanis, self.neden = "acik", None, None
        self.basarisiz, self.teyitli, self.birikim = 0, False, birikim
        self.rezerv, self.gecikmis_bayrak, self.ops_deneme, self.masa_deneme = False, False, 0, 0
        self.rez_birim = birim
        self.e3 = False


def beklenen_birim(j):
    """Takvime yazılan birim = işin BEKLENEN saha maliyeti (fazla rezervasyon / overbooking).
    BTK ilk denemede ~0,57, diğer ~0,79, teyitli ~0,97 birim. Gerçekleşen fazla ise dilim taşar ve
    kalan iş aynı teknisyenin sonraki dilimine öncelikli geçer."""
    if j.teyitli:
        pa, fix, ert = P["cevap_teyitli"], 0.0, 0.0
    else:
        pa = P["cevap"]
        fix = P["btk_telefon_cozum"] if (j.btk and j.basarisiz == 0) else 0.0
        ert = P["erteleme"]
    cevap = fix * MALIYET["telefon"] + (1 - fix) * (ert * MALIYET["erteleme"] + (1 - ert) * j.birim)
    cevapsiz = (P["yakin"] * (P["evde_cevapsiz"] * j.birim + (1 - P["evde_cevapsiz"]) * MALIYET["bosa"])
                + (1 - P["yakin"]) * MALIYET["atla"])
    return pa * cevap + (1 - pa) * cevapsiz


class Sim:
    def __init__(self, zonlar, senaryo, seed, gun_sayisi=35, gun0_hafta=2):
        self.Z = zonlar
        self.S = senaryo
        self.rng = np.random.default_rng(seed)
        self.G = gun_sayisi
        self.g0 = gun0_hafta      # 30.09.2026 = Çarşamba (Pzt=0)
        self.SL = senaryo.get("slotlar", SLOTLAR)
        self.KL = senaryo.get("kilit_saat", DALGA_KILIT)
        self.kilit = senaryo.get("kilit", False)   # False: yayından sonra geç ekleme serbest (>=60 dk)
        self.w = np.array([z["gunluk_saha_birim_haftaici"] for z in zonlar])
        self.wp = self.w / self.w.sum()
        self.C = np.array([z["merkez_km"] for z in zonlar])
        self.isler, self.nid = [], 0
        self.kap = {}          # (gun, havuz, slot) -> dict(cap, kul, btk_kul, isler[])
        self.havuz = {}        # gun -> (zon->havuz, havuz merkezleri, havuz tech)
        self.aksam = {}        # gun -> (zon->aksam grubu)
        self.birikim_havuz = {}  # zon -> list of Is (dolgu adayları)
        self.masa = []         # (erken_zaman, oncelik, sira, Is, tur)
        self.say = dict(sms=0, tek_cagri=0, ops_cagri=0, masa_cagri=0, bosa=0, ziyaret=0, atla=0, telefon=0,
                        komsu=0, alarm=0, dolgu=0, erteleme=0, e5=0, e3=0, kurtarma_ziyaret=0, tasma=0)
        self.gunluk = []

    # ---------------- kadro ve havuzlar
    def teknisyen_sayisi(self, d):
        return self.S["kadro"](d, (self.g0 + d) % 7)

    def havuz_kur(self, d):
        """Gün d kadrosu: her tam bölgeye 1 sahip; N > bölge ise fazlası SEKTÖR yüzeni; N < bölge ise
        en az yüklü bölge en yakın komşusuyla birleştirilir (Pazartesi/Pazar). Hibrit bölge: kurulum
        teknisyeni S1 + S3 (dilim başına Q birim)."""
        wd = (self.g0 + d) % 7
        N = self.teknisyen_sayisi(d)
        tam = [z["id"] for z in self.Z if not z["hibrit"]]
        hib = [z["id"] for z in self.Z if z["hibrit"]]
        grp = [[k] for k in tam]
        yuk = [self.w[k] for k in tam]
        while len(grp) > max(1, N):
            i = int(np.argmin(yuk))
            ci = np.average(self.C[grp[i]], 0, self.w[grp[i]])
            best, bd = None, 1e9
            for j in range(len(grp)):
                if j == i:
                    continue
                cj = np.average(self.C[grp[j]], 0, self.w[grp[j]])
                dd = np.hypot(*(ci - cj)) * (1 if self.Z[grp[i][0]]["grup"] == self.Z[grp[j][0]]["grup"] else 3)
                if dd < bd:
                    best, bd = j, dd
            grp[best] += grp[i]
            yuk[best] += yuk[i]
            del grp[i], yuk[i]
        F = max(0, N - len(grp))
        z2h = {z: h for h, g in enumerate(grp) for z in g}
        for z in hib:
            z2h[z] = ("H", z)
        mer = {h: np.average(self.C[g], 0, self.w[g]) for h, g in enumerate(grp)}
        sek_of = {z["id"]: z["sektor"] for z in self.Z}
        sek_yuk, sek_sahip = {}, {}
        for z in tam:
            sek_yuk[sek_of[z]] = sek_yuk.get(sek_of[z], 0) + self.w[z]
            sek_sahip[sek_of[z]] = sek_sahip.get(sek_of[z], 0) + 1
        yuzen = {k: 0 for k in sek_yuk}
        for _ in range(F):
            k = max(sek_yuk, key=lambda s_: sek_yuk[s_] / (sek_sahip[s_] + yuzen[s_]))
            yuzen[k] += 1
        self.havuz[d] = dict(z2h=z2h, mer=mer, grp=grp, sek_of=sek_of, yuzen=yuzen)
        for h in range(len(grp)):
            for s_ in ("S1", "S2", "S3", "S4"):
                self.kap[(d, h, s_)] = dict(cap=Q_DILIM, kul=0.0, rez=BTK_REZERV, isler=[])
        for k, f in yuzen.items():
            if f:
                for s_ in ("S1", "S2", "S3", "S4"):
                    self.kap[(d, ("F", k), s_)] = dict(cap=Q_DILIM * f, kul=0.0, rez=BTK_REZERV * f, isler=[])
        for z in hib:
            for s_ in ("S1", "S3"):
                self.kap[(d, ("H", z), s_)] = dict(cap=Q_DILIM, kul=0.0, rez=0.0, isler=[])
        # akşam nöbeti (13:00-21:00): S3-S4'te kendi sektörünün yüzeni gibi, S5'te akşam grubunun tek teknisyeni
        E = self.S["aksam"](d, wd)
        self.aksam[d] = {}
        if E > 0:
            from scipy.cluster.vq import kmeans2
            Ct = self.C[tam].astype(float)
            lab = kmeans2(Ct, E, seed=11, minit="++")[1] if E > 1 else np.zeros(len(tam), int)
            self.aksam[d] = {z: int(l) for z, l in zip(tam, lab)}
            for e in range(E):
                zs = [z for z, l in self.aksam[d].items() if l == e]
                if not zs:
                    continue
                sek = sek_of[max(zs, key=lambda z: self.w[z])]
                for s_ in ("S3", "S4"):
                    key = (d, ("F", sek), s_)
                    if key not in self.kap:
                        self.kap[key] = dict(cap=0.0, kul=0.0, rez=0.0, isler=[])
                    self.kap[key]["cap"] += Q_DILIM
                    self.kap[key]["rez"] += BTK_REZERV
                self.kap[(d, ("E", e), "S5")] = dict(cap=Q_DILIM, kul=0.0, rez=0.0, isler=[])

    # ---------------- rezervasyon
    def slot_listesi(self, is_, simdi, aksam_serbest=False):
        """(T0, tercih, T1, anahtar) — bugün + 2 gün; aynı dilimde önce bölge sahibi, sonra sektör yüzeni.
        Kurallar: dilim başlangıcına en az 60 dk (BTK 45 dk); dalga kilitlendiyse (SABAH 07:45, ÖĞLE 12:45,
        AKŞAM 16:45) BTK dışı iş o dalgaya eklenmez; S5 (akşam) yalnız BTK, 2. deneme veya son çare."""
        d0 = int(simdi // 1440)
        out = []
        lead = ONCELIK_SURESI["btk" if is_.btk else "normal"]
        for d in range(d0, min(self.G, d0 + 3)):
            if d not in self.havuz:
                continue
            H = self.havuz[d]
            for ad, bas, bit, dalga in self.SL:
                T0, T1 = d * 1440 + bas, d * 1440 + bit
                if T0 - simdi < lead:
                    continue
                if self.kilit and not is_.btk and simdi >= d * 1440 + self.KL[dalga]:
                    continue
                if ad == "S5":
                    if is_.zon not in self.aksam[d]:
                        continue
                    if not (aksam_serbest or is_.btk):
                        continue
                    out.append((T0, 2, T1, (d, ("E", self.aksam[d][is_.zon]), "S5")))
                    continue
                for pref, key in ((0, (d, H["z2h"][is_.zon], ad)), (1, (d, ("F", H["sek_of"][is_.zon]), ad))):
                    if key in self.kap:
                        out.append((T0, pref, T1, key))
        out.sort(key=lambda x: (x[0], x[1]))
        return out

    def komsu_listesi(self, is_, simdi, son):
        """Aynı sektördeki (yoksa en yakın) diğer bölge sahipleri, uzaklık sırasıyla en fazla 4; x1,25 birim."""
        d0 = int(simdi // 1440)
        out = []
        for d in range(d0, min(self.G, d0 + 2)):
            if d not in self.havuz:
                continue
            Hv = self.havuz[d]
            h0 = Hv["z2h"][is_.zon]
            c0 = self.C[is_.zon]
            sek = Hv["sek_of"][is_.zon]
            havuzlar = [h for h in Hv["mer"] if h != h0]
            ayni = [h for h in havuzlar if any(Hv["sek_of"][z] == sek for z in Hv["grp"][h])]
            kom = sorted(ayni or havuzlar, key=lambda h: np.hypot(*(Hv["mer"][h] - c0)))[:4]
            for h in kom:
                for ad, bas, bit, dalga in self.SL[:4]:
                    T0, T1 = d * 1440 + bas, d * 1440 + bit
                    if T0 - simdi < ONCELIK_SURESI["normal"] or T1 > son:
                        continue
                    if self.kilit and not is_.btk and simdi >= d * 1440 + self.KL[dalga]:
                        continue
                    out.append((T0, 3, T1, (d, h, ad)))
        out.sort(key=lambda x: (x[0], x[1]))
        return out

    def rezerve(self, is_, simdi, aksam_tercih=False, son_tarih=None):
        """Rezervasyon geçişleri (ilk tutan kazanır):
        G1 BTK: FOX hedefi (Bağlantı/Arama 12 s, TV 6 s, Doping 24 s) içinde en erken dilim, rezerv kullanılabilir.
        G2 24 s içinde en erken dilim, sahip > yüzen; BTK dışı iş BTK rezervine dokunmaz.
        G3 24 s içinde, BTK dışı iş rezervi ve S5 akşam dilimini de kullanır (son tarihi kurtaran tek seçenekse).
        G4 aynı sektörde komşu bölge sahibi (uzaklık sırası, en çok 4), x1,25 birim, 24 s içinde.
        G5 geç: kendi takviminde ilk boş dilim + KAPASİTE ALARMI (vardiya lideri kurtarma/mesai kararı)."""
        son = son_tarih if son_tarih is not None else is_.gelis + 1440
        is_.rez_birim = beklenen_birim(is_) if self.S.get("fazla_rezervasyon", True) else is_.birim

        def bos(key, rezerv_serbest, carpan=1.0):
            k = self.kap[key]
            rez = 0.0 if (is_.btk or rezerv_serbest or key[2] == "S5") else k["rez"]
            return k["cap"] - k["kul"] - rez >= is_.rez_birim * carpan - 1e-9

        aday = self.slot_listesi(is_, simdi, aksam_serbest=aksam_tercih)
        if is_.btk and is_.fox:
            H = min(son, is_.gelis + is_.fox * 60)
            for T0, pref, T1, key in aday:
                if T1 <= H and bos(key, True):
                    return self._yaz(is_, key)
        for T0, pref, T1, key in aday:
            if T1 <= son and bos(key, False):
                return self._yaz(is_, key)
        for T0, pref, T1, key in self.slot_listesi(is_, simdi, aksam_serbest=True):
            if T1 <= son and bos(key, self.S.get("g3_rezerv", False)):
                return self._yaz(is_, key)
        for T0, pref, T1, key in self.komsu_listesi(is_, simdi, son):
            if bos(key, True, 1.25):
                self.say["komsu"] += 1
                is_.birim *= 1.25
                is_.rez_birim *= 1.25
                return self._yaz(is_, key)
        self.say["alarm"] += 1
        is_.gecikmis_bayrak = True
        for T0, pref, T1, key in self.slot_listesi(is_, simdi, aksam_serbest=True):
            if bos(key, True):
                return self._yaz(is_, key, sms=False)
        for d in range(int(simdi // 1440) + 1, self.G):
            if d in self.havuz:
                self.say["tasma"] += 1
                return self._yaz(is_, (d, self.havuz[d]["z2h"][is_.zon], "S1"), sms=False)
        is_.durum = "sim_disi"

    def _yaz(self, is_, key, sms=True):
        k = self.kap[key]
        k["kul"] += is_.rez_birim
        if is_.btk and key[2] != "S5":
            k["rez"] = max(0.0, k["rez"] - is_.rez_birim)
        k["isler"].append(is_)
        is_.durum = "randevulu"
        if sms:
            self.say["sms"] += 1
        else:
            self.say["bekleme_listesi"] = self.say.get("bekleme_listesi", 0) + 1
        return key

    # ---------------- iş üretimi
    def uret(self, d):
        wd = (self.g0 + d) % 7
        lam = LAMBDA_GUN[wd] * float(np.exp(self.rng.normal(0, GUN_SAPMA_SIGMA) - GUN_SAPMA_SIGMA ** 2 / 2))
        n = self.rng.poisson(lam)
        hp = np.array([SAAT_PROFIL[h] for h in range(24)])
        hp = hp / hp.sum()
        kods = list(TIPLER)
        tp = np.array([TIPLER[k][0] for k in kods])
        tp = tp / tp.sum()
        saat = self.rng.choice(24, n, p=hp)
        dk = self.rng.random(n) * 60
        tip = self.rng.choice(len(kods), n, p=tp)
        zon = self.rng.choice(len(self.Z), n, p=self.wp)
        out = []
        for i in range(n):
            j = Is(self.nid, d * 1440 + saat[i] * 60 + dk[i], kods[tip[i]], int(zon[i]))
            self.nid += 1
            out.append(j)
        out.sort(key=lambda x: x.gelis)
        self.isler += out
        return out

    def birikim_yukle(self):
        """30.09 sabahı başlangıç birikimi (mevcut müşteri 953): A saha 415, C ofis 397, B askı/merkez 138."""
        yaslar = self.rng.choice([36, 60, 120, 400, 900], 415, p=[0.12, 0.2, 0.22, 0.4, 0.06])
        for i in range(415):
            kod = self.rng.choice(["BAGLANTI", "TV_ARIZA", "DOPING_ARIZA", "MODEM_DEGISIKLIGI", "UCRETLENDIRME",
                                   "IKINCI_DONANIM", "EVRAK_SOSYAL"], p=[0.52, 0.12, 0.04, 0.12, 0.05, 0.12, 0.03])
            j = Is(self.nid, -yaslar[i] * 60, kod, int(self.rng.choice(len(self.Z), p=self.wp)), birikim=True)
            self.nid += 1
            self.isler.append(j)
            self.birikim_havuz.setdefault(j.zon, []).append(j)
            # kurtarma masası doğrulama araması (1. gün başlar)
            self.masaya(j, 8 * 60 + 30, 3 if not j.btk else 2, "dogrulama")
        for i, kod in enumerate(["KANAL_SIKAYETI"] * 179 + ["CIHAZ_IADE"] * 218):
            j = Is(self.nid, -self.rng.choice([60, 170, 300]) * 60, kod, int(self.rng.choice(len(self.Z), p=self.wp)), birikim=True)
            self.nid += 1
            self.isler.append(j)
            self.masaya(j, 8 * 60 + 30, 4, "masa" if kod == "KANAL_SIKAYETI" else "loj")
        for i in range(138):
            kod = self.rng.choice(["BAGLANTI", "TV_ARIZA", "MODEM_DEGISIKLIGI"], p=[0.6, 0.15, 0.25])
            j = Is(self.nid, -200 * 60, kod, int(self.rng.choice(len(self.Z), p=self.wp)), birikim=True)
            j.basarisiz = 2
            self.nid += 1
            self.isler.append(j)
            self.masaya(j, 8 * 60 + 30, 3, "istisna")

    # ---------------- masa (operasyon) kuyruğu
    def masaya(self, is_, zaman, oncelik, tur):
        self.masa.append((zaman, oncelik, is_.id, is_, tur))

    def masa_calis(self, simdi, kisi):
        kap = int(round(kisi * MASA_KAP_SAAT))
        hazir = [x for x in self.masa if x[0] <= simdi and x[3].durum not in ("kapandi",)]
        hazir.sort(key=lambda x: (x[1], x[3].gelis))
        yapilan = set()
        for x in hazir[:kap]:
            yapilan.add(id(x))
            self._masa_isle(x, simdi)
        self.masa = [x for x in self.masa if id(x) not in yapilan and x[3].durum != "kapandi"]

    def _masa_isle(self, x, simdi):
        _, onc, _, j, tur = x
        r = self.rng.random
        if tur == "loj":
            if r() < P["loj_masada_kapanis"]:
                return self.kapat(j, simdi, "loj_masa")
            j.serit, j.birim = "SAHA", 0.5
            return self.rezerve(j, simdi, son_tarih=max(j.gelis + 1440, simdi + 1440 if j.birikim else 0))
        self.say["masa_cagri" if tur == "masa" else "ops_cagri"] += 1
        if tur == "masa":
            j.masa_deneme += 1
            if r() < P["masa_cevap"]:
                if r() < P["masa_cozum"]:
                    return self.kapat(j, simdi, "masa_telefon")
                j.serit, j.birim, j.btk, j.fox = "SAHA", 1.0, True, 24
                return self.rezerve(j, simdi)
            if j.masa_deneme < 4:
                gecikme = 120 if j.masa_deneme < 3 else 60 * 24
                return self.masaya(j, simdi + gecikme, onc, "masa")
            self.say["e5"] += 1
            return self.kapat(j, simdi, "E5_ulasilamadi")
        if tur == "altyapi":   # ticket çözüldü -> müşteriye haber, teyitli randevu
            j.teyitli = True
            self.say["ops_cagri"] += 1
            return self.rezerve(j, simdi, son_tarih=simdi + 1440)
        if tur == "dogrulama":
            j.ops_deneme += 1
            if r() < P["birikim_cevap"]:
                if r() < P["birikim_duzelmis"]:
                    return self.kapat(j, simdi, "birikim_dogrulamada_eridi")
                j.teyitli = True
                return
            if j.ops_deneme < 2:
                return self.masaya(j, simdi + 1440, onc, "dogrulama")
            return  # teyitsiz kalır; dolguda/kurtarmada kapıda denenir
        if tur == "istisna":
            j.ops_deneme += 1
            if r() < P["ops_cevap"]:
                j.teyitli = True
                j.basarisiz = 0
                return self.rezerve(j, simdi, son_tarih=max(j.gelis + 1440, simdi + 2 * 1440))
            # 3 deneme planı: +60 dk, 17:30 akşam, ertesi gün 09:00
            if j.ops_deneme < 3:
                d = int(simdi // 1440)
                sonraki = simdi + 60 if j.ops_deneme == 1 else max(simdi + 60, d * 1440 + 17 * 60 + 30)
                if sonraki > d * 1440 + 19 * 60 + 30:
                    sonraki = (d + 1) * 1440 + 9 * 60
                return self.masaya(j, sonraki, onc, "istisna")
            if j.ops_deneme == 3:  # askı (abone kaynaklı) 48 s, uyanınca son çağrı
                j.durum = "aski"
                return self.masaya(j, simdi + 2 * 1440, onc, "istisna")
            self.say["e5"] += 1
            return self.kapat(j, simdi, "E5_ulasilamadi")

    # ---------------- dilim yürütme
    def kapat(self, j, t, neden):
        j.durum, j.kapanis, j.neden = "kapandi", t, neden

    def cagri_sonucu(self, j, birikim=False):
        r = self.rng.random
        self.say["tek_cagri"] += 1
        pc = P["cevap_teyitli"] if j.teyitli else (P["birikim_cevap"] if birikim else P["cevap"])
        if r() < pc:
            if birikim and not j.teyitli and r() < P["birikim_duzelmis"]:
                return "telefon"
            if j.btk and j.basarisiz == 0 and not j.teyitli and r() < P["btk_telefon_cozum"]:
                return "telefon"
            if not j.teyitli and r() < P["erteleme"]:
                return "erteleme"
            return "ziyaret_evde"
        if r() < P["yakin"]:
            pe = P["birikim_evde_cevapsiz"] if birikim else P["evde_cevapsiz"]
            return "ziyaret_evde" if r() < pe else "bosa"
        return "atla"

    def ziyaret(self, j, t):
        self.say["ziyaret"] += 1
        if self.rng.random() < P["ilk_seferde_cozum"]:
            self.kapat(j, t, "saha")
            return True
        j.teyitli = True   # ikinci ziyaret (malzeme / uzman) — teyitli, ertesi güne
        self.rezerve(j, t, son_tarih=t + 1440)
        return False

    def basarisiz_isle(self, j, t):
        j.basarisiz += 1
        if j.basarisiz == 1:
            self.rezerve(j, t)                      # sonraki dalga + SMS
        elif j.basarisiz == 2:
            self.rezerve(j, t, aksam_tercih=True)   # akşam dilimi (çalışan müşteri)
        else:
            self.masaya(j, t + 60, 0 if j.btk else 2, "istisna")   # operasyon istisna masası

    def dilim_yurut(self, key, T0):
        k = self.kap[key]
        cap = k["cap"]
        isler = sorted(k["isler"], key=lambda j: (not j.btk, j.gelis))
        kul = 0.0
        for j in isler:
            if j.durum != "randevulu":
                continue
            if kul + MALIYET["atla"] > cap + 0.5:  # aşırı dolu (yeniden randevular): ertesi dilime taşı
                self.say["tasma"] += 1
                self.rezerve(j, T0 + 1)
                continue
            s = self.cagri_sonucu(j)
            if s == "telefon":
                kul += MALIYET["telefon"]
                self.say["telefon"] += 1
                self.kapat(j, T0 + kul * BIRIM_DK, "telefon_on_teshis")
            elif s == "erteleme":
                kul += MALIYET["erteleme"]
                self.say["erteleme"] += 1
                j.teyitli = True
                self.rezerve(j, T0 + 1, son_tarih=j.gelis + 2 * 1440)
            elif s == "ziyaret_evde":
                kul += j.birim
                self.ziyaret(j, T0 + kul * BIRIM_DK)
            elif s == "bosa":
                kul += MALIYET["bosa"]
                self.say["bosa"] += 1
                self.basarisiz_isle(j, T0 + kul * BIRIM_DK)
            else:
                kul += MALIYET["atla"]
                self.say["atla"] += 1
                self.basarisiz_isle(j, T0 + kul * BIRIM_DK)
        # dolgu: boş kapasite bölgenin birikimiyle doldurulur (teyitli -> BTK -> en eski)
        if key[2] != "S5" and self.S.get("dolgu", True):
            d, h = key[0], key[1]
            Hv = self.havuz[d]
            if isinstance(h, tuple) and h[0] == "F":
                zs = [z for z, s_ in Hv["sek_of"].items() if s_ == h[1]]
            elif isinstance(h, tuple):
                zs = [h[1]]
            else:
                zs = Hv["grp"][h]
            kul = self.dolgu(zs, cap, kul, T0, limit=6)

    def dolgu(self, zs, cap, kul, T0, limit=6, kurtarma=False):
        aday = [j for z in zs for j in self.birikim_havuz.get(z, []) if j.durum == "acik"]
        aday.sort(key=lambda j: (not j.teyitli, not j.btk, j.gelis))
        n = 0
        for j in aday:
            if cap - kul < 1.0 or n >= limit:
                break
            n += 1
            self.say["dolgu"] += 1
            s = self.cagri_sonucu(j, birikim=True)
            t = T0 + kul * BIRIM_DK
            if s == "telefon":
                kul += MALIYET["telefon"]
                self.kapat(j, t, "birikim_telefon")
            elif s in ("ziyaret_evde",):
                kul += j.birim
                if kurtarma:
                    self.say["kurtarma_ziyaret"] += 1
                if self.rng.random() < P["ilk_seferde_cozum"]:
                    self.kapat(j, t + j.birim * BIRIM_DK, "birikim_saha")
                self.say["ziyaret"] += 1
            elif s == "erteleme":
                kul += MALIYET["erteleme"]
                j.teyitli = True
            elif s == "bosa":
                kul += MALIYET["bosa"]
                self.say["bosa"] += 1
                j.basarisiz += 1
            else:
                kul += MALIYET["dolgu_arama"]
                j.basarisiz += 1
            if j.durum == "acik" and j.basarisiz >= 3:
                j.durum = "istisnada"
                self.masaya(j, T0 + 120, 3, "istisna")
        return kul

    def kurtarma_gunu(self, d):
        R = self.S["kurtarma"](d, (self.g0 + d) % 7)
        if R <= 0:
            return
        say = {}
        for z, L in self.birikim_havuz.items():
            say[z] = sum(1 for j in L if j.durum == "acik")
        # timin her üyesi bir gün boyunca birikimi en yoğun bölgeyi 'süpürür' (küme halinde)
        secilen = sorted(say, key=lambda z: -say[z])[:R]
        for z in secilen:
            for ad, bas, bit, _ in self.SL[:4]:
                self.dolgu([z], Q_DILIM, 0.0, d * 1440 + bas, limit=8, kurtarma=True)

    # ---------------- ana döngü
    def calis(self):
        self.birikim_yukle()
        bekleyen = []
        for d in range(min(3, self.G)):
            self.havuz_kur(d)
        for d in range(self.G):
            if d + 2 < self.G and (d + 2) not in self.havuz:
                self.havuz_kur(d + 2)
            yeni = self.uret(d)
            bekleyen += yeni
            wd = (self.g0 + d) % 7
            olaylar = []
            for t in self.S["intake"]:
                olaylar.append((d * 1440 + t, 0, "intake"))
            for ad, bas, bit, _ in self.SL:
                olaylar.append((d * 1440 + bas, 1, ad))
            for t in MASA_SAATLER:
                olaylar.append((d * 1440 + t, 2, "masa"))
            olaylar.append((d * 1440 + 8 * 60, 3, "kurtarma"))
            olaylar.sort()
            for T, _, tur in olaylar:
                if tur == "intake":
                    gel = [j for j in bekleyen if j.gelis <= T]
                    bekleyen = [j for j in bekleyen if j.gelis > T]
                    for j in gel:
                        self.intake(j, T)
                elif tur == "masa":
                    self.masa_calis(T, self.S["masa_kisi"](d, wd))
                elif tur == "kurtarma":
                    self.kurtarma_gunu(d)
                else:
                    for key in [k for k in self.kap if k[0] == d and k[2] == tur]:
                        self.dilim_yurut(key, T)
            self.gun_sonu(d)
        return self.ozet()

    def intake(self, j, T):
        if j.serit == "MASA":
            return self.masaya(j, T, 1, "masa")
        if j.serit == "LOJ":
            return self.masaya(j, T, 2, "loj")
        if self.rng.random() < P["altyapi_bayrak"]:
            self.say["e3"] += 1
            j.durum = "E3_altyapi"   # OneDesk/ONENT ticket; bina bazında tek ticket
            j.e3 = True
            gecikme = float(self.rng.lognormal(math.log(72 * 60), 0.6))
            return self.masaya(j, T + gecikme, 1, "altyapi")
        self.rezerve(j, T)

    def gun_sonu(self, d):
        T = (d + 1) * 1440
        acik = [j for j in self.isler if j.gelis < T and j.durum not in ("kapandi", "sim_disi")]
        self.gunluk.append(dict(
            gun=d, acik=len(acik),
            acik_24s_ustu=sum(1 for j in acik if T - j.gelis > 1440),
            birikim_kalan=sum(1 for j in acik if j.birikim),
            yeni_acik=sum(1 for j in acik if not j.birikim)))

    def ozet(self):
        yeni = [j for j in self.isler if not j.birikim and j.gelis < (self.G - 3) * 1440 and j.gelis >= 2 * 1440]

        def uyum(L, saat):
            if not L:
                return None
            return round(sum(1 for j in L if j.kapanis is not None and j.kapanis - j.gelis <= saat * 60) / len(L), 3)

        saha = [j for j in yeni if j.serit == "SAHA" or TIPLER[j.kod][2] == "SAHA"]
        btk = [j for j in yeni if TIPLER[j.kod][1]]
        bag = [j for j in yeni if j.kod == "BAGLANTI"]
        tv = [j for j in yeni if j.kod == "TV_ARIZA"]
        masa = [j for j in yeni if TIPLER[j.kod][2] == "MASA"]
        loj = [j for j in yeni if TIPLER[j.kod][2] == "LOJ"]
        ulasilan = [j for j in saha if j.basarisiz == 0 and not getattr(j, "e3", False)]
        e3siz = [j for j in saha if not getattr(j, "e3", False)]
        haftalik = {}
        for w in range(self.G // 7):
            L = [j for j in yeni if w * 7 * 1440 <= j.gelis < (w + 1) * 7 * 1440]
            haftalik[f"hafta_{w + 1}"] = uyum(L, 24)
        gun = pd.DataFrame(self.gunluk)
        brk_bitti = gun.index[gun.birikim_kalan <= 20]
        return dict(
            yeni_is=len(yeni),
            uyum_24s_tum=uyum(yeni, 24), uyum_24s_saha=uyum(saha, 24), uyum_24s_btk=uyum(btk, 24),
            uyum_12s_baglanti_fox=uyum(bag, 12), uyum_6s_tv_fox=uyum(tv, 6), uyum_24s_masa=uyum(masa, 24),
            uyum_24s_lojistik=uyum(loj, 24), uyum_48s_tum=uyum(yeni, 48), haftalik_24s=haftalik,
            uyum_24s_saha_ulasilan_musteri=uyum(ulasilan, 24), uyum_24s_saha_E3_haric=uyum(e3siz, 24),
            ilk_denemede_ulasilamayan_orani=round(1 - len(ulasilan) / max(1, len(e3siz)), 3),
            birikim_kalan_gun_sonu=gun.birikim_kalan.tolist(),
            birikim_20_alti_gun=int(brk_bitti[0]) + 1 if len(brk_bitti) else None,
            acik_24s_ustu_gun_sonu=gun.acik_24s_ustu.tolist(),
            gunluk_ort=dict(
                sms=round(self.say["sms"] / self.G, 1), teknisyen_cagri=round(self.say["tek_cagri"] / self.G, 1),
                ops_istisna_cagri=round(self.say["ops_cagri"] / self.G, 1), masa_cagri=round(self.say["masa_cagri"] / self.G, 1),
                ziyaret=round(self.say["ziyaret"] / self.G, 1), bosa_ziyaret=round(self.say["bosa"] / self.G, 1),
                telefon_kapanis=round(self.say["telefon"] / self.G, 1), komsu_odunc=round(self.say["komsu"] / self.G, 1),
                kapasite_alarm=round(self.say["alarm"] / self.G, 1), dolgu_deneme=round(self.say["dolgu"] / self.G, 1),
                e5_ulasilamadi_kapanis=round(self.say["e5"] / self.G, 1), e3_altyapi=round(self.say["e3"] / self.G, 1),
                bekleme_listesi_sozsuz=round(self.say.get("bekleme_listesi", 0) / self.G, 1)),
            bosa_ziyaret_orani=round(self.say["bosa"] / max(1, self.say["bosa"] + self.say["ziyaret"]), 3),
            teknisyen_gun=int(sum(self.teknisyen_sayisi(d) for d in range(self.G))),
        )


# ------------------------------------------------------------------ 3) KADRO FORMÜLÜ
def saha_birim_per_gelis():
    """Gelen bir mevcut-müşteri işinin beklenen saha birimi (telefon ön-teşhisi ve masa/lojistik ayrımı sonrası)."""
    tot = sum(v[0] for v in TIPLER.values())
    btk_tel = P["cevap"] * P["btk_telefon_cozum"]
    u = 0.0
    for k, (g, btk, serit, fox, birim) in TIPLER.items():
        if serit == "SAHA":
            u += g * (1 - (btk_tel if btk else 0)) * birim
        elif serit == "LOJ":
            u += g * (1 - P["loj_masada_kapanis"]) * birim
    return u / tot


def gerekli_teknisyen(wd, rho=0.30, util=0.80):
    """wd gününde hizmet edilecek iş: dünkü 12:00 sonrası + bugünkü 12:00 öncesi gelenler.
    rho = yeniden randevu payı (ulaşılamayan/evde yok %24, erteleme %6, ikinci ziyaret %8 -> simülasyonda
    ~%30); util = bölge/dilim parçalanması nedeniyle ulaşılabilir doluluk (%80). Kalibrasyon: 1,0-1,5 x
    ızgarasında saha 24 s uyumu 1,25 x (eski rho=0,18/util=0,92 formülüne göre) civarında doyuyor."""
    a12 = sum(v for h, v in SAAT_PROFIL.items() if h >= 12) / sum(SAAT_PROFIL.values())
    f = saha_birim_per_gelis()
    V = f * (LAMBDA_GUN[(wd - 1) % 7] * a12 + LAMBDA_GUN[wd] * (1 - a12))
    return V, math.ceil(V * (1 + rho) / (4 * Q_DILIM * util))


def main():
    global Q_DILIM
    b, f, t, an, anp, m, REF = A.yukle()
    f_birim = saha_birim_per_gelis()
    V_hi = f_birim * LAMBDA_GUN[1]
    hedef_yuk = ZON_HEDEF   # bölge sahibinin günlük hedef saha birimi (12 birim kapasitenin ~%92si)
    zonlar, M = bolge_uret(b, t, m, V_hi, hedef_yuk)
    K = len(zonlar)
    kadro_formul = {GUN: gerekli_teknisyen(i) for i, GUN in enumerate(A.GUN)}
    N_form = {i: kadro_formul[g][1] for i, g in enumerate(A.GUN)}

    INTAKE_30DK = list(range(7 * 60 + 30, 20 * 60 + 1, 30))
    INTAKE_3X = [7 * 60 + 45, 12 * 60 + 15, 16 * 60 + 45]
    ONERILEN = dict(
        kadro=lambda d, wd: N_form[wd], aksam=lambda d, wd: 3 if wd != 6 else 1,
        kurtarma=lambda d, wd: 4 if (d < 21 and wd != 6) else 0,
        masa_kisi=lambda d, wd: (6 if d < 21 else 4) if wd != 6 else 2, intake=INTAKE_30DK)
    senaryolar = {
        "S0_BUGUNKU_KADRO_10_6": dict(
            kadro=lambda d, wd: 6 if wd == 6 else 10, aksam=lambda d, wd: 0, kurtarma=lambda d, wd: 0,
            masa_kisi=lambda d, wd: 3, intake=INTAKE_30DK),
        "S1_ONERILEN": ONERILEN,
        "S2_MANUEL_3X_ICE_AKTARIM": dict(ONERILEN, intake=INTAKE_3X),
        "S3_KURTARMA_TIMI_YOK": dict(ONERILEN, kurtarma=lambda d, wd: 0, masa_kisi=lambda d, wd: 4 if wd != 6 else 2),
        "S4_PAZAR_YARIM_KADRO": dict(ONERILEN, kadro=lambda d, wd: (math.ceil(N_form[wd] / 2) if wd == 6 else N_form[wd]),
                                     aksam=lambda d, wd: 3 if wd != 6 else 0),
        "S7_SIMETRIK_DALGA_KILITLI": dict(ONERILEN, slotlar=SLOTLAR_SIMETRIK, kilit_saat=DALGA_KILIT_SIMETRIK, kilit=True),
        "S8_FAZLA_REZERVASYON_YOK": dict(ONERILEN, fazla_rezervasyon=False),
        "S9_KADEMELI_KADRO_2_3_4_3_TAM": dict(
            ONERILEN, kadro=lambda d, wd: math.ceil(N_form[wd] * (0.67 if d < 7 else (0.83 if d < 14 else 1.0)))),
    }
    # SMS kanalı yoksa (BOSS/Turkcell randevu SMS'i çıkmıyorsa) duyarlılık
    SMS_YOK = dict(cevap=0.55, evde_cevapsiz=0.30)
    TEKRAR = 5
    sonuc = {}
    for ad, S in senaryolar.items():
        sonuc[ad] = ortala([Sim(zonlar, S, seed).calis() for seed in range(TEKRAR)])
    eski = dict(P)
    P.update(SMS_YOK)
    sonuc["S5_SMS_KANALI_YOK"] = ortala([Sim(zonlar, ONERILEN, seed).calis() for seed in range(TEKRAR)])
    P.clear()
    P.update(eski)
    # verim duyarlılığı: yoğun bölgede dilim başına 3,5 birim (medyan komşu 112 m, rota yarıçapı 1,8 km)
    Q_DILIM = 3.5
    N35 = {i: gerekli_teknisyen(i)[1] for i in range(7)}
    sonuc["S6_VERIM_3_5_BIRIM"] = ortala([Sim(zonlar, dict(ONERILEN, kadro=lambda d, wd: N35[wd]), seed).calis()
                                          for seed in range(TEKRAR)])
    sonuc["S6_VERIM_3_5_BIRIM"]["kadro_gunluk"] = {A.GUN[i]: N35[i] for i in range(7)}
    Q_DILIM = 3.0
    for ad in sonuc:
        sonuc[ad].pop("birikim_20_alti_gun_tekrarlar", None)

    haftalik_tek_gun = sum(N_form.values())
    aksam_gun = 3 * 6 + 1
    out = dict(
        meta=dict(referans_an=str(REF), not_="Toplu çıktı; kişisel veri yok. Simülasyon 30.09.2026 Çar başlangıçlı 35 gün, 5 tekrar ortalaması. Uyum: 2.-32. gün gelen yeni işler."),
        bolge=dict(sayi=K, hedef_gunluk_birim_teknisyen=round(hedef_yuk, 1),
                   saha_birim_per_gelen_is=round(f_birim, 3), haftaici_gunluk_saha_birim=round(V_hi, 1),
                   gruplar={g: sum(1 for z in zonlar if z["grup"] == g) for g in ILCE_GRUP},
                   hibrit_bolge=[z["ad"] for z in zonlar if z["hibrit"]],
                   liste=zonlar),
        kadro=dict(
            gunluk_gerekli_teknisyen={g: dict(hizmet_birim=round(v[0], 1), teknisyen=v[1]) for g, v in kadro_formul.items()},
            haftalik_teknisyen_gun=haftalik_tek_gun,
            aksam_nobet_teknisyen_gun=aksam_gun,
            bolge_kadrosu_6_gun_calisma=math.ceil((haftalik_tek_gun + aksam_gun) / 6),
            bolge_kadrosu_izin_rapor_payi_ile=math.ceil((haftalik_tek_gun + aksam_gun) / 6 / 0.9),
            kurtarma_timi="4 teknisyen x 3 hafta (Pzt-Cmt) + 2 kurtarma masası",
            kadro_gunluk={A.GUN[i]: N_form[i] for i in range(7)},
            bugun_ariza_ekibi=12),
        parametreler=dict(P=P, Q_DILIM=Q_DILIM, BIRIM_DK=BIRIM_DK, BTK_REZERV=BTK_REZERV, MALIYET=MALIYET,
                          SLOTLAR=SLOTLAR, DALGA_YAYIN=DALGA_KILIT, ONCELIK_SURESI=ONCELIK_SURESI,
                          ZON_HEDEF=ZON_HEDEF, TIPLER=TIPLER, LAMBDA_GUN=LAMBDA_GUN),
        senaryolar=sonuc,
    )
    (OUT / "strateji_bolge_dalga.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=A.py), encoding="utf-8")
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk not in ("acik_24s_ustu_gun_sonu",)} for k, v in sonuc.items()},
                     ensure_ascii=False, indent=1, default=A.py))
    print("K", K, "f", f_birim, "V_hi", V_hi, "hedef", hedef_yuk, "N", N_form)
    for z in zonlar:
        print(z["ad"], z["grup"], z["gunluk_saha_birim_haftaici"], z["yaricap_km_agirlikli_p90"], z["bina_sayisi"], z["hibrit"])


def ortala(runs):
    o = {}
    for k in runs[0]:
        vs = [r[k] for r in runs]
        if isinstance(vs[0], (int, float)) and not isinstance(vs[0], bool):
            o[k] = round(float(np.mean([v for v in vs if v is not None])), 3) if any(v is not None for v in vs) else None
        elif isinstance(vs[0], dict):
            o[k] = {kk: (round(float(np.mean([v[kk] for v in vs if v[kk] is not None])), 3)
                         if any(v[kk] is not None for v in vs) else None) for kk in vs[0]}
        elif isinstance(vs[0], list):
            o[k] = [round(float(x), 0) for x in np.mean(np.array(vs, float), 0)]
        else:
            o[k] = vs[0]
    o["birikim_20_alti_gun_tekrarlar"] = [r["birikim_20_alti_gun"] for r in runs]
    return o


if __name__ == "__main__":
    main()
