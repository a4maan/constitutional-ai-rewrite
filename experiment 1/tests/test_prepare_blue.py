import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import prepare_blue


class PreparationTests(unittest.TestCase):
    def config(self):
        config = json.loads((ROOT / "prepare-blue.example.json").read_text(encoding="utf-8"))
        config["game"]["rounds"] = 2
        config["blue_preparation"].update(generations=1, candidates_per_generation=1,
                                           selection_seeds=[2001], evaluation_seeds=[3001])
        return config

    def test_mock_pipeline_keeps_red_fixed_and_outputs_replayable_games(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "blue"
            config = self.config()
            result = prepare_blue.prepare(config, output, mock=True)
            self.assertEqual(result["status"], "complete")
            traces = list(output.glob("*/seed-*.json"))
            self.assertEqual(len(traces), 4)
            for path in traces:
                trace = json.loads(path.read_text())
                prepare_blue.pilot.replay(trace)
                self.assertEqual(trace["runner"]["red"], config["red_seed"])
            self.assertFalse((output / "adversarial-config.json").exists())

    def test_maximizes_blue_not_red_objective(self):
        def evaluate(blue, red, seeds, folder, *args):
            score = .8 if blue["name"].startswith("synthetic") else .3
            return {"valid": True, "red_optimization_mean": -score}
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(prepare_blue.pilot, "evaluate", side_effect=evaluate):
                result = prepare_blue.prepare(self.config(), Path(temp) / "blue", mock=True)
            self.assertTrue(result["selected_blue"]["name"].startswith("synthetic"))
            self.assertEqual(result["generations"][0]["mean_S_Blue"], .8)

    def test_rejects_leakage_into_future_adversarial_seeds(self):
        config = self.config()
        config["blue_preparation"]["selection_seeds"] = config["selection_seeds"]
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "later Red"):
                prepare_blue.prepare(config, Path(temp) / "blue", mock=True)
