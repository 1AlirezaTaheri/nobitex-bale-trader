# Weekly SHADOW observation report

## Weaknesses FIRST

- No clean historical holdout; this is forward SHADOW only, not executable orders or permission to invest.
- Short regimes can flatter any method. PASS only permits continued observation. No parameter changes; any change starts a new clock.
- Hash chains detect inconsistency, not a malicious rewrite/deletion of the entire root; export the latest hash to an independent location weekly.
- Economic marked equity includes downtime exposure; unobserved interval returns are null in clean performance. Interruption forbids checkpoint PASS.

Observed snapshots: 0; clean observed intervals: 0; interrupted: False.
Latest independently exportable chain hash: `None`.
Missing daily boundaries (Unix UTC): `[]`.
Outstanding missed boundaries after the latest snapshot: `[]`.
Report execution time (Unix UTC): `1795581493`.

| Account | Equity USDT | Net return | Max marked DD | Exposure | Costs | Legs |
|---|---:|---:|---:|---:|---:|---:|
| A | 100.000 | 0.00% | 0.00% | 0.00% | 0.000 | 0 |
| D | 100.000 | 0.00% | 0.00% | 0.00% | 0.000 | 0 |
| B1 | 100.000 | 0.00% | 0.00% | 0.00% | 0.000 | 0 |
| B3 | 100.000 | 0.00% | 0.00% | 0.00% | 0.000 | 0 |
| B4_25 | 100.000 | 0.00% | 0.00% | 0.00% | 0.000 | 0 |
| B4_50 | 100.000 | 0.00% | 0.00% | 0.00% | 0.000 | 0 |
| B4_75 | 100.000 | 0.00% | 0.00% | 0.00% | 0.000 | 0 |
| B7_A | 100.000 | 0.00% | 0.00% | 0.00% | 0.000 | 0 |
| B7_D | 100.000 | 0.00% | 0.00% | 0.00% | 0.000 | 0 |
| B8 | 100.000 | 0.00% | 0.00% | 0.00% | 0.000 | 0 |

B7 uses only lagged observed average exposure. It is not an exactly matched future-exposure control. No terminal liquidation is assumed in marked forward accounts.
Initial entry costs are included even before a full observed daily interval. Clean rebased returns exclude gap factors and are NOT economic account returns.

## Fixed review checkpoints

- 3 months / A: **PENDING**, due=None, checks={'minimum_days': False, 'uninterrupted': True, 'dd_le_60pct_B1': True, 'return_ge_B7_minus_2pp': True, 'positive_gross_and_costs_le_25pct': False}.
- 3 months / D: **PENDING**, due=None, checks={'minimum_days': False, 'uninterrupted': True, 'dd_le_60pct_B1': True, 'return_ge_B7_minus_2pp': True, 'positive_gross_and_costs_le_25pct': False}.
- 6 months / A: **PENDING**, due=None, checks={'minimum_days': False, 'uninterrupted': True, 'dd_le_60pct_B1': True, 'return_ge_B7_minus_2pp': True, 'positive_gross_and_costs_le_25pct': False}.
- 6 months / D: **PENDING**, due=None, checks={'minimum_days': False, 'uninterrupted': True, 'dd_le_60pct_B1': True, 'return_ge_B7_minus_2pp': True, 'positive_gross_and_costs_le_25pct': False}.
- 12 months / A: **PENDING**, due=None, checks={'minimum_days': False, 'uninterrupted': True, 'dd_le_60pct_B1': True, 'return_ge_B7_minus_2pp': True, 'positive_gross_and_costs_le_25pct': False}.
- 12 months / D: **PENDING**, due=None, checks={'minimum_days': False, 'uninterrupted': True, 'dd_le_60pct_B1': True, 'return_ge_B7_minus_2pp': True, 'positive_gross_and_costs_le_25pct': False}.

## Registered constant-mix risk comparisons (descriptive hindsight only)

All registered B4 weights; closest absolute marked MaxDD distance is descriptive hindsight, not an investable selection or exact risk match.
Status: INSUFFICIENT_OBSERVATIONS

| Strategy | Mix | Mix return | Mix MaxDD | DD distance | Return difference |
|---|---|---:|---:|---:|---:|
| A | B4_25 | 0.00% | 0.00% | 0.00% | 0.00% |
| A | B4_50 | 0.00% | 0.00% | 0.00% | 0.00% |
| A | B4_75 | 0.00% | 0.00% | 0.00% | 0.00% |
| D | B4_25 | 0.00% | 0.00% | 0.00% | 0.00% |
| D | B4_50 | 0.00% | 0.00% | 0.00% | 0.00% |
| D | B4_75 | 0.00% | 0.00% | 0.00% | 0.00% |

There is not enough evidence to infer an edge from a short forward period. No LIVE authorization, parameter changes or performance promises.
