"""Tests for logging helpers."""

from __future__ import annotations

from core.logging import prune_observation


def test_prune_observation_limits_notifications() -> None:
    observation = {
        "turn": 5,
        "team_id": "market",
        "position": [1, 2],
        "inventory": {"wood": 1},
        "projects": {"market": 0.1},
        "hunger_state": {"energy": 80, "status": "Peckish"},
        "notifications": ["a", "b", "c", "d"],
    }

    pruned = prune_observation(observation)

    assert pruned["turn"] == 5
    assert pruned["notifications"] == ["b", "c", "d"]

