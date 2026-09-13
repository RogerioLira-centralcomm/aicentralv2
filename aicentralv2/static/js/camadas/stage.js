import { hitLayer } from "./utils.js";
import { segmentPoint } from "./api.js";
import { replaceLayer } from "./mask-editor.js";

export function bindStage(store, history, setStatus) {
  const viewport = document.getElementById("mcCv2Viewport");
  const world = document.getElementById("mcCv2World");
  const canvas = document.getElementById("mcCv2Canvas");
  const zoomLabel = document.getElementById("mcCv2ZoomLabel");
  if (!viewport || !world || !canvas) return;

  function applyZoom() {
    const zoom = store.getState().zoom || 1;
    world.style.transform = `translate(-50%, -50%) scale(${zoom})`;
    if (zoomLabel) zoomLabel.textContent = `${Math.round(zoom * 100)}%`;
  }

  function imagePoint(event) {
    const rect = canvas.getBoundingClientRect();
    if (!rect.width || !rect.height) return null;
    const x = (event.clientX - rect.left) / rect.width;
    const y = (event.clientY - rect.top) / rect.height;
    if (x < 0 || y < 0 || x > 1 || y > 1) return null;
    return { x, y };
  }

  document.querySelectorAll("[data-stage-mode]").forEach((button) => {
    button.addEventListener("click", () => {
      store.setState({ stageMode: button.getAttribute("data-stage-mode") });
    });
  });
  document.getElementById("mcCv2ZoomIn")?.addEventListener("click", () => {
    store.setState({ zoom: Math.min(4, (store.getState().zoom || 1) + 0.25) });
  });
  document.getElementById("mcCv2ZoomOut")?.addEventListener("click", () => {
    store.setState({ zoom: Math.max(0.25, (store.getState().zoom || 1) - 0.25) });
  });
  viewport.addEventListener("wheel", (event) => {
    if (!event.ctrlKey && !event.metaKey) return;
    event.preventDefault();
    const delta = event.deltaY > 0 ? -0.1 : 0.1;
    store.setState({ zoom: Math.min(4, Math.max(0.25, (store.getState().zoom || 1) + delta)) });
  }, { passive: false });

  viewport.addEventListener("click", async (event) => {
    const point = imagePoint(event);
    const state = store.getState();
    if (!point || !state.creative) return;
    const tool = state.activeTool;
    if (event.shiftKey || tool === "add") {
      await clickSegment(store, point, setStatus, history);
      return;
    }
    if (event.altKey || tool === "subtract") {
      const selected = state.selectedLayerId;
      if (selected) {
        const { refineMask } = await import("./api.js");
        history.push();
        const updated = await refineMask(selected, { negative_points: [point] });
        replaceLayer(store, updated);
      }
      return;
    }
    const hit = hitLayer(state.layers, point.x * 100, point.y * 100);
    if (hit) {
      store.setState({ selectedLayerId: hit.id });
      return;
    }
    if (state.stageMode === "masks") {
      await clickSegment(store, point, setStatus, history);
    }
  });

  viewport.addEventListener("dblclick", (event) => {
    const point = imagePoint(event);
    if (!point) return;
    const hit = hitLayer(store.getState().layers, point.x * 100, point.y * 100);
    if (!hit) return;
    store.setState((state) => ({
      layers: state.layers.map((item) => ({
        ...item,
        visible: item.id === hit.id || item.role === "background",
      })),
      selectedLayerId: hit.id,
    }));
  });

  window.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      store.setState({ activeTool: "select", stageMode: store.getState().stageMode === "masks" ? "layers" : store.getState().stageMode });
    }
  });

  store.subscribe(() => {
    applyZoom();
    document.querySelectorAll("[data-stage-mode]").forEach((button) => {
      button.classList.toggle("is-current", button.getAttribute("data-stage-mode") === store.getState().stageMode);
    });
    const html = store.getState().stageMode === "html";
    canvas.classList.toggle("hidden", html);
    document.getElementById("mcCv2Overlay")?.classList.toggle("hidden", html);
    document.getElementById("mcCv2Svg")?.classList.toggle("hidden", html);
    document.getElementById("mcCv2Handles")?.classList.toggle("hidden", html);
  });
  applyZoom();
}

async function clickSegment(store, point, setStatus, history) {
  const state = store.getState();
  setStatus("Procurando elemento no clique.");
  history.push();
  const result = await segmentPoint(state.creative.id, {
    positive_points: [point],
    negative_points: [],
    element_id: state.selectedLayerId,
  });
  if (result.element) {
    replaceLayer(store, result.element);
    setStatus(result.created ? "Nova camada no clique." : "Camada selecionada.");
  }
  return result;
}
