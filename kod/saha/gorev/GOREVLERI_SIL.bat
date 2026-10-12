@echo off
rem ============================================================================
rem  SAHA SISTEMI - zamanlanmis gorevleri kaldirir.
rem  SAG TIKLAYIN > "Yonetici olarak calistir".
rem  Veritabanina, yedeklere ve uygulamaya DOKUNMAZ; yalnizca otomatik
rem  baslatma ve otomatik yedek gorevlerini siler.
rem ============================================================================
chcp 65001 >nul
setlocal
rem --- Gelistirme kopyasi gorev KURMAZ/SILMEZ ---------------------------------
rem  Gorev adlari canli kurulumla AYNIDIR. Bu kopya (kod\saha\gorev) gelistirme
rem  kodudur; "Yedek" gorevi buradan kurulursa canli veritabaninin gunluk yedegi
rem  sessizce gelistirme verisinin yedegiyle yer degistirir. Canli gorevler
rem  canli\ altindaki kopyadan kurulur (YAYINLA.bat hazir olana kadar:
rem  canli\surum\saha\gorev\%~nx0).
set "GOREV_YERI=%~dp0"
if /i "%GOREV_YERI:\canli\=%"=="%GOREV_YERI%" (
    echo.
    echo   Bu dosya GELISTIRME kopyasidir; zamanlanmis gorevlere dokunmaz.
    echo   Canli sistemin gorevleri icin su dosyayi kullanin:
    for %%I in ("%~dp0..\..\..\canli\surum\saha\gorev\%~nx0") do echo     %%~fI
    echo.
    pause
    exit /b 1
)

net session >nul 2>&1
if errorlevel 1 (
    echo.
    echo   Bu dosyaya SAG TIKLAYIP "Yonetici olarak calistir" deyin.
    pause
    exit /b 1
)
echo.
schtasks /Delete /TN "Saha Sistemi - Sunucu" /F
schtasks /Delete /TN "Saha Sistemi - Yedek" /F
echo.
echo   Gorevler kaldirildi. Sunucu hala calisiyorsa: kod\saha\DURDUR.bat
echo.
pause
