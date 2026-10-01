"""Bölge KPI'ları, bölge adları, renkler ve bölge sınır poligonları.

Sınır poligonları (2.5): binaların Voronoi mozaiği bölge bölge birleştirilir ve
bina tamponu bu hücreyle kırpılır. Böylece bölgeler **tanım gereği** iç içe geçmez
(komşu bölgelerin sınırları birebir aynı Voronoi kenarını paylaşır) ve hesap
bölge başına ~1 s yerine ~0,05 s sürer.
"""
from __future__ import annotations

import colorsys
from collections import defaultdict

import numpy as np
import pandas as pd
import shapely
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import minimum_spanning_tree
from scipy.spatial import Delaunay
from shapely.geometry import mapping
from shapely.ops import polylabel

from . import config
from .enrich import M_PER_DEG_LAT, _m_per_deg_lon

# 8'e kadar el seçimi, koyu zeminde net ayrışan canlı renkler; fazlası için altın oran tonları.
# Sarı (#FFC400) markaya ve ofis işaretçisine ayrıldı — hiçbir bölge sarı değildir.
TEMEL_RENKLER = ["#6EFF3D", "#1FC7FF", "#FF3D8E", "#1FFFC7", "#5C77FF", "#F7A164", "#EA00FF", "#FF2E2E",
                 "#9BE564", "#B8F2E6", "#E6ADEA", "#D65BD6"]
MARKA_SARI = "#FFC400"


def renkler(n: int) -> list[str]:
    """N bölge için palet. 12'ye kadar el seçimi, fazlası altın oran tonları.

    Üretilen tonlardan marka sarısına (ΔE76 < 38 — denetim eşiği 30, pay bırakılır) düşenler
    tonu kaydırılarak ayrılır:
    sarı yalnız ofis işaretçisinin ve marka vurgusunun rengidir, hiçbir bölge sarı olmaz.
    """
    if n <= len(TEMEL_RENKLER):
        return TEMEL_RENKLER[:n]
    sari = _srgb_lab(MARKA_SARI)
    out = []
    for i in range(n):
        h = (0.13 + i * 0.61803398875) % 1.0
        isik = 0.58 if i % 2 else 0.5
        for _ in range(16):
            r, g, b = colorsys.hls_to_rgb(h, isik, 0.85)
            onerilen = "#{:02X}{:02X}{:02X}".format(int(r * 255), int(g * 255), int(b * 255))
            if float(np.sqrt(((_srgb_lab(onerilen) - sari) ** 2).sum())) >= 38.0:
                break
            h = (h + 0.055) % 1.0
        out.append(onerilen)
    return out


# ----------------------------------------------------------------- renk denetimi (CIELAB ΔE76)
def _srgb_lab(renk: str) -> np.ndarray:
    c = np.array([int(renk.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)], float) / 255
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    M = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = (M @ c) / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.array([116 * f[1] - 16, 500 * (f[0] - f[1]), 200 * (f[1] - f[2])])


def renk_ayrimi(renkler_: list[str]) -> float:
    """Listedeki renkler arasındaki en küçük CIELAB ΔE76 farkı."""
    lab = np.array([_srgb_lab(r) for r in renkler_])
    d = np.sqrt(((lab[:, None, :] - lab[None, :, :]) ** 2).sum(2))
    np.fill_diagonal(d, np.inf)
    return float(d.min())


def _haversine_km(lat1, lon1, lat2, lon2):
    p = np.pi / 180
    a = np.sin((lat2 - lat1) * p / 2) ** 2 + np.cos(lat1 * p) * np.cos(lat2 * p) * np.sin((lon2 - lon1) * p / 2) ** 2
    return 12742 * np.arcsin(np.sqrt(a))


def _mst_km(x: np.ndarray, y: np.ndarray) -> float:
    """Birim noktalarını birleştiren en kısa ağ (MST) uzunluğu — saha gezisi yükü göstergesi."""
    pts = np.unique(np.c_[x, y].round(4), axis=0)
    if len(pts) < 2:
        return 0.0
    if len(pts) == 2:
        return float(np.hypot(*(pts[0] - pts[1])))
    try:
        tri = Delaunay(pts)
        e = np.vstack([tri.simplices[:, [0, 1]], tri.simplices[:, [1, 2]], tri.simplices[:, [0, 2]]])
    except Exception:  # eş doğrusal noktalar
        o = np.argsort(pts[:, 0])
        return float(np.hypot(*np.diff(pts[o], axis=0).T).sum())
    e = np.unique(np.sort(e, 1), axis=0)
    w = np.hypot(*(pts[e[:, 0]] - pts[e[:, 1]]).T)
    g = coo_matrix((w + 1e-9, (e[:, 0], e[:, 1])), shape=(len(pts), len(pts)))
    return float(minimum_spanning_tree(g).sum())


# ----------------------------------------------------------------- sınır poligonları
def _voronoi_hucreleri(xy: np.ndarray, bolge: np.ndarray, n: int) -> dict[int, object]:
    """Binaların Voronoi mozaiği; bölge başına birleştirilmiş, örtüşmeyen hücre."""
    uniq, ters = np.unique(xy, axis=0, return_inverse=True)
    ters = np.asarray(ters).ravel()
    bu = np.zeros(len(uniq), int)
    bu[ters[::-1]] = np.asarray(bolge)[::-1]          # aynı noktadaki ilk binanın bölgesi
    mp = shapely.multipoints(uniq)
    kutu = shapely.buffer(shapely.box(*shapely.bounds(mp)), 5000, quad_segs=1)
    hucre = shapely.get_parts(shapely.voronoi_polygons(mp, extend_to=kutu, ordered=True))
    if len(hucre) != len(uniq):                       # beklenmedik sürüm davranışı: kırpma yok
        return {}
    kodlar, gecmeler = [], []
    for k in range(1, n + 1):
        m = bu == k
        if not m.any():
            continue
        parca = hucre[m]
        try:
            g = shapely.coverage_union_all(parca)
        except Exception:
            g = shapely.union_all(parca)
        kodlar.append(k)
        gecmeler.append(g)
    if not kodlar:
        return {}
    try:
        # Ortak sınırları koruyarak sadeleştirir: bölgeler örtüşmeden kalır, nokta sayısı çok azalır
        gecmeler = list(shapely.coverage_simplify(np.array(gecmeler, dtype=object), 60.0))
    except Exception:
        pass
    return dict(zip(kodlar, gecmeler))


def _geri_cevir(geo: dict, kx: float, ky: float, lon0: float, lat0: float) -> dict:
    def g(c):
        return [round(c[0] / kx + lon0, 6), round(c[1] / ky + lat0, 6)]

    if geo["type"] == "Polygon":
        geo["coordinates"] = [[g(c) for c in r] for r in geo["coordinates"]]
    elif geo["type"] == "MultiPolygon":
        geo["coordinates"] = [[[g(c) for c in r] for r in p] for p in geo["coordinates"]]
    else:                                  # beklenmedik geometri: uygulama yalnız (Multi)Polygon okur
        return {"type": "Polygon", "coordinates": []}
    return geo


def _sinir_poligonu(xy: np.ndarray, hucre, kx: float, ky: float, lon0: float, lat0: float,
                    tampon_m: float = 220.0):
    """Bina tamponu → içe büzme → sadeleştirme → Voronoi hücresiyle kırpma.

    Sadeleştirme kırpmadan önce yapılır: ortak sınır birebir Voronoi kenarı kalır,
    bölgeler bu yüzden hiç örtüşmez.
    """
    tampon = shapely.union_all(shapely.buffer(shapely.points(xy), tampon_m, quad_segs=6))
    alan = shapely.simplify(shapely.buffer(tampon, -tampon_m * 0.35), 35)
    if hucre is not None:
        kirpik = shapely.intersection(alan, hucre)
        if not shapely.is_empty(kirpik) and shapely.area(kirpik) > 0:
            alan = kirpik
    alan = shapely.make_valid(alan)
    if alan.geom_type == "Polygon":
        parcalar = [alan] if not alan.is_empty else []
    else:
        parcalar = [p for p in shapely.get_parts(alan) if p.geom_type == "Polygon" and not p.is_empty]
        alan = shapely.union_all(parcalar) if parcalar else alan
    etiket = None
    if parcalar:
        en_buyuk = max(parcalar, key=lambda p: p.area)
        try:
            p = polylabel(en_buyuk, tolerance=20)
            etiket = [round(p.x / kx + lon0, 6), round(p.y / ky + lat0, 6)]
        except Exception:
            c = en_buyuk.representative_point()
            etiket = [round(c.x / kx + lon0, 6), round(c.y / ky + lat0, 6)]
    geo = _geri_cevir(mapping(alan), kx, ky, lon0, lat0)
    return geo, float(shapely.area(alan) / 1e6), etiket


# ----------------------------------------------------------------- bölge adları
def _kisa_ilce(i: str) -> str:
    return "Yalova" if str(i).startswith("Yalova") else str(i)


def _yon(dx: float, dy: float) -> str:
    """Metre cinsinden fark vektörünün baskın yönü: Kuzey / Güney / Doğu / Batı."""
    if abs(dy) >= abs(dx):
        return "Kuzey" if dy >= 0 else "Güney"
    return "Doğu" if dx >= 0 else "Batı"


def _yerlestir(liste: list[str], deger: str, konum: int, ust: int) -> list[str]:
    out = [x for x in liste if x != deger]
    out.insert(min(konum, len(out)), deger)
    return out[:ust]


def _tekillestir(kayitlar: list[dict], alan: str, ayrac: str) -> None:
    """Aynı ada sahip bölgeleri ayırır.

    Sıra: imza mahallesi → yön → ikinci ayırıcı mahalle → (B{k}). Ada zaten geçen bir parça
    hiçbir turda tekrar eklenmez; "Yeni–Yeni" gibi kendini tekrar eden adlar bu yüzden oluşmaz,
    ve kod eki ("Nilüfer–Batı (B3)") ancak ayırt edecek mahalle kalmadığında yazılır.
    """
    kullanilan: set[str] = set()

    def _parcalar(ad: str) -> set[str]:
        return {p.strip() for p in ad.replace(" · ", "\x00").replace(ayrac, "\x00").split("\x00") if p.strip()}

    def _mahalle_ek(r: dict, siki: bool) -> str | None:
        var = _parcalar(r[alan])
        for m in r["_mah_sira"]:
            if not m or m == "Bilinmiyor" or m in var:
                continue
            if siki and m in kullanilan:
                continue
            kullanilan.add(m)
            return m
        return None

    for tur in range(4):
        gruplar: dict[str, list[dict]] = defaultdict(list)
        for r in kayitlar:
            gruplar[r[alan]].append(r)
        cakisan = [g for g in gruplar.values() if len(g) > 1]
        if not cakisan:
            return
        for g in cakisan:
            for r in g:
                if tur == 0:
                    ek = _mahalle_ek(r, True)
                    if ek:
                        r[alan] = f"{r[alan]}{ayrac}{ek}"
                elif tur == 1:
                    yon = r["_yon"]
                    if yon and yon not in _parcalar(r[alan]):
                        r[alan] = f"{r[alan]}{ayrac}{yon}"
                        r["_yon_ekli"] = True
                elif tur == 2:
                    ek = _mahalle_ek(r, False)
                    if not ek:
                        continue
                    yon = r["_yon"]
                    if r.get("_yon_ekli") and yon and r[alan].endswith(f"{ayrac}{yon}"):
                        # "Nilüfer–Batı" + "Görükle" → "Nilüfer–Görükle Batı" (üç parçalı ada dönmesin)
                        r[alan] = f"{r[alan][: -len(yon)]}{ek} {yon}"
                    else:
                        r[alan] = f"{r[alan]}{ayrac}{ek}"
                else:
                    r[alan] = f"{r[alan]} ({r['kod']})"


def _ad_uret(g: pd.DataFrame, ilce_toplam: dict, ilce_merkez: dict, ust_mah: list[str],
             ana_ilce: str, kx: float, ky: float) -> tuple[str, str]:
    """Bölgenin uzun adı ve kısa adı. Döner: ("Mudanya · Yalova · Gemlik · Orhangazi", "Mudanya–Yalova").

    * **sahip** ilçe: HP'sinin ≥ %50'si bu bölgede olan ilçe — adı olduğu gibi yazılır.
    * **kısmi** ilçe: sahip olunmayan ama bölgenin HP'sinin ≥ %20'sini veren ilçe — yön ekiyle
      yazılır ("Yıldırım Doğu"), çünkü ilçenin yalnız bir parçası bu bölgededir.
    * İki veya daha çok ilçe seçilmediyse tek ilçe + imza mahalleleri kullanılır.
    * Bölgede Yalova binası varsa "Yalova" her iki adda da 2. sıraya konur (sunumda hep görünsün).
    """
    pay = g.groupby("ilce")["res_hp"].sum()
    top = max(float(pay.sum()), 1.0)
    ic = (pay / top).sort_values(ascending=False)
    sahip = {i for i in ic.index if ilce_toplam.get(i, 0) > 0 and float(pay[i]) / ilce_toplam[i] >= 0.5}
    kismi = {i for i in ic.index if i not in sahip and float(ic[i]) >= 0.20}
    secili = [i for i in ic.index if i in sahip or i in kismi][:4]

    if len(secili) >= 2:
        parcalar = []
        for i in secili:
            metin = _kisa_ilce(i)
            if i in kismi and i in ilce_merkez:
                gi = g[g["ilce"] == i]
                wi = gi["res_hp"].clip(lower=0) + 1
                clon = float(np.average(gi["lon"], weights=wi))
                clat = float(np.average(gi["lat"], weights=wi))
                ilon, ilat = ilce_merkez[i]
                metin += " " + _yon((clon - ilon) * kx, (clat - ilat) * ky)
            parcalar.append(metin)
        kisa_liste = [_kisa_ilce(i) for i in secili if i in sahip][:2] or [parcalar[0].split(" ")[0]]
    else:
        ana = _kisa_ilce(ana_ilce)
        parcalar = [ana] + ([" – ".join(ust_mah)] if ust_mah else [])
        kisa_liste = [ust_mah[0]] if ust_mah else [ana]

    if (g["il"] == "Yalova").any():                 # Yalova her zaman görünür (2. sırada)
        parcalar = _yerlestir(parcalar, "Yalova", 1, 4)
        kisa_liste = _yerlestir(kisa_liste, "Yalova", 1, 2)
    return " · ".join(parcalar[:4]), "–".join(kisa_liste[:2])


# ----------------------------------------------------------------- ana giriş
def bolge_ozetleri(df: pd.DataFrame, atama: pd.Series, olcu: str, hedef: float, poligon: bool = True) -> list[dict]:
    """Her bölge için KPI sözlüğü (bölge no sırasıyla)."""
    d = df.assign(bolge=df["bina_serial"].map(atama)).dropna(subset=["bolge"])
    d["bolge"] = d["bolge"].astype(int)
    n = int(d["bolge"].max())
    lat0, lon0 = float(d["lat"].mean()), float(d["lon"].mean())
    kx_m, ky_m = _m_per_deg_lon(lat0), M_PER_DEG_LAT
    kx, ky = kx_m / 1000, ky_m / 1000
    renk = renkler(n)
    mah_toplam = d.groupby(["ilce", "mahalle"])["res_hp"].sum()
    ilce_toplam = d.groupby("ilce")["res_hp"].sum().to_dict()
    iw = d["res_hp"].clip(lower=0) + 1
    ilce_merkez = {i: (float(np.average(gg["lon"], weights=iw.loc[gg.index])),
                       float(np.average(gg["lat"], weights=iw.loc[gg.index])))
                   for i, gg in d.groupby("ilce")}

    xy = np.c_[(d["lon"].to_numpy() - lon0) * kx_m, (d["lat"].to_numpy() - lat0) * ky_m]
    hucreler = _voronoi_hucreleri(xy, d["bolge"].to_numpy(), n) if poligon else {}

    sonuc = []
    for k in range(1, n + 1):
        maske = (d["bolge"] == k).to_numpy()
        g = d[maske]
        if g.empty:
            sonuc.append({"bolge": k, "kod": f"B{k}", "bos": True})
            continue
        w = g["res_hp"].clip(lower=0) + 1
        mlat, mlon = float(np.average(g["lat"], weights=w)), float(np.average(g["lon"], weights=w))
        uz = _haversine_km(g["lat"].to_numpy(), g["lon"].to_numpy(), mlat, mlon)
        ilce_pay = g.groupby("ilce")["res_hp"].sum().sort_values(ascending=False)
        ilce_pay = ilce_pay[ilce_pay > 0] / max(g["res_hp"].sum(), 1)
        mah = g.groupby(["ilce", "mahalle"]).agg(firsat=("firsat", "sum"), res_hp=("res_hp", "sum"), bina=("bina", "sum")) \
               .sort_values("firsat", ascending=False).reset_index()
        ana_ilce = ilce_pay.index[0] if len(ilce_pay) else g["ilce"].iloc[0]
        # Bölgenin "imza" mahalleleri: HP'sinin çoğu bu bölgede olan, adı tekrar etmeyen en büyük 2 mahalle
        mah_hp = mah.set_index(["ilce", "mahalle"])["res_hp"]
        mah_pay = (mah_hp / mah_toplam.reindex(mah_hp.index).clip(lower=1)).fillna(0)
        buyuk = mah.sort_values("res_hp", ascending=False)
        ust_mah: list[str] = []
        for _, satir in buyuk.iterrows():
            m = satir["mahalle"]
            if m != "Bilinmiyor" and float(mah_pay.loc[(satir["ilce"], m)]) >= 0.5 and m not in ust_mah:
                ust_mah.append(m)
            if len(ust_mah) == 2:
                break
        birimler = g.groupby("site_grup")[["lon", "lat"]].mean()
        ad, kisa = _ad_uret(g, ilce_toplam, ilce_merkez, ust_mah, ana_ilce, kx, ky)
        ilon, ilat = ilce_merkez.get(ana_ilce, (mlon, mlat))
        kayit = {
            "bolge": k,
            "kod": f"B{k}",
            "ad": ad,
            "kisa_ad": kisa,
            "renk": renk[k - 1],
            "bina": int(len(g)),
            "site": int(g["site_grup"].nunique()),
            "toplam_hp": int(g["toplam_hp"].sum()),
            "res_hp": int(g["res_hp"].sum()),
            "soho_hp": int(g["soho_hp"].sum()),
            "aktif_res": int(g["aktif_res"].sum()),
            "aktif_toplam": int(g["aktif_toplam"].sum()),
            "firsat": int(g["firsat"].sum()),
            "penetrasyon": float(g["aktif_res"].sum() / max(g["res_hp"].sum(), 1)),
            "kurulum_son_ay": int(g["kurulum_son_ay"].sum()),
            "churn_son_ay": int(g["churn_son_ay"].sum()),
            "tv": int(g["tv"].fillna(0).sum()),
            "olcu": olcu,
            "olcu_deger": float(g[olcu].sum()),
            "sapma": float(g[olcu].sum() / hedef - 1),
            "merkez": [round(mlon, 5), round(mlat, 5)],
            "ofis_km": float(_haversine_km(config.OFIS["lat"], config.OFIS["lon"], mlat, mlon)),
            "ort_merkez_km": float(np.average(uz, weights=w)),
            "maks_merkez_km": float(uz.max()),
            "mst_km": _mst_km(birimler["lon"].to_numpy() * kx, birimler["lat"].to_numpy() * ky),
            "ilceler": [{"ilce": i, "pay": round(float(p), 4)} for i, p in ilce_pay.items()],
            "mahalle_sayisi": int(g.groupby(["ilce", "mahalle"]).ngroups),
            "ust_mahalleler": mah.head(8).to_dict("records"),
            "yalova_bina": int((g["il"] == "Yalova").sum()),
            "yalova_res_hp": int(g.loc[g["il"] == "Yalova", "res_hp"].sum()),
            "_mah_sira": [m for m in buyuk["mahalle"].tolist() if m != "Bilinmiyor"],
            "_yon": _yon((mlon - ilon) * kx, (mlat - ilat) * ky),
        }
        if poligon:
            kayit["poligon"], kayit["alan_km2"], et = _sinir_poligonu(xy[maske], hucreler.get(k), kx_m, ky_m, lon0, lat0)
            kayit["etiket"] = et or kayit["merkez"]
        sonuc.append(kayit)

    dolu = [r for r in sonuc if not r.get("bos")]
    _tekillestir(dolu, "ad", " · ")
    _tekillestir(dolu, "kisa_ad", "–")
    for r in dolu:
        r.pop("_mah_sira", None)
        r.pop("_yon", None)
        r.pop("_yon_ekli", None)
    return sonuc
