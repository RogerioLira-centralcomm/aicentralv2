(() => {
    const money = (value) => {
        const num = Number(value || 0);
        return num.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
    };

    const escapeHtml = (value) => String(value == null ? '' : value).replace(/[&<>"']/g, (ch) => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;',
    }[ch]));

    function notify(host, message) {
        if (typeof window.showToast === 'function') {
            window.showToast(message, true);
            return;
        }
        let box = host.querySelector('[data-plano-erro]');
        if (!box) {
            box = document.createElement('p');
            box.className = 'cot-plano-aviso';
            box.setAttribute('data-plano-erro', '');
            host.prepend(box);
        }
        box.textContent = message;
    }

    async function postJson(url, body) {
        const response = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
            body: body ? JSON.stringify(body) : '{}',
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok || payload.success === false) {
            throw new Error(payload.message || 'Não foi possível atualizar o briefing.');
        }
        return payload;
    }

    function bind(root) {
        const host = root || document;
        host.querySelectorAll('[data-plano-root]').forEach((el) => {
            const id = el.getAttribute('data-cotacao-id');
            if (!id || el.getAttribute('data-plano-bound') === '1') return;
            el.setAttribute('data-plano-bound', '1');

            el.querySelectorAll('[data-plano-principal]').forEach((btn) => {
                btn.addEventListener('click', async (event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    const target = btn.getAttribute('data-plano-principal') || id;
                    try {
                        await postJson(`/api/cotacoes/${target}/plano/principal`);
                        window.location.reload();
                    } catch (error) {
                        notify(el, error.message);
                    }
                });
            });

            el.querySelectorAll('[data-plano-duplicar]').forEach((btn) => {
                btn.addEventListener('click', async (event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    try {
                        const payload = await postJson(`/api/cotacoes/${id}/duplicar`);
                        window.location.href = `/cotacoes/${payload.nova_cotacao_id}/abrir`;
                    } catch (error) {
                        notify(el, error.message);
                    }
                });
            });

            el.querySelectorAll('[data-plano-soltar]').forEach((btn) => {
                btn.addEventListener('click', async (event) => {
                    event.preventDefault();
                    if (!window.confirm('Soltar esta proposta deste briefing?')) return;
                    try {
                        await postJson(`/api/cotacoes/${id}/plano/desvincular`);
                        window.location.reload();
                    } catch (error) {
                        notify(el, error.message);
                    }
                });
            });

            const search = el.querySelector('[data-plano-busca]');
            const results = el.querySelector('[data-plano-resultados]');
            if (search && results) {
                let timer;
                search.addEventListener('input', () => {
                    window.clearTimeout(timer);
                    timer = window.setTimeout(async () => {
                        const query = search.value.trim();
                        try {
                            const resp = await fetch(`/api/cotacoes/${id}/plano/buscar?q=${encodeURIComponent(query)}`);
                            const payload = await resp.json().catch(() => ({}));
                            if (!resp.ok || payload.success === false) {
                                throw new Error(payload.message || 'Não foi possível buscar propostas.');
                            }
                            results.innerHTML = (payload.itens || []).map((item) => (
                                `<button type="button" class="cot-plano-item" data-plano-ligar="${escapeHtml(item.id)}">` +
                                `<span class="cot-plano-body"><span class="cot-plano-line">` +
                                `<span class="cot-plano-num">${escapeHtml(item.numero_cotacao)}</span>` +
                                `<span class="cot-plano-val">${money(item.valor_total)}</span>` +
                                `</span><span class="cot-plano-meta">${escapeHtml(item.nome_campanha || '')}</span></span></button>`
                            )).join('') || '<p class="cot-plano-copy">Nenhuma proposta deste cliente.</p>';
                        } catch (error) {
                            results.innerHTML = `<p class="cot-plano-aviso">${escapeHtml(error.message)}</p>`;
                        }
                    }, 220);
                });
                results.addEventListener('click', async (event) => {
                    const btn = event.target.closest('[data-plano-ligar]');
                    if (!btn) return;
                    try {
                        await postJson(`/api/cotacoes/${id}/plano/vincular`, { alvo_id: btn.getAttribute('data-plano-ligar') });
                        window.location.reload();
                    } catch (error) {
                        notify(el, error.message);
                    }
                });
            }
        });
    }

    document.addEventListener('DOMContentLoaded', () => bind(document));
    window.cotacaoPlanoBind = bind;
})();
