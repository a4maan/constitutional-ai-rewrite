# Experiment 1 PGG archive

This folder consolidates the fixed-Blue, evolving-Red PGG experiment. It includes the runner, model adapters, Blue preparation tools, tests, PGG source, configurations, documentation, scoring validation, static no-LLM results, and the completed EC2 pilot summary.

The completed pilot used the selected Blue constitution, neutral resident prompts, anonymous resident names, two Red-search generations, two candidates per generation, two selection seeds, and four held-out seeds. It completed 28/28 game traces with `research_valid: true`. The complete trace archive has been copied locally to `results/remote-pilot/pilot`.

## Local contents

- `code/` contains the experiment runner and supporting scripts.
- `tests/` contains the experiment tests.
- `source/pgg/` contains the PGG implementation used by the runner.
- `configs/` contains pilot and preparation configurations.
- `docs/` contains the experiment specification, scoring validation, and handoff.
- `results/` contains the static no-LLM results, compact EC2 pilot results, and the complete copied pilot archive under `remote-pilot/pilot/`.
- `archive-manifest.json` records the remote trace location, hashes, sizes, and copied artifacts.

The copied pilot trace directory is `results/remote-pilot/pilot/`. It contains 2,271 files totaling 70,549,656 bytes, including all 28 replayable traces, the event journal, source snapshot, raw model responses, checkpoints, and selection records. The original source was `/home/ec2-user/experiment-1-v4-20261125/output/pilot` on EC2 instance `i-0048e12021a977608` in `us-east-2`.
