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
CONTEXT_ALERT_THRESHOLD = 0.90
STATE_DIR = Path.home() / ".cache" / "claude-telegram-thinking"
ACCESS_FILE = Path.home() / ".claude" / "channels" / "telegram" / "access.json"
CONTEXT_STATE_DIR = STATE_DIR / "context"


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


def _latest_context_usage(transcript_path: str) -> dict | None:
    path = Path(transcript_path)
    if not path.is_file():
        return None
    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - 512 * 1024))
            raw = handle.read().decode("utf-8", errors="replace")
    except OSError:
        return None

    for line in reversed(raw.splitlines()):
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("type") != "assistant" or entry.get("isSidechain"):
            continue
        usage = (entry.get("message") or {}).get("usage") or {}
        if not usage:
            continue
        breakdown = {
            "input": int(usage.get("input_tokens") or 0),
            "cache_creation": int(usage.get("cache_creation_input_tokens") or 0),
            "cache_read": int(usage.get("cache_read_input_tokens") or 0),
        }
        tokens = sum(breakdown.values())
        if not tokens:
            continue
        model = str((entry.get("message") or {}).get("model") or "").lower()
        if "[1m]" in model or model == "fable" or model.startswith("claude-fable"):
            window = 1_000_000
        elif model.startswith("claude-") or model.startswith("claude_"):
            window = 200_000
        else:
            return None
        if tokens > window:
            window = 1_000_000
        return {
            "tokens": tokens,
            "window": window,
            "pct": tokens / window,
        }
    return None


def _context_marker_path(session_id: str) -> Path:
    digest = hashlib.sha256(session_id.encode("utf-8")).hexdigest()
    return CONTEXT_STATE_DIR / (digest + ".json")


def _context_alerted(session_id: str) -> bool:
    try:
        data = json.loads(_context_marker_path(session_id).read_text(encoding="utf-8"))
        return bool(data.get("alerted"))
    except (OSError, json.JSONDecodeError, AttributeError):
        return False


def _clear_context_alert(session_id: str) -> None:
    try:
        _context_marker_path(session_id).unlink()
    except FileNotFoundError:
        pass
    except OSError:
        pass


def _mark_context_alerted(session_id: str, usage: dict) -> None:
    try:
        CONTEXT_STATE_DIR.mkdir(parents=True, exist_ok=True)
        _context_marker_path(session_id).write_text(
            json.dumps({"alerted": True, "tokens": usage["tokens"], "window": usage["window"]}),
            encoding="utf-8",
        )
    except OSError:
        pass


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


def _send_body(token: str, chat_id: str, body: str) -> None:
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


def _send(token: str, chat_id: str, summary: str) -> None:
    body = "☁️ 思考摘要\n<blockquote expandable>" + html.escape(summary) + "</blockquote>"
    _send_body(token, chat_id, body)


def _maybe_send_context_alert(token: str, chat_ids: list[str], session_id: str, transcript: str) -> None:
    usage = _latest_context_usage(transcript)
    if not usage or usage["pct"] < CONTEXT_ALERT_THRESHOLD:
        _clear_context_alert(session_id)
        return
    if _context_alerted(session_id):
        return

    percent = usage["pct"] * 100
    body = (
        "☁️ 上下文提醒\n"
        f"当前占用约 <b>{usage['tokens']:,} / {usage['window']:,}</b> tokens（{percent:.1f}%）。\n"
        "建议现在压缩一下上下文，避免后续对话遗忘或失败。"
    )
    sent = False
    for chat_id in chat_ids:
        try:
            _send_body(token, chat_id, body)
            sent = True
        except Exception:
            continue
    if sent:
        _mark_context_alerted(session_id, usage)


def main() -> None:
    event = _load_input()
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    transcript = event.get("transcript_path")
    session_id = str(event.get("session_id") or transcript or "unknown")
    if not token or not isinstance(transcript, str):
        return

    if not _latest_user_is_telegram(transcript):
        return
    chat_ids = _allowed_chats()
    if not chat_ids:
        return

    summary = _thinking_summary(transcript)
    if summary and not _already_sent(session_id, summary):
        sent = False
        for chat_id in chat_ids:
            try:
                _send(token, chat_id, summary)
                sent = True
            except Exception:
                continue
        if sent:
            _mark_sent(session_id, summary)

    _maybe_send_context_alert(token, chat_ids, session_id, transcript)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
