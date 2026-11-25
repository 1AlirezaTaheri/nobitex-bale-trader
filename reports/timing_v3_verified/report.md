# Strategy V3 — frozen daily timing research

## Weaknesses and limits first

- Only continuous common BTC/ETH segments with more than 300 raw daily candles are evaluable; all shorter DST-phase segments and timestamp gaps are excluded without bridging.
- Price-only execution ignores historical depth, spread, venue precision, minimum order sizes, and latency; fixed 0.15% adverse slippage and 0.25% fee are assumptions, not realized fills.
- The cache's older zero volumes matched sampled raw UDF responses. These strategies ignore volume; the comparison is not evidence of executable liquidity.
- The 25% chronological holdout is small and must not be treated as independent confirmation. A few trend episodes cannot establish statistical significance.
- The random cyclic-shift diagnostic preserves target blocks approximately but is a simulated null, not an executable strategy or statistical significance test.
- Daily closes understate intraday drawdown; outages, stablecoin risk, model error, future fees, and exchange execution remain unmodeled.
- The legacy 4h baseline uses the unchanged engine and may cover different continuous dates; costs are applied by that engine, but its result schema does not expose aggregate costs.

Pre-registration SHA256: `6f26ccabb14fa92b477a94b873f3309a0eb9b30a3d873118def5fa81ec3489af`. No amendment.
Fee per side `0.25%`, adverse slippage per side `0.15%`; source: https://apiv2.nobitex.ir/v2/options public schedule, max tier 0.0013.
Coverage: 2750 exact common timestamps; 2 eligible segments; 905 evaluated observations; holdout 227.

## Full-sample metrics and baselines

| Run | Return | CAGR | Max DD | Calmar | Sharpe | Sortino | Worst 12m | Avg exposure | Invested days | Round trips | Legs | Turnover | Costs USDT |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 60.83% | 21.12% | -42.32% | 0.499 | 0.691 | 1.037 | -32.23% | 72.82% | 72.82% | 11.000 | 22.000 | 1932.36% | 12.073 |
| A matched | 124.27% | 38.51% | -21.50% | 1.791 | 1.177 | 1.823 | 7.72% | 72.82% | 100.00% | 2.000 | 34.000 | 375.05% | 2.906 |
| B | 107.02% | 34.11% | -37.19% | 0.917 | 0.984 | 1.514 | -18.65% | 73.55% | 85.30% | 8.000 | 59.000 | 1741.69% | 12.397 |
| B matched | 125.73% | 38.87% | -21.70% | 1.791 | 1.176 | 1.822 | 7.74% | 73.55% | 100.00% | 2.000 | 34.000 | 377.42% | 2.942 |
| C | 115.20% | 36.22% | -32.30% | 1.121 | 1.096 | 1.692 | -13.01% | 67.34% | 87.96% | 5.000 | 40.000 | 1329.17% | 9.651 |
| C matched | 113.35% | 35.75% | -19.96% | 1.791 | 1.180 | 1.828 | 7.58% | 67.34% | 100.00% | 2.000 | 34.000 | 356.42% | 2.636 |
| D | 74.35% | 25.13% | -25.15% | 0.999 | 0.893 | 1.314 | -10.22% | 54.71% | 88.84% | 9.000 | 60.000 | 1095.44% | 6.967 |
| D matched | 48.19% | 17.19% | -29.22% | 0.588 | 0.720 | 1.080 | -16.28% | 54.71% | 100.00% | 4.000 | 68.000 | 325.38% | 1.862 |
| BTC buy-and-hold | 180.12% | 51.50% | -28.95% | 1.779 | 1.162 | 1.797 | 7.32% | 100.00% | 100.00% | 2.000 | 4.000 | 444.17% | 4.296 |
| BTC+ETH equal-weight buy-and-hold | 87.59% | 28.88% | -41.37% | 0.698 | 0.770 | 1.152 | -22.96% | 100.00% | 100.00% | 4.000 | 8.000 | 407.99% | 3.068 |
| Legacy 4h BTC seg 7 | 3.88% | 2.01% | -4.09% | 0.491 | 0.592 | 1.096 | N/A | N/A | N/A | N/A | 21.000 | N/A | N/A |
| Legacy 4h BTC seg 8 | 0.42% | 0.75% | -2.95% | 0.255 | 0.195 | 0.448 | N/A | N/A | N/A | N/A | 7.000 | N/A | N/A |

## Acceptance — per candidate

| Candidate | Status | Criteria | Enabled |
|---|---|---|---|
| A | NOT VALIDATED | PASS 1; FAIL 2; FAIL 3; FAIL 4; FAIL 5; PASS 6; FAIL 7 | No |
| B | NOT VALIDATED | PASS 1; FAIL 2; FAIL 3; FAIL 4; FAIL 5; PASS 6; FAIL 7 | No |
| C | NOT VALIDATED | PASS 1; FAIL 2; FAIL 3; FAIL 4; FAIL 5; PASS 6; FAIL 7 | No |
| D | NOT VALIDATED | PASS 1; FAIL 2; PASS 3; FAIL 4; FAIL 5; PASS 6; PASS 7 | No |

## Robustness and regimes

### Candidate A

- Plateau: **fragile / no demonstrated plateau**, 0/8 grid cases pass (0.0%); return range 60.83% to 125.43%, drawdown range -43.16% to -32.90%.
- Timing null: 999 cyclic shifts; share matching/exceeding actual return `0.8468468468468469`, actual Calmar `0.8678678678678678`; unshifted reconstruction error `4.440892098500626e-15`. No significance claim.
- Major phases >=90 days: 3; candidate invested episodes: 11; regime metrics: `{"down": {"average_exposure": 0.0, "days": 246, "mean_daily_return": -0.0001788576777058275, "net_pnl": -6.197885405076008, "pnl_on_initial_capital": -0.06197885405076008, "time_invested": 0.0}, "up": {"average_exposure": 1.0, "days": 659, "mean_daily_return": 0.0010641660728049267, "net_pnl": 67.02289647184905, "pnl_on_initial_capital": 0.6702289647184905, "time_invested": 1.0}}`.
- Last 12 calendar months actually observed: `{"average_exposure": 0.39024390243902446, "days": 205, "end": 1795120200, "return": -0.04312213570165291, "start": 1777408200, "time_invested": 0.3902439024390244}`.

### Candidate B

- Plateau: **fragile / no demonstrated plateau**, 0/22 grid cases pass (0.0%); return range 82.06% to 123.85%, drawdown range -38.20% to -32.47%.
- Timing null: 999 cyclic shifts; share matching/exceeding actual return `0.6426426426426426`, actual Calmar `0.7027027027027027`; unshifted reconstruction error `4.440892098500626e-15`. No significance claim.
- Major phases >=90 days: 3; candidate invested episodes: 8; regime metrics: `{"down": {"average_exposure": 0.12919179652000426, "days": 246, "mean_daily_return": 0.00034955657584185, "net_pnl": 14.258661920184409, "pnl_on_initial_capital": 0.1425866192018441, "time_invested": 0.45934959349593496}, "up": {"average_exposure": 0.961767111752937, "days": 659, "mean_daily_return": 0.001224743762263091, "net_pnl": 92.75679137707641, "pnl_on_initial_capital": 0.9275679137707641, "time_invested": 1.0}}`.
- Last 12 calendar months actually observed: `{"average_exposure": 0.43888551996382497, "days": 205, "end": 1795120200, "return": -0.010621131587711052, "start": 1777408200, "time_invested": 0.5414634146341464}`.

### Candidate C

- Plateau: **fragile / no demonstrated plateau**, 0/26 grid cases pass (0.0%); return range 81.12% to 120.35%, drawdown range -35.00% to -28.35%.
- Timing null: 999 cyclic shifts; share matching/exceeding actual return `0.5635635635635635`, actual Calmar `0.5905905905905906`; unshifted reconstruction error `8.43769498715119e-15`. No significance claim.
- Major phases >=90 days: 3; candidate invested episodes: 5; regime metrics: `{"down": {"average_exposure": 0.14201877439746952, "days": 246, "mean_daily_return": 0.000522862960088809, "net_pnl": 21.142234355363357, "pnl_on_initial_capital": 0.21142234355363357, "time_invested": 0.556910569105691}, "up": {"average_exposure": 0.8718183077213338, "days": 659, "mean_daily_return": 0.0011751244308642495, "net_pnl": 94.05727663833802, "pnl_on_initial_capital": 0.9405727663833803, "time_invested": 1.0}}`.
- Last 12 calendar months actually observed: `{"average_exposure": 0.42709023460032136, "days": 205, "end": 1795120200, "return": -0.010008136026015357, "start": 1777408200, "time_invested": 0.5414634146341464}`.

### Candidate D

- Plateau: **fragile / no demonstrated plateau**, 23/26 grid cases pass (88.5%); return range 34.43% to 84.06%, drawdown range -31.75% to -23.12%.
- Timing null: 999 cyclic shifts; share matching/exceeding actual return `0.3963963963963964`, actual Calmar `0.26126126126126126`; unshifted reconstruction error `5.551115123125783e-15`. No significance claim.
- Major phases >=90 days: 3; candidate invested episodes: 3; regime metrics: `{"down": {"average_exposure": 0.10355216138633065, "days": 246, "mean_daily_return": 0.0006052587147509563, "net_pnl": 22.84358193667468, "pnl_on_initial_capital": 0.2284358193667468, "time_invested": 0.5894308943089431}, "up": {"average_exposure": 0.7126750174097153, "days": 659, "mean_daily_return": 0.0007893219794119497, "net_pnl": 51.50435330360445, "pnl_on_initial_capital": 0.5150435330360444, "time_invested": 1.0}}`.
- Last 12 calendar months actually observed: `{"average_exposure": 0.33888489698999025, "days": 205, "end": 1795120200, "return": -0.05086905623542892, "start": 1777408200, "time_invested": 0.5073170731707317}`.

## Coverage detail

| Segment | Start UTC | End UTC | Inputs | Evaluable after warmup | Grid offset |
|---:|---|---|---:|---:|---:|
| 0 | 2019-04-25T19:30:00+00:00 | 2019-09-20T19:30:00+00:00 | 149 | 0 | 70200s |
| 1 | 2019-09-21T20:30:00+00:00 | 2020-03-20T20:30:00+00:00 | 182 | 0 | 73800s |
| 2 | 2020-03-21T19:30:00+00:00 | 2020-09-19T19:30:00+00:00 | 183 | 0 | 70200s |
| 3 | 2020-09-20T20:30:00+00:00 | 2021-03-21T20:30:00+00:00 | 183 | 0 | 73800s |
| 4 | 2021-03-22T19:30:00+00:00 | 2021-09-20T19:30:00+00:00 | 183 | 0 | 70200s |
| 5 | 2021-09-21T20:30:00+00:00 | 2022-03-21T20:30:00+00:00 | 182 | 0 | 73800s |
| 6 | 2022-03-22T19:30:00+00:00 | 2022-09-20T19:30:00+00:00 | 183 | 0 | 70200s |
| 7 | 2022-09-21T20:30:00+00:00 | 2025-06-16T20:30:00+00:00 | 1000 | 700 | 73800s |
| 8 | 2025-07-02T20:30:00+00:00 | 2026-11-18T20:30:00+00:00 | 505 | 205 | 73800s |

Excluded segment policy: common segments of 300 candles or fewer cannot supply 300 warmup candles plus an execution candle; no gap is bridged.

## Legacy 4h baseline coverage

- `evaluated` segment 7: 1689712200 to 1750192200; 701 daily-sampled observations.
- `evaluated` segment 8: 1777408200 to 1795120200; 206 daily-sampled observations.

No candidate was enabled by this report. All candidates remain disabled; LIVE remains blocked.
