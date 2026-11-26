"""Convert PGG tool invocations into PGGActionRequest-compatible dicts."""

from __future__ import annotations

from typing import Any


def convert_pgg_tool_invocation(name: str, args: dict[str, Any]) -> dict[str, Any] | None:
    if not name:
        return None

    if name == "contribute_to_pool":
        amount = args.get("amount", 0)
        return {"action": "CONTRIBUTE", "parameters": {"amount": float(amount)}}

    if name == "punish_agent":
        target = args.get("target")
        amount = args.get("amount", 0)
        if isinstance(target, str):
            return {
                "action": "PUNISH",
                "parameters": {"target": target, "amount": float(amount)},
            }
        return None

    if name == "broadcast_message":
        message = args.get("message")
        if isinstance(message, str):
            return {"action": "COMMUNICATE", "parameters": {"message": message}}
        return None

    if name == "send_private_message":
        recipient = args.get("recipient")
        message = args.get("message")
        if isinstance(recipient, str) and isinstance(message, str):
            return {
                "action": "SEND_PRIVATE_MESSAGE",
                "parameters": {"recipient": recipient, "message": message},
            }
        return None

    if name == "rest":
        return {"action": "REST", "parameters": {}}

    return None


__all__ = ["convert_pgg_tool_invocation"]
