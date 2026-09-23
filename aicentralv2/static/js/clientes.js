function escapeHtml(valor) {
    const elemento = document.createElement('div');
    elemento.textContent = String(valor ?? '');
    return elemento.innerHTML;
  }

  function confirmarAcaoCliente(opcoes) {
    return new Promise(resolve => {
      showConfirm({
        ...opcoes,
        onConfirm: () => resolve(true),
        onCancel: () => resolve(false)
      });
    });
  }

  // Filtros
  function salvarFiltrosClientes() {
    const form = document.getElementById('filtros_form');
    setCookie('cc_filtro_exec', form.querySelector('[name="executivo_id"]').value, 30);
    setCookie('cli_search', form.querySelector('[name="search"]').value, 30);
    setCookie('cli_status', document.getElementById('status_filter').value, 30);
    setCookie('cli_categoria', document.getElementById('categoria_filter').value, 30);
    setCookie('cli_agencia', document.getElementById('agencia_filter').value, 30);
  }

  function filtrarStatus(status) {
    document.getElementById('status_filter').value = status;
    salvarFiltrosClientes();
    document.getElementById('filtros_form').submit();
  }

  function filtrarCategoria(cat) {
    document.getElementById('categoria_filter').value = cat;
    salvarFiltrosClientes();
    document.getElementById('filtros_form').submit();
  }

  function filtrarAgencia(valor) {
    document.getElementById('agencia_filter').value = valor;
    salvarFiltrosClientes();
    document.getElementById('filtros_form').submit();
  }

  document.getElementById('filtros_form').addEventListener('submit', function() {
    salvarFiltrosClientes();
  });

  (function restoreClientesFilters() {
    const params = new URLSearchParams(window.location.search);
    if (params.has('_restored')) {
      params.delete('_restored');
      const cleanedQuery = params.toString();
      window.history.replaceState({}, '', window.__CLIENTES_CONFIG.clientesUrl + (cleanedQuery ? '?' + cleanedQuery : ''));
    }
    const cExec = getCookie('cc_filtro_exec');
    const cSearch = getCookie('cli_search');
    const cStatus = getCookie('cli_status');
    const cCat = getCookie('cli_categoria');
    const cAg = getCookie('cli_agencia');
    let needsRedirect = false;
    const rp = new URLSearchParams(params);
    if (cExec && !params.has('executivo_id')) { rp.set('executivo_id', cExec); needsRedirect = true; }
    if (cSearch && !params.has('search')) { rp.set('search', cSearch); needsRedirect = true; }
    if (!params.has('status')) { rp.set('status', cStatus || 'ativo'); needsRedirect = true; }
    if (cCat && !params.has('categoria')) { rp.set('categoria', cCat); needsRedirect = true; }
    if (!params.has('agencia')) { rp.set('agencia', cAg || 'nao'); needsRedirect = true; }
    if (!needsRedirect) return;
    window.location.href = window.__CLIENTES_CONFIG.clientesUrl + '?' + rp.toString();
  })();

  // Recategorizar ABC
  function recategorizarABC() {
    showConfirm({
      title: 'Recalcular categorias ABC',
      message: 'Deseja recalcular as categorias de todos os clientes?',
      detail: '<strong>A</strong>: aprovações a partir de R$ 200 mil/mês<br><strong>B</strong>: cliente ativo abaixo de R$ 200 mil/mês<br><strong>C</strong>: sem briefings ou cotações',
      confirmText: 'Recalcular',
      theme: 'warning',
      onConfirm: executarRecategorizacaoABC
    });
  }

  async function executarRecategorizacaoABC() {
    try {
      const response = await fetch('/admin/clientes/recategorizar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });

      const data = await response.json();

      if (data.success) {
        showToast(data.message, 'success');
        location.reload();
      } else {
        showToast('Erro: ' + data.message, 'error');
      }
    } catch (error) {
      showToast('Erro ao recategorizar: ' + error.message, 'error');
    }
  }

const LOGGED_USER_ID = window.__CLIENTES_CONFIG?.loggedUserId ?? 0;
let agenciasVinculadasCtrl = null;

function renderAgenciasVinculadasForm(agencias) {
  agenciasVinculadasCtrl?.render(agencias);
}

function atualizarVisibilidadeAgenciasVinculadas() {
  agenciasVinculadasCtrl?.updateVisibility();
}

// Funções do Modal de Cliente
document.addEventListener('DOMContentLoaded', function() {
  const formCliente = document.getElementById('form_cliente');

  agenciasVinculadasCtrl = initAgenciasVinculadasForm({
    blockId: 'agencias_vinculadas_fields',
    pickerId: 'agencias-vinculadas-picker',
    listaId: 'agencias-vinculadas-lista',
    hiddenId: 'agencias-vinculadas-hidden',
    addBtnId: 'btn-agencia-vinculada-add',
    getAgenciaSelect: () => document.querySelector('#form_cliente select[name="pk_id_tbl_agencia"]'),
    getPessoa: () => document.querySelector('#form_cliente input[name="pessoa"]:checked')?.value || 'J',
  });
  agenciasVinculadasCtrl.carregarPicker().then(() => agenciasVinculadasCtrl.popularPicker());

  if (formCliente) {
    // Handler para mudança de pessoa (PF/PJ) no modal
    const pessoaRadios = formCliente.querySelectorAll('input[name="pessoa"]');
    pessoaRadios.forEach(radio => {
      radio.addEventListener('change', togglePessoaFieldsModal);
    });

    const selAgenciaCliente = formCliente.querySelector('select[name="pk_id_tbl_agencia"]');
    if (selAgenciaCliente) {
      selAgenciaCliente.addEventListener('change', () => {
        atualizarVisibilidadeBv();
        atualizarVisibilidadeAgenciasVinculadas();
      });
    }

    const selTipoCliente = document.getElementById('select_tipo_cliente');
    if (selTipoCliente) {
      selTipoCliente.addEventListener('change', atualizarVisibilidadeBv);
    }

    // Handler para blur do CNPJ/CPF no modal
    const cnpjInput = document.getElementById('input_cnpj');
    if (cnpjInput) {
      cnpjInput.addEventListener('blur', onCnpjCpfBlur);
    }

    // Handler para submit do formulário
    formCliente.addEventListener('submit', async function(e) {
      e.preventDefault();

      const clienteId = document.getElementById('cliente_id').value;
      const formData = new FormData(formCliente);
      formData.set('_return_json', '1');
      const url = clienteId ? `/clientes/${clienteId}/editar` : '/clientes/novo';

      try {
        const response = await fetch(url, {
          method: 'POST',
          body: formData,
          redirect: 'manual'
        });

        const data = await response.json().catch(() => null);

        if (data && data.success) {
          modal_cliente.close();

          if (data.warning) {
            showToast(data.warning, 'warning');
          }

          if (clienteId) {
            showToast('Cliente atualizado com sucesso!', 'success');
            window.location.reload();
          } else {
            const novoClienteId = data.id_cliente;

            if (novoClienteId) {
              const clienteResponse = await fetch(`/api/cliente/${novoClienteId}`);
              const cliente = await clienteResponse.json();

              const tbody = document.querySelector('table tbody');
              const novaLinha = document.createElement('tr');
              novaLinha.className = 'hover';
              novaLinha.innerHTML = `
                <td>
                  <div class="font-semibold text-slate-900">${cliente.nome_fantasia || cliente.razao_social}</div>
                  ${cliente.nome_fantasia && cliente.razao_social !== cliente.nome_fantasia ? `<div class="text-xs text-slate-500">${cliente.razao_social}</div>` : ''}
                </td>
                <td>
                  ${cliente.executivo_nome ? `<span class="text-slate-900">${cliente.executivo_nome}</span>` : `<span class="text-slate-400 italic">Não atribuído</span>`}
                </td>
                <td class="text-center">${cliente.pessoa}</td>
                <td class="text-center">
                  ${cliente.nome_fantasia && cliente.nome_fantasia.toUpperCase() !== 'CENTRALCOMM' ? `
                    <button type="button"
                            class="cx-badge cursor-pointer transition-all hover:scale-105"
                            style="${cliente.status ? 'background-color: #72cd80; color: white; border-color: #72cd80;' : 'background-color: #ef4444; color: white; border-color: #ef4444;'}"
                            onclick="toggleStatus(${cliente.id_cliente}, this, ${cliente.status})"
                            title="Clique para ${cliente.status ? 'desativar' : 'ativar'}">
                      ${cliente.status ? 'Ativo' : 'Inativo'}
                    </button>
                  ` : `
                    <span class="cx-badge cx-badge-success">
                      <i class="fas fa-lock mr-1"></i>Ativo
                    </span>
                  `}
                </td>
                <td class="text-center">
                  <span class="cx-badge cx-badge-muted">0</span>
                </td>
                <td>
                  <div class="flex items-center justify-center gap-1">
                    <button onclick="abrirModalEditar(${cliente.id_cliente})" class="cx-btn cx-btn-xs cx-btn-icon cx-btn-outline cx-btn-primary" title="Editar">
                      <i class="fas fa-edit"></i>
                    </button>
                    <button id="btn_detalhes_${cliente.id_cliente}"
                       onclick="abrirModalDetalhes(${cliente.id_cliente})"
                       class="cx-btn cx-btn-xs cx-btn-icon cx-btn-outline cx-btn-info"
                       title="Detalhes">
                      <i class="fas fa-eye"></i>
                    </button>
                  </div>
                </td>
              `;

              tbody.insertBefore(novaLinha, tbody.firstChild);
              showToast(`Cliente "${data.nome_fantasia}" criado com sucesso!`, 'success');
            } else {
              showToast('Cliente criado com sucesso!', 'success');
              window.location.reload();
            }
          }
        } else {
          const msg = (data && data.message) || 'Erro ao salvar cliente.';
          showToast(msg, 'error');
        }
      } catch (error) {
        console.error('Erro:', error);
        showToast('Erro ao salvar cliente.', 'error');
      }
    });

    // Inicializar campos ao abrir modal
    togglePessoaFieldsModal();
  }
});

// Função para abrir modal para novo cliente
function abrirModalNovo() {
  document.getElementById('form_cliente').reset();
  document.getElementById('modal_title').textContent = 'Novo cliente';
  document.getElementById('cliente_id').value = '';
  document.getElementById('btn_submit_text').textContent = 'Cadastrar cliente';
  _ultimoCepBuscado = '';

  // Resetar para Pessoa Jurídica
  document.querySelector('input[name="pessoa"][value="J"]').checked = true;

  // Limpar mensagens de erro
  document.getElementById('cnpjcpf_msg').innerText = '';
  const inpMargem = document.querySelector('#form_cliente input[name="margem_cc"]');
  if (inpMargem) inpMargem.value = '';
  const selClassificacao = document.querySelector('#form_cliente select[name="classificacao_cliente"]');
  if (selClassificacao) selClassificacao.value = 'Prospecção';
  const selOperaMidia = document.querySelector('#form_cliente select[name="opera_midia"]');
  if (selOperaMidia) selOperaMidia.value = '0';
  const selDemandaDados = document.querySelector('#form_cliente select[name="demanda_dados"]');
  if (selDemandaDados) selDemandaDados.value = '0';
  const selDemandaProgramatica = document.querySelector('#form_cliente select[name="demanda_programatica_canais"]');
  if (selDemandaProgramatica) selDemandaProgramatica.value = '0';
  const obsComerciais = document.querySelector('#form_cliente textarea[name="observacoes_comerciais_adicionais"]');
  if (obsComerciais) obsComerciais.value = '';
  const hintMargem = document.getElementById('margem_cc_hint');
  if (hintMargem) hintMargem.textContent = '';

  // Atualizar campos visíveis
  togglePessoaFieldsModal();
  agenciasVinculadasCtrl?.reset();

  // Ocultar status, abas e botão excluir (modo novo)
  document.getElementById('status_toggle_container').style.display = 'none';
  document.getElementById('tabs_container').style.display = 'none';
  document.getElementById('btn_excluir_cliente').style.display = 'none';

  // Mostrar apenas o formulário
  document.querySelectorAll('.modal-tab-content').forEach(content => {
    if (content.dataset.tab === 'editar') {
      content.classList.remove('hidden');
      content.style.display = '';
    } else {
      content.classList.add('hidden');
      content.style.display = 'none';
    }
  });

  // Pré-selecionar executivo de vendas logado
  const selectVendas = document.querySelector('select[name="vendas_central_comm"]');
  const optionLogado = selectVendas.querySelector(`option[value="${LOGGED_USER_ID}"]`);
  if (optionLogado) {
    selectVendas.value = LOGGED_USER_ID;
  }

  // Abrir modal
  modal_cliente.showModal();
}

// Função para abrir modal em modo de edição
async function abrirModalEditar(clienteId) {
  try {
    // Buscar dados do cliente
    const response = await fetch(`/api/cliente/${clienteId}`);
    const cliente = await response.json();

    // Foto de colaborador só vale para a CentralComm
    window.__clienteEhCentralComm = (cliente.nome_fantasia || '').trim().toUpperCase() === 'CENTRALCOMM';

    // Buscar contatos do cliente
    const contatosResponse = await fetch(`/api/cliente/${clienteId}/contatos`);
    const contatos = await contatosResponse.json();

    // Preencher o formulário
    document.getElementById('modal_title').textContent = cliente.nome_fantasia || cliente.razao_social;
    document.getElementById('cliente_id').value = clienteId;
    document.getElementById('btn_submit_text').textContent = 'Salvar alterações';

    // Tipo de pessoa
    const pessoaRadio = document.querySelector(`input[name="pessoa"][value="${cliente.pessoa}"]`);
    if (pessoaRadio) pessoaRadio.checked = true;

    // Campos básicos
    document.getElementById('select_tipo_cliente').value = cliente.id_tipo_cliente || '';
    document.getElementById('input_cnpj').value = cliente.cnpj || '';
    document.getElementById('input_razao_social').value = cliente.razao_social || '';
    document.getElementById('input_nome_fantasia').value = cliente.nome_fantasia || '';
    const selClassificacao = document.querySelector('#form_cliente select[name="classificacao_cliente"]');
    if (selClassificacao) selClassificacao.value = cliente.classificacao_cliente || 'Prospecção';
    const selOperaMidia = document.querySelector('#form_cliente select[name="opera_midia"]');
    if (selOperaMidia) selOperaMidia.value = cliente.opera_midia ? '1' : '0';
    const selDemandaDados = document.querySelector('#form_cliente select[name="demanda_dados"]');
    if (selDemandaDados) selDemandaDados.value = cliente.demanda_dados ? '1' : '0';
    const selDemandaProgramatica = document.querySelector('#form_cliente select[name="demanda_programatica_canais"]');
    if (selDemandaProgramatica) selDemandaProgramatica.value = cliente.demanda_programatica_canais ? '1' : '0';
    const obsComerciais = document.querySelector('#form_cliente textarea[name="observacoes_comerciais_adicionais"]');
    if (obsComerciais) obsComerciais.value = cliente.observacoes_comerciais_adicionais || '';

    // Inscrições
    document.querySelector('input[name="inscricao_estadual"]').value = cliente.inscricao_estadual || '';
    document.querySelector('input[name="inscricao_municipal"]').value = cliente.inscricao_municipal || '';

    // Endereço
    document.getElementById('cep').value = cliente.cep || '';
    document.getElementById('estado').value = cliente.estado || '';
    document.getElementById('cidade').value = cliente.cidade || '';
    document.getElementById('bairro').value = cliente.bairro || '';
    document.getElementById('logradouro').value = cliente.logradouro || '';
    document.getElementById('numero').value = cliente.numero || '';
    document.getElementById('complemento').value = cliente.complemento || '';

    // Informações comerciais
    document.querySelector('select[name="vendas_central_comm"]').value = cliente.vendas_central_comm || '';
    document.querySelector('select[name="pk_id_tbl_agencia"]').value = cliente.pk_id_tbl_agencia || '';
    renderAgenciasVinculadasForm(cliente.agencias_vinculadas || []);
    atualizarVisibilidadeAgenciasVinculadas();

    const inpMargemEd = document.querySelector('#form_cliente input[name="margem_cc"]');
    if (inpMargemEd) {
      inpMargemEd.value = (cliente.margem_cc !== undefined && cliente.margem_cc !== null && cliente.margem_cc !== '')
        ? String(parseInt(cliente.margem_cc, 10))
        : '';
    }

    // BV (percentual) - formatar com vírgula
    var feeVal = cliente.fee != null ? cliente.fee : cliente.percentual;
    if (feeVal) {
      const percentualFormatado = parseFloat(feeVal).toFixed(2).replace('.', ',');
      var feeInput = document.querySelector('input[name="fee"]');
      if (feeInput) feeInput.value = percentualFormatado;
    } else {
      var feeInputEmpty = document.querySelector('input[name="fee"]');
      if (feeInputEmpty) feeInputEmpty.value = '';
    }

    // Status do cliente
    document.getElementById('status_toggle_container').style.display = '';
    document.getElementById('btn_excluir_cliente').style.display = '';
    toggleStatusField(!!cliente.status);

    _ultimoCepBuscado = cliente.cep ? cliente.cep.replace(/\D/g, '') : '';

    // Atualizar campos visíveis baseado no tipo de pessoa
    togglePessoaFieldsModal();
    atualizarHintMargemCc();

    // Preencher aba de detalhes
    preencherAbaDetalhes(cliente, contatos);

    // Mostrar abas (modo edição)
    document.getElementById('tabs_container').style.display = '';
    trocarAba('editar'); // Começar na aba Editar

    // Abrir modal
    modal_cliente.showModal();
  } catch (error) {
    console.error('Erro ao carregar cliente:', error);
    showToast('Erro ao carregar dados do cliente.', 'error');
  }
}

// Máscara para percentual XX,XX
function mascaraPercentual(input) {
  // Remove tudo que não é dígito
  let valor = input.value.replace(/\D/g, '');

  // Se vazio, limpa o campo
  if (valor.length === 0) {
    input.value = '';
    return;
  }

  // Limita a 4 dígitos (9999 = 99,99)
  if (valor.length > 4) {
    valor = valor.substring(0, 4);
  }

  // Converte para número e divide por 100 para ter 2 casas decimais
  const numero = parseInt(valor) / 100;

  // Formata com 2 casas decimais e substitui ponto por vírgula
  input.value = numero.toFixed(2).replace('.', ',');
}

function _selecionarOptionPorTexto(selectEl, texto) {
  if (!selectEl) return;
  const normalizado = texto.trim().toLowerCase();
  for (const opt of selectEl.options) {
    if (opt.text.trim().toLowerCase() === normalizado) {
      selectEl.value = opt.value;
      return;
    }
  }
}

function togglePessoaFieldsModal() {
  const pessoa = document.querySelector('#form_cliente input[name="pessoa"]:checked')?.value || 'J';

  const labelJ = document.getElementById('label_pessoa_j');
  const labelF = document.getElementById('label_pessoa_f');
  labelJ?.classList.toggle('is-active', pessoa === 'J');
  labelF?.classList.toggle('is-active', pessoa === 'F');

  // Campos específicos de PJ
  const tipoClienteField = document.getElementById('tipo_cliente_fields');
  const selectTipoCliente = document.getElementById('select_tipo_cliente');
  const agenciaFields = document.getElementById('agencia_fields');
  const inscricoesFields = document.getElementById('inscricoes_fields');
  const razaoSocialFields = document.getElementById('razao_social_fields');
  const inputRazaoSocial = document.getElementById('input_razao_social');

  const selectAgencia = document.querySelector('select[name="pk_id_tbl_agencia"]');

  if (pessoa === 'F') {
    // Pessoa Física — campos ocultos com valores automáticos
    tipoClienteField.style.display = 'none';
    selectTipoCliente.required = false;
    agenciaFields.style.display = 'none';
    if (selectAgencia) selectAgencia.required = false;
    inscricoesFields.style.display = 'none';
    razaoSocialFields.style.display = 'none';
    inputRazaoSocial.required = false;

    _selecionarOptionPorTexto(selectTipoCliente, 'Privado');
    _selecionarOptionPorTexto(selectAgencia, 'Não');

    document.getElementById('label_cnpj').innerText = 'CPF';
    document.getElementById('input_cnpj').placeholder = 'Digite o CPF';
    document.getElementById('label_nome_fantasia').innerText = 'Nome Completo *';
    document.getElementById('input_nome_fantasia').placeholder = 'Digite o nome completo';
  } else {
    // Pessoa Jurídica
    tipoClienteField.style.display = '';
    selectTipoCliente.required = true;
    agenciaFields.style.display = '';
    if (selectAgencia) selectAgencia.required = true;
    inscricoesFields.style.display = '';
    razaoSocialFields.style.display = '';
    inputRazaoSocial.required = true;

    document.getElementById('label_cnpj').innerText = 'CNPJ';
    document.getElementById('input_cnpj').placeholder = 'Digite o CNPJ';
    document.getElementById('label_nome_fantasia').innerText = 'Nome Fantasia *';
    document.getElementById('input_nome_fantasia').placeholder = 'Digite o nome fantasia';
  }

  atualizarVisibilidadeBv();
  atualizarVisibilidadeAgenciasVinculadas();
}

function clienteTipoEhParceiro() {
  const selTipo = document.getElementById('select_tipo_cliente');
  const optTipo = selTipo?.selectedOptions?.[0];
  if (optTipo && optTipo.getAttribute('data-parceiro') === '1') return true;
  return !!(optTipo && (optTipo.textContent || '').toLowerCase().includes('parceiro'));
}

function atualizarVisibilidadeBv() {
  const formCliente = document.getElementById('form_cliente');
  if (!formCliente) return;
  const pessoa = formCliente.querySelector('input[name="pessoa"]:checked')?.value || 'J';
  const percentualFields = document.getElementById('percentual_fields');
  if (!percentualFields) return;
  const inputPercentual = percentualFields.querySelector('input[name="fee"]');
  const labelPercentual = document.getElementById('percentual_label');
  if (pessoa !== 'J') {
    percentualFields.style.display = 'none';
    if (inputPercentual) inputPercentual.value = '';
    return;
  }
  const sel = formCliente.querySelector('select[name="pk_id_tbl_agencia"]');
  const opt = sel?.selectedOptions?.[0];
  const agenciaSim = opt && opt.getAttribute('data-agencia-sim') === '1';
  const parceiro = clienteTipoEhParceiro();
  if (labelPercentual) labelPercentual.textContent = parceiro ? 'Fee_pr (%)' : 'Fee_ag (%)';
  if (parceiro || agenciaSim) {
    percentualFields.style.display = '';
  } else {
    percentualFields.style.display = 'none';
    if (inputPercentual) inputPercentual.value = '';
  }
  atualizarVisibilidadeAgenciasVinculadas();
}

function renderAgenciasVinculadasDetalhes(cliente, listaId, sectionId) {
  const section = document.getElementById(sectionId);
  const container = document.getElementById(listaId);
  if (!section || !container) return;
  if (cliente.agencia_key) {
    section.style.display = 'none';
    return;
  }
  section.style.display = '';
  const agencias = cliente.agencias_vinculadas || [];
  if (!agencias.length) {
    container.innerHTML = '<div class="text-gray-400 italic">Nenhuma agência vinculada.</div>';
    return;
  }
  container.innerHTML = agencias.map(a => {
    const nome = a.nome_fantasia || a.razao_social || ('#' + a.id_agencia_cliente);
    return `<div class="flex items-center gap-2 py-0.5">${a.is_principal ? '<span class="cx-badge text-white" style="background:#166534">Principal</span>' : ''}<span>${nome}</span></div>`;
  }).join('');
}

function atualizarHintMargemCc() {
  const formCliente = document.getElementById('form_cliente');
  if (!formCliente) return;
  const inp = formCliente.querySelector('input[name="margem_cc"]');
  const hint = document.getElementById('margem_cc_hint');
  if (!inp || !hint) return;
  const raw = (inp.value || '').trim();
  if (raw === '' || isNaN(parseFloat(raw.replace(',', '.')))) {
    hint.textContent = 'Vazio/inválido: será salva como 0.';
  } else {
    hint.textContent = '';
  }
}

function toggleStatusField(ativo) {
  const labelAtivo = document.getElementById('label_status_ativo');
  const labelInativo = document.getElementById('label_status_inativo');

  if (ativo) {
    labelAtivo.querySelector('input').checked = true;
    labelAtivo.classList.add('is-active');
    labelInativo.classList.remove('is-active', 'is-danger');
  } else {
    labelInativo.querySelector('input').checked = true;
    labelInativo.classList.add('is-active', 'is-danger');
    labelAtivo.classList.remove('is-active');
  }
}

function validarCPF(cpf) {
  cpf = cpf.replace(/\D/g, '');
  if (cpf.length !== 11 || /^([0-9])\1+$/.test(cpf)) return false;
  let soma = 0, resto;
  for (let i = 1; i <= 9; i++) soma += parseInt(cpf.substring(i-1, i)) * (11 - i);
  resto = (soma * 10) % 11;
  if (resto === 10 || resto === 11) resto = 0;
  if (resto !== parseInt(cpf.substring(9, 10))) return false;
  soma = 0;
  for (let i = 1; i <= 10; i++) soma += parseInt(cpf.substring(i-1, i)) * (12 - i);
  resto = (soma * 10) % 11;
  if (resto === 10 || resto === 11) resto = 0;
  if (resto !== parseInt(cpf.substring(10, 11))) return false;
  return true;
}

async function buscarEmpresaPorCNPJ(cnpj) {
  cnpj = cnpj.replace(/\D/g, '');
  if (cnpj.length !== 14) {
    document.getElementById('cnpjcpf_msg').innerText = 'CNPJ deve ter 14 dígitos';
    return;
  }

  try {
    // Mostrar loading
    document.getElementById('cnpjcpf_msg').innerText = 'Buscando dados do CNPJ...';
    document.getElementById('cnpjcpf_msg').classList.remove('text-error');
    document.getElementById('cnpjcpf_msg').classList.add('text-info');

    // Pegar cliente_id se estiver editando
    const clienteId = document.getElementById('cliente_id').value;
    let url = '/api/buscar_cnpj/' + cnpj;
    if (clienteId) {
      url += '?cliente_id=' + clienteId;
    }

    const resp = await fetch(url);
    const result = await resp.json();

    if (result.success) {
      const data = result.data;

      // Atualizar razão social e nome fantasia
      const inputRazaoSocial = document.getElementById('input_razao_social');
      const inputNomeFantasia = document.getElementById('input_nome_fantasia');

      if (inputRazaoSocial && data.razao_social) {
        inputRazaoSocial.value = data.razao_social;
      }
      // Se nome_fantasia vier vazio da ReceitaWS, usar razão social como fallback
      if (inputNomeFantasia) {
        if (data.nome_fantasia) {
          inputNomeFantasia.value = data.nome_fantasia;
        } else if (data.razao_social) {
          inputNomeFantasia.value = data.razao_social;
        }
      }

      // Atualizar inscrições
      const inscEstadual = document.querySelector('#form_cliente input[name="inscricao_estadual"]');
      if (inscEstadual && data.inscricao_estadual) {
        inscEstadual.value = data.inscricao_estadual;
      }
      const inscMunicipal = document.querySelector('#form_cliente input[name="inscricao_municipal"]');
      if (inscMunicipal && data.inscricao_municipal) {
        inscMunicipal.value = data.inscricao_municipal;
      }

      // Atualizar campos de endereço
      if (data.cep) {
        const cepInput = document.getElementById('cep');
        if (cepInput) {
          // Formatar CEP: 12345-678
          let cepFormatado = data.cep.replace(/\D/g, '');
          if (cepFormatado.length === 8) {
            cepFormatado = cepFormatado.slice(0, 5) + '-' + cepFormatado.slice(5);
          }
          cepInput.value = cepFormatado;
        }
      }
      if (data.uf) {
        const estadoSelect = document.getElementById('estado');
        if (estadoSelect) {
          const estadoId = getEstadoIdBySigla(data.uf);
          if (estadoId) {
            estadoSelect.value = estadoId;
          }
        }
      }
      if (data.municipio) {
        const cidadeInput = document.getElementById('cidade');
        if (cidadeInput) cidadeInput.value = data.municipio;
      }
      if (data.bairro) {
        const bairroInput = document.getElementById('bairro');
        if (bairroInput) bairroInput.value = data.bairro;
      }
      if (data.logradouro) {
        const logradouroInput = document.getElementById('logradouro');
        if (logradouroInput) logradouroInput.value = data.logradouro;
      }
      if (data.numero) {
        const numeroInput = document.getElementById('numero');
        if (numeroInput) numeroInput.value = data.numero;
      }
      if (data.complemento) {
        const complementoInput = document.getElementById('complemento');
        if (complementoInput) complementoInput.value = data.complemento;
      }

      // Limpar mensagem de sucesso
      document.getElementById('cnpjcpf_msg').innerText = '';
      document.getElementById('cnpjcpf_msg').classList.remove('text-info');

      showToast('Dados do CNPJ carregados com sucesso!', 'success');
    } else {
      document.getElementById('cnpjcpf_msg').innerText = result.message || 'CNPJ inválido!';
      document.getElementById('cnpjcpf_msg').classList.remove('text-info');
      document.getElementById('cnpjcpf_msg').classList.add('text-error');
    }
  } catch (e) {
    console.error('Erro ao buscar CNPJ:', e);
    document.getElementById('cnpjcpf_msg').innerText = 'Erro ao consultar CNPJ';
    document.getElementById('cnpjcpf_msg').classList.remove('text-info');
    document.getElementById('cnpjcpf_msg').classList.add('text-error');
  }
}

async function verificarExistenciaNome() {
  const nomeEl = document.getElementById('input_nome_fantasia');
  const msgEl = document.getElementById('nome_msg');
  if (!nomeEl || !msgEl) return;
  const nome = nomeEl.value.trim();
  if (!nome) { msgEl.innerText = ''; return; }
  const clienteId = document.getElementById('cliente_id') ? document.getElementById('cliente_id').value : '';
  try {
    let url = `/api/verifica_nome?nome=${encodeURIComponent(nome)}`;
    if (clienteId) url += `&excluir_id=${encodeURIComponent(clienteId)}`;
    const resp = await fetch(url);
    const data = await resp.json();
    msgEl.innerText = data.existe ? 'Já existe um cliente cadastrado com este nome!' : '';
  } catch (e) {
    console.error('Erro ao verificar nome:', e);
  }
}

async function onCnpjCpfBlur() {
  const pessoa = document.querySelector('#form_cliente input[name="pessoa"]:checked')?.value || 'J';
  const doc = document.getElementById('input_cnpj').value.replace(/\D/g, '');
  if (!doc) return;

  if (pessoa === 'F') {
    if (!validarCPF(doc)) {
      document.getElementById('cnpjcpf_msg').innerText = 'CPF inválido!';
      return;
    }
    document.getElementById('cnpjcpf_msg').innerText = '';
  } else {
    if (doc.length !== 14) {
      document.getElementById('cnpjcpf_msg').innerText = 'CNPJ inválido!';
      return;
    }
    document.getElementById('cnpjcpf_msg').innerText = '';

    // Buscar dados na ReceitaWS (autofill)
    await buscarEmpresaPorCNPJ(doc);
  }
}

function mascaraCep(input) {
  const digits = input.value.replace(/\D/g, '').slice(0, 8);
  let formatted = digits;
  if (digits.length > 5) formatted = digits.slice(0,5) + '-' + digits.slice(5);
  input.value = formatted;
  if (digits.length === 8) {
    buscarEnderecoPorCep(digits);
  }
}

function mascaraCnpjCpf(input) {
  const pessoa = document.querySelector('#form_cliente input[name="pessoa"]:checked')?.value || 'J';
  let v = input.value.replace(/\D/g, '');

  if (pessoa === 'F') {
    // Máscara CPF: 999.999.999-99 (14 caracteres)
    v = v.slice(0, 11); // Limita a 11 dígitos
    v = v.replace(/(\d{3})(\d)/, '$1.$2');
    v = v.replace(/(\d{3})(\d)/, '$1.$2');
    v = v.replace(/(\d{3})(\d{1,2})$/, '$1-$2');
    input.maxLength = 14;
  } else {
    // Máscara CNPJ: 99.999.999/9999-99 (18 caracteres)
    v = v.slice(0, 14); // Limita a 14 dígitos
    v = v.replace(/^(\d{2})(\d)/, '$1.$2');
    v = v.replace(/^(\d{2})\.(\d{3})(\d)/, '$1.$2.$3');
    v = v.replace(/\.(\d{3})(\d)/, '.$1/$2');
    v = v.replace(/(\d{4})(\d)/, '$1-$2');
    input.maxLength = 18;
  }

  input.value = v;
}

function buscarCepEnter(event) {
  if (event.key === 'Enter') {
    event.preventDefault();
    buscarEnderecoPorCep(event.target.value);
  }
}

let _ultimoCepBuscado = '';

function buscarEnderecoPorCep(cep) {
  cep = cep.replace(/\D/g, '');

  if (cep.length === 0) {
    showToast('Digite um CEP para buscar', 'warning');
    return;
  }

  if (cep.length !== 8) {
    showToast('CEP inválido! Deve ter 8 dígitos', 'error');
    return;
  }

  if (/^(\d)\1{7}$/.test(cep)) {
    showToast('CEP inválido!', 'error');
    return;
  }

  if (cep === _ultimoCepBuscado) return;
  _ultimoCepBuscado = cep;

  const cepInput = document.getElementById('cep');
  cepInput.classList.add('opacity-50');
  cepInput.style.pointerEvents = 'none';
  showToast('Buscando endereço...', 'info');

  fetch('https://viacep.com.br/ws/' + cep + '/json/')
    .then(response => response.json())
    .then(data => {
      if (!data.erro) {
        document.getElementById('estado').value = getEstadoIdBySigla(data.uf);
        document.getElementById('cidade').value = data.localidade || '';
        document.getElementById('bairro').value = data.bairro || '';
        document.getElementById('logradouro').value = data.logradouro || '';
        showToast('Endereço preenchido!', 'success');
        document.getElementById('numero').focus();
      } else {
        showToast('CEP não encontrado!', 'error');
        _ultimoCepBuscado = '';
      }
    })
    .catch(e => {
      console.error('Erro ao buscar CEP:', e);
      showToast('Erro ao buscar CEP. Tente novamente.', 'error');
      _ultimoCepBuscado = '';
    })
    .finally(() => {
      cepInput.classList.remove('opacity-50');
      cepInput.style.pointerEvents = '';
    });
}

function getEstadoIdBySigla(sigla) {
  const select = document.getElementById('estado');
  for (let i = 0; i < select.options.length; i++) {
    const option = select.options[i];
    if (option.dataset.sigla === sigla) {
      return option.value;
    }
  }
  // Fallback
  for (let i = 0; i < select.options.length; i++) {
    if (select.options[i].text.startsWith(sigla + ' ')) {
      return select.options[i].value;
    }
  }
  return '';
}

// Função para toggle de status de cliente
async function toggleStatus(clienteId, badgeElement, statusAtual) {
  const novoStatus = !statusAtual;

  // Desabilitar badge durante a requisição
  badgeElement.disabled = true;
  badgeElement.classList.add('opacity-50');

  try {
    const response = await fetch(`/clientes/${clienteId}/toggle-status`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      }
    });

    if (response.ok) {
      // Atualizar o badge
      badgeElement.textContent = novoStatus ? 'Ativo' : 'Inativo';
      badgeElement.className = 'cx-badge cursor-pointer transition-all hover:scale-105';
      badgeElement.style = novoStatus ? 'background-color: #72cd80; color: white; border-color: #72cd80;' : 'background-color: #ef4444; color: white; border-color: #ef4444;';
      badgeElement.title = `Clique para ${novoStatus ? 'desativar' : 'ativar'}`;
      badgeElement.setAttribute('onclick', `toggleStatus(${clienteId}, this, ${novoStatus})`);
    } else {
      showToast('Erro ao alterar status do cliente.', 'error');
    }
  } catch (error) {
    console.error('Erro:', error);
    showToast('Erro ao alterar status do cliente.', 'error');
  } finally {
    badgeElement.disabled = false;
    badgeElement.classList.remove('opacity-50');
  }
}

// Função para abrir modal de detalhes
let clienteIdAtual = null;

async function abrirModalDetalhes(clienteId) {
  clienteIdAtual = clienteId;
  await abrirModalEditar(clienteId);
  trocarAba('detalhes');
}

async function criarPlanoBetaTester(clienteId) {
  const confirmado = await confirmarAcaoCliente({
    title: 'Criar plano Beta Tester',
    message: 'Deseja criar um plano Beta Tester para este cliente?',
    detail: '100.000 tokens/mês<br>50 imagens/mês<br>10 usuários<br>Validade de 3 meses',
    confirmText: 'Criar plano',
    theme: 'primary'
  });
  if (!confirmado) return;

  fetch(`/api/cliente/${clienteId}/criar-plano-beta`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'same-origin'
  })
  .then(response => {
    const contentType = response.headers.get('content-type');
    if (!contentType || !contentType.includes('application/json')) {
      throw new Error('Servidor retornou resposta inválida. Verifique se está logado.');
    }
    return response.json();
  })
  .then(data => {
    if (data.success) {
      showToast('Plano Beta Tester criado com sucesso!', 'success');

      // Recarregar lista de contratos se estiver na aba de contratos
      if (document.getElementById('contratos_aba_content') &&
          document.getElementById('contratos_aba_content').style.display !== 'none') {
        carregarContratosCliente(clienteId);
      }

      // Atualizar a cor do botão de detalhes na listagem
      const btnDetalhes = document.getElementById(`btn_detalhes_${clienteId}`);
      if (btnDetalhes) {
        btnDetalhes.classList.remove('cx-btn-info');
        btnDetalhes.classList.add('cx-btn-success');
        btnDetalhes.title = 'Detalhes - 1 plano(s) ativo(s)';
      }
      modal_cliente.close();
    } else {
      if (data.error && (data.error.includes('Sessão') || data.error.includes('login'))) {
        showToast(data.error + ' Você será redirecionado para a página de login.', 'error');
        setTimeout(() => { window.location.href = '/login'; }, 2000);
      } else {
        showToast('Erro ao criar plano: ' + (data.error || 'Erro desconhecido'), 'error');
      }
    }
  })
  .catch(error => {
    console.error('Erro completo:', error);
    showToast('Erro na requisição: ' + error.message, 'error');
  });
}

// Função para filtrar clientes por executivo e agência
function filtrarClientes() {
  const pesquisa = document.getElementById('pesquisa_cliente')?.value.toLowerCase().trim() || '';
  const filtroExecutivo = document.getElementById('filtro_executivo')?.value || '';
  const filtroAgencia = document.getElementById('filtro_agencia')?.value || '';
  const tbody = document.querySelector('table tbody');
  const linhas = tbody.querySelectorAll('tr');
  let totalVisiveis = 0;

  linhas.forEach(linha => {
    const nomeCell = linha.children[0]; // Primeira coluna = nome
    const executivoCell = linha.children[1]; // Segunda coluna = executivo

    const nomeFantasia = nomeCell.querySelector('.font-semibold')?.textContent.toLowerCase() || '';
    const razaoSocial = nomeCell.querySelector('.text-xs')?.textContent.toLowerCase() || '';
    const executivoTexto = executivoCell.textContent.trim();
    const agenciaData = linha.dataset.agencia || 'nao';

    // Verificar se passa no filtro de pesquisa
    const passaPesquisa = !pesquisa || nomeFantasia.includes(pesquisa) || razaoSocial.includes(pesquisa);

    // Verificar se passa no filtro de executivo
    let passaExecutivo = true;
    if (filtroExecutivo === 'NAO_ATRIBUIDO') {
      passaExecutivo = executivoTexto === 'Não atribuído';
    } else if (filtroExecutivo !== '') {
      passaExecutivo = executivoTexto === filtroExecutivo;
    }

    // Verificar se passa no filtro de agência
    let passaAgencia = true;
    if (filtroAgencia === 'sim') {
      passaAgencia = agenciaData === 'sim';
    } else if (filtroAgencia === 'nao') {
      passaAgencia = agenciaData === 'nao';
    }

    // Mostrar apenas se passar em todos os filtros
    if (passaPesquisa && passaExecutivo && passaAgencia) {
      linha.style.display = '';
      totalVisiveis++;
    } else {
      linha.style.display = 'none';
    }
  });

  // Atualizar contador
  const contador = document.getElementById('contador_filtro');
  const totalClientes = linhas.length;

  // Mostrar contador apenas se houver filtros ativos (agencia 'todos' não conta como filtro)
  const filtroAgenciaAtivo = filtroAgencia && filtroAgencia !== 'todos';
  if (pesquisa || filtroExecutivo || filtroAgenciaAtivo) {
    contador.textContent = `Mostrando ${totalVisiveis} de ${totalClientes} cliente(s)`;
  } else {
    contador.textContent = '';
  }
}

// Função para pesquisar cliente (chama filtrarClientes)
function pesquisarCliente() {
  filtrarClientes();
}

// Manter compatibilidade com código antigo
function filtrarPorExecutivo() {
  filtrarClientes();
}

// Função para trocar entre abas no modal
function trocarAba(aba) {
  // Atualizar botões das tabs
  document.querySelectorAll('#tabs_container .cx-tab').forEach(btn => {
    const isActive = btn.dataset.tab === aba;
    btn.classList.toggle('cx-tab-active', isActive);
    btn.setAttribute('aria-selected', String(isActive));
  });

  // Mostrar/ocultar conteúdos
  document.querySelectorAll('.modal-tab-content').forEach(content => {
    const tabName = content.dataset.tab;
    if (tabName === aba) {
      content.classList.remove('hidden');
      content.style.display = '';
    } else {
      content.classList.add('hidden');
      content.style.display = 'none';
    }
  });

  // Carregar dados específicos da aba
  const clienteId = document.getElementById('cliente_id')?.value;
  if (clienteId && aba === 'contratos') {
    carregarContratosCliente(clienteId);
  }
  if (clienteId && aba === 'contatos') {
    carregarContatosAba(clienteId);
  }
}

// Função para preencher aba de detalhes
function preencherAbaDetalhes(cliente, contatos) {
  // Preencher informações principais
  const infoPrincipais = document.getElementById('info_principais_aba');
  infoPrincipais.innerHTML = `
    <div class="flex items-center"><span class="font-semibold text-slate-600 w-16">ID:</span><span>#${cliente.id_cliente}</span></div>
    <div class="flex items-center"><span class="font-semibold text-slate-600 w-16">Status:</span><span class="cx-badge ${cliente.status ? 'cx-badge-success' : 'cx-badge-danger'}">${cliente.status ? 'Ativo' : 'Inativo'}</span></div>
    <div class="flex items-center"><span class="font-semibold text-slate-600 w-16">${cliente.pessoa === 'F' ? 'CPF' : 'CNPJ'}:</span><span>${cliente.cnpj || '—'}</span></div>
    <div class="flex items-center"><span class="font-semibold text-slate-600 w-16">Tipo:</span><span>${cliente.tipo_cliente_display || '—'}</span></div>
    ${cliente.pessoa !== 'F' ? `<div class="flex items-center md:col-span-2"><span class="font-semibold text-slate-600 w-16">Razão:</span><span class="truncate">${cliente.razao_social || '—'}</span></div>` : ''}
    <div class="flex items-center md:col-span-2"><span class="font-semibold text-slate-600 w-16">${cliente.pessoa === 'F' ? 'Nome' : 'Fantasia'}:</span><span class="truncate">${cliente.nome_fantasia || '—'}</span></div>
    <div class="flex items-center"><span class="font-semibold text-slate-600 w-16">Executivo:</span><span>${cliente.executivo_nome || '—'}</span></div>
    <div class="flex items-center md:col-span-2"><span class="font-semibold text-slate-600 w-16">Margem CC:</span><span>${(cliente.margem_cc !== undefined && cliente.margem_cc !== null && cliente.margem_cc !== '') ? cliente.margem_cc + '%' : '—'}</span></div>
    ${cliente.pessoa === 'J' && cliente.agencia_key === true && (cliente.fee || cliente.percentual) ? `<div class="flex items-center"><span class="font-semibold text-slate-600 w-16">Fee_ag:</span><span>${parseFloat(cliente.fee || cliente.percentual).toFixed(2).replace('.', ',')}%</span></div>` : ''}
    ${cliente.pessoa !== 'F' ? `<div class="flex items-center"><span class="font-semibold text-slate-600 w-16">Insc. Est.:</span><span>${cliente.inscricao_estadual || '—'}</span></div><div class="flex items-center"><span class="font-semibold text-slate-600 w-16">Insc. Mun.:</span><span>${cliente.inscricao_municipal || '—'}</span></div>` : ''}
  `;

  // Preencher endereço se existir
  const enderecoSection = document.getElementById('endereco_section_aba');
  const infoEndereco = document.getElementById('info_endereco_aba');
  if (cliente.cep || cliente.logradouro || cliente.cidade) {
    enderecoSection.style.display = '';
    infoEndereco.innerHTML = `
      <div class="flex items-center"><span class="font-semibold text-slate-600 w-16">CEP:</span><span>${cliente.cep || '—'}</span></div>
      <div class="flex items-center"><span class="font-semibold text-slate-600 w-16">Estado:</span><span>${cliente.estado_nome || '—'}</span></div>
      <div class="flex items-center"><span class="font-semibold text-slate-600 w-16">Cidade:</span><span>${cliente.cidade || '—'}</span></div>
      <div class="flex items-center"><span class="font-semibold text-slate-600 w-16">Bairro:</span><span>${cliente.bairro || '—'}</span></div>
      <div class="flex items-center md:col-span-4"><span class="font-semibold text-slate-600 w-16">Endereço:</span><span class="truncate">${cliente.logradouro || '—'}${cliente.numero ? ', ' + cliente.numero : ''}${cliente.complemento ? ' - ' + cliente.complemento : ''}</span></div>
    `;
  } else {
    enderecoSection.style.display = 'none';
  }

  renderAgenciasVinculadasDetalhes(cliente, 'agencias_vinculadas_lista_aba', 'agencias_vinculadas_section_aba');

  // Preencher contatos
  const listaContatos = document.getElementById('lista_contatos_aba');
  if (contatos && contatos.length > 0) {
    listaContatos.innerHTML = contatos.map(c => renderContatoRowHtml(c, cliente.id_cliente)).join('');
  } else {
    listaContatos.innerHTML = '<p class="cliente-contato-empty">Nenhum contato vinculado</p>';
  }

  // Carregar contratos do cliente
  carregarContratosCliente(cliente.id_cliente);
}


function contatoInviteBadgeClass(status) {
  if (status === 'accepted') return 'cx-badge-success';
  if (status === 'pending') return 'cx-badge-warning';
  return 'cx-badge-muted';
}

function contatoInviteLabel(status) {
  if (status === 'accepted') return 'Aceito';
  if (status === 'pending') return 'Pendente';
  return 'Sem convite';
}

function renderContatoRowHtml(c, clienteId) {
  const nomeEsc = (c.nome_completo || '').replace(/'/g, "\\'");
  const statusClass = c.status ? 'cx-badge-success' : 'cx-badge-danger';
  const inviteClass = contatoInviteBadgeClass(c.invite_status);
  const inviteLabel = contatoInviteLabel(c.invite_status);
  return `<div class="cliente-contato-row" data-contato-id="${c.id_contato_cliente}">
    <button type="button" class="cliente-contato-main" onclick="abrirModalEditarContato(${c.id_contato_cliente})">
      <span class="cliente-contato-nome">${escapeHtml(c.nome_completo)}</span>
      <span class="cliente-contato-email">${escapeHtml(c.email || '—')}</span>
    </button>
    <div class="cliente-contato-actions">
      <button type="button" class="cx-badge ${statusClass} cliente-contato-status" onclick="toggleContatoStatus(${c.id_contato_cliente}, ${clienteId}, this, ${c.status})">${c.status ? 'Ativo' : 'Inativo'}</button>
      <span class="cx-badge ${inviteClass}">${inviteLabel}</span>
      ${contatoInviteBtnHtml(c)}
      <button type="button" class="cx-btn cx-btn-icon cx-btn-ghost cx-btn-xs cliente-contato-delete" title="Excluir contato" onclick="deletarContato(${c.id_contato_cliente}, ${clienteId}, '${nomeEsc}')"><i class="fas fa-trash" aria-hidden="true"></i></button>
    </div>
  </div>`;
}

// Avatar do contato: usa foto_url se houver, senão iniciais (mesma lógica do perfil)
// Aplicável somente a colaboradores da CentralComm
function contatoAvatarHtml(c) {
  if (!window.__clienteEhCentralComm) return '';
  const nome = c.nome_completo || '';
  if (c.foto_url) {
    return `<div class="cx-avatar shrink-0"><div class="rounded-full w-7 h-7"><img src="${c.foto_url}" alt="Foto"></div></div>`;
  }
  const iniciais = nome.substring(0, 2).toUpperCase() || 'U';
  return `<div class="cx-avatar shrink-0"><div class="bg-[#1e4d4f] text-white rounded-full w-7 h-7 text-xs"><span class="font-semibold">${iniciais}</span></div></div>`;
}

// Função para carregar contatos na aba
async function carregarContatosAba(clienteId) {
  const listaContatos = document.getElementById('lista_contatos_aba');

  if (!listaContatos) {
    console.error('Elemento lista_contatos_aba não encontrado');
    return;
  }

  try {
    const response = await fetch(`/api/cliente/${clienteId}/contatos`);
    if (!response.ok) throw new Error('Erro ao buscar contatos');

    const contatos = await response.json();

    if (contatos && contatos.length > 0) {
      listaContatos.innerHTML = contatos.map(c => renderContatoRowHtml(c, clienteId)).join('');
    } else {
      listaContatos.innerHTML = '<p class="cliente-contato-empty">Nenhum contato vinculado</p>';
    }

  } catch (error) {
    console.error('Erro ao carregar contatos:', error);
    listaContatos.innerHTML = '<p class="cliente-contato-empty cliente-contato-empty--error">Erro ao carregar contatos</p>';
  }
}

// Função para carregar contratos do cliente
async function carregarContratosCliente(clienteId) {
  const listaContratos = document.getElementById('lista_contratos_aba');

  if (!listaContratos) {
    console.error('Elemento lista_contratos_aba não encontrado');
    return;
  }

  listaContratos.innerHTML = '<p class="text-center text-slate-500 text-sm py-4">Carregando...</p>';

  try {
    const response = await fetch(`/api/cliente/${clienteId}/planos`);
    const data = await response.json();

    if (data.success && data.planos && data.planos.length > 0) {
      listaContratos.innerHTML = `
        <div class="overflow-x-auto">
          <table class="cx-table cx-table-dense w-full">
            <thead class="text-white rounded-lg" style="background-color: #72cd80;">
              <tr>
                <th class="rounded-tl-lg">Tipo</th>
                <th>Status</th>
                <th>Tokens</th>
                <th>Imagens</th>
                <th>Usuários</th>
                <th class="rounded-tr-lg">Validade</th>
              </tr>
            </thead>
            <tbody>
              ${data.planos.map(p => `
                <tr class="hover">
                  <td class="font-semibold">${p.plan_name || '—'}</td>
                  <td>
                    <button type="button"
                            class="cx-badge cursor-pointer transition-all hover:scale-105"
                            style="${p.plan_status === 'active' ? 'background-color: #72cd80; color: white; border-color: #72cd80;' : p.plan_status === 'suspended' ? 'background-color: #fbbf24; color: white; border-color: #fbbf24;' : 'background-color: #ef4444; color: white; border-color: #ef4444;'}"
                            onclick="togglePlanoStatus(${p.id}, this, '${p.plan_status}')"
                            title="Clique para ${p.plan_status === 'active' ? 'cancelar' : 'ativar'}">
                      ${p.plan_status === 'active' ? 'Ativo' : p.plan_status === 'suspended' ? 'Suspenso' : 'Cancelado'}
                    </button>
                  </td>
                  <td>
                    <div class="text-xs">
                      ${(p.tokens_used_current_month || 0).toLocaleString()} / ${(p.tokens_monthly_limit || 0).toLocaleString()}
                    </div>
                    <div class="text-xs text-slate-500">${p.tokens_usage_percentage || 0}%</div>
                  </td>
                  <td>
                    <div class="text-xs">
                      ${p.image_credits_used_current_month || 0} / ${p.image_credits_monthly || 0}
                    </div>
                    <div class="text-xs text-slate-500">${p.images_usage_percentage || 0}%</div>
                  </td>
                  <td>${p.max_users || '—'}</td>
                  <td class="text-xs">${p.valid_until ? new Date(p.valid_until).toLocaleDateString('pt-BR') : '—'}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      `;
    } else {
      listaContratos.innerHTML = '<p class="text-center text-slate-500 text-sm py-4">Nenhuma assinatura encontrada</p>';
    }
  } catch (error) {
    console.error('Erro ao carregar assinaturas:', error);
    listaContratos.innerHTML = '<p class="text-center text-error text-sm py-4">Erro ao carregar assinaturas</p>';
  }
}

// Função para toggle de status de plano
async function togglePlanoStatus(planoId, badgeElement, statusAtual) {
  try {
    const response = await fetch(`/api/plano/${planoId}/toggle-status`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      }
    });

    if (response.ok) {
      const data = await response.json();
      const novoStatus = data.novo_status;

      // Atualizar o badge
      badgeElement.textContent = novoStatus === 'active' ? 'Ativo' : novoStatus === 'suspended' ? 'Suspenso' : 'Cancelado';
      badgeElement.className = 'cx-badge cursor-pointer transition-all hover:scale-105';

      if (novoStatus === 'active') {
        badgeElement.style = 'background-color: #72cd80; color: white; border-color: #72cd80;';
        badgeElement.title = 'Clique para cancelar';
      } else if (novoStatus === 'suspended') {
        badgeElement.style = 'background-color: #fbbf24; color: white; border-color: #fbbf24;';
        badgeElement.title = 'Clique para ativar';
      } else {
        badgeElement.style = 'background-color: #ef4444; color: white; border-color: #ef4444;';
        badgeElement.title = 'Clique para ativar';
      }

      badgeElement.setAttribute('onclick', `togglePlanoStatus(${planoId}, this, '${novoStatus}')`);
    } else {
      showToast('Erro ao alterar status do plano.', 'error');
    }
  } catch (error) {
    console.error('Erro ao alterar status do plano:', error);
    showToast('Erro ao alterar status do plano.', 'error');
  }
}

// Função para criar plano beta tester da aba
function criarPlanoBetaTesterAba() {
  const clienteId = document.getElementById('cliente_id').value;
  if (clienteId) {
    criarPlanoBetaTester(clienteId);
  }
}

// Função para abrir modal de novo contato
function abrirModalNovoContato() {
  const clienteId = document.getElementById('cliente_id').value;
  if (clienteId) {
    // Resetar formulário
    document.getElementById('form_contato').reset();
    document.getElementById('contato_id').value = '';
    document.getElementById('contato_cliente_id').value = clienteId;

    // Atualizar título e botão
    document.getElementById('contato_modal_title').textContent = 'Novo Contato';
    document.getElementById('contato_btn_text').textContent = 'Criar contato';

    // Ocultar campo telefone em novo contato
    document.getElementById('contato_telefone_container').classList.add('hidden');
    document.getElementById('contato_telefone_secundario_container').classList.add('hidden');
    if (document.getElementById('contato_wasender_api_key')) {
      document.getElementById('contato_wasender_api_key').value = '';
      document.getElementById('contato_wasender_session_id').value = '';
      document.getElementById('contato_wasender_ativo').checked = false;
      document.getElementById('contato_wasender_api_key_mask').textContent = '';
    }
    // Ajustar largura dos campos nome e email para ocupar todo o espaço
    document.getElementById('contato_nome_container').classList.remove('col-span-4');
    document.getElementById('contato_nome_container').classList.add('col-span-6');
    document.getElementById('contato_email_container').classList.remove('col-span-4');
    document.getElementById('contato_email_container').classList.add('col-span-6');

    // Limpar select de cargos
    const cargoSelect = document.getElementById('contato_cargo');
    cargoSelect.innerHTML = '<option value="">Selecione setor</option>';

    // Foto só fica disponível na edição (precisa do id do contato)
    document.getElementById('contato_foto_container').classList.add('hidden');

    // Abrir modal
    modal_contato.showModal();
  }
}

// Renderiza o avatar do contato no modal (foto ou iniciais) e configura o upload
function configurarFotoContato(contato) {
  const container = document.getElementById('contato_foto_container');
  const avatar = document.getElementById('contato_foto_avatar');
  const input = document.getElementById('contato_foto_input');
  const msg = document.getElementById('contato_foto_msg');
  const label = document.getElementById('contato_foto_label');
  if (!container || !avatar || !input) return;

  // Foto de colaborador só vale para a CentralComm
  const ehCentralComm = (contato.nome_fantasia || '').trim().toUpperCase() === 'CENTRALCOMM';
  if (!ehCentralComm) {
    container.classList.add('hidden');
    return;
  }

  msg.textContent = '';
  label.textContent = 'Alterar foto';

  const nome = contato.nome_completo || '';
  if (contato.foto_url) {
    avatar.innerHTML = `<div class="cx-avatar"><div class="rounded-full w-12 h-12"><img id="contato_foto_img" src="${contato.foto_url}" alt="Foto"></div></div>`;
  } else {
    const iniciais = nome.substring(0, 2).toUpperCase() || 'U';
    avatar.innerHTML = `<div class="cx-avatar"><div class="bg-[#1e4d4f] text-white rounded-full w-12 h-12 text-sm"><span class="font-semibold">${iniciais}</span></div></div>`;
  }
  container.classList.remove('hidden');

  // Substitui o input para limpar listeners anteriores
  const novoInput = input.cloneNode(true);
  input.parentNode.replaceChild(novoInput, input);
  novoInput.addEventListener('change', function () {
    const file = novoInput.files && novoInput.files[0];
    if (!file) return;
    msg.textContent = 'Enviando...';
    msg.className = 'text-xs text-slate-500 ml-1';
    label.textContent = 'Enviando...';

    const fd = new FormData();
    fd.append('foto', file);
    fetch(`/api/contato/${contato.id_contato_cliente}/foto`, { method: 'POST', body: fd })
      .then(r => r.json())
      .then(data => {
        if (data && data.success) {
          const cacheBust = data.foto_url + '?t=' + Date.now();
          avatar.innerHTML = `<div class="cx-avatar"><div class="rounded-full w-12 h-12"><img id="contato_foto_img" src="${cacheBust}" alt="Foto"></div></div>`;
          msg.textContent = 'Foto atualizada!';
          msg.className = 'text-xs text-success ml-1';
          // Atualiza a listagem de contatos para refletir a nova foto
          const clienteId = document.getElementById('contato_cliente_id').value;
          if (clienteId) carregarContatosAba(clienteId);
        } else {
          msg.textContent = (data && data.error) ? data.error : 'Erro ao enviar foto';
          msg.className = 'text-xs text-error ml-1';
        }
        label.textContent = 'Alterar foto';
      })
      .catch(() => {
        msg.textContent = 'Erro ao enviar foto';
        msg.className = 'text-xs text-error ml-1';
        label.textContent = 'Alterar foto';
      })
      .finally(() => { novoInput.value = ''; });
  });
}

// Função para abrir modal de editar contato
async function abrirModalEditarContato(contatoId) {
  try {
    // Buscar dados do contato
    const response = await fetch(`/api/contato/${contatoId}`);
    if (!response.ok) throw new Error('Erro ao buscar dados do contato');

    const contato = await response.json();

    console.log('Dados do contato:', contato); // Debug

    // Preencher formulário
    document.getElementById('contato_id').value = contato.id_contato_cliente;
    document.getElementById('contato_cliente_id').value = contato.pk_id_tbl_cliente;
    document.getElementById('contato_nome_completo').value = contato.nome_completo;
    document.getElementById('contato_email').value = contato.email;
    document.getElementById('contato_telefone').value = formatarTelefone(contato.telefone || '');
    document.getElementById('contato_telefone_secundario').value = formatarTelefone(contato.telefone_secundario || '');
    if (document.getElementById('contato_wasender_api_key')) {
      document.getElementById('contato_wasender_api_key').value = '';
      document.getElementById('contato_wasender_api_key').placeholder = contato.wasender_api_key_mask ? 'Preencha para alterar' : 'Informe para criar/alterar';
      document.getElementById('contato_wasender_session_id').value = contato.wasender_session_id || '';
      document.getElementById('contato_wasender_ativo').checked = !!contato.wasender_ativo;
      document.getElementById('contato_wasender_api_key_mask').textContent = contato.wasender_api_key_mask ? `Chave atual: ${contato.wasender_api_key_mask}` : 'Sem chave cadastrada';
    }
    document.getElementById('contato_cohorts').value = contato.cohorts || 1;
    document.getElementById('contato_user_type').value = contato.user_type || 'client';

    // Mostrar campo telefone em edição
    document.getElementById('contato_telefone_container').classList.remove('hidden');
    document.getElementById('contato_telefone_secundario_container').classList.remove('hidden');
    // Ajustar largura dos campos para acomodar o telefone
    document.getElementById('contato_nome_container').classList.remove('col-span-6');
    document.getElementById('contato_nome_container').classList.add('col-span-4');
    document.getElementById('contato_email_container').classList.remove('col-span-6');
    document.getElementById('contato_email_container').classList.add('col-span-4');

    // Setor e cargo
    const setorId = contato.pk_id_tbl_setor;
    const cargoSelect = document.getElementById('contato_cargo');

    if (setorId) {
      document.getElementById('contato_setor').value = setorId;
      // Carregar cargos do setor e depois selecionar o cargo
      await carregarCargosPorSetor(setorId);
      document.getElementById('contato_cargo').value = contato.pk_id_tbl_cargo || '';
    } else {
      // Se não tem setor, resetar para "Selecione"
      document.getElementById('contato_setor').value = '';
      cargoSelect.innerHTML = '<option value="">Selecione o setor primeiro</option>';
    }

    // Atualizar título e botão
    document.getElementById('contato_modal_title').textContent = 'Editar contato';
    document.getElementById('contato_btn_text').textContent = 'Atualizar Contato';

    // Configurar foto do contato (preview + upload)
    configurarFotoContato(contato);

    // Abrir modal
    modal_contato.showModal();

  } catch (error) {
    console.error('Erro ao carregar contato:', error);
    showToast('Erro ao carregar dados do contato!', 'error');
  }
}

// Função para carregar cargos por setor
async function carregarCargosPorSetor(setorId) {
  const cargoSelect = document.getElementById('contato_cargo');

  if (!setorId) {
    cargoSelect.innerHTML = '<option value="">Selecione primeiro o setor</option>';
    return;
  }

  try {
    const response = await fetch(`/api/setor/${setorId}/cargos`);
    if (!response.ok) throw new Error('Erro ao buscar cargos');

    const cargos = await response.json();

    cargoSelect.innerHTML = '<option value="">Selecione o cargo</option>';
    cargos.forEach(cargo => {
      const option = document.createElement('option');
      option.value = cargo.id_cargo_contato;
      option.textContent = cargo.descricao;
      cargoSelect.appendChild(option);
    });

  } catch (error) {
    console.error('Erro ao carregar cargos:', error);
    cargoSelect.innerHTML = '<option value="">Erro ao carregar cargos</option>';
  }
}

// Função para formatar telefone
function formatarTelefone(valor) {
  // Remove tudo que não é dígito
  const digits = valor.replace(/\D/g, '');

  if (digits.length === 0) return '';

  // Aceita formato internacional BR usado no WhatsApp: +55 (DD) 99999-9999
  if (digits.startsWith('55') && digits.length > 11) {
    const limited = digits.slice(0, 13);
    const ddd = limited.slice(2, 4);
    const numero = limited.slice(4);
    if (numero.length <= 4) {
      return '+55 (' + ddd + ') ' + numero;
    } else if (numero.length <= 8) {
      return '+55 (' + ddd + ') ' + numero.slice(0, 4) + '-' + numero.slice(4);
    }
    return '+55 (' + ddd + ') ' + numero.slice(0, 5) + '-' + numero.slice(5);
  }

  // Limita a 11 dígitos
  const limited = digits.slice(0, 11);

  // Formatar conforme quantidade de dígitos
  if (limited.length <= 2) {
    return '(' + limited;
  } else if (limited.length <= 6) {
    // Telefone fixo parcial: (XX) XXXX
    return '(' + limited.slice(0, 2) + ') ' + limited.slice(2);
  } else if (limited.length <= 10) {
    // Telefone fixo: (XX) XXXX-XXXX
    return '(' + limited.slice(0, 2) + ') ' + limited.slice(2, 6) + '-' + limited.slice(6);
  } else {
    // Celular: (XX) XXXXX-XXXX
    return '(' + limited.slice(0, 2) + ') ' + limited.slice(2, 7) + '-' + limited.slice(7);
  }
}

// Handler para submit do formulário de contato
document.addEventListener('DOMContentLoaded', function() {
  const formContato = document.getElementById('form_contato');

  // Máscara de telefone para contato
  const telefoneInput = document.getElementById('contato_telefone');
  const telefoneSecundarioInput = document.getElementById('contato_telefone_secundario');
  [telefoneInput, telefoneSecundarioInput].filter(Boolean).forEach(function(inputTel) {
    inputTel.addEventListener('input', function(e) {
      const formatted = formatarTelefone(e.target.value);

      // Só atualiza se o valor mudou
      if (e.target.value !== formatted) {
        // Guardar posição do cursor
        const cursorPos = e.target.selectionStart;
        const oldLen = e.target.value.length;

        e.target.value = formatted;

        // Ajustar posição do cursor
        const newLen = formatted.length;
        const diff = newLen - oldLen;
        const newPos = Math.max(0, Math.min(cursorPos + diff, newLen));
        e.target.setSelectionRange(newPos, newPos);
      }
    });

    // Formatar ao colar
    inputTel.addEventListener('paste', function(e) {
      e.preventDefault();
      const pastedText = (e.clipboardData || window.clipboardData).getData('text');
      e.target.value = formatarTelefone(pastedText);
    });
  });

  if (formContato) {
    formContato.addEventListener('submit', async function(e) {
      e.preventDefault();

      const contatoId = document.getElementById('contato_id').value;
      const clienteId = document.getElementById('contato_cliente_id').value;
      const senha = document.getElementById('contato_senha').value;

      // Preparar dados
      const formData = new FormData(formContato);
      const setorValue = formData.get('pk_id_aux_setor');
      const cargoValue = formData.get('pk_id_tbl_cargo');
      const data = {
        nome_completo: (formData.get('nome_completo') || '').trim(),
        email: (formData.get('email') || '').trim(),
        telefone: (formData.get('telefone') || '').trim(),
        telefone_secundario: (formData.get('telefone_secundario') || '').trim(),
        pk_id_aux_setor: setorValue ? parseInt(setorValue, 10) : null,
        pk_id_tbl_cargo: cargoValue ? parseInt(cargoValue, 10) : null,
        cohorts: 1,  // Valor fixo
        user_type: formData.get('user_type')
      };

      if (document.getElementById('contato_wasender_api_key')) {
        data.wasender_api_key = formData.get('wasender_api_key') || '';
        data.wasender_session_id = formData.get('wasender_session_id') || '';
        data.wasender_ativo = document.getElementById('contato_wasender_ativo').checked;
      }

      // Adicionar senha apenas se preenchida
      if (senha) {
        if (contatoId) {
          data.nova_senha = senha;
        } else {
          data.senha = senha;
        }
      }

      try {
        let response;
        if (contatoId) {
          // Editar contato existente
          response = await fetch(`/api/contato/${contatoId}/editar`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
          });
        } else {
          // Criar novo contato
          response = await fetch(`/api/cliente/${clienteId}/criar-contato`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
          });
        }

        const result = await response.json();

        if (result.success) {
          showToast(result.message, 'success');
          modal_contato.close();

          // Recarregar lista de contatos se estiver na aba de contatos
          if (document.getElementById('contatos_aba_content').style.display !== 'none') {
            await carregarContatosAba(clienteId);
          }
        } else {
          showToast(result.message || 'Erro ao salvar contato!', 'error');
        }

      } catch (error) {
        console.error('Erro ao salvar contato:', error);
        showToast('Erro ao salvar contato!', 'error');
      }
    });
  }
});

// Função para alternar status do contato
async function toggleContatoStatus(contatoId, clienteId, badgeElement, statusAtual) {
  try {
    const response = await fetch(`/api/contato/${contatoId}/toggle-status`, {
      method: 'POST'
    });

    const result = await response.json();

    if (result.success) {
      const novoStatus = !statusAtual;

      badgeElement.textContent = novoStatus ? 'Ativo' : 'Inativo';
      badgeElement.className = `cx-badge ${novoStatus ? 'cx-badge-success' : 'cx-badge-danger'} cliente-contato-status`;
      badgeElement.removeAttribute('style');
      badgeElement.setAttribute('onclick', `toggleContatoStatus(${contatoId}, ${clienteId}, this, ${novoStatus})`);
    } else {
      showToast(result.message || 'Erro ao alterar status!', 'error');
    }

  } catch (error) {
    console.error('Erro ao alterar status:', error);
    showToast('Erro ao alterar status do contato!', 'error');
  }
}

// Função para excluir cliente
async function excluirCliente() {
  const clienteId = document.getElementById('cliente_id').value;
  if (!clienteId) return;

  const confirmado = await confirmarAcaoCliente({
    title: 'Excluir cliente',
    message: 'Tem certeza que deseja excluir este cliente?',
    detail: 'Esta ação é permanente e não poderá ser desfeita.',
    confirmText: 'Excluir cliente',
    theme: 'danger'
  });
  if (!confirmado) return;

  try {
    const response = await fetch(`/api/cliente/${clienteId}/excluir`, {
      method: 'DELETE'
    });

    const result = await response.json();

    if (result.success) {
      showToast(result.message, 'success');
      modal_cliente.close();
      window.location.reload();
    } else {
      showToast(result.message || 'Erro ao excluir cliente!', 'error');
    }

  } catch (error) {
    console.error('Erro ao excluir cliente:', error);
    showToast('Erro ao excluir cliente!', 'error');
  }
}

// Função para deletar contato
async function deletarContato(contatoId, clienteId, nomeContato) {
  const confirmado = await confirmarAcaoCliente({
    title: 'Excluir contato',
    message: `Deseja excluir o contato <strong>${escapeHtml(nomeContato)}</strong>?`,
    detail: 'Esta ação não poderá ser desfeita.',
    confirmText: 'Excluir contato',
    theme: 'danger'
  });
  if (!confirmado) return;

  try {
    const response = await fetch(`/api/contato/${contatoId}/deletar`, {
      method: 'DELETE'
    });

    const result = await response.json();

    if (result.success) {
      showToast(result.message, 'success');
      await carregarContatosAba(clienteId);
    } else if (result.has_vinculos) {
      const inativar = await confirmarAcaoCliente({
        title: 'Contato com vínculos',
        message: escapeHtml(result.message),
        detail: 'O contato não pode ser excluído, mas pode ser inativado.',
        confirmText: 'Inativar contato',
        theme: 'warning'
      });
      if (inativar) {
        const resp = await fetch(`/api/contato/${contatoId}/toggle-status`, { method: 'POST' });
        const res = await resp.json();
        if (res.success) {
          showToast('Contato inativado com sucesso!', 'success');
          await carregarContatosAba(clienteId);
        } else {
          showToast(res.message || 'Erro ao inativar contato!', 'error');
        }
      }
    } else {
      showToast(result.message || 'Erro ao deletar contato!', 'error');
    }

  } catch (error) {
    console.error('Erro ao deletar contato:', error);
    showToast('Erro ao deletar contato!', 'error');
  }
}

// Abrir modal automaticamente via URL params (?open=&tab=)
document.addEventListener('DOMContentLoaded', function() {
  const urlParams = new URLSearchParams(window.location.search);
  const clienteId = urlParams.get('open');
  const tab = urlParams.get('tab');

  if (!clienteId) return;

  const id = parseInt(clienteId, 10);
  const openPromise = tab === 'detalhes'
    ? abrirModalDetalhes(id)
    : abrirModalEditar(id);

  openPromise.then(() => {
    if (tab && tab !== 'editar' && tab !== 'detalhes') {
      trocarAba(tab);
    }
  });
});

// ==================== FUNÇÕES DE INVITES ====================

function contatoInviteBtnHtml(c) {
  const emailEsc = (c.email || '').replace(/'/g, "\\'");
  const nomeEsc = (c.nome_completo || '').replace(/'/g, "\\'");
  if (c.email && c.status) {
    return `<button type="button" class="cx-btn cx-btn-icon cx-btn-ghost cx-btn-xs" title="Enviar convite" onclick="event.stopPropagation();enviarConviteContato(${c.id_contato_cliente}, '${emailEsc}', '${nomeEsc}')"><i class="fas fa-paper-plane text-emerald-600" aria-hidden="true"></i></button>`;
  }
  const title = !c.email ? 'Sem email cadastrado' : 'Contato inativo';
  return `<button type="button" class="cx-btn cx-btn-icon cx-btn-ghost cx-btn-xs" disabled title="${title}"><i class="fas fa-paper-plane text-slate-300" aria-hidden="true"></i></button>`;
}

// Função para formatar o badge de status do convite
function getInviteStatusBadge(inviteStatus, inviteExpiresAt) {
  // Se não há convite
  if (!inviteStatus) {
    return '<span class="cx-badge" style="background-color: #e5e7eb; color: #6b7280; border-color: #e5e7eb;">Sem convite</span>';
  }

  // Verificar se o convite expirou
  const isExpired = inviteExpiresAt ? new Date(inviteExpiresAt) < new Date() : false;

  // Status aceito
  if (inviteStatus === 'accepted') {
    return '<span class="cx-badge" style="background-color: #10b981; color: white; border-color: #10b981;">Aceito</span>';
  }

  // Status pendente mas expirado
  if (inviteStatus === 'pending' && isExpired) {
    return '<span class="cx-badge" style="background-color: #ef4444; color: white; border-color: #ef4444;">Expirado</span>';
  }

  // Status pendente não expirado
  if (inviteStatus === 'pending') {
    return '<span class="cx-badge" style="background-color: #f59e0b; color: white; border-color: #f59e0b;">Pendente</span>';
  }

  // Status cancelado
  if (inviteStatus === 'cancelled') {
    return '<span class="cx-badge" style="background-color: #9ca3af; color: white; border-color: #9ca3af;">Cancelado</span>';
  }

  // Fallback para outros status
  return '<span class="cx-badge" style="background-color: #e5e7eb; color: #6b7280; border-color: #e5e7eb;">—</span>';
}

async function enviarConviteContato(contatoId, email, nomeContato) {
  if (!email || !String(email).trim()) {
    showToast('Nenhum e-mail cadastrado para este contato.', 'error');
    return;
  }
  const emailTrim = email.trim();
  if (!validateEmail(emailTrim)) {
    showToast('Este endereço de e-mail não é válido. Corrija o cadastro do contato antes de enviar.', 'warning');
    return;
  }
  const confirmado = await confirmarAcaoCliente({
    title: 'Enviar convite',
    message: `Enviar convite para <strong>${escapeHtml(nomeContato)}</strong>?`,
    detail: escapeHtml(emailTrim),
    confirmText: 'Enviar convite',
    theme: 'primary'
  });
  if (!confirmado) return;

  const clienteId = document.getElementById('cliente_id').value;

  if (!clienteId) {
    showToast('Erro: Cliente não identificado.', 'error');
    return;
  }

  try {
    const response = await fetch(`/api/cliente/${clienteId}/invites`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: emailTrim, role: 'member', contato_id: contatoId })
    });

    const result = await response.json();

    if (result.success) {
      showToast(result.message || `Convite enviado para ${nomeContato}!`, 'success');
      await carregarContatosAba(clienteId);
      const row = document.querySelector(`[data-contato-id="${contatoId}"]`);
      if (row) {
        if (window.scrollIntoViewSuave) {
          window.scrollIntoViewSuave(row, { block: 'center' });
        } else {
          row.scrollIntoView({ behavior: window.getScrollBehavior ? window.getScrollBehavior() : 'smooth', block: 'center' });
        }
        row.style.transition = 'background-color 0.3s ease';
        row.style.backgroundColor = '#d1fae5';
        setTimeout(() => { row.style.backgroundColor = ''; }, 3000);
      }
    } else {
      showToast(result.message || 'Erro ao enviar convite!', 'error');
    }
  } catch (error) {
    console.error('Erro ao enviar convite:', error);
    showToast('Erro ao enviar convite!', 'error');
  }
}

function validateEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}
