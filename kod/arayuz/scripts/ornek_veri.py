# Saha uygulamasi icin ornek veri (fixture) uretir.
# Gercek atama.csv'den bolge 3 (Nilufer - 23 Nisan / Ataevler) alinir.
import csv, json, math, random, io, os, sys

if __package__ in (None, ""):  # dogrudan calistirildi: kod/ ice aktarma yoluna (yollar)
    sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")))
import yollar  # noqa: E402

ATAMA = str(yollar.CIKTI / "N08_res_hp" / "atama.csv")
CIKIS = str(yollar.ARAYUZ / "src" / "api" / "sahteVeri.ts")
YOLLAR_GEOJSON = str(yollar.VERI / "ref" / "osm_yollar.geojson")
BOLGE = 3
OFIS = (40.22043814320989, 28.953528321918512)

random.seed(20260921)

rows = []
with io.open(ATAMA, encoding="utf-8-sig", newline="") as f:
    for r in csv.DictReader(f):
        if int(float(r["bolge"])) != BOLGE:
            continue
        try:
            lat = float(r["lat"]); lon = float(r["lon"])
        except Exception:
            continue
        rows.append({
            "bina_serial": r["bina_serial"],
            "ad": r["ad"].strip(),
            "site_adi": (r["site_adi"] or "").strip() or None,
            "mahalle": r["mahalle"].strip(),
            "ilce": r["ilce"].strip(),
            "cadde": (r["cadde"] or "").strip() or None,
            "sokak": (r["sokak"] or "").strip() or None,
            "kapi_no": (r["kapi_no"] or "").strip() or None,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "kat": int(float(r["kat"])) if r["kat"] else None,
            "daire": int(float(r["res_hp"])) if r["res_hp"] else 0,
            "res_hp": int(float(r["res_hp"])) if r["res_hp"] else 0,
            "aktif_res": int(float(r["aktif_res"])) if r["aktif_res"] else 0,
            "firsat": int(float(r["firsat"])) if r["firsat"] else 0,
        })

print("bolge %d bina: %d" % (BOLGE, len(rows)))

def mesafe(a, b):
    # haversine, metre
    R = 6371000.0
    p1 = math.radians(a[0]); p2 = math.radians(b[0])
    dp = math.radians(b[0]-a[0]); dl = math.radians(b[1]-a[1])
    h = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*R*math.asin(math.sqrt(h))

# --- Bugunun rotasi: yuksek firsatli bir mahalleden 25 bina, en yakin komsu siralamasi
mahalle_sayac = {}
for r in rows:
    mahalle_sayac.setdefault(r["mahalle"], []).append(r)
hedef_mahalle = max(mahalle_sayac.items(), key=lambda kv: sum(x["firsat"] for x in kv[1]))[0]
havuz = sorted(mahalle_sayac[hedef_mahalle], key=lambda x: -x["firsat"])[:90]
print("rota mahallesi:", hedef_mahalle, "havuz:", len(havuz))

kalan = list(havuz)
nokta = OFIS
rota = []
while kalan and len(rota) < 25:
    kalan.sort(key=lambda x: mesafe(nokta, (x["lat"], x["lon"])))
    s = kalan.pop(0)
    s = dict(s)
    s["mesafe_m"] = int(round(mesafe(nokta, (s["lat"], s["lon"]))))
    rota.append(s)
    nokta = (s["lat"], s["lon"])

# Sunucu gibi IKI ayri durum: gorev_durum = bugunku liste, durum = binanin hali
for i, s in enumerate(rota, 1):
    s["sira"] = i
    s["gorev_durum"] = "bekliyor"
    s["durum"] = "planli"

# ilk 7 bina "bugun yapildi" gorunsun - ekran gercekci olsun
for s in rota[:7]:
    s["gorev_durum"] = "tamam"
    s["durum"] = "ziyaret_edildi"

# --- Harita verisi: bolgenin tamami yerine temsili bir ornek (paket hafif kalsin)
ornek = rows if len(rows) <= 900 else random.sample(rows, 900)
rota_serial = {s["bina_serial"] for s in rota}
for r in ornek:
    if r["bina_serial"] in rota_serial:
        continue
d = []
for r in ornek:
    p = random.random()
    if r["bina_serial"] in rota_serial:
        d.append("planli")
    elif p < 0.26:
        d.append("ziyaret_edildi")
    elif p < 0.33:
        d.append("tekrar_gel")
    elif p < 0.36:
        d.append("girilemedi")
    elif p < 0.38:
        d.append("altyapi_sorunu")
    else:
        d.append("bekliyor")
harita = {
    "serial": [r["bina_serial"] for r in ornek],
    "lat": [r["lat"] for r in ornek],
    "lon": [r["lon"] for r in ornek],
    "durum": d,
    "firsat": [r["firsat"] for r in ornek],
    "ad": [r["ad"] for r in ornek],
}

# rotadaki binalar da haritada olsun
for s in rota:
    if s["bina_serial"] not in set(harita["serial"]):
        harita["serial"].append(s["bina_serial"])
        harita["lat"].append(s["lat"])
        harita["lon"].append(s["lon"])
        harita["durum"].append(s["durum"])
        harita["firsat"].append(s["firsat"])
        harita["ad"].append(s["ad"])
    else:
        i = harita["serial"].index(s["bina_serial"])
        harita["durum"][i] = s["durum"]

# --- Yollar: rota cevresindeki OSM yollarindan kucuk bir kesit
lats = [s["lat"] for s in rota]; lons = [s["lon"] for s in rota]
kutu = (min(lats)-0.012, min(lons)-0.012, max(lats)+0.012, max(lons)+0.012)
yol_ozellik = []
try:
    with io.open(YOLLAR_GEOJSON, encoding="utf-8") as f:
        gj = json.load(f)
    for ft in gj.get("features", []):
        g = ft.get("geometry") or {}
        if g.get("type") == "LineString":
            parcalar = [g["coordinates"]]
        elif g.get("type") == "MultiLineString":
            parcalar = g["coordinates"]
        else:
            continue
        for c in parcalar:
            ic = [p for p in c if kutu[1] <= p[0] <= kutu[3] and kutu[0] <= p[1] <= kutu[2]]
            if len(ic) >= 2:
                yol_ozellik.append({
                    "type": "Feature",
                    "geometry": {"type": "LineString",
                                 "coordinates": [[round(p[0], 5), round(p[1], 5)] for p in ic]},
                    "properties": None,
                })
        if len(yol_ozellik) > 700:
            break
except Exception as e:
    print("yol okunamadi:", e)
print("yol parcasi:", len(yol_ozellik))

bolge_toplam = len(rows)
bolge_dokunulan = sum(1 for x in d if x in ("ziyaret_edildi", "tekrar_gel", "girilemedi", "altyapi_sorunu"))
oran = bolge_dokunulan / max(1, len(d))
dokunulan = int(round(bolge_toplam * oran))

meta = {
    "bolge": BOLGE,
    "bolge_adi": "Nilüfer · 23 Nisan – Ataevler",
    "mahalle": hedef_mahalle,
    "ofis": {"lat": OFIS[0], "lon": OFIS[1]},
    "bolge_toplam": bolge_toplam,
    "bolge_dokunulan": dokunulan,
}

def ts(o):
    return json.dumps(o, ensure_ascii=False, separators=(",", ":"))

out = []
out.append("/* OTOMATİK ÜRETİLDİ — elle düzenlemeyin.")
out.append(" * Kaynak: cikti/N08_res_hp/atama.csv (bölge %d) + veri/ref/osm_yollar.geojson" % BOLGE)
out.append(" * Üreten: scripts/ornek_veri.py — yalnız `?sahte=1` modunda yüklenir.")
out.append(" */")
out.append("")
out.append("import type { GorevBinasi, HaritaVerisi, YolAgi } from './tipler';")
out.append("")
out.append("export const META = %s as const;" % ts(meta))
out.append("")
out.append("export const ROTA: GorevBinasi[] = %s;" % ts(rota))
out.append("")
out.append("export const HARITA: HaritaVerisi = %s;" % ts(harita))
out.append("")
out.append("export const YOLLAR: YolAgi = %s;" % ts({"type": "FeatureCollection", "features": yol_ozellik}))
out.append("")

with io.open(CIKIS, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(out))

print("yazildi:", CIKIS)
print("rota:", len(rota), "harita:", len(harita["serial"]))
