import React, {useState} from 'react';
import {PageVisual} from '../../PageDetail.jsx';
import {ReportsTabs} from '../../ReportsTabs.jsx';
import {periodDays, useReportsContext} from '../../shell/context.js';
import {apiUrl, useApi} from '../../shell/useApi.js';
import {Async, EmptyState, Section} from '../../shell/primitives.jsx';
import {number} from '../shared.jsx';
import './journey.css';

const WINDOWS = [7, 14, 30, 60, 90];
// Celular groups phones and tablets (viewport < 1024 px) over the phone capture; Computador is >= 1024 px.
const DEVICES = [{id: 'desktop', label: 'Computador', heat: 'desktop'}, {id: 'mobile', label: 'Celular', heat: 'handheld'}];
const LAYERS = [{id: 'clicks', label: 'Cliques'}, {id: 'scroll', label: 'Rolagem'}];
const pageKey = page => `${page.site_id}${page.path}`;

/** Site & Jornada → Heatmap: one device at a time, the pages that had views and clicks on it, and the heat over the capture. */
export function Heatmap({data, sites = []}) {
  const {period, scope} = useReportsContext();
  const [device, setDevice] = useState('desktop');
  const [mode, setMode] = useState('clicks');
  const [chosen, setChosen] = useState('');
  const [state, retry] = useApi(apiUrl('/journey/heatmap-pages', {start_date: period.start, end_date: period.end, device, site_id: scope.site}));
  const target = periodDays(period);
  // The click layer comes from a rolling window; the closest one to the chosen period.
  const days = WINDOWS.reduce((best, item) => Math.abs(item - target) < Math.abs(best - target) ? item : best, 30);
  const option = DEVICES.find(item => item.id === device);
  const pages = state.body?.device === device ? state.body.pages : [];
  const page = pages.find(item => pageKey(item) === chosen) || pages[0];
  const siteLabel = id => {const site = sites.find(item => item.id === id); return site?.allowed_host || site?.label || '';};
  return <Section className="rs-heatmap" title="Heatmap" description="Onde as pessoas clicam e até onde rolam, um dispositivo por vez."
    action={<div className="rs-toolbar">
      <ReportsTabs label="Dispositivo" value={device} onChange={setDevice} items={DEVICES}/>
      <ReportsTabs label="Camada do calor" value={mode} onChange={setMode} items={LAYERS}/>
    </div>}>
    <Async state={state.body?.device === device || state.error ? state : {...state, body: null, loading: true}} onRetry={retry} rows={4}
      isEmpty={body => !body.pages.length}
      empty={<EmptyState title={`Sem páginas com visitas e cliques no ${option.label.toLowerCase()}`}
        description="Só entram páginas que tiveram visualizações e cliques neste dispositivo no período. Mude o período, o site ou o dispositivo."/>}>
      {() => <div className="rs-heatmap__body">
        <nav className="rs-heatmap__pages" aria-label={`Páginas com cliques no ${option.label.toLowerCase()}`}>
          <div className="rs-heatmap__pages-head" aria-hidden="true"><span>Página</span><span>Views</span><span>Cliques</span></div>
          <ul>{pages.map(item => {
            const active = pageKey(item) === pageKey(page);
            return <li key={pageKey(item)}><button type="button" className={active ? 'is-active' : ''} aria-current={active ? 'true' : undefined}
              onClick={() => setChosen(pageKey(item))} title={`${item.host}${item.path}`}>
              <span className="rs-path">{item.path}{!scope.site && <small>{siteLabel(item.site_id) || item.host}</small>}</span>
              <span>{number(item.views)}</span><strong>{number(item.clicks)}</strong>
            </button></li>;
          })}</ul>
        </nav>
        <div className="rs-heatmap__stage">
          <header className="rs-heatmap__page">
            <div><h3 className="rs-path" title={`${page.host}${page.path}`}>{page.path}</h3><p>{page.host} · {option.label}</p></div>
            <dl><div><dt>Views</dt><dd>{number(page.views)}</dd></div><div><dt>Cliques</dt><dd>{number(page.clicks)}</dd></div></dl>
          </header>
          <PageVisual key={`${pageKey(page)}:${device}`} siteId={page.site_id} path={page.path} device={device} heatDevice={option.heat} days={days}
            metrics={page} mode={mode} canEdit={data.client.role !== 'viewer'} client={data.client.client_id} csrf={data.csrf}
            costTokens={state.body.cost_tokens} variant="heatmap"/>
        </div>
      </div>}
    </Async>
  </Section>;
}
