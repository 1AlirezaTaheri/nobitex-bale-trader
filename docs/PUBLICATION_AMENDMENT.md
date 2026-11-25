# Public publication amendment - 2026-11-25

This amendment supplements the completed product evidence. It does not replace or
re-seal `reports/final_product/completion_manifest.json` or its bound evidence.

The user authorized a public GitHub repository. The default target is
`1AlirezaTaheri/nobitex-bale-trader`, on branch `main`. Authentication verified that
account, and the target returned HTTP 404 before creation; no existing repository
history will be overwritten.

## Packaging changes

- `.gitignore` adds publication exclusions for local logs, raw pytest XML,
  runtime locks, SQLite variants, private-key file types and product SHADOW
  runtime roots. Existing environment, database and receipt exclusions remain.
- `.gitattributes` disables automatic line-ending conversion so public clones
  preserve frozen evidence and source-fingerprint bytes on every host.
- `docs/ASSUMPTIONS.md` records the repository, branch and publication boundaries.
- New publication evidence is written only under
  `reports/final_product/publication_001/`, starting with `before.json`.
- No strategy, application code, configuration, dependency lockfile, prior
  report, snapshot, database or sealed evidence is edited for publication.

## Public evidence limitations

The repository is a curated public copy, not a complete operator backup. Local
logs, raw pytest XML, databases and runtime state are deliberately omitted.
Historical manifests retain their original inventories and may reference these
omitted files; omission is not deletion or a claim that every archived artifact
is available from a public clone. Structured validation summaries, research
inputs, result tables, plots and the original evidence manifests are retained.

The previous engineering result remains 304 passing tests with the limitations
recorded in `reports/final_product/final_validation.json`. Publication checks
verify packaging, staged bytes and exclusions. Any additional test execution
is recorded separately in this publication's evidence directory. Remote GitHub
Actions results must be checked separately after the push.

All evaluated strategies remain NOT VALIDATED. PAPER/SHADOW restrictions and
disabled experimental defaults remain unchanged. The operator's optional Bale
configuration still requires correction and an explicit user-operated test.

No project license is selected by this publication step. Reviews of third-party
licenses do not grant a license to this project's own code.

## Credential handling

The supplied GitHub credential is read from the original user message into
process memory. Neither the transcript nor the credential is exported to a
file. Authentication is passed through a child-process environment; it is never
included in a command argument, remote URL or Git configuration. The public
candidate files are scanned against configured private values and credential
patterns. Heuristic scanning cannot prove the absence of every possible secret.

The credential was shared in conversation and should be revoked after use.
