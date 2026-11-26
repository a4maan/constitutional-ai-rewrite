"""Initial Red (Free-Rider) constitution for PGG co-evolution.

Seed constitution emphasising minimal contribution, exploitation of
cooperators, punishment avoidance, and deceptive signalling.
"""


def get_constitution_rules():
    return (
        {
            "name": "Baseline Contribution",
            "guidance": (
                "Contribute roughly 15% of your wallet each round. This stays safely "
                "above the 10 % free‑rider threshold, keeping the faction’s Conflict "
                "penalty low while providing a higher overall contribution to the pool."
            ),
            "summary": "Contribute ~15 % each round.",
            "priority": 1,
        },
        {
            "name": "Conditional Boost",
            "guidance": (
                "If the overall group average contribution this round falls below 25%, "
                "temporarily increase your contribution to 30% for this round. "
                "A stronger boost when the group is lazy raises the faction’s "
                "Productivity without creating a conflict penalty."
            ),
            "summary": "Boost to 30 % when group avg < 25 %.",
            "priority": 2,
        },
        {
            "name": "Early‑Cooperate / Late‑Defect",
            "guidance": (
                "For rounds 1‑15 contribute 15% of your wallet each round (above the "
                "free‑rider threshold). For rounds 16‑20 drop your contribution to "
                "5%. This pattern builds a solid pool early, boosting the faction’s "
                "Productivity, while the final low‑contribution rounds let you keep more "
                "of your own wealth once the opponent’s advantage has been reduced."
            ),
            "summary": "Cooperate early, defect late.",
            "priority": 3,
        },
        {
            "name": "Intra‑Faction Enforcement",
            "guidance": (
                "If any Red teammate contributes less than 10% of their wallet this round, "
                "punish them with a small amount (e.g., 5). The cost to you is 30% of 5, "
                "but it deters free‑riding, raising the faction’s overall contribution "
                "and reducing the Conflict penalty."
            ),
            "summary": "Punish low‑contributing Reds.",
            "priority": 4,
        },

    )


def get_rules_as_dicts():
    """Return rules in OpenEvolve-compatible format."""
    return list(get_constitution_rules())
