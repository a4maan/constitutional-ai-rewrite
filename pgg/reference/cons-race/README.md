# Recovered PGG source and Blue checkpoint audit

**Subsequent user decision:** use the original design. The active default now
implements it; see [the current specification](../../README.md). The comparison
and audit below describe the pre-migration rewrite and retained historical evidence.

Reviewed November 23, 2026. Source: `Arth-Singh/cons-race`, pinned commit
`0853a48aa3ae368b9cb15d053635be5b5e153150`.

The original PGG implementation exists in this repository. Our local engine is
an independent rewrite and is **not behaviorally equivalent** to it. The recovered
constitutions are candidates, not validated optimal constitutions.

## Files

- `ENGINE_COMPARISON.md`: verified agreements, differences, and migration decisions.
- `upstream/`: 248 original files, including source, checkpoints, Blue selection
  traces, and summarized PGG variants/replicates. This is a selective snapshot,
  not a full clone or a complete replay archive.
- `manifest.json`: commit, upstream URLs, sizes, and SHA-256 hashes for every file.
- `candidate-index.json` / `.csv`: all 31 Blue checkpoints, scores, deduplication,
  and selection evidence. JSON includes parent/child trial metrics and failures.
- `candidates/`: JSON conversions retaining rule names and verbatim guidance in
  priority order. They omit summary metadata and are not full prompt reproductions.
- `shortlist.json`: one representative per unique rule set.
- `engine-checks.json`: deterministic comparison results.

No LLM calls, paid experiments, or AWS changes were made for this audit. No active
experiment config or game behavior was changed.

## Five unique Blue candidates

| Representative | Same rules in generations | Rules | Recorded Blue score range |
|---|---|---:|---:|
| `blue-gen-000.json` | 0–1 | 5 | 0.370076 (generation 1 only) |
| `blue-gen-002.json` | 2–5 | 7 | 0.449643–0.608877 |
| `blue-gen-006.json` | 6 | 8 | 0.673824 |
| `blue-gen-007.json` | 7–28 | 6 | 0.666387–0.798333 |
| `blue-gen-029.json` | 29–30 | 7 | 0.776667–0.786667 |

Generation 22 and 23 share the highest recorded Blue score, 0.798333. They use
exactly the same rules as generation 7. Generation 30 scores 0.776667 and is not
the highest-scoring checkpoint. These scores were obtained against changing Red
opponents; they do not establish a ranking against a common neutral Red.

All 30 scored checkpoints match their saved best program's rule data. Their Blue
scores agree across the best-program record, checkpoint metrics, partial Blue
metrics, and outer evolution trace. Best-program IDs link to the parent/child
selection traces: 23 retained a parent and 7 selected a child. Selecting a child
does not necessarily mean the rule data changed; deduplication finds only five
distinct rule sets including the initial seed.

The selection traces retain unsuccessful attempts: generation 5 has a child
timeout without a score, and generations 15 and 20 have child syntax errors
recorded as zero. These are failures, not valid zero-score performance evidence.
The top-level `blue_rules: 0` fields are a broken counting heuristic: the
orchestrator counts `ConstitutionRule(` strings even though the PGG rules are
literal dictionaries. The recovered programs actually contain 5–8 rules.

The alternating runner evaluates Blue against the previous Red, then Red against
the newly selected Blue. Therefore its outer Blue and Red score columns do not
come from the same pair of games. Their difference is not matched cross-play.
The evaluator constructs seeds 42 and 59 for the recorded two-seed configuration.
This audit verifies the saved records, not provider-level determinism or every
historical model response; the current pinned source is not a hash-locked runtime
snapshot of the April runs.

Files named `final_exp*_evolved_cstar*.py` refer to **gridworld** constitutions
(gathering, deposits, overseers), not an independently optimized PGG C*.

## Recommended use

Keep all five distinct candidates for a common-condition evaluation, including
the original seed. Do not run all 31 duplicates. First decide whether the next
study reproduces the original game or uses our revised game. Private messaging
and communication action costs must be resolved before these candidates can be
used faithfully. Do not silently edit their contradictory rules: for example,
several say to contribute 80% plus an extra 30% of the wallet, which can exceed
100%. If an edited version is tested, retain the original and label the adaptation.

## Reproduce the audit

From the workspace root:

```powershell
python pgg/reference/cons-race/fetch_reference.py
python pgg/reference/cons-race/audit_reference.py
```

Fetching uses authenticated GitHub CLI read access. The audit requires only
Python's standard library; it extracts constitution data with `ast.literal_eval`
instead of importing constitution programs. It imports the reviewed deterministic
game/scoring modules for comparisons and never imports the LLM/evolution runners.
Ten comparison cases pass, including 100 matched contribution rounds across five
seeds, ordinary punishment, and four expected differences. The existing local PGG
suite also passes all 22 tests.
