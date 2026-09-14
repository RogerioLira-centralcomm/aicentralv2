import { hideVideo, showVideo } from "../trocr/animate-player.js";
import { beatFor, state } from "./state.js";
import { escapeHtml, formatMoney, scriptText } from "./utils.js";

function $(id) {
  return document.getElementById(id);
}

export { showVideo as playClip, hideVideo as clearClip };

export function setStatus(message) {
  if ($("mcAnimateStatus")) $("mcAnimateStatus").textContent = message || "";
}

export function paintAll() {
  syncFormControls();
  paintLibrary();
  paintClips();
  paintProps();
  paintBeats();
  paintTimeline();
  paintCanvas();
  paintQuote();
  paintAudioRows();
  updateGenerateEnabled();
}

export function syncFormControls() {
  if ($("mcVideoName") && document.activeElement !== $("mcVideoName")) {
    $("mcVideoName").value = state.name || "";
  }
  if ($("mcVideoAspect")) $("mcVideoAspect").value = state.aspectRatio || "16:9";
  const duration = document.querySelector(`input[name="mcVideoDuration"][value="${state.duration}"]`);
  if (duration) duration.checked = true;
  const quality = document.querySelector(`input[name="mcVideoQuality"][value="${state.quality}"]`);
  if (quality) quality.checked = true;
  const audio = document.querySelector(`input[name="mcVideoAudio"][value="${state.audio.mode}"]`);
  if (audio) audio.checked = true;
  const voice = document.querySelector(`input[name="mcVideoVoiceGender"][value="${state.audio.voice}"]`);
  if (voice) voice.checked = true;
  const pace = document.querySelector(`input[name="mcVideoVoicePace"][value="${state.audio.pace}"]`);
  if (pace) pace.checked = true;
  const motion = document.querySelector(`input[name="mcVideoMotion"][value="${state.motion.preset}"]`);
  if (motion) motion.checked = true;
  if ($("mcVideoIntensity")) $("mcVideoIntensity").value = state.motion.intensity || "subtle";
  if ($("mcVideoMotionNote") && document.activeElement !== $("mcVideoMotionNote")) {
    $("mcVideoMotionNote").value = state.motion.note || "";
  }
  if ($("mcVideoVoicePrompt") && document.activeElement !== $("mcVideoVoicePrompt")) {
    $("mcVideoVoicePrompt").value = state.audio.prompt || "";
  }
  if ($("mcVideoVoiceover") && document.activeElement !== $("mcVideoVoiceover")) {
    $("mcVideoVoiceover").value = state.audio.script || "";
  }
  if ($("mcVideoMusic") && document.activeElement !== $("mcVideoMusic")) {
    $("mcVideoMusic").value = state.audio.music_note || "";
  }
  if ($("mcVideoScript") && document.activeElement !== $("mcVideoScript")) {
    $("mcVideoScript").value = state.script ? scriptText(state.script) : "";
  }
  if ($("mcVideoSearch") && document.activeElement !== $("mcVideoSearch")) {
    $("mcVideoSearch").value = state.search || "";
  }
  document.querySelectorAll("[data-lib-tab]").forEach((btn) => {
    const on = btn.getAttribute("data-lib-tab") === state.libTab;
    btn.classList.toggle("is-active", on);
    btn.setAttribute("aria-selected", on ? "true" : "false");
  });
  document.querySelectorAll("[data-panel-tab]").forEach((btn) => {
    const on = btn.getAttribute("data-panel-tab") === state.panelTab;
    btn.classList.toggle("is-active", on);
    btn.setAttribute("aria-selected", on ? "true" : "false");
  });
  document.querySelectorAll("[data-panel-pane]").forEach((pane) => {
    const on = pane.getAttribute("data-panel-pane") === state.panelTab;
    pane.hidden = !on;
    pane.classList.toggle("is-active", on);
  });
}

export function paintAudioRows() {
  const mode = state.audio.mode;
  if ($("mcVideoVoiceRow")) $("mcVideoVoiceRow").hidden = mode !== "voice";
  if ($("mcVideoVoiceoverRow")) $("mcVideoVoiceoverRow").hidden = mode !== "voiceover";
  if ($("mcVideoMusicRow")) $("mcVideoMusicRow").hidden = mode !== "music";
}

export function paintLibrary() {
  const list = $("mcVideoLibrary");
  const clips = $("mcVideoClips");
  if (!list || !clips) return;
  const stillMode = state.libTab !== "video";
  list.hidden = !stillMode;
  clips.hidden = stillMode;
  if (!stillMode) {
    paintClips();
    return;
  }
  const query = String(state.search || "").trim().toLowerCase();
  const rows = state.library.filter((item) => {
    if (!query) return true;
    return String(item.name || "").toLowerCase().includes(query)
      || String(item.headline || "").toLowerCase().includes(query);
  });
  list.innerHTML = rows.map((item) => {
    const selected = state.scenes.some((scene) => scene.id === item.id);
    const thumb = item.thumb_url || item.image_url;
    return `<li class="${item.broken ? "is-broken" : ""}" data-id="${escapeHtml(item.id)}">
      <button type="button" data-id="${escapeHtml(item.id)}" data-action="pick" class="${selected ? "is-selected" : ""}" ${item.broken ? "disabled" : ""}>
        ${thumb ? `<img src="${escapeHtml(thumb)}" alt="">` : "<span></span>"}
        <strong>${escapeHtml(item.name || "Peça")}</strong>
        ${item.broken ? "<small>404</small>" : ""}
      </button>
      <button type="button" class="mc-cadu-video-delete" data-id="${escapeHtml(item.id)}" data-action="delete">Apagar</button>
    </li>`;
  }).join("");
  list.querySelectorAll("img").forEach((img) => {
    img.addEventListener("error", () => {
      const id = img.closest("[data-id]")?.getAttribute("data-id");
      const item = state.library.find((row) => row.id === id);
      if (!item || item.broken) return;
      item.broken = true;
      paintLibrary();
      if ($("mcVideoLibHint")) $("mcVideoLibHint").textContent = libraryHint();
    });
  });
  paintPurge();
  if ($("mcVideoLibHint")) $("mcVideoLibHint").textContent = libraryHint();
}

export function libraryHint() {
  if (!state.clientId) return "Escolha a marca na barra para ver as peças.";
  if (state.libTab === "video") {
    if (!state.clips.length) return "Ainda não há clipe nesta marca.";
    return "Abra um clipe para restaurar cenas e roteiro.";
  }
  if (!state.library.length) return "Ainda não há peça nesta marca. Faça upload ou solte um still.";
  const broken = state.library.filter((item) => item.broken).length;
  if (broken) return `${broken} peça${broken === 1 ? "" : "s"} com 404. Apague ou crie uma nova.`;
  return "Clique para adicionar à timeline. A ordem é a do clipe.";
}

function paintPurge() {
  const broken = state.library.some((item) => item.broken);
  if ($("mcVideoPurgeBroken")) $("mcVideoPurgeBroken").hidden = !broken;
}

export function paintClips() {
  const list = $("mcVideoClips");
  if (!list) return;
  const query = String(state.search || "").trim().toLowerCase();
  const rows = state.clips.filter((item) => {
    if (!query) return true;
    return String(item.name || "").toLowerCase().includes(query);
  });
  list.innerHTML = rows.map((item) => {
    const current = item.id === state.activeClipId;
    const poster = item.poster_url || item.thumb_url || item.image_url || "";
    const seconds = Number(item.duration || 0);
    return `<li data-clip="${escapeHtml(item.id)}">
      <button type="button" data-clip="${escapeHtml(item.id)}" data-action="play" class="${current ? "is-current" : ""}">
        ${poster ? `<img src="${escapeHtml(poster)}" alt="">` : `<span class="mc-cadu-video-clip-ph"></span>`}
        <strong>${escapeHtml(item.name || "Clipe")}</strong>
        ${seconds ? `<small>${Math.round(seconds)}s</small>` : ""}
      </button>
      <button type="button" class="mc-cadu-video-delete" data-clip="${escapeHtml(item.id)}" data-action="delete">Apagar</button>
    </li>`;
  }).join("");
  if (state.libTab === "video" && $("mcVideoLibHint")) {
    $("mcVideoLibHint").textContent = libraryHint();
  }
}

export function paintProps() {
  const count = state.scenes.length;
  if ($("mcVideoSceneCount")) $("mcVideoSceneCount").textContent = String(count);
  const index = state.scenes.findIndex((item) => item.id === state.selectedSceneId);
  if ($("mcVideoSceneIndex")) {
    $("mcVideoSceneIndex").textContent = index >= 0 ? String(index + 1) : "—";
  }
  if ($("mcVideoSceneHint")) {
    $("mcVideoSceneHint").textContent = count < 2
      ? "Selecione pelo menos duas cenas."
      : count > 30
        ? "O Seedance aceita no máximo 30 cenas."
        : `${count} cenas na ordem do clipe.`;
  }
  const props = $("mcVideoProps");
  const scene = state.scenes[index];
  if (!props || !scene) {
    if (props) props.hidden = true;
    return;
  }
  props.hidden = false;
  const beat = beatFor(scene.id) || {};
  if ($("mcVideoBeatPurpose")) $("mcVideoBeatPurpose").value = beat.purpose || "beat";
  if ($("mcVideoBeatVisual") && document.activeElement !== $("mcVideoBeatVisual")) {
    $("mcVideoBeatVisual").value = beat.visual || "";
  }
  if ($("mcVideoBeatMotion") && document.activeElement !== $("mcVideoBeatMotion")) {
    $("mcVideoBeatMotion").value = beat.motion || "";
  }
  if ($("mcVideoBeatHold") && document.activeElement !== $("mcVideoBeatHold")) {
    $("mcVideoBeatHold").value = beat.hold || "";
  }
  if ($("mcVideoBeatSpoken") && document.activeElement !== $("mcVideoBeatSpoken")) {
    $("mcVideoBeatSpoken").value = beat.spoken || "";
  }
  if ($("mcVideoScriptBtn")) $("mcVideoScriptBtn").disabled = count < 2 || count > 30;
}

export function paintBeats() {
  const host = $("mcVideoBeats");
  if (!host) return;
  const beats = (state.script || {}).beats || [];
  if (!beats.length) {
    host.innerHTML = `<p class="mc-cadu-video-hint">Monte o roteiro com IA ou edite o texto completo abaixo.</p>`;
    return;
  }
  host.innerHTML = beats.map((beat, index) => {
    const active = beat.id === state.selectedSceneId;
    return `<article class="mc-cadu-video-beat ${active ? "is-active" : ""}" data-scene="${escapeHtml(beat.id)}">
      <strong>Cena ${index + 1} — ${escapeHtml(beat.purpose || "beat")}</strong>
      <small>${escapeHtml(beat.visual || "Sem visual")}</small>
      ${beat.spoken ? `<small>Fala: ${escapeHtml(beat.spoken)}</small>` : ""}
    </article>`;
  }).join("");
}

export function paintTimeline() {
  const video = $("mcVideoTrackVideo");
  const text = $("mcVideoTrackText");
  const audio = $("mcVideoTrackAudio");
  const elements = $("mcVideoTrackElements");
  if (!video || !text || !audio || !elements) return;
  const total = Math.max(state.scenes.length, 1);
  video.innerHTML = state.scenes.map((scene, index) => {
    const thumb = scene.thumb_url || scene.image_url || "";
    const active = scene.id === state.selectedSceneId;
    return `<button type="button" class="mc-cadu-video-block ${active ? "is-active" : ""}" draggable="true" data-scene="${escapeHtml(scene.id)}" data-index="${index}">
      ${thumb ? `<img src="${escapeHtml(thumb)}" alt="">` : `<span class="mc-cadu-video-block-ph"></span>`}
      <strong>${escapeHtml(scene.name || `Cena ${index + 1}`)}</strong>
      <small>${Math.round(state.duration / total)}s</small>
    </button>`;
  }).join("");
  text.innerHTML = state.scenes.map((scene, index) => {
    const beat = beatFor(scene.id);
    const label = beat?.visual || scene.headline || scene.name || `Cena ${index + 1}`;
    const active = scene.id === state.selectedSceneId;
    return `<button type="button" class="mc-cadu-video-block ${active ? "is-active" : ""}" data-scene="${escapeHtml(scene.id)}">
      <strong>${escapeHtml(label)}</strong>
      <small>${escapeHtml(beat?.purpose || "texto")}</small>
    </button>`;
  }).join("");
  const spoken = spokenFromBeatsSafe();
  if (state.audio.mode === "voiceover" && (state.audio.script || spoken)) {
    audio.innerHTML = `<div class="mc-cadu-video-block" data-kind="audio">
      <strong>Locução</strong>
      <small>${escapeHtml((state.audio.script || spoken).slice(0, 48))}</small>
    </div>`;
  } else if (state.audio.mode === "silence") {
    audio.innerHTML = `<div class="mc-cadu-video-block" data-kind="audio"><strong>Silêncio</strong><small>—</small></div>`;
  } else {
    audio.innerHTML = `<div class="mc-cadu-video-block" data-kind="audio"><strong>${escapeHtml(state.audio.mode)}</strong><small>no plano</small></div>`;
  }
  elements.innerHTML = state.scenes.map((scene) => {
    const beat = beatFor(scene.id);
    const hold = beat?.hold || (scene.ocr?.logo_text || scene.ocr?.price || "");
    const active = scene.id === state.selectedSceneId;
    return `<button type="button" class="mc-cadu-video-block ${active ? "is-active" : ""}" data-scene="${escapeHtml(scene.id)}">
      <strong>${escapeHtml(hold || "—")}</strong>
      <small>trava</small>
    </button>`;
  }).join("");
  if ($("mcVideoTimelineHint")) {
    $("mcVideoTimelineHint").textContent = state.scenes.length
      ? "Arraste na faixa Vídeo para reordenar. Sem corte — o Seedance gera um clipe único."
      : "Adicione peças na biblioteca para montar a timeline.";
  }
}

function spokenFromBeatsSafe() {
  return ((state.script || {}).beats || [])
    .map((beat) => String(beat.spoken || "").trim())
    .filter(Boolean)
    .join(" ");
}

export function paintCanvas() {
  const still = $("mcVideoStill");
  const empty = $("mcVideoEmpty");
  const video = $("mcSwapVideo");
  const selected = state.scenes.find((item) => item.id === state.selectedSceneId) || state.scenes[0];
  const index = selected ? state.scenes.findIndex((item) => item.id === selected.id) + 1 : 0;
  if ($("mcVideoStageMeta")) {
    if (state.activeClipId && video && !video.hidden && video.getAttribute("src")) {
      $("mcVideoStageMeta").textContent = "Clipe gerado";
    } else if (selected) {
      $("mcVideoStageMeta").textContent = `Cena ${index} · ${selected.name || "peça"}`;
    } else {
      $("mcVideoStageMeta").textContent = "Cena —";
    }
  }
  if (state.activeClipId && video && video.getAttribute("src") && !video.hidden) {
    if (still) still.hidden = true;
    if (empty) empty.hidden = true;
    return;
  }
  if (selected) {
    const src = selected.image_url || selected.thumb_url || "";
    if (still && src) {
      still.src = src;
      still.hidden = false;
    } else if (still) {
      still.hidden = true;
    }
    if (video) video.hidden = true;
    if (empty) empty.hidden = true;
    return;
  }
  if (still) still.hidden = true;
  if (video) video.hidden = true;
  if (empty) empty.hidden = false;
}

export function paintQuote() {
  const node = $("mcVideoQuote");
  if (!node) return;
  if (state.quoteError) {
    node.textContent = state.quoteError;
    return;
  }
  if (state.quote) {
    const warning = state.quote.warning ? ` · ${state.quote.warning}` : "";
    node.textContent = `${formatMoney(state.quote)}${warning}`.slice(0, 160);
    return;
  }
  node.textContent = state.scenes.length >= 2 ? "Cotando…" : "Monte duas cenas para cotar.";
}

export function updateGenerateEnabled() {
  const ready = state.scenes.length >= 2
    && state.scenes.length <= 30
    && Boolean(state.script?.beats?.length)
    && !state.quoteError;
  if ($("mcVideoGenerate")) $("mcVideoGenerate").disabled = !ready;
}

export function syncPlayhead() {
  const head = $("mcVideoPlayhead");
  const video = $("mcSwapVideo");
  const timeline = document.querySelector(".mc-cadu-video-timeline");
  if (!head || !video || !timeline || video.hidden || !video.duration) {
    if (head) head.hidden = true;
    return;
  }
  head.hidden = false;
  const lane = $("mcVideoTrackVideo");
  if (!lane) return;
  const rect = lane.getBoundingClientRect();
  const root = timeline.getBoundingClientRect();
  const ratio = Math.min(1, Math.max(0, video.currentTime / video.duration));
  const left = rect.left - root.left + rect.width * ratio;
  head.style.left = `${left}px`;
}
