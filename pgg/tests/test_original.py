"""Compare active old-design mechanics with the commit-pinned original engine."""
import copy
import json
from pathlib import Path
import random
import sys
import unittest

from pgg import Action, Config, Game
from pgg.replay import replay
from pgg.runner import run

REFERENCE = Path(__file__).resolve().parents[1] / "reference/cons-race/upstream/src"
sys.path.insert(0, str(REFERENCE))
from environment.pgg import PublicGoodsEnvironment, PGGSettings, PGGActionRequest, PGGActionType
from environment.game import AgentSpawn
from experiments.pgg_scoring import compute_pgg_stability


class OriginalTests(unittest.TestCase):
    def pair(self, endowment=100):
        active = Game(Config(endowment=endowment))
        reference = PublicGoodsEnvironment(PGGSettings(initial_endowment=endowment))
        reference.reset([AgentSpawn(a.name, "cooperators" if a.faction == "Blue" else "free_riders",
                                    faction=a.faction.lower()) for a in active.agents])
        return active, reference

    def check_round(self, active, reference, choices):
        mapping = {"contribute": "CONTRIBUTE", "punish": "PUNISH", "rest": "REST",
                   "broadcast": "COMMUNICATE", "private_message": "SEND_PRIVATE_MESSAGE"}
        converted = {}
        for name, value in choices.items():
            values = [value] if isinstance(value, Action) else value
            converted[name] = [PGGActionRequest(PGGActionType(mapping[a.kind]),
                {"amount": a.amount, "target": a.target or "", "message": a.message,
                 "recipient": a.recipient or ""}) for a in values]
        observations = reference.step(converted)
        record = active.step(choices)
        self.assertEqual(dict(active.wallets), reference._wallets)
        self.assertEqual(record["events"], reference.turn_log[-1].events)
        for agent in active.agents:
            self.assertEqual(active.observe(agent.name), observations[agent.name])
        score = compute_pgg_stability(reference)
        for faction in ("Blue", "Red"):
            self.assertEqual(active.scores()[faction]["raw_score"], score.faction_scores[faction.lower()].S)
        return record

    def test_default_is_original_and_zero_based(self):
        game = Game()
        self.assertEqual(game.config.design, "original")
        self.assertEqual(game.agents[0].name, "Blue1")
        self.assertEqual(game.observe("Blue1")["round"], 0)

    def test_seeded_full_games_match_wallets_observations_events_scores(self):
        for seed in range(5):
            with self.subTest(seed=seed):
                active, reference = self.pair()
                rng = random.Random(seed)
                names = [a.name for a in active.agents]
                for turn in range(20):
                    choices = {}
                    for name in names:
                        physical = (Action("contribute", amount=rng.random() * active.wallets[name])
                                    if rng.random() < .7 else Action("punish", target=rng.choice(names), amount=rng.random() * 50))
                        choices[name] = [physical, (Action("broadcast", message=f"round {turn}")
                            if rng.random() < .5 else Action("private_message", recipient=rng.choice(names), message="hello"))]
                    self.check_round(active, reference, choices)

    def test_contribution_clamping_and_no_100_unit_engine_cap(self):
        active, reference = self.pair()
        self.check_round(active, reference, {a.name: Action("contribute", amount=1000) for a in active.agents})
        record = self.check_round(active, reference, {"Blue1": Action("contribute", amount=1000),
                                                     "Blue2": Action("contribute", amount=-10)})
        self.assertEqual(record["contributions"]["Blue1"], 150)
        self.assertEqual(record["contributions"]["Blue2"], 0)

    def test_punishment_order(self):
        active, reference = self.pair()
        self.check_round(active, reference, {f"Blue{i}": Action("punish", target="Red1", amount=30) for i in range(1, 4)})
        record = self.check_round(active, reference, {"Blue1": Action("punish", target="Red1", amount=10),
                                                     "Red1": Action("punish", target="Blue1", amount=10)})
        self.assertEqual(active.wallets["Blue1"], 88)
        self.assertFalse(record["punishment_outcomes"][-1]["accepted"])

    def test_pool_returns_can_fund_punishment(self):
        active, reference = self.pair()
        self.check_round(active, reference, {"Red1": Action("punish", target="Blue1", amount=49),
                                             "Red2": Action("punish", target="Blue1", amount=50)})
        record = self.check_round(active, reference, {"Blue1": Action("punish", target="Red1", amount=10),
            **{a.name: Action("contribute", amount=100) for a in active.agents if a.name != "Blue1"}})
        self.assertEqual(record["punishment_costs"]["Blue1"], 3)

    def test_message_and_contribution_same_round_private_visibility(self):
        active, reference = self.pair()
        self.check_round(active, reference, {"Blue1": [Action("contribute", amount=60),
            Action("private_message", recipient="Blue2", message="secret")]})
        self.assertEqual(active.observe("Blue2")["private_messages"], ["[PM from Blue1]: secret"])
        self.assertEqual(active.observe("Red1")["private_messages"], [])
        self.assertEqual(active.wallets["Blue1"], 55)

    def test_history_window_and_wallet_privacy(self):
        active, reference = self.pair()
        for _ in range(6):
            self.check_round(active, reference, {})
        observation = active.observe("Blue1")
        self.assertEqual(len(observation["round_history"]), 5)
        self.assertNotIn("wallet", observation["residents"][1])
        self.assertNotIn("history", observation)

    def test_message_caps_and_inbox_retention(self):
        active, reference = self.pair()
        for _ in range(12):
            self.check_round(active, reference, {"Blue1": Action("broadcast", message="x" * 600)})
        self.assertEqual(len(active.observe("Red1")["public_messages"]), 10)
        self.assertEqual(len(active.observe("Red1")["public_messages"][0]), len("[Blue1]: ") + 512)

    def test_threshold_scales_with_initial_endowment(self):
        active, reference = self.pair(endowment=200)
        self.check_round(active, reference, {a.name: Action("contribute", amount=15) for a in active.agents})
        self.assertEqual(active.scores()["Blue"]["free_riding_rate"], 1)

    def test_unknown_self_unaffordable_punishments_skipped(self):
        active, reference = self.pair()
        record = self.check_round(active, reference, {"Blue1": [Action("punish", target="Blue1", amount=1),
            Action("punish", target="absent", amount=1), Action("punish", target="Red1", amount=1000)]})
        self.assertEqual(len(record["punishment_outcomes"]), 3)
        self.assertTrue(all(not row["accepted"] for row in record["punishment_outcomes"]))

    def test_zero_contributions_communication_counts_as_free_riding(self):
        active, reference = self.pair()
        self.check_round(active, reference, {"Blue1": Action("broadcast", message="hello")})
        self.assertEqual(active.scores()["Blue"]["free_riding_rate"], 1)

    def test_reset_clears_private_and_public_history(self):
        game = Game()
        game.step({"Blue1": [Action("broadcast", message="public"), Action("private_message", recipient="Blue2", message="private")]})
        game.reset()
        self.assertEqual(game.observe("Blue2")["private_messages"], [])
        self.assertEqual(game.observe("Blue2")["public_messages"], [])
        self.assertEqual(game.history, [])

    def test_replay_multi_actions_and_tamper_detection(self):
        game = Game(Config(rounds=2))
        trace = run(game, {a.name: lambda obs: [Action("contribute", amount=60),
            Action("private_message", recipient="Blue2", message="hello")] for a in game.agents})
        self.assertEqual(trace["trace_version"], 2)
        self.assertEqual(replay(json.loads(json.dumps(trace))), game.export())
        altered = copy.deepcopy(trace)
        altered["history"][0]["actions"]["Blue1"][1]["message"] = "changed"
        with self.assertRaisesRegex(ValueError, "action"):
            replay(altered)

    def test_round_limit(self):
        game = Game(Config(rounds=1))
        game.step({})
        with self.assertRaises(RuntimeError):
            game.step({})

    def test_old_unversioned_revised_log_still_replays(self):
        game = Game(Config(design="revised", rounds=1))
        game.step({})
        trace = game.export()
        for key in ("design", "free_rider_fraction", "resident_role_prompts"):
            trace["config"].pop(key)
        for action in trace["history"][0]["actions"].values():
            action.pop("recipient")
        self.assertEqual(replay(trace)["rounds_played"], 1)


if __name__ == "__main__":
    unittest.main()
