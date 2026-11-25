# Final adversarial audit — delivery record

## Weaknesses, provenance and contamination FIRST

1. **No clean historical holdout remains.** Legacy, LayeredPortfolio, V3 A–D, ablations and grids
   repeatedly reused this history. Old holdout results are descriptive, not independent OOS evidence.
2. The old audit manifest does not authenticate the current protocol. The earlier document was not
   inspected before writing; its absence is unproved. The original manifest is preserved. Amendments
   001/002 disclose provenance/method gaps; amendment 003 discloses post-results reporting fixes.
3. The trial inventory contains **262 archived rows +25 audit series, M=287**. These are correlated
   configuration rows, not 287 independent experiments; unlogged human trials are unknowable.
   With 999 add-one draws, minimum adjusted tail is **0.287**, so adjusted significance cannot pass.
   Increasing simulations after seeing results was not used to rescue anything.
4. Native S0/S1 and daily price-only baselines do not have identical fills, depth, precision, stops
   or sizing. Exact native exposure/costs/B7, native fresh-start sensitivity, executable same-turnover
   random schedules and full native crash/delay stresses are **unavailable**, not passes.
5. Historical prices do not establish executable liquidity or intraday drawdown. Survivor selection,
   zero reported volumes, omitted short segments, UTC-grid changes and genuine gaps limit evidence.
   No interpolation, synthetic prices, missing-day trades or gap-bridged returns were created.
6. Bootstrap sign tails are uncentered descriptive resampling tails, **not exact null-test p-values**.
   Extreme adjusted percentile intervals lack adequate simulation resolution. Monte Carlo frequencies
   are resampled-history diagnostics, not forecasts or loss guarantees.
7. The developer-context date is **2026-11-25**, but the SHADOW smoke measured execution UTC
   **2026-11-24T23:06:11.096013+00:00**. Activation before **2026-11-25T00:00:00+00:00** was correctly
   refused with exit 2. **Zero genuine forward snapshots** exist at delivery; weekly results are PENDING.
8. No LIVE order/cancellation was sent. No strategy was retuned or enabled. Software tests, short public
   probes, hash consistency and replay do not certify profitability, security, uptime or execution.

## Outcome

**All seven strategy variants remain category 1 / NOT VALIDATED.** Category 1 means the fixed
checklist did not establish enough evidence over simple controls; it is not personalized advice.
Neither category 2 nor category 3 was awarded. A/D are tracked in the independent SHADOW framework
only because the requested forward experiment includes them, not because they passed a promotion gate.

Among the **registered positive-return B4/B5 constant-mix choices**, B4_25 had the smallest daily
historical drawdown: **+36.27% net return, −7.99% MaxDD, 136.266 USDT final** from 100 USDT, costs
0.634 USDT. It targets 25% BTC /75% USDT, checks monthly, and trades only at a 5pp absolute drift.
Cash B6 has zero modeled price DD and zero nominal profit, but still has custody/USDT/FX risks.

S0 has a smaller observed daily DD (−4.07%) than B4_25, but only +4.32% return and **−1.68% at 2x
costs**; its execution/risk model differs and its exact exposure control is unavailable. Therefore
B4_25 is not called a universal winner or the minimum-DD positive strategy across incompatible models.

## Coverage and accounting

- BTC/ETH share 2,750 raw timestamps; seven segments cannot supply 300 warmup candles plus evaluation.
  Eligible inputs are 1,000 and 505 candles, giving **700 +205 =905 evaluated days**. See
  `results/coverage.json` for every raw segment/grid and unmatched timestamp.
- S0 covers both evaluated segments (28 completed round trips). S1 full/L1 cover **700 days only**;
  segment 8 lacks the complete frozen five-asset timestamp set. Its prior 203-day supplemental study
  is preserved elsewhere, not silently substituted into this cohort.
- S1 full/L1 have zero fills, with 232/163 `entry modeled depth` rejections. Zero DD on zero trades
  is not demonstrated risk control. Native-cohort baseline reruns are `results/native_cohort_controls.csv`.
- Daily price-only fee is 0.25% and adverse slippage 0.15% **per side**, including historical endpoint
  liquidation. Holdings reset at gaps; equity/high-water compound, but no gap returns are inferred.
  CAGR and durations use evaluated days, not elapsed calendar years. Native models are unchanged.
- Every account begins with 100 USDT. Historical B3 is prefunded across observed UTC month buckets;
  no external deposits. Forward B3 uses 100/12 USDT monthly until cash is exhausted. B4/B5 use a
  5pp monthly band. Historical B7 fits aggregate sample exposure in 32 bisections: diagnostic hindsight,
  not a future-executable signal. Forward B7 instead uses lagged observed exposure only.

## All available series: net historical comparison

MaxDD is negative. N/A means undefined/unavailable, never an assumed zero. All but S1 cover 905 days;
S1 full/L1 cover 700. Native S0/S1 are not execution-identical to daily baselines.

| Series | Description | Days | Net return | MaxDD | Calmar | Sharpe | Worst 365d | Costs USDT |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| S0 | Legacy BTC 4h, native | 905 | +4.32% | −4.07% | 0.423 | 0.483 | −1.94% | N/A |
| S1_full | Full portfolio, native | 700 | 0.00% | 0.00% | N/A | N/A | 0.00% | N/A |
| S1_L1 | Trend layer only, native | 700 | 0.00% | 0.00% | N/A | N/A | 0.00% | N/A |
| S2_A | Frozen V3 A | 905 | +60.83% | −42.32% | 0.499 | 0.691 | −32.23% | 12.073 |
| S2_B | Frozen V3 B | 905 | +107.02% | −37.19% | 0.917 | 0.984 | −18.65% | 12.397 |
| S2_C | Frozen V3 C | 905 | +115.20% | −32.30% | 1.121 | 1.096 | −13.01% | 9.651 |
| S2_D | Frozen V3 D | 905 | +74.35% | −25.15% | 0.999 | 0.893 | −10.22% | 6.967 |
| B1 | BTC buy/hold | 905 | +180.12% | −28.95% | 1.779 | 1.162 | +7.32% | 4.296 |
| B2 | BTC/ETH equal buy/hold | 905 | +87.59% | −41.37% | 0.698 | 0.770 | −22.96% | 3.068 |
| B3 | BTC prefunded DCA | 905 | +69.06% | −27.83% | 0.848 | 0.863 | +6.27% | 2.667 |
| B4_25 | 25% BTC constant mix | 905 | +36.27% | −7.99% | 1.664 | 1.165 | +3.97% | 0.634 |
| B4_50 | 50% BTC constant mix | 905 | +81.36% | −15.37% | 1.766 | 1.184 | +6.42% | 1.606 |
| B4_75 | 75% BTC constant mix | 905 | +126.38% | −22.47% | 1.737 | 1.158 | +7.49% | 2.704 |
| B5_25 | 25% BTC/ETH risky mix | 905 | +22.60% | −13.75% | 0.623 | 0.729 | −7.27% | 0.645 |
| B5_50 | 50% BTC/ETH risky mix | 905 | +43.84% | −26.16% | 0.604 | 0.720 | −15.07% | 1.400 |
| B5_75 | 75% BTC/ETH risky mix | 905 | +65.46% | −34.59% | 0.651 | 0.741 | −19.47% | 2.108 |
| B6 | Cash, zero yield | 905 | 0.00% | 0.00% | N/A | N/A | 0.00% | 0.000 |
| B7_S2_A | Matched exposure A | 905 | +124.27% | −21.50% | 1.791 | 1.177 | +7.72% | 2.906 |
| B7_S2_B | Matched exposure B | 905 | +125.73% | −21.70% | 1.791 | 1.176 | +7.74% | 2.942 |
| B7_S2_C | Matched exposure C | 905 | +113.35% | −19.96% | 1.791 | 1.180 | +7.58% | 2.636 |
| B7_S2_D | Matched BTC/ETH exposure D | 905 | +48.19% | −29.22% | 0.588 | 0.720 | −16.28% | 1.862 |
| B8 | BTC above SMA200, else cash | 905 | +96.72% | −30.55% | 1.027 | 0.916 | −16.00% | 16.584 |
| B7_S0 | Native exposure unavailable | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| B7_S1_full | Native exposure unavailable | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| B7_S1_L1 | Native exposure unavailable | N/A | N/A | N/A | N/A | N/A | N/A | N/A |

All extended metrics (CAGR, volatility, Sortino, Ulcer, CVaR, DD duration, underwater/invested time,
exposure, trips/legs, turnover, costs/gross and final capital) are in `results/metrics.csv` and `.json`,
both pooled and per segment. Worst 21/63/126/365 days are fixed evaluated-day windows, not calendar months.

## Statistical uncertainty

Moving blocks never cross input segments; seed 20261125, 999 draws, primary block20, sensitivities
10/40. The following are **unadjusted 95% descriptive percentile intervals**, not predictive ranges.
Complete raw/adjusted metrics and paired differences at every block size are in
`statistical_intervals.csv`, `.json` and `.md` (270 rows), and per-segment in `results/bootstrap_segment.json`.

| Series | Sharpe 95% | Calmar 95% | MaxDD 95% |
|---|---|---|---|
| S0 | [−0.860, 1.630] | [−0.345, 3.040] | [−8.75%, −2.02%] |
| S1_full | N/A | N/A | [0.00%, 0.00%] |
| S1_L1 | N/A | N/A | [0.00%, 0.00%] |
| S2_A | [−0.759, 2.169] | [−0.433, 4.165] | [−73.71%, −24.70%] |
| S2_B | [−0.361, 2.410] | [−0.295, 5.206] | [−64.48%, −21.83%] |
| S2_C | [−0.281, 2.538] | [−0.245, 5.859] | [−58.70%, −19.44%] |
| S2_D | [−0.269, 2.261] | [−0.256, 4.925] | [−53.91%, −16.76%] |
| B1 | [0.034, 2.567] | [−0.144, 7.106] | [−64.27%, −23.55%] |
| B2 | [−0.296, 2.222] | [−0.360, 5.193] | [−75.05%, −28.17%] |
| B3 | [−0.114, 2.325] | [−0.190, 4.781] | [−48.83%, −15.48%] |
| B4_25 | [−0.017, 2.575] | [−0.044, 4.772] | [−22.11%, −6.27%] |
| B4_50 | [0.009, 2.605] | [−0.070, 5.512] | [−39.30%, −12.31%] |
| B4_75 | [0.021, 2.577] | [−0.112, 6.127] | [−53.14%, −18.04%] |
| B5_25 | [−0.419, 2.214] | [−0.249, 3.497] | [−28.27%, −7.72%] |
| B5_50 | [−0.390, 2.203] | [−0.302, 3.968] | [−49.46%, −14.95%] |
| B5_75 | [−0.338, 2.218] | [−0.326, 4.504] | [−64.73%, −21.61%] |
| B6 | N/A | N/A | [0.00%, 0.00%] |
| B7_S2_A | [0.029, 2.594] | [−0.098, 6.046] | [−51.61%, −17.35%] |
| B7_S2_B | [0.029, 2.594] | [−0.099, 6.067] | [−51.99%, −17.51%] |
| B7_S2_C | [0.030, 2.599] | [−0.089, 5.880] | [−48.68%, −16.09%] |
| B7_S2_D | [−0.399, 2.202] | [−0.321, 4.002] | [−53.22%, −16.71%] |
| B8 | [−0.305, 2.369] | [−0.292, 5.338] | [−64.04%, −20.61%] |

Paired difference is strategy minus control, so positive favors the strategy. Closest B4 is chosen
by exposure, not return (A/B/C: B4_75; D: B4_50). These are descriptive sign tails, despite the
legacy JSON key names `p_unadjusted`/`p_bonferroni`. Every adjusted Sharpe/Calmar tail below is 1.000.

| Strategy | Control | Metric | Raw 95% interval | Adjusted interval, resolution-limited | Raw tail | Adjusted tail |
|---|---|---|---|---|---:|---:|
| S2_A | B4 | Sharpe | [−1.277, 0.137] | [−2.246, 0.563] | 0.938 | 1.000 |
| S2_A | B4 | Calmar | [−3.689, 0.483] | [−6.665, 3.018] | 0.917 | 1.000 |
| S2_A | B7 | Sharpe | [−1.311, 0.123] | [−2.305, 0.550] | 0.942 | 1.000 |
| S2_A | B7 | Calmar | [−3.728, 0.490] | [−6.638, 3.046] | 0.918 | 1.000 |
| S2_B | B4 | Sharpe | [−0.829, 0.277] | [−1.435, 0.679] | 0.848 | 1.000 |
| S2_B | B4 | Calmar | [−2.490, 0.981] | [−4.929, 4.892] | 0.801 | 1.000 |
| S2_B | B7 | Sharpe | [−0.858, 0.269] | [−1.494, 0.665] | 0.853 | 1.000 |
| S2_B | B7 | Calmar | [−2.559, 0.981] | [−4.948, 4.928] | 0.803 | 1.000 |
| S2_C | B4 | Sharpe | [−0.700, 0.383] | [−1.163, 0.823] | 0.726 | 1.000 |
| S2_C | B4 | Calmar | [−2.087, 1.259] | [−4.860, 3.419] | 0.721 | 1.000 |
| S2_C | B7 | Sharpe | [−0.730, 0.362] | [−1.223, 0.796] | 0.738 | 1.000 |
| S2_C | B7 | Calmar | [−1.994, 1.391] | [−4.539, 3.613] | 0.728 | 1.000 |
| S2_D | B4 | Sharpe | [−0.958, 0.309] | [−1.463, 0.601] | 0.854 | 1.000 |
| S2_D | B4 | Calmar | [−2.422, 1.224] | [−4.721, 2.929] | 0.779 | 1.000 |
| S2_D | B7 | Sharpe | [−0.550, 0.799] | [−0.931, 1.269] | 0.396 | 1.000 |
| S2_D | B7 | Calmar | [−1.220, 2.327] | [−3.325, 4.885] | 0.356 | 1.000 |

## Rolling, fresh starts, timing null and regimes

- Only the 700-day segment can supply 365-day windows: **336 heavily overlapping windows**, not
  independent trials. A/B/C/D rolling comparisons and distributions are in `results/rolling_summary.json`.
  A has 66.96% positive windows and beats B7 in 1.79%; D has 89.88% positive and beats B7 in 85.42%,
  but beats closest B4 in only 42.86% and B1 in 0%. Window win shares are return comparisons.
- Price-only fresh accounts are rerun at each of 905 eligible start dates with retained causal warmup
  and fixed segment terminal dates. B4_25 start-return min/median/max is **−7.34%/+11.70%/+51.75%**;
  A is −23.54%/−3.04%/+113.85%; D is −17.57%/+5.98%/+107.92%. Varying horizons and very short
  tails bias this diagnostic. Native fresh-start reruns remain unavailable.
- Timing null uses circular observed joint weights/cost drag, **not executable random orders with
  exact turnover**. A/B/C/D Calmar percentiles are 14.21/31.93/42.44/73.37%; none is promoted.
- Regimes use prior closed BTC drawdown and SMA200 slope only; there are **nine >=20-day major
  episode proxies** over both segments. Conditional bull/bear/range concatenations are not tradable
  equity paths or independent episodes. See `results/regimes.csv`, `episodes.csv`, `yearly.csv`.
- HAC-inflated mean-return record-length estimates are rough, not a rigorous minimum Sharpe record
  or prospective power analysis. D vs B7 is about 4,833 raw /22,845 adjusted evaluated days; A/B
  nonpositive excess mean has undefined/infinite requirement. These are not recommendations to wait
  exactly those durations or guarantees of eventual significance.

## Stress and Monte Carlo

| Strategy | 2x-cost return | 3x-cost return | One-day-delay return | Checklist category |
|---|---:|---:|---:|---|
| S0 | −1.68% | −5.60% | Unavailable | 1 / NOT VALIDATED |
| S1_full | 0.00% | 0.00% | Unavailable | 1 / NOT VALIDATED |
| S1_L1 | 0.00% | 0.00% | Unavailable | 1 / NOT VALIDATED |
| S2_A | +47.28% | +34.87% | +72.65% | 1 / NOT VALIDATED |
| S2_B | +91.81% | +77.72% | +103.15% | 1 / NOT VALIDATED |
| S2_C | +103.20% | +91.86% | +109.03% | 1 / NOT VALIDATED |
| S2_D | +66.57% | +59.11% | +63.00% | 1 / NOT VALIDATED |

Positive return at higher costs does not establish excess risk-adjusted performance. D improves on its
retrospective B7 but not closest B4 on both ratios; A/B/C also fail B7. All fail the combined criteria.
Crash slippage stress uses ex-post BTC close/open losses below −8%, not a causal signal; unchanged
returns in this stress do not prove crash safety. Leave-one-asset-out preserves the omitted sleeve
as cash. Dropping 20-day gap edges is an omission diagnostic only, not edited tradable history.
Original archived parameter neighborhoods are copied without selecting a new winner.

999 resampled 365-day paths, block20; percentages below are **historical simulation frequencies**:

| Series | P(MaxDD >15%) | P(>25%) | P(>40%) |
|---|---:|---:|---:|
| S2_A | 97.10% | 73.37% | 27.73% |
| S2_B | 94.89% | 59.96% | 14.51% |
| S2_C | 90.59% | 47.75% | 8.11% |
| S2_D | 83.88% | 33.13% | 3.40% |
| B1 | 98.00% | 68.17% | 17.82% |
| B4_25 | 6.21% | 0.00% | 0.00% |

All series, including native S0/S1 and cash, are in `results/monte_carlo.csv`. Zero events in 999
draws are not zero real risk; flat S1 produces degenerate zero-risk simulations of a no-trade input.

## Least-loss comparison in plain language

Relative to B4_25 over the same 905 daily observations:

| Candidate | Extra net return, percentage points | Extra absolute daily DD, pp (worse) |
|---|---:|---:|
| A | +24.56 | +34.33 |
| B | +70.75 | +29.21 |
| C | +78.93 | +24.31 |
| D | +38.08 | +17.17 |

The extra historical return came with substantially more drawdown. None satisfies the fixed evidence
bar. B4_25 is a sample-relative simple comparison, not a guarantee of low future losses or positive profit.

## Deliverables and operating instructions

- `results/`: original 30 artifacts. `replay/`: original byte-identical replay, `byte_replay_check.json`.
- `results_verified/`, `replay_verified/`: **incomplete** 300-second timeout attempts, four preliminary
  files each. Preserved with logs; not certified output. No `byte_replay_verified.json` success is claimed.
- `results_verified_002/`, `replay_verified_002/`: fresh color-corrected recovery with 1,800-second
  subprocess bounds. **Both completed with exit 0** in 357.681/355.479 seconds. All **30 artifacts
  are byte-identical** between them; all **24 non-chart artifacts match the original**. Only equity/DD
  PNGs and the resulting hash manifest changed from the original. See `byte_replay_verified_002.json`.
- `v3_actual_input_parity.json`: exact 905-row grids for A–D, daily returns/equity/exposure and 11 aggregate
  fields agree with archived V3 within 1e-9; this is adapter parity, not a new validation sample.
- `operational_report.md`: public telemetry, reliability/security findings, test evidence and limits.
- `FORWARD_FRAMEWORK.md`: isolated SHADOW commands, persistence, weekly reports and 3/6-month rules.
- `weekly_initial/`: zero-observation CLI output with PENDING checkpoints, no invented performance.
- `integrity_after.json`, `source_checksums.json`, `process_audit_final.json`: final preservation/source/process evidence.
- `visual_qa_final.json`: direct inspection of all five corrected charts plus the empty weekly chart;
  no gaps were joined and no forward-data lines were invented.
- Project-root `docs/RISK_REGISTER.md` (relative path `../../docs/RISK_REGISTER.md` from this report's
  directory) tracks unresolved risks; none is closed by a passing local test alone.

Final software evidence: **239 full-suite tests passed**, zero failures/errors/skips; Ruff check,
Ruff format (**66 files**, including the bounded recovery script), compileall and pip check all exit 0
in `quality_checks_final_002.json`. Of the 272 baseline hashes, **270 are unchanged**; the only two
intentional exceptions are the in-progress audit runner/core (`backtest/final_audit.py` and
`backtest/final_audit_core.py`). All frozen legacy sources, configuration, data/cache and old-report
hashes match, including the original V3 protocol and preserved incompatible old audit manifest.
Both portfolio/timing enabled flags remain false. Process inspection at
**2026-11-24T23:21:28.0923802Z** found zero Python/pytest/Ruff processes and no project bot/test/audit
left running. This is a point-in-time local check, not an uptime guarantee or provenance cure.

Use a **fresh** output name on every replay/report; do not overwrite prior evidence:

```powershell
.\.venv\Scripts\python.exe -m backtest.final_audit --snapshot reports/final_audit/inputs --output reports/final_audit/reproduction_001
.\.venv\Scripts\python.exe -m app.forward_shadow --mode shadow --root reports/final_audit/forward --max-seconds 45
.\.venv\Scripts\python.exe -m app.forward_report --root reports/final_audit/forward --output reports/final_audit/weekly_001
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m compileall -q app backtest data exchange execution indicators notify risk strategy tests
.\.venv\Scripts\python.exe -m pip check
```

Leave the clock gate, all LIVE blockers and both disabled strategy flags intact. No bot is intended
to remain running after this delivery. Genuine forward evidence requires future actually observed days.
