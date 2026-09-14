import { createStore } from "./store.js";
import { createHistory } from "./history.js";
import { cleanBackground, exportCreative } from "./api.js";
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
import { bindAnimation } from "./animation-panel.js";
import { needsReview } from "./utils.js";

const STEPS = ["upload", "read", "segment", "review", "html", "animation", "publish"];
const STAGE_STEP = {
  queued: "upload",
  reading_creative: "read",
  finding_objects: "segment",
  extracting_elements: "segment",
  assembling_scene: "html",
  preparing_review: "review",
  done: "review",
  failed: "upload",
};

const root = document.getElementById("mcCv2App");
if (root) {
  const store = createStore();
  const history = createHistory(store);
  const status = document.getElementById("mcCamadasV2Status");

  function setStatus(text, isError) {
    if (!status) return;
    status.textContent = text;
    status.classList.toggle("is-error", Boolean(isError));
  }

  function setStep(name) {
    const index = STEPS.indexOf(name);
    document.querySelectorAll("[data-cv2-step]").forEach((node) => {
      const here = STEPS.indexOf(node.getAttribute("data-cv2-step"));
      node.classList.toggle("is-current", here === index);
      node.classList.toggle("is-done", here >= 0 && here < index);
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
  bindAnimation(store, setStatus, setStep);

  document.getElementById("mcCv2Undo")?.addEventListener("click", () => history.undo());
  document.getElementById("mcCv2Redo")?.addEventListener("click", () => history.redo());
  document.getElementById("mcCv2Save")?.addEventListener("click", () => {
    store.setState({ dirty: false });
    setStatus("Alterações desta sessão estão no servidor.");
  });
  function syncClean(state) {
    const button = document.getElementById("mcCv2Clean");
    if (!button) return;
    const creative = state.creative || {};
    const allowed = Boolean(creative.can_clean_background && creative.clean_configured);
    button.disabled = !allowed;
    button.title = !creative.id
      ? "Mapeie um criativo."
      : !creative.can_clean_background
        ? "Só limpa poço de foto. Em papel a tinta já é o wash."
        : !creative.clean_configured
          ? "Configure o modelo de imagem da Camadas."
          : "Limpa o poço fotográfico. Não recria pessoa, produto nem logo.";
  }

  document.getElementById("mcCv2Clean")?.addEventListener("click", async () => {
    const creative = store.getState().creative;
    if (!creative?.can_clean_background) {
      setStatus("Este still é papel. A tinta já é o wash.");
      return;
    }
    if (!creative.clean_configured) {
      setStatus("Limpar fundo não está configurado.");
      return;
    }
    const button = document.getElementById("mcCv2Clean");
    if (button) button.disabled = true;
    setStatus("Limpando o poço fotográfico.");
    try {
      const saved = await cleanBackground(creative.id);
      store.setState((state) => ({
        layers: state.layers.map((item) => (
          item.id === saved.element?.id ? { ...item, ...saved.element } : item
        )),
        scene: saved.scene || state.scene,
        creative: { ...state.creative, ...(saved.creative || {}) },
        dirty: true,
      }));
      setStatus("Poço limpo. Pessoa, produto e logo ficaram no recorte original.");
    } catch (error) {
      setStatus(error.message || "Não limpei o fundo.", true);
    } finally {
      syncClean(store.getState());
    }
  });
  document.getElementById("mcCv2Export")?.addEventListener("click", async () => {
    const creative = store.getState().creative;
    if (!creative) return;
    try {
      const payload = await exportCreative(creative.id);
      const blob = new Blob([payload.html || ""], { type: "text/html;charset=utf-8" });
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = `${payload.name || "camadas"}.html`;
      link.click();
      URL.revokeObjectURL(link.href);
      setStatus("HTML exportado.");
    } catch (error) {
      setStatus(error.message || "Não exportei o HTML.", true);
    }
  });
  document.getElementById("mcCv2Advance")?.addEventListener("click", () => {
    const state = store.getState();
    const jobStep = STAGE_STEP[state.job?.stage] || "";
    if (!state.creative) {
      document.getElementById("mcCv2Map")?.click();
      return;
    }
    const pending = (state.layers || []).filter(needsReview);
    if (pending.length && jobStep === "review") {
      const current = pending.find((item) => item.id === state.selectedLayerId);
      const index = pending.indexOf(current);
      store.setState({ selectedLayerId: pending[(index + 1) % pending.length].id });
      setStep("review");
      return;
    }
    store.setState({ stageMode: "html" });
    setStep("html");
  });

  store.subscribe((state) => {
    const save = document.getElementById("mcCv2Save");
    const exported = document.getElementById("mcCv2Export");
    if (save) save.disabled = !state.creative;
    if (exported) exported.disabled = !state.creative;
    syncClean(state);
    if (state.job?.stage) setStep(STAGE_STEP[state.job.stage] || "upload");
    if ((state.assets || []).length) setStep("publish");
    if (state.stageMode === "html") setStep("html");
    if (state.stageMode === "animation") setStep("animation");
    if (state.job?.status === "failed") setStatus(state.job.error || state.job.message || "A análise falhou.", true);
  });
}
