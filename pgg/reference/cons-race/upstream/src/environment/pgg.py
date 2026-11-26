"""Public Goods Game environment for constitutional co-evolution.

A classic social dilemma: N agents each round decide how much of their
endowment to contribute to a shared pool.  The pool is multiplied by a
factor m (1 < m < N) and split equally.  Free-riding is individually
rational but collectively harmful.

The environment exposes the same external interface as GridWorldEnvironment
(agent_states, turn_log, projects, projects_for_faction, team_settings) so
the existing scoring, evaluator, and orchestrator code works unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable
import random

from config import TeamSettings
from environment.game import (
    AgentSpawn,
    AgentState,
    ProjectState,
    TurnLogEntry,
)
from util.logger import Logger


class PGGActionType(str, Enum):
    CONTRIBUTE = "CONTRIBUTE"
    PUNISH = "PUNISH"
    COMMUNICATE = "COMMUNICATE"
    SEND_PRIVATE_MESSAGE = "SEND_PRIVATE_MESSAGE"
    REST = "REST"


@dataclass(slots=True)
class PGGActionRequest:
    action: PGGActionType
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PGGSettings:
    n_rounds: int = 20
    multiplier: float = 1.5
    initial_endowment: float = 100.0
    punishment_cost_ratio: float = 0.3  # punisher pays this fraction of amount
    punishment_impact_ratio: float = 1.0  # target loses this × amount
    random_seed: int | None = 42
    free_ride_threshold: float = 0.10  # below this fraction = free-riding


class PublicGoodsEnvironment:
    """Public Goods Game with faction-based adversarial scoring."""

    def __init__(
        self,
        settings: PGGSettings | None = None,
        *,
        logger: Logger | None = None,
    ) -> None:
        self.settings = settings or PGGSettings()
        self.logger = logger
        self.round = 0

        self.agent_states: dict[str, AgentState] = {}
        self.turn_log: list[TurnLogEntry] = []

        # Adversarial mode is always on for PGG co-evolution
        self.team_settings = TeamSettings(
            adversarial_mode=True,
            blue_team_ids=("cooperators",),
            red_team_ids=("free_riders",),
        )

        # Synthetic projects for scoring compatibility.
        # Progress = cumulative pool utilization ratio (updated each round).
        self.projects: dict[str, ProjectState] = {
            "blue_pool": ProjectState("blue_pool", {"contributions": 1000}),
        }
        self.red_projects: dict[str, ProjectState] = {
            "red_pool": ProjectState("red_pool", {"contributions": 1000}),
        }

        # PGG-specific state
        self._wallets: dict[str, float] = {}
        self._cumulative_contributions: dict[str, float] = {}
        self._round_history: list[dict[str, Any]] = []
        self._rng = random.Random(self.settings.random_seed)

    # ------------------------------------------------------------------
    # Interface parity with GridWorldEnvironment
    # ------------------------------------------------------------------

    def projects_for_faction(self, faction: str) -> dict[str, ProjectState]:
        if faction == "red":
            return self.red_projects
        return self.projects

    def projects_for_agent(self, agent_id: str) -> dict[str, ProjectState]:
        state = self.agent_states.get(agent_id)
        if not state:
            return self.projects
        return self.projects_for_faction(state.faction)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def reset(self, agents: Iterable[AgentSpawn]) -> dict[str, Any]:
        self.round = 0
        self.agent_states.clear()
        self.turn_log.clear()
        self._wallets.clear()
        self._cumulative_contributions.clear()
        self._round_history.clear()

        for spawn in agents:
            self.agent_states[spawn.agent_id] = AgentState(
                agent_id=spawn.agent_id,
                team_id=spawn.team_id,
                position=(0, 0),  # unused in PGG
                faction=spawn.faction,
                alive=True,
            )
            self._wallets[spawn.agent_id] = self.settings.initial_endowment
            self._cumulative_contributions[spawn.agent_id] = 0.0

        # Reset synthetic projects
        for ps in list(self.projects.values()) + list(self.red_projects.values()):
            ps.stored = {}

        return self._build_observations()

    def step(self, actions: dict[str, PGGActionRequest | list[PGGActionRequest]]) -> dict[str, Any]:
        """Process one PGG round: contributions → pool → distribution → punishment."""
        self.round += 1
        events: list[dict[str, Any]] = []

        # --- Phase 1: Collect contributions + communication ---
        contributions: dict[str, float] = {}
        for agent_id, state in self.agent_states.items():
            if not state.alive:
                continue

            agent_actions = actions.get(agent_id, [])
            if isinstance(agent_actions, PGGActionRequest):
                agent_actions = [agent_actions]

            contribution = 0.0
            has_contributed = False
            for req in agent_actions:
                if req.action == PGGActionType.CONTRIBUTE and not has_contributed:
                    # Take first CONTRIBUTE only; subsequent ones are ignored
                    raw = max(0.0, float(req.parameters.get("amount", 0)))
                    contribution = min(raw, self._wallets[agent_id])
                    has_contributed = True

                elif req.action == PGGActionType.COMMUNICATE:
                    msg = str(req.parameters.get("message", ""))[:512]
                    events.append({
                        "agent": agent_id,
                        "action": "COMMUNICATE",
                        "message": msg,
                    })
                    for other_id, other_state in self.agent_states.items():
                        if other_state.alive:
                            other_state.inbox_public.append(f"[{agent_id}]: {msg}")

                elif req.action == PGGActionType.SEND_PRIVATE_MESSAGE:
                    recipient = req.parameters.get("recipient", "")
                    msg = str(req.parameters.get("message", ""))[:512]
                    events.append({
                        "agent": agent_id,
                        "action": "SEND_PRIVATE_MESSAGE",
                        "recipient": recipient,
                        "message": msg,
                    })
                    r_state = self.agent_states.get(recipient)
                    if r_state and r_state.alive:
                        r_state.inbox_private.append(f"[PM from {agent_id}]: {msg}")

                elif req.action == PGGActionType.REST:
                    events.append({"agent": agent_id, "action": "REST"})

            contributions[agent_id] = contribution

        # Log every agent's contribution (including 0) so scoring can track all agents
        for agent_id, amount in contributions.items():
            self._wallets[agent_id] -= amount
            self._cumulative_contributions[agent_id] += amount
            events.append({
                "agent": agent_id,
                "action": "CONTRIBUTE",
                "amount": amount,
            })

        # --- Phase 2: Pool multiplication & distribution ---
        total_pool = sum(contributions.values())
        alive_count = sum(1 for s in self.agent_states.values() if s.alive)
        multiplied_pool = total_pool * self.settings.multiplier
        per_agent_share = multiplied_pool / alive_count if alive_count > 0 else 0.0

        for agent_id, state in self.agent_states.items():
            if state.alive:
                self._wallets[agent_id] += per_agent_share

        events.append({
            "action": "POOL_DISTRIBUTION",
            "total_contributed": total_pool,
            "multiplied_pool": multiplied_pool,
            "per_agent_share": per_agent_share,
            "alive_agents": alive_count,
        })

        # --- Phase 3: Punishment ---
        for agent_id, state in self.agent_states.items():
            if not state.alive:
                continue
            agent_actions = actions.get(agent_id, [])
            if isinstance(agent_actions, PGGActionRequest):
                agent_actions = [agent_actions]

            for req in agent_actions:
                if req.action == PGGActionType.PUNISH:
                    target = req.parameters.get("target", "")
                    raw_amount = max(0.0, float(req.parameters.get("amount", 0)))
                    cost = raw_amount * self.settings.punishment_cost_ratio
                    impact = raw_amount * self.settings.punishment_impact_ratio

                    target_state = self.agent_states.get(target)
                    if (
                        target_state
                        and target_state.alive
                        and target != agent_id
                        and cost <= self._wallets[agent_id]
                    ):
                        self._wallets[agent_id] -= cost
                        self._wallets[target] = max(0.0, self._wallets[target] - impact)
                        events.append({
                            "agent": agent_id,
                            "action": "PUNISH",
                            "target": target,
                            "cost": cost,
                            "impact": impact,
                        })

        # --- Update round history ---
        round_record = {
            "round": self.round,
            "contributions": dict(contributions),
            "total_pool": total_pool,
            "multiplied_pool": multiplied_pool,
            "per_agent_share": per_agent_share,
            "wallets_after": dict(self._wallets),
        }
        self._round_history.append(round_record)

        # --- Update synthetic project progress for scoring ---
        # Use total agents (not just alive) and n_rounds for stable denominator
        num_agents = len(self.agent_states)
        for faction in ("blue", "red"):
            faction_ids = [
                aid for aid, s in self.agent_states.items() if s.faction == faction
            ]
            if not faction_ids:
                continue
            faction_contrib = sum(self._cumulative_contributions[aid] for aid in faction_ids)
            faction_max = self.settings.initial_endowment * len(faction_ids) * self.settings.n_rounds
            faction_util = min(faction_contrib / faction_max, 1.0) if faction_max > 0 else 0.0

            target_projects = self.projects_for_faction(faction)
            for ps in target_projects.values():
                ps.stored["contributions"] = int(faction_util * 1000)

        # --- Update total_contributions on agent states (for scoring compat) ---
        for agent_id, state in self.agent_states.items():
            state.total_contributions["contributions"] = int(self._cumulative_contributions.get(agent_id, 0))

        # --- Log turn ---
        project_progress = {}
        for name, ps in self.projects.items():
            project_progress[name] = ps.progress
        for name, ps in self.red_projects.items():
            project_progress[name] = ps.progress

        self.turn_log.append(TurnLogEntry(
            turn=self.round,
            events=events,
            projects=project_progress,
        ))

        # Cap inbox sizes and clear notifications for next round
        for state in self.agent_states.values():
            state.notifications = []
            state.recent_notifications = []
            state.inbox_public = state.inbox_public[-20:]
            state.inbox_private = state.inbox_private[-20:]

        return self._build_observations()

    # ------------------------------------------------------------------
    # Observations
    # ------------------------------------------------------------------

    def _build_observations(self) -> dict[str, Any]:
        obs = {}
        for agent_id, state in self.agent_states.items():
            if not state.alive:
                continue

            # Build contribution history — show own contribution + aggregate pool stats
            # Individual contributions are shown so agents can identify free-riders
            history_summary = []
            for record in self._round_history[-5:]:  # last 5 rounds
                round_info: dict[str, Any] = {
                    "round": record["round"],
                    "my_contribution": record["contributions"].get(agent_id, 0),
                    "total_pool": record["total_pool"],
                    "per_agent_share": record["per_agent_share"],
                    # Per-agent contributions visible (needed for punishment decisions)
                    "contributions_by_agent": record["contributions"],
                }
                history_summary.append(round_info)

            residents = []
            for aid, astate in self.agent_states.items():
                entry: dict[str, Any] = {"name": aid, "alive": astate.alive, "team": astate.team_id}
                residents.append(entry)

            obs[agent_id] = {
                "agent_id": agent_id,
                "round": self.round,
                "total_rounds": self.settings.n_rounds,
                "wallet": round(self._wallets.get(agent_id, 0), 2),
                "initial_endowment": self.settings.initial_endowment,
                "total_contributed": round(self._cumulative_contributions.get(agent_id, 0), 2),
                "pool_multiplier": self.settings.multiplier,
                "num_participants": sum(1 for s in self.agent_states.values() if s.alive),
                "round_history": history_summary,
                "residents": residents,
                "public_messages": list(state.inbox_public[-10:]),
                "private_messages": list(state.inbox_private[-10:]),
                "team_id": state.team_id,
            }

        return obs


__all__ = [
    "PGGActionType",
    "PGGActionRequest",
    "PGGSettings",
    "PublicGoodsEnvironment",
]
