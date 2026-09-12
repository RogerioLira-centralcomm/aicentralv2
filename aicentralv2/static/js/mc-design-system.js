(() => {
  const API = {
    clients: '/parametros/api/clients',
    campaigns: '/parametros/api/campaigns',
    brand: (id) => `/parametros/api/design-system/brand/${id}`,
    refine: (id) => `/parametros/api/design-system/brand/${id}/refine`,
    approve: (id) => `/parametros/api/design-system/brand/${id}/approve`,
    tokens: (id) => `/parametros/api/design-system/brand/${id}/tokens`,
    loop: (id) => `/parametros/api/design-system/brand/${id}/loop`,
    track: (id, track) => `/parametros/api/design-system/brand/${id}/tracks/${track}`,
    adapt: (id) => `/parametros/api/design-system/brand/${id}/adapt`,
    validateRender: (id) => `/parametros/api/design-system/brand/${id}/validate-render`,
    campaign: (id) => `/parametros/api/design-system/campaign/${id}`,
    campaignAdapt: (id) => `/parametros/api/design-system/campaign/${id}/adapt`,
    campaignValidateRender: (id) => `/parametros/api/design-system/campaign/${id}/validate-render`,
  };

  const COLOR_TOKENS = new Set(['paper', 'ink', 'accent', 'muted', 'cta_ink', 'highlight', 'hairline']);
  const CORE_ROLES = new Set(['visual', 'product', 'logo', 'headline', 'support', 'cta']);
  const ROLE_INTENT = { colors: 'contrast', type: 'type', cta: 'cta' };
  const INTENT_LABEL = { contrast: 'Contraste', type: 'Tipo', cta: 'CTA' };
  const TRACK_LABEL = { packshot: 'Gerar produto', kv: 'Gerar KV', lifestyle: 'Gerar cena', wash: 'Gerar tinta' };

  const state = {
    clients: [],
    campaigns: [],
    clientId: 'centralcomm',
    campaignId: '',
    format: 'iab-billboard',
    layers: 4,
    highlight: '',
    swaps: [],
    stageOpen: true,
    archetype: 'brand',
    looping: false,
    system: null,
    patchTimer: 0,
    console: [],
    consoleOpen: false,
  };

  const CONSOLE_KEY = 'mc-dsa-console';
  const CONSOLE_MAX = 40;

  function $(id) {
    return document.getElementById(id);
  }

  function escapeHtml(value) {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  async function readJson(response) {
    let payload = {};
    try {
      payload = await response.json();
    } catch (_error) {
      pushConsole({ step: 'http', status: 'error', error: `HTTP ${response.status}. Resposta sem JSON.` });
      const error = new Error('A mesa de Ads não concluiu.');
      error.status = response.status;
      throw error;
    }
    ingestRun(payload.data && payload.data.run);
    if (!response.ok || payload.success === false) {
      const last = state.console[state.console.length - 1];
      if (payload.error && last?.error !== payload.error) {
        pushConsole({ step: 'http', status: 'error', error: payload.error });
      }
      const error = new Error(payload.error || 'A mesa de Ads não concluiu.');
      error.status = response.status;
      throw error;
    }
    return payload.data;
  }

  function currentRevision() {
    const raw = state.system && state.system.revision;
    const value = Number(raw);
    return Number.isFinite(value) && value >= 0 ? value : 0;
  }

  function revisionBody(extra, revision) {
    return Object.assign({}, extra || {}, { expected_revision: revision });
  }

  function cancelQueuedPatch() {
    window.clearTimeout(state.patchTimer);
    state.patchTimer = 0;
  }

  const queueApi = window.McDsaWriteQueue || {};
  const BRAND_CONFLICT = queueApi.BRAND_CONFLICT || 'A marca mudou. Recarregue.';
  const DISCARDED_EDIT = queueApi.DISCARDED_EDIT || 'Edição pendente descartada. A marca mudou.';
  const DISCARDED_STALE_LOCAL = queueApi.DISCARDED_STALE_LOCAL
    || 'O ajuste anterior foi gravado. Este pedido usava o estado antigo e não foi reenviado.';
  let writeEpoch = 0;
  let lastWriteSucceeded = false;
  let pendingPatch = queueApi.emptyPatch ? queueApi.emptyPatch() : { tokens: {}, adCopy: {}, dna: {} };

  function discardPendingWrites(message) {
    writeEpoch += 1;
    lastWriteSucceeded = false;
    pendingPatch = queueApi.emptyPatch ? queueApi.emptyPatch() : { tokens: {}, adCopy: {}, dna: {} };
    cancelQueuedPatch();
    if (message) {
      setStatus(message);
      pushConsole({ step: 'http', status: 'error', error: message });
    }
  }

  async function reloadOnConflict(error) {
    if (error && error.status === 409) {
      discardPendingWrites(error.message || BRAND_CONFLICT);
      try { await loadSystem({ skipAdapt: true }); } catch (_reload) { /* keep the write error */ }
    }
  }

  let writeQueue = Promise.resolve();

  async function writeJson(url, extra) {
    const job = {
      url,
      extra: extra || {},
      revision: currentRevision(),
      epoch: writeEpoch,
    };
    const run = writeQueue.then(async () => {
      const reason = queueApi.queuedWriteReason
        ? queueApi.queuedWriteReason(
          job.revision,
          currentRevision(),
          job.epoch,
          writeEpoch,
          lastWriteSucceeded
        )
        : ((job.epoch !== writeEpoch || job.revision !== currentRevision()) ? 'stale' : null);
      if (reason) {
        const message = queueApi.messageFor ? queueApi.messageFor(reason) : DISCARDED_EDIT;
        const error = new Error(message);
        error.discarded = true;
        error.reason = reason;
        setStatus(message);
        pushConsole({ step: 'http', status: 'error', error: message });
        throw error;
      }
      try {
        const data = await readJson(await fetch(job.url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(revisionBody(job.extra, job.revision)),
        }));
        lastWriteSucceeded = true;
        return data;
      } catch (error) {
        lastWriteSucceeded = false;
        await reloadOnConflict(error);
        throw error;
      }
    });
    writeQueue = run.catch(() => {});
    return run;
  }

  function slimConsoleItem(item) {
    return {
      id: item.id,
      hop: item.hop || 0,
      step: item.step,
      status: item.status,
      model: item.model,
      duration_ms: item.duration_ms,
      usage: item.usage,
      error: item.error,
      notes: item.notes,
      artifact: item.artifact,
      result: item.result,
    };
  }

  function loadConsole() {
    try {
      const stored = JSON.parse(sessionStorage.getItem(CONSOLE_KEY) || '[]');
      state.console = Array.isArray(stored) ? stored.slice(-CONSOLE_MAX) : [];
    } catch (_error) {
      state.console = [];
    }
  }

  function saveConsole() {
    try {
      sessionStorage.setItem(CONSOLE_KEY, JSON.stringify(state.console.slice(-CONSOLE_MAX).map(slimConsoleItem)));
    } catch (_error) {
      /* ignore quota */
    }
  }

  function setConsoleOpen(open) {
    state.consoleOpen = Boolean(open);
    const host = $('mcDsa');
    const panel = $('mcDsaConsole');
    const tab = $('mcDsaConsoleTab');
    if (host) host.dataset.console = state.consoleOpen ? 'open' : 'closed';
    if (panel) panel.hidden = !state.consoleOpen;
    if (tab) tab.setAttribute('aria-expanded', state.consoleOpen ? 'true' : 'false');
  }

  function stepLabel(step) {
    return {
      compose: 'Montar DNA',
      contrast: 'Contraste',
      review: 'Revisar fidelidade',
      track: 'Gerar trilha',
      rules: 'Regras da IA',
      campaign: 'Campanha',
      refine: 'Refinar',
      persist: 'Gravar',
      report: 'Relatório',
      validação: 'Validação',
      render: 'Render',
      needs_input: 'Falta dado',
      loop: 'Hop',
      http: 'HTTP',
      llm: 'Modelo',
      ready: 'Pronto',
    }[step] || step || 'Passo';
  }

  function modelLabel(model) {
    const value = String(model || '');
    return value.includes('/') ? value.split('/').pop() : value;
  }

  function durationLabel(ms) {
    const value = Number(ms) || 0;
    if (!value) return '';
    return value >= 1000 ? `${(value / 1000).toFixed(1)}s` : `${value}ms`;
  }

  function usageLabel(usage) {
    if (!usage || typeof usage !== 'object') return '';
    if (usage.prompt_tokens == null && usage.completion_tokens == null) return '';
    return `${usage.prompt_tokens ?? '–'}→${usage.completion_tokens ?? '–'}`;
  }

  function resultFromOutput(output, error, notes, artifact) {
    if (error) return String(error);
    const text = String(output || '').replace(/^```(?:json)?\n?/i, '').replace(/\n```$/, '');
    try {
      const parsed = JSON.parse(text);
      const copy = parsed.ad_copy || {};
      if (copy.headline) return copy.cta ? `${copy.headline} — ${copy.cta}` : copy.headline;
      if (Object.prototype.hasOwnProperty.call(parsed, 'passed')) {
        return parsed.passed ? `passou${parsed.score != null ? ` (${parsed.score})` : ''}` : 'não passou';
      }
    } catch (_error) {
      const start = text.indexOf('{');
      const end = text.lastIndexOf('}');
      if (start >= 0 && end > start) {
        try {
          return resultFromOutput(text.slice(start, end + 1), '', notes, artifact);
        } catch (_nested) {
          /* ignore */
        }
      }
    }
    if (artifact) return artifact;
    const note = (notes || []).find(Boolean);
    if (note) return String(note);
    return text.slice(0, 160);
  }

  function lastConsoleItem() {
    return state.console[state.console.length - 1] || null;
  }

  function settleRunning(step) {
    state.console = state.console.filter((item) => !(
      item.status === 'running' && (item.step === step || item.step === 'loop')
    ));
  }

  function renderConsole() {
    const list = $('mcDsaConsoleList');
    const count = $('mcDsaConsoleCount');
    const live = $('mcDsaConsoleLive');
    const tab = $('mcDsaConsoleTab');
    const items = state.console.slice(-CONSOLE_MAX);
    const last = lastConsoleItem();
    const hasError = items.some((item) => item.status === 'error');
    if (count) count.textContent = items.length ? `${items.length} ${items.length === 1 ? 'passo' : 'passos'}` : '';
    if (live) live.textContent = last ? (last.result || stepLabel(last.step)) : '';
    if (tab) tab.classList.toggle('is-error', hasError);
    if (!list) return;
    list.innerHTML = items.map((item, index) => {
      const notes = (item.notes || []).filter(Boolean).map((note) => `<p class="mc-dsa-console-notes">${escapeHtml(note)}</p>`).join('');
      const error = item.error ? `<p class="mc-dsa-console-error">${escapeHtml(item.error)}</p>` : '';
      const artifact = item.artifact
        ? `<p class="mc-dsa-console-artifact"><a href="${escapeHtml(item.artifact)}" target="_blank" rel="noreferrer">Ver geração</a></p>`
        : '';
      const dump = [item.input, item.output].filter(Boolean).join('\n\n');
      const model = [modelLabel(item.model), durationLabel(item.duration_ms), usageLabel(item.usage)].filter(Boolean).join('  ');
      const result = item.result || resultFromOutput(item.output, item.error, item.notes, item.artifact);
      const canOpen = Boolean(dump || error || notes || artifact);
      const head = (
        `<span class="mc-dsa-console-hop">${index + 1}</span>`
        + `<b>${escapeHtml(stepLabel(item.step))}</b>`
        + (model ? `<p class="mc-dsa-console-meta">${escapeHtml(model)}</p>` : '')
        + (result ? `<p class="mc-dsa-console-result">${escapeHtml(result)}</p>` : '')
      );
      return (
        `<li data-status="${escapeHtml(item.status || 'ok')}">`
        + `<details>`
        + `<summary>${head}</summary>`
        + (canOpen
          ? `<div class="mc-dsa-console-body">${error}${notes}${artifact}`
            + (dump ? `<pre>${escapeHtml(dump)}</pre>` : '')
            + `</div>`
          : '')
        + `</details></li>`
      );
    }).join('');
    list.scrollTop = list.scrollHeight;
  }

  function pushConsole(entry) {
    state.console.push({
      id: entry.id || `step-${Date.now()}-${state.console.length + 1}`,
      hop: entry.hop || state.console.length + 1,
      step: entry.step || 'passo',
      status: entry.status || 'ok',
      model: entry.model || '',
      duration_ms: entry.duration_ms || 0,
      usage: entry.usage || {},
      input: entry.input || entry.input_text || '',
      output: entry.output || '',
      error: entry.error || '',
      notes: entry.notes || [],
      artifact: entry.artifact || '',
      result: entry.result || resultFromOutput(entry.output, entry.error, entry.notes, entry.artifact),
    });
    state.console = state.console.slice(-CONSOLE_MAX);
    saveConsole();
    renderConsole();
    if (entry.status === 'running' || entry.status === 'error') {
      setConsoleOpen(true);
    }
  }

  function ingestRun(run) {
    const steps = run && Array.isArray(run.steps) ? run.steps : [];
    if (!steps.length) return;
    const seen = new Set(state.console.map((item) => item.id));
    steps.forEach((step) => {
      const id = `${run.run_id || 'run'}-${step.id || step.step}`;
      if (seen.has(id)) return;
      seen.add(id);
      settleRunning(step.step);
      state.console.push({
        id,
        hop: state.console.length + 1,
        step: step.step || 'passo',
        status: step.status || 'ok',
        model: step.model || '',
        duration_ms: step.duration_ms || 0,
        usage: step.usage || {},
        input: step.input || '',
        output: step.output || '',
        error: step.error || '',
        notes: step.notes || [],
        artifact: step.artifact || '',
        result: step.result || resultFromOutput(step.output, step.error, step.notes, step.artifact),
      });
    });
    state.console = state.console.slice(-CONSOLE_MAX);
    saveConsole();
    renderConsole();
    if (steps.some((step) => step.status === 'error')) {
      setConsoleOpen(true);
    }
  }

  function setStatus(text) {
    const node = $('mcDsaStatus');
    if (node) node.textContent = text || '';
  }

  function currentId() {
    return state.clientId || 'centralcomm';
  }

  function isCampaign() {
    return Boolean(state.campaignId);
  }

  function brandUrl() {
    return `/lab/design-system/marca/${currentId()}`;
  }

  function pieceUrl() {
    const extra = state.highlight ? `&highlight=${encodeURIComponent(state.highlight)}` : '';
    if (isCampaign()) {
      return `/lab/design-system/campanha/${state.campaignId}?format=${state.format}&layers=${state.layers}${extra}`;
    }
    return `${brandUrl()}?format=${state.format}&layers=${state.layers}${extra}`;
  }

  function setStage(format, archetype) {
    if (format) state.format = format;
    if (archetype) state.archetype = archetype;
    state.stageOpen = true;
    const stage = $('mcDsaStage');
    if (stage) stage.hidden = false;
    syncFrames();
  }

  function hideStage() {
    state.stageOpen = true;
    const stage = $('mcDsaStage');
    if (stage) stage.hidden = false;
  }

  function renderClients() {
    const select = $('mcDsaClient');
    if (!select) return;
    const extras = state.clients.map((item) => (
      `<option value="${item.id}">${escapeHtml(item.name || item.id)}</option>`
    )).join('');
    select.innerHTML = `<option value="centralcomm">CentralComm Ads</option>${extras}`;
    select.value = currentId();
  }

  function renderCampaigns() {
    const select = $('mcDsaCampaign');
    if (!select) return;
    const extras = state.campaigns
      .filter((item) => !state.clientId || state.clientId === 'centralcomm' || String(item.client_id) === String(state.clientId))
      .map((item) => (
        `<option value="${item.id}">${escapeHtml(item.name || item.id)}</option>`
      )).join('');
    select.innerHTML = `<option value="">Só a marca</option><option value="centralcomm-verao">Verao · CentralComm</option>${extras}`;
    if (state.campaignId && ![...select.options].some((item) => item.value === String(state.campaignId))) {
      state.campaignId = '';
    }
    select.value = state.campaignId;
  }

  function renderLayerControl(system) {
    const input = $('mcDsaLayerCount');
    const label = $('mcDsaLayerLabel');
    const spec = system?.layers || {};
    if (input) {
      input.min = spec.min || 4;
      input.max = spec.max || 40;
      input.value = state.layers;
    }
    if (label) {
      const extras = Math.max(0, state.layers - 4);
      label.textContent = extras ? `${state.layers} camadas · ${extras} no poço` : '4 camadas';
    }
  }

  function renderLayerList(system) {
    const list = $('mcDsaLayerList');
    if (!list) return;
    const layers = [...(system?.adapt?.layers || [])].sort((left, right) => (right.z || 0) - (left.z || 0));
    list.innerHTML = layers.map((item) => {
      const selected = state.highlight === item.id ? ' is-selected' : '';
      const parked = item.parked ? ' no poço' : '';
      const core = CORE_ROLES.has(item.role) && !item.parked;
      return (
        `<li class="${core ? 'is-core' : 'is-extra'}">`
        + `<button type="button" class="mc-dsa-layer${selected}" data-layer="${escapeHtml(item.id)}">`
        + `<strong>${escapeHtml(item.label)}</strong>`
        + `<small>${escapeHtml(item.role)}${parked} · ${Math.round(item.w)}×${Math.round(item.h)}</small>`
        + `</button>`
        + `<span class="mc-dsa-layer-move">`
        + `<button type="button" data-move="${escapeHtml(item.id)}" data-dir="-1" aria-label="Subir">↑</button>`
        + `<button type="button" data-move="${escapeHtml(item.id)}" data-dir="1" aria-label="Descer">↓</button>`
        + `</span></li>`
      );
    }).join('');
  }

  function hexColor(value) {
    return /^#[0-9A-Fa-f]{6}$/.test(value) ? value : '#000000';
  }

  function renderCatalog(system) {
    const host = $('mcDsaCatalog');
    if (!host) return;
    const catalog = system?.catalog || {};
    const dna = catalog.dna || system?.dna || {};
    const tokens = system?.tokens || {};
    const copy = system?.ad_copy || {};
    const pairs = system?.contrast?.pairs || {};
    const personality = (dna.personality || []).map((item) => `<li>${escapeHtml(item)}</li>`).join('');
    const must = (dna.must || []).map((item) => `<li>${escapeHtml(item)}</li>`).join('');
    const avoid = (dna.avoid || []).map((item) => `<li>${escapeHtml(item)}</li>`).join('');
    const colors = (catalog.token_roles || []).find((item) => item.id === 'colors');
    const swatches = (colors?.items || []).map((item) => (
      `<label class="mc-dsa-color" title="${escapeHtml(item.label)}">`
      + `<input type="color" data-token="${escapeHtml(item.id)}" value="${escapeHtml(hexColor(item.value))}" aria-label="${escapeHtml(item.label)}">`
      + `</label>`
    )).join('');
    const components = (catalog.components || []).map((item) => (
      `<article class="mc-dsa-comp" data-comp="${escapeHtml(item.id)}">`
      + (item.image ? `<img src="${escapeHtml(item.image)}" alt="">` : `<span class="mc-dsa-comp-mark" style="color:${escapeHtml(tokens.ink || '#1E4D4F')};font-family:${escapeHtml(tokens['font-display'] || 'Inter')},sans-serif">${escapeHtml(item.text || item.label)}</span>`)
      + `<strong>${escapeHtml(item.label)}</strong>`
      + `<small>P${item.priority}</small>`
      + `</article>`
    )).join('');
    const tracks = (system?.tracks || []).map((item) => {
      const label = TRACK_LABEL[item.id] || item.label;
      return (
        `<button type="button" class="mc-dsa-track" data-track="${escapeHtml(item.id)}">`
        + (item.url
          ? `<img src="${escapeHtml(item.url)}" alt="${escapeHtml(label)}">`
          : `<span class="mc-dsa-track-empty">${escapeHtml(label)}</span>`)
        + `</button>`
      );
    }).join('');
    const effects = catalog.effects || {};
    const formats = (catalog.iab_formats || []).map((item) => {
      const size = item.size_label || item.label;
      const active = item.key === state.format ? ' is-active' : '';
      const valid = item.valid || 'unchecked';
      const pending = item.pending || '';
      return (
        `<button type="button" class="mc-dsa-format${active}" data-format="${escapeHtml(item.key)}" data-valid="${escapeHtml(valid)}" data-pending="${escapeHtml(pending)}">`
        + `<strong>${escapeHtml(size)}</strong>`
        + `<em>${escapeHtml(item.density || '')}</em>`
        + `</button>`
      );
    }).join('');
    const pendingItems = system?.pendencies || catalog.pendencies || [];
    const pendingBlock = renderPendencies(pendingItems);
    host.innerHTML = (
      `<p class="mc-dsa-tagline">${escapeHtml(catalog.tagline || catalog.creative_line || '')}</p>`
      + `<section class="mc-dsa-block" data-block="dna">`
      + `<h2>DNA</h2>`
      + (dna.logo_url || dna.product_url ? `<img src="${escapeHtml(dna.product_url || dna.logo_url)}" alt="">` : '')
      + `<ul class="mc-dsa-chips">${personality}</ul>`
      + `<form class="mc-dsa-dna-form" id="mcDsaDna">`
      + `<label>Personalidade <input name="personality" value="${escapeHtml((dna.personality || []).join(', '))}" maxlength="180"></label>`
      + `<label>Obrigatório <input name="must" value="${escapeHtml((dna.must || []).join(', '))}" maxlength="240"></label>`
      + `<label>Evitar <input name="avoid" value="${escapeHtml((dna.avoid || []).join(', '))}" maxlength="240"></label>`
      + `</form>`
      + `<form class="mc-dsa-copy" id="mcDsaCopy">`
      + `<label>Headline <input name="headline" value="${escapeHtml(copy.headline || '')}" maxlength="80"></label>`
      + `<label>Apoio <input name="support" value="${escapeHtml(copy.support || '')}" maxlength="140"></label>`
      + `<label>CTA <input name="cta" value="${escapeHtml(copy.cta || '')}" maxlength="32"></label>`
      + `<label>Legal <input name="legal" value="${escapeHtml(copy.legal || '')}" maxlength="80"></label>`
      + `</form>`
      + `<div class="mc-dsa-rules"><p>Fazer</p><ul>${must}</ul><p>Não fazer</p><ul>${avoid}</ul></div>`
      + `</section>`
      + `<section class="mc-dsa-block" data-block="tokens"><h2>Tinta</h2>`
      + `<div class="mc-dsa-dna-swatches">${swatches}</div>`
      + `<p class="mc-dsa-lockup" style="font-family:${escapeHtml(tokens['font-display'] || 'Inter')},sans-serif">${escapeHtml(copy.headline || dna.name || '')}</p>`
      + `<span class="mc-dsa-cta-chip" style="background:${escapeHtml(tokens.accent || '#111')};color:${escapeHtml(tokens.cta_ink || '#fff')}">${escapeHtml(copy.cta || 'CTA')}</span>`
      + `<div>${Object.entries(ROLE_INTENT).map(([key, intent]) => (
        `<button type="button" class="mc-dsa-intent" data-intent="${intent}">${INTENT_LABEL[intent]}</button>`
      )).join('')}</div>`
      + `<dl class="mc-dsa-contrast${system?.contrast?.passed ? ' is-ok' : ' is-bad'}">`
      + `<div><dt>Texto</dt><dd>${pairs.ink_on_paper || '—'} : 1</dd></div>`
      + `<div><dt>Botão</dt><dd>${pairs.cta_on_accent || '—'} : 1</dd></div>`
      + `</dl></section>`
      + `<section class="mc-dsa-block" data-block="effects"><h2>Efeito</h2>`
      + `<label>Lavagem <input data-token="wash-strength" value="${escapeHtml(effects['wash-strength'] || tokens['wash-strength'] || '16%')}" maxlength="8"></label>`
      + `<label>Grain <input data-token="grain" value="${escapeHtml(effects.grain || tokens.grain || '0.12')}" maxlength="8"></label>`
      + `</section>`
      + `<section class="mc-dsa-block" data-block="tracks"><h2>Trilhas</h2><div class="mc-dsa-tracks">${tracks}</div></section>`
      + `<section class="mc-dsa-block" data-block="components"><h2>Camadas</h2><div class="mc-dsa-comps">${components}</div></section>`
      + pendingBlock
      + `<section class="mc-dsa-block" data-block="formats"><h2>IAB</h2><div class="mc-dsa-formats is-catalog">${formats}</div></section>`
    );
  }

  function pendencyLabel(state) {
    return {
      needs_input: 'Falta dado',
      missing_track: 'Trilha',
      needs_confirm: 'Confirmar',
      stale: 'Stale',
    }[state] || state;
  }

  function renderPendencies(items) {
    const rows = Array.isArray(items) ? items : [];
    if (!rows.length) {
      return (
        `<section class="mc-dsa-block" data-block="pendencies">`
        + `<h2>Pendências</h2>`
        + `<p class="mc-dsa-pendencies-empty">Nenhuma pendência.</p>`
        + `</section>`
      );
    }
    const list = rows.map((item) => (
      `<li>`
      + `<button type="button" data-format="${escapeHtml(item.format || '')}">`
      + `<strong>${escapeHtml(item.size_label || item.label || item.format || '')}</strong>`
      + `<em>${escapeHtml(pendencyLabel(item.state))}</em>`
      + `<span>${escapeHtml(item.detail || '')}</span>`
      + `</button>`
      + `</li>`
    )).join('');
    return (
      `<section class="mc-dsa-block" data-block="pendencies">`
      + `<h2>Pendências</h2>`
      + `<ol class="mc-dsa-pendencies">${list}</ol>`
      + `</section>`
    );
  }

  function renderGrounds(system) {
    const host = $('mcDsaGrounds');
    if (!host) return;
    const tokens = system?.tokens || {};
    const grounds = system?.catalog?.backgrounds || system?.backgrounds || [];
    host.innerHTML = grounds.map((item) => {
      const kind = item.id || item.kind || 'paper';
      const active = item.active || kind === tokens['ground-kind'] ? ' is-active' : '';
      const fill = item.preview || item.fill || tokens.paper || '#fff';
      const image = item.image || (kind === 'image' ? tokens.ground : '');
      return (
        `<button type="button" class="mc-dsa-ground${active}" data-ground="${escapeHtml(kind)}">`
        + `<i style="background:${image ? `center/cover url('${escapeHtml(image)}')` : escapeHtml(fill)}"></i>`
        + `<span>${escapeHtml(item.label || kind)}</span>`
        + `</button>`
      );
    }).join('');
  }

  function renderArchBoard(system) {
    const host = $('mcDsaArchBoard');
    if (!host) return;
    const tokens = system?.tokens || {};
    const rows = system?.catalog?.archetypes || system?.archetypes || [];
    host.innerHTML = rows.map((item) => {
      const image = item.image || '';
      const wash = item.ground === 'wash';
      const bg = image
        ? `center/cover url('${escapeHtml(image)}')`
        : (wash ? tokens.ink : tokens.paper);
      const fg = wash && !image ? (tokens.paper || '#fff') : (tokens.ink || '#111');
      return (
        `<button type="button" class="mc-dsa-arch${item.active || item.id === state.archetype ? ' is-active' : ''}" data-archetype="${escapeHtml(item.id)}" data-format="${escapeHtml(item.format || 'iab-billboard')}">`
        + `<span class="mc-dsa-arch-stage" style="background:${escapeHtml(bg)};color:${escapeHtml(fg)}">`
        + `<strong>${escapeHtml(item.headline || item.label)}</strong>`
        + `<em>${escapeHtml(item.cta || '')}</em>`
        + `</span>`
        + `<b>${escapeHtml(item.label)}</b>`
        + `</button>`
      );
    }).join('');
  }

  function renderArchetypes(system) {
    const host = $('mcDsaArchetypes');
    if (!host) return;
    const rows = system?.archetypes || system?.catalog?.archetypes || [];
    host.innerHTML = rows.map((item) => (
      `<button type="button" class="mc-dsa-arch${item.id === state.archetype || item.active ? ' is-active' : ''}" data-archetype="${escapeHtml(item.id)}" data-format="${escapeHtml(item.format)}">${escapeHtml(item.label)}</button>`
    )).join('');
  }

  function renderProvenance(system) {
    const node = $('mcDsaProvenance');
    if (!node) return;
    const banner = system?.provenance?.banner || {};
    if (!banner.text) {
      node.hidden = true;
      node.textContent = '';
      return;
    }
    node.hidden = false;
    node.className = `mc-dsa-provenance is-${banner.kind === 'ok' ? 'ok' : 'warn'}`;
    node.textContent = banner.text;
  }

  function renderStorage(system) {
    const node = $('mcDsaStorage');
    if (!node) return;
    const storage = system?.storage || {};
    if (!storage.orphan) {
      node.hidden = true;
      node.textContent = '';
      return;
    }
    node.hidden = false;
    node.className = 'mc-dsa-provenance is-warn';
    node.textContent = storage.label || 'Este Ads veio da projeção. Grave na marca para ficar canônico.';
  }

  function renderNeedsInput(system) {
    const node = $('mcDsaNeedsInput');
    if (!node) return;
    const items = system?.needs_input || system?.loop?.needs_input || [];
    const label = system?.loop?.action === 'needs_input'
      ? (system.loop.label || '')
      : '';
    if (!items.length && !label) {
      node.hidden = true;
      node.textContent = '';
      return;
    }
    node.hidden = false;
    node.className = 'mc-dsa-provenance is-warn';
    node.textContent = label || (items.length === 1 ? `Falta ${items[0]}.` : `Falta ${items.join(', ')}.`);
  }

  function renderPassMeta(system) {
    const node = $('mcDsaPass');
    if (!node) return;
    const format = system?.adapt?.format || {};
    node.textContent = format.size_label
      ? `${format.label} · ${format.size_label} · ${state.layers} camadas`
      : '';
  }

  function syncFrames() {
    if (!state.stageOpen) return;
    const piece = pieceUrl();
    const pieceFrame = $('mcDsaFrame');
    if (pieceFrame && pieceFrame.src !== new URL(piece, window.location.origin).href) {
      pieceFrame.src = piece;
    }
  }

  function renderSystem(system) {
    state.system = system;
    if (system?.adapt?.format?.key && state.stageOpen) {
      state.format = system.adapt.format.key;
    }
    if (system?.adapt?.layer_count) state.layers = system.adapt.layer_count;
    if (system?.archetype) state.archetype = system.archetype;
    const exists = Boolean(system?.exists);
    const approved = system?.status === 'approved';
    const offer = $('mcDsaOffer');
    const create = $('mcDsaCreate');
    const approve = $('mcDsaApprove');
    if (offer) {
      if (system?.scope === 'campaign' && !exists) {
        offer.textContent = 'A campanha ainda não herdou a tinta da marca.';
      } else if (system?.scope === 'campaign') {
        offer.textContent = system.creative_line || 'Campanha herda a tinta. Copy e recortes mudam.';
      } else if (system?.preset) {
        offer.textContent = 'CentralComm Ads. Ajuste a tinta, depois assente no IAB.';
      } else if (!exists) {
        offer.textContent = 'A marca ainda não tem linha de anúncio. Monte a partir do logo e da paleta.';
      } else if (approved) {
        offer.textContent = 'Aprovado. Abra um formato IAB.';
      } else {
        offer.textContent = 'Rascunho da marca. Ajuste no catálogo, depois aprove.';
      }
    }
    if (create) {
      create.textContent = 'Montar a marca';
      create.disabled = state.looping || isCampaign();
    }
    const campaignMount = $('mcDsaCampaignMount');
    if (campaignMount) {
      campaignMount.disabled = state.looping || !state.campaignId;
    }
    if (approve) approve.disabled = !exists || approved || system?.scope === 'campaign';
    const confer = $('mcDsaValidateRender');
    if (confer) confer.disabled = state.looping || !(exists || system?.preset);
    renderCampaigns();
    renderProvenance(system);
    renderStorage(system);
    renderNeedsInput(system);
    renderCatalog(system);
    renderGrounds(system);
    renderArchBoard(system);
    renderArchetypes(system);
    renderLayerControl(system);
    renderLayerList(system);
    renderPassMeta(system);
    syncFrames();
    logValidation(system);
  }

  let lastValidationFingerprint = '';

  function logValidation(system) {
    const report = system && system.validation;
    const digest = report && report.fingerprint;
    if (!digest || digest === lastValidationFingerprint) return;
    lastValidationFingerprint = digest;
    const stale = Number(report.stale_count) || 0;
    const short = report.fingerprint_short || digest.slice(0, 8);
    pushConsole({
      step: 'validação',
      status: report.passed ? 'ok' : 'error',
      result: `${short} · ${stale} stale`,
      notes: stale
        ? [`${stale} formato${stale === 1 ? '' : 's'} stale.`]
        : [report.notes && report.notes[0] ? report.notes[0] : 'Contrato atual.'],
    });
  }

  function logRender(system) {
    const report = system && system.validation;
    if (!report || !report.render || report.render === 'skipped') return;
    const failed = report.render === 'failed';
    pushConsole({
      step: 'render',
      status: failed ? 'error' : 'ok',
      result: failed
        ? ((report.defects && report.defects[0]) || 'peça falhou')
        : 'peça ok',
      notes: report.notes || [],
    });
  }

  async function loadSystem(options) {
    const url = isCampaign() ? API.campaign(state.campaignId) : API.brand(currentId());
    const data = await readJson(await fetch(url));
    lastWriteSucceeded = false;
    renderSystem(data);
    if ((data.exists || data.preset) && !options?.skipAdapt) await adaptSystem();
  }

  async function adaptSystem() {
    const url = isCampaign() ? API.campaignAdapt(state.campaignId) : API.adapt(currentId());
    const data = await writeJson(url, {
      format: state.format,
      layers: state.layers,
      swaps: state.swaps,
      archetype: state.archetype,
    });
    renderSystem(data);
  }

  async function createSystem() {
    const url = isCampaign() ? API.campaign(state.campaignId) : API.brand(currentId());
    const data = await writeJson(url);
    renderSystem(data);
    return data;
  }

  async function improveSystem(intent) {
    setStatus(`Ajustando ${INTENT_LABEL[intent] || intent}.`);
    const data = await writeJson(API.refine(currentId()), { intent });
    renderSystem(data);
    setStatus('Ajuste aplicado no catálogo.');
  }

  async function approveSystem() {
    setStatus('Aprovando a marca.');
    const data = await writeJson(API.approve(currentId()));
    renderSystem(data);
    setStatus('Marca aprovada.');
  }

  async function validateRender() {
    const url = isCampaign()
      ? API.campaignValidateRender(state.campaignId)
      : API.validateRender(currentId());
    setStatus('Conferindo a peça no browser.');
    const data = await writeJson(url, {
      format: state.format,
      layers: state.layers,
    });
    renderSystem(data);
    logRender(data);
    const report = data.validation || {};
    if (report.render === 'skipped') {
      setStatus(report.notes && report.notes[0] ? report.notes[0] : 'Render não conferido.');
      return;
    }
    setStatus(report.render === 'passed' ? 'Peça conferida.' : 'A peça falhou no specimen.');
  }

  async function patchSystem(tokens, adCopy, dna, archetype) {
    const data = await writeJson(API.tokens(currentId()), {
      tokens: tokens || undefined,
      ad_copy: adCopy || undefined,
      dna: dna || undefined,
      archetype: archetype || undefined,
    });
    renderSystem(data);
  }

  async function generateTrack(trackId) {
    const data = await writeJson(API.track(currentId(), trackId));
    renderSystem(data);
    return data;
  }

  async function continueLoop() {
    if (state.looping) return;
    state.looping = true;
    const create = $('mcDsaCreate');
    if (create) create.disabled = true;
    try {
      setConsoleOpen(true);
      for (let hop = 0; hop < 8; hop += 1) {
        setStatus('Montando a linha da marca.');
        pushConsole({
          id: `hop-${hop + 1}`,
          hop: hop + 1,
          step: 'loop',
          status: 'running',
          notes: [`${hop + 1}  ${currentId()}`],
          result: `hop ${hop + 1}`,
        });
        const data = await writeJson(API.loop(currentId()));
        settleRunning('loop');
        renderSystem(data);
        const info = data.loop || {};
        setStatus(info.label || '');
        if (info.action === 'needs_input') {
          pushConsole({
            step: 'needs_input',
            status: 'ok',
            notes: info.needs_input || [],
            result: info.label || 'Falta dado da marca.',
          });
          break;
        }
        if (info.action === 'track' && info.track_id) {
          if (info.track_id === 'wash') continue;
          setStatus(TRACK_LABEL[info.track_id] || `Gerando ${info.track_id}.`);
          pushConsole({
            step: 'track',
            status: 'running',
            notes: [info.track_id],
            result: TRACK_LABEL[info.track_id] || info.track_id,
          });
          try {
            await generateTrack(info.track_id);
            settleRunning('track');
          } catch (error) {
            settleRunning('track');
            setStatus(error.message);
            break;
          }
          continue;
        }
        if (info.ready) {
          setStatus('Pronto. Abra um formato IAB.');
          break;
        }
        if (!['compose', 'contrast', 'review', 'rules'].includes(info.action)) break;
      }
    } finally {
      state.looping = false;
      if (create) create.disabled = false;
    }
  }

  async function mountBrand() {
    state.campaignId = '';
    renderCampaigns();
    const exists = Boolean(state.system?.exists || state.system?.preset);
    if (!exists || state.system?.scope === 'campaign') {
      setStatus('Montando a marca.');
      await createSystem();
    }
    await continueLoop();
  }

  async function mountCampaign() {
    if (!state.campaignId) {
      throw new Error('Escolha a campanha. A tinta da marca fica travada.');
    }
    setStatus('Montando a campanha.');
    await createSystem();
    setStatus(state.system?.creative_line || 'Campanha na tinta da marca.');
    if (state.system?.exists || state.system?.preset) await adaptSystem();
  }

  function queuePatch(tokens, adCopy, dna) {
    pendingPatch = queueApi.mergePatch
      ? queueApi.mergePatch(pendingPatch, { tokens: tokens || {}, adCopy: adCopy || {}, dna: dna || {} })
      : Object.assign(pendingPatch, { tokens: tokens || pendingPatch.tokens, adCopy: adCopy || pendingPatch.adCopy, dna: dna || pendingPatch.dna });
    window.clearTimeout(state.patchTimer);
    state.patchTimer = window.setTimeout(async () => {
      const payload = pendingPatch;
      pendingPatch = queueApi.emptyPatch ? queueApi.emptyPatch() : { tokens: {}, adCopy: {}, dna: {} };
      if (queueApi.patchIsEmpty && queueApi.patchIsEmpty(payload)) return;
      try {
        await patchSystem(payload.tokens, payload.adCopy, payload.dna);
        setStatus('Gravado.');
        if (queueApi.patchIsEmpty && !queueApi.patchIsEmpty(pendingPatch)) {
          queuePatch();
        }
      } catch (error) {
        setStatus(error.message);
      }
    }, 280);
  }

  function neighborId(layerId, dir) {
    const layers = [...(state.system?.adapt?.layers || [])].sort((left, right) => (left.z || 0) - (right.z || 0));
    const index = layers.findIndex((item) => item.id === layerId);
    const other = layers[index + Number(dir)];
    return other?.id || '';
  }

  async function openPiece(format, archetype) {
    setStage(format, archetype);
    try {
      await adaptSystem();
    } catch (error) {
      setStatus(error.message);
    }
  }

  async function boot() {
    loadConsole();
    renderConsole();
    $('mcDsaConsoleTab')?.addEventListener('click', () => setConsoleOpen(!state.consoleOpen));
    $('mcDsaConsoleClose')?.addEventListener('click', () => setConsoleOpen(false));
    $('mcDsaConsoleClear')?.addEventListener('click', () => {
      state.console = [];
      saveConsole();
      renderConsole();
    });
    try {
      state.clients = await readJson(await fetch(API.clients));
    } catch (_error) {
      state.clients = [];
    }
    try {
      const campaigns = await readJson(await fetch(API.campaigns));
      state.campaigns = Array.isArray(campaigns) ? campaigns : [];
    } catch (_error) {
      state.campaigns = [];
    }
    renderClients();
    renderCampaigns();
    $('mcDsaClient')?.addEventListener('change', async (event) => {
      state.clientId = event.target.value || 'centralcomm';
      state.campaignId = '';
      state.swaps = [];
      state.highlight = '';
      hideStage();
      setStatus('');
      renderCampaigns();
      try {
        await loadSystem();
      } catch (error) {
        setStatus(error.message);
      }
    });
    $('mcDsaCampaign')?.addEventListener('change', async (event) => {
      state.campaignId = event.target.value || '';
      state.swaps = [];
      state.highlight = '';
      setStatus('');
      try {
        await loadSystem();
      } catch (error) {
        setStatus(error.message);
      }
    });
    $('mcDsaLayerCount')?.addEventListener('input', (event) => {
      state.layers = Number(event.target.value) || 4;
      renderLayerControl(state.system);
    });
    $('mcDsaLayerCount')?.addEventListener('change', async () => {
      state.swaps = [];
      try {
        await adaptSystem();
      } catch (error) {
        setStatus(error.message);
      }
    });
    $('mcDsaLayerList')?.addEventListener('click', async (event) => {
      const move = event.target.closest('[data-move]');
      if (move) {
        const other = neighborId(move.getAttribute('data-move'), move.getAttribute('data-dir'));
        if (!other) return;
        state.swaps = [...state.swaps, [move.getAttribute('data-move'), other]];
        try {
          await adaptSystem();
          setStatus('Camada movida.');
        } catch (error) {
          setStatus(error.message);
        }
        return;
      }
      const button = event.target.closest('[data-layer]');
      if (!button) return;
      const id = button.getAttribute('data-layer');
      state.highlight = state.highlight === id ? '' : id;
      renderLayerList(state.system);
      syncFrames();
    });
    $('mcDsaCatalog')?.addEventListener('click', async (event) => {
      const track = event.target.closest('[data-track]');
      if (track) {
        track.disabled = true;
        const id = track.getAttribute('data-track');
        setStatus(TRACK_LABEL[id] || `Gerando ${id}.`);
        try {
          await generateTrack(id);
          setStatus('Trilha gerada.');
        } catch (error) {
          setStatus(error.message);
        } finally {
          track.disabled = false;
        }
        return;
      }
      const intent = event.target.closest('[data-intent]');
      if (intent) {
        try {
          await improveSystem(intent.getAttribute('data-intent'));
        } catch (error) {
          setStatus(error.message);
        }
        return;
      }
      const archetype = event.target.closest('[data-archetype]');
      if (archetype) {
        await openPiece(
          archetype.getAttribute('data-format') || state.format,
          archetype.getAttribute('data-archetype') || 'brand',
        );
        return;
      }
      const format = event.target.closest('[data-format]');
      if (format) {
        await openPiece(format.getAttribute('data-format') || 'iab-billboard', state.archetype);
      }
    });
    $('mcDsaCatalog')?.addEventListener('input', (event) => {
      const token = event.target.closest('[data-token]');
      if (token) {
        let value = token.value;
        if (token.type === 'color') value = value.toUpperCase();
        queuePatch({ [token.getAttribute('data-token')]: value });
        return;
      }
      const copy = event.target.closest('#mcDsaCopy');
      if (copy) {
        queuePatch(null, {
          headline: copy.elements.headline.value,
          support: copy.elements.support.value,
          cta: copy.elements.cta.value,
          legal: copy.elements.legal.value,
        });
      }
    });
    $('mcDsaCatalog')?.addEventListener('change', (event) => {
      const form = event.target.closest('#mcDsaDna');
      if (!form) return;
      queuePatch(null, null, {
        personality: form.elements.personality.value,
        must: form.elements.must.value,
        avoid: form.elements.avoid.value,
      });
    });
    $('mcDsaArchetypes')?.addEventListener('click', async (event) => {
      const button = event.target.closest('[data-archetype]');
      if (!button) return;
      await openPiece(
        button.getAttribute('data-format') || state.format,
        button.getAttribute('data-archetype') || 'brand',
      );
    });
    $('mcDsaGrounds')?.addEventListener('click', async (event) => {
      const button = event.target.closest('[data-ground]');
      if (!button) return;
      try {
        await patchSystem({ 'ground-kind': button.getAttribute('data-ground') });
        if (state.system?.exists || state.system?.preset) await adaptSystem();
      } catch (error) {
        setStatus(error.message);
      }
    });
    $('mcDsaArchBoard')?.addEventListener('click', async (event) => {
      const button = event.target.closest('[data-archetype]');
      if (!button) return;
      await openPiece(
        button.getAttribute('data-format') || state.format,
        button.getAttribute('data-archetype') || 'brand',
      );
    });
    $('mcDsaCreate')?.addEventListener('click', async () => {
      try {
        await mountBrand();
      } catch (error) {
        setStatus(error.message);
      }
    });
    $('mcDsaCampaignMount')?.addEventListener('click', async () => {
      try {
        await mountCampaign();
      } catch (error) {
        setStatus(error.message);
      }
    });
    $('mcDsaApprove')?.addEventListener('click', async () => {
      try {
        await approveSystem();
      } catch (error) {
        setStatus(error.message);
      }
    });
    $('mcDsaValidateRender')?.addEventListener('click', async () => {
      const button = $('mcDsaValidateRender');
      if (button) button.disabled = true;
      try {
        await validateRender();
      } catch (error) {
        setStatus(error.message);
      } finally {
        if (button) button.disabled = state.looping || !(state.system?.exists || state.system?.preset);
      }
    });
    try {
      await loadSystem();
    } catch (error) {
      setStatus(error.message);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
