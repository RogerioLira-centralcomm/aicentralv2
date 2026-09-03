/**
 * CRM v3 — Atalhos de teclado + toggle de densidade + modo split.
 *
 * Atalhos globais (quando /crm-v3 está aberto e o foco não está em input/textarea):
 *   j / ↓  — próximo cliente na lista
 *   k / ↑  — cliente anterior
 *   Enter  — abrir cliente focado
 *   n      — novo cliente (drawer)
 *   t      — nova atividade (drawer) do cliente selecionado
 *   c      — nova cotação (drawer)
 *   d      — alternar densidade confortável/compacto
 *   Esc    — fecha drawer aberto
 *
 * Depende de:
 * - window.crmV3 (crm_v3.js)
 * - window.crmV3Drawer (crm_v3_drawers.js)
 * - window.cxDrawer (cx_drawer.js)
 */
(function () {
    'use strict';

    var focusedIdx = -1;

    function isTypingContext(el) {
        if (!el) return false;
        var tag = (el.tagName || '').toLowerCase();
        if (tag === 'input' || tag === 'textarea' || tag === 'select') return true;
        if (el.isContentEditable) return true;
        return false;
    }

    function getCards() {
        return Array.prototype.slice.call(document.querySelectorAll('#crm-v3-lista-clientes .crm-v3-cliente'));
    }

    function focusCard(cards, idx) {
        if (!cards.length) return;
        idx = Math.max(0, Math.min(cards.length - 1, idx));
        cards.forEach(function (c) { c.classList.remove('is-focused'); });
        cards[idx].classList.add('is-focused');
        cards[idx].scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        focusedIdx = idx;
    }

    function openFocused(cards) {
        if (focusedIdx < 0 || focusedIdx >= cards.length) return;
        var id = cards[focusedIdx].getAttribute('data-cliente-id');
        if (id && window.crmV3 && typeof window.crmV3.selectCliente === 'function') {
            window.crmV3.selectCliente(id);
        }
    }

    function toggleDensidade() {
        var page = document.querySelector('.crm-v3-page');
        if (!page) return;
        page.classList.toggle('is-compact');
        try {
            localStorage.setItem('crmV3.densidade', page.classList.contains('is-compact') ? 'compact' : 'comfort');
        } catch (_) { /* ignore */ }
    }

    function restoreDensidade() {
        try {
            var v = localStorage.getItem('crmV3.densidade');
            if (v === 'compact') {
                var page = document.querySelector('.crm-v3-page');
                if (page) page.classList.add('is-compact');
            }
        } catch (_) { /* ignore */ }
    }

    document.addEventListener('DOMContentLoaded', function () {
        // Restaurar densidade
        restoreDensidade();

        // Botão de densidade
        var btnDens = document.getElementById('crm-v3-btn-densidade');
        if (btnDens) btnDens.addEventListener('click', toggleDensidade);

        // Registrar atalhos apenas na página /crm-v3
        if (!document.querySelector('.crm-v3-page')) return;

        document.addEventListener('keydown', function (ev) {
            if (isTypingContext(document.activeElement)) return;
            // Deixa Ctrl/Cmd/Alt passar
            if (ev.ctrlKey || ev.metaKey || ev.altKey) return;

            var cards = getCards();
            var state = (window.crmV3 && window.crmV3.state) || {};
            var handled = false;

            switch (ev.key) {
                case 'j':
                case 'ArrowDown':
                    if (focusedIdx < 0) {
                        // Se há cliente selecionado, começa dele
                        var currentId = state.clienteId;
                        focusedIdx = cards.findIndex(function (c) { return c.getAttribute('data-cliente-id') === currentId; });
                        if (focusedIdx < 0) focusedIdx = 0;
                    } else {
                        focusedIdx += 1;
                    }
                    focusCard(cards, focusedIdx);
                    handled = true;
                    break;
                case 'k':
                case 'ArrowUp':
                    if (focusedIdx < 0) focusedIdx = 0;
                    else focusedIdx -= 1;
                    focusCard(cards, focusedIdx);
                    handled = true;
                    break;
                case 'Enter':
                    openFocused(cards);
                    handled = true;
                    break;
                case 'n':
                    if (window.crmV3Drawer) { window.crmV3Drawer.openCliente(null); handled = true; }
                    break;
                case 't':
                    if (state.clienteId && window.crmV3Drawer) {
                        window.crmV3Drawer.openAtividade(null, state.clienteId);
                        handled = true;
                    }
                    break;
                case 'c':
                    if (state.clienteId && window.crmV3Drawer) {
                        window.crmV3Drawer.openCotacao(null, state.clienteId);
                        handled = true;
                    }
                    break;
                case 'd':
                    toggleDensidade();
                    handled = true;
                    break;
                case '?':
                    mostrarAtalhos();
                    handled = true;
                    break;
                default:
                    break;
            }

            if (handled) ev.preventDefault();
        });
    });

    function mostrarAtalhos() {
        if (!window.cxDrawer) return;
        var html = (
            '<div class="cx-drawer-section">' +
            '<div class="cx-drawer-section-title">Atalhos</div>' +
            '<table class="table table-sm">' +
            '<tbody>' +
            '<tr><td><kbd>j</kbd> / <kbd>↓</kbd></td><td>Próximo cliente</td></tr>' +
            '<tr><td><kbd>k</kbd> / <kbd>↑</kbd></td><td>Cliente anterior</td></tr>' +
            '<tr><td><kbd>Enter</kbd></td><td>Abrir cliente focado</td></tr>' +
            '<tr><td><kbd>n</kbd></td><td>Novo cliente (drawer)</td></tr>' +
            '<tr><td><kbd>t</kbd></td><td>Nova atividade (drawer)</td></tr>' +
            '<tr><td><kbd>c</kbd></td><td>Nova cotação (drawer)</td></tr>' +
            '<tr><td><kbd>d</kbd></td><td>Alternar densidade</td></tr>' +
            '<tr><td><kbd>Esc</kbd></td><td>Fechar drawer</td></tr>' +
            '<tr><td><kbd>?</kbd></td><td>Mostrar esta lista</td></tr>' +
            '</tbody></table></div>'
        );
        window.cxDrawer.open({
            title: 'Atalhos de teclado',
            breadcrumb: 'CRM v3 · Ajuda',
            size: 'sm',
            content: html,
            actions: [{ label: 'Fechar', variant: 'primary', close: true }]
        });
    }
})();
