/* UI adapter for the existing swap pipeline. No generation on local edits. */
(function () {
  'use strict';
  const FIELDS = [
    ['headline', 'mcSwapHeadline', 'Título'], ['support', 'mcSwapSupport', 'Apoio'],
    ['subtitle', 'mcTrocrSubtitle', 'Subtítulo'], ['price', 'mcTrocrPrice', 'Preço'],
    ['cta', 'mcSwapCta', 'CTA'], ['cta2', 'mcTrocrCta2', 'Segundo CTA'],
    ['dates', 'mcTrocrDates', 'Datas'], ['venue', 'mcTrocrVenue', 'Local'],
    ['logo', 'mcTrocrLogo', 'Marca'], ['disclaimer', 'mcTrocrDisclaimer', 'Texto legal'],
  ];
  const INPUTS = [...FIELDS.map((row) => row[1]), 'mcSwapNote', 'mcTrocrPrompt'];
  const GROUPS = ['mcTrocrPreserve', 'mcTrocrAlter', 'mcTrocrAnalysis'];
  const LABELS = { person: 'Pessoa', background: 'Fundo', product: 'Produto', graphic: 'Grafismo' };
  const $ = (id) => document.getElementById(id);
  const clone = (value) => JSON.parse(JSON.stringify(value));

  window.TrocrEditor = function (api) {
    const { state } = api;
    let selected = '';
    let undo = [];
    let redo = [];
    let last = null;
    let applying = false;
    let frame = 0;
    let saveState = 'idle';
    let dirty = false;
    let context = '';
    const locked = new Map();

    function snapshot() {
      const values = {};
      INPUTS.forEach((id) => { if ($(id)) values[id] = $(id).value; });
      const checks = {};
      GROUPS.forEach((name) => {
        checks[name] = Array.from(document.querySelectorAll(`input[name="${name}"]:checked`), (node) => node.value);
      });
      return {
        version: 1, base_id: state.baseId, values, checks,
        aspect_ratio: state.aspectRatio, region: state.region ? clone(state.region) : null,
        quality: state.quality, brand_context: state.brandContext,
        prompt_edited: state.promptEdited, prompt_locked: state.promptLocked,
        force_image: Boolean($('mcTrocrForceImage')?.checked),
      };
    }

    function restore(draft) {
      if (!draft || draft.base_id !== state.baseId) return false;
      applying = true;
      INPUTS.forEach((id) => {
        if ($(id) && typeof draft.values?.[id] === 'string') $(id).value = draft.values[id];
      });
      GROUPS.forEach((name) => {
        if (!Array.isArray(draft.checks?.[name])) return;
        document.querySelectorAll(`input[name="${name}"]`).forEach((node) => {
          node.checked = draft.checks[name].includes(node.value);
        });
      });
      state.region = draft.region ? clone(draft.region) : null;
      state.selectedRegionField = state.region?.field || '';
      ['trocrRegionX','trocrRegionY','trocrRegionWidth','trocrRegionHeight'].forEach((id) => $(id)?.setCustomValidity(''));
      if ($('mcTrocrForceImage')) $('mcTrocrForceImage').checked = Boolean(draft.force_image);
      state.quality = draft.quality === 'production' ? 'production' : 'draft';
      state.brandContext = Boolean(draft.brand_context);
      state.promptEdited = Boolean(draft.prompt_edited);
      state.promptLocked = Boolean(draft.prompt_locked);
      if ($('mcTrocrPrompt')) $('mcTrocrPrompt').readOnly = !state.promptEdited;
      if ($('mcTrocrBrandContext')) $('mcTrocrBrandContext').checked = state.brandContext;
      document.querySelectorAll('input[name="mcTrocrQuality"]').forEach((node) => { node.checked = node.value === state.quality; });
      api.highlightQuality();
      api.selectFormat(draft.aspect_ratio || state.aspectRatio);
      api.syncOptionalUi();
      api.renderEditPanels();
      api.paintRegionBox();
      api.refreshPrompt();
      applying = false;
      render();
      return true;
    }

    function saveStatus(status, message) {
      saveState = status;
      if (status === 'saved') dirty = false;
      if (status === 'dirty' || status === 'error') dirty = true;
      const node = $('trocrSaveStatus');
      if (node) {
        node.dataset.status = status;
        node.textContent = message || ({ idle: 'Nenhuma alteração', dirty: 'Alterações pendentes', saving: 'Salvando…', saved: 'Edição salva', error: 'Falha ao salvar · tente novamente' })[status];
      }
      if ($('trocrExportDraft')) $('trocrExportDraft').hidden = status !== 'error';
      if ($('trocrSave')) $('trocrSave').disabled = status === 'saving' || !state.versions.length;
    }

    function changed() {
      if (applying || !state.baseId) return;
      const next = snapshot();
      if (last && JSON.stringify(last) !== JSON.stringify(next)) {
        undo.push(last);
        if (undo.length > 60) undo.shift();
        redo = [];
      }
      last = clone(next);
      state.editorDraft = next;
      saveStatus('dirty');
      api.schedulePersist();
      render();
    }

    function travel(direction) {
      const stack = direction === 'undo' ? undo : redo;
      if (!stack.length || state.generating) return;
      const next = stack.pop();
      (direction === 'undo' ? redo : undo).push(snapshot());
      restore(next);
      last = clone(next);
      state.editorDraft = next;
      saveStatus('dirty');
      api.schedulePersist();
      render();
    }

    function reset(draft) {
      context = `${state.runId}:${state.baseId}`;
      selected = '';
      undo = [];
      redo = [];
      if (draft) restore(draft);
      last = snapshot();
      state.editorDraft = state.baseId ? snapshot() : null;
      dirty = false;
      saveStatus(state.baseId ? 'saved' : 'idle');
      render();
    }

    function entries() {
      const rows = [];
      const recognized = state.lastRead?.elements || [];
      FIELDS.forEach(([role, field, label]) => {
        const text = $(field)?.value || '';
        const matches = recognized.filter((item) => item.role === (role === 'cta2' ? 'cta' : role));
        const detected = matches[role === 'cta2' ? 1 : 0];
        if (!text && !detected) return;
        const regionRole = role === 'support' ? 'secondary' : role;
        const box = state.region?.field === regionRole ? state.region.box : detected?.bbox_px;
        rows.push({ id: field, field, role, label, text, box, verified: detected?.user_verified, confidence: detected?.recognition_score ?? detected?.confidence });
      });
      recognized.filter((item) => LABELS[item.role]).forEach((item, index) => {
        rows.push({ id: item.id || `visual-${index}`, role: item.role, label: LABELS[item.role], text: item.text || '', box: item.bbox_px });
      });
      return rows;
    }

    function setTab(name) {
      document.querySelectorAll('[data-editor-tab]').forEach((node) => {
        const active = node.dataset.editorTab === name;
        node.setAttribute('aria-selected', String(active));
        node.tabIndex = active ? 0 : -1;
        const panel = $(node.getAttribute('aria-controls'));
        if (panel) panel.hidden = !active;
      });
      api.fitCreative();
    }

    function select(id) {
      const row = entries().find((item) => item.id === id);
      if (!row) return;
      selected = id;
      document.querySelectorAll('.trocr-field-selected').forEach((node) => node.classList.remove('trocr-field-selected'));
      if (row.field) {
        setTab('properties');
        const field = $(row.field);
        if ($('mcTrocrOcr')) $('mcTrocrOcr').open = true;
        const label = field?.closest('label');
        if (label) { label.hidden = false; label.classList.add('trocr-field-selected'); }
        field?.focus({ preventScroll: true });
        label?.scrollIntoView({ block: 'nearest', behavior: 'auto' });
      } else {
        setTab('ai');
      }
      render();
    }

    function render() {
      const list = $('trocrElementList');
      if (!list) return;
      const rows = entries();
      const query = ($('trocrElementSearch')?.value || '').toLocaleLowerCase();
      const filtered = rows.filter((row) => `${row.label} ${row.text}`.toLocaleLowerCase().includes(query));
      const fragment = document.createDocumentFragment();
      filtered.forEach((row) => {
        const button = document.createElement('button');
        button.type = 'button'; button.className = 'trocr-element-row';
        button.dataset.elementId = row.id;
        button.setAttribute('aria-pressed', String(selected === row.id));
        const icon = document.createElement('span'); icon.className = 'trocr-element-icon'; icon.textContent = row.field ? 'Tt' : '◇'; icon.setAttribute('aria-hidden', 'true');
        const copy = document.createElement('span'); copy.className = 'trocr-element-copy';
        const title = document.createElement('strong'); title.textContent = row.text || row.label;
        const uncertain=typeof row.confidence==='number'&&row.confidence<.8&&!row.verified;
        button.classList.toggle('trocr-ocr-review',uncertain);
        const meta = document.createElement('small'); meta.textContent = uncertain
          ? `${row.label} · Revisar OCR (${Math.round(row.confidence*100)}%)`
          : `${row.label} · ${row.box ? 'Texto localizado' : row.field ? 'Texto identificado' : 'Identificado'}`;
        copy.append(title, meta); button.append(icon, copy); fragment.append(button);
      });
      list.replaceChildren(fragment);
      $('trocrElementCount').textContent = rows.length;
      $('trocrElementEmpty').hidden = Boolean(filtered.length);
      $('trocrElementEmpty').textContent = query ? 'Nenhum elemento encontrado.' : state.baseId ? 'Nenhum elemento identificado. Preencha os campos manualmente.' : 'Envie uma peça para identificar seus elementos.';
      const row = rows.find((item) => item.id === selected);
      $('trocrSelection').hidden = !row;
      if (row) {
        $('trocrSelectedName').textContent = row.label;
        const markable = ['headline', 'support', 'price', 'cta'].includes(row.role);
        $('trocrMarkSelected').hidden = !markable;
        $('trocrMarkSelected').disabled = state.activeId !== state.baseId || state.generating;
        $('trocrSelectedHint').textContent = state.activeId !== state.baseId
          ? 'Visualize a versão base para marcar uma região.'
          : markable ? 'Marque a área do texto na imagem base. A alteração será incluída no próximo pedido.' : 'Use o assistente para solicitar mudanças neste elemento.';
      }
      const region = state.region;
      const regionRole = row?.role === 'support' ? 'secondary' : row?.role;
      $('trocrRegionGeometry').disabled = state.activeId !== state.baseId || state.generating;
      $('trocrRegionGeometry').hidden = !region?.box || region.field !== regionRole;
      if (region?.box && region.field === regionRole) {
        const [x,y,right,bottom] = region.box;
        [['trocrRegionX',x],['trocrRegionY',y],['trocrRegionWidth',right-x],['trocrRegionHeight',bottom-y]].forEach(([id,value]) => { if(document.activeElement !== $(id)) $(id).value=Math.round(value); });
      }
      $('trocrUndo').disabled = !undo.length || state.generating;
      $('trocrRedo').disabled = !redo.length || state.generating;
      $('trocrSave').disabled = saveState === 'saving' || !state.versions.length;
      queueOverlay();
    }

    function queueOverlay() {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(drawOverlay);
    }

    function drawOverlay() {
      const host = $('trocrElementOverlays');
      if (!host) return;
      host.replaceChildren();
      if (state.activeId !== state.baseId || state.viewMode !== 'view' || state.presentation !== 'final' || state.generating) return;
      const img = $('mcSwapImage');
      const content = api.imageContentRect(img);
      const frameBox = img?.parentElement?.getBoundingClientRect();
      if (!content || !frameBox) return;
      entries().filter((row) => Array.isArray(row.box) && row.box.length === 4).forEach((row) => {
        const [x1,y1,x2,y2] = row.box;
        if (![x1,y1,x2,y2].every(Number.isFinite) || x1 < 0 || y1 < 0 || x2 > content.nw || y2 > content.nh || x2 <= x1 || y2 <= y1) return;
        const node = document.createElement('button'); node.type = 'button'; node.className = 'trocr-element-box'; node.dataset.elementId = row.id;
        node.setAttribute('aria-label', `Selecionar ${row.label}`);
        node.setAttribute('aria-pressed', String(selected === row.id));
        Object.assign(node.style, { left: `${content.left-frameBox.left+x1*content.scale}px`, top: `${content.top-frameBox.top+y1*content.scale}px`, width: `${(x2-x1)*content.scale}px`, height: `${(y2-y1)*content.scale}px` });
        host.append(node);
      });
    }

    function showPlan(plan) {
      let host = $('trocrPlanSummary');
      if (!host) { host = document.createElement('section'); host.id = 'trocrPlanSummary'; host.className = 'trocr-plan-summary'; $('mcTrocrEditBlock')?.after(host); }
      host.replaceChildren();
      const title = document.createElement('h3'); title.textContent = 'Prévia das alterações'; host.append(title);
      const operations = plan.operations || plan.plan?.operations || [];
      if (!operations.length) { const p=document.createElement('p'); p.className='trocr-helper'; p.textContent=plan.preview || 'Descreva o que deseja mudar para revisar o pedido.'; host.append(p); return; }
      const list=document.createElement('dl');
      operations.forEach((op) => { const dt=document.createElement('dt'); dt.textContent=FIELDS.find((row)=>row[0]===op.field)?.[2] || op.field; const dd=document.createElement('dd'); dd.textContent=`${op.from || '(vazio)'} → ${op.to || '(remover)'}`; list.append(dt,dd); });
      host.append(list);
    }

    function setBusy(busy) {
      if (busy) {
        $('mcSwap').querySelectorAll('input,select,textarea,#mcTrocrNewPiece,#mcTrocrNewEdit,#mcTrocrHistoryBtn,#mcTrocrResetPanel,#trocrMarkSelected').forEach((node) => {
          locked.set(node, node.disabled); node.disabled = true;
        });
      } else {
        locked.forEach((disabled, node) => { node.disabled = disabled; }); locked.clear();
      }
      render();
    }

    function bind() {
      document.querySelectorAll('[data-editor-tab]').forEach((node) => {
        node.addEventListener('click', () => setTab(node.dataset.editorTab));
        node.addEventListener('keydown', (event) => {
          if (!['ArrowLeft','ArrowRight','Home','End'].includes(event.key)) return;
          event.preventDefault();
          const name = event.key === 'Home' ? 'properties' : event.key === 'End' ? 'ai' : node.dataset.editorTab === 'ai' ? 'properties' : 'ai';
          setTab(name); document.querySelector(`[data-editor-tab="${name}"]`)?.focus();
        });
      });
      ['trocrElementList','trocrElementOverlays'].forEach((id) => $(id)?.addEventListener('click', (event) => {
        const button = event.target.closest('[data-element-id]');
        if (button) { event.stopPropagation(); select(button.dataset.elementId); }
      }));
      $('trocrElementSearch')?.addEventListener('input', render);
      $('trocrShowFields')?.addEventListener('click', () => {
        setTab('properties'); $('mcTrocrOcr').open = true; $('mcSwapHeadline')?.focus();
      });
      $('trocrMarkSelected')?.addEventListener('click', () => {
        const row = entries().find((item) => item.id === selected);
        if (!row || state.activeId !== state.baseId) return;
        const role = row.role === 'support' ? 'secondary' : row.role;
        state.selectedRegionField = role;
        const alter = document.querySelector(`input[name="mcTrocrAlter"][value="${role}"]`);
        if (alter) alter.checked = true;
        if (!state.picking) api.togglePickRegion();
        api.refreshPrompt(); changed();
      });
      ['trocrRegionX','trocrRegionY','trocrRegionWidth','trocrRegionHeight'].forEach((id) => $(id)?.addEventListener('change', () => {
        if (!state.region || state.activeId !== state.baseId || state.generating) return;
        const [x,y,w,h]=['trocrRegionX','trocrRegionY','trocrRegionWidth','trocrRegionHeight'].map((key)=>$(key).valueAsNumber);
        const valid=[x,y,w,h].every(Number.isFinite) && x>=0 && y>=0 && w>=8 && h>=8 && x+w<=state.region.ref_width && y+h<=state.region.ref_height;
        $(id).setCustomValidity(valid ? '' : 'A região deve ficar dentro da imagem, com pelo menos 8 × 8 px.');
        if(!valid) { $(id).reportValidity(); return; }
        ['trocrRegionX','trocrRegionY','trocrRegionWidth','trocrRegionHeight'].forEach((key)=>$(key).setCustomValidity(''));
        state.region.box=[x,y,x+w,y+h]; api.paintRegionBox(); api.refreshPrompt(); changed();
      }));
      $('trocrUndo')?.addEventListener('click', () => travel('undo'));
      $('trocrRedo')?.addEventListener('click', () => travel('redo'));
      $('trocrExportDraft')?.addEventListener('click', () => {
        const url = URL.createObjectURL(new Blob([JSON.stringify({ run_id: state.runId, ...snapshot() }, null, 2)], {type:'application/json'}));
        const link = document.createElement('a'); link.href=url; link.download=`edicao-${state.runId || 'trocr'}.json`; link.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
      });
      $('trocrSave')?.addEventListener('click', () => { state.editorDraft = snapshot(); api.persistHistory(); });
      $('mcSwap')?.addEventListener('input', (event) => {
        if (!INPUTS.includes(event.target.id)) return;
        const role = {mcSwapHeadline:'headline', mcSwapSupport:'secondary', mcTrocrPrice:'price', mcSwapCta:'cta', mcTrocrCta2:'cta'}[event.target.id];
        if (role) { const toggle=document.querySelector(`input[name="mcTrocrAlter"][value="${role}"]`); if(toggle) toggle.checked=true; }
        changed();
      });
      $('mcSwap')?.addEventListener('change', (event) => {
        if (GROUPS.includes(event.target.name) || ['mcSwapOut','mcTrocrQuality'].includes(event.target.name) || ['mcTrocrBrandContext','mcTrocrForceImage'].includes(event.target.id)) changed();
      });
      $('mcSwap')?.addEventListener('keydown', (event) => {
        if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') { event.preventDefault(); state.editorDraft = snapshot(); api.persistHistory(); }
        if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'z' && !event.target.matches('input,textarea,[contenteditable]')) { event.preventDefault(); travel(event.shiftKey ? 'redo' : 'undo'); }
      });
      window.addEventListener('beforeunload', (event) => {
        if (dirty || saveState === 'saving') { event.preventDefault(); event.returnValue = ''; }
      });
      $('mcSwapImage')?.addEventListener('load', queueOverlay);
      if (window.ResizeObserver) new ResizeObserver(queueOverlay).observe($('mcTrocrViewport'));
      const prompt = $('mcTrocrEditBlock');
      if (prompt) {
        const suggestions = document.createElement('div'); suggestions.className = 'trocr-suggestions';
        [['Atualizar preço','Atualizar o preço para R$ __. Manter pessoas e fundo.'],['Trocar título','Trocar o título para “__”. Preservar o restante da peça.'],['Adaptar formato','Adaptar a composição ao formato selecionado, preservando a marca e a legibilidade.']].forEach(([label,text]) => {
          const button = document.createElement('button'); button.type='button'; button.textContent=label;
          button.addEventListener('click', () => { $('mcSwapNote').value=text; $('mcSwapNote').dispatchEvent(new Event('input',{bubbles:true})); $('mcSwapNote').focus(); });
          suggestions.append(button);
        });
        prompt.querySelector('h2')?.after(suggestions);
      }
      last = snapshot(); render();
    }
    bind();
    return { snapshot, restore, reset, changed, render, queueOverlay, saveStatus, setTab, setBusy, showPlan,
      isDirty: () => dirty || saveState === 'saving',
      sync: () => { if (context !== `${state.runId}:${state.baseId}`) reset(state.editorDraft); else render(); },
    };
  };
})();
