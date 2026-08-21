# Live selector smoke test

The live adapter is intentionally conservative because Snapchat Web’s DOM is
not a stable public API and no signed-in chat was available during the initial
build. This is the exact next step once the user has a suitable browser state:

1. In the Codex in-app browser, sign in manually if needed. Never provide
   credentials to CatchThat or to the tool.
2. Open exactly one intended conversation yourself. Do not use the adapter to
   search, navigate, click, scroll, or expand.
3. Scroll/expand the open chat yourself until a useful visible window is
   present. Keep at least one overlapping message visible if this is a later
   range.
4. Run the read-only evaluate surface with the contents of
   `tools/snapchat_visible_capture.js`.
5. Inspect the returned `metadata.source.selector_notes`,
   `metadata.thread_identity`, `metadata.capture_range`, and the first/last
   message IDs and timestamps. Confirm that every row is from the current
   chat, not the sidebar or a notification surface.
6. Save the returned object under `private-data\range-001.json`, run
   `python -m catchthat import-capture ...`, and validate/build it.

The adapter currently tries message-row candidates in this order:

1. `[data-message-id]`
2. `[data-testid*="message" i]`
3. `[role="article"]`
4. `main [role="listitem"]`
5. `main [class*="message" i]`

It accepts only visible candidates with a timestamp-like `datetime`, visible
text or media evidence, and no `nav`/`aside` ancestor. If a selector is too
broad or no timestamps are exposed, the capture reports selector notes and
skips uncertain rows rather than inventing dates or silently claiming
coverage. Adjustments should be made only after inspecting one user-opened
chat and should remain DOM-only and read-only.

If the browser is logged out, stop at the synthetic smoke build in the README;
do not attempt credential entry through CatchThat.

