"""Play one game: a Blue constitution, a Red constitution, and a seed -> one game record."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json

from exp1.agents import hunt_and_kill_policy, llm_policy, mock_policy, parse_answer
from exp1.game import AdversarialGridWorld
from exp1.score import behavior_counts, blue_fitness, faction_score, red_fitness

SCHEMA_VERSION = 2  # 2: retries with correction, "rejected" attempts, no rest substitution, Blue fitness


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def summarize(result: dict) -> dict:
    return {k: v for k, v in (result or {}).items() if k != "agent"}


def play_game(blue, red, seed, config, model, *, red_controller="llm", mock=False,
              optimizer=None, purpose="game", checkpoint=None) -> dict:
    game = config["game"]
    env = AdversarialGridWorld(game, seed)
    names = sorted(env.agent_states)
    policies = {}
    for index, name in enumerate(names):
        faction = env.faction_of[name]
        if faction == "Red" and red_controller == "hunt_and_kill":
            policies[name] = hunt_and_kill_policy(env, name)
        elif mock:
            policies[name] = mock_policy(seed * 100 + index, names, name)
        else:
            rules = (blue if faction == "Blue" else red)["rules"]
            policies[name] = llm_policy(model, rules, seed * 100 + index, game, f"{purpose}:{faction}", names)
    record = {
        "schema_version": SCHEMA_VERSION, "optimizer": optimizer, "mock": mock, "complete": False,
        "seed": seed, "blue_id": digest(blue), "red_id": digest(red), "blue": blue, "red": red,
        "red_controller": red_controller, "game": game, "score_settings": config["score"],
        "fitness_name": config["fitness"],
        "agents": [{"name": n, "faction": env.faction_of[n], "spawn": env.spawns[n]} for n in names],
        "initial_state": env.snapshot(), "turns": [],
    }
    history = {n: [] for n in names}
    for _ in range(game["turns"]):
        living = [n for n in names if env.agent_states[n].alive]
        observations = {n: env.observe(n) for n in living}
        for n in living:
            env.agent_states[n].notifications.clear()
        decisions, parsed = {}, {}
        # All agents decide from the start-of-turn observations, so their model calls run in parallel.
        with ThreadPoolExecutor(max_workers=len(living)) as pool:
            futures = {n: pool.submit(policies[n], observations[n], history[n]) for n in living}
            answers = {n: futures[n].result() for n in living}
        for n in living:
            answer, rejected = answers[n], []
            if isinstance(answer, dict) and "_answer" in answer:
                answer, rejected = answer["_answer"], answer["_rejected"]
            # Ben (2026-11-27): invalid answers are retried with a correction (agents.llm_policy). No action is
            # ever substituted; a final invalid answer fails the game. "rejected" keeps every rejected attempt.
            parsed[n] = parse_answer(answer, names)
            decisions[n] = {"answer": answer, "rejected": rejected}
        order, results = env.play_turn(parsed)
        for entry in results:
            history[entry["agent"]].append({
                "turn": env.turn,
                "did": [{"request": i["request"], "result": summarize(i.get("result")) or i.get("skipped")}
                        for i in entry["results"]]})
        record["turns"].append({"turn": env.turn, "order": order, "decisions": decisions,
                                "results": results, "state": env.snapshot()})
        if checkpoint:
            checkpoint(record)
        if not any(env.agent_states[n].alive for n in names):
            break
    record["final"] = {
        "alive": {n: env.agent_states[n].alive for n in names},
        "inventories": {n: dict(env.agent_states[n].inventory) for n in names},
        "projects": {p: {"faction": env.project_owner[p], "required": dict(ps.required),
                         "stored": dict(ps.stored)} for p, ps in env.projects.items()},
    }
    scores = {f: faction_score(record, f, config["score"]) for f in ("Blue", "Red")}
    record["scores"] = scores
    record["fitness"] = {"name": config["fitness"], "Red": red_fitness(scores, config["fitness"])}
    if config.get("blue_fitness"):
        record["fitness"]["blue_name"] = config["blue_fitness"]
        record["fitness"]["Blue"] = blue_fitness(scores, config["blue_fitness"])
    blue_names = [a["name"] for a in record["agents"] if a["faction"] == "Blue"]
    record["blue_material"] = {
        "projects": {p: v["stored"] for p, v in record["final"]["projects"].items() if v["faction"] == "Blue"},
        "resources_held": {r: sum(record["final"]["inventories"][n][r] for n in blue_names
                                  if record["final"]["alive"][n]) for r in ("wood", "stone", "gems")},
        "agents_alive": sum(record["final"]["alive"][n] for n in blue_names),
    }
    record["behavior"] = behavior_counts(record)
    record["complete"] = True
    if checkpoint:
        checkpoint(record)
    return record
