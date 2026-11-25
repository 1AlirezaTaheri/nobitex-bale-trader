# Unverified contracts and release limitations

## Final product scope, 2026-11-25

Product code adds owner-gated Bale orchestration, doctor, Windows scripts and 12-month descriptive
review; it does not validate investment performance. Real Bale delivery/configuration, getUpdates
behavior with this user's account, physical sleep/restart/power-loss, registered Task Scheduler tasks,
independent UTC/hash anchoring and long-term forward results remain UNVERIFIED. No advisory database
or vulnerability scanner was installed; pip check is compatibility only. Some scientific primary pages
were inaccessible and some PDFs only partially extractable; the access ledger distinguishes those
from genuinely reviewed text. No unavailable study is presented as a local replication. Partial/failed
test runs remain in reports/final_product alongside the final successful evidence. Invalid optional
Bale settings do not block public recording, but doctor still exposes their status without values.

**LIVE IS NOT RELEASED / NOT OPERATIONAL.** Changing MODE, YAML verification strings, or the unprotected
positions flag cannot unlock exchange writes. `NobitexClient.place_order` and `cancel_order` deliberately
raise `Blocked`; its HTTP dispatcher has a read-only allowlist. The full abstract interface and generic
persistent execution engine exist, but real placement/cancel/protective transport is not certified or
implemented as an enabled feature. This is an explicit incomplete portion of the original live-bot scope.

No real order, cancellation, withdrawal or transfer was sent during development. Tests prohibit external
network connections and use mocks. Read-only endpoint success proves only the observed read schema,
not idempotency, trading permissions, execution, fee denomination, stop placement or cancellation races.

## Final adversarial audit and SHADOW limitations — 2026-11-25 context

- **All seven strategy variants are category 1 / NOT VALIDATED.** Former holdouts are contaminated;
  262 archived configuration rows +25 audit series give M=287. With 999 draws, adjusted add-one tails
  cannot go below 0.287. Descriptive uncentered bootstrap tails are not exact null-test p-values;
  extreme adjusted percentile CIs lack resolution. No historical significance or profit guarantee.
- The old final-audit manifest does not match the current amendment-bound protocol. The original
  earlier document was not inspected before writing; neither its absence nor pristine registration
  provenance is established. Preserve both protocols/manifest evidence and amendments 001–003.
- Native S0/S1 fill/depth/stop/precision models are not economically identical to daily price-only
  baselines. Exact native exposure/costs/B7, native fresh-start reruns and full native delay/crash
  stresses are unavailable. S1 full/L1 lack the second complete common cohort; zero trades on the
  700-day cohort are not proof of risk control. No fabricated exposure proxy repairs this.
- Timing null is a circular observed-weight/cost surrogate, not an executable same-turnover random
  order schedule. HAC record-length estimates are not rigorous Sharpe power/minimum-record proofs.
  Heavy overlap, few major regime episodes, selected survivors and data gaps restrict inference.
- Initial color-corrected verification attempts timed out and left four preliminary artifacts per
  directory. Those partial `results_verified/` and `replay_verified/` are preserved, not successful
  replays. Recovery completed in separate `_002` directories with 30 byte-identical artifacts and no
  drift in 24 non-chart artifacts versus the original. This proves consistency, not a new sample or
  repair of provenance. `byte_replay_verified_002.json` records the completed comparison.
- Genuine forward performance is **unobserved**. The smoke at 2026-11-24T23:06:11.096013+00:00
  refused before startup because not-before is 2026-11-25T00:00:00+00:00. No clock override,
  historical backfill or warmup counts as genuine daily observations. The delivered weekly example
  has zero snapshots and PENDING checkpoints. The context date is not a trusted execution clock.
- The independent SHADOW ledger uses public opens and modeled costs, not executable paper orders,
  books, native protection or live reconciliation. Economic marking across downtime cannot reveal
  unobserved intragap minima. Clean gap factors are null; missed days cannot pass a checkpoint.
- A SHA256 chain and frozen source/config fingerprint detect inconsistency, not complete malicious
  history replacement or final-tail deletion without an independent prior anchor. Weekly external
  anchoring, trustworthy time and actual installed-binary identity were not certified.
- Checkpoint PASS only allows further observation; never LIVE, parameter retuning or meaningful funds.
  Real multi-month runs, OS sleep/lid/reboot/power/ISP/scheduler behavior and private Bale delivery
  remain unverified. A local child pause is not a real laptop suspend test.
- Public telemetry covers 15 requests/15.255s only; startup-dominated 30-day growth projections are
  very low confidence and no SLA. USDTIRT history returned three403 responses; exact FX coverage
  and IRT/IRR unit identity are unverified. No synthetic/cross-implied FX translation was substituted.
- The corrected heuristic security scan found one deliberately synthetic test token-shape fixture,
  not a real credential leak. Zero heuristic credential findings would not establish secret absence.
  No Git history exists locally to audit older remote exposure. Offline advisory-backed dependency
  vulnerability scanning and independent penetration/security review were **NOT RUN**. `pip check`
  proves dependency compatibility only, not security.

Full findings: `reports/final_audit/report.md`, `operational_report.md`, `FORWARD_FRAMEWORK.md`,
[RISK_REGISTER](RISK_REGISTER.md), [VALIDATION](VALIDATION.md). Hash/replay agreement and 239 passing
tests establish selected consistency contracts, not historical accuracy, investment edge or LIVE safety.

## Central live blockers

| Item in `exchange/nobitex_spec.yaml` | Status / evidence still needed |
|---|---|
| `authenticated_read_contract` | UNVERIFIED: no owner-supplied READ key; actual signed profile/wallet/order/status probes pending |
| `fee_currency_and_fill_accounting` | UNVERIFIED: exact live buy/sell fee assets, incremental fee updates and fill ledger |
| `terminal_client_order_id_recovery` | UNVERIFIED: official docs limit client-ID lookup to open orders; recovery after lost terminal response needs a durable history contract |
| `live_limit_and_cancel_semantics` | UNVERIFIED: placement acceptance/rejection, partial fills, limit constraints, cancel/fill races and duplicate requests |
| `executable_symbol_precision` | UNVERIFIED: public precision is observed, but live executable rounding/minimums and fee deductions are not exercised |
| `native_protection_lifecycle` | UNVERIFIED: stop_market/stop_limit/OCO are documented, but actual reserve/rearm/partial-fill/OCO/trailing lifecycle is not tested |

Native protective orders **are documented**, not assumed unsupported. They are not claimed to be active.
All PAPER positions have software-only protection. A future certified LIVE implementation must either
use confirmed venue-resident protection or require `ALLOW_UNPROTECTED_POSITIONS=true`, still with a
local interactive typed `I UNDERSTAND THE RISK` and every other checklist condition satisfied.

`python -m app.verify_exchange`:
- Public: current candles, order book age, public symbol precision and fee schedule.
- With API keys: signed profile, selected spot wallets and paginated open orders; existing order status
  by server ID, and by open client ID when one is available.
- Never places/cancels a test order, never accesses private account changes, and never rewrites spec
  verification strings. A successful read cannot certify a write. Exit **2** while live blockers remain
  is deliberate, not a command error. Keep this output private if you later add account-specific probes.

## Additional unverified operational behavior

- Final online attempts were not all successful: portfolio and legacy smokes failed before startup with
  bounded public-options errors, and the latest public verification failed on candles. An earlier portfolio
  smoke passed two healthy cycles. These distinct records do not establish current endpoint availability
  or continuous uptime; no guard was relaxed. See `docs/VALIDATION.md` and the named report logs.
- **LayeredPortfolio is NOT VALIDATED and disabled by default.** The longest raw common segment has only
  zero reported volumes and hence no depth-model fills. The supplemental recent sample has just seven
  trades, loses under 2x costs, has negative holdout return and fails the combination-DD/fragility criteria.
  These are failed research results, not reasons to tune the defaults or authorize LIVE.
- No genuine historical L2 archive is available. Daily historical capacity is explicitly modeled from
  previous reported volume; current spread/depth measurements cannot certify old liquidity. Per-poll
  bid risk marks and software-stop timing differ from daily OHLC simulation. Intraday DD can be worse.
- New multi-symbol runtime trade/stop/recovery paths have offline tests, not an organic online execution
  history. Short public-data PAPER smoke staying flat does not validate an edge, limit queue or latency.
- Current universe/rules cause survivor bias; gaps, old DST grids and missing/unreliable volumes constrain
  the sample. More history with reliable volume and books is needed, not interpolated or invented inputs.
- Real Bale token/chat delivery and commands: mocked and whitelist-tested only until configured by owner.
- At least 2–4 weeks of paper performance, laptop suspend/reboot/power-loss recovery, Task Scheduler,
  lid-close behavior, Windows Update interruptions and real network latency remain operator checks.
- Windows/Python variants other than the locally available installation are not executed here.
- Historical/current venue metadata, endpoint reachability/rate limits, and default 4h grid can change.
  Read API errors and reject inconsistent data rather than normalizing it silently.
- This is not a penetration test, independent financial-model audit, formal proof, exchange certification,
  regulatory opinion, or guarantee that losses/bugs cannot occur.

## Official references consulted

- https://apidocs.nobitex.ir/
- https://apidocs.nobitex.ir/getting-started
- https://apidocs.nobitex.ir/openapi/market_data.yaml
- https://apidocs.nobitex.ir/openapi/spot_trade.yaml
- https://apidocs.nobitex.ir/openapi/user_data.yaml
- https://apidocs.nobitex.ir/openapi/api_key.yaml
- https://github.com/nobitex/docs-api
- https://docs.bale.ai/ (sendMessage, getUpdates; HTTPS base https://tapi.bale.ai)

The conservative client request caps in the centralized spec are local throttles, not universal rate-limit
guarantees. Nobitex's official quickstart mentions Iran-origin access. Network failures may reflect IP,
local ISP, venue restrictions, or temporary outages; do not infer permission to evade restrictions.
