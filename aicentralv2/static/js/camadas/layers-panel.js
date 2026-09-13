import { escapeHtml, qualityLabel } from "./utils.js";
import { patchElement } from "./api.js";

export function bindLayersPanel(store, history) {
  const list = document.getElementById("mcCv2LayerList");
  const count = document.getElementById("mcCv2LayerCount");
  if (!list) return;

  function paint() {
    const state = store.getState();
    const layers = [...(state.layers || [])].sort((a, b) => (b.z_index || 0) - (a.z_index || 0));
    if (count) count.textContent = String(layers.length);
    list.innerHTML = layers.map((layer) => {
      const current = layer.id === state.selectedLayerId ? " border-teal-700 bg-teal-50" : "";
      return `<li class="grid grid-cols-[auto_1fr_auto] items-center gap-2 border border-stone-200 px-2 py-1 text-sm${current}" data-layer-id="${escapeHtml(layer.id)}">
        <button type="button" data-vis="${escapeHtml(layer.id)}" aria-label="Visibilidade">${layer.visible === false ? "○" : "●"}</button>
        <button class="truncate text-left" type="button" data-select="${escapeHtml(layer.id)}">${escapeHtml(layer.label || layer.role)}</button>
        <span class="text-stone-500">${escapeHtml(qualityLabel(layer.quality))}</span>
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
