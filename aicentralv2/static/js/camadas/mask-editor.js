import { refineMask } from "./api.js";

export function bindMaskEditor(store, history, setStatus) {
  document.querySelectorAll("[data-tool]").forEach((button) => {
    button.addEventListener("click", () => {
      store.setState({ activeTool: button.getAttribute("data-tool") });
    });
  });
  document.querySelectorAll("[data-mask-op]").forEach((button) => {
    button.addEventListener("click", async () => {
      const id = store.getState().selectedLayerId;
      if (!id) {
        setStatus("Selecione uma camada de imagem.");
        return;
      }
      const op = button.getAttribute("data-mask-op");
      const body = {
        expand: { expand_px: 3 },
        contract: { expand_px: -3 },
        feather: { feather_px: 1.5 },
        halo: { remove_halo: true },
      }[op] || {};
      history.push();
      setStatus("Refinando a máscara.");
      const updated = await refineMask(id, body);
      replaceLayer(store, updated);
      setStatus("Máscara atualizada.");
    });
  });
  store.subscribe(() => {
    const tool = store.getState().activeTool;
    document.querySelectorAll("[data-tool]").forEach((button) => {
      button.classList.toggle("is-current", button.getAttribute("data-tool") === tool);
    });
    const viewport = document.getElementById("mcCv2Viewport");
    viewport?.classList.toggle("is-brush", tool === "brush");
    viewport?.classList.toggle("is-erase", tool === "erase");
  });

  const viewport = document.getElementById("mcCv2Viewport");
  const canvas = document.getElementById("mcCv2Canvas");
  let drawing = false;
  let strokes = [];
  viewport?.addEventListener("pointerdown", (event) => {
    const tool = store.getState().activeTool;
    if (tool !== "brush" && tool !== "erase") return;
    drawing = true;
    strokes = [pointOn(event, canvas, tool)];
  });
  window.addEventListener("pointermove", (event) => {
    if (!drawing) return;
    strokes.push(pointOn(event, canvas, store.getState().activeTool));
  });
  window.addEventListener("pointerup", async () => {
    if (!drawing) return;
    drawing = false;
    const id = store.getState().selectedLayerId;
    if (!id || !strokes.length) return;
    history.push();
    const updated = await refineMask(id, { brush_strokes: strokes.filter(Boolean) });
    replaceLayer(store, updated);
    strokes = [];
  });
}

function pointOn(event, canvas, tool) {
  if (!canvas) return null;
  const rect = canvas.getBoundingClientRect();
  return {
    x: (event.clientX - rect.left) / rect.width,
    y: (event.clientY - rect.top) / rect.height,
    r: 8,
    mode: tool === "erase" ? "erase" : "include",
  };
}

export function replaceLayer(store, layer) {
  if (!layer?.id) return;
  store.setState((state) => ({
    layers: state.layers.some((item) => item.id === layer.id)
      ? state.layers.map((item) => (item.id === layer.id ? { ...item, ...layer } : item))
      : state.layers.concat(layer),
    selectedLayerId: layer.id,
    dirty: true,
  }));
}
