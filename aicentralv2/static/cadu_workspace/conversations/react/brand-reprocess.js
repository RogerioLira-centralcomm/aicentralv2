(() => {
  const root = document.getElementById('cadu-conversations-v2-root');
  const bootstrap = document.getElementById('cadu-conversations-v2-bootstrap');
  if (!root || !bootstrap) return;

  let data;
  try { data = JSON.parse(bootstrap.textContent || '{}'); } catch { return; }
  const brand = data.brand || {};
  const hasPreviousAnalysis = Boolean(
    brand.reviewPack?.status || brand.analysisMetadata?.pagesAnalyzed || brand.auditInput?.websiteUrl,
  );

  const enhance = () => {
    const dialog = root.querySelector('.cadu-ds-brand-dialog');
    const form = dialog?.querySelector('form.cadu-ds-brand-form');
    if (!dialog || !form || form.dataset.reprocessReady === 'true') return;
    if (!/\/auditoria(?:\/|$)/.test(form.action || '')) return;
    form.dataset.reprocessReady = 'true';

    if (hasPreviousAnalysis) {
      const title = dialog.querySelector('header h2');
      if (title && /analisar marca|iniciar análise/i.test(title.textContent || '')) {
        title.textContent = 'Reprocessar análise';
      }
    }

    const note = document.createElement('aside');
    note.className = 'cadu-ds-brand-reprocess-note';
    const heading = document.createElement('strong');
    heading.textContent = hasPreviousAnalysis ? 'Dados preservados nesta nova análise' : 'Como a análise funciona';
    const detail = document.createElement('span');
    detail.textContent = 'URL e logo atual continuam protegidos. Edite a URL abaixo ou solte novas referências para complementar a análise.';
    note.append(heading, detail);
    if (brand.preserved?.logoUrl) {
      const logoNote = document.createElement('small');
      logoNote.textContent = 'Logo principal atual: preservado até você escolher outro na biblioteca da marca.';
      note.append(logoNote);
    }
    form.prepend(note);

    const website = form.querySelector('input[name="website_url"]');
    if (website && !website.value) website.value = brand.preserved?.websiteUrl || brand.auditInput?.websiteUrl || '';
  };

  new MutationObserver(enhance).observe(root, { childList: true, subtree: true });
  enhance();
})();
