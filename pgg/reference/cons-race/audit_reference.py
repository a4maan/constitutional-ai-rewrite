"""Audit pinned artifacts and compare deterministic engines; makes no API calls."""
import ast
import csv
import hashlib
import json
import math
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parent
UP = ROOT / "upstream"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def rules_from_text(text):
    # Extract only literal data. Never import or execute constitution programs.
    tree = ast.parse(text)
    func = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                and n.name == "get_constitution_rules")
    statements = [n for n in func.body if not isinstance(n, ast.Expr)]
    if len(statements) != 1 or not isinstance(statements[0], ast.Return):
        raise ValueError("Expected a single literal return")
    rules = list(ast.literal_eval(statements[0].value))
    if not rules or any(set(r) != {"name", "guidance", "summary", "priority"} for r in rules):
        raise ValueError("Unexpected rule schema")
    if any(not isinstance(r["guidance"], str) or not isinstance(r["priority"], int) for r in rules):
        raise ValueError("Invalid rule types")
    return rules


def fingerprint(rules):
    return hashlib.sha256(json.dumps(rules, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def audit_candidates():
    trace = read(UP / "paper/results/exp4-pgg/evolution_trace.json")
    indexed = {r["generation"]: r for r in trace["generations"]}
    rows = []
    candidates = ROOT / "candidates"
    candidates.mkdir(exist_ok=True)
    for generation in range(31):
        relative = f"paper/results/exp4-pgg/checkpoints/gen_{generation:03d}/blue_best.py"
        path = UP / relative
        rules = rules_from_text(path.read_text(encoding="utf-8"))
        ordered = sorted(rules, key=lambda r: r["priority"])
        current = {"name": f"cons-race-blue-gen-{generation:03d}",
                   "rules": [f"{r['name']}: {r['guidance']}" for r in ordered]}
        assert 1 <= len(current["rules"]) <= 20
        assert all(0 < len(rule) <= 2000 for rule in current["rules"])
        # This is a syntactic conversion only, not approval for the current game.
        (candidates / f"blue-gen-{generation:03d}.json").write_text(
            json.dumps(current, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        row = {"generation": generation, "rule_count": len(rules), "rules_sha256": fingerprint(rules),
               "recorded_blue_score": None, "opponent_score_in_blue_evaluation": None,
               "selection": "initial_seed", "checkpoint_matches_best": None,
               "score_records_agree": None, "source": relative}
        if generation:
            logdir = UP / f"logs/exp4-pgg/blue/gen_{generation:03d}"
            info = read(logdir / "best/best_program_info.json")
            metrics = read(path.parent / "metrics.json")
            partial = read(path.parent / "partial_blue.json")
            events = [json.loads(line) for line in (logdir / "evolution_trace.jsonl").read_text(
                encoding="utf-8").splitlines() if line.strip()]
            selection_trials = []
            for event in events:
                try:
                    child_hash = fingerprint(rules_from_text(event["child_code"]))
                    parse_error = None
                except (ValueError, SyntaxError, StopIteration) as exc:
                    child_hash, parse_error = None, type(exc).__name__
                selection_trials.append({"parent_score": event["parent_metrics"].get("combined_score"),
                                         "child_metrics": event["child_metrics"],
                                         "child_rules_sha256": child_hash,
                                         "child_literal_parse_error": parse_error})
            matches = []
            for event in events:
                for role in ("parent", "child"):
                    if event.get(role + "_id") == info["id"]:
                        matched_rules = rules_from_text(event[role + "_code"])
                        matches.append({"role": role, "rules_match": fingerprint(matched_rules) == fingerprint(rules),
                                        "metrics": event[role + "_metrics"]})
            best_rules = rules_from_text((logdir / "best/best_program.py").read_text(encoding="utf-8"))
            score = info["metrics"]["combined_score"]
            row.update(recorded_blue_score=score,
                       opponent_score_in_blue_evaluation=info["metrics"].get("opponent_score"),
                       selection="/".join(sorted({m["role"] for m in matches})) or "unresolved",
                       checkpoint_matches_best=fingerprint(best_rules) == fingerprint(rules),
                       score_records_agree=all(math.isclose(score, value, abs_tol=1e-12) for value in (
                           metrics["blue_S"], partial["blue_S"], indexed[generation]["blue_S"])),
                       selection_evidence=matches, best_program_id=info["id"])
            row["selection_trials"] = selection_trials
            assert row["checkpoint_matches_best"] and row["score_records_agree"], generation
            assert matches and all(m["rules_match"] for m in matches), generation
            assert all(math.isclose(m["metrics"]["combined_score"], score, abs_tol=1e-12)
                       for m in matches), generation
        row["same_rules_as_generations"] = [r["generation"] for r in rows
                                               if r["rules_sha256"] == row["rules_sha256"]]
        rows.append(row)
    result = {"status": "recovered_not_reevaluated", "config": trace["config"],
              "selection_seeds_from_evaluator": [42, 59],
              "unique_rule_sets": len({r["rules_sha256"] for r in rows}), "candidates": rows}
    groups = {}
    for row in rows:
        groups.setdefault(row["rules_sha256"], []).append(row)
    shortlist = []
    for group in groups.values():
        first = group[0]
        scores = [r["recorded_blue_score"] for r in group if r["recorded_blue_score"] is not None]
        shortlist.append({"representative_generation": first["generation"],
                          "candidate": f"candidates/blue-gen-{first['generation']:03d}.json",
                          "equivalent_generations": [r["generation"] for r in group],
                          "rule_count": first["rule_count"], "rules_sha256": first["rules_sha256"],
                          "recorded_score_range": [min(scores), max(scores)],
                          "status": "requires_game_compatibility_review_and_fresh_evaluation"})
    (ROOT / "shortlist.json").write_text(json.dumps(shortlist, indent=2) + "\n", encoding="utf-8")
    (ROOT / "candidate-index.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    columns = ["generation", "rule_count", "recorded_blue_score", "opponent_score_in_blue_evaluation",
               "selection", "checkpoint_matches_best", "score_records_agree", "rules_sha256"]
    with (ROOT / "candidate-index.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return result


def compare_engines():
    # Load only the reviewed deterministic engines/scoring, not the LLM runners.
    sys.path.insert(0, str(UP / "src"))
    sys.path.insert(0, str(ROOT.parents[1]))
    from environment.pgg import PublicGoodsEnvironment, PGGSettings, PGGActionRequest, PGGActionType
    from environment.game import AgentSpawn
    from experiments.pgg_scoring import compute_pgg_stability
    from pgg import Game, Config, Action, Agent

    names = [f"{f}{i}" for f in ("Blue", "Red") for i in range(1, 4)]

    def pair():
        original = PublicGoodsEnvironment(PGGSettings())
        original.reset([AgentSpawn(n, "cooperators" if n.startswith("Blue") else "free_riders",
                                  faction="blue" if n.startswith("Blue") else "red") for n in names])
        current = Game(Config(design="revised"), [Agent(n, "Blue" if n.startswith("Blue") else "Red") for n in names])
        return original, current

    def old(kind, **params):
        return PGGActionRequest(PGGActionType(kind), params)

    results = []
    # Exercise the common single-action domain, including growing wallets.
    for seed in range(5):
        rng = random.Random(seed)
        a, b = pair()
        for _ in range(20):
            fractions = {n: rng.choice([0, .05, .1, .6, 1]) for n in names}
            a.step({n: old("CONTRIBUTE", amount=a._wallets[n] * f) for n, f in fractions.items()})
            b.step({n: Action("contribute", fraction=f) for n, f in fractions.items()})
            assert all(math.isclose(a._wallets[n], b.wallets[n], rel_tol=1e-12, abs_tol=1e-9) for n in names)
            scores = compute_pgg_stability(a).faction_scores
            assert all(math.isclose(scores[f.lower()].S, b.scores()[f]["raw_score"], abs_tol=1e-12)
                       for f in ("Blue", "Red"))
        results.append({"case": f"contributions_and_scores_seed_{seed}", "rounds": 20, "result": "match"})
    a, b = pair()
    a.step({"Blue1": old("PUNISH", target="Red1", amount=15)})
    b.step({"Blue1": Action("punish", target="Red1", amount=15)})
    assert a._wallets == dict(b.wallets)
    results.append({"case": "ordinary_punishment", "result": "match"})

    a, b = pair()
    # All requests remain within the advertised original 0-50 severity range.
    setup_old = {n: old("PUNISH", target="Red1", amount=30) for n in names[:3]}
    setup_new = {n: Action("punish", target="Red1", amount=30) for n in names[:3]}
    a.step(setup_old)
    b.step(setup_new)
    a.step({"Blue1": old("PUNISH", target="Red1", amount=10),
            "Red1": old("PUNISH", target="Blue1", amount=10)})
    b.step({"Blue1": Action("punish", target="Red1", amount=10),
            "Red1": Action("punish", target="Blue1", amount=10)})
    assert a._wallets["Blue1"] == 88 and b.wallets["Blue1"] == 78
    results.append({"case": "punishment_order", "result": "different_as_expected",
                    "original_Blue1": 88, "current_Blue1": 78})

    a, b = pair()
    a.step({"Red1": old("PUNISH", target="Blue1", amount=49),
            "Red2": old("PUNISH", target="Blue1", amount=50)})
    b.step({"Red1": Action("punish", target="Blue1", amount=49),
            "Red2": Action("punish", target="Blue1", amount=50)})
    a.step({"Blue1": old("PUNISH", target="Red1", amount=10),
            **{n: old("CONTRIBUTE", amount=100) for n in names if n != "Blue1"}})
    try:
        b.step({"Blue1": Action("punish", target="Red1", amount=10),
                **{n: Action("contribute", fraction=1) for n in names if n != "Blue1"}})
    except ValueError:
        pass
    else:
        raise AssertionError("Current engine accepted unaffordable start-of-round punishment")
    assert any(e.get("action") == "PUNISH" for e in a.turn_log[1].events) and b.round == 1
    results.append({"case": "punishment_affordability", "result": "different_as_expected",
                    "note": "Original engine can spend this round's pool return; current rejects atomically."})

    a, b = pair()
    a.step({"Blue1": [old("CONTRIBUTE", amount=60), old("SEND_PRIVATE_MESSAGE", recipient="Blue2", message="hello")]})
    assert a._wallets["Blue1"] == 55 and "hello" in a._build_observations()["Blue2"]["private_messages"][0]
    try:
        b.step({"Blue1": [Action("contribute", fraction=.6), Action("broadcast", message="hello")]})
    except ValueError:
        pass
    else:
        raise AssertionError("Current engine accepted multiple actions")
    results.append({"case": "communication_plus_physical_action", "result": "different_as_expected"})

    a, b = pair()
    for _ in range(6):
        a.step({})
        b.step({})
    original_obs = a._build_observations()["Blue1"]
    current_obs = b.observe("Blue1")
    assert len(original_obs["round_history"]) == 5 and len(current_obs["history"]) == 6
    assert "team" in original_obs["residents"][0] and "wallet" not in original_obs["residents"][0]
    assert "wallet" in current_obs["players"][0]
    results.append({"case": "observation_information", "result": "different_as_expected",
                    "original_history_rounds": 5, "current_history_rounds": 6})
    (ROOT / "engine-checks.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    return results


def main():
    manifest = read(ROOT / "manifest.json")
    for entry in manifest["files"]:
        assert hashlib.sha256((UP / entry["path"]).read_bytes()).hexdigest() == entry["sha256"]
    candidates = audit_candidates()
    checks = compare_engines()
    print(f"Verified {len(manifest['files'])} source hashes; recovered 31 candidates, "
          f"{candidates['unique_rule_sets']} unique rule sets; passed {len(checks)} comparison cases.")
    print("Highest recorded Blue score:", max(r["recorded_blue_score"] for r in candidates["candidates"][1:]))


if __name__ == "__main__":
    main()
