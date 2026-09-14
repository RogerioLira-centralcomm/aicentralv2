import { bindStudio, resetStudio, recordStudioChange, defaultEdit, paintStudio } from "./cadu-video/studio.js";
import { quoteAnimate, submitAnimate } from "./trocr/animate-api.js";
import { startPoll } from "./trocr/animate-poller.js";
import { deleteLibrary, get, loadVideoProject, post, saveVideoProject } from "./cadu-video/api.js";
import {
  clearClip,
  paintAll,
  paintCanvas,
  paintClips,
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
  ensureBeat,
  normalizeAudioState,
  normalizeWorkspaceSpend,
  resetProjectFields,
  spokenFromBeats,
  state,
  syncAudioMode,
  upsertWorkspaceSpend,
} from "./cadu-video/state.js";
import { parseScript, scriptText } from "./cadu-video/utils.js";

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
  document.addEventListener("cadu:brand-ready", (event) => applyBrand(event.detail?.clientId));
  document.addEventListener("cadu:brand-change", (event) => {
    applyBrand(event.detail?.clientId, { reset: true });
  });
  await applyBrand(params.get("client") || Desk.read());
  const pending = sessionStorage.getItem(JOB_KEY);
  if (pending) resume(pending);
}

function bindUi() {
  document.getElementById("mcVideoFile")?.addEventListener("change", (event) => {
    takeFile(event.target.files?.[0]);
  });
  bindDrop(document.getElementById("mcVideoLibDrop"));
  document.getElementById("mcVideoLibrary")?.addEventListener("click", onLibraryClick);
  document.getElementById("mcVideoClips")?.addEventListener("click", onClipClick);
  document.getElementById("mcVideoScriptBtn")?.addEventListener("click", buildScript);
  document.getElementById("mcVideoCreateScene2")?.addEventListener("click", createScene2WithTrocr);
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
  document.getElementById("mcVideoAspect")?.addEventListener("change", (event) => {
    state.aspectRatio = event.target.value || "16:9";
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
  document.getElementById("mcVideoScript")?.addEventListener("change", (event) => {
    state.script = parseScript(event.target.value, state.script, state.scenes);
    alignBeatsToScenes();
    markDirty();
    scheduleQuote();
    paintAll();
  });
  ["mcVideoBeatPurpose", "mcVideoBeatVisual", "mcVideoBeatMotion", "mcVideoBeatHold", "mcVideoBeatSpoken"]
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
    const node = event.target.closest("[data-scene]");
    if (!node) return;
    selectScene(node.getAttribute("data-scene"));
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
    applyProject(data.project || {});
  } catch (error) {
    setStatus(`Não foi possível abrir o projeto: ${error.message}`);
  }
  if (state.activeClipId) {
    const clip = state.clips.find((item) => item.id === state.activeClipId || item.job_id === state.activeClipId);
    if (clip) await selectClip(clip, { restore: false });
  }
}

function applyProject(project) {
  if (!project || typeof project !== "object") return;
  state.edit = { ...defaultEdit(), ...(project.edit || {}) };
  state.seed = project.seed ?? null;
  state.generationMode = project.generation_mode === "single_image" ? "single_image" : "storyboard";
  state.name = project.name || state.name;
  state.aspectRatio = project.aspect_ratio || state.aspectRatio;
  state.duration = Number(project.duration || state.duration) || 8;
  state.quality = project.quality || state.quality;
  state.activeClipId = project.active_clip_id || state.activeClipId;
  state.selectedSceneId = project.selected_scene_id || state.selectedSceneId;
  if (project.script && Array.isArray(project.script.beats)) state.script = project.script;
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
      duration: state.duration,
      quality: state.quality,
      scene_ids: state.scenes.map((item) => item.id),
      script: state.script,
      audio: state.audio,
      edit: state.edit,
      seed: state.seed,
      generation_mode: state.generationMode,
      motion: state.motion,
      spend: state.spend,
      active_clip_id: state.activeClipId,
      selected_scene_id: state.selectedSceneId,
    },
  };
}

function markDirty() {
  recordStudioChange();
  paintStudio();
  state.dirty = true;
  state.saveStatus = "pending";
  state.quote = null;
  state.quoteError = "";
  state.quoteStatus = "idle";
  state.requestVersion += 1;
  paintSaveStatus();
  paintQuote();
  updateGenerateEnabled();
  scheduleSave();
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
    await saveVideoProject(projectPayload());
    if (clientId === state.clientId && request === saveRequest && version === state.requestVersion) {
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
    const data = await get(`/parametros/api/format-lab/swap/library?client_id=${encodeURIComponent(clientId)}&media=still`);
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

async function createScene2WithTrocr() {
  if (state.creatingScene2 || state.scenes.length !== 1 || !state.clientId) return;
  const base = state.scenes[0];
  const reference = base.image_url || base.image;
  if (!reference) {
    setStatus("A primeira cena não possui uma imagem disponível.");
    return;
  }
  const copy = { ...(base.ocr || {}), ...(base.params || {}) };
  const before = new Set(state.library.map((item) => item.id));
  state.creatingScene2 = true;
  paintProps();
  setStatus("Trocr está criando uma segunda tomada coerente com a primeira…");
  try {
    const data = await post("/parametros/api/format-lab/swap", {
      client_id: state.clientId,
      reference,
      base_id: base.version_id || String(base.id || "").split(":").pop(),
      run_id: base.run_id || undefined,
      aspect_ratio: state.aspectRatio || base.aspect_ratio || "16:9",
      quality: "production",
      force_image: true,
      use_brand_context: true,
      scene_variant: 2,
      scene_index: 2,
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
      note: "Crie uma segunda tomada da mesma campanha, preserve elenco, produto, marca e texto; varie enquadramento e ambiente para continuar a narrativa.",
    });
    if (!data?.image_url && !data?.png_data_url) throw new Error(data?.preview || "O Trocr não devolveu a cena 2.");
    recordSpend(`trocr:${data.plan_hash || data.image_url || Date.now()}`, "image", "Cena 2 com Trocr", data.quote, "confirmed");
    markDirty();
    const items = await loadLibrary();
    const created = items.find((item) => !before.has(item.id) && (
      item.image_url === data.image_url ||
      (item.run_id === base.run_id && Number(item.scene_index) === 2)
    ));
    if (!created) throw new Error("A cena foi gerada, mas não apareceu na biblioteca. Recarregue o Studio.");
    state.scenes = [base, created];
    state.selectedSceneId = created.id;
    state.generationMode = "storyboard";
    alignBeatsToScenes();
    markDirty();
    setStatus("Cena 2 pronta. Revise as duas tomadas e monte o roteiro.");
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
    const data = await get(`/parametros/api/format-lab/swap/library?client_id=${encodeURIComponent(clientId)}&media=video`);
    if (clientId !== state.clientId) return;
    state.clips = (data.items || []).filter((item) => item.video_url);
  } catch (_error) {
    if (!opts.prefer) state.clips = [];
  }
  const chosen = pickClip(opts.prefer);
  if (chosen) await selectClip(chosen, { restore: Boolean(opts.restore) });
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

async function selectClip(clip, { restore = true } = {}) {
  if (!clip?.video_url) return;
  state.activeClipId = clip.id || clip.job_id || "";
  state.previewMode = "clip";
  const still = document.getElementById("mcVideoStill");
  if (still) still.hidden = true;
  playClip(clip);
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
  if (state.generationMode === "single_image") adoptSelectedAspect();
  state.previewMode = "scene";
  const empty = document.getElementById("mcVideoEmpty");
  if (empty) empty.hidden = true;
  paintAll();
  markDirty();
  scheduleQuote();
}

function adoptSelectedAspect(item = null) {
  const selected = item || state.scenes.find((row) => row.id === state.selectedSceneId);
  const ratio = String(selected?.aspect_ratio || "");
  if (["16:9", "9:16", "1:1", "4:3", "3:4", "21:9"].includes(ratio)) state.aspectRatio = ratio;
}

function stepScene(delta) {
  if (!state.scenes.length) return;
  const current = Math.max(0, state.scenes.findIndex((item) => item.id === state.selectedSceneId));
  const next = (current + delta + state.scenes.length) % state.scenes.length;
  selectScene(state.scenes[next].id);
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
  const item = state.library.find((row) => row.id === id);
  if (!item || item.broken) return;
  if (state.scenes.some((scene) => scene.id === item.id)) {
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
      const item = await post("/parametros/api/format-lab/swap/library", {
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
    const data = await deleteLibrary({
      client_id: state.clientId || undefined,
      id,
      media: "video",
    });
    state.clips = (data.items || []).filter((item) => item.video_url);
    if (state.activeClipId === id) {
      state.activeClipId = "";
      state.previewMode = "scene";
      clearClip();
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
    const data = await post("/parametros/api/format-lab/swap/animate/script", {
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
  const scriptNode = document.getElementById("mcVideoScript");
  if (scriptNode?.value) {
    state.script = parseScript(scriptNode.value, state.script, state.scenes) || state.script;
  }
  alignBeatsToScenes();
  const audio = syncAudioMode({ ...state.audio });
  if (audio.narration_mode === "voiceover" && !audio.script) {
    audio.script = spokenFromBeats();
  }
  const singleImage = state.generationMode === "single_image";
  const selected = state.scenes.find((item) => item.id === state.selectedSceneId) || state.scenes[0];
  return {
    client_id: state.clientId || undefined,
    duration: state.duration,
    seed: singleImage ? null : state.seed,
    quality: singleImage ? "production" : state.quality,
    aspect_ratio: state.aspectRatio,
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
    const result = await post("/parametros/api/format-lab/studio/agent/narration", {
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
  const body = planBody();
  const version = state.requestVersion;
  state.generating = true;
  updateGenerateEnabled();
  setStatus("Cotando…");
  try {
    await quoteAnimate(body);
    if (version !== state.requestVersion) throw new Error("O projeto mudou. Confira o custo atualizado antes de gerar.");
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
    setStatus(error.message);
    state.generating = false;
    updateGenerateEnabled();
  }
}

function resume(jobId) {
  if (!jobId) return;
  state.generating = true;
  updateGenerateEnabled();
  startPoll(jobId, async (job) => {
    sessionStorage.removeItem(JOB_KEY);
    const version = job.version || {};
    await loadClips({ prefer: version, restore: false });
    const clip = pickClip(version);
    if (clip) await selectClip(clip, { restore: false });
    recordSpend(`video:${jobId}`, "video", `Geração de vídeo · ${job.plan?.duration || state.duration}s`, job.quote, "confirmed");
    setStatus(job.message || "Clipe pronto.");
    state.generating = false;
    state.previewMode = "clip";
    markDirty();
  }, (job) => {
    sessionStorage.removeItem(JOB_KEY);
    setStatus(job?.error || job?.message || "A animação falhou.");
    state.generating = false;
    recordSpend(`video:${jobId}`, "video", `Geração de vídeo · ${state.duration}s`, job?.quote, "failed");
    markDirty();
    updateGenerateEnabled();
  });
}

function recordSpend(id, kind, label, quote, status) {
  const existing = state.spend?.events?.find((event) => event.id === id);
  const amountBrl = Number(quote?.estimated_cost_brl ?? quote?.spent_brl ?? quote?.cost_brl ?? existing?.amount_brl ?? 0) || 0;
  const amountUsd = Number(quote?.estimated_cost_usd ?? quote?.spent_usd ?? quote?.cost_usd ?? existing?.amount_usd ?? 0) || 0;
  upsertWorkspaceSpend({id, kind, label, amount_brl:amountBrl, amount_usd:amountUsd, status, created_at:new Date().toISOString()});
}
