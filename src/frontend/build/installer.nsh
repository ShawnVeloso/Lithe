; Auto-included by electron-builder (buildResources/installer.nsh).
; Upgrades hang when a stale lithe-server.exe keeps the install dir locked.
!macro customInit
  nsExec::Exec `taskkill /f /t /im lithe-server.exe`
  nsExec::Exec `taskkill /f /t /im Lithe.exe`
!macroend

!macro customUnInit
  nsExec::Exec `taskkill /f /t /im lithe-server.exe`
  nsExec::Exec `taskkill /f /t /im Lithe.exe`
!macroend
