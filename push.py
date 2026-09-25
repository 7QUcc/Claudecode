"""Web Push for 小克的家.

Sends a notification to the phone when a Claude Code / Codex session
finishes a turn or stops to wait for the user (a permission prompt, an
AskUserQuestion menu, ...). iOS delivers these to a home-screen web app on
iOS 16.4 and later.

State lives in PRISM_DATA_DIR:
  vapid_private.pem   VAPID signing key, generated on first run
  push_subs.json      the subscribed devices and their preferences
"""

import base64
import json
import logging
import os
import re
import threading
import time
from pathlib import Path
from typing import Callable, Optional

log = logging.getLogger("push")

DATA_DIR = Path(os.path.expanduser(os.environ.get("PRISM_DATA_DIR", "~/.local/share/prism")))
KEY_PATH = DATA_DIR / "vapid_private.pem"
SUBS_PATH = DATA_DIR / "push_subs.json"
# Apple rejects localhost mailto claims with 403 BadJwtToken. Use the public
# HTTPS origin by default; deployments can override it with PUSH_CONTACT.
VAPID_SUBJECT = os.environ.get("PUSH_CONTACT", "https://xiaoke.41297.site")
POLL_SECONDS = float(os.environ.get("PUSH_POLL_SECONDS", "4"))
# Skip a notification if the phone reported looking at that session this recently.
PRESENCE_SECONDS = 45

_lock = threading.Lock()
_presence: dict = {}  # session name -> last time the app was visibly showing it

try:
    from py_vapid import Vapid02  # RFC 8292 "vapid t=…, k=…" header, which Apple expects
    from pywebpush import webpush, WebPushException
    AVAILABLE = True
except ImportError:  # pragma: no cover - dependency missing
    AVAILABLE = False


# ---------- keys & subscriptions ----------

def _vapid() -> "Vapid02":
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if KEY_PATH.exists():
        return Vapid02.from_file(str(KEY_PATH))
    v = Vapid02()
    v.generate_keys()
    v.save_key(str(KEY_PATH))
    os.chmod(KEY_PATH, 0o600)
    return v


def public_key() -> str:
    """Application server key for PushManager.subscribe (base64url, raw point)."""
    from cryptography.hazmat.primitives import serialization
    raw = _vapid().public_key.public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _load_subs() -> list:
    try:
        data = json.loads(SUBS_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save_subs(subs: list) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = SUBS_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(subs, ensure_ascii=False, indent=1), encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(SUBS_PATH)


def subscribe(sub: dict, prefs: Optional[dict] = None) -> None:
    endpoint = (sub or {}).get("endpoint")
    keys = (sub or {}).get("keys") or {}
    if not endpoint or not keys.get("p256dh") or not keys.get("auth"):
        raise ValueError("invalid subscription")
    prefs = {"done": True, "waiting": True, **(prefs or {})}
    with _lock:
        subs = [s for s in _load_subs() if s["sub"]["endpoint"] != endpoint]
        subs.append({"sub": {"endpoint": endpoint, "keys": keys}, "prefs": prefs, "created": time.time()})
        _save_subs(subs)


def unsubscribe(endpoint: str) -> None:
    with _lock:
        _save_subs([s for s in _load_subs() if s["sub"]["endpoint"] != endpoint])


def status(endpoint: Optional[str]) -> dict:
    for s in _load_subs():
        if s["sub"]["endpoint"] == endpoint:
            return {"subscribed": True, "prefs": s["prefs"]}
    return {"subscribed": False, "prefs": {"done": True, "waiting": True}}


def mark_presence(session: Optional[str]) -> None:
    if session:
        _presence[session] = time.time()


def clear_presence(session: Optional[str] = None) -> None:
    """Stop suppressing notifications for a session that left the foreground."""
    if session:
        _presence.pop(session, None)
    else:
        _presence.clear()


# ---------- sending ----------

def send(title: str, body: str, *, kind: str, session: Optional[str] = None,
         only_endpoint: Optional[str] = None) -> int:
    """Send to every subscribed device that wants this kind. Returns #sent."""
    if not AVAILABLE:
        return 0
    payload = json.dumps({
        "title": title,
        "body": body[:180],
        "tag": f"{kind}:{session or ''}",
        "session": session,
        "url": "/?s=" + session if session else "/",
    }, ensure_ascii=False)
    vapid = _vapid()
    sent, dead = 0, []
    for s in _load_subs():
        if only_endpoint and s["sub"]["endpoint"] != only_endpoint:
            continue
        if kind in ("done", "waiting") and not s["prefs"].get(kind, True):
            continue
        try:
            webpush(s["sub"], payload, vapid_private_key=vapid,
                    vapid_claims={"sub": VAPID_SUBJECT}, ttl=3600,
                    headers={"Urgency": "high" if kind == "waiting" else "normal"})
            sent += 1
        except WebPushException as exc:
            code = getattr(exc.response, "status_code", None)
            if code in (404, 410):  # the device unsubscribed or the app was removed
                dead.append(s["sub"]["endpoint"])
            else:
                log.warning("push failed (%s): %s", code, exc)
        except Exception as exc:
            log.warning("push failed: %s", exc)
    for endpoint in dead:
        unsubscribe(endpoint)
    if sent:
        log.info("push sent kind=%s session=%s count=%d", kind, session or "", sent)
    return sent


# ---------- watching sessions ----------

_WORKING_RE = re.compile(r"esc to interrupt", re.IGNORECASE)
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


class Watcher:
    """Polls agent sessions and turns state changes into notifications.

    working -> idle          : "done"    (the turn finished)
    anything -> prompt shown : "waiting" (a menu / permission prompt needs you)
    """

    def __init__(self, tm):
        self.tm = tm
        self.state: dict = {}  # name -> {"working": bool, "idle_polls": int, "prompt": str|None}

    def _pane(self, name: str) -> str:
        r = self.tm._run(["tmux", "capture-pane", "-p", "-t", name, "-S", "-15"], timeout=3)
        return _ANSI_RE.sub("", r.stdout or "") if r.returncode == 0 else ""

    def _seen_recently(self, name: str) -> bool:
        return time.time() - _presence.get(name, 0) < PRESENCE_SECONDS

    def _turn_activity(self, info: dict) -> Optional[dict]:
        """Read turn boundaries from the agent transcript.

        Claude's TUI status text changes between releases and may not include
        the old ``esc to interrupt`` marker. The transcript is the stable
        source: a turn is working while its latest user message is newer than
        the latest assistant text message.
        """
        kind = info.get("kind")
        if kind == "cc":
            jsonl = self.tm._claude_jsonl_for_pid(info.get("claude_pid"))
        elif kind == "codex":
            jsonl = self.tm._find_codex_jsonl(info.get("codex_pid"))
        else:
            return None
        if not jsonl or not jsonl.exists():
            return None
        try:
            with open(jsonl, "rb") as f:
                f.seek(0, 2)
                size = f.tell()
                f.seek(max(0, size - 512 * 1024))
                lines = f.read().decode("utf-8", errors="replace").splitlines()
        except OSError:
            return None

        latest_user = None
        latest_assistant = None
        latest_assistant_text = None
        last_tool_use = 0.0
        assistant_texts = []
        for line in lines:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("isSidechain"):
                continue
            ts = self.tm._parse_iso_ts(obj.get("timestamp"))
            if not ts:
                continue
            message = obj.get("message") or {}
            content = message.get("content")
            if obj.get("type") == "user":
                parts = []
                if isinstance(content, str):
                    parts.append(content)
                elif isinstance(content, list):
                    parts.extend(
                        block.get("text") or ""
                        for block in content
                        if isinstance(block, dict) and block.get("type") == "text"
                    )
                text = " ".join(parts).strip()
                if text and not text.startswith(("<command-", "<bash-", "<local-command-", "[Request interrupted")):
                    latest_user = ts
            elif obj.get("type") == "assistant":
                parts = []
                has_tool_use = False
                if isinstance(content, str):
                    parts.append(content)
                elif isinstance(content, list):
                    for block in content:
                        if not isinstance(block, dict):
                            continue
                        if block.get("type") == "tool_use":
                            has_tool_use = True
                        elif block.get("type") == "text":
                            parts.append(block.get("text") or "")
                text = " ".join(parts).strip()
                if has_tool_use:
                    last_tool_use = max(last_tool_use, ts)
                if text:
                    assistant_texts.append((ts, text))

        # Text accompanying a tool_use is a preamble, not a completed turn.
        # Prefer the latest text written after all tool calls in the transcript.
        for ts, text in reversed(assistant_texts):
            if ts > last_tool_use:
                latest_assistant = ts
                latest_assistant_text = re.sub(r"\s+", " ", text).strip()[:180]
                break

        if latest_user is None and latest_assistant is None:
            return None
        return {
            "user_ts": latest_user or 0.0,
            "assistant_ts": latest_assistant or 0.0,
            "assistant_text": latest_assistant_text or "",
            "working": bool(latest_user and (not latest_assistant or latest_user > latest_assistant)),
        }

    def tick(self) -> None:
        if not _load_subs():
            self.state.clear()
            return
        # Read-only probes (list_sessions() also archives and writes state files).
        alive = set()
        for raw in self.tm._tmux_sessions_raw():
            name = raw["name"]
            info = self.tm._pane_info(name) or {}
            kind = info.get("kind")
            if kind not in ("cc", "codex", "opencode"):
                continue
            alive.add(name)
            title = self.tm.get_chat_name(name) or self.tm.get_display_name(name) or name
            activity = self._turn_activity(info)
            working = activity["working"] if activity else bool(_WORKING_RE.search(self._pane(name)))
            prompt = None
            if not working and kind == "cc":
                p = self.tm.detect_terminal_prompt(name)
                if p and p.get("type") != "feedback":
                    prompt = p.get("label") or "需要你选择"
            prev = self.state.get(name)
            if prev is None:  # first sighting: learn the state, don't notify
                self.state[name] = {
                    "working": working,
                    "idle_polls": 0,
                    "prompt": prompt,
                    "user_ts": activity["user_ts"] if activity else 0.0,
                    "assistant_ts": activity["assistant_ts"] if activity else 0.0,
                }
                continue
            if prompt and prompt != prev["prompt"] and not self._seen_recently(name):
                send(f"{title} 在等你", prompt, kind="waiting", session=name)
            if activity:
                user_ts = activity["user_ts"]
                assistant_ts = activity["assistant_ts"]
                new_user = user_ts > (prev.get("user_ts") or 0.0)
                new_assistant = assistant_ts > (prev.get("assistant_ts") or 0.0)
                prev["user_ts"] = user_ts
                prev["assistant_ts"] = assistant_ts
                if new_user and assistant_ts > user_ts:
                    if not prompt and not self._seen_recently(name):
                        send(
                            f"{title} 做完了",
                            activity["assistant_text"] or "这一轮做完了",
                            kind="done",
                            session=name,
                        )
                    prev["working"] = False
                    prev["idle_polls"] = 0
                elif new_assistant and prev["working"] and not prompt and not self._seen_recently(name):
                    send(
                        f"{title} 做完了",
                        activity["assistant_text"] or "这一轮做完了",
                        kind="done",
                        session=name,
                    )
                    prev["working"] = False
                    prev["idle_polls"] = 0
                else:
                    prev["working"] = working
                    prev["idle_polls"] = 0
            elif working:
                prev["idle_polls"] = 0
                prev["working"] = True
            elif prev["working"]:
                # Debounce: the spinner line can blink off between tool calls.
                prev["idle_polls"] += 1
                if prev["idle_polls"] >= 2:
                    prev["working"] = False
                    prev["idle_polls"] = 0
                    if not prompt and not self._seen_recently(name):
                        summary = (self.tm._session_activity(name, info)[0] or "这一轮做完了").strip()
                        send(f"{title} 做完了", summary, kind="done", session=name)
            prev["prompt"] = prompt
        for gone in set(self.state) - alive:
            self.state.pop(gone, None)

    def run_forever(self) -> None:
        while True:
            try:
                self.tick()
            except Exception as exc:
                log.warning("push watcher error: %s", exc)
            time.sleep(POLL_SECONDS)


def start_watcher(tm) -> None:
    if not AVAILABLE:
        log.warning("pywebpush not installed; push notifications are off")
        return
    if os.environ.get("PUSH_DISABLED") == "1":
        return
    threading.Thread(target=Watcher(tm).run_forever, name="push-watcher", daemon=True).start()
