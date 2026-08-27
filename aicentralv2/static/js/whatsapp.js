(function () {
    'use strict';

    const API = '/whatsapp/api';
    const POLL_MS = 5000;

    let conversasCache = [];
    let conversaSelecionadaId = null;
    let chatTab = 'todas';
    let chatBusca = '';
    let pollTimer = null;

    const $ = (sel, root = document) => root.querySelector(sel);
    const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

    function escapeHtml(str) {
        return String(str ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function showToast(msg, type) {
        if (typeof window.showToast === 'function') {
            window.showToast(msg, type);
            return;
        }
        if (type === 'error') console.error(msg);
        else console.log(msg);
    }

    async function api(path, opts = {}) {
        const res = await fetch(`${API}${path}`, {
            headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) },
            credentials: 'same-origin',
            ...opts,
        });
        let data = {};
        try {
            data = await res.json();
        } catch (_) {
            data = {};
        }
        if (!res.ok || data.success === false) {
            throw new Error(data.error || `Erro HTTP ${res.status}`);
        }
        return data;
    }

    async function apiUpload(path, formData) {
        const res = await fetch(`${API}${path}`, {
            method: 'POST',
            body: formData,
            credentials: 'same-origin',
        });
        let data = {};
        try {
            data = await res.json();
        } catch (_) {
            data = {};
        }
        if (!res.ok || data.success === false) {
            throw new Error(data.error || `Erro HTTP ${res.status}`);
        }
        return data;
    }

    function setComposeEnabled(enabled) {
        const input = $('#wa-chat-input');
        const enviar = $('#wa-chat-enviar');
        const audioBtn = $('#wa-chat-audio');
        if (input) input.disabled = !enabled;
        if (enviar) enviar.disabled = !enabled;
        if (audioBtn) audioBtn.disabled = !enabled;
    }

    function showEmpty(container, text) {
        if (!container) return;
        container.innerHTML = `<div class="wa-empty-state">${escapeHtml(text)}</div>`;
    }

    function showSpinner(container) {
        if (!container) return;
        container.innerHTML = '<div class="wa-spinner"></div>';
    }

    function formatHora(dateStr) {
        if (!dateStr) return '';
        return new Date(dateStr).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
    }

    function formatTelefone(tel) {
        const d = String(tel || '').replace(/\D/g, '');
        if (d.length === 13 && d.startsWith('55')) {
            return `+${d.slice(0, 2)} (${d.slice(2, 4)}) ${d.slice(4, 9)}-${d.slice(9)}`;
        }
        if (d.length === 11) {
            return `(${d.slice(0, 2)}) ${d.slice(2, 7)}-${d.slice(7)}`;
        }
        return tel || '—';
    }

    function pararPolling() {
        if (pollTimer) {
            clearInterval(pollTimer);
            pollTimer = null;
        }
    }

    function iniciarPolling() {
        pararPolling();
        if (!conversaSelecionadaId) return;
        pollTimer = setInterval(() => {
            carregarMensagens(conversaSelecionadaId, { silent: true });
            carregarConversas({ silent: true });
        }, POLL_MS);
    }

    function atualizarContadores() {
        const todas = conversasCache.length;
        const naoLidas = conversasCache.filter(c => Number(c.unread_count) > 0).length;
        const elTodas = $('#wa-chat-count-todas');
        const elNaoLidas = $('#wa-chat-count-nao-lidas');
        if (elTodas) elTodas.textContent = String(todas);
        if (elNaoLidas) elNaoLidas.textContent = String(naoLidas);
    }

    function renderConversas() {
        const container = $('#wa-conversas-lista');
        if (!container) return;

        const termo = chatBusca.trim().toLowerCase();
        let conversas = conversasCache.filter(c => {
            if (chatTab === 'nao_lidas' && !(Number(c.unread_count) > 0)) return false;
            if (!termo) return true;
            return [c.nome_contato, c.telefone, c.ultimo_preview].some(v =>
                String(v || '').toLowerCase().includes(termo)
            );
        });

        atualizarContadores();

        if (!conversas.length) {
            showEmpty(container, conversasCache.length ? 'Nenhuma conversa encontrada.' : 'Nenhuma conversa ainda. Clique em Nova mensagem.');
            return;
        }

        container.innerHTML = conversas.map(c => {
            const ativo = String(c.id) === String(conversaSelecionadaId);
            const nome = c.nome_contato || formatTelefone(c.telefone);
            const hora = formatHora(c.ultimo_evento_em);
            return `
                <button type="button" class="wa-conversa ${ativo ? 'wa-conversa-active' : ''}" data-id="${c.id}">
                    <div class="wa-avatar"><span>WA</span></div>
                    <div class="wa-conversa-info">
                        <div class="wa-conversa-top">
                            <span>${escapeHtml(nome)}</span>
                            <small>${escapeHtml(hora)}</small>
                        </div>
                        <div class="wa-conversa-preview">${escapeHtml(c.ultimo_preview || 'Sem mensagens ainda.')}</div>
                    </div>
                    ${Number(c.unread_count) > 0 ? `<span class="wa-unread">${c.unread_count}</span>` : ''}
                </button>
            `;
        }).join('');

        $$('.wa-conversa', container).forEach(btn => {
            btn.addEventListener('click', () => selecionarConversa(parseInt(btn.dataset.id, 10)));
        });
    }

    async function carregarConversas(opts = {}) {
        const container = $('#wa-conversas-lista');
        if (!opts.silent && container) showSpinner(container);
        try {
            const qs = new URLSearchParams();
            if (chatTab) qs.set('tab', chatTab);
            if (chatBusca.trim()) qs.set('busca', chatBusca.trim());
            const data = await api(`/conversas?${qs.toString()}`);
            conversasCache = data.conversas || [];
            renderConversas();
        } catch (e) {
            if (!opts.silent && container) showEmpty(container, 'Erro ao carregar conversas.');
            console.error(e);
        }
    }

    function atualizarHeaderConversa(conversa) {
        const card = $('#wa-chat-contact');
        const empty = $('#wa-chat-header-empty');
        const input = $('#wa-chat-input');
        const enviar = $('#wa-chat-enviar');
        if (!conversa) {
            card?.classList.add('hidden');
            empty?.classList.remove('hidden');
            if (input) input.value = '';
            setComposeEnabled(false);
            return;
        }
        empty?.classList.add('hidden');
        card?.classList.remove('hidden');
        if (card) {
            const nome = conversa.nome_contato || formatTelefone(conversa.telefone);
            card.innerHTML = `
                <div class="wa-avatar"><span>WA</span></div>
                <div>
                    <div class="wa-chat-contact-name">${escapeHtml(nome)}</div>
                    <div class="wa-chat-contact-tel">${escapeHtml(formatTelefone(conversa.telefone))}</div>
                </div>
            `;
        }
        setComposeEnabled(true);
    }

    function normalizarStatusProvider(s) {
        const v = String(s || '').trim().toLowerCase();
        if (v === '4' || v === 'read') return 'read';
        if (v === '3' || v === 'delivered') return 'delivered';
        if (v === '2' || v === 'sent' || v === 'in_progress') return 'sent';
        if (v === '1' || v === 'pending') return 'pending';
        if (v === '0' || v === 'error' || v === 'failed') return 'error';
        return v;
    }

    function metaStatusMsg(m) {
        if (m.direcao !== 'outbound') return '';
        if (m.status === 'erro') return '<span class="wa-msg-status wa-msg-status-erro" title="Falha">!</span>';
        const st = normalizarStatusProvider(m.provider_status);
        if (st === 'read') {
            return '<span class="wa-msg-status wa-msg-status-read" title="Lida">✓✓</span>';
        }
        if (st === 'delivered') {
            return '<span class="wa-msg-status wa-msg-status-delivered" title="Entregue">✓✓</span>';
        }
        return '<span class="wa-msg-status" title="Enviada">✓</span>';
    }

    function agruparMensagens(mensagens) {
        const grupos = [];
        let atual = null;
        for (const m of mensagens) {
            const dir = m.direcao === 'inbound' ? 'in' : 'out';
            const ts = m.created_at ? new Date(m.created_at).getTime() : 0;
            const quebra = !atual || atual.dir !== dir ||
                (ts && atual.lastTs && Math.abs(ts - atual.lastTs) > 5 * 60 * 1000);
            if (quebra) {
                atual = { dir, items: [m], lastTs: ts };
                grupos.push(atual);
            } else {
                atual.items.push(m);
                atual.lastTs = ts;
            }
        }
        return grupos;
    }

    function posicaoBolha(idx, total) {
        if (total === 1) return 'single';
        if (idx === 0) return 'first';
        if (idx === total - 1) return 'last';
        return 'middle';
    }

    function renderConteudoMsg(m) {
        const url = m.media_url;
        const type = m.media_type;
        const caption = m.texto && !/^\[(GIF|Imagem|Vídeo|Áudio de voz|Áudio|Documento|Sticker|Mídia)\]$/.test(m.texto)
            ? m.texto
            : '';

        if (url && type === 'gif') {
            const isImageGif = /\.(gif|webp)(\?|$)/i.test(url);
            if (isImageGif) {
                const media = `<img class="wa-msg-media wa-msg-gif" src="${escapeHtml(url)}" alt="" loading="lazy">`;
                return caption
                    ? `${media}<span class="wa-msg-text wa-msg-caption">${escapeHtml(caption)}</span>`
                    : media;
            }
            const attrs = 'class="wa-msg-media wa-msg-gif" autoplay loop muted playsinline';
            const media = `<video ${attrs} src="${escapeHtml(url)}"></video>`;
            return caption
                ? `${media}<span class="wa-msg-text wa-msg-caption">${escapeHtml(caption)}</span>`
                : media;
        }
        if (url && type === 'video') {
            const media = `<video class="wa-msg-media" controls playsinline src="${escapeHtml(url)}"></video>`;
            return caption
                ? `${media}<span class="wa-msg-text wa-msg-caption">${escapeHtml(caption)}</span>`
                : media;
        }
        if (url && type === 'image') {
            const media = `<img class="wa-msg-media" src="${escapeHtml(url)}" alt="" loading="lazy">`;
            return caption
                ? `${media}<span class="wa-msg-text wa-msg-caption">${escapeHtml(caption)}</span>`
                : media;
        }
        if (url && type === 'sticker') {
            return `<img class="wa-msg-media wa-msg-sticker" src="${escapeHtml(url)}" alt="" loading="lazy">`;
        }
        if (url && type === 'audio') {
            const dur = m.media_seconds ? `<span class="wa-audio-dur">${Math.round(Number(m.media_seconds))}s</span>` : '';
            const label = m.media_ptt ? 'Áudio de voz' : 'Áudio';
            return `
                <div class="wa-audio-wrap">
                    <span class="wa-audio-label">${escapeHtml(label)}</span>
                    <audio class="wa-msg-audio" controls preload="metadata" src="${escapeHtml(url)}"></audio>
                    ${dur}
                </div>
            `;
        }
        if (url && type === 'document') {
            const label = escapeHtml(m.texto || '[Documento]');
            return `<a class="wa-msg-media-link" href="${escapeHtml(url)}" target="_blank" rel="noopener">${label}</a>`;
        }
        if (type === 'audio' && !url) {
            return `<span class="wa-msg-text wa-msg-media-pending">${escapeHtml(m.texto || '[Áudio]')} <small>(processando…)</small></span>`;
        }
        return `<span class="wa-msg-text">${escapeHtml(m.texto)}</span>`;
    }

    function renderMensagens(mensagens) {
        const container = $('#wa-chat-mensagens');
        if (!container) return;
        if (!mensagens.length) {
            showEmpty(container, 'Nenhuma mensagem ainda. Envie a primeira!');
            return;
        }
        const grupos = agruparMensagens(mensagens);
        container.innerHTML = grupos.map(g => {
            const dirClass = g.dir === 'in' ? 'wa-msg-group-in' : 'wa-msg-group-out';
            const bubbleClass = g.dir === 'in' ? 'wa-msg-bubble-in' : 'wa-msg-bubble-out';
            const bubbles = g.items.map((m, i) => {
                const pos = posicaoBolha(i, g.items.length);
                const hora = formatHora(m.created_at);
                const meta = g.dir === 'out' ? metaStatusMsg(m) : '';
                return `
                    <div class="wa-msg-bubble ${bubbleClass} wa-msg-bubble-${pos}">
                        ${renderConteudoMsg(m)}
                        <span class="wa-msg-meta">${hora}${meta}</span>
                    </div>
                `;
            }).join('');
            return `<div class="wa-msg-group ${dirClass}">${bubbles}</div>`;
        }).join('');
        container.scrollTop = container.scrollHeight;
    }

    async function carregarMensagens(conversaId, opts = {}) {
        const container = $('#wa-chat-mensagens');
        if (!opts.silent && container) showSpinner(container);
        try {
            const data = await api(`/conversas/${conversaId}/mensagens`);
            renderMensagens(data.mensagens || []);
        } catch (e) {
            if (!opts.silent && container) showEmpty(container, 'Erro ao carregar mensagens.');
            console.error(e);
        }
    }

    function selecionarConversa(conversaId) {
        const conversa = conversasCache.find(x => String(x.id) === String(conversaId));
        if (!conversa) return;
        conversaSelecionadaId = conversaId;
        renderConversas();
        atualizarHeaderConversa(conversa);
        carregarMensagens(conversaId);
        iniciarPolling();
        api(`/conversas/${conversaId}/status`, {
            method: 'PATCH',
            body: JSON.stringify({ status: 'aberta', unread_count: 0 }),
        }).then(() => {
            const c = conversasCache.find(x => String(x.id) === String(conversaId));
            if (c) c.unread_count = 0;
            renderConversas();
        }).catch(() => {});
    }

    async function enviarAudio(file) {
        if (!file || !conversaSelecionadaId) return;
        setComposeEnabled(false);
        try {
            const form = new FormData();
            form.append('audio', file);
            const data = await apiUpload(`/conversas/${conversaSelecionadaId}/mensagens`, form);
            renderMensagens(data.mensagens || []);
            await carregarConversas({ silent: true });
        } catch (e) {
            showToast(e.message || 'Erro ao enviar áudio.', 'error');
            await carregarMensagens(conversaSelecionadaId, { silent: true });
        } finally {
            setComposeEnabled(true);
            const fileInput = $('#wa-chat-audio-file');
            if (fileInput) fileInput.value = '';
            $('#wa-chat-input')?.focus();
        }
    }

    async function enviarMensagem() {
        const input = $('#wa-chat-input');
        if (!input || !conversaSelecionadaId) return;
        const texto = input.value.trim();
        if (!texto) return;
        input.disabled = true;
        $('#wa-chat-enviar')?.setAttribute('disabled', 'disabled');
        try {
            const data = await api(`/conversas/${conversaSelecionadaId}/mensagens`, {
                method: 'POST',
                body: JSON.stringify({ texto }),
            });
            input.value = '';
            renderMensagens(data.mensagens || []);
            await carregarConversas({ silent: true });
        } catch (e) {
            showToast(e.message || 'Erro ao enviar mensagem.', 'error');
            await carregarMensagens(conversaSelecionadaId, { silent: true });
        } finally {
            input.disabled = false;
            $('#wa-chat-enviar')?.removeAttribute('disabled');
            input.focus();
        }
    }

    function abrirModalNova() {
        const modal = $('#wa-modal-nova');
        if (!modal) return;
        modal.classList.remove('hidden');
        const tel = $('#wa-nova-telefone');
        const nome = $('#wa-nova-nome');
        if (tel) { tel.value = ''; tel.focus(); }
        if (nome) nome.value = '';
    }

    function fecharModalNova() {
        $('#wa-modal-nova')?.classList.add('hidden');
    }

    async function confirmarNovaConversa() {
        const telefone = ($('#wa-nova-telefone')?.value || '').trim();
        const nome = ($('#wa-nova-nome')?.value || '').trim() || null;
        if (!telefone) {
            showToast('Informe o telefone.', 'error');
            return;
        }
        try {
            const data = await api('/conversas', {
                method: 'POST',
                body: JSON.stringify({ telefone, nome_contato: nome }),
            });
            fecharModalNova();
            await carregarConversas();
            if (data.id) selecionarConversa(data.id);
        } catch (e) {
            showToast(e.message || 'Erro ao criar conversa.', 'error');
        }
    }

    function bindEvents() {
        $('#wa-btn-nova-conversa')?.addEventListener('click', abrirModalNova);
        $('#wa-nova-confirmar')?.addEventListener('click', confirmarNovaConversa);
        $$('[data-close-modal]').forEach(el => el.addEventListener('click', fecharModalNova));

        $('#wa-chat-enviar')?.addEventListener('click', enviarMensagem);
        $('#wa-chat-audio')?.addEventListener('click', () => $('#wa-chat-audio-file')?.click());
        $('#wa-chat-audio-file')?.addEventListener('change', e => {
            const file = e.target.files && e.target.files[0];
            if (file) enviarAudio(file);
        });
        $('#wa-chat-input')?.addEventListener('keydown', e => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                enviarMensagem();
            }
        });

        $('#wa-chat-busca')?.addEventListener('input', e => {
            chatBusca = e.target.value || '';
            renderConversas();
        });

        $$('#wa-chat-tabs button').forEach(btn => {
            btn.addEventListener('click', () => {
                $$('#wa-chat-tabs button').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                chatTab = btn.dataset.chatTab || 'todas';
                carregarConversas();
            });
        });

        document.addEventListener('keydown', e => {
            if (e.key === 'Escape') fecharModalNova();
        });
    }

    document.addEventListener('DOMContentLoaded', () => {
        bindEvents();
        carregarConversas();
    });

    window.addEventListener('beforeunload', pararPolling);
})();
