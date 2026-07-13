(function () {
    'use strict';

    const BASE = '/financeiro/api';

    function $(sel, root) { return (root || document).querySelector(sel); }
    function money(v) {
        const n = Number(v) || 0;
        return n.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
    }
    function statusBadge(st) {
        const map = {
            draft: ['Rascunho', 'badge-ghost'],
            submitted: ['Enviado', 'badge-info'],
            approved: ['Aprovado', 'badge-success'],
            rejected: ['Rejeitado', 'badge-error'],
            closed: ['Fechado', 'badge-neutral'],
            processing: ['Processando', 'badge-warning'],
            extracted: ['Conferir', 'badge-warning'],
            extraction_failed: ['Falha IA', 'badge-error'],
        };
        const [label, cls] = map[st] || [st, 'badge-ghost'];
        return `<span class="badge badge-sm ${cls}">${label}</span>`;
    }
    function showToast(msg, type) {
        if (typeof window.showToast === 'function') window.showToast(msg, type);
        else alert(msg);
    }

    async function api(path, opts = {}) {
        const resp = await fetch(BASE + path, {
            headers: opts.body instanceof FormData
                ? { ...(opts.headers || {}) }
                : { 'Content-Type': 'application/json', ...(opts.headers || {}) },
            ...opts,
        });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok) {
            const err = new Error(data.error || `HTTP ${resp.status}`);
            err.data = data;
            throw err;
        }
        return data;
    }

    async function loadCategories() {
        const r = await api('/categories');
        const sel = $('#fin-category');
        if (!sel) return;
        sel.innerHTML = '<option value="">Selecione…</option>' +
            (r.categories || []).map(c => `<option value="${c.id}">${c.label}</option>`).join('');
    }

    async function loadClients() {
        const r = await api('/clients');
        const sel = $('#fin-client');
        if (!sel) return;
        sel.innerHTML = '<option value="">—</option>' +
            (r.clients || []).map(c =>
                `<option value="${c.id_cliente}">${(c.nome_fantasia || c.razao_social || '').replace(/</g, '')}</option>`
            ).join('');
    }

    async function loadSummary() {
        const r = await api('/my/summary');
        const s = r.summary || {};
        $('#fin-sum-draft').textContent = money(s.draft_total);
        $('#fin-sum-submitted').textContent = money(s.submitted_total);
        $('#fin-sum-approved').textContent = money(s.approved_total);
        $('#fin-sum-rejected').textContent = money(s.rejected_total);
    }

    async function loadLista() {
        const status = $('#fin-filter-status')?.value || '';
        const qs = status ? `?status=${encodeURIComponent(status)}` : '';
        const container = $('#fin-lista');
        try {
            const r = await api('/expenses' + qs);
            const rows = r.expenses || [];
            if (!rows.length) {
                container.innerHTML = '<div class="text-center text-sm opacity-50 py-8">Nenhuma despesa ainda.</div>';
                return;
            }
            container.innerHTML = rows.map(e => `
                <div class="bg-base-100 border border-base-200 rounded-lg p-3 flex flex-wrap gap-3 items-start justify-between" data-id="${e.id}">
                    <div class="min-w-0 flex-1">
                        <div class="flex flex-wrap items-center gap-2 mb-1">
                            ${statusBadge(e.status)}
                            <span class="font-medium text-sm">${escapeHtml(e.merchant_name || 'Sem estabelecimento')}</span>
                            <span class="text-xs opacity-50">${e.expense_date || '—'}</span>
                        </div>
                        <div class="text-sm font-semibold">${money(e.total_amount)}</div>
                        <div class="text-xs opacity-60">
                            ${escapeHtml(e.category_label || '')}
                            ${e.association_type ? ' · ' + e.association_type + (e.association_label ? ': ' + escapeHtml(e.association_label) : '') : ''}
                        </div>
                        ${e.status === 'rejected' && e.rejection_reason
                            ? `<div class="text-xs text-error mt-1">Motivo: ${escapeHtml(e.rejection_reason)}</div>` : ''}
                    </div>
                    <div class="flex flex-wrap gap-1">
                        ${['draft', 'rejected', 'extracted', 'extraction_failed'].includes(e.status)
                            ? `<button type="button" class="btn btn-xs btn-primary fin-submit" data-id="${e.id}">Enviar</button>` : ''}
                        ${!['approved', 'closed'].includes(e.status)
                            ? `<button type="button" class="btn btn-xs btn-ghost text-error fin-delete" data-id="${e.id}">Excluir</button>` : ''}
                    </div>
                </div>
            `).join('');

            container.querySelectorAll('.fin-submit').forEach(btn => {
                btn.addEventListener('click', async () => {
                    try {
                        await api(`/expenses/${btn.dataset.id}/submit`, { method: 'POST' });
                        showToast('Despesa enviada ao financeiro.', 'success');
                        refreshAll();
                    } catch (err) {
                        showToast(err.message, 'error');
                    }
                });
            });
            container.querySelectorAll('.fin-delete').forEach(btn => {
                btn.addEventListener('click', async () => {
                    if (!confirm('Excluir esta despesa?')) return;
                    try {
                        await api(`/expenses/${btn.dataset.id}`, { method: 'DELETE' });
                        showToast('Despesa excluída.', 'success');
                        refreshAll();
                    } catch (err) {
                        showToast(err.message, 'error');
                    }
                });
            });
        } catch (err) {
            container.innerHTML = `<div class="text-error text-sm text-center py-4">${escapeHtml(err.message)}</div>`;
        }
    }

    function escapeHtml(s) {
        return String(s || '')
            .replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    function parseMoneyBR(str) {
        if (str == null || str === '') return null;
        const digits = String(str).replace(/[^\d]/g, '');
        if (!digits) return null;
        return parseInt(digits, 10) / 100;
    }

    function formatMoneyInput(input) {
        const digits = String(input.value || '').replace(/[^\d]/g, '');
        if (!digits) {
            input.value = '';
            return;
        }
        const num = parseInt(digits, 10) / 100;
        input.value = 'R$ ' + num.toLocaleString('pt-BR', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
    }

    function openDatePicker(el) {
        if (!el) return;
        try {
            if (typeof el.showPicker === 'function') el.showPicker();
        } catch (_) {
            // alguns browsers bloqueiam showPicker fora de gesto do usuário
            el.focus();
        }
    }

    function formData() {
        return {
            expense_date: $('#fin-date').value || null,
            merchant_name: $('#fin-merchant').value.trim(),
            total_amount: parseMoneyBR($('#fin-total').value),
            category_id: $('#fin-category').value || null,
            association_type: $('#fin-assoc-type').value || null,
            association_label: $('#fin-assoc-label').value.trim(),
            client_id: $('#fin-client').value || null,
            notes: $('#fin-notes').value.trim(),
        };
    }

    function resetForm() {
        $('#fin-form-nova')?.reset();
        $('#fin-file-name').textContent = '';
        $('#fin-client-wrap').classList.add('hidden');
    }

    async function createAndMaybeUpload(submitAfter) {
        const fileInput = $('#fin-file');
        const file = fileInput?.files?.[0];
        if (submitAfter && !file) {
            showToast('Anexe o comprovante antes de enviar.', 'warning');
            return;
        }
        const payload = formData();
        if (!payload.expense_date || payload.total_amount == null || payload.total_amount <= 0) {
            showToast('Data e valor total são obrigatórios.', 'warning');
            return;
        }

        const btnDraft = $('#fin-btn-draft');
        const btnSubmit = $('#fin-btn-submit');
        btnDraft?.classList.add('loading');
        btnSubmit?.classList.add('loading');
        try {
            const r = await api('/expenses', {
                method: 'POST',
                body: JSON.stringify(payload),
            });
            const id = r.expense.id;
            if (file) {
                const fd = new FormData();
                fd.append('file', file);
                await api(`/expenses/${id}/receipts`, { method: 'POST', body: fd });
            }
            if (submitAfter) {
                await api(`/expenses/${id}/submit`, { method: 'POST' });
                showToast('Despesa enviada ao financeiro.', 'success');
            } else {
                showToast('Rascunho salvo.', 'success');
            }
            resetForm();
            refreshAll();
        } catch (err) {
            showToast(err.message, 'error');
        } finally {
            btnDraft?.classList.remove('loading');
            btnSubmit?.classList.remove('loading');
        }
    }

    function refreshAll() {
        loadSummary();
        loadLista();
    }

    document.addEventListener('DOMContentLoaded', () => {
        if (!$('#fin-reembolsos-app')) return;

        const drop = $('#fin-dropzone');
        const fileInput = $('#fin-file');
        drop?.addEventListener('click', () => fileInput?.click());
        drop?.addEventListener('dragover', (e) => { e.preventDefault(); drop.classList.add('border-primary'); });
        drop?.addEventListener('dragleave', () => drop.classList.remove('border-primary'));
        drop?.addEventListener('drop', (e) => {
            e.preventDefault();
            drop.classList.remove('border-primary');
            if (e.dataTransfer.files?.[0]) {
                fileInput.files = e.dataTransfer.files;
                $('#fin-file-name').textContent = e.dataTransfer.files[0].name;
            }
        });
        fileInput?.addEventListener('change', () => {
            $('#fin-file-name').textContent = fileInput.files?.[0]?.name || '';
        });

        $('#fin-assoc-type')?.addEventListener('change', () => {
            const isCli = $('#fin-assoc-type').value === 'cliente';
            $('#fin-client-wrap').classList.toggle('hidden', !isCli);
        });

        const dateEl = $('#fin-date');
        dateEl?.addEventListener('click', () => openDatePicker(dateEl));
        dateEl?.addEventListener('focus', () => openDatePicker(dateEl));

        const totalEl = $('#fin-total');
        totalEl?.addEventListener('input', () => formatMoneyInput(totalEl));
        totalEl?.addEventListener('blur', () => {
            if (totalEl.value && !String(totalEl.value).startsWith('R$')) {
                formatMoneyInput(totalEl);
            }
        });

        $('#fin-form-nova')?.addEventListener('submit', (e) => {
            e.preventDefault();
            createAndMaybeUpload(false);
        });
        $('#fin-btn-submit')?.addEventListener('click', () => createAndMaybeUpload(true));
        $('#fin-btn-refresh')?.addEventListener('click', refreshAll);
        $('#fin-filter-status')?.addEventListener('change', loadLista);

        loadCategories();
        loadClients();
        refreshAll();
    });
})();
