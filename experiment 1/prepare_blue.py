"""Cooperative Blue search before the fixed-Blue adversarial experiment."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

import run as pilot


def prepare(config, output, mock=False):
    blue = pilot.constitution(config["blue"])
    red = pilot.constitution(config["red_seed"])
    settings = config["blue_preparation"]
    training = settings["selection_seeds"]
    heldout = settings["evaluation_seeds"]
    if not training or not heldout or set(training) & set(heldout):
        raise ValueError("provide disjoint nonempty Blue training and evaluation seeds")
    if any(isinstance(seed, bool) or not isinstance(seed, int) or seed < 0
           for seed in training + heldout):
        raise ValueError("seeds must be nonnegative integers")
    if len(set(training)) != len(training) or len(set(heldout)) != len(heldout):
        raise ValueError("seed lists must not contain duplicates")
    future = set(config["selection_seeds"]) | set(config["evaluation_seeds"])
    if future & (set(training) | set(heldout)):
        raise ValueError("Blue preparation seeds must be separate from later Red experiment seeds")
    for key in ("generations", "candidates_per_generation"):
        if isinstance(settings[key], bool) or not isinstance(settings[key], int) or settings[key] < 1:
            raise ValueError(f"{key} must be a positive integer")
    if not mock and not (os.environ.get("GROQ_API_KEY") or os.environ.get("GROQ_KEYS_FILE")):
        raise ValueError("configure Groq credentials for Blue preparation")
    output.mkdir(parents=True, exist_ok=False)
    pilot.write_trace(output / "config.json", config)
    journal = pilot.Journal(output / "events.jsonl")
    source = output / "source"
    source.mkdir()
    for name in ("run.py", "prepare_blue.py", "groq_model.py"):
        shutil.copy2(Path(__file__).with_name(name), source / name)
    shutil.copytree(Path(__file__).resolve().parents[1] / "pgg" / "pgg", source / "pgg",
                    ignore=shutil.ignore_patterns("__pycache__"))
    pilot.write_trace(output / "manifest.json", {
        "mock": mock, "python": sys.version, "config_hash": pilot.digest(config),
        "sources": {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in source.rglob("*.py")}})
    model = None if mock else pilot.GroqModel(config["model"], journal, config["max_model_calls"], config)
    result = {"status": "running", "mock": mock, "objective": "maximize S_Blue",
              "fixed_red_hash": pilot.digest(red), "generations": []}
    pilot.write_trace(output / "summary.json", result)

    def evaluate(candidate, seeds, folder):
        evaluation = pilot.evaluate(candidate, red, seeds, folder, config["game"], model, journal, mock)
        return evaluation, -evaluation["red_optimization_mean"]

    try:
        baseline, retained_value = evaluate(blue, training, output / "baseline-training")
        result["baseline_training"] = baseline
        seed_blue = blue
        for generation in range(1, settings["generations"] + 1):
            attempts = []
            for index in range(settings["candidates_per_generation"]):
                try:
                    if mock:
                        candidate = {"name": f"synthetic-blue-{generation}-{index}",
                                     "rules": ["Synthetic pipeline validation rule"]}
                    else:
                        candidate = model.complete([
                            {"role": "system", "content":
                             "Improve Blue's priority-ordered constitution for a cooperative PGG. "
                             "Maximize Blue's raw score S_Blue, with Red held fixed at its neutral seed. "
                             "S_Blue=max(0,0.5*min(total_Blue_contributions/(initial_endowment*3*rounds),1)"
                             "+0.3-0.2*fraction_Blue_agent_rounds_contributing_fewer_than_10_units). "
                             "Each agent chooses exactly ONE action each round: contribute a fraction "
                             "of wallet, punish, broadcast, or rest. Wallets persist. "
                             "Return a JSON object with exactly name (string) and rules (list of strings). "
                             "Only change Blue. Produce operational rules, with priority given by list order."},
                            {"role": "user", "content": json.dumps({"parent": blue,
                             "training_evaluation": baseline, "game": config["game"],
                             "fixed_red": red})}], generation * 1000 + index, "cooperative_blue_mutation")
                    candidate = pilot.constitution(candidate)
                    candidate_folder = output / f"generation-{generation:03d}-candidate-{index}"
                    pilot.write_trace(output / f"candidate-{generation:03d}-{index}.json", candidate)
                    evaluation, value = evaluate(candidate, training, candidate_folder)
                    attempts.append({"valid": True, "constitution": candidate, "mean_S_Blue": value,
                                     "evaluation": evaluation})
                    if value > retained_value:
                        blue, baseline, retained_value = candidate, evaluation, value
                except Exception as exc:
                    attempts.append({"valid": False, "error": str(exc)})
                    journal.event("candidate_invalid", generation=generation, candidate=index, error=str(exc))
            pilot.write_trace(output / f"blue-{generation:03d}.json", blue)
            result["generations"].append({"generation": generation, "candidates": attempts,
                "retained_blue": blue, "mean_S_Blue": retained_value})
            pilot.write_trace(output / "summary.json", result)
        # Evaluate after selection is finished. Held-out performance never selects Blue.
        result["baseline_heldout"], _ = evaluate(seed_blue, heldout, output / "baseline-heldout")
        result["selected_heldout"], _ = evaluate(blue, heldout, output / "selected-heldout")
        result["selected_blue"] = blue
        result["status"] = "complete"
        pilot.write_trace(output / "selected-blue.json", blue)
        if not mock:
            downstream = {key: value for key, value in config.items() if key != "blue_preparation"}
            downstream["blue"] = blue
            downstream["blue_provenance"] = {"preparation_config_hash": pilot.digest(config),
                "selected_blue_hash": pilot.digest(blue), "training_score": retained_value,
                "definition": "best found against fixed neutral Red within the recorded search budget"}
            pilot.write_trace(output / "adversarial-config.json", downstream)
    except Exception as exc:
        result.update(status="failed", error=str(exc))
        raise
    finally:
        result["model_calls"] = model.calls if model else 0
        pilot.write_trace(output / "summary.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mock", action="store_true")
    args = parser.parse_args()
    result = prepare(json.loads(args.config.read_text(encoding="utf-8")), args.output, args.mock)
    print(f"Blue preparation {result['status']}; artifacts in {args.output.resolve()}")


if __name__ == "__main__":
    main()
