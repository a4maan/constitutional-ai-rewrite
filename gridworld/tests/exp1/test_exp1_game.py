"""Adversarial gridworld rules."""
import json

from environment.game import ActionRequest, ActionType
from exp1.game import AdversarialGridWorld

GAME = json.loads(open(__file__.rsplit("/tests/", 1)[0] + "/exp1-configs/pilot.json").read())["game"]


def act(env, name, action, **params):
    return env.play_turn({name: [({"kind": action.value}, ActionRequest(action, params))]})[1]


def members(env, faction):
    return [n for n, f in sorted(env.faction_of.items()) if f == faction]


def test_seed_fixes_factions_and_spawns():
    a, b = AdversarialGridWorld(GAME, 7), AdversarialGridWorld(GAME, 7)
    assert a.faction_of == b.faction_of and a.spawns == b.spawns
    assert sorted(a.faction_of.values()) == ["Blue"] * 3 + ["Red"] * 3
    assert len({tuple(p) for p in a.spawns.values()}) == 6


def test_deposit_only_to_own_projects():
    env = AdversarialGridWorld(GAME, 1)
    blue = members(env, "Blue")[0]
    env.agent_states[blue].inventory["wood"] = 10
    log = act(env, blue, ActionType.DEPOSIT_STONE, resource="wood", project="fortress")
    assert "error" in log[[e["agent"] for e in log].index(blue)]["results"][0]["result"]
    act(env, blue, ActionType.DEPOSIT_STONE, resource="wood", project="shelter")
    assert env.projects["shelter"].stored == {"wood": 10} and env.projects["fortress"].stored == {}


def test_observation_hides_factions():
    env = AdversarialGridWorld(GAME, 3)
    text = json.dumps(env.observe(members(env, "Blue")[0]))
    assert "Blue" not in text and "Red" not in text and "team" not in text


def test_attack_kills_drops_inventory_and_dead_agent_cannot_act():
    game = dict(GAME, attack_success=1.0)
    env = AdversarialGridWorld(game, 5)
    red, blue = members(env, "Red")[0], members(env, "Blue")[0]
    env.agent_states[blue].position = env.agent_states[red].position
    env.agent_states[blue].inventory["wood"] = 4
    order, log = env.play_turn({
        red: [({"kind": "attack"}, ActionRequest(ActionType.ATTACK, {"target": blue}))],
        blue: [({"kind": "move"}, ActionRequest(ActionType.MOVE, {"direction": "N"}))]})
    assert not env.agent_states[blue].alive
    assert env.agent_states[blue].inventory["wood"] == 0
    blue_entry = log[order.index(blue)]["results"][0]
    if order.index(blue) > order.index(red):
        assert blue_entry["skipped"]


def test_steal_moves_one_unit():
    env = AdversarialGridWorld(dict(GAME, steal_success=1.0), 5)
    red, blue = members(env, "Red")[0], members(env, "Blue")[0]
    env.agent_states[blue].position = env.agent_states[red].position
    env.agent_states[blue].inventory["stone"] = 3
    act(env, red, ActionType.STEAL, target=blue, resource="stone")
    assert env.agent_states[blue].inventory["stone"] == 2 and env.agent_states[red].inventory["stone"] == 1
