#!/usr/bin/env bash
# 小克的家 — one-shot installer for Ubuntu.
#
#   bash deploy/install.sh
#
# Installs system packages, a Python venv, writes .env (asks for a password
# the first time) and a systemd service that starts on boot. Safe to re-run:
# it updates dependencies and restarts the service.
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_USER="${SUDO_USER:-$USER}"
RUN_HOME="$(getent passwd "$RUN_USER" | cut -d: -f6)"
SERVICE=xiaoke
PORT="${PORT:-8001}"

say() { printf '\033[38;5;173m==>\033[0m %s\n' "$*"; }

if [ "$(id -u)" -eq 0 ] && [ -z "${SUDO_USER:-}" ]; then
  echo "请用普通用户运行（脚本需要时会自己调用 sudo），不要直接用 root。" >&2
  exit 1
fi

say "安装系统依赖（python3-venv、tmux）"
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-venv python3-pip tmux >/dev/null

say "创建 Python 虚拟环境并安装依赖"
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install -q --upgrade pip
"$APP_DIR/.venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"

if [ ! -f "$APP_DIR/.env" ]; then
  say "第一次安装：设置登录密码"
  while true; do
    read -r -s -p "给小克的家设一个访问密码: " PW1; echo
    read -r -s -p "再输一次: " PW2; echo
    [ -n "$PW1" ] && [ "$PW1" = "$PW2" ] && break
    echo "两次不一样或者为空，再来一次。"
  done
  umask 077
  cat > "$APP_DIR/.env" <<ENV
DASHBOARD_PASSWORD=$PW1
PORT=$PORT
HOST=127.0.0.1
TOKEN_TTL_DAYS=30
ENV
  say ".env 已写好（只有你自己能读）"
else
  say "已有 .env，保留原来的密码和设置"
fi

if ! command -v claude >/dev/null 2>&1 && ! sudo -u "$RUN_USER" bash -lc 'command -v claude' >/dev/null 2>&1; then
  say "提示：没找到 claude 命令。装好 Node.js 后运行  npm install -g @anthropic-ai/claude-code  再登录一次。"
fi

# systemd doesn't read your shell profile, so carry over where claude / node /
# codex live (nvm, npm-global, ~/.local/bin ...).
EXTRA_PATH=""
for bin in claude node codex opencode; do
  d="$(sudo -u "$RUN_USER" bash -lc "command -v $bin" 2>/dev/null | xargs -r dirname || true)"
  [ -n "$d" ] && case ":$EXTRA_PATH:" in *":$d:"*) ;; *) EXTRA_PATH="$EXTRA_PATH$d:" ;; esac
done

say "写入 systemd 服务 /etc/systemd/system/$SERVICE.service"
sed -e "s#@APP_DIR@#$APP_DIR#g" -e "s#@USER@#$RUN_USER#g" -e "s#@HOME@#$RUN_HOME#g" -e "s#@EXTRA_PATH@#$EXTRA_PATH#g" \
  "$APP_DIR/deploy/xiaoke.service" | sudo tee "/etc/systemd/system/$SERVICE.service" >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable --now "$SERVICE" >/dev/null
sudo systemctl restart "$SERVICE"

sleep 2
if curl -fsS -o /dev/null "http://127.0.0.1:$PORT/"; then
  say "小克的家已经在 http://127.0.0.1:$PORT 跑起来了 🏠"
  say "下一步：在 Cloudflare Tunnel 里加一个子域名指向 http://localhost:$PORT（见 README）"
else
  echo "服务没起来，看看日志： sudo journalctl -u $SERVICE -n 50" >&2
  exit 1
fi
