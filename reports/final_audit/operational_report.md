# Final audit — operational and security evidence

## Weaknesses FIRST

- These are short, local/mock or public-read observations, not an SLA, penetration test or LIVE certification.
  Historical holdouts remain contaminated; manifest provenance remains unresolved. No tuning or LIVE promotion.
- The context date 2026-11-25 differs from observed execution UTC. Clock-gated SHADOW refusal is not a
  successful forward run. There are no genuine forward performance observations at delivery.
- No real Bale delivery, laptop-wide suspend, Windows Task Scheduler deployment, abrupt power failure,
  real cancellation race or every possible LIVE bypass was certified. No secrets or exchange writes were used.
- Dependency vulnerability scanning was **NOT RUN**: no offline advisory database/scanner was available.
  `pip check` checks installed dependency compatibility, not known vulnerabilities.
- Hash chains require an independently exported anchor. They cannot prove absence of a complete malicious rewrite.

## Local process-fault and refusal evidence

Source: `operations/reliability.json`. Test-owned children only were killed/suspended; unrelated processes
were never terminated. These durations include local Python startup, not venue recovery latency.

| Check | Observation |
|---|---|
| Actual own-child termination mid-cycle | PASS; uncommitted marker absent, 0 orders/quantity, reconciled; restart wall 2.483s |
| Actual own-child termination mid-order | PASS; exactly 1 PAPER order and 0.1 BTC, no active intents/duplicate submission; restart wall 2.840s |
| Actual same-child process suspend/resume | PASS; 0.252s pause; not laptop/OS sleep |
| LIVE refusal: legacy /portfolio /timing A /timing D /independent SHADOW | All five return exit 2; isolated test state; no credential loader for legacy tests |

Offline tests separately exercise stale/skew/gap rejection, fixed A/D target parity, locked/corrupt SQLite,
snapshot/index recovery, hash tampering/deletion, changed config, retained closed-candle revisions, KILL,
mock timeout/partial fills/reconciliation, redaction and command-whitelist contracts. Passing tests are not
proof of all crash points, filesystem atomicity, disk survival or safe real orders.

## Public-only probe: tiny bounded sample

Source: `operations/public/public_probes.json`, `requests.csv`, `telemetry.db`, `raw/` and `raw_hashes.json`.
Observed completion UTC: **2026-11-24T22:57:10.770660+00:00**. Elapsed **15.255s**. Data are read-only;
there is no authentication, placement, cancellation, withdrawal or transfer request.

| Measurement | Observed value |
|---|---:|
| Requests | 15 |
| HTTP 200 /403 | 12 /3 |
| Timeout /retry /HTTP429 | 0 /0 /0 |
| Latency p50 /p95 /max | 0.424 /1.019 /1.212 seconds |
| First options response | 1.212 seconds |
| CPU time | 0.65625 seconds |
| Working set | 122,449,920 bytes |
| Request CSV /telemetry SQLite | 1,661 /8,192 bytes |

Retry count is zero **by design**, not proof retries are unnecessary. Startup-to-SHADOW-ready was not
measured by this probe and remains unavailable. The existing 6,016-byte prior log has 39 JSON records
but no parsed timestamps under the inspected keys; no daily growth/ready-time was invented from it.

Linear 30-day projections from this 15-second startup-dominated sample are 282,229,417 log bytes and
1,391,946,651 database bytes. They are **VERY LOW CONFIDENCE**, not capacity-planning estimates;
SQLite page allocation and one-time setup dominate. A representative long-running observation is needed.

## Genuine IRT coverage, not fabricated FX

BTCIRT returned 905 validated candles at all 905 exact needed timestamps. USDTIRT metadata returned
200, but **all three history pages returned HTTP403** and yielded zero usable FX candles. The metadata
said `IRT` without explicitly establishing toman vs rial under the conservative unit-verification rule.
Consequently quote units were not certified, no BTC-implied cross-rate was used, and **no IRT equity
translation/rank-change table was manufactured**. Coverage-only CSVs are retained, including the empty
USDTIRT output. This does not prove that the venue has no USDTIRT history; it describes these requests.

## Security scan correction and limits

Original `operations/security.json`: 185 text files, flags in four files. `security_review.json` safely
compared counts against existing example content without displaying values. Later diagnosis found
the credential-assignment regex could cross a newline after an empty `=`. Those four flags were
cross-line false positives, not evidence of a confirmed credential leak. The original scan/review remain.

The corrected horizontal-whitespace-only scan is recorded independently in `operations/security_final.json`:
**226 text files**, one token-shape finding in a deliberately synthetic fixture in
`tests/test_final_audit_ops.py`, no credential-assignment or PEM findings. A separate fixture review
records its source hash without printing the synthetic value. Its regression test prevents blank
assignments from consuming the following line. Findings are counts and filenames only; a zero count
would **not** prove secret absence or compromise freedom. `.env` is
ignored, `.env.example` exists, and no Git repository/history is available to audit historical remote leaks.
Real credentials were not loaded for trading or displayed. There is no independent security audit.

## SHADOW smoke and weekly CLI

`smoke_evidence_001.json`: at execution UTC **2026-11-24T23:06:11.096013+00:00**, independent SHADOW
refused before network/startup with exit **2**, in **2.742s**, because not-before is
**2026-11-25T00:00:00+00:00**. This is **PASS of the clock-refusal contract**, not a successful data
cycle or forward performance run. Neither the clock nor registration was bypassed.

The weekly CLI returned exit 0 and wrote `weekly_initial/weekly.md`, `.json`, `accounts.csv`, `curves.csv`
and `weekly.png`: zero snapshots, no clean returns, no trades, both checkpoints PENDING for A/D.
The displayed 100 USDT account values are initial research capital, not an actual observed balance.

## Final software and preservation checks

Final test logs/JUnit: `pytest_final_002.log` /`pytest_final_002.xml`: **239 passed in 44.49s**, zero
failures, errors or skips, verified from both log and JUnit. The earlier **235-pass** full run
and intermediate `pytest_final_001.*` are retained, not overwritten. The focused new-component suite
passed **46 tests**, including reporting-color and stopped-run checkpoint regressions.

`quality_checks_final_002.json` records exit 0 for Ruff check, Ruff format check (**66 files**, including
the bounded replay-recovery script), compileall and pip check, with separate logs. The prior 65-file
check remains in `quality_checks_final_001.json`. No dependency was silently installed or upgraded.

`v3_actual_input_parity.json` verifies A–D on the actual archived data, 905 timestamps each, within
1e-9. Original replay matched 30 artifacts byte-for-byte. The fresh color-corrected pair and economic
drift check use fresh `_002` outputs and `byte_replay_verified_002.json`: both exit 0 in
357.681/355.479s, **30 identical artifacts**, zero differences in **24 non-chart artifacts** relative
to the original. Only equity/DD PNGs and their hash manifest changed. The first color-corrected
attempts exceeded 300 seconds and produced four preliminary files each; their incomplete folders and
logs are retained with `verification_timeout_001.json`. Recovery allowed 1,800 seconds per child,
without changing any economics, seed, draw count or decision threshold. All five corrected charts
and the zero-data weekly chart were directly inspected; `visual_qa_final.json` binds their hashes.

`integrity_after.json`: 272 baseline files, **270 unchanged**, only the two in-progress audit-only
runner/core files intentionally changed. No unexpected legacy/config/state/cache/old-report drift;
input and artifact manifests, original V3 protocol and preserved old audit manifest hashes match.
The portfolio/timing enabled flags remain false. This does not repair the unresolved old-manifest
provenance. `source_checksums.json` binds final sources and documentation; no credential file is included.

`process_audit_final.json`: **zero** Python/pytest/Ruff processes at
**2026-11-24T23:21:28.0923802Z**, after both recovery jobs completed. No project bot/test/audit process
remained, and no unrelated process was terminated. This is a point-in-time inspection, not a future guarantee.

## Remaining operator/research work

Genuine 3/6-month SHADOW observation; independent weekly hash export; representative storage/latency
measurement; verified exact USDTIRT units/history; native exposure/cost instrumentation in a separately
versioned study; executable random-order null; advisory-backed vulnerability/independent security review;
real private Bale and actual OS/lid/reboot tests. None permits changing frozen parameters or LIVE blockers.
