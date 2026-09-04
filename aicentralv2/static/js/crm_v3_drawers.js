/**
 * CRM v3 Drawers — plug-in que substitui os modais grandes (cliente, atividade,
 * cotação e contato) por drawers off-canvas usando cxDrawer.
 *
 * Estratégia
 * ----------
 * O `crm_v3.js` continua abrindo os modais tradicionais como fallback; este
 * módulo intercepta os mesmos handlers (via wrappers das funções globais
 * exportadas em `window.crmV3.*`) e chama `cxDrawer.open()` com os templates
 * <template id="cx-drawer-*-tpl">. O submit envia via as mesmas APIs REST do CRM v3.
 */
(function () {
    'use strict';

    var API_BASE = '/crm-v3/api';

    function $(sel, root) { return (root || document).querySelector(sel); }
    function $$(sel, root) {
        return Array.prototype.slice.call((root || document).querySelectorAll(sel));
    }

    function cloneTpl(id) {
        var tpl = document.getElementById(id);
        if (!tpl || !tpl.content) return null;
        return tpl.content.cloneNode(true);
    }

    function apiFetch(path, opts) {
        opts = opts || {};
        var init = {
            method: opts.method || 'GET',
            headers: { 'Content-Type': 'application/json' }
        };
        if (opts.body) init.body = JSON.stringify(opts.body);
        return fetch(API_BASE + path, init).then(function (r) {
            return r.json().then(function (data) {
                if (!r.ok || (data && data.success === false)) {
                    var err = new Error((data && data.error) || 'Erro na requisição');
                    err.status = r.status;
                    throw err;
                }
                return data;
            });
        });
    }

    function fillForm(form, data) {
        if (!form || !data) return;
        $$('[data-field]', form).forEach(function (el) {
            var key = el.getAttribute('data-field');
            var val = readDeep(data, key);
            if (val === undefined || val === null) return;
            if (el.type === 'checkbox') el.checked = !!val;
            else el.value = String(val);
        });
    }

    function serializeForm(form) {
        var out = {};
        $$('[data-field]', form).forEach(function (el) {
            var key = el.getAttribute('data-field');
            var val = el.type === 'checkbox' ? el.checked : el.value;
            writeDeep(out, key, val);
        });
        return out;
    }

    function readDeep(obj, path) {
        return path.split('.').reduce(function (acc, k) {
            return (acc == null) ? acc : acc[k];
        }, obj);
    }

    function writeDeep(obj, path, value) {
        var parts = path.split('.');
        var last = parts.pop();
        var cursor = obj;
        parts.forEach(function (k) {
            if (!cursor[k] || typeof cursor[k] !== 'object') cursor[k] = {};
            cursor = cursor[k];
        });
        cursor[last] = value;
    }

    function toast(msg, err) {
        if (typeof window.showToast === 'function') window.showToast(msg, !!err);
        else console.log(msg);
    }

    function formatarCepInput(value, whileTyping) {
        var d = String(value || '').replace(/\D/g, '').slice(0, 8);
        if (whileTyping && d.length <= 5) return d;
        if (d.length > 5) return d.slice(0, 5) + '-' + d.slice(5);
        return d;
    }

    function bindCepLookup(root) {
        var cepInput = root.querySelector('[data-field="endereco.cep"]');
        if (!cepInput || cepInput.dataset.cepBound === '1') return;
        cepInput.dataset.cepBound = '1';
        var last = '';

        function applyEndereco(data) {
            if (!data) return;
            var map = {
                logradouro: '[data-field="endereco.logradouro"]',
                bairro: '[data-field="endereco.bairro"]',
                cidade: '[data-field="endereco.cidade"]'
            };
            Object.keys(map).forEach(function (k) {
                var el = root.querySelector(map[k]);
                if (el && data[k]) el.value = data[k];
            });
            var uf = root.querySelector('[data-field="endereco.uf"]');
            if (uf && data.uf) uf.value = data.uf;
            var numero = root.querySelector('[data-field="endereco.numero"]');
            if (numero) numero.focus();
            toast('Endereço preenchido pelo CEP');
        }

        function lookup() {
            var digits = String(cepInput.value || '').replace(/\D/g, '');
            cepInput.value = formatarCepInput(digits);
            if (digits.length !== 8 || digits === last) return;
            if (/^(\d)\1{7}$/.test(digits)) return;
            last = digits;
            apiFetch('/cep/' + encodeURIComponent(digits)).then(function (resp) {
                applyEndereco((resp && resp.data) || null);
            }).catch(function (err) {
                last = '';
                toast(err.message || 'CEP não encontrado', true);
            });
        }

        cepInput.addEventListener('input', function () {
            cepInput.value = formatarCepInput(cepInput.value, true);
        });
        cepInput.addEventListener('blur', lookup);
        cepInput.addEventListener('keydown', function (ev) {
            if (ev.key === 'Enter') {
                ev.preventDefault();
                lookup();
            }
        });
    }

    /* -----------------------------------------------------------
       Drawer: Cliente
       ----------------------------------------------------------- */

    function openDrawerCliente(cliente, opts) {
        try {
            if (typeof cxDrawer === 'undefined' || typeof cxDrawer.open !== 'function') {
                toast('Drawer indisponível. Recarregue a página.', true);
                return;
            }
            var frag = cloneTpl('cx-drawer-cliente-tpl');
            if (!frag) { toast('Template do drawer não encontrado', true); return; }

            var wrapper = document.createElement('div');
            wrapper.appendChild(frag);
            var form = wrapper.querySelector('form');
            fillForm(form, cliente || {});

            populateLookupSelects(wrapper, cliente);

            bindCepLookup(wrapper);

            renderAgenciaRows(wrapper.querySelector('#cx-drawer-cliente-agencias'), cliente);
            var addBtn = wrapper.querySelector('[data-drawer-action="add-agencia"]');
            if (addBtn) {
                addBtn.addEventListener('click', function () {
                    addAgenciaRow(wrapper.querySelector('#cx-drawer-cliente-agencias'), '');
                });
            }

            cxDrawer.open({
                title: cliente ? 'Editar cliente' : 'Novo cliente',
                breadcrumb: 'CRM v3 · Cadastro',
                size: 'lg',
                contentEl: wrapper,
                split: false,
                actions: [
                    { label: 'Cancelar', variant: 'ghost', close: true },
                    {
                        label: cliente ? 'Salvar alterações' : 'Criar cliente',
                        variant: 'primary',
                        id: 'cx-drawer-cliente-submit',
                        onClick: function (ev, id) { submitCliente(form, cliente, id); }
                    }
                ]
            });

            var focusField = opts && opts.focusField;
            if (focusField) {
                var field = wrapper.querySelector('[name="' + focusField + '"]');
                if (field) {
                    setTimeout(function () {
                        if (typeof field.scrollIntoView === 'function') {
                            field.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
                        }
                        field.focus();
                    }, 80);
                }
            }
        } catch (err) {
            toast((err && err.message) || 'Não foi possível abrir o cadastro do cliente.', true);
        }
    }

    function submitCliente(form, cliente, drawerId) {
        var payload = serializeForm(form);
        payload.is_agencia = payload.perfil === 'agencia';
        payload.tipo_label = payload.is_agencia ? 'Agência' : 'Cliente final';

        // `id_tipo_cliente` agora vem como ID numérico do tbl_tipo_cliente
        // (antes eram strings "publico"/"privado" hardcoded no template).
        // Populamos `tipo` (label humano) a partir do <option> selecionado
        // para retro-compat com a UI legada; o backend usa apenas o id.
        if (payload.id_tipo_cliente) {
            var _sel = form.querySelector('select[name="id_tipo_cliente"]');
            var _opt = _sel && _sel.options[_sel.selectedIndex];
            payload.tipo = _opt ? _opt.textContent.trim() : payload.id_tipo_cliente;
            var _n = parseInt(payload.id_tipo_cliente, 10);
            if (!isNaN(_n)) payload.id_tipo_cliente = _n;
        }
        payload.categoria = payload.tipo;

        // `executivo_id` também é numérico agora (id_contato_cliente do
        // vendedor em vendas_central_comm). Convertemos para int para o
        // backend não precisar coagir a string.
        if (payload.executivo_id) {
            var _e = parseInt(payload.executivo_id, 10);
            if (!isNaN(_e)) payload.executivo_id = _e;
            var _selE = form.querySelector('select[name="executivo_id"]');
            var _optE = _selE && _selE.options[_selE.selectedIndex];
            if (_optE) payload.responsavel = _optE.textContent.trim();
        }

        payload.bv_percentual = parseFloat(payload.bv_percentual) || 0;
        payload.margem_cc = parseFloat(payload.margem_cc) || 0;
        var end = payload.endereco;
        if (end && typeof end === 'object') {
            ['cep', 'uf', 'cidade', 'bairro', 'logradouro', 'numero', 'complemento'].forEach(function (k) {
                if (end[k] != null && String(end[k]).trim() !== '') payload[k] = end[k];
            });
        }
        payload.agencias_vinculadas = coletarAgenciasVinculadasFrom(form.closest('div').querySelector('#cx-drawer-cliente-agencias'));

        var isEdit = !!(cliente && cliente.id);
        var req = isEdit
            ? apiFetch('/clientes/' + encodeURIComponent(cliente.id), { method: 'PATCH', body: payload })
            : apiFetch('/clientes', { method: 'POST', body: payload });
        req.then(function (data) {
            toast(isEdit ? 'Cliente atualizado' : 'Cliente criado');
            cxDrawer.close(drawerId);
            var novoId = (data.cliente && data.cliente.id) || (cliente && cliente.id);
            if (window.crmV3 && typeof window.crmV3.reloadClientes === 'function') {
                window.crmV3.reloadClientes(novoId);
            }
        }).catch(function (err) { toast(err.message, true); });
    }

    function renderAgenciaRows(container, cliente) {
        if (!container) return;
        container.innerHTML = '';
        var vinculos = [];
        if (cliente) {
            if (Array.isArray(cliente.agencias_vinculadas) && cliente.agencias_vinculadas.length) {
                vinculos = cliente.agencias_vinculadas;
            } else if (cliente.agencia_id) {
                vinculos = [{ agencia_id: cliente.agencia_id, is_principal: true }];
            }
        }
        if (!vinculos.length) vinculos.push({ agencia_id: '', is_principal: true });

        // Placeholder visual enquanto a lista de agências é carregada
        // (só na primeira abertura do drawer). Assim o usuário vê algo
        // imediatamente sem parecer que o drawer travou.
        var loading = document.createElement('div');
        loading.className = 'text-xs text-base-content/60 py-1';
        loading.textContent = 'Carregando agências…';
        container.appendChild(loading);

        ensureAgenciasCarregadas().then(function () {
            container.innerHTML = '';
            vinculos.forEach(function (v) { addAgenciaRow(container, v.agencia_id, v.is_principal); });
        }).catch(function (err) {
            container.innerHTML = '';
            toast(err.message || 'Falha ao carregar agências.', true);
            vinculos.forEach(function (v) { addAgenciaRow(container, v.agencia_id, v.is_principal); });
        });
    }

    function addAgenciaRow(container, selectedId, isPrincipal) {
        if (!container) return;
        var agencias = getAgencias();
        var sid = String(selectedId || '');
        // Se a agência salva não estiver na lista carregada (ex.: outra
        // filial, agência desativada), preservamos o vínculo criando
        // uma option extra "id — não encontrada". Assim o PATCH não
        // apaga o dado por engano só porque o combo não tem o item.
        var opts = ['<option value="">— Selecionar agência —</option>'];
        var achou = false;
        agencias.forEach(function (a) {
            var sel = String(a.id) === sid ? ' selected' : '';
            if (sel) achou = true;
            opts.push('<option value="' + a.id + '"' + sel + '>' + a.nome + '</option>');
        });
        if (sid && !achou) {
            opts.push('<option value="' + sid + '" selected>#' + sid + ' — (não encontrada)</option>');
        }
        var row = document.createElement('div');
        row.className = 'crm-v3-agencia-row';
        row.innerHTML = (
            '<select class="select select-bordered select-sm crm-v3-agencia-select">' + opts.join('') + '</select>' +
            '<label class="crm-v3-agencia-principal">' +
            '<input type="radio" name="cx-drawer-cliente-principal" class="radio radio-xs" ' + (isPrincipal ? 'checked' : '') + ' />' +
            '<span>Principal</span></label>' +
            '<button type="button" class="btn btn-ghost btn-xs btn-square crm-v3-agencia-remove"><i class="fa-solid fa-xmark"></i></button>'
        );
        container.appendChild(row);
        row.querySelector('.crm-v3-agencia-remove').addEventListener('click', function () {
            row.remove();
        });
    }

    function coletarAgenciasVinculadasFrom(container) {
        if (!container) return [];
        var out = [];
        $$('.crm-v3-agencia-row', container).forEach(function (row) {
            var sel = row.querySelector('.crm-v3-agencia-select');
            var principal = row.querySelector('input[name="cx-drawer-cliente-principal"]');
            if (sel && sel.value) {
                out.push({ agencia_id: sel.value, is_principal: !!(principal && principal.checked) });
            }
        });
        return out;
    }

    /* Cache de agências reais, carregado via /crm-v3/api/agencias.
       Antes o combo dependia de `state.clientes` (paginado), o que
       fazia aparecer só 2-3 agências. Agora buscamos a lista completa
       do backend uma única vez e reutilizamos em todos os drawers. */
    var _agenciasCache = null;   // Array<{id, nome}> uma vez carregado
    var _agenciasPromise = null; // dedup de chamadas concorrentes

    function ensureAgenciasCarregadas(force) {
        if (!force && Array.isArray(_agenciasCache)) {
            return Promise.resolve(_agenciasCache);
        }
        if (_agenciasPromise && !force) return _agenciasPromise;
        _agenciasPromise = apiFetch('/agencias').then(function (data) {
            var lista = (data && (data.agencias || data.data)) || [];
            _agenciasCache = lista.slice().sort(function (a, b) {
                return (a.nome || '').localeCompare(b.nome || '', 'pt-BR', { sensitivity: 'base' });
            });
            _agenciasPromise = null;
            return _agenciasCache;
        }).catch(function (err) {
            _agenciasPromise = null;
            throw err;
        });
        return _agenciasPromise;
    }

    function getAgencias() {
        // Sempre prefere o cache real; se não estiver carregado ainda
        // (ex.: drawer aberto antes do primeiro fetch), cai no fallback
        // antigo de state.clientes filtrado por is_agencia — assim o
        // combo ao menos não fica vazio.
        if (Array.isArray(_agenciasCache) && _agenciasCache.length) {
            return _agenciasCache;
        }
        var lista = (window.crmV3 && window.crmV3.state && window.crmV3.state.clientes) || [];
        return lista.filter(function (c) { return c.is_agencia; })
            .map(function (c) { return { id: c.id, nome: c.nome }; });
    }

    /* ============================================================
       Cache central de LOOKUPS (tipos_cliente, estados, setores,
       cargos, executivos reais, plataformas, classificações).
       Antes cada combo tinha <option> hardcoded no template com
       nomes mock ("Luisa Santana", "João Paulo"). Agora um único
       GET /crm-v3/api/lookups traz tudo direto do Postgres e
       populamos os selects programaticamente.
       ============================================================ */
    var _lookupsCache = null;
    var _lookupsPromise = null;

    function ensureLookupsCarregados(force) {
        if (!force && _lookupsCache) return Promise.resolve(_lookupsCache);
        if (_lookupsPromise && !force) return _lookupsPromise;
        _lookupsPromise = apiFetch('/lookups').then(function (data) {
            // Backend envia os campos no root (spread) e também em `data`.
            _lookupsCache = {
                tipos_cliente:   data.tipos_cliente   || [],
                estados:         data.estados         || [],
                setores:         data.setores         || [],
                cargos:          data.cargos          || [],
                executivos:      data.executivos      || [],
                plataformas:     data.plataformas     || [],
                classificacoes:  data.classificacoes  || []
            };
            _lookupsPromise = null;
            return _lookupsCache;
        }).catch(function (err) {
            _lookupsPromise = null;
            throw err;
        });
        return _lookupsPromise;
    }

    function getLookups() {
        return _lookupsCache || {
            tipos_cliente: [], estados: [], setores: [], cargos: [],
            executivos: [], plataformas: [], classificacoes: []
        };
    }

    /**
     * Popula um <select> a partir de uma lista de items com forma
     * {id/value, label/nome, ...}. Preserva o valor atualmente
     * selecionado, e adiciona uma option "não encontrada" quando o
     * valor salvo não aparece na lista — assim o PATCH não zera o
     * dado só porque o combo carregou tarde.
     */
    function populateSelect(select, items, opts) {
        if (!select) return;
        opts = opts || {};
        var placeholder = opts.placeholder || '— Selecionar —';
        var valueKey    = opts.valueKey    || 'id';
        var labelKey    = opts.labelKey    || 'nome';
        var current     = opts.currentValue != null ? String(opts.currentValue) : String(select.value || '');
        var htmlParts   = [];
        if (opts.allowEmpty !== false) {
            htmlParts.push('<option value="">' + placeholder + '</option>');
        }
        var achou = false;
        (items || []).forEach(function (it) {
            var val = it[valueKey] != null ? String(it[valueKey]) : '';
            var lab = it[labelKey] != null ? String(it[labelKey]) : val;
            var sel = (val === current) ? ' selected' : '';
            if (sel) achou = true;
            htmlParts.push('<option value="' + escapeAttr(val) + '"' + sel + '>' + escapeHtml(lab) + '</option>');
        });
        // Preservação de vínculo legado (mesma lógica de agências).
        if (current && !achou && current !== '') {
            htmlParts.push('<option value="' + escapeAttr(current) + '" selected>' + escapeHtml(current) + ' — (não listado)</option>');
        }
        select.innerHTML = htmlParts.join('');
    }

    function escapeHtml(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }
    function escapeAttr(s) { return escapeHtml(s); }

    // Prefetch em background após o boot da página — deixa TODOS os
    // drawers instantâneos na primeira abertura. Falhas são silenciosas
    // (os renderers usam o fallback antigo e tentam de novo).
    if (typeof window !== 'undefined') {
        var _prefetch = function () {
            ensureAgenciasCarregadas().catch(function () { /* silencioso */ });
            ensureLookupsCarregados().catch(function () { /* silencioso */ });
        };
        if (document.readyState === 'complete' || document.readyState === 'interactive') {
            setTimeout(_prefetch, 200);
        } else {
            document.addEventListener('DOMContentLoaded', function () {
                setTimeout(_prefetch, 200);
            });
        }
    }

    /**
     * Faz o scan de todos os `<select data-lookup="<chave>">` dentro de
     * `root` e popula usando o cache de lookups. Atributos suportados:
     *   - data-lookup       (obrigatório): chave do lookup (tipos_cliente|estados|...).
     *   - data-lookup-value (opcional, default: "id"): campo do item usado como value.
     *   - data-lookup-label (opcional, default: "nome"): campo do item usado como label.
     *   - data-lookup-empty (opcional): texto do placeholder vazio; se "false" omite.
     *
     * Preserva o valor atualmente selecionado (fillForm já rodou antes).
     * Se os lookups ainda não foram carregados, retorna já com os selects
     * exibindo "— Carregando… —" e re-popula assim que a promise resolver.
     */
    function populateLookupSelects(root, cliente) {
        if (!root) return;
        var selects = $$('select[data-lookup]', root);
        var datalists = $$('datalist[data-lookup-datalist]', root);
        if (!selects.length && !datalists.length) return;

        var apply = function () {
            var lookups = getLookups();
            // Datalists (autocomplete em inputs) — a "value" é usada
            // como conteúdo do <option> (input.list usa value para
            // sugerir). Não seleciona nada; só popula sugestões.
            datalists.forEach(function (dl) {
                var key = dl.getAttribute('data-lookup-datalist');
                var lista = lookups[key] || [];
                var valueKey = dl.getAttribute('data-lookup-value') || 'nome';
                dl.innerHTML = lista.map(function (it) {
                    var v = it[valueKey] != null ? String(it[valueKey]) : '';
                    return '<option value="' + escapeAttr(v) + '"></option>';
                }).join('');
            });
            selects.forEach(function (sel) {
                var key = sel.getAttribute('data-lookup');
                var lista = lookups[key] || [];
                var valueKey = sel.getAttribute('data-lookup-value') || 'id';
                var labelKey = sel.getAttribute('data-lookup-label') || 'nome';
                var placeholderAttr = sel.getAttribute('data-lookup-empty');
                var allowEmpty = placeholderAttr !== 'false';
                var placeholder = placeholderAttr && placeholderAttr !== 'false'
                    ? placeholderAttr
                    : '— Selecionar —';

                // Descobre o valor atual: se `cliente` foi passado, usamos
                // cliente[data-field] — isso resolve o caso do fillForm
                // ter rodado ANTES do lookup chegar (quando o select só
                // tinha placeholder "Carregando…"): a atribuição
                // `select.value = "7"` foi silenciosamente descartada
                // porque a option "7" ainda não existia. Sem esse
                // reforço, o select ficaria em branco na 1a abertura.
                var currentValue = sel.value;
                if (cliente) {
                    var field = sel.getAttribute('data-field');
                    if (field) {
                        var v = field.indexOf('.') >= 0
                            ? field.split('.').reduce(function (o, k) { return o ? o[k] : undefined; }, cliente)
                            : cliente[field];
                        if (v !== undefined && v !== null && v !== '') currentValue = String(v);
                    }
                }
                populateSelect(sel, lista, {
                    valueKey: valueKey,
                    labelKey: labelKey,
                    allowEmpty: allowEmpty,
                    placeholder: placeholder,
                    currentValue: currentValue
                });
            });
        };

        if (_lookupsCache) {
            apply();
        } else {
            ensureLookupsCarregados().then(apply).catch(function (err) {
                // Falha silenciosa: os placeholders "Carregando…" ficam.
                // Reportamos apenas se o usuário tentar salvar sem
                // conseguir selecionar (validação do form).
                console.warn('[crm-v3] Falha ao carregar lookups:', err && err.message);
            });
        }
    }

    // Exposto para outros módulos (crm_v3.js) reutilizarem se quiserem.
    window.crmV3Drawer = window.crmV3Drawer || {};
    window.crmV3Drawer.lookups = {
        ensure: ensureLookupsCarregados,
        get: getLookups,
        populateSelect: populateSelect,
        applyToRoot: populateLookupSelects
    };

    /* -----------------------------------------------------------
       Drawer: Atividade + IA
       ----------------------------------------------------------- */

    /**
     * Popula um <select> a partir da lista de executivos reais do
     * `window.CRM_V3_CONTEXT.executivos` (mesmo formato usado no drawer
     * de cotação). Usa o nome como VALOR — o backend
     * (`update_atividade` / `create_atividade`) resolve para
     * `executivo_id` via `_executivo_id_por_nome` ou usa o executivo
     * logado como default.
     */
    function populateAtividadeResponsaveis(select, atividade) {
        if (!select) return;
        var ctx = window.CRM_V3_CONTEXT || {};
        var lista = Array.isArray(ctx.executivos) ? ctx.executivos : [];
        // Preserva a option "— Selecionar —" (index 0) já no template.
        // Deduplica por nome porque a lista pode vir do estado do CRM.
        var vistos = {};
        lista.forEach(function (ex) {
            var nome = ex.nome_completo || ex.nome || '';
            if (!nome || vistos[nome]) return;
            vistos[nome] = true;
            var opt = document.createElement('option');
            opt.value = nome;
            opt.textContent = nome;
            select.appendChild(opt);
        });
        // Preferência de valor selecionado:
        //   1) responsavel já vindo da atividade (edição)
        //   2) responsável do cliente atualmente selecionado no CRM
        //   3) usuário logado (ctx.userName)
        var preferido = (atividade && atividade.responsavel)
            || (window.crmV3 && window.crmV3.state && window.crmV3.state.cliente && window.crmV3.state.cliente.responsavel)
            || ctx.userName
            || '';
        if (preferido) {
            var achou = false;
            for (var i = 0; i < select.options.length; i++) {
                if (select.options[i].value === preferido) { achou = true; select.selectedIndex = i; break; }
            }
            // Se não estava na lista, adiciona no topo para não perder o
            // valor (ex.: legado com nome fora do vendas_central_comm).
            if (!achou) {
                var extra = document.createElement('option');
                extra.value = preferido;
                extra.textContent = preferido;
                extra.selected = true;
                select.insertBefore(extra, select.options[1] || null);
            }
        }
    }

    /**
     * Popula o <select> de contato relacionado com os contatos do
     * cliente atualmente carregado no CRM (`state.contatos`).
     */
    function populateAtividadeContatos(select, atividade) {
        if (!select) return;
        var contatos = (window.crmV3 && window.crmV3.state && window.crmV3.state.contatos) || [];
        contatos.forEach(function (c) {
            var opt = document.createElement('option');
            opt.value = String(c.id);
            opt.textContent = c.nome + (c.cargo ? ' — ' + c.cargo : '');
            select.appendChild(opt);
        });
        var pref = atividade && (atividade.contato_id != null ? String(atividade.contato_id) : '');
        if (pref) {
            for (var i = 0; i < select.options.length; i++) {
                if (select.options[i].value === pref) { select.selectedIndex = i; break; }
            }
        }
    }

    /**
     * Conecta um grupo de chips a um <input type="hidden">. Cada chip
     * tem `data-value=X`; a hidden `data-field=<name>` recebe o valor
     * selecionado. `data-chip-group` no container define qual field
     * é alvo. Suporta valor inicial vindo do form (ex.: edição).
     */
    function wireChipGroups(wrapper, form) {
        $$('.cx-drawer-chip-group', wrapper).forEach(function (group) {
            var field = group.getAttribute('data-chip-group');
            if (!field) return;
            var hidden = form.querySelector('[data-field="' + field + '"]');
            var chips = $$('.cx-drawer-chip', group);

            function markActive(val) {
                chips.forEach(function (chip) {
                    var active = chip.getAttribute('data-value') === val;
                    chip.classList.toggle('is-active', active);
                    chip.setAttribute('aria-checked', active ? 'true' : 'false');
                });
            }

            // Sincroniza com o valor inicial da hidden.
            var initial = hidden ? hidden.value : (chips[0] && chips[0].getAttribute('data-value'));
            if (initial) markActive(initial);

            chips.forEach(function (chip) {
                chip.addEventListener('click', function () {
                    var val = chip.getAttribute('data-value');
                    if (hidden) hidden.value = val;
                    markActive(val);
                });
            });
        });
    }

    function openDrawerAtividade(atividade, clienteId, opts) {
        opts = opts || {};
        var frag = cloneTpl('cx-drawer-atividade-tpl');
        if (!frag) { toast('Template do drawer não encontrado', true); return; }
        var wrapper = document.createElement('div');
        wrapper.appendChild(frag);
        var form = wrapper.querySelector('form');

        // Popula selects ANTES do fillForm — o `data-field` só reflete
        // o valor se as <option>s já existem no DOM.
        populateAtividadeResponsaveis(wrapper.querySelector('#cx-ativ-responsavel'), atividade);
        populateAtividadeContatos(wrapper.querySelector('#cx-ativ-contato'), atividade);

        // Preenche todos os `data-field` (input/select/hidden) a partir
        // do objeto atividade. Isso alimenta as hiddens `tipo` e
        // `status` — que serão sincronizadas com os chips logo abaixo.
        fillForm(form, atividade || {});

        var tipoVal = (form.querySelector('[data-field="tipo"]') || {}).value || '';
        var fmtEl = form.querySelector('[data-field="formato"]');
        if (fmtEl && (!fmtEl.value || fmtEl.value === 'roteiro')) {
            if (tipoVal === 'email' || tipoVal === 'whatsapp') fmtEl.value = tipoVal;
        }

        // Conecta os chip-groups (Tipo, Status, Formato) à respectiva hidden.
        // Precisa vir DEPOIS do fillForm para pegar o valor inicial.
        wireChipGroups(wrapper, form);

        $$('[data-chip-group="tipo"] .cx-drawer-chip', wrapper).forEach(function (chip) {
            chip.addEventListener('click', function () {
                var val = chip.getAttribute('data-value');
                var fmt = form.querySelector('[data-field="formato"]');
                var fg = wrapper.querySelector('[data-chip-group="formato"]');
                if (!fmt || (val !== 'email' && val !== 'whatsapp')) return;
                fmt.value = val;
                if (!fg) return;
                $$('.cx-drawer-chip', fg).forEach(function (c) {
                    var active = c.getAttribute('data-value') === val;
                    c.classList.toggle('is-active', active);
                    c.setAttribute('aria-checked', active ? 'true' : 'false');
                });
            });
        });

        // IA actions
        $$('[data-ia-action]', wrapper).forEach(function (btn) {
            btn.addEventListener('click', function () {
                runIA(btn, form, wrapper.querySelector('[data-ia-output]'), clienteId);
            });
        });

        cxDrawer.open({
            title: (atividade && atividade.id) ? 'Editar atividade' : 'Nova atividade',
            breadcrumb: 'CRM v3 · Atividade',
            size: 'md',
            contentEl: wrapper,
            // Sobreposto — não empurra as colunas do CRM.
            split: false,
            actions: [
                { label: 'Cancelar', variant: 'ghost', close: true },
                {
                    label: (atividade && atividade.id) ? 'Salvar alterações' : 'Criar atividade',
                    variant: 'primary',
                    onClick: function (ev, id) { submitAtividade(form, atividade, clienteId, id); }
                }
            ]
        });

        if (opts.gerarRoteiro) {
            var roteiroBtn = wrapper.querySelector('[data-ia-action="gerar-roteiro"]');
            var outEl = wrapper.querySelector('[data-ia-output]');
            if (roteiroBtn) runIA(roteiroBtn, form, outEl, clienteId);
        }
    }

    function submitAtividade(form, atividade, clienteId, drawerId) {
        var payload = serializeForm(form);
        if (!payload.titulo || !payload.titulo.trim()) { toast('Título é obrigatório', true); return; }
        if (!payload.data) { toast('Data é obrigatória', true); return; }
        // Normalizações:
        // - status vazio → pendente (default do banco)
        // - contato_id "" (sem seleção) → null para o backend
        if (!payload.status) payload.status = 'pendente';
        if (payload.contato_id === '' || payload.contato_id == null) payload.contato_id = null;
        // Prazo vazio significa "sem prazo" — mande null para o server.
        if (!payload.data_prazo) payload.data_prazo = null;
        // Hora vazia significa "sem hora" — mande null. Só é persistido
        // no banco se a base tiver a coluna `hora_atividade` (opcional).
        if (!payload.hora) payload.hora = null;

        var isEdit = !!(atividade && atividade.id);
        var req = isEdit
            ? apiFetch('/atividades/' + encodeURIComponent(atividade.id), { method: 'PATCH', body: payload })
            : apiFetch('/clientes/' + encodeURIComponent(clienteId) + '/atividades', { method: 'POST', body: payload });
        req.then(function () {
            toast(isEdit ? 'Atividade atualizada' : 'Atividade criada');
            cxDrawer.close(drawerId);
            if (window.crmV3 && typeof window.crmV3.reloadAtividades === 'function') {
                window.crmV3.reloadAtividades();
            }
        }).catch(function (err) { toast(err.message, true); });
    }

    function stripMarkdown(s) {
        s = String(s == null ? '' : s);
        s = s.replace(/```[\s\S]*?```/g, function (m) { return m.replace(/```/g, ''); });
        s = s.replace(/^#{1,6}\s+/gm, '');
        s = s.replace(/\*\*(.+?)\*\*/g, '$1');
        s = s.replace(/__(.+?)__/g, '$1');
        s = s.replace(/`([^`]+)`/g, '$1');
        s = s.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1');
        s = s.replace(/\*\*/g, '');
        return s.trim();
    }

    function runIA(btn, form, output, clienteId) {
        var action = btn.getAttribute('data-ia-action');
        var payload = serializeForm(form);
        payload.cliente_id = clienteId;
        if (!payload.objetivo) payload.objetivo = payload.titulo || payload.descricao || '';
        var endpoint = action;
        if (action === 'gerar-comunicacao') {
            var fmt = String(payload.formato || payload.tipo || '').toLowerCase();
            if (fmt === 'sequencia') endpoint = 'touchpoints';
            else if (fmt === 'roteiro' || fmt === 'ligacao' || fmt === 'reuniao') endpoint = 'gerar-roteiro';
            else payload.tipo = fmt === 'whatsapp' ? 'whatsapp' : 'email';
        }
        btn.disabled = true;
        output.classList.add('is-visible');
        output.textContent = 'Consultando assistente…';

        apiFetch('/ia/' + endpoint, { method: 'POST', body: payload }).then(function (res) {
            var data = res.data || res;
            if (endpoint === 'melhorar-texto' || endpoint === 'gerar-roteiro') {
                var texto = stripMarkdown((data && (data.texto || data.descricao || data.texto_melhorado)) || '');
                if (texto) {
                    var desc = form.querySelector('[data-field="descricao"]');
                    if (desc) desc.value = texto;
                    output.textContent = 'Roteiro preenchido na descrição. Ajuste se precisar, execute e salve.';
                } else {
                    output.textContent = 'A IA não devolveu roteiro. Tente de novo ou escreva na descrição.';
                }
            } else if (action === 'sugerir-atividade' || endpoint === 'sugerir-atividade') {
                if (data) {
                    // Helper defensivo: só atualiza se o campo existir
                    // no drawer atual (o form de atividade pode não ter
                    // todos os campos legados como "prioridade").
                    var setField = function (name, value) {
                        if (value == null) return;
                        var el = form.querySelector('[data-field="' + name + '"]');
                        if (!el) return;
                        el.value = value;
                        // Se o field é uma hidden ligada a chip-group,
                        // reflete visualmente o novo valor.
                        var chipGroup = form.parentNode
                            && form.parentNode.querySelector
                            && form.parentNode.querySelector('.cx-drawer-chip-group[data-chip-group="' + name + '"]');
                        if (chipGroup) {
                            $$('.cx-drawer-chip', chipGroup).forEach(function (chip) {
                                var active = chip.getAttribute('data-value') === value;
                                chip.classList.toggle('is-active', active);
                                chip.setAttribute('aria-checked', active ? 'true' : 'false');
                            });
                        }
                    };
                    setField('titulo', stripMarkdown(data.titulo));
                    setField('descricao', stripMarkdown(data.descricao));
                    setField('tipo', data.tipo);
                    setField('data', data.data_sugerida);
                    output.textContent = 'Sugestão preenchida no formulário.';
                }
            } else if (endpoint === 'touchpoints') {
                var list = (data && data.touchpoints) || [];
                if (!list.length) { output.textContent = 'Sem sequência sugerida.'; }
                else {
                    output.textContent = 'Sequência sugerida:\n' + list.map(function (t) {
                        return '• ' + (t.data_sugerida || '') + ' · ' + (t.tipo || '') + ' — ' + (t.titulo || '');
                    }).join('\n') + '\n\nUse "Criar sequência" para inserir todas.';
                    // Adiciona botão dinâmico
                    if (!output.querySelector('.cx-drawer-ia-apply')) {
                        var apply = document.createElement('button');
                        apply.type = 'button';
                        apply.className = 'cx-drawer-ia-action cx-drawer-ia-apply';
                        apply.style.marginTop = '8px';
                        apply.textContent = 'Criar ' + list.length + ' atividades';
                        apply.addEventListener('click', function () {
                            Promise.all(list.map(function (t) {
                                return apiFetch('/clientes/' + encodeURIComponent(clienteId) + '/atividades', {
                                    method: 'POST',
                                    body: {
                                        titulo: stripMarkdown(t.titulo),
                                        descricao: stripMarkdown(t.descricao || ''),
                                        tipo: t.tipo || 'ligacao',
                                        prioridade: t.prioridade || 'Média',
                                        data: t.data_sugerida,
                                        hora: t.hora || '',
                                        responsavel: (window.crmV3 && window.crmV3.state && window.crmV3.state.cliente && window.crmV3.state.cliente.responsavel) || 'Luisa Santana'
                                    }
                                });
                            })).then(function () {
                                toast('Sequência criada');
                                if (window.crmV3 && typeof window.crmV3.reloadAtividades === 'function') {
                                    window.crmV3.reloadAtividades();
                                }
                                apply.disabled = true;
                            }).catch(function (err) { toast(err.message, true); });
                        });
                        output.appendChild(document.createElement('br'));
                        output.appendChild(apply);
                    }
                }
            } else if (endpoint === 'gerar-comunicacao') {
                if (data && data.mensagem) {
                    var msg = stripMarkdown(data.mensagem);
                    var descEl = form.querySelector('[data-field="descricao"]');
                    if (descEl) descEl.value = msg;
                    if (data.assunto) {
                        var titEl = form.querySelector('[data-field="titulo"]');
                        if (titEl && !(titEl.value || '').trim()) titEl.value = stripMarkdown(data.assunto);
                    }
                    output.textContent = 'Mensagem preenchida no roteiro. Revise, envie e marque a atividade como concluída.';
                    data.mensagem = msg;
                    data.assunto = stripMarkdown(data.assunto || '');
                    setTimeout(function () { openDrawerComunicacao(data, clienteId); }, 200);
                } else {
                    output.textContent = 'Sem conteúdo gerado.';
                }
            }
        }).catch(function (err) {
            output.textContent = 'Erro: ' + err.message;
        }).finally(function () {
            btn.disabled = false;
        });
    }

    function openDrawerComunicacao(data, clienteId) {
        var wrap = document.createElement('div');
        wrap.innerHTML = (
            '<div class="cx-drawer-section">' +
            '<div class="cx-drawer-section-title">Assunto</div>' +
            '<div class="cx-drawer-field"><input type="text" id="cx-com-assunto" value="' + escapeHtml(data.assunto || '') + '" /></div>' +
            '</div>' +
            '<div class="cx-drawer-section">' +
            '<div class="cx-drawer-section-title">Mensagem</div>' +
            '<div class="cx-drawer-field"><textarea rows="12" id="cx-com-body">' + escapeHtml(data.mensagem || '') + '</textarea></div>' +
            '</div>'
        );

        cxDrawer.open({
            title: 'Preparar comunicação',
            breadcrumb: 'CRM v3 · IA · Comunicação',
            size: 'md',
            contentEl: wrap,
            nested: true,
            actions: [
                { label: 'Fechar', variant: 'ghost', close: true },
                {
                    label: 'Registrar como atividade',
                    variant: 'primary',
                    onClick: function (ev, id) {
                        var assunto = wrap.querySelector('#cx-com-assunto').value;
                        var msg = wrap.querySelector('#cx-com-body').value;
                        apiFetch('/clientes/' + encodeURIComponent(clienteId) + '/atividades', {
                            method: 'POST',
                            body: {
                                titulo: assunto || 'E-mail para contato principal',
                                descricao: msg,
                                tipo: 'email',
                                prioridade: 'Média',
                                data: new Date().toISOString().slice(0, 10),
                                responsavel: (window.crmV3 && window.crmV3.state && window.crmV3.state.cliente && window.crmV3.state.cliente.responsavel) || 'Luisa Santana'
                            }
                        }).then(function () {
                            toast('E-mail registrado como atividade');
                            cxDrawer.close(id);
                            if (window.crmV3 && typeof window.crmV3.reloadAtividades === 'function') {
                                window.crmV3.reloadAtividades();
                            }
                        }).catch(function (err) { toast(err.message, true); });
                    }
                }
            ]
        });
    }

    function escapeHtml(str) {
        return String(str == null ? '' : str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    /* -----------------------------------------------------------
       Drawer: Contato
       ----------------------------------------------------------- */

    function openDrawerContato(contato, clienteId) {
        var frag = cloneTpl('cx-drawer-contato-tpl');
        if (!frag) return;
        var wrapper = document.createElement('div');
        wrapper.appendChild(frag);
        var form = wrapper.querySelector('form');
        fillForm(form, contato || {});
        // Popula cargos/setores reais (tbl_cargo_contato / tbl_setor) —
        // antes eram inputs livres, agora combos padronizados. Passa o
        // `contato` para preservar seleção existente.
        populateLookupSelects(wrapper, contato);
        cxDrawer.open({
            title: contato ? 'Editar contato' : 'Novo contato',
            breadcrumb: 'CRM v3 · Contato',
            size: 'sm',
            contentEl: wrapper,
            actions: [
                { label: 'Cancelar', variant: 'ghost', close: true },
                {
                    label: contato ? 'Salvar' : 'Criar contato',
                    variant: 'primary',
                    onClick: function (ev, id) {
                        var payload = serializeForm(form);
                        var isEdit = !!(contato && contato.id);
                        var req = isEdit
                            ? apiFetch('/contatos/' + encodeURIComponent(contato.id), { method: 'PATCH', body: payload })
                            : apiFetch('/clientes/' + encodeURIComponent(clienteId) + '/contatos', { method: 'POST', body: payload });
                        req.then(function () {
                            toast(isEdit ? 'Contato atualizado' : 'Contato criado');
                            cxDrawer.close(id);
                            if (window.crmV3 && typeof window.crmV3.reloadClientes === 'function') {
                                window.crmV3.reloadClientes();
                            }
                        }).catch(function (err) { toast(err.message, true); });
                    }
                }
            ]
        });
    }

    /* -----------------------------------------------------------
       Drawer: Cotação — Caminho A
       -----------------------------------------------------------
       Só os campos essenciais do cabeçalho (mesma Seção 1 do form
       /cotacoes/nova). Após criar, redireciona para /cotacoes/<id>/detalhes
       para o usuário completar audiência/produtos/preço/comissões.

       Ações:
       - "Salvar rascunho": cria e permanece no CRM v3.
       - "Salvar e montar cotação": cria e navega para a tela dedicada.
       ----------------------------------------------------------- */

    function populateResponsaveis(select, cotacao) {
        if (!select) return;
        var ctx = window.CRM_V3_CONTEXT || {};
        var lista = Array.isArray(ctx.executivos) ? ctx.executivos : [];
        // Mantém o placeholder que já veio do template.
        var selectedId = cotacao && (cotacao.responsavel_comercial || cotacao.responsavel_id);
        // Se não veio da cotação (nova), usa o usuário logado.
        if (!selectedId && ctx.userId) selectedId = ctx.userId;
        lista.forEach(function (ex) {
            var opt = document.createElement('option');
            opt.value = String(ex.id_contato_cliente || ex.id || '');
            opt.textContent = ex.nome_completo || ex.nome || opt.value;
            if (selectedId && String(selectedId) === opt.value) opt.selected = true;
            select.appendChild(opt);
        });
    }

    function submitCotacaoCaminhoA(form, cotacao, clienteId, drawerId, abrirMontagem) {
        var payload = serializeForm(form);
        // Sanidade mínima do lado do cliente. O server valida definitivamente.
        var nome = (payload.nome_campanha || '').trim();
        if (!nome) { toast('Nome da campanha é obrigatório', true); return; }
        if (!payload.periodo_inicio) { toast('Data de início é obrigatória', true); return; }

        var isEdit = !!(cotacao && cotacao.id);
        var req = isEdit
            ? apiFetch('/cotacoes/' + encodeURIComponent(cotacao.id), { method: 'PATCH', body: payload })
            : apiFetch('/clientes/' + encodeURIComponent(clienteId) + '/cotacoes', { method: 'POST', body: payload });

        req.then(function (resp) {
            toast(isEdit ? 'Cotação atualizada' : 'Cotação criada');
            cxDrawer.close(drawerId);
            if (window.crmV3 && typeof window.crmV3.reloadCotacoes === 'function') {
                window.crmV3.reloadCotacoes();
            }
            if (abrirMontagem) {
                // Preferência: URL vinda do backend (mais seguro se a rota mudar).
                // Fallback: /cotacoes/<id>/detalhes (padrão do módulo legado).
                var url = (resp && resp.redirect_url)
                    || (resp && resp.cotacao && resp.cotacao.detalhes_url)
                    || null;
                if (!url) {
                    var novoId = (resp && resp.cotacao && resp.cotacao.id) || (cotacao && cotacao.id);
                    if (novoId) url = '/cotacoes/' + encodeURIComponent(novoId) + '/detalhes';
                }
                if (url) {
                    // Nova aba: o usuário mantém contexto no CRM v3 e volta
                    // com um "Ctrl+W" após montar. Comportamento amigável a
                    // multi-tarefa comercial.
                    window.open(url, '_blank', 'noopener');
                }
            }
        }).catch(function (err) { toast(err.message, true); });
    }

    /* ------------------------------------------------------------
     * Cabeçalho contextual read-only do drawer de cotação.
     * ------------------------------------------------------------
     * Puxa o cliente/agência do estado atual do CRM v3 e preenche o
     * bloco `.cx-drawer-context`. Se o cliente selecionado É a
     * agência (is_agencia=true), mostra apenas a linha "Agência".
     * Caso contrário mostra Cliente e, se houver agência pai,
     * mostra também a linha "Agência". Cliente direto (sem agência)
     * mostra apenas a linha "Cliente".
     * ------------------------------------------------------------ */
    function fillContextoCotacao(wrapper, clienteId) {
        var box = wrapper.querySelector('#cx-cot-contexto');
        var clienteRow = wrapper.querySelector('#cx-cot-ctx-cliente-row');
        var agenciaRow = wrapper.querySelector('#cx-cot-ctx-agencia-row');
        var clienteVal = wrapper.querySelector('#cx-cot-ctx-cliente-nome');
        var agenciaVal = wrapper.querySelector('#cx-cot-ctx-agencia-nome');
        if (!box || !clienteRow || !agenciaRow) return;

        var cliente = (window.crmV3 && window.crmV3.state && window.crmV3.state.cliente) || null;
        // Sanidade: só usamos o state.cliente se casar com o clienteId
        // que abriu o drawer. Se abriu de um deep-link ou trocou de
        // cliente por baixo, evitamos mostrar dado inconsistente.
        if (cliente && clienteId && String(cliente.id) !== String(clienteId)) {
            cliente = null;
        }
        if (!cliente) {
            box.hidden = true;
            return;
        }

        var nome = cliente.nome || '—';
        var isAgencia = !!cliente.is_agencia;
        var agenciaNome = cliente.agencia_nome || '';

        if (isAgencia) {
            // Cliente selecionado é a própria agência — mostra só
            // "Agência: <nome>" para deixar o vínculo claro.
            clienteRow.hidden = true;
            agenciaRow.hidden = false;
            if (agenciaVal) agenciaVal.textContent = nome;
        } else {
            clienteRow.hidden = false;
            if (clienteVal) {
                clienteVal.textContent = nome;
                clienteVal.title = nome;
            }
            if (agenciaNome) {
                agenciaRow.hidden = false;
                if (agenciaVal) {
                    agenciaVal.textContent = agenciaNome;
                    agenciaVal.title = agenciaNome;
                }
            } else {
                agenciaRow.hidden = true;
            }
        }
        box.hidden = false;
    }

    /* ------------------------------------------------------------
     * Datas: defaults hoje / hoje+30d e contador de duração.
     * ------------------------------------------------------------
     * Só aplicamos defaults quando é criação (isEdit=false) e os
     * campos não vieram preenchidos. Na edição respeitamos o valor
     * salvo. `wireDuracaoCotacao` recalcula dias corridos e dias
     * úteis (seg-sex) em cada input/change e mostra hint em vermelho
     * quando fim < inicio ou qualquer campo está vazio.
     * ------------------------------------------------------------ */
    function isoHoje() {
        // Usa data local (não UTC) para não pular um dia quando o
        // fuso é negativo. `toISOString().slice(0,10)` produziria
        // resultado errado em GMT-3 perto da meia-noite.
        var d = new Date();
        var y = d.getFullYear();
        var m = String(d.getMonth() + 1).padStart(2, '0');
        var day = String(d.getDate()).padStart(2, '0');
        return y + '-' + m + '-' + day;
    }
    function isoMaisDias(baseIso, days) {
        var parts = String(baseIso || '').split('-');
        if (parts.length !== 3) return '';
        var d = new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]));
        d.setDate(d.getDate() + Number(days || 0));
        var y = d.getFullYear();
        var m = String(d.getMonth() + 1).padStart(2, '0');
        var day = String(d.getDate()).padStart(2, '0');
        return y + '-' + m + '-' + day;
    }

    function contarDias(inicioIso, fimIso) {
        // Retorna { corridos, uteis } inclusivos.
        // Considera "dia útil" apenas seg-sex; feriados ficam fora
        // desta fase para manter paridade com o campo "Duração" do
        // form legado `/cotacoes/nova` (que também não desconta
        // feriados hoje).
        var pInicio = String(inicioIso).split('-');
        var pFim = String(fimIso).split('-');
        if (pInicio.length !== 3 || pFim.length !== 3) return null;
        var a = new Date(Number(pInicio[0]), Number(pInicio[1]) - 1, Number(pInicio[2]));
        var b = new Date(Number(pFim[0]), Number(pFim[1]) - 1, Number(pFim[2]));
        if (isNaN(a.getTime()) || isNaN(b.getTime())) return null;
        if (b < a) return null;
        var corridos = Math.round((b - a) / 86400000) + 1;
        // Loop de dias úteis. 30 dias médios × ~2 anos = ~700 iter
        // máx num caso patológico; ainda barato.
        var uteis = 0;
        var cursor = new Date(a);
        for (var i = 0; i < corridos; i++) {
            var dow = cursor.getDay();
            if (dow !== 0 && dow !== 6) uteis++;
            cursor.setDate(cursor.getDate() + 1);
        }
        return { corridos: corridos, uteis: uteis };
    }

    function wireDuracaoCotacao(wrapper) {
        var inicioEl = wrapper.querySelector('#cx-cot-periodo-inicio');
        var fimEl = wrapper.querySelector('#cx-cot-periodo-fim');
        var corridosEl = wrapper.querySelector('#cx-cot-dias-corridos');
        var uteisEl = wrapper.querySelector('#cx-cot-dias-uteis');
        var hintEl = wrapper.querySelector('#cx-cot-duracao-hint');
        if (!inicioEl || !fimEl || !corridosEl || !uteisEl) return;

        function atualizar() {
            var ini = inicioEl.value;
            var fim = fimEl.value;
            if (!ini || !fim) {
                corridosEl.textContent = '—';
                uteisEl.textContent = '—';
                if (hintEl) {
                    hintEl.hidden = false;
                    hintEl.textContent = 'Preencha início e fim para calcular';
                }
                return;
            }
            var r = contarDias(ini, fim);
            if (!r) {
                corridosEl.textContent = '—';
                uteisEl.textContent = '—';
                if (hintEl) {
                    hintEl.hidden = false;
                    hintEl.textContent = 'Data de fim antes do início';
                }
                return;
            }
            corridosEl.textContent = String(r.corridos);
            uteisEl.textContent = String(r.uteis);
            if (hintEl) hintEl.hidden = true;
        }

        inicioEl.addEventListener('input', atualizar);
        inicioEl.addEventListener('change', atualizar);
        fimEl.addEventListener('input', atualizar);
        fimEl.addEventListener('change', atualizar);
        atualizar();
    }

    function openDrawerCotacao(cotacao, clienteId) {
        var frag = cloneTpl('cx-drawer-cotacao-tpl');
        if (!frag) { toast('Template do drawer não encontrado', true); return; }
        var wrapper = document.createElement('div');
        wrapper.appendChild(frag);
        var form = wrapper.querySelector('form');

        // Populações antes do fill (o `data-field` do responsável precisa
        // ter as <option>s renderizadas para conseguir setar o valor).
        populateResponsaveis(wrapper.querySelector('#cx-cot-responsavel'), cotacao);

        fillForm(form, cotacao || {});

        var isEdit = !!(cotacao && cotacao.id);

        // Cabeçalho de contexto (Cliente / Agência) — read-only.
        // Preenche a partir do state global do CRM v3.
        fillContextoCotacao(wrapper, clienteId);

        // Defaults de data: hoje / hoje+30d — só em criação e só se
        // o valor ainda estiver vazio (não sobrescreve dados de
        // edição vindos do fillForm acima).
        if (!isEdit) {
            var inicioInput = wrapper.querySelector('#cx-cot-periodo-inicio');
            var fimInput = wrapper.querySelector('#cx-cot-periodo-fim');
            var hoje = isoHoje();
            if (inicioInput && !inicioInput.value) inicioInput.value = hoje;
            if (fimInput && !fimInput.value) fimInput.value = isoMaisDias(hoje, 30);
        }

        // Contador dinâmico de duração — precisa vir DEPOIS de setar
        // os defaults acima para que a leitura inicial já mostre "31
        // dias corridos" (hoje + 30) em vez de "—".
        wireDuracaoCotacao(wrapper);

        var actions = [
            { label: 'Cancelar', variant: 'ghost', close: true },
            {
                label: isEdit ? 'Salvar alterações' : 'Salvar rascunho',
                variant: 'ghost',
                onClick: function (ev, id) {
                    submitCotacaoCaminhoA(form, cotacao, clienteId, id, false);
                }
            },
            {
                label: isEdit ? 'Salvar e abrir montagem' : 'Salvar e montar cotação',
                variant: 'primary',
                onClick: function (ev, id) {
                    submitCotacaoCaminhoA(form, cotacao, clienteId, id, true);
                }
            }
        ];

        cxDrawer.open({
            title: isEdit ? 'Editar cotação' : 'Nova cotação',
            breadcrumb: 'CRM v3 · Cotação · Cabeçalho',
            size: 'md',
            contentEl: wrapper,
            // Sobreposto ao layout — não empurra as colunas do CRM.
            split: false,
            actions: actions
        });
    }

    function openDrawerSugestoes(clienteId) {
        var list = (window.crmV3 && typeof window.crmV3.getQuickSuggestions === 'function')
            ? window.crmV3.getQuickSuggestions()
            : [];
        var wrap = document.createElement('div');
        wrap.className = 'cx-sugestoes-drawer';
        var items = list.map(function (s, i) {
            return (
                '<button type="button" class="cx-sugestao-row" data-idx="' + i + '">' +
                '<span class="cx-sugestao-row-icon"><i class="' + (s.icon || 'fa-solid fa-circle') + '" aria-hidden="true"></i></span>' +
                '<span class="cx-sugestao-row-body">' +
                '<strong>' + escapeHtml(s.titulo) + '</strong>' +
                '<span>' + escapeHtml(s.hint || '') + '</span>' +
                '</span>' +
                '<span class="cx-sugestao-row-cta">Criar com roteiro</span>' +
                '</button>'
            );
        }).join('');
        wrap.innerHTML = (
            '<p class="cx-sugestoes-intro">Mesmas sugestões da coluna Atividades. Clique para abrir o formulário com o título pronto e a IA montar o roteiro de execução.</p>' +
            (items
                ? '<div class="cx-sugestoes-list">' + items + '</div>'
                : '<p class="cx-sugestoes-empty">Nenhuma sugestão pendente neste cliente.</p>') +
            '<button type="button" class="cx-drawer-ia-action" id="cx-sugestao-ia">' +
            '<i class="fa-solid fa-wand-magic-sparkles" aria-hidden="true"></i>' +
            '<span>Pedir outra atividade à IA</span></button>'
        );
        $$('.cx-sugestao-row', wrap).forEach(function (btn) {
            btn.addEventListener('click', function () {
                var idx = parseInt(btn.getAttribute('data-idx') || '0', 10);
                var s = list[idx];
                if (!s) return;
                var d = new Date();
                d.setDate(d.getDate() + (s.daysAhead || 0));
                openDrawerAtividade({
                    titulo: s.titulo,
                    tipo: s.tipo,
                    data: d.toISOString().slice(0, 10),
                    status: 'pendente'
                }, clienteId, { gerarRoteiro: true });
            });
        });
        var iaBtn = wrap.querySelector('#cx-sugestao-ia');
        if (iaBtn) {
            iaBtn.addEventListener('click', function () {
                iaBtn.disabled = true;
                apiFetch('/ia/sugerir-atividade', { method: 'POST', body: { cliente_id: clienteId } })
                    .then(function (res) {
                        var data = res.data || res;
                        openDrawerAtividade({
                            titulo: data.titulo,
                            descricao: data.descricao,
                            tipo: data.tipo || 'atividade',
                            data: data.data_sugerida,
                            status: 'pendente'
                        }, clienteId);
                    })
                    .catch(function (err) { toast(err.message, true); })
                    .finally(function () { iaBtn.disabled = false; });
            });
        }
        cxDrawer.open({
            title: 'Sugestões de atividade',
            breadcrumb: 'CRM v3 · Próximos passos',
            size: 'md',
            contentEl: wrap,
            split: false,
            actions: [{ label: 'Fechar', variant: 'ghost', close: true }]
        });
    }

    /* -----------------------------------------------------------
       Expose e integração
       ----------------------------------------------------------- */

    window.crmV3Drawer = Object.assign(window.crmV3Drawer || {}, {
        openCliente: openDrawerCliente,
        openAtividade: openDrawerAtividade,
        openContato: openDrawerContato,
        openCotacao: openDrawerCotacao,
        openSugestoes: openDrawerSugestoes,
    });

    // Redireciona os botões existentes para usar drawer no lugar dos modais grandes.
    document.addEventListener('DOMContentLoaded', function () {
        // Novo cliente (header e coluna)
        ['crm-v3-btn-novo-cliente-header'].forEach(function (id) {
            var btn = document.getElementById(id);
            if (!btn) return;
            btn.addEventListener('click', function (ev) {
                ev.stopImmediatePropagation();
                ev.preventDefault();
                openDrawerCliente(null);
            }, true);
        });

        // Editar cliente (menu 3 pontinhos)
        document.addEventListener('click', function (ev) {
            var el = ev.target;
            if (!el) return;

            var editBtn = el.closest ? el.closest('.crm-v3-header-action-edit') : null;
            if (editBtn) {
                ev.stopImmediatePropagation();
                ev.preventDefault();
                var cliente = window.crmV3 && window.crmV3.state && window.crmV3.state.cliente;
                if (!cliente) { toast('Selecione um cliente', true); return; }
                openDrawerCliente(cliente, {
                    focusField: editBtn.getAttribute('data-focus-field') || ''
                });
                return;
            }

            // Nova atividade
            if (el.id === 'crm-v3-btn-nova-atividade' || (el.closest && el.closest('#crm-v3-btn-nova-atividade'))) {
                ev.stopImmediatePropagation();
                ev.preventDefault();
                var clienteId = window.crmV3 && window.crmV3.state && window.crmV3.state.clienteId;
                if (!clienteId) { toast('Selecione um cliente', true); return; }
                openDrawerAtividade(null, clienteId);
                return;
            }

            // Nova cotação
            if (el.id === 'crm-v3-btn-nova-cotacao' || (el.closest && el.closest('#crm-v3-btn-nova-cotacao'))) {
                ev.stopImmediatePropagation();
                ev.preventDefault();
                var cid = window.crmV3 && window.crmV3.state && window.crmV3.state.clienteId;
                if (!cid) { toast('Selecione um cliente', true); return; }
                openDrawerCotacao(null, cid);
                return;
            }

            // Novo contato
            if (el.id === 'crm-v3-btn-novo-contato' || (el.closest && el.closest('#crm-v3-btn-novo-contato'))) {
                ev.stopImmediatePropagation();
                ev.preventDefault();
                var ccid = window.crmV3 && window.crmV3.state && window.crmV3.state.clienteId;
                if (!ccid) { toast('Selecione um cliente', true); return; }
                openDrawerContato(null, ccid);
                return;
            }
        }, true);
    });
})();
