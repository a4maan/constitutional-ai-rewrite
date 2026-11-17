"""Tests for the dynamic tool registry."""

from __future__ import annotations

from unittest.mock import MagicMock

from core.tools.registry import build_agent_tools
from environment.game import GridWorldEnvironment

EXPECTED_TOOL_ORDER = [
    "broadcast_message",
    "send_private_message",
    "request_observation_snapshot",
    "move_resident",
    "gather_resources",
    "deposit_resources",
    "rest_and_recover",
    "consume_food",
    "attack_resident",
    "steal_resource",
    "give_resource",
    "review_private_messages",
    "review_public_broadcasts",
]


def test_build_agent_tools_registers_expected_tools() -> None:
    """Tool registry should create the full, ordered toolkit."""
    env = GridWorldEnvironment()
    tools = build_agent_tools(env, "Aria")
    tool_names = [tool.name for tool in tools]

    assert tool_names == EXPECTED_TOOL_ORDER
    assert all(tool.handler is not None for tool in tools)


def test_move_tool_previews_action_without_mutation() -> None:
    env = GridWorldEnvironment()
    env.tool_move = MagicMock()

    tool_map = {tool.name: tool for tool in build_agent_tools(env, "Niko")}
    assert tool_map["move_resident"].invoke({"direction": "S"}) == "Will move S"
    env.tool_move.assert_not_called()


def test_observation_tool_previews_request_without_fetching_snapshot() -> None:
    env = GridWorldEnvironment()
    env.tool_observation_snapshot = MagicMock()

    tool_map = {tool.name: tool for tool in build_agent_tools(env, "Bryn")}
    tool = tool_map["request_observation_snapshot"]
    assert tool.invoke({"include_local_view": False}) == "Observation will be provided"
    env.tool_observation_snapshot.assert_not_called()
