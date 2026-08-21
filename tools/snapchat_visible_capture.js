async () => {
  const clean = (value) => String(value ?? "").replace(/\s+/g, " ").trim();
  const isHttp = (value) => /^https?:\/\//i.test(String(value ?? ""));
  const isSnapchatHost = /(^|\.)snapchat\.com$/i.test(String(location.hostname || ""));
  const slug = (value) => clean(value).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  const displayTimezone = typeof Intl !== "undefined" && Intl.DateTimeFormat
    ? Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC"
    : "UTC";
  const isoWithTimezone = (value) => /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})$/i.test(String(value || ""));
  const fileName = (value) => {
    try {
      const path = new URL(value, location.href).pathname;
      return path.split("/").filter(Boolean).pop() || "media";
    } catch {
      return "media";
    }
  };
  const mediaKind = (value) => {
    const extension = String(value || "").split(/[?#]/, 1)[0].split(".").pop().toLowerCase();
    if (["png", "jpg", "jpeg", "gif", "webp", "svg", "heic"].includes(extension)) return "image";
    if (["mp4", "webm", "mov", "m4v"].includes(extension)) return "video";
    if (["mp3", "wav", "ogg", "m4a"].includes(extension)) return "audio";
    return "unknown";
  };
  const hashText = (value) => {
    let hash = 2166136261;
    for (const character of String(value || "")) {
      hash ^= character.charCodeAt(0);
      hash = Math.imul(hash, 16777619);
    }
    return (hash >>> 0).toString(16).padStart(8, "0");
  };
  const isVisible = (element) => {
    if (!element) return false;
    const style = getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return style.display !== "none" && style.visibility !== "hidden" && Number(style.opacity || 1) > 0 && rect.width > 0 && rect.height > 0;
  };
  const classes = (element) => element && typeof element.className === "string" ? element.className : "";
  const cleanPageUrl = () => {
    const url = new URL(location.href);
    url.search = "";
    url.hash = "";
    return url.toString();
  };
  const sourceUrl = cleanPageUrl();
  if (!isSnapchatHost) throw new Error("Open the intended Snapchat Web chat before capturing.");

  const main = document.querySelector("main") || document.body;
  const timestampSelector = "time[datetime], [data-timestamp], [data-time]";
  const selectorCandidates = [
    "[data-message-id]",
    "[data-testid*='message' i]",
    "[role='article']",
    "main [role='listitem']",
    "main [class*='message' i]",
    "main li",
  ];
  const rowFor = (candidate) => candidate.closest("[data-message-id], [role='article'], [role='listitem'], li") || candidate;
  const validRow = (row) => {
    if (!isVisible(row) || row.closest("nav, aside")) return false;
    const text = clean(row.innerText || row.textContent);
    const media = row.querySelector("img[src], video[src], audio[src], source[src]");
    const timestamp = row.querySelector(timestampSelector);
    return Boolean((text || media) && timestamp);
  };
  let usedSelector = null;
  let candidateNodes = [];
  const timestampAnchoredRows = Array.from(new Set(
    Array.from(main.querySelectorAll(timestampSelector))
      .filter((element) => isVisible(element))
      .map((element) => rowFor(element))
      .filter(Boolean),
  )).filter(validRow);
  if (timestampAnchoredRows.length) {
    usedSelector = "visible timestamp-anchored rows";
    candidateNodes = timestampAnchoredRows;
  } else {
    for (const selector of selectorCandidates) {
      const found = Array.from(main.querySelectorAll(selector)).filter((element) => isVisible(element));
      if (found.length) {
        usedSelector = selector;
        candidateNodes = found;
        break;
      }
    }
  }
  if (!candidateNodes.length) throw new Error("No visible message rows were found in the currently open Snapchat Web chat.");

  const rows = Array.from(new Set(candidateNodes.map(rowFor))).filter(validRow);
  if (!rows.length) throw new Error("Visible candidates were found, but none exposed both message evidence and a timestamp.");

  let messageScroller = rows[0]?.parentElement || null;
  while (messageScroller && messageScroller !== document.body) {
    const style = getComputedStyle(messageScroller);
    if (messageScroller.scrollHeight > messageScroller.clientHeight + 80 && /(auto|scroll)/i.test(style.overflowY)) break;
    messageScroller = messageScroller.parentElement;
  }
  if (!messageScroller || messageScroller === document.body) messageScroller = document.scrollingElement || document.documentElement;
  const scrollTop = Number(messageScroller?.scrollTop || 0);
  const scrollHeight = Number(messageScroller?.scrollHeight || 0);
  const viewportHeight = Number(messageScroller?.clientHeight || 0);
  const scrollPosition = {
    scroll_top: scrollTop,
    scroll_height: scrollHeight,
    viewport_height: viewportHeight,
    at_start: scrollTop <= 4,
    at_end: scrollTop + viewportHeight >= scrollHeight - 4,
  };

  const participants = new Map();
  const messages = [];
  let skippedWithoutTimestamp = 0;
  const selectorNotes = [
    `Selected visible row candidate: ${usedSelector}.`,
    "Timestamp-anchored rows are preferred so visible conversation messages are not confused with the Snapchat sidebar list.",
    "Rows were read from the current visible DOM only; no navigation or expansion was performed.",
    "Rows without an ISO-8601 timestamp with timezone were skipped rather than assigned a date.",
    "Media URLs are references from visible elements; media bytes were not captured or downloaded.",
    "Selector certainty is provisional until one signed-in, user-opened chat is inspected.",
  ];

  for (let index = 0; index < rows.length; index += 1) {
    const row = rows[index];
    const timestampElement = row.querySelector(timestampSelector);
    const timestamp = timestampElement?.getAttribute("datetime") || timestampElement?.getAttribute("data-timestamp") || timestampElement?.getAttribute("data-time");
    if (!isoWithTimezone(timestamp)) {
      skippedWithoutTimestamp += 1;
      continue;
    }

    const authorElement = row.querySelector("[data-author-id], [data-sender-id], [data-user-id], [data-testid*='author' i], [data-testid*='sender' i], [class*='author' i], [class*='sender' i], [class*='username' i]");
    const headerElement = row.querySelector("header");
    const timestampLabel = clean(timestampElement?.innerText || timestamp);
    const headerAuthor = clean(headerElement?.innerText).replace(timestampLabel, "").trim();
    const avatarElement = Array.from(row.querySelectorAll("img[alt], img[src]")).find((element) => !/avatar|emoji|sticker/i.test(`${element.alt || ""} ${classes(element)}`));
    const authorName = clean(authorElement?.innerText || authorElement?.getAttribute("aria-label") || avatarElement?.alt || headerAuthor) || "Unknown participant";
    const authorId = authorElement?.getAttribute("data-author-id") || authorElement?.getAttribute("data-sender-id") || authorElement?.getAttribute("data-user-id") || avatarElement?.getAttribute("data-user-id") || `author-${slug(authorName) || participants.size + 1}`;
    const participant = participants.get(authorId) || { id: authorId, display_name: authorName, username: authorName };
    participant.display_name = authorName;
    participant.username = authorName;
    const avatarRef = avatarElement?.getAttribute("src");
    if (isHttp(avatarRef)) participant.avatar_ref = avatarRef;
    participants.set(authorId, participant);

    const contentElement = row.querySelector("[data-message-content], [data-testid*='content' i], [class*='messageText' i], [class*='content' i], [dir='auto'], p");
    let content = clean(contentElement?.innerText || contentElement?.textContent);
    if (!content) {
      content = clean(row.innerText || row.textContent);
      for (const excluded of [authorName, timestampElement?.innerText, timestamp]) {
        if (excluded) content = content.replace(clean(excluded), "");
      }
      content = clean(content);
    }

    const sourceId = row.getAttribute("data-message-id") || row.getAttribute("data-item-id") || row.id?.match(/(?:message|chat)[-_]([A-Za-z0-9_-]+)/i)?.[1] || null;
    const messageId = sourceId || `local-${hashText(`${timestamp}|${authorId}|${content}`)}`;
    const media = [];
    const mediaSeen = new Set();
    for (const element of row.querySelectorAll("img[src], video[src], audio[src], source[src]")) {
      if (/avatar|emoji|sticker/i.test(`${element.alt || ""} ${classes(element)}`) || element.closest("[aria-hidden='true']")) continue;
      const reference = element.getAttribute("src");
      const label = clean(element.getAttribute("alt") || element.getAttribute("aria-label") || fileName(reference) || element.tagName.toLowerCase());
      const key = `${element.tagName}:${label}:${reference || ""}`;
      if (mediaSeen.has(key)) continue;
      mediaSeen.add(key);
      const item = {
        kind: mediaKind(reference || element.tagName.toLowerCase()),
        label: label || "Media",
        placeholder: "Media visible in source; bytes were not captured.",
      };
      if (isHttp(reference)) item.source_url = reference;
      media.push(item);
    }

    const stateEvidence = Array.from(row.querySelectorAll("[aria-label], [title], [data-state], [data-retention]")
      .map((element) => clean(element.getAttribute("aria-label") || element.getAttribute("title") || element.getAttribute("data-state") || element.getAttribute("data-retention")))
      .filter(Boolean));
    const savedEvidence = stateEvidence.find((value) => /save|keep in chat/i.test(value));
    const retentionEvidence = stateEvidence.find((value) => /view once|one time|disappear|delete|expire|keep in chat/i.test(value));
    const savedState = savedEvidence ? { state: /unsave|not saved/i.test(savedEvidence) ? "unsaved" : "saved", evidence: savedEvidence, visible: true } : null;
    const retention = retentionEvidence ? { state: /view once|one time/i.test(retentionEvidence) ? "view_once" : /disappear|delete|expire/i.test(retentionEvidence) ? "expires" : "kept_in_chat", evidence: retentionEvidence, visible: true } : null;

    const sourceRefs = [];
    for (const link of row.querySelectorAll("a[href]")) {
      const href = link.href || link.getAttribute("href");
      if (!isHttp(href)) continue;
      sourceRefs.push({ kind: "visible_link", label: clean(link.innerText || link.getAttribute("aria-label")) || "Visible source link", url: href });
    }
    const message = {
      id: messageId,
      author_id: authorId,
      timestamp,
      content,
      content_kind: content && media.length ? "mixed" : media.length ? "media_placeholder" : content ? "visible_text" : "empty",
      media,
      source_refs: sourceRefs,
      grouped: !authorElement,
      provenance: {
        source_id: sourceId,
        source_url: sourceUrl,
        capture_id: `capture-${Date.now()}`,
        id_generated: !sourceId,
        selector: usedSelector,
        visible_dom: true,
      },
    };
    if (savedState) message.saved_state = savedState;
    if (retention) message.retention = retention;
    messages.push(message);
  }
  if (!messages.length) throw new Error("No timestamped visible message rows could be captured from the open chat.");

  const ordered = [...messages].sort((a, b) => String(a.timestamp).localeCompare(String(b.timestamp)) || String(a.id).localeCompare(String(b.id)));
  const oldest = ordered[0];
  const newest = ordered[ordered.length - 1];
  const headingElement = Array.from(main.querySelectorAll("h1, h2, h3, [role='heading'], [aria-haspopup='listbox']"))
    .filter((element) => isVisible(element) && !element.closest("nav, aside") && clean(element.innerText || element.getAttribute("aria-label")))
    .sort((left, right) => left.getBoundingClientRect().top - right.getBoundingClientRect().top || clean(left.innerText).length - clean(right.innerText).length)[0];
  const heading = clean(headingElement?.innerText || document.title.replace(/^•\s*/, "")) || "Snapchat Web chat";
  const threadMatch = location.pathname.match(/(?:chat|conversation|thread|messages)[^/]*\/([^/]+)/i);
  const threadId = threadMatch?.[1] || null;
  const threadIdentity = { id: threadId, title: heading, path: location.pathname };
  const captureId = `capture-${Date.now()}`;
  const captureRange = {
    version: 1,
    capture_id: captureId,
    rendered_count: messages.length,
    skipped_without_timestamp: skippedWithoutTimestamp,
    oldest_message_id: oldest.id,
    oldest_timestamp: oldest.timestamp,
    newest_message_id: newest.id,
    newest_timestamp: newest.timestamp,
    ...scrollPosition,
    selector: usedSelector,
    selector_notes: selectorNotes,
  };
  return {
    metadata: {
      kind: "snapchat_chat",
      title: heading,
      thread_id: threadId,
      thread_identity: threadIdentity,
      captured_at: new Date().toISOString(),
      display_timezone: displayTimezone,
      capture_range: captureRange,
      selector_notes: selectorNotes,
      source: {
        type: "snapchat_visible_dom",
        label: "Snapchat visible chat capture",
        url: sourceUrl,
        capture_method: "foreground_visible_dom",
        read_only: true,
        thread_identity: threadIdentity,
        selector_notes: selectorNotes,
        notes: [
          "Captured from the user-opened Snapchat Web chat currently rendered in the foreground browser.",
          "The user controlled the chat position and expansion; this adapter did not navigate, scroll, or expand.",
          `Capture range: ${messages.length} rendered row(s), ${scrollPosition.at_start ? "at the oldest boundary" : "not at the oldest boundary"}, ${scrollPosition.at_end ? "at the newest boundary" : "not at the newest boundary"}.`,
          "Visible text, media placeholders, saved-state/retention indicators, and visible source references are preserved separately.",
          "This is a range capture, not a claim that the entire conversation is present.",
        ],
      },
    },
    participants: Array.from(participants.values()),
    messages,
  };
}
