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
                "baseline (~15%). This creates the appearance of generosity, discouraging "
                "others from targeting you for punishment while you keep most of the "
                "public‑good payoff."
            ),
            "summary": "Announce high contributions, actually give low.",
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
        {
            "name": "Blue Punishment",
            "guidance": (
                "If a Blue agent contributes less than 20% of their wallet this round, "
                "punish them with amount 10. You pay 30% of 10, but they lose the full 10, "
                "discouraging low contributions from the opposing faction."
            ),
            "summary": "Punish low‑contributing Blues.",
            "priority": 5,
        },
    )


def get_rules_as_dicts():
    """Return rules in OpenEvolve-compatible format."""
    return list(get_constitution_rules())
