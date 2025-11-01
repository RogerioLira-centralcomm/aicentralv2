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
    if (cargoSelect) {
        cargoOptions = Array.from(cargoSelect.options);

        // Event listener para mudança no select de setor
        if (setorSelect) {
            setorSelect.addEventListener('change', function() {
                const setorId = this.value;
                filtrarCargos(setorId);
                
                // Reseta a seleção do cargo quando o setor muda
                cargoSelect.value = '';
            });

            // Inicialização: se já houver um setor selecionado
            if (setorSelect.value) {
                filtrarCargos(setorSelect.value);
            }
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

    // Remove todas as opções atuais exceto a primeira (placeholder)
    while (cargoSelect.options.length > 1) {
        cargoSelect.remove(1);
    }

    // Se nenhum setor selecionado, desabilita o select de cargo
    if (!setorId) {
        cargoSelect.disabled = true;
        return;
    }

    // Filtra e adiciona apenas os cargos do setor selecionado
    const cargosFiltrados = cargoOptions.filter(option => {
        if (!option.dataset.setorId) return true; // mantém opções sem setor (como placeholder)
        
        // Converte ambos para número para garantir a comparação correta
        const optionSetorId = parseInt(option.dataset.setorId);
        const selectedSetorId = parseInt(setorId);
        
        console.log('Comparando:', {
            optionSetorId,
            selectedSetorId,
            raw: {
                option: option.dataset.setorId,
                selected: setorId
            }
        });
        
        return optionSetorId === selectedSetorId;
    });

    cargosFiltrados.forEach(option => {
        if (option.value) { // Não duplica a opção placeholder
            cargoSelect.add(option.cloneNode(true));
        }
    });

    // Habilita o select de cargo
    cargoSelect.disabled = false;
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