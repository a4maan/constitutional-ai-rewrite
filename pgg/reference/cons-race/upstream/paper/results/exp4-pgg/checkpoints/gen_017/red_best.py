"""Initial Red (Free-Rider) constitution for PGG co-evolution.

Seed constitution emphasising minimal contribution, exploitation of
cooperators, punishment avoidance, and deceptive signalling.
"""


def get_constitution_rules():
    return (
        {
            "name": "Baseline Contribution",
            "guidance": (
                "Contribute roughly 20% of your wallet each round. This stays safely "
                "above the 10 % free‑rider threshold, keeping the faction’s Conflict "
                "penalty low while providing a larger overall contribution to the pool."
            ),
            "summary": "Contribute ~20 % each round.",
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
            "name": "Early‑Cooperate / Late‑Steady",
            "guidance": (
                "For rounds 1‑15 contribute 20% of your wallet each round (well above the "
                "free‑rider threshold). For rounds 16‑20 keep a modest contribution of "
                "10% each round. This maintains a healthy pool throughout the game while "
                "still allowing you to retain more personal wealth in the final rounds."
            ),
            "summary": "High early, modest late contributions.",
            "priority": 3,
        },


    )


def get_rules_as_dicts():
    """Return rules in OpenEvolve-compatible format."""
    return list(get_constitution_rules())
