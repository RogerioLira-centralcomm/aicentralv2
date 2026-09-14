import { animatePreview, animateRecompose } from "./api.js";

export function bindAnimation(store, setStatus, setStep) {
  const pane = document.getElementById("mcCv2AnimPane");
  const refresh = document.getElementById("mcCv2AnimRefresh");
  const recompose = document.getElementById("mcCv2AnimRecompose");
  if (!pane) return;
  let jobId = "";

  async function loadPreview() {
    const state = store.getState();
    const creativeId = state.creative?.id;
    if (!creativeId) {
      setStatus("Abra um criativo para ver a placa.");
      return;
    }
    setStatus("Montando placa e overlay…");
    const data = await animatePreview(creativeId);
    jobId = data.job_id || "";
    setImage("mcCv2AnimPlate", data.plate);
    setImage("mcCv2AnimOverlay", data.overlay);
    setImage("mcCv2AnimComposite", data.composite);
    const meta = document.getElementById("mcCv2AnimMeta");
    if (meta) {
      meta.textContent = data.job_id
        ? `${data.creative_id} · cena v${data.scene_version} · job ${data.job_id}`
        : `${data.creative_id} · cena v${data.scene_version} · ainda sem clipe`;
    }
    const ahead = document.getElementById("mcCv2AnimAhead");
    if (ahead) ahead.classList.toggle("hidden", !data.scene_ahead);
    if (recompose) recompose.disabled = !jobId;
    setStatus(data.scene_ahead ? "Há revisão nova na cena." : "Preview da composição.");
  }

  refresh?.addEventListener("click", () => loadPreview().catch((error) => setStatus(error.message)));
  recompose?.addEventListener("click", async () => {
    const creativeId = store.getState().creative?.id;
    if (!creativeId || !jobId) return;
    setStatus("Recompondo overlay…");
    try {
      await animateRecompose(creativeId, { job_id: jobId });
      await loadPreview();
      setStatus("Overlay novo no histórico do Trocar.");
    } catch (error) {
      setStatus(error.message);
    }
  });

  let lastKey = "";
  store.subscribe((state) => {
    const active = state.stageMode === "animation";
    pane.classList.toggle("hidden", !active);
    pane.hidden = !active;
    if (!active) return;
    setStep("animation");
    const key = `${state.creative?.id || ""}:${state.sceneVersion || 0}`;
    if (key === lastKey) return;
    lastKey = key;
    if (state.creative?.id) loadPreview().catch((error) => setStatus(error.message));
  });
}

function setImage(id, url) {
  const node = document.getElementById(id);
  if (node && url) node.src = url;
}
