#!/usr/bin/env python3
"""Register the Telegram tool summary Stop hook without replacing settings."""

import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
from datetime import datetime


COMMAND = "python3 /home/cc/.claude/hooks/send_tool_usage.py"
HOOK = {"hooks": [{"type": "command", "command": COMMAND, "timeout": 20}]}


def install(settings_path):
    settings_path = Path(settings_path)
    data = json.loads(settings_path.read_text(encoding="utf-8"))
    stop_hooks = data.setdefault("hooks", {}).setdefault("Stop", [])
    for group in stop_hooks:
        if any(hook.get("command") == COMMAND for hook in group.get("hooks", [])):
            return None
    stop_hooks.append(HOOK)

    suffix = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = settings_path.with_name(f"{settings_path.name}.before-telegram-tools-{suffix}")
    shutil.copy2(settings_path, backup)
    mode = stat.S_IMODE(settings_path.stat().st_mode)
    fd, temporary = tempfile.mkstemp(prefix=".settings-", dir=settings_path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.chmod(temporary, mode)
        os.replace(temporary, settings_path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return backup


if __name__ == "__main__":
    backup = install(Path.home() / ".claude/settings.json")
    print(f"Backup: {backup}" if backup else "Telegram tool hook already installed")
