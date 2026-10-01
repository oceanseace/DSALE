; Dehanet Saha — kurulum programı eklentileri (electron-builder NSIS şablonuna eklenir).
;
; 1) Güncellemede çalışan uygulamadan önce KENDİSİNİN kapanması istenir (--kapat): sunucu açık
;    kayıtları tamamlayıp veritabanını düzgün kapatır. 25 sn içinde kapanmazsa şablonun olağan
;    denetimi devreye girer (kapat / zorla kapat).
; 2) Veri klasörü (%ProgramData%\DehanetSaha ya da Ayarlar'da seçilen) kurulumda, güncellemede ve
;    kaldırmada ASLA silinmez; bu dosya ona hiç dokunmaz.
; 3) Kaldırmada (güncelleme değilse) "bilgisayar açılınca başlat" kaydı temizlenir.

!include "getProcessInfo.nsh"
Var pid

!macro customCheckAppRunning
  !insertmacro IS_POWERSHELL_AVAILABLE
  IfFileExists "$INSTDIR\${APP_EXECUTABLE_FILENAME}" 0 dehanetKontrol
    DetailPrint "Dehanet Saha kapatiliyor (sunucu veritabanini duzgun kapatir)..."
    nsExec::Exec '"$INSTDIR\${APP_EXECUTABLE_FILENAME}" --kapat'
    Pop $R0
    StrCpy $R2 0
    dehanetBekle:
      !insertmacro FIND_PROCESS "${APP_EXECUTABLE_FILENAME}" $R0
      ${if} $R0 == 0
        ${if} $R2 < 25
          Sleep 1000
          IntOp $R2 $R2 + 1
          Goto dehanetBekle
        ${endIf}
      ${endIf}
  dehanetKontrol:
  !insertmacro _CHECK_APP_RUNNING
!macroend

!macro customUnInstall
  ${ifNot} ${isUpdated}
    DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "DehanetSaha"
  ${endIf}
!macroend
