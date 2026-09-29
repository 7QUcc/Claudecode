import unittest

from deploy.telegram_context import context_message


class FakeManager:
    def __init__(self, holder="keke", usage=None):
        self.holder = holder
        self.usage = usage

    def telegram_status(self):
        return {"holder": self.holder}

    def _pane_info(self, name):
        return {"claude_pid": 123} if name == self.holder else None

    def _claude_jsonl_for_pid(self, pid):
        return "session.jsonl" if pid == 123 else None

    def _read_last_usage(self, jsonl):
        return self.usage if jsonl == "session.jsonl" else None


class ContextMessageTests(unittest.TestCase):
    def test_no_connected_session(self):
        self.assertIn("没有连接", context_message(FakeManager(holder=None)))

    def test_no_usage_yet(self):
        self.assertIn("暂无上下文用量", context_message(FakeManager()))

    def test_uses_reported_model_and_window(self):
        usage = {"model": "claude-opus-4-6", "tokens": 33139,
                 "window": 200000, "pct": 16.57, "ts": None}
        message = context_message(FakeManager(usage=usage))
        self.assertIn("keke · claude-opus-4-6", message)
        self.assertIn("33,139 / 200,000（16.6%）", message)

    def test_one_million_token_window(self):
        usage = {"model": "claude-opus-4-6[1m]", "tokens": 250000,
                 "window": 1000000, "pct": 25.0, "ts": None}
        self.assertIn("250,000 / 1,000,000（25.0%）",
                      context_message(FakeManager(usage=usage)))


if __name__ == "__main__":
    unittest.main()
