/* Área do Cliente: tela de carregamento com barra de progresso de 3 s.
   Telas de acesso: sempre que abrem. Shell logado: uma vez por sessão (data-once="1"). */
(function () {
  var el = document.getElementById('ac-splash');
  if (!el) return;
  if (el.getAttribute('data-once') === '1') {
    var visto = false;
    try { visto = sessionStorage.getItem('ac-splash') === '1'; sessionStorage.setItem('ac-splash', '1'); } catch (e) {}
    if (visto) { el.remove(); return; }
  }
  var fill = el.querySelector('.ac-splash__fill');
  var reduz = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var dur = reduz ? 1 : 3000, t0 = null;
  el.classList.add('has-js');
  function passo(t) {
    if (t0 === null) t0 = t;
    var p = Math.min(1, (t - t0) / dur);
    var suave = 1 - Math.pow(1 - p, 2.2); /* começa rápido, desacelera no fim */
    if (fill) fill.style.transform = 'scaleX(' + suave.toFixed(4) + ')';
    if (p < 1) { requestAnimationFrame(passo); }
    else { el.classList.add('is-done'); setTimeout(function () { el.remove(); }, 500); }
  }
  requestAnimationFrame(passo);
})();
