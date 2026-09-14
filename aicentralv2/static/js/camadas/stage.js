import { hitLayer } from "./utils.js";
import { segmentPoint } from "./api.js";
import { replaceLayer } from "./mask-editor.js";

export function bindStage(store, history, setStatus) {
  const viewport = document.getElementById("mcCv2Viewport");
  const world = document.getElementById("mcCv2World");
  const canvas = document.getElementById("mcCv2Canvas");
  const zoomLabel = document.getElementById("mcCv2ZoomLabel");
  if (!viewport || !world || !canvas) return;

  function fitScale() {
    const pad = 56;
    const vw = Math.max(160, viewport.clientWidth - pad);
    const vh = Math.max(120, viewport.clientHeight - pad);
    const width = canvas.width || 1;
    const height = canvas.height || 1;
    return Math.min(vw / width, vh / height);
  }

  function applyZoom() {
    const zoom = store.getState().zoom || 1;
    const fit = store.getState().creative ? fitScale() : 1;
    world.style.width = `${canvas.width || 0}px`;
    world.style.height = `${canvas.height || 0}px`;
    world.style.transform = `translate(-50%, -50%) scale(${zoom * fit})`;
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
  function holdCompare(on) {
    store.setState({ comparing: on });
  }
  document.getElementById("mcCv2Compare")?.addEventListener("pointerdown", () => holdCompare(true));
  document.getElementById("mcCv2Compare")?.addEventListener("pointerup", () => holdCompare(false));
  document.getElementById("mcCv2Compare")?.addEventListener("pointerleave", () => holdCompare(false));
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
    const typing = /INPUT|TEXTAREA|SELECT/.test(event.target.tagName);
    if (event.code === "Space" && !typing) {
      event.preventDefault();
      holdCompare(true);
      return;
    }
    if (event.key === "Escape") {
      store.setState({
        activeTool: "select",
        stageMode: store.getState().stageMode === "masks" ? "layers" : store.getState().stageMode,
      });
      return;
    }
    if (typing) return;
    if (event.key === "1") store.setState({ stageMode: "original" });
    if (event.key === "2") store.setState({ stageMode: "layers" });
    if (event.key === "3") store.setState({ stageMode: "html" });
    if (event.key === "[" || event.key === "]") {
      const layers = store.getState().layers || [];
      if (!layers.length) return;
      const index = layers.findIndex((item) => item.id === store.getState().selectedLayerId);
      const next = event.key === "]"
        ? (index + 1) % layers.length
        : (index - 1 + layers.length) % layers.length;
      store.setState({ selectedLayerId: layers[next].id });
    }
  });
  window.addEventListener("keyup", (event) => {
    if (event.code === "Space") holdCompare(false);
  });

  store.subscribe(() => {
    applyZoom();
    const state = store.getState();
    document.querySelectorAll("[data-stage-mode]").forEach((button) => {
      button.classList.toggle("is-current", button.getAttribute("data-stage-mode") === state.stageMode);
    });
    const html = state.stageMode === "html";
    const animation = state.stageMode === "animation";
    const hideStage = html || animation;
    const app = document.getElementById("mcCv2App");
    const selected = (state.layers || []).find((item) => item.id === state.selectedLayerId);
    app?.classList.toggle("is-html", html);
    app?.classList.toggle("is-image-selected", Boolean(selected && selected.type === "image"));
    canvas.classList.toggle("hidden", hideStage);
    document.getElementById("mcCv2Overlay")?.classList.toggle("hidden", hideStage);
    document.getElementById("mcCv2Svg")?.classList.toggle("hidden", hideStage);
    document.getElementById("mcCv2Handles")?.classList.toggle("hidden", hideStage);
    document.getElementById("mcCv2AnimPane")?.classList.toggle("relative", animation);
    document.getElementById("mcCv2AnimPane")?.classList.toggle("z-10", animation);
    document.getElementById("mcCv2AnimPane")?.classList.toggle("bg-white", animation);
    const creative = state.creative;
    const name = document.getElementById("mcCv2FileName");
    const size = document.getElementById("mcCv2Size");
    const ratio = document.getElementById("mcCv2Ratio");
    if (name) name.textContent = creative?.name || "Sem criativo";
    if (size) size.textContent = creative ? `${creative.width} × ${creative.height}` : "—";
    if (ratio && creative?.width && creative?.height) {
      const value = creative.width / creative.height;
      ratio.textContent = value >= 1.45 ? "16:9" : value <= 0.75 ? "9:16" : "1:1";
    } else if (ratio) ratio.textContent = "—";
  });
  if (typeof ResizeObserver !== "undefined") {
    new ResizeObserver(() => applyZoom()).observe(viewport);
  }
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
