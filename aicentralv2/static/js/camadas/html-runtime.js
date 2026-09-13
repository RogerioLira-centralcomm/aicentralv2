const RENDER = "camadas:render";
const SELECT = "camadas:select";
const EDIT = "camadas:edit";
const ASSET_PREFIX = "/static/uploads/camadas/";
const TEXT_ROLES = new Set([
  "headline", "support", "subtitle", "price", "cta", "legal",
  "date", "venue", "person_label", "logo_text",
]);
const IMAGE_ROLES = new Set([
  "background", "person", "product", "logo", "illustration", "graphic",
  "badge", "decoration", "foreground", "shadow",
]);

const root = document.getElementById("mcHtmlRuntime");
let editingId = "";
let lastScene = "";

function sameOrigin(event) {
  return event.origin === window.location.origin;
}

function safeColor(value) {
  return /^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/.test(String(value || "")) ? value : "#FFFFFF";
}

function safeFont(value) {
  const family = String(value || "Arial, sans-serif");
  if (!/^[A-Za-z0-9 ,.\-']+$/.test(family) || /url|expression|@import/i.test(family)) {
    return "Arial, sans-serif";
  }
  return family;
}

function pct(value, fallback) {
  const number = Number(value);
  if (!Number.isFinite(number)) return fallback;
  return `${Math.min(100, Math.max(0, number))}%`;
}

function assetSrc(path) {
  const value = String(path || "");
  if (value.startsWith(ASSET_PREFIX) && !value.includes("..") && !value.includes("<")) {
    return value;
  }
  return "";
}

function render(scene) {
  if (!root || !scene || scene.schema_version !== "2.0") return;
  const snapshot = JSON.stringify(scene);
  if (snapshot === lastScene) return;
  lastScene = snapshot;
  const canvas = scene.canvas || {};
  root.style.background = safeColor(canvas.background || "#000000");
  if (canvas.width && canvas.height) {
    root.style.aspectRatio = `${Number(canvas.width)} / ${Number(canvas.height)}`;
  }
  const selected = editingId;
  const nodes = (scene.layers || [])
    .filter((layer) => layer && layer.visible !== false)
    .sort((a, b) => Number(a.z_index || 0) - Number(b.z_index || 0))
    .map((layer) => makeLayer(layer, selected))
    .filter(Boolean);
  root.replaceChildren(...nodes);
}

function makeLayer(layer, selected) {
  const type = layer.type;
  const role = String(layer.role || "");
  if (type === "text" && !TEXT_ROLES.has(role)) return null;
  if (type === "image" && !IMAGE_ROLES.has(role)) return null;
  const style = layer.style || {};
  const node = document.createElement(type === "text" ? "p" : "img");
  node.className = "mc-html-layer";
  if (layer.id === selected) node.classList.add("is-selected");
  node.dataset.layer = String(layer.id || "");
  node.style.left = pct(layer.x, "8%");
  node.style.top = pct(layer.y, "12%");
  node.style.width = pct(layer.width, type === "image" ? "100%" : "40%");
  if (layer.height != null) node.style.height = pct(layer.height, "auto");
  node.style.zIndex = String(Number(layer.z_index || 0));
  node.style.transform = `rotate(${Number(layer.rotation || 0)}deg)`;
  if (type === "text") {
    node.contentEditable = "true";
    node.spellcheck = false;
    node.style.fontFamily = safeFont(style.font_family);
    node.style.fontSize = `${Math.min(240, Math.max(8, Number(style.font_size) || 32))}px`;
    node.style.fontWeight = String(Math.min(900, Math.max(100, Number(style.font_weight) || 400)));
    node.style.lineHeight = String(Math.min(2.5, Math.max(0.7, Number(style.line_height) || 1.05)));
    node.style.letterSpacing = `${Math.min(1, Math.max(-0.2, Number(style.letter_spacing) || 0))}em`;
    node.style.color = safeColor(style.color || "#FFFFFF");
    node.style.textAlign = ["left", "center", "right", "justify"].includes(style.text_align)
      ? style.text_align
      : "left";
    node.textContent = String(layer.text || "");
    node.addEventListener("focus", () => {
      editingId = layer.id;
      post(SELECT, { layerId: layer.id });
    });
    node.addEventListener("blur", () => {
      editingId = "";
      post(EDIT, { layerId: layer.id, properties: { text: node.textContent || "" } });
    });
    return node;
  }
  node.alt = String(layer.label || role);
  node.src = assetSrc(layer.asset_path);
  node.addEventListener("click", (event) => {
    event.stopPropagation();
    post(SELECT, { layerId: layer.id });
  });
  return node;
}

function post(type, extra) {
  window.parent.postMessage({ type, ...extra }, window.location.origin);
}

window.addEventListener("message", (event) => {
  if (!sameOrigin(event)) return;
  if (event.data?.type !== RENDER) return;
  render(event.data.scene);
});

root?.addEventListener("click", (event) => {
  if (event.target === root) post(SELECT, { layerId: "" });
});
