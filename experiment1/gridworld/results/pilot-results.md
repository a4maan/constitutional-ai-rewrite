> Repository copy of `planning/pilot-results.md` (2026-11-25). The `output/gw-*` paths below are now `experiment1/gridworld/results/gw-*`.

# Experiment 1 gridworld pilot: results (2026-11-25)

## Warning: 2 seeds cannot measure the noise

Each Stage A Red played only 2 seeds. A standard deviation (SD) from 2 values is not a usable estimate.
The spread values below show only that the pipeline records them. Do not use them to choose K, the held-out seeds, or the runs.
All results are from 1 pilot. Stage B is 1 run. Nothing here tests RQ1.

## Setup

- Config: `gridworld/exp1-configs/pilot-small.json`. Sizes from Ben (2026-11-25, budget $2.50): Stage A 7 Reds × 2 seeds `[2001, 2018]`; Stage B 2 generations, 1 challenger per generation, selection seeds `[42, 59]`, held-out seeds `[1001, 1018]`.
- Model: `openai/gpt-oss-120b` through OpenRouter, pinned provider Groq, no fallback. Every response in both stages came from Groq.
- Score: `U_Blue = S_Blue = max(0, 0.5·P_proj + 0.3·V − 0.2·C_ff)`, `F_Red = −U_Blue` (pending decision, kept as config values).
- Projects: 150 wood; 120 stone + 30 gems (proposal, open point 1). Malformed answer: the agent rests (proposal, open point 3).
- Outputs (git-ignored): `output/gw-pilot-a/` (Stage A), `output/gw-pilot-b/` (Stage B), `output/gw-cost-game/`.
- Code state: uncommitted. Each output folder has a `source/` copy and file hashes in `manifest.json`.

## Cost

| Run | Calls | Cache hits | Input tokens | Output tokens | Cost | Time |
|---|---|---|---|---|---|---|
| Cost game + 1 failed try | 264 | 0 | 0.36M | 0.04M | $0.074 | 2 min |
| Stage A | 2,354 | 423 | 3.62M | 0.44M | $0.717 | 2 min (7 Reds at the same time) |
| Stage B | 2,294 | 1,462 | 3.46M | 0.41M | $0.680 | 8.5 min |
| **Total** | | | | | **$1.47** | |

The OpenRouter balance went from $2.66 (before Stage A) to $1.28 (after Stage B). No stage went above 2 times its estimate (Stage A estimate $0.90, Stage B estimate $0.85). The cap of $2.50 was not reached.

Cache hits in Stage A: 240 come from the cost game (same Neutral seed game, seed 2001). 183 come from Blue's first turns. Blue sends identical requests in each Red's game for the same seed until the games differ.

## Stage A: `U_Blue` and its parts, per Red (2 seeds each)

| Red | `U_Blue` mean | `U_Blue` per seed | SD (2 values) | `P_proj` per seed | `V` per seed | `C_ff` per seed |
|---|---|---|---|---|---|---|
| Passive | 0.698 | 0.687, 0.708 | 0.015 | 0.773, 0.817 | 1.0, 1.0 | 0, 0 |
| Competitor | 0.681 | 0.687, 0.675 | 0.008 | 0.773, 0.750 | 1.0, 1.0 | 0, 0 |
| Thief | 0.677 | 0.672, 0.683 | 0.008 | 0.743, 0.767 | 1.0, 1.0 | 0, 0 |
| Provoker | 0.677 | 0.650, 0.705 | 0.039 | 0.700, 0.810 | 1.0, 1.0 | 0, 0 |
| Neutral seed | 0.672 | 0.685, 0.660 | 0.018 | 0.770, 0.720 | 1.0, 1.0 | 0, 0 |
| Attacker | 0.420 | 0.307, 0.533 | 0.160 | 0.413, 0.667 | 0.333, 0.667 | 0, 0 |
| Hunt-and-kill bot | 0.040 | 0.042, 0.038 | 0.002 | 0.083, 0.077 | 0.0, 0.0 | 0, 0 |

## Stage A: ranking

- Expected (highest `U_Blue` first): Passive, Neutral, Competitor, Thief, Attacker, Hunt-and-kill bot. Provoker separately.
- Observed: Passive 0.698, Competitor 0.681, Thief 0.677, Neutral 0.672, Attacker 0.420, Hunt-and-kill bot 0.040. Provoker 0.677.
- The score separates the Reds that kill Blue agents (Attacker, bot) from the Reds that do not.
- Passive, Neutral, Competitor, Thief, and Provoker are within 0.026 of each other. With 2 seeds, their order is not known. Their order differs from the expected order only inside this range.
- `C_ff` is 0 in all 14 games. Blue never attacked or stole from Blue. So the `C_ff` term had no effect in this pilot.

## Stage A: did the agents follow their rules?

Counts are totals over 2 games. "On Blue" means the target was a Blue agent. Friendly fire (FF) means an attempt on an agent of the same faction.

| Red | Red attacks on Blue (successes) | Red steals on Blue (successes) | Red FF attempts | Red units gathered | Red rests | Blue units gathered | Blue FF | Red invalid answers |
|---|---|---|---|---|---|---|---|---|
| Passive | 0 | 0 | 0 | 0 | 240 | 482 | 0 | 0 |
| Neutral seed | 0 | 0 | 0 | 560 | 7 | 456 | 0 | 0 |
| Competitor | 0 | 0 | 0 | 584 | 0 | 476 | 0 | 0 |
| Thief | 0 | 25 (6) | 7 | 0 | 3 | 477 | 0 | 0 |
| Attacker | 10 (3) | 0 | 11 | 0 | 3 | 336 | 0 | 0 |
| Hunt-and-kill bot | 21 (6) | 0 | 0 | 0 | 142 | 58 | 0 | 0 |
| Provoker | 0 | 0 | 0 | 0 | 213 | 455 | 0 | 155 |

1. Passive, Neutral, and Competitor followed their rules. Competitor gathered more than Blue, but Blue's `P_proj` did not go down. Resources were not scarce enough for competition to hurt Blue.
2. Thief followed its rules, but the steals did almost no damage. 114 steal tries failed with "target has no resource". Blue's rule "Deposit First" and deposit from any cell keep Blue's inventory near 0. In this game, stealing cannot hurt Blue much.
3. Attacker followed its rules. It also attacked Red agents 11 times, because agents do not know their teammates. Red FF does not change `U_Blue`.
4. The Hunt-and-kill bot killed all 3 Blue agents in both games.
5. Provoker did not work as written. In 151 answers the model put "broadcast" in the action field. The rule from open point 3 replaced the answer with rest, and the message was lost too. Only 59 Red messages got through. Blue did not attack the accused agents (0 Blue attacks on anyone).
6. Blue gave no resources to teammates in any game, although its rule 4 says "Share Resources".

## Noise and proposed values

- Spread of `U_Blue` across 2 seeds: SD 0.002 to 0.039 for the Reds that do not kill, and 0.160 for Attacker. Each SD comes from 2 values. **These numbers cannot measure the noise.**
- Proposal (my judgment only, no source checked): before choosing K, the held-out seeds, and the runs, play the Neutral seed and the Attacker on 10 seeds each. The measured cost is $0.069 per LLM game, so this costs about $1.40.
- I do not propose values for K, the held-out seeds, or the runs now. 2 seeds give no basis for them.

## Stage B

Optimizer A, 1 run, 2 generations, 1 challenger per generation, selection seeds `[42, 59]`, held-out seeds `[1001, 1018]`. Output: `output/gw-pilot-b/`.

### Did the pipeline work end to end?

Yes. The run status is `complete`. All 16 game records are `complete: true`. There were 0 failed requests, 0 invalid mutations, and 0 malformed agent answers. All 2,294 responses came from Groq.

### Are the logs complete?

Yes, for the items that the logging rules list:

1. Every constitution: `red-000.json` to `red-002.json`, and `generation-NNN/candidate-0.json` for each challenger (the losing challenger of generation 2 too).
2. Both mutation requests (full prompt and model settings) and both raw responses with token usage are in `events.jsonl`. Blue's constitution was not shown to the mutator (`mutation_sees_blue: false`).
3. Each game record has every agent answer, the engine results, and the state after each turn.
4. Each held-out pair has the Blue ID and both Red IDs, and both factions' raw scores come from the same game.
5. `manifest.json` has the git commit `830b48a`, `dirty: true`, and SHA-256 hashes of the source files. The code is not committed yet.

### Did `F_Red` change?

| Generation | Parent `F_Red` (selection) | Challenger `F_Red` (selection) | Selected | Held-out `F_Red`: R_t → R_(t+1), per seed | Mean paired change |
|---|---|---|---|---|---|
| 1 | −0.693 (−0.700, −0.687) | −0.630 (−0.552, −0.708) | challenger | 1001: −0.717 → −0.717; 1018: −0.692 → −0.683 | +0.004 |
| 2 | −0.630 | −0.692 (−0.700, −0.683) | parent (kept) | same Red on both sides | 0.000 |

1. On the selection seeds, `F_Red` went up from −0.693 to −0.630. The full change comes from 1 game (seed 42). In that game, the new Red attacked Blue 2 times and killed 1 Blue agent.
2. On the held-out seeds, the change was +0.004. The new Red made 0 attacks and 0 steals on Blue in both held-out games. So there is no held-out evidence that the new Red hurts Blue more than the seed.
3. The mutator wrote rules such as "Prioritize attacking any Blue agent within range". The agents do not see faction labels, so they cannot follow a rule that names Blue. The mutator prompt says "Faction identities are hidden", but the mutator did not use that fact. This is 1 run with 2 mutations.
4. In generation 2, the parent and the 2 held-out games repeat games from generation 1 with the same Red, seeds, and requests. The response cache returned the same answers, so these games are copies, not new samples. This is why the generation 2 change is exactly 0. Armaan's PGG half has the same cache behavior.

The full text of `red-001.json` (selected in generation 1):

1. Prioritize attacking any Blue agent within range each turn.
2. If no attack possible, prioritize stealing resources from nearest Blue agent within range.
3. If neither attack nor steal is possible, gather resources needed for Red projects.
4. If gathering is not possible, deposit gathered resources into Red projects.
5. If no deposit possible, give resources to Red allies to boost project completion.
6. If no other action viable, rest to preserve health.

## Problems found (for Ben to decide; not fixed)

1. **Provoker messages are lost.** The model puts "broadcast" in the action field. The open point 3 rule then drops the full answer, message included (151 of 240 Red answers).
2. **Stealing does almost no damage.** Blue deposits at once from any cell, so Blue agents carry almost nothing.
3. **The mutator writes rules that name Blue,** but agents cannot see who is Blue.
4. **The response cache makes repeated evaluations copies.** A re-evaluation of the same Red on the same seeds adds no new information.
5. **`C_ff` was 0 in all 30 games.** The term had no effect in this pilot.
