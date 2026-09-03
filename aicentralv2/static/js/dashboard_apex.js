/**
 * Dashboard Comercial - ApexCharts
 * Versão migrada de Chart.js para ApexCharts
 */
(() => {
    'use strict';

    const MONTH_LABELS = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];

    // Instâncias dos gráficos para cleanup
    const charts = {};

    // Inicialização
    document.addEventListener('DOMContentLoaded', () => {
        document.getElementById('sales-refresh')?.addEventListener('click', loadDashboard);
        document.getElementById('sales-year')?.addEventListener('change', loadDashboard);
        loadDashboard();
    });

    async function loadDashboard() {
        const button = document.getElementById('sales-refresh');
        const year = document.getElementById('sales-year')?.value || '2026';
        setLoading(button, true);
        try {
            const response = await fetch(`/api/dashboard/comercial-anual?year=${encodeURIComponent(year)}`, {
                headers: { Accept: 'application/json' }
            });
            const payload = await response.json();
            if (!response.ok || !payload.success) {
                throw new Error(payload.message || 'Não foi possível carregar o painel');
            }
            renderDashboard(payload.data || {});
        } catch (error) {
            console.error('Erro no dashboard comercial:', error);
            renderError(error.message);
        } finally {
            setLoading(button, false);
        }
    }

    function renderDashboard(data) {
        renderKpis(data.resumo_atual || {}, data.resumo_anterior || {}, data.mes_referencia);

        const apex = data.apex || {};
        renderOverview(apex.overview, data.ano || 2026);
        renderQuotes(apex.quotes, data.cotacoes_trimestres || []);
        renderExecutives(data.executivos || [], apex.executivos || []);
        renderCampaigns(apex.campaigns, data.campanhas_mensal || []);
    }

    // ========== KPIs ==========

    function renderKpis(current, previous, referenceMonth) {
        setText('sales-kpi-clientes', formatNumber(current.clientes_novos));
        setText('sales-kpi-cotacoes', formatNumber(current.cotacoes));
        setText('sales-kpi-pis', formatNumber(current.pis));
        setText('sales-kpi-valor', formatCurrencyShort(current.valor_pi));
        renderDelta('sales-delta-clientes', current.clientes_novos, previous.clientes_novos);
        renderDelta('sales-delta-cotacoes', current.cotacoes, previous.cotacoes);
        renderDelta('sales-delta-pis', current.pis, previous.pis);
        renderDelta('sales-delta-valor', current.valor_pi, previous.valor_pi);

        if (referenceMonth) {
            const [year, month] = referenceMonth.split('-').map(Number);
            const label = new Intl.DateTimeFormat('pt-BR', { month: 'long', year: 'numeric' })
                .format(new Date(year, month - 1, 1));
            setText('sales-reference-copy', ` · referência: ${label}`);
        }
    }

    function renderDelta(id, currentValue, previousValue) {
        const element = document.getElementById(id);
        if (!element) return;
        const current = Number(currentValue || 0);
        const previous = Number(previousValue || 0);
        element.className = 'sales-delta';
        if (previous === 0) {
            element.innerHTML = current === 0
                ? '<i class="fas fa-minus" aria-hidden="true"></i> sem variação mensal'
                : '<i class="fas fa-arrow-trend-up" aria-hidden="true"></i> novo volume no mês';
            if (current > 0) element.classList.add('is-positive');
            return;
        }
        const percentage = ((current - previous) / previous) * 100;
        const positive = percentage > 0;
        const negative = percentage < 0;
        if (positive) element.classList.add('is-positive');
        if (negative) element.classList.add('is-negative');
        const icon = positive ? 'fa-arrow-trend-up' : negative ? 'fa-arrow-trend-down' : 'fa-minus';
        const prefix = positive ? '+' : '';
        element.innerHTML = `<i class="fas ${icon}" aria-hidden="true"></i> ${prefix}${percentage.toFixed(1)}% vs. mês anterior`;
    }

    // ========== Overview Chart ==========

    function renderOverview(apex, year) {
        destroyChart('overview');
        const container = document.getElementById('sales-overview-wrap');
        if (!container) return;

        if (!apex || !apex.series || !apex.series.length) {
            container.innerHTML = '<div class="sales-empty">Sem dados comerciais para o período.</div>';
            return;
        }

        container.innerHTML = '<div id="sales-overview-chart"></div>';
        const chartEl = document.getElementById('sales-overview-chart');
        if (!chartEl) return;

        charts.overview = new ApexCharts(chartEl, {
            chart: {
                type: 'line',
                height: '100%',
                fontFamily: 'Inter, sans-serif',
                toolbar: { show: false },
                animations: { enabled: true, easing: 'easeinout', speed: 400 },
            },
            series: apex.series.map(s => ({
                name: s.name,
                type: s.type,
                data: s.data,
            })),
            colors: apex.series.map(s => s.color),
            stroke: {
                width: apex.series.map(s => s.type === 'line' ? 2.5 : 0),
                curve: 'smooth',
            },
            fill: {
                opacity: apex.series.map(s => s.type === 'bar' ? 1 : 1),
            },
            markers: {
                size: apex.series.map(s => s.type === 'line' ? 4 : 0),
                strokeWidth: 2,
                strokeColors: '#fff',
                hover: { size: 6 },
            },
            plotOptions: {
                bar: {
                    borderRadius: 4,
                    columnWidth: '60%',
                },
            },
            xaxis: {
                categories: apex.categories,
                labels: { style: { colors: '#64748b', fontSize: '11px' } },
                axisBorder: { show: false },
                axisTicks: { show: false },
            },
            yaxis: [
                {
                    title: { text: 'Entradas na carteira', style: { color: '#64748b', fontSize: '11px' } },
                    labels: { style: { colors: '#64748b' }, formatter: val => Math.round(val) },
                },
                {
                    opposite: true,
                    title: { text: 'Cotações e PIs', style: { color: '#64748b', fontSize: '11px' } },
                    labels: { style: { colors: '#64748b' }, formatter: val => Math.round(val) },
                },
            ],
            grid: { borderColor: '#e2e8f0', strokeDashArray: 4 },
            legend: {
                position: 'top',
                horizontalAlign: 'left',
                markers: { width: 10, height: 10, radius: 2 },
                itemMargin: { horizontal: 12 },
            },
            tooltip: {
                shared: true,
                intersect: false,
                y: { formatter: val => formatNumber(val) },
            },
            dataLabels: { enabled: false },
        });
        charts.overview.render();
        setText('sales-overview-badge', `${year} · Top 3 executivos`);
    }

    // ========== Quotes Chart ==========

    function renderQuotes(apex, quarters) {
        destroyChart('quotes');

        // Atualizar cards de trimestre
        for (let q = 1; q <= 4; q++) {
            const item = quarters.find(row => Number(row.trimestre) === q);
            setText(`sales-quotes-q${q}`, formatNumber(item?.total || 0));
            setText(`sales-quotes-q${q}-value`, formatCurrency(item?.valor_total || 0));
        }
        const total = quarters.reduce((sum, row) => sum + Number(row.total || 0), 0);
        const totalValue = quarters.reduce((sum, row) => sum + Number(row.valor_total || 0), 0);
        setText('sales-quotes-badge', `${formatNumber(total)} cotações · ${formatCurrency(totalValue)}`);

        const container = document.getElementById('sales-quotes-wrap');
        if (!container) return;

        if (!apex || !apex.series || !apex.series.length) {
            container.innerHTML = '<div class="sales-empty">Sem cotações semanais em 2026.</div>';
            return;
        }

        container.innerHTML = '<div id="sales-quotes-chart"></div>';
        const chartEl = document.getElementById('sales-quotes-chart');
        if (!chartEl) return;

        // Guardar valores de moeda para tooltip
        const currencyData = apex.series.map(s => s.currencyValues || []);

        charts.quotes = new ApexCharts(chartEl, {
            chart: {
                type: 'bar',
                height: '100%',
                stacked: true,
                fontFamily: 'Inter, sans-serif',
                toolbar: { show: false },
            },
            series: apex.series.map(s => ({
                name: s.name,
                data: s.data,
            })),
            colors: apex.series.map(s => s.color),
            plotOptions: {
                bar: {
                    borderRadius: 3,
                    columnWidth: '70%',
                },
            },
            xaxis: {
                categories: apex.categories,
                labels: {
                    style: { colors: '#64748b', fontSize: '10px' },
                    rotate: 0,
                    hideOverlappingLabels: true,
                },
                axisBorder: { show: false },
                axisTicks: { show: false },
            },
            yaxis: {
                labels: { style: { colors: '#64748b' }, formatter: val => Math.round(val) },
            },
            grid: { borderColor: '#e2e8f0', strokeDashArray: 4 },
            legend: {
                position: 'top',
                horizontalAlign: 'left',
                markers: { width: 10, height: 10, radius: 2 },
            },
            tooltip: {
                shared: true,
                intersect: false,
                custom: function({ series, seriesIndex, dataPointIndex, w }) {
                    const statusNames = apex.series.map(s => s.name);
                    let html = `<div class="apexcharts-tooltip-custom" style="padding: 8px 12px; font-size: 12px;">`;
                    html += `<div style="font-weight: 600; margin-bottom: 6px;">${apex.categories[dataPointIndex]}</div>`;
                    let totalQty = 0;
                    let totalVal = 0;
                    statusNames.forEach((name, idx) => {
                        const qty = series[idx]?.[dataPointIndex] || 0;
                        const val = currencyData[idx]?.[dataPointIndex] || 0;
                        if (qty > 0) {
                            totalQty += qty;
                            totalVal += val;
                            html += `<div style="display: flex; justify-content: space-between; gap: 16px; margin: 2px 0;">`;
                            html += `<span style="color: ${apex.series[idx].color};">● ${name}</span>`;
                            html += `<span>${formatNumber(qty)} · ${formatCurrency(val)}</span>`;
                            html += `</div>`;
                        }
                    });
                    if (statusNames.length > 1) {
                        html += `<div style="border-top: 1px solid #e2e8f0; margin-top: 6px; padding-top: 6px; font-weight: 600;">`;
                        html += `Total: ${formatNumber(totalQty)} · ${formatCurrency(totalVal)}`;
                        html += `</div>`;
                    }
                    html += `</div>`;
                    return html;
                },
            },
            dataLabels: { enabled: false },
        });
        charts.quotes.render();
    }

    // ========== Executives ==========

    function renderExecutives(executives, apexData) {
        const container = document.getElementById('sales-executives-list');
        if (!container) return;

        // Destruir gráficos anteriores de executivos
        Object.keys(charts)
            .filter(key => key.startsWith('exec-'))
            .forEach(destroyChart);

        if (!executives.length) {
            container.innerHTML = '<div class="sales-card sales-empty">Nenhum executivo com carteira ativa.</div>';
            return;
        }

        container.innerHTML = executives.slice(0, 3).map((exec, index) => `
            <article class="sales-card sales-executive-card">
                <header class="sales-card-header">
                    <div>
                        <h3 class="sales-card-title">${escapeHtml(exec.nome)}</h3>
                        <p class="sales-card-subtitle">Carteira, cotações e PIs em 2026</p>
                    </div>
                    <span class="sales-card-badge">${formatNumber(exec.total_clientes)} clientes</span>
                </header>
                <div class="sales-executive-views">
                    <section class="sales-mini-view">
                        <div class="sales-mini-title">Carteira atual</div>
                        <div class="sales-mini-subtitle">Ativos e prospecção por perfil</div>
                        <div class="sales-mini-chart" id="exec-${index}-portfolio-wrap"></div>
                    </section>
                    <section class="sales-mini-view">
                        <div class="sales-mini-title">Cotações</div>
                        <div class="sales-mini-subtitle">Quantidade por mês</div>
                        <div class="sales-mini-chart" id="exec-${index}-quotes-wrap"></div>
                    </section>
                    <section class="sales-mini-view">
                        <div class="sales-mini-title">PIs</div>
                        <div class="sales-mini-subtitle">Quantidade por mês</div>
                        <div class="sales-mini-chart" id="exec-${index}-pis-wrap"></div>
                    </section>
                </div>
            </article>
        `).join('');

        // Renderizar gráficos após DOM estar pronto
        setTimeout(() => {
            executives.slice(0, 3).forEach((exec, index) => {
                const apex = apexData[index] || {};
                renderExecutivePortfolio(index, apex.portfolio);
                renderExecutiveLine(index, 'quotes', apex.quotes);
                renderExecutiveLine(index, 'pis', apex.pis);
            });
        }, 50);
    }

    function renderExecutivePortfolio(index, apex) {
        const container = document.getElementById(`exec-${index}-portfolio-wrap`);
        if (!container || !apex) return;

        container.innerHTML = `<div id="exec-${index}-portfolio"></div>`;
        const chartEl = document.getElementById(`exec-${index}-portfolio`);
        if (!chartEl) return;

        const key = `exec-${index}-portfolio`;
        charts[key] = new ApexCharts(chartEl, {
            chart: {
                type: 'bar',
                height: '100%',
                stacked: true,
                fontFamily: 'Inter, sans-serif',
                toolbar: { show: false },
            },
            series: apex.series.map(s => ({
                name: s.name,
                data: s.data,
            })),
            colors: apex.series.map(s => s.color),
            plotOptions: {
                bar: {
                    horizontal: true,
                    borderRadius: 3,
                    barHeight: '60%',
                },
            },
            xaxis: {
                categories: apex.categories,
                labels: { style: { colors: '#64748b', fontSize: '10px' }, formatter: val => Math.round(val) },
            },
            yaxis: {
                labels: { style: { colors: '#64748b', fontSize: '10px' } },
            },
            grid: { borderColor: '#e2e8f0', strokeDashArray: 4, xaxis: { lines: { show: true } }, yaxis: { lines: { show: false } } },
            legend: {
                position: 'top',
                fontSize: '10px',
                markers: { width: 8, height: 8, radius: 2 },
            },
            tooltip: { y: { formatter: val => formatNumber(val) } },
            dataLabels: { enabled: false },
        });
        charts[key].render();
    }

    function renderExecutiveLine(index, suffix, apex) {
        const container = document.getElementById(`exec-${index}-${suffix}-wrap`);
        if (!container || !apex) return;

        container.innerHTML = `<div id="exec-${index}-${suffix}"></div>`;
        const chartEl = document.getElementById(`exec-${index}-${suffix}`);
        if (!chartEl) return;

        const key = `exec-${index}-${suffix}`;
        charts[key] = new ApexCharts(chartEl, {
            chart: {
                type: 'line',
                height: '100%',
                fontFamily: 'Inter, sans-serif',
                toolbar: { show: false },
                sparkline: { enabled: false },
            },
            series: apex.series.map(s => ({
                name: s.name,
                data: s.data,
            })),
            colors: apex.series.map(s => s.color),
            stroke: { width: 2.5, curve: 'smooth' },
            markers: {
                size: 3,
                strokeWidth: 2,
                strokeColors: '#fff',
                hover: { size: 5 },
            },
            xaxis: {
                categories: apex.categories,
                labels: {
                    style: { colors: '#64748b', fontSize: '9px' },
                    rotate: 0,
                    hideOverlappingLabels: true,
                },
                axisBorder: { show: false },
                axisTicks: { show: false },
            },
            yaxis: {
                labels: { style: { colors: '#64748b', fontSize: '10px' }, formatter: val => Math.round(val) },
            },
            grid: { borderColor: '#e2e8f0', strokeDashArray: 4 },
            legend: { show: false },
            tooltip: { y: { formatter: val => formatNumber(val) } },
        });
        charts[key].render();
    }

    // ========== Campaigns Chart ==========

    function renderCampaigns(apex, rows) {
        destroyChart('campaigns');
        const container = document.getElementById('sales-campaigns-wrap');
        if (!container) return;

        const total = rows.reduce((sum, row) => sum + Number(row.total || 0), 0);
        setText('sales-campaigns-badge', `${formatNumber(total)} campanhas`);

        if (!apex || !apex.series || !apex.series.length) {
            container.innerHTML = '<div class="sales-empty">Sem campanhas por plataforma em 2026.</div>';
            return;
        }

        container.innerHTML = '<div id="sales-campaigns-chart"></div>';
        const chartEl = document.getElementById('sales-campaigns-chart');
        if (!chartEl) return;

        charts.campaigns = new ApexCharts(chartEl, {
            chart: {
                type: 'bar',
                height: '100%',
                stacked: true,
                fontFamily: 'Inter, sans-serif',
                toolbar: { show: false },
            },
            series: apex.series.map(s => ({
                name: s.name,
                data: s.data,
            })),
            colors: apex.series.map(s => s.color),
            plotOptions: {
                bar: {
                    borderRadius: 3,
                    columnWidth: '60%',
                },
            },
            xaxis: {
                categories: apex.categories,
                labels: { style: { colors: '#64748b', fontSize: '11px' } },
                axisBorder: { show: false },
                axisTicks: { show: false },
            },
            yaxis: {
                labels: { style: { colors: '#64748b' }, formatter: val => Math.round(val) },
            },
            grid: { borderColor: '#e2e8f0', strokeDashArray: 4 },
            legend: {
                position: 'top',
                horizontalAlign: 'left',
                markers: { width: 10, height: 10, radius: 2 },
            },
            tooltip: {
                shared: true,
                intersect: false,
                y: { formatter: val => formatNumber(val) },
            },
            dataLabels: { enabled: false },
        });
        charts.campaigns.render();
    }

    // ========== Utilities ==========

    function destroyChart(key) {
        if (charts[key]) {
            charts[key].destroy();
            delete charts[key];
        }
    }

    function renderError(message) {
        const msg = escapeHtml(message);
        ['sales-overview-wrap', 'sales-quotes-wrap', 'sales-campaigns-wrap'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.innerHTML = `<div class="sales-empty">${msg}</div>`;
        });
        const executives = document.getElementById('sales-executives-list');
        if (executives) executives.innerHTML = `<div class="sales-card sales-empty">${msg}</div>`;
    }

    function setLoading(button, loading) {
        if (!button) return;
        button.disabled = loading;
        button.classList.toggle('loading', loading);
        button.querySelector('i')?.classList.toggle('fa-spin', loading);
    }

    function setText(id, value) {
        const element = document.getElementById(id);
        if (element) element.textContent = value;
    }

    function formatNumber(value) {
        return Number(value || 0).toLocaleString('pt-BR');
    }

    function formatCurrencyShort(value) {
        const number = Number(value || 0);
        if (Math.abs(number) >= 1000000) return `R$ ${(number / 1000000).toFixed(1)} mi`;
        if (Math.abs(number) >= 1000) return `R$ ${(number / 1000).toFixed(1)} mil`;
        return new Intl.NumberFormat('pt-BR', {
            style: 'currency',
            currency: 'BRL',
            maximumFractionDigits: 0
        }).format(number);
    }

    function formatCurrency(value) {
        return new Intl.NumberFormat('pt-BR', {
            style: 'currency',
            currency: 'BRL'
        }).format(Number(value || 0));
    }

    function escapeHtml(value) {
        return String(value || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    // Expor para debug
    window.salesDashboard = { charts, loadDashboard };
})();
