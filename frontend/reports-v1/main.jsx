import {Flow} from './FlowsPage.jsx';
import {ImportsPage} from './ImportsPage.jsx';
import {MediaData} from './MediaData.jsx';
import {AccessPage} from './AccessPage.jsx';
import {LinkTester} from './LinkTester.jsx';
import {EventsPage} from './EventsPage.jsx';
import {ReportsLibrary} from './ReportsLibrary.jsx';
import {CampaignDetail} from './CampaignDetail.jsx';
import {SuperTagPage} from './SuperTagPage.jsx';
import {CAMPAIGN_STATUS, ClientsAccounts, Status as CampaignStatus, channelLabel} from './ClientsAccounts.jsx';
import {UnlinkedGoogleCampaigns} from './GoogleCampaignLinks.jsx';
import {SharedReports} from './SharedReports.jsx';
import React, {useEffect, useMemo, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {SolutionSidebar} from '../cadu-design-system/components/SolutionSidebar.jsx';
import {Button as UntitledButton} from '../cadu-design-system/untitled-kit/button.tsx';
import {PageDetail} from './PageDetail.jsx';
import {AlertsCenter} from './AlertsCenter.jsx';
import {REPORT_FILTER_DEFAULTS, ReportsFilterBar} from './PageChrome.jsx';
import {APP_BASE, HUBS, applyLegacyRedirect, navigateOnClick, resolveRoute, useLocationKey} from './shell/routes.js';
import {ReportsContext, periodFilters, readPeriod, readSavedScope, readScope, initialScope, initialSite, saveScope, writePeriod, writeScope} from './shell/context.js';
import {ContextSelector, PageHeader} from './shell/PageHeader.jsx';
import {LoadingState} from './shell/primitives.jsx';
import {apiUrl, setActiveClient, useApi} from './shell/useApi.js';
import {platformName} from './shell/media.jsx';
import {Overview} from './hubs/overview/Overview.jsx';
import {MediaOverview} from './hubs/media/MediaOverview.jsx';
import {GoogleAds} from './hubs/media/GoogleAds.jsx';
import {MediaCreatives} from './hubs/media/MediaCreatives.jsx';
import {Contents} from './hubs/journey/Contents.jsx';
import {JourneyOverview} from './hubs/journey/JourneyOverview.jsx';
import {Navigation} from './hubs/journey/Navigation.jsx';
import {Conversions} from './hubs/journey/Conversions.jsx';
import {Heatmap} from './hubs/journey/Heatmap.jsx';
import {DataSources} from './hubs/data-sources/DataSources.jsx';
import {dropClientFromUrl, flowEditorId, reportUrl, json, Empty} from './reportsCommon.jsx';
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






const campaignIdFromUrl = () => resolveRoute().entity || new URLSearchParams(location.search).get('campaign_id') || '';

function Campaigns({data, save, busy, filters, refreshRevision}) {
  const [campaignId, setCampaignId] = useState(campaignIdFromUrl);
  const [campaignDetail, setCampaignDetail] = useState(null);
  const [detailError, setDetailError] = useState('');
  const [tab, setTab] = useState(() => {
    const current = new URLSearchParams(location.search).get('campaign_tab') || 'overview';
    return current === 'metrics' ? 'performance' : current;
  });
  const visibleCampaigns = data.campaigns.filter(item => {
    if (filters.platform && item.platform !== filters.platform) return false;
    if (filters.account && String(item.account_id) !== filters.account) return false;
    if (filters.campaign && String(item.id) !== filters.campaign) return false;
    if (filters.tags && !(item.tags || []).includes(filters.tags)) return false;
    return true;
  });
  useEffect(() => {
    let live = true;
    if (!campaignId) {setCampaignDetail(null); return () => {live=false;};}
    json(`/connect/api/v2/reports/campaigns/${campaignId}`)
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
  return <section className="reports-campaigns-page reports-campaigns-list-page">
    <UnlinkedGoogleCampaigns save={save} busy={busy} clientId={data.client.client_id} revision={refreshRevision}/>
    <article className="reports-panel">
    <div className="reports-panel-head"><div><h2>Campanhas <small>{visibleCampaigns.length} de {data.campaigns.length}</small></h2><p>Abra uma campanha para ver desempenho, criativos e jornada.</p></div>
      <UntitledButton size="sm" color="secondary" href={`${APP_BASE}/settings/accounts`}>Gerenciar em Clientes e contas</UntitledButton></div>
    {visibleCampaigns.length ? <div className="reports-table-wrap"><table className="cadu-table"><thead><tr><th>Campanha</th><th>Conta</th><th>Tipo</th><th>Tags</th><th>Status</th></tr></thead><tbody>{visibleCampaigns.map(item => <tr key={item.id}>
      <td><a className="reports-campaign-link" href={campaignUrl({id: item.id}).pathname} onClick={event => {event.preventDefault(); openCampaign(item);}}><strong>{item.name}</strong><small>{item.external_id ? `ID ${item.external_id}` : 'Campanha manual'}</small></a></td>
      <td><span className="reports-cell-stack"><span>{item.account_name || 'Sem conta de mídia'}</span><small>{platformName(item.platform)}</small></span></td>
      <td>{channelLabel(item.channel_type || item.objective) || '—'}</td>
      <td><div style={{display: 'flex', gap: '4px', flexWrap: 'wrap'}}>{(item.tags || []).map(tag => <span key={tag} style={{display: 'inline-flex', alignItems: 'center', padding: '2px 8px', fontSize: '12px', backgroundColor: '#f0f0f0', borderRadius: '4px', color: '#666'}}>{tag}</span>)}</div></td>
      <td><CampaignStatus map={CAMPAIGN_STATUS} value={item.status}/></td></tr>)}</tbody></table></div>
      : <Empty message={data.campaigns.length ? 'Nenhuma campanha corresponde aos filtros desta página.' : 'Nenhuma campanha ainda. Cadastre em Clientes e contas ou sincronize uma conta de mídia.'} />}
  </article></section>;
}

const reportIcons = {overview:'home', media:'analysis', journey:'branch', reports:'file', alerts:'alert', 'data-sources':'plugin', supertag:'pulse', events:'calendar', imports:'download', links:'link', customers:'users', accounts:'table', access:'folder'};
const NAV_GROUPS = [
  ['', [['overview', 'Visão geral', 'overview']]],
  ['Análise', [['media', 'Mídia', 'media'], ['journey', 'Site & Jornada', 'journey'], ['reports', 'Relatórios', 'reports'], ['alerts', 'Alertas', 'alerts']]],
  ['Dados', [['data-sources', 'Fontes de dados', 'data-sources']]],
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
  const [scope, setScopeState] = useState(readScope);
  const setScope = next => {setScopeState(next); if (data?.client?.client_id) saveScope(data.client.client_id, next);};
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
    setScopeState({account: '', campaign: '', site: ''});
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
      const result = await json(`/connect/api/v2/reports${path}`, {method, headers: {'Content-Type': 'application/json', 'X-CSRF-Token': data.csrf}, body: JSON.stringify({...payload})});
      if (reload) await load(data.client.client_id);
      return result;
    } catch (failure) {if(!path.startsWith('/flow/'))setError(failure.message); throw failure;} finally {setBusy(false);}
  };
  const groups = NAV_GROUPS.map(([label, items]) => ({label, items: items
    .filter(([id]) => id !== 'access' || data?.can_manage_access)
    .map(([id, title, path]) => ({id, label: title, icon: reportIcons[id], href: `${APP_BASE}/${path}`}))}));
  const solutionUrls={workspace:rootElement.dataset.workspaceUrl,planner:rootElement.dataset.plannerUrl,studio:rootElement.dataset.studioUrl,connect:location.pathname+location.search,skills:rootElement.dataset.skillsUrl};
  const solutionIcons={workspace:'/static/images/cadu/products/cadu-icon.png',planner:'/static/images/cadu/products/planner-icon.png',studio:'/static/images/cadu/products/studio-icon.png',connect:'/static/images/cadu/products/connect-icon.png',skills:'/static/images/cadu/products/skills-icon.png'};
  // Once a client's data is in: reopen the last source/campaign used, or the only one there is.
  useEffect(() => {
    if (!data?.ready || !data.client?.client_id) return;
    const next = initialScope({urlScope: readScope(), saved: readSavedScope(data.client.client_id), accounts: data.accounts || [], campaigns: data.campaigns || []});
    setScopeState(current => ({...next, site: current.site}));
  }, [data?.client?.client_id, data?.ready]);
  const siteRoute = Boolean(data?.ready) && route.scope === 'site';
  const [siteList] = useApi(siteRoute ? apiUrl('/supertag/sites', {for_client: data?.client?.client_id}) : '');
  const sites = (siteList.body?.sites || []).filter(item => !item.revoked_at);
  useEffect(() => {
    if (!siteList.body) return;
    // Old Super Tag links carry the site in the path (/supertag/sites/<id>); the header picker takes it from there.
    const site = initialSite({urlSite: readScope().site || (route.page === 'supertag' ? route.entity : ''), savedSite: readSavedScope(data.client.client_id)?.site, sites});
    setScopeState(current => ({...current, site}));
  }, [siteList.body]);
  // Screens that always show one site (Super Tag) open on the busiest one when nothing was chosen yet.
  // Functional update: the site picked above (URL, old path or saved) in the same pass wins over this fallback.
  useEffect(() => {
    if (!route.siteRequired || scope.site || !sites.length) return;
    const busiest = (sites.find(item => Number(item.events_30d) > 0) || sites[0]).id;
    setScopeState(current => current.site ? current : {...current, site: busiest});
  }, [route.path, siteList.body, scope.site]);
  // In-app links that carry ?scope_site= (alerts, overview) pick that site; read it before the URL is rewritten below.
  useEffect(() => {
    const urlSite = readScope().site;
    if (route.scope === 'site' && urlSite && urlSite !== scope.site) setScopeState(current => ({...current, site: urlSite}));
  }, [locationKey]);
  // The selection lives in the address only on the screens it applies to, so shared links keep it and other pages stay clean.
  useEffect(() => {
    if (!data?.ready) return;
    writeScope(route.scope === true ? {account: scope.account, campaign: scope.campaign, site: ''}
      : route.scope === 'account' ? {account: scope.account, campaign: '', site: ''}
      : route.scope === 'site' ? {account: '', campaign: '', site: scope.site} : {account: '', campaign: '', site: ''});
  }, [scope, locationKey, data?.ready]);
  // Source and campaign lists follow the page: Google Ads lists what its scripts saw (registered or not),
  // the other Mídia pages list registered campaigns. Managers (MCC) hold no metrics, so they are never a source.
  const googleRoute = route.path === 'media/google-ads';
  const [googleScope] = useApi(googleRoute && data?.ready ? apiUrl('/google-ads/scope', {client_id: data?.client?.client_id}) : '');
  const scopeAccounts = googleRoute ? (googleScope.body?.accounts || []) : (data?.accounts || []).filter(item => item.account_kind !== 'manager');
  const scopeCampaigns = googleRoute ? (googleScope.body?.campaigns || []) : (data?.campaigns || []);
  // A choice made on one page is carried to the other: map it to the same campaign there, or clear it when there is none.
  useEffect(() => {
    if (!data?.ready || route.scope !== true || (googleRoute && !googleScope.body)) return;
    const composite = /^\d+:\d+$/.test(scope.campaign);
    let next = scope;
    if (googleRoute && scope.campaign && !composite) {
      const known = (data.campaigns || []).find(item => String(item.id) === scope.campaign);
      const target = known && known.account_id ? `${known.account_id}:${known.external_id}` : '';
      next = {...scope, account: target ? String(known.account_id) : '', campaign: target};
    } else if (!googleRoute && composite) {
      const linked = scopeCampaigns.find(item => String(item.id) === scope.campaign);
      next = {...scope, campaign: linked ? String(linked.id) : ''};
      if (!linked) next.account = scope.account;
    }
    const accountOk = !next.account || scopeAccounts.some(item => String(item.id) === next.account);
    const campaignOk = !next.campaign || scopeCampaigns.some(item => String(item.id) === next.campaign);
    if (!accountOk || !campaignOk) next = {...next, account: accountOk ? next.account : '', campaign: ''};
    if (next.account !== scope.account || next.campaign !== scope.campaign) setScope(next);
  }, [route.path, scope.account, scope.campaign, data?.ready, googleScope.body, data?.campaigns]);
  const onRefresh = () => {setRefreshRevision(value => value + 1); load(data?.client?.client_id);};
  const context = useMemo(() => ({period, setPeriod, switchClient, scope, setScope}), [period, scope, data?.client?.client_id]);
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
      heatmap: () => <Heatmap data={data}/>,
      reports: () => <ReportsLibrary data={data} save={save} busy={busy}/>,
      alerts: () => <AlertsCenter data={data} />,
      'data-sources': () => <DataSources data={data}/>,
      supertag: () => <SuperTagPage data={data}/>,
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
            context={<ContextSelector clients={data.clients} client={data.client} accounts={route.scope === true || route.scope === 'account' ? scopeAccounts : undefined} campaigns={route.scope === true ? scopeCampaigns : undefined} sites={route.scope === 'site' ? sites : undefined} siteRequired={Boolean(route.siteRequired)} alwaysClient={route.page === 'overview' || route.hub === 'data'} showPeriod={Boolean(route.period) && !(pageSection === 'pages' && new URLSearchParams(location.search).get('site_id'))}/>}/>}
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
