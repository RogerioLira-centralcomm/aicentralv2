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
import {SharedReports} from './SharedReports.jsx';
import React, {useEffect, useMemo, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {SolutionSidebar} from '../cadu-design-system/components/SolutionSidebar.jsx';
import {Button as UntitledButton} from '../cadu-design-system/untitled-kit/button.tsx';
import {PageDetail} from './PageDetail.jsx';
import {AlertsCenter} from './AlertsCenter.jsx';
import {REPORT_FILTER_DEFAULTS, ReportsFilterBar} from './PageChrome.jsx';
import {APP_BASE, HUBS, applyLegacyRedirect, navigateOnClick, resolveRoute, useLocationKey} from './shell/routes.js';
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
