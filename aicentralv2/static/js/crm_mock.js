(function () {
    'use strict';

    /* ===== SELEÇÃO DE CLIENTE ===== */
    function selectCliente(card) {
        document.querySelectorAll('.crm-mock-cliente').forEach(function (c) {
            c.classList.remove('crm-mock-cliente-ativo');
            c.setAttribute('aria-current', 'false');
        });
        card.classList.add('crm-mock-cliente-ativo');
        card.setAttribute('aria-current', 'true');
    }

    document.querySelectorAll('.crm-mock-cliente').forEach(function (card) {
        card.setAttribute('aria-current', card.classList.contains('crm-mock-cliente-ativo') ? 'true' : 'false');

        card.addEventListener('click', function () {
            selectCliente(card);
        });

        card.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                selectCliente(card);
            }
        });
    });

    /* ===== PILLS DE FILTRO ===== */
    document.querySelectorAll('.crm-mock-pill').forEach(function (pill) {
        pill.addEventListener('click', function () {
            document.querySelectorAll('.crm-mock-pill').forEach(function (p) {
                p.classList.remove('crm-mock-pill-active');
                p.setAttribute('aria-pressed', 'false');
            });
            pill.classList.add('crm-mock-pill-active');
            pill.setAttribute('aria-pressed', 'true');

            var filtro = pill.getAttribute('data-filter');
            document.querySelectorAll('.crm-mock-cliente').forEach(function (card) {
                if (filtro === 'todos') {
                    card.classList.remove('hidden-by-filter');
                } else {
                    var status = card.getAttribute('data-status') || '';
                    card.classList.toggle('hidden-by-filter', status !== filtro);
                }
            });

            var visibles = document.querySelectorAll('.crm-mock-cliente:not(.hidden-by-filter)').length;
            var countEl = document.querySelector('.crm-mock-count');
            if (countEl) {
                countEl.textContent = visibles;
            }
        });
        pill.setAttribute('aria-pressed', pill.classList.contains('crm-mock-pill-active') ? 'true' : 'false');
    });

    /* ===== ABAS GENÉRICAS ===== */
    function initTabs(groupName) {
        var tabContainer = document.querySelector('[data-tab-group="' + groupName + '"]');
        if (!tabContainer) return;

        var tabs = tabContainer.querySelectorAll('.crm-mock-tab');

        function activateTab(tab) {
            var target = tab.getAttribute('data-tab');

            tabs.forEach(function (t) {
                t.classList.remove('crm-mock-tab-active');
                t.setAttribute('aria-selected', 'false');
            });
            tab.classList.add('crm-mock-tab-active');
            tab.setAttribute('aria-selected', 'true');

            document.querySelectorAll('[data-panel-group="' + groupName + '"]').forEach(function (panel) {
                var isTarget = panel.getAttribute('data-panel') === target;
                panel.classList.toggle('crm-mock-tab-panel-active', isTarget);
                if (panel.hasAttribute('hidden')) {
                    panel.hidden = !isTarget;
                }
            });

            if (groupName === 'atividades') {
                filterAtividades(target);
            }
        }

        tabs.forEach(function (tab, index) {
            tab.addEventListener('click', function () {
                activateTab(tab);
            });

            tab.addEventListener('keydown', function (e) {
                var nextIndex = index;
                if (e.key === 'ArrowRight') {
                    nextIndex = (index + 1) % tabs.length;
                } else if (e.key === 'ArrowLeft') {
                    nextIndex = (index - 1 + tabs.length) % tabs.length;
                } else if (e.key === 'Home') {
                    nextIndex = 0;
                } else if (e.key === 'End') {
                    nextIndex = tabs.length - 1;
                } else {
                    return;
                }
                e.preventDefault();
                tabs[nextIndex].focus();
                activateTab(tabs[nextIndex]);
            });
        });
    }

    initTabs('atividades');
    initTabs('sidebar');

    /* ===== FILTRO DE ATIVIDADES POR ABA ===== */
    function filterAtividades(filtro) {
        document.querySelectorAll('.crm-mock-ativ-list .crm-mock-ativ').forEach(function (item) {
            var status = item.getAttribute('data-status') || 'pendente';
            var show = true;

            if (filtro === 'pendentes') {
                show = status !== 'concluida';
            } else if (filtro === 'concluidas') {
                show = status === 'concluida';
            }

            item.classList.toggle('hidden-by-tab', !show);
        });

        document.querySelectorAll('.crm-mock-date-group').forEach(function (group) {
            var visibleItems = group.querySelectorAll('.crm-mock-ativ:not(.hidden-by-tab)').length;
            group.style.display = visibleItems > 0 ? '' : 'none';
        });
    }

    /* ===== CHECKBOX DE ATIVIDADE ===== */
    document.querySelectorAll('.crm-mock-ativ-check').forEach(function (cb) {
        cb.addEventListener('change', function () {
            var row = cb.closest('.crm-mock-ativ');
            if (row) {
                row.classList.toggle('crm-mock-ativ-concluida', cb.checked);
                row.setAttribute('data-status', cb.checked ? 'concluida' : 'pendente');
            }
        });
    });

    /* ===== BUSCA DE CLIENTES ===== */
    var buscaCliente = document.getElementById('crm-mock-busca');
    if (buscaCliente) {
        buscaCliente.addEventListener('input', function () {
            var termo = buscaCliente.value.toLowerCase().trim();
            document.querySelectorAll('.crm-mock-cliente').forEach(function (card) {
                var nome = (card.getAttribute('data-nome') || '').toLowerCase();
                var shouldHide = termo !== '' && nome.indexOf(termo) === -1;
                card.classList.toggle('hidden-by-filter', shouldHide);
            });

            var visibles = document.querySelectorAll('.crm-mock-cliente:not(.hidden-by-filter)').length;
            var countEl = document.querySelector('.crm-mock-count');
            if (countEl) {
                countEl.textContent = visibles;
            }
        });
    }

    /* ===== FECHAR SIDEBAR ===== */
    var closeBtn = document.getElementById('crm-mock-close-sidebar');
    var sidebar = document.getElementById('crm-mock-sidebar');
    if (closeBtn && sidebar) {
        closeBtn.addEventListener('click', function () {
            sidebar.classList.toggle('is-hidden');
        });
    }

    /* ===== FAVORITAR CLIENTE ===== */
    document.querySelectorAll('.crm-mock-star').forEach(function (star) {
        star.addEventListener('click', function () {
            var isActive = star.classList.toggle('active');
            star.setAttribute('aria-pressed', isActive ? 'true' : 'false');
            star.setAttribute('aria-label', isActive ? 'Remover dos favoritos' : 'Adicionar aos favoritos');
        });
    });

    /* ===== SELECTS DO HEADER ===== */
    document.querySelectorAll('.crm-mock-select').forEach(function (select) {
        select.addEventListener('change', function () {
            select.style.borderColor = '#1E4D4F';
            setTimeout(function () {
                select.style.borderColor = '';
            }, 300);
        });
    });

    /* ===== CHECKBOXES DE OBJETIVOS ===== */
    document.querySelectorAll('.crm-mock-objetivo .crm-mock-checkbox').forEach(function (cb) {
        cb.addEventListener('change', function () {
            var row = cb.closest('.crm-mock-objetivo');
            if (row) {
                var text = row.querySelector('.crm-mock-obj-text');
                if (text) {
                    text.style.textDecoration = cb.checked ? 'line-through' : '';
                    text.style.color = cb.checked ? '#9ca3af' : '';
                }
            }
        });
    });

})();
