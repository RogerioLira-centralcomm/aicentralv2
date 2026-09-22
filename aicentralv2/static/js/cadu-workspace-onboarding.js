(function () {
  const root = document.querySelector('[data-onboarding-root]');
  const form = document.querySelector('[data-onboarding-form]');
  if (!root || !form) return;
  const steps = [...form.querySelectorAll('[data-step]')];
  const progress = [...root.querySelectorAll('[data-progress-step]')];
  const next = root.querySelector('[data-onboarding-next]');
  const back = root.querySelector('[data-onboarding-back]');
  const submit = root.querySelector('[data-onboarding-submit]');
  const feedback = root.querySelector('[data-onboarding-feedback]');
  const storySlides = [...root.querySelectorAll('[data-onboarding-story-slide]')];
  const storyDots = [...root.querySelectorAll('[data-story-dot]')];
  const storyPrevious = root.querySelector('[data-story-prev]');
  const storyNext = root.querySelector('[data-story-next]');
  const mobileStory = root.querySelector('[data-onboarding-mobile-story]');
  let current = 0;
  let storyIndex = 0;
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

  function clearFeedback() {
    if (!feedback) return;
    feedback.hidden = true;
    feedback.textContent = '';
  }

  function showFeedback(message, control) {
    if (!feedback) return;
    feedback.textContent = message;
    feedback.hidden = false;
    control?.focus();
  }

  function showStory(index) {
    if (!storySlides.length) return;
    storyIndex = (index + storySlides.length) % storySlides.length;
    storySlides.forEach((slide, position) => {
      const active = position === storyIndex;
      slide.classList.toggle('is-active', active);
      slide.setAttribute('aria-hidden', String(!active));
    });
    storyDots.forEach((dot, position) => {
      const active = position === storyIndex;
      dot.classList.toggle('is-active', active);
      dot.setAttribute('aria-current', active ? 'true' : 'false');
    });
    const active = storySlides[storyIndex];
    if (mobileStory && active) {
      mobileStory.replaceChildren();
      const label = document.createElement('span');
      const title = document.createElement('b');
      const copy = document.createElement('p');
      label.textContent = active.dataset.storyName || '';
      title.textContent = active.dataset.storyTitle || '';
      copy.textContent = active.dataset.storyCopy || '';
      mobileStory.append(label, title, copy);
    }
  }

  function show(index) {
    clearFeedback();
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
    if (current > 0) steps[current].querySelector('input, textarea')?.focus({ preventScroll: true });
  }

  function validateCurrent() {
    const controls = [...steps[current].querySelectorAll('input, textarea')].filter((control) => !control.disabled && !control.closest('[hidden]'));
    for (const control of controls) {
      if (!control.checkValidity()) {
        control.reportValidity();
        return false;
      }
    }
    if (current === 2 && field('images')?.files?.length > 4) {
      showFeedback('Selecione no máximo quatro referências visuais.', field('images'));
      return false;
    }
    if (current === 2 && !value('website_url') && !field('images')?.files?.length) {
      showFeedback('Informe o site oficial ou envie uma referência visual para iniciar a auditoria.', field('website_url'));
      return false;
    }
    return true;
  }

  form.addEventListener('change', (event) => {
    clearFeedback();
    if (event.target.name === 'operation_type') updateAgencyFields();
  });
  form.addEventListener('input', clearFeedback);
  next.addEventListener('click', () => {
    if (validateCurrent()) show(current + 1);
  });
  back.addEventListener('click', () => show(current - 1));
  storyPrevious?.addEventListener('click', () => showStory(storyIndex - 1));
  storyNext?.addEventListener('click', () => showStory(storyIndex + 1));
  storyDots.forEach((dot) => dot.addEventListener('click', () => showStory(Number(dot.dataset.storyDot))));
  form.addEventListener('submit', (event) => {
    if (current !== steps.length - 1 || !validateCurrent()) {
      event.preventDefault();
      return;
    }
    submit.disabled = true;
    submit.textContent = 'Preparando seu Workspace…';
  });
  updateAgencyFields();
  showStory(0);
  show(0);
}());
