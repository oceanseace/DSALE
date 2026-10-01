@echo off
rem ============================================================================
rem  SAHA SISTEMI - GELISTIRME sunucusu (yalniz bu bilgisayar: 127.0.0.1:8090)
rem
rem  Gunluk kullanim icin DEGIL. Her gun kokteki BASLAT.bat calistirilir (canli).
rem  Bu dosya gelistirme kodunu (kod\) gelistirme verisiyle (gelistirme\veri\)
rem  acar; canli\ klasorune ve 8080 portuna hic dokunmaz.
rem
rem    GELISTIRME_BASLAT.bat            127.0.0.1:8090
rem    GELISTIRME_BASLAT.bat 8095       127.0.0.1:8095  (8090-8099 arasi)
rem
rem  Calisma klasoru: SAHA_VERI_DIZINI (yoksa gelistirme\veri). Bu klasorde
rem    saha\saha.db  saha\gizli.key  saha\yedek\  saha\kayit\  operasyon\ ...
rem
rem  Kapatmak: bu pencerede Ctrl+C.
rem
rem  NOT: bu dosya bilerek Turkce karakter icermez (chcp 65001 + cmd.exe).
rem ============================================================================
chcp 65001 >nul
setlocal
title Saha Sistemi - GELISTIRME (127.0.0.1)

rem --- Ortam: depo koku, Python (.venv), kod yolu, calisma klasoru ---------
for %%I in ("%~dp0..\..") do set "KOK=%%~fI"
cd /d "%KOK%"
set "PY=%KOK%\.venv\Scripts\python.exe"
if not exist "%PY%" (
    echo   [bilgi] .venv bulunamadi, sistemdeki Python kullanilacak.
    set "PY=python"
)
set "PYTHONPATH=%KOK%\kod"
set "PYTHONUNBUFFERED=1"
if not defined SAHA_VERI_DIZINI set "SAHA_VERI_DIZINI=%KOK%\gelistirme\veri"
set "VERI=%SAHA_VERI_DIZINI%"

set "PORT=8090"
if not "%~1"=="" set "PORT=%~1"
rem  Gelistirme yalniz 8090-8099 kullanir (8080 canli sunucunundur).
set "PORT_UYGUN="
if %PORT% GEQ 8090 if %PORT% LEQ 8099 set "PORT_UYGUN=1"
if not defined PORT_UYGUN (
    echo.
    echo   Port %PORT% kullanilamaz. Gelistirme icin 8090-8099 arasini kullanin
    echo   ^(8080 canli sunucunun portudur^).
    echo.
    pause
    exit /b 1
)

rem  Calisma klasoru canli\ altinda olamaz: canli veriye yalniz YAYINLA baglanir.
"%PY%" -c "import sys, yollar; c = yollar.CALISMA.resolve(); k = yollar.CANLI.resolve(); sys.exit(1 if c == k or k in c.parents else 0)"
if errorlevel 1 (
    echo.
    echo   HATA: SAHA_VERI_DIZINI canli klasorunu gosteriyor: %VERI%
    echo   Gelistirme sunucusu canli veriyle acilmaz.
    echo.
    pause
    exit /b 1
)

echo.
echo   ==========================================================
echo     SAHA SISTEMI - GELISTIRME  http://127.0.0.1:%PORT%
echo     Veri: %VERI%
echo   ==========================================================
echo.

rem --- 1) Gerekli paketler -------------------------------------------------
"%PY%" -c "import fastapi, uvicorn, itsdangerous, openpyxl, multipart, pandas, scipy, shapely" >nul 2>&1
if errorlevel 1 (
    echo   Eksik paketler kuruluyor...
    "%PY%" -m pip install --disable-pip-version-check -q -r "%KOK%\kod\saha\gereksinimler.txt"
    if errorlevel 1 goto hata
)

rem --- 2) Veritabani -------------------------------------------------------
rem  Veritabani yok AMA yedek varsa: yeniden tohumlanmaz. Geri yukleme: GERI_YUKLE.bat
if not exist "%VERI%\saha\saha.db" (
    "%PY%" -c "import sys, yollar; y = yollar.CALISMA_SAHA / 'yedek'; sys.exit(1 if (list(y.glob('saha-*.db')) + list(y.glob('goc/saha-*.db'))) else 0)"
    if errorlevel 1 goto yedek_var
)
if not exist "%VERI%\saha\saha.db" (
    echo   Gelistirme veritabani ilk kez kuruluyor...
    "%PY%" -m saha.kur
    if errorlevel 1 goto hata
)

rem --- 3) Arayuz derlendi mi -----------------------------------------------
if not exist "%KOK%\kod\arayuz\dist\index.html" (
    echo   [UYARI] Arayuz derlenmemis: kod\arayuz klasorunde  npm run build
    echo.
)

rem --- 4) Sunucu (yalniz bu bilgisayar) -------------------------------------
"%PY%" -m saha.sunucu --host 127.0.0.1 --port %PORT%
if errorlevel 3 goto hata
if errorlevel 2 goto son
if errorlevel 1 goto hata
:son
echo.
echo   Gelistirme sunucusu kapandi.
pause
exit /b 0

:yedek_var
echo.
echo   Veritabani yok (%VERI%\saha\saha.db), ama yedek var; bos veritabani KURULMADI.
echo   Geri yuklemek icin: kod\saha\GERI_YUKLE.bat
echo.
pause
exit /b 1

:hata
echo.
echo   HATA: gelistirme sunucusu acilamadi. Gunluk: %VERI%\saha\kayit\saha.log
echo.
pause
exit /b 1
