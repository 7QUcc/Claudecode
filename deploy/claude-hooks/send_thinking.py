#!/usr/bin/env python3
"""Forward Claude's visible thinking summaries to paired Telegram chats.

This hook deliberately reads only Claude Code's emitted ``thinking`` blocks;
it does not attempt to reconstruct hidden reasoning or inspect unrelated files.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path


MAX_SUMMARY_CHARS = 2600
STATE_DIR = Path.home() / ".cache" / "claude-telegram-thinking"
ACCESS_FILE = Path.home() / ".claude" / "channels" / "telegram" / "access.json"


def _redact(text: str) -> str:
    patterns = (
        (r"(?i)\b(?:telegram[_ -]?bot[_ -]?token|api[_ -]?key|access[_ -]?token|password|passwd|secret)\s*[:=]\s*\S+", "[credential hidden]"),
        (r"\b\d{8,12}:[A-Za-z0-9_-]{30,}\b", "[bot token hidden]"),
        (r"\bsk-[A-Za-z0-9_-]{16,}\b", "[API key hidden]"),
        (r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b", "[GitHub token hidden]"),
    )
    for pattern, replacement in patterns:
        text = re.sub(pattern, replacement, text)
    return text.strip()


def _load_input() -> dict:
    try:
        value = json.load(sys.stdin)
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _thinking_summary(transcript_path: str) -> str:
    path = Path(transcript_path)
    if not path.is_file():
        return ""

    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - 4 * 1024 * 1024))
            raw = handle.read().decode("utf-8", errors="replace")
    except OSError:
        return ""

    latest = ""
    for line in raw.splitlines():
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        message = entry.get("message") or {}
        content = message.get("content")
        if entry.get("type") != "assistant" or not isinstance(content, list):
            continue
        blocks = [
            block.get("thinking", "").strip()
            for block in content
            if isinstance(block, dict)
            and block.get("type") == "thinking"
            and isinstance(block.get("thinking"), str)
        ]
        if blocks:
            latest = "\n\n".join(block for block in blocks if block)

    latest = _redact(latest)
    if len(latest) > MAX_SUMMARY_CHARS:
        latest = latest[:MAX_SUMMARY_CHARS].rstrip() + "\n…"
    return latest


def _latest_user_is_telegram(transcript_path: str) -> bool:
    path = Path(transcript_path)
    if not path.is_file():
        return False
    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - 4 * 1024 * 1024))
            raw = handle.read().decode("utf-8", errors="replace")
    except OSError:
        return False

    latest_user_text = ""
    for line in raw.splitlines():
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("type") != "user":
            continue
        content = (entry.get("message") or {}).get("content")
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            text = "\n".join(
                block.get("text", "")
                for block in content
                if isinstance(block, dict)
                and block.get("type") != "tool_result"
                and isinstance(block.get("text"), str)
            )
        else:
            text = ""

        if not text.strip():
            continue
        if re.search(
            r"<channel\b[^>]*\bsource\s*=\s*(?:[\"'][^\"']*telegram[^\"']*[\"']|[^\s>]*telegram[^\s>]*)",
            text,
            re.I,
        ) or not entry.get("isMeta"):
            # Telegram plugin prompts are marked as meta; internal meta
            # records without a channel marker must not hide them.
            latest_user_text = text
    return bool(re.search(
        r"<channel\b[^>]*\bsource\s*=\s*(?:[\"'][^\"']*telegram[^\"']*[\"']|[^\s>]*telegram[^\s>]*)",
        latest_user_text,
        re.I,
    ))


def _allowed_chats() -> list[str]:
    try:
        data = json.loads(ACCESS_FILE.read_text(encoding="utf-8"))
        values = data.get("allowFrom", [])
        if isinstance(values, str):
            values = [values]
        return [str(value) for value in values if str(value).strip()]
    except (OSError, json.JSONDecodeError, AttributeError, TypeError):
        return []


def _marker_path(session_id: str) -> Path:
    return STATE_DIR / (hashlib.sha256(session_id.encode("utf-8")).hexdigest() + ".json")


def _already_sent(session_id: str, summary: str) -> bool:
    digest = hashlib.sha256(summary.encode("utf-8")).hexdigest()
    marker = _marker_path(session_id)
    try:
        previous = json.loads(marker.read_text(encoding="utf-8"))
        if previous.get("digest") == digest:
            return True
    except (OSError, json.JSONDecodeError, AttributeError):
        pass
    return False


def _mark_sent(session_id: str, summary: str) -> None:
    marker = _marker_path(session_id)
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        marker.write_text(json.dumps({"digest": hashlib.sha256(summary.encode("utf-8")).hexdigest()}), encoding="utf-8")
    except OSError:
        pass


def _send(token: str, chat_id: str, summary: str) -> None:
    body = "☁️ 思考摘要\n<blockquote expandable>" + html.escape(summary) + "</blockquote>"
    payload = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": body,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }).encode("utf-8")
    url = "https://api.telegram.org/bot" + token + "/sendMessage"
    request = urllib.request.Request(url, data=payload, method="POST")
    with urllib.request.urlopen(request, timeout=15) as response:
        if response.status >= 300:
            raise RuntimeError("Telegram returned HTTP %s" % response.status)


def main() -> None:
    event = _load_input()
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    transcript = event.get("transcript_path")
    session_id = str(event.get("session_id") or transcript or "unknown")
    if not token or not isinstance(transcript, str):
        return

    summary = _thinking_summary(transcript)
    if not summary or not _latest_user_is_telegram(transcript) or _already_sent(session_id, summary):
        return

    sent = False
    for chat_id in _allowed_chats():
        try:
            _send(token, chat_id, summary)
            sent = True
        except Exception:
            # A notification failure must never block Claude from stopping.
            continue
    if sent:
        _mark_sent(session_id, summary)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
