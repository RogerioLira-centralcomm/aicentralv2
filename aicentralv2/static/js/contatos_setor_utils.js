/**
 * Filtro de contatos por setor (PI: Operações/Financeiro; Cotação: Comercial)
 * e pré-seleção por responsavel_setor.
 */
(function (global) {
  'use strict';

  function stripAccents(s) {
    return String(s || '')
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '');
  }

  function escapeHtml(text) {
    return String(text == null ? '' : text)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function normalizeSetorKey(display) {
    const raw = stripAccents(String(display || '').trim().toLowerCase());
    if (!raw || raw === 'sem setor') return '';
    if (raw === 'operacoes' || raw === 'operacao' || raw.startsWith('operac')) return 'operacoes';
    if (raw === 'financeiro' || raw.startsWith('financ')) return 'financeiro';
    if (raw === 'comercial' || raw.startsWith('comerc')) return 'comercial';
    return raw;
  }

  function contatoNoSetor(contato, setorCanonico) {
    return normalizeSetorKey(contato && contato.setor) === setorCanonico;
  }

  function filtrarContatos(contatos, setorCanonico) {
    const lista = Array.isArray(contatos) ? contatos : [];
    return lista.filter(function (c) {
      return contatoNoSetor(c, setorCanonico);
    });
  }

  function isResponsavelSetor(contato) {
    return !!(contato && contato.responsavel_setor);
  }

  function ordenarContatosLista(lista) {
    return lista.slice().sort(function (a, b) {
      const ra = isResponsavelSetor(a) ? 0 : 1;
      const rb = isResponsavelSetor(b) ? 0 : 1;
      if (ra !== rb) return ra - rb;
      return String(a.nome_completo || '').localeCompare(String(b.nome_completo || ''), 'pt-BR', {
        sensitivity: 'base',
      });
    });
  }

  /**
   * Se houver um ou mais Resp. e-mails no setor, a lista traz todos eles.
   * Caso contrário, todos os contatos ativos daquele setor.
   */
  function listaContatosSetor(contatos, setorCanonico) {
    const noSetor = filtrarContatos(contatos, setorCanonico);
    const responsaveis = noSetor.filter(isResponsavelSetor);
    const base = responsaveis.length ? responsaveis : noSetor;
    return ordenarContatosLista(base);
  }

  function formatarLabelContato(contato) {
    const nome = escapeHtml(String(contato.nome_completo || 'Contato').trim());
    const email = escapeHtml(String(contato.email || '').trim() || '—');
    const setor = escapeHtml(String(contato.setor || '').trim() || 'Sem setor');
    return nome + ' · ' + email + ' · Setor: ' + setor;
  }

  function idResponsavelSetorMarcado(contatos, setorCanonico) {
    const filtrados = filtrarContatos(contatos, setorCanonico);
    const flagged = filtrados.filter(isResponsavelSetor);
    if (flagged.length) return flagged[0].id_contato_cliente;
    return null;
  }

  function escolherResponsavelSetor(contatos, setorCanonico) {
    const marcado = idResponsavelSetorMarcado(contatos, setorCanonico);
    if (marcado != null) return marcado;

    const filtrados = filtrarContatos(contatos, setorCanonico);
    if (filtrados.length === 1) return filtrados[0].id_contato_cliente;
    return null;
  }

  function idValidoNaLista(id, contatosFiltrados) {
    if (id === null || id === undefined || id === '') return false;
    const s = String(id);
    return contatosFiltrados.some(function (c) {
      return String(c.id_contato_cliente) === s;
    });
  }

  function resolverValorSelect(contatosFiltrados, contatosCompletos, setorCanonico, valorPreferido) {
    if (idValidoNaLista(valorPreferido, contatosFiltrados)) {
      return String(valorPreferido);
    }
    const respNaLista = (contatosFiltrados || []).filter(isResponsavelSetor);
    if (respNaLista.length) {
      return String(respNaLista[0].id_contato_cliente);
    }
    const escolhido = escolherResponsavelSetor(contatosCompletos || contatosFiltrados, setorCanonico);
    return escolhido != null ? String(escolhido) : '';
  }

  function preencherSelect(selectEl, contatosFiltrados, options) {
    if (!selectEl) return;
    const opts = options || {};
    const labelFn = opts.labelFn || formatarLabelContato;
    const placeholder = opts.placeholder != null ? opts.placeholder : 'Selecione';
    const setorCanonico = opts.setorCanonico;
    const contatosCompletos = opts.contatosCompletos || contatosFiltrados;
    const lista = ordenarContatosLista(contatosFiltrados || []);
    const valor = resolverValorSelect(
      lista,
      contatosCompletos,
      setorCanonico,
      opts.valorPreferido
    );

    let html = '<option value="">' + escapeHtml(placeholder) + '</option>';
    lista.forEach(function (c) {
      html += '<option value="' + c.id_contato_cliente + '">' + labelFn(c) + '</option>';
    });
    selectEl.innerHTML = html;
    if (valor) selectEl.value = valor;
    else selectEl.value = '';
  }

  global.ContatosSetorUtils = {
    normalizeSetorKey: normalizeSetorKey,
    contatoNoSetor: contatoNoSetor,
    filtrarContatos: filtrarContatos,
    listaContatosSetor: listaContatosSetor,
    ordenarContatosLista: ordenarContatosLista,
    formatarLabelContato: formatarLabelContato,
    escapeHtml: escapeHtml,
    isResponsavelSetor: isResponsavelSetor,
    idResponsavelSetorMarcado: idResponsavelSetorMarcado,
    escolherResponsavelSetor: escolherResponsavelSetor,
    preencherSelect: preencherSelect,
    resolverValorSelect: resolverValorSelect,
  };
})(typeof window !== 'undefined' ? window : globalThis);
