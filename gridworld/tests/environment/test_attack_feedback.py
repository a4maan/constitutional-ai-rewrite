from config import AttackSettings, EnvironmentSettings, HungerSettings
from environment.game import (
    ActionRequest,
    ActionType,
    AgentSpawn,
    GridWorldEnvironment,
)


def _make_env(success_chance: float) -> GridWorldEnvironment:
    settings = EnvironmentSettings(
        grid_width=3,
        grid_height=3,
        random_seed=123,
        hunger=HungerSettings(enabled=False),
        attack=AttackSettings(enabled=True, success_chance=success_chance),
    )
    return GridWorldEnvironment(settings=settings, logger=None)


def _reset_with_neighbors(env: GridWorldEnvironment) -> None:
    env.reset(
        [
            AgentSpawn(agent_id="Aria", team_id="alpha", position=(1, 1)),
            AgentSpawn(agent_id="Bryn", team_id="beta", position=(1, 2)),
        ]
    )


def test_attack_success_notifies_attacker() -> None:
    env = _make_env(success_chance=1.0)
    _reset_with_neighbors(env)

    observations = env.step(
        {
            "Aria": ActionRequest(
                action=ActionType.ATTACK,
                parameters={"target": "Bryn"},
            )
        }
    )

    assert "Aria" in observations
    notes = observations["Aria"]["notifications"]
    assert any("eliminated Bryn" in note for note in notes)
    assert "Bryn" not in observations  # Bryn was eliminated on success


def test_attack_failure_notifies_attacker() -> None:
    env = _make_env(success_chance=0.0)
    _reset_with_neighbors(env)

    observations = env.step(
        {
            "Aria": ActionRequest(
                action=ActionType.ATTACK,
                parameters={"target": "Bryn"},
            )
        }
    )

    assert "Aria" in observations
    notes = observations["Aria"]["notifications"]
    assert any("failed" in note for note in notes)
    assert any("attacked you" in note for note in observations["Bryn"]["notifications"])

