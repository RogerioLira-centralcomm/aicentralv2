import React, {useCallback, useEffect, useMemo, useState} from 'react';
import {createRoot} from 'react-dom/client';
import '../cadu-design-system/tokens.css';
import '../cadu-design-system/primitives.css';
import './planner.css';
import {SolutionSidebar} from '../cadu-design-system/components/SolutionSidebar.jsx';
import {CatalogDetail, CatalogPage} from './Catalog.jsx';
import {ContextSelector, PlannerChrome} from './PlannerHeader.jsx';
import {AudienceShowcase} from './AudienceShowcase.jsx';
import {FormatShowcase} from './FormatShowcase.jsx';
import {AudienceDetail} from './details/AudienceDetail.jsx';
import {ChannelDetail} from './details/ChannelDetail.jsx';
import {FormatDetail} from './details/FormatDetail.jsx';
import {PlaceDetail} from './details/PlaceDetail.jsx';
import {PortalDetail} from './details/PortalDetail.jsx';
import {RadarPage} from './Radar.jsx';
import {RadarListPage} from './RadarList.jsx';
import {DocsPage} from './Docs.jsx';
import {MonitorPage} from './monitoring.jsx';
import {PlanDetail} from './PlanDetail.jsx';
import {PlanCreatePage, PlannerHome, PlansPage} from './PlansPages.jsx';
import {PlanDock} from './PlanDock.jsx';
import {PlannerNotice, usePlanSelection} from './PlannerUi.jsx';
import {PublicDoc, PublicPlan} from './PublicViews.jsx';
import {CATALOG_KINDS, createPlannerApi, moduleUrl, newPlanUrl} from './api.js';

const PUBLIC_VIEWS = new Set(['public-plan', 'public-doc']);
const SOLUTION_ICONS = {
  workspace: '/static/images/cadu/products/cadu-icon.png', planner: '/static/images/cadu/products/planner-icon.png',
  studio: '/static/images/cadu/products/studio-icon.png', connect: '/static/images/cadu/products/connect-icon.png',
  skills: '/static/images/cadu/products/skills-icon.png',
};

function sidebarGroups(urls) {
  const item = (id, label, icon, href) => ({id, label, icon, href: href || moduleUrl(urls, id)});
  return [
    {label: '', items: [item('inicio', 'Início', 'home')]},
    {label: 'Planejamento', items: [item('novo-plano', 'Novo planejamento', 'plus', newPlanUrl(urls)), item('planos', 'Planos', 'history')]},
    {label: 'Oportunidades', items: [item('radar', 'Novo radar', 'pulse'), item('radares', 'Meus radares', 'history')]},
    {label: 'Descobrir', items: [item('canais', 'Canais', 'share'), item('audiencias', 'Audiências', 'users'), item('formatos', 'Formatos', 'table'), item('interativos', 'Interativos', 'plugin'), item('portais', 'Portais e veículos', 'library'), item('places', 'Locais', 'browser')]},
    // Docs and "Sites e funis" are legacy tools: reachable by URL, not part of the Planner flow.
  ];
}

function App({boot}) {
  const request = useMemo(() => createPlannerApi(boot.csrf), [boot.csrf]);
  const [notice, setNotice] = useState(null);
  const notify = useCallback(next => setNotice(next), []);
  const [plan, setPlan] = useState(boot.plan || null);
  // The server renders plans with the home's progress details; no second fetch.
  const plans = ['inicio', 'planos'].includes(boot.module) && Array.isArray(boot.records) ? boot.records : [];
  const creating = boot.module === 'planos' && boot.view === 'page' && new URLSearchParams(window.location.search).get('create') === '1';
  const publicView = PUBLIC_VIEWS.has(boot.view);
  const selection = usePlanSelection(request, plan, setPlan, notify, !publicView);
  const [context, setContext] = useState({brand_ref: boot.contextBar?.brand_ref || '', project_ref: boot.contextBar?.project_ref || ''});
  // Catalog pages add to the open plan; the plan page itself does not need the chip.
  const chrome = useMemo(() => ({
    urls: boot.urls,
    activePlan: boot.view !== 'plan-detail' && CATALOG_KINDS.includes(boot.module) ? plan : null,
    contextNode: publicView ? null : <ContextSelector boot={boot} notify={notify} onChange={setContext}/>,
  }), [boot, plan, publicView, notify]);

  // Success messages fade on their own; errors wait for the person.
  useEffect(() => {
    if (!notice || notice.tone === 'error') return undefined;
    const timer = window.setTimeout(() => setNotice(null), 4000);
    return () => window.clearTimeout(timer);
  }, [notice]);

  const view = (() => {
    if (boot.view === 'public-plan') return <PublicPlan plan={plan}/>;
    if (boot.view === 'public-doc') return <PublicDoc document={boot.document}/>;
    if (boot.view === 'plan-detail') return <PlanDetail boot={boot} request={request} plan={plan} setPlan={setPlan} selection={selection} notify={notify}/>;
    if (boot.view === 'channel-detail') return <ChannelDetail boot={boot} selection={selection} plan={plan}/>;
    if (boot.view === 'audience-detail') return <AudienceDetail boot={boot} selection={selection} plan={plan}/>;
    if (boot.view === 'format-detail') return <FormatDetail boot={boot} selection={selection} plan={plan}/>;
    if (boot.view === 'catalog-detail' && boot.module === 'places') return <PlaceDetail boot={boot} selection={selection} plan={plan}/>;
    if (boot.view === 'catalog-detail' && boot.module === 'portais') return <PortalDetail boot={boot} selection={selection} plan={plan}/>;
    if (boot.view === 'catalog-detail') return <CatalogDetail boot={boot} selection={selection}/>;
    if (creating) return <PlanCreatePage boot={boot} request={request} notify={notify} selection={context}/>;
    if (boot.module === 'radares') return <RadarListPage boot={boot} request={request} notify={notify}/>;
    if (boot.module === 'radar') return <RadarPage boot={boot} request={request} notify={notify} context={context}/>;
    if (boot.module === 'inicio') return <PlannerHome boot={boot} plans={plans}/>;
    if (boot.module === 'planos') return <PlansPage boot={boot} plans={plans}/>;
    if (boot.module === 'monitoramento') return <MonitorPage request={request}/>;
    if (boot.module === 'docs') return <DocsPage boot={boot} request={request} notify={notify}/>;
    if (boot.module === 'audiencias') return <AudienceShowcase boot={boot} request={request} selection={selection} notify={notify}/>;
    if (boot.module === 'formatos' || boot.module === 'interativos') return <FormatShowcase boot={boot} selection={selection}/>;
    if (CATALOG_KINDS.includes(boot.module)) return <CatalogPage boot={boot} request={request} selection={selection} notify={notify}/>;
    return null;
  })();

  const dockViews = ['channel-detail', 'audience-detail', 'format-detail', 'catalog-detail'];
  const showDock = !publicView && !creating && (dockViews.includes(boot.view) || (boot.view === 'page' && (CATALOG_KINDS.includes(boot.module) || ['audiencias', 'formatos', 'interativos'].includes(boot.module))));
  const active = creating ? 'novo-plano' : boot.module;
  const urls = boot.urls;
  return <div className={`planner-shell${publicView ? ' is-public' : ''}`}>
    {!publicView && <SolutionSidebar solution="Planner" accent="var(--cadu-accent)" storageKey="planner-sidebar" active={active} autoCollapse={boot.view === 'plan-detail'}
      activeSolutionId="planner" solutionLogo={SOLUTION_ICONS.planner} solutionIcons={SOLUTION_ICONS}
      solutionUrls={{workspace: urls.workspace, planner: urls.home, studio: urls.studio, connect: urls.reports, skills: urls.skills}}
      groups={sidebarGroups(urls)} userName={boot.user?.name || 'Minha conta'} accountLabel={boot.clientName || undefined}
      userAvatar={boot.user?.avatar || ''} creditsUrl={urls.credits} profileUrl={urls.profile}/>}
    <main className={`planner-main${boot.view === 'page' && CATALOG_KINDS.includes(boot.module) ? ' is-shelf' : ''}`} id="content">
      <PlannerNotice notice={notice} onDismiss={() => setNotice(null)}/>
      <PlannerChrome.Provider value={chrome}>{view}</PlannerChrome.Provider>
      {showDock && <PlanDock boot={boot} request={request} plan={plan} setPlan={setPlan} selection={selection} notify={notify}/>}
    </main>
  </div>;
}

const root = document.getElementById('planner-root');
if (root) {
  const node = document.getElementById('planner-bootstrap');
  createRoot(root).render(<App boot={JSON.parse(node?.textContent || '{}')}/>);
}
