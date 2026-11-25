# Final product implementation amendments

## Final disclosed scope and verification

The 541-file before inventory remains the comparison authority. Existing files intentionally edited:

| Existing path | Reason / evidence |
|---|---|
| app/forward_shadow.py | Approved isolated product root, schema/source fingerprint, 12-month metadata, atomic immutable JSON publication and local PAUSE guard; economic functions unchanged by intent, covered by full tests and A/D target parity regression |
| app/forward_report.py | Fixed 12-month checkpoint, all registered B4 descriptive risk comparisons, explicit zero-data chart and fresh approved report paths; prior 3/6-month thresholds retained |
| backtest/final_audit.py | Output-root allowlist admits reports/final_product; Ruff formatting only elsewhere; frozen replay matches all 30 authoritative artifacts byte-for-byte |
| tests/test_portfolio_reports.py | Load only strategy YAML instead of optional operator .env; no strategy data or assertion weakened |
| setup.bat | Existing venv/version checks, pinned dependencies, --check-only, pip check and offline doctor; never overwrite existing .env |
| .gitignore | Exclude the local user-test receipt |
| README.md / README.fa.md | Product operations and evidence links, weaknesses/limits |
| docs/ASSUMPTIONS.md / UNVERIFIED.md / VALIDATION.md | Disclose decisions, actual verification/failures and unresolved limitations |

Six new product modules, two launch scripts, mocked product regressions, the Persian user guide,
research reviews and isolated evidence were added. No reviewed bot code or dependencies were copied.
Original preregistrations, strategy/config sources, requirements.lock, data/caches/databases, old
reports and manifests must remain byte-identical; integrity_after.json records every actual existing
file difference and its before/after hash. No Git repository exists and no commit/push was performed.

Final full pytest run 005 has 304 passes. Quality run 003 has Ruff/format/pip/compileall exit 0.
The final short smoke has zero genuine observations; old-root refusal run 003 preserves every file.
The doctor/configuration FAIL is unresolved operator configuration and has not been hidden by
editing .env. Earlier test failures, the encoding drill failure and SQLite-sidecar finding remain
preserved. Final completion metadata supplements rather than overwrites the original mission manifest.

## 004 — 2026-11-25, immutable old-root refusal ordering

operations_002.json correctly records old_root_unchanged_after_refusal=false: opening the old
WAL-mode SQLite database for a read-only integrity check created shadow.db-wal/shadow.db-shm
sidecars before the incompatible source fingerprint was rejected. No observation was appended;
preserve both the false result and sidecars rather than erasing evidence. Check configuration/source
compatibility before opening SQLite, strengthen the regression with a pre-existing DB and a
database-open tripwire, and explicitly close read-only SQLite connections to avoid relying on GC.
Repeat the actual old-root refusal inventory and use a new final smoke root after the source change.
The source-order/resource fix does not change SQLite contents, economics, registered rules or prices.

## 003 — 2026-11-25, Windows redirected-output recovery

The seven-entrypoint refusal drill found six expected exit codes and a product-shadow exit 1
caused by UnicodeEncodeError while printing its safe Persian refusal to a legacy-codepage pipe.
No market/Bale transport or LIVE operation was reached. Explicit UTF-8 environment produced exit 2.
Before correction, preserve safety_001.json and live_refusal_encoding_001.json as failed/recovery
evidence. Configure UTF-8 stdout/stderr in the four new product CLI entrypoints, add subprocess
regressions using forced ASCII and blocked networking, then repeat full checks and a new smoke root.
This changes a fingerprint-bound operational source; preserve shadow_smoke_001 and refuse its restart.
No economics, strategy rule or historical input is changed.

## 002 — 2026-11-25, validation recovery

Malformed receipt JSON values of valid JSON types other than objects are refused as unverified,
with console fallback; this does not change receipt permissions or economics. Regression fixtures
cover arrays, null, numbers, strings and missing binding.

The first complete product suite recorded 289 passed and 2 failed. One new synthetic 12-month fixture used an empty configuration object, correctly refused by the reporter; fix the fixture, not the production check. An existing portfolio snapshot test unnecessarily loaded the operator's .env to obtain only frozen strategy YAML, so malformed optional Bale configuration caused an unrelated test failure. Read only StrategyConfig/legacy_section there; do not alter .env or relax live guards. Both original logs remain preserved. Product recording/reporting falls back to console on optional Bale validation errors while MODE validation remains fail-closed; setup/test and doctor still report invalid configuration safely. Additional tests cover this distinction. No strategy economics or frozen protocol changed.

## 001 — 2026-11-25, before product code edits

The original final-product preregistration and manifest remain immutable. Scope decision: zero new strategy candidates and zero historical parameter searches, for the reasons in RESEARCH/SYNTHESIS.md. The new experiment is identified as product-shadow-v2 and uses reports/final_product/shadow_v2; the operational smoke will use a separate fresh root. Existing forward roots will fail current-fingerprint restart instead of silently mixing code versions. Existing roots remain reportable without migration.

Minimal existing-code changes authorized: forward_shadow storage allowlist, atomic immutable publication, fingerprint/12-month metadata and PAUSE observation guards; forward_report 12-month checkpoint, descriptive registered-weight risk comparison and fresh product output allowance; final_audit confined output allowance for reports/final_product only; setup.bat environment/version/offline-check hardening. No strategy, fee/slippage, capital, rebalance, timing, target, fill or existing gate formula will be retuned. New operational modules isolate Bale, doctor, weekly delivery and product orchestration. All runtime defaults remain PAPER, and portfolio/timing enabled flags remain false. No existing DB, cache, snapshot, report or manifest will be overwritten.

Official sendPhoto support was verified before implementing optional chart upload. Delivery remains gated behind a receipt written only by the user's explicit successful --test command, plus the explicit --bale flag. No such command will be run against the real service here. Discovery prints a fresh one-time challenge; the matching private sender ID is saved locally in .env without printing any ID. No existing webhook is changed. Automated tests inject HTTP transports, synthetic users and temporary directories only.

The 12-month gate is an engineering review requiring 320 observed intervals; it is not published statistical validation. Matched-risk reporting uses only registered B4 weights, with all distances shown; the closest realized-drawdown match is hindsight and never a deployable recommendation. Trusted UTC, hardware power loss/sleep, actual scheduler operation, advisory vulnerability scanning and future performance remain unverified until separately evidenced.
