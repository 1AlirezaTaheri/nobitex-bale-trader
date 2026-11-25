# Operations and failure drills

## Release boundary

This build trades simulated money only. Do not delete safety guards to enable LIVE. If credentials are
configured, PAPER still builds a public-data client without passing them to it. Private API access is only
used by the explicit read-only verification utility. `MODE=live` is a refused configuration in this release.

## Daily operator checks

1. Read `/status` and current heartbeat. A running process alone is not evidence of fresh market data.
2. Read `/balance`, `/positions`, `/pnl`; remember the balances are simulated. Review the local JSON log.
3. Check disk space, Windows clock sync, power/ventilation, internet and upcoming Windows maintenance.
4. Check Nobitex public API/market health and liquidity; do not override stale-data gates during an outage.
5. Review error/risk latch messages before attempting a restart. A restart cannot erase financial latches.
6. Keep a private stopped-state backup of PAPER results periodically; record config for each experiment.

## Paper-only failure drills

| Drill | Expected result |
|---|---|
| Ctrl+C while idle | Clean reconciliation and stopped notice; restart possible |
| Create data/KILL | Trading stops, tracked cancellation checked, file persists and next launch refuses |
| Send /stop from whitelist | Same persistent KILL behavior; never liquidation |
| Send /pause then /resume | Pause persists before command acknowledgment; resume only when safety gates pass |
| Send a command from any other account | Silently ignored; no disclosure of state or IDs |
| Disconnect/reconnect network | No order from stale book; entry disabled, bounded retries, error notifications and possible latched fault |
| Sleep across a candle close | Detect gap; collect missing bars; do not replay offline entry signal |
| Crash after paper fill before ledger commit | Startup recovers by durable client ID and accounts fill once; no duplicate |
| Change cached wallet/base/cash externally | Independent ledger mismatch blocks trading (use a test DB, never edit a real account) |
| Start second app process | OS lock rejects the second process |

Unit tests exercise mocked variants without external network. Real Windows sleep/reboot, Bale sender tests,
and multi-week performance still need operator validation; a short smoke is not a substitute.

## Recovery without hiding evidence

- Normal restart: preserve `.env`, SQLite databases and logs. It reconciles and ignores stale entries.
- Data outage: restore network/venue access; do not invent candles or force old signals to execute.
- Unknown order outcome: never retry with a new ID until ownership/status is established. This is one reason
  live execution is withheld: Nobitex open-only client-ID lookup is not sufficient terminal recovery.
- Corruption/disk errors: stop all copies. Preserve a copy of DB/WAL/SHM and logs. Do not blindly delete or
  reinitialize a database, and do not run a database repair utility against a trading account without review.
- New PAPER experiment: stop first. Rename/archive `data/paper.db` (and associated WAL/SHM only if present
  after full shutdown), preserve reports/config, then start a separate simulated account. Do not do this
  to claim a continuous performance history or to disguise a drawdown.
- Fault latches: intentional conservative state. In this PAPER release, preserve the failed experiment and
  begin a distinct reviewed run rather than adding a remote financial-risk bypass.

## Data and notifications

Notifications use a bounded in-memory queue, one Bale message per at least 1.25 seconds. API failures fall
back to console. A lost power supply can lose queued messages; financial intents and simulated fills are
durable independently of notification delivery. Do not treat a missing notification as proof no fill occurred.

The current history cache includes a genuine gap. `--latest-contiguous` explicitly restricts analysis and
reports excluded data; this is not a reconstruction of trading through the gap. Keep provenance with CSV
imports. Neither a profitable segment nor a successful unit suite warrants funding the strategy.
