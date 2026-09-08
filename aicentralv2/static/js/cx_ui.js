/**
 * Interações compartilhadas do design system CentralX.
 * Usa somente APIs nativas e atributos data-* para não acoplar regra de negócio.
 */
(function (global) {
    'use strict';

    function getDialog(target) {
        if (!target) return null;
        if (target instanceof HTMLDialogElement) return target;
        if (typeof target === 'string') {
            return document.getElementById(target.replace(/^#/, ''));
        }
        return target.closest ? target.closest('dialog') : null;
    }

    function openModal(target) {
        var dialog = getDialog(target);
        if (!dialog || typeof dialog.showModal !== 'function') return false;
        if (!dialog.open) dialog.showModal();
        return true;
    }

    function closeModal(target, returnValue) {
        var dialog = getDialog(target);
        if (!dialog || typeof dialog.close !== 'function') return false;
        if (dialog.open) dialog.close(returnValue || '');
        return true;
    }

    function activateTab(button) {
        var tablist = button.closest('[role="tablist"], [data-cx-tabs]');
        if (!tablist) return;

        var targetId = button.getAttribute('aria-controls') || button.dataset.cxTab;
        tablist.querySelectorAll('[role="tab"], [data-cx-tab]').forEach(function (tab) {
            var active = tab === button;
            tab.classList.toggle('cx-tab-active', active);
            tab.setAttribute('aria-selected', active ? 'true' : 'false');
            tab.tabIndex = active ? 0 : -1;
        });

        if (targetId) {
            var scope = tablist.closest('[data-cx-tab-scope]') || document;
            scope.querySelectorAll('[role="tabpanel"], [data-cx-tab-panel]').forEach(function (panel) {
                var active = panel.id === targetId;
                panel.hidden = !active;
                panel.classList.toggle('hidden', !active);
            });
        }
    }

    document.addEventListener('click', function (event) {
        var openButton = event.target.closest('[data-cx-modal-open], [data-open-modal]');
        if (openButton) {
            openModal(openButton.dataset.cxModalOpen || openButton.dataset.openModal);
            return;
        }

        var closeButton = event.target.closest('[data-cx-modal-close], [data-close-modal]');
        if (closeButton) {
            closeModal(closeButton);
            return;
        }

        var tabButton = event.target.closest('[data-cx-tab]');
        if (tabButton) activateTab(tabButton);
    });

    document.addEventListener('keydown', function (event) {
        var tab = event.target.closest && event.target.closest('[role="tab"][data-cx-tab]');
        if (!tab || !['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;

        var tabs = Array.from(tab.closest('[role="tablist"]').querySelectorAll('[role="tab"][data-cx-tab]'));
        var current = tabs.indexOf(tab);
        var next = event.key === 'Home' ? 0
            : event.key === 'End' ? tabs.length - 1
                : (current + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
        event.preventDefault();
        tabs[next].focus();
        activateTab(tabs[next]);
    });

    global.cxUI = {
        openModal: openModal,
        closeModal: closeModal,
        activateTab: activateTab
    };
})(window);
