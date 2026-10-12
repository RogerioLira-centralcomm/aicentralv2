(function () {
  var gate = document.querySelector('.cadu-mobile-gate');
  if (!gate) return;
  var url = window.location.origin + window.location.pathname;
  var mail = gate.querySelector('[data-gate-mail]');
  var copy = gate.querySelector('[data-gate-copy]');
  var status = gate.querySelector('.cadu-mobile-gate__status');
  if (mail) mail.href = 'mailto:?subject=' + encodeURIComponent('Abrir o Cadu Studio no computador') + '&body=' + encodeURIComponent('Abra este link no computador para usar o Cadu Studio:\n' + url);
  if (copy) copy.addEventListener('click', function () {
    var done = function (ok) { if (status) status.textContent = ok ? 'Link copiado.' : 'Não foi possível copiar. Use o envio por e-mail.'; };
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(url).then(function () { done(true); }, function () { done(false); });
    else done(false);
  });
})();
