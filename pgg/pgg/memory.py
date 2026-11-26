"""Lightweight resident memory helpers used by controllers and the visualizer."""

from __future__ import annotations

from collections import deque
from typing import Any, Sequence


def sanitize_memory_entry(value: Any) -> str:
    """Normalize memory strings by stripping whitespace and collapsing spaces."""
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    return " ".join(text.split())


class ResidentMemoryBuffer:
    """Rolling buffer that turns turn data into short memory strings."""

    def __init__(
        self,
        capacity: int = 8,
        *,
        reasoning_limit: int = 200,
        message_limit: int = 80,
        notification_limit: int = 100,
    ) -> None:
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self.capacity = capacity
        self._entries: deque[str] = deque(maxlen=capacity)
        self._reasoning_limit = max(1, reasoning_limit)
        self._message_limit = max(1, message_limit)
        self._notification_limit = max(1, notification_limit)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def record(
        self,
        *,
        turn: int,
        observation: dict[str, Any] | None,
        reasoning: str | None,
        payloads: Sequence[dict[str, Any]] | None = None,
    ) -> list[str]:
        """Add a new summary string built from the latest turn."""
        entry = self._build_entry(
            turn=turn,
            observation=observation or {},
            reasoning=reasoning,
            payloads=payloads or [],
        )
        if entry:
            self._entries.append(entry)
        return self.snapshot()

    def snapshot(self) -> list[str]:
        """Return a copy of the buffered memory strings."""
        return list(self._entries)

    def load(self, entries: Sequence[str]) -> list[str]:
        """Replace the buffer with precomputed entries (used by overrides/tests)."""
        self._entries.clear()
        for entry in entries or []:
            cleaned = sanitize_memory_entry(entry)
            if cleaned:
                self._entries.append(cleaned)
        return self.snapshot()

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _build_entry(
        self,
        *,
        turn: int,
        observation: dict[str, Any],
        reasoning: str | None,
        payloads: Sequence[dict[str, Any]],
    ) -> str:
        parts: list[str] = []
        parts.append(self._turn_fragment(turn, observation.get("position")))

        hunger_fragment = self._hunger_fragment(observation.get("hunger_state"))
        if hunger_fragment:
            parts.append(hunger_fragment)

        if reasoning:
            cleaned_reasoning = self._truncate(reasoning, self._reasoning_limit)
            if cleaned_reasoning:
                parts.append(f"Thought: {cleaned_reasoning}")

        actions_fragment = self._actions_fragment(payloads)
        if actions_fragment:
            parts.append(actions_fragment)

        notifications_fragment = self._notifications_fragment(observation.get("notifications"))
        if notifications_fragment:
            parts.append(notifications_fragment)

        # Filter out any empty fragments before joining
        filtered = [fragment for fragment in parts if fragment]
        return " — ".join(filtered)

    @staticmethod
    def _turn_fragment(turn: int, position: Any) -> str:
        fragment = f"Turn {turn}"
        coords = ResidentMemoryBuffer._coords(position)
        if coords is not None:
            row, col = coords
            fragment += f" @ ({row}, {col})"
        return fragment

    @staticmethod
    def _coords(position: Any) -> tuple[int, int] | None:
        if isinstance(position, (list, tuple)) and len(position) == 2:
            row, col = position
            if isinstance(row, int) and isinstance(col, int):
                return row, col
        return None

    def _hunger_fragment(self, hunger_state: Any) -> str:
        if not isinstance(hunger_state, dict):
            return ""
        energy = hunger_state.get("energy")
        status = hunger_state.get("status") or hunger_state.get("state")
        if energy is None and not status:
            return ""
        fragment = f"Energy {energy}" if energy is not None else "Energy"
        if status:
            fragment += f" ({sanitize_memory_entry(status)})"
        return fragment

    def _actions_fragment(self, payloads: Sequence[dict[str, Any]]) -> str:
        if not payloads:
            return ""

        phrases: list[str] = []
        for payload in payloads:
            action, params = self._normalize_payload(payload)
            if not action:
                continue
            phrase = self._action_phrase(action, params)
            if phrase:
                phrases.append(phrase)

        if not phrases:
            return ""
        return "Actions: " + "; ".join(phrases)

    @staticmethod
    def _normalize_payload(payload: Any) -> tuple[str, dict[str, Any]]:
        if isinstance(payload, dict):
            action = payload.get("action")
            params = payload.get("parameters") or {}
        else:  # Fallback for dataclasses like ActionRequest
            action = getattr(payload, "action", None)
            params = getattr(payload, "parameters", {}) or {}

        if hasattr(action, "value"):
            action = action.value

        action_name = str(action).upper() if action else ""
        params_dict = dict(params) if isinstance(params, dict) else {}
        return action_name, params_dict

    def _action_phrase(self, action: str, params: dict[str, Any]) -> str:
        action = action.upper()
        if action == "MOVE":
            direction = sanitize_memory_entry(params.get("direction"))
            return f"moved {direction}" if direction else "moved"
        if action == "GATHER":
            resource = sanitize_memory_entry(params.get("resource") or "resources")
            return f"gathered {resource}"
        if action in {"DEPOSIT_WOOD", "DEPOSIT_STONE"}:
            resource = sanitize_memory_entry(
                params.get("resource") or ("wood" if action == "DEPOSIT_WOOD" else "stone")
            )
            project = sanitize_memory_entry(params.get("project"))
            phrase = f"deposited {resource}"
            if project:
                phrase += f" to {project}"
            return phrase
        if action == "REST":
            return "rested"
        if action == "CONSUME_FOOD":
            quantity = params.get("quantity")
            if isinstance(quantity, int):
                return f"ate {quantity} food"
            return "ate food"
        if action == "COMMUNICATE":
            message = self._truncate(params.get("message"), self._message_limit)
            return f'broadcasted "{message}"' if message else "broadcasted a message"
        if action == "SEND_PRIVATE_MESSAGE":
            recipient = sanitize_memory_entry(params.get("recipient"))
            message = self._truncate(params.get("message"), self._message_limit)
            if recipient and message:
                return f'messaged {recipient}: "{message}"'
            if recipient:
                return f"messaged {recipient}"
            return "sent a private message"
        if action == "GIVE_RESOURCE":
            recipient = sanitize_memory_entry(params.get("recipient"))
            resource = sanitize_memory_entry(params.get("resource") or "resource")
            quantity = params.get("quantity")
            prefix = f"gave {quantity} {resource}" if isinstance(quantity, int) else f"gave {resource}"
            if recipient:
                prefix += f" to {recipient}"
            return prefix
        if action == "ATTACK":
            target = sanitize_memory_entry(params.get("target"))
            return f"attacked {target}" if target else "attacked"
        if action == "STEAL":
            resource = sanitize_memory_entry(params.get("resource") or "resource")
            target = sanitize_memory_entry(params.get("target"))
            if target:
                return f"tried to steal {resource} from {target}"
            return f"tried to steal {resource}"

        # Default: fallback to lowercase action name for visibility
        return action.lower()

    def _notifications_fragment(self, notifications: Any) -> str:
        if not isinstance(notifications, list):
            return ""
        recent = []
        for note in notifications[-2:]:
            cleaned = self._truncate(note, self._notification_limit)
            if cleaned:
                recent.append(cleaned)
        if not recent:
            return ""
        return "Alerts: " + " | ".join(recent)

    @staticmethod
    def _truncate(value: Any, limit: int) -> str:
        text = sanitize_memory_entry(value)
        if not text:
            return ""
        if len(text) <= limit:
            return text
        return text[: limit - 3].rstrip() + "..."


__all__ = ["ResidentMemoryBuffer", "sanitize_memory_entry"]

