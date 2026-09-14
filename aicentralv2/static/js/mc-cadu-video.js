import { quoteAnimate, submitAnimate } from "./trocr/animate-api.js";
import { showVideo } from "./trocr/animate-player.js";
import { startPoll } from "./trocr/animate-poller.js";
import { $, csrf } from "./trocr/animate-utils.js";

const JOB_KEY = "cx-cadu-video-job";
const Desk = window.McDeskBrand || {
  read() { return ""; },
  write() {},
};

const state = {
  clientId: "",
  library: [],
  scenes: [],
  script: null,
  clips: [],
  jobId: "",
  activeClipId: "",
};

boot();

async function boot() {
  const params = new URLSearchParams(window.location.search);
  state.activeClipId = params.get("clip") || "";
  document.addEventListener("cadu:brand-ready", (event) => applyBrand(event.detail?.clientId));
  document.addEventListener("cadu:brand-change", (event) => {
    applyBrand(event.detail?.clientId, { reset: true });
  });
  $("mcVideoFile")?.addEventListener("change", () => takeFile($("mcVideoFile").files?.[0]));
  $("mcVideoLibrary")?.addEventListener("click", onLibraryClick);
  $("mcVideoScenes")?.addEventListener("click", onSceneClick);
  $("mcVideoScriptBtn")?.addEventListener("click", buildScript);
  $("mcVideoGenerate")?.addEventListener("click", generate);
  $("mcVideoClips")?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-clip]");
    if (!button) return;
    const clip = state.clips.find((item) => item.id === button.getAttribute("data-clip"));
    if (clip) selectClip(clip);
  });
  await applyBrand(params.get("client") || Desk.read());
  const pending = sessionStorage.getItem(JOB_KEY);
  if (pending) resume(pending);
}

function currentBrand(id) {
  return String(id || Desk.read() || $("mcCaduBarClient")?.value || "").trim();
}

async function applyBrand(id, { reset = false } = {}) {
  const next = currentBrand(id);
  if (!next) {
    if ($("mcVideoLibHint")) $("mcVideoLibHint").textContent = "Escolha a marca na barra para ver as peças.";
    return;
  }
  if (next === state.clientId && !reset) {
    if (!state.library.length) await loadLibrary();
    if (!state.clips.length) await loadClips();
    return;
  }
  state.clientId = next;
  if (reset) {
    state.scenes = [];
    state.script = null;
    state.activeClipId = "";
    if ($("mcVideoScript")) $("mcVideoScript").value = "";
    paintScenes();
  }
  await loadLibrary();
  await loadClips();
}

async function loadLibrary() {
  const list = $("mcVideoLibrary");
  if (!list) return;
  if (!state.clientId) {
    list.innerHTML = "";
    $("mcVideoLibHint").textContent = "Escolha a marca na barra para ver as peças.";
    return;
  }
  try {
    const data = await get(`/parametros/api/format-lab/swap/library?client_id=${encodeURIComponent(state.clientId)}&media=still`);
    state.library = data.items || [];
    paintLibrary();
    $("mcVideoLibHint").textContent = state.library.length
      ? "Selecione as cenas. A ordem é a do clipe."
      : "Ainda não há peça nesta marca. Ajuste uma ou solte um still extra.";
  } catch (error) {
    $("mcVideoLibHint").textContent = error.message;
  }
}

async function loadClips(opts = {}) {
  if (!state.clientId) return;
  try {
    const data = await get(`/parametros/api/format-lab/swap/library?client_id=${encodeURIComponent(state.clientId)}&media=video`);
    state.clips = (data.items || []).filter((item) => item.video_url);
  } catch (_error) {
    if (!opts.prefer) state.clips = [];
  }
  const chosen = pickClip(opts.prefer);
  if (chosen) selectClip(chosen);
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
    };
    state.clips = [synthetic, ...state.clips.filter((item) => item.video_url !== synthetic.video_url)];
    return synthetic;
  }
  if (state.activeClipId) {
    const current = state.clips.find((item) => (
      item.id === state.activeClipId || item.job_id === state.activeClipId
    ));
    if (current) return current;
  }
  return state.clips[0] || null;
}

function selectClip(clip) {
  if (!clip?.video_url) return;
  state.activeClipId = clip.id || clip.job_id || "";
  showVideo(clip);
  paintClips();
}

function paintLibrary() {
  const list = $("mcVideoLibrary");
  if (!list) return;
  list.innerHTML = state.library.map((item) => {
    const selected = state.scenes.some((scene) => scene.id === item.id);
    return `<li>
      <button type="button" data-id="${escapeHtml(item.id)}" class="${selected ? "is-selected" : ""}">
        ${item.thumb_url || item.image_url ? `<img src="${escapeHtml(item.thumb_url || item.image_url)}" alt="">` : "<span></span>"}
        <strong>${escapeHtml(item.name || "Peça")}</strong>
      </button>
    </li>`;
  }).join("");
}

function paintScenes() {
  const list = $("mcVideoScenes");
  const count = state.scenes.length;
  if ($("mcVideoSceneCount")) $("mcVideoSceneCount").textContent = String(count);
  if (list) {
    list.innerHTML = state.scenes.map((item, index) => `
      <li>
        <button type="button" data-remove="${escapeHtml(item.id)}">
          <em>${index + 1}</em>
          <strong>${escapeHtml(item.name || "Cena")}</strong>
          Remover
        </button>
      </li>`).join("");
  }
  const ready = count >= 2 && count <= 30;
  if ($("mcVideoSceneHint")) {
    $("mcVideoSceneHint").textContent = count < 2
      ? "Selecione pelo menos duas cenas."
      : count > 30
        ? "O Seedance aceita no máximo 30 cenas."
        : `${count} cenas na ordem do clipe.`;
  }
  if ($("mcVideoScriptBtn")) $("mcVideoScriptBtn").disabled = !ready;
  if ($("mcVideoGenerate")) $("mcVideoGenerate").disabled = !ready || !state.script;
  paintLibrary();
}

function paintClips() {
  const list = $("mcVideoClips");
  if (!list) return;
  list.hidden = false;
  list.innerHTML = state.clips.map((item) => {
    const current = item.id === state.activeClipId;
    const poster = item.poster_url || item.thumb_url || item.image_url || "";
    const seconds = Number(item.duration || 0);
    return `<li>
      <button type="button" data-clip="${escapeHtml(item.id)}" class="${current ? "is-current" : ""}">
        ${poster ? `<img src="${escapeHtml(poster)}" alt="">` : `<span class="mc-cadu-video-clip-ph"></span>`}
        <strong>${escapeHtml(item.name || "Clipe")}</strong>
        ${seconds ? `<small>${Math.round(seconds)}s</small>` : ""}
      </button>
    </li>`;
  }).join("");
}

function onLibraryClick(event) {
  const button = event.target.closest("[data-id]");
  if (!button) return;
  const item = state.library.find((row) => row.id === button.getAttribute("data-id"));
  if (!item) return;
  if (state.scenes.some((scene) => scene.id === item.id)) {
    state.scenes = state.scenes.filter((scene) => scene.id !== item.id);
  } else if (state.scenes.length < 30) {
    state.scenes.push(item);
  }
  state.script = null;
  if ($("mcVideoScript")) $("mcVideoScript").value = "";
  paintScenes();
}

function onSceneClick(event) {
  const button = event.target.closest("[data-remove]");
  if (!button) return;
  state.scenes = state.scenes.filter((scene) => scene.id !== button.getAttribute("data-remove"));
  state.script = null;
  if ($("mcVideoScript")) $("mcVideoScript").value = "";
  paintScenes();
}

async function takeFile(file) {
  if (!file || !String(file.type || "").startsWith("image/")) return;
  const reader = new FileReader();
  reader.onload = async () => {
    try {
      const item = await post("/parametros/api/format-lab/swap/library", {
        client_id: state.clientId || undefined,
        image: String(reader.result || ""),
        name: file.name || "Cena",
      });
      state.library.unshift(item);
      if (state.scenes.length < 30) state.scenes.push(item);
      paintLibrary();
      paintScenes();
    } catch (error) {
      setStatus(error.message);
    }
  };
  reader.readAsDataURL(file);
}

async function buildScript() {
  if (state.scenes.length < 2) {
    setStatus("Selecione pelo menos duas cenas.");
    return;
  }
  setStatus("Lendo as cenas…");
  try {
    const data = await post("/parametros/api/format-lab/swap/animate/script", {
      client_id: state.clientId || undefined,
      duration: duration(),
      scene_ids: state.scenes.map((item) => item.id),
    });
    state.script = data.script;
    if ($("mcVideoScript")) $("mcVideoScript").value = scriptText(state.script);
    paintScenes();
    setStatus("Roteiro pronto. Edite se precisar e gere o clipe.");
  } catch (error) {
    setStatus(error.message);
  }
}

async function generate() {
  if (state.scenes.length < 2) {
    setStatus("Selecione pelo menos duas cenas.");
    return;
  }
  state.script = parseScript($("mcVideoScript")?.value, state.script);
  if (!state.script) {
    setStatus("Monte o roteiro antes de gerar.");
    return;
  }
  const body = {
    client_id: state.clientId || undefined,
    duration: duration(),
    quality: quality(),
    source: { mode: "storyboard", ref_ids: state.scenes.map((item) => item.id) },
    scene_ids: state.scenes.map((item) => item.id),
    ref_ids: state.scenes.map((item) => item.id),
    script: state.script,
    require_refs: true,
  };
  setStatus("Cotando…");
  try {
    await quoteAnimate(body);
    const job = await submitAnimate(body);
    state.jobId = job.job_id || job.public_id || "";
    if (state.jobId) sessionStorage.setItem(JOB_KEY, state.jobId);
    setStatus(job.message || "Gerando o clipe…");
    resume(state.jobId);
  } catch (error) {
    setStatus(error.message);
  }
}

function resume(jobId) {
  if (!jobId) return;
  startPoll(jobId, async (job) => {
    sessionStorage.removeItem(JOB_KEY);
    const version = job.version || {};
    await loadClips({ prefer: version });
    setStatus(job.message || "Clipe pronto.");
  }, (job) => {
    sessionStorage.removeItem(JOB_KEY);
    setStatus(job?.error || job?.message || "A animação falhou.");
  });
}

function duration() {
  return Number(document.querySelector('input[name="mcVideoDuration"]:checked')?.value || 8);
}

function quality() {
  return document.querySelector('input[name="mcVideoQuality"]:checked')?.value || "draft";
}

function scriptText(script) {
  return ((script || {}).beats || []).map((beat, index) => (
    `Cena ${index + 1} — ${beat.purpose || "beat"}\nVisual: ${beat.visual || ""}\nMovimento: ${beat.motion || ""}\nTrava: ${beat.hold || ""}${beat.spoken ? `\nFala: ${beat.spoken}` : ""}`
  )).join("\n\n");
}

function parseScript(text, fallback) {
  const blocks = String(text || "").split(/\n\s*\n/).map((item) => item.trim()).filter(Boolean);
  if (!blocks.length) return fallback;
  const beats = blocks.map((block, index) => {
    const lines = block.split("\n");
    const head = lines[0] || "";
    const purpose = (head.split("—")[1] || fallback?.beats?.[index]?.purpose || "beat").trim();
    const pick = (label) => {
      const line = lines.find((row) => row.toLowerCase().startsWith(label));
      return line ? line.slice(label.length).trim() : "";
    };
    return {
      id: state.scenes[index]?.id || fallback?.beats?.[index]?.id || `scene-${index + 1}`,
      purpose,
      visual: pick("visual:") || fallback?.beats?.[index]?.visual || "",
      motion: pick("movimento:") || fallback?.beats?.[index]?.motion || "",
      hold: pick("trava:") || fallback?.beats?.[index]?.hold || "",
      spoken: pick("fala:") || "",
    };
  });
  return { beats };
}

function setStatus(message) {
  if ($("mcAnimateStatus")) $("mcAnimateStatus").textContent = message || "";
}

async function get(url) {
  const response = await fetch(url, { credentials: "same-origin", headers: { Accept: "application/json" } });
  return parse(response);
}

async function post(url, body) {
  const response = await fetch(url, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      "X-Trocr-CSRF-Token": csrf(),
    },
    body: JSON.stringify(body || {}),
  });
  return parse(response);
}

async function parse(response) {
  const payload = await response.json().catch(() => ({}));
  if (!response.ok || payload.success === false) {
    throw new Error(payload.error || "A mesa de vídeo não respondeu.");
  }
  return payload.data !== undefined ? payload.data : payload;
}

function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
