# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller: Saha sunucusu → kod/masaustu/build/sunucu/SahaSunucu.exe (tek klasör).

    .venv\\Scripts\\python.exe -m PyInstaller kod\\masaustu\\sunucu.spec --noconfirm ^
        --distpath kod\\masaustu\\build --workpath kod\\masaustu\\build\\pyi-is

Kod repo'dan OKUNUR (kod/ altındaki yollar.py, saha/, operasyon/, dsale/ değiştirilmez). Dinamik içe aktarılan modüller
(``operasyon.v2.api``, ``dsale.partition`` ...) ``collect_submodules`` ile eklenir; testler ve
analiz betikleri dışarıda kalır. Veri dosyalarını ``araclar/kaynak_topla.py`` ayrıca kopyalar.
"""
import json
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.utils.win32 import versioninfo as vi

MASAUSTU = Path(SPECPATH)
KOD = MASAUSTU.parent                     # kod/: yollar.py ve Python paketleri burada
if str(KOD) not in sys.path:
    sys.path.insert(0, str(KOD))

SURUM = json.loads((MASAUSTU / "package.json").read_text(encoding="utf-8"))["version"]
HARIC_PARCA = (".testler", ".analiz", ".tests", ".test_")


def bizim(paket):
    return collect_submodules(paket, filter=lambda ad: not any(h in ad for h in HARIC_PARCA))


gizli = ["yollar"] + bizim("saha") + bizim("operasyon") + bizim("dsale")
gizli += collect_submodules("uvicorn")
gizli += ["python_multipart", "multipart", "openpyxl", "itsdangerous", "shapely", "scipy.spatial",
          "scipy.sparse.csgraph", "httptools", "email.mime.multipart"]

a = Analysis(
    [str(MASAUSTU / "sunucu_giris.py")],
    pathex=[str(KOD)],
    binaries=[],
    datas=[],
    hiddenimports=gizli,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "_tkinter", "matplotlib", "IPython", "pytest", "_pytest", "PyInstaller", "pip",
              "watchfiles", "saha.testler", "operasyon.testler", "operasyon.analiz", "httpx", "httpcore"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

parca = tuple(int(x) for x in (SURUM.split(".") + ["0", "0", "0"])[:4])
surum_bilgisi = vi.VSVersionInfo(
    ffi=vi.FixedFileInfo(filevers=parca, prodvers=parca),
    kids=[
        vi.StringFileInfo([vi.StringTable("041F04B0", [
            vi.StringStruct("CompanyName", "Dehanet EÇM"),
            vi.StringStruct("FileDescription", "Dehanet Saha Sunucusu"),
            vi.StringStruct("FileVersion", SURUM),
            vi.StringStruct("InternalName", "SahaSunucu"),
            vi.StringStruct("OriginalFilename", "SahaSunucu.exe"),
            vi.StringStruct("ProductName", "Dehanet Saha"),
            vi.StringStruct("ProductVersion", SURUM),
            vi.StringStruct("LegalCopyright", "© 2026 TURKCELL SUPERONLINE DEHANET EÇM"),
        ])]),
        vi.VarFileInfo([vi.VarStruct("Translation", [0x041F, 1200])]),
    ],
)

ikon = MASAUSTU / "build" / "icon.ico"
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SahaSunucu",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,                 # kabuk gizli pencereyle başlatır; elle de komut satırından kullanılabilir
    disable_windowed_traceback=False,
    icon=str(ikon) if ikon.exists() else None,
    version=surum_bilgisi,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="sunucu",
)
