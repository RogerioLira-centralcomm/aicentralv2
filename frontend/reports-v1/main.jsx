import React, {useEffect, useMemo, useRef, useState} from 'react';
import {createRoot} from 'react-dom/client';
import './styles.css';
import {SolutionSidebar} from '../cadu-design-system/components/SolutionSidebar.jsx';

const SECTIONS = [
  ['overview', 'Visão geral', '◫'], ['accounts', 'Contas', '▤'],
  ['campaigns', 'Campanhas', '◎'], ['reports', 'Relatórios', '▥'],
  ['imports', 'Importações', '⇧'], ['monitor', 'Dados de mídia', '⌘'],
  ['supertag', 'Tags e tracking', '</>'], ['flow', 'Fluxos', '◇'],
  ['events', 'Eventos', '◉'], ['links', 'Link Tester', '↗'],
  ['access', 'Acessos', '♙'],
];
const TITLES = Object.fromEntries(SECTIONS.map(([id, title]) => [id, title]));
const SECTION_ALIASES = {'data-library': 'imports', conversions: 'events'};
const formatter = new Intl.DateTimeFormat('pt-BR', {day: '2-digit', month: 'short', year: 'numeric'});
const shortDate = value => value ? formatter.format(new Date(/^\d{4}-\d{2}-\d{2}$/.test(value) ? `${value}T12:00:00` : value)) : '—';
const integer = value => new Intl.NumberFormat('pt-BR', {maximumFractionDigits: 0}).format(value || 0);
const decimal = value => new Intl.NumberFormat('pt-BR', {maximumFractionDigits: 1}).format(value || 0);
const money = (micros, currency) => micros == null || !currency ? '—' : new Intl.NumberFormat('pt-BR', {style: 'currency', currency}).format(micros / 1_000_000);
const amount = (value, currency) => value == null || !currency ? '—' : new Intl.NumberFormat('pt-BR', {style: 'currency', currency}).format(Number(value));
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
      chart: {type, height, toolbar: {show: false}, animations: {enabled: false}, fontFamily: '-apple-system, BlinkMacSystemFont, Segoe UI, Arial, sans-serif'},
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

const FLOW_PLATFORMS = {
  google: {label: 'Google Ads', logo: '/static/images/cadu/technology-logos/google.svg'},
  meta: {label: 'Meta Ads'},
  linkedin: {label: 'LinkedIn Ads', logo: '/static/images/creative-viewers/linkedin.svg'},
  tiktok: {label: 'TikTok Ads', logo: '/static/images/canais/tiktok.png'},
  whatsapp: {label: 'WhatsApp', logo: '/static/images/canais/whatsapp.svg'},
  amazon_ads: {label: 'Amazon Ads', wordmark: 'amazon'},
  spotify_ads: {label: 'Spotify Ads', logo: '/static/images/canais/spotify.svg'},
  netflix_ads: {label: 'Netflix Ads', logo: '/static/images/creative-viewers/netflix.png'},
  serasa: {label: 'Serasa', wordmark: 'serasa'},
  disney_ads: {label: 'Disney Ads', logo: '/static/images/creative-viewers/disney-plus.png'},
  email: {label: 'E-mail', wordmark: 'email'},
};

const FLOW_CHANNELS = [
  {id:'netflix_ads',label:'Netflix Ads',aliases:['netflix']},
  {id:'serasa',label:'Serasa',aliases:['serasa']},
  {id:'spotify_ads',label:'Spotify Ads',aliases:['spotify']},
  {id:'amazon_ads',label:'Amazon Ads',aliases:['amazon']},
  {id:'disney_ads',label:'Disney Ads',aliases:['disney','hulu','espn']},
  {id:'google_ads',label:'Google Ads',aliases:['google','adwords','youtube','dv360','gclid']},
  {id:'meta_ads',label:'Meta Ads',aliases:['meta','facebook','instagram','fbclid','ig','fb']},
  {id:'linkedin_ads',label:'LinkedIn Ads',aliases:['linkedin','licdn','li_fat_id']},
  {id:'tiktok',label:'TikTok Ads',aliases:['tiktok','ttclid']},
  {id:'email',label:'E-mail',aliases:['email','e-mail','newsletter','mailchimp','rdstation']},
  {id:'whatsapp',label:'WhatsApp',aliases:['whatsapp','wa.me']},
];

function FlowPlatformLogo({platform}) {
  const brand = FLOW_PLATFORMS[platform] || FLOW_PLATFORMS[({google_ads:'google',meta_ads:'meta',linkedin_ads:'linkedin'})[platform]];
  if (!brand) return <span className="reports-flow-brand-fallback" aria-hidden="true">◇</span>;
  if (platform === 'meta' || platform === 'meta_ads') return <svg className="reports-flow-brand-mark is-meta" viewBox="0 0 44 28" role="img" aria-label="Meta"><path d="M3 19c4-11 8-14 12-10l8 11c4 5 8 2 12-8 2-6 5-7 7-1 3 8-1 14-6 12-3-1-6-5-9-9l-6-8C16 1 11 5 6 14l-3 5" fill="none" stroke="currentColor" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round"/></svg>;
  if (brand.wordmark === 'amazon') return <svg className="reports-flow-brand-mark is-amazon" viewBox="0 0 48 28" role="img" aria-label="Amazon"><text x="2" y="17" fontSize="15" fontWeight="700" fill="currentColor">amazon</text><path d="M10 21c10 6 23 6 32-1m0 0-5-1m5 1-2 4" fill="none" stroke="#f0a323" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"/></svg>;
  if (brand.wordmark === 'serasa') return <span className="reports-brand-wordmark is-serasa" aria-label="Serasa">serasa</span>;
  if (brand.wordmark === 'email') return <svg className="reports-flow-brand-mark is-email" viewBox="0 0 24 24" role="img" aria-label="E-mail"><path d="M3 5h18v14H3zM4 7l8 6 8-6" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round"/></svg>;
  return <img className="reports-flow-brand-mark" src={brand.logo} alt={brand.label} draggable="false" />;
}

function Kpi({label, value, detail}) {
  return <article className="reports-kpi"><span>{label}</span><strong>{value}</strong><small>{detail}</small></article>;
}

function Overview({data, metrics, imported}) {
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
    <section className="reports-grid reports-grid--four" aria-label="Exportações conciliadas"><Kpi label="Impressões importadas" value={integer(imported?.totals?.impressions)} detail="arquivos diários sem divergência" /><Kpi label="Cliques importados" value={integer(imported?.totals?.clicks)} detail="arquivos diários sem divergência" /><Kpi label="Investimento importado" value={amount(imported?.totals?.cost, imported?.currency)} detail={imported?.currency || 'Moedas distintas ou sem custo'} /><Kpi label="Valores em conflito" value={integer(imported?.conflicts)} detail="campanha, dia e métrica para revisão" /></section>
    <section className="reports-grid reports-grid--three"><article className="reports-panel reports-span-two"><div className="reports-panel-head"><h2>Exportações por plataforma</h2><span>Fonte separada do Google Ads Script</span></div>{(imported?.by_platform || []).length ? imported.by_platform.map(item => <div className="reports-row" key={item.platform}><span>{item.platform}</span><b>{integer(item.clicks)} cliques · {amount(item.cost, item.currency)}</b></div>) : <Empty message="Envie um CSV ou XLSX em Importações para acompanhar outras plataformas." />}</article><article className="reports-panel"><h2>Leitura dos arquivos</h2><p>Reenvios idênticos contam uma vez. Se dois arquivos trazem valores diferentes para a mesma campanha, data e métrica, o valor fica fora desta visão até revisão.</p><a className="reports-inline-link" href="#imports">Abrir Importações ↗</a></article></section>
  </>;
}

function Accounts({data, save, busy}) {
  const [form, setForm] = useState({platform: 'google_ads', account_kind: 'advertiser', external_id: '', name: '', parent_account_id: ''});
  const [clientName, setClientName] = useState('');
  const [query, setQuery] = useState('');
  const managers = data.accounts.filter(account => account.account_kind === 'manager' && account.platform === form.platform);
  const advertisers = data.accounts.filter(account => account.account_kind === 'advertiser');
  const visibleAccounts = data.accounts.filter(item => `${item.name} ${item.external_id} ${item.platform} ${item.account_kind}`.toLowerCase().includes(query.trim().toLowerCase()));
  const submit = async event => {
    event.preventDefault();
    try {await save('/accounts', form); setForm({...form, external_id: '', name: '', parent_account_id: ''});}
    catch (_) { /* Global error banner shows the failure. */ }
  };
  const createClient = async event => {
    event.preventDefault();
    try {
      const result = await save('/clients', {name: clientName}, false);
      location.href = `/connect/app?client_id=${encodeURIComponent(result.client.id)}#accounts`;
    } catch (_) { /* Global error banner shows the failure. */ }
  };
  return <section className="reports-grid reports-grid--four">
    <header className="reports-panel reports-span-three reports-accounts-heading"><div><h2>Clientes e contas</h2><p>Crie clientes independentes do CRM e cadastre as contas de mídia de cada cliente. As campanhas ficam na página Campanhas.</p></div><a className="reports-primary-link" href="#monitor">Conectar fonte</a></header>
    <Kpi label="Clientes Reports" value={data.clients.length} detail={`${data.client.client_name || `Cliente ${data.client.client_id}`} · ID ${data.client.client_id}`} />
    <Kpi label="Contas de anúncios" value={advertisers.length} detail="contas vinculadas a este cliente" />
    <Kpi label="Contas MCC" value={managers.length} detail="gerentes cadastrados neste cliente" />
    <Kpi label="Campanhas" value={data.campaigns.length} detail="associadas às contas deste cliente" />
    {data.can_manage_clients && <article className="reports-panel reports-span-four"><div className="reports-panel-head"><h2>Novo cliente Reports</h2><span>Identidade independente</span></div><p>Crie um cliente para centralizar contas, campanhas, integrações, fluxos e relatórios neste Reports.</p><form className="reports-form reports-space-create" onSubmit={createClient}><label>Nome do cliente<input required maxLength="200" value={clientName} onChange={event => setClientName(event.target.value)} placeholder="Ex.: CEMIG" /></label><button disabled={busy || !clientName.trim()}>Criar cliente</button></form></article>}
    <article className="reports-panel reports-span-three"><div className="reports-accounts-toolbar"><strong>Contas vinculadas ao cliente</strong><input type="search" placeholder="Buscar contas…" value={query} onChange={event=>setQuery(event.target.value)} aria-label="Buscar contas"/></div>
      {visibleAccounts.length ? <div className="reports-table-wrap"><table><thead><tr><th>Conta</th><th>Plataforma</th><th>ID externo</th><th>Tipo</th><th>MCC vinculada</th><th>Status</th></tr></thead><tbody>{visibleAccounts.map(item => <AccountRow key={item.id} item={item} data={data} save={save} busy={busy} />)}</tbody></table></div> : <Empty message={data.accounts.length?'Nenhuma conta corresponde à busca.':'Adicione uma conta para organizar campanhas e relatórios.'} />}
    </article>
    <article className="reports-panel"><div className="reports-panel-head"><h2>Adicionar conta</h2><span>Cadastro inicial</span></div>{data.client.role==='viewer'?<Empty message="Seu acesso permite consultar as contas, sem cadastrar ou editar."/>:<form className="reports-form" onSubmit={submit}>
      <label>Plataforma<select value={form.platform} onChange={event => setForm({...form, platform: event.target.value, parent_account_id: ''})}><option value="google_ads">Google Ads</option><option value="meta_ads">Meta Ads</option><option value="microsoft_ads">Microsoft Ads</option><option value="other">Outra</option></select></label>
      <label>Tipo<select value={form.account_kind} onChange={event => setForm({...form, account_kind: event.target.value, parent_account_id: ''})}><option value="advertiser">Conta de mídia</option><option value="manager">MCC / gerente</option></select></label>
      <label>Nome<input required maxLength="240" value={form.name} onChange={event => setForm({...form, name: event.target.value})} placeholder="Nome exibido na plataforma" /></label>
      <label>ID da conta<input required maxLength="160" value={form.external_id} onChange={event => setForm({...form, external_id: event.target.value})} placeholder="ID fornecido pela plataforma" /></label>
      {form.account_kind === 'advertiser' && managers.length > 0 && <label>Conta gerente<select value={form.parent_account_id} onChange={event => setForm({...form, parent_account_id: event.target.value})}><option value="">Sem gerente</option>{managers.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>}
      <button disabled={busy} type="submit">Salvar conta</button>
    </form>}</article>
  </section>;
}

function AccountRow({item, data, save, busy}) {
  const [draft, setDraft] = useState({name: item.name, status: item.status || 'active', parent_account_id: item.parent_account_id || ''});
  const [saved, setSaved] = useState(false);
  useEffect(() => setDraft({name: item.name, status: item.status || 'active', parent_account_id: item.parent_account_id || ''}), [item]);
  const managers = data.accounts.filter(account => account.platform === item.platform && account.account_kind === 'manager' && account.status !== 'disabled' && account.id !== item.id);
  const update = async event => {event.preventDefault(); setSaved(false); try {await save(`/accounts/${item.id}`, draft, true, 'PATCH'); setSaved(true);} catch (_) { /* Global error banner shows the failure. */ }};
  return <tr><td>{data.client.role==='viewer'?item.name:<form className="reports-inline-edit" onSubmit={update}><input aria-label={`Nome da conta ${item.external_id}`} value={draft.name} onChange={event => setDraft({...draft, name: event.target.value})} required maxLength="240" />{item.account_kind === 'advertiser' && <select aria-label="MCC vinculada" value={draft.parent_account_id} onChange={event => setDraft({...draft, parent_account_id: event.target.value})}><option value="">Sem MCC</option>{managers.map(manager => <option key={manager.id} value={manager.id}>{manager.name}</option>)}</select>}<button className="reports-text-button" type="submit" disabled={busy}>Salvar</button>{saved && <small>Salvo</small>}</form>}</td><td>{item.platform}</td><td>{item.external_id}</td><td>{item.account_kind === 'manager' ? 'MCC / gerente' : 'Anunciante'}</td><td>{data.accounts.find(parent => parent.id === item.parent_account_id)?.name || '—'}</td><td>{data.client.role==='viewer'?({active:'Ativa',paused:'Pausada',disabled:'Desativada'})[item.status]||item.status:<form onSubmit={update}><select aria-label="Estado da conta" value={draft.status} onChange={event => setDraft({...draft, status: event.target.value})}><option value="active">Ativa</option><option value="paused">Pausada</option><option value="disabled">Desativada</option></select><button className="reports-text-button" type="submit" disabled={busy}>Salvar</button></form>}</td></tr>;
}

function Campaigns({data, save, busy, filters}) {
  const [form, setForm] = useState({account_id: '', external_id: '', name: '', objective: '', channel_type: ''});
  const [campaignId, setCampaignId] = useState(new URLSearchParams(location.search).get('campaign_id') || new URLSearchParams(location.hash.split('?')[1] || '').get('campaign_id') || '');
  const [campaignDetail, setCampaignDetail] = useState(null);
  const [detailError, setDetailError] = useState('');
  const [tab, setTab] = useState(() => {
    const current = new URLSearchParams(location.search).get('campaign_tab') || 'overview';
    return current === 'metrics' ? 'performance' : current;
  });
  const accounts = data.accounts.filter(item => item.account_kind === 'advertiser');
  useEffect(() => {
    let live = true;
    if (!campaignId) {setCampaignDetail(null); return () => {live=false;};}
    json(`/connect/api/v1/reports/campaigns/${campaignId}?client_id=${data.client.client_id}`)
      .then(value => {if(live){setCampaignDetail(value);setDetailError('');}})
      .catch(error => {if(live)setDetailError(error.message);});
    return () => {live=false;};
  }, [campaignId, data.client.client_id]);
  useEffect(()=>{const sync=()=>{const params=new URLSearchParams(location.search);setCampaignId(params.get('campaign_id')||new URLSearchParams(location.hash.split('?')[1]||'').get('campaign_id')||'');const current=params.get('campaign_tab')||'overview';setTab(current==='metrics'?'performance':current);};addEventListener('popstate',sync);return()=>removeEventListener('popstate',sync);},[]);
  const openCampaign = item => {setCampaignId(String(item.id));setTab('overview');history.pushState(null,'',`?client_id=${data.client.client_id}&campaign_id=${item.id}#campaigns`);};
  const changeCampaignTab = value => {setTab(value);const params=new URLSearchParams(location.search);params.set('client_id',data.client.client_id);params.set('campaign_id',campaignId);params.set('campaign_tab',value);history.pushState(null,'',`?${params.toString()}#campaigns`);};
  const closeCampaign = () => {setCampaignId('');setCampaignDetail(null);history.pushState(null,'',`?client_id=${data.client.client_id}#campaigns`);};
  const submit = async event => {event.preventDefault(); try {await save('/campaigns', form); setForm({...form, external_id: '', name: '', objective: '', channel_type: ''});} catch (_) { /* Global error banner shows the failure. */ }};
  if (campaignId) return <CampaignDetail data={data} detail={campaignDetail} error={detailError} tab={tab} setTab={changeCampaignTab} close={closeCampaign} filters={filters} save={save} busy={busy} updateDetail={setCampaignDetail} />;
  return <section className="reports-grid reports-grid--three"><article className="reports-panel reports-span-two"><div className="reports-panel-head"><div><h2>Campanhas</h2><p>Cadastro e gestão pertencem ao cliente selecionado. O projeto do Workspace pode ser associado depois.</p></div><span>{data.campaigns.length} cadastradas</span></div>
    {data.campaigns.length ? <div className="reports-table-wrap"><table><thead><tr><th>Campanha</th><th>Conta</th><th>Plataforma</th><th>Tipo</th><th>ID externo</th><th>Projeto Workspace (opcional)</th><th>Status</th></tr></thead><tbody>{data.campaigns.map(item => <tr key={item.id}><td><button type="button" className="reports-campaign-open" onClick={()=>openCampaign(item)}><strong>{item.name}</strong><small>Abrir detalhes ↗</small></button></td><td>{item.account_name}</td><td>{item.platform}</td><td>{item.channel_type || item.objective || '—'}</td><td>{item.external_id}</td><td><select aria-label={`Projeto Workspace da campanha ${item.name}`} value={item.workspace_project_id || ''} disabled={busy || data.client.role !== 'admin'} onChange={event=>save(`/campaigns/${item.id}/workspace-project`,{workspace_project_id:event.target.value||null}).catch(()=>{})}><option value="">Sem associação</option>{!(data.workspace_projects||[]).length&&<option disabled value="__none__">Nenhum projeto acessível</option>}{(data.workspace_projects||[]).map(project=><option key={project.id} value={project.id}>{project.name}</option>)}</select></td><td>{({ENABLED:'Ativa',PAUSED:'Pausada',REMOVED:'Removida',unknown:'Não informado'})[item.status] || item.status}</td></tr>)}</tbody></table></div> : <Empty message="As campanhas cadastradas e sincronizadas aparecerão aqui." />}</article>
    <article className="reports-panel"><div className="reports-panel-head"><h2>Adicionar campanha</h2><span>Cadastro inicial</span></div>{data.client.role==='viewer'?<Empty message="Seu acesso permite consultar as campanhas, sem cadastrar ou editar."/>:<form className="reports-form" onSubmit={submit}>
      {!accounts.length && <p className="reports-suggestion">Cadastre primeiro uma conta de mídia em <a href="#accounts">Contas</a>. A campanha ficará vinculada ao cliente Reports selecionado.</p>}
      <label>Conta<select required value={form.account_id} onChange={event => setForm({...form, account_id: event.target.value})}><option value="">Selecione</option>{accounts.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
      <label>Nome<input required maxLength="240" value={form.name} onChange={event => setForm({...form, name: event.target.value})} /></label>
      <label>ID da campanha<input required maxLength="160" value={form.external_id} onChange={event => setForm({...form, external_id: event.target.value})} /></label>
      <label>Objetivo (opcional)<input maxLength="160" value={form.objective} onChange={event => setForm({...form, objective: event.target.value})} placeholder="Ex.: geração de leads" /></label>
      <label>Tipo de canal (opcional)<input maxLength="64" value={form.channel_type} onChange={event => setForm({...form, channel_type: event.target.value})} placeholder="Ex.: pesquisa, social, vídeo" /></label>
      <button disabled={busy || !accounts.length} type="submit">Salvar campanha</button>
    </form>}</article></section>;
}

function CampaignDetail({data, detail, error, tab, setTab, close, filters, save, busy, updateDetail}) {
  const [channelData, setChannelData] = useState(null);
  const [flowData, setFlowData] = useState(null);
  const [analysisError, setAnalysisError] = useState('');
  const [settings, setSettings] = useState({name: '', objective: '', channel_type: ''});
  const [settingsNotice, setSettingsNotice] = useState('');
  const campaignId = detail?.campaign?.id;
  useEffect(() => {
    if (!campaignId) return undefined;
    let active = true;
    const params = new URLSearchParams({
      client_id: String(data.client.client_id),
      campaign_id: String(campaignId),
      days: filters.period,
      start_date: filters.startDate,
      end_date: filters.endDate,
    });
    Promise.all([
      json(`/connect/api/v1/reports/metrics?${params}`),
      json(`/connect/api/v1/reports/flow?${params}`),
    ]).then(([metrics, flow]) => {
      if (active) {setChannelData(metrics);setFlowData(flow);setAnalysisError('');}
    }).catch(failure => {if(active)setAnalysisError(failure.message);});
    return () => {active = false;};
  }, [campaignId, data.client.client_id, filters.period, filters.startDate, filters.endDate]);
  useEffect(() => {
    if (!detail?.campaign) return;
    setSettings({name: detail.campaign.name || '', objective: detail.campaign.objective || '', channel_type: detail.campaign.channel_type || ''});
    setSettingsNotice('');
  }, [detail?.campaign?.id, detail?.campaign?.name, detail?.campaign?.objective, detail?.campaign?.channel_type]);
  if(error)return <section className="reports-grid"><article className="reports-panel"><button type="button" className="reports-text-button" onClick={close}>← Voltar às campanhas</button><p className="reports-error">{error}</p></article></section>;
  if(!detail)return <section className="reports-grid"><article className="reports-panel"><Empty message="Carregando detalhes da campanha…"/></article></section>;
  const campaign=detail.campaign;
  const saveSettings = async event => {
    event.preventDefault();
    try {
      await save(`/campaigns/${campaign.id}`, settings, true, 'PATCH');
      const updated = await json(`/connect/api/v1/reports/campaigns/${campaign.id}?client_id=${data.client.client_id}`);
      updateDetail(updated);
      setSettingsNotice('Campanha atualizada.');
    } catch (failure) {setAnalysisError(failure.message); setSettingsNotice('');}
  };
  const totals=detail.metric_totals||[];
  const latest=totals.reduce((value,item)=>!value||item.latest_date>value?item.latest_date:value,'');
  const periodMetricValue=key=>detail.metrics.filter(item=>item.metric_key===key&&item.metric_date>=filters.startDate&&item.metric_date<=filters.endDate&&item.value_numeric!=null).reduce((sum,item)=>sum+Number(item.value_numeric||0),0);
  const metricLabels={impressions:'Impressões',clicks:'Cliques',cost:'Investimento',conversions:'Conversões',conversion_value:'Valor de conversão'};
  const stateLabel=({ENABLED:'Ativa',PAUSED:'Pausada',REMOVED:'Removida',unknown:'Não informado'})[campaign.status]||campaign.status||'Ativa';
  const channelEvents = Object.values((flowData?.events || []).reduce((map, item) => {
    const key = item.source_label || 'Origem direta';
    map[key] = map[key] || {source_label: key, total: 0, mapped: 0};
    map[key].total += Number(item.total || 0);
    map[key].mapped += Number(item.mapped || 0);
    return map;
  }, {}));
  const forms = (flowData?.events || []).filter(item => item.event_kind === 'form_submit');
  const confirmed = flowData?.confirmed || [];
  const ingestedDaily = (channelData?.days || []).flatMap(item => [
    {metric_date:item.date,metric_key:'impressions',value_numeric:item.impressions,source:'google_ads_script'},
    {metric_date:item.date,metric_key:'clicks',value_numeric:item.clicks,source:'google_ads_script'},
    {metric_date:item.date,metric_key:'cost',value_numeric:item.cost_micros == null ? null : Number(item.cost_micros) / 1_000_000,currency:channelData.currency,source:'google_ads_script'},
    {metric_date:item.date,metric_key:'conversions',value_numeric:item.conversions,source:'google_ads_script'},
  ]).filter(item=>item.value_numeric!=null);
  const importedDaily=detail.metrics.filter(item=>item.value_numeric!=null&&item.metric_date>=filters.startDate&&item.metric_date<=filters.endDate);
  const dimensionalDaily=(detail.metric_observations||[]).filter(item=>item.metric_date>=filters.startDate&&item.metric_date<=filters.endDate);
  const campaignTabs = [
    ['overview','Visão geral'],['performance','Performance'],['channels','Canais'],
    ['pages','Páginas'],['forms','Formulários'],['leads','Leads'],
    ['conversions','Conversões'],['heatmap','Mapa de calor'],['reports','Relatórios'],
    ['imports','Dados de origem'],['settings','Configurações'],
  ];
  const periodLabel = `${shortDate(filters.startDate)} – ${shortDate(filters.endDate)}`;
  return <section className="reports-grid reports-grid--four reports-campaign-detail">
    <div className="reports-campaign-crumb reports-span-four"><button type="button" className="reports-text-button" onClick={close}>Campanhas</button><span>›</span><b>{campaign.name}</b></div>
    <header className="reports-panel reports-span-four reports-campaign-hero"><div><small>{campaign.platform} · {campaign.account_name} · ID {campaign.external_id}</small><h2>{campaign.name}<span className={`reports-campaign-status ${campaign.status==='PAUSED'?'is-paused':''}`}>{stateLabel}</span></h2><p>Campanha de mídia do cliente {data.client.client_name}. Criada em {shortDate(campaign.created_at)} · Atualizada em {shortDate(campaign.updated_at)}.</p></div><a className="reports-primary-link" href="#imports">Importar dados</a></header>
    <nav className="reports-panel reports-span-four reports-campaign-tabs" aria-label="Seções da campanha">{campaignTabs.map(([key,label])=><button type="button" className={tab===key?'is-active':''} aria-current={tab===key?'page':undefined} onClick={()=>setTab(key)} key={key}>{label}</button>)}</nav>
    {analysisError&&<div className="reports-error reports-span-four" role="alert">Não foi possível carregar os dados desta campanha: {analysisError}</div>}
    {tab==='overview'&&<><Kpi label="Impressões" value={integer(channelData?.totals?.impressions ?? periodMetricValue('impressions'))} detail={`${periodLabel} · mídia`}/><Kpi label="Cliques" value={integer(channelData?.totals?.clicks ?? periodMetricValue('clicks'))} detail={`${periodLabel} · mídia`}/><Kpi label="Conversões" value={decimal(channelData?.totals?.conversions ?? periodMetricValue('conversions'))} detail="Métricas recebidas da plataforma"/><Kpi label="Último dado" value={shortDate(latest)} detail="data mais recente entre as métricas importadas"/><article className="reports-panel reports-span-two"><div className="reports-panel-head"><h3>Performance no período</h3><span>{periodLabel}</span></div><Chart type="area" labels={(channelData?.days||[]).map(item=>shortDate(item.date))} values={(channelData?.days||[]).map(item=>item.impressions)}/></article><article className="reports-panel reports-span-two"><div className="reports-panel-head"><h3>Dados personalizados</h3><span>{detail.custom_values.length} pares chave/valor</span></div>{detail.custom_values.length?detail.custom_values.slice(0,8).map((item,index)=><div className="reports-row" key={`${item.metric_key}:${item.metric_date}:${index}`}><span>{item.metric_label} · {item.channel}<small>{item.metric_key} · {shortDate(item.metric_date)}</small></span><b>{item.value_numeric} {item.currency||item.unit}</b></div>):<Empty message="Dados extras importados aparecerão associados a esta campanha."/>}</article></>}
    {tab==='performance'&&<article className="reports-panel reports-span-four"><div className="reports-panel-head"><h3>Performance da campanha</h3><span>{periodLabel} · origem: Google Ads Script</span></div><div className="reports-grid reports-grid--four"><Kpi label="Impressões" value={integer(channelData?.totals?.impressions)} detail="No período selecionado"/><Kpi label="Cliques" value={integer(channelData?.totals?.clicks)} detail="No período selecionado"/><Kpi label="Investimento" value={money(channelData?.totals?.cost_micros,channelData?.currency)} detail="Moeda da conta"/><Kpi label="Conversões da plataforma" value={decimal(channelData?.totals?.conversions)} detail="Métrica enviada pela plataforma"/></div><Chart type="area" labels={(channelData?.days||[]).map(item=>shortDate(item.date))} values={(channelData?.days||[]).map(item=>item.impressions)}/></article>}
    {tab==='channels'&&<><Kpi label="Plataforma" value={campaign.platform} detail={campaign.channel_type||campaign.objective||'Canal não informado'}/><Kpi label="Origens atribuídas" value={integer(channelEvents.length)} detail="UTM ou domínio de referência"/><Kpi label="Eventos atribuídos" value={integer(channelEvents.reduce((sum,item)=>sum+item.total,0))} detail="No período selecionado"/><Kpi label="Campanha" value={campaign.name} detail={campaign.external_id}/><article className="reports-panel reports-span-four"><div className="reports-panel-head"><h3>Origem do tráfego</h3><span>Eventos da tag de fluxo · {periodLabel}</span></div>{channelEvents.length?<div className="reports-table-wrap"><table><thead><tr><th>Origem / canal</th><th>Eventos</th><th>Mapeados em etapas</th></tr></thead><tbody>{channelEvents.map(item=><tr key={item.source_label}><td>{item.source_label}</td><td>{integer(item.total)}</td><td>{integer(item.mapped)}</td></tr>)}</tbody></table></div>:<Empty message="Não há eventos atribuídos a esta campanha no período."/>}</article></>}
    {tab==='pages'&&<article className="reports-panel reports-span-four"><div className="reports-panel-head"><h3>Páginas do fluxo</h3><span>{periodLabel}</span></div>{flowData?.activity?.length?<div className="reports-table-wrap"><table><thead><tr><th>Página</th><th>Visitas</th><th>Visitantes</th><th>Formulários</th><th>Conversões</th></tr></thead><tbody>{flowData.activity.map(item=><tr key={`${item.tag_id}:${item.page_path}`}><td>{item.page_path}</td><td>{integer(item.views)}</td><td>{integer(item.visitors)}</td><td>{integer(item.form_submissions)}</td><td>{integer(item.conversions)}</td></tr>)}</tbody></table></div>:<Empty message="As páginas aparecem quando o Funnel Flow recebe visitas atribuídas à campanha."/>}</article>}
    {tab==='forms'&&<article className="reports-panel reports-span-four"><div className="reports-panel-head"><h3>Eventos de formulário</h3><span>{forms.length} combinações de evento e página</span></div>{forms.length?<div className="reports-table-wrap"><table><thead><tr><th>Evento</th><th>Página</th><th>Origem</th><th>Envios</th><th>Mapeados</th></tr></thead><tbody>{forms.map((item,index)=><tr key={`${item.event_name}:${item.page_path}:${index}`}><td>{item.event_name}</td><td>{item.page_path}</td><td>{item.source_label}</td><td>{integer(item.total)}</td><td>{integer(item.mapped)}</td></tr>)}</tbody></table></div>:<Empty message="Nenhum envio de formulário foi recebido para esta campanha no período. Os valores dos campos não são armazenados."/>}</article>}
    {tab==='leads'&&<><Kpi label="Leads" value={integer(confirmed.find(item=>item.conversion_kind==='lead')?.total)} detail="Confirmações do CRM"/><Kpi label="Qualificados" value={integer(confirmed.find(item=>item.conversion_kind==='qualified_lead')?.total)} detail="Confirmações do CRM"/><Kpi label="Vendas" value={integer(confirmed.find(item=>item.conversion_kind==='sale')?.total)} detail="Confirmações do CRM"/><article className="reports-panel"><h3>Dados protegidos</h3><p>Esta tela mostra totais agregados. Dados pessoais ficam no CRM de origem.</p></article><article className="reports-panel reports-span-four"><div className="reports-panel-head"><h3>Confirmações recebidas</h3><span>CRM · {periodLabel}</span></div>{confirmed.length?<div className="reports-table-wrap"><table><thead><tr><th>Etapa</th><th>Total confirmado</th></tr></thead><tbody>{confirmed.map(item=><tr key={item.conversion_kind}><td>{({lead:'Lead',qualified_lead:'Lead qualificado',sale:'Venda'})[item.conversion_kind]||item.conversion_kind}</td><td>{integer(item.total)}</td></tr>)}</tbody></table></div>:<Empty message="Conecte o CRM em Monitoramentos para receber confirmações de leads e vendas."/>}</article></>}
    {tab==='conversions'&&<><Kpi label="Conversões da plataforma" value={decimal(channelData?.totals?.conversions)} detail="Importadas da conta de mídia"/><Kpi label="Conversões no site" value={integer(channelData?.observed_conversions)} detail="Eventos de conversão atribuídos"/><Kpi label="Confirmadas pelo CRM" value={integer(channelData?.confirmed_conversions)} detail="Leads, qualificados e vendas"/><article className="reports-panel"><h3>Leitura dos dados</h3><p>Plataforma, site e CRM usam critérios diferentes; os totais ficam separados para comparação.</p></article><article className="reports-panel reports-span-four"><div className="reports-panel-head"><h3>Eventos de conversão</h3><span>{periodLabel}</span></div>{(flowData?.events||[]).filter(item=>item.event_kind==='conversion').length?<div className="reports-table-wrap"><table><thead><tr><th>Evento</th><th>Página</th><th>Origem</th><th>Ocorrências</th></tr></thead><tbody>{flowData.events.filter(item=>item.event_kind==='conversion').map((item,index)=><tr key={`${item.event_name}:${item.page_path}:${index}`}><td>{item.event_name}</td><td>{item.page_path}</td><td>{item.source_label}</td><td>{integer(item.total)}</td></tr>)}</tbody></table></div>:<Empty message="Nenhuma conversão própria foi registrada neste período."/>}</article></>}
    {tab==='heatmap'&&<article className="reports-panel reports-span-four"><div className="reports-panel-head"><h3>Mapa de calor</h3><span>Super Tag</span></div><p>O mapa visual fica nas instalações da Super Tag. Ainda não há vínculo entre uma instalação e esta campanha para filtrar os cliques com segurança.</p><a className="reports-primary-link" href="#supertag">Abrir Super Tag</a></article>}
    {tab==='performance'&&<article className="reports-panel reports-span-four"><div className="reports-panel-head"><h3>Métricas por data</h3><span>{periodLabel} · mídia e importações conciliadas</span></div><div className="reports-table-wrap"><table><thead><tr><th>Data</th><th>Métrica</th><th>Valor</th><th>Moeda</th><th>Fonte / estado</th></tr></thead><tbody>{[...ingestedDaily,...importedDaily].map((item,index)=><tr key={`${item.metric_date}:${item.metric_key}:${index}`}><td>{shortDate(item.metric_date)}</td><td>{metricLabels[item.metric_key]||item.metric_key}</td><td>{item.metric_key==='cost'||item.metric_key==='conversion_value'?amount(item.value_numeric,item.currency):integer(item.value_numeric)}</td><td>{item.currency||'—'}</td><td>{item.source==='google_ads_script'?'Google Ads':item.version_count>1?'Revisar divergência':'Importação'}</td></tr>)}</tbody></table>{!ingestedDaily.length&&!importedDaily.length&&<Empty message="Ainda não há dados de performance no período."/>}</div></article>}
    {tab==='performance'&&<article className="reports-panel reports-span-four"><div className="reports-panel-head"><h3>Detalhe por anúncio e dimensão</h3><span>{dimensionalDaily.length} valores de origem · não somados entre dimensões</span></div>{dimensionalDaily.length?<div className="reports-table-wrap"><table><thead><tr><th>Data</th><th>Métrica</th><th>Valor</th><th>Dimensões do export</th></tr></thead><tbody>{dimensionalDaily.slice(0,500).map((item,index)=><tr key={`${item.metric_date}:${item.metric_key}:${index}`}><td>{shortDate(item.metric_date)}</td><td>{metricLabels[item.metric_key]||item.metric_key}</td><td>{item.metric_key==='cost'||item.metric_key==='conversion_value'?amount(item.value_numeric,item.currency):integer(item.value_numeric)}</td><td>{Object.values(item.dimensions||{}).map(value=>`${value.label}: ${value.value}`).join(' · ')||'Campanha'}</td></tr>)}</tbody></table></div>:<Empty message="O detalhamento por anúncio aparece quando o export traz essa dimensão."/>}</article>}
    {tab==='reports'&&<article className="reports-panel reports-span-four"><div className="reports-panel-head"><h3>Relatórios associados</h3><span>{detail.reports.length}</span></div>{detail.reports.length?detail.reports.map(item=><div className="reports-row" key={item.id}><span>{item.campaign_name}<small>Versão {item.revision} · {shortDate(item.updated_at)}</small></span><a className="reports-inline-link" href="#reports">Abrir relatório ↗</a></div>):<Empty message="Nenhum relatório está associado a esta campanha."/>}</article>}
    {tab==='imports'&&<><article className="reports-panel reports-span-two"><div className="reports-panel-head"><h3>Arquivos de origem</h3><span>{detail.imports.length}</span></div>{detail.imports.length?detail.imports.map(item=><div className="reports-row" key={item.id}><span>{item.original_name}<small>{item.file_kind} · {item.observations} métricas · {shortDate(item.created_at)}</small></span><a className="reports-inline-link" href="#imports">Abrir Importações ↗</a></div>):<Empty message="Nenhum arquivo importado para esta campanha."/>}</article><article className="reports-panel reports-span-two"><div className="reports-panel-head"><h3>Totais por intervalo</h3><span>{detail.range_snapshots.length}</span></div>{detail.range_snapshots.length?detail.range_snapshots.map(item=><div className="reports-row" key={item.id}><span>{shortDate(item.period_start)} – {shortDate(item.period_end)}<small>{item.original_name}</small></span><b>{item.metrics.map(metric=>`${metric.metric_label}: ${metric.value_numeric} ${metric.currency||metric.unit}`).join(' · ')}</b></div>):<Empty message="Snapshots de período aparecem separados dos dados diários."/>}</article></>}
    {tab==='settings'&&<><article className="reports-panel reports-span-two"><div className="reports-panel-head"><h3>Identificação da campanha</h3><span>Dados da conta de mídia</span></div><div className="reports-campaign-settings"><p><small>Plataforma</small><b>{campaign.platform}</b></p><p><small>Conta anunciante</small><b>{campaign.account_name}</b></p><p><small>ID externo da conta</small><b>{campaign.account_external_id}</b></p><p><small>ID externo da campanha</small><b>{campaign.external_id}</b></p><p><small>Status na plataforma</small><b>{stateLabel}</b></p><p><small>Última atualização</small><b>{shortDate(campaign.updated_at)}</b></p></div></article><article className="reports-panel reports-span-two"><div className="reports-panel-head"><h3>Editar classificação</h3><span>Nome e contexto Reports</span></div>{data.client.role==='viewer'?<Empty message="Seu acesso permite consultar a campanha, sem editar seus dados."/>:<form className="reports-form" onSubmit={saveSettings}><label>Nome<input required maxLength="240" value={settings.name} onChange={event=>setSettings({...settings,name:event.target.value})}/></label><label>Objetivo<input maxLength="160" value={settings.objective} onChange={event=>setSettings({...settings,objective:event.target.value})} placeholder="Ex.: geração de leads"/></label><label>Tipo de canal<input maxLength="64" value={settings.channel_type} onChange={event=>setSettings({...settings,channel_type:event.target.value})} placeholder="Ex.: pesquisa, social, vídeo"/></label><button disabled={busy}>Salvar alterações</button>{settingsNotice&&<small role="status">{settingsNotice}</small>}</form>}</article></>}
  </section>;
}

function Reports({data, save, busy}) {
  const [form, setForm] = useState({campaign_name: '', media_campaign_id: ''});
  const [detail, setDetail] = useState(null);
  const [draft, setDraft] = useState({});
  const [note, setNote] = useState('');
  const [expiresDays, setExpiresDays] = useState('30');
  const [detailError, setDetailError] = useState('');
  const [reviewSource, setReviewSource] = useState(null);
  const [reviewMetrics, setReviewMetrics] = useState([]);
  const [reviewNote, setReviewNote] = useState('');
  const [reviewHistory, setReviewHistory] = useState([]);
  const [suggesting, setSuggesting] = useState(false);
  const [typeSafeReview, setTypeSafeReview] = useState(null);
  const [reviewingTypeSafe, setReviewingTypeSafe] = useState(false);
  const [planSuggestion, setPlanSuggestion] = useState(null);
  const [planning, setPlanning] = useState(false);
  useEffect(() => {setDetail(null); setDraft({}); setPlanSuggestion(null); setTypeSafeReview(null); setDetailError('');}, [data.client.client_id]);
  const submit = async event => {event.preventDefault(); try {await save('/workspaces', form); setForm({campaign_name: '', media_campaign_id: ''});} catch (_) { /* Global error banner shows the failure. */ }};
  const open = async (event, reportId) => {event.preventDefault(); setDetailError(''); setPlanSuggestion(null); setReviewSource(null); setTypeSafeReview(null); try {const value = await json(`/connect/api/v1/reports/workspaces/${reportId}?client_id=${data.client.client_id}`); setDetail(value); setDraft(value.report.document || {}); setNote('');} catch (failure) {setDetailError(failure.message);}};
  const refresh = async reportId => {const value = await json(`/connect/api/v1/reports/workspaces/${reportId}?client_id=${data.client.client_id}`); setDetail(value); setDraft(value.report.document || {});};
  const update = async event => {event.preventDefault(); if (!detail) return; try {await save(`/workspaces/${detail.report.id}/document`, {revision: detail.report.revision, update_note: note, document: Object.fromEntries(['objective', 'goals', 'management_notes', 'start_date', 'end_date', 'accent'].map(field => [field, draft[field] || '']))}); await refresh(detail.report.id); setNote(''); setDetailError('');} catch (failure) {setDetailError(failure.message);}};
  const planNextAction = async () => {
    if (!detail) return;
    setPlanning(true); setDetailError('');
    try {
      const body = await json(`/connect/api/v1/reports/workspaces/${detail.report.id}/plan`, {
        method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': data.csrf},
        body: JSON.stringify({client_id: data.client.client_id}),
      });
      setPlanSuggestion(body.plan);
    } catch (failure) {setDetailError(failure.message);} finally {setPlanning(false);}
  };
  const incorporatePlan = () => {
    if (!planSuggestion) return;
    const addition = `${planSuggestion.title}\n${planSuggestion.steps.map(step => `• ${step}`).join('\n')}`;
    setDraft(current => ({...current, management_notes: [current.management_notes, addition].filter(Boolean).join('\n\n')}));
    setPlanSuggestion(null);
  };
  const publish = async () => {if (!detail) return; try {await save(`/workspaces/${detail.report.id}/publish`, {expires_days: Number(expiresDays)}, false); await refresh(detail.report.id); setDetailError('');} catch (failure) {setDetailError(failure.message);}};
  const unpublish = async () => {if (!detail) return; try {await save(`/workspaces/${detail.report.id}/unpublish`, {}, false); await refresh(detail.report.id); setDetailError('');} catch (failure) {setDetailError(failure.message);}};
  const edit = (field, value) => {setDraft(current => ({...current, [field]: value})); if (field === 'objective' || field === 'goals') setPlanSuggestion(null);};
  const openReview = async source => {
    try {const body = await json(`/connect/relatorios/${detail.report.id}/fontes/${source.id}/revisar`); setReviewSource(source); setReviewMetrics(body.metrics?.length ? body.metrics : [{name: '', raw: '', unit: 'count', definition: '', scope: '', evidence: ''}]); setReviewHistory(body.history || []); setReviewNote(''); setTypeSafeReview(null); setDetailError('');}
    catch (failure) {setDetailError(failure.message);}
  };
  const suggestReview = async () => {
    if (!reviewSource) return;
    setSuggesting(true); setDetailError('');
    try {
      const payload = new FormData(); payload.append('_csrf', data.csrf);
      const response = await fetch(`/connect/relatorios/${detail.report.id}/fontes/${reviewSource.id}/sugerir`, {method: 'POST', credentials: 'same-origin', body: payload});
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || `Falha HTTP ${response.status}`);
      setReviewMetrics(body.suggestion.metrics.length ? body.suggestion.metrics : [{name: '', raw: '', unit: 'count', definition: '', scope: '', evidence: ''}]);
      setTypeSafeReview(null);
    } catch (failure) {setDetailError(failure.message);} finally {setSuggesting(false);}
  };
  const reviewWithTypeSafe = async () => {
    if (!reviewSource) return;
    setReviewingTypeSafe(true); setDetailError('');
    try {
      const body = await json(`/connect/relatorios/${detail.report.id}/fontes/${reviewSource.id}/revisar-typesafe`, {
        method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': data.csrf},
        body: JSON.stringify({metrics: reviewMetrics}),
      });
      setTypeSafeReview(body.review);
    } catch (failure) {setDetailError(failure.message);} finally {setReviewingTypeSafe(false);}
  };
  const updateReviewMetric = (index, key, value) => {
    setReviewMetrics(current => current.map((item, itemIndex) => itemIndex === index ? {...item, [key]: value} : item));
    setTypeSafeReview(null);
  };
  const saveReview = async event => {
    event.preventDefault(); if (!reviewSource) return;
    try {
      const payload = {revision: detail.report.revision, note: reviewNote, metrics: reviewMetrics.map(item => ({name: item.name, value: item.raw, unit: item.unit, definition: item.definition, scope: item.scope, evidence: item.evidence}))};
      await json(`/connect/relatorios/${detail.report.id}/fontes/${reviewSource.id}/revisar?client_id=${data.client.client_id}`, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': data.csrf}, body: JSON.stringify(payload)});
      await refresh(detail.report.id); setReviewSource(null); setReviewNote(''); setTypeSafeReview(null);
    } catch (failure) {setDetailError(failure.message);}
  };
  return <><section className="reports-grid reports-grid--four"><article className="reports-panel reports-span-three"><div className="reports-panel-head"><h2>Biblioteca</h2><span>{data.reports.length} relatórios</span></div><div className="reports-grid reports-grid--three">{data.reports.length ? data.reports.map(item => <a className="reports-panel reports-report-card" key={item.id} href="#reports" onClick={event => open(event, item.id)}><span>Relatório · v{item.revision}</span><h2>{item.campaign_name}</h2><p>{item.project_ref || 'Sem projeto associado'}</p><small>Atualizado em {shortDate(item.updated_at)}</small></a>) : <Empty message="Crie um relatório independente ou associado a uma campanha." />}</div></article><article className="reports-panel"><div className="reports-panel-head"><h2>Novo relatório</h2><span>Reports</span></div>{data.client.role !== 'viewer' && <form className="reports-form" onSubmit={submit}><label>Nome<input required maxLength="200" value={form.campaign_name} onChange={event => setForm({...form, campaign_name: event.target.value})} placeholder="Ex.: Resultado de setembro" /></label><label>Campanha (opcional)<select value={form.media_campaign_id} onChange={event => setForm({...form, media_campaign_id: event.target.value})}><option value="">Sem campanha vinculada</option>{data.campaigns.map(item => <option key={item.id} value={item.id}>{item.account_name} · {item.name}</option>)}</select></label><button disabled={busy} type="submit">Criar relatório</button></form>}</article></section>
    {detailError && <p className="reports-error" role="alert">{detailError}</p>}
    {detail && <section className="reports-grid reports-grid--three" aria-label="Detalhe do relatório"><article className="reports-panel reports-span-two"><div className="reports-panel-head"><h2>{detail.report.campaign_name}</h2><span>Versão {detail.report.revision} · {shortDate(detail.report.updated_at)}</span></div><form className="reports-form" onSubmit={update}><label>Objetivo<textarea disabled={data.client.role === 'viewer'} maxLength="2000" rows="3" value={draft.objective || ''} onChange={event => edit('objective', event.target.value)} /></label><label>Metas<textarea disabled={data.client.role === 'viewer'} maxLength="4000" rows="3" value={draft.goals || ''} onChange={event => edit('goals', event.target.value)} /></label><label>Notas de gestão<textarea disabled={data.client.role === 'viewer'} maxLength="8000" rows="4" value={draft.management_notes || ''} onChange={event => edit('management_notes', event.target.value)} /></label>{data.client.role !== 'viewer' && <button type="button" className="reports-text-button" disabled={planning} onClick={planNextAction}>{planning ? 'Planejando…' : 'Planejar próximo passo com TypeSafe'}</button>}{planSuggestion && <div className="reports-suggestion"><strong>Plano sugerido · {planSuggestion.title}</strong><ul>{planSuggestion.steps.map((step,index)=><li key={index}>{step}</li>)}</ul><p>Escolha do TypeSafe entre ações elegíveis a partir do objetivo e das métricas revisadas. O plano não altera o relatório até você incorporá-lo e salvar uma nova versão.</p><button type="button" className="reports-text-button" onClick={incorporatePlan}>Incorporar às notas do relatório</button></div>}<div className="reports-form-pair"><label>Início<input disabled={data.client.role === 'viewer'} type="date" value={draft.start_date || ''} onChange={event => edit('start_date', event.target.value)} /></label><label>Fim<input disabled={data.client.role === 'viewer'} type="date" value={draft.end_date || ''} onChange={event => edit('end_date', event.target.value)} /></label><label>Cor<input disabled={data.client.role === 'viewer'} type="color" value={draft.accent || '#1767c5'} onChange={event => edit('accent', event.target.value)} /></label></div>{data.client.role !== 'viewer' && <><label>Nota desta versão<input required maxLength="2000" value={note} onChange={event => setNote(event.target.value)} placeholder="O que mudou neste relatório?" /></label><button disabled={busy} type="submit">Salvar atualização</button></>}</form></article><article className="reports-panel"><div className="reports-panel-head"><h2>Publicação</h2><span>{detail.public_link ? 'Link ativo' : 'Privado'}</span></div>{detail.public_link ? <><p>{detail.public_link.expires_at ? `Relatório disponível para leitura até ${shortDate(detail.public_link.expires_at)}.` : 'Relatório disponível para leitura sem data de expiração.'}</p><a className="reports-inline-link" href={`/connect/r/${detail.public_link.token}`} target="_blank" rel="noopener noreferrer">Abrir link público ↗</a>{data.client.role !== 'viewer' && <p><button className="reports-text-button" type="button" disabled={busy} onClick={unpublish}>Revogar link</button></p>}</> : data.client.role !== 'viewer' ? <div className="reports-form"><label>Validade<select value={expiresDays} onChange={event => setExpiresDays(event.target.value)}><option value="7">7 dias</option><option value="30">30 dias</option><option value="90">90 dias</option><option value="0">Sem expiração</option></select></label><button type="button" disabled={busy} onClick={publish}>Publicar relatório</button></div> : <p>Este relatório ainda não foi publicado.</p>}<div className="reports-association-history"><h3>Versões</h3>{detail.versions.map(item => <p key={item.revision}>v{item.revision} · {item.note} · {shortDate(item.created_at)}</p>)}</div></article><article className="reports-panel reports-span-three"><div className="reports-panel-head"><h2>Fontes e evidências</h2><span>{detail.sources.length} fontes</span></div>{detail.sources.length ? detail.sources.map(item => <div className="reports-row" key={item.id}><span>{item.original_name} · {item.supplier || 'Fornecedor não informado'} · {item.status === 'reviewed' ? 'Revisada' : 'Aguardando revisão'}</span><button className="reports-inline-link" type="button" onClick={() => openReview(item)}>Revisar ↗</button><a className="reports-inline-link" href={`/connect/relatorios/${detail.report.id}/fontes/${item.id}`} target="_blank" rel="noopener noreferrer">Abrir print ↗</a></div>) : <Empty message="As fontes recebidas aparecerão aqui." />}<div className="reports-form-pair"><label>Prints<input type="file" multiple accept="image/png,image/jpeg,image/webp" id="report-source-files" /></label><label>Origem<input maxLength="200" id="report-source-supplier" placeholder="Ex.: Meta Ads" /></label><label>Início<input type="date" id="report-source-start" /></label><label>Fim<input type="date" id="report-source-end" /></label></div>{data.client.role !== 'viewer' && <button type="button" disabled={busy} onClick={async () => {const files=document.getElementById('report-source-files')?.files;if(!files?.length)return;const payload=new FormData();Array.from(files).forEach(file=>payload.append('prints',file));payload.append('supplier',document.getElementById('report-source-supplier')?.value||'');payload.append('period_start',document.getElementById('report-source-start')?.value||'');payload.append('period_end',document.getElementById('report-source-end')?.value||'');payload.append('_csrf',data.csrf);try{const response=await fetch(`/connect/relatorios/${detail.report.id}/fontes`,{method:'POST',body:payload,credentials:'same-origin'});if(!response.ok)throw new Error(`Falha HTTP ${response.status}`);await refresh(detail.report.id);}catch(failure){setDetailError(failure.message);}}}>Receber fontes</button>}</article>{reviewSource && <article className="reports-panel reports-span-three"><div className="reports-panel-head"><h2>Revisar fonte · {reviewSource.original_name}</h2><div><button type="button" className="reports-text-button" disabled={suggesting || data.client.role==='viewer'} onClick={suggestReview}>{suggesting ? 'Lendo print…' : 'Sugerir com IA'}</button><button type="button" className="reports-text-button" disabled={reviewingTypeSafe || data.client.role==='viewer' || !reviewMetrics.some(metric=>metric.name&&metric.raw&&metric.evidence)} onClick={reviewWithTypeSafe}>{reviewingTypeSafe ? 'Revisando evidências…' : 'Revisar evidências com TypeSafe'}</button><button type="button" className="reports-text-button" onClick={() => setReviewSource(null)}>Fechar</button></div></div><img className="reports-source-preview" src={`/connect/relatorios/${detail.report.id}/fontes/${reviewSource.id}`} alt={`Print ${reviewSource.original_name}`} /><p>Confira cada valor e evidência no print antes de confirmar. A sugestão de extração não altera os dados até a revisão.</p>{typeSafeReview && <div className="reports-suggestion"><strong>Revisão TypeSafe · confira antes de confirmar</strong><p>A concentração descreve a distribuição das opções, não a chance de acerto. Verifique a evidência original antes de decidir.</p>{typeSafeReview.judgments.map(item=><p key={item.index}>{item.name}: {item.judgment==='supported'?'evidência direta':item.judgment==='contradicted'?'possível divergência':'evidência insuficiente'} · concentração {Math.round(item.confidence*100)}%</p>)}<p>Esta análise não alterou os valores. Revise os apontamentos e confirme manualmente.</p>{typeSafeReview.omitted_count>0&&<p>{typeSafeReview.omitted_count} indicadores ficaram fora desta revisão.</p>}</div>}{reviewHistory.map(item => <p key={item.report_revision}>Revisão v{item.report_revision} · {item.note} · {shortDate(item.created_at)}</p>)}<form className="reports-form" onSubmit={saveReview}><div className="reports-form-pair">{reviewMetrics.map((metric,index) => <fieldset className="reports-metric-review" key={index}><label>Indicador<input required maxLength="120" value={metric.name} onChange={event => updateReviewMetric(index,'name',event.target.value)} /></label><label>Valor (use vírgula decimal)<input inputMode="decimal" value={metric.raw || ''} onChange={event => updateReviewMetric(index,'raw',event.target.value)} /></label><label>Unidade<select value={metric.unit} onChange={event => updateReviewMetric(index,'unit',event.target.value)}>{['count','BRL','USD','percent','seconds'].map(unit => <option key={unit}>{unit}</option>)}</select></label>{[['definition','Definição'],['scope','Escopo'],['evidence','Evidência']].map(([key,label]) => <label key={key}>{label}<input required maxLength="1000" value={metric[key] || ''} onChange={event => updateReviewMetric(index,key,event.target.value)} /></label>)}{reviewMetrics.length>1 && <button type="button" className="reports-text-button" onClick={() => {setReviewMetrics(reviewMetrics.filter((_,i)=>i!==index)); setTypeSafeReview(null);}}>Remover</button>}</fieldset>)}</div>{reviewMetrics.length<60 && <button type="button" className="reports-text-button" onClick={() => {setReviewMetrics([...reviewMetrics,{name:'',raw:'',unit:'count',definition:'',scope:'',evidence:''}]); setTypeSafeReview(null);}}>+ Indicador</button>}<label>Nota da revisão<textarea required maxLength="2000" value={reviewNote} onChange={event => setReviewNote(event.target.value)} /></label><button disabled={busy || data.client.role==='viewer'} type="submit">Confirmar e registrar versão</button></form></article>}</section>}
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
  const shareUrl = token => `${location.origin}/connect/public/link-tests/${encodeURIComponent(token)}`;
  const copyShare = async token => {try {await navigator.clipboard.writeText(shareUrl(token));} catch (_) { /* Browser may deny clipboard access. */ }};
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
  </form></article><article className="reports-panel reports-span-two"><div className="reports-panel-head"><h2>Resultado</h2>{result && <span>{result.score}/100</span>}</div>{result ? <><strong className="reports-result-title">{result.status_label}</strong><p>{result.summary}</p><p className="reports-url">{result.final_url}</p>{result.public_token && <button type="button" className="reports-text-button" onClick={() => copyShare(result.public_token)}>Copiar link de compartilhamento</button>}{result.alerts?.length > 0 && <ul className="reports-alerts">{result.alerts.map((alert, index) => <li key={index}>{alert}</li>)}</ul>}</> : <Empty message="Execute uma análise para ver o resultado e as evidências." />}</article>
    <article className="reports-panel reports-span-three"><div className="reports-panel-head"><h2>Histórico</h2><span>{data.link_tests.length} recentes</span></div>{aiStatus && !aiStatus.configured && <p className="reports-suggestion">TypeSafe ainda não está configurada nas Integrações do Cadu. IDs exatos de campanha continuam reconhecidos por regra; a revisão semântica fica disponível após configurar a chave.</p>}{data.link_tests.length ? <div className="reports-table-wrap"><table><thead><tr><th>Destino</th><th>Tipo</th><th>Resultado</th><th>Data</th><th>Associação confirmada</th><th>Ações</th></tr></thead><tbody>{data.link_tests.map(item => <tr key={item.id}><td>{item.final_url}</td><td>{item.mode}</td><td>{item.score}/100 · {item.status_label}</td><td>{shortDate(item.created_at)}</td><td>{item.campaign_name || 'Sem campanha'}{item.report_name ? ` · ${item.report_name}` : ''}</td><td><button type="button" className="reports-text-button" disabled={busy} onClick={() => choose(item)}>Associar</button> · <button type="button" className="reports-text-button" disabled={busy} onClick={() => suggest(item)}>Sugerir</button> · <button type="button" className="reports-text-button" onClick={() => showHistory(item)}>Decisões</button>{item.public_token && <> · <button type="button" className="reports-text-button" onClick={() => copyShare(item.public_token)}>Copiar link</button></>}</td></tr>)}</tbody></table></div> : <Empty message="Os testes realizados neste cliente aparecerão aqui." />}</article>
    {editing && <article className="reports-panel reports-span-three"><div className="reports-panel-head"><h2>Associar link à operação</h2><span>Decisão do usuário · {editing.final_url}</span></div>{suggestion && <p className="reports-suggestion">{suggestion.suggestion ? <>Sugestão: <strong>{suggestion.suggestion.name}</strong> · {suggestion.model === 'exact_id' ? 'ID externo exato' : suggestion.model === 'exact_name' ? 'nome exato' : `concentração ${Math.round((suggestion.confidence || 0) * 100)}%`}. Confirme antes de salvar.</> : (suggestion.reason || 'Nenhuma campanha sugerida.')}{suggestion.page_role && <span className="reports-suggestion-role">Tipo provável de página: {({landing: 'entrada', form: 'formulário', thank_you: 'obrigado', content: 'conteúdo', unknown: 'indefinido'})[suggestion.page_role] || suggestion.page_role}.</span>}</p>}<form className="reports-form" onSubmit={confirm}><label>Campanha<select value={campaignId} onChange={event => {setCampaignId(event.target.value); setReportId('');}}><option value="">Sem campanha · limpar associação</option>{data.campaigns.map(item => <option key={item.id} value={item.id}>{item.account_name} · {item.name}</option>)}</select></label><label>Relatório (opcional)<select value={reportId} disabled={!campaignId} onChange={event => setReportId(event.target.value)}><option value="">Sem relatório</option>{availableReports.map(item => <option key={item.id} value={item.id}>{item.campaign_name}</option>)}</select></label>{data.client.role !== 'viewer' && <button type="submit" disabled={busy}>Confirmar associação</button>}</form>{history && <div className="reports-association-history"><h3>Decisões anteriores</h3>{history.length ? history.map((item, index) => <p key={`${item.decided_at}-${index}`}>{shortDate(item.decided_at)} · {item.action === 'clear' ? 'Associação removida' : `Campanha #${item.campaign_id}${item.report_id ? ` · relatório #${item.report_id}` : ''}`} · usuário #{item.decided_by}</p>) : <p>Nenhuma decisão anterior.</p>}</div>}</article>}
  </section>;
}

function Monitor({data, save, busy}) {
  const [keys, setKeys] = useState([]);
  const [runs, setRuns] = useState([]);
  const [label, setLabel] = useState('Google Ads · monitoramento');
  const [sourceKind, setSourceKind] = useState('google_ads_script');
  const [managerAccountId, setManagerAccountId] = useState('');
  const [accountIds, setAccountIds] = useState([]);
  const [script, setScript] = useState('');
  const [generatedKind, setGeneratedKind] = useState('google_ads_script');
  const [localError, setLocalError] = useState('');
  const managers = data.accounts.filter(account => account.platform === 'google_ads' && account.account_kind === 'manager' && account.status !== 'disabled');
  const advertisers = data.accounts.filter(account => account.platform === 'google_ads' && account.account_kind === 'advertiser' && account.status !== 'disabled');
  const children = advertisers.filter(account => String(account.parent_account_id || '') === managerAccountId);
  const formatGoogleId = value => String(value).replace(/^(\d{3})(\d{3})(\d{4})$/, '$1-$2-$3');
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
      const selectedIds = accountIds;
      const created = await save('/ingest-keys', {label, source_kind: sourceKind, manager_account_id: managerAccountId ? managers.find(item => String(item.id) === managerAccountId)?.external_id : '', account_ids: sourceKind === 'google_ads_script' ? selectedIds : []}, false);
      if (sourceKind === 'google_ads_script') {
        const scriptIds = created.allowed_account_ids.map(formatGoogleId);
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
  return <section className="reports-grid reports-grid--three"><article className="reports-panel"><div className="reports-panel-head"><h2>Conectar fonte</h2><span>Instalação</span></div><p>Google Ads envia campanhas e métricas. O webhook recebe conversões confirmadas pelo CRM sem dados pessoais.</p>{data.client.role !== 'viewer' && <form className="reports-form" onSubmit={create}><label>Fonte<select value={sourceKind} onChange={event => {setSourceKind(event.target.value); setLabel(event.target.value === 'conversion_webhook' ? 'CRM · conversões' : 'Google Ads · monitoramento');}}><option value="google_ads_script">Google Ads Script</option><option value="conversion_webhook">CRM / conversões</option></select></label><label>Nome da instalação<input required maxLength="120" value={label} onChange={event => setLabel(event.target.value)} /></label>{sourceKind === 'google_ads_script' && <><label>MCC / conta gerente<select value={managerAccountId} onChange={event => {setManagerAccountId(event.target.value); setAccountIds([]);}}><option value="">Instalação direta em uma conta anunciante</option>{managers.map(item => <option key={item.id} value={item.id}>{item.name} · {formatGoogleId(item.external_id)}</option>)}</select></label>{managerAccountId ? <fieldset className="reports-account-picker"><legend>Contas anunciantes autorizadas</legend>{children.length ? children.map(item => <label key={item.id} className="reports-checkbox"><input type="checkbox" checked={accountIds.includes(item.external_id)} onChange={event => setAccountIds(event.target.checked ? [...accountIds, item.external_id] : accountIds.filter(id => id !== item.external_id))} />{item.name} · {formatGoogleId(item.external_id)}</label>) : <small>Cadastre os anunciantes e associe-os a esta MCC na área Contas.</small>}</fieldset> : <label>Conta anunciante<select value={accountIds[0] || ''} onChange={event => setAccountIds(event.target.value ? [event.target.value] : [])}><option value="">Selecione a conta que receberá os dados</option>{advertisers.filter(item => !item.parent_account_id).map(item => <option key={item.id} value={item.external_id}>{item.name} · {formatGoogleId(item.external_id)}</option>)}</select><small>Para várias contas, cadastre uma MCC, associe os anunciantes e gere o script pela MCC.</small></label>}</>}<button disabled={busy || (sourceKind === 'google_ads_script' && (!accountIds.length || (managerAccountId && !children.length)))} type="submit">Gerar integração</button></form>}{localError && <p className="reports-error">{localError}</p>}</article><article className="reports-panel reports-span-two"><div className="reports-panel-head"><h2>Chaves de ingestão</h2><span>{keys.length} criadas</span></div>{keys.length ? <div className="reports-table-wrap"><table><thead><tr><th>Nome</th><th>Fonte</th><th>MCC / contas permitidas</th><th>Último envio</th><th>Estado</th><th></th></tr></thead><tbody>{keys.map(item => <tr key={item.id}><td>{item.label}</td><td>{item.source_kind === 'conversion_webhook' ? 'CRM' : 'Google Ads'}</td><td>{item.source_kind === 'google_ads_script' ? <>{item.manager_external_id ? `MCC ${formatGoogleId(item.manager_external_id)} · ` : ''}{item.allowed_account_ids?.length ? item.allowed_account_ids.map(formatGoogleId).join(', ') : item.bound_account_id || 'Vincula no primeiro envio'}</> : '—'}</td><td>{shortDate(item.last_used_at)}</td><td>{sourceHealth(item)}</td><td>{!item.revoked_at && data.client.role !== 'viewer' && <button className="reports-text-button" disabled={busy} onClick={() => revoke(item.id)}>Revogar</button>}</td></tr>)}</tbody></table></div> : <Empty message="Gere uma chave para conectar uma fonte." />}</article>{script && <article className="reports-panel reports-span-three"><div className="reports-panel-head"><h2>{generatedKind === 'conversion_webhook' ? 'Contrato do webhook' : 'Script gerado'}</h2><span>Copie agora: a chave não será mostrada novamente</span></div><textarea className="reports-code" readOnly value={script} aria-label="Código da integração" /><button className="reports-copy" onClick={() => navigator.clipboard.writeText(script)}>Copiar</button></article>}<article className="reports-panel reports-span-three"><div className="reports-panel-head"><h2>Últimos envios do Google Ads</h2><span>{runs.length} lotes</span></div>{runs.length ? <div className="reports-table-wrap"><table><thead><tr><th>Recebido</th><th>Período</th><th>Linhas</th><th>Estado</th></tr></thead><tbody>{runs.map(item => <tr key={item.id}><td>{shortDate(item.created_at)}</td><td>{shortDate(item.period_start)} – {shortDate(item.period_end)}</td><td>{integer(item.record_count)}</td><td>{item.status === 'completed' ? 'Concluído' : item.status}</td></tr>)}</tbody></table></div> : <Empty message="Os lotes recebidos aparecerão aqui." />}</article></section>;
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

const FLOW_CARD_WIDTH = 172;
const FLOW_CARD_HEIGHT = 116;
const FLOW_GRID_SIZE = 20;

function Flow({data, save, busy, filters}) {
  const [flowView, setFlowViewState] = useState(() => {const requested=new URLSearchParams(location.search).get('flow_view');return ['create','edit','monitor'].includes(requested)?requested:'create';});
  const [flow, setFlow] = useState({tags: [], steps: [], flows: [], tests: [], tag_urls: {}, activity: [], online: 0, conversions: 0, confirmed: []});
  const [discovery, setDiscovery] = useState({run:null,pages:[]});
  const [discoveryBusy, setDiscoveryBusy] = useState(false);
  const [selectedFlowId, setSelectedFlowId] = useState(() => new URLSearchParams(location.search).get('flow_id') || '');
  const [flowName, setFlowName] = useState('');
  const [flowHost, setFlowHost] = useState('');
  const [flowConfig, setFlowConfig] = useState({nodes: [], edges: []});
  const [selectedNodeId, setSelectedNodeId] = useState('');
  const [connectSourceId, setConnectSourceId] = useState('');
  const [draggingNode, setDraggingNode] = useState('');
  const [paletteDragOver, setPaletteDragOver] = useState(false);
  const [snapToGrid, setSnapToGrid] = useState(true);
  const [flowLayoutNote, setFlowLayoutNote] = useState('');
  const [simulation, setSimulation] = useState(null);
  const [verifyUrl, setVerifyUrl] = useState('');
  const [verifyState, setVerifyState] = useState('');
  const [copyState, setCopyState] = useState('');
  const [localError, setLocalError] = useState('');
  const [monitorInterval, setMonitorInterval] = useState(15);
  const reload = () => {
    const params = new URLSearchParams({client_id: String(data.client.client_id), days: filters.period,
      start_date: filters.startDate, end_date: filters.endDate});
    if (selectedFlowId) params.set('flow_id', selectedFlowId);
    if (filters.platform) params.set('platform', filters.platform);
    if (filters.account) params.set('account_id', filters.account);
    if (filters.campaign) params.set('campaign_id', filters.campaign);
    return json(`/connect/api/v1/reports/flow?${params}`).then(setFlow);
  };
  const loadDiscoveries = async flowId => {
    if (!flowId) {setDiscovery({run:null,pages:[]});return;}
    setDiscovery(await json(`/connect/api/v1/reports/flow/flows/${flowId}/discoveries?client_id=${data.client.client_id}`));
  };
  useEffect(() => {reload().catch(failure => setLocalError(failure.message));}, [data.client.client_id, filters.period, filters.startDate, filters.endDate, filters.platform, filters.account, filters.campaign, selectedFlowId]);
  useEffect(() => {loadDiscoveries(selectedFlowId).catch(failure => setLocalError(failure.message));}, [selectedFlowId,data.client.client_id]);
  useEffect(() => {const found = flow.flows.find(item => item.id === selectedFlowId); if (found) {setFlowName(found.name); setFlowHost(found.allowed_host); setFlowConfig(found.config || {nodes: [], edges: []});}}, [selectedFlowId, flow.flows]);
  useEffect(() => {const found=flow.flows.find(item=>item.id===selectedFlowId);if(found)setMonitorInterval(Number(found.monitor_interval_minutes)||15);}, [selectedFlowId,flow.flows]);
  useEffect(() => {if(flowView!=='monitor'||!flow.flows.find(item=>item.id===selectedFlowId)?.monitor_enabled)return;const timer=window.setInterval(()=>reload().catch(failure=>setLocalError(failure.message)),60000);return()=>window.clearInterval(timer);}, [flowView,selectedFlowId,flow.flows]);
  const navigateFlowView = view => {setFlowViewState(view);const url=new URL(location.href);url.searchParams.set('flow_view',view);history.replaceState(null,'',url);};
  const chooseFlow = id => {setSelectedFlowId(id);const url=new URL(location.href);if(id)url.searchParams.set('flow_id',id);else url.searchParams.delete('flow_id');history.replaceState(null,'',url);};
  const openFlow = (item, view) => {chooseFlow(item.id);navigateFlowView(view);};
  const newFlow = async event => {event.preventDefault(); try {const result = await save('/flow/flows', {name: flowName, allowed_host: flowHost}, false); await reload(); chooseFlow(result.flow.id);navigateFlowView('edit');} catch (failure) {setLocalError(failure.message);}};
  const addNode = (type, options = {}, point = null) => {const defaults={source:'Origem de tráfego',page:'Página / URL',form:'Formulário',event:'Evento',conversion:'Conversão',whatsapp:'Clique WhatsApp',error:'Página de erro'};const index=flowConfig.nodes.length;const node={id:crypto.randomUUID(),type,title:options.title||defaults[type]||type,path:type==='page'?'/':type==='form'?'/formulario':type==='conversion'?'/obrigado':type==='error'?'/erro':type==='event'?'/':'',event_name:type==='event'?'lead_qualificado':undefined,source:type==='source'?(options.source||'google'):undefined,x:point?Math.max(16,snap(point.x-80)):24+(index%3)*240,y:point?Math.max(100,snap(point.y-30)):80+Math.floor(index/3)*160,fields:type==='form'?[{name:'nome',label:'Nome',required:true},{name:'email',label:'E-mail',required:true}]:[]};setFlowConfig(current=>({...current,nodes:[...current.nodes,node]}));setSelectedNodeId(node.id);};
  const startPaletteDrag = (event, item) => {event.dataTransfer.effectAllowed='copy';event.dataTransfer.setData('application/x-cadu-flow-node',JSON.stringify(item));};
  const dropPaletteNode = event => {event.preventDefault();setPaletteDragOver(false);try{const item=JSON.parse(event.dataTransfer.getData('application/x-cadu-flow-node'));const bounds=event.currentTarget.getBoundingClientRect();addNode(item.type,item,{x:event.clientX-bounds.left+event.currentTarget.scrollLeft,y:event.clientY-bounds.top+event.currentTarget.scrollTop});}catch(_){setLocalError('Não foi possível adicionar este bloco ao fluxo.');}};
  const updateNode = (key,value) => setFlowConfig({...flowConfig,nodes:flowConfig.nodes.map(node=>node.id===selectedNodeId?{...node,[key]:value}:node)});
  const connectNode = targetId => {if(!connectSourceId||connectSourceId===targetId)return; if(flowConfig.edges.some(edge=>edge.from===connectSourceId&&edge.to===targetId)){setConnectSourceId('');return;}const pending=[targetId],seen=new Set();while(pending.length){const current=pending.pop();if(current===connectSourceId){setFlowLayoutNote('Essa conexão criaria um ciclo. O fluxo deve avançar da entrada para as saídas.');setConnectSourceId('');return;}if(seen.has(current))continue;seen.add(current);flowConfig.edges.filter(edge=>edge.from===current).forEach(edge=>pending.push(edge.to));}setFlowConfig(current=>({...current,edges:[...current.edges,{id:crypto.randomUUID(),from:connectSourceId,to:targetId,label:'Próximo'}]})); setSelectedNodeId(targetId); setConnectSourceId('');setFlowLayoutNote('Conexão adicionada. Revise o caminho antes de publicar.');};
  const snap = value => snapToGrid ? Math.round(value/FLOW_GRID_SIZE)*FLOW_GRID_SIZE : value;
  const moveNode = event => {if(!draggingNode)return;const canvas=event.currentTarget.getBoundingClientRect();const x=Math.max(20,event.clientX-canvas.left+event.currentTarget.scrollLeft-FLOW_CARD_WIDTH/2);const y=Math.max(100,event.clientY-canvas.top+event.currentTarget.scrollTop-28);setFlowConfig(current=>({...current,nodes:current.nodes.map(node=>node.id===draggingNode?{...node,x:snap(x),y:snap(y)}:node)}));};
  const autoArrange = () => {
    const nodes=flowConfig.nodes;if(!nodes.length)return;
    const byId=new Map(nodes.map(node=>[node.id,node]));
    const incoming=new Map(nodes.map(node=>[node.id,0]));
    const outgoing=new Map(nodes.map(node=>[node.id,[]]));
    flowConfig.edges.forEach(edge=>{if(byId.has(edge.from)&&byId.has(edge.to)){incoming.set(edge.to,(incoming.get(edge.to)||0)+1);outgoing.get(edge.from).push(edge.to);}});
    const originalOrder=new Map(nodes.map((node,index)=>[node.id,index]));
    const depth=new Map(nodes.map(node=>[node.id,0]));
    const queue=nodes.filter(node=>(incoming.get(node.id)||0)===0||node.isEntry||node.type==='source').sort((a,b)=>Number(Boolean(b.isEntry||b.type==='source'))-Number(Boolean(a.isEntry||a.type==='source'))||a.x-b.x||a.y-b.y);
    const visitedIds=new Set();let visited=0;
    while(queue.length){const node=queue.shift();if(visitedIds.has(node.id))continue;visitedIds.add(node.id);visited++;for(const nextId of outgoing.get(node.id)||[]){depth.set(nextId,Math.max(depth.get(nextId)||0,(depth.get(node.id)||0)+1));incoming.set(nextId,incoming.get(nextId)-1);if(incoming.get(nextId)===0)queue.push(byId.get(nextId));}}
    if(visited<nodes.length){nodes.filter(node=>!depth.has(node.id)||incoming.get(node.id)>0).sort((a,b)=>a.x-b.x||a.y-b.y).forEach(node=>depth.set(node.id,Math.max(depth.get(node.id)||0,Math.ceil((node.x||0)/(FLOW_CARD_WIDTH+64)))));}
    const columns=new Map();nodes.forEach(node=>{const column=depth.get(node.id)||0;if(!columns.has(column))columns.set(column,[]);columns.get(column).push(node);});
    const arranged=[];[...columns.keys()].sort((a,b)=>a-b).forEach(column=>columns.get(column).sort((a,b)=>(originalOrder.get(a.id)||0)-(originalOrder.get(b.id)||0)).forEach((node,row)=>arranged.push({...node,x:20+column*(FLOW_CARD_WIDTH+68),y:100+row*(FLOW_CARD_HEIGHT+44)})));
    setFlowConfig(current=>({...current,nodes:arranged}));
  };
  const autoConnect = () => {
    const nodes=[...flowConfig.nodes].sort((a,b)=>a.x-b.x||a.y-b.y);
    if(nodes.length<2)return;
    const edges=[...flowConfig.edges];let added=0;
    const reaches=(start,target)=>{const seen=new Set(),pending=[start];while(pending.length){const current=pending.pop();if(current===target)return true;if(seen.has(current))continue;seen.add(current);edges.filter(edge=>edge.from===current).forEach(edge=>pending.push(edge.to));}return false;};
    nodes.slice(0,-1).forEach((node,index)=>{const next=nodes[index+1];if(edges.some(edge=>edge.from===node.id&&edge.to===next.id))return;if(reaches(next.id,node.id))return;edges.push({id:crypto.randomUUID(),from:node.id,to:next.id,label:'Próximo'});added++;});
    setFlowConfig(current=>({...current,edges}));
    setFlowLayoutNote(added?`${added} conexão${added===1?'':'ões'} adicionada${added===1?'':'s'} na ordem visual. Revise o caminho antes de publicar.`:'Não havia conexões seguras a adicionar. Revise a posição dos blocos ou as ramificações existentes.');
  };
  const saveFlow = async () => {if(!selectedFlowId)return; try {await save(`/flow/flows/${selectedFlowId}`,{name:flowName,config:flowConfig},false,'PATCH'); await reload();} catch(failure){setLocalError(failure.message);}};
  const publishFlow = async () => {if(!selectedFlowId)return; try {await save(`/flow/flows/${selectedFlowId}/publish`,{},false);await reload();}catch(failure){setLocalError(failure.message);}};
  const configureMonitor = async enabled => {if(!selectedFlowId)return;try{await save(`/flow/flows/${selectedFlowId}/monitor`,{enabled,interval_minutes:monitorInterval},false,'PATCH');await reload();}catch(failure){setLocalError(failure.message);}};
  const checkMonitorNow = async () => {if(!selectedFlowId)return;try{await save(`/flow/flows/${selectedFlowId}/monitor/check`,{},false);await reload();}catch(failure){setLocalError(failure.message);}};
  const testFlow = async () => {if(!selectedFlowId)return;const current=flow.flows.find(item=>item.id===selectedFlowId);if(current?.status==='published'){setLocalError('Despublique o fluxo para editar e executar um teste fictício.');return;}const demo=[{kind:'page_view',path:'/',source:'google'},{kind:'page_view',path:'/landing',source:'google'},{kind:'form_submit',path:'/formulario',source:'Teste fictício',data:{nome:'Lead de teste',email:'teste@example.invalid'}},{kind:'whatsapp_click',path:'/formulario',source:'whatsapp'},{kind:'conversion',path:'/obrigado',source:'google'}]; try {const result=await save(`/flow/flows/${selectedFlowId}/test`,{events:demo},false);setSimulation(result);}catch(failure){setLocalError(failure.message);}};
  const discoverSite = async () => {if(!selectedFlowId)return;const current=flow.flows.find(item=>item.id===selectedFlowId);if(!current)return;const resume=discovery.run?.status==='partial'&&Number(discovery.run.pending_count)>0;setDiscoveryBusy(true);setLocalError('');try{const result=await save(`/flow/flows/${selectedFlowId}/discover`,{root_url:`https://${current.allowed_host}`,...(resume?{run_id:discovery.run.id}:{})},false);if(result.run.status==='failed')setLocalError('Não encontramos páginas acessíveis. Confira se o domínio está no ar e se o sitemap permite a leitura.');await loadDiscoveries(selectedFlowId);}catch(failure){setLocalError(failure.message);}finally{setDiscoveryBusy(false);}};
  const chooseDiscoveredPage = async (page,selection) => {setDiscoveryBusy(true);setLocalError('');try{await save(`/flow/flows/${selectedFlowId}/discoveries/${page.id}/select`,{selection,campaign_id:selection==='ignore'?null:page.campaign_id||null},false);await Promise.all([loadDiscoveries(selectedFlowId),reload()]);}catch(failure){setLocalError(failure.message);}finally{setDiscoveryBusy(false);}};
  const associatePageCampaign = async (page,campaignId) => {setDiscoveryBusy(true);setLocalError('');try{const selection=page.selected_kind==='conversion'?'conversion':page.selected_kind==='error'?'error':page.selected_kind==='form'?'form':page.selected_kind==='page'?(page.selected_as_entry?'entry':'intermediate'):'ignore';await save(`/flow/flows/${selectedFlowId}/discoveries/${page.id}/select`,{selection,campaign_id:campaignId||null},false);await Promise.all([loadDiscoveries(selectedFlowId),reload()]);}catch(failure){setLocalError(failure.message);}finally{setDiscoveryBusy(false);}};
  const verifyInstall = async tag => {setVerifyState('checking'); try {const parsed = new URL(verifyUrl);const root=tag.allowed_host.toLowerCase().replace(/^www\./,'');if(parsed.hostname.toLowerCase()!==root&&!parsed.hostname.toLowerCase().endsWith(`.${root}`)) throw new Error('A URL precisa usar o domínio autorizado ou um subdomínio dele.'); window.open(parsed.href, '_blank', 'noopener'); setVerifyState('waiting'); window.setTimeout(() => reload().then(value => {const seen = value.activity.some(row => row.tag_id === tag.id); setVerifyState(seen ? 'success' : 'waiting');}), 6000);} catch (failure) {setLocalError(failure.message); setVerifyState('error');}};
  const copy = async value => {try {await navigator.clipboard.writeText(value); setCopyState('Copiado'); window.setTimeout(() => setCopyState(''), 1800);} catch (_) {setCopyState('Não foi possível copiar');}};
  const snippet = flowItem => `<script async src="${flow.tag_urls?.flow || `${location.origin}/static/cadu_connect/cadu-flow-tag.js?client=${data.client.client_id}`}" data-cadu-key="${flowItem.public_key}" data-cadu-client="${data.client.client_id}" data-cadu-flow="${flowItem.flow_code}"></script>`;
  const paletteGroups = [
    ['Páginas', [{type:'page',label:'Página / URL'}]],
    ['Captura de dados', [{type:'form',label:'Formulário'}, {type:'event',label:'Evento'}, {type:'whatsapp',label:'Clique WhatsApp',source:'whatsapp'}]],
    ['Conversões e erros', [{type:'conversion',label:'Conversão'}, {type:'error',label:'Página de erro'}]],
  ];
  const selectedFlow = flow.flows.find(item => item.id === selectedFlowId);
  const readOnly = data.client.role === 'viewer' || selectedFlow?.status === 'published';
  const scannedIntegrations = discovery.platform_integrations || [];
  const scannedPageCount = Number(discovery.integration_scan_pages || 0);
  const channelOrigins = FLOW_CHANNELS.map(channel => {
    const aliases = channel.aliases.map(value => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase());
    const events = (flow.events || []).filter(item => {
      const source = String(item.source_label || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
      return aliases.some(alias => source.includes(alias));
    });
    const detected = scannedIntegrations.filter(item => item.platform === channel.id);
    return {channel, total: events.reduce((sum, item) => sum + Number(item.total || 0), 0),
      sources: events.map(item => item.source_label), tags: detected.filter(item => item.signal === 'tracker'),
      links: detected.filter(item => item.signal === 'site_link')};
  });
  const monitorCanvasNodes = (flow.canvas_nodes || []).map((node, index) => ({...node,
    x: Number.isFinite(Number(node.x)) ? Number(node.x) : 70 + (index % 3) * 220,
    y: Number.isFinite(Number(node.y)) ? Number(node.y) : 60 + Math.floor(index / 3) * 130}));
  const monitorCanvasById = Object.fromEntries(monitorCanvasNodes.map(node => [String(node.id), node]));
  const monitorCanvasWidth = Math.max(760, ...monitorCanvasNodes.map(node => node.x + 202));
  const monitorCanvasHeight = Math.max(190, ...monitorCanvasNodes.map(node => node.y + 130));
  const viewTabs = [['create','Criar'],['edit','Editar'],['monitor','Jornada do site']];
  return <>
    <nav className="reports-flow-views" aria-label="Etapas de trabalho dos fluxos">
      <div><h2>Fluxos de captura e conversão</h2><p>Criação, edição visual e acompanhamento em áreas separadas.</p></div>
      <div role="tablist" aria-label="Área de fluxos">{viewTabs.map(([id,label])=><button type="button" role="tab" aria-selected={flowView===id} className={flowView===id?'is-active':''} key={id} onClick={()=>navigateFlowView(id)}>{label}{id==='create'&&flow.flows.length>0?<small>{flow.flows.length}</small>:null}</button>)}</div>
    </nav>
    {localError&&<div className="reports-error" role="alert">{localError}</div>}
    {flowView==='create'&&<>
      <section className="reports-panel reports-flow-create-page">
        <div className="reports-panel-head"><div><h3>Novo fluxo</h3><p>Escolha o nome do fluxo e o domínio que receberá a tag. Depois, associe as etapas às campanhas deste cliente.</p></div><span>Cliente Reports: {data.client.client_name}</span></div>
        {data.client.role!=='viewer'?<form className="reports-form reports-flow-create" onSubmit={newFlow}><label>Nome do fluxo<input required maxLength="120" value={flowName} onChange={event=>setFlowName(event.target.value)} placeholder="Ex.: Campanha de aquisição 2026" /></label><label>Domínio do site<input required value={flowHost} onChange={event=>setFlowHost(event.target.value)} placeholder="exemplo.com.br" /></label><button disabled={busy}>Criar fluxo e abrir editor</button></form>:<p>Seu acesso permite acompanhar fluxos existentes.</p>}
      </section>
      <section className="reports-panel reports-flow-list-panel"><div className="reports-panel-head"><div><h3>Fluxos deste cliente</h3><p>Abra o editor visual ou acompanhe os resultados de cada domínio.</p></div><span>{flow.flows.length} fluxos</span></div>
        {flow.flows.length?<div className="reports-flow-list">{flow.flows.map(item=><article className="reports-flow-list-item" key={item.id}><div><small>{item.flow_code} · {item.status==='published'?'Publicado':'Rascunho'}</small><strong>{item.name}</strong><span>{item.allowed_host}{item.campaign_names?` · Campanhas: ${item.campaign_names}`:''}</span><small>Monitoramento: {item.monitor_enabled?({online:'online',degraded:'com falhas',offline:'offline',checking:'verificando',unknown:'aguardando checagem'})[item.monitor_status]||'ativo':'não ativado'}</small></div><div className="reports-flow-list-actions"><button type="button" onClick={()=>openFlow(item,'edit')}>Editar fluxo</button><button type="button" onClick={()=>openFlow(item,'monitor')}>Monitorar</button></div></article>)}</div>:<Empty message="Nenhum fluxo foi criado para este cliente." />}
      </section>
    </>}
    {flowView==='edit'&&(selectedFlow?<>
      <section className="reports-panel reports-flow-builder">
        <div className="reports-flow-topbar"><div className="reports-flow-title-field"><label>Nome do fluxo<input value={flowName} readOnly={readOnly} onChange={event=>setFlowName(event.target.value)} maxLength="120"/></label><p>{selectedFlow?.flow_code} · {selectedFlow?.allowed_host} · {readOnly?'Publicado — somente leitura':'rascunho editável'}</p></div><div className="reports-flow-actions"><select aria-label="Fluxo em edição" value={selectedFlowId} onChange={event=>{chooseFlow(event.target.value);setSelectedNodeId('');}}>{flow.flows.map(item=><option key={item.id} value={item.id}>{item.flow_code} · {item.name}</option>)}</select><button type="button" onClick={saveFlow} disabled={!selectedFlowId||busy||readOnly}>Salvar</button><button type="button" onClick={testFlow} disabled={!selectedFlowId||busy||readOnly}>Testar</button>{selectedFlow?.status==='published'?<button type="button" onClick={async()=>{try{await save(`/flow/flows/${selectedFlowId}/unpublish`,{},false);await reload();}catch(failure){setLocalError(failure.message);}}} disabled={busy||data.client.role==='viewer'}>Despublicar para editar</button>:<button type="button" className="reports-flow-publish" onClick={publishFlow} disabled={!selectedFlowId||busy||!flowConfig.nodes.length||data.client.role==='viewer'}>Publicar</button>}</div></div>
        <div className="reports-flow-designer"><aside className="reports-node-palette"><p className="reports-palette-note">Origens são lidas de UTMs e referências. O editor adiciona páginas, formulários, eventos, conversões e páginas de erro que a tag consegue medir.</p><input aria-label="Buscar blocos" placeholder="Buscar blocos…" onChange={event=>document.querySelectorAll('.reports-palette-group button').forEach(button=>button.hidden=!button.textContent.toLowerCase().includes(event.target.value.toLowerCase()))}/>{paletteGroups.map(([heading,items])=><div className="reports-palette-group" key={heading}><strong>{heading}</strong>{items.map((item,index)=><button type="button" key={`${item.type}:${item.source||''}:${index}`} draggable={!readOnly} disabled={readOnly} onDragStart={event=>startPaletteDrag(event,item)} onClick={()=>addNode(item.type,item)}><span className="reports-palette-icon">{item.source?<FlowPlatformLogo platform={item.source}/>:item.type==='form'?'▤':item.type==='conversion'?'✓':item.type==='page'?'▧':item.type==='error'?'!':'◇'}</span>{item.label}</button>)}</div>)}</aside>
          <div className={`reports-flow-canvas${paletteDragOver?' is-drop-target':''}`} style={{minHeight:Math.max(570,...flowConfig.nodes.map(node=>Number(node.y||0)+FLOW_CARD_HEIGHT+48))}} aria-label="Editor visual do fluxo" onDragOver={event=>{event.preventDefault();if(!readOnly)setPaletteDragOver(true);}} onDragLeave={()=>setPaletteDragOver(false)} onDrop={readOnly?undefined:dropPaletteNode} onPointerMove={readOnly?undefined:moveNode} onPointerUp={()=>setDraggingNode('')} onPointerLeave={()=>setDraggingNode('')}><div className="reports-canvas-toolbar"><span>{selectedFlow?.flow_code} · {flowName}</span><span>{readOnly?'Fluxo publicado':connectSourceId?'Escolha o bloco de destino':paletteDragOver?'Solte para adicionar':flowLayoutNote||'Entrada → páginas e ações → conversão ou saída'}</span><div className="reports-canvas-tools"><button type="button" onClick={()=>setSnapToGrid(value=>!value)} aria-pressed={snapToGrid}>{snapToGrid?'Grade ativa':'Grade livre'}</button><button type="button" onClick={autoArrange} disabled={readOnly||!flowConfig.nodes.length}>Alinhar fluxo</button><button type="button" onClick={autoConnect} disabled={readOnly||flowConfig.nodes.length<2}>Conectar sequência</button><button type="button" onClick={testFlow} disabled={readOnly}>Testar</button></div></div><svg className="reports-edge"><defs><marker id="reports-flow-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#2083f7"/></marker></defs>{flowConfig.edges.map(edge=>{const from=flowConfig.nodes.find(node=>node.id===edge.from),to=flowConfig.nodes.find(node=>node.id===edge.to);return from&&to?<path key={edge.id} d={`M ${from.x+FLOW_CARD_WIDTH} ${from.y+FLOW_CARD_HEIGHT/2} C ${from.x+FLOW_CARD_WIDTH+36} ${from.y+FLOW_CARD_HEIGHT/2}, ${to.x-36} ${to.y+FLOW_CARD_HEIGHT/2}, ${to.x} ${to.y+FLOW_CARD_HEIGHT/2}`}/>:null})}</svg>{flowConfig.nodes.map(node=><div className={`reports-flow-block${node.id===selectedNodeId?' is-selected':''}${node.isEntry||node.type==='source'?' is-entry':''}${['conversion','error'].includes(node.type)?' is-exit':''}`} style={{left:node.x,top:node.y}} key={node.id} onPointerDown={event=>{if(readOnly||event.target.closest('button'))return;event.currentTarget.setPointerCapture(event.pointerId);setDraggingNode(node.id);setSelectedNodeId(node.id);}} onClick={()=>{if(!readOnly&&connectSourceId)connectNode(node.id);else setSelectedNodeId(node.id);}}><div className="reports-flow-block-head">{node.source&&<FlowPlatformLogo platform={node.source}/>}<small>{node.type==='source'?`Entrada · ${FLOW_PLATFORMS[node.source]?.label||node.source}`:node.isEntry?'Entrada':node.type==='conversion'?'Saída · Conversão':node.type==='error'?'Saída · Erro':node.type}</small></div><strong>{node.title}</strong><span>{node.path||node.event||'Configure este bloco'}</span>{node.stepId&&discovery.pages.find(page=>String(page.step_id)===String(node.stepId))?.campaign_id&&<small>{data.campaigns.find(campaign=>campaign.id===discovery.pages.find(page=>String(page.step_id)===String(node.stepId)).campaign_id)?.name||'Campanha associada'}</small>}{!readOnly&&<div className="reports-block-actions"><button type="button" onClick={event=>{event.stopPropagation();setSelectedNodeId(node.id);setConnectSourceId(node.id);}}>Conectar</button><button type="button" aria-label="Mover para esquerda" onClick={event=>{event.stopPropagation();setFlowConfig(current=>({...current,nodes:current.nodes.map(item=>item.id===node.id?{...item,x:Math.max(20,snap(item.x-25))}:item)}));}}>←</button><button type="button" aria-label="Mover para direita" onClick={event=>{event.stopPropagation();setFlowConfig(current=>({...current,nodes:current.nodes.map(item=>item.id===node.id?{...item,x:snap(item.x+25)}:item)}));}}>→</button></div>}{node.id===selectedNodeId&&<em>{readOnly?'Publicado':connectSourceId===node.id?'Origem da conexão selecionada':connectSourceId?'Clique para conectar':'Arraste para organizar'}</em>}</div>)}{!flowConfig.nodes.length&&<div className="reports-canvas-empty">Arraste um bloco da paleta ou clique nele para começar.</div>}</div>
          <aside className="reports-node-settings"><button className="reports-node-close" type="button" aria-label="Fechar propriedades" onClick={()=>setSelectedNodeId('')}>×</button>{(()=>{const node=flowConfig.nodes.find(item=>item.id===selectedNodeId);return node?<><h3>{node.title}</h3><p>Propriedades do bloco · {node.type}</p><label className="reports-entry-toggle"><input type="checkbox" checked={Boolean(node.isEntry)} disabled={readOnly} onChange={event=>updateNode('isEntry',event.target.checked)}/>Definir como ponto de entrada</label>{node.host&&<p>Domínio: <strong>{node.host}</strong></p>}<label>Nome<input readOnly={readOnly} value={node.title} onChange={event=>updateNode('title',event.target.value)}/></label>{['page','form','event','conversion','whatsapp','error'].includes(node.type)&&<label>Página / URL<input readOnly={readOnly} value={node.path||''} onChange={event=>updateNode('path',event.target.value)} placeholder="/caminho"/></label>}{node.type==='event'&&<label>Nome do evento<input readOnly={readOnly} required pattern="[A-Za-z][A-Za-z0-9_]{0,79}" value={node.event_name||''} onChange={event=>updateNode('event_name',event.target.value)} placeholder="lead_qualificado"/><small>Use letras, números e _; o evento precisa usar o mesmo nome enviado pelo site.</small></label>}{node.type==='form'&&<><strong>Campos de teste</strong>{(node.fields||[]).map((field,index)=><label key={index}>{field.label}<input readOnly={readOnly} value={field.label} onChange={event=>updateNode('fields',node.fields.map((item,i)=>i===index?{...item,label:event.target.value}:item))}/></label>)}{!readOnly&&<button type="button" onClick={()=>updateNode('fields',[...(node.fields||[]),{name:'campo',label:'Novo campo',required:false}])}>Adicionar campo</button>}</>}{node.type==='whatsapp'&&<p>O site confirma o link wa.me; o fluxo registra o clique depois da instalação da tag.</p>}{!readOnly&&<button className="reports-danger-button" type="button" onClick={()=>{setFlowConfig(current=>({...current,nodes:current.nodes.filter(item=>item.id!==node.id),edges:current.edges.filter(edge=>edge.from!==node.id&&edge.to!==node.id)}));setSelectedNodeId('');}}>Remover bloco</button>}</>:<><h3>Propriedades</h3><p>Selecione um bloco para configurar página, formulário, evento ou conversão.</p></>;})()}</aside>
        </div>
      </section>
      <section className="reports-grid reports-grid--three"><article className="reports-panel reports-span-three reports-flow-discovery"><div className="reports-panel-head"><div><h3>Páginas e conversões do domínio</h3><p>Mapeia páginas, formulários, subdomínios e links de contato; valores digitados não são lidos.</p></div><button type="button" disabled={discoveryBusy||busy||readOnly||(discovery.run?.status==='partial'&&!Number(discovery.run?.pending_count))} onClick={discoverSite}>{discoveryBusy?'Analisando…':discovery.run?.status==='partial'&&Number(discovery.run.pending_count)>0?'Continuar análise':discovery.run?'Analisar o site novamente':'Analisar site'}</button></div>{discovery.run&&<p className="reports-info">{integer(discovery.run.page_count)} páginas · {discovery.run.status==='completed'?'análise concluída':discovery.run.status==='partial'?`${integer(discovery.run.pending_count)} URLs pendentes`:'análise sem páginas válidas'}</p>}{discovery.pages?.length>0?<div className="reports-table-wrap"><table><thead><tr><th>Página</th><th>Host</th><th>Sinais</th><th>Sugestão</th><th>Etapa do fluxo</th><th>Campanha associada</th></tr></thead><tbody>{discovery.pages.map(page=>{const choice=page.selected_kind==='conversion'?'conversion':page.selected_kind==='error'?'error':page.selected_kind==='form'?'form':page.selected_kind==='page'?(page.selected_as_entry?'entry':'intermediate'):'ignore';const roleName={entry:'Entrada provável',form:'Formulário provável',conversion:'Conversão provável',error:'Página de erro provável',intermediate:'Intermediária'}[page.suggested_role];return <tr key={page.id}><td><strong>{page.title||page.path_prefix}</strong><small><a href={page.url} target="_blank" rel="noopener noreferrer">{page.path_prefix}</a></small></td><td>{page.page_host}</td><td>{page.form_count?`${page.form_count} formulário(s)`:page.evidence?.signals?.[0]||'Link interno'}{page.evidence?.integrations?.length>0&&<small>{page.evidence.integrations.map(item=>FLOW_CHANNELS.find(channel=>channel.id===item.platform)?.label||item.platform).join(' · ')}</small>}</td><td>{roleName}</td><td><select aria-label={`Etapa para ${page.path_prefix}`} value={choice} disabled={discoveryBusy||busy||readOnly} onChange={event=>chooseDiscoveredPage(page,event.target.value)}><option value="ignore">Não incluir</option><option value="entry">Ponto de partida</option><option value="intermediate">Etapa intermediária</option>{page.form_count>0&&<option value="form">Formulário</option>}<option value="conversion">Conversão</option><option value="error">Página de erro</option></select></td><td><select aria-label={`Campanha para ${page.path_prefix}`} value={page.campaign_id||''} disabled={discoveryBusy||busy||readOnly||!page.selected_kind} onChange={event=>associatePageCampaign(page,event.target.value)}><option value="">Sem campanha</option>{data.campaigns.map(campaign=><option key={campaign.id} value={campaign.id}>{campaign.account_name} · {campaign.name}</option>)}</select></td></tr>;})}</tbody></table></div>:<Empty message="Analise o domínio para sugerir páginas, formulários, conversões e erros."/>}</article></section>
      <section className="reports-panel reports-platform-panel"><div className="reports-panel-head"><div><h3>Redes e origens detectadas</h3><p>Sinais técnicos da varredura e origens reais recebidas pela tag.</p></div><span>{scannedPageCount?`${integer(scannedPageCount)} páginas verificadas`:'Aguardando análise do site'}</span></div><div className="reports-platform-grid">{channelOrigins.map(({channel,tags,links})=>{const supportsTagScan=['google_ads','meta_ads','linkedin_ads','tiktok','amazon_ads','spotify_ads','disney_ads','email'].includes(channel.id);const trackerCount=tags.reduce((sum,item)=>sum+item.pages,0);const linkCount=links.reduce((sum,item)=>sum+item.pages,0);return <article className="reports-platform-row" key={channel.id}><FlowPlatformLogo platform={channel.id}/><strong>{channel.label}</strong><span className={trackerCount||linkCount?'is-detected':''}>{scannedPageCount?(trackerCount?`Tag em ${trackerCount} página(s)`:linkCount?`Link em ${linkCount} página(s)`:supportsTagScan?'Nenhuma tag detectada':'Origem via UTM/referrer'):'Site ainda não analisado'}</span>{trackerCount>0&&<small>{tags.flatMap(item=>item.evidence).slice(0,2).join(' · ')}</small>}</article>;})}</div><p className="reports-platform-note">Netflix, Serasa, Disney, Spotify, Amazon, e-mail e outras fontes podem aparecer por UTMs ou domínio de referência. A presença da marca na página não é tratada como prova de conexão de anúncios.</p></section>
      <section className="reports-grid reports-grid--three"><article className="reports-panel"><div className="reports-panel-head"><h3>Instalação deste fluxo</h3><span>{selectedFlow?.flow_code}</span></div><p>Instale o snippet no domínio e seus subdomínios. As conexões de mídia ficam separadas da Supertag.</p><code className="reports-flow-snippet">{snippet(selectedFlow)}</code><button type="button" className="reports-text-button" onClick={()=>copy(snippet(selectedFlow))}>Copiar snippet</button><label className="reports-verify-label">Abrir página para validar<input type="url" value={verifyUrl} onChange={event=>setVerifyUrl(event.target.value)} placeholder={`https://${selectedFlow?.allowed_host}/landing`}/></label><button type="button" disabled={!verifyUrl||readOnly} onClick={()=>verifyInstall(selectedFlow)}>Verificar instalação</button>{verifyState==='waiting'&&<small>Aguardando evento de visita no site.</small>}{verifyState==='success'&&<p className="reports-success">Evento recebido.</p>}</article><article className="reports-panel reports-span-two"><div className="reports-panel-head"><h3>URL exclusiva de cada fluxo</h3><span>{flow.flows.length} códigos CF</span></div>{flow.flows.map(item=><div className="reports-tag-card" key={item.id}><div className="reports-tag-toggle"><span><strong>{item.flow_code} · {item.name}</strong><small>{item.allowed_host} · {item.status}</small></span><button type="button" onClick={()=>copy(snippet(item))}>Copiar código</button></div><code>{snippet(item)}</code></div>)}<small>Funnel Flow, Super Tag e Google Ads usam serviços e credenciais separados.</small></article></section>
    </>:<section className="reports-panel"><Empty message="Crie um fluxo ou selecione um existente na área Criar."/></section>)}
    {flowView==='monitor'&&(selectedFlow?<>
      <div className="reports-flow-topbar reports-monitor-toolbar"><div><h3>Jornada do site institucional</h3><p>Páginas visitadas, tempo ativo e avanço para formulário ou conversão · {selectedFlow?.flow_code} · {selectedFlow?.allowed_host}. Investimento e entrega de mídia ficam em Monitor.</p></div><select aria-label="Site monitorado" value={selectedFlowId} onChange={event=>chooseFlow(event.target.value)}>{flow.flows.map(item=><option key={item.id} value={item.id}>{item.flow_code} · {item.name}</option>)}</select></div>
      <article className="reports-panel reports-page-monitor"><div className="reports-panel-head"><div><h3>Disponibilidade das páginas</h3><p>Verificações HTTP/HTTPS feitas pelo servidor Python nas páginas configuradas neste fluxo.</p></div><span className={`reports-monitor-status is-${selectedFlow.monitor_status||'unknown'}`}><i/>{{online:'Online',degraded:'Com falhas',offline:'Offline',checking:'Verificando',unknown:'Sem checagem'}[selectedFlow.monitor_status||'unknown']}</span></div><div className="reports-monitor-controls"><label>Verificar a cada<select value={monitorInterval} disabled={busy||data.client.role==='viewer'} onChange={event=>setMonitorInterval(Number(event.target.value))}><option value={5}>5 minutos</option><option value={15}>15 minutos</option><option value={30}>30 minutos</option><option value={60}>1 hora</option></select></label><span>{selectedFlow.monitor_checked_at?`Última verificação: ${shortDate(selectedFlow.monitor_checked_at)}`:'Ainda não verificado'}</span><div><button type="button" disabled={busy||selectedFlow.status!=='published'||data.client.role==='viewer'} onClick={checkMonitorNow}>Verificar agora</button><button type="button" className={selectedFlow.monitor_enabled?'reports-monitor-enabled':''} disabled={busy||selectedFlow.status!=='published'||data.client.role==='viewer'} onClick={()=>configureMonitor(!selectedFlow.monitor_enabled)}>{selectedFlow.monitor_enabled?'Desativar monitoramento':'Ativar monitoramento'}</button></div></div>{selectedFlow.status!=='published'&&<p className="reports-info">Publique o fluxo para ativar verificações automáticas.</p>}{flow.monitor_checks?.length?<div className="reports-monitor-pages">{flow.monitor_checks[0].pages.map((page,index)=><div className="reports-monitor-page" key={`${page.host}:${page.path}:${index}`}><span className={`reports-monitor-dot is-${page.status}`}/><strong>{page.label}</strong><small>{page.host}{page.path}</small><b>{page.http_status||'—'}</b><em>{page.detail}</em></div>)}</div>:<Empty message="Execute uma verificação para registrar a disponibilidade das páginas deste fluxo."/>}<small className="reports-monitor-note">O monitor valida resposta HTTP e redirecionamentos dentro do domínio permitido. Capturas de tela e comparação visual ficam para uma etapa futura.</small></article>
      {flow.monitor_checks?.length>1&&<article className="reports-panel reports-monitor-history"><div className="reports-panel-head"><h3>Verificações recentes</h3><span>Últimas {flow.monitor_checks.length}</span></div>{flow.monitor_checks.slice(0,8).map(check=><div className="reports-monitor-history-row" key={check.id}><span className={`reports-monitor-status is-${check.status}`}><i/>{({online:'Online',degraded:'Com falhas',offline:'Offline'})[check.status]||check.status}</span><small>{shortDate(check.checked_at)}</small><small>{check.duration_ms} ms</small><small>{check.pages.filter(page=>page.status==='online').length}/{check.pages.length} páginas disponíveis</small></div>)}</article>}
      <section className="reports-grid reports-grid--four"><Kpi label="Sessões ativas" value={integer(flow.online)} detail="Atividade nos últimos 90 s"/><Kpi label="Visitas às páginas" value={integer(flow.activity.reduce((sum,item)=>sum+Number(item.views||0),0))} detail={`Últimos ${flow.period_days||30} dias`}/><Kpi label="Conversões no site" value={integer(flow.conversions)} detail="Eventos observados pela tag"/><Kpi label="Tempo ativo médio" value={flow.event_summary?.avg_active_seconds==null?'—':`${decimal(flow.event_summary.avg_active_seconds)} s`} detail={`${integer(flow.event_summary?.page_leave_count||0)} saídas medidas`}/></section>
      {monitorCanvasNodes.length>0&&<article className="reports-panel reports-span-three"><div className="reports-panel-head"><div><h3>Desenho do fluxo</h3><p>Sessões que passaram por cada bloco e avanço pelas conexões salvas · período selecionado.</p></div><span>{monitorCanvasNodes.length} blocos</span></div><div className="reports-flow-monitor-scroll"><div className="reports-flow-monitor-canvas" style={{width:monitorCanvasWidth,height:monitorCanvasHeight}}><svg aria-hidden="true" width={monitorCanvasWidth} height={monitorCanvasHeight}>{(flow.canvas_edges||[]).map((edge,index)=>{const from=monitorCanvasById[String(edge.from)],to=monitorCanvasById[String(edge.to)];return from&&to?<line key={`${edge.from}:${edge.to}:${index}`} x1={from.x+172} y1={from.y+53} x2={to.x} y2={to.y+53} markerEnd="url(#reports-monitor-arrow)"/>:null;})}<defs><marker id="reports-monitor-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#3285e7"/></marker></defs></svg>{monitorCanvasNodes.map(node=><article className={`reports-flow-monitor-node${node.type==='conversion'?' is-conversion':node.type==='error'?' is-error':''}`} key={node.id} style={{left:node.x,top:node.y}}><small>{node.type==='conversion'?'Conversão':node.type==='error'?'Página de erro':node.type==='form'?'Formulário':node.type==='event'?'Evento':node.type==='whatsapp'?'WhatsApp':'Página'}</small><strong>{node.title}</strong><span>{node.path||'—'}{node.event_name?` · ${node.event_name}`:''}</span><b>{integer(node.reached)} sessões</b><em>{integer(node.progressed)} avançaram pelas conexões</em></article>)}</div></div></article>}
      <section className="reports-grid reports-grid--three"><article className="reports-panel reports-span-three"><div className="reports-panel-head"><div><h3>Páginas que receberam tráfego</h3><p>Período selecionado · ordenadas por visitas; destaque automático de entradas, formulários, conversões e erros.</p></div><span>{integer((flow.site_pages||[]).length)} páginas</span></div>{flow.site_pages?.length?<div className="reports-table-wrap"><table><thead><tr><th>Página</th><th>Classificação</th><th>Visitas / sessões</th><th>Tempo ativo médio</th><th>Enviaram formulário</th><th>Chegaram à conversão</th><th>Origem</th></tr></thead><tbody>{flow.site_pages.slice(0,50).map(page=>{const kinds=[page.entry_sessions>0?'Entrada':null,page.is_form_page?'Formulário':null,page.is_conversion_page?'Conversão':null,page.is_error_page||Number(page.error_views)>0?'Erro':null].filter(Boolean);return <tr key={`${page.page_host}:${page.page_path}`}><td><strong>{page.page_path}</strong><small>{page.page_host}</small></td><td>{kinds.length?kinds.map(kind=><span key={kind} className={`reports-page-kind is-${kind==='Erro'?'error':kind==='Conversão'?'conversion':kind==='Formulário'?'form':'entry'}`}>{kind}</span>):'Página visitada'}{Number(page.error_views)>0&&<small>{integer(page.error_views)} ocorrências de erro</small>}</td><td>{integer(page.views)} · {integer(page.sessions)}</td><td>{Number(page.measured_visits)>0?`${decimal(page.avg_seconds)} s`:'Aguardando saídas medidas'}<small>{integer(page.measured_visits)} visitas medidas</small></td><td>{integer(page.sessions_to_form)} sessões</td><td>{integer(page.sessions_to_conversion)} sessões</td><td>{(page.sources||[]).slice(0,3).join(' · ')||'Direto / sem UTM'}</td></tr>;})}</tbody></table></div>:<Empty message="Ainda não há visitas no período. A tag passa a preencher esta tabela depois da instalação."/>}</article></section>
      <section className="reports-grid reports-grid--three"><article className="reports-panel reports-span-two"><div className="reports-panel-head"><h3>Rotas entre páginas</h3><span>Sequência observada na sessão</span></div>{flow.page_transitions?.length?<div className="reports-table-wrap"><table><thead><tr><th>De</th><th>Para</th><th>Sessões</th><th>Destino</th></tr></thead><tbody>{flow.page_transitions.slice(0,20).map((route,index)=>{const next=(flow.site_pages||[]).find(page=>page.page_host===route.next_host&&page.page_path===route.next_path);return <tr key={`${route.page_host}:${route.page_path}:${route.next_host}:${route.next_path}:${index}`}><td>{route.page_path}<small>{route.page_host}</small></td><td>{route.next_path}<small>{route.next_host}</small></td><td>{integer(route.sessions)}</td><td>{next?.is_conversion_page?'Conversão':next?.is_form_page?'Formulário':next?.is_error_page?'Erro':'Continuação'}</td></tr>;})}</tbody></table></div>:<Empty message="As rotas entre páginas aparecem quando uma sessão visita mais de uma URL com a tag."/>}</article><article className="reports-panel"><div className="reports-panel-head"><h3>Entrada e páginas-chave</h3><span>Escolhidas pelo usuário</span></div>{flow.steps.filter(step=>step.is_entry||['form','conversion','error'].includes(step.step_kind)).length?<div className="reports-origin-list">{flow.steps.filter(step=>step.is_entry||['form','conversion','error'].includes(step.step_kind)).map(step=><div className="reports-origin-row" key={step.id}><span className={`reports-page-kind is-${step.step_kind==='conversion'?'conversion':step.step_kind==='error'?'error':step.step_kind==='form'?'form':'entry'}`}>{step.is_entry?'Entrada':{form:'Formulário',conversion:'Conversão',error:'Erro'}[step.step_kind]||'Página-chave'}<small>{step.name} · {step.page_host||selectedFlow.allowed_host}{step.path_prefix}</small></span><b>{integer(step.reached)}</b></div>)}</div>:<Empty message="No editor, marque páginas de entrada, formulário, conversão ou erro para destacá-las."/>}</article></section>
      <section className="reports-grid reports-grid--three"><article className="reports-panel reports-span-two"><div className="reports-panel-head"><h3>Etapas mapeadas no site</h3><span>{flow.steps.length} etapas · {flow.period_days||30} dias</span></div>{flow.steps.length?flow.tags.map(tag=>{const stages=flow.steps.filter(step=>step.tag_id===tag.id);return stages.length?<div className="reports-flow-group" key={tag.id}><strong>{tag.label}</strong><div className="reports-flow-rail">{stages.map((step,index)=>{const prev=stages[index-1];const rate=prev?.reached?Math.round(Number(step.progressed)/Number(prev.reached)*100):null;return <article className={`reports-flow-node${step.step_kind==='conversion'?' is-conversion':''}`} key={step.id}><small>{step.is_entry?'Entrada':step.step_kind==='conversion'?'Conversão':step.step_kind==='error'?'Erro':`Etapa ${index+1}`}</small><strong>{step.name}</strong><span>{step.page_host?`${step.page_host} · `:''}{step.path_prefix}</span>{step.campaign_name&&<small>Campanha: {step.campaign_name}</small>}<b>{integer(step.reached)} sessões</b><em>{index?`${integer(step.progressed)} avançaram${rate===null?'':` · ${rate}%`}`:'Ponto inicial'}</em></article>;})}</div></div>:null;}):<Empty message="Ainda não há etapas mapeadas. Abra Editar para conectar páginas e conversões."/>}</article>
        <article className="reports-panel"><div className="reports-panel-head"><h3>Origens de mercado</h3><span>UTM / referrer</span></div><div className="reports-origin-list">{channelOrigins.map(({channel,total,sources})=><div className="reports-origin-row" key={channel.id}><FlowPlatformLogo platform={channel.id}/><span>{channel.label}<small>{sources.slice(0,2).join(' · ')||'Sem origem observada'}</small></span><b>{integer(total)}</b></div>)}</div></article></section>
      <section className="reports-grid reports-grid--three"><article className="reports-panel"><div className="reports-panel-head"><h3>Conversões confirmadas</h3><a className="reports-inline-link" href="#monitor">Integrações ↗</a></div><p>Página de conversão é observada pela tag; confirmação de lead, qualificação e venda vem do CRM.</p><div className="reports-confirmed-grid">{[['lead','Leads'],['qualified_lead','Qualificados'],['sale','Vendas']].map(([kind,label])=><Kpi key={kind} label={label} value={integer(flow.confirmed.find(item=>item.conversion_kind===kind)?.total)} detail={`${flow.period_days||30} dias · CRM`}/>)}</div></article><article className="reports-panel reports-span-two"><div className="reports-panel-head"><h3>Páginas e atividade</h3><button className="reports-text-button" type="button" onClick={()=>reload().catch(failure=>setLocalError(failure.message))}>Atualizar</button></div>{flow.activity.length?<div className="reports-table-wrap"><table><thead><tr><th>Página</th><th>Visitas</th><th>Visitantes</th><th>Online</th><th>Formulários</th><th>Cliques</th><th>Conversões</th></tr></thead><tbody>{flow.activity.map(item=><tr key={`${item.tag_id}:${item.page_path}`}><td>{item.page_path}</td><td>{integer(item.views)}</td><td>{integer(item.visitors)}</td><td>{integer(item.online)}</td><td>{integer(item.form_submissions)}</td><td>{integer(item.clicks)}</td><td>{integer(item.conversions)}</td></tr>)}</tbody></table></div>:<Empty message="As páginas visitadas aparecerão após a instalação do snippet."/>}</article></section>
    </>:<section className="reports-panel"><Empty message="Selecione um fluxo para acompanhar o funil."/></section>)}
    {simulation&&<p className="reports-success">Teste fictício: {simulation.events.length} eventos · {simulation.flow_code}. Nenhum evento real foi enviado.</p>}
    {copyState&&<p className="reports-info" role="status">{copyState}</p>}
  </>;
}

function SuperTag({data}) {
  const [sites, setSites] = useState([]);
  const [selectedId, setSelectedId] = useState('');
  const [detail, setDetail] = useState(null);
  const [label, setLabel] = useState('Site principal');
  const [host, setHost] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [installOpen, setInstallOpen] = useState(false);
  const load = async () => {
    const value = await json(`/connect/api/v1/reports/supertag/sites?client_id=${data.client.client_id}`);
    setSites(value.sites || []);
    if (selectedId && value.sites.some(item => item.id === selectedId)) return;
    const first = value.sites?.find(item => !item.revoked_at);
    setSelectedId(first?.id || '');
  };
  useEffect(() => {load().catch(failure => setError(failure.message));}, [data.client.client_id]);
  useEffect(() => {
    if (!selectedId) {setDetail(null); return;}
    json(`/connect/api/v1/reports/supertag/sites/${selectedId}/events?client_id=${data.client.client_id}`)
      .then(setDetail).catch(failure => setError(failure.message));
  }, [selectedId, data.client.client_id]);
  const create = async event => {
    event.preventDefault(); setBusy(true); setError(''); setNotice('');
    try {
      const result = await json(`/connect/api/v1/reports/supertag/sites?client_id=${data.client.client_id}`, {
        method:'POST', headers:{'Content-Type':'application/json','X-CSRF-Token':data.csrf},
        body:JSON.stringify({label,allowed_host:host,consent_mode:'auto'})});
      await load(); setSelectedId(result.site.id); setHost(''); setInstallOpen(false); setNotice('Instalação Super Tag criada.');
    } catch (failure) {setError(failure.message);} finally {setBusy(false);}
  };
  const update = async changes => {
    if (!selectedId) return;
    setBusy(true); setError('');
    try {
      await json(`/connect/api/v1/reports/supertag/sites/${selectedId}?client_id=${data.client.client_id}`, {
        method:'PATCH', headers:{'Content-Type':'application/json','X-CSRF-Token':data.csrf}, body:JSON.stringify(changes)});
      await load();
      const latest = await json(`/connect/api/v1/reports/supertag/sites/${selectedId}/events?client_id=${data.client.client_id}`);
      setDetail(latest);
    } catch (failure) {setError(failure.message);} finally {setBusy(false);}
  };
  const revoke = async () => {
    if (!selectedId || !window.confirm('Revogar a Super Tag deste domínio? A coleta será interrompida.')) return;
    setBusy(true); setError('');
    try {
      await json(`/connect/api/v1/reports/supertag/sites/${selectedId}/revoke?client_id=${data.client.client_id}`, {
        method:'POST', headers:{'X-CSRF-Token':data.csrf}, body:JSON.stringify({})});
      setSelectedId(''); setDetail(null); await load();
    } catch (failure) {setError(failure.message);} finally {setBusy(false);}
  };
  const selected = sites.find(item => item.id === selectedId);
  const copy = async value => {
    try {await navigator.clipboard.writeText(value); setNotice('Copiado.');}
    catch (_) {setNotice('Não foi possível copiar automaticamente. Selecione o código e copie.');}
  };
  const kindTotal = kind => Number((detail?.summary || []).find(item => item.event_kind === kind)?.total || 0);
  return <section className="reports-grid reports-grid--three reports-supertag">
    <article className="reports-panel reports-span-three"><div className="reports-panel-head"><div><h2>Super Tag</h2><p>Instalações e coleta de atividade consentida</p></div>{data.client.role !== 'viewer' && <button className="reports-primary-button" type="button" onClick={()=>setInstallOpen(true)}>Nova instalação</button>}</div>
      {error && <p className="reports-error" role="alert">{error}</p>}{notice && <p className="reports-success" role="status">{notice}</p>}
      {sites.length ? <div className="reports-supertag-list">{sites.map(site=><button type="button" key={site.id} className={`reports-supertag-item${selectedId===site.id?' is-selected':''}`} onClick={()=>setSelectedId(site.id)}><strong>{site.label}</strong><span>{site.allowed_host}</span><small>{site.revoked_at?'Revogada':site.enabled?'Ativa':'Desativada'}</small></button>)}</div> : <Empty message="Nenhuma instalação criada para este cliente."/>}
    </article>
    <article className="reports-panel reports-span-three"><div className="reports-panel-head"><h2>{selected?.label || 'Instalação selecionada'}</h2>{selected && <span>{selected.allowed_host}</span>}</div>
      {selected ? <>
        <div className="reports-tag-card"><div className="reports-tag-card-head"><strong>Código de instalação</strong><button type="button" onClick={()=>copy(selected.snippet)}>Copiar snippet</button></div><code>{selected.snippet}</code><small>Adicione este código ao site autorizado. O código não inclui credenciais secretas.</small></div>
        <div className="reports-supertag-settings"><label>Duração do identificador<select disabled={busy || data.client.role==='viewer'} value={selected.config?.audience_days || 90} onChange={event=>update({audience_days:Number(event.target.value)})}>{[30,60,90,180,365].map(days=><option key={days} value={days}>{days} dias</option>)}</select></label>
          <label>Retenção dos eventos<select disabled={busy || data.client.role==='viewer'} value={selected.config?.retention_days || 90} onChange={event=>update({retention_days:Number(event.target.value)})}>{[30,60,90,180,365].map(days=><option key={days} value={days}>{days} dias</option>)}</select></label>
          <label>Consentimento<select disabled={busy || data.client.role==='viewer'} value={selected.config?.consent_mode || 'auto'} onChange={event=>update({consent_mode:event.target.value})}><option value="auto">Detectar CMP; usar aviso Cadu se necessário</option><option value="manual">CMP integrada manualmente</option></select></label>
          <label className="reports-checkbox"><input type="checkbox" disabled={busy || data.client.role==='viewer'} checked={selected.config?.visibility_enabled !== false} onChange={event=>update({visibility_enabled:event.target.checked})} />Medir visibilidade em elementos marcados</label></div>
        {data.client.role!=='viewer' && !selected.revoked_at && <button type="button" className="reports-danger-button" disabled={busy} onClick={revoke}>Revogar instalação</button>}
      </> : <Empty message="Selecione uma instalação para ver seu código e as configurações."/>}
    </article>
    {installOpen && <div className="reports-modal-backdrop" role="presentation" onMouseDown={event=>{if(event.target===event.currentTarget)setInstallOpen(false);}}><section className="reports-modal" role="dialog" aria-modal="true" aria-labelledby="reports-install-title"><div className="reports-panel-head"><div><h2 id="reports-install-title">Nova instalação da Super Tag</h2><p>Informe o site que poderá enviar eventos.</p></div><button type="button" className="reports-modal-close" aria-label="Fechar" onClick={()=>setInstallOpen(false)}>×</button></div>
      <form className="reports-form" onSubmit={create}><label>Nome do site<input required maxLength="120" value={label} onChange={event=>setLabel(event.target.value)} placeholder="Site principal" /></label><label>Domínio permitido<input required value={host} onChange={event=>setHost(event.target.value)} placeholder="www.exemplo.com.br" /></label><p className="reports-info">O consentimento pode vir de uma CMP compatível ou do aviso da Cadu. A instalação não começa a coletar antes da escolha de analytics.</p>{error && <p className="reports-error" role="alert">{error}</p>}<div className="reports-modal-actions"><button type="button" onClick={()=>setInstallOpen(false)}>Cancelar</button><button className="reports-primary-button" disabled={busy}>{busy?'Criando…':'Criar instalação'}</button></div></form>
    </section></div>}
    {detail && <>
      <Kpi label="Eventos · 30 dias" value={integer(detail.site.events_30d)} detail="Eventos aceitos pelo coletor" />
      <Kpi label="Páginas vistas" value={integer(kindTotal('page_view'))} detail="Após consentimento" />
      <Kpi label="Formulários" value={integer(kindTotal('form_submit'))} detail="Sem capturar os valores enviados" />
      <Kpi label="Conversões" value={integer(kindTotal('conversion'))} detail="Marcadas via trackConversion" />
      <article className="reports-panel reports-span-three"><div className="reports-panel-head"><h2>Atividade por página</h2><span>Últimos 30 dias · caminhos sem query string</span></div>
        {detail.pages?.length ? <div className="reports-table-wrap"><table><thead><tr><th>Página</th><th>Visitas</th><th>Formulários</th><th>Cliques</th><th>Conversões</th><th>Visibilidade</th><th>Rolagem</th></tr></thead><tbody>{detail.pages.map(item=><tr key={item.page_path}><td>{item.page_path}</td><td>{integer(item.views)}</td><td>{integer(item.form_submissions)}</td><td>{integer(item.clicks)}</td><td>{integer(item.conversions)}</td><td>{integer(item.visibility_events)}</td><td>{integer(item.scroll_events)}</td></tr>)}</tbody></table></div> : <Empty message="Os eventos aparecem depois de consentimento e da primeira visita." />}
      </article>
      <article className="reports-panel reports-span-three"><div className="reports-panel-head"><h2>Dados para mapas de interação</h2><span>{detail.heatmap?.length || 0} células agregadas</span></div><p>Cliques são agrupados em uma grade normalizada de 5% do viewport. Para mapas de visibilidade, marque os elementos com <code>data-cadu-track data-cadu-element="hero_cta"</code>. O código não lê texto nem valores de formulário.</p>
        {detail.heatmap?.length ? <div className="reports-table-wrap"><table><thead><tr><th>Tipo</th><th>Elemento</th><th>Grade normalizada</th><th>Ocorrências</th></tr></thead><tbody>{detail.heatmap.slice(0,30).map((item,index)=><tr key={`${item.event_kind}:${item.element_id}:${index}`}><td>{item.event_kind}</td><td>{item.element_id || '—'}</td><td>{item.x != null ? `${(Number(item.x)/10).toFixed(1)}–${Math.min(100,(Number(item.x)+49)/10).toFixed(1)}% × ${(Number(item.y)/10).toFixed(1)}–${Math.min(100,(Number(item.y)+49)/10).toFixed(1)}%` : item.ratio != null ? `${item.ratio}% visível` : item.depth != null ? `${item.depth}% rolagem` : '—'}</td><td>{integer(item.total)}</td></tr>)}</tbody></table></div> : <Empty message="Os agregados de cliques e visibilidade aparecerão com o tráfego consentido." />}
      </article>
    </>}
  </section>;
}

function Events({data, filters, initialKind = 'all'}) {
  const [result, setResult] = useState({events: [], event_summary: {}});
  const [query, setQuery] = useState('');
  const [kindFilter, setKindFilter] = useState(initialKind);
  useEffect(() => setKindFilter(initialKind), [initialKind]);
  const [sourceFilter, setSourceFilter] = useState('all');
  const [newEventName, setNewEventName] = useState('');
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState('');
  const requestVersion = useRef(0);
  const loadEvents = () => {
    const currentRequest = ++requestVersion.current;
    const params = new URLSearchParams({client_id: String(data.client.client_id), days: filters.period, start_date: filters.startDate, end_date: filters.endDate});
    if (filters.platform) params.set('platform', filters.platform);
    if (filters.account) params.set('account_id', filters.account);
    if (filters.campaign) params.set('campaign_id', filters.campaign);
    json(`/connect/api/v1/reports/flow?${params}`).then(value => {
      if (currentRequest === requestVersion.current) {setResult(value); setError('');}
    }).catch(failure => {if (currentRequest === requestVersion.current) setError(failure.message);});
  };
  useEffect(() => {
    loadEvents();
    return () => {requestVersion.current += 1;};
  }, [data.client.client_id, filters.period, filters.startDate, filters.endDate, filters.platform, filters.account, filters.campaign]);
  const allEvents = result.events || [];
  const sources = [...new Set(allEvents.map(item => item.source_label))];
  const visible = allEvents.filter(item => {
    const term = query.trim().toLowerCase();
    const searchMatch = !term || `${item.event_name} ${item.page_path} ${item.source_label}`.toLowerCase().includes(term);
    const typeMatch = kindFilter === 'all' || (kindFilter === 'custom' ? item.event_kind === 'custom_event' : kindFilter === 'conversion' ? item.event_kind === 'conversion' : item.event_kind !== 'custom_event' && item.event_kind !== 'conversion');
    return searchMatch && typeMatch && (sourceFilter === 'all' || item.source_label === sourceFilter);
  });
  const summary = result.event_summary || {};
  const health = summary.total ? Math.round(Number(summary.attributed || 0) / Number(summary.total) * 100) : 0;
  const normalizedEventName = newEventName.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim().replace(/[\s-]+/g, '_').replace(/[^a-z0-9_]/g, '').replace(/^[^a-z]+/, '').slice(0, 80) || 'lead_qualified';
  const customSnippet = `window.CaduFlow && window.CaduFlow.trackEvent('${normalizedEventName}');`;
  const copyEvent = async () => {try {await navigator.clipboard.writeText(customSnippet);setCopied(true);window.setTimeout(()=>setCopied(false),1800);} catch (_) {setError('Não foi possível copiar o código.');}};
  const timeAgo = value => {const minutes = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 60000)); return minutes < 60 ? `há ${minutes} min` : minutes < 1440 ? `há ${Math.floor(minutes / 60)} h` : `há ${Math.floor(minutes / 1440)} d`;};
  return <>
    <section className="reports-events-layout"><article className="reports-panel reports-events-main"><div className="reports-panel-head"><div><h2>Eventos</h2><p>Veja as interações recebidas pela tag do Funnel Flow e prepare eventos personalizados.</p></div><a className="reports-inline-link" href="#flow">Abrir Funnel Flow ↗</a></div>
      <div className="reports-event-tabs"><button className={kindFilter==='all'?'is-active':''} onClick={()=>setKindFilter('all')}>Todos os eventos</button><button className={kindFilter==='standard'?'is-active':''} onClick={()=>setKindFilter('standard')}>Padrão</button><button className={kindFilter==='custom'?'is-active':''} onClick={()=>setKindFilter('custom')}>Personalizados</button><button className={kindFilter==='conversion'?'is-active':''} onClick={()=>setKindFilter('conversion')}>Conversões</button></div>
      <div className="reports-event-filters"><input type="search" aria-label="Buscar eventos" placeholder="Buscar evento ou página…" value={query} onChange={event=>setQuery(event.target.value)}/><select aria-label="Filtrar fonte" value={sourceFilter} onChange={event=>setSourceFilter(event.target.value)}><option value="all">Todas as fontes</option>{sources.map(source=><option key={source}>{source}</option>)}</select><button type="button" onClick={loadEvents}>↻ Atualizar</button></div>
      {error&&<div className="reports-error" role="alert">{error}</div>}
      <div className="reports-table-wrap"><table className="reports-events-table"><thead><tr><th>Evento</th><th>Tipo</th><th>Fonte / Página</th><th>Última ocorrência</th><th>Mapeamento</th></tr></thead><tbody>{visible.map((item,index)=><tr key={`${item.event_kind}:${item.event_name}:${item.page_path}:${item.source_label}:${index}`}><td><span className="reports-event-icon">{item.event_kind==='conversion'?'✓':item.event_kind==='form_submit'?'▤':item.event_kind==='whatsapp_click'?'◉':item.event_kind==='custom_event'?'✳':'⌖'}</span><span><strong>{item.event_name}</strong><small>{item.page_path}</small></span></td><td><span className={`reports-event-type ${item.event_kind==='custom_event'?'is-custom':item.event_kind==='conversion'?'is-conversion':''}`}>{item.event_kind==='custom_event'?'Personalizado':item.event_kind==='conversion'?'Conversão':'Automático'}</span></td><td>{item.source_label}<small>{item.total} ocorrências · {item.page_path}</small></td><td>{timeAgo(item.last_occurred_at)}<small>{shortDate(item.last_occurred_at)}</small></td><td><span className={`reports-event-status ${Number(item.mapped)>0?'is-mapped':''}`}><i/>{Number(item.mapped)>0?'URL mapeada':'Sem etapa'}</span></td></tr>)}</tbody></table>{!visible.length&&<Empty message="Nenhum evento corresponde aos filtros. A atividade aparecerá quando a tag enviar eventos." />}</div>
      <div className="reports-events-foot">Mostrando {visible.length} de {integer(result.event_group_count ?? allEvents.length)} combinações de evento, página e origem · {shortDate(filters.startDate)} – {shortDate(filters.endDate)}{Number(result.event_group_count)>allEvents.length?' · exibindo as 300 mais recentes':''}</div>
    </article><aside className="reports-events-side"><article className="reports-panel"><div className="reports-panel-head"><h2>Resumo de eventos</h2><span>{shortDate(filters.startDate)} – {shortDate(filters.endDate)}</span></div><div className="reports-event-kpis"><Kpi label="Ocorrências" value={integer(summary.total)} detail="No intervalo selecionado"/><Kpi label="Envios de formulário" value={integer(summary.form_submissions)} detail="Sem registrar valores enviados"/><Kpi label="Conversões" value={integer(summary.conversions)} detail="Páginas de conversão mapeadas"/><Kpi label="Origem identificada" value={`${health}%`} detail="UTM ou domínio de referência"/></div><p className="reports-event-health">{health>=80?'Boa atribuição das origens':health?'Algumas visitas não têm UTM ou referência':'Aguardando os primeiros eventos'}</p></article>
      <article className="reports-panel"><div className="reports-panel-head"><h2>Adicionar evento personalizado</h2><span>Usa a tag de Fluxos</span></div><p>Gere uma chamada para marcar ações específicas do site, como lead qualificado ou início de checkout.</p><label className="reports-event-name">Nome do evento<input value={newEventName} onChange={event=>setNewEventName(event.target.value)} maxLength={120} placeholder="lead_qualified"/></label><code className="reports-event-snippet">{customSnippet}</code><button className="reports-event-copy" type="button" onClick={copyEvent}>{copied?'Copiado':'Copiar código'}</button><small>Publique um fluxo no Funnel Flow antes de instalar a tag. Chame este código no momento da ação; use um identificador genérico, sem nome, e-mail, telefone ou outros dados pessoais.</small></article>
      <article className="reports-panel reports-event-help"><h2>Melhores resultados</h2><p>Use nomes consistentes e marque a URL de obrigado como conversão no Funnel Flow. Cliques de WhatsApp são detectados automaticamente por links wa.me e api.whatsapp.com.</p><a className="reports-inline-link" href="#flow">Configurar páginas e conversões ↗</a></article></aside></section>
  </>;
}

function VisualConfirm({detail, data, busy, setBusy, setError, onRefresh}) {
  const [active, setActive] = useState(null);
  const [draft, setDraft] = useState({});
  const [createCampaign, setCreateCampaign] = useState(false);
  const [campaignMatch, setCampaignMatch] = useState(null);
  const scopes = detail.visual?.result?.scopes || [];
  const begin = (scope, index) => {
    const metricValues = {};
    const aliases = {impressions:'impressions', impressoes:'impressions', clicks:'clicks', cliques:'clicks',
      cost:'cost', spend:'cost', gasto:'cost', custo:'cost', conversions:'conversions', conversoes:'conversions',
      'conversion value':'conversion_value', 'valor de conversao':'conversion_value'};
    for (const metric of scope.metrics || []) {
      const label = metric.label.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').trim();
      const key = aliases[label];
      if (key) metricValues[key] = metric.raw_value;
    }
    setDraft({platform:scope.platform || '', external_account_id:scope.account_id || '',
      account_name:scope.account_name || '', external_campaign_id:scope.campaign_id || '',
      campaign_name:scope.campaign_name || '', metric_date:scope.period_start || '',
      period_start:scope.period_start || '', period_end:scope.period_end || '',
      currency:scope.currency || '', impressions:'', clicks:'', cost:'', conversions:'',
      conversion_value:'', ...metricValues, note:''});
    setCreateCampaign(false);
    setActive(index);
    setCampaignMatch(null);
  };
  useEffect(() => {
    let live = true;
    if (active === null || !draft.platform || !draft.external_account_id || !draft.external_campaign_id) {
      setCampaignMatch(null);
      return () => {live = false;};
    }
    const params = new URLSearchParams({client_id: String(data.client.client_id), platform: draft.platform,
      account_id: draft.external_account_id, campaign_id: draft.external_campaign_id});
    fetch(`/connect/api/v1/reports/imports/${detail.import_file.id}/campaign-match?${params}`, {credentials:'same-origin'})
      .then(response => response.ok ? response.json() : Promise.reject(new Error('Falha ao verificar campanha')))
      .then(value => {if (live) setCampaignMatch(value.match);})
      .catch(() => {if (live) setCampaignMatch({state:'unmatched'});});
    return () => {live = false;};
  }, [active, draft.platform, draft.external_account_id, draft.external_campaign_id, data.client.client_id]);
  const confirm = async (event, daily) => {
    event.preventDefault(); setBusy(true); setError('');
    try {
      const {metric_date, period_start, period_end, ...shared} = draft;
      const payload = daily ? {...shared, metric_date, create_campaign:createCampaign} : {...shared, period_start, period_end, create_campaign:createCampaign};
      const action = daily ? 'confirm' : 'range';
      await json(`/connect/api/v1/reports/imports/${detail.import_file.id}/visual/${active}/${action}?client_id=${data.client.client_id}`,
        {method:'POST', headers:{'Content-Type':'application/json', 'X-CSRF-Token':data.csrf}, body:JSON.stringify(payload)});
      setActive(null); await onRefresh();
    } catch (failure) {setError(failure.message);} finally {setBusy(false);}
  };
  const baseFields = [['platform','Plataforma'], ['external_account_id','ID da conta'],
    ['account_name','Nome da conta'], ['external_campaign_id','ID da campanha'],
    ['campaign_name','Nome da campanha']];
  const metricFields = [['currency','Moeda'], ['impressions','Impressões'], ['clicks','Cliques'],
    ['cost','Custo'], ['conversions','Conversões'], ['conversion_value','Valor das conversões']];
  return <article className="reports-panel reports-span-three">
    <div className="reports-panel-head"><h2>Conferir print</h2><span>Imagem original normalizada</span></div>
    <img className="reports-import-image" src={`/connect/api/v1/reports/imports/${detail.import_file.id}/image?client_id=${data.client.client_id}`} alt={`Print enviado: ${detail.import_file.original_name}`} />
    {scopes.map((scope, index) => {
      const daily = scope.granularity === 'day' && scope.period_start && scope.period_start === scope.period_end;
      const range = scope.granularity === 'range' || Boolean(scope.period_start && scope.period_end && scope.period_start !== scope.period_end);
      const dailyConfirmed = detail.rows.some(row => row.sheet_name === 'Print' && row.source_row === index + 1);
      const snapshot = (detail.range_snapshots || []).find(item => item.scope_index === index);
      const fields = [...baseFields, ...(daily ? [['metric_date','Data ISO']] : [['period_start','Início ISO'],['period_end','Fim ISO']]), ...metricFields];
      return <div key={index} className="reports-suggestion">
        <strong>Bloco {index + 1} · {scope.campaign_name || scope.campaign_id || 'Campanha sem identificação'}</strong>
        <p>A associação será conferida por plataforma, conta e ID da campanha antes de gravar.</p>
        {dailyConfirmed ? <p>Dia confirmado e incluído nas observações.</p> : snapshot ? <p>Intervalo confirmado: {shortDate(snapshot.period_start)} a {shortDate(snapshot.period_end)}. {snapshot.note}</p> : daily || range ? data.client.role !== 'viewer' && <button type="button" className="reports-text-button" onClick={() => begin(scope,index)}>{daily ? 'Conferir e confirmar dia' : 'Conferir total do intervalo'}</button> : <p>Período indefinido: mantenha como evidência até identificar as datas no print.</p>}
        {active === index && <form className="reports-form" onSubmit={event => confirm(event, daily)}>
          <div className="reports-form-pair">{fields.map(([key,label]) => <label key={key}>{label}<input value={draft[key] || ''} onChange={event => setDraft({...draft,[key]:event.target.value})} /></label>)}</div>
          {campaignMatch?.state === 'missing' && <div className="reports-suggestion"><strong>Campanha não encontrada</strong><p>Não localizamos {draft.campaign_name} na conta selecionada.</p><label className="reports-checkbox"><input type="checkbox" checked={createCampaign} onChange={event => setCreateCampaign(event.target.checked)} />Criar esta campanha e armazenar os dados do print</label></div>}
          {campaignMatch?.state === 'matched' && <p>Campanha encontrada: {campaignMatch.campaign_name} · {campaignMatch.account_name}</p>}
          {campaignMatch?.state === 'unmatched' && <p className="reports-error">{campaignMatch.reason || 'Complete plataforma, ID da conta e ID da campanha para validar a associação.'}</p>}
          <label>Justificativa<input required maxLength="1000" value={draft.note || ''} onChange={event => setDraft({...draft,note:event.target.value})} placeholder="Conferi os números, IDs e período no print" /></label>
          <button disabled={busy || !campaignMatch || campaignMatch?.state === 'unmatched' || (campaignMatch?.state === 'missing' && !createCampaign)}>Confirmar {daily ? 'dados do dia' : 'total do intervalo'}</button>
        </form>}
      </div>;
    })}
  </article>;
}

function ColumnMapping({detail, data, busy, setBusy, setError, onRefresh}) {
  const [mapping, setMapping] = useState({});
  const [suggestions, setSuggestions] = useState(detail.column_suggestions || null);
  const [platformHint, setPlatformHint] = useState(detail.import_file.platform_hint || '');
  const [currencyHint, setCurrencyHint] = useState('');
  const [dateOrder, setDateOrder] = useState('auto');
  const [note, setNote] = useState('');
  const fields = [['platform','Plataforma'],['account_id','ID da conta'],['account_name','Nome da conta'],
    ['campaign_id','ID da campanha'],['campaign_name','Nome da campanha'],['date','Data'],
    ['currency','Moeda'],['impressions','Impressões'],['clicks','Cliques'],['cost','Custo'],
    ['conversions','Conversões'],['conversion_value','Valor das conversões']];
  const suggest = async () => {
    setBusy(true); setError('');
    try {
      const value = await json(`/connect/api/v1/reports/imports/${detail.import_file.id}/suggest-columns?client_id=${data.client.client_id}`,
        {method:'POST', headers:{'X-CSRF-Token':data.csrf}});
      setSuggestions(value.suggestion);
    } catch (failure) {setError(failure.message);} finally {setBusy(false);}
  };
  const submit = async event => {
    event.preventDefault(); setBusy(true); setError('');
    try {
      const chosen = Object.fromEntries(Object.entries(mapping).filter(([,header]) => header));
      await json(`/connect/api/v1/reports/imports/${detail.import_file.id}/map-columns?client_id=${data.client.client_id}`,
        {method:'POST', headers:{'Content-Type':'application/json','X-CSRF-Token':data.csrf},
          body:JSON.stringify({mapping:chosen, platform_hint:platformHint, currency_hint:currencyHint,
            date_order:dateOrder, note})});
      await onRefresh();
    } catch (failure) {setError(failure.message);} finally {setBusy(false);}
  };
  return <article className="reports-panel reports-span-three"><div className="reports-panel-head"><h2>Mapear colunas do arquivo</h2><span>{detail.headers.length} cabeçalhos detectados</span></div>
    <p>Use quando o export tiver nomes de colunas que o Reports não reconheceu. O mapa será aplicado às linhas pendentes deste arquivo; o original fica preservado.</p>
    {data.client.role !== 'viewer' && detail.import_file.applied_count < detail.import_file.row_count && !suggestions && <button type="button" className="reports-text-button" disabled={busy} onClick={suggest}>Corrigir mapeamento com TypeSafe</button>}
    {suggestions && <div className="reports-suggestion"><strong>Correções TypeSafe sugeridas · confira antes de aplicar</strong><p>Concentração das alternativas, não uma garantia de acerto. O mapa só é aplicado após sua revisão e confirmação.</p>{suggestions.result.suggestions.length ? suggestions.result.suggestions.map((item,index) => <p key={`${item.header}:${index}`}>{item.header} → {fields.find(([key]) => key === item.field)?.[1] || 'Sem correspondência'} · concentração {Math.round(item.confidence * 100)}% {item.field !== 'none' && data.client.role !== 'viewer' && <button type="button" className="reports-text-button" onClick={() => setMapping({...mapping,[item.field]:item.header})}>Usar no formulário</button>}</p>) : <p>Nenhum cabeçalho desconhecido encontrado.</p>}{suggestions.result.omitted_count > 0 && <p>{suggestions.result.omitted_count} cabeçalhos ficaram fora da sugestão; mapeie manualmente.</p>}</div>}
    {data.client.role !== 'viewer' && detail.import_file.applied_count < detail.import_file.row_count && <form className="reports-form" onSubmit={submit}>
      <div className="reports-form-pair">{fields.map(([key,label]) => <label key={key}>{label}<select value={mapping[key] || ''} onChange={event => setMapping({...mapping,[key]:event.target.value})}><option value="">Usar leitura automática</option>{detail.headers.map(header => <option key={header} value={header}>{header}</option>)}</select></label>)}</div>
      <div className="reports-form-pair"><label>Plataforma do arquivo, se ausente<input value={platformHint} onChange={event => setPlatformHint(event.target.value)} placeholder="Ex.: Meta Ads" /></label><label>Moeda, se ausente<input maxLength="3" value={currencyHint} onChange={event => setCurrencyHint(event.target.value)} placeholder="BRL" /></label><label>Formato de data<select value={dateOrder} onChange={event => setDateOrder(event.target.value)}><option value="auto">Detectar</option><option value="dmy">Dia/mês/ano</option><option value="mdy">Mês/dia/ano</option></select></label></div>
      <label>Justificativa<input required maxLength="1000" value={note} onChange={event => setNote(event.target.value)} placeholder="Ex.: cabeçalhos do export conferidos" /></label><button disabled={busy}>Aplicar às linhas pendentes</button>
    </form>}
    {(detail.column_maps || []).map((item,index) => <p key={index}>{shortDate(item.created_at)} · {item.applied_rows} linhas reconhecidas · {item.note}</p>)}
  </article>;
}

function Imports({data, reloadBootstrap, focusLibrary = false}) {
  const [items, setItems] = useState([]);
  const [customMetrics, setCustomMetrics] = useState([]);
  const [rangeSnapshots, setRangeSnapshots] = useState([]);
  const [conflicts, setConflicts] = useState([]);
  const [choices, setChoices] = useState({});
  const [reasons, setReasons] = useState({});
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
  const refresh = async () => {const [body, pending, ranges] = await Promise.all([json(base), json(`/connect/api/v1/reports/import-conflicts?client_id=${data.client.client_id}`), json(`/connect/api/v1/reports/import-ranges?client_id=${data.client.client_id}`)]); setReady(body.ready); setItems(body.imports || []); setCustomMetrics(body.custom_metrics || ranges.custom_metrics || []); setConflicts(pending.conflicts || []); setRangeSnapshots(ranges.snapshots || []);};
  useEffect(() => {setDetail(null); setEditing(null); refresh().catch(failure => setError(failure.message));}, [data.client.client_id]);
  useEffect(() => {if (focusLibrary) document.getElementById('reports-data-library')?.scrollIntoView({behavior: 'smooth', block: 'start'});}, [focusLibrary, customMetrics.length]);
  const open = async id => {try {setDetail(await json(`/connect/api/v1/reports/imports/${id}?client_id=${data.client.client_id}`)); setError('');} catch (failure) {setError(failure.message);}};
  const edit = row => {setEditing(row.id); setDraft({...row.parsed, metric_date: row.parsed.metric_date || '', ...row.parsed.metrics, create_campaign:false, note: ''});};
  const resolve = async event => {
    event.preventDefault(); setBusy(true); setError('');
    try {
      const payload = Object.fromEntries(['platform','external_account_id','account_name','external_campaign_id','campaign_name','metric_date','currency','impressions','clicks','cost','conversions','conversion_value','note'].map(key => [key, String(draft[key] || '')]));
      payload.create_campaign = Boolean(draft.create_campaign);
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
  const resolveConflict = async (event, conflict) => {
    event.preventDefault(); setBusy(true); setError('');
    const key = `${conflict.campaign_id}:${conflict.metric_date}:${conflict.metric_key}`;
    try {
      await json(`/connect/api/v1/reports/import-conflicts/${conflict.campaign_id}/${conflict.metric_date}/${conflict.metric_key}/resolve?client_id=${data.client.client_id}`, {method: 'POST', headers: {'Content-Type': 'application/json','X-CSRF-Token': data.csrf}, body: JSON.stringify({observation_id: choices[key] || conflict.candidates[0]?.id, note: reasons[key] || ''})});
      await refresh(); await reloadBootstrap();
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
    <article className="reports-panel"><div className="reports-panel-head"><h2>Enviar dados</h2><span>CSV · XLSX · print</span></div><p>Exporte da plataforma ou envie uma captura. Usamos IDs e nomes da origem; você confirma campanhas ausentes antes de armazenar os dados.</p>{!ready && <p className="reports-error">A migração de importações precisa ser aplicada neste ambiente.</p>}{ready && data.client.role !== 'viewer' && <form className="reports-form" onSubmit={submit}><label>Arquivo<input type="file" accept=".csv,.xlsx,.png,.jpg,.jpeg,.webp" required onChange={event => setFile(event.target.files?.[0] || null)} /></label><label>Plataforma, se não estiver no arquivo<input value={platform} onChange={event => setPlatform(event.target.value)} placeholder="Ex.: Google Ads, Meta Ads" /></label><label>Moeda, se houver valores<input maxLength="3" value={currency} onChange={event => setCurrency(event.target.value)} placeholder="BRL" /></label><label>Datas com barras<select value={dateOrder} onChange={event => setDateOrder(event.target.value)}><option value="auto">Detectar; revisar datas ambíguas</option><option value="dmy">Dia/mês/ano</option><option value="mdy">Mês/dia/ano</option></select></label><button disabled={busy || !file}>Enviar arquivo</button></form>}{note && <p>{note}</p>}{error && <p className="reports-error" role="alert">{error}</p>}</article>
    <article className="reports-panel reports-span-two"><div className="reports-panel-head"><h2>Arquivos recebidos</h2><span>{items.length} recentes</span></div>{items.length ? <div className="reports-table-wrap"><table><thead><tr><th>Arquivo</th><th>Estado</th><th>Linhas</th><th>Recebido</th><th></th></tr></thead><tbody>{items.map(item => <tr key={item.id}><td>{item.original_name}</td><td>{({parsed:'Lido',needs_review:'Revisão necessária',awaiting_extraction:'Aguardando leitura visual'})[item.status] || item.status}</td><td>{item.applied_count}/{item.row_count}</td><td>{shortDate(item.created_at)}</td><td><button className="reports-text-button" onClick={() => open(item.id)}>Abrir</button></td></tr>)}</tbody></table></div> : <Empty message="Nenhum arquivo enviado para este cliente." />}</article>
    <article id="reports-data-library" className="reports-panel reports-span-three"><div className="reports-panel-head"><h2>Coleção de métricas personalizadas</h2><span>{customMetrics.length} pares canal/chave</span></div>{customMetrics.length ? <div className="reports-table-wrap"><table><thead><tr><th>Canal</th><th>Chave</th><th>Campo de origem</th><th>Dimensão</th><th>Data</th><th>Último valor</th><th>Observações</th></tr></thead><tbody>{customMetrics.map((metric,index)=><tr key={`${metric.campaign_id}:${metric.channel}:${metric.metric_key}:${metric.metric_date}:${index}`}><td>{metric.channel}</td><td>{metric.metric_key}</td><td>{metric.metric_label}</td><td>{Object.values(metric.dimensions || {}).map(dimension => `${dimension.label}: ${dimension.value}`).join(' · ') || '—'}</td><td>{shortDate(metric.metric_date)}</td><td>{metric.latest_value} {metric.currency || metric.unit}</td><td>{metric.observations}</td></tr>)}</tbody></table></div>:<Empty message="Campos numéricos adicionais dos canais aparecerão aqui como chave/valor."/>}</article>
    <article className="reports-panel reports-span-three"><div className="reports-panel-head"><h2>Valores divergentes</h2><span>{conflicts.length} pendências recentes</span></div>{conflicts.length ? conflicts.map(conflict => {const key = `${conflict.campaign_id}:${conflict.metric_date}:${conflict.metric_key}`; return <details className="reports-suggestion" key={key}><summary><strong>{conflict.platform} · {conflict.account_name} · {conflict.campaign_name}</strong> · {shortDate(conflict.metric_date)} · {conflict.metric_key} · {conflict.version_count} valores distintos</summary><p>Confira os arquivos de origem e escolha um valor. O histórico será preservado.</p>{data.client.role !== 'viewer' ? <form className="reports-form" onSubmit={event => resolveConflict(event, conflict)}><label>Observação<select value={choices[key] || conflict.candidates[0]?.id || ''} onChange={event => setChoices({...choices,[key]:event.target.value})}>{conflict.candidates.map(candidate => <option key={candidate.id} value={candidate.id}>{candidate.value_numeric} {candidate.currency || ''}{Object.values(candidate.dimensions || {}).map(dimension => ` · ${dimension.label}: ${dimension.value}`).join('')} · {candidate.original_name} · {shortDate(candidate.created_at)}</option>)}</select></label><label>Justificativa<input required maxLength="1000" value={reasons[key] || ''} onChange={event => setReasons({...reasons,[key]:event.target.value})} placeholder="Ex.: export mais recente conferido na plataforma" /></label><button disabled={busy || !conflict.candidates.length}>Confirmar valor</button></form> : conflict.candidates.map(candidate => <p key={candidate.id}>{candidate.value_numeric} {candidate.currency || ''} · {candidate.original_name}</p>)}</details>;}) : <Empty message="Nenhuma divergência entre arquivos importados." />}</article>
    <article className="reports-panel reports-span-three"><div className="reports-panel-head"><h2>Snapshots de intervalo</h2><span>{rangeSnapshots.length} recentes · sem soma diária</span></div>{rangeSnapshots.length ? <div className="reports-table-wrap"><table><thead><tr><th>Conta e campanha</th><th>Período</th><th>Métricas do intervalo</th><th>Origem</th><th></th></tr></thead><tbody>{rangeSnapshots.map(snapshot => <tr key={snapshot.id}><td>{snapshot.platform} · {snapshot.account_name} · {snapshot.campaign_name}</td><td>{shortDate(snapshot.period_start)} a {shortDate(snapshot.period_end)}</td><td>{snapshot.metrics.map(metric => `${metric.metric_key}: ${metric.value_numeric} ${metric.currency || metric.unit}`).join(' · ')}</td><td>{snapshot.original_name}</td><td><button type="button" className="reports-text-button" onClick={() => open(snapshot.import_id)}>Abrir print</button></td></tr>)}</tbody></table></div> : <Empty message="Totais de período confirmados em prints aparecerão aqui, separados das métricas diárias." />}</article>
    {detail && <article className="reports-panel reports-span-three"><div className="reports-panel-head"><h2>{detail.import_file.original_name}</h2><span>{detail.import_file.row_count} linhas</span></div>{detail.import_file.file_kind === 'image' ? <>{detail.visual ? <><p>Leitura visual sugerida por {detail.visual.model}. Confira o print antes de usar qualquer número.</p>{detail.visual.result.scopes.map((scope,index) => <div className="reports-suggestion" key={index}><strong>Bloco {index + 1}: {scope.platform || 'Plataforma não identificada'} · {scope.account_name || scope.account_id || 'Conta não identificada'} · {scope.campaign_name || scope.campaign_id || 'Campanha não identificada'}</strong><p>{scope.period_start || 'Período não identificado'}{scope.period_end && scope.period_end !== scope.period_start ? ` a ${scope.period_end}` : ''} · {scope.granularity || 'Granularidade indefinida'} · {scope.currency || 'Moeda não identificada'}</p><small>Evidência: {scope.evidence}</small>{scope.metrics.length ? <ul>{scope.metrics.map((metric,metricIndex) => <li key={metricIndex}>{metric.label}: {metric.raw_value} {metric.unit} · {metric.evidence}</li>)}</ul> : <p>Sem métricas legíveis neste bloco.</p>}</div>)}{detail.visual.result.questions.map((question,index) => <p key={index}>{question}</p>)}</> : <><p>Print recebido. A leitura visual consome créditos Cadu e gera sugestões com evidências; nenhuma campanha ou métrica é confirmada automaticamente.</p>{data.client.role !== 'viewer' && <button type="button" className="reports-text-button" disabled={busy} onClick={extract}>Ler print com IA</button>}</>}</> : <><div className="reports-table-wrap"><table><thead><tr><th>Linha</th><th>Plataforma</th><th>Conta</th><th>Campanha</th><th>Atualização</th><th>Data</th><th>Estado</th><th></th></tr></thead><tbody>{detail.rows.map(row => <tr key={row.id}><td>{row.sheet_name} · {row.source_row}</td><td>{row.parsed.platform || '—'}</td><td>{row.parsed.account_name || row.parsed.external_account_id || '—'}</td><td>{row.parsed.campaign_name || row.parsed.external_campaign_id || '—'}{row.parsed.campaign_match?.state === 'missing' && <small>Campanha associada automaticamente quando a identidade é única</small>}</td><td>{{first:'Primeiros dados',incremental:'Novos dias',revision:'Revisão de valores',duplicate:'Reenvio idêntico',campaign_missing:'Campanha ausente'}[row.parsed.update_kind] || 'Análise pendente'}</td><td>{row.metric_date || '—'}</td><td>{row.reason || (row.decision_note ? `Confirmada: ${row.decision_note}` : 'Incluída na projeção quando não há conflito')}</td><td>{row.status === 'needs_review' && data.client.role !== 'viewer' && <button type="button" className="reports-text-button" onClick={() => edit(row)}>Revisar</button>}</td></tr>)}</tbody></table></div><small>Mostrando até 100 linhas, com pendências primeiro. Valores divergentes entre arquivos aparecem acima para revisão.</small>{(detail.custom_values || []).length > 0 && <div className="reports-suggestion"><strong>Métricas personalizadas · chave/valor</strong>{detail.custom_values.map((metric,index) => <p key={`${metric.import_row_id}:${metric.metric_key}:${index}`}>{metric.campaign_name} · {metric.metric_label} ({metric.metric_key}): {metric.value_numeric} {metric.currency || metric.unit}{Object.values(metric.dimensions || {}).map(dimension => ` · ${dimension.label}: ${dimension.value}`).join('')}</p>)}</div>}</>}</article>}
    {detail?.import_file?.file_kind === 'image' && <VisualConfirm key={detail.import_file.id} detail={detail} data={data} busy={busy} setBusy={setBusy} setError={setError} onRefresh={async () => {await open(detail.import_file.id); await refresh(); await reloadBootstrap();}} />}
    {detail && detail.import_file.file_kind !== 'image' && <ColumnMapping key={detail.import_file.id} detail={detail} data={data} busy={busy} setBusy={setBusy} setError={setError} onRefresh={async () => {await open(detail.import_file.id); await refresh(); await reloadBootstrap();}} />}
    {editing && <article className="reports-panel reports-span-three"><div className="reports-panel-head"><h2>Revisar linha</h2><button type="button" className="reports-text-button" onClick={() => setEditing(null)}>Fechar</button></div>{draft.campaign_match?.state === 'missing' && <div className="reports-suggestion"><strong>Campanha não encontrada</strong><p>Não localizamos {draft.campaign_name} ({draft.platform} · conta {draft.external_account_id} · campanha {draft.external_campaign_id}). Escolha criar essa campanha para armazenar os dados importados.</p>{!draft.campaign_match?.account_id && <p>Se a conta ainda não estiver cadastrada, os campos acima serão usados para criar o vínculo; sem ID externo, ela ficará identificada como conta de importação do Reports.</p>}<label className="reports-checkbox"><input type="checkbox" checked={Boolean(draft.create_campaign)} onChange={event => setDraft({...draft,create_campaign:event.target.checked})} />Criar campanha e associar os dados desta linha</label></div>}{draft.update_kind && <p>Tipo identificado: {{first:'primeiros dados da campanha',incremental:'novos dias de dados',revision:'valores diferentes para uma data já recebida',duplicate:'reenvio com os mesmos valores',campaign_missing:'campanha ainda sem associação'}[draft.update_kind]}.</p>}<form className="reports-form" onSubmit={resolve}><div className="reports-form-pair">{[['platform','Plataforma'],['external_account_id','ID da conta'],['account_name','Nome da conta'],['external_campaign_id','ID da campanha'],['campaign_name','Nome da campanha'],['metric_date','Data ISO (AAAA-MM-DD)'],['currency','Moeda'],['impressions','Impressões'],['clicks','Cliques'],['cost','Custo'],['conversions','Conversões'],['conversion_value','Valor das conversões']].map(([key,label]) => <label key={key}>{label}<input value={draft[key] || ''} onChange={event => setDraft({...draft,[key]:event.target.value})} /></label>)}</div><label>Justificativa<input required maxLength="1000" value={draft.note || ''} onChange={event => setDraft({...draft,note:event.target.value})} placeholder="Ex.: data e conta conferidas no export original" /></label><button disabled={busy || (draft.campaign_match?.state === 'missing' && !draft.create_campaign)}>Confirmar linha</button></form></article>}
  </section>;
}

function App() {
  const [section, setSection] = useState(() => location.hash.slice(1) || 'overview');
  const pageSection = SECTION_ALIASES[section] || section;
  const [data, setData] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [importedMetrics, setImportedMetrics] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const dateToday = new Date();
  const dateStart = new Date(dateToday); dateStart.setDate(dateStart.getDate() - 29);
  const isoDate = value => `${value.getFullYear()}-${String(value.getMonth()+1).padStart(2,'0')}-${String(value.getDate()).padStart(2,'0')}`;
  const [filters, setFilters] = useState({platform: '', account: '', campaign: '', period: '30', startDate: isoDate(dateStart), endDate: isoDate(dateToday)});
  const sectionsWithGlobalFilters = new Set(['overview', 'campaigns', 'reports', 'flow', 'events']);
  const clientId = new URLSearchParams(location.search).get('client_id');
  const load = async () => {
    try {setData(await json(`/connect/api/v1/reports/bootstrap${clientId ? `?client_id=${encodeURIComponent(clientId)}` : ''}`)); setError('');}
    catch (failure) {setError(failure.message);}
  };
  useEffect(() => {load(); const onHash = () => setSection(location.hash.slice(1) || 'overview'); addEventListener('hashchange', onHash); return () => removeEventListener('hashchange', onHash);}, []);
  useEffect(() => {
    if (!data?.ready) return undefined;
    let cancelled = false;
    const params = new URLSearchParams({client_id: String(data.client.client_id), days: filters.period, start_date: filters.startDate, end_date: filters.endDate});
    if (filters.platform) params.set('platform', filters.platform);
    if (filters.account) params.set('account_id', filters.account);
    if (filters.campaign) params.set('campaign_id', filters.campaign);
    json(`/connect/api/v1/reports/metrics?${params}`).then(value => {if (!cancelled) setMetrics(value);}).catch(failure => {if (!cancelled) setError(failure.message);});
    json(`/connect/api/v1/reports/import-metrics?${params}`).then(value => {if (!cancelled) setImportedMetrics(value);}).catch(failure => {if (!cancelled) setError(failure.message);});
    return () => {cancelled = true;};
  }, [data?.client?.client_id, data?.ready, filters.platform, filters.account, filters.campaign, filters.period, filters.startDate, filters.endDate, section]);
  const save = async (path, payload, reload = true, method = 'POST') => {
    setBusy(true); setError('');
    try {
      const result = await json(`/connect/api/v1/reports${path}`, {method, headers: {'Content-Type': 'application/json', 'X-CSRF-Token': data.csrf}, body: JSON.stringify({...payload, client_id: data.client.client_id})});
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
  const reportIcons = {overview:'home',accounts:'users',campaigns:'plan',reports:'analysis',imports:'download',monitor:'pulse',supertag:'plugin',flow:'branch',events:'calendar',links:'link',access:'folder'};
  const navItems = ids => SECTIONS.filter(([id]) => ids.includes(id) && (id !== 'access' || data?.can_manage_access)).map(([id,title]) => ({id,label:title,icon:reportIcons[id],href:`#${id}`}));
  const solutionUrls={workspace:rootElement.dataset.workspaceUrl,planner:rootElement.dataset.plannerUrl,studio:rootElement.dataset.studioUrl,connect:location.pathname+location.search,skills:rootElement.dataset.skillsUrl};
  const solutionIcons={workspace:'/static/images/cadu/products/cadu-icon.png',planner:'/static/images/cadu/products/planner-icon.png',studio:'/static/images/cadu/products/studio-icon.png',connect:'/static/images/cadu/products/connect-icon.png',skills:'/static/images/cadu/products/skills-icon.png'};
  return <div className={`reports-shell reports-shell--${pageSection}`}>
    <SolutionSidebar solution="Reports" context={data?.client?.client_name || 'Cliente'} userName={rootElement.dataset.userName||'Minha conta'} userAvatar={rootElement.dataset.userAvatar||''} creditsUrl={rootElement.dataset.creditsUrl} profileUrl={rootElement.dataset.profileUrl} accent="#2871d2" storageKey="reports-sidebar" active={pageSection} activeSolutionId="connect" solutionLogo={solutionIcons.connect} solutionUrls={solutionUrls} solutionIcons={solutionIcons} groups={[{label:'Visão geral',items:navItems(['overview'])},{label:'Operação de mídia',items:navItems(['accounts','campaigns','reports','imports','monitor'])},{label:'Mensuração',items:navItems(['supertag','flow','events','links'])},{label:'Administração',items:navItems(['access'])}]} />
    <main className="reports-main"><header className="reports-header"><div><p>Reports</p><h1>{TITLES[pageSection] || (section === 'data-library' ? 'Biblioteca de dados' : 'Visão geral')}</h1></div><div className="reports-header-actions"><select className="reports-client-pill" aria-label="Cliente Reports" value={data?.client?.client_id || ''} onChange={event => {location.href = `/connect/app?client_id=${encodeURIComponent(event.target.value)}#${section}`;}}>{(data?.clients || []).map(item => <option key={item.id} value={item.id}>{item.name}{item.kind === 'reports' ? ' · Reports' : ''}</option>)}</select>{pageSection === 'overview' && <a href="#data-library">Biblioteca de dados ↗</a>}</div></header>
      {sectionsWithGlobalFilters.has(pageSection) && <div className="reports-filters reports-filters--combined" aria-label="Filtros e período"><label>Plataforma<select value={filters.platform} onChange={event => setFilters({...filters, platform: event.target.value, account: '', campaign: ''})}><option value="">Todas</option>{[...new Set((data?.accounts || []).map(item => item.platform))].map(value => <option key={value} value={value}>{value}</option>)}</select></label><label>Conta<select value={filters.account} onChange={event => setFilters({...filters, account: event.target.value, campaign: ''})}><option value="">Todas</option>{(data?.accounts || []).filter(item => item.account_kind === 'advertiser' && (!filters.platform || item.platform === filters.platform)).map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Campanha<select value={filters.campaign} onChange={event => setFilters({...filters, campaign: event.target.value})}><option value="">Todas</option>{(data?.campaigns || []).filter(item => !filters.account || String(item.account_id) === filters.account).map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Período<select value={filters.period} onChange={event => {const period=event.target.value;const end=new Date();const start=new Date(end);start.setDate(start.getDate()-Number(period)+1);setFilters({...filters,period,startDate:isoDate(start),endDate:isoDate(end)});}}><option value="7">7 dias</option><option value="30">30 dias</option><option value="90">90 dias</option></select></label><button type="button" onClick={load}>Atualizar</button></div>}
      <div className="reports-content">{error && <div className="reports-error" role="alert">{error}</div>}{!data ? <Empty message="Carregando Reports…" /> : !data.ready ? <Empty message="A base de Reports V1 ainda precisa da migração de dados." /> : pageSection === 'accounts' ? <Accounts data={data} save={save} busy={busy} /> : pageSection === 'campaigns' ? <Campaigns data={data} save={save} busy={busy} filters={filters} /> : pageSection === 'reports' ? <Reports data={data} save={save} busy={busy} /> : pageSection === 'supertag' ? <SuperTag data={data} /> : pageSection === 'links' ? <Links data={data} save={save} busy={busy} /> : pageSection === 'imports' ? <Imports data={data} reloadBootstrap={load} focusLibrary={section === 'data-library'} /> : pageSection === 'monitor' ? <Monitor data={data} save={save} busy={busy} /> : pageSection === 'flow' ? <Flow data={data} save={save} busy={busy} filters={filters} /> : pageSection === 'events' ? <Events key={section} data={data} filters={filters} initialKind={section === 'conversions' ? 'conversion' : 'all'} /> : pageSection === 'access' && data.can_manage_access ? <Access data={data} save={save} busy={busy} /> : <Overview data={selected} metrics={metrics} imported={importedMetrics} />}</div>
    </main>
  </div>;
}

createRoot(rootElement).render(<App />);
