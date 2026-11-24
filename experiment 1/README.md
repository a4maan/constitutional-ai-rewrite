# Experiment 1 — fixed Blue, evolving Red

Implements the November 19–21 design discussion with Prof. Tan. Blue's
constitution is frozen. Red begins with neutral rules and receives candidate
natural-language mutations. Each generation compares the parent and candidates
against the same Blue on the same selection seeds. The candidate with highest
mean negative Blue score replaces the parent. Ties preserve the parent.

Blue utility is explicitly defined as the existing capped PGG raw score S_Blue.
Optimization scores are F_Blue = S_Blue and F_Red = -S_Blue. Raw game mechanics
and the original scoring formula are retained. Every generation separately
compares frozen Blue against R_t and R_(t+1) over matched held-out seeds.
Held-out outcomes do not determine selection.

## Run from the repository root

```bash
python "experiment 1/run.py" --config "experiment 1/pilot.example.json" --output output/experiment-1-smoke --mock
python "experiment 1/run.py" --replay output/experiment-1-smoke
python -m unittest discover -s "experiment 1/tests" -v
```

The mock mode uses synthetic actions and mutations solely to validate execution
and artifacts. Its output must be labeled mock and excluded from research results.

For a model-backed run, copy the example configuration, select the actual PGG
Blue C*, set OPENROUTER_API_KEY in the execution environment, and omit --mock.
The example Blue is the paper's cooperative starting seed, not a recovered
optimized C*. Its name explicitly records this provenance. Model requests incur
API charges. The maximum number of requests is configurable. The example uses
two generations, two challengers per generation, two selection seeds, and four
held-out seeds, as a small pilot rather than an agreed final research budget.
Expected successful example requests are 3,364: 28 games × 120 agent decisions
plus 4 mutations. Tokens and actual cost depend on outputs and growing histories.

The mutation operator receives parent performance, game configuration, and the
adversarial objective. It sees the Blue constitution only if mutation_sees_blue
is true. Resident controllers receive their own constitution, current wallets,
and completed public history. Default agent names contain faction prefixes as
in the existing PGG, so hiding the faction field does not guarantee hidden team
identity. The example neutral rules have no adversarial instruction; the
evolutionary objective is supplied to the mutation operator.

## Measurements

Each completed evaluation records both factions' raw scores, capped and uncapped
contribution utilization, absolute free-riding rate, total contributions, final
wallets, net material payoff relative to initial endowment, contribution fraction
on positive-wallet rounds, zero-wallet rounds, pool returns, punishment costs,
punishment damage, action counts, and score saturation. Summary records include
paired held-out Red improvement and mean optimization scores with standard error
where at least two seeds are available. These seed-level errors do not replace
independent repetitions of evolution.

## Reproducibility and failures

Output directories must be new, to preserve previous runs. Configurations,
constitutions, source copies and hashes, runtime version, model requests and raw
responses, returned explanations, usage metadata returned by OpenRouter, seed
lists, selections, and episode checkpoints are saved. Authentication headers and
API keys are excluded. Explanations are model-returned text.

Invalid mutations or failed candidate evaluations are logged as invalid and
excluded from selection. A failed parent evaluation stops the experiment.
Failed held-out comparisons have no numerical improvement value. Errors never
become successful zero scores. There are no automatic retries or silent action
substitutions. An exhausted model-call budget stops subsequent requests and may
leave the experiment with invalid evaluations, which are visible in the summary.

Replay verifies saved episode observations, settlements, scores, and final states
without models. The source and config hashes are checked. The event journal
preserves mutation inputs/outputs and selection decisions for inspection.
The current replay command does not reissue model requests, resume interrupted
searches, or statistically validate an arms-race claim. Archive the entire output
directory for each independent experiment.

The optimizer is a transparent parent-plus-challengers selection loop. OpenEvolve
and MAP-Elites are not dependencies. This implements the fixed-Blue pilot, while
exact reproduction of the paper's search algorithm would require that integration.
