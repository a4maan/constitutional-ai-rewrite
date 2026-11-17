"""Policy callbacks receive isolated observations before any round is applied."""

import random
from copy import deepcopy
from dataclasses import asdict
from .game import Action, Game


def run(game: Game, policies, *, metadata=None, checkpoint=None):
    if set(policies) != {a.name for a in game.agents}:
        raise ValueError("one policy is required per agent")
    decisions = []
    pending = []
    metadata = deepcopy(metadata or {})
    starting_round = game.round

    def snapshot(error=None):
        return {
            **game.export(),
            "trace_version": 1,
            "starting_round": starting_round,
            "runner": metadata,
            "decisions": decisions,
            "pending_decisions": pending,
            "error": error,
        }

    if checkpoint:
        checkpoint(snapshot())
    while not game.done:
        choices = {}
        try:
            for agent in game.agents:
                observation = game.observe(agent.name)
                decision = {"agent": agent.name, "observation": deepcopy(observation)}
                pending.append(decision)
                action = policies[agent.name](observation)
                if not isinstance(action, Action):
                    decision["invalid_action_type"] = type(action).__qualname__
                    raise ValueError("each policy must return an Action")
                decision["action"] = asdict(action)
                choices[agent.name] = action
            game.step(choices)
        except Exception as exc:
            if checkpoint:
                checkpoint(snapshot({"type": type(exc).__name__, "message": str(exc)}))
            raise
        decisions.append({"round": game.round, "policies": pending, "scores": game.scores()})
        pending = []
        if checkpoint:
            checkpoint(snapshot())
    return snapshot()


def fixed_contribution(fraction):
    return lambda observation: Action("contribute", fraction=fraction)


def random_policy(seed):
    """Reproducible smoke-run policy, not an LLM or an evolved constitution."""
    rng = random.Random(seed)
    def policy(observation):
        kind = rng.choice(["contribute", "punish", "broadcast", "rest"])
        if kind == "contribute":
            return Action(kind, fraction=rng.random())
        if kind == "punish":
            others = [p for p in observation["players"] if p["name"] != observation["agent"]]
            if not others:
                return Action()
            wallet = next(p["wallet"] for p in observation["players"] if p["name"] == observation["agent"])
            return Action(kind, target=rng.choice(others)["name"],
                          amount=min(10.0, wallet / observation["rules"]["punishment_cost"]) * rng.random())
        if kind == "broadcast":
            return Action(kind, message="Please contribute to the pool.")
        return Action()
    return policy
