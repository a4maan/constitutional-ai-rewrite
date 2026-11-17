import json
import unittest

from pgg import Action, Config, Game
from pgg.replay import replay
from pgg.runner import run


class ReplayTests(unittest.TestCase):
    def test_saved_trace_reconstructs_episode_and_detects_tampering(self):
        game = Game(Config(rounds=2))

        def policy(observation):
            observation["players"].clear()
            return Action("contribute", fraction=0.5)

        trace = run(game, dict.fromkeys((a.name for a in game.agents), policy))
        self.assertEqual(replay(json.loads(json.dumps(trace))), game.export())
        trace["decisions"][0]["policies"][0]["observation"]["players"].clear()
        with self.assertRaisesRegex(ValueError, "round 1 observation"):
            replay(trace)

    def test_failure_checkpoint_replays_completed_prefix(self):
        game = Game(Config(rounds=2))
        checkpoints = []

        def policy(observation):
            if observation["round"] == 2:
                raise RuntimeError("policy failed")
            return Action()

        with self.assertRaisesRegex(RuntimeError, "policy failed"):
            run(game, dict.fromkeys((a.name for a in game.agents), policy),
                checkpoint=lambda trace: checkpoints.append(json.loads(json.dumps(trace))))
        trace = checkpoints[-1]
        self.assertEqual(trace["error"]["message"], "policy failed")
        self.assertEqual(len(trace["pending_decisions"]), 1)
        self.assertEqual(replay(trace)["rounds_played"], 1)
