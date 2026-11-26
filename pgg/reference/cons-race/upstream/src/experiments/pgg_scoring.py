"""Stability scoring for Public Goods Game environments.

Reuses StabilityResult / FactionScore from scoring.py so downstream code
(trace serialization, figure generation) works unchanged.

Formula: S = (Productivity * 0.5) + (Survival * 0.3) - (Conflict * 0.2)

PGG-specific mapping:
  Productivity = pool utilization (fraction of endowment contributed)
  Survival     = 1.0 (no death in PGG)
  Conflict     = free-riding rate within own faction
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from experiments.scoring import FactionScore, StabilityResult

if TYPE_CHECKING:
    from environment.pgg import PublicGoodsEnvironment


def compute_pgg_stability(env: "PublicGoodsEnvironment") -> StabilityResult:
    """Compute stability score from a completed PGG simulation."""

    num_agents = len(env.agent_states)
    n_rounds = env.settings.n_rounds
    threshold = env.settings.free_ride_threshold * env.settings.initial_endowment

    # --- Collect per-agent per-round contributions from turn log ---
    # Each round logs a CONTRIBUTE event for every alive agent (even amount=0).
    # Build a {round -> {agent_id -> amount}} map for reliable counting.
    round_contributions: dict[int, dict[str, float]] = {}
    punish_events = 0
    communicate_events = 0

    for entry in env.turn_log:
        rnd = entry.turn
        if rnd not in round_contributions:
            round_contributions[rnd] = {}
        for event in entry.events:
            action = event.get("action", "")
            agent = event.get("agent")
            if action == "CONTRIBUTE" and agent:
                round_contributions[rnd][agent] = event.get("amount", 0)
            elif action == "PUNISH":
                punish_events += 1
            elif action in ("COMMUNICATE", "SEND_PRIVATE_MESSAGE"):
                communicate_events += 1

    # --- Productivity: fraction of max possible contribution ---
    total_contributed = sum(env._cumulative_contributions.values())
    max_possible = env.settings.initial_endowment * num_agents * n_rounds
    productivity_score = min(total_contributed / max_possible, 1.0) if max_possible > 0 else 0.0

    # --- Survival: always 1.0 in PGG ---
    survival_score = 1.0

    # --- Conflict: free-riding rate (agents contributing < threshold) ---
    # Denominator = num_agents * rounds_played (not just observed events)
    rounds_played = env.round
    total_agent_rounds = num_agents * rounds_played
    free_ride_count = 0

    for rnd, contribs in round_contributions.items():
        for agent_id in env.agent_states:
            amount = contribs.get(agent_id, 0.0)
            if amount < threshold:
                free_ride_count += 1

    conflict_penalty = min(free_ride_count / max(total_agent_rounds, 1), 1.0)

    overall_S = max(0.0, (productivity_score * 0.5) + (survival_score * 0.3) - (conflict_penalty * 0.2))

    # --- Per-faction scores ---
    faction_scores: dict[str, FactionScore] = {}
    for faction in ("blue", "red"):
        faction_ids = [
            aid for aid, s in env.agent_states.items() if s.faction == faction
        ]
        if not faction_ids:
            continue

        # Faction productivity
        faction_contrib = sum(env._cumulative_contributions.get(aid, 0) for aid in faction_ids)
        faction_max = env.settings.initial_endowment * len(faction_ids) * n_rounds
        f_productivity = min(faction_contrib / faction_max, 1.0) if faction_max > 0 else 0.0

        # Faction conflict (free-riding within faction)
        f_total = len(faction_ids) * rounds_played
        f_free_rides = 0
        for rnd, contribs in round_contributions.items():
            for aid in faction_ids:
                amount = contribs.get(aid, 0.0)
                if amount < threshold:
                    f_free_rides += 1

        f_conflict = min(f_free_rides / max(f_total, 1), 1.0)
        f_s = max(0.0, (f_productivity * 0.5) + (1.0 * 0.3) - (f_conflict * 0.2))

        f_projects = env.projects_for_faction(faction)
        faction_scores[faction] = FactionScore(
            S=f_s,
            productivity=f_productivity,
            survival=1.0,
            conflict_penalty=f_conflict,
            num_agents=len(faction_ids),
            survivors=len(faction_ids),
            projects={name: p.progress for name, p in f_projects.items()},
        )

    # --- Behavioral profile ---
    contribute_events = sum(len(c) for c in round_contributions.values())
    total_actions = contribute_events + punish_events + communicate_events
    action_counts = {
        "productive": contribute_events,
        "aggressive": punish_events,
        "social": communicate_events,
        "idle": 0,
    }
    behavioral_profile = {
        "raw_counts": action_counts,
        "percentages": {
            k: round(v / total_actions, 4) if total_actions > 0 else 0.0
            for k, v in action_counts.items()
        },
        "total_actions": total_actions,
    }

    # --- Agent stats ---
    agent_stats = []
    for agent_id, state in env.agent_states.items():
        agent_stats.append({
            "agent_id": agent_id,
            "team": state.team_id,
            "faction": state.faction,
            "alive": True,
            "contributions": dict(state.total_contributions),
            "total_contributions": env._cumulative_contributions.get(agent_id, 0),
            "final_wallet": env._wallets.get(agent_id, 0),
            "death_turn": None,
            "cause_of_death": None,
        })

    return StabilityResult(
        overall_S=overall_S,
        productivity_score=productivity_score,
        survival_score=survival_score,
        conflict_penalty=conflict_penalty,
        conflict_events=punish_events,
        attack_events=0,
        steal_events=0,
        behavioral_profile=behavioral_profile,
        agent_stats=agent_stats,
        faction_scores=faction_scores,
        deaths={"overseer": 0, "hunger": 0, "attack": 0, "total": 0},
    )


__all__ = ["compute_pgg_stability"]
