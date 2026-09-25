import React, {useEffect, useMemo, useRef, useState} from 'react';
import {createRoot} from 'react-dom/client';
import './styles.css';

const SECTIONS = [
  ['overview', 'Visão geral', '◫'], ['accounts', 'Contas', '▤'],
  ['campaigns', 'Campanhas', '◎'], ['flow', 'Funnel Flow', '◇'],
  ['reports', 'Relatórios', '▥'], ['links', 'Link Tester', '↗'],
  ['imports', 'Importações', '⇧'], ['monitor', 'Monitoramentos', '◉'], ['access', 'Acesso', '♙'],
];
const TITLES = Object.fromEntries(SECTIONS.map(([id, title]) => [id, title]));
const formatter = new Intl.DateTimeFormat('pt-BR', {day: '2-digit', month: 'short', year: 'numeric'});
const shortDate = value => value ? formatter.format(new Date(/^\d{4}-\d{2}-\d{2}$/.test(value) ? `${value}T12:00:00` : value)) : '—';
const integer = value => new Intl.NumberFormat('pt-BR', {maximumFractionDigits: 0}).format(value || 0);
const decimal = value => new Intl.NumberFormat('pt-BR', {maximumFractionDigits: 1}).format(value || 0);
const money = (micros, currency) => micros == null || !currency ? '—' : new Intl.NumberFormat('pt-BR', {style: 'currency', currency}).format(micros / 1_000_000);
const sourceHealth = item => item.revoked_at ? 'Revogada' : !item.last_used_at ? 'Aguardando primeiro envio' : item.source_kind === 'google_ads_script' && Date.now() - new Date(item.last_used_at).getTime() > 48 * 3600 * 1000 ? 'Sem envio há 48 h' : 'Ativa';
const rootElement = document.getElementById('cadu-reports-v1-root');

async function json(url, options = {}) {
  const response = await fetch(url, {credentials: 'same-origin', ...options});
  let body = {};
  try { body = await response.json(); } catch (_) { /* The response may be an HTML error page. */ }
  if (!response.ok) throw new Error(body.error || body.description || `Falha HTTP ${response.status}`);
  return body;
}

function Chart({type = 'bar', labels, values, height = 260, horizontal = false}) {
  const host = useRef(null);
  useEffect(() => {
    if (!host.current || !window.ApexCharts || !values?.length) return undefined;
    const chart = new window.ApexCharts(host.current, {
      chart: {type, height, toolbar: {show: false}, animations: {enabled: false}, fontFamily: 'Inter, Arial, sans-serif'},
      series: [{name: 'Total', data: values}],
      colors: ['#2871d2'],
      dataLabels: {enabled: false},
      grid: {borderColor: '#e8edf2'},
      plotOptions: {bar: {horizontal, borderRadius: 5, columnWidth: '44%'}},
      xaxis: {categories: labels, labels: {style: {colors: '#64748b'}}},
      yaxis: {labels: {style: {colors: '#64748b'}}},
      tooltip: {theme: 'light'},
      legend: {show: false},
    });
    chart.render();
    return () => chart.destroy();
  }, [type, height, horizontal, JSON.stringify(labels), JSON.stringify(values)]);
  return values?.length ? <div ref={host} className="reports-chart" /> : <Empty message="O gráfico aparece quando houver dados para esta seleção." />;
}

function Empty({message}) { return <p className="reports-empty">{message}</p>; }

function Kpi({label, value, detail}) {
  return <article className="reports-kpi"><span>{label}</span><strong>{value}</strong><small>{detail}</small></article>;
}

function Overview({data, metrics}) {
  const platformCounts = Object.entries(data.accounts.reduce((out, account) => {
    if (account.account_kind === 'advertiser') out[account.platform] = (out[account.platform] || 0) + 1;
    return out;
  }, {}));
  return <>
    <section className="reports-grid reports-grid--four" aria-label="Resumo">
      <Kpi label="Investimento" value={money(metrics?.totals?.cost_micros, metrics?.currency)} detail={metrics?.currency ? `${metrics.period_days} dias · ${metrics.source}` : 'Selecione contas na mesma moeda'} />
      <Kpi label="Impressões" value={integer(metrics?.totals?.impressions)} detail={`${metrics?.period_days || 30} dias`} />
      <Kpi label="Cliques" value={integer(metrics?.totals?.clicks)} detail={`${metrics?.period_days || 30} dias`} />
      <Kpi label="Conversões da plataforma" value={decimal(metrics?.totals?.conversions)} detail="informadas pelo Google Ads" />
    </section>
    <section className="reports-grid reports-grid--three" aria-label="Conversões próprias"><Kpi label="Conversões no site" value={integer(metrics?.observed_conversions)} detail="visitantes em páginas marcadas" /><Kpi label="Confirmadas pelo CRM" value={integer(metrics?.confirmed_conversions)} detail="leads, qualificados e vendas" /><article className="reports-panel"><h2>Leituras independentes</h2><p>Google Ads, páginas e CRM medem momentos diferentes. Abra o Funnel Flow para ver a passagem entre etapas e a origem atribuída.</p><a className="reports-inline-link" href="#flow">Abrir Funnel Flow ↗</a></article></section>
    <section className="reports-grid reports-grid--three">
      <article className="reports-panel reports-span-two"><div className="reports-panel-head"><h2>Impressões por dia</h2><span>{metrics?.source || 'Aguardando fonte'}</span></div><Chart type="area" labels={(metrics?.days || []).map(item => shortDate(item.date))} values={(metrics?.days || []).map(item => item.impressions)} /></article>
      <article className="reports-panel"><div className="reports-panel-head"><h2>Atividade recente</h2><span>Link Tester</span></div>{data.link_tests.length ? data.link_tests.slice(0, 5).map(item => <div className="reports-row" key={item.id}><span>{item.final_url}</span><b>{item.score}/100</b></div>) : <Empty message="Os diagnósticos de links aparecerão aqui." />}</article>
    </section>
    <section className="reports-grid reports-grid--three"><article className="reports-panel"><div className="reports-panel-head"><h2>Contas por plataforma</h2><span>Inventário</span></div><Chart labels={platformCounts.map(([name]) => name)} values={platformCounts.map(([, count]) => count)} height={220} /></article><article className="reports-panel reports-span-two"><div className="reports-panel-head"><h2>Fontes de mídia</h2><span>Últimos {metrics?.period_days || 30} dias</span></div>{(metrics?.by_platform || []).length ? metrics.by_platform.map(item => <div className="reports-row" key={item.platform}><span>{item.platform}</span><b>{integer(item.clicks)} cliques · {money(item.cost_micros, metrics.currency)}</b></div>) : <Empty message="Conecte o script do Google Ads para receber métricas diárias." />}</article></section>
  </>;
}

function Accounts({data, save, busy}) {
  const [form, setForm] = useState({platform: 'google_ads', account_kind: 'advertiser', external_id: '', name: '', parent_account_id: ''});
  const managers = data.accounts.filter(account => account.account_kind === 'manager' && account.platform === form.platform);
  const submit = async event => {
    event.preventDefault();
    try {await save('/accounts', form); setForm({...form, external_id: '', name: '', parent_account_id: ''});}
    catch (_) { /* Global error banner shows the failure. */ }
  };
  return <section className="reports-grid reports-grid--three">
    <article className="reports-panel reports-span-two"><div className="reports-panel-head"><h2>Hierarquia de contas</h2><span>{data.accounts.length} contas</span></div>
      {data.accounts.length ? <div className="reports-table-wrap"><table><thead><tr><th>Conta</th><th>Plataforma</th><th>ID externo</th><th>Tipo</th><th>Gerente</th></tr></thead><tbody>{data.accounts.map(item => <tr key={item.id}><td><strong>{item.name}</strong></td><td>{item.platform}</td><td>{item.external_id}</td><td>{item.account_kind === 'manager' ? 'MCC / gerente' : 'Anunciante'}</td><td>{data.accounts.find(parent => parent.id === item.parent_account_id)?.name || '—'}</td></tr>)}</tbody></table></div> : <Empty message="Adicione uma conta para organizar campanhas e relatórios." />}
    </article>
    <article className="reports-panel"><div className="reports-panel-head"><h2>Adicionar conta</h2><span>Cadastro inicial</span></div><form className="reports-form" onSubmit={submit}>
      <label>Plataforma<select value={form.platform} onChange={event => setForm({...form, platform: event.target.value, parent_account_id: ''})}><option value="google_ads">Google Ads</option><option value="meta_ads">Meta Ads</option><option value="microsoft_ads">Microsoft Ads</option><option value="other">Outra</option></select></label>
      <label>Tipo<select value={form.account_kind} onChange={event => setForm({...form, account_kind: event.target.value, parent_account_id: ''})}><option value="advertiser">Conta de mídia</option><option value="manager">MCC / gerente</option></select></label>
      <label>Nome<input required maxLength="240" value={form.name} onChange={event => setForm({...form, name: event.target.value})} placeholder="Nome exibido na plataforma" /></label>
      <label>ID da conta<input required maxLength="160" value={form.external_id} onChange={event => setForm({...form, external_id: event.target.value})} placeholder="ID fornecido pela plataforma" /></label>
      {form.account_kind === 'advertiser' && managers.length > 0 && <label>Conta gerente<select value={form.parent_account_id} onChange={event => setForm({...form, parent_account_id: event.target.value})}><option value="">Sem gerente</option>{managers.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>}
      <button disabled={busy} type="submit">Salvar conta</button>
    </form></article>
  </section>;
}

function Campaigns({data, save, busy}) {
  const [form, setForm] = useState({account_id: '', external_id: '', name: ''});
  const accounts = data.accounts.filter(item => item.account_kind === 'advertiser');
  const submit = async event => {event.preventDefault(); try {await save('/campaigns', form); setForm({...form, external_id: '', name: ''});} catch (_) { /* Global error banner shows the failure. */ }};
  return <section className="reports-grid reports-grid--three"><article className="reports-panel reports-span-two"><div className="reports-panel-head"><h2>Campanhas</h2><span>{data.campaigns.length} cadastradas</span></div>
    {data.campaigns.length ? <div className="reports-table-wrap"><table><thead><tr><th>Campanha</th><th>Conta</th><th>Plataforma</th><th>ID externo</th><th>Status</th></tr></thead><tbody>{data.campaigns.map(item => <tr key={item.id}><td><strong>{item.name}</strong></td><td>{item.account_name}</td><td>{item.platform}</td><td>{item.external_id}</td><td>{item.status}</td></tr>)}</tbody></table></div> : <Empty message="As campanhas cadastradas e sincronizadas aparecerão aqui." />}</article>
    <article className="reports-panel"><div className="reports-panel-head"><h2>Adicionar campanha</h2><span>Cadastro inicial</span></div><form className="reports-form" onSubmit={submit}>
      <label>Conta<select required value={form.account_id} onChange={event => setForm({...form, account_id: event.target.value})}><option value="">Selecione</option>{accounts.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
      <label>Nome<input required maxLength="240" value={form.name} onChange={event => setForm({...form, name: event.target.value})} /></label>
      <label>ID da campanha<input required maxLength="160" value={form.external_id} onChange={event => setForm({...form, external_id: event.target.value})} /></label>
      <button disabled={busy || !accounts.length} type="submit">Salvar campanha</button>
    </form></article></section>;
}

function Reports({data, save, busy}) {
  const [form, setForm] = useState({campaign_name: '', media_campaign_id: ''});
  const [detail, setDetail] = useState(null);
  const [draft, setDraft] = useState({});
  const [note, setNote] = useState('');
  const [expiresDays, setExpiresDays] = useState('30');
  const [detailError, setDetailError] = useState('');
  useEffect(() => {setDetail(null); setDraft({}); setDetailError('');}, [data.client.client_id]);
  const submit = async event => {event.preventDefault(); try {await save('/workspaces', form); setForm({campaign_name: '', media_campaign_id: ''});} catch (_) { /* Global error banner shows the failure. */ }};
  const open = async (event, reportId) => {event.preventDefault(); setDetailError(''); try {const value = await json(`/connect/api/v1/reports/workspaces/${reportId}?client_id=${data.client.client_id}`); setDetail(value); setDraft(value.report.document || {}); setNote('');} catch (failure) {setDetailError(failure.message);}};
  const refresh = async reportId => {const value = await json(`/connect/api/v1/reports/workspaces/${reportId}?client_id=${data.client.client_id}`); setDetail(value); setDraft(value.report.document || {});};
  const update = async event => {event.preventDefault(); if (!detail) return; try {await save(`/workspaces/${detail.report.id}/document`, {revision: detail.report.revision, update_note: note, document: Object.fromEntries(['objective', 'goals', 'management_notes', 'start_date', 'end_date', 'accent'].map(field => [field, draft[field] || '']))}); await refresh(detail.report.id); setNote(''); setDetailError('');} catch (failure) {setDetailError(failure.message);}};
  const publish = async () => {if (!detail) return; try {await save(`/workspaces/${detail.report.id}/publish`, {expires_days: Number(expiresDays)}, false); await refresh(detail.report.id); setDetailError('');} catch (failure) {setDetailError(failure.message);}};
  const unpublish = async () => {if (!detail) return; try {await save(`/workspaces/${detail.report.id}/unpublish`, {}, false); await refresh(detail.report.id); setDetailError('');} catch (failure) {setDetailError(failure.message);}};
  const edit = (field, value) => setDraft({...draft, [field]: value});
  return <><section className="reports-grid reports-grid--four"><article className="reports-panel reports-span-three"><div className="reports-panel-head"><h2>Biblioteca</h2><span>{data.reports.length} relatórios</span></div><div className="reports-grid reports-grid--three">{data.reports.length ? data.reports.map(item => <a className="reports-panel reports-report-card" key={item.id} href={`/connect/relatorios?report_id=${item.id}`} onClick={event => open(event, item.id)}><span>Relatório · v{item.revision}</span><h2>{item.campaign_name}</h2><p>{item.project_ref || 'Espaço independente'}</p><small>Atualizado em {shortDate(item.updated_at)}</small></a>) : <Empty message="Crie um relatório independente ou associado a uma campanha." />}</div></article><article className="reports-panel"><div className="reports-panel-head"><h2>Novo relatório</h2><span>Reports</span></div>{data.client.role !== 'viewer' && <form className="reports-form" onSubmit={submit}><label>Nome<input required maxLength="200" value={form.campaign_name} onChange={event => setForm({...form, campaign_name: event.target.value})} placeholder="Ex.: Resultado de setembro" /></label><label>Campanha (opcional)<select value={form.media_campaign_id} onChange={event => setForm({...form, media_campaign_id: event.target.value})}><option value="">Sem campanha vinculada</option>{data.campaigns.map(item => <option key={item.id} value={item.id}>{item.account_name} · {item.name}</option>)}</select></label><button disabled={busy} type="submit">Criar relatório</button></form>}</article></section>
    {detailError && <p className="reports-error" role="alert">{detailError}</p>}
    {detail && <section className="reports-grid reports-grid--three" aria-label="Detalhe do relatório"><article className="reports-panel reports-span-two"><div className="reports-panel-head"><h2>{detail.report.campaign_name}</h2><span>Versão {detail.report.revision} · {shortDate(detail.report.updated_at)}</span></div><form className="reports-form" onSubmit={update}><label>Objetivo<textarea disabled={data.client.role === 'viewer'} maxLength="2000" rows="3" value={draft.objective || ''} onChange={event => edit('objective', event.target.value)} /></label><label>Metas<textarea disabled={data.client.role === 'viewer'} maxLength="4000" rows="3" value={draft.goals || ''} onChange={event => edit('goals', event.target.value)} /></label><label>Notas de gestão<textarea disabled={data.client.role === 'viewer'} maxLength="8000" rows="4" value={draft.management_notes || ''} onChange={event => edit('management_notes', event.target.value)} /></label><div className="reports-form-pair"><label>Início<input disabled={data.client.role === 'viewer'} type="date" value={draft.start_date || ''} onChange={event => edit('start_date', event.target.value)} /></label><label>Fim<input disabled={data.client.role === 'viewer'} type="date" value={draft.end_date || ''} onChange={event => edit('end_date', event.target.value)} /></label><label>Cor<input disabled={data.client.role === 'viewer'} type="color" value={draft.accent || '#1767c5'} onChange={event => edit('accent', event.target.value)} /></label></div>{data.client.role !== 'viewer' && <><label>Nota desta versão<input required maxLength="2000" value={note} onChange={event => setNote(event.target.value)} placeholder="O que mudou neste relatório?" /></label><button disabled={busy} type="submit">Salvar atualização</button></>}</form></article><article className="reports-panel"><div className="reports-panel-head"><h2>Publicação</h2><span>{detail.public_link ? 'Link ativo' : 'Privado'}</span></div>{detail.public_link ? <><p>{detail.public_link.expires_at ? `Relatório disponível para leitura até ${shortDate(detail.public_link.expires_at)}.` : 'Relatório disponível para leitura sem data de expiração.'}</p><a className="reports-inline-link" href={`/connect/r/${detail.public_link.token}`} target="_blank" rel="noopener noreferrer">Abrir link público ↗</a>{data.client.role !== 'viewer' && <p><button className="reports-text-button" type="button" disabled={busy} onClick={unpublish}>Revogar link</button></p>}</> : data.client.role !== 'viewer' ? <div className="reports-form"><label>Validade<select value={expiresDays} onChange={event => setExpiresDays(event.target.value)}><option value="7">7 dias</option><option value="30">30 dias</option><option value="90">90 dias</option><option value="0">Sem expiração</option></select></label><button type="button" disabled={busy} onClick={publish}>Publicar relatório</button></div> : <p>Este relatório ainda não foi publicado.</p>}<div className="reports-association-history"><h3>Versões</h3>{detail.versions.map(item => <p key={item.revision}>v{item.revision} · {item.note} · {shortDate(item.created_at)}</p>)}</div></article><article className="reports-panel reports-span-three"><div className="reports-panel-head"><h2>Fontes e evidências</h2><span>{detail.sources.length} fontes</span></div>{detail.sources.length ? detail.sources.map(item => <div className="reports-row" key={item.id}><span>{item.original_name} · {item.supplier || 'Fornecedor não informado'} · {item.status === 'reviewed' ? 'Revisada' : 'Aguardando revisão'}</span><a className="reports-inline-link" href={`/connect/relatorios/${detail.report.id}/fontes/${item.id}/revisar`}>Revisar ↗</a></div>) : <Empty message="As fontes recebidas aparecerão aqui." />}<a className="reports-inline-link" href={`/connect/relatorios?report_id=${detail.report.id}`}>Adicionar fontes ou editar identidade ↗</a></article></section>}
  </>;
}

function Links({data, save, busy}) {
  const [form, setForm] = useState({url: '', mode: 'destination'});
  const [result, setResult] = useState(null);
  const [suggestion, setSuggestion] = useState(null);
  const [editing, setEditing] = useState(null);
  const [campaignId, setCampaignId] = useState('');
  const [reportId, setReportId] = useState('');
  const [history, setHistory] = useState(null);
  const [aiStatus, setAiStatus] = useState(null);
  useEffect(() => {json('/connect/api/v1/reports/ai/status').then(setAiStatus).catch(() => setAiStatus(null));}, []);
  useEffect(() => {setEditing(null); setSuggestion(null); setHistory(null);}, [data.client.client_id]);
  const submit = async event => {event.preventDefault(); try {const body = await save('/link-tests', form); setResult(body.result);} catch (_) { /* Global error banner shows the failure. */ }};
  const choose = run => {setEditing(run); setSuggestion(null); setCampaignId(run.media_campaign_id ? String(run.media_campaign_id) : ''); setReportId(run.report_workspace_id ? String(run.report_workspace_id) : ''); setHistory(null);};
  const suggest = async run => {choose(run); try {const body = await save(`/link-tests/${run.id}/suggest-campaign`, {}, false); setSuggestion(body); if (body.suggestion) {setCampaignId(String(body.suggestion.id)); setReportId('');}} catch (_) { /* Global error banner shows the failure. */ }};
  const confirm = async event => {event.preventDefault(); if (!editing) return; try {await save(`/link-tests/${editing.id}/association`, {campaign_id: campaignId || null, report_id: reportId || null}); setEditing(null); setSuggestion(null); setHistory(null);} catch (_) { /* Global error banner shows the failure. */ }};
  const showHistory = async run => {choose(run); try {const body = await json(`/connect/api/v1/reports/link-tests/${run.id}/association-history?client_id=${data.client.client_id}`); setHistory(body.history);} catch (_) { /* Global error banner shows the failure. */ }};
  const selectedCampaign = data.campaigns.find(item => String(item.id) === campaignId);
  const availableReports = data.reports.filter(item => !item.media_campaign_id || String(item.media_campaign_id) === campaignId).filter(item => !item.account_id || item.account_id === selectedCampaign?.account_id);
  return <section className="reports-grid reports-grid--three"><article className="reports-panel"><div className="reports-panel-head"><h2>Testar destino</h2><span>Link Tester</span></div><form className="reports-form" onSubmit={submit}>
    <label>URL<input required type="url" maxLength="2048" value={form.url} onChange={event => setForm({...form, url: event.target.value})} placeholder="https://exemplo.com/pagina?utm_source=..." /></label>
    <label>Análise<select value={form.mode} onChange={event => setForm({...form, mode: event.target.value})}><option value="destination">Destino e redirecionamentos</option><option value="media">Medição de mídia</option><option value="agentic">Presença para agentes</option></select></label>
    <button disabled={busy} type="submit">Analisar link</button>
  </form></article><article className="reports-panel reports-span-two"><div className="reports-panel-head"><h2>Resultado</h2>{result && <span>{result.score}/100</span>}</div>{result ? <><strong className="reports-result-title">{result.status_label}</strong><p>{result.summary}</p><p className="reports-url">{result.final_url}</p>{result.alerts?.length > 0 && <ul className="reports-alerts">{result.alerts.map((alert, index) => <li key={index}>{alert}</li>)}</ul>}</> : <Empty message="Execute uma análise para ver o resultado e as evidências." />}</article>
    <article className="reports-panel reports-span-three"><div className="reports-panel-head"><h2>Histórico</h2><span>{data.link_tests.length} recentes</span></div>{aiStatus && !aiStatus.configured && <p className="reports-suggestion">TypeSafe ainda não está configurada nas Integrações do Cadu. IDs exatos de campanha continuam reconhecidos por regra; a revisão semântica fica disponível após configurar a chave.</p>}{data.link_tests.length ? <div className="reports-table-wrap"><table><thead><tr><th>Destino</th><th>Tipo</th><th>Resultado</th><th>Data</th><th>Associação confirmada</th><th>Ações</th></tr></thead><tbody>{data.link_tests.map(item => <tr key={item.id}><td>{item.final_url}</td><td>{item.mode}</td><td>{item.score}/100 · {item.status_label}</td><td>{shortDate(item.created_at)}</td><td>{item.campaign_name || 'Sem campanha'}{item.report_name ? ` · ${item.report_name}` : ''}</td><td><button type="button" className="reports-text-button" disabled={busy} onClick={() => choose(item)}>Associar</button> · <button type="button" className="reports-text-button" disabled={busy} onClick={() => suggest(item)}>Sugerir</button> · <button type="button" className="reports-text-button" onClick={() => showHistory(item)}>Decisões</button></td></tr>)}</tbody></table></div> : <Empty message="Os testes realizados neste cliente aparecerão aqui." />}</article>
    {editing && <article className="reports-panel reports-span-three"><div className="reports-panel-head"><h2>Associar link à operação</h2><span>Decisão do usuário · {editing.final_url}</span></div>{suggestion && <p className="reports-suggestion">{suggestion.suggestion ? <>Sugestão: <strong>{suggestion.suggestion.name}</strong> · {suggestion.model === 'exact_id' ? 'ID externo exato' : suggestion.model === 'exact_name' ? 'nome exato' : `confiança ${Math.round((suggestion.confidence || 0) * 100)}%`}. Confirme antes de salvar.</> : (suggestion.reason || 'Nenhuma campanha sugerida.')}{suggestion.page_role && <span className="reports-suggestion-role">Tipo provável de página: {({landing: 'entrada', form: 'formulário', thank_you: 'obrigado', content: 'conteúdo', unknown: 'indefinido'})[suggestion.page_role] || suggestion.page_role}.</span>}</p>}<form className="reports-form" onSubmit={confirm}><label>Campanha<select value={campaignId} onChange={event => {setCampaignId(event.target.value); setReportId('');}}><option value="">Sem campanha · limpar associação</option>{data.campaigns.map(item => <option key={item.id} value={item.id}>{item.account_name} · {item.name}</option>)}</select></label><label>Relatório (opcional)<select value={reportId} disabled={!campaignId} onChange={event => setReportId(event.target.value)}><option value="">Sem relatório</option>{availableReports.map(item => <option key={item.id} value={item.id}>{item.campaign_name}</option>)}</select></label>{data.client.role !== 'viewer' && <button type="submit" disabled={busy}>Confirmar associação</button>}</form>{history && <div className="reports-association-history"><h3>Decisões anteriores</h3>{history.length ? history.map((item, index) => <p key={`${item.decided_at}-${index}`}>{shortDate(item.decided_at)} · {item.action === 'clear' ? 'Associação removida' : `Campanha #${item.campaign_id}${item.report_id ? ` · relatório #${item.report_id}` : ''}`} · usuário #{item.decided_by}</p>) : <p>Nenhuma decisão anterior.</p>}</div>}</article>}
  </section>;
}

function Monitor({data, save, busy}) {
  const [keys, setKeys] = useState([]);
  const [runs, setRuns] = useState([]);
  const [label, setLabel] = useState('Google Ads · monitoramento');
  const [sourceKind, setSourceKind] = useState('google_ads_script');
  const [accountIds, setAccountIds] = useState('');
  const [script, setScript] = useState('');
  const [generatedKind, setGeneratedKind] = useState('google_ads_script');
  const [localError, setLocalError] = useState('');
  const reload = () => json(`/connect/api/v1/reports/ingest-keys?client_id=${data.client.client_id}`).then(value => {setKeys(value.keys); setRuns(value.runs || []);});
  useEffect(() => {reload().catch(failure => setLocalError(failure.message));}, [data.client.client_id]);
  const create = async event => {
    event.preventDefault();
    try {
      let template = '';
      if (sourceKind === 'google_ads_script') {
        const response = await fetch('/static/cadu_connect/google-ads-monitor.js', {credentials: 'same-origin'});
        if (!response.ok) throw new Error('Não foi possível carregar o script do Google Ads.');
        template = await response.text();
      }
      const selectedIds = accountIds.split(/[\s,;]+/).map(value => value.trim()).filter(Boolean);
      const created = await save('/ingest-keys', {label, source_kind: sourceKind, account_ids: sourceKind === 'google_ads_script' ? selectedIds : []}, false);
      if (sourceKind === 'google_ads_script') {
        const scriptIds = created.allowed_account_ids.map(id => `${id.slice(0, 3)}-${id.slice(3, 6)}-${id.slice(6)}`);
        setScript(template.replace('__CADU_INGEST_URL__', `${location.origin}/connect/api/v1/reports/ingest/google-ads`).replace('__CADU_API_KEY__', created.token).replace('__CADU_ACCOUNT_IDS__', JSON.stringify(scriptIds)));
      } else {
        setScript(`POST ${location.origin}/connect/api/v1/reports/ingest/conversions\nAuthorization: Bearer ${created.token}\nContent-Type: application/json\n\n${JSON.stringify({events: [{external_event_id: 'pedido-123', visitor_id: 'UUID recebido de window.CaduFlow.getVisitorId()', kind: 'sale', occurred_at: new Date().toISOString(), value_micros: 129000000, currency: 'BRL'}]}, null, 2)}`);
      }
      setGeneratedKind(sourceKind);
      await reload();
    } catch (failure) {setLocalError(failure.message);}
  };
  const revoke = async id => {
    if (!window.confirm('Revogar esta chave de ingestão? O script que a utiliza deixará de enviar dados.')) return;
    try {await save(`/ingest-keys/${id}/revoke`, {}, false); await reload();} catch (failure) {setLocalError(failure.message);}
  };
  return <section className="reports-grid reports-grid--three"><article className="reports-panel"><div className="reports-panel-head"><h2>Conectar fonte</h2><span>Instalação</span></div><p>Google Ads envia campanhas e métricas. O webhook recebe conversões confirmadas pelo CRM sem dados pessoais.</p>{data.client.role !== 'viewer' && <form className="reports-form" onSubmit={create}><label>Fonte<select value={sourceKind} onChange={event => {setSourceKind(event.target.value); setLabel(event.target.value === 'conversion_webhook' ? 'CRM · conversões' : 'Google Ads · monitoramento');}}><option value="google_ads_script">Google Ads Script</option><option value="conversion_webhook">CRM / conversões</option></select></label><label>Nome da instalação<input required maxLength="120" value={label} onChange={event => setLabel(event.target.value)} /></label>{sourceKind === 'google_ads_script' && <label>IDs das contas na MCC (obrigatório em MCC)<input value={accountIds} onChange={event => setAccountIds(event.target.value)} placeholder="123-456-7890, 987-654-3210" /><small>Separe por vírgula. Deixe vazio apenas se instalar diretamente em uma única conta; a chave ficará vinculada à primeira conta que enviar dados.</small></label>}<button disabled={busy} type="submit">Gerar chave</button></form>}{localError && <p className="reports-error">{localError}</p>}</article><article className="reports-panel reports-span-two"><div className="reports-panel-head"><h2>Chaves de ingestão</h2><span>{keys.length} criadas</span></div>{keys.length ? <div className="reports-table-wrap"><table><thead><tr><th>Nome</th><th>Fonte</th><th>Contas permitidas</th><th>Último envio</th><th>Estado</th><th></th></tr></thead><tbody>{keys.map(item => <tr key={item.id}><td>{item.label}</td><td>{item.source_kind === 'conversion_webhook' ? 'CRM' : 'Google Ads'}</td><td>{item.source_kind === 'google_ads_script' ? item.allowed_account_ids?.length ? item.allowed_account_ids.join(', ') : item.bound_account_id || 'Vincula no primeiro envio' : '—'}</td><td>{shortDate(item.last_used_at)}</td><td>{sourceHealth(item)}</td><td>{!item.revoked_at && data.client.role !== 'viewer' && <button className="reports-text-button" disabled={busy} onClick={() => revoke(item.id)}>Revogar</button>}</td></tr>)}</tbody></table></div> : <Empty message="Gere uma chave para conectar uma fonte." />}</article>{script && <article className="reports-panel reports-span-three"><div className="reports-panel-head"><h2>{generatedKind === 'conversion_webhook' ? 'Contrato do webhook' : 'Script gerado'}</h2><span>Copie agora: a chave não será mostrada novamente</span></div><textarea className="reports-code" readOnly value={script} aria-label="Código da integração" /><button className="reports-copy" onClick={() => navigator.clipboard.writeText(script)}>Copiar</button></article>}<article className="reports-panel reports-span-three"><div className="reports-panel-head"><h2>Últimos envios do Google Ads</h2><span>{runs.length} lotes</span></div>{runs.length ? <div className="reports-table-wrap"><table><thead><tr><th>Recebido</th><th>Período</th><th>Linhas</th><th>Estado</th></tr></thead><tbody>{runs.map(item => <tr key={item.id}><td>{shortDate(item.created_at)}</td><td>{shortDate(item.period_start)} – {shortDate(item.period_end)}</td><td>{integer(item.record_count)}</td><td>{item.status === 'completed' ? 'Concluído' : item.status}</td></tr>)}</tbody></table></div> : <Empty message="Os lotes recebidos aparecerão aqui." />}</article></section>;
}

function Access({data, save, busy}) {
  const [users, setUsers] = useState([]);
  const [userId, setUserId] = useState('');
  const [role, setRole] = useState('viewer');
  const [exclusive, setExclusive] = useState(false);
  const [localError, setLocalError] = useState('');
  const reload = () => json(`/connect/api/v1/reports/access?client_id=${data.client.client_id}`).then(value => setUsers(value.users));
  useEffect(() => {reload().catch(error => setLocalError(error.message));}, [data.client.client_id]);
  const choose = value => {
    setUserId(value);
    const selected = users.find(item => String(item.id) === value);
    setRole(selected?.role && !selected.revoked_at ? selected.role : 'viewer');
    setExclusive(Boolean(selected?.reports_only));
  };
  const grant = async event => {
    event.preventDefault();
    try {await save('/access', {user_id: Number(userId), role, exclusive}, false); await reload(); setLocalError('');}
    catch (error) {setLocalError(error.message);}
  };
  const revoke = async user => {
    if (!window.confirm(`Remover o acesso de ${user.name} a este cliente no Reports?`)) return;
    try {await save(`/access/${user.id}/revoke`, {}, false); await reload(); setLocalError('');}
    catch (error) {setLocalError(error.message);}
  };
  return <section className="reports-grid reports-grid--three">
    <article className="reports-panel"><div className="reports-panel-head"><h2>Conceder acesso</h2><span>{data.client.client_name}</span></div>
      <p>Selecione uma conta existente da organização. O acesso exclusivo permite usar Reports sem abrir os demais módulos do Cadu.</p>
      {localError && <p className="reports-error" role="alert">{localError}</p>}
      <form className="reports-form" onSubmit={grant}><label>Usuário<select required value={userId} onChange={event => choose(event.target.value)}><option value="">Selecione</option>{users.map(user => <option key={user.id} value={user.id}>{user.name} · {user.email}</option>)}</select></label><label>Papel<select value={role} onChange={event => setRole(event.target.value)}><option value="viewer">Visualização</option><option value="member">Operação</option><option value="admin">Administração de dados</option></select></label><label className="reports-checkbox"><input type="checkbox" checked={exclusive} onChange={event => setExclusive(event.target.checked)} />Acesso exclusivo ao Reports</label><button disabled={busy || !userId} type="submit">Salvar acesso</button></form>
    </article>
    <article className="reports-panel reports-span-two"><div className="reports-panel-head"><h2>Usuários deste cliente</h2><span>{users.filter(user => user.role && !user.revoked_at).length} ativos</span></div>
      {users.some(user => user.role && !user.revoked_at) ? <div className="reports-table-wrap"><table><thead><tr><th>Usuário</th><th>Papel</th><th>Tipo</th><th></th></tr></thead><tbody>{users.filter(user => user.role && !user.revoked_at).map(user => <tr key={user.id}><td>{user.name}</td><td>{user.role}</td><td>{user.reports_only ? 'Só Reports' : 'Cadu + Reports'}</td><td><button className="reports-text-button" disabled={busy} onClick={() => revoke(user)}>Revogar</button></td></tr>)}</tbody></table></div> : <Empty message="Nenhum acesso próprio do Reports concedido para este cliente." />}
    </article>
  </section>;
}

function Flow({data, save, busy, filters}) {
  const [flow, setFlow] = useState({tags: [], steps: [], activity: [], online: 0, conversions: 0, confirmed: []});
  const [tagForm, setTagForm] = useState({label: '', allowed_host: ''});
  const [stepForm, setStepForm] = useState({tag_id: '', name: '', path_prefix: '/', step_kind: 'page', campaign_id: '', position: 0});
  const [localError, setLocalError] = useState('');
  const reload = () => {
    const params = new URLSearchParams({client_id: String(data.client.client_id), days: filters.period});
    if (filters.platform) params.set('platform', filters.platform);
    if (filters.account) params.set('account_id', filters.account);
    if (filters.campaign) params.set('campaign_id', filters.campaign);
    return json(`/connect/api/v1/reports/flow?${params}`).then(setFlow);
  };
  useEffect(() => {reload().catch(failure => setLocalError(failure.message));}, [data.client.client_id, filters.period, filters.platform, filters.account, filters.campaign]);
  const createTag = async event => {event.preventDefault(); try {await save('/flow/tags', tagForm, false); setTagForm({label: '', allowed_host: ''}); await reload();} catch (failure) {setLocalError(failure.message);}};
  const createStep = async event => {event.preventDefault(); try {await save('/flow/steps', stepForm, false); setStepForm({...stepForm, name: '', path_prefix: '/', position: Number(stepForm.position) + 1}); await reload();} catch (failure) {setLocalError(failure.message);}};
  const revokeTag = async tag => {if (!window.confirm(`Revogar a tag ${tag.label}?`)) return; try {await save(`/flow/tags/${tag.id}/revoke`, {}, false); await reload();} catch (failure) {setLocalError(failure.message);}};
  const archiveStep = async step => {if (!window.confirm(`Arquivar a etapa ${step.name}?`)) return; try {await save(`/flow/steps/${step.id}/archive`, {}, false); await reload();} catch (failure) {setLocalError(failure.message);}};
  const activeTags = flow.tags.filter(item => !item.revoked_at);
  return <>
    <section className="reports-grid reports-grid--four"><Kpi label="Tags ativas" value={integer(activeTags.length)} detail="Domínios autorizados" /><Kpi label="Sessões online" value={integer(flow.online)} detail="Sinal nos últimos 90 s" /><Kpi label="Visitas" value={integer(flow.activity.reduce((sum, item) => sum + Number(item.views || 0), 0))} detail={`Últimos ${flow.period_days || 30} dias`} /><Kpi label="Conversões" value={integer(flow.conversions)} detail="Visitantes em páginas de obrigado" /></section>
    {localError && <div className="reports-error" role="alert">{localError}</div>}
    <section className="reports-grid reports-grid--three"><article className="reports-panel"><div className="reports-panel-head"><h2>Instalar a tag</h2><span>Código direto ou GTM</span></div><p>Instale a mesma tag em todas as páginas do fluxo. O domínio informado limita de onde ela aceita eventos.</p><p>No GTM, use HTML personalizado após o disparo de medição definido pelo site. Em páginas SPA, adicione um gatilho de mudança de histórico que chame <code>window.CaduFlow &amp;&amp; window.CaduFlow.trackPage()</code> após a URL mudar.</p>{data.client.role !== 'viewer' && <form className="reports-form" onSubmit={createTag}><label>Nome<input required maxLength="120" value={tagForm.label} onChange={event => setTagForm({...tagForm, label: event.target.value})} placeholder="Site principal" /></label><label>Domínio<input required value={tagForm.allowed_host} onChange={event => setTagForm({...tagForm, allowed_host: event.target.value})} placeholder="exemplo.com.br" /></label><button disabled={busy} type="submit">Criar instalação</button></form>}</article>
      <article className="reports-panel reports-span-two"><div className="reports-panel-head"><h2>Instalações</h2><span>{activeTags.length} ativas</span></div>{flow.tags.length ? flow.tags.map(tag => <div className="reports-tag-card" key={tag.id}><strong>{tag.label}</strong><small>{tag.allowed_host} · {tag.revoked_at ? 'revogada' : 'ativa'}</small>{!tag.revoked_at && <><code>{`<script async src="${location.origin}/static/cadu_connect/cadu-flow-tag.js" data-cadu-key="${tag.public_key}"></script>`}</code><button className="reports-text-button" type="button" onClick={() => navigator.clipboard.writeText(`<script async src="${location.origin}/static/cadu_connect/cadu-flow-tag.js" data-cadu-key="${tag.public_key}"></script>`)}>Copiar tag</button>{data.client.role !== 'viewer' && <button className="reports-text-button" type="button" disabled={busy} onClick={() => revokeTag(tag)}>Revogar</button>}</>}</div>) : <Empty message="Crie uma instalação para começar a medir páginas e conversões." />}</article></section>
    <section className="reports-grid reports-grid--three"><article className="reports-panel"><div className="reports-panel-head"><h2>Mapear etapa</h2><span>Funnel Flow</span></div>{data.client.role !== 'viewer' && <form className="reports-form" onSubmit={createStep}><label>Instalação<select required value={stepForm.tag_id} onChange={event => setStepForm({...stepForm, tag_id: event.target.value})}><option value="">Selecione</option>{activeTags.map(tag => <option key={tag.id} value={tag.id}>{tag.label}</option>)}</select></label><label>Nome<input required maxLength="120" value={stepForm.name} onChange={event => setStepForm({...stepForm, name: event.target.value})} placeholder="Página de obrigado" /></label><label>Caminho da URL<input required maxLength="500" value={stepForm.path_prefix} onChange={event => setStepForm({...stepForm, path_prefix: event.target.value})} placeholder="/obrigado" /></label><label>Tipo<select value={stepForm.step_kind} onChange={event => setStepForm({...stepForm, step_kind: event.target.value})}><option value="page">Página</option><option value="conversion">Conversão</option></select></label><label>Campanha (opcional)<select value={stepForm.campaign_id} onChange={event => setStepForm({...stepForm, campaign_id: event.target.value})}><option value="">Sem campanha</option>{data.campaigns.map(item => <option key={item.id} value={item.id}>{item.account_name} · {item.name}</option>)}</select></label><button disabled={busy || !activeTags.length} type="submit">Salvar etapa</button></form>}</article>
      <article className="reports-panel reports-span-two"><div className="reports-panel-head"><h2>Fluxo configurado</h2><span>{flow.steps.length} etapas · {flow.period_days || 30} dias</span></div>{flow.steps.length ? flow.tags.map(tag => {const stages = flow.steps.filter(step => step.tag_id === tag.id); return stages.length ? <div className="reports-flow-group" key={tag.id}><strong>{tag.label}</strong><div className="reports-flow-rail">{stages.map((step, index) => {const previous = stages[index - 1]; const rate = previous?.reached ? Math.round(Number(step.progressed) / Number(previous.reached) * 100) : null; return <article className={`reports-flow-node${step.step_kind === 'conversion' ? ' is-conversion' : ''}`} key={step.id}><small>{step.step_kind === 'conversion' ? 'Conversão' : `Etapa ${index + 1}`}</small><strong>{step.name}</strong><span>{step.path_prefix}</span><b>{integer(step.reached)} sessões</b><em>{index ? `${integer(step.progressed)} vieram da anterior${rate === null ? '' : ` · ${rate}%`}` : 'Entrada do fluxo'}</em>{data.client.role !== 'viewer' && <button type="button" className="reports-text-button" disabled={busy} onClick={() => archiveStep(step)}>Arquivar</button>}</article>;})}</div></div> : null;}) : <Empty message="Defina as páginas e marque a URL de obrigado como conversão." />}</article></section>
    <section className="reports-grid reports-grid--three"><article className="reports-panel reports-span-three"><div className="reports-panel-head"><h2>Conversões confirmadas</h2><a className="reports-inline-link" href="#monitor">Conectar CRM ↗</a></div><p>O acesso à página de obrigado mede a conclusão do fluxo no site. O CRM pode confirmar lead, qualificação ou venda pelo webhook.</p><div className="reports-confirmed-grid">{[['lead', 'Leads'], ['qualified_lead', 'Qualificados'], ['sale', 'Vendas']].map(([kind, label]) => <Kpi key={kind} label={label} value={integer(flow.confirmed.find(item => item.conversion_kind === kind)?.total)} detail={`${flow.period_days || 30} dias · CRM`} />)}</div></article></section>
    <section className="reports-panel"><div className="reports-panel-head"><h2>Páginas monitoradas</h2><button className="reports-text-button" type="button" onClick={() => reload().catch(failure => setLocalError(failure.message))}>Atualizar</button></div>{flow.activity.length ? <div className="reports-table-wrap"><table><thead><tr><th>Página</th><th>Visitas</th><th>Visitantes estimados</th><th>Online</th><th>Conversões</th></tr></thead><tbody>{flow.activity.map(item => <tr key={`${item.tag_id}:${item.page_path}`}><td>{item.page_path}</td><td>{integer(item.views)}</td><td>{integer(item.visitors)}</td><td>{integer(item.online)}</td><td>{integer(item.conversions)}</td></tr>)}</tbody></table></div> : <Empty message="As páginas aparecerão após a primeira visita com a tag instalada." />}</section>
  </>;
}

function Imports({data, reloadBootstrap}) {
  const [items, setItems] = useState([]);
  const [ready, setReady] = useState(true);
  const [detail, setDetail] = useState(null);
  const [editing, setEditing] = useState(null);
  const [draft, setDraft] = useState({});
  const [file, setFile] = useState(null);
  const [platform, setPlatform] = useState('');
  const [currency, setCurrency] = useState('');
  const [dateOrder, setDateOrder] = useState('auto');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [note, setNote] = useState('');
  const base = `/connect/api/v1/reports/imports?client_id=${data.client.client_id}`;
  const refresh = async () => {const body = await json(base); setReady(body.ready); setItems(body.imports || []);};
  useEffect(() => {setDetail(null); setEditing(null); refresh().catch(failure => setError(failure.message));}, [data.client.client_id]);
  const open = async id => {try {setDetail(await json(`/connect/api/v1/reports/imports/${id}?client_id=${data.client.client_id}`)); setError('');} catch (failure) {setError(failure.message);}};
  const edit = row => {setEditing(row.id); setDraft({...row.parsed, metric_date: row.parsed.metric_date || '', ...row.parsed.metrics, note: ''});};
  const resolve = async event => {
    event.preventDefault(); setBusy(true); setError('');
    try {
      const payload = Object.fromEntries(['platform','external_account_id','account_name','external_campaign_id','campaign_name','metric_date','currency','impressions','clicks','cost','conversions','conversion_value','note'].map(key => [key, String(draft[key] || '')]));
      await json(`/connect/api/v1/reports/imports/${detail.import_file.id}/rows/${editing}/resolve?client_id=${data.client.client_id}`, {method: 'POST', headers: {'Content-Type': 'application/json','X-CSRF-Token': data.csrf}, body: JSON.stringify(payload)});
      setEditing(null); await open(detail.import_file.id); await refresh(); await reloadBootstrap();
    } catch (failure) {setError(failure.message);} finally {setBusy(false);}
  };
  const extract = async () => {
    setBusy(true); setError('');
    try {
      await json(`/connect/api/v1/reports/imports/${detail.import_file.id}/extract?client_id=${data.client.client_id}`, {method: 'POST', headers: {'X-CSRF-Token': data.csrf}});
      await open(detail.import_file.id); await refresh();
    } catch (failure) {setError(failure.message);} finally {setBusy(false);}
  };
  const submit = async event => {
    event.preventDefault(); if (!file) return;
    setBusy(true); setError(''); setNote('');
    try {
      const payload = new FormData(); payload.append('file', file);
      if (platform) payload.append('platform_hint', platform);
      if (currency) payload.append('currency_hint', currency.toUpperCase());
      payload.append('date_order', dateOrder);
      const result = await json(base, {method: 'POST', headers: {'X-CSRF-Token': data.csrf}, body: payload});
      setNote(result.duplicate ? 'Este arquivo já foi importado para o cliente.' : `${result.applied_count || 0} de ${result.row_count || 0} linhas prontas para reconciliação.`);
      await refresh(); await open(result.import_id); await reloadBootstrap();
      event.target.reset(); setFile(null);
    } catch (failure) {setError(failure.message);} finally {setBusy(false);}
  };
  return <section className="reports-grid reports-grid--three">
    <article className="reports-panel"><div className="reports-panel-head"><h2>Enviar dados</h2><span>CSV · XLSX · print</span></div><p>Exporte da plataforma ou envie uma captura. Identificamos contas e campanhas pelos IDs da origem.</p>{!ready && <p className="reports-error">A migração de importações precisa ser aplicada neste ambiente.</p>}{ready && data.client.role !== 'viewer' && <form className="reports-form" onSubmit={submit}><label>Arquivo<input type="file" accept=".csv,.xlsx,.png,.jpg,.jpeg,.webp" required onChange={event => setFile(event.target.files?.[0] || null)} /></label><label>Plataforma, se não estiver no arquivo<input value={platform} onChange={event => setPlatform(event.target.value)} placeholder="Ex.: Google Ads, Meta Ads" /></label><label>Moeda, se houver valores<input maxLength="3" value={currency} onChange={event => setCurrency(event.target.value)} placeholder="BRL" /></label><label>Datas com barras<select value={dateOrder} onChange={event => setDateOrder(event.target.value)}><option value="auto">Detectar; revisar datas ambíguas</option><option value="dmy">Dia/mês/ano</option><option value="mdy">Mês/dia/ano</option></select></label><button disabled={busy || !file}>Enviar arquivo</button></form>}{note && <p>{note}</p>}{error && <p className="reports-error" role="alert">{error}</p>}</article>
    <article className="reports-panel reports-span-two"><div className="reports-panel-head"><h2>Arquivos recebidos</h2><span>{items.length} recentes</span></div>{items.length ? <div className="reports-table-wrap"><table><thead><tr><th>Arquivo</th><th>Estado</th><th>Linhas</th><th>Recebido</th><th></th></tr></thead><tbody>{items.map(item => <tr key={item.id}><td>{item.original_name}</td><td>{({parsed:'Lido',needs_review:'Revisão necessária',awaiting_extraction:'Aguardando leitura visual'})[item.status] || item.status}</td><td>{item.applied_count}/{item.row_count}</td><td>{shortDate(item.created_at)}</td><td><button className="reports-text-button" onClick={() => open(item.id)}>Abrir</button></td></tr>)}</tbody></table></div> : <Empty message="Nenhum arquivo enviado para este cliente." />}</article>
    {detail && <article className="reports-panel reports-span-three"><div className="reports-panel-head"><h2>{detail.import_file.original_name}</h2><span>{detail.import_file.row_count} linhas</span></div>{detail.import_file.file_kind === 'image' ? <>{detail.visual ? <><p>Leitura visual sugerida por {detail.visual.model}. Confira o print antes de usar qualquer número.</p>{detail.visual.result.scopes.map((scope,index) => <div className="reports-suggestion" key={index}><strong>Bloco {index + 1}: {scope.platform || 'Plataforma não identificada'} · {scope.account_name || scope.account_id || 'Conta não identificada'} · {scope.campaign_name || scope.campaign_id || 'Campanha não identificada'}</strong><p>{scope.period_start || 'Período não identificado'}{scope.period_end && scope.period_end !== scope.period_start ? ` a ${scope.period_end}` : ''} · {scope.granularity || 'Granularidade indefinida'} · {scope.currency || 'Moeda não identificada'}</p><small>Evidência: {scope.evidence}</small>{scope.metrics.length ? <ul>{scope.metrics.map((metric,metricIndex) => <li key={metricIndex}>{metric.label}: {metric.raw_value} {metric.unit} · {metric.evidence}</li>)}</ul> : <p>Sem métricas legíveis neste bloco.</p>}</div>)}{detail.visual.result.questions.map((question,index) => <p key={index}>{question}</p>)}</> : <><p>Print recebido. A leitura visual consome créditos Cadu e gera sugestões com evidências; nenhuma campanha ou métrica é confirmada automaticamente.</p>{data.client.role !== 'viewer' && <button type="button" className="reports-text-button" disabled={busy} onClick={extract}>Ler print com IA</button>}</>}</> : <><div className="reports-table-wrap"><table><thead><tr><th>Linha</th><th>Plataforma</th><th>Conta</th><th>Campanha</th><th>Data</th><th>Estado</th><th></th></tr></thead><tbody>{detail.rows.map(row => <tr key={row.id}><td>{row.sheet_name} · {row.source_row}</td><td>{row.parsed.platform || '—'}</td><td>{row.parsed.account_name || row.parsed.external_account_id || '—'}</td><td>{row.parsed.campaign_name || row.parsed.external_campaign_id || '—'}</td><td>{row.metric_date || '—'}</td><td>{row.reason || (row.decision_note ? `Confirmada: ${row.decision_note}` : 'Pronta para reconciliação')}</td><td>{row.status === 'needs_review' && data.client.role !== 'viewer' && <button type="button" className="reports-text-button" onClick={() => edit(row)}>Revisar</button>}</td></tr>)}</tbody></table></div><small>Mostrando até 100 linhas, com pendências primeiro. Os valores confirmados ainda aguardam a projeção de métricas.</small></>}</article>}
    {editing && <article className="reports-panel reports-span-three"><div className="reports-panel-head"><h2>Revisar linha</h2><button type="button" className="reports-text-button" onClick={() => setEditing(null)}>Fechar</button></div><form className="reports-form" onSubmit={resolve}><div className="reports-form-pair">{[['platform','Plataforma'],['external_account_id','ID da conta'],['account_name','Nome da conta'],['external_campaign_id','ID da campanha'],['campaign_name','Nome da campanha'],['metric_date','Data ISO (AAAA-MM-DD)'],['currency','Moeda'],['impressions','Impressões'],['clicks','Cliques'],['cost','Custo'],['conversions','Conversões'],['conversion_value','Valor das conversões']].map(([key,label]) => <label key={key}>{label}<input value={draft[key] || ''} onChange={event => setDraft({...draft,[key]:event.target.value})} /></label>)}</div><label>Justificativa<input required maxLength="1000" value={draft.note || ''} onChange={event => setDraft({...draft,note:event.target.value})} placeholder="Ex.: data e conta conferidas no export original" /></label><button disabled={busy}>Confirmar linha</button></form></article>}
  </section>;
}

function App() {
  const [section, setSection] = useState(() => location.hash.slice(1) || 'overview');
  const [data, setData] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [filters, setFilters] = useState({platform: '', account: '', campaign: '', period: '30'});
  const clientId = new URLSearchParams(location.search).get('client_id');
  const load = async () => {
    try {setData(await json(`/connect/api/v1/reports/bootstrap${clientId ? `?client_id=${encodeURIComponent(clientId)}` : ''}`)); setError('');}
    catch (failure) {setError(failure.message);}
  };
  useEffect(() => {load(); const onHash = () => setSection(location.hash.slice(1) || 'overview'); addEventListener('hashchange', onHash); return () => removeEventListener('hashchange', onHash);}, []);
  useEffect(() => {
    if (!data?.ready) return undefined;
    let cancelled = false;
    const params = new URLSearchParams({client_id: String(data.client.client_id), days: filters.period});
    if (filters.platform) params.set('platform', filters.platform);
    if (filters.account) params.set('account_id', filters.account);
    if (filters.campaign) params.set('campaign_id', filters.campaign);
    json(`/connect/api/v1/reports/metrics?${params}`).then(value => {if (!cancelled) setMetrics(value);}).catch(failure => {if (!cancelled) setError(failure.message);});
    return () => {cancelled = true;};
  }, [data?.client?.client_id, data?.ready, filters.platform, filters.account, filters.campaign, filters.period]);
  const save = async (path, payload, reload = true) => {
    setBusy(true); setError('');
    try {
      const result = await json(`/connect/api/v1/reports${path}`, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': data.csrf}, body: JSON.stringify({...payload, client_id: data.client.client_id})});
      if (reload) await load();
      return result;
    } catch (failure) {setError(failure.message); throw failure;} finally {setBusy(false);}
  };
  const selected = useMemo(() => {
    if (!data) return null;
    const accounts = data.accounts.filter(item => (!filters.platform || item.platform === filters.platform) && (!filters.account || String(item.id) === filters.account));
    const ids = new Set(accounts.map(item => item.id));
    return {...data, accounts, campaigns: data.campaigns.filter(item => ids.has(item.account_id) && (!filters.campaign || String(item.id) === filters.campaign))};
  }, [data, filters]);
  return <div className="reports-shell">
    <nav className="reports-dock" aria-label="Soluções Cadu"><a className="reports-dock-logo" href="/connect/app" title="Reports" aria-label="Reports"><img src="/static/images/cadu/brand-icons/connect-192.png" alt="" /></a><a href={rootElement.dataset.workspaceUrl} title="Workspace" aria-label="Workspace">⌂</a><a href={rootElement.dataset.plannerUrl} title="Planner" aria-label="Planner">◈</a></nav>
    <aside className="reports-sidebar"><div className="reports-brand"><span className="reports-brand-mark"><img src="/static/images/cadu/brand-icons/connect-192.png" alt="" /></span><div><strong>Reports</strong><small>Operação de mídia</small></div></div><p className="reports-sidebar-label">NAVEGAÇÃO</p><nav aria-label="Áreas do Reports">{SECTIONS.filter(([id]) => id !== 'access' || data?.can_manage_access).map(([id, title, glyph]) => <a key={id} href={`#${id}`} aria-current={section === id ? 'page' : undefined}><span>{glyph}</span>{title}</a>)}</nav><div className="reports-sidebar-foot"><strong>{data?.client?.client_name || 'Cliente'}</strong><small>Espaço #{data?.client?.client_id || '—'}</small></div></aside>
    <main className="reports-main"><header className="reports-header"><div><p>REPORTS / {TITLES[section] || 'Visão geral'}</p><h1>{TITLES[section] || 'Visão geral'}</h1></div><div className="reports-header-actions"><select className="reports-client-pill" aria-label="Cliente" value={data?.client?.client_id || ''} onChange={event => {location.href = `/connect/app?client_id=${encodeURIComponent(event.target.value)}#${section}`;}}>{(data?.clients || []).map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select><a href="/connect/relatorios">Biblioteca atual ↗</a></div></header>
      <div className="reports-filters reports-filters--primary" aria-label="Filtros principais"><label>Período<select value={filters.period} onChange={event => setFilters({...filters, period: event.target.value})}><option value="7">7 dias</option><option value="30">30 dias</option><option value="90">90 dias</option></select></label><label>Plataforma<select value={filters.platform} onChange={event => setFilters({...filters, platform: event.target.value, account: '', campaign: ''})}><option value="">Todas</option>{[...new Set((data?.accounts || []).map(item => item.platform))].map(value => <option key={value} value={value}>{value}</option>)}</select></label><label>Conta<select value={filters.account} onChange={event => setFilters({...filters, account: event.target.value, campaign: ''})}><option value="">Todas</option>{(data?.accounts || []).filter(item => item.account_kind === 'advertiser' && (!filters.platform || item.platform === filters.platform)).map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Campanha<select value={filters.campaign} onChange={event => setFilters({...filters, campaign: event.target.value})}><option value="">Todas</option>{(data?.campaigns || []).filter(item => !filters.account || String(item.account_id) === filters.account).map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label></div>
      <div className="reports-filters reports-filters--secondary" aria-label="Filtros e estado"><span>Fonte de mídia: Google Ads Script</span><span>Páginas e CRM: medição própria</span><button type="button" onClick={load}>Atualizar</button></div>
      <div className="reports-content">{error && <div className="reports-error" role="alert">{error}</div>}{!data ? <Empty message="Carregando Reports…" /> : !data.ready ? <Empty message="A base de Reports V1 ainda precisa da migração de dados." /> : section === 'accounts' ? <Accounts data={selected} save={save} busy={busy} /> : section === 'campaigns' ? <Campaigns data={selected} save={save} busy={busy} /> : section === 'reports' ? <Reports data={selected} save={save} busy={busy} /> : section === 'links' ? <Links data={data} save={save} busy={busy} /> : section === 'imports' ? <Imports data={data} reloadBootstrap={load} /> : section === 'monitor' ? <Monitor data={data} save={save} busy={busy} /> : section === 'flow' ? <Flow data={data} save={save} busy={busy} filters={filters} /> : section === 'access' && data.can_manage_access ? <Access data={data} save={save} busy={busy} /> : <Overview data={selected} metrics={metrics} />}</div>
    </main>
  </div>;
}

createRoot(rootElement).render(<App />);
