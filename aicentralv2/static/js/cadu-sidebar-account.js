/* Keeps the server-rendered sidebar footer's credit usage in step with the React sidebars. */
(function () {
  var link = document.querySelector('.cadu-sidebar-account__usage');
  if (!link) return;
  function refresh() {
    fetch('/workspace/api/creditos/resumo', {credentials: 'same-origin', headers: {Accept: 'application/json'}})
      .then(function (r) { return r.ok ? r.json() : Promise.reject(); })
      .then(function (data) {
        var value = Number(data.monthly_usage_percentage);
        if (!isFinite(value)) return;
        value = Math.max(0, Math.min(100, value));
        var label = new Intl.NumberFormat('pt-BR', {maximumFractionDigits: 1}).format(value) + '%';
        link.querySelector('span').textContent = label;
        link.querySelector('b').style.width = value + '%';
        link.classList.toggle('is-high', value >= 80);
        link.setAttribute('aria-label', 'Créditos: ' + label + ' usados no mês');
      })
      .catch(function () {});
  }
  refresh();
  setInterval(refresh, 60000);
})();
