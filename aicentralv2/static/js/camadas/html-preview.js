import { patchScene } from "./api.js";
import { composeScene } from "./utils.js";

const RENDER = "camadas:render";
const SELECT = "camadas:select";
const EDIT = "camadas:edit";

export function bindHtmlPreview(store, history, setStatus) {
  const pane = document.getElementById("mcCv2HtmlPane");
  const frame = document.getElementById("mcHtmlStage");
  if (!pane || !frame) return;
  let ready = false;
  let lastPayload = "";

  function send() {
    const state = store.getState();
    const htmlMode = state.stageMode === "html";
    pane.classList.toggle("hidden", !htmlMode);
    pane.hidden = !htmlMode;
    if (!htmlMode) {
      lastPayload = "";
      return;
    }
    if (!ready || !frame.contentWindow) return;
    const scene = composeScene(state);
    const payload = JSON.stringify(scene);
    if (payload === lastPayload) return;
    lastPayload = payload;
    frame.contentWindow.postMessage(
      { type: RENDER, scene },
      window.location.origin,
    );
  }

  frame.addEventListener("load", () => {
    ready = true;
    send();
  });
  if (frame.contentDocument?.readyState === "complete") {
    ready = true;
  }

  window.addEventListener("message", async (event) => {
    if (event.origin !== window.location.origin) return;
    if (event.source !== frame.contentWindow) return;
    if (event.data?.type === SELECT) {
      store.setState({ selectedLayerId: event.data.layerId || null });
      return;
    }
    if (event.data?.type !== EDIT) return;
    const layerId = event.data.layerId;
    const properties = event.data.properties || {};
    if (!layerId || !store.getState().creative) return;
    history?.push();
    try {
      const saved = await persistScene(store, [{
        operation: "update",
        layer_id: layerId,
        properties,
      }]);
      store.setState((state) => ({
        scene: saved.scene,
        sceneVersion: saved.scene_version,
        layers: syncLayers(state.layers, saved.scene),
        dirty: false,
      }));
    } catch (error) {
      setStatus?.(error.message || "Não gravei o texto da cena.");
    }
  });

  store.subscribe(send);
  send();
}

export async function persistScene(store, operations) {
  const state = store.getState();
  return patchScene(state.creative.id, {
    version: state.sceneVersion || 1,
    operations,
  });
}

function syncLayers(layers, scene) {
  const byId = new Map((scene?.layers || []).map((item) => [item.id, item]));
  return (layers || []).map((layer) => {
    const next = byId.get(layer.id);
    if (!next) return layer;
    return {
      ...layer,
      text: next.text ?? layer.text,
      visible: next.visible,
      z_index: next.z_index,
      label: next.label || layer.label,
      bbox: {
        ...(layer.bbox || {}),
        x: next.x,
        y: next.y,
        w: next.width,
        h: next.height,
      },
    };
  });
}
