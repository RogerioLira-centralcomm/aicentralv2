import React, {useCallback, useEffect, useMemo, useState} from 'react';
import {Empty, integer, json, reportUrl} from './reportsCommon.jsx';
import {ReportsNativeSelect} from './ReportsNativeSelect.jsx';
import {sankeyLayout} from './sankeyLayout.js';
import {DomainsOverview} from './DomainsOverview.jsx';
import './page-detail.css';

const PERIODS = [7, 14, 30, 60, 90];
const dash = '—';
const number = value => value == null ? dash : integer(value);
const percent = value => value == null ? dash : `${Number(value).toLocaleString('pt-BR', {maximumFractionDigits: 1})}%`;
const seconds = value => {
  if (value == null) return dash;
  const total = Math.round(value);
  return total >= 60 ? `${Math.floor(total / 60)} min ${String(total % 60).padStart(2, '0')} s` : `${total} s`;
};
const money = (micros, currency) => micros == null || !currency ? dash
  : new Intl.NumberFormat('pt-BR', {style: 'currency', currency}).format(micros / 1_000_000);
const dateTime = value => value ? new Date(value).toLocaleString('pt-BR', {timeZone: 'America/Sao_Paulo', dateStyle: 'short', timeStyle: 'short'}) : dash;
const STATUS = {online: 'Disponível', degraded: 'Degradada', offline: 'Indisponível'};

function Change({change, unit}) {
  if (!change) return <small className="page-detail-change">Sem período anterior comparável</small>;
  const {absolute, relative} = change;
  if (!absolute) return <small className="page-detail-change">Estável vs. período anterior</small>;
  const sign = absolute > 0 ? '▲' : '▼';
  const text = unit === 'percent' ? `${Math.abs(absolute).toLocaleString('pt-BR', {maximumFractionDigits: 1})} p.p.`
    : relative == null ? `${Math.abs(absolute).toLocaleString('pt-BR')}` : `${Math.abs(relative).toLocaleString('pt-BR', {maximumFractionDigits: 1})}%`;
  return <small className="page-detail-change">{sign} {text} vs. período anterior</small>;
}

function Metric({label, value, change, unit, hint}) {
  return <article className="reports-kpi page-detail-kpi" title={hint}><span>{label}</span><strong>{value}</strong><Change change={change} unit={unit}/></article>;
}

function Bars({rows}) {
  const max = Math.max(1, ...rows.map(row => row.sessions || 0));
  return rows.length ? <ul className="page-detail-bars">{rows.map(row => <li key={row.key}>
    <span>{row.label}</span>
    <div className="page-detail-bar" role="img" aria-label={`${row.label}: ${number(row.sessions)} sessões`}><i style={{width: `${Math.max(2, 100 * row.sessions / max)}%`}}/></div>
    <b>{number(row.sessions)}</b><small>{row.converted ? `${number(row.converted)} converteram` : ''}</small>
  </li>)}</ul> : <Empty message="Sem sessões no período."/>;
}

function Scroll({metrics}) {
  const steps = [['scroll_25', '25%'], ['scroll_50', '50%'], ['scroll_75', '75%'], ['scroll_100', 'Fim da página']];
  return <ul className="page-detail-bars">{steps.map(([key, label]) => <li key={key}>
    <span>{label}</span>
    <div className="page-detail-bar" role="img" aria-label={`${label}: ${percent(metrics[key])} das sessões`}><i style={{width: `${metrics[key] ?? 0}%`}}/></div>
    <b>{percent(metrics[key])}</b><small/>
  </li>)}</ul>;
}

function Table({head, rows, empty}) {
  return rows.length ? <div className="reports-table-wrap"><table><thead><tr>{head.map(item => <th key={item}>{item}</th>)}</tr></thead>
    <tbody>{rows.map((row, index) => <tr key={index}>{row.map((cell, i) => <td key={i}>{cell}</td>)}</tr>)}</tbody></table></div> : <Empty message={empty}/>;
}

function PaidOrigin({paid}) {
  if (!paid) return null;
  if (!paid.available) return <p className="page-detail-note">{paid.reason}</p>;
  const campaigns = paid.campaigns || [];
  if (!campaigns.length) return <Empty message="Nenhuma campanha do Google Ads aponta para esta página no período, ou o script v2 ainda não enviou páginas de destino."/>;
  const names = Object.fromEntries(campaigns.map(item => [item.campaign_external_id, item.campaign_name]));
  return <>
    <h3>Google Ads · informado pela plataforma</h3>
    <Table head={['Campanha', 'Cliques', 'Custo', 'Conversões (Ads)', 'Custo por conversão']}
      rows={campaigns.map(item => [item.campaign_name, number(item.clicks), money(item.cost_micros, item.currency),
        item.conversions == null ? dash : Number(item.conversions).toLocaleString('pt-BR', {maximumFractionDigits: 1}),
        money(item.cost_per_conversion_micros, item.currency)])} empty=""/>
    <h3>Super Tag · observado na página</h3>
    <Table head={['Campanha (UTM)', 'Sessões', 'Sessões que converteram', 'Ligada à campanha']}
      rows={(paid.observed_campaigns || []).map(item => [item.utm_campaign, number(item.sessions), number(item.converted_sessions),
        item.matched_campaign_id ? names[item.matched_campaign_id] : 'Sem correspondência'])}
      empty="Nenhuma sessão com UTM de campanha no período."/>
    <h3>Termos de pesquisa dessas campanhas</h3>
    <Table head={['Termo', 'Cliques', 'Custo', 'Conversões']}
      rows={(paid.search_terms || []).map(item => [item.search_term, number(item.clicks), money(item.cost_micros, campaigns[0].currency), item.conversions == null ? dash : Number(item.conversions).toLocaleString('pt-BR', {maximumFractionDigits: 1})])}
      empty="Sem termos de pesquisa recebidos."/>
    <h3>Palavras-chave dessas campanhas</h3>
    <Table head={['Palavra-chave', 'Correspondência', 'Índice de Qualidade', 'Cliques', 'Custo']}
      rows={(paid.keywords || []).map(item => [item.keyword_text, item.match_type, item.quality_score ?? dash, number(item.clicks), money(item.cost_micros, campaigns[0].currency)])}
      empty="Sem palavras-chave recebidas."/>
    <p className="page-detail-note">{paid.note} Os números do Google Ads e da Super Tag medem coisas diferentes e não são somados.</p>
  </>;
}


const SEVERITY = {high: 'Prioridade alta', medium: 'Prioridade média', low: 'Prioridade baixa'};
function evidenceValue(item) {
  if (item.value == null) return dash;
  if (item.unit === 'money') return money(item.value, item.currency);
  if (item.unit === 'percent') return percent(item.value);
  if (item.unit === 'count') return number(item.value);
  return String(item.value);
}

function Suggestions({siteId, path, days, client}) {
  const [state, setState] = useState({loading: true, error: '', body: null});
  useEffect(() => {
    let active = true;
    setState({loading: true, error: '', body: null});
    json(`/connect/api/v2/reports/pages/suggestions?${new URLSearchParams({client_id: client, site_id: siteId, path, days})}`)
      .then(body => { if (active) setState({loading: false, error: '', body}); })
      .catch(failure => { if (active) setState({loading: false, error: failure.message, body: null}); });
    return () => { active = false; };
  }, [siteId, path, days, client]);
  const body = state.body;
  return <article className="reports-panel" id="acoes"><div className="reports-panel-head"><h2>Ações sugeridas</h2><span>Só sugestões: nada é alterado no Google Ads</span></div>
    {state.error && <div className="reports-error" role="alert">{state.error}</div>}
    {state.loading && <div className="reports-loading" role="status">Analisando a página…</div>}
    {body && !body.suggestions.length && <Empty message="Nenhuma ação sugerida: nada ultrapassou os limites com os dados deste período."/>}
    {body?.suggestions.length > 0 && <ol className="page-suggestions">{body.suggestions.map(item => <li key={item.id} className={`page-suggestion is-${item.severity}`}>
      <header><span className="page-suggestion-badge">{SEVERITY[item.severity]}</span><h3>{item.title}</h3></header>
      <p>{item.summary}</p>
      <dl className="page-suggestion-evidence">{item.evidence.map((entry, index) => <div key={index}><dt>{entry.label}</dt><dd>{evidenceValue(entry)}</dd></div>)}</dl>
      <p className="page-suggestion-action"><b>O que verificar:</b> {item.action}</p>
      <a className="reports-inline-link" href={`#${item.anchor}`}>Ver os dados</a>
    </li>)}</ol>}
    {body?.skipped.map(note => <p key={note} className="page-detail-note" role="note">{note}</p>)}
    {body && <details className="page-detail-rules"><summary>Como decidimos</summary>
      <ul>{body.rules.map(rule => <li key={rule.rule}><b>{rule.title}.</b> {rule.when}</li>)}</ul></details>}
  </article>;
}

const NODE_TONE = id => id === 'r:yes' ? 'is-good' : id === 'n:exit' || id === 'r:no' ? 'is-loss' : id === 'n:active' ? 'is-neutral' : id === 'page' ? 'is-page' : 'is-flow';

function Sankey({map}) {
  const layout = useMemo(() => sankeyLayout({nodes: map.nodes, links: map.links}, {width: 980, height: 360}), [map]);
  const total = map.total;
  return <div className="page-detail-sankey-wrap"><svg className="page-detail-sankey" viewBox={`-4 -30 ${layout.width + 8} ${layout.height + 40}`} role="img"
      aria-label={`Mapa de conversão com ${number(total)} sessões: origem, esta página, próximo passo e resultado.`}>
    <g className="page-detail-sankey-links">{layout.links.map(link => <path key={`${link.source}>${link.target}`} d={link.path} strokeWidth={Math.max(1, link.width)}
      className={NODE_TONE(link.target)}><title>{`${layout.nodes.find(n => n.id === link.source).label} → ${layout.nodes.find(n => n.id === link.target).label}: ${number(link.value)} sessões (${percent(100 * link.value / total)})`}</title></path>)}</g>
    <g>{layout.nodes.map(node => <g key={node.id} className={NODE_TONE(node.id)}>
      <rect x={node.x} y={node.y} width={node.w} height={Math.max(2, node.h)} rx="3"/>
      {node.column === 1
        ? <text x={node.x + node.w / 2} y={node.y - 10} textAnchor="middle"><tspan>{node.label}</tspan><tspan className="page-detail-sankey-count" dx="6">{number(node.value)} sessões</tspan></text>
        : <text x={node.column === 0 ? node.x - 8 : node.x + node.w + 8} y={node.y + Math.max(2, node.h) / 2}
            textAnchor={node.column === 0 ? 'end' : 'start'} dy="0.35em">
            <tspan>{node.label}</tspan><tspan className="page-detail-sankey-count" x={node.column === 0 ? node.x - 8 : node.x + node.w + 8} dy="1.25em">{number(node.value)} · {percent(100 * node.value / total)}</tspan>
          </text>}
    </g>)}</g>
  </svg></div>;
}

function CrmStrip({map, coverage}) {
  if (!map.crm.available) return <p className="page-detail-note">Sem integração de CRM por visitante: {coverage.events ? `${number(coverage.events)} conversões do CRM chegaram, mas nenhuma com identificação do visitante, então não dá para ligá-las a esta página.` : 'nenhuma conversão do CRM recebida no período.'} As etapas de lead, lead qualificado e venda aparecem aqui quando o webhook enviar o visitor_id.</p>;
  return <ul className="page-detail-crm" aria-label="Etapas confirmadas pelo CRM">{map.crm.stages.map(stage => <li key={stage.key}>
    <span>{stage.label}</span><strong>{number(stage.sessions)}</strong><small>{percent(stage.rate)} das sessões · em até 30 dias</small></li>)}</ul>;
}

function ConversionMap({siteId, path, days, client}) {
  const [state, setState] = useState({loading: true, error: '', body: null});
  useEffect(() => {
    let active = true;
    setState({loading: true, error: '', body: null});
    json(`/connect/api/v2/reports/pages/conversion-map?${new URLSearchParams({client_id: client, site_id: siteId, path, days})}`)
      .then(body => { if (active) setState({loading: false, error: '', body}); })
      .catch(failure => { if (active) setState({loading: false, error: failure.message, body: null}); });
    return () => { active = false; };
  }, [siteId, path, days, client]);
  const body = state.body;
  return <article className="reports-panel"><div className="reports-panel-head"><h2>Mapa de conversão</h2><span>Sessões que viram esta página</span></div>
    {state.error && <div className="reports-error" role="alert">{state.error}</div>}
    {state.loading && <div className="reports-loading" role="status">Carregando mapa de conversão…</div>}
    {body && !body.has_data && <Empty message="Nenhuma sessão viu esta página no período."/>}
    {body?.has_data && <>
      {!body.reliable && <p className="page-detail-warning" role="note">Amostra pequena ({number(body.total)} sessões): os caminhos variam muito com poucas visitas.</p>}
      <Sankey map={body}/>
      <div className="page-detail-column-heads" aria-hidden="true"><span>Origem</span><span>Esta página</span><span>Próximo passo</span><span>Resultado no site</span></div>
      <h3>Confirmado pelo CRM</h3>
      <CrmStrip map={body} coverage={body.crm_coverage}/>
      <ul className="page-detail-notes">{body.notes.map(note => <li key={note}>{note}</li>)}</ul>
    </>}
  </article>;
}

const DEVICE_OPTIONS = [['all', 'Todos os dispositivos'], ['mobile', 'Celular'], ['tablet', 'Tablet'], ['desktop', 'Computador']];

function ClickGrid({grid}) {
  const label = (x, y, value) => `Coluna ${x + 1}, linha ${y + 1}: ${value} ${value === 1 ? 'clique' : 'cliques'}`;
  return <div className="page-detail-grid-wrap">
    <div className="page-detail-heat" role="img" aria-label={`Mapa de cliques da primeira tela. Total de ${grid.total} cliques; maior concentração com ${grid.peak}.`}>
      {grid.cells.flatMap((line, y) => line.map((value, x) => <i key={`${y}-${x}`} title={label(x, y, value)}
        style={{'--heat': grid.peak ? value / grid.peak : 0}} data-empty={value === 0 ? '' : undefined}>{value ? value : ''}</i>))}
    </div>
    <div className="page-detail-legend" aria-hidden="true"><span>Menos cliques</span><b/><span>Mais cliques</span></div>
  </div>;
}

function DocumentGrid({document: doc}) {
  if (!doc || !doc.total) return <Empty message="Ainda não há cliques com posição na página inteira. Eles passam a aparecer quando a Super Tag atualizada for carregada pelos visitantes."/>;
  return <div className="page-detail-grid-wrap">
    <div className="page-detail-heat page-detail-heat--page" role="img" aria-label={`Mapa de cliques da página inteira em ${doc.rows} faixas. Total de ${doc.total} cliques; maior concentração com ${doc.peak}.`}>
      {doc.cells.flatMap((line, y) => line.map((value, x) => <i key={`${y}-${x}`} title={`Faixa ${y + 1} de ${doc.rows}, coluna ${x + 1}: ${value} ${value === 1 ? 'clique' : 'cliques'}`}
        style={{'--heat': doc.peak ? value / doc.peak : 0}} data-empty={value === 0 ? '' : undefined}>{value ? value : ''}</i>))}
    </div>
    <div className="page-detail-legend" aria-hidden="true"><span>Topo da página</span><b/><span>Rodapé</span></div>
    <p className="page-detail-note">{percent(doc.coverage)} dos cliques têm posição na página inteira{doc.median_height ? ` · altura mediana ${integer(doc.median_height)} px` : ''}. Sem imagem da página: as faixas são proporcionais à altura.</p>
  </div>;
}

const SCROLL_BANDS = [['scroll_25', '0–25%'], ['scroll_50', '25–50%'], ['scroll_75', '50–75%'], ['scroll_100', '75–100%']];

function CaptureHeat({siteId, path, device, document: doc, metrics, canEdit, client, csrf}) {
  const [mode, setMode] = useState('clicks');
  const [intensity, setIntensity] = useState(70);
  const [state, setState] = useState({loading: true, error: '', body: null});
  const [starting, setStarting] = useState(false);
  const query = new URLSearchParams({client_id: client, site_id: siteId, path, device});
  const load = useCallback(() => json(`/connect/api/v2/reports/pages/capture?${query}`)
    .then(body => setState({loading: false, error: '', body})).catch(failure => setState({loading: false, error: failure.message, body: null})),
  [siteId, path, device, client]);
  useEffect(() => { setState({loading: true, error: '', body: null}); load(); }, [load]);
  const status = state.body?.status;
  useEffect(() => {
    if (status !== 'capturing') return undefined;
    const timer = setInterval(load, 3000);
    return () => clearInterval(timer);
  }, [status, load]);
  const capture = async () => {
    setStarting(true);
    try {
      const body = await json('/connect/api/v2/reports/pages/capture', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf},
        body: JSON.stringify({client_id: client, site_id: siteId, path, device})});
      setState({loading: false, error: '', body});
    } catch (failure) { setState(current => ({...current, error: failure.message})); }
    setStarting(false);
  };
  const body = state.body;
  const ready = body?.image_url && (body.status === 'ready' || body.status === 'failed');
  return <div className="page-detail-capture">
    {state.error && <div className="reports-error" role="alert">{state.error}</div>}
    {state.loading && <div className="reports-loading" role="status">Verificando captura…</div>}
    {body && !ready && <div className="page-detail-capture-empty">
      <p>{body.status === 'capturing' ? 'Capturando a página… isso leva cerca de um minuto.' : body.status === 'failed' ? (body.message || 'A captura falhou.') : 'Ainda não há captura desta página neste dispositivo.'}</p>
      {body.status !== 'capturing' && (!body.available ? <p className="page-detail-note">A captura depende da integração Firecrawl, que não está configurada neste ambiente.</p>
        : canEdit ? <><button type="button" className="page-detail-button" disabled={starting} onClick={capture}>Capturar a página</button>
          <p className="page-detail-note">A captura usa créditos do provedor e só acontece quando você pede.</p></>
        : <p className="page-detail-note">Peça a alguém com permissão de edição para capturar a página.</p>)}
    </div>}
    {ready && <>
      <div className="page-detail-capture-tools">
        <div className="page-detail-views" role="tablist" aria-label="Camada do calor">
          {[['clicks', 'Cliques'], ['scroll', 'Rolagem']].map(([key, label]) => <button key={key} type="button" role="tab" aria-selected={mode === key} className={mode === key ? 'is-active' : ''} onClick={() => setMode(key)}>{label}</button>)}</div>
        <label className="page-detail-inline">Intensidade<input type="range" min="10" max="100" value={intensity} aria-label="Intensidade do calor" onChange={event => setIntensity(Number(event.target.value))}/></label>
        {canEdit && body.status !== 'capturing' && <button type="button" className="page-detail-button is-quiet" disabled={starting} onClick={capture}>Capturar de novo</button>}
      </div>
      {body.status === 'failed' && <p className="page-detail-warning" role="note">{body.message} Mostrando a captura anterior.</p>}
      <div className="page-detail-capture-stage" style={{aspectRatio: `${body.width} / ${body.height}`, '--intensity': intensity / 100}}>
        <img src={body.image_url} alt={`Captura da página ${path} no dispositivo ${DEVICE_OPTIONS.find(([key]) => key === device)?.[1] || device}`}/>
        {mode === 'clicks' && doc?.total > 0 && <div className="page-detail-overlay" aria-hidden="true">{doc.cells.flatMap((line, y) => line.map((value, x) =>
          <i key={`${y}-${x}`} style={{'--heat': doc.peak ? value / doc.peak : 0}} data-empty={value === 0 ? '' : undefined}/>))}</div>}
        {mode === 'scroll' && <div className="page-detail-overlay page-detail-overlay--bands" aria-hidden="true">{SCROLL_BANDS.map(([key, label]) =>
          <i key={key} style={{'--heat': (metrics[key] ?? 0) / 100}} data-empty={metrics[key] ? undefined : ''}><b>{label} · {percent(metrics[key])}</b></i>)}</div>}
      </div>
      <p className="page-detail-note">Captura de {dateTime((body.captured_at || 0) * 1000)}. {mode === 'scroll'
        ? 'Cada faixa mostra a % das sessões que chegaram até o fim dela.'
        : doc?.total ? `Calor de ${number(doc.total)} cliques com posição na página inteira, em faixas proporcionais à altura.` : 'Ainda não há cliques com posição na página inteira para sobrepor.'}
        {' '}Se a página mudou depois da captura, o calor pode não coincidir com o desenho: capture de novo.</p>
    </>}
  </div>;
}

function Interactions({siteId, path, days, client, metrics, canEdit, csrf}) {
  const [device, setDevice] = useState('all');
  const [view, setView] = useState('screen');
  const [state, setState] = useState({loading: true, error: '', body: null});
  useEffect(() => {
    let active = true;
    setState(current => ({...current, loading: true, error: ''}));
    json(`/connect/api/v2/reports/pages/interactions?${new URLSearchParams({client_id: client, site_id: siteId, path, days, device})}`)
      .then(body => { if (active) setState({loading: false, error: '', body}); })
      .catch(failure => { if (active) setState({loading: false, error: failure.message, body: null}); });
    return () => { active = false; };
  }, [siteId, path, days, client, device]);
  const body = state.body;
  return <article className="reports-panel"><div className="reports-panel-head"><h2>Mapa de interação</h2>
    <label className="page-detail-inline">Dispositivo<ReportsNativeSelect value={device} onChange={event => setDevice(event.target.value)} aria-label="Dispositivo do mapa de interação">
      {DEVICE_OPTIONS.map(([value, text]) => <option key={value} value={value}>{text}</option>)}</ReportsNativeSelect></label></div>
    {state.error && <div className="reports-error" role="alert">{state.error}</div>}
    {state.loading && !body && <div className="reports-loading" role="status">Carregando interações…</div>}
    {body && !body.has_data && <Empty message="Nenhum clique registrado nesta página para o dispositivo e o período escolhidos."/>}
    {body?.has_data && <>
      {body.mixed_layouts && <p className="page-detail-warning" role="note">Esta página tem cliques de mais de um tipo de dispositivo. Os layouts são diferentes: escolha um dispositivo para ler o mapa com segurança.</p>}
      {!body.reliable && <p className="page-detail-warning" role="note">Poucos cliques ({number(body.clicks)}): a distribuição varia muito com amostras pequenas.</p>}
      <div className="page-detail-interactions">
        <div><div className="page-detail-views" role="tablist" aria-label="Área do mapa">
          {[['screen', 'Primeira tela'], ['page', 'Página inteira'], ['capture', 'Sobre a captura']].map(([key, label]) => <button key={key} type="button" role="tab" aria-selected={view === key} className={view === key ? 'is-active' : ''} onClick={() => setView(key)}>{label}</button>)}</div>
          <h3>{view === 'screen' ? 'Onde clicam · primeira tela' : view === 'page' ? 'Onde clicam · página inteira' : 'Calor sobre a página'}</h3>
          {view === 'screen' ? <ClickGrid grid={body.grid}/> : view === 'page' ? <DocumentGrid document={body.document}/>
            : device === 'all' ? <Empty message="Escolha um dispositivo (celular, tablet ou computador) para sobrepor o calor à captura da página."/>
            : <CaptureHeat siteId={siteId} path={path} device={device} document={body.document} metrics={metrics} canEdit={canEdit} client={client} csrf={csrf}/>}
          <p className="page-detail-note">{number(body.clicks)} cliques em {number(body.sessions)} sessões. {number(body.unidentified_clicks)} sem identificação de elemento aparecem somente na grade.</p></div>
        <div><h3>Elementos marcados</h3>
          {body.marked_elements ? <Table head={['Elemento', 'Cliques', 'Sessões que clicaram', '% das sessões', 'Viram o elemento', 'Clicaram entre os que viram']}
            rows={body.elements.map(item => [item.element_id, number(item.clicks), number(item.click_sessions), percent(item.share_of_sessions),
              number(item.seen_sessions), percent(item.click_rate_of_seen)])} empty=""/>
            : <Empty message="Nenhum elemento marcado recebeu cliques. Marque botões e links importantes com data-cadu-element para ver o ranking."/>}
          {body.marked_elements && !body.visibility_tracked && <p className="page-detail-note">A taxa entre os que viram o elemento só existe para elementos com data-cadu-track.</p>}</div>
      </div>
      <ul className="page-detail-notes">{body.notes.map(note => <li key={note}>{note}</li>)}</ul>
    </>}
  </article>;
}

function Health({health}) {
  if (!health?.monitored) return <Empty message="Esta página ainda não é verificada por nenhum fluxo publicado com monitoramento."/>;
  const latest = health.latest;
  return <>
    <p className={`page-detail-status is-${latest.status}`}><b>{STATUS[latest.status] || latest.status}</b> · {latest.http_status ? `HTTP ${latest.http_status} · ` : ''}{latest.duration_ms != null ? `${integer(latest.duration_ms)} ms · ` : ''}verificada em {dateTime(latest.checked_at)}</p>
    {latest.detail && <p className="page-detail-note">{latest.detail}</p>}
    <ul className="page-detail-timeline" aria-label="Últimas verificações">{health.timeline.map((item, index) =>
      <li key={index} className={`is-${item.status}`} title={`${STATUS[item.status] || item.status} · ${dateTime(item.checked_at)}`}><span className="reports-sr-only">{STATUS[item.status]} em {dateTime(item.checked_at)}</span></li>)}</ul>
    <p className="page-detail-note">Disponibilidade técnica da página (resposta HTTP). Não mede velocidade de carregamento no navegador.</p>
  </>;
}

function PagePicker({data}) {
  const [sites, setSites] = useState(null);
  const [siteId, setSiteId] = useState('');
  const [pages, setPages] = useState(null);
  const [error, setError] = useState('');
  const client = data.client.client_id;
  useEffect(() => {
    json(`/connect/api/v2/reports/supertag/sites?client_id=${client}`).then(value => {
      const list = (value.sites || []).filter(site => !site.revoked_at);
      setSites(list);
      if (list.length === 1) setSiteId(list[0].id);
    }).catch(failure => setError(failure.message));
  }, [client]);
  useEffect(() => {
    if (!siteId) { setPages(null); return undefined; }
    let active = true;
    setPages(null);
    json(`/connect/api/v2/reports/supertag/sites/${siteId}/events?client_id=${client}`)
      .then(value => { if (active) setPages(value.pages || []); }).catch(failure => { if (active) setError(failure.message); });
    return () => { active = false; };
  }, [siteId, client]);
  if (error) return <div className="reports-error" role="alert">{error}</div>;
  if (!sites) return <div className="reports-loading" role="status">Carregando sites…</div>;
  if (!sites.length) return <Empty message="Instale a Super Tag em um site para ver os detalhes das páginas."/>;
  return <article className="reports-panel">
    <div className="reports-panel-head"><h2>Escolha uma página</h2><span>Últimos 30 dias</span></div>
    <label className="page-detail-picker">Site<ReportsNativeSelect value={siteId} onChange={event => setSiteId(event.target.value)} aria-label="Site">
      <option value="">Selecione…</option>{sites.map(site => <option key={site.id} value={site.id}>{site.label} · {site.allowed_host}</option>)}</ReportsNativeSelect></label>
    {siteId && (pages == null ? <div className="reports-loading" role="status">Carregando páginas…</div> :
      <Table head={['Página', 'Visualizações', 'Conversões']} empty="Nenhuma página recebeu visitas no período."
        rows={pages.map(page => [<a href={reportUrl('pages', {site_id: siteId, path: page.page_path})}>{page.page_path}</a>, number(page.views), number(page.conversions)])}/>)}
  </article>;
}

export function PageDetail({data}) {
  const query = new URLSearchParams(location.search);
  const siteId = query.get('site_id') || '';
  const path = query.get('path') || '';
  const [days, setDays] = useState(() => PERIODS.includes(Number(query.get('days'))) ? Number(query.get('days')) : 30);
  const [state, setState] = useState({loading: true, error: '', body: null});
  const client = data.client.client_id;
  useEffect(() => {
    if (!siteId || !path) return undefined;
    let active = true;
    setState({loading: true, error: '', body: null});
    json(`/connect/api/v2/reports/pages/overview?${new URLSearchParams({client_id: client, site_id: siteId, path, days})}`)
      .then(body => { if (active) setState({loading: false, error: '', body}); })
      .catch(failure => { if (active) setState({loading: false, error: failure.message, body: null}); });
    return () => { active = false; };
  }, [siteId, path, days, client]);
  useEffect(() => {
    if (!siteId || !path) return;
    const url = new URL(location.href);
    url.searchParams.set('days', String(days));
    history.replaceState(null, '', url);
  }, [days, siteId, path]);
  const body = state.body;
  const sources = useMemo(() => (body?.sources || []).map(item => ({key: item.platform, label: item.label, sessions: item.sessions, converted: item.converted_sessions})), [body]);
  const devices = useMemo(() => (body?.devices || []).map(item => ({key: item.device, label: item.label, sessions: item.sessions, converted: item.converted_sessions})), [body]);
  if (!siteId || !path) return <DomainsOverview data={data}/>;
  if (state.loading) return <div className="reports-loading" role="status">Carregando página…</div>;
  if (state.error) return <div className="reports-error" role="alert">{state.error} <a className="reports-inline-link" href={reportUrl('pages')}>Escolher outra página</a></div>;
  const m = body.metrics;
  const change = body.change || {};
  return <div className="page-detail">
    <header className="page-detail-head">
      <div><a className="reports-inline-link" href={reportUrl('pages')}>← Todas as páginas</a>
        <h2>{body.page.path}</h2>
        <p>{body.page.host} · {body.page.site_label}</p></div>
      <label>Período<ReportsNativeSelect value={days} onChange={event => setDays(Number(event.target.value))} aria-label="Período">
        {PERIODS.map(item => <option key={item} value={item}>Últimos {item} dias</option>)}</ReportsNativeSelect></label>
    </header>
    <p className="page-detail-scope" role="status">Super Tag · janela móvel de {body.window.days} dias até {dateTime(body.window.until)} · fuso {body.window.timezone}
      {body.previous_unavailable ? ` · ${body.previous_unavailable}` : ''}</p>
    {!body.has_data && <Empty message="Nenhuma visita registrada para esta página no período. Confira o caminho, o período e se a Super Tag está instalada."/>}
    {body.has_data && !m.reliable && <p className="page-detail-warning" role="note">Amostra pequena ({number(m.sessions)} sessões): percentuais variam muito com poucas visitas.</p>}
    {body.has_data && <>
      <Suggestions siteId={siteId} path={path} days={days} client={client}/>
      <section className="page-detail-kpis" id="numeros" aria-label="Números da página">
        <Metric label="Sessões" value={number(m.sessions)} change={change.sessions} hint="Sessões com ao menos uma visualização desta página"/>
        <Metric label="Visitantes únicos" value={number(m.visitors)} change={change.visitors}/>
        <Metric label="Conversão da sessão" value={percent(m.session_conversion_rate)} change={change.session_conversion_rate} unit="percent" hint="Sessões que converteram ÷ sessões da página"/>
        <Metric label="Taxa de saída" value={percent(m.exit_rate)} change={change.exit_rate} unit="percent"/>
        <Metric label="Tempo ativo médio" value={seconds(m.avg_active_seconds)} change={change.avg_active_seconds}/>
      </section>
      <div className="page-detail-grid">
        <article className="reports-panel"><div className="reports-panel-head"><h2>Origem do tráfego</h2><span>Sessões</span></div><Bars rows={sources}/></article>
        <article className="reports-panel"><div className="reports-panel-head"><h2>Dispositivos</h2><span>Sessões</span></div><Bars rows={devices}/></article>
        <article className="reports-panel"><div className="reports-panel-head"><h2>Rolagem</h2><span>% das sessões</span></div><Scroll metrics={m}/></article>
        <article className="reports-panel" id="comportamento"><div className="reports-panel-head"><h2>Comportamento</h2><span>No período</span></div>
          <dl className="page-detail-facts">
            <div><dt>Visualizações</dt><dd>{number(m.views)}</dd></div>
            <div><dt>Entradas</dt><dd>{number(m.entrances)}</dd></div>
            <div><dt>Saídas</dt><dd>{number(m.exits)}</dd></div>
            <div><dt>Visita de uma página</dt><dd>{percent(m.single_page_rate)}</dd></div>
            <div><dt>Tempo ativo mediano</dt><dd>{seconds(m.median_active_seconds)}</dd></div>
            <div><dt>Cliques por sessão</dt><dd>{m.clicks_per_session == null ? dash : m.clicks_per_session.toLocaleString('pt-BR')}</dd></div>
            <div><dt>Envios de formulário</dt><dd>{number(m.form_submits)}</dd></div>
            <div><dt>Conversões na página</dt><dd>{number(m.conversions_on_page)}</dd></div>
          </dl></article>
      </div>
    </>}
    <ConversionMap siteId={siteId} path={path} days={days} client={client}/>
    <Interactions siteId={siteId} path={path} days={days} client={client} metrics={m} canEdit={data.client.role !== 'viewer'} csrf={data.csrf}/>
    <article className="reports-panel" id="origem-paga"><div className="reports-panel-head"><h2>Origem paga</h2><span>Google Ads × Super Tag</span></div><PaidOrigin paid={body.paid}/></article>
    <article className="reports-panel" id="saude"><div className="reports-panel-head"><h2>Saúde da página</h2><span>Monitor HTTP</span></div><Health health={body.health}/></article>
    <details className="reports-panel page-detail-dictionary"><summary>Como lemos esses números</summary>
      <dl>{body.dictionary.map(item => <div key={item.key}><dt>{item.label} <small>({item.source})</small></dt><dd>{item.definition}</dd></div>)}</dl></details>
  </div>;
}
