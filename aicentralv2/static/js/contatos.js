/**
 * Contatos Page Scripts
 */

document.addEventListener('DOMContentLoaded', function() {
    console.log('=== CONTATOS PAGE LOADED ===');
    console.log('URL:', window.location.href);
    
    // Elementos
    const searchInput = document.getElementById('searchInput');
    const table = document.getElementById('contatosTable');
    const noResults = document.getElementById('noResults');
    const searchResults = document.getElementById('searchResults');
    
    if (searchInput && table) {
        // Contar contatos total
        const allRows = table.querySelectorAll('tbody tr');
        const totalContatos = allRows.length;
        console.log('Total de contatos:', totalContatos);
        
        // Pesquisa em tempo real
        searchInput.addEventListener('input', function() {
            const searchTerm = this.value.toLowerCase().trim();
            let visibleCount = 0;
            
            allRows.forEach(row => {
                const nomeCompleto = row.cells[0].textContent.toLowerCase();
                
                // Buscar por nome completo
                if (nomeCompleto.includes(searchTerm)) {
                    row.style.display = '';
                    visibleCount++;
                } else {
                    row.style.display = 'none';
                }
            });
            
            // Atualizar contador de resultados
            if (searchTerm) {
                searchResults.textContent = `${visibleCount} de ${totalContatos}`;
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
    }
    
    // Contar ativos/inativos
    const ativos = document.querySelectorAll('.badge-active').length;
    const inativos = document.querySelectorAll('.badge-inactive').length;
    console.log('Ativos:', ativos, '| Inativos:', inativos);
    
    // Adicionar confirmação para deletar
    const deleteForms = document.querySelectorAll('form[action*="deletar"]');
    deleteForms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const nomeContato = this.closest('tr').querySelector('td strong').textContent;
            
            if (!confirm(`Tem certeza que deseja deletar o contato:\n${nomeContato}?\n\nEsta ação não pode ser desfeita.`)) {
                e.preventDefault();
            } else {
                console.log('Deletando contato:', nomeContato);
            }
        });
    });
    
    // Adicionar confirmação para toggle status
    const toggleForms = document.querySelectorAll('form[action*="toggle-status"]');
    toggleForms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const badge = this.closest('tr').querySelector('.badge');
            const isActive = badge.classList.contains('badge-active');
            const action = isActive ? 'desativar' : 'ativar';
            
            if (!confirm(`Tem certeza que deseja ${action} este contato?`)) {
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
    const table = document.getElementById('contatosTable');
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

console.log('Contatos.js loaded successfully');