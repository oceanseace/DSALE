"""Çevrimdışı altlık harita: OpenStreetMap'ten ana yollar, kıyı/su ve ilçe sınırları.

Bir kez çalıştırılır; sonuç `data/ref/osm_*.geojson` olarak saklanır.
Veri © OpenStreetMap katkıcıları (ODbL) — sunumda kaynak olarak belirtilir.

    python -m dsale.basemap
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request

import pandas as pd
from shapely.geometry import LineString, MultiLineString, Polygon, mapping, shape
from shapely.ops import linemerge, polygonize, unary_union

from . import config

AYNALAR = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
USER_AGENT = "DSALE-bolgeleme/1.0 (tek seferlik altlik indirme)"


def _overpass(sorgu: str, deneme: int = 2) -> dict:
    son_hata = None
    for url in AYNALAR:
        for _ in range(deneme):
            try:
                istek = urllib.request.Request(url, data=urllib.parse.urlencode({"data": sorgu}).encode(),
                                               headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(istek, timeout=240) as r:
                    return json.loads(r.read().decode("utf-8"))
            except Exception as e:  # 429/504 vb. -> sonraki ayna
                son_hata = e
                time.sleep(5)
    raise RuntimeError(f"Overpass erişilemedi: {son_hata}")


def _bbox(pay: float = 0.08) -> str:
    df = pd.read_csv(config.MASTER_CSV, encoding="utf-8-sig", usecols=["lat", "lon"])
    return f"{df.lat.min() - pay},{df.lon.min() - pay},{df.lat.max() + pay},{df.lon.max() + pay}"


def _yaz(ad: str, ozellikler: list[dict]) -> None:
    fc = {"type": "FeatureCollection", "features": ozellikler,
          "attribution": "© OpenStreetMap katkıcıları (ODbL)"}
    yol = config.REF / f"osm_{ad}.geojson"
    json.dump(fc, open(yol, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(ad, len(ozellikler), "öğe", round(yol.stat().st_size / 1e6, 2), "MB")


def _yuvarla(geom, basamak: int = 5):
    def r(c):
        return [round(c[0], basamak), round(c[1], basamak)]
    g = mapping(geom)
    t = g["type"]
    if t == "LineString":
        g["coordinates"] = [r(c) for c in g["coordinates"]]
    elif t == "MultiLineString":
        g["coordinates"] = [[r(c) for c in l] for l in g["coordinates"]]
    elif t == "Polygon":
        g["coordinates"] = [[r(c) for c in ring] for ring in g["coordinates"]]
    elif t == "MultiPolygon":
        g["coordinates"] = [[[r(c) for c in ring] for ring in p] for p in g["coordinates"]]
    return g


def yollar(bbox: str) -> None:
    sinif = {"motorway": 1, "trunk": 1, "primary": 2, "secondary": 3, "tertiary": 4}
    j = _overpass(f'[out:json][timeout:200];way["highway"~"^(motorway|trunk|primary|secondary|tertiary)$"]({bbox});out geom;')
    ozellik = []
    for el in j["elements"]:
        if "geometry" not in el:
            continue
        ls = LineString([(p["lon"], p["lat"]) for p in el["geometry"]]).simplify(0.00015)
        s = sinif.get(el["tags"].get("highway"), 4)
        ozellik.append({"type": "Feature", "properties": {"s": s}, "geometry": _yuvarla(ls)})
    _yaz("yollar", ozellik)


def su(bbox: str) -> None:
    j = _overpass(f'[out:json][timeout:200];(way["natural"="coastline"]({bbox});way["natural"="water"]["water"~"lake|reservoir"]({bbox});relation["natural"="water"]["water"~"lake|reservoir"]({bbox}););out geom;')
    kiyi, gol = [], []
    for el in j["elements"]:
        t = el.get("tags", {})
        if el["type"] == "way" and "geometry" in el:
            pts = [(p["lon"], p["lat"]) for p in el["geometry"]]
            if t.get("natural") == "coastline":
                kiyi.append(LineString(pts))
            elif len(pts) >= 4 and pts[0] == pts[-1]:
                gol.append(Polygon(pts))
        elif el["type"] == "relation":
            dis = [LineString([(p["lon"], p["lat"]) for p in m["geometry"]]) for m in el.get("members", [])
                   if m.get("role") == "outer" and "geometry" in m]
            gol.extend(polygonize(linemerge(dis)) if dis else [])
    ozellik = []
    if kiyi:
        k = linemerge(kiyi).simplify(0.0002)
        ozellik.append({"type": "Feature", "properties": {"tur": "kiyi"}, "geometry": _yuvarla(k)})
    for p in gol:
        if p.is_valid and p.area > 0.00005:      # ~0.5 km²'den büyük göller/barajlar
            ozellik.append({"type": "Feature", "properties": {"tur": "gol"}, "geometry": _yuvarla(p.simplify(0.0003))})
    _yaz("su", ozellik)


def ilceler(bbox: str) -> None:
    j = _overpass(f'[out:json][timeout:200];relation["boundary"="administrative"]["admin_level"="6"]({bbox});out geom;')
    ozellik = []
    for el in j["elements"]:
        dis = [LineString([(p["lon"], p["lat"]) for p in m["geometry"]]) for m in el.get("members", [])
               if m.get("role") == "outer" and m.get("type") == "way" and "geometry" in m]
        if not dis:
            continue
        poly = unary_union(list(polygonize(linemerge(dis))))
        if poly.is_empty:
            continue
        ad = el["tags"].get("name", "")
        ozellik.append({"type": "Feature", "properties": {"ad": ad},
                        "geometry": _yuvarla(poly.simplify(0.0004))})
    _yaz("ilce", ozellik)


if __name__ == "__main__":
    config.REF.mkdir(parents=True, exist_ok=True)
    kutu = _bbox()
    print("bbox", kutu)
    for adim in (yollar, su, ilceler):
        try:
            adim(kutu)
        except Exception as e:
            print("HATA", adim.__name__, e)
