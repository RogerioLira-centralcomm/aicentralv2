import { listBrandAssets, listBrandCollections, placeAsset } from "./api.js";
import { assetUrl, escapeHtml } from "./utils.js";

const GROUPS = ["person", "product", "logo", "badge", "graphic", "background", "composition"];

export function bindLibrary(store, history, setStatus, setStep) {
  const list = document.getElementById("mcCv2LibraryList");
  const search = document.getElementById("mcCv2LibrarySearch");
  const viewport = document.getElementById("mcCv2Viewport");
  const note = document.getElementById("mcCv2LibraryNote");
  if (!list) return;

  function brandId() {
    return document.getElementById("mcCv2Brand")?.value.trim()
      || store.getState().creative?.brand_id
      || "";
  }

  async function load() {
    const id = brandId();
    if (!id) {
      store.setState({ assets: [], collections: [] });
      return;
    }
    try {
      const [payload, collections] = await Promise.all([
        listBrandAssets(id, {
          q: search?.value || "",
          collection_id: document.getElementById("mcCv2Collection")?.value || "",
        }),
        listBrandCollections(id),
      ]);
      store.setState({
        assets: payload.assets || [],
        collections: collections.collections || payload.collections || [],
      });
      paintCollections(collections.collections || payload.collections || []);
      if ((payload.assets || []).length) setStep?.("publish");
    } catch (error) {
      setStatus?.(error.message || "Não carreguei a folha da marca.");
    }
  }

  function paintCollections(collections) {
    const select = document.getElementById("mcCv2Collection");
    if (!select) return;
    const current = select.value;
    select.innerHTML = `<option value="">Geral</option>${(collections || []).map((item) => (
      `<option value="${escapeHtml(item.id)}">${escapeHtml(item.name)}</option>`
    )).join("")}`;
    if (current && [...select.options].some((item) => item.value === current)) {
      select.value = current;
    }
  }

  function paint() {
    const state = store.getState();
    const assets = state.assets || [];
    const counts = { all: assets.length };
    GROUPS.forEach((role) => {
      counts[role] = assets.filter((item) => item.kind === role).length;
    });
    document.querySelectorAll("[data-library-group]").forEach((node) => {
      const role = node.getAttribute("data-library-group") || "";
      const label = node.querySelector("span");
      if (label) label.textContent = String(counts[role] || 0);
    });
    if (note) {
      note.textContent = brandId()
        ? (assets.length ? "" : "Nada publicado nesta coleção. Publique um recorte no docket.")
        : "Escolha a marca para ver a coleção.";
    }
    document.querySelectorAll("[data-library-group]").forEach((node) => {
      const role = node.getAttribute("data-library-group") || "";
      const items = assets.filter((item) => item.kind === role);
      let strip = node.querySelector(".cv2-strip");
      if (!strip) {
        strip = document.createElement("ol");
        strip.className = "cv2-strip";
        node.appendChild(strip);
      }
      strip.hidden = !node.classList.contains("is-open");
      strip.innerHTML = items.map(thumbItem).join("");
    });
    list.innerHTML = "";
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
      setStep?.("publish");
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

  document.querySelectorAll("[data-library-group]").forEach((node) => {
    node.querySelector(".cv2-group-toggle")?.addEventListener("click", () => {
      node.classList.toggle("is-open");
      paint();
    });
  });
  search?.addEventListener("input", () => {
    window.clearTimeout(search._timer);
    search._timer = window.setTimeout(() => load(), 240);
  });
  document.getElementById("mcCv2Brand")?.addEventListener("change", () => load());
  document.getElementById("mcCv2Collection")?.addEventListener("change", () => load());
  document.getElementById("mcCv2LibraryClose")?.addEventListener("click", () => {
    const closed = document.getElementById("mcCv2App")?.classList.toggle("is-library-closed");
    sessionStorage.setItem("cv2Library", closed ? "closed" : "open");
  });

  const groups = document.getElementById("mcCv2LibraryGroups") || list;
  groups.addEventListener("dragstart", (event) => {
    const item = event.target.closest("[data-asset-id]");
    if (!item) return;
    event.dataTransfer.setData("application/x-camadas-asset", item.getAttribute("data-asset-id"));
    event.dataTransfer.setData("text/plain", item.getAttribute("data-asset-id"));
    event.dataTransfer.effectAllowed = "copy";
  });
  groups.addEventListener("click", (event) => {
    const item = event.target.closest("[data-asset-id]");
    if (!item) return;
    groups.querySelectorAll(".cv2-thumb").forEach((node) => node.classList.remove("is-current"));
    item.classList.add("is-current");
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

  if (sessionStorage.getItem("cv2Library") === "closed") {
    document.getElementById("mcCv2App")?.classList.add("is-library-closed");
  }

  store.subscribe(paint);
  paint();
  load();
}

function thumbItem(item) {
  const thumb = item.thumb_path && item.thumb_path !== item.asset_path ? item.thumb_path : "";
  const body = thumb
    ? `<img src="${escapeHtml(assetUrl(thumb))}" alt="">`
    : `<p>${escapeHtml(item.text || item.name || "")}</p>`;
  return `<li class="cv2-thumb${thumb ? "" : " is-empty"}" draggable="true" data-asset-id="${escapeHtml(item.id)}">${body}</li>`;
}
