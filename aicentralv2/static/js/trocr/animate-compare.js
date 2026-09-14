import { $ } from "./animate-utils.js";

export function bindCompare() {
  const dialog = $("mcTrocrClipCompare");
  if (!dialog) return;
  $("mcTrocrClipCompareBtn")?.addEventListener("click", () => openCompare());
  $("mcCompareA")?.addEventListener("change", loadPair);
  $("mcCompareB")?.addEventListener("change", loadPair);
  $("mcComparePlay")?.addEventListener("click", () => sync("play"));
  $("mcComparePause")?.addEventListener("click", () => sync("pause"));
  $("mcCompareRestart")?.addEventListener("click", () => sync("restart"));
}

export function refreshCompareButton() {
  const button = $("mcTrocrClipCompareBtn");
  if (!button) return;
  button.disabled = videos().length < 2;
}

function openCompare() {
  const items = videos();
  const dialog = $("mcTrocrClipCompare");
  if (!dialog || items.length < 2) return;
  fillSelect($("mcCompareA"), items, items[0]?.id);
  fillSelect($("mcCompareB"), items, items[1]?.id);
  loadPair();
  dialog.showModal();
}

function fillSelect(select, items, selected) {
  if (!select) return;
  select.innerHTML = items.map((item) => (
    `<option value="${escapeHtml(item.id)}"${item.id === selected ? " selected" : ""}>${escapeHtml(item.name || item.id)}</option>`
  )).join("");
}

function loadPair() {
  const items = videos();
  const left = items.find((item) => item.id === $("mcCompareA")?.value) || items[0];
  const right = items.find((item) => item.id === $("mcCompareB")?.value) || items[1];
  assign($("mcCompareVideoA"), left);
  assign($("mcCompareVideoB"), right);
}

function assign(node, version) {
  if (!node || !version) return;
  node.src = version.video_url || "";
  node.poster = version.poster_url || version.image || "";
  node.currentTime = 0;
}

function sync(action) {
  const pair = [$("mcCompareVideoA"), $("mcCompareVideoB")].filter(Boolean);
  pair.forEach((node) => {
    if (action === "restart") {
      node.currentTime = 0;
      node.play()?.catch(() => {});
      return;
    }
    if (action === "play") node.play()?.catch(() => {});
    else node.pause();
  });
}

function videos() {
  return window.__trocrAnimate?.videos?.() || [];
}

function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
