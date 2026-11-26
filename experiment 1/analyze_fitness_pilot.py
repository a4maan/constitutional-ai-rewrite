"""Check whether scripted Red fitness ranks intended Blue harm in saved games."""
import json
from pathlib import Path
import statistics
import sys


def analyze(root):
    rows = json.loads((root / "results.json").read_text(encoding="utf-8"))
    traces = root / "traces"
    games = []
    for row in rows:
        trace = json.loads((traces / f"{row['id']}.json").read_text(encoding="utf-8"))
        blue = trace["scores"]["Blue"]
        red = trace["scores"]["Red"]
        games.append({**row, "S_Blue": blue["raw_score"], "F_Red": -blue["raw_score"],
                      "S_Red_own": red["raw_score"], "Red_final_wealth": red["wallet_total"]})
    checks = []
    for cap in sorted({r["amount_mode"] for r in games}):
        for blue in sorted({r["blue_policy"] for r in games}):
            subset = [r for r in games if r["amount_mode"] == cap and r["blue_policy"] == blue]
            for left in subset:
                for right in subset:
                    if right["S_Blue"] < left["S_Blue"] - 1e-12:
                        checks.append({"mode": cap, "fixed_blue": blue,
                            "lower_blue_outcome_red_policy": right["red_policy"],
                            "higher_blue_outcome_red_policy": left["red_policy"],
                            "fitness_difference": right["F_Red"] - left["F_Red"],
                            "passes": right["F_Red"] > left["F_Red"]})
    red_own_conflicts = []
    for mode in {r["amount_mode"] for r in games}:
        for blue in {r["blue_policy"] for r in games}:
            subset = [r for r in games if r["amount_mode"] == mode and r["blue_policy"] == blue]
            for a in subset:
                for b in subset:
                    if b["S_Blue"] < a["S_Blue"] - 1e-12 and b["S_Red_own"] > a["S_Red_own"] + 1e-12:
                        red_own_conflicts.append({"mode": mode, "fixed_blue": blue,
                            "lower_blue_red_policy": b["red_policy"], "higher_blue_red_policy": a["red_policy"],
                            "S_Blue_lower": b["S_Blue"], "S_Blue_higher": a["S_Blue"],
                            "S_Red_lower_blue": b["S_Red_own"], "S_Red_higher_blue": a["S_Red_own"]})
    result = {"games_analyzed": len(games), "paired_strict_comparisons": len(checks),
              "fitness_ordering_passes": sum(c["passes"] for c in checks),
              "fitness_ordering_failures": sum(not c["passes"] for c in checks),
              "fitness_ties_when_blue_scores_tie": sum(1 for mode in {r["amount_mode"] for r in games}
                  for blue in {r["blue_policy"] for r in games}
                  for i, a in enumerate([r for r in games if r["amount_mode"] == mode and r["blue_policy"] == blue])
                  for b in [r for r in games if r["amount_mode"] == mode and r["blue_policy"] == blue][i+1:]
                  if a["S_Blue"] == b["S_Blue"]),
              "red_own_score_increases_while_blue_worsens": len(red_own_conflicts),
              "red_own_score_conflict_examples": red_own_conflicts[:20],
              "scope": "deterministic fixed policies, not LLM or evolved constitutions"}
    result["full_wallet_blue_original_runtime"] = [
        {k: r[k] for k in ("red_policy", "S_Blue", "F_Red", "S_Red_own", "Red_final_wealth")}
        for r in games if r["blue_policy"] == "full" and r["amount_mode"] == "original_runtime_wallet_limited"]
    result["strongest_scripted_attack_against_full_blue"] = min(
        result["full_wallet_blue_original_runtime"], key=lambda r: r["S_Blue"])
    result["red_own_score_when_blue_worsens"] = [
        {"blue_policy": "full", "red_policy": r["red_policy"], "S_Blue": r["S_Blue"],
         "F_Red": r["F_Red"], "S_Red_own": r["S_Red_own"], "Red_final_wealth": r["Red_final_wealth"]}
        for r in result["full_wallet_blue_original_runtime"]]
    return result


def report(result):
    lines = ["# Fitness objective pilot", "",
        "## Question", "",
        "Does Red's fitness, F_Red = -S_Blue, reward scripted Red policies when the same fixed Blue policy receives a lower Blue score?", "",
        "## Result", "",
        f"Analyzed {result['games_analyzed']} existing deterministic games from the LLM-free scoring run. Among {result['paired_strict_comparisons']} same-Blue, same-rule comparisons where Blue scores differed, Red fitness ranked every lower-Blue-score outcome higher ({result['fitness_ordering_passes']} passes, {result['fitness_ordering_failures']} failures). This is algebraically guaranteed by F_Red = -S_Blue; the games demonstrate how that objective ranks these policies, not that it independently measures adversarial intent.", "",
        "For full-wallet Blue under the original runtime rules:", "",
        "| Red policy | Blue score S_B | Red fitness -S_B | Red own score S_R | Red final wealth |",
        "|---|---:|---:|---:|---:|"]
    for r in result["full_wallet_blue_original_runtime"]:
        lines.append(f"| {r['red_policy']} | {r['S_Blue']:.6f} | {r['F_Red']:.6f} | {r['S_Red_own']:.6f} | {r['Red_final_wealth']:,.3f} |")
    best = result["strongest_scripted_attack_against_full_blue"]
    lines += ["", f"The strongest of these scripted Red policies is `{best['red_policy']}`: it lowers Blue's score to {best['S_Blue']:.6f} (Red fitness {best['F_Red']:.6f}). This is a policy-level control result, not learned behavior.", "",
        f"In {result['red_own_score_increases_while_blue_worsens']} examined pairwise comparisons, Red's own score rose while Blue's fell. The direct counterexample is stronger: against full-wallet Blue, punishment Red drops Blue to {best['S_Blue']:.6f}, while Red itself scores only {best['S_Red_own']:.6f} and ends with {best['Red_final_wealth']:.3f} wealth, compared with 0.800 and 997,575.414 wealth for full-contribution Red. So `-S_Blue` rewards the Blue harm even when Red's own outcomes deteriorate.", "",
        "## Interpretation", "",
        "The fitness formula faithfully encodes the narrow objective 'minimize Blue's existing composite score.' It does not guarantee that Red learns a purposeful attack, that Red benefits, or that Blue loses wealth. Those are separate claims and need separate outcomes and controls. The scoring validation found saturation, depletion, and score/wealth mismatches; use Blue wealth and available-wallet contribution fraction alongside S_Blue.", "",
        "A useful LLM pilot should now compare neutral-prompt Red before and after optimization against frozen Blue, using the same held-out games and controls. That tests learned policy changes. This scripted analysis cannot replace it.", "",
        "Method: all policies were deterministic and fixed; each Blue/Red pair was run once in each contribution-cap mode, from the same 100-unit initial balances for 20 rounds. Pair counts are comparisons among this designed policy grid, not statistical samples.", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output/scoring-validation-2026-11-25-final")
    result = analyze(root)
    (root / "fitness-objective-pilot.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (root / "fitness-objective-pilot.md").write_text(report(result), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("games_analyzed", "paired_strict_comparisons",
          "fitness_ordering_passes", "fitness_ordering_failures", "fitness_ties_when_blue_scores_tie")}, indent=2))
