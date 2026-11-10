/* Painel lateral de detalhe (campanha ou PI) da Área do Cliente.
   Dados em #ac-painel-dados (lista); cada [data-painel="i"] abre o item i. Tudo com
   textContent (nada de HTML vindo dos dados). Anel, barras e números animam ao abrir;
   com prefers-reduced-motion, aparecem direto no valor final. */
(function () {
  'use strict';
  var fonte = document.getElementById('ac-painel-dados');
  var painel = document.getElementById('ac-painel');
  if (!fonte || !painel) return;
  var dados = [];
  try { dados = JSON.parse(fonte.textContent || '[]'); } catch (e) { return; }
  var scrim = document.querySelector('[data-painel-fechar].ac-drawer-scrim');
  var icones = document.getElementById('ac-painel-icones');
  var quieto = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var origem = null, quadros = [];
  var RITMOS = { adiantado: ['success', 'Adiantada'], no_ritmo: ['brand', 'No ritmo'], atencao: ['warning', 'Em otimização'] };
  var brl = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 });
  var inteiro = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 0 });

  function $(sel) { return painel.querySelector(sel); }
  function el(tag, cls, texto) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (texto != null) n.textContent = texto;
    return n;
  }
  function icone(nome) {
    var s = icones && icones.content.querySelector('[data-i="' + nome + '"] svg');
    return s ? s.cloneNode(true) : null;
  }
  function limita(v) { return Math.max(0, Math.min(100, Number(v) || 0)); }
  function formata(v, formato) {
    if (formato === 'brl') return brl.format(v);
    if (formato === 'pct') return inteiro.format(v) + '%';
    return inteiro.format(v);
  }
  function parar() { quadros.forEach(cancelAnimationFrame); quadros = []; }
  function conta(no, alvo, formato, ms) {
    if (quieto || !isFinite(alvo)) { no.textContent = formata(alvo, formato); return; }
    var t0 = null;
    function passo(t) {
      if (t0 === null) t0 = t;
      var k = Math.min(1, (t - t0) / ms), suave = 1 - Math.pow(1 - k, 3);
      no.textContent = formata(alvo * suave, formato);
      if (k < 1) quadros.push(requestAnimationFrame(passo));
    }
    no.textContent = formata(0, formato);
    quadros.push(requestAnimationFrame(passo));
  }
  function arco(circ, pct) {
    var r = Number(circ.getAttribute('r')), total = 2 * Math.PI * r;
    circ.style.strokeDasharray = total.toFixed(2);
    circ.style.transition = 'none';
    circ.style.strokeDashoffset = total.toFixed(2);
    circ.getBoundingClientRect();                     // força o estado inicial antes da transição
    circ.style.transition = quieto ? 'none' : '';
    circ.style.strokeDashoffset = (total * (1 - limita(pct) / 100)).toFixed(2);
  }
  function texto(chave, valor) {
    painel.querySelectorAll('[data-p="' + chave + '"]').forEach(function (n) { n.textContent = valor || ''; });
  }
  function mostra(chave, sim) {
    painel.querySelectorAll('[data-p-se="' + chave + '"]').forEach(function (n) { n.hidden = !sim; });
  }

  function preencher(d) {
    parar();
    painel.dataset.tipo = d.tipo || '';
    texto('eyebrow', d.eyebrow); texto('titulo', d.titulo); texto('sub', d.sub);
    var logo = $('[data-p-logo]');
    logo.hidden = !d.logo;
    if (d.logo) logo.querySelector('img').src = d.logo;

    // Anel: entrega (grosso) e tempo decorrido (fino).
    var temPct = typeof d.pct === 'number', temTempo = typeof d.tempo === 'number';
    $('[data-p-hero]').hidden = !temPct;
    if (temPct) {
      var cor = (RITMOS[d.ritmo] || [])[0] || (d.pct >= 100 ? 'success' : 'brand');
      painel.dataset.cor = cor;
      arco($('[data-p-arco="entrega"]'), d.pct);
      arco($('[data-p-arco="tempo"]'), temTempo ? d.tempo : 0);
      $('[data-p-anel]').setAttribute('aria-label', 'Entrega ' + Math.round(d.pct) + '%' + (temTempo ? ', tempo decorrido ' + Math.round(d.tempo) + '%' : ''));
      conta($('[data-p-pct]'), d.pct, 'pct', 900);
      texto('pct_txt', formata(d.pct, 'pct'));
      texto('tempo_txt', temTempo ? formata(d.tempo, 'pct') : '');
      mostra('tempo', temTempo);
      var r = RITMOS[d.ritmo];
      mostra('ritmo_txt', !!r);
      if (r) {
        var badge = $('[data-p-ritmo]');
        badge.className = 'ac-badge ac-badge--ritmo ac-badge--' + r[0];
        badge.textContent = d.ritmo_txt || r[1];
        texto('dif_txt', typeof d.dif === 'number' ? (d.dif > 0 ? '+' : '') + Math.round(d.dif) + ' p.p. da meta do período' : '');
      }
    }

    // Números (contam até o valor).
    var nums = $('[data-p-nums]');
    nums.textContent = '';
    (d.nums || []).forEach(function (n, i) {
      var card = el('div', 'ac-painel__num');
      card.style.setProperty('--i', i);
      card.appendChild(el('span', null, n.rotulo));
      var b = el('b');
      card.appendChild(b);
      if (typeof n.valor === 'number') conta(b, n.valor, n.formato, 700 + i * 120); else b.textContent = n.texto || '—';
      if (n.nota) card.appendChild(el('small', null, n.nota));
      nums.appendChild(card);
    });
    nums.hidden = !(d.nums || []).length;

    // Barras (por campanha no PI; entrega x tempo na campanha). Clique leva ao destino, se houver.
    var lista = $('[data-p-barras]');
    lista.textContent = '';
    (d.barras || []).forEach(function (b, i) {
      var li = el('li', 'ac-painel__barra');
      li.style.setProperty('--i', i);
      var alvo = b.href ? el('a') : el('div');
      if (b.href) alvo.href = b.href;
      var topo = el('span', 'ac-painel__barra-topo');
      topo.appendChild(el('span', null, b.rotulo));
      topo.appendChild(el('b', null, typeof b.pct === 'number' ? formata(b.pct, 'pct') : '—'));
      alvo.appendChild(topo);
      var trilho = el('span', 'ac-painel__trilho');
      var fill = el('span', 'ac-painel__fill' + (b.ritmo ? ' is-' + b.ritmo : ''));
      trilho.appendChild(fill);
      if (typeof b.marca === 'number') { var m = el('span', 'ac-painel__marca'); m.style.left = limita(b.marca) + '%'; trilho.appendChild(m); }
      alvo.appendChild(trilho);
      li.appendChild(alvo);
      lista.appendChild(li);
      fill.style.width = '0%';
      requestAnimationFrame(function () { requestAnimationFrame(function () { fill.style.width = limita(b.pct) + '%'; }); });
    });
    texto('barras_titulo', d.barras_titulo || '');
    mostra('barras', !!(d.barras || []).length);

    // Definições.
    var defs = $('[data-p-defs]');
    defs.textContent = '';
    (d.defs || []).forEach(function (x) {
      var linha = el('div');
      linha.appendChild(el('dt', null, x.rotulo));
      var dd = el('dd');
      if (x.href) { var a = el('a', 'ac-link', x.valor); a.href = x.href; dd.appendChild(a); } else dd.textContent = x.valor || '—';
      linha.appendChild(dd);
      defs.appendChild(linha);
    });

    // Ações: primária em largura toda; as demais lado a lado.
    var acoes = $('[data-p-acoes]');
    acoes.textContent = '';
    (d.acoes || []).forEach(function (a) {
      var bt = el('a', 'ac-btn ac-btn--sm ' + (a.primario ? 'ac-btn--primary ac-painel__principal' : 'ac-btn--secondary'));
      bt.href = a.href;
      if (a.externo) { bt.target = '_blank'; bt.rel = 'noopener'; }
      var ic = a.icone && icone(a.icone);
      if (ic) bt.appendChild(ic);
      bt.appendChild(el('span', null, a.rotulo));
      if (a.externo) { var ex = icone('external'); if (ex) bt.appendChild(ex); }
      acoes.appendChild(bt);
    });
    acoes.hidden = !(d.acoes || []).length;
  }

  function abrir(i, botao) {
    var d = dados[i];
    if (!d) return;
    origem = botao;
    painel.hidden = false;
    if (scrim) scrim.hidden = false;
    document.documentElement.classList.add('ac-painel-aberto');
    preencher(d);
    painel.classList.remove('is-entrando');
    void painel.offsetWidth;
    painel.classList.add('is-entrando');
    document.querySelectorAll('[data-painel-linha]').forEach(function (tr) {
      tr.classList.toggle('is-selected', tr.getAttribute('data-painel-linha') === String(i));
    });
    var fechar = painel.querySelector('[data-painel-fechar]');
    if (fechar) fechar.focus();
  }
  function fechar() {
    parar();
    painel.hidden = true;
    if (scrim) scrim.hidden = true;
    document.documentElement.classList.remove('ac-painel-aberto');
    document.querySelectorAll('[data-painel-linha].is-selected').forEach(function (tr) { tr.classList.remove('is-selected'); });
    if (origem) origem.focus();
  }

  document.addEventListener('click', function (ev) {
    var b = ev.target.closest('[data-painel]');
    if (b) { ev.preventDefault(); abrir(Number(b.getAttribute('data-painel')), b); return; }
    if (ev.target.closest('[data-painel-fechar]')) fechar();
  });
  document.addEventListener('keydown', function (ev) {
    if (painel.hidden) return;
    if (ev.key === 'Escape') { fechar(); return; }
    if (ev.key === 'Tab') {                           // foco preso no painel enquanto aberto
      var foco = painel.querySelectorAll('a[href], button:not([disabled])');
      if (!foco.length) return;
      var primeiro = foco[0], ultimo = foco[foco.length - 1];
      if (ev.shiftKey && document.activeElement === primeiro) { ev.preventDefault(); ultimo.focus(); }
      else if (!ev.shiftKey && document.activeElement === ultimo) { ev.preventDefault(); primeiro.focus(); }
    }
  });
})();
