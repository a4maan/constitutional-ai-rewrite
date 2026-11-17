"""LangChain-powered resident controller."""

from __future__ import annotations

import json
from typing import Any, Sequence

from langchain_core.tools import StructuredTool
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field, create_model
from langchain_openai import ChatOpenAI

from config import config, HungerSettings
from config_prompts import PromptLibrary
from core.action_mapping import convert_tool_invocation
from core.logging import AgentEventEmitter, AgentTurnLog, prune_observation
from core.constitution import Constitution
from core.memory import ResidentMemoryBuffer, sanitize_memory_entry
from core.tools.tool import Tool


class LangChainResident:
    """Resident controller that delegates reasoning to LangChain."""

    def __init__(
        self,
        name: str,
        *,
        constitution: Constitution,
        tools: Sequence[Tool],
        hunger_enabled: bool,
        hunger_settings: HungerSettings | None = None,
        logger: Any | None = None,
        prompt_library: PromptLibrary | None = None,
        llm: ChatOpenAI | None = None,
    ) -> None:
        self.name = name
        self.constitution = constitution
        self.prompt_library = prompt_library or config.prompts
        self.hunger_enabled = hunger_enabled
        self.hunger_settings = hunger_settings or config.environment.hunger
        self.logger = logger
        self.event_emitter = AgentEventEmitter(name, logger, subdir="residents") if logger else None
        self.system_prompt = self._build_system_prompt()
        self._tools = [tool for tool in tools if tool.name != "consult_memory"]
        self._langchain_tools = [self._to_langchain_tool(tool) for tool in self._tools]
        self._llm = llm or self._build_llm()
        self._llm_with_tools = self._llm.bind_tools(list(self._langchain_tools))
        # Store last internal state for visualizer
        self._last_thought: str | None = None
        self._last_tool_call: list[dict[str, Any]] | None = None
        # Lightweight episodic memory for prompts + visualizer
        self._memory_capacity = max(1, config.agent.max_conversation_history)
        self._memory_buffer: ResidentMemoryBuffer | None = (
            ResidentMemoryBuffer(
                capacity=self._memory_capacity,
                reasoning_limit=config.agent.memory_reasoning_chars,
                message_limit=config.agent.memory_message_chars,
                notification_limit=config.agent.memory_notification_chars,
            )
            if config.agent.enable_memory
            else None
        )
        self.memory_snapshot: list[str] = []

    def decide_action(self, *, observation: dict[str, Any], turn: int) -> list[dict[str, Any]]:
        """Process agent decision, allowing both communication and physical actions per turn.
        
        Returns a list of action payloads (can be empty, have one action, or multiple actions).
        Agents can do one communication action (broadcast/private message) AND one physical action
        (move, gather, rest, etc.) per turn.
        """
        user_input = self._format_observation(observation)
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=user_input),
        ]
        try:
            response = self._llm_with_tools.invoke(messages)
        except Exception as exc:  # pragma: no cover - runtime safeguard
            if self.logger:
                self.logger.log(f"{self.name} failed to plan action: {exc}", filename="errors.log")
            return []

        # Use LangChain's parsed tool_calls instead of raw additional_kwargs
        tool_calls_list = getattr(response, "tool_calls", None) or []
        if not tool_calls_list:
            # Fallback to raw format if tool_calls attribute not available
            raw_tool_calls = (response.additional_kwargs or {}).get("tool_calls") or []
            if not raw_tool_calls:
                reasoning = self._response_reasoning(response)
                self._last_thought = reasoning
                self._last_tool_call = None
                self._log_turn(
                    turn=turn,
                    observation=observation,
                    reasoning=reasoning,
                    action_payload=None,
                    tool_name="",
                    tool_args={},
                    tool_result="",
                    final_output=response.content,
                )
                self._record_memory_snapshot(
                    observation=observation,
                    payloads=[],
                    turn=turn,
                    reasoning=reasoning,
                )
                return []
            # Convert raw format to parsed format
            tool_calls_list = []
            for raw_call in raw_tool_calls:
                function = raw_call.get("function") or {}
                tool_calls_list.append({
                    "name": function.get("name", ""),
                    "args": self._parse_tool_input(function.get("arguments"))
                })
        
        # Process all tool calls and convert to action payloads
        payloads = []
        communication_tools = {"broadcast_message", "send_private_message"}
        physical_tools = {"move_resident", "gather_resources", "deposit_resources", "rest_and_recover", 
                         "consume_food", "give_resource", "attack_resident", "steal_resource"}
        
        has_communication = False
        has_physical = False
        all_tool_calls = []
        reasoning_text = None
        
        for tool_call in tool_calls_list:
            tool_name = tool_call.get("name", "")
            tool_args = dict(tool_call.get("args", {}))  # Make a copy
            
            # Extract reasoning from first tool call
            if not reasoning_text:
                reasoning_text = tool_args.pop("reasoning", None)
            else:
                tool_args.pop("reasoning", None)  # Remove from subsequent calls
            
            # Track for logging
            all_tool_calls.append({"name": tool_name, "arguments": tool_args})
            
            # Check if we've already used this action type
            if tool_name in communication_tools and has_communication:
                continue  # Skip additional communication actions
            if tool_name in physical_tools and has_physical:
                continue  # Skip additional physical actions
            
            payload = convert_tool_invocation(tool_name, tool_args)
            if payload:
                payloads.append(payload)
                if tool_name in communication_tools:
                    has_communication = True
                elif tool_name in physical_tools:
                    has_physical = True
        
        # Store internal state for visualizer (store ALL tool calls, not just first)
        self._last_thought = reasoning_text or self._response_reasoning(response)
        self._last_tool_call = all_tool_calls if all_tool_calls else None
        
        # Log the turn with all tool calls and all payloads
        self._log_turn_multi(
            turn=turn,
            observation=observation,
            reasoning=self._last_thought,
            action_payloads=payloads,
            tool_calls=all_tool_calls,
            final_output=response.content,
        )

        self._record_memory_snapshot(
            observation=observation,
            payloads=payloads,
            turn=turn,
            reasoning=self._last_thought,
        )
        
        return payloads

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _build_system_prompt(self) -> str:
        constitution_block = self.constitution.export_rules()
        hunger_clause = self.prompt_library.hunger_clause(
            enabled=self.hunger_enabled,
            hunger_settings=self.hunger_settings if self.hunger_enabled else None,
        )
        return self.prompt_library.agent.system_prompt.format(
            constitution_block=constitution_block,
            hunger_clause=hunger_clause,
        )

    def _format_observation(self, observation: dict[str, Any]) -> str:
        schema = self.prompt_library.agent.observation_schema.format(agent_name=self.name)
        env_guidance = self.prompt_library.environment.tool_usage_intro
        memory_block = self._render_memory_context()
        payload = json.dumps(observation, indent=2, sort_keys=True)
        return f"{memory_block}{schema}\n\n{env_guidance}\n\nObservation Payload:\n{payload}"

    def _to_langchain_tool(self, tool: Tool) -> StructuredTool:
        def _handler(**kwargs: Any) -> str:
            return json.dumps({"tool": tool.name, "arguments": kwargs})

        args_schema = self._augment_args_model(tool.args_model)

        return StructuredTool.from_function(
            func=_handler,
            name=tool.name,
            description=tool.description,
            args_schema=args_schema,
        )

    @staticmethod
    def _augment_args_model(args_model: type[BaseModel] | None) -> type[BaseModel]:
        fields: dict[str, tuple[Any, Any]] = {}
        if args_model:
            for name, field in args_model.model_fields.items():
                annotation = field.annotation or Any
                default = field.default if not field.is_required else ...
                fields[name] = (annotation, default)
        fields["reasoning"] = (
            str,
            Field(
                ...,
                description="Briefly explain your plan and decision.",
            ),
        )
        model_name = (args_model.__name__ if args_model else "Tool") + "WithReasoning"
        return create_model(model_name, **fields)  # type: ignore[arg-type]

    def _build_llm(self) -> ChatOpenAI:
        if not config.openrouter_api_key:
            raise RuntimeError("OPENROUTER_API_KEY is required for LangChain residents.")
        return ChatOpenAI(
            model=config.agent.default_model,
            temperature=config.agent.temperature,
            openai_api_key=config.openrouter_api_key,
            base_url="https://openrouter.ai/api/v1",
            max_retries=2,
        )

    @staticmethod
    def _parse_tool_input(raw: Any) -> dict[str, Any]:
        if raw is None:
            return {}
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                return {"__raw": raw}
        return {"__raw": raw}

    def _log_turn_multi(
        self,
        *,
        turn: int,
        observation: dict[str, Any],
        reasoning: str | None,
        action_payloads: list[dict[str, Any]],
        tool_calls: list[dict[str, Any]],
        final_output: Any,
    ) -> None:
        """Log a turn with potentially multiple tool calls and actions."""
        if not self.event_emitter:
            return
        pruned_observation = prune_observation(observation)
        
        # Use first action payload for primary action field (for backwards compatibility)
        first_payload = action_payloads[0] if action_payloads else None
        
        log = AgentTurnLog(
            turn=turn,
            agent=self.name,
            observation=pruned_observation,
            thought=reasoning,
            action=first_payload.get("action") if first_payload else None,
            parameters=first_payload.get("parameters") if first_payload else None,
            tool_calls=tool_calls,  # Log ALL tool calls
            tool_results=[{"name": tc["name"], "content": ""} for tc in tool_calls],  # Empty results for now
            hunger_state=observation.get("hunger_state"),
            messages=[],
            raw_response={"output": final_output},
        )
        self.event_emitter.emit(log)
    
    def _log_turn(
        self,
        *,
        turn: int,
        observation: dict[str, Any],
        reasoning: str | None,
        action_payload: dict[str, Any] | None,
        tool_name: str,
        tool_args: dict[str, Any],
        tool_result: str | None,
        final_output: Any,
    ) -> None:
        """Legacy logging method for single tool call (kept for compatibility)."""
        if not self.event_emitter:
            return
        pruned_observation = prune_observation(observation)
        log = AgentTurnLog(
            turn=turn,
            agent=self.name,
            observation=pruned_observation,
            thought=reasoning,
            action=action_payload.get("action") if action_payload else None,
            parameters=action_payload.get("parameters") if action_payload else None,
            tool_calls=[{"name": tool_name, "arguments": tool_args}],
            tool_results=[{"name": tool_name, "content": tool_result or ""}],
            hunger_state=observation.get("hunger_state"),
            messages=[],
            raw_response={"output": final_output},
        )
        self.event_emitter.emit(log)

    @staticmethod
    def _response_reasoning(response: Any) -> str | None:
        content = getattr(response, "content", None)
        if isinstance(content, str):
            return content.strip() or None
        return None

    def set_memory_snapshot(self, entries: Sequence[str] | None) -> None:
        """Update the cached memory snapshot used by the visualizer."""
        values = entries or []
        if self._memory_buffer:
            self.memory_snapshot = self._memory_buffer.load(values)
        else:
            cleaned = [sanitize_memory_entry(entry) for entry in values]
            self.memory_snapshot = [entry for entry in cleaned if entry]

    def _render_memory_context(self) -> str:
        if not self._memory_buffer or not self.memory_snapshot:
            return ""
        window = self.memory_snapshot[-self._memory_capacity :]
        header = self.prompt_library.agent.memory_section_header
        lines = "\n".join(f"- {entry}" for entry in window)
        return f"{header}:\n{lines}\n\n"

    def _record_memory_snapshot(
        self,
        *,
        observation: dict[str, Any] | None,
        payloads: Sequence[dict[str, Any]] | None,
        turn: int,
        reasoning: str | None,
    ) -> None:
        if not self._memory_buffer:
            return
        snapshot = self._memory_buffer.record(
            turn=turn,
            observation=observation or {},
            reasoning=reasoning,
            payloads=payloads or [],
        )
        self.memory_snapshot = snapshot


__all__ = ["LangChainResident"]

