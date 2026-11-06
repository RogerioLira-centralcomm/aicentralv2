/* Ficha da estratégia: simulador de verba e praças. O servidor calcula e devolve o
   fragmento pronto (_estrategia_simulacao.html); aqui só guardamos a escolha, trocamos o
   fragmento, a URL e os campos que vão para o briefing. */
(function () {
  'use strict';
  var box = document.querySelector('[data-es-simulador]');
  if (!box) return;
  var area = box.querySelector('[data-es-sim-area]');
  var chips = box.querySelector('[data-es-chips]');
  var busca = box.querySelector('[data-es-praca-busca]');
  var itens = JSON.parse(document.getElementById('es-pracas-json').textContent);
  var porId = {}, porNome = {};
  itens.forEach(function (p) { porId[p.id] = p; porNome[p.nome.toLowerCase()] = p; });
  var sim = area.querySelector('.es-sim');
  var estado = {
    verba: Number(sim.dataset.esSimVerbaAtual),
    pracas: (sim.dataset.esSimIds || '').split(',').filter(Boolean)
  };
  var seq = 0;

  function esc(t) { return String(t).replace(/[&<>"]/g, function (c) { return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]; }); }
  function pessoas(n) { return n >= 1e6 ? (n / 1e6).toFixed(1).replace('.', ',') + ' mi' : Math.round(n / 1e3) + ' mil'; }

  function desenharChips() {
    if (!estado.pracas.length) {
      chips.innerHTML = '<li class="es-chip-praca is-br">Brasil inteiro</li>';
      return;
    }
    chips.innerHTML = estado.pracas.map(function (id) {
      var p = porId[id]; if (!p) return '';
      return '<li class="es-chip-praca es-chip-praca--' + p.tipo + '"><span>' + esc(p.nome) + '</span><small>' + pessoas(p.pop) + '</small>' +
        '<button type="button" data-es-tirar="' + esc(id) + '" aria-label="Tirar ' + esc(p.nome) + '">×</button></li>';
    }).join('');
  }

  function atualizar() {
    var n = ++seq;
    var qs = 'verba=' + estado.verba + (estado.pracas.length ? '&pracas=' + encodeURIComponent(estado.pracas.join(',')) : '');
    box.querySelectorAll('[data-es-tier]').forEach(function (t) {
      var on = Number(t.dataset.esTier) === estado.verba;
      t.classList.toggle('is-on', on);
      if (on) t.setAttribute('aria-current', 'true'); else t.removeAttribute('aria-current');
    });
    document.querySelectorAll('[data-es-sim-verba]').forEach(function (i) { i.value = estado.verba; });
    document.querySelectorAll('[data-es-sim-pracas]').forEach(function (i) { i.value = estado.pracas.join(','); });
    desenharChips();
    area.classList.add('is-loading');
    fetch(box.dataset.url + '?' + qs, {credentials: 'same-origin'})
      .then(function (r) { if (!r.ok) throw new Error(); return r.text(); })
      .then(function (html) {
        if (n !== seq) return;
        area.innerHTML = html;
        try { history.replaceState(null, '', location.pathname + '?' + qs + '#verba'); } catch (e) {}
      })
      .catch(function () {})
      .then(function () { if (n === seq) area.classList.remove('is-loading'); });
  }

  box.addEventListener('click', function (ev) {
    var t = ev.target.closest('[data-es-tier]');
    if (t) {
      ev.preventDefault();
      if (t.getAttribute('aria-disabled') === 'true') return;
      estado.verba = Number(t.dataset.esTier); atualizar(); return;
    }
    var x = ev.target.closest('[data-es-tirar]');
    if (x) { estado.pracas = estado.pracas.filter(function (id) { return id !== x.dataset.esTirar; }); atualizar(); return; }
    var pr = ev.target.closest('[data-es-preset]');
    if (pr) {
      var ids = pr.dataset.esPreset.split(',').filter(Boolean);
      estado.pracas = ids.length === 1 && ids[0] === 'BR' ? [] : ids;
      atualizar();
    }
  });

  function escolher() {
    var p = porNome[(busca.value || '').trim().toLowerCase()];
    if (!p) return;
    busca.value = '';
    if (p.id === 'BR') estado.pracas = [];
    else if (estado.pracas.indexOf(p.id) < 0) estado.pracas.push(p.id);
    atualizar();
  }
  busca.addEventListener('change', escolher);
  busca.addEventListener('input', function () { if (porNome[(busca.value || '').trim().toLowerCase()]) escolher(); });
  busca.addEventListener('keydown', function (ev) { if (ev.key === 'Enter') { ev.preventDefault(); escolher(); } });

  desenharChips();
})();
