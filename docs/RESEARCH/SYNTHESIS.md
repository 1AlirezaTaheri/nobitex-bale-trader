# Product decisions, registered before implementation

Decision date: 2026-11-25. Weaknesses first: historical reuse, unresolved old audit provenance, no clean holdout, zero genuine forward observations, no executable fill evidence and no verified return advantage. Published research is not local replication. No new strategy candidate is justified in this mission: **new candidates = 0; new historical parameter searches = 0**. Existing audit family M=287 remains unchanged; descriptive new reporting is not an extra independent test.

Grades: A = primary theoretical/empirical result with clear limits; B = primary implementation documentation or scoped observational evidence; C = engineering inference needing local testing. Grades do not rate expected profit. The table ranks only these eight decisions.

Access correction: the BIBLIOGRAPHY actual-access ledger overrides generic evidence grades below.
R2/R5/R7/R8/R9/R10/R11/R12/R15 were not substantively full-text reviewed; do not treat their
sample details or purported full-text results as authenticated by this mission. Later NBER landing-page
abstracts for R5/R12 were successfully reviewed, without full-text methods/sample verification. Decisions 5/7/8 are conservative
engineering choices, not conclusions newly established by those inaccessible studies. R3/R4/R6
were only partially readable. No completed systematic review or independent replication is claimed.

| Rank | Decision and tag | Evidence | Benefit | Cost | Risk / falsification |
|---|---|---|---|---|---|
| 1 | Keep LIVE blocked; preserve rules, snapshots and preregistrations — engineering/safety | A: partial R3/R4; B: R14; C: safety decision | Prevents contaminated selection from becoming real losses | Low | Local hashes do not independently authenticate history; any frozen mismatch fails verification |
| 2 | Explicit Bale setup/test, owner challenge, fresh private commands, safe console fallback — engineering/safety | B: official Bale; C: failure injection | Makes unattended state visible without exposing identifiers | Medium | Delivery is not guaranteed; timeout/replay/unknown chat must never trade or crash recorder |
| 3 | Atomic publish, SQLite/disk/clock checks, bounded logs, offline doctor — engineering/safety | B: repository failure reports; C: local tests | Reduces corruption and silent failure | Medium | Not a power-loss certification; fail closed on clock/DB inconsistency |
| 4 | Separate versioned SHADOW root; report genuine gaps and lifecycle/heartbeat — engineering/safety | B: Freqtrade parity docs; C: local contracts | Honest continuity and recoverability | Medium | Sleep/network outages lose actual boundaries; never reconstruct fills |
| 5 | Fixed 3/6/12-month reviews and all three registered constant-mix risk comparisons — engineering/safety | A: partial R1, R5 abstract; C: checkpoint/risk-report design | Reduces unfair exposure comparisons | Medium | 12 months can still be one regime; ex-post closest risk is descriptive only; PASS never permits LIVE |
| 6 | Weekly Persian report/chart and Windows logon/weekly scheduling guidance — engineering/safety | B: Bale sendPhoto, Microsoft Task Scheduler | Low-maintenance monitoring | Medium | Hardware sleep/reboot/delivery remain user checks; no fake zero-data performance |
| 7 | Loss-tolerance framework and manual monthly allocation alternative — engineering/safety | B: R14, approximate R16; C: stress arithmetic and manual-process alternative | Makes exposure, costs and custody risks explicit | Low | USDT is not insured cash; rough allocation stress is not a drawdown bound; R16 footnotes are inconsistent |
| 8 | Reject grid/martingale/leverage/LLM signal trading, Kelly fitted to contaminated returns, mass optimization — do not do | A: partial R3/R4/R6/R13; B: R14; C: conservative scope decision | Avoids fragile sizing, cost drag and trial proliferation | Foregone speculative upside | These sources do not prove every named method universally fails; reconsider only with separate registration/evidence; no new candidate now |

## Automation versus constant mix

Automation is justified here for consistent observation, records and alerts. It has not demonstrated better net returns or drawdown at matched risk than simple allocation. B4_25 was only the lowest historical drawdown among the positive-return registered B4/B5 mixes, not a universally best portfolio. B7 is causal average-exposure matching, not exact future risk matching. The new report shows all B4_25/50/75 realized risk distances; its closest-by-realized-drawdown label is explicitly hindsight and cannot authorize selection. Lower exposure can itself explain lower drawdown. Manual monthly review with a weight chosen from loss capacity beforehand is a legitimate comparison, not a promised profitable replacement.

Trend evidence (R1) needs exposure/scaling controls; the cited replication R2 and implementability paper R7 remain full-text access gaps, not newly confirmed counter-results. R5's reviewed abstract does not establish implementability in this product. Diversified futures, foreign stocks and early crypto samples do not establish an edge in two local spot USDT markets. Costs and gaps remain explicit model limitations. No code or dependency was imported from reviewed bots.
