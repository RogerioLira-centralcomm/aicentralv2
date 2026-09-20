(function () {
  const root = document.querySelector('[data-onboarding-root]');
  const form = document.querySelector('[data-onboarding-form]');
  if (!root || !form) return;
  const steps = [...form.querySelectorAll('[data-step]')];
  const progress = [...root.querySelectorAll('[data-progress-step]')];
  const next = root.querySelector('[data-onboarding-next]');
  const back = root.querySelector('[data-onboarding-back]');
  const submit = root.querySelector('[data-onboarding-submit]');
  let current = 0;
  const field = (name) => form.elements.namedItem(name);
  const value = (name) => String(field(name)?.value || '').trim();

  function updateAgencyFields() {
    const selected = form.querySelector('input[name="operation_type"]:checked')?.value;
    root.querySelectorAll('[data-agency-only]').forEach((item) => {
      item.hidden = selected !== 'agency';
    });
  }

  function updateSummary() {
    const values = { organization: value('organization_name'), brand: value('brand_name'), project: value('project_name') };
    Object.entries(values).forEach(([key, text]) => {
      const target = root.querySelector(`[data-summary="${key}"]`);
      if (target) target.textContent = text || '—';
    });
  }

  function show(index) {
    current = Math.max(0, Math.min(index, steps.length - 1));
    steps.forEach((step, position) => {
      step.hidden = position !== current;
      step.classList.toggle('is-visible', position === current);
    });
    progress.forEach((item, position) => {
      item.classList.toggle('is-active', position === current);
      item.classList.toggle('is-done', position < current);
    });
    back.hidden = current === 0;
    next.hidden = current === steps.length - 1;
    submit.hidden = current !== steps.length - 1;
    if (current === steps.length - 1) updateSummary();
    steps[current].querySelector('input, textarea')?.focus({ preventScroll: true });
  }

  function validateCurrent() {
    const controls = [...steps[current].querySelectorAll('input, textarea')].filter((control) => !control.disabled && !control.closest('[hidden]'));
    for (const control of controls) {
      if (!control.checkValidity()) {
        control.reportValidity();
        return false;
      }
    }
    if (current === 1 && !value('website_url') && !field('images')?.files?.length) {
      window.alert('Informe o site oficial ou envie ao menos uma referência visual para iniciar a auditoria.');
      field('website_url')?.focus();
      return false;
    }
    return true;
  }

  form.addEventListener('change', (event) => {
    if (event.target.name === 'operation_type') updateAgencyFields();
  });
  next.addEventListener('click', () => {
    if (validateCurrent()) show(current + 1);
  });
  back.addEventListener('click', () => show(current - 1));
  form.addEventListener('submit', (event) => {
    if (current !== steps.length - 1 || !validateCurrent()) {
      event.preventDefault();
      return;
    }
    submit.disabled = true;
    submit.textContent = 'Preparando seu Workspace…';
  });
  updateAgencyFields();
  show(0);
}());
