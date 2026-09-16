(() => {
  'use strict';
  const key = 'cadu-sidebar-state';
  const root = document.documentElement;
  const desktop = () => window.matchMedia('(min-width: 821px)').matches;
  const setState = collapsed => {
    root.dataset.caduSidebar = collapsed && desktop() ? 'collapsed' : 'expanded';
    document.querySelectorAll('[data-cadu-sidebar-toggle]').forEach(button => {
      button.setAttribute('aria-expanded', String(!collapsed));
      button.setAttribute('aria-label', collapsed ? 'Expandir navegação' : 'Recolher navegação');
    });
  };
  try { setState(localStorage.getItem(key) === 'collapsed'); } catch (_) { setState(false); }
  document.addEventListener('click', event => {
    const toggle = event.target.closest('[data-cadu-sidebar-toggle]');
    if (toggle) { const next = root.dataset.caduSidebar !== 'collapsed'; setState(next); try { localStorage.setItem(key, next ? 'collapsed' : 'expanded'); } catch (_) {} return; }
    if (event.target.closest('[data-cadu-sidebar-mobile-toggle]')) { document.body.classList.add('cadu-sidebar-drawer-open'); return; }
    if (event.target.closest('[data-cadu-sidebar-overlay]') || event.target.closest('.cadu-app-sidebar a,.workspace-app-sidebar a,.connect-entry-sidebar a,.family-modules a')) document.body.classList.remove('cadu-sidebar-drawer-open');
  });
  document.addEventListener('keydown', event => { if (event.key === 'Escape') document.body.classList.remove('cadu-sidebar-drawer-open'); });
  window.addEventListener('resize', () => { if (desktop()) document.body.classList.remove('cadu-sidebar-drawer-open'); });
})();
