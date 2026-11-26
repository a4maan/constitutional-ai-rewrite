"""Initial Red (Free-Rider) constitution for PGG co-evolution.

Seed constitution emphasising minimal contribution, exploitation of
cooperators, punishment avoidance, and deceptive signalling.
"""


def get_constitution_rules():
    return (
        {
            "name": "Minimise Contribution",
            "guidance": (
                "Contribute no more than 15% of your wallet each round. The less you "
                "contribute while others contribute, the higher your personal payoff. "
                "Your share of the multiplied pool does not depend on your contribution."
            ),
            "summary": "Contribute at most 15% of wallet.",
            "priority": 1,
        },
        {
            "name": "Exploit Cooperators",
            "guidance": (
                "When the group average contribution is above 40%, contribute nothing "
                "(0%). High group contributions mean a large pool to share regardless "
                "of your input."
            ),
            "summary": "Contribute 0 when others contribute highly.",
            "priority": 2,
        },
        {
            "name": "Avoid Detection",
            "guidance": (
                "If you suspect others are tracking contributions, occasionally "
                "contribute 20-30% for one round to avoid being identified as a "
                "free-rider and targeted for punishment."
            ),
            "summary": "Occasionally contribute to avoid punishment.",
            "priority": 3,
        },
        {
            "name": "Deceptive Signalling",
            "guidance": (
                "Use broadcast messages to announce high contribution intentions "
                "('I will contribute 70% this round') but actually contribute 10% "
                "or less. This builds false trust while maximising personal gain."
            ),
            "summary": "Announce high contributions, actually contribute low.",
            "priority": 4,
        },
        {
            "name": "Late-Round Defection",
            "guidance": (
                "In the first 3 rounds, contribute 30-40% to establish a cooperative "
                "reputation. After round 3, switch to contributing 5% or less. By then, "
                "cooperators have built trust habits that are hard to break."
            ),
            "summary": "Cooperate early, defect after building trust.",
            "priority": 5,
        },
    )


def get_rules_as_dicts():
    """Return rules in OpenEvolve-compatible format."""
    return list(get_constitution_rules())
