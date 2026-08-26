# Design direction: CatchThat Offline Reader

<!--
THESIS: Make a captured chat feel native to Snapchat Web without pretending it is live.
OWN-WORLD: Near-black chrome, a dense chat list, compact bubble rows, ghost-yellow identity signals, and a quiet evidence drawer.
STORY: The reader knows which chat is open, what range was observed, who spoke, and which evidence survives; they can search, inspect, and print without sending anything.
FIRST VIEWPORT: The selected chat, newest captured messages, read-only capture bar, and partial-range state appear in one familiar two-pane shell.
FORM: Operate/Read Snapchat-style two-pane reader with an on-demand provenance drawer; row selection remains the signature interaction and deep links remain stable.
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
- Layout: responsive Snapchat Web-style two-pane shell on desktop; the chat
  list carries product identity, local/read-only status, search, and author
  filters, while the transcript owns the largest region. Provenance is a
  right-side inspector drawer opened from the transcript header rather than a
  permanent report column.
- Product identity: CatchThat’s ghost-yellow ghost-catcher mark and product name
  sit above the archive chat list; the same mark is the offline favicon. The
  sidebar footer keeps the local/read-only boundary visible after the
  navigation rail is removed.
- Message visibility: the closed author control is one compact “All authors”
  disclosure, not a list of conversations. Its open menu contains independent
  multi-select message-visibility toggles, using the captured participant
  avatar/Bitmoji when a local asset exists and honest initials/reference
  metadata otherwise. Readable avatar pixels captured from the visible DOM are
  materialized as local assets during import; reference-only states remain
  explicit in provenance.
- Message rows are compact dark bubble clusters with a Snapchat-style header
  above each bubble: colored author label at left and a short local/UTC time at
  right. Full timestamps remain in the evidence drawer. Cyan/coral speaker
  rails, stable deep links, content kind,
  image/sticker/Bitmoji preview or reference card, and optional evidence
  badges. The bottom composer is a visual read-only status bar, never an input.
- Provenance is a first-class drawer: source URL/reference, capture range, raw
  UTC timestamp, IDs, and visible-vs-placeholder distinctions remain one
  click away without interrupting transcript reading.
- Capture affordance: the live helper presents visible `Capture current`, `Walk
  older`, and `Walk newer` actions for the currently open chat. Each action
  advances one bounded visible-DOM range or composes those steps in the
  foreground until a boundary, no-progress result, unchanged rendered window,
  or cap. The reader presents direction, movement, ranges, and stop state as a
  coverage ledger, never as a complete-chat claim.
- Motion is limited to short state transitions and disabled for reduced-motion
  users. Print switches to high-contrast paper output and expands the selected
  filtered view.
- Iconography: local inline SVG system icons are used for coverage status,
  timestamp mode, printing, filters, and evidence. Icon-only actions retain
  visible focus, an accessible action label, and a title tooltip; icon size is
  kept around the 18–20px system-icon scale.

## Settled implementation tokens

- `--yellow: #fffc00` is the identity accent; `--night: #0f1011`,
  `--chrome: #151617`, and `--surface: #242628` define the dark reader.
- `--text: #f5f5f5`, `--muted: #b5b6ba`, `--cyan: #35c7ff`,
  `--coral: #ff477e`, and `--green: #7be495` support readable evidence and
  speaker/state labels.
- Radius is restrained (8–20px for Snapchat-like pills), shadows are soft and
  sparse, and layout spacing follows an 8px rhythm. Yellow is reserved for
  identity, focus, selected archive state, and the read-only boundary.
- The viewer emits `index.html`, `app.js`, `archive.json`, `manifest.json`,
  and any referenced local assets. It has no runtime network dependency.
