(() => {
  'use strict';
  const editor = document.getElementById('copy-editor');
  if (!editor) return;
  const select = document.getElementById('copy-format');
  const fields = document.getElementById('copy-fields');
  const status = document.getElementById('copy-status');
  const preview = document.getElementById('copy-preview-content');
  const validate = document.getElementById('copy-validate');
  const download = document.getElementById('copy-export');
  const retry = document.getElementById('copy-retry');
  const drafts = new Map();
  let formats = [], active = null, revision = 0;
  const values = () => Object.fromEntries([...fields.querySelectorAll('textarea')].map(node => [node.name, node.value]));
  const textNode = (tag, text) => { const node = document.createElement(tag); node.textContent = text; return node; };
  function renderPreview() {
    revision += 1;
    if (!active) return;
    const draft = values(); drafts.set(String(active.id), draft);
    preview.replaceChildren();
    for (const field of active.fields) {
      const text = draft[field.name] || '';
      const count = Array.from(text).length;
      const input = document.getElementById('copy-' + field.name);
      const counter = document.getElementById('copy-count-' + field.name);
      input.setAttribute('aria-invalid', String(count > field.limit));
      counter.textContent = `${count} / ${field.limit} caracteres. Recomendado: ${field.recommended}.`;
      counter.classList.toggle('copy-over-limit', count > field.limit);
      const item = document.createElement('article');
      item.append(textNode('strong', field.label), textNode('p', text || 'Texto ainda não preenchido.'));
      preview.append(item);
    }
    status.textContent = 'Rascunho local. Valide os textos antes de usar.';
  }
  select.addEventListener('change', () => {
    if (active) drafts.set(String(active.id), values());
    active = formats.find(item => String(item.id) === select.value) || null;
    fields.replaceChildren(); preview.replaceChildren();
    validate.disabled = download.disabled = !active;
    document.getElementById('copy-format-description').textContent = active ? [active.description, active.dimensions].filter(Boolean).join(' — ') : '';
    document.getElementById('copy-specs').replaceChildren(...(active?.specs || []).map(spec => textNode('li', spec)));
    if (!active) { revision += 1; return; }
    for (const field of active.fields) {
      const label = textNode('label', field.label);
      const input = document.createElement('textarea'); input.name = field.name; input.id = 'copy-' + field.name;
      input.maxLength = 20000; input.value = drafts.get(String(active.id))?.[field.name] || '';
      const counter = document.createElement('small'); counter.id = 'copy-count-' + field.name;
      input.setAttribute('aria-describedby', counter.id); label.htmlFor = input.id;
      input.addEventListener('input', renderPreview);
      label.append(input, counter); fields.append(label);
    }
    renderPreview();
  });
  async function load() {
    retry.hidden = true; status.textContent = 'Carregando formatos…';
    try {
      const response = await fetch('/familia/api/studio/copy-ads/formats', {credentials: 'same-origin'});
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Não foi possível carregar os formatos.');
      formats = data.formats;
      select.replaceChildren(new Option('Selecione um formato', ''), ...formats.map(item => new Option(`${item.platform} — ${item.name}`, String(item.id))));
      select.disabled = !formats.length;
      status.textContent = formats.length ? 'Selecione o formato do anúncio.' : 'Não há formatos ativos no catálogo.';
    } catch (error) { status.textContent = error.message; retry.hidden = false; }
  }
  retry.addEventListener('click', load);
  editor.addEventListener('submit', async event => {
    event.preventDefault(); if (!active) return;
    const expectedRevision = revision;
    validate.disabled = true; status.textContent = 'Validando…';
    try {
      const response = await fetch('/familia/api/studio/copy-ads/validate', {
        method: 'POST', credentials: 'same-origin',
        headers: {'Content-Type': 'application/json', 'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]').content},
        body: JSON.stringify({format_id: active.id, values: values()})
      });
      const data = await response.json();
      if (expectedRevision !== revision) return;
      if (!response.ok) throw new Error(data.error || 'Não foi possível validar.');
      status.textContent = data.valid ? 'Textos preenchidos e dentro dos limites do catálogo.' : 'Revise os campos vazios ou acima do limite.';
      for (const field of data.fields) document.getElementById('copy-' + field.name)?.setAttribute('aria-invalid', String(!field.valid));
    } catch (error) { if (expectedRevision === revision) status.textContent = error.message; }
    finally { validate.disabled = !active; }
  });
  download.addEventListener('click', () => {
    if (!active) return;
    const draft = values();
    const text = [active.platform + ' — ' + active.name, 'Rascunho — confira os limites antes de publicar.',
      ...active.fields.map(field => field.label + '\n' + (draft[field.name] || ''))].join('\n\n');
    const url = URL.createObjectURL(new Blob([text], {type: 'text/plain;charset=utf-8'}));
    const link = document.createElement('a'); link.href = url; link.download = 'cadu-copy-ads.txt'; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
  window.addEventListener('beforeunload', event => {
    if ([...drafts.values()].some(draft => Object.values(draft).some(Boolean))) { event.preventDefault(); event.returnValue = ''; }
  });
  load();
})();
