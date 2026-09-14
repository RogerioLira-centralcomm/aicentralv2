export const JOB_KEY = "cx-cadu-video-job";

export const Desk = window.McDeskBrand || {
  read() { return ""; },
  write() {},
};

export const state = {
  clientId: "",
  library: [],
  clips: [],
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
  requestVersion: 0,
  search: "",
  name: "",
  seed: null,
  aspectRatio: "16:9",
  duration: 8,
  quality: "draft",
  audio: {
    mode: "ambient",
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
  quote: null,
  quoteError: "",
  saving: false,
  dirty: false,
  dragSceneId: "",
};

export function resetProjectFields() {
  state.scenes = [];
  state.script = null;
  state.ocrFailed = false;
  state.activeClipId = "";
  state.selectedSceneId = "";
  state.name = "";
  state.seed = null;
  state.aspectRatio = "16:9";
  state.duration = 8;
  state.quality = "draft";
  state.audio = {
    mode: "ambient",
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
  state.quote = null;
  state.quoteError = "";
  state.previewMode = "scene";
  state.saveStatus = "saved";
  state.quoteStatus = "idle";
  state.generating = false;
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
