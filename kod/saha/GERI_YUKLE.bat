@echo off
rem ============================================================================
rem  SAHA SISTEMI - yedekten geri yukleme (guncelleme geri donusu).
rem
rem  Yaptiklari (hicbir sey SILINMEZ):
rem    1. Sunucu aciksa "once DURDUR.bat" der ve cikar.
rem    2. <calisma>\saha\yedek\goc\ (guncelleme oncesi) ve <calisma>\saha\yedek\ (gunluk) yedeklerini
rem       tarihleriyle listeler; numara sorar.
rem    3. Mevcut saha.db'yi saha-hatali-<zaman>.db adiyla KENARA koyar.
rem    4. Secilen yedegi kopyalar, salt okunurlugu kaldirir, butunluk denetimi yapar.
rem    5. "Onceki surum klasorunden BASLAT.bat ile acin" der.
rem
rem  NOT: bu dosya bilerek Turkce karakter icermez (chcp 65001 + cmd.exe).
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

"%PY%" -m saha.yedekle --geri-yukle
set "SONUC=%errorlevel%"
echo.
pause
exit /b %SONUC%
