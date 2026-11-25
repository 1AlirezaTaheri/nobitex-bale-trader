# Final audit amendments and provenance limitations

## Weaknesses first

The pre-existing `reports/final_audit/preregistration_manifest.json` claims a protocol hash different
from the protocol written for this run. It has been preserved unchanged. Its corresponding original
document was not inspected before the Add File operation. Consequently absence of an earlier document
is **not established**. Amendment 001's assertion of absence is an unverified inference, not evidence.
No original text is recoverable from a hash. This provenance limitation must be flagged prominently.

## Amendment 001 — 2026-11-25 context / 2026-11-24 execution clock

Before any new return computation, bind this run to SHA256
`ce32f959aeb29a5f914fb0c44d010d1f49243f71170f05b01ab4c9994e644911`
in `reports/final_audit/preregistration_amendment_001.json`. Preserve the prior manifest, do not claim
that it authenticates the newly written protocol. No strategy parameters or statistical thresholds
are changed by this amendment. The clock conflict blocks valid forward activation before the later
not-before timestamp. A smoke may verify that refusal, never substitute fabricated observations.

## Amendment 003 — post-results reporting corrections, 2026-11-25 context

These are disclosed after inspecting results; they do not change signals, parameters, accounts,
statistical draws or thresholds. The original `results/` and `replay/` remain immutable evidence.

- Visual QA found that Matplotlib advanced its color cycle between segments, so a single series had
  different colors on either side of a gap. The audit renderer now binds one fixed color per series.
  The first `results_verified/` and `replay_verified/` attempts each exceeded a 300-second subprocess
  deadline and left only four preliminary files. Both partial directories and logs are preserved,
  never presented as successful replays. Recovery uses fresh `results_verified_002/` and
  `replay_verified_002/`, with an explicit 1,800-second bound per child. Completion and byte identity
  must be established by `byte_replay_verified_002.json`, not inferred from a started job. All 24
  non-chart artifacts must match the original; chart changes and the hash-manifest change are
  intentionally separate. The immediately preceding runner is archived as
  `reports/final_audit/runner_before_visual_fix.source`.
  Recovery subsequently completed: both exit 0 in 357.681/355.479 seconds, all 30 artifacts byte-identical,
  all 24 non-chart artifacts unchanged from the original. Only equity/DD charts and the hash manifest
  differ from the original. `byte_replay_verified_002.json` records that actual outcome.
- Weekly checkpoint due dates now use the report's execution clock, not only its latest snapshot.
  Missed boundaries after a stopped run are enumerated after the 60-second observation grace;
  missing days crossing a checkpoint also invalidate it when a later snapshot discloses them.
  A backwards report clock is refused. Three regression tests cover these cases.
- The heuristic secret-assignment regex used `\s*` around `=`, accidentally capturing a following
  line after blank credentials. It now accepts horizontal whitespace only. The original four-file
  flags and the safe equality review are retained; `operations/security_final.json` is a separate
  corrected scan, not a retroactive rewrite of `operations/security.json`.
- `integrity_before.json` already included the in-progress audit runner and core. Both audit-only
  files have intentional differences. No claim that only the core changed is valid; final integrity
  evidence must disclose both exceptions while requiring all legacy sources/config/state/reports
  to match exactly. This is not permission to alter any frozen strategy.
