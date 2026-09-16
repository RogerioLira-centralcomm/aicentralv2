(() => {
  'use strict';
  const root = document.querySelector('[data-link-tester]');
  if (!root) return;
  const form = root.querySelector('[data-link-form]'), result = root.querySelector('[data-link-result]');
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content;
  const write = (selector, value) => { root.querySelector(selector).textContent = value; };
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const button = form.querySelector('button'), url = new FormData(form).get('url');
    button.disabled = true; button.textContent = 'Testando…'; result.hidden = false; write('[data-link-status]', 'Verificando destino'); write('[data-link-destination]', 'Aguarde…');
    try {
      const response = await fetch('/familia/api/planner/link-tester', {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf}, body: JSON.stringify({url})});
      const data = await response.json(); if (!response.ok) throw new Error(data.error || 'Não foi possível testar o link.');
      const item = data.result;
      write('[data-link-status]', item.reachable ? `Destino disponível · HTTP ${item.status}` : `Destino com problema · HTTP ${item.status}`);
      write('[data-link-destination]', new URL(item.final_url).hostname); write('[data-link-time]', `${item.elapsed_ms} ms`);
      write('[data-link-original]', item.original_url); write('[data-link-final]', item.final_url); write('[data-link-redirects]', `${Math.max(0, item.redirects.length - 1)} redirecionamento(s)`);
      const alerts = root.querySelector('[data-link-alerts]'); alerts.replaceChildren();
      (item.alerts.length ? item.alerts : ['Nenhum alerta básico encontrado.']).forEach(message => alerts.append(Object.assign(document.createElement('p'), {textContent: message})));
    } catch (error) { write('[data-link-status]', 'Teste indisponível'); write('[data-link-destination]', error.message); root.querySelector('[data-link-alerts]').replaceChildren(); }
    finally { button.disabled = false; button.textContent = 'Testar link'; }
  });
})();
