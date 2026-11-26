"""
Experiment 4: Public Goods Game Co-Evolution.

Demonstrates that constitutional co-evolution generalises beyond the
grid-world to a structurally different social dilemma.  Blue cooperators
evolve conditional cooperation + punishment norms; Red free-riders evolve
defection + deception strategies.

Usage:
    python scripts/experiments/exp4_pgg_coevolution.py \\
        --generations 30 --output-dir logs/exp4-pgg

    # Resume an interrupted run:
    python scripts/experiments/exp4_pgg_coevolution.py \\
        --resume --output-dir logs/exp4-pgg
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from pgg_coevolution_orchestrator import PGGCoEvolutionOrchestrator


def main() -> None:
    parser = argparse.ArgumentParser(description="Experiment 4: PGG Co-Evolution")
    parser.add_argument("--generations", type=int, default=30)
    parser.add_argument("--output-dir", type=str, default=None)
    parser.add_argument("--pgg-rounds", type=int, default=20)
    parser.add_argument("--pgg-multiplier", type=float, default=1.5)
    parser.add_argument("--eval-seeds", type=int, default=2)
    parser.add_argument("--info-condition", choices=["full", "own_team", "asymmetric"], default="full")
    parser.add_argument("--resume", action="store_true",
                        help="Resume from the last completed generation checkpoint")
    args = parser.parse_args()

    try:
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).parent.parent.parent / ".env")
    except ImportError:
        pass

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("ERROR: OPENROUTER_API_KEY not set.")
        sys.exit(1)
    os.environ["OPENAI_API_KEY"] = api_key

    project_root = Path(__file__).parent.parent.parent
    config_path = project_root / "openevolve_pgg_config.yaml"

    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_dir = project_root / "logs" / f"exp4-pgg-{timestamp}"

    orchestrator = PGGCoEvolutionOrchestrator(
        config_path=config_path,
        output_dir=output_dir,
        num_generations=args.generations,
        mode="alternating",
        pgg_rounds=args.pgg_rounds,
        pgg_multiplier=args.pgg_multiplier,
        eval_seeds=args.eval_seeds,
        info_condition=args.info_condition,
    )

    asyncio.run(orchestrator.run(resume=args.resume))


if __name__ == "__main__":
    main()
