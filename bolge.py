"""Bursa fiber satış bölgeleme — komut satırı.

Örnekler:
    python bolge.py                      # 8 satışçı, RES HP dengesi (varsayılan)
    python bolge.py --n 10               # 10 satışçı
    python bolge.py --n 12 --olcu firsat # boş HP (fırsat) dengesi
    python bolge.py --n 8 --haric-il Yalova

Çıktılar: outputs/N08_res_hp/ (atama.csv, bolgeler.json, Excel raporu, plan_N08.json)
ve sunum uygulamasının veri paketi: app/src/data/generated/
Ham veri değiştiğinde önce:  python -m dsale.enrich
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd

from dsale import bundle, config, metrics
from dsale.partition import ALGORITMA_SURUMU, bolgele

ATAMA_KOLONLARI = ["bina_serial", "tellcordia_id", "location_id", "ad", "site_adi", "blok_adi", "kapi_no", "mahalle",
                   "cadde", "sokak", "ilce", "il", "obek", "lat", "lon", "kat", "toplam_hp", "res_hp", "aktif_res",
                   "firsat", "penetrasyon", "ofis_km"]


def master_oku() -> pd.DataFrame:
    if not config.MASTER_CSV.exists():
        sys.exit("Master tablo yok. Önce çalıştırın:  python -m dsale.enrich")
    return pd.read_csv(config.MASTER_CSV, encoding="utf-8-sig", dtype={"tellcordia_id": str, "location_id": str})


def aralik(spec: str) -> list[int]:
    out: set[int] = set()
    for parca in filter(None, (p.strip() for p in spec.split(","))):
        if "-" in parca:
            a, b = map(int, parca.split("-"))
            out.update(range(a, b + 1))
        else:
            out.add(int(parca))
    return sorted(k for k in out if k >= 2)


def _onbellek_anahtari(olcu: str, haric: list[str]) -> str:
    """Alternatif plan önbelleğinin anahtarı.

    Algoritma sürümü ve master CSV'nin yanı sıra `dsale/metrics.py` de anahtara girer: önbellekteki
    plan kayıtları bölge ADLARINI ve RENKLERİNİ de taşıyor, dolayısıyla yalnız metrics değişse bile
    eski kayıtlar bayatlıyor (isim tekilleştirme / palet düzeltmeleri sessizce göz ardı ediliyordu).
    """
    m = config.MASTER_CSV.stat()
    mm = (Path(__file__).resolve().parent / "dsale" / "metrics.py").stat()
    imza = f"{ALGORITMA_SURUMU}|{m.st_size}|{int(m.st_mtime)}|{mm.st_size}|{int(mm.st_mtime)}|{olcu}|{','.join(sorted(haric))}"
    return hashlib.md5(imza.encode()).hexdigest()[:10]


def _alternatif_hesapla(args) -> tuple[int, dict]:
    n, olcu, haric, anahtar = args
    klasor = config.OUTPUTS / "_onbellek" / anahtar
    yol = klasor / f"plan_N{n:02d}.json"
    if yol.exists():
        return n, json.load(open(yol, encoding="utf-8"))
    df = master_oku()
    if haric:                       # ana çalıştırmayla aynı süzgeç: birim sözlüğü birebir aynı olmalı
        df = df[~df["il"].isin(haric)].reset_index(drop=True)
    s = bolgele(df, n, olcu=olcu, haric_il=None)
    bolgeler = metrics.bolge_ozetleri(df, s.atama, olcu, s.hedef)
    birim_sozluk = sorted(df["site_grup"].fillna("").astype(str).unique().tolist())
    plan = bundle.plan_kaydi(df, s, bolgeler, birim_sozluk)
    klasor.mkdir(parents=True, exist_ok=True)
    json.dump(plan, open(yol, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    return n, plan


def calistir(n: int, olcu: str, haric: list[str], alternatifler: list[int], excel: bool, paket: bool, paralel: int) -> Path:
    t0 = time.time()
    df = master_oku()
    if haric:
        df = df[~df["il"].isin(haric)].reset_index(drop=True)
    print(f"▶ {len(df):,} bina · {n} bölge · denge ölçüsü: {olcu} ({config.OLCULER.get(olcu, olcu)})")

    sure: dict[str, float] = {}
    t = time.time()
    s = bolgele(df, n, olcu=olcu, haric_il=None, anlik_kaydet=True)
    sure["bölgeleme"] = time.time() - t
    t = time.time()
    bolgeler = metrics.bolge_ozetleri(df, s.atama, olcu, s.hedef)
    sure["ölçümler"] = time.time() - t
    sapmalar = [b["sapma"] for b in bolgeler]
    print(f"  bölgeleme {s.sure_sn}s · ölçümler {sure['ölçümler']:.1f}s · hedef {s.hedef:,.0f} · "
          f"sapma {min(sapmalar):+.2%} / {max(sapmalar):+.2%} · ada düzeltme {s.parametreler.get('ada_duzeltme', 0)}")

    ek = ("_haric_" + "_".join(h.lower() for h in haric)) if haric else ""
    cikti = config.OUTPUTS / f"N{n:02d}_{olcu}{ek}"
    cikti.mkdir(parents=True, exist_ok=True)

    atama = df[ATAMA_KOLONLARI].copy()
    atama.insert(0, "bolge", atama["bina_serial"].map(s.atama).astype(int))
    ad_map = {b["bolge"]: b["ad"] for b in bolgeler}
    atama.insert(1, "bolge_adi", atama["bolge"].map(ad_map))
    atama.sort_values(["bolge", "ilce", "mahalle", "ad"]).to_csv(cikti / "atama.csv", index=False, encoding="utf-8-sig")

    ozet = {"n": n, "olcu": olcu, "hedef": s.hedef, "haric_il": haric, "sure_sn": s.sure_sn,
            "parametreler": s.parametreler, "toplam": {c: int(df[c].sum()) for c in ["bina", "res_hp", "toplam_hp", "aktif_res", "firsat"]},
            "ofis": config.OFIS, "bolgeler": bolgeler}
    json.dump(ozet, open(cikti / "bolgeler.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    birim_sozluk = sorted(df["site_grup"].fillna("").astype(str).unique().tolist())
    ana_plan = bundle.plan_kaydi(df, s, bolgeler, birim_sozluk)
    json.dump(ana_plan, open(cikti / f"plan_N{n:02d}.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))

    if excel:
        t = time.time()
        try:
            from dsale import excel_report
            yol = excel_report.build(df, s, bolgeler, cikti)
            print(f"  Excel: {yol}")
        except ImportError:
            print("  (Excel modülü henüz yok: dsale/excel_report.py)")
        sure["excel"] = time.time() - t

    if paket:
        t = time.time()
        alt = [k for k in alternatifler if k != n]
        planlar: dict[int, dict] = {}
        if alt:
            anahtar = _onbellek_anahtari(olcu, haric)
            print(f"  alternatif planlar ({len(alt)} adet, {paralel} paralel)…", flush=True)
            for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
                os.environ[v] = "1"          # her işçi tek iş parçacığı: aşırı yüklenmeyi önler
            with ProcessPoolExecutor(max_workers=paralel) as ex:
                for k, plan in ex.map(_alternatif_hesapla, [(k, olcu, haric, anahtar) for k in alt]):
                    planlar[k] = plan
                    print(f"    N={k:>2}  sapma {plan['sapma_min']:+.2%}/{plan['sapma_maks']:+.2%}  {plan['sure_sn']}s", flush=True)
        boyut = bundle.yaz(df, ana_plan, planlar)
        sure["paket"] = time.time() - t
        print(f"  uygulama veri paketi: {bundle.APP_DATA}  {boyut}")
        dengesiz = [(k, p["sapma_min"], p["sapma_maks"]) for k, p in sorted({**planlar, n: ana_plan}.items())
                    if max(abs(p["sapma_min"]), abs(p["sapma_maks"])) > 0.01]
        if dengesiz:
            print("  ! ±%1 dışında kalan planlar: " +
                  " · ".join(f"N={k} {a:+.2%}/{b:+.2%}" for k, a, b in dengesiz))
        else:
            print("  ✓ bütün planlar ±%1 içinde")

    print(f"✔ bitti ({time.time() - t0:.0f}s) → {cikti}")
    print("  süreler: " + " · ".join(f"{k} {v:.1f}s" for k, v in sure.items()))
    return cikti


def main() -> None:
    ap = argparse.ArgumentParser(description="Bursa fiber satış bölgeleme")
    ap.add_argument("--n", type=int, default=config.VARSAYILAN_N, help="satışçı / bölge sayısı")
    ap.add_argument("--olcu", default=config.VARSAYILAN_OLCU, choices=list(config.OLCULER), help="dengelenecek ölçü")
    ap.add_argument("--haric-il", nargs="*", default=[], help="hariç tutulacak il(ler), örn. Yalova")
    ap.add_argument("--alternatifler", default=config.VARSAYILAN_ALTERNATIFLER, help="uygulamadaki N kaydırıcısı için, örn. 2-30,35,40")
    ap.add_argument("--excel", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument("--paket", action=argparse.BooleanOptionalAction, default=True, help="app/src/data/generated paketini üret")
    ap.add_argument("--paralel", type=int, default=max(1, min(8, (os.cpu_count() or 4) - 2)))
    a = ap.parse_args()
    calistir(a.n, a.olcu, a.haric_il, aralik(a.alternatifler) if a.paket else [], a.excel, a.paket, a.paralel)


if __name__ == "__main__":
    main()
