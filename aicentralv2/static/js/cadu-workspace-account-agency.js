(() => {
  'use strict';
  const bind = (selector, dialogSelector) => {
    const button = document.querySelector(selector);
    const dialog = document.querySelector(dialogSelector);
    if (!button || !dialog) return;
    button.addEventListener('click', () => dialog.showModal());
    dialog.querySelectorAll('[data-dialog-close]').forEach(close => close.addEventListener('click', () => dialog.close()));
    dialog.addEventListener('click', event => { if (event.target === dialog) dialog.close(); });
  };
  bind('[data-team-invite]', '[data-invite-dialog]');
  bind('[data-team-details]', '[data-details-dialog]');
  const confirm = document.createElement('dialog');
  confirm.className = 'account-dialog account-dialog--confirm';
  confirm.innerHTML = '<form method="dialog"><header><div><span>Confirmar ação</span><h2></h2><p>Esta ação altera o acesso da equipe.</p></div><button aria-label="Fechar">×</button></header><footer><button>Voltar</button><button class="primary" value="confirm">Confirmar</button></footer></form>';
  document.body.append(confirm);
  const protect = (form, label) => form.addEventListener('submit', event => {
    event.preventDefault(); confirm.querySelector('h2').textContent = `${label}?`; confirm.showModal();
    confirm.addEventListener('close', function proceed() { if (confirm.returnValue === 'confirm') form.submit(); confirm.removeEventListener('close', proceed); }, {once: true});
  });
  document.querySelectorAll('[data-team-sensitive]').forEach(form => {
    protect(form, `${form.dataset.teamAction} ${form.dataset.teamName}`);
  });
  confirm.addEventListener('click', event => { if (event.target === confirm) confirm.close(); });
})();
