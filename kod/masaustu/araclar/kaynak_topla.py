"""Sunucunun salt okunur kaynaklarını dondurulmuş sunucunun ``_internal`` klasörüne kopyalar.

Yerleşim repo ile BİREBİR aynıdır (``veri/master/...``, ``kod/arayuz/dist/...``): kod yollarını
``kod/yollar.py``'den alır; donmuş sürümde ``yollar.KOK`` = ``_internal`` olduğu için aynı göreli yollar
orada da bulunur, kodda tek satır değişmez. Dosya zamanları korunur (``copy2``): veri kalitesi önbelleğinin imzası
kaynak dosyaların boyut+zamanına bakar, zaman değişirse 19.706 bina baştan hesaplanırdı.

Kişisel veri İÇERMEYEN, çalışma için gereken dosyalar alınır. Alınmayanlar bilinçli:
``veri/raw/data.xlsx`` (ham döküm), çalışma klasöründeki ``operasyon/obekler.json`` (kullanıcının canlı tanımı;
ilk kurulumda VERİ klasörüne ``ice-aktar`` getirir), ``saha.db``, ``gizli.key``, yedekler, günlükler.

    python kod/masaustu/araclar/kaynak_topla.py --hedef kod/masaustu/build/sunucu/_internal [--pwa <dist klasörü>]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import sys
from pathlib import Path

if __package__ in (None, ""):  # doğrudan çalıştırıldı: kod/ içe aktarma yoluna (yollar)
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import yollar  # noqa: E402

REPO = yollar.KOK


def _goreli(yol: Path) -> str:
    return yol.relative_to(REPO).as_posix()


# (repo içi yol, zorunlu mu)
DOSYALAR = [
    (_goreli(yollar.VERI / "master" / "bina_master.csv"), True),
    (_goreli(yollar.VERI / "master" / "bina_geometri.json"), False),
    (_goreli(yollar.VERI / "master" / "veri_kalitesi.json"), False),
    (_goreli(yollar.VERI / "master" / "bina_kalite_kanit.json"), False),   # önbellek: yoksa ilk açılışta hesaplanır
    (_goreli(yollar.VERI / "raw" / "onemap_bina_bursa.json"), False),      # veri kalitesi kanıtları (OneMap öznitelikleri)
    (_goreli(yollar.CIKTI / "N08_res_hp" / "atama.csv"), True),            # ilk kurulumda 8 bölge
    (_goreli(yollar.SUNUM_URETILEN / "binalar.json"), False),              # bölge planlayıcı: hazır planlar
    (_goreli(yollar.SUNUM_URETILEN / "planlar.json"), False),
    (_goreli(yollar.KOD / "operasyon" / "obekler.ornek.json"), False),
    (_goreli(yollar.KOD / "lisans" / "genel_anahtar.pem"), False),         # lisans doğrulama anahtarı (varsa)
]
KLASORLER = [
    (_goreli(yollar.VERI / "ref"), False),                                 # ilçe/mahalle sözlüğü, OSM altlık
    (_goreli(yollar.KOD / "saha" / "araclar"), False),                     # OneMap çekme betiği (yönetici ekranı gösterir)
]


def kopyala(kaynak: Path, hedef: Path, liste: list) -> None:
    hedef.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(kaynak, hedef)
    liste.append({"yol": hedef.as_posix(), "bayt": kaynak.stat().st_size})


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--hedef", required=True, help="Dondurulmuş sunucunun _internal klasörü")
    p.add_argument("--pwa", default=None, help="Telefon uygulamasının derlenmiş hâli (varsayılan kod/arayuz/dist)")
    a = p.parse_args(argv)
    hedef = Path(a.hedef).resolve()
    if not hedef.is_dir():
        print(f"Hedef klasör yok (önce PyInstaller): {hedef}")
        return 1

    eksik: list[str] = []
    liste: list[dict] = []
    for goreli, zorunlu in DOSYALAR:
        k = REPO / goreli
        if k.exists():
            kopyala(k, hedef / goreli, liste)
        elif zorunlu:
            eksik.append(goreli)
        else:
            print(f"  (atlandı, yok) {goreli}")
    for goreli, zorunlu in KLASORLER:
        k = REPO / goreli
        if not k.is_dir():
            if zorunlu:
                eksik.append(goreli + "/")
            continue
        for dosya in sorted(k.rglob("*")):
            if dosya.is_file() and "__pycache__" not in dosya.parts:
                kopyala(dosya, hedef / goreli / dosya.relative_to(k), liste)

    pwa = Path(a.pwa).resolve() if a.pwa else yollar.ARAYUZ_DIST
    if not (pwa / "index.html").exists():
        eksik.append(f"{pwa} (index.html) — telefon uygulaması derlenmemiş")
    else:
        pwa_hedef = hedef / _goreli(yollar.ARAYUZ_DIST)
        if pwa_hedef.exists():
            shutil.rmtree(pwa_hedef)
        for dosya in sorted(pwa.rglob("*")):
            if dosya.is_file():
                kopyala(dosya, pwa_hedef / dosya.relative_to(pwa), liste)

    if eksik:
        print("EKSİK ZORUNLU KAYNAK:")
        for e in eksik:
            print("   -", e)
        return 2

    toplam = sum(x["bayt"] for x in liste)
    kok = hedef.as_posix() + "/"
    for x in liste:
        x["yol"] = x["yol"].removeprefix(kok)
    (hedef / "masaustu_kaynaklar.json").write_text(json.dumps(
        {"zaman": dt.datetime.now().isoformat(timespec="seconds"), "dosya": len(liste), "bayt": toplam,
         "dosyalar": liste}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Kaynaklar kopyalandı: {len(liste)} dosya, {toplam / 1024 / 1024:.1f} MB → {hedef}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
