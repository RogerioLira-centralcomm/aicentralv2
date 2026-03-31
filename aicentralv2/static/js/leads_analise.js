/* Análise de Leads — Página dedicada de relatório */

const EXEC_NAMES = {};
(window.EXECUTIVOS || []).forEach(e => EXEC_NAMES[e.id] = e.nome);

function esc(s) { const d = document.createElement('div'); d.textContent = s || ''; return d.innerHTML; }
function fmtMoeda(v) { return 'R$ ' + Number(v || 0).toLocaleString('pt-BR', {minimumFractionDigits: 2}); }
function fmtData(iso) { if (!iso) return '-'; return new Date(iso).toLocaleDateString('pt-BR'); }
function execNome(id) { return EXEC_NAMES[id] || (id ? '#' + id : 'Sem executivo'); }

document.addEventListener('DOMContentLoaded', () => {
    const now = new Date();
    const inicio = new Date(now.getFullYear(), now.getMonth(), 1);
    document.getElementById('filtro_data_inicio').value = inicio.toISOString().slice(0, 10);
    document.getElementById('filtro_data_fim').value = now.toISOString().slice(0, 10);
    loadAnalise();
});

async function loadAnalise() {
    const dataInicio = document.getElementById('filtro_data_inicio').value;
    const dataFim = document.getElementById('filtro_data_fim').value;
    const execId = document.getElementById('filtro_executivo').value;

    if (!dataInicio || !dataFim) return;

    let url = `/api/leads/analise?data_inicio=${dataInicio}&data_fim=${dataFim}`;
    if (execId) url += `&id_executivo=${execId}`;

    try {
        const resp = await fetch(url);
        const json = await resp.json();
        if (!json.success) throw new Error(json.message);

        const d = json.data;
        renderKPIs(d.kpis || {});
        renderTempoConversao(d.tempo_conversao || {});
        renderTempoStatus(d.tempo_por_status || []);
        renderProdutividade(d.produtividade_executivo || [], d.atividades_executivo || []);
        renderAtividades(d.atividades_executivo || []);
        renderDesqualificados(d.desqualificados || []);
    } catch (e) {
        console.error('Erro loadAnalise:', e);
    }
}

function renderKPIs(k) {
    document.getElementById('kpi_total').textContent = k.total_leads ?? '-';
    document.getElementById('kpi_convertidos').textContent = k.convertidos ?? '-';
    document.getElementById('kpi_desqualificados').textContent = k.desqualificados ?? '-';
    document.getElementById('kpi_perdidos').textContent = k.perdidos ?? '-';
    document.getElementById('kpi_taxa').textContent = k.taxa_conversao != null ? k.taxa_conversao + '%' : '-';
    document.getElementById('kpi_receita').textContent = k.receita_total != null ? fmtMoeda(k.receita_total) : '-';
}

function renderTempoConversao(t) {
    document.getElementById('tempo_avg').textContent = t.avg_dias_conversao != null ? t.avg_dias_conversao : '-';
    document.getElementById('tempo_min').textContent = t.min_dias != null ? Math.round(t.min_dias) : '-';
    document.getElementById('tempo_max').textContent = t.max_dias != null ? Math.round(t.max_dias) : '-';
    document.getElementById('tempo_total_conv').textContent = t.total_convertidos ?? '-';
}

function renderTempoStatus(rows) {
    const container = document.getElementById('section_tempo_status');
    if (rows.length === 0) {
        container.innerHTML = '<div class="analise-empty">Sem dados de transição de status no período</div>';
        return;
    }
    container.innerHTML = `
        <table class="analise-table">
            <thead><tr>
                <th>Transição de Status</th>
                <th>Transições</th>
                <th>Média dias desde criação</th>
            </tr></thead>
            <tbody>${rows.map(r => `<tr>
                <td class="font-medium">${esc(r.status_destino)}</td>
                <td>${r.transicoes}</td>
                <td>${r.avg_dias_desde_criacao ?? '-'}</td>
            </tr>`).join('')}</tbody>
        </table>`;
}

function renderProdutividade(rows, ativRows) {
    const container = document.getElementById('section_produtividade');
    if (rows.length === 0) {
        container.innerHTML = '<div class="analise-empty">Sem dados de produtividade no período</div>';
        return;
    }

    const ativMap = {};
    ativRows.forEach(a => { ativMap[a.id_executivo] = a; });

    container.innerHTML = `
        <table class="analise-table">
            <thead><tr>
                <th>Executivo</th>
                <th>Leads</th>
                <th>Convertidos</th>
                <th>Desqualificados</th>
                <th>Taxa Conv.</th>
                <th>Receita</th>
                <th>Avg Conversão (dias)</th>
                <th>Avg 1o Contato (h)</th>
                <th>Atividades</th>
                <th>Leads Trabalhados</th>
            </tr></thead>
            <tbody>${rows.map(r => {
                const at = ativMap[r.id_executivo] || {};
                return `<tr>
                    <td class="font-semibold">${esc(execNome(r.id_executivo))}</td>
                    <td>${r.total_leads}</td>
                    <td class="analise-kpi-success font-semibold">${r.convertidos}</td>
                    <td class="analise-kpi-danger">${r.desqualificados}</td>
                    <td class="font-semibold">${r.taxa_conversao ?? 0}%</td>
                    <td>${fmtMoeda(r.receita)}</td>
                    <td>${r.avg_dias_conversao ?? '-'}</td>
                    <td>${r.avg_horas_primeiro_contato ?? '-'}</td>
                    <td>${at.total_atividades ?? '-'}</td>
                    <td>${at.leads_trabalhados ?? '-'}</td>
                </tr>`;
            }).join('')}</tbody>
        </table>`;
}

function renderAtividades(rows) {
    const container = document.getElementById('section_atividades');
    if (rows.length === 0) {
        container.innerHTML = '<div class="analise-empty">Sem atividades no período</div>';
        return;
    }
    container.innerHTML = `
        <table class="analise-table">
            <thead><tr>
                <th>Executivo</th>
                <th>Total</th>
                <th>Ligações</th>
                <th>WhatsApp</th>
                <th>Emails</th>
                <th>Reuniões</th>
                <th>Tentativas Contato</th>
                <th>Leads Trabalhados</th>
            </tr></thead>
            <tbody>${rows.map(r => `<tr>
                <td class="font-semibold">${esc(execNome(r.id_executivo))}</td>
                <td class="font-semibold">${r.total_atividades}</td>
                <td>${r.ligacoes}</td>
                <td>${r.whatsapp}</td>
                <td>${r.emails}</td>
                <td>${r.reunioes}</td>
                <td>${r.tentativas_contato}</td>
                <td>${r.leads_trabalhados}</td>
            </tr>`).join('')}</tbody>
        </table>`;
}

function renderDesqualificados(rows) {
    const container = document.getElementById('section_desqualificados');
    if (rows.length === 0) {
        container.innerHTML = '<div class="analise-empty">Nenhum lead desqualificado no período</div>';
        return;
    }
    container.innerHTML = `
        <div class="mb-2 text-sm text-gray-500">${rows.length} lead(s) desqualificado(s)</div>
        <table class="analise-table">
            <thead><tr>
                <th>Empresa</th>
                <th>Nome</th>
                <th>Email</th>
                <th>Motivo</th>
                <th>Executivo</th>
                <th>Fonte</th>
                <th>Valor Estimado</th>
                <th>Criado em</th>
                <th>Desqualificado em</th>
            </tr></thead>
            <tbody>${rows.map(r => `<tr>
                <td class="font-medium">${esc(r.empresa || '-')}</td>
                <td>${esc(r.nome || '-')}</td>
                <td>${esc(r.email || '-')}</td>
                <td><span class="analise-motivo-badge">${esc(r.motivo_desqualificacao || '-')}</span></td>
                <td>${esc(execNome(r.id_executivo))}</td>
                <td>${esc(r.fonte || '-')}</td>
                <td>${r.valor_estimado ? fmtMoeda(r.valor_estimado) : '-'}</td>
                <td>${fmtData(r.created_at)}</td>
                <td>${fmtData(r.updated_at)}</td>
            </tr>`).join('')}</tbody>
        </table>`;
}
