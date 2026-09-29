#!/usr/bin/env python3
"""Send a safe, per-turn tool summary to the paired Telegram DM."""

from __future__ import annotations

from collections import Counter
from html import escape
from html.parser import HTMLParser
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import urllib.request


MAX_TAIL_BYTES = 8 * 1024 * 1024
MAX_TOOL_NAMES = 20
ACCESS_FILE = Path.home() / ".claude/channels/telegram/access.json"
STATE_DIR = Path.home() / ".cache/claude-telegram-tools"
TRANSPORT_PREFIX = "mcp__plugin_telegram_"


class ChannelTag(HTMLParser):
    def __init__(self):
        super().__init__()
        self.attrs = None

    def handle_starttag(self, tag, attrs):
        if self.attrs is None and tag == "channel":
            self.attrs = dict(attrs)


def _channel_turn(content):
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        text = "\n".join(
            block.get("text", "") for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    else:
        return None
    text = text.lstrip()
    if not text.startswith("<channel "):
        return None
    end = text.find(">")
    if end < 0 or end > 1000:
        return None
    parser = ChannelTag()
    parser.feed(text[:end + 1])
    attrs = parser.attrs or {}
    chat_id = attrs.get("chat_id", "")
    if (attrs.get("source") != "telegram"
            or not re.fullmatch(r"\d+", chat_id)
            or chat_id != attrs.get("user_id")):
        return None
    return chat_id


def latest_turn_tools(transcript_path):
    path = Path(transcript_path)
    if not path.is_file():
        return None
    chat_id = turn_id = None
    names = []
    seen_ids = set()
    with path.open("rb") as handle:
        size = handle.seek(0, os.SEEK_END)
        start = max(0, size - MAX_TAIL_BYTES)
        handle.seek(start)
        if start:
            handle.readline()
        for raw_line in handle:
            try:
                entry = json.loads(raw_line)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            kind = entry.get("type")
            content = (entry.get("message") or {}).get("content")
            if kind == "user":
                if (isinstance(content, list) and content
                        and all(isinstance(block, dict) and block.get("type") == "tool_result"
                                for block in content)):
                    continue
                chat_id = _channel_turn(content) if entry.get("isMeta") else None
                turn_id = str(entry.get("uuid") or "") if chat_id else None
                names = []
                seen_ids = set()
            elif kind == "assistant" and chat_id and not entry.get("isSidechain"):
                if not isinstance(content, list):
                    continue
                for block in content:
                    if not isinstance(block, dict) or block.get("type") != "tool_use":
                        continue
                    name = block.get("name")
                    tool_id = block.get("id")
                    if (not isinstance(name, str) or not name
                            or name.startswith(TRANSPORT_PREFIX)
                            or (tool_id and tool_id in seen_ids)):
                        continue
                    if tool_id:
                        seen_ids.add(tool_id)
                    names.append(name)
    return (chat_id, turn_id, names) if chat_id and turn_id and names else None


def format_message(names):
    counts = Counter(names)
    lines = []
    for name, count in list(counts.items())[:MAX_TOOL_NAMES]:
        safe_name = re.sub(r"\s+", " ", name).strip()[:72]
        lines.append(f"{safe_name} ×{count}")
    if len(counts) > MAX_TOOL_NAMES:
        lines.append(f"另有 {len(counts) - MAX_TOOL_NAMES} 种工具")
    details = escape("\n".join(lines))
    return f"🔧 工具使用（{len(names)} 次）\n<blockquote expandable>{details}</blockquote>"


def _allowed_chat(chat_id, access_file):
    try:
        access = json.loads(Path(access_file).read_text(encoding="utf-8"))
        allowed = access.get("allowFrom", [])
        return isinstance(allowed, list) and chat_id in map(str, allowed)
    except (OSError, json.JSONDecodeError, AttributeError, TypeError):
        return False


def _marker_path(state_dir, session_id):
    digest = hashlib.sha256(session_id.encode("utf-8")).hexdigest()
    return Path(state_dir) / f"{digest}.json"


def _already_sent(marker, turn_id):
    try:
        return json.loads(marker.read_text(encoding="utf-8")).get("turn_id") == turn_id
    except (OSError, json.JSONDecodeError, AttributeError):
        return False


def _send_message(token, chat_id, body):
    payload = json.dumps({
        "chat_id": chat_id,
        "text": body,
        "parse_mode": "HTML",
        "link_preview_options": {"is_disabled": True},
    }).encode("utf-8")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    request = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=12) as response:
        if not json.load(response).get("ok"):
            raise RuntimeError("Telegram rejected the tool summary")


def process_hook(event, token, access_file=ACCESS_FILE, state_dir=STATE_DIR,
                 send_message=_send_message):
    transcript = event.get("transcript_path")
    session_id = event.get("session_id")
    if not token or not isinstance(transcript, str) or not session_id:
        return False
    turn = latest_turn_tools(transcript)
    if not turn:
        return False
    chat_id, turn_id, names = turn
    if not _allowed_chat(chat_id, access_file):
        return False
    marker = _marker_path(state_dir, str(session_id))
    if _already_sent(marker, turn_id):
        return False
    send_message(token, chat_id, format_message(names))
    marker.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    marker.write_text(json.dumps({"turn_id": turn_id}), encoding="utf-8")
    marker.chmod(0o600)
    return True


def main():
    try:
        event = json.load(sys.stdin)
        if isinstance(event, dict):
            process_hook(event, os.environ.get("TELEGRAM_BOT_TOKEN", ""))
    except Exception:
        pass


if __name__ == "__main__":
    main()
