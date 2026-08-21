# Design direction: CatchThat Offline Reader

<!--
THESIS: Make a captured chat feel instantly readable while refusing the live-client illusion.
OWN-WORLD: White and paper-gray reading surfaces, ink-blue text, a ghost-yellow identity stripe, compact ledger labels, and soft outlined message rows.
STORY: The reader knows which chat is open, what range was observed, who spoke, and which evidence survives; they can search, inspect, and print without sending anything.
FIRST VIEWPORT: A yellow-topped CatchThat rail, a centered chat transcript, and a slim provenance panel establish local-only status, coverage, and the first readable rows immediately.
FORM: Operate/Read three-column archive reader; row selection is the signature interaction, with deep-linkable messages and a coverage ledger alongside the transcript.
-->

## Durable visual rules

- Mode: Operate/Read. Scanability, evidence, and native controls outrank
  decoration.
- Palette: light paper and white surfaces, ink-blue text, cool gray borders,
  ghost yellow `#fffc00` for identity and selected edges, and a separate
  high-contrast teal/ink status color for verified or local state. Yellow is
  never the only coverage signal.
- Typography: system sans for the reader and messages; a compact monospace
  stack for IDs, timestamps, and provenance. No remote font dependency.
- Layout: responsive three-column archive shell on desktop; the filter/source
  rails collapse above the transcript on narrow screens. The transcript is
  the largest region and stays visually calm.
- Message rows are readable text blocks, not speech bubbles. Each row keeps an
  author, timestamp, stable deep link, content kind, and optional evidence
  badges addressable.
- Provenance is a first-class side panel: source URL/reference, capture range,
  raw UTC timestamp, IDs, and visible-vs-placeholder distinctions remain one
  click away.
- Motion is limited to short state transitions and disabled for reduced-motion
  users. Print hides controls and expands the selected filtered view.

## Settled implementation tokens

- `--yellow: #fffc00` is the identity accent; `--ink: #183248` is the primary
  text color; `--paper: #f5f7f8` and `--surface: #ffffff` define the reader.
- `--line: #d7e0e5`, `--muted: #5f7180`, and `--teal: #0b6b73` support
  accessible evidence and status labels.
- Radius is modest (8–14px), shadows are soft and sparse, and layout spacing
  follows an 8px rhythm.
- The viewer emits `index.html`, `app.js`, `archive.json`, `manifest.json`,
  and any referenced local assets. It has no runtime network dependency.

