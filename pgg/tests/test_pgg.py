import json
import math
import tempfile
import unittest
from pathlib import Path
import subprocess
import sys

from pgg import Action, Agent, Config, Game
from pgg.runner import fixed_contribution, random_policy, run


class PGGTests(unittest.TestCase):
    def test_01_default_setup(self):
        game = Game()
        self.assertEqual(len(game.agents), 6)
        self.assertEqual([a.faction for a in game.agents].count("Blue"), 3)
        self.assertEqual(sum(game.wallets.values()), 600)
        self.assertEqual(game.config.rounds, 20)
        self.assertIsNone(game.scores()["Blue"]["raw_score"])

    def test_02_full_cooperation_pool_and_payout(self):
        game = Game()
        record = game.step({a.name: Action("contribute", fraction=1) for a in game.agents})
        self.assertEqual(record["pool"], 600)
        self.assertEqual(record["payout_per_agent"], 150)
        self.assertTrue(all(w == 150 for w in game.wallets.values()))

    def test_03_wallets_persist_and_percent_uses_current_balance(self):
        game = Game()
        choices = {a.name: Action("contribute", fraction=1) for a in game.agents}
        game.step(choices)
        record = game.step(choices)
        self.assertEqual(record["contributions"]["blue_1"], 150)
        self.assertEqual(game.wallets["blue_1"], 225)

    def test_04_free_rider_receives_equal_pool_share(self):
        game = Game()
        game.step({"blue_1": Action("contribute", fraction=1)})
        self.assertEqual(game.wallets["blue_1"], 25)
        self.assertEqual(game.wallets["red_1"], 125)

    def test_05_rest_preserves_money_and_counts_free_riding(self):
        game = Game()
        game.step({})
        self.assertEqual(sum(game.wallets.values()), 600)
        self.assertAlmostEqual(game.scores()["Blue"]["raw_score"], 0.1)
        self.assertEqual(game.scores()["Blue"]["free_riding_rate"], 1)

    def test_06_punishment_cost_and_damage(self):
        game = Game()
        record = game.step({"blue_1": Action("punish", target="red_1", amount=10)})
        self.assertEqual(game.wallets["blue_1"], 97)
        self.assertEqual(game.wallets["red_1"], 90)
        self.assertEqual(record["punishment_costs"]["blue_1"], 3)

    def test_07_mutual_punishments_are_simultaneous(self):
        game = Game()
        game.step({"blue_1": Action("punish", target="red_1", amount=100),
                   "red_1": Action("punish", target="blue_1", amount=100)})
        self.assertEqual(game.wallets["blue_1"], 0)
        self.assertEqual(game.wallets["red_1"], 0)

    def test_08_many_attackers_cannot_make_wallet_negative(self):
        game = Game()
        record = game.step({"blue_1": Action("punish", target="red_1", amount=100),
                            "blue_2": Action("punish", target="red_1", amount=100)})
        self.assertEqual(record["punishment_requested"]["red_1"], 200)
        self.assertEqual(record["punishment_damage"]["red_1"], 100)
        self.assertEqual(game.wallets["blue_1"], 70)
        self.assertEqual(game.wallets["blue_2"], 70)

    def test_09_payout_precedes_punishment(self):
        game = Game()
        game.step({"blue_1": Action("contribute", fraction=1),
                   "red_1": Action("punish", target="blue_1", amount=10)})
        self.assertEqual(game.wallets["blue_1"], 15)
        self.assertEqual(game.wallets["red_1"], 122)

    def test_10_broadcast_observation_and_no_current_action_leak(self):
        game = Game()
        observed = []
        def policy(obs):
            observed.append(obs)
            return Action("broadcast", message="cooperate")
        run(game, {a.name: policy for a in game.agents})
        self.assertTrue(all(o["history"] == [] for o in observed[:6]))
        self.assertEqual(len(observed[6]["history"][0]["messages"]), 6)
        self.assertNotIn("faction", observed[0]["players"][0])
        visible = Game(Config(reveal_factions=True))
        self.assertEqual(visible.observe("blue_1")["players"][0]["faction"], "Blue")
        self.assertEqual(sum(game.wallets.values()), 600)

    def test_11_free_rider_threshold_is_strict_and_absolute(self):
        game = Game(Config(rounds=1))
        game.step({"blue_1": Action("contribute", fraction=.1),
                   "blue_2": Action("contribute", fraction=.099),
                   "blue_3": Action("contribute", fraction=.5)})
        self.assertAlmostEqual(game.scores()["Blue"]["free_riding_rate"], 1/3)
        self.assertAlmostEqual(game.scores()["Blue"]["contribution_total"], 69.9)

    def test_12_score_uses_configured_rounds_and_played_rounds(self):
        game = Game(Config(rounds=20))
        game.step({a.name: Action("contribute", fraction=.5) for a in game.agents if a.faction == "Blue"})
        score = game.scores()["Blue"]
        self.assertEqual(score["contribution_utilization"], .025)
        self.assertEqual(score["free_riding_rate"], 0)
        self.assertAlmostEqual(score["raw_score"], .3125)

    def test_13_score_cap_retains_uncapped_utilization(self):
        game = Game(Config(rounds=2))
        run(game, {a.name: fixed_contribution(1) for a in game.agents})
        score = game.scores()["Blue"]
        self.assertEqual(score["utilization_uncapped"], 1.25)
        self.assertEqual(score["contribution_utilization"], 1)
        self.assertEqual(score["raw_score"], .8)

    def test_14_fitness_modes_and_same_snapshot_antisymmetry(self):
        game = Game(Config(rounds=1))
        game.step({a.name: Action("contribute", fraction=1) for a in game.agents if a.faction == "Blue"})
        self.assertAlmostEqual(game.fitness("Blue"), .8)
        self.assertAlmostEqual(game.fitness("Red"), .1)
        self.assertAlmostEqual(game.fitness("Blue", "advantage"), .7)
        self.assertAlmostEqual(game.fitness("Blue", "advantage"), -game.fitness("Red", "advantage"))
        self.assertAlmostEqual(game.fitness("Red", "pure_adversary"), .2)
        with self.assertRaises(ValueError):
            game.fitness("Blue", "unknown")

    def test_15_exact_episode_length_and_reset(self):
        game = Game()
        for _ in range(20):
            game.step({})
        self.assertTrue(game.done)
        with self.assertRaises(RuntimeError):
            game.step({})
        game.reset()
        self.assertEqual(game.round, 0)
        self.assertFalse(game.done)
        self.assertEqual(sum(game.wallets.values()), 600)
        self.assertEqual(game.scores()["Blue"]["contribution_total"], 0)
        with self.assertRaises(ValueError):
            game.fitness("Blue")

    def test_16_invalid_actions_reject_entire_round(self):
        bad = [Action("unknown"), Action("contribute", fraction=-.1),
               Action("contribute", fraction=1.01), Action("contribute", fraction=float("nan")),
               Action("contribute", fraction=float("inf")), Action("contribute", fraction=True),
               Action("punish", target="blue_1", amount=10),
               Action("punish", target="missing", amount=10),
               Action("punish", target="red_1", amount=-1),
               Action("punish", target="red_1", amount=334),
               Action("rest", fraction=.2), Action("rest", amount=10),
               Action("rest", message="extra"), Action("broadcast", message=42), "not an action"]
        for action in bad:
            with self.subTest(action=action):
                game = Game()
                before = game.export()
                with self.assertRaises(ValueError):
                    game.step({"blue_2": Action("contribute", fraction=1), "blue_1": action})
                self.assertEqual(game.export(), before)
        with self.assertRaises(ValueError):
            Game().step({"unknown": Action()})

    def test_17_configuration_roster_and_action_schema_validation(self):
        for kwargs in ({"rounds": 0}, {"rounds": True}, {"rounds": 1.5},
                       {"endowment": 0}, {"multiplier": -1}, {"punishment_cost": 0},
                       {"free_rider_threshold": -1}, {"endowment": float("inf")}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                Config(**kwargs)
        with self.assertRaises(ValueError):
            Game(agents=[])
        with self.assertRaises(ValueError):
            Game(agents=[Agent("same", "Blue"), Agent("same", "Red")])
        with self.assertRaises(ValueError):
            Action.from_dict({"kind": "rest", "extra": 2})
        self.assertEqual(Action.from_dict({"kind": "contribute", "fraction": .6}), Action("contribute", fraction=.6))

    def test_18_order_independence_and_protected_state(self):
        choices = {"blue_1": Action("contribute", fraction=.3),
                   "red_1": Action("punish", target="blue_1", amount=20)}
        a, b = Game(), Game()
        self.assertEqual(a.step(choices), b.step(dict(reversed(list(choices.items())))))
        with self.assertRaises(TypeError):
            a.wallets["blue_1"] = 999
        a.history[0]["wallets_after"]["blue_1"] = 999
        a.observe("blue_1")["history"][0]["contributions"]["blue_1"] = 999
        self.assertEqual(a.export(), b.export())

    def test_19_random_episodes_accounting_bounds_and_reproducibility(self):
        for seed in range(10):
            def episode():
                game = Game()
                result = run(game, {a.name: random_policy(seed * 100 + i) for i, a in enumerate(game.agents)})
                return result
            result = episode()
            self.assertEqual(result, episode())
            self.assertEqual(result["rounds_played"], 20)
            for record in result["history"]:
                expected = (math.fsum(record["wallets_before"].values()) + .5 * record["pool"]
                            - math.fsum(record["punishment_costs"].values())
                            - math.fsum(record["punishment_damage"].values()))
                self.assertAlmostEqual(math.fsum(record["wallets_after"].values()), expected)
                self.assertTrue(all(math.isfinite(w) and w >= 0 for w in record["wallets_after"].values()))
            for score in result["scores"].values():
                self.assertTrue(.1 - 1e-12 <= score["raw_score"] <= .8)
            json.dumps(result, allow_nan=False)

    def test_20_cli_writes_complete_json_episode(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "episode.json"
            result = subprocess.run([sys.executable, "-m", "pgg", "--policy", "random",
                                     "--seed", "123", "--output", str(output)],
                                    cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(data["complete"])
            self.assertEqual(len(data["history"]), 20)
            self.assertEqual(data["runner"]["seed"], 123)


if __name__ == "__main__":
    unittest.main()
