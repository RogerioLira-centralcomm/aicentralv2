import { csrf } from "../trocr/animate-utils.js";

async function parse(response) {
  const payload = await response.json().catch(() => ({}));
  if (!response.ok || payload.success === false) {
    throw new Error(payload.error || "A mesa de vídeo não respondeu.");
  }
  return payload.data !== undefined ? payload.data : payload;
}

export async function get(url) {
  const response = await fetch(url, {
    credentials: "same-origin",
    headers: { Accept: "application/json" },
  });
  return parse(response);
}

export async function post(url, body) {
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

export async function deleteLibrary(body) {
  const response = await fetch("/parametros/api/format-lab/swap/library", {
    method: "DELETE",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      "X-Trocr-CSRF-Token": csrf(),
    },
    body: JSON.stringify(body || {}),
  });
  return parse(response);
}

export function loadVideoProject(clientId) {
  return get(`/parametros/api/format-lab/swap/video-project?client_id=${encodeURIComponent(clientId)}`);
}

export function saveVideoProject(body) {
  return post("/parametros/api/format-lab/swap/video-project", body);
}
