import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("experiment", ROOT / "run.py")
experiment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(experiment)


class ExperimentTests(unittest.TestCase):
    def config(self):
        config = json.loads((ROOT / "pilot.example.json").read_text(encoding="utf-8"))
        config.update(generations=2, candidates_per_generation=1,
                      selection_seeds=[42], evaluation_seeds=[1001])
        config["game"]["rounds"] = 2
        return config

    def test_fixed_blue_matched_pairs_replay_and_selection(self):
        config = self.config()
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "run"
            result = experiment.execute(config, output, mock=True)
            self.assertEqual(result["status"], "complete")
            self.assertEqual(result["model_calls"], 0)
            self.assertEqual(experiment.verify_experiment(output), 8)
            for generation in result["generations"]:
                self.assertEqual(generation["blue_hash"], experiment.digest(config["blue"]))
                self.assertEqual(generation["selected_red_hash"], generation["previous_red_hash"])
                self.assertEqual(generation["paired_heldout_changes"], [{"seed": 1001, "red_improvement": 0}])
            trace = json.loads(next(output.glob("generation-*/*/seed-*.json")).read_text())
            metrics = experiment.metrics(trace)
            self.assertEqual(metrics["optimization"]["Red"], -metrics["optimization"]["Blue"])
            for faction in ("Blue", "Red"):
                row = metrics[faction]
                self.assertAlmostEqual(row["material_payoff"], row["pool_returns"] -
                                       row["contribution_total"] - row["punishment_cost_paid"] -
                                       row["punishment_damage_received"])

    def test_seed_leakage_rejected_before_creating_output(self):
        config = self.config()
        config["evaluation_seeds"] = [42]
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "run"
            with self.assertRaisesRegex(ValueError, "disjoint"):
                experiment.execute(config, output, mock=True)
            self.assertFalse(output.exists())

    def test_invalid_constitutions(self):
        for value in ({"name": "bad", "rules": []}, {"name": "bad", "rules": [42]},
                      {"name": "bad", "rules": ["x"], "code": "do something"}):
            with self.assertRaises(ValueError):
                experiment.constitution(value)

    def test_existing_output_protected(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(FileExistsError):
                experiment.execute(self.config(), Path(temp), mock=True)

    def test_invalid_model_candidate_is_excluded(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            original = experiment.constitution
            def validate(value):
                if value["name"].startswith("synthetic"):
                    raise ValueError("invalid candidate")
                return original(value)
            with patch.object(experiment, "constitution", side_effect=validate):
                result = experiment.execute(self.config(), Path(temp) / "run", mock=True)
            for generation in result["generations"]:
                self.assertFalse(generation["selection"][0]["valid"])
                self.assertEqual(generation["selected_red_hash"], generation["previous_red_hash"])

    def test_replay_detects_source_tampering(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "run"
            experiment.execute(self.config(), output, mock=True)
            (output / "source" / "experiment.py").write_text("tampered")
            with self.assertRaisesRegex(ValueError, "source hash"):
                experiment.verify_experiment(output)

    def test_selection_prefers_lower_blue_score(self):
        from unittest.mock import patch
        def evaluate(blue, red, seeds, folder, *args):
            value = -.2 if red["name"].startswith("synthetic") else -.7
            episodes = [{"seed": seed, "metrics": {"optimization": {"Red": value}}}
                        for seed in seeds]
            return {"valid": True, "episodes": episodes, "red_optimization_mean": value}
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(experiment, "evaluate", side_effect=evaluate):
                result = experiment.execute(self.config(), Path(temp) / "run", mock=True)
            first = result["generations"][0]
            self.assertNotEqual(first["selected_red_hash"], first["previous_red_hash"])
            self.assertAlmostEqual(first["mean_red_improvement_heldout"], .5)


if __name__ == "__main__":
    unittest.main()
