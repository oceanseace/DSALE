@echo off
rem ============================================================================
rem  SAHA SISTEMI - sunucuyu durdurur.
rem
rem  BASLAT.bat penceresi kapanmadiysa ya da sunucu arka planda calisiyorsa
rem  (zamanlanmis gorev ile acilmissa) bu dosyaya cift tiklayin.
rem
rem    DURDUR.bat          "saha.sunucu" calistiran BUTUN Python sureclerini kapatir
rem                        (canli VE gelistirme sunucusu)
rem    DURDUR.bat 8090     yalniz o portta acilmis sunucuyu kapatir (gelistirme)
rem
rem  Not: bilgisayardaki diger Python islerine dokunmaz.
rem
rem  NOT: bu dosya bilerek Turkce karakter icermez. chcp 65001 sonrasi
rem  cmd.exe cok baytli karakterlerde satiri kaydiriyor.
rem ============================================================================
chcp 65001 >nul
setlocal
set "SAHA_DURDUR_PORT=%~1"

echo.
echo   Saha Sistemi sunucusu araniyor...
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$p = Get-CimInstance Win32_Process -Filter \"Name='python.exe' or Name='pythonw.exe'\" | Where-Object { $_.CommandLine -like '*saha.sunucu*' };" ^
  "if ($env:SAHA_DURDUR_PORT) { $p = $p | Where-Object { $_.CommandLine -like ('*--port ' + $env:SAHA_DURDUR_PORT + '*') } };" ^
  "if (-not $p) { Write-Host '  Calisan sunucu bulunamadi. (Zaten kapali.)' -ForegroundColor Yellow; exit 0 }" ^
  "foreach ($x in $p) { Write-Host ('  Kapatiliyor: PID ' + $x.ProcessId); Stop-Process -Id $x.ProcessId -Force }" ^
  "Start-Sleep -Milliseconds 800;" ^
  "$k = Get-CimInstance Win32_Process -Filter \"Name='python.exe' or Name='pythonw.exe'\" | Where-Object { $_.CommandLine -like '*saha.sunucu*' };" ^
  "if ($env:SAHA_DURDUR_PORT) { $k = $k | Where-Object { $_.CommandLine -like ('*--port ' + $env:SAHA_DURDUR_PORT + '*') } };" ^
  "if ($k) { Write-Host '  UYARI: bazi surecler kapanmadi.' -ForegroundColor Red; exit 1 }" ^
  "Write-Host '  Sunucu durduruldu.' -ForegroundColor Green"

echo.
echo   Yeniden acmak icin: BASLAT.bat (canli) ya da kod\saha\GELISTIRME_BASLAT.bat
echo.
pause
