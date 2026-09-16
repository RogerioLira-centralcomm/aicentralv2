(() => {
  const form = document.querySelector('[data-project-query]');
  const output = document.querySelector('[data-query-results]');
  if (!form || !output) return;

  const escape = (value) => String(value || '').replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const query = form.elements.query.value.trim();
    if (query.length < 3) { output.textContent = 'Escreva ao menos três caracteres para consultar.'; return; }
    output.textContent = 'Consultando fontes indexadas…';
    try {
      const response = await fetch(form.dataset.url, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({query})});
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || 'Não foi possível consultar a base.');
      output.innerHTML = payload.results.length ? payload.results.map((item) => `<article><b>${escape(item.titulo || 'Fonte')}</b><p>${escape(item.conteudo)}</p></article>`).join('') : '<p>Nenhum trecho indexado corresponde a esta consulta.</p>';
    } catch (error) { output.textContent = error.message || 'Não foi possível consultar a base.'; }
  });
})();
