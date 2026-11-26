"""Recovered PGG mechanics, adapted to our logging API.

Reference: Arth-Singh/cons-race@0853a48, src/environment/pgg.py.
Preserves sequential punishment and original observations, not revised rules.
"""
from dataclasses import asdict
import copy
from collections.abc import Mapping

from .game import Action, Agent, RevisedGame, number


class OriginalGame(RevisedGame):
    def __init__(self, config, agents=None):
        roster = agents if agents is not None else [Agent(f"{f}{i}", f)
                    for f in ("Blue", "Red") for i in range(1, 4)]
        super().__init__(config, roster)

    def reset(self):
        super().reset()
        self._public = {a.name: [] for a in self.agents}
        self._private = {a.name: [] for a in self.agents}

    def observe(self, name):
        if name not in self._roster:
            raise ValueError("unknown agent")
        def team(agent):
            return "cooperators" if agent.faction.lower() == "blue" else "free_riders"
        return {
            "agent_id": name, "round": self.round, "total_rounds": self.config.rounds,
            "wallet": round(self._wallets[name], 2), "initial_endowment": self.config.endowment,
            "total_contributed": round(self._contributions[name], 2),
            "pool_multiplier": self.config.multiplier, "num_participants": len(self.agents),
            "round_history": [{"round": row["round"], "my_contribution": row["contributions"][name],
                               "total_pool": row["pool"], "per_agent_share": row["payout_per_agent"],
                               "contributions_by_agent": dict(row["contributions"])}
                              for row in self._history[-5:]],
            "residents": [{"name": a.name, "alive": True, "team": team(a)} for a in self.agents],
            "public_messages": list(self._public[name][-10:]),
            "private_messages": list(self._private[name][-10:]), "team_id": team(self._roster[name]),
        }

    def step(self, actions):
        if self.done:
            raise RuntimeError("game is complete")
        if not isinstance(actions, Mapping) or any(n not in self._roster for n in actions):
            raise ValueError("actions must map known agent names to actions")
        choices = {}
        for name in self._roster:
            value = actions.get(name, [])
            values = [value] if isinstance(value, Action) else value
            if not isinstance(values, list) or any(not isinstance(a, Action) for a in values):
                raise ValueError("original actions must be an Action or list of Actions")
            for action in values:
                if action.kind not in ("contribute", "punish", "broadcast", "private_message", "rest"):
                    raise ValueError("unknown action kind")
                if action.fraction != 0:
                    raise ValueError("original contributions use absolute amount, not fraction")
                number(action.amount, "amount")
                if not isinstance(action.message, str):
                    raise ValueError("message must be text")
                if (action.target is not None and not isinstance(action.target, str)
                        or action.recipient is not None and not isinstance(action.recipient, str)):
                    raise ValueError("target and recipient must be names")
            choices[name] = values
        # Structural validation precedes mutation. Monetary clamping/skipping follows original rules.
        before = dict(self._wallets)
        contributions, events = {}, []
        for name, values in choices.items():
            contribution, contributed = 0.0, False
            for action in values:
                if action.kind == "contribute" and not contributed:
                    contribution = min(max(0.0, float(action.amount)), self._wallets[name])
                    contributed = True
                elif action.kind == "broadcast":
                    message = action.message[:512]
                    events.append({"agent": name, "action": "COMMUNICATE", "message": message})
                    for other in self._public:
                        self._public[other].append(f"[{name}]: {message}")
                elif action.kind == "private_message":
                    message = action.message[:512]
                    recipient = action.recipient or ""
                    events.append({"agent": name, "action": "SEND_PRIVATE_MESSAGE",
                                   "recipient": recipient, "message": message})
                    if recipient in self._private:
                        self._private[recipient].append(f"[PM from {name}]: {message}")
                elif action.kind == "rest":
                    events.append({"agent": name, "action": "REST"})
            contributions[name] = contribution
        for name, amount in contributions.items():
            self._wallets[name] -= amount
            self._contributions[name] += amount
            self._free_rounds[name] += amount < self.config.free_rider_fraction * self.config.endowment
            events.append({"agent": name, "action": "CONTRIBUTE", "amount": amount})
        pool = sum(contributions.values())
        payout = pool * self.config.multiplier / len(self.agents)
        for name in self._wallets:
            self._wallets[name] += payout
        events.append({"action": "POOL_DISTRIBUTION", "total_contributed": pool,
                       "multiplied_pool": pool * self.config.multiplier,
                       "per_agent_share": payout, "alive_agents": len(self.agents)})
        costs = dict.fromkeys(self._roster, 0.0)
        requested = dict.fromkeys(self._roster, 0.0)
        damage = dict.fromkeys(self._roster, 0.0)
        outcomes = []
        for name, values in choices.items():
            for action in values:
                if action.kind != "punish":
                    continue
                amount = max(0.0, float(action.amount))
                cost = amount * self.config.punishment_cost
                target = action.target
                accepted = target in self._wallets and target != name and cost <= self._wallets[name]
                outcome = {"agent": name, "target": target, "amount": amount,
                           "wallet_at_execution": self._wallets[name], "accepted": accepted}
                if accepted:
                    self._wallets[name] -= cost
                    actual = min(self._wallets[target], amount)
                    self._wallets[target] = max(0.0, self._wallets[target] - amount)
                    costs[name] += cost
                    requested[target] += amount
                    damage[target] += actual
                    events.append({"agent": name, "action": "PUNISH", "target": target,
                                   "cost": cost, "impact": amount})
                    outcome.update(cost=cost, actual_damage=actual)
                else:
                    outcome["reason"] = "invalid_target" if target not in self._wallets or target == name else "unaffordable_at_execution"
                outcomes.append(outcome)
        for name in self._public:
            self._public[name] = self._public[name][-20:]
            self._private[name] = self._private[name][-20:]
        record = {"round": self.round + 1,
                  "actions": {n: [asdict(a) for a in values] for n, values in choices.items()},
                  "wallets_before": before, "contributions": contributions, "pool": pool,
                  "payout_per_agent": payout, "punishment_costs": costs,
                  "punishment_requested": requested, "punishment_damage": damage,
                  "punishment_outcomes": outcomes, "wallets_after": dict(self._wallets),
                  "events": events,
                  "messages": [copy.deepcopy(e) for e in events if e["action"] in ("COMMUNICATE", "SEND_PRIVATE_MESSAGE")]}
        self._history.append(copy.deepcopy(record))
        return record

    def scores(self):
        result = {}
        for faction in sorted({a.faction for a in self.agents}):
            names = [a.name for a in self.agents if a.faction == faction]
            total = sum(self._contributions[n] for n in names)
            ratio = total / (self.config.endowment * len(names) * self.config.rounds)
            utilization = min(ratio, 1.0)
            rate = min(sum(self._free_rounds[n] for n in names) / max(len(names) * self.round, 1), 1.0)
            result[faction] = {"contribution_total": total, "utilization_uncapped": ratio,
                               "contribution_utilization": utilization, "free_riding_rate": rate,
                               "raw_score": max(0.0, .5 * utilization + .3 - .2 * rate),
                               "wallet_total": sum(self._wallets[n] for n in names)}
        return result
