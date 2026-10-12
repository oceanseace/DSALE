"""Turkcell.exe'yi derler (PyInstaller, tek klasör) ve depo köküne koyar. .bat yok:

    .venv\\Scripts\\python.exe kod\\masaustu\\derle.py            # derle + köke kopyala
    .venv\\Scripts\\python.exe kod\\masaustu\\derle.py --kopyalama  # yalnız derle (kod/masaustu/derleme/dist)

Çıktı (depo kökü):
    Turkcell.exe      pencereli (konsolsuz) uygulama; simge kod/marka/turkcell-kaynak.png'den
    .turkcell/        gizli: Python çalışma zamanı + salt okunur kaynaklar (kod/arayuz/dist, veri/ref, bina tablosu …)
Veri ASLA burada değil: çalışma klasörü ``veri/canli`` (kod/yollar.py). Ara dosyalar ``kod/masaustu/derleme/`` (git dışı).

Arayüz (kod/arayuz/dist) önceden derlenmiş olmalı; bu betik onu derlemez, olduğu gibi paketler.
Kaynak dosyalar zamanları korunarak (copy2) kopyalanır: veri kalitesi önbelleğinin imzası boyut+zamana bakar.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import yollar  # noqa: E402

MASAUSTU = yollar.KOD / "masaustu"
DERLEME = MASAUSTU / "derleme"
AD = "Turkcell"
ICERIK = ".turkcell"                                   # --contents-directory

# Python paketleri: dinamik içe aktarılanlar dahil hepsi; testler, analiz betikleri ve araçlar dışarıda.
PAKETLER = ("saha", "operasyon", "dsale")
HARIC_KLASOR = {"testler", "tests", "analiz", "araclar", "__pycache__", "node_modules"}
DIS_MODUL = ["tkinter", "_tkinter", "matplotlib", "IPython", "pytest", "_pytest", "PyInstaller", "pip",
             "watchfiles", "httpx", "httpcore", "saha.testler", "operasyon.testler", "lisans.testler",
             "pystray._gtk", "pystray._appindicator", "pystray._xorg", "pystray._darwin", "gi",
             "webview.platforms.gtk", "webview.platforms.qt", "webview.platforms.cocoa", "webview.platforms.android"]

# Sunucunun çalışma anında okuduğu salt okunur kaynaklar (depo düzeniyle; yollar.KOK = .turkcell). (yol, zorunlu)
DOSYALAR = [
    (yollar.VERI / "master" / "bina_master.csv", True),
    (yollar.VERI / "master" / "bina_geometri.json", False),
    (yollar.VERI / "master" / "veri_kalitesi.json", False),
    (yollar.VERI / "master" / "bina_kalite_kanit.json", False),   # önbellek: yoksa ilk açılışta hesaplanır
    (yollar.VERI / "raw" / "onemap_bina_bursa.json", False),      # veri kalitesi kanıtları
    (yollar.CIKTI / "N08_res_hp" / "atama.csv", True),            # ilk kurulumda 8 bölge
    (yollar.SUNUM_URETILEN / "binalar.json", False),              # bölge planlayıcı: hazır planlar
    (yollar.SUNUM_URETILEN / "planlar.json", False),
    (yollar.KOD / "operasyon" / "obekler.ornek.json", False),
    (yollar.KOD / "lisans" / "genel_anahtar.pem", False),
]
KLASORLER = [
    (yollar.VERI / "ref", False),                                 # ilçe/mahalle sözlüğü, OSM altlık
    (yollar.KOD / "saha" / "araclar", False),                     # OneMap çekme betiği (yönetici ekranı gösterir)
    (yollar.ARAYUZ_DIST, True),                                   # uygulama arayüzü (PWA)
]


def surum() -> str:
    m = re.search(r'^SURUM\s*=\s*["\']([^"\']+)', (yollar.KOD / "saha" / "__init__.py").read_text(encoding="utf-8"),
                  re.M)
    return m.group(1) if m else "1.0.0"


def gizli_moduller() -> list[str]:
    adlar = ["yollar", "masaustu", "masaustu.devir", "pystray._win32", "webview.platforms.winforms",
             "webview.platforms.edgechromium", "python_multipart", "multipart", "openpyxl", "itsdangerous",
             "shapely", "scipy.spatial", "scipy.sparse.csgraph", "httptools", "email.mime.multipart"]
    for paket in PAKETLER:
        kok = yollar.KOD / paket
        for py in sorted(kok.rglob("*.py")):
            goreli = py.relative_to(yollar.KOD)
            if HARIC_KLASOR.intersection(goreli.parts[:-1]) or py.name.startswith("test_"):
                continue
            parca = list(goreli.with_suffix("").parts)
            if parca[-1] == "__init__":
                parca.pop()
            adlar.append(".".join(parca))
    return adlar


def surum_dosyasi(s: str) -> Path:
    p = tuple(int(x) if x.isdigit() else 0 for x in (s.split(".") + ["0"] * 4)[:4])
    metin = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={p}, prodvers={p}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0),
  kids=[
    StringFileInfo([StringTable('041F04B0', [
      StringStruct('CompanyName', 'TURKCELL SUPERONLINE DEHANET EÇM'),
      StringStruct('FileDescription', 'Turkcell'),
      StringStruct('FileVersion', '{s}'),
      StringStruct('InternalName', 'Turkcell'),
      StringStruct('OriginalFilename', 'Turkcell.exe'),
      StringStruct('ProductName', 'Turkcell'),
      StringStruct('ProductVersion', '{s}'),
      StringStruct('LegalCopyright', '© 2026 TURKCELL SUPERONLINE DEHANET EÇM')])]),
    VarFileInfo([VarStruct('Translation', [0x041F, 1200])])
  ]
)"""
    yol = DERLEME / "surum.txt"
    yol.write_text(metin, encoding="utf-8")
    return yol


def kaynaklari_kopyala(icerik: Path) -> tuple[int, int]:
    eksik, sayi, bayt = [], 0, 0

    def kopya(k: Path, h: Path) -> None:
        nonlocal sayi, bayt
        h.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(k, h)
        sayi += 1
        bayt += k.stat().st_size

    for yol, zorunlu in DOSYALAR:
        if yol.is_file():
            kopya(yol, icerik / yol.relative_to(yollar.KOK))
        elif zorunlu:
            eksik.append(yol)
    for kok, zorunlu in KLASORLER:
        if not kok.is_dir():
            if zorunlu:
                eksik.append(kok)
            continue
        hedef = icerik / kok.relative_to(yollar.KOK)
        for d in sorted(kok.rglob("*")):
            if d.is_file() and "__pycache__" not in d.parts:
                kopya(d, hedef / d.relative_to(kok))
    for ad in ("turkcell.ico", "logo.png"):
        kopya(MASAUSTU / "kaynak" / ad, icerik / "masaustu" / ad)
    if not (yollar.ARAYUZ_DIST / "index.html").is_file():
        eksik.append(yollar.ARAYUZ_DIST / "index.html")
    if eksik:
        raise SystemExit("EKSİK ZORUNLU KAYNAK:\n" + "\n".join(f"  - {e}" for e in eksik))
    return sayi, bayt


def gizle(yol: Path) -> None:
    ctypes.windll.kernel32.SetFileAttributesW(str(yol), 0x2)     # FILE_ATTRIBUTE_HIDDEN (attrib +h)


def koke_kopyala(dist: Path) -> None:
    kok = yollar.DEPO
    exe, icerik = kok / f"{AD}.exe", kok / ICERIK
    acik = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {AD}.exe", "/NH"], capture_output=True, text=True,
                          errors="replace").stdout
    if f"{AD}.exe" in acik:
        raise SystemExit(f"{AD}.exe açık. Kapatın (bildirim alanı simgesi → Çıkış) ve yeniden derleyin.")
    if icerik.exists():
        if not (icerik / "turkcell_derleme.json").is_file():             # yalnız kendi önceki derlememizi sileriz
            raise SystemExit(f"{icerik} bu derlemenin çıktısı değil (turkcell_derleme.json yok); elle bakın.")
        shutil.rmtree(icerik)
    shutil.copytree(dist / ICERIK, icerik, copy_function=shutil.copy2)
    shutil.copy2(dist / f"{AD}.exe", exe)
    gizle(icerik)
    print(f"  Köke kopyalandı: {exe}  (+ gizli {ICERIK}\\)")


def main(argv: list[str] | None = None) -> int:
    a = argparse.ArgumentParser(description="Turkcell.exe derlemesi")
    a.add_argument("--kopyalama", action="store_true", help="depo köküne kopyalama (yalnız derle)")
    ayar = a.parse_args(argv)
    t0 = time.perf_counter()
    DERLEME.mkdir(parents=True, exist_ok=True)

    from masaustu import ikon
    ico, _ = ikon.uret()
    s = surum()
    print(f"[1/3] PyInstaller · {AD} {s}")
    arg = [
        str(MASAUSTU / "turkcell.py"), "--name", AD, "--onedir", "--windowed", "--noconfirm", "--clean",
        "--contents-directory", ICERIK, "--icon", str(ico), "--version-file", str(surum_dosyasi(s)),
        "--distpath", str(DERLEME / "dist"), "--workpath", str(DERLEME / "is"), "--specpath", str(DERLEME),
        "--paths", str(yollar.KOD), "--log-level", "WARN", "--collect-submodules", "uvicorn",
    ]
    for m in gizli_moduller():
        arg += ["--hidden-import", m]
    for m in DIS_MODUL:
        arg += ["--exclude-module", m]
    import PyInstaller.__main__
    PyInstaller.__main__.run(arg)
    dist = DERLEME / "dist" / AD

    print("[2/3] Kaynaklar")
    sayi, bayt = kaynaklari_kopyala(dist / ICERIK)
    print(f"  {sayi} dosya, {bayt / 1048576:.1f} MB")
    (dist / ICERIK / "turkcell_derleme.json").write_text(json.dumps(
        {"surum": s, "zaman": time.strftime("%Y-%m-%dT%H:%M:%S"), "kaynak_dosya": sayi}, ensure_ascii=False),
        encoding="utf-8")

    if ayar.kopyalama:
        print(f"[3/3] Köke kopyalama atlandı: {dist}")
    else:
        print("[3/3] Depo kökü")
        koke_kopyala(dist)
    toplam = sum(f.stat().st_size for f in dist.rglob("*") if f.is_file())
    print(f"TAMAM · {toplam / 1048576:.0f} MB · {time.perf_counter() - t0:.0f} sn")
    return 0


if __name__ == "__main__":
    sys.exit(main())
