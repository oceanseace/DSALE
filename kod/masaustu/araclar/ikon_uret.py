"""Simgeler: kod/arayuz/public/ikon/ikon-512.png → kod/masaustu/build/{icon.ico, icon.png, tepsi*.png}.

Telefon uygulamasıyla AYNI simge (mavi zemin, sarı S): kullanıcı iki yerde iki ayrı marka görmesin.
Tepsi için ayrıca gri "durdu" sürümü üretilir (sunucu kapalıyken simge soluklaşır).

    .venv\\Scripts\\python.exe kod\\masaustu\\araclar\\ikon_uret.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageEnhance, ImageOps

if __package__ in (None, ""):  # doğrudan çalıştırıldı: kod/ içe aktarma yoluna (yollar)
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import yollar  # noqa: E402

MASAUSTU = yollar.KOD / "masaustu"
KAYNAK = yollar.ARAYUZ / "public" / "ikon" / "ikon-512.png"
HEDEF = MASAUSTU / "build"
BOYUTLAR = [16, 20, 24, 32, 40, 48, 64, 128, 256]


def main() -> int:
    if not KAYNAK.exists():
        print(f"Simge kaynağı yok: {KAYNAK}")
        return 1
    HEDEF.mkdir(parents=True, exist_ok=True)
    ana = Image.open(KAYNAK).convert("RGBA")
    ana.save(HEDEF / "icon.png")
    ana.save(HEDEF / "icon.ico", sizes=[(b, b) for b in BOYUTLAR])

    # Tepsi: 16/32 px (Windows ölçeklemesi için ikisi de), çalışıyor + durdu.
    gri = ImageOps.grayscale(ana.convert("RGB")).convert("RGBA")
    gri.putalpha(ana.getchannel("A"))
    gri = ImageEnhance.Brightness(gri).enhance(1.25)
    for ad, resim in (("tepsi", ana), ("tepsi-durdu", gri)):
        resim.resize((32, 32), Image.LANCZOS).save(HEDEF / f"{ad}.png")
        resim.resize((16, 16), Image.LANCZOS).save(HEDEF / f"{ad}-16.png")
        resim.save(HEDEF / f"{ad}.ico", sizes=[(16, 16), (20, 20), (24, 24), (32, 32), (48, 48)])
    print(f"Simgeler hazır: {HEDEF}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
