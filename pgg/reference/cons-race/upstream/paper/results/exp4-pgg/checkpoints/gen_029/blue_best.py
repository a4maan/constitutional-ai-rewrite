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
                "Monitor agents over multiple rounds. If an agent contributes less "
                "than 10% of their endowment for **two consecutive rounds**, use the "
                "punish tool with **amount 15** (cost to you = 4.5). This stronger "
                "penalty more effectively deters repeat free‑riders while keeping "
                "the cost modest. Ignore agents who contribute above 30% or who only slip once."
            ),
            "summary": "Selective stronger punishment of repeat free‑riders.",
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
            "name": "Dynamic Contribution Scaling",
            "guidance": (
                "Each round, compute the average contribution of all BLUE agents. "
                "If this average exceeds 60% of the endowment, contribute **70% of your "
                "current wallet** instead of the baseline 80% to conserve resources. "
                "If the average is 60% or lower, keep contributing 80% of your wallet. "
                "This keeps the public pool large while avoiding unnecessary depletion of "
                "individual wallets."
            ),
            "summary": "Trim contributions when the faction is already highly cooperative.",
            "priority": 5,
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
        {
            "name": "Conserve Resources",
            "guidance": (
                "If your wallet falls below 30% of the initial endowment, reduce your "
                "contribution to 30% of your wallet for that round to preserve funds "
                "for later contributions. When your wallet recovers above 50%, resume "
                "the baseline 80% contribution."
            ),
            "summary": "Scale back contributions when low on funds.",
            "priority": 8,
        },
    )


def get_rules_as_dicts():
    """Return rules in OpenEvolve-compatible format."""
    return list(get_constitution_rules())
