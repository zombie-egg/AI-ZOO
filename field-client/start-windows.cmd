@echo off
setlocal EnableExtensions
set "PROJECT_DIR=%~dp0.."
set "CONFIG_DIR=%LOCALAPPDATA%\AI-ZOO"
set "TERMINAL_FILE=%CONFIG_DIR%\terminal-id.txt"
set "RUNNER_FILE=%CONFIG_DIR%\run-print-agent.cmd"
set "STARTUP_FILE=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\AI-ZOO-Print-Agent.cmd"
set "CLOUD_URL=https://ai-zoo-zombie.zeabur.app"

where node >nul 2>nul || (
  echo Please install Node.js 20 or newer from https://nodejs.org
  pause
  exit /b 1
)

if not exist "%CONFIG_DIR%" mkdir "%CONFIG_DIR%"
if not exist "%TERMINAL_FILE%" powershell -NoProfile -Command "$id=[guid]::NewGuid().ToString('N'); Set-Content -NoNewline -Encoding ascii '%TERMINAL_FILE%' $id"
set /p TERMINAL_ID=<"%TERMINAL_FILE%"

cd /d "%PROJECT_DIR%\print-agent"
if not exist "node_modules\.bin\electron.cmd" call npm ci
if errorlevel 1 exit /b 1

>"%RUNNER_FILE%" echo @echo off
>>"%RUNNER_FILE%" echo cd /d "%PROJECT_DIR%\print-agent"
>>"%RUNNER_FILE%" echo set "AI_ZOO_PRINT_RELAY_URL=%CLOUD_URL%"
>>"%RUNNER_FILE%" echo set "AI_ZOO_TERMINAL_ID=%TERMINAL_ID%"
>>"%RUNNER_FILE%" echo npm start ^> "%%TEMP%%\ai-zoo-print-agent.log" 2^>^&1
>"%STARTUP_FILE%" echo @start "AI ZOO Print Agent" /min "%RUNNER_FILE%"

start "AI ZOO Print Agent" /min "%RUNNER_FILE%"
start "" "%CLOUD_URL%/kiosk/?terminal=%TERMINAL_ID%"
echo AI ZOO background print service is installed and will start at login.
echo From now on, only open: %CLOUD_URL%/kiosk/
echo Terminal ID: %TERMINAL_ID%
pause
exit /b 0
