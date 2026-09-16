/* One preference across Cadu products. Studio never writes over it. */
(() => {
  'use strict';
  const root = document.documentElement;
  const script = document.currentScript;
  const forced = script?.dataset.forceTheme === 'dark';
  const cookieName = 'cadu-theme';
  const configuredDomain = (script?.dataset.cookieDomain || '').replace(/^\./, '');
  function read() {
    try {
      const value = document.cookie.split(';').map(part => part.trim()).find(part => part.startsWith(cookieName + '='))?.slice(cookieName.length + 1);
      if (value === 'light' || value === 'dark') return value;
    } catch (_) {}
    return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  function apply(theme) {
    root.dataset.caduTheme = theme;
    root.style.colorScheme = theme;
    document.querySelectorAll('[data-cadu-theme-toggle]').forEach(button => {
      button.hidden = forced;
      button.textContent = theme === 'dark' ? 'Modo claro' : 'Modo escuro';
      button.setAttribute('aria-label', theme === 'dark' ? 'Usar aparência clara' : 'Usar aparência escura');
      button.setAttribute('aria-pressed', String(theme === 'dark'));
    });
  }
  apply(forced ? 'dark' : read());
  document.addEventListener('DOMContentLoaded', () => apply(root.dataset.caduTheme), {once:true});
  document.addEventListener('click', event => {
    if (forced || !event.target.closest('[data-cadu-theme-toggle]')) return;
    const theme = root.dataset.caduTheme === 'dark' ? 'light' : 'dark';
    apply(theme);
    const host = window.location.hostname;
    const domain = configuredDomain.includes('.') && (host === configuredDomain || host.endsWith('.' + configuredDomain)) ? '; Domain=' + configuredDomain : '';
    try { document.cookie = cookieName + '=' + theme + '; Path=/; Max-Age=31536000; SameSite=Lax' + domain + (location.protocol === 'https:' ? '; Secure' : ''); } catch (_) {}
  });
  window.addEventListener('pageshow', () => apply(forced ? 'dark' : read()));
})();
