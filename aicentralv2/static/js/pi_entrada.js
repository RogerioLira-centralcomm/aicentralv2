/* Entrada de PI automática (CentralX): fila com arrastar e soltar, e página de verificação com ajustes justificados. */
(function () {
  'use strict';
  var raiz = document.querySelector('[data-pie]');
  if (!raiz) return;

  function $(sel, ctx) { return (ctx || document).querySelector(sel); }
  function $$(sel, ctx) { return Array.prototype.slice.call((ctx || document).querySelectorAll(sel)); }
  function mostrarErro(el, texto) { if (!el) return; el.textContent = texto || ''; el.hidden = !texto; }
  function postJson(url, corpo) {
    return fetch(url, { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' }, body: JSON.stringify(corpo) })
      .then(function (r) { return r.json().catch(function () { return { ok: false, erro: 'Resposta inesperada do servidor.' }; }); });
  }

  /* ---------- fila ---------- */
  if (raiz.dataset.pie === 'fila') {
    var zona = $('#pie-drop'), entrada = $('#pie-arquivo'), prog = $('#pie-progresso'), progTexto = $('#pie-progresso-texto'), erro = $('#pie-erro');
    var enviar = function (arquivos) {
      arquivos = Array.prototype.slice.call(arquivos || []);
      if (!arquivos.length) return;
      mostrarErro(erro, '');
      var dados = new FormData();
      arquivos.forEach(function (a) { dados.append('arquivos', a); });
      prog.hidden = false; zona.classList.add('is-enviando');
      progTexto.textContent = arquivos.length === 1 ? 'Enviando o PDF…' : 'Enviando ' + arquivos.length + ' PDFs…';
      fetch(raiz.dataset.uploadUrl, { method: 'POST', credentials: 'same-origin', body: dados })
        .then(function (r) { return r.json().catch(function () { return { ok: false, erro: 'Resposta inesperada do servidor.' }; }); })
        .then(function (res) {
          if (!res.ok) throw new Error(res.erro || 'Não consegui enviar.');
          var boas = res.entradas.filter(function (e) { return e.url; });
          var ruins = res.entradas.filter(function (e) { return e.erro; });
          if (ruins.length) mostrarErro(erro, ruins.map(function (e) { return e.nome + ': ' + e.erro; }).join(' · '));
          if (boas.length === 1 && !ruins.length) { window.location.href = boas[0].url; return; }
          if (boas.length) { setTimeout(function () { window.location.reload(); }, ruins.length ? 2500 : 300); }
        })
        .catch(function (e) { mostrarErro(erro, e.message); })
        .then(function () { prog.hidden = true; zona.classList.remove('is-enviando'); });
    };
    $('#pie-escolher').addEventListener('click', function () { entrada.click(); });
    entrada.addEventListener('change', function () { enviar(entrada.files); entrada.value = ''; });
    zona.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); entrada.click(); } });
    ['dragenter', 'dragover'].forEach(function (nome) {
      zona.addEventListener(nome, function (e) { e.preventDefault(); zona.classList.add('is-sobre'); });
    });
    ['dragleave', 'drop'].forEach(function (nome) {
      zona.addEventListener(nome, function (e) { e.preventDefault(); zona.classList.remove('is-sobre'); });
    });
    zona.addEventListener('drop', function (e) { enviar(e.dataTransfer && e.dataTransfer.files); });
    /* entradas que ainda estão sendo lidas: confere a cada 3 s e recarrega quando terminar */
    var lendo = $$('tr[data-status="lendo"], tr[data-status="recebido"]');
    if (lendo.length) {
      var tentativas = 0;
      var timer = setInterval(function () {
        tentativas += 1;
        Promise.all(lendo.map(function (tr) { return fetch('/pi-entrada/' + tr.dataset.id + '/status', { credentials: 'same-origin' }).then(function (r) { return r.json(); }); }))
          .then(function (rs) { if (rs.some(function (r) { return r.ok && r.pronto; }) || tentativas > 60) { clearInterval(timer); window.location.reload(); } })
          .catch(function () {});
      }, 3000);
    }
    return;
  }

  /* ---------- verificação ---------- */
  var painel = $('#pie-pdf'), iframe = painel && $('iframe', painel);
  var botaoPdf = $('#pie-ver-pdf');
  if (botaoPdf) {
    botaoPdf.addEventListener('click', function () {
      if (!iframe.src) iframe.src = iframe.dataset.src;
      painel.hidden = !painel.hidden;
      botaoPdf.setAttribute('aria-expanded', String(!painel.hidden));
    });
    $('#pie-fechar-pdf').addEventListener('click', function () { painel.hidden = true; botaoPdf.setAttribute('aria-expanded', 'false'); });
  }

  if (raiz.dataset.carregando === '1') {
    var tent = 0;
    var t = setInterval(function () {
      tent += 1;
      fetch(raiz.dataset.statusUrl, { credentials: 'same-origin' }).then(function (r) { return r.json(); })
        .then(function (r) { if ((r.ok && r.pronto) || tent > 90) { clearInterval(t); window.location.reload(); } })
        .catch(function () {});
    }, 2500);
    return;
  }

  var msg = $('#pie-msg'), salvar = $('#pie-salvar'), aprovar = $('#pie-aprovar'), contador = $('#pie-edicoes'), contadorN = $('#pie-edicoes-n');
  var sujos = {};   // grupo -> [{campo, valor}]

  function atualizarSujos() {
    var grupos = Object.keys(sujos).filter(function (g) { return sujos[g].length; });
    var total = grupos.reduce(function (n, g) { return n + sujos[g].length; }, 0);
    contador.hidden = total === 0; contadorN.textContent = total; salvar.disabled = total === 0;
    if (aprovar) aprovar.disabled = total > 0 || aprovar.dataset.bloqueado === '1';
    $$('.pie-ajuste').forEach(function (tr) { tr.hidden = !(sujos[tr.dataset.ajusteDe] && sujos[tr.dataset.ajusteDe].length); });
  }
  if (aprovar && aprovar.disabled) aprovar.dataset.bloqueado = '1';

  $$('.pie-edit').forEach(function (campo) {
    campo.addEventListener('input', function () {
      var g = campo.dataset.grupo;
      var lista = (sujos[g] || []).filter(function (x) { return x.campo !== campo.dataset.caminho; });
      if (campo.value.trim() !== campo.dataset.original.trim()) lista.push({ campo: campo.dataset.caminho, valor: campo.value, el: campo });
      sujos[g] = lista;
      campo.classList.toggle('is-sujo', campo.value.trim() !== campo.dataset.original.trim());
      atualizarSujos();
    });
  });

  function lerJustificativa(container) {
    var motivo = $('.pie-motivo', container), texto = $('.pie-just', container);
    return { motivo: motivo ? motivo.value : '', justificativa: texto ? texto.value.trim() : '', texto: texto };
  }

  if (salvar) {
    salvar.addEventListener('click', function () {
      mostrarErro(msg, '');
      var itens = [], faltou = null;
      Object.keys(sujos).forEach(function (g) {
        if (!sujos[g].length) return;
        var form = $('.pie-ajuste[data-ajuste-de="' + g + '"]');
        var j = lerJustificativa(form);
        if (!j.motivo || j.justificativa.length < 5) { faltou = faltou || form; return; }
        sujos[g].forEach(function (x) { itens.push({ campo: x.campo, tipo: 'ajuste', valor: x.valor, motivo: j.motivo, justificativa: j.justificativa }); });
      });
      if (faltou) { mostrarErro(msg, 'Escolha o motivo e escreva a justificativa de cada campo editado.'); faltou.scrollIntoView({ block: 'center', behavior: 'smooth' }); return; }
      salvar.disabled = true;
      postJson(raiz.dataset.ajustesUrl, { itens: itens }).then(function (r) {
        if (!r.ok) { mostrarErro(msg, r.erro || 'Não consegui salvar.'); salvar.disabled = false; return; }
        window.location.reload();
      }).catch(function () { mostrarErro(msg, 'Sem conexão. Tente de novo.'); salvar.disabled = false; });
    });
  }

  $$('[data-acao="aceitar"]').forEach(function (botao) {
    botao.addEventListener('click', function () {
      var cartao = botao.closest('.pie-pend'), j = lerJustificativa(cartao);
      mostrarErro(msg, '');
      if (!j.motivo || j.justificativa.length < 5) { mostrarErro(msg, 'Escolha o motivo e escreva a justificativa.'); cartao.scrollIntoView({ block: 'center', behavior: 'smooth' }); return; }
      botao.disabled = true;
      postJson(raiz.dataset.ajustesUrl, { itens: [{ campo: cartao.dataset.campo, tipo: 'aceite', motivo: j.motivo, justificativa: j.justificativa, referencia: cartao.dataset.referencia }] })
        .then(function (r) { if (!r.ok) { mostrarErro(msg, r.erro || 'Não consegui registrar.'); botao.disabled = false; return; } window.location.reload(); })
        .catch(function () { mostrarErro(msg, 'Sem conexão. Tente de novo.'); botao.disabled = false; });
    });
  });
})();
