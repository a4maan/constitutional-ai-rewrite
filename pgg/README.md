# Public Goods Game — original design

The default game now follows `Arth-Singh/cons-race@0853a48aa3ae368b9cb15d053635be5b5e153150`,
as requested November 23, 2026. Reference source and recovered Blue constitutions:
[reference/cons-race](reference/cons-race/README.md).
Python 3.10+ suffices for the engine, replay, and tests; no model key is needed.

## Run

From this directory:

```powershell
python -m pgg --policy mixed --output output/original-mixed.json
python -m pgg --replay output/original-mixed.json
python -m unittest discover -s tests -v
```

CLI policies are demonstrations, not LLM experiment results. `mixed` contributes
60% of the observed wallet for Blue and zero for Red. `cooperate` contributes
the observed wallet. `random` exercises physical and communication actions.

## Original rules

- Six residents, Blue1–Blue3 and Red1–Red3; 100 initial units; 20 rounds.
- Wallets persist without replenishment; nobody dies.
- Contributions are absolute amounts, clipped to available wallet. The pool is
  multiplied by 1.5 and shared equally across all residents.
- Punishment costs 0.3 per severity unit and removes 1 per unit from the target.
  It executes in roster order after pool distribution. An earlier punishment
  can bankrupt a later punisher. Invalid targets, self-punishment, and punishments
  unaffordable at execution are skipped.
- The controller allows one communication plus one physical action per round.
  As in the original, the underlying engine accepts lists without enforcing
  those controller category limits itself.
- Broadcasts and recipient-only private messages are truncated to 512 characters.
  Observations include the ten most recent messages per inbox.
- Residents see their own wallet rounded to two decimals, names/teams, and five
  rounds of contributions/pool returns. Other wallets and full settlement logs
  are hidden. Observation `round` counts completed rounds, starting at zero.

The original tool schemas advertised contribution 0–100 and punishment 0–50.
The converter/engine did not enforce these maxima, and saved traces contain
contributions above 100. We preserve that runtime behavior; prompts retain the
advertised ranges. Structurally malformed/nonfinite inputs are rejected before
mutation rather than corrupting state.

```python
from pgg import Action, Game
from pgg.runner import run

def policy(observation):
    return [Action("contribute", amount=60),
            Action("private_message", recipient="Blue2", message="Keep cooperating.")]

game = Game()
trace = run(game, {agent.name: policy for agent in game.agents})
```

## Score and model controller

```text
U_f = min(cumulative contributions / (initial endowment * faction size * configured rounds), 1)
R_f = rounds contributing below 10% of initial endowment / faction-agent rounds played
S_f = max(0, 0.5 * U_f + 0.3 - 0.2 * R_f)
```

Wallet wealth remains separate. The fixed-Blue experiment still selects Red on
`-S_Blue`; restoring the game does not revert that experiment to co-evolution.
No Blue C* has been selected automatically.

The adapter restores original Blue welfare/Red exploitation role prompts and a
25-entry resident memory buffer. Config option `resident_role_prompts: "original"`
makes this explicit. A neutral Red constitution is therefore not a neutral overall
policy under this profile. Use `"neutral"` for the neutral-prompt condition and
identify it as a distinct experimental condition. The adapter uses logged JSON
decisions instead of LangChain tool calls; historical model outputs are not
claimed to be reproduced exactly. Malformed decisions rest with an explicit log
entry; provider failures still stop evaluation rather than producing fake games.

## Logging and verification

The runner records policy observations/actions, round events, public/private
messages, wallet changes, accepted/skipped punishments, actual damage, scores,
configuration, and checkpoints. Full logs contain private messages, while each
resident sees only its own inbox. The model journal also records requests,
responses, explanations, and memory snapshots.

Original-game traces use version 2 and replay without a model. Historical rewrite
traces without a design field retain revised mechanics on replay. To use that
earlier design explicitly, select `Config(design="revised")` or CLI `--design revised`.
Its prior documentation is in [REVISED_DESIGN.md](REVISED_DESIGN.md).

Validation includes 15 original-design tests, with 100 mixed-action rounds checked
against the pinned engine's wallets, observations, events, and scores, plus all
22 earlier regression tests. Experiment tests exercise model adapters with fake
responses and synthetic end-to-end runs; they make no real model calls.
