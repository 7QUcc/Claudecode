#!/usr/bin/env bash
set -euo pipefail

args=("$@")
settings="$(dirname "$(dirname "$0")")/claude-session-settings.json"
if [[ -f "$settings" ]]; then
  args+=(--settings "$settings")
fi
if [[ "${XIAOKE_WITH_TELEGRAM:-0}" == "1" ]]; then
  args+=(--channels plugin:telegram@claude-plugins-official)
fi
exec claude "${args[@]}"
