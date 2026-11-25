# Risk register — final audit, 2026-11-25 context

## Weaknesses FIRST

No strategy is validated, no clean historical holdout remains, and no LIVE execution is authorized.
Severity is qualitative, not an estimated probability. Controls reduce selected failure modes only;
none guarantees safety, custody, availability, positive returns or a maximum loss.

| ID | Risk / severity | Observed evidence | Current control | Residual / follow-up |
|---|---|---|---|---|
| R01 | Repeated-data selection /Critical | 262 archived rows +25 audit series; contaminated former holdouts | M=287, no tuning, all strategies category1 | Genuine frozen forward observations; no historical significance claim |
| R02 | Protocol provenance /High | Old manifest hash mismatches current protocol | Preserve old manifest; disclose amendments001–003 | Earlier document provenance unresolved; cannot authenticate absence |
| R03 | Clock integrity /High | Context Nov25 vs measured UTC Nov24 | Not-before Nov25 00:00 UTC, fail closed | Trusted clock/independent timestamp needed; zero genuine forward data |
| R04 | Historical data gaps/grid/volume /High | Seven short excluded common segments; zero reported volumes | Exact raw timestamps, no interpolation/backfill trades | Endpoint revisions and survivor selection; no full outage return reconstruction |
| R05 | Incompatible execution models /High | Native S0/S1 exposure/cost unavailable; S1 latest cohort absent | Null missing controls/metrics; native-cohort baselines | Separately versioned instrumentation, never proxy into PASS |
| R06 | Statistical overstatement /High | 999 draws cannot resolve M=287 adjusted threshold | Sign-tail and extreme-CI caveats, no promotion | Cyclic surrogate not executable null; rough HAC length not Sharpe proof |
| R07 | Slippage/liquidity/intraday tails /Critical | No historical L2, daily marks only | Conservative explicit costs; 2x/3x/delay diagnostics | Actual fills/gaps can be worse; software stops are not guaranteed protection |
| R08 | Offline laptop/network /Critical | Tiny public sample; process pause only | Stale-boundary refusal, KILL, gap flags, economic marks | Actual sleep/lid/reboot/power/ISP/scheduler unverified; no protection offline |
| R09 | Crash/corrupt/locked state /High | Mock/local child kill and SQLite tests | FULL/WAL, exclusive snapshots, index recovery, single-instance lock | Hardware/file truncation can still force refusal; retain backups, no manual financial edits |
| R10 | History rewrite /High | Local SHA256 chain only | Fingerprints and immutable-by-contract appends | No independent weekly anchor yet; full rewrite/final-tail deletion may evade local chain |
| R11 | Credential/command compromise /Critical | Corrected heuristic scan; whitelist/redaction tests | No key loader in SHADOW; read-only exchange allowlist; .env ignored | Not a pen-test; no Git history audit, private Bale delivery untested; plaintext .env |
| R12 | Dependency vulnerability /High | pip check only, no offline advisory DB | Pinned dependencies; no silent upgrades | Advisory-backed vulnerability scan and independent review NOT RUN |
| R13 | USDT/custody/withdrawal /Critical | Not modeled by price-only history | No real funds, transfers or withdrawals in audit | Depeg, freeze, insolvency and access loss may dominate market DD |
| R14 | IRT/IRR/FX/regulatory /High | USDTIRT history403; quote unit not certified | No invented FX, no implied BTC cross-rate | Exact complete verified FX and jurisdictional review unavailable |
| R15 | Forward expectation/false PASS /High | Zero true observations; corrected stopped-run due handling | Fixed80/160-day and3/6-month gates; no interruptions | Short-regime luck remains; PASS only extends observation, never LIVE |
| R16 | Operational sizing /Medium | 15.255s startup-heavy telemetry | Report raw sizes and low-confidence growth projections | Representative long-running CPU/memory/storage measurement needed |
| R17 | Reporting ambiguity /Medium | Original chart colors changed across gaps; regex crossed blank lines | Amendment003, separate corrected outputs, regression tests | Old artifacts retained and explicitly superseded for visual use, not erased |

Evidence index: `reports/final_audit/report.md`, `operational_report.md`, `FORWARD_FRAMEWORK.md`,
`docs/FINAL_AUDIT_AMENDMENTS.md`, `docs/VALIDATION.md` and `docs/UNVERIFIED.md`.
Do not close a risk merely because a related offline test or read-only probe passes.
