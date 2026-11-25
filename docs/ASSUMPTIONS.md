# Assumptions and deliberate safety choices

## Public GitHub publication assumptions (2026-11-25)

- The user authorized public publication. Use `nobitex-bale-trader` under the authenticated
  GitHub account, with `main` as the initial branch. Do not overwrite an existing remote history.
- Publish reviewed source, documentation and research artifacts. Keep `.env`, Bale verification
  receipts, virtual environments, caches, databases, process locks, raw test XML and local logs
  private. Existing excluded artifacts remain untouched on disk.
- Publication supplements are under `reports/final_product/publication_001/`. The prior completion
  manifest, evidence index, preregistrations and frozen research evidence remain byte-identical.
- Authentication is supplied only to a child process in memory. Never put a credential into a
  command argument, remote URL, publication report, Git configuration or committed file.
- Publication changes packaging only. PAPER/SHADOW restrictions, disabled experimental defaults,
  NOT VALIDATED strategy verdicts and unresolved operator-configuration issues still apply.
- Public GitHub visibility does not establish a clean holdout, independent evidence anchoring,
  successful remote CI, a license grant or investment suitability.

## Final product assumptions (2026-11-25)

- No user questions are needed: retain PAPER/SHADOW, disabled portfolio/timing flags, all frozen rules,
  capital and cost assumptions. The final-product manifest binds the before inventory and preregistration.
- Evidence/output for this mission is under reports/final_product/. The new default observation root is
  shadow_v2; old roots are preserved and are not migrated across incompatible fingerprints.
- Zero new candidates, no optimization and no clean-holdout claim. Research access failures and partial
  PDF extraction are explicit in RESEARCH/BIBLIOGRAPHY.md; publication quality is not local validation.
- 12 months requires 320 genuine intervals; existing 3/6-month criteria/economics remain unchanged.
  All three registered B4 risk comparisons are reported; closest realized DD is hindsight only.
- Official sendPhoto documentation permits optional weekly PNG upload; actual delivery requires a
  current owner-operated --test receipt plus --bale. No real Bale API call is made here. Discovery
  writes only a challenge-verified private owner to .env and never prints any person's chat ID.
- Optional Bale configuration/delivery failure falls back to console; MODE errors remain blocked.
  Notification retries never delay the boundary recorder. Pause/stop are local to this SHADOW root.
- Product logs rotate; immutable snapshots/reports are retained. Disk growth must be monitored.
  Atomic hard-link publication requires a local filesystem supporting hard links (tested here on NTFS).
- Local date now matches the context date, but independent UTC, trusted anchoring, real scheduler,
  sleep/lid/reboot/power-loss, delivery and advisory-backed vulnerability scanning remain unverified.

## Final audit assumptions (2026-11-25)

- Existing strategies and enabled flags are immutable for this audit. Research outputs, copies,
  telemetry and forward storage are confined to `reports/final_audit/` and never replace earlier evidence.
- Historical holdouts are contaminated. Trial-count floor 250 and multiplicity correction are fixed
  before new returns, not calibrated to obtain a desired verdict. DCA is prefunded, not external cash
  contributions; cash remaining in the account is included in returns.
- The existing final-audit manifest and newly written protocol do not match. See
  `FINAL_AUDIT_AMENDMENTS.md`; this provenance limitation disqualifies an unqualified pristine
  preregistration claim. V3's original protocol must still match its original hash.
- Execution-clock/context-date disagreement blocks trustworthy post-registration shadow activation.
  Public smoke can verify blocked/warmup behavior, not claim genuine forward performance.
- Native legacy/portfolio fills retain their own risk and depth model. Baselines use the registered
  price-only model; report structural noncomparability rather than modifying frozen strategies.
- Final inventory is 262 archived configuration rows plus 25 audit series, hence M=287. With 999
  draws and add-one tails, minimum adjusted tail is 0.287; insufficient resolution cannot pass.
- Exact-turnover executable random-order nulls and native exposure/cost/B7, fresh-start and full
  crash/delay tests are unavailable, not approximated into passes. See amendment 002.
- After-results reporting fixes are amendment 003: stable colors across segments, execution-time
  checkpoint expiry, and a horizontal-whitespace credential regex. No strategy was retuned.
- The SHADOW fingerprint binds the timing rules, ledger, report/checkpoints, public parser/spec,
  boundary helper and dependency lockfile. Any change requires new storage and a new observation
  clock. Actual installed dependency identity is not cryptographically certified by the lockfile.
- Snapshots are authoritative; their SQLite index can recover from a missing commit. Public warmup
  is append-only, written before snapshots, retained for consistent recursive indicators, and checked
  for revisions. No snapshots or missed signals are reconstructed after downtime. The chain needs
  external hash anchoring to resist complete malicious history rewrites.
- Execution date is measured and recorded separately from the developer-context date 2026-11-25.
  The not-before gate is 2026-11-25T00:00:00+00:00, not a reason to alter the local clock artificially.
- A 300-second verification subprocess deadline proved too short for two parallel complete audits.
  Preserve both four-file partial outputs and logs; recovery uses new `_002` names and an explicit
  1,800-second deadline. This changes operational time allowance only, not statistical draws, frozen
  economics or an acceptance threshold. A started background job is never counted as a replay pass.
  The recovery actually completed with 30 byte-identical artifacts and 24 unchanged non-chart files;
  only two chart images and their manifest differ from the original pair.
- The corrected security scan is separate evidence: 226 text files, one deliberately synthetic test
  token-shape fixture, no confirmed real secret. Heuristics cannot establish secret absence. The
  offline dependency vulnerability scan is NOT RUN; compatibility checks are not a substitute.

1. This is a personal, single-process **PAPER-first spot long-only** research application. The unchanged
   default is the legacy BTC/USDT 4h strategy and its one-position wallet. A separate, explicitly opted-in
   daily LayeredPortfolio PAPER experiment supports five USDT pairs; it is NOT VALIDATED and disabled by
   default. No leverage, shorts, transfers, withdrawals, password handling or web administration.
2. No secrets were supplied. `.env` is the intended secret store, with standard Pydantic environment
   override support (`MODE=live` is never silently ignored). An inherited MODE can override `.env`.
   Keep backups private; `.env` is plaintext, not an encrypted vault. Avoid OneDrive/shared folders.
3. Python 3.13 on Windows was available. Source supports 3.11+, with platform-marked locked dependencies.
   Other Python/Windows versions must be tested independently. No Docker/WSL requirement.
4. Default capital and paper wallet are 100 USDT, risk is 1% of capped equity, and a trade's fee-inclusive
   initial outlay cannot exceed the capital/order limits. Profitable mark-to-market appreciation can
   exceed the original allocation: this is **not** a guarantee of maximum loss or market value.
5. Nobitex's current official onboarding describes API public/private keys and Ed25519 signatures.
   Keys are created/rotated in the Nobitex panel; there is no invented login or token-refresh endpoint.
   Expired/revoked keys require operator rotation. Time must remain synchronized within venue limits.
6. Public OHLCV observations for current 4-hour bars have epoch remainder 1800 seconds, not a UTC
   multiple of four hours. Alignment is centralized in `exchange/nobitex_spec.yaml`. Older DST-era
   data can use different grids. Never relabel timestamps or invent missing bars to hide a mismatch.
   History download accepts strictly ordered raw rows; current trading still requires the current grid.
   Alignment is frame-specific: observed 1h/4h offset 1800 seconds and 1d offset 73800 seconds.
7. Current API precision fields observed: `amountPrecisions.BTCUSDT=0.000001`,
   `pricePrecisions.BTCUSDT=0.01`, `minOrders.usdt=0.5`. Runtime reads fresh public metadata;
   backtests use these explicit present-day defaults, not a claimed historical rules archive.
8. Simulated fees are charged in quote currency, at the larger of configured fee and observed public
   taker ceiling in the PAPER runner. This conservative simplification is **not** a certified live fee
   accounting contract. Buy/sell fees and depth-weighted adverse slippage are included. PAPER orders
   fill completely or cancel completely; they are immediate simulated IOC outcomes, not historical
   limit-queue emulation. The general order manager separately tests cumulative partial fills.
9. Default TrendFollowing requires close above EMA200 and an EMA20/50 crossover, with ATR volatility
   filter and 2.5×ATR initial/trailing software stops. EMA uses recursive first-price initialization;
   Wilder RSI/ATR use an SMA seed. Three times the longest period is excluded as warmup.
   RSI mean reversion is optional (`name: rsi`) and is not assumed profitable.
10. Startup, wake, or a polling gap primes the newest closed candle but **never** replays an entry.
    A new entry must be observed continuously near its close (120-second deadline). This can miss trades;
    that is preferable to retroactive/stale fills. Existing software stops can act on a fresh current book.
11. `/pause` blocks entries but continues stop/exit monitoring. `/stop`, Ctrl+C and `data/KILL` cancel
    tracked open orders and halt without selling holdings. The KILL file persists. No forced liquidation
    on shutdown. Stops offer no protection offline, and cannot act on stale/missing prices.
12. The legacy daily loss uses UTC account-equity boundaries, including unrealized marks; drawdown is high-water
    equity. Daily latch resets next UTC day; drawdown and repeated-error faults do not auto-clear.
    Restart does not reset financial risk latches. No remote bypass exists. To restart a **PAPER experiment**
    with different configuration/risk baseline, stop and archive its database first; never erase live state.
13. Unexpected balance drift/external orders cause a fault, not automatic adoption or cancellation of
    someone else's orders. This build does not have a certified LIVE transport at all. `verify_exchange`
    performs read-only probes and deliberately cannot manufacture verification of side effects.
14. Bale control is stricter than a group whitelist: positive private chat ID equals sender ID;
    ignore other chats silently, forwarded/edited messages, unknown commands, old updates and bot senders.
    Long polling and offsets persist; send queue is bounded with a console fallback and rate limiting.
    This is not a durable exactly-once delivery service. Notifications may be lost during sudden power loss.
15. SQLite FULL/WAL durability and an OS process lock reduce crash risk, not hardware corruption risk.
    Reconciliation independently checks both BTC quantity and quote cash against initial capital,
    remaining cost basis and realized PnL; matching only the base balance is insufficient.
    Cold backups should be taken only after shutdown (or via SQLite backup), including WAL when necessary.
    Do not run two copies or edit financial state manually. Never delete an unfamiliar existing file.
16. Laptop shutdown callbacks are best effort. Windows may terminate processes before network
    cancellation finishes; force-kill/power loss cannot be made graceful. Restarts reconcile again.
17. Backtest fills are next-open approximations; intrabar software-stop responsiveness differs from real
    polling. No look-ahead signal input, retroactive trailing stop, same-close entry, or missing-bar fabrication.
    Both benchmark and strategy incur modeled two-sided fees/slippage. Walk-forward folds start independent
    paper accounts and are not misrepresented as one continuously traded account.
18. Profitability, bug-free behavior, regulatory suitability, API uptime, and future execution quality
    are not guaranteed. Fees/spread, thin liquidity, counterparty failure, overfitting and downtime matter.

## LayeredPortfolio choices (2026-11-20)

- `config/strategy.yaml:portfolio.enabled` remains **false**. Ordinary `run.bat` keeps the old 4h BTC
  strategy, values and `data/paper.db`. `run.bat --portfolio-paper` explicitly requests unvalidated research
  with `data/portfolio_paper.db`; both paths share `data/KILL` and the OS process lock, so cannot run together.
  Neither path can place/cancel a real order. The public PAPER client receives no exchange signing keys.
- The objective screen uses the real open USDT list, available public precision and the top 16 by current
  24h quote turnover plus mandatory BTC. Enumerated stable/fiat/gold proxies are excluded. Require 90-day
  median `close * base volume` >=10,000 USDT, three fresh books, median spread <=0.40%, and >=500 USDT each
  side within 0.50% of midpoint. Rank passes by the median volume proxy, not historical returns.
- The initial >=750 consecutive-bar screen selected NONE. **Before running returns**, split that history
  rule into >=750 actual raw bars plus >=301 current-grid recent consecutive bars with the latest close.
  This is a disclosed eligibility change, not evidence the original screen passed. Both screens are saved.
  Frozen selection is BTC, ETH, XRP, SOL, DOGE / USDT. It creates present-day survivor/selection bias in older tests.
- Full collection uses 499-day windows because an older DST 500-day request returned 501 genuine records;
  the strict response ceiling was retained. Two empty windows end collection. No time labels were changed.
  Daily candle opens currently have epoch remainder **73800**; older DST rows use **70200**.
- Primary analysis was predefined as the **longest common gap-free current-grid segment**: 1,000 bars with
  300 warmup and 700 evaluated days. After this run showed no fills, an input audit found **all 1,000 volume
  values per asset were zero**. Do not infer zero historical activity; zero is what the endpoint returned.
  Preserve those values and the no-fill result. The additional `--segment latest` report has 503 nonzero-volume
  bars per asset, 300 warmup and only 203 evaluated days. It is supplemental, not a replacement or a promotion.
- Recursive EMA uses the first shared contiguous raw-grid observation as its seed; Wilder ATR/RSI use SMA
  seeds. Both runners use exactly the same feature and rule functions. Runtime retains all available common
  continuous cache history, not a sliding EMA seed. Different cache origins can change recursive indicators;
  parity means the **same ordered input candles**, configuration, marks and costs, not arbitrary cache origins.
- Trend rules: close > EMA200 and strictly > previous-55-day highest high; initial stop at actual fill minus
  3*ATR20. The prior-20-day low tightens at the next open and is never lowered, with close < EMA200 exit.
  Pullback: above EMA200, Wilder RSI3 <15 and current low >= prior-20-day minimum (equal low is not a fresh
  lower low). Exit at RSI3 >60, close > prior-five-day high, seven elapsed 24h days, or actual fill -2*ATR20.
- A symbol has at most one sleeve. Trend beats Pullback on overlapping same-symbol signals; process all
  Trend candidates first, then Pullback, alphabetically within each. Symbols held at a decision or stopped
  during that execution bar cannot re-enter from that same daily signal. USDT stays uninvested otherwise.
- BTC below EMA200 blocks **new entries**, never protective exits. Optional breadth requires at least
  half the frozen universe above its own EMA200; it is OFF by default and is reported separately.
- Shared sizing includes entry and adverse stop-exit fees/slippage. Risk per trade is 0.75% Trend / 0.50%
  Pullback; risk is based on equity capped at MAX_CAPITAL_QUOTE. Open-risk cap 3%, per-asset fee-inclusive
  entry outlay <=25%, maximum four positions. Sleeve shares are **risk caps**, 50%/30% with 20% unused reserve:
  1.5% Trend +0.9% Pullback, not forced investment targets or a guaranteed cash allocation. Existing open
  risk is mark-to-net-stop loss; gaps can exceed it. Appreciation is not forcibly sold to restore entry caps.
- The loss ladder uses the portfolio high-water mark: at 5% DD halve new risk; at 10% block new entries;
  at 15% latch a full **entry halt**, issue a notification and still manage exits. Resume requires exactly
  `/resume I UNDERSTAND THE RISK`, fresh/reconciled state **and recovery below 15% DD**. Never reset the peak;
  the 10% entry block, daily latch, cooldown, KILL and operational faults cannot be cleared by this command.
  A halted, liquidated account below the boundary may remain halted indefinitely; this is intentional.
- Portfolio loss days follow **20:30 UTC**, the verified exchange daily grid, not legacy UTC midnight.
  A 2% equity loss latches until the next exchange day. A gap at rollover is charged versus last known equity;
  intraday recovery does not clear that day's latch. Three losing completed positions trigger a three-day
  cooldown. Risk state and atomically journaled closure cursors survive restart; config limits are persisted.
- Correlation is the arithmetic mean of the held assets' pairwise correlations over 60 **closed** daily
  returns. If >0.85, multiply new risk by 0.5. With two or more held assets and insufficient/constant-series
  data, use the same conservative scaling. Unheld candidate returns do not enter the held-assets average.
- Historical L2 is unavailable. Every hypothetical IOC uses the shared executable depth walk with one
  level, 0.10% half-spread and 0.10% of **prior closed daily base volume** on each side. A zero volume means
  zero modeled depth and no fill. This is not fabricated L2 or a proven venue capacity model. PAPER instead
  requires an actual fresh public book. Each simulated order fills fully or cancels; no queue priority claim.
  Initial stop uses actual volume-weighted fill, not its limit. Failed protective exits stay pending.
- Signals use only closed candles and fills use next-open references. Gap stops execute at the worse open;
  new trailing lows never act against already-observed candle lows. Cross-asset intraday order and true
  equity minima are unknowable from daily OHLC. DD metrics use closes; breakers also observe opens/transactions.
  PAPER observes bid marks per poll; identical live/PAPER paths or intraday results are **not** claimed.
- Buy-and-hold benchmarks are buy-once, fractional-unit, nonrebalanced, with modeled round-trip spread,
  slippage and fees, but without sleeve/risk/depth restrictions. The old BTC 4h comparator keeps its rules
  and fill model; DD is measured on its 4h curve, Sharpe/Sortino on matched daily samples.
- Holdout is the final 25% of **evaluable** days, independent cash/risk at the split with earlier candles
  retained for features. Walk-forward selects from a frozen 3x3 Donchian/ATR set on expanding training data
  only, entirely before the holdout; its three disjoint test accounts are not a compounded portfolio.
  Train ranking is net return with baseline preference on ties. No chosen parameters are deployed.
- Full sensitivity has 31 one-factor cases: entry 30-100, exit 10-40, Trend and Pullback ATR 2-4, RSI
  entry 5-30, EMA 100-250. Fourteen one-factor/joint +/-20% checks include ATR multiples for **both** sleeves.
  Robustness passes only if baseline and every perturbed return are positive and each retains >=50% of
  baseline net return. 2x/3x stress multiplies fees and adverse slippage, not assumed spread/depth.
- No acceptance failure is fixed by changing parameters. All eight are printed for both reports; even
  numerical passes on a zero-trade account carry no validation evidence. Default remains disabled.
- `/portfolio`, `/layers`, `/risk` and the single exact typed resume form use the existing private sender/chat
  whitelist, timestamp/forward/edit guards and durable update offset. No remote parameter/mode changes.
  Daily close summaries deduplicate by the original daily timestamp; messages have console fallback but
  are not durable exactly-once notifications. A failed feed cannot suppress another asset's fresh-book stop.
