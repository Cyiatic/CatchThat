# Live selector smoke test

The live adapter is intentionally conservative because Snapchat Web’s DOM is
not a stable public API. A signed-in, user-opened chat was smoke-tested in the
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
   user-triggered foreground run. It stops at a boundary, no progress, or the
   bounded step cap; repeated rendered windows are recorded as provenance but
   do not stop a walk while scrollTop is still moving. It never runs a
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

Snapchat can render a message-group `<li>` around smaller message `<li>` rows.
The adapter excludes that aggregate wrapper when it contains visible
timestamped child rows, then retains the child rows as the message units. It
also uses a source ID or visible DOM path to avoid counting the same rendered
row twice when timestamp metadata and sibling discovery reach it through more
than one selector path. Two genuinely separate rows with identical visible
text, author, and timestamp remain separate records.

For media, inspect the returned `messages[].media` entries and
`participants[].visible_profile` values during the smoke test. The adapter
preserves visible image/video/audio/sticker/Bitmoji kind, subtype, alt text,
dimensions, source element, remote source reference, avatar reference, handle,
status, label, and visible source ID. A displayed avatar may additionally
include a bounded `avatar_data_url` when already-rendered pixels were readable;
`import-capture` turns that into a local `assets/avatars/` file and records
`avatar_provenance`. A rendered message `img` or Bitmoji/sticker canvas may
similarly include bounded `media_data_url` pixels; import materializes those
under `assets/media/` and records `media_provenance`. Snapchat may expose a
Bitmoji as a small square layout-only image with no alt text; the adapter uses
the visible author/header context to associate it and can also capture a
readable canvas avatar. No remote fetch is used.
Confirm that a message image or Bitmoji is not incorrectly classified as the
sender avatar, and that any visible profile metadata belongs to the current
conversation row. When the page blocks pixel reads, confirm the viewer honestly
falls back to the placeholder/reference-only state.

Earlier authorized smoke runs captured timestamped visible rows, skipped an
uncertain row without a timezone-aware timestamp, and correctly reported
partial ranges. Their raw captures and normalized archives were validated and
built locally under ignored `private-data/`; they were not committed or
pushed.

One longer smoke run showed that the same DOM row IDs can repeat while the
conversation pane moves. That result exposed a capture bug: stopping after two
repeated windows could prevent the walk from reaching the oldest boundary in a
non-virtualized pane. The live result was treated as private and was not
committed or pushed.

A follow-up run captured 62 timestamped rows at the oldest visible boundary
(`at_start: true`, `at_end: false`). It preserved seven visible link-preview
thumbnails and excluded seven decorative favicon nodes; two visible
participants were retained with their visible labels. The normalized result
remains a partial range, not a complete-chat claim.

The current adapter records repeated rendered message IDs through
`unchanged_window_steps` and `repeated_ranges` evidence, but does not stop
solely for that reason:
non-virtualized Snapchat panes can keep the same DOM row set while scrollTop
continues moving toward the oldest boundary. Boundary, no-progress, and bounded
step-cap results govern the walk; repeated ranges remain a coverage caveat.

A grouped-row smoke run after the deduplication fixes reached
`at_start: true` with 40 leaf message rows, two attributed participants, and
three media records. It skipped seven visible date-separator nodes (not message
rows), preserved grouped timestamps as approximate provenance, and remained
partial because `at_end: false`. The resulting viewer remained under ignored
`private-data/`.

A group-chat smoke run exercised the complementary newer walk. It produced 77
unique rows from eight bounded ranges and seven foreground scroll steps, reached
both observed boundaries, attributed all rows to seven visible participants,
and reported zero unknown authors. Twenty-three rows inherited a timestamp from
a visible message group, while two date-separator nodes were skipped. Eleven
visible Snap-media nodes appeared only after walking toward the newest boundary;
they were preserved as media placeholders with dimensions and opaque visible
labels (two media-only rows, including one ten-item gallery), because no
readable pixels or safe HTTP source reference was exposed. All seven participant
avatars were reference-only for the same cross-origin pixel-read limitation.
`verify-coverage` reported `Complete: True` for the observed rendered range,
while retaining the caveat that deleted or unseen history cannot be established
from visible DOM capture. The normalized archive and viewer remained under
ignored `private-data/`.

If the browser is logged out, stop at the synthetic smoke build in the README;
do not attempt credential entry through CatchThat.
