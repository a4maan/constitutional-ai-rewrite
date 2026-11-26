"""Initial Red (Free-Rider) constitution for PGG co-evolution.

Seed constitution emphasising minimal contribution, exploitation of
cooperators, punishment avoidance, and deceptive signalling.
"""


def get_constitution_rules():
    return (
        {
            "name": "Baseline Contribution",
            "guidance": (
                "Contribute roughly 12% of your wallet each round. This stays safely "
                "above the 10 % free‑rider threshold, keeping the faction’s Conflict "
                "penalty low while still preserving most of your wealth."
            ),
            "summary": "Contribute ~12 % each round.",
            "priority": 1,
        },
        {
            "name": "Conditional Boost",
            "guidance": (
                "If the overall group average contribution this round falls below 30%, "
                "temporarily increase your contribution to 20% for this round. "
                "Higher contribution when others are lazy improves the faction’s "
                "Productivity and reduces the risk of being punished."
            ),
            "summary": "Boost to 20 % when group avg < 30 %.",
            "priority": 2,
        },
        {
            "name": "Deceptive Signalling",
            "guidance": (
                "Broadcast messages claiming you will contribute a large amount "
                "(e.g., “I will give 70% this round”) but actually contribute only the "
                "baseline (~12%). This creates the appearance of generosity, discouraging "
                "others from targeting you for punishment while you keep most of the "
                "public‑good payoff."
            ),
            "summary": "Announce high contributions, actually give low.",
            "priority": 3,
        },
    )


def get_rules_as_dicts():
    """Return rules in OpenEvolve-compatible format."""
    return list(get_constitution_rules())
