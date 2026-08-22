async function capture(options = {}) {
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
  const mediaKind = (value, descriptors = "") => {
    const descriptor = `${value || ""} ${descriptors}`.toLowerCase();
    if (/bitmoji/.test(descriptor) || /sticker/.test(descriptor)) return "sticker";
    if (/snap(?:chat)?\b/.test(descriptor)) return "snap";
    const extension = String(value || "").split(/[?#]/, 1)[0].split(".").pop().toLowerCase();
    if (["png", "jpg", "jpeg", "gif", "webp", "svg", "heic"].includes(extension)) return "image";
    if (["mp4", "webm", "mov", "m4v"].includes(extension)) return "video";
    if (["mp3", "wav", "ogg", "m4a"].includes(extension)) return "audio";
    if (["tgs"].includes(extension)) return "sticker";
    return "unknown";
  };
  const mediaDescriptor = (element) => clean([
    element?.getAttribute?.("alt"),
    element?.getAttribute?.("aria-label"),
    element?.getAttribute?.("data-kind"),
    element?.getAttribute?.("data-media-type"),
    element?.getAttribute?.("data-testid"),
    classes(element),
  ].filter(Boolean).join(" "));
  const mediaReference = (element) => {
    if (!element) return null;
    const tag = element.tagName?.toLowerCase();
    const candidates = [
      element.currentSrc,
      element.getAttribute("src"),
      element.getAttribute("data-src"),
      element.getAttribute("data-original"),
      tag === "video" ? element.getAttribute("poster") : null,
      tag === "video" ? element.getAttribute("data-poster") : null,
      element.getAttribute("srcset")?.split(",")[0]?.trim().split(/\s+/)[0],
    ].filter(Boolean);
    return candidates.find((candidate) => isHttp(candidate)) || candidates[0] || null;
  };
  const captureVisibleAvatar = (element) => {
    if (!element || element.tagName?.toLowerCase() !== "img" || !isVisible(element)) return null;
    const naturalWidth = Number(element.naturalWidth || dimension(element, "width"));
    const naturalHeight = Number(element.naturalHeight || dimension(element, "height"));
    if (!element.complete || !naturalWidth || !naturalHeight) return null;
    const scale = Math.min(1, 512 / Math.max(naturalWidth, naturalHeight));
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round(naturalWidth * scale));
    canvas.height = Math.max(1, Math.round(naturalHeight * scale));
    try {
      const context = canvas.getContext("2d");
      if (!context) return null;
      context.drawImage(element, 0, 0, canvas.width, canvas.height);
      const dataUrl = canvas.toDataURL("image/png");
      if (!/^data:image\/png;base64,/i.test(dataUrl) || dataUrl.length > 2_000_000) return null;
      return { data_url: dataUrl, method: "visible_pixels_png" };
    } catch {
      // A cross-origin image without a readable CORS response taints the canvas.
      // Keep the visible URL as provenance instead of attempting a network read.
      return null;
    }
  };
  const dimension = (element, attribute) => {
    const value = Number(element?.getAttribute?.(attribute) || element?.[attribute] || 0);
    return Number.isFinite(value) && value > 0 ? Math.round(value) : null;
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
  const requestedScroll = options && (options.scroll === "older" || options.scroll === "newer") ? options.scroll : null;
  const walkDirection = options && (options.walk === "older" || options.walk === "newer") ? options.walk : null;
  const requestedMaxSteps = Number(options?.max_steps);
  const maxSteps = walkDirection
    ? Math.min(Math.max(Number.isFinite(requestedMaxSteps) ? Math.floor(requestedMaxSteps) : 40, 1), 80)
    : requestedScroll ? 1 : 0;

  if (walkDirection) {
    const walkOptions = { ...options, walk: null, max_steps: undefined };
    const captures = [await capture({ ...walkOptions, scroll: null })];
    let stopReason = "max_steps";
    for (let step = 0; step < maxSteps; step += 1) {
      const currentRange = captures[captures.length - 1]?.metadata?.capture_range || {};
      if (walkDirection === "older" ? currentRange.at_start : currentRange.at_end) {
        stopReason = walkDirection === "older" ? "oldest_boundary" : "newest_boundary";
        break;
      }
      const nextCapture = await capture({ ...walkOptions, scroll: walkDirection });
      captures.push(nextCapture);
      const nextRange = nextCapture.metadata?.capture_range || {};
      if (walkDirection === "older" ? nextRange.at_start : nextRange.at_end) {
        stopReason = walkDirection === "older" ? "oldest_boundary" : "newest_boundary";
        break;
      }
      if (!nextRange.scroll_action?.moved) {
        stopReason = "no_scroll_progress";
        break;
      }
    }

    const messageById = new Map();
    const participantById = new Map();
    const mergeParticipant = (existing, incoming) => {
      if (!existing) return { ...incoming, visible_profile: incoming.visible_profile ? { ...incoming.visible_profile } : undefined };
      for (const field of ["display_name", "username", "avatar_alt", "avatar_ref", "avatar_path", "avatar_data_url", "avatar_capture_method", "avatar_capture_note"]) {
        if (!existing[field] && incoming[field]) existing[field] = incoming[field];
      }
      if (incoming.visible_profile) existing.visible_profile = { ...(existing.visible_profile || {}), ...incoming.visible_profile };
      return existing;
    };
    const mergeMessage = (existing, incoming, rangeIndex) => {
      if (!existing) {
        return {
          ...incoming,
          media: Array.isArray(incoming.media) ? [...incoming.media] : [],
          source_refs: Array.isArray(incoming.source_refs) ? [...incoming.source_refs] : [],
          provenance: { ...(incoming.provenance || {}), capture_walk_index: rangeIndex },
        };
      }
      if (!existing.content && incoming.content) existing.content = incoming.content;
      if (existing.content_kind === "empty" && incoming.content_kind) existing.content_kind = incoming.content_kind;
      const media = [...(existing.media || []), ...(incoming.media || [])];
      existing.media = [...new Map(media.map((item) => [JSON.stringify([item.kind, item.subtype, item.label, item.source_url, item.path]), item])).values()];
      const refs = [...(existing.source_refs || []), ...(incoming.source_refs || [])];
      existing.source_refs = [...new Map(refs.map((item) => [JSON.stringify([item.kind, item.label, item.url]), item])).values()];
      if (incoming.provenance?.notes) existing.provenance = { ...(existing.provenance || {}), notes: [...new Set([...(existing.provenance?.notes || []), ...incoming.provenance.notes])] };
      return existing;
    };
    const rangeSummaries = [];
    const selectorNotes = new Set();
    let skippedWithoutTimestamp = 0;
    captures.forEach((result, rangeIndex) => {
      const captureRange = result.metadata?.capture_range || {};
      rangeSummaries.push({
        range_index: rangeIndex,
        captured_at: result.metadata?.captured_at || null,
        rendered_count: Number(captureRange.rendered_count || 0),
        skipped_without_timestamp: Number(captureRange.skipped_without_timestamp || 0),
        oldest_message_id: captureRange.oldest_message_id || null,
        oldest_timestamp: captureRange.oldest_timestamp || null,
        newest_message_id: captureRange.newest_message_id || null,
        newest_timestamp: captureRange.newest_timestamp || null,
        scroll_top: Number(captureRange.scroll_top || 0),
        scroll_height: Number(captureRange.scroll_height || 0),
        viewport_height: Number(captureRange.viewport_height || 0),
        at_start: Boolean(captureRange.at_start),
        at_end: Boolean(captureRange.at_end),
        scroll_action: captureRange.scroll_action || null,
        selector: captureRange.selector || null,
        message_ids: (result.messages || []).map((message) => message.id).filter(Boolean),
      });
      skippedWithoutTimestamp = Math.max(skippedWithoutTimestamp, Number(captureRange.skipped_without_timestamp || 0));
      (result.metadata?.selector_notes || []).forEach((note) => selectorNotes.add(note));
      (result.participants || []).forEach((participant) => {
        if (!participant?.id) return;
        participantById.set(participant.id, mergeParticipant(participantById.get(participant.id), participant));
      });
      (result.messages || []).forEach((message) => {
        if (message?.id) messageById.set(message.id, mergeMessage(messageById.get(message.id), message, rangeIndex));
      });
    });
    const messages = [...messageById.values()].sort((a, b) => String(a.timestamp).localeCompare(String(b.timestamp)) || String(a.id).localeCompare(String(b.id)));
    if (!messages.length) throw new Error("The foreground walk produced no timestamped visible message rows.");
    const oldest = messages[0];
    const newest = messages[messages.length - 1];
    const last = captures[captures.length - 1];
    const selectorNoteList = [...selectorNotes];
    const walkNote = `The user explicitly triggered a foreground ${walkDirection} walk; ${captures.length - 1} bounded step(s) were executed and the walk stopped at ${stopReason}.`;
    const rangeKeys = rangeSummaries.map((range) => `${range.oldest_message_id || ""}|${range.newest_message_id || ""}|${range.rendered_count}`);
    const uniqueRangeCount = new Set(rangeKeys).size;
    const repeatedRangeCount = rangeSummaries.length - uniqueRangeCount;
    const repeatedRangeNote = repeatedRangeCount
      ? `The visible DOM produced ${repeatedRangeCount} repeated range boundary result(s) across ${rangeSummaries.length} capture(s); additional history was not verified from a changed rendered message window.`
      : null;
    const skippedCountNote = "For a merged walk, skipped_without_timestamp is the maximum observed in one rendered range; overlapping ranges are not added together.";
    selectorNoteList.push(walkNote);
    if (repeatedRangeNote) selectorNoteList.push(repeatedRangeNote);
    const sourceNotes = [
      ...(last.metadata?.source?.notes || []),
      walkNote,
      ...(repeatedRangeNote ? [repeatedRangeNote] : []),
      skippedCountNote,
      "This merged result contains only ranges rendered during this foreground walk; it is not a claim that unseen or deleted history is present.",
    ];
    const captureRange = {
      ...(last.metadata?.capture_range || {}),
      capture_id: `capture-${Date.now()}`,
      rendered_count: messages.length,
      skipped_without_timestamp: skippedWithoutTimestamp,
      oldest_message_id: oldest.id,
      oldest_timestamp: oldest.timestamp,
      newest_message_id: newest.id,
      newest_timestamp: newest.timestamp,
      range_count: rangeSummaries.length,
      ranges: rangeSummaries,
      scroll_action: null,
      scroll_walk: {
        requested: walkDirection,
        max_steps: maxSteps,
        steps: captures.length - 1,
        ranges_captured: rangeSummaries.length,
        unique_ranges: uniqueRangeCount,
        repeated_ranges: repeatedRangeCount,
        stopped_reason: stopReason,
        reached_boundary: stopReason === (walkDirection === "older" ? "oldest_boundary" : "newest_boundary"),
      },
    };
    return {
      metadata: {
        ...last.metadata,
        captured_at: new Date().toISOString(),
        capture_range: captureRange,
        selector_notes: selectorNoteList,
        source: {
          ...last.metadata.source,
          selector_notes: selectorNoteList,
          notes: [...new Set(sourceNotes)],
        },
      },
      participants: [...participantById.values()],
      messages,
    };
  }

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
  const collectRows = () => {
    let selector = null;
    let candidateNodes = [];
    const timestampAnchoredRows = Array.from(new Set(
      Array.from(main.querySelectorAll(timestampSelector))
        .filter((element) => isVisible(element))
        .map((element) => rowFor(element))
        .filter(Boolean),
    )).filter(validRow);
    if (timestampAnchoredRows.length) {
      selector = "visible timestamp-anchored rows";
      candidateNodes = timestampAnchoredRows;
    } else {
      for (const candidateSelector of selectorCandidates) {
        const found = Array.from(main.querySelectorAll(candidateSelector)).filter((element) => isVisible(element));
        if (found.length) {
          selector = candidateSelector;
          candidateNodes = found;
          break;
        }
      }
    }
    return {
      usedSelector: selector,
      rows: Array.from(new Set(candidateNodes.map(rowFor))).filter(validRow),
    };
  };
  let { usedSelector, rows } = collectRows();
  if (!rows.length) throw new Error("No visible message rows were found in the currently open Snapchat Web chat.");

  const scrollableAncestor = (row) => {
    let element = row?.parentElement || null;
    while (element && element !== document.body) {
      const style = getComputedStyle(element);
      if (element.scrollHeight > element.clientHeight + 80 && /(auto|scroll)/i.test(style.overflowY)) return element;
      element = element.parentElement;
    }
    return document.scrollingElement || document.documentElement;
  };
  const scopeToConversationScroller = (candidateRows) => {
    const groups = new Map();
    candidateRows.forEach((row) => {
      const scroller = scrollableAncestor(row);
      const group = groups.get(scroller) || { scroller, rows: [] };
      group.rows.push(row);
      groups.set(scroller, group);
    });
    const ranked = Array.from(groups.values()).sort((left, right) => {
      const leftRect = left.scroller?.getBoundingClientRect?.() || { x: 0 };
      const rightRect = right.scroller?.getBoundingClientRect?.() || { x: 0 };
      return Number(right.scroller?.clientWidth || 0) - Number(left.scroller?.clientWidth || 0)
        || right.rows.length - left.rows.length
        || Number(rightRect.x || 0) - Number(leftRect.x || 0);
    });
    const selected = ranked[0];
    return {
      scroller: selected?.scroller || document.scrollingElement || document.documentElement,
      rows: selected?.rows || candidateRows,
      group_count: ranked.length,
    };
  };
  let scoped = scopeToConversationScroller(rows);
  let messageScroller = scoped.scroller;
  rows = scoped.rows;
  let scrollTop = Number(messageScroller?.scrollTop || 0);
  let scrollHeight = Number(messageScroller?.scrollHeight || 0);
  let viewportHeight = Number(messageScroller?.clientHeight || 0);
  const scrollAction = {
    requested: requestedScroll,
    moved: false,
    method: null,
    step_pixels: 0,
    from_scroll_top: scrollTop,
    to_scroll_top: scrollTop,
  };
  if (requestedScroll) {
    const stepPixels = Math.max(Math.round(Math.max(viewportHeight, 300) * 0.8), 240);
    const maxScrollTop = Math.max(0, scrollHeight - viewportHeight);
    const targetScrollTop = requestedScroll === "older"
      ? Math.max(0, scrollTop - stepPixels)
      : Math.min(maxScrollTop, scrollTop + stepPixels);
    scrollAction.step_pixels = stepPixels;
    if (messageScroller && targetScrollTop !== scrollTop) {
      const delta = targetScrollTop - scrollTop;
      if (typeof messageScroller.scrollBy === "function") {
        messageScroller.scrollBy({ top: delta, left: 0, behavior: "auto" });
        scrollAction.method = "scrollBy";
      } else if (typeof messageScroller.scrollTo === "function") {
        messageScroller.scrollTo({ top: targetScrollTop, left: 0, behavior: "auto" });
        scrollAction.method = "scrollTo";
      } else {
        throw new Error("The visible message scroller exposes no read-only-safe scroll method.");
      }
      await new Promise((resolve) => {
        setTimeout(resolve, 75);
      });
      scrollAction.moved = Number(messageScroller.scrollTop || 0) !== scrollTop;
      if (!scrollAction.moved && scrollAction.method === "scrollBy" && typeof messageScroller.scrollTo === "function") {
        messageScroller.scrollTo({ top: targetScrollTop, left: 0, behavior: "auto" });
        scrollAction.method = "scrollTo_fallback";
        await new Promise((resolve) => {
          setTimeout(resolve, 75);
        });
        scrollAction.moved = Number(messageScroller.scrollTop || 0) !== scrollTop;
      }
    }
    scrollAction.to_scroll_top = Number(messageScroller?.scrollTop || targetScrollTop);
    ({ usedSelector, rows } = collectRows());
    scoped = scopeToConversationScroller(rows);
    messageScroller = scoped.scroller;
    rows = scoped.rows;
    if (!rows.length) throw new Error("The requested scroll step completed, but no visible timestamped message rows remain.");
    scrollTop = Number(messageScroller?.scrollTop || 0);
    scrollHeight = Number(messageScroller?.scrollHeight || 0);
    viewportHeight = Number(messageScroller?.clientHeight || 0);
  }
  const scrollPosition = {
    scroll_top: scrollTop,
    scroll_height: scrollHeight,
    viewport_height: viewportHeight,
    at_start: scrollTop <= 4,
    at_end: scrollTop + viewportHeight >= scrollHeight - 4,
    scroll_action: scrollAction,
  };

  const participants = new Map();
  const messages = [];
  let skippedWithoutTimestamp = 0;
  const selectorNotes = [
    `Selected visible row candidate: ${usedSelector}.`,
    "Timestamp-anchored rows are preferred so visible conversation messages are not confused with the Snapchat sidebar list.",
    `Selected the widest visible timestamped scroll container from ${scoped.group_count} candidate container(s) so the conversation pane is separated from the sidebar when both expose timestamps.`,
    requestedScroll
      ? `Applied one bounded ${requestedScroll} scroll step because the caller explicitly requested it; no follow-up scroll was scheduled.`
      : "No scroll action was requested; rows were read from the current visible DOM without navigation or expansion.",
    "Rows without an ISO-8601 timestamp with timezone were skipped rather than assigned a date.",
     "Visible message images, stickers, Bitmojis, alt text, dimensions, user labels, and profile indicators are preserved as references or placeholders; message media bytes are not captured or downloaded.",
     "A displayed participant avatar may be copied from readable pixels already rendered in the DOM into a bounded local data URL; cross-origin or blob-only avatars remain reference-only and are never fetched.",
    "Decorative favicon and site-icon nodes inside visible link previews are excluded from message media cards.",
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
    const authorSourceId = authorElement?.getAttribute("data-user-id") || authorElement?.getAttribute("data-author-id") || authorElement?.getAttribute("data-sender-id") || null;
    const visualElements = Array.from(row.querySelectorAll("img[src], img[srcset], img[data-src], img[data-original], [data-avatar] img"));
    const avatarElement = visualElements.find((element) => {
      const avatarContext = element.closest("[data-avatar], [data-testid*=avatar i], [aria-label*=avatar i]");
      const descriptor = `${mediaDescriptor(element)} ${mediaDescriptor(avatarContext)}`.toLowerCase();
      return element.hasAttribute("data-avatar")
        || Boolean(avatarContext)
        || /avatar|profile(?:[- ]?photo)?|user(?:[- ]?photo)?/.test(descriptor)
        || (authorSourceId && (element.getAttribute("data-user-id") === authorSourceId || element.closest("[data-user-id]")?.getAttribute("data-user-id") === authorSourceId));
    }) || null;
    const authorName = clean(authorElement?.innerText || authorElement?.getAttribute("aria-label") || headerAuthor || avatarElement?.alt) || "Unknown participant";
    const authorId = authorSourceId || avatarElement?.getAttribute("data-user-id") || `author-${slug(authorName) || participants.size + 1}`;
    const handleElement = row.querySelector("[data-username], [data-user-name], [data-handle], [data-testid*='username' i], [data-testid*='handle' i], [class*='username' i], [class*='handle' i]");
    const statusElement = row.querySelector("[data-status], [data-user-status], [data-testid*='status' i], [class*='profileStatus' i]");
    const profileLabelElement = row.querySelector("[data-profile-label], [data-user-label], [data-testid*='profile-label' i]");
    const handle = clean(handleElement?.getAttribute("data-username") || handleElement?.getAttribute("data-handle") || handleElement?.innerText || handleElement?.getAttribute("aria-label"));
    const participant = participants.get(authorId) || { id: authorId, display_name: authorName, username: handle || authorName };
    participant.display_name = participant.display_name === "Unknown participant" ? authorName : participant.display_name || authorName;
    participant.username = handle || participant.username || authorName;
    const avatarRef = mediaReference(avatarElement);
    if (isHttp(avatarRef)) participant.avatar_ref = avatarRef;
    const avatarCapture = captureVisibleAvatar(avatarElement);
    if (avatarCapture) {
      participant.avatar_data_url = avatarCapture.data_url;
      participant.avatar_capture_method = avatarCapture.method;
      participant.avatar_capture_note = "Captured from the displayed avatar pixels in the foreground DOM; no remote fetch was used.";
    }
    const avatarAlt = clean(avatarElement?.getAttribute("alt") || avatarElement?.getAttribute("aria-label"));
    if (avatarAlt) participant.avatar_alt = avatarAlt;
    const visibleProfile = participant.visible_profile || {};
    visibleProfile.label = clean(profileLabelElement?.innerText || profileLabelElement?.getAttribute("aria-label") || authorName) || authorName;
    if (handle) visibleProfile.handle = handle;
    const status = clean(statusElement?.innerText || statusElement?.getAttribute("aria-label") || statusElement?.getAttribute("data-status"));
    if (status) visibleProfile.status = status;
    if (authorSourceId) visibleProfile.source_id = authorSourceId;
    const profileLink = Array.from(row.querySelectorAll("a[href]"))
      .find((link) => /profile|user|avatar|author|sender|username/i.test(mediaDescriptor(link)) && isHttp(link.href || link.getAttribute("href")));
    if (profileLink) visibleProfile.source_url = profileLink.href || profileLink.getAttribute("href");
    if (Object.keys(visibleProfile).length) participant.visible_profile = visibleProfile;
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
    for (const element of row.querySelectorAll("img[src], img[srcset], img[data-src], img[data-original], video[src], video[poster], video[data-src], audio[src], audio[data-src], source[src]")) {
      const mediaContainer = element.closest("video, audio");
      if (element === avatarElement || element.closest("[aria-hidden='true']") || !(isVisible(element) || (mediaContainer && isVisible(mediaContainer)))) continue;
      const descriptor = mediaDescriptor(element);
      if (/avatar|profile(?:[- ]?photo)?|user(?:[- ]?photo)?/.test(descriptor.toLowerCase())) continue;
      const reference = mediaReference(element);
      const tag = element.tagName.toLowerCase();
      const label = clean(element.getAttribute("alt") || element.getAttribute("aria-label") || element.getAttribute("data-label") || fileName(reference) || (/bitmoji/i.test(descriptor) ? "Bitmoji" : tag));
      const width = dimension(element, "width");
      const height = dimension(element, "height");
      if (/favicon|site[- ]?icon|link[- ]?icon/i.test(`${label} ${descriptor}`)) continue;
      const key = `${label}:${reference || ""}`;
      if (mediaSeen.has(key)) continue;
      mediaSeen.add(key);
      const detectedKind = tag === "video" ? "video" : tag === "audio" ? "audio" : mediaKind(reference, descriptor);
      const item = {
        kind: detectedKind === "unknown" && tag === "img" ? "image" : detectedKind,
        label: label || "Media",
        placeholder: /bitmoji/i.test(descriptor) ? "Bitmoji visible in source; bytes were not captured." : "Media visible in source; bytes were not captured.",
        source_element: tag,
      };
      if (/bitmoji/i.test(descriptor)) item.subtype = "bitmoji";
      if (isHttp(reference)) item.source_url = reference;
      if (element.getAttribute("alt")) item.alt = clean(element.getAttribute("alt"));
      if (width) item.width = width;
      if (height) item.height = height;
      media.push(item);
    }
    for (const element of row.querySelectorAll("[data-bitmoji], [data-sticker], [aria-label*='bitmoji' i], [aria-label*='sticker' i], [class*='bitmoji' i], [class*='sticker' i]")) {
      if (!isVisible(element) || element.closest("[aria-hidden='true']")) continue;
      if (element.querySelector("img[src], img[srcset], img[data-src], img[data-original], video[src], video[data-src], audio[src], audio[data-src]")) continue;
      const descriptor = mediaDescriptor(element);
      const reference = mediaReference(element);
      const label = clean(element.getAttribute("aria-label") || element.getAttribute("data-label") || (descriptor.match(/bitmoji|sticker/i)?.[0]) || "Sticker");
      const key = `${element.tagName}:${label}:${reference || ""}`;
      if (mediaSeen.has(key)) continue;
      mediaSeen.add(key);
      const item = {
        kind: "sticker",
        subtype: /bitmoji/i.test(descriptor) ? "bitmoji" : "sticker",
        label,
        placeholder: /bitmoji/i.test(descriptor) ? "Bitmoji visible in source; no source URL or bytes were captured." : "Sticker visible in source; no source URL or bytes were captured.",
        source_element: element.tagName.toLowerCase(),
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
          requestedScroll
            ? `The user explicitly triggered one foreground ${requestedScroll} scroll step; no follow-up scroll, navigation, or expansion was scheduled.`
            : "No scroll action was requested; the adapter did not navigate, scroll, or expand the open chat.",
          `Capture range: ${messages.length} rendered row(s), ${scrollPosition.at_start ? "at the oldest boundary" : "not at the oldest boundary"}, ${scrollPosition.at_end ? "at the newest boundary" : "not at the newest boundary"}; scroll moved: ${scrollAction.moved ? "yes" : "no"}.`,
           "Visible text, image/sticker/Bitmoji placeholders, user metadata, saved-state/retention indicators, and visible source references are preserved separately.",
           "Participant avatar bytes are captured only from already-rendered readable pixels when the page permits it; remote-only avatar references remain provenance-only.",
          "This is a range capture, not a claim that the entire conversation is present.",
        ],
      },
    },
    participants: Array.from(participants.values()),
    messages,
  };
}
