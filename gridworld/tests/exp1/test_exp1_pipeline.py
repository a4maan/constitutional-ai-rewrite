"""Constitution checks, game record, evaluator with a fake model, and Optimizer A logging. No API calls."""
import copy
import json
from pathlib import Path

import pytest

from exp1.play import digest, play_game
from exp1.run import constitution, evaluate, execute, stage_a
from exp1.score import faction_score

CONFIG = json.loads((Path(__file__).parents[2] / "exp1-configs" / "pilot.json").read_text())
CONFIG["game"]["turns"] = 4
CONFIG["selection_seeds"], CONFIG["evaluation_seeds"], CONFIG["stage_a_seeds"] = [1, 2], [3, 4], [5]


class FakeModel:
    """Scripted answers. Agents gather; every 7th call is malformed; mutations follow a script."""

    def __init__(self, mutations=()):
        self.calls, self.mutations, self.requests = 0, list(mutations), []

    def complete(self, messages, seed, purpose):
        self.calls += 1
        self.requests.append((purpose, messages))
        if purpose == "constitution_mutation":
            return self.mutations.pop(0)
        if self.calls % 7 == 0:
            return {"action": {"kind": "fly"}}
        return {"message": None, "action": {"kind": "gather", "resource": "wood"}, "explanation": "x"}


def test_constitution_validation():
    constitution({"name": "ok", "rules": ["a"]})
    for bad in [{"name": "x", "rules": []}, {"name": "", "rules": ["a"]}, {"name": "x", "rules": [""]},
                {"name": "x", "rules": ["a"] * 21}, {"rules": ["a"]}, "text"]:
        with pytest.raises(ValueError):
            constitution(bad)


def test_record_fields_and_scores_recompute():
    r = play_game(CONFIG["blue"], CONFIG["red_seed"], 11, CONFIG, None, mock=True)
    for key in ("blue_id", "red_id", "seed", "scores", "fitness", "blue_material", "behavior", "turns",
                "agents", "final", "complete", "initial_state"):
        assert key in r
    assert r["blue_id"] == digest(CONFIG["blue"]) and r["red_id"] == digest(CONFIG["red_seed"])
    assert set(r["turns"][0]) == {"turn", "order", "decisions", "results", "state"}
    for f in ("Blue", "Red"):
        assert r["scores"][f] == faction_score(r, f, CONFIG["score"])
    assert r["fitness"]["Red"] == -r["scores"]["Blue"]["S"]


def test_evaluator_mean_and_invalid_output(tmp_path):
    model = FakeModel()
    result = evaluate(CONFIG["blue"], CONFIG["red_seed"], [1, 2], tmp_path, CONFIG, model, False)
    values = [e["fitness"] for e in result["episodes"]]
    assert result["red_optimization_mean"] == pytest.approx(sum(values) / 2)
    record = json.loads((tmp_path / "seed-1.json").read_text())
    assert record["scores"] == result["episodes"][0]["scores"]
    invalid = sum(b["invalid_outputs"] for b in record["behavior"].values())
    assert invalid > 0
    # Agents spawn on empty cells, so "gather wood" reaches the engine and fails there as a logged error.
    assert record["behavior"]["Blue"]["action_errors"] > 0
    first = record["turns"][0]["results"][0]["results"][0]
    assert first["request"]["kind"] in ("gather", "rest") and "result" in first
    calls = model.calls
    evaluate(CONFIG["blue"], CONFIG["red_seed"], [1, 2], tmp_path, CONFIG, model, False)
    assert model.calls == calls  # complete saved games are reused


def test_optimizer_a_logs_losers_invalid_and_keeps_parent_on_tie(tmp_path):
    config = copy.deepcopy(CONFIG)
    # Candidate 1 is invalid 3 times in a row, so it stays invalid after the retries.
    mutations = [{"name": "c0", "rules": ["Gather wood."]}, {"bad": True}, {"bad": 2}, {"bad": 3},
                 {"name": "c2", "rules": ["Gather stone."]}, {"name": "c3", "rules": ["Rest."]}]
    summary = execute(config, tmp_path / "run", model=FakeModel(mutations))
    out = tmp_path / "run"
    assert summary["status"] == "complete" and summary["optimizer"] == "A"
    g1 = summary["generations"][0]
    assert [c["valid"] for c in g1["selection"]] == [True, False]
    assert "red_optimization_mean" not in g1["selection"][1]  # invalid: no score
    assert (out / "generation-001" / "candidate-0.json").exists()
    for row in summary["generations"]:
        best = max([row["parent_selection"]["red_optimization_mean"]] +
                   [c["red_optimization_mean"] for c in row["selection"] if c["valid"]])
        if best == row["parent_selection"]["red_optimization_mean"]:
            assert row["selected_red_id"] == row["previous_red_id"]
        assert all({"blue_id", "red_t_id", "red_t1_id"} <= set(p) for p in row["paired_heldout_changes"])
    events = [json.loads(line)["event"] for line in (out / "events.jsonl").read_text().splitlines()]
    assert "mutation_invalid" in events and events.count("selection") == 2
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["git"]["commit"] and manifest["sources"]


class BadAgentModel(FakeModel):
    """Every agent answer is invalid."""

    def complete(self, messages, seed, purpose):
        self.calls += 1
        return {"action": {"kind": "fly"}}


def test_invalid_answer_is_retried_with_correction_never_rest(tmp_path):
    model = FakeModel()
    evaluate(CONFIG["blue"], CONFIG["red_seed"], [1], tmp_path, CONFIG, model, False)
    record = json.loads((tmp_path / "seed-1.json").read_text())
    rejected = [d for t in record["turns"] for d in t["decisions"].values() if d["rejected"]]
    assert rejected and all(d["answer"]["action"]["kind"] == "gather" for d in rejected)
    assert all(r["error"] for d in rejected for r in d["rejected"])
    corrections = [m for _, msgs in model.requests for m in msgs if "failed validation" in m["content"]]
    assert corrections  # the retry carries the correction message
    assert not any(i["request"]["kind"] == "rest" for t in record["turns"] for e in t["results"]
                   for i in e["results"])  # no rest is substituted


def test_three_invalid_answers_fail_the_evaluation(tmp_path):
    from exp1.run import Journal, assess
    model = BadAgentModel()
    result = assess(Journal(tmp_path / "events.jsonl"), CONFIG["blue"], CONFIG["red_seed"], [1],
                    tmp_path / "e", CONFIG, model, False)
    assert result["valid"] is False and "3 attempts" in result["error"]
    assert "red_optimization_mean" not in result


def test_overlapping_seeds_rejected(tmp_path):
    config = copy.deepcopy(CONFIG)
    config["evaluation_seeds"] = [2, 9]
    with pytest.raises(ValueError):
        execute(config, tmp_path / "run", mock=True)


def test_stage_a_mock_with_bot(tmp_path):
    rows = stage_a(CONFIG, tmp_path / "a", mock=True, only="Hunt-and-kill bot")
    assert rows[0]["valid"]
    r = json.loads((tmp_path / "a" / "stage-a" / "hunt-and-kill-bot" / "seed-5.json").read_text())
    assert r["red_controller"] == "hunt_and_kill"
    assert r["behavior"]["Red"]["steal_attempts"] == {"Blue": 0, "Red": 0}
