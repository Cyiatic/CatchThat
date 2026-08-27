# CatchThat security best-practices review

Date: 2026-08-27

Scope: the local CatchThat Python archive engine, generated static viewer,
foreground capture helper, and the Concordance-derived local tooling added in
this pass. No Snapchat credentials, cookies, browser stores, live page data,
or remote API were accessed during this review.

## Review evidence

- Python syntax check: `python -m py_compile src/catchthat/core.py src/catchthat/cli.py`.
- JavaScript syntax checks: the capture adapter, visible controls, generated
  viewer app, and generated catalog app all passed `node --check`.
- Static sink scan found no `innerHTML`, `document.write`, `eval`,
  `postMessage`, browser storage, `fetch`, XHR, or WebSocket usage in the
  viewer, adapter, or controls after the hardening pass.
- Sentry CLI check: `sentry auth status` is unavailable because the CLI is not
  installed. CatchThat is an offline static viewer with no production runtime,
  so telemetry was not added; adding it would expand the privacy boundary.
- Ownership-map runs over recent history reported no default-rule flagged
  orphaned sensitive paths or bus-factor hotspots in CatchThat or Concordance.
  This is a narrow heuristic, not a complete ownership audit.
- Portable bundle tests cover round-trip import/export and the optional
  password-protected AES-256-GCM path, including wrong-password rejection and
  safe extraction limits.

## Findings

### CT-JS-001 — generated viewer policy boundary — Medium — Resolved

- Location: `src/catchthat/core.py:1664-1706` (`build_archive`), generated
  `index.html`.
- Evidence: the builder extracts the template stylesheet to `app.css`, keeps
  the behavior in same-origin `app.js`, and emits a restrictive CSP with
  `default-src 'none'`, `script-src 'self'`, `style-src 'self'`,
  `connect-src 'none'`, `object-src 'none'`, and `form-action 'none'`.
- Impact: a static archive can contain user-controlled text and source
  references. A CSP limits unexpected resource execution if a future UI edit
  introduces a mistake.
- Fix/mitigation: generated artifacts are external-file-only and verified by
  the SHA-256 manifest. The CSP is a document meta policy because the viewer
  is opened from `file:`; deployments that serve it should also send an HTTP
  CSP header.
- False-positive/limit: the source template necessarily has build-time CSS
  and script blocks; the generated artifact, not the template, is the shipped
  boundary.

### CT-JS-002 — local asset URL validation — Medium — Resolved

- Location: `src/catchthat/core.py:99-109` (`_normalise_local_reference`) and
  `viewer/template.html:981-1003` (`safePath`, `safeHttp`).
- Evidence: local references reject schemes, protocol-relative values,
  absolute paths, traversal segments, empty path segments, and backslash
  ambiguity. HTTP references are parsed and limited to `http:`/`https:` with a
  hostname.
- Impact: without the allowlist, a tampered archive could make an offline
  viewer assign a non-local URL or a traversal-like asset reference to a DOM
  attribute.
- Fix/mitigation: both normalized archives and the viewer enforce the same
  relative-path model; source-reference links use `safeHttp` and open with
  `noreferrer noopener`.
- False-positive/limit: this does not make a malicious local file safe to
  open; it only prevents the viewer from treating it as a resource reference.

### CT-JS-003 — DOM construction in foreground controls — Low — Resolved

- Location: `tools/snapchat_capture_controls.js` panel construction.
- Evidence: the helper now creates nodes and assigns static attributes and
  `textContent`; it does not use an HTML string sink. It remains a visible,
  user-installed panel and does not inspect storage or call network APIs.
- Impact: reduces the chance that a future status/result field becomes an HTML
  injection path in the page where the helper is evaluated.
- Fix/mitigation: keep result data in the read-only textarea `.value`, retain
  the visible panel, and continue forbidding login/account actions and
  background work.
- False-positive/limit: inline style attributes are static presentation for
  the user-installed helper and are not a data-bearing HTML sink.

### CT-PY-001 — private archive handling — Low — Accepted mitigation

- Location: `AGENTS.md`, `.gitignore`, `src/catchthat/core.py` evidence,
  redaction, catalog, and capture-session functions.
- Evidence: session records contain relative capture paths and SHA-256 hashes;
  evidence reports exclude message bodies; safe-share output removes content,
  identities, source links, avatar paths, and media bytes; generated manifests
  hash local output files.
- Impact: private data remains sensitive even when the viewer is offline.
- Fix/mitigation: keep live captures and generated private viewers under the
  ignored `private-data/` tree or another access-controlled directory. Use
  `redact` before sharing. `verify-evidence`, `verify`, and `verify-catalog`
  detect changed or missing files.
- False-positive/limit: hashes prove file identity, not confidentiality.
  Filesystem permissions and any disk encryption remain the owner’s
  responsibility.

## Not findings / intentionally out of scope

- No remote media downloader, private API, login automation, account search,
  message sending, WebSocket/XHR/fetch capture, or stealth notification logic
  was added.
- No Sentry integration was added. This project has no online runtime, and
  telemetry would conflict with the declared local-first boundary.
- Concordance’s platform-specific import paths were not copied because they
  would require platform authority outside the visible-DOM scope. Its useful
  portable/encrypted sharing idea is now implemented as a local ZIP workflow
  with an optional `cryptography` dependency. Encryption protects a bundle in
  transit or at rest; it does not replace redaction or filesystem controls.

## Remaining validation limits

The live Snapchat selector set still needs one signed-in, user-opened chat
smoke test after a Snapchat Web release change. The correct test is the
documented visible-DOM capture flow in `docs/live-smoke-test.md`; if the
browser surface is read-only, use the one explicit adapter evaluation and do
not install controls. This review does not claim that a synthetic fixture
proves every live DOM variant.
