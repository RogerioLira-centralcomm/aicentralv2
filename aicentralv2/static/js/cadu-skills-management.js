document.addEventListener('DOMContentLoaded', () => {
  const root = document.querySelector('[data-skills-management]');
  if (!root) return;
  root.addEventListener('click', async event => {
    const managed = event.target.closest('[data-managed-skill]');
    if (managed) {
      const form = managed.querySelector('[data-skill-form]');
      if (event.target.closest('[data-edit-skill]')) { form.hidden = !form.hidden; if (!form.hidden) form.querySelector('input,textarea,select')?.focus(); }
      if (event.target.closest('[data-cancel-skill]')) form.hidden = true;
    }
    const custom = event.target.closest('[data-custom-skill]');
    if (!custom) return;
    if (event.target.closest('[data-open-custom-links]')) { custom.querySelector('[data-custom-links]').hidden = false; custom.querySelector('select')?.focus(); }
    if (event.target.closest('[data-close-custom-links]')) custom.querySelector('[data-custom-links]').hidden = true;
    if (event.target.closest('[data-open-custom-test]')) { custom.querySelector('[data-custom-test]').hidden = false; custom.querySelector('textarea')?.focus(); }
    if (event.target.closest('[data-close-custom-test]')) custom.querySelector('[data-custom-test]').hidden = true;
    const linkButton = event.target.closest('[data-create-link]');
    if (linkButton) {
      const box = custom.querySelector('[data-custom-link]'), status = box.querySelector('[data-link-status]');
      box.hidden = false; status.textContent = 'Criando link privado…'; linkButton.disabled = true;
      try {
        const response = await fetch(linkButton.dataset.url, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({permission:box.querySelector('select').value})});
        const body = await response.json(); if (!response.ok) throw new Error(body.error || 'Não foi possível criar o link.');
        box.querySelector('[data-link-output]').textContent = body.url; box.querySelector('[data-copy-link]').hidden = false; status.textContent = body.message;
      } catch (error) { status.textContent = error.message; } finally { linkButton.disabled = false; }
    }
    const copyButton = event.target.closest('[data-copy-link]');
    if (copyButton) { await navigator.clipboard.writeText(custom.querySelector('[data-link-output]').textContent); copyButton.textContent = 'Copiado'; }
    const revokeButton = event.target.closest('[data-revoke-links]');
    if (revokeButton && window.confirm('Revogar todos os links ativos desta skill? Os endereços atuais deixarão de funcionar.')) {
      revokeButton.disabled = true;
      try { const response = await fetch(revokeButton.dataset.url, {method:'POST'}); const body = await response.json(); if (!response.ok) throw new Error(body.error || 'Não foi possível revogar.'); revokeButton.textContent = body.message; }
      catch (error) { revokeButton.textContent = error.message; revokeButton.disabled = false; }
    }
  });
  root.querySelectorAll('[data-skill-form]').forEach(form => form.addEventListener('submit', async event => {
    event.preventDefault(); const button = form.querySelector('[type="submit"]'), status = form.querySelector('[data-form-status]'), data = Object.fromEntries(new FormData(form));
    data.is_testable = form.elements.is_testable.checked; data.display_rank = Number(data.display_rank); data.credit_cost = Number(data.credit_cost); button.disabled = true; status.textContent = 'Salvando…';
    try { const response = await fetch(form.dataset.url, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)}); const body = await response.json(); if (!response.ok) throw new Error(body.error || 'Não foi possível salvar.'); status.textContent = body.message; window.setTimeout(() => window.location.reload(), 500); }
    catch (error) { status.textContent = error.message; } finally { button.disabled = false; }
  }));
  root.querySelectorAll('[data-custom-test]').forEach(form => form.addEventListener('submit', async event => {
    if (form.matches('[data-custom-links]')) return;
    event.preventDefault(); const button = form.querySelector('[type="submit"]'), status = form.querySelector('[data-test-status]'), answer = form.querySelector('[data-test-answer]');
    button.disabled = true; status.textContent = 'Executando e verificando créditos…'; answer.hidden = true;
    try {
      const response = await fetch(form.dataset.url, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({prompt:form.elements.prompt.value, confirm_charge:form.elements.confirm_charge.checked})});
      const body = await response.json(); if (!response.ok) throw new Error(body.error || 'Não foi possível testar.');
      status.textContent = `${body.charged_credits} crédito(s) utilizado(s). Saldo: ${body.remaining_credits}.`; answer.textContent = body.answer; answer.hidden = false;
    } catch (error) { status.textContent = error.message; } finally { button.disabled = false; }
  }));
  root.querySelectorAll('[data-custom-links]').forEach(form => {
    const client = form.elements.client_id, project = form.elements.project_id;
    const filterProjects = () => { [...project.options].forEach(option => { option.hidden = Boolean(option.value) && option.dataset.clientId !== client.value; }); if (project.selectedOptions[0]?.hidden) project.value = ''; };
    client.addEventListener('change', filterProjects); filterProjects();
    form.addEventListener('submit', async event => {
      event.preventDefault(); const button = form.querySelector('[type="submit"]'), status = form.querySelector('[data-links-status]'), data = Object.fromEntries(new FormData(form)); button.disabled = true; status.textContent = 'Salvando vínculos…';
      try { const response = await fetch(form.dataset.url, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)}); const body = await response.json(); if (!response.ok) throw new Error(body.error || 'Não foi possível salvar.'); status.textContent = body.message; window.setTimeout(() => window.location.reload(), 500); }
      catch (error) { status.textContent = error.message; } finally { button.disabled = false; }
    });
  });
  root.querySelector('[data-custom-search]')?.addEventListener('input', event => {
    const query = event.target.value.toLocaleLowerCase('pt-BR');
    root.querySelectorAll('[data-custom-skill]').forEach(row => { row.hidden = !row.dataset.search.toLocaleLowerCase('pt-BR').includes(query); });
  });
});
