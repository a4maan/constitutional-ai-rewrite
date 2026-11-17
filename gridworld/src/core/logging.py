"""Shared logging helpers for resident controllers."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from util.logger import Logger


class AgentTurnLog(BaseModel):
    """Structured record for a single agent decision."""

    turn: int | None = None
    agent: str
    observation: dict[str, Any] = Field(default_factory=dict)
    thought: str | None = None
    action: str | None = None
    parameters: dict[str, Any] | None = None
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    tool_results: list[dict[str, Any]] = Field(default_factory=list)
    hunger_state: dict[str, Any] | None = None
    messages: list[dict[str, Any]] = Field(default_factory=list)
    raw_response: Any = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AgentEventEmitter:
    """Bridge between a resident controller and the shared Logger."""

    def __init__(self, agent_name: str, logger: Logger | None, *, subdir: str = "residents") -> None:
        self.agent_name = agent_name
        self.logger = logger
        self.subdir = subdir

    def emit(self, event: AgentTurnLog) -> None:
        if not self.logger:
            return
        relative_path = f"{self.subdir}/{self.agent_name}.jsonl"
        payload = event.model_dump(exclude_none=True)
        json_block = json.dumps(payload, indent=2, default=self._json_default)
        self.logger.append_text(relative_path, json_block)

    @staticmethod
    def _json_default(value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat()
        raise TypeError(f"Object of type {value.__class__.__name__} is not JSON serializable")


def prune_observation(observation: dict[str, Any] | None) -> dict[str, Any]:
    """Strip large sections from the observation payload before logging.
    
    Note: This only affects what gets written to log files, NOT what agents see.
    Agents receive the full observation including local_view, deposit_locations, etc.
    """
    if not observation:
        return {}
    return {
        "turn": observation.get("turn"),
        "team_id": observation.get("team_id"),
        "position": observation.get("position"),
        "inventory": observation.get("inventory"),
        "projects": observation.get("projects"),
        "hunger_state": observation.get("hunger_state"),
        "notifications": (observation.get("notifications") or [])[-3:],
    }


__all__ = ["AgentTurnLog", "AgentEventEmitter", "prune_observation"]

