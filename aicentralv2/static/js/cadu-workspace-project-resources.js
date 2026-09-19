(() => {
  const root = document.querySelector('[data-project-resources]');
  if (!root) return;
  const buttons = [...root.querySelectorAll('[data-resource-filter]')];
  const rows = [...root.querySelectorAll('[data-resource-kind]')];
  buttons.forEach(button => button.addEventListener('click', () => {
    const kind = button.dataset.resourceFilter;
    buttons.forEach(item => item.classList.toggle('is-active', item === button));
    rows.forEach(row => { row.hidden = kind !== 'all' && row.dataset.resourceKind !== kind; });
  }));
})();
