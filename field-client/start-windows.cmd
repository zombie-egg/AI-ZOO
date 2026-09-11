@echo off
setlocal EnableExtensions
set "AI_ZOO_SYSTEM_ROOT=%SystemRoot%"
if not defined AI_ZOO_SYSTEM_ROOT set "AI_ZOO_SYSTEM_ROOT=%windir%"
if not defined AI_ZOO_SYSTEM_ROOT set "AI_ZOO_SYSTEM_ROOT=C:\Windows"
set "AI_ZOO_SYSTEM32=%AI_ZOO_SYSTEM_ROOT%\System32"
set "AI_ZOO_POWERSHELL=%AI_ZOO_SYSTEM32%\WindowsPowerShell\v1.0\powershell.exe"

if exist "%AI_ZOO_SYSTEM32%\chcp.com" "%AI_ZOO_SYSTEM32%\chcp.com" 65001 >nul
if not exist "%AI_ZOO_POWERSHELL%" goto powershell_missing

set "SETUP_SCRIPT=%~dp0setup-windows.ps1"
set "DOWNLOADED_SCRIPT=%TEMP%\AI-ZOO-setup-windows.ps1"

echo [AI ZOO] Downloading the Windows one-click installer...
"%AI_ZOO_POWERSHELL%" -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ^
  "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -UseBasicParsing 'https://ai-zoo-zombie.zeabur.app/windows-client/setup-windows.ps1' -OutFile '%DOWNLOADED_SCRIPT%'"
if not errorlevel 1 set "SETUP_SCRIPT=%DOWNLOADED_SCRIPT%"
if not exist "%SETUP_SCRIPT%" goto download_failed

:run_setup
"%AI_ZOO_POWERSHELL%" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%SETUP_SCRIPT%"
if errorlevel 1 goto setup_failed
exit /b 0

:download_failed
echo.
echo [AI ZOO] Download failed. Check the Internet connection and run this file again.
pause
exit /b 1

:setup_failed
echo.
echo [AI ZOO] Setup did not finish. Keep this window open and send the error above to support.
pause
exit /b 1

:powershell_missing
echo.
echo [AI ZOO] Windows PowerShell was not found at:
echo %AI_ZOO_POWERSHELL%
echo Please send a photo of this message to support.
pause
exit /b 1
