import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parents[0] / "pgg"))
from groq_model import GroqModel, compact_observation
from pgg import Game, Action, Config


class SilentJournal:
    def __init__(self, path):
        self.path = path
        self.events = []

    def event(self, kind, **values):
        self.events.append((kind, values))


class GroqTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        keys = self.root / "keys.json"
        keys.write_text(json.dumps(["test-account-one", "test-account-two"]))
        self.env = patch.dict(os.environ, {"GROQ_KEYS_FILE": str(keys)})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.settings = {"rate_limits": {"requests_per_minute": 2, "requests_per_day": 3,
                                        "tokens_per_minute": 100, "tokens_per_day": 150}}
        self.model = GroqModel("model", SilentJournal(self.root / "events.jsonl"), 100, self.settings)

    def test_independent_accounts_reserve_without_sharing_quota(self):
        with patch("groq_model.time.time", return_value=1000):
            _, first = self.model.reserve(80)
            _, second = self.model.reserve(80)
            self.assertNotEqual(first["label"], second["label"])

    def test_both_accounts_wait_for_minute_reset(self):
        clock = [1000.0]
        def wait(seconds, reason):
            clock[0] += seconds
        with patch("groq_model.time.time", side_effect=lambda: clock[0]), patch.object(self.model, "wait", side_effect=wait):
            self.model.reserve(80)
            self.model.reserve(80)
            self.model.reserve(60)
            self.assertGreaterEqual(clock[0], 1061)

    def test_daily_token_budget_waits_and_is_persisted(self):
        clock = [1000.0]
        def wait(seconds, reason):
            clock[0] += seconds
        with patch("groq_model.time.time", side_effect=lambda: clock[0]), patch.object(self.model, "wait", side_effect=wait):
            for account in self.model.accounts:
                account["ledger"] = [{"time": 900, "tokens": 140}]
            self.model.reserve(20)
            self.assertGreaterEqual(clock[0], 900 + 86401)
            self.assertTrue(any(a["path"].exists() for a in self.model.accounts))

    def test_large_single_request_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "exceeding"):
            self.model.reserve(101)

    def test_response_cache_avoids_network(self):
        import hashlib
        body = {"model": "model", "messages": [], "temperature": 1, "seed": 42,
                "max_completion_tokens": 700, "reasoning_effort": "low",
                "response_format": {"type": "json_object"}}
        key = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        (self.model.cache / (key + ".json")).write_text('{"answer":{"cached":true}}')
        with patch("urllib.request.urlopen", side_effect=AssertionError("network called")):
            self.assertEqual(self.model.complete([], 42, "test"), {"cached": True})

    def test_full_history_and_exact_wallets_survive_compaction(self):
        game = Game(Config(design="revised"))
        game.step({"blue_1": Action("broadcast", message="hello")})
        obs = game.observe("blue_1")
        compact = compact_observation(obs)
        self.assertEqual(len(compact["history"]), len(obs["history"]))
        self.assertEqual(compact["history"][0]["actions"][0], {"kind": "broadcast", "message": "hello"})
        self.assertEqual(compact["history"][0]["ending_wallets"], list(game.wallets.values()))
        self.assertEqual(compact["initial_wallets"], [100] * 6)


if __name__ == "__main__":
    unittest.main()
