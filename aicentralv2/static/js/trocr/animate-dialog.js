import { cancelAnimate, quoteAnimate, submitAnimate } from "./animate-api.js";
import { bindLayers, layerIntents, refreshLayers, selectedToId, sourceMode } from "./animate-layers.js";
import { startPoll } from "./animate-poller.js";
import { animateState } from "./animate-store.js";
import { $ } from "./animate-utils.js";

export function readForm() {
  const duration = Number(document.querySelector("input[name=mcAnimateDuration]:checked")?.value || 8);
  const quality = document.querySelector("input[name=mcAnimateQuality]:checked")?.value || "draft";
  const motion = document.querySelector("input[name=mcAnimateMotion]:checked")?.value || "live";
  const audio = document.querySelector("input[name=mcAnimateAudio]:checked")?.value || "silence";
  const delivery = ["master"];
  document.querySelectorAll("input[name=mcAnimatePack]:checked").forEach((node) => {
    if (node.value !== "master") delivery.push(node.value);
  });
  return {
    duration,
    quality,
    resolution: quality === "production" ? "720p" : "480p",
    motion: {
      preset: motion,
      intensity: $("mcAnimateIntensity")?.value || "subtle",
      note: $("mcAnimateNote")?.value || "",
    },
    audio: {
      mode: audio,
      prompt: $("mcAnimateVoice")?.value || "",
      music_note: $("mcAnimateMusic")?.value || "",
    },
    delivery,
    gif_window: document.querySelector("input[name=mcAnimateGifWindow]:checked")?.value || "first",
    source: { mode: sourceMode(), to_id: selectedToId() },
    to_id: selectedToId(),
    extra_ids: selectedToId() ? [selectedToId()] : [],
    layer_intents: layerIntents(),
    camadas_creative_id: window.__trocrAnimate?.camadasId?.() || "",
  };
}

export function bindDialog(context) {
  const dialog = $("mcTrocrAnimate");
  if (!dialog) return;
  document.querySelectorAll("input[name=mcAnimateAudio]").forEach((node) => {
    node.addEventListener("change", () => {
      const mode = document.querySelector("input[name=mcAnimateAudio]:checked")?.value;
      $("mcAnimateVoiceRow").hidden = mode !== "voice";
      $("mcAnimateMusicRow").hidden = mode !== "music";
      refreshQuote(context);
    });
  });
  $("mcAnimateGif")?.addEventListener("change", () => {
    $("mcAnimateGifWindow").hidden = !$("mcAnimateGif").checked;
  });
  ["mcAnimateDuration", "mcAnimateQuality"].forEach((name) => {
    document.querySelectorAll(`input[name=${name}]`).forEach((node) => {
      node.addEventListener("change", () => refreshQuote(context));
    });
  });
  $("mcAnimateCancel")?.addEventListener("click", () => dialog.close());
  $("mcAnimateSubmit")?.addEventListener("click", () => submit(context));
  bindLayers(context);
  document.querySelectorAll("input[name=mcAnimateSource]").forEach((node) => {
    node.addEventListener("change", () => refreshQuote(context));
  });
  $("mcAnimateToId")?.addEventListener("change", () => refreshQuote(context));
}

export async function openDialog(context) {
  const dialog = $("mcTrocrAnimate");
  if (!dialog) return;
  $("mcAnimateForm").classList.remove("hidden");
  $("mcAnimateProgress").classList.add("hidden");
  const linked = Boolean(window.__trocrAnimate?.camadasId?.());
  const protectedRadio = document.querySelector("input[name=mcAnimateSource][value=protected_scene]");
  const flatRadio = document.querySelector("input[name=mcAnimateSource][value=flattened_still]");
  if (linked && protectedRadio) protectedRadio.checked = true;
  else if (flatRadio) flatRadio.checked = true;
  const toSelect = $("mcAnimateToId");
  if (toSelect) delete toSelect.dataset.ready;
  $("mcAnimateLead").textContent = linked
    ? `${context.aspectRatio || "16:9"} · cena protegida`
    : `${context.aspectRatio || "16:9"} · still achatado`;
  await refreshLayers(context);
  await refreshQuote(context);
  dialog.showModal();
}

async function refreshQuote(context) {
  try {
    const quote = await quoteAnimate({ ...readForm(), ...context.ids() });
    const usd = quote.estimated_cost_usd ?? "—";
    const brl = quote.estimated_cost_brl ?? quote.spent_brl ?? "—";
    $("mcAnimateQuote").textContent = `Seedance 2.5 · US$ ${usd} · cerca de R$ ${brl} · 2 a 6 min`;
    if ($("mcAnimateWarn") && quote.warning) $("mcAnimateWarn").textContent = quote.warning;
  } catch (error) {
    $("mcAnimateQuote").textContent = error.message;
  }
}

async function submit(context) {
  $("mcAnimateForm").classList.add("hidden");
  $("mcAnimateProgress").classList.remove("hidden");
  $("mcAnimateClock").textContent = "0:00";
  try {
    const job = await submitAnimate({ ...readForm(), ...context.ids() });
    animateState.jobId = job.job_id;
    document.dispatchEvent(new CustomEvent("trocr:animate-started", { detail: job }));
    startPoll(job.job_id, (ready) => {
      document.dispatchEvent(new CustomEvent("trocr:animate-ready", { detail: ready }));
      $("mcTrocrAnimate")?.close();
    });
  } catch (error) {
    $("mcAnimateStatus").textContent = error.message;
  }
}

export async function cancelCurrent() {
  if (animateState.jobId) {
    await cancelAnimate(animateState.jobId).catch(() => {});
  }
}
