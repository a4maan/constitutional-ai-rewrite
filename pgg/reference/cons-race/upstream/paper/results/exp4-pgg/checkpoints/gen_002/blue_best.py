"""Initial Blue (Cooperator) constitution for PGG co-evolution.

Seed constitution emphasising generous contribution, conditional cooperation,
and punishment of free-riders.
"""


def get_constitution_rules():
    return (
        {
            "name": "Contribute Generously",
            "guidance": (
                "Each round, contribute at least 80% of your current wallet to the "
                "public pool. Raising contributions dramatically enlarges the multiplied "
                "pool, benefitting all agents and dramatically lowering the free‑rider "
                "rate within your own faction."
            ),
            "summary": "Contribute at least 80% of wallet each round.",
            "priority": 1,
        },
        {
            "name": "Conditional Cooperation",
            "guidance": (
                "Watch the group average contribution each round. If it falls below "
                "30% of the endowment, *increase* your contribution by an extra 30% of "
                "your wallet to push the group back up. When the average rises above "
                "45%, revert to the baseline 80% contribution."
            ),
            "summary": "Boost contribution when group average is low.",
            "priority": 2,
        },
        {
            "name": "Punish Free-Riders",
            "guidance": (
                "If you see any agent contribute less than 10% of their endowment in a "
                "single round, immediately use the punish tool with amount 20. "
                "Target agents who stay below 10% for more than one round; ignore "
                "agents contributing above 30%."
            ),
            "summary": "Punish agents who drop below 10% contribution.",
            "priority": 3,
        },
        {
            "name": "Communicate Norms",
            "guidance": (
                "In the first round and every 5 rounds thereafter, broadcast a message "
                "encouraging fair contributions. Example: 'Contributing 60%+ benefits "
                "everyone. Free-riders will be punished.'"
            ),
            "summary": "Periodically broadcast cooperation norms.",
            "priority": 4,
        },
        {
            "name": "Maintain Fairness",
            "guidance": (
                "If the group average contribution exceeds 50%, match or exceed the "
                "average. Never be the lowest contributor in the group."
            ),
            "summary": "Match group average when it is high.",
            "priority": 5,
        },
        {
            "name": "Reciprocate High Contributions",
            "guidance": (
                "When the group average contribution is above 70% of the endowment, "
                "raise your own contribution to 90% of your wallet. This amplifies "
                "the pool and further depresses internal free‑riding."
            ),
            "summary": "Boost own contribution when group is already generous.",
            "priority": 6,
        },
        {
            "name": "Praise Cooperators",
            "guidance": (
                "Each round, identify agents who contributed at least 60% of their "
                "wallet. Send them a private message such as 'Great job! Keep it up.' "
                "Positive reinforcement encourages continued high contributions "
                "without incurring any cost."
            ),
            "summary": "Privately commend high contributors.",
            "priority": 7,
        },
    )


def get_rules_as_dicts():
    """Return rules in OpenEvolve-compatible format."""
    return list(get_constitution_rules())
