#!/usr/bin/env bash
set -euo pipefail

plugin_dir="$HOME/.claude/plugins/cache/claude-plugins-official/telegram/0.0.7"
plugin_file="$plugin_dir/server.ts"
patch_file="$(dirname "$(realpath "$0")")/telegram-context.patch"
expected_sha="d902d7195a527b579b889cfdbf251fc24fd224a68e319ac6b7c3b691515c3458"
expected_patched_sha="b3aaed221d4c52fd27d6072dd00b1335d691ba4e384aa2aa69726af27f09664f"

if [[ ! -f "$plugin_file" ]]; then
  echo "Telegram plugin 0.0.7 is not installed" >&2
  exit 1
fi
actual_sha="$(sha256sum "$plugin_file" | cut -d ' ' -f 1)"
if [[ "$actual_sha" == "$expected_patched_sha" ]]; then
  echo "Telegram context command already installed"
  exit 0
fi
if [[ "$actual_sha" != "$expected_sha" ]]; then
  echo "Telegram plugin has changed; review the patch before applying it" >&2
  exit 1
fi

patch --dry-run -d "$plugin_dir" -p0 < "$patch_file"
cp -p "$plugin_file" "$plugin_file.before-xiaoke-context"
patch -d "$plugin_dir" -p0 < "$patch_file"
echo "Telegram context command installed; restart its Claude session to load it"
