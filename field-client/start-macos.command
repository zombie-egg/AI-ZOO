#!/bin/zsh
set -e

SCRIPT_DIR=${0:A:h}
PROJECT_DIR=${SCRIPT_DIR:h}

if ! command -v node >/dev/null 2>&1; then
  echo "请先安装 Node.js 20 或更高版本：https://www.nodejs.org"
  read -k 1
  exit 1
fi

cd "$PROJECT_DIR/print-agent"
if [ ! -x node_modules/.bin/electron ]; then
  npm ci
fi
if ! lsof -nP -iTCP:17521 -sTCP:LISTEN >/dev/null 2>&1; then
  nohup npm start > /tmp/ai-zoo-print-agent.log 2>&1 &
fi

cd "$PROJECT_DIR/kiosk"
if [ ! -d node_modules ]; then
  npm ci
fi

(sleep 2; open "http://127.0.0.1:4175/kiosk/") &
export VITE_API_BASE_URL="https://ai-zoo-zombie.zeabur.app"
exec npm run dev -- --host 127.0.0.1 --port 4175
