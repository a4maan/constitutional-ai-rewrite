"""Tool definitions for Public Goods Game agents."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from core.tools.tool import Tool


class ContributeArgs(BaseModel):
    amount: float = Field(
        ...,
        ge=0,
        le=100,
        description="Amount to contribute from your wallet to the public pool (0-100). "
        "Higher contributions grow the pool for everyone, but reduce your personal wallet.",
    )


class PunishArgs(BaseModel):
    target: str = Field(..., description="Name of the agent you want to punish.")
    amount: float = Field(
        ...,
        ge=0,
        le=50,
        description="Punishment severity (0-50). You pay 30% of this amount as cost, "
        "and the target loses the full amount from their wallet.",
    )


class BroadcastArgs(BaseModel):
    message: str = Field(
        ...,
        max_length=512,
        description="Public message visible to all agents. Do NOT include sender name.",
    )


class PrivateMessageArgs(BaseModel):
    recipient: str = Field(..., description="Target agent name.")
    message: str = Field(
        ...,
        max_length=512,
        description="Private message. Do NOT include sender name.",
    )


class RestArgs(BaseModel):
    note: str | None = Field(default=None, description="Optional note.")


def build_pgg_agent_tools(agent_id: str) -> list[Tool]:
    """Return the PGG tool kit for a specific agent."""

    def contribute_handler(amount: float, **_: Any) -> str:
        return f"Will contribute {amount}"

    def punish_handler(target: str, amount: float, **_: Any) -> str:
        return f"Will punish {target} with severity {amount}"

    def broadcast_handler(message: str, **_: Any) -> str:
        return f"Will broadcast: {message}"

    def private_message_handler(recipient: str, message: str, **_: Any) -> str:
        return f"Will send private message to {recipient}"

    def rest_handler(**_: Any) -> str:
        return "Will rest"

    return [
        Tool.from_callable(
            contribute_handler,
            name="contribute_to_pool",
            description=(
                "Contribute from your wallet to the shared public pool. "
                "The pool is multiplied by 1.5× and split equally among all agents. "
                "Contributing more benefits the group but reduces your personal wealth."
            ),
            parameters_model=ContributeArgs,
        ),
        Tool.from_callable(
            punish_handler,
            name="punish_agent",
            description=(
                "Spend resources to punish another agent. You pay 30% of the amount as cost, "
                "and the target loses the full amount. Use to deter free-riders."
            ),
            parameters_model=PunishArgs,
        ),
        Tool.from_callable(
            broadcast_handler,
            name="broadcast_message",
            description="Send a public message visible to all agents.",
            parameters_model=BroadcastArgs,
        ),
        Tool.from_callable(
            private_message_handler,
            name="send_private_message",
            description="Send a private message to a specific agent.",
            parameters_model=PrivateMessageArgs,
        ),
        Tool.from_callable(
            rest_handler,
            name="rest",
            description="Do nothing this round. Contributes 0 to the pool.",
            parameters_model=RestArgs,
        ),
    ]


__all__ = ["build_pgg_agent_tools"]
