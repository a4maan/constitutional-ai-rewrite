"""Helpers for converting tool invocations into environment actions."""

from __future__ import annotations

from typing import Any


def convert_tool_invocation(name: str, args: dict[str, Any]) -> dict[str, Any] | None:
    if not name:
        return None

    if name == "move_resident":
        direction = args.get("direction")
        if isinstance(direction, str):
            return {"action": "MOVE", "parameters": {"direction": direction.upper()}}
        return None

    if name == "gather_resources":
        resource = args.get("resource")
        if isinstance(resource, str):
            return {"action": "GATHER", "parameters": {"resource": resource.lower()}}
        return None

    if name == "deposit_resources":
        resource = (args.get("resource") or "").lower()
        project = args.get("project", "shelter")
        if resource == "wood":
            return {"action": "DEPOSIT_WOOD", "parameters": {"project": project}}
        if resource:
            return {
                "action": "DEPOSIT_STONE",
                "parameters": {"project": project, "resource": resource},
            }
        return None

    if name == "rest_and_recover":
        return {"action": "REST", "parameters": {}}
    
    if name == "consume_food":
        quantity = args.get("quantity", 1)
        if isinstance(quantity, int) and quantity > 0:
            return {"action": "CONSUME_FOOD", "parameters": {"quantity": quantity}}
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
    
    if name == "give_resource":
        recipient = args.get("recipient")
        resource = args.get("resource")
        quantity = args.get("quantity", 1)
        if isinstance(recipient, str) and isinstance(resource, str) and isinstance(quantity, int):
            return {
                "action": "GIVE_RESOURCE",
                "parameters": {
                    "recipient": recipient,
                    "resource": resource.lower(),
                    "quantity": quantity,
                },
            }
        return None

    if name == "attack_resident":
        target = args.get("target")
        if isinstance(target, str):
            return {
                "action": "ATTACK",
                "parameters": {"target": target},
            }
        return None
    
    if name == "steal_resource":
        target = args.get("target")
        resource = args.get("resource")
        if isinstance(target, str) and isinstance(resource, str):
            return {
                "action": "STEAL",
                "parameters": {
                    "target": target,
                    "resource": resource.lower(),
                },
            }
        return None

    return None


__all__ = ["convert_tool_invocation"]

