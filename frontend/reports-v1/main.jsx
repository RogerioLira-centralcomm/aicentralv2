import {Flow} from './FlowsPage.jsx';
import {ImportsPage} from './ImportsPage.jsx';
import {MediaData} from './MediaData.jsx';
import {AccessPage} from './AccessPage.jsx';
import {LinkTester} from './LinkTester.jsx';
import {EventsPage} from './EventsPage.jsx';
import {ReportsLibrary} from './ReportsLibrary.jsx';
import {CampaignDetail} from './CampaignDetail.jsx';
import {CAMPAIGN_STATUS, ClientsAccounts, Status as CampaignStatus, channelLabel} from './ClientsAccounts.jsx';
import {ReportsRelationships} from './ReportsRelationships.jsx';
import {SharedReports} from './SharedReports.jsx';
import React, {useEffect, useMemo, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {SolutionSidebar} from '../cadu-design-system/components/SolutionSidebar.jsx';
import {Button as UntitledButton} from '../cadu-design-system/untitled-kit/button.tsx';
import {ReportsActionButton} from './ReportsActionButton.jsx';
import {ReportsFieldInput} from './ReportsFieldInput.jsx';
import {ReportsNativeSelect} from './ReportsNativeSelect.jsx';
import {ReportsDrawer} from './ReportsDrawer.jsx';
import {ReportsTextArea} from './ReportsTextArea.jsx';
import {ReportsConfirmDialog} from './ReportsConfirmDialog.jsx';
import {ReportsTabs} from './ReportsTabs.jsx';
import {AccessCard, InstallCard, InstallGuide, InstallStatus, LinkedFlows, RecentEvents, SiteSidebar, SiteSummary, StatusBadge} from './SuperTagParts.jsx';
import './supertag-workspace.css';
import {PageDetail} from './PageDetail.jsx';
import {AlertsCenter} from './AlertsCenter.jsx';
import {REPORT_FILTER_DEFAULTS, ReportsFilterBar} from './PageChrome.jsx';
import {APP_BASE, HUBS, applyLegacyRedirect, navigate, navigateOnClick, resolveRoute, useLocationKey} from './shell/routes.js';
import {ReportsContext, periodFilters, readPeriod, writePeriod} from './shell/context.js';
import {ContextSelector, PageHeader} from './shell/PageHeader.jsx';
import {LoadingState} from './shell/primitives.jsx';
import {setActiveClient} from './shell/useApi.js';
import {platformName} from './shell/media.jsx';
import {Overview} from './hubs/overview/Overview.jsx';
import {MediaOverview} from './hubs/media/MediaOverview.jsx';
import {GoogleAds} from './hubs/media/GoogleAds.jsx';
import {MediaCreatives} from './hubs/media/MediaCreatives.jsx';
import {Contents} from './hubs/journey/Contents.jsx';
import {JourneyOverview} from './hubs/journey/JourneyOverview.jsx';
import {Navigation} from './hubs/journey/Navigation.jsx';
import {Conversions} from './hubs/journey/Conversions.jsx';
import {DataSources} from './hubs/data-sources/DataSources.jsx';
import {Plus} from '@untitledui/icons';
import {dropClientFromUrl, flowEditorId, reportUrl, shortDate, integer, decimal, json, Empty, Kpi} from './reportsCommon.jsx';
import '../cadu-design-system/tokens.css';
import './styles.css';
import './flow-workspace.css';
import './reports-refinement.css';
import '../cadu-design-system/primitives.css';
// Shell layer last: the new header, blocks and navigation win over the older page styles.
import './shell/shell.css';
// Last: the single definition of each layout primitive (Untitled v8, tokens only).
import './reports-ui.css';

const rootElement = document.getElementById('cadu-reports-v1-root');
document.documentElement.dataset.caduSkin = 'reports';






const FLOW_ROLE_LABELS = {
  entry:'Entrada', intermediate:'Página', form:'Formulário',
  conversion:'Conversão', error:'Erro', none:'Sem correspondência',
};
const FLOW_NODE_LABELS = {page:'Página', form:'Formulário', event:'Evento', whatsapp:'WhatsApp', conversion:'Conversão', erro:'Erro'};

function FlowSuggestionConfidence({suggestion}) {
  const alternatives = Object.entries(suggestion?.probabilities || {})
    .filter(([role, probability]) => FLOW_ROLE_LABELS[role] && Number.isFinite(Number(probability)))
    .sort((left, right) => Number(right[1]) - Number(left[1]));
  const confidence = Number(suggestion?.confidence);
  if (!alternatives.length) return null;
  return <span className="reports-flow-ai-confidence" title="A concentração resume a distribuição das alternativas; não é garantia de acerto.">
    {Number.isFinite(confidence) ? `Concentração ${Math.round(confidence * 100)}% · ` : ''}
    Alternativas: {alternatives.map(([role, probability]) => `${FLOW_ROLE_LABELS[role]} ${Math.round(Number(probability) * 100)}%`).join(' / ')}
  </span>;
}



/** Campaign detail lives at /media/campaigns/<id>; ?campaign_id= from older links is still understood. */
const campaignIdFromUrl = () => resolveRoute().entity || new URLSearchParams(location.search).get('campaign_id') || '';

function Campaigns({data, save, busy, filters, refreshRevision}) {
  const [campaignId, setCampaignId] = useState(campaignIdFromUrl);
  const [campaignDetail, setCampaignDetail] = useState(null);
  const [detailError, setDetailError] = useState('');
  const [tab, setTab] = useState(() => {
    const current = new URLSearchParams(location.search).get('campaign_tab') || 'overview';
    return current === 'metrics' ? 'performance' : current;
  });
  const visibleCampaigns = data.campaigns.filter(item =>
    (!filters.platform || item.platform === filters.platform) &&
    (!filters.account || String(item.account_id) === filters.account) &&
    (!filters.campaign || String(item.id) === filters.campaign));
  useEffect(() => {
    let live = true;
    if (!campaignId) {setCampaignDetail(null); return () => {live=false;};}
    json(`/connect/api/v2/reports/campaigns/${campaignId}?client_id=${data.client.client_id}`)
      .then(value => {if(live){setCampaignDetail(value);setDetailError('');}})
      .catch(error => {if(live)setDetailError(error.message);});
    return () => {live=false;};
  }, [campaignId, data.client.client_id]);
  useEffect(()=>{const sync=()=>{const params=new URLSearchParams(location.search);setCampaignId(campaignIdFromUrl());const current=params.get('campaign_tab')||'overview';setTab(current==='metrics'?'performance':current);};addEventListener('popstate',sync);return()=>removeEventListener('popstate',sync);},[]);
  const campaignUrl = ({id = campaignId, view = ''} = {}) => {
    const url = new URL(location.href);
    url.searchParams.delete('client_id');
    url.searchParams.delete('campaign_id');
    if (view) url.searchParams.set('campaign_tab', view); else url.searchParams.delete('campaign_tab');
    url.pathname = `${APP_BASE}/media/campaigns${id ? `/${encodeURIComponent(id)}` : ''}`;
    url.hash = '';
    return url;
  };
  const openCampaign = item => {setCampaignId(String(item.id));setTab('overview');history.pushState(null,'',campaignUrl({id:item.id}));};
  const changeCampaignTab = value => {setTab(value);history.replaceState(history.state,'',campaignUrl({view:value}));};
  const closeCampaign = () => {setCampaignId('');setCampaignDetail(null);setDetailError('');history.replaceState(history.state,'',campaignUrl({id:'',view:''}));};
  if (campaignId) return <CampaignDetail data={data} detail={campaignDetail} error={detailError} tab={tab} setTab={changeCampaignTab} close={closeCampaign} filters={filters} refreshRevision={refreshRevision} save={save} busy={busy} updateDetail={setCampaignDetail} />;
  return <section className="reports-campaigns-page reports-campaigns-list-page"><article className="reports-panel">
    <div className="reports-panel-head"><div><h2>Campanhas <small>{visibleCampaigns.length} de {data.campaigns.length}</small></h2><p>Abra uma campanha para ver desempenho, criativos e jornada.</p></div>
      <UntitledButton size="sm" color="secondary" href={`${APP_BASE}/settings/accounts`}>Gerenciar em Clientes e contas</UntitledButton></div>
    {visibleCampaigns.length ? <div className="reports-table-wrap"><table className="cadu-table"><thead><tr><th>Campanha</th><th>Conta</th><th>Tipo</th><th>Status</th></tr></thead><tbody>{visibleCampaigns.map(item => <tr key={item.id}>
      <td><a className="reports-campaign-link" href={campaignUrl({id: item.id}).pathname} onClick={event => {event.preventDefault(); openCampaign(item);}}><strong>{item.name}</strong><small>{item.external_id ? `ID ${item.external_id}` : 'Campanha manual'}</small></a></td>
      <td><span className="reports-cell-stack"><span>{item.account_name || 'Sem conta de mídia'}</span><small>{platformName(item.platform)}</small></span></td>
      <td>{channelLabel(item.channel_type || item.objective) || '—'}</td>
      <td><CampaignStatus map={CAMPAIGN_STATUS} value={item.status}/></td></tr>)}</tbody></table></div>
      : <Empty message={data.campaigns.length ? 'Nenhuma campanha corresponde aos filtros desta página.' : 'Nenhuma campanha ainda. Cadastre em Clientes e contas ou sincronize uma conta de mídia.'} />}
  </article></section>;
}

// Flows page lives in FlowsPage.jsx.
function BrandingInsights({branding}) {
  const overall = branding?.overall;
  if (!overall || !Number(overall.sessions)) return null;
  const engagedRate = Number(overall.sessions) ? Math.round(100 * Number(overall.engaged_sessions) / Number(overall.sessions)) : 0;
  const coverage = Number(overall.sessions) ? Math.round(100 * Number(overall.measured_sessions) / Number(overall.sessions)) : 0;
  return <div className="reports-supertag-branding">
    <article className="reports-panel"><div className="reports-panel-head"><div><h2>Visão de marca e público</h2><p>Últimos 30 dias · sessões com consentimento e página vista</p></div><span>Site conectado</span></div>
      <div className="reports-supertag-kpis"><Kpi label="Visitantes observados" value={integer(overall.visitors)} detail="Identificadores desta instalação"/><Kpi label="Sessões" value={integer(overall.sessions)} detail={`${integer(overall.closed_sessions)} encerradas por inatividade`}/><Kpi label="Engajamento" value={`${engagedRate}%`} detail="2+ páginas, 10 s ativos ou conversão"/><Kpi label="Tempo ativo médio" value={overall.avg_active_seconds == null?'—':`${decimal(overall.avg_active_seconds)} s`} detail={`${coverage}% das sessões com duração medida`}/></div>
      <p className="reports-info">Média de {decimal(overall.avg_pages || 0)} páginas por sessão · {integer(overall.deep_scroll_sessions)} sessões chegaram a 75% de rolagem. O tempo exclui períodos em que a aba estava oculta.</p>
    </article>
    <article className="reports-panel"><div className="reports-panel-head"><div><h2>Campanhas observadas no site</h2><p>Primeira UTM da sessão; eventos permanecem atribuídos durante a navegação</p></div><span>{branding.campaigns?.length || 0} origens</span></div>
      {branding.campaigns?.length?<div className="reports-table-wrap"><table className="cadu-table"><thead><tr><th>Campanha</th><th>Visitantes</th><th>Sessões</th><th>Engajadas</th><th>Tempo ativo</th><th>Formulários</th><th>WhatsApp</th><th>Conversões</th></tr></thead><tbody>{branding.campaigns.map(row=><tr key={row.campaign_scope||'sem-campanha'}><td>{row.campaign_scope||'Sem campanha identificada'}</td><td>{integer(row.visitors)}</td><td>{integer(row.sessions)}</td><td>{integer(row.engaged_sessions)}</td><td>{row.avg_active_seconds==null?'—':`${decimal(row.avg_active_seconds)} s`}</td><td>{integer(row.forms)}</td><td>{integer(row.whatsapp_clicks)}</td><td>{integer(row.conversions)}</td></tr>)}</tbody></table></div>:<Empty message="As campanhas aparecem quando o tráfego chega com utm_id ou utm_campaign."/>}
    </article>
    <article className="reports-panel"><div className="reports-panel-head"><div><h2>Coortes de retorno</h2><p>Semana da primeira visita observada · retorno entre 1 e 7 dias</p></div><span>Até 8 semanas</span></div>
      {branding.cohorts?.length?<div className="reports-table-wrap"><table className="cadu-table"><thead><tr><th>Semana</th><th>Campanha</th><th>Visitantes</th><th>Retornaram</th><th>Taxa</th></tr></thead><tbody>{branding.cohorts.map(row=><tr key={`${row.campaign_scope}:${row.cohort_week}`}><td>{shortDate(row.cohort_week)}</td><td>{row.campaign_scope||'Sem campanha identificada'}</td><td>{integer(row.visitors)}</td><td>{integer(row.returned_7d)}</td><td>{Number(row.visitors)?`${Math.round(100*Number(row.returned_7d)/Number(row.visitors))}%`:'—'}</td></tr>)}</tbody></table></div>:<Empty message="Coortes aparecem após sete dias de visitas consentidas."/>}
    </article>
  </div>;
}

const siteFaviconCache = new Map();

function SiteFavicon({site}) {
  const host = site.allowed_host;
  const [favicon, setFavicon] = useState(() => siteFaviconCache.get(host) ?? `https://${host}/favicon.ico`);
  const [loaded, setLoaded] = useState(false);
  const [checked, setChecked] = useState(false);
  useEffect(() => {
    setFavicon(siteFaviconCache.get(host) ?? `https://${host}/favicon.ico`);
    setLoaded(false);
    setChecked(false);
  }, [host]);
  // The initial stays on screen until an image really loads, so a failing favicon never shows a broken-image icon.
  const recover = async () => {
    setLoaded(false);
    if (checked) {
      siteFaviconCache.set(host, '');
      setFavicon('');
      return;
    }
    setChecked(true);
    try {
      const preview = await json(`/connect/api/v2/reports/supertag/site-check?url=${encodeURIComponent(`https://${host}`)}`);
      const next = preview.favicon || '';
      siteFaviconCache.set(host, next);
      setFavicon(next);
    } catch (_) {
      siteFaviconCache.set(host, '');
      setFavicon('');
    }
  };
  return <span className="reports-site-list-favicon" aria-hidden="true">
    <span className="reports-site-list-favicon__initial">{(site.label || host).trim().charAt(0).toUpperCase()}</span>
    {favicon && <img src={favicon} alt="" referrerPolicy="no-referrer" onLoad={() => setLoaded(true)} onError={recover} style={loaded ? undefined : {visibility: 'hidden'}}/>}
  </span>;
}

function SuperTag({data}) {
  const [sites, setSites] = useState([]);
  const [sitesLoading, setSitesLoading] = useState(true);
  const [sitesLoadFailed, setSitesLoadFailed] = useState(false);
  const [selectedId, setSelectedId] = useState(() => location.pathname.match(/^\/connect\/app\/supertag\/sites\/([0-9a-f-]{36})(?:\/monitor)?\/?$/i)?.[1] || '');
  const [siteTab, setSiteTab] = useState('overview');
  const [siteFlows, setSiteFlows] = useState([]);
  const [siteQuery, setSiteQuery] = useState('');
  const [detailLoading, setDetailLoading] = useState(false);
  const [detail, setDetail] = useState(null);
  const [label, setLabel] = useState('Site principal');
  const [host, setHost] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [installOpen, setInstallOpen] = useState(false);
  const [verify, setVerify] = useState(null);
  const [verifying, setVerifying] = useState(false);
  const [revokeConfirmOpen, setRevokeConfirmOpen] = useState(false);
  const [siteCheck, setSiteCheck] = useState(null);
  const [checkingSite, setCheckingSite] = useState(false);
  const load = async () => {
    const value = await json(`/connect/api/v2/reports/supertag/sites?client_id=${data.client.client_id}`);
    setSites(value.sites || []);
    if (selectedId && value.sites.some(item => item.id === selectedId)) return;
    setSelectedId('');
  };
  useEffect(() => {
    let active = true;
    setSites([]);
    setSitesLoading(true);
    setSitesLoadFailed(false);
    json(`/connect/api/v2/reports/supertag/sites?client_id=${data.client.client_id}`)
      .then(value => {
        if (!active) return;
        const nextSites = value.sites || [];
        setSites(nextSites);
        setSelectedId(current => current && !nextSites.some(item => item.id === current) ? '' : current);
      })
      .catch(failure => {if (active) {setSitesLoadFailed(true);setError(failure.message);}})
      .finally(() => {if (active) setSitesLoading(false);});
    return () => {active = false;};
  }, [data.client.client_id]);
  useEffect(() => {
    setDetail(null);setSiteFlows([]);setError('');setVerify(null);
    if (!selectedId) {setDetailLoading(false);return;}
    let cancelled=false;setDetailLoading(true);
    Promise.allSettled([
      json(`/connect/api/v2/reports/supertag/sites/${selectedId}/events?client_id=${data.client.client_id}`),
      json(`/connect/api/v2/reports/flow?client_id=${data.client.client_id}&view=create`)
    ]).then(([events,flows])=>{
      if(cancelled)return;
      if(events.status==='fulfilled')setDetail(events.value);
      if(flows.status==='fulfilled')setSiteFlows(flows.value.flows||[]);
      const failures=[];
      if(events.status==='rejected')failures.push(`Não foi possível carregar a atividade: ${events.reason.message}`);
      if(flows.status==='rejected')failures.push(`Não foi possível carregar os fluxos: ${flows.reason.message}`);
      setError(failures.join(' '));
    })
      .finally(()=>{if(!cancelled)setDetailLoading(false);});
    return()=>{cancelled=true;};
  }, [selectedId, data.client.client_id]);
  const create = async event => {
    event.preventDefault(); setBusy(true); setError(''); setNotice('');
    try {
      const checkedHost = new URL(host.includes('://') ? host : `https://${host}`).host;
      const result = await json(`/connect/api/v2/reports/supertag/sites?client_id=${data.client.client_id}`, {
        method:'POST', headers:{'Content-Type':'application/json','X-CSRF-Token':data.csrf},
        body:JSON.stringify({label,allowed_host:checkedHost})});
      if (siteCheck?.favicon) siteFaviconCache.set(checkedHost, siteCheck.favicon);
      await load(); location.assign(reportUrl('supertag', {}, result.site.id));
    } catch (failure) {setError(failure.message);} finally {setBusy(false);}
  };
  const update = async changes => {
    if (!selectedId) return;
    setBusy(true); setError('');
    try {
      await json(`/connect/api/v2/reports/supertag/sites/${selectedId}?client_id=${data.client.client_id}`, {
        method:'PATCH', headers:{'Content-Type':'application/json','X-CSRF-Token':data.csrf}, body:JSON.stringify(changes)});
      await load();
      const latest = await json(`/connect/api/v2/reports/supertag/sites/${selectedId}/events?client_id=${data.client.client_id}`);
      setDetail(latest);
    } catch (failure) {setError(failure.message);} finally {setBusy(false);}
  };
  const revoke = async () => {
    if (!selectedId) return;
    setBusy(true); setError('');
    try {
      await json(`/connect/api/v2/reports/supertag/sites/${selectedId}/revoke?client_id=${data.client.client_id}`, {
        method:'POST', headers:{'X-CSRF-Token':data.csrf}, body:JSON.stringify({})});
      setSelectedId(''); setDetail(null); setRevokeConfirmOpen(false); await load(); location.assign(reportUrl('supertag'));
    } catch (failure) {setError(failure.message);} finally {setBusy(false);}
  };
  const selected = sites.find(item => item.id === selectedId);
  const copy = async value => {
    try {await navigator.clipboard.writeText(value); setNotice('Copiado.');}
    catch (_) {setNotice('Não foi possível copiar automaticamente. Selecione o código e copie.');}
  };
  const verifyInstall = async () => {
    if (!selectedId) return;
    setVerifying(true); setError('');
    try {
      const [result, latest] = await Promise.all([
        json(`/connect/api/v2/reports/supertag/sites/${selectedId}/verify-install?client_id=${data.client.client_id}`),
        json(`/connect/api/v2/reports/supertag/sites/${selectedId}/events?client_id=${data.client.client_id}`)]);
      setVerify(result); setDetail(latest); await load();
    } catch (failure) {setError(failure.message);} finally {setVerifying(false);}
  };
  const kindTotal = kind => Number((detail?.summary || []).find(item => item.event_kind === kind)?.total || 0);
  const checkSite = async () => {
    if (!host.trim()) return;
    setCheckingSite(true); setSiteCheck(null); setError('');
    try {setSiteCheck(await json(`/connect/api/v2/reports/supertag/site-check?url=${encodeURIComponent(host.trim())}`));}
    catch (failure) {setSiteCheck({error:failure.message});}
    finally {setCheckingSite(false);}
  };
  const downloadSnippet = () => {
    if (!selected) return;
    const blob = new Blob([selected.snippet], {type:'text/plain;charset=utf-8'});
    const url = URL.createObjectURL(blob); const anchor = document.createElement('a');
    anchor.href=url; anchor.download=`cadu-supertag-${selected.allowed_host}.txt`; anchor.click(); URL.revokeObjectURL(url);
  };
  const emailSnippet = () => {
    if (!selected) return;
    const subject = encodeURIComponent(`Instalação da Super Tag no site ${selected.allowed_host}`);
    const body = encodeURIComponent(`Olá!\n\nPor favor, instale a Super Tag no site ${selected.allowed_host}.\n\nCole este código antes de </head> ou pelo gerenciador de tags:\n\n${selected.snippet}\n\nDepois de publicar, avise para validarmos o primeiro envio. A coleta respeita o consentimento configurado.\n`);
    window.location.href=`mailto:?subject=${subject}&body=${body}`;
  };
  // The site list carries the 30-day total; the detail call only refines it, so either source proves collection.
  const hasEvents = Number(selected?.events_30d || detail?.site?.events_30d || 0)>0;
  const tagInstalled = Boolean(selected && hasEvents);
  const collectionKnown = Boolean(detail?.site);
  const visibleSites = sites.filter(site => `${site.label} ${site.allowed_host}`.toLowerCase().includes(siteQuery.toLowerCase()));
  const installationState = selected?.revoked_at ? 'Revogada' : !selected?.enabled ? 'Desativada' : !collectionKnown ? 'Coleta não consultada' : tagInstalled ? 'Eventos recebidos · 30 dias' : 'Sem eventos · 30 dias';
  const sitesTotal = sites.length;
  const renderFavicon = site => <SiteFavicon site={site}/>;
  const canEdit = data.client.role !== 'viewer';
  const activeSites = sites.filter(site => Number(site.events_30d) > 0).length;
  const openInstall = () => {setInstallOpen(true);setSiteCheck(null);};
  const hostKey = value => String(value || '').replace(/^www\./, '');
  const linkedFlowsCount = selected ? siteFlows.filter(item => hostKey(item.allowed_host) === hostKey(selected.allowed_host)).length : 0;
  const tabs = [{id:'overview',label:'Visão geral'},{id:'install',label:'Instalação'},{id:'flows',label:'Fluxos'},{id:'settings',label:'Configurações'}];
  return <section className="st-page">
    <header className="st-topbar"><p className="reports-sr-only">Sites com a Super Tag e o estado da coleta.</p>
      <div className="st-topbar__side">{sitesTotal>0&&<><StatusBadge tone="gray">{sitesTotal} {sitesTotal===1?'site conectado':'sites conectados'}</StatusBadge><StatusBadge tone={activeSites?'success':'warning'}>{activeSites?`${activeSites} com coleta ativa`:'Sem coleta ativa'}</StatusBadge></>}{canEdit&&<ReportsActionButton color={selected?'secondary':'primary'} iconLeading={Plus} onClick={openInstall}>Conectar site</ReportsActionButton>}</div></header>
    {error&&<p className="reports-error" role="alert">{error}</p>}{notice&&<p className="reports-success" role="status">{notice}</p>}
    <div className="st-layout">
      <SiteSidebar sites={sites} loading={sitesLoading} query={siteQuery} onQuery={setSiteQuery} selectedId={selectedId} canAdd={canEdit} onAdd={openInstall} renderFavicon={renderFavicon}/>
      <main className="st-main">
        {!selected&&!sitesLoading&&<div className="st-empty"><h2>{sitesTotal?'Selecione um site':canEdit?'Conecte seu primeiro site':'Nenhum site conectado'}</h2><p>{sitesTotal?'Escolha um site na lista para ver a instalação, os eventos e os fluxos vinculados.':canEdit?'Instale a Super Tag para acompanhar visitas e eventos consentidos.':'Os sites autorizados para este cliente aparecerão aqui.'}</p>{!sitesTotal&&canEdit&&<ReportsActionButton color="primary" onClick={openInstall}>Conectar site</ReportsActionButton>}</div>}
        {selected&&<>
          <SiteSummary site={selected} flowsCount={detailLoading?null:linkedFlowsCount} hasEvents={hasEvents} renderFavicon={renderFavicon}/>
          <ReportsTabs className="reports-site-tabs" label="Áreas do site" value={siteTab} onChange={setSiteTab} items={tabs}/>
          {detailLoading&&<p className="st-muted" role="status">Carregando dados do site…</p>}
          {siteTab==='overview'&&<>
            <InstallStatus site={selected} hasEvents={hasEvents} verify={verify} verifying={verifying} onVerify={verifyInstall} onCopy={()=>copy(selected.snippet)} onGuide={()=>setSiteTab('install')}/>
            <div className="st-grid"><InstallCard site={selected} onCopy={()=>copy(selected.snippet)} onDownload={downloadSnippet} onEmail={emailSnippet}/>{hasEvents?<RecentEvents summary={detail?.summary}/>:<InstallGuide/>}</div>
            <div className="st-grid st-grid--wide"><LinkedFlows flows={siteFlows} site={selected}/><AccessCard data={data} site={selected}/></div>
          </>}
          {siteTab==='install'&&<>
            <InstallCard site={selected} onCopy={()=>copy(selected.snippet)} onDownload={downloadSnippet} onEmail={emailSnippet}/>
            <InstallGuide/>
          </>}
          {siteTab==='flows'&&<LinkedFlows flows={siteFlows} site={selected}/>}
          {siteTab==='settings'&&<article className="st-card st-settings"><header><div><h3>Configurações da tag</h3><p>Identificação, retenção e consentimento deste site.</p></div></header>
        <div className="reports-supertag-settings">
          <label>Duração do identificador<ReportsNativeSelect disabled={busy || data.client.role==='viewer'} value={selected.config?.audience_days || 365} onChange={event=>update({audience_days:Number(event.target.value)})}>{[[30,'30 dias'],[60,'60 dias'],[90,'90 dias'],[180,'6 meses'],[365,'1 ano'],[395,'13 meses (máximo do navegador)']].map(([days,name])=><option key={days} value={days}>{name}</option>)}</ReportsNativeSelect><small>Tempo que o mesmo visitante é reconhecido. Navegadores limitam este valor a cerca de 13 meses.</small></label>
          <label>Retenção dos eventos<ReportsNativeSelect disabled={busy || data.client.role==='viewer'} value={selected.config?.retention_days || 365} onChange={event=>update({retention_days:Number(event.target.value)})}>{[[30,'30 dias'],[60,'60 dias'],[90,'90 dias'],[180,'6 meses'],[365,'1 ano'],[730,'2 anos'],[1095,'3 anos'],[1825,'5 anos']].map(([days,name])=><option key={days} value={days}>{name}</option>)}</ReportsNativeSelect><small>Por quanto tempo os eventos ficam guardados para comparar períodos.</small></label>
          <label>Consentimento<ReportsNativeSelect disabled={busy || data.client.role==='viewer'} value={selected.config?.consent_mode || 'auto'} onChange={event=>update({consent_mode:event.target.value})}><option value="auto">Automático</option><option value="manual">Integrado ao meu aviso</option></ReportsNativeSelect><small>{(selected.config?.consent_mode||'auto')==='manual'?'A Super Tag nunca mostra aviso. Informe a decisão com o evento cadu:consent.':'Lê o aviso de cookies do site (OneTrust, Cookiebot, Google Consent Mode e similares). Só mostra o aviso próprio se não encontrar nenhum.'}</small></label>
          <label className="reports-checkbox"><ReportsFieldInput type="checkbox" disabled={busy || data.client.role==='viewer'} checked={selected.config?.visibility_enabled !== false} onChange={event=>update({visibility_enabled:event.target.checked})} /><span>Medir visibilidade em elementos marcados<small>Registra quando um elemento marcado aparece na tela.</small></span></label></div>
        <div className="reports-tag-card"><div className="reports-tag-card-head"><div><strong>Associar visita a um usuário conhecido</strong><small>Chame após login ou confirmação do formulário, com consentimento concedido</small></div></div><code>{"window.CaduSuperTag?.identify({ name: usuario.nome, email: usuario.email });"}</code><small>Também aceita telefone. E-mail e telefone são protegidos por HMAC; valores de formulário nunca são lidos automaticamente. A associação expira conforme a retenção configurada.</small></div>
        {data.client.role!=='viewer' && !selected.revoked_at && <ReportsActionButton type="button" className="reports-danger-button" disabled={busy} onClick={() => setRevokeConfirmOpen(true)}>Revogar instalação</ReportsActionButton>}
          </article>}
          {selected&&siteTab==='overview'&&detail&&hasEvents && <div className="st-analytics">
      {hasEvents ? <div className="reports-supertag-analytics"><div className="reports-supertag-kpis"><Kpi label="Eventos · 30 dias" value={integer(detail.site.events_30d)} detail="Eventos aceitos pelo coletor" /><Kpi label="Páginas vistas" value={integer(kindTotal('page_view'))} detail="Após consentimento" /><Kpi label="Sessões conhecidas" value={integer(detail.known_sessions||0)} detail="Identificadas pelo site" /><Kpi label="Sessões encerradas" value={integer(detail.branding?.overall?.closed_sessions||0)} detail="Após 30 min sem eventos" /></div><BrandingInsights branding={detail.branding}/><article className="reports-panel reports-supertag-activity"><div className="reports-panel-head"><div><h2>Atividade por página</h2><p>Saída = última página de uma sessão encerrada</p></div><span>Últimos 30 dias</span></div>
        {detail.pages?.length ? <div className="reports-table-wrap"><table className="cadu-table"><thead><tr><th>Página</th><th>Visitas</th><th>Saídas</th><th>Tempo ativo médio</th><th>Formulários</th><th>Cliques</th><th>Conversões</th><th>Visibilidade</th><th>Rolagem</th></tr></thead><tbody>{detail.pages.map(item=><tr key={item.page_path}><td>{item.page_path}</td><td>{integer(item.views)}</td><td>{integer(item.exits)}</td><td>{item.avg_active_seconds==null?'—':`${decimal(item.avg_active_seconds)} s`}<small>{integer(item.measured_visits)} visitas medidas</small></td><td>{integer(item.form_submissions)}</td><td>{integer(item.clicks)}</td><td>{integer(item.conversions)}</td><td>{integer(item.visibility_events)}</td><td>{integer(item.scroll_events)}</td></tr>)}</tbody></table></div> : <Empty message="Os eventos aparecem depois de consentimento e da primeira visita." />}
      </article>
      <article className="reports-panel reports-supertag-journeys"><div className="reports-panel-head"><div><h2>Sessões e navegação</h2><p>Até 100 sessões recentes · páginas percorridas e saída</p></div><span>{integer(detail.sessions?.length||0)} sessões</span></div>
        {detail.sessions?.length ? <div className="reports-table-wrap"><table className="cadu-table"><thead><tr><th>Visitante</th><th>Campanha</th><th>Início</th><th>Navegação</th><th>Página de saída</th></tr></thead><tbody>{detail.sessions.map(item=>{const pages=(item.journey||[]).filter(event=>event.kind==='page_view'||event.kind==='conversion');return <tr key={item.session_id}><td>{item.known_name||'Anônimo'}{item.known_name&&<small>Conhecido</small>}</td><td>{item.campaign||'Sem campanha'}</td><td>{new Date(item.started_at).toLocaleString('pt-BR')}</td><td>{pages.length?pages.map((event,index)=><React.Fragment key={`${event.page}:${index}`}>{index>0?' → ':''}{event.page}</React.Fragment>):'—'}</td><td>{item.exit_page||'—'}</td></tr>;})}</tbody></table></div> : <Empty message="As sessões aparecem depois de consentimento e da primeira visita." />}
      </article>
      <article className="reports-panel reports-supertag-heatmap"><div className="reports-panel-head"><h2>Dados para mapas de interação</h2><span>{detail.heatmap?.length || 0} células agregadas</span></div><p>Cliques são agrupados em uma grade normalizada de 5% do viewport. Para mapas de visibilidade, marque os elementos com <code>data-cadu-track data-cadu-element="hero_cta"</code>. O código não lê texto nem valores de formulário.</p>
        {detail.heatmap?.length ? <div className="reports-table-wrap"><table className="cadu-table"><thead><tr><th>Tipo</th><th>Elemento</th><th>Grade normalizada</th><th>Ocorrências</th></tr></thead><tbody>{detail.heatmap.slice(0,30).map((item,index)=><tr key={`${item.event_kind}:${item.element_id}:${index}`}><td>{item.event_kind}</td><td>{item.element_id || '—'}</td><td>{item.x != null ? `${(Number(item.x)/10).toFixed(1)}–${Math.min(100,(Number(item.x)+49)/10).toFixed(1)}% × ${(Number(item.y)/10).toFixed(1)}–${Math.min(100,(Number(item.y)+49)/10).toFixed(1)}%` : item.ratio != null ? `${item.ratio}% visível` : item.depth != null ? `${item.depth}% rolagem` : '—'}</td><td>{integer(item.total)}</td></tr>)}</tbody></table></div> : <Empty message="Os agregados de cliques e visibilidade aparecerão com o tráfego consentido." />}
      </article></div> : null}
    </div>}
        </>}
      </main>
    </div>
    <ReportsDrawer open={installOpen} onOpenChange={setInstallOpen} onDiscard={()=>{setHost('');setLabel('Site principal');setSiteCheck(null);setError('');}} title="Nova instalação da Super Tag" description="Informe a página inicial para personalizar e testar a conexão." context={data.client.client_name}>
      <form className="reports-form" onSubmit={create}><label>URL do site<ReportsFieldInput required type="url" value={host} onChange={event=>{setHost(event.target.value);setSiteCheck(null);}} placeholder="https://www.exemplo.com.br" /></label><ReportsActionButton type="button" className="reports-secondary-button" disabled={!host.trim()||checkingSite} onClick={checkSite}>{checkingSite?'Verificando site…':'Verificar site'}</ReportsActionButton>{siteCheck && <div className={`reports-site-preview${siteCheck.error?' has-error':''}`}><span className="reports-site-favicon">{siteCheck.favicon?<img src={siteCheck.favicon} alt=""/>:'◎'}</span><div><strong>{siteCheck.title||siteCheck.host||'Site encontrado'}</strong><small>{siteCheck.host}{siteCheck.status?` · Respondeu com HTTP ${siteCheck.status}`:''}</small></div>{!siteCheck.error&&<b>Ping concluído</b>}{siteCheck.error&&<p role="alert">{siteCheck.error}</p>}</div>}{error && <p className="reports-error" role="alert">{error}</p>}<label>Nome desta instalação<ReportsFieldInput required maxLength="120" value={label} onChange={event=>setLabel(event.target.value)} placeholder={siteCheck?.title||'Site principal'} /></label><p className="reports-info">A Super Tag verifica o domínio usando o servidor Python, identifica o título e favicon e confirma que o site responde. Eventos só serão coletados após consentimento.</p><div className="reports-modal-actions"><ReportsActionButton type="submit" className="reports-primary-button" disabled={busy||!siteCheck||Boolean(siteCheck.error)}>{busy?'Criando…':'Criar instalação'}</ReportsActionButton></div></form>
    </ReportsDrawer>
    <ReportsConfirmDialog open={revokeConfirmOpen} title="Revogar Super Tag" description="A coleta neste domínio será interrompida. Os dados já recebidos permanecem no Reports." confirmLabel="Revogar instalação" busy={busy} onCancel={() => setRevokeConfirmOpen(false)} onConfirm={revoke} />
  </section>;
}

const reportIcons = {overview:'home', media:'analysis', journey:'branch', reports:'file', alerts:'alert', 'data-sources':'plugin', supertag:'pulse', events:'calendar', imports:'download', links:'link', customers:'users', accounts:'table', access:'folder'};
const NAV_GROUPS = [
  ['', [['overview', 'Visão geral', 'overview']]],
  ['Análise', [['media', 'Mídia', 'media'], ['journey', 'Site & Jornada', 'journey'], ['reports', 'Relatórios', 'reports'], ['alerts', 'Alertas', 'alerts']]],
  ['Dados', [['data-sources', 'Fontes de dados', 'data-sources'], ['supertag', 'Super Tag', 'supertag'], ['events', 'Eventos', 'events'], ['imports', 'Importações', 'imports']]],
  ['Ferramentas', [['links', 'Link Tester', 'tools/link-tester']]],
  ['Configurações', [['accounts', 'Clientes e contas', 'settings/accounts'], ['access', 'Acessos', 'settings/access']]],
];

// Sections that older links addressed as #section?params.
const LEGACY_HASHES = new Set(['overview', 'customers', 'accounts', 'campaigns', 'reports', 'imports', 'monitor', 'supertag', 'flow', 'flows', 'pages', 'alerts', 'events', 'conversions', 'links', 'access', 'data-library']);

function App() {
  const locationKey = useLocationKey();
  const route = useMemo(() => resolveRoute(), [locationKey]);
  const pageSection = route.page;
  const [data, setData] = useState(null);
  const isFlowEditor = Boolean(flowEditorId())&&(!/\/monitor\/?$/.test(location.pathname)||Boolean(data?.features?.flows_workspace_v2));
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [period, setPeriodState] = useState(readPeriod);
  const setPeriod = range => {setPeriodState(range); writePeriod(range);};
  // Platform/account/campaign filters stay per page; the period is one for the whole app.
  const [filtersByPage, setFiltersByPage] = useState({});
  const filters = {...REPORT_FILTER_DEFAULTS, ...(filtersByPage[pageSection] || {}), ...periodFilters(period)};
  const updateFilters = ({period: preset, startDate, endDate, ...changes}) => {
    if (startDate && endDate) setPeriod({start: startDate, end: endDate});
    if (Object.keys(changes).length) setFiltersByPage(current => ({...current, [pageSection]: {...(current[pageSection] || {}), ...changes}}));
  };
  const [refreshRevision, setRefreshRevision] = useState(0);
  const load = async (clientId = new URLSearchParams(location.search).get('client_id')) => {
    try {
      const body = await json(`/connect/api/v2/reports/bootstrap${clientId ? `?client_id=${encodeURIComponent(clientId)}` : ''}`);
      setActiveClient(body.client?.client_id);
      setData(body); setError(''); dropClientFromUrl();
    } catch (failure) {setError(failure.message);}
  };
  /** Changes the analysed client in place: same page, same period, data reloaded. */
  const switchClient = async clientId => {
    if (String(clientId) === String(data?.client?.client_id)) return;
    setFiltersByPage({});
    await load(clientId);
  };
  useEffect(() => {
    const legacySection = location.hash.slice(1).split('?')[0];
    if (LEGACY_HASHES.has(legacySection)) {
      const legacyParams = Object.fromEntries(new URLSearchParams(location.hash.split('?')[1] || ''));
      location.replace(reportUrl(legacySection, legacyParams));
      return undefined;
    }
    const syncRoute = () => {
      applyLegacyRedirect();
      const query = new URLSearchParams(location.search);
      // Links between pages don't carry the period; keep the current one in the new URL.
      if (['period', 'days', 'start_date', 'end_date'].some(key => query.has(key))) setPeriodState(readPeriod());
      else setPeriodState(current => {writePeriod(current); return current;});
      window.scrollTo(0, 0);
    };
    load();
    syncRoute();
    addEventListener('popstate', syncRoute);
    return () => {removeEventListener('popstate', syncRoute);};
  }, []);
  const save = async (path, payload, reload = true, method = 'POST') => {
    setBusy(true); setError('');
    try {
      const result = await json(`/connect/api/v2/reports${path}`, {method, headers: {'Content-Type': 'application/json', 'X-CSRF-Token': data.csrf}, body: JSON.stringify({...payload, client_id: data.client.client_id})});
      if (reload) await load(data.client.client_id);
      return result;
    } catch (failure) {if(!path.startsWith('/flow/'))setError(failure.message); throw failure;} finally {setBusy(false);}
  };
  const groups = NAV_GROUPS.map(([label, items]) => ({label, items: items
    .filter(([id]) => id !== 'access' || data?.can_manage_access)
    .map(([id, title, path]) => ({id, label: title, icon: reportIcons[id], href: `${APP_BASE}/${path}`}))}));
  const solutionUrls={workspace:rootElement.dataset.workspaceUrl,planner:rootElement.dataset.plannerUrl,studio:rootElement.dataset.studioUrl,connect:location.pathname+location.search,skills:rootElement.dataset.skillsUrl};
  const solutionIcons={workspace:'/static/images/cadu/products/cadu-icon.png',planner:'/static/images/cadu/products/planner-icon.png',studio:'/static/images/cadu/products/studio-icon.png',connect:'/static/images/cadu/products/connect-icon.png',skills:'/static/images/cadu/products/skills-icon.png'};
  const onRefresh = () => {setRefreshRevision(value => value + 1); load(data?.client?.client_id);};
  const context = useMemo(() => ({period, setPeriod, switchClient}), [period, data?.client?.client_id]);
  if(data?.shared)return <SharedReports key={data.client.client_id} data={data}/>;
  const hub = route.hub ? HUBS[route.hub] : null;
  const library = pageSection === 'imports' && new URLSearchParams(location.search).get('view') === 'library';
  const header = hub ? {title: hub.title, description: hub.description, tabs: hub.tabs}
    : {title: library ? 'Biblioteca de dados' : route.title, description: library ? 'Campos personalizados e dados preservados dos arquivos importados.' : route.description};
  const showFilterBar = data?.ready && !isFlowEditor && (pageSection === 'campaigns' && !route.entity && !new URLSearchParams(location.search).get('campaign_id')
    || pageSection === 'events' || (pageSection === 'flow' && new URLSearchParams(location.search).get('flow_view') === 'monitor'));
  const clientKey = data?.client?.client_id;
  const page = !data ? <LoadingState rows={4} label="Carregando Reports…"/>
    : !data.ready ? <Empty message="A base de Reports V1 ainda precisa da migração de dados." />
    : {
      overview: () => <Overview data={data}/>,
      media: () => <MediaOverview data={data}/>,
      campaigns: () => <Campaigns data={data} save={save} busy={busy} filters={filters} refreshRevision={refreshRevision} />,
      'google-ads': () => <GoogleAds data={data}/>,
      creatives: () => <MediaCreatives data={data}/>,
      content: () => <Contents/>,
      monitor: () => <MediaData data={data} save={save} busy={busy}/>,
      journey: () => <JourneyOverview data={data}/>,
      flow: () => <Flow data={data} save={save} busy={busy} filters={filters} refreshRevision={refreshRevision} />,
      pages: () => <PageDetail data={data} />,
      navigation: () => <Navigation/>,
      conversions: () => <Conversions/>,
      reports: () => <ReportsLibrary data={data} save={save} busy={busy}/>,
      alerts: () => <AlertsCenter data={data} />,
      'data-sources': () => <DataSources data={data}/>,
      supertag: () => <SuperTag data={data} />,
      events: () => <EventsPage data={data} filters={filters} refreshRevision={refreshRevision} />,
      imports: () => <ImportsPage data={data} reloadBootstrap={() => load(data.client.client_id)} focusLibrary={library} />,
      links: () => <LinkTester data={data} save={save} busy={busy}/>,
      accounts: () => <ClientsAccounts data={data} save={save} busy={busy} reload={() => load(data.client.client_id)}/>,
      access: () => data.can_manage_access ? <AccessPage data={data} save={save} busy={busy}/> : <Empty message="Seu acesso não permite administrar usuários do Reports neste cliente." />,
    }[pageSection]();
  return <ReportsContext.Provider value={context}><div data-cadu-skin="reports" className={`reports-shell reports-shell--${pageSection}${isFlowEditor?' reports-shell--flow-editor':''}`}>
    {!isFlowEditor && <SolutionSidebar solution="Reports" userName={rootElement.dataset.userName||'Minha conta'} accountLabel={rootElement.dataset.agencyName||'Agência'} userAvatar={rootElement.dataset.userAvatar||''} creditsUrl={rootElement.dataset.creditsUrl} profileUrl={rootElement.dataset.profileUrl} accent="#175cd3" storageKey="reports-sidebar" active={route.nav} activeSolutionId="connect" solutionLogo={solutionIcons.connect} solutionUrls={solutionUrls} solutionIcons={solutionIcons} groups={groups} onNavigate={navigateOnClick} />}
    <main className="reports-main">
      <>
          {data && !isFlowEditor && <PageHeader {...header} activeTab={route.path}
            context={<ContextSelector clients={data.clients} client={data.client} showPeriod={Boolean(route.period) && !(pageSection === 'pages' && new URLSearchParams(location.search).get('site_id'))}/>}/>}
          {showFilterBar && <ReportsFilterBar data={data} filters={filters} onChange={updateFilters} onRefresh={onRefresh} />}
          <div className="reports-content">{error && <div className="reports-error" role="alert">{error}</div>}<React.Fragment key={`${clientKey}:${route.path}`}>{page}</React.Fragment></div>
      </>
    </main>
  </div></ReportsContext.Provider>;
}

class ReportsErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = {failed: false};
  }

  static getDerivedStateFromError() {
    return {failed: true};
  }

  componentDidCatch(error) {
    console.error('Reports render failed:', error);
  }

  render() {
    if (this.state.failed) return <main className="reports-content" role="alert">
      <div className="reports-error">Não foi possível exibir o Reports. Atualize a página para tentar novamente.</div>
    </main>;
    return this.props.children;
  }
}

createRoot(rootElement).render(<ReportsErrorBoundary><App /></ReportsErrorBoundary>);
