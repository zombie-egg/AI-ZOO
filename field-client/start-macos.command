#!/bin/zsh
set -e

SCRIPT_DIR=${0:A:h}
PROJECT_DIR=${SCRIPT_DIR:h}
CONFIG_DIR="${XDG_CONFIG_HOME:-${HOME}/.config}/ai-zoo"
TERMINAL_FILE="$CONFIG_DIR/terminal-id"
RUNNER_FILE="$CONFIG_DIR/run-print-agent.command"
PLIST_FILE="${HOME}/Library/LaunchAgents/com.aizoo.print-agent.plist"
CLOUD_URL="https://ai-zoo-zombie.zeabur.app"

if ! command -v node >/dev/null 2>&1; then
  echo "请先安装 Node.js 20 或更高版本：https://nodejs.org"
  read -k 1
  exit 1
fi
NODE_BIN_DIR="$(dirname "$(command -v node)")"

mkdir -p "$CONFIG_DIR" "${HOME}/Library/LaunchAgents"
if [ ! -s "$TERMINAL_FILE" ]; then
  uuidgen | tr -d '-' | tr '[:upper:]' '[:lower:]' > "$TERMINAL_FILE"
fi
TERMINAL_ID="$(tr -d '\r\n' < "$TERMINAL_FILE")"

cd "$PROJECT_DIR/print-agent"
if [ ! -x node_modules/.bin/electron ]; then
  npm ci
fi

printf '%s\n' '#!/bin/zsh' \
  "cd ${(q)PROJECT_DIR}/print-agent" \
  "export AI_ZOO_PRINT_RELAY_URL=${(q)CLOUD_URL}" \
  "export AI_ZOO_TERMINAL_ID=${(q)TERMINAL_ID}" \
  "export PATH=${(q)NODE_BIN_DIR}:/usr/local/bin:/usr/bin:/bin" \
  'exec npm start' > "$RUNNER_FILE"
chmod 0700 "$RUNNER_FILE"

launchctl bootout "gui/$(id -u)/com.aizoo.print-agent" >/dev/null 2>&1 || true
cat > "$PLIST_FILE" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.aizoo.print-agent</string>
  <key>ProgramArguments</key><array><string>${RUNNER_FILE}</string></array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>/tmp/ai-zoo-print-agent.log</string>
  <key>StandardErrorPath</key><string>/tmp/ai-zoo-print-agent-error.log</string>
</dict></plist>
EOF
plutil -lint "$PLIST_FILE" >/dev/null
launchctl bootstrap "gui/$(id -u)" "$PLIST_FILE"
launchctl kickstart -k "gui/$(id -u)/com.aizoo.print-agent"

open "${CLOUD_URL}/kiosk/?terminal=${TERMINAL_ID}"
echo "AI ZOO 后台打印服务已安装并设置为开机自启。"
echo "今后只需打开：${CLOUD_URL}/kiosk/"
echo "终端编号：${TERMINAL_ID}"
read -k 1
