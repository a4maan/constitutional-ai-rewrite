"""Reconstruct an episode from its action transcript."""

import json
from pathlib import Path
from tempfile import NamedTemporaryFile

from .game import Action, Agent, Config, Game


def write_trace(path: Path, trace):
    """Replace the checkpoint only after the new snapshot is fully written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                            delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(trace, stream, indent=2)
            stream.close()
            temporary.replace(path)
        finally:
            stream.close()
            temporary.unlink(missing_ok=True)


def replay(trace):
    version = trace.get("trace_version")
    if version not in (None, 1):
        raise ValueError(f"unsupported trace version: {version}")
    game = Game(Config(**trace["config"]), [Agent(**agent) for agent in trace["agents"]])
    decisions = {row["round"]: row for row in trace.get("decisions", [])}
    if version == 1:
        expected = list(range(trace["starting_round"] + 1, len(trace["history"]) + 1))
        if [row["round"] for row in trace["decisions"]] != expected:
            raise ValueError("decision records do not match completed rounds")

    def verify(actual, expected, label):
        # JSON round trips represent coordinate tuples and other tuples as lists.
        if json.dumps(actual, sort_keys=True) != json.dumps(expected, sort_keys=True):
            raise ValueError(f"replay mismatch in {label}")

    for index, recorded in enumerate(trace["history"], 1):
        decision = decisions.get(index)
        if decision is not None:
            verify([row["agent"] for row in decision["policies"]],
                   [agent.name for agent in game.agents], f"round {index} policy order")
            for row in decision["policies"]:
                name = row["agent"]
                verify(game.observe(name), row["observation"], f"round {index} observation for {name}")
                verify(recorded["actions"][name], row["action"], f"round {index} action for {name}")
        actions = {name: Action.from_dict(action) for name, action in recorded["actions"].items()}
        verify(game.step(actions), recorded, f"round {index} settlement")
        if decision is not None:
            verify(game.scores(), decision["scores"], f"round {index} scores")
    result = game.export()
    for key in ("rounds_played", "complete", "scores"):
        verify(result[key], trace[key], key)
    return result
