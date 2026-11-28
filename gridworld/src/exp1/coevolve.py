"""Experiment 1 gridworld pilots 2 and 3, with Optimizer A (parent plus challengers) for each side.

Modes (config key "mode"):
  red_vs_fixed_blue  Blue is fixed. Red evolves (pilot 1 design, deeper run).
  blue_vs_fixed_red  Red is a fixed hand-written constitution. Blue evolves.
  alternating        Blue and Red both evolve. Each generation: Blue step first (B_g against R_(g-1)),
                     then Red step (R_g against B_g). The schedule is a setting; only "alternating" exists.

Held-out evaluation (never used for selection), on the evaluation seeds:
  baseline (B_0, R_0); then for each generation g:
  red_vs_fixed_blue: (B_0, R_g).  blue_vs_fixed_red: (B_g, R_0).
  alternating: (B_g, R_(g-1)), where Blue moved last, and (B_g, R_g), the aligned same-generation pair,
  where Red moved last. Paired changes per seed: Blue's response = (B_g, R_(g-1)) - (B_(g-1), R_(g-1));
  Red's response = (B_g, R_g) - (B_g, R_(g-1)), both in S_Blue on the same seeds.

An evaluation of the same (Blue, Red, seeds) as an earlier evaluation in the run is not played again.
The row refers to the first evaluation ("reused_from"). With the response cache, a replay is a copy.

Run from the repository root:
  .venv/bin/python gridworld/src/exp1/coevolve.py --config gridworld/exp1-configs/pilot2-blue-vs-red.json \
      --output output/X [--mock] [--resume] [--max-cost USD]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from exp1.openrouter_model import BudgetExceeded  # noqa: E402
from exp1.play import digest  # noqa: E402
from exp1.run import (assess, constitution, make_model, mutate, mutator_prompt, prepare,  # noqa: E402
                      write_json)
from exp1.score import BLUE_FITNESS, FITNESS  # noqa: E402

MODES = ("red_vs_fixed_blue", "blue_vs_fixed_red", "alternating")
LABELS = {
    "baseline": "baseline: B_0 against R_0",
    "fixed": "B_g against the fixed Red",
    "fixed_blue": "the fixed Blue against R_g",
    "blue_last": "B_g against R_(g-1): Blue moved last; favors Blue",
    "aligned": "aligned B_g against R_g (same generation): Red moved last; favors Red",
}


RED_SIDE = {"fitness", "fitness_name", "red_optimization_mean", "red_optimization_standard_error"}


def for_mutator(evaluation, side):
    """The Blue mutator must not learn Red's objective: drop the Red fitness fields (scores stay)."""
    if side == "Red":
        return evaluation
    strip = lambda d: {k: v for k, v in d.items() if k not in RED_SIDE}
    return {**strip(evaluation), "episodes": [strip(e) for e in evaluation.get("episodes", [])]}


def check(config, mock, model_given):
    import os
    if config.get("mode") not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    constitution(config["blue"])
    constitution(config["red"])
    for key in ("generations", "candidates_per_generation"):
        if isinstance(config[key], bool) or not isinstance(config[key], int) or config[key] < 1:
            raise ValueError(f"{key} must be a positive integer")
    lists = {"red_vs_fixed_blue": ["red_selection_seeds"], "blue_vs_fixed_red": ["blue_selection_seeds"],
             "alternating": ["blue_selection_seeds", "red_selection_seeds"]}[config["mode"]] + ["evaluation_seeds"]
    seen = set()
    for key in lists:
        seeds = config[key]
        if not seeds or any(isinstance(s, bool) or not isinstance(s, int) or s < 0 for s in seeds) \
                or len(set(seeds)) != len(seeds):
            raise ValueError(f"{key} must contain distinct nonnegative integers")
        if seen & set(seeds):
            raise ValueError("selection and held-out seed lists must be disjoint")
        seen |= set(seeds)
    if config["fitness"] not in FITNESS or config["blue_fitness"] not in BLUE_FITNESS:
        raise ValueError("unknown fitness name")
    if config.get("provider") != "openrouter" or not config.get("openrouter_provider"):
        raise ValueError("provider must be openrouter, with 1 pinned openrouter_provider")
    if not mock and not model_given and not os.environ.get("OPENROUTER_API_KEY"):
        raise ValueError("OPENROUTER_API_KEY is required for a model-backed run (put it in .env)")


def run(config, output, mock=False, resume=False, model=None, max_cost=None):
    check(config, mock, model is not None)
    mode, alternating = config["mode"], config["mode"] == "alternating"
    red_only = mode == "red_vs_fixed_blue"
    journal = prepare(config, output, mock, resume, mode, "A")
    model = make_model(config, journal, mock, model, max_cost)
    played = {}  # (blue_id, red_id, seeds) -> (folder, evaluation)

    def play(blue, red, seeds, folder):
        key = (digest(blue), digest(red), tuple(seeds))
        here = str(folder.relative_to(output))
        if key in played:
            first, evaluation = played[key]
            journal.event("evaluation_reused", folder=here, reused_from=first)
            return {**evaluation, "folder": first, "reused_from": first}
        evaluation = assess(journal, blue, red, seeds, folder, config, model, mock, optimizer="A")
        if evaluation["valid"]:
            played[key] = (here, evaluation)
        return {**evaluation, "folder": here}

    def step(side, parent, opponent, seeds, folder, generation):
        """One Optimizer A step for one side. The opponent is fixed during the step."""
        pair = (lambda c: (c, opponent)) if side == "Blue" else (lambda c: (opponent, c))
        value = "blue_optimization_mean" if side == "Blue" else "red_optimization_mean"
        parent_eval = play(*pair(parent), seeds, folder / "parent-selection")
        if not parent_eval["valid"]:
            raise RuntimeError(f"{side} parent evaluation failed; generation {generation} cannot select")
        best, best_eval, rows = parent, parent_eval, []
        for index in range(config["candidates_per_generation"]):
            try:
                if mock:
                    proposed = {"name": f"synthetic-{side.lower()}-{generation}-{index}",
                                "rules": [f"Synthetic {side} rule {generation}-{index}"]}
                else:
                    sees = config.get("mutation_sees_opponent", False)  # TODO(decision): separate agreed test
                    proposed = mutate(model, journal, mutator_prompt(config, side, alternating), json.dumps({
                        "parent": parent, "parent_evaluation": for_mutator(parent_eval, side), "game": config["game"],
                        "opponent_constitution": opponent if sees else None}),
                        generation * 1000 + index + (500 if side == "Red" else 0),
                        f"{side.lower()}_constitution_mutation")
                proposed = constitution(proposed)
                journal.event("mutation_valid", side=side, generation=generation, candidate=index,
                              constitution=proposed)
                write_json(folder / f"candidate-{index}.json", proposed)
                evaluation = play(*pair(proposed), seeds, folder / f"candidate-{index}-selection")
                rows.append({"candidate": index, "constitution_id": digest(proposed),
                             "opponent_id": digest(opponent), **evaluation})
                if evaluation["valid"] and evaluation[value] > best_eval[value]:
                    best, best_eval = proposed, evaluation
            except BudgetExceeded:
                raise
            except Exception as exc:
                rows.append({"candidate": index, "valid": False, "error": str(exc)})
                journal.event("mutation_invalid", side=side, generation=generation, candidate=index,
                              error=str(exc))
        journal.event("selection", side=side, generation=generation, previous=parent, selected=best,
                      opponent_id=digest(opponent),
                      criterion=f"maximize mean {value} on {side} selection seeds; retain parent on ties")
        return best, {"side": side, "previous_id": digest(parent), "selected_id": digest(best),
                      "opponent_id": digest(opponent), "parent_selection": parent_eval, "selection": rows}

    def heldout(gb, gr, blue, red, label):
        evaluation = play(blue, red, config["evaluation_seeds"], output / "heldout" / f"B{gb:03d}-R{gr:03d}")
        if not evaluation["valid"]:
            raise RuntimeError(f"held-out evaluation B{gb:03d}-R{gr:03d} failed: {evaluation.get('error')}")
        episodes = [{"seed": e["seed"], "blue_id": e["blue_id"], "red_id": e["red_id"],
                     "S_Blue": e["scores"]["Blue"]["S"], "S_Red": e["scores"]["Red"]["S"],
                     "scores": e["scores"], "behavior": e["behavior"]} for e in evaluation["episodes"]]
        return {"blue_generation": gb, "red_generation": gr, "blue_id": digest(blue), "red_id": digest(red),
                "label": LABELS[label], "folder": evaluation["folder"],
                "reused_from": evaluation.get("reused_from"), "episodes": episodes,
                "mean_S_Blue": statistics.mean(e["S_Blue"] for e in episodes),
                "mean_S_Red": statistics.mean(e["S_Red"] for e in episodes)}

    def paired(after, before, name):
        return {"change": name, "after": f"B{after['blue_generation']:03d}-R{after['red_generation']:03d}",
                "before": f"B{before['blue_generation']:03d}-R{before['red_generation']:03d}",
                "per_seed": [{"seed": a["seed"], "S_Blue_before": b["S_Blue"], "S_Blue_after": a["S_Blue"],
                              "difference": a["S_Blue"] - b["S_Blue"]}
                             for a, b in zip(after["episodes"], before["episodes"])],
                "mean_difference_S_Blue": after["mean_S_Blue"] - before["mean_S_Blue"]}

    blue, red = config["blue"], config["red"]
    summary = {"status": "running", "mode": mode, "optimizer": "A", "mock": mock,
               "schedule": {"alternating": "alternating, Blue first", "blue_vs_fixed_red": "Red fixed",
                            "red_vs_fixed_blue": "Blue fixed"}[mode],
               "blue_fitness": None if red_only else config["blue_fitness"],
               "red_fitness": None if mode == "blue_vs_fixed_red" else config["fitness"],
               "note": "Selection scores are internal to the optimizer. Report only held-out rows.",
               "generations": [], "heldout": [], "paired_changes": []}
    write_json(output / "summary.json", summary)
    try:
        write_json(output / "blue-000.json", blue)
        write_json(output / "red-000.json", red)
        base = heldout(0, 0, blue, red, "baseline")
        summary["heldout"].append(base)
        previous = base  # (B_(g-1), R_(g-1)) held-out row
        for g in range(1, config["generations"] + 1):
            folder = output / f"generation-{g:03d}"
            if red_only:
                red, red_row = step("Red", red, blue, config["red_selection_seeds"], folder / "red-step", g)
                write_json(output / f"red-{g:03d}.json", red)
                row = {"generation": g, "red_step": red_row}
                current = heldout(0, g, blue, red, "fixed_blue")
                summary["heldout"].append(current)
                summary["paired_changes"].append(paired(current, previous, "Red step"))
                previous = current
                summary["generations"].append(row)
                write_json(output / "summary.json", summary)
                continue
            blue, blue_row = step("Blue", blue, red, config["blue_selection_seeds"], folder / "blue-step", g)
            write_json(output / f"blue-{g:03d}.json", blue)
            row = {"generation": g, "blue_step": blue_row}
            blue_last = heldout(g, g - 1 if alternating else 0, blue, red, "blue_last" if alternating else "fixed")
            summary["heldout"].append(blue_last)
            summary["paired_changes"].append(paired(blue_last, previous, "Blue step"))
            previous = blue_last
            if alternating:
                red, red_row = step("Red", red, blue, config["red_selection_seeds"], folder / "red-step", g)
                write_json(output / f"red-{g:03d}.json", red)
                row["red_step"] = red_row
                aligned = heldout(g, g, blue, red, "aligned")
                summary["heldout"].append(aligned)
                summary["paired_changes"].append(paired(aligned, blue_last, "Red step"))
                previous = aligned
            summary["generations"].append(row)
            write_json(output / "summary.json", summary)
        summary["status"] = "complete"
    except Exception as exc:
        summary["status"], summary["error"] = "failed", str(exc)
        raise
    finally:
        summary["model_calls"] = getattr(model, "calls", 0)
        summary["model_usage"] = getattr(model, "usage", None)
        write_json(output / "summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mock", action="store_true", help="synthetic actions, no model calls")
    parser.add_argument("--resume", action="store_true", help="reuse the output folder; skip complete games")
    parser.add_argument("--max-cost", type=float, help="stop the run when its model cost reaches this USD value")
    args = parser.parse_args()
    summary = run(json.loads(args.config.read_text(encoding="utf-8")), args.output, args.mock, args.resume,
                  max_cost=args.max_cost)
    print(f"{summary['mode']} {summary['status']}; artifacts in {args.output.resolve()}")


if __name__ == "__main__":
    main()
