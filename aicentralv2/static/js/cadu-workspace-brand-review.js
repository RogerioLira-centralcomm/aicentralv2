(() => {
  'use strict';
  const dialog = document.querySelector('[data-brand-review-dialog]');
  const audit = document.querySelector('.workspace-brand-audit-form');
  const summary = document.querySelector('[data-brand-review-summary]');
  const processDialog = document.querySelector('[data-brand-process-dialog]');
  const balanceTarget = document.querySelector('.workspace-brand-audit-card');
  if (balanceTarget) {
    if (!document.getElementById('workspace-token-balance-style')) {
      const style = document.createElement('style'); style.id = 'workspace-token-balance-style';
      style.textContent = '.workspace-token-balance{display:grid;grid-template-columns:1fr auto;gap:5px 14px;margin:14px 0;padding:11px 12px;border:1px solid #c9e4da;border-radius:10px;background:linear-gradient(100deg,#edf9f4,#fff);color:#244b41}.workspace-token-balance>span{grid-column:1/-1;color:#287160;font-size:10px;font-weight:750}.workspace-token-balance strong{font-size:18px;letter-spacing:-.04em}.workspace-token-balance strong small{font-size:10px;font-weight:650;letter-spacing:0}.workspace-token-balance p{grid-column:1/-1;margin:0;color:#5b7069;font-size:10px;line-height:1.4}.workspace-token-balance a{grid-column:2;grid-row:2;align-self:end;color:#176b5e;font-size:10px;font-weight:700;text-decoration:none}.workspace-token-balance a:hover{text-decoration:underline}';
      document.head.append(style);
    }
    fetch('/workspace/api/creditos/resumo', {headers: {'Accept': 'application/json'}, cache: 'no-store'})
      .then(response => response.ok ? response.json() : null)
      .then(credit => {
        if (!credit?.configured) return;
        const card = document.createElement('aside');
        card.className = 'workspace-token-balance';
        const available = Number(credit.available || 0).toLocaleString('pt-BR');
        card.innerHTML = `<span>Saldo compartilhado</span><strong>${available} <small>tokens disponíveis</small></strong><p>A auditoria usa tokens pelo processamento efetivo das evidências e referências enviadas.</p><a href="/workspace/app/creditos">Ver consumo e histórico</a>`;
        const steps = balanceTarget.querySelector('.workspace-brand-audit-steps');
        steps?.insertAdjacentElement('afterend', card);
      }).catch(() => {});
  }
  if (!dialog) return;

  const websiteInput = audit?.querySelector('input[name="website_url"]');
  if (websiteInput) {
    websiteInput.type = 'text'; websiteInput.inputMode = 'url';
    websiteInput.addEventListener('blur', () => {
      const value = websiteInput.value.trim();
      if (value && !/^https?:\/\//i.test(value)) websiteInput.value = `https://${value.replace(/^\/+/, '')}`;
    });
  }

  const body = dialog.querySelector('[data-brand-review-body]');
  const footer = dialog.querySelector('[data-brand-review-footer]');
  let inlineProgress = summary?.querySelector('[data-brand-audit-progress]');
  const statusUrl = summary?.dataset.statusUrl;
  let timer; let startedAt = 0;
  const escape = (value) => String(value || '').replace(/[<>&]/g, '');
  const open = () => { if (!dialog.open) dialog.showModal(); };
  const close = () => dialog.close();
  const elapsed = () => startedAt ? Math.max(0, Math.floor((Date.now() - startedAt) / 1000)) : 0;
  const formatElapsed = () => {
    const seconds = elapsed();
    return seconds >= 60 ? `${Math.floor(seconds / 60)} min ${seconds % 60}s` : `${seconds}s`;
  };
  const setSummaryLoading = (message) => {
    summary?.setAttribute('aria-busy', 'true');
    const title = summary?.querySelector('h2'); const copy = summary?.querySelector('p');
    if (title) title.textContent = 'Análise em andamento';
    if (copy) copy.textContent = message || 'Processando a marca. Você pode manter esta página aberta.';
    summary?.querySelectorAll('.workspace-brand-review-actions button').forEach((button) => { button.disabled = true; });
  };
  const setInlineProgress = (value) => {
    if (!inlineProgress && summary) {
      inlineProgress = document.createElement('small');
      inlineProgress.className = 'workspace-brand-audit-progress';
      inlineProgress.dataset.brandAuditProgress = '';
      summary.querySelector('div')?.append(inlineProgress);
    }
    if (inlineProgress) inlineProgress.textContent = value;
  };
  const renderProgress = (data) => {
    if (!startedAt) startedAt = data.created_at ? Date.parse(data.created_at) : Date.now();
    const current = Math.max(0, Number(data.index || 0));
    const labels = ['Organizando evidências', 'Revisando evidências', 'Revisando estratégia', 'Traduzindo direção criativa'];
    const message = data.message || 'Preparando análise';
    setSummaryLoading(message);
    setInlineProgress(`${current ? `Etapa ${Math.min(current, 4)} de 4` : 'Na fila'} · ${formatElapsed()} decorridos`);
    body.innerHTML = `<section class="workspace-brand-review-progress" aria-live="polite"><i aria-hidden="true"></i><div><strong>${escape(message)}</strong><p>${current ? `Etapa ${Math.min(current, 4)} de 4 · ${formatElapsed()} decorridos.` : `Entrando na fila · ${formatElapsed()} decorridos.`}</p><small>Você pode sair desta janela: o processamento continua e o resultado ficará salvo.</small></div><ol>${labels.map((label, index) => `<li class="${index < current ? 'is-active' : ''}">${label}</li>`).join('')}</ol></section>`;
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
        summary?.removeAttribute('aria-busy');
        body.innerHTML = '<section class="workspace-brand-review-complete"><i class="fa-solid fa-circle-check" aria-hidden="true"></i><div><strong>Proposta pronta para decisão</strong><p>Os pareceres foram salvos. Revise a síntese antes de aplicá-la à marca e aos projetos.</p></div></section>';
        footer.hidden = false;
        footer.innerHTML = '<button type="button" data-brand-review-reload>Revisar pareceres</button>';
        footer.querySelector('[data-brand-review-reload]').addEventListener('click', () => window.location.reload());
        return;
      }
      if (data.status === 'failed') {
        summary?.removeAttribute('aria-busy');
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
  if (!startedAt && summary?.dataset.createdAt) startedAt = Date.parse(summary.dataset.createdAt) || 0;
  if (summary && (['queued', 'running'].includes(summary.dataset.status || '') || currentTitle === 'Análise em andamento')) { open(); poll(); }
  if (!audit) return;
  audit.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (websiteInput) websiteInput.dispatchEvent(new Event('blur'));
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
