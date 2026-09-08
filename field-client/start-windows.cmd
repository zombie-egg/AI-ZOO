@echo off
setlocal EnableExtensions
chcp 65001 >nul

set "SETUP_SCRIPT=%~dp0setup-windows.ps1"
set "DOWNLOADED_SCRIPT=%TEMP%\AI-ZOO-setup-windows.ps1"

if exist "%SETUP_SCRIPT%" goto run_setup

echo [AI ZOO] Downloading the Windows one-click installer...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ^
  "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -UseBasicParsing 'https://raw.githubusercontent.com/zombie-egg/AI-ZOO/main/field-client/setup-windows.ps1' -OutFile '%DOWNLOADED_SCRIPT%'"
if errorlevel 1 goto download_failed
set "SETUP_SCRIPT=%DOWNLOADED_SCRIPT%"

:run_setup
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%SETUP_SCRIPT%"
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
