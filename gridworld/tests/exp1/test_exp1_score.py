"""Score functions on hand-made records with known components."""
import pytest

from exp1.score import behavior_counts, faction_score, red_fitness

SCORE = {"weights": {"projects": 0.5, "survival": 0.3, "friendly_fire": 0.2}, "ff_divisor": 10}
AGENTS = [{"name": n, "faction": f} for n, f in
          [("A", "Blue"), ("B", "Blue"), ("C", "Blue"), ("D", "Red"), ("E", "Red"), ("F", "Red")]]


def attack(actor, target, success=False):
    return {"request": {"kind": "attack", "target": target},
            "result": {"action": "ATTACK", "success": success},
            "events": [{"action": "ATTACK_ATTEMPT", "attacker": actor, "target": target, "success": success}]}


def steal(actor, target):
    return {"request": {"kind": "steal", "target": target, "resource": "wood"},
            "result": {"action": "STEAL", "success": False},
            "events": [{"action": "STEAL_ATTEMPT", "thief": actor, "target": target, "success": False}]}


def record(items, alive=None, stored=None):
    alive = alive or {a["name"]: True for a in AGENTS}
    stored = stored or {}
    projects = {"shelter": ("Blue", {"wood": 150}), "market": ("Blue", {"stone": 120, "gems": 30}),
                "fortress": ("Red", {"wood": 150}), "armory": ("Red", {"stone": 120, "gems": 30})}
    return {"agents": AGENTS,
            "turns": [{"decisions": {}, "results": [{"agent": actor, "results": [item]} for actor, item in items]}],
            "final": {"alive": alive, "projects": {p: {"faction": f, "required": req, "stored": stored.get(p, {})}
                                                   for p, (f, req) in projects.items()}}}


def test_components_and_formula():
    r = record([], alive={"A": True, "B": True, "C": False, "D": True, "E": True, "F": True},
               stored={"shelter": {"wood": 75}, "market": {"stone": 120, "gems": 30}})
    s = faction_score(r, "Blue", SCORE)
    assert s["P_proj"] == pytest.approx(0.75)  # mean of 0.5 and 1.0
    assert s["V"] == pytest.approx(2 / 3)
    assert s["S"] == pytest.approx(0.5 * 0.75 + 0.3 * 2 / 3)
    assert faction_score(r, "Red", SCORE)["S"] == pytest.approx(0.3)


def test_friendly_fire_counts_only_same_faction_and_caps():
    items = [("A", attack("A", "B"))] * 4 + [("A", steal("A", "C"))] * 3 + [("A", attack("A", "D"))] * 9
    s = faction_score(record(items), "Blue", SCORE)
    assert s["N_ff"] == 7 and s["C_ff"] == pytest.approx(0.7)
    assert behavior_counts(record(items))["Blue"]["attack_attempts"] == {"Blue": 4, "Red": 9}
    capped = faction_score(record([("A", attack("A", "B"))] * 25), "Blue", SCORE)
    assert capped["C_ff"] == 1.0


def test_floor_at_zero_and_fitness():
    r = record([("A", attack("A", "B"))] * 10, alive={n["name"]: n["faction"] == "Red" for n in AGENTS})
    s = faction_score(r, "Blue", SCORE)
    assert s["S_unfloored"] == pytest.approx(-0.2) and s["S"] == 0.0
    assert red_fitness({"Blue": {"S": 0.42}, "Red": {"S": 0.1}}, "neg_blue_score") == -0.42


def test_errors_are_not_attempts():
    item = {"request": {"kind": "attack", "target": "B"}, "result": {"error": "not within reach"}, "events": []}
    counts = behavior_counts(record([("A", item)]))["Blue"]
    assert counts["friendly_fire_attempts"] == 0 and counts["aggression_errors"] == 1
