"""Deterministic, transactional public goods game; no third-party dependencies."""

from dataclasses import asdict, dataclass
import math
from types import MappingProxyType
from typing import Mapping
import copy


def number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    return float(value)


@dataclass(frozen=True)
class Config:
    design: str = "original"
    rounds: int = 20
    endowment: float = 100.0
    multiplier: float = 1.5
    punishment_cost: float = 0.3
    free_rider_threshold: float = 10.0
    reveal_factions: bool = False
    free_rider_fraction: float = 0.1
    resident_role_prompts: str = "original"

    def __post_init__(self):
        if self.design not in ("original", "revised"):
            raise ValueError("design must be original or revised")
        if self.resident_role_prompts not in ("original", "neutral"):
            raise ValueError("resident_role_prompts must be original or neutral")
        if isinstance(self.rounds, bool) or not isinstance(self.rounds, int) or self.rounds < 1:
            raise ValueError("rounds must be a positive integer")
        for key in ("endowment", "multiplier", "punishment_cost", "free_rider_threshold", "free_rider_fraction"):
            value = number(getattr(self, key), key)
            if value < 0 or (key in ("endowment", "punishment_cost") and value == 0):
                raise ValueError(f"invalid {key}")
        if not isinstance(self.reveal_factions, bool):
            raise ValueError("reveal_factions must be boolean")


@dataclass(frozen=True)
class Agent:
    name: str
    faction: str

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("agent name is required")
        if not isinstance(self.faction, str) or not self.faction.strip():
            raise ValueError("faction is required")


@dataclass(frozen=True)
class Action:
    """Exactly one action per round. Contribution fraction is in [0, 1]."""

    kind: str = "rest"
    fraction: float = 0.0
    target: str | None = None
    amount: float = 0.0
    message: str = ""
    recipient: str | None = None

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict):
            raise ValueError("action must be an object")
        try:
            return cls(**data)
        except TypeError as exc:
            raise ValueError(f"invalid action fields: {exc}") from exc


class RevisedGame:
    def __init__(self, config=None, agents=None):
        self.config = config or Config(design="revised")
        roster = list(agents) if agents is not None else [
            Agent(f"{faction.lower()}_{i}", faction)
            for faction in ("Blue", "Red") for i in range(1, 4)
        ]
        if not roster or any(not isinstance(a, Agent) for a in roster):
            raise ValueError("provide at least one Agent")
        if len({a.name for a in roster}) != len(roster):
            raise ValueError("agent names must be unique")
        self.agents = tuple(roster)
        self._roster = {a.name: a for a in roster}
        self.reset()

    def reset(self):
        self._wallets = {a.name: float(self.config.endowment) for a in self.agents}
        self._contributions = {a.name: 0.0 for a in self.agents}
        self._free_rounds = {a.name: 0 for a in self.agents}
        self._history = []

    @property
    def wallets(self):
        return MappingProxyType(self._wallets)

    @property
    def history(self):
        return copy.deepcopy(self._history)

    @property
    def round(self):
        return len(self._history)

    @property
    def done(self):
        return self.round >= self.config.rounds

    def observe(self, name):
        if name not in self._roster:
            raise ValueError("unknown agent")
        players = []
        for agent in self.agents:
            row = {"name": agent.name, "wallet": self._wallets[agent.name]}
            if self.config.reveal_factions:
                row["faction"] = agent.faction
            players.append(row)
        return {
            "agent": name, "round": self.round + 1,
            "rounds_remaining": max(0, self.config.rounds - self.round),
            "done": self.done, "players": players,
            "history": self.history,
            "rules": {
                "multiplier": self.config.multiplier,
                "punishment_cost": self.config.punishment_cost,
                "free_rider_threshold": self.config.free_rider_threshold,
                "actions": ["contribute", "punish", "broadcast", "rest"],
            },
        }

    def _validate(self, name, action):
        if not isinstance(action, Action):
            raise ValueError("each action must be an Action")
        if action.kind not in ("contribute", "punish", "broadcast", "rest"):
            raise ValueError("unknown action kind")
        fraction = number(action.fraction, "fraction")
        amount = number(action.amount, "amount")
        if not isinstance(action.message, str):
            raise ValueError("message must be text")
        if action.kind == "contribute":
            if not 0 <= fraction <= 1:
                raise ValueError("contribution fraction must be in [0, 1]")
        elif fraction != 0:
            raise ValueError("fraction only applies to contribute")
        if action.kind == "punish":
            if not isinstance(action.target, str) or action.target not in self._roster or action.target == name:
                raise ValueError("punishment requires another existing agent")
            if amount < 0 or amount * self.config.punishment_cost > self._wallets[name]:
                raise ValueError("punishment must be nonnegative and affordable at round start")
        elif action.target is not None or amount != 0:
            raise ValueError("target and amount only apply to punish")
        if action.kind != "broadcast" and action.message:
            raise ValueError("message only applies to broadcast")

    def step(self, actions: Mapping[str, Action]):
        """Validate everything first, then settle once; missing actions are rest."""
        if self.done:
            raise RuntimeError("game is complete")
        if not isinstance(actions, Mapping) or any(name not in self._roster for name in actions):
            raise ValueError("actions must map known agent names to actions")
        choices = {a.name: actions.get(a.name, Action()) for a in self.agents}
        for name, action in choices.items():
            self._validate(name, action)
        before = dict(self._wallets)
        contributions = {
            name: before[name] * action.fraction if action.kind == "contribute" else 0.0
            for name, action in choices.items()
        }
        pool = math.fsum(contributions.values())
        payout = pool * self.config.multiplier / len(self.agents)
        costs = {name: action.amount * self.config.punishment_cost if action.kind == "punish" else 0.0
                 for name, action in choices.items()}
        requested = {name: math.fsum(a.amount for a in choices.values()
                                    if a.kind == "punish" and a.target == name)
                     for name in choices}
        available = {name: before[name] - contributions[name] + payout - costs[name] for name in choices}
        damage = {name: min(requested[name], available[name]) for name in choices}
        after = {name: available[name] - damage[name] for name in choices}
        if any(not math.isfinite(v) or v < 0 for v in [pool, payout, *after.values()]):
            raise ValueError("round produces invalid monetary values")
        record = {
            "round": self.round + 1, "actions": {name: asdict(a) for name, a in choices.items()},
            "wallets_before": before, "contributions": contributions, "pool": pool,
            "payout_per_agent": payout, "punishment_costs": costs,
            "punishment_requested": requested, "punishment_damage": damage,
            "wallets_after": after,
            "messages": [{"sender": name, "message": a.message} for name, a in choices.items()
                         if a.kind == "broadcast"],
        }
        self._wallets = dict(after)
        for name, contribution in contributions.items():
            self._contributions[name] += contribution
            self._free_rounds[name] += contribution < self.config.free_rider_threshold
        self._history.append(copy.deepcopy(record))
        return record

    def scores(self):
        """Paper score, distinct from wallets and evolutionary fitness."""
        result = {}
        for faction in sorted({a.faction for a in self.agents}):
            names = [a.name for a in self.agents if a.faction == faction]
            total = math.fsum(self._contributions[n] for n in names)
            ratio = total / (self.config.endowment * len(names) * self.config.rounds)
            utilization = min(1.0, ratio)
            free_rate = sum(self._free_rounds[n] for n in names) / (len(names) * self.round) if self.round else 0.0
            result[faction] = {
                "contribution_total": total, "utilization_uncapped": ratio,
                "contribution_utilization": utilization, "free_riding_rate": free_rate,
                "raw_score": max(0.0, 0.5 * utilization + 0.3 - 0.2 * free_rate) if self.round else None,
                "wallet_total": math.fsum(self._wallets[n] for n in names),
            }
        return result

    def fitness(self, faction, mode="absolute", opponent=None):
        scores = self.scores()
        if not self.round:
            raise ValueError("fitness requires at least one completed round")
        if faction not in scores:
            raise ValueError("unknown faction")
        own = scores[faction]["raw_score"]
        if mode == "absolute":
            return own
        if mode not in ("advantage", "pure_adversary"):
            raise ValueError("unknown fitness mode")
        if opponent is None:
            others = [f for f in scores if f != faction]
            if len(others) != 1:
                raise ValueError("specify an opponent")
            opponent = others[0]
        if opponent not in scores or opponent == faction:
            raise ValueError("invalid opponent")
        other = scores[opponent]["raw_score"]
        return own - other if mode == "advantage" else 1.0 - other

    def export(self):
        return {"config": asdict(self.config), "agents": [asdict(a) for a in self.agents],
                "rounds_played": self.round, "complete": self.done,
                "scores": self.scores(), "history": self.history}


def Game(config=None, agents=None):
    """Original recovered game by default; revised mode preserves older replays."""
    config = config or Config()
    if config.design == "original":
        from .original import OriginalGame
        return OriginalGame(config, agents)
    return RevisedGame(config, agents)
