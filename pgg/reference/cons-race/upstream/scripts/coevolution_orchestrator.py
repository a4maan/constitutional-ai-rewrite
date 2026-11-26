"""
Adversarial Constitutional Co-Evolution Orchestrator.

Core contribution: manages two OpenEvolve instances that evolve blue and red
team constitutions against each other.  Each generation:

  1. Evolve C_blue for one iteration (evaluated against current C_red)
  2. Evolve C_red  for one iteration (evaluated against current C_blue)
  3. Record per-faction stability scores
  4. Checkpoint constitutions and metrics

Supports two pacing modes:
  - alternating (default): blue evolves, then red evolves
  - simultaneous: both evolve against the PREVIOUS generation's opponent

Resilience features:
  - Automatic checkpoint after every generation
  - --resume flag to pick up from the last completed generation
  - Per-generation timeout with graceful fallback
  - caffeinate integration on macOS to prevent sleep during runs

Usage:
    python scripts/coevolution_orchestrator.py \\
        --generations 30 \\
        --mode alternating \\
        --output-dir logs/coevolution-run1

    # Resume an interrupted run:
    python scripts/coevolution_orchestrator.py \\
        --resume --output-dir logs/coevolution-run1
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from openevolve import OpenEvolve


@dataclass
class GenerationRecord:
    """Metrics recorded after each co-evolution generation."""

    generation: int
    blue_S: float
    red_S: float
    blue_rules_count: int
    red_rules_count: int
    blue_constitution_path: str
    red_constitution_path: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


# ---------------------------------------------------------------------------
# System sleep prevention
# ---------------------------------------------------------------------------

class SleepInhibitor:
    """Prevents the system from sleeping during long-running evolution jobs.

    On macOS uses caffeinate; on Linux uses systemd-inhibit if available.
    Falls back to a no-op if neither is available.
    """

    def __init__(self) -> None:
        self._process: subprocess.Popen | None = None

    def acquire(self) -> None:
        system = platform.system()
        try:
            if system == "Darwin":
                # -i  = prevent idle sleep
                # -s  = prevent system sleep (on AC power)
                # -d  = prevent display sleep
                self._process = subprocess.Popen(
                    ["caffeinate", "-i", "-s", "-d"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                print("  [SleepInhibitor] macOS caffeinate acquired — system will stay awake")
            elif system == "Linux":
                # systemd-inhibit blocks idle sleep for the lifetime of the child
                self._process = subprocess.Popen(
                    ["systemd-inhibit", "--what=idle", "--who=coevolution",
                     "--why=Running co-evolution experiment", "sleep", "infinity"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                print("  [SleepInhibitor] Linux systemd-inhibit acquired")
            else:
                print(f"  [SleepInhibitor] No sleep inhibitor available for {system}")
        except FileNotFoundError:
            print("  [SleepInhibitor] Sleep inhibitor command not found — continuing without it")

    def release(self) -> None:
        if self._process is not None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
            self._process = None
            print("  [SleepInhibitor] Released — system may sleep again")

    def __enter__(self) -> "SleepInhibitor":
        self.acquire()
        return self

    def __exit__(self, *_: object) -> None:
        self.release()


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class CoEvolutionOrchestrator:
    """Orchestrates adversarial constitutional co-evolution."""

    def __init__(
        self,
        *,
        config_path: str | Path,
        output_dir: str | Path,
        num_generations: int = 30,
        mode: str = "alternating",
        eval_turns: int = 40,
        eval_seeds: int = 2,
        overseer_enabled: bool = False,
        info_condition: str = "full",
        generation_timeout: int = 100000,
    ) -> None:
        self.config_path = Path(config_path)
        self.output_dir = Path(output_dir)
        self.num_generations = num_generations
        self.mode = mode
        self.eval_turns = eval_turns
        self.eval_seeds = eval_seeds
        self.overseer_enabled = overseer_enabled
        self.info_condition = info_condition
        self.generation_timeout = generation_timeout
        self.generation_log: list[GenerationRecord] = []

        # Paths
        self.blue_dir = self.output_dir / "blue"
        self.red_dir = self.output_dir / "red"
        self.checkpoints_dir = self.output_dir / "checkpoints"
        self.evolution_dir = Path(__file__).parent / "evolution"
        self.evaluator_path = self.evolution_dir / "adversarial_evaluator.py"

        # Current best constitutions (start from initial templates)
        self.current_blue_path = self.evolution_dir / "initial_blue_constitution.py"
        self.current_red_path = self.evolution_dir / "initial_red_constitution.py"

        self._sleep_inhibitor = SleepInhibitor()
        self._resume_red_only: int | None = None  # set when resuming a partial gen
        self._shutdown_requested = False

    # ------------------------------------------------------------------ #
    # Checkpoint / Resume
    # ------------------------------------------------------------------ #

    def _save_run_config(self) -> None:
        """Persist run configuration so --resume can reconstruct the orchestrator."""
        run_config = {
            "config_path": str(self.config_path),
            "num_generations": self.num_generations,
            "mode": self.mode,
            "eval_turns": self.eval_turns,
            "eval_seeds": self.eval_seeds,
            "overseer_enabled": self.overseer_enabled,
            "info_condition": self.info_condition,
            "generation_timeout": self.generation_timeout,
        }
        (self.output_dir / "run_config.json").write_text(json.dumps(run_config, indent=2))

    def _find_last_completed_generation(self) -> tuple[int, str]:
        """Scan checkpoints to find the highest completed generation.

        Returns (generation_number, status) where status is one of:
          "complete"      — both sides finished, metrics written
          "blue_only"     — blue finished mid-generation, red did not
          "none"          — no completed generations found
        """
        if not self.checkpoints_dir.exists():
            return 0, "none"

        max_complete = 0
        partial_gen = 0

        for gen_dir in self.checkpoints_dir.iterdir():
            if not gen_dir.is_dir() or not gen_dir.name.startswith("gen_"):
                continue
            try:
                gen_num = int(gen_dir.name.split("_")[1])
            except (IndexError, ValueError):
                continue

            has_blue = (gen_dir / "blue_best.py").exists()
            has_red = (gen_dir / "red_best.py").exists()
            has_metrics = (gen_dir / "metrics.json").exists()

            if has_blue and has_red and (gen_num == 0 or has_metrics):
                max_complete = max(max_complete, gen_num)
            elif has_blue and not has_metrics and gen_num > 0:
                # Blue finished but red didn't — partial checkpoint
                partial_gen = max(partial_gen, gen_num)

        if partial_gen > max_complete:
            return partial_gen, "blue_only"
        if max_complete > 0:
            return max_complete, "complete"
        return 0, "none"

    def _load_checkpoint(self, generation: int, status: str) -> int:
        """Restore state from a checkpoint.

        Returns the generation to start from.
        """
        # Reload generation log from completed generations
        self.generation_log = []
        for g in range(1, generation + 1):
            metrics_path = self.checkpoints_dir / f"gen_{g:03d}" / "metrics.json"
            if metrics_path.exists():
                m = json.loads(metrics_path.read_text())
                self.generation_log.append(GenerationRecord(
                    generation=m["generation"],
                    blue_S=m["blue_S"],
                    red_S=m["red_S"],
                    blue_rules_count=m.get("blue_rules", 0),
                    red_rules_count=m.get("red_rules", 0),
                    blue_constitution_path=str(self.checkpoints_dir / f"gen_{g:03d}" / "blue_best.py"),
                    red_constitution_path=str(self.checkpoints_dir / f"gen_{g:03d}" / "red_best.py"),
                    timestamp=m.get("timestamp", ""),
                ))

        if status == "blue_only":
            # Blue finished this generation but red didn't — load blue's result
            # and set red to the previous generation's best so we only re-run red
            gen_dir = self.checkpoints_dir / f"gen_{generation:03d}"
            self.current_blue_path = gen_dir / "blue_best.py"
            prev_gen = generation - 1
            prev_dir = self.checkpoints_dir / f"gen_{prev_gen:03d}"
            self.current_red_path = prev_dir / "red_best.py"
            self._resume_red_only = generation  # signal to run_generation
            print(f"  [Resume] Partial checkpoint at generation {generation} (blue done, red pending)")
            print(f"    Blue constitution: {self.current_blue_path}")
            print(f"    Red constitution:  {self.current_red_path} (from gen {prev_gen})")
            return generation  # restart this generation, but skip blue
        else:
            gen_dir = self.checkpoints_dir / f"gen_{generation:03d}"
            self.current_blue_path = gen_dir / "blue_best.py"
            self.current_red_path = gen_dir / "red_best.py"
            print(f"  [Resume] Loaded checkpoint at generation {generation}")
            print(f"    Blue constitution: {self.current_blue_path}")
            print(f"    Red constitution:  {self.current_red_path}")
            if self.generation_log:
                last = self.generation_log[-1]
                print(f"    Last scores — Blue: {last.blue_S:.4f}, Red: {last.red_S:.4f}")
            return generation + 1

    # ------------------------------------------------------------------ #
    # Setup
    # ------------------------------------------------------------------ #

    def setup(self, resume: bool = False) -> int:
        """Create output directories and validate inputs.

        Returns the generation to start from (1 for fresh, N+1 for resume).
        """
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

        if start_gen == 1:
            # Validate initial constitutions exist
            if not self.current_blue_path.exists():
                raise FileNotFoundError(f"Initial blue constitution not found: {self.current_blue_path}")
            if not self.current_red_path.exists():
                raise FileNotFoundError(f"Initial red constitution not found: {self.current_red_path}")

            # Copy initial constitutions to checkpoint gen_0
            gen0_dir = self.checkpoints_dir / "gen_000"
            gen0_dir.mkdir(exist_ok=True)
            shutil.copy2(self.current_blue_path, gen0_dir / "blue_best.py")
            shutil.copy2(self.current_red_path, gen0_dir / "red_best.py")

        self._save_run_config()

        print("=" * 70)
        print("ADVERSARIAL CONSTITUTIONAL CO-EVOLUTION")
        print("=" * 70)
        print(f"  Generations:      {self.num_generations}")
        print(f"  Starting from:    generation {start_gen}")
        print(f"  Mode:             {self.mode}")
        print(f"  Eval turns:       {self.eval_turns}")
        print(f"  Eval seeds:       {self.eval_seeds}")
        print(f"  Gen timeout:      {self.generation_timeout}s")
        print(f"  Overseer:         {'enabled' if self.overseer_enabled else 'disabled'}")
        print(f"  Info condition:   {self.info_condition}")
        print(f"  Output dir:       {self.output_dir}")
        print("=" * 70)

        return start_gen

    # ------------------------------------------------------------------ #
    # Evolution
    # ------------------------------------------------------------------ #

    async def _evolve_faction(
        self,
        faction: str,
        generation: int,
    ) -> tuple[float, int, str]:
        """Run one OpenEvolve iteration for a single faction.

        Returns (faction_score, num_rules, best_constitution_path).
        """
        opponent_path = self.current_red_path if faction == "blue" else self.current_blue_path
        initial_path = self.current_blue_path if faction == "blue" else self.current_red_path
        faction_output = (self.blue_dir if faction == "blue" else self.red_dir) / f"gen_{generation:03d}"

        # Set environment variables for the evaluator
        os.environ["EVOLVING_FACTION"] = faction
        os.environ["OPPONENT_CONSTITUTION_PATH"] = str(opponent_path)
        os.environ["INFO_CONDITION"] = self.info_condition
        os.environ["EVAL_TURNS"] = str(self.eval_turns)
        os.environ["EVAL_SEEDS"] = str(self.eval_seeds)
        os.environ["OVERSEER_ENABLED"] = "1" if self.overseer_enabled else "0"

        # Pick faction-specific config if available (e.g. openevolve_adversarial_red_config.yaml).
        # Convention: replace "_config.yaml" with f"_{faction}_config.yaml" and check existence.
        active_config_path = self.config_path
        cfg_name = self.config_path.name
        if cfg_name.endswith("_config.yaml"):
            faction_cfg_name = cfg_name.replace("_config.yaml", f"_{faction}_config.yaml")
            faction_cfg_path = self.config_path.parent / faction_cfg_name
            if faction_cfg_path.exists():
                active_config_path = faction_cfg_path

        # Initialize OpenEvolve for this faction
        evolve = OpenEvolve(
            initial_program_path=str(initial_path),
            evaluation_file=str(self.evaluator_path),
            config_path=str(active_config_path),
            output_dir=str(faction_output),
        )
        evolve.config.max_iterations = 1

        print(f"\n  [{faction.upper()}] Evolving generation {generation}...")
        print(f"    Initial:  {initial_path.name}")
        print(f"    Opponent: {opponent_path.name}")
        print(f"    Config:   {active_config_path.name}")

        try:
            best_program = await evolve.run()
        except Exception as e:
            print(f"    [{faction.upper()}] ERROR during evolution: {e}")
            print(f"    [{faction.upper()}] Falling back to previous best constitution")
            return 0.0, 0, str(initial_path)

        if best_program is None:
            print(f"    [{faction.upper()}] WARNING: OpenEvolve returned None — using previous best")
            return 0.0, 0, str(initial_path)

        # Extract results
        score = best_program.metrics.get("combined_score", 0.0)
        code = best_program.code

        # Save best constitution
        best_path = faction_output / "best_constitution.py"
        best_path.parent.mkdir(parents=True, exist_ok=True)
        best_path.write_text(code)

        # Count rules (rough heuristic)
        num_rules = code.count("ConstitutionRule(")

        # Validate the constitution loads before treating it as the next seed.
        # LLM mutation sometimes produces code with syntax errors; if that
        # broken code becomes the seed for the next generation, every mutation
        # of it also breaks and the search poisons itself with 0-score clones.
        import ast, importlib.util as _iu
        try:
            ast.parse(code)
            _spec = _iu.spec_from_file_location(f"{faction}_g{generation}_test", str(best_path))
            _mod = _iu.module_from_spec(_spec)
            _spec.loader.exec_module(_mod)
            if not hasattr(_mod, "get_rules_as_dicts"):
                raise AttributeError("missing get_rules_as_dicts")
            _ = _mod.get_rules_as_dicts()
            is_valid = True
        except Exception as e:
            is_valid = False
            print(f"    [{faction.upper()}] WARNING: best constitution failed validation "
                  f"({type(e).__name__}: {e}); reusing previous {initial_path.name}")

        print(f"    [{faction.upper()}] Score: {score:.4f}, Rules: {num_rules}, Valid: {is_valid}")

        if not is_valid:
            # Keep the previous working constitution as the next seed
            return score, num_rules, str(initial_path)
        return score, num_rules, str(best_path)

    async def run_generation(self, generation: int) -> GenerationRecord:
        """Run one full generation of co-evolution with mid-generation checkpointing."""
        print(f"\n{'─' * 70}")
        print(f"GENERATION {generation}/{self.num_generations}")
        print(f"{'─' * 70}")

        gen_dir = self.checkpoints_dir / f"gen_{generation:03d}"
        gen_dir.mkdir(exist_ok=True)

        if self.mode == "alternating":
            # Check if resuming a partial generation (blue done, red pending)
            if self._resume_red_only == generation:
                print(f"  [Resume] Skipping blue (already done), running red only")
                blue_path = str(self.current_blue_path)
                blue_score = 0.0
                blue_rules = 0
                # Try to read blue's score from a partial metrics file
                partial_metrics = gen_dir / "partial_blue.json"
                if partial_metrics.exists():
                    pm = json.loads(partial_metrics.read_text())
                    blue_score = pm.get("blue_S", 0.0)
                    blue_rules = pm.get("blue_rules", 0)
                self._resume_red_only = None
            else:
                blue_score, blue_rules, blue_path = await self._evolve_faction("blue", generation)
                self.current_blue_path = Path(blue_path)

                # Immediately checkpoint blue so it's not lost if red crashes
                _blue_ckpt = gen_dir / "blue_best.py"
                if self.current_blue_path.resolve() != _blue_ckpt.resolve():
                    shutil.copy2(self.current_blue_path, _blue_ckpt)
                (gen_dir / "partial_blue.json").write_text(json.dumps({
                    "blue_S": blue_score, "blue_rules": blue_rules,
                }))
                print(f"    [Checkpoint] Blue gen {generation} saved")

            red_score, red_rules, red_path = await self._evolve_faction("red", generation)
            self.current_red_path = Path(red_path)

        elif self.mode == "simultaneous":
            blue_task = self._evolve_faction("blue", generation)
            red_task = self._evolve_faction("red", generation)
            (blue_score, blue_rules, blue_path), (red_score, red_rules, red_path) = (
                await asyncio.gather(blue_task, red_task)
            )
            self.current_blue_path = Path(blue_path)
            self.current_red_path = Path(red_path)
        else:
            raise ValueError(f"Unknown mode: {self.mode}")

        # Checkpoint
        gen_dir = self.checkpoints_dir / f"gen_{generation:03d}"
        gen_dir.mkdir(exist_ok=True)
        blue_dest = gen_dir / "blue_best.py"
        red_dest = gen_dir / "red_best.py"
        if self.current_blue_path.resolve() != blue_dest.resolve():
            shutil.copy2(self.current_blue_path, blue_dest)
        if self.current_red_path.resolve() != red_dest.resolve():
            shutil.copy2(self.current_red_path, red_dest)

        record = GenerationRecord(
            generation=generation,
            blue_S=blue_score,
            red_S=red_score,
            blue_rules_count=blue_rules,
            red_rules_count=red_rules,
            blue_constitution_path=blue_path,
            red_constitution_path=red_path,
        )
        self.generation_log.append(record)

        # Save metrics
        metrics = {
            "generation": generation,
            "blue_S": blue_score,
            "red_S": red_score,
            "blue_rules": blue_rules,
            "red_rules": red_rules,
            "score_gap": blue_score - red_score,
            "timestamp": record.timestamp,
        }
        (gen_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))

        print(f"\n  GENERATION {generation} SUMMARY:")
        print(f"    Blue S: {blue_score:.4f}  |  Red S: {red_score:.4f}  |  Gap: {blue_score - red_score:+.4f}")

        return record

    async def run(self, resume: bool = False) -> list[GenerationRecord]:
        """Run the full co-evolution loop."""
        import signal

        start_gen = self.setup(resume=resume)

        if start_gen > self.num_generations:
            print(f"\n  All {self.num_generations} generations already completed!")
            self._print_summary()
            return self.generation_log

        # Graceful shutdown on SIGTERM/SIGINT — finish current gen, then stop
        def _handle_signal(signum: int, frame: object) -> None:
            sig_name = signal.Signals(signum).name
            print(f"\n  [SIGNAL] {sig_name} received — will stop after current generation")
            print(f"  (checkpoints are saved, use --resume to continue)")
            self._shutdown_requested = True

        old_sigterm = signal.signal(signal.SIGTERM, _handle_signal)
        old_sigint = signal.signal(signal.SIGINT, _handle_signal)

        try:
            # Prevent system sleep for the duration of the run
            with self._sleep_inhibitor:
                for gen in range(start_gen, self.num_generations + 1):
                    if self._shutdown_requested:
                        print(f"\n  [Shutdown] Stopping at generation {gen - 1}")
                        break
                    await self.run_generation(gen)
                    self._save_evolution_trace()
        finally:
            signal.signal(signal.SIGTERM, old_sigterm)
            signal.signal(signal.SIGINT, old_sigint)

        self._print_summary()
        return self.generation_log

    def _save_evolution_trace(self) -> None:
        """Save the full evolution trace to disk."""
        trace = {
            "config": {
                "num_generations": self.num_generations,
                "mode": self.mode,
                "eval_turns": self.eval_turns,
                "eval_seeds": self.eval_seeds,
                "overseer_enabled": self.overseer_enabled,
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
        """Print final co-evolution summary."""
        print("\n" + "=" * 70)
        print("CO-EVOLUTION COMPLETE")
        print("=" * 70)

        if not self.generation_log:
            print("  No generations completed.")
            return

        first = self.generation_log[0]
        last = self.generation_log[-1]

        print(f"\n  Generations completed: {len(self.generation_log)}")
        print(f"\n  Initial → Final:")
        print(f"    Blue S: {first.blue_S:.4f} → {last.blue_S:.4f} (Δ {last.blue_S - first.blue_S:+.4f})")
        print(f"    Red  S: {first.red_S:.4f} → {last.red_S:.4f} (Δ {last.red_S - first.red_S:+.4f})")

        # Find peak scores
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
        description="Adversarial Constitutional Co-Evolution Orchestrator"
    )
    parser.add_argument(
        "--generations", type=int, default=30,
        help="Number of co-evolution generations (default: 30)",
    )
    parser.add_argument(
        "--mode", choices=["alternating", "simultaneous"], default="alternating",
        help="Evolution pacing mode (default: alternating)",
    )
    parser.add_argument(
        "--output-dir", type=str, default=None,
        help="Output directory (default: logs/coevolution-<timestamp>)",
    )
    parser.add_argument(
        "--config", type=str, default=None,
        help="OpenEvolve config path (default: openevolve_adversarial_config.yaml)",
    )
    parser.add_argument(
        "--eval-turns", type=int, default=40,
        help="Turns per evaluation simulation (default: 40)",
    )
    parser.add_argument(
        "--eval-seeds", type=int, default=2,
        help="Number of seeds to average per evaluation (default: 2)",
    )
    parser.add_argument(
        "--overseer", action="store_true",
        help="Enable the Overseer elimination mechanic",
    )
    parser.add_argument(
        "--info-condition", choices=["full", "own_team", "asymmetric"], default="full",
        help="Information condition for Experiment 3 ablation (default: full)",
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="Resume from the last completed generation checkpoint",
    )
    parser.add_argument(
        "--gen-timeout", type=int, default=100000,
        help="Timeout per faction evolution in seconds (default: 100000 — effectively no limit)",
    )
    args = parser.parse_args()

    # Load .env if available
    try:
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).parent.parent / ".env")
    except ImportError:
        pass

    # Validate API key
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("ERROR: OPENROUTER_API_KEY not set.")
        sys.exit(1)
    os.environ["OPENAI_API_KEY"] = api_key

    # Paths
    project_root = Path(__file__).parent.parent
    config_path = Path(args.config) if args.config else project_root / "openevolve_adversarial_config.yaml"

    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_dir = project_root / "logs" / f"coevolution-{timestamp}"

    orchestrator = CoEvolutionOrchestrator(
        config_path=config_path,
        output_dir=output_dir,
        num_generations=args.generations,
        mode=args.mode,
        eval_turns=args.eval_turns,
        eval_seeds=args.eval_seeds,
        overseer_enabled=args.overseer,
        info_condition=args.info_condition,
        generation_timeout=args.gen_timeout,
    )

    asyncio.run(orchestrator.run(resume=args.resume))


if __name__ == "__main__":
    main()
