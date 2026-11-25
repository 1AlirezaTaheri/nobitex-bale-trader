# Nobitex / Bale — safety-first PAPER trading laboratory

**Runnable Windows-native PAPER trader, not a certified live trading product.** Public Nobitex data,
persistent simulated execution, shared strategy/risk backtesting, and a thin Bale control client.
No withdrawal/transfer code. No secrets needed for PAPER. **Live placement/cancellation are intentionally
disabled** while the live contracts in [docs/UNVERIFIED.md](docs/UNVERIFIED.md) remain unresolved.
Adding credentials alone will NOT enable live trading. Do not interpret test success as exchange certification.

فارسی: [README.fa.md](README.fa.md). Decisions: [ASSUMPTIONS](docs/ASSUMPTIONS.md).
Validation evidence: [VALIDATION](docs/VALIDATION.md). API sources: [UNVERIFIED](docs/UNVERIFIED.md).

## Final adversarial audit and independent SHADOW — NOT VALIDATED

Product engineering update (2026-11-25): see [Persian user guide](docs/USER_GUIDE.fa.md),
[ranked evidence synthesis](docs/RESEARCH/SYNTHESIS.md), [source/access limitations](docs/RESEARCH/BIBLIOGRAPHY.md),
[repository/license review](docs/RESEARCH/LICENSES.md), and [implementation amendments](docs/FINAL_PRODUCT_AMENDMENTS.md).
Run `python -m app.doctor` offline, then `run_shadow.bat` / `run_weekly_report.bat`.
The new `product-shadow-v2` experiment uses `reports/final_product/shadow_v2`; do not restart an old root
with changed fingerprint-bound code. There are zero new strategy candidates or historical parameter searches.
Bale requires the owner's explicit `python -m app.bale_setup --find-chat`, then `--test`, and an explicit
`--bale` request (included in the launch scripts). No real Bale call was made during implementation.
Invalid optional Bale settings fall back to console; invalid MODE remains blocked. Fixed review checkpoints
are 3/6/12 months, and realized-risk B4 comparisons are explicitly descriptive hindsight.

**Weaknesses first:** all earlier historical holdouts are contaminated by repeated research. The old
final-audit manifest does not authenticate the current protocol; provenance remains unresolved and
amendments are explicit. The inventory is 262 archived rows +25 audit series (**M=287**); 999 draws
cannot establish the adjusted significance threshold. Native S0/S1 fills are not execution-identical
to daily price-only baselines; missing native exposure/cost/B7/stress checks remain unavailable.

All seven frozen strategy variants are **category 1 / NOT VALIDATED**, with no parameter or enabled-flag
change. Across 905 evaluated days in two disconnected segments, B4_25 (25% BTC /75% USDT, monthly
5pp drift band) had +36.27% net return and −7.99% daily MaxDD, the smallest DD **only among the
registered positive-return B4/B5 constant mixes**. This is not a universal winner, a recommendation or
a profit/loss guarantee. S0's smaller observed daily DD has a different model and negative 2x-cost return.

Evidence: [full comparison and limitations](reports/final_audit/report.md),
[operations/security](reports/final_audit/operational_report.md),
[SHADOW contract](reports/final_audit/FORWARD_FRAMEWORK.md), [risk register](docs/RISK_REGISTER.md),
and [provenance amendments](docs/FINAL_AUDIT_AMENDMENTS.md). The full offline suite passed **239 tests**;
passing software checks do not establish investment validity. Earlier test counts below are historical.
The corrected full rerun/replay matched **30 artifacts byte-for-byte**, with all **24 non-chart files**
unchanged from the original. The earlier timed-out partial directories were preserved, not relabeled
as successful. All five corrected charts were inspected; the original results remain intact.

SHADOW has separate snapshots, `shadow.db` and `public_cache.db` under `reports/final_audit/forward/`.
It observes A/D and fixed controls without real orders, credentials, legacy wallets or historical trade
backfill. The 2026-11-24 23:06:11 UTC smoke was **refused** because activation requires at least
2026-11-25 00:00:00 UTC. Zero genuine snapshots exist in the delivered example; both checkpoints
are PENDING. The date is measured execution time, not the developer-context date 2026-11-25.

```powershell
.\.venv\Scripts\python.exe -m backtest.final_audit --snapshot reports/final_audit/inputs --output reports/final_audit/reproduction_001
.\.venv\Scripts\python.exe -m app.forward_shadow --mode shadow --root reports/final_audit/forward --max-seconds 45
.\.venv\Scripts\python.exe -m app.forward_report --root reports/final_audit/forward --output reports/final_audit/weekly_001
```

Choose a new output name each time; keep prior evidence. A 45-second smoke need not observe a daily
boundary. For continuous observation omit `--max-seconds`, in a separate deliberate operator run; it is
not left running by this delivery. SHADOW uses its **own** `forward/KILL`, not Bale or `data/KILL`.
Any 3/6-month PASS allows continued observation only, never LIVE or meaningful capital. See the
framework before operating it; independently export the chain hash weekly. USDTIRT history returned
403 and units were unverified, so no IRT returns were invented. Vulnerability scanning remains NOT RUN.

## LayeredPortfolio daily research — NOT VALIDATED, disabled by default

The existing 4h BTC strategy, legacy risk values, and `data/paper.db` remain the default. New daily
`portfolio` sections in `config/strategy.yaml` and `config/risk.yaml` configure shared causal signals,
central risk, and a separate multi-symbol PAPER wallet. `portfolio.enabled: false` is deliberate:
the research **fails acceptance**. Do not change it merely because some drawdown numbers are small.

Frozen universe: **BTC/USDT, ETH/USDT, XRP/USDT, SOL/USDT, DOGE/USDT** in `config/universe.yaml`.
The real public screen ranks current liquidity and checks history, spread and two-sided book depth;
selection evidence and exclusions are in `reports/universe.md` and `.json`. No returns selected the pairs.
This is a current-survivor universe, not an unbiased historical universe. An initially stricter consecutive
history screen failed and is preserved in `reports/universe_initial_screen.md`.

- **L1 DailyDonchianTrend:** above EMA200, previous-55-day high breakout, 3xATR20 initial software stop,
  never-lowered prior-20-day low trailing stop / EMA200 close exit, 0.75% initial risk.
- **L2 TrendPullback:** above EMA200, RSI3 <15, no fresh prior-20-day lower low; RSI3 >60, prior-five-day
  high close, seven-day timeout or 2xATR20 hard stop; 0.50% initial risk. Trend has same-symbol precedence.
- **L3 RegimeCashFilter:** BTC below EMA200 blocks new entries; existing stops continue. Optional breadth
  is OFF. Unallocated capital remains USDT. No leverage or short selling.
- **Central risk:** 3% open-risk cap, 25% fee-inclusive per-asset entry outlay, four positions, 50/30/20
  risk-budget caps/reserve, DD ladder 5% half-risk /10% no entries /15% latched halt, 2% daily loss, three
  losses/three-day cooldown and held-asset 60-day correlation scaling. Sizing/risk functions are shared by
  backtest and PAPER; SQLite risk, closure journal, sleeve ownership and consumed closes survive restart.

At 15% drawdown, protective exits still run. The only portfolio halt-resume form is exactly
`/resume I UNDERSTAND THE RISK`; it additionally requires healthy fresh/reconciled state and recovery
below 15% DD. It does **not** reset the peak, 10% entry block, daily loss, cooldown, KILL or operational
faults. Portfolio days use the actual **20:30 UTC** daily boundary; the legacy strategy retains UTC days.

### Observed results and evidence

At the earlier portfolio delivery: **165 offline tests passed**, Ruff lint/format passed (49 Python files),
and `pip check` passed. An earlier portfolio PAPER smoke completed two healthy cycles; the final smoke
failed before startup because public options were unavailable after bounded retries. Current legacy
smokes and public verification also failed on public endpoint availability. See `docs/VALIDATION.md`
for separate successful and failed evidence; passing tests do not imply current connectivity.

The longest common segment has 1,000 inputs per asset, 300 warmup /700 evaluated days
(2023-07-18 20:30 to 2025-06-17 20:30 UTC). **All its reported volumes are zero**: modeled depth therefore
rejects every entry; zero return and zero DD are **not** evidence of safety. That original failed result is
preserved as the primary `reports/backtest_report.md` and `reports/portfolio/` artifacts.

The separate latest segment has 503 nonzero-volume inputs per asset, 300 warmup /203 evaluated days
(2026-04-30 20:30 to 2026-11-19 20:30 UTC). Full portfolio: **+0.08%, -2.27% maximum daily-close DD,
seven trades, PF 1.119**; 2x costs **-0.33%**; final-25% holdout **-0.86%**. Combining did not reduce DD
versus either trading layer alone. See `reports/portfolio_recent/backtest_report.md` for the complete
ablation/benchmark/acceptance table and sensitivity. Both samples are explicitly **NOT VALIDATED**.

Each output directory includes exact input CSVs and SHA256 manifest, equity/trade/monthly CSVs,
summary JSON, chronological holdout, train-only walk-forward, 31 sensitivity cases, 14 +/-20% cases,
2x/3x cost stress, and four PNGs (equity/benchmark, DD, standalone-sleeve equity, monthly heatmap).
Historical depth is **assumed**, not archived: one executable level with 0.10% half-spread and 0.10%
of prior closed daily base volume per IOC. Zero volume is never replaced. PAPER uses real fresh books.
Daily OHLC cannot certify intraday DD, cross-asset event timing, queue execution or software-stop latency.

### Exact commands (Windows Command Prompt)

```bat
cd /d C:\Users\ALIREZA\Desktop\nobitex-bale-trader
set MODE=paper
rem Primary frozen-policy analysis from the real cache
.venv\Scripts\python.exe -m backtest.portfolio_run
rem Supplemental recent nonzero-volume segment, never substituted silently
.venv\Scripts\python.exe -m backtest.portfolio_run --segment latest --output reports\portfolio_recent
rem Offline checksum-verified replay, using the same YAML and capital
.venv\Scripts\python.exe -m backtest.portfolio_run --snapshot reports\portfolio_recent\inputs --output reports\portfolio_recent_replay
rem Explicit opt-in to unvalidated research, separate wallet; not live
run.bat --portfolio-paper --smoke-seconds 30
run.bat --portfolio-paper
rem Ordinary run remains the unchanged legacy strategy
run.bat
.venv\Scripts\python.exe -m app.verify_exchange
```

Do not run both runners together. They share `data/KILL` and `data/bot.lock`. Portfolio state is
`data/portfolio_paper.db`, never the legacy wallet. First startup/wake consumes the latest close without
entry replay; only a continuously observed new close within the 120-second entry deadline may trade.
Stops retry at available fresh prices, never retroactively at a missed historical stop. `/portfolio`,
`/layers`, `/risk`, daily close summaries and exact typed resume keep the existing private Bale whitelist;
layer status is informational, not remote parameter editing. All messages have console fallback.

Optional data maintenance: `python -m app.universe` extends the already-frozen selected inputs;
`python -m app.universe --screen` refreshes evidence but does **not** silently rewrite universe YAML.
Keep prior reports/snapshots before a new screen or experiment. Raw gaps and old DST grids are never filled.

## Strategy V3 daily timing — NOT VALIDATED, disabled by default

The frozen, checksum-verified BTC/ETH timing study is in `docs/STRATEGY_V3_PREREGISTRATION.md` and
`reports/timing_v3/`. It evaluated 905 observations across two eligible common-calendar segments. All
four candidates failed at least one frozen acceptance criterion and remain disabled. BTC buy-and-hold
returned **+180.12%**; candidates A/B/C/D returned **+60.83% / +107.02% / +115.20% / +74.35%** after
base costs. Do not interpret positive backtest returns or a passing individual criterion as validation.
The sample is short, daily OHLC omits executable historical depth, and the timing null is diagnostic only.

Timing PAPER is a separate, simulated-only opt-in; default execution and the existing wallets remain
unchanged. Example short smoke: `python -m app.main --timing-paper --timing-candidate A --smoke-seconds 30`.
Only A–D are selectable; candidate D requires both BTC/USDT and ETH/USDT in `config/timing.yaml`. Each
candidate has its own `data/timing_v3_<candidate>_paper.db` and uses `data/timing_v3_candles.db`, a separate
copy of the public cache. Timing PAPER uses console notifications only and shares the existing lock and
KILL switch. It cannot submit real exchange orders. See `docs/VALIDATION.md` for replay and smoke evidence.

## Windows quick start

1. Install **64-bit Python 3.11+** from python.org (the development environment used Python 3.13).
   Enable the Python launcher/PATH option. Keep this folder on a private local disk, not a shared/cloud folder.
2. In Command Prompt:

```bat
cd /d C:\Users\ALIREZA\Desktop\nobitex-bale-trader
setup.bat
run.bat
```

`setup.bat` creates `.venv`, installs exact pinned dependencies from `requirements.lock`, and copies
`.env.example` to `.env` **only if `.env` does not already exist**. It does not overwrite financial data.
`run.bat` activates the environment and retries unexpected crashes with exponential 5–300-second backoff.
Normal stop, validation refusal and KILL are not automatically restarted. Press Ctrl+C to stop gracefully.
Use a fresh terminal if you previously set environment overrides: inherited `MODE` takes precedence over `.env`.

Without Bale credentials, notifications print to the console. Runtime log: `logs/bot.jsonl` (rotated).
Candles: `data/candles.db`. Simulated wallet, intents, position, risk latches, offsets: `data/paper.db`.
The wallet starts only once; restarting does not refill it. The startup reconciliation compares PAPER
execution storage against the independent manager ledger. Real account reconciliation is a live prerequisite,
not something PAPER pretends to perform against an account without keys.

Manual installation on a supported system:

```bat
python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install -r requirements.lock
python -m pip install --no-build-isolation --no-deps -e .
copy .env.example .env
python -m app.main
```

Do not run the `copy` line if you already have a configured `.env`.

## Configuration and secrets

Only edit `.env` locally. Never send tokens/keys/passwords in chat, screenshots, Git, tickets or logs.
`.env` and runtime logs/databases are ignored by Git. The file itself is plaintext: restrict folder access
and use device encryption. The application does not ask for exchange username/password or a TOTP seed.

```dotenv
MODE=paper
NOBITEX_PUBLIC_KEY=
NOBITEX_PRIVATE_KEY=
BALE_BOT_TOKEN=
BALE_CHAT_ID=
MAX_CAPITAL_QUOTE=100
ALLOW_UNPROTECTED_POSITIONS=false
LOG_LEVEL=INFO
```

For public-only PAPER, leave all four credential fields blank. For Bale, create a bot through the official
`@botfather`, put its token and **your positive private chat/user ID** in `.env`, start a private conversation
with the bot, and restart. Both Bale fields are required together; group control is deliberately disabled.
You can use Bale's documented getUpdates method through your own private tools to identify the ID; do not
paste a token into a browser/shared shell history. The app does not enumerate or print unknown chat IDs.

For private read probes, create an expiring, IP-restricted **READ-only** API key pair in Nobitex's API-services
panel and put the public/private values in the two `NOBITEX_*` fields. Signature uses documented Ed25519
over timestamp + METHOD + exact path/query + raw body. Keys expire/revoke; rotate them in the panel.
No fabricated password login, bearer-token refresh or withdrawal permissions are requested.

YAML files reject unknown keys:
- `config/strategy.yaml`: unchanged legacy trend/optional RSI, BTC/USDT, default 4h; nested `portfolio` parameters.
- `config/risk.yaml`: 1% risk, one position, fee-inclusive order cap, daily 3% loss, 10% drawdown,
  loss cooldown, modeled fee/slippage and spread guard.
- `config/app.yaml`: polling/reconciliation/heartbeat/close grace/freshness limits.
- `config/universe.yaml`: four to six distinct USDT pairs including mandatory BTC for the portfolio.
- `exchange/nobitex_spec.yaml`: origin, endpoint methods/paths/auth, local request caps, precision keys,
  timeframes, candle alignment, order types and UNVERIFIED contracts.

Changing a running PAPER experiment's strategy/risk/app configuration requires stopping it and archiving
the old PAPER database before a new run; silently reusing incompatible position state is rejected.
Lowering MAX_CAPITAL_QUOTE restricts new outlays immediately but does not forcibly sell an existing position.
The cap is not a guarantee of maximum loss, nor a ceiling on unrealized appreciation.

## Commands and safety behavior

Only fresh, non-forwarded messages from the whitelisted private chat **and sender** are accepted;
other chats are silently ignored. Commands are exact (no arbitrary arguments or remote mode switching;
the single typed portfolio halt-resume form is documented above).

| Command | Behavior |
|---|---|
| `/status` | Pause/fault/data/reconciliation/book freshness and latest signal |
| `/balance` | Simulated cash/base balances |
| `/positions` | Tracked base quantity, cost and software stop; offline warning |
| `/pnl` | Realized PnL and current mark-to-bid unrealized estimate |
| `/pause` | Block new entries; software stops/exits keep running |
| `/resume` | Resume manual pause only when safety gates are healthy; never clears risk/fault latches |
| `/stop` | Persist `data/KILL`, cancel tracked open orders and stop; **not liquidation** |
| `/mode` | Report PAPER; cannot change mode remotely |
| `/help` | Command summary |

Local persistent kill switch from another Command Prompt:

```bat
type nul > data\KILL
```

An independent watcher notices KILL while API requests are in flight; simulated submission checks it again
before committing. No software can undo a real request already transmitted to an exchange. Restart refuses
while KILL exists. After inspecting position/order state, deliberately remove **only that file** to allow a
future start. Ctrl+C stops without persisting KILL. Abrupt power loss cannot send a shutdown message.
Run the paper kill-switch test before considering real capital.

The order manager persists an intent before submission, accumulates partial fills exactly once, polls
server state, reconciles balances/open orders on startup and periodically, and confirms cancellation before
replacement. Unknown outcomes are never blindly resubmitted. Partial entries are managed, not topped up.
External orders/balance drift block trading rather than being silently adopted/cancelled.

On startup and after sleep/downtime the bot backfills missing closed candles, primes the newest signal,
and **does not enter from a signal produced while it was offline**. A continuously observed new close has
a short entry deadline and must be no older than one timeframe. Never trades on stale books/candles.
No retrospective fill is fabricated for an offline stop: only current executable prices can be used.

**Protection warning:** Nobitex documents stop_market/stop_limit/OCO, but their complete lifecycle is
UNVERIFIED here. PAPER positions have **software ATR stops only**. They are unprotected while the bot,
internet or laptop is offline, and can gap well beyond the stop. Graceful stop cancels orders but does not
sell holdings. Financial drawdown latches persist across restarts. API-error faults are latched conservatively;
diagnose them and archive/restart a PAPER experiment rather than manually editing database entries.

## Legacy history, CSV and backtest

With the environment activated:

```bat
python -m app.download_history
python -m backtest.run
```

If real history contains a venue outage gap, the default backtest refuses it. To explicitly evaluate
only the latest continuous segment, run `python -m backtest.run --latest-contiguous`. The report counts
excluded older bars and warns that the result does not represent trading through the omitted outage.

History downloads backwards in bounded 500-bar windows, caches each successful window, and stops after two
empty windows or the configured page ceiling (`--max-pages 100`, maximum 500). If a ceiling is reached it
does not claim the exchange has no older history. Failed downloads retain prior successful data.
The live public collector continuously caches current bars and backfills downtime gaps.

Alternative import/backtest:

```bat
python -m backtest.run --csv C:\private\btc_4h.csv
```

CSV columns: `timestamp,open,high,low,close,volume`. Timestamp must be **Unix seconds for candle OPEN**, rows
must be unique and exactly one timeframe apart, and all bars must be closed. Candles need positive valid
OHLC and nonnegative volume. Do not relabel other venues' data as Nobitex. Inadequate or gapped history is
reported honestly: no synthetic data is silently substituted and no missing candles are manufactured.
Historical DST/time-grid discontinuities may require a continuous later segment or properly sourced CSV.

Legacy outputs in `reports/` (the new portfolio command writes its own folders and root report;
the previously delivered legacy report is preserved as `legacy_4h_backtest_report.md`):
- `backtest_report.md`: metrics, benchmark, assumptions, weaknesses and verdict.
- `backtest_summary.json`: reproducible config and metric snapshot (no secrets).
- `market_candles.csv`: exact input, including warmup; its SHA256 is recorded in the report/summary.
- `backtest_trades.csv`, `backtest_equity.csv`, `backtest_equity.png`.
- `train_*`, `out_of_sample_*`: chronological 70/30 holdout with indicator warmup retained but excluded
  from evaluated time. No tuning on this holdout.
- `walk_forward.csv`: three expanding-window train-only parameter selections and disjoint test slices.
- `sensitivity.csv`: nine EMA-fast/ATR combinations, descriptive only (not independent evidence).

Replay the saved input without downloading revised venue candles:
`python -m backtest.run --csv reports\market_candles.csv --output reports\replay`.
Keep the same YAML settings and capital cap to reproduce the original metrics.

Same Strategy/Risk code as PAPER, with signal-on-close / fill-on-next-open, fees, slippage, entry-bar stops,
gap stops and non-retroactive trailing updates. Benchmark pays both-side modeled costs too. Historical
open fills do not model actual queues/spread/depth/outage latency; real/PAPER fills may be worse or rejected.
Too few trades, short history, underperformance and risk latches are disclosed, never hidden.

## Verification and paper-to-live checklist

```bat
python -m app.verify_exchange
```

Uses read-only calls, even when MODE=live. Without keys, public probes only; private probes are explicitly
skipped. **Exit 2 is expected while any UNVERIFIED live contract remains.** A read-only probe cannot prove
order placement/cancellation/fees/protection semantics, and this tool never clears those blockers by fiat.
See [docs/UNVERIFIED.md](docs/UNVERIFIED.md) for the missing live implementation/certification work.

When MODE=live is requested the app prints:
1. Backtest reviewed (including benchmark/trade count/weaknesses).
2. At least 2–4 weeks of PAPER results consistent with the model.
3. verify_exchange passes with no UNVERIFIED live contracts.
4. Confirmed exchange-side protection, or consciously enabled `ALLOW_UNPROTECTED_POSITIONS=true`.
5. MAX_CAPITAL_QUOTE is an amount affordable to lose.
6. Kill switch and all Bale commands tested.

Any future live release must also require a local interactive typed **`I UNDERSTAND THE RISK` on every
startup**; Task Scheduler/unattended restart must not bypass it. This build refuses live before asking
for an acknowledgment that cannot resolve its blockers. **Do not remove the guards to make it trade.**

## Native Windows deployment / Task Scheduler

Keep the laptop plugged in and connected. Settings → System → Power & battery → Screen/sleep:
**Never sleep when plugged in** (screen can turn off). Control Panel → Power Options → Choose what
closing the lid does → Plugged in: **Do nothing**. Ensure ventilation; a closed overheating laptop is
not reliable. Configure Windows Update **active hours**; updates/reboots can still interrupt operation.
This is not a server: no trading or software protection while off, sleeping, disconnected or updating.

Task Scheduler → Create Task:
- General: run as your normal user, **Run only when user is logged on** (visible PAPER console); avoid
  unnecessary administrator privileges. Trigger: **At log on**, optional 30-second network delay.
- Action: Program `C:\Windows\System32\cmd.exe`; arguments `/c ""C:\Users\ALIREZA\Desktop\nobitex-bale-trader\run.bat""`;
  Start in `C:\Users\ALIREZA\Desktop\nobitex-bale-trader` (no surrounding quotes in Start in).
- Conditions: do not configure it to force-stop on battery if you need a graceful stop; prefer a manual
  Ctrl+C before unplugging. Wake-on-task is optional and does not provide continuous uptime.
- Settings: allow manual start; **Do not start a new instance**; disable “Stop task if it runs longer than”.
  **Restart on failure every 1 minute, up to 3 times**. run.bat already backs off unexpected crashes;
  do not create two independent schedules. Task Scheduler may retry an intentional config refusal;
  safety gates still refuse it. KILL causes clean exit and suppresses the wrapper's restart.
- Test logon/reboot, real Bale commands and KILL in PAPER. Do not assume these UI instructions were
  exercised on your Windows account. “End task” is not guaranteed to be graceful.

## Tests and troubleshooting

```bat
python -m pytest -q
ruff check .
ruff format --check .
python -m app.main --smoke-seconds 30
python -m pip check
```

Tests block external sockets (except Windows asyncio's internal loopback socketpair), use temporary SQLite
and mocked exchange/Bale calls, and **cannot place real orders**. The online smoke uses only public data.
It succeeds only if at least one healthy candle-data cycle completes; network-failure smoke is not called a pass.

| Symptom | Action |
|---|---|
| API timeout/403 | Check official Nobitex status, Iran-origin access requirements, ISP, clock and connectivity. Do not weaken TLS or trade on cached stale prices. HTTP proxy environment is not automatically trusted. |
| Insufficient history | Download more/collect over time, or import sourced CSV. No meaningful result exists without enough closed bars. |
| Grid/gap error | Venue may have missing bars or a DST/grid change; inspect timestamps. Do not synthesize prices or edit timestamps to force a pass. |
| LIVE refused | Expected. Unverified real execution and protection are intentionally disabled. |
| Bale no messages | Both token/chat fields must be set; start the bot's private conversation; verify whitelist ID and internet access. Console fallback remains. No unofficial wrappers/webhook needed. |
| Commands ignored | Only the exact private whitelisted sender/chat is allowed. Old, forwarded, edited, bot, group or argument-bearing commands are ignored. |
| Another instance/storage failure | Check the running task/process, folder permissions and disk. Never delete DB/lock files to defeat a running instance. |
| Config changed / latched risk | Stop, preserve the logs and state. For a fresh PAPER experiment, archive `paper.db` after shutdown, then start a new account. Never reset live state to hide a loss. |
| KILL present | Review remaining holdings/open orders; remove only `data/KILL` deliberately if you intend to restart. |

## Risk disclaimer

No profit, loss ceiling, bug-free behavior, uninterrupted service or fitness for real capital is promised.
Backtests can overfit; low trade counts and favorable historical periods are weak evidence. Fees/spreads,
slippage, thin liquidity, order gaps, exchange/custody/counterparty failure, internet/power failures and laptop
downtime can wipe out capital. A stop is not a guaranteed price. Review local laws and exchange terms.
This is a software/research deliverable, not financial advice or permission to trade unsafely.
