// TitleRig live preview: a canvas widget on TitleRig Render / Render Animation that re-renders whenever anything
// upstream changes (Text, Look, Shadow, Layout, Style Preset, Animate, Magnet). The server renders with the real rig
// (POST /titlerig/preview), so what you see is what the workflow will make. Themed from ComfyUI's own palette
// variables, so it follows the dark (default) and light colour palettes.
import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const TARGETS = ["TitleRigRender", "TitleRigRenderAnimation"];
const PASSES = [["beauty", "Beauty"], ["depth", "Depth"], ["edges", "Edges"], ["alpha", "Alpha"], ["letter_ids", "IDs"]];
const POLL_MS = 400;

const CSS = `
.tr-preview { --tr-accent: #8f91ff; display: flex; flex-direction: column; gap: 6px; padding: 6px;
  box-sizing: border-box; width: 100%; height: 100%; color: var(--fg-color, #ddd);
  background: var(--comfy-menu-bg, #202020); border: 1px solid var(--border-color, #444); border-radius: 6px;
  font: 11px/1.3 system-ui, sans-serif; }
.tr-preview .tr-bar { display: flex; flex-wrap: wrap; gap: 4px; align-items: center; }
.tr-preview button { font: inherit; color: inherit; background: var(--comfy-input-bg, #2a2a2a);
  border: 1px solid var(--border-color, #444); border-radius: 999px; padding: 2px 8px; cursor: pointer; }
.tr-preview button[aria-pressed="true"] { background: var(--tr-accent); border-color: var(--tr-accent); color: #14141a; }
.tr-preview button:focus-visible { outline: 2px solid var(--tr-accent); outline-offset: 1px; }
.tr-preview .tr-stage { flex: 1; min-height: 160px; display: flex; align-items: center; justify-content: center;
  overflow: hidden; border-radius: 4px; background: var(--comfy-input-bg, #2a2a2a); position: relative; }
.tr-preview img { max-width: 100%; max-height: 100%; object-fit: contain; display: block; }
.tr-preview .tr-busy { position: absolute; top: 4px; right: 6px; width: 6px; height: 6px; border-radius: 50%;
  background: var(--tr-accent); opacity: 0; transition: opacity .15s; }
.tr-preview .tr-busy.on { opacity: 1; }
.tr-preview .tr-msg { color: var(--descrip-text, #999); min-height: 1.3em; }
.tr-preview .tr-msg.err { color: var(--error-text, #ff6b6b); }
.tr-preview .tr-time { display: flex; gap: 6px; align-items: center; }
.tr-preview .tr-time input { flex: 1; accent-color: var(--tr-accent); }
.tr-preview .tr-time span { font-variant-numeric: tabular-nums; color: var(--descrip-text, #999); min-width: 64px;
  text-align: right; }
@media (prefers-reduced-motion: reduce) { .tr-preview .tr-busy { transition: none; } }
`;

function injectCss() {
  if (document.getElementById("titlerig-preview-css")) return;
  const s = document.createElement("style");
  s.id = "titlerig-preview-css";
  s.textContent = CSS;
  document.head.appendChild(s);
}

function getLink(graph, id) {
  if (id == null) return null;
  if (typeof graph.getLink === "function") return graph.getLink(id);
  const links = graph.links;
  return links instanceof Map ? links.get(id) : links?.[id];
}

// The node's upstream graph as plain JSON: widgets by name + linked inputs (recursively).
function treeFor(node, seen = new Set()) {
  if (!node || seen.has(node.id)) return null;
  seen.add(node.id);
  const widgets = {};
  for (const w of node.widgets || []) {
    if (!w?.name || w.name.startsWith("titlerig_") || typeof w.value === "function") continue;
    widgets[w.name] = w.value;
  }
  const inputs = {};
  for (const inp of node.inputs || []) {
    const l = getLink(node.graph || app.graph, inp.link);
    if (!l) continue;
    const origin = (node.graph || app.graph).getNodeById(l.origin_id);
    inputs[inp.name] = { node: treeFor(origin, new Set(seen)), slot: l.origin_slot };
  }
  return { type: node.comfyClass || node.type, widgets, inputs };
}

function el(tag, attrs = {}, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") e.className = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v);
  }
  kids.forEach((c) => e.append(c));
  return e;
}

function attachPreview(node) {
  injectCss();
  const animated = node.comfyClass === "TitleRigRenderAnimation";
  const state = { pass: "beauty", guides: false, frame: 0, frames: 1, fps: 24, playing: false, last: "", busy: false,
                  url: null };

  const img = el("img", { alt: "TitleRig preview" });
  const busy = el("div", { class: "tr-busy", "aria-hidden": "true" });
  const msg = el("div", { class: "tr-msg", role: "status" });
  const chips = PASSES.map(([key, label]) => el("button", {
    type: "button", "aria-pressed": String(key === state.pass), title: `Show the ${label.toLowerCase()} pass`,
    onclick: () => { state.pass = key; chips.forEach((c, i) => c.setAttribute("aria-pressed", String(PASSES[i][0] === key))); },
  }, label));
  const guides = el("button", { type: "button", "aria-pressed": "false", title: "Overlay the type guides",
    onclick: () => { state.guides = !state.guides; guides.setAttribute("aria-pressed", String(state.guides)); } }, "Guides");
  const bar = el("div", { class: "tr-bar" }, ...chips, guides);

  const root = el("div", { class: "tr-preview" }, bar, el("div", { class: "tr-stage" }, img, busy), msg);
  let slider, label, play;
  if (animated) {
    slider = el("input", { type: "range", min: "0", max: "0", value: "0", "aria-label": "Preview frame",
      oninput: () => { state.frame = +slider.value; } });
    label = el("span", {}, "0 / 0");
    play = el("button", { type: "button", "aria-pressed": "false", title: "Play the preview (at render speed)",
      onclick: () => { state.playing = !state.playing; play.setAttribute("aria-pressed", String(state.playing));
                       play.textContent = state.playing ? "Pause" : "Play"; } }, "Play");
    root.append(el("div", { class: "tr-time" }, play, slider, label));
  }

  const widget = node.addDOMWidget("titlerig_preview", "titlerig_preview", root, {
    serialize: false,
    hideOnZoom: false,
    getMinHeight: () => (animated ? 300 : 260),
  });
  widget.serializeValue = () => undefined;

  async function refresh() {
    if (state.busy || !node.graph) return;
    const payload = { node: treeFor(node), pass: state.pass, guides: state.guides, frame: state.frame,
                      max_width: Math.min(1024, Math.max(256, Math.round((root.clientWidth || 360) * devicePixelRatio))) };
    const key = JSON.stringify(payload);
    if (key === state.last) {
      if (!state.playing) return;
    }
    state.last = key;
    state.busy = true;
    busy.classList.add("on");
    try {
      const r = await api.fetchApi("/titlerig/preview", { method: "POST", body: key,
                                                          headers: { "Content-Type": "application/json" } });
      if (!r.ok) {
        const e = await r.json().catch(() => ({}));
        throw new Error(e.error || `preview failed (${r.status})`);
      }
      const blob = await r.blob();
      if (state.url) URL.revokeObjectURL(state.url);
      state.url = URL.createObjectURL(blob);
      img.src = state.url;
      const err = r.headers.get("X-TitleRig-Error") || "";
      msg.textContent = err;
      msg.classList.toggle("err", !!err);
      if (animated) {
        state.frames = +(r.headers.get("X-TitleRig-Frames") || 1);
        state.fps = +(r.headers.get("X-TitleRig-Fps") || 24);
        slider.max = String(Math.max(0, state.frames - 1));
        if (state.frame > state.frames - 1) state.frame = state.frames - 1;
        slider.value = String(state.frame);
        label.textContent = `${state.frame + 1} / ${state.frames}`;
        if (state.playing) state.frame = (state.frame + 1) % state.frames;
      }
    } catch (e) {
      msg.textContent = String(e.message || e);
      msg.classList.add("err");
    } finally {
      state.busy = false;
      busy.classList.remove("on");
    }
  }

  const timer = setInterval(refresh, POLL_MS);
  const onRemoved = node.onRemoved;
  node.onRemoved = function () {
    clearInterval(timer);
    if (state.url) URL.revokeObjectURL(state.url);
    return onRemoved?.apply(this, arguments);
  };
  const [w, h] = node.size;
  node.setSize([Math.max(w, 400), h + (animated ? 310 : 270)]);
  refresh();
}

app.registerExtension({
  name: "TitleRig.Preview",
  nodeCreated(node) {
    if (TARGETS.includes(node.comfyClass)) attachPreview(node);
  },
});
