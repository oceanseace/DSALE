"""STRATEJİ: UZAKTAN-ÖNCE HUNİ (U1H) -- mevcut müşteri iş emirleri için simülasyon.

Fikir: Kurulum dışındaki her iş, geldiği andan itibaren 1-2 saat içinde bir
"Uzaktan Çözüm Masası"ndan (UÇM) geçer: sistem ön kontrolü -> arama merdiveni
-> senaryolu uzaktan teşhis -> (uzaktan kapat | şebeke beklet | kurye/bayiden
teslim | iptal | teyitli 2 saatlik dilimle sahaya ver | dolgu durağı).
Sahaya yalnız uzaktan çözülemeyen ve müşterisi teyitli iş iner; boşalan saha
kapasitesi BTK'ya ve birikime gider.

Bu dosya kuralları KOD olarak tanımlar ve 28 günlük iş-seviyesi Monte Carlo
simülasyonuyla sınar. Parametrelerin kaynağı:
  - cikti/is_emri_analizi.json (giriş hızı, varış saati profili, tip payları,
    kapanış nedenleri, teknisyen verimi, birikim kovaları)  -> VERİ
  - aşağıda VARSAYIM diye işaretli değerler ölçülmedi; pilotta ölçülecek.

Kişisel veri YOK: yalnız toplu oranlar/sayılar kullanılır.
Ağ çağrısı YOK.

Çalıştırma:
  .venv/Scripts/python.exe operasyon/analiz/strateji_uzaktan_once.py
Çıktı:
  operasyon/analiz/cikti/strateji_uzaktan_once.json
"""

from __future__ import annotations

import heapq
import json
import math
from datetime import date, timedelta
from pathlib import Path

import numpy as np

BURASI = Path(__file__).resolve().parent
ANALIZ = BURASI / "cikti" / "is_emri_analizi.json"
CIKTI = BURASI / "cikti" / "strateji_uzaktan_once.json"

A = json.loads(ANALIZ.read_text(encoding="utf-8"))
PAR = A["parametreler"]

# ---------------------------------------------------------------------------
# 1. GİRİŞ (VERİ)
# ---------------------------------------------------------------------------
GUN_ADI = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]
GUN_ORT = A["giris"]["mevcut_gelen_haftanin_gunu_ort"]          # mevcut müşteri/gün
VARIS = np.array([A["giris"]["mevcut_varis_saat_profili"][str(h)] for h in range(24)], float)
VARIS = VARIS / VARIS.sum()
TIP_PAY = dict(A["giris"]["mevcut_tip_payi"])
IKINCI_DONANIM_GUN = PAR["ikinci_donanim_giris_alt_sinir_gunluk"]   # 5.43/gün (alt sınır)
BASLANGIC = date(2026, 9, 30)                                     # simülasyon 1. günü (Çarşamba)

# ---------------------------------------------------------------------------
# 2. TİP KURALLARI
#   btk      : BTK'ya sayılan arıza (öncelikli şerit)
#   tsl      : Turkcell FOX hedef saati (bayi hedefi = min(tsl, 24))
#   masa_dk  : ulaşılan müşteride masa işlem süresi (dk)  [VARSAYIM]
#   saha_dk  : saha ziyareti (yol+iş) dk. VERİ vekili: ardışık kapanış p50 31 dk,
#              gerçek ziyaret ~38-40 dk (telefonla kapanışlar ayıklanınca)
#   sistem   : aramadan önce sistemden kapanabilme olasılığı (Cihaz İade uzlaştırma) [VARSAYIM]
#   p        : müşteriye ulaşıldığında sonuç dağılımı.
#              BTK için VERİ: TAMAMLANDI 3-15 Eylül Arıza Nedeni -> telefon/uzaktan
#              Bağlantı %28,6 / TV %34,1 / Doping %33,7; şebeke %11,2 / %14,3 / %15,1.
#              Erken aramada 'düzeldi' daha az yakalanır -> telefon payı ~%10 kırpıldı.
#              Kurye kabulü, iptal oranı: VARSAYIM.
# ---------------------------------------------------------------------------
TIPLER = {
    "BAGLANTI":          dict(btk=1, tsl=12, masa_dk=10, saha_dk=40, p=dict(uzaktan=.26, sebeke=.10, saha=.64)),
    "TV_ARIZA":          dict(btk=1, tsl=6,  masa_dk=10, saha_dk=40, p=dict(uzaktan=.30, sebeke=.12, saha=.58)),
    "DOPING_ARIZA":      dict(btk=1, tsl=24, masa_dk=10, saha_dk=40, p=dict(uzaktan=.30, sebeke=.13, saha=.57)),
    "ARAMA":             dict(btk=1, tsl=12, masa_dk=10, saha_dk=40, p=dict(uzaktan=.25, sebeke=.10, saha=.65)),
    "KANAL_SIKAYETI":    dict(btk=0, tsl=24, masa_dk=4,  saha_dk=40, p=dict(uzaktan=.97, saha=.03)),
    "CIHAZ_IADE":        dict(btk=0, tsl=24, masa_dk=4,  saha_dk=12, sistem=.60, p=dict(kurye=.55, dolgu=.45)),
    "MODEM_DEGISIKLIGI": dict(btk=0, tsl=24, masa_dk=6,  saha_dk=35, p=dict(kurye=.35, saha=.65)),
    "SUPERBOX_MODEM":    dict(btk=0, tsl=24, masa_dk=6,  saha_dk=35, p=dict(kurye=.70, saha=.30)),
    "STB_DEGISIKLIGI":   dict(btk=0, tsl=24, masa_dk=6,  saha_dk=35, p=dict(kurye=.50, saha=.50)),
    "UCRETLENDIRME":     dict(btk=0, tsl=24, masa_dk=5,  saha_dk=40, p=dict(iptal=.15, saha=.85)),
    "EVRAK_SOSYAL":      dict(btk=0, tsl=24, masa_dk=3,  saha_dk=12, p=dict(dolgu=1.0)),
    "EVRAK_TURKSAT":     dict(btk=0, tsl=24, masa_dk=3,  saha_dk=12, p=dict(dolgu=1.0)),
    "CIHAZ_GERI_ALIM":   dict(btk=0, tsl=48, masa_dk=4,  saha_dk=12, p=dict(kurye=.80, dolgu=.20)),
    "TURKSAT_CIHAZ_IADE": dict(btk=0, tsl=24, masa_dk=4, saha_dk=12, p=dict(kurye=.50, dolgu=.50)),
    "SORU_CEVAP":        dict(btk=0, tsl=24, masa_dk=5,  saha_dk=40, p=dict(uzaktan=.90, saha=.10)),
    "UCRETSIZ_KUMANDA":  dict(btk=0, tsl=24, masa_dk=3,  saha_dk=12, p=dict(kurye=1.0)),
    "TV_KURULUM":        dict(btk=0, tsl=24, masa_dk=5,  saha_dk=60, p=dict(saha=1.0)),
    "IKINCI_DONANIM":    dict(btk=0, tsl=24, masa_dk=5,  saha_dk=50, p=dict(saha=1.0)),
}

# ---------------------------------------------------------------------------
# 3. STRATEJİ PARAMETRELERİ (kural sabitleri)
# ---------------------------------------------------------------------------
TEMEL = dict(
    # --- Arama merdiveni ---
    ulasma=[0.55, 0.40, 0.35, 0.45, 0.45, 0.30],   # deneme k'da ulaşma olasılığı [VARSAYIM; pilotta ölç]
    birikim_ulasma_carpan=0.85,                     # eski işte ulaşma daha düşük [VARSAYIM]
    deneme_arasi_dk=[30, 90],                       # 1->2: +30 dk (SMS ile), 2->3: +90 dk
    aksam_deneme_saat=17.5,                         # 4. deneme 17:30-20:00
    sabah_deneme_saat=8.25,                         # 5. deneme ertesi 08:15
    aski_uyandirma_saat=48,                         # askı -> 48 s sonra 6. deneme
    basarisiz_dk=1.5, dogrulama_dk=3, kurye_destek_dk=8, sistem_dk=2,
    tekrar_orani_btk=0.25,                          # 7 gün içinde tekrar arıza payı (VERİ %34,8/15 gün -> ~%25/7 gün)
    uzaktan_ek_tekrar=0.08,                         # uzaktan kapanan BTK'da ek tekrar riski [VARSAYIM]
    birikim_btk_uzaktan_ek=0.10,                    # 72 s+ eski BTK'da 'düzeldi' olasılığı artar [VARSAYIM]
    # --- Masa (UÇM) kadrosu: vardiya A 08:00-16:30, B 12:30-21:00 ---
    masa_A={"hi": 6, "Cmt": 5, "Paz": 2}, masa_B={"hi": 4, "Cmt": 3, "Paz": 2},
    masa_doluluk=0.85,
    # --- Saha: arıza ekibi (VERİ: 12 kişi, günlük aktif p50 10, Pazar 4-8) ---
    saha_gunduz={"hi": 7, "Cmt": 7, "Paz": 4},      # 08:30-18:30  (VERİ: arıza ekibi 12, günlük aktif p50 10)
    saha_gec={"hi": 3, "Cmt": 3, "Paz": 1},         # 11:00-21:00 (akşam dilimi + BTK)
    saha_verim=0.90,                                # mola payı
    esnek_havuz=0,                                  # sabit mod: kurulumdan ödünç teknisyen (hafta içi, 08:30-18:30)
    esnek_havuz_gun=28,                             # sabit mod: esnek havuz kaç gün
    esnek_birikim_oncelik=True,                     # esnek havuz önce birikimi eritir
    esnek_dinamik=False,                            # True: her sabah 07:45 formülle esnek sayısı
    esnek_max={"hi": 0, "Cmt": 0, "Paz": 0},        # dinamik mod üst sınırı
    saha_dk_is_tahmin=22.0,                         # yeni iş başına beklenen saha dk (S0 simülasyonundan)
    btk_bonus_dk=240,                               # saha sırası: anahtar = son_tarih - BTK bonusu
    bosa_teyitli=0.05, bosa_teyitsiz=0.35, bosa_dk=20,
    tercih=dict(en_erken=.65, aksam=.20, yarin=.15),  # teyitli müşterinin dilim tercihi [VARSAYIM]
    min_hazirlik_dk_btk=60, min_hazirlik_dk=120,
    # --- Kurye / bayiden teslim ---
    kurye_kapasite_gun=40, kurye_son_saat=16, kurye_sure_dk=150, kurye_destek_basari=0.90,
    # --- Şebeke bekletme (genel arıza) çözülme süresi: lognormal medyan 6 s [VARSAYIM] ---
    sebeke_medyan_saat=6.0, sebeke_sigma=0.8,
    # --- BTK uzaktan çözüm verimi çarpanı (duyarlılık için) ---
    uzaktan_carpan=1.0, kurye_carpan=1.0,
    ziyaret_dk_carpan=1.0,                          # küme rotası ile ziyaret süresi kısalırsa (<1)
    gun=28,
)

BIRIKIM = {   # VERİ: birikim.tip_x_aksiyon (mevcut müşteri, 29.09.2026)
    "A": {"BAGLANTI": 161, "TV_ARIZA": 40, "DOPING_ARIZA": 19, "ARAMA": 2, "MODEM_DEGISIKLIGI": 54,
          "IKINCI_DONANIM": 99, "UCRETLENDIRME": 15, "EVRAK_SOSYAL": 12, "EVRAK_TURKSAT": 1,
          "CIHAZ_GERI_ALIM": 5, "STB_DEGISIKLIGI": 4, "SUPERBOX_MODEM": 2, "TURKSAT_CIHAZ_IADE": 1},
    "C": {"KANAL_SIKAYETI": 179, "CIHAZ_IADE": 218},
    "B": {"BAGLANTI": 71, "TV_ARIZA": 18, "UCRETLENDIRME": 9, "MODEM_DEGISIKLIGI": 4, "EVRAK_SOSYAL": 2,
          "EVRAK_TURKSAT": 3, "STB_DEGISIKLIGI": 1, "SUPERBOX_MODEM": 3, "TURKSAT_CIHAZ_IADE": 1,
          "IKINCI_DONANIM": 26},
    "E": {"BAGLANTI": 2, "ARAMA": 1},
}
BIRIKIM_YAS_SAAT = {"<24s": 12, "24-48s": 36, "48-72s": 60, "3-7g": 120, "7-30g": 400, ">30g": 800}

ADIM = 15  # dk


def _gun_tipi(gun_idx: int) -> str:
    wd = (BASLANGIC + timedelta(days=gun_idx)).weekday()
    return "Paz" if wd == 6 else ("Cmt" if wd == 5 else "hi")


def _saat(t):
    return (t % 1440) / 60.0


def simule(P: dict, tohum: int) -> dict:
    rng = np.random.default_rng(tohum)
    GUN = P["gun"]
    UFUK = (GUN + 3) * 1440
    isler: list[dict] = []
    olay: list = []          # masa eylem kuyruğu: (zaman, sıra, iş_id, eylem)
    sira = [0]

    def ekle_is(tip, varis, birikim=False, yas_saat=0.0, tekrar=False, aski=False):
        T = TIPLER[tip]
        j = dict(id=len(isler), tip=tip, btk=T["btk"], varis=varis - yas_saat * 60, geldi=varis,
                 birikim=birikim, tekrar=tekrar, k=0, kapanis=None, sonuc=None, saha_hazir=None,
                 teyitli=False, ziyaret=0, bosa=0, yol=None, aski=aski, ertelendi=False)
        isler.append(j)
        return j

    def masa(j, zaman, eylem):
        sira[0] += 1
        heapq.heappush(olay, (zaman, sira[0], j["id"], eylem))

    # --- yeni giriş üret ---
    tip_ad = [t for t in TIP_PAY if TIP_PAY[t] > 0 and t in TIPLER]
    tip_p = np.array([TIP_PAY[t] for t in tip_ad]); tip_p /= tip_p.sum()
    for g in range(GUN + 3):
        wd = (BASLANGIC + timedelta(days=g)).weekday()
        n = rng.poisson(GUN_ORT[GUN_ADI[wd]])
        n2 = rng.poisson(IKINCI_DONANIM_GUN)
        saatler = rng.choice(24, size=n + n2, p=VARIS)
        tipler = list(rng.choice(tip_ad, size=n, p=tip_p)) + ["IKINCI_DONANIM"] * n2
        for s, tip in zip(saatler, tipler):
            t = g * 1440 + int(s) * 60 + int(rng.integers(0, 60))
            tekrar = bool(TIPLER[tip]["btk"] and rng.random() < P["tekrar_orani_btk"])
            j = ekle_is(tip, t, tekrar=tekrar)
            masa(j, t, "sistem" if "sistem" in TIPLER[tip] else "temas")

    # --- birikim (t=0 anında içeride) ---
    yas_kovalari = A["birikim"]["tip_x_yas"]
    for kova, d in BIRIKIM.items():
        for tip, n in d.items():
            yk = yas_kovalari.get(tip, {"3-7g": 1})
            ad = [k for k in yk if yk[k] > 0] or ["3-7g"]
            pr = np.array([yk[k] for k in ad], float); pr /= pr.sum()
            for _ in range(n):
                yas = BIRIKIM_YAS_SAAT[rng.choice(ad, p=pr)]
                j = ekle_is(tip, 0, birikim=True, yas_saat=yas, aski=(kova == "B"))
                masa(j, int(rng.integers(0, 60)), "sistem" if "sistem" in TIPLER[tip] else "temas")

    saha_kuyruk: list[int] = []
    kurye_kullanim: dict[int, int] = {}
    ekstra_tekrar = []

    def kapat(j, t, sonuc):
        j["kapanis"] = t; j["sonuc"] = sonuc
        if j["btk"] and sonuc == "uzaktan" and rng.random() < P["uzaktan_ek_tekrar"]:
            ekstra_tekrar.append((t + int(rng.uniform(1, 7) * 1440), j["tip"]))

    def sahaya(j, t, teyitli, tercih_uygula=True):
        j["teyitli"] = teyitli
        hz = P["min_hazirlik_dk_btk"] if j["btk"] else P["min_hazirlik_dk"]
        basla = t + hz
        if teyitli and tercih_uygula:
            r = rng.random(); tp = P["tercih"]
            gun0 = (t // 1440) * 1440
            if r < tp["en_erken"]:
                pass
            elif r < tp["en_erken"] + tp["aksam"]:
                basla = max(basla, gun0 + 17 * 60 if _saat(t) < 16 else gun0 + 1440 + 17 * 60)
                if _saat(t) >= 16: j["ertelendi"] = True
            else:
                basla = max(basla, gun0 + 1440 + 9 * 60)
                j["ertelendi"] = True
        j["saha_hazir"] = basla
        saha_kuyruk.append(j["id"])

    def sonraki_deneme(j, t):
        """Ulaşılamadı -> merdivenin bir sonraki basamağı."""
        k = j["k"]
        gun0 = (t // 1440) * 1440
        if k == 1:
            masa(j, t + P["deneme_arasi_dk"][0], "temas")
        elif k == 2:
            masa(j, t + P["deneme_arasi_dk"][1], "temas")
        elif k == 3:
            if j["btk"] and j["ziyaret"] == 0:
                sahaya(j, t, teyitli=False)          # BTK: 3 deneme sonra teyitsiz dolgu ziyareti
                # teyitsiz ziyaret boşa düşerse akşam denemesiyle devam eder
                return
            aksam = gun0 + int(P["aksam_deneme_saat"] * 60)
            masa(j, aksam if t < aksam + 150 - 60 else gun0 + 1440 + int(P["sabah_deneme_saat"] * 60), "temas")
        elif k == 4:
            masa(j, gun0 + 1440 + int(P["sabah_deneme_saat"] * 60), "temas")
        elif k == 5:
            j["aski"] = True                           # E2 abone kaynaklı askı + SMS
            masa(j, t + P["aski_uyandirma_saat"] * 60, "temas")
        else:
            kapat(j, t, "ulasilamadi_kapat")          # Turkcell kuralıyla 'ulaşılamadı' kapanış

    def ulasildi(j, t):
        T = TIPLER[j["tip"]]
        p = dict(T["p"])
        if j["btk"]:
            p["uzaktan"] = p.get("uzaktan", 0) * P["uzaktan_carpan"]
            if j["birikim"] and (j["geldi"] - j["varis"]) >= 72 * 60:
                p["uzaktan"] += P["birikim_btk_uzaktan_ek"]
            if j["tekrar"]:
                p["saha"] = p.get("saha", 0) + p.pop("uzaktan", 0)   # E6: tekrar arıza telefonla kapanmaz
        if "kurye" in p and P["kurye_carpan"] != 1.0:
            yeni = p["kurye"] * P["kurye_carpan"]
            fark = p["kurye"] - yeni
            p["kurye"] = yeni
            p["saha" if "saha" in p else "dolgu"] = p.get("saha" if "saha" in p else "dolgu", 0) + fark
        toplam = sum(p.values()); ad = list(p); pr = np.array([p[a] for a in ad]) / toplam
        sonuc = rng.choice(ad, p=pr)
        j["yol"] = str(sonuc)
        if sonuc in ("uzaktan", "iptal"):
            kapat(j, t, str(sonuc))
        elif sonuc == "sebeke":
            sure = rng.lognormal(math.log(P["sebeke_medyan_saat"] * 60), P["sebeke_sigma"])
            masa(j, t + int(sure), "dogrulama")
        elif sonuc == "kurye":
            g = t // 1440
            if _saat(t) < P["kurye_son_saat"] and kurye_kullanim.get(g, 0) < P["kurye_kapasite_gun"]:
                kurye_kullanim[g] = kurye_kullanim.get(g, 0) + 1
                teslim = t + P["kurye_sure_dk"]
            else:
                g2 = g + 1
                while kurye_kullanim.get(g2, 0) >= P["kurye_kapasite_gun"]:
                    g2 += 1
                kurye_kullanim[g2] = kurye_kullanim.get(g2, 0) + 1
                teslim = g2 * 1440 + 11 * 60 + int(rng.integers(0, 180))
            masa(j, teslim + 30, "kurye_destek")
        elif sonuc == "dolgu":
            sahaya(j, t, teyitli=True, tercih_uygula=False)
        else:
            sahaya(j, t, teyitli=True)

    # --- kadro fonksiyonları ---
    def masa_kisi(t):
        g = t // 1440; gt = _gun_tipi(g); s = _saat(t)
        n = 0
        if 8.0 <= s < 16.5: n += P["masa_A"][gt]
        if 12.5 <= s < 21.0: n += P["masa_B"][gt]
        return n

    esnek_gun = {}
    asiri_yuk = {}

    def esnek_hesapla(t):
        """07:45 kuralı: esnek = ceil((kuyruk_dk + bugün_tahmini_dk - ana_kapasite_dk) / 540), [0, max]."""
        g = t // 1440; gt = _gun_tipi(g)
        wd = (BASLANGIC + timedelta(days=g)).weekday()
        kuyruk_dk = sum((TIPLER[isler[i]["tip"]]["saha_dk"] if isler[i]["yol"] != "dolgu" else 12)
                        for i in saha_kuyruk if isler[i]["kapanis"] is None)
        tahmin_dk = GUN_ORT[GUN_ADI[wd]] * P["saha_dk_is_tahmin"] * 0.75   # gün içinde sahaya inebilecek pay
        kap = (P["saha_gunduz"][gt] + P["saha_gec"][gt]) * 600 * P["saha_verim"]
        ihtiyac = kuyruk_dk + tahmin_dk - kap
        ham = max(0, math.ceil(ihtiyac / (600 * P["saha_verim"])))
        izinli = P["esnek_max"][gt] if P["esnek_dinamik"] else (
            P["esnek_havuz"] if (gt == "hi" and g < P["esnek_havuz_gun"]) else 0)
        asiri_yuk[g] = ham > izinli          # kapasite yetmiyor -> BTK-önce triaj sırası
        return int(min(izinli, ham))

    def saha_kisi(t):
        g = t // 1440; gt = _gun_tipi(g); s = _saat(t)
        ana = 0; esnek = 0
        if 8.5 <= s < 18.5: ana += P["saha_gunduz"][gt]
        if 11.0 <= s < 21.0: ana += P["saha_gec"][gt]
        if g not in esnek_gun and s >= 7.75:
            esnek_gun[g] = esnek_hesapla(t)
        if 8.5 <= s < 18.5:
            esnek = esnek_gun.get(g, 0)
        return ana, esnek

    # --- ölçümler ---
    gunluk = {k: np.zeros(GUN + 3) for k in
              ["masa_dk_kull", "masa_dk_kap", "saha_dk_kull", "saha_dk_kap", "ziyaret", "bosa", "kurye",
               "birikim_acik", "acik_24s_ustu", "acik_toplam", "saha_kuyruk"]}

    masa_hazir: list = []   # (öncelik, son_tarih, sıra, iş_id, eylem)
    banka_ana = 0.0; banka_esnek = 0.0
    hedef = lambda j: j["varis"] + min(TIPLER[j["tip"]]["tsl"], 24) * 60

    for t in range(0, UFUK, ADIM):
        g = t // 1440
        # ekstra tekrar girişleri
        if ekstra_tekrar:
            kalan = []
            for (tt, tip) in ekstra_tekrar:
                if tt <= t:
                    j = ekle_is(tip, tt, tekrar=True); masa(j, tt, "temas")
                else:
                    kalan.append((tt, tip))
            ekstra_tekrar[:] = kalan
        # vadesi gelen masa eylemleri -> hazır listesi
        while olay and olay[0][0] < t + ADIM:
            zaman, s, jid, eylem = heapq.heappop(olay)
            j = isler[jid]
            if j["kapanis"] is not None:
                continue
            if eylem == "temas":
                onc = (0 if j["btk"] else 2) + (1 if j["k"] > 0 else 0) + (4 if j["birikim"] else 0)
            elif eylem == "sistem":
                onc = 3 + (4 if j["birikim"] else 0)
            else:
                onc = 1  # doğrulama/kurye destek: kısa, kapanış getirir
            heapq.heappush(masa_hazir, (onc, hedef(j), s, jid, eylem))
        # masa kapasitesi
        kap = masa_kisi(t) * ADIM * P["masa_doluluk"]
        gunluk["masa_dk_kap"][g] += kap
        kull = 0.0
        ertelenen = []
        while masa_hazir and kull < kap:
            onc, _, s, jid, eylem = heapq.heappop(masa_hazir)
            j = isler[jid]
            if j["kapanis"] is not None:
                continue
            T = TIPLER[j["tip"]]
            if eylem == "sistem":
                kull += P["sistem_dk"]
                if rng.random() < T.get("sistem", 0) * (1.0 if not j["birikim"] else 1.0):
                    kapat(j, t, "sistem_uzlastirma")
                else:
                    masa(j, t, "temas")
            elif eylem == "dogrulama":
                kull += P["dogrulama_dk"]; kapat(j, t, "sebeke_giderildi")
            elif eylem == "kurye_destek":
                kull += P["kurye_destek_dk"]
                if rng.random() < P["kurye_destek_basari"]:
                    kapat(j, t, "kurye")
                else:
                    sahaya(j, t, teyitli=True)
            else:  # temas
                pk = P["ulasma"][min(j["k"], len(P["ulasma"]) - 1)]
                if j["birikim"]:
                    pk *= P["birikim_ulasma_carpan"]
                j["k"] += 1
                if rng.random() < pk:
                    kull += T["masa_dk"]; ulasildi(j, t)
                else:
                    kull += P["basarisiz_dk"]; sonraki_deneme(j, t)
        gunluk["masa_dk_kull"][g] += kull

        # saha
        ana, esnek = saha_kisi(t)
        ka = ana * ADIM * P["saha_verim"]; ke = esnek * ADIM * P["saha_verim"]
        gunluk["saha_dk_kap"][g] += ka + ke
        banka_ana = min(banka_ana, 0) + ka
        banka_esnek = min(banka_esnek, 0) + ke
        hazir = [isler[i] for i in saha_kuyruk if isler[i]["kapanis"] is None and isler[i]["saha_hazir"] is not None
                 and isler[i]["saha_hazir"] <= t]
        if hazir and (banka_ana > 0 or banka_esnek > 0):
            def anahtar(j, esnek_mod):
                """Saha sırası (R-SAHA-SIRA).
                ANA havuz = musluğu korur: 24 saati dolmamış yeni işler önce; sıra = Turkcell/bayi son
                tarihi - BTK bonusu (EDF). Aşırı yük gününde BTK kesin önde. 24 saati geçmiş iş ve
                birikim 'kurtarma' sınıfına düşer (en eski önce); ESNEK havuz önce kurtarma sınıfını
                eritir. Dolgu durakları en son (rotada boşluk varsa)."""
                if j["yol"] == "dolgu":
                    return (9, j["varis"])
                gec = j["birikim"] or (t > j["varis"] + 1440)
                if gec:
                    return ((0 if j["btk"] else 1) if esnek_mod and P["esnek_birikim_oncelik"]
                            else (2 if j["btk"] else 3), j["varis"])
                yeni_k = hedef(j) - (P["btk_bonus_dk"] if j["btk"] else 0)
                if esnek_mod and P["esnek_birikim_oncelik"]:
                    return (2, yeni_k)
                if asiri_yuk.get(t // 1440, False):
                    return (0, hedef(j)) if j["btk"] else (1, hedef(j))   # aşırı yük: BTK önce
                return (0, yeni_k)
            for havuz in ("ana", "esnek"):
                banka = banka_ana if havuz == "ana" else banka_esnek
                if banka <= 0: continue
                hazir.sort(key=lambda j: anahtar(j, havuz == "esnek"))
                kalan = []
                for j in hazir:
                    if banka <= 0 or j["kapanis"] is not None:
                        kalan.append(j); continue
                    T = TIPLER[j["tip"]]
                    dur = (T["saha_dk"] * P["ziyaret_dk_carpan"]) if j["yol"] != "dolgu" else 12
                    j["ziyaret"] += 1; gunluk["ziyaret"][g] += 1
                    p_bosa = P["bosa_teyitli"] if j["teyitli"] else P["bosa_teyitsiz"]
                    if rng.random() < p_bosa:
                        banka -= P["bosa_dk"]; gunluk["bosa"][g] += 1; j["bosa"] += 1
                        j["saha_hazir"] = None
                        saha_kuyruk.remove(j["id"])
                        masa(j, t + ADIM, "temas")   # masa merdivene geri alır
                    else:
                        banka -= dur; gunluk["saha_dk_kull"][g] += dur
                        kapat(j, t + ADIM, "saha")
                hazir = [j for j in kalan if j["kapanis"] is None and j["saha_hazir"] is not None]
                if havuz == "ana": banka_ana = banka
                else: banka_esnek = banka
            saha_kuyruk[:] = [i for i in saha_kuyruk if isler[i]["kapanis"] is None and isler[i]["saha_hazir"] is not None]
        # gün sonu ölçüm
        if (t + ADIM) % 1440 == 0:
            acik = [j for j in isler if j["geldi"] <= t and j["kapanis"] is None]
            gunluk["acik_toplam"][g] = len(acik)
            gunluk["birikim_acik"][g] = sum(1 for j in acik if j["birikim"])
            gunluk["acik_24s_ustu"][g] = sum(1 for j in acik if t - j["varis"] > 1440)
            gunluk["saha_kuyruk"][g] = len(saha_kuyruk)
    for g, n in kurye_kullanim.items():
        if g < GUN + 3:
            gunluk["kurye"][g] = n

    # --- sonuç metrikleri: gün 3..GUN arasında gelen yeni işler (ilk 2 gün ısınma) ---
    yeni = [j for j in isler if not j["birikim"] and 2 * 1440 <= j["geldi"] < GUN * 1440]
    def oran(js, saat):
        if not js: return None
        return sum(1 for j in js if j["kapanis"] is not None and j["kapanis"] - j["varis"] <= saat * 60) / len(js)
    btk = [j for j in yeni if j["btk"]]
    bag = [j for j in yeni if j["tip"] == "BAGLANTI"]
    tv = [j for j in yeni if j["tip"] == "TV_ARIZA"]
    sonuc_say = {}
    for j in yeni:
        k = j["sonuc"] or "acik"
        sonuc_say[k] = sonuc_say.get(k, 0) + 1
    sure = np.array([(j["kapanis"] - j["varis"]) / 60 for j in yeni if j["kapanis"] is not None])
    ilk_temas_btk = []
    gunler = slice(2, GUN)
    gs = lambda k: float(np.mean(gunluk[k][gunler]))
    birikim_bitti = next((g for g in range(GUN + 3) if gunluk["birikim_acik"][g] <= 20), None)
    return dict(
        yeni_is=len(yeni),
        uyum_24s=oran(yeni, 24), uyum_12s=oran(yeni, 12), uyum_48s=oran(yeni, 48),
        uyum_24s_bayi_kontrol=oran([j for j in yeni if not j["ertelendi"] and not j["aski"]
                                    and j["sonuc"] != "ulasilamadi_kapat"], 24),
        ertelenen_payi=sum(1 for j in yeni if j["ertelendi"]) / max(len(yeni), 1),
        ulasilamadi_payi=sum(1 for j in yeni if j["sonuc"] == "ulasilamadi_kapat" or j["aski"]) / max(len(yeni), 1),
        asiri_yuk_gun=int(sum(1 for g in range(2, GUN) if asiri_yuk.get(g))),
        saha_dk_per_yeni_is_son7=float(gunluk["saha_dk_kull"][GUN - 7:GUN].sum() /
                                       max(1, sum(1 for j in isler if not j["birikim"] and (GUN - 7) * 1440 <= j["geldi"] < GUN * 1440))),
        ziyaret_per_yeni_is_son7=float(gunluk["ziyaret"][GUN - 7:GUN].sum() /
                                       max(1, sum(1 for j in isler if not j["birikim"] and (GUN - 7) * 1440 <= j["geldi"] < GUN * 1440))),
        masa_dk_per_yeni_is_son7=float(gunluk["masa_dk_kull"][GUN - 7:GUN].sum() /
                                       max(1, sum(1 for j in isler if not j["birikim"] and (GUN - 7) * 1440 <= j["geldi"] < GUN * 1440))),
        btk_24s=oran(btk, 24), baglanti_12s=oran(bag, 12), tv_6s=oran(tv, 6), tv_24s=oran(tv, 24),
        kapanis_saat_p50=float(np.percentile(sure, 50)) if len(sure) else None,
        kapanis_saat_p90=float(np.percentile(sure, 90)) if len(sure) else None,
        sonuc_payi={k: v / len(yeni) for k, v in sorted(sonuc_say.items())},
        gunluk_ort=dict(
            masa_doluluk=gs("masa_dk_kull") / max(gs("masa_dk_kap"), 1),
            masa_dk=gs("masa_dk_kull"),
            saha_doluluk=gs("saha_dk_kull") / max(gs("saha_dk_kap"), 1),
            ziyaret=gs("ziyaret"), bosa_ziyaret=gs("bosa"), kurye=gs("kurye"),
        ),
        birikim_acik_gun=[int(x) for x in gunluk["birikim_acik"][:GUN]],
        acik_24s_ustu_gun=[int(x) for x in gunluk["acik_24s_ustu"][:GUN]],
        acik_toplam_gun=[int(x) for x in gunluk["acik_toplam"][:GUN]],
        birikim_20_alti_gun=birikim_bitti,
        esnek_ort_gun=float(np.mean([esnek_gun.get(g, 0) for g in range(2, GUN)])),
        esnek_ilk7=float(np.mean([esnek_gun.get(g, 0) for g in range(0, 7)])),
        esnek_son7=float(np.mean([esnek_gun.get(g, 0) for g in range(GUN - 7, GUN)])),
    )


def ozetle(sonuclar: list[dict]) -> dict:
    def ort(k, alt=None):
        v = [s[k] if alt is None else s[k][alt] for s in sonuclar]
        v = [x for x in v if x is not None]
        return round(float(np.mean(v)), 3) if v else None
    out = {k: ort(k) for k in ["yeni_is", "uyum_24s", "uyum_12s", "uyum_48s", "btk_24s", "baglanti_12s",
                                "tv_6s", "tv_24s", "kapanis_saat_p50", "kapanis_saat_p90",
                                "uyum_24s_bayi_kontrol", "ertelenen_payi", "ulasilamadi_payi", "asiri_yuk_gun",
                                "saha_dk_per_yeni_is_son7", "ziyaret_per_yeni_is_son7", "masa_dk_per_yeni_is_son7",
                                "esnek_ort_gun", "esnek_ilk7", "esnek_son7"]}
    out["gunluk_ort"] = {k: ort("gunluk_ort", k) for k in sonuclar[0]["gunluk_ort"]}
    tum = {}
    for s in sonuclar:
        for k, v in s["sonuc_payi"].items():
            tum[k] = tum.get(k, 0) + v / len(sonuclar)
    out["sonuc_payi"] = {k: round(v, 3) for k, v in sorted(tum.items(), key=lambda x: -x[1])}
    for k in ["birikim_acik_gun", "acik_24s_ustu_gun", "acik_toplam_gun"]:
        out[k] = [int(round(x)) for x in np.mean([s[k] for s in sonuclar], axis=0)]
    bb = [s["birikim_20_alti_gun"] for s in sonuclar]
    out["birikim_20_alti_gun"] = None if any(b is None for b in bb) else float(np.mean(bb))
    out["birikim_20_alti_gun_bitmeyen_tekrar"] = sum(1 for b in bb if b is None)
    return out


DIN = dict(esnek_dinamik=True, esnek_max={"hi": 8, "Cmt": 8, "Paz": 5})
SENARYOLAR = {
    "S0_bugunku_saha_kadrosu_esneksiz": {},
    "S1_ONERILEN_huni_dinamik_esnek": dict(DIN),
    "S2_onerilen_kume_rotasi_35dk": dict(DIN, ziyaret_dk_carpan=35 / 40),
    "S3_onerilen_dusuk_ulasma": dict(DIN, ulasma=[0.45, 0.30, 0.25, 0.35, 0.35, 0.20]),
    "S4_onerilen_dusuk_uzaktan_kurye": dict(DIN, uzaktan_carpan=0.6, kurye_carpan=0.5),
    "S5_onerilen_yuksek_uzaktan_hat_testi": dict(DIN, uzaktan_carpan=1.35),
    "S6_onerilen_kucuk_masa_7kisi": dict(DIN, masa_A={"hi": 4, "Cmt": 3, "Paz": 2}, masa_B={"hi": 3, "Cmt": 2, "Paz": 1}),
    "S7_onerilen_tekrar_korumasiz": dict(DIN, tekrar_orani_btk=0.0),
    "S8_esnek_tavan4_asiri_yuk": dict(DIN, esnek_max={"hi": 4, "Cmt": 4, "Paz": 2}),
}


def main(tekrar: int = 5):
    rapor = {"aciklama": "Uzaktan-Önce Huni (U1H) simülasyonu; mevcut müşteri akışı; 28 gün; "
                         f"{tekrar} tekrar ortalaması. Gün 3-28 arası gelen yeni işler ölçülür.",
             "temel_parametre": {k: v for k, v in TEMEL.items()},
             "tip_kurallari": TIPLER, "birikim_baslangic": BIRIKIM, "senaryo": {}}
    for ad, deg in SENARYOLAR.items():
        P = dict(TEMEL); P.update(deg)
        res = [simule(P, 1000 + i) for i in range(tekrar)]
        rapor["senaryo"][ad] = {"degisiklik": deg, "sonuc": ozetle(res)}
        o = rapor["senaryo"][ad]["sonuc"]
        print(f"{ad:32s} 24s={o['uyum_24s']} btk24={o['btk_24s']} bag12={o['baglanti_12s']} tv6={o['tv_6s']} "
              f"sdk/is={o['saha_dk_per_yeni_is_son7']} z/is={o['ziyaret_per_yeni_is_son7']} mdk/is={o['masa_dk_per_yeni_is_son7']} "
              f"bk24={o['uyum_24s_bayi_kontrol']} ert={o['ertelenen_payi']} ul={o['ulasilamadi_payi']} ay={o['asiri_yuk_gun']} "
              f"p50={o['kapanis_saat_p50']} masa={o['gunluk_ort']['masa_doluluk']} saha={o['gunluk_ort']['saha_doluluk']} "
              f"ziy={o['gunluk_ort']['ziyaret']} bosa={o['gunluk_ort']['bosa_ziyaret']} "
              f"birikim20={o['birikim_20_alti_gun']} acik24_son={o['acik_24s_ustu_gun'][-1]} esnek={o['esnek_ort_gun']}/{o['esnek_ilk7']}/{o['esnek_son7']}")
    CIKTI.write_text(json.dumps(rapor, ensure_ascii=False, indent=1), encoding="utf-8")
    print("yazildi:", CIKTI)


if __name__ == "__main__":
    main()
