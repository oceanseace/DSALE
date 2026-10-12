"""Turkcell logosundan masaüstü simgeleri üretir (derle.py çağırır; elle de çalışır).

    .venv\\Scripts\\python.exe kod\\masaustu\\ikon.py

Kaynak: ``kod/marka/turkcell-kaynak.png`` (841x595, şeffaf zemin). Çıktılar ``kod/masaustu/kaynak/`` altına:
    turkcell.ico   çok boyutlu (16-256), kareye ortalanmış, şeffaf — exe, pencere ve bildirim alanı simgesi
    logo.png       açılış ekranındaki logo (en çok 320 px genişlik)
Çıktılar depoda tutulur: kabuk geliştirmede de (derlemeden) aynı simgeleri kullanır.
"""
from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import yollar  # noqa: E402

KAYNAK = yollar.KOD / "marka" / "turkcell-kaynak.png"
HEDEF = yollar.KOD / "masaustu" / "kaynak"
BOYUTLAR = [16, 20, 24, 32, 40, 48, 64, 96, 128, 256]


def uret(kaynak: Path = KAYNAK, hedef: Path = HEDEF) -> tuple[Path, Path]:
    from PIL import Image

    hedef.mkdir(parents=True, exist_ok=True)
    logo = Image.open(kaynak).convert("RGBA")
    logo = logo.crop(logo.getbbox() or (0, 0, *logo.size))       # şeffaf kenarları at
    kenar = max(logo.size)
    kare = Image.new("RGBA", (kenar, kenar), (0, 0, 0, 0))
    kare.paste(logo, ((kenar - logo.width) // 2, (kenar - logo.height) // 2), logo)
    buyuk = kare.resize((256, 256), Image.LANCZOS)
    ico = hedef / "turkcell.ico"
    buyuk.save(ico, format="ICO", sizes=[(b, b) for b in BOYUTLAR])

    genislik = min(320, logo.width)
    acilis = logo.resize((genislik, round(logo.height * genislik / logo.width)), Image.LANCZOS)
    png = hedef / "logo.png"
    acilis.save(png, optimize=True)
    return ico, png


if __name__ == "__main__":
    for yol in uret():
        print(f"{yol}  {yol.stat().st_size:,} bayt")
