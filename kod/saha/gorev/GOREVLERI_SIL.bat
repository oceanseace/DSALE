@echo off
rem ============================================================================
rem  SAHA SISTEMI - zamanlanmis gorevleri kaldirir.
rem  SAG TIKLAYIN > "Yonetici olarak calistir".
rem  Veritabanina, yedeklere ve uygulamaya DOKUNMAZ; yalnizca otomatik
rem  baslatma ve otomatik yedek gorevlerini siler.
rem ============================================================================
chcp 65001 >nul
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
