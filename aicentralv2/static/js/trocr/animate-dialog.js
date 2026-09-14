import { cancelAnimate, quoteAnimate, submitAnimate } from "./animate-api.js";
import { bindLayers, layerIntents, refreshLayers, selectedExtendId, selectedRefIds, selectedToId, sourceMode } from "./animate-layers.js";
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
      script: $("mcAnimateVoiceover")?.value || "",
      voice: document.querySelector("input[name=mcAnimateVoiceGender]:checked")?.value || "male",
      pace: document.querySelector("input[name=mcAnimateVoicePace]:checked")?.value || "normal",
    },
    delivery,
    gif_window: document.querySelector("input[name=mcAnimateGifWindow]:checked")?.value || "first",
    source: {
      mode: sourceMode(),
      to_id: selectedToId(),
      ref_ids: selectedRefIds(),
      extended_from: selectedExtendId(),
    },
    to_id: selectedToId(),
    extra_ids: sourceMode() === "storyboard" ? selectedRefIds() : (selectedToId() ? [selectedToId()] : []),
    ref_ids: selectedRefIds(),
    extended_from: selectedExtendId(),
    layer_intents: layerIntents(),
    camadas_creative_id: window.__trocrAnimate?.camadasId?.() || "",
  };
}

export function bindDialog(context) {
  if (!$("mcTrocrAnimate") || !$("mcAnimateForm")) return;
  document.querySelectorAll("input[name=mcAnimateAudio]").forEach((node) => {
    node.addEventListener("change", () => {
      const mode = document.querySelector("input[name=mcAnimateAudio]:checked")?.value;
      $("mcAnimateVoiceRow").hidden = mode !== "voice";
      $("mcAnimateMusicRow").hidden = mode !== "music";
      $("mcAnimateVoiceoverRow").hidden = mode !== "voiceover";
      refreshQuote(context);
    });
  });
  $("mcAnimateGif")?.addEventListener("change", () => {
    $("mcAnimateGifWindow").hidden = !$("mcAnimateGif").checked;
  });
  ["mcAnimateDuration", "mcAnimateQuality", "mcAnimateVoiceGender", "mcAnimateVoicePace"].forEach((name) => {
    document.querySelectorAll(`input[name=${name}]`).forEach((node) => {
      node.addEventListener("change", () => refreshQuote(context));
    });
  });
  $("mcAnimateVoiceover")?.addEventListener("input", () => refreshQuote(context));
  $("mcAnimateCancel")?.addEventListener("click", () => {
    window.__trocrAnimate?.setWorkspace?.("still");
  });
  $("mcAnimateAbort")?.addEventListener("click", async () => {
    await cancelCurrent();
    $("mcAnimateStatus").textContent = "Geração cancelada.";
  });
  $("mcAnimateSubmit")?.addEventListener("click", () => submit(context));
  bindLayers(context);
  document.querySelectorAll("input[name=mcAnimateSource]").forEach((node) => {
    node.addEventListener("change", () => refreshQuote(context));
  });
  $("mcAnimateToId")?.addEventListener("change", () => refreshQuote(context));
  $("mcAnimateExtendId")?.addEventListener("change", () => refreshQuote(context));
  document.addEventListener("trocr:animate-source", () => refreshQuote(context));
}

export async function openDialog(context) {
  if (!$("mcAnimateForm")) return;
  $("mcAnimateForm").classList.remove("hidden");
  $("mcAnimateProgress").classList.add("hidden");
  const linked = Boolean(window.__trocrAnimate?.camadasId?.());
  const hasStill = Boolean(window.__trocrAnimate?.activeStill?.()?.image);
  const protectedRadio = document.querySelector("input[name=mcAnimateSource][value=protected_scene]");
  const flatRadio = document.querySelector("input[name=mcAnimateSource][value=flattened_still]");
  if (linked && protectedRadio) protectedRadio.checked = true;
  else if (flatRadio) flatRadio.checked = true;
  const toSelect = $("mcAnimateToId");
  if (toSelect) delete toSelect.dataset.ready;
  const ratio = context.aspectRatio || "16:9";
  const surface = ratio === "1:1" ? "display 1:1" : ratio;
  if ($("mcAnimateLead")) {
    if (!hasStill) $("mcAnimateLead").textContent = "Envie um still na aba Still para gerar o clipe.";
    else if (linked) $("mcAnimateLead").textContent = `${surface} · cena protegida`;
    else $("mcAnimateLead").textContent = `${surface} · still achatado`;
  }
  await refreshLayers(context);
  await refreshQuote(context);
}

async function refreshQuote(context) {
  try {
    const quote = await quoteAnimate({ ...readForm(), ...context.ids() });
    const usd = quote.estimated_cost_usd ?? "—";
    const brl = quote.estimated_cost_brl ?? quote.spent_brl ?? "—";
    const tts = quote.tts_estimated_cost_usd;
    const ttsBit = tts != null && tts !== "" ? ` · locução US$ ${tts}` : "";
    $("mcAnimateQuote").textContent = `Vídeo · US$ ${usd}${ttsBit} · cerca de R$ ${brl} · 2 a 6 min`;
    if ($("mcAnimateWarn") && quote.warning) $("mcAnimateWarn").textContent = quote.warning;
    if ($("mcAnimateVoiceoverHint") && quote.voiceover_words != null) {
      const fits = quote.voiceover_fits !== false;
      $("mcAnimateVoiceoverHint").textContent = fits
        ? `${quote.voiceover_words} palavras · cabem em cerca de ${quote.voiceover_budget || "—"}`
        : `${quote.voiceover_words} palavras · acima de ${quote.voiceover_budget || "—"} para esta duração`;
    }
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
      $("mcAnimateForm")?.classList.remove("hidden");
      $("mcAnimateProgress")?.classList.add("hidden");
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
