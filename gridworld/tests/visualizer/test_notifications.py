"""Tests ensuring notifications surface in the visualizer."""

from __future__ import annotations

from config import EnvironmentSettings, HungerSettings
from environment.game import AgentSpawn, GridWorldEnvironment
from visualizer.state import WorldStateSerializer


def test_recent_notifications_visible_in_visualizer() -> None:
    settings = EnvironmentSettings(hunger=HungerSettings(enabled=False))
    env = GridWorldEnvironment(settings=settings)
    env.reset([AgentSpawn(agent_id="Aria", team_id="alpha")])
    state = env.agent_states["Aria"]

    GridWorldEnvironment._queue_notification(state, "Bryn attacked you on turn 3.")

    observations = env._build_observations()
    assert observations["Aria"]["notifications"] == ["Bryn attacked you on turn 3."]
    assert state.recent_notifications == ["Bryn attacked you on turn 3."]
    assert state.notifications == []

    serializer = WorldStateSerializer(env)
    snapshot = serializer.snapshot()
    agent_entry = next(res for res in snapshot["residents"] if res["name"] == "Aria")
    assert "Bryn attacked you on turn 3." in agent_entry["notifications"]

