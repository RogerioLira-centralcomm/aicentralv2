(() => {
  'use strict';
  const stack = document.createElement('div'); stack.className = 'cx-toast-stack';
  document.addEventListener('DOMContentLoaded', () => {
    document.body.append(stack);
    const polish = document.createElement('style');
    polish.textContent = '.portal--connect a:focus-visible,.portal--connect button:focus-visible,.portal--connect input:focus-visible,.portal--connect select:focus-visible,.portal--connect textarea:focus-visible{outline:3px solid #2b7fff;outline-offset:3px}.cr-publish{display:flex;align-items:center;justify-content:space-between;gap:16px;margin:0 0 28px;padding:16px 18px;border:1px solid #d8e6e1;border-radius:12px;background:#fff}.cr-publish>div{display:grid;gap:5px}.cr-publish strong{font-size:13px}.cr-publish small,.cr-publish a{color:#55706e;font-size:12px}.cr-publish a{color:#1363c5;font-weight:700}.cr-publish form{display:flex;gap:8px}.cr-publish select{min-height:36px;border:1px solid #cdded8;border-radius:8px;padding:0 8px;background:#fff}@media(max-width:640px){.cr-publish,.cr-publish form{align-items:stretch;flex-direction:column}}';
    document.head.append(polish);
  });
  window.ConnectUI = {
    toast(message, type = 'info') { const el = document.createElement('div'); el.className = `cx-toast ${type === 'error' ? 'is-error' : ''}`; el.innerHTML = `<span aria-hidden="true">${type === 'error' ? '!' : '✓'}</span><span></span>`; el.lastChild.textContent = message; stack.append(el); setTimeout(() => { el.classList.add('is-leaving'); setTimeout(() => el.remove(), 240); }, 4200); },
    setBusy(button, busy, label) { if (!button) return; if (busy) { button.dataset.cxLabel = button.textContent; button.disabled = true; button.innerHTML = `<span class="cx-loading">${label || 'Processando'}</span>`; } else { button.disabled = false; button.textContent = button.dataset.cxLabel || label; } },
    dialog(id) { document.getElementById(id)?.showModal(); }
  };
  document.addEventListener('click', event => { const opener = event.target.closest('[data-cx-dialog]'); if (opener) { event.preventDefault(); window.ConnectUI.dialog(opener.dataset.cxDialog); } const closer = event.target.closest('[data-cx-close]'); if (closer) closer.closest('dialog')?.close(); });
  document.addEventListener('DOMContentLoaded', () => { const reveal = document.querySelectorAll('[data-cx-reveal]'); if (!('IntersectionObserver' in window)) return reveal.forEach(el => el.classList.add('is-visible')); const observer = new IntersectionObserver(entries => entries.forEach(entry => { if (entry.isIntersecting) { entry.target.classList.add('is-visible'); observer.unobserve(entry.target); } }), {threshold:.08}); reveal.forEach(el => observer.observe(el)); });
})();
