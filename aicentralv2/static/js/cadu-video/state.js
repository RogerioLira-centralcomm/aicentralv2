export const JOB_KEY = "cx-cadu-video-job";

export function normalizeAudioState(raw = {}) {
  const audio = raw && typeof raw === "object" ? raw : {};
  const legacy = audio.mode || "ambient";
  const hasComposition = ["enabled", "ambience", "narration_mode", "music_enabled"]
    .some((key) => Object.prototype.hasOwnProperty.call(audio, key));
  const result = {
    mode: legacy,
    enabled: hasComposition ? audio.enabled !== false : legacy !== "silence",
    ambience: hasComposition ? Boolean(audio.ambience) : legacy === "ambient",
    ambience_note: String(audio.ambience_note || ""),
    narration_mode: hasComposition
      ? (["guided", "voiceover"].includes(audio.narration_mode) ? audio.narration_mode : "none")
      : (legacy === "voice" ? "guided" : legacy === "voiceover" ? "voiceover" : "none"),
    music_enabled: hasComposition ? Boolean(audio.music_enabled) : legacy === "music",
    script: String(audio.script || ""),
    voice: audio.voice === "female" ? "female" : "male",
    pace: audio.pace === "fast" ? "fast" : "normal",
    prompt: String(audio.prompt || ""),
    music_note: String(audio.music_note || ""),
  };
  return syncAudioMode(result);
}

export function syncAudioMode(audio) {
  if (!audio.enabled) audio.mode = "silence";
  else if (audio.narration_mode === "voiceover") audio.mode = "voiceover";
  else if (audio.narration_mode === "guided") audio.mode = "voice";
  else if (audio.music_enabled) audio.mode = "music";
  else audio.mode = "ambient";
  return audio;
}

export function normalizeWorkspaceSpend(raw = {}) {
  const events = Array.isArray(raw?.events) ? raw.events : [];
  return {
    events: events.slice(-200).map((event) => ({
      id: String(event?.id || "").slice(0, 160),
      kind: ["video", "voice", "image", "edit"].includes(event?.kind) ? event.kind : "edit",
      label: String(event?.label || "Operação").slice(0, 160),
      amount_tokens: Math.max(0, Number(event?.amount_tokens) || 0),
      amount_brl: Math.max(0, Number(event?.amount_brl) || 0),
      amount_usd: Math.max(0, Number(event?.amount_usd) || 0),
      status: ["pending", "confirmed", "failed"].includes(event?.status) ? event.status : "pending",
      created_at: String(event?.created_at || new Date().toISOString()).slice(0, 40),
    })).filter((event) => event.id),
  };
}

export function upsertWorkspaceSpend(event) {
  state.spend = normalizeWorkspaceSpend(state.spend);
  const packed = normalizeWorkspaceSpend({ events: [event] }).events[0];
  if (!packed) return;
  const index = state.spend.events.findIndex((item) => item.id === packed.id);
  if (index >= 0) state.spend.events[index] = { ...state.spend.events[index], ...packed };
  else state.spend.events.push(packed);
  state.spend.events = state.spend.events.slice(-200);
}

export function workspaceSpendTotals() {
  const events = normalizeWorkspaceSpend(state.spend).events;
  return {
    confirmed_tokens: events.filter((event) => event.status === "confirmed").reduce((sum, event) => sum + event.amount_tokens, 0),
    pending_tokens: events.filter((event) => event.status === "pending").reduce((sum, event) => sum + event.amount_tokens, 0),
    confirmed_brl: events.filter((event) => event.status === "confirmed").reduce((sum, event) => sum + event.amount_brl, 0),
    pending_brl: events.filter((event) => event.status === "pending").reduce((sum, event) => sum + event.amount_brl, 0),
    confirmed_count: events.filter((event) => event.status === "confirmed").length,
    events,
  };
}

export const Desk = window.McDeskBrand || {
  read() { return ""; },
  write() {},
};

export const state = {
  clientId: "",
  library: [],
  clips: [],
  sounds: [],
  scenes: [],
  script: null,
  ocrFailed: false,
  jobId: "",
  activeClipId: "",
  selectedSceneId: "",
  libTab: "still",
  panelTab: "scene",
  previewMode: "scene",
  saveStatus: "saved",
  quoteStatus: "idle",
  generating: false,
  creatingScene2: false,
  requestVersion: 0,
  search: "",
  name: "",
  projectId: "",
  projects: [],
  seed: null,
  generationMode: "storyboard",
  aspectRatio: "16:9",
  aspectExplicit: false,
  aspectPending: null,
  duration: 8,
  quality: "draft",
  audio: {
    mode: "ambient",
    enabled: true,
    ambience: true,
    ambience_note: "",
    narration_mode: "none",
    music_enabled: false,
    script: "",
    voice: "male",
    pace: "normal",
    prompt: "",
    music_note: "",
  },
  motion: {
    preset: "live",
    intensity: "subtle",
    note: "",
  },
  spend: { events: [] },
  quote: null,
  quoteError: "",
  saving: false,
  dirty: false,
  dragSceneId: "",
};

export function resetProjectFields() {
  state.clipEdits={};state.aspectExplicit=false;state.aspectPending=null;state.composition=null;
  state.scenes = [];
  state.script = null;
  state.ocrFailed = false;
  state.activeClipId = "";
  state.selectedSceneId = "";
  state.name = "";
  state.seed = null;
  state.generationMode = "storyboard";
  state.aspectRatio = "16:9";
  state.duration = 8;
  state.quality = "draft";
  state.audio = {
    mode: "ambient",
    enabled: true,
    ambience: true,
    ambience_note: "",
    narration_mode: "none",
    music_enabled: false,
    script: "",
    voice: "male",
    pace: "normal",
    prompt: "",
    music_note: "",
  };
  state.motion = {
    preset: "live",
    intensity: "subtle",
    note: "",
  };
  state.spend = { events: [] };
  state.quote = null;
  state.quoteError = "";
  state.previewMode = "scene";
  state.saveStatus = "saved";
  state.quoteStatus = "idle";
  state.generating = false;
  state.creatingScene2 = false;
  state.requestVersion += 1;
  state.dirty = false;
}

export function beatFor(sceneId) {
  return (state.script?.beats || []).find((beat) => beat.id === sceneId) || null;
}

export function ensureBeat(sceneId) {
  if (!state.script || !Array.isArray(state.script.beats)) {
    state.script = { beats: [] };
  }
  let beat = state.script.beats.find((item) => item.id === sceneId);
  if (!beat) {
    beat = {
      id: sceneId,
      purpose: "beat",
      visual: "",
      motion: "Avança para a próxima peça sem saltar.",
      hold: "",
      spoken: "",
    };
    state.script.beats.push(beat);
  }
  return beat;
}

export function alignBeatsToScenes() {
  if (!state.script || !Array.isArray(state.script.beats)) {
    state.script = { beats: state.scenes.map((scene) => ({
      id: scene.id,
      purpose: "beat",
      visual: scene.headline || scene.name || "",
      motion: "Avança para a próxima peça sem saltar.",
      hold: "",
      spoken: "",
    })) };
    return;
  }
  const byId = new Map(state.script.beats.map((beat) => [beat.id, beat]));
  state.script.beats = state.scenes.map((scene) => {
    const prev = byId.get(scene.id);
    return prev || {
      id: scene.id,
      purpose: "beat",
      visual: scene.headline || scene.name || "",
      motion: "Avança para a próxima peça sem saltar.",
      hold: "",
      spoken: "",
    };
  });
}

export function spokenFromBeats() {
  return ((state.script || {}).beats || [])
    .map((beat) => String(beat.spoken || "").trim())
    .filter(Boolean)
    .join(" ");
}
