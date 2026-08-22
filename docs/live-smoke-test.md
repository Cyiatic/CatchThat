# Live selector smoke test

The live adapter is intentionally conservative because Snapchat Web’s DOM is
not a stable public API. A signed-in Rick Bailer chat was smoke-tested in the
Codex in-app browser; use the same procedure for each new Snapchat Web layout:

1. In the Codex in-app browser, sign in manually if needed. Never provide
   credentials to CatchThat or to the tool.
2. Open exactly one intended conversation yourself. Do not use the adapter to
   search, navigate, click, expand, or discover another chat.
3. On a writable evaluate surface, run the contents of
   `tools/snapchat_visible_capture.js`, then evaluate
   `tools/snapchat_capture_controls.js` in the same tab. The visible panel’s
   `Capture current`, `Walk older`, and `Walk newer` buttons are the preferred
   smoke path; the latest JSON stays in the panel and
   `CatchThatCapture.lastResult` for local saving. If the evaluate surface is
   read-only and freezes `window`/DOM creation (as the Codex in-app surface
   does), evaluate the adapter and invoke
   `capture({walk: "older", max_steps: 40})` in one explicit async expression
   instead; do not try to mount the
   panel or work around the surface restrictions.
4. To test attended capture without manual scroll input, explicitly invoke the
   adapter with `{walk: "older", max_steps: 40}` (or `newer`) when testing the
   direct evaluate path. It moves the
   current chat's visible message scroller by one bounded step, waits for the
   foreground DOM to settle, captures that range, and repeats only within this
   user-triggered foreground run. It stops at a boundary, no progress, an
   unchanged rendered message window, or the step cap; it never runs a
   background loop. Use `{scroll: "older"}` or `{scroll: "newer"}` when
   validating one step only. `settle_ms` may be supplied for a slow layout and
   is bounded by the adapter.
5. Inspect the returned `metadata.source.selector_notes`,
   `metadata.thread_identity`, `metadata.capture_range`, and the first/last
   message IDs and timestamps. For a walk, confirm
   `capture_range.scroll_walk` reports the stop reason and range count; for a
   single step, confirm `capture_range.scroll_action` reports the requested
   direction and whether the scroll moved. Confirm every row is from the
   current chat, not the sidebar or a notification surface.
6. Save each returned object under `private-data\range-001.json`, run
   `python -m catchthat capture-result --input private-data\range-001.json
   --output private-data\range-001.archive.json --build-output
   private-data\range-001-view`, and inspect the coverage result.

The adapter currently prefers message-row candidates in this order:

1. visible rows anchored to `time[datetime]`, `data-timestamp`, or `data-time`
2. `[data-message-id]`
3. `[data-testid*="message" i]`
4. `[role="article"]`
5. `main [role="listitem"]`
6. `main [class*="message" i]`
7. `main li`

It accepts only visible candidates with a timestamp-like `datetime`, visible
text or media evidence, and no `nav`/`aside` ancestor. Timestamp-anchored leaf
rows prevent Snapchat’s visible conversation from being confused with its
sidebar `role=listitem` nodes. The adapter derives author labels from explicit
author metadata or the visible message header, and uses visible `[dir="auto"]`
content when available. If a selector is too broad or no timestamps are
exposed, the capture reports selector notes and skips uncertain rows rather
than inventing dates or silently claiming coverage. Adjustments should remain
DOM-only and read-only.

For media, inspect the returned `messages[].media` entries and
`participants[].visible_profile` values during the smoke test. The adapter
preserves visible image/video/audio/sticker/Bitmoji kind, subtype, alt text,
dimensions, source element, remote source reference, avatar reference, handle,
status, label, and visible source ID. A displayed avatar may additionally
include a bounded `avatar_data_url` when already-rendered pixels were readable;
`import-capture` turns that into a local `assets/avatars/` file and records
`avatar_provenance`. A rendered message `img` or Bitmoji/sticker canvas may
similarly include bounded `media_data_url` pixels; import materializes those
under `assets/media/` and records `media_provenance`. No remote fetch is used.
Confirm that a message image or Bitmoji is not incorrectly classified as the
sender avatar, and that any visible profile metadata belongs to the current
conversation row. When the page blocks pixel reads, confirm the viewer honestly
falls back to the placeholder/reference-only state.

The Rick Bailer smoke test captured six timestamped visible rows, skipped one
visible row without a timezone-aware timestamp, and correctly reported a
partial range (`at_start: false`, `at_end: true`). The resulting raw capture
and normalized archive were validated and built locally under ignored
`private-data/`; they were not committed or pushed.

A longer authorized Aiden Lautt smoke test validated the attended walk path
without manual scroll input: `{walk: "older", max_steps: 40}` selected the
conversation pane, performed two bounded steps, and stopped at
`rendered_window_unchanged` after three captures. It observed 62 timestamped
message rows, two participants, and eight media references; neither boundary
was established (`at_start: false`, `at_end: false`). The oldest visible row was
`local-9d4fe06b` at `2020-04-30T05:57:47.476Z`; the newest was `local-7f481427`
at `2021-11-17T04:47:06.151Z`. The read-only evaluate surface did not expose
canvas creation, so media and avatar pixels stayed as references/placeholders;
no source bytes were fetched. This confirms the bounded-walk guard and selector
shape on the current layout, but does not verify additional history/loading.
The live result was treated as private and was not committed or pushed.

A follow-up Aiden run against the currently open chat captured the same 62
timestamped rows at the oldest visible boundary (`at_start: true`,
`at_end: false`). It preserved seven visible link-preview thumbnails and
excluded seven decorative favicon nodes; two visible participants were
retained with their visible labels. The normalized result is under ignored
`private-data\\aiden-media-run-20260821.*` and remains a partial range, not a
complete-chat claim.

The current adapter treats two consecutive moved steps with the same rendered
message IDs as `rendered_window_unchanged` and stops the walk early. This is an
intentional guard against reporting scroll movement as pagination progress; a
new signed-in run should record that stop reason before any selector tuning.

If the browser is logged out, stop at the synthetic smoke build in the README;
do not attempt credential entry through CatchThat.
