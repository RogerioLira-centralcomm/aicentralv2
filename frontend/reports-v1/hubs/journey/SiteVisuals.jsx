import React, {useMemo, useState} from 'react';
import {PageVisual} from '../../PageDetail.jsx';
import {ReportsNativeSelect} from '../../ReportsNativeSelect.jsx';
import {ReportsTabs} from '../../ReportsTabs.jsx';
import {periodDays, useReportsContext} from '../../shell/context.js';
import {apiUrl, useApi} from '../../shell/useApi.js';
import {EmptyState, Section} from '../../shell/primitives.jsx';

const WINDOWS = [7, 14, 30, 60, 90];
const DEVICES = [['desktop', 'Computador'], ['mobile', 'Celular']];

/** The selected site as people see it: desktop and mobile screenshots with the click or scroll heat on top. */
export function SiteVisuals({data, pages, sites}) {
  const {period, scope} = useReportsContext();
  const site = sites.find(item => item.id === scope.site);
  const options = useMemo(() => pages.filter(item => item.site_id === scope.site).sort((a, b) => b.views - a.views).slice(0, 30), [pages, scope.site]);
  const [chosen, setChosen] = useState('');
  const [mode, setMode] = useState('clicks');
  // The chosen page only counts while it belongs to this site; otherwise the home page, or the most viewed one.
  const path = options.some(item => item.path === chosen) ? chosen : options.find(item => item.path === '/')?.path || options[0]?.path || '/';
  const target = periodDays(period);
  const days = WINDOWS.reduce((best, item) => Math.abs(item - target) < Math.abs(best - target) ? item : best, 30);
  const [overview] = useApi(site ? apiUrl('/pages/overview', {site_id: site.id, path, days}) : '');
  if (!site) return <Section title="Site em imagens" description="Captura de celular e computador com mapa de calor">
    <EmptyState title="Escolha um site" description="Selecione o site no topo da página para ver como ele aparece em cada dispositivo e onde as pessoas clicam e rolam."/>
  </Section>;
  return <Section title="Site em imagens" description={`${site.allowed_host || site.label} · janela de ${days} dias`}
    action={<div className="rs-toolbar">
      <label className="rs-search"><span className="reports-sr-only">Página</span>
        <ReportsNativeSelect value={path} onChange={event => setChosen(event.target.value)} aria-label="Página">
          {(options.some(item => item.path === path) ? options : [{path}, ...options]).map(item => <option key={item.path} value={item.path}>{item.path}</option>)}
        </ReportsNativeSelect></label>
      <ReportsTabs label="Camada do calor" value={mode} onChange={setMode} items={[{id: 'clicks', label: 'Cliques'}, {id: 'scroll', label: 'Visualização (rolagem)'}]}/>
    </div>}>
    <div className="rs-grid rs-grid--2">
      {DEVICES.map(([device, label]) => <div key={device}><h3>{label}</h3>
        <PageVisual siteId={site.id} path={path} device={device} days={days} metrics={overview.body?.metrics} mode={mode}
          canEdit={data.client.role !== 'viewer'} client={data.client.client_id} csrf={data.csrf}/></div>)}
    </div>
  </Section>;
}
