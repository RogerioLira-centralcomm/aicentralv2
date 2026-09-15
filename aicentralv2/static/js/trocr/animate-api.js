import {showProcessing,updateProcessing} from '../media-progress.js';
import { csrf } from "./animate-utils.js";

const BASE = "/parametros/api/format-lab/swap/animate";

async function parse(response) {
  const payload = await response.json();
  if (!response.ok || payload.success === false) {
    throw new Error(payload.error || "A animação não respondeu.");
  }
  return payload.data || {};
}

function headers() {
  return {
    "Content-Type": "application/json",
    "X-Trocr-CSRF-Token": csrf(),
  };
}

export function quoteAnimate(body) {
  return fetch(`${BASE}/quote`, {
    method: "POST",
    credentials: "same-origin",
    headers: headers(),
    body: JSON.stringify(body || {}),
  }).then(parse);
}

export function submitAnimate(body) {
  showProcessing({status:"preparing", message:"Enviando o projeto…", preview_images:body.preview_images||[], plan:body});
  return fetch(BASE, {
    method: "POST",
    credentials: "same-origin",
    headers: headers(),
    body: JSON.stringify(body || {}),
  }).then(parse).then(job=>{updateProcessing({...job,adopt_pending:true});return job;}).catch(error=>{updateProcessing({status:"failed",error:error.message});throw error;});
}

export function getAnimate(jobId) {
  return fetch(`${BASE}/${encodeURIComponent(jobId)}`, {
    credentials: "same-origin",
  }).then(parse);
}

export function animateLayers(body) {
  return fetch(`${BASE}/layers`, {
    method: "POST",
    credentials: "same-origin",
    headers: headers(),
    body: JSON.stringify(body || {}),
  }).then(parse);
}

export function mapAnimateCamadas(body) {
  return fetch(`${BASE}/map`, {
    method: "POST",
    credentials: "same-origin",
    headers: headers(),
    body: JSON.stringify(body || {}),
  }).then(parse);
}

export function previewAnimate(body) {
  return fetch(`${BASE}/preview`, {
    method: "POST",
    credentials: "same-origin",
    headers: headers(),
    body: JSON.stringify(body || {}),
  }).then(parse);
}

export function recomposeAnimate(jobId, body) {
  return fetch(`${BASE}/${encodeURIComponent(jobId)}/recompose`, {
    method: "POST",
    credentials: "same-origin",
    headers: headers(),
    body: JSON.stringify(body || {}),
  }).then(parse);
}

export function cancelAnimate(jobId) {
  return fetch(`${BASE}/${encodeURIComponent(jobId)}/cancel`, {
    method: "POST",
    credentials: "same-origin",
    headers: headers(),
  }).then(parse);
}
