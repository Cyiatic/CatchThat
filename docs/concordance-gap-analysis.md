# Concordance feature and risk review

Reviewed read-only: `C:\Users\cyiat\OneDrive\Documents\Docker\discord-archive`.
CatchThat was the only checkout changed.

## Feature matrix

| Concordance idea | CatchThat decision | Why |
| --- | --- | --- |
| Overlap-aware range merge and coverage | Already present and retained | It is the core protection against claiming a virtualized Snapchat chat is complete. |
| Capture-session ledger/checkpoints | Added as `capture-session init/add/status/finalize` | Keeps multiple attended DOM ranges, relative paths, and hashes together before merge. |
| Metadata-only evidence export/verify | Added as `export-evidence` / `verify-evidence` | Preserves provenance and integrity without duplicating message bodies into a report. |
| Safe-share redaction | Added as `redact --profile safe-share` | Creates a non-destructive anonymized fixture for UI review or bug reports. |
| Multi-archive catalog | Added as `build-catalog` / `verify-catalog` | Gives several local viewers one metadata-only launcher while retaining per-viewer manifests. |
| Large bounded viewer lists | Already present | The static viewer limits rendered rows and keeps archive-wide search/deep links. |
| Remote media materialization | Excluded | Snapchat’s boundary forbids remote media fetching; visible pixels may be materialized only by the foreground adapter. |
| Official platform data-package import | Excluded | There is no Snapchat equivalent in scope, and it would not be visible-DOM capture. |
| Optional encrypted bundle | Implemented | `export-bundle` creates a portable ZIP; the optional `secure` extra adds password-protected PBKDF2-HMAC-SHA256/AES-256-GCM bundles. Raw archives still remain local and must be redacted before sharing. |
| Sentry telemetry | Not applicable | Sentry CLI is not installed, and adding network telemetry would conflict with the offline/local-first boundary. |

## Security review

- The generated viewer now has same-origin `app.css` and `app.js` plus a
  restrictive offline CSP. The source template still contains build-time
  placeholders; the generated artifact is the security boundary.
- Local avatar/media paths are accepted only as normalized relative paths in
  both Python and JavaScript. Scheme-bearing, absolute, traversal, and
  backslash-ambiguous values are rejected before use.
- The viewer uses DOM construction and `textContent`; no `innerHTML`,
  `document.write`, `eval`, `postMessage`, browser storage, fetch/XHR, or
  WebSocket path was introduced.
- Evidence reports contain hashes, counts, timestamps, coverage and selected
  source metadata only. Verification rejects archive collections/message body
  keys if a hand-edited report tries to add them.
- The ownership-map run over the recent history found no default-rule flagged
  orphaned sensitive paths or bus-factor hotspots in CatchThat or Concordance.
  This is a narrow heuristic result, not proof of complete ownership safety.

See `security_best_practices_report.md` for the evidence-backed findings and
remaining limitations.
