(function () {
    'use strict';

    const BASE = '/financeiro/api';
    const expandedSummaries = new Set();

    function $(sel, root) { return (root || document).querySelector(sel); }

    function money(v) {
        const n = Number(v) || 0;
        return n.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
    }

    function dateBR(iso) {
        if (!iso) return '—';
        const m = String(iso).match(/^(\d{4})-(\d{2})-(\d{2})/);
        return m ? `${m[3]}/${m[2]}/${m[1]}` : iso;
    }

    function escapeHtml(s) {
        return String(s || '')
            .replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    const STATUS_MAP = {
        draft: ['Rascunho', 'badge-ghost'],
        submitted: ['Enviado', 'badge-info'],
        approved: ['Aprovado', 'badge-success'],
        rejected: ['Rejeitado', 'badge-error'],
        closed: ['Fechado', 'badge-neutral'],
        processing: ['Processando', 'badge-warning'],
        extracted: ['Conferir', 'badge-warning'],
        extraction_failed: ['Falha IA', 'badge-error'],
    };

    const SUMMARY_STATUS = {
        open: ['Em andamento', 'badge-warning'],
        paid: ['Pago', 'badge-success'],
    };

    function statusBadge(st) {
        const [label, cls] = STATUS_MAP[st] || [st, 'badge-ghost'];
        return `<span class="badge badge-sm ${cls}">${label}</span>`;
    }

    function summaryStatusBadge(st) {
        const [label, cls] = SUMMARY_STATUS[st] || [st, 'badge-ghost'];
        return `<span class="badge badge-sm ${cls}">${label}</span>`;
    }

    function showToast(msg, type) {
        if (typeof window.showToast === 'function') window.showToast(msg, type);
        else alert(msg);
    }

    function openDatePicker(el) {
        if (!el) return;
        try { if (typeof el.showPicker === 'function') el.showPicker(); }
        catch (_) { el.focus(); }
    }

    function wireDatePickers() {
        ['#fin-f-from', '#fin-f-to', '#fin-adm-paid-date'].forEach(sel => {
            const el = $(sel);
            if (!el) return;
            el.addEventListener('click', () => openDatePicker(el));
            el.addEventListener('focus', () => openDatePicker(el));
        });
    }

    async function api(path, opts = {}) {
        const resp = await fetch(BASE + path, {
            headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) },
            ...opts,
        });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok) throw new Error(data.error || `HTTP ${resp.status}`);
        return data;
    }

    function currentFilters() {
        const p = new URLSearchParams();
        const status = $('#fin-f-status').value;
        const user = $('#fin-f-user').value;
        const from = $('#fin-f-from').value;
        const to = $('#fin-f-to').value;
        if (status) p.set('status', status);
        if (user) p.set('user_id', user);
        if (from) p.set('date_from', from);
        if (to) p.set('date_to', to);
        const qs = p.toString();
        return qs ? '?' + qs : '';
    }

    async function loadFilters() {
        try {
            const uc = await api('/admin/users');
            const uSel = $('#fin-f-user');
            uSel.innerHTML = '<option value="">Todos</option>' +
                (uc.users || []).map(u =>
                    `<option value="${u.id}">${escapeHtml(u.nome || u.email || ('#' + u.id))}</option>`
                ).join('');
        } catch (err) {
            showToast(err.message, 'error');
        }
    }

    async function loadSummary() {
        try {
            const r = await api('/admin/summary' + currentFilters());
            const s = r.summary || {};
            $('#fin-adm-open-q').textContent = String(s.open_qtd || 0);
            $('#fin-adm-approved').textContent = money(s.payable_total);
            $('#fin-adm-submitted').textContent = money(s.submitted_total);
            $('#fin-adm-submitted-q').textContent = (s.submitted_qtd || 0) + ' itens';
            $('#fin-adm-rejected').textContent = money(s.rejected_total);
        } catch (err) {
            showToast(err.message, 'error');
        }
    }

    function renderExpenseRow(e) {
        const rejectedNote = e.status === 'rejected' && e.rejection_reason
            ? `<div class="text-xs text-error mt-0.5">Motivo: ${escapeHtml(e.rejection_reason)}</div>` : '';
        const reviewActions = e.status === 'submitted'
            ? `<button type="button" class="btn btn-xs btn-success fin-adm-approve" data-id="${e.id}">Aprovar</button>
               <button type="button" class="btn btn-xs btn-error btn-outline fin-adm-reject" data-id="${e.id}">Reprovar</button>`
            : '';
        return `
        <tr class="fin-expense-row" data-id="${e.id}">
            <td class="whitespace-nowrap pl-4">${dateBR(e.expense_date)}</td>
            <td class="text-right font-medium whitespace-nowrap">${money(e.total_amount)}</td>
            <td class="whitespace-nowrap">${escapeHtml(e.category_label || '—')}</td>
            <td class="min-w-[8rem]">${escapeHtml(e.merchant_name || '—')}${rejectedNote}</td>
            <td class="whitespace-nowrap">${statusBadge(e.status)}</td>
            <td class="text-right whitespace-nowrap">
                <div class="flex gap-1 justify-end flex-wrap">
                    ${reviewActions}
                    <button type="button" class="btn btn-xs btn-ghost fin-adm-receipt" data-id="${e.id}" title="Ver comprovante">📎</button>
                </div>
            </td>
        </tr>`;
    }

    function wireExpenseRows(container) {
        container.querySelectorAll('.fin-adm-receipt').forEach(btn => {
            btn.addEventListener('click', () => openReceipt(btn.dataset.id));
        });
        container.querySelectorAll('.fin-adm-approve').forEach(btn => {
            btn.addEventListener('click', () => approveExpense(btn.dataset.id));
        });
        container.querySelectorAll('.fin-adm-reject').forEach(btn => {
            btn.addEventListener('click', () => openRejectModal(btn.dataset.id));
        });
    }

    async function loadExpensesForSummary(summaryId, tbody) {
        const detailRow = tbody.querySelector(`tr.fin-detail[data-summary-id="${summaryId}"]`);
        if (!detailRow) return;
        const inner = detailRow.querySelector('.fin-detail-inner');
        inner.innerHTML = '<tr><td colspan="6" class="text-center text-xs opacity-50 py-4">Carregando despesas…</td></tr>';
        try {
            const r = await api(`/admin/summaries/${summaryId}/expenses`);
            const rows = r.expenses || [];
            if (!rows.length) {
                inner.innerHTML = '<tr><td colspan="6" class="text-center text-xs opacity-50 py-4">Nenhuma despesa neste lote.</td></tr>';
                return;
            }
            inner.innerHTML = rows.map(renderExpenseRow).join('');
            wireExpenseRows(detailRow);
        } catch (err) {
            inner.innerHTML = `<tr><td colspan="6" class="text-error text-xs text-center py-4">${escapeHtml(err.message)}</td></tr>`;
        }
    }

    async function loadLista() {
        const tbody = $('#fin-adm-lista');
        try {
            const r = await api('/admin/summaries' + currentFilters());
            const summaries = r.summaries || [];
            if (!summaries.length) {
                tbody.innerHTML = '<tr><td colspan="8" class="text-center text-sm opacity-50 py-8">Nenhum lote encontrado.</td></tr>';
                return;
            }

            let html = '';
            summaries.forEach(s => {
                const expanded = expandedSummaries.has(s.id);
                const markPaidBtn = s.status === 'open'
                    ? `<button type="button" class="btn btn-xs btn-success fin-adm-mark-paid" data-id="${s.id}" data-desc="${escapeHtml(s.description)}">Marcar pago</button>`
                    : '';
                html += `
                <tr class="fin-summary-row cursor-pointer hover:bg-base-200/50" data-summary-id="${s.id}">
                    <td><button type="button" class="btn btn-xs btn-ghost fin-toggle" data-id="${s.id}">${expanded ? '▼' : '▶'}</button></td>
                    <td class="font-medium">${escapeHtml(s.description)}</td>
                    <td class="whitespace-nowrap">${escapeHtml(s.user_name || s.user_email || ('#' + s.user_id))}</td>
                    <td>${summaryStatusBadge(s.status)}</td>
                    <td class="text-right text-green-600 font-medium">${money(s.total_payable)}</td>
                    <td class="text-right text-red-600">${money(s.total_rejected)}</td>
                    <td class="whitespace-nowrap">${dateBR(s.payment_date)}</td>
                    <td class="text-right whitespace-nowrap">
                        <div class="flex gap-1 justify-end">${markPaidBtn}</div>
                    </td>
                </tr>`;
                if (expanded) {
                    html += `
                <tr class="fin-detail" data-summary-id="${s.id}">
                    <td colspan="8" class="p-0">
                        <table class="table table-xs w-full">
                            <thead>
                                <tr class="text-xs opacity-60">
                                    <th>Data</th>
                                    <th class="text-right">Valor</th>
                                    <th>Categoria</th>
                                    <th>Estabelecimento</th>
                                    <th>Status</th>
                                    <th class="text-right">Ações</th>
                                </tr>
                            </thead>
                            <tbody class="fin-detail-inner"></tbody>
                        </table>
                    </td>
                </tr>`;
                }
            });
            tbody.innerHTML = html;

            tbody.querySelectorAll('.fin-toggle').forEach(btn => {
                btn.addEventListener('click', (ev) => {
                    ev.stopPropagation();
                    const id = btn.dataset.id;
                    if (expandedSummaries.has(id)) expandedSummaries.delete(id);
                    else expandedSummaries.add(id);
                    loadLista();
                });
            });

            tbody.querySelectorAll('.fin-summary-row').forEach(row => {
                row.addEventListener('click', (ev) => {
                    if (ev.target.closest('.fin-adm-mark-paid')) return;
                    const id = row.dataset.summaryId;
                    if (expandedSummaries.has(id)) expandedSummaries.delete(id);
                    else expandedSummaries.add(id);
                    loadLista();
                });
            });

            tbody.querySelectorAll('.fin-adm-mark-paid').forEach(btn => {
                btn.addEventListener('click', (ev) => {
                    ev.stopPropagation();
                    openPaidModal(btn.dataset.id, btn.dataset.desc);
                });
            });

            summaries.forEach(s => {
                if (expandedSummaries.has(s.id)) {
                    loadExpensesForSummary(s.id, tbody);
                }
            });
        } catch (err) {
            tbody.innerHTML = `<tr><td colspan="8" class="text-error text-sm text-center py-4">${escapeHtml(err.message)}</td></tr>`;
        }
    }

    async function approveExpense(id) {
        if (!confirm('Aprovar esta despesa?')) return;
        try {
            await api(`/admin/expenses/${id}/approve`, { method: 'POST' });
            showToast('Despesa aprovada.', 'success');
            refreshAll();
        } catch (err) {
            showToast(err.message, 'error');
        }
    }

    function rejectModal() { return $('#fin-adm-reject-modal'); }

    function openRejectModal(id) {
        $('#fin-adm-reject-id').value = id;
        $('#fin-adm-reject-reason').value = '';
        rejectModal().showModal();
    }

    async function confirmReject() {
        const id = $('#fin-adm-reject-id').value;
        const reason = ($('#fin-adm-reject-reason').value || '').trim();
        if (!reason) {
            showToast('Informe o motivo da reprovação.', 'warning');
            return;
        }
        const btn = $('#fin-adm-reject-confirm');
        btn.classList.add('loading');
        try {
            await api(`/admin/expenses/${id}/reject`, {
                method: 'POST',
                body: JSON.stringify({ rejection_reason: reason }),
            });
            rejectModal().close();
            showToast('Despesa reprovada.', 'success');
            refreshAll();
        } catch (err) {
            showToast(err.message, 'error');
        } finally {
            btn.classList.remove('loading');
        }
    }

    function paidModal() { return $('#fin-adm-paid-modal'); }

    function openPaidModal(id, desc) {
        $('#fin-adm-paid-id').value = id;
        $('#fin-adm-paid-date').value = new Date().toISOString().slice(0, 10);
        $('#fin-adm-paid-hint').textContent = `Concluir lote ${desc || ''}. Informe a data de pagamento.`;
        paidModal().showModal();
        openDatePicker($('#fin-adm-paid-date'));
    }

    async function confirmPaid() {
        const id = $('#fin-adm-paid-id').value;
        const paymentDate = $('#fin-adm-paid-date').value;
        if (!paymentDate) {
            showToast('Informe a data de pagamento.', 'warning');
            return;
        }
        const btn = $('#fin-adm-paid-confirm');
        btn.classList.add('loading');
        try {
            await api(`/admin/summaries/${id}/mark-paid`, {
                method: 'POST',
                body: JSON.stringify({ payment_date: paymentDate }),
            });
            paidModal().close();
            showToast('Lote marcado como pago.', 'success');
            refreshAll();
        } catch (err) {
            showToast(err.message, 'error');
        } finally {
            btn.classList.remove('loading');
        }
    }

    async function openReceipt(id) {
        try {
            const r = await api(`/expenses/${id}`);
            const receipts = (r.expense && r.expense.receipts) || [];
            if (!receipts.length) {
                showToast('Sem comprovante anexado.', 'warning');
                return;
            }
            window.open(receipts[0].download_url, '_blank');
        } catch (err) {
            showToast(err.message, 'error');
        }
    }

    function refreshAll() {
        loadSummary();
        loadLista();
    }

    function wireFilterAutoApply() {
        ['#fin-f-status', '#fin-f-user', '#fin-f-from', '#fin-f-to'].forEach(sel => {
            $(sel)?.addEventListener('change', refreshAll);
        });
    }

    document.addEventListener('DOMContentLoaded', () => {
        if (!$('#fin-gestao-app')) return;
        $('#fin-f-apply')?.addEventListener('click', refreshAll);
        $('#fin-f-clear')?.addEventListener('click', () => {
            $('#fin-f-status').value = '';
            $('#fin-f-user').value = '';
            $('#fin-f-from').value = '';
            $('#fin-f-to').value = '';
            refreshAll();
        });
        $('#fin-adm-reject-confirm')?.addEventListener('click', confirmReject);
        $('#fin-adm-reject-cancel')?.addEventListener('click', () => rejectModal().close());
        $('#fin-adm-paid-confirm')?.addEventListener('click', confirmPaid);
        $('#fin-adm-paid-cancel')?.addEventListener('click', () => paidModal().close());

        wireFilterAutoApply();
        wireDatePickers();
        loadFilters().then(refreshAll);
    });
})();
