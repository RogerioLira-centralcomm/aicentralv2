/* Versioned artifact surface for Conversations V2. */
(() => {
  'use strict';
  const panel = document.getElementById('conversation-artifact-panel');
  const content = document.getElementById('conversation-artifact-content');
  const title = document.getElementById('conversation-artifact-title');
  const kind = document.getElementById('conversation-artifact-kind');
  const tools = document.getElementById('conversation-artifact-tools');
  const shell = document.querySelector('.workspace-conversations');
  if (!panel || !content) return;
  const csrf = () => document.querySelector('meta[name="csrf-token"]')?.content || '';
  const clean = value => String(value ?? '').trim();
  const request = async (path, method, data) => {
    const response = await fetch(path, {method, credentials:'same-origin', headers:{'Content-Type':'application/json','X-CSRF-Token':csrf()}, body:JSON.stringify(data)});
    const result = await response.json().catch(() => ({}));
    if (!response.ok) { const error = new Error(result.error || 'Não foi possível salvar o artefato.'); error.status = response.status; throw error; }
    return result;
  };
  const open = artifact => {
    if (!artifact?.id || !artifact?.content) return;
    let current = artifact, dirty = false;
    kind.textContent = ({brief:'Briefing',document:'Documento',note:'Nota',executive_summary:'Resumo executivo',media_plan:'Plano de mídia',scenario:'Cenário',research:'Pesquisa'})[artifact.type] || 'Artefato';
    title.textContent = artifact.title || artifact.content.title || 'Trabalho em andamento';
    content.replaceChildren(); tools?.replaceChildren();
    const meta = document.createElement('p'); meta.className = 'conversation-v2-artifact-meta';
    meta.textContent = `Rascunho · versão ${artifact.current_version}`; content.append(meta);
    const summary = document.createElement('textarea'); summary.className = 'conversation-v2-artifact-summary'; summary.value = clean(artifact.content.summary); summary.placeholder = 'Resumo do trabalho'; summary.setAttribute('aria-label','Resumo do artefato'); content.append(summary);
    const fields = document.createElement('div'); fields.className = 'conversation-v2-artifact-fields';
    (Array.isArray(artifact.content.fields) ? artifact.content.fields : []).forEach((field, index) => {
      const row = document.createElement('label'); row.className = 'conversation-v2-artifact-field'; row.dataset.state = field.state || 'inferred';
      const label = document.createElement('span'); label.textContent = clean(field.key) || `Campo ${index + 1}`;
      const input = document.createElement('textarea'); input.value = clean(field.value); input.rows = 2; input.dataset.fieldIndex = String(index);
      input.setAttribute('aria-label', label.textContent); row.append(label, input); fields.append(row);
    });
    content.append(fields);
    const status = document.createElement('p'); status.className = 'conversation-v2-artifact-status'; status.setAttribute('role','status'); content.append(status);
    const save = document.createElement('button'); save.type = 'button'; save.className = 'conversation-artifact-tool is-primary'; save.textContent = 'Salvar'; save.disabled = true;
    const markDirty = () => { dirty = true; save.disabled = false; status.textContent = 'Alterações não salvas'; };
    summary.addEventListener('input', markDirty); fields.addEventListener('input', markDirty);
    save.addEventListener('click', async () => {
      if (!dirty) return;
      save.disabled = true; save.textContent = 'Salvando…'; status.textContent = '';
      const nextContent = {...current.content, summary:summary.value.trim(), fields:(current.content.fields || []).map((field, index) => ({...field, value:fields.querySelector(`[data-field-index="${index}"]`)?.value.trim() || ''}))};
      try {
        const result = await request(`/workspace/api/v2/artifacts/${encodeURIComponent(current.id)}`, 'PATCH', {expected_version:current.current_version, content:nextContent, title:title.textContent, change_summary:'Revisão no painel da conversa'});
        current = result.artifact; dirty = false; meta.textContent = `Rascunho · versão ${current.current_version} · salvo agora`; status.textContent = 'Alterações salvas'; save.textContent = 'Salvo';
        window.setTimeout(() => { if (!dirty) { save.textContent = 'Salvar'; status.textContent = ''; } }, 1200);
      } catch (error) {
        save.disabled = false; save.textContent = 'Tentar novamente'; status.textContent = error.status === 409 ? 'Este artefato mudou em outra sessão. Atualize a página antes de salvar.' : error.message;
      }
    });
    tools?.append(save); panel.hidden = false; panel.tabIndex = -1; shell?.classList.add('artifact-open'); panel.focus();
  };
  window.CaduV2Artifacts = {open};
})();
