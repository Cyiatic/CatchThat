# Live selector smoke test

The live adapter is intentionally conservative because Snapchat Web’s DOM is
not a stable public API. A signed-in Rick Bailer chat was smoke-tested in the
Codex in-app browser; use the same procedure for each new Snapchat Web layout:

1. In the Codex in-app browser, sign in manually if needed. Never provide
   credentials to CatchThat or to the tool.
2. Open exactly one intended conversation yourself. Do not use the adapter to
   search, navigate, click, expand, or discover another chat.
3. Run the read-only evaluate surface with the contents of
   `tools/snapchat_visible_capture.js` and no options for the current range.
4. For the next range, explicitly invoke the same adapter with one option,
   `{scroll: "older"}` or `{scroll: "newer"}`. This moves the current chat's
   visible message scroller by one bounded step, waits for the foreground DOM
   to settle, and captures that range. Repeat only when the user starts the
   next action; the adapter never runs a background loop.
5. Inspect the returned `metadata.source.selector_notes`,
   `metadata.thread_identity`, `metadata.capture_range`, and the first/last
   message IDs and timestamps. Confirm `capture_range.scroll_action` reports
   the requested direction and whether the scroll moved, and confirm every
   row is from the current chat, not the sidebar or a notification surface.
6. Save each returned object under `private-data\range-001.json`, run
   `python -m catchthat import-capture ...`, and validate/build it.

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

The Rick Bailer smoke test captured six timestamped visible rows, skipped one
visible row without a timezone-aware timestamp, and correctly reported a
partial range (`at_start: false`, `at_end: true`). The resulting raw capture
and normalized archive were validated and built locally under ignored
`private-data/`; they were not committed or pushed.

A longer authorized Aiden Lautt smoke test also validated the attended scroll
path: one `{scroll: "older"}` invocation selected the conversation pane, moved
the visible range by one bounded step, returned 62 timestamped rows, and
reported both boundaries as unconfirmed. The live result was treated as
private and was not committed or pushed.

If the browser is logged out, stop at the synthetic smoke build in the README;
do not attempt credential entry through CatchThat.
