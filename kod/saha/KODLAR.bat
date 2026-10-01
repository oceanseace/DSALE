@echo off
rem ============================================================================
rem  SAHA SISTEMI - ilk giris davet kodlarini yazar.
rem
rem  Her satisci ilk girisinde: telefon -> DAVET KODU -> kendi PIN'i.
rem  Kod bir kez kullanilir; PIN belirlendikten sonra listede gorunmez.
rem  Birisi PIN'ini unutursa yonetici ekranindan "PIN sifirla" deyin,
rem  yeni kod orada buyuk puntoyla cikar.
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
echo.
"%PY%" -m saha.kur --kodlar
echo.
pause
