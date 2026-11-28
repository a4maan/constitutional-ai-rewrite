"""Configuration for the constitutional optimization project."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from importlib import import_module

try:  # pragma: no cover - optional dependency shim for type checkers
    load_dotenv = import_module("dotenv").load_dotenv 
except ModuleNotFoundError:  # pragma: no cover
    def load_dotenv(*_args, **_kwargs):
        return False

from config_prompts import PromptLibrary

BASE = Path(__file__).parent.parent

try:
    load_dotenv(BASE / ".env")
except PermissionError:
    pass


def _env_bool(key: str, default: bool) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(key: str, default: int) -> int:
    raw = os.getenv(key)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(key: str, default: float) -> float:
    raw = os.getenv(key)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


ACTION_COST_ENV_MAP: dict[str, tuple[str, int]] = {
    "MOVE": ("HUNGER_COST_MOVE", 0),
    "GATHER": ("HUNGER_COST_GATHER", 0),
    "DEPOSIT_WOOD": ("HUNGER_COST_DEPOSIT_WOOD", 0),
    "DEPOSIT_STONE": ("HUNGER_COST_DEPOSIT_STONE", 0),
    "COMMUNICATE": ("HUNGER_COST_COMMUNICATE", 0),
    "SEND_PRIVATE_MESSAGE": ("HUNGER_COST_SEND_PRIVATE_MESSAGE", 0),
    "REST": ("HUNGER_COST_REST", 0),
    "CONSUME_FOOD": ("HUNGER_COST_CONSUME_FOOD", 0),
    "GIVE_RESOURCE": ("HUNGER_COST_GIVE_RESOURCE", 0),
    "ATTACK": ("HUNGER_COST_ATTACK", 0),
    "STEAL": ("HUNGER_COST_STEAL", 0),
}


def _env_action_costs() -> dict[str, int]:
    costs: dict[str, int] = {}
    for action, (env_key, default) in ACTION_COST_ENV_MAP.items():
        costs[action] = _env_int(env_key, default)
    return costs


@dataclass(slots=True)
class HungerSettings:
    enabled: bool = field(default_factory=lambda: _env_bool("HUNGER_ENABLED", False))
    max_energy: int = field(default_factory=lambda: _env_int("HUNGER_MAX_ENERGY", 100))
    consumption_per_turn: int = field(default_factory=lambda: _env_int("HUNGER_COST_PER_TURN", 5))
    rest_recovery: int = field(default_factory=lambda: _env_int("HUNGER_REST_RECOVERY", 20))
    starvation_threshold: int = field(default_factory=lambda: _env_int("HUNGER_STARVATION_THRESHOLD", 0))
    leave_corpses: bool = field(default_factory=lambda: _env_bool("HUNGER_LEAVE_CORPSE", True))
    food_recovery_per_unit: int = field(
        default_factory=lambda: _env_int("HUNGER_FOOD_RECOVERY", 20)
    )
    action_costs: dict[str, int] = field(default_factory=_env_action_costs)


@dataclass(slots=True)
class AttackSettings:
    enabled: bool = field(default_factory=lambda: _env_bool("ATTACK_ENABLED", False))
    success_chance: float = field(default_factory=lambda: _env_float("ATTACK_SUCCESS_CHANCE", 0.25))


@dataclass(slots=True)
class StealSettings:
    enabled: bool = field(default_factory=lambda: _env_bool("STEAL_ENABLED", False))
    success_chance: float = field(default_factory=lambda: _env_float("STEAL_SUCCESS_CHANCE", 0.4))


@dataclass(slots=True)
class EnvironmentSettings:
    grid_width: int = field(default_factory=lambda: _env_int("GRID_WIDTH", 8))
    grid_height: int = field(default_factory=lambda: _env_int("GRID_HEIGHT", 8))
    review_interval: int = field(default_factory=lambda: _env_int("REVIEW_INTERVAL", 5))
    max_turns: int = field(default_factory=lambda: _env_int("MAX_TURNS", 50))
    random_seed: int | None = field(
        default=None if os.getenv("ENV_RANDOM_SEED") is None else _env_int("ENV_RANDOM_SEED", 0)
    )
    reveal_teams: bool = field(default_factory=lambda: _env_bool("REVEAL_TEAMS", True))
    hunger: HungerSettings = field(default_factory=HungerSettings)
    attack: AttackSettings = field(default_factory=AttackSettings)
    steal: StealSettings = field(default_factory=StealSettings)


@dataclass(slots=True)
class AgentRuntimeSettings:
    default_model: str = field(default_factory=lambda: os.getenv("DEFAULT_AGENT_MODEL", "openai/gpt-oss-120b"))
    temperature: float = field(default_factory=lambda: _env_float("AGENT_TEMPERATURE", 1.0))
    max_conversation_history: int = field(
        default_factory=lambda: _env_int("AGENT_MAX_HISTORY", 25)
    )  # Remember last 25 messages
    memory_reasoning_chars: int = field(
        default_factory=lambda: _env_int("AGENT_MEMORY_REASONING_CHARS", 400)
    )
    memory_message_chars: int = field(
        default_factory=lambda: _env_int("AGENT_MEMORY_MESSAGE_CHARS", 160)
    )
    memory_notification_chars: int = field(
        default_factory=lambda: _env_int("AGENT_MEMORY_NOTIFICATION_CHARS", 160)
    )
    enable_memory: bool = field(default_factory=lambda: _env_bool("AGENT_ENABLE_MEMORY", True))


@dataclass(slots=True)
class ToolingSettings:
    parallel_tool_calls: bool = field(default_factory=lambda: _env_bool("TOOL_PARALLEL_CALLS", True))
    prefer_auto_tool_choice: bool = field(default_factory=lambda: _env_bool("TOOL_AUTO_CHOICE", True))
    max_tool_calls_per_turn: int = field(default_factory=lambda: _env_int("MAX_TOOL_CALLS_PER_TURN", 1))


@dataclass(slots=True)
class VisualizerSettings:
    host: str = field(default_factory=lambda: os.getenv("VISUALIZER_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: _env_int("VISUALIZER_PORT", 8000))


@dataclass(slots=True)
class Config:
    openrouter_api_key: str | None = os.getenv("OPENROUTER_API_KEY")
    agent: AgentRuntimeSettings = field(default_factory=AgentRuntimeSettings)
    environment: EnvironmentSettings = field(default_factory=EnvironmentSettings)
    tooling: ToolingSettings = field(default_factory=ToolingSettings)
    prompts: PromptLibrary = field(default_factory=PromptLibrary)
    visualizer: VisualizerSettings = field(default_factory=VisualizerSettings)


config = Config()

__all__ = [
    "Config",
    "config",
    "AgentRuntimeSettings",
    "EnvironmentSettings",
    "HungerSettings",
    "AttackSettings",
    "StealSettings",
    "ToolingSettings",
    "VisualizerSettings",
]