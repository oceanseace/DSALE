# -*- coding: utf-8 -*-
"""İş emri (BOSS + FOX + PS26 manuel sayfalar) nicel analizi.

Çalıştırma:  .venv/Scripts/python.exe operasyon/analiz/is_emri_analizi.py
Çıktı     :  operasyon/analiz/cikti/is_emri_analizi.json   (sonra rapor_md.py -> is_emri_analizi.md)

GİZLİLİK: Kaynaklarda müşteri adı/adres/telefon var. Bu betik yalnızca SAYIM/ORAN/SÜRE ve
kategori (ilçe, mahalle, task tipi) düzeyinde çıktı üretir; müşteri no, ad, adres, task no,
lokasyon kimliği tek tek yazılmaz. Ağ çağrısı yok.
"""
import json
import os
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from scipy.sparse.csgraph import connected_components

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).parent))
import taksonomi as TX  # noqa: E402

if __package__ in (None, ""):  # doğrudan çalıştırıldı: kod/ içe aktarma yoluna (yollar)
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import yollar  # noqa: E402

# ------------------------------------------------------------------ kaynaklar
DESK = Path(r"C:/Users/EXT03426951/Desktop")
SRC = dict(
    boss=DESK / "TeknikTaskDetayRaporu.xlsx",
    fox_acik=DESK / "ReportResultAçık.xls",
    fox_aski=DESK / "ReportResultAskı.xls",
    ps26=yollar.PS26 / "data.xlsx",
    # Ek (masaüstünde bulundu, kullanıcı bu istekte ayrıca eklemedi): 1-15 Eylül tamamlanan arıza
    # task'ları ve günlük GELEN/YAPILAN tablosu. Sansürsüz giriş (inflow) tahmini için kritik.
    tamamlandi=DESK / "TAMAMLANDI.xlsx",
    anlatilan=DESK / "ANLATILAN.xlsx",
    bina=yollar.VERI / "master" / "bina_master.csv",
)
OUT = Path(__file__).parent / "cikti"
OUT.mkdir(parents=True, exist_ok=True)

GUN = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]
YAS_BIN = [0, 24, 48, 72, 168, 720, 1e9]
YAS_LBL = ["<24s", "24-48s", "48-72s", "3-7g", "7-30g", ">30g"]
SAHA_NEDEN = {
    "Müşteri Sorununun Düzeldiğini Söyledi": "telefon_uzaktan",
    "Çağrı Merkezi Tarafından Çözülebilirdi": "telefon_uzaktan",
    "Müşteriyle görüşüldü, işlem yapıldı, mutabık kalındı": "telefon_uzaktan",
    "Lokasyonda Genel Arıza Vardı": "sebeke_altyapi",
    "BÇO / NW Müdahale Sonrası Düzeldi": "sebeke_altyapi",
    "TT Kaynaklı Sorun": "sebeke_altyapi",
    "Kablo, Konnektör, Uç Değişimi Yapıldı": "saha_mudahale",
    "Cihaz Değişimi Yapıldı. (Modem, STB, ONT, Superbox vs.)": "saha_mudahale",
    "Kurulum müşterinin istediği gibi düzeltildi": "saha_mudahale",
    "Randevu yenilendi, kuruluma gidildi": "saha_mudahale",
}


def py(o):
    """numpy/pandas -> JSON uyumlu."""
    if isinstance(o, dict):
        return {str(k): py(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [py(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating, float)):
        return None if (o is None or np.isnan(o)) else round(float(o), 3)
    if isinstance(o, (pd.Timestamp,)):
        return o.isoformat()
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if o is pd.NaT:
        return None
    return o


def vc(s, n=None):
    r = s.value_counts(dropna=False)
    r.index = [("(boş)" if (isinstance(i, float) and np.isnan(i)) else str(i)) for i in r.index]
    return r.head(n).to_dict() if n else r.to_dict()


def ct(a, b):
    t = pd.crosstab(a.fillna("(boş)"), b.fillna("(boş)"))
    return {str(i): {str(c): int(t.loc[i, c]) for c in t.columns if t.loc[i, c]} for i in t.index}


def q(s, qs=(0.1, 0.25, 0.5, 0.75, 0.9)):
    s = pd.Series(s).dropna()
    if not len(s):
        return {}
    d = {f"p{int(x*100)}": float(s.quantile(x)) for x in qs}
    d["ort"] = float(s.mean())
    d["n"] = int(len(s))
    return d


def yas_dagilimi(h):
    c = pd.cut(h, YAS_BIN, labels=YAS_LBL, right=False)
    return {k: int(v) for k, v in c.value_counts().reindex(YAS_LBL).fillna(0).items()}


# ------------------------------------------------------------------ yükleme
def yukle():
    b = pd.read_excel(SRC["boss"])
    for c in ["Askıya Alınma Nedeni", "Merkeze Gönder Statüsü", "Task Durumu", "Randevu Durumu"]:
        b[c] = b[c].map(lambda v: v.strip() if isinstance(v, str) else np.nan).astype(object)
    fa = pd.read_excel(SRC["fox_acik"]); fa["fox_dosya"] = "acik"
    fs = pd.read_excel(SRC["fox_aski"]); fs["fox_dosya"] = "aski"
    f = pd.concat([fa, fs], ignore_index=True)
    f["kalan_h"] = (f["Kalan Süre"].astype(str).str.replace(".", "", regex=False)
                    .str.replace(",", ".", regex=False).astype(float))
    for c in ["Başlangıç Tarihi", "Atanma Zamanı"]:
        f[c] = pd.to_datetime(f[c])
    # referans an: export'taki en son zaman damgası (BOSS/FOX aynı dakikada çekilmiş)
    ref_ts = max(b["Task Başlangıç Tarihi"].max(), b["Teknik Ekip İşe Başlama Tarihi"].max(),
                 b["Teknik Ekip Konum Paylaşma Tarihi"].max(), f["Atanma Zamanı"].where(
                     f["Atanma Zamanı"] < pd.Timestamp("2026-09-30")).max())
    ref_ts = ref_ts.ceil("min")
    b["kod"] = b["Task Adı"].map(TX.boss_kod)
    f["kod"] = f["Task Adı"].map(TX.fox_kod)
    # FOX kaydı BOSS'ta varsa BOSS'un (daha ayrıntılı) kodunu kullan
    bk = b.set_index("Task No")["kod"]
    f["kod"] = f["Akış No"].map(bk).fillna(f["kod"])
    for d in (b, f):
        d["sahip"] = d["kod"].map(lambda k: TX.KOD[k]["sahip"] if k in TX.KOD else "bilinmeyen")
        d["grup"] = d["kod"].map(lambda k: TX.KOD[k]["grup"] if k in TX.KOD else "bilinmeyen")
        d["btk"] = d["kod"].map(lambda k: TX.KOD[k]["btk"] if k in TX.KOD else False)
    b["yas_h"] = (ref_ts - b["Task Başlangıç Tarihi"]).dt.total_seconds() / 3600
    f["yas_h"] = (ref_ts - f["Başlangıç Tarihi"]).dt.total_seconds() / 3600

    t = pd.read_excel(SRC["tamamlandi"], sheet_name="Task Detail Report")
    t["kod"] = t["Task Adı"].map(TX.boss_kod)
    t["sahip"] = t["kod"].map(lambda k: TX.KOD[k]["sahip"] if k in TX.KOD else "bilinmeyen")
    t["sure_h"] = (t["Task Bitiş Tarihi"] - t["Task Başlangıç Tarihi"]).dt.total_seconds() / 3600
    an = pd.read_excel(SRC["anlatilan"], sheet_name="WHY")
    anp = pd.read_excel(SRC["anlatilan"], sheet_name="PIVOT")
    m = pd.read_csv(SRC["bina"], dtype=str)
    for c in ["lat", "lon", "ofis_km"]:
        m[c] = pd.to_numeric(m[c], errors="coerce")
    return b, f, t, an, anp, m, ref_ts


def lokasyon_bagla(df, m, col="Lokasyon"):
    """BOSS Lokasyon -> bina_master.location_id (doğrudan; olmazsa baştaki 0'lar atılarak)."""
    ids = set(m["location_id"])
    L = df[col].astype("string").str.strip()
    direct = L.where(L.isin(ids))
    alt = L.str.lstrip("0").where(~L.isin(ids))
    alt = alt.where(alt.isin(ids))
    key = direct.fillna(alt)
    mm = m.set_index("location_id")[["lat", "lon", "ilce", "mahalle", "ofis_km"]]
    out = df.join(mm, on=key.rename("_k")) if False else df.assign(_k=key).join(mm, on="_k")
    out["eslesme"] = np.where(L.isna(), "lokasyon_yok",
                              np.where(direct.notna(), "dogrudan",
                                       np.where(alt.notna(), "sifir_kirpma", "master_da_yok")))
    return out


def xy(lat, lon, lat0=40.2, lon0=29.0):
    return np.c_[(lon - lon0) * np.cos(np.radians(lat0)) * 111320.0, (lat - lat0) * 110540.0]


def kume_analizi(g):
    """g: lat/lon'lu satırlar. 500 m / 2 km komşuluk ve 500 m bağlantılı kümeler."""
    g = g.dropna(subset=["lat", "lon"])
    n = len(g)
    if n < 2:
        return {"n": n}
    P = xy(g["lat"].values, g["lon"].values)
    tr = cKDTree(P)
    res = {"n": n}
    for r in (100, 500, 2000):
        cnt = np.array([len(x) - 1 for x in tr.query_ball_point(P, r)])
        res[f"komsu_{r}m"] = {"ort_komsu": float(cnt.mean()), "medyan_komsu": float(np.median(cnt)),
                               "en_az_1_komsu_orani": float((cnt >= 1).mean()),
                               "en_az_5_komsu_orani": float((cnt >= 5).mean())}
    d, _ = tr.query(P, k=2)
    nn = d[:, 1]
    res["en_yakin_komsu_m"] = q(nn)
    res["ayni_bina_orani"] = float((nn < 1).mean())
    res["ayni_binada_birden_fazla_is_bina_sayisi"] = int((g.groupby("_k").size() > 1).sum())
    for r in (500, 2000):
        A = tr.sparse_distance_matrix(tr, r, output_type="coo_matrix")
        nc, lab = connected_components(A, directed=False)
        sz = pd.Series(lab).value_counts()
        res[f"kume_{r}m"] = {"kume_sayisi": int(nc), "tekil_is": int((sz == 1).sum()),
                             "5+_isli_kume": int((sz >= 5).sum()),
                             "5+_isli_kumelerdeki_is_orani": float(sz[sz >= 5].sum() / n),
                             "en_buyuk_kume": int(sz.max())}
    return res


# ------------------------------------------------------------------ analiz
def main():
    b, f, t, an, anp, m, REF = yukle()
    R = {"meta": {}, "taksonomi": {}, "sla": {}, "birikim": {}, "giris": {}, "teknisyen": {},
         "randevu": {}, "ps26": {}, "parametreler": {}}
    R["meta"] = dict(
        referans_an=REF, olusturma="operasyon/analiz/is_emri_analizi.py",
        kaynaklar={k: str(v) for k, v in SRC.items()},
        satir=dict(boss_acik=len(b), fox_acik=int((f.fox_dosya == "acik").sum()),
                   fox_aski=int((f.fox_dosya == "aski").sum()), tamamlandi_1_15_eylul=len(t),
                   bina_master=len(m)),
        not_=("TAMAMLANDI.xlsx ve ANLATILAN.xlsx kullanıcı tarafından bu istekte eklenmedi; masaüstünde "
              "bulundu ve yalnızca toplu sayım için okundu (1-15 Eylül tamamlanan mevcut-müşteri task'ları "
              "ve günlük GELEN/YAPILAN). Giriş hızı ve telefonla çözülebilirlik tahminleri bu dosyaya dayanır."),
        gizlilik="Çıktılarda müşteri adı/no/adres/telefon, task no ve tekil lokasyon kimliği yoktur.",
    )

    # ============================================================ 1. TAKSONOMİ
    j = f.merge(b[["Task No", "Task Adı", "kod"]], left_on="Akış No", right_on="Task No", how="outer",
                suffixes=("_fox", "_boss"), indicator=True)
    esl = (j[j["_merge"] == "both"].groupby(["Task Adı_fox", "Task Adı_boss"]).size()
           .reset_index(name="n").sort_values("n", ascending=False))
    R["taksonomi"]["fox_boss_birlesim"] = {
        "ortak": int((j["_merge"] == "both").sum()),
        "sadece_fox": int((j["_merge"] == "left_only").sum()),
        "sadece_boss": int((j["_merge"] == "right_only").sum()),
        "sadece_fox_task_adi": vc(j.loc[j["_merge"] == "left_only", "Task Adı_fox"]),
        "sadece_boss_task_adi": vc(j.loc[j["_merge"] == "right_only", "Task Adı_boss"]),
        "sadece_fox_dosya": vc(j.loc[j["_merge"] == "left_only", "fox_dosya"]),
    }
    R["taksonomi"]["ad_eslemesi"] = [dict(fox=r["Task Adı_fox"], boss=r["Task Adı_boss"], n=int(r.n))
                                     for _, r in esl.iterrows()]
    isim_farki = esl[esl["Task Adı_fox"].map(TX.norm) != esl["Task Adı_boss"].map(TX.norm)]
    R["taksonomi"]["farkli_isimli_eslesmeler"] = [dict(fox=r["Task Adı_fox"], boss=r["Task Adı_boss"], n=int(r.n))
                                                  for _, r in isim_farki.iterrows()]
    R["taksonomi"]["bilinmeyen_kod"] = dict(boss=vc(b.loc[b.kod == "BILINMEYEN", "Task Adı"]),
                                            fox=vc(f.loc[f.kod == "BILINMEYEN", "Task Adı"]),
                                            tamamlandi=vc(t.loc[t.kod == "BILINMEYEN", "Task Adı"]))

    # TAMAMLANDI kapanış nedenleri -> saha ihtiyacı
    fieldset = set(TX.norm(x) for x in pd.concat([t["Ekip"], b["Ekip"]]).dropna().unique())
    t["kapatan"] = np.where(t["Teknisyen"].map(TX.norm).isin(fieldset), "saha_teknisyeni", "ofis_operasyon")
    t["neden_grup"] = t["Arıza Nedeni"].map(SAHA_NEDEN).fillna("neden_girilmemis")
    tt = t[t["Task Durumu"] == "Tamamlandı"]
    # 1-2 Eylül'de BOSS 'Teknisyen' alanı hiç dolmamış (tüm kapanışlar boş) -> kapatan analizi 3-15 Eylül
    tk = tt[tt["Task Bitiş Tarihi"] >= "2026-09-03"]
    kap = {}
    for k, g in tk.groupby("kod"):
        gk = g
        d = dict(n=len(gk),
                 kapatan=vc(gk["kapatan"]),
                 neden_grup=vc(gk["neden_grup"]),
                 neden_grup_saha_kapanisinda=vc(gk.loc[gk.kapatan == "saha_teknisyeni", "neden_grup"]),
                 ofis_kapanis_orani=float((gk.kapatan == "ofis_operasyon").mean()))
        known = gk[gk.neden_grup != "neden_girilmemis"]
        if len(known) >= 10:
            d["neden_girilenlerde"] = {k2: float(v) for k2, v in known.neden_grup.value_counts(normalize=True).items()}
        # ziyaret gerektirmeyen tahmini: ofis kapanışı VEYA telefon/uzaktan VEYA şebeke nedeni
        nov = (gk.kapatan == "ofis_operasyon") | gk.neden_grup.isin(["telefon_uzaktan", "sebeke_altyapi"])
        d["ziyaretsiz_kapanis_orani"] = float(nov.mean())
        d["telefon_uzaktan_orani_tum"] = float((gk.neden_grup == "telefon_uzaktan").mean())
        kap[k] = d
    R["taksonomi"]["kapanis_nedenleri_3_15_eylul"] = kap
    # tekrarlayan arıza: 1-15 Eylül'de aynı müşteride >1 BTK arıza task'ı (yalnızca sayım)
    ba = t[t.kod.isin(["BAGLANTI", "TV_ARIZA", "ARAMA", "DOPING_ARIZA"])]
    per = ba.groupby("Müşteri No").size()
    R["taksonomi"]["tekrar_ariza_1_15_eylul"] = dict(
        task=len(ba), musteri=int(len(per)), birden_fazla_task_musteri=int((per > 1).sum()),
        tekrar_task=int((per - 1).clip(lower=0).sum()),
        tekrar_task_orani=float((per - 1).clip(lower=0).sum() / len(ba)),
        not_="Aynı müşteride 15 gün içinde 2.,3.… arıza task'ı = tekrar. İlk müdahale kalitesinin göstergesi.")
    R["taksonomi"]["ayni_musteride_birden_fazla_acik_task"] = int((b.groupby("Müşteri No").size() > 1).sum())
    R["taksonomi"]["kapanis_nedeni_x_tip"] = ct(tt["Task Adı"], tt["Arıza Nedeni"])

    tip_rows = []
    for k in TX.KANONIK:
        kod = k["kod"]
        bb = b[b.kod == kod]; ff = f[f.kod == kod]; t_ = t[t.kod == kod]
        tip_rows.append(dict(
            kod=kod, ad=k["ad"], boss_adlari=k["boss"], fox_adlari=k["fox"], grup=k["grup"],
            sahip=k["sahip"], sahip_fox_adina_gore=k["sahip_fox_adina_gore"], belirsiz=k.get("belirsiz"),
            btk_kritik=k["btk"], saha_ihtiyaci=k["saha"],
            acik_boss=len(bb), acik_fox=int((ff.fox_dosya == "acik").sum()), aski_fox=int((ff.fox_dosya == "aski").sum()),
            tamamlanan_1_15_eylul=len(t_),
            ziyaretsiz_kapanis_orani=kap.get(kod, {}).get("ziyaretsiz_kapanis_orani"),
        ))
    R["taksonomi"]["kanonik_tipler"] = tip_rows
    R["taksonomi"]["telefon_alanlari_not"] = (
        "BOSS açık export'ta 'Telefonla Çözülebilir Miydi?', 'Temel Arıza Nedeni', 'Arıza Nedeni' sütunları "
        "2.567 satırın hiçbirinde dolu değil (kapanışta doldurulan alanlar). Telefon/saha ayrımı bu yüzden "
        "TAMAMLANDI.xlsx 'Arıza Nedeni' + kapatan kişi (saha teknisyeni mi ofis mi) üzerinden yapıldı.")

    # ============================================================ 2. SLA
    br = b[b.SL == "SL Geçti"].copy()
    br["hedef"] = br["yas_h"] - br["SL Süresi(Sa)"]
    boss_hedef = br.groupby("Task Adı")["hedef"].median().apply(lambda x: float(np.floor(x)))
    sla_boss_tip = {}
    for ad, g in b.groupby("Task Adı"):
        sla_boss_tip[ad] = dict(n=len(g), sl_gecti=int((g.SL == "SL Geçti").sum()),
                                sl_gecmedi=int((g.SL == "SL Geçmedi").sum()), sl_yok=int(g.SL.isna().sum()),
                                boss_hedef_saat=boss_hedef.get(ad))
    fh = f.groupby("Task Adı")["Hedef SL"].agg(lambda s: s.value_counts().index[0])
    g2 = f[f["Hedef SL"] > 0].copy()
    g2["gecen_sl"] = g2["Hedef SL"] - g2["kalan_h"]
    g2["fark_bas"] = g2["yas_h"] - g2["gecen_sl"]
    R["sla"]["tanimlar"] = {
        "BOSS_SL": "'SL Geçti' / 'SL Geçmedi'; boş = o task tipi için BOSS'ta SL tanımı yok.",
        "BOSS_SL_Suresi_Sa": ("SL hedefinin KAÇ SAAT AŞILDIĞI (tam saat, aşağı yuvarlanmış). 'SL Geçmedi' ise 0. "
                              "Doğrulama: (şimdi - Task Başlangıç) - SL Süresi, her tip için sabit bir hedefe "
                              "oturuyor (±1 saat), saat takvim saati (gece/hafta sonu düşülmüyor)."),
        "FOX_Hedef_SL": "Turkcell'in akış (ticket) bazlı SL hedefi, saat. 0 = FOX'ta SL yok (kurulum tipleri).",
        "FOX_Kalan_Sure": ("Hedef SL - geçen süre (saat); negatif = gecikmiş. Geçen süre çoğunlukla Başlangıç'tan "
                           "sayılıyor ama bazı kayıtlarda saat duruyor/sınırlanıyor (ör. Cihaz İade'de -72'de, "
                           "Bağlantı'da -36'da donmuş kayıtlar). Yaşlandırma için güvenilmez; yaş Başlangıç'tan "
                           "hesaplanmalı."),
        "Teknik_Ekip_SL_Suresi_Dk": ("Teknisyenin 'konum paylaş' (yola çıktım) anından 'işe başla' anına kadar geçen "
                                     "dakika; işe başlanmadıysa konum paylaşımından export anına kadar geçen dakika. "
                                     "Konum paylaşılmayan kayıtlarda 0. Yani varış/yol süresi göstergesi, task SL'i değil."),
    }
    R["sla"]["boss_hedef_saat_tip"] = {k: v for k, v in boss_hedef.items()}
    R["sla"]["fox_hedef_saat_tip"] = {k: int(v) for k, v in fh.items()}
    R["sla"]["boss_sl_tip"] = sla_boss_tip
    R["sla"]["fox_kalan_tutarlilik"] = dict(
        n=len(g2), fark_3saat_ici=float((g2.fark_bas.abs() <= 3).mean()),
        fark_q=q(g2.fark_bas), negatif_kalan=int((f.kalan_h < 0).sum()),
        negatif_kalan_orani_hedefli=float((g2.kalan_h < 0).mean()))
    k_ = b[b["Teknik Ekip SL Süresi(Dk)"] != 0]
    ibkp = (b["Teknik Ekip İşe Başlama Tarihi"] - b["Teknik Ekip Konum Paylaşma Tarihi"]).dt.total_seconds() / 60
    R["sla"]["teknik_ekip_sl_dk"] = dict(sifir_disi=len(k_), konum_paylasilan=int(b["Teknik Ekip Konum Paylaşma Tarihi"].notna().sum()),
                                         ise_baslanan=int(b["Teknik Ekip İşe Başlama Tarihi"].notna().sum()),
                                         bitirilen=int(b["Teknik Ekip Bitirme Tarihi"].notna().sum()),
                                         ikisi_de_dolu=int(ibkp.notna().sum()),
                                         ayni_dakikada_basilan=int((ibkp.abs() < 60 / 60).sum()),
                                         ayni_dakikada_orani=float((ibkp.abs() < 1).sum() / max(ibkp.notna().sum(), 1)),
                                         pozitif_1dk_ustu_dk=q(ibkp[ibkp >= 1]),
                                         not_=("Teknisyenler 'konum paylaş' ve 'işe başla'yı çoğunlukla aynı anda (varışta) "
                                               "basıyor -> yol süresi bu alanlardan ölçülemiyor."))

    # SLA ihlali (kanonik tip bazında; 3 ölçü)
    def fox_hedef(kod):
        x = f.loc[(f.kod == kod) & (f["Hedef SL"] > 0), "Hedef SL"]
        return float(x.mode().iloc[0]) if len(x) else None
    sla_kod = {}
    for kod, g in b.groupby("kod"):
        bh = boss_hedef.reindex(g["Task Adı"].unique()).dropna()
        fhk = fox_hedef(kod)
        sla_kod[kod] = dict(
            n=len(g), sahip=TX.KOD[kod]["sahip"] if kod in TX.KOD else None,
            boss_hedef_saat=float(bh.min()) if len(bh) else None, fox_hedef_saat=fhk,
            boss_sl_gecti=int((g.SL == "SL Geçti").sum()),
            boss_sl_tanimsiz=int(g.SL.isna().sum()),
            yas_24s_ustu=int((g.yas_h > 24).sum()), yas_24s_ustu_oran=float((g.yas_h > 24).mean()),
            fox_hedef_asimi=(int((g.yas_h > fhk).sum()) if fhk else None),
            yas_medyan_saat=float(g.yas_h.median()), yas_dagilimi=yas_dagilimi(g.yas_h))
    R["sla"]["ihlal_kanonik"] = sla_kod
    for s in ["mevcut_musteri", "yeni_musteri_kurulum"]:
        g = b[b.sahip == s]
        R["sla"][f"yas_{s}"] = dict(n=len(g), dagilim=yas_dagilimi(g.yas_h), medyan_saat=float(g.yas_h.median()),
                                    yas_24s_ustu_oran=float((g.yas_h > 24).mean()),
                                    boss_sl_gecti=int((g.SL == "SL Geçti").sum()), boss_sl_gecmedi=int((g.SL == "SL Geçmedi").sum()),
                                    boss_sl_yok=int(g.SL.isna().sum()))
    R["sla"]["yas_tum"] = yas_dagilimi(b.yas_h)

    # Gerçek 24 saat uyumu (kohort): 1-14 Eylül'de açılan mevcut-müşteri task'ları
    an2 = an.copy(); an2.columns = [str(c).strip() for c in an2.columns]
    an2 = an2[pd.to_datetime(an2["TARİH"], errors="coerce").notna()].copy()
    an2["TARİH"] = pd.to_datetime(an2["TARİH"])
    an2 = an2[an2["TARİH"] <= "2026-09-15"]
    gelen = an2.set_index(an2["TARİH"].dt.date)["GELEN"].astype(float)
    # 16 Eylül satırı toplam satırı (4847 = 1-15 toplamı) -> ayıklandı
    t["bas_gun"] = t["Task Başlangıç Tarihi"].dt.date
    coh = t[t["Task Başlangıç Tarihi"] < "2026-09-15"]
    ok24 = coh[(coh["Task Durumu"] == "Tamamlandı") & (coh.sure_h <= 24)]
    den = gelen[[d for d in gelen.index if str(d) < "2026-09-15"]].sum()
    comp = {}
    for lim in (6, 12, 24, 48, 72):
        comp[f"{lim}s"] = float(((coh["Task Durumu"] == "Tamamlandı") & (coh.sure_h <= lim)).sum() / den)
    # tip bazında payda tahmini: T tipi + (açık kalan) * BOSS'ta bugün hâlâ açık olan 1-15 Eylül kohortunun tip payı
    acik_1_15 = b[(b["Task Başlangıç Tarihi"] >= "2026-09-01") & (b["Task Başlangıç Tarihi"] < "2026-09-16") & (b.sahip == "mevcut_musteri")]
    kalan_1_15 = float(gelen.sum() - len(t))
    # T kapsamı: 2.Donanım/Yan Oda gibi tipler TAMAMLANDI'da yok -> tahmin kapsamı T'deki tiplerle sınırlı
    kapsam = set(t.kod.unique())
    # 16 Eylül'de açık kalan 1.180 işin tip dağılımı bilinmiyor. Bugün (29 Eylül) açık olan ve yaşı ≤15 gün
    # olan mevcut-müşteri işleri aynı 'yaş penceresinin' anlık görüntüsü -> durağanlık varsayımıyla onun tip payı.
    ref_pencere = b[(b.sahip == "mevcut_musteri") & (b.yas_h <= 15 * 24) & b.kod.isin(kapsam)]
    pay_acik_k = ref_pencere.kod.value_counts(normalize=True)
    tip24 = {}
    for kod in sorted(kapsam):
        n_t = int((coh.kod == kod).sum())
        est_open_14 = kalan_1_15 * pay_acik_k.get(kod, 0) * (den / gelen.sum())
        d_ = n_t + est_open_14
        done = (coh.kod == kod) & (coh["Task Durumu"] == "Tamamlandı")
        fhk = {"BAGLANTI": 12, "TV_ARIZA": 6, "ARAMA": 12, "KANAL_SIKAYETI": 24, "DOPING_ARIZA": 24,
               "CIHAZ_IADE": 24, "CIHAZ_GERI_ALIM": 48}.get(kod)
        tip24[kod] = dict(tamamlanan_kohort=n_t, tahmini_acik_kalan=round(est_open_14, 1),
                          uyum_24s=(float((done & (coh.sure_h <= 24)).sum() / d_) if d_ else None),
                          fox_hedef_saat=fhk,
                          uyum_fox_hedef=(float((done & (coh.sure_h <= fhk)).sum() / d_) if (d_ and fhk) else None))
    R["sla"]["gercek_24s_uyum_kohort"] = dict(
        tanim=("1-14 Eylül'de açılan mevcut-müşteri task'larından kaçı açılıştan sonraki X saat içinde tamamlandı. "
               "Payda = ANLATILAN 'GELEN' (günlük açılan), pay = TAMAMLANDI'da süresi ≤X saat olanlar. 24 saat içinde "
               "kapanan her task TAMAMLANDI'da görünür (export 16 Eylül sabahı), bu yüzden oran sansürsüz."),
        payda_gelen=float(den), orani=comp, tip_bazinda=tip24,
        acik_1_15_bugun_hala_acik_mevcut=len(acik_1_15), anlatilan_16_eylul_acik=kalan_1_15)
    ok_gun = ok24.groupby(ok24["Task Başlangıç Tarihi"].dt.date).size()
    R["sla"]["gunluk_24s_uyum_acilis_gunune_gore"] = {
        str(d): dict(gun=GUN[pd.Timestamp(d).dayofweek], gelen=int(gelen[d]), ok24=int(ok_gun.get(d, 0)),
                     oran=float(ok_gun.get(d, 0) / gelen[d])) for d in gelen.index if str(d) < "2026-09-15"}
    ok_h = ok24["Task Başlangıç Tarihi"].dt.hour.value_counts()
    all_h = pd.concat([coh["Task Başlangıç Tarihi"], acik_1_15.loc[acik_1_15["Task Başlangıç Tarihi"] < "2026-09-15", "Task Başlangıç Tarihi"]]).dt.hour.value_counts()
    # payda yalnızca TAMAMLANDI + bugün hâlâ açık olanlar (16 Eylül'de açık olup sonra kapananlar eksik) -> ÜST SINIR
    R["sla"]["acilis_saatine_gore_24s_uyum_ust_sinir"] = {
        int(h): float(ok_h.get(h, 0) / all_h[h]) for h in sorted(all_h.index) if all_h[h] >= 30}
    R["sla"]["anlik_24s_uyum"] = dict(
        tum_acik_24s_ustu=float((b.yas_h > 24).mean()),
        mevcut_acik_24s_ustu=float((b[b.sahip == "mevcut_musteri"].yas_h > 24).mean()),
        yeni_acik_24s_ustu=float((b[b.sahip == "yeni_musteri_kurulum"].yas_h > 24).mean()))
    # tamamlanan süreleri (kapatan türüne göre)
    R["sla"]["tamamlanma_suresi_saat"] = {
        "tum": q(tt.sure_h), "saha_teknisyeni": q(tt[tt.kapatan == "saha_teknisyeni"].sure_h),
        "ofis_operasyon": q(tt[tt.kapatan == "ofis_operasyon"].sure_h),
        "tip": {k: q(g.sure_h) for k, g in tt.groupby("kod") if len(g) >= 5},
        "not": "Sağdan sansürlü: 16 Eylül'e kadar kapanmayanlar yok -> gerçek süreler daha uzun."}

    # ============================================================ 3. BİRİKİM
    b["randevu_konum"] = np.select(
        [b["Randevu Başlangıç Tarihi"].isna(),
         b["Randevu Bitiş Tarihi"] < REF,
         b["Randevu Başlangıç Tarihi"] < REF.normalize() + pd.Timedelta(days=1)],
        ["randevusuz", "randevu_gecmis", "randevu_bugun"], "randevu_ileri_tarih")

    def aciklama_grup(s):
        if pd.isna(s):
            return "(boş)"
        n = TX.norm(s)
        if any(w in n for w in ["ULASILAMA", "CEVAPSIZ", "CEVAP VERM", "CVP VERM", "ULASILAMIYOR", "ACMIYOR"]):
            return "musteriye_ulasilamadi"
        if "ETIKET" in n:
            return "tt_etiketleme_bekliyor"
        if "RANDEVU" in n or "ILERI TARIH" in n or "ERTELE" in n:
            return "musteri_ileri_tarih_istedi"
        if "GUZERGAH" in n:
            return "guzergah"
        if "STOK" in n or "DEPO" in n:
            return "stok_cihaz_yok"
        if "TESLIM" in n:
            return "musteri_cihazi_teslim_edecek"
        if "PORT" in n or "SINYAL" in n or "KAPASITE" in n or "EK SP" in n:
            return "port_sinyal_kapasite"
        if "EKIP" in n or "ATAMA" in n or "ILETILDI" in n or "IELTILDI" in n or "ILEITLDI" in n:
            return "ekibe_atandi_notu"
        if "IPTAL" in n:
            return "iptal_istegi"
        return "diger"
    b["aciklama_grup"] = b["Son Açıklama"].map(aciklama_grup)
    b["atanmis"] = np.where(b["Ekip"].notna(), "ekip_atanmis", "ekip_yok")

    def aksiyon(r):
        if TX.KOD.get(r["kod"], {}).get("saha") == "hayir" or r["kod"] == "CIHAZ_IADE":
            return "C_ofisten_kapatilabilir"
        if r["Task Durumu"] == "Askıya alındı" or pd.notna(r["Askıya Alınma Nedeni"]):
            if r["Askıya Alınma Nedeni"] == "TT kaynaklı":
                return "D_dis_bagimli_TT"
            return "B_askida_abone_takip"
        if r["Task Durumu"] == "Merkeze gönderildi":
            return "B_merkezde_operasyon_aksiyonu"
        if r["randevu_konum"] == "randevu_ileri_tarih":
            return "E_ileri_tarihli_randevu"
        return "A_bugun_sahaya_verilebilir"
    b["aksiyon"] = b.apply(aksiyon, axis=1)
    R["birikim"]["aksiyon_tanimi"] = {
        "A_bugun_sahaya_verilebilir": "Açık/Konum paylaşıldı/Başlandı, askıda değil, ileri tarihli randevusu yok, saha gerektiren tip.",
        "B_askida_abone_takip": "Abone kaynaklı askı (müşteri müsait değil vb.) -> operasyon tekrar arayıp randevu verir.",
        "B_merkezde_operasyon_aksiyonu": "Teknisyen 'merkeze gönderdi' (ulaşılamadı, güzergah/sinyal/port yok...) -> ofis çözer.",
        "C_ofisten_kapatilabilir": ("Saha gerektirmeyen tipler: Kanal Şikayeti (%98 'müşteri düzeldi dedi' ile ofisten "
                                    "kapanıyor), Cihaz İade (lojistik), FOX ofis işleri -> telefonla/ofisten kapatılır."),
        "D_dis_bagimli_TT": "TT kaynaklı askı (etiketleme vb.) -> dış bağımlı, takip.",
        "E_ileri_tarihli_randevu": "Randevusu yarın veya sonrasında.",
    }
    bir = {}
    for s, g in b.groupby("sahip"):
        bir[s] = dict(
            n=len(g), durum=vc(g["Task Durumu"]), aski_nedeni=vc(g["Askıya Alınma Nedeni"]),
            merkeze_gonder=vc(g["Merkeze Gönder Statüsü"]), randevu=vc(g["Randevu Durumu"]),
            randevu_konum=vc(g["randevu_konum"]), atanmis=vc(g["atanmis"]), aksiyon=vc(g["aksiyon"]),
            aciklama_grup=vc(g["aciklama_grup"]), ilce=vc(g["İlçe"]), segment=vc(g["Segment"]), urun=vc(g["Ürün Bilgisi"]),
            btk=int(g.btk.sum()))
    R["birikim"]["sahip"] = bir
    R["birikim"]["tip_x_durum"] = ct(b["kod"], b["Task Durumu"])
    R["birikim"]["tip_x_aksiyon"] = ct(b["kod"], b["aksiyon"])
    R["birikim"]["tip_x_aski"] = ct(b["kod"], b["Askıya Alınma Nedeni"])
    R["birikim"]["tip_x_randevu"] = ct(b["kod"], b["randevu_konum"])
    R["birikim"]["tip_x_atama"] = ct(b["kod"], b["atanmis"])
    R["birikim"]["tip_x_yas"] = {k: yas_dagilimi(g.yas_h) for k, g in b.groupby("kod")}
    R["birikim"]["tip_x_aciklama"] = ct(b["kod"], b["aciklama_grup"])
    R["birikim"]["tip_x_merkeze"] = ct(b["kod"], b["Merkeze Gönder Statüsü"])
    R["birikim"]["ilce_x_sahip"] = ct(b["İlçe"], b["sahip"])
    R["birikim"]["fox_akis_statusu_x_boss_durum"] = ct(
        j["Akış Statüsü"], j.merge(b[["Task No", "Task Durumu"]], on="Task No", how="left")["Task Durumu"])
    R["birikim"]["fox_akis_tipi_x_sahip"] = ct(f["Akış Tipi"], f["sahip"])
    R["birikim"]["fox_dosya_x_kod"] = ct(f["kod"], f["fox_dosya"])
    R["birikim"]["fox_kanal_x_sahip"] = ct(f["Siparişi Oluşturan Kanal Bilgisi"].fillna("(boş)").str.upper(), f["sahip"])
    # "askı" süresi: askıdaki mevcut-müşteri işlerinin yaşı
    aski = b[(b["Task Durumu"] == "Askıya alındı")]
    R["birikim"]["askidaki_yas"] = {s: yas_dagilimi(g.yas_h) for s, g in aski.groupby("sahip")}

    # ============================================================ 4. GİRİŞ (inflow)
    b["bas_gun"] = b["Task Başlangıç Tarihi"].dt.normalize()
    son30 = b[b["bas_gun"] >= REF.normalize() - pd.Timedelta(days=30)]
    gunluk = son30.groupby([son30.bas_gun.dt.date.astype(str), "sahip"]).size().unstack(fill_value=0)
    R["giris"]["boss_acik_gunluk_son30_sansurlu"] = gunluk.to_dict(orient="index")
    R["giris"]["boss_acik_tip_son14_sansurlu"] = ct(
        b.loc[b.bas_gun >= REF.normalize() - pd.Timedelta(days=14), "kod"],
        b.loc[b.bas_gun >= REF.normalize() - pd.Timedelta(days=14), "bas_gun"].dt.date.astype(str))
    # son 24 saat / son 7 gün (hala açık) -> alt sınır
    alt = {}
    for s, g in b.groupby("sahip"):
        alt[s] = dict(son_24s=int((g.yas_h <= 24).sum()),
                      son_7g_gunluk_ort=float(((g.yas_h > 0) & (g.yas_h <= 168)).sum() / 7),
                      tip_son_7g_gunluk=({k: round(v / 7, 2) for k, v in g[g.yas_h <= 168].kod.value_counts().items()}))
    R["giris"]["alt_sinir_hala_acik"] = alt
    # Sansürsüz (mevcut müşteri) : ANLATILAN GELEN
    gl = gelen.copy(); gl.index = pd.to_datetime(gl.index)
    R["giris"]["mevcut_gelen_gunluk_1_15_eylul"] = {str(d.date()): int(v) for d, v in gl.items()}
    wd = gl.groupby(gl.index.dayofweek).mean()
    R["giris"]["mevcut_gelen_haftanin_gunu_ort"] = {GUN[i]: float(v) for i, v in wd.items()}
    R["giris"]["mevcut_gelen_ozet"] = dict(
        toplam_15_gun=int(gl.sum()), takvim_gunu_ort=float(gl.mean()),
        hafta_ici_ort=float(gl[gl.index.dayofweek < 5].mean()),
        cumartesi_ort=float(gl[gl.index.dayofweek == 5].mean()), pazar_ort=float(gl[gl.index.dayofweek == 6].mean()),
        hafta_ici_std=float(gl[gl.index.dayofweek < 5].std()))
    yap = an2.set_index(an2["TARİH"].dt.date)[["YAPILAN", "EKİP SAYISI", "ARIZACI", "KRLMCU", "OFİS"]]
    R["giris"]["anlatilan_yapilan_gunluk"] = {str(k): {c: (None if pd.isna(v) or isinstance(v, str) else float(v))
                                                       for c, v in r.items()} for k, r in yap.iterrows()}
    # tip bazında sansürsüz tahmin
    tip_in = {}
    for kod in sorted(kapsam):
        n_t = int((t.kod == kod).sum())
        est = kalan_1_15 * pay_acik_k.get(kod, 0)
        tip_in[kod] = dict(tamamlanan=n_t, tahmini_acik_kalan=round(est, 1),
                           gunluk_ort=round((n_t + est) / 15, 2))
    R["giris"]["mevcut_tip_bazinda_gunluk_tahmin"] = tip_in
    tot = sum(v["gunluk_ort"] for v in tip_in.values())
    R["giris"]["mevcut_tip_payi"] = {k: round(v["gunluk_ort"] / tot, 4) for k, v in tip_in.items()}
    # saatlik varış profili (mevcut): TAMAMLANDI + hâlâ açık 1-15 Eylül (varış saatine göre)
    arr = pd.concat([t["Task Başlangıç Tarihi"], acik_1_15["Task Başlangıç Tarihi"]])
    R["giris"]["mevcut_varis_saat_profili"] = {int(h): float(v) for h, v in arr.dt.hour.value_counts(normalize=True).sort_index().items()}
    arr_y = b.loc[(b.sahip == "yeni_musteri_kurulum") & (b.yas_h <= 24 * 14), "Task Başlangıç Tarihi"]
    R["giris"]["kurulum_varis_saat_profili_sansurlu"] = {int(h): float(v) for h, v in arr_y.dt.hour.value_counts(normalize=True).sort_index().items()}
    R["giris"]["haftanin_gunu_sansurlu_son28"] = ct(
        b.loc[b.yas_h <= 24 * 28, "sahip"], b.loc[b.yas_h <= 24 * 28, "Task Başlangıç Tarihi"].dt.dayofweek.map(lambda i: GUN[i]))
    R["giris"]["sansur_notu"] = (
        "BOSS/FOX export'ları yalnızca HÂLÂ AÇIK işleri içerir; kapanmış işler görünmez. Bu yüzden açık dosyadan "
        "sayılan 'günlük açılış' her gün için bir ALT SINIRdır ve eski günlerde (kapananlar düştükçe) sistematik "
        "olarak küçülür. Mevcut-müşteri için sansürsüz tahmin ANLATILAN 'GELEN' (= o gün açılan tüm task; "
        "TAMAMLANDI + 16 Eylül'de açık kalan) ile yapıldı. Kurulum için sansürsüz kaynak yok; kapanmış kurulum "
        "raporu (BOSS 'Tamamlandı' filtresi) gerekir.")

    # ============================================================ 5. TEKNİSYEN / COĞRAFYA
    ekip = b.groupby("Ekip").agg(n=("Task No", "size"), mevcut=("sahip", lambda s: int((s == "mevcut_musteri").sum())),
                                 btk=("btk", "sum"), ilce_sayisi=("İlçe", "nunique"),
                                 yas_medyan_saat=("yas_h", "median")).sort_values("n", ascending=False)
    R["teknisyen"]["boss_acik_ekip_yuku"] = {k: {c: py(v) for c, v in r.items()} for k, r in ekip.iterrows()}
    R["teknisyen"]["boss_acik_ekip_ozet"] = dict(ekip_sayisi=int(b.Ekip.nunique()), atanmis_is=int(b.Ekip.notna().sum()),
                                                  atanmamis_is=int(b.Ekip.isna().sum()), is_basina_q=q(ekip.n))
    R["teknisyen"]["boss_teknisyen_alani"] = dict(
        dolu=int(b.Teknisyen.notna().sum()), kisi=int(b.Teknisyen.nunique()), pozisyon=vc(b.Pozisyon.dropna()),
        not_=("BOSS 'Teknisyen' alanı saha teknisyeni değil, işi üstlenen kullanıcı; açık export'ta dolu olanların "
              "pozisyonu çoğunlukla 'Satış Destek - Sorumlu' (operasyon)."))
    # arızacı listesi (ANLATILAN PIVOT sütunları)
    ariza_ekibi = [TX.norm(c) for c in anp.columns[1:] if TX.norm(c) not in ("OFIS", "GENEL TOPLAM", "")]
    tt2 = tt.copy()
    tt2["tek_n"] = tt2["Teknisyen"].map(TX.norm)
    tt2["bit_gun"] = tt2["Task Bitiş Tarihi"].dt.date
    fld = tt2[(tt2.kapatan == "saha_teknisyeni") & (tt2["Task Bitiş Tarihi"] >= "2026-09-03")]
    td = fld.groupby(["tek_n", "bit_gun"]).size()
    td_ar = td[td.index.get_level_values(0).isin(ariza_ekibi)]
    aktif_gun = fld.groupby("bit_gun")["tek_n"].nunique()
    aktif_ar = fld[fld.tek_n.isin(ariza_ekibi)].groupby("bit_gun")["tek_n"].nunique()
    # ardışık kapanış aralığı (dk) -> saha döngü süresi vekili
    fld_s = fld.sort_values("Task Bitiş Tarihi")
    gaps = fld_s.groupby(["tek_n", "bit_gun"])["Task Bitiş Tarihi"].diff().dt.total_seconds() / 60
    span = fld_s.groupby(["tek_n", "bit_gun"])["Task Bitiş Tarihi"].agg(lambda s: (s.max() - s.min()).total_seconds() / 3600)
    first = fld_s.groupby(["tek_n", "bit_gun"])["Task Bitiş Tarihi"].min().dt.hour + fld_s.groupby(["tek_n", "bit_gun"])["Task Bitiş Tarihi"].min().dt.minute / 60
    last = fld_s.groupby(["tek_n", "bit_gun"])["Task Bitiş Tarihi"].max().dt.hour + fld_s.groupby(["tek_n", "bit_gun"])["Task Bitiş Tarihi"].max().dt.minute / 60
    R["teknisyen"]["tamamlanan_verimlilik_3_15_eylul"] = dict(
        ariza_ekibi_kisi=len(ariza_ekibi),
        ariza_ekibi_gunluk_is_per_teknisyen=q(td_ar),
        tum_saha_gunluk_is_per_teknisyen=q(td),
        gunluk_aktif_saha_teknisyeni=q(aktif_gun), gunluk_aktif_ariza_teknisyeni=q(aktif_ar),
        ardisik_kapanis_arasi_dk=q(gaps[(gaps > 0)]),
        ardisik_kapanis_arasi_dk_5_180=q(gaps[(gaps >= 5) & (gaps <= 180)]),
        toplu_kapanis_orani_5dk_alti=float(((gaps >= 0) & (gaps < 5)).sum() / gaps.notna().sum()),
        gun_ici_ilk_kapanis_saati=q(first), gun_ici_son_kapanis_saati=q(last),
        ilk_son_kapanis_arasi_saat=q(span[td.reindex(span.index) >= 3]),
        teknisyen_basina_toplam={k: int(v) for k, v in fld.tek_n.value_counts().items()},
        not_=("Sahadaki gerçek iş süresi (İşe Başlama->Bitirme) kapanmış işlerde yok (TAMAMLANDI'da sütun yok, açık "
              "export'ta yalnızca 2 bitirme var). Döngü süresi (yol + iş) vekili: aynı teknisyenin aynı gün ardışık "
              "iki kapanışı arasındaki süre. <5 dk aralıklar toplu (sonradan) kapanış işaretidir."))
    ofis_pay = tt2[tt2["Task Bitiş Tarihi"] >= "2026-09-03"]
    R["teknisyen"]["ofis_kapanis"] = dict(
        oran_3_15_eylul=float((ofis_pay.kapatan == "ofis_operasyon").mean()),
        oran_12_eylul_haric=float((ofis_pay[ofis_pay.bit_gun != pd.Timestamp("2026-09-12").date()].kapatan == "ofis_operasyon").mean()),
        gunluk={str(k): int(v) for k, v in ofis_pay[ofis_pay.kapatan == "ofis_operasyon"].groupby("bit_gun").size().items()},
        tip=vc(ofis_pay.loc[ofis_pay.kapatan == "ofis_operasyon", "kod"]))
    R["teknisyen"]["ekip_listesi_birlesik"] = dict(
        boss_acik_ekip=int(b.Ekip.nunique()), tamamlandi_ekip=int(t.Ekip.nunique()),
        birlesik_saha_ismi=len(fieldset), ariza_ekibi=len(ariza_ekibi),
        ekip_sayisi_gunluk_anlatilan=q(an2["EKİP SAYISI"].astype(float)))

    # coğrafya
    bl = lokasyon_bagla(b, m)
    tl = lokasyon_bagla(t, m)
    R["teknisyen"]["lokasyon_eslesme"] = dict(
        boss=vc(bl.eslesme), boss_konumlu_oran=float(bl.lat.notna().mean()),
        boss_mevcut_konumlu_oran=float(bl[bl.sahip == "mevcut_musteri"].lat.notna().mean()),
        boss_yeni_konumlu_oran=float(bl[bl.sahip == "yeni_musteri_kurulum"].lat.notna().mean()),
        boss_lokasyon_dolu_icinde_eslesme=float(bl[bl.eslesme != "lokasyon_yok"].lat.notna().mean()),
        tip_konumlu_oran={k: float(g.lat.notna().mean()) for k, g in bl.groupby("kod")},
        tamamlandi=vc(tl.eslesme), tamamlandi_konumlu_oran=float(tl.lat.notna().mean()),
        not_=("Lokasyon boş olan tipler: Superbox (kablosuz), Kanal Şikayeti, TT Fiber, Kurulum ve Cihaz Gönderim, "
              "çoğu Cihaz İade -> bunlar için yalnızca ilçe var. 'master_da_yok' = tur raporunda olmayan binalar "
              "(yeni eklenmiş olabilir)."))
    R["teknisyen"]["kume_acik_tum"] = kume_analizi(bl)
    R["teknisyen"]["kume_acik_mevcut"] = kume_analizi(bl[bl.sahip == "mevcut_musteri"])
    R["teknisyen"]["kume_acik_mevcut_saha"] = kume_analizi(bl[(bl.sahip == "mevcut_musteri") & (bl.aksiyon == "A_bugun_sahaya_verilebilir")])
    R["teknisyen"]["kume_acik_yeni"] = kume_analizi(bl[bl.sahip == "yeni_musteri_kurulum"])
    # tipik bir günün girişi (mevcut, konumlu) ne kadar kümeli? -> 1-15 Eylül her gün ayrı
    tl["bas_gun"] = tl["Task Başlangıç Tarihi"].dt.date
    gun_k = []
    for d, g in tl.groupby("bas_gun"):
        r = kume_analizi(g)
        if r.get("n", 0) > 20:
            gun_k.append(dict(gun=str(d), n=r["n"], nn_medyan_m=r["en_yakin_komsu_m"]["p50"],
                              komsu500_orani=r["komsu_500m"]["en_az_1_komsu_orani"],
                              komsu2000_ort=r["komsu_2000m"]["ort_komsu"]))
    R["teknisyen"]["gunluk_giris_kumelenme_tamamlanan"] = gun_k
    # teknisyenin bir gündeki işlerinin yayılımı (tamamlanan, konumlu)
    tl["tek_n"] = tl["Teknisyen"].map(TX.norm)
    tl["bit_gun"] = tl["Task Bitiş Tarihi"].dt.date
    sp = []
    for (tn, d), g in tl[tl.tek_n.isin(fieldset) & tl.lat.notna()].groupby(["tek_n", "bit_gun"]):
        if len(g) >= 4:
            P = xy(g.lat.values, g.lon.values)
            c = P.mean(axis=0)
            sp.append(dict(n=len(g), yaricap_m=float(np.median(np.linalg.norm(P - c, axis=1))),
                           ilce=g.ilce.nunique()))
    sp = pd.DataFrame(sp)
    R["teknisyen"]["teknisyen_gunluk_yayilim"] = dict(
        teknisyen_gun=len(sp), medyan_yaricap_m=q(sp.yaricap_m) if len(sp) else {},
        ilce_sayisi=q(sp.ilce) if len(sp) else {},
        not_="Aynı teknisyenin aynı gün kapattığı (≥4, konumlu) işlerin ağırlık merkezine medyan uzaklığı.")
    ilce_m = bl[bl.sahip == "mevcut_musteri"].groupby("İlçe").size().sort_values(ascending=False)
    R["teknisyen"]["mevcut_acik_ilce"] = {k: int(v) for k, v in ilce_m.items()}
    mah = bl[(bl.sahip == "mevcut_musteri") & bl.mahalle.notna()].groupby(["ilce", "mahalle"]).size().sort_values(ascending=False).head(25)
    R["teknisyen"]["mevcut_acik_mahalle_top25"] = [dict(ilce=i, mahalle=mh, n=int(v)) for (i, mh), v in mah.items()]
    R["teknisyen"]["ofis_uzaklik_km_mevcut_acik"] = q(bl[bl.sahip == "mevcut_musteri"].ofis_km)

    # ============================================================ 6. RANDEVU
    rv = b[b["Randevu Başlangıç Tarihi"].notna()].copy()
    rv["bas_randevu_saat"] = (rv["Randevu Başlangıç Tarihi"] - rv["Task Başlangıç Tarihi"]).dt.total_seconds() / 3600
    rv["pencere_saat"] = (rv["Randevu Bitiş Tarihi"] - rv["Randevu Başlangıç Tarihi"]).dt.total_seconds() / 3600
    rv["ileri_gun"] = (rv["Randevu Başlangıç Tarihi"].dt.normalize() - REF.normalize()).dt.days
    R["randevu"] = dict(
        randevu_durumu=vc(b["Randevu Durumu"]), randevu_tarihli=len(rv),
        sahip=ct(b["sahip"], b["randevu_konum"]),
        acilistan_randevuya_saat=q(rv.bas_randevu_saat), acilistan_randevuya_saat_sahip={s: q(g.bas_randevu_saat) for s, g in rv.groupby("sahip")},
        pencere_saat=vc(rv.pencere_saat.round(1)),
        randevu_saat_basi=vc(rv["Randevu Başlangıç Tarihi"].dt.hour),
        gecmis_randevu_hala_acik=int((rv["Randevu Bitiş Tarihi"] < REF).sum()),
        gecmis_randevu_durum=vc(rv.loc[rv["Randevu Bitiş Tarihi"] < REF, "Task Durumu"]),
        gecmis_randevu_gecikme_gun=q((REF - rv.loc[rv["Randevu Bitiş Tarihi"] < REF, "Randevu Bitiş Tarihi"]).dt.total_seconds() / 86400),
        gecmis_randevu_tip=vc(rv.loc[rv["Randevu Bitiş Tarihi"] < REF, "kod"]),
        ileri_tarih_gun=vc(rv.loc[rv.ileri_gun >= 0, "ileri_gun"]),
        randevulu_tip=vc(rv.kod),
        randevulu_ekip_atanmis_orani=float(rv.Ekip.notna().mean()),
        randevu_x_ekip=ct(b["Randevu Durumu"], b["atanmis"]),
        yorum=("BOSS'ta 'Randevulu' = işin bir ekibe 2 saatlik zaman dilimiyle atanması (randevulu işlerin %98'inde "
               "Ekip dolu, randevusuzların hiçbirinde yok). Yani 'randevu' müşteriyle kararlaştırılmış saatten çok "
               "sevk (dispatch) kaydı; 'geçmiş randevu + hâlâ açık' = sevk edilmiş ama kapanmamış iş."),
        randevusuz_ekip_atanmis_orani=float(b.loc[b["Randevu Başlangıç Tarihi"].isna(), "Ekip"].notna().mean()),
        not_="Randevu alanları yalnızca BOSS'ta; TAMAMLANDI'daki 3.667 kapanışın tamamı 'Randevusuz'.")

    # ============================================================ 7. PS26
    P = SRC["ps26"]
    tk_ = pd.read_excel(P, sheet_name="TICKET")
    gz = pd.read_excel(P, sheet_name="GUZERGAH").dropna(how="all")
    gz = gz[gz[["Lokasyon", "Konu", "Musteri"]].notna().any(axis=1)]
    gz_all = pd.read_excel(P, sheet_name="GUZERGAH")
    al = pd.read_excel(P, sheet_name="ALTYAPI")
    pv = pd.read_excel(P, sheet_name="PVT")
    orj = pd.read_excel(P, sheet_name="ORIGN")
    ids = set(m.location_id)

    def loc_match(s):
        s = s.dropna().astype(str).str.strip()
        return float((s.isin(ids) | s.str.lstrip("0").isin(ids)).mean()) if len(s) else None
    tk_["yas_gun"] = (REF.normalize() - pd.to_datetime(tk_["Baslangic"])).dt.days
    boss_sinyal_loc = set(b.loc[b["Merkeze Gönder Statüsü"].isin(["SİNYAL YOK", "BOŞ PORT YOK"]), "Lokasyon"].dropna().astype(str))
    boss_guz_loc = set(b.loc[b["Merkeze Gönder Statüsü"] == "GÜZERGAH YOK", "Lokasyon"].dropna().astype(str))
    tk_loc = set(tk_.Lokasyon.dropna().astype(str)); gz_loc = set(gz.Lokasyon.dropna().astype(str))
    orj_loc_col = [c for c in orj.columns if TX.norm(c) == "LOCATION ID"]
    orj_ids = set(orj[orj_loc_col[0]].dropna().astype(str)) if orj_loc_col else set()
    R["ps26"] = dict(
        ORIGN=dict(satir=len(orj), sutun=len(orj.columns), location_id_master_ile_ortak=len(orj_ids & ids),
                   sadece_orjinde=len(orj_ids - ids), sadece_masterda=len(ids - orj_ids),
                   surec="Tur raporu (fiber bina envanteri: HP, aktif abone, altyapı, sales-ready). Bölgeleme ve LOCS'un kaynağı."),
        LOCS=dict(satir_dolu_bina=19707, surec=(
            "BTK acil sinyal ticket'ı metin şablonu ('*BTK ÇAĞRISI ACİL MÜDAHALE* … sinyal zayıftır') + bina arama "
            "tablosu (Bina Serial, Tellcordia ID, Location Id, Öbek, Site Adı). OneDesk ticket'ı açarken lokasyon "
            "bilgisini kopyalamak için kullanılıyor; OPENED = bugün."), musteri_no_dolu=int(pd.read_excel(P, sheet_name="LOCS").iloc[:, 8].notna().sum())),
        TICKET=dict(
            n=len(tk_), konu=vc(tk_.Konu), durum=vc(tk_.Durum), konu_x_durum=ct(tk_.Konu, tk_.Durum), kanal=vc(tk_.Kanal),
            kanal_x_konu=ct(tk_.Kanal, tk_.Konu),
            ticket_no_dolu=int(tk_.Ticket.notna().sum()), ticket_no_bos_durum=vc(tk_.loc[tk_.Ticket.isna(), "Durum"]),
            aylik=vc(pd.to_datetime(tk_.Baslangic).dt.to_period("M").astype(str)),
            acik_yas_gun=q(tk_.loc[tk_.Durum == "AÇIK", "yas_gun"]),
            hata_yas_gun=q(tk_.loc[tk_.Durum == "HATA", "yas_gun"]),
            son_30_gun=int((tk_.yas_gun <= 30).sum()), son_30_gun_gunluk=round((tk_.yas_gun <= 30).sum() / 30, 2),
            lokasyon_master_eslesme=loc_match(tk_.Lokasyon),
            detay_dolu=int(tk_.Detay.notna().sum()),
            detay_tekrar_acildi=int(tk_.Detay.fillna("").map(TX.norm).str.contains("TEKRAR ACILDI").sum()),
            detay_ek_sp_musteri_eklenmeli=int(tk_.Detay.fillna("").map(TX.norm).str.contains("MUSTERI EKLENMELI").sum()),
            detay_reddedildi=int(tk_.Detay.fillna("").map(TX.norm).str.contains("RED").sum()),
            boss_sinyal_port_merkeze_lokasyon=len(boss_sinyal_loc), bunlardan_ticket_sayfasinda=len(boss_sinyal_loc & tk_loc),
            surec=("Sinyal zayıf/yok (SİNYAL, 132) ve ek splitter/kapasite (EK SP, 65) talepleri: lokasyon bazında OneDesk "
                   "(sinyal) / ONENT PYS 'Ek Kapasite' (EK SP) ticket'ı açılıp durum elle izleniyor. HATA = ticket "
                   "reddedildi/hatalı; Ticket no boş = henüz ticket açılamamış (çoğu EK SP HATA).")),
        GUZERGAH=dict(
            sayfa_satir=len(gz_all), gercek_kayit=len(gz), durum=vc(gz.Durum), kanal=vc(gz.Kanal),
            aylik=vc(pd.to_datetime(gz.Baslangic, errors="coerce").dt.to_period("M").astype(str)),
            site_turda_yok=int((gz.Site.astype(str).str.upper() == "TURDA YOK").sum()),
            lokasyon_master_eslesme=loc_match(gz.Lokasyon),
            boss_guzergah_yok_lokasyon=len(boss_guz_loc), bunlardan_guzergah_sayfasinda=len(boss_guz_loc & gz_loc),
            yas_gun=q((REF.normalize() - pd.to_datetime(gz.Baslangic, errors="coerce")).dt.days),
            surec=("Kurulumda 'güzergah yok' (binaya/daireye kablo yolu yok) çıkan işler. Sayfada 16.912 satır var ama "
                   "yalnızca ~64'ü dolu (geri kalanı boş/biçim satırı). Hepsi 'YOK' durumunda: kapanış/çözüm alanı yok.")),
        ALTYAPI=dict(
            n=len(al), kanal=vc(al.Kanal), aylik=vc(pd.to_datetime(al.Baslangic).dt.to_period("M").astype(str)),
            bolge_top=vc(al["Bölge"], 12), satici_sayisi=int(al.Satici.nunique()),
            yas_gun=q((REF.normalize() - pd.to_datetime(al.Baslangic)).dt.days),
            surec=("Altyapı kaynaklı gecikme/iptal: satışı yapılmış ama altyapı (port/fiber yok) yüzünden kurulamayan "
                   "müşteriler; satıcı ve bölge ile. Durum/çözüm sütunu yok.")),
        PVT=dict(n=len(pv), surec="ALTYAPI sayfasının satıcıya göre pivotu (toplam 66-67)."),
    )

    # ============================================================ PARAMETRELER (simülasyon)
    mv = b[b.sahip == "mevcut_musteri"]
    yn = b[b.sahip == "yeni_musteri_kurulum"]
    gi = R["giris"]["mevcut_gelen_ozet"]
    # telefon/ziyaretsiz oranları (mevcut, TAMAMLANDI 3-15 Eylül)
    tkm = tk[tk.sahip == "mevcut_musteri"]
    nov_all = (tkm.kapatan == "ofis_operasyon") | tkm.neden_grup.isin(["telefon_uzaktan", "sebeke_altyapi"])
    btk_m = tkm[tkm.kod.isin(["BAGLANTI", "TV_ARIZA", "ARAMA", "DOPING_ARIZA"])]
    nov_btk = (btk_m.kapatan == "ofis_operasyon") | btk_m.neden_grup.isin(["telefon_uzaktan", "sebeke_altyapi"])
    field_btk = btk_m[btk_m.kapatan == "saha_teknisyeni"]
    ver = R["teknisyen"]["tamamlanan_verimlilik_3_15_eylul"]
    R["parametreler"] = dict(
        referans_an=REF.isoformat(),
        gunluk_giris_mevcut=dict(takvim_ort=gi["takvim_gunu_ort"], hafta_ici=gi["hafta_ici_ort"],
                                 cumartesi=gi["cumartesi_ort"], pazar=gi["pazar_ort"], hafta_ici_std=gi["hafta_ici_std"],
                                 kaynak="ANLATILAN GELEN 1-15 Eylül (sansürsüz)"),
        gunluk_giris_mevcut_tip=R["giris"]["mevcut_tip_bazinda_gunluk_tahmin"],
        gunluk_giris_mevcut_tip_payi=R["giris"]["mevcut_tip_payi"],
        gunluk_giris_yeni_kurulum_alt_sinir=dict(son_24s_hala_acik=alt.get("yeni_musteri_kurulum", {}).get("son_24s"),
                                                 son_7g_gunluk_ort_hala_acik=alt.get("yeni_musteri_kurulum", {}).get("son_7g_gunluk_ort")),
        varis_saat_profili_mevcut=R["giris"]["mevcut_varis_saat_profili"],
        ziyaretsiz_kapanis_orani_mevcut=float(nov_all.mean()),
        ziyaretsiz_kapanis_orani_btk_ariza=float(nov_btk.mean()),
        telefon_uzaktan_neden_orani_btk_ariza=float(btk_m.neden_grup.eq("telefon_uzaktan").mean()),
        saha_kapanista_telefon_neden_orani_btk_ariza=float(field_btk.neden_grup.eq("telefon_uzaktan").mean()),
        tip_ziyaretsiz_orani={k: v["ziyaretsiz_kapanis_orani"] for k, v in kap.items()},
        tip_saha_ihtiyaci={k["kod"]: k["saha"] for k in TX.KANONIK},
        ofis_kapanis_orani=R["teknisyen"]["ofis_kapanis"]["oran_12_eylul_haric"],
        tekrar_ariza_orani=R["taksonomi"]["tekrar_ariza_1_15_eylul"]["tekrar_task_orani"],
        telefon_cozum_dayanak=("TAMAMLANDI 3-15 Eylül: 'Arıza Nedeni' ∈ {Müşteri sorununun düzeldiğini söyledi, Çağrı merkezi "
                               "çözebilirdi, Müşteriyle görüşüldü} = telefon/uzaktan; {Lokasyonda genel arıza, BÇO/NW sonrası "
                               "düzeldi, TT kaynaklı} = şebeke (ziyaret gereksiz); ayrıca kapatan kişi saha teknisyeni değilse "
                               "(ofis) ziyaretsiz sayıldı. Üst sınır: teknisyen gidip 'düzelmiş' bulduysa da telefon sayılır."),
        teknisyen_gunluk_is_ariza_ekibi=ver["ariza_ekibi_gunluk_is_per_teknisyen"],
        teknisyen_gunluk_is_tum_saha=ver["tum_saha_gunluk_is_per_teknisyen"],
        dongu_suresi_dk_vekil=ver["ardisik_kapanis_arasi_dk_5_180"],
        yol_suresi_dk="ÖLÇÜLEMEDİ: 'konum paylaş' ile 'işe başla' çoğunlukla aynı anda basılıyor; mesafe/hız varsayımı gerekir.",
        yerinde_is_suresi="TÜRETİLEMEDİ (İşe Başlama->Bitirme kapanmış işlerde yok). Vekil: döngü süresi (yol+iş).",
        gunluk_aktif_saha_teknisyeni=ver["gunluk_aktif_saha_teknisyeni"],
        gunluk_aktif_ariza_teknisyeni=ver["gunluk_aktif_ariza_teknisyeni"],
        ariza_ekibi_kisi=ver["ariza_ekibi_kisi"],
        saha_ismi_toplam_distinct=len(fieldset),
        boss_acik_ekip_sayisi=int(b.Ekip.nunique()),
        birikim=dict(toplam=len(b), mevcut=len(mv), yeni=len(yn),
                     mevcut_tip={k: int(v) for k, v in mv.kod.value_counts().items()},
                     yeni_tip={k: int(v) for k, v in yn.kod.value_counts().items()},
                     mevcut_yas=yas_dagilimi(mv.yas_h), yeni_yas=yas_dagilimi(yn.yas_h),
                     mevcut_aksiyon=vc(mv.aksiyon), yeni_aksiyon=vc(yn.aksiyon),
                     fox_sadece=int((j["_merge"] == "left_only").sum()),
                     fox_sadece_tip=vc(j.loc[j["_merge"] == "left_only", "Task Adı_fox"])),
        sla_hedef_saat=dict(boss=R["sla"]["boss_hedef_saat_tip"], fox=R["sla"]["fox_hedef_saat_tip"], kullanici_kurali=24),
        gercek_24s_uyum_mevcut_kohort=R["sla"]["gercek_24s_uyum_kohort"]["orani"],
        gercek_24s_uyum_tip={k: v["uyum_24s"] for k, v in R["sla"]["gercek_24s_uyum_kohort"]["tip_bazinda"].items()},
        ikinci_donanim_giris_alt_sinir_gunluk=round(float(((b.kod == "IKINCI_DONANIM") & (b.yas_h <= 168)).sum() / 7), 2),
        konumlu_oran=dict(tum=R["teknisyen"]["lokasyon_eslesme"]["boss_konumlu_oran"],
                          mevcut=R["teknisyen"]["lokasyon_eslesme"]["boss_mevcut_konumlu_oran"],
                          yeni=R["teknisyen"]["lokasyon_eslesme"]["boss_yeni_konumlu_oran"],
                          tamamlanan_mevcut=R["teknisyen"]["lokasyon_eslesme"]["tamamlandi_konumlu_oran"]),
        ulasilamama=dict(
            boss_merkeze_abone_ulasilamadi=int((b["Merkeze Gönder Statüsü"] == "ABONEYE ULAŞILAMADI - MÜSAİT DEĞİL").sum()),
            son_aciklama_ulasilamadi_tum=int((b.aciklama_grup == "musteriye_ulasilamadi").sum()),
            son_aciklama_ulasilamadi_mevcut=int((mv.aciklama_grup == "musteriye_ulasilamadi").sum()),
            son_aciklama_ulasilamadi_orani_aciklamali=float((b.aciklama_grup == "musteriye_ulasilamadi").sum() / b["Son Açıklama"].notna().sum()),
            abone_kaynakli_aski=int((b["Askıya Alınma Nedeni"] == "Abone kaynaklı").sum()),
            ulasilamadi_notlu_tip_mevcut={k: int(v) for k, v in mv.loc[mv.aciklama_grup == "musteriye_ulasilamadi", "kod"].value_counts().items()},
            baglanti_acik_ulasilamadi_orani=float((mv.loc[mv.kod == "BAGLANTI", "aciklama_grup"] == "musteriye_ulasilamadi").mean())),
        kapasite_kaba_denge=dict(
            mevcut_giris_takvim=gi["takvim_gunu_ort"],
            ziyaretsiz_pay=float(nov_all.mean()),
            saha_gereken_gunluk=float(gi["takvim_gunu_ort"] * (1 - nov_all.mean())),
            ariza_teknisyen_kapasitesi_gunluk=float(ver["gunluk_aktif_ariza_teknisyeni"]["ort"] * ver["ariza_ekibi_gunluk_is_per_teknisyen"]["ort"]),
            saha_kapanisinda_duzelmis_bulunan_pay_btk=float(field_btk.neden_grup.isin(["telefon_uzaktan", "sebeke_altyapi"]).mean()),
            not_=("Kaba denge: saha gereken iş/gün ≈ giriş × (1 - ziyaretsiz pay); kapasite ≈ ort. aktif arıza teknisyeni × ort. "
                  "iş/gün. Teknisyen iş/gün'ün bir kısmı ('düzelmiş' bulunan) gerçek onarım değil -> telefon filtresiyle "
                  "kalan işlerin süresi uzar, iş/gün düşer.")),
        randevu=dict(randevulu_oran=float(b["Randevu Başlangıç Tarihi"].notna().mean()),
                     gecmis_randevu_acik=R["randevu"]["gecmis_randevu_hala_acik"],
                     acilistan_randevuya_saat=R["randevu"]["acilistan_randevuya_saat"]),
        mevcut_kapasite_acigi=dict(
            gelen_hafta_ici=gi["hafta_ici_ort"],
            yapilan_7_15_eylul_ort=float(pd.Series([v["YAPILAN"] for k, v in R["giris"]["anlatilan_yapilan_gunluk"].items()
                                                     if "2026-09-07" <= k <= "2026-09-15" and k != "2026-09-12" and k != "2026-09-13"]).mean()),
            not_="YAPILAN yalnızca 1 Eylül sonrası açılan task'ların kapanışını sayar (Ağustos devri hariç) -> kapasite hafif eksik."),
    )
    (OUT / "is_emri_analizi.json").write_text(json.dumps(py(R), ensure_ascii=False, indent=1), encoding="utf-8")
    print("yazıldı:", OUT / "is_emri_analizi.json")
    return R


if __name__ == "__main__":
    main()
