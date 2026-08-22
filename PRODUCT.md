# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

The primary user is the owner of a private Snapchat conversation, or someone
acting with the conversation owner’s authorization. They want to preserve and
read a conversation after leaving Snapchat Web, including when working
offline.

This audience and workflow are inferred from the explicit project brief; no
additional user interview was available in the current execution mode.

## Product Purpose

CatchThat turns a user-supplied transcript or an attended visible-DOM capture
of one currently open Snapchat Web chat into a normalized JSON archive and a
portable offline reader. Success means the owner can read messages in a
clear `Person: message` rhythm while seeing exactly what was captured, which
media is only a placeholder, and where each record came from.

## Positioning

CatchThat separates acquisition from presentation: acquisition is a narrow,
foreground, user-triggered read of the visible DOM in the chat the user has
already opened, while the archive and viewer remain local, deterministic, and
service-independent.

## Operating Context

- The source is Snapchat Web in the Codex in-app browser; the archive owner
  opens the intended chat and starts each capture action in the foreground.
- A capture run may perform one bounded `older` or `newer` scroll step, or a
  user-triggered bounded walk made from those steps, when explicitly requested.
  There is no background loop: the visible result reports the direction, step
  cap, ranges, movement, and boundary/no-progress/unchanged-window stop reason.
- The web app may virtualize history, so captures are range-based and may be
  partial. The user can capture overlapping ranges and merge them later.
- Real chat archives and raw captures are private data and stay under ignored
  or access-controlled paths.
- The reader is opened from static files without Snapchat, a network, a
  background process, or a credential.

## Capabilities and Constraints

- Normalize participants, message IDs, UTC timestamps, visible text, images,
  stickers/Bitmojis, alt text, dimensions, user-visible profile metadata,
  media placeholders, saved-state/retention indicators, source references,
  and per-record provenance into schema version 1 JSON.
- Validate unsafe paths, missing timezone information, duplicate IDs, invalid
  references, and malformed capture metadata with actionable messages.
- Import an explicitly supplied transcript or visible-capture JSON; merge
  overlapping ranges and report coverage, gaps, boundaries, duplicates, and
  conflicts.
- Build an offline static viewer with search, author filters, deep links,
  timestamp modes, provenance, print/PDF-friendly output, and a SHA-256
  integrity manifest.
- The adapter must not automate login or friend actions, inspect credentials or
  browser stores, call private APIs or network primitives, send messages,
  search arbitrary accounts, crawl, or evade notifications.
- The adapter reads only the currently open chat's rendered DOM. A scroll step
  moves the chat's visible message scroller by one viewport-sized increment and
  captures that resulting rendered range. A walk merges only the ranges it
  rendered during that foreground invocation; it never claims to load or verify
  unseen history by itself.
- Visible media is represented by safe local supplied assets or reference-only
  placeholders; the adapter never downloads remote media bytes. Already-rendered
  `img`/Bitmoji canvas pixels may be copied into a bounded data URL for local
  import, then materialized under the archive output.
- A complete archive claim is out of scope unless the overlap chain and
  boundaries justify `verified`; a verified rendered-range chain still cannot
  prove unseen or deleted messages.

## Brand Commitments

The name is CatchThat. The viewer borrows Snapchat Web's dark, high-contrast
conversation shell, ghost-yellow identity accent, compact chat rail, and
friendly readable rows while remaining unmistakably an archive. It must not
pretend to be a live client or offer a send action.

## Evidence on Hand

The kickoff brief supplies the desired readable unit:

    Person A: message 1
    Person B: message 2

Synthetic fixtures remain the committed source of truth. Private signed-in
Rick Bailer and Aiden Lautt smoke runs supplied local evidence for the current
selector candidates, author metadata, visible media references, avatar-pixel
path, and bounded scroll behavior. They do not establish a stable Snapchat DOM
contract or prove unseen history; the live selector uncertainty and the exact
next smoke step remain documented in `docs/live-smoke-test.md`.

## Product Principles

1. Preserve source truth and provenance.
2. Keep acquisition attended, visible, read-only, and narrowly scoped.
3. Make partial coverage impossible to mistake for a complete chat.
4. Keep personal archives portable without making them public.
5. Degrade gracefully when avatars, media, indicators, or source IDs are
   missing.

## Accessibility & Inclusion

The viewer uses semantic landmarks, keyboard-operable controls, visible focus,
readable contrast against the dark shell and yellow accent, text alternatives
for avatars and media placeholders, reduced-motion support, responsive layout,
and print styles. Color is never the only signal for coverage or message state.
