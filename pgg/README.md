# Public Goods Game

A standalone implementation of the PGG described in Sections 3.2 and 4.2 of
`C:/Users/armaa/CAI/constitutional-arms-races-overleaf.pdf`. This is newly written
source, not the recovered implementation behind the paper's results.
Requires Python 3.10+; no third-party packages or API keys are needed.

## Run

Run these commands from this project's `pgg/` directory (the directory containing
this README and `tests/`). From the workspace root, first run `cd pgg`.

```powershell
python -m pgg --policy mixed --output output/pgg-mixed.json
python -m pgg --policy random --seed 42 --output output/pgg-random.json
python -m pgg --policy cooperate --rounds 20
python -m unittest discover -s tests -v
```

`mixed` uses a fixed 60% contribution for Blue and zero for Red. `cooperate`
contributes 100%; `random` exercises all four actions using independent seeded
generators. These are demonstration policies, not implementations of the paper's
LLM constitutions or evidence of constitutional co-evolution.

## Rules and accounting

Default: six agents (three Blue, three Red), 100 initial units each, 20 rounds,
pool multiplier 1.5, punishment cost 0.3 and target damage 1.0 per unit.
Wallets persist; there is no replenishment, spatial world, gathering, or death.

Each agent chooses one action per round:

* `Action("contribute", fraction=0.6)` spends 60% of its starting wallet.
* `Action("punish", target="red_1", amount=10)` costs 3 and requests 10 damage.
* `Action("broadcast", message="Please cooperate")` publishes text without moving money.
* `Action()` rests. Missing actions also rest.

Round resolution is atomic: validate all actions, deduct contributions, distribute
the multiplied pool equally among all agents, deduct punishment costs, then apply
incoming damage simultaneously. All policies see the same round-start state.
Punishment budgets are constrained by the starting wallet, so anticipated pool
returns cannot finance a punishment. Damage is capped at the target's remaining
wallet after its own costs; attackers still pay the full requested cost. Multiple
punishments aggregate without dependence on iteration order. Self-punishment,
unknown targets, mixed-action fields, nonfinite numbers, and overspending reject
the entire round. Zero-wallet agents remain participants and receive pool returns.
Floating point arithmetic is used; balances are not rounded to whole tokens.

These resolution, affordability, damage-cap, one-action, and observation choices
make details underspecified in the paper explicit. They must be matched against
the original code before claiming exact reproduction of its experiments.

## Observations and policies

Agents see identities, current wallets, and the complete public history of
completed rounds (including contributions, actions, punishments, and broadcasts).
They cannot see another agent's pending action. Faction labels are hidden by
default, with `Config(reveal_factions=True)` to expose them. Public history allows
conditional contributions and punishment based on previous behavior. Messages
are recorded verbatim and are never executed.

```python
from pgg import Action, Game
from pgg.runner import run

def policy(observation):
    return Action("contribute", fraction=0.6)

game = Game()
result = run(game, {agent.name: policy for agent in game.agents})
```

An LLM adapter can implement this callback and return validated `Action` objects
(or use `Action.from_dict` to parse its JSON object). Assign different callbacks
or constitution-bearing controllers to each faction. Invalid policy output raises
an error before the round changes; the runner does not silently fabricate actions.
The game engine and policies are separate so arbitrary constitutions or an
external evolutionary optimizer can be evaluated without changing the rules.

## Scoring and fitness

For each faction:

```
uncapped_utilization = cumulative_contributions / (initial_endowment * faction_size * configured_rounds)
U = min(1, uncapped_utilization)
R = count(agent-round contributions < 10) / (faction_size * completed_rounds)
S = max(0, 0.5 * U + 0.3 - 0.2 * R)
```

The free-riding threshold is an absolute 10 units by default, not 10% of the
current wallet. Punish, broadcast, and rest contribute zero and therefore count
as free-riding rounds under this definition. Partial-episode contribution scores
still use the configured episode length; free-riding uses rounds actually played.
Before any round, raw score is `None` and fitness evaluation raises an error.

The paper says utilization is bounded by 1 but gives a fixed denominator while
allowing wallets to grow. Those statements need an additional rule: this version
caps utilization for scoring, and logs the uncapped ratio so saturation is visible.
This is an explicit interpretation, not a verified detail of the original code.
It yields the stated raw score range [0.1, 0.8]. Wallet payoffs remain separate.

`game.fitness("Blue", "absolute")` returns S_Blue;
`game.fitness("Blue", "advantage")` returns S_Blue - S_Red;
`game.fitness("Red", "pure_adversary")` returns 1 - S_Blue.
All use the same episode snapshot. Fitness does not change environment mechanics.
The runner does not implement OpenEvolve, model calls, or 30-generation search.

## Logs and checks

Replay a trace without policies or model calls:

```powershell
python -m pgg --replay output/pgg-mixed.json
```

The CLI checkpoints the trace after each completed round and records pending
decisions and the error if a round fails. Replay verifies the completed prefix.
Each decision includes the exact observation passed to the policy and its
returned action. Each round also records the faction score components.
From Python, pass `metadata=` to `run` for experiment IDs, constitutions,
model settings, or seeds, and `checkpoint=` to persist the trace as it runs.
The policy callback exposes only observations and actions to the runner.
Provider requests, responses, and optimizer state would need instrumentation
in their respective adapters.

JSON exports include configuration, roster, policy metadata (CLI), complete round
actions, starting/ending wallets, contributions, pool, individual returns,
punishment costs, requested/actual damage, messages, and faction score components.
`reset()` clears all episode state for a new evaluation.

The 20 unittest cases cover the formulas, persistent wallets, equal distribution,
free-riding, simultaneous punishment, caps, transactional failures, observation
isolation, fitness, reset, deterministic replay, and the CLI. The random accounting
test checks ten independent seeded 20-round episodes plus deterministic replays:

```
total_after = total_before + (multiplier - 1) * pool - punishment_costs - actual_damage
```
