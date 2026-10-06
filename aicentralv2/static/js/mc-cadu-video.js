import {showProcessing,updateProcessing,followingJob} from './media-progress.js';
import {sourceAspect} from './cadu-video/aspect.js';
import { bindStudio, resetStudio, recordStudioChange, defaultEdit, paintStudio, resetClipHistory, showSavedAgentPlan } from "./cadu-video/studio.js";
import { quoteAnimate, submitAnimate } from "./trocr/animate-api.js";
import { startPoll } from "./trocr/animate-poller.js";
import { deleteLibrary, get, loadVideoProject, post, saveVideoProject, studioApi, swapApi } from "./cadu-video/api.js?v=2";
import {
  clearClip,
  currentIssues,
  paintAll,
  paintCanvas,
  paintClips,
  paintDraft,
  paintLibrary,
  paintProps,
  paintQuote,
  paintSaveStatus,
  paintTimeline,
  playClip,
  setStatus,
  syncPlayhead,
  updateGenerateEnabled,
} from "./cadu-video/render.js";
import {
  JOB_KEY,
  Desk,
  alignBeatsToScenes,
  beatFor,
  ensureBeat,
  normalizeAudioState,
  normalizeWorkspaceSpend,
  resetProjectFields,
  spokenFromBeats,
  state,
  syncAudioMode,
  upsertWorkspaceSpend,
} from "./cadu-video/state.js";
import { newId, scriptText } from "./cadu-video/utils.js";

let quoteTimer = null;
let saveTimer = null;
let quoteRequest = 0;
let saveRequest = 0;
let narrationRequest = 0;

boot();

async function boot() {
  if (!document.getElementById("mcSwap")?.classList.contains("mc-cadu-video")) return;
  const params = new URLSearchParams(window.location.search);
  state.activeClipId = params.get("clip") || "";
  bindUi();
  bindStudio(markDirty, paintAll);
  document.addEventListener('cadu:resume-job',event=>{if(!state.generating){state.jobId=event.detail.job_id;resume(state.jobId);}});
  document.addEventListener('cadu:job-open',async event=>{
    if(String(event.detail.client_id)!==String(state.clientId))return;
    await loadClips({prefer:event.detail.version,restore:false});
  });
  document.addEventListener("cadu:brand-ready", (event) => applyBrand(event.detail?.clientId));
  document.addEventListener("cadu:brand-change", (event) => {
    applyBrand(event.detail?.clientId, { reset: true });
  });
  const linkedClient = params.get("creative_client_id") || params.get("client") || Desk.read();
  await applyBrand(linkedClient);
  const linkedSessionId = String(params.get("studio_session_id") || "").trim();
  if (linkedSessionId && /^\d+$/.test(String(linkedClient || ""))) {
    try {
      const saved = await get(`${studioApi}/sessions/${encodeURIComponent(linkedSessionId)}?client_id=${encodeURIComponent(linkedClient)}`);
      const session = saved?.data || saved;
      const prompt = String(session?.original_prompt || "").trim();
      if (prompt) {
        const field = document.getElementById("mcStudioAgentPrompt");
        if (field) field.value = prompt.slice(0, 2000);
        document.getElementById("mcVideoAgentTab")?.click();
        const status = document.getElementById("mcStudioAgentStatus");
        if (status) status.textContent = "Pedido recuperado da sessão. Revise o plano antes de gerar ou editar o vídeo.";
      }
      if (session?.metadata?.video_plan) showSavedAgentPlan(session.metadata.video_plan);
    } catch (_) {
      const status = document.getElementById("mcStudioAgentStatus");
      if (status) status.textContent = "Não foi possível recuperar esta sessão. O Studio continua disponível para uma nova criação.";
    }
  }
  adoptHandoffScenes(params);
  const pending = sessionStorage.getItem(JOB_KEY);
  if (pending && !state.generating) resume(pending);
}

function adoptHandoffScenes(params) {
  const ids = String(params.get("scenes") || "").split(",").map((id) => id.trim()).filter(Boolean).slice(0, 30);
  if (!ids.length) return;
  const scenes = ids.map((id) => state.library.find((item) => item.id === id)).filter((item) => item && !item.broken);
  const clean = new URL(window.location.href);
  clean.searchParams.delete("scenes");
  clean.searchParams.delete("from");
  window.history.replaceState(null, "", clean.toString());
  if (!scenes.length) {
    setStatus("As imagens enviadas pelo Criar ainda não apareceram na biblioteca. Atualize a página.");
    return;
  }
  state.scenes = scenes;
  state.selectedSceneId = scenes[0].id;
  state.generationMode = scenes.length > 1 ? "storyboard" : "single_image";
  if (state.generationMode === "single_image") adoptSelectedAspect(scenes[0]);
  alignBeatsToScenes();
  state.previewMode = "scene";
  paintAll();
  markDirty();
  scheduleQuote();
  setStatus(scenes.length > 1
    ? `${scenes.length} cenas vieram do Criar e já estão no storyboard, na ordem escolhida.`
    : "A imagem do Criar já está pronta para animar.");
}

function bindUi() {
  document.getElementById("mcStudioProjectAspect")?.addEventListener("change",event=>{
    const input=document.getElementById("mcVideoAspect");input.value=event.target.value;input.dispatchEvent(new Event("change"));
  });
  document.getElementById("mcVideoFile")?.addEventListener("change", (event) => {
    takeFile(event.target.files?.[0]);
  });
  bindDrop(document.getElementById("mcVideoLibDrop"));
  document.getElementById("mcVideoLibrary")?.addEventListener("click", onLibraryClick);
  document.getElementById("mcVideoClips")?.addEventListener("click", onClipClick);
  document.getElementById("mcVideoScriptBtn")?.addEventListener("click", buildScript);
  document.getElementById("mcVideoCreateScene2")?.addEventListener("click", createNextSceneWithTrocr);
  document.getElementById("mcVideoGenerate")?.addEventListener("click", generate);
  document.getElementById("mcVideoSaveStatus")?.addEventListener("click", () => {
    if (state.saveStatus === "error") persistProject();
  });
  document.getElementById("mcVideoPurgeBroken")?.addEventListener("click", purgeBroken);
  document.getElementById("mcVideoPrevScene")?.addEventListener("click", () => stepScene(-1));
  document.getElementById("mcVideoNextScene")?.addEventListener("click", () => stepScene(1));
  document.getElementById("mcVideoRemoveScene")?.addEventListener("click", removeSelectedScene);
  document.getElementById("mcVideoMoveBefore")?.addEventListener("click", () => moveSelectedScene(-1));
  document.getElementById("mcVideoMoveAfter")?.addEventListener("click", () => moveSelectedScene(1));
  document.querySelectorAll("[data-preview-mode]").forEach((button) => {
    button.addEventListener("click", () => {
      if (button.dataset.previewMode === "clip" && !state.activeClipId) return;
      state.previewMode = button.dataset.previewMode || "scene";
      paintCanvas();
      paintStudio();
    });
  });
  document.getElementById("mcVideoSearch")?.addEventListener("input", (event) => {
    state.search = event.target.value || "";
    paintLibrary();
    paintClips();
    paintStudio();
  });
  document.getElementById("mcVideoName")?.addEventListener("input", (event) => {
    state.name = event.target.value || "";
    markDirty();
  });
  document.getElementById("mcStudioProjectSelect")?.addEventListener("change", async (event) => {
    const projectId = event.target.value;
    if (!projectId || projectId === state.projectId) return;
    await openProject(projectId);
  });
  document.getElementById("mcStudioNewProject")?.addEventListener("click", newProject);
  document.getElementById("mcVideoAspect")?.addEventListener("change", (event) => {
    state.aspectRatio = event.target.value || "16:9";
    state.aspectExplicit = true;
    markDirty();
    scheduleQuote();
  });
  document.querySelectorAll('input[name="mcVideoSource"]').forEach((input) => {
    input.addEventListener("change", () => {
      state.generationMode = input.value === "single_image" ? "single_image" : "storyboard";
      if (state.generationMode === "single_image") {
        state.quality = "production";
        state.seed = null;
        adoptSelectedAspect();
      }
      markDirty();
      scheduleQuote();
      paintAll();
    });
  });
  document.querySelectorAll('input[name="mcVideoDuration"]').forEach((input) => {
    input.addEventListener("change", () => {
      state.duration = Number(input.value || 8);
      markDirty();
      scheduleQuote();
      paintTimeline();
    });
  });
  document.querySelectorAll('input[name="mcVideoQuality"]').forEach((input) => {
    input.addEventListener("change", () => {
      state.quality = input.value || "draft";
      markDirty();
      scheduleQuote();
    });
  });
  document.querySelectorAll('input[name="mcVideoAudioEnabled"]').forEach((input) => {
    input.addEventListener("change", () => {
      state.audio.enabled = input.value === "on";
      if (state.audio.enabled && !state.audio.ambience && !state.audio.music_enabled && state.audio.narration_mode === "none") {
        state.audio.ambience = true;
      }
      syncAudioMode(state.audio);
      markDirty();
      scheduleQuote();
      paintAll();
    });
  });
  document.querySelectorAll('input[name="mcVideoNarration"]').forEach((input) => {
    input.addEventListener("change", () => {
      state.audio.narration_mode = input.value || "none";
      if (state.audio.narration_mode === "voiceover" && !state.audio.script) {
        state.audio.script = spokenFromBeats();
      }
      syncAudioMode(state.audio);
      markDirty();
      scheduleQuote();
      paintAll();
    });
  });
  document.getElementById("mcVideoAmbience")?.addEventListener("change", (event) => {
    state.audio.ambience = event.target.checked;
    syncAudioMode(state.audio);
    markDirty();
    scheduleQuote();
    paintAll();
  });
  document.getElementById("mcVideoMusicEnabled")?.addEventListener("change", (event) => {
    state.audio.music_enabled = event.target.checked;
    syncAudioMode(state.audio);
    markDirty();
    scheduleQuote();
    paintAll();
  });
  document.querySelectorAll('input[name="mcVideoVoiceGender"]').forEach((input) => {
    input.addEventListener("change", () => {
      state.audio.voice = input.value || "male";
      markDirty();
      scheduleQuote();
    });
  });
  document.querySelectorAll('input[name="mcVideoVoicePace"]').forEach((input) => {
    input.addEventListener("change", () => {
      state.audio.pace = input.value || "normal";
      markDirty();
      scheduleQuote();
    });
  });
  document.querySelectorAll('input[name="mcVideoMotion"]').forEach((input) => {
    input.addEventListener("change", () => {
      state.motion.preset = input.value || "live";
      markDirty();
      scheduleQuote();
    });
  });
  document.getElementById("mcVideoIntensity")?.addEventListener("change", (event) => {
    state.motion.intensity = event.target.value || "subtle";
    markDirty();
    scheduleQuote();
  });
  document.getElementById("mcVideoMotionNote")?.addEventListener("input", (event) => {
    state.motion.note = event.target.value || "";
    markDirty();
  });
  document.getElementById("mcVideoVoicePrompt")?.addEventListener("input", (event) => {
    state.audio.prompt = event.target.value || "";
    markDirty();
  });
  document.getElementById("mcVideoAmbienceNote")?.addEventListener("input", (event) => {
    state.audio.ambience_note = event.target.value || "";
    markDirty();
  });
  document.getElementById("mcVideoVoiceover")?.addEventListener("input", (event) => {
    state.audio.script = event.target.value || "";
    markDirty();
    scheduleQuote();
    paintTimeline();
  });
  document.getElementById("mcVideoMusic")?.addEventListener("input", (event) => {
    state.audio.music_note = event.target.value || "";
    markDirty();
  });
  document.getElementById("mcVideoMusicPreset")?.addEventListener("change", (event) => {
    if (event.target.value) state.audio.music_note = event.target.value;
    markDirty();
    paintAll();
  });
  document.getElementById("mcVideoSuggestNarration")?.addEventListener("click", () => suggestNarration("guided"));
  document.getElementById("mcVideoSuggestVoiceover")?.addEventListener("click", () => suggestNarration("voiceover"));
  document.getElementById("mcVideoSceneCards")?.addEventListener("click", onSceneCardClick);
  document.getElementById("mcVideoChecks")?.addEventListener("click", (event) => {
    const target = event.target.closest("[data-check-scene]");
    if (target) selectScene(target.getAttribute("data-check-scene"));
  });
  document.getElementById("mcVideoDraftBtn")?.addEventListener("click", buildDraft);
  document.getElementById("mcVideoBriefing")?.addEventListener("input", (event) => {
    state.draft.briefing = event.target.value;
    markDirty();
  });
  document.getElementById("mcVideoDraftGenerate")?.addEventListener("click", generateAllDraftImages);
  document.getElementById("mcVideoDraftStop")?.addEventListener("click", () => { state.draft.stopRequested = true; });
  const draftList = document.getElementById("mcVideoDraft");
  draftList?.addEventListener("click", onDraftClick);
  draftList?.addEventListener("input", onDraftField);
  draftList?.addEventListener("change", onDraftField);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && (state.replaceSceneId || state.pickDraftId)) cancelReplace();
  });
  ["mcVideoBeatTransition", "mcVideoBeatPurpose", "mcVideoBeatVisual", "mcVideoBeatMotion", "mcVideoBeatHold", "mcVideoBeatSpoken"]
    .forEach((id) => {
      document.getElementById(id)?.addEventListener("input", onBeatField);
      document.getElementById(id)?.addEventListener("change", onBeatField);
    });
  document.querySelectorAll("[data-lib-tab]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.libTab = btn.getAttribute("data-lib-tab") || "still";
      paintAll();
    });
  });
  document.querySelectorAll("[data-panel-tab]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.panelTab = btn.getAttribute("data-panel-tab") || "scene";
      paintAll();
      document.querySelector(".mc-cadu-video-desk")?.scrollTo({ top: 0, behavior: "auto" });
    });
  });
  document.querySelectorAll('[role="tablist"]').forEach((tablist) => {
    tablist.addEventListener("keydown", (event) => {
      if (!["ArrowLeft", "ArrowRight"].includes(event.key)) return;
      const tabs = [...tablist.querySelectorAll('[role="tab"]')];
      const current = tabs.indexOf(document.activeElement);
      if (current < 0) return;
      event.preventDefault();
      tabs[(current + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length].click();
      tabs[(current + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length].focus();
    });
  });
  bindTimelineDrag(document.getElementById("mcVideoScenes"));
  document.getElementById("mcVideoScenes")?.addEventListener("click", (event) => {
    const remove = event.target.closest("[data-scene-remove]");
    if (remove) {
      event.preventDefault();
      state.selectedSceneId = remove.getAttribute("data-scene-remove") || "";
      removeSelectedScene();
      return;
    }
    const node = event.target.closest("[data-scene]");
    if (!node) return;
    selectScene(node.getAttribute("data-scene"));
  });
  document.getElementById("mcStudioAddAudio")?.addEventListener("click", () => {
    state.libTab = "sound";
    paintAll();
    document.querySelector(".mc-cadu-video-lib")?.scrollTo({ top: 0, behavior: "auto" });
  });
  const video = document.getElementById("mcSwapVideo");
  video?.addEventListener("timeupdate", syncPlayhead);
  video?.addEventListener("play", syncPlayhead);
  video?.addEventListener("pause", syncPlayhead);
}

function onBeatField() {
  if (!state.selectedSceneId) return;
  const beat = ensureBeat(state.selectedSceneId);
  beat.purpose = document.getElementById("mcVideoBeatPurpose")?.value || beat.purpose;
  beat.visual = document.getElementById("mcVideoBeatVisual")?.value || "";
  beat.transition = document.getElementById("mcVideoBeatTransition")?.value || "cut";
  beat.motion = document.getElementById("mcVideoBeatMotion")?.value || "";
  beat.hold = document.getElementById("mcVideoBeatHold")?.value || "";
  beat.spoken = document.getElementById("mcVideoBeatSpoken")?.value || "";
  if (state.audio.narration_mode === "voiceover") {
    state.audio.script = spokenFromBeats();
  }
  const scriptNode = document.getElementById("mcVideoScript");
  if (scriptNode && document.activeElement !== scriptNode) {
    scriptNode.value = scriptText(state.script);
  }
  markDirty();
  scheduleQuote();
  paintProps();
  paintTimeline();
  paintQuote();
}

function currentBrand(id) {
  return String(id || Desk.read() || document.getElementById("mcCaduBarClient")?.value || "").trim();
}

async function applyBrand(id, { reset = false } = {}) {
  const next = currentBrand(id);
  if (!next) {
    state.clientId = "";
    state.projectId = "";
    state.projects = [];
    resetProjectFields();
    state.library = [];
    state.clips = [];
    state.edit = defaultEdit();
    clearClip();
    await resetStudio();
    paintAll();
    return;
  }
  if (next === state.clientId && !reset) {
    if (!state.library.length) await loadLibrary();
    if (!state.clips.length) await loadClips();
    return;
  }
  clearTimeout(saveTimer);
  clearTimeout(quoteTimer);
  saveRequest += 1;
  state.saving = false;
  state.clientId = next;
  state.projectId = "";
  state.projects = [];
  resetProjectFields();
  state.edit = defaultEdit();
  clearClip();
  await Promise.all([loadLibrary(), loadClips()]);
  if (state.clientId !== next) return;
  await restoreProject();
  if (state.clientId !== next) return;
  await resetStudio();
  paintAll();
  scheduleQuote();
}

async function restoreProject() {
  if (!state.clientId) return;
  const clientId = state.clientId;
  try {
    const data = await loadVideoProject(clientId);
    if (clientId !== state.clientId) return;
    state.projects = data.items || [];
    state.projectId = data.activeId || "";
    applyProject(data.project || {});
  } catch (error) {
    setStatus(`Não foi possível abrir o projeto: ${error.message}`);
  }
  if (state.activeClipId) {
    const clip = state.clips.find((item) => item.id === state.activeClipId || item.job_id === state.activeClipId);
    if (clip) await selectClip(clip, { restore: false });
  }
}

async function openProject(projectId) {
  if (!state.clientId || projectId === state.projectId) return;
  if (state.dirty) await persistProject();
  const clientId = state.clientId;
  try {
    const data = await loadVideoProject(clientId, projectId);
    if (clientId !== state.clientId) return;
    resetProjectFields(); state.edit = defaultEdit(); clearClip();
    state.projects = data.items || state.projects;
    state.projectId = data.activeId || "";
    applyProject(data.project || {});
    await resetStudio(); paintAll(); scheduleQuote();
  } catch (error) {
    setStatus(`Não foi possível abrir o projeto: ${error.message}`); paintAll();
  }
}

async function newProject() {
  if (!state.clientId) return;
  if (state.dirty) await persistProject();
  resetProjectFields(); state.edit = defaultEdit(); state.projectId = ""; state.name = "Novo projeto";
  clearClip(); await resetStudio(); markDirty(); await persistProject(); paintAll();
}

function applyProject(project) {
  if (!project || typeof project !== "object") return;
  state.clipEdits = project.clip_edits || {};
  state.composition = project.composition || null;
  state.edit = { ...defaultEdit(), ...(project.edit || {}) };
  state.seed = project.seed ?? null;
  state.generationMode = project.generation_mode === "single_image" ? "single_image" : "storyboard";
  state.name = project.name || state.name;
  state.aspectRatio = project.aspect_ratio || state.aspectRatio;
  state.aspectExplicit = project.aspect_explicit === true;
  state.duration = Number(project.duration || state.duration) || 8;
  state.quality = project.quality || state.quality;
  state.activeClipId = project.active_clip_id || state.activeClipId;
  state.selectedSceneId = project.selected_scene_id || state.selectedSceneId;
  if (project.script && Array.isArray(project.script.beats)) state.script = project.script;
  const savedDraft = project.storyboard_draft;
  if (savedDraft && typeof savedDraft === "object") {
    state.draft = {
      briefing: String(savedDraft.briefing || ""),
      beats: Array.isArray(savedDraft.beats) ? savedDraft.beats.map((beat) => ({ ...beat, generating: false })) : [],
      warnings: Array.isArray(savedDraft.warnings) ? savedDraft.warnings : [],
      anchorUrl: String(savedDraft.anchor_url || ""),
      runId: String(savedDraft.run_id || ""),
      status: "idle",
      error: "",
    };
  }
  if (project.audio && typeof project.audio === "object") {
    state.audio = normalizeAudioState(project.audio);
  }
  if (project.motion && typeof project.motion === "object") {
    state.motion = { ...state.motion, ...project.motion };
  }
  state.spend = normalizeWorkspaceSpend(project.spend);
  const ids = Array.isArray(project.scene_ids) ? project.scene_ids : [];
  if (ids.length) {
    state.scenes = ids
      .map((id) => state.library.find((item) => item.id === id))
      .filter(Boolean);
    if (!state.selectedSceneId && state.scenes[0]) state.selectedSceneId = state.scenes[0].id;
    alignBeatsToScenes();
  }
  state.dirty = false;
}

function projectPayload() {
  return {
    client_id: state.clientId || undefined,
    project: {
      name: state.name,
      aspect_ratio: state.aspectRatio,
      aspect_explicit: state.aspectExplicit,
      duration: state.duration,
      quality: state.quality,
      scene_ids: state.scenes.map((item) => item.id),
      script: state.script,
      storyboard_draft: { briefing: state.draft.briefing, beats: state.draft.beats, warnings: state.draft.warnings, anchor_url: state.draft.anchorUrl || "", run_id: state.draft.runId || "" },
      audio: state.audio,
      edit: state.edit,
      composition:state.composition,
      clip_edits: {...(state.clipEdits || {}), ...(state.activeClipId ? {[state.activeClipId]:state.edit} : {})},
      seed: state.seed,
      generation_mode: state.generationMode,
      motion: state.motion,
      spend: state.spend,
      active_clip_id: state.activeClipId,
      selected_scene_id: state.selectedSceneId,
    },
  };
}

// Só o que entra na cotação do Seedance; corte, volume e efeitos da edição não mudam o preço.
function quoteSignature() {
  return JSON.stringify([
    state.generationMode, state.selectedSceneId, state.scenes.map((item) => item.id), state.duration, state.seed,
    state.quality, state.aspectRatio, state.aspectExplicit, state.script, state.audio, state.motion,
  ]);
}

function markDirty() {
  recordStudioChange();
  paintStudio();
  state.dirty = true;
  state.saveStatus = "pending";
  paintSaveStatus();
  scheduleSave();
  if (state.quoteSignature === quoteSignature() && state.quoteStatus !== "idle") return;
  state.quote = null;
  state.quoteError = "";
  state.quoteStatus = "idle";
  state.requestVersion += 1;
  paintQuote();
  updateGenerateEnabled();
  scheduleQuote();
}

function scheduleSave() {
  window.clearTimeout(saveTimer);
  saveTimer = window.setTimeout(persistProject, 900);
}

async function persistProject() {
  if (!state.clientId) return;
  if (state.saving) {
    scheduleSave();
    return;
  }
  const clientId = state.clientId;
  const version = state.requestVersion;
  const request = ++saveRequest;
  state.saving = true;
  state.saveStatus = "saving";
  paintSaveStatus();
  try {
    const saved = await saveVideoProject(projectPayload());
    if (clientId === state.clientId && request === saveRequest && version === state.requestVersion) {
      state.projectId = saved.activeId || state.projectId;
      if (saved.item) {
        const index = state.projects.findIndex((item) => String(item.id) === String(saved.item.id));
        if (index >= 0) state.projects[index] = {...state.projects[index], ...saved.item};
        else state.projects.unshift(saved.item);
      }
      state.dirty = false;
      state.saveStatus = "saved";
    }
  } catch (error) {
    if (clientId === state.clientId && request === saveRequest) {
      state.saveStatus = "error";
      setStatus(error.message);
    }
  } finally {
    if (clientId === state.clientId && request === saveRequest) {
      state.saving = false;
      paintSaveStatus();
      if (state.dirty && state.saveStatus !== "error") scheduleSave();
    }
  }
}

async function loadLibrary() {
  if (!state.clientId) return;
  const clientId = state.clientId;
  try {
    const data = await get(`${swapApi}/library?client_id=${encodeURIComponent(clientId)}&media=still`);
    if (clientId !== state.clientId) return;
    state.library = data.items || [];
    const keep = new Set(state.library.map((item) => item.id));
    state.scenes = state.scenes.filter((scene) => keep.has(scene.id) && !state.library.find((item) => item.id === scene.id)?.broken);
    paintLibrary();
    return state.library;
  } catch (error) {
    setStatus(error.message);
    return [];
  }
}

async function createNextSceneWithTrocr() {
  if (state.creatingScene2 || !state.scenes.length || state.scenes.length >= 30 || !state.clientId) return;
  const base = state.scenes.find((scene) => scene.id === state.selectedSceneId) || state.scenes[state.scenes.length - 1];
  const nextIndex = state.scenes.length + 1;
  const reference = base.image_url || base.image;
  if (!reference) {
    setStatus("A cena em foco não possui uma imagem disponível.");
    return;
  }
  const copy = { ...(base.ocr || {}), ...(base.params || {}) };
  const before = new Set(state.library.map((item) => item.id));
  state.creatingScene2 = true;
  paintProps();
  setStatus(`Trocr está criando a imagem ${nextIndex} da sequência…`);
  try {
    const data = await post(`${swapApi}`, {
      client_id: state.clientId,
      reference,
      base_id: base.version_id || String(base.id || "").split(":").pop(),
      run_id: base.run_id || undefined,
      aspect_ratio: state.aspectRatio || base.aspect_ratio || "16:9",
      quality: "production",
      force_image: true,
      use_brand_context: true,
      scene_variant: nextIndex,
      scene_index: nextIndex,
      scene_group: base.scene_group || undefined,
      headline: copy.headline || base.headline || "",
      support: copy.support || "",
      subtitle: copy.subtitle || "",
      price: copy.price || "",
      cta: copy.cta || "",
      logo_text: copy.logo_text || "",
      dates: copy.dates || "",
      venue: copy.venue || "",
      disclaimer: copy.disclaimer || "",
      ocr: base.ocr || undefined,
      elements: Array.isArray(base.ocr?.elements) ? base.ocr.elements : undefined,
      preserve: ["layout", "people", "product", "logo", "text_position", "colors", "graphic"],
      alter: ["background"],
      note: "Crie a próxima tomada da mesma campanha, preserve elenco, produto, marca e texto; varie enquadramento e ambiente para continuar a narrativa.",
    });
    if (!data?.image_url && !data?.png_data_url) throw new Error(data?.preview || "O Trocr não devolveu a próxima imagem.");
    recordSpend(`trocr:${data.plan_hash || data.image_url || Date.now()}`, "image", `Imagem ${nextIndex} da sequência`, data.quote, "confirmed");
    markDirty();
    const items = await loadLibrary();
    const created = items.find((item) => !before.has(item.id) && (
      item.image_url === data.image_url ||
      (item.run_id === base.run_id && Number(item.scene_index) === nextIndex)
    ));
    if (!created) throw new Error("A cena foi gerada, mas não apareceu na biblioteca. Recarregue o Studio.");
    state.scenes.push(created);
    state.selectedSceneId = created.id;
    state.generationMode = "storyboard";
    alignBeatsToScenes();
    markDirty();
    setStatus(`Imagem ${nextIndex} pronta. Revise a sequência e monte o roteiro.`);
  } catch (error) {
    setStatus(error.message);
  } finally {
    state.creatingScene2 = false;
    paintAll();
  }
}

async function loadClips(opts = {}) {
  if (!state.clientId) return;
  const clientId = state.clientId;
  try {
    const results = await Promise.allSettled([
      get(`${swapApi}/library?client_id=${encodeURIComponent(clientId)}&media=video`),
      get(`${studioApi}/clips?client_id=${encodeURIComponent(clientId)}`),
    ]);
    if (clientId !== state.clientId) return;
    state.clips = results.flatMap(result => result.status === 'fulfilled' ? result.value.items || [] : []).filter(item => item.video_url);
    if (results.some(result => result.status === 'rejected')) setStatus('Parte da biblioteca está indisponível. Os vídeos carregados continuam acessíveis.');
  } catch (_error) {
    if (!opts.prefer) state.clips = [];
  }
  const chosen = pickClip(opts.prefer);
  if (chosen && opts.select !== false) await selectClip(chosen, { restore: Boolean(opts.restore) });
  else paintClips();
}

function pickClip(prefer) {
  const matches = (item, row) => {
    if (!item || !row) return false;
    if (row.job_id && item.job_id === row.job_id) return true;
    if (row.video_url && item.video_url === row.video_url) return true;
    if (row.id && (item.id === row.id || item.version_id === row.id || String(item.id).endsWith(`:${row.id}`))) return true;
    return false;
  };
  if (prefer?.video_url) {
    const found = state.clips.find((item) => matches(item, prefer));
    if (found) return found;
    const synthetic = {
      id: prefer.id || (prefer.job_id ? `job:${prefer.job_id}` : "clip-ready"),
      name: prefer.name || "Clipe",
      video_url: prefer.video_url,
      poster_url: prefer.poster_url || prefer.image_url || prefer.image || "",
      duration: prefer.duration,
      job_id: prefer.job_id || "",
      script: prefer.script || null,
      storyboard_ids: prefer.storyboard_ids || [],
      voiceover_script: prefer.voiceover_script || "",
      quality: prefer.quality || "",
    };
    state.clips = [synthetic, ...state.clips.filter((item) => item.video_url !== synthetic.video_url)];
    return synthetic;
  }
  if (state.activeClipId) {
    return state.clips.find((item) => item.id === state.activeClipId || item.job_id === state.activeClipId) || null;
  }
  return null;
}

document.addEventListener("cadu:clip-imported", event => {
  state.clips.unshift(event.detail);
  state.libTab = "video";
  selectClip(event.detail, {restore:false}).then(()=>{paintAll();if(event.detail.autocut)document.dispatchEvent(new CustomEvent('cadu:apply-autocut',{detail:event.detail}));});
});

async function selectClip(clip, { restore = true } = {}) {
  if (!clip?.video_url) return;
  const switching = state.activeClipId !== (clip.id || clip.job_id);
  if (switching) {
    state.clipEdits ||= {};
    if (state.activeClipId) state.clipEdits[state.activeClipId] = structuredClone(state.edit);
    state.edit = structuredClone(state.clipEdits[clip.id || clip.job_id] || defaultEdit());
    resetClipHistory();
  }
  state.activeClipId = clip.id || clip.job_id || "";
  state.previewMode = "clip";
  const still = document.getElementById("mcVideoStill");
  if (still) still.hidden = true;
  playClip(clip);
  document.dispatchEvent(new CustomEvent("cadu:clip-selected"));
  if (restore) restoreFromClip(clip);
  paintClips();
  paintCanvas();
  markDirty();
  scheduleQuote();
}

function restoreFromClip(clip) {
  const ids = Array.isArray(clip.storyboard_ids) ? clip.storyboard_ids : [];
  if (ids.length) {
    state.scenes = ids
      .map((id) => state.library.find((item) => item.id === id || item.version_id === id || String(item.id).endsWith(`:${id}`)))
      .filter(Boolean);
    if (state.scenes[0]) state.selectedSceneId = state.scenes[0].id;
  }
  if (clip.script && Array.isArray(clip.script.beats)) {
    state.script = clip.script;
  } else {
    alignBeatsToScenes();
  }
  if (clip.quality) state.quality = clip.quality;
  if ([4,5,8,10,15,20,30].includes(Number(clip.duration))) state.duration = Number(clip.duration);
  if (clip.voiceover_script) {
    state.audio.enabled = true;
    state.audio.narration_mode = "voiceover";
    syncAudioMode(state.audio);
    state.audio.script = clip.voiceover_script;
  }
  alignBeatsToScenes();
  paintAll();
}

function selectScene(id) {
  if (!id) return;
  state.selectedSceneId = id;
  state.previewMode = "scene";
  const empty = document.getElementById("mcVideoEmpty");
  if (empty) empty.hidden = true;
  paintAll();
  markDirty();
  scheduleQuote();
}

let aspectRequest=0;
function adoptSelectedAspect(item = null) {
  if(state.aspectExplicit)return;
  const selected = item || state.scenes[0];
  if(!selected)return;
  const request=++aspectRequest, client=state.clientId;
  state.aspectPending=sourceAspect(selected).then(ratio=>{
    if(request!==aspectRequest||client!==state.clientId||state.aspectExplicit||!state.scenes.some(s=>s.id===selected.id))return;
    if(ratio){state.aspectRatio=ratio;paintAll();markDirty();}
  });
}

function stepScene(delta) {
  if (!state.scenes.length) return;
  const current = Math.max(0, state.scenes.findIndex((item) => item.id === state.selectedSceneId));
  const next = (current + delta + state.scenes.length) % state.scenes.length;
  selectScene(state.scenes[next].id);
}

function moveScene(id, delta) {
  const from = state.scenes.findIndex((item) => item.id === id);
  const to = from + delta;
  if (from < 0 || to < 0 || to >= state.scenes.length) return;
  const [scene] = state.scenes.splice(from, 1);
  state.scenes.splice(to, 0, scene);
  alignBeatsToScenes();
  paintAll();
  markDirty();
  scheduleQuote();
}

function cancelReplace() {
  if (!state.replaceSceneId && !state.pickDraftId) return;
  state.replaceSceneId = "";
  state.pickDraftId = "";
  setStatus("");
  paintProps();
}

// A cena troca de imagem e mantém o roteiro: o beat é re-chaveado para o novo ID.
function replaceScene(oldId, item) {
  const index = state.scenes.findIndex((row) => row.id === oldId);
  if (index < 0 || item.broken) return;
  if (state.scenes.some((row) => row.id === item.id)) {
    setStatus("Essa peça já está na sequência. Escolha outra.");
    return;
  }
  const beat = state.script?.beats?.find((row) => row.id === oldId);
  state.scenes.splice(index, 1, item);
  if (beat) beat.id = item.id;
  if (state.selectedSceneId === oldId) state.selectedSceneId = item.id;
  state.replaceSceneId = "";
  if (state.scenes.length === 1) adoptSelectedAspect(item);
  alignBeatsToScenes();
  setStatus(`Cena ${index + 1} trocada; roteiro mantido.`);
  paintAll();
  markDirty();
  scheduleQuote();
}

function onSceneCardClick(event) {
  const button = event.target.closest("[data-card-action]");
  if (!button) return;
  const id = button.getAttribute("data-id");
  const action = button.getAttribute("data-card-action");
  if (action === "select") return selectScene(id);
  if (action === "up") return moveScene(id, -1);
  if (action === "down") return moveScene(id, 1);
  if (action === "remove") {
    state.selectedSceneId = id;
    return removeSelectedScene();
  }
  if (action === "regen-image") return regenerateSceneImage(id);
  if (action === "rewrite") return rewriteSceneText(id);
  if (action === "undo-text") return undoSceneText(id);
  if (action === "replace") {
    if (state.replaceSceneId === id) return cancelReplace();
    state.replaceSceneId = id;
    state.libTab = "still";
    setStatus("Escolha na biblioteca a peça que entra no lugar desta cena. Esc cancela.");
    paintAll();
  }
}

const BEAT_TEXT_FIELDS = ["purpose", "visual", "motion", "hold", "transition", "spoken"];
const beatText = (beat) => Object.fromEntries(BEAT_TEXT_FIELDS.map((key) => [key, String(beat?.[key] || "")]));

// Reescreve só o texto de UMA cena (texto barato). A versão anterior fica guardada para "Desfazer texto".
async function rewriteSceneText(id) {
  const index = state.scenes.findIndex((scene) => scene.id === id);
  const clientId = state.clientId;
  if (index < 0 || !clientId || state.regeneratingId || state.draft.generating) return;
  const instruction = window.prompt(`O que mudar na cena ${index + 1}? (opcional: deixe vazio para uma nova versão)`, "");
  if (instruction === null) return;
  const beats = state.scenes.map((scene) => ({ id: scene.id, ...beatText(beatFor(scene.id)) }));
  const briefing = String(state.draft.briefing || "").trim() || beats.map((row) => row.visual).filter(Boolean).join(". ");
  if (briefing.length < 10) {
    setStatus("Descreva o visual das cenas ou o briefing do vídeo antes de reescrever.");
    return;
  }
  state.regeneratingId = id;
  state.regeneratingKind = "text";
  paintAll();
  try {
    const data = await post(`${studioApi}/agent/storyboard/beat`, {
      client_id: clientId, request_id: newId(), briefing, beats, index, instruction: instruction.trim(), duration: state.duration,
    });
    if (clientId !== state.clientId) return;
    const beat = ensureBeat(id);
    beat.previous = beatText(beat);
    const { visual, motion, hold, transition, spoken } = data.beat;
    Object.assign(beat, { visual, motion, hold, transition, spoken });
    const note = data.warnings?.length ? ` Atenção: ${data.warnings.join(" ")}` : "";
    setStatus(`Cena ${index + 1} reescrita. A imagem não mudou; use "Gerar nova imagem" se quiser refazê-la.${note}`);
    if (state.audio.narration_mode === "voiceover") state.audio.script = spokenFromBeats();
    markDirty();
    scheduleQuote();
  } catch (error) {
    setStatus(error.message);
  } finally {
    state.regeneratingId = "";
    state.regeneratingKind = "";
    paintAll();
  }
}

function undoSceneText(id) {
  const beat = state.script?.beats?.find((row) => row.id === id);
  if (!beat?.previous) return;
  Object.assign(beat, beat.previous);
  delete beat.previous;
  if (state.audio.narration_mode === "voiceover") state.audio.script = spokenFromBeats();
  setStatus("Texto anterior restaurado.");
  paintAll();
  markDirty();
  scheduleQuote();
}

// Gera uma nova imagem só desta cena, no estilo da 1ª cena, e a troca no lugar mantendo o roteiro.
async function regenerateSceneImage(id) {
  const index = state.scenes.findIndex((scene) => scene.id === id);
  const clientId = state.clientId;
  if (index < 0 || !clientId || state.regeneratingId || state.draft.generating) return;
  const beat = ensureBeat(id);
  if (!String(beat.visual || "").trim()) {
    setStatus("Descreva o visual da cena antes de gerar uma nova imagem.");
    return;
  }
  let credits = null;
  try {
    const prices = await post(`${studioApi}/agent/storyboard/image`, { client_id: clientId, dry_run: true, aspect_ratio: state.aspectRatio });
    credits = index > 0 ? prices.credits_with_reference || prices.credits_per_image : prices.credits_per_image;
  } catch (_) { /* a confirmação segue sem o valor */ }
  const price = credits ? `cerca de ${Number(credits).toLocaleString("pt-BR")} tokens` : "tokens reais de imagem";
  const note = index === 0 && state.scenes.length > 1 ? " Esta é a 1ª cena: ela define o estilo, então as outras podem ficar diferentes dela." : "";
  if (!window.confirm(`Gerar uma nova imagem para a cena ${index + 1}? Vai usar ${price}. A imagem atual continua na biblioteca.${note}`)) return;
  const anchor = index > 0 ? (state.scenes[0].image_url || "") : "";
  const total = state.scenes.length;
  // Mesmo pedido = mesmo request_id (repetir após queda de rede reaproveita a imagem já paga); depois do sucesso o
  // próximo clique nasce com id novo, para vir uma variação diferente.
  const key = JSON.stringify([id, beat.visual, beat.hold, state.aspectRatio, anchor, index, total]);
  if (!beat.regen || beat.regen.key !== key) beat.regen = { key, request_id: newId() };
  state.aspectExplicit = true;
  state.regeneratingId = id;
  state.regeneratingKind = "image";
  paintAll();
  try {
    const data = await post(`${studioApi}/agent/storyboard/image`, {
      client_id: clientId, request_id: beat.regen.request_id, beat: { visual: beat.visual, hold: beat.hold },
      index, total, aspect_ratio: state.aspectRatio, anchor_url: anchor, run_id: state.draft.runId || "", title: `Cena ${index + 1}`,
    });
    if (clientId !== state.clientId) return;
    state.draft.runId ||= data.run_id;
    const items = await loadLibrary();
    const item = (items || state.library).find((row) => row.id === data.scene_id);
    if (!item) throw new Error("A imagem foi gerada, mas não apareceu na biblioteca. Recarregue o Studio.");
    delete beat.regen;
    replaceScene(id, item);
    delete state.sceneAspects[id];
    refreshSceneAspects();
  } catch (error) {
    setStatus(error.message);
  } finally {
    state.regeneratingId = "";
    state.regeneratingKind = "";
    paintAll();
  }
}

// Proporção real de cada imagem da sequência, para a checagem avisar quando elas diferem.
function refreshSceneAspects() {
  for (const scene of state.scenes) {
    if (scene.id in state.sceneAspects) continue;
    state.sceneAspects[scene.id] = "";
    sourceAspect(scene).then((ratio) => {
      state.sceneAspects[scene.id] = ratio || "";
      updateGenerateEnabled();
    });
  }
}

async function buildDraft() {
  const briefing = String(state.draft.briefing || "").trim();
  if (!state.clientId) return;
  if (briefing.length < 10) {
    state.draft.error = "Descreva o vídeo em pelo menos uma frase.";
    paintDraft();
    return;
  }
  if (state.draft.status === "loading") return;
  if (state.draft.beats.length && !window.confirm("Montar de novo substitui o rascunho atual. Continuar?")) return;
  const clientId = state.clientId;
  state.draft.status = "loading";
  state.draft.error = "";
  paintDraft();
  try {
    const data = await post(`${studioApi}/agent/storyboard`, {
      client_id: clientId,
      briefing,
      duration: state.duration,
      aspect_ratio: state.aspectRatio,
      request_id: newId(),
    });
    if (clientId !== state.clientId) return;
    state.draft.beats = data.beats || [];
    state.draft.warnings = data.warnings || [];
    state.draft.anchorUrl = "";
    state.draft.runId = "";
    state.draft.status = "ready";
    state.pickDraftId = "";
    markDirty();
  } catch (error) {
    if (clientId !== state.clientId) return;
    state.draft.status = "idle";
    state.draft.error = error.message;
  }
  paintDraft();
}

function onDraftField(event) {
  const field = event.target.closest("[data-draft-field]");
  if (!field) return;
  const beat = state.draft.beats.find((row) => row.id === field.getAttribute("data-id"));
  if (!beat) return;
  beat[field.getAttribute("data-draft-field")] = field.value;
  markDirty();
}

function onDraftClick(event) {
  const button = event.target.closest("[data-draft-action]");
  if (!button) return;
  const action = button.getAttribute("data-draft-action");
  const id = button.getAttribute("data-id");
  const beats = state.draft.beats;
  const index = beats.findIndex((row) => row.id === id);
  if (action === "discard") {
    if (!window.confirm("Descartar o rascunho do storyboard?")) return;
    state.draft.beats = [];
    state.draft.warnings = [];
    state.pickDraftId = "";
  } else if (action === "up" || action === "down") {
    const to = index + (action === "up" ? -1 : 1);
    if (index < 0 || to < 0 || to >= beats.length) return;
    const [row] = beats.splice(index, 1);
    beats.splice(to, 0, row);
  } else if (action === "remove") {
    if (index < 0) return;
    beats.splice(index, 1);
    if (state.pickDraftId === id) state.pickDraftId = "";
  } else if (action === "generate") {
    generateDraftImages([id]);
    return;
  } else if (action === "pick") {
    state.replaceSceneId = "";
    state.pickDraftId = state.pickDraftId === id ? "" : id;
    if (state.pickDraftId) {
      state.libTab = "still";
      setStatus("Escolha na biblioteca a peça desta cena. Esc cancela.");
    }
  }
  paintAll();
  markDirty();
}

async function generateAllDraftImages() {
  await generateDraftImages(state.draft.beats.map((beat) => beat.id));
}

// Gera em ordem, uma por vez: a 1ª imagem vira a referência de estilo das seguintes. Para no primeiro erro.
async function generateDraftImages(ids) {
  const draft = state.draft;
  const clientId = state.clientId;
  if (!clientId || draft.generating || !ids.length) return;
  if (state.scenes.length + ids.length > 30) {
    setStatus("O clipe aceita no máximo 30 cenas.");
    return;
  }
  let prices = null;
  try {
    prices = await post(`${studioApi}/agent/storyboard/image`, { client_id: clientId, dry_run: true, aspect_ratio: state.aspectRatio });
  } catch (_) { /* a confirmação segue sem o valor */ }
  // A 1ª imagem do storyboard não tem referência de estilo; as seguintes têm e custam um pouco mais.
  const plain = Number(prices?.credits_per_image || 0), styled = Number(prices?.credits_with_reference || plain);
  const total = draft.anchorUrl ? styled * ids.length : plain + styled * (ids.length - 1);
  const price = plain ? `cerca de ${Math.round(total / ids.length).toLocaleString("pt-BR")} tokens cada (total ≈ ${Math.round(total).toLocaleString("pt-BR")})` : "tokens reais de imagem";
  if (!window.confirm(`Gerar ${ids.length} ${ids.length === 1 ? "imagem" : "imagens"}? Vai usar ${price}. Cada imagem é cobrada ao ficar pronta e você pode parar a qualquer momento.`)) return;
  // O formato foi decidido antes de gerar; a primeira imagem não pode trocá-lo para o das seguintes.
  state.aspectExplicit = true;
  draft.generating = true;
  draft.stopRequested = false;
  paintDraft();
  try {
    for (const id of ids) {
      if (draft.stopRequested || clientId !== state.clientId) break;
      const index = draft.beats.findIndex((row) => row.id === id);
      if (index < 0) continue;
      const beat = draft.beats[index];
      beat.error = "";
      beat.generating = true;
      // O mesmo request_id é mantido enquanto o pedido for idêntico: repetir após queda de rede reaproveita a imagem
      // já paga. Se o conteúdo mudou (texto editado, referência de estilo, posição), o servidor recusaria o id antigo.
      const requestKey = JSON.stringify([beat.visual, beat.hold, state.aspectRatio, draft.anchorUrl || "", state.scenes.length, state.scenes.length + draft.beats.length]);
      if (!beat.request_id || beat.request_key !== requestKey) {
        beat.request_id = newId();
        beat.request_key = requestKey;
      }
      paintDraft();
      try {
        const data = await post(`${studioApi}/agent/storyboard/image`, {
          client_id: clientId,
          request_id: beat.request_id,
          beat: { visual: beat.visual, hold: beat.hold },
          index: state.scenes.length,
          total: state.scenes.length + draft.beats.length,
          aspect_ratio: state.aspectRatio,
          anchor_url: draft.anchorUrl || "",
          run_id: draft.runId || "",
          title: `Cena ${state.scenes.length + 1}`,
        });
        if (clientId !== state.clientId) break;
        draft.anchorUrl ||= data.image_url;
        draft.runId ||= data.run_id;
        const items = await loadLibrary();
        const item = (items || state.library).find((row) => row.id === data.scene_id);
        if (!item) throw new Error("A imagem foi gerada, mas não apareceu na biblioteca. Recarregue o Studio.");
        beat.generating = false;
        useDraftBeat(id, item);
      } catch (error) {
        beat.generating = false;
        beat.error = error.message;
        break;
      }
    }
  } finally {
    draft.generating = false;
    draft.stopRequested = false;
    paintAll();
    markDirty();
  }
}

// A peça escolhida vira cena e leva o roteiro do rascunho; o beat passa a ser chaveado pelo ID da cena.
function useDraftBeat(draftId, item) {
  const index = state.draft.beats.findIndex((row) => row.id === draftId);
  if (index < 0 || item.broken) return;
  if (state.scenes.some((scene) => scene.id === item.id)) {
    setStatus("Essa peça já está na sequência. Escolha outra.");
    return;
  }
  if (state.scenes.length >= 30) {
    setStatus("O clipe aceita no máximo 30 cenas.");
    return;
  }
  const [draftBeat] = state.draft.beats.splice(index, 1);
  state.scenes.push(item);
  state.selectedSceneId = item.id;
  if (state.scenes.length === 1) state.generationMode = "single_image";
  else if (state.scenes.length === 2) state.generationMode = "storyboard";
  if (state.generationMode === "single_image") adoptSelectedAspect(item);
  alignBeatsToScenes();
  const { id: _ignored, ...fields } = draftBeat;
  Object.assign(ensureBeat(item.id), fields);
  state.pickDraftId = "";
  state.previewMode = "scene";
  setStatus(`Peça ligada à cena ${state.scenes.length}; faltam ${state.draft.beats.length} no rascunho.`);
  paintAll();
  markDirty();
  scheduleQuote();
}

function moveSelectedScene(delta) {
  const from = state.scenes.findIndex((item) => item.id === state.selectedSceneId);
  const to = from + delta;
  if (from < 0 || to < 0 || to >= state.scenes.length) return;
  const [scene] = state.scenes.splice(from, 1);
  state.scenes.splice(to, 0, scene);
  alignBeatsToScenes();
  paintAll();
  markDirty();
  scheduleQuote();
}

function onLibraryClick(event) {
  const button = event.target.closest("[data-action]");
  if (!button) return;
  const id = button.getAttribute("data-id");
  if (button.getAttribute("data-action") === "delete") {
    removeLibraryItem(id);
    return;
  }
  if (button.getAttribute("data-action") === "remove") {
    state.selectedSceneId = id;
    removeSelectedScene();
    return;
  }
  const item = state.library.find((row) => row.id === id);
  if (!item || item.broken) return;
  if (state.pickDraftId) {
    useDraftBeat(state.pickDraftId, item);
    return;
  }
  if (state.replaceSceneId && !state.scenes.some((row) => row.id === state.replaceSceneId)) {
    state.replaceSceneId = "";
  }
  if (state.replaceSceneId) {
    replaceScene(state.replaceSceneId, item);
    return;
  }
  if (button.getAttribute("data-action") === "select" || state.scenes.some((scene) => scene.id === item.id)) {
    selectScene(item.id);
    return;
  } else if (state.scenes.length < 30) {
    state.scenes.push(item);
    state.selectedSceneId = item.id;
    if (state.scenes.length === 1) state.generationMode = "single_image";
    else if (state.scenes.length === 2) state.generationMode = "storyboard";
    if (state.generationMode === "single_image") adoptSelectedAspect(item);
  }
  alignBeatsToScenes();
  state.previewMode = "scene";
  paintAll();
  markDirty();
  scheduleQuote();
}

function onClipClick(event) {
  const button = event.target.closest("[data-action]");
  if (!button) return;
  const id = button.getAttribute("data-clip");
  if (button.getAttribute("data-action") === "delete") {
    removeClip(id);
    return;
  }
  const clip = state.clips.find((item) => item.id === id);
  if (clip) selectClip(clip, { restore: true });
}

function bindDrop(node) {
  if (!node) return;
  node.addEventListener("dragover", (event) => {
    event.preventDefault();
    node.classList.add("is-drop");
  });
  node.addEventListener("dragleave", () => node.classList.remove("is-drop"));
  node.addEventListener("drop", (event) => {
    event.preventDefault();
    node.classList.remove("is-drop");
    takeFile(event.dataTransfer?.files?.[0]);
  });
}

function bindTimelineDrag(lane) {
  if (!lane) return;
  lane.addEventListener("dragstart", (event) => {
    const block = event.target.closest("[data-scene]");
    if (!block) return;
    state.dragSceneId = block.getAttribute("data-scene") || "";
    block.classList.add("is-dragging");
    event.dataTransfer?.setData("text/plain", state.dragSceneId);
  });
  lane.addEventListener("dragend", (event) => {
    event.target.closest(".mc-cadu-video-block")?.classList.remove("is-dragging");
    state.dragSceneId = "";
  });
  lane.addEventListener("dragover", (event) => {
    event.preventDefault();
  });
  lane.addEventListener("drop", (event) => {
    event.preventDefault();
    const target = event.target.closest("[data-scene]");
    const fromId = state.dragSceneId || event.dataTransfer?.getData("text/plain");
    const toId = target?.getAttribute("data-scene");
    if (!fromId || !toId || fromId === toId) return;
    const from = state.scenes.findIndex((item) => item.id === fromId);
    const to = state.scenes.findIndex((item) => item.id === toId);
    if (from < 0 || to < 0) return;
    const [row] = state.scenes.splice(from, 1);
    state.scenes.splice(to, 0, row);
    alignBeatsToScenes();
    paintAll();
    markDirty();
    scheduleQuote();
  });
}

async function takeFile(file) {
  if (!file || !String(file.type || "").startsWith("image/")) return;
  const clientId = state.clientId;
  const reader = new FileReader();
  reader.onload = async () => {
    try {
      const item = await post(`${swapApi}/library`, {
        client_id: clientId || undefined,
        image: String(reader.result || ""),
        name: pieceName(file.name),
        new_piece: true,
      });
      if (clientId !== state.clientId) return;
      state.library = [item, ...state.library.filter((row) => row.id !== item.id)];
      if (!item.broken && state.scenes.length < 30) {
        state.scenes.push(item);
        state.selectedSceneId = item.id;
        if (state.scenes.length === 1) state.generationMode = "single_image";
        else if (state.scenes.length === 2) state.generationMode = "storyboard";
        if (state.generationMode === "single_image") adoptSelectedAspect(item);
        alignBeatsToScenes();
      }
      paintAll();
      markDirty();
      scheduleQuote();
      setStatus("Peça nova na biblioteca.");
    } catch (error) {
      setStatus(error.message);
    }
  };
  reader.readAsDataURL(file);
  const input = document.getElementById("mcVideoFile");
  if (input) input.value = "";
}

function pieceName(filename) {
  const stem = String(filename || "").replace(/\.[^.]+$/, "").trim();
  return stem || "Peça";
}

async function removeLibraryItem(id) {
  const item = state.library.find((row) => row.id === id);
  if (!item) return;
  if (!item.broken && !window.confirm("Apagar esta peça da biblioteca?")) return;
  try {
    const data = await deleteLibrary({
      client_id: state.clientId || undefined,
      id,
      media: "still",
    });
    applyLibrary(data.items);
    setStatus("Peça apagada.");
  } catch (error) {
    setStatus(error.message);
  }
}

async function purgeBroken() {
  const broken = state.library.filter((item) => item.broken);
  if (!broken.length) return;
  try {
    const data = await deleteLibrary({
      client_id: state.clientId || undefined,
      ids: broken.map((item) => item.id),
      broken: true,
      media: "still",
    });
    applyLibrary(data.items);
    setStatus(broken.length === 1 ? "Arquivo indisponível removido." : `${broken.length} arquivos indisponíveis removidos.`);
  } catch (error) {
    setStatus(error.message);
  }
}

async function removeClip(id) {
  const clip = state.clips.find((item) => item.id === id);
  if (!clip) return;
  if (!window.confirm("Apagar este clipe?")) return;
  try {
    if (id.startsWith('upload:')) {
      await post(`${studioApi}/archive-clip`, {client_id:state.clientId, clip_id:id});
    } else {
      await deleteLibrary({client_id:state.clientId || undefined,id,media:'video'});
    }
    state.clips = state.clips.filter(item => item.id !== id);
    delete state.clipEdits?.[id];
    if (state.activeClipId === id) {
      state.activeClipId = "";
      state.previewMode = "scene";
      clearClip();
      document.dispatchEvent(new Event("cadu:clip-cleared"));
      paintCanvas();
    }
    paintClips();
    setStatus("Clipe apagado.");
    markDirty();
  } catch (error) {
    setStatus(error.message);
  }
}

function applyLibrary(items) {
  state.library = items || [];
  const keep = new Set(state.library.map((item) => item.id));
  state.scenes = state.scenes.filter((scene) => keep.has(scene.id) && !state.library.find((item) => item.id === scene.id)?.broken);
  if (!state.scenes.some((item) => item.id === state.selectedSceneId)) {
    state.selectedSceneId = state.scenes[0]?.id || "";
  }
  alignBeatsToScenes();
  paintAll();
  markDirty();
  scheduleQuote();
}

function removeSelectedScene() {
  if (!state.selectedSceneId) return;
  state.scenes = state.scenes.filter((item) => item.id !== state.selectedSceneId);
  state.replaceSceneId = "";
  state.selectedSceneId = state.scenes[0]?.id || "";
  if (state.scenes.length === 1) {
    state.generationMode = "single_image";
    adoptSelectedAspect(state.scenes[0]);
  }
  alignBeatsToScenes();
  paintAll();
  markDirty();
  scheduleQuote();
}

async function buildScript() {
  if (state.scenes.length < 2) {
    setStatus("Adicione pelo menos duas cenas.");
    return;
  }
  if (state.scenes.some((item) => item.broken)) {
    setStatus("Remova os arquivos indisponíveis do roteiro.");
    return;
  }
  setStatus("Lendo as cenas…");
  const version = state.requestVersion;
  const clientId = state.clientId;
  try {
    const data = await post(`${swapApi}/animate/script`, {
      client_id: state.clientId || undefined,
      duration: state.duration,
      scene_ids: state.scenes.map((item) => item.id),
      force_ocr: Boolean(state.ocrFailed),
    });
    if (version !== state.requestVersion || clientId !== state.clientId) return;
    state.script = data.script;
    state.ocrFailed = Boolean(data.warnings?.length);
    (data.scenes || []).forEach((scene) => {
      const local = state.scenes.find((row) => row.id === scene.id);
      if (!local) return;
      local.headline = scene.headline || "";
      local.support = scene.support || "";
      local.cta = scene.cta || "";
      local.ocr = scene.ocr || null;
    });
    if (state.audio.narration_mode === "voiceover") {
      state.audio.script = spokenFromBeats() || state.audio.script;
    }
    paintAll();
    markDirty();
    scheduleQuote();
    if (data.warnings?.length) setStatus(data.warnings.join(" "));
    else setStatus("Roteiro pronto. Edite se precisar e gere o clipe.");
  } catch (error) {
    state.ocrFailed = true;
    setStatus(error.message);
  }
}

function planBody() {
  alignBeatsToScenes();
  const audio = syncAudioMode({ ...state.audio });
  if (audio.narration_mode === "voiceover" && !audio.script) {
    audio.script = spokenFromBeats();
  }
  const singleImage = state.generationMode === "single_image";
  const selected = state.scenes.find((item) => item.id === state.selectedSceneId) || state.scenes[0];
  return {
    client_id: state.clientId || undefined,
    preview_images: state.scenes.map(scene=>scene.image_url||scene.thumb_url).filter(Boolean),
    duration: state.duration,
    seed: singleImage ? null : state.seed,
    quality: singleImage ? "production" : state.quality,
    aspect_ratio: state.aspectRatio,
    aspect_explicit: state.aspectExplicit,
    source: singleImage
      ? { mode: "flattened_still", base_id: selected?.id || "" }
      : { mode: "storyboard", ref_ids: state.scenes.map((item) => item.id) },
    scene_ids: state.scenes.map((item) => item.id),
    ref_ids: state.scenes.map((item) => item.id),
    script: state.script,
    require_refs: !singleImage,
    audio,
    motion: {
      preset: state.motion.preset,
      intensity: state.motion.intensity,
      note: state.motion.note,
    },
  };
}

async function suggestNarration(mode) {
  if (!state.clientId) return;
  const request = ++narrationRequest;
  const buttons = [document.getElementById("mcVideoSuggestNarration"), document.getElementById("mcVideoSuggestVoiceover")];
  const status = document.getElementById(mode === "voiceover" ? "mcVideoVoiceoverHint" : "mcVideoNarrationStatus");
  buttons.forEach((button) => { if (button) button.disabled = true; });
  if (status) status.textContent = "Lendo a peça e preparando uma sugestão…";
  try {
    const result = await post(`${studioApi}/agent/narration`, {
      client_id: state.clientId,
      duration: state.duration,
      creative: {
        scenes: state.scenes.map((scene) => {
          const beat = (state.script?.beats || []).find((item) => item.id === scene.id) || {};
          return {
            name: scene.name || "",
            headline: scene.headline || "",
            support: scene.support || "",
            cta: scene.cta || "",
            spoken: beat.spoken || "",
          };
        }),
      },
    });
    if (request !== narrationRequest) return;
    state.audio.enabled = true;
    state.audio.narration_mode = mode;
    if (mode === "voiceover") state.audio.script = result.script || state.audio.script;
    else state.audio.prompt = result.prompt || state.audio.prompt;
    syncAudioMode(state.audio);
    markDirty();
    scheduleQuote();
    paintAll();
    if (status) status.textContent = result.provider === "ai" ? "Sugestão criada. Revise antes de gerar." : "Rascunho criado com o texto disponível. Revise antes de gerar.";
  } catch (error) {
    if (request === narrationRequest && status) status.textContent = error.message;
  } finally {
    if (request === narrationRequest) buttons.forEach((button) => { if (button) button.disabled = false; });
  }
}

function scheduleQuote() {
  refreshSceneAspects();
  window.clearTimeout(quoteTimer);
  state.quote = null;
  state.quoteError = "";
  state.quoteStatus = "idle";
  paintQuote();
  updateGenerateEnabled();
  quoteTimer = window.setTimeout(refreshQuote, 450);
}

async function refreshQuote() {
  const singleImage = state.generationMode === "single_image";
  if ((singleImage && !state.selectedSceneId) || (!singleImage && (state.scenes.length < 2 || !state.script?.beats?.length))) {
    state.quote = null;
    state.quoteError = "";
    state.quoteStatus = "idle";
    paintQuote();
    updateGenerateEnabled();
    return;
  }
  const request = ++quoteRequest;
  const version = state.requestVersion;
  state.quoteSignature = quoteSignature();
  state.quoteStatus = "loading";
  paintQuote();
  updateGenerateEnabled();
  try {
    const quote = await quoteAnimate(planBody());
    if (request !== quoteRequest || version !== state.requestVersion) return;
    state.quote = quote;
    state.quoteError = quote.voiceover_fits === false
      ? "A locução não cabe nesta duração."
      : "";
    state.quoteStatus = state.quoteError ? "error" : "ready";
    paintQuote();
    updateGenerateEnabled();
  } catch (error) {
    if (request !== quoteRequest || version !== state.requestVersion) return;
    state.quote = null;
    state.quoteError = error.message;
    state.quoteStatus = "error";
    paintQuote();
    updateGenerateEnabled();
  }
}

const VIDEO_CONFIRM_TOKENS = 100000;
const AUDIO_BLOCKED = "[audio_bloqueado]";

// O provedor barrou o áudio gerado: desliga o áudio e deixa o custo atualizado; quem gera de novo é a pessoa.
function retryWithoutAudio() {
  state.audio.enabled = false;
  syncAudioMode(state.audio);
  markDirty();
  scheduleQuote();
  paintAll();
  setStatus("Áudio desligado. Confira o custo e clique em Gerar clipe.");
}

async function generate() {
  const singleImage = state.generationMode === "single_image";
  if (singleImage && !state.selectedSceneId) {
    setStatus("Selecione a imagem que será animada.");
    return;
  }
  if (!singleImage && state.scenes.length < 2) {
    setStatus("Adicione pelo menos duas cenas.");
    return;
  }
  if (!singleImage && !state.script?.beats?.length) {
    setStatus("Monte o roteiro antes de gerar.");
    return;
  }
  const issues = currentIssues();
  const blocker = issues.find((issue) => issue.level === "error");
  if (blocker) {
    setStatus(blocker.message);
    return;
  }
  const warnings = issues.filter((issue) => issue.level === "warn");
  if (warnings.length && !window.confirm(`Antes de gerar, ${warnings.length === 1 ? "há 1 aviso" : `há ${warnings.length} avisos`}:\n\n${warnings.slice(0, 5).map((issue) => `• ${issue.message}`).join("\n")}${warnings.length > 5 ? `\n• e mais ${warnings.length - 5}…` : ""}\n\nGerar mesmo assim?`)) return;
  await state.aspectPending;
  const body = planBody();
  const version = state.requestVersion;
  state.generating = true;
  showProcessing({status:"preparing",message:"Conferindo roteiro, formato e custo…",preview_images:body.preview_images,plan:body});
  updateGenerateEnabled();
  setStatus("Cotando…");
  try {
    const confirmedQuote = await quoteAnimate(body);
    if (version !== state.requestVersion) throw new Error("O projeto mudou. Confira o custo atualizado antes de gerar.");
    // A long or high-resolution clip costs hundreds of thousands of credits: the person confirms the amount first.
    const estimated = Number(confirmedQuote?.estimated_tokens || 0);
    if (estimated >= VIDEO_CONFIRM_TOKENS && !window.confirm(`Este vídeo deve consumir cerca de ${estimated.toLocaleString("pt-BR")} tokens. Gerar mesmo assim?`)) {
      throw new Error("Geração cancelada. Nenhum token foi usado.");
    }
    await persistProject();
    const job = await submitAnimate(body);
    state.jobId = job.job_id || job.public_id || "";
    if (state.jobId) {
      recordSpend(`video:${state.jobId}`, "video", `Geração de vídeo · ${state.duration}s`, job.quote || state.quote, "pending");
      markDirty();
    }
    if (state.jobId) sessionStorage.setItem(JOB_KEY, state.jobId);
    setStatus(job.message || "Gerando o clipe…");
    resume(state.jobId);
  } catch (error) {
    updateProcessing({status:"failed",error:error.message});
    setStatus(error.message);
    state.generating = false;
    updateGenerateEnabled();
  }
}

function resume(jobId) {
  if (!jobId) return;
  state.generating = true;
  updateGenerateEnabled();
  const client=state.clientId;
  startPoll(jobId, async (job) => {
    if(client!==state.clientId)return;
    sessionStorage.removeItem(JOB_KEY);
    const version = job.version || {};
    const follow=followingJob(jobId);
    await loadClips({ prefer: version, restore: false, select:follow });
    recordSpend(`video:${jobId}`, "video", `Geração de vídeo · ${job.plan?.duration || state.duration}s`, job.quote, "confirmed");
    setStatus(job.message || "Clipe pronto.");
    state.generating = false;
    markDirty();
  }, (job) => {
    if(client!==state.clientId)return;
    sessionStorage.removeItem(JOB_KEY);
    const reason = String(job?.error || job?.message || "A animação falhou.");
    const audioBlocked = reason.includes(AUDIO_BLOCKED);
    setStatus(reason.replace(AUDIO_BLOCKED, "").trim(), audioBlocked && state.audio.enabled !== false ? { label: "Tentar sem áudio", onClick: retryWithoutAudio } : null);
    state.generating = false;
    recordSpend(`video:${jobId}`, "video", `Geração de vídeo · ${state.duration}s`, job?.quote, "failed");
    markDirty();
    updateGenerateEnabled();
  });
}

function recordSpend(id, kind, label, quote, status) {
  const existing = state.spend?.events?.find((event) => event.id === id);
  const amountTokens = Number(quote?.estimated_tokens ?? existing?.amount_tokens ?? 0) || 0;
  const amountBrl = Number(quote?.estimated_cost_brl ?? quote?.spent_brl ?? quote?.cost_brl ?? existing?.amount_brl ?? 0) || 0;
  const amountUsd = Number(quote?.estimated_cost_usd ?? quote?.spent_usd ?? quote?.cost_usd ?? existing?.amount_usd ?? 0) || 0;
  upsertWorkspaceSpend({id, kind, label, amount_tokens:amountTokens, amount_brl:amountBrl, amount_usd:amountUsd, status, created_at:new Date().toISOString()});
}
