"""Read the active Telegram session's last Claude context usage."""

from datetime import datetime
from pathlib import Path
import sys


def context_message(manager):
    holder = manager.telegram_status().get("holder")
    if not holder:
        return "当前没有连接的 Telegram 会话。"

    info = manager._pane_info(holder) or {}
    claude_pid = info.get("claude_pid")
    jsonl = manager._claude_jsonl_for_pid(claude_pid) if claude_pid else None
    usage = manager._read_last_usage(jsonl) if jsonl else None
    if not usage:
        return f"{holder}：暂无上下文用量，等 Claude 回复一次后再查。"

    tokens = usage["tokens"]
    window = usage["window"]
    pct = usage["pct"]
    model = usage["model"]
    message = f"{holder} · {model}\n上下文 {tokens:,} / {window:,}（{pct:.1f}%）"
    if usage.get("ts") is not None:
        updated = datetime.fromtimestamp(usage["ts"]).strftime("%m-%d %H:%M")
        message += f"\n最近一次模型调用：{updated}"
    return message


def main():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import terminal_manager

    print(context_message(terminal_manager))


if __name__ == "__main__":
    main()
