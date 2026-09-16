import { csrf } from "../trocr/animate-utils.js";

export const apiRoot = document.getElementById('mcCaduBar')?.dataset.mcApiRoot || '/parametros/api';
export const studioApi = `${apiRoot}/format-lab/studio`;
export const swapApi = `${apiRoot}/format-lab/swap`;

async function parse(response) {
  const payload = await response.json().catch(() => ({}));
  if (!response.ok || payload.success === false) {
    const error = new Error(payload.error || "A mesa de vídeo não respondeu.");
    error.status = response.status;
    error.code = payload.code;
    throw error;
  }
  return normalizeUrls(payload.data !== undefined ? payload.data : payload);
}

function normalizeUrls(value) {
  if (typeof value === 'string') return value.replace(/^\/parametros\/api\//, `${apiRoot}/`);
  if (Array.isArray(value)) return value.map(normalizeUrls);
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, normalizeUrls(item)]));
  }
  return value;
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
  const response = await fetch(`${swapApi}/library`, {
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
const projectsUrl = `${studioApi}/projects`;

export async function loadVideoProject(clientId, projectId = "") {
  const key = String(clientId);
  projectVersions.delete(key);
  const list = await get(`${projectsUrl}?client_id=${encodeURIComponent(key)}`);
  const items = Array.isArray(list.items) ? list.items : [];
  const chosen = items.find((item) => String(item.id) === String(projectId)) || items[0];
  if (chosen) {
    const saved = await get(`${projectsUrl}/${chosen.id}?client_id=${encodeURIComponent(key)}`);
    projectVersions.set(key, {id:saved.id, revision:saved.revision});
    return {project:saved.document, items, activeId:saved.id};
  }
  const legacy = await get(`${swapApi}/video-project?client_id=${encodeURIComponent(key)}`);
  projectVersions.set(key, {id:null, revision:0});
  return {...legacy, items:[], activeId:""};
}

export async function saveVideoProject(body) {
  const key = String(body.client_id), version = projectVersions.get(key);
  if (!version) throw new Error('Reabra o projeto para recuperar a versão salva antes de editar.');
  const saved = await post(version.id ? `${projectsUrl}/${version.id}` : projectsUrl, {
    client_id:body.client_id, expected_revision:version.revision,
    document:{...body.project, schema_version:1},
  });
  projectVersions.set(key, {id:saved.id, revision:saved.revision});
  return {project:saved.document, activeId:saved.id, item:{id:saved.id,name:saved.name,revision:saved.revision,updated_at:saved.updated_at}};
}
