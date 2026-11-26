# Constitution-Shiba Experiment Run Logs

This repository contains a snapshot of the experiment logs and run artifacts found in the Constitution-Shiba workspace. It was assembled on 2026-08-17 in the Asia/Kolkata time zone.

## Scope

The repository contains the active experiment log tree and every local backup discovered during inspection. Python bytecode and cache directories were omitted because they are generated artifacts, not experiment records.

| Repository path | Purpose | Files | `.log` files | Approx. size |
| --- | --- | ---: | ---: | ---: |
| `logs/` | Current experiment outputs | 13,904 | 2,684 | 833 MB |
| `results-backup/` | General results backup | 1,018 | 106 | 129 MB |
| `results-backup-20260415-140918-before-rerun/` | Snapshot made before rerun | 985 | 116 | 137 MB |
| `results-backup-20260415-0558/` | Empty snapshot retained with a `.gitkeep` provenance marker | 1 | 0 | negligible |

Total run-artifact inventory: 15,908 files, including 2,906 `.log` files. Uncompressed size is approximately 1.1 GB. Timestamped run names cover 2026-04-14 through 2026-04-19.

## Experiment groups

- `exp1-fragility`: constitutional fragility experiment.
- `exp2-coevolution`: full co-evolution experiment.
- `exp2b-coevolution`: additional or restarted co-evolution run.
- `exp3-awareness`: awareness ablations, including `full`, `own_team`, and `asymmetric` variants.
- `exp4-pgg`: public-goods-game co-evolution experiment.
- `exp5-pure-adversary`: pure-adversary evolution experiment.

Directories and files ending in `.OLD` preserve earlier attempts. The dated `before-rerun` backup preserves state immediately before a rerun.

## File guide

- `exp*.log`: top-level console output for experiment drivers.
- `society.log`: readable society-level events from one simulation.
- `environment.jsonl`: structured environment events, one JSON object per line.
- `residents/<name>.jsonl`: structured resident turns, prompts, actions, and responses.
- `logs/openevolve_*.log`: OpenEvolve execution logs for an individual generation.
- `evolution_trace.json` and `evolution_trace.jsonl`: mutation, evaluation, and score history.
- `run_config.json` and `experiment_config.json`: recorded run settings when available.
- `checkpoints/`, `best/`, and `best_constitution.py`: saved evolutionary state and selected programs.
- `metrics.json` and experiment-specific trace files: summarized scores and outcomes.

## Run-status caveats

These are raw operational artifacts, not a cleaned set containing only successful runs.

- `exp1.log` and `exp5.log` contain explicit experiment-complete markers.
- `exp4.log` reports 30 completed generations and a final evolution-trace path, but also contains earlier tracebacks from retries.
- Current `exp2` and `exp3` driver logs contain tracebacks or stop without a clean completion marker. Their per-generation traces, checkpoints, and evaluation logs remain included and may contain usable completed work.
- Empty, short, duplicate, interrupted, and retried runs are intentionally retained. Do not infer success from file presence alone.

## Quick inspection

Clone repository:

```bash
git clone https://github.com/Arth-Singh/cons-race.git
cd cons-race
```

List all plain-text logs:

```bash
find . -type f -name '*.log' | sort
```

Find failures and completion markers:

```bash
rg -n 'Traceback|ERROR|COMPLETE|Generations completed' \
  logs
```

Read structured JSONL safely without loading a whole file:

```bash
head -n 5 path/to/file.jsonl | jq .
```

## Reproducibility notes

Prefer each run's recorded config, trace, and checkpoint together. A top-level console log alone may combine retries or end before child processes finish. Match generations using directory names and timestamps, then verify final state in trace and checkpoint files.

Experiment outputs are normally ignored by this project's `.gitignore`, but this snapshot force-adds the existing files so they are available from GitHub. Newly generated untracked log files will remain ignored unless explicitly added with `git add -f`.

## Data handling

A high-confidence scan found no common OpenAI or OpenRouter API-key patterns in included `.log`, `.json`, or `.jsonl` files. This is not a full security audit. Logs contain model prompts, responses, resident messages, actions, and research data; review before public distribution.

The workspace `.env` file is deliberately excluded from this repository.
