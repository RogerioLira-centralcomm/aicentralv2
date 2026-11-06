/* Editor de estratégias de mídia (Parâmetros > Estratégias).
   O estado inteiro vive em `est`; cada campo tem data-bind="caminho" e o tipo em data-tipo.
   Mudança estrutural (incluir, tirar, mover) redesenha as seções que dependem dos canais. */
(function () {
  'use strict';
  var raiz = document.querySelector('[data-es-editor]');
  if (!raiz) return;
  var est = JSON.parse(document.getElementById('es-dados').textContent);
  var meta = JSON.parse(document.getElementById('es-meta').textContent);
  var podeSalvar = raiz.dataset.doBanco === '1';
  var porSlug = {};
  meta.canais.forEach(function (c) { porSlug[c.slug] = c; });
  meta.nos.forEach(function (n) { porSlug[n.slug] = {slug: n.slug, nome: n.nome, logo: n.logo || '', no: true}; });

  function $(sel) { return raiz.querySelector(sel); }
  function esc(v) { return String(v == null ? '' : v).replace(/[&<>"']/g, function (c) { return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]; }); }
  function brl(n) { return 'R$ ' + Math.round(n).toLocaleString('pt-BR'); }
  function nomeDe(slug) { return (porSlug[slug] || {}).nome || slug; }
  function logo(slug, tam) {
    var c = porSlug[slug] || {}; tam = tam || 20;
    return c.logo ? '<img class="es-logo" src="' + esc(c.logo) + '" alt="" width="' + tam + '" height="' + tam + '">' :
      '<b class="es-logo es-logo--txt" style="width:' + tam + 'px;height:' + tam + 'px">' + esc(nomeDe(slug).slice(0, 1)) + '</b>';
  }
  function ehNo(slug) { return !!(porSlug[slug] || {}).no; }
  function opts(lista, atual) {
    return lista.map(function (o) { var v = typeof o === 'string' ? o : o[0], r = typeof o === 'string' ? o : o[1];
      return '<option value="' + esc(v) + '"' + (String(v) === String(atual) ? ' selected' : '') + '>' + esc(r) + '</option>'; }).join('');
  }
  function pares(obj) { return Object.keys(obj).map(function (k) { return [k, obj[k]]; }); }
  function campo(rotulo, html, largo) { return '<label class="es-field' + (largo ? ' is-wide' : '') + '"><span>' + rotulo + '</span>' + html + '</label>'; }
  function inp(path, valor, tipo, extra) { return '<input class="cx-input cx-input-sm" data-bind="' + path + '" data-tipo="' + (tipo || 'str') + '" value="' + esc(valor) + '"' + (extra || '') + '>'; }
  function area(path, valor, linhas, tipo) {
    var v = Array.isArray(valor) ? valor.join('\n') : (valor || '');
    return '<textarea class="cx-input es-textarea" rows="' + (linhas || 3) + '" data-bind="' + path + '" data-tipo="' + (tipo || 'str') + '">' + esc(v) + '</textarea>';
  }
  function chk(path, valor, rotulo) { return '<label class="es-check"><input type="checkbox" data-bind="' + path + '" data-tipo="bool"' + (valor ? ' checked' : '') + '> ' + rotulo + '</label>'; }

  function obter(path) { return path.split('.').reduce(function (o, k) { return o == null ? o : o[k]; }, est); }
  function definir(path, valor) {
    var partes = path.split('.'), o = est;
    for (var i = 0; i < partes.length - 1; i++) { if (o[partes[i]] == null) o[partes[i]] = {}; o = o[partes[i]]; }
    o[partes[partes.length - 1]] = valor;
  }
  function ler(el) {
    var t = el.dataset.tipo;
    if (t === 'bool') return el.checked;
    if (t === 'int') return el.value === '' ? null : Number(el.value);
    if (t === 'lines') return el.value.split('\n').map(function (s) { return s.trim(); }).filter(Boolean);
    return el.value;
  }

  // ---------- seções ----------
  function basico() {
    $('[data-es-basico]').innerHTML = [
      campo('Nome', inp('nome', est.nome, 'str', ' maxlength="140" required'), true),
      campo('Slug', inp('slug', est.slug, 'str', ' maxlength="80" pattern="[a-z0-9-]+"')),
      campo('Objetivo', '<select class="cx-select cx-select-sm" data-bind="objetivo" data-tipo="str">' + opts(pares(meta.objetivos), est.objetivo) + '</select>'),
      campo('Verba mínima', '<select class="cx-select cx-select-sm" data-bind="verba_minima" data-tipo="int" data-previa>' +
        opts(meta.faixas.map(function (f) { return [f, brl(f)]; }), est.verba_minima) + '</select>'),
      campo('Ordem', inp('ordem', est.ordem, 'int', ' type="number" min="0" max="10000"')),
      campo('Duração', inp('duracao', est.duracao)),
      campo('Público', inp('publico', est.publico), true),
      campo('Resumo (cartão do Descobrir)', area('resumo', est.resumo, 2), true),
      campo('Descrição', area('descricao', est.descricao, 4), true),
      campo('Cena (prompt das imagens, em inglês)', area('cena', est.cena, 2), true),
      campo('Nota de escala (opcional; a frase automática aparece ao lado)', area('como_escala', est.como_escala, 2), true),
      '<div class="es-field is-wide">' + chk('ativo', est.ativo, 'Ativa no Descobrir') + '</div>'
    ].join('');
  }

  function canais() {
    var html = (est.canais || []).map(function (c, i) {
      var p = 'canais.' + i;
      var cab = '<div class="es-row__head">' + logo(c.slug, 24) + '<strong>' + esc(nomeDe(c.slug)) + '</strong>' +
        (ehNo(c.slug) ? '<span class="es-chip">' + esc(c.papel || 'Destino') + ', sem verba</span>' : '') +
        '<span class="es-row__tools">' + mover('canais', i) + '<button type="button" class="es-icon" data-remover="canais" data-i="' + i + '" title="Tirar"><i class="fa-solid fa-xmark"></i></button></span></div>';
      if (ehNo(c.slug)) return '<div class="es-row es-row--no">' + cab + '</div>';
      return '<div class="es-row">' + cab + '<div class="es-fields es-fields--4">' +
        campo('Papel', '<select class="cx-select cx-select-sm" data-bind="' + p + '.papel" data-tipo="str">' + opts(meta.papeis, c.papel) + '</select>') +
        campo('Peso', inp(p + '.peso', c.peso, 'int', ' type="number" min="0" max="100" data-previa')) +
        campo('Mínimo (R$)', inp(p + '.minimo', c.minimo == null ? '' : c.minimo, 'int', ' type="number" min="0" step="500" placeholder="' + (meta.minimos[c.slug] || 3000) + '" data-previa')) +
        '<div class="es-field">' + chk(p + '.essencial', c.essencial, 'Essencial').replace('data-tipo="bool"', 'data-tipo="bool" data-previa') + '</div>' +
        campo('Formatos (um por linha)', area(p + '.formatos', c.formatos, 3, 'lines'), true) +
        campo('Otimizações do canal (uma por linha)', area(p + '.otimizacoes', c.otimizacoes, 3, 'lines'), true) +
        campo('Nota', inp(p + '.nota', c.nota), true) + '</div></div>';
    }).join('');
    $('[data-es-canais]').innerHTML = html || '<p class="es-hint">Nenhum canal ainda.</p>';
    var usados = (est.canais || []).map(function (c) { return c.slug; });
    var grupos = {};
    meta.canais.forEach(function (c) { if (usados.indexOf(c.slug) < 0) (grupos[c.categoria || 'Outros'] = grupos[c.categoria || 'Outros'] || []).push(c); });
    var sel = '<option value="">Escolha um canal…</option>' + Object.keys(grupos).sort().map(function (g) {
      return '<optgroup label="' + esc(g) + '">' + grupos[g].map(function (c) { return '<option value="' + esc(c.slug) + '">' + esc(c.nome) + '</option>'; }).join('') + '</optgroup>';
    }).join('') + '<optgroup label="Destinos e dados (sem verba)">' + meta.nos.filter(function (n) { return usados.indexOf(n.slug) < 0; })
      .map(function (n) { return '<option value="' + esc(n.slug) + '">' + esc(n.nome) + '</option>'; }).join('') + '</optgroup>';
    $('[data-es-add-canal]').innerHTML = sel;
  }

  function mover(lista, i) {
    return '<button type="button" class="es-icon" data-mover="' + lista + '" data-i="' + i + '" data-d="-1" title="Subir"><i class="fa-solid fa-arrow-up"></i></button>' +
      '<button type="button" class="es-icon" data-mover="' + lista + '" data-i="' + i + '" data-d="1" title="Descer"><i class="fa-solid fa-arrow-down"></i></button>';
  }

  function chipsCanais(path, marcados) {
    return '<div class="es-chips">' + (est.canais || []).map(function (c) {
      var on = (marcados || []).indexOf(c.slug) >= 0;
      return '<button type="button" class="es-chipbtn' + (on ? ' is-on' : '') + '" data-chip="' + path + '" data-slug="' + esc(c.slug) + '" aria-pressed="' + on + '">' + logo(c.slug, 16) + esc(nomeDe(c.slug)) + '</button>';
    }).join('') + '</div>';
  }

  function fluxo() {
    $('[data-es-fluxo]').innerHTML = (est.fluxo || []).map(function (e, i) {
      var p = 'fluxo.' + i;
      return '<div class="es-row"><div class="es-row__head"><span class="es-step">' + (i + 1) + '</span><strong>' + esc(e.titulo || 'Etapa') + '</strong><span class="es-row__tools">' + mover('fluxo', i) +
        '<button type="button" class="es-icon" data-remover="fluxo" data-i="' + i + '" title="Tirar"><i class="fa-solid fa-xmark"></i></button></span></div>' +
        '<div class="es-fields">' + campo('Título', inp(p + '.titulo', e.titulo, 'str', ' maxlength="60"')) + campo('Descrição', inp(p + '.descricao', e.descricao), true) +
        '<div class="es-field is-wide"><span>Canais e nós da etapa</span>' + chipsCanais(p + '.nos', e.nos) + '</div></div></div>';
    }).join('');
  }

  function conversao() {
    var c = est.conversao || {}, r = est.remarketing || {}, l = est.lista_clientes || {};
    $('[data-es-conversao]').innerHTML =
      '<h3 class="es-h3">Conversão</h3><div class="es-fields">' +
      campo('Destino', '<select class="cx-select cx-select-sm" data-bind="conversao.destino" data-tipo="str">' + opts(pares(meta.destinos), c.destino) + '</select>') +
      '<div class="es-field">' + chk('conversao.precisa_link', c.precisa_link, 'Precisa criar link ou landing page') + '</div>' +
      campo('O que o cliente precisa ter', area('conversao.descricao', c.descricao, 2), true) +
      campo('Eventos medidos (um por linha)', area('conversao.eventos', c.eventos, 3, 'lines'), true) + '</div>' +
      '<h3 class="es-h3">Remarketing</h3><div class="es-fields">' +
      '<div class="es-field">' + chk('remarketing.usa', r.usa, 'Usa remarketing') + '</div>' +
      campo('Janela (dias)', inp('remarketing.janela_dias', r.janela_dias, 'int', ' type="number" min="0" max="540"')) +
      campo('Públicos (um por linha)', area('remarketing.publicos', r.publicos, 3, 'lines'), true) +
      campo('Observação', inp('remarketing.descricao', r.descricao), true) + '</div>' +
      '<h3 class="es-h3">Lista de clientes da empresa</h3><div class="es-fields">' +
      '<div class="es-field">' + chk('lista_clientes.usa', l.usa, 'Usa lista de clientes') + '</div>' +
      campo('Usos (um por linha)', area('lista_clientes.usos', l.usos, 3, 'lines'), true) +
      campo('Requisito', area('lista_clientes.requisito', l.requisito, 2), true) + '</div>';
  }

  function criativos() {
    $('[data-es-criativos]').innerHTML = (est.criativos || []).map(function (p, i) {
      var b = 'criativos.' + i;
      return '<div class="es-row"><div class="es-row__head"><strong>' + esc(p.peca || 'Peça') + '</strong><span class="es-row__tools">' + mover('criativos', i) +
        '<button type="button" class="es-icon" data-remover="criativos" data-i="' + i + '" title="Tirar"><i class="fa-solid fa-xmark"></i></button></span></div>' +
        '<div class="es-fields es-fields--4">' + campo('Peça', inp(b + '.peca', p.peca), true) + campo('Quantidade', inp(b + '.quantidade', p.quantidade, 'int', ' type="number" min="1" max="50"')) +
        campo('Especificação', inp(b + '.specs', p.specs), true) + '<div class="es-field is-wide"><span>Onde roda</span>' + chipsCanais(b + '.canais', p.canais) + '</div></div></div>';
    }).join('') || '<p class="es-hint">Nenhuma peça.</p>';
  }

  function kpis() {
    var etapas = (est.fluxo || []).map(function (e) { return e.titulo; });
    $('[data-es-kpis]').innerHTML = (est.kpis || []).map(function (k, i) {
      var b = 'kpis.' + i, lista = etapas.indexOf(k.etapa) < 0 && k.etapa ? etapas.concat([k.etapa]) : etapas;
      return '<div class="es-row es-row--kpi"><div class="es-fields es-fields--kpi">' + campo('Indicador', inp(b + '.nome', k.nome), true) +
        campo('Etapa', '<select class="cx-select cx-select-sm" data-bind="' + b + '.etapa" data-tipo="str"><option value="">—</option>' + opts(lista, k.etapa) + '</select>') +
        campo('Fonte', '<select class="cx-select cx-select-sm" data-bind="' + b + '.fonte" data-tipo="str">' + opts(meta.fontes, k.fonte) + '</select>') +
        '<div class="es-field">' + chk(b + '.principal', k.principal, 'Principal') + '</div>' +
        campo('Como medir', inp(b + '.como', k.como), true) + '</div><span class="es-row__tools">' + mover('kpis', i) +
        '<button type="button" class="es-icon" data-remover="kpis" data-i="' + i + '" title="Tirar"><i class="fa-solid fa-xmark"></i></button></span></div>';
    }).join('') || '<p class="es-hint">Nenhum indicador.</p>';
  }

  function efeitos() {
    $('[data-es-efeitos]').innerHTML = (est.efeitos || []).map(function (ef, i) {
      var b = 'efeitos.' + i;
      return '<div class="es-row"><div class="es-row__head"><span class="es-step">' + (i + 1) + '</span><strong>' + esc(ef.fase || 'Fase') + '</strong><span class="es-row__tools">' + mover('efeitos', i) +
        '<button type="button" class="es-icon" data-remover="efeitos" data-i="' + i + '" title="Tirar"><i class="fa-solid fa-xmark"></i></button></span></div>' +
        '<div class="es-fields">' + campo('Fase', inp(b + '.fase', ef.fase, 'str', ' maxlength="40" placeholder="Semanas 1 e 2"')) +
        campo('O que acontece', area(b + '.texto', ef.texto, 2), true) + '</div></div>';
    }).join('') || '<p class="es-hint">Nenhuma fase.</p>';
  }

  function tudo() { efeitos(); basico(); canais(); fluxo(); conversao(); criativos(); kpis(); $('[data-es-otimizacoes]').value = (est.otimizacoes || []).join('\n'); previa(); }
  function dependentes() { canais(); fluxo(); criativos(); kpis(); previa(); }

  // ---------- prévia da divisão ----------
  var timer = null, seq = 0;
  function previa() {
    clearTimeout(timer);
    timer = setTimeout(function () {
      var n = ++seq;
      fetch('/parametros/api/estrategias/previa', {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({canais: est.canais, verba_minima: est.verba_minima})})
        .then(function (r) { return r.json(); })
        .then(function (d) { if (n === seq && d.success) desenharPrevia(d.data); })
        .catch(function () {});
    }, 250);
  }
  function desenharPrevia(d) {
    var pagos = (est.canais || []).filter(function (c) { return !ehNo(c.slug) && Number(c.peso) > 0; });
    if (pagos.length < 2) { $('[data-es-previa]').innerHTML = '<p class="es-hint">Pelo menos 2 canais com peso.</p>'; $('[data-es-escala]').textContent = ''; return; }
    var cab = '<tr><th>Canal</th>' + d.faixas.map(function (f) { return '<th class="' + (f.disponivel ? '' : 'is-off') + '">' + esc(f.rotulo.replace('R$ ', '')) + '</th>'; }).join('') + '</tr>';
    var linhas = pagos.map(function (c) {
      return '<tr><th>' + logo(c.slug, 16) + '<span>' + esc(nomeDe(c.slug)) + '</span></th>' + d.faixas.map(function (f) {
        var l = f.linhas.filter(function (x) { return x.slug === c.slug; })[0];
        return '<td class="' + (f.disponivel ? '' : 'is-off') + '">' + (l ? (l.valor / 1000).toLocaleString('pt-BR', {maximumFractionDigits: 1}) + 'k' : '·') + '</td>';
      }).join('') + '</tr>';
    }).join('');
    $('[data-es-previa]').innerHTML = '<div class="es-previa-wrap"><table class="es-previa">' + cab + linhas + '</table></div><p class="es-hint">Valores em R$ mil. Colunas apagadas ficam abaixo da verba mínima.</p>';
    $('[data-es-escala]').textContent = d.escala || '';
  }

  // ---------- eventos ----------
  raiz.addEventListener('input', function (ev) {
    var el = ev.target;
    if (!el.dataset.bind) return;
    definir(el.dataset.bind, ler(el));
    if (el.dataset.bind === 'nome') $('[data-es-titulo]').textContent = el.value || 'Nova estratégia';
    if ('previa' in el.dataset) previa();
  });
  raiz.addEventListener('change', function (ev) {
    var el = ev.target;
    if (!el.dataset.bind) return;
    definir(el.dataset.bind, ler(el));
    if ('previa' in el.dataset) previa();
    if (/^fluxo\.\d+\.titulo$/.test(el.dataset.bind)) { fluxo(); kpis(); }
  });
  $('[data-es-otimizacoes]').addEventListener('input', function (ev) {
    est.otimizacoes = ev.target.value.split('\n').map(function (s) { return s.trim(); }).filter(Boolean);
  });
  raiz.addEventListener('click', function (ev) {
    var b = ev.target.closest('button');
    if (!b) return;
    if (b.dataset.remover) {
      var lista = est[b.dataset.remover], tirado = lista.splice(Number(b.dataset.i), 1)[0];
      if (b.dataset.remover === 'canais') limparSlug(tirado.slug);
      if (b.dataset.remover === 'efeitos') efeitos(); else dependentes();
      return;
    }
    if (b.dataset.mover) {
      var l = est[b.dataset.mover], i = Number(b.dataset.i), j = i + Number(b.dataset.d);
      if (j < 0 || j >= l.length) return;
      l.splice(j, 0, l.splice(i, 1)[0]);
      if (b.dataset.mover === 'efeitos') efeitos(); else dependentes();
      return;
    }
    if (b.matches('[data-es-add-efeito]')) { (est.efeitos = est.efeitos || []).push({fase: '', texto: ''}); efeitos(); return; }
    if (b.dataset.chip) {
      var arr = obter(b.dataset.chip) || [], s = b.dataset.slug, k = arr.indexOf(s);
      if (k >= 0) arr.splice(k, 1); else arr.push(s);
      definir(b.dataset.chip, arr);
      b.classList.toggle('is-on', k < 0); b.setAttribute('aria-pressed', k < 0); return;
    }
    if (b.matches('[data-es-add-canal-btn]')) {
      var slug = $('[data-es-add-canal]').value; if (!slug) return;
      var no = ehNo(slug), pd = meta.padrao[slug] || {formatos: [], otimizacoes: []};
      est.canais = est.canais || [];
      est.canais.push({slug: slug, papel: no ? (slug === 'crm' ? 'Dados' : 'Destino') : 'Alcance', peso: no ? 0 : 20, essencial: false, minimo: null,
        formatos: no ? [] : pd.formatos.slice(), otimizacoes: no ? [] : pd.otimizacoes.slice(), nota: ''});
      dependentes(); return;
    }
    if (b.matches('[data-es-add-etapa]')) { est.fluxo.push({titulo: 'Nova etapa', descricao: '', nos: []}); fluxo(); kpis(); return; }
    if (b.matches('[data-es-add-peca]')) { (est.criativos = est.criativos || []).push({peca: '', specs: '', quantidade: 1, canais: []}); criativos(); return; }
    if (b.matches('[data-es-add-kpi]')) { (est.kpis = est.kpis || []).push({nome: '', etapa: '', fonte: 'Plataforma', principal: false, como: ''}); kpis(); return; }
    if (b.matches('[data-es-salvar]')) salvar(b);
  });
  function limparSlug(slug) {
    (est.fluxo || []).forEach(function (e) { e.nos = (e.nos || []).filter(function (s) { return s !== slug; }); });
    (est.criativos || []).forEach(function (p) { p.canais = (p.canais || []).filter(function (s) { return s !== slug; }); });
  }

  function aviso(texto, ok) {
    var f = $('[data-es-feedback]');
    f.hidden = false; f.className = 'es-feedback ' + (ok ? 'is-ok' : 'is-erro'); f.textContent = texto;
    f.scrollIntoView({block: 'nearest', behavior: 'smooth'});
  }
  function salvar(btn) {
    if (!podeSalvar) return;
    btn.disabled = true;
    var novo = !est.id;
    fetch('/parametros/api/estrategias' + (novo ? '' : '/' + est.id), {method: novo ? 'POST' : 'PUT', credentials: 'same-origin',
      headers: {'Content-Type': 'application/json'}, body: JSON.stringify(est)})
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d.success) throw new Error(d.error || 'Não foi possível salvar.');
        if (novo) { window.location.href = '/parametros/estrategias/' + d.data.id; return; }
        aviso('Estratégia salva.', true);
      })
      .catch(function (e) { aviso(e.message, false); })
      .finally(function () { btn.disabled = false; });
  }

  tudo();
})();
