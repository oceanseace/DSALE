"""data.xlsx + OneMap bina katmanı -> tek master tablo.

Bir kez çalıştırılır; sonuç `data/master/` altına yazılır ve tüm bölgeleme
çalıştırmaları (N=8, 10, 50 ...) bu tabloyu kullanır.

    python -m dsale.enrich
"""
from __future__ import annotations

import json
import re

import numpy as np
import pandas as pd
from shapely.geometry import Polygon

from . import config

# data.xlsx kolon adı -> master kolon adı
DATA_KOLONLARI = {
    "Bina Serial Number": "bina_serial",
    "Tellcordia ID": "tellcordia_id",
    "Location Id": "location_id",
    "Toplu Satış Mı": "toplu_satis",
    "Protokol Segment": "protokol_segment",
    "Obek Adı": "obek",
    "Adı": "ad",
    "Site Adı": "site_adi_crm",
    "Blok Adı": "blok_adi_crm",
    "Kapı No": "kapi_no_crm",
    "Ilçe": "ilce_crm",
    "IL": "il",
    "Kurumsal Sabit Evrak Tipi": "evrak_tipi",
    "Kurumsal Sözleşme Tipi": "altyapi",
    "Sales Ready Tarihi": "sales_ready",
    "Toplam HP": "toplam_hp",
    "Soho Op": "soho_hp",
    "RES HP": "res_hp",
    "Aktif Abone (Residential+Toptan+Esnaf)": "aktif_toplam",
    "Aktif Abone Residential Segment": "aktif_res",
    "Aktif Abone SOHO Segment": "aktif_soho",
    "Aktif Abone TOPTAN Segment": "aktif_toptan",
    "Aktif Abone Diğer Segment": "aktif_diger",
    "Aktif Abone SOHO Segment (Esnaf)": "aktif_esnaf",
    "Son Ay Yapılan Kurulum Sayısı (Residential)": "kurulum_son_ay",
    "Son Ay Yapılan Churn Sayısı (Residential)": "churn_son_ay",
    "Aktif Abone Turkcell Tv": "tv",
    "Aktif Abone Yan Oda Turkcell Tv": "tv_yan_oda",
}

ONEMAP_KOLONLARI = {
    "OBJECTID": "onemap_objectid",
    "ID": "onemap_id",
    "LOCATION_ID": "onemap_location_id",
    "ADI": "onemap_adi",
    "SITE_ADI": "site_adi",
    "BLOK_ADI": "blok_adi",
    "KAPI_NO": "kapi_no",
    "TURU": "bina_turu",
    "KAT_ADEDI": "kat_adedi_onemap",
    "KONUT_SAYISI": "konut_sayisi",
    "ISYERI_SAYISI": "isyeri_sayisi",
    "MAHALLE": "mahalle",
    "CADDE": "cadde",
    "SOKAK": "sokak",
    "ILCE": "ilce",
    "OBEK_ADI": "obek_onemap",
    "TEKNOLOJI": "teknoloji",
    "LAT": "lat_onemap",
    "LON": "lon_onemap",
    "UAVT_BINA_KODU": "uavt_bina_kodu",
}

M_PER_DEG_LAT = 110_574.0


def _m_per_deg_lon(lat: float) -> float:
    return 111_320.0 * np.cos(np.radians(lat))


def _bos(x) -> bool:
    return x is None or (isinstance(x, float) and np.isnan(x)) or str(x).strip() in ("", "nan", "None")


def tr_norm(s) -> str:
    """Türkçe büyük harf + sadeleştirme (eşleştirme anahtarları için)."""
    if _bos(s):
        return ""
    s = str(s).replace("i", "İ").replace("ı", "I").upper()
    s = s.translate(str.maketrans("İIŞĞÜÖÇÂÎÛ", "IISGUOCAIU"))
    s = re.sub(r"\b(SITESI|SITE|SIT|BLOK|BLK|APARTMANI|APT|KONUTLARI|EVLERI|ETAP)\b\.?", " ", s)
    return re.sub(r"[^A-Z0-9]+", " ", s).strip()


MAHALLE_DUZELTME = {"75.yıl": "75. Yıl", "Yenımahalle": "Yenimahalle"}


def mahalle_norm(s) -> str:
    """OneMap mahalle adlarındaki 'Mh.' / 'Mah.' eklerini ve yazım farklarını temizler."""
    if _bos(s):
        return "Bilinmiyor"
    s = re.sub(r"\s*\b(Mahallesi|Mah\.?|Mh\.?)$", "", str(s).strip(), flags=re.IGNORECASE).strip()
    return MAHALLE_DUZELTME.get(s, s)


def _poligon(rings):
    """Esri halkaları (lon/lat) -> (merkez lon, merkez lat, alan m², sadeleştirilmiş dış halka)."""
    dis = rings[0]
    lat0 = float(np.mean([p[1] for p in dis]))
    kx, ky = _m_per_deg_lon(lat0), M_PER_DEG_LAT
    xy = [((p[0]) * kx, (p[1]) * ky) for p in dis]
    try:
        poly = Polygon(xy)
        if not poly.is_valid:
            poly = poly.buffer(0)
        c = poly.centroid
        alan = float(poly.area)
        cx, cy = c.x / kx, c.y / ky
    except Exception:  # dejenere poligon
        cx, cy, alan = float(np.mean([p[0] for p in dis])), lat0, 0.0
    halka = [[round(p[0], 6), round(p[1], 6)] for p in dis]
    return cx, cy, alan, halka


def _kat_tahmini(df: pd.DataFrame) -> pd.Series:
    """Kat adedi OneMap'te ~%50 dolu. Eksikleri konut sayısı ve taban alanından tahmin et."""
    bilinen = (df["kat_adedi_onemap"] >= 1) & (df["kat_adedi_onemap"] <= 60) & (df["taban_alani_m2"] > 20) & (df["konut_sayisi"] > 0)
    # kat başına konut ≈ a × taban alanı
    oran = (df.loc[bilinen, "konut_sayisi"] / df.loc[bilinen, "kat_adedi_onemap"]) / df.loc[bilinen, "taban_alani_m2"]
    a = float(oran.median()) if bilinen.any() else 1 / 110
    kat_basi = (df["taban_alani_m2"].clip(lower=40) * a).clip(lower=1)
    tahmin = (df["konut_sayisi"].fillna(1).clip(lower=1) / kat_basi).round().clip(1, 30)
    kat = df["kat_adedi_onemap"].where((df["kat_adedi_onemap"] >= 1) & (df["kat_adedi_onemap"] <= 60), tahmin)
    return kat.astype(int), a


def site_gruplari(df: pd.DataFrame, esik_m: float = 350.0) -> pd.Series:
    """Aynı sitenin blokları aynı satışçıda kalsın diye site grubu anahtarı üretir.

    Anahtar: ilçe + mahalle + normalize site adı. Aynı ada sahip ama birbirinden
    `esik_m`'den uzak blok kümeleri ayrı gruplara bölünür.
    """
    from scipy.cluster.hierarchy import fcluster, linkage

    ad = df["site_adi"].map(tr_norm)
    ad = ad.where(ad != "", df["site_adi_crm"].map(tr_norm))
    tekil = ad.eq("") | df["bina_turu"].fillna("").str.upper().str.contains("TEK")
    anahtar = df["ilce"].fillna("") + "|" + df["mahalle"].fillna("") + "|" + ad
    grup = pd.Series(index=df.index, dtype=object)
    grup[tekil] = "B:" + df.loc[tekil, "bina_serial"]
    for k, idx in df[~tekil].groupby(anahtar[~tekil]).groups.items():
        idx = list(idx)
        if len(idx) == 1:
            grup[idx[0]] = "S:" + k
            continue
        lat0 = df.loc[idx, "lat"].mean()
        xy = np.c_[df.loc[idx, "lon"] * _m_per_deg_lon(lat0), df.loc[idx, "lat"] * M_PER_DEG_LAT]
        etiket = fcluster(linkage(xy, "single"), esik_m, "distance")
        for j, e in zip(idx, etiket):
            grup[j] = f"S:{k}#{e}"
    return grup


def build() -> dict:
    config.MASTER.mkdir(parents=True, exist_ok=True)
    kalite: dict = {}

    # --- data.xlsx
    d = pd.read_excel(config.DATA_XLSX, dtype={"Tellcordia ID": str, "Location Id": str, "Müşteri No": str})
    d.columns = [c.strip() for c in d.columns]
    d = d.rename(columns=DATA_KOLONLARI)
    kalite["data_satir"] = int(len(d))
    for c in ["bina_serial", "tellcordia_id", "location_id"]:
        d[c] = d[c].astype(str).str.strip()
    bozuk_tell = ~d["tellcordia_id"].str.fullmatch(r"\d+")
    kalite["bozuk_tellcordia_id"] = d.loc[bozuk_tell, ["bina_serial", "tellcordia_id", "ad"]].to_dict("records")
    tekrar = d[d["bina_serial"].duplicated(keep=False)]
    kalite["tekrar_eden_satir"] = tekrar[["bina_serial", "ad", "res_hp", "toplam_hp"]].to_dict("records")
    d = d.sort_values("toplam_hp", ascending=False).drop_duplicates("bina_serial").sort_index()
    kalite["tekil_bina"] = int(len(d))

    # --- OneMap
    j = json.load(open(config.ONEMAP_JSON, encoding="utf-8"))
    kalite["onemap_kaynak"] = j.get("source")
    kalite["onemap_cekim_tarihi"] = j.get("extracted_at")
    kayit, geom = [], {}
    for f in j["features"]:
        a = f["a"]
        cx, cy, alan, halka = _poligon(f["g"])
        r = {v: a.get(k) for k, v in ONEMAP_KOLONLARI.items()}
        r.update(lon=cx, lat=cy, taban_alani_m2=alan)
        r["onemap_id"] = str(int(a["ID"])) if a.get("ID") is not None else None
        kayit.append(r)
        geom[a["LOCATION_ID"]] = halka
    om = pd.DataFrame(kayit)

    # --- eşleştirme: önce Tellcordia ID = OneMap ID, sonra Bina Serial = LOCATION_ID
    m1 = d.merge(om, left_on="tellcordia_id", right_on="onemap_id", how="left")
    eksik = m1["onemap_objectid"].isna()
    if eksik.any():
        m2 = d[eksik.values].merge(om, left_on="bina_serial", right_on="onemap_location_id", how="left")
        m1 = pd.concat([m1[~eksik], m2], ignore_index=True)
    m1["eslesme"] = np.where(m1["tellcordia_id"] == m1["onemap_id"], "Tellcordia ID", np.where(m1["onemap_objectid"].notna(), "Bina Serial", "YOK"))
    df = m1.sort_values("bina_serial").reset_index(drop=True)
    kalite["eslesme"] = df["eslesme"].value_counts().to_dict()

    # --- alan / tür düzeltmeleri
    df["ilce"] = df["ilce"].fillna(df["ilce_crm"])
    df.loc[df["il"].eq("Yalova") & df["ilce"].isin(["Merkez", "Yalova Merkez"]), "ilce"] = "Yalova Merkez"
    kalite["ilce_uyusmazligi"] = df.loc[(df["ilce"] != df["ilce_crm"]) & ~df["il"].eq("Yalova"), ["bina_serial", "ilce_crm", "ilce"]].to_dict("records")
    df["mahalle"] = df["mahalle"].map(mahalle_norm)
    df["obek"] = df["obek"].fillna(df["obek_onemap"])
    for c in ["toplam_hp", "soho_hp", "res_hp", "aktif_toplam", "aktif_res", "aktif_soho", "aktif_toptan", "aktif_diger",
              "aktif_esnaf", "kurulum_son_ay", "churn_son_ay", "tv", "tv_yan_oda", "konut_sayisi", "isyeri_sayisi", "kat_adedi_onemap"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in ["toplam_hp", "soho_hp", "res_hp", "aktif_toplam", "aktif_res", "kurulum_son_ay", "churn_son_ay"]:
        df[c] = df[c].fillna(0).astype(int)

    # --- türetilmiş ölçüler
    df["firsat"] = (df["res_hp"] - df["aktif_res"]).clip(lower=0).astype(int)
    df["bina"] = 1
    df["penetrasyon"] = np.where(df["res_hp"] > 0, df["aktif_res"] / df["res_hp"].where(df["res_hp"] > 0, 1), np.nan)
    kalite["aktif_res_gt_res_hp"] = int((df["aktif_res"] > df["res_hp"]).sum())
    df["sales_ready"] = pd.to_datetime(df["sales_ready"], errors="coerce")
    df["satisa_hazir_yil"] = df["sales_ready"].dt.year
    df["kat"], kat_katsayi = _kat_tahmini(df)
    df["kat_kaynagi"] = np.where((df["kat_adedi_onemap"] >= 1) & (df["kat_adedi_onemap"] <= 60), "OneMap", "Tahmin")
    kalite["kat_tahmin_katsayisi_konut_per_m2_per_kat"] = kat_katsayi
    kalite["kat_kaynagi"] = df["kat_kaynagi"].value_counts().to_dict()
    df["konum_kaynagi"] = "OneMap bina poligonu merkezi"
    df["site_grup"] = site_gruplari(df)
    kalite["site_grup_sayisi"] = int(df["site_grup"].nunique())

    # --- ofise uzaklık (kuş uçuşu km)
    ky, kx = M_PER_DEG_LAT, _m_per_deg_lon(config.OFIS["lat"])
    df["ofis_km"] = np.hypot((df["lon"] - config.OFIS["lon"]) * kx, (df["lat"] - config.OFIS["lat"]) * ky) / 1000

    kolonlar = [
        "bina_serial", "tellcordia_id", "location_id", "onemap_objectid", "eslesme", "ad", "site_adi", "blok_adi", "kapi_no",
        "bina_turu", "mahalle", "cadde", "sokak", "ilce", "il", "obek", "site_grup", "lat", "lon", "konum_kaynagi",
        "taban_alani_m2", "kat", "kat_kaynagi", "konut_sayisi", "isyeri_sayisi", "toplam_hp", "soho_hp", "res_hp",
        "aktif_toplam", "aktif_res", "aktif_soho", "aktif_toptan", "aktif_esnaf", "aktif_diger", "firsat", "bina",
        "penetrasyon", "kurulum_son_ay", "churn_son_ay", "tv", "tv_yan_oda", "protokol_segment", "toplu_satis", "altyapi",
        "teknoloji", "evrak_tipi", "sales_ready", "satisa_hazir_yil", "uavt_bina_kodu", "ofis_km",
    ]
    df = df[kolonlar]
    df.to_csv(config.MASTER_CSV, index=False, encoding="utf-8-sig")
    json.dump({k: geom[k] for k in df["bina_serial"] if k in geom}, open(config.GEOM_JSON, "w", encoding="utf-8"), separators=(",", ":"))

    kalite["toplamlar"] = {c: int(df[c].sum()) for c in ["toplam_hp", "res_hp", "soho_hp", "aktif_toplam", "aktif_res", "firsat", "bina"]}
    kalite["il_dagilimi"] = df["il"].value_counts().to_dict()
    kalite["ilce_dagilimi"] = df["ilce"].value_counts().to_dict()
    kalite["mahalle_sayisi"] = int(df["mahalle"].nunique())
    kalite["konum_eksik"] = int(df["lat"].isna().sum())
    json.dump(kalite, open(config.QUALITY_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    return kalite


if __name__ == "__main__":
    k = build()
    print(json.dumps({x: k[x] for x in ["data_satir", "tekil_bina", "eslesme", "toplamlar", "kat_kaynagi", "site_grup_sayisi", "konum_eksik", "mahalle_sayisi"]}, ensure_ascii=False, indent=1))
