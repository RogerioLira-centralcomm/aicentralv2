(function () {
    'use strict';

    const BASE = '/financeiro/api';

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
    function statusBadge(st) {
        const [label, cls] = STATUS_MAP[st] || [st, 'badge-ghost'];
        return `<span class="badge badge-sm ${cls}">${label}</span>`;
    }
    function showToast(msg, type) {
        if (typeof window.showToast === 'function') window.showToast(msg, type);
        else alert(msg);
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
        const cat = $('#fin-f-category').value;
        const from = $('#fin-f-from').value;
        const to = $('#fin-f-to').value;
        if (status) p.set('status', status);
        if (user) p.set('user_id', user);
        if (cat) p.set('category_id', cat);
        if (from) p.set('date_from', from);
        if (to) p.set('date_to', to);
        const qs = p.toString();
        return qs ? '?' + qs : '';
    }

    async function loadFilters() {
        try {
            const [uc, cc] = await Promise.all([api('/admin/users'), api('/categories')]);
            const uSel = $('#fin-f-user');
            uSel.innerHTML = '<option value="">Todos</option>' +
                (uc.users || []).map(u => `<option value="${u.id}">${escapeHtml(u.nome || u.email || ('#' + u.id))}</option>`).join('');
            const cSel = $('#fin-f-category');
            cSel.innerHTML = '<option value="">Todas</option>' +
                (cc.categories || []).map(c => `<option value="${c.id}">${escapeHtml(c.label)}</option>`).join('');
        } catch (err) {
            showToast(err.message, 'error');
        }
    }

    async function loadSummary() {
        try {
            const r = await api('/admin/summary' + currentFilters());
            const s = r.summary || {};
            $('#fin-adm-submitted').textContent = money(s.submitted_total);
            $('#fin-adm-submitted-q').textContent = (s.submitted_qtd || 0) + ' itens';
            $('#fin-adm-approved').textContent = money(s.approved_total);
            $('#fin-adm-approved-q').textContent = (s.approved_qtd || 0) + ' itens';
            $('#fin-adm-draft').textContent = money(s.draft_total);
            $('#fin-adm-draft-q').textContent = (s.draft_qtd || 0) + ' itens';
            $('#fin-adm-rejected').textContent = money(s.rejected_total);
            $('#fin-adm-rejected-q').textContent = (s.rejected_qtd || 0) + ' itens';
        } catch (err) {
            showToast(err.message, 'error');
        }
    }

    async function loadLista() {
        const tbody = $('#fin-adm-lista');
        try {
            const r = await api('/admin/expenses' + currentFilters());
            const rows = r.expenses || [];
            if (!rows.length) {
                tbody.innerHTML = '<tr><td colspan="8" class="text-center text-sm opacity-50 py-8">Nenhum reembolso encontrado.</td></tr>';
                return;
            }
            tbody.innerHTML = rows.map(e => {
                const rejectedNote = e.status === 'rejected' && e.rejection_reason
                    ? `<div class="text-[11px] text-error mt-0.5">Motivo: ${escapeHtml(e.rejection_reason)}</div>` : '';
                const reviewActions = e.status === 'submitted'
                    ? `<button type="button" class="btn btn-xs btn-success fin-adm-approve" data-id="${e.id}">Aprovar</button>
                       <button type="button" class="btn btn-xs btn-error btn-outline fin-adm-reject" data-id="${e.id}">Reprovar</button>`
                    : '';
                return `
                <tr data-id="${e.id}">
                    <td class="whitespace-nowrap">${dateBR(e.expense_date)}</td>
                    <td class="text-right font-medium whitespace-nowrap">${money(e.total_amount)}</td>
                    <td class="whitespace-nowrap">${escapeHtml(e.user_name || e.user_email || ('#' + e.user_id))}</td>
                    <td class="whitespace-nowrap">${escapeHtml(e.category_label || '—')}</td>
                    <td class="min-w-[8rem]">${escapeHtml(e.merchant_name || '—')}</td>
                    <td class="whitespace-nowrap">${statusBadge(e.status)}${rejectedNote}</td>
                    <td class="text-right whitespace-nowrap">
                        <div class="flex gap-1 justify-end flex-wrap">
                            ${reviewActions}
                            <button type="button" class="btn btn-xs btn-ghost fin-adm-receipt" data-id="${e.id}" title="Ver comprovante">📎</button>
                        </div>
                    </td>
                </tr>`;
            }).join('');

            tbody.querySelectorAll('.fin-adm-receipt').forEach(btn => {
                btn.addEventListener('click', () => openReceipt(btn.dataset.id));
            });
            tbody.querySelectorAll('.fin-adm-approve').forEach(btn => {
                btn.addEventListener('click', () => approveExpense(btn.dataset.id));
            });
            tbody.querySelectorAll('.fin-adm-reject').forEach(btn => {
                btn.addEventListener('click', () => openRejectModal(btn.dataset.id));
            });
        } catch (err) {
            tbody.innerHTML = `<tr><td colspan="8" class="text-error text-sm text-center py-4">${escapeHtml(err.message)}</td></tr>`;
        }
    }

    async function approveExpense(id) {
        if (!confirm('Aprovar este reembolso?')) return;
        try {
            await api(`/admin/expenses/${id}/approve`, { method: 'POST' });
            showToast('Reembolso aprovado.', 'success');
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
            showToast('Reembolso reprovado.', 'success');
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
        ['#fin-f-status', '#fin-f-user', '#fin-f-category', '#fin-f-from', '#fin-f-to'].forEach(sel => {
            $(sel)?.addEventListener('change', refreshAll);
        });
    }

    document.addEventListener('DOMContentLoaded', () => {
        if (!$('#fin-gestao-app')) return;
        $('#fin-f-apply')?.addEventListener('click', refreshAll);
        $('#fin-f-clear')?.addEventListener('click', () => {
            $('#fin-f-status').value = '';
            $('#fin-f-user').value = '';
            $('#fin-f-category').value = '';
            $('#fin-f-from').value = '';
            $('#fin-f-to').value = '';
            refreshAll();
        });
        $('#fin-adm-reject-confirm')?.addEventListener('click', confirmReject);
        $('#fin-adm-reject-cancel')?.addEventListener('click', () => rejectModal().close());

        wireFilterAutoApply();
        loadFilters().then(refreshAll);
    });
})();
