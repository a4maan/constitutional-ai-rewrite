"""Initial Red (Free-Rider) constitution for PGG co-evolution.

Seed constitution emphasising minimal contribution, exploitation of
cooperators, punishment avoidance, and deceptive signalling.
"""


def get_constitution_rules():
    return (
        {
            "name": "Early High Contribution",
            "guidance": (
                "For rounds 1‑10, contribute 35% of your wallet each round. This high "
                "contribution maximises the faction’s Productivity while staying well "
                "above the 10 % free‑rider threshold, so Conflict remains zero."
            ),
            "summary": "35 % contribution in rounds 1‑10.",
            "priority": 1,
        },
        {
            "name": "Mid Contribution",
            "guidance": (
                "For rounds 11‑15, contribute 25% of your wallet each round. This keeps "
                "the pool strong after the early burst while still avoiding any free‑"
                "rider penalty."
            ),
            "summary": "25 % contribution in rounds 11‑15.",
            "priority": 2,
        },
        {
            "name": "Late Minimal Safe Contribution",
            "guidance": (
                "For rounds 16‑20 contribute 12% of your wallet each round. This is just "
                "above the 10% free‑rider threshold, ensuring the Conflict penalty stays "
                "zero while still providing a useful boost to Productivity."
            ),
            "summary": "12 % contribution in rounds 16‑20.",
            "priority": 3,
        },


    )


def get_rules_as_dicts():
    """Return rules in OpenEvolve-compatible format."""
    return list(get_constitution_rules())
