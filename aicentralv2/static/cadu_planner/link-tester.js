(() => {
  'use strict';

  const root = document.querySelector('[data-link-tester]');
  if (!root) return;

  const form = root.querySelector('[data-link-form]');
  const result = root.querySelector('[data-link-result]');
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content;
  const share = root.querySelector('[data-link-share]');
  const shareStatus = root.querySelector('[data-link-share-status]');
  const preview = root.querySelector('[data-link-preview]');
  const previewImage = root.querySelector('[data-link-preview-image]');
  const copy = {
    destination: {
      button: 'Analisar destino', help: 'Use a URL que será veiculada na campanha.',
      kicker: 'Auditoria de destino', title: 'O clique chega onde deveria.',
      description: 'Verifique redirects, UTMs, HTTPS e disponibilidade antes de publicar a mídia.'
    },
    media: {
      button: 'Auditar mídia', help: 'Analise a landing page, as tags e os sinais de conversão.',
      kicker: 'Mídia e conversão', title: 'A página mede o que ela promete converter?',
      description: 'Mapeie tags, eventos, CTAs, consentimento e prontidão por plataforma.'
    },
    agentic: {
      button: 'Auditar site agêntico', help: 'Esta análise considera o domínio, não apenas a campanha.',
      kicker: 'Site agêntico', title: 'O domínio está legível para agentes de IA?',
      description: 'Avalie robots, llms.txt, sitemap e dados estruturados sem misturar métricas de campanha.'
    }
  };

  const write = (selector, value) => { root.querySelector(selector).textContent = value || '—'; };
  const escape = value => String(value ?? '').replace(/[&<>"']/g, character => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'
  }[character]));
  const selectedMode = () => new FormData(form).get('mode');

  function resetShare() {
    share.hidden = true;
    share.textContent = 'Copiar link público';
    shareStatus.textContent = '';
    share.onclick = null;
  }

  function refreshMode() {
    const mode = selectedMode();
    const content = copy[mode];
    root.dataset.activeMode = mode;
    root.querySelectorAll('[data-link-mode]').forEach(label => {
      label.classList.toggle('is-selected', label.querySelector('input').checked);
    });
    form.querySelector('button[type="submit"]').textContent = content.button;
    write('[data-link-help]', content.help);
    write('[data-link-hero-kicker]', content.kicker);
    write('[data-link-hero-title]', content.title);
    write('[data-link-hero-description]', content.description);
  }

  async function copyPublicLink(url) {
    try {
      if (navigator.clipboard?.writeText && window.isSecureContext) {
        await navigator.clipboard.writeText(url);
      } else {
        const input = Object.assign(document.createElement('textarea'), {value: url});
        input.setAttribute('readonly', '');
        input.style.cssText = 'position:fixed;opacity:0';
        document.body.append(input);
        input.select();
        const copied = document.execCommand('copy');
        input.remove();
        if (!copied) throw new Error('copy failed');
      }
      share.textContent = 'Link público copiado';
      shareStatus.textContent = 'O link foi copiado para a área de transferência.';
    } catch (_) {
      shareStatus.textContent = `Copie este endereço: ${url}`;
    }
  }

  function evidence(item) {
    const evidence = item.evidence || {};
    if (item.kind === 'destination') return [
      ['HTTP', evidence.http_status], ['Resposta', `${evidence.elapsed_ms} ms`],
      ['Redirecionamentos', Math.max(0, (evidence.redirects || []).length - 1)],
      ['UTMs', Object.keys(evidence.utm || {}).length || 'nenhuma'],
      ['SSL', evidence.ssl?.valid ? 'válido' : 'atenção'], ['Título', evidence.title || 'não encontrado']
    ];
    if (item.kind === 'media') return [
      ['Tags detectadas', (evidence.tags || []).filter(tag => tag.detected).map(tag => tag.name).join(', ') || 'nenhuma'],
      ['Eventos', (evidence.events || []).join(', ') || 'nenhum'], ['Formulários', evidence.conversion?.forms || 'nenhum'],
      ['WhatsApp', evidence.conversion?.whatsapp ? 'detectado' : 'não detectado'],
      ['Consentimento', evidence.compliance?.consent_detected ? 'detectado' : 'não detectado'],
      ['Google', `${evidence.platforms?.find(platform => platform.name === 'Google')?.score ?? 0}%`]
    ];
    return [
      ['Robots.txt', evidence.resources?.['robots.txt']?.available ? 'disponível' : 'ausente'],
      ['llms.txt', evidence.resources?.['llms.txt']?.available ? 'disponível' : 'ausente'],
      ['Sitemap', evidence.resources?.['sitemap.xml']?.available ? 'disponível' : 'ausente'],
      ['Schema', (evidence.schema_types || []).join(', ') || 'não detectado'],
      ['Links no llms.txt', evidence.llms_quality?.links || 'nenhum'],
      ['Agentes bloqueados', (evidence.bot_access || []).filter(bot => bot.blocked).map(bot => bot.name).join(', ') || 'nenhum']
    ];
  }

  function displayResult(item) {
    result.hidden = false;
    write('[data-link-status]', item.status_label);
    write('[data-link-summary]', item.summary);
    write('[data-link-score]', `${item.score}/100`);
    write('[data-link-final]', item.final_url);
    const screenshot = item.evidence?.screenshot;
    preview.hidden = !screenshot;
    if (screenshot) previewImage.src = screenshot;
    root.querySelector('[data-link-evidence]').innerHTML = evidence(item)
      .map(([label, value]) => `<article><small>${escape(label)}</small><b>${escape(value)}</b></article>`).join('');
    root.querySelector('[data-link-alerts]').innerHTML = (item.alerts?.length ? item.alerts : ['Nenhuma pendência crítica encontrada.'])
      .map(message => `<p>${escape(message)}</p>`).join('');
    if (item.public_token) {
      const publicUrl = `${location.origin}/familia/public/link-tester/${item.public_token}`;
      share.hidden = false;
      share.onclick = () => copyPublicLink(publicUrl);
    }
  }

  async function loadHistory() {
    const target = root.querySelector('[data-link-history]');
    try {
      const response = await fetch('/familia/api/planner/link-tester/history', {credentials: 'same-origin'});
      const data = await response.json();
      if (!response.ok) throw new Error();
      if (!data.runs?.length) { target.innerHTML = '<p class="planner-link-history-empty">Ainda não há análises salvas para este cliente.</p>'; return; }
      target.innerHTML = data.runs.map(run => `<article class="planner-link-history-card" data-run-id="${escape(run.id)}"><span class="planner-link-history-icon" aria-hidden="true">${run.mode === 'agentic' ? 'IA' : run.mode === 'media' ? 'M' : '↗'}</span><div><small>Link de anúncio · ${escape(run.mode)}</small><b>${escape(run.final_url)}</b><p>${escape(run.status_label)} · ${escape(run.score)}/100</p></div><button type="button">Abrir detalhe</button></article>`).join('');
      target.querySelectorAll('[data-run-id]').forEach(card => card.querySelector('button').addEventListener('click', async () => {
        const response = await fetch(`/familia/api/planner/link-tester/${card.dataset.runId}`, {credentials: 'same-origin'});
        const data = await response.json();
        if (!response.ok) return;
        resetShare(); displayResult({...data.run.result, public_token: data.run.public_token, final_url: data.run.final_url});
        result.scrollIntoView({behavior: 'smooth', block: 'start'});
      }));
    } catch (_) { target.innerHTML = '<p class="planner-link-history-empty">Não foi possível carregar o histórico agora.</p>'; }
  }

  form.addEventListener('change', () => { resetShare(); refreshMode(); });
  refreshMode();
  loadHistory();

  form.addEventListener('submit', async event => {
    event.preventDefault();
    const button = form.querySelector('button[type="submit"]');
    const mode = selectedMode();
    button.disabled = true;
    button.textContent = 'Analisando…';
    result.hidden = false;
    resetShare();
    write('[data-link-status]', 'Coletando evidências');
    write('[data-link-summary]', 'Aguarde enquanto verificamos a URL.');
    write('[data-link-score]', '');

    try {
      const response = await fetch('/familia/api/planner/link-tester', {
        method: 'POST', credentials: 'same-origin',
        headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf},
        body: JSON.stringify({url: new FormData(form).get('url'), mode})
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Não foi possível analisar esta URL.');
      const item = data.result;
      displayResult(item);
      if (!item.public_token) {
        shareStatus.textContent = 'A análise foi concluída, mas o link público não pôde ser salvo.';
      }
      loadHistory();
    } catch (error) {
      write('[data-link-status]', 'Análise indisponível');
      write('[data-link-summary]', error.message);
      write('[data-link-score]', '');
      root.querySelector('[data-link-evidence]').replaceChildren();
      root.querySelector('[data-link-alerts]').replaceChildren();
    } finally {
      button.disabled = false;
      refreshMode();
    }
  });
})();
