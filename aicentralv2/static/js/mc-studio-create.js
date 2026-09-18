(function () {
  const app = document.getElementById('studioCreate');
  if (!app) return;

  const $ = (id) => document.getElementById(id);
  const apiRoot = String(app.dataset.apiRoot || '/parametros/api').replace(/\/$/, '');
  const csrf = document.querySelector('meta[name="trocr-csrf-token"]')?.content || '';
  const STORAGE_PREFIX = 'cadu-studio-visual-draft-v3';
  const ASSET_DB = 'cadu-studio-assets-v1';
  const ROLE_LABELS = {
    primary: 'Principal', insert: 'Inserir elemento', replace: 'Substituir seleção',
    style: 'Referência de estilo', composition: 'Referência de composição', identity: 'Preservar identidade',
  };
  const ZONE_ORIGINS = { table: [100, 150], approved: [1580, 150], removed: [1580, 735] };
  const state = {
    nodes: [], bindings: [], messages: [], selected: [], directions: [], activeId: '',
    clientId: String(app.dataset.clientId || ''), projectId: '', projectReady: false, projectDocument: {}, quickMode: true,
    zoom: .75, sequence: 0, chosenDirection: null, mask: null, maskMode: 'paint',
    maskUndo: [], maskRedo: [], dragging: null, saving: 0, pendingImageRequest: null,
    sessionId: '', sessionRevision: 0, sessionStatus: '', sessionRootId: '', sessionProjectId: '', sessionActiveAssetId: '', sessionReadOnly: false,
    sessionQueue: Promise.resolve(), sessionCreating: null, sessions: [], startedAt: Date.now(),
    originalPrompt: '', optimizedPrompt: '', promptLanguage: 'pt-BR',
  };

  function uid(prefix = 'node') {
    return `${prefix}-${window.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`}`;
  }
  function escapeHtml(value) {
    return String(value || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
  function fingerprint(value) { let hash=2166136261;const input=String(value||'');for(let index=0;index<input.length;index++){hash^=input.charCodeAt(index);hash=Math.imul(hash,16777619);}return (hash>>>0).toString(16); }
  function nodeById(id) { return state.nodes.find((node) => node.id === id); }
  function imageUrl(item) { return String(item?.thumbnail_url || item?.url || item?.image_url || item?.preview_url || item?.asset_url || ''); }
  function storageKey() {
    return `${STORAGE_PREFIX}:${app.dataset.userId || 'anonymous'}:${state.clientId || app.dataset.clientId || 'account'}`;
  }
  function sessionPointerKey() { return `${STORAGE_PREFIX}:session:${app.dataset.userId || 'anonymous'}:${state.clientId || 'account'}:${state.projectId || 'free'}`; }
  function openAssetDb() {
    return new Promise((resolve, reject) => {
      const opening = indexedDB.open(ASSET_DB, 1);
      opening.onupgradeneeded = () => opening.result.createObjectStore('assets');
      opening.onsuccess = () => resolve(opening.result);
      opening.onerror = () => reject(opening.error);
    });
  }
  async function assetWrite(key, value) {
    const db = await openAssetDb();
    await new Promise((resolve, reject) => { const transaction=db.transaction('assets','readwrite');transaction.objectStore('assets').put(value,key);transaction.oncomplete=resolve;transaction.onerror=()=>reject(transaction.error); });
    db.close();
  }
  async function assetRead(key) {
    const db = await openAssetDb();
    const value = await new Promise((resolve, reject) => { const request=db.transaction('assets').objectStore('assets').get(key);request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error); });
    db.close(); return value;
  }
  async function assetDeletePrefix(prefix) {
    const db = await openAssetDb();
    await new Promise((resolve, reject) => { const transaction=db.transaction('assets','readwrite');const store=transaction.objectStore('assets');const cursor=store.openCursor();cursor.onsuccess=()=>{const item=cursor.result;if(!item)return;if(String(item.key).startsWith(prefix))item.delete();item.continue();};transaction.oncomplete=resolve;transaction.onerror=()=>reject(transaction.error); });
    db.close();
  }
  function announce(message) {
    const target = $('studioBoardAnnounce');
    target.textContent = message;
    target.classList.add('is-visible');
    window.clearTimeout(target._hideTimer);
    target._hideTimer = window.setTimeout(() => target.classList.remove('is-visible'), 4200);
  }
  function setSaveStatus(message, busy = false) {
    $('studioSaveStatus').textContent = message;
    $('studioSaveStatus').parentElement?.classList.toggle('is-busy', busy);
  }
  async function request(url, options = {}) {
    const response = await fetch(url, { credentials: 'same-origin', headers: { Accept: 'application/json', ...(csrf ? {'X-Trocr-CSRF-Token': csrf} : {}), ...(options.headers || {}) }, ...options });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.success === false) throw new Error(payload.error || 'Não foi possível concluir esta ação.');
    return payload.data !== undefined ? payload.data : payload;
  }

  function renderPromptOptimization() {
    const box = $('studioPromptOptimization');
    box.hidden = !state.originalPrompt;
    if (!state.originalPrompt) return;
    $('studioOriginalPrompt').textContent = state.originalPrompt;
    $('studioOptimizedPrompt').textContent = state.optimizedPrompt || state.originalPrompt;
  }
  async function optimizePrompt(original, bindings) {
    try {
      const result = await request(`${apiRoot}/format-lab/studio/prompt/optimize`, {
        method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({
          client_id:state.clientId, prompt:original,
          mode:(state.mask?.data || bindings.length) ? 'edit' : 'create',
          context:{aspect_ratio:$('studioRatio').value, references:bindings.map((binding) => ({label:binding.node.label, role:binding.role}))},
        }),
      });
      state.originalPrompt = String(result.original_prompt || original);
      state.optimizedPrompt = String(result.optimized_prompt || original);
      state.promptLanguage = String(result.detected_language || 'pt-BR');
    } catch (_error) {
      state.originalPrompt = original; state.optimizedPrompt = original; state.promptLanguage = 'pt-BR';
    }
    renderPromptOptimization(); scheduleSave();
    return state.optimizedPrompt || original;
  }

  function sessionUrl(suffix = '') { return `${apiRoot}/format-lab/studio/sessions${suffix}`; }
  function canPersistSession() { return Boolean(app.dataset.userId && state.clientId); }
  function remoteWorkspace(snapshot = serializableState()) {
    return {
      ...snapshot,
      nodes: snapshot.nodes.map((node) => ({...node, url:String(node.url || '').startsWith('data:') ? '' : node.url})),
      mask: null,
    };
  }
  function updateSession(session) {
    if (!session?.id) return;
    state.sessionId = String(session.id);
    state.sessionRevision = Number(session.revision || 0);
    state.sessionStatus = String(session.status || 'draft');
    state.sessionRootId = String(session.root_session_id || session.id);
    state.sessionProjectId = String(session.project_id || '');
    state.sessionActiveAssetId = String(session.active_asset_id || '');
    state.sessionReadOnly = Boolean(session.read_only);
    state.originalPrompt = String(session.original_prompt || state.originalPrompt || '');
    state.optimizedPrompt = String(session.optimized_prompt || state.optimizedPrompt || '');
    state.promptLanguage = String(session.prompt_language || state.promptLanguage || 'pt-BR');
    try { localStorage.setItem(sessionPointerKey(), state.sessionId); } catch (_error) { /* Session remains usable without a browser pointer. */ }
    const assetBySource = new Map((session.assets || []).map((asset) => [String(asset.source_id || ''), asset]));
    state.nodes.forEach((node) => {
      const asset = assetBySource.get(String(node.id));
      if (asset) { node.assetId = String(asset.id); node.sessionRole = String(asset.role || node.sessionRole || ''); }
    });
    renderSessionState();
  }
  function renderSessionState() {
    app.classList.toggle('is-read-only', state.sessionReadOnly);
    $('studioFinalizedBanner').hidden = !state.sessionReadOnly;
    $('studioWorkspaceName').readOnly = state.sessionReadOnly;
    $('studioSessionSelect').value = state.sessionId || '';
    if (state.sessionReadOnly) setSaveStatus('Finalizado e preservado');
    else if (state.sessionId) setSaveStatus('Sessão sincronizada');
  }
  function queueSessionMutation(callback) {
    state.sessionQueue = state.sessionQueue.catch(() => {}).then(callback);
    return state.sessionQueue;
  }
  async function ensureSession() {
    if (state.sessionId || !canPersistSession()) return state.sessionId;
    if (state.sessionCreating) return state.sessionCreating;
    state.sessionCreating = request(sessionUrl(), {
      method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({
        client_id:state.clientId, project_id:state.projectId || '', studio_type:'create',
        title:$('studioWorkspaceName').value || 'Mesa sem título', original_prompt:state.originalPrompt,
        optimized_prompt:state.optimizedPrompt, prompt_language:state.promptLanguage,
        prompt_version:'studio-create-v1', metadata:{workspace:remoteWorkspace()},
      }),
    }).then((session) => { updateSession(session); return state.sessionId; }).finally(() => { state.sessionCreating = null; });
    return state.sessionCreating;
  }
  async function saveSessionNow({create = true} = {}) {
    if (state.sessionReadOnly || !canPersistSession()) return null;
    if (create) await ensureSession();
    if (!state.sessionId) return null;
    return queueSessionMutation(async () => {
      const session = await request(sessionUrl(`/${encodeURIComponent(state.sessionId)}`), {
        method:'PATCH', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({
          client_id:state.clientId, expected_revision:state.sessionRevision,
          title:$('studioWorkspaceName').value || 'Mesa sem título',
          original_prompt:state.originalPrompt, optimized_prompt:state.optimizedPrompt,
          prompt_language:state.promptLanguage, prompt_version:'studio-create-v1',
          metadata:{workspace:remoteWorkspace()},
        }),
      });
      updateSession(session);
      return session;
    });
  }

  function serializableState() {
    return {
      nodes: state.nodes.map(({ maskCanvas, ...node }) => node), bindings: state.bindings,
      messages: state.messages.slice(-60), sequence: state.sequence, chosenDirection: state.chosenDirection,
      name: $('studioWorkspaceName').value, zoom: state.zoom, mask: state.mask,
      pendingImageRequest: state.pendingImageRequest,
    };
  }
  async function persistDraftNow(key = storageKey(), snapshot = serializableState()) {
    for (const node of snapshot.nodes) {
      if (!String(node.url || '').startsWith('data:image/')) continue;
      const assetKey = `${key}:node:${node.id}`;
      await assetWrite(assetKey, node.url);
      node.url = `indexeddb:${assetKey}`;
    }
    if (String(snapshot.mask?.data || '').startsWith('data:image/')) {
      const assetKey = `${key}:mask:${snapshot.mask.nodeId}`;
      await assetWrite(assetKey, snapshot.mask.data);
      snapshot.mask = {...snapshot.mask, data:`indexeddb:${assetKey}`};
    }
    localStorage.setItem(key, JSON.stringify(snapshot));
  }
  function scheduleSave() {
    window.clearTimeout(state.saving);
    setSaveStatus('Salvando…', true);
    const key = storageKey();
    const snapshot = serializableState();
    state.saving = window.setTimeout(async () => {
      try {
        await persistDraftNow(key, snapshot);
        if (state.sessionId && !state.sessionReadOnly) {
          await saveSessionNow({create:false});
          setSaveStatus('Salvo no Studio');
        } else setSaveStatus('Salvo neste dispositivo');
      } catch (error) {
        setSaveStatus(error.message || 'Não foi possível salvar');
      }
    }, 650);
  }
  async function restoreDraft() {
    try {
      const data = JSON.parse(localStorage.getItem(storageKey()) || '{}');
      for (const node of data.nodes || []) {
        if (String(node.url || '').startsWith('indexeddb:')) node.url = await assetRead(node.url.slice(10)) || '';
      }
      if (String(data.mask?.data || '').startsWith('indexeddb:')) data.mask.data = await assetRead(data.mask.data.slice(10)) || '';
      if (Array.isArray(data.nodes)) state.nodes = data.nodes;
      if (Array.isArray(data.bindings)) state.bindings = data.bindings;
      if (Array.isArray(data.messages)) state.messages = data.messages;
      state.sequence = Number(data.sequence || state.nodes.length || 0);
      state.chosenDirection = data.chosenDirection || null;
      state.mask = data.mask?.nodeId && data.mask?.data ? data.mask : null;
      state.pendingImageRequest = data.pendingImageRequest || null;
      state.zoom = Math.max(.35, Math.min(1.35, Number(data.zoom || .75)));
      if (data.name) $('studioWorkspaceName').value = data.name;
    } catch (_error) { /* A broken browser draft must not prevent a new table. */ }
  }
  function resetDraftState({keepSession = false} = {}) {
    state.nodes=[];state.bindings=[];state.messages=[];state.selected=[];state.directions=[];state.activeId='';
    state.sequence=0;state.chosenDirection=null;state.mask=null;state.pendingImageRequest=null;
    state.originalPrompt='';state.optimizedPrompt='';state.promptLanguage='pt-BR';state.startedAt=Date.now();
    if (!keepSession) {
      state.sessionId='';state.sessionRevision=0;state.sessionStatus='';state.sessionRootId='';state.sessionProjectId='';state.sessionActiveAssetId='';state.sessionReadOnly=false;
    }
    $('studioWorkspaceName').value='Mesa sem título';
    renderSessionState();
  }

  function restoreWorkspace(workspace = {}) {
    resetDraftState({keepSession:true});
    if (Array.isArray(workspace.nodes)) state.nodes = workspace.nodes.filter((node) => node?.id && node?.url);
    if (Array.isArray(workspace.bindings)) state.bindings = workspace.bindings;
    if (Array.isArray(workspace.messages)) state.messages = workspace.messages;
    state.sequence = Number(workspace.sequence || state.nodes.length || 0);
    state.chosenDirection = workspace.chosenDirection || null;
    state.pendingImageRequest = workspace.pendingImageRequest || null;
    state.zoom = Math.max(.35, Math.min(1.35, Number(workspace.zoom || .75)));
    if (workspace.name) $('studioWorkspaceName').value = workspace.name;
  }

  async function loadSessions({openId = ''} = {}) {
    if (!canPersistSession()) return;
    const query = new URLSearchParams({client_id:state.clientId, limit:'100'});
    if (state.projectId) query.set('project_id', state.projectId);
    const data = await request(`${sessionUrl()}?${query}`);
    state.sessions = data.items || [];
    $('studioSessionSelect').innerHTML = '<option value="">Nova sessão</option>' + state.sessions.map((session) => `<option value="${escapeHtml(session.id)}">${escapeHtml(session.title || 'Sem título')} · ${session.read_only ? 'Finalizada' : 'Em andamento'}</option>`).join('');
    let remembered = openId;
    if (!remembered && !state.sessionId) { try { remembered = localStorage.getItem(sessionPointerKey()) || ''; } catch (_error) { remembered = ''; } }
    if (remembered && state.sessions.some((session) => String(session.id) === remembered)) await openSession(remembered);
    else renderSessionState();
  }

  async function openSession(ident) {
    if (!ident) return newSession();
    if (state.sessionId && state.sessionId !== ident && !state.sessionReadOnly) {
      window.clearTimeout(state.saving); state.saving = 0;
      await saveSessionNow({create:false});
    }
    const session = await request(`${sessionUrl(`/${encodeURIComponent(ident)}`)}?client_id=${encodeURIComponent(state.clientId)}`);
    restoreWorkspace(session.metadata?.workspace || {});
    updateSession(session);
    $('studioWorkspaceName').value = session.title || $('studioWorkspaceName').value;
    renderAll();
    announce(session.read_only ? 'Sessão finalizada aberta para consulta.' : 'Sessão retomada do ponto em que foi salva.');
  }

  async function newSession() {
    window.clearTimeout(state.saving); state.saving = 0;
    if (state.sessionId && !state.sessionReadOnly) { try { await saveSessionNow({create:false}); } catch (error) { announce(error.message || 'A sessão anterior ficou salva neste dispositivo.'); } }
    resetDraftState(); renderAll();
    if (canPersistSession()) { await ensureSession(); await loadSessions(); }
    announce('Nova sessão criada.');
  }

  function nextPosition(zone = 'table') {
    const count = state.nodes.filter((node) => node.zone === zone).length;
    const [left, top] = ZONE_ORIGINS[zone];
    const columns = zone === 'table' ? 4 : 2;
    return { x: left + (count % columns) * 330, y: top + Math.floor(count / columns) * 360 };
  }
  function addNode(url, options = {}) {
    if (!url) return null;
    const duplicate = state.nodes.find((node) => node.url === url);
    if (duplicate && !options.allowDuplicate) { selectNode(duplicate.id); return duplicate; }
    const zone = options.zone || 'table';
    const position = nextPosition(zone);
    const node = {
      id: uid(), url, label: options.label || `Imagem ${++state.sequence}`, zone,
      x: options.x ?? position.x, y: options.y ?? position.y, parentId: options.parentId || '',
      origin: options.origin || 'upload', status: options.status || 'ready', createdAt: Date.now(),
    };
    state.nodes.push(node);
    renderBoard(); selectNode(node.id); scheduleSave();
    return node;
  }
  function selectNode(id, additive = false) {
    if (!nodeById(id)) return;
    if (additive) state.selected = state.selected.includes(id) ? state.selected.filter((value) => value !== id) : [...state.selected, id];
    else state.selected = [id];
    state.activeId = id;
    renderBoard(); renderSelectionBar();
  }
  function focusNode(id) {
    const node = nodeById(id); if (!node) return;
    selectNode(id);
    const viewport = $('studioBoardViewport');
    viewport.scrollTo({ left: Math.max(0, node.x * state.zoom - viewport.clientWidth / 2), top: Math.max(0, node.y * state.zoom - viewport.clientHeight / 2), behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
  }
  async function registerNode(node, role = 'attempt') {
    if (!node || String(node.url || '').startsWith('data:') || !canPersistSession()) return null;
    await ensureSession();
    return queueSessionMutation(async () => {
      const session = await request(sessionUrl(`/${encodeURIComponent(state.sessionId)}/accept`), {
        method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({
          client_id:state.clientId, asset_id:node.assetId || '', asset_url:node.assetId ? '' : node.url,
          source_type:'studio-create', source_id:node.id, title:node.label, kind:'image', role,
          metadata:{origin:node.origin || 'studio', parent_node_id:node.parentId || ''},
        }),
      });
      updateSession(session);
      const asset = (session.assets || []).find((item) => String(item.source_id || '') === String(node.id));
      if (asset) { node.assetId = String(asset.id); node.sessionRole = role; }
      return asset || null;
    });
  }
  async function syncNodeZone(node, previousZone) {
    if (!node || state.sessionReadOnly) return;
    try {
      if (node.zone === 'approved' && node.sessionRole !== 'accepted') await registerNode(node, 'accepted');
      else if (node.zone === 'removed') {
        if (!node.assetId) await registerNode(node, 'attempt');
        if (node.assetId) {
          const session = await queueSessionMutation(() => request(sessionUrl(`/${encodeURIComponent(state.sessionId)}/discard`), {
            method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({client_id:state.clientId, asset_id:node.assetId}),
          }));
          updateSession(session); node.sessionRole = 'discard';
        }
      } else if (previousZone === 'removed' && node.assetId) {
        const session = await queueSessionMutation(() => request(sessionUrl(`/${encodeURIComponent(state.sessionId)}/restore`), {
          method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({client_id:state.clientId, asset_id:node.assetId}),
        }));
        updateSession(session); node.sessionRole = 'attempt';
      }
      scheduleSave();
    } catch (error) {
      node.zone = previousZone; Object.assign(node, nextPosition(previousZone));
      renderBoard(); renderSelectionBar(); scheduleSave();
      announce(error.message || 'Não foi possível atualizar esta peça.');
    }
  }
  function moveNodeToZone(id, zone) {
    const node = nodeById(id); if (!node || !ZONE_ORIGINS[zone]) return;
    if (state.sessionReadOnly) { announce('Este trabalho está finalizado. Use Continuar editando.'); return; }
    const previousZone = node.zone;
    node.zone = zone; Object.assign(node, nextPosition(zone));
    announce(`${node.label} movida para ${zone === 'table' ? 'Mesa' : zone === 'approved' ? 'Aprovadas' : 'Retiradas'}.`);
    renderBoard(); renderSelectionBar(); scheduleSave();
    if (previousZone !== zone) syncNodeZone(node, previousZone);
  }

  function renderBoard() {
    $('studioBoardWorld').style.setProperty('--board-scale', state.zoom);
    $('studioZoomLabel').textContent = `${Math.round(state.zoom * 100)}%`;
    $('studioBoardEmpty').hidden = state.nodes.length > 0;
    $('studioApprovedCount').textContent = state.nodes.filter((node) => node.zone === 'approved').length;
    $('studioRemovedCount').textContent = state.nodes.filter((node) => node.zone === 'removed').length;
    $('studioCompare').disabled = state.selected.length !== 2;
    $('studioBoardNodes').innerHTML = state.nodes.map((node, index) => {
      const bindingIndex = state.bindings.findIndex((binding) => binding.nodeId === node.id);
      const selected = state.selected.includes(node.id);
      return `<article class="studio-node ${selected ? 'is-selected' : ''} ${bindingIndex >= 0 ? 'is-bound' : ''} ${node.status === 'arriving' ? 'is-arriving' : ''}" data-node-id="${node.id}" data-zone="${node.zone}" style="left:${node.x}px;top:${node.y}px;--node-accent:${bindingIndex >= 0 ? ['var(--studio-mint)','var(--studio-violet)','var(--studio-blue)'][bindingIndex % 3] : 'var(--studio-mint)'}">
        <div class="studio-node__media"><img src="${escapeHtml(node.url)}" alt="${escapeHtml(node.label)}" draggable="false"><span class="studio-node__index">${bindingIndex >= 0 ? bindingIndex + 1 : index + 1}</span><canvas data-mask-canvas hidden></canvas></div>
        <footer class="studio-node__meta"><div><strong>${escapeHtml(node.label)}</strong><span>${node.zone === 'approved' ? 'Aprovada' : node.zone === 'removed' ? 'Retirada' : node.parentId ? 'Nova versão' : 'Na mesa'}</span></div><button type="button" data-node-menu aria-label="Ações">•••</button></footer>
      </article>`;
    }).join('');
    document.querySelectorAll('.studio-node').forEach(bindNode);
  }
  function bindNode(element) {
    const id = element.dataset.nodeId;
    element.addEventListener('click', (event) => {
      if (state.mask || event.target.closest('[data-node-menu],[data-mask-canvas]')) return;
      selectNode(id, event.shiftKey || event.metaKey || event.ctrlKey);
    });
    element.addEventListener('dblclick', () => attachBinding(id));
    element.querySelector('[data-node-menu]')?.addEventListener('click', () => selectNode(id));
    element.addEventListener('pointerdown', (event) => {
      if (state.sessionReadOnly || state.mask || event.target.closest('button,canvas')) return;
      const node = nodeById(id); if (!node) return;
      selectNode(id, event.shiftKey);
      element.setPointerCapture?.(event.pointerId);
      state.dragging = { id, startX: event.clientX, startY: event.clientY, x: node.x, y: node.y };
    });
    element.addEventListener('pointermove', (event) => {
      if (!state.dragging || state.dragging.id !== id) return;
      const node = nodeById(id); if (!node) return;
      node.x = Math.max(10, state.dragging.x + (event.clientX - state.dragging.startX) / state.zoom);
      node.y = Math.max(10, state.dragging.y + (event.clientY - state.dragging.startY) / state.zoom);
      element.style.left = `${node.x}px`; element.style.top = `${node.y}px`;
      const zone = node.x > 1500 ? (node.y < 610 ? 'approved' : 'removed') : 'table';
      document.querySelectorAll('.studio-zone').forEach((item) => item.classList.toggle('is-drop-target', item.dataset.zone === zone));
    });
    element.addEventListener('pointerup', (event) => {
      if (!state.dragging || state.dragging.id !== id) return;
      const node = nodeById(id); const drag = state.dragging; state.dragging = null;
      document.querySelectorAll('.studio-zone').forEach((item) => item.classList.remove('is-drop-target'));
      const composer = $('studioComposer').getBoundingClientRect();
      if (event.clientX >= composer.left && event.clientX <= composer.right && event.clientY >= composer.top && event.clientY <= composer.bottom) {
        node.x = drag.x; node.y = drag.y; attachBinding(id); renderBoard(); return;
      }
      const previousZone = node.zone;
      node.zone = node.x > 1500 ? (node.y < 610 ? 'approved' : 'removed') : 'table';
      renderBoard(); scheduleSave();
      if (previousZone !== node.zone) syncNodeZone(node, previousZone);
    });
  }

  function renderSelectionBar() {
    const node = nodeById(state.activeId);
    $('studioSelectionBar').hidden = !node || Boolean(state.mask);
    if (!node) return;
    $('studioSelectionName').textContent = state.selected.length > 1 ? `${state.selected.length} imagens` : node.label;
    const editor = $('studioOpenEditor');
    editor.href = `${app.dataset.editorUrl}?source=${encodeURIComponent(node.url)}${state.clientId ? `&creative_client_id=${encodeURIComponent(state.clientId)}` : ''}${state.projectId ? `&project_id=${encodeURIComponent(state.projectId)}` : ''}`;
  }
  function roleForNextBinding() {
    if (!state.bindings.length) return state.mask ? 'primary' : 'primary';
    if (state.mask) return 'replace';
    return 'insert';
  }
  function attachBinding(id, explicitRole) {
    const node = nodeById(id); if (!node) return;
    const existing = state.bindings.find((binding) => binding.nodeId === id);
    if (existing) {
      if (state.mask?.nodeId === id) { existing.role='primary';normalizePrimary(id);renderBindings();updateInterpretation();scheduleSave(); }
      focusNode(id); return;
    }
    if (state.bindings.length >= 2) {
      announce('Este gerador aceita duas imagens por pedido. Remova uma referência para adicionar outra.');
      return;
    }
    state.bindings.push({ nodeId: id, role: explicitRole || roleForNextBinding() });
    if (state.bindings.filter((binding) => binding.role === 'primary').length > 1) {
      state.bindings.at(-1).role = state.mask ? 'replace' : 'insert';
    }
    renderBindings(); renderBoard(); updateInterpretation(); scheduleSave();
    announce(`${node.label} relacionada ao pedido como ${ROLE_LABELS[state.bindings.at(-1).role]}.`);
  }
  function renderBindings() {
    $('studioCreateReferenceCount').textContent = `${state.bindings.length} selecionada${state.bindings.length === 1 ? '' : 's'}`;
    $('studioBindings').innerHTML = state.bindings.map((binding, index) => {
      const node = nodeById(binding.nodeId); if (!node) return '';
      const locked = state.mask?.nodeId === node.id;
      return `<div class="studio-binding ${locked?'is-locked':''}" data-binding-id="${node.id}" style="--binding-color:${['var(--studio-mint)','var(--studio-violet)','var(--studio-blue)'][index % 3]}"><img src="${escapeHtml(node.url)}" alt=""><select aria-label="Função de ${escapeHtml(node.label)}" ${locked?'disabled title="A imagem com área marcada é sempre a principal"':''}>${Object.entries(ROLE_LABELS).map(([value,label]) => `<option value="${value}" ${binding.role === value ? 'selected' : ''}>Imagem ${index + 1} · ${label}</option>`).join('')}</select><button type="button" aria-label="Remover ${escapeHtml(node.label)}" ${locked?'disabled title="Remova primeiro a área marcada"':''}>×</button></div>`;
    }).join('');
    document.querySelectorAll('.studio-binding').forEach((item) => {
      item.addEventListener('mouseenter', () => document.querySelector(`[data-node-id="${item.dataset.bindingId}"]`)?.classList.add('is-selected'));
      item.addEventListener('mouseleave', renderBoard);
      item.querySelector('img')?.addEventListener('click', () => focusNode(item.dataset.bindingId));
      item.querySelector('select')?.addEventListener('change', (event) => {
        if (state.mask?.nodeId === item.dataset.bindingId) return;
        const binding = state.bindings.find((row) => row.nodeId === item.dataset.bindingId); if (binding) binding.role = event.target.value;
        normalizePrimary(item.dataset.bindingId); updateInterpretation(); renderBoard(); scheduleSave();
      });
      item.querySelector('button')?.addEventListener('click', () => {
        if (state.mask?.nodeId === item.dataset.bindingId) { announce('Remova primeiro a área marcada.'); return; }
        state.bindings = state.bindings.filter((row) => row.nodeId !== item.dataset.bindingId);
        renderBindings(); renderBoard(); updateInterpretation(); scheduleSave();
      });
    });
    syncGenerateLabel();
  }
  function normalizePrimary(changedId) {
    const changed = state.bindings.find((row) => row.nodeId === changedId);
    if (changed?.role !== 'primary') return;
    state.bindings.forEach((row) => { if (row.nodeId !== changedId && row.role === 'primary') row.role = state.mask ? 'replace' : 'insert'; });
    renderBindings();
  }
  function updateInterpretation() {
    const target = $('studioInterpretation');
    if (!state.bindings.length && !state.mask) { target.hidden = true; return; }
    const primary = state.bindings.find((binding) => binding.role === 'primary');
    const others = state.bindings.filter((binding) => binding !== primary);
    const parts = [primary ? `Base: ${nodeById(primary.nodeId)?.label}` : 'Base: escolha uma imagem principal'];
    others.forEach((binding) => parts.push(`${ROLE_LABELS[binding.role]}: ${nodeById(binding.nodeId)?.label}`));
    if (state.mask) parts.push('Alterar somente a área marcada');
    target.innerHTML = `<strong>Entendi assim:</strong> ${escapeHtml(parts.join(' · '))}`;
    target.hidden = false;
  }

  function renderMessages() {
    const initial = '<article class="studio-message studio-message--assistant"><div><strong>O que vamos criar?</strong><p>Descreva a ideia. Se você selecionar imagens, eu mostro exatamente o papel de cada uma antes de gerar.</p></div></article>';
    $('studioChatMessages').innerHTML = initial + state.messages.map((message) => {
      const refs = (message.bindings || []).map((binding, index) => {
        const node = nodeById(binding.nodeId); return node ? `<button type="button" data-message-node="${node.id}">Imagem ${index + 1} · ${escapeHtml(ROLE_LABELS[binding.role])}</button>` : '';
      }).join('');
      return `<article class="studio-message studio-message--${message.role}"><div>${message.title ? `<strong>${escapeHtml(message.title)}</strong>` : ''}<p>${escapeHtml(message.text)}</p>${refs ? `<div class="studio-message__refs">${refs}</div>` : ''}</div></article>`;
    }).join('');
    document.querySelectorAll('[data-message-node]').forEach((button) => button.addEventListener('click', () => focusNode(button.dataset.messageNode)));
    $('studioChatMessages').scrollTop = $('studioChatMessages').scrollHeight;
  }
  function addMessage(role, text, extra = {}) {
    state.messages.push({ id: uid('message'), role, text, ...extra }); renderMessages(); scheduleSave();
  }
  function renderDirections(items) {
    state.directions = Array.isArray(items) ? items : [];
    $('studioCreateDirections').hidden = !state.directions.length;
    $('studioCreateDirections').innerHTML = state.directions.map((item, index) => `<article class="studio-direction"><i>${index + 1}</i><div><strong>${escapeHtml(item.title)}</strong><span>${escapeHtml(item.summary || item.prompt)}</span></div><button type="button" data-direction="${index}">Escolher</button></article>`).join('');
    document.querySelectorAll('[data-direction]').forEach((button) => button.addEventListener('click', () => chooseDirection(Number(button.dataset.direction))));
  }
  async function chooseDirection(index) {
    const direction = state.directions[index]; if (!direction) return;
    state.chosenDirection = direction; $('studioCreatePrompt').value = direction.prompt || '';
    addMessage('assistant', `Direção escolhida: ${direction.title}. Agora posso gerar a imagem ou aplicar essa direção à base selecionada.`, { title: direction.title });
    $('studioCreateGenerate').innerHTML = `Gerar imagem <span>↑</span>`;
    $('studioCreateDirections').hidden = true; scheduleSave();
    if (direction.id && state.clientId && state.projectId) {
      request(`${apiRoot}/format-lab/studio/projects/${encodeURIComponent(state.projectId)}/directions/${encodeURIComponent(direction.id)}/select`, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({client_id:state.clientId}) }).catch(() => {});
    }
  }

  async function submitPrompt(event) {
    event?.preventDefault();
    if (state.sessionReadOnly) { announce('Este trabalho está finalizado. Use Continuar editando.'); return; }
    const prompt = $('studioCreatePrompt').value.trim();
    if (!prompt) { $('studioCreatePrompt').focus(); return; }
    const button = $('studioCreateGenerate'); button.disabled = true;
    const bindings = state.bindings.map((binding) => ({ ...binding, node: nodeById(binding.nodeId) })).filter((binding) => binding.node);
    state.originalPrompt = prompt;
    addMessage('user', prompt, { bindings: state.bindings.map((binding) => ({...binding})) });
    try {
      button.textContent = 'Preparando o pedido…';
      const runtimePrompt = await optimizePrompt(prompt, bindings);
      await ensureSession();
      if (state.chosenDirection || state.mask?.data || bindings.length) await generateImage(runtimePrompt, bindings, button);
      else await generateDirections(runtimePrompt, bindings, button);
      $('studioCreatePrompt').value = '';
    } catch (error) {
      addMessage('assistant', error.message || 'Não foi possível concluir o pedido.', { title: 'A geração não foi concluída' });
    } finally { button.disabled = false; syncGenerateLabel(); }
  }
  async function generateDirections(prompt, bindings, button) {
    const count = Number($('studioDirectionCount').value || 5);
    button.textContent = `Criando ${count} direções…`;
    const references = bindings.slice(0, 2).map((binding) => ({ id: binding.node.id, name: `${binding.node.label} · ${ROLE_LABELS[binding.role]}`, url: binding.node.url, role: binding.role }));
    const scopedReferences=state.quickMode?[]:references;
    const result = await request(`${apiRoot}/format-lab/studio/create/directions`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ client_id:state.quickMode ? '' : state.clientId, project_id:state.quickMode ? '' : state.projectId, quick_mode:state.quickMode, count, prompt, references:scopedReferences, context:{ project_name:state.quickMode ? 'Rascunho pessoal' : $('studioCreateProject').textContent, brand:state.projectDocument.brand_name || '', brief:state.projectDocument.brief || '', purpose:'criacao', channels:['social','web'], format:$('studioRatio').value, direction_intensity:Number($('studioCreateRange').value), references:scopedReferences } }) });
    renderDirections(result.directions || []);
    addMessage('assistant', `Criei ${result.directions?.length || 0} direções. Escolha uma para gerar a imagem.`, { title: 'Direções prontas' });
    if (result.remaining_credits !== undefined) $('studioCreateCreditHint').textContent = `${Number(result.remaining_credits).toLocaleString('pt-BR')} créditos disponíveis`;
  }
  async function generateImage(prompt, bindings, button) {
    const primary = bindings.find((binding) => binding.role === 'primary');
    if (bindings.length && !primary) throw new Error('Escolha qual imagem será a principal antes de gerar.');
    button.textContent = 'Preparando referências…';
    const parent = primary?.node;
    const position = parent ? {x: parent.x + 250, y: parent.y + 28} : nextPosition('table');
    const waitingImage = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="600" height="800"><rect width="100%" height="100%" fill="#182126"/><text x="50%" y="50%" text-anchor="middle" fill="#82dfc8" font-family="Arial" font-size="24">Gerando…</text></svg>');
    const placeholder = addNode(waitingImage, {label:'Gerando imagem…', x:position.x, y:position.y, parentId:parent?.id, status:'pending'});
    renderBoard();
    const references = bindings.slice(0, 2).map((binding) => ({id:binding.node.id,url:binding.node.url, role:binding.role, label:binding.node.label}));
    const signature = JSON.stringify({prompt,ratio:$('studioRatio').value,references:references.map(({id,role})=>({id,role})),maskNodeId:state.mask?.nodeId||'',mask:fingerprint(state.mask?.data)});
    if (state.pendingImageRequest?.signature !== signature) state.pendingImageRequest={signature,id:uid('image')};
    const quickSource=state.quickMode?references.filter(reference=>reference.role==='primary').slice(0,1):references;
    const requestPayload={client_id:state.quickMode ? '' : state.clientId, project_id:state.quickMode?'':state.projectId, quick_mode:state.quickMode, prompt, title:state.chosenDirection?.title || 'Imagem criada no Studio', aspect_ratio:$('studioRatio').value, references:quickSource, mask:state.mask?.data || '', mask_node_id:state.mask?.nodeId || '', request_id:state.pendingImageRequest.id};
    scheduleSave();
    let result;
    try {
      result = await request(`${apiRoot}/format-lab/studio/create/image`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(requestPayload)});
    } catch (error) {
      state.nodes = state.nodes.filter((item) => item.id !== placeholder?.id);
      state.selected = state.selected.filter((id) => id !== placeholder?.id);
      if (state.activeId === placeholder?.id) state.activeId = parent?.id || '';
      renderBoard(); renderSelectionBar(); scheduleSave();
      announce(error.message || 'A imagem não foi gerada. Tente novamente.');
      throw error;
    }
    const node = placeholder && nodeById(placeholder.id);
    if (node) { node.url = result.image_url; node.label = `Imagem ${++state.sequence}`; node.status = 'arriving'; node.origin = 'generation'; window.setTimeout(() => { node.status = 'ready'; renderBoard(); }, 1100); }
    state.chosenDirection = null; state.mask = null; state.pendingImageRequest=null; renderMaskBinding(); renderBoard();
    addMessage('assistant', 'A nova imagem está na Mesa, ligada à base e às referências deste pedido.', { title:'Imagem pronta', bindings:node ? [{nodeId:node.id, role:'primary'}] : [] });
    if (node) focusNode(node.id);
    if (node) registerNode(node, 'attempt').catch((error) => announce(error.message || 'A imagem ficou salva apenas neste dispositivo.'));
    if (result.remaining_credits !== undefined) $('studioCreateCreditHint').textContent = `${Number(result.remaining_credits).toLocaleString('pt-BR')} créditos disponíveis`;
    if (result.history_sync_pending && state.projectId) window.setTimeout(()=>request(`${apiRoot}/format-lab/studio/create/image`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(requestPayload)}).then((synced)=>{if(!synced.history_sync_pending)announce('Imagem vinculada ao histórico do projeto.');}).catch(()=>{}),2200);
  }
  function syncGenerateLabel() {
    const count = Number($('studioDirectionCount').value || 5);
    const direct = state.chosenDirection || state.mask?.data || state.bindings.length;
    $('studioCreateGenerate').innerHTML = direct ? `${state.mask?.data?'Aplicar edição':'Gerar imagem'} <span>↑</span>` : `Gerar ${count} ${count === 1 ? 'direção' : 'direções'} <span>↑</span>`;
  }

  function startMask() {
    const node = nodeById(state.activeId); if (!node) return;
    state.mask = { nodeId: node.id, data: '', dirty: false };
    state.pendingImageRequest = null;
    state.maskUndo = []; state.maskRedo = [];
    renderBoard(); renderSelectionBar(); $('studioMaskTools').hidden = false;
    const element = document.querySelector(`[data-node-id="${node.id}"]`); const image = element?.querySelector('img'); const canvas = element?.querySelector('canvas');
    if (!image || !canvas) return;
    const init = () => { canvas.width = image.naturalWidth || 800; canvas.height = image.naturalHeight || 800; canvas.hidden = false; canvas.getContext('2d').clearRect(0,0,canvas.width,canvas.height); bindMaskCanvas(canvas); };
    image.complete ? init() : image.addEventListener('load', init, {once:true});
    announce('Modo de seleção ativo. Pinte a área que o Cadu pode alterar.');
  }
  function bindMaskCanvas(canvas) {
    const context = canvas.getContext('2d'); let drawing = false; let previous = null;
    const point = (event) => { const box = canvas.getBoundingClientRect(); return {x:(event.clientX-box.left)*canvas.width/box.width,y:(event.clientY-box.top)*canvas.height/box.height}; };
    const brush = () => { const size=Number($('studioMaskSize').value);context.globalCompositeOperation=state.maskMode==='erase'?'destination-out':'source-over';context.strokeStyle='rgba(130,223,200,.82)';context.fillStyle='rgba(130,223,200,.82)';context.lineWidth=size;context.lineCap='round';return size; };
    canvas.onpointerdown = (event) => { event.preventDefault(); canvas.setPointerCapture?.(event.pointerId); state.maskUndo.push(canvas.toDataURL()); state.maskRedo=[]; drawing=true; previous=point(event);const size=brush();context.beginPath();context.arc(previous.x,previous.y,size/2,0,Math.PI*2);context.fill();state.mask.dirty=true;updateMaskButtons(); };
    canvas.onpointermove = draw; canvas.onpointerup = canvas.onpointercancel = () => { drawing=false; previous=null; };
    function draw(event) {
      if (!drawing) return; const current=point(event);brush();context.beginPath();context.moveTo(previous.x,previous.y);context.lineTo(current.x,current.y);context.stroke();previous=current;state.mask.dirty=true;
    }
  }
  function maskCanvas() { return document.querySelector(`[data-node-id="${state.mask?.nodeId}"] [data-mask-canvas]`); }
  function updateMaskButtons(){ $('studioMaskUndo').disabled=!state.maskUndo.length; $('studioMaskRedo').disabled=!state.maskRedo.length; }
  async function restoreMaskSnapshot(data) { const canvas=maskCanvas(); if(!canvas||!data)return; const image=new Image(); image.src=data; await image.decode(); const ctx=canvas.getContext('2d');ctx.clearRect(0,0,canvas.width,canvas.height);ctx.drawImage(image,0,0); }
  function maskData(canvas) {
    const source=canvas.getContext('2d').getImageData(0,0,canvas.width,canvas.height).data;const binary=document.createElement('canvas');binary.width=canvas.width;binary.height=canvas.height;const ctx=binary.getContext('2d');const pixels=ctx.createImageData(binary.width,binary.height);let selected=0;for(let i=0;i<pixels.data.length;i+=4){const on=source[i+3]>8;const value=on?255:0;pixels.data[i]=pixels.data[i+1]=pixels.data[i+2]=value;pixels.data[i+3]=255;if(on)selected++;}ctx.putImageData(pixels,0,0);return {data:binary.toDataURL('image/png'),percent:Math.round(selected/(binary.width*binary.height)*100)};
  }
  function confirmMask() { const canvas=maskCanvas();if(!canvas)return;const output=maskData(canvas);if(!output.percent){announce('Pinte uma área antes de usar a seleção.');return;}state.mask.data=output.data;state.mask.percent=output.percent;state.mask.dirty=false;const previous=state.bindings.find((item)=>item.nodeId===state.mask.nodeId);const others=state.bindings.filter((item)=>item.nodeId!==state.mask.nodeId);state.bindings=[previous||{nodeId:state.mask.nodeId,role:'primary'},...others].slice(0,2);state.bindings[0].role='primary';state.bindings.slice(1).forEach((item)=>{if(item.role==='primary')item.role='replace';});state.pendingImageRequest=null;$('studioMaskTools').hidden=true;renderBoard();renderSelectionBar();renderMaskBinding();renderBindings();updateInterpretation();announce(`Área marcada: ${output.percent}% da imagem.`);scheduleSave(); }
  function cancelMask(clear=true) { if(clear)state.mask=null;$('studioMaskTools').hidden=true;renderBoard();renderSelectionBar();renderMaskBinding();renderBindings();updateInterpretation();syncGenerateLabel(); }
  function renderMaskBinding(){const box=$('studioMaskBinding');box.hidden=!state.mask?.data;if(state.mask?.data){box.querySelector('img').src=state.mask.data;box.querySelector('span').textContent=`${state.mask.percent}% da imagem será alterado.`;}}

  function renderLibrary(items) {
    const library = Array.isArray(items) ? items : [];
    $('studioCreateReferences').innerHTML = library.slice(0,12).map((item,index)=>{const url=imageUrl(item);return `<article class="studio-library__item">${url?`<img src="${escapeHtml(url)}" alt="Imagem ${index+1} da biblioteca">`:''}<button type="button" data-library-index="${index}">Levar à mesa</button></article>`;}).join('');
    $('studioCreateReferenceHint').textContent=library.length?'Arraste o papel de cada imagem para o chat.':'Adicione imagens ou vincule um projeto com biblioteca.';
    document.querySelectorAll('[data-library-index]').forEach((button)=>button.addEventListener('click',()=>{const item=library[Number(button.dataset.libraryIndex)];addNode(imageUrl(item),{label:item.title||item.name||`Imagem ${state.sequence+1}`,origin:'library'});}));
  }
  async function loadLibrary(){if(!state.clientId){renderLibrary([]);return;}try{const data=await request(`${apiRoot}/format-lab/swap/library?client_id=${encodeURIComponent(state.clientId)}&media=still`);renderLibrary(data.items||[]);}catch(_error){renderLibrary([]);}}
  async function loadHistory(){if(!state.clientId||!state.projectId)return;try{const data=await request(`${apiRoot}/format-lab/studio/projects/${encodeURIComponent(state.projectId)}/creation-history?client_id=${encodeURIComponent(state.clientId)}&limit=8`);const runs=data.runs||[];$('studioCreateHistory').innerHTML=runs.map((run)=>`<article class="studio-history-row"><i></i><div><strong>${escapeHtml(run.directions?.[0]?.title||run.prompt||'Direção criativa')}</strong><span>${run.status==='failed'?'Não concluída':`${run.returned_count||0} direções`}</span></div></article>`).join('')||'<p>Nenhuma direção criada neste projeto.</p>';}catch(_error){$('studioCreateHistory').innerHTML='<p>O histórico será carregado quando o projeto estiver disponível.</p>';}}
  async function loadProject(detail={}) {
    const nextProjectId=String($('mcCaduProject')?.value||'');
    if(state.sessionId&&state.sessionProjectId!==nextProjectId){try{await saveSessionNow({create:false});}catch(_error){}resetDraftState();renderAll();}
    state.projectId=nextProjectId;state.quickMode=!state.projectId;state.projectReady=false;
    if(!state.clientId||!state.projectId){
      $('studioCreateProject').textContent='Criação rápida';$('studioCreateBrand').textContent='Só você vê esta mesa. Use uma imagem como base ou crie sem referência.';$('studioCreateReferenceHint').textContent='Sem projeto: uma imagem pode ser a base da edição; referências de projeto não serão usadas.';
      await Promise.all([loadLibrary(),loadSessions().catch(()=>{})]); return;
    }
    try{const project=await request(`${apiRoot}/format-lab/studio/projects/${encodeURIComponent(state.projectId)}?client_id=${encodeURIComponent(state.clientId)}`);state.projectDocument=project.document||{};state.projectReady=true;$('studioCreateProject').textContent=state.projectDocument.name||project.name||'Projeto selecionado';$('studioCreateBrand').textContent=state.projectDocument.brand_name||state.projectDocument.brand||detail.brandName||'Marca vinculada';$('studioCreatePath').textContent=$('studioCreateProject').textContent;$('studioCreateAgentContext').textContent='O projeto e a marca entram como contexto opcional.';}catch(_error){state.projectId='';state.quickMode=true;}
    await Promise.all([loadLibrary(),loadHistory(),loadSessions().catch(()=>{})]);
  }
  async function switchClient(nextClientId, detail={}) {
    const next=String(nextClientId||'');
    if(next!==state.clientId){window.clearTimeout(state.saving);state.saving=0;const previousKey=storageKey();try{await persistDraftNow(previousKey);}catch(_error){}state.clientId=next;resetDraftState();await restoreDraft();renderAll();announce('Mesa da conta selecionada carregada.');}
    if($('mcCaduProject')?.value)await loadProject(detail);else{state.projectId='';state.quickMode=true;$('studioCreateProject').textContent='Criação rápida';$('studioCreateBrand').textContent='Só você vê esta mesa. Use uma imagem como base ou crie sem referência.';$('studioCreateReferenceHint').textContent='Sem projeto: uma imagem pode ser a base da edição; referências de projeto não serão usadas.';await Promise.all([loadLibrary(),loadSessions().catch(()=>{})]);}
  }

  function finalCandidate() {
    return state.nodes.find((node) => node.assetId && node.assetId === state.sessionActiveAssetId)
      || state.nodes.find((node) => node.zone === 'approved') || null;
  }
  async function openFinishDialog() {
    const node = finalCandidate();
    if (!node) { announce('Mova a peça escolhida para Aprovadas antes de finalizar.'); return; }
    if (node.zone !== 'approved') moveNodeToZone(node.id, 'approved');
    $('studioFinishPreview').src = node.url;
    $('studioFinishAssetName').textContent = node.label;
    $('studioFinishDialog').showModal();
  }
  async function finalizeSession() {
    const button = $('studioConfirmFinish');
    const node = finalCandidate();
    if (!node) return;
    button.disabled = true; button.textContent = 'Finalizando…';
    try {
      await ensureSession();
      if (node.sessionRole !== 'accepted') await registerNode(node, 'accepted');
      await saveSessionNow({create:false});
      const result = await queueSessionMutation(() => request(sessionUrl(`/${encodeURIComponent(state.sessionId)}/finalize`), {
        method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({client_id:state.clientId, active_seconds:Math.round((Date.now()-state.startedAt)/1000), pending_jobs:false}),
      }));
      updateSession(result.session);
      $('studioFinishDialog').close();
      await loadSessions();
      announce('Trabalho finalizado. A peça foi preservada e o resumo entrou na fila de envio.');
    } catch (error) { announce(error.message || 'Não foi possível finalizar o trabalho.'); }
    finally { button.disabled = false; button.textContent = 'Sim, finalizar trabalho'; }
  }
  async function continueSession() {
    if (!state.sessionId) return;
    try {
      const session = await request(sessionUrl(`/${encodeURIComponent(state.sessionId)}/continue`), {
        method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({client_id:state.clientId, studio_type:'create', title:`Continuação de ${$('studioWorkspaceName').value || 'trabalho'}`}),
      });
      updateSession(session); restoreWorkspace(session.metadata?.workspace || serializableState()); updateSession(session);
      $('studioWorkspaceName').value = session.title || 'Continuação';
      renderAll(); await loadSessions();
      announce('Nova etapa criada com a peça final como referência.');
    } catch (error) { announce(error.message || 'Não foi possível continuar esta sessão.'); }
  }
  async function openEditorWithSession(event) {
    event.preventDefault();
    const node = nodeById(state.activeId);
    if (!node || state.sessionReadOnly) return;
    try {
      await ensureSession();
      if (node.sessionRole !== 'accepted') await registerNode(node, 'accepted');
      const child = await request(sessionUrl(`/${encodeURIComponent(state.sessionId)}/handoff`), {
        method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({client_id:state.clientId, studio_type:'edit', title:`Edição de ${node.label}`, request_id:`editor:${node.assetId || node.id}`}),
      });
      const target = new URL(app.dataset.editorUrl, window.location.origin);
      target.searchParams.set('source', node.url);
      target.searchParams.set('studio_session_id', child.id);
      if (state.clientId) target.searchParams.set('creative_client_id', state.clientId);
      if (state.projectId) target.searchParams.set('project_id', state.projectId);
      window.location.assign(target.toString());
    } catch (error) { announce(error.message || 'Não foi possível abrir o editor.'); }
  }

  function takeFiles(files) {
    if (state.sessionReadOnly) { announce('Este trabalho está finalizado. Use Continuar editando.'); return; }
    Array.from(files||[]).filter((file)=>/^image\/(png|jpeg|webp)$/.test(file.type)&&file.size<=20*1024*1024).slice(0,8).forEach((file)=>{const reader=new FileReader();reader.onload=()=>addNode(reader.result,{label:file.name.replace(/\.[^.]+$/,''),origin:'upload'});reader.readAsDataURL(file);});
  }
  function bindUi() {
    $('studioComposer').addEventListener('submit',submitPrompt);
    $('studioDirectionCount').addEventListener('change',syncGenerateLabel);
    $('studioCreateRange').addEventListener('input',()=>{$('studioCreateIntensity').textContent=`${$('studioCreateRange').value}%`;});
    $('studioWorkspaceName').addEventListener('input',scheduleSave);
    $('studioCreatePrompt').addEventListener('input',renderMentionPicker);
    $('studioUploadInput').addEventListener('change',(event)=>takeFiles(event.target.files));
    $('studioComposerUpload').addEventListener('click',()=>$('studioUploadInput').click());$('studioEmptyUpload').addEventListener('click',()=>$('studioUploadInput').click());
    const drop=$('studioUploadDrop');drop.addEventListener('dragover',(event)=>{event.preventDefault();drop.classList.add('is-dragging');});drop.addEventListener('dragleave',()=>drop.classList.remove('is-dragging'));drop.addEventListener('drop',(event)=>{event.preventDefault();drop.classList.remove('is-dragging');takeFiles(event.dataTransfer.files);});
    window.addEventListener('paste',(event)=>{const files=Array.from(event.clipboardData?.files||[]).filter((file)=>file.type.startsWith('image/'));if(files.length)takeFiles(files);});
    $('studioLibraryClose').addEventListener('click',()=>toggleLibrary(false));$('studioLibraryToggle').addEventListener('click',()=>toggleLibrary($('studioLibraryPanel').hidden));
    $('studioChatToggle').addEventListener('click',()=>toggleChat(!$('studioChat').classList.contains('is-open')));
    $('studioChatClose').addEventListener('click',()=>toggleChat(false));
    $('studioAttachProject').addEventListener('click',()=>{const select=$('mcCaduProject');select?.focus();select?.showPicker?.();announce('Escolha um projeto na barra superior.');});
    document.querySelectorAll('[data-board-focus]').forEach((button)=>button.addEventListener('click',()=>focusZone(button.dataset.boardFocus)));
    $('studioZoomIn').addEventListener('click',()=>setZoom(state.zoom+.1));$('studioZoomOut').addEventListener('click',()=>setZoom(state.zoom-.1));$('studioFitBoard').addEventListener('click',()=>{setZoom(.55);focusZone('table');});
    $('studioBoardViewport').addEventListener('wheel',(event)=>{if(!event.ctrlKey&&!event.metaKey)return;event.preventDefault();setZoom(state.zoom+(event.deltaY<0?.08:-.08));},{passive:false});
    document.querySelectorAll('[data-selection-action]').forEach((button)=>button.addEventListener('click',()=>{const action=button.dataset.selectionAction;if(action==='chat')state.selected.forEach((id)=>attachBinding(id));if(action==='mask')startMask();if(action==='approve')state.selected.forEach((id)=>moveNodeToZone(id,'approved'));if(action==='remove')state.selected.forEach((id)=>moveNodeToZone(id,'removed'));}));
    document.querySelectorAll('[data-mask-mode]').forEach((button)=>button.addEventListener('click',()=>{state.maskMode=button.dataset.maskMode;document.querySelectorAll('[data-mask-mode]').forEach((item)=>item.setAttribute('aria-pressed',String(item===button)));}));
    $('studioMaskClear').addEventListener('click',()=>{const canvas=maskCanvas();if(canvas){state.maskUndo.push(canvas.toDataURL());canvas.getContext('2d').clearRect(0,0,canvas.width,canvas.height);updateMaskButtons();}});$('studioMaskCancel').addEventListener('click',()=>cancelMask());$('studioMaskConfirm').addEventListener('click',confirmMask);
    $('studioMaskUndo').addEventListener('click',async()=>{const canvas=maskCanvas();if(!canvas||!state.maskUndo.length)return;state.maskRedo.push(canvas.toDataURL());await restoreMaskSnapshot(state.maskUndo.pop());updateMaskButtons();});$('studioMaskRedo').addEventListener('click',async()=>{const canvas=maskCanvas();if(!canvas||!state.maskRedo.length)return;state.maskUndo.push(canvas.toDataURL());await restoreMaskSnapshot(state.maskRedo.pop());updateMaskButtons();});
    $('studioMaskBinding').querySelector('button').addEventListener('click',()=>{state.mask=null;state.pendingImageRequest=null;renderMaskBinding();renderBindings();updateInterpretation();syncGenerateLabel();scheduleSave();});
    $('studioCompare').addEventListener('click',openCompare);$('studioCompareDialog').querySelector('[data-close-dialog]').addEventListener('click',()=>$('studioCompareDialog').close());
    $('studioNewDraft').addEventListener('click',newSession);
    $('studioSessionSelect').addEventListener('change',(event)=>openSession(event.target.value).catch((error)=>announce(error.message||'Não foi possível abrir a sessão.')));
    $('studioSaveNow').addEventListener('click',async()=>{try{await ensureSession();await saveSessionNow({create:false});setSaveStatus('Salvo no Studio');announce('Sessão salva.');await loadSessions();}catch(error){announce(error.message||'Não foi possível salvar a sessão.');}});
    $('studioFinish').addEventListener('click',openFinishDialog);
    $('studioConfirmFinish').addEventListener('click',finalizeSession);
    document.querySelectorAll('[data-close-finish]').forEach((button)=>button.addEventListener('click',()=>$('studioFinishDialog').close()));
    $('studioContinueSession').addEventListener('click',continueSession);
    $('studioOpenEditor').addEventListener('click',openEditorWithSession);
    document.addEventListener('cadu:project-ready',(event)=>switchClient(event.detail?.clientId||'',event.detail||{}));document.addEventListener('cadu:project-change',(event)=>switchClient(event.detail?.clientId||state.clientId||'',event.detail||{}));
  }
  function toggleLibrary(open){$('studioLibraryPanel').hidden=!open;$('studioLibraryToggle').setAttribute('aria-expanded',String(open));document.querySelector('.studio-workspace').classList.toggle('is-library-closed',!open);}
  function toggleChat(open){const chat=$('studioChat');chat.classList.toggle('is-open',open);$('studioChatToggle').setAttribute('aria-expanded',String(open));if(open)$('studioCreatePrompt').focus();}
  function setZoom(value){state.zoom=Math.max(.35,Math.min(1.35,value));renderBoard();scheduleSave();}
  function focusZone(zone){const viewport=$('studioBoardViewport');const [x,y]=ZONE_ORIGINS[zone]||ZONE_ORIGINS.table;viewport.scrollTo({left:Math.max(0,x*state.zoom-40),top:Math.max(0,y*state.zoom-40),behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});}
  function openCompare(){if(state.selected.length!==2)return;const [first,second]=state.selected.map(nodeById);$('studioCompareBody').innerHTML=[first,second].map((node)=>`<figure><img src="${escapeHtml(node.url)}" alt="${escapeHtml(node.label)}"><figcaption><span>${escapeHtml(node.label)}</span><button type="button" data-compare-choose="${node.id}">Manter esta versão</button></figcaption></figure>`).join('');document.querySelectorAll('[data-compare-choose]').forEach((button)=>button.addEventListener('click',()=>{const keep=button.dataset.compareChoose;state.selected.filter((id)=>id!==keep).forEach((id)=>moveNodeToZone(id,'removed'));moveNodeToZone(keep,'approved');state.selected=[keep];state.activeId=keep;$('studioCompareDialog').close();renderBoard();renderSelectionBar();announce('Versão mantida em Aprovadas; a outra foi movida para Retiradas.');}));$('studioCompareDialog').showModal();}
  function renderMentionPicker(){let picker=document.querySelector('.studio-mention-picker');const textarea=$('studioCreatePrompt');const match=textarea.value.slice(0,textarea.selectionStart).match(/@([^\s@]*)$/);if(!match){picker?.remove();return;}if(!picker){picker=document.createElement('div');picker.className='studio-mention-picker';$('studioComposer').append(picker);}const query=match[1].toLocaleLowerCase('pt-BR');const choices=state.nodes.filter((node)=>node.label.toLocaleLowerCase('pt-BR').includes(query)).slice(0,6);picker.innerHTML=choices.map((node)=>`<button type="button" data-mention-node="${node.id}"><img src="${escapeHtml(node.url)}" alt=""><span>${escapeHtml(node.label)}</span></button>`).join('')||'<p>Nenhuma imagem encontrada.</p>';picker.querySelectorAll('[data-mention-node]').forEach((button)=>button.addEventListener('click',()=>{const node=nodeById(button.dataset.mentionNode);const before=textarea.value.slice(0,textarea.selectionStart).replace(/@([^\s@]*)$/,`@${node.label} `);textarea.value=before+textarea.value.slice(textarea.selectionStart);attachBinding(node.id);picker.remove();textarea.focus();}));}
  function renderAll(){renderBoard();renderSelectionBar();renderBindings();renderMessages();renderMaskBinding();renderPromptOptimization();updateInterpretation();syncGenerateLabel();}

  function hydrateConversationHandoff() {
    const params = new URLSearchParams(window.location.search);
    const prompt = String(params.get('prompt') || '').trim();
    if (prompt) { $('studioCreatePrompt').value = prompt.slice(0, 6000); toggleChat(true); }
    const ratio = params.get('ratio');
    if (ratio && [...$('studioRatio').options].some(option => option.value === ratio)) $('studioRatio').value = ratio;
    const directions = params.get('directions');
    if (directions && [...$('studioDirectionCount').options].some(option => option.value === directions)) $('studioDirectionCount').value = directions;
    const intensity = Number(params.get('intensity'));
    if (Number.isFinite(intensity) && intensity >= 0 && intensity <= 100) { $('studioCreateRange').value = String(intensity); $('studioCreateIntensity').textContent = intensity + '%'; }
    if (prompt) announce('Direção recebida da conversa. Revise antes de gerar.');
  }
  async function boot(){await restoreDraft();bindUi();hydrateConversationHandoff();renderAll();focusZone('table');const select=$('mcCaduProject');if(select?.value){state.quickMode=false;await loadProject();}else await loadSessions().catch(()=>{});}
  boot();
})();
