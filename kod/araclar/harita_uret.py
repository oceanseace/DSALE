"""Kod haritasını koddan günceller: ``kod/HARITA.md`` (çapalar + OTOMATIK bölüm) ve ``kod/HARITA_UCLAR.md``.

    .venv\\Scripts\\python.exe kod\\araclar\\harita_uret.py             # güncelle
    .venv\\Scripts\\python.exe kod\\araclar\\harita_uret.py --denetle   # eskimişse çıkış kodu 1 (değiştirmez)

Üretilenler: uç → dosya:satır fonksiyon → izin (``saha.api.uygulama`` + ``yetki.ROTA_IZNI``; sunucu geçici, boş bir
veri klasörüyle İÇE AKTARILIR, başlatılmaz) · menü bölümü → ekran dosyası (``menu.ts`` + ``Konsol.tsx``) · eklenti mesaj
türleri → işleyen fonksiyon · HARITA.md'deki `` `kod/yol:satır sembol` `` çapalarının satır numaraları.
"""
from __future__ import annotations

import argparse
import inspect
import logging
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

KOK = Path(__file__).resolve().parents[2]
KOD = KOK / "kod"
HARITA = KOD / "HARITA.md"
UCLAR = KOD / "HARITA_UCLAR.md"
SRC = KOD / "arayuz" / "src"
EKLENTI = KOD / "eklenti"
BASLA, BITIR = "<!-- OTOMATIK:BASLA -->", "<!-- OTOMATIK:BITIR -->"
CAPA = re.compile(r"`(kod/[^`\s:]+):(\d+) ([^`]+)`")


def _oku(yol: Path) -> str:
    return yol.read_text(encoding="utf8")


def _goreli(yol: str | Path) -> str:
    return Path(yol).resolve().relative_to(KOK).as_posix()


# ----------------------------------------------------------------------------- çapalar
def sembol_satiri(yol: Path, sembol: str) -> int | None:
    """Sembolün tanımlandığı satır (1'den). Tanımlayıcıysa tanımı, değilse metnin ilk geçtiği satırı arar."""
    satirlar = _oku(yol).splitlines()
    if re.fullmatch(r"[A-Za-z_$][\w$]*", sembol):
        s = re.escape(sembol)
        tanim = re.compile(rf"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?(?:def|class|function|const|let|var|interface|type|enum)"
                           rf"\s+{s}\b|^\s*{s}\s*(?::[^=]*)?=[^=]|^\s*(?:async\s+)?function\s+{s}\b")
        for i, l in enumerate(satirlar, 1):
            if tanim.search(l):
                return i
        for i, l in enumerate(satirlar, 1):                       # yedek: sözcüğün ilk geçtiği yer
            if re.search(rf"\b{s}\b", l):
                return i
        return None
    for i, l in enumerate(satirlar, 1):
        if sembol in l:
            return i
    return None


def capalari_guncelle(metin: str, hatalar: list[str]) -> str:
    def degistir(m: re.Match) -> str:
        yol, sembol = m.group(1), m.group(3)
        dosya = KOK / yol
        if not dosya.is_file():
            hatalar.append(f"çapa dosyası yok: {yol}")
            return m.group(0)
        satir = sembol_satiri(dosya, sembol)
        if satir is None:
            hatalar.append(f"çapa sembolü bulunamadı: {yol} → {sembol}")
            return m.group(0)
        return f"`{yol}:{satir} {sembol}`"
    return CAPA.sub(degistir, metin)


# ----------------------------------------------------------------------------- uçlar
def _gecici_ortam() -> Path:
    """Sunucu modülleri içe aktarılırken hiçbir gerçek veri klasörüne dokunulmasın."""
    gecici = Path(tempfile.mkdtemp(prefix="harita-"))
    for ad, deger in {"SAHA_VERI_DIZINI": gecici, "SAHA_DB": gecici / "saha.db", "SAHA_GELEN": gecici / "gelen",
                      "SAHA_CIKTI": gecici / "cikti", "SAHA_EK": gecici / "ek", "OPERASYON_VERI": gecici / "op",
                      "OPERASYON_OBEK": gecici / "obekler.json"}.items():
        os.environ[ad] = str(deger)
    return gecici


def uclari_topla() -> list[dict]:
    if str(KOD) not in sys.path:
        sys.path.insert(0, str(KOD))
    logging.disable(logging.CRITICAL)
    from fastapi.routing import APIRoute

    from saha import api, yetki

    if api.V2_YUKLEME_HATASI:
        raise SystemExit(f"Uç modülü yüklenemedi: {api.V2_YUKLEME_HATASI}")

    def gez(liste):
        for r in liste:
            if isinstance(r, APIRoute):
                yield r
            alt = getattr(r, "original_router", None)
            if alt is not None:
                yield from gez(alt.routes)

    uclar = []
    for r in gez(api.uygulama.routes):
        f = inspect.unwrap(r.endpoint)
        dosya = _goreli(inspect.getsourcefile(f))
        satir = inspect.getsourcelines(f)[1]
        for yontem in sorted(r.methods - {"HEAD", "OPTIONS"}):
            anahtar = (yontem, r.path)
            if anahtar not in yetki.ROTA_IZNI:
                izin = "TABLODA YOK"
            else:
                d = yetki.ROTA_IZNI[anahtar]
                izin = "herkese açık" if d is None else (d if isinstance(d, str) else " · ".join(d))
            uclar.append({"yontem": yontem, "yol": r.path, "dosya": dosya, "satir": satir, "fonk": f.__name__,
                          "izin": izin, "modul": f.__module__})
    uclar.sort(key=lambda u: (u["yol"], u["yontem"]))
    return uclar


def uclar_md(uclar: list[dict]) -> str:
    satirlar = ["# Uçlar — otomatik", "",
                "Bu dosyayı `kod/araclar/harita_uret.py` üretir; elle düzenleme. Giriş: [`HARITA.md`](HARITA.md).",
                "İzin = `yetki.ROTA_IZNI` (eylemlerden biri yeter; tanımlar `kod/saha/yetki.py` IZINLER).", "",
                "| Yöntem | Yol | İşleyen | İzin |", "|---|---|---|---|"]
    for u in uclar:
        satirlar.append(f"| {u['yontem']} | `{u['yol']}` | `{u['dosya']}:{u['satir']}` {u['fonk']} | {u['izin']} |")
    return "\n".join(satirlar) + "\n"


# ----------------------------------------------------------------------------- menü
def _ts_coz(baz: Path, spec: str) -> Path | None:
    t = (baz / spec).resolve()
    for aday in (t, t.with_name(t.name + ".tsx"), t.with_name(t.name + ".ts"), t / "index.ts", t / "index.tsx"):
        if aday.is_file():
            return aday
    return None


def _bileseni_bul(dosya: Path, ad: str, derinlik: int = 0) -> tuple[Path, int] | None:
    """`ad`'ın tanımlandığı dosya ve satır; index.ts yeniden dışa aktarımlarını izler."""
    metin = _oku(dosya)
    for m in re.finditer(r"export\s*\{([^}]*)\}\s*from\s*'([^']+)'", metin):
        if derinlik < 3 and re.search(rf"\b{ad}\b", m.group(1)):
            hedef = _ts_coz(dosya.parent, m.group(2))
            if hedef:
                return _bileseni_bul(hedef, ad, derinlik + 1)
    satir = sembol_satiri(dosya, ad)
    return (dosya, satir) if satir else None


def menu_topla() -> list[dict]:
    menu = _oku(SRC / "cekirdek" / "konsol" / "menu.ts")
    konsol = _oku(SRC / "Konsol.tsx")
    ice = {}
    for m in re.finditer(r"import\s*\{([^}]*)\}\s*from\s*'(\./[^']+)'", konsol):
        for ad in re.findall(r"\b(\w+)\b", m.group(1)):
            ice[ad] = (m.group(2), ad)
    for m in re.finditer(r"const (\w+) = lazy\(\(\) => import\('([^']+)'\)\.then\(\(m\) => \(\{ default: m\.(\w+) \}\)\)\)", konsol):
        ice[m.group(1)] = (m.group(2), m.group(3))
    govde = konsol[konsol.index("function Bolumu"):]
    ekran, bekleyen = {}, []
    for m in re.finditer(r"case '([\w-]+)':|default:|return <(\w+)", govde):
        if m.group(1):
            bekleyen.append(m.group(1))
        elif m.group(2):
            for b in bekleyen:
                ekran.setdefault(b, m.group(2))
            bekleyen = []
    oge = re.compile(r"\{\s*birim:\s*'(\w+)',\s*bolum:\s*'([\w-]+)',\s*etiket:\s*'([^']+)'.*?izin:\s*\[([^\]]*)\](.*?)\}")
    liste = []
    for m in oge.finditer(menu):
        bolum = m.group(2)
        bilesen = ekran.get(bolum)
        yer = "?"
        if bilesen and bilesen in ice:
            spec, ad = ice[bilesen]
            dosya = _ts_coz(SRC, spec)
            bulunan = _bileseni_bul(dosya, ad) if dosya else None
            if bulunan:
                yer = f"`{_goreli(bulunan[0])}:{bulunan[1]}` {ad}"
        liste.append({"birim": m.group(1), "bolum": bolum, "etiket": m.group(3), "yer": yer,
                      "izin": ", ".join(re.findall(r"'([^']+)'", m.group(4))),
                      "gizli": "gizli: true" in m.group(5)})
    return liste


# ----------------------------------------------------------------------------- eklenti mesajları
def mesajlari_topla() -> list[dict]:
    gonderen: dict[str, set[str]] = {}
    isleyen: dict[str, list[str]] = {}
    for dosya in ("kanca.js", "kopru.js", "arka.js", "panel.js"):
        satirlar = _oku(EKLENTI / dosya).splitlines()
        for i, l in enumerate(satirlar, 1):
            for m in re.finditer(r"\btur:\s*'([\w-]+)'", l):
                gonderen.setdefault(m.group(1), set()).add(dosya)
            for m in re.finditer(r"\b\w+\.tur === '([\w-]+)'(?:\s*&&[^)]*)?\)\s*(\{)?\s*(?:([\w.]+)\()?", l):
                isim = m.group(3)
                if not isim and m.group(2):                       # blok: sonraki satırdaki ilk çağrı
                    sonraki = satirlar[i] if i < len(satirlar) else ""
                    c = re.search(r"([\w.]+)\(", sonraki)
                    isim = c.group(1) if c else None
                if isim in (None, "if", "return"):
                    isim = "satır içi"
                isleyen.setdefault(m.group(1), []).append(f"`kod/eklenti/{dosya}:{i}` {isim}")
    turler = sorted(set(gonderen) | set(isleyen))
    return [{"tur": t, "gonderen": ", ".join(sorted(gonderen.get(t, []))) or "—",
             "isleyen": " · ".join(isleyen.get(t, [])) or "—"} for t in turler]


# ----------------------------------------------------------------------------- birleştirme
def otomatik_bolum(uclar: list[dict], menu: list[dict], mesajlar: list[dict]) -> str:
    s = [BASLA, "## 6. Otomatik (harita_uret.py üretir — elle düzenleme)", "",
         "### Menü bölümü → ekran", "", "| Birim | Bölüm (#/yonetici/…) | Etiket | Ekran | İzin |", "|---|---|---|---|---|"]
    for m in menu:
        etiket = m["etiket"] + (" (gizli)" if m["gizli"] else "")
        s.append(f"| {m['birim']} | `{m['bolum']}` | {etiket} | {m['yer']} | {m['izin']} |")
    s += ["", "### Eklenti mesajları (kanca ↔ kopru ↔ arka ↔ panel)", "", "| Tür | Gönderen | İşleyen |", "|---|---|---|"]
    for m in mesajlar:
        s.append(f"| `{m['tur']}` | {m['gonderen']} | {m['isleyen']} |")
    moduller: dict[str, list[dict]] = {}
    for u in uclar:
        moduller.setdefault(u["dosya"], []).append(u)
    eksik = [u for u in uclar if u["izin"] == "TABLODA YOK"]
    s += ["", f"### Uçlar: {len(uclar)} (tam liste [`HARITA_UCLAR.md`](HARITA_UCLAR.md))", "",
          "| Dosya | Uç | Yol önekleri |", "|---|---|---|"]
    for dosya, liste in sorted(moduller.items(), key=lambda x: -len(x[1])):
        onekler = sorted({"/".join(u["yol"].split("/")[:3]) for u in liste})
        s.append(f"| `{dosya}` | {len(liste)} | {' '.join(onekler[:8])}{' …' if len(onekler) > 8 else ''} |")
    if eksik:
        s.append(f"\n**İzin tablosunda olmayan {len(eksik)} uç var** (test_yetki_matrisi kırılır).")
    s.append(BITIR)
    return "\n".join(s)


def uret() -> tuple[str, str, list[str]]:
    hatalar: list[str] = []
    gecici = _gecici_ortam()
    try:
        uclar = uclari_topla()
    finally:
        shutil.rmtree(gecici, ignore_errors=True)
    harita = _oku(HARITA)
    if BASLA not in harita or BITIR not in harita:
        raise SystemExit(f"{HARITA} içinde {BASLA} … {BITIR} işaretleri yok.")
    once, kalan = harita.split(BASLA, 1)
    _, sonra = kalan.split(BITIR, 1)
    once = capalari_guncelle(once, hatalar)
    yeni = once + otomatik_bolum(uclar, menu_topla(), mesajlari_topla()) + sonra
    return yeni, uclar_md(uclar), hatalar


def main(argv: list[str] | None = None) -> int:
    for akis in (sys.stdout, sys.stderr):
        try:
            akis.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ayrac = argparse.ArgumentParser(description="Kod haritasını (kod/HARITA.md) koddan günceller.")
    ayrac.add_argument("--denetle", action="store_true", help="yazma; harita eskimişse çıkış kodu 1")
    a = ayrac.parse_args(argv)
    harita, uclar, hatalar = uret()
    for h in hatalar:
        print("HATA:", h)
    eski = {HARITA: _oku(HARITA), UCLAR: _oku(UCLAR) if UCLAR.exists() else ""}
    yeni = {HARITA: harita, UCLAR: uclar}
    farkli = [p for p in yeni if eski[p] != yeni[p]]
    if a.denetle:
        for p in farkli:
            print(f"ESKİMİŞ: {_goreli(p)} — güncellemek için: python kod/araclar/harita_uret.py")
        return 1 if (farkli or hatalar) else 0
    for p in farkli:
        p.write_text(yeni[p], encoding="utf8", newline="\n")
        print("güncellendi:", _goreli(p))
    satir = harita.count("\n") + 1
    print(f"HARITA.md {satir} satır" + (" (250'yi aşıyor!)" if satir > 250 else ""))
    return 1 if hatalar else 0


if __name__ == "__main__":
    sys.exit(main())
