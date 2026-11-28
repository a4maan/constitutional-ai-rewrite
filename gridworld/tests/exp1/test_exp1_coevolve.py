"""Pilot 2 and 3 runner: step order, aligned held-out pairs, both IDs on every row, reuse, seed checks. No API."""
import copy
import json
from pathlib import Path

import pytest

import exp1.coevolve as co
from exp1.play import digest

CONFIGS = Path(__file__).parents[2] / "exp1-configs"
ALT = json.loads((CONFIGS / "pilot3-alternating.json").read_text())
FIXED = json.loads((CONFIGS / "pilot2-blue-vs-red.json").read_text())
ALT["generations"] = FIXED["generations"] = 2


class Mutator:
    """Each mutation adds 1 rule, so every challenger wins (scripted evaluator below)."""

    def __init__(self):
        self.purposes, self.calls = [], 0

    def complete(self, messages, seed, purpose):
        self.calls += 1
        self.purposes.append(purpose)
        parent = json.loads(messages[1]["content"])["parent"]
        return {"name": parent["name"] + "+", "rules": parent["rules"] + [f"rule {self.calls}"]}


@pytest.fixture
def scripted(monkeypatch):
    """S_Blue grows with Blue's rule count and falls with Red's rule count."""
    played = []

    def assess(journal, blue, red, seeds, folder, config, model, mock, **kwargs):
        played.append((digest(blue), digest(red), tuple(seeds)))
        s = 0.05 * len(blue["rules"]) - 0.04 * len(red["rules"])
        episodes = [{"seed": x, "blue_id": digest(blue), "red_id": digest(red), "fitness": -s, "blue_fitness": s,
                     "scores": {"Blue": {"S": s}, "Red": {"S": 0.1}}, "behavior": {}} for x in seeds]
        return {"valid": True, "blue_id": digest(blue), "red_id": digest(red), "episodes": episodes,
                "red_optimization_mean": -s, "blue_optimization_mean": s}

    monkeypatch.setattr(co, "assess", assess)
    return played


def test_alternating_order_aligned_pairs_and_ids(tmp_path, scripted):
    model = Mutator()
    summary = co.run(copy.deepcopy(ALT), tmp_path / "r", model=model)
    out = tmp_path / "r"
    assert summary["status"] == "complete"
    assert model.purposes == ["blue_constitution_mutation"] * 2 + ["red_constitution_mutation"] * 2 + \
        ["blue_constitution_mutation"] * 2 + ["red_constitution_mutation"] * 2
    ids = {(side, g): digest(json.loads((out / f"{side}-{g:03d}.json").read_text()))
           for side in ("blue", "red") for g in range(3)}
    for g, row in enumerate(summary["generations"], start=1):
        assert row["blue_step"]["opponent_id"] == ids["red", g - 1]   # B_g selected against R_(g-1)
        assert row["red_step"]["opponent_id"] == ids["blue", g]       # R_g selected against B_g
        assert row["blue_step"]["selected_id"] == ids["blue", g] != ids["blue", g - 1]
        for step in ("blue_step", "red_step"):
            assert all({"constitution_id", "opponent_id"} <= set(c) for c in row[step]["selection"])
    pairs = [(h["blue_generation"], h["red_generation"]) for h in summary["heldout"]]
    assert pairs == [(0, 0), (1, 0), (1, 1), (2, 1), (2, 2)]
    for h in summary["heldout"]:
        assert h["blue_id"] == ids["blue", h["blue_generation"]] and h["red_id"] == ids["red", h["red_generation"]]
        assert all(e["blue_id"] == h["blue_id"] and e["red_id"] == h["red_id"] for e in h["episodes"])
    assert "aligned" in summary["heldout"][2]["label"]
    assert [p["change"] for p in summary["paired_changes"]] == ["Blue step", "Red step"] * 2
    assert len(scripted) == len(set(scripted))  # no (Blue, Red, seeds) evaluation is played twice


def test_blue_vs_fixed_red_keeps_red(tmp_path, scripted):
    summary = co.run(copy.deepcopy(FIXED), tmp_path / "f", model=Mutator())
    assert summary["status"] == "complete"
    assert [(h["blue_generation"], h["red_generation"]) for h in summary["heldout"]] == [(0, 0), (1, 0), (2, 0)]
    assert not (tmp_path / "f" / "red-001.json").exists() and (tmp_path / "f" / "blue-002.json").exists()
    assert all("red_step" not in row for row in summary["generations"])


def test_mutator_prompt_hides_attacks_and_opponent(tmp_path, scripted):
    from exp1.run import mutator_prompt
    model = Mutator()
    requests = []
    original = model.complete
    model.complete = lambda m, s, p: (requests.append(m), original(m, s, p))[1]
    co.run(copy.deepcopy(FIXED), tmp_path / "p", model=model)
    system = requests[0][0]["content"]
    assert system == mutator_prompt(FIXED, "Blue") and system.startswith("Improve Blue's")
    user = json.loads(requests[0][1]["content"])
    assert user["opponent_constitution"] is None
    text = json.dumps(user["parent_evaluation"])
    for key in ("red_optimization_mean", "neg_blue_score", '"fitness"'):
        assert key not in text  # the Blue mutator never sees Red's objective
    assert "blue_optimization_mean" in text and "scores" in text


def test_red_and_blue_selection_seeds_must_be_disjoint(tmp_path):
    config = copy.deepcopy(ALT)
    config["red_selection_seeds"] = [config["blue_selection_seeds"][0], 999]
    with pytest.raises(ValueError):
        co.run(config, tmp_path / "x", mock=True)


def test_red_vs_fixed_blue_keeps_blue(tmp_path, scripted):
    config = json.loads((CONFIGS / "pilot1-deep-red-vs-blue.json").read_text())
    config["generations"] = 2
    model = Mutator()
    summary = co.run(config, tmp_path / "r", model=model)
    assert summary["status"] == "complete" and set(model.purposes) == {"red_constitution_mutation"}
    assert [(h["blue_generation"], h["red_generation"]) for h in summary["heldout"]] == [(0, 0), (0, 1), (0, 2)]
    assert not (tmp_path / "r" / "blue-001.json").exists() and (tmp_path / "r" / "red-002.json").exists()
