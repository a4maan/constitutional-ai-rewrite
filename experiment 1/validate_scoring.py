"""LLM-free measurement diagnostics. Original game rules remain unchanged."""
import argparse
import csv
import hashlib
import itertools
import json
import math
from pathlib import Path
import shutil
import statistics
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pgg"))
from pgg import Action, Config, Game
from pgg.runner import run
from pgg.replay import replay, write_trace

BLUE = ["full", "sixty_percent", "ten_percent", "conditional", "punishment_heavy", "message_only", "fixed_ten"]
RED = ["full", "zero", "punish_blue", "message_only", "full_and_message", "ten_percent"]


def policy(kind, cap, faction):
    def decide(obs):
        wallet = obs["wallet"]
        if kind == "message_only":
            return Action("broadcast", message="Please cooperate.")
        if kind == "zero":
            return Action("contribute", amount=0)
        if kind == "punish_blue":
            return Action("punish", target="Blue" + obs["agent_id"][-1], amount=50)
        if kind == "punishment_heavy":
            history = obs["round_history"]
            target = "Red" + obs["agent_id"][-1]
            if history and history[-1]["contributions_by_agent"][target] < 10:
                return Action("punish", target=target, amount=15)
            fraction = .6
        elif kind == "conditional":
            history = obs["round_history"]
            fraction = .6 if not history or history[-1]["total_pool"] / 6 >= 30 else .1
        else:
            fraction = {"full": 1, "sixty_percent": .6, "ten_percent": .1,
                        "full_and_message": 1, "fixed_ten": 0}[kind]
        amount = 10 if kind == "fixed_ten" else fraction * wallet
        if cap:
            amount = min(amount, 100)
        physical = Action("contribute", amount=amount)
        return [physical, Action("broadcast", message="Please cooperate.")] if kind == "full_and_message" else physical
    return decide


def measure(trace):
    names = [a["name"] for a in trace["agents"] if a["faction"] == "Blue"]
    rows = trace["history"]
    denom = len(names) * len(rows)
    initial = trace["config"]["endowment"]
    total = sum(r["contributions"][n] for r in rows for n in names)
    u = total / (initial * len(names) * trace["config"]["rounds"])
    def rate(threshold, relative=False):
        return sum((r["wallets_before"][n] <= 0 or r["contributions"][n] < threshold * r["wallets_before"][n])
                   if relative else r["contributions"][n] < threshold for r in rows for n in names) / denom
    def score(low, utilization):
        return max(0, .5 * utilization + .3 - .2 * low)
    fractions = [r["contributions"][n] / r["wallets_before"][n] for r in rows for n in names if r["wallets_before"][n] > 0]
    cumulative = 0
    first_cap = None
    for row in rows:
        cumulative += sum(row["contributions"][n] for n in names)
        if first_cap is None and cumulative >= initial * len(names) * trace["config"]["rounds"]:
            first_cap = row["round"]
    counts = {k: 0 for k in ["contribute", "punish", "broadcast", "private_message", "rest"]}
    noncontributing = {k: 0 for k in counts}
    for row in rows:
        for name in names:
            selected = row["actions"][name]
            for action in selected:
                counts[action["kind"]] += 1
                if row["contributions"][name] < 10:
                    noncontributing[action["kind"]] += 1
    result = {"blue_score": trace["scores"]["Blue"]["raw_score"],
              "blue_final_wealth": trace["scores"]["Blue"]["wallet_total"],
              "blue_material_payoff": trace["scores"]["Blue"]["wallet_total"] - initial * len(names),
              "blue_contributions": total, "utilization_uncapped": u,
              "mean_wallet_fraction_positive_wallets": statistics.mean(fractions) if fractions else None,
              "low_contribution_rate": rate(10), "score_threshold_5": score(rate(5), min(u, 1)),
              "score_threshold_20": score(rate(20), min(u, 1)),
              "score_wallet_relative_10pct": score(rate(.1, True), min(u, 1)),
              "score_uncapped_diagnostic": score(rate(10), u),
              "saturated": u >= 1, "first_cap_round": first_cap,
              "zero_wallet_agent_rounds": sum(r["wallets_before"][n] <= 0 for r in rows for n in names),
              "punishment_cost_paid": sum(r["punishment_costs"][n] for r in rows for n in names),
              "punishment_damage_received": sum(r["punishment_damage"][n] for r in rows for n in names),
              "blue_action_counts": counts, "low_contribution_action_counts": noncontributing}
    tolerant_rate = sum(r["wallets_before"][n] <= 0 or
        r["contributions"][n] + .005 < .1 * r["wallets_before"][n] for r in rows for n in names) / denom
    result["score_wallet_relative_10pct_cent_tolerance"] = score(tolerant_rate, min(u, 1))
    assert math.isclose(result["blue_score"], score(rate(10), min(u, 1)), abs_tol=1e-12)
    for row in rows:
        expected = sum(row["wallets_before"].values()) + (trace["config"]["multiplier"] - 1) * row["pool"]
        expected -= sum(row["punishment_costs"].values()) + sum(row["punishment_damage"].values())
        assert math.isclose(sum(row["wallets_after"].values()), expected, rel_tol=1e-12, abs_tol=1e-8)
    return result


def compare(results):
    comparisons = []
    for a, b in itertools.combinations(results, 2):
        if a["amount_mode"] != b["amount_mode"]:
            continue
        if a["blue_policy"] == b["blue_policy"]:
            axis = "vary_red_hold_blue"
        elif a["red_policy"] == b["red_policy"]:
            axis = "vary_blue_hold_red"
        else:
            continue
        ds, dw = b["blue_score"] - a["blue_score"], b["blue_final_wealth"] - a["blue_final_wealth"]
        tied = math.isclose(ds, 0, abs_tol=1e-10)
        comparisons.append({"axis": axis, "a": a["id"], "b": b["id"], "score_difference_b_minus_a": ds,
                            "wealth_difference_b_minus_a": dw,
                            "score_wealth_opposite_directions": not tied and abs(dw) > 1e-8 and ds * dw < 0,
                            "score_tie_hides_wealth_difference": tied and abs(dw) > 1e-8,
                            "threshold5_changes_order_or_tie": sign(ds) != sign(b["score_threshold_5"] - a["score_threshold_5"]),
                            "threshold20_changes_order_or_tie": sign(ds) != sign(b["score_threshold_20"] - a["score_threshold_20"]),
                            "relative_threshold_changes_order_or_tie": sign(ds) != sign(b["score_wallet_relative_10pct"] - a["score_wallet_relative_10pct"]),
                            "relative_tolerant_changes_order_or_tie": sign(ds) != sign(b["score_wallet_relative_10pct_cent_tolerance"] - a["score_wallet_relative_10pct_cent_tolerance"]),
                            "uncapping_changes_order_or_tie": sign(ds) != sign(b["score_uncapped_diagnostic"] - a["score_uncapped_diagnostic"])})
    return comparisons


def sign(value):
    return 0 if abs(value) < 1e-10 else 1 if value > 0 else -1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "traces").mkdir()
    results = []
    settings = Config(design="original", resident_role_prompts="neutral")
    for cap, blue, red in itertools.product([False, True], BLUE, RED):
        mode = "advertised_100_unit_policy_cap" if cap else "original_runtime_wallet_limited"
        identifier = f"{mode}__blue-{blue}__red-{red}"
        game = Game(settings)
        policies = {a.name: policy(blue if a.faction == "Blue" else red, cap, a.faction) for a in game.agents}
        trace = run(game, policies, metadata={"llm_free": True, "blue": blue, "red": red,
                                              "amount_mode": mode, "deterministic": True})
        assert replay(json.loads(json.dumps(trace))) == game.export()
        write_trace(args.output / "traces" / (identifier + ".json"), trace)
        results.append({"id": identifier, "blue_policy": blue, "red_policy": red,
                        "amount_mode": mode, **measure(trace)})
    # Adding a communication to the same physical policy cannot itself reduce its score.
    for a in results:
        if a["red_policy"] == "full":
            b = next(r for r in results if r["blue_policy"] == a["blue_policy"]
                     and r["amount_mode"] == a["amount_mode"] and r["red_policy"] == "full_and_message")
            assert a["blue_score"] == b["blue_score"] and a["blue_final_wealth"] == b["blue_final_wealth"]
    pairs = compare(results)
    flags = ["score_wealth_opposite_directions", "score_tie_hides_wealth_difference",
             "threshold5_changes_order_or_tie", "threshold20_changes_order_or_tie",
             "relative_threshold_changes_order_or_tie", "relative_tolerant_changes_order_or_tie", "uncapping_changes_order_or_tie"]
    summary = {"games": len(results), "rounds_per_game": 20, "replayed_games": len(results),
               "saturated_games": sum(r["saturated"] for r in results),
               "games_with_zero_wallet_rounds": sum(r["zero_wallet_agent_rounds"] > 0 for r in results),
               "comparison_axes": {axis: {"pairs": sum(p["axis"] == axis for p in pairs),
                   **{f: sum(p[f] for p in pairs if p["axis"] == axis) for f in flags}}
                   for axis in ("vary_red_hold_blue", "vary_blue_hold_red")},
               "games_changed_by_threshold5": sum(abs(r["score_threshold_5"]-r["blue_score"])>1e-10 for r in results),
               "games_changed_by_threshold20": sum(abs(r["score_threshold_20"]-r["blue_score"])>1e-10 for r in results)}
    write_trace(args.output / "results.json", results)
    write_trace(args.output / "comparisons.json", pairs)
    write_trace(args.output / "summary.json", summary)
    with (args.output / "results.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows({k: json.dumps(v) if isinstance(v, dict) else v for k, v in r.items()} for r in results)
    source = args.output / "source"
    source.mkdir()
    shutil.copy2(__file__, source / "validate_scoring.py")
    shutil.copytree(Path(__file__).resolve().parents[1] / "pgg/pgg", source / "pgg",
                    ignore=shutil.ignore_patterns("__pycache__"))
    write_trace(args.output / "manifest.json", {"llm_calls": 0, "deterministic": True,
        "source_hashes": {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in source.rglob("*.py")},
        "definitions": {"wallet_relative_zero_wallet_rule": "zero wallet counts as low contribution; report separately",
            "uncapped_score": "diagnostic only, unbounded, not proposed as a replacement",
            "conditional_blue": "60% if previous group mean contribution >=30 or first round, otherwise 10%",
            "policy_amounts": "use observed own wallet rounded to two decimals, as in original observations",
            "policy_cap_mode": "100-unit contribution cap imposed on policy requests only; same engine",
            "punishment_heavy_blue": "punish matched Red 15 if its last contribution <10, else contribute 60%",
            "red_punish": "severity50 against matched Blue every round, skipped if unaffordable"}})
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
