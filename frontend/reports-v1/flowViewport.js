// Fits the map inside the part of the canvas that panels leave visible, so the
// journey is centered where the user can actually see it, not under a drawer.
const PALETTE_INSET = 288 + 16;
const INSPECTOR_INSET = 304 + 16;
const EDGE = 24;
const TOP = 56;
// Zoom controls and the minimap sit at the bottom; content is fitted above them.
const BOTTOM = 80;

export function visibleCanvasArea() {
  const canvas = document.querySelector('.reports-flow-canvas');
  if (!canvas) return null;
  const rect = canvas.getBoundingClientRect();
  const designer = document.querySelector('.reports-flow-designer');
  const left = designer?.classList.contains('has-palette') ? PALETTE_INSET : 0;
  const right = designer?.classList.contains('has-inspector') || document.querySelector('.flow-blueprint-panel') ? INSPECTOR_INSET : 0;
  return {left: left + EDGE, top: TOP, width: Math.max(160, rect.width - left - right - EDGE * 2), height: Math.max(160, rect.height - TOP - BOTTOM)};
}

export function fitToVisibleArea(flow, {maxZoom = 1.5, minZoom = .25, duration = 0, nodes} = {}) {
  if (!flow) return false;
  const area = visibleCanvasArea();
  const items = (nodes || flow.getNodes()).filter(node => !node.hidden);
  if (!area || !items.length) return false;
  const bounds = flow.getNodesBounds(items);
  if (!bounds.width || !bounds.height) return false;
  const zoom = Math.max(minZoom, Math.min(maxZoom, area.width / bounds.width, area.height / bounds.height));
  const x = area.left + (area.width - bounds.width * zoom) / 2 - bounds.x * zoom;
  const y = area.top + (area.height - bounds.height * zoom) / 2 - bounds.y * zoom;
  flow.setViewport({x, y, zoom}, {duration});
  return true;
}
