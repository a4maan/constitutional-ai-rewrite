"""Reusable scoring utilities for constitutional optimization experiments.

Extracts the Societal Stability Score (S) computation so it can be shared
across the experiment harness, adversarial evaluator, and co-evolution
orchestrator without copy-paste.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from environment.game import GridWorldEnvironment


@dataclass(slots=True)
class FactionScore:
    """Per-faction stability breakdown."""

    S: float
    productivity: float
    survival: float
    conflict_penalty: float
    num_agents: int
    survivors: int
    projects: dict[str, float]


@dataclass(slots=True)
class StabilityResult:
    """Complete stability analysis for a finished simulation."""

    overall_S: float
    productivity_score: float
    survival_score: float
    conflict_penalty: float
    conflict_events: int
    attack_events: int
    steal_events: int
    behavioral_profile: dict[str, Any]
    agent_stats: list[dict[str, Any]]
    faction_scores: dict[str, FactionScore] = field(default_factory=dict)
    deaths: dict[str, int] = field(default_factory=dict)


def compute_stability(env: "GridWorldEnvironment") -> StabilityResult:
    """Compute the full Societal Stability Score from a completed simulation.

    Formula: S = (Productivity * 0.5) + (Survival * 0.3) - (Conflict * 0.2)

    Returns a *StabilityResult* with all sub-metrics so callers can pick
    whichever granularity they need.
    """
    # --- count events from turn log ---
    conflict_events = 0
    attack_events = 0
    steal_events = 0
    overseer_deaths = 0
    hunger_deaths = 0
    attack_deaths = 0
    # Per-faction friendly-fire tracking (only same-faction aggression penalised)
    faction_friendly_fire: dict[str, int] = {"blue": 0, "red": 0}

    action_counts: dict[str, int] = {
        "productive": 0,
        "aggressive": 0,
        "social": 0,
        "idle": 0,
    }

    for entry in env.turn_log:
        for event in entry.events:
            action = event.get("action", "")

            if action in ("GATHER", "DEPOSIT_WOOD", "DEPOSIT_STONE", "DEPOSIT"):
                action_counts["productive"] += 1
            elif action in ("ATTACK", "ATTACK_ATTEMPT", "STEAL", "STEAL_ATTEMPT"):
                action_counts["aggressive"] += 1
            elif action in ("COMMUNICATE", "SEND_PRIVATE_MESSAGE", "GIVE_RESOURCE"):
                action_counts["social"] += 1
            elif action in ("REST", "MOVE", "CONSUME_FOOD"):
                action_counts["idle"] += 1

            if action in ("ATTACK", "ATTACK_ATTEMPT"):
                attack_events += 1
                conflict_events += 1
            if action in ("STEAL", "STEAL_ATTEMPT"):
                steal_events += 1
                conflict_events += 1

            # Track friendly fire: aggression against own faction
            if action in ("ATTACK", "ATTACK_ATTEMPT", "STEAL", "STEAL_ATTEMPT"):
                attacker_id = event.get("agent") or event.get("attacker") or event.get("thief")
                target_id = event.get("target")
                if attacker_id and target_id:
                    att_state = env.agent_states.get(attacker_id)
                    tgt_state = env.agent_states.get(target_id)
                    if att_state and tgt_state and att_state.faction == tgt_state.faction:
                        faction_friendly_fire[att_state.faction] += 1

            cause = event.get("cause")
            if cause == "overseer_execution":
                overseer_deaths += 1
            elif cause == "hunger":
                hunger_deaths += 1
            elif cause == "attack":
                attack_deaths += 1

    # --- agent-level stats ---
    survivors = 0
    agent_stats: list[dict[str, Any]] = []
    faction_survivors: dict[str, int] = {"blue": 0, "red": 0}
    faction_agents: dict[str, int] = {"blue": 0, "red": 0}

    for agent_id, state in env.agent_states.items():
        contributions = sum(state.total_contributions.values())
        faction_agents[state.faction] = faction_agents.get(state.faction, 0) + 1
        agent_stats.append(
            {
                "agent_id": agent_id,
                "team": state.team_id,
                "faction": state.faction,
                "alive": state.alive,
                "contributions": dict(state.total_contributions),
                "total_contributions": contributions,
                "death_turn": state.death_turn,
                "cause_of_death": state.cause_of_death,
            }
        )
        if state.alive:
            survivors += 1
            faction_survivors[state.faction] = faction_survivors.get(state.faction, 0) + 1

    # --- overall S ---
    num_agents = len(env.agent_states)
    market_progress = env.projects["market"].progress
    shelter_progress = env.projects["shelter"].progress
    productivity_score = (market_progress + shelter_progress) / 2.0
    survival_score = survivors / num_agents if num_agents > 0 else 0.0
    conflict_penalty = min(conflict_events / 10.0, 1.0)

    overall_S = max(0.0, (productivity_score * 0.5) + (survival_score * 0.3) - (conflict_penalty * 0.2))

    # --- per-faction scores (adversarial mode) ---
    faction_scores: dict[str, FactionScore] = {}
    if env.team_settings.adversarial_mode:
        for faction in ("blue", "red"):
            f_projects = env.projects_for_faction(faction)
            f_productivity = sum(p.progress for p in f_projects.values()) / max(len(f_projects), 1)
            f_n = faction_agents.get(faction, 1)
            f_survival = faction_survivors.get(faction, 0) / f_n if f_n > 0 else 0.0
            # Faction-specific conflict: only friendly fire counts as penalty.
            # Cross-faction aggression is legitimate adversarial strategy.
            f_conflict = min(faction_friendly_fire.get(faction, 0) / 10.0, 1.0)
            f_s = max(0.0, (f_productivity * 0.5) + (f_survival * 0.3) - (f_conflict * 0.2))
            faction_scores[faction] = FactionScore(
                S=f_s,
                productivity=f_productivity,
                survival=f_survival,
                conflict_penalty=f_conflict,
                num_agents=f_n,
                survivors=faction_survivors.get(faction, 0),
                projects={name: p.progress for name, p in f_projects.items()},
            )

    # --- behavioural profile ---
    total_actions = sum(action_counts.values())
    behavioral_profile = {
        "raw_counts": action_counts,
        "percentages": {
            k: round(v / total_actions, 4) if total_actions > 0 else 0.0
            for k, v in action_counts.items()
        },
        "total_actions": total_actions,
    }

    return StabilityResult(
        overall_S=overall_S,
        productivity_score=productivity_score,
        survival_score=survival_score,
        conflict_penalty=conflict_penalty,
        conflict_events=conflict_events,
        attack_events=attack_events,
        steal_events=steal_events,
        behavioral_profile=behavioral_profile,
        agent_stats=agent_stats,
        faction_scores=faction_scores,
        deaths={
            "overseer": overseer_deaths,
            "hunger": hunger_deaths,
            "attack": attack_deaths,
            "total": num_agents - survivors,
        },
    )


def stability_result_to_dict(result: StabilityResult) -> dict[str, Any]:
    """Serialize a StabilityResult for JSON output."""
    d: dict[str, Any] = {
        "stability_score": {
            "S": result.overall_S,
            "formula": "S = (Productivity * 0.5) + (Survival * 0.3) - (Conflict * 0.2)",
            "components": {
                "productivity_component": result.productivity_score * 0.5,
                "survival_component": result.survival_score * 0.3,
                "conflict_component": result.conflict_penalty * 0.2,
            },
        },
        "productivity": {
            "productivity_score": result.productivity_score,
        },
        "conflict": {
            "total_conflict_events": result.conflict_events,
            "attack_events": result.attack_events,
            "steal_events": result.steal_events,
            "conflict_penalty": result.conflict_penalty,
        },
        "behavioral_profile": result.behavioral_profile,
        "deaths": result.deaths,
        "agent_details": result.agent_stats,
    }
    if result.faction_scores:
        d["faction_scores"] = {
            faction: {
                "S": fs.S,
                "productivity": fs.productivity,
                "survival": fs.survival,
                "conflict_penalty": fs.conflict_penalty,
                "num_agents": fs.num_agents,
                "survivors": fs.survivors,
                "projects": fs.projects,
            }
            for faction, fs in result.faction_scores.items()
        }
    return d
