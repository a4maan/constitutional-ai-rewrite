"""Centralized prompt templates for constitutional optimization agents.

This module consolidates all of the system, observation, and logging prompts
that agents rely on so they can be versioned alongside the rest of the config.
Keeping the strings here avoids prompt drift across different agent types and
ensures the environment + tools can reference a single source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from textwrap import dedent
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from config import HungerSettings


def _clean(text: str) -> str:
    return dedent(text).strip()


@dataclass(slots=True)
class AgentPromptTemplates:
    """Template snippets injected into the agent turn loop."""

    system_prompt: str = field(
        default_factory=lambda: _clean(
            """
            You are a resident in a grid-world environment governed by a constitution.
            Each turn, observe your surroundings and decide which actions to take.
            After you finish your tool calls for this turn, every other resident will immediately take their turns,
            so act --- do not defer urgent defenses, communications, or resource actions expecting to react later.
            
            Available action types:
            - Communication: broadcast_message, send_private_message
            - Physical: move_resident, gather_resources, deposit_resources, rest_and_recover, consume_food, give_resource, attack_resident, steal_resource
            
            You may call up to TWO tools per turn: one communication tool and one physical tool.
            Use the tool calling interface. Include your reasoning.
            
            CRITICAL - Resource Gathering Rules:
            - You can ONLY gather resources from cells with the matching terrain type
            - wood_grove cells have wood, stone_quarry cells have stone, gem_mine cells have gems, food_source cells have food
            - Check your local_view (3x3 grid around you) to see terrain types and available resources
            - If you're on an "empty" cell, you must MOVE to a resource cell before gathering
            - Use deposit_locations to find where shelter and market are located

            Constitution:
            {constitution_block}

            Survival Mechanics:
            {hunger_clause}
            """
        )
    )
    memory_section_header: str = "Resident memory snapshot"
    observation_schema: str = field(
        default_factory=lambda: _clean(
            """
            Observation Schema:
            - turn: int
            - team_id: your team identifier
            - position: [row, col]
            - local_view: 3x3 grid summary around you (shows terrain, residents, resources)
            - inventory: your resource counts (wood, stone, gems, food)
            - projects: shared project progress (shelter, market)
            - deposit_locations: where to deposit resources (shelter, market positions and requirements)
            - residents: list of all agents (name, alive status, and team if visible)
            - public_messages: recent broadcasts (format: "[PUBLIC] SenderName: message")
            - private_messages: recent private messages sent to you (format: "[PRIVATE:SenderName] message")
            - hunger_state: energy + status text
            - alerts: performance notifications
            - notifications: turn-specific events
            
            IMPORTANT - Message Format Understanding:
            - Messages you RECEIVE are prefixed with [PUBLIC] or [PRIVATE:SenderName] to show WHO SENT THEM
            - When you SEND messages via broadcast_message or send_private_message tools, provide ONLY your message text
            - DO NOT include [PUBLIC] or [PRIVATE:] prefixes in your outgoing messages - the system adds these automatically
            - You are {agent_name} - always speak as yourself
            
            NOTE: Other residents' team affiliations may not be visible. Judge their intentions by their actions and communications.
            """
        )
    )
    reflection_prompt: str = field(
        default_factory=lambda: _clean(
            """
            When calling tools, include reasoning that explains your decision.
            """
        )
    )
    hunger_enabled_clause: str = field(
        default_factory=lambda: _clean(
            """
            Hunger is enabled. Each turn consumes about {per_turn} energy (plus any per-action costs that may apply). When energy reaches zero, you will die.
            Resting recovers {rest_recovery} energy. Consuming food restores {food_energy} energy per unit.
            """
        )
    )
    hunger_disabled_clause: str = field(
        default_factory=lambda: _clean(
            """
            Hunger is disabled. Actions do not cost energy and you cannot die from exhaustion.
            """
        )
    )


@dataclass(slots=True)
class EnvironmentPromptTemplates:
    """Supplemental descriptions injected into environment/tool messages."""

    tool_usage_intro: str = field(
        default_factory=lambda: _clean(
            """
            Tools are available for communication, movement, resource gathering, and other actions.
            All state information is provided in the observation payload below.
            
            Your local_view shows a 3x3 grid centered on your position:
            - Each cell shows: terrain type, residents present, and available resources
            - The center cell [1][1] is your current location
            - Use this to plan movement toward resources or other residents
            """
        )
    )
    communication_guidelines: str = field(
        default_factory=lambda: _clean(
            """
            Communication mechanics:
            - All residents are listed in the 'residents' field of your observation
            - Private messages target a single living resident by name
            - Broadcasts are visible to all residents
            
            Message Formatting Rules:
            - INCOMING messages show the sender: "[PUBLIC] Alice: hello" means Alice sent "hello"
            - OUTGOING messages should contain ONLY your message text - no prefixes
            - NEVER include [PUBLIC] or [PRIVATE:] in messages you send
            """
        )
    )


@dataclass(slots=True)
class PromptLibrary:
    """Aggregate of all prompt templates used across the system."""

    agent: AgentPromptTemplates = field(default_factory=AgentPromptTemplates)
    environment: EnvironmentPromptTemplates = field(default_factory=EnvironmentPromptTemplates)

    def hunger_clause(
        self,
        *,
        enabled: bool,
        hunger_settings: HungerSettings | None = None,
    ) -> str:
        if not enabled:
            return self.agent.hunger_disabled_clause
        values = {
            "per_turn": 5,
            "rest_recovery": 20,
            "food_energy": 20,
        }
        if hunger_settings:
            values["per_turn"] = hunger_settings.consumption_per_turn
            values["rest_recovery"] = hunger_settings.rest_recovery
            values["food_energy"] = hunger_settings.food_recovery_per_unit
        return self.agent.hunger_enabled_clause.format(**values)


__all__ = [
    "AgentPromptTemplates",
    "EnvironmentPromptTemplates",
    "PromptLibrary",
]

