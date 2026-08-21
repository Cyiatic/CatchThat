# Design direction: CatchThat Offline Reader

<!--
THESIS: Make a captured chat feel like a familiar Snapchat Web conversation while refusing the live-client illusion.
OWN-WORLD: Near-black conversation surfaces, white type, ghost-yellow identity signals, cyan/coral message rails, compact source labels, and evidence-forward archive controls.
STORY: The reader knows which chat is open, what range was observed, who spoke, and which evidence survives; they can search, inspect, and print without sending anything.
FIRST VIEWPORT: A Snapchat-like dark chat rail, a bright readable transcript, and a provenance panel establish local-only status, partial coverage, and the first rows immediately.
FORM: Operate/Read three-column archive reader; row selection is the signature interaction, with deep-linkable messages and a coverage ledger alongside the transcript.
-->

## Durable visual rules

- Mode: Operate/Read. Scanability, evidence, and native controls outrank
  decoration; this is an archive shell, not an imitation composer.
- Palette: near-black chrome and feed surfaces, white text, cool gray borders,
  ghost yellow `#fffc00` for identity and selected edges, cyan and coral rails
  to separate speaker rows, and green/amber text for local and partial states.
  Yellow is never the only coverage signal.
- Typography: system sans for the reader and messages; a compact monospace
  stack for IDs, timestamps, and provenance. No remote font dependency.
- Layout: responsive three-column Snapchat-like shell on desktop; the archive
  rail and provenance panel collapse above/below the transcript on narrow
  screens. The transcript is the largest region and stays visually calm.
- Message rows are compact dark conversation blocks with a small avatar, a
  speaker label, timestamp, stable deep link, content kind, and optional
  evidence badges addressable. They resemble chat rows without creating a
  sendable message composer.
- Provenance is a first-class side panel: source URL/reference, capture range,
  raw UTC timestamp, IDs, and visible-vs-placeholder distinctions remain one
  click away.
- Capture affordance: each explicit `older`/`newer` action advances one bounded
  visible-DOM range and returns its scroll movement and boundary state. The
  reader presents that state as a coverage ledger, never as an automatic crawl.
- Motion is limited to short state transitions and disabled for reduced-motion
  users. Print switches to high-contrast paper output and expands the selected
  filtered view.

## Settled implementation tokens

- `--yellow: #fffc00` is the identity accent; `--night: #0f1011`,
  `--chrome: #151617`, and `--surface: #242628` define the dark reader.
- `--text: #f5f5f5`, `--muted: #b5b6ba`, `--cyan: #35c7ff`,
  `--coral: #ff477e`, and `--green: #7be495` support readable evidence and
  speaker/state labels.
- Radius is restrained (8–14px), shadows are soft and sparse, and layout
  spacing follows an 8px rhythm. Yellow is reserved for identity, focus, and
  selected archive state.
- The viewer emits `index.html`, `app.js`, `archive.json`, `manifest.json`,
  and any referenced local assets. It has no runtime network dependency.
