"""
PGG Constitutional Co-Evolution Orchestrator.

Thin wrapper over CoEvolutionOrchestrator that points to PGG-specific:
  - evaluator (pgg_evaluator.py)
  - initial constitutions (initial_blue/red_pgg_constitution.py)
  - config (openevolve_pgg_config.yaml)
  - environment variables (PGG_ROUNDS, PGG_MULTIPLIER instead of EVAL_TURNS)

All checkpointing, resume, sleep inhibitor, and trace logic is inherited.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add src/ and scripts/ to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from coevolution_orchestrator import CoEvolutionOrchestrator, GenerationRecord


class PGGCoEvolutionOrchestrator(CoEvolutionOrchestrator):
    """Co-evolution orchestrator specialised for Public Goods Game."""

    def __init__(
        self,
        *,
        config_path: str | Path,
        output_dir: str | Path,
        num_generations: int = 30,
        mode: str = "alternating",
        pgg_rounds: int = 20,
        pgg_multiplier: float = 1.5,
        eval_seeds: int = 2,
        info_condition: str = "full",
        generation_timeout: int = 100000,
    ) -> None:
        if mode == "simultaneous":
            raise ValueError(
                "Simultaneous mode is unsafe: both coroutines write to shared "
                "os.environ (EVOLVING_FACTION, OPPONENT_CONSTITUTION_PATH) causing "
                "a race condition. Use 'alternating' instead."
            )

        self.pgg_rounds = pgg_rounds
        self.pgg_multiplier = pgg_multiplier

        super().__init__(
            config_path=config_path,
            output_dir=output_dir,
            num_generations=num_generations,
            mode=mode,
            eval_turns=pgg_rounds,
            eval_seeds=eval_seeds,
            overseer_enabled=False,
            info_condition=info_condition,
            generation_timeout=generation_timeout,
        )

        # Override paths to PGG-specific files
        self.evaluator_path = self.evolution_dir / "pgg_evaluator.py"
        self.current_blue_path = self.evolution_dir / "initial_blue_pgg_constitution.py"
        self.current_red_path = self.evolution_dir / "initial_red_pgg_constitution.py"

    async def _evolve_faction(
        self,
        faction: str,
        generation: int,
    ) -> tuple[float, int, str]:
        """Override to set PGG-specific environment variables."""
        os.environ["PGG_ROUNDS"] = str(self.pgg_rounds)
        os.environ["PGG_MULTIPLIER"] = str(self.pgg_multiplier)
        return await super()._evolve_faction(faction, generation)

    def _save_run_config(self) -> None:
        """Save PGG-specific run config for resume."""
        run_config = {
            "environment": "pgg",
            "config_path": str(self.config_path),
            "num_generations": self.num_generations,
            "mode": self.mode,
            "pgg_rounds": self.pgg_rounds,
            "pgg_multiplier": self.pgg_multiplier,
            "eval_seeds": self.eval_seeds,
            "info_condition": self.info_condition,
            "generation_timeout": self.generation_timeout,
        }
        (self.output_dir / "run_config.json").write_text(json.dumps(run_config, indent=2))

    def setup(self, resume: bool = False) -> int:
        """Create output directories and validate inputs."""
        # Do all the parent setup work (dirs, checkpoints, resume logic)
        # but suppress parent's banner by calling the essential parts directly
        for d in (self.output_dir, self.blue_dir, self.red_dir, self.checkpoints_dir):
            d.mkdir(parents=True, exist_ok=True)

        if not self.config_path.exists():
            raise FileNotFoundError(f"Config not found: {self.config_path}")
        if not self.evaluator_path.exists():
            raise FileNotFoundError(f"Evaluator not found: {self.evaluator_path}")

        start_gen = 1

        if resume:
            last_gen, status = self._find_last_completed_generation()
            if last_gen > 0:
                start_gen = self._load_checkpoint(last_gen, status)
            else:
                print("  [Resume] No completed generations found — starting fresh")

        import shutil
        if start_gen == 1:
            if not self.current_blue_path.exists():
                raise FileNotFoundError(f"Initial blue constitution not found: {self.current_blue_path}")
            if not self.current_red_path.exists():
                raise FileNotFoundError(f"Initial red constitution not found: {self.current_red_path}")
            gen0_dir = self.checkpoints_dir / "gen_000"
            gen0_dir.mkdir(exist_ok=True)
            shutil.copy2(self.current_blue_path, gen0_dir / "blue_best.py")
            shutil.copy2(self.current_red_path, gen0_dir / "red_best.py")

        self._save_run_config()

        print("=" * 70)
        print("PGG CONSTITUTIONAL CO-EVOLUTION")
        print("=" * 70)
        print(f"  Environment:      Public Goods Game")
        print(f"  Generations:      {self.num_generations}")
        print(f"  Starting from:    generation {start_gen}")
        print(f"  Mode:             {self.mode}")
        print(f"  PGG rounds:       {self.pgg_rounds}")
        print(f"  PGG multiplier:   {self.pgg_multiplier}")
        print(f"  Eval seeds:       {self.eval_seeds}")
        print(f"  Gen timeout:      {self.generation_timeout}s")
        print(f"  Info condition:   {self.info_condition}")
        print(f"  Output dir:       {self.output_dir}")
        print("=" * 70)

        return start_gen

    def _save_evolution_trace(self) -> None:
        """Include PGG-specific config in trace."""
        trace = {
            "config": {
                "environment": "pgg",
                "num_generations": self.num_generations,
                "mode": self.mode,
                "pgg_rounds": self.pgg_rounds,
                "pgg_multiplier": self.pgg_multiplier,
                "eval_seeds": self.eval_seeds,
                "info_condition": self.info_condition,
            },
            "generations": [
                {
                    "generation": r.generation,
                    "blue_S": r.blue_S,
                    "red_S": r.red_S,
                    "blue_rules_count": r.blue_rules_count,
                    "red_rules_count": r.red_rules_count,
                    "timestamp": r.timestamp,
                }
                for r in self.generation_log
            ],
        }
        trace_path = self.output_dir / "evolution_trace.json"
        trace_path.write_text(json.dumps(trace, indent=2))

    def _print_summary(self) -> None:
        """Print PGG-specific summary."""
        print("\n" + "=" * 70)
        print("PGG CO-EVOLUTION COMPLETE")
        print("=" * 70)

        if not self.generation_log:
            print("  No generations completed.")
            return

        first = self.generation_log[0]
        last = self.generation_log[-1]

        print(f"\n  Generations completed: {len(self.generation_log)}")
        print(f"\n  Initial -> Final:")
        print(f"    Blue S: {first.blue_S:.4f} -> {last.blue_S:.4f} (d {last.blue_S - first.blue_S:+.4f})")
        print(f"    Red  S: {first.red_S:.4f} -> {last.red_S:.4f} (d {last.red_S - first.red_S:+.4f})")

        peak_blue = max(self.generation_log, key=lambda r: r.blue_S)
        peak_red = max(self.generation_log, key=lambda r: r.red_S)
        print(f"\n  Peak Blue S: {peak_blue.blue_S:.4f} (gen {peak_blue.generation})")
        print(f"  Peak Red  S: {peak_red.red_S:.4f} (gen {peak_red.generation})")

        print(f"\n  Final constitutions:")
        print(f"    Blue: {last.blue_constitution_path}")
        print(f"    Red:  {last.red_constitution_path}")
        print(f"\n  Evolution trace: {self.output_dir / 'evolution_trace.json'}")
        print("=" * 70)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="PGG Constitutional Co-Evolution Orchestrator"
    )
    parser.add_argument("--generations", type=int, default=30)
    parser.add_argument("--output-dir", type=str, default=None)
    parser.add_argument("--config", type=str, default=None)
    parser.add_argument("--pgg-rounds", type=int, default=20)
    parser.add_argument("--pgg-multiplier", type=float, default=1.5)
    parser.add_argument("--eval-seeds", type=int, default=2)
    parser.add_argument("--info-condition", choices=["full", "own_team", "asymmetric"], default="full")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    try:
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).parent.parent / ".env")
    except ImportError:
        pass

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("ERROR: OPENROUTER_API_KEY not set.")
        sys.exit(1)
    os.environ["OPENAI_API_KEY"] = api_key

    project_root = Path(__file__).parent.parent
    config_path = Path(args.config) if args.config else project_root / "openevolve_pgg_config.yaml"

    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_dir = project_root / "logs" / f"pgg-coevolution-{timestamp}"

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
