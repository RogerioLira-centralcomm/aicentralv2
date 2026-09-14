import { assetUrl, layerBox } from "./utils.js";

const images = new Map();

function loadImage(src) {
  if (!src) return Promise.resolve(null);
  if (images.has(src)) return images.get(src);
  const pending = new Promise((resolve) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => resolve(null);
    image.src = src;
  });
  images.set(src, pending);
  return pending;
}

export function bindCanvas(store) {
  const canvas = document.getElementById("mcCv2Canvas");
  const overlay = document.getElementById("mcCv2Overlay");
  if (!canvas || !overlay) return { paint() {} };
  const ctx = canvas.getContext("2d");
  const over = overlay.getContext("2d");

  async function paint() {
    const state = store.getState();
    const creative = state.creative;
    const empty = document.getElementById("mcCv2Empty");
    if (!creative) {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      over.clearRect(0, 0, overlay.width, overlay.height);
      empty?.classList.remove("hidden");
      return;
    }
    empty?.classList.add("hidden");
    const width = creative.width || 800;
    const height = creative.height || 450;
    canvas.width = width;
    canvas.height = height;
    overlay.width = width;
    overlay.height = height;
    ctx.clearRect(0, 0, width, height);
    over.clearRect(0, 0, width, height);
    const original = await loadImage(assetUrl(creative.original_path));
    const comparing = state.comparing || state.stageMode === "original";
    if (comparing) {
      if (original) ctx.drawImage(original, 0, 0, width, height);
    } else if (state.stageMode === "layers" || state.stageMode === "masks") {
      const layers = [...(state.layers || [])].sort((a, b) => (a.z_index || 0) - (b.z_index || 0));
      const selected = state.selectedLayerId;
      for (const layer of layers) {
        if (layer.visible === false || layer.type === "text") continue;
        const image = await loadImage(assetUrl(layer.png_path));
        if (!image) continue;
        const box = layerBox(layer);
        ctx.save();
        ctx.globalAlpha = selected && layer.id !== selected ? 0.42 : 1;
        ctx.drawImage(
          image,
          (box.x / 100) * width,
          (box.y / 100) * height,
          (box.w / 100) * width,
          (box.h / 100) * height,
        );
        ctx.restore();
      }
    }
    const selected = (state.layers || []).find((item) => item.id === state.selectedLayerId);
    if (state.showMask && selected?.mask_path) {
      const mask = await loadImage(assetUrl(selected.mask_path));
      if (mask) {
        over.save();
        over.globalAlpha = 0.35;
        over.drawImage(mask, 0, 0, width, height);
        over.restore();
      }
    }
  }

  store.subscribe(() => {
    paint();
  });
  paint();
  return { paint };
}
