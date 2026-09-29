import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tools = load_module("send_tool_usage", ROOT / "deploy/claude-hooks/send_tool_usage.py")
installer = load_module("install_telegram_tool_hook", ROOT / "deploy/install-telegram-tool-hook.py")


def channel_turn(turn_id="turn-1", chat_id="123", user_id="123"):
    return {
        "type": "user", "isMeta": True, "uuid": turn_id,
        "message": {"content": (
            f'<channel source="telegram" chat_id="{chat_id}" '
            f'user_id="{user_id}">message</channel>'
        )},
    }


def tool_use(name, tool_id, secret="private-key"):
    return {
        "type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": name, "id": tool_id,
             "input": {"command": secret}},
        ]},
    }


class TelegramToolUsageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.transcript = self.root / "session.jsonl"
        self.access = self.root / "access.json"
        self.access.write_text(json.dumps({"allowFrom": ["123"]}), encoding="utf-8")
        self.sent = []

    def write_events(self, *events):
        self.transcript.write_text(
            "\n".join(json.dumps(event) for event in events) + "\n", encoding="utf-8",
        )

    def process(self):
        return tools.process_hook(
            {"transcript_path": str(self.transcript), "session_id": "session"},
            "test-token", self.access, self.root / "state",
            lambda *args: self.sent.append(args),
        )

    def test_sends_only_unique_non_transport_tools_once(self):
        self.write_events(
            channel_turn(), tool_use("Bash", "tool-1"),
            {"type": "user", "message": {"content": [
                {"type": "tool_result", "tool_use_id": "tool-1", "content": "private output"},
            ]}},
            tool_use("Bash", "tool-1"),
            tool_use("mcp__plugin_telegram_telegram__reply", "tool-2"),
            tool_use("Read", "tool-3"),
        )
        self.assertTrue(self.process())
        self.assertFalse(self.process())
        self.assertEqual(len(self.sent), 1)
        _, chat_id, body = self.sent[0]
        self.assertEqual(chat_id, "123")
        self.assertIn("工具使用（2 次）", body)
        self.assertIn("<blockquote expandable>", body)
        self.assertIn("Bash ×1", body)
        self.assertIn("Read ×1", body)
        self.assertNotIn("private-key", body)
        self.assertNotIn("private output", body)
        self.assertNotIn("telegram__reply", body)

    def test_new_turn_is_not_suppressed(self):
        self.write_events(channel_turn(), tool_use("Bash", "tool-1"))
        self.assertTrue(self.process())
        self.write_events(
            channel_turn(), tool_use("Bash", "tool-1"),
            channel_turn("turn-2"), tool_use("Read", "tool-2"),
        )
        self.assertTrue(self.process())
        self.assertEqual(len(self.sent), 2)
        self.assertIn("Read ×1", self.sent[-1][2])

    def test_does_not_send_for_other_user_or_unpaired_chat(self):
        self.write_events(
            channel_turn(), tool_use("Bash", "tool-1"),
            {"type": "user", "message": {"content": "frontend message"}},
            tool_use("Read", "tool-2"),
        )
        self.assertFalse(self.process())
        self.write_events(channel_turn(chat_id="456", user_id="456"),
                          tool_use("Bash", "tool-3"))
        self.assertFalse(self.process())
        self.write_events(channel_turn(chat_id="123", user_id="456"),
                          tool_use("Bash", "tool-4"))
        self.assertFalse(self.process())

    def test_ignores_untrusted_or_toolless_turns(self):
        self.write_events(
            {**channel_turn(), "isMeta": False}, tool_use("Bash", "tool-1"),
        )
        self.assertFalse(self.process())
        self.write_events(channel_turn())
        self.assertFalse(self.process())


class InstallerTests(unittest.TestCase):
    def test_preserves_settings_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = Path(directory) / "settings.json"
            original = {"model": "claude-opus-4-6", "hooks": {"Stop": [
                {"hooks": [{"type": "command", "command": "existing-hook"}]},
            ]}}
            settings.write_text(json.dumps(original), encoding="utf-8")
            backup = installer.install(settings)
            self.assertIsNotNone(backup)
            self.assertEqual(json.loads(backup.read_text()), original)
            updated = json.loads(settings.read_text())
            self.assertEqual(updated["model"], original["model"])
            self.assertEqual(updated["hooks"]["Stop"][0], original["hooks"]["Stop"][0])
            self.assertEqual(updated["hooks"]["Stop"][1], installer.HOOK)
            self.assertIsNone(installer.install(settings))
            self.assertEqual(len(list(Path(directory).glob("*.before-telegram-tools-*"))), 1)


if __name__ == "__main__":
    unittest.main()
