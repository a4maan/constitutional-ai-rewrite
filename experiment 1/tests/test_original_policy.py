import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("original_policy_test", ROOT / "run.py")
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)


class FakeModel:
    def __init__(self, answer):
        self.answer = answer
        self.requests = []

    def complete(self, messages, seed, purpose):
        self.requests.append(messages)
        return self.answer


class OriginalPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.journal = pilot.Journal(Path(self.temp.name) / "events.jsonl")
        self.rules = {"name": "test", "rules": ["Cooperate."]}

    def test_original_role_prompt_memory_and_action_categories(self):
        model = FakeModel({"actions": [{"kind": "contribute", "amount": 60},
            {"kind": "private_message", "recipient": "Blue2", "message": "hello"}], "explanation": "contribute and communicate"})
        policy = pilot.policy_for(model, self.rules, 42, "test", self.journal)
        game = pilot.Game()
        actions = policy(game.observe("Blue1"))
        self.assertEqual([a.kind for a in actions], ["contribute", "private_message"])
        game.step({"Blue1": actions})
        policy(game.observe("Blue1"))
        payload = json.loads(model.requests[1][1]["content"])
        self.assertTrue(payload["resident_memory_snapshot"])
        self.assertNotIn("players", payload["observation"])
        self.assertIn("MAXIMISE GROUP WELFARE", model.requests[0][0]["content"])

    def test_red_original_and_neutral_prompt_modes_are_explicit(self):
        model = FakeModel({"actions": [], "explanation": "rest"})
        for mode in ("original", "neutral"):
            policy = pilot.policy_for(model, self.rules, 42, "test", self.journal,
                                     faction="Red", role_prompts=mode)
            policy(pilot.Game().observe("Red1"))
            self.assertEqual("EXPLOIT cooperators" in model.requests[-1][0]["content"], mode == "original")

    def test_malformed_decision_fails_without_substituting_rest(self):
        policy = pilot.policy_for(FakeModel({"actions": [{"kind": "contribute", "amount": "bad"}],
                                            "explanation": "invalid"}), self.rules, 42, "test", self.journal)
        with self.assertRaisesRegex(ValueError, "3 validation attempts"):
            policy(pilot.Game().observe("Blue1"))
        events = self.journal.path.read_text()
        self.assertEqual(events.count('"event": "response_invalid"'), 3)
        self.assertNotIn("decision_rest_fallback", events)

    def test_wrapped_final_string_and_object_are_unwrapped(self):
        valid = {"actions": [{"kind": "contribute", "amount": 64}], "explanation": "cooperate"}
        for value in (valid, json.dumps(valid)):
            policy = pilot.policy_for(FakeModel({"final": value}), self.rules, 42, "test", self.journal)
            self.assertEqual(policy(pilot.Game().observe("Blue1"))[0].amount, 64)
        self.assertIn("response_unwrapped", self.journal.path.read_text())

    def test_invalid_response_is_retried_before_a_decision_is_applied(self):
        class SequenceModel:
            calls = 0
            def complete(self, messages, seed, purpose):
                self.calls += 1
                if self.calls == 1:
                    return {'final{': 'explanation'}
                return {'actions': [{'kind': 'contribute', 'amount': 60}], 'explanation': 'valid'}
        model = SequenceModel()
        game = pilot.Game()
        policy = pilot.policy_for(model, self.rules, 42, 'test', self.journal)
        actions = policy(game.observe('Blue1'))
        self.assertEqual(model.calls, 2)
        self.assertEqual(actions[0].amount, 60)
        game.step({'Blue1': actions})
        self.assertEqual(game.export()['history'][0]['contributions']['Blue1'], 60)
        events = [json.loads(x) for x in self.journal.path.read_text().splitlines()]
        self.assertEqual(sum(x['event']=='policy_decision' for x in events), 1)

    def test_invalid_actions_never_change_state(self):
        game = pilot.Game()
        before = game.export()
        invalid = [
            [{"kind": "contribute", "amount": -1}],
            [{"kind": "contribute", "amount": True}],
            [{"kind": "contribute", "amount": float('nan')}],
            [{"kind": "punish", "amount": 10, "target": "Blue1"}],
            [{"kind": "punish", "amount": 10, "target": "Unknown"}],
            [{"kind": "private_message", "recipient": "Unknown", "message": "hello"}],
            [{"kind": "unknown"}],
            [{"kind": "contribute", "amount": 10}, {"kind": "rest"}],
            [{"kind": "rest", "extra": 2}],
        ]
        for actions in invalid:
            with self.subTest(actions=actions):
                with self.assertRaises((ValueError, TypeError)):
                    pilot.original_actions({"actions": actions, "explanation": "x"}, game.observe("Blue1"))
                self.assertEqual(game.export(), before)

    def test_model_boundary_hides_all_team_fields(self):
        model = FakeModel({"actions": [], "explanation": "wait"})
        policy = pilot.policy_for(model, self.rules, 42, "test", self.journal,
                                 faction="Red", role_prompts="neutral", reveal_factions=False)
        policy(pilot.Game().observe("Red1"))
        payload = json.loads(model.requests[0][1]["content"])
        self.assertNotIn("team_id", payload["observation"])
        self.assertTrue(all("team" not in row for row in payload["observation"]["residents"]))
        self.assertNotIn("EXPLOIT cooperators", model.requests[0][0]["content"])

    def test_compaction_preserves_original_information_boundary(self):
        game = pilot.Game()
        game.step({"Red1": pilot.Action("private_message", recipient="Red2", message="secret")})
        obs = game.observe("Blue1")
        compact = pilot.compact_observation(obs)
        self.assertEqual(compact, obs)
        self.assertNotIn("secret", json.dumps(compact))


if __name__ == "__main__":
    unittest.main()
