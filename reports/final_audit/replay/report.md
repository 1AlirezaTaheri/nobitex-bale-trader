# Final adversarial audit

## Weaknesses and data contamination FIRST

- Repeated historical reuse across legacy, LayeredPortfolio, V3 and sensitivity grids; former holdout is NOT clean OOS. All historical results are hypothesis-generating only.
- Old audit manifest does not authenticate the current protocol. Original document was not inspected before writing; provenance is unresolved. Amendment 001/002 explicitly disclosed.
- Selected current universe has survivorship bias; no historical order books, interpolation, missing-day signals or guaranteed executable prices.
- Pooled CAGR and underwater duration count evaluated days, not elapsed calendar time through gaps. Segment-end liquidations and cash resets are research conventions.
- Native S0/S1 risk, precision, depth and intrabar models are NOT economically identical to price-only baselines. Their fractional exposure/B7 and explicit costs are unavailable; no rescue verdict is allowed.
- Uncentered bootstrap sign tails are descriptive, not exact null-test p-values. Extreme adjusted percentile bounds are simulation-resolution limited. The cyclic timing null is NOT executable same-turnover random orders.
- Daily drawdown understates intraday risk. No result authorizes LIVE or meaningful capital. Genuine post-registration forward results are not manufactured by smoke tests.
- Configuration-row inventory: 262 archived rows plus 25 audit series; Bonferroni M=287. 999 draws imply minimum adjusted tail 0.287; no adjusted p<0.05 can pass.
- Amendments: FINAL_AUDIT_AMENDMENTS.md and FINAL_AUDIT_IMPLEMENTATION_NOTES.md. Native B7, exact-turnover executable random schedules, native fresh-start sensitivity and full native delayed/crash execution are unverified/unavailable, not passes.

## Common-calendar metrics (net costs; 100 USDT initial)

| Name | Days | Return | Max DD | Calmar | Sharpe | Worst 365d | Costs USDT |
|---|---:|---:|---:|---:|---:|---:|---:|
| S2_A | 905 | 60.83% | -42.32% | 0.499 | 0.691 | -32.23% | 12.073 |
| S2_B | 905 | 107.02% | -37.19% | 0.917 | 0.984 | -18.65% | 12.397 |
| S2_C | 905 | 115.20% | -32.30% | 1.121 | 1.096 | -13.01% | 9.651 |
| S2_D | 905 | 74.35% | -25.15% | 0.999 | 0.893 | -10.22% | 6.967 |
| B1 | 905 | 180.12% | -28.95% | 1.779 | 1.162 | 7.32% | 4.296 |
| B2 | 905 | 87.59% | -41.37% | 0.698 | 0.770 | -22.96% | 3.068 |
| B3 | 905 | 69.06% | -27.83% | 0.848 | 0.863 | 6.27% | 2.667 |
| B6 | 905 | 0.00% | 0.00% | N/A | N/A | 0.00% | 0.000 |
| B8 | 905 | 96.72% | -30.55% | 1.027 | 0.916 | -16.00% | 16.584 |
| B4_25 | 905 | 36.27% | -7.99% | 1.664 | 1.165 | 3.97% | 0.634 |
| B4_50 | 905 | 81.36% | -15.37% | 1.766 | 1.184 | 6.42% | 1.606 |
| B4_75 | 905 | 126.38% | -22.47% | 1.737 | 1.158 | 7.49% | 2.704 |
| B5_25 | 905 | 22.60% | -13.75% | 0.623 | 0.729 | -7.27% | 0.645 |
| B5_50 | 905 | 43.84% | -26.16% | 0.604 | 0.720 | -15.07% | 1.400 |
| B5_75 | 905 | 65.46% | -34.59% | 0.651 | 0.741 | -19.47% | 2.108 |
| S0 | 905 | 4.32% | -4.07% | 0.423 | 0.483 | -1.94% | N/A |
| S1_full | 700 | 0.00% | 0.00% | N/A | N/A | 0.00% | N/A |
| S1_L1 | 700 | 0.00% | 0.00% | N/A | N/A | 0.00% | N/A |
| B7_S2_A | 905 | 124.27% | -21.50% | 1.791 | 1.177 | 7.72% | 2.906 |
| B7_S2_B | 905 | 125.73% | -21.70% | 1.791 | 1.176 | 7.74% | 2.942 |
| B7_S2_C | 905 | 113.35% | -19.96% | 1.791 | 1.180 | 7.58% | 2.636 |
| B7_S2_D | 905 | 48.19% | -29.22% | 0.588 | 0.720 | -16.28% | 1.862 |

S0/S1 rows may have shorter cohorts. Never rank them against a 905-day row. See native_coverage.json and native_cohort_controls.csv. B7_S0/S1 unavailable because fractional exposure is not exposed.

## Mechanical ranked checklist and verdicts

No fitted composite score. Checks are listed in preregistered order.

### S0: category 1 — A simple baseline is the best risk-adjusted choice
- FAIL / UNAVAILABLE: 1_valid_comparable_data_and_no_provenance_drift
- FAIL / UNAVAILABLE: 2_positive_2x_cost_return
- PASS: 3_dd_le_60pct_B1
- FAIL / UNAVAILABLE: 4_sharpe_and_calmar_above_B7_and_B4
- FAIL / UNAVAILABLE: 5_all_stresses_positive_edge
- FAIL / UNAVAILABLE: 6_costs_le_25pct_positive_gross
- FAIL / UNAVAILABLE: 7_adjusted_statistical_bar

### S1_full: category 1 — A simple baseline is the best risk-adjusted choice
- FAIL / UNAVAILABLE: 1_valid_comparable_data_and_no_provenance_drift
- FAIL / UNAVAILABLE: 2_positive_2x_cost_return
- PASS: 3_dd_le_60pct_B1
- FAIL / UNAVAILABLE: 4_sharpe_and_calmar_above_B7_and_B4
- FAIL / UNAVAILABLE: 5_all_stresses_positive_edge
- FAIL / UNAVAILABLE: 6_costs_le_25pct_positive_gross
- FAIL / UNAVAILABLE: 7_adjusted_statistical_bar

### S1_L1: category 1 — A simple baseline is the best risk-adjusted choice
- FAIL / UNAVAILABLE: 1_valid_comparable_data_and_no_provenance_drift
- FAIL / UNAVAILABLE: 2_positive_2x_cost_return
- PASS: 3_dd_le_60pct_B1
- FAIL / UNAVAILABLE: 4_sharpe_and_calmar_above_B7_and_B4
- FAIL / UNAVAILABLE: 5_all_stresses_positive_edge
- FAIL / UNAVAILABLE: 6_costs_le_25pct_positive_gross
- FAIL / UNAVAILABLE: 7_adjusted_statistical_bar

### S2_A: category 1 — A simple baseline is the best risk-adjusted choice
- FAIL / UNAVAILABLE: 1_valid_comparable_data_and_no_provenance_drift
- PASS: 2_positive_2x_cost_return
- FAIL / UNAVAILABLE: 3_dd_le_60pct_B1
- FAIL / UNAVAILABLE: 4_sharpe_and_calmar_above_B7_and_B4
- FAIL / UNAVAILABLE: 5_all_stresses_positive_edge
- PASS: 6_costs_le_25pct_positive_gross
- FAIL / UNAVAILABLE: 7_adjusted_statistical_bar

### S2_B: category 1 — A simple baseline is the best risk-adjusted choice
- FAIL / UNAVAILABLE: 1_valid_comparable_data_and_no_provenance_drift
- PASS: 2_positive_2x_cost_return
- FAIL / UNAVAILABLE: 3_dd_le_60pct_B1
- FAIL / UNAVAILABLE: 4_sharpe_and_calmar_above_B7_and_B4
- FAIL / UNAVAILABLE: 5_all_stresses_positive_edge
- PASS: 6_costs_le_25pct_positive_gross
- FAIL / UNAVAILABLE: 7_adjusted_statistical_bar

### S2_C: category 1 — A simple baseline is the best risk-adjusted choice
- FAIL / UNAVAILABLE: 1_valid_comparable_data_and_no_provenance_drift
- PASS: 2_positive_2x_cost_return
- FAIL / UNAVAILABLE: 3_dd_le_60pct_B1
- FAIL / UNAVAILABLE: 4_sharpe_and_calmar_above_B7_and_B4
- FAIL / UNAVAILABLE: 5_all_stresses_positive_edge
- PASS: 6_costs_le_25pct_positive_gross
- FAIL / UNAVAILABLE: 7_adjusted_statistical_bar

### S2_D: category 1 — A simple baseline is the best risk-adjusted choice
- FAIL / UNAVAILABLE: 1_valid_comparable_data_and_no_provenance_drift
- PASS: 2_positive_2x_cost_return
- FAIL / UNAVAILABLE: 3_dd_le_60pct_B1
- FAIL / UNAVAILABLE: 4_sharpe_and_calmar_above_B7_and_B4
- FAIL / UNAVAILABLE: 5_all_stresses_positive_edge
- PASS: 6_costs_le_25pct_positive_gross
- FAIL / UNAVAILABLE: 7_adjusted_statistical_bar

## Least historical loss with some nominal profit

Among fixed positive-return B4/B5 choices, **B4_25** has the smallest modeled daily drawdown, not the best promised future result. Cash has zero modeled price DD and zero nominal return; exchange/USDT/IRT risks remain.

| Candidate vs selected baseline | Return delta (pp) | Change in absolute drawdown (pp) |
|---|---:|---:|
| S2_A | 24.56 | 34.33 |
| S2_B | 70.75 | 29.21 |
| S2_C | 78.93 | 24.31 |
| S2_D | 38.08 | 17.17 |

Positive drawdown delta is WORSE. These are matched 905-day historical comparisons only.

## Coverage, statistics and robustness

See coverage.json (raw timestamp grids and excluded short segments); metrics.csv/json (pooled/segment); bootstrap.json and bootstrap_segment.json (raw/adjusted 95% intervals, 10/20/40-day sensitivity); rolling_windows.csv/rolling_summary.json; start_dates.csv/start_summary.json; monte_carlo.csv; timing_null.json; record_length.json; regimes.csv/episodes.csv; robustness.csv; yearly.csv; archived_parameter_neighborhood.csv.
Worst-month labels mean fixed 21/63/126/365 evaluated days, NOT exact calendar-month holding periods. Short segment tails cannot yield 365-day windows. Regime runs >=20 days are dependence proxies, not independent trials. Low episode counts and repeated data use defeat strong inference.
No claim survives all checks; unavailable native stress tests remain failures of evidence. B7 retrospective exposure fitting uses future sample exposure and is not an investable forward signal. Prefunded DCA knows its selected investment horizon; no external contributions are added.

## Reliability, security, IRT and forward

See the separate weaknesses-first operational_report.md, reliability.json, security.json, public_probes.json and FORWARD_FRAMEWORK.md. Public telemetry is a short sample, not an SLA. Real Bale delivery, actual laptop suspend, OS scheduling, withdrawal/counterparty risks and all possible LIVE bypasses are not certified.
The independent forward framework tracks A/D and fixed baselines. Clock conflicts can allow refusal/warmup smoke only. It cannot manufacture post-registration days; 3/6-month PASS only permits continued observation, never live funds.

## Reproduce (fresh output directories only)

```powershell
.\.venv\Scripts\python.exe -m backtest.final_audit --snapshot reports/final_audit/inputs --output reports/final_audit/reproduction_001
.\.venv\Scripts\python.exe -m app.forward_shadow --mode shadow --root reports/final_audit/forward_new --max-seconds 45
.\.venv\Scripts\python.exe -m app.forward_report --root reports/final_audit/forward_new --output reports/final_audit/weekly_new
```

No performance promises. No order placement or cancellation is added by this audit.
