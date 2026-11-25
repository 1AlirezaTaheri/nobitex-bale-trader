# Validation record — final audit context 2026-11-25

## Final product engineering, 2026-11-25 — investment performance still NOT VALIDATED

Evidence for this mission is isolated under `reports/final_product/`. All seven frozen variants
remain category 1 / NOT VALIDATED. There are zero new strategy candidates, zero new historical
parameter searches and zero genuine forward observations. No exchange order/cancellation or real
Bale request/message was made. No dependency was installed and requirements.lock is unchanged.

| Check | Actual result / evidence |
|---|---|
| Final full suite | **304 passed**; pytest_full_005.log / .xml; execution JSON records the actual runtime |
| Earlier full suites | 001: 289 passed, 2 failed; 002: 293 passed; 003: 298 passed; 004: 304 passed; retained, not overwritten |
| Focused pre-recovery suite | 93 passed; pytest_focused_001.log / .xml; not substituted for final full coverage |
| Ruff check / format check | Both exit 0 in quality_003.json; corresponding logs retained |
| pip check / compileall | Both exit 0 in quality_003.json; compatibility/compilation only, not vulnerability certification |
| Real frozen snapshot replay | frozen_replay_001 completed exit 0 in 372.49 seconds; **30/30 artifacts byte-identical** to results_verified_002, including charts |
| LIVE refusal | live_refusals_003.json: all seven entrypoints exit 2; the final full suite also covers forced-ASCII CLI output and refuses MODE=live |
| Final public-only smoke | shadow_smoke_003, 20-second requested duration (22.74 seconds including startup), exit 0, **zero snapshots/intervals**, no Bale; operations_003.json |
| Old-root refusal | operations_003.json: exit 2 before DB/network work; before/after hashes of all eight files identical |
| Weekly report | Local JSON/CSV/English/Persian/PNG generated successfully at weekly_20261125T044752298983Z; no delivery requested |
| Chart inspection | Model visually inspected final PNG; readable zero-data message in every panel, no fabricated performance curve or overlap |
| Offline doctor | doctor_003.log: one FAIL for invalid local optional Bale configuration; local DB/chain/disk/registration checks pass; delivery/hardware/time anchoring UNVERIFIED |
| setup.bat --check-only | Exit 1 because doctor fails on that local configuration; pip check passes; .env was not rewritten |
| Configured-secret scan | configured_secret_scan_001.json: zero configured-secret matches outside .env in 562 text files at that stage; final scan 002 records its actual count; heuristic limitations explicit |
| Process audit | process_inventory_001.json: zero project processes excluding the audit wrapper/ancestors; no unrelated process terminated |

Final machine-readable summaries and before/after source hashes are published as final_validation.json,
integrity_after.json and completion_manifest.json; the evidence index excludes its own hash by design.
Hashes prove local consistency, not independent authorship, UTC or tamper resistance against a full rewrite.

Corrections are explicit in FINAL_PRODUCT_AMENDMENTS.md: synthetic checkpoint fixture and an old test's
unnecessary .env loading; invalid optional notification settings now fall back to console while MODE
remains fail-closed; non-object receipt refusal; UTF-8 diagnostics under redirected Windows output;
and compatibility checking before SQLite. The initial LIVE drill had one unexpected exit 1 caused
by UnicodeEncodeError while printing a safe refusal, not by a LIVE operation. The first old-root
check created SQLite WAL/SHM sidecars before refusing; operations_002.json therefore correctly says
unchanged=false. It is preserved alongside the corrected unchanged=true run, not relabeled PASS.
No observation was appended during either refusal attempt.

Real user-operated Bale discovery/delivery, physical sleep/lid/reboot/power-loss, registered Windows
tasks, independent UTC/hash anchoring, advisory-backed vulnerability scanning, multi-month performance,
full primary-literature access/replication and private/executable exchange contracts remain UNVERIFIED.
Some source pages failed and a commercial stress source has inconsistent date footnotes; the research
access ledger downgrades those items. This engineering release is not a completed systematic review
or evidence that automation beats constant mix at matched risk.

## Final adversarial audit — weaknesses and verdict FIRST

**All seven frozen strategy variants remain category 1 / NOT VALIDATED.** Historical reuse contaminates
all previous holdouts; the old final-audit manifest does not authenticate the current protocol. Its
earlier document provenance remains unresolved. Amendments 001–003 disclose the mismatch and later
reporting corrections. There was no parameter retuning, enabled-flag change, real order/cancellation
or credential use for trading. The unchanged V3 preregistration SHA256 is
`6f26ccabb14fa92b477a94b873f3309a0eb9b30a3d873118def5fa81ec3489af`.

The final-audit protocol SHA256 is `ce32f959aeb29a5f914fb0c44d010d1f49243f71170f05b01ab4c9994e644911`,
bound by amendment 001, not authenticated by the incompatible old manifest. Inventory: 262 archived
configuration rows +25 audit series, M=287. With 999 draws the minimum adjusted add-one tail is 0.287;
no adjusted significance pass is possible. Uncentered sign tails are descriptive, not exact p-values.

| Check | Observed result / evidence under `reports/final_audit/` |
|---|---|
| Full offline suite, final runtime code | **239 passed in 44.49s**, 0 failures/errors/skipped; `pytest_final_002.log` /`.xml` |
| Focused audit/SHADOW/operations tests | **46 passed in 20.47s**; includes color, stopped-run checkpoint and blank-credential regex regressions |
| Earlier full runs retained | 235 passed /238 passed, then the 239-test final run; not interchangeable counts |
| Ruff check /format, compileall, pip check | All exit 0; final `quality_checks_final_002.json`, 66 Python files formatted; earlier 65-file evidence retained; vulnerability scanning is NOT RUN |
| Original historical replay | **30 artifacts byte-identical**; `byte_replay_check.json`, immutable `results/` and `replay/` |
| Initial color-corrected full rerun attempt | Both 300-second runs timed out after four preliminary files; `results_verified/` /`replay_verified/` are incomplete, not validated outputs |
| Recovery rerun | **PASS**: both fresh `_002` runs exit 0 in 357.681/355.479s; 30 artifacts byte-identical, all 24 non-chart artifacts match the original; `byte_replay_verified_002.json` |
| Actual-input V3 parity A–D | PASS: each 905 exact timestamps/segments, returns/equity/exposure and 11 aggregates within 1e-9; `v3_actual_input_parity.json` |
| Real local process kill /suspend drills | 3/3 PASS, all owned children reaped; only a child process was suspended, not the laptop; `operations/reliability.json` |
| LIVE refusal routes | Five exit-2 refusals: legacy, portfolio, timing A, timing D, SHADOW; no exchange write |
| Public bounded probe | 15 requests in 15.255s, 12 HTTP200 /3 HTTP403, no retry/timeout/429; tiny startup-heavy sample, not an SLA |
| IRT coverage | BTCIRT 905 matches; USDTIRT three history403 responses, no complete FX, units unverified; no translated equity invented |
| Corrected heuristic security scan | 226 text files; one synthetic token-shape fixture in a test, no credential-assignment or PEM findings; original scans preserved |
| Genuine SHADOW smoke | **CLOCK_REFUSAL**, exit 2 in 2.742s at 2026-11-24T23:06:11.096013+00:00; zero snapshots, not a successful forward run |
| Weekly CLI example | Exit 0, `weekly_initial/`, zero snapshots, null clean returns and PENDING 3/6-month checkpoints |
| Preservation | 270/272 baseline hashes unchanged; only intentional in-progress audit runner/core exceptions; no frozen legacy/config/data/cache/old-report drift; `integrity_after.json` |
| Visual inspection | All five corrected PNGs plus the empty zero-data weekly chart inspected; `visual_qa_final.json` |
| Final process check | Zero Python/pytest/Ruff processes at 2026-11-24T23:21:28.0923802Z; no unrelated process terminated; `process_audit_final.json` |

The developer-context date is 2026-11-25; measured execution UTC was still 2026-11-24. The not-before
gate is **2026-11-25T00:00:00+00:00** and was not bypassed. A trustworthy future clock and naturally
observed boundaries are required. No historical warmup or synthetic fixture counts as forward evidence.

The historical comparison uses 700+205 evaluated days without bridging the gap. S1 full/L1 cover only
700 days and have zero trades due to modeled depth. Their missing complete five-asset second cohort
was not replaced with the older 203-day report. Native S0/S1 exposure/cost/B7, fresh starts, full native
delay/crash tests and executable same-turnover random schedules remain unavailable, not passes.

B4_25's +36.27% return /−7.99% daily MaxDD is the lowest DD only among registered positive-return
B4/B5 mixes, not a universal winner. S0's lower daily DD uses a different execution model and its 2x-cost
return is −1.68%. The full comparison, CIs, stresses and caveats are in `reports/final_audit/report.md`;
operations in `operational_report.md`; future observation rules in `FORWARD_FRAMEWORK.md`.
Use fresh output directories for every replay/report and retain prior evidence. See
[RISK_REGISTER](RISK_REGISTER.md), [ASSUMPTIONS](ASSUMPTIONS.md), [UNVERIFIED](UNVERIFIED.md).

The sections below are preserved **earlier release evidence**, not claims of a clean current holdout,
the latest suite size, current connectivity or authorization to deploy funds.

## Release verdict

**LayeredPortfolio is NOT VALIDATED and remains disabled by default.** Software checks passed, but both
real-input research samples failed the frozen acceptance criteria. The latest portfolio PAPER smoke
failed before startup because the public options endpoint was unavailable after bounded retries;
an earlier short portfolio smoke passed. These are distinct observations, not continuous uptime.
**LIVE trading is not operational in this release.** No real exchange order/cancellation, withdrawal or transfer was submitted. No production
exchange or Bale secret was supplied. Passing these checks is neither a proof of correctness nor a
profitability, security or live-execution certification.

Local environment: Windows 11 (`10.0.26300`), 64-bit Python **3.13.10**, project-local `.venv`.
Other OS/Python combinations have a CI workflow definition but were not executed here. This folder
is not a Git repository; no CI run, commit or push is claimed.

## Strategy V3 daily timing — NOT VALIDATED

All four candidates remain disabled by default. The [frozen protocol](STRATEGY_V3_PREREGISTRATION.md)
is unchanged (SHA256 `6f26ccabb14fa92b477a94b873f3309a0eb9b30a3d873118def5fa81ec3489af`). No
parameters were selected or adjusted after observing results. The final timing-null report compares
shifted return and Calmar to the actual strategy; that reporting correction did not change any
candidate economics or acceptance decision.

The backtest read the real public cache without writing to it. Of 2,750 exact BTC/ETH common
timestamps, two segments (1,000 and 505 input candles) could supply 300 warmup candles each. This
left 905 evaluated days, including 227 holdout observations. No candles were synthesized, interpolated
or bridged. The price-only model used 0.25% quote fees plus 0.15% adverse slippage per side; the largest
recorded public USDT taker tier was 0.13%. Stress runs doubled and tripled both model costs. Volume is
not used in these simulations; sampled zero volumes from public UDF are in `reports/v3_data_quality_probes.json`.

| Run | Net return | Max DD | Holdout net return | Failed criteria |
|---|---:|---:|---:|---|
| A | +60.83% | -42.32% | -9.22% | 2, 3, 4, 5, 7 |
| B | +107.02% | -37.19% | -6.14% | 2, 3, 4, 5, 7 |
| C | +115.20% | -32.30% | -6.08% | 2, 3, 4, 5, 7 |
| D | +74.35% | -25.15% | -7.93% | 2, 4, 5 |
| BTC buy-and-hold | +180.12% | -28.95% | — | — |
| BTC+ETH equal-weight buy-and-hold | +87.59% | -41.37% | — | — |

D exceeded its matched-exposure control on both Calmar and Sharpe, but not the preregistered
buy-and-hold drawdown threshold; it also failed holdout and one-at-a-time ±20% robustness. No
candidate was promoted. Monthly DCA/hold can be used as a simple comparison, or timing research can
continue in forward PAPER only. These are historical diagnostics, not evidence of executable returns.

| Check | Observed result |
|---|---|
| Full offline suite | **193 passed** |
| Ruff lint/format, `compileall`, `pip check` | **PASS** |
| Snapshot replay | **19 files byte-identical**, including JSON, CSV, Markdown and input snapshot files; `reports/timing_v3_artifact_audit.json` |
| Online candidate A, 30-second PAPER loop | **PASS**: two healthy data cycles, exit 0, clean reconciliation; `reports/timing_v3_paper_smoke.txt` |
| Smoke state and process audit | Zero intents and zero simulated orders; 100 USDT, zero BTC, no remaining project bot/replay process. Pre-existing wallet/cache files and cache sidecars had identical before/after hashes; `reports/timing_v3_smoke_audit.json` |

The smoke covered public data, startup, stale-signal suppression and shutdown, **not** a naturally
triggered buy/sell. Offline tests exercised order cancellation on insufficient depth, scaling and
reductions, restart reconciliation, explicit routing, stop/pause, and state/cache isolation. Neither
the smoke nor a passing replay authorizes LIVE. Use unchanged YAML and legacy symbol-rule evidence
to replay, and choose a fresh output directory:

```bat
.venv\Scripts\python.exe -m backtest.timing_v3 --snapshot reports\timing_v3\inputs --output reports\timing_v3_new_replay
.venv\Scripts\python.exe -m app.audit_timing_v3 --source reports\timing_v3 --replay reports\timing_v3_new_replay
```

## Final LayeredPortfolio software and operational checks

| Check | Observed result / evidence |
|---|---|
| Full offline suite after final runtime changes | **165 passed in 11.67s**; `reports/pytest_portfolio_final.txt` |
| `python -m ruff check .` | **PASS**, all checks passed; `reports/ruff_check_portfolio_final.txt` |
| `python -m ruff format --check .` | **PASS**, 49 files already formatted; `reports/ruff_format_portfolio_final.txt` |
| `python -m pip check` | **PASS**, no broken requirements; `reports/pip_check_portfolio_final.txt` |
| Primary actual-input backtest and offline replay | Completed; **NOT VALIDATED**; `reports/portfolio/` and `reports/portfolio_replay/` |
| Supplemental recent backtest and offline replay | Completed; **NOT VALIDATED**; `reports/portfolio_recent/` and `reports/portfolio_recent_replay/` |
| Primary artifact audit | **PASS**: 6 hashed input files, 701 equity rows, 0 trades, 4 PNGs, exact JSON/CSV replay; `reports/portfolio_artifact_audit.txt` |
| Recent artifact audit | **PASS**: 6 hashed input files, 204 equity rows, 7 trades, 4 PNGs, exact JSON/CSV replay; `reports/portfolio_recent_artifact_audit.txt` |
| Four charts per sample | Visually inspected equity/benchmark, drawdown, sleeve equity and monthly heatmap; data audit is separate |
| Earlier `run.bat --portfolio-paper --smoke-seconds 30` | **PASS**, 2 healthy data cycles, cash only, clean all-symbol shutdown; `reports/portfolio_paper_smoke.txt` |
| Final portfolio smoke after summary/risk-notification edits | **FAIL**, exit **1** before startup: `Nobitex options unavailable after bounded retries`; `reports/portfolio_paper_smoke_final.txt` |
| Two current legacy smoke attempts | **FAIL** before startup with the same bounded options error; `reports/legacy_paper_smoke_after_portfolio.txt`, `reports/legacy_paper_smoke_retry.txt` |
| Current public `app.verify_exchange` | **FAIL**, candles unavailable after bounded retries; private reads skipped, all six LIVE blockers retained; `reports/public_verification_portfolio.txt` |
| LIVE startup with `--portfolio-paper` | **PASS refusal**, confirmed exit **2**; `reports/portfolio_live_refusal.txt` |
| Final local state | PAPER mode, portfolio/breadth disabled, expected legacy strategy values retained, both wallet files present, shared process lock available; `reports/portfolio_final_state.json` |
| Final process inspection | **0** matching project/bot/test Python processes at inspection; `reports/portfolio_process_audit.json` |

The earlier successful portfolio smoke predates the last daily-summary observation and risk-block-ended
notification changes. The final offline suite covers the final code; the attempted online smoke of that
code did not reach startup. Neither short smoke exercised an organic online buy/sell. No network guard,
freshness requirement or retry bound was weakened to obtain a pass.

The 165-test suite blocks external sockets and uses temporary state/mocked HTTP. Added coverage includes
closed-candle causality, next-open timing, raw gaps, zero-volume no-fills, layer precedence, no same-bar
re-entry, persistent rejected exits, fee-aware caps and sleeve budgets, held-asset correlation, daily-loss
boundaries, persistent DD/cooldown/halt state, typed resume, stale startup/wake suppression, multi-symbol
ledger drift, ambiguous-fill restart recovery, whitelist/edited-command guards, snapshot tampering and
historical/PAPER feature/size/fill/stop parity for identical synthetic input. This does not certify a venue.

## Actual-input research coverage and limits

- Frozen real markets: **BTC/USDT, ETH/USDT, XRP/USDT, SOL/USDT, DOGE/USDT**. The public liquidity screen,
  candidate exclusions and full raw gaps are in `reports/universe.md` and `.json`; the original failed
  >=750-consecutive-bar screen is preserved separately. Before return evaluation, history eligibility
  changed to >=750 raw bars plus >=301 recent consecutive current-grid bars. This change is disclosed,
  not described as passing the initial rule. No return ranking selected the markets.
- Preserved full daily histories: BTC **2,951**, ETH **2,750**, XRP **2,751**, SOL **1,557**, DOGE **2,141**
  actual rows. Current-grid epoch remainder is **73800** (20:30 UTC); older DST remainder is **70200**.
  Genuine gaps, including 13-17 missing days in June/July 2025, were not filled or relabeled.
- **Primary longest common continuous segment:** 1,000 inputs per asset, 300 warmup /700 evaluated days,
  **2023-07-18 20:30 to 2025-06-17 20:30 UTC**. All reported volumes are zero: 232 modeled-depth entry
  rejections and no trades. This is an input limitation, not evidence of zero historical market activity.
  Primary final-25% holdout: 175 days from **2024-12-24 20:30 UTC**. The primary result was not replaced.
- **Supplemental latest continuous segment:** 503 nonzero-volume inputs per asset, 300 warmup /203
  evaluated days, **2026-04-30 20:30 to 2026-11-19 20:30 UTC**. Final-25% holdout: 51 days from
  **2026-09-29 20:30 UTC**. Only seven completed trades; no reliable edge claim is possible.
- Initial capital **100 USDT**. Per side: fee **0.25%**, adverse slippage **0.15%** and assumed half-spread
  **0.10%**. No historical L2 archive exists: one modeled executable level with capacity **0.10% of prior
  closed daily base volume per IOC**. Zero volume means zero capacity; no invented/substituted liquidity.
  PAPER uses actual fresh public books instead. Daily OHLC cannot reveal true intraday equity minima.
- Exact evaluated CSVs, raw timestamps and SHA256 live in each output's `inputs/manifest.json`. Each also
  contains equity, trades, monthly results, six ablations, three benchmarks, fixed holdout, three train-only
  walk-forward folds, 31 sensitivity cases, 14 one-factor/joint +/-20% cases and 2x/3x fee/slippage stress.
  A hash/replay verifies consistency, not the exchange's historical accuracy or executable liquidity.

## All eight frozen acceptance decisions

| Criterion | Primary longest segment | Supplemental recent segment |
|---|---|---|
| At least 100 completed trades | **FAIL**: 0 | **FAIL**: 7 |
| Positive net return at baseline and 2x costs | **FAIL**: 0.00% /0.00% | **FAIL**: +0.08% /-0.33% |
| Positive fixed final-25% holdout return | **FAIL**: 0.00% | **FAIL**: -0.86% |
| Profit factor greater than 1.30 | **FAIL**: undefined | **FAIL**: 1.119 |
| Maximum drawdown no worse than 25% | **PASS**: 0.00%, no trades | **PASS**: -2.27% daily-close DD |
| Calmar better than equal-weight buy and hold | **FAIL**: undefined vs 1.522 | **PASS**: 0.066 vs -1.149 |
| Robust to +/-20% perturbations | **FAIL**: no positive baseline | **FAIL**: returns -0.28% to +0.34% |
| Combined drawdown no worse than worst pure single trading layer | **PASS**: all 0.00%, no trades | **FAIL**: -2.27% vs worst single -1.70% |

**Both verdicts: NOT VALIDATED.** Numerical passes on a zero-trade account provide no validation evidence.
Perturbation requires positive baseline and every one-factor/joint case positive and retaining >=50%
of baseline return. No criterion, parameter or enabled flag was changed to hide failure.

## Supplemental ablation and three benchmarks

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

Full combination does **not** reduce drawdown versus either standalone trading layer, or improve
Calmar/Sharpe versus L1. Standalone sleeve daily-return correlation is **0.214628**; combined-account
PnL-contribution correlation is **0.110807**. Correlation alone did not produce useful diversification.
Recent 3x cost return is **-0.68%**; 31 sensitivity returns range **-0.75% to +0.93%**. Three losing positions
triggered three cooldown days. Walk-forward test returns are **0.00%, +1.69%, -0.19%**, with independent
cash/risk per fold, selected only using expanding pre-holdout training. No candidate was deployed.

Primary ablations all have zero return, zero DD and zero trades; Sharpe/Sortino/Calmar/PF are undefined.
Primary benchmarks: equal-weight +218.03% /-54.48% DD; BTC +246.01% /-27.98% DD; matched legacy 4h
+3.88% /-4.09% DD, 21 trades, PF 1.618. Buy-and-hold benchmarks use fractional units and round-trip
costs, not portfolio risk/depth caps. Legacy keeps its old fill model and 4h DD observations, with daily
Sharpe/Sortino sampling. Full primary tables remain in `reports/portfolio/backtest_report.md` and root
`reports/backtest_report.md`; the recent result is `reports/portfolio_recent/backtest_report.md`.

## Reproduce current evidence (Windows Command Prompt)

```bat
cd /d C:\Users\ALIREZA\Desktop\nobitex-bale-trader
set MODE=paper
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m pip check
.venv\Scripts\python.exe -m backtest.portfolio_run
.venv\Scripts\python.exe -m backtest.portfolio_run --segment latest --output reports\portfolio_recent
.venv\Scripts\python.exe -m backtest.portfolio_run --snapshot reports\portfolio\inputs --output reports\portfolio_replay
.venv\Scripts\python.exe -m backtest.portfolio_run --snapshot reports\portfolio_recent\inputs --output reports\portfolio_recent_replay
.venv\Scripts\python.exe -m app.audit_portfolio --source reports\portfolio --replay reports\portfolio_replay
.venv\Scripts\python.exe -m app.audit_portfolio --source reports\portfolio_recent --replay reports\portfolio_recent_replay
run.bat --portfolio-paper --smoke-seconds 30
run.bat --portfolio-paper
.venv\Scripts\python.exe -m app.verify_exchange
```

The continuous PAPER command intentionally runs until stopped; do not execute it concurrently with
another runner or the smoke. Ordinary `run.bat` remains legacy 4h BTC with `data/paper.db`; explicit
portfolio PAPER uses `data/portfolio_paper.db`. Both share KILL/process locking. `portfolio.enabled`
remains **false**; the explicit flag is an unvalidated research opt-in, never a live authorization.

## Historical legacy validation record (earlier delivery)

The following 125-test record and successful legacy online probes are preserved as **historical evidence**.
They are not the final suite size or the current connectivity result. The earlier legacy report now lives
at `reports/legacy_4h_backtest_report.md`; root `reports/backtest_report.md` is the primary portfolio report.

### Earlier completed checks

| Check | Observed result |
|---|---|
| `setup.bat` | Completed, pinned dependencies installed, existing data preserved, secret-free `.env` created only when absent |
| `python -m pytest -q` | **125 passed in 9.68s**; final output in `reports/pytest.txt` |
| `ruff check .` | All checks passed |
| `ruff format --check .` | 36 Python files formatted |
| `python -m pip check` | No broken requirements found |
| Public `python -m app.verify_exchange` | Earlier online run passed candles, fresh book, public rules/fee schedule; private probes explicitly skipped |
| `MODE=live` startup | Refused with confirmed process exit **2**, checklist, offline-protection warning and six live blockers |
| `run.bat --smoke-seconds 30` | Final online run completed **2 healthy cycles**, clean reconciliation, remaining BTC **0** |
| Persistent KILL process drill | Ordinary app process stopped cleanly after test-owned KILL appeared; file persisted through exit; `reports/kill_smoke.txt` records `KILL_SMOKE_PASS=True` |
| `python -m backtest.run --latest-contiguous` | Completed on cached real public candles, including holdout, sensitivity, walk-forward, CSV/JSON/PNG artifacts |
| Exact-input replay audit | Snapshot SHA256 matches report/summary; replay reproduced all full-sample metrics; see `reports/artifact_audit.txt` |

The suite uses temporary SQLite and mocked HTTP. External socket connections are blocked; Windows
asyncio's internal loopback socketpair is allowed. These tests cannot send real trading requests.
Coverage includes indicators and causality, position sizing, risk latches, two-sided costs, gap/entry-bar
stops, non-retroactive trailing, stale data, persistent pause/KILL, independent BTC and cash ledgers,
partial cumulative fills, cancellation confirmation, unknown outcomes and crash recovery. Final added
runner regressions confirm that a failed control task cannot skip financial shutdown reconciliation,
and a failed shutdown is not returned as a successful run. Manual pause still allows an existing stop.

The final short PAPER run remained flat; it validates startup/data cycles/shutdown, **not** a naturally
triggered online buy/sell. Simulated trade and stop execution paths were exercised offline by tests.
No bot process is intentionally left running for delivery.

### Earlier legacy data and provenance

- Cache at inspection: **8,923 unique BTC/USDT 4h candles**, sourced from Nobitex public endpoints.
- A genuine gap follows `2025-06-18T04:30:00+00:00`; the next row is
  `2025-07-01T12:30:00+00:00`: **79 missing 4h bars**. Missing prices were not manufactured.
- Default backtesting rejects nonconsecutive rows. The explicit `--latest-contiguous` sample uses
  **3,041** rows and discloses **5,882** excluded older rows. This selection can bias conclusions and
  does not demonstrate how trading would have performed through the omitted outage.
- Warmup: **602** rows; evaluated bars: **2,439**.
- Evaluation UTC: **2025-10-09 20:30** to **2026-11-20 08:30**.
- Exact input including warmup: `reports/market_candles.csv`.
- SHA256: `d0d0c6927691028f99cf7b69cb7bdb900487b12a7a50b84db47cf1563b3df80b`.
- Modeled fee per side: **0.25%**; adverse slippage per side: **0.15%**; initial capital: **100 USDT**.
  These are modeling assumptions, not verified historical fee/fill contracts.

With unchanged YAML settings and capital cap, replay the snapshot using:

```bat
.venv\Scripts\python.exe -m backtest.run --csv reports\market_candles.csv --output reports\replay
```

The original public cache can grow/change later; the saved snapshot, not a future download, identifies
the evaluated input. A hash detects changes; it does not independently certify the venue's price history.

### Earlier legacy sample results

| Metric | Strategy | Buy and hold |
|---|---:|---:|
| Total return | -0.23% | -49.22% |
| CAGR | -0.21% | -45.60% |
| Maximum drawdown | -3.02% | -51.96% |
| Sharpe | -0.0420 | -1.2553 |
| Sortino | -0.0873 | -1.7126 |

Strategy: **8 trades**, win rate **37.50%**, profit factor **0.9241**. Chronological holdout:
**+1.17%**, benchmark **-7.19%**, only **5 trades**. The strategy lost money over the full sample.
Outperforming a falling benchmark is not evidence of positive expected return. Trade counts are far
too small for a reliability claim. Walk-forward folds are independent accounts, not one continuous
return series. Some folds underperform their benchmark; no parameter winner is automatically deployed.

`reports/legacy_4h_backtest_report.md` includes model weaknesses. Historical opens and intrabar stops cannot
reconstruct actual spread, queues, contemporaneous depth, stop latency or laptop outages. Current
precision assumptions are not a historical rules archive. End-of-test liquidation is a convention.
The equity PNG was visually inspected; no visual claim substitutes for the CSV/metric audit.

### Earlier failed attempts and limits of the evidence

Public connectivity intermittently failed with connection timeouts/bounded-retry errors during
development. Some history downloads and an early KILL harness failed before startup. Later downloads,
public verification and multiple PAPER smokes succeeded. This is **not** evidence of continuous uptime.

An intermediate KILL harness used smoke mode and stopped before any healthy cycle: smoke correctly
reported failure despite clean shutdown. The final KILL drill instead ran ordinary `app.main` and
confirmed clean exit plus the persistent flag. Only the flag created by that test was removed afterward;
no operator-owned flag or financial database was deleted.

## Remaining unverified / incomplete work

1. **LIVE execution remains disabled**, including real placement/cancellation and a certified protective
   order lifecycle. The six blockers are `authenticated_read_contract`, `executable_symbol_precision`,
   `fee_currency_and_fill_accounting`, `live_limit_and_cancel_semantics`, `native_protection_lifecycle`
   and `terminal_client_order_id_recovery`. Successful reads cannot resolve them.
2. Nobitex documents native stops/OCO, but no real protection is active here. PAPER stops are software-only
   and cannot protect an offline laptop. Unknown terminal client-ID recovery is particularly important
   because documented client-ID lookup is limited to open orders.
3. Real Bale delivery/control with the owner's token/chat has not been exercised. Whitelist and protocol
   behavior are mocked/tested, not production-validated.
4. Two to four weeks of PAPER observation, actual suspend/reboot/power-loss behavior, Task Scheduler
   deployment, Windows shutdown deadlines, ISP outages and OS/Python variants need operator validation.
5. No independent security review, financial audit, formal verification or regulatory review was performed.

See `docs/UNVERIFIED.md` for API sources and live prerequisites, `docs/ASSUMPTIONS.md` for deliberate
choices, and `docs/OPERATIONS.md` for recovery drills. Do not fund this release or remove guards to
turn the PAPER laboratory into an uncertified live trader.
