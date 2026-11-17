"""Tests for hunger configuration knobs."""

from __future__ import annotations

from environment.game import (
    ActionRequest,
    ActionType,
    AgentSpawn,
    GridWorldEnvironment,
)
from config import EnvironmentSettings, HungerSettings


def _make_env(hunger: HungerSettings) -> GridWorldEnvironment:
    settings = EnvironmentSettings(hunger=hunger)
    return GridWorldEnvironment(settings=settings, logger=None)


def test_food_recovery_uses_configured_value() -> None:
    hunger = HungerSettings(
        enabled=True,
        max_energy=100,
        consumption_per_turn=0,
        rest_recovery=10,
        food_recovery_per_unit=15,
        action_costs={"CONSUME_FOOD": 0},
    )
    env = _make_env(hunger)
    env.reset([AgentSpawn(agent_id="Aria", team_id="alpha")])
    state = env.agent_states["Aria"]
    assert state.hunger
    state.hunger.energy = 40
    state.inventory["food"] = 5

    actions = {
        "Aria": ActionRequest(
            action=ActionType.CONSUME_FOOD,
            parameters={"quantity": 2},
        )
    }
    env.step(actions)

    assert state.hunger.energy == 70  # 40 + (2 * 15)


def test_action_cost_consumes_energy() -> None:
    hunger = HungerSettings(
        enabled=True,
        max_energy=100,
        consumption_per_turn=0,
        action_costs={"MOVE": 7},
    )
    env = _make_env(hunger)
    env.reset([AgentSpawn(agent_id="Bryn", team_id="beta")])
    state = env.agent_states["Bryn"]
    assert state.hunger
    state.hunger.energy = 100

    actions = {
        "Bryn": ActionRequest(
            action=ActionType.MOVE,
            parameters={"direction": "N"},
        )
    }
    env.step(actions)

    assert state.hunger.energy == 93  # 100 - 7

