@echo off
rem ============================================================================
rem  DEHANET SAHA - masaustu uygulamasini bastan derler (tek komut, tekrarlanabilir)
rem
rem  Cikti:
rem    kod\masaustu\dist\DehanetSaha-Kurulum-<surum>.exe   kurulum programi (NSIS)
rem    kod\masaustu\dist\DehanetSaha.exe                   tasinabilir (kurulumsuz)
rem    <repo>\DehanetSaha.exe                          kok dizindeki kopya
rem
rem  Adimlar: 1 simgeler  2 SahaSunucu.exe (PyInstaller)  3 veri + telefon uygulamasi
rem           4 npm paketleri (yalniz ilk sefer)  5 electron-builder  6 kok kopya
rem
rem  Secenekler:
rem    DERLE.bat /hizli   PyInstaller adimini atlar (yalniz kabuk/ekranlar degistiyse)
rem    DERLE.bat /pwa     telefon uygulamasini once kod\masaustu\build\pwa'ya derler
rem                       (kod\arayuz\dist'e DOKUNMAZ; varsayilan: hazir kod\arayuz\dist)
rem
rem  Gerekenler: repo'da .venv (Python 3.14), Node 24. Surum: kod\masaustu\package.json
rem ============================================================================
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
set "MASAUSTU=%~dp0"
for %%I in ("%~dp0..\..") do set "KOK=%%~fI"
set "PY=%KOK%\.venv\Scripts\python.exe"
set "PYTHONPATH=%KOK%\kod"
set "HIZLI="
set "PWA="
for %%A in (%*) do (
    if /i "%%~A"=="/hizli" set "HIZLI=1"
    if /i "%%~A"=="/pwa" set "PWA=1"
)

echo.
echo   ==========================================================
echo     DEHANET SAHA - masaustu derlemesi
echo   ==========================================================

if not exist "%PY%" (
    echo   HATA: Python ortami yok: %PY%
    goto hata
)
where node >nul 2>&1
if errorlevel 1 (
    echo   HATA: Node.js bulunamadi. https://nodejs.org adresinden Node 24 kurun.
    goto hata
)

rem --- 0) PyInstaller (yoksa .venv'e kurulur) ---------------------------------
"%PY%" -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo   PyInstaller kuruluyor...
    "%PY%" -m pip install --disable-pip-version-check -q pyinstaller
    if errorlevel 1 goto hata
)

rem --- 1) Simgeler ------------------------------------------------------------
echo.
echo   [1/6] Simgeler
"%PY%" araclar\ikon_uret.py
if errorlevel 1 goto hata

rem --- 2) Sunucu: SahaSunucu.exe ----------------------------------------------
echo.
if defined HIZLI (
    echo   [2/6] SahaSunucu.exe - atlandi ^(/hizli^)
    if not exist "build\sunucu\SahaSunucu.exe" (
        echo   HATA: build\sunucu\SahaSunucu.exe yok; /hizli olmadan calistirin.
        goto hata
    )
) else (
    echo   [2/6] SahaSunucu.exe derleniyor ^(PyInstaller, 3-5 dakika^)
    if exist "build\sunucu" rmdir /s /q "build\sunucu"
    "%PY%" -m PyInstaller sunucu.spec --noconfirm --distpath build --workpath build\pyi-is --log-level WARN
    if errorlevel 1 goto hata
)

rem --- 3) Veri kaynaklari + telefon uygulamasi --------------------------------
echo.
echo   [3/6] Veri kaynaklari ve telefon uygulamasi
set "PWA_ARG="
if not defined PWA goto kaynaklar
if not exist "%KOK%\kod\arayuz\node_modules\vite\bin\vite.js" (
    echo   HATA: kod\arayuz\node_modules yok. kod\arayuz klasorunde once: npm install
    goto hata
)
pushd "%KOK%\kod\arayuz"
node node_modules\vite\bin\vite.js build --outDir "%MASAUSTU%build\pwa" --emptyOutDir
if errorlevel 1 (
    popd
    goto hata
)
popd
set "PWA_ARG=--pwa build\pwa"
:kaynaklar
"%PY%" araclar\kaynak_topla.py --hedef build\sunucu\_internal %PWA_ARG%
if errorlevel 1 goto hata
build\sunucu\SahaSunucu.exe surum
if errorlevel 1 goto hata

rem --- 4) npm paketleri -------------------------------------------------------
echo.
echo   [4/6] Electron paketleri
if not exist "node_modules\electron-builder\cli.js" (
    call npm install --no-audit --no-fund
    if errorlevel 1 goto hata
)
if not exist "node_modules\electron\dist\electron.exe" (
    node node_modules\electron\install.js
    if errorlevel 1 goto hata
)

rem --- 5) Kurulum programi + tasinabilir exe ----------------------------------
echo.
echo   [5/6] Kurulum programi ve tasinabilir exe ^(electron-builder^)
set "CSC_IDENTITY_AUTO_DISCOVERY=false"
node node_modules\electron-builder\cli.js --win nsis portable --x64 --publish never
if errorlevel 1 goto hata

rem --- 6) Kok dizindeki kopya -------------------------------------------------
echo.
echo   [6/6] Kok dizine kopya: DehanetSaha.exe
copy /y "dist\DehanetSaha.exe" "%KOK%\DehanetSaha.exe" >nul
if errorlevel 1 (
    echo   UYARI: kok kopya yazilamadi ^(uygulama acik olabilir^). dist\DehanetSaha.exe kullanin.
)

echo.
echo   ==========================================================
echo     TAMAM
echo   ==========================================================
for %%F in ("dist\DehanetSaha-Kurulum-*.exe" "dist\DehanetSaha.exe" "%KOK%\DehanetSaha.exe") do (
    if exist "%%~F" echo     %%~zF bayt   %%~fF
)
echo.
exit /b 0

:hata
echo.
echo   DERLEME DURDU. Yukaridaki mesaji okuyun.
echo.
exit /b 1
