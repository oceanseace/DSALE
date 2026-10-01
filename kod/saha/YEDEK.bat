@echo off
rem ============================================================================
rem  SAHA SISTEMI - veritabani yedegi (<calisma>\saha\yedek\, 30 gun saklanir).
rem
rem  Elle: bu dosyaya cift tiklayin.
rem  Otomatik: kod\saha\gorev\ klasorundeki XML'i Gorev Zamanlayici'ya alin,
rem            her gun 19:30'da kendiliginden calisir.
rem
rem  Sunucu acikken calistirilabilir; SQLite backup() kullanildigi icin
rem  yarim yazilmis dosya olusmaz.
rem ============================================================================
chcp 65001 >nul
setlocal
rem Depo koku (kod\saha -> ..\..), .venv Python'u, kod\ ice aktarma yolu.
rem Calisma klasoru: SAHA_VERI_DIZINI (yoksa gelistirme\veri; kod\yollar.py).
for %%I in ("%~dp0..\..") do set "KOK=%%~fI"
cd /d "%KOK%"
set "PY=%KOK%\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
set "PYTHONPATH=%KOK%\kod"

"%PY%" -m saha.yedekle
if errorlevel 1 (
    echo.
    echo   HATA: Yedek alinamadi.
    if not "%1"=="/sessiz" pause
    exit /b 1
)

if not "%1"=="/sessiz" (
    echo.
    "%PY%" -m saha.yedekle --liste
    echo.
    pause
)
exit /b 0
