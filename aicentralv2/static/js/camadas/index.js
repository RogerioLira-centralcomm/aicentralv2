import { createStore } from "./store.js";
import { createHistory } from "./history.js";
import { bindUpload } from "./upload.js";
import { bindCanvas } from "./canvas-renderer.js";
import { bindContours } from "./contour-renderer.js";
import { bindStage } from "./stage.js";
import { bindMaskEditor } from "./mask-editor.js";
import { bindTransforms } from "./transform-controls.js";
import { bindLayersPanel } from "./layers-panel.js";
import { bindInspector } from "./inspector.js";
import { bindLibrary } from "./asset-library.js";
import { bindHtmlPreview } from "./html-preview.js";

const root = document.getElementById("mcCv2App");
if (root) {
  const store = createStore();
  const history = createHistory(store);
  const status = document.getElementById("mcCamadasV2Status");

  function setStatus(text) {
    if (status) status.textContent = text;
  }

  function setStep(name) {
    const order = ["upload", "map", "split", "review", "html", "library"];
    const index = order.indexOf(name);
    document.querySelectorAll("[data-cv2-step]").forEach((node) => {
      const step = node.getAttribute("data-cv2-step");
      const here = order.indexOf(step);
      node.classList.toggle("border-teal-700", here <= index);
      node.classList.toggle("text-stone-500", here > index);
    });
  }

  bindUpload(store, setStatus, setStep);
  bindCanvas(store);
  bindContours(store);
  bindStage(store, history, setStatus);
  bindMaskEditor(store, history, setStatus);
  bindTransforms(store, history);
  bindLayersPanel(store, history);
  bindInspector(store, history, setStatus);
  bindLibrary(store, history, setStatus, setStep);
  bindHtmlPreview(store, history, setStatus);

  document.getElementById("mcCv2Undo")?.addEventListener("click", () => history.undo());
  document.getElementById("mcCv2Redo")?.addEventListener("click", () => history.redo());
  document.getElementById("mcCv2Save")?.addEventListener("click", () => {
    store.setState({ dirty: false });
    setStatus("Alterações desta sessão estão no servidor.");
  });
  document.getElementById("mcCv2Clean")?.addEventListener("click", () => {
    setStatus("Limpar fundo entra na Fase 6.");
  });

  store.subscribe((state) => {
    const save = document.getElementById("mcCv2Save");
    if (save) save.disabled = !state.creative;
    if (state.stageMode === "html") setStep("html");
  });
}
