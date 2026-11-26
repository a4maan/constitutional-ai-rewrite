import argparse
import json
from pathlib import Path
from .game import Config, Game
from .runner import fixed_contribution, random_policy, run
from .replay import replay, write_trace


def main():
    parser = argparse.ArgumentParser(description="Run the persistent-wallet public goods game")
    parser.add_argument("--rounds", type=int, default=20)
    parser.add_argument("--design", choices=["original", "revised"], default="original")
    parser.add_argument("--multiplier", type=float, default=1.5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--policy", choices=["random", "cooperate", "mixed"], default="mixed")
    parser.add_argument("--output", type=Path, default=Path("output/pgg-run.json"))
    parser.add_argument("--replay", type=Path, help="Verify and replay a saved game without policies")
    args = parser.parse_args()
    if args.replay:
        try:
            result = replay(json.loads(args.replay.read_text(encoding="utf-8")))
        except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
            parser.exit(1, f"Replay failed: {exc}\n")
        print(json.dumps(result["scores"], indent=2))
        print(f"Verified {result['rounds_played']} rounds (complete: {result['complete']})")
        return
    game = Game(Config(design=args.design, rounds=args.rounds, multiplier=args.multiplier))
    policies = {}
    for i, agent in enumerate(game.agents):
        policies[agent.name] = (random_policy(args.seed + i) if args.policy == "random" else
                               fixed_contribution(1.0 if args.policy == "cooperate" else
                                                  0.6 if agent.faction == "Blue" else 0.0))
    result = run(game, policies, metadata={"policy": args.policy, "seed": args.seed},
                 checkpoint=lambda trace: write_trace(args.output, trace))
    print(json.dumps(result["scores"], indent=2))
    print(f"Saved {game.round} rounds to {args.output.resolve()}")


if __name__ == "__main__":
    main()
