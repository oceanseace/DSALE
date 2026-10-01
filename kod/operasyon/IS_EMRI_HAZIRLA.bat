@echo off
rem ============================================================================
rem  IS EMRI HAZIRLA - BOSS "Teknik Task Detay Raporu"nu makro gibi hazirlar.
rem
rem  Kullanim: BOSS'tan indirdiginiz .xlsx dosyasini bu dosyanin UZERINE SURUKLEYIN.
rem    - Task Adi'nda "kurulum" ya da "2. donanim" gecen satirlar cikarilir
rem    - Adresten mahalle bulunur (ilce ile birlikte: Nilufer/Dumlupinar ayri,
rem      Osmangazi/Dumlupinar ayri)
rem    - Tanimli obekler yazilir
rem    - Ayni klasore  <dosya>_hazir.xlsx  olusur (Isler, Obekler, Mahalleler,
rem      Kontrol, Cikarilanlar, Ozet sayfalari)
rem
rem  Obek tanimlamak: _hazir.xlsx dosyasinin "Mahalleler" sayfasinda Obek
rem  sutununu doldurup kaydedin, sonra o dosyayi da bunun uzerine surukleyin.
rem  (Ayni isi yonetici ekranindaki "Is emirleri" bolumunden de yapabilirsiniz.)
rem ============================================================================
chcp 65001 >nul
setlocal
rem Depo koku (kod\operasyon -> ..\..), .venv Python'u, kod\ ice aktarma yolu.
for %%I in ("%~dp0..\..") do set "KOK=%%~fI"
cd /d "%KOK%"
set "PY=%KOK%\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
set "PYTHONPATH=%KOK%\kod"
set "PYTHONIOENCODING=utf-8"
if "%~1"=="" (
    echo.
    echo   BOSS raporunu ^(.xlsx^) bu dosyanin uzerine surukleyip birakin.
    echo.
    pause
    exit /b 1
)
"%PY%" -W ignore -m operasyon.is_emri %*
echo.
pause
