"""Serialization helpers for exposing world state to the visualizer."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from environment.game import GridWorldEnvironment


class WorldStateSerializer:
    """Serializes the grid and resident state for clients."""

    def __init__(
        self,
        env: GridWorldEnvironment,
        resident_metadata: Callable[[str], dict[str, Any]] | None = None,
    ):
        self.env = env
        self.current_agent: str | None = None  # Track which agent is currently processing
        self._resident_metadata = resident_metadata

    def set_current_agent(self, agent_name: str | None) -> None:
        """Set which agent is currently taking their turn."""
        self.current_agent = agent_name

    def snapshot(self) -> dict[str, Any]:
        data = {
            "turn": self.env.turn,
            "max_turns": self.env.settings.max_turns,
            "grid": self._serialize_grid(),
            "residents": self._serialize_residents(),
            "projects": {name: proj.progress for name, proj in self.env.projects.items()},
            "current_agent": self.current_agent,
        }
        return data

    def render_template(self) -> str:
        """Load and return the HTML template."""
        template_path = Path(__file__).parent / "template.html"
        return template_path.read_text()

    def _serialize_grid(self) -> list[list[dict[str, Any]]]:
        rows: list[list[dict[str, Any]]] = []
        for r in range(self.env.settings.grid_height):
            row: list[dict[str, Any]] = []
            for c in range(self.env.settings.grid_width):
                cell = self.env.grid[r][c]
                row.append(
                    {
                        "terrain": cell.cell_type.value,
                        "residents": [
                            {
                                "name": resident_id,
                                "alive": self.env.agent_states[resident_id].alive,
                            }
                            for resident_id in cell.agents_present
                        ],
                        "corpses": [corpse.description for corpse in cell.corpses],
                        "dropped_items": cell.dropped_items,
                    }
                )
            rows.append(row)
        return rows

    def _serialize_residents(self) -> list[dict[str, Any]]:
        """Serialize resident data including internal state."""
        residents: list[dict[str, Any]] = []
        for resident in self.env.agent_states.values():
            agent_data = {
                "name": resident.agent_id,
                "team": resident.team_id,
                "position": resident.position,
                "alive": resident.alive,
                "inventory": resident.inventory,
                "notifications": getattr(resident, "recent_notifications", [])[-5:],
                "inbox_public": resident.inbox_public[-5:],  # Last 5 public messages
                "inbox_private": resident.inbox_private[-5:],  # Last 5 private messages
            }
            
            # Add hunger state if available
            if resident.hunger:
                agent_data["energy"] = resident.hunger.energy
                agent_data["hunger_status"] = resident.hunger.status_text
            
            # Add last thought and tool call (would be populated by resident controller)
            # These would be set by the experiment runner when processing agent turns
            agent_data["last_thought"] = getattr(resident, "last_thought", None)
            agent_data["last_tool_call"] = getattr(resident, "last_tool_call", None)

            metadata = self._metadata_for(resident.agent_id)
            if metadata:
                agent_data.update(metadata)
            
            residents.append(agent_data)
        return residents

    def _metadata_for(self, agent_name: str) -> dict[str, Any]:
        if not self._resident_metadata:
            return {}
        try:
            return self._resident_metadata(agent_name) or {}
        except Exception:
            return {}

