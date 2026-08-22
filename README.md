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

The generated directory is portable: copy `index.html`, `app.js`,
`archive.json`, `manifest.json`, and its local `assets/` together. `verify`
checks the archive, required files, referenced assets, sizes, and SHA-256
hashes.

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
   at a boundary, no-progress result, unchanged rendered window, or the step
   cap; it never starts a background job. Save each returned JSON object as
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
reference-only. Participant `visible_profile` fields contain only metadata
exposed in the captured DOM (for example a handle, status, label, or source ID).

## Current status

The fixture, validator, importer, range merge/coverage verifier, attended
capture adapter, test suite, offline viewer, and GitHub Actions smoke build are
included. The current signed-in Aiden Lautt smoke test confirms the selectors
and bounded foreground walk on this layout, while repeated message boundaries
leave additional history/loading behavior unverified. The project does not
store live data in the repository.
