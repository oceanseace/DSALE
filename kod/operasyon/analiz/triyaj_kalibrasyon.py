# -*- coding: utf-8 -*-
"""RİSK PUANLI HİBRİT TRİYAJ — kalibrasyon ve akış dengesi.

Amaç: gelen her mevcut-müşteri işine giriş anında bilinen özelliklerle
  p_uzak  = ziyaret gerekmeden (telefon/uzaktan/şebeke) kapanma olasılığı
  p_ulas  = ilk aramada müşteriye ulaşma olasılığı (vekil)
tahmini koymak ve 4 şeride (UZAK-ÖNCE / DOĞRUDAN SEVK / TEYİT-SONRA-SEVK / RANDEVU)
dağıtımın günlük yükünü hesaplamak.

Kaynaklar (salt okuma): TAMAMLANDI.xlsx (1-15 Eylül kapanışlar), TeknikTaskDetayRaporu.xlsx
(BOSS açık), bina_master.csv. Çıktı yalnızca toplu sayım/oran: kişi adı, müşteri no, adres,
telefon, task no, tekil lokasyon YOK.

Çalıştır: .venv/Scripts/python.exe operasyon/analiz/triyaj_kalibrasyon.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import taksonomi as TX  # noqa: E402
from is_emri_analizi import SAHA_NEDEN, SRC, py  # noqa: E402

BTK_ARIZA = ["BAGLANTI", "TV_ARIZA", "DOPING_ARIZA", "ARAMA"]
OUT = HERE / "cikti" / "triyaj_kalibrasyon.json"


def norm_lok(s):
    s = s.astype("string").str.strip()
    return s.where(~s.str.fullmatch(r"\d+", na=False), s.str.zfill(8))


def xy(lat, lon, lat0=40.2, lon0=29.0):
    return np.c_[(lon - lon0) * np.cos(np.radians(lat0)) * 111320.0, (lat - lat0) * 110540.0]


def saat_kovasi(h):
    return pd.cut(h, [-1, 8.99, 11.99, 16.99, 24], labels=["00-09", "09-12", "12-17", "17-24"]).astype(str)


def oran_tablosu(df, by, hedef, min_n=25):
    g = df.groupby(by, observed=True)[hedef].agg(["mean", "size"])
    g = g[g["size"] >= min_n]
    return {(" | ".join(map(str, k)) if isinstance(k, tuple) else str(k)): {"oran": round(float(r["mean"]), 3),
                                                                            "n": int(r["size"])}
            for k, r in g.iterrows()}


def main():
    m = pd.read_csv(SRC["bina"], dtype=str)
    m["lat"] = pd.to_numeric(m["lat"], errors="coerce")
    m["lon"] = pd.to_numeric(m["lon"], errors="coerce")
    m["ofis_km"] = pd.to_numeric(m["ofis_km"], errors="coerce")
    mm = m.set_index("location_id")[["lat", "lon", "ofis_km"]]

    t = pd.read_excel(SRC["tamamlandi"], sheet_name="Task Detail Report")
    b = pd.read_excel(SRC["boss"])
    for d in (t, b):
        d["kod"] = d["Task Adı"].map(TX.boss_kod)
        d["sahip"] = d["kod"].map(lambda k: TX.KOD[k]["sahip"] if k in TX.KOD else "bilinmeyen")
        L_ = d["Lokasyon"].astype("string").str.strip()
        ids = set(mm.index)
        k1 = norm_lok(d["Lokasyon"]); k2 = L_.str.lstrip("0")
        d["lok"] = k1.where(k1.isin(ids), k2.where(k2.isin(ids), L_.where(L_.isin(ids))))
        d[["lat", "lon", "ofis_km"]] = d.join(mm, on="lok")[["lat", "lon", "ofis_km"]].values
        d["bas"] = pd.to_datetime(d["Task Başlangıç Tarihi"])
        d["saat"] = d["bas"].dt.hour + d["bas"].dt.minute / 60
        d["gun"] = d["bas"].dt.dayofweek

    R = {"meta": dict(olusturma="operasyon/analiz/triyaj_kalibrasyon.py",
                      gizlilik="Yalnız toplu oran/sayım; kişi/müşteri/adres/telefon/task no yok.",
                      donem="TAMAMLANDI 3-15 Eylül kapanış; akış 1-15 Eylül açılış")}

    # -------------------------------------------------- 1) varış akışı (burst / tekrar) 1-15 Eylül
    ak = pd.concat([t[["Müşteri No", "kod", "sahip", "lok", "lat", "lon", "bas"]].assign(kaynak="T"),
                    b[["Müşteri No", "kod", "sahip", "lok", "lat", "lon", "bas"]].assign(kaynak="B")],
                   ignore_index=True)
    ak = ak[(ak.sahip == "mevcut_musteri") & (ak.bas >= "2026-08-25") & (ak.bas < "2026-09-16")]
    ak_btk = ak[ak.kod.isin(BTK_ARIZA)].copy()

    def burst_say(df_hedef, df_akis, r_m=300, pencere_h=6):
        """Hedefteki her iş için: akıştaki başka BTK arızalarından ±pencere içinde r_m metre içinde kaç tane var."""
        a = df_akis.dropna(subset=["lat", "lon"]).reset_index(drop=True)
        P = xy(a.lat.values, a.lon.values)
        tr = cKDTree(P)
        at = a.bas.values.astype("datetime64[s]").astype(np.int64)
        out = np.full(len(df_hedef), np.nan)
        h = df_hedef.reset_index(drop=True)
        ok = h.lat.notna().values
        Q = xy(h.lat.values[ok], h.lon.values[ok])
        ht = h.bas.values.astype("datetime64[s]").astype(np.int64)[ok]
        res = []
        for q_, tt_, lst in zip(Q, ht, tr.query_ball_point(Q, r_m)):
            dt = np.abs(at[lst] - tt_)
            res.append(int(((dt <= pencere_h * 3600) & (dt > 0)).sum()))
        out[ok] = res
        return out

    # -------------------------------------------------- 2) p_uzak kalibrasyonu (BTK arıza kapanışları)
    fieldset = set(TX.norm(x) for x in pd.concat([t["Ekip"], b["Ekip"]]).dropna().unique())
    t["kapatan"] = np.where(t["Teknisyen"].map(TX.norm).isin(fieldset), "saha", "ofis")
    t["neden_grup"] = t["Arıza Nedeni"].map(SAHA_NEDEN).fillna("girilmemis")
    tk = t[(t["Task Durumu"] == "Tamamlandı") & (t["Task Bitiş Tarihi"] >= "2026-09-03")
           & t.kod.isin(BTK_ARIZA)].copy()
    tk = tk[tk["Task Bitiş Tarihi"].dt.date.astype(str) != "2026-09-12"]  # 12 Eylül toplu ofis kapatma günü hariç
    tk["uzak"] = ((tk.kapatan == "ofis") | tk.neden_grup.isin(["telefon_uzaktan", "sebeke_altyapi"])).astype(int)
    tk["telefon"] = (tk.neden_grup == "telefon_uzaktan").astype(int)
    tk["sebeke"] = (tk.neden_grup == "sebeke_altyapi").astype(int)
    tk["burst300_6s"] = burst_say(tk, ak_btk, 300, 6)
    tk["ayni_bina_6s"] = burst_say(tk, ak_btk, 15, 6)
    tk["burst_k"] = pd.cut(tk["burst300_6s"], [-1, 0, 1, 3, 1e9], labels=["0", "1", "2-3", "4+"]).astype(str)
    tk.loc[tk.burst300_6s.isna(), "burst_k"] = "konumsuz"
    # tekrar: aynı müşteride önceki 15 gün içinde BTK arıza açılışı var mı
    ak_btk_s = ak_btk.sort_values("bas")
    onceki = {}
    for mno, g in ak_btk_s.groupby("Müşteri No"):
        onceki[mno] = g.bas.values
    def tekrar_mi(r):
        arr = onceki.get(r["Müşteri No"])
        if arr is None:
            return 0
        bt = np.datetime64(r["bas"])
        return int(((arr < bt - np.timedelta64(60, "s")) & (arr >= bt - np.timedelta64(15, "D"))).any())
    tk["tekrar"] = tk.apply(tekrar_mi, axis=1)
    tk["saat_k"] = saat_kovasi(tk["saat"])
    tk["hs"] = np.where(tk.gun >= 5, "hafta_sonu", "hafta_ici")
    tk["sure_h"] = (tk["Task Bitiş Tarihi"] - tk["Task Başlangıç Tarihi"]).dt.total_seconds() / 3600

    R["p_uzak"] = dict(
        n=int(len(tk)),
        genel=round(float(tk.uzak.mean()), 3),
        telefon=round(float(tk.telefon.mean()), 3),
        sebeke=round(float(tk.sebeke.mean()), 3),
        tip=oran_tablosu(tk, "kod", "uzak", 5),
        burst=oran_tablosu(tk, "burst_k", "uzak"),
        burst_sebeke=oran_tablosu(tk, "burst_k", "sebeke"),
        tekrar=oran_tablosu(tk, "tekrar", "uzak"),
        saat=oran_tablosu(tk, "saat_k", "uzak"),
        hafta=oran_tablosu(tk, "hs", "uzak"),
        tip_x_tekrar=oran_tablosu(tk, ["kod", "tekrar"], "uzak"),
        tip_x_burst=oran_tablosu(tk, ["kod", "burst_k"], "uzak"),
        sure_uzak_vs_saha_p50=dict(uzak=round(float(tk.loc[tk.uzak == 1, "sure_h"].median()), 1),
                                   saha=round(float(tk.loc[tk.uzak == 0, "sure_h"].median()), 1)),
        not_="uzak = ofis kapanışı VEYA neden ∈ {telefon/uzaktan, şebeke}. 12 Eylül toplu ofis kapatma günü hariç.",
    )

    # basit lojistik model (numpy): uzak ~ tip + burst + tekrar + saat kovası
    X = pd.get_dummies(tk[["kod", "burst_k", "saat_k", "hs"]].astype(str), drop_first=True)
    X["tekrar"] = tk["tekrar"].values
    X.insert(0, "sabit", 1.0)
    Xv = X.values.astype(float); y = tk.uzak.values.astype(float)
    w = np.zeros(Xv.shape[1])
    for _ in range(4000):
        p = 1 / (1 + np.exp(-Xv @ w))
        w -= 0.5 * (Xv.T @ (p - y) / len(y) + 0.01 * np.r_[0, w[1:]])
    p = 1 / (1 + np.exp(-Xv @ w))
    # ayrıştırma gücü: p_uzak'a göre 4'e bölünce uzak oranı
    kv = pd.qcut(p, 4, labels=["Q1", "Q2", "Q3", "Q4"], duplicates="drop")
    R["p_uzak_model"] = dict(
        katsayi={c: round(float(v), 3) for c, v in zip(X.columns, w)},
        ceyrek_gercek_oran={str(k): round(float(v), 3) for k, v in pd.Series(y).groupby(kv, observed=True).mean().items()},
        ceyrek_tahmin_ort={str(k): round(float(v), 3) for k, v in pd.Series(p).groupby(kv, observed=True).mean().items()},
        auc=round(float(auc(y, p)), 3),
    )

    # -------------------------------------------------- 3) ulaşılamama vekili (BOSS açık, mevcut)
    bm = b[b.sahip == "mevcut_musteri"].copy()
    son = bm["Son Açıklama"].astype(str).str.lower()
    bm["ulasilamadi"] = (son.str.contains("ulaşılamadı|ulasilamadi|ulaşılamamış|açmadı|cevap verme|meşgul")
                         | bm["Merkeze Gönder Statüsü"].astype(str).str.contains("ULAŞILAMADI")
                         | bm["Askıya Alınma Nedeni"].astype(str).str.contains("Abone")).astype(int)
    bm["yas_h"] = (pd.Timestamp("2026-09-29 16:45") - bm.bas).dt.total_seconds() / 3600
    bm["saat_k"] = saat_kovasi(bm["saat"])
    bm["seg"] = bm["Segment"].fillna("bos")
    bm["musteri_acik_is"] = bm.groupby("Müşteri No")["kod"].transform("size").clip(upper=3)
    bm["merkez_ilce"] = np.where(bm["İlçe"].isin(["Nilüfer", "Osmangazi", "Yıldırım"]), "merkez3", "diger")
    # 6-72 saat yaşındaki açık işler: en az bir temas denemesi yapılmış olması beklenen pencere
    bw = bm[(bm.yas_h >= 6) & (bm.yas_h <= 72)]
    R["ulasilamama_vekili"] = dict(
        not_=("BOSS açık listede 'ulaşılamadı' izi (Son Açıklama / Merkeze ABONEYE ULAŞILAMADI / abone kaynaklı askı). "
              "Seçim yanlı: ulaşılanlar kapanıp listeden düştüğü için oran ÜST SINIR; yalnız sıralama için kullanılır."),
        tum_mevcut=round(float(bm.ulasilamadi.mean()), 3),
        yas_6_72=dict(n=int(len(bw)), oran=round(float(bw.ulasilamadi.mean()), 3)),
        tip=oran_tablosu(bw, "kod", "ulasilamadi", 10),
        saat=oran_tablosu(bw, "saat_k", "ulasilamadi", 10),
        segment=oran_tablosu(bw, "seg", "ulasilamadi", 10),
        ilce=oran_tablosu(bw, "merkez_ilce", "ulasilamadi", 10),
        musteri_acik_is=oran_tablosu(bw, "musteri_acik_is", "ulasilamadi", 10),
    )

    # tekrar eden müşteride önceki işin ulaşılamadı izi -> sonraki iş (BOSS açık içinde aynı müşteri)
    cok = bm[bm.musteri_acik_is >= 2].sort_values("bas")
    ilk = cok.groupby("Müşteri No").head(1).set_index("Müşteri No")["ulasilamadi"]
    son_ = cok.groupby("Müşteri No").tail(1).set_index("Müşteri No")["ulasilamadi"]
    jj = pd.concat([ilk.rename("ilk"), son_.rename("son")], axis=1).dropna()
    if len(jj) >= 20:
        R["ulasilamama_vekili"]["gecmis_etkisi"] = dict(
            n_musteri=int(len(jj)),
            ilk_ulasilamadi_ise_son_ulasilamadi=round(float(jj.loc[jj.ilk == 1, "son"].mean()), 3) if (jj.ilk == 1).sum() else None,
            ilk_ulasildi_ise_son_ulasilamadi=round(float(jj.loc[jj.ilk == 0, "son"].mean()), 3) if (jj.ilk == 0).sum() else None)

    # -------------------------------------------------- 4) mesafe / yalnızlık (günlük giriş, konumlu)
    ak_g = ak[(ak.bas >= "2026-09-01") & ak.lat.notna()].copy()
    ak_g["gun_"] = ak_g.bas.dt.date
    yalniz = []
    for g_, gg in ak_g.groupby("gun_"):
        if len(gg) < 20:
            continue
        P = xy(gg.lat.values, gg.lon.values)
        d, _ = cKDTree(P).query(P, k=2)
        yalniz.append(dict(n=len(gg), nn_gt_1km=float((d[:, 1] > 1000).mean()), nn_gt_2km=float((d[:, 1] > 2000).mean()),
                           nn_p50=float(np.median(d[:, 1]))))
    yd = pd.DataFrame(yalniz)
    R["yalnizlik_gunluk_giris"] = dict(gun=int(len(yd)), nn_1km_ustu_orani_ort=round(float(yd.nn_gt_1km.mean()), 3),
                                        nn_2km_ustu_orani_ort=round(float(yd.nn_gt_2km.mean()), 3),
                                        nn_p50_m_ort=round(float(yd.nn_p50.mean()), 0),
                                        ofis_km_p75=round(float(ak_g.merge(mm, left_on="lok", right_index=True, how="left", suffixes=("", "_m"))["ofis_km"].quantile(0.75)), 1))

    # -------------------------------------------------- 5) akış dengesi: şerit hacimleri (hafta içi 338 mevcut iş)
    R["akis_dengesi"] = akis_dengesi(R)
    OUT.write_text(json.dumps(py(R), ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(py(R), ensure_ascii=False, indent=1)[:9000])


def auc(y, p):
    o = np.argsort(p)
    r = np.empty(len(p)); r[o] = np.arange(1, len(p) + 1)
    n1 = y.sum(); n0 = len(y) - n1
    return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)


def akis_dengesi(R):
    """Hafta içi günlük ~338 mevcut iş için RİSK PUANLI HİBRİT şerit yükü (deterministik beklenen değer).

    Birim: teknisyen-dakika (ziyaret) ve masa-dakika (arama). Varsayımlar 'varsayim' altında; ilk hafta ölçülüp
    güncellenecek (özellikle p_ulas1, p_evde_*)."""
    G = 337.7
    pay = {"BTK_ARIZA": 0.44 + 0.09 + 0.027 + 0.0025, "KANAL_SIKAYETI": 0.152, "CIHAZ_IADE": 0.107,
           "SAHA_CIHAZ_DIGER": 0.099 + 0.034 + 0.051 - 0.0025}
    pu = R["p_uzak"]
    b = pu["burst"]
    n_loc = sum(b[k]["n"] for k in ["0", "1", "2-3"])
    p_uzak_normal = sum(b[k]["n"] * b[k]["oran"] for k in ["0", "1", "2-3"]) / n_loc
    ntot = sum(v["n"] for v in b.values())
    V = dict(
        pay_toplu=b["4+"]["n"] / ntot, pay_konumsuz=b["konumsuz"]["n"] / ntot, pay_kotu_gecmis=0.12,
        p_uzak_normal=round(p_uzak_normal, 3), p_uzak_konumsuz=b["konumsuz"]["oran"], p_uzak_toplu=b["4+"]["oran"],
        p_ulas1=0.55, p_ulas2_ek=0.40, p_ulas3_kum=0.82, uzak_cozum_verimi=0.90,
        p_evde_habersiz=0.80, p_evde_teyitli=0.95, tek_yoldayim_cozum=0.25,
        arama_dk=3.0, uzak_teshis_dk=8.0, ziyaret_dk=31.0, bosa_ziyaret_dk_kume=10.0, toplu_kume_is=5.0,
        saha_teyit_payi=0.35, ikinci_deneme_eta_gt90_payi=0.5)
    n_btk = G * pay["BTK_ARIZA"]
    out = {}
    # --- BTK: toplu arıza şeridi
    n = n_btk * V["pay_toplu"]
    kume = n / V["toplu_kume_is"]
    kalan = n * (1 - V["p_uzak_toplu"])
    out["BTK_TOPLU"] = dict(gelen=n, arama=n * 1.5, masa_dk=n * 1.5 * V["arama_dk"] + kume * 15,
                            ziyaret=kume + kalan, bosa=kalan * (1 - V["p_evde_teyitli"]), uzak_kapanan=n - kalan)
    # --- BTK: uzak-önce (normal + konumsuz)
    for ad, pay_, pz in [("BTK_UZAK_ONCE_KONUMLU", 1 - V["pay_toplu"] - V["pay_konumsuz"] - V["pay_kotu_gecmis"], V["p_uzak_normal"]),
                         ("BTK_UZAK_ONCE_KONUMSUZ", V["pay_konumsuz"], V["p_uzak_konumsuz"])]:
        n = n_btk * pay_
        ul = n * V["p_ulas1"]
        coz1 = ul * pz * V["uzak_cozum_verimi"]
        teyitli = ul - coz1
        habersiz = n - ul
        a2 = habersiz * V["ikinci_deneme_eta_gt90_payi"]
        coz2 = a2 * V["p_ulas2_ek"] * pz * V["uzak_cozum_verimi"]
        habersiz_z = habersiz - coz2
        out[ad] = dict(gelen=n, arama=n + a2, masa_dk=n * V["arama_dk"] + ul * V["uzak_teshis_dk"] + a2 * V["arama_dk"]
                       + a2 * V["p_ulas2_ek"] * V["uzak_teshis_dk"],
                       ziyaret=teyitli + habersiz_z, uzak_kapanan=coz1 + coz2,
                       bosa=teyitli * (1 - V["p_evde_teyitli"]) + habersiz_z * (1 - V["p_evde_habersiz"]))
    # --- BTK: kötü ulaşılabilirlik geçmişi -> doğrudan sevk (masa aramaz)
    n = n_btk * V["pay_kotu_gecmis"]
    tel = n * V["tek_yoldayim_cozum"] * 0.3
    out["BTK_DOGRUDAN_KOTU_GECMIS"] = dict(gelen=n, arama=0, masa_dk=0, ziyaret=n - tel, uzak_kapanan=tel,
                                            bosa=(n - tel) * (1 - V["p_evde_habersiz"]))
    # --- Kanal şikayeti: yalnız telefon
    n = G * pay["KANAL_SIKAYETI"]
    out["KANAL_TELEFON"] = dict(gelen=n, arama=n * 1.8, masa_dk=n * 1.8 * V["arama_dk"] + n * V["p_ulas3_kum"] * 3,
                                ziyaret=0, uzak_kapanan=n * V["p_ulas3_kum"], bosa=0)
    # --- Cihaz iade: masa kaydı, %10 teknisyen dolgu durağı
    n = G * pay["CIHAZ_IADE"]
    out["CIHAZ_IADE_MASA"] = dict(gelen=n, arama=n * 0.1, masa_dk=n * 1.5 + n * 0.1 * V["arama_dk"], ziyaret=n * 0.1,
                                  uzak_kapanan=n * 0.9, bosa=n * 0.1 * 0.05)
    # --- Cihaz değişimi/ücretlendirme/evrak: p_uzak≈0; teyit yalnız ΔE>0 olan (yalnız/uzak/konumsuz/kötü geçmiş değil)
    n = G * pay["SAHA_CIHAZ_DIGER"]
    ty = n * V["saha_teyit_payi"]; dg = n - ty
    out["SAHA_TEYIT_VEYA_DOGRUDAN"] = dict(gelen=n, arama=ty * 1.6, masa_dk=ty * 1.6 * V["arama_dk"], ziyaret=n,
                                           uzak_kapanan=0, bosa=ty * (1 - V["p_evde_teyitli"]) + dg * (1 - V["p_evde_habersiz"]))
    top = {c: round(sum(v[c] for v in out.values()), 1) for c in ["gelen", "arama", "masa_dk", "ziyaret", "uzak_kapanan", "bosa"]}
    top["masa_kisi_6s_etkin"] = round(top["masa_dk"] / 360, 1)
    top["teknisyen_gun_17is"] = round(top["ziyaret"] / 17, 1)
    top["bosa_orani"] = round(top["bosa"] / top["ziyaret"], 3)
    top["ziyaretsiz_kapanis_orani"] = round(top["uzak_kapanan"] / top["gelen"], 3)
    # karşılaştırma: kullanıcının fikri (herkes doğrudan sevk, yalnız ulaşılamayan aranır) aynı parametrelerle
    btk_n = n_btk
    kul = dict(ziyaret=G * (pay["BTK_ARIZA"] + pay["SAHA_CIHAZ_DIGER"]) + G * pay["CIHAZ_IADE"] * 0.1
               - btk_n * V["tek_yoldayim_cozum"],
               arama=G * (pay["BTK_ARIZA"] + pay["SAHA_CIHAZ_DIGER"]) * (1 - V["p_evde_habersiz"]) * 1.8 + G * pay["KANAL_SIKAYETI"] * 1.8)
    kul["bosa"] = (G * (pay["BTK_ARIZA"] + pay["SAHA_CIHAZ_DIGER"]) - btk_n * V["tek_yoldayim_cozum"]) * (1 - V["p_evde_habersiz"])
    kul["teknisyen_gun_17is"] = round(kul["ziyaret"] / 17, 1)
    # teknisyen dakikası: ziyaret + boşa ziyaretin %80'i yeniden ziyaret + teknisyenin kendi araması
    habersiz_ziyaret = (out["BTK_UZAK_ONCE_KONUMLU"]["ziyaret"] + out["BTK_UZAK_ONCE_KONUMSUZ"]["ziyaret"]) * (1 - V["p_ulas1"])         + out["BTK_DOGRUDAN_KOTU_GECMIS"]["ziyaret"] + out["SAHA_TEYIT_VEYA_DOGRUDAN"]["ziyaret"] * (1 - V["saha_teyit_payi"])
    top["teknisyen_dk"] = round(top["ziyaret"] * V["ziyaret_dk"] + top["bosa"] * 0.8 * V["ziyaret_dk"] + habersiz_ziyaret * 1.0, 0)
    kul["teknisyen_dk"] = round(kul["ziyaret"] * V["ziyaret_dk"] + kul["bosa"] * 0.8 * V["ziyaret_dk"]
                                + G * (pay["BTK_ARIZA"] + pay["SAHA_CIHAZ_DIGER"]) * 2.5, 0)
    top["teknisyen_gun_esdeger_510dk"] = round(top["teknisyen_dk"] / 510, 1)
    kul["teknisyen_gun_esdeger_510dk"] = round(kul["teknisyen_dk"] / 510, 1)
    top["btk_uzak_kapanan_2s_icinde"] = round(sum(out[k]["uzak_kapanan"] for k in ["BTK_UZAK_ONCE_KONUMLU", "BTK_UZAK_ONCE_KONUMSUZ"]), 1)
    return dict(varsayim={k: (round(v, 3) if isinstance(v, float) else v) for k, v in V.items()}, n_btk_gun=round(n_btk, 1),
                serit={k: {c: round(x, 1) for c, x in v.items()} for k, v in out.items()}, toplam=top,
                karsilastirma_hepsini_dogrudan_sevk={k: round(v, 1) for k, v in kul.items()})


if __name__ == "__main__":
    main()
