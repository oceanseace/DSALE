@echo off
rem ============================================================================
rem  SAHA SISTEMI - gelistirme kodunu (kod\) canli sisteme (canli\) yayinlar.
rem
rem  Asil arac kod\saha\YAYINLA.bat'tir; bu dosya yalniz onu cagirir.
rem  Arac hazir olana kadar canli\ klasorune hicbir sey yapilmaz.
rem ============================================================================
chcp 65001 >nul
if exist "%~dp0kod\saha\YAYINLA.bat" (
    call "%~dp0kod\saha\YAYINLA.bat" %*
    exit /b %errorlevel%
)
echo.
echo   Yayin araci hazirlaniyor. Canli sistem degismedi.
echo   Gunluk kullanim icin: BASLAT.bat
echo.
pause
exit /b 1
