/* Briefing da Área do Cliente: wizard dinâmico.
 * Sem JS a página é um formulário único com todos os blocos. Com JS vira um
 * passo a passo: passos e campos aparecem conforme as respostas
 * (data-show-when / data-show-unless), o histórico do cliente pré-preenche,
 * as praças ganham autocompletar local e organização com IA, e a nota de
 * qualidade segue as mesmas regras de briefing.qualidade() no servidor. */
(function () {
  'use strict';
  var form = document.getElementById('bw');
  var dadosEl = document.getElementById('bw-dados');
  if (!form || !dadosEl) return;
  var D = JSON.parse(dadosEl.textContent);
  var OBJ = {};
  D.opcoes.objetivos.forEach(function (o) { OBJ[o.id] = o; });
  var HIST = {};
  (D.opcoes.historico || []).forEach(function (h) { HIST[h.id] = h; });

  var $ = function (sel, el) { return (el || form).querySelector(sel); };
  var $$ = function (sel, el) { return Array.prototype.slice.call((el || form).querySelectorAll(sel)); };
  var esc = function (s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); };
  var semAcento = function (s) { return String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim(); };
  var ICON_X = '<svg class="ac-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18"/></svg>';

  function val(nome) {
    var el = form.elements[nome];
    if (!el) return '';
    if (el instanceof RadioNodeList) {
      if (el[0] && el[0].type === 'checkbox') return $$('input[name="' + nome + '"]:checked').map(function (i) { return i.value; });
      return el.value || '';
    }
    if (el.type === 'checkbox') return el.checked ? el.value : '';
    return (el.value || '').trim();
  }
  function lista(nome) { var v = val(nome); return Array.isArray(v) ? v : (v ? [v] : []); }
  function pracas() { return $$('#bw-tokens-list input[name="pracas"]').map(function (i) { return i.value; }); }

  /* ---------- Estado ---------- */
  function estado() {
    return {
      titulo: val('titulo'), objetivo: val('objetivo'), objetivo_tipo: val('objetivo_tipo'), kpi: val('kpi'),
      kpi_meta: val('kpi_meta'), publico: val('publico'), idades: lista('idades'), genero: val('genero'),
      classes: lista('classes'), b2b: val('b2b') === '1', publico_b2b: val('publico_b2b'),
      abrangencia: val('abrangencia'), pracas: pracas(), raio_detalhe: val('raio_detalhe'),
      inicio: val('inicio'), fim: val('fim'), datas_chave: val('datas_chave'), verba: val('verba'),
      canais: lista('canais'), materiais: val('materiais'), materiais_detalhe: val('materiais_detalhe'),
      site: val('site'), mensuracao: lista('mensuracao'), concorrentes: val('concorrentes'), descricao: val('descricao'),
      origem: val('origem')
    };
  }

  /* ---------- Qualidade (espelho de briefing.qualidade) ---------- */
  function qualidade(e) {
    var conv = !!(OBJ[e.objetivo_tipo] && OBJ[e.objetivo_tipo].conversao);
    var c = [
      ['objetivo', !!(e.objetivo_tipo && e.kpi), 'Tipo de objetivo e KPI'],
      ['publico', !!(e.idades.length || e.classes.length || e.genero === 'mulheres' || e.genero === 'homens' || e.b2b || e.publico.length >= 20), 'Público com um recorte'],
      ['pracas', !!(e.abrangencia === 'nacional' || e.pracas.length || (e.abrangencia === 'raio' && e.raio_detalhe)), 'Praças definidas'],
      ['periodo', !!(e.inicio && e.fim), 'Início e fim'],
      ['periodo', !!e.verba, 'Verba ou faixa'],
      ['canais', !!e.canais.length, 'Canais ou pedido de sugestão'],
      ['canais', !!e.materiais, 'Situação das peças']
    ];
    if (conv) c.push(['canais', !!(e.site && e.mensuracao.length), 'Site e mensuração da conversão']);
    var feitos = c.filter(function (x) { return x[1]; }).length;
    var avisos = [];
    var hoje = new Date(); hoje.setHours(0, 0, 0, 0);
    var ini = e.inicio ? new Date(e.inicio + 'T00:00:00') : null;
    var fim = e.fim ? new Date(e.fim + 'T00:00:00') : null;
    if (ini && (ini - hoje) / 864e5 < 7) avisos.push(['periodo', 'Início em menos de 7 dias: prazo curto para planejar e subir as campanhas.']);
    if (ini && fim && (fim - ini) / 864e5 < 7) avisos.push(['periodo', 'Período menor que 7 dias: pouco tempo para otimizar.']);
    if (conv && e.mensuracao.indexOf('Não tenho') >= 0) avisos.push(['canais', 'Objetivo de conversão sem mensuração instalada.']);
    return { nota: Math.round(100 * feitos / c.length), checks: c, avisos: avisos };
  }

  /* ---------- Campos condicionais ---------- */
  function casa(regra, e) {
    var p = regra.split(':'), campo = p[0], valores = (p[1] || '').split(',');
    var atual = campo === 'b2b' ? (e.b2b ? '1' : '') : e[campo];
    if (Array.isArray(atual)) return atual.some(function (a) { return valores.indexOf(a) >= 0; });
    return valores.indexOf(atual || '') >= 0;
  }
  function aplicarCondicoes(e) {
    $$('[data-show-when]').forEach(function (el) { el.hidden = !casa(el.dataset.showWhen, e); });
    $$('[data-show-unless]').forEach(function (el) { el.hidden = casa(el.dataset.showUnless, e); });
    $$('[data-label-when]').forEach(function (el) {
      if (!el.dataset.labelBase) el.dataset.labelBase = el.textContent;
      el.textContent = casa(el.dataset.labelWhen, e) ? el.dataset.labelAlt : el.dataset.labelBase;
    });
  }

  /* ---------- KPIs conforme o objetivo ---------- */
  var kpiChips = document.getElementById('bw-kpi-chips');
  function desenharKpis(e) {
    var o = OBJ[e.objetivo_tipo];
    kpiChips.innerHTML = o ? o.kpis.map(function (k) {
      return '<button type="button" class="bw-pill' + (k === e.kpi ? ' is-on' : '') + '" data-fill="b-kpi" data-value="' + esc(k) + '">' + esc(k) + '</button>';
    }).join('') : '';
    $('#b-kpi').placeholder = o ? 'Ex.: ' + o.kpis[0] : 'Ex.: Leads';
  }

  /* ---------- Passos ---------- */
  var passos = $$('.bw-step');
  var atual = 0;
  function passosVisiveis() { return passos.filter(function (p) { return !p.dataset.skip; }); }
  var nav = $('.bw-nav'), navList = document.getElementById('bw-nav'), navBar = document.getElementById('bw-nav-bar');
  var btVoltar = document.getElementById('bw-voltar'), btSeguir = document.getElementById('bw-seguir'), btEnviar = document.getElementById('bw-enviar');

  function irPara(i, foco) {
    var vis = passosVisiveis();
    atual = Math.max(0, Math.min(i, vis.length - 1));
    passos.forEach(function (p) { p.hidden = p !== vis[atual]; });
    vis.forEach(function (p, n) { var num = p.querySelector('[data-bw-num]'); if (num) num.textContent = (n + 1) + ' de ' + vis.length; });
    navList.innerHTML = vis.map(function (p, n) {
      var cls = n === atual ? 'is-atual' : (n < atual ? 'is-feito' : '');
      return '<li class="' + cls + '"><button type="button" data-ir="' + n + '"' + (n === atual ? ' aria-current="step"' : '') + '><span>' + (n + 1) + '</span>' + esc(p.dataset.label) + '</button></li>';
    }).join('');
    navBar.style.width = (100 * atual / Math.max(1, vis.length - 1)) + '%';
    var ultimo = atual === vis.length - 1;
    btVoltar.hidden = atual === 0;
    btSeguir.hidden = ultimo;
    btEnviar.hidden = !ultimo;
    document.getElementById('bw-dica').hidden = !ultimo && atual !== 0;
    if (vis[atual].dataset.step === 'revisao') desenharRevisao();
    if (foco) {
      var h = vis[atual].querySelector('h2');
      if (h) { h.setAttribute('tabindex', '-1'); h.focus({ preventScroll: true }); }
      var topo = form.getBoundingClientRect().top + window.scrollY - 80;
      if (window.scrollY > topo) window.scrollTo({ top: topo, behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
    }
    try { sessionStorage.setItem('bw-passo', vis[atual].dataset.step); } catch (err) { /* sem storage */ }
  }
  function irParaPasso(nome) {
    var vis = passosVisiveis();
    for (var i = 0; i < vis.length; i++) if (vis[i].dataset.step === nome) return irPara(i, true);
  }
  function validarPasso() {
    var p = passosVisiveis()[atual];
    if (p.dataset.step !== 'objetivo') return true;
    var ok = true;
    [['b-titulo', 3, 'Dê um nome para a campanha ou ação.'], ['b-objetivo', 10, 'Conte em uma ou duas frases o que você quer alcançar.']].forEach(function (r) {
      var el = document.getElementById(r[0]);
      var id = 'erro-' + el.name;
      var msg = document.getElementById(id);
      if (el.value.trim().length < r[1]) {
        el.setAttribute('aria-invalid', 'true'); el.setAttribute('aria-describedby', id);
        if (!msg) { msg = document.createElement('p'); msg.className = 'ac-field__error'; msg.id = id; el.insertAdjacentElement('afterend', msg); }
        msg.textContent = r[2];
        if (ok) el.focus();
        ok = false;
      } else {
        el.removeAttribute('aria-invalid');
        if (msg) msg.remove();
      }
    });
    return ok;
  }

  /* ---------- Reaproveitar histórico ---------- */
  function setRadio(nome, valor) { $$('input[name="' + nome + '"]').forEach(function (i) { i.checked = i.value === valor; }); }
  function setChecks(nome, valores) { $$('input[name="' + nome + '"]').forEach(function (i) { i.checked = valores.indexOf(i.value) >= 0; }); }
  function aplicarOrigem(id) {
    var h = HIST[id], aviso = document.getElementById('bw-filled');
    if (!h) { if (aviso) aviso.hidden = true; return; }
    var feitos = [];
    var titulo = $('#b-titulo');
    if (!titulo.value.trim()) { titulo.value = h.titulo + ' (nova edição)'; feitos.push('nome'); }
    var obj = $('#b-objetivo');
    if (h.objetivo && !obj.value.trim()) { obj.value = h.objetivo; feitos.push('objetivo'); }
    if (h.objetivo_tipo && !val('objetivo_tipo')) { setRadio('objetivo_tipo', h.objetivo_tipo); feitos.push('tipo de objetivo'); }
    if (h.kpi && !val('kpi')) { $('#b-kpi').value = h.kpi; feitos.push('KPI'); }
    var pub = $('#b-publico');
    if (h.publico && !pub.value.trim()) { pub.value = h.publico; feitos.push('público'); }
    if (h.pracas.length && !pracas().length) {
      h.pracas.forEach(addToken);
      if (!val('abrangencia')) setRadio('abrangencia', 'cidades');
      feitos.push(h.pracas.length + ' praça' + (h.pracas.length > 1 ? 's' : ''));
    }
    if (h.canais.length && !lista('canais').length) { setChecks('canais', h.canais); feitos.push('canais'); }
    if (h.dias && !val('inicio')) {
      var ini = new Date(); ini.setDate(ini.getDate() + 21);
      var fim = new Date(ini); fim.setDate(fim.getDate() + h.dias);
      $('#b-inicio').value = ini.toISOString().slice(0, 10);
      $('#b-fim').value = fim.toISOString().slice(0, 10);
      feitos.push('período de ' + h.dias + ' dias a partir de daqui a 3 semanas');
    }
    if (aviso) {
      aviso.hidden = false;
      aviso.textContent = feitos.length
        ? 'Trouxemos de "' + h.titulo + '": ' + feitos.join(', ') + '. Revise nos próximos passos.'
        : 'Os campos já estavam preenchidos; nada foi substituído.';
    }
    atualizar();
  }

  function desenharReuso() {
    var hs = D.opcoes.historico || [];
    var pubs = [], prs = [];
    hs.forEach(function (h) {
      if (h.publico && pubs.indexOf(h.publico) < 0) pubs.push(h.publico);
      h.pracas.forEach(function (p) { if (prs.indexOf(p) < 0) prs.push(p); });
    });
    var bp = $('[data-reuse="publico"]'), bpr = $('[data-reuse="pracas"]');
    if (pubs.length) {
      bp.hidden = false;
      document.getElementById('bw-reuse-publico').innerHTML = pubs.slice(0, 4).map(function (p) {
        return '<button type="button" class="bw-pill bw-pill--long" data-fill="b-publico" data-value="' + esc(p) + '" title="' + esc(p) + '">' + esc(p.length > 70 ? p.slice(0, 68) + '…' : p) + '</button>';
      }).join('');
    }
    if (prs.length) {
      bpr.hidden = false;
      document.getElementById('bw-reuse-pracas').innerHTML = prs.slice(0, 14).map(function (p) {
        return '<button type="button" class="bw-pill" data-add-praca="' + esc(p) + '">+ ' + esc(p) + '</button>';
      }).join('');
    }
  }

  /* ---------- Praças ---------- */
  var tokens = document.getElementById('bw-tokens-list');
  var busca = document.getElementById('b-praca-busca');
  var combo = document.getElementById('bw-sugestoes-locais');
  var BASE = (D.opcoes.base_pracas || []).map(function (p) { return { nome: p.nome, tipo: p.tipo, chave: semAcento(p.nome) }; });
  var ALIAS = { bh: 'Belo Horizonte - MG', sampa: 'São Paulo - SP', sp: 'São Paulo (estado)', rj: 'Rio de Janeiro (estado)', rio: 'Rio de Janeiro - RJ', poa: 'Porto Alegre - RS', floripa: 'Florianópolis - SC', bsb: 'Brasília - DF', df: 'Distrito Federal (estado)', mg: 'Minas Gerais (estado)', cwb: 'Curitiba - PR', ssa: 'Salvador - BA', rec: 'Recife - PE', bh_rm: 'RM de Belo Horizonte - MG' };

  function addToken(nome) {
    nome = String(nome || '').replace(/\s+/g, ' ').trim();
    if (!nome) return;
    var ja = pracas().map(semAcento);
    if (ja.indexOf(semAcento(nome)) >= 0) return;
    if (/^brasil/i.test(nome)) { setRadio('abrangencia', 'nacional'); atualizar(); return; }
    var li = document.createElement('li');
    li.className = 'ac-tag';
    li.innerHTML = esc(nome) + '<input type="hidden" name="pracas" value="' + esc(nome) + '"><button type="button" class="ac-tag__remove" aria-label="Tirar ' + esc(nome) + '">' + ICON_X + '</button>';
    tokens.appendChild(li);
    if (!val('abrangencia')) setRadio('abrangencia', /\(estado\)$/.test(nome) ? 'estados' : (/^Região/.test(nome) ? 'regioes' : 'cidades'));
    atualizar();
  }
  var ativo = -1, opcoesCombo = [];
  function fecharCombo() { combo.hidden = true; busca.setAttribute('aria-expanded', 'false'); ativo = -1; busca.removeAttribute('aria-activedescendant'); }
  function abrirCombo() {
    var q = semAcento(busca.value);
    if (q.length < 2) return fecharCombo();
    var ja = pracas().map(semAcento);
    opcoesCombo = [];
    if (ALIAS[q.replace(/\s+/g, '_')]) opcoesCombo.push({ nome: ALIAS[q.replace(/\s+/g, '_')], tipo: 'atalho' });
    BASE.forEach(function (p) {
      if (ja.indexOf(p.chave) >= 0) return;
      var pos = p.chave.indexOf(q);
      if (pos === 0 || (pos > 0 && /[\s(-]/.test(p.chave[pos - 1]))) opcoesCombo.push(p);
    });
    opcoesCombo = opcoesCombo.slice(0, 8);
    var tipos = { cidade: 'Cidade', estado: 'Estado', regiao: 'Região', pais: 'País', atalho: 'Atalho' };
    combo.innerHTML = opcoesCombo.map(function (p, i) {
      return '<li role="option" id="bw-op-' + i + '" data-i="' + i + '"><span>' + esc(p.nome) + '</span><small>' + (tipos[p.tipo] || '') + '</small></li>';
    }).join('') + '<li role="option" id="bw-op-ia" data-ia="1" class="bw-combo__ia"><span>Organizar "' + esc(busca.value.trim()) + '" com IA</span><small>IA</small></li>';
    combo.hidden = false;
    busca.setAttribute('aria-expanded', 'true');
    ativo = -1;
  }
  function marcar(i) {
    var itens = $$('li', combo);
    if (!itens.length) return;
    ativo = (i + itens.length) % itens.length;
    itens.forEach(function (li, n) { li.classList.toggle('is-ativo', n === ativo); li.setAttribute('aria-selected', n === ativo ? 'true' : 'false'); });
    busca.setAttribute('aria-activedescendant', itens[ativo].id);
  }
  function escolher(li) {
    if (!li) return;
    if (li.dataset.ia) { fecharCombo(); return pedirIA(); }
    addToken(opcoesCombo[+li.dataset.i].nome);
    busca.value = '';
    fecharCombo();
    busca.focus();
  }
  function adicionarTextoLivre() {
    var t = busca.value.trim();
    if (!t) return;
    if (opcoesCombo.length && semAcento(opcoesCombo[0].nome).indexOf(semAcento(t)) === 0) addToken(opcoesCombo[0].nome);
    else t.split(/[;,\n]+/).forEach(addToken);
    busca.value = '';
    fecharCombo();
  }

  var btIA = document.getElementById('bw-ia-pracas'), iaStatus = document.getElementById('bw-ia-status');
  var iaBox = document.getElementById('bw-ia-sugestoes'), iaLista = document.getElementById('bw-ia-sugestoes-lista');
  function pedirIA() {
    var texto = busca.value.trim();
    var escolhidas = pracas();
    if (!texto && !escolhidas.length) { iaStatus.textContent = 'Digite as praças do seu jeito ou escolha algumas para a IA sugerir vizinhas.'; busca.focus(); return; }
    var corpo = new FormData();
    corpo.append('csrf', D.csrf);
    corpo.append('texto', texto);
    escolhidas.forEach(function (p) { corpo.append('escolhidas', p); });
    btIA.disabled = true;
    btIA.classList.add('is-loading');
    iaStatus.textContent = 'Organizando as praças…';
    fetch(D.urlPracas, { method: 'POST', body: corpo, credentials: 'same-origin', headers: { 'X-Requested-With': 'fetch' } })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (res) {
        if (!res.ok) throw new Error(res.j.erro || 'Falhou');
        var j = res.j;
        var antes = pracas().length;
        (j.pracas || []).forEach(function (p) { if (p.tipo === 'pais') setRadio('abrangencia', 'nacional'); else addToken(p.nome); });
        var novas = pracas().length - antes;
        if (texto) busca.value = '';
        iaLista.innerHTML = (j.sugestoes || []).map(function (s) {
          return '<button type="button" class="bw-pill bw-pill--sug" data-add-praca="' + esc(s.nome) + '" title="' + esc(s.motivo) + '">+ ' + esc(s.nome) + (s.motivo ? '<small>' + esc(s.motivo) + '</small>' : '') + '</button>';
        }).join('');
        iaBox.hidden = !(j.sugestoes || []).length;
        iaStatus.textContent = (novas ? novas + ' praça' + (novas > 1 ? 's organizadas' : ' organizada') + '. ' : '') +
          ((j.sugestoes || []).length ? 'Veja as praças próximas sugeridas.' : '') + (j.observacao ? ' ' + j.observacao : '') || 'Nada a ajustar.';
        atualizar();
      })
      .catch(function (err) { iaStatus.textContent = err.message && err.message !== 'Failed to fetch' ? err.message : 'A IA não respondeu agora. Você pode digitar as praças à mão.'; })
      .finally(function () { btIA.disabled = false; btIA.classList.remove('is-loading'); });
  }

  /* ---------- Resumo, nota e revisão ---------- */
  function fmtData(s) { return s ? s.split('-').reverse().join('/') : 'a definir'; }
  function secoes(e) {
    var o = OBJ[e.objetivo_tipo];
    var recortes = [];
    if (e.genero && e.genero !== 'todos') recortes.push(D.generos[e.genero]);
    if (e.idades.length) recortes.push('idades ' + e.idades.join(', '));
    if (e.classes.length) recortes.push('classes ' + e.classes.join(', '));
    var conv = o && o.conversao;
    return [
      ['objetivo', 'Objetivo', [e.titulo && '<b>' + esc(e.titulo) + '</b>', o && esc(o.rotulo), e.kpi && 'KPI: ' + esc(e.kpi) + (e.kpi_meta ? ' (meta: ' + esc(e.kpi_meta) + ')' : ''), esc(e.objetivo)]],
      ['publico', 'Público', [esc(e.publico), recortes.length && 'Recorte: ' + esc(recortes.join('; ')), e.b2b && 'B2B' + (e.publico_b2b ? ': ' + esc(e.publico_b2b) : '')]],
      ['pracas', 'Praças', [e.abrangencia && esc(D.abrangencias[e.abrangencia]), e.abrangencia !== 'nacional' && e.pracas.length && esc(e.pracas.join('; ')), e.abrangencia === 'raio' && esc(e.raio_detalhe)]],
      ['periodo', 'Período e verba', [(e.inicio || e.fim) && fmtData(e.inicio) + ' a ' + fmtData(e.fim), e.datas_chave && 'Datas: ' + esc(e.datas_chave), e.verba && 'Verba: ' + esc(e.verba)]],
      ['canais', 'Canais e materiais', [e.canais.length && esc(e.canais.map(function (c) { return D.canaisRotulo[c]; }).join(', ')), e.materiais && esc(D.materiais[e.materiais]), esc(e.materiais_detalhe), conv && e.site && 'Destino: ' + esc(e.site), conv && e.mensuracao.length && 'Mensuração: ' + esc(e.mensuracao.join(', ')), e.concorrentes && 'Referências: ' + esc(e.concorrentes)]]
    ];
  }
  function desenharRevisao() {
    var e = estado(), q = qualidade(e);
    var origem = HIST[e.origem];
    document.getElementById('bw-review').innerHTML = secoes(e).map(function (s) {
      var linhas = s[2].filter(Boolean);
      var falta = q.checks.filter(function (c) { return c[0] === s[0] && !c[1]; }).map(function (c) { return c[2]; });
      return '<button type="button" class="bw-review__item' + (falta.length ? ' is-falta' : '') + '" data-ir-passo="' + s[0] + '">' +
        '<span class="bw-review__label">' + s[1] + '<em>Editar</em></span>' +
        (linhas.length ? linhas.map(function (l) { return '<span class="bw-review__line">' + l + '</span>'; }).join('') : '<span class="bw-review__line is-vazio">Não informado</span>') +
        (falta.length ? '<span class="bw-review__falta">Falta: ' + esc(falta.join(', ')) + '</span>' : '') + '</button>';
    }).join('') + (origem ? '<p class="ac-form__hint">Reaproveitou dados de ' + esc(origem.fonte + ' ' + origem.titulo) + '.</p>' : '');
  }
  var nomesPasso = {};
  passos.forEach(function (p) { nomesPasso[p.dataset.step] = p.dataset.label; });
  function desenharNota(e) {
    var q = qualidade(e);
    document.getElementById('bw-nota').textContent = q.nota;
    var meter = document.getElementById('bw-meter');
    meter.style.width = q.nota + '%';
    meter.parentNode.dataset.tom = q.nota >= 80 ? 'ok' : (q.nota >= 50 ? 'meio' : 'baixo');
    document.getElementById('bw-check').innerHTML = q.checks.map(function (c) {
      return '<li class="' + (c[1] ? 'is-ok' : '') + '"><button type="button" data-ir-passo="' + c[0] + '"><span class="bw-check__dot" aria-hidden="true"></span>' + esc(c[2]) + '<span class="ac-sr">' + (c[1] ? ' (feito)' : ' (pendente)') + '</span></button></li>';
    }).join('');
    document.getElementById('bw-avisos').innerHTML = q.avisos.map(function (a) { return '<li>' + esc(a[1]) + '</li>'; }).join('');
  }
  function dicaPeriodo(e) {
    var el = document.getElementById('bw-periodo-hint');
    if (!(e.inicio && e.fim)) { el.textContent = ''; return; }
    var dias = Math.round((new Date(e.fim) - new Date(e.inicio)) / 864e5) + 1;
    el.textContent = dias > 0 ? dias + ' dias de campanha.' : '';
  }

  function atualizar() {
    var e = estado();
    aplicarCondicoes(e);
    desenharKpis(e);
    desenharNota(e);
    dicaPeriodo(e);
    $$('[data-fill]').forEach(function (b) {
      var alvo = document.getElementById(b.dataset.fill);
      if (alvo) b.classList.toggle('is-on', alvo.value.trim() === b.dataset.value);
    });
    $$('[data-add-praca]').forEach(function (b) { b.hidden = pracas().map(semAcento).indexOf(semAcento(b.dataset.addPraca)) >= 0; });
    var vis = passosVisiveis();
    if (vis[atual] && vis[atual].dataset.step === 'revisao') desenharRevisao();
  }

  /* ---------- Ligações ---------- */
  function iniciar() {
    form.classList.add('is-wizard');
    nav.hidden = false;
    btSeguir.hidden = false;
    btIA.hidden = false;
    $('.bw-score', document).hidden = false;
    $$('[data-js-only]').forEach(function (el) { el.hidden = false; });
    busca.removeAttribute('name');
    var inicial = 0;
    if (D.comErros) {
      var err = form.querySelector('[aria-invalid="true"]');
      var passo = err && err.closest('.bw-step');
      inicial = Math.max(0, passosVisiveis().indexOf(passo));
    }
    desenharReuso();
    atualizar();
    irPara(inicial, false);
  }

  form.addEventListener('change', function (ev) {
    if (ev.target.name === 'origem') aplicarOrigem(ev.target.value);
    atualizar();
  });
  form.addEventListener('input', function (ev) { if (ev.target !== busca) atualizar(); });
  form.addEventListener('click', function (ev) {
    var t = ev.target.closest('button');
    if (!t) return;
    if (t.dataset.fill) {
      var alvo = document.getElementById(t.dataset.fill);
      if (t.dataset.fill === 'b-publico' && alvo.value.trim() && alvo.value.indexOf(t.dataset.value) < 0) alvo.value = alvo.value.trim() + '\n' + t.dataset.value;
      else alvo.value = t.dataset.value;
      atualizar();
    } else if (t.dataset.addPraca) {
      addToken(t.dataset.addPraca);
    } else if (t.classList.contains('ac-tag__remove') && t.closest('#bw-tokens-list')) {
      t.closest('li').remove();
      atualizar();
      busca.focus();
    } else if (t.dataset.ir !== undefined) {
      var alvoN = +t.dataset.ir;
      if (alvoN <= atual || validarPasso()) irPara(alvoN, true);
    } else if (t.dataset.irPasso) {
      irParaPasso(t.dataset.irPasso);
    }
  });
  document.querySelector('.bw-side').addEventListener('click', function (ev) {
    var t = ev.target.closest('[data-ir-passo]');
    if (t && form.classList.contains('is-wizard')) irParaPasso(t.dataset.irPasso);
  });
  btSeguir.addEventListener('click', function () { if (validarPasso()) irPara(atual + 1, true); });
  btVoltar.addEventListener('click', function () { irPara(atual - 1, true); });
  btIA.addEventListener('click', pedirIA);

  busca.addEventListener('input', abrirCombo);
  busca.addEventListener('keydown', function (ev) {
    if (ev.key === 'ArrowDown') { ev.preventDefault(); if (combo.hidden) abrirCombo(); marcar(ativo + 1); }
    else if (ev.key === 'ArrowUp') { ev.preventDefault(); marcar(ativo - 1); }
    else if (ev.key === 'Enter') { ev.preventDefault(); if (ativo >= 0) escolher($$('li', combo)[ativo]); else adicionarTextoLivre(); }
    else if (ev.key === 'Escape') fecharCombo();
    else if (ev.key === 'Backspace' && !busca.value && tokens.lastElementChild) { tokens.lastElementChild.remove(); atualizar(); }
    else if (ev.key === ',' || ev.key === ';') { ev.preventDefault(); adicionarTextoLivre(); }
  });
  combo.addEventListener('mousedown', function (ev) { ev.preventDefault(); escolher(ev.target.closest('li')); });
  busca.addEventListener('blur', function () { setTimeout(fecharCombo, 120); });

  form.addEventListener('keydown', function (ev) {
    if (ev.key === 'Enter' && ev.target.tagName === 'INPUT' && ev.target !== busca && form.classList.contains('is-wizard') && !btSeguir.hidden) {
      ev.preventDefault();
      btSeguir.click();
    }
  });
  form.addEventListener('submit', function (ev) {
    if (busca.value.trim()) adicionarTextoLivre();
    var vis = passosVisiveis();
    if (form.classList.contains('is-wizard') && vis[atual].dataset.step !== 'revisao') {
      ev.preventDefault();
      return;
    }
    var t = $('#b-titulo'), o = $('#b-objetivo');
    if (t.value.trim().length < 3 || o.value.trim().length < 10) {
      ev.preventDefault();
      irParaPasso('objetivo');
      validarPasso();
      return;
    }
    btEnviar.disabled = true;
    btEnviar.classList.add('is-loading');
  });

  /* Itens do Descobrir saem sem recarregar. */
  $$('.ac-tag__remove[data-secao]').forEach(function (btn) {
    btn.addEventListener('click', function (ev) {
      ev.preventDefault();
      ev.stopPropagation();
      var corpo = new FormData();
      corpo.append('csrf', D.csrf);
      corpo.append('secao', btn.dataset.secao);
      corpo.append('id', btn.dataset.id);
      btn.disabled = true;
      fetch(D.urlSelecao, { method: 'POST', body: corpo, credentials: 'same-origin', headers: { 'X-Requested-With': 'fetch' } })
        .then(function (r) {
          if (!r.ok) throw new Error();
          var li = btn.closest('li'), ul = li.parentNode;
          li.remove();
          if (!ul.children.length) ul.outerHTML = '<p class="ac-form__hint">Nenhum item separado.</p>';
        })
        .catch(function () { btn.disabled = false; btn.form.requestSubmit(btn); });
    });
  });

  /* Primeira vez: as ilustrações explicam as etapas e o botão abre o wizard. */
  var intro = document.getElementById('bw-intro');
  var layout = document.querySelector('.bw-layout');
  if (intro && form.dataset.intro) {
    layout.hidden = true;
    intro.querySelector('[data-bw-start]').addEventListener('click', function (ev) {
      ev.preventDefault();
      intro.hidden = true;
      layout.hidden = false;
      irPara(0, true);
      $('#b-titulo').focus();
    });
  }
  iniciar();
})();
