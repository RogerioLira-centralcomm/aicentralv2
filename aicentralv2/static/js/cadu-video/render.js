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
  paintTimeline();
  paintCanvas();
  paintQuote();
  paintSaveStatus();
  paintAudioRows();
  updateGenerateEnabled();
  document.dispatchEvent(new Event("cadu:studio-paint"));
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
    btn.tabIndex = on ? 0 : -1;
  });
  document.querySelectorAll("[data-panel-tab]").forEach((btn) => {
    const on = btn.getAttribute("data-panel-tab") === state.panelTab;
    btn.classList.toggle("is-active", on);
    btn.setAttribute("aria-selected", on ? "true" : "false");
    btn.tabIndex = on ? 0 : -1;
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
  const stillMode = state.libTab === "still";
  list.hidden = !stillMode;
  clips.hidden = state.libTab !== "video";
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
        ${thumb ? `<img loading="lazy" decoding="async" src="${escapeHtml(thumb)}" alt="">` : "<span></span>"}
        <strong>${escapeHtml(item.name || "Peça")}</strong>
        <small>${item.broken ? "Arquivo indisponível" : selected ? "Na sequência" : "Adicionar cena"}</small>
      </button>
      <button type="button" class="mc-cadu-video-delete" data-id="${escapeHtml(item.id)}" data-action="delete">Excluir da biblioteca</button>
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
  if (!state.library.length) return "Ainda não há peças nesta marca. Envie uma imagem para começar.";
  if (state.search && !state.library.some((item) => String(item.name || "").toLowerCase().includes(state.search.toLowerCase()))) return "Nenhuma peça corresponde à busca.";
  const broken = state.library.filter((item) => item.broken).length;
  if (broken) return `${broken} arquivo${broken === 1 ? " está" : "s estão"} indisponível${broken === 1 ? "" : "is"}.`;
  return "Adicione peças e organize a ordem do clipe.";
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
        ${poster ? `<img loading="lazy" decoding="async" src="${escapeHtml(poster)}" alt="">` : `<span class="mc-cadu-video-clip-ph"></span>`}
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
      ? "Adicione pelo menos duas cenas."
      : count > 30
        ? "O clipe aceita no máximo 30 cenas."
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
  if ($("mcVideoMoveBefore")) $("mcVideoMoveBefore").disabled = index <= 0;
  if ($("mcVideoMoveAfter")) $("mcVideoMoveAfter").disabled = index < 0 || index >= count - 1;
}

export function paintTimeline() {
  const video = $("mcVideoScenes");
  if (!video) return;
  video.innerHTML = state.scenes.map((scene, index) => {
    const thumb = scene.thumb_url || scene.image_url || "";
    const active = scene.id === state.selectedSceneId;
    return `<button type="button" class="mc-cadu-video-block ${active ? "is-active" : ""}" draggable="true" data-scene="${escapeHtml(scene.id)}" data-index="${index}">
      ${thumb ? `<img loading="lazy" decoding="async" src="${escapeHtml(thumb)}" alt="">` : `<span class="mc-cadu-video-block-ph"></span>`}
      <small>Cena ${index + 1}</small>
      <strong>${escapeHtml(scene.name || `Cena ${index + 1}`)}</strong>
    </button>`;
  }).join("");
  if ($("mcVideoTimelineHint")) {
    $("mcVideoTimelineHint").textContent = state.scenes.length
      ? "Arraste para reordenar ou use os comandos da cena."
      : "Adicione peças da biblioteca para começar.";
  }
}

export function paintCanvas() {
  const still = $("mcVideoStill");
  const empty = $("mcVideoEmpty");
  const video = $("mcSwapVideo");
  const selected = state.scenes.find((item) => item.id === state.selectedSceneId) || state.scenes[0];
  const index = selected ? state.scenes.findIndex((item) => item.id === selected.id) + 1 : 0;
  if ($("mcVideoStageMeta")) {
    if (state.previewMode === "clip" && state.activeClipId && video?.getAttribute("src")) {
      $("mcVideoStageMeta").textContent = "Clipe gerado";
    } else if (selected) {
      $("mcVideoStageMeta").textContent = `Cena ${index} · ${selected.name || "peça"}`;
    } else {
      $("mcVideoStageMeta").textContent = "Cena —";
    }
  }
  const showClip = state.previewMode === "clip" && state.activeClipId && video?.getAttribute("src");
  document.querySelectorAll("[data-preview-mode]").forEach((button) => {
    const active = button.dataset.previewMode === state.previewMode;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", active ? "true" : "false");
    if (button.dataset.previewMode === "clip") button.disabled = !state.activeClipId || !video?.getAttribute("src");
  });
  if (showClip) {
    video.hidden = false;
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
  if (state.quoteStatus === "loading") {
    node.textContent = "Calculando custo…";
    return;
  }
  if (state.quote) {
    const warning = state.quote.warning ? ` · ${state.quote.warning}` : "";
    node.textContent = `${formatMoney(state.quote)}${warning}`.slice(0, 160);
    return;
  }
  node.textContent = state.scenes.length >= 2 ? "Custo pendente" : "Adicione duas cenas para calcular o custo.";
}

export function paintSaveStatus() {
  const node = $("mcVideoSaveStatus");
  if (!node) return;
  node.textContent = ({ pending: "Alterações pendentes", saving: "Salvando…", saved: "Salvo", error: "Falha ao salvar — tentar novamente" })[state.saveStatus] || "Salvo";
  node.classList.toggle("is-error", state.saveStatus === "error");
}

export function updateGenerateEnabled() {
  const ready = state.scenes.length >= 2
    && state.scenes.length <= 30
    && Boolean(state.script?.beats?.length)
    && !state.quoteError && state.quoteStatus === "ready" && !state.generating;
  const button = $("mcVideoGenerate");
  if (!button) return;
  button.disabled = !ready;
  const reason = !state.clientId ? "Escolha uma marca" : state.scenes.length < 2 ? "Adicione duas cenas" : !state.script?.beats?.length ? "Monte o roteiro" : state.quoteError ? state.quoteError : state.quoteStatus !== "ready" ? "Aguarde o cálculo do custo" : state.generating ? "Gerando clipe" : "";
  button.title = reason;
  button.setAttribute("aria-label", reason ? `Gerar clipe: ${reason}` : "Gerar clipe");
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
  const lane = $("mcVideoScenes");
  if (!lane) return;
  const rect = lane.getBoundingClientRect();
  const root = timeline.getBoundingClientRect();
  const ratio = Math.min(1, Math.max(0, video.currentTime / video.duration));
  const left = rect.left - root.left + rect.width * ratio;
  head.style.left = `${left}px`;
}
