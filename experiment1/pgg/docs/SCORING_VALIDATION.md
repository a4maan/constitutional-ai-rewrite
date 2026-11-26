# LLM-free PGG scoring validation — November 25, 2026

**Outcome:** the existing score measures a capped, contribution-based composite.
It does not independently measure willingness to cooperate or material wealth.
Its implementation passed the diagnostic checks; its interpretation needs care.
No scoring equation or active experiment configuration was changed.

## What ran

84 distinct deterministic 20-round games (1,680 rounds), all replay-verified:
seven fixed Blue policies × six fixed Red policies × two contribution-request modes.
No LLM calls or AWS operations were made.

- Blue policies: full wallet, 60%, 10%, conditional cooperation, punishment-heavy,
  message-only, and fixed 10 units.
- Red policies: full wallet, zero, punish Blue, message-only, full wallet plus
  broadcast, and 10% wallet.
- Primary amount mode: original engine's wallet-limited contributions.
- Sensitivity mode: cap policy contribution requests at the advertised 100 units,
  without changing the engine. Punishment requests use severity at most 50.

All agents start with 100. Growth and depletion arise from play. Policies use the
original rounded own-wallet observation. Conditional Blue contributes 60% unless
the previous pool per resident was below 30, when it contributes 10%.
Punishment-heavy Blue punishes its matched Red with severity15 if that Red's last
contribution was below10; otherwise it contributes60%. Attacking Red requests
severity50 against its matched Blue every round, skipped if unaffordable.

These are programmed controls, not implementations of recovered natural-language
constitutions. Fixed policies do not interpret messages. Consequently, this cannot
test the behavioral effects of persuasion, actual constitutions, or LLM evolution.

## Concrete outcomes

Original runtime amount mode; wealth is the **total for all three Blue agents**.

| Blue policy | Red policy | Blue score | Final Blue wealth | Mean contribution fraction of positive starting wallets |
|---|---|---:|---:|---:|
| Full wallet | Full wallet | 0.800000 | 997,575.414 | ~100% |
| 60% wallet | Full wallet | 0.800000 | 233,477.710 | ~60% |
| Full wallet | Zero | 0.289681 | 0.958 | ~99.90% |
| 10% wallet | Zero | 0.149731 | 180.808 | ~10% |
| Full wallet | Punish Blue | 0.151250 | 0 | 100% |
| Punishment-heavy | Zero | 0.125000 | 12 | 3% |
| Punishment-heavy | Punish Blue | 0.125000 | 0 | 30% |

### 1. Depletion can look like reduced cooperation

Full-wallet Blue facing zero-contribution Red continues giving essentially all
its available wallet but receives only 0.289681. The fixed initial-endowment
denominator and absolute low-contribution threshold penalize its shrinking
resources. A low score can mean inability to fund the pool, not unwillingness.
Zero-wallet rounds must also be distinguished from deliberate withholding.

### 2. Saturation hides meaningful differences

14 of the 84 games reach the utilization cap. Full-wallet Blue versus full Red
reaches it at round6; 60%-wallet Blue versus full Red at round8. Both finish at
0.8 despite very different wealth and cumulative contributions. Uncapped
utilization is approximately332.43 versus60.85, respectively.

This establishes a counterexample, not an estimate of saturation frequency in
LLM experiments: the policy matrix was deliberately chosen, not randomly sampled.

### 3. The score is not a wealth proxy

Holding Red at zero, full-wallet Blue has a higher score than 10%-wallet Blue
while ending with dramatically less wealth. Holding punishment-heavy Blue fixed,
zero Red and attacking Red produce the same score0.125 but wealth12 versus0.

Across the 210 within-Blue matched Red-policy comparisons, there are54 score
ties hiding wealth differences, but no strict score/wealth direction reversals.
Across 252 within-Red comparisons of different Blue policies, there are70 strict
direction reversals and9 such ties. These are dependent descriptive comparisons,
not independent samples or statistical significance tests.

### 4. Communication has an important qualification

Full-contribution Red and full-contribution-plus-broadcast Red produce identical
wallets and scores under every Blue policy in both amount modes. Therefore a
message does **not** incur an extra scoring penalty when paired with the same
physical contribution in the original game.

Messaging-only and punishment-only agent-rounds contribute zero and enter the
low-contribution rate. Report these action types separately; calling all of them
"free-riding" overstates what the measurement establishes.

### 5. Alternative scoring definitions change some conclusions

Rescoring the same games, without re-optimizing their policies:

| Diagnostic | Games with changed score | Changes to Red comparisons within fixed Blue (210 pairs) | Changes to Blue comparisons within fixed Red (252 pairs) |
|---|---:|---:|---:|
| Absolute threshold5 instead of10 | 16 | 0 | 16 |
| Absolute threshold20 instead of10 | 32 | 0 | 14 |
| Threshold10% of current wallet | See results JSON | 12 | 12 |
| Current-wallet threshold with half-cent tolerance | See results JSON | 12 | 16 |
| Uncapped utilization diagnostic | See results JSON | 8 | 9 |

"Changes" include breaking or creating ties, not only strict order reversals.
Current-wallet thresholds need a rounding convention: original observations round
wallets to cents, so a policy requesting exactly10% of its observed wallet can
fall just below10% of its exact wallet. The half-cent tolerance is a diagnostic,
not an installed rule. Both relative variants count zero-wallet rounds as low
contribution and report their count separately. 14 games include zero-wallet
agent-rounds.

Uncapping exposes lost information but produces an unbounded score under wallet
growth. These results do not validate it as a replacement objective.

## Checks and artifacts

Every game passed deterministic replay, an independent recomputation of the
original Blue score, and every-round monetary conservation:

`wealth_after = wealth_before + (multiplier - 1) * pool - punishment_costs - actual_damage`

Final artifacts are in `output/scoring-validation-2026-11-25-final/`:

- `results.json` and `results.csv`: all episode metrics, alternative scores,
  action counts, punishment costs/damage, saturation, and zero-wallet rounds.
- `comparisons.json`: every matched comparison and its flags.
- `traces/`: all84 replayable games, including observations, actions, and events.
- `summary.json`: counts; `source/` and `manifest.json`: source snapshot and hashes.

The earlier `output/scoring-validation-2026-11-25/` is the preliminary pass. Use
the `-final` artifacts for the expanded threshold/rounding and comparison analysis.
Output folders are ignored by Git; this report and the runner can be retained in
the repository. Reproduce from the workspace root with a new output folder:

```powershell
python "experiment 1/validate_scoring.py" --output output/scoring-validation-new
```

## Recommendation

Retain the original equation for an explicitly labeled **composite-score
suppression** pilot, pending agreement with Prof Tan. Report final wealth/material
payoff, contribution fractions, total contributions, action-specific low
contribution, zero-wallet rounds, punishment costs/damage, and saturation alongside
it. Do not interpret a score decrease alone as learned defection or material harm.

If the primary claim is that Red makes Blue poorer, define Blue material payoff
as the primary outcome instead. If it is reduced cooperation, choose a definition
that separates available resources from the fraction voluntarily contributed.
These deterministic diagnostics do not establish that an evolved LLM Red exploits
Blue, select an optimal constitution, or demonstrate an arms race.
