"""Common-seed screening of recovered Blue PGG constitutions against neutral Red."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import statistics
import sys

import run as pilot


REFERENCE = Path(__file__).resolve().parents[1] / "pgg/reference/cons-race"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, nargs="+", default=[9001, 9018])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default="openai/gpt-oss-120b")
    args = parser.parse_args()
    if len(set(args.seeds)) != len(args.seeds) or not args.seeds:
        parser.error("supply distinct shared seeds")
    candidates = json.loads((REFERENCE / "shortlist.json").read_text(encoding="utf-8"))
    neutral = {"name": "Neutral Red constitution", "rules": [
        "Observe the completed public game history and available actions before deciding.",
        "Choose a valid action using only the information in your observation."]}
    config = json.loads((Path(__file__).with_name("pilot.groq.json")).read_text(encoding="utf-8"))
    config["game"]["resident_role_prompts"] = "neutral"
    config["red_seed"] = neutral
    config["selection_seeds"] = args.seeds
    config["evaluation_seeds"] = []
    config["max_model_calls"] = len(candidates) * len(args.seeds) * 6 * config["game"]["rounds"]
    config["model"] = args.model
    args.output.mkdir(parents=True, exist_ok=False)
    pilot.write_trace(args.output / "config.json", config)
    shutil.copy2(__file__, args.output / "select_blue_baseline.py")
    shutil.copy2(Path(__file__).with_name("run.py"), args.output / "run.py")
    shutil.copy2(Path(__file__).with_name("groq_model.py"), args.output / "groq_model.py")
    shutil.copytree(Path(__file__).resolve().parents[1] / "pgg/pgg", args.output / "source/pgg",
                    ignore=shutil.ignore_patterns("__pycache__"))
    journal = pilot.Journal(args.output / "events.jsonl")
    model = pilot.GroqModel(args.model, journal, config["max_model_calls"], config)
    records = []
    for item in candidates:
        blue = json.loads((REFERENCE / item["candidate"]).read_text(encoding="utf-8"))
        name = blue["name"].replace(" ", "-")
        folder = args.output / "candidates" / name
        evaluation = pilot.evaluate(blue, neutral, args.seeds, folder, config["game"],
                                    model, journal, mock=False)
        episode_metrics = [e["metrics"] for e in evaluation["episodes"]]
        scores = [m["Blue"]["raw_score"] for m in episode_metrics]
        record = {"representative_generation": item["representative_generation"],
                  "equivalent_generations": item["equivalent_generations"], "blue": blue,
                  "rules_sha256": item["rules_sha256"], "seeds": args.seeds,
                  "mean_S_Blue": statistics.mean(scores),
                  "sd_S_Blue": statistics.stdev(scores) if len(scores) > 1 else None,
                  "by_seed": [{"seed": episode["seed"], "trace": str(folder / episode["trace"]),
                      "Blue": metrics["Blue"], "Red": metrics["Red"]}
                      for episode, metrics in zip(evaluation["episodes"], episode_metrics)]}
        records.append(record)
        pilot.write_trace(args.output / "results-partial.json", records)
    records.sort(key=lambda row: (-row["mean_S_Blue"],
        -statistics.mean(x["Blue"]["mean_wallet_contribution_fraction"] or 0 for x in row["by_seed"])))
    result = {"status": "complete", "model": args.model, "seeds": args.seeds,
              "neutral_red_constitution": neutral, "resident_role_prompts": "neutral",
              "game": config["game"], "selection_rule": "screen by mean Blue score; report wealth and contribution behavior alongside; two seeds are exploratory, not confirmatory",
              "model_calls": model.calls, "candidates": records,
              "provisional_recommendation": records[0]["blue"],
              "provisional_only": True}
    pilot.write_trace(args.output / "results.json", result)
    pilot.write_trace(args.output / "selected-blue-provisional.json", records[0]["blue"])
    pilot.write_trace(args.output / "manifest.json", {
        "source_hashes": {name: hashlib.sha256((args.output / name).read_bytes()).hexdigest()
                          for name in ("select_blue_baseline.py", "run.py", "groq_model.py")},
        "candidate_index": json.loads((REFERENCE / "candidate-index.json").read_text(encoding="utf-8")),
        "llm_calls": model.calls,
        "note": "provisional screen; repeat the winner and controls on separate held-out seeds before freezing C*"})
    print(json.dumps({"status": "complete", "model_calls": model.calls,
        "ranking": [{"generation": x["representative_generation"], "mean_S_Blue": x["mean_S_Blue"],
                     "mean_Blue_wealth": statistics.mean(m["Blue"]["wallet_total"] for m in x["by_seed"]),
                     "mean_contribution_fraction": statistics.mean(m["Blue"]["mean_wallet_contribution_fraction"]
                         for m in x["by_seed"])} for x in records],
        "provisional_recommendation": records[0]["blue"]["name"]}, indent=2))


if __name__ == "__main__":
    main()
