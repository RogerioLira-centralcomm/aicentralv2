// ===== DASHBOARD JAVASCRIPT =====

document.addEventListener('DOMContentLoaded', function() {

    // ===== SIDEBAR TOGGLE (MOBILE) =====
    const sidebar = document.getElementById('sidebar');
    const mobileMenuToggle = document.getElementById('mobileMenuToggle');

    if (mobileMenuToggle) {
        mobileMenuToggle.addEventListener('click', function() {
            sidebar.classList.toggle('active');
        });
    }

    // ===== SEARCH FUNCTIONALITY =====
    const searchInput = document.getElementById('searchInput');
    const tableRows = document.querySelectorAll('.table-row');
    const noResults = document.getElementById('noResults');
    const tableWrapper = document.querySelector('.table-wrapper');

    if (searchInput) {
        searchInput.addEventListener('input', function() {
            const searchTerm = this.value.toLowerCase();
            let visibleCount = 0;

            tableRows.forEach(row => {
                const searchData = row.getAttribute('data-search');
                const matchesSearch = searchData.includes(searchTerm);
                const matchesFilter = checkFilters(row);

                if (matchesSearch && matchesFilter) {
                    row.style.display = '';
                    visibleCount++;
                } else {
                    row.style.display = 'none';
                }
            });

            // Show/hide no results message
            if (visibleCount === 0) {
                tableWrapper.style.display = 'none';
                noResults.style.display = 'block';
            } else {
                tableWrapper.style.display = 'block';
                noResults.style.display = 'none';
            }
        });
    }

    // ===== FILTER CHIPS =====
    const filterChips = document.querySelectorAll('.chip');
    let activeFilter = 'all';

    filterChips.forEach(chip => {
        chip.addEventListener('click', function() {
            // Remove active class from all chips
            filterChips.forEach(c => c.classList.remove('active'));

            // Add active class to clicked chip
            this.classList.add('active');

            // Update active filter
            activeFilter = this.getAttribute('data-filter');

            // Apply filters
            applyFilters();
        });
    });

    function checkFilters(row) {
        if (activeFilter === 'all') return true;

        if (activeFilter === 'active') {
            return row.getAttribute('data-status') === 'active';
        }

        if (activeFilter === 'inactive') {
            return row.getAttribute('data-status') === 'inactive';
        }

        if (activeFilter === 'admin') {
            return row.getAttribute('data-admin') === 'true';
        }

        if (activeFilter === 'cliente') {
            return row.getAttribute('data-cliente') === 'true';
        }

        return true;
    }

    function applyFilters() {
        const searchTerm = searchInput ? searchInput.value.toLowerCase() : '';
        let visibleCount = 0;

        tableRows.forEach(row => {
            const searchData = row.getAttribute('data-search');
            const matchesSearch = searchTerm === '' || searchData.includes(searchTerm);
            const matchesFilter = checkFilters(row);

            if (matchesSearch && matchesFilter) {
                row.style.display = '';
                visibleCount++;
            } else {
                row.style.display = 'none';
            }
        });

        // Show/hide no results
        if (visibleCount === 0) {
            tableWrapper.style.display = 'none';
            noResults.style.display = 'block';
        } else {
            tableWrapper.style.display = 'block';
            noResults.style.display = 'none';
        }
    }

    // ===== SELECT ALL CHECKBOX =====
    const selectAllCheckbox = document.getElementById('selectAll');
    const rowCheckboxes = document.querySelectorAll('.row-checkbox');

    if (selectAllCheckbox) {
        selectAllCheckbox.addEventListener('change', function() {
            rowCheckboxes.forEach(checkbox => {
                checkbox.checked = this.checked;
            });
        });
    }

    // ===== AUTO-HIDE ALERTS =====
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.animation = 'slideUp 0.3s ease';
            setTimeout(() => {
                alert.remove();
            }, 300);
        }, 5000);
    });

    // ===== CLEAR FILTERS FUNCTION =====
    window.clearFilters = function() {
        // Reset search
        if (searchInput) {
            searchInput.value = '';
        }

        // Reset filter chips
        filterChips.forEach(chip => {
            chip.classList.remove('active');
            if (chip.getAttribute('data-filter') === 'all') {
                chip.classList.add('active');
            }
        });

        activeFilter = 'all';

        // Show all rows
        tableRows.forEach(row => {
            row.style.display = '';
        });

        // Hide no results
        if (tableWrapper && noResults) {
            tableWrapper.style.display = 'block';
            noResults.style.display = 'none';
        }
    };

    // ===== SMOOTH ANIMATIONS =====
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.animation = 'fadeInUp 0.5s ease';
            }
        });
    }, { threshold: 0.1 });

    // Observe stat cards
    document.querySelectorAll('.stat-card').forEach(card => {
        observer.observe(card);
    });

    console.log('✅ Dashboard carregado com sucesso!');
});

// ===== CSS ANIMATIONS =====
const style = document.createElement('style');
style.textContent = `
    @keyframes fadeInUp {
        from {
            opacity: 0;
            transform: translateY(20px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }

    @keyframes slideUp {
        to {
            opacity: 0;
            transform: translateY(-10px);
        }
    }
`;
document.head.appendChild(style);