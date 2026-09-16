(() => {
  'use strict';
  const key = 'cadu-sidebar-state';
  const root = document.documentElement;
  const desktop = () => window.matchMedia('(min-width: 821px)').matches;
  const drawer = document.querySelector('.cadu-app-sidebar,.workspace-app-sidebar,.reports-app-sidebar,.connect-entry-sidebar,.family-layout--sidebar .family-modules');
  const mobileToggles = [...document.querySelectorAll('[data-cadu-sidebar-mobile-toggle]')];
  const main = document.querySelector('.workspace-app-main,.reports-app-main,.connect-entry,.cadu-app-shell>main,.family-layout--sidebar>main') || document.querySelector('main#content');
  const obscuredWhileOpen = [main, document.querySelector('.portal-skip'), document.querySelector('.cadu-conversation-launcher'), document.querySelector('.cadu-family-footer')].filter(Boolean);
  let lastTrigger = null;
  if (drawer) {
    drawer.id ||= 'cadu-app-sidebar';
    mobileToggles.forEach(button => { button.setAttribute('aria-controls', drawer.id); button.setAttribute('aria-expanded', 'false'); });
  }
  const drawerFocusables = () => drawer ? [...drawer.querySelectorAll('a[href],button:not([disabled]),summary,input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])')].filter(item => !item.hidden) : [];
  const setDrawer = open => {
    document.body.classList.toggle('cadu-sidebar-drawer-open', open);
    mobileToggles.forEach(button => button.setAttribute('aria-expanded', String(open)));
    if (drawer) {
      const hiddenMobileDrawer = !desktop() && !open;
      drawer.toggleAttribute('inert', hiddenMobileDrawer);
      if (hiddenMobileDrawer) drawer.setAttribute('aria-hidden', 'true');
      else drawer.removeAttribute('aria-hidden');
    }
    obscuredWhileOpen.forEach(region => {
      if (region.contains(drawer)) return;
      region.toggleAttribute('inert', open);
      if (open) region.setAttribute('aria-hidden', 'true');
      else region.removeAttribute('aria-hidden');
    });
    if (open) requestAnimationFrame(() => (drawerFocusables()[0] || drawer)?.focus());
    else if (lastTrigger) { lastTrigger.focus(); lastTrigger = null; }
  };
  const setState = collapsed => {
    root.dataset.caduSidebar = collapsed && desktop() ? 'collapsed' : 'expanded';
    document.querySelectorAll('[data-cadu-sidebar-toggle]').forEach(button => {
      button.setAttribute('aria-expanded', String(!collapsed));
      button.setAttribute('aria-label', collapsed ? 'Expandir navegação' : 'Recolher navegação');
    });
  };
  try { setState(localStorage.getItem(key) === 'collapsed'); } catch (_) { setState(false); }
  setDrawer(false);
  const closePanels = except => document.querySelectorAll('.cadu-app-sidebar details,.workspace-app-sidebar details,.reports-app-sidebar details,.connect-entry-sidebar details,.family-modules details').forEach(panel => { if (panel !== except) panel.open = false; });
  document.addEventListener('click', event => {
    const toggle = event.target.closest('[data-cadu-sidebar-toggle]');
    if (toggle) { const next = root.dataset.caduSidebar !== 'collapsed'; setState(next); try { localStorage.setItem(key, next ? 'collapsed' : 'expanded'); } catch (_) {} return; }
    const mobileToggle = event.target.closest('[data-cadu-sidebar-mobile-toggle]');
    if (mobileToggle) { lastTrigger = mobileToggle; setDrawer(!document.body.classList.contains('cadu-sidebar-drawer-open')); return; }
    if (event.target.closest('[data-cadu-sidebar-mobile-close]')) { setDrawer(false); return; }
    const panel = event.target.closest('.cadu-app-sidebar details,.workspace-app-sidebar details,.reports-app-sidebar details,.connect-entry-sidebar details,.family-modules details');
    if (panel) { closePanels(panel); } else { closePanels(); }
    if (event.target.closest('[data-cadu-sidebar-overlay]') || event.target.closest('.cadu-app-sidebar a,.workspace-app-sidebar a,.reports-app-sidebar a,.connect-entry-sidebar a,.family-modules a')) setDrawer(false);
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') { closePanels(); setDrawer(false); return; }
    if (event.key !== 'Tab' || !document.body.classList.contains('cadu-sidebar-drawer-open')) return;
    const items = drawerFocusables(); if (!items.length) return;
    const first = items[0], last = items[items.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  });
  window.addEventListener('resize', () => { if (desktop()) setDrawer(false); });
})();
