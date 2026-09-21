"""Sunum uygulaması (app/) için kompakt veri paketi (Vite ile derlemeye gömülür).

Üretilen dosyalar (app/src/data/generated/):
  binalar.json  — 19.706 binanın sütunsal verisi + taban poligonları (merkeze göre mikro-derece farkları)
  planlar.json  — her N için birim→bölge dizisi, bölge KPI'ları, sınır poligonları (Voronoi ile kırpılmış,
                  örtüşmeyen) ve varsayılan planda algoritmanın ara adımları (merkezler + birim etiketleri)
  meta.json     — toplamlar, ofis, organizasyon, ilçe/mahalle özetleri, Yalova, veri kalitesi
  altlik.json   — çevrimdışı altlık (OSM yollar, kıyı/göller, ilçe sınırları)

Uygulama tarafındaki tip tanımları: app/src/data/types.ts
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from . import config

APP_DATA = config.ROOT / "app" / "src" / "data" / "generated"
PAKET_SURUMU = 1


def _sozluk(seri: pd.Series) -> tuple[list[str], list[int]]:
    kod, uniq = pd.factorize(seri.fillna("").astype(str), sort=True)
    return list(uniq), kod.tolist()


def _metin(seri: pd.Series) -> pd.Series:
    """Kaynaktaki 'Null' / 'None' / 'nan' yazımlarını ve boşlukları gerçek boş metne çevirir."""
    s = seri.fillna("").astype(str).str.strip()
    return s.where(~s.str.lower().isin(["null", "none", "nan", "-"]), "")


def binalar(df: pd.DataFrame) -> dict:
    geom = json.load(open(config.GEOM_JSON, encoding="utf-8"))
    birim_sozluk, birim = _sozluk(df["site_grup"])
    s_mah, mah = _sozluk(df["mahalle"])
    s_ilce, ilce = _sozluk(df["ilce"])
    s_il, il = _sozluk(df["il"])
    site, bina_ad = _metin(df["site_adi"]), _metin(df["ad"])
    s_ad, ad = _sozluk(site.where(site != "", bina_ad))

    ofs, farklar = [0], []
    for serial, lon, lat in zip(df["bina_serial"], df["lon"], df["lat"]):
        halka = geom.get(serial) or []
        for x, y in halka:
            farklar.append(int(round((x - lon) * 1e6)))
            farklar.append(int(round((y - lat) * 1e6)))
        ofs.append(len(farklar) // 2)

    return {
        "surum": PAKET_SURUMU,
        "n": int(len(df)),
        "serial": df["bina_serial"].tolist(),
        "lon": df["lon"].round(6).tolist(),
        "lat": df["lat"].round(6).tolist(),
        "kat": df["kat"].astype(int).tolist(),
        "toplam_hp": df["toplam_hp"].astype(int).tolist(),
        "res_hp": df["res_hp"].astype(int).tolist(),
        "aktif": df["aktif_res"].astype(int).tolist(),
        "firsat": df["firsat"].astype(int).tolist(),
        "birim": birim,
        "mahalle": mah, "ilce": ilce, "il": il, "ad": ad,
        "sozluk": {"mahalle": s_mah, "ilce": s_ilce, "il": s_il, "ad": s_ad, "birim": birim_sozluk},
        "poligon": {"fark": farklar, "ofs": ofs, "olcek": 1e-6},
    }


def plan_kaydi(df: pd.DataFrame, sonuc, bolgeler: list[dict], birim_sozluk: list[str]) -> dict:
    """Bir bölgeleme sonucunu uygulama biçimine çevirir (birim → bölge)."""
    birim_bolge = df.groupby("site_grup")["bina_serial"].first().map(sonuc.atama)
    dizi = birim_bolge.reindex(birim_sozluk).fillna(0).astype(int).tolist()
    return {
        "n": sonuc.n,
        "olcu": sonuc.olcu,
        "hedef": round(float(sonuc.hedef), 2),
        "sapma_min": float(min(b["sapma"] for b in bolgeler)),
        "sapma_maks": float(max(b["sapma"] for b in bolgeler)),
        "sure_sn": sonuc.sure_sn,
        "parametreler": sonuc.parametreler,
        "birim_bolge": dizi,
        "bolgeler": bolgeler,
        "anlik": sonuc.anlik,
        "anlik_etiket": list(getattr(sonuc, "anlik_etiket", []) or []),
    }


def meta(df: pd.DataFrame, ana_plan: dict) -> dict:
    kalite = json.load(open(config.QUALITY_JSON, encoding="utf-8"))
    ilce = df.groupby(["il", "ilce"]).agg(bina=("bina", "sum"), res_hp=("res_hp", "sum"), aktif=("aktif_res", "sum"),
                                          firsat=("firsat", "sum"), lon=("lon", "mean"), lat=("lat", "mean")) \
             .sort_values("res_hp", ascending=False).reset_index()
    mah = df.groupby(["ilce", "mahalle"]).agg(bina=("bina", "sum"), res_hp=("res_hp", "sum"), firsat=("firsat", "sum"),
                                              lon=("lon", "mean"), lat=("lat", "mean")) \
            .sort_values("firsat", ascending=False).reset_index()
    y = df[df["il"] == "Yalova"]
    yalova_bolge = sorted({b["bolge"] for b in ana_plan["bolgeler"] if b.get("yalova_bina")})
    return {
        "surum": PAKET_SURUMU,
        "uretim": datetime.now().isoformat(timespec="seconds"),
        "organizasyon": config.ORGANIZASYON,
        "organizasyon_kisa": config.ORGANIZASYON_KISA,
        "hitap": config.SUNUM_HITAP,
        "baslik": config.SUNUM_BASLIK,
        "ofis": config.OFIS,
        "ekip": {"mudur": config.SATIS_EKIBI["mudur"], "takim_lideri": config.SATIS_EKIBI["takim_lideri"],
                 "sorumlu_sayisi": len(config.SATIS_EKIBI["sorumlular"])},
        "toplam": {c: int(df[c].sum()) for c in ["bina", "toplam_hp", "res_hp", "soho_hp", "aktif_res", "aktif_toplam",
                                                 "firsat", "kurulum_son_ay", "churn_son_ay"]},
        # Mahalle kimliği (ilçe, mahalle) çiftidir: aynı ad farklı ilçelerde tekrar edebilir.
        "mahalle_sayisi": int(df.groupby(["ilce", "mahalle"]).ngroups),
        "ilce_sayisi": int(df["ilce"].nunique()),
        "penetrasyon": float(df["aktif_res"].sum() / df["res_hp"].sum()),
        "ilceler": ilce.round(5).to_dict("records"),
        "ust_mahalleler": mah.head(15).round(5).to_dict("records"),
        "yalova": {"bina": int(len(y)), "res_hp": int(y["res_hp"].sum()), "toplam_hp": int(y["toplam_hp"].sum()),
                   "aktif": int(y["aktif_res"].sum()), "firsat": int(y["firsat"].sum()),
                   "merkez": [round(float(y["lon"].mean()), 5), round(float(y["lat"].mean()), 5)] if len(y) else None,
                   "bolgeler": yalova_bolge},
        "sinir": {"lon": [float(df["lon"].min()), float(df["lon"].max())], "lat": [float(df["lat"].min()), float(df["lat"].max())]},
        "kaynaklar": {
            "bina": "Superonline bina listesi (data.xlsx, ORIGN)",
            "konum": "Turkcell OneMap — ONEMAP/BINA katmanı, %100 eşleşme",
            "altlik": "© OpenStreetMap katkıcıları (ODbL)",
        },
        "kalite": {k: kalite.get(k) for k in ["data_satir", "tekil_bina", "eslesme", "kat_kaynagi", "aktif_res_gt_res_hp",
                                               "onemap_cekim_tarihi", "site_grup_sayisi"]},
    }


def altlik() -> dict:
    out = {"attribution": "© OpenStreetMap katkıcıları (ODbL)"}
    for ad in ["yollar", "su", "ilce"]:
        yol = config.REF / f"osm_{ad}.geojson"
        out[ad] = json.load(open(yol, encoding="utf-8")) if yol.exists() else {"type": "FeatureCollection", "features": []}
    return out


def yaz(df: pd.DataFrame, ana: dict, alternatifler: dict[int, dict], hedef_klasor: Path = APP_DATA) -> dict[str, float]:
    hedef_klasor.mkdir(parents=True, exist_ok=True)
    b = binalar(df)
    birim_sayisi = len(b["sozluk"]["birim"])
    tum = {**alternatifler, ana["n"]: ana}
    for k, plan in tum.items():
        if len(plan["birim_bolge"]) != birim_sayisi:
            raise ValueError(f"N={k} planında birim sayısı uyuşmuyor: "
                             f"{len(plan['birim_bolge'])} ≠ {birim_sayisi} (farklı veri/--haric-il ile mi üretildi?)")
    planlar = {"varsayilan": ana["n"], "olcu": ana["olcu"], "birim_sayisi": birim_sayisi,
               "planlar": {str(k): v for k, v in sorted(tum.items())}}
    dosyalar = {"binalar.json": b, "planlar.json": planlar, "meta.json": meta(df, ana), "altlik.json": altlik()}
    boyut = {}
    for ad, icerik in dosyalar.items():
        yol = hedef_klasor / ad
        json.dump(icerik, open(yol, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
        boyut[ad] = round(yol.stat().st_size / 1e6, 2)
    return boyut
