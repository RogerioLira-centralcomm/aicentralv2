document.addEventListener('DOMContentLoaded', function() {
    // Elementos DOM
    const searchInput = document.getElementById('searchInput');
    const statusFilter = document.getElementById('statusFilter');
    const table = document.getElementById('clientesTable');
    const tbody = table.querySelector('tbody');
    const noResults = document.getElementById('noResults');
    const rows = Array.from(tbody.querySelectorAll('tr'));
    const vendedorFilter = document.getElementById('vendedorFilter');

    // Função para filtrar a tabela
    function filterTable() {
        const searchTerm = searchInput.value.toLowerCase();
        const statusValue = statusFilter.value;
        let visibleCount = 0;

        rows.forEach(row => {
            // Encontrar células com dados
            const cells = row.querySelectorAll('td');
            const razaoSocial = cells[0].textContent.toLowerCase();
            const nomeFantasia = cells[1].textContent.toLowerCase();
            
            // Encontrar o ícone de status no botão de ações
            const actionsCell = cells[cells.length - 1];
            const statusForm = actionsCell.querySelector('form');
            const statusButton = statusForm ? statusForm.querySelector('button') : null;
            const statusIcon = statusButton ? statusButton.querySelector('i') : null;
            
            // Determinar se está ativo baseado no ícone de banimento (fa-ban significa inativo)
            const isAtivo = !(statusIcon && statusIcon.classList.contains('fa-ban'));

            // Verificar se atende aos critérios de filtro
            const matchesSearch = razaoSocial.includes(searchTerm) || 
                                nomeFantasia.includes(searchTerm);
            
            const matchesStatus = statusValue === 'todos' || 
                                (statusValue === 'true' && !isAtivo) || 
                                (statusValue === 'false' && isAtivo);

            // Mostrar/esconder linha
            if (matchesSearch && matchesStatus) {
                row.style.display = '';
                visibleCount++;
            } else {
                row.style.display = 'none';
            }
        });

        // Mostrar/esconder mensagem de "nenhum resultado" (sem exibir contagem)
        if (noResults) {
            if (visibleCount === 0) {
                tbody.style.display = 'none';
                noResults.style.display = '';
            } else {
                tbody.style.display = '';
                noResults.style.display = 'none';
            }
        }
    }

    // Event Listeners
    if (searchInput) {
        searchInput.addEventListener('input', filterTable);
        searchInput.setAttribute('placeholder', 'R_Social, Nome');
    }
    if (statusFilter) {
        statusFilter.addEventListener('change', filterTable);
    }
    if (vendedorFilter) {
        vendedorFilter.addEventListener('change', function() {
            const url = new URL(window.location.href);
            const val = vendedorFilter.value;
            if (val) {
                url.searchParams.set('vendas_central_comm', val);
            } else {
                url.searchParams.delete('vendas_central_comm');
            }
            window.location.href = url.toString();
        });
    }

    // Função para limpar pesquisa
    window.clearSearch = function() {
        if (searchInput) searchInput.value = '';
        if (statusFilter) statusFilter.value = 'todos';
        filterTable();
    };

    // Inicialização
    filterTable();
});