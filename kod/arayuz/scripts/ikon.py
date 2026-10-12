# Turkcell PWA / tarayici simgeleri.
# Kaynak: kod/marka/turkcell-kaynak.png (seffaf zeminde sari isaret).
# Cikti (public/ikon): isaret.png (kirpilmis, seffaf; Marka bileseni ve
# acilis ekrani), favicon-32.png, favicon.ico, apple-touch-icon.png,
# ikon-192.png, ikon-512.png, ikon-maskable-512.png.
# Simge zemini koyu lacivert (sari isaret onun ustunde 9:1'den yuksek okunur).

import os, sys
from PIL import Image, ImageDraw

if __package__ in (None, ""):  # dogrudan calistirildi: kod/ ice aktarma yoluna (yollar)
    sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")))
import yollar  # noqa: E402

KAYNAK = str(yollar.KOD / "marka" / "turkcell-kaynak.png")
CIKIS = str(yollar.ARAYUZ / "public" / "ikon")
os.makedirs(CIKIS, exist_ok=True)

ZEMIN = (16, 28, 48, 255)  # koyu lacivert


def isaret():
    g = Image.open(KAYNAK).convert("RGBA")
    return g.crop(g.getchannel("A").getbbox())


ISARET = isaret()


def yerlestir(tuval, oran):
    """Isareti tuvalin ortasina, kisa kenarin `oran`i kadar sigdir."""
    b = tuval.size[0]
    hedef = int(b * oran)
    w, h = ISARET.size
    k = hedef / max(w, h)
    kucuk = ISARET.resize((max(1, round(w * k)), max(1, round(h * k))), Image.LANCZOS)
    tuval.alpha_composite(kucuk, ((b - kucuk.size[0]) // 2, (b - kucuk.size[1]) // 2))
    return tuval


def kare(boyut, yaricap_orani=0.0, oran=0.62):
    t = Image.new("RGBA", (boyut, boyut), (0, 0, 0, 0))
    c = ImageDraw.Draw(t)
    if yaricap_orani:
        c.rounded_rectangle([0, 0, boyut - 1, boyut - 1], radius=int(boyut * yaricap_orani), fill=ZEMIN)
    else:
        c.rectangle([0, 0, boyut, boyut], fill=ZEMIN)
    return yerlestir(t, oran)


# Seffaf isaret (arayuzde <img>): 256 px yeter, 2x ekranlarda 128 px'e kadar keskin.
yerlestir(Image.new("RGBA", (256, 256), (0, 0, 0, 0)), 1.0).save(os.path.join(CIKIS, "isaret.png"), optimize=True)

for boyut in (192, 512):
    kare(boyut, 0.225).save(os.path.join(CIKIS, "ikon-%d.png" % boyut), optimize=True)
# Maskable: tum kare dolu; isaret %80 guvenli dairenin icinde (cap %56).
kare(512, 0, 0.56).save(os.path.join(CIKIS, "ikon-maskable-512.png"), optimize=True)
# iOS koseleri kendi yuvarlar -> dolu kare, saydamlik yok.
kare(180, 0, 0.62).convert("RGB").save(os.path.join(CIKIS, "apple-touch-icon.png"), optimize=True)
# Sekme simgesi: kucuk boyutta zemin yok, isaret dolu gorunsun.
fav = yerlestir(Image.new("RGBA", (64, 64), (0, 0, 0, 0)), 0.96)
fav.resize((32, 32), Image.LANCZOS).save(os.path.join(CIKIS, "favicon-32.png"), optimize=True)
fav.save(os.path.join(CIKIS, "favicon.ico"), sizes=[(16, 16), (32, 32), (48, 48)])

print("ikonlar yazildi:", sorted(os.listdir(CIKIS)))
