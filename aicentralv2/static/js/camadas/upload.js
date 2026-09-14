import { createCreative, getCreative } from "./api.js";
import { waitJob } from "./jobs.js";

export function bindUpload(store, setStatus, setStep) {
  const fileInput = document.getElementById("mcCamadasV2File");
  const mapBtn = document.getElementById("mcCv2Map");
  const viewport = document.getElementById("mcCv2Viewport");
  if (!fileInput || !mapBtn) return;

  async function run(file) {
    if (!file || !file.type.startsWith("image/")) {
      setStatus("Envie um PNG, JPG ou WEBP.");
      return;
    }
    mapBtn.disabled = true;
    setStep("upload");
    setStatus("Enviando original.");
    try {
      const created = await createCreative({
        file,
        name: file.name || "",
        brandId: document.getElementById("mcCv2Brand")?.value || "",
        collectionId: document.getElementById("mcCv2Collection")?.value || "",
      });
      const job = await waitJob(created.job_id, (item) => {
        store.setState({ job: item });
        setStatus(item.message || "Analisando.");
      });
      if (job.status === "failed") {
        throw new Error(job.error || job.message || "A análise falhou.");
      }
      const payload = await getCreative(created.creative_id);
      store.setState({
        creative: payload.creative,
        layers: payload.elements || [],
        scene: payload.scene,
        sceneVersion: payload.scene_version || 1,
        assets: payload.assets || [],
        selectedLayerId: null,
        job,
        dirty: false,
        stageMode: "layers",
      });
      setStep("review");
      setStatus(job.message || "Camadas prontas.");
    } catch (error) {
      setStatus(error.message || "Não mapeei o criativo.");
    } finally {
      mapBtn.disabled = false;
    }
  }

  mapBtn.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", () => {
    const file = fileInput.files?.[0];
    if (file) run(file);
  });
  viewport?.addEventListener("dragover", (event) => {
    event.preventDefault();
    viewport.classList.add("is-pan");
  });
  viewport?.addEventListener("dragleave", () => viewport.classList.remove("is-pan"));
  viewport?.addEventListener("drop", (event) => {
    const assetId = event.dataTransfer?.getData("application/x-camadas-asset")
      || event.dataTransfer?.getData("text/plain");
    if (String(assetId).startsWith("ast_")) return;
    event.preventDefault();
    viewport.classList.remove("is-pan");
    run(event.dataTransfer?.files?.[0]);
  });
}
