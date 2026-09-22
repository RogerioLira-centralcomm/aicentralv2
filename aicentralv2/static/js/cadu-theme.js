/* Light by default, Studio dark, and an isolated preference for conversations. */
(() => {
  'use strict';
  const root = document.documentElement;
  const THEME_TRANSITION_MS = 200;
  const script = document.currentScript;
  const mode = script?.dataset.themeMode || 'light';
  const skin = script?.dataset.themeSkin || '';
  const defaultTheme = script?.dataset.themeDefault === 'dark' ? 'dark' : 'light';
  const allowsPreference = mode === 'preference';
  const forcedTheme = mode === 'dark' ? 'dark' : mode === 'light' ? 'light' : null;
  const storageKey = 'cadu-theme:' + (script?.dataset.themeScope || 'default');
  function read() {
    try {
      const value = window.localStorage?.getItem(storageKey);
      if (value === 'light' || value === 'dark') return value;
    } catch (_) {}
    return defaultTheme;
  }
  function apply(theme) {
    root.dataset.caduTheme = theme;
    if (skin) root.dataset.caduSkin = skin;
    root.style.colorScheme = theme;
    document.querySelectorAll('[data-cadu-theme-toggle]').forEach(button => {
      button.hidden = !allowsPreference;
      button.textContent = theme === 'dark' ? 'Modo claro' : 'Modo escuro';
      button.setAttribute('aria-label', theme === 'dark' ? 'Usar aparência clara' : 'Usar aparência escura');
      button.setAttribute('aria-pressed', String(theme === 'dark'));
    });
  }
  function animateThemeChange() {
    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return;
    root.classList?.remove?.('cadu-theme-transition');
    // Force a clean reflow so repeated toggles always restart the same motion.
    void root.offsetWidth;
    root.classList?.add?.('cadu-theme-transition');
    window.setTimeout?.(() => root.classList?.remove?.('cadu-theme-transition'), THEME_TRANSITION_MS);
  }
  const currentTheme = () => forcedTheme || read();
  apply(currentTheme());
  document.addEventListener('DOMContentLoaded', () => apply(root.dataset.caduTheme), {once:true});
  document.addEventListener('click', event => {
    if (!allowsPreference || !event.target.closest('[data-cadu-theme-toggle]')) return;
    const theme = root.dataset.caduTheme === 'dark' ? 'light' : 'dark';
    animateThemeChange();
    apply(theme);
    try { window.localStorage?.setItem(storageKey, theme); } catch (_) {}
  });
  window.addEventListener('pageshow', () => apply(currentTheme()));
})();
