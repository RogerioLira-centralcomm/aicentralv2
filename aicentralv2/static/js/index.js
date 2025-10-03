/**
 * JavaScript para Dashboard (Index)
 * Funcionalidades: Filtros, Busca, Alertas
 */

document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Dashboard loaded');

    // Elementos
    const searchInput = document.getElementById('searchInput');
    const filterButtons = document.querySelectorAll('.filter-btn');
    const tableRows = document.querySelectorAll('.users-table tbody tr:not(.no-data)');
    const noResults = document.getElementById('noResults');
    const table = document.querySelector('.users-table');

    // Estado atual
    let currentFilter = 'all';
    let currentSearch = '';

    /**
     * Aplicar filtros e busca
     */
    function applyFilters() {
        let visibleCount = 0;

        tableRows.forEach(row => {
            const status = row.dataset.status;
            const isAdmin = row.dataset.admin === 'true';
            const hasCliente = row.dataset.cliente === 'true';
            const searchText = row.dataset.search || '';

            // Verificar filtro
            let matchFilter = false;

            switch(currentFilter) {
                case 'all':
                    matchFilter = true;
                    break;
                case 'active':
                    matchFilter = status === 'active';
                    break;
                case 'inactive':
                    matchFilter = status === 'inactive';
                    break;
                case 'admin':
                    matchFilter = isAdmin;
                    break;
                case 'cliente':
                    matchFilter = hasCliente;
                    break;
            }

            // Verificar busca
            const matchSearch = currentSearch === '' ||
                              searchText.includes(currentSearch.toLowerCase());

            // Mostrar/ocultar
            if (matchFilter && matchSearch) {
                row.style.display = '';
                visibleCount++;
            } else {
                row.style.display = 'none';
            }
        });

        // Mostrar mensagem de "nenhum resultado"
        if (visibleCount === 0) {
            table.style.display = 'none';
            noResults.style.display = 'block';
        } else {
            table.style.display = 'table';
            noResults.style.display = 'none';
        }
    }

    /**
     * Busca em tempo real
     */
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            currentSearch = this.value;
            applyFilters();
        });

        // Limpar busca com ESC
        searchInput.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                this.value = '';
                currentSearch = '';
                applyFilters();
                this.blur();
            }
        });
    }

    /**
     * Filtros por botões
     */
    filterButtons.forEach(button => {
        button.addEventListener('click', function() {
            // Remover active de todos
            filterButtons.forEach(btn => btn.classList.remove('active'));

            // Adicionar active no clicado
            this.classList.add('active');

            // Atualizar filtro
            currentFilter = this.dataset.filter;

            // Aplicar filtros
            applyFilters();
        });
    });

    /**
     * Auto-remover alertas após 5 segundos
     */
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        // Botão de fechar (se adicionar depois)
        const closeBtn = document.createElement('button');
        closeBtn.className = 'alert-close';
        closeBtn.innerHTML = '×';
        closeBtn.title = 'Fechar';
        closeBtn.onclick = function() {
            removeAlert(alert);
        };
        alert.appendChild(closeBtn);

        // Auto-remover
        setTimeout(() => {
            removeAlert(alert);
        }, 5000);
    });

    /**
     * Remover alerta com animação
     */
    function removeAlert(alert) {
        alert.style.animation = 'slideOutUp 0.5s ease-out forwards';
        setTimeout(() => {
            alert.remove();
        }, 500);
    }

    /**
     * Destacar linha ao passar mouse
     */
    tableRows.forEach(row => {
        row.addEventListener('mouseenter', function() {
            this.style.transform = 'scale(1.01)';
            this.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.1)';
            this.style.zIndex = '1';
        });

        row.addEventListener('mouseleave', function() {
            this.style.transform = '';
            this.style.boxShadow = '';
            this.style.zIndex = '';
        });
    });

    /**
     * Atalhos de teclado
     */
    document.addEventListener('keydown', function(e) {
        // Ctrl/Cmd + K = Focar na busca
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            searchInput.focus();
        }

        // Ctrl/Cmd + N = Novo usuário (se admin)
        if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
            const addButton = document.querySelector('.btn-primary');
            if (addButton) {
                e.preventDefault();
                addButton.click();
            }
        }
    });

    /**
     * Confirmar ações de delete com duplo clique
     */
    const deleteButtons = document.querySelectorAll('.btn-delete');
    deleteButtons.forEach(button => {
        let clickCount = 0;
        let clickTimer = null;

        button.addEventListener('click', function(e) {
            clickCount++;

            if (clickCount === 1) {
                clickTimer = setTimeout(() => {
                    clickCount = 0;
                }, 2000);
            }
        });
    });

    /**
     * Tooltip para botões de ação
     */
    const actionButtons = document.querySelectorAll('.btn-action');
    actionButtons.forEach(button => {
        button.addEventListener('mouseenter', function() {
            const title = this.getAttribute('title');
            if (title) {
                const tooltip = document.createElement('div');
                tooltip.className = 'tooltip';
                tooltip.textContent = title;
                document.body.appendChild(tooltip);

                const rect = this.getBoundingClientRect();
                tooltip.style.left = rect.left + (rect.width / 2) - (tooltip.offsetWidth / 2) + 'px';
                tooltip.style.top = rect.top - tooltip.offsetHeight - 8 + 'px';

                this._tooltip = tooltip;
            }
        });

        button.addEventListener('mouseleave', function() {
            if (this._tooltip) {
                this._tooltip.remove();
                this._tooltip = null;
            }
        });
    });

    /**
     * Contador de usuários visíveis
     */
    function updateVisibleCount() {
        const visible = Array.from(tableRows).filter(row => row.style.display !== 'none').length;
        const total = tableRows.length;

        // Pode adicionar um elemento para mostrar isso se quiser
        console.log(`Mostrando ${visible} de ${total} usuários`);
    }

    /**
     * Exportar dados (futuro)
     */
    function exportData() {
        // TODO: Implementar exportação para CSV/Excel
        console.log('Export feature - Coming soon!');
    }

    /**
     * Atualizar tabela sem reload (futuro - com AJAX)
     */
    function refreshTable() {
        // TODO: Implementar refresh via AJAX
        console.log('Refresh feature - Coming soon!');
    }

    console.log('✅ Dashboard initialized');
    console.log('💡 Atalhos:');
    console.log('   Ctrl+K ou Cmd+K = Focar na busca');
    console.log('   Ctrl+N ou Cmd+N = Novo usuário');
    console.log('   ESC = Limpar busca');
});