# Strategy V3 — frozen research protocol (2026-11-20)

This protocol is frozen before any V3 return simulation. No strategy or parameter selection, optimization,
walk-forward, promotion or additional candidates. PAPER is opt-in only, default disabled. LIVE is blocked.

## Candidates

- **A — TrendTiming (BTC/USDT):** one EMA200 vote. Enter 100% above `EMA * 1.02`, exit to USDT below
  `EMA * 0.98`; equalities and the intervening band retain the prior vote. Initial state is off.
- **B — EnsembleTiming (BTC/USDT):** independent identical hysteresis on EMA100, EMA150, EMA200 and
  EMA250. Target exposure is the share of votes on. Act only if the target changes by at least 25 percentage
  points from the last accepted target; market drift alone never triggers a trade.
- **C — Volatility-scaled B (BTC/USDT):** multiply B's target by `min(1, 0.40 / realized_vol)`. Realized
  volatility is the sample standard deviation of the last 30 closed simple close-to-close returns, times
  `sqrt(365)`. Zero realized vol has scale 1; uninitialized features have target 0. Same 25pp target-change rule.
- **D — BTC and ETH C:** apply C separately to BTC/USDT and ETH/USDT, each with half of the same ex-ante
  risk budget (0.50 sleeve cap and 40% volatility target within each sleeve). This targets equal standalone
  risk when fully signaled and uncapped, not exact covariance risk parity; cash from one sleeve is not
  assigned to the other. Total target <=100%. The 25pp trigger applies to the sum of absolute changes in
  the two risky weights, not to cash or passive drift. Sell reductions before funding increases.

EMA uses `ewm(adjust=False, min_periods=length)` initialized from the first raw close in each segment;
votes update throughout warmup. A acts on every vote change. B–D start each account with last reference
target zero; when a threshold is met, accept the new vector. Only the immediately preceding closed daily
candle can generate orders; evaluate at candle close, trade the next raw open (not the signal close).
Long-only spot, no leverage, yield, shorting, or cash interest. USDT is the unit of account.

## Data and evaluation windows

Use complete closed daily candles in the existing BTC/ETH public cache, plus public pages if accessible.
Keep history evidence and new downloads separate from pre-existing databases. Inspect actual raw UDF JSON
`v` versus cache and parser on older/recent BTC and ETH windows; report unavailable checks honestly. Missing
days and DST offset changes delimit segments: use jointly aligned exact timestamps 86,400 seconds apart,
including older raw grids when internally continuous. Do not repair, infer, relabel or bridge any candle.
Use all common segments with more than 300 inputs; 300 warmup candles each, first trade at index 300.
Use a shared calendar for A–D and the daily baselines. List dates/counts of all raw/common segments and
reasons for exclusions, including otherwise available single-asset history. The current PAPER grid is
73800 seconds (20:30 UTC); past raw phase analysis uses each segment's native grid.

Start independently in cash at each eligible segment; liquidation at the last known close is a disclosed
boundary convention (with costs, no price bridging), then concatenate net daily returns without imputing
skipped periods. Carry the compounded equity high-water across independent segment returns for pooled DD
and also show per-segment results. Annualization and drawdown duration use evaluated days (calendar gaps
not charged); duration in evaluated days; CAGR uses 365 days. Final 25% = final `ceil(N/4)` evaluated
observations, in chronological order; restart cash/risk at its first open and at gaps, retain earlier
continuous candles for features; no selection on any sample. Three legacy 4h warmup requirements apply
only to the legacy baseline (unchanged configured warmup, actual 4h alignment, gap-free slice); if exact
coverage is unavailable, disclose excluded intervals and do not pretend the comparator is fully matched.

## Costs and baseline construction

Initial 100 USDT. Historical execution is **price-only**: fixed adverse slippage 0.15% per side at the
open (boundary liquidations at close) plus quote fee equal to the greater of configured 0.25% and the
largest tier in the publicly observed Nobitex USDT taker fee schedule. Use a prior recorded public
observation if endpoint is temporarily unavailable, label which observation, and snapshot the inputs.
No extra historical spread (the fixed slippage models execution friction); baseline round trip is about
0.80% at 0.25% fee. Fee/slippage both multiply at 2x and 3x. No OHLC volume/depth limit or assumed historical
venue precision for daily price-only research; fractional units, fee-inclusive cash and exposure caps,
no fill beyond available cash. Target dollar allocations are fractions of pre-trade equity at open;
sell first, scale requested buys pro rata down for fee-inclusive cash. Record explicit fee plus adverse
price difference as total cost; gross profit for criterion 6 is terminal net profit plus explicit costs,
not the sum of winning trades. Turnover is total absolute reference notional divided by average equity,
and trade count is executed legs; round trips are transitions from invested back to flat per symbol,
including sample-end closeout (no double count of top-ups/partial reductions).

1. BTC buy-and-hold (buy once at each segment start, then drift).
2. BTC+ETH equal-weight buy-and-hold (50/50 at each segment start, then drift).
3. Matched exposure per candidate: same assets, equal split of the risky budget, USDT remainder. A
   constant target risky weight is rebalanced at sample start and the first available open of each new
   UTC calendar month; otherwise drift. Fit one scalar on the corresponding candidate's average
   same-day post-fill **open-mark** risky equity fraction, including cash days. Use deterministic
   bisection (32 iterations) on [0,1] for the simulated baseline's realized average to within 0.01pp or
   report boundary residual if infeasible. Compute separately on full, holdout and per-segment samples,
   as an ex-post diagnostic control, not a deployable or time-travel strategy. Time invested = fraction
   of days with nonzero mark exposure; report average exposure separately.
4. Unchanged legacy BTC 4h rules/fill model with the same nominal fee/slippage, configured warmup/risk
   and volume-independent legacy sizing/precision. Keep original 4h DD; other comparable metrics use
   daily-sampled equity. Flag any additional unavailable legacy metrics or dates.

Corresponding buy-and-hold for A–C = BTC; for D = equal BTC+ETH. Report compounded return, CAGR, max DD,
Calmar, annualized daily Sharpe/Sortino (zero cash rate; sample volatility; downside deviation over all
days), worst rolling 365 evaluated daily returns **within a segment** (undefined if none), longest
drawdown, exposure/time invested, executed legs, round trips, costs and turnover. Undefined ratios fail
if required. Major phases are maximal >=90 evaluated-day runs of the prior-close BTC A vote ON (up)
or OFF (down), without joining across gaps. Report all phases and counts, pooled up/down days and the
last 365 calendar days through the final close, with actual strategy state (no ex-post return filtering).
Report phase returns and average exposure; phase DD uses an independent phase-start high-water.
Count candidate contiguous invested/exposure episodes separately from BTC regime runs; neither is an
assertion of statistical independence.

## Robustness, timing null, acceptance

Change one parameter at a time; never promote a variant. Robustness requires both -20% and +20% on
every applicable individual EMA length, hysteresis, volatility target and rebalance threshold (keep
every vote, including when perturbation duplicates another length; periods rounded half-up). Exploratory
grid: individual EMA lengths +/-10%; all EMA lengths jointly at factors 0.8/0.9/1/1.1/1.2;
hysteresis 0/1/2/3/4%; vol target 30/35/40/45/50%; threshold 10/15/20/25/30/35/40pp. Numeric plateau
label: all single-parameter +/-20% cases must pass criterion 5 and >=80% of all unique non-base grid
cases must have positive return and DD <=75% of corresponding buy-and-hold DD; report metric ranges and
failures regardless. A has no rebalance threshold; A/B have no vol target. The vol window is fixed, not
an optimization axis. Show base and stress results.

Timing diagnostic: 999 seeded (`20261120`) independent uniform cyclic shifts per contiguous segment of
each candidate's joint post-open weights and proportional cost drag (same risky exposure and preserved
blocks/turnover structure modulo circular seam), relative to the actual day returns. For the exact
unshifted reconstruction use open-to-next-open risky returns, last day open-to-close, open cost charged
before the return and the observed terminal liquidation cost kept at the fixed terminal boundary.
Report the fraction matching/exceeding actual Calmar and net return, with no significance claim.
This random-entry timing surrogate is not an executable backtest or evidence that adjacent trends
are independent; with ~10–20 independent trends no claim of statistical significance is justified.

Each candidate, no exceptions:

1. **PASS** iff net return >0 at 2x costs.
2. **PASS** iff absolute max DD <=60% of corresponding buy-and-hold absolute max DD.
3. **PASS** iff both Calmar and Sharpe strictly exceed its full matched-exposure control.
4. **PASS** iff holdout net return >=0 and absolute DD <= its holdout matched-exposure control DD.
5. **PASS** iff all applicable one-at-a-time +/-20% runs retain positive net return and absolute DD
   <=75% of the corresponding base-cost buy-and-hold DD.
6. **PASS** iff gross profit >0 and total costs <=25% of gross profit.
7. **PASS** iff worst 365-day return strictly exceeds buy-and-hold's worst 365-day return.

Any failure => NOT VALIDATED / disabled; if none pass recommend simple monthly DCA/hold as a comparison
or only continued forward PAPER. Even passing never enables a candidate or authorizes LIVE.

## PAPER deployment boundary

Default remains off; explicit PAPER flag chooses A by default (fixed simplicity choice, not ranked by
results), or B/C/D manually. Use candidate-specific databases, record protocol SHA256 and first forward
startup UTC, and keep existing state/locks. PAPER uses the same causal targets/threshold and verified
daily alignment, real fresh public book depth/minimums, maximum configured capital, existing reconciliation
and KILL. It additionally retains the existing account risk ladder, daily-loss/cooldown and typed-resume
guards; these may block or scale increases, not target reductions. They are operational safety overlays,
not part of the pure timing backtest; actual fills and realized exposures can differ. No stale orders
on startup/wake, no intraday discretionary timing, no use of secrets. No stop indicator is added to the
candidates. A missed signal does not get a retroactive fill. Software-only exposure management needs
connectivity; no guarantee of capital preservation.
