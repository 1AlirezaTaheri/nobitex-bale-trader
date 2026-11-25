# Independent SHADOW forward framework

## Weaknesses FIRST

Historical holdouts are contaminated and the audit manifest mismatch is unresolved. This is an
amendment-bound observation framework, **not a validated strategy, executable PAPER engine or LIVE
trader**. Public raw opens plus fixed modeled costs cannot certify book depth or fills. No genuine
forward snapshots exist at delivery: execution-clock refusal prevented pre-registration performance.
The zero-data weekly example has PENDING checkpoints, not a successful investment record.

## Scope and isolation

`app.forward_shadow` observes A, D, B1, B3, B4_25/50/75, B7_A/B7_D and B8 simultaneously. All are
independent 100-USDT long-only research accounts on the same actually observed BTC/ETH daily boundaries.
No Settings/.env/key loader, real placement, cancellation, exchange wallet or Bale transport is used.
`--mode live` and an inherited non-paper MODE are refused. Existing strategy configs/enabled flags,
wallets, market caches and old research reports are never written by this framework.

Default root: `reports/final_audit/forward/` (not initialized by the clock-refused smoke).

- `configuration.json`: exclusive-create frozen rules, public fee, registration and source hashes.
- `shadow.db`: independent WAL/FULL SQLite snapshot index, not the legacy wallet.
- `public_cache.db`: append-only genuine warmup observations, separate from all older caches.
- `snapshots/snapshot_<unix>.json`: exclusive-create canonical daily payload and SHA256 chain.
- `shadow.lock`: own single-instance lock. Do not bypass it by deleting a running process's lock.
- `KILL`: local persistent stop flag. It is **not** `data/KILL`; legacy Bale `/stop` does not control SHADOW.

## Observation contract

1. Verify unchanged registered audit/V3 hashes. Reject execution clocks before
   **2026-11-25T00:00:00+00:00**. Do not advance a clock artificially to bypass the gate.
2. Warm indicators from >=300 genuinely contiguous, common **closed** daily candles. The current
   raw exchange daily offset in the frozen spec is 73,800 seconds (20:30 UTC), not midnight.
   Requests use a 490-day lookback to remain below the documented 500-candle response ceiling.
3. Only observe a current boundary within **60 seconds**, using the genuine current daily open.
   Closed warmup never creates earlier holdings, trades, PnL or observations. A/D retain frozen signals.
4. Retain the original history for recursive features. Refuse a revision to a previously frozen closed
   candle, missing/shifted common grid, invalid price, stale boundary or a backwards clock.
5. Write the append-only warmup cache **before** its snapshot. The snapshot includes its warmup hash,
   predecessor hash, configuration fingerprint, sequence, observation time, fills/accounts and gap flags.
   Then commit the secondary SQLite index. Restart can recover a snapshot whose index commit was lost;
   conflicting/extra index rows or broken/missing chain/config/cache are refused, never silently reset.
6. Enumerate missed boundaries; do not replay missed trades. Existing holdings stay economically
   exposed. Mark the next actual observation at current prices, but set that gap interval's clean return
   to null. Interruption persists. Reports distinguish economic marked return from clean rebased factors.
7. An unobserved stopped period is **unknown**, not zero loss. The report enumerates outstanding missed
   boundaries after the last snapshot even before restart. It cannot invent their missing prices/marks.

Fixed fee is max(0.25%, startup public fee), adverse slippage 0.15% each side. Source/config/fee changes
refuse reuse and require a new version/root and clock. The fingerprint includes timing rules, SHADOW
ledger, checkpoint reporter, public parser/spec, boundary helper and dependency lockfile. It does not
cryptographically certify actual installed binaries or provide an external timestamp authority.

B3 buys at most 100/12 USDT from prefunded cash at each first **observed** new UTC month; no missed
monthly make-up budget or external deposits. B4 checks monthly with 5pp drift. B7 monthly weights use
the source strategy's **lagged observed expanding exposure**, not its future exposure. Therefore forward
B7 is a causal diagnostic, not the exact hindsight-matched historical B7. No terminal liquidation is
assumed in ongoing marked accounts; initial modeled entry costs are included before a full daily interval.

## Commands (PowerShell from project root)

No new output directory may overwrite prior evidence. A 45-second smoke may initialize and wait
without observing a boundary; exit 0 alone is not proof a daily observation happened.

```powershell
.\.venv\Scripts\python.exe -m app.forward_shadow --mode shadow --root reports/final_audit/forward --max-seconds 45
.\.venv\Scripts\python.exe -m app.forward_shadow --mode shadow --root reports/final_audit/forward
```

The second command is intentionally continuous. Do not run both together. Ctrl+C stops and does not
sell. For a local persistent stop, create **only the SHADOW root's** KILL file from another console:

```powershell
New-Item -ItemType File -Path reports/final_audit/forward/KILL
```

Inspect state before deliberately removing only that file. Do not delete databases/snapshots, reset peaks,
backdate observations, remove blockers or resubmit an old signal. Corruption/revision requires preserving
evidence and investigating; a new experiment is a new root, not an invisible repair of performance.

## Weekly report and independent hash anchor

```powershell
.\.venv\Scripts\python.exe -m app.forward_report --root reports/final_audit/forward --output reports/final_audit/weekly_001
```

Use `weekly_002`, etc. for later reports, or omit `--output` for a new timestamped directory. Output:
weaknesses-first Markdown/JSON, per-account CSVs/curves and four-panel equity/DD/exposure/cost chart.
No-data output has zero snapshots and null clean returns, never manufactured performance. The current
100-USDT rows are initial capital only. Check the explicit snapshot count and latest hash.

Weekly, copy the latest chain hash plus report execution time to an **independently controlled** record
(for example a private separate device or externally timestamped archive), and verify continuity against
the prior anchor. This export is an operator step; it was **not performed** here. A locally self-consistent
chain alone cannot detect deletion of its final tail or complete malicious replacement of the root.

## Frozen 3/6-calendar-month review

The clock begins at the first eligible **actual observation**, not the protocol date, warmup date or
process startup. Reviews are due after 3/6 calendar months, clamping month-end days, with at least
80/160 actually observed daily intervals respectively. Each A/D checkpoint requires:

- No interruption, no hash/config violation; a missing day cannot be counted as observed.
- Strategy daily marked MaxDD <=60% of B1's absolute daily marked MaxDD.
- Net return >=its causal B7 net return minus **2 percentage points**.
- Positive modeled gross profit (net profit +costs), and costs <=25% of that positive gross profit.

The reporter evaluates due-ness using **execution time**, not only the latest snapshot. A stopped run
cannot remain indefinitely PENDING after its deadline. Only the window ending at/before the due
boundary is scored; later observations cannot rescue a failed/insufficient checkpoint. A later-disclosed
gap crossing the checkpoint still invalidates it. A backwards report clock is refused.

**PASS_CONTINUE_OBSERVING_ONLY** permits further observation, never LIVE or meaningful capital.
**FAIL_NOT_VALIDATED** keeps the model unvalidated, with no tuning. Short periods/regimes may flatter
any method. Changes to rules/costs/sources require a separately identified experiment and a new clock.
