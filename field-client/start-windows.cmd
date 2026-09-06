@echo off
setlocal
set "PROJECT_DIR=%~dp0.."

where node >nul 2>nul || (
  echo Please install Node.js 20 or newer from https://nodejs.org
  pause
  exit /b 1
)

cd /d "%PROJECT_DIR%\print-agent"
if not exist "node_modules\.bin\electron.cmd" call npm ci
start "AI ZOO Print Agent" /min cmd /c "npm start > %TEMP%\ai-zoo-print-agent.log 2>&1"

cd /d "%PROJECT_DIR%\kiosk"
if not exist "node_modules" call npm ci
set "VITE_API_BASE_URL=https://ai-zoo-zombie.zeabur.app"
start "AI ZOO Kiosk" /min cmd /c "set VITE_API_BASE_URL=https://ai-zoo-zombie.zeabur.app&& npm run dev -- --host 127.0.0.1 --port 4175"
timeout /t 3 /nobreak >nul
start "" "http://127.0.0.1:4175/kiosk/"
exit /b 0
