(function (global) {
  'use strict';

  let pickerCache = null;

  function escapeHtml(str) {
    return String(str ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function isAgenciaSimOption(opt) {
    if (!opt) return false;
    const sim = opt.getAttribute('data-agencia-sim');
    if (sim === '1') return true;
    const key = opt.getAttribute('data-key');
    if (key == null || key === '') return false;
    const normalized = String(key).toLowerCase();
    return normalized === 'true' || normalized === '1';
  }

  /**
   * @param {object} config
   * @param {string} config.blockId
   * @param {string} config.pickerId
   * @param {string} config.listaId
   * @param {string} config.hiddenId
   * @param {string} [config.addBtnId]
   * @param {() => HTMLSelectElement|null} [config.getAgenciaSelect]
   * @param {() => string} [config.getPessoa]
   * @param {string} [config.principalRadioName]
   * @param {boolean} [config.useHiddenInputs=true]
   */
  function initAgenciasVinculadasForm(config) {
    const block = document.getElementById(config.blockId);
    const picker = document.getElementById(config.pickerId);
    const lista = document.getElementById(config.listaId);
    const hiddenWrap = document.getElementById(config.hiddenId);
    const addBtn = config.addBtnId ? document.getElementById(config.addBtnId) : null;
    const getAgenciaSelect = config.getAgenciaSelect || (() => null);
    const getPessoa = config.getPessoa || (() => 'J');
    const principalRadioName = config.principalRadioName || 'agencia_principal_radio';
    const useHiddenInputs = config.useHiddenInputs !== false;

    let state = [];

    async function carregarPicker() {
      if (pickerCache) return pickerCache;
      try {
        const response = await fetch('/api/clientes/agencias');
        pickerCache = await response.json();
      } catch (e) {
        console.error(e);
        pickerCache = [];
      }
      return pickerCache;
    }

    async function popularPicker() {
      if (!picker) return;
      const agencias = await carregarPicker();
      const selected = new Set(state.map(a => String(a.id_agencia_cliente)));
      picker.innerHTML = '<option value="">Adicionar agência...</option>' +
        agencias.filter(a => !selected.has(String(a.id_cliente)))
          .map(a => `<option value="${a.id_cliente}">${escapeHtml(a.nome_fantasia || a.razao_social || '')}</option>`)
          .join('');
    }

    function renderUI() {
      if (!lista) return;

      if (!state.length) {
        lista.innerHTML = '<div class="text-[10px] text-gray-400 italic">Nenhuma agência vinculada.</div>';
      } else {
        lista.innerHTML = state.map(a => {
          const nome = escapeHtml(a.nome_fantasia || a.razao_social || ('#' + a.id_agencia_cliente));
          return `
            <div class="flex items-center gap-2 text-[10px] border border-gray-200 rounded px-2 py-1 bg-white">
              <label class="flex items-center gap-1 cursor-pointer shrink-0">
                <input type="radio" name="${principalRadioName}" value="${a.id_agencia_cliente}" ${a.is_principal ? 'checked' : ''}>
                <span class="text-gray-500">Principal</span>
              </label>
              <span class="flex-1 truncate">${nome}</span>
              <button type="button" class="text-red-500 hover:text-red-700 av-del-btn" data-id="${a.id_agencia_cliente}" title="Remover">×</button>
            </div>`;
        }).join('');
      }

      if (useHiddenInputs && hiddenWrap) {
        const principal = state.find(a => a.is_principal);
        hiddenWrap.innerHTML = state.map(a =>
          `<input type="hidden" name="agencias_vinculadas[]" value="${a.id_agencia_cliente}">`
        ).join('') + (principal
          ? `<input type="hidden" name="agencia_principal_id" value="${principal.id_agencia_cliente}">`
          : '');
      }
    }

    function updateVisibility() {
      if (!block) return;
      const pessoa = getPessoa();
      const sel = getAgenciaSelect();
      const opt = sel?.selectedOptions?.[0];
      const agenciaSim = isAgenciaSimOption(opt);
      if (pessoa === 'J' && !agenciaSim) {
        block.classList.remove('hidden');
        block.style.display = '';
      } else {
        block.classList.add('hidden');
        block.style.display = 'none';
        if (agenciaSim || pessoa === 'F') {
          state = [];
          renderUI();
          popularPicker();
        }
      }
    }

    function render(agencias) {
      state = (agencias || []).map(a => ({
        id_agencia_cliente: a.id_agencia_cliente || a.id_cliente,
        nome_fantasia: a.nome_fantasia || '',
        razao_social: a.razao_social || '',
        is_principal: !!a.is_principal
      }));
      if (state.length === 1) state[0].is_principal = true;
      renderUI();
      popularPicker();
      updateVisibility();
    }

    function reset() {
      state = [];
      if (picker) picker.value = '';
      renderUI();
      popularPicker();
      updateVisibility();
    }

    function definirPrincipal(id) {
      state.forEach(a => { a.is_principal = a.id_agencia_cliente === id; });
      renderUI();
    }

    function remover(id) {
      state = state.filter(a => a.id_agencia_cliente !== id);
      if (state.length === 1) {
        state[0].is_principal = true;
      } else if (!state.some(a => a.is_principal)) {
        state.forEach(a => { a.is_principal = false; });
      }
      renderUI();
      popularPicker();
    }

    async function adicionar() {
      if (!picker || !picker.value) return;
      const id = parseInt(picker.value, 10);
      if (state.some(a => a.id_agencia_cliente === id)) return;
      const agencias = await carregarPicker();
      const found = agencias.find(a => a.id_cliente === id);
      state.push({
        id_agencia_cliente: id,
        nome_fantasia: found?.nome_fantasia || '',
        razao_social: found?.razao_social || '',
        is_principal: state.length === 0
      });
      if (state.length === 1) state[0].is_principal = true;
      picker.value = '';
      renderUI();
      popularPicker();
    }

    function getPayload() {
      const principal = state.find(a => a.is_principal);
      return {
        agencias_vinculadas: state.map(a => a.id_agencia_cliente),
        agencia_principal_id: principal ? principal.id_agencia_cliente : null
      };
    }

    if (lista) {
      lista.addEventListener('click', (e) => {
        const btn = e.target.closest('.av-del-btn');
        if (btn) remover(parseInt(btn.dataset.id, 10));
      });
      lista.addEventListener('change', (e) => {
        if (e.target.matches(`input[name="${principalRadioName}"]`)) {
          definirPrincipal(parseInt(e.target.value, 10));
        }
      });
    }
    if (addBtn) addBtn.addEventListener('click', adicionar);

    return {
      render,
      reset,
      updateVisibility,
      adicionar,
      getPayload,
      popularPicker,
      carregarPicker
    };
  }

  global.initAgenciasVinculadasForm = initAgenciasVinculadasForm;
})(window);
