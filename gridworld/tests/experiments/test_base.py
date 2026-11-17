"""Tests for ExperimentRunner helpers."""

from __future__ import annotations

from core.action_mapping import convert_tool_invocation


def test_convert_tool_invocation_move() -> None:
    action = convert_tool_invocation("move_resident", {"direction": "s"})
    assert action == {"action": "MOVE", "parameters": {"direction": "S"}}


def test_convert_tool_invocation_broadcast() -> None:
    action = convert_tool_invocation("broadcast_message", {"message": "Team up!"})
    assert action == {"action": "COMMUNICATE", "parameters": {"message": "Team up!"}}


def test_convert_tool_invocation_invalid_args() -> None:
    assert convert_tool_invocation("move_resident", {"direction": 42}) is None

