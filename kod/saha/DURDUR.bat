@echo off
rem ============================================================================
rem  SAHA SISTEMI - sunucuyu durdurur.
rem
rem  GELISTIRME kopyasi (kod\saha\DURDUR.bat) yalniz gelistirme sunucularini
rem  (127.0.0.1, port 8090-8099) kapatir; canli sunucuya (8080) DOKUNMAZ:
rem
rem    DURDUR.bat          8090-8099 portlarindaki BUTUN gelistirme sunucularini kapatir
rem    DURDUR.bat 8092     yalniz 8092 portundaki sunucuyu kapatir
rem                        (port birebir eslesir: "DURDUR.bat 809" hicbir seyi kapatmaz)
rem
rem  Port, komut satirindaki --port N'den; --port verilmemisse (or. varsayilan
rem  8090 ile "python -m saha.sunucu") surecin DINLEDIGI porttan okunur
rem  (Get-NetTCPConnection; .venv baslaticisi icin alt surecin portu).
rem
rem  Canli sunucuyu durdurmak: canli\ altindaki kopyanin DURDUR.bat'i
rem  (bu dosya canli\ altindan calisiyorsa her port, argumansiz: hepsi).
rem
rem  Not: bilgisayardaki diger Python islerine dokunmaz.
rem
rem  NOT: bu dosya bilerek Turkce karakter icermez. chcp 65001 sonrasi
rem  cmd.exe cok baytli karakterlerde satiri kaydiriyor.
rem ============================================================================
chcp 65001 >nul
setlocal
set "SAHA_DURDUR_PORT=%~1"
set "SAHA_DURDUR_YER=%~dp0"

echo.
echo   Turkcell sunucusu araniyor...
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$canli = $env:SAHA_DURDUR_YER -match '\\canli\\';" ^
  "$port = $env:SAHA_DURDUR_PORT;" ^
  "if ($port -and $port -notmatch '^\d+$') { Write-Host '  Port bir sayi olmali (or. DURDUR.bat 8090).' -ForegroundColor Red; exit 1 }" ^
  "if ($port -and -not $canli -and ([int]$port -lt 8090 -or [int]$port -gt 8099)) { Write-Host ('  Gelistirme kopyasi yalniz 8090-8099 portlarini kapatir; ' + $port + ' kapatilmadi (8080 canli sunucunundur).') -ForegroundColor Red; exit 1 }" ^
  "function Dinlenen { $d = @{}; try { Get-NetTCPConnection -State Listen -ErrorAction Stop | ForEach-Object { $d[[int]$_.OwningProcess] = [int]$_.LocalPort } } catch {}; return $d };" ^
  "function PortNo($x) { if ($x.CommandLine -match '--port[ =]+(\d+)') { return [int]$Matches[1] }; $id = [int]$x.ProcessId; if ($script:dinle.ContainsKey($id)) { return $script:dinle[$id] }; foreach ($c in $script:tum) { if ([int]$c.ParentProcessId -eq $id -and $script:dinle.ContainsKey([int]$c.ProcessId)) { return $script:dinle[[int]$c.ProcessId] } }; return -1 };" ^
  "function Bul { $script:dinle = Dinlenen; $script:tum = @(Get-CimInstance Win32_Process -Filter \"Name='python.exe' or Name='pythonw.exe'\" | Where-Object { $_.CommandLine -like '*saha.sunucu*' }); $s = $script:tum; if ($port) { return @($s | Where-Object { (PortNo $_) -eq [int]$port }) }; if ($canli) { return $s }; return @($s | Where-Object { $n = PortNo $_; $n -ge 8090 -and $n -le 8099 }) };" ^
  "$p = Bul;" ^
  "if (-not $p) { Write-Host '  Calisan sunucu bulunamadi. (Zaten kapali.)' -ForegroundColor Yellow; exit 0 }" ^
  "foreach ($x in $p) { Write-Host ('  Kapatiliyor: PID ' + $x.ProcessId + ' (port ' + (PortNo $x) + ')'); Stop-Process -Id $x.ProcessId -Force }" ^
  "Start-Sleep -Milliseconds 800;" ^
  "if (Bul) { Write-Host '  UYARI: bazi surecler kapanmadi.' -ForegroundColor Red; exit 1 }" ^
  "Write-Host '  Sunucu durduruldu.' -ForegroundColor Green"
set "SONUC=%errorlevel%"

echo.
echo   Yeniden acmak icin: BASLAT.bat (canli) ya da kod\saha\GELISTIRME_BASLAT.bat
echo.
if not "%SAHA_DURDUR_SESSIZ%"=="1" pause
exit /b %SONUC%
