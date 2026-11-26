# Fitness objective pilot

## Question

Does Red's fitness, F_Red = -S_Blue, reward scripted Red policies when the same fixed Blue policy receives a lower Blue score?

## Result

Analyzed 84 existing deterministic games from the LLM-free scoring run. Among 128 same-Blue, same-rule comparisons where Blue scores differed, Red fitness ranked every lower-Blue-score outcome higher (128 passes, 0 failures). This is algebraically guaranteed by F_Red = -S_Blue; the games demonstrate how that objective ranks these policies, not that it independently measures adversarial intent.

For full-wallet Blue under the original runtime rules:

| Red policy | Blue score S_B | Red fitness -S_B | Red own score S_R | Red final wealth |
|---|---:|---:|---:|---:|
| full | 0.800000 | -0.800000 | 0.800000 | 997,575.414 |
| zero | 0.289681 | -0.289681 | 0.100000 | 1,197.126 |
| punish_blue | 0.151250 | -0.151250 | 0.100000 | 41.250 |
| message_only | 0.289681 | -0.289681 | 0.100000 | 1,197.126 |
| full_and_message | 0.800000 | -0.800000 | 0.800000 | 997,575.414 |
| ten_percent | 0.800000 | -0.800000 | 0.701928 | 6,778.893 |

The strongest of these scripted Red policies is `punish_blue`: it lowers Blue's score to 0.151250 (Red fitness -0.151250). This is a policy-level control result, not learned behavior.

In 0 examined pairwise comparisons, Red's own score rose while Blue's fell. The direct counterexample is stronger: against full-wallet Blue, punishment Red drops Blue to 0.151250, while Red itself scores only 0.100000 and ends with 41.250 wealth, compared with 0.800 and 997,575.414 wealth for full-contribution Red. So `-S_Blue` rewards the Blue harm even when Red's own outcomes deteriorate.

## Interpretation

The fitness formula faithfully encodes the narrow objective 'minimize Blue's existing composite score.' It does not guarantee that Red learns a purposeful attack, that Red benefits, or that Blue loses wealth. Those are separate claims and need separate outcomes and controls. The scoring validation found saturation, depletion, and score/wealth mismatches; use Blue wealth and available-wallet contribution fraction alongside S_Blue.

A useful LLM pilot should now compare neutral-prompt Red before and after optimization against frozen Blue, using the same held-out games and controls. That tests learned policy changes. This scripted analysis cannot replace it.

Method: all policies were deterministic and fixed; each Blue/Red pair was run once in each contribution-cap mode, from the same 100-unit initial balances for 20 rounds. Pair counts are comparisons among this designed policy grid, not statistical samples.
