# -*- coding: utf-8 -*-
"""
simulasyon.py - Dehanet EÇM mevcut-müşteri iş emri sistemi için ayrık olay benzetimi (DES)
ve strateji yarışı.

Yarışan stratejiler (hepsi AYNI gelişler, AYNI müşteri davranışı, AYNI kaynakla):
  BUGUN  - bugünkü süreç (kalibrasyon referansı): 2 kişilik ofis her işi bir kez arar; ulaşırsa dilim yazar,
           ulaşamazsa not düşer ve ertesi gün yine arar; teknisyen yalnız dilimli işe gider; Kanal ~1 hafta askıda.
  HAM    - kullanıcının ham fikri: aramadan doğrudan ekibe ver, teknisyen habersiz gider, evde olmayanı
           operasyon arar ve randevular.
  DSIR   - Doğrudan Sevk + İstisna Randevu (ham fikrin titiz hali).
  RPHT   - Risk Puanlı Hibrit Triyaj.
  BOLGE  - Bölge Dalgaları (sabit bölge takvimi, aramasız SMS dilimi).
  U1H    - Uzaktan-Önce Huni.
  KARMA  - yarış sonrası birleşim: aramasız doğrudan sevk + 'yetişir' sıralaması (24 saatine yetişebilecek iş önce,
           gecikmişe kota) + BTK'da masanın paralel hızlı teşhisi. Tasarımı tohum 1-3 ile yapıldı; raporlanan
           sonuçlar tasarımda kullanılmayan 101-105 ve 201-203 tohumlarıyla.
  (BOLGE_ESNEK yalnız kontrol amaçlı: BÖLGE takviminin gevşetilmiş hali.)

Adil yarış ilkeleri
  1) Ortak dünya: her tohum için gelişler, iş tipi, konum, arıza doğası (telefonla çözülür / şebeke /
     saha / altyapı), müşterinin ulaşılabilirlik sınıfı ve tercihi, k. aramada açıp açmayacağı, v. ziyarette
     evde olup olmayacağı ve yerinde iş süresi işe bağlı rastgele akışlardan gelir (ortak rastgele sayılar).
     Stratejiler yalnız KARARLARIYLA ayrışır.
  2) Aynı kaynak: aynı teknisyen sayısı (hafta içi/Cumartesi N, Pazar tavan(0,55·N)) ve aynı operasyon
     arama havuzu (O kişi 08:30-17:30, O_aksam kişi 17:30-20:30, Pazar O_pazar). Strateji gündüz/akşam
     vardiya bölüşümünü kendi seçer; ek geçici teknisyen, kurtarma timi ya da esnek havuz verilmez.
  3) Aynı ölçüm: 24 saat takvim saatidir; her kapanış türü sayılır (ulaşılamadı kapanışı ayrıca raporlanır).

Gizlilik: BOSS dışa aktarımından yalnız iş tipi, başlangıç zamanı, durum, 'ulaşılamadı' notu bayrağı ve
bina konumu bellekte kullanılır. Hiçbir çıktıya müşteri, task, lokasyon kimliği ya da kişi adı yazılmaz.
Ağ çağrısı yoktur.

Çalıştırma:  python simulasyon.py              (tam deney seti: 723 koşu, 16 çekirdekte ~10 dk)
             python simulasyon.py --hizli      (kısa deneme)
             python simulasyon.py --tek KARMA 16  (tek koşu özeti)
             python simulasyon.py --md         (simulasyon.md'yi cikti/simulasyon.json'dan yeniden yaz)
Çıktı:       cikti/simulasyon.json, simulasyon.md
"""
from __future__ import annotations

import argparse
import heapq
import json
import math
import os
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

# HAKEM1 kopyası: girdiler üst klasörden (operasyon/analiz), çıktılar hakem1/cikti altına.
HAKEM = os.path.dirname(os.path.abspath(__file__))
BURADA = os.path.dirname(HAKEM)
if __package__ in (None, ""):  # doğrudan çalıştırıldı: kod/ içe aktarma yoluna (yollar)
    sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")))
import yollar  # noqa: E402
CIKTI_GIRDI = os.path.join(BURADA, "cikti")
CIKTI = os.path.join(HAKEM, "cikti")
sys.path.insert(0, BURADA)
import taksonomi as tk  # noqa: E402

BOSS_XLSX = r"C:\Users\EXT03426951\Desktop\TeknikTaskDetayRaporu.xlsx"
BOSS_SAYFA = "Task Detail Report"
BINA_CSV = str(yollar.VERI / "master" / "bina_master.csv")
ANALIZ_JSON = os.path.join(CIKTI_GIRDI, "is_emri_analizi.json")

# ------------------------------------------------------------------ zaman
T0 = datetime(2026, 9, 29)       # t = 0  -> 29.09.2026 00:00 (Salı)
DOW_T0 = 1                       # 0 = Pazartesi
REF_DK = 18 * 60                 # BOSS dışa aktarım anı (~29.09 18:00) = simülasyon başlangıcı
GUN = 1440
GUN_SAYISI = 36                  # gün 0 (kısmi, 18:00'den) + 35 tam gün: 30.09-03.11 = 30 iş günü + 5 Pazar
GUN_ADI = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]


def gun(t):
    return int(t // GUN)


def dk(t):
    return t - (t // GUN) * GUN


def dow(t):
    return (DOW_T0 + int(t // GUN)) % 7


def dow_gun(d):
    return (DOW_T0 + d) % 7


# ------------------------------------------------------------------ geometri (km düzlemi)
LAT0, LON0 = 40.2, 29.0
KX = math.cos(math.radians(40.2)) * 111.32
KY = 110.54
OFIS = (40.22043814320989, 28.953528321918512)   # bayi ofisi (Nilüfer)


def xy(lat, lon):
    return (lon - LON0) * KX, (lat - LAT0) * KY


OFIS_XY = xy(*OFIS)

# master'da bina konumu olmayan ilçeler için yaklaşık ilçe merkezi (genel bilgi; ağ çağrısı yok)
ILCE_MERKEZ_EK = {"Çiftlikköy": (40.662, 29.321), "Altınova": (40.694, 29.508), "Armutlu": (40.520, 28.830),
                  "Çınarcık": (40.644, 29.120), "Termal": (40.607, 29.172), "Karacabey": (40.214, 28.360),
                  "Mustafakemalpaşa": (40.037, 28.408), "İznik": (40.429, 29.720), "Orhaneli": (39.903, 28.990),
                  "Keles": (39.913, 29.228), "Büyükorhan": (39.767, 28.891), "Yalova Merkez": (40.655, 29.275)}
BOSS_ILCE_DUZELT = {"Merkez": "Yalova Merkez"}
# Kapsam: arıza ekibinin metro alanı. Uzak ilçeler (Yalova, İnegöl, Gemlik, Karacabey, MKP, İznik...) yerel/hibrit
# teknisyene bağlı kabul edilir ve simülasyona alınmaz (son 24 s BOSS işlerinin %4'ü; birikimin %13'ü).
METRO = ("Nilüfer", "Osmangazi", "Yıldırım", "Mudanya", "Gürsu", "Kestel")

# ------------------------------------------------------------------ iş tipleri
# kod: (btk, hedef_saat = min(Turkcell FOX hedefi, 24), kanal, konumlu olasılığı (BOSS), yerinde süre ort dk)
TIP = {
    "BAGLANTI": (True, 12, "SAHA", 0.735, 30),
    "TV_ARIZA": (True, 6, "SAHA", 1.0, 30),
    "ARAMA": (True, 12, "SAHA", 0.667, 30),
    "DOPING_ARIZA": (True, 24, "SAHA", 1.0, 30),
    "MODEM_DEGISIKLIGI": (False, 24, "SAHA", 1.0, 35),
    "SUPERBOX_MODEM": (False, 24, "SAHA", 0.0, 25),
    "STB_DEGISIKLIGI": (False, 24, "SAHA", 1.0, 30),
    "UCRETLENDIRME": (False, 24, "SAHA", 0.5, 30),
    "EVRAK_SOSYAL": (False, 24, "SAHA", 0.0, 15),
    "EVRAK_TURKSAT": (False, 24, "SAHA", 0.0, 15),
    "CIHAZ_GERI_ALIM": (False, 24, "SAHA", 0.2, 15),
    "TURKSAT_CIHAZ_IADE": (False, 24, "SAHA", 0.0, 15),
    "IKINCI_DONANIM": (False, 24, "SAHA", 1.0, 55),
    "KANAL_SIKAYETI": (False, 24, "MASA", 0.0, 30),
    "SORU_CEVAP": (False, 24, "MASA", 0.0, 0),
    "CIHAZ_IADE": (False, 24, "LOJ", 0.275, 12),
}
BTK_TIP = [k for k, v in TIP.items() if v[0]]
KURYE_TIP = ("MODEM_DEGISIKLIGI", "STB_DEGISIKLIGI", "SUPERBOX_MODEM")
TELEFON_KAPANIS = ("tel_masa", "tel_tek")


# ================================================================== PARAMETRELER
def varsayilan():
    """Tüm varsayımlar tek yerde. VERİ = is_emri_analizi.json toplu sayımları; VARSAYIM = aralıkla taranır."""
    return dict(
        # --- giriş (VERİ: ANLATILAN GELEN 1-15 Eylül; hafta içi ort 337,7, Cmt 384, Paz 182) ---
        giris_gun=[337.7, 337.7, 337.7, 337.7, 337.7, 384.0, 182.0],
        giris_carpan=1.0,             # VARSAYIM tarama 0,85-1,15
        giris_sigma=0.15,             # günlük aşırı dağılım (lognormal)
        ikinci_donanim_gun=5.43,      # VERİ alt sınır
        # --- müşteri: gizli 'evde mi' durumu + telefon (VARSAYIM; 3 sınıf) ---
        # veri: önceki işinde ulaşılamayan müşteriye sonraki işte de %94 ulaşılamıyor -> kalıcı sınıf
        sinif_pay=(0.60, 0.25, 0.15), sinif_pay_notlu=(0.20, 0.35, 0.45),
        isyeri_p=(0.08, 0.22, 0.45),  # hafta içi 09-17 evde olmayan (çalışan) müşteri payı
        evde_gurultu=0.06,            # herhangi 2 saatlik blokta dışarıda olma (alışveriş vb.)
        aksam_disari=0.30,            # çalışan müşterinin akşam/hafta sonu blokta dışarıda olma olasılığı
        cevap_p=(0.80, 0.45, 0.12),   # hafta içi gündüz tek aramada açma (marjinal)
        rho=0.30,                     # P(açar | evde değil) / P(açar | evde): cep telefonu bilgisi
        evdeyok_hedef=None,           # tarama: habersiz ziyarette hafta içi gündüz ort. evde yok hedefi
        evdeyok_teyitli=0.05, evdeyok_randevu=0.08, gec_basari=0.6, evdeyok_aksamci_gunduz=0.25,
        sms_etkisi=0.6,               # SMS dilimi bildirilen, o saatte dışarıda olan müşterinin yine de
                                      # evde olamaması olasılığı (1 = SMS etkisiz / kanal yok)
        sonra_p=(0.10, 0.12, 0.15),   # ulaşıldığında 'ileri bir gün gelin' diyen müşteri
        # --- arıza doğası (VERİ: TAMAMLANDI 3-15 Eylül Arıza Nedeni, toplu) ---
        tel_pay=dict(BAGLANTI=0.286, TV_ARIZA=0.341, DOPING_ARIZA=0.337, ARAMA=0.25),
        sebeke_pay=dict(BAGLANTI=0.112, TV_ARIZA=0.143, DOPING_ARIZA=0.151, ARAMA=0.125),
        tel_carpan=1.0,               # VARSAYIM tarama 0,6-1,3 (telefonla çözülebilir pay çarpanı)
        altyapi_pay=0.02, altyapi_bilinen=0.5, altyapi_medyan_saat=72.0,
        tel_kendiliginden=0.4, tel_tau_ort_saat=6.0,
        q_kontrol=0.45,               # kısa kontrol aramasında (2 soru) çözülme
        q_teshis=0.85,                # masa uzaktan teşhis betiğinde (8-10 dk) çözülme
        sebeke_medyan_saat=6.0, sebeke_sigma=0.8, sebeke_kume_payi=0.5, olay_boyut_ek=3.0,
        sebeke_tespit=0.7,
        birikim_tel_ek=0.10,          # 72 s'ten eski birikim BTK işinde kendiliğinden düzelmiş olma +10 puan
        tekrar7_pay=0.25, tekrar_ek=0.06, tekrar_ek_tekrar7=0.20,   # telefonla kapanışın ek tekrar riski
        ftf=0.92, kanal_tv=0.02, iade_sistem=0.60, iade_getirir=0.5, ucret_iptal=0.15,
        kurye_kabul=dict(MODEM_DEGISIKLIGI=0.35, STB_DEGISIKLIGI=0.50, SUPERBOX_MODEM=0.70),
        kurye_basari=0.90, kurye_kapasite=40, kurye_var=True,
        sms_geri_donus=0.25,
        # --- teknisyen ---
        N=10, pazar_oran=0.55,
        gunduz=(510, 1110), aksam=(720, 1260), mola_gunduz=750, mola_aksam=960, mola_dk=30,
        hiz_sehir=25.0, hiz_yol=60.0, yol_katsayi=1.35, park_dk=5.0, sure_sigma=0.5,
        sure_tel=12, sure_sebeke=15, sure_altyapi=20, sure_duzelmis=10, sure_iptal=5,
        tek_arama_dk=(1.5, 2.5), kapida_bekle_dk=10,
        # --- operasyon arama havuzu ---
        O=8, O_aksam=4, O_pazar=3, verim=0.8,
        masa_acilis=510, masa_aksam_bas=1050, masa_kapanis=1230,
        masa_sure=dict(basarisiz=2.0, kontrol=4.0, randevu=4.0, teshis=10.0, kanal=4.0, dogrulama=3.0,
                       iade=3.0, kurye=8.0, sistem=2.0, noc=5.0, geri_arama=5.0, istisna=4.0, teyit=4.0,
                       tarama=5.0, ilk=3.0),
        randevu_blok_kap=2.2,         # 2 saatlik blokta teknisyen başına randevu tavanı (≈1,1 ziyaret/saat)
        senkron=None,                 # None = stratejinin kendi senkronu (30 dk)
        konumsuz_plan="mahalle",      # konumsuz işte planlama noktası: 'mahalle' (adres->mahalle) | 'ilce' merkezi
    )


# ================================================================== VERİ
def _norm_lok(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    s = str(v).strip()
    if s.endswith(".0"):
        s = s[:-2]
    if not s or s.lower() == "nan":
        return None
    if s.isdigit():
        s = s.zfill(8)
    return s


def veri_yukle():
    """Toplu parametreler + bina konumları + BOSS açık mevcut-müşteri işleri (yalnız gerekli alanlar)."""
    an = json.load(open(ANALIZ_JSON, encoding="utf-8"))
    P = an["parametreler"]
    b = pd.read_csv(BINA_CSV, usecols=["location_id", "ilce", "mahalle", "lat", "lon", "aktif_toplam"],
                    dtype={"location_id": str})
    b["lat"] = pd.to_numeric(b["lat"], errors="coerce")
    b["lon"] = pd.to_numeric(b["lon"], errors="coerce")
    b = b.dropna(subset=["lat", "lon"]).reset_index(drop=True)
    w = pd.to_numeric(b["aktif_toplam"], errors="coerce").fillna(0).clip(lower=0).to_numpy() + 0.2
    w = np.where(b["ilce"].isin(METRO).to_numpy(), w, 0.0)   # yalnız metro binalarından örnekle
    bx, by = xy(b["lat"].to_numpy(), b["lon"].to_numpy())
    ilce = b["ilce"].fillna("?").to_numpy()
    merkez = {}
    ilce_bina = {}
    w_tum = pd.to_numeric(b["aktif_toplam"], errors="coerce").fillna(0).clip(lower=0).to_numpy() + 0.2
    for il in np.unique(ilce):
        m = ilce == il
        ww = w_tum[m]
        merkez[il] = (float(np.average(bx[m], weights=ww)), float(np.average(by[m], weights=ww)))
        idx = np.nonzero(m)[0]
        ilce_bina[il] = (idx, ww / ww.sum())
    for il, (la, lo) in ILCE_MERKEZ_EK.items():
        merkez.setdefault(il, xy(la, lo))
    lok_idx = {str(l): i for i, l in enumerate(b["location_id"].astype(str))}
    # mahalle merkezi (konumsuz işte planlama: adres metninden yerel mahalle eşlemesi varsayımı)
    mah = (b["ilce"].fillna("?") + "|" + b["mahalle"].fillna("?")).to_numpy()
    mx = np.zeros(len(b))
    my = np.zeros(len(b))
    for key in np.unique(mah):
        m = mah == key
        ww = w_tum[m]
        mx[m] = np.average(bx[m], weights=ww)
        my[m] = np.average(by[m], weights=ww)

    # saat profili (VERİ)
    sp = np.array([P["varis_saat_profili_mevcut"].get(str(h), 0.0) for h in range(24)], float)
    sp = np.maximum(sp, 0.001)
    sp = sp / sp.sum()
    pay = dict(P["gunluk_giris_mevcut_tip_payi"])
    dahil = {k: v for k, v in pay.items() if k in TIP}
    dahil_top = sum(dahil.values())
    tipler = list(dahil)
    tip_w = np.array([dahil[k] for k in tipler]) / dahil_top

    # ---- BOSS birikim (başlangıç durumu) ----
    df = pd.read_excel(BOSS_XLSX, sheet_name=BOSS_SAYFA,
                       usecols=["Task Adı", "İlçe", "Task Başlangıç Tarihi", "Task Durumu", "Randevu Durumu",
                                "Randevu Başlangıç Tarihi", "Askıya Alınma Nedeni", "Lokasyon", "Son Açıklama"])
    birikim = []
    atlanan = defaultdict(int)
    # metro payı (VERİ): son 24 saatte açılan işlerin metro ilçelerindeki payı -> geliş hacmi çarpanı
    _ts = pd.to_datetime(df["Task Başlangıç Tarihi"], dayfirst=True, errors="coerce")
    _yas = (pd.Timestamp(T0) + pd.Timedelta(minutes=REF_DK) - _ts).dt.total_seconds() / 3600
    _son = df[_yas < 24]
    metro_pay = float(_son["İlçe"].astype(str).str.strip().isin(METRO).mean()) if len(_son) else 0.95
    for r in df.itertuples(index=False):
        kod = tk.boss_kod(r[0])
        if kod not in TIP:
            atlanan[kod] += 1
            continue
        ts = pd.to_datetime(r[2], dayfirst=True, errors="coerce")
        if pd.isna(ts):
            atlanan["tarih_yok"] += 1
            continue
        t0 = (ts.to_pydatetime() - T0).total_seconds() / 60.0
        il = BOSS_ILCE_DUZELT.get(str(r[1]).strip(), str(r[1]).strip())
        if il not in METRO:
            atlanan["metro_disi"] += 1
            continue
        lok = _norm_lok(r[7])
        bi = lok_idx.get(lok, -1) if lok else -1
        ws = None
        if str(r[4]).strip() == "Randevulu":
            rs = pd.to_datetime(r[5], dayfirst=True, errors="coerce")
            if not pd.isna(rs):
                ws = (rs.to_pydatetime() - T0).total_seconds() / 60.0
        notlu = "ULAŞILAMADI" in str(r[8]).upper() or "ULASILAMADI" in str(r[8]).upper()
        birikim.append(dict(tip=kod, t0=t0, ilce=il, bina=bi, durum=str(r[3]).strip(), ws=ws, notlu=notlu))
    return dict(P=P, bx=bx, by=by, mx=mx, my=my, bw=w / w.sum(), bcum=np.cumsum(w / w.sum()), bilce=ilce, merkez=merkez, ilce_bina=ilce_bina,
                saat=sp, tipler=tipler, tip_w=tip_w, dahil_top=dahil_top, birikim=birikim, metro_pay=metro_pay,
                birikim_atlanan=dict(atlanan), zon_cache={}, komsu_cache={})


def zon_merkez(V, K, seed=7):
    """K teknisyen bölgesi: tipik geliş konumlarından ağırlıklı k-ortalama (her gün aynı; önbellekli)."""
    if K in V["zon_cache"]:
        return V["zon_cache"][K]
    if K <= 0:
        V["zon_cache"][K] = np.zeros((0, 2))
        return V["zon_cache"][K]
    rng = np.random.default_rng(seed)
    n = 6000
    idx = rng.choice(len(V["bx"]), n, p=V["bw"])
    X = np.c_[V["bx"][idx], V["by"][idx]]
    C = X[rng.choice(len(X), K, replace=False)].copy()
    for _ in range(40):
        dd = ((X[:, None, :] - C[None, :, :]) ** 2).sum(-1)
        a = dd.argmin(1)
        for k in range(K):
            m = a == k
            if m.any():
                C[k] = X[m].mean(0)
    V["zon_cache"][K] = C
    return C


# ================================================================== VARLIKLAR
class Is:
    __slots__ = ("id", "tip", "t0", "btk", "hedef", "kanal", "x", "y", "px", "py", "konumlu", "ilce",
                 "sinif", "tercih", "sonra_gun", "doga", "tel_kendi", "tau", "tekrar7", "gecmis_bilinen",
                 "altyapi_bilinen", "kurye_kabul", "ftf_ok", "sure", "U", "na", "nv", "nr",
                 "birikim", "notlu", "teyit", "pencere", "uygun", "state", "havuzda", "gorev", "token",
                 "t_gor", "t_kapat", "tur", "ziyaret", "bosa", "cagri_ops", "cagri_tek", "son_cevapsiz",
                 "deneme", "tek_deneme", "erteledi", "zon", "zon_gun", "kume", "lane", "slot", "olay",
                 "sms_ok", "dolgu", "tarandi", "kidemli", "bas_durum", "ws0", "hedef_t", "atla", "kacan_we", "isyeri")

    def __init__(self):
        self.na = self.nv = self.nr = 0
        self.teyit = "habersiz"
        self.pencere = None
        self.uygun = 0.0
        self.state = "GELECEK"
        self.havuzda = False
        self.gorev = None
        self.token = 0
        self.t_gor = None
        self.t_kapat = None
        self.tur = None
        self.ziyaret = self.bosa = self.cagri_ops = self.cagri_tek = 0
        self.son_cevapsiz = -1e9
        self.deneme = self.tek_deneme = 0
        self.erteledi = False
        self.zon = -1
        self.zon_gun = -1
        self.kume = None
        self.lane = None
        self.slot = None
        self.olay = None
        self.sms_ok = False
        self.dolgu = False
        self.tarandi = False
        self.kidemli = False
        self.notlu = False
        self.birikim = False
        self.bas_durum = None
        self.ws0 = None
        self.atla = 0
        self.kacan_we = None


class Gorev:
    __slots__ = ("j", "amac", "hazir", "son", "oncelik", "meta", "iptal", "seq")

    def __init__(self, j, amac, hazir, son, oncelik, meta, seq):
        self.j, self.amac, self.hazir, self.son, self.oncelik, self.meta = j, amac, hazir, son, oncelik, meta
        self.iptal = False
        self.seq = seq


class Tek:
    __slots__ = ("i", "zon", "x", "y", "bas", "bit", "mola", "mola_ok", "free", "aktif", "km", "ziyaret",
                 "bosa", "cagri", "bos_dk", "sayac", "aksam", "sektor", "dolgu_say")

    def __init__(self, i, zon, x, y, bas, bit, mola, aksam=False):
        self.i, self.zon, self.x, self.y = i, zon, x, y
        self.bas, self.bit, self.mola = bas, bit, mola
        self.mola_ok = False
        self.free = bas
        self.aktif = True
        self.km = 0.0
        self.ziyaret = self.bosa = self.cagri = 0
        self.bos_dk = 0.0
        self.sayac = 0
        self.aksam = aksam
        self.sektor = None
        self.dolgu_say = defaultdict(int)


# ================================================================== DÜNYA ÜRETİMİ (ortak)
def _lognormal_ort(rng, ort, sigma):
    mu = math.log(ort) - sigma * sigma / 2
    return float(rng.lognormal(mu, sigma))


def _komsular(V, bi, r_km=0.3):
    c = V["komsu_cache"]
    if bi in c:
        return c[bi]
    dx = V["bx"] - V["bx"][bi]
    dy = V["by"] - V["by"][bi]
    idx = np.nonzero(dx * dx + dy * dy <= r_km * r_km)[0]
    ww = V["bw"][idx]
    c[bi] = (idx, ww / ww.sum())
    return c[bi]


def _dog(M, j, rng, birikim_yas_saat=0.0):
    """Arıza doğası ve gizli (strateji bağımsız) özellikler."""
    P = M.P
    tip = j.tip
    u = rng.random()
    j.tel_kendi = False
    j.tau = 1e12
    if j.btk:
        pt = P["tel_pay"][tip] * P["tel_carpan"]
        if birikim_yas_saat > 72:
            pt += P["birikim_tel_ek"]
        ps = P["sebeke_pay"][tip] * (1 - P["sebeke_kume_payi"])
        pa = P["altyapi_pay"]
        if u < pt:
            j.doga = "tel"
            j.tel_kendi = rng.random() < P["tel_kendiliginden"]
            if j.tel_kendi:
                j.tau = j.t0 + rng.exponential(P["tel_tau_ort_saat"] * 60)
        elif u < pt + ps:
            j.doga = "sebeke"
            j.tau = j.t0 + 60 * math.exp(math.log(P["sebeke_medyan_saat"]) + P["sebeke_sigma"] * rng.standard_normal())
        elif u < pt + ps + pa:
            j.doga = "altyapi"
        else:
            j.doga = "saha"
    elif tip == "KANAL_SIKAYETI":
        j.doga = "kanal_tv" if u < P["kanal_tv"] else "masa"
    elif tip == "SORU_CEVAP":
        j.doga = "masa"
    elif tip == "CIHAZ_IADE":
        j.doga = "iade_sistem" if u < P["iade_sistem"] else "iade_musteri"
    elif tip == "UCRETLENDIRME":
        j.doga = "iptal" if u < P["ucret_iptal"] else "saha"
    else:
        j.doga = "saha"
    j.tekrar7 = j.btk and rng.random() < P["tekrar7_pay"]
    j.gecmis_bilinen = rng.random() < 0.35
    j.altyapi_bilinen = rng.random() < P["altyapi_bilinen"]
    j.kurye_kabul = tip in KURYE_TIP and rng.random() < P["kurye_kabul"][tip]
    j.ftf_ok = rng.random() < P["ftf"]
    ort = TIP[tip][4] or 15
    j.sure = _lognormal_ort(rng, ort, P["sure_sigma"])
    j.U = rng.random(48)


def _sinif_tercih(M, j, rng, notlu=False):
    P = M.P
    pay = P["sinif_pay_notlu"] if notlu else P["sinif_pay"]
    u = rng.random()
    j.sinif = 0 if u < pay[0] / sum(pay) else (1 if u < (pay[0] + pay[1]) / sum(pay) else 2)
    j.isyeri = rng.random() < M.isyeri[j.sinif]
    if rng.random() < P["sonra_p"][j.sinif]:
        j.tercih = 2
    else:
        j.tercih = 1 if j.isyeri else 0
    j.sonra_gun = int(rng.integers(1, 4))


def _konum(M, j, rng, bi=None, ilce=None, konumlu_p=None):
    V = M.V
    if bi is None and ilce is None:
        bi = int(min(np.searchsorted(V["bcum"], rng.random()), len(V["bx"]) - 1))
    if bi is not None and bi >= 0:
        b_gercek = bi
        j.ilce = V["bilce"][bi]
        kp = TIP[j.tip][3] if konumlu_p is None else konumlu_p
        j.konumlu = rng.random() < kp
    else:
        j.ilce = ilce
        idx, ww = V["ilce_bina"][ilce]
        b_gercek = int(idx[min(np.searchsorted(np.cumsum(ww), rng.random()), len(idx) - 1)])
        j.konumlu = False
    j.x, j.y = float(V["bx"][b_gercek]), float(V["by"][b_gercek])
    if j.konumlu:
        j.px, j.py = j.x, j.y
    elif M.P.get("konumsuz_plan", "mahalle") == "mahalle":
        j.px, j.py = float(V["mx"][b_gercek]), float(V["my"][b_gercek])
    else:
        j.px, j.py = V["merkez"].get(j.ilce, OFIS_XY)


def _is_kur(M, tip, t0, rng):
    j = Is()
    j.id = len(M.isler)
    j.tip = tip
    j.t0 = float(t0)
    j.btk, hs, j.kanal = TIP[tip][0], TIP[tip][1], TIP[tip][2]
    j.hedef = j.t0 + hs * 60
    M.isler.append(j)
    return j


def dunya_uret(M):
    """Tohuma bağlı ortak dünya: 35 günlük gelişler + şebeke olayları + BOSS birikimi."""
    V, P, seed = M.V, M.P, M.seed
    rng = np.random.default_rng([seed, 1])
    lam_top = V["dahil_top"]
    for d in range(GUN_SAYISI):
        dw = dow_gun(d)
        lam = P["giris_gun"][dw] * P["giris_carpan"] * lam_top * V["metro_pay"] * float(np.exp(rng.normal(0, P["giris_sigma"]) - P["giris_sigma"] ** 2 / 2))
        bas = REF_DK if d == 0 else 0
        pay_gun = 1.0 if d > 0 else float(V["saat"][18:].sum())
        # şebeke kümeleri: BTK şebeke hacminin 'sebeke_kume_payi' kadarı olay olarak gelir
        btk_pay = sum(V["tip_w"][i] for i, k in enumerate(V["tipler"]) if TIP[k][0])
        seb_ort = sum(V["tip_w"][i] * P["sebeke_pay"][k] for i, k in enumerate(V["tipler"]) if TIP[k][0]) / btk_pay
        kume_is = lam * btk_pay * seb_ort * P["sebeke_kume_payi"]
        n = int(rng.poisson(lam * pay_gun * (1 - btk_pay * seb_ort * P["sebeke_kume_payi"])))
        tips = rng.choice(len(V["tipler"]), n, p=V["tip_w"])
        saat = rng.choice(24, n, p=V["saat"])
        dakika = rng.uniform(0, 60, n)
        for k in range(n):
            t0 = d * GUN + saat[k] * 60 + dakika[k]
            if t0 < bas:
                continue
            j = _is_kur(M, V["tipler"][tips[k]], t0, rng)
            jr = np.random.default_rng([seed, 2, j.id])
            _sinif_tercih(M, j, jr)
            _konum(M, j, jr)
            _dog(M, j, jr)
        # 2. Donanım (VERİ alt sınır 5,43/gün)
        n2 = int(rng.poisson(P["ikinci_donanim_gun"] * P["giris_carpan"] * V["metro_pay"] * pay_gun * P["giris_gun"][dw] / 337.7))
        for k in range(n2):
            t0 = d * GUN + rng.choice(24, p=V["saat"]) * 60 + rng.uniform(0, 60)
            if t0 < bas:
                continue
            j = _is_kur(M, "IKINCI_DONANIM", t0, rng)
            jr = np.random.default_rng([seed, 2, j.id])
            _sinif_tercih(M, j, jr)
            _konum(M, j, jr)
            _dog(M, j, jr)
        # şebeke olayları
        n_olay = int(rng.poisson(kume_is * pay_gun / (1 + P["olay_boyut_ek"])))
        for e in range(n_olay):
            bas_t = d * GUN + rng.choice(24, p=V["saat"]) * 60 + rng.uniform(0, 60)
            if bas_t < bas:
                continue
            bi = int(min(np.searchsorted(V["bcum"], rng.random()), len(V["bx"]) - 1))
            idx, ww = _komsular(V, bi)
            boyut = 1 + int(rng.poisson(P["olay_boyut_ek"]))
            tau = bas_t + 60 * math.exp(math.log(P["sebeke_medyan_saat"]) + P["sebeke_sigma"] * rng.standard_normal())
            for s in range(boyut):
                t0 = bas_t + min(rng.exponential(45), 180)
                tip = "BAGLANTI" if rng.random() < 0.83 else "TV_ARIZA"
                j = _is_kur(M, tip, t0, rng)
                jr = np.random.default_rng([seed, 2, j.id])
                _sinif_tercih(M, j, jr)
                b2 = int(idx[jr.choice(len(idx), p=ww)])
                _konum(M, j, jr, bi=b2)
                _dog(M, j, jr)
                j.doga = "sebeke"
                j.tel_kendi = False
                j.tau = tau
                j.olay = (d, e)
    # ---- birikim (BOSS 29.09 açık mevcut-müşteri işleri) ----
    for r in V["birikim"]:
        j = _is_kur(M, r["tip"], r["t0"], rng)
        jr = np.random.default_rng([seed, 3, j.id])
        j.birikim = True
        j.notlu = r["notlu"]
        j.bas_durum = r["durum"]
        j.ws0 = r["ws"]
        _sinif_tercih(M, j, jr, notlu=r["notlu"])
        _konum(M, j, jr, bi=(r["bina"] if r["bina"] >= 0 else None), ilce=r["ilce"], konumlu_p=1.0)
        _dog(M, j, jr, birikim_yas_saat=(REF_DK - r["t0"]) / 60.0)
        if j.doga == "sebeke" and j.tau < REF_DK:
            pass  # olay bitmiş: temasla 'düzeldi'
    for j in M.isler:
        if not j.birikim:
            heapq.heappush(M.gelecek, (j.t0, j.id))


# ================================================================== MOTOR
class Motor:
    def __init__(self, V, P, strateji_cls, seed):
        self.V, self.P, self.seed = V, P, seed
        self.H = GUN_SAYISI * GUN
        self.isler = []
        self.gelecek = []
        # gizli evde-olma modeli: hafta içi gündüz habersiz ziyarette evde yok = isyeri + (1-isyeri)*gürültü
        g = P["evde_gurultu"]
        base = sum(a * (b + (1 - b) * g) for a, b in zip(P["sinif_pay"], P["isyeri_p"]))
        if P.get("evdeyok_hedef"):
            k = max(0.0, (P["evdeyok_hedef"] - g) / max(1e-9, base - g))
        else:
            k = 1.0
        self.isyeri = [min(0.95, x * k) for x in P["isyeri_p"]]
        self.evdeyok_gunduz_ort = sum(a * (b + (1 - b) * g) for a, b in zip(P["sinif_pay"], self.isyeri))
        # açma olasılığı evde/dışarıda: marjinal gündüz değerini koruyacak şekilde
        self.c_ev, self.c_dis = [], []
        for c, (pa, iy) in enumerate(zip(P["cevap_p"], self.isyeri)):
            ph = (1 - iy) * (1 - g)
            ch = min(0.97, pa / (ph + P["rho"] * (1 - ph)))
            self.c_ev.append(ch)
            self.c_dis.append(ch * P["rho"])
        dunya_uret(self)
        cap = len(self.isler) + 5000
        self.PX = np.zeros(cap)
        self.PY = np.zeros(cap)
        self.ZON = np.full(cap, -1, dtype=np.int64)
        self.INPOOL = np.zeros(cap, dtype=bool)
        for j in self.isler:
            self.PX[j.id] = j.px
            self.PY[j.id] = j.py
        self.son_btk = []          # (t_gor, is) son 6 saatte görünür olmuş konumlu BTK işleri
        self.saha = []
        self.masa = []
        self.masa_kap = 0.0
        self.zam = []
        self.seq = 0
        self.teknisyenler = []
        self.ledger = defaultdict(float)
        self.kurye_say = defaultdict(int)
        self.gun_no = -1
        self.g = defaultdict(float)
        self.gunluk = []
        self.kadro_cache = {}
        self.st = strateji_cls(self)
        self.senkron = P["senkron"] or self.st.senkron
        self.olay_say = defaultdict(int)

    # ---------------------------------------------------------- zaman / kadro
    def zamanla(self, t, fn, *args):
        self.seq += 1
        heapq.heappush(self.zam, (t, self.seq, fn, args))

    def kadro(self, d):
        if d in self.kadro_cache:
            return self.kadro_cache[d]
        dw = dow_gun(d)
        n = self.P["N"] if dw != 6 else int(math.ceil(self.P["N"] * self.P["pazar_oran"]))
        r = self.st.vardiya(n, dw)
        self.kadro_cache[d] = r
        return r

    def zon_merkez_gun(self, d):
        ng, na = self.kadro(d)
        return zon_merkez(self.V, ng)

    def sektor_merkez(self, d):
        ng, na = self.kadro(d)
        return zon_merkez(self.V, na) if na > 0 else np.zeros((0, 2))

    def sektor_bul(self, zon, d):
        """Gündüz bölgesinin bağlı olduğu akşam sektörü (akşam teknisyeni sayısı kadar)."""
        ng, na = self.kadro(d)
        if na <= 0 or zon < 0:
            return -1
        key = ("sek", ng, na)
        if key not in self.kadro_cache:
            C = zon_merkez(self.V, ng)
            S = zon_merkez(self.V, na)
            self.kadro_cache[key] = ((C[:, None, 0] - S[None, :, 0]) ** 2 + (C[:, None, 1] - S[None, :, 1]) ** 2).argmin(1)
        return int(self.kadro_cache[key][zon])

    def zon_bul(self, j, d):
        C = self.zon_merkez_gun(d)
        if len(C) == 0:
            return -1
        return int((((C[:, 0] - j.px) ** 2) + ((C[:, 1] - j.py) ** 2)).argmin())

    def zon(self, j):
        return int(self.ZON[j.id])

    def gun_basla(self, d):
        self.gun_no = d
        ng, na = self.kadro(d)
        C = zon_merkez(self.V, ng)
        n = len(self.isler)
        if len(C):
            dd = (self.PX[:n, None] - C[None, :, 0]) ** 2 + (self.PY[:n, None] - C[None, :, 1]) ** 2
            self.ZON[:n] = dd.argmin(1)
        P = self.P
        gb = d * GUN
        self.teknisyenler = []
        gec = self.st.gecikme
        for i in range(ng):
            self.teknisyenler.append(Tek(i, i, float(C[i, 0]), float(C[i, 1]), gb + P["gunduz"][0] + gec,
                                         gb + P["gunduz"][1], gb + P["mola_gunduz"]))
        S = self.sektor_merkez(d)
        for i in range(na):
            tkn = Tek(ng + i, None, float(S[i, 0]), float(S[i, 1]), gb + P["aksam"][0], gb + P["aksam"][1],
                      gb + P["mola_aksam"], aksam=True)
            tkn.sektor = i
            self.teknisyenler.append(tkn)
        if d == 0:
            for tkn in self.teknisyenler:
                tkn.aktif = False  # 29.09 akşamı: simülasyon 18:00'de başlar, saha kapanmış kabul
        self.st.gun_basla(d)

    def gun_bitir(self):
        if self.gun_no < 0:
            return
        t = (self.gun_no + 1) * GUN
        g = dict(self.g)
        g["gun"] = self.gun_no
        acik = 0
        acik24 = 0
        bir_acik = 0
        for j in self.isler:
            if j.t0 >= t or j.state == "KAPALI":
                continue
            acik += 1
            if t - j.t0 > GUN:
                acik24 += 1
            if j.birikim and REF_DK - j.t0 > GUN:
                bir_acik += 1
        g["acik"] = acik
        g["acik_24s_ustu"] = acik24
        g["birikim_gecikmis_acik"] = bir_acik
        g["tek_gun"] = sum(1 for tkn in self.teknisyenler if tkn.ziyaret > 0)
        g["tek_bos_dk"] = sum(tkn.bos_dk for tkn in self.teknisyenler)
        self.gunluk.append(g)
        self.g = defaultdict(float)
        # kaçan randevular: günü geçmiş pencereler stratejiye bildirilir
        for j in self.havuz_listesi():
            if j.pencere is not None and j.pencere[1] < t - 60:
                if j.kacan_we != j.pencere[1]:
                    self.gunluk[-1]["kacan_randevu"] = self.gunluk[-1].get("kacan_randevu", 0) + 1
                    j.kacan_we = j.pencere[1]
                    self.st.kacan_randevu(j, t)

    # ---------------------------------------------------------- olasılıklar
    def aksam_mi(self, t):
        return dk(t) >= 17 * 60

    @staticmethod
    def _hash(a, b):
        x = math.sin(a * 12.9898 + b * 78.233) * 43758.5453
        return x - math.floor(x)

    def evde(self, j, t):
        """Gizli durum: müşteri t anında evde mi? (işe ve 2 saatlik bloğa bağlı, stratejiden bağımsız)"""
        m = dk(t)
        gunduz = dow(t) < 5 and 540 <= m < 1020
        if gunduz and j.isyeri:
            return False
        g = self.P["evde_gurultu"]
        if j.isyeri:
            g = max(g, self.P["aksam_disari"])
        return self._hash(j.id + 0.5, int(t // 120)) >= g

    def cevap(self, j, t):
        u = j.U[j.na % 16]
        j.na += 1
        p = self.c_ev[j.sinif] if self.evde(j, t) else self.c_dis[j.sinif]
        ok = u < p
        if not ok:
            j.son_cevapsiz = t
        return ok

    def kapida_basari(self, j, t):
        """Ziyarette müşteri kapıyı açar mı? teyit durumuna göre (u: işe bağlı çekiliş)."""
        P = self.P
        u = j.U[16 + (j.nv % 8)]
        j.nv += 1
        gec = j.pencere is not None and t > j.pencere[1]
        if j.teyit == "teyitli":
            if gec:
                return self.evde(j, t) and u < P["gec_basari"]
            return u >= P["evdeyok_teyitli"]
        if j.teyit == "randevu":
            if gec:
                return self.evde(j, t) and u < P["gec_basari"]
            if j.tercih == 1 and dow(t) < 5 and j.pencere is not None and dk(j.pencere[0]) < 17 * 60:
                return u >= P["evdeyok_aksamci_gunduz"]
            return u >= P["evdeyok_randevu"]
        if self.evde(j, t):
            return True
        if j.teyit == "sms":
            # dilimi SMS ile öğrenen ve o saatte dışarıda olan müşteri: bir kısmı evde birini bulundurur
            return u >= P["sms_etkisi"] and not gec
        return False

    def simdi_musait(self, j, t):
        """Telefonda ulaşılan müşteri şimdi (1-3 saat içinde) ziyareti kabul eder mi?"""
        if j.tercih == 2:
            return False
        u = j.U[26 + (j.nr % 6)]
        j.nr += 1
        return self.evde(j, t) and self.evde(j, t + 90) and u < 0.95

    def cozum(self, j, t, tur):
        """Telefon temasında sonuç: 'cozuldu' | 'sebeke' (şebeke arızası tespit edildi) | 'iptal' | 'saha'."""
        d = j.doga
        if d == "sebeke":
            if t >= j.tau:
                return "cozuldu"
            if tur == "teshis" and j.U[25] < self.P["sebeke_tespit"]:
                return "sebeke"
            return "saha"
        if d == "tel":
            if j.tel_kendi and t >= j.tau:
                return "cozuldu"
            q = self.P["q_teshis"] if tur == "teshis" else self.P["q_kontrol"]
            return "cozuldu" if j.U[24] < q else "saha"
        if d == "iptal":
            return "iptal"
        return "saha"

    # ---------------------------------------------------------- yol
    def yol_dk(self, km_duz):
        P = self.P
        r = km_duz * P["yol_katsayi"]
        return P["park_dk"] + (min(r, 10.0) / P["hiz_sehir"] + max(r - 10.0, 0.0) / P["hiz_yol"]) * 60.0

    def yol_dk_vec(self, d):
        P = self.P
        r = d * P["yol_katsayi"]
        return P["park_dk"] + (np.minimum(r, 10.0) / P["hiz_sehir"] + np.maximum(r - 10.0, 0.0) / P["hiz_yol"]) * 60.0

    # ---------------------------------------------------------- havuz / masa / bekletme
    def havuza(self, j, teyit="habersiz", pencere=None, uygun=0.0):
        if j.state == "KAPALI":
            return
        j.state = "SAHA"
        self.INPOOL[j.id] = True
        j.teyit = teyit
        j.pencere = pencere
        j.uygun = uygun
        j.token += 1

    def masa_ekle(self, j, amac, hazir, son=None, oncelik=5, meta=None, durum=True):
        if j.state == "KAPALI":
            return None
        if j.gorev is not None:
            j.gorev.iptal = True
        self.seq += 1
        g = Gorev(j, amac, hazir, son, oncelik, meta, self.seq)
        j.gorev = g
        if durum:
            j.state = "MASA"
            self.INPOOL[j.id] = False
            j.token += 1
        self.masa.append(g)
        return g

    def beklet(self, j, until, fn=None, *args):
        if j.state == "KAPALI":
            return
        j.state = "BEKLE"
        self.INPOOL[j.id] = False
        j.token += 1
        if j.gorev is not None:
            j.gorev.iptal = True
            j.gorev = None
        self.zamanla(until, self._uyan, j, j.token, fn, args)

    def _uyan(self, t, j, token, fn, args):
        if j.state == "KAPALI" or j.token != token:
            return
        (fn or self.st.uyan)(j, t, *args)

    def kapat(self, j, t, tur):
        if j.state == "KAPALI":
            return
        j.state = "KAPALI"
        self.INPOOL[j.id] = False
        j.t_kapat = t
        j.tur = tur
        j.pencere = None
        j.token += 1
        if j.gorev is not None:
            j.gorev.iptal = True
            j.gorev = None
        self.g["kapanis"] += 1
        self.g["kapanis_" + tur] += 1
        if tur in TELEFON_KAPANIS and j.btk:
            r = self.P["tekrar_ek_tekrar7"] if j.tekrar7 else self.P["tekrar_ek"]
            if j.U[40] < r:
                self.tekrar_uret(j, t + (1 + 6 * j.U[41]) * GUN)

    def tekrar_uret(self, ebeveyn, t_yeni, doga=None):
        if t_yeni >= self.H:
            return
        jr = np.random.default_rng([self.seed, 5, ebeveyn.id])
        j = _is_kur(self, ebeveyn.tip, t_yeni, jr)
        j.sinif, j.tercih, j.sonra_gun, j.isyeri = ebeveyn.sinif, ebeveyn.tercih, ebeveyn.sonra_gun, ebeveyn.isyeri
        j.x, j.y, j.px, j.py, j.konumlu, j.ilce = ebeveyn.x, ebeveyn.y, ebeveyn.px, ebeveyn.py, ebeveyn.konumlu, ebeveyn.ilce
        _dog(self, j, jr)
        if doga is None:
            j.doga = "saha" if jr.random() < 0.7 else "tel"
        else:
            j.doga = doga
        j.tel_kendi = False
        j.tau = 1e12
        j.tekrar7 = True
        self.g["tekrar_uretilen"] += 1
        if j.id >= len(self.PX):
            ek = 5000
            self.PX = np.concatenate([self.PX, np.zeros(ek)])
            self.PY = np.concatenate([self.PY, np.zeros(ek)])
            self.ZON = np.concatenate([self.ZON, np.full(ek, -1, dtype=np.int64)])
            self.INPOOL = np.concatenate([self.INPOOL, np.zeros(ek, dtype=bool)])
        self.PX[j.id] = j.px
        self.PY[j.id] = j.py
        self.ZON[j.id] = self.zon_bul(j, max(self.gun_no, 0))
        heapq.heappush(self.gelecek, (j.t0, j.id))

    def altyapi_bilet(self, j, t):
        """Bina bazlı tek ticket (OneDesk/EKSP): çözülene kadar sahaya gönderilmez."""
        self.g["altyapi_bilet"] += 1
        sure = 60 * math.exp(math.log(self.P["altyapi_medyan_saat"]) + 0.5 * (j.U[44] * 2 - 1) * 1.2)
        self.beklet(j, t + sure, self._altyapi_coz)

    def _altyapi_coz(self, j, t):
        self.kapat(j, t, "altyapi")

    def sms(self, j, t):
        """Şablon SMS; müşteri %25 olasılıkla masa hattını geri arar (işe bağlı çekiliş)."""
        self.g["sms"] += 1
        if not j.sms_ok and j.U[42] < self.P["sms_geri_donus"]:
            j.sms_ok = True
            self.zamanla(t + 60 * (0.5 + 7.5 * j.U[43]), self._geri_arama, j)

    def _geri_arama(self, t, j):
        if j.state in ("KAPALI", "SAHA", "ZIYARET"):
            return
        self.masa_ekle(j, "geri_arama", t, oncelik=0, meta=j.lane)

    def randevu_ver(self, j, t, lead=120, maxgun=4, aksam_izin=True, zon_sabit=None):
        """Müşteri tercihine uygun en erken 2 saatlik pencere (bölge kapasite defterine göre)."""
        P = self.P
        en_erken = t + lead
        ertele = False
        if j.tercih == 2:
            ee = (gun(t) + j.sonra_gun) * GUN + 540
            if ee > en_erken:
                en_erken = ee
                ertele = True
        d0 = gun(en_erken)
        secim = None
        yedek = None
        for d in range(d0, d0 + maxgun + 1):
            ng, na = self.kadro(d)
            dw = dow_gun(d)
            if self.st.pazar_sadece_btk and dw == 6 and not j.btk:
                continue
            saatler = []
            if ng > 0:
                saatler += [(h, "G") for h in range(9, 17)]
            if na > 0 and aksam_izin:
                saatler += [(h, "A") for h in (17, 18, 19)]
            zon_d = self.zon_bul(j, d) if zon_sabit is None else zon_sabit
            for h, v in saatler:
                ws = d * GUN + h * 60
                if ws < en_erken:
                    continue
                if j.tercih == 1 and dw < 5 and h < (17 if na > 0 else 16):
                    continue
                if yedek is None:
                    yedek = ws
                if v == "G":
                    key = ("G", zon_d, d, (h - 9) // 2)
                    cap = P["randevu_blok_kap"] * self.st.randevu_pay
                else:
                    key = ("A", self.sektor_bul(zon_d, d), d, (h - 17) // 2)
                    cap = P["randevu_blok_kap"] * self.st.randevu_pay
                if self.ledger[key] + 1 <= cap + 0.5:
                    self.ledger[key] += 1
                    secim = ws
                    break
            if secim is not None:
                break
        if secim is None:
            secim = yedek if yedek is not None else en_erken
            self.g["randevu_tasma"] += 1
        teyit = "teyitli" if secim - t <= 180 else "randevu"
        if ertele or (secim >= j.t0 + GUN and j.tercih == 2):
            j.erteledi = True
        self.g["randevu"] += 1
        self.havuza(j, teyit, (secim, secim + 120))
        return secim

    # ---------------------------------------------------------- aday seçimi
    def son_btk_yakin(self, j, t, pencere_dk, r_km=0.3):
        """Son 'pencere_dk' içinde görünür olmuş konumlu BTK işlerinden r_km içindekiler (j hariç)."""
        while self.son_btk and t - self.son_btk[0][0] > 400:
            self.son_btk.pop(0)
        out = []
        for tg, x in self.son_btk:
            if x is j or t - x.t0 > pencere_dk or x.t0 > t:
                continue
            if abs(x.px - j.px) <= r_km and abs(x.py - j.py) <= r_km and math.hypot(x.px - j.px, x.py - j.py) <= r_km:
                out.append(x)
        return out

    def havuz_listesi(self):
        return [self.isler[i] for i in np.nonzero(self.INPOOL[:len(self.isler)])[0]]

    def havuz_yakin(self, x, y, r):
        """Havuzda (x,y)'ye r km içindeki işler."""
        n = len(self.isler)
        ids = np.nonzero(self.INPOOL[:n])[0]
        if len(ids) == 0:
            return []
        d = np.hypot(self.PX[ids] - x, self.PY[ids] - y)
        return [self.isler[i] for i in ids[d <= r]]

    def sec_katman(self, tkn, t, fn, filtre=None):
        """Aday katmanları (kendi bölgesi+3 km -> 10 km -> tümü) sırayla denenir; fn(pool, d) ilk sonucu döner."""
        n = len(self.isler)
        ids = np.nonzero(self.INPOOL[:n])[0]
        if len(ids) == 0:
            return None
        d = np.hypot(self.PX[ids] - tkn.x, self.PY[ids] - tkn.y)
        onceki = -1
        for kademe in range(3):
            if kademe == 0 and tkn.zon is not None:
                m = (self.ZON[ids] == tkn.zon) | (d <= 3.0)
            elif kademe == 0 and tkn.sektor is not None:
                ng, na = self.kadro(self.gun_no)
                smap = self.kadro_cache.get(("sek", ng, na))
                if smap is None:
                    self.sektor_bul(0, self.gun_no)
                    smap = self.kadro_cache[("sek", ng, na)]
                m = (smap[np.clip(self.ZON[ids], 0, len(smap) - 1)] == tkn.sektor) | (d <= 3.0)
            elif kademe == 1:
                m = d <= 10.0
            else:
                m = np.ones(len(ids), dtype=bool)
            k = int(m.sum())
            if k == 0 or k == onceki:
                continue
            onceki = k
            sub = ids[m]
            dsub = d[m]
            pool, dd = [], []
            for q, i in enumerate(sub):
                j = self.isler[i]
                if j.uygun <= t and (filtre is None or filtre(j)):
                    pool.append(j)
                    dd.append(dsub[q])
            if pool:
                r = fn(pool, np.array(dd))
                if r is not None:
                    return r
        return None

    def adaylar(self, tkn, t, filtre=None):
        """Teknisyenin aday işleri: kendi bölgesi + 3 km (yoksa 10 km, yoksa tümü); uygunluk/filtre sonra."""
        n = len(self.isler)
        ids = np.nonzero(self.INPOOL[:n])[0]
        if len(ids) == 0:
            return [], None
        d = np.hypot(self.PX[ids] - tkn.x, self.PY[ids] - tkn.y)
        for kademe in range(3):
            if kademe == 0 and tkn.zon is not None:
                m = (self.ZON[ids] == tkn.zon) | (d <= 3.0)
            elif kademe <= 1 and tkn.zon is not None:
                m = d <= 10.0
            else:
                m = np.ones(len(ids), dtype=bool)
            if not m.any():
                continue
            sub = ids[m]
            dsub = d[m]
            pool, dd = [], []
            for k, i in enumerate(sub):
                j = self.isler[i]
                if j.uygun <= t and (filtre is None or filtre(j)):
                    pool.append(j)
                    dd.append(dsub[k])
            if pool:
                return pool, np.array(dd)
            if tkn.zon is None:
                break
        return [], None

    def pencere_sec(self, tkn, t, pool, d, tol=30, min_ws=None):
        """P0: penceresi açılmak üzere / açık işler. Kaçmak üzere olan (bitişe <45 dk) varsa en acili,
        yoksa en yakını (zikzak yerine kısa yol)."""
        tr = self.yol_dk_vec(d)
        risk, bk_r = None, None
        yakin, bk_y = None, None
        for i, j in enumerate(pool):
            if j.pencere is None:
                continue
            ws, we = j.pencere
            if min_ws is not None and ws < min_ws:
                continue
            varis = t + tr[i]
            if ws - tol > varis:
                continue
            if we - varis < 45:
                if bk_r is None or we < bk_r:
                    risk, bk_r = j, we
            elif bk_y is None or tr[i] < bk_y:
                yakin, bk_y = j, tr[i]
        return risk if risk is not None else yakin

    # ---------------------------------------------------------- saha
    def tek_ara(self, tkn, j):
        ok = self.cevap(j, tkn.free)
        tkn.free += self.P["tek_arama_dk"][1 if ok else 0]
        self.g["tek_cagri"] += 1
        j.cagri_tek += 1
        tkn.cagri += 1
        return ok

    def git(self, tkn, j):
        P = self.P
        t = tkn.free
        dist = math.hypot(tkn.x - j.x, tkn.y - j.y)
        ta = t + self.yol_dk(dist)
        if j.pencere is not None and ta < j.pencere[0] and self.st.pencere_bekle:
            tkn.bos_dk += j.pencere[0] - ta
            ta = j.pencere[0]
        km = dist * P["yol_katsayi"]
        tkn.km += km
        self.g["km"] += km
        tkn.x, tkn.y = j.x, j.y
        j.ziyaret += 1
        tkn.ziyaret += 1
        self.g["ziyaret"] += 1
        if j.birikim:
            self.g["ziyaret_birikim"] += 1
        j.state = "ZIYARET"
        self.INPOOL[j.id] = False
        if j.gorev is not None:
            j.gorev.iptal = True
            j.gorev = None
        if j.pencere is not None and ta > j.pencere[1]:
            self.g["gec_varis"] += 1
        if not self.kapida_basari(j, ta):
            j.bosa += 1
            tkn.bosa += 1
            self.g["bosa"] += 1
            tkn.free = ta + P["kapida_bekle_dk"]
            j.pencere = None
            j.teyit = "habersiz"
            j.state = "BEKLE"
            self.st.evde_yok(j, tkn, tkn.free)
            return
        d = j.doga
        if d == "tel":
            dur = P["sure_duzelmis"] if (j.tel_kendi and ta >= j.tau) else P["sure_tel"]
            self.kapat(j, ta + dur, "saha_hafif")
        elif d == "sebeke":
            dur = P["sure_sebeke"] if ta < j.tau else P["sure_duzelmis"]
            self.kapat(j, ta + dur, "saha_sebeke")
            self.st.sebeke_bulundu(j, ta + dur)
        elif d == "iptal":
            dur = P["sure_iptal"]
            self.kapat(j, ta + dur, "iptal")
        elif d == "altyapi":
            dur = P["sure_altyapi"]
            self.altyapi_bilet(j, ta + dur)
        elif d == "iade_musteri":
            dur = TIP["CIHAZ_IADE"][4]
            self.kapat(j, ta + dur, "saha")
        else:
            dur = j.sure
            if not j.ftf_ok and j.ziyaret == 1:
                self.g["ikinci_ziyaret"] += 1
                j.state = "BEKLE"
                self.randevu_ver(j, ta + dur, lead=12 * 60)
            else:
                self.kapat(j, ta + dur, "saha")
        tkn.free = ta + dur

    def tek_isle(self, tkn, t_son):
        guard = 0
        while tkn.aktif and tkn.free < t_son and guard < 50:
            guard += 1
            t = tkn.free
            if t >= tkn.bit - 15:
                tkn.aktif = False
                break
            if not tkn.mola_ok and t >= tkn.mola:
                tkn.mola_ok = True
                tkn.free += self.P["mola_dk"]
                continue
            j = self.st.sec(tkn, t)
            if j is None:
                bekle = self.st.bos_bekle(tkn, tkn.free)
                tkn.bos_dk += bekle
                tkn.free += bekle
                continue
            self.git(tkn, j)

    # ---------------------------------------------------------- masa (operasyon arama havuzu)
    def masa_kisi(self, t):
        v = self.st.masa_kisi(t)
        if v is not None:
            return v
        P = self.P
        m = dk(t)
        if dow(t) == 6:
            return P["O_pazar"] if 540 <= m < 1080 else 0
        if P["masa_acilis"] <= m < P["masa_aksam_bas"]:
            return P["O"]
        if P["masa_aksam_bas"] <= m < P["masa_kapanis"]:
            return P["O_aksam"]
        return 0

    def masa_isle(self, t):
        k = self.masa_kisi(t)
        if k <= 0:
            return
        self.g["ops_kapasite_dk"] += k * 5
        self.masa_kap += k * 5 * self.P["verim"]
        if self.masa_kap <= 0:
            return
        eski = self.masa
        self.masa = []
        hazir, kalan = [], []
        for g in eski:
            if g.iptal or g.j.gorev is not g or g.j.state == "KAPALI":
                continue
            (hazir if g.hazir <= t else kalan).append(g)
        if self.st.son_var:
            h2 = []
            for g in hazir:
                if g.son is not None and g.son < t:
                    g.iptal = True
                    g.j.gorev = None
                    self.st.masa_son(g, t)
                else:
                    h2.append(g)
            hazir = h2
        hazir.sort(key=lambda g: self.st.masa_oncelik(g, t))
        i = 0
        while i < len(hazir) and self.masa_kap > 0:
            g = hazir[i]
            i += 1
            if g.iptal or g.j.gorev is not g or g.j.state == "KAPALI":
                continue
            dur = self._masa_islem(g, t)
            self.masa_kap -= dur
            self.g["ops_dk"] += dur
        for g in hazir[i:]:
            if not g.iptal:
                kalan.append(g)
        self.masa.extend(kalan)
        if self.masa_kap > 0:
            self.masa_kap = 0.0

    def _masa_islem(self, g, t):
        j = g.j
        S = self.P["masa_sure"]
        g.iptal = True
        j.gorev = None
        if g.amac in ("sistem", "noc"):
            self.st.masa_sonuc(g, "sistem", t)
            return S[g.amac]
        if g.amac == "geri_arama":
            ok = True
            self.g["geri_arama"] += 1
        else:
            ok = self.cevap(j, t)
            self.g["ops_cagri"] += 1
            j.cagri_ops += 1
        if not ok:
            self.st.masa_sonuc(g, "cevapsiz", t)
            return S["basarisiz"]
        r = self.st.masa_sonuc(g, "ulasildi", t)
        return r if r is not None else S.get(g.amac, 4.0)

    # ---------------------------------------------------------- ana döngü
    def senkron_mu(self, t):
        m = dk(t)
        s = self.senkron
        if s == "anlik":
            return True
        if s == "30dk":
            return m % 30 == 0 and 480 <= m <= 1200
        if s == "3x":
            return m in (465, 735, 1005)
        return False

    def calis(self):
        t = float(REF_DK)
        self.gun_basla(0)
        bir = [j for j in self.isler if j.birikim]
        for j in bir:
            j.t_gor = t
        self.st.baslangic(t, bir)
        while t < self.H:
            d = gun(t)
            if d != self.gun_no:
                self.gun_bitir()
                self.gun_basla(d)
            while self.zam and self.zam[0][0] <= t:
                tt, _, fn, args = heapq.heappop(self.zam)
                fn(tt, *args)
            if self.senkron_mu(t):
                while self.gelecek and self.gelecek[0][0] <= t:
                    _, i = heapq.heappop(self.gelecek)
                    j = self.isler[i]
                    j.t_gor = t
                    j.state = "YENI"
                    if j.btk and j.konumlu:
                        self.son_btk.append((t, j))
                    self.st.gelen(j, t)
            self.st.tik(t)
            self.masa_isle(t)
            for tkn in self.teknisyenler:
                if tkn.aktif and tkn.free < t + 5 and tkn.bas < t + 5:
                    if tkn.free < t:
                        tkn.free = t if tkn.free < tkn.bas else tkn.free
                    self.tek_isle(tkn, t + 5)
            t += 5
        self.gun_bitir()
        return self


# ================================================================== STRATEJİLER
def aksam_bandi(t, bas=1050, bit=1170):
    """Aynı gün 17:30-19:30 bandındaki en yakın an; geçtiyse ertesi gün 08:30."""
    m = dk(t)
    if m < bas:
        return gun(t) * GUN + bas
    if m < bit:
        return t
    return (gun(t) + 1) * GUN + 510


def sabah(t, saat=510):
    m = dk(t)
    if m < saat:
        return gun(t) * GUN + saat
    return (gun(t) + 1) * GUN + saat


def is_gunu_sonra(t, n, saat=510):
    d = gun(t)
    k = 0
    while k < n:
        d += 1
        if dow_gun(d) != 6:
            k += 1
    return d * GUN + saat


def mesaiye(t):
    """Masa kapalıysa bir sonraki açılışa (08:30) ötele."""
    m = dk(t)
    if m < 510:
        return gun(t) * GUN + 510
    if m >= 1230:
        return (gun(t) + 1) * GUN + 510
    return t


class Strateji:
    ad = ""
    kod = ""
    senkron = "30dk"
    aksam_oran = 0.0
    gecikme = 0
    pazar_sadece_btk = False
    son_var = False
    randevu_pay = 0.7
    pencere_bekle = True

    def __init__(self, m):
        self.m = m
        self.P = m.P

    def vardiya(self, n, dw):
        na = int(round(n * self.aksam_oran))
        if n <= 2:
            na = 0
        return n - na, na

    def masa_kisi(self, t):
        return None

    def gun_basla(self, d):
        pass

    def tik(self, t):
        pass

    def bos_bekle(self, tkn, t):
        return 10.0

    def masa_oncelik(self, g, t):
        return (g.oncelik, g.hazir, g.seq)

    def masa_son(self, g, t):
        pass

    def uyan(self, j, t):
        self.m.havuza(j, "habersiz")

    def kacan_randevu(self, j, t):
        j.pencere = None
        j.teyit = "habersiz"

    def sebeke_bulundu(self, j, t):
        pass

    # ---- ortak masa kalıpları ----
    def iade_gir(self, j, t):
        """Cihaz İade: sistem kaydı kontrolü (arama yok) -> kapanır ya da müşteri araması."""
        self.m.masa_ekle(j, "sistem", t, oncelik=1, meta="iade")

    def iade_sonuc(self, j, sonuc, t):
        m = self.m
        if sonuc == "sistem":
            if j.doga == "iade_sistem":
                m.kapat(j, t, "sistem")
            else:
                j.lane = "iade"
                m.masa_ekle(j, "iade", t, oncelik=6)
            return True
        return False

    def iade_ulasildi(self, j, t):
        m = self.m
        if j.U[45] < self.P["iade_getirir"]:
            m.beklet(j, t + 60 * (4 + 44 * j.U[46]), self._iade_getirdi)
        else:
            m.randevu_ver(j, t, lead=120)

    def _iade_getirdi(self, j, t):
        self.m.kapat(j, t, "lojistik")

    def masa_ulasildi_kanal(self, j, t):
        m = self.m
        if j.doga == "kanal_tv":
            j.doga = "saha"
            j.btk = True
            m.randevu_ver(j, t, lead=90)
        else:
            m.kapat(j, t, "tel_masa")


# ------------------------------------------------------------------ BUGÜN (kalibrasyon referansı)
class Bugun(Strateji):
    """Bugünkü süreç (kalibrasyon referansı). Ofis her yeni saha işini bir kez arar ('BOSS üzerinden arama
    sağlandı'); ulaşırsa 'düzeldi' kontrolü, değilse 2 saatlik dilim yazar. Ulaşılamayan iş notla bekler ve
    ofis ertesi gün bir kez daha arar (7 günde kapatılır). Teknisyen yalnız dilimli işlere gider (bugünün
    dilimleri önce), ~09:15 başlar. Kanal Şikayeti ~1 hafta askıda bekleyip ofisten kapanır."""
    ad = "BUGÜN (mevcut süreç, referans)"
    kod = "BUGUN"
    senkron = "anlik"
    gecikme = 45
    randevu_pay = 0.8
    pencere_bekle = False

    def masa_kisi(self, t):
        m = dk(t)
        if dow(t) == 6:
            return 0
        return 2 if 540 <= m < 1080 else 0      # 'ofis kullanıcısı'

    def _lognormal(self, j, med_saat, sig, k=47):
        return 60 * med_saat * math.exp(sig * (j.U[k] * 2 - 1) * 1.7)

    def gelen(self, j, t):
        m = self.m
        if j.tip == "KANAL_SIKAYETI":
            m.beklet(j, t + self._lognormal(j, 150, 0.6), self._ofis_kapat)
        elif j.tip == "SORU_CEVAP":
            m.beklet(j, t + self._lognormal(j, 3, 1.0), self._ofis_kapat)
        elif j.tip == "CIHAZ_IADE":
            if j.doga == "iade_sistem":
                m.beklet(j, t + 120 * j.U[46], self._sistem_kapat)
            else:
                m.beklet(j, t + self._lognormal(j, 200, 0.5), self._lojistik_kapat)
        else:
            m.masa_ekle(j, "ilk", t, oncelik=5)

    def _ofis_kapat(self, j, t):
        self.m.kapat(j, t, "tel_masa")

    def _sistem_kapat(self, j, t):
        self.m.kapat(j, t, "sistem")

    def _lojistik_kapat(self, j, t):
        self.m.kapat(j, t, "lojistik")

    def baslangic(self, t, birikim):
        m = self.m
        for j in birikim:
            if j.tip == "KANAL_SIKAYETI":
                kalan = max(60.0, j.t0 + self._lognormal(j, 150, 0.6) - t)
                m.beklet(j, t + kalan, self._ofis_kapat)
            elif j.bas_durum == "Askıya alındı" or j.notlu:
                m.masa_ekle(j, "ilk", sabah(t, 540) + 480 * j.U[46], oncelik=6)
            elif j.ws0 is not None and j.ws0 > t:
                m.havuza(j, "randevu", (j.ws0, j.ws0 + 120))
            else:
                m.masa_ekle(j, "ilk", sabah(t, 540), oncelik=6)

    def masa_oncelik(self, g, t):
        return (g.oncelik, g.hazir, g.seq)

    def masa_sonuc(self, g, sonuc, t):
        j = g.j
        m = self.m
        if sonuc == "ulasildi":
            r = m.cozum(j, t, "kontrol")
            if r in ("cozuldu", "iptal"):
                m.kapat(j, t, "tel_masa" if r == "cozuldu" else "iptal")
            else:
                m.randevu_ver(j, t, lead=120)
            return 3.0
        j.notlu = True
        j.deneme += 1
        if j.deneme >= 7:
            m.kapat(j, t, "ulasilamadi")
        else:
            m.masa_ekle(j, "ilk", sabah(t, 540) + 300 * j.U[(30 + j.deneme) % 48], oncelik=6)
        return None

    def _sec1(self, tkn, t, pool, d):
        m = self.m
        j = m.pencere_sec(tkn, t, pool, d, tol=60, min_ws=gun(t) * GUN)
        if j is None:
            idx = [i for i, x in enumerate(pool) if x.pencere is not None and x.pencere[0] < (gun(t) + 1) * GUN]
            if not idx:
                return None
            j = pool[min(idx, key=lambda i: (pool[i].pencere[0], d[i]))]
        return j

    def sec(self, tkn, t):
        return self.m.sec_katman(tkn, t, lambda pool, d: self._sec1(tkn, t, pool, d))

    def evde_yok(self, j, tkn, t):
        j.notlu = True
        self.m.masa_ekle(j, "ilk", sabah(t, 540), oncelik=6)

    def kacan_randevu(self, j, t):
        pass   # bugünkü süreçte dilimi geçmiş iş olduğu gibi kalır, teknisyen fırsat buldukça gider


# ------------------------------------------------------------------ HAM (kullanıcının ham fikri)
class Ham(Strateji):
    ad = "HAM: doğrudan sevk, ulaşılamayanı ara (kullanıcının ilk fikri)"
    kod = "HAM"

    def gelen(self, j, t):
        m = self.m
        if j.kanal == "MASA":
            j.lane = "masa"
            j.deneme = 0
            m.masa_ekle(j, "kanal", t, oncelik=4)
        elif j.kanal == "LOJ":
            self.iade_gir(j, t)
        else:
            m.havuza(j, "habersiz")

    def baslangic(self, t, birikim):
        for j in birikim:
            self.gelen(j, t)

    def _sonraki(self, j, t):
        """Merdiven: hemen, +2 s, ertesi gün 10:00 -> SMS + 48 s askı -> son deneme -> kapat."""
        m = self.m
        j.deneme += 1
        k = j.deneme
        if k == 1:
            m.masa_ekle(j, j.lane if j.lane != "iade" else "iade", t + 120, oncelik=4)
        elif k == 2:
            m.masa_ekle(j, j.lane, sabah(t, 600), oncelik=4)
        elif k == 3:
            m.sms(j, t)
            m.beklet(j, t + 2 * GUN, self._son_deneme)
        else:
            m.kapat(j, t, "ulasilamadi")

    def _son_deneme(self, j, t):
        self.m.masa_ekle(j, j.lane, mesaiye(t), oncelik=4)

    def masa_sonuc(self, g, sonuc, t):
        j = g.j
        m = self.m
        if g.meta == "iade" and self.iade_sonuc(j, sonuc, t):
            return None
        if sonuc == "cevapsiz":
            if j.lane is None:
                j.lane = "istisna"
            self._sonraki(j, t)
            return None
        if j.kanal == "MASA":
            self.masa_ulasildi_kanal(j, t)
            return 4.0
        if j.tip == "CIHAZ_IADE" and j.doga != "saha":
            self.iade_ulasildi(j, t)
            return 3.0
        if j.btk:
            r = m.cozum(j, t, "kontrol")
            if r == "cozuldu":
                m.kapat(j, t, "tel_masa")
                return 4.0
        if j.doga == "iptal":
            m.kapat(j, t, "iptal")
            return 3.0
        m.randevu_ver(j, t, lead=120)
        return 4.0

    def _sec1(self, tkn, t, pool, d):
        m = self.m
        j = m.pencere_sec(tkn, t, pool, d)
        if j is not None:
            return j
        habersiz = [i for i, x in enumerate(pool) if x.pencere is None]
        if not habersiz:
            return None
        order = sorted(habersiz, key=lambda i: (not pool[i].btk, pool[i].t0))[:5]
        return pool[min(order, key=lambda i: d[i])]

    def sec(self, tkn, t):
        return self.m.sec_katman(tkn, t, lambda pool, d: self._sec1(tkn, t, pool, d))

    def evde_yok(self, j, tkn, t):
        j.lane = "istisna"
        j.deneme = 0
        self.m.masa_ekle(j, "istisna", t, oncelik=3)


# ------------------------------------------------------------------ DSİR
class Dsir(Strateji):
    ad = "DSİR: Doğrudan Sevk + İstisna Randevu"
    kod = "DSIR"
    aksam_oran = 0.10
    pazar_sadece_btk = True
    randevu_pay = 0.6

    def __init__(self, m):
        super().__init__(m)
        self.kumeler = []   # dict(merkez, isler, nobetci, durum)

    # -- K1 giriş
    def gelen(self, j, t):
        m = self.m
        if j.btk and j.tekrar7:
            j.kidemli = True
        if j.doga == "altyapi" and j.altyapi_bilinen:
            m.altyapi_bilet(j, t)
            return
        if j.kanal == "MASA":
            j.lane = "masa"
            m.masa_ekle(j, "kanal", t, oncelik=3)
            return
        if j.kanal == "LOJ":
            self.iade_gir(j, t)
            return
        if j.btk and j.konumlu and self._kume_kontrol(j, t):
            return
        m.havuza(j, "habersiz")

    def _kume_kontrol(self, j, t):
        """K1c: aynı lokasyonda 6 s'te >=3 ya da 300 m'de 3 s'te >=5 BTK -> yalnız en eski nöbetçi gider."""
        m = self.m
        for k in self.kumeler:
            if k["durum"] == "acik" and math.hypot(k["x"] - j.px, k["y"] - j.py) <= 0.3:
                k["isler"].append(j)
                m.beklet(j, t + 180, self._kume_birak)
                return True
        ayni, yakin = [], []
        for x in m.havuz_yakin(j.px, j.py, 0.3):
            if not x.btk or not x.konumlu or x.birikim or x.t_gor is None:
                continue
            dd = math.hypot(x.px - j.px, x.py - j.py)
            if dd < 0.01 and t - x.t_gor <= 360:
                ayni.append(x)
            if dd <= 0.3 and t - x.t_gor <= 180:
                yakin.append(x)
        if len(ayni) + 1 >= 3 or len(yakin) + 1 >= 5:
            grup = (ayni if len(ayni) + 1 >= 3 else yakin) + [j]
            grup.sort(key=lambda x: x.t0)
            nob = grup[0]
            k = dict(x=j.px, y=j.py, isler=[], nobetci=nob, durum="acik", t=t)
            nob.kume = k
            self.kumeler.append(k)
            m.g["kume_alarm"] += 1
            for x in grup[1:]:
                k["isler"].append(x)
                x.kume = k
                m.beklet(x, t + 180, self._kume_birak)
            if nob is not j:
                return True
            m.havuza(j, "habersiz")
            return True
        return False

    def _kume_birak(self, j, t):
        k = j.kume
        if k is not None and k["durum"] == "acik":
            pass
        self.m.havuza(j, "habersiz")

    def sebeke_bulundu(self, j, t):
        k = j.kume
        if k is None or k.get("nobetci") is not j or k["durum"] != "acik":
            return
        k["durum"] = "sebeke"
        m = self.m
        m.g["kume_sebeke"] += 1
        for x in k["isler"]:
            if x.state == "KAPALI":
                continue
            # kullanıcı tek OneDesk ticket'ı açar; bekleyenler çözümde toplu kapatılır
            cozum = max(t, j.tau)
            m.beklet(x, cozum, self._toplu_kapat)

    def _toplu_kapat(self, x, t):
        m = self.m
        m.kapat(x, t, "sebeke_toplu")
        if x.doga != "sebeke":
            m.tekrar_uret(x, t + 60 * (2 + 22 * x.U[47]), doga=x.doga if x.doga != "tel" else "saha")

    def baslangic(self, t, birikim):
        m = self.m
        for j in birikim:
            if j.btk and j.tekrar7:
                j.kidemli = True
            if j.kanal == "MASA":
                j.lane = "masa"
                m.masa_ekle(j, "kanal", t, oncelik=6)
            elif j.kanal == "LOJ":
                self.iade_gir(j, t)
            elif j.notlu or j.bas_durum == "Askıya alındı":
                j.lane = "istisna"
                m.masa_ekle(j, "istisna", mesaiye(t), oncelik=6)
            else:
                m.havuza(j, "habersiz")

    # -- masa
    def masa_oncelik(self, g, t):
        j = g.j
        yeni = 0 if (t - j.t0) < GUN else 1
        if g.amac == "geri_arama":
            return (0, 0, j.hedef)
        if g.amac == "istisna":
            return (1 if j.btk else 2 + yeni, yeni, j.hedef)
        return (3 + yeni, yeni, j.hedef)

    def _istisna_sonraki(self, j, t):
        """K4: D1 <=60 dk, D2 +60, D3 17:30-19:30, D4 ertesi 08:30, D5 (BTK) ertesi akşam; BTK dışı D3 sonrası 2 iş günü askı."""
        m = self.m
        j.deneme += 1
        k = j.deneme
        if k == 1:
            m.masa_ekle(j, "istisna", t + 60, oncelik=2)
        elif k == 2:
            m.masa_ekle(j, "istisna", aksam_bandi(t), oncelik=2)
        elif k == 3:
            m.sms(j, t)
            if j.btk:
                m.masa_ekle(j, "istisna", sabah(t), oncelik=2)
            else:
                m.beklet(j, is_gunu_sonra(t, 2), self._aski_uyan)
        elif k == 4:
            if j.btk:
                m.masa_ekle(j, "istisna", aksam_bandi(t + 8 * 60), oncelik=2)
            else:
                m.masa_ekle(j, "istisna", t + 120, oncelik=2)
        else:
            m.kapat(j, t, "ulasilamadi")

    def _aski_uyan(self, j, t):
        self.m.masa_ekle(j, j.lane or "istisna", mesaiye(t), oncelik=2)

    def masa_sonuc(self, g, sonuc, t):
        j = g.j
        m = self.m
        if g.meta == "iade" and self.iade_sonuc(j, sonuc, t):
            return None
        if sonuc == "cevapsiz":
            if j.lane is None:
                j.lane = "istisna"
            self._istisna_sonraki(j, t)
            return None
        if j.kanal == "MASA":
            self.masa_ulasildi_kanal(j, t)
            return 4.0
        if j.tip == "CIHAZ_IADE" and j.doga != "saha":
            self.iade_ulasildi(j, t)
            return 3.0
        if j.doga == "iptal":
            m.kapat(j, t, "iptal")
            return 3.0
        if j.btk and not j.kidemli:
            r = m.cozum(j, t, "kontrol")
            if r == "cozuldu":
                m.kapat(j, t, "tel_masa")
                return 4.0
        # K4b: gerçek ETA'lı 2 s dilim: aynı gün >=3 s, akşamcıya akşam, yoksa ertesi gün
        m.randevu_ver(j, t, lead=180)
        return 4.0

    # -- K2 atama / K3 temas
    def sec(self, tkn, t):
        m = self.m
        pazar = dow(t) == 6
        atla = set()
        for _ in range(6):
            t = tkn.free
            if pazar:
                filtre = lambda x: (x.btk or x.pencere is not None) and x.id not in atla
            else:
                filtre = (lambda x: x.id not in atla) if atla else None
            j = m.sec_katman(tkn, t, lambda pool, d: self._oncelik(tkn, t, pool, d), filtre)
            if j is None:
                return None
            if j.pencere is not None:
                # K4c: randevulu işte 30 dk önce teyit araması
                ok = m.tek_ara(tkn, j)
                if ok and not m.simdi_musait(j, tkn.free) and j.pencere[0] - tkn.free < 60:
                    pass
                return j
            # K3: sıradaki müşteri aranır (son 10 dk içinde, ek 1,5 dk)
            ok = m.tek_ara(tkn, j)
            if ok:
                if j.btk and not j.kidemli:
                    r = m.cozum(j, tkn.free, "kontrol")
                    if r == "cozuldu":
                        m.kapat(j, tkn.free, "tel_tek")
                        continue
                if j.doga == "iptal":
                    m.kapat(j, tkn.free, "iptal")
                    continue
                if m.simdi_musait(j, tkn.free):
                    j.teyit = "teyitli"
                    return j
                # (c) şimdi değil: teknisyen kendi boş diliminden randevu yazar
                m.randevu_ver(j, tkn.free, lead=180)
                continue
            j.tek_deneme += 1
            if j.tek_deneme == 1:
                j.uygun = tkn.free + 10
                atla.add(j.id)
                continue
            # K3a: iki aramada ulaşılamadı
            if j.btk and math.hypot(tkn.x - j.x, tkn.y - j.y) <= 0.15:
                m.g["kapi_calma"] += 1
                return j
            m.sms(j, tkn.free)
            j.lane = "istisna"
            j.deneme = 0
            m.masa_ekle(j, "istisna", tkn.free, oncelik=2)
            m.g["istisna_kuyrugu"] += 1
        return None

    def _oncelik(self, tkn, t, pool, d):
        m = self.m
        j = m.pencere_sec(tkn, t, pool, d)
        if j is not None:
            return j
        tr = m.yol_dk_vec(d)
        idx = [i for i, x in enumerate(pool) if x.pencere is None]
        if not idx:
            return None
        tkn.sayac += 1
        if tkn.sayac % 3 == 0:
            eski = [i for i in idx if pool[i].btk and t - pool[i].t0 >= GUN]
            if eski:
                return pool[min(eski, key=lambda i: pool[i].t0)]
        yeni = [i for i in idx if t - pool[i].t0 < GUN]
        if yeni:
            yeni.sort(key=lambda i: (pool[i].hedef, not pool[i].btk))
            acil = [i for i in yeni if pool[i].hedef - t - tr[i] - 35 < 120]
            if acil:
                return pool[min(acil, key=lambda i: pool[i].hedef + tr[i])]
            ilk5 = yeni[:5]
            return pool[min(ilk5, key=lambda i: d[i])]
        eski = sorted(idx, key=lambda i: pool[i].t0)[:5]
        return pool[min(eski, key=lambda i: d[i])]

    def evde_yok(self, j, tkn, t):
        m = self.m
        j.lane = "istisna"
        j.deneme = max(j.deneme, 0)
        j.atla += 1
        if j.atla >= 2 and not j.btk:
            m.beklet(j, is_gunu_sonra(t, 2), self._aski_uyan)
            return
        m.masa_ekle(j, "istisna", t, oncelik=2)

    def kacan_randevu(self, j, t):
        j.lane = "istisna"
        self.m.masa_ekle(j, "istisna", mesaiye(t), oncelik=2)


# ------------------------------------------------------------------ RPHT
class Rpht(Strateji):
    ad = "RPHT: Risk Puanlı Hibrit Triyaj"
    kod = "RPHT"
    son_var = True
    randevu_pay = 0.7

    def gelen(self, j, t):
        m = self.m
        if j.doga == "altyapi" and j.altyapi_bilinen:
            m.altyapi_bilet(j, t)
            return
        if j.kanal == "MASA":
            j.lane = "kanal"
            m.masa_ekle(j, "kanal", t, oncelik=5)
            return
        if j.kanal == "LOJ":
            self.iade_gir(j, t)
            return
        kotu = j.gecmis_bilinen and j.sinif == 2
        if j.btk:
            if j.konumlu and self._toplu(j, t):
                return
            if kotu:
                m.havuza(j, "habersiz")
                m.g["dogrudan"] += 1
                return
            j.lane = "uzak"
            m.masa_ekle(j, "teshis", t, son=t + 30, oncelik=1)
            return
        # BTK dışı saha: Vb > 12,5 dk (komşu > 0,3 km, konumsuz) -> teyit; yoksa doğrudan
        if kotu:
            m.havuza(j, "habersiz")
            return
        yakin = bool(j.konumlu and m.havuz_yakin(j.px, j.py, 0.3))
        if yakin:
            m.havuza(j, "habersiz")
            m.g["dogrudan"] += 1
        else:
            j.lane = "teyit"
            m.masa_ekle(j, "teyit", t, son=t + 120, oncelik=4)

    def _toplu(self, j, t):
        """R6a/R13: 300 m'de 6 s'te >=4 diğer BTK ya da aynı binada >=3 açık BTK -> küme bekletme + NW kontrolü."""
        m = self.m
        burst, ayni = [], []
        for x in m.son_btk_yakin(j, t, 360):
            burst.append(x)
            if math.hypot(x.px - j.px, x.py - j.py) < 0.01 and x.state != "KAPALI":
                ayni.append(x)
        if len(burst) >= 4 or len(ayni) + 1 >= 3:
            m.g["kume_alarm"] += 1
            bekle = 60 if j.tip == "TV_ARIZA" else 90
            j.lane = "toplu"
            m.masa_ekle(j, "noc", t, oncelik=0, meta=bekle)
            return True
        return False

    def baslangic(self, t, birikim):
        m = self.m
        for j in birikim:
            j.lane = "tarama"
            if j.kanal == "MASA":
                j.lane = "kanal"
                m.masa_ekle(j, "kanal", mesaiye(t), oncelik=7)
            elif j.kanal == "LOJ":
                self.iade_gir(j, t)
            else:
                m.masa_ekle(j, "tarama", mesaiye(t), oncelik=8)

    def masa_oncelik(self, g, t):
        j = g.j
        o = g.oncelik
        if g.amac == "geri_arama":
            o = 0
        # bant sırası: BTK/TV > bağlantı > E1 > teyit > kanal > birikim
        tvb = 0 if j.tip == "TV_ARIZA" else 1
        return (o, tvb, j.hedef)

    def masa_son(self, g, t):
        """Son arama anı kaçtı -> doğrudan sevk (kuyruk teknisyeni bekletmez); Kanal bir sonraki tike."""
        j = g.j
        m = self.m
        if g.amac in ("teshis", "teyit"):
            m.havuza(j, "habersiz")
            m.g["son_an_kacti"] += 1
        else:
            m.masa_ekle(j, g.amac, t, oncelik=g.oncelik)

    def masa_sonuc(self, g, sonuc, t):
        j = g.j
        m = self.m
        if g.meta == "iade" and self.iade_sonuc(j, sonuc, t):
            return None
        if g.amac == "noc":
            return self._noc(j, t, g.meta)
        if sonuc == "cevapsiz":
            return self._cevapsiz(g, j, t)
        if j.kanal == "MASA":
            self.masa_ulasildi_kanal(j, t)
            return 4.0
        if j.tip == "CIHAZ_IADE" and j.doga != "saha":
            self.iade_ulasildi(j, t)
            return 3.0
        if j.doga == "iptal":
            m.kapat(j, t, "iptal")
            return 3.0
        if j.btk:
            r = m.cozum(j, t, "teshis")
            if r == "cozuldu":
                m.kapat(j, t, "tel_masa")
                return 10.0
            if r == "sebeke":
                m.beklet(j, max(j.tau, t + 30), self._sebeke_dogrula)
                return 10.0
            m.randevu_ver(j, t, lead=60)
            return 10.0
        m.randevu_ver(j, t, lead=90)
        return 4.0

    def _sebeke_dogrula(self, j, t):
        self.m.masa_ekle(j, "dogrulama", mesaiye(t), oncelik=2, meta="dogrula")

    def _noc(self, j, t, bekle):
        """Altyapı masası NW kontrolü: şebeke arızası sürüyorsa küme bekletilir, yoksa UZAK-ÖNCE."""
        m = self.m
        if j.doga == "sebeke" and t < j.tau and j.U[25] < 0.8:
            m.beklet(j, j.tau, self._sebeke_dogrula)
            m.g["kume_sebeke"] += 1
        else:
            j.lane = "uzak"
            m.masa_ekle(j, "teshis", t, son=t + 30 + bekle, oncelik=1)
        return None

    def _cevapsiz(self, g, j, t):
        m = self.m
        if g.meta == "dogrula":
            m.kapat(j, t, "sebeke_toplu")
            return None
        j.deneme += 1
        k = j.deneme
        if g.amac in ("teshis",):
            m.havuza(j, "habersiz")
            m.g["dogrudan"] += 1
            if k == 1:
                m.masa_ekle(j, "teshis", t + 60, oncelik=2, durum=False)
            return None
        if g.amac == "tarama":
            m.havuza(j, "habersiz")
            j.dolgu = True
            return None
        if g.amac == "kanal":
            if k == 1:
                m.masa_ekle(j, "kanal", t + 180, oncelik=5)
            elif k == 2:
                m.masa_ekle(j, "kanal", max(t, gun(t) * GUN + 1020) if dk(t) < 1230 - 30 else sabah(t), oncelik=5)
            elif k == 3:
                m.sms(j, t)
                m.masa_ekle(j, "kanal", sabah(t, 600), oncelik=5)
            else:
                m.kapat(j, t, "ulasilamadi")
            return None
        # teyit / E1
        if k == 1:
            if j.konumlu and m.havuz_yakin(j.px, j.py, 0.5):
                m.havuza(j, "habersiz")
                m.g["kosullu_sevk"] += 1
                return None
            m.masa_ekle(j, g.amac, t + 120, oncelik=4)
        elif k == 2:
            m.masa_ekle(j, g.amac, max(t + 60, gun(t) * GUN + 1020) if dk(t) < 1200 else sabah(t), oncelik=4)
        elif k == 3:
            m.sms(j, t)
            m.beklet(j, t + (24 if j.btk else 48) * 60, self._uyanis)
        else:
            m.kapat(j, t, "ulasilamadi")
        return None

    def _uyanis(self, j, t):
        self.m.masa_ekle(j, "teyit", mesaiye(t), oncelik=4)

    def sec(self, tkn, t):
        m = self.m
        for _ in range(4):
            t = tkn.free
            j = m.sec_katman(tkn, t, lambda pool, d: self._sec1(tkn, t, pool, d))
            if j is None:
                return None
            if j.pencere is not None:
                return j
            # habersiz iş: 'yoldayım' araması (varıştan ~30 dk önce, tek deneme)
            ok = m.tek_ara(tkn, j)
            if ok:
                if j.btk and j.lane != "uzak_ok":
                    r = m.cozum(j, tkn.free, "kontrol")
                    if r == "cozuldu":
                        m.kapat(j, tkn.free, "tel_tek")
                        continue
                if j.doga == "iptal":
                    m.kapat(j, tkn.free, "iptal")
                    continue
                if not m.simdi_musait(j, tkn.free):
                    m.randevu_ver(j, tkn.free, lead=120)
                    continue
                j.teyit = "teyitli"
            return j
        return None

    def _sec1(self, tkn, t, pool, d):
        m = self.m
        j = m.pencere_sec(tkn, t, pool, d)
        if j is not None:
            return j
        tr = m.yol_dk_vec(d)
        best, bk = None, None
        for i, x in enumerate(pool):
            if x.pencere is not None:
                continue
            slack = (x.hedef - t) / 60.0
            k = slack - 4 * x.btk - 2 * (x.tip == "TV_ARIZA") - 1 * x.tekrar7 + tr[i] / 30.0
            if x.birikim or t - x.t0 >= GUN:
                k += 12.0 if (t - x.t0) < 7 * GUN else 0.0
            if bk is None or k < bk:
                best, bk = x, k
        return best

    def evde_yok(self, j, tkn, t):
        j.lane = "E1"
        j.deneme = 0
        self.m.masa_ekle(j, "istisna", t + 30, oncelik=3)

    def kacan_randevu(self, j, t):
        j.lane = "E1"
        self.m.masa_ekle(j, "istisna", mesaiye(t), oncelik=3)


# ------------------------------------------------------------------ BÖLGE DALGALARI
SLOT_G = [(510, 630), (630, 750), (780, 900), (900, 1020), (1020, 1110)]     # gündüz S1-S5
SLOT_A = [(780, 900), (900, 1020), (1020, 1140), (1140, 1260)]              # akşam yüzeni E3-E6


class Bolge(Strateji):
    ad = "BÖLGE DALGA: sabit bölge takvimi + aramasız SMS dilimi"
    kod = "BOLGE"
    aksam_oran = 0.10
    randevu_pay = 0.7
    BIRIM = 40.0
    one_cek = False           # boşta kalan teknisyen sonraki dilimin işini öne çekebilir mi (tasarımda yok)
    atla_km = 1.0             # K10(d): cevapsızda gidilecek en çok mesafe

    def __init__(self, m):
        super().__init__(m)
        self.kap = defaultdict(float)   # (d, sahip, slot) -> kullanılan birim
        self.slot_is = defaultdict(list)   # sahip -> dilime yazılmış işler (tembel temizlik)
        self.rez = {}                      # iş -> (dilim, ayrılan birim): yeniden yazımda serbest bırakılır

    def _birak(self, j):
        r = self.rez.pop(j.id, None)
        if r is not None:
            self.kap[r[0]] = max(0.0, self.kap[r[0]] - r[1])

    def _slotlar(self, d):
        """Gün d için (sahip, slot_idx, bas, bit, kapasite_birim, aksam_mi)."""
        ng, na = self.m.kadro(d)
        out = []
        for z in range(ng):
            for s, (a, b) in enumerate(SLOT_G):
                out.append((("G", z), s, d * GUN + a, d * GUN + b, (b - a) / self.BIRIM, False))
        for k in range(na):
            for s, (a, b) in enumerate(SLOT_A):
                cap = (b - a) / self.BIRIM
                if s == 1:
                    cap -= 30 / self.BIRIM
                out.append((("A", k), s, d * GUN + a, d * GUN + b, cap, True))
        return out

    def _sektor(self, zon, d):
        ng, na = self.m.kadro(d)
        if na == 0:
            return None
        return self.m.sektor_bul(zon, d)

    def _beklenen(self, j):
        if j.teyit == "teyitli":
            b = 0.97
        elif j.btk:
            b = 0.57
        else:
            b = 0.79
        if j.tip in ("EVRAK_SOSYAL", "EVRAK_TURKSAT", "CIHAZ_GERI_ALIM", "TURKSAT_CIHAZ_IADE", "CIHAZ_IADE"):
            b *= 0.5
        return b

    def rezerve(self, j, t, teyitli=False, aksam_tercih=False, son=None):
        """K7: G1 BTK hedef içi (rezerv), G2 24 s içi, G3 akşam, G4 komşu x1,25, G5 alarm."""
        m = self.m
        lead = 45 if j.btk else 60
        if son is None:
            son = j.t0 + GUN
        hedef = j.hedef if j.btk else son
        bir = self._beklenen(j) if not teyitli else 0.97
        d0 = gun(t)
        adaylar = []
        for d in range(d0, d0 + 3):
            ng, na = m.kadro(d)
            if ng == 0:
                continue
            zon = m.zon_bul(j, d)
            sek = self._sektor(zon, d)
            C = zon_merkez(m.V, ng)
            dz = np.hypot(C[:, 0] - C[zon, 0], C[:, 1] - C[zon, 1])
            komsu = [int(z) for z in np.argsort(dz)[1:5]]
            for sahip, s, a, b, cap, ak in self._slotlar(d):
                if a < t + lead:
                    continue
                if ak:
                    if sahip[1] != sek:
                        continue
                    carp = 1.0
                    sinif = 1
                elif sahip[1] == zon:
                    carp = 1.0
                    sinif = 0
                elif sahip[1] in komsu:
                    carp = 1.25
                    sinif = 2
                else:
                    continue
                if j.tercih == 1 and aksam_tercih and dow_gun(d) < 5 and a % GUN < 1020:
                    continue
                adaylar.append((a, sinif, sahip, s, b, cap, carp, d))
        adaylar.sort(key=lambda x: (x[0], x[1]))
        for gecis in ("G1", "G2", "G3", "G4"):
            for a, sinif, sahip, s, b, cap, carp, d in adaylar:
                if gecis in ("G1", "G2") and sinif != 0:
                    continue
                if gecis == "G3" and sinif > 1:
                    continue
                if gecis == "G1":
                    if not j.btk or b > hedef:
                        continue
                    lim = cap
                else:
                    if b > son:
                        continue
                    serbest = t >= a - 45
                    lim = cap if (j.btk or serbest) else cap - 1.0
                key = (d, sahip, s)
                if self.kap[key] + bir * carp <= lim + 1e-9:
                    self._birak(j)
                    self.kap[key] += bir * carp
                    self.rez[j.id] = (key, bir * carp)
                    return self._yaz(j, key, a, b, teyitli)
        # G5: kapasite alarmı -> kendi takviminde ilk boş dilim (bekleme listesi, SMS'te saat yok)
        m.g["kapasite_alarmi"] += 1
        for d in range(d0, d0 + 6):
            ng, na = m.kadro(d)
            if ng == 0:
                continue
            zon = m.zon_bul(j, d)
            for sahip, s, a, b, cap, ak in self._slotlar(d):
                if ak or sahip[1] != zon or a < t + lead:
                    continue
                key = (d, sahip, s)
                if self.kap[key] + bir <= cap + 1e-9:
                    self._birak(j)
                    self.kap[key] += bir
                    self.rez[j.id] = (key, bir)
                    return self._yaz(j, key, a, b, teyitli, alarm=True)
        d = d0 + 1
        ng, na = m.kadro(d)
        zon = m.zon_bul(j, d) if ng else 0
        return self._yaz(j, (d, ("G", zon), 0), d * GUN + 510, d * GUN + 630, teyitli, alarm=True)

    def _yaz(self, j, key, a, b, teyitli, alarm=False):
        m = self.m
        j.slot = key
        self.slot_is[key[1]].append(j)
        teyit = "teyitli" if teyitli else ("habersiz" if alarm else "sms")
        m.havuza(j, teyit, (a, b))
        if not teyitli and not alarm:
            m.g["sms"] += 1
        m.g["randevu"] += 1
        return a

    def gelen(self, j, t):
        m = self.m
        if j.doga == "altyapi" and j.altyapi_bilinen:
            m.altyapi_bilet(j, t)
            return
        if j.kanal == "MASA":
            j.lane = "masa"
            m.masa_ekle(j, "kanal", t, oncelik=4)
            return
        if j.kanal == "LOJ":
            self.iade_gir(j, t)
            return
        self.rezerve(j, t)

    def baslangic(self, t, birikim):
        m = self.m
        for j in birikim:
            if j.kanal == "MASA":
                j.lane = "masa"
                m.masa_ekle(j, "kanal", mesaiye(t), oncelik=6)
            elif j.kanal == "LOJ":
                self.iade_gir(j, t)
            else:
                j.dolgu = True
                m.havuza(j, "habersiz")
                m.masa_ekle(j, "tarama", mesaiye(t), oncelik=8, durum=False)

    def masa_oncelik(self, g, t):
        o = 0 if g.amac == "geri_arama" else g.oncelik
        return (o, g.j.hedef)

    def masa_sonuc(self, g, sonuc, t):
        j = g.j
        m = self.m
        if g.meta == "iade" and self.iade_sonuc(j, sonuc, t):
            return None
        if g.amac == "tarama":
            # kurtarma masası doğrulama çağrısı (K17)
            if sonuc == "ulasildi":
                if j.btk:
                    r = m.cozum(j, t, "kontrol")
                    if r == "cozuldu":
                        m.kapat(j, t, "tel_masa")
                        return 4.0
                if j.doga == "iptal":
                    m.kapat(j, t, "iptal")
                    return 3.0
                j.tarandi = True
            return None
        if sonuc == "cevapsiz":
            j.deneme += 1
            k = j.deneme
            if j.lane == "masa" or j.kanal == "MASA" or g.meta == "iade" or j.lane == "iade":
                if k <= 2:
                    m.masa_ekle(j, g.amac, t + 120, oncelik=4)
                elif k == 3:
                    m.masa_ekle(j, g.amac, sabah(t, 600), oncelik=4)
                else:
                    m.kapat(j, t, "ulasilamadi")
                return None
            # K11 istisna masası: +60, 17:30, ertesi 09:00 -> 48 s askı -> son çağrı -> kapat
            if k == 1:
                m.masa_ekle(j, "istisna", t + 60, oncelik=3)
            elif k == 2:
                m.masa_ekle(j, "istisna", aksam_bandi(t), oncelik=3)
            elif k == 3:
                m.masa_ekle(j, "istisna", sabah(t, 540), oncelik=3)
            elif k == 4:
                m.sms(j, t)
                m.beklet(j, t + 48 * 60, self._son_cagri)
            else:
                m.kapat(j, t, "ulasilamadi")
            return None
        if j.kanal == "MASA":
            self.masa_ulasildi_kanal(j, t)
            return 4.0
        if j.tip == "CIHAZ_IADE" and j.doga != "saha":
            if j.U[45] < self.P["iade_getirir"]:
                m.beklet(j, t + 60 * (4 + 44 * j.U[46]), self._iade_getirdi)
            else:
                self.rezerve(j, t, teyitli=True)
            return 3.0
        if j.btk:
            r = m.cozum(j, t, "kontrol")
            if r == "cozuldu":
                m.kapat(j, t, "tel_masa")
                return 4.0
        if j.doga == "iptal":
            m.kapat(j, t, "iptal")
            return 3.0
        self._teyitli_yaz(j, t)
        return 4.0

    def _teyitli_yaz(self, j, t):
        m = self.m
        if j.tercih == 2:
            j.erteledi = True
            tt = (gun(t) + j.sonra_gun) * GUN + 480
            self.rezerve(j, tt, teyitli=True, son=tt + 2 * GUN)
        else:
            self.rezerve(j, t, teyitli=True, aksam_tercih=True, son=max(j.t0 + GUN, t + 12 * 60) if j.tercih == 0 else t + 2 * GUN)

    def _son_cagri(self, j, t):
        self.m.masa_ekle(j, "istisna", mesaiye(t), oncelik=3)

    def _slot_now(self, tkn, t):
        m_ = dk(t)
        tab = SLOT_A if tkn.aksam else SLOT_G
        for s, (a, b) in enumerate(tab):
            if m_ < b:
                return s, a
        return len(tab) - 1, tab[-1][0]

    def sec(self, tkn, t):
        m = self.m
        d = gun(t)
        sahip = ("A", tkn.sektor) if tkn.aksam else ("G", tkn.zon)
        for _ in range(6):
            t = tkn.free
            s_now, a_now = self._slot_now(tkn, t)
            benim = []
            sonraki = []
            liste = self.slot_is[sahip]
            temiz = []
            for x in liste:
                if x.state == "KAPALI" or x.slot is None or x.slot[1] != sahip:
                    continue
                temiz.append(x)
                if x.state != "SAHA" or x.uygun > t:
                    continue
                xd, xs, xss = x.slot
                if xd < d or (xd == d and xss <= s_now and d * GUN + (SLOT_A if tkn.aksam else SLOT_G)[xss][0] <= t + 20):
                    benim.append(x)
                elif self.one_cek and xd == d and xss == s_now + 1:
                    sonraki.append(x)
            if len(temiz) < len(liste):
                self.slot_is[sahip] = list(dict.fromkeys(temiz))
            if not benim and sonraki:
                benim = sonraki
            if benim:
                benim.sort(key=lambda x: (x.slot[0], x.slot[2], not x.btk, math.hypot(x.px - tkn.x, x.py - tkn.y)))
                j = benim[0]
            else:
                # dolgu (K16): yalnız birikim, dilim başına en çok 6 deneme
                if tkn.dolgu_say[s_now] >= 6 or tkn.aksam and False:
                    return None
                cand = [x for x in m.havuz_yakin(tkn.x, tkn.y, 5.0) if x.dolgu and x.slot is None and x.uygun <= t
                        and (tkn.zon is None or m.zon(x) == tkn.zon or math.hypot(x.px - tkn.x, x.py - tkn.y) <= 2.0)]
                if not cand:
                    m.g["bolge_bos"] += 1
                    return None
                cand.sort(key=lambda x: (not x.tarandi, not x.btk, x.t0))
                j = min(cand[:6], key=lambda x: math.hypot(x.px - tkn.x, x.py - tkn.y))
                tkn.dolgu_say[s_now] += 1
            # K10 yola çıkış çağrısı
            ok = m.tek_ara(tkn, j)
            if ok:
                if j.btk:
                    r = m.cozum(j, tkn.free, "kontrol")
                    if r == "cozuldu":
                        m.kapat(j, tkn.free, "tel_tek")
                        continue
                if j.doga == "iptal":
                    m.kapat(j, tkn.free, "iptal")
                    continue
                if not m.simdi_musait(j, tkn.free):
                    j.slot = None
                    self._teyitli_yaz(j, tkn.free)
                    continue
                j.teyit = "teyitli"
                j.pencere = None
                return j
            if math.hypot(tkn.x - j.x, tkn.y - j.y) <= self.atla_km:
                j.pencere = None
                return j
            # atla -> K11 merdiveni
            m.g["bolge_atla"] += 1
            j.tek_deneme += 1
            self._atla(j, tkn.free)
        return None

    def _atla(self, j, t):
        m = self.m
        j.slot = None
        k = j.tek_deneme
        if j.dolgu and j.slot is None and k < 3:
            j.uygun = t + 180
            m.havuza(j, "habersiz")
            return
        m.sms(j, t)
        if k == 1:
            self.rezerve(j, t + 60)
        elif k == 2:
            self.rezerve(j, max(t, gun(t) * GUN + 960), son=t + GUN)
        else:
            j.deneme = 0
            j.lane = "istisna"
            m.masa_ekle(j, "istisna", t + 60, oncelik=3)

    def bos_bekle(self, tkn, t):
        s, a = self._slot_now(tkn, t)
        tab = SLOT_A if tkn.aksam else SLOT_G
        m_ = dk(t)
        for (aa, bb) in tab:
            if aa > m_:
                return max(5.0, min(aa - m_, 15.0))
        return 15.0

    def evde_yok(self, j, tkn, t):
        j.tek_deneme += 1
        j.slot = None
        self._atla(j, t)

    def kacan_randevu(self, j, t):
        if j.slot is not None:
            return
        j.pencere = None
        j.teyit = "habersiz"


# ------------------------------------------------------------------ U1H
class U1h(Strateji):
    ad = "U1H: Uzaktan-Önce Huni"
    kod = "U1H"
    aksam_oran = 0.30
    randevu_pay = 1.0

    def gelen(self, j, t):
        m = self.m
        if j.btk and j.tekrar7:
            j.kidemli = True
        if j.doga == "altyapi" and j.altyapi_bilinen:
            m.altyapi_bilet(j, t)
            return
        if j.kanal == "LOJ":
            self.iade_gir(j, t)
            return
        if j.btk and j.konumlu and self._sebeke_suphe(j, t):
            return
        j.lane = "huni"
        j.deneme = 0
        m.masa_ekle(j, "ilk", t, oncelik=0 if j.btk else 2)

    def _sebeke_suphe(self, j, t):
        m = self.m
        n_ayni = n_yakin = 0
        for x in m.son_btk_yakin(j, t, 120):
            if x.state == "KAPALI":
                continue
            n_yakin += 1
            if math.hypot(x.px - j.px, x.py - j.py) < 0.01:
                n_ayni += 1
        if n_ayni + 1 >= 3 or n_yakin + 1 >= 5:
            m.g["kume_alarm"] += 1
            j.lane = "sebeke"
            m.masa_ekle(j, "noc", t, oncelik=1)
            return True
        return False

    def baslangic(self, t, birikim):
        m = self.m
        for j in birikim:
            if j.btk and j.tekrar7:
                j.kidemli = True
            if j.kanal == "LOJ":
                self.iade_gir(j, t)
                continue
            j.lane = "huni"
            j.deneme = 0
            m.masa_ekle(j, "ilk", mesaiye(t), oncelik=4 if j.btk else 6)

    def masa_oncelik(self, g, t):
        j = g.j
        o = 0 if g.amac == "geri_arama" else g.oncelik
        return (o, j.hedef, g.seq)

    def masa_sonuc(self, g, sonuc, t):
        j = g.j
        m = self.m
        if g.meta == "iade" and self.iade_sonuc(j, sonuc, t):
            return None
        if g.amac == "noc":
            if j.doga == "sebeke" and t < j.tau and j.U[25] < 0.8:
                m.beklet(j, j.tau, self._dogrula)
                m.g["kume_sebeke"] += 1
            else:
                j.lane = "huni"
                m.masa_ekle(j, "ilk", t, oncelik=0)
            return None
        if g.amac == "dogrulama":
            if sonuc == "ulasildi" and j.doga != "sebeke":
                j.lane = "huni"
                return self._ulasildi(j, t)
            m.kapat(j, t, "sebeke_toplu")
            return None
        if g.amac == "kurye":
            if sonuc == "ulasildi":
                if j.U[39] < self.P["kurye_basari"]:
                    m.kapat(j, t, "kurye")
                    return 8.0
                m.randevu_ver(j, t, lead=120)
                return 8.0
            j.deneme += 1
            if j.deneme <= 3:
                m.masa_ekle(j, "kurye", t + 120 if dk(t) < 1110 else sabah(t, 495), oncelik=1)
            else:
                m.randevu_ver(j, t, lead=120)
            return None
        if sonuc == "cevapsiz":
            self._merdiven(j, t)
            return None
        return self._ulasildi(j, t)

    def _merdiven(self, j, t):
        """R4: 1. deneme -> SMS + 30 dk -> 90 dk; BTK 3 başarısızda teyitsiz sahaya; diğerleri akşam, ertesi sabah, 48 s askı."""
        m = self.m
        j.deneme += 1
        k = j.deneme
        bir = 2 if j.birikim else 0
        if k == 1:
            m.sms(j, t)
            m.masa_ekle(j, "ilk", t + 30, oncelik=(1 if j.btk else 3) + bir)
        elif k == 2:
            m.masa_ekle(j, "ilk", t + 90, oncelik=(1 if j.btk else 3) + bir)
        elif k == 3 and j.btk:
            m.havuza(j, "habersiz")
            m.g["teyitsiz_sevk"] += 1
        elif k == 3:
            m.masa_ekle(j, "ilk", aksam_bandi(t, 1050, 1140), oncelik=3 + bir)
        elif k == 4:
            m.masa_ekle(j, "ilk", sabah(t, 495), oncelik=3 + bir)
        elif k == 5:
            m.beklet(j, t + 48 * 60, self._uyanis)
        else:
            m.kapat(j, t, "ulasilamadi")

    def _uyanis(self, j, t):
        self.m.masa_ekle(j, "ilk", mesaiye(t), oncelik=3)

    def _dogrula(self, j, t):
        self.m.masa_ekle(j, "dogrulama", mesaiye(t), oncelik=1)

    def _ulasildi(self, j, t):
        m = self.m
        P = self.P
        if j.tip == "KANAL_SIKAYETI":
            self.masa_ulasildi_kanal(j, t)
            return 4.0
        if j.tip == "SORU_CEVAP":
            m.kapat(j, t, "tel_masa")
            return 3.0
        if j.tip == "CIHAZ_IADE" and j.doga != "saha":
            self.iade_ulasildi(j, t)
            return 3.0
        if j.doga == "iptal":
            m.kapat(j, t, "iptal")
            return 5.0
        if j.btk:
            if not j.kidemli:
                r = m.cozum(j, t, "teshis")
                if r == "cozuldu":
                    m.kapat(j, t, "tel_masa")
                    return 10.0
                if r == "sebeke":
                    m.beklet(j, max(j.tau, t + 30), self._dogrula)
                    return 10.0
            m.randevu_ver(j, t, lead=60)
            return 10.0
        if P["kurye_var"] and j.tip in KURYE_TIP and j.kurye_kabul:
            d = gun(t)
            if dk(t) < 960 and m.kurye_say[d] < P["kurye_kapasite"]:
                m.kurye_say[d] += 1
                m.beklet(j, t + 150, self._kurye_teslim)
                return 6.0
            d2 = d + 1
            while m.kurye_say[d2] >= P["kurye_kapasite"]:
                d2 += 1
            m.kurye_say[d2] += 1
            m.beklet(j, d2 * GUN + 660 + 180 * j.U[38], self._kurye_teslim)
            return 6.0
        m.randevu_ver(j, t, lead=120)
        return 6.0

    def _kurye_teslim(self, j, t):
        self.m.g["kurye"] += 1
        j.deneme = 0
        self.m.masa_ekle(j, "kurye", t + 30, oncelik=1)

    def sec(self, tkn, t):
        m = self.m
        for _ in range(4):
            t = tkn.free
            j = m.sec_katman(tkn, t, lambda pool, d: self._sec1(tkn, t, pool, d))
            if j is None:
                return None
            if j.pencere is None:
                # teyitsiz BTK: teknisyenin 45 dk önceki araması ilk temas
                ok = m.tek_ara(tkn, j)
                if ok:
                    if j.btk and not j.kidemli:
                        r = m.cozum(j, tkn.free, "kontrol")
                        if r == "cozuldu":
                            m.kapat(j, tkn.free, "tel_tek")
                            continue
                    if not m.simdi_musait(j, tkn.free):
                        m.randevu_ver(j, tkn.free, lead=120)
                        continue
                    j.teyit = "teyitli"
                return j
            # teyitli iş: 45 dk önce 'yoldayım' araması
            ok = m.tek_ara(tkn, j)
            return j
        return None

    def _sec1(self, tkn, t, pool, d):
        m = self.m
        j = m.pencere_sec(tkn, t, pool, d)
        if j is not None:
            return j
        tr = m.yol_dk_vec(d)
        best, bk = None, None
        for i, x in enumerate(pool):
            if x.pencere is not None:
                continue
            if (t - x.t0) >= GUN:
                k = (1, (0 if x.btk else 1), x.t0 + tr[i])
            else:
                k = (0, 0, x.hedef - (240 if x.btk else 0) + tr[i])
            if bk is None or k < bk:
                best, bk = x, k
        return best

    def evde_yok(self, j, tkn, t):
        m = self.m
        j.lane = "huni"
        if j.deneme >= 3 and j.btk:
            m.masa_ekle(j, "ilk", aksam_bandi(t, 1050, 1140), oncelik=1)
        else:
            m.masa_ekle(j, "ilk", t, oncelik=1)

    def kacan_randevu(self, j, t):
        j.lane = "huni"
        self.m.masa_ekle(j, "ilk", mesaiye(t), oncelik=1)


# ------------------------------------------------------------------ KARMA (yarış sonrası birleşim)
class Karma(Strateji):
    """Yarıştan çıkan dersleri birleştiren aday: HAM'ın 'aramadan sahaya ver' hızı + teknisyenin tek
    'yoldayım' araması (ulaşılamazsa YİNE gider) + BTK'da masanın paralel hızlı teşhisi (sahayı bekletmez)
    + hedef (TV 6 s / Bağlantı 12 s / 24 s) sıralı rota + musluk koruması + şebeke kümesi NOC kontrolü
    + %15 akşam vardiyası. Tasarım tohumu 1 ile yapıldı; sonuçlar ayrı tohumlarda raporlanır."""
    ad = "KARMA: aramasız doğrudan sevk + 'yetişir' sıralaması + paralel BTK masa teşhisi"
    kod = "KARMA"
    son_var = True
    randevu_pay = 0.6
    masa_teshis = True
    yoldayim = False          # teknisyenin 'yoldayım' araması (tarama: rho yüksekse yararlı)
    siralama = "yetisir"      # 'yetisir' | 'hedef' | 'ham'
    kume_nok = True
    gec_kota = 4              # her 4. seçimde 24 s'i kaçmış en eski iş (birikim erisin diye); 0 = kapalı
    aksam_oran = 0.0
    asiri_yuk_esigi = 15      # adayların içinde >= bu kadar gecikmiş iş varsa 'yetişir', yoksa HAM (FIFO) sırası
    gec_btk_avans = 720       # gecikmiş işler arasında seçimde BTK'ya verilen yaş avansı (dk)

    def gelen(self, j, t):
        m = self.m
        if j.btk and j.tekrar7:
            j.kidemli = True
        if j.doga == "altyapi" and j.altyapi_bilinen:
            m.altyapi_bilet(j, t)
            return
        if j.kanal == "MASA":
            j.lane = "masa"
            m.masa_ekle(j, "kanal", t, oncelik=4)
            return
        if j.kanal == "LOJ":
            self.iade_gir(j, t)
            return
        if j.btk and j.konumlu and self.kume_nok and self._kume(j, t):
            return
        m.havuza(j, "habersiz")
        if j.btk and self.masa_teshis and not j.kidemli:
            # paralel: iş sahada sırasını beklerken masa 30 dk içinde bir kez arar
            m.masa_ekle(j, "teshis", t, son=t + 45, oncelik=1, durum=False)

    def _kume(self, j, t):
        m = self.m
        n_ayni = n_yakin = 0
        for x in m.son_btk_yakin(j, t, 120):
            if x.state == "KAPALI":
                continue
            n_yakin += 1
            if math.hypot(x.px - j.px, x.py - j.py) < 0.01:
                n_ayni += 1
        if n_ayni + 1 >= 3 or n_yakin + 1 >= 5:
            m.g["kume_alarm"] += 1
            j.lane = "sebeke"
            m.masa_ekle(j, "noc", t, oncelik=0)
            return True
        return False

    def baslangic(self, t, birikim):
        m = self.m
        for j in birikim:
            if j.btk and j.tekrar7:
                j.kidemli = True
            if j.kanal == "MASA":
                j.lane = "masa"
                m.masa_ekle(j, "kanal", mesaiye(t), oncelik=6)
            elif j.kanal == "LOJ":
                self.iade_gir(j, t)
            else:
                m.havuza(j, "habersiz")

    def masa_oncelik(self, g, t):
        o = 0 if g.amac == "geri_arama" else g.oncelik
        return (o, g.j.hedef, g.seq)

    def masa_son(self, g, t):
        pass   # teşhis yetişmediyse iş zaten sahada; bir şey yapılmaz

    def masa_sonuc(self, g, sonuc, t):
        j = g.j
        m = self.m
        if g.meta == "iade" and self.iade_sonuc(j, sonuc, t):
            return None
        if g.amac == "noc":
            if j.doga == "sebeke" and t < j.tau and j.U[25] < 0.8:
                m.beklet(j, j.tau, self._dogrula)
                m.g["kume_sebeke"] += 1
            else:
                m.havuza(j, "habersiz")
            return None
        if g.amac == "dogrulama":
            if sonuc == "ulasildi" and j.doga != "sebeke":
                m.havuza(j, "habersiz")
                return 3.0
            m.kapat(j, t, "sebeke_toplu")
            return None
        if g.amac == "teshis":
            if j.state != "SAHA":
                return None
            if sonuc == "cevapsiz":
                return None          # iş sahada, teknisyen gider
            r = m.cozum(j, t, "teshis")
            if r == "cozuldu":
                m.kapat(j, t, "tel_masa")
            elif r == "sebeke":
                m.beklet(j, max(j.tau, t + 30), self._dogrula)
            elif m.simdi_musait(j, t):
                j.teyit = "teyitli"
            else:
                m.randevu_ver(j, t, lead=60)
            return 10.0
        if sonuc == "cevapsiz":
            self._sonraki(j, t)
            return None
        if j.kanal == "MASA":
            self.masa_ulasildi_kanal(j, t)
            return 4.0
        if j.tip == "CIHAZ_IADE" and j.doga != "saha":
            self.iade_ulasildi(j, t)
            return 3.0
        if j.doga == "iptal":
            m.kapat(j, t, "iptal")
            return 3.0
        if j.btk and not j.kidemli:
            r = m.cozum(j, t, "kontrol")
            if r == "cozuldu":
                m.kapat(j, t, "tel_masa")
                return 4.0
        m.randevu_ver(j, t, lead=90)
        return 4.0

    def _dogrula(self, j, t):
        self.m.masa_ekle(j, "dogrulama", mesaiye(t), oncelik=1)

    def _sonraki(self, j, t):
        """Evde yok / masa: hemen, +2 s, akşam bandı -> SMS + ertesi gün akşam habersiz tekrar -> 48 s askı -> kapat."""
        m = self.m
        j.deneme += 1
        k = j.deneme
        if j.kanal in ("MASA", "LOJ"):
            if k == 1:
                m.masa_ekle(j, g_amac(j), t + 120, oncelik=4)
            elif k == 2:
                m.masa_ekle(j, g_amac(j), aksam_bandi(t), oncelik=4)
            elif k == 3:
                m.sms(j, t)
                m.masa_ekle(j, g_amac(j), sabah(t, 600), oncelik=4)
            else:
                m.kapat(j, t, "ulasilamadi")
            return
        if k == 1:
            m.masa_ekle(j, "istisna", t + 120, oncelik=2 if j.btk else 3)
        elif k == 2:
            m.masa_ekle(j, "istisna", aksam_bandi(t), oncelik=2 if j.btk else 3)
        elif k == 3 and j.bosa < 2:
            m.sms(j, t)
            ng, na = m.kadro(gun(t) + 1)
            uy = (gun(t) + 1) * GUN + (17 * 60 if na > 0 else 9 * 60)
            m.havuza(j, "habersiz", uygun=uy)
        elif k <= 4:
            m.beklet(j, t + 48 * 60, self._son_deneme)
        else:
            m.kapat(j, t, "ulasilamadi")

    def _son_deneme(self, j, t):
        self.m.masa_ekle(j, "istisna", mesaiye(t), oncelik=3)

    def _sec1(self, tkn, t, pool, d):
        m = self.m
        j = m.pencere_sec(tkn, t, pool, d)
        if j is not None:
            return j
        tr = m.yol_dk_vec(d)
        siralama = self.siralama
        if self.asiri_yuk_esigi is not None:
            n_gec = sum(1 for x in pool if x.pencere is None and t - x.t0 >= GUN)
            siralama = "yetisir" if n_gec >= self.asiri_yuk_esigi else "ham"
        if siralama == "ham":
            idx = [i for i, x in enumerate(pool) if x.pencere is None]
            if not idx:
                return None
            order = sorted(idx, key=lambda i: (not pool[i].btk, pool[i].t0))[:5]
            return pool[min(order, key=lambda i: d[i])]
        if self.gec_kota and siralama == "yetisir":
            tkn.sayac += 1
            if tkn.sayac % self.gec_kota == 0:
                gec = [i for i, x in enumerate(pool) if x.pencere is None and t + tr[i] + 30 >= x.t0 + GUN]
                if gec:
                    av = self.gec_btk_avans
                    if av is None:
                        i = min(gec, key=lambda i: (not pool[i].btk, pool[i].t0 + 4 * tr[i]))
                    else:
                        i = min(gec, key=lambda i: pool[i].t0 - (av if pool[i].btk else 0) + 4 * tr[i])
                    return pool[i]
        best, bk = None, None
        for i, x in enumerate(pool):
            if x.pencere is not None:
                continue
            yas = t - x.t0
            if siralama == "yetisir":
                # 24 saate hâlâ yetişebilecek işler önce (son tarihe göre, BTK 6 s öne), yetişemeyecekler sonra
                if t + tr[i] + 30 < x.t0 + GUN:
                    k = (0, x.t0 + GUN - (360 if x.btk else 0) - (120 if x.tip == "TV_ARIZA" else 0) + tr[i])
                else:
                    k = (1, 0 if x.btk else 1, x.t0 + tr[i])
            elif yas < GUN:
                k = (0, (x.hedef - t) + 1.5 * tr[i] - (60 if x.teyit == "teyitli" else 0))
            else:
                k = (1, 1.5 * tr[i] - min(yas / 60.0, 240) - (120 if x.btk else 0))
            if bk is None or k < bk:
                best, bk = x, k
        return best

    def sec(self, tkn, t):
        m = self.m
        for _ in range(4):
            t = tkn.free
            j = m.sec_katman(tkn, t, lambda pool, d: self._sec1(tkn, t, pool, d))
            if j is None:
                return None
            if j.pencere is not None or j.teyit == "teyitli" or not self.yoldayim:
                return j
            ok = m.tek_ara(tkn, j)
            if ok:
                if j.btk and not j.kidemli:
                    r = m.cozum(j, tkn.free, "kontrol")
                    if r == "cozuldu":
                        m.kapat(j, tkn.free, "tel_tek")
                        continue
                if j.doga == "iptal":
                    m.kapat(j, tkn.free, "iptal")
                    continue
                if not m.simdi_musait(j, tkn.free):
                    m.randevu_ver(j, tkn.free, lead=120)
                    continue
                j.teyit = "teyitli"
            return j        # ulaşılamasa da gidilir
        return None

    def evde_yok(self, j, tkn, t):
        j.lane = "istisna"
        j.deneme = 0
        self.m.masa_ekle(j, "istisna", t, oncelik=2 if j.btk else 3)

    def kacan_randevu(self, j, t):
        j.lane = "istisna"
        self.m.masa_ekle(j, "istisna", mesaiye(t), oncelik=2)


class BolgeEsnek(Bolge):
    """Duyarlılık kontrolü: BÖLGE'nin katı takvimi gevşetilir (boştaki teknisyen sonraki dilimi öne çeker,
    cevapsızda 2 km'ye kadar gidilir). Tasarımın kendisi değil; sonucun uygulama ayrıntısından kaynaklanıp
    kaynaklanmadığını sınamak için."""
    ad = "BÖLGE-esnek (kontrol: öne çekme + 2 km)"
    kod = "BOLGE_ESNEK"
    one_cek = True
    atla_km = 2.0


def g_amac(j):
    return "kanal" if j.kanal == "MASA" else "iade"


STRATEJILER = {"BUGUN": Bugun, "HAM": Ham, "DSIR": Dsir, "RPHT": Rpht, "BOLGE": Bolge, "U1H": U1h, "KARMA": Karma}
EK_STRATEJI = {"BOLGE_ESNEK": BolgeEsnek}
TUM_STRATEJI = dict(STRATEJILER, **EK_STRATEJI)


# ================================================================== ÖLÇÜM
def ozet(M):
    P = M.P
    son = M.H - GUN
    yeni = [j for j in M.isler if not j.birikim and REF_DK <= j.t0 < son]
    kararli = [j for j in yeni if j.t0 >= 15 * GUN]

    def oran(L, saat, f=None):
        L2 = [j for j in L if f is None or f(j)]
        if not L2:
            return None
        return sum(1 for j in L2 if j.t_kapat is not None and j.t_kapat - j.t0 <= saat * 60) / len(L2)

    btk = lambda j: j.btk and j.tip in BTK_TIP
    r = {}
    for ad, L in (("tum", yeni), ("kararli", kararli)):
        r[ad] = dict(
            n=len(L),
            uyum_24s=oran(L, 24), uyum_12s=oran(L, 12), uyum_48s=oran(L, 48),
            btk_24s=oran(L, 24, btk),
            tv_6s=oran(L, 6, lambda j: j.tip == "TV_ARIZA"),
            baglanti_12s=oran(L, 12, lambda j: j.tip == "BAGLANTI"),
            saha_24s=oran(L, 24, lambda j: j.kanal == "SAHA"),
            masa_24s=oran(L, 24, lambda j: j.kanal != "SAHA"),
            erteleme_haric_24s=oran(L, 24, lambda j: not j.erteledi),
            ulasilamadi_kapanis=sum(1 for j in L if j.tur == "ulasilamadi") / max(1, len(L)),
            erteleme_payi=sum(1 for j in L if j.erteledi) / max(1, len(L)),
        )
        kap = [(j.t_kapat - j.t0) / 60 for j in L if j.t_kapat is not None]
        r[ad]["kapanis_saat_p50"] = float(np.median(kap)) if kap else None
    # ---- HAKEM1 ek ölçütler: kuyruk (tail) ve gerçek çözüm. Her işin en az 7 gün izlendiği pencere
    # (gün 1 - H-7 gün arası gelenler); açık kalan iş ufukta (H) sansürlenir. ----
    kuyruk = [j for j in yeni if j.t0 < M.H - 7 * GUN]

    def sure_s(j):
        return ((j.t_kapat if j.t_kapat is not None else M.H) - j.t0) / 60.0

    def kmet(L2):
        if not L2:
            return {}
        s_ = np.array([sure_s(j) for j in L2])
        cozum = [j for j in L2 if j.tur != "ulasilamadi"]
        return dict(
            n=len(L2),
            uyum_24s=float(np.mean(s_ <= 24)), uyum_48s=float(np.mean(s_ <= 48)), uyum_72s=float(np.mean(s_ <= 72)),
            asim_72s_pay=float(np.mean(s_ > 72)), asim_7g_pay=float(np.mean(s_ > 168)),
            ort_saat=float(np.mean(s_)), p90_saat=float(np.percentile(s_, 90)), p95_saat=float(np.percentile(s_, 95)),
            gecikme_saat_is=float(np.mean(np.maximum(0.0, s_ - 24))),
            gercek_cozum_24s=float(np.mean([(j.t_kapat is not None and j.tur != "ulasilamadi" and sure_s(j) <= 24)
                                            for j in L2])),
            ulasilamadi_pay=float(np.mean([j.tur == "ulasilamadi" for j in L2])),
            acik_kalan_pay=float(np.mean([j.t_kapat is None for j in L2])),
        )
    r["kuyruk_tum"] = kmet(kuyruk)
    r["kuyruk_btk"] = kmet([j for j in kuyruk if j.btk and j.tip in BTK_TIP])
    # HAKEM1: 'gerçek çözüm' — şebeke arızası ancak şebeke düzelince (tau) çözülmüş sayılır; 'ulaşılamadı'
    # kapanışı çözüm sayılmaz. BOSS kapanışı ile müşterinin hizmete kavuşması arasındaki farkı ölçer.
    def gercek_t(j):
        if j.t_kapat is None or j.tur == "ulasilamadi":
            return None
        return max(j.t_kapat, j.tau) if j.doga == "sebeke" else j.t_kapat
    Lb = [j for j in yeni if j.btk and j.tip in BTK_TIP]
    r["btk_gercek_24s"] = (sum(1 for j in Lb if gercek_t(j) is not None and gercek_t(j) - j.t0 <= 1440) / len(Lb)) if Lb else None
    r["tum_gercek_24s"] = sum(1 for j in yeni if gercek_t(j) is not None and gercek_t(j) - j.t0 <= 1440) / max(1, len(yeni))
    Ls = [j for j in Lb if j.doga == "sebeke"]
    r["sebeke_erken_kapanis"] = (sum(1 for j in Ls if j.t_kapat is not None and j.t_kapat < j.tau) / len(Ls)) if Ls else None
    tur = defaultdict(int)
    for j in yeni:
        tur[j.tur or "acik"] += 1
    r["kapanis_turu_payi"] = {k: round(v / max(1, len(yeni)), 4) for k, v in sorted(tur.items(), key=lambda x: -x[1])}
    tip24 = {}
    for tp in ("BAGLANTI", "TV_ARIZA", "KANAL_SIKAYETI", "MODEM_DEGISIKLIGI", "CIHAZ_IADE", "UCRETLENDIRME", "IKINCI_DONANIM"):
        v = oran(yeni, 24, lambda j, tp=tp: j.tip == tp)
        if v is not None:
            tip24[tp] = round(v, 3)
    r["tip_24s"] = tip24
    G = M.gunluk
    gg = [g for g in G if g["gun"] >= 1]
    ng = max(1, len(gg))
    top = lambda k: sum(g.get(k, 0.0) for g in gg)
    r["gunluk"] = dict(
        ops_cagri=top("ops_cagri") / ng, tek_cagri=top("tek_cagri") / ng,
        toplam_cagri=(top("ops_cagri") + top("tek_cagri") + top("geri_arama")) / ng,
        geri_arama=top("geri_arama") / ng, sms=top("sms") / ng,
        ziyaret=top("ziyaret") / ng, bosa=top("bosa") / ng, kapanis=top("kapanis") / ng,
        km_filo=top("km") / ng, tek_gun=top("tek_gun") / ng, randevu=top("randevu") / ng,
        ops_saat=top("ops_dk") / 60 / P["verim"] / ng,
        ops_kapasite_saat=top("ops_kapasite_dk") / 60 / ng,
        kacan_randevu=top("kacan_randevu") / ng, gec_varis=top("gec_varis") / ng,
        bos_dk_tek=top("tek_bos_dk") / max(1.0, top("tek_gun")),
        ziyaret_tek=top("ziyaret") / max(1.0, top("tek_gun")),
        kapasite_alarmi=top("kapasite_alarmi") / ng, kume_alarm=top("kume_alarm") / ng,
        tekrar_uretilen=top("tekrar_uretilen") / ng,
        telefon_kapanis=(top("kapanis_tel_masa") + top("kapanis_tel_tek")) / ng,
    )
    r["bosa_ziyaret_orani"] = top("bosa") / max(1.0, top("ziyaret"))
    r["km_teknisyen_gun"] = top("km") / max(1.0, top("tek_gun"))
    r["ops_doluluk"] = top("ops_dk") / max(1.0, top("ops_kapasite_dk") * P["verim"])
    # birikim erime
    bir0 = sum(1 for j in M.isler if j.birikim and REF_DK - j.t0 > GUN)
    seri = [(g["gun"], g["birikim_gecikmis_acik"]) for g in G]
    esik = 0.05 * bir0
    erime = None
    for d, v in seri:
        if v <= esik:
            erime = d
            break
    tahmini = False
    if erime is None and len(seri) >= 8:
        a = seri[-8][1]
        b = seri[-1][1]
        hiz = (a - b) / 7.0
        if hiz > 0.05:
            erime = seri[-1][0] + (b - esik) / hiz
            tahmini = True
        else:
            erime = 999.0
            tahmini = True
    r["birikim"] = dict(gecikmis_baslangic=bir0, erime_gun=erime, erime_tahmini=tahmini,
                        seri=[v for _, v in seri])
    a24 = [(g["gun"], g["acik_24s_ustu"]) for g in G]
    r["acik_24s_ustu_seri"] = [v for _, v in a24]
    r["acik_24s_ustu_son_hafta"] = float(np.mean([v for _, v in a24[-7:]]))
    ilk100 = next((d for d, v in a24 if v < 100 and d >= 1), None)
    r["acik_24s_ustu_100_alti_ilk_gun"] = ilk100
    return r


def calistir(args):
    kod, seed, deg = args
    P = varsayilan()
    for k, v in (deg or {}).items():
        P[k] = v
    V = _VERI
    M = Motor(V, P, STRATEJILER[kod], seed)
    M.calis()
    r = ozet(M)
    r["kod"] = kod
    r["seed"] = seed
    return r


_VERI = None


def _init(V):
    global _VERI
    _VERI = V

# ================================================================== DENEYLER
TOHUM_ANA = [101, 102, 103, 104, 105]      # tasarımda kullanılmayan tohumlar (KARMA tohum 1-3 ile tasarlandı)
TOHUM_TARAMA = [201, 202, 203]
KADRO_ANA = [10, 16, 20]
KADRO_TARAMA = [10, 12, 14, 16, 18, 20, 22, 24]
N_REF = 16
DUYARLILIK = {
    "referans": dict(),
    "evde_yok_%15": dict(evdeyok_hedef=0.15),
    "evde_yok_%30": dict(evdeyok_hedef=0.30),
    "evde_yok_%45": dict(evdeyok_hedef=0.45),
    "telefonla_cozulur_x0.6": dict(tel_carpan=0.6),
    "telefonla_cozulur_x1.3": dict(tel_carpan=1.3),
    "disaridaki_acar_rho0.1": dict(rho=0.1),
    "disaridaki_acar_rho0.6": dict(rho=0.6),
    "disaridaki_acar_rho0.9": dict(rho=0.9),
    "ulasma_dusuk": dict(cevap_p=(0.70, 0.35, 0.08)),
    "ulasma_yuksek": dict(cevap_p=(0.88, 0.55, 0.18)),
    "operasyon_4_kisi": dict(O=4, O_aksam=2, O_pazar=2),
    "operasyon_12_kisi": dict(O=12, O_aksam=6, O_pazar=4),
    "arama_hizi_dusuk_verim0.6": dict(verim=0.6),
    "arama_hizi_yuksek_verim0.95": dict(verim=0.95),
    "giris_-15%": dict(giris_carpan=0.85),
    "giris_+15%": dict(giris_carpan=1.15),
    "trafik_20kmsa": dict(hiz_sehir=20.0),
    "trafik_35kmsa": dict(hiz_sehir=35.0),
    "elle_3_aktarim": dict(senkron="3x"),
    "konumsuz_ilce_merkezi": dict(konumsuz_plan="ilce"),
    "sms_kanali_yok": dict(sms_etkisi=1.0),
    "kurye_yok": dict(kurye_var=False),
    "uzaktan_cozum_dusuk": dict(q_teshis=0.6, q_kontrol=0.3),
}
METRIK = ["uyum_24s", "uyum_24s_kararli", "btk_24s", "tv_6s", "baglanti_12s", "uyum_12s", "uyum_48s", "saha_24s",
          "masa_24s", "erteleme_haric_24s", "ulasilamadi_kapanis", "kapanis_saat_p50", "erime_gun",
          "acik_24s_ustu_son_hafta", "gunluk_arama", "ops_cagri", "tek_cagri", "ziyaret", "bosa_ziyaret_orani",
          "km_teknisyen_gun", "km_filo", "ops_saat", "ops_doluluk", "ziyaret_tek", "bos_dk_tek", "sms", "randevu",
          "telefon_kapanis", "kapanis", "cagri_saat_kisi",
          "k_uyum_72s", "k_asim_72s", "k_asim_7g", "k_ort_saat", "k_p90_saat", "k_gecikme_saat", "k_gercek_24s",
          "k_acik_kalan", "kb_uyum_24s", "kb_uyum_48s", "kb_asim_72s", "kb_ort_saat", "kb_gecikme_saat", "kb_p90_saat",
          "acik24_son", "acik24_egim_gun", "btk_gercek_24s", "tum_gercek_24s", "sebeke_erken_kapanis"]


def duz(r):
    g = r["gunluk"]
    return dict(
        uyum_24s=r["tum"]["uyum_24s"], uyum_24s_kararli=r["kararli"]["uyum_24s"], btk_24s=r["tum"]["btk_24s"],
        tv_6s=r["tum"]["tv_6s"], baglanti_12s=r["tum"]["baglanti_12s"], uyum_12s=r["tum"]["uyum_12s"],
        uyum_48s=r["tum"]["uyum_48s"], saha_24s=r["tum"]["saha_24s"], masa_24s=r["tum"]["masa_24s"],
        erteleme_haric_24s=r["tum"]["erteleme_haric_24s"], ulasilamadi_kapanis=r["tum"]["ulasilamadi_kapanis"],
        kapanis_saat_p50=r["tum"]["kapanis_saat_p50"], erime_gun=min(999.0, r["birikim"]["erime_gun"]),
        acik_24s_ustu_son_hafta=r["acik_24s_ustu_son_hafta"], gunluk_arama=g["toplam_cagri"],
        ops_cagri=g["ops_cagri"], tek_cagri=g["tek_cagri"], ziyaret=g["ziyaret"],
        bosa_ziyaret_orani=r["bosa_ziyaret_orani"], km_teknisyen_gun=r["km_teknisyen_gun"], km_filo=g["km_filo"],
        ops_saat=g["ops_saat"], ops_doluluk=r["ops_doluluk"], ziyaret_tek=g["ziyaret_tek"],
        bos_dk_tek=g["bos_dk_tek"], sms=g["sms"], randevu=g["randevu"], telefon_kapanis=g["telefon_kapanis"],
        kapanis=g["kapanis"], cagri_saat_kisi=(g["ops_cagri"] + g["geri_arama"]) / max(0.1, g["ops_saat"]),
        k_uyum_72s=r["kuyruk_tum"].get("uyum_72s"), k_asim_72s=r["kuyruk_tum"].get("asim_72s_pay"),
        k_asim_7g=r["kuyruk_tum"].get("asim_7g_pay"), k_ort_saat=r["kuyruk_tum"].get("ort_saat"),
        k_p90_saat=r["kuyruk_tum"].get("p90_saat"), k_gecikme_saat=r["kuyruk_tum"].get("gecikme_saat_is"),
        k_gercek_24s=r["kuyruk_tum"].get("gercek_cozum_24s"), k_acik_kalan=r["kuyruk_tum"].get("acik_kalan_pay"),
        kb_uyum_24s=r["kuyruk_btk"].get("uyum_24s"), kb_uyum_48s=r["kuyruk_btk"].get("uyum_48s"),
        kb_asim_72s=r["kuyruk_btk"].get("asim_72s_pay"), kb_ort_saat=r["kuyruk_btk"].get("ort_saat"),
        kb_gecikme_saat=r["kuyruk_btk"].get("gecikme_saat_is"), kb_p90_saat=r["kuyruk_btk"].get("p90_saat"),
        btk_gercek_24s=r.get("btk_gercek_24s"), tum_gercek_24s=r.get("tum_gercek_24s"),
        sebeke_erken_kapanis=r.get("sebeke_erken_kapanis"),
        acik24_son=r["acik_24s_ustu_seri"][-1], acik24_egim_gun=(r["acik_24s_ustu_seri"][-1] - r["acik_24s_ustu_seri"][-15]) / 14.0,
        birikim_seri=r["birikim"]["seri"], acik24_seri=r["acik_24s_ustu_seri"], tip_24s=r["tip_24s"],
        kapanis_turu=r["kapanis_turu_payi"],
    )


def gorev(args):
    deney, kod, N, seed, deg = args
    P = varsayilan()
    P["N"] = N
    for k, v in (deg or {}).items():
        P[k] = v
    M = Motor(_VERI, P, TUM_STRATEJI[kod], seed)
    M.calis()
    r = duz(ozet(M))
    r.update(deney=deney, kod=kod, N=N, seed=seed, evdeyok_gunduz=M.evdeyok_gunduz_ort)
    return r


def ortalama(rs):
    out = {}
    for k in METRIK:
        v = [r[k] for r in rs if r.get(k) is not None]
        if not v:
            out[k] = None
            continue
        if k == "erime_gun":
            out[k] = float(np.median(v))
            out["erime_gun_min"] = float(min(v))
            out["erime_gun_max"] = float(max(v))
        else:
            out[k] = float(np.mean(v))
            if k in ("uyum_24s", "btk_24s"):
                out[k + "_min"] = float(min(v))
                out[k + "_max"] = float(max(v))
    out["n_tekrar"] = len(rs)
    return out


def deney_listesi(hizli=False):
    kodlar = list(STRATEJILER)
    t_ana = TOHUM_ANA[:2] if hizli else TOHUM_ANA
    t_tar = TOHUM_TARAMA[:1] if hizli else TOHUM_TARAMA
    L = []
    for N in KADRO_ANA:
        for k in kodlar:
            for s in t_ana:
                L.append(("ana", k, N, s, None))
    for N in KADRO_TARAMA:
        if N in KADRO_ANA:
            continue
        for k in kodlar:
            for s in t_tar:
                L.append(("kadro", k, N, s, None))
    for N in (16, 20, 24):
        for s in t_tar:
            L.append(("ek", "BOLGE_ESNEK", N, s, None))
    duy = list(DUYARLILIK.items())[:3] if hizli else list(DUYARLILIK.items())
    for ad, deg in duy:
        for k in kodlar:
            for s in t_tar:
                L.append(("duy:" + ad, k, N_REF, s, deg))
    return L


def calistir_hepsi(hizli=False, isci=None):
    V = veri_yukle()
    L = deney_listesi(hizli)
    isci = isci or max(1, (os.cpu_count() or 4) - 1)
    t1 = time.time()
    sonuc = []
    with ProcessPoolExecutor(isci, initializer=_init, initargs=(V,)) as ex:
        for i, r in enumerate(ex.map(gorev, L, chunksize=1)):
            sonuc.append(r)
            if (i + 1) % 50 == 0:
                print(f"  {i + 1}/{len(L)} koşu, {time.time() - t1:.0f} s", flush=True)
    return V, sonuc, time.time() - t1


def topla(V, sonuc, sure):
    kodlar = list(STRATEJILER)
    grup = defaultdict(list)
    for r in sonuc:
        grup[(r["deney"], r["kod"], r["N"])].append(r)
    ana = {str(N): {k: ortalama(grup[("ana", k, N)]) for k in kodlar} for N in KADRO_ANA}
    kadro = {}
    for k in kodlar:
        kadro[k] = {}
        for N in KADRO_TARAMA:
            rs = grup[("ana", k, N)] + grup[("kadro", k, N)]
            if rs:
                kadro[k][str(N)] = {m: ortalama(rs)[m] for m in ("uyum_24s", "btk_24s", "erime_gun", "gunluk_arama",
                                                                    "bosa_ziyaret_orani", "ops_saat",
                                                                    "acik_24s_ustu_son_hafta", "km_teknisyen_gun")}
    # seriler (ana deney, ilk tohum ortalaması)
    seri = {}
    for N in KADRO_ANA:
        seri[str(N)] = {}
        for k in kodlar:
            rs = grup[("ana", k, N)]
            if rs:
                seri[str(N)][k] = dict(
                    acik_24s_ustu=np.mean([r["acik24_seri"] for r in rs], axis=0).round(1).tolist(),
                    birikim_gecikmis_acik=np.mean([r["birikim_seri"] for r in rs], axis=0).round(1).tolist())
    tip = {str(N): {k: grup[("ana", k, N)][0]["tip_24s"] for k in kodlar} for N in KADRO_ANA}
    tur = {str(N): {k: grup[("ana", k, N)][0]["kapanis_turu"] for k in kodlar} for N in KADRO_ANA}
    duy = {}
    for ad in DUYARLILIK:
        if not grup.get(("duy:" + ad, kodlar[0], N_REF)):
            continue
        duy[ad] = {}
        for k in kodlar:
            o = ortalama(grup[("duy:" + ad, k, N_REF)])
            duy[ad][k] = {m: o[m] for m in ("uyum_24s", "btk_24s", "erime_gun", "gunluk_arama",
                                            "bosa_ziyaret_orani", "ops_saat", "km_teknisyen_gun")}
    # sıralama sağlamlığı (BUGÜN referansı hariç)
    yarisan = [k for k in kodlar if k != "BUGUN"]
    birinci = defaultdict(int)
    btk_birinci = defaultdict(int)
    siralar = {}
    senaryolar = {}
    for N in KADRO_TARAMA:
        senaryolar[f"N={N}"] = {k: kadro[k][str(N)] for k in yarisan}
    for ad, d in duy.items():
        senaryolar[f"N={N_REF} {ad}"] = {k: d[k] for k in yarisan}
    for s_ad, d in senaryolar.items():
        sira = sorted(yarisan, key=lambda k: -d[k]["uyum_24s"])
        siralar[s_ad] = sira
        birinci[sira[0]] += 1
        btk_birinci[max(yarisan, key=lambda k: d[k]["btk_24s"])] += 1
    ek = {}
    for N in (16, 20, 24):
        rs = grup[("ek", "BOLGE_ESNEK", N)]
        if rs:
            o = ortalama(rs)
            ek[str(N)] = {m: o[m] for m in ("uyum_24s", "btk_24s", "erime_gun", "bos_dk_tek", "ziyaret_tek",
                                            "bosa_ziyaret_orani", "acik_24s_ustu_son_hafta")}
    return dict(ana=ana, kadro=kadro, seri=seri, tip_24s=tip, kapanis_turu=tur, duyarlilik=duy, bolge_esnek=ek,
                siralar=siralar, birinci_sayisi=dict(birinci), btk_birinci_sayisi=dict(btk_birinci),
                sure_s=round(sure, 1), kosu_sayisi=len(sonuc))


def varsayim_tablosu():
    P = varsayilan()
    t = lambda v: ", ".join(f"{x:.2f}".replace(".", ",") for x in v)
    return {
        "giris_gunluk": dict(ad="Günlük geliş", deger="Hafta içi 337,7 · Cumartesi 384 · Pazar 182 (× metro payı 0,96)",
                             kaynak="VERİ (ANLATILAN 1-15 Eylül)", aralik="×0,85-1,15"),
        "tip_payi": dict(ad="Tip payları", deger="Bağlantı %44, Kanal %15, Cihaz İade %11, Modem %10, TV %9 ...", kaynak="VERİ"),
        "saat_profili": dict(ad="Saatlik varış", deger="09:00'da %13 zirve, 10-19 arası saat başı %6-8", kaynak="VERİ"),
        "konum": dict(ad="Konum", deger="Metro binaları, aktif abone ağırlıklı; konumlu olma BOSS tip oranı (%0-100)",
                      kaynak="VERİ (bina_master + BOSS Lokasyon)"),
        "telefonla_cozulur_pay": dict(ad="Telefonla çözülebilir BTK payı", deger="Bağlantı %28,6, TV %34,1, Doping %33,7",
                                      kaynak="VERİ (TAMAMLANDI kapanış nedeni; üst sınır)", aralik="×0,6-1,3"),
        "sebeke_pay": dict(ad="Şebeke kaynaklı BTK payı", deger="Bağlantı %11,2, TV %14,3; yarısı 300 m kümeler, çözüm medyanı 6 s",
                           kaynak="VERİ + VARSAYIM (küme)"),
        "sinif_payi": dict(ad="Ulaşılabilirlik sınıfları (kolay/orta/zor)", deger=t(P["sinif_pay"]) + "; notlu birikimde " + t(P["sinif_pay_notlu"]),
                           kaynak="VARSAYIM (veri: önce ulaşılamayana sonra da %94 ulaşılamıyor)"),
        "cevap_p": dict(ad="Tek aramada açma (gündüz, sınıf başına)", deger=t(P["cevap_p"]), kaynak="VARSAYIM",
                        aralik="0,70/0,35/0,08 - 0,88/0,55/0,18"),
        "rho": dict(ad="ρ: dışarıdaki müşterinin açma oranı / evdekinin", deger="0,30", kaynak="VARSAYIM", aralik="0,1-0,9"),
        "evde_yok_habersiz": dict(ad="Habersiz ziyarette evde yok", deger="hafta içi gündüz ~%22 (çalışan müşteri %8/%22/%45 + %6 gürültü); akşam/hafta sonu ~%11",
                                  kaynak="VARSAYIM", aralik="%15-45"),
        "teyitli_evde_yok": dict(ad="Teyitli ziyarette evde yok / randevuda gelmeme", deger="%5 / %8 (geç kalınırsa başarı ×0,6)",
                                 kaynak="VARSAYIM"),
        "uzaktan_cozum": dict(ad="Telefonla çözme başarısı", deger="masa teşhisi %85, kısa kontrol %45; kendiliğinden düzelme %40 (ort. 6 s)",
                              kaynak="VARSAYIM", aralik="%60 / %30"),
        "yerinde_sure": dict(ad="Yerinde süre", deger="arıza 30, modem 35, 2.Donanım 55 dk (lognormal σ 0,5); hafif 12, şebeke 15; kapıda bekleme 10",
                             kaynak="VERİ vekili (ardışık kapanış 31 dk) + VARSAYIM"),
        "yol": dict(ad="Yol", deger="kuş uçuşu ×1,35; şehir 25 km/sa (10 km üstü 60 km/sa); park 5 dk", kaynak="VARSAYIM",
                    aralik="20-35 km/sa"),
        "teknisyen_vardiya": dict(ad="Teknisyen vardiyası", deger="gündüz 08:30-18:30 (BUGÜN ~09:15), akşam 12:00-21:00, 30 dk mola; Pazar tavan(0,55·N)",
                                  kaynak="VERİ (Pazar 4-8 kişi) + VARSAYIM", aralik="N = 10-24"),
        "operasyon": dict(ad="Operasyon masası", deger="8 kişi 08:30-17:30, 4 kişi 17:30-20:30, Pazar 3; verim 0,8; başarısız arama 2 dk, randevu 4, teşhis 10",
                          kaynak="VARSAYIM", aralik="4-12 kişi; verim 0,6-0,95"),
        "ilk_seferde_cozum": dict(ad="İlk seferde çözüm", deger="%92", kaynak="VARSAYIM"),
        "telefonla_kapanis_ek_tekrar": dict(ad="Telefonla kapanışın ek tekrar riski", deger="%6 (7 günlük tekrar bayraklıda %20)",
                                            kaynak="VARSAYIM (veri: 15 günde tekrar %35)"),
        "altyapi": dict(ad="Altyapı engeli", deger="BTK'nın %2'si; çözüm medyanı 72 s; yarısı binada önceden biliniyor", kaynak="VARSAYIM"),
        "sms_geri_donus": dict(ad="SMS'e geri dönüş", deger="%25", kaynak="VARSAYIM"),
        "kurye": dict(ad="Kurye (yalnız U1H)", deger="kabul Modem %35 / STB %50 / Superbox %70; 40 durak/gün; destek araması %90",
                      kaynak="VARSAYIM (U1H önerisi)"),
        "tekrar7": dict(ad="7 gün içinde tekrar arıza bayrağı", deger="BTK işlerinin %25'i", kaynak="VERİ (U1H analizi) + VARSAYIM"),
    }


def _yuvarla(o, nd=4):
    if isinstance(o, float):
        return round(o, nd)
    if isinstance(o, dict):
        return {k: _yuvarla(v, nd) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_yuvarla(v, nd) for v in o]
    if isinstance(o, (np.floating,)):
        return round(float(o), nd)
    if isinstance(o, (np.integer,)):
        return int(o)
    return o


def kalibrasyon_ozeti(J, V):
    P = V["P"]
    b = J["ana"]["10"]["BUGUN"]
    return dict(
        aciklama="BUGÜN modeli (N=10 arıza teknisyeni, 2 kişilik ofis araması) gözlenen değerlerle karşılaştırılır.",
        model=dict(uyum_24s=b["uyum_24s"], uyum_48s=b["uyum_48s"], btk_24s=b["btk_24s"], kapanis_gun=b["kapanis"],
                   ziyaret_teknisyen_gun=b["ziyaret_tek"], bosa_ziyaret=b["bosa_ziyaret_orani"]),
        gozlenen=dict(uyum_24s_1_14_eylul_kohort=P["gercek_24s_uyum_mevcut_kohort"]["24s"],
                      uyum_48s_1_14_eylul_kohort=P["gercek_24s_uyum_mevcut_kohort"]["48s"],
                      uyum_24s_12_14_eylul="0,21-0,24",
                      kapanis_hafta_ici_gun=P["mevcut_kapasite_acigi"]["yapilan_7_15_eylul_ort"],
                      teknisyen_gunluk_kapanis_p50=P["teknisyen_gunluk_is_ariza_ekibi"]["p50"]),
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hizli", action="store_true", help="kısa deneme (az tohum, az senaryo)")
    ap.add_argument("--md", action="store_true", help="yalnız simulasyon.md'yi mevcut json'dan yeniden yaz")
    ap.add_argument("--tek", nargs=2, metavar=("STRATEJI", "N"), help="tek koşu (tohum 1) özet yazdır")
    ap.add_argument("--isci", type=int, default=None)
    a = ap.parse_args()
    yol_json = os.path.join(CIKTI, "simulasyon.json")
    yol_md = os.path.join(HAKEM, "simulasyon_hakem.md")
    if a.md:
        J = json.load(open(yol_json, encoding="utf-8"))
        J["varsayimlar"] = varsayim_tablosu()
        json.dump(_yuvarla(J), open(yol_json, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
        open(yol_md, "w", encoding="utf-8").write(md_yaz(J))
        print("yazıldı:", yol_md)
        return
    if a.tek:
        V = veri_yukle()
        _init(V)
        r = gorev(("tek", a.tek[0], int(a.tek[1]), 1, None))
        print(json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()
                          if not isinstance(v, (list, dict))}, ensure_ascii=False, indent=1))
        return
    V, sonuc, sure = calistir_hepsi(a.hizli, a.isci)
    T = topla(V, sonuc, sure)
    J = dict(
        meta=dict(
            olusturma="operasyon/analiz/simulasyon.py",
            tarih=datetime.now().strftime("%Y-%m-%d %H:%M"),
            baslangic="29.09.2026 18:00 (BOSS dışa aktarım anı), ufuk 35 gün (30 iş günü + 5 Pazar)",
            kapsam="Mevcut müşteri iş emirleri (adında 'kurulum' geçmeyenler; 'Kurulum Taskı Ürememiş' dahil sayılır "
                   "ama BOSS'ta yok). Metro ilçeler: " + ", ".join(METRO) + f". Geliş hacmi x{V['metro_pay']:.3f} (son 24 s BOSS işlerinin metro payı).",
            birikim_baslangic=len(V["birikim"]), birikim_atlanan=V["birikim_atlanan"],
            tohumlar=dict(ana=TOHUM_ANA, tarama=TOHUM_TARAMA, tasarim="1-3 (yalnız KARMA tasarımında)"),
            kadro_ana=KADRO_ANA, kadro_tarama=KADRO_TARAMA, n_referans=N_REF,
            hizli=a.hizli,
            gizlilik="Çıktıda yalnız toplu sayılar; müşteri/task/lokasyon kimliği, adres, telefon ya da kişi adı yok.",
            kaynaklar=["cikti/is_emri_analizi.json (toplu parametreler)", "veri/master/bina_master.csv (bina konumu, aktif abone)",
                       "TeknikTaskDetayRaporu.xlsx 'Task Detail Report' (başlangıç birikimi: tip, yaş, durum, not, lokasyon)"],
        ),
        stratejiler={k: STRATEJILER[k].ad for k in STRATEJILER},
        varsayimlar=varsayim_tablosu(),
        duyarlilik_senaryolari={k: {kk: (list(vv) if isinstance(vv, tuple) else vv) for kk, vv in v.items()}
                                for k, v in DUYARLILIK.items()},
        **T,
    )
    J["kalibrasyon"] = kalibrasyon_ozeti(J, V)
    os.makedirs(CIKTI, exist_ok=True)
    json.dump(_yuvarla(J), open(yol_json, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
    open(yol_md, "w", encoding="utf-8").write(md_yaz(J))
    print("yazıldı:", yol_json, yol_md, f"({T['kosu_sayisi']} koşu, {T['sure_s']} s)")


def _y(x, nd=0):
    """Türkçe yüzde: 0,662 -> %66"""
    if x is None:
        return "-"
    v = round(100 * x, nd)
    s = (f"{v:.{nd}f}" if nd else f"{int(round(v))}").replace(".", ",")
    return "%" + s


def _s(x, nd=0):
    if x is None:
        return "-"
    if nd == 0:
        return f"{int(round(x)):,}".replace(",", ".")
    return f"{x:.{nd}f}".replace(".", ",")


def _erime(x):
    if x is None:
        return "-"
    if x >= 999:
        return "erimiyor"
    return _s(x, 0) if x == int(x) else _s(x, 1)


KISA = {"BUGUN": "BUGÜN", "HAM": "HAM", "DSIR": "DSİR", "RPHT": "RPHT", "BOLGE": "BÖLGE", "U1H": "U1H",
        "KARMA": "KARMA", "BOLGE_ESNEK": "BÖLGE-esnek"}
TANIM = {
    "BUGUN": "Bugünkü süreç (referans): ofis her işi bir kez arar; ulaşırsa 2 saatlik dilim yazar, ulaşamazsa not düşer ve "
             "ertesi gün yine arar. Teknisyen yalnız dilimli işe gider. Kanal Şikayeti ~1 hafta askıda.",
    "HAM": "Kullanıcının ilk fikri: iş aranmadan ekibe verilir, teknisyen habersiz gider (BTK önce, sonra en eski). "
           "Evde olmayanı operasyon arar ve randevular.",
    "DSIR": "Doğrudan Sevk + İstisna Randevu: aramasız sevk, EDF sırası; teknisyen her işten önce 2 kez arar, ulaşamazsa "
            "iş operasyonun 5 denemeli istisna kuyruğuna gider. %10 akşam vardiyası; Pazar yalnız BTK.",
    "RPHT": "Risk Puanlı Hibrit Triyaj: BTK'yı masa 15-30 dk içinde uzaktan teşhis eder, ulaşamazsa habersiz sevk; "
            "BTK dışı işi teyit edip dilim verir; küme bekletme; birikim için masa taraması.",
    "BOLGE": "Bölge Dalgaları: her iş aranmadan bölge takviminde 24 saat içindeki ilk 2 saatlik dilime yazılır ve SMS "
             "gider; teknisyen yola çıkarken bir kez arar, ulaşamazsa ≤1 km ise gider, değilse atlar. Fazla rezervasyon.",
    "U1H": "Uzaktan-Önce Huni: her iş önce masaya gelir (~2 saatte 3 deneme); ulaşılan iş uzaktan teşhis, kurye ya da "
           "aynı görüşmede verilen dilimle kapanır; BTK'da 3 denemede ulaşılamazsa teyitsiz sevk. %30 geç vardiya.",
    "KARMA": "Yarış sonrası birleşim: HAM'ın aramasız sevki + 'yetişir' sıralaması (24 saatine hâlâ yetişebilecek iş önce, "
             "gecikmişe kota) + BTK'da masanın paralel hızlı teşhisi (sahayı bekletmez) + şebeke kümesi NOC kontrolü.",
}


def md_yaz(J):
    ana = J["ana"]
    kod = [k for k in J["stratejiler"]]
    yarisan = [k for k in kod if k != "BUGUN"]
    Nref = str(J["meta"]["n_referans"])
    r16 = ana[Nref]
    sira16 = sorted(yarisan, key=lambda k: -r16[k]["uyum_24s"])
    r10, r20 = ana["10"], ana["20"]
    sira10 = sorted(yarisan, key=lambda k: -r10[k]["uyum_24s"])
    sira20 = sorted(yarisan, key=lambda k: -r20[k]["uyum_24s"])
    kad = J["kadro"]
    duy = J["duyarlilik"]
    kal = J["kalibrasyon"]
    bir = J.get("birinci_sayisi", {})
    btkbir = J.get("btk_birinci_sayisi", {})
    toplam_sen = sum(bir.values())
    L = []
    w = L.append

    w("# İş Emri Simülasyonu: Strateji Yarışı")
    w("")
    w(f"*Dehanet EÇM, mevcut müşteri iş emirleri. Ayrık olay benzetimi; {J['meta']['tarih']} tarihli çalıştırma, "
      f"{J['kosu_sayisi']} koşu. Kod: `operasyon/analiz/simulasyon.py`, sayısal çıktı: `cikti/simulasyon.json`.*")
    w("")
    w("## 1. Kısa sonuç")
    w("")
    w(f"- **Kazanan: {KISA[sira16[0]]}.** Tüm stratejiler aynı gelişler, aynı müşteri davranışı ve aynı kaynakla "
      f"yarıştı. Referans kadroda ({Nref} arıza teknisyeni) yeni işlerin 24 saatte kapanma oranı "
      + ", ".join(f"{KISA[k]} {_y(r16[k]['uyum_24s'])}" for k in sira16)
      + f"; bugünkü süreç {_y(r16['BUGUN']['uyum_24s'])}.")
    w(f"- **Bugünkü kadroda (10 teknisyen) fark en büyük.** {KISA[sira10[0]]} {_y(r10[sira10[0]]['uyum_24s'])}, "
      f"ikinci {KISA[sira10[1]]} {_y(r10[sira10[1]]['uyum_24s'])}. Kullanıcının ham fikri (HAM) {_y(r10['HAM']['uyum_24s'])}, "
      f"bugünkü süreç {_y(r10['BUGUN']['uyum_24s'])}.")
    w(f"- **Kadro yeterliyse ham fikir de iyi çalışıyor.** 20 teknisyende HAM {_y(r20['HAM']['uyum_24s'])} ile KARMA "
      f"{_y(r20['KARMA']['uyum_24s'])} başa baş. HAM'ın katı 'önce BTK' sırası BTK'da biraz daha iyi "
      f"({_y(r20['HAM']['btk_24s'])} ve {_y(r20['KARMA']['btk_24s'])}).")
    w("- **Asıl kaldıraç teknisyen sayısı.** Hiçbir strateji 24 teknisyene kadar %90'a ulaşmıyor. KARMA'da 24 saat uyumu "
      + ", ".join(f"{N} kişide {_y(kad['KARMA'][N]['uyum_24s'])}" for N in ("10", "14", "16", "20", "24")) + ".")
    w("- **Arama politikası:** aramadan gidip evde olmayanı aramak, herkesi önce aramaktan hızlı. Boşa ziyaret "
      f"(HAM {_y(r16['HAM']['bosa_ziyaret_orani'])}), bekletilen işin 24 saati kaçırmasından ucuz. Önce arayan stratejilerde "
      f"boşa ziyaret düşük (DSİR {_y(r16['DSIR']['bosa_ziyaret_orani'])}) ama ulaşılamayan iş masada günlerce bekliyor.")
    w(f"- **Bugünkü süreçte darboğaz ofis.** BUGÜN modelinde 2 kişilik ofis araması %100 dolu; teknisyen 10'dan 24'e "
      f"çıksa da 24 saat uyumu {_y(kad['BUGUN']['10']['uyum_24s'])} → {_y(kad['BUGUN']['24']['uyum_24s'])} kalıyor. "
      "Önce süreç değişmeli ('herkesi ara' kaldırılmalı), sonra kadro eklenmeli.")
    w(f"- **Sıralamanın sağlamlığı:** {toplam_sen} senaryonun (8 kadro düzeyi + {toplam_sen - 8} duyarlılık) "
      f"{bir.get('KARMA', 0)}'inde KARMA, {bir.get('HAM', 0)}'inde HAM birinci; diğerleri hiçbir senaryoda birinci değil. "
      "Yöntem sıralamasını tersine çeviren tek şey kapasite/yük oranı: kıt kapasitede KARMA açık ara önde, bol kapasitede "
      "HAM ile başa baş (BTK'da HAM önde).")
    w("")

    w("## 2. Yöntem")
    w("")
    w("**Model.** 5 dakikalık adımlı ayrık olay benzetimi. Başlangıç 29.09.2026 18:00 (BOSS dışa aktarım anı), ufuk 35 gün "
      "(30 iş günü + 5 Pazar). Bileşenler:")
    w("")
    w("- **Gelişler (VERİ).** Günlük hacim ANLATILAN 1-15 Eylül'den alındı: hafta içi 337,7, Cumartesi 384, Pazar 182; "
      "günlük sapma lognormal σ=0,15. Tip payları ve saatlik varış profili (09:00 zirvesi) de veriden. 2.Donanım günde 5,4.")
    w(f"- **Kapsam (metro).** Nilüfer, Osmangazi, Yıldırım, Mudanya, Gürsu ve Kestel; son 24 saatteki BOSS işlerinin "
      f"payı %{int(round(100 * float(J['meta']['kapsam'].split('x')[-1].split(' ')[0])))}. Uzak ilçeler (Yalova, İnegöl, Gemlik, "
      "Karacabey...) yerel teknisyene bağlı kabul edildi.")
    w(f"- **Başlangıç birikimi.** BOSS 'Task Detail Report' sayfasındaki {J['meta']['birikim_baslangic']} metro mevcut-müşteri "
      "işi; tip, yaş, askı/durum, 'ulaşılamadı' notu ve bina konumuyla (Lokasyon, 8 haneye tamamlanarak bina_master'a bağlandı).")
    w("- **Konum.** Yeni iş, aktif abone sayısına göre ağırlıklı rastgele bir metro binasına düşer. Konumlu olma olasılığı "
      "BOSS'taki tip oranıdır (TV %100, Bağlantı %74, Kanal/Superbox %0). Konumsuz iş planlamada mahalle merkezine, yol "
      "hesabında gerçek binaya göre yürür. Yol: kuş uçuşu ×1,35, şehirde 25 km/sa (10 km üstü 60 km/sa), park 5 dk.")
    w("- **Arıza doğası (VERİ, TAMAMLANDI kapanış nedenleri).** BTK işi telefonla çözülür (Bağlantı %28,6, TV %34), "
      "şebeke (%11-14; yarısı 300 m içinde 3 saatte gelen kümeler, çözüm medyanı 6 s), altyapı (%2, 72 s) ya da gerçek "
      "saha işidir. Telefonla çözülenin %40'ı kendiliğinden düzelir (ort. 6 s). Masa teşhisi %85, kısa kontrol %45 çözer.")
    w("- **Müşteri (VARSAYIM).** Üç ulaşılabilirlik sınıfı var: %60 kolay, %25 orta, %15 zor; 'ulaşılamadı' notlu "
      "birikimde bu oranlar %20/%35/%45. Her müşterinin gizli bir 'evde mi' durumu var. Çalışan müşteri (%8/%22/%45) hafta "
      "içi 09-17 dışarıda, herkes her 2 saatlik blokta %6 dışarıda. Habersiz gündüz ziyarette ortalama evde yok ≈%22. "
      "Telefonu açma evde olmaya bağlı: dışarıdaki müşteri, evdekinin ρ=0,3 katı olasılıkla açar. Bu yüzden 'açmadı' "
      "bilgisi 'evde değil' olasılığını artırır ve bu korelasyon her stratejiye aynı işler.")
    w("- **Ziyaret sonucu.** Habersiz ziyarette müşteri gizli duruma göre evdedir ya da değildir. Teyitli ziyarette %5, "
      "randevuda %8 gelmeme var; pencereye geç kalınırsa başarı ×0,6. SMS ile dilim bildirilen ve o saatte dışarıda "
      "olan müşterinin %40'ı yine de evde birini bulundurur. İlk seferde çözüm %92. Telefonla kapatılan BTK işinin %6'sı "
      "(7 günlük tekrar bayraklıda %20) 1-7 gün içinde tekrar arıza olarak geri gelir.")
    w("- **Teknisyen.** Hafta içi ve Cumartesi N kişi, Pazar tavan(0,55·N). Gündüz vardiyası 08:30-18:30 (BUGÜN ~09:15), "
      "akşam vardiyası 12:00-21:00, 30 dk mola. Her teknisyenin k-ortalama ile belirlenen bir bölgesi var. Aday "
      "sırası: önce kendi bölgesi ve 3 km içi, sonra 10 km içi, sonra tüm metro. İş biten teknisyen bir sonraki işi "
      "stratejinin kuralıyla seçer.")
    w("- **Operasyon (masa).** 08:30-17:30 arası 8 kişi, 17:30-20:30 arası 4 kişi, Pazar 3 kişi; verim 0,8. Arama "
      "süreleri: başarısız 2 dk, randevu/kontrol 4 dk, uzaktan teşhis 10 dk. BUGÜN'de ofis araması 2 kişi. Önceliği "
      "strateji belirler; kapasite dolarsa kuyruk bekler.")
    w("- **Adil yarış.** Ortak rastgele sayılar kullanıldı: aynı tohumda her strateji aynı işleri, aynı müşteriyi ve k. "
      "aramada aynı açma/açmama çekilişini görür. Stratejiler yalnız kararlarıyla ayrışır. Kaynaklar eşit: aynı N, aynı "
      "masa. Geçici kurtarma timi ya da esnek teknisyen yok. Önerilen stratejiler kendi vardiya bölüşümünü seçer.")
    w("- **Tohumlar.** KARMA, tohum 1-3 ile tasarlandı. Raporlanan ana yarış 101-105, kadro taraması ve duyarlılık "
      "201-203 tohumlarıyla koşuldu. Bu tohumlar tasarımda hiç kullanılmadı.")
    w("")
    w("**Ölçütler.** Hepsi 35 günlük dönem için; yeni işler son 24 saat hariç.")
    w("")
    w("- **24 s uyumu:** 29.09 18:00'den sonra gelen işlerin 24 takvim saatinde kapanan payı. Kapanış türüne bakılmaz; "
      "ulaşılamadı kapanışı ayrıca raporlanır.")
    w("- **BTK 24 s:** Bağlantı, TV+ Arıza, Arama ve Doping işlerinde aynı oran. TV 6 s ve Bağlantı 12 s, Turkcell FOX hedefleri.")
    w("- **Birikim erime günü:** başlangıçta 24 saati geçmiş birikimin %95'inin kapandığı gün. 35 günde erimiyorsa son "
      "haftanın hızıyla uzatılır; hız sıfırsa 'erimiyor' yazılır.")
    w("- **Çağrı/gün:** operasyon ve teknisyen denemeleri ile müşterinin geri araması.")
    w("- **Boşa ziyaret:** ziyaretlerde evde yok ve gelmeme payı.")
    w("- **km/teknisyen-gün:** ziyaret yapan teknisyen başına yol (km).")
    w("- **Operasyon saat/gün:** masa meşguliyeti ÷ verim.")
    w("")

    w("## 3. Yarışan stratejiler")
    w("")
    w("| Kod | Özet |")
    w("|---|---|")
    for k in kod:
        w(f"| **{KISA[k]}** | {TANIM[k]} |")
    w("")
    w("BÖLGE, DSİR, RPHT ve U1H'nin kuralları kendi tasarım belgelerindeki sıraya sadık kodlandı (K/R numaraları "
      "koddaki yorumlarda). Eşit kaynak ilkesi gereği önerilerdeki ek kadro (DSİR 17+2, BÖLGE 34-38 kişi, U1H 10 kişilik "
      "masa + esnek havuz) yarışa verilmedi; etkisi kadro ve masa taramasında görülür.")
    w("")

    w("## 4. Kalibrasyon (bugünkü süreç)")
    w("")
    mo, go = kal["model"], kal["gozlenen"]
    w("| Ölçü | Model (BUGÜN, 10 teknisyen) | Gözlenen |")
    w("|---|---|---|")
    w(f"| 24 s uyumu | {_y(mo['uyum_24s'])} | 1-14 Eylül kohortu %{_s(100 * go['uyum_24s_1_14_eylul_kohort'], 0)}; 12-14 Eylül %21-24 |")
    w(f"| 48 s uyumu | {_y(mo['uyum_48s'])} | 1-14 Eylül kohortu %{_s(100 * go['uyum_48s_1_14_eylul_kohort'], 0)} |")
    w(f"| Kapanış/gün | {_s(mo['kapanis_gun'])} (takvim günü ort.) | hafta içi ~{_s(go['kapanis_hafta_ici_gun'])} |")
    w(f"| Teknisyen başına ziyaret/gün | {_s(mo['ziyaret_teknisyen_gun'], 1)} | kapanış medyanı {_s(go['teknisyen_gunluk_kapanis_p50'])} "
      "(telefonla ve toplu kapanış dahil) |")
    w("")
    w("Model, eylül ortasındaki bozulmuş durumu (%21-24) yakalıyor. Ayın başındaki kohort ortalamasından (%43) düşük; o "
      "dönemde birikim küçüktü. 48 saat uyumu gözlenenden düşük, yani model bugünkü süreç için biraz karamsar. "
      "Stratejiler aynı dünyada yarıştığı için bu fark sıralamayı etkilemez.")
    w("")

    for N in ("10", Nref, "20"):
        d = ana[N]
        sira = sorted(kod, key=lambda k: (k == "BUGUN", -d[k]["uyum_24s"]))
        baslik = {"10": "Bugünkü kadro: 10 arıza teknisyeni (Pazar 6)",
                  Nref: f"Referans: {Nref} teknisyen (Pazar {int(math.ceil(int(Nref) * 0.55))})",
                  "20": "Hedefe yakın kadro: 20 teknisyen (Pazar 11)"}[N]
        w(f"## 5.{['10', Nref, '20'].index(N) + 1} {baslik}")
        w("")
        w("5 tekrar ortalaması; köşeli parantez içinde en düşük ve en yüksek tekrar.")
        w("")
        w("| Strateji | 24 s uyumu | BTK 24 s | TV 6 s | Bağlantı 12 s | 48 s | Birikim erime (gün) | Çağrı/gün (ops+tek.) | Boşa ziyaret | km/tek.-gün | Operasyon saat/gün | 24 s üstü açık (son hafta) |")
        w("|---|---|---|---|---|---|---|---|---|---|---|---|")
        for k in sira:
            v = d[k]
            w(f"| {'**' + KISA[k] + '**' if k == sira[0] else KISA[k]} | {_y(v['uyum_24s'])} [{_y(v['uyum_24s_min'])}-{_y(v['uyum_24s_max'])}] | "
              f"{_y(v['btk_24s'])} | {_y(v['tv_6s'])} | {_y(v['baglanti_12s'])} | {_y(v['uyum_48s'])} | {_erime(v['erime_gun'])} | "
              f"{_s(v['gunluk_arama'])} ({_s(v['ops_cagri'])}+{_s(v['tek_cagri'])}) | {_y(v['bosa_ziyaret_orani'])} | "
              f"{_s(v['km_teknisyen_gun'], 1)} | {_s(v['ops_saat'], 1)} | {_s(v['acik_24s_ustu_son_hafta'])} |")
        w("")

    w("## 6. Kadro taraması")
    w("")
    w("24 saat uyumu ve parantez içinde BTK 24 saat uyumu. 10, 16 ve 20 kişide 5 tekrar (tohum 101-105), diğer düzeylerde "
      "3 tekrar (tohum 201-203).")
    w("")
    Ns = [str(n) for n in J["meta"]["kadro_tarama"]]
    w("| Strateji | " + " | ".join(f"N={n}" for n in Ns) + " |")
    w("|---|" + "---|" * len(Ns))
    for k in sorted(kod, key=lambda k: (k == "BUGUN", -kad[k][Nref]["uyum_24s"])):
        w(f"| {KISA[k]} | " + " | ".join(f"{_y(kad[k][n]['uyum_24s'])} ({_y(kad[k][n]['btk_24s'])})" for n in Ns) + " |")
    w("")
    w("Birikim erime günü, kadroya göre:")
    w("")
    w("| Strateji | " + " | ".join(f"N={n}" for n in Ns) + " |")
    w("|---|" + "---|" * len(Ns))
    for k in sorted(kod, key=lambda k: (k == "BUGUN", -kad[k][Nref]["uyum_24s"])):
        w(f"| {KISA[k]} | " + " | ".join(_erime(kad[k][n]["erime_gun"]) for n in Ns) + " |")
    w("")
    esn = J.get("bolge_esnek", {})
    if esn:
        w(f"**BÖLGE için kontrol.** BÖLGE'nin düşük sonucu uygulama ayrıntısından mı kaynaklanıyor? Bunu sınamak için "
          f"takvim gevşetildi: boştaki teknisyen sonraki dilimi öne çekebiliyor ve cevapsız müşteriye 2 km'ye kadar "
          f"gidiliyor. Sonuç (BÖLGE-esnek): "
          + ", ".join(f"N={n}: {_y(v['uyum_24s'])} (BTK {_y(v['btk_24s'])})" for n, v in esn.items())
          + ". Sonuç iyileşiyor ama sıralama değişmiyor. Katı dilim takvimi, boştaki teknisyenin bekleyen işi "
          "alamaması demek (teknisyen başına günde 2-3 saat boşta).")
        w("")

    w(f"## 7. Duyarlılık ({Nref} teknisyen, 3 tekrar, tohum 201-203)")
    w("")
    w("Her satırda tek bir varsayım değişti, diğerleri referansta kaldı. Hücrelerde 24 saat uyumu ve parantez içinde BTK "
      "24 saat uyumu var.")
    w("")
    ks = sorted(yarisan, key=lambda k: -duy["referans"][k]["uyum_24s"]) + ["BUGUN"]
    w("| Senaryo | " + " | ".join(KISA[k] for k in ks) + " | 1. |")
    w("|---|" + "---|" * (len(ks) + 1))
    for ad, d in duy.items():
        sira = sorted(yarisan, key=lambda k: -d[k]["uyum_24s"])
        w(f"| {ad.replace('_', ' ')} | " + " | ".join(f"{_y(d[k]['uyum_24s'])} ({_y(d[k]['btk_24s'])})" for k in ks)
          + f" | {KISA[sira[0]]} |")
    w("")
    w(f"**Sıralama sağlamlığı ({toplam_sen} senaryo = 8 kadro + {toplam_sen - 8} duyarlılık).**")
    w("")
    w("- 24 s uyumunda birinci: " + ", ".join(f"{KISA[k]} {v}" for k, v in sorted(bir.items(), key=lambda x: -x[1])) + ".")
    w("- BTK 24 s uyumunda birinci: " + ", ".join(f"{KISA[k]} {v}" for k, v in sorted(btkbir.items(), key=lambda x: -x[1])) + ".")
    w("")
    ref = duy["referans"]

    def fark(ad, k):
        return duy[ad][k]["uyum_24s"] - ref[k]["uyum_24s"]

    w("**Sıralamayı değiştiren ve değiştirmeyen varsayımlar**")
    w("")
    w(f"1. **Kapasite/yük oranı** (teknisyen sayısı, giriş hacmi, evde yok oranı) KARMA ile HAM'ın yerini değiştiren tek "
      f"etken. Kapasite kıtken HAM'ın 'en eski önce' sırası domino etkisiyle çöküyor; KARMA yeni işlerin 24 saatini "
      f"korurken gecikmişleri kotayla eritiyor. Giriş %15 artınca KARMA {_y(duy['giris_+15%']['KARMA']['uyum_24s'])}, "
      f"HAM {_y(duy['giris_+15%']['HAM']['uyum_24s'])}. Evde yok %45 olunca KARMA {_y(duy['evde_yok_%45']['KARMA']['uyum_24s'])}, "
      f"HAM {_y(duy['evde_yok_%45']['HAM']['uyum_24s'])}. Kapasite bolken (giriş %15 az, evde yok %15) HAM bir iki puan önde.")
    sir = J["siralar"]
    top2 = sum(1 for v in sir.values() if set(v[:2]) == {"KARMA", "HAM"})
    ucuncu = defaultdict(int)
    sonuncu = defaultdict(int)
    for v in sir.values():
        ucuncu[v[2]] += 1
        sonuncu[v[-1]] += 1
    istisna = [k for k, v in sir.items() if set(v[:2]) != {"KARMA", "HAM"}]
    w(f"2. **İlk iki sıra neredeyse hiç değişmiyor.** {len(sir)} senaryonun {top2}'inde ilk iki KARMA ve HAM"
      + (f"; istisna {', '.join(istisna)} (orada HAM dördüncü, RPHT ikinci)" if istisna else "") + ". "
      + "Üçüncülük: " + ", ".join(f"{KISA[k]} {v}" for k, v in sorted(ucuncu.items(), key=lambda x: -x[1]))
      + ". Sonunculuk: " + ", ".join(f"{KISA[k]} {v}" for k, v in sorted(sonuncu.items(), key=lambda x: -x[1]))
      + " (BUGÜN hariç; U1H masa doyduğunda 10-12 kişide BÖLGE'nin de altına düşüyor).")
    w(f"3. **Telefonla çözülebilir pay** tüm stratejileri aynı yönde kaydırıyor (×0,6 ile ×1,3 arası). En duyarlı U1H: "
      f"{_y(duy['telefonla_cozulur_x0.6']['U1H']['uyum_24s'])} ile {_y(duy['telefonla_cozulur_x1.3']['U1H']['uyum_24s'])} arası. "
      f"Sıralamayı değiştirmiyor.")
    w(f"4. **Masa kapasitesi (operasyon kişi sayısı, arama hızı)** yalnız masa ağırlıklı stratejileri etkiliyor. 4 kişilik "
      f"masada U1H {_y(duy['operasyon_4_kisi']['U1H']['uyum_24s'])}, RPHT {_y(duy['operasyon_4_kisi']['RPHT']['uyum_24s'])}. "
      f"12 kişide U1H ancak {_y(duy['operasyon_12_kisi']['U1H']['uyum_24s'])}. HAM ve KARMA masaya az yük bindirdiği için "
      f"etkilenmiyor. BUGÜN'de ofis arama hızı düşerse uyum {_y(duy['arama_hizi_dusuk_verim0.6']['BUGUN']['uyum_24s'])} oluyor.")
    w(f"5. **Dışarıdaki müşterinin telefonu açma oranı (ρ)** teknisyenin gitmeden aramasının değerini belirliyor. ρ 0,1 ile "
      f"0,9 arasında sonuçlar ±1-2 puan oynuyor. Aramadan gitme avantajı, arayan stratejilerin ulaşılamayanı saatlerce "
      f"masada bekletmesinden geliyor; ρ'dan değil.")
    w(f"6. **Konum kalitesi:** konumsuz iş mahalle yerine ilçe merkezinde planlanırsa bir bölgeye yığılma oluyor. HAM "
      f"{_s(100 * fark('konumsuz_ilce_merkezi', 'HAM'), 0)} puan, KARMA {_s(100 * fark('konumsuz_ilce_merkezi', 'KARMA'), 0)} "
      f"puan etkileniyor. Adres metninden mahalle eşlemesi yapılması (yerel, ağ çağrısı yok) bu yüzden önemli.")
    w(f"7. **Elle günde 3 dışa aktarım (30 dk köprü yerine)** en çok RPHT'yi vuruyor "
      f"({_s(100 * fark('elle_3_aktarim', 'RPHT'), 0)} puan), çünkü 15-30 dakikalık BTK arama hedefi tutmuyor. KARMA "
      f"{_s(100 * fark('elle_3_aktarim', 'KARMA'), 0)} puan etkileniyor.")
    w(f"8. **SMS kanalı ve kurye** yalnız kendi stratejilerini etkiliyor. Kurye olmayınca U1H "
      f"{_s(100 * fark('kurye_yok', 'U1H'), 0)} puan kaybediyor. SMS kanalı yokken BÖLGE'de değişim ≤1 puan, çünkü BÖLGE'yi "
      f"geride bırakan etken kapasite takvimi.")
    w(f"9. **Trafik (20-35 km/sa)** ve **ulaşma oranı** düzeyi kaydırıyor, sıralamayı değiştirmiyor.")
    w("")

    w("## 8. Bulgular")
    w("")
    k16, h16, d16 = r16["KARMA"], r16["HAM"], r16["DSIR"]
    w("1. **Aramadan sevk, önce aramaktan hızlı.** Müşteriye ulaşamayan her strateji işi bir kuyruğa (istisna, "
      "merdiven, dilim) koyuyor ve iş orada saatlerce, bazen günlerce bekliyor. Habersiz ziyarette evde yok olasılığı "
      "~%22. Boşa giden ziyaretin maliyeti yaklaşık 20-25 dk (yol + 10 dk bekleme); bekleyen işin 24 saati kaçırma "
      "maliyeti ise çok daha büyük.")
    w(f"2. **Sıralama kuralı, kapasite kıtken belirleyici.** Kapasite yetmediğinde 'en eski önce' (FIFO) kuralı, 24 "
      f"saati zaten kaçmış işleri yapmakla yeni işleri de kaçırıyor (domino etkisi). 'Yetişir' kuralıyla KARMA, 10 "
      f"teknisyende HAM'dan {_s(100 * (r10['KARMA']['uyum_24s'] - r10['HAM']['uyum_24s']), 0)} puan önde. Gecikmiş işlere "
      f"kota ayrıldığı için birikim de {_erime(r10['KARMA']['erime_gun'])} günde eriyor; HAM'da erimiyor.")
    w(f"3. **BTK için masanın paralel teşhisi yararlı.** İş sahada sırasını beklerken masa bir kez arıyor; telefonla "
      f"çözülen iş hiç ziyaret edilmeden kapanıyor. Masa yükü {_s(k16['ops_saat'], 0)} kişi-saat/gün (≈4 kişi). "
      f"Sahayı bekleten 'önce masa' tasarımları (U1H, RPHT) bu kazancı gecikmeyle geri veriyor.")
    w(f"4. **Teknisyenin gitmeden araması net kayıp.** DSİR teknisyenleri günde {_s(d16['tek_cagri'])} arama yapıyor "
      f"(teknisyen başına ~{_s(d16['tek_cagri'] / (int(Nref) * 0.95), 0)}). Boşa ziyaret {_y(d16['bosa_ziyaret_orani'])}'ye iniyor, ama "
      f"ulaşılamayan iş istisna kuyruğunda bekliyor ve 24 saat uyumu {_y(d16['uyum_24s'])} kalıyor. Kural 'arama yap, "
      f"ulaşamazsan yine git' olsaydı da arama süresi kazancı yiyordu (tasarım denemelerinde −1,5 ile −3,5 puan).")
    w(f"5. **Takvime dayalı rezervasyon (BÖLGE) eşit kadroda en zayıf.** Beklenen birimle yapılan fazla rezervasyon, "
      f"geliş dalgalanmasında takvimi günler ötesine itiyor. Teknisyen kendi dilimi boşalınca bekleyen işi alamıyor ve "
      f"günde {_s(r16['BOLGE']['bos_dk_tek'])} dk boşta kalıyor. Tasarım da 34-38 kişi öngörüyordu.")
    w(f"6. **Hiçbir yöntem %90'a kadro olmadan ulaşmıyor.** KARMA'da 24 saat uyumu 20 kişide "
      f"{_y(kad['KARMA']['20']['uyum_24s'])}, 24 kişide {_y(kad['KARMA']['24']['uyum_24s'])}. Tavanı şunlar belirliyor: "
      f"müşterinin ileri gün istemesi, üç denemede ulaşılamayan müşteri, Pazar'ın yarım kadrosu ve akşam 17:00 sonrası "
      f"gelen işler (girişin ~%30'u). Turkcell FOX hedefleri (TV 6 s, Bağlantı 12 s) 20 kişide bile yaklaşık %50'de; "
      f"gece gelen işler için bu hedefler fiziksel olarak tutulamıyor.")
    w("7. **Bugünkü süreçte teknisyen eklemek yetmiyor.** Herkesi önce ofis aradığı ve ulaşılamayan iş teknisyene hiç "
      "gitmediği için darboğaz ofis araması. Modelde teknisyen sayısı artsa da uyum yerinde sayıyor.")
    w("")

    w("## 9. Önerilen işleyiş (KARMA kuralları)")
    w("")
    w("1. **Giriş.** BOSS ve FOX 08:00-20:00 arasında 30 dakikada bir içe aktarılır. Adında 'kurulum' geçen iş kapsam "
      "dışıdır ('Kurulum Taskı Ürememiş' hariç). Kanal Şikayeti ve Soru-Cevap masaya gider (hemen, +2 s ve akşam "
      "denemesi). Cihaz İade önce sistemde kontrol edilir, gerekirse aranır.")
    w("2. **Saha işi aranmadan kuyruğa girer.** İş, bölge teknisyeninin kuyruğuna doğrudan düşer. Randevu yalnız "
      "istisnada verilir: müşteri 'şimdi olmaz' derse, evde bulunamazsa ya da masa teşhisinde müşteri başka bir saat isterse.")
    w("3. **BTK'da paralel masa teşhisi.** İş sahadayken masa 30-45 dk içinde bir kez arar ve 10 dakikalık uzaktan "
      "teşhis yapar. Çözülürse iş kapanır. Şebeke arızası çıkarsa iş bekletilir. Müşteri şimdi müsait değilse randevu "
      "verilir. Ulaşılamazsa hiçbir şey yapılmaz, teknisyen zaten gidecek. Son 7 günde tekrar eden arızada telefonla "
      "kapatma yapılmaz.")
    w("4. **Sıralama: 'yetişir' kuralı.** Teknisyen her işi bitirince sıradaki işi şöyle seçer:")
    w("   - Önce penceresi açılan randevu.")
    w("   - Sonra 24 saatine hâlâ yetişebilecek işler, son tarih sırasıyla. BTK 6 saat, TV 2 saat daha öne alınır; yakınlık "
      "hafif ağırlıklıdır.")
    w("   - Sonra 24 saati kaçmış işler, en eski önce; BTK 12 saat öne alınır.")
    w("   - Teknisyenin aday listesinde 15 ya da daha fazla gecikmiş iş varsa (aşırı yük), gecikmiş işlere her 4. seçimde "
      "bir yer verilir. Yoksa sıra normal FIFO'dur: önce BTK, sonra en eski.")
    w("5. **Teknisyen gitmeden aramaz.** Müşteri evde değilse 10 dk bekler ve iş masaya düşer. Masa hemen, +2 saatte "
      "ve akşam arar; ulaşınca 'düzeldi mi' kontrolü yapar ya da randevu verir. Üç denemede ulaşılamazsa SMS gider ve "
      "iş ertesi gün yine habersiz ziyarete çıkar. İkinci boşa ziyaretten sonra 48 saat askı, bir son arama, sonra "
      "Turkcell kuralıyla kapatma.")
    w("6. **Şebeke kümesi.** 2 saat içinde aynı binada 3 ya da 300 m içinde 5 BTK işi gelirse NOC kontrolü yapılır. "
      "Arıza varsa işler bekletilir ve çözümde doğrulama aramasıyla kapatılır.")
    w(f"7. **Kaynak.** Masa ≈{_s(k16['ops_saat'], 0)} kişi-saat/gün (4-5 kişi), teknisyen ≈{_s(k16['km_teknisyen_gun'], 0)} "
      f"km/gün. Kadro hedefi: hafta içi 16 aktif teknisyenle ~{_y(kad['KARMA']['16']['uyum_24s'])}, 20 ile "
      f"~{_y(kad['KARMA']['20']['uyum_24s'])}. Kadro 20'yi geçip kapasite bollaşınca katı 'önce BTK, sonra en eski' "
      "sırasına (HAM) geçmek BTK'da 2-4 puan kazandırır; KARMA'nın aşırı yük eşiği bu geçişi yalnız kısmen yapıyor.")
    w("")

    w("## 10. Varsayımlar")
    w("")
    w("| Parametre | Değer | Kaynak | Taranan aralık |")
    w("|---|---|---|---|")
    for ad, v in J["varsayimlar"].items():
        w(f"| {v.get('ad', ad)} | {v.get('deger', '')} | {v.get('kaynak', '')} | {v.get('aralik', '-')} |")
    w("")
    w("İlk hafta pilotta ölçülmesi gerekenler:")
    w("")
    w("- Habersiz ziyarette evde yok oranı.")
    w("- İlk aramada ulaşma oranı.")
    w("- Masa uzaktan teşhisinin çözme oranı.")
    w("- Telefonla kapatılan işin 7 günlük tekrar oranı.")
    w("- Teknisyen başına ziyaret/gün.")
    w("")
    w("Bu ölçümler `varsayilan()` içine yazılıp simülasyon yeniden koşulabilir.")
    w("")

    w("## 11. Sınırlamalar")
    w("")
    w("- **Rota planı.** Rota eniyilemesi (zaman pencereli araç rotalama) yok. Teknisyen her iş sonunda kuralına göre "
      "tek bir iş seçiyor. Pencere ağırlıklı stratejiler (U1H, BÖLGE) gerçek bir rota planlayıcıyla biraz daha iyi "
      "sonuç alabilir; BÖLGE-esnek kontrolü bu payın sıralamayı değiştirmediğini gösteriyor.")
    w("- **Kapsam.** Yalnız metro. Uzak ilçelerin yerel teknisyenleri ve kurulum ekipleriyle kaynak paylaşımı modellenmedi.")
    w("- **Veri kaynağı.** Telefonla çözülebilirlik ve yerinde süre, kapanmış işlerin toplu sayımından geliyor "
      "(TAMAMLANDI; bu istekte eklenmedi, önceki analiz toplu parametre olarak kullandı). Bu dosyaya burada doğrudan "
      "erişilmedi.")
    w("- **Ölçülmemiş davranış.** Müşteri davranışı (sınıf payları, ρ, evde yok) ölçülmedi; aralıklarla tarandı.")
    w(f"- **Başlangıç birikimi.** Kullanıcının 18:21 dışa aktarımı kullanıldı; {J['meta']['birikim_baslangic']} metro satırı "
      f"alındı, metro dışı {J['meta']['birikim_atlanan'].get('metro_disi', 0)} satır atlandı. Bu dışa aktarımda Cihaz İade ve "
      "2.Donanım yok, ama yeni gelişlerde bu tipler var. 16:45 anlık görüntüsündeki 953 işlik birikimle erime süreleri uzar.")
    w("- **Turkcell kuralları.** Askıdayken SLA saati duruyor mu, ulaşılamayan iş kaç denemede kapatılır? Bunlar teyit "
      "edilmedi. Modelde saat hep işliyor; 5-6 başarısız temastan sonra kapatılıyor.")
    w("")
    w("## 12. Dosyalar ve çalıştırma")
    w("")
    w("- `operasyon/analiz/simulasyon.py`: model, stratejiler, deneyler.")
    w("  - `python simulasyon.py`: tam set, 16 çekirdekte ~10 dk.")
    w("  - `--hizli`: kısa deneme.")
    w("  - `--tek KARMA 16`: tek koşu.")
    w("  - `--md`: raporu JSON'dan yeniden yazar.")
    w("- `operasyon/analiz/cikti/simulasyon.json`: bütün ortalamalar, en düşük ve en yüksek tekrar, günlük seriler, "
      "kadro taraması, duyarlılık ve sıralamalar.")
    w("- Gizlilik: çıktılarda yalnız toplu sayılar var. Müşteri, task ya da lokasyon kimliği, adres, telefon ya da kişi "
      "adı yok.")
    w("")
    return "\n".join(L)



# ================================================================== HAKEM1 EKLERİ
class HamPlus(Karma):
    """Ayrıştırma kontrolü: KARMA'nın TÜM eklentileri (paralel BTK masa teşhisi, NOC küme kontrolü, altyapı
    bayrağı, ulaşılamayan merdiveni) AMA sıralama her zaman HAM'ınki (önce BTK, sonra en eski; ilk 5'ten en yakın).
    KARMA ile farkı yalnız 'yetişir' sıralamasının etkisini ölçer."""
    ad = "HAM+ (KARMA eklentileri + HAM sıralaması)"
    kod = "HAMPLUS"
    siralama = "ham"
    asiri_yuk_esigi = None


class KarmaY(Karma):
    """Ayrıştırma kontrolü: her zaman 'yetişir' (aşırı yük eşiği yok)."""
    ad = "KARMA-Y (her zaman yetişir)"
    kod = "KARMA_Y"
    siralama = "yetisir"
    asiri_yuk_esigi = None


class HakemA(HamPlus):
    """HAM+ sadeleştirilmiş: masa teşhisi yalnız KAPATMAK için. Teşhiste çözülmeyen iş havuzda habersiz kalır
    (müşteri açıkça 'başka gün' demedikçe randevu verilmez); kaçan randevu havuzda kalır (HAM gibi);
    ulaşılamayan merdiveni HAM'ınki. Bayraklar ablasyon için ayrı ayrı açılıp kapatılabilir."""
    ad = "HAKEM-A (HAM sırası + yalnız-kapatan BTK teşhisi + NOC)"
    kod = "HAKEM_A"
    teshis_randevu = False     # teşhiste 'şimdi müsait değil' -> randevu (KARMA: True)
    karma_merdiven = False     # KARMA'nın 'ertesi gün yine habersiz' merdiveni (False = HAM merdiveni)
    karma_kacan = False        # kaçan randevu -> masa istisna (KARMA) | havuzda kal (HAM)

    def masa_sonuc(self, g, sonuc, t):
        j = g.j
        m = self.m
        if g.amac == "teshis" and not self.teshis_randevu:
            if j.state != "SAHA":
                return None
            if sonuc == "cevapsiz":
                return None
            r = m.cozum(j, t, "teshis")
            if r == "cozuldu":
                m.kapat(j, t, "tel_masa")
            elif r == "sebeke":
                m.beklet(j, max(j.tau, t + 30), self._dogrula)
            elif j.tercih == 2:
                m.randevu_ver(j, t, lead=60)          # müşteri açıkça ileri gün istedi
            elif m.simdi_musait(j, t):
                j.teyit = "teyitli"
            return 10.0
        return super().masa_sonuc(g, sonuc, t)

    def _sonraki(self, j, t):
        if self.karma_merdiven or j.kanal in ("MASA", "LOJ"):
            return super()._sonraki(j, t)
        m = self.m
        j.deneme += 1
        k = j.deneme
        if k == 1:
            m.masa_ekle(j, "istisna", t + 120, oncelik=2 if j.btk else 3)
        elif k == 2:
            m.masa_ekle(j, "istisna", sabah(t, 600), oncelik=2 if j.btk else 3)
        elif k == 3:
            m.sms(j, t)
            m.beklet(j, t + 2 * GUN, self._son_deneme)
        else:
            m.kapat(j, t, "ulasilamadi")

    def kacan_randevu(self, j, t):
        if self.karma_kacan:
            return super().kacan_randevu(j, t)
        j.pencere = None
        j.teyit = "habersiz"


class HakemB(HakemA):
    """HAKEM-B: HAKEM-A + aşırı yükte 'BTK-katı yetişir'. Sınıf sırası: (1) 24 saatine yetişecek BTK (son tarih
    sırası, TV 2 s öne) (2) gecikmiş BTK (en eski önce) (3) yetişecek BTK dışı (son tarih) (4) gecikmiş BTK dışı
    (en eski). Her sınıfta ilk 5'ten en yakını (yol verimi). Gecikmiş BTK, yetişecek BTK varken her 'q_btk'.
    seçimde bir kez; gecikmiş BTK dışı, yetişecek BTK dışı varken her 'q_diger'. seçimde bir kez alınır
    (açlık koruması). Aşırı yük yoksa HAM sırası."""
    ad = "HAKEM-B (BTK-katı yetişir + açlık koruması + ilk-5-en-yakın)"
    kod = "HAKEM_B"
    asiri_yuk_esigi = 15
    q_btk = 3
    q_diger = 4
    ust_k = 5

    def _sec1(self, tkn, t, pool, d):
        m = self.m
        j = m.pencere_sec(tkn, t, pool, d)
        if j is not None:
            return j
        idx = [i for i, x in enumerate(pool) if x.pencere is None]
        if not idx:
            return None
        n_gec = sum(1 for i in idx if t - pool[i].t0 >= GUN)
        if self.asiri_yuk_esigi is not None and n_gec < self.asiri_yuk_esigi:
            order = sorted(idx, key=lambda i: (not pool[i].btk, pool[i].t0))[:5]
            return pool[min(order, key=lambda i: d[i])]
        tr = m.yol_dk_vec(d)

        def yetisir(i):
            return t + tr[i] + 30 < pool[i].t0 + GUN

        def en_yakin(L, key):
            L = sorted(L, key=key)[:self.ust_k]
            return pool[min(L, key=lambda i: d[i])]

        tkn.sayac += 1
        for btk_sinif, q in ((True, self.q_btk), (False, self.q_diger)):
            S = [i for i in idx if bool(pool[i].btk) == btk_sinif]
            if not S:
                continue
            Y = [i for i in S if yetisir(i)]
            G = [i for i in S if not yetisir(i)]
            if G and (not Y or tkn.sayac % q == 0):
                return en_yakin(G, key=lambda i: pool[i].t0)
            if Y:
                return en_yakin(Y, key=lambda i: pool[i].t0 + GUN - (120 if pool[i].tip == "TV_ARIZA" else 0))
        return None


class AblR(HakemA):
    """Ablasyon: HAKEM-A + KARMA'nın 'teşhiste şimdi müsait değil -> randevu' kuralı."""
    ad = "ABL-R (HAKEM-A + teşhis randevusu)"
    kod = "ABL_R"
    teshis_randevu = True


class AblM(HakemA):
    """Ablasyon: HAKEM-A + KARMA'nın ulaşılamayan merdiveni (ertesi gün yine habersiz ziyaret)."""
    ad = "ABL-M (HAKEM-A + KARMA merdiveni)"
    kod = "ABL_M"
    karma_merdiven = True


class AblK(HakemA):
    """Ablasyon: HAKEM-A + KARMA'nın 'kaçan randevu -> masa istisna' kuralı."""
    ad = "ABL-K (HAKEM-A + kaçan randevu masaya)"
    kod = "ABL_K"
    karma_kacan = True


class KarmaD(HakemA):
    """KARMA'nın 'yetişir' sıralaması (aşırı yük eşiği 15, gecikmişe her 4. seçim) + HAKEM-A masa düzeltmeleri.
    KARMA ile farkı yalnız masa katmanının etkisini, HAKEM-B ile farkı yalnız sıralamanın etkisini ölçer."""
    ad = "KARMA-D (KARMA sırası + yalnız-kapatan teşhis)"
    kod = "KARMA_D"
    siralama = "yetisir"
    asiri_yuk_esigi = 15


class HakemBA(HakemB):
    """Aşı denemesi: HAKEM-B + %15 akşam vardiyası (12:00-21:00; DSİR/U1H'den)."""
    ad = "HAKEM-B + %15 akşam"
    kod = "HAKEM_BA"
    aksam_oran = 0.15


HAKEM_STRATEJI = {"HAKEM_BA": HakemBA, "HAMPLUS": HamPlus, "KARMA_Y": KarmaY, "HAKEM_A": HakemA, "HAKEM_B": HakemB,
                  "ABL_R": AblR, "ABL_M": AblM, "ABL_K": AblK, "KARMA_D": KarmaD}
TUM_STRATEJI.update(HAKEM_STRATEJI)

HAKEM_METRIK = ["uyum_24s", "btk_24s", "btk_gercek_24s", "tum_gercek_24s", "sebeke_erken_kapanis", "uyum_24s_kararli", "uyum_48s", "tv_6s", "baglanti_12s", "k_uyum_72s", "k_asim_72s", "k_asim_7g",
                "k_ort_saat", "k_p90_saat", "k_gecikme_saat", "k_gercek_24s", "k_acik_kalan", "kb_uyum_24s",
                "kb_uyum_48s", "kb_asim_72s", "kb_ort_saat", "kb_gecikme_saat", "kb_p90_saat", "acik24_son",
                "acik24_egim_gun", "acik_24s_ustu_son_hafta", "erime_gun", "kapanis", "ziyaret", "ziyaret_tek",
                "km_teknisyen_gun", "bos_dk_tek", "bosa_ziyaret_orani", "ops_saat", "gunluk_arama", "ulasilamadi_kapanis",
                "erteleme_haric_24s"]


def hakem_calistir(kodlar, Nler, tohumlar, deg=None, etiket="hakem", isci=None):
    V = veri_yukle()
    L = [(etiket, k, N, s, deg) for N in Nler for k in kodlar for s in tohumlar]
    isci = isci or max(1, (os.cpu_count() or 4) - 1)
    t1 = time.time()
    with ProcessPoolExecutor(isci, initializer=_init, initargs=(V,)) as ex:
        sonuc = list(ex.map(gorev, L, chunksize=1))
    grup = defaultdict(list)
    for r in sonuc:
        grup[(r["kod"], r["N"])].append(r)
    out = {}
    for (k, N), rs in grup.items():
        o = {}
        for m in HAKEM_METRIK:
            v = [r[m] for r in rs if r.get(m) is not None]
            if not v:
                o[m] = None
                continue
            o[m] = float(np.median(v)) if m == "erime_gun" else float(np.mean(v))
            if m in ("uyum_24s", "btk_24s", "k_gecikme_saat"):
                o[m + "_min"], o[m + "_max"] = float(min(v)), float(max(v))
        o["n_tekrar"] = len(rs)
        o["acik24_seri"] = np.mean([r["acik24_seri"] for r in rs], axis=0).round(1).tolist()
        out.setdefault(str(N), {})[k] = o
    return out, time.time() - t1


def hakem_main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--kod", nargs="+", default=["KARMA", "HAM", "HAMPLUS", "KARMA_Y"])
    ap.add_argument("--N", nargs="+", type=int, default=[10, 12, 14, 16, 18, 20])
    ap.add_argument("--tohum", nargs="+", type=int, default=TOHUM_ANA)
    ap.add_argument("--etiket", default="hakem")
    ap.add_argument("--deg", default=None, help="JSON: parametre değişikliği")
    ap.add_argument("--isci", type=int, default=None)
    a = ap.parse_args(argv)
    deg = json.loads(a.deg) if a.deg else None
    if deg:
        deg = {k: (tuple(v) if isinstance(v, list) else v) for k, v in deg.items()}
    out, sure = hakem_calistir(a.kod, a.N, a.tohum, deg, a.etiket, a.isci)
    os.makedirs(CIKTI, exist_ok=True)
    yol = os.path.join(CIKTI, f"{a.etiket}.json")
    json.dump(_yuvarla(dict(etiket=a.etiket, kodlar=a.kod, N=a.N, tohumlar=a.tohum, deg=a.deg, sure_s=round(sure, 1),
                            sonuc=out)), open(yol, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
    goster = ["uyum_24s", "btk_24s", "uyum_48s", "k_uyum_72s", "k_asim_7g", "k_ort_saat", "k_gecikme_saat",
              "kb_gecikme_saat", "acik24_son", "acik24_egim_gun", "kapanis", "km_teknisyen_gun"]
    print(f"{yol}  ({sure:.0f} s)")
    print("N   kod        " + " ".join(f"{m[:12]:>12}" for m in goster))
    for N in a.N:
        for k in a.kod:
            o = out[str(N)][k]
            print(f"{N:<3} {k:<10} " + " ".join(f"{(o[m] if o[m] is not None else float('nan')):12.3f}" for m in goster))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--hakem":
        hakem_main(sys.argv[2:])
    else:
        main()
