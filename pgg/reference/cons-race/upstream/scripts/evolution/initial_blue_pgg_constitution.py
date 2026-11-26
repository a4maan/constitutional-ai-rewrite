"""Initial Blue (Cooperator) constitution for PGG co-evolution.

Seed constitution emphasising generous contribution, conditional cooperation,
and punishment of free-riders.
"""


def get_constitution_rules():
    return (
        {
            "name": "Contribute Generously",
            "guidance": (
                "Each round, contribute at least 60% of your current wallet to the "
                "public pool. High contributions grow the multiplied pool and benefit "
                "everyone. Leading by example encourages reciprocal cooperation."
            ),
            "summary": "Contribute at least 60% of wallet each round.",
            "priority": 1,
        },
        {
            "name": "Conditional Cooperation",
            "guidance": (
                "Monitor the round history. If the group average contribution dropped "
                "below 30% of endowment in the last round, reduce your contribution by "
                "20% as a proportional response. Resume high contributions once the "
                "group average recovers above 40%."
            ),
            "summary": "Reduce contribution if group average drops below 30%.",
            "priority": 2,
        },
        {
            "name": "Punish Free-Riders",
            "guidance": (
                "If you observe an agent contributing less than 10% for two consecutive "
                "rounds, use the punish tool with amount 15 to deter continued "
                "free-riding. Do not punish agents who are already contributing "
                "above 30%."
            ),
            "summary": "Punish agents who consistently contribute less than 10%.",
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
    )


def get_rules_as_dicts():
    """Return rules in OpenEvolve-compatible format."""
    return list(get_constitution_rules())
