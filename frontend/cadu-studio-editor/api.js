function unwrap(response) {
  if (!response.ok) return response.json().catch(() => ({})).then(body => Promise.reject(new Error(body.error || 'Não foi possível concluir a operação.')));
  return response.json().then(body => {
    if (!body.success) throw new Error(body.error || 'Não foi possível concluir a operação.');
    return body.data;
  });
}

function requestJson(url, csrf, method, body) {
  return fetch(url, {
    method, credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf || ''}, body: JSON.stringify(body),
  }).then(unwrap);
}

function postJson(url, csrf, body) { return requestJson(url, csrf, 'POST', body); }

const sessionRoot = apiRoot => `${apiRoot}/format-lab/studio/sessions`;

function getJson(url) { return fetch(url, {credentials: 'same-origin', headers: {Accept: 'application/json'}}).then(unwrap); }

export function loadProjectContexts({apiRoot}) {
  return getJson(`${apiRoot}/format-lab/studio/project-contexts`);
}

export function listStudioSessions({apiRoot, clientId, projectId}) {
  const query = new URLSearchParams({client_id: clientId || '', limit: '24', scope: 'all'});
  if (projectId) query.set('project_id', projectId);
  return getJson(`${sessionRoot(apiRoot)}?${query}`);
}

export function readStudioSession({apiRoot, clientId, sessionId}) {
  return getJson(`${sessionRoot(apiRoot)}/${encodeURIComponent(sessionId)}?${new URLSearchParams({client_id: clientId || ''})}`);
}

export function createStudioSession({apiRoot, csrf, clientId, payload}) {
  return postJson(sessionRoot(apiRoot), csrf, {client_id: clientId, studio_type: 'edit', ...payload});
}

export function saveStudioSession({apiRoot, csrf, clientId, sessionId, payload}) {
  return requestJson(`${sessionRoot(apiRoot)}/${encodeURIComponent(sessionId)}`, csrf, 'PATCH', {client_id: clientId, ...payload});
}

export function acceptStudioSessionAsset({apiRoot, csrf, clientId, sessionId, asset, role = 'accepted'}) {
  return postJson(`${sessionRoot(apiRoot)}/${encodeURIComponent(sessionId)}/accept`, csrf, {
    client_id: clientId, role, kind: 'image', source_type: 'studio-editor', source_id: asset.id,
    asset_id: asset.assetId || undefined, title: asset.name || 'Peça final do Studio', asset_url: asset.url,
  });
}

export function continueStudioSession({apiRoot, csrf, clientId, sessionId, title}) {
  return postJson(`${sessionRoot(apiRoot)}/${encodeURIComponent(sessionId)}/continue`, csrf, {
    client_id: clientId, studio_type: 'edit', title: title || 'Continuação da edição',
  });
}

export function attachStudioSessionProject({apiRoot, csrf, clientId, sessionId, projectId}) {
  return postJson(`${sessionRoot(apiRoot)}/${encodeURIComponent(sessionId)}/attach-project`, csrf, {
    client_id: clientId, project_id: projectId,
  });
}

export function finalizeStudioSession({apiRoot, csrf, clientId, sessionId, activeSeconds}) {
  return postJson(`${sessionRoot(apiRoot)}/${encodeURIComponent(sessionId)}/finalize`, csrf, {
    client_id: clientId, active_seconds: activeSeconds, pending_jobs: false,
  });
}

export function uploadStudioAsset({apiRoot, csrf, clientId, projectId, file}) {
  const form = new FormData();
  form.append('client_id', clientId || '');
  if (projectId) form.append('project_id', projectId);
  form.append('files', file, file.name);
  return fetch(`${apiRoot}/format-lab/studio/reference-uploads`, {
    method: 'POST', credentials: 'same-origin', headers: {'X-CSRF-Token': csrf || ''}, body: form,
  }).then(unwrap).then(data => data.items?.[0] || Promise.reject(new Error('O Studio não devolveu o ativo enviado.')));
}

export function requestQuote({apiRoot, csrf, prompt, format, clientId, hasMask}) {
  return postJson(`${apiRoot}/format-lab/quote`, csrf, {
    kind: 'swap', client_id: clientId || undefined, instruction: prompt, note: prompt,
    aspect_ratio: format, quality: 'draft', use_brand_context: true,
    selection_context: hasMask ? {role: 'marked_region'} : undefined,
  });
}

function publicImageUrl(value) {
  const raw = String(value || '').trim();
  if (!raw || raw.startsWith('data:')) return '';
  try { const url = new URL(raw, window.location.origin); return /^https?:$/.test(url.protocol) ? url.href : ''; } catch { return ''; }
}

export function requestEdition({apiRoot, csrf, asset, prompt, director, format, mask, crop, clientId, references, globalReferenceIds, brand}) {
  const selection = mask?.dataUrl ? {role: 'marked_region', mask_data_url: mask.dataUrl, bbox_px: mask.bounds, instruction: 'Apply the requested change only inside the marked region. Preserve the source image outside it.'} : crop?.bounds ? {role: 'crop', bbox_px: crop.bounds, instruction: 'Use the selected crop as the composition frame. Preserve the content inside it and rebalance only when required by the requested output format.'} : undefined;
  const localReferences = references.map(item => ({id: item.id, url: publicImageUrl(item.dataUrl), role: 'reference', source: 'user', label: item.name || 'Referência local'})).filter(item => item.url);
  const globalReferences = (brand?.assets?.references || []).map((url, index) => ({id: `brand-reference-${index}`, url: publicImageUrl(url), role: 'reference', source: 'project', label: 'Referência global da marca'})).filter(item => item.url && (!Array.isArray(globalReferenceIds) || globalReferenceIds.includes(item.id)));
  const directorReferences = [...localReferences, ...globalReferences].slice(0, 4);
  const payload = {
    reference: asset.dataUrl,
    note: prompt,
    instruction: director?.instruction || prompt,
    original_instruction: prompt,
    director_instruction: director?.instruction || '',
    client_id: clientId || undefined,
    aspect_ratio: format,
    quality: 'draft',
    reference_images: directorReferences.map(item => item.url),
    reference_inputs: directorReferences.map((item, index) => ({image: item.url, role: item.role, source: item.source, label: item.label, order: index + 2})),
    director_context: {brand_context: brand || {}, references: directorReferences, preserve: director?.preserve || [], objective: director?.objective || '', reference_policy: 'similarity_only_preserve_source_identity'},
    logo_url: publicImageUrl(brand?.logo_url) || undefined,
    selection_context: selection,
    regions: mask?.bounds ? {marked_region: mask.bounds} : crop?.bounds ? {crop: crop.bounds} : undefined,
    use_brand_context: true,
    confirm_conflicts: true,
    variation_count: 1,
  };
  return postJson(`${apiRoot}/format-lab/swap`, csrf, payload);
}
