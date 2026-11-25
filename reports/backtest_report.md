# LayeredPortfolio — daily Nobitex PAPER research

## Weaknesses first

**NOT VALIDATED — numerical acceptance failed**. Runtime default enabled: `false`.

This is the preserved **primary longest-segment** result. The separately labeled supplemental recent
analysis is `reports/portfolio_recent/backtest_report.md`; it also fails acceptance and does not replace
this result. Both samples and current software/network evidence are recorded in `docs/VALIDATION.md`.

- Today's universe/precision create survivorship and selection bias. Excluded gaps and older/unmatched bars are not traded through.
- Historical order books are unavailable: each modeled IOC uses the existing depth walk, a fixed half-spread and a one-level capacity of 0.1% of the prior closed day's base volume at default. This is an assumption, not measured historical executable liquidity.
- Zero-volume input bars per asset: `{'BTC/USDT': 1000, 'DOGE/USDT': 1000, 'ETH/USDT': 1000, 'SOL/USDT': 1000, 'XRP/USDT': 1000}`. Zero-volume prior bars imply zero modeled capacity: no substitution or inferred liquidity. A no-trade run cannot validate the strategy.
- Daily OHLC cannot time stops across assets or capture the intraday equity minimum. Reported drawdown uses daily closes; the ladder also checks opens. Paper stops require connectivity. A rejected exit may remain exposed.
- Walk-forward accounts restart risk and cash, do not compound fold returns, and use only the pre-holdout period. The holdout is not evidence of future safety. Small trade counts make ratios fragile.

## Acceptance (frozen criteria)

- **FAIL** — At least 100 completed trades
- **FAIL** — Positive net return at baseline and 2x costs
- **FAIL** — Positive fixed final-25% holdout return
- **FAIL** — Profit factor greater than 1.30
- **PASS** — Maximum drawdown no worse than 25%
- **FAIL** — Calmar better than equal-weight buy and hold
- **FAIL** — Robust to +/-20% perturbations
- **PASS** — Combined drawdown no worse than worst pure single trading layer

Perturbation passes only when baseline is positive and **all** one-at-a-time and joint +/-20% runs stay positive and retain at least 50% of baseline net return. No rule was changed to pass.

## Coverage and reproducibility

Evaluation UTC: 2023-07-18T20:30:00+00:00 to 2025-06-17T20:30:00+00:00. Final holdout: 175 days from 2024-12-24T20:30:00+00:00.
Common contiguous policy: `longest`, 1000 inputs per asset including warmup. Excluded counts: `{'BTC/USDT': 1951, 'DOGE/USDT': 1141, 'ETH/USDT': 1750, 'SOL/USDT': 557, 'XRP/USDT': 1751}`.
Base costs per side: fee 0.25%, adverse slippage 0.15%, plus modeled half-spread 0.10%.
The primary raw input CSV SHA256 manifest is `reports/portfolio/inputs/manifest.json`; `reports/universe.md` records raw coverage/gaps. A snapshot can be replayed without API access.

## Ablation and benchmarks

| Run | Return | CAGR | Max DD | Calmar | Sharpe | Sortino | Trades | PF |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| L3 Cash only | 0.00% | 0.00% | 0.00% | N/A | N/A | N/A | 0 | N/A |
| L1 Trend only | 0.00% | 0.00% | 0.00% | N/A | N/A | N/A | 0 | N/A |
| L2 Pullback only | 0.00% | 0.00% | 0.00% | N/A | N/A | N/A | 0 | N/A |
| L1+L2 (no BTC gate) | 0.00% | 0.00% | 0.00% | N/A | N/A | N/A | 0 | N/A |
| Full (L1+L2+BTC) | 0.00% | 0.00% | 0.00% | N/A | N/A | N/A | 0 | N/A |
| Full + breadth | 0.00% | 0.00% | 0.00% | N/A | N/A | N/A | 0 | N/A |
| Equal weight B&H | 218.03% | 82.89% | -54.48% | 1.522 | 1.213 | 1.827 | 0 | N/A |
| BTC B&H | 246.01% | 91.11% | -27.98% | 3.256 | 1.638 | 2.565 | 0 | N/A |
| Legacy 4h BTC trend | 3.88% | 2.01% | -4.09% | 0.491 | 0.592 | 1.096 | 21 | 1.618 |

Legacy BTC strategy uses its unchanged rules/fill model, 4h drawdown observations and daily-sampled Sharpe/Sortino. Buy-and-hold buys equal weights once, not daily rebalanced, with modeled round-trip costs and fractional units; it does not impose the portfolio's risk or modeled-depth caps.

Sleeve return correlation: undefined.
Layer 3 alone is all cash; it has no trade/exit rule. Sleeve capital caps are unchanged in all ablations.
Daily contribution correlation inside the actual combined account (sleeve PnL changes divided by prior total equity): `None`.

- L1+L2 (no BTC gate) vs L1 Trend only: strictly reduced drawdown **NO**; improved Calmar **undefined**; improved Sharpe **undefined**.
- Full (L1+L2+BTC) vs L1 Trend only: strictly reduced drawdown **NO**; improved Calmar **undefined**; improved Sharpe **undefined**.
- L1+L2 (no BTC gate) vs L2 Pullback only: strictly reduced drawdown **NO**; improved Calmar **undefined**; improved Sharpe **undefined**.
- Full (L1+L2+BTC) vs L2 Pullback only: strictly reduced drawdown **NO**; improved Calmar **undefined**; improved Sharpe **undefined**.

## Risk, trade and stability details

- Final holdout: 0.00%, 0 completed trades, DD 0.00%.
- 2x fee/slippage stress (spread/depth fixed): 0.00%, DD 0.00%, 0 trades.
- 3x fee/slippage stress (spread/depth fixed): 0.00%, DD 0.00%, 0 trades.
- Sensitivity (31 cases): return 0.00% to 0.00%; perturbations (14 cases): 0.00% to 0.00%.
- Closed trades by asset: `{'BTC/USDT': 0, 'DOGE/USDT': 0, 'ETH/USDT': 0, 'SOL/USDT': 0, 'XRP/USDT': 0}`; by layer (count and win rate): `{'DailyDonchianTrend': {'trades': 0, 'win_rate': None}, 'TrendPullback': {'trades': 0, 'win_rate': None}}`.
- Win rate 0.00%; average win/loss 0.0000 / 0.0000 USDT; exposure 0.00%; longest flat period 700 days.
- Worst month 0.00%; maximum consecutive losses 0; longest underwater stretch 0 days (including unrecovered tail).
- Breaker days by first blocking reason: `{}`. Size/fill rejections: `{'entry modeled depth': 232}`. Unliquidated at sample end: `[]`.

No execution guarantee, no evidence of a live edge, and no authorization for real orders.
