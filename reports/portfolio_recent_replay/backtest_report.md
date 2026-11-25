# LayeredPortfolio — daily Nobitex PAPER research

## Weaknesses first

**NOT VALIDATED — numerical acceptance failed**. Runtime default enabled: `false`.
- Today's universe/precision create survivorship and selection bias. Excluded gaps and older/unmatched bars are not traded through.
- Historical order books are unavailable: each modeled IOC uses the existing depth walk, a fixed half-spread and a one-level capacity of 0.1% of the prior closed day's base volume at default. This is an assumption, not measured historical executable liquidity.
- Zero-volume input bars per asset: `{'BTC/USDT': 0, 'DOGE/USDT': 0, 'ETH/USDT': 0, 'SOL/USDT': 0, 'XRP/USDT': 0}`. Zero-volume prior bars imply zero modeled capacity: no substitution or inferred liquidity. A no-trade run cannot validate the strategy.
- Daily OHLC cannot time stops across assets or capture the intraday equity minimum. Reported drawdown uses daily closes; the ladder also checks opens. Paper stops require connectivity. A rejected exit may remain exposed.
- Walk-forward accounts restart risk and cash, do not compound fold returns, and use only the pre-holdout period. The holdout is not evidence of future safety. Small trade counts make ratios fragile.

## Acceptance (frozen criteria)

- **FAIL** — At least 100 completed trades
- **FAIL** — Positive net return at baseline and 2x costs
- **FAIL** — Positive fixed final-25% holdout return
- **FAIL** — Profit factor greater than 1.30
- **PASS** — Maximum drawdown no worse than 25%
- **PASS** — Calmar better than equal-weight buy and hold
- **FAIL** — Robust to +/-20% perturbations
- **FAIL** — Combined drawdown no worse than worst pure single trading layer

Perturbation passes only when baseline is positive and **all** one-at-a-time and joint +/-20% runs stay positive and retain at least 50% of baseline net return. No rule was changed to pass.

## Coverage and reproducibility

Evaluation UTC: 2026-04-30T20:30:00+00:00 to 2026-11-19T20:30:00+00:00. Final holdout: 51 days from 2026-09-29T20:30:00+00:00.
Common contiguous policy: `latest`, 503 inputs per asset including warmup. Excluded counts: `{'BTC/USDT': 2448, 'DOGE/USDT': 1638, 'ETH/USDT': 2247, 'SOL/USDT': 1054, 'XRP/USDT': 2248}`.
Base costs per side: fee 0.25%, adverse slippage 0.15%, plus modeled half-spread 0.10%.
See `inputs/manifest.json` next to this report's artifacts for raw input CSV SHA256; `reports/universe.md` records raw coverage/gaps. A snapshot can be replayed without API access.

## Ablation and benchmarks

| Run | Return | CAGR | Max DD | Calmar | Sharpe | Sortino | Trades | PF |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| L3 Cash only | 0.00% | 0.00% | 0.00% | N/A | N/A | N/A | 0 | N/A |
| L1 Trend only | 0.43% | 0.77% | -1.70% | 0.452 | 0.236 | 0.350 | 3 | 2.514 |
| L2 Pullback only | -0.86% | -1.54% | -1.06% | -1.445 | -1.456 | -1.539 | 6 | 0.079 |
| L1+L2 (no BTC gate) | 0.08% | 0.15% | -2.27% | 0.066 | 0.059 | 0.086 | 7 | 1.119 |
| Full (L1+L2+BTC) | 0.08% | 0.15% | -2.27% | 0.066 | 0.059 | 0.086 | 7 | 1.119 |
| Full + breadth | -0.52% | -0.93% | -1.93% | -0.484 | -0.277 | -0.383 | 7 | 0.282 |
| Equal weight B&H | -26.40% | -42.39% | -36.88% | -1.149 | -0.894 | -1.292 | 0 | N/A |
| BTC B&H | -19.23% | -31.91% | -29.02% | -1.100 | -0.866 | -1.247 | 0 | N/A |
| Legacy 4h BTC trend | 0.42% | 0.76% | -2.95% | 0.258 | 0.197 | 0.452 | 7 | 1.173 |

Legacy BTC strategy uses its unchanged rules/fill model, 4h drawdown observations and daily-sampled Sharpe/Sortino. Buy-and-hold buys equal weights once, not daily rebalanced, with modeled round-trip costs and fractional units; it does not impose the portfolio's risk or modeled-depth caps.

Pearson correlation of aligned daily net returns of the standalone L1 and L2 sleeves (including cash days): **0.215**.
Layer 3 alone is all cash; it has no trade/exit rule. Sleeve capital caps are unchanged in all ablations.
Daily contribution correlation inside the actual combined account (sleeve PnL changes divided by prior total equity): `0.11080672691104715`.

- L1+L2 (no BTC gate) vs L1 Trend only: strictly reduced drawdown **NO**; improved Calmar **NO**; improved Sharpe **NO**.
- Full (L1+L2+BTC) vs L1 Trend only: strictly reduced drawdown **NO**; improved Calmar **NO**; improved Sharpe **NO**.
- L1+L2 (no BTC gate) vs L2 Pullback only: strictly reduced drawdown **NO**; improved Calmar **YES**; improved Sharpe **YES**.
- Full (L1+L2+BTC) vs L2 Pullback only: strictly reduced drawdown **NO**; improved Calmar **YES**; improved Sharpe **YES**.

## Risk, trade and stability details

- Final holdout: -0.86%, 6 completed trades, DD -1.06%.
- 2x fee/slippage stress (spread/depth fixed): -0.33%, DD -2.33%, 7 trades.
- 3x fee/slippage stress (spread/depth fixed): -0.68%, DD -2.41%, 8 trades.
- Sensitivity (31 cases): return -0.75% to 0.93%; perturbations (14 cases): -0.28% to 0.34%.
- Closed trades by asset: `{'BTC/USDT': 3, 'DOGE/USDT': 0, 'ETH/USDT': 2, 'SOL/USDT': 1, 'XRP/USDT': 1}`; by layer (count and win rate): `{'DailyDonchianTrend': {'trades': 3, 'win_rate': 0.6666666666666666}, 'TrendPullback': {'trades': 4, 'win_rate': 0.25}}`.
- Win rate 42.86%; average win/loss 0.2604 / -0.1746 USDT; exposure 30.54%; longest flat period 112 days.
- Worst month -1.63%; maximum consecutive losses 3; longest underwater stretch 59 days (including unrecovered tail).
- Breaker days by first blocking reason: `{'loss cooldown': 3}`. Size/fill rejections: `{'entry risk/minimum': 8}`. Unliquidated at sample end: `[]`.

No execution guarantee, no evidence of a live edge, and no authorization for real orders.
