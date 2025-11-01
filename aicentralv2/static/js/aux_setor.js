// Elementos do DOM
const searchInput = document.getElementById('searchInput');
const setoresTableBody = document.getElementById('setoresTableBody');
const setorModal = document.getElementById('setorModal');
const setorForm = document.getElementById('setorForm');
const modalTitle = document.getElementById('modalTitle');

// Cache dos dados originais
let originalData = [];

// Inicialização
document.addEventListener('DOMContentLoaded', () => {
    // Armazena os dados originais da tabela
    originalData = Array.from(setoresTableBody.getElementsByTagName('tr')).map(row => ({
        element: row,
        searchText: row.textContent.toLowerCase()
    }));

    // Configura o listener de busca
    searchInput.addEventListener('input', handleSearch);
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
    modalTitle.textContent = 'Novo Setor';
    setorForm.reset();
    setorForm.querySelector('#setorId').value = '';
    setorModal.classList.remove('hidden');
    setorModal.classList.add('flex');
}

function openEditModal(setor) {
    console.log('Dados do setor recebidos:', setor);
    modalTitle.textContent = 'Editar Setor';
    setorForm.querySelector('#setorId').value = setor.id_aux_setor;
    setorForm.querySelector('#display').value = setor.display;
    setorForm.querySelector('#status').value = setor.status.toString();
    setorModal.classList.remove('hidden');
    setorModal.classList.add('flex');
}

function closeModal() {
    setorModal.classList.add('hidden');
    setorModal.classList.remove('flex');
    setorForm.reset();
}

// Manipulação do formulário
async function handleSubmit(e) {
    e.preventDefault();
    
    const formData = new FormData(setorForm);
    const setorId = formData.get('id_aux_setor');
    const isEdit = setorId !== '';
    
    try {
        const response = await fetch(
            isEdit ? `/setor/${setorId}` : '/setor/create',
            {
                method: isEdit ? 'PUT' : 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    display: formData.get('display'),
                    status: formData.get('status') === 'true'
                })
            }
        );
        
        if (response.ok) {
            window.location.reload();
        } else {
            const data = await response.json();
            alert(data.message || 'Erro ao salvar setor');
        }
    } catch (error) {
        console.error('Erro:', error);
        alert('Erro ao processar a requisição');
    }
}

// Toggle de Status
async function toggleStatus(id, currentStatus) {
    if (!confirm(`Deseja ${currentStatus ? 'desativar' : 'ativar'} este setor?`)) {
        return;
    }
    
    try {
        const response = await fetch(`/setor/${id}/toggle_status`, {
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