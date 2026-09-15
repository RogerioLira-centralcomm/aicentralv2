(() => {
  const app = document.querySelector('[data-server-monitor]');
  if (!app) return;
  const $ = (selector) => app.querySelector(selector);
  const text = (selector, value) => { const node = $(selector); if (node) node.textContent = value; };
  const escape = (value) => String(value || '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
  const resource = (key, data) => {
    const value = Number(data.value);
    text(`[data-resource-${key}]`, Number.isFinite(value) ? `${value}%` : 'Indisponível');
    text(`[data-resource-${key}-detail]`, data.detail);
    const bar = $(`[data-resource-${key}-bar]`);
    if (bar) { bar.style.width = `${Math.min(value || 0, 100)}%`; bar.className = value >= 85 ? 'is-critical' : value >= 80 ? 'is-warning' : ''; }
  };
  const render = (data) => {
    text('[data-server-status]', data.server.status === 'healthy' ? 'Todos os sistemas operacionais' : 'Atenção necessária');
    text('[data-server-name]', data.server.name); text('[data-server-uptime]', data.server.uptime); text('[data-server-platform]', data.server.platform);
    resource('cpu', data.resources.cpu); resource('memory', data.resources.memory); resource('disk', data.resources.disk);
    const domains = data.domains || []; text('[data-domain-count]', `${domains.length} ${domains.length === 1 ? 'domínio' : 'domínios'}`);
    $('[data-domain-list]').innerHTML = domains.map(item => `<article class="domain-row"><span class="domain-state is-${escape(item.status)}"></span><div><strong>${escape(item.domain)}</strong><small>${escape(item.detail)}</small></div><div class="domain-meta"><span>${item.latency ? `${item.latency} ms` : '—'}</span><em class="is-${escape(item.status)}">${item.status === 'healthy' ? 'Operando' : item.status === 'warning' ? 'Verificar' : 'Indisponível'}</em></div></article>`).join('') || '<p class="empty-state">Nenhum domínio configurado.</p>';
    const alerts = data.alerts || [];
    $('[data-alert-list]').innerHTML = alerts.length ? alerts.map(item => `<article class="alert-row is-${escape(item.level)}"><i class="fa-solid ${item.level === 'critical' ? 'fa-circle-exclamation' : 'fa-triangle-exclamation'}" aria-hidden="true"></i><div><strong>${escape(item.title)}</strong><p>${escape(item.message)}</p></div></article>`).join('') : '<div class="all-clear"><i class="fa-solid fa-circle-check" aria-hidden="true"></i><div><strong>Nenhum alerta aberto</strong><p>Capacidade e conectividade operando dentro do esperado.</p></div></div>';
    text('[data-monitor-updated]', `Atualizado às ${new Intl.DateTimeFormat('pt-BR', {hour:'2-digit', minute:'2-digit', second:'2-digit'}).format(new Date())}`);
  };
  const refresh = async () => { const button = $('[data-monitor-refresh]'); button.disabled = true; button.classList.add('is-loading'); try { const response = await fetch(app.dataset.apiUrl, {headers:{Accept:'application/json'}}); const payload = await response.json(); if (!response.ok || !payload.success) throw new Error(payload.error || 'Não foi possível atualizar os dados.'); render(payload.data); } catch (error) { text('[data-monitor-updated]', error.message); } finally { button.disabled = false; button.classList.remove('is-loading'); } };
  $('[data-monitor-refresh]').addEventListener('click', refresh); refresh();
})();
