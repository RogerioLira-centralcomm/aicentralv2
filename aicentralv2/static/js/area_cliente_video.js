/* Cartão flutuante do Início: convida para o vídeo de visão geral depois de 5 segundos.
 * Quem dispensa, ou abre o vídeo, não vê de novo por 14 dias (guardado só neste navegador). */
(function () {
  'use strict';
  var card = document.getElementById('ac-vcard');
  if (!card) return;
  var CHAVE = 'ac-vcard', DIAS = 14;
  function visto() {
    try { var t = +localStorage.getItem(CHAVE); return t && Date.now() - t < DIAS * 864e5; } catch (e) { return false; }
  }
  function marcar() { try { localStorage.setItem(CHAVE, String(Date.now())); } catch (e) { /* sem storage */ } }
  if (visto()) return;
  var espera = +card.dataset.delay || 5000;
  setTimeout(function () { card.hidden = false; requestAnimationFrame(function () { card.classList.add('is-on'); }); }, espera);
  document.getElementById('ac-vcard-x').addEventListener('click', function () { marcar(); card.classList.remove('is-on'); setTimeout(function () { card.hidden = true; }, 220); });
  card.addEventListener('click', function (ev) { if (ev.target.closest('a')) marcar(); });
})();
