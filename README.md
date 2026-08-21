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
user opened. The user controls scrolling and expansion. CatchThat never
automates login or friend actions, searches arbitrary accounts, sends
messages, inspects cookies/browser stores/tokens/passwords, calls private APIs,
uses fetch/XHR/WebSocket, downloads media, crawls in the background, or hides
capture behavior. Remote media is recorded as a reference or placeholder; it
is never fetched by the project.

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

`import-transcript` is an alias for `import-capture`; it also accepts a bare
message array. Each imported message keeps its source filename and record
index, and absolute paths are omitted from the normalized archive.

## Capture one currently open Snapchat Web chat

1. Open Snapchat Web in the Codex in-app browser and open the intended chat
   yourself. Do not ask CatchThat to log in, search for a friend, or navigate
   to a chat.
2. Scroll or expand the chat yourself. Capture one visible DOM window at a
   time, preferably with overlap between windows. The adapter does not scroll
   or expand anything.
3. Pass `tools/snapchat_visible_capture.js` to the in-app browser’s
   read-only evaluate surface. It returns a JSON object; save that result as
   `private-data\range-001.json`.
4. Review the returned `metadata.source.notes`, `metadata.thread_identity`,
   `metadata.capture_range`, `selector_notes`, and the message count before
   importing.
5. Normalize and build the offline viewer. For more history, repeat steps 2–4
   after the user moves the open chat, then merge the ranges.

The adapter records the sanitized current URL/path and thread heading, oldest
and newest rendered message IDs/timestamps, rendered count, scroll metrics,
boundary flags, capture time, selector notes, and source notes. It never
claims a complete chat from one rendered window. See
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
  "participants": [{"id": "mara", "display_name": "Mara"}],
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

`media` entries are placeholders or already-supplied local files; HTTP(S)
references remain provenance and do not become runtime dependencies.

## Current status

The fixture, validator, importer, range merge/coverage verifier, attended
capture adapter, test suite, and offline viewer are included. Live Snapchat
selector certainty is intentionally pending one signed-in, user-opened chat;
the project does not store live data in the repository.

