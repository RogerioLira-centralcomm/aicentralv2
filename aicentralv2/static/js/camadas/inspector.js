import { assetUrl, coverageLabel, layerBox, qualityLabel } from "./utils.js";
import { deleteElement, patchElement, publishElement, refineMask } from "./api.js";
import { persistScene } from "./html-preview.js";
import { replaceLayer } from "./mask-editor.js";

export function bindInspector(store, history, setStatus) {
  const form = document.getElementById("mcCv2Inspector");
  const empty = document.getElementById("mcCv2InspectorEmpty");
  if (!form) return;
  let painting = false;

  function current() {
    const state = store.getState();
    return (state.layers || []).find((item) => item.id === state.selectedLayerId) || null;
  }

  function sceneLayer(layer) {
    const scene = store.getState().scene;
    return (scene?.layers || []).find((item) => item.id === layer.id) || null;
  }

  function paint() {
    const layer = current();
    form.classList.toggle("hidden", !layer);
    empty?.classList.toggle("hidden", Boolean(layer));
    if (!layer) return;
    painting = true;
    const html = sceneLayer(layer) || {};
    const style = html.style || {};
    document.getElementById("mcCv2FieldLabel").value = layer.label || "";
    document.getElementById("mcCv2FieldText").value = html.text || layer.text || "";
    document.getElementById("mcCv2TextWrap").classList.toggle("hidden", layer.type !== "text");
    document.getElementById("mcCv2ImageWrap")?.classList.toggle("hidden", layer.type === "text");
    const box = layerBox(layer);
    setValue("mcCv2FieldX", box.x);
    setValue("mcCv2FieldY", box.y);
    setValue("mcCv2FieldW", box.w);
    setValue("mcCv2FieldH", box.h);
    const mask = document.getElementById("mcCv2FieldMask");
    if (mask) mask.checked = Boolean(store.getState().showMask);
    setValue("mcCv2FieldFont", style.font_family || "Arial, sans-serif");
    setValue("mcCv2FieldSize", style.font_size || 32);
    setValue("mcCv2FieldWeight", style.font_weight || 400);
    setValue("mcCv2FieldLeading", style.line_height || 1.05);
    setValue("mcCv2FieldTracking", style.letter_spacing || 0);
    setValue("mcCv2FieldAlign", style.text_align || "left");
    setValue("mcCv2FieldColor", toColorInput(style.color || "#FFFFFF"));
    document.getElementById("mcCv2FieldVisible").checked = layer.visible !== false;
    document.getElementById("mcCv2FieldLocked").checked = Boolean(layer.locked);
    document.getElementById("mcCv2FieldApproved").checked = Boolean(layer.approved);
    document.getElementById("mcCv2FieldMeta").textContent = [
      layer.role,
      qualityLabel(layer.quality),
      coverageLabel(layer),
    ].filter(Boolean).join("  ");
    const download = document.getElementById("mcCv2Download");
    if (download) {
      download.hidden = !layer.png_path;
      download.dataset.href = assetUrl(layer.png_path);
    }
    const publish = document.getElementById("mcCv2Publish");
    if (publish) publish.disabled = !layer.id;
    painting = false;
  }

  async function persist(partial) {
    const layer = current();
    if (!layer) return;
    history.push();
    const updated = await patchElement(layer.id, partial);
    store.setState((state) => ({
      layers: state.layers.map((item) => (item.id === layer.id ? { ...item, ...updated } : item)),
      dirty: true,
    }));
  }

  async function persistHtml(properties) {
    const layer = current();
    if (!layer || !store.getState().creative) return;
    history.push();
    try {
      const saved = await persistScene(store, [{
        operation: "update",
        layer_id: layer.id,
        properties,
      }]);
      store.setState((state) => ({
        scene: saved.scene,
        sceneVersion: saved.scene_version,
        layers: state.layers.map((item) => (
          item.id === layer.id
            ? { ...item, text: properties.text ?? item.text, label: properties.label || item.label }
            : item
        )),
        dirty: false,
      }));
    } catch (error) {
      setStatus?.(error.message || "Não gravei a cena HTML.");
    }
  }

  document.getElementById("mcCv2FieldLabel")?.addEventListener("change", (event) => {
    persist({ label: event.target.value });
  });
  document.getElementById("mcCv2FieldText")?.addEventListener("change", (event) => {
    persistHtml({ text: event.target.value });
  });
  document.getElementById("mcCv2FieldFont")?.addEventListener("change", (event) => {
    persistHtml({ style: { font_family: event.target.value } });
  });
  document.getElementById("mcCv2FieldSize")?.addEventListener("change", (event) => {
    persistHtml({ style: { font_size: Number(event.target.value) } });
  });
  document.getElementById("mcCv2FieldWeight")?.addEventListener("change", (event) => {
    persistHtml({ style: { font_weight: Number(event.target.value) } });
  });
  document.getElementById("mcCv2FieldLeading")?.addEventListener("change", (event) => {
    persistHtml({ style: { line_height: Number(event.target.value) } });
  });
  document.getElementById("mcCv2FieldTracking")?.addEventListener("change", (event) => {
    persistHtml({ style: { letter_spacing: Number(event.target.value) } });
  });
  document.getElementById("mcCv2FieldAlign")?.addEventListener("change", (event) => {
    persistHtml({ style: { text_align: event.target.value } });
  });
  document.getElementById("mcCv2FieldColor")?.addEventListener("change", (event) => {
    persistHtml({ style: { color: event.target.value } });
  });
  document.getElementById("mcCv2FieldVisible")?.addEventListener("change", (event) => {
    persist({ visible: event.target.checked });
  });
  document.getElementById("mcCv2FieldLocked")?.addEventListener("change", (event) => {
    persist({ locked: event.target.checked });
  });
  document.getElementById("mcCv2FieldApproved")?.addEventListener("change", (event) => {
    persist({ approved: event.target.checked });
  });
  document.getElementById("mcCv2Brand")?.addEventListener("change", paint);
  document.getElementById("mcCv2Publish")?.addEventListener("click", async () => {
    const layer = current();
    if (!layer) return;
    const brand = document.getElementById("mcCv2Brand")?.value.trim()
      || store.getState().creative?.brand_id;
    if (!brand) {
      setStatus?.("Informe a marca antes de publicar.");
      return;
    }
    try {
      const saved = await publishElement(layer.id, {
        collection_id: document.getElementById("mcCv2Collection")?.value || "",
        name: layer.label || layer.role,
      });
      const assets = store.getState().assets || [];
      const next = saved.asset;
      store.setState({
        assets: next && !assets.some((item) => item.id === next.id) ? [next, ...assets] : assets,
      });
      setStatus?.(
        saved.duplicate
          ? "Este recorte já estava na folha."
          : "Recorte publicado na folha.",
      );
    } catch (error) {
      setStatus?.(error.message || "Não publiquei o recorte.");
    }
  });
  document.getElementById("mcCv2FieldMask")?.addEventListener("change", (event) => {
    store.setState({ showMask: event.target.checked });
  });
  document.getElementById("mcCv2FieldFeather")?.addEventListener("change", async (event) => {
    const layer = current();
    if (!layer || layer.type === "text") return;
    history.push();
    const updated = await refineMask(layer.id, { feather_px: Number(event.target.value) || 0 });
    replaceLayer(store, updated);
  });
  document.getElementById("mcCv2FieldHalo")?.addEventListener("change", async (event) => {
    const layer = current();
    if (!layer || layer.type === "text" || !event.target.checked) return;
    history.push();
    const updated = await refineMask(layer.id, { remove_halo: true });
    replaceLayer(store, updated);
  });
  document.getElementById("mcCv2Remove")?.addEventListener("click", async () => {
    const layer = current();
    if (!layer) return;
    if (!window.confirm(`Remover ${layer.label || layer.role} da placa?`)) return;
    try {
      const saved = await deleteElement(layer.id);
      store.setState((state) => ({
        layers: state.layers.filter((item) => item.id !== layer.id),
        scene: saved.scene || state.scene,
        selectedLayerId: null,
      }));
      setStatus?.("Acetato removido.");
    } catch (error) {
      setStatus?.(error.message || "Não removi o acetato.");
    }
  });
  document.getElementById("mcCv2Download")?.addEventListener("click", () => {
    const href = document.getElementById("mcCv2Download")?.dataset.href;
    if (!href) return;
    const link = document.createElement("a");
    link.href = href;
    link.download = "";
    link.click();
  });

  store.subscribe(() => {
    if (!painting) paint();
  });
  paint();
}

function setValue(id, value) {
  const node = document.getElementById(id);
  if (node) node.value = value;
}

function toColorInput(value) {
  const text = String(value || "#FFFFFF");
  if (/^#[0-9a-fA-F]{6}$/.test(text)) return text;
  if (/^#[0-9a-fA-F]{3}$/.test(text)) {
    return `#${text[1]}${text[1]}${text[2]}${text[2]}${text[3]}${text[3]}`;
  }
  return "#FFFFFF";
}
