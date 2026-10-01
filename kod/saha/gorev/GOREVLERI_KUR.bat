@echo off
rem ============================================================================
rem  SAHA SISTEMI - Windows Gorev Zamanlayici kurulumu (bir kez calistirilir).
rem
rem  Kurdugu iki gorev:
rem    "Saha Sistemi - Sunucu"  bilgisayar acildiktan 1 dakika sonra sunucuyu
rem                             baslatir (ofis agi, port 8080)
rem    "Saha Sistemi - Yedek"   her gun 19:30'da veritabani yedegi alir
rem
rem  KULLANIM: bu dosyaya SAG TIKLAYIN > "Yonetici olarak calistir".
rem  Klasor yolu otomatik bulunur, elle duzenleme gerekmez.
rem
rem  Kaldirmak icin:  GOREVLERI_SIL.bat
rem ============================================================================
chcp 65001 >nul
setlocal EnableDelayedExpansion

net session >nul 2>&1
if errorlevel 1 (
    echo.
    echo   Bu dosyaya SAG TIKLAYIP "Yonetici olarak calistir" demeniz gerekiyor.
    echo.
    pause
    exit /b 1
)

rem kod\saha\gorev\ -> depo kokune cik
rem TODO(YAYINLA): "Yedek" gorevi kod\saha\YEDEK.bat'i calistirir; canli verinin yedegi icin
rem   YEDEK.bat SAHA_VERI_DIZINI=canli\veri ile calismali (yayin araci ayarlar).
for %%I in ("%~dp0..\..\..") do set "KOK=%%~fI"

echo.
echo   ==========================================================
echo     SAHA SISTEMI - zamanlanmis gorevler kuruluyor
echo   ==========================================================
echo.
echo   Proje klasoru: %KOK%
echo.

if not exist "%KOK%\BASLAT.bat" (
    echo   HATA: %KOK%\BASLAT.bat bulunamadi.
    echo   Bu dosyayi depo icindeki kod\saha\gorev\ klasorunden calistirin.
    pause
    exit /b 1
)

set "GECICI=%TEMP%\saha-gorev"
if not exist "%GECICI%" mkdir "%GECICI%"

call :kur "Saha Sistemi - Sunucu"
if errorlevel 1 goto son
call :kur "Saha Sistemi - Yedek"
if errorlevel 1 goto son

echo.
echo   ----------------------------------------------------------
echo     Kuruldu. Kontrol etmek icin: Gorev Zamanlayici ^> Gorev
echo     Zamanlayici Kitapligi ^> "Saha Sistemi - ..." satirlari.
echo.
echo     Sunucuyu SIMDI baslatmak icin: BASLAT.bat
echo     Durdurmak icin                : kod\saha\DURDUR.bat
echo   ----------------------------------------------------------

:son
echo.
pause
exit /b 0

rem --- Bir gorevi yer tutucuyu doldurup kurar ------------------------------
:kur
set "AD=%~1"
echo   [%AD%] hazirlaniyor...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$x = Get-Content -Raw -Encoding Unicode '%~dp0%AD%.xml';" ^
  "$x = $x -replace '__SAHA_KLASORU__', [regex]::Escape('%KOK%').Replace('\\','\');" ^
  "Set-Content -Path '%GECICI%\%AD%.xml' -Value $x -Encoding Unicode -NoNewline"
if errorlevel 1 (
    echo   HATA: XML hazirlanamadi.
    exit /b 1
)
schtasks /Delete /TN "%AD%" /F >nul 2>&1
schtasks /Create /TN "%AD%" /XML "%GECICI%\%AD%.xml" >nul
if errorlevel 1 (
    echo   HATA: "%AD%" gorevi kurulamadi.
    exit /b 1
)
del "%GECICI%\%AD%.xml" >nul 2>&1
echo   [%AD%] kuruldu.
exit /b 0
