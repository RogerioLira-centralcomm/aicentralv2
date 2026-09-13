import { listBrandAssets, placeAsset } from "./api.js";
import { assetUrl, escapeHtml, provenanceLabel } from "./utils.js";

const GROUPS = [
  "person", "product", "logo", "badge", "graphic",
  "illustration", "background", "composition",
];

export function bindLibrary(store, history, setStatus, setStep) {
  const list = document.getElementById("mcCv2LibraryList");
  const search = document.getElementById("mcCv2LibrarySearch");
  const viewport = document.getElementById("mcCv2Viewport");
  if (!list) return;
  let kind = "";

  function brandId() {
    return document.getElementById("mcCv2Brand")?.value.trim()
      || store.getState().creative?.brand_id
      || "";
  }

  async function load() {
    const id = brandId();
    if (!id) {
      store.setState({ assets: [] });
      return;
    }
    try {
      const payload = await listBrandAssets(id, {
        kind,
        q: search?.value || "",
      });
      store.setState({
        assets: payload.assets || [],
        collections: payload.collections || [],
      });
      if ((payload.assets || []).length) setStep?.("library");
    } catch (error) {
      setStatus?.(error.message || "Não carreguei a biblioteca.");
    }
  }

  function paint() {
    const state = store.getState();
    const assets = state.assets || [];
    const counts = { all: assets.length };
    GROUPS.forEach((role) => {
      counts[role] = assets.filter((item) => item.kind === role).length;
    });
    document.querySelectorAll("[data-library-group]").forEach((button) => {
      const role = button.getAttribute("data-library-group") || "";
      const node = button.querySelector("span");
      if (node) node.textContent = String(role ? counts[role] || 0 : counts.all);
      button.classList.toggle("is-current", role === kind);
    });
    if (!assets.length) {
      list.innerHTML = `<li class="text-sm text-stone-500">${
        brandId()
          ? "Nenhum ativo publicado nesta coleção."
          : "Informe a marca para ver a biblioteca."
      }</li>`;
      return;
    }
    list.innerHTML = assets.map((item) => {
      const thumb = item.thumb_path || item.asset_path;
      return `<li class="grid gap-1 border border-stone-200 p-1" draggable="true" data-asset-id="${escapeHtml(item.id)}">
        ${thumb
          ? `<img class="pointer-events-none h-16 w-full object-contain" src="${escapeHtml(assetUrl(thumb))}" alt="${escapeHtml(item.name || "")}">`
          : `<p class="m-0 line-clamp-3 text-sm">${escapeHtml(item.text || item.name || "")}</p>`}
        <span class="text-sm">${escapeHtml(item.name || item.kind)}</span>
        <span class="text-xs text-stone-500">${escapeHtml(provenanceLabel(item.provenance))}</span>
      </li>`;
    }).join("");
  }

  async function dropAsset(assetId, point) {
    const creative = store.getState().creative;
    if (!creative) {
      setStatus?.("Mapeie um criativo antes de soltar o ativo.");
      return;
    }
    history?.push();
    try {
      const placed = await placeAsset(creative.id, {
        asset_id: assetId,
        x: point?.x,
        y: point?.y,
      });
      store.setState((state) => ({
        layers: [...state.layers, placed.element],
        scene: placed.scene || state.scene,
        sceneVersion: placed.scene_version || state.sceneVersion,
        selectedLayerId: placed.element?.id || state.selectedLayerId,
        dirty: true,
      }));
      setStatus?.("Ativo na cena.");
      setStep?.("library");
    } catch (error) {
      setStatus?.(error.message || "Não coloquei o ativo na cena.");
    }
  }

  function dropPoint(event) {
    const rect = viewport?.getBoundingClientRect();
    if (!rect?.width || !rect.height) return {};
    return {
      x: ((event.clientX - rect.left) / rect.width) * 100,
      y: ((event.clientY - rect.top) / rect.height) * 100,
    };
  }

  document.querySelectorAll("[data-library-group]").forEach((button) => {
    button.addEventListener("click", () => {
      kind = button.getAttribute("data-library-group") || "";
      if (brandId()) load();
      else paint();
    });
  });
  search?.addEventListener("input", () => {
    window.clearTimeout(search._timer);
    search._timer = window.setTimeout(() => load(), 240);
  });
  document.getElementById("mcCv2Brand")?.addEventListener("change", () => load());

  list.addEventListener("dragstart", (event) => {
    const item = event.target.closest("[data-asset-id]");
    if (!item) return;
    event.dataTransfer.setData("application/x-camadas-asset", item.getAttribute("data-asset-id"));
    event.dataTransfer.setData("text/plain", item.getAttribute("data-asset-id"));
    event.dataTransfer.effectAllowed = "copy";
  });

  viewport?.addEventListener("dragover", (event) => {
    const types = [...(event.dataTransfer?.types || [])];
    if (!types.includes("application/x-camadas-asset") && !types.includes("text/plain")) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "copy";
  });
  viewport?.addEventListener("drop", (event) => {
    const assetId = event.dataTransfer.getData("application/x-camadas-asset")
      || event.dataTransfer.getData("text/plain");
    if (!String(assetId).startsWith("ast_")) return;
    event.preventDefault();
    event.stopPropagation();
    dropAsset(assetId, dropPoint(event));
  });

  store.subscribe(paint);
  paint();
  load();
}
