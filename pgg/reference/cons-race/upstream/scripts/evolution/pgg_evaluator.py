"""
PGG Evaluator for Constitutional Co-Evolution.

Runs a Public Goods Game simulation (3v3 blue vs red) and returns the
evolving faction's stability score as the fitness metric for OpenEvolve.

Environment variables consumed by this evaluator:
    EVOLVING_FACTION    – "blue" or "red" (default: "blue")
    OPPONENT_CONSTITUTION_PATH – path to the opponent's current best constitution .py
    INFO_CONDITION      – "full", "own_team", or "asymmetric" (default: "full")
    PGG_ROUNDS          – rounds per game (default: 20)
    PGG_MULTIPLIER      – pool multiplier (default: 1.5)
    EVAL_SEEDS          – number of seeds to average (default: 2)
"""

from __future__ import annotations

import asyncio
import os
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# Add src/ to path first (BEFORE scripts/ to avoid scripts/experiments/ shadowing src/experiments/).
# When loaded via OpenEvolve's exec_module, the evaluator's directory is already on sys.path.
_this_dir = Path(__file__).resolve().parent          # scripts/evolution/
_scripts_dir = _this_dir.parent                       # scripts/
_project_root = _scripts_dir.parent                   # project root
_src_dir = str(_project_root / "src")
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from openevolve.evaluation_result import EvaluationResult

from core.constitution import Constitution, MoralRule
from core.langchain_resident import LangChainResident
from core.tools.pgg_registry import build_pgg_agent_tools
from core.pgg_action_mapping import convert_pgg_tool_invocation
from environment.pgg import PGGActionRequest, PGGActionType, PGGSettings, PublicGoodsEnvironment
from environment.game import AgentSpawn
from experiments.pgg_scoring import compute_pgg_stability

# Import constitution loader directly to avoid needing scripts/ on sys.path
# (scripts/experiments/ would shadow src/experiments/ if scripts/ were added)
_adv_eval_path = _this_dir / "adversarial_evaluator.py"
import importlib.util as _ilu
_spec = _ilu.spec_from_file_location("_adversarial_evaluator", str(_adv_eval_path))
_adv_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_adv_mod)
load_constitution_from_program = _adv_mod.load_constitution_from_program


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_single_pgg_simulation(
    blue_rules: list[MoralRule],
    red_rules: list[MoralRule],
    rounds: int,
    seed: int,
    multiplier: float,
) -> dict:
    """Run one PGG simulation and return raw metrics."""
    settings = PGGSettings(
        n_rounds=rounds,
        multiplier=multiplier,
        initial_endowment=100.0,
        random_seed=seed,
    )
    env = PublicGoodsEnvironment(settings)

    spawns = [
        AgentSpawn("Blue1", "cooperators", faction="blue"),
        AgentSpawn("Blue2", "cooperators", faction="blue"),
        AgentSpawn("Blue3", "cooperators", faction="blue"),
        AgentSpawn("Red1", "free_riders", faction="red"),
        AgentSpawn("Red2", "free_riders", faction="red"),
        AgentSpawn("Red3", "free_riders", faction="red"),
    ]

    blue_constitution = Constitution(rules=list(blue_rules))
    red_constitution = Constitution(rules=list(red_rules))

    # Build LLM agents with PGG tools and PGG action converter
    agents: dict[str, LangChainResident] = {}
    for spawn in spawns:
        constitution = blue_constitution if spawn.faction == "blue" else red_constitution
        tools = build_pgg_agent_tools(spawn.agent_id)
        agents[spawn.agent_id] = LangChainResident(
            spawn.agent_id,
            constitution=constitution,
            tools=tools,
            hunger_enabled=False,
            faction=spawn.faction,
            adversarial_mode=True,
            action_converter=convert_pgg_tool_invocation,
            environment_type="pgg",
        )

    observations = env.reset(spawns)

    def _decide_pgg(agent_id: str, agent: LangChainResident, obs: dict) -> tuple[str, list[PGGActionRequest]]:
        """Single agent decision — run in thread pool."""
        try:
            payloads = agent.decide_action(observation=obs, turn=_current_round[0])
            round_actions: list[PGGActionRequest] = []
            for payload in payloads:
                action_str = payload.get("action", "")
                params = payload.get("parameters", {})
                try:
                    pgg_action = PGGActionType(action_str)
                    round_actions.append(PGGActionRequest(pgg_action, params))
                except ValueError:
                    pass
            if not round_actions:
                round_actions = [PGGActionRequest(PGGActionType.REST, {})]
            return agent_id, round_actions
        except Exception:
            return agent_id, [PGGActionRequest(PGGActionType.REST, {})]

    _current_round = [0]  # mutable container for closure

    for round_num in range(1, rounds + 1):
        _current_round[0] = round_num
        actions: dict[str, PGGActionRequest | list[PGGActionRequest]] = {}

        live = [(aid, ag, observations[aid]) for aid, ag in agents.items() if aid in observations]
        with ThreadPoolExecutor(max_workers=min(len(live), 6)) as pool:
            futures = [pool.submit(_decide_pgg, aid, ag, obs) for aid, ag, obs in live]
            for f in futures:
                aid, acts = f.result()
                actions[aid] = acts

        observations = env.step(actions)

    sr = compute_pgg_stability(env)
    return {"stability_result": sr, "env": env}


def _build_pgg_action_log(env: PublicGoodsEnvironment, faction_filter: str | None = None) -> str:
    """Build a compact action log string for OpenEvolve artifacts."""
    lines: list[str] = []
    faction_agents: set[str] | None = None
    if faction_filter:
        faction_agents = {
            aid for aid, st in env.agent_states.items() if st.faction == faction_filter
        }

    for entry in env.turn_log:
        rnd = entry.turn
        for event in entry.events:
            agent = event.get("agent", "?")
            if faction_agents and agent not in faction_agents:
                continue
            action = event.get("action", "?")
            if action == "POOL_DISTRIBUTION":
                pool = event.get("total_contributed", 0)
                share = event.get("per_agent_share", 0)
                lines.append(f"R{rnd}:POOL={pool:.0f}->share={share:.1f}")
                continue
            amount = event.get("amount", "")
            target = event.get("target", "")
            extra = ""
            if amount != "":
                extra = f"({amount:.0f})"
            if target:
                extra += f">{target}"
            lines.append(f"R{rnd}:{agent}-{action[:3]}{extra}")

    return "\n".join(lines[-200:])


# ---------------------------------------------------------------------------
# Main evaluation entry points
# ---------------------------------------------------------------------------

def evaluate(program_path: str) -> EvaluationResult:
    """Evaluate a PGG constitution by running simulations."""
    try:
        faction = os.environ.get("EVOLVING_FACTION", "blue")
        opponent_path = os.environ.get("OPPONENT_CONSTITUTION_PATH", "")
        info_condition = os.environ.get("INFO_CONDITION", "full")
        rounds = int(os.environ.get("PGG_ROUNDS", "20"))
        multiplier = float(os.environ.get("PGG_MULTIPLIER", "1.5"))
        num_seeds = int(os.environ.get("EVAL_SEEDS", "2"))

        # Load the evolved constitution
        evolved_rules = load_constitution_from_program(program_path)
        if not evolved_rules:
            return EvaluationResult(
                metrics={"combined_score": 0.0, "error": "empty constitution"},
                artifacts={"suggestion": "Ensure get_rules_as_dicts() returns rules"},
            )

        # Load opponent constitution
        if opponent_path and Path(opponent_path).exists():
            opponent_rules = load_constitution_from_program(opponent_path)
        else:
            default_dir = Path(__file__).parent
            if faction == "blue":
                opponent_rules = load_constitution_from_program(
                    str(default_dir / "initial_red_pgg_constitution.py")
                )
            else:
                opponent_rules = load_constitution_from_program(
                    str(default_dir / "initial_blue_pgg_constitution.py")
                )

        # Assign rules based on evolving faction
        if faction == "blue":
            blue_rules, red_rules = evolved_rules, opponent_rules
        else:
            blue_rules, red_rules = opponent_rules, evolved_rules

        # Run simulations across seeds — parallel when possible
        seeds = [42 + i * 17 for i in range(num_seeds)]

        if num_seeds > 1:
            with ThreadPoolExecutor(max_workers=min(num_seeds, 4)) as pool:
                futures = [
                    pool.submit(_run_single_pgg_simulation, blue_rules, red_rules, rounds, seed, multiplier)
                    for seed in seeds
                ]
                results = [f.result() for f in futures]
        else:
            results = [_run_single_pgg_simulation(blue_rules, red_rules, rounds, seeds[0], multiplier)]

        # Collect scores
        faction_scores: list[float] = []
        opponent_scores: list[float] = []
        all_action_logs: list[str] = []

        for result in results:
            sr = result["stability_result"]
            env = result["env"]

            if sr.faction_scores:
                faction_scores.append(sr.faction_scores[faction].S)
                opponent_faction = "red" if faction == "blue" else "blue"
                opponent_scores.append(sr.faction_scores[opponent_faction].S)

            if info_condition == "full":
                all_action_logs.append(_build_pgg_action_log(env))
            elif info_condition == "own_team":
                all_action_logs.append(_build_pgg_action_log(env, faction_filter=faction))
            elif info_condition == "asymmetric":
                if faction == "red":
                    all_action_logs.append(_build_pgg_action_log(env))
                else:
                    all_action_logs.append(_build_pgg_action_log(env, faction_filter="blue"))

        # Average scores
        avg_score = sum(faction_scores) / len(faction_scores) if faction_scores else 0.0
        avg_opponent = sum(opponent_scores) / len(opponent_scores) if opponent_scores else 0.0
        score_advantage = avg_score - avg_opponent

        artifacts = {
            "simulation_summary": (
                f"Environment: Public Goods Game\n"
                f"Faction: {faction}\n"
                f"Avg {faction} S: {avg_score:.4f}\n"
                f"Avg opponent S: {avg_opponent:.4f}\n"
                f"Score advantage: {score_advantage:+.4f}\n"
                f"Seeds: {num_seeds}, Rounds: {rounds}, Multiplier: {multiplier}\n"
                f"Info condition: {info_condition}"
            ),
            "action_log": "\n---\n".join(all_action_logs),
            "constitution_rules_count": len(evolved_rules),
        }

        if avg_score < 0.1:
            artifacts["suggestion"] = (
                "Very low faction score. Ensure rules guide agents to contribute "
                "to the public pool."
            )

        # FITNESS_MODE controls what OpenEvolve optimises:
        #   "absolute"        (default) = raw S_faction
        #   "advantage"       = S_faction - S_opponent (zero-sum search)
        #   "pure_adversary"  = 1 - S_opponent (Red's only goal: minimise Blue)
        fitness_mode = os.environ.get("FITNESS_MODE", "absolute")
        if fitness_mode == "advantage":
            fitness = score_advantage
        elif fitness_mode == "pure_adversary" and faction == "red":
            fitness = 1.0 - avg_opponent
        else:
            fitness = avg_score

        return EvaluationResult(
            metrics={
                "combined_score": fitness,
                f"{faction}_score": avg_score,
                "opponent_score": avg_opponent,
                "score_advantage": score_advantage,
                "fitness_mode": fitness_mode,
                "num_rules": len(evolved_rules),
            },
            artifacts=artifacts,
        )

    except Exception as e:
        traceback.print_exc()
        return EvaluationResult(
            metrics={"combined_score": 0.0, "error": str(e)},
            artifacts={
                "error_type": type(e).__name__,
                "error_message": str(e),
                "full_traceback": traceback.format_exc(),
            },
        )


def evaluate_stage1(program_path: str) -> EvaluationResult:
    """Quick viability check."""
    try:
        rules = load_constitution_from_program(program_path)
        if not rules:
            return EvaluationResult(
                metrics={"loads_successfully": 0.0, "combined_score": 0.0},
                artifacts={"error": "No rules found"},
            )
        for rule in rules:
            if not rule.name or not rule.guidance:
                return EvaluationResult(
                    metrics={"loads_successfully": 0.5, "combined_score": 0.1},
                    artifacts={"error": f"Invalid rule: {rule.name}"},
                )
        return EvaluationResult(
            metrics={"loads_successfully": 1.0, "combined_score": 0.3},
            artifacts={"stage": "1"},
        )
    except Exception as e:
        return EvaluationResult(
            metrics={"loads_successfully": 0.0, "combined_score": 0.0},
            artifacts={"error": str(e)},
        )


def evaluate_stage2(program_path: str) -> EvaluationResult:
    """Full evaluation — delegates to evaluate()."""
    return evaluate(program_path)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        result = evaluate(sys.argv[1])
    else:
        initial = Path(__file__).parent / "initial_blue_pgg_constitution.py"
        if initial.exists():
            result = evaluate(str(initial))
        else:
            print("Usage: python pgg_evaluator.py <path>")
            sys.exit(1)

    print("\nPGG Evaluation Results:")
    print("=" * 40)
    for metric, value in result.metrics.items():
        if isinstance(value, float):
            print(f"  {metric}: {value:.4f}")
        else:
            print(f"  {metric}: {value}")
