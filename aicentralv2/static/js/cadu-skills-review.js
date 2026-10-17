// Cadu Análise — envia o plano, mostra o parecer. O texto dos achados vem do servidor e entra como textContent.
(() => {
  const page = document.querySelector('[data-review-page]');
  if (!page) return;
  const form = page.querySelector('[data-review-form]');
  const drop = page.querySelector('[data-review-drop]');
  const fileInput = page.querySelector('[data-review-file]');
  const fileName = page.querySelector('[data-review-file-name]');
  const submit = page.querySelector('[data-review-submit]');
  const status = page.querySelector('[data-review-status]');
  const result = page.querySelector('[data-review-result]');
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
  const STATUS = { ok: 'OK', atencao: 'Atenção', erro: 'Erro', na: 'Sem dados' };
  const ALLOWED = /\.(xlsx|csv|pdf)$/i;
  let markdown = '';

  const el = (tag, props = {}, children = []) => {
    const node = document.createElement(tag);
    Object.entries(props).forEach(([key, value]) => { if (key === 'text') node.textContent = value; else node.setAttribute(key, value); });
    children.forEach(child => node.append(child));
    return node;
  };
  const money = value => value == null ? '—' : value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
  const num = value => value == null ? '—' : value.toLocaleString('pt-BR', { maximumFractionDigits: 2 });
  const date = value => value ? value.split('-').reverse().join('/') : '';
  const setStatus = (text, error = false) => { status.textContent = text; status.classList.toggle('is-error', error); };

  const showFile = () => {
    const file = fileInput.files[0];
    fileName.textContent = file ? file.name : 'Arraste o plano aqui ou escolha um arquivo';
    drop.classList.toggle('has-file', Boolean(file));
    setStatus(file && !ALLOWED.test(file.name) ? 'Envie XLSX, CSV ou PDF.' : '', Boolean(file && !ALLOWED.test(file.name)));
  };
  fileInput.addEventListener('change', showFile);
  ['dragenter', 'dragover'].forEach(type => drop.addEventListener(type, () => drop.classList.add('is-dragging')));
  ['dragleave', 'drop'].forEach(type => drop.addEventListener(type, () => drop.classList.remove('is-dragging')));

  const pill = state => el('span', { class: `skills-review-status is-${state}`, text: STATUS[state] });

  const render = data => {
    const { summary } = data;
    const verdict = page.querySelector('[data-review-verdict]');
    verdict.textContent = summary.verdict_label;
    verdict.className = `is-${summary.verdict}`;
    page.querySelector('[data-review-score]').textContent = summary.score;
    page.querySelector('[data-review-meta]').textContent =
      `${data.file.name} · ${data.file.lines} linhas · ${money(summary.investimento_total)} · ${summary.criteria} critérios`;
    page.querySelector('[data-review-partial]').hidden = !summary.partial;
    const counts = page.querySelector('[data-review-counts]');
    counts.replaceChildren(...['erro', 'atencao', 'ok', 'na'].filter(key => summary.counts[key])
      .map(key => el('li', {}, [el('span', { class: `skills-review-status is-${key}`, text: `${summary.counts[key]} ${STATUS[key].toLowerCase()}` })])));

    const groups = ['Conta', 'Estratégia'].map(group => {
      const items = data.findings.filter(item => item.group === group);
      const note = group === 'Conta' ? 'calculado pelo código' : 'julgado pelo TypeSafe';
      return el('section', { class: 'skills-review-group' }, [
        el('h3', {}, [group, el('small', { text: note })]),
        el('ol', {}, items.map(item => el('li', { class: 'skills-review-finding' }, [
          el('b', { text: item.label }), pill(item.status), el('p', { text: item.detail }),
          ...(item.suggestion ? [el('small', { text: item.suggestion })] : []),
        ]))),
      ]);
    });
    page.querySelector('[data-review-groups]').replaceChildren(...groups);

    const flagged = new Set(data.findings.filter(item => item.status === 'erro' || item.status === 'atencao').flatMap(item => item.lines));
    page.querySelector('[data-review-lines-title]').textContent = `Linhas lidas (${data.lines.length})`;
    page.querySelector('[data-review-lines]').replaceChildren(...data.lines.map(line => el('tr', { class: flagged.has(line.linha) ? 'is-flagged' : '' }, [
      el('td', { text: line.linha }), el('td', { text: line.canal }), el('td', { text: line.formato }),
      el('td', { text: (line.modelo || line.modelo_original || '').toUpperCase() }),
      el('td', { class: 'is-number', text: line.custo_unitario == null ? '—' : money(line.custo_unitario) }),
      el('td', { class: 'is-number', text: num(line.quantidade) }),
      el('td', { class: 'is-number', text: money(line.investimento ?? line.investimento_bruto) }),
      el('td', { text: [date(line.inicio), date(line.fim)].filter(Boolean).join(' a ') }),
    ])));
    markdown = data.markdown || '';
    result.hidden = false;
    result.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  form.addEventListener('submit', async event => {
    event.preventDefault();
    const file = fileInput.files[0];
    if (!file) { setStatus('Escolha o arquivo do plano.', true); return; }
    if (!ALLOWED.test(file.name)) { setStatus('Envie XLSX, CSV ou PDF.', true); return; }
    if (file.size > 5 * 1024 * 1024) { setStatus('O arquivo deve ter até 5 MB.', true); return; }
    submit.disabled = true;
    submit.textContent = 'Revisando…';
    setStatus('Conferindo a conta e consultando o TypeSafe. Leva até um minuto.');
    try {
      const response = await fetch(page.dataset.endpoint, {
        method: 'POST', body: new FormData(form), credentials: 'same-origin',
        headers: { 'X-CSRF-Token': csrf, Accept: 'application/json' },
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || !payload.success) throw new Error(payload.error || 'Não foi possível revisar o plano agora.');
      setStatus('');
      render(payload.result);
    } catch (error) {
      setStatus(error.message, true);
    } finally {
      submit.disabled = false;
      submit.textContent = 'Revisar plano';
    }
  });

  page.querySelector('[data-review-copy]').addEventListener('click', async event => {
    const button = event.currentTarget;
    try { await navigator.clipboard.writeText(markdown); button.textContent = 'Parecer copiado'; }
    catch { button.textContent = 'Não foi possível copiar'; }
    setTimeout(() => { button.textContent = 'Copiar parecer'; }, 2000);
  });
  page.querySelector('[data-review-again]').addEventListener('click', () => {
    form.reset(); showFile(); result.hidden = true; markdown = '';
    page.querySelector('.skills-review-page__run').scrollIntoView({ behavior: 'smooth' });
  });
})();
