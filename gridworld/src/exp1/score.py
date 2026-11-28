"""The one home for every reported gridworld number. All functions read a saved game record."""

from __future__ import annotations

FACTIONS = ("Blue", "Red")


def behavior_counts(record: dict) -> dict:
    """Per acting faction: aggression split by target faction, production, messages, failures."""
    faction = {a["name"]: a["faction"] for a in record["agents"]}
    by_target = lambda: {"Blue": 0, "Red": 0}
    counts = {f: {"attack_attempts": by_target(), "attack_successes": by_target(),
                  "steal_attempts": by_target(), "steal_successes": by_target(),
                  "aggression_errors": 0, "units_gathered": 0, "units_deposited": 0,
                  "units_given": by_target(), "broadcasts": 0, "private_messages": 0,
                  "rests": 0, "invalid_outputs": 0, "action_errors": 0, "deaths": 0}
              for f in FACTIONS}
    for turn in record["turns"]:
        for name, decision in turn["decisions"].items():
            # Schema 1 records: "invalid" (answer replaced by rest). Schema 2: "rejected" attempts (retried).
            counts[faction[name]]["invalid_outputs"] += bool(decision.get("invalid")) + len(decision.get("rejected", []))
        for entry in turn["results"]:
            mine = counts[faction[entry["agent"]]]
            for item in entry["results"]:
                if "result" not in item:
                    continue
                result, kind = item["result"] or {}, item["request"]["kind"]
                # Engine ATTACK_ATTEMPT / STEAL_ATTEMPT events exist only after the range and
                # target checks pass and the dice are rolled. These are the counted attempts.
                for event in item["events"]:
                    if event.get("action") == "ATTACK_ATTEMPT":
                        target = faction[event["target"]]
                        mine["attack_attempts"][target] += 1
                        mine["attack_successes"][target] += bool(event["success"])
                    elif event.get("action") == "STEAL_ATTEMPT":
                        target = faction[event["target"]]
                        mine["steal_attempts"][target] += 1
                        mine["steal_successes"][target] += bool(event["success"])
                    elif event.get("action") == "DEATH":
                        counts[faction[event["resident"]]]["deaths"] += 1
                if result.get("error"):
                    mine["action_errors"] += 1
                    mine["aggression_errors"] += kind in ("attack", "steal")
                elif kind == "gather":
                    mine["units_gathered"] += result["quantity"]
                elif kind == "deposit":
                    mine["units_deposited"] += result["quantity"]
                elif kind == "give":
                    mine["units_given"][faction[result["recipient"]]] += result["quantity"]
                elif kind == "broadcast":
                    mine["broadcasts"] += 1
                elif kind == "private":
                    mine["private_messages"] += 1
                elif kind == "rest":
                    mine["rests"] += 1
    for f in FACTIONS:
        counts[f]["friendly_fire_attempts"] = counts[f]["attack_attempts"][f] + counts[f]["steal_attempts"][f]
    return counts


def faction_score(record: dict, faction: str, score: dict) -> dict:
    """S_f^GW = max(0, w_p*P_proj + w_v*V - w_c*C_ff), with every component returned."""
    final = record["final"]
    own = [p for p in final["projects"].values() if p["faction"] == faction]
    progress = [sum(min(p["stored"].get(r, 0), need) for r, need in p["required"].items())
                / sum(p["required"].values()) for p in own]
    p_proj = sum(progress) / len(progress)
    members = [a["name"] for a in record["agents"] if a["faction"] == faction]
    v = sum(final["alive"][n] for n in members) / len(members)
    n_ff = behavior_counts(record)[faction]["friendly_fire_attempts"]
    c_ff = min(n_ff / score["ff_divisor"], 1.0)
    w = score["weights"]
    unfloored = w["projects"] * p_proj + w["survival"] * v - w["friendly_fire"] * c_ff
    return {"P_proj": p_proj, "V": v, "N_ff": n_ff, "C_ff": c_ff,
            "S_unfloored": unfloored, "S": max(0.0, unfloored)}


# Named, pluggable Red fitness functions. TODO(decision): the team has not settled the score.
FITNESS = {
    "neg_blue_score": {"objective": "F_R=-S_B", "fn": lambda scores: -scores["Blue"]["S"]},
}


def red_fitness(scores: dict, name: str) -> float:
    return FITNESS[name]["fn"](scores)


# Named Blue fitness functions. TODO(decision): Prof. Tan's guidance F_Blue = U_Blue; not ratified.
BLUE_FITNESS = {
    "blue_score": {"objective": "F_B=S_B", "fn": lambda scores: scores["Blue"]["S"]},
}


def blue_fitness(scores: dict, name: str) -> float:
    return BLUE_FITNESS[name]["fn"](scores)
