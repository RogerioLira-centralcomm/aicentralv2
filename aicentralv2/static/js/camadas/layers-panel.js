import { coverageLabel, escapeHtml, needsReview, qualityLabel, thumbUrl } from "./utils.js";
import { patchElement } from "./api.js";

export function bindLayersPanel(store, history) {
  const list = document.getElementById("mcCv2LayerList");
  const count = document.getElementById("mcCv2LayerCount");
  const review = document.getElementById("mcCv2ReviewCount");
  if (!list) return;

  function paint() {
    const state = store.getState();
    const layers = [...(state.layers || [])].sort((a, b) => {
      const rev = Number(needsReview(b)) - Number(needsReview(a));
      if (rev) return rev;
      return (b.z_index || 0) - (a.z_index || 0);
    });
    if (count) count.textContent = `${layers.length} elementos`;
    const pending = layers.filter(needsReview).length;
    if (review) review.textContent = `${pending} pedem revisão`;
    list.innerHTML = layers.map((layer) => {
      const current = layer.id === state.selectedLayerId ? " is-current" : "";
      const warn = needsReview(layer) ? " is-review" : "";
      const thumb = thumbUrl(layer);
      const seal = coverageLabel(layer) || qualityLabel(layer.quality);
      const initial = (layer.label || layer.role || "?").slice(0, 1).toUpperCase();
      const media = thumb
        ? `<img class="cv2-layer-thumb" src="${escapeHtml(thumb)}" alt="">`
        : `<span class="cv2-layer-thumb is-text">${escapeHtml(initial)}</span>`;
      return `<li class="cv2-layer${current}${warn}" data-layer-id="${escapeHtml(layer.id)}">
        <button type="button" data-vis="${escapeHtml(layer.id)}" aria-label="Visibilidade">
          <svg class="cv2-ico" aria-hidden="true"><use href="#${layer.visible === false ? "cv2-eye-off" : "cv2-eye"}"/></svg>
        </button>
        ${media}
        <button class="truncate text-left" type="button" data-select="${escapeHtml(layer.id)}">${escapeHtml(layer.label || layer.role)}</button>
        <span class="cv2-seal">${escapeHtml(seal)}</span>
      </li>`;
    }).join("");
  }

  list.addEventListener("click", async (event) => {
    const select = event.target.closest("[data-select]");
    const vis = event.target.closest("[data-vis]");
    if (select) {
      store.setState({ selectedLayerId: select.getAttribute("data-select") });
      return;
    }
    if (!vis) return;
    const id = vis.getAttribute("data-vis");
    const layer = store.getState().layers.find((item) => item.id === id);
    if (!layer) return;
    history.push();
    const visible = layer.visible === false;
    const updated = await patchElement(id, { visible });
    store.setState((state) => ({
      layers: state.layers.map((item) => (item.id === id ? { ...item, ...updated, visible } : item)),
    }));
  });

  store.subscribe(paint);
  paint();
}
