(function () {
    'use strict';

    /* ===== SELEÇÃO DE CLIENTE ===== */
    document.querySelectorAll('.crm-mock-cliente').forEach(function (card) {
        card.addEventListener('click', function () {
            document.querySelectorAll('.crm-mock-cliente').forEach(function (c) {
                c.classList.remove('crm-mock-cliente-ativo');
            });
            card.classList.add('crm-mock-cliente-ativo');
        });
    });

    /* ===== PILLS DE FILTRO ===== */
    document.querySelectorAll('.crm-mock-pill').forEach(function (pill) {
        pill.addEventListener('click', function () {
            document.querySelectorAll('.crm-mock-pill').forEach(function (p) {
                p.classList.remove('crm-mock-pill-active');
            });
            pill.classList.add('crm-mock-pill-active');

            var filtro = pill.getAttribute('data-filter');
            document.querySelectorAll('.crm-mock-cliente').forEach(function (card) {
                if (filtro === 'todos') {
                    card.classList.remove('hidden-by-filter');
                } else {
                    var status = card.getAttribute('data-status') || '';
                    card.classList.toggle('hidden-by-filter', status !== filtro);
                }
            });

            // Atualizar contador
            var visibles = document.querySelectorAll('.crm-mock-cliente:not(.hidden-by-filter)').length;
            var countEl = document.querySelector('.crm-mock-count');
            if (countEl) {
                countEl.textContent = visibles;
            }
        });
    });

    /* ===== ABAS GENÉRICAS ===== */
    function initTabs(groupName) {
        var tabContainer = document.querySelector('[data-tab-group="' + groupName + '"]');
        if (!tabContainer) return;

        tabContainer.querySelectorAll('.crm-mock-tab').forEach(function (tab) {
            tab.addEventListener('click', function () {
                var target = tab.getAttribute('data-tab');

                // Atualizar tabs ativas
                tabContainer.querySelectorAll('.crm-mock-tab').forEach(function (t) {
                    t.classList.remove('crm-mock-tab-active');
                });
                tab.classList.add('crm-mock-tab-active');

                // Atualizar painéis
                document.querySelectorAll('[data-panel-group="' + groupName + '"]').forEach(function (panel) {
                    var isTarget = panel.getAttribute('data-panel') === target;
                    panel.classList.toggle('crm-mock-tab-panel-active', isTarget);
                });

                // Se for aba de atividades, filtrar a lista
                if (groupName === 'atividades') {
                    filterAtividades(target);
                }
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

        // Esconder grupos de data vazios
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

            // Atualizar contador
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
            sidebar.style.display = sidebar.style.display === 'none' ? '' : 'none';
        });
    }

    /* ===== FAVORITAR CLIENTE ===== */
    document.querySelectorAll('.crm-mock-star').forEach(function (star) {
        star.addEventListener('click', function () {
            star.classList.toggle('active');
        });
    });

    /* ===== HOVER NOS BOTÕES DE AÇÃO RÁPIDA ===== */
    document.querySelectorAll('.crm-mock-quick-btn').forEach(function (btn) {
        btn.addEventListener('mouseenter', function () {
            btn.style.transform = 'translateY(-2px)';
        });
        btn.addEventListener('mouseleave', function () {
            btn.style.transform = '';
        });
    });

    /* ===== SELECTS DO HEADER ===== */
    document.querySelectorAll('.crm-mock-select').forEach(function (select) {
        select.addEventListener('change', function () {
            // Simular ação visual
            select.style.borderColor = '#22c55e';
            setTimeout(function () {
                select.style.borderColor = '';
            }, 300);
        });
    });

    /* ===== EFEITO NOS CARDS DE CLIENTE ===== */
    document.querySelectorAll('.crm-mock-cliente').forEach(function (card) {
        card.addEventListener('mouseenter', function () {
            if (!card.classList.contains('crm-mock-cliente-ativo')) {
                card.style.transform = 'translateX(2px)';
            }
        });
        card.addEventListener('mouseleave', function () {
            card.style.transform = '';
        });
    });

    /* ===== BOTÕES DE AÇÃO NAS ATIVIDADES ===== */
    document.querySelectorAll('.crm-mock-ativ-actions').forEach(function (btn) {
        btn.addEventListener('click', function (e) {
            e.stopPropagation();
            // Simular feedback visual
            btn.style.background = '#dcfce7';
            btn.style.color = '#166534';
            setTimeout(function () {
                btn.style.background = '';
                btn.style.color = '';
            }, 200);
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
