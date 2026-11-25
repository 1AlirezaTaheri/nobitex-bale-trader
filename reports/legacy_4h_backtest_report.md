# Backtest report — BTC/USDT / 4h

**Verdict:** Strategy outperformed buy-and-hold on this sample. TOO FEW TRADES for meaningful statistical conclusions.

Evaluation UTC: 2025-10-09 20:30:00+00:00 to 2026-11-20 08:30:00+00:00. Evaluation bars: 2439; excluded warmup: 602.
Fees each side: 0.25%; slippage each side: 0.15%. Risk-blocked bars: 5.

| Measure | Strategy | Buy and hold |
|---|---:|---:|
| Total return | -0.23% | -49.22% |
| CAGR | -0.21% | -45.60% |
| Max drawdown | -3.02% | -51.96% |
| Sharpe | -0.0420 | -1.2553 |
| Sortino | -0.0873 | -1.7126 |

Trades: 8; win rate: 37.50%; profit factor: 0.9241.
Average win / loss in USDT: 0.9521 / -0.6182.
Risk-free rate is assumed zero. Crypto annualization uses 365.25 days. Undefined ratios are not zeroes.

## Method and weaknesses

Signals use closed bars; fills use the next bar open. Existing gap stops precede open-time exits;
the entry-bar initial stop can execute within that bar. Trailing stops calculated from a completed
bar only activate for the following bar. Fees and slippage apply on both sides, including the benchmark.
Daily loss, drawdown latches, cooldown, quantity steps, and capped position sizing use the same risk code
as the PAPER runner. Drawdown latches persist for the entire simulated account (they do not silently reset).

Candles cannot reveal order queues, contemporaneous spread, intrabar stop latency, or execution depth.
The PAPER runner can reject depth-limited fills that the historical open model would accept. Software
stops require the laptop to be online; historical intrabar stop simulation is more responsive than polling.
Constant fees/slippage and present-day symbol rules are approximations, not historical venue guarantees.
Past public candles may be revised by the venue. Missing candles are not invented. Forced end-of-test
liquidation is a reporting convention. Short-period CAGR and annualized ratios may be misleading.
Parameter grids and walk-forward selection can overfit; out-of-sample results are not a guarantee.

No profitability is promised. Thin liquidity, spreads/fees, exchange counterparty risk, internet failures,
API changes, and laptop sleep/power/downtime can cause substantial loss. This is not financial advice.

## Provenance and holdout

Public Nobitex candles cached in data/candles.db; no synthetic substitutions; explicitly selected latest continuous segment, 5882 older bars excluded after a gap. Generated 2026-11-20T10:42:52.157402+00:00.

Exact evaluated input (including warmup): `market_candles.csv`; SHA256 `d0d0c6927691028f99cf7b69cb7bdb900487b12a7a50b84db47cf1563b3df80b`.

WARNING: This segment omits a historical data gap and all preceding bars. Its results do not describe trading through that outage; segment selection can bias conclusions.

70/30 chronological evaluation split. Train return: -1.39%; holdout return: 1.17%, holdout buy-and-hold: -7.19%, holdout trades: 5.

Holdout has too few trades to support reliability claims.

## Walk-forward and parameter sensitivity

See `walk_forward.csv` and `sensitivity.csv`. Three expanding-window folds select ATR multiple on past training return only, then test on the next disjoint slice. Each fold restarts cash/risk state: fold returns are NOT a single continuous equity curve. The nine full-sample sensitivity combinations are descriptive, not independent confirmations. The fixed holdout uses no grid-selected parameters.

- Fold 1: selected ATR=3.0, test=-0.90%, benchmark=-17.21%, trades=2.
- Fold 2: selected ATR=2.0, test=1.25%, benchmark=19.18%, trades=3.
- Fold 3: selected ATR=3.0, test=0.18%, benchmark=-19.99%, trades=2.
