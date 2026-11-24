# Prepare an optimized Blue baseline

`prepare_blue.py` runs cooperative constitutional search before Experiment 1.
It holds neutral Red fixed and proposes Blue mutations using the existing model
adapter. Candidates replace Blue only when they improve mean S_Blue on selection
seeds. Within a generation, each challenger is proposed from the current retained
parent. The initial and selected Blue are evaluated on separate held-out seeds
after selection finishes. Those seeds are also distinct from Experiment 1's seeds.

The example budget is two generations with two challengers per generation, two
selection seeds, and three held-out seeds. It evaluates 16 full 20-round games
and proposes four mutations, requiring up to 1,924 successful requests before
response reuse. This is a small preparation budget chosen for the pilot.

From the repository root:

```bash
python -m pip install -r "experiment 1/requirements.txt"
python "experiment 1/prepare_blue.py" --config "experiment 1/prepare-blue.example.json" --output output/blue-validation --mock
```

For real optimization, configure GROQ_API_KEY or GROQ_KEYS_FILE and omit --mock.
The supplied Groq rate limits are conservatively set below the published free
limits. When using GROQ_KEYS_FILE, it must contain a JSON list of keys from
independent organizations. Keys from one organization share a quota. Run a single
process per organization so the local ledgers accurately cover its requests.

The new output directory contains the source snapshot, configuration, model
request/response journal, selection history, full replayable game logs,
`selected-blue.json`, and summary. A successful model-backed run also exports
`adversarial-config.json` with Blue replaced by the selected rules and provenance.
Mock runs do not export a configuration for research use.

The resulting constitution is the best found within this budget against the
specified neutral opponent. It can be frozen as the optimized Blue baseline for
Experiment 1. Finite search does not establish global optimality. If all candidates
fail to improve, the initial cooperative seed is retained, which is visible in
the selection history. Held-out behavior and saturation must be inspected before
describing it as a strong cooperative baseline.

All model calls and optimization remain separate from synthetic validation.
The preparation command currently requires a new output directory. The underlying
Groq client persists successful responses and quota state, but this preparation
entry point does not yet resume interrupted searches. The adversarial runner has
an explicit --resume option.
