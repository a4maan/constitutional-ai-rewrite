# Experiment 1 — fixed Blue, evolving Red

**November 25 repair:** the active pilot uses the original game engine with a
neutral resident prompt for both factions. The selected constitution supplies
Blue's behavioral rules; neutral starting rules supply Red's initial behavior.
The mutation model alone receives the adversarial objective. These are explicit
changes to the earlier original-role-prompt condition; results must not be pooled.
The scoring equation remains unchanged.

When factions are hidden, resident names are neutral and faction assignments are
shuffled reproducibly per seed. Team fields are removed from model inputs.
Authoritative private game logs retain faction assignments for scoring and replay.
Messages and inferred behavioral identities can still reveal information during play.
The original engine remains wallet-limited, with no hard 100-unit contribution
cap. Actor and mutation instructions now describe this consistently.

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

For an OpenRouter run, use `pilot.openrouter.json`, set OPENROUTER_API_KEY
in the execution environment, and omit --mock. All pilot example configurations use
the selected best recorded historical Blue constitution: generation 22, whose
rules are identical to generations 7–28 in the recovered runs. Its highest
recorded Blue score was 0.7983. The historical Red opponents varied, so that
score is not a matched comparison against a common neutral Red. Model requests
incur API charges. The maximum number of requests is configurable. The example uses
two generations, two challengers per generation, two selection seeds, and four
held-out seeds, as a small pilot rather than an agreed final research budget.
Without response reuse, the example requires 3,364 logical completions:
28 games × 120 agent decisions plus 4 mutations. Caching can reduce requests,
while validation and network retries can increase them. Tokens and actual cost
depend on outputs and growing histories.

The mutation operator receives parent selection performance, game configuration,
and the adversarial objective. It sees the Blue constitution only when
mutation_sees_blue is true. Held-out results never enter mutation inputs or selection.
The actor and mutation instructions include contributions, punishment, broadcasts,
private messages, and rest. The active neutral resident prompt adds no wealth,
cooperation, or exploitation objective beyond the supplied constitution.
The original role prompts remain available as an explicitly different condition.


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
excluded from selection. Any such failure produces `complete_with_failures`,
`research_valid: false`, and a nonzero command exit. A failed parent evaluation
stops the experiment.
Failed held-out comparisons stop the experiment with a failed status. Errors never
become successful zero scores. OpenRouter retries truncated responses with a larger output allowance and
retries transient transport/server failures, up to four attempts per API completion;
every attempt counts toward the call budget and is logged. The OpenRouter
configuration selects low reasoning effort and an initial 4,096-token output
allowance. Exhausted retries invalidate an evaluation rather than create an action.
An exhausted model-call budget stops subsequent requests and may
leave the experiment with invalid evaluations, which are visible in the summary.

Replay verifies saved episode observations, settlements, scores, and final states
without models. The source and config hashes are checked. The event journal
preserves mutation inputs/outputs and selection decisions for inspection.
The replay command does not reissue model requests or statistically validate
an arms-race claim. `--resume` requires identical source and configuration and
reuses completed episodes and cached OpenRouter responses. Call and reported
cost budgets survive resume. Interrupted partial episodes are reconstructed
from their beginning using cached responses, not accepted as completed games. Archive the entire output
directory for each independent experiment.

The optimizer is a transparent parent-plus-challengers selection loop. OpenEvolve
and MAP-Elites are not dependencies. This implements the fixed-Blue pilot, while
exact reproduction of the paper's search algorithm would require that integration.

## Response validation and interpretation

OpenRouter requests a strict JSON schema for action decisions and a separate
constitution schema for mutations, and requires a provider that supports the
requested parameters. Local validation remains mandatory because provider
compliance can vary. See [OpenRouter structured outputs](https://openrouter.ai/docs/guides/features/structured-outputs).

The decoder accepts a plain response object or unwraps an unambiguous `final`
object/string, recording every unwrap. Invalid structures, unknown action fields,
nonfinite/negative amounts, invalid targets, and duplicate action categories are
rejected. Up to three validation attempts are logged; exhausted retries fail the
evaluation. Format failures never become synthetic rest actions. An explicitly
chosen rest or empty action list remains a legitimate zero-contribution turn.

The OpenRouter client retries transient transport/server failures and truncated
or invalid JSON responses, logs raw responses, and caches decoded responses by
request hash. A retry can incur additional API charges. The local cost guard uses
reported API costs and can overshoot by one request; the API key's spending limit
is the external cap. Configured pilot limit: $3.75, beneath the key's $4 cap.
Remote account balance or provider availability can still stop execution safely.

Interpret S_Blue as a capped contribution composite. Each episode also reports
wealth, material payoff, contribution fractions, zero-wallet rounds, uncapped
utilization, punishment, and saturation; held-out records retain paired Blue
diagnostics. Reduced S_Blue does not by itself distinguish unwillingness from
depletion. Two generations and a few seeds form an exploratory pilot. Independent
search repetitions and transfer tests against other fixed Blue constitutions
are required before claiming general or constitution-specific adversarial effects.
The fixed-Blue experiment cannot establish reciprocal coevolution by itself.

The repaired EC2 launcher first runs a separate three-round live engineering
preflight on disjoint seeds and replays it. It launches the full 20-round pilot
only if that check passes without failed evaluations. Engineering preflight data
and the two stopped earlier attempts are excluded from the main results.

Seeds control roster assignment and model request seeds. Remote model inference
is not guaranteed bitwise deterministic. Exact replay uses the recorded actions
and responses; cached repeated identical requests avoid re-sampling unchanged
policies on the same observation. API-provided model/provider metadata is retained
in each raw response.
