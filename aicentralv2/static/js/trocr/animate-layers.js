import { animateLayers, mapAnimateCamadas } from "./animate-api.js";
import { $ } from "./animate-utils.js";

const INTENTS = [
  ["protect", "Proteger"],
  ["animate", "Animar"],
  ["hide", "Ocultar"],
];

export function sourceMode() {
  return document.querySelector("input[name=mcAnimateSource]:checked")?.value || "flattened_still";
}

export function selectedToId() {
  return $("mcAnimateToId")?.value || "";
}

export function layerIntents() {
  const mapping = {};
  document.querySelectorAll("[data-layer-intent]").forEach((node) => {
    mapping[node.getAttribute("data-layer-intent")] = node.value;
  });
  return mapping;
}

export function bindLayers(context) {
  document.querySelectorAll("input[name=mcAnimateSource]").forEach((node) => {
    node.addEventListener("change", () => {
      toggleSource();
      refreshLayers(context);
    });
  });
  $("mcAnimateMap")?.addEventListener("click", () => mapNow(context));
  $("mcAnimateToId")?.addEventListener("change", () => paintTransition(context));
}

export async function refreshLayers(context) {
  toggleSource();
  if (sourceMode() === "transition_ab") {
    paintTransition(context);
    return;
  }
  if (sourceMode() !== "protected_scene") return;
  const status = $("mcAnimateMapStatus");
  try {
    const data = await animateLayers({ ...context.ids(), layer_intents: layerIntents() });
    paintLayers(data);
    if (status) {
      status.textContent = data.linked
        ? `Cena ${data.creative_id} · v${data.scene_version}`
        : "Peça ainda sem mapa no Camadas.";
    }
  } catch (error) {
    if (status) status.textContent = error.message;
  }
}

function toggleSource() {
  const mode = sourceMode();
  if ($("mcAnimateLayersWrap")) $("mcAnimateLayersWrap").classList.toggle("hidden", mode !== "protected_scene");
  if ($("mcAnimateTransitionWrap")) $("mcAnimateTransitionWrap").classList.toggle("hidden", mode !== "transition_ab");
  if (mode === "transition_ab") {
    const motion = document.querySelector("input[name=mcAnimateMotion][value=transition]");
    if (motion) motion.checked = true;
  }
  if ($("mcAnimateSourceHint")) {
    $("mcAnimateSourceHint").textContent = {
      protected_scene: "Textos e logos entram depois, como overlay.",
      transition_ab: "Esta transição trava o primeiro e o último quadro. Música de referência não entra.",
    }[mode] || "Texto e logo podem variar no Seedance.";
  }
}

function paintTransition(context) {
  const select = $("mcAnimateToId");
  const stills = (window.__trocrAnimate?.stills?.() || []).filter((item) => item.id !== context.ids()?.base_id);
  if (select && !select.dataset.ready) {
    select.innerHTML = stills.map((item) => (
      `<option value="${escapeHtml(item.id)}">${escapeHtml(item.name || item.id)}</option>`
    )).join("");
    select.dataset.ready = "1";
  } else if (select) {
    const current = select.value;
    select.innerHTML = stills.map((item) => (
      `<option value="${escapeHtml(item.id)}"${item.id === current ? " selected" : ""}>${escapeHtml(item.name || item.id)}</option>`
    )).join("");
  }
  const active = window.__trocrAnimate?.activeStill?.() || {};
  const other = stills.find((item) => item.id === select?.value) || stills[0] || {};
  if ($("mcAnimateThumbA")) $("mcAnimateThumbA").src = active.thumb || active.image || "";
  if ($("mcAnimateThumbB")) $("mcAnimateThumbB").src = other.thumb || other.image || "";
  if ($("mcAnimateCapA")) $("mcAnimateCapA").textContent = `A · ${active.name || active.id || "ativa"}`;
  if ($("mcAnimateCapB")) $("mcAnimateCapB").textContent = other.id ? `B · ${other.name || other.id}` : "B · escolha uma versão";
  const ratio = context.aspectRatio || window.__trocrAnimate?.aspectRatio?.() || "16:9";
  const showSafe = ratio === "4:5";
  $("mcAnimateSafeA")?.classList.toggle("hidden", !showSafe);
  $("mcAnimateSafeB")?.classList.toggle("hidden", !showSafe);
}

function paintLayers(data) {
  const list = $("mcAnimateLayerList");
  const warn = $("mcAnimateUnplaced");
  if (!list) return;
  const layers = data.layers || [];
  list.innerHTML = layers.map((layer) => {
    const options = INTENTS.map(([value, label]) => {
      const selected = (layer.intent || "unplaced") === value ? " selected" : "";
      return `<option value="${value}"${selected}>${label}</option>`;
    }).join("");
    const pending = layer.intent === "unplaced" ? " text-amber-800" : "";
    return `<li class="grid grid-cols-[1fr_auto] items-center gap-2${pending}">
      <span class="truncate">${escapeHtml(layer.label || layer.role || layer.id)}</span>
      <select class="cx-select" data-layer-intent="${escapeHtml(layer.id)}">${options}</select>
    </li>`;
  }).join("");
  if (warn) {
    const pending = (data.unplaced_layer_ids || []).length;
    warn.hidden = !pending;
    warn.textContent = pending
      ? `${pending} camada(s) precisam de revisão antes do envio.`
      : "";
  }
}

async function mapNow(context) {
  const status = $("mcAnimateMapStatus");
  if (status) status.textContent = "Enviando still ao Camadas…";
  try {
    const mapped = await mapAnimateCamadas(context.ids());
    if (status) {
      status.textContent = mapped.reused
        ? `Reusou ${mapped.creative_id}`
        : `Mapeando ${mapped.creative_id}`;
    }
    const radio = document.querySelector("input[name=mcAnimateSource][value=protected_scene]");
    if (radio) radio.checked = true;
    document.dispatchEvent(new CustomEvent("trocr:camadas-linked", { detail: mapped }));
    await refreshLayers(context);
  } catch (error) {
    if (status) status.textContent = error.message;
  }
}

function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
