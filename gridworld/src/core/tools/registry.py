"""Factory helpers that bind environment utilities to Tool objects."""

from __future__ import annotations

from typing import Any, Iterable, Sequence

from pydantic import BaseModel, Field, create_model

from core.tools.tool import Tool
from environment.game import GridWorldEnvironment


class BroadcastArgs(BaseModel):
    message: str = Field(..., max_length=512, description="Your message text only. Do NOT include [PUBLIC] or sender name - those are added automatically.")


class PrivateMessageArgs(BaseModel):
    recipient: str = Field(..., description="Target recipient name.")
    message: str = Field(..., max_length=512, description="Your message text only. Do NOT include [PRIVATE:] or sender name - those are added automatically.")


class ObservationArgs(BaseModel):
    include_local_view: bool = Field(default=True)
    include_inventory: bool = Field(default=True)


class MoveArgs(BaseModel):
    direction: str = Field(
        ...,
        description="Cardinal direction to travel (N, S, E, W).",
        pattern="^[NSEW]$",
    )


class GatherArgs(BaseModel):
    resource: str = Field(..., description="Resource to gather (wood, stone, gems, food).")


class DepositArgs(BaseModel):
    resource: str = Field(..., description="Resource to deposit (wood, stone, gems, food).")
    project: str = Field(..., description="Project to contribute toward (shelter or market).")


class RestArgs(BaseModel):
    note: str | None = Field(
        default=None,
        description="Optional note describing why you are resting.",
    )


class AttackArgs(BaseModel):
    target: str = Field(..., description="Name of the nearby resident you wish to strike.")


class StealArgs(BaseModel):
    target: str = Field(..., description="Resident you wish to steal from.")
    resource: str = Field(..., description="Resource name to attempt to take.")


class GiveResourceArgs(BaseModel):
    recipient: str = Field(..., description="Name of the resident to give the resource to.")
    resource: str = Field(..., description="Resource to give (wood, stone, gems, or food).")
    quantity: int = Field(
        default=1,
        ge=1,
        le=100,
        description="Amount of the resource to give (1-100).",
    )


class PrivateMessagesArgs(BaseModel):
    sender: str | None = Field(
        default=None,
        description="Filter messages from this resident (optional).",
    )
    limit: int = Field(default=5, ge=1, le=20)


class PublicMessagesArgs(BaseModel):
    limit: int = Field(default=5, ge=1, le=20)


def _build_consume_food_args(energy_per_unit: int) -> type[BaseModel]:
    description = (
        f"Number of food units to consume (1-10). Each unit restores {energy_per_unit} energy."
    )
    return create_model(
        f"ConsumeFoodArgs_{energy_per_unit}",
        quantity=(int, Field(default=1, ge=1, le=10, description=description)),
    )


def build_agent_tools(env: GridWorldEnvironment, agent_id: str) -> list[Tool]:
    """Return the standard tool kit bound to a specific agent.
    
    These tools are used to define the schema for LangChain's tool calling.
    The handlers are placeholders - actual execution happens via action conversion.
    """

    def broadcast_handler(message: str, **_: Any) -> str:
        return f"Will broadcast: {message}"

    def private_message_handler(recipient: str, message: str, **_: Any) -> str:
        return f"Will send private message to {recipient}: {message}"

    def observation_handler(
        include_local_view: bool = True,
        include_inventory: bool = True,
        **_: Any,
    ) -> str:
        return "Observation will be provided"

    def move_handler(direction: str, **_: Any) -> str:
        return f"Will move {direction.upper()}"

    def gather_handler(resource: str, **_: Any) -> str:
        return f"Will gather {resource}"

    def deposit_handler(resource: str, project: str, **_: Any) -> str:
        return f"Will deposit {resource} to {project}"

    def rest_handler(**_: Any) -> str:
        return "Will rest"
    
    def consume_food_handler(quantity: int = 1, **_: Any) -> str:
        return f"Will consume {quantity} food"

    def attack_handler(target: str, **_: Any) -> str:
        return f"Will attack {target}"

    def steal_handler(target: str, resource: str, **_: Any) -> str:
        return f"Will steal {resource} from {target}"
    
    def give_resource_handler(recipient: str, resource: str, quantity: int = 1, **_: Any) -> str:
        return f"Will give {quantity} {resource} to {recipient}"

    def private_messages_handler(sender: str | None = None, limit: int = 5, **_: Any) -> str:
        return "Will fetch private messages"

    def public_messages_handler(limit: int = 5, **_: Any) -> str:
        return "Will fetch public messages"

    food_energy = env.hunger_settings.food_recovery_per_unit
    consume_food_args_model = _build_consume_food_args(food_energy)

    return [
        Tool.from_callable(
            broadcast_handler,
            name="broadcast_message",
            description="Send a public broadcast to everyone. Provide ONLY your message text - the system automatically adds [PUBLIC] and your name.",
            parameters_model=BroadcastArgs,
        ),
        Tool.from_callable(
            private_message_handler,
            name="send_private_message",
            description="Send a private message to a single person. Provide ONLY your message text - the system automatically adds [PRIVATE:YourName] prefix.",
            parameters_model=PrivateMessageArgs,
        ),
        Tool.from_callable(
            observation_handler,
            name="request_observation_snapshot",
            description="Fetch your local view of the world.",
            parameters_model=ObservationArgs,
        ),
        Tool.from_callable(
            move_handler,
            name="move_resident",
            description="Travel one cell in a cardinal direction (N, S, E, W). Use this to move around.",
            parameters_model=MoveArgs,
        ),
        Tool.from_callable(
            gather_handler,
            name="gather_resources",
            description="Collect resources from the current cell. You must be on the correct terrain type: wood_grove for wood, stone_quarry for stone, gem_mine for gems, food_source for food. Check your local_view to see your current terrain.",
            parameters_model=GatherArgs,
        ),
        Tool.from_callable(
            deposit_handler,
            name="deposit_resources",
            description="Contribute gathered resources to a project. You can deposit from anywhere, but check deposit_locations in your observation to see what each project accepts (shelter wants wood, market wants stone/gems).",
            parameters_model=DepositArgs,
        ),
        Tool.from_callable(
            rest_handler,
            name="rest_and_recover",
            description="Pause to recover energy when exhaustion looms.",
            parameters_model=RestArgs,
        ),
        Tool.from_callable(
            consume_food_handler,
            name="consume_food",
            description=f"Consume food from your inventory to restore energy. Each food unit restores {food_energy} energy.",
            parameters_model=consume_food_args_model,
        ),
        Tool.from_callable(
            attack_handler,
            name="attack_resident",
            description="Attempt to kill a resident within your 3x3 local view. Cannot target yourself. Only has a chance to succeed.",
            parameters_model=AttackArgs,
        ),
        Tool.from_callable(
            steal_handler,
            name="steal_resource",
            description="Attempt to lift a resource from a resident within your 3x3 local view. Cannot target yourself. Only has a chance to succeed.",
            parameters_model=StealArgs,
        ),
        Tool.from_callable(
            give_resource_handler,
            name="give_resource",
            description="Give some number of a resource from your inventory to another resident within your 3x3 local view. Cannot give to yourself.",
            parameters_model=GiveResourceArgs,
        ),
        Tool.from_callable(
            private_messages_handler,
            name="review_private_messages",
            description="Review recent private messages, optionally filtering by sender.",
            parameters_model=PrivateMessagesArgs,
        ),
        Tool.from_callable(
            public_messages_handler,
            name="review_public_broadcasts",
            description="Review the latest public broadcasts.",
            parameters_model=PublicMessagesArgs,
        ),
    ]


def build_tool_index(env: GridWorldEnvironment, agent_ids: Iterable[str]) -> dict[str, Sequence[Tool]]:
    """Utility that builds a mapping of agent_id -> Tool list."""
    return {agent_id: build_agent_tools(env, agent_id) for agent_id in agent_ids}


__all__ = ["build_agent_tools", "build_tool_index"]

