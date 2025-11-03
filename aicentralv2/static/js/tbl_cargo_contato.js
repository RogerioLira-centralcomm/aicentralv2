// Elementos do DOM
const searchInput = document.getElementById('searchInput');
const cargosTableBody = document.getElementById('cargosTableBody');
const cargoModal = document.getElementById('cargoModal');
const cargoForm = document.getElementById('cargoForm');
const modalTitle = document.getElementById('modalTitle');
const setorSelect = document.getElementById('setor_select');
const cargoSelect = document.getElementById('cargo_select');

// Cache dos dados originais
let originalData = [];
let cargoOptions = [];
let setorInicial = null; // Guarda o setor inicial
let cargoInicialSelecionado = null; // Guarda o cargo inicialmente selecionado (no modo editar)

// Inicialização
document.addEventListener('DOMContentLoaded', () => {
    // Armazena os dados originais da tabela
    if (cargosTableBody) {
        originalData = Array.from(cargosTableBody.getElementsByTagName('tr')).map(row => ({
            element: row,
            searchText: row.textContent.toLowerCase()
        }));

        // Configura o listener de busca
        searchInput.addEventListener('input', handleSearch);
    }

    // Inicialização do selector de cargos
    if (cargoSelect && setorSelect) {
        // Guarda TODAS as opções originais uma única vez
        cargoOptions = Array.from(cargoSelect.options).map(opt => opt.cloneNode(true));
        
        // Guarda o setor inicial
        setorInicial = setorSelect.value;
        // Guarda o cargo inicialmente selecionado (se houver)
        cargoInicialSelecionado = cargoSelect.value || null;
        
        setorSelect.addEventListener('change', function() {
            const setorAtual = this.value;
            
            // Verifica se houve alteração no setor
            if (setorAtual !== setorInicial) {
                // Limpa o cargo
                cargoSelect.value = '';
                // Atualiza o setor inicial para a próxima comparação
                setorInicial = setorAtual;
                // Zera o cargo inicial para não ser reaplicado após mudança
                cargoInicialSelecionado = null;
            }
            
            // Filtra os cargos do setor atual
            filtrarCargos(setorAtual);
        });
        
        // Inicialização: se já houver um setor selecionado
        if (setorSelect.value) {
            filtrarCargos(setorSelect.value);
        }
    }
});

// Função de busca
function handleSearch(e) {
    const searchTerm = e.target.value.toLowerCase();
    
    originalData.forEach(item => {
        item.element.style.display = 
            item.searchText.includes(searchTerm) ? '' : 'none';
    });
}

// Funções do Modal
function openCreateModal() {
    modalTitle.textContent = 'Novo Cargo';
    cargoForm.reset();
    cargoForm.querySelector('#cargoId').value = '';
    cargoModal.classList.remove('hidden');
    cargoModal.classList.add('flex');
}

function openEditModal(cargo) {
    console.log('Dados do cargo recebidos:', cargo);
    modalTitle.textContent = 'Editar Cargo';
    cargoForm.querySelector('#cargoId').value = cargo.id_cargo_contato;
    cargoForm.querySelector('#descricao').value = cargo.descricao;
    cargoForm.querySelector('#setor').value = cargo.pk_id_aux_setor || '';
    cargoForm.querySelector('#id_centralx').value = cargo.id_centralx || '';
    cargoForm.querySelector('#indice').value = cargo.indice || '';
    cargoForm.querySelector('#status').value = cargo.status.toString();
    cargoModal.classList.remove('hidden');
    cargoModal.classList.add('flex');
}

function closeModal() {
    cargoModal.classList.add('hidden');
    cargoModal.classList.remove('flex');
    cargoForm.reset();
}

// Manipulação do formulário
async function handleSubmit(e) {
    e.preventDefault();
    
    const formData = new FormData(cargoForm);
    const cargoId = formData.get('id_cargo_contato');
    const isEdit = cargoId !== '';
    
    try {
        const response = await fetch(
            isEdit ? `/cargo/${cargoId}` : '/cargo/create',
            {
                method: isEdit ? 'PUT' : 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    descricao: formData.get('descricao'),
                    pk_id_aux_setor: parseInt(formData.get('pk_id_aux_setor')),
                    id_centralx: formData.get('id_centralx') || null,
                    indice: formData.get('indice') ? parseInt(formData.get('indice')) : null,
                    status: formData.get('status') === 'true'
                })
            }
        );
        
        if (response.ok) {
            window.location.reload();
        } else {
            const data = await response.json();
            alert(data.message || 'Erro ao salvar cargo');
        }
    } catch (error) {
        console.error('Erro:', error);
        alert('Erro ao processar a requisição');
    }
}

// Função para filtrar os cargos baseado no setor selecionado
function filtrarCargos(setorId) {
    if (!cargoSelect) return;

    // Sempre começa desabilitado até confirmar que há cargos
    cargoSelect.disabled = true;
    cargoSelect.setAttribute('disabled', 'disabled');

    // Limpa TODAS as opções e adiciona placeholder
    cargoSelect.innerHTML = '';
    const emptyOption = document.createElement('option');
    emptyOption.value = '';
    emptyOption.textContent = 'Selecione um cargo...';
    cargoSelect.appendChild(emptyOption);
    cargoSelect.selectedIndex = 0;

    // Se não tem setor, permanece desabilitado
    if (!setorId) {
        return;
    }

    // Filtra cargos que pertencem ao setor e adiciona
    let cargosAdicionados = 0;
    const setorAlvo = String(setorId).trim();
    let hasPreservedSelection = false;
    cargoOptions.forEach(option => {
        const optVal = option.value != null ? String(option.value) : '';
        const optSetor = option.dataset && option.dataset.setorId != null ? String(option.dataset.setorId).trim() : '';
        if (optVal && optSetor === setorAlvo) {
            cargoSelect.appendChild(option.cloneNode(true));
            cargosAdicionados++;
            // Se for inicialização e o cargo pertence a este setor, preserva seleção
            if (!hasPreservedSelection && cargoInicialSelecionado && String(cargoInicialSelecionado) === optVal) {
                hasPreservedSelection = true;
            }
        }
    });

    // Habilita se houver ao menos um cargo adicionado
    if (cargosAdicionados > 0) {
        cargoSelect.disabled = false;
        cargoSelect.removeAttribute('disabled');
        // Reaplica seleção inicial quando apropriado
        if (hasPreservedSelection) {
            cargoSelect.value = String(cargoInicialSelecionado);
            // Seleção inicial já aplicada, evita reaplicar em próximas mudanças
            cargoInicialSelecionado = null;
        }
    } else {
        cargoSelect.disabled = true;
        cargoSelect.setAttribute('disabled', 'disabled');
    }
}

// Toggle de Status
async function toggleStatus(id, currentStatus) {
    if (!confirm(`Deseja ${currentStatus ? 'desativar' : 'ativar'} este cargo?`)) {
        return;
    }
    
    try {
        const response = await fetch(`/cargo/${id}/toggle_status`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                status: !currentStatus
            })
        });
        
        if (response.ok) {
            window.location.reload();
        } else {
            const data = await response.json();
            alert(data.message || 'Erro ao alterar status');
        }
    } catch (error) {
        console.error('Erro:', error);
        alert('Erro ao processar a requisição');
    }
}