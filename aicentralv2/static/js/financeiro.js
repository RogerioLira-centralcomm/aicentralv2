(function () {
    'use strict';

    const BASE = '/financeiro/api';
    const EDITABLE = ['draft', 'rejected', 'extracted', 'extraction_failed'];
    const DELETABLE = EDITABLE;
    const MAX_IMPORT = 20;

    // pending file for manual entry (no expense id yet)
    let pendingManualFile = null;
    let selectedIds = new Set();

    function $(sel, root) { return (root || document).querySelector(sel); }

    function money(v) {
        const n = Number(v) || 0;
        return n.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
    }

    function dateBR(iso) {
        if (!iso) return '—';
        const m = String(iso).match(/^(\d{4})-(\d{2})-(\d{2})/);
        if (m) return `${m[3]}/${m[2]}/${m[1]}`;
        return iso;
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

    function escapeHtml(s) {
        return String(s || '')
            .replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
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

    // ---------- money / date helpers ----------
    function parseMoneyBR(str) {
        if (str == null || str === '') return null;
        const digits = String(str).replace(/[^\d]/g, '');
        if (!digits) return null;
        return parseInt(digits, 10) / 100;
    }
    function formatMoneyInput(input) {
        const digits = String(input.value || '').replace(/[^\d]/g, '');
        if (!digits) { input.value = ''; return; }
        const num = parseInt(digits, 10) / 100;
        input.value = 'R$ ' + num.toLocaleString('pt-BR', {
            minimumFractionDigits: 2, maximumFractionDigits: 2,
        });
    }
    function setMoneyValue(input, num) {
        if (num == null || num === '') { input.value = ''; return; }
        input.value = 'R$ ' + Number(num).toLocaleString('pt-BR', {
            minimumFractionDigits: 2, maximumFractionDigits: 2,
        });
    }
    function openDatePicker(el) {
        if (!el) return;
        try { if (typeof el.showPicker === 'function') el.showPicker(); }
        catch (_) { el.focus(); }
    }

    // ---------- summary + list ----------
    async function loadSummary() {
        const r = await api('/my/summary');
        const s = r.summary || {};
        $('#fin-sum-draft').textContent = money(s.draft_total);
        $('#fin-sum-submitted').textContent = money(s.submitted_total);
        $('#fin-sum-approved').textContent = money(s.approved_total);
        $('#fin-sum-rejected').textContent = money(s.rejected_total);
    }

    function canSelectRow(e) {
        return EDITABLE.includes(e.status) && e.expense_date && Number(e.total_amount) > 0;
    }

    function updateBulkSubmitButton() {
        const btn = $('#fin-btn-bulk-submit');
        if (!btn) return;
        const n = selectedIds.size;
        btn.textContent = `Enviar selecionados (${n})`;
        btn.disabled = n === 0;
    }

    function syncSelectAllCheckbox() {
        const master = $('#fin-select-all');
        if (!master) return;
        const boxes = document.querySelectorAll('.fin-row-select');
        const checked = document.querySelectorAll('.fin-row-select:checked');
        master.indeterminate = checked.length > 0 && checked.length < boxes.length;
        master.checked = boxes.length > 0 && checked.length === boxes.length;
    }

    function assocText(e) {
        if (!e.association_type) return '—';
        return e.association_type + (e.association_label ? ': ' + escapeHtml(e.association_label) : '');
    }

    async function loadLista() {
        const status = $('#fin-filter-status')?.value || '';
        const qs = status ? `?status=${encodeURIComponent(status)}` : '';
        const tbody = $('#fin-lista');
        selectedIds.clear();
        updateBulkSubmitButton();
        try {
            const r = await api('/expenses' + qs);
            const rows = r.expenses || [];
            if (!rows.length) {
                tbody.innerHTML = '<tr><td colspan="8" class="text-center text-sm opacity-50 py-8">Nenhuma despesa ainda. Importe um comprovante acima.</td></tr>';
                syncSelectAllCheckbox();
                return;
            }
            tbody.innerHTML = rows.map(e => {
                const canEdit = EDITABLE.includes(e.status);
                const canDelete = DELETABLE.includes(e.status);
                const canSubmit = EDITABLE.includes(e.status);
                const selectable = canSelectRow(e);
                const rejected = e.status === 'rejected' && e.rejection_reason
                    ? `<div class="text-[11px] text-error mt-0.5">Motivo: ${escapeHtml(e.rejection_reason)}</div>` : '';
                const review = e.needs_review && canEdit
                    ? '<span class="badge badge-xs badge-warning ml-1">revisar</span>' : '';
                return `
                <tr data-id="${e.id}">
                    <td>${selectable
                        ? `<input type="checkbox" class="checkbox checkbox-xs fin-row-select" data-id="${e.id}" />`
                        : ''}</td>
                    <td class="whitespace-nowrap">${dateBR(e.expense_date)}</td>
                    <td class="min-w-[8rem]">${escapeHtml(e.merchant_name || '—')}${rejected}</td>
                    <td class="text-right font-medium whitespace-nowrap">${money(e.total_amount)}</td>
                    <td class="whitespace-nowrap">${escapeHtml(e.category_label || '—')}</td>
                    <td class="whitespace-nowrap text-xs opacity-80">${assocText(e)}</td>
                    <td class="whitespace-nowrap">${statusBadge(e.status)}${review}</td>
                    <td class="text-right whitespace-nowrap">
                        <div class="flex gap-1 justify-end">
                            ${canEdit ? `<button type="button" class="btn btn-xs btn-ghost fin-edit" data-id="${e.id}" title="Editar">✏️</button>` : ''}
                            <button type="button" class="btn btn-xs btn-ghost fin-receipt" data-id="${e.id}" title="Ver comprovante">📎</button>
                            ${canSubmit ? `<button type="button" class="btn btn-xs btn-primary fin-submit" data-id="${e.id}">Enviar</button>` : ''}
                            ${canDelete ? `<button type="button" class="btn btn-xs btn-ghost text-error fin-delete" data-id="${e.id}" title="Excluir">🗑️</button>` : ''}
                        </div>
                    </td>
                </tr>`;
            }).join('');

            tbody.querySelectorAll('.fin-row-select').forEach(cb => {
                cb.addEventListener('change', () => {
                    if (cb.checked) selectedIds.add(cb.dataset.id);
                    else selectedIds.delete(cb.dataset.id);
                    updateBulkSubmitButton();
                    syncSelectAllCheckbox();
                });
            });
            tbody.querySelectorAll('.fin-edit').forEach(btn => {
                btn.addEventListener('click', () => openEditModal(btn.dataset.id));
            });
            tbody.querySelectorAll('.fin-submit').forEach(btn => {
                btn.addEventListener('click', () => submitExpense(btn.dataset.id));
            });
            tbody.querySelectorAll('.fin-delete').forEach(btn => {
                btn.addEventListener('click', () => deleteExpense(btn.dataset.id));
            });
            tbody.querySelectorAll('.fin-receipt').forEach(btn => {
                btn.addEventListener('click', () => openReceipt(btn.dataset.id));
            });
            syncSelectAllCheckbox();
        } catch (err) {
            tbody.innerHTML = `<tr><td colspan="8" class="text-error text-sm text-center py-4">${escapeHtml(err.message)}</td></tr>`;
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

    async function submitBulk(ids) {
        if (!ids.length) return;
        if (!confirm(`Enviar ${ids.length} reembolso(s) ao financeiro?`)) return;
        const btn = $('#fin-btn-bulk-submit');
        btn?.classList.add('loading');
        try {
            const r = await api('/expenses/submit-bulk', {
                method: 'POST',
                body: JSON.stringify({ expense_ids: ids }),
            });
            const ok = (r.submitted || []).length;
            const fail = (r.failed || []).length;
            if (fail === 0) {
                showToast(`${ok} reembolso(s) enviado(s).`, 'success');
            } else if (ok === 0) {
                const msg = r.failed.map(f => f.error).join('; ');
                showToast(`Nenhum enviado: ${msg}`, 'error');
            } else {
                showToast(`${ok} enviado(s), ${fail} com erro.`, 'warning');
            }
            selectedIds.clear();
            refreshAll();
        } catch (err) {
            showToast(err.message, 'error');
        } finally {
            btn?.classList.remove('loading');
        }
    }

    async function submitExpense(id) {
        try {
            await api(`/expenses/${id}/submit`, { method: 'POST' });
            showToast('Despesa enviada ao financeiro.', 'success');
            refreshAll();
        } catch (err) {
            showToast(err.message, 'error');
        }
    }

    async function deleteExpense(id) {
        if (!confirm('Excluir esta despesa? Essa ação não pode ser desfeita.')) return;
        try {
            await api(`/expenses/${id}`, { method: 'DELETE' });
            showToast('Despesa excluída.', 'success');
            refreshAll();
        } catch (err) {
            showToast(err.message, 'error');
        }
    }

    // ---------- categorias / clientes ----------
    async function loadCategories() {
        const r = await api('/categories');
        const sel = $('#fin-category');
        if (!sel) return;
        sel.innerHTML = '<option value="">Selecione…</option>' +
            (r.categories || []).map(c => `<option value="${c.id}">${escapeHtml(c.label)}</option>`).join('');
    }
    async function loadClients() {
        const r = await api('/clients');
        const sel = $('#fin-client');
        if (!sel) return;
        sel.innerHTML = '<option value="">—</option>' +
            (r.clients || []).map(c =>
                `<option value="${c.id_cliente}">${escapeHtml(c.nome_fantasia || c.razao_social || '')}</option>`
            ).join('');
    }

    // ---------- modal ----------
    function modal() { return $('#fin-edit-modal'); }

    function fillForm(e) {
        e = e || {};
        $('#fin-edit-id').value = e.id || '';
        $('#fin-date').value = e.expense_date ? String(e.expense_date).slice(0, 10) : '';
        $('#fin-merchant').value = e.merchant_name || '';
        setMoneyValue($('#fin-total'), e.total_amount);
        $('#fin-category').value = e.category_id || '';
        $('#fin-assoc-type').value = e.association_type || '';
        $('#fin-assoc-label').value = e.association_label || '';
        $('#fin-client').value = e.client_id || '';
        $('#fin-notes').value = e.notes || '';
        $('#fin-client-wrap').classList.toggle('hidden', e.association_type !== 'cliente');
        renderModalReceipts(e.receipts || []);
    }

    function renderModalReceipts(receipts) {
        const box = $('#fin-receipts-list');
        if (!receipts.length) { box.innerHTML = '<span class="opacity-50">Nenhum comprovante anexado.</span>'; return; }
        box.innerHTML = receipts.map(r =>
            `<a href="${r.download_url}" target="_blank" class="link link-primary block">📎 ${escapeHtml(r.file_name || 'comprovante')}</a>`
        ).join('');
    }

    function collectForm() {
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

    async function openEditModal(id) {
        pendingManualFile = null;
        $('#fin-manual-file-name').textContent = '';
        $('#fin-ai-banner').classList.add('hidden');
        try {
            const r = await api(`/expenses/${id}`);
            const e = r.expense;
            $('#fin-modal-title').textContent = 'Editar despesa';
            $('#fin-modal-hint').textContent = 'Revise os dados e envie ao financeiro.';
            if (e.status === 'extracted' || e.needs_review) {
                $('#fin-ai-banner').classList.remove('hidden');
            }
            fillForm(e);
            modal().showModal();
        } catch (err) {
            showToast(err.message, 'error');
        }
    }

    function openManualModal() {
        pendingManualFile = null;
        $('#fin-manual-file-name').textContent = '';
        $('#fin-ai-banner').classList.add('hidden');
        $('#fin-modal-title').textContent = 'Lançar despesa';
        $('#fin-modal-hint').textContent = 'Preencha os dados e anexe o comprovante.';
        fillForm({});
        modal().showModal();
    }

    // opens modal directly from an imported expense object (skips extra GET)
    function openModalForImported(e, aiOk) {
        pendingManualFile = null;
        $('#fin-manual-file-name').textContent = '';
        $('#fin-modal-title').textContent = 'Conferir importação';
        $('#fin-modal-hint').textContent = aiOk
            ? 'A IA leu o comprovante. Confira data e valor antes de enviar.'
            : 'Não foi possível ler automaticamente. Preencha os dados manualmente.';
        $('#fin-ai-banner').classList.toggle('hidden', !aiOk);
        fillForm(e);
        modal().showModal();
    }

    async function saveModal(submitAfter) {
        const payload = collectForm();
        if (!payload.expense_date || payload.total_amount == null || payload.total_amount <= 0) {
            showToast('Data e valor total são obrigatórios.', 'warning');
            return;
        }
        let id = $('#fin-edit-id').value || null;
        const btnDraft = $('#fin-btn-save-draft');
        const btnSubmit = $('#fin-btn-save-submit');
        btnDraft.classList.add('loading');
        btnSubmit.classList.add('loading');
        try {
            if (id) {
                await api(`/expenses/${id}`, { method: 'PATCH', body: JSON.stringify(payload) });
            } else {
                const r = await api('/expenses', { method: 'POST', body: JSON.stringify(payload) });
                id = r.expense.id;
            }
            if (pendingManualFile) {
                const fd = new FormData();
                fd.append('file', pendingManualFile);
                await api(`/expenses/${id}/receipts`, { method: 'POST', body: fd });
                pendingManualFile = null;
            }
            if (submitAfter) {
                await api(`/expenses/${id}/submit`, { method: 'POST' });
                showToast('Despesa enviada ao financeiro.', 'success');
            } else {
                showToast('Rascunho salvo.', 'success');
            }
            modal().close();
            refreshAll();
        } catch (err) {
            showToast(err.message, 'error');
        } finally {
            btnDraft.classList.remove('loading');
            btnSubmit.classList.remove('loading');
        }
    }

    // ---------- importação ----------
    const ALLOWED_EXT = ['.jpg', '.jpeg', '.png', '.webp', '.heic', '.pdf'];

    function filterValidFiles(fileList) {
        return Array.from(fileList || []).filter(f => {
            const name = (f.name || '').toLowerCase();
            return ALLOWED_EXT.some(ext => name.endsWith(ext));
        });
    }

    async function importFiles(fileList) {
        const files = filterValidFiles(fileList);
        if (!files.length) {
            showToast('Nenhum arquivo válido (use imagem ou PDF).', 'warning');
            return;
        }
        if (files.length > MAX_IMPORT) {
            showToast(`Máximo de ${MAX_IMPORT} arquivos por vez. Selecione menos arquivos.`, 'warning');
            return;
        }

        const statusBox = $('#fin-import-status');
        const progress = $('#fin-import-progress');
        statusBox.classList.remove('hidden');
        $('#fin-import-status-text').textContent =
            files.length === 1
                ? 'Importando 1 comprovante…'
                : `Importando ${files.length} comprovantes…`;
        if (progress) {
            progress.removeAttribute('value');
            progress.classList.add('progress-indeterminate');
        }

        try {
            const fd = new FormData();
            files.forEach(f => fd.append('file', f));
            const r = await api('/expenses/import-bulk', { method: 'POST', body: fd });
            const created = r.created || 0;
            const failed = (r.failed || []).length;
            if (failed === 0) {
                showToast(`${created} comprovante(s) importado(s). Revise na lista e envie.`, 'success');
            } else if (created === 0) {
                showToast('Nenhum comprovante importado.', 'error');
            } else {
                showToast(`${created} de ${r.total} importado(s). ${failed} falhou(aram).`, 'warning');
            }
            refreshAll();
        } catch (err) {
            showToast(err.message, 'error');
        } finally {
            statusBox.classList.add('hidden');
            if (progress) progress.classList.remove('progress-indeterminate');
            $('#fin-import-file').value = '';
        }
    }

    function refreshAll() {
        loadSummary();
        loadLista();
    }

    document.addEventListener('DOMContentLoaded', () => {
        if (!$('#fin-reembolsos-app')) return;

        // dropzone de importação
        const drop = $('#fin-dropzone');
        const importInput = $('#fin-import-file');
        drop?.addEventListener('click', () => importInput?.click());
        drop?.addEventListener('dragover', (e) => { e.preventDefault(); drop.classList.add('dragover'); });
        drop?.addEventListener('dragleave', () => drop.classList.remove('dragover'));
        drop?.addEventListener('drop', (e) => {
            e.preventDefault();
            drop.classList.remove('dragover');
            if (e.dataTransfer.files?.length) importFiles(e.dataTransfer.files);
        });
        importInput?.addEventListener('change', () => {
            if (importInput.files?.length) importFiles(importInput.files);
        });

        $('#fin-select-all')?.addEventListener('change', (e) => {
            const checked = e.target.checked;
            document.querySelectorAll('.fin-row-select').forEach(cb => {
                cb.checked = checked;
                if (checked) selectedIds.add(cb.dataset.id);
                else selectedIds.delete(cb.dataset.id);
            });
            updateBulkSubmitButton();
            syncSelectAllCheckbox();
        });

        $('#fin-btn-bulk-submit')?.addEventListener('click', () => {
            submitBulk(Array.from(selectedIds));
        });

        // lançar manualmente
        $('#fin-btn-manual')?.addEventListener('click', openManualModal);

        // modal: dropzone de anexo
        const mDrop = $('#fin-manual-dropzone');
        const mFile = $('#fin-manual-file');
        mDrop?.addEventListener('click', () => mFile?.click());
        mDrop?.addEventListener('dragover', (e) => { e.preventDefault(); mDrop.classList.add('border-primary'); });
        mDrop?.addEventListener('dragleave', () => mDrop.classList.remove('border-primary'));
        mDrop?.addEventListener('drop', async (e) => {
            e.preventDefault();
            mDrop.classList.remove('border-primary');
            const f = e.dataTransfer.files?.[0];
            if (f) await attachInModal(f);
        });
        mFile?.addEventListener('change', async () => {
            const f = mFile.files?.[0];
            if (f) await attachInModal(f);
        });

        // associação -> cliente
        $('#fin-assoc-type')?.addEventListener('change', () => {
            const isCli = $('#fin-assoc-type').value === 'cliente';
            $('#fin-client-wrap').classList.toggle('hidden', !isCli);
        });

        // data / valor
        const dateEl = $('#fin-date');
        dateEl?.addEventListener('click', () => openDatePicker(dateEl));
        dateEl?.addEventListener('focus', () => openDatePicker(dateEl));
        const totalEl = $('#fin-total');
        totalEl?.addEventListener('input', () => formatMoneyInput(totalEl));

        // ações do modal
        $('#fin-btn-save-draft')?.addEventListener('click', () => saveModal(false));
        $('#fin-btn-save-submit')?.addEventListener('click', () => saveModal(true));

        // filtros
        $('#fin-btn-refresh')?.addEventListener('click', refreshAll);
        $('#fin-filter-status')?.addEventListener('change', loadLista);

        loadCategories();
        loadClients();
        refreshAll();
    });

    // anexa comprovante dentro do modal: se já existe expense, sobe na hora; senão guarda
    async function attachInModal(file) {
        const id = $('#fin-edit-id').value || null;
        $('#fin-manual-file-name').textContent = file.name;
        if (id) {
            try {
                const fd = new FormData();
                fd.append('file', file);
                const r = await api(`/expenses/${id}/receipts`, { method: 'POST', body: fd });
                showToast('Comprovante anexado.', 'success');
                const cur = await api(`/expenses/${id}`);
                renderModalReceipts(cur.expense.receipts || []);
            } catch (err) {
                showToast(err.message, 'error');
            }
        } else {
            pendingManualFile = file;
        }
    }
})();
