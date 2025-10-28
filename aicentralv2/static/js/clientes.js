/**
 * Clientes Page Scripts
 */

document.addEventListener('DOMContentLoaded', function() {
    console.log('=== CLIENTES PAGE LOADED ===');
    console.log('URL:', window.location.href);
    
    // Elementos
    const searchInput = document.getElementById('searchInput');
    const table = document.getElementById('clientesTable');
    const noResults = document.getElementById('noResults');
    const searchResults = document.getElementById('searchResults');
    
    if (searchInput && table) {
        // Contar clientes total
        const allRows = table.querySelectorAll('tbody tr');
        const totalClientes = allRows.length;
        console.log('Total de clientes:', totalClientes);
        
        // Pesquisa em tempo real
        searchInput.addEventListener('input', function() {
            const searchTerm = this.value.toLowerCase().trim();
            let visibleCount = 0;
            
            allRows.forEach(row => {
                const razaoSocial = row.cells[0].textContent.toLowerCase();
                const nomeFantasia = row.cells[1].textContent.toLowerCase();
                
                // Buscar em razão social OU nome fantasia
                if (razaoSocial.includes(searchTerm) || nomeFantasia.includes(searchTerm)) {
                    row.style.display = '';
                    visibleCount++;
                } else {
                    row.style.display = 'none';
                }
            });
            
            // Atualizar contador de resultados
            if (searchTerm) {
                searchResults.textContent = `${visibleCount} de ${totalClientes}`;
            } else {
                searchResults.textContent = '';
            }
            
            // Mostrar mensagem de "nenhum resultado"
            if (visibleCount === 0 && searchTerm) {
                table.style.display = 'none';
                noResults.style.display = 'block';
            } else {
                table.style.display = 'table';
                noResults.style.display = 'none';
            }
            
            console.log(`Pesquisa: "${searchTerm}" - ${visibleCount} resultados`);
        });
        
        // Limpar pesquisa ao pressionar ESC
        searchInput.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                clearSearch();
            }
        });
        
        // Auto-focus no campo de pesquisa (opcional)
        // searchInput.focus();
    }
    
    // Contar ativos/inativos
    const ativos = document.querySelectorAll('.badge-active').length;
    const inativos = document.querySelectorAll('.badge-inactive').length;
    console.log('Ativos:', ativos, '| Inativos:', inativos);
    
    // Adicionar confirmação para toggle status
    const toggleForms = document.querySelectorAll('form[action*="toggle-status"]');
    toggleForms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const badge = this.closest('tr').querySelector('.badge');
            const isActive = badge.classList.contains('badge-active');
            const action = isActive ? 'desativar' : 'ativar';
            
            if (!confirm(`Tem certeza que deseja ${action} este cliente?`)) {
                e.preventDefault();
            }
        });
    });
});

/**
 * Limpar pesquisa
 */
function clearSearch() {
    const searchInput = document.getElementById('searchInput');
    const table = document.getElementById('clientesTable');
    const noResults = document.getElementById('noResults');
    const searchResults = document.getElementById('searchResults');
    
    if (searchInput) {
        searchInput.value = '';
        searchResults.textContent = '';
        
        // Mostrar todas as linhas
        const allRows = table.querySelectorAll('tbody tr');
        allRows.forEach(row => {
            row.style.display = '';
        });
        
        table.style.display = 'table';
        noResults.style.display = 'none';
        
        searchInput.focus();
        console.log('Pesquisa limpa');
    }
}

console.log('Clientes.js loaded successfully');