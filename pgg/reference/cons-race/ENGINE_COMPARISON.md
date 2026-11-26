# Original PGG versus current rewrite

Historical comparison before the November 23 migration. The user subsequently
selected the original game. `pgg/pgg/original.py` is now the default; the revised
engine remains available for older replays. The differences below describe that
retained revised engine, not the active original profile.

Reference paths below are under `upstream/`; current paths are under `pgg/pgg/`
or `experiment 1/` in the workspace. Source is pinned in `manifest.json`.

## Agreements confirmed

Both default to six residents, three per faction, 20 rounds, 100 initial units,
pool multiplier 1.5, punishment cost 0.3, and target loss 1 per severity unit.
Wallets persist without replenishment or deaths. Contributions are deducted,
then the multiplied pool is shared equally, then punishment is settled.

Both compute, after at least one round:

`U_f = min(cumulative faction contributions / (100 * faction size * 20), 1)`

`R_f = faction-agent rounds contributing below 10 / (faction size * played rounds)`

`S_f = max(0, 0.5 * U_f + 0.3 - 0.2 * R_f)`

The configured endowment and horizon replace 100 and 20 when changed. At a
non-default endowment, the original threshold scales as 10% of endowment, whereas
our threshold remains the independently configured absolute value (default 10).
Score saturation at 0.8 is shared by both implementations and is not fixed by
switching engines. At zero completed rounds our raw score is null; the original
scorer would return 0.3. That does not affect completed-game scores.

Contribution-only wallet settlements and faction scores agree over 100 matched
rounds across five seeded action sequences. A normal affordable punishment also
agrees. These checks cover common mechanics, not full behavioral equivalence.

## Material differences

| Area | Original implementation | Current rewrite | Consequence / decision needed |
|---|---|---|---|
| Action allowance | Resident controller allows one communication **and** one physical action per round. Engine accepts lists and does not itself enforce these category limits. | Exactly one action total. | Our messages consume a contribution/punishment opportunity. Restore the original allowance for a reproduction; label a one-action study as revised. |
| Private messages | Public broadcasts and recipient-only private inboxes. | Public broadcasts only. | Four of five unique candidate rule sets request private praise. They cannot follow those instructions literally in our game. |
| Contribution units | Absolute amount, clipped to current wallet by engine. Tool schema advertises 0–100. | Fraction of round-start wallet in [0,1]. | Fractions can be translated for settlement comparisons, but model choices/prompts differ. Do not impose a new 100-unit cap without resolving the original schema/runtime inconsistency. |
| Declared tool limits | Contribution 100, punishment 50, message 512 characters in tool schema. Converter/controller do not explicitly validate against these models before forwarding parsed calls; engine accepts larger affordable monetary requests. | No equivalent severity/message caps; numeric actions strictly validated. | Original trace artifacts contain contributions above 100. A schema limit is not evidence that the historical run enforced it. |
| Punishment timing | Iterates residents in roster order, mutating balances immediately. An earlier attack can prevent a later resident from affording its chosen punishment. Pool returns can fund punishment. | All costs/attacks settled simultaneously; affordability checked at round start. | Different outcomes near depleted wallets; original order can advantage earlier residents (Blue listed first). Preserve only if reproducing the original rules. |
| Other wallets | Own wallet rounded to two decimals; roster includes names, alive flags, and teams, but no other wallets. | All current wallets visible at full precision. | Our agents have extra information, including for estimating contribution fractions and targeting. |
| History | Last five rounds of contributions and pool statistics, plus recent public/private messages. Resident controller also maintains a memory context. | Full game history; Groq adapter compacts records while retaining all rounds. | More history and settlement detail can change behavior. Exact reproduction also requires matching controller memory, not just trimming observations. |
| Identity | Blue1/Red1 names and explicit cooperators/free_riders teams. | blue_1/red_1 names; faction field hidden by default. | Both leak faction through names. Current `reveal_factions=False` is not an anonymity treatment. |
| Round index | Observation round starts at 0, reaches 20 after final settlement. | Next-action round starts at 1; `done` and remaining rounds explicit. | Periodic broadcast and late-round rules may trigger differently. Use an explicit convention. |
| Invalid actions | Engine clips some values and silently ignores invalid/unaffordable punishment; evaluator catches decision exceptions and rests. It is not transactional. | Invalid action rejects the whole round before mutation; experiment may fail the episode. | Need an explicit logged correction/failure policy before model experiments. |
| Objectives in resident prompts | Blue gets group-welfare/punishment instructions; Red gets personal-wealth/exploitation instructions in addition to constitutions. | Shared neutral action instructions plus own constitution. | Reusing identical constitution text does not reproduce the original policy. For the neutral-Red study, keeping prompts neutral is intentional. |
| Evolution objective | Evaluator defaults to own faction S; supports advantage and Red `1-S_B` modes. YAML explicitly tells both sides to maximize own S. | Fixed-Blue runner uses Red `-S_B`. | The original main run selects cooperation, not adversarial Blue suppression. `1-S_B` and `-S_B` rank candidates equally only for valid scores and compatible failure handling. |

## Concrete difference checks

`engine-checks.json` records reproducible cases:

1. Five seeded 20-round contribution sequences: wallets and faction scores match.
2. Ordinary punishment: wallets match.
3. Deplete Red1 to 10 using three 30-unit punishments. Next round Blue1 and Red1
   target each other with severity 10. Original Blue1 ends at 88 because Red's
   chosen attack is skipped after bankruptcy; current Blue1 ends at 78 because
   the two chosen attacks settle simultaneously. All severities are within 50.
4. Deplete Blue1 to 1. Next round it requests severity 10 while others contribute.
   Original allows the 3-unit cost after pool distribution; current rejects the
   round because Blue1 cannot afford it from its starting wallet.
5. Original permits contributing 60 and privately messaging in the same round.
   Current rejects action lists and has no private-message action.
6. After six rounds, original contribution history has five entries while the
   current observation retains six and exposes other residents' wallets.

## Migration recommendation

Keep the active engine and experiment configs unchanged during this audit.
Preserve the original source and candidate texts. Before evaluation, choose and
document one protocol:

- **Original-game reproduction:** match communication allowance, private inboxes,
  observation visibility/history/memory, absolute action interface, prompt roles,
  round convention, and sequential punishment; explicitly address the advertised
  action-limit inconsistency and record whether it changes the protocol.
- **Revised fixed-Blue experiment:** retain deliberate changes with a versioned
  specification, provide private messages or openly adapted constitutions, and
  evaluate all candidates anew. Original scores are provenance, not transferable
  performance estimates.

The second protocol fits the planned neutral-Red study, but is a new controlled
experiment rather than an exact replay of the April results. No candidate is
selected or installed as C* by this audit.
