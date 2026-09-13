const BASE = "/parametros/api/camadas/v2";

async function parse(response) {
  const payload = await response.json();
  if (!response.ok || payload.success === false) {
    throw new Error(payload.error || "A Camadas V2 não respondeu.");
  }
  return payload.data || {};
}

export function createCreative({ file, name = "", brandId = "", collectionId = "" }) {
  const body = new FormData();
  body.append("file", file);
  if (name) body.append("name", name);
  if (brandId) body.append("brand_id", brandId);
  if (collectionId) body.append("collection_id", collectionId);
  return fetch(`${BASE}/creatives`, {
    method: "POST",
    credentials: "same-origin",
    body,
  }).then(parse);
}

export function getCreative(creativeId) {
  return fetch(`${BASE}/creatives/${encodeURIComponent(creativeId)}`, {
    credentials: "same-origin",
  }).then(parse);
}

export function getJob(jobId) {
  return fetch(`${BASE}/jobs/${encodeURIComponent(jobId)}`, {
    credentials: "same-origin",
  }).then(parse);
}

export function segmentPoint(creativeId, body) {
  return fetch(`${BASE}/creatives/${encodeURIComponent(creativeId)}/segment`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  }).then(parse);
}

export function refineMask(elementId, body) {
  return fetch(`${BASE}/elements/${encodeURIComponent(elementId)}/mask/refine`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  }).then(parse);
}

export function patchElement(elementId, body) {
  return fetch(`${BASE}/elements/${encodeURIComponent(elementId)}`, {
    method: "PATCH",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  }).then(parse);
}

export function patchScene(creativeId, body) {
  return fetch(`${BASE}/creatives/${encodeURIComponent(creativeId)}/scene`, {
    method: "PATCH",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  }).then(parse);
}

export function listBrandAssets(brandId, query = {}) {
  const params = new URLSearchParams();
  Object.entries(query).forEach(([key, value]) => {
    if (value) params.set(key, value);
  });
  const suffix = params.toString() ? `?${params}` : "";
  return fetch(`${BASE}/brands/${encodeURIComponent(brandId)}/assets${suffix}`, {
    credentials: "same-origin",
  }).then(parse);
}

export function createCollection(brandId, body) {
  return fetch(`${BASE}/brands/${encodeURIComponent(brandId)}/collections`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  }).then(parse);
}

export function publishElement(elementId, body) {
  return fetch(`${BASE}/elements/${encodeURIComponent(elementId)}/publish`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  }).then(parse);
}

export function placeAsset(creativeId, body) {
  return fetch(`${BASE}/creatives/${encodeURIComponent(creativeId)}/place`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  }).then(parse);
}
