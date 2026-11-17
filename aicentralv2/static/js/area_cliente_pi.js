/* Hub de mídia: enviar PI (arrastar e soltar) e acompanhar a leitura. */
(function () {
  'use strict';
  var raiz = document.querySelector('[data-pe]');
  if (!raiz) return;
  function $(s) { return raiz.querySelector(s); }
  function erro(texto) { var el = $('#pe-erro'); if (!el) return; el.textContent = texto || ''; el.hidden = !texto; }

  if (raiz.dataset.pe === 'enviar') {
    var zona = $('#pe-drop'), entrada = $('#pe-arquivo'), prog = $('#pe-progresso'), progTexto = $('#pe-progresso-texto');
    if (zona.classList.contains('is-off')) return;
    var enviar = function (arquivos) {
      arquivos = Array.prototype.slice.call(arquivos || []);
      if (!arquivos.length) return;
      erro('');
      var dados = new FormData();
      dados.append('csrf', raiz.dataset.csrf);
      arquivos.forEach(function (a) { dados.append('arquivos', a); });
      prog.hidden = false; zona.classList.add('is-enviando');
      progTexto.textContent = arquivos.length === 1 ? 'Enviando o PDF…' : 'Enviando ' + arquivos.length + ' PDFs…';
      fetch(raiz.dataset.uploadUrl, { method: 'POST', credentials: 'same-origin', body: dados })
        .then(function (r) { return r.json().catch(function () { return { ok: false, erro: 'Resposta inesperada. Tente novamente.' }; }); })
        .then(function (res) {
          if (!res.ok) throw new Error(res.erro || 'Não foi possível enviar o arquivo.');
          var boas = res.entradas.filter(function (e) { return e.url; });
          var ruins = res.entradas.filter(function (e) { return e.erro; });
          if (ruins.length) erro(ruins.map(function (e) { return e.nome + ': ' + e.erro; }).join(' · '));
          if (boas.length === 1 && !ruins.length) { window.location.href = boas[0].url; return; }
          if (boas.length) setTimeout(function () { window.location.reload(); }, ruins.length ? 2500 : 300);
        })
        .catch(function (e) { erro(e.message); })
        .then(function () { prog.hidden = true; zona.classList.remove('is-enviando'); });
    };
    $('#pe-escolher').addEventListener('click', function () { entrada.click(); });
    entrada.addEventListener('change', function () { enviar(entrada.files); entrada.value = ''; });
    zona.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); entrada.click(); } });
    ['dragenter', 'dragover'].forEach(function (n) { zona.addEventListener(n, function (e) { e.preventDefault(); zona.classList.add('is-sobre'); }); });
    ['dragleave', 'drop'].forEach(function (n) { zona.addEventListener(n, function (e) { e.preventDefault(); zona.classList.remove('is-sobre'); }); });
    zona.addEventListener('drop', function (e) { enviar(e.dataTransfer && e.dataTransfer.files); });
    return;
  }

  if (raiz.dataset.pe === 'enviado' && raiz.dataset.estado === 'lendo') {
    var tentativas = 0;
    var timer = setInterval(function () {
      tentativas += 1;
      fetch(raiz.dataset.statusUrl, { credentials: 'same-origin' }).then(function (r) { return r.json(); })
        .then(function (r) { if ((r.ok && r.pronto) || tentativas > 90) { clearInterval(timer); window.location.reload(); } })
        .catch(function () {});
    }, 2500);
  }
})();
