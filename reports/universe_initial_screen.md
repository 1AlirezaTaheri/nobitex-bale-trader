# Nobitex daily universe

Screen UTC: 2026-11-20T11:57:41+00:00. Selected: NONE.

Source: public market stats, options, full order books and actual daily candles. No returns used to select.
Screen: top 16 open USDT markets by current 24h quote turnover (plus BTC), with public rules; exclude stable/fiat/gold proxies listed in code.
Require >=750 consecutive current-grid bars with latest closed bar, median of last 90 daily close x base volume >=10,000 USDT,
and three fresh book observations (<=90s old), median spread <=0.40% and >=500 USDT each side within 0.50% of midpoint.
Rank eligible markets by median daily quote-volume proxy; BTC is mandatory for the regime. Screening is a current snapshot,
subject to survivorship/selection bias when applied to older history; it is not historical liquidity evidence.

| Symbol | 24h turnover | Contiguous screen bars | 90d median quote proxy | Median spread | Bid / ask depth USDT | Decision |
|---|---:|---:|---:|---:|---:|---|
| BTC/USDT | 1641121 | 507 | 1321196 | 0.160% | 25105 / 18232 | <750 current contiguous closed bars or stale latest |
| ZEC/USDT | 1175393 | 501 | 1154436 | 0.273% | 14519 / 3713 | <750 current contiguous closed bars or stale latest |
| ETH/USDT | 720553 | 505 | 774406 | 0.067% | 13976 / 3862 | <750 current contiguous closed bars or stale latest |
| SKY/USDT | 254829 | 429 | 2459 | 0.467% | 1812 / 317 | <750 current contiguous closed bars or stale latest; median daily quote-volume proxy <10,000 USDT; requires 3 fresh books, median spread <=0.40%, depth >=500 USDT each side |
| SOL/USDT | 238127 | 503 | 334464 | 0.131% | 9275 / 5476 | <750 current contiguous closed bars or stale latest |
| XRP/USDT | 205677 | 505 | 373400 | 0.081% | 8895 / 2847 | <750 current contiguous closed bars or stale latest |
| NEAR/USDT | 196513 | 501 | 159885 | 0.134% | 8698 / 1634 | <750 current contiguous closed bars or stale latest |
| HMSTR/USDT | 172430 | 505 | 23101 | 0.402% | 4399 / 3594 | <750 current contiguous closed bars or stale latest; requires 3 fresh books, median spread <=0.40%, depth >=500 USDT each side |
| ZIL/USDT | 148810 | 501 | 13253 | 0.445% | 592 / 352 | <750 current contiguous closed bars or stale latest; requires 3 fresh books, median spread <=0.40%, depth >=500 USDT each side |
| DOGE/USDT | 145017 | 504 | 241190 | 0.313% | 918 / 5338 | <750 current contiguous closed bars or stale latest |
| HUMA/USDT | 129702 | 215 | 1679 | 0.333% | 1427 / 174 | <750 current contiguous closed bars or stale latest; median daily quote-volume proxy <10,000 USDT; requires 3 fresh books, median spread <=0.40%, depth >=500 USDT each side |
| MMT/USDT | 83200 | 368 | 709 | 0.949% | 12 / 258 | <750 current contiguous closed bars or stale latest; median daily quote-volume proxy <10,000 USDT; requires 3 fresh books, median spread <=0.40%, depth >=500 USDT each side |
| 1M_PEPE/USDT | 80679 | 505 | 52390 | 0.142% | 388 / 530 | <750 current contiguous closed bars or stale latest; requires 3 fresh books, median spread <=0.40%, depth >=500 USDT each side |
| TRX/USDT | 75579 | 503 | 68754 | 0.068% | 916 / 2733 | <750 current contiguous closed bars or stale latest |
| ADA/USDT | 73418 | 503 | 142198 | 0.136% | 4197 / 1536 | <750 current contiguous closed bars or stale latest |
| GRAM/USDT | 60812 | 504 | 69345 | 0.195% | 584 / 617 | <750 current contiguous closed bars or stale latest |

## Raw cached coverage (UTC candle opens)

