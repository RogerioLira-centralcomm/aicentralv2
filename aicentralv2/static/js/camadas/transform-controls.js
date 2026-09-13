import { layerBox } from "./utils.js";
import { patchElement } from "./api.js";

export function bindTransforms(store, history) {
  const host = document.getElementById("mcCv2Handles");
  if (!host) return;

  function paint() {
    const state = store.getState();
    host.replaceChildren();
    if (state.stageMode !== "layers") return;
    const layer = (state.layers || []).find((item) => item.id === state.selectedLayerId);
    if (!layer || layer.locked || layer.type === "text") return;
    const box = layerBox(layer);
    [["nw", box.x, box.y], ["ne", box.x + box.w, box.y], ["sw", box.x, box.y + box.h], ["se", box.x + box.w, box.y + box.h]]
      .forEach(([name, x, y]) => {
        const handle = document.createElement("i");
        handle.className = `mc-cv2-handle is-${name}`;
        handle.style.left = `${x}%`;
        handle.style.top = `${y}%`;
        handle.addEventListener("pointerdown", (event) => start(event, layer, name, box));
        host.append(handle);
      });
  }

  function start(event, layer, corner, box) {
    event.stopPropagation();
    history.push();
    const startX = event.clientX;
    const startY = event.clientY;
    const move = (next) => {
      const dx = ((next.clientX - startX) / Math.max(1, host.clientWidth)) * 100;
      const dy = ((next.clientY - startY) / Math.max(1, host.clientHeight)) * 100;
      const nextBox = { ...box };
      if (corner.includes("e")) nextBox.w = Math.max(2, box.w + dx);
      if (corner.includes("s")) nextBox.h = Math.max(2, box.h + dy);
      if (corner.includes("w")) {
        nextBox.x = box.x + dx;
        nextBox.w = Math.max(2, box.w - dx);
      }
      if (corner.includes("n")) {
        nextBox.y = box.y + dy;
        nextBox.h = Math.max(2, box.h - dy);
      }
      replaceBox(layer.id, nextBox);
    };
    const up = async () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      const current = store.getState().layers.find((item) => item.id === layer.id);
      if (current?.bbox) {
        await patchElement(layer.id, { bbox: current.bbox });
      }
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  }

  function replaceBox(id, box) {
    store.setState((state) => ({
      layers: state.layers.map((item) => (
        item.id === id ? { ...item, bbox: { x: box.x, y: box.y, w: box.w, h: box.h } } : item
      )),
      dirty: true,
    }));
  }

  store.subscribe(paint);
  paint();
}
