// ============================================
// VARIÁVEIS GLOBAIS
// ============================================
let allRows = [];
let currentPage = 1;
const rowsPerPage = 10;
let statusFilter = null;
let searchInput = null;

// ============================================
// INICIALIZAÇÃO
// ============================================
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Iniciando sistema de contatos...');
    
    statusFilter = document.getElementById('statusFilter');
    searchInput = document.getElementById('searchInput');
    const tableBody = document.querySelector('#contatosTable tbody');
    
    if (tableBody) {
        allRows = Array.from(tableBody.querySelectorAll('tr'));
        console.log('📊 Total de contatos:', allRows.length);
    }
    
    setupEventListeners();
    updatePagination();
    updateDebugInfo(); // Debug info
});

// ============================================
// EVENT LISTENERS
// ============================================
function setupEventListeners() {
    console.log('🎧 Configurando event listeners...');
    
    if (statusFilter) {
        statusFilter.addEventListener('change', function() {
            console.log('🔄 Status mudou para:', this.value);
            handleFilterChange();
        });
    }
    
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            console.log('🔍 Busca mudou para:', this.value);
            handleFilterChange();
        });
    }
}

function handleFilterChange() {
    currentPage = 1;
    updatePagination();
    updateDebugInfo();
}

// ============================================
// FILTROS
// ============================================
function getFilteredRows() {
    const searchTerm = searchInput ? searchInput.value.toLowerCase().trim() : '';
    const statusValue = statusFilter ? statusFilter.value : 'todos';
    
    console.log('🔍 Aplicando filtros:', { 
        searchTerm, 
        statusValue,
        totalRows: allRows.length 
    });
    
    const filtered = allRows.filter(row => {
        const cells = row.querySelectorAll('td');
        if (cells.length < 4) return false;
        
        const nome = cells[0].textContent.trim().toLowerCase();
        const email = cells[1].textContent.trim().toLowerCase();
        
        // Detecta status pela classe do botão e ícone
        const actionsCell = cells[cells.length - 1];
        const statusButton = actionsCell.querySelector('button[type="submit"]');
        const statusIcon = statusButton ? statusButton.querySelector('i') : null;
        
        // Determina o status pelo ícone (fa-ban = inativo, fa-check = ativo)
        // true = ativo (fa-check), false = inativo (fa-ban)
        const isAtivo = statusIcon && statusIcon.classList.contains('fa-check');
        
        console.log('Status detectado:', { 
            nome: cells[0].textContent.trim(),
            isAtivo: isAtivo,
            statusValue: statusValue,
            buttonClasses: statusButton ? statusButton.className : 'no-button',
            iconClasses: statusIcon ? statusIcon.className : 'no-icon'
        });
        
        // Filtro de busca
        const matchesSearch = !searchTerm || 
                            nome.includes(searchTerm) || 
                            email.includes(searchTerm);
        
        // Filtro de status (true = mostrar ativos, false = mostrar inativos)
        const matchesStatus = statusValue === 'todos' || 
                            (statusValue === 'true' && isAtivo) || 
                            (statusValue === 'false' && !isAtivo);
                            
        console.log(`Row "${nome}": status=${isAtivo}, matches=${matchesStatus}`);
        
        console.log('Resultado do filtro:', {
            searchTerm,
            statusValue,
            isAtivo,
            matchesSearch,
            matchesStatus
        });
        
        return matchesSearch && matchesStatus;
    });
    
    console.log('✅ Resultados filtrados:', filtered.length);
    return filtered;
}

// ============================================
// PAGINAÇÃO
// ============================================
function updatePagination() {
    const filteredRows = getFilteredRows();
    const totalPages = Math.ceil(filteredRows.length / rowsPerPage);
    
    if (currentPage > totalPages) currentPage = totalPages;
    if (currentPage < 1) currentPage = 1;
    
    const start = (currentPage - 1) * rowsPerPage;
    const end = start + rowsPerPage;
    
    allRows.forEach(row => row.style.display = 'none');
    filteredRows.slice(start, end).forEach(row => row.style.display = '');
    
    updatePaginationControls(filteredRows.length, totalPages);
    updateCounter(filteredRows.length);
}

function updatePaginationControls(totalRows, totalPages) {
    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');
    const pageInfo = document.getElementById('pageInfo');
    
    if (prevBtn) prevBtn.disabled = currentPage === 1;
    if (nextBtn) nextBtn.disabled = currentPage >= totalPages;
    
    if (pageInfo) {
        const start = totalRows === 0 ? 0 : (currentPage - 1) * rowsPerPage + 1;
        const end = Math.min(currentPage * rowsPerPage, totalRows);
        pageInfo.textContent = `${start}-${end} de ${totalRows}`;
    }
}

function updateCounter(count) {
    const counter = document.getElementById('contatosCounter');
    if (counter) {
        counter.textContent = count;
    }
}

function prevPage() {
    if (currentPage > 1) {
        currentPage--;
        updatePagination();
        updateDebugInfo();
    }
}

function nextPage() {
    const filteredRows = getFilteredRows();
    const totalPages = Math.ceil(filteredRows.length / rowsPerPage);
    if (currentPage < totalPages) {
        currentPage++;
        updatePagination();
        updateDebugInfo();
    }
}

// ============================================
// DEBUG INFO (remover em produção)
// ============================================
function updateDebugInfo() {
    const debugTotal = document.getElementById('debugTotal');
    const debugFiltered = document.getElementById('debugFiltered');
    const debugStatus = document.getElementById('debugStatus');
    const debugSearch = document.getElementById('debugSearch');
    const debugPage = document.getElementById('debugPage');
    
    if (debugTotal) debugTotal.textContent = allRows.length;
    if (debugFiltered) debugFiltered.textContent = getFilteredRows().length;
    if (debugStatus) debugStatus.textContent = statusFilter?.value || 'N/A';
    if (debugSearch) debugSearch.textContent = searchInput?.value || 'vazio';
    if (debugPage) debugPage.textContent = currentPage;
}

// ============================================
// MODAIS
// ============================================
const importBtn = document.getElementById('importBtn');
const importModal = document.getElementById('importModal');
const closeImportModal = document.getElementById('closeImportModal');
const cancelImport = document.getElementById('cancelImport');

if (importBtn && importModal) {
    importBtn.addEventListener('click', () => importModal.classList.remove('hidden'));
}
if (closeImportModal && importModal) {
    closeImportModal.addEventListener('click', () => importModal.classList.add('hidden'));
}
if (cancelImport && importModal) {
    cancelImport.addEventListener('click', () => importModal.classList.add('hidden'));
}

function openEditModal(contatoId) {
    console.log('📝 Abrindo modal de edição:', contatoId);
}

function confirmDelete(contatoId) {
    if (confirm('Tem certeza que deseja excluir este contato?')) {
        document.getElementById('deleteForm' + contatoId).submit();
    }
}

// ============================================
// TOGGLE STATUS (AJAX)
// ============================================
function toggleStatus(contatoId) {
    const form = document.getElementById('toggleForm' + contatoId);
    if (!form) return;
    
    const formData = new FormData(form);
    
    fetch(form.action, {
        method: 'POST',
        body: formData,
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            const button = form.querySelector('button[type="submit"]');
            const icon = button.querySelector('i');
            
            if (data.status === true) {
                button.className = 'px-3 py-1 bg-orange-50 hover:bg-orange-100 text-orange-600 rounded-md transition-colors duration-200';
                icon.className = 'fas fa-toggle-on';
                button.setAttribute('title', 'Desativar contato');
            } else {
                button.className = 'px-3 py-1 bg-green-50 hover:bg-green-100 text-green-600 rounded-md transition-colors duration-200';
                icon.className = 'fas fa-toggle-off';
                button.setAttribute('title', 'Ativar contato');
            }
            
            updatePagination();
            updateDebugInfo();
        } else {
            alert(data.error || 'Erro ao alterar status');
        }
    })
    .catch(error => {
        console.error('Erro:', error);
        alert('Erro ao alterar status');
    });
    
    return false;
}

// ============================================
// IMPORTAR CONTATOS
// ============================================
function handleImportSubmit(event) {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);
    const submitBtn = form.querySelector('button[type="submit"]');
    
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Importando...';
    
    fetch(form.action, {
        method: 'POST',
        body: formData,
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert(data.message || 'Contatos importados com sucesso!');
            location.reload();
        } else {
            alert(data.error || 'Erro ao importar contatos');
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="fas fa-file-import mr-2"></i>Importar';
        }
    })
    .catch(error => {
        console.error('Erro:', error);
        alert('Erro ao importar contatos');
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<i class="fas fa-file-import mr-2"></i>Importar';
    });
}