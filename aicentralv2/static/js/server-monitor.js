(() => {
  const app = document.querySelector('[data-server-monitor]');
  if (!app) return;
  const $ = (selector) => app.querySelector(selector);
  const text = (selector, value) => { const node = $(selector); if (node) node.textContent = value; };
  const escape = (value) => String(value || '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));

  const progressClass = (value) => {
    if (value >= 85) return 'cx-progress cx-progress-danger';
    if (value >= 80) return 'cx-progress cx-progress-warning';
    return 'cx-progress cx-progress-success';
  };

  const resource = (key, data) => {
    const value = Number(data.value);
    text(`[data-resource-${key}]`, Number.isFinite(value) ? `${value}%` : 'Indisponível');
    text(`[data-resource-${key}-detail]`, data.detail);
    const bar = $(`progress[data-resource-${key}-bar]`);
    if (bar) {
      bar.value = Math.min(Number.isFinite(value) ? value : 0, 100);
      bar.className = progressClass(Number.isFinite(value) ? value : 0);
    }
  };

  const domainBadge = (status) => {
    if (status === 'healthy') return { cls: 'cx-badge-success', label: 'Operando' };
    if (status === 'warning') return { cls: 'cx-badge-warning', label: 'Verificar' };
    return { cls: 'cx-badge-danger', label: 'Indisponível' };
  };

  const alertClass = (level) => {
    if (level === 'critical' || level === 'error') return 'cx-alert cx-alert-danger';
    return 'cx-alert cx-alert-warning';
  };

  const alertIcon = (level) => (
    level === 'critical' || level === 'error'
      ? 'fa-solid fa-circle-exclamation'
      : 'fa-solid fa-triangle-exclamation'
  );

  const render = (data) => {
    text('[data-server-status]', data.server.status === 'healthy' ? 'Todos os sistemas operacionais' : 'Atenção necessária');
    text('[data-server-name]', data.server.name);
    text('[data-server-uptime]', data.server.uptime);
    text('[data-server-platform]', data.server.platform);
    resource('cpu', data.resources.cpu);
    resource('memory', data.resources.memory);
    resource('disk', data.resources.disk);

    const domains = data.domains || [];
    text('[data-domain-count]', `${domains.length} ${domains.length === 1 ? 'domínio' : 'domínios'}`);
    $('[data-domain-list]').innerHTML = domains.length
      ? domains.map((item) => {
          const badge = domainBadge(item.status);
          return `<article class="server-monitor-domain-row">
            <span class="server-monitor-domain-dot is-${escape(item.status)}" aria-hidden="true"></span>
            <div class="server-monitor-domain-copy">
              <strong>${escape(item.domain)}</strong>
              <small>${escape(item.detail)}</small>
            </div>
            <div class="server-monitor-domain-meta">
              <span>${item.latency ? `${item.latency} ms` : '—'}</span>
              <span class="cx-badge ${badge.cls}">${badge.label}</span>
            </div>
          </article>`;
        }).join('')
      : '<p class="cx-help">Nenhum domínio configurado.</p>';

    const alerts = data.alerts || [];
    $('[data-alert-list]').innerHTML = alerts.length
      ? alerts.map((item) => `<div class="${alertClass(item.level)}" role="alert">
          <i class="${alertIcon(item.level)}" aria-hidden="true"></i>
          <div><strong>${escape(item.title)}</strong><p>${escape(item.message)}</p></div>
        </div>`).join('')
      : `<div class="cx-alert cx-alert-success" role="status">
          <i class="fa-solid fa-circle-check" aria-hidden="true"></i>
          <div><strong>Nenhum alerta aberto</strong><p>Capacidade e conectividade operando dentro do esperado.</p></div>
        </div>`;

    text('[data-monitor-updated]', `Atualizado às ${new Intl.DateTimeFormat('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' }).format(new Date())}`);
  };

  const refresh = async () => {
    const button = $('[data-monitor-refresh]');
    button.disabled = true;
    button.classList.add('is-loading');
    try {
      const response = await fetch(app.dataset.apiUrl, { headers: { Accept: 'application/json' } });
      const payload = await response.json();
      if (!response.ok || !payload.success) throw new Error(payload.error || 'Não foi possível atualizar os dados.');
      render(payload.data);
    } catch (error) {
      text('[data-monitor-updated]', error.message);
    } finally {
      button.disabled = false;
      button.classList.remove('is-loading');
    }
  };

  $('[data-monitor-refresh]').addEventListener('click', refresh);
  refresh();
})();
