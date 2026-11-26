import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import urllib.error
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("openrouter_experiment", ROOT / "run.py")
experiment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(experiment)


class Response:
    status = 200

    def __init__(self, content, finish="stop"):
        self.payload = {"choices": [{"finish_reason": finish,
                                     "message": {"content": content}}]}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


class OpenRouterTests(unittest.TestCase):
    def test_strict_actor_and_mutation_schema_are_distinct(self):
        actor = experiment.response_format('parent-selection', {})
        mutation = experiment.response_format('constitution_mutation', {})
        self.assertEqual(actor['type'], 'json_schema')
        self.assertTrue(actor['json_schema']['strict'])
        self.assertEqual(actor['json_schema']['schema']['required'], ['actions', 'explanation'])
        self.assertEqual(mutation['json_schema']['schema']['required'], ['name', 'rules'])
        self.assertFalse(actor['json_schema']['schema']['additionalProperties'])

    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-only"})
    def test_cache_and_usage_survive_restart(self):
        with tempfile.TemporaryDirectory() as temp:
            journal = experiment.Journal(Path(temp) / "events.jsonl")
            model = experiment.Model("test", journal, 10)
            response = Response('{"ok": true}')
            response.payload['usage'] = {'cost': .25}
            with patch.object(experiment.urllib.request, 'urlopen', return_value=response) as http:
                self.assertEqual(model.complete([], 1, 'decision'), {'ok': True})
                resumed = experiment.Model('test', journal, 10)
                self.assertEqual(resumed.calls, 1)
                self.assertEqual(resumed.cost, .25)
                self.assertEqual(resumed.complete([], 1, 'another-folder'), {'ok': True})
                self.assertEqual(http.call_count, 1)

    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-only"})
    def test_transient_retry_and_permanent_auth_failure(self):
        for status, expected in ((429, 2), (401, 1)):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as temp:
                model = experiment.Model('test', experiment.Journal(Path(temp) / 'events.jsonl'), 10)
                error = urllib.error.HTTPError('https://example.invalid', status, 'test', {}, None)
                with patch.object(experiment.urllib.request, 'urlopen', side_effect=[error, Response('{"ok": true}')]) as http, patch.object(experiment.time, 'sleep'):
                    if status == 401:
                        with self.assertRaises(urllib.error.HTTPError):
                            model.complete([], 1, 'decision')
                    else:
                        self.assertEqual(model.complete([], 1, 'decision'), {'ok': True})
                    self.assertEqual(http.call_count, expected)

    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-only"})
    def test_spending_limit_stops_next_request(self):
        with tempfile.TemporaryDirectory() as temp:
            model = experiment.Model('test', experiment.Journal(Path(temp) / 'events.jsonl'), 10, {'max_cost_usd': .1})
            response = Response('{"ok": true}')
            response.payload['usage'] = {'cost': .1}
            with patch.object(experiment.urllib.request, 'urlopen', return_value=response) as http:
                model.complete([], 1, 'decision')
                with self.assertRaisesRegex(RuntimeError, 'spending budget'):
                    model.complete([], 2, 'decision')
                self.assertEqual(http.call_count, 1)

    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-only"})
    def test_truncated_reasoning_retries_without_becoming_an_action(self):
        with tempfile.TemporaryDirectory() as temp:
            journal = experiment.Journal(Path(temp) / "events.jsonl")
            model = experiment.Model("test", journal, 10)
            with patch.object(experiment.urllib.request, "urlopen", side_effect=[
                Response(None, "length"), Response('{"actions": []}')
            ]) as http:
                self.assertEqual(model.complete([], 1, "decision"), {"actions": []})
            bodies = [json.loads(call.args[0].data) for call in http.call_args_list]
            self.assertEqual([b["max_tokens"] for b in bodies], [4096, 8192])
            self.assertEqual(bodies[0]["reasoning"], {"effort": "low"})
            events = [json.loads(x) for x in journal.path.read_text().splitlines()]
            self.assertEqual(sum(e["event"] == "model_response" for e in events), 2)
            self.assertEqual(sum(e["event"] == "model_retry" for e in events), 1)

    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-only"})
    def test_retry_obeys_call_budget(self):
        with tempfile.TemporaryDirectory() as temp:
            model = experiment.Model("test", experiment.Journal(Path(temp) / "events.jsonl"), 1)
            with patch.object(experiment.urllib.request, "urlopen", return_value=Response(None, "length")) as http:
                with self.assertRaisesRegex(RuntimeError, "budget exhausted"):
                    model.complete([], 1, "decision")
            self.assertEqual(http.call_count, 1)

    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-only"})
    def test_empty_nontruncated_response_fails_explicitly(self):
        with tempfile.TemporaryDirectory() as temp:
            model = experiment.Model("test", experiment.Journal(Path(temp) / "events.jsonl"), 4)
            with patch.object(experiment.urllib.request, "urlopen", return_value=Response(None)):
                with self.assertRaisesRegex(ValueError, "no JSON content"):
                    model.complete([], 1, "decision")


if __name__ == "__main__":
    unittest.main()
