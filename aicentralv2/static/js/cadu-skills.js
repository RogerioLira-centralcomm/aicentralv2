document.addEventListener('DOMContentLoaded', () => {
  const normalize = value => (value || '').toLocaleLowerCase('pt-BR').normalize('NFD').replace(/[\u0300-\u036f]/g, '');
  const show = (node, value) => { node.textContent = value || ''; node.hidden = !value; };
  const copyText = async value => {
    if (navigator.clipboard?.writeText) return navigator.clipboard.writeText(value);
    const field = document.createElement('textarea');
    field.value = value; field.setAttribute('readonly', ''); field.style.position = 'fixed'; field.style.opacity = '0';
    document.body.appendChild(field); field.select();
    const copied = document.execCommand('copy'); field.remove();
    if (!copied) throw new Error('copy unavailable');
  };
  const search = document.querySelector('[data-search]');
  if (search) {
    const input = search.querySelector('input');
    const filter = () => {
      const query = normalize(input.value);
      const active = document.querySelector('[data-categories] .is-active')?.dataset.category || 'all';
      let visible = 0;
      document.querySelectorAll('[data-item]').forEach(item => {
        item.hidden = !(normalize(item.dataset.text).includes(query) && (active === 'all' || item.dataset.category === active));
        if (!item.hidden) visible += 1;
      });
      const empty = document.querySelector('[data-empty]'); if (empty) empty.hidden = visible > 0;
    };
    search.addEventListener('submit', event => { event.preventDefault(); filter(); });
    input.addEventListener('input', filter);
    document.querySelector('[data-categories]')?.addEventListener('click', event => {
      const button = event.target.closest('[data-category]'); if (!button) return;
      event.currentTarget.querySelectorAll('button').forEach(item => item.classList.toggle('is-active', item === button)); filter();
    });
  }
  document.querySelectorAll('[data-prompt]').forEach(button => button.addEventListener('click', () => {
    const composer = document.querySelector('[data-public-composer], [data-composer]');
    if (composer) { composer.value = button.textContent.trim(); composer.focus(); }
  }));
  const publicButton = document.querySelector('[data-public-preview]');
  const applyPreviewState = state => {
    if (!state) return;
    const remaining = document.querySelector('[data-remaining]'); if (remaining) remaining.textContent = state.remaining;
    const invite = document.querySelector('[data-ecosystem-invite]');
    if (invite) {
      invite.hidden = !state.show_ecosystem_invite;
      invite.dataset.stage = state.ecosystem_stage || '';
      const count = invite.querySelector('[data-preview-count]'); if (count) count.textContent = state.count;
      if (!invite.hidden) invite.scrollIntoView({behavior:'smooth', block:'nearest'});
    }
    publicButton.disabled = !state.allowed;
    publicButton.textContent = state.allowed ? publicButton.dataset.runLabel : 'Prévias concluídas';
  };
  publicButton?.addEventListener('click', async () => {
    const composer = document.querySelector('[data-public-composer]'), answer = document.querySelector('[data-public-answer]');
    publicButton.disabled = true; show(answer, 'Executando a skill…');
    try {
      const response = await fetch(publicButton.dataset.url, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({prompt:composer.value})});
      const body = await response.json(); applyPreviewState(body.state);
      if (!response.ok) throw new Error(body.error || 'Não foi possível executar a skill.');
      show(answer, body.answer);
    } catch (error) { show(answer, error.message); } finally {
      if (publicButton.textContent !== 'Prévias concluídas') publicButton.disabled = false;
    }
  });
  document.querySelector('[data-copy-skill]')?.addEventListener('click', async event => {
    const button = event.currentTarget, content = document.querySelector('[data-skill-instructions]')?.textContent || '';
    try { await copyText(content); button.textContent = 'Instruções copiadas'; fetch(button.dataset.url, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({event:'copy'})}); }
    catch (_) { button.textContent = 'Não foi possível copiar'; }
  });
  document.querySelectorAll('[data-copy-value]').forEach(button => button.addEventListener('click', async () => {
    const original = button.dataset.copyLabel || button.textContent;
    try {
      await copyText(button.dataset.copyValue || ''); button.textContent = 'Copiado';
    } catch (_) { button.textContent = 'Não foi possível copiar'; }
    window.setTimeout(() => { button.textContent = original; }, 1800);
  }));
  const runButton = document.querySelector('[data-run]');
  runButton?.addEventListener('click', async () => {
    const answer = document.querySelector('[data-message]'); runButton.disabled = true; show(answer, 'Executando e verificando créditos…');
    try {
      const response = await fetch(runButton.dataset.url, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({prompt:document.querySelector('[data-composer]').value})});
      const body = await response.json(); if (!response.ok) throw new Error(body.error || 'Não foi possível executar.');
      show(answer, `${body.answer}\n\n${body.charged_credits} crédito(s) utilizado(s). Saldo: ${body.remaining_credits}.`);
    } catch (error) { show(answer, error.message); } finally { runButton.disabled = false; }
  });
  const sharedForm = document.querySelector('[data-shared-run]');
  sharedForm?.addEventListener('submit', async event => {
    event.preventDefault(); const button = sharedForm.querySelector('button[type="submit"]'), status = sharedForm.querySelector('[data-run-status]'), answer = sharedForm.querySelector('[data-run-answer]');
    button.disabled = true; status.textContent = 'Executando e verificando créditos…'; answer.hidden = true;
    try {
      const response = await fetch(sharedForm.dataset.url, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({prompt:sharedForm.querySelector('textarea').value})});
      const body = await response.json(); if (!response.ok) throw new Error(body.error || 'Não foi possível executar.');
      status.textContent = `${body.charged_credits} crédito(s) utilizado(s). Saldo: ${body.remaining_credits}.`; show(answer, body.answer);
    } catch (error) { status.textContent = error.message; } finally { button.disabled = false; }
  });
});
