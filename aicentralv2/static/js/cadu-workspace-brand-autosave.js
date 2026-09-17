(() => {
  const form = document.querySelector('[data-brand-autosave]');
  const status = document.querySelector('[data-brand-save-status]');
  if (!form || !status) return;
  let timer; let controller; let dirty = false;
  const setStatus = (value, tone = '') => { status.textContent = value; status.dataset.tone = tone; };
  const save = async () => {
    if (!dirty) return;
    dirty = false;
    controller?.abort(); controller = new AbortController();
    setStatus('Salvando…', 'saving');
    try {
      const response = await fetch(form.action, {method: 'POST', body: new FormData(form), headers: {'Accept': 'application/json'}, signal: controller.signal});
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.error || 'Não foi possível salvar.');
      setStatus('Salvo agora', 'saved');
    } catch (error) {
      if (error.name === 'AbortError') return;
      dirty = true; setStatus('Não salvo · tentar novamente', 'error');
    }
  };
  const schedule = () => { dirty = true; setStatus('Alterações pendentes', 'pending'); window.clearTimeout(timer); timer = window.setTimeout(save, 700); };
  form.querySelectorAll('input, textarea, select').forEach((field) => {
    if (field.type === 'hidden') return;
    field.addEventListener('input', schedule);
    field.addEventListener('change', schedule);
    field.addEventListener('blur', save);
  });
  form.addEventListener('submit', (event) => { event.preventDefault(); window.clearTimeout(timer); dirty = true; save(); });
  const linkDialog = document.querySelector('[data-brand-link-dialog]');
  document.querySelectorAll('[data-brand-link-open]').forEach((button) => button.addEventListener('click', () => linkDialog?.showModal()));
  linkDialog?.querySelectorAll('[data-brand-link-close]').forEach((button) => button.addEventListener('click', () => linkDialog.close()));
  linkDialog?.addEventListener('click', (event) => { if (event.target === linkDialog) linkDialog.close(); });
  const sectionLinks = [...document.querySelectorAll('.workspace-brand-section-nav a')];
  const sections = sectionLinks.map((link) => document.querySelector(link.hash)).filter(Boolean);
  const setActiveSection = (id) => sectionLinks.forEach((link) => {
    const active = link.hash === `#${id}`;
    link.toggleAttribute('aria-current', active);
    if (active) link.setAttribute('aria-current', 'location');
  });
  sectionLinks.forEach((link) => link.addEventListener('click', () => {
    const target = document.querySelector(link.hash);
    if (target) setActiveSection(target.id);
  }));
  if (sections.length) {
    const current = sections.find((section) => section.getBoundingClientRect().top >= 0) || sections[0];
    setActiveSection(current.id);
  }
  if ('IntersectionObserver' in window && sections.length) {
    const observer = new IntersectionObserver((entries) => {
      const active = entries.filter((entry) => entry.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
      if (!active) return;
      setActiveSection(active.target.id);
    }, {rootMargin: '-18% 0px -65% 0px', threshold: [0.05, 0.25]});
    sections.forEach((section) => observer.observe(section));
  }
})();
