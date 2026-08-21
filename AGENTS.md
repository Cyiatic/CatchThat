# CatchThat project guidance

## Scope

CatchThat is a private/local-first archive engine, import flow, attended
visible-DOM capture adapter, and offline static viewer for an authorized
Snapchat Web conversation. Source control contains code, synthetic fixtures,
and documentation only. Real chats, browser captures, attachments, avatars,
and exports belong under the ignored `private-data/` directory or another
access-controlled location.

## Safety boundary

The browser adapter is a foreground, user-triggered, read-only DOM read of the
currently open Snapchat Web chat. It must never:

- automate login, friend actions, account search, or message sending;
- inspect cookies, localStorage, sessionStorage, tokens, passwords, or private
  APIs;
- call `fetch`, XHR, WebSocket, background jobs, or remote media downloads;
  - crawl, expand, or discover chats without the user doing it; or
- use stealth behavior to hide capture or evade notifications.

The user controls which chat is open and explicitly starts each capture action.
An action may perform one bounded `older` or `newer` scroll step in the
foreground, then records only visible message rows in the resulting DOM
window. There is no unattended loop. It must preserve visible text, media
placeholders, saved-state/retention indicators, source references, and capture
provenance. It must never imply that a rendered range is the whole
conversation.

## Development commands

From this directory in Windows PowerShell:

```powershell
$env:PYTHONPATH = "src"
python -m catchthat validate fixtures/sample/archive.json
python -m catchthat build fixtures/sample/archive.json --output dist/sample
python -m catchthat verify dist/sample
python -m catchthat export-text fixtures/sample/archive.json
python -m catchthat import-capture --input private-data\capture-001.json --output private-data\capture-001.archive.json
python -m catchthat merge-captures `
  --input private-data\range-001.json `
  --input private-data\range-002.json `
  --output private-data\merged-transcript.json
python -m catchthat verify-coverage private-data\merged-transcript.json
python -m unittest discover -s tests -v
```

`import-transcript` is retained as a friendly alias for
`import-capture`. `merge-transcripts` is retained as an alias for
`merge-captures`.

## Coverage rules

Ranges are merged by stable message ID, overlapping IDs are deduplicated, and
conflicting duplicate records are reported. Coverage is `verified` only when
all ranges carry capture metadata, adjacent ranges form an overlap-linked
chain, both oldest/newest boundaries are observed or explicitly attested, and
there are no conflicts. Even then, the result means “verified from observed
rendered ranges”; it cannot prove messages Snapchat failed to render or later
deleted.

## Viewer rules

- The generated viewer is static, dependency-free, and works offline.
- The viewer is visibly read-only and keeps the partial-coverage state
  prominent.
- Search covers the complete normalized archive; message rendering is bounded
  for large archives while deep links reveal the selected message.
- Author filters, timestamp modes, source/provenance details, media
  placeholders, print/PDF output, and the generated SHA-256 manifest remain
  available without a live Snapchat session.

## Live smoke-test handoff

The adapter intentionally uses conservative selector candidates because
Snapchat Web DOM details can vary by release. If the live browser is logged
out, use the synthetic fixture and run the commands above. The exact next
smoke-test step is documented in `docs/live-smoke-test.md`: sign in manually in
the in-app browser, open one intended chat yourself, run the read-only evaluate
adapter once, then use an explicit one-step `older` or `newer` invocation while
inspecting its selector notes and boundary result before importing the range.
Never enter credentials into CatchThat or the tool.
