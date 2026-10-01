# Saha Sistemi PWA simgeleri.
# Ana ekrana eklendiginde gorunen ikon: lacivert kare, sari "S".
# Dis kaynak yok; Pillow ile cizilir.

import io, os, sys
from PIL import Image, ImageDraw, ImageFont

if __package__ in (None, ""):  # dogrudan calistirildi: kod/ ice aktarma yoluna (yollar)
    sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")))
import yollar  # noqa: E402

CIKIS = str(yollar.ARAYUZ / "public" / "ikon")
os.makedirs(CIKIS, exist_ok=True)

MAVI = (11, 99, 229, 255)
SARI = (255, 201, 0, 255)


def yazi_tipi(boyut):
    for ad in ("segoeuib.ttf", "arialbd.ttf", "seguisb.ttf", "calibrib.ttf"):
        yol = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", ad)
        if os.path.exists(yol):
            try:
                return ImageFont.truetype(yol, boyut)
            except Exception:
                pass
    return ImageFont.load_default()


def harf(cizim, kutu, boyut):
    f = yazi_tipi(boyut)
    metin = "S"
    sol, ust, sag, alt = cizim.textbbox((0, 0), metin, font=f)
    g, y = sag - sol, alt - ust
    x = kutu[0] + (kutu[2] - kutu[0] - g) / 2 - sol
    t = kutu[1] + (kutu[3] - kutu[1] - y) / 2 - ust
    cizim.text((x, t), metin, font=f, fill=SARI)


def kare_ikon(boyut, yuvarlak=True, dolgu=0.0):
    # dolgu: maskable ikonlarda kenar bosluğu orani
    g = Image.new("RGBA", (boyut, boyut), (0, 0, 0, 0))
    c = ImageDraw.Draw(g)
    if dolgu > 0:
        # maskable: tum kare lacivert, harf ortada kucuk kalir
        c.rectangle([0, 0, boyut, boyut], fill=MAVI)
        ic = boyut * dolgu
        harf(c, (ic, ic, boyut - ic, boyut - ic), int(boyut * (1 - 2 * dolgu) * 0.72))
    else:
        r = int(boyut * 0.22) if yuvarlak else 0
        c.rounded_rectangle([0, 0, boyut - 1, boyut - 1], radius=r, fill=MAVI)
        harf(c, (0, 0, boyut, boyut), int(boyut * 0.58))
    return g


for boyut in (192, 512):
    kare_ikon(boyut).save(os.path.join(CIKIS, "ikon-%d.png" % boyut))
kare_ikon(512, dolgu=0.18).save(os.path.join(CIKIS, "ikon-maskable-512.png"))
# iOS ana ekran ikonu koseleri kendi yuvarlar -> dolu kare
apple = Image.new("RGBA", (180, 180), MAVI)
harf(ImageDraw.Draw(apple), (0, 0, 180, 180), int(180 * 0.58))
apple.convert("RGB").save(os.path.join(CIKIS, "apple-touch-icon.png"))

print("ikonlar yazildi:", sorted(os.listdir(CIKIS)))
