(() => {
  const form = document.querySelector('.connect-entry-selector');
  if (form) form.addEventListener('submit', () => window.ConnectUI?.setBusy(form.querySelector('button'), true, 'Abrindo…'));
  document.querySelectorAll('.connect-entry-sidebar nav a[href^="#"]').forEach((link) => link.addEventListener('click', () => {
    document.querySelectorAll('.connect-entry-sidebar nav a').forEach((item) => item.classList.remove('is-current'));
    link.classList.add('is-current');
  }));
})();
