// CatchThat foreground controls.
// Run snapchat_visible_capture.js first, then evaluate this file in the same
// user-opened Snapchat Web chat. It appends only this visible helper panel;
// Snapchat controls, navigation, account state, and browser stores are never
// touched. The result remains in the page until the user saves it locally.
(() => {
  "use strict";

  const pageHost = typeof window !== "undefined" ? window : typeof globalThis !== "undefined" ? globalThis : null;
  // Some browser evaluate surfaces freeze the page global. When this file is
  // evaluated together with the adapter, use its lexical capture function
  // instead of trying to publish state on window.
  const api = pageHost?.CatchThatCapture || (typeof capture === "function" ? { captureVisibleChat: capture } : null);
  if (!api || typeof api.captureVisibleChat !== "function") {
    throw new Error("Run tools/snapchat_visible_capture.js before installing CatchThat controls.");
  }
  const existing = document.getElementById("catchthat-capture-controls");
  if (existing) return { installed: false, reason: "already_installed" };

  const panel = document.createElement("section");
  panel.id = "catchthat-capture-controls";
  panel.setAttribute("aria-label", "CatchThat foreground capture controls");
  panel.style.cssText = [
    "position:fixed", "right:16px", "bottom:16px", "z-index:2147483647", "width:min(420px, calc(100vw - 32px))",
    "padding:14px", "border:2px solid #fffc00", "border-radius:14px", "background:#171819", "color:#f5f5f5",
    "box-shadow:0 14px 40px rgba(0,0,0,.42)", "font:14px/1.4 system-ui,sans-serif",
  ].join(";");
  panel.innerHTML = `
    <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:12px">
      <div>
        <strong style="display:block;font-size:16px">CatchThat capture</strong>
        <span style="display:block;color:#b5b6ba;font-size:12px">Visible, read-only · current chat only</span>
      </div>
      <button type="button" data-catchthat-action="close" aria-label="Close CatchThat controls" style="border:1px solid #555;background:#242628;color:#f5f5f5;border-radius:50%;width:28px;height:28px">×</button>
    </div>
    <div style="display:flex;flex-wrap:wrap;gap:7px;margin-top:12px">
      <button type="button" data-catchthat-action="current" style="border:1px solid #fffc00;background:#fffc00;color:#101112;border-radius:8px;padding:8px 10px;font-weight:700">Capture current</button>
      <button type="button" data-catchthat-action="older" style="border:1px solid #555;background:#242628;color:#f5f5f5;border-radius:8px;padding:8px 10px">Walk older</button>
      <button type="button" data-catchthat-action="newer" style="border:1px solid #555;background:#242628;color:#f5f5f5;border-radius:8px;padding:8px 10px">Walk newer</button>
    </div>
    <p data-catchthat-status role="status" aria-live="polite" style="margin:10px 0 0;color:#b5b6ba;font-size:12px">Ready. Nothing has been captured yet.</p>
    <textarea data-catchthat-result readonly aria-label="Latest CatchThat capture JSON" spellcheck="false" style="display:block;width:100%;height:92px;box-sizing:border-box;margin-top:10px;padding:8px;border:1px solid #3d3f42;border-radius:8px;background:#0f1011;color:#f5f5f5;font:11px/1.35 ui-monospace,SFMono-Regular,Consolas,monospace;resize:vertical" placeholder="The latest JSON result appears here for local saving."></textarea>
  `;
  document.body.appendChild(panel);

  const status = panel.querySelector("[data-catchthat-status]");
  const resultField = panel.querySelector("[data-catchthat-result]");
  const actionButtons = Array.from(panel.querySelectorAll("button[data-catchthat-action]"));
  const setBusy = (busy) => actionButtons.forEach((button) => {
    if (button.dataset.catchthatAction !== "close") button.disabled = busy;
  });
  const run = async (options, label) => {
    setBusy(true);
    status.textContent = `${label}… reading only the currently rendered chat window.`;
    try {
      const result = await api.captureVisibleChat(options);
      api.lastResult = result;
      resultField.value = JSON.stringify(result, null, 2);
      const range = result.metadata?.capture_range || {};
      const walk = range.scroll_walk;
      const stop = walk ? ` stopped: ${walk.stopped_reason}` : range.scroll_action?.requested ? ` moved: ${range.scroll_action.moved ? "yes" : "no"}` : "";
      status.textContent = `Ready to save locally · ${result.messages?.length || 0} rendered message(s)${stop}.`;
    } catch (error) {
      status.textContent = `Capture failed: ${error?.message || String(error)}`;
    } finally {
      setBusy(false);
    }
  };
  panel.querySelector('[data-catchthat-action="current"]').addEventListener("click", () => run({}, "Capturing current range"));
  panel.querySelector('[data-catchthat-action="older"]').addEventListener("click", () => run({ walk: "older", max_steps: 40 }, "Walking older"));
  panel.querySelector('[data-catchthat-action="newer"]').addEventListener("click", () => run({ walk: "newer", max_steps: 40 }, "Walking newer"));
  panel.querySelector('[data-catchthat-action="close"]').addEventListener("click", () => panel.remove());
  return { installed: true, note: "Capture controls are visible and user-triggered; save api.lastResult or the read-only result field locally." };
})();
