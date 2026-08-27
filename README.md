<p align="center">
  <img src="assets/catchthat-logo.png" alt="CatchThat ghost vacuum logo" width="240">
</p>

# CatchThat

CatchThat is a private/local-first Snapchat chat archiver. It turns a supplied
transcript or a foreground, user-triggered visible-DOM capture of the current
Snapchat Web chat into normalized JSON and an offline reader with a clear
coverage ledger.

It is modeled on the sound archive/merge ideas in the local Concordance-style
Discord project, but this project is independent and intentionally does not
edit or depend on that checkout.

## Safety boundary

The browser adapter only reads message rows already rendered in the chat the
user opened. Each user-triggered run may perform one bounded `older` or `newer`
scroll step; the user remains in control of every action and expansion.
CatchThat never automates login or friend actions, searches arbitrary accounts,
sends messages, inspects cookies/browser stores/tokens/passwords, calls private APIs,
uses fetch/XHR/WebSocket, downloads remote media, crawls in the background, or
hides capture behavior. A displayed participant avatar may be copied from
already-rendered readable pixels into a bounded local asset; cross-origin or
blob-only avatars remain references and are never fetched by the project.

Real captures belong under `private-data/`, which is ignored by Git. Treat the
archive as sensitive even though the viewer is offline.

## Codex plugin and public package

The repository includes a repo-local, skills-only Codex plugin at
`plugins/catchthat/`. It packages the workflow, safety boundary, and CLI
handoff without an MCP server or an account-access connector. The optional
browser helper operates only on a chat the user has already opened and signed
into themselves; CatchThat never receives credentials or browser session
state.

CatchThat is an offline archive companion, not a Snapchat/Discord profile
reconstructor. It can preserve supplied or visibly rendered messages, bounded
media/profile pixels, and provenance. It cannot recreate friend state, hidden
history, or anything that was not supplied or rendered.

Prepare a public/source-only attachment with the release script:

```powershell
.\scripts\package_release.ps1 -OutputPath dist\catchthat-release.zip
```

The script allowlists the source, documentation, tests, tools, plugin, and
synthetic fixture, then validates the staging tree. It never copies
`private-data/` or generated `output/` content. This separation follows the
[OpenAI plugin packaging model](https://developers.openai.com/plugins/build/plugins):
the plugin is source-only and the local workflow remains explicit about what
the user supplies and approves.

## Quick start with the synthetic fixture

From `catchthat/` in Windows PowerShell:

```powershell
$env:PYTHONPATH = "src"
python -m catchthat validate fixtures/sample/archive.json
python -m catchthat build fixtures/sample/archive.json --output dist/sample
python -m catchthat verify dist/sample
Start-Process (Resolve-Path dist/sample/index.html)
python -m catchthat export-text fixtures/sample/archive.json
python -m unittest discover -s tests -v
```

The generated directory is portable: copy `index.html`, `app.css`, `app.js`,
`archive.json`, `manifest.json`, and its local `assets/` together. `verify`
checks the archive, required files, referenced assets, sizes, SHA-256 hashes,
and the generated offline CSP boundary.

## Import a capture or supplied transcript

The adapter returns JSON shaped like the import format. Keep the raw result
private, then normalize it:

```powershell
python -m catchthat import-capture `
  --input private-data\capture-001.json `
  --output private-data\capture-001.archive.json
python -m catchthat build `
  private-data\capture-001.archive.json `
  --output private-data\capture-001-view
```

For the common post-capture path, `capture-result` performs the import and
can build the viewer and readable text export together:

```powershell
python -m catchthat capture-result `
  --input private-data\capture-001.json `
  --output private-data\capture-001.archive.json `
  --build-output private-data\capture-001-view `
  --text-output private-data\capture-001.txt
```

This command processes a saved result; it does not open a browser or capture
without the user explicitly running the adapter in the read-only evaluate
surface.

`import-transcript` is an alias for `import-capture`; it also accepts a bare
message array. Each imported message keeps its source filename and record
index, and absolute paths are omitted from the normalized archive.

## Capture one currently open Snapchat Web chat

1. Open Snapchat Web in the Codex in-app browser and open the intended chat
   yourself. Do not ask CatchThat to log in, search for a friend, or navigate
   to a chat.
2. On a writable evaluate surface, evaluate
   `tools/snapchat_visible_capture.js` once, then evaluate
   `tools/snapchat_capture_controls.js` in the same tab. This installs a
   visible CatchThat panel with `Capture current`, `Walk older`, and `Walk
   newer` buttons. Each click is user-triggered and bounded; it reads only the
   current rendered chat window. The result stays in the panel and in
   `CatchThatCapture.lastResult` for local saving. If the browser exposes only
   a read-only/frozen evaluate surface, run the adapter and invoke its local
   `capture({walk: "older", max_steps: 40})` function in one explicit async
   evaluation instead; do not attempt to create a panel or bypass that limit.
3. For direct evaluation without the panel, call the adapter with no options
   for the current range, `{scroll: "older"}`/`{scroll: "newer"}` for one
   bounded step, or `{walk: "older", max_steps: 40}` (or `newer`) for an
   attended foreground walk. It waits for the visible DOM to settle and stops
   at a boundary, no-progress result, or the bounded step cap; repeated
   rendered windows are recorded as provenance but do not stop a walk while
   scrollTop is still moving. It never starts a background job. Save each
   returned JSON object as
   `private-data\range-001.json`, `range-002.json`, and so on.
4. Review the returned `metadata.source.notes`, `metadata.thread_identity`,
   `metadata.capture_range`, `selector_notes`, and the message count before
   importing.
5. Normalize and build the offline viewer. Merge overlapping ranges after the
   attended capture runs; do not treat one run as a complete conversation.

The adapter records the sanitized current URL/path and thread heading, oldest
and newest rendered message IDs/timestamps, rendered count, scroll metrics,
boundary flags, the requested scroll direction and movement, walk step/range
metadata including per-range message IDs, capture time, selector notes, and
source notes. Repeated rendered boundaries are retained as a DOM evidence note;
coverage still depends on observed boundaries and linked ranges, and never
claims unseen or deleted history. See
`docs/live-smoke-test.md` for the exact next validation step and selector
uncertainty.

For Snapchat’s grouped message markup, the adapter records leaf message rows
instead of the surrounding aggregate `<li>`, carries a visible group timestamp
or author forward only with explicit provenance, and uses stable source IDs or
visible DOM paths to prevent duplicate enumeration.

## Merge overlapping ranges and verify coverage

```powershell
python -m catchthat merge-captures `
  --input private-data\range-001.json `
  --input private-data\range-002.json `
  --input private-data\range-003.json `
  --output private-data\merged-transcript.json `
  --reached-start `
  --reached-end
python -m catchthat verify-coverage private-data\merged-transcript.json
python -m catchthat import-capture `
  --input private-data\merged-transcript.json `
  --output private-data\conversation.json
python -m catchthat build private-data\conversation.json --output private-data\conversation-view
```

Verification is conservative: adjacent ranges must share message IDs, both
oldest/newest boundaries must be observed or explicitly attested, and
conflicts must be absent. A `verified` report means verified from the observed
rendered ranges, not proof that Snapchat had no unseen or deleted messages.
Incomplete reports always include a concrete next action, and the viewer
repeats it in a prominent coverage banner.

## Review, share, and organize archives locally

The Concordance comparison identified several useful archive-engine features
that fit CatchThat without widening its Snapchat safety boundary:

```powershell
# Keep a tamper-evident, message-free provenance sidecar.
python -m catchthat export-evidence `
  --input private-data\conversation.json `
  --output private-data\conversation.evidence.json
python -m catchthat verify-evidence private-data\conversation.evidence.json

# Make an anonymized copy for a bug report or UI fixture; the source is never overwritten.
python -m catchthat redact `
  --input private-data\conversation.json `
  --output private-data\conversation.safe-share.json

# Track multiple attended ranges before merging them.
python -m catchthat capture-session init `
  --output private-data\conversation.session.json `
  --title "Example capture"
python -m catchthat capture-session add `
  --session private-data\conversation.session.json `
  --input private-data\range-001.json
python -m catchthat capture-session status --session private-data\conversation.session.json
python -m catchthat capture-session finalize `
  --session private-data\conversation.session.json `
  --output private-data\conversation.merged.json

# Build one local launcher for several archives. The catalog is metadata-only;
# each linked archive remains a separately integrity-checked viewer.
python -m catchthat build-catalog `
  --input private-data\conversation-a.archive.json `
  --input private-data\conversation-b.archive.json `
  --output private-data\catalog
python -m catchthat verify-catalog private-data\catalog
```

Evidence contains archive hashes, coverage/boundary metrics, source metadata
and local-asset hashes, but never message bodies or participant collections.
The safe-share profile removes content, identities, source links, avatar paths,
and media bytes while retaining timestamps and enough coverage/media shape for
layout and audit testing. The session ledger stores only relative capture paths
and hashes, so a changed raw capture is rejected before finalization.

### Portable and encrypted bundles

Export only a reviewed viewer directory or redacted archive. The ZIP format is
portable and can be imported into a new local directory with path and size
checks:

```powershell
python -m catchthat export-bundle `
  --input private-data\conversation-safe-view `
  --output private-data\conversation.safe.catchthat.zip
python -m catchthat import-bundle `
  --input private-data\conversation.safe.catchthat.zip `
  --output private-data\conversation-restored-view
```

For a password-protected share, install the optional dependency and keep the
password out of command history. The CLI prompts securely unless a private
password file is explicitly supplied:

```powershell
python -m pip install -e ".[secure]"
python -m catchthat encrypt-bundle `
  --input private-data\conversation.safe.catchthat.zip `
  --output private-data\conversation.safe.catchthat.enc
python -m catchthat decrypt-bundle `
  --input private-data\conversation.safe.catchthat.enc `
  --output private-data\conversation-decrypted-view
```

The convenience script redacts, builds, verifies, exports, and optionally
encrypts in one local pipeline. It refuses to overwrite an existing output:

```powershell
.\scripts\share_archive.ps1 `
  -ArchivePath private-data\conversation.json `
  -OutputPath private-data\conversation.safe.catchthat.enc `
  -Encrypt
```

Encryption provides confidentiality for the bundle; it does not replace
redaction, access controls, or the archive’s integrity manifest.

## Archive format

The normalized schema is versioned and intentionally explicit:

```json
{
  "schema_version": 1,
  "metadata": {
    "kind": "snapchat_chat",
    "title": "Mara and Eli",
    "thread_id": "thread-synthetic-001",
    "captured_at": "2024-03-10T02:00:00Z",
    "display_timezone": "America/Phoenix",
    "capture_range": {
      "version": 1,
      "rendered_count": 7,
      "oldest_message_id": "snap-001",
      "newest_message_id": "snap-007",
      "at_start": false,
      "at_end": true
    },
    "source": {
      "type": "snapchat_visible_dom",
      "url": "https://web.snapchat.com/chat/thread-synthetic-001",
      "notes": ["Visible DOM only; partial coverage is explicit."]
    }
  },
  "participants": [{
    "id": "mara",
    "display_name": "Mara",
    "visible_profile": {"handle": "mara", "status": "Active", "source_id": "user-mara"}
  }],
  "messages": [{
    "id": "snap-001",
    "author_id": "mara",
    "timestamp": "2024-03-10T01:30:00Z",
    "content": "A visible message",
    "content_kind": "visible_text",
    "saved_state": {"state": "saved", "evidence": "Saved in chat"},
    "retention": {"state": "unknown", "visible": false},
    "provenance": {"source_file": "range-001.json", "record_index": 0}
  }]
}
```

`media` entries preserve the visible kind, optional Bitmoji/sticker subtype,
alt text, dimensions, source element, and either a safe local `path` or an
HTTP(S) `source_url`. Local supplied assets are displayed in the offline
viewer; remote message references remain provenance-only and are never fetched
by CatchThat. When a rendered message `img` or Bitmoji/sticker canvas can be
read as visible pixels, the adapter supplies a bounded PNG data URL and
`import-capture` materializes it under `assets/media/`, records
`media_provenance`, then removes the data URL from normalized JSON. Video/audio
and cross-origin or otherwise unreadable media remain explicit placeholders or
references. The same rule applies to participant avatars under
`assets/avatars/` with `avatar_provenance`; otherwise `avatar_ref` remains
reference-only. Snapchat avatar images can be layout-only `<img>` elements
without alt text or semantic class names, so the foreground adapter also
recognizes small square images only when they are in the visible author context
or a named header/list item. Participant `visible_profile` fields contain only metadata
exposed in the captured DOM (for example a handle, status, label, or source ID).

## Current status

The fixture, validator, importer, range merge/coverage verifier, capture-session
ledger, metadata evidence verifier, safe-share redactor, multi-archive catalog,
portable/encrypted bundle workflow, attended capture adapter, test suite,
offline viewer, public-package validator, and GitHub Actions smoke build are
included. The live smoke-test handoff remains intentionally generic: it needs
one user-opened, signed-in chat after a Snapchat Web release change, and no
live capture is stored in the repository. The archive is explicit about the
limits of visible-DOM coverage: deleted or unseen history is not established,
and cross-origin avatars/media remain reference-only when pixels are
unreadable.
The project does not store live data in the repository.
