/**
 * CRM v3 Drawers — editores off-canvas de cliente, atividade, cotação e contato.
 *
 * Estratégia
 * ----------
 * Os cadastros extensos têm um único fluxo no cxDrawer. O submit envia pelas
 * APIs REST do CRM v3 e notifica a página para atualizar os dados exibidos.
 */
(function () {
    'use strict';

    var API_BASE = '/crm-v3/api';

    function $(sel, root) { return (root || document).querySelector(sel); }
    function $$(sel, root) {
        return Array.prototype.slice.call((root || document).querySelectorAll(sel));
    }

    function notifyEntityUpdated(type, id) {
        if (!id) return;
        window.dispatchEvent(new CustomEvent('centralx:entity-updated', {
            detail: { entity_type: type, entity_id: String(id) }
        }));
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
            updateClienteAddressSummary(root);
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

    function updateClienteAddressSummary(root) {
        var summary = root.querySelector('#cx-cliente-endereco-resumo');
        if (!summary) return;
        var value = function (field) {
            var el = root.querySelector('[data-field="endereco.' + field + '"]');
            return el ? String(el.value || '').trim() : '';
        };
        var cidade = value('cidade');
        var uf = value('uf');
        var cep = value('cep');
        var logradouro = value('logradouro');
        var localidade = cidade && uf ? cidade + '/' + uf : (cidade || uf);
        summary.textContent = localidade || cep || logradouro || 'Não informado';
    }

    function wireClienteAddressSummary(root) {
        var address = root.querySelector('.crm-v3-cliente-address');
        if (!address) return;
        address.addEventListener('input', function () {
            updateClienteAddressSummary(root);
        });
        address.addEventListener('change', function () {
            updateClienteAddressSummary(root);
        });
        updateClienteAddressSummary(root);
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
            var formData = cliente || {
                pessoa: 'J',
                perfil: 'direto',
                classificacao_cliente: 'Prospecção',
                bv_percentual: 0,
                margem_cc: 0
            };
            fillForm(form, formData);

            populateLookupSelects(wrapper, formData);

            bindCepLookup(wrapper);
            wireClienteAddressSummary(wrapper);

            renderAgenciaRows(wrapper.querySelector('#cx-drawer-cliente-agencias'), cliente);
            wireAgenciaSearch(wrapper);

            cxDrawer.open({
                title: cliente ? 'Editar cliente' : 'Novo cliente',
                breadcrumb: 'CRM v3 · Cadastro',
                size: 'xl',
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
        if (!form || !form.reportValidity()) return;
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
            notifyEntityUpdated('cliente', novoId);
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

        var loading = document.createElement('div');
        loading.className = 'crm-v3-cliente-agencias-empty';
        loading.textContent = 'Carregando agências…';
        container.appendChild(loading);

        ensureAgenciasCarregadas().then(function () {
            container.innerHTML = '';
            vinculos.forEach(function (v) { addAgenciaRow(container, v.agencia_id, v.is_principal); });
            updateAgenciaManager(container);
        }).catch(function (err) {
            container.innerHTML = '';
            toast(err.message || 'Falha ao carregar agências.', true);
            vinculos.forEach(function (v) { addAgenciaRow(container, v.agencia_id, v.is_principal); });
            updateAgenciaManager(container);
        });
    }

    function addAgenciaRow(container, selectedId, isPrincipal) {
        if (!container || !selectedId) return;
        var agencias = getAgencias();
        var sid = String(selectedId || '');
        var duplicate = $$('.crm-v3-agencia-select', container).some(function (sel) {
            return String(sel.value) === sid;
        });
        if (duplicate) return;
        var agencia = agencias.find(function (a) { return String(a.id) === sid; });
        var nome = agencia ? agencia.nome : ('Agência #' + sid + ' (não encontrada)');
        var cnpj = agencia && agencia.cnpj ? agencia.cnpj : '';
        var shouldBePrincipal = !!isPrincipal || !container.querySelector('.crm-v3-agencia-row');
        var row = document.createElement('div');
        row.className = 'crm-v3-agencia-row';
        row.innerHTML = (
            '<select class="crm-v3-agencia-select" aria-hidden="true" tabindex="-1">' +
            '<option value="' + escapeAttr(sid) + '" selected>' + escapeHtml(nome) + '</option></select>' +
            '<span class="crm-v3-agencia-icon" aria-hidden="true"><i class="fa-solid fa-building"></i></span>' +
            '<span class="crm-v3-agencia-info"><strong>' + escapeHtml(nome) + '</strong>' +
            (cnpj ? '<small>' + escapeHtml(cnpj) + '</small>' : '<small>Agência vinculada</small>') + '</span>' +
            '<label class="crm-v3-agencia-principal">' +
            '<input type="radio" name="cx-drawer-cliente-principal" class="cx-radio cx-radio-sm" ' + (shouldBePrincipal ? 'checked' : '') + ' />' +
            '<span>Principal</span></label>' +
            '<button type="button" class="crm-v3-agencia-remove" aria-label="Remover vínculo com ' + escapeAttr(nome) + '">' +
            '<i class="fa-solid fa-xmark" aria-hidden="true"></i></button>'
        );
        container.appendChild(row);
        row.querySelector('input[type="radio"]').addEventListener('change', function () {
            updateAgenciaManager(container);
        });
        row.querySelector('.crm-v3-agencia-remove').addEventListener('click', function () {
            var wasPrincipal = !!row.querySelector('input[type="radio"]:checked');
            row.remove();
            if (wasPrincipal) {
                var next = container.querySelector('input[name="cx-drawer-cliente-principal"]');
                if (next) next.checked = true;
            }
            updateAgenciaManager(container);
        });
        updateAgenciaManager(container);
    }

    function updateAgenciaManager(container) {
        if (!container) return;
        var rows = $$('.crm-v3-agencia-row', container);
        var root = container.closest('.crm-v3-cliente-editor');
        var count = root && root.querySelector('#cx-drawer-cliente-agencias-count');
        if (count) count.textContent = String(rows.length);
        var empty = container.querySelector('.crm-v3-cliente-agencias-empty');
        if (!rows.length && !empty) {
            empty = document.createElement('div');
            empty.className = 'crm-v3-cliente-agencias-empty';
            empty.innerHTML = '<i class="fa-regular fa-building" aria-hidden="true"></i>' +
                '<strong>Nenhuma agência vinculada</strong>' +
                '<span>Use a busca acima para adicionar.</span>';
            container.appendChild(empty);
        } else if (rows.length && empty) {
            empty.remove();
        }
    }

    function wireAgenciaSearch(root) {
        var input = root.querySelector('#cx-drawer-cliente-agencia-search');
        var results = root.querySelector('#cx-drawer-cliente-agencia-results');
        var container = root.querySelector('#cx-drawer-cliente-agencias');
        if (!input || !results || !container) return;

        function normalize(value) {
            return String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
        }

        function closeResults() {
            results.hidden = true;
            results.innerHTML = '';
            input.setAttribute('aria-expanded', 'false');
        }

        function renderResults() {
            var query = normalize(input.value).trim();
            if (!query) {
                closeResults();
                return;
            }
            var queryDigits = query.replace(/\D/g, '');
            var selected = new Set($$('.crm-v3-agencia-select', container).map(function (sel) {
                return String(sel.value);
            }));
            var matches = getAgencias().filter(function (agencia) {
                if (selected.has(String(agencia.id))) return false;
                var cnpj = normalize(agencia.cnpj);
                return normalize(agencia.nome).includes(query)
                    || cnpj.includes(query)
                    || (queryDigits.length >= 3 && cnpj.replace(/\D/g, '').includes(queryDigits));
            }).slice(0, 8);
            results.innerHTML = '';
            matches.forEach(function (agencia) {
                var button = document.createElement('button');
                button.type = 'button';
                button.setAttribute('role', 'option');
                button.innerHTML = '<i class="fa-solid fa-building" aria-hidden="true"></i><span><strong>' +
                    escapeHtml(agencia.nome) + '</strong>' +
                    (agencia.cnpj ? '<small>' + escapeHtml(agencia.cnpj) + '</small>' : '') + '</span>';
                button.addEventListener('click', function () {
                    addAgenciaRow(container, agencia.id, false);
                    input.value = '';
                    closeResults();
                    input.focus();
                });
                results.appendChild(button);
            });
            if (!matches.length) {
                results.innerHTML = '<div class="crm-v3-cliente-agencia-no-results">Nenhuma agência encontrada</div>';
            }
            results.hidden = false;
            input.setAttribute('aria-expanded', 'true');
        }

        input.addEventListener('input', renderResults);
        input.addEventListener('keydown', function (event) {
            if (event.key === 'Escape') {
                input.value = '';
                closeResults();
            } else if (event.key === 'ArrowDown') {
                var first = results.querySelector('button');
                if (first) {
                    event.preventDefault();
                    first.focus();
                }
            }
        });
        results.addEventListener('keydown', function (event) {
            if (event.key === 'Escape') {
                closeResults();
                input.focus();
                return;
            }
            if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
                var options = $$('button', results);
                var current = options.indexOf(document.activeElement);
                if (!options.length) return;
                event.preventDefault();
                var next = event.key === 'ArrowDown' ? current + 1 : current - 1;
                if (next >= options.length) next = 0;
                if (next < 0) next = options.length - 1;
                options[next].focus();
            }
        });
        root.addEventListener('click', function (event) {
            var search = input.closest('.crm-v3-cliente-agencia-search');
            if (!results.contains(event.target) && !(search && search.contains(event.target))) {
                closeResults();
            }
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

    /** Popula o responsável usando o ID real de vendas_central_comm. */
    function populateAtividadeResponsaveis(select, atividade) {
        if (!select) return;
        var ctx = window.CRM_V3_CONTEXT || {};
        var lista = Array.isArray(ctx.executivos) ? ctx.executivos : [];
        var vistos = {};
        lista.forEach(function (ex) {
            var nome = ex.nome_completo || ex.nome || '';
            var id = ex.id_contato_cliente || ex.id || '';
            if (!nome || !id || vistos[String(id)]) return;
            vistos[String(id)] = true;
            var opt = document.createElement('option');
            opt.value = String(id);
            opt.textContent = nome;
            select.appendChild(opt);
        });
        var cliente = window.crmV3 && window.crmV3.state && window.crmV3.state.cliente;
        var preferido = (atividade && atividade.executivo_id)
            || (cliente && cliente.executivo_id)
            || ctx.userId
            || '';
        if (preferido) {
            var achou = false;
            for (var i = 0; i < select.options.length; i++) {
                if (select.options[i].value === String(preferido)) {
                    achou = true;
                    select.selectedIndex = i;
                    break;
                }
            }
            if (!achou) {
                var extra = document.createElement('option');
                extra.value = String(preferido);
                extra.textContent = (atividade && atividade.responsavel) || ('Executivo #' + preferido);
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
            opt.dataset.email = c.email || '';
            opt.dataset.name = c.nome || '';
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

    function fillAtividadeContext(wrapper, clienteId) {
        var target = wrapper.querySelector('[data-atividade-cliente]');
        if (!target) return;
        var state = window.crmV3 && window.crmV3.state;
        var cliente = state && state.cliente;
        if (cliente && String(cliente.id) === String(clienteId)) {
            target.textContent = cliente.nome || ('Cliente #' + clienteId);
            return;
        }
        target.textContent = clienteId ? ('Cliente #' + clienteId) : '—';
    }

    function applyTextSafely(form, texto) {
        var desc = form.querySelector('[data-field="descricao"]');
        texto = stripMarkdown(texto || '');
        if (!desc || !texto) return false;
        desc.value = texto;
        desc.focus();
        return true;
    }

    function addIaHistory(wrapper, form, item) {
        if (!wrapper || !item || !item.texto) return;
        var section = wrapper.querySelector('[data-ia-history-section]');
        var list = wrapper.querySelector('[data-ia-history]');
        if (!section || !list) return;
        section.hidden = false;
        var row = document.createElement('div');
        row.className = 'cx-atividade-ia-history-item';
        var copy = document.createElement('div');
        copy.className = 'cx-atividade-ia-history-copy';
        var meta = document.createElement('strong');
        meta.textContent = (item.label || 'Roteiro') + (item.source ? ' — ' + item.source : '');
        var text = document.createElement('span');
        text.textContent = item.texto;
        copy.appendChild(meta);
        copy.appendChild(text);
        var apply = document.createElement('button');
        apply.type = 'button';
        apply.className = 'cx-atividade-ia-history-apply';
        apply.textContent = item.canApply ? 'Aplicar no registro' : 'Copiar';
        apply.addEventListener('click', function () {
            if (!item.canApply) {
                navigator.clipboard.writeText(item.texto).then(function () {
                    toast('Conteúdo copiado');
                }).catch(function () { toast('Não foi possível copiar', true); });
                return;
            }
            if (!applyTextSafely(form, item.texto)) return;
            if (item.historyId) {
                apiFetch('/ia/historico/' + encodeURIComponent(item.historyId) + '/aplicar', {
                    method: 'PATCH',
                    body: {}
                }).catch(function () { /* migration opcional */ });
            }
        });
        row.appendChild(copy);
        row.appendChild(apply);
        list.insertBefore(row, list.firstChild);
    }

    function loadIaHistory(wrapper, form, clienteId) {
        if (!clienteId) return;
        apiFetch('/clientes/' + encodeURIComponent(clienteId) + '/ia/historico?limit=8')
            .then(function (res) {
                var data = res.data || res;
                var items = data.historico || (Array.isArray(data) ? data : []);
                items.slice().reverse().forEach(function (item) {
                    if (['gerar-roteiro', 'melhorar-texto'].indexOf(item.function) === -1) return;
                    var content = item.content || {};
                    var texto = content.texto || content.mensagem || content.titulo || '';
                    if (!texto) return;
                    addIaHistory(wrapper, form, {
                        label: item.function === 'melhorar-texto' ? 'Registro revisado' : 'Roteiro',
                        source: item.source === 'openrouter' ? 'IA' : 'fallback',
                        texto: stripMarkdown(texto),
                        historyId: item.id,
                        canApply: item.function === 'melhorar-texto'
                    });
                });
            }).catch(function () { /* migration ainda não aplicada */ });
    }

    function wireAtividadeModelo(wrapper, form) {
        var btn = wrapper.querySelector('[data-atividade-modelo]');
        if (!btn) return;
        btn.addEventListener('click', function () {
            var tipo = (form.querySelector('[data-field="tipo"]') || {}).value || 'atividade';
            var modelos = {
                ligacao: 'Objetivo: \n\nPerguntas principais:\n- \n- \n\nArgumentos e informações:\n- \n\nPróximo passo combinado: ',
                reuniao: 'Objetivo da reunião: \n\nAgenda:\n- Contexto e alinhamento\n- Necessidades e prioridades\n- Proposta de próximo passo\n\nDecisões e responsáveis: ',
                email: 'Objetivo da mensagem: \n\nContexto: \n\nPontos principais:\n- \n- \n\nChamada para ação: ',
                whatsapp: 'Objetivo da conversa: \n\nMensagem principal: \n\nPergunta de fechamento: ',
                planejamento: 'Objetivo: \n\nCenário atual: \n\nAções:\n- \n- \n\nPrazo e responsável: ',
                atividade: 'Objetivo: \n\nO que executar:\n- \n- \n\nResultado esperado: \n\nPróximo passo: '
            };
            applyTextSafely(form, modelos[tipo] || modelos.atividade);
        });
    }

    function setupMeetingEditor(wrapper, form, atividade) {
        var panel = wrapper.querySelector('[data-meeting-panel]');
        var attendeesEl = wrapper.querySelector('[data-meeting-attendees]');
        var attendeeInput = wrapper.querySelector('[data-meeting-attendee-input]');
        var attendeeAdd = wrapper.querySelector('[data-meeting-attendee-add]');
        var eventStatus = wrapper.querySelector('[data-meeting-event-status]');
        var preview = wrapper.querySelector('[data-meeting-preview]');
        var contactSelect = form.querySelector('[data-field="contato_id"]');
        var dateLabel = wrapper.querySelector('[data-activity-date-label]');
        var attendees = [];
        var currentMeeting = null;
        var activityRef = atividade || null;

        function addAttendee(email, name, source) {
            email = String(email || '').trim().toLowerCase();
            if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return false;
            if (attendees.some(function (item) { return item.email === email; })) return true;
            attendees.push({ email: email, name: name || '', source: source || 'manual' });
            renderAttendees();
            return true;
        }

        function addRelatedContact() {
            if (!contactSelect || !contactSelect.selectedOptions.length) return;
            var option = contactSelect.selectedOptions[0];
            if (option.dataset.email) {
                addAttendee(option.dataset.email, option.dataset.name, 'contact');
            }
        }

        function renderAttendees() {
            if (!attendeesEl) return;
            attendeesEl.replaceChildren();
            attendees.forEach(function (item, index) {
                var chip = document.createElement('span');
                chip.className = 'cx-meeting-attendee-chip';
                var text = document.createElement('span');
                text.textContent = item.name ? item.name + ' · ' + item.email : item.email;
                var remove = document.createElement('button');
                remove.type = 'button';
                remove.setAttribute('aria-label', 'Remover ' + item.email);
                remove.innerHTML = '<i class="fa-solid fa-xmark" aria-hidden="true"></i>';
                remove.addEventListener('click', function () {
                    attendees.splice(index, 1);
                    renderAttendees();
                });
                chip.append(text, remove);
                attendeesEl.appendChild(chip);
            });
            renderPreview();
        }

        function renderPreview() {
            if (!preview) return;
            var title = (form.querySelector('[data-field="titulo"]') || {}).value || 'Reunião';
            var date = (form.querySelector('[data-field="data"]') || {}).value || 'data pendente';
            var time = (form.querySelector('[data-field="hora"]') || {}).value || 'hora pendente';
            var duration = (wrapper.querySelector('[data-meeting-field="duration_minutes"]') || {}).value || '30';
            preview.replaceChildren();
            var strong = document.createElement('strong');
            var detail = document.createElement('span');
            strong.textContent = title;
            detail.textContent = date + ' às ' + time + ' · ' + duration +
                ' min · ' + attendees.length + ' convidado(s)';
            preview.append(strong, detail);
        }

        function renderStatus(meeting) {
            currentMeeting = meeting || null;
            if (!eventStatus || !meeting) {
                if (eventStatus) eventStatus.hidden = true;
                return;
            }
            eventStatus.hidden = false;
            eventStatus.replaceChildren();
            var message = document.createElement('span');
            var labels = {
                draft: 'Reunião salva no CRM; convite ainda não enviado.',
                syncing: 'Sincronizando com o Google Calendar…',
                synced: 'Convite sincronizado com o Google Calendar.',
                error: meeting.sync_error || 'Não foi possível sincronizar o convite.',
                cancelled: 'Evento cancelado no Google Calendar.'
            };
            message.textContent = labels[meeting.sync_status] || 'Estado da reunião atualizado.';
            eventStatus.appendChild(message);
            if (meeting.meet_url) {
                var meet = document.createElement('a');
                meet.href = meeting.meet_url;
                meet.target = '_blank';
                meet.rel = 'noopener noreferrer';
                meet.textContent = 'Abrir Meet';
                eventStatus.appendChild(meet);
            }
            if (activityRef && activityRef.id && meeting.sync_status === 'error') {
                var retry = document.createElement('button');
                retry.type = 'button';
                retry.textContent = 'Tentar novamente';
                retry.addEventListener('click', function () {
                    retry.disabled = true;
                    apiFetch('/atividades/' + encodeURIComponent(activityRef.id) + '/reuniao/sincronizar', {
                        method: 'POST', body: {}
                    }).then(function (res) {
                        renderStatus((res.data && res.data.meeting) || res.meeting || res.data);
                    }).catch(function (error) {
                        toast(error.message, true);
                    }).finally(function () { retry.disabled = false; });
                });
                eventStatus.appendChild(retry);
            }
            if (activityRef && activityRef.id && meeting.google_event_id && meeting.sync_status !== 'cancelled') {
                var cancel = document.createElement('button');
                cancel.type = 'button';
                cancel.className = 'is-danger';
                cancel.textContent = 'Cancelar convite';
                cancel.addEventListener('click', function () {
                    window.showConfirm({
                        title: 'Cancelar convite',
                        message: 'O evento será cancelado no Google Calendar e os convidados serão avisados.',
                        theme: 'danger',
                        confirmText: 'Cancelar evento',
                        onConfirm: function () {
                            cancel.disabled = true;
                            apiFetch('/atividades/' + encodeURIComponent(activityRef.id) + '/reuniao/evento', {
                                method: 'DELETE'
                            }).then(function (res) {
                                renderStatus((res.data && res.data.meeting) || res.meeting || res.data);
                            }).catch(function (error) {
                                toast(error.message, true);
                            }).finally(function () { cancel.disabled = false; });
                        }
                    });
                });
                eventStatus.appendChild(cancel);
            }
        }

        function toggle(value) {
            var visible = value === 'reuniao';
            if (panel) panel.hidden = !visible;
            if (dateLabel) {
                dateLabel.innerHTML = visible
                    ? 'Data da reunião <span class="cx-required">*</span>'
                    : 'Data planejada <span class="cx-required">*</span>';
            }
            if (visible) addRelatedContact();
        }

        if (attendeeAdd) {
            attendeeAdd.addEventListener('click', function () {
                if (!addAttendee(attendeeInput.value, '', 'manual')) {
                    toast('Informe um e-mail válido para o convidado', true);
                    return;
                }
                attendeeInput.value = '';
                attendeeInput.focus();
            });
        }
        if (attendeeInput) {
            attendeeInput.addEventListener('keydown', function (event) {
                if (event.key === 'Enter') {
                    event.preventDefault();
                    attendeeAdd.click();
                }
            });
        }
        if (contactSelect) contactSelect.addEventListener('change', addRelatedContact);
        [
            form.querySelector('[data-field="titulo"]'),
            form.querySelector('[data-field="data"]'),
            form.querySelector('[data-field="hora"]'),
            wrapper.querySelector('[data-meeting-field="duration_minutes"]')
        ].forEach(function (field) {
            if (field) field.addEventListener('input', renderPreview);
        });
        renderPreview();

        if (atividade && atividade.id && atividade.tipo === 'reuniao') {
            apiFetch('/atividades/' + encodeURIComponent(atividade.id) + '/reuniao')
                .then(function (res) {
                    var meeting = (res.data && res.data.meeting) || res.meeting || res.data;
                    if (!meeting) return;
                    attendees = (meeting.attendees || []).map(function (item) {
                        return { email: item.email, name: item.name || '', source: item.source || 'manual' };
                    });
                    var duration = wrapper.querySelector('[data-meeting-field="duration_minutes"]');
                    var timezone = wrapper.querySelector('[data-meeting-field="timezone"]');
                    var sync = wrapper.querySelector('[data-meeting-field="sync_google"]');
                    if (duration && meeting.starts_at && meeting.ends_at) {
                        duration.value = String(Math.round(
                            (new Date(meeting.ends_at) - new Date(meeting.starts_at)) / 60000
                        ));
                    }
                    if (timezone) timezone.value = meeting.timezone || 'America/Sao_Paulo';
                    if (sync) {
                        sync.checked = meeting.sync_status === 'synced'
                            || meeting.sync_status === 'error'
                            || Boolean(meeting.google_event_id);
                    }
                    renderAttendees();
                    renderStatus(meeting);
                }).catch(function () { /* migration ainda não aplicada */ });
        }

        return {
            toggle: toggle,
            payload: function () {
                var duration = wrapper.querySelector('[data-meeting-field="duration_minutes"]');
                var timezone = wrapper.querySelector('[data-meeting-field="timezone"]');
                var sync = wrapper.querySelector('[data-meeting-field="sync_google"]');
                return {
                    duration_minutes: Number(duration && duration.value || 30),
                    timezone: timezone && timezone.value || 'America/Sao_Paulo',
                    attendees: attendees.slice(),
                    sync_google: Boolean(sync && sync.checked)
                };
            },
            renderStatus: renderStatus,
            setActivity: function (value) { activityRef = value || activityRef; },
            current: function () { return currentMeeting; }
        };
    }

    var _atividadeDrawerId = null;

    function openDrawerAtividade(atividade, clienteId, opts) {
        opts = opts || {};
        // Defesa contra clique duplo e contra listeners legados duplicados:
        // só pode existir um editor de atividade aberto por vez.
        if (_atividadeDrawerId
            && typeof cxDrawer !== 'undefined'
            && typeof cxDrawer.isOpen === 'function'
            && cxDrawer.isOpen(_atividadeDrawerId)) {
            var aberto = document.getElementById(_atividadeDrawerId);
            if (aberto) aberto.focus();
            return _atividadeDrawerId;
        }
        var frag = cloneTpl('cx-drawer-atividade-tpl');
        if (!frag) { toast('Template do drawer não encontrado', true); return; }
        var wrapper = document.createElement('div');
        wrapper.appendChild(frag);
        var form = wrapper.querySelector('form');

        // Popula selects ANTES do fillForm — o `data-field` só reflete
        // o valor se as <option>s já existem no DOM.
        populateAtividadeResponsaveis(wrapper.querySelector('#cx-ativ-responsavel'), atividade);
        populateAtividadeContatos(wrapper.querySelector('#cx-ativ-contato'), atividade);
        fillAtividadeContext(wrapper, clienteId);

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
        wireAtividadeModelo(wrapper, form);
        loadIaHistory(wrapper, form, clienteId);
        var meetingEditor = setupMeetingEditor(wrapper, form, atividade);

        function syncAssistantChannel(value) {
            var fmt = form.querySelector('[data-field="formato"]');
            var label = wrapper.querySelector('[data-ia-channel-label]');
            var generate = wrapper.querySelector('[data-ia-action="gerar-roteiro"]');
            var channel = value === 'email' || value === 'whatsapp' ? value : 'roteiro';
            if (fmt) fmt.value = channel;
            var labels = {
                email: 'E-mail com assunto e mensagem',
                whatsapp: 'Mensagem pronta para WhatsApp',
                ligacao: 'Abertura e perguntas para ligação',
                reuniao: 'Abertura e perguntas para reunião'
            };
            if (label) label.textContent = labels[value] || 'Abordagem para a atividade';
            if (generate) {
                generate.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles" aria-hidden="true"></i> ' +
                    (value === 'email' ? 'Gerar e-mail' : value === 'whatsapp'
                        ? 'Gerar mensagem' : 'Gerar abordagem');
            }
        }
        syncAssistantChannel(tipoVal);
        meetingEditor.toggle(tipoVal);

        $$('[data-chip-group="tipo"] .cx-drawer-chip', wrapper).forEach(function (chip) {
            chip.addEventListener('click', function () {
                var val = chip.getAttribute('data-value');
                syncAssistantChannel(val);
                meetingEditor.toggle(val);
            });
        });

        // IA actions
        $$('[data-ia-action]', wrapper).forEach(function (btn) {
            btn.addEventListener('click', function () {
                runIA(btn, form, wrapper.querySelector('[data-ia-output]'), clienteId, wrapper);
            });
        });

        _atividadeDrawerId = cxDrawer.open({
            title: (atividade && atividade.id) ? 'Editar atividade' : 'Nova atividade',
            breadcrumb: 'CRM v3 · Atividade',
            size: 'editor',
            contentEl: wrapper,
            // Sobreposto — não empurra as colunas do CRM.
            split: false,
            onClose: function (id) {
                if (_atividadeDrawerId === id) _atividadeDrawerId = null;
            },
            actions: [
                { label: 'Cancelar', variant: 'ghost', close: true },
                {
                    label: (atividade && atividade.id) ? 'Salvar alterações' : 'Criar atividade',
                    variant: 'primary',
                    id: 'cx-drawer-atividade-submit',
                    onClick: function (ev, id) {
                        submitAtividade(
                            form, atividade, clienteId, id, ev.currentTarget,
                            meetingEditor
                        );
                    }
                }
            ]
        });

        if (opts.gerarRoteiro) {
            var roteiroBtn = wrapper.querySelector('[data-ia-action="gerar-roteiro"]');
            var outEl = wrapper.querySelector('[data-ia-output]');
            if (roteiroBtn) runIA(roteiroBtn, form, outEl, clienteId, wrapper);
        }
        return _atividadeDrawerId;
    }

    function submitAtividade(form, atividade, clienteId, drawerId, submitBtn, meetingEditor) {
        if (form.dataset.submitting === '1') return;
        if (typeof form.reportValidity === 'function' && !form.reportValidity()) return;
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
        if (payload.tipo === 'reuniao' && meetingEditor) {
            payload.meeting = meetingEditor.payload();
            if (!payload.hora) {
                toast('Informe a hora de início da reunião', true);
                return;
            }
            if (payload.meeting.sync_google) {
                var googleStatus = form.querySelector('[data-meeting-sync]');
                if (googleStatus && googleStatus.dataset.googleConnected !== 'true') {
                    toast('Conecte o Google Calendar no seu perfil ou salve sem enviar o convite.', true);
                    return;
                }
            }
        }

        function persist() {
            form.dataset.submitting = '1';
            form.setAttribute('aria-busy', 'true');
            var submitLabel = submitBtn ? submitBtn.textContent : '';
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin" aria-hidden="true"></i> Salvando…';
            }
            var isEdit = !!(atividade && atividade.id);
            var req = isEdit
                ? apiFetch('/atividades/' + encodeURIComponent(atividade.id), { method: 'PATCH', body: payload })
                : apiFetch('/clientes/' + encodeURIComponent(clienteId) + '/atividades', { method: 'POST', body: payload });
            req.then(function (res) {
                var meeting = res.meeting || (res.data && res.data.meeting);
                if (meetingEditor && (res.atividade || res.data)) {
                    meetingEditor.setActivity(res.atividade || res.data);
                }
                if (meeting && meeting.sync_status === 'error') {
                    meetingEditor.renderStatus(meeting);
                    toast('Atividade salva, mas o convite não foi sincronizado.', true);
                    notifyEntityUpdated('cliente', clienteId);
                    return;
                }
                toast(isEdit ? 'Atividade atualizada' : 'Atividade criada');
                notifyEntityUpdated('cliente', clienteId);
                cxDrawer.close(drawerId);
                if (window.crmV3 && typeof window.crmV3.reloadAtividades === 'function') {
                    window.crmV3.reloadAtividades();
                }
            }).catch(function (err) {
                toast(err.message, true);
            }).finally(function () {
                form.dataset.submitting = '0';
                form.removeAttribute('aria-busy');
                if (submitBtn && document.body.contains(submitBtn)) {
                    submitBtn.disabled = false;
                    submitBtn.textContent = submitLabel;
                }
            });
        }

        if (payload.meeting && payload.meeting.sync_google) {
            window.showConfirm({
                title: atividade && atividade.id ? 'Atualizar convite' : 'Enviar convite',
                message: 'A atividade será salva e o Google Calendar avisará os convidados.',
                detail: payload.meeting.attendees.length + ' convidado(s) receberão a atualização.',
                confirmText: atividade && atividade.id ? 'Salvar e atualizar' : 'Salvar e enviar',
                onConfirm: persist
            });
            return;
        }
        persist();
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

    function whatsappNumber(value) {
        var digits = String(value || '').replace(/\D/g, '');
        if (digits.indexOf('55') === 0 && digits.length >= 12) return digits;
        return digits.length === 10 || digits.length === 11 ? '55' + digits : '';
    }

    function copyAssistantText(text) {
        return navigator.clipboard.writeText(String(text || '')).then(function () {
            toast('Conteúdo copiado');
        }).catch(function () {
            toast('Não foi possível copiar o conteúdo', true);
        });
    }

    function renderAssistantResult(output, data, channel) {
        output.replaceChildren();
        output.classList.add('is-visible', 'is-result');
        var result = document.createElement('article');
        result.className = 'cx-atividade-result';
        var head = document.createElement('header');
        var heading = document.createElement('strong');
        var source = document.createElement('span');
        var labels = {
            whatsapp: 'Mensagem de WhatsApp',
            email: 'E-mail pronto',
            ligacao: 'Guia para ligação',
            reuniao: 'Guia para reunião'
        };
        heading.textContent = labels[channel] || 'Abordagem sugerida';
        source.textContent = data.source === 'openrouter' ? 'IA contextual' : 'Modelo local';
        head.append(heading, source);
        result.appendChild(head);

        var subject = stripMarkdown(data.assunto || '');
        var message = stripMarkdown(data.mensagem || data.texto || '');
        if (subject) {
            var subjectBlock = document.createElement('div');
            subjectBlock.className = 'cx-atividade-result-subject';
            subjectBlock.innerHTML = '<span>Assunto</span><strong>' + escapeHtml(subject) + '</strong>';
            result.appendChild(subjectBlock);
        }
        if (channel === 'ligacao' || channel === 'reuniao') {
            if (data.objetivo) {
                var goal = document.createElement('section');
                goal.innerHTML = '<h3>Objetivo da conversa</h3><p>' +
                    escapeHtml(data.objetivo) + '</p>';
                result.appendChild(goal);
            }
            if (data.abertura) {
                var opening = document.createElement('section');
                opening.innerHTML = '<h3>Abertura</h3><p>' + escapeHtml(data.abertura) + '</p>';
                result.appendChild(opening);
            }
            if (Array.isArray(data.perguntas) && data.perguntas.length) {
                var questions = document.createElement('section');
                questions.innerHTML = '<h3>Perguntas para aproximar</h3><ol>' +
                    data.perguntas.map(function (item) {
                        return '<li>' + escapeHtml(item) + '</li>';
                    }).join('') + '</ol>';
                result.appendChild(questions);
            }
            if (data.fechamento) {
                var closing = document.createElement('section');
                closing.innerHTML = '<h3>Fechamento</h3><p>' + escapeHtml(data.fechamento) + '</p>';
                result.appendChild(closing);
            }
            var objections = Array.isArray(data.objecoes_a_explorar)
                ? data.objecoes_a_explorar : [];
            var attentionPoints = Array.isArray(data.pontos_de_atencao)
                ? data.pontos_de_atencao : [];
            if (objections.length || attentionPoints.length) {
                var guidance = document.createElement('details');
                guidance.className = 'cx-atividade-result-guidance';
                guidance.innerHTML = '<summary>Objeções e orientações adicionais</summary>' +
                    (objections.length ? '<h4>Objeções a explorar</h4><ul>' +
                        objections.map(function (item) {
                            return '<li>' + escapeHtml(item) + '</li>';
                        }).join('') + '</ul>' : '') +
                    (attentionPoints.length ? '<h4>Pontos de atenção</h4><ul>' +
                        attentionPoints.map(function (item) {
                            return '<li>' + escapeHtml(item) + '</li>';
                        }).join('') + '</ul>' : '');
                result.appendChild(guidance);
            }
        } else {
            var copy = document.createElement('div');
            copy.className = 'cx-atividade-result-message';
            copy.textContent = message;
            result.appendChild(copy);
        }

        var actions = document.createElement('footer');
        var copyButton = document.createElement('button');
        copyButton.type = 'button';
        copyButton.className = 'cx-atividade-result-action';
        copyButton.innerHTML = '<i class="fa-regular fa-copy"></i> Copiar ' +
            (channel === 'email' ? 'e-mail' : channel === 'whatsapp' ? 'mensagem' : 'guia');
        copyButton.addEventListener('click', function () {
            copyAssistantText(subject ? subject + '\n\n' + message : message);
        });
        actions.appendChild(copyButton);
        if (subject) {
            var copySubject = document.createElement('button');
            copySubject.type = 'button';
            copySubject.className = 'cx-atividade-result-action';
            copySubject.innerHTML = '<i class="fa-regular fa-copy"></i> Copiar assunto';
            copySubject.addEventListener('click', function () {
                copyAssistantText(subject);
            });
            actions.appendChild(copySubject);
        }

        var contact = data.contato || {};
        if (channel === 'whatsapp') {
            var phone = whatsappNumber(
                data.telefone || contact.telefone || contact.telefone_secundario
            );
            if (phone) {
                var whatsapp = document.createElement('a');
                whatsapp.className = 'cx-atividade-result-action is-primary';
                whatsapp.target = '_blank';
                whatsapp.rel = 'noopener noreferrer';
                whatsapp.href = 'https://wa.me/' + phone + '?text=' + encodeURIComponent(message);
                whatsapp.innerHTML = '<i class="fa-brands fa-whatsapp"></i> Abrir WhatsApp';
                actions.appendChild(whatsapp);
            }
        }
        var contactEmail = String(data.email || contact.email || '').trim();
        if (channel === 'email' && contactEmail) {
            var email = document.createElement('a');
            email.className = 'cx-atividade-result-action is-primary';
            email.href = 'mailto:' + encodeURIComponent(contactEmail) +
                '?subject=' + encodeURIComponent(subject) +
                '&body=' + encodeURIComponent(message);
            email.innerHTML = '<i class="fa-regular fa-envelope"></i> Criar e-mail';
            actions.appendChild(email);
        }
        result.appendChild(actions);
        if (
            (channel === 'whatsapp' && actions.children.length === 1)
            || (channel === 'email' && actions.children.length === 1)
        ) {
            var missing = document.createElement('small');
            missing.className = 'cx-atividade-result-missing';
            missing.textContent = channel === 'whatsapp'
                ? 'O contato selecionado não possui celular válido.'
                : 'O contato selecionado não possui e-mail.';
            result.appendChild(missing);
        }
        output.appendChild(result);
    }

    function runIA(btn, form, output, clienteId, wrapper) {
        if (!wrapper || wrapper.dataset.iaBusy === '1') return;
        var action = btn.getAttribute('data-ia-action');
        var payload = serializeForm(form);
        payload.cliente_id = clienteId;
        var instrucoes = wrapper && wrapper.querySelector('[data-ia-field="instrucoes"]');
        payload.instrucoes = instrucoes ? (instrucoes.value || '').trim() : '';
        if (!payload.objetivo) payload.objetivo = payload.titulo || payload.descricao || '';
        var endpoint = action;
        if (action === 'gerar-roteiro') {
            var activityType = String(payload.tipo || 'atividade').toLowerCase();
            payload.notas_executivo = payload.descricao || '';
            payload.objetivo = [payload.titulo, payload.descricao]
                .filter(Boolean).join('\n\n');
            delete payload.descricao;
            if (activityType === 'email' || activityType === 'whatsapp') {
                endpoint = 'gerar-comunicacao';
                payload.formato = activityType;
                payload.tipo = activityType;
            }
        }
        if (action === 'gerar-comunicacao') {
            var fmt = String(payload.formato || payload.tipo || '').toLowerCase();
            if (fmt === 'sequencia') endpoint = 'touchpoints';
            else {
                endpoint = 'gerar-comunicacao';
                payload.tipo = fmt === 'whatsapp' ? 'whatsapp' : 'email';
            }
        }
        wrapper.dataset.iaBusy = '1';
        var iaButtons = $$('[data-ia-action]', wrapper);
        iaButtons.forEach(function (actionBtn) { actionBtn.disabled = true; });
        var iaPanel = wrapper.querySelector('.cx-atividade-ia');
        if (iaPanel) iaPanel.setAttribute('aria-busy', 'true');
        output.classList.add('is-visible');
        output.classList.remove('is-result');
        output.setAttribute('aria-busy', 'true');
        output.textContent = 'Consultando assistente…';

        apiFetch('/ia/' + endpoint, { method: 'POST', body: payload }).then(function (res) {
            var data = res.data || res;
            if (endpoint === 'melhorar-texto') {
                var texto = stripMarkdown((data && (data.texto || data.descricao || data.texto_melhorado)) || '');
                if (texto) {
                    addIaHistory(wrapper, form, {
                        label: 'Texto revisado',
                        texto: texto,
                        source: data.source === 'openrouter' ? 'IA' : 'fallback',
                        historyId: data.history_id,
                        canApply: true
                    });
                    if (applyTextSafely(form, texto)) {
                        output.textContent = 'Texto revisado' +
                            '. Origem: ' + (data.source === 'openrouter' ? 'IA contextual' : 'fallback local') +
                            '\nRevise antes de salvar.';
                    } else {
                        output.textContent = 'Sugestão guardada no histórico sem substituir seu texto.';
                    }
                } else {
                    output.textContent = 'A IA não devolveu texto. Tente novamente.';
                }
            } else if (endpoint === 'gerar-roteiro') {
                var guideText = stripMarkdown((data && data.texto) || '');
                if (guideText) {
                    addIaHistory(wrapper, form, {
                        label: payload.tipo === 'reuniao' ? 'Guia de reunião' : 'Guia de ligação',
                        texto: guideText,
                        source: data.source === 'openrouter' ? 'IA' : 'fallback',
                        historyId: data.history_id,
                        canApply: false
                    });
                }
                renderAssistantResult(
                    output,
                    data,
                    payload.tipo === 'reuniao' ? 'reuniao' : 'ligacao'
                );
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
                    var sugestaoTexto = stripMarkdown(data.descricao);
                    setField('titulo', stripMarkdown(data.titulo));
                    setField('tipo', data.tipo);
                    setField('data', data.data_sugerida);
                    if (sugestaoTexto) {
                        addIaHistory(wrapper, form, {
                            label: 'Próxima atividade',
                            texto: sugestaoTexto,
                            source: data.source === 'openrouter' ? 'IA' : 'fallback',
                            historyId: data.history_id
                        });
                        applyTextSafely(form, sugestaoTexto);
                    }
                    output.textContent = 'Sugestão aplicada aos campos disponíveis.' +
                        (data.motivo ? '\nPor quê: ' + stripMarkdown(data.motivo) : '') +
                        '\nOrigem: ' + (data.source === 'openrouter' ? 'IA contextual' : 'fallback local');
                }
            } else if (endpoint === 'touchpoints') {
                var list = (data && data.touchpoints) || [];
                if (!list.length) { output.textContent = 'Sem sequência sugerida.'; }
                else {
                    output.innerHTML = '<strong>Revise a sequência antes de criar</strong>' +
                        '<p>' + escapeHtml(data.motivo || '') + '</p>' +
                        '<div class="cx-sequence-preview">' + list.map(function (t) {
                            return '<div class="cx-sequence-preview-row">' +
                                '<input type="date" data-seq-date value="' + escapeHtml(t.data_sugerida || '') + '">' +
                                '<select data-seq-type>' +
                                ['email', 'whatsapp', 'ligacao', 'reuniao'].map(function (tipo) {
                                    return '<option value="' + tipo + '"' + (tipo === t.tipo ? ' selected' : '') + '>' + tipo + '</option>';
                                }).join('') + '</select>' +
                                '<input type="text" data-seq-title value="' + escapeHtml(stripMarkdown(t.titulo || '')) + '">' +
                                '<textarea data-seq-description>' + escapeHtml(stripMarkdown(t.descricao || '')) + '</textarea>' +
                                '</div>';
                        }).join('') + '</div>';
                    var apply = document.createElement('button');
                    apply.type = 'button';
                    apply.className = 'cx-drawer-ia-action cx-drawer-ia-apply';
                    apply.textContent = 'Criar ' + list.length + ' atividades em uma transação';
                    apply.addEventListener('click', function () {
                        if (apply.disabled) return;
                        var itens = $$('.cx-sequence-preview-row', output).map(function (row, idx) {
                            return {
                                titulo: row.querySelector('[data-seq-title]').value,
                                descricao: row.querySelector('[data-seq-description]').value,
                                tipo: row.querySelector('[data-seq-type]').value,
                                data: row.querySelector('[data-seq-date]').value,
                                hora: list[idx].hora || '09:00',
                                prioridade: list[idx].prioridade || 'Média',
                                contato_id: payload.contato_id || null,
                                executivo_id: payload.executivo_id || null
                            };
                        });
                        apply.disabled = true;
                        apply.textContent = 'Criando sequência…';
                        apiFetch('/clientes/' + encodeURIComponent(clienteId) + '/atividades/sequencia', {
                            method: 'POST',
                            body: {
                                titulo: 'Follow-up comercial',
                                source: data.source || 'fallback',
                                executivo_id: payload.executivo_id || null,
                                itens: itens
                            }
                        }).then(function () {
                            toast('Sequência criada por completo');
                            if (window.crmV3 && typeof window.crmV3.reloadAtividades === 'function') {
                                window.crmV3.reloadAtividades();
                            }
                            apply.textContent = 'Sequência criada';
                        }).catch(function (err) {
                            apply.disabled = false;
                            apply.textContent = 'Tentar criar sequência novamente';
                            toast(err.message, true);
                        });
                    });
                    output.appendChild(apply);
                }
            } else if (endpoint === 'gerar-comunicacao') {
                if (data && data.mensagem) {
                    var msg = stripMarkdown(data.mensagem);
                    addIaHistory(wrapper, form, {
                        label: String(payload.tipo || 'Comunicação'),
                        texto: msg,
                        source: data.source === 'openrouter' ? 'IA' : 'fallback',
                        historyId: data.history_id,
                        canApply: false
                    });
                    data.mensagem = msg;
                    data.assunto = stripMarkdown(data.assunto || '');
                    renderAssistantResult(output, data, payload.tipo);
                } else {
                    output.textContent = 'Sem conteúdo gerado.';
                }
            }
        }).catch(function (err) {
            output.textContent = 'Erro: ' + err.message;
        }).finally(function () {
            wrapper.dataset.iaBusy = '0';
            iaButtons.forEach(function (actionBtn) { actionBtn.disabled = false; });
            output.removeAttribute('aria-busy');
            if (iaPanel) iaPanel.removeAttribute('aria-busy');
        });
    }

    function openDrawerComunicacao(data, clienteId, atividadePayload) {
        atividadePayload = atividadePayload || {};
        var canal = data.tipo === 'whatsapp' ? 'whatsapp' : 'email';
        var contato = data.contato || {};
        var wrap = document.createElement('div');
        wrap.innerHTML = (
            '<div class="cx-drawer-section"><div class="cx-drawer-section-title">Canal e destinatário</div>' +
            '<p>' + escapeHtml(canal === 'whatsapp' ? 'WhatsApp' : 'E-mail') + ' · ' +
            escapeHtml(contato.nome || 'Contato selecionado') + '</p></div>' +
            '<div class="cx-drawer-section">' +
            '<div class="cx-drawer-section-title">Assunto</div>' +
            '<div class="cx-drawer-field"><input type="text" id="cx-com-assunto" value="' + escapeHtml(data.assunto || '') + '" /></div>' +
            '</div>' +
            '<div class="cx-drawer-section">' +
            '<div class="cx-drawer-section-title">Mensagem</div>' +
            '<div class="cx-drawer-field"><textarea rows="12" id="cx-com-body">' + escapeHtml(data.mensagem || '') + '</textarea></div>' +
            '</div>' +
            '<div class="cx-drawer-section cx-com-actions">' +
            '<button type="button" class="cx-drawer-ia-action" data-com-action="copy"><i class="fa-regular fa-copy"></i> Copiar mensagem</button> ' +
            '<button type="button" class="cx-drawer-ia-action" data-com-action="open"><i class="fa-solid fa-arrow-up-right-from-square"></i> Abrir ' +
            (canal === 'whatsapp' ? 'WhatsApp' : 'e-mail') + '</button></div>'
        );

        wrap.addEventListener('click', function (event) {
            var btn = event.target.closest('[data-com-action]');
            if (!btn) return;
            var assunto = wrap.querySelector('#cx-com-assunto').value;
            var msg = wrap.querySelector('#cx-com-body').value;
            if (btn.getAttribute('data-com-action') === 'copy') {
                if (!navigator.clipboard || !navigator.clipboard.writeText) {
                    toast('Copie a mensagem pelo campo de texto.', true);
                    return;
                }
                navigator.clipboard.writeText(msg).then(function () { toast('Mensagem copiada'); })
                    .catch(function () { toast('Não foi possível copiar automaticamente.', true); });
                return;
            }
            var destino;
            if (canal === 'whatsapp') {
                var telefone = String(contato.telefone || '').replace(/\D/g, '');
                if (!telefone) {
                    toast('O contato selecionado não possui telefone.', true);
                    return;
                }
                destino = 'https://wa.me/' + telefone + '?text=' + encodeURIComponent(msg);
            } else {
                if (!contato.email) {
                    toast('O contato selecionado não possui e-mail.', true);
                    return;
                }
                destino = 'mailto:' + encodeURIComponent(contato.email || '') +
                    '?subject=' + encodeURIComponent(assunto) + '&body=' + encodeURIComponent(msg);
            }
            window.open(destino, '_blank', 'noopener');
        });

        cxDrawer.open({
            title: 'Preparar comunicação',
            breadcrumb: 'CRM v3 · IA · Comunicação',
            size: 'md',
            contentEl: wrap,
            nested: true,
            actions: [
                { label: 'Fechar', variant: 'ghost', close: true },
                {
                    label: 'Registrar contato realizado',
                    variant: 'primary',
                    onClick: function (ev, id) {
                        var assunto = wrap.querySelector('#cx-com-assunto').value;
                        var msg = wrap.querySelector('#cx-com-body').value;
                        apiFetch('/clientes/' + encodeURIComponent(clienteId) + '/atividades', {
                            method: 'POST',
                            body: {
                                titulo: assunto || (canal === 'whatsapp' ? 'WhatsApp para contato selecionado' : 'E-mail para contato selecionado'),
                                descricao: msg,
                                tipo: canal,
                                prioridade: 'Média',
                                data: new Date().toISOString().slice(0, 10),
                                status: 'concluida',
                                contato_id: contato.id || atividadePayload.contato_id || null,
                                executivo_id: atividadePayload.executivo_id || null
                            }
                        }).then(function () {
                            toast((canal === 'whatsapp' ? 'WhatsApp' : 'E-mail') + ' registrado como atividade');
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
                            notifyEntityUpdated('cliente', clienteId);
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
        var selectedId = cotacao && (
            cotacao.responsavel_comercial ||
            cotacao.responsavel_id ||
            cotacao.executivo_id
        );
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

    function uploadCotacaoBriefing(wrapper, cotacaoId) {
        var input = wrapper.querySelector('#cx-cot-briefing-file');
        var file = input && input.files && input.files[0];
        if (!file || !cotacaoId) return Promise.resolve();
        var data = new FormData();
        data.append('arquivo', file);
        return fetch(
            API_BASE + '/cotacoes/' + encodeURIComponent(cotacaoId) + '/briefing',
            { method: 'POST', body: data }
        ).then(function (response) {
            return response.json().then(function (payload) {
                if (!response.ok || payload.success === false) {
                    throw new Error(payload.error || 'Não foi possível anexar o briefing');
                }
                return payload;
            });
        });
    }

    function submitCotacaoCaminhoA(form, wrapper, cotacao, clienteId, drawerId, abrirMontagem) {
        var payload = serializeForm(form);
        payload.tipo_comercial = payload.tipo_comercial || 'midia';
        if (payload.tipo_comercial === 'midia' &&
                form.querySelector('[data-field="plataformas"]')) {
            payload.plataformas = String(payload.plataformas || '')
                .split(',')
                .map(function (item) { return item.trim(); })
                .filter(Boolean);
        } else {
            delete payload.plataformas;
        }
        var nome = (payload.nome_campanha || '').trim();
        if (!nome) { toast('Nome da campanha é obrigatório', true); return; }
        if (!payload.periodo_inicio) { toast('Data de início é obrigatória', true); return; }
        var isEdit = !!(cotacao && cotacao.id);
        if (!isEdit) payload.status = 'rascunho';
        if (payload.tipo_comercial !== 'midia') {
            payload.status = 'rascunho';
        }

        var targetId = String(payload.client_id || clienteId || '').trim();
        if (!isEdit && !targetId) {
            toast('Selecione o cliente da cotação', true);
            return;
        }

        var req = isEdit
            ? apiFetch('/cotacoes/' + encodeURIComponent(cotacao.id), { method: 'PATCH', body: payload })
            : apiFetch('/clientes/' + encodeURIComponent(targetId) + '/cotacoes', { method: 'POST', body: payload });

        return req.then(function (resp) {
            var updatedQuoteId = (resp.cotacao && resp.cotacao.id) || (cotacao && cotacao.id);
            return uploadCotacaoBriefing(wrapper, updatedQuoteId)
                .then(function () { return { response: resp, quoteId: updatedQuoteId }; });
        }).then(function (result) {
            var resp = result.response;
            toast(isEdit ? 'Cotação atualizada' : 'Cotação criada');
            var updatedQuoteId = result.quoteId;
            notifyEntityUpdated('cotacao', updatedQuoteId);
            cxDrawer.close(drawerId);
            if (window.crmV3 && typeof window.crmV3.reloadCotacoes === 'function') {
                window.crmV3.reloadCotacoes();
            }
            if (abrirMontagem) {
                // Preferência: URL vinda do backend (mais seguro se a rota mudar).
                var url = (resp && resp.redirect_url)
                    || (resp && resp.cotacao && resp.cotacao.detalhes_url)
                    || null;
                if (!url) {
                    var novoId = (resp && resp.cotacao && resp.cotacao.id) || (cotacao && cotacao.id);
                    var sufixo = payload.tipo_comercial === 'midia' ? 'detalhes' : 'workspace';
                    if (novoId) url = '/cotacoes/' + encodeURIComponent(novoId) + '/' + sufixo;
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

    function wireTipoCotacao(wrapper) {
        var tipo = wrapper.querySelector('#cx-cot-tipo');
        var options = $$('[data-cot-type]', wrapper);
        var status = wrapper.querySelector('#cx-cot-status');
        var hint = wrapper.querySelector('#cx-cot-tipo-hint');
        var note = wrapper.querySelector('#cx-cot-montagem-note');
        var fullLink = wrapper.querySelector('#cx-cot-open-full');
        if (!tipo) return;

        function selectTipo(value, fromUser) {
            var valid = options.some(function (button) {
                return button.getAttribute('data-cot-type') === value;
            });
            tipo.value = valid ? value : 'midia';
            if (fromUser) wrapper._cotTypeTouched = true;
            options.forEach(function (button) {
                var active = button.getAttribute('data-cot-type') === tipo.value;
                button.classList.toggle('is-active', active);
                button.setAttribute('aria-checked', String(active));
                button.tabIndex = active ? 0 : -1;
            });
            update();
        }

        function update() {
            var isMidia = (tipo.value || 'midia') === 'midia';
            var agent = wrapper.querySelector('.cx-cot-agent');
            var main = wrapper.querySelector('.cx-cotacao-editor-main');
            var side = wrapper.querySelector('.cx-cotacao-editor-side');
            var refine = wrapper.querySelector('.cx-cot-refine');
            var control = wrapper.querySelector('.cx-cot-control');
            if (agent && main && side) {
                if (isMidia && control) side.insertBefore(agent, control);
                if (!isMidia && refine) main.insertBefore(agent, refine);
            }
            $$('[data-cot-media-only]', wrapper).forEach(function (element) {
                element.hidden = !isMidia ||
                    (element.id === 'cx-cot-agency-clients' && !wrapper._cotAgencyId);
            });
            if (status) {
                if (!isMidia) status.value = 'rascunho';
                status.disabled = !isMidia;
            }
            if (hint) {
                hint.textContent = isMidia
                    ? 'Mídia usa a montagem e a calculadora atuais.'
                    : 'Primeira fase: cabeçalho em rascunho. Precificação e PI terão módulo próprio.';
            }
            if (note) {
                var title = note.querySelector('strong');
                var body = note.querySelector('.cx-drawer-note-body > div');
                if (title) title.textContent = isMidia ? 'Montagem completa' : 'Módulo próprio em preparação';
                if (body) {
                    body.textContent = isMidia
                        ? 'Audiência, produtos, valores detalhados, comissões e PI ficam na tela de montagem.'
                        : 'Esta categoria não usa a calculadora nem o PI de Mídia.';
                }
            }
            if (fullLink) fullLink.hidden = !fullLink.getAttribute('href');
        }

        options.forEach(function (button, index) {
            button.addEventListener('click', function () {
                selectTipo(button.getAttribute('data-cot-type'), true);
            });
            button.addEventListener('keydown', function (event) {
                if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') return;
                event.preventDefault();
                var next = index + (event.key === 'ArrowRight' ? 1 : -1);
                if (next < 0) next = options.length - 1;
                if (next >= options.length) next = 0;
                options[next].focus();
                selectTipo(options[next].getAttribute('data-cot-type'), true);
            });
        });
        wrapper._selectCotacaoTipo = selectTipo;
        selectTipo(tipo.value || 'midia', false);
    }

    /* ------------------------------------------------------------
     * Cabeçalho Cliente / Agência do drawer de cotação.
     * Ficha de agência: modal com nome dos clientes finais vinculados.
     * Ficha de cliente final: nome só leitura; várias agências também abrem modal.
     * ------------------------------------------------------------ */
    function fillContextoCotacao(wrapper, clienteId, cotacao) {
        var box = wrapper.querySelector('#cx-cot-contexto');
        var clienteRow = wrapper.querySelector('#cx-cot-ctx-cliente-row');
        var agenciaRow = wrapper.querySelector('#cx-cot-ctx-agencia-row');
        var clienteVal = wrapper.querySelector('#cx-cot-ctx-cliente-nome');
        var agenciaVal = wrapper.querySelector('#cx-cot-ctx-agencia-nome');
        var clientInput = wrapper.querySelector('#cx-cot-client-id');
        var clientPicker = wrapper.querySelector('#cx-cot-client-picker');
        var clientPickerLabel = wrapper.querySelector('#cx-cot-client-picker-label');
        var agenciaPicker = wrapper.querySelector('#cx-cot-agencia-picker');
        var agenciaPickerLabel = wrapper.querySelector('#cx-cot-agencia-picker-label');
        var agenciaIdInput = wrapper.querySelector('#cx-cot-agencia-id');
        if (!box || !clienteRow || !agenciaRow) return;

        var cliente = (window.crmV3 && window.crmV3.state && window.crmV3.state.cliente) || null;
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
        var finais = Array.isArray(cliente.clientes_finais) ? cliente.clientes_finais.slice() : [];
        if (!finais.length && isAgencia && window.crmV3 && Array.isArray(window.crmV3.state.clientes)) {
            finais = window.crmV3.state.clientes
                .filter(function (c) {
                    if (String(c.id) === String(cliente.id)) return false;
                    if (String(c.agencia_id || '') === String(cliente.id)) return true;
                    return (c.agencias_vinculadas || []).some(function (v) {
                        return String(v.agencia_id) === String(cliente.id);
                    });
                })
                .map(function (c) { return { id: c.id, nome: c.nome }; });
        }
        var agenciasVinc = Array.isArray(cliente.agencias_vinculadas) ? cliente.agencias_vinculadas.slice() : [];

        box.hidden = false;
        clienteRow.hidden = false;
        wrapper._cotFinais = finais;
        wrapper._cotAgencyId = isAgencia ? String(cliente.id) : '';
        wrapper._cotAgencias = agenciasVinc.map(function (a) {
            return {
                id: a.agencia_id || a.id || a.id_agencia_cliente,
                nome: a.nome || a.nome_fantasia || a.razao_social || ('#' + (a.agencia_id || a.id || ''))
            };
        });

        wirePickModal(wrapper);

        if (isAgencia) {
            agenciaRow.hidden = false;
            if (agenciaPicker) agenciaPicker.hidden = true;
            if (agenciaVal) {
                agenciaVal.hidden = false;
                agenciaVal.textContent = nome;
                agenciaVal.title = nome;
            }
            if (agenciaIdInput) agenciaIdInput.value = String(cliente.id);
            if (clienteVal) clienteVal.hidden = true;
            var selectedClientId = cotacao && cotacao.cliente_id &&
                String(cotacao.cliente_id) !== String(cliente.id)
                ? String(cotacao.cliente_id)
                : '';
            var selectedClient = finais.find(function (item) {
                return String(item.id) === selectedClientId;
            });
            if (clientInput) clientInput.value = selectedClientId;
            if (clientPicker) {
                clientPicker.hidden = false;
                clientPicker.disabled = !finais.length;
                if (clientPickerLabel) {
                    clientPickerLabel.textContent = selectedClient
                        ? selectedClient.nome
                        : (selectedClientId && cotacao.cliente_nome
                            ? cotacao.cliente_nome
                            : (finais.length ? 'Selecionar cliente' : 'Nenhum cliente vinculado'));
                }
                clientPicker.classList.toggle('has-value', !!selectedClientId);
            }
            wireAgencyClientManager(wrapper, cliente);
        } else {
            if (clientInput) clientInput.value = String(cliente.id);
            if (clientPicker) clientPicker.hidden = true;
            if (clienteVal) {
                clienteVal.hidden = false;
                clienteVal.textContent = nome;
                clienteVal.title = nome;
            }
            if (wrapper._cotAgencias.length > 1) {
                agenciaRow.hidden = false;
                if (agenciaVal) agenciaVal.hidden = true;
                if (agenciaPicker) {
                    agenciaPicker.hidden = false;
                    if (agenciaPickerLabel) {
                        agenciaPickerLabel.textContent = agenciaNome || 'Buscar agência pelo nome';
                    }
                }
                if (agenciaIdInput) agenciaIdInput.value = String(cliente.agencia_id || '');
            } else if (agenciaNome) {
                agenciaRow.hidden = false;
                if (agenciaPicker) agenciaPicker.hidden = true;
                if (agenciaVal) {
                    agenciaVal.hidden = false;
                    agenciaVal.textContent = agenciaNome;
                    agenciaVal.title = agenciaNome;
                }
                if (agenciaIdInput) agenciaIdInput.value = String(cliente.agencia_id || '');
            } else {
                agenciaRow.hidden = true;
                if (agenciaIdInput) agenciaIdInput.value = '';
            }
        }
    }

    function wirePickModal(wrapper) {
        if (wrapper._cotPickWired) return;
        wrapper._cotPickWired = true;
        var modal = wrapper.querySelector('#cx-cot-pick-modal');
        var listEl = wrapper.querySelector('#cx-cot-pick-list');
        var q = wrapper.querySelector('#cx-cot-pick-q');
        var title = wrapper.querySelector('#cx-cot-pick-title');
        var cancel = wrapper.querySelector('#cx-cot-pick-cancel');
        var clear = wrapper.querySelector('#cx-cot-pick-clear');
        var clientPicker = wrapper.querySelector('#cx-cot-client-picker');
        var agenciaPicker = wrapper.querySelector('#cx-cot-agencia-picker');

        function render(kind, filtro) {
            var items = kind === 'cliente' ? (wrapper._cotFinais || []) : (wrapper._cotAgencias || []);
            var termo = String(filtro || '').toLowerCase();
            listEl.innerHTML = '';
            items.filter(function (it) {
                return !termo || String(it.nome || '').toLowerCase().indexOf(termo) !== -1;
            }).forEach(function (it) {
                var btn = document.createElement('button');
                btn.type = 'button';
                btn.className = 'cx-name-pick-item';
                btn.textContent = it.nome || ('#' + it.id);
                btn.addEventListener('click', function () {
                    if (kind === 'cliente') {
                        var input = wrapper.querySelector('#cx-cot-client-id');
                        var lab = wrapper.querySelector('#cx-cot-client-picker-label');
                        if (input) input.value = String(it.id);
                        if (input) input.dispatchEvent(new Event('change'));
                        if (lab) lab.textContent = it.nome || ('#' + it.id);
                        if (clientPicker) clientPicker.classList.add('has-value');
                    } else {
                        var hid = wrapper.querySelector('#cx-cot-agencia-id');
                        var alab = wrapper.querySelector('#cx-cot-agencia-picker-label');
                        if (hid) hid.value = String(it.id);
                        if (hid) hid.dispatchEvent(new Event('change'));
                        if (alab) alab.textContent = it.nome || ('#' + it.id);
                        if (agenciaPicker) agenciaPicker.classList.add('has-value');
                    }
                    if (modal && modal.close) modal.close();
                });
                listEl.appendChild(btn);
            });
            if (!listEl.childNodes.length) {
                listEl.innerHTML = '<p class="cx-name-pick-empty">Nenhum resultado</p>';
            }
        }

        function openKind(kind) {
            wrapper._cotPickKind = kind;
            if (title) title.textContent = kind === 'cliente' ? 'Escolher cliente' : 'Escolher agência';
            if (clear) clear.hidden = kind !== 'cliente';
            if (q) q.value = '';
            render(kind, '');
            if (modal && modal.showModal) modal.showModal();
            if (q) setTimeout(function () { q.focus(); }, 40);
        }

        if (q) {
            q.addEventListener('input', function () {
                render(wrapper._cotPickKind || 'cliente', q.value);
            });
        }
        if (cancel) {
            cancel.addEventListener('click', function () {
                if (modal && modal.close) modal.close();
            });
        }
        if (clear) {
            clear.addEventListener('click', function () {
                var input = wrapper.querySelector('#cx-cot-client-id');
                var label = wrapper.querySelector('#cx-cot-client-picker-label');
                if (input) input.value = '';
                if (input) input.dispatchEvent(new Event('change'));
                if (label) label.textContent = 'Selecionar cliente';
                if (clientPicker) clientPicker.classList.remove('has-value');
                if (modal && modal.close) modal.close();
            });
        }
        if (clientPicker) {
            clientPicker.addEventListener('click', function () { openKind('cliente'); });
        }
        if (agenciaPicker) {
            agenciaPicker.addEventListener('click', function () { openKind('agencia'); });
        }
    }

    function normalizeAgencyClient(item) {
        return {
            id: String(item.id || item.id_cliente || ''),
            nome: item.nome || item.nome_fantasia || item.razao_social || '',
            cidade: item.cidade || (item.endereco && item.endereco.cidade) || '',
            cnpj: item.cnpj || ''
        };
    }

    function renderAgencyClients(wrapper) {
        var section = wrapper.querySelector('#cx-cot-agency-clients');
        var list = wrapper.querySelector('#cx-cot-agency-list');
        var count = wrapper.querySelector('#cx-cot-agency-count');
        var picker = wrapper.querySelector('#cx-cot-client-picker');
        var pickerLabel = wrapper.querySelector('#cx-cot-client-picker-label');
        var current = (wrapper._cotFinais || []).map(normalizeAgencyClient);
        if (!section || !list || !wrapper._cotAgencyId) return;

        section.hidden = false;
        if (count) count.textContent = String(current.length);
        if (picker) picker.disabled = !current.length;
        if (!current.length) {
            list.innerHTML = '<p class="cx-agency-clients-empty">Nenhum cliente vinculado. Adicione o primeiro cliente da agência.</p>';
            if (pickerLabel) pickerLabel.textContent = 'Nenhum cliente vinculado';
            return;
        }

        list.innerHTML = current.map(function (item) {
            return (
                '<div class="cx-agency-client-row">' +
                    '<button type="button" class="cx-agency-client-select" data-select-client="' + escapeAttr(item.id) + '">' +
                        '<strong>' + escapeHtml(item.nome || ('Cliente #' + item.id)) + '</strong>' +
                        (item.cidade ? '<span>' + escapeHtml(item.cidade) + '</span>' : '') +
                    '</button>' +
                    '<button type="button" class="cx-agency-client-remove" data-remove-client="' + escapeAttr(item.id) + '"' +
                        ' aria-label="Retirar ' + escapeAttr(item.nome || 'cliente') + ' da agência" title="Retirar vínculo">' +
                        '<i class="fa-solid fa-xmark" aria-hidden="true"></i>' +
                    '</button>' +
                '</div>'
            );
        }).join('');

        $$('[data-select-client]', list).forEach(function (button) {
            button.addEventListener('click', function () {
                var selected = current.find(function (item) {
                    return item.id === button.getAttribute('data-select-client');
                });
                var input = wrapper.querySelector('#cx-cot-client-id');
                if (input) input.value = selected ? selected.id : '';
                if (input) input.dispatchEvent(new Event('change'));
                if (pickerLabel && selected) pickerLabel.textContent = selected.nome;
                if (picker) picker.classList.toggle('has-value', !!selected);
            });
        });

        $$('[data-remove-client]', list).forEach(function (button) {
            button.addEventListener('click', function () {
                var selected = current.find(function (item) {
                    return item.id === button.getAttribute('data-remove-client');
                });
                if (!selected) return;
                button.disabled = true;
                changeAgencyClientLink(wrapper, selected, false)
                    .catch(function (err) {
                        button.disabled = false;
                        toast(err.message, true);
                    });
            });
        });
    }

    function syncAgencyClients(wrapper, response) {
        wrapper._cotFinais = (response.clientes || []).map(normalizeAgencyClient);
        var state = window.crmV3 && window.crmV3.state;
        if (state && state.cliente && String(state.cliente.id) === String(wrapper._cotAgencyId)) {
            state.cliente.clientes_finais = wrapper._cotFinais.slice();
            state.cliente.clientes_finais_ids = wrapper._cotFinais.map(function (item) { return item.id; });
        }
        renderAgencyClients(wrapper);
    }

    function changeAgencyClientLink(wrapper, client, active) {
        if (!client || !client.id || !wrapper._cotAgencyId) return Promise.resolve();
        return apiFetch(
            '/agencias/' + encodeURIComponent(wrapper._cotAgencyId) +
            '/clientes/' + encodeURIComponent(client.id),
            { method: active ? 'POST' : 'DELETE' }
        ).then(function (response) {
            syncAgencyClients(wrapper, response);
            if (!active) {
                var selectedInput = wrapper.querySelector('#cx-cot-client-id');
                var pickerLabel = wrapper.querySelector('#cx-cot-client-picker-label');
                var picker = wrapper.querySelector('#cx-cot-client-picker');
                if (selectedInput && String(selectedInput.value) === String(client.id)) {
                    selectedInput.value = '';
                    if (pickerLabel) pickerLabel.textContent = 'Selecionar cliente';
                    if (picker) picker.classList.remove('has-value');
                }
            }
            notifyEntityUpdated('cliente', client.id);
            notifyEntityUpdated('cliente', wrapper._cotAgencyId);
            toast(active ? 'Cliente adicionado à agência' : 'Cliente retirado da agência');
            return response;
        });
    }

    function wireAgencyClientManager(wrapper) {
        if (wrapper._cotAgencyWired || !wrapper._cotAgencyId) return;
        wrapper._cotAgencyWired = true;
        var add = wrapper.querySelector('#cx-cot-agency-add');
        var searchBox = wrapper.querySelector('#cx-cot-agency-search');
        var search = wrapper.querySelector('#cx-cot-agency-search-input');
        var results = wrapper.querySelector('#cx-cot-agency-results');
        var allClients = [];

        function renderResults() {
            var linked = new Set((wrapper._cotFinais || []).map(function (item) {
                return String(item.id || item.id_cliente);
            }));
            var term = String(search && search.value || '').trim().toLocaleLowerCase('pt-BR');
            var available = allClients.filter(function (item) {
                if (!item.id || item.is_agencia || linked.has(String(item.id))) return false;
                var haystack = [item.nome, item.cidade, item.cnpj].join(' ').toLocaleLowerCase('pt-BR');
                return !term || haystack.indexOf(term) !== -1;
            }).slice(0, 12);
            if (!results) return;
            results.innerHTML = available.length ? available.map(function (item) {
                return (
                    '<button type="button" class="cx-agency-client-result" data-add-client="' + escapeAttr(item.id) + '">' +
                        '<span><strong>' + escapeHtml(item.nome || ('Cliente #' + item.id)) + '</strong>' +
                        (item.cidade ? '<small>' + escapeHtml(item.cidade) + '</small>' : '') + '</span>' +
                        '<i class="fa-solid fa-plus" aria-hidden="true"></i>' +
                    '</button>'
                );
            }).join('') : '<p class="cx-agency-clients-empty">Nenhum cliente disponível para este filtro.</p>';
            $$('[data-add-client]', results).forEach(function (button) {
                button.addEventListener('click', function () {
                    var client = available.find(function (item) {
                        return item.id === button.getAttribute('data-add-client');
                    });
                    button.disabled = true;
                    changeAgencyClientLink(wrapper, client, true)
                        .then(function () {
                            if (search) search.value = '';
                            renderResults();
                        })
                        .catch(function (err) { toast(err.message, true); })
                        .finally(function () { button.disabled = false; });
                });
            });
        }

        function loadAvailableClients() {
            var stateClients = window.crmV3 && window.crmV3.state && window.crmV3.state.clientes;
            if (Array.isArray(stateClients) && stateClients.length) {
                allClients = stateClients.map(function (item) {
                    return Object.assign(normalizeAgencyClient(item), { is_agencia: !!item.is_agencia });
                });
                renderResults();
                return Promise.resolve();
            }
            return apiFetch('/clientes').then(function (response) {
                allClients = (response.clientes || []).map(function (item) {
                    return Object.assign(normalizeAgencyClient(item), { is_agencia: !!item.is_agencia });
                });
                renderResults();
            });
        }

        if (add) {
            add.addEventListener('click', function () {
                searchBox.hidden = !searchBox.hidden;
                add.setAttribute('aria-expanded', String(!searchBox.hidden));
                if (!searchBox.hidden) {
                    loadAvailableClients()
                        .then(function () { if (search) search.focus(); })
                        .catch(function (err) { toast(err.message, true); });
                }
            });
        }
        if (search) search.addEventListener('input', renderResults);
        renderAgencyClients(wrapper);
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
        // Retorna a diferença entre as datas, sem contar o dia inicial.
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
        var corridos = Math.round((b - a) / 86400000);
        // Loop de dias úteis. 30 dias médios × ~2 anos = ~700 iter
        // máx num caso patológico; ainda barato.
        var uteis = 0;
        var cursor = new Date(a);
        cursor.setDate(cursor.getDate() + 1);
        for (var i = 0; i < corridos; i++) {
            var dow = cursor.getDay();
            if (dow !== 0 && dow !== 6) uteis++;
            cursor.setDate(cursor.getDate() + 1);
        }
        return { corridos: corridos, uteis: uteis };
    }

    function parseBudgetBr(value) {
        var raw = String(value == null ? '' : value).trim();
        if (!raw) return '';
        raw = raw.replace(/[R$\s]/g, '');
        if (raw.indexOf(',') >= 0) {
            raw = raw.replace(/\./g, '').replace(',', '.');
        }
        var number = Number(raw);
        return Number.isFinite(number) && number >= 0 ? number.toFixed(2) : '';
    }

    function formatBudgetBr(value) {
        var canonical = parseBudgetBr(value);
        if (!canonical) return '';
        return Number(canonical).toLocaleString('pt-BR', {
            style: 'currency',
            currency: 'BRL',
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
    }

    function wireBudgetCotacao(wrapper) {
        var display = wrapper.querySelector('#cx-cot-budget');
        var hidden = wrapper.querySelector('#cx-cot-budget-value');
        if (!display || !hidden) return;

        function setValue(value) {
            var canonical = parseBudgetBr(value);
            hidden.value = canonical;
            display.value = canonical ? formatBudgetBr(canonical) : '';
        }
        function syncRaw() {
            hidden.value = parseBudgetBr(display.value);
        }
        display.addEventListener('input', syncRaw);
        display.addEventListener('blur', function () { setValue(display.value); });
        display.addEventListener('focus', function () {
            if (hidden.value) display.value = Number(hidden.value).toFixed(2).replace('.', ',');
        });
        wrapper._setCotBudget = setValue;
        setValue(hidden.value);
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

    function contactOptionValue(contact) {
        return String(contact.id || contact.id_contato_cliente || '');
    }

    function loadCotacaoContacts(clienteId, select, selectedId) {
        if (!select) return Promise.resolve();
        select.innerHTML = '<option value="">Selecione depois</option>';
        if (!clienteId) return Promise.resolve();
        select.disabled = true;
        return apiFetch('/clientes/' + encodeURIComponent(clienteId) + '/contatos')
            .then(function (response) {
                (response.contatos || response.data || []).forEach(function (contact) {
                    var option = document.createElement('option');
                    option.value = contactOptionValue(contact);
                    option.textContent = contact.nome || contact.nome_completo || contact.email || option.value;
                    if (selectedId && String(selectedId) === option.value) option.selected = true;
                    select.appendChild(option);
                });
            })
            .catch(function () {
                select.innerHTML = '<option value="">Contatos indisponíveis</option>';
            })
            .finally(function () { select.disabled = false; });
    }

    function wireCotacaoParticipants(wrapper, cotacao) {
        var clientInput = wrapper.querySelector('#cx-cot-client-id');
        var agencyInput = wrapper.querySelector('#cx-cot-agencia-id');
        var clientContact = wrapper.querySelector('#cx-cot-client-user');
        var agencyContact = wrapper.querySelector('#cx-cot-agencia-user');
        var partner = wrapper.querySelector('#cx-cot-parceiro');
        var partnerContact = wrapper.querySelector('#cx-cot-parceiro-user');
        var clients = (window.crmV3 && window.crmV3.state && window.crmV3.state.clientes) || [];

        if (partner) {
            clients.filter(function (item) { return !item.is_agencia; }).forEach(function (item) {
                var option = document.createElement('option');
                option.value = String(item.id || '');
                option.textContent = item.nome || ('Cliente #' + item.id);
                if (cotacao && String(cotacao.id_parceiro || '') === option.value) option.selected = true;
                partner.appendChild(option);
            });
            partner.addEventListener('change', function () {
                loadCotacaoContacts(partner.value, partnerContact, '');
            });
        }
        if (clientInput) {
            clientInput.addEventListener('change', function () {
                loadCotacaoContacts(clientInput.value, clientContact, '');
            });
        }
        if (agencyInput) {
            agencyInput.addEventListener('change', function () {
                loadCotacaoContacts(agencyInput.value, agencyContact, '');
            });
        }
        loadCotacaoContacts(
            clientInput && clientInput.value,
            clientContact,
            cotacao && cotacao.client_user_id
        );
        loadCotacaoContacts(
            agencyInput && agencyInput.value,
            agencyContact,
            cotacao && cotacao.agencia_user_id
        );
        loadCotacaoContacts(
            partner && partner.value,
            partnerContact,
            cotacao && cotacao.parceiro_user_id
        );
    }

    function applyCotacaoSuggestion(wrapper, suggestion, key, force) {
        var selectors = {
            nome_campanha: '[data-field="nome_campanha"]',
            objetivo: '[data-field="objetivo"]',
            periodo_inicio: '[data-field="periodo_inicio"]',
            periodo_fim: '[data-field="periodo_fim"]',
            budget_estimado: '[data-field="budget_estimado"]',
            apresentacao_dados: '[data-field="apresentacao_dados"]'
        };
        if (key === 'tipo_comercial') {
            if ((force || !wrapper._cotTypeTouched) && wrapper._selectCotacaoTipo) {
                wrapper._selectCotacaoTipo(suggestion[key] || 'midia', false);
            }
            return;
        }
        if (key === 'budget_estimado' && wrapper._setCotBudget) {
            if (force || !wrapper.querySelector('#cx-cot-budget-value').value) {
                wrapper._setCotBudget(suggestion[key]);
            }
            return;
        }
        var input = wrapper.querySelector(selectors[key] || '');
        if (!input || suggestion[key] == null || suggestion[key] === '') return;
        if (!force && String(input.value || '').trim()) return;
        input.value = Array.isArray(suggestion[key]) ? suggestion[key].join(', ') : String(suggestion[key]);
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
    }

    function wireCotacaoAgent(wrapper) {
        var trigger = wrapper.querySelector('#cx-cot-agent-trigger');
        var result = wrapper.querySelector('#cx-cot-agent-result');
        var form = wrapper.querySelector('form');
        if (!trigger || !result || !form) return;

        trigger.addEventListener('click', function () {
            var payload = serializeForm(form);
            payload.cliente_id = payload.client_id || '';
            trigger.disabled = true;
            trigger.textContent = 'Preparando…';
            result.hidden = false;
            result.innerHTML = '<p class="cx-cot-agent-working">Lendo o contexto comercial deste cliente.</p>';
            apiFetch('/ia/sugerir-cotacao', { method: 'POST', body: payload })
                .then(function (response) {
                    var suggestion = response.sugestao || response.data || {};
                    var fieldLabels = {
                        tipo_comercial: 'Tipo',
                        nome_campanha: 'Campanha',
                        objetivo: 'Objetivo',
                        periodo_inicio: 'Início',
                        periodo_fim: 'Fim',
                        budget_estimado: 'Budget',
                        apresentacao_dados: 'Briefing'
                    };
                    if ((wrapper.querySelector('#cx-cot-tipo').value || 'midia') === 'midia') {
                        fieldLabels.plataformas = 'Plataformas';
                    }
                    Object.keys(fieldLabels).forEach(function (key) {
                        applyCotacaoSuggestion(wrapper, suggestion, key, false);
                    });
                    var proposals = Object.keys(fieldLabels).filter(function (key) {
                        return suggestion[key] != null && suggestion[key] !== '';
                    }).map(function (key) {
                        var value = Array.isArray(suggestion[key])
                            ? suggestion[key].join(', ')
                            : String(suggestion[key]);
                        return '<button type="button" class="cx-cot-agent-field" data-apply-cot="' +
                            escapeAttr(key) + '"><span>' + escapeHtml(fieldLabels[key]) +
                            '</span><strong>' + escapeHtml(value) + '</strong></button>';
                    }).join('');
                    var context = (suggestion.contexto_utilizado || []).map(function (item) {
                        return '<li>' + escapeHtml(item) + '</li>';
                    }).join('');
                    result.innerHTML =
                        '<p class="cx-cot-agent-reason">' +
                            escapeHtml(suggestion.motivo || 'Sugestão preparada para revisão.') +
                        '</p><div class="cx-cot-agent-fields">' + proposals + '</div>' +
                        (context ? '<ul class="cx-cot-agent-context">' + context + '</ul>' : '') +
                        '<small>Campos vazios foram preenchidos. Clique em uma sugestão para substituir o campo.</small>';
                    $$('[data-apply-cot]', result).forEach(function (button) {
                        button.addEventListener('click', function () {
                            applyCotacaoSuggestion(
                                wrapper,
                                suggestion,
                                button.getAttribute('data-apply-cot'),
                                true
                            );
                            button.classList.add('is-applied');
                        });
                    });
                })
                .catch(function (error) {
                    result.innerHTML = '<p class="cx-cot-agent-error">' + escapeHtml(error.message) + '</p>';
                })
                .finally(function () {
                    trigger.disabled = false;
                    trigger.textContent = 'Gerar outra sugestão';
                });
        });
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

        fillForm(form, Object.assign({ tipo_comercial: 'midia' }, cotacao || {}));

        var isEdit = !!(cotacao && cotacao.id);

        fillContextoCotacao(wrapper, clienteId, cotacao);

        var fullLink = wrapper.querySelector('#cx-cot-open-full');
        if (fullLink && isEdit) {
            fullLink.href = cotacao.detalhes_url || (
                '/cotacoes/' + encodeURIComponent(cotacao.id) + '/' +
                ((cotacao.tipo_comercial || 'midia') === 'midia' ? 'detalhes' : 'workspace')
            );
            fullLink.hidden = false;
        }
        wireTipoCotacao(wrapper);
        wireCotacaoParticipants(wrapper, cotacao || {});
        wireBudgetCotacao(wrapper);
        wireCotacaoAgent(wrapper);

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
                label: 'Salvar',
                variant: 'ghost',
                onClick: function (ev, id) {
                    submitCotacaoCaminhoA(form, wrapper, cotacao, clienteId, id, false);
                }
            },
            {
                label: 'Salvar e continuar',
                variant: 'primary',
                onClick: function (ev, id) {
                    submitCotacaoCaminhoA(form, wrapper, cotacao, clienteId, id, true);
                }
            }
        ];

        cxDrawer.open({
            title: isEdit ? 'Editar cotação' : 'Nova cotação',
            breadcrumb: 'CRM v3 · Cotação',
            size: 'editor',
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
