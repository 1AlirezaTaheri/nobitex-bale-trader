# Final audit preregistration — 2026-11-25

## Weaknesses and data contamination first

The same history has already informed the legacy 4h trend family, LayeredPortfolio full/three
ablations and its sensitivity grids, and V3 A–D and their grids. The former holdouts are contaminated
by repeated human inspection. All historical findings are hypothesis-generating, never clean OOS.
Daily prices cannot certify execution or tail risk. No strategy or baseline is a capital guarantee.

This is a new audit, not an amendment to V3. Preserve V3 SHA256
`6f26ccabb14fa92b477a94b873f3309a0eb9b30a3d873118def5fa81ec3489af`.
Do not change strategy code/parameters, existing flags, databases, caches or research reports.
New evidence goes only under reports/final_audit. Required documentation updates are allowed.
All execution is PAPER/shadow only, public data only, no exchange placement/cancellation.

## Trial count and statistical methods

Before examining new returns, use a conservative floor of **250 historical research configurations**
(approximately: legacy >=12 including base/sensitivity/walk-forward selection; portfolio >=50
including full, ablations, sensitivity and perturbations; V3 >=160 including base, neighborhoods,
grids and cost stresses). Count actual archived configuration rows during inventory; use
M=max(250, archived rows plus audit strategy/baseline series). Correlated configurations are not
independent trials: Bonferroni remains a conservative disclosure, not a correction for researcher
judgment. Report inventory, M, raw and adjusted one-sided bootstrap tail probabilities for Sharpe
and Calmar differences vs B7 and the closest B4; p_adjusted=min(1,M*p_raw). Statistical bar: adjusted
p<0.05 and multiplicity-adjusted lower confidence bound >0 for both differences. Empirical tails
use add-one smoothing. Insufficient simulation resolution cannot pass the bar.

Moving-block bootstrap: seed 20261125, 999 draws, contiguous blocks of 20 evaluated days,
sensitivity 10 and 40, never resample a block across input segment boundaries. Paired strategy/control
draws use identical indices. Report 95% percentile intervals and Bonferroni quantiles for Sharpe,
Calmar and maximum drawdown and paired differences. Approximate minimum record length uses
one-sided normal threshold 1.645 (and inverse normal 1-0.05/M) times a 20-day dependence inflation
estimated from daily variance/autocovariance; zero/nonpositive edge => undefined/infinite. This is
an approximation, not a proof of independence or a prospective power calculation.

Timing null: 999 seeded within-segment cyclic shifts of joint observed post-fill risky weights and
proportional cost drag against actual open returns; fixed terminal liquidation drag. Preserve exposure
distribution and circular trading blocks, not executable orders at seams. S0/S1 lack exact open weights:
declare unavailable rather than invent them. Monte Carlo: 999 within-segment block-bootstrap
365-day paths, report P(max DD >15%,25%,40%) for every series. Never call these forecasts.

## Universe, data, accounting and costs

Existing unchanged strategies: S0 legacy BTC 4h; S1 LayeredPortfolio full and Layer 1 alone;
S2 V3 A/B/C/D. Use exact shared BTC/ETH daily segments with >300 inputs and existing V3 snapshot.
Portfolio requires all its frozen assets and 300 warmup rows; S0 requires configured 4h warmup and
exact grid. If unavailable on the common interval, label partial/unavailable, never fill gaps or
pretend unmatched models/dates are comparable. Keep original native execution models for S0/S1;
their economic comparability is limited. Pooled series reset holdings at gaps, carry compounded
equity and high-water, count evaluated days, not missing calendar time. Keep per-segment metrics.

Baselines at next raw daily open: B1 BTC buy/hold; B2 BTC/ETH 50/50 buy/hold; B3 BTC monthly DCA;
B4 BTC/USDT 25/50/75%; B5 equal BTC/ETH risky sleeves at same total exposures; B6 cash;
B7 independently fitted same-asset constant-mix exposure control for each strategy, 32 bisections;
B8 BTC close>SMA200, otherwise cash, no band/filter. B4/B5 rebalance at segment start and first
available UTC monthly open only when absolute risky exposure drift >=0.05; B7 monthly without band.
Choose matching B4 by nearest total target exposure (ties lower exposure), not highest return.
B3 has a fixed, prefunded 100-USDT account: per segment allocate the starting cash equally across
the number of observed UTC month buckets; buy that fixed amount at each first observed monthly
open; unused funds remain cash. No external contributions, so returns are comparable. No DCA
budget borrowed across gaps. Forward B3 uses fixed 100/12 USDT per month until cash exhausted,
no injection or extra purchases. All accounts start 100 USDT and liquidate with costs at known
segment endpoints for historical research only. Cash has zero yield.

Daily price-only cost model: fee=max(0.0025, archived public max USDT taker fee), adverse slippage
0.0015 per side, including liquidation; fee-inclusive cash, sell before buys, fractional units, no
historical depth fabricated. S0/S1 retain native precision/fill/risk/depth assumptions and disclose
them. Stress both costs 2x/3x. Crash widening: 3x slippage on dates BTC close/open-1 < -0.08;
this is an ex-post friction stress, never a causal signal. One-day delay: execute the frozen
target one additional raw day later. No parameter optimization.

## Metrics, rolling and robustness

For each series pooled/per segment: net total return, 365-evaluated-day CAGR, sample annualized
volatility, max daily DD, Calmar, annualized Sharpe/Sortino (zero cash rate), Ulcer index, mean
worst ceil(5%N) daily returns (CVaR), worst 21/63/126/365 consecutive evaluated-day returns
within segment, DD duration, underwater fraction, invested fraction, average exposure, round
trips, legs, turnover, explicit costs, costs/gross profit (gross=net profit+cost), final USDT.
Undefined values remain null, never zero substituted. Native missing execution statistics remain null.
Rolling 365-day return/DD distributions within segment; strategy win shares vs B1/B3/nearest B4/B7;
positive-window share. Start-date sensitivity for every evaluated start date uses a fresh cash
account/retained causal warmup, terminal segment close; no hindsight target selection. Report short
holding-period bias. S0/S1 fresh-start reruns where feasible, otherwise flag unavailable explicitly.

Reuse archived sensitivity rows without choosing winners. Costs 1x/2x/3x; crash widening; delayed
execution; calendar-year attribution; leave-one-asset-out (D sleeves held at original half budget,
omitted sleeve cash, B2/B5 likewise; full portfolio removal is diagnostic only, preserve all rules);
gap neighborhoods: drop first/last 20 evaluation returns of each segment and recompute metrics,
explicitly an omission diagnostic, not tradable edited history; 1000 vs 505 input segments. An edge
survives only if net return>0 and Sharpe/Calmar differences vs B7>0 in every applicable stress.

Regimes use BTC prior closed candle only. At signal t: running peak from segment first close;
DD=close/peak-1; SMA200 slope=SMA200[t]/SMA200[t-20]-1. Bull if DD>-0.20 and slope>0;
bear if DD<=-0.20 and slope<0; range otherwise. Uninitialized => unknown. Contiguous runs are
episodes, never statistical independence; effective major episodes = maximal runs >=20 days,
per segment. Report days, episodes, regime return/DD, exposure, costs, and concentration.

## Iran exploratory check

Probe public USDTIRT and BTCIRT history only, bounded timeout and retries, keep raw responses.
Only use genuine overlapping timestamps; quote-unit verification (IRT vs IRR) is mandatory.
If verified complete daily overlap exists, translate equity using observed USDT/IRT and disclose
rank changes; no FX interpolation or implied FX from BTC crosses. Partial/no access => coverage
only, exploratory analysis unavailable. Counterparty/withdrawal, regulatory, offline software stops,
API outages, thin books and survivor-universe risks remain unmodeled.

## Reliability/security measurements

Full pytest/Ruff/compileall/pip check. Local-copy fault drills: terminate mid-cycle/mid-order,
reconcile restart, mock timeout/stale/skew, suspend/resume simulation, locked/corrupt SQLite refusal,
duplicate lock, KILL. Native OS suspend not executed => unverified. Never kill unrelated processes.
Bounded public-only smoke <=45 seconds of loop activity, <=120 seconds outer process deadline;
collect request latency/status/timeouts/retries, ready time, CPU/memory and file growth. Monthly
growth projections explicitly linear and very uncertain. Security scan returns filenames/counts only,
never secret values; inspect env ignore/redaction/command-whitelist/LIVE-refusal tests. Offline
vulnerability scanner absent or advisory DB unavailable => not run, never install/download silently.

## Forward shadow rules and checkpoints

Fresh isolated database/cache under reports/final_audit/forward, no existing storage writes.
Track A,D,B1,B3,B4_25/50/75,B7_A,B7_D,B8 on identical observed daily public opens/closes and costs.
Forward B7 is a causal diagnostic: use lagged expanding observed exposure, monthly rebalance;
it cannot match an unknown future average and is explicitly not retrospective B7.
All existing A/D parameters/features remain frozen; initialize from genuine contiguous 300+
closed warmup candles, no retroactive exposure. First observed eligible daily boundary only after
manifest not-before UTC; no pre-registration returns in forward PnL. New observations are hash-chained
exclusive-create daily JSON snapshots; refuse broken hash chain or conflicting overwrite.
Missed days are enumerated; mark interrupted, do not trade a missed signal. Existing holdings remain
economically exposed during downtime: do not hide a gap by claiming zero loss; record current
marked account separately and exclude unobserved intervals from clean comparable performance.
No checkpoint PASS after an interruption; any rule change/new version restarts a new clock/database.

Review at 3 and 6 calendar months after eligible first observation, respectively >=80 and >=160
actually observed daily intervals, no interruptions, no hash violations. PASS requires strategy
DD <=0.60*B1 DD, net return >= causal B7 return minus 0.02 (two percentage points), gross profit>0,
costs<=0.25*gross profit. Short regimes can flatter any model. PASS only permits continued observation,
never LIVE or meaningful capital; FAIL means remain unvalidated, no tuning. Weekly report prints
equity/exposure/DD/costs/trades, comparisons, hashes, gaps, insufficient-data caveats and checkpoints.

## Mechanical historical decision checklist (Step 9)

Rank checks lexicographically, never a fitted composite: (1) valid comparable data/no protocol drift,
(2) positive 2x-cost return, (3) DD<=60% B1 (D uses corresponding B2 in supplemental V3 check only),
(4) Sharpe AND Calmar >B7 and nearest B4, (5) all applicable stress differences positive,
(6) costs<=25% positive gross profit, (7) adjusted statistical bar above. Category 3 "shows initial
evidence" only if all seven pass. Category 2 "worth forward observation only" if positive 2x-cost
return, better Sharpe/Calmar than B7, costs test and original fixed V3 acceptance all pass except
significance (strict, prevents selective rescue). Otherwise category 1 "a simple baseline is the best
risk-adjusted choice"; this is a sample-relative comparison, not personal financial advice. Cash is
the minimum modeled-price-DD option, but has no positive nominal return and retains counterparty/FX risk.
For minimum-loss/some-profit comparison choose the positive-return B4/B5 with lowest absolute DD
(ties lower exposure), then display candidate return/DD deltas. Never label sample winner guaranteed.

## Freeze and clock integrity

Record manifest UTC from execution clock AND developer-context date 2026-11-25. If they disagree,
disclose the conflict, set forward not-before to the later timestamp/date, and block forward activation
when the execution clock is earlier. A public-price smoke can exercise refusal/warmup but cannot
claim post-registration forward observations. Any methodological change after hash needs a dated
amendment file and prominent final-report flag; the frozen document itself is never rewritten.
