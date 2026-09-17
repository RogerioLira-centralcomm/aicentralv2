(() => {
  'use strict';
  const root = document.querySelector('[data-doc-editor]');
  if (!root) return;
  const id = root.dataset.documentId;
  const csrf = root.dataset.csrf;
  const content = root.querySelector('[data-editor-content]');
  const title = root.querySelector('[data-editor-title]');
  const status = root.querySelector('[data-editor-status]');
  const notice = root.querySelector('[data-editor-notice]');
  const show = message => { notice.textContent = message; notice.hidden = !message; };
  const request = async (path, options = {}) => {
    const response = await fetch(`/docs/${id}${path}`, {credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf, ...(options.headers || {})}, ...options});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.description || data.error || 'Não foi possível concluir esta ação.');
    return data;
  };
  const save = async () => {
    if (!content) return;
    show('Salvando alterações…');
    const data = await request('/content', {method: 'PUT', body: JSON.stringify({title: title.value, status: status.value, html: content.innerHTML})});
    root.querySelector('[data-editor-heading]').textContent = data.document.title;
    root.querySelector('[data-editor-status-label]').textContent = {'draft':'Rascunho', 'published':'Publicado', 'archived':'Arquivado'}[data.document.status] || 'Rascunho';
    show('Alterações salvas.');
  };
  root.querySelector('[data-editor-save]')?.addEventListener('click', () => save().catch(error => show(error.message)));
  document.addEventListener('keydown', event => { if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 's' && content?.contains(document.activeElement)) { event.preventDefault(); save().catch(error => show(error.message)); } });
  root.querySelectorAll('[data-editor-format]').forEach(button => button.addEventListener('click', () => {
    content?.focus(); const [command, value] = button.dataset.editorFormat.split(':');
    if (command === 'createLink') { const href = window.prompt('Endereço do link'); if (href) document.execCommand(command, false, href); }
    else document.execCommand(command, false, value || null);
  }));
  const templates = {
    briefing: '<h2>Decisão que este trabalho precisa apoiar</h2><p>Descreva o problema, a oportunidade ou a mudança que torna este trabalho necessário.</p><h2>Objetivo e resultado esperado</h2><ul><li><strong>Objetivo:</strong> [preencher]</li><li><strong>Indicador de sucesso:</strong> [preencher]</li><li><strong>Prazo:</strong> [preencher]</li></ul><h2>Público e mensagem</h2><p>Quem precisa ser movido, o que já sabe e qual mensagem deve ficar clara?</p><h2>Restrições e decisões já tomadas</h2><p>Registre aprovações, limites, ativos obrigatórios e o que não deve ser feito.</p><h2>Próximos passos</h2><ol><li>[responsável] · [ação] · [data]</li></ol>',
    plano: '<h2>Resumo executivo</h2><p>Qual é a recomendação e por que ela é a melhor resposta ao desafio?</p><h2>Contexto e objetivo</h2><p>[descreva o cenário, objetivo e KPI prioritário]</p><h2>Estratégia de mídia</h2><p>Explique a função de cada frente: alcance, consideração, conversão ou retenção.</p><h2>Investimento e distribuição</h2><table><thead><tr><th>Canal</th><th>Função</th><th>Investimento</th><th>KPI</th></tr></thead><tbody><tr><td>[canal]</td><td>[função]</td><td>[valor]</td><td>[KPI]</td></tr></tbody></table><h2>Premissas e riscos</h2><p>O que precisa se manter verdadeiro para este plano funcionar?</p><h2>Próxima decisão</h2><p>O que o time precisa aprovar ou entregar para começar?</p>',
    proposta: '<h2>O desafio</h2><p>Mostre que entendemos o contexto e a decisão que importa para o cliente.</p><h2>Nossa recomendação</h2><p>Apresente a solução, o escopo e o motivo da escolha.</p><h2>Entregas</h2><ul><li>[entrega]</li><li>[entrega]</li></ul><h2>Investimento e condições</h2><p>[preencher após validação comercial]</p><h2>Próximos passos</h2><p>Defina aprovação, responsáveis e início previsto.</p>',
    relatorio: '<h2>Leitura do período</h2><p>O que aconteceu e qual é a principal conclusão?</p><h2>Resultados</h2><table><thead><tr><th>Indicador</th><th>Meta</th><th>Resultado</th><th>Leitura</th></tr></thead><tbody><tr><td>[KPI]</td><td>[meta]</td><td>[resultado]</td><td>[interpretação]</td></tr></tbody></table><h2>O que aprendemos</h2><ul><li>[aprendizado]</li></ul><h2>Otimizações recomendadas</h2><ol><li>[ação] · [impacto esperado]</li></ol><h2>Próximo ciclo</h2><p>O que manter, testar ou interromper?</p>'
  };
  root.querySelectorAll('[data-editor-template]').forEach(button => button.addEventListener('click', () => { if (!content) return; if (content.textContent.trim() && !window.confirm('Aplicar esta estrutura substitui o conteúdo atual. Continuar?')) return; content.innerHTML = templates[button.dataset.editorTemplate] || ''; content.focus(); show('Estrutura aplicada. Personalize com o contexto do projeto e salve.'); }));
  root.querySelector('[data-editor-duplicate]')?.addEventListener('click', async () => { try { const data = await request('/duplicate', {method: 'POST', body: '{}'}); window.location.assign(`/docs/${data.document.id}`); } catch (error) { show(error.message); } });
  root.querySelector('[data-editor-share]')?.addEventListener('click', async event => { try { const data = await request('/share', {method: 'POST', body: JSON.stringify({enabled: true})}); const url = new URL(`/familia/planner/docs/public/${encodeURIComponent(data.document.share_token)}`, window.location.origin).href; await navigator.clipboard?.writeText(url); event.currentTarget.textContent = 'Link público copiado'; show('Link público ativado e copiado.'); } catch (error) { show(error.message); } });
  root.querySelector('[data-editor-review]')?.addEventListener('click', async event => { try { const estimate = await request('/review/estimate', {method: 'GET'}); if (!window.confirm(`O Cadu fará ${estimate.passes} revisões e pode usar até ${Number(estimate.estimated_tokens).toLocaleString('pt-BR')} créditos. Continuar?`)) return; event.currentTarget.disabled = true; show('O Cadu está revisando o documento…'); const source_ids = Array.from(root.querySelectorAll('[data-source-id]:checked'), item => Number(item.dataset.sourceId)); const data = await request('/review', {method: 'POST', body: JSON.stringify({source_ids})}); if (data.document?.html && content) content.innerHTML = data.document.html; show('Revisão aplicada. Confira e salve a versão.'); } catch (error) { show(error.message); } finally { event.currentTarget.disabled = false; } });
})();
