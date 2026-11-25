# Nobitex daily universe

Screen UTC: 2026-11-20T12:03:04+00:00. Selected: BTC/USDT, ETH/USDT, XRP/USDT, SOL/USDT, DOGE/USDT.

Source: public market stats, options, full order books and actual daily candles. No returns used to select.
Screen: top 16 open USDT markets by current 24h quote turnover (plus BTC), with public rules; exclude stable/fiat/gold proxies listed in code.
The first screen required 750 consecutive bars; no symbol passed because of genuine daily discontinuities. Before evaluating returns,
the history rule was split into >=750 raw bars and >=301 recent consecutive current-grid bars including the latest close.
Require median of last 90 daily close x base volume >=10,000 USDT,
and three fresh book observations (<=90s old), median spread <=0.40% and >=500 USDT each side within 0.50% of midpoint.
Rank eligible markets by median daily quote-volume proxy; BTC is mandatory for the regime. Screening is a current snapshot,
subject to survivorship/selection bias when applied to older history; it is not historical liquidity evidence.

| Symbol | 24h turnover | Raw / recent contiguous | 90d median quote proxy | Median spread | Bid / ask depth USDT | Decision |
|---|---:|---:|---:|---:|---:|---|
| BTC/USDT | 1643000 | 987 / 507 | 1321196 | 0.053% | 73325 / 8303 | Selected |
| ZEC/USDT | 1179963 | 643 / 501 | 1154436 | 0.171% | 12128 / 3891 | <750 raw bars, <301 recent contiguous current-grid bars, or stale latest |
| ETH/USDT | 720871 | 985 / 505 | 774406 | 0.123% | 14236 / 2637 | Selected |
| SKY/USDT | 255031 | 429 / 429 | 2459 | 0.627% | 2309 / 4554 | <750 raw bars, <301 recent contiguous current-grid bars, or stale latest; median daily quote-volume proxy <10,000 USDT; requires 3 fresh books, median spread <=0.40%, depth >=500 USDT each side |
| SOL/USDT | 238174 | 983 / 503 | 334464 | 0.074% | 7029 / 5190 | Selected |
| XRP/USDT | 206934 | 985 / 505 | 373400 | 0.038% | 7781 / 3075 | Selected |
| NEAR/USDT | 196589 | 981 / 501 | 159885 | 0.369% | 8618 / 401 | requires 3 fresh books, median spread <=0.40%, depth >=500 USDT each side |
| HMSTR/USDT | 172552 | 771 / 505 | 23101 | 0.397% | 946 / 3589 | Eligible below cutoff |
| ZIL/USDT | 149525 | 664 / 501 | 13253 | 0.334% | 569 / 427 | <750 raw bars, <301 recent contiguous current-grid bars, or stale latest; requires 3 fresh books, median spread <=0.40%, depth >=500 USDT each side |
| DOGE/USDT | 145053 | 984 / 504 | 241190 | 0.346% | 1021 / 5425 | Selected |
| HUMA/USDT | 130072 | 215 / 215 | 1679 | 0.204% | 1655 / 174 | <750 raw bars, <301 recent contiguous current-grid bars, or stale latest; median daily quote-volume proxy <10,000 USDT; requires 3 fresh books, median spread <=0.40%, depth >=500 USDT each side |
| MMT/USDT | 83347 | 368 / 368 | 709 | 0.674% | 65 / 359 | <750 raw bars, <301 recent contiguous current-grid bars, or stale latest; median daily quote-volume proxy <10,000 USDT; requires 3 fresh books, median spread <=0.40%, depth >=500 USDT each side |
| 1M_PEPE/USDT | 80679 | 891 / 505 | 52390 | 0.571% | 2027 / 522 | requires 3 fresh books, median spread <=0.40%, depth >=500 USDT each side |
| TRX/USDT | 76108 | 983 / 503 | 68754 | 0.384% | 920 / 1572 | Eligible below cutoff |
| ADA/USDT | 73516 | 983 / 503 | 142198 | 0.273% | 5426 / 1582 | Eligible below cutoff |
| GRAM/USDT | 61221 | 984 / 504 | 69345 | 0.586% | 1324 / 734 | requires 3 fresh books, median spread <=0.40%, depth >=500 USDT each side |

## Raw cached coverage (UTC candle opens)

- BTC/USDT: 2951 bars, 2018-10-08T20:30:00+00:00 to 2026-11-18T20:30:00+00:00; 2951 fetched / 8 windows / two consecutive empty windows.
  - Gap from 2019-03-21T20:30:00+00:00 to 2019-03-22T19:30:00+00:00: 82800s discontinuity (grid shift).
  - Gap from 2019-09-20T19:30:00+00:00 to 2019-09-21T20:30:00+00:00: 90000s discontinuity (grid shift).
  - Gap from 2020-03-20T20:30:00+00:00 to 2020-03-21T19:30:00+00:00: 82800s discontinuity (grid shift).
  - Gap from 2020-09-19T19:30:00+00:00 to 2020-09-20T20:30:00+00:00: 90000s discontinuity (grid shift).
  - Gap from 2021-03-21T20:30:00+00:00 to 2021-03-22T19:30:00+00:00: 82800s discontinuity (grid shift).
  - Gap from 2021-09-20T19:30:00+00:00 to 2021-09-21T20:30:00+00:00: 90000s discontinuity (grid shift).
  - Gap from 2022-03-21T20:30:00+00:00 to 2022-03-22T19:30:00+00:00: 82800s discontinuity (grid shift).
  - Gap from 2022-09-20T19:30:00+00:00 to 2022-09-21T20:30:00+00:00: 90000s discontinuity (grid shift).
  - Gap from 2025-06-16T20:30:00+00:00 to 2025-06-30T20:30:00+00:00: 13 missing days.
- ETH/USDT: 2750 bars, 2019-04-25T19:30:00+00:00 to 2026-11-18T20:30:00+00:00; 2750 fetched / 8 windows / two consecutive empty windows.
  - Gap from 2019-09-20T19:30:00+00:00 to 2019-09-21T20:30:00+00:00: 90000s discontinuity (grid shift).
  - Gap from 2020-03-20T20:30:00+00:00 to 2020-03-21T19:30:00+00:00: 82800s discontinuity (grid shift).
  - Gap from 2020-09-19T19:30:00+00:00 to 2020-09-20T20:30:00+00:00: 90000s discontinuity (grid shift).
  - Gap from 2021-03-21T20:30:00+00:00 to 2021-03-22T19:30:00+00:00: 82800s discontinuity (grid shift).
  - Gap from 2021-09-20T19:30:00+00:00 to 2021-09-21T20:30:00+00:00: 90000s discontinuity (grid shift).
  - Gap from 2022-03-21T20:30:00+00:00 to 2022-03-22T19:30:00+00:00: 82800s discontinuity (grid shift).
  - Gap from 2022-09-20T19:30:00+00:00 to 2022-09-21T20:30:00+00:00: 90000s discontinuity (grid shift).
  - Gap from 2025-06-16T20:30:00+00:00 to 2025-07-02T20:30:00+00:00: 15 missing days.
- XRP/USDT: 2751 bars, 2019-04-24T19:30:00+00:00 to 2026-11-18T20:30:00+00:00; 2751 fetched / 8 windows / two consecutive empty windows.
  - Gap from 2019-09-20T19:30:00+00:00 to 2019-09-21T20:30:00+00:00: 90000s discontinuity (grid shift).
  - Gap from 2020-03-20T20:30:00+00:00 to 2020-03-21T19:30:00+00:00: 82800s discontinuity (grid shift).
  - Gap from 2020-09-19T19:30:00+00:00 to 2020-09-20T20:30:00+00:00: 90000s discontinuity (grid shift).
  - Gap from 2021-03-21T20:30:00+00:00 to 2021-03-22T19:30:00+00:00: 82800s discontinuity (grid shift).
  - Gap from 2021-09-20T19:30:00+00:00 to 2021-09-21T20:30:00+00:00: 90000s discontinuity (grid shift).
  - Gap from 2022-03-21T20:30:00+00:00 to 2022-03-22T19:30:00+00:00: 82800s discontinuity (grid shift).
  - Gap from 2022-09-20T19:30:00+00:00 to 2022-09-21T20:30:00+00:00: 90000s discontinuity (grid shift).
  - Gap from 2025-06-16T20:30:00+00:00 to 2025-07-02T20:30:00+00:00: 15 missing days.
- SOL/USDT: 1557 bars, 2022-07-29T19:30:00+00:00 to 2026-11-18T20:30:00+00:00; 1557 fetched / 6 windows / two consecutive empty windows.
  - Gap from 2022-09-20T19:30:00+00:00 to 2022-09-21T20:30:00+00:00: 90000s discontinuity (grid shift).
  - Gap from 2025-06-16T20:30:00+00:00 to 2025-07-04T20:30:00+00:00: 17 missing days.
- DOGE/USDT: 2141 bars, 2020-12-23T20:30:00+00:00 to 2026-11-18T20:30:00+00:00; 2141 fetched / 7 windows / two consecutive empty windows.
  - Gap from 2021-03-21T20:30:00+00:00 to 2021-03-22T19:30:00+00:00: 82800s discontinuity (grid shift).
  - Gap from 2021-09-20T19:30:00+00:00 to 2021-09-21T20:30:00+00:00: 90000s discontinuity (grid shift).
  - Gap from 2022-03-21T20:30:00+00:00 to 2022-03-22T19:30:00+00:00: 82800s discontinuity (grid shift).
  - Gap from 2022-09-20T19:30:00+00:00 to 2022-09-21T20:30:00+00:00: 90000s discontinuity (grid shift).
  - Gap from 2025-06-16T20:30:00+00:00 to 2025-07-03T20:30:00+00:00: 16 missing days.
