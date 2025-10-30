// Configuração da tabela
const config = {
    itemsPerPage: 10,
    currentPage: 1,
    sortColumn: null,
    sortDirection: 'asc'
};

// Elementos DOM
const table = document.getElementById('contatosTable');
const tbody = table.querySelector('tbody');
const rows = Array.from(tbody.querySelectorAll('tr'));
const totalItems = rows.length;
const statusFilter = document.getElementById('statusFilter');

// Elementos de paginação
const showingStart = document.getElementById('showing-start');
const showingEnd = document.getElementById('showing-end');
const totalItemsSpan = document.getElementById('total-items');
const prevPageBtn = document.getElementById('prev-page');
const nextPageBtn = document.getElementById('next-page');

// Função para ordenar a tabela
function sortTable(column) {
    const sortButtons = document.querySelectorAll('.sort-btn');
    const currentButton = document.querySelector(`.sort-btn[data-column="${column}"]`);
    
    // Reset outros ícones
    sortButtons.forEach(btn => {
        if (btn !== currentButton) {
            btn.querySelector('i').className = 'fas fa-sort text-gray-400';
        }
    });

    // Atualiza direção da ordenação
    if (config.sortColumn === column) {
        config.sortDirection = config.sortDirection === 'asc' ? 'desc' : 'asc';
    } else {
        config.sortColumn = column;
        config.sortDirection = 'asc';
    }

    // Atualiza ícone
    const icon = currentButton.querySelector('i');
    icon.className = `fas fa-sort-${config.sortDirection === 'asc' ? 'up' : 'down'} text-primary`;

    // Ordena as linhas
    rows.sort((a, b) => {
        let aValue, bValue;

        switch(column) {
            case 'nome':
                aValue = a.querySelector('td:first-child .font-medium').textContent.trim();
                bValue = b.querySelector('td:first-child .font-medium').textContent.trim();
                break;
            case 'email':
                aValue = a.querySelector('td:nth-child(2)').textContent.trim();
                bValue = b.querySelector('td:nth-child(2)').textContent.trim();
                break;
            case 'cliente':
                aValue = a.querySelector('td:nth-child(3)').textContent.trim();
                bValue = b.querySelector('td:nth-child(3)').textContent.trim();
                break;
            default:
                return 0;
        }

        if (config.sortDirection === 'asc') {
            return aValue.localeCompare(bValue, 'pt-BR');
        } else {
            return bValue.localeCompare(aValue, 'pt-BR');
        }
    });

    updateTable();
}

// Função para atualizar a exibição da tabela
function updateTable() {
    const start = (config.currentPage - 1) * config.itemsPerPage;
    const end = Math.min(start + config.itemsPerPage, totalItems);
    
    // Limpa a tabela
    tbody.innerHTML = '';
    
    // Adiciona apenas as linhas da página atual
    for (let i = start; i < end; i++) {
        tbody.appendChild(rows[i].cloneNode(true));
    }
    
    // Atualiza informações de paginação
    showingStart.textContent = start + 1;
    showingEnd.textContent = end;
    totalItemsSpan.textContent = totalItems;
    
    // Atualiza estado dos botões de paginação
    prevPageBtn.disabled = config.currentPage === 1;
    nextPageBtn.disabled = end >= totalItems;
    
    // Atualiza classes zebra
    Array.from(tbody.querySelectorAll('tr')).forEach((row, index) => {
        if (index % 2 === 0) {
            row.classList.remove('bg-gray-50/30');
        } else {
            row.classList.add('bg-gray-50/30');
        }
    });

    // Reaplica event listeners
    setupEventListeners();
}

// Configuração de event listeners
function setupEventListeners() {
    // Tooltips para ações
    document.querySelectorAll('[data-tooltip]').forEach(element => {
        element.addEventListener('mouseenter', showTooltip);
        element.addEventListener('mouseleave', hideTooltip);
    });
}

// Busca
const searchInput = document.getElementById('searchInput');
const searchResults = document.getElementById('searchResults');
const noResults = document.getElementById('noResults');

searchInput.addEventListener('input', (e) => {
    const searchTerm = e.target.value.toLowerCase();
    let matchCount = 0;
    config.currentPage = 1; // Reset para primeira página

    const selectedStatus = statusFilter.value;
    
    const filteredRows = rows.filter(row => {
        const nome = row.querySelector('td:first-child .font-medium').textContent.toLowerCase();
        const email = row.querySelector('td:nth-child(2)').textContent.toLowerCase();
        
        // Determina o status baseado no ícone do botão de toggle
        const toggleButton = row.querySelector('button[type="submit"] i');
        const status = toggleButton.classList.contains('fa-ban') ? 'true' : 'false';
        
        const matchesSearch = searchTerm === '' || nome.includes(searchTerm) || email.includes(searchTerm);
        const matchesStatus = selectedStatus === 'todos' || status === selectedStatus;

        const matches = matchesSearch && matchesStatus;
        if (matches) matchCount++;
        return matches;
    });

    // Atualiza contador de resultados
    searchResults.textContent = matchCount > 0 ? `${matchCount} resultado${matchCount > 1 ? 's' : ''}` : 'Nenhum resultado';
    
    // Mostra/esconde mensagem de "Nenhum resultado"
    if (matchCount === 0 && searchTerm !== '') {
        noResults.classList.remove('hidden');
        tbody.innerHTML = '';
    } else {
        noResults.classList.add('hidden');
        
        // Atualiza apenas as linhas filtradas
        tbody.innerHTML = '';
        const end = Math.min(config.itemsPerPage, filteredRows.length);
        for (let i = 0; i < end; i++) {
            tbody.appendChild(filteredRows[i].cloneNode(true));
        }
        
        // Atualiza paginação
        showingStart.textContent = filteredRows.length > 0 ? '1' : '0';
        showingEnd.textContent = end;
        totalItemsSpan.textContent = filteredRows.length;
        
        // Atualiza estado dos botões de paginação
        prevPageBtn.disabled = true;
        nextPageBtn.disabled = end >= filteredRows.length;
    }
    
    setupEventListeners();
});

// Função para limpar busca
window.clearSearch = function() {
    searchInput.value = '';
    searchResults.textContent = '';
    noResults.classList.add('hidden');
    config.currentPage = 1;
    statusFilter.value = 'todos'; // Reseta também o filtro de status
    updateTable();
};

// Event Listeners para paginação
prevPageBtn.addEventListener('click', () => {
    if (config.currentPage > 1) {
        config.currentPage--;
        updateTable();
    }
});

nextPageBtn.addEventListener('click', () => {
    const maxPage = Math.ceil(totalItems / config.itemsPerPage);
    if (config.currentPage < maxPage) {
        config.currentPage++;
        updateTable();
    }
});

// Event Listeners para ordenação
document.querySelectorAll('.sort-btn').forEach(button => {
    button.addEventListener('click', () => {
        sortTable(button.dataset.column);
    });
});

// Event listener para o filtro de status
statusFilter.addEventListener('change', () => {
    searchInput.dispatchEvent(new Event('input'));
});

// Inicializa a contagem inicial
function initializeCounters() {
    const totalContatos = rows.length;
    let totalAtivos = 0;
    
    rows.forEach(row => {
        const toggleButton = row.querySelector('button[type="submit"] i');
        if (toggleButton.classList.contains('fa-ban')) {
            totalAtivos++;
        }
    });

    // Atualiza os contadores na interface
    totalItemsSpan.textContent = totalContatos;
    showingStart.textContent = totalContatos > 0 ? '1' : '0';
    showingEnd.textContent = Math.min(config.itemsPerPage, totalContatos);
}

// Inicialização
document.addEventListener('DOMContentLoaded', () => {
    initializeCounters();
    setupEventListeners();
    updateTable();
});
