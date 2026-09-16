(() => {
  'use strict';
  const dialog = document.querySelector('[data-brand-review-dialog]');
  const audit = document.querySelector('.workspace-brand-audit-form');
  const summary = document.querySelector('[data-brand-review-summary]');
  const processDialog = document.querySelector('[data-brand-process-dialog]');
  if (!dialog) return;

  const body = dialog.querySelector('[data-brand-review-body]');
  const footer = dialog.querySelector('[data-brand-review-footer]');
  const statusUrl = summary?.dataset.statusUrl;
  let timer;
  const escape = (value) => String(value || '').replace(/[<>&]/g, '');
  const open = () => { if (!dialog.open) dialog.showModal(); };
  const close = () => { window.clearTimeout(timer); dialog.close(); };
  const renderProgress = (data) => {
    const current = Math.max(0, Number(data.index || 0));
    const labels = ['Organizando evidências', 'Revisando evidências', 'Revisando estratégia', 'Traduzindo direção criativa'];
    body.innerHTML = `<section class="workspace-brand-review-progress"><i aria-hidden="true"></i><div><strong>${escape(data.message || 'Preparando análise')}</strong><p>${current ? `Etapa ${Math.min(current, 4)} de 4.` : 'A auditoria está entrando na fila.'}</p></div><ol>${labels.map((label, index) => `<li class="${index < current ? 'is-active' : ''}">${label}</li>`).join('')}</ol></section>`;
    footer.hidden = true;
  };
  const poll = async () => {
    if (!statusUrl) return;
    try {
      const response = await fetch(statusUrl, {headers: {'Accept': 'application/json'}, cache: 'no-store'});
      const data = await response.json();
      if (!response.ok) throw new Error(data.description || 'Não foi possível acompanhar a análise.');
      if (data.status === 'queued' || data.status === 'running') {
        renderProgress(data);
        timer = window.setTimeout(poll, 1500);
        return;
      }
      if (data.status === 'pending_approval') {
        body.innerHTML = '<section class="workspace-brand-review-complete"><i class="fa-solid fa-circle-check" aria-hidden="true"></i><div><strong>Proposta pronta para decisão</strong><p>Os três pareceres foram salvos. Revise a síntese antes de aplicá-la à marca e aos projetos.</p></div></section>';
        footer.hidden = false;
        footer.innerHTML = '<button type="button" data-brand-review-reload>Revisar pareceres</button>';
        footer.querySelector('[data-brand-review-reload]').addEventListener('click', () => window.location.reload());
        return;
      }
      if (data.status === 'failed') {
        body.innerHTML = `<section class="workspace-brand-review-complete is-error"><i class="fa-solid fa-triangle-exclamation" aria-hidden="true"></i><div><strong>A análise não foi concluída</strong><p>${escape(data.error || data.message || 'Tente novamente.')}</p></div></section>`;
        footer.hidden = false;
      }
    } catch (error) {
      body.innerHTML = `<section class="workspace-brand-review-complete is-error"><i class="fa-solid fa-triangle-exclamation" aria-hidden="true"></i><div><strong>Não foi possível acompanhar a análise</strong><p>${escape(error.message || 'Atualize a página para verificar o status.')}</p></div></section>`;
      footer.hidden = false;
    }
  };
  document.querySelectorAll('[data-brand-review-open]').forEach((button) => button.addEventListener('click', open));
  document.querySelectorAll('[data-brand-review-close]').forEach((button) => button.addEventListener('click', close));
  dialog.addEventListener('click', (event) => { if (event.target === dialog) close(); });
  if (processDialog) {
    const openProcess = () => { if (!processDialog.open) processDialog.showModal(); };
    const closeProcess = () => processDialog.close();
    document.querySelectorAll('[data-brand-process-open]').forEach((button) => button.addEventListener('click', openProcess));
    document.querySelectorAll('[data-brand-process-close]').forEach((button) => button.addEventListener('click', closeProcess));
    processDialog.addEventListener('click', (event) => { if (event.target === processDialog) closeProcess(); });
  }
  const currentTitle = summary?.querySelector('h2')?.textContent?.trim();
  if (summary && (['queued', 'running'].includes(summary.dataset.status || '') || currentTitle === 'Análise em andamento')) { open(); poll(); }
  if (!audit) return;
  audit.addEventListener('submit', async (event) => {
    event.preventDefault();
    const submit = audit.querySelector('button[type="submit"], button:not([type])');
    if (submit?.disabled) return;
    renderProgress({status: 'queued', message: 'Iniciando auditoria…'});
    open();
    submit.disabled = true;
    try {
      const response = await fetch(audit.action, {method: 'POST', body: new FormData(audit), headers: {'Accept': 'application/json'}});
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.description || data.error || 'Não foi possível iniciar a análise.');
      timer = window.setTimeout(poll, 300);
    } catch (error) {
      body.innerHTML = `<section class="workspace-brand-review-complete is-error"><i class="fa-solid fa-triangle-exclamation" aria-hidden="true"></i><div><strong>A análise não foi iniciada</strong><p>${escape(error.message || 'Tente novamente.')}</p></div></section>`;
      footer.hidden = false;
    } finally { submit.disabled = false; }
  });
})();
