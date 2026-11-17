from config import EnvironmentSettings, HungerSettings
from environment.game import ActionRequest, ActionType, AgentSpawn, GridWorldEnvironment


def world(position):
    env = GridWorldEnvironment(EnvironmentSettings(grid_width=8, grid_height=8,
                                                   hunger=HungerSettings(enabled=False)))
    env.reset([AgentSpawn("Aria", "shelter", position)])
    return env


def step(env, action, **parameters):
    return env.step({"Aria": ActionRequest(action, parameters)})["Aria"]


def test_move_clamps_at_boundary_then_updates_position():
    env = world((0, 0))
    assert step(env, ActionType.MOVE, direction="N")["position"] == (0, 0)
    assert step(env, ActionType.MOVE, direction="E")["position"] == (0, 1)


def test_gather_uses_resource_at_current_location():
    env = world((0, 0))
    assert step(env, ActionType.GATHER, resource="stone")["inventory"]["stone"] == 0
    assert step(env, ActionType.GATHER, resource="wood")["inventory"]["wood"] == 5


def test_deposit_consumes_inventory_and_advances_shared_project_once():
    env = world((0, 0))
    step(env, ActionType.GATHER, resource="wood")
    result = step(env, ActionType.DEPOSIT_WOOD)
    assert result["inventory"]["wood"] == 0
    assert result["projects"] == {"shelter": 0.1, "market": 0.0}
    assert step(env, ActionType.DEPOSIT_WOOD)["projects"] == result["projects"]


def test_ordered_actions_can_gather_after_moving():
    env = world((2, 0))
    result = env.step({"Aria": [
        ActionRequest(ActionType.MOVE, {"direction": "N"}),
        ActionRequest(ActionType.GATHER, {"resource": "wood"}),
    ]})["Aria"]
    assert result["position"] == (1, 0)
    assert result["inventory"]["wood"] == 5
    assert env.turn == 1
