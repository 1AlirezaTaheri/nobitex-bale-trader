# Final audit implementation notes — amendment 002

## Weaknesses first

The old/new registration-hash mismatch in FINAL_AUDIT_AMENDMENTS.md remains unresolved.
This note does not repair that provenance or create a clean holdout. All historical results are
hypothesis-generating. This implementation clarification is recorded before new return computation.

- Native S0/S1 are run without modifying their strategies, fees, sizing or execution model. Complete
  common evaluation segments are required; unavailable segments stay excluded, never silently sliced
  into a favorable partial interval. Baselines are rerun on each native strategy's available cohort.
- If exact exposure or costs are not exposed by the native result, those fields and B7 are unavailable.
  Binary invested-day estimates from trade intervals are not substituted for fractional exposure.
  Daily and 4h drawdowns are distinguished. No significance/decision pass is possible with missing checks.
- Per-segment and grouped regime metrics normalize initial equity to 100; native USDT costs, if known,
  are scaled consistently. Regime concatenations are conditional attribution, not tradable paths.
- Start-date sensitivity reruns price-only accounts from cash each date, with the frozen signal state
  restarted at the retained causal warmup boundary as prescribed by targets_for. Native fresh-start
  reruns are explicitly unavailable, not reused suffix returns mislabeled as fresh accounts.
- For B7 of D, same-asset means equal BTC/ETH risky allocation. Native S1's unknown exposure means no
  fitted B7 is manufactured. The closest B4 uses observed average risky exposure, not return.
- The preregistered cyclic timing null preserves circular observed weights/drag only. It is NOT the
  executable same-turnover random-order null requested by the user; this methodological gap is disclosed.
  Bootstrap sign-tail values are descriptive uncentered resampling tails, not exact frequentist p-values.
- Percentile bootstrap tail quantiles below one simulation count are resolution-limited and cannot pass.
  Mean-return HAC record-length approximations are not a rigorous minimum Sharpe track-record proof.
- Native intrabar crash-cost and delayed-order stress require unavailable fill metadata or a changed
  native simulator; report unavailable, do not simulate an altered native strategy or call it robust.
