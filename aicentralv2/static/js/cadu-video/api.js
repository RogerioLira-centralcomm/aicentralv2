import { csrf } from "../trocr/animate-utils.js";

async function parse(response) {
  const payload = await response.json().catch(() => ({}));
  if (!response.ok || payload.success === false) {
    const error = new Error(payload.error || "A mesa de vídeo não respondeu.");
    error.status = response.status;
    error.code = payload.code;
    throw error;
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

const projectVersions = new Map();
const projectsUrl = '/parametros/api/format-lab/studio/projects';

export async function loadVideoProject(clientId) {
  const key = String(clientId);
  projectVersions.delete(key);
  const list = await get(`${projectsUrl}?client_id=${encodeURIComponent(key)}`);
  if (list.items.length) {
    const saved = await get(`${projectsUrl}/${list.items[0].id}?client_id=${encodeURIComponent(key)}`);
    projectVersions.set(key, {id:saved.id, revision:saved.revision});
    return {project:saved.document};
  }
  const legacy = await get(`/parametros/api/format-lab/swap/video-project?client_id=${encodeURIComponent(key)}`);
  projectVersions.set(key, {id:null, revision:0});
  return legacy;
}

export async function saveVideoProject(body) {
  const key = String(body.client_id), version = projectVersions.get(key);
  if (!version) throw new Error('Reabra o projeto para recuperar a versão salva antes de editar.');
  const saved = await post(version.id ? `${projectsUrl}/${version.id}` : projectsUrl, {
    client_id:body.client_id, expected_revision:version.revision,
    document:{...body.project, schema_version:1},
  });
  projectVersions.set(key, {id:saved.id, revision:saved.revision});
  return {project:saved.document};
}
