"""Reusable experiment harness for constitutional optimization runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import json
import threading
from typing import Any, Iterable

import uvicorn

from config import config
from core.constitution import Constitution, MoralRule
from core.langchain_resident import LangChainResident
from core.tools.registry import build_agent_tools
from environment.game import ActionRequest, ActionType, AgentSpawn, GridWorldEnvironment
from util.logger import Logger
from visualizer.server import VisualizerServer
from visualizer.state import WorldStateSerializer


@dataclass(slots=True)
class ResidentProfile:
    name: str
    team: str
    constitution_rules: list[MoralRule] | None = None


@dataclass(slots=True)
class ExperimentConfig:
    name: str
    description: str
    residents: list[ResidentProfile]
    constitution_rules: list[MoralRule] = field(default_factory=list)
    environment_overrides: dict[str, Any] = field(default_factory=dict)
    use_resident_constitutions: bool = False


class ExperimentRunner:
    """Runs an experiment with reusable hooks for observers/visualizers."""

    def __init__(
        self,
        exp_config: ExperimentConfig,
        enable_visualizer: bool = True,
        visualizer_host: str | None = None,
        visualizer_port: int | None = None,
        use_resident_constitutions: bool | None = None,
    ):
        self.exp_config = exp_config
        self.logger = Logger(exp_config.name)
        self.env = GridWorldEnvironment(settings=config.environment, logger=self.logger)
        self.residents: dict[str, LangChainResident] = {}
        self.enable_visualizer = enable_visualizer
        self._visualizer_server: VisualizerServer | None = None
        self._visualizer_thread: threading.Thread | None = None
        self._visualizer_host = visualizer_host or config.visualizer.host
        self._visualizer_port = visualizer_port or config.visualizer.port
        self._serializer: WorldStateSerializer | None = None
        # Use CLI flag if provided, otherwise use experiment config default
        self.use_resident_constitutions = (
            use_resident_constitutions 
            if use_resident_constitutions is not None 
            else exp_config.use_resident_constitutions
        )

    def apply_overrides(self) -> None:
        for key, value in self.exp_config.environment_overrides.items():
            current = getattr(self.env.settings, key)
            if isinstance(value, dict):
                self._deep_update(current, value)
            else:
                setattr(self.env.settings, key, value)

    def build_residents(self) -> None:
        shared_constitution = Constitution(rules=list(self.exp_config.constitution_rules))
        for profile in self.exp_config.residents:
            constitution = shared_constitution
            if self.use_resident_constitutions and profile.constitution_rules:
                constitution = Constitution(rules=list(profile.constitution_rules))
            tools = build_agent_tools(self.env, profile.name)
            controller = LangChainResident(
                profile.name,
                constitution=constitution,
                tools=tools,
                hunger_enabled=self.env.hunger_settings.enabled,
                hunger_settings=self.env.hunger_settings,
                logger=self.logger,
            )
            self.residents[controller.name] = controller

    def run(self, max_turns: int | None = None) -> None:
        self.apply_overrides()
        self.build_residents()
        spawns: Iterable[AgentSpawn] = [
            AgentSpawn(agent_id=profile.name, team_id=profile.team)
            for profile in self.exp_config.residents
        ]
        observations = self.env.reset(spawns)
        
        # Save experiment configuration to JSON
        self._save_experiment_config(max_turns)
        
        if self.enable_visualizer:
            self._start_visualizer()
        self._log_console("Simulation started.")

        total_turns = max_turns or self.env.settings.max_turns
        for turn in range(1, total_turns + 1):
            actions = self._collect_actions(observations, turn)
            total_actions = sum(len(agent_actions) for agent_actions in actions.values())
            self._log_console(f"Turn {turn}: collected {total_actions} actions from {len(actions)} residents.")
            observations = self.env.step(actions)

        self._log_console("Experiment complete.")
        for name, project in self.env.projects.items():
            self._log_console(f"{name} progress: {project.progress:.2%}")

    def _collect_actions(self, observations: dict[str, Any], turn: int) -> dict[str, list[ActionRequest]]:
        """Collect actions from all living agents. Each agent can return multiple actions.
        
        Dead agents are skipped - they don't receive observations and don't take actions.
        
        Returns a dict mapping agent_id -> list of ActionRequests (can be empty list).
        """
        actions: dict[str, list[ActionRequest]] = {}
        for name, controller in self.residents.items():
            # Check if agent is alive
            agent_state = self.env.agent_states.get(name)
            if not agent_state or not agent_state.alive:
                # Skip dead agents
                continue
            
            # Update visualizer to show which agent is currently processing
            if self._serializer:
                self._serializer.set_current_agent(name)
            
            obs = observations.get(name)
            if not obs:
                # No observation means agent shouldn't act (safety check)
                actions[name] = []
                continue
            
            payloads = controller.decide_action(observation=obs, turn=turn)
            
            # Store agent's last internal state for visualizer
            agent_state = self.env.agent_states.get(name)
            if agent_state:
                # Get the last thought and tool call from the controller
                agent_state.last_thought = getattr(controller, "_last_thought", None)
                agent_state.last_tool_call = getattr(controller, "_last_tool_call", None)
            
            # Log tool invocations to console
            tool_calls = getattr(controller, "_last_tool_call", None)
            if tool_calls:
                for tool_call in tool_calls:
                    tool_name = tool_call.get("name", "unknown")
                    tool_args = tool_call.get("arguments", {})
                    self._log_console(f"  [{name}] Tool: {tool_name}({tool_args})")
            
            # Convert all valid payloads to ActionRequests
            agent_actions = []
            for payload in payloads:
                try:
                    action_type = ActionType(payload["action"])
                    agent_actions.append(
                        ActionRequest(action=action_type, parameters=payload.get("parameters", {}))
                    )
                    # Log the resulting action
                    params_str = str(payload.get("parameters", {}))
                    self._log_console(f"  [{name}] Action: {action_type.value} {params_str}")
                except (ValueError, KeyError):
                    continue
            
            actions[name] = agent_actions
        
        # Clear current agent after all processing
        if self._serializer:
            self._serializer.set_current_agent(None)
        
        return actions

    @staticmethod
    def _deep_update(target: Any, overrides: dict[str, Any]) -> None:
        for key, value in overrides.items():
            current = getattr(target, key)
            if isinstance(value, dict) and not isinstance(current, (str, int, float, bool)):
                ExperimentRunner._deep_update(current, value)
            else:
                setattr(target, key, value)

    def _start_visualizer(self) -> None:
        self._serializer = WorldStateSerializer(self.env, self._resident_metadata)
        self._visualizer_server = VisualizerServer(self._serializer)
        uvicorn_config = uvicorn.Config(
            self._visualizer_server.app,
            host=self._visualizer_host,
            port=self._visualizer_port,
            log_level="warning",
            loop="asyncio",
        )

        def _run_server() -> None:
            server = uvicorn.Server(uvicorn_config)
            server.run()

        self._visualizer_thread = threading.Thread(target=_run_server, daemon=True)
        self._visualizer_thread.start()
        self._log_console(
            f"Visualizer available at http://{self._visualizer_host}:{self._visualizer_port}"
        )

    def _save_experiment_config(self, max_turns: int | None) -> None:
        """Save experiment configuration to JSON file for reproducibility."""
        config_data = {
            "experiment": {
                "name": self.exp_config.name,
                "description": self.exp_config.description,
                "timestamp": datetime.now().isoformat(),
            },
            "residents": self._serialize_residents(),
            "constitution": [self._rule_to_dict(rule) for rule in self.exp_config.constitution_rules],
            "environment": {
                "grid_width": self.env.settings.grid_width,
                "grid_height": self.env.settings.grid_height,
                "max_turns": max_turns or self.env.settings.max_turns,
                "review_interval": self.env.settings.review_interval,
                "random_seed": self.env.settings.random_seed,
                "reveal_teams": self.env.settings.reveal_teams,
                "hunger": {
                    "enabled": self.env.hunger_settings.enabled,
                    "max_energy": self.env.hunger_settings.max_energy,
                    "consumption_per_turn": self.env.hunger_settings.consumption_per_turn,
                    "rest_recovery": self.env.hunger_settings.rest_recovery,
                    "food_recovery_per_unit": self.env.hunger_settings.food_recovery_per_unit,
                    "action_costs": self.env.hunger_settings.action_costs,
                    "starvation_threshold": self.env.hunger_settings.starvation_threshold,
                    "leave_corpses": self.env.hunger_settings.leave_corpses,
                },
                "attack": {
                    "enabled": self.env.attack_settings.enabled,
                    "success_chance": self.env.attack_settings.success_chance,
                },
                "steal": {
                    "enabled": self.env.steal_settings.enabled,
                    "success_chance": self.env.steal_settings.success_chance,
                },
            },
            "agent": {
                "default_model": config.agent.default_model,
                "temperature": config.agent.temperature,
                "max_conversation_history": config.agent.max_conversation_history,
                "enable_memory": config.agent.enable_memory,
            },
            "tooling": {
                "parallel_tool_calls": config.tooling.parallel_tool_calls,
                "prefer_auto_tool_choice": config.tooling.prefer_auto_tool_choice,
                "max_tool_calls_per_turn": config.tooling.max_tool_calls_per_turn,
            },
            "visualizer": {
                "enabled": self.enable_visualizer,
                "host": self._visualizer_host,
                "port": self._visualizer_port,
            },
            "overrides": self.exp_config.environment_overrides,
            "resident_constitutions_enabled": self.use_resident_constitutions,
        }
        
        config_json = json.dumps(config_data, indent=2, sort_keys=False)
        self.logger.write_text(
            "experiment_config.json",
            config_json,
            append=False,
            ensure_newline=True,
        )
        self._log_console("Experiment configuration saved to experiment_config.json")

    def _log_console(self, message: str) -> None:
        timestamped = f"[Experiment] {message}"
        print(timestamped)
        self.logger.log(message, filename="society.log")

    def _resident_metadata(self, agent_name: str) -> dict[str, Any]:
        controller = self.residents.get(agent_name)
        if not controller:
            return {}
        metadata: dict[str, Any] = {}
        constitution = getattr(controller, "constitution", None)
        if constitution and getattr(constitution, "rules", None):
            metadata["constitution"] = {
                "title": constitution.title,
                "rules": [self._rule_to_dict(rule) for rule in constitution.rules],
            }
        memories = getattr(controller, "memory_snapshot", None)
        if memories is not None:
            metadata["memories"] = list(memories)
        return metadata

    def _serialize_residents(self) -> list[dict[str, Any]]:
        residents: list[dict[str, Any]] = []
        for profile in self.exp_config.residents:
            entry: dict[str, Any] = {"name": profile.name, "team": profile.team}
            if self.use_resident_constitutions and profile.constitution_rules:
                entry["constitution"] = [self._rule_to_dict(rule) for rule in profile.constitution_rules]
            residents.append(entry)
        return residents

    @staticmethod
    def _rule_to_dict(rule: MoralRule) -> dict[str, Any]:
        return {
            "name": rule.name,
            "guidance": rule.guidance,
            "summary": rule.summary,
            "priority": rule.priority,
            "tags": list(rule.tags),
        }

