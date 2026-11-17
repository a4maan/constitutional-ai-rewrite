"""Tests for society log output for communications."""

from __future__ import annotations

from config import EnvironmentSettings, HungerSettings
from environment.game import ActionRequest, ActionType, AgentSpawn, GridWorldEnvironment
from util.logger import Logger


def _make_env(tmp_path, agent_ids: list[str]) -> tuple[GridWorldEnvironment, Logger]:
    logger = Logger("logging-events", base_dir=tmp_path, use_timestamp=False)
    hunger = HungerSettings(enabled=False)
    settings = EnvironmentSettings(hunger=hunger)
    env = GridWorldEnvironment(settings=settings, logger=logger)
    spawns = [AgentSpawn(agent_id=name, team_id="team") for name in agent_ids]
    env.reset(spawns)
    return env, logger


def test_public_broadcast_logged(tmp_path) -> None:
    env, logger = _make_env(tmp_path, ["Aria"])
    actions = {
        "Aria": ActionRequest(
            action=ActionType.COMMUNICATE,
            parameters={"message": "Hello everyone!"},
        )
    }
    env.step(actions)
    log_text = logger.read_text("society.log")
    assert "Aria broadcasted" in log_text
    assert "Hello everyone!" in log_text


def test_private_message_logged(tmp_path) -> None:
    env, logger = _make_env(tmp_path, ["Aria", "Bryn"])
    actions = {
        "Aria": ActionRequest(
            action=ActionType.SEND_PRIVATE_MESSAGE,
            parameters={"recipient": "Bryn", "message": "Meet me at the market."},
        )
    }
    env.step(actions)
    log_text = logger.read_text("society.log")
    assert "Aria privately messaged Bryn" in log_text
    assert "Meet me at the market." in log_text

