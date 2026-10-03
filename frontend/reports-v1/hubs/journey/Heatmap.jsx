import React, {useEffect, useId, useMemo, useRef, useState} from 'react';
import {ArrowRight, InfoCircle, LinkExternal01, RefreshCw01, SearchLg} from '@untitledui/icons';
import {usePageCapture} from '../../PageDetail.jsx';
import {ReportsActionButton} from '../../ReportsActionButton.jsx';
import {ReportsTabs} from '../../ReportsTabs.jsx';
import {friendlyAgo} from '../../friendlyDates.js';
import {reportUrl} from '../../reportsCommon.jsx';
import {useReportsContext} from '../../shell/context.js';
import {apiUrl, useApi} from '../../shell/useApi.js';
import {AppLink, Async, EmptyState, Section} from '../../shell/primitives.jsx';
import {number} from '../shared.jsx';
import './journey.css';

// Celular groups phones and tablets (viewport < 1024 px) over the phone capture; Computador is >= 1024 px.
const DEVICES = [{id: 'desktop', label: 'Computador'}, {id: 'mobile', label: 'Celular'}];
const LAYERS = [{id: 'clicks', label: 'Cliques'}, {id: 'scroll', label: 'Rolagem'}];
const PANELS = [{id: 'elements', label: 'Cliques'}, {id: 'zones', label: 'Zonas'}];
const SCROLL_STEPS = [['scroll_25', '25%'], ['scroll_50', '50%'], ['scroll_75', '75%'], ['scroll_100', '100%']];
const SCROLL_BANDS = [['scroll_25', '0–25%'], ['scroll_50', '25–50%'], ['scroll_75', '50–75%'], ['scroll_100', '75–100%']];
const pageKey = page => `${page.site_id}${page.path}`;
const pageName = path => path === '/' ? '/ · Página inicial' : path;
const share = value => value == null ? '—' : `${Number(value).toLocaleString('pt-BR', {maximumFractionDigits: 1})}%`;

/** Searchable page selector: path plus views and clicks of the period on the chosen device. */
function PagePicker({pages, value, onChange}) {
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const listId = useId();
  const found = useMemo(() => {
    const text = query.trim().toLowerCase();
    return text ? pages.filter(item => item.path.toLowerCase().includes(text)) : pages;
  }, [pages, query]);
  useEffect(() => setActive(0), [query]);
  const choose = item => {onChange(pageKey(item)); setQuery(''); setOpen(false);};
  return <div className="rs-heatmap__picker">
    <SearchLg size={16} aria-hidden="true"/>
    <input role="combobox" aria-label="Página" aria-expanded={open} aria-controls={listId} aria-autocomplete="list" autoComplete="off"
      value={open ? query : pageName(value.path)} placeholder="Buscar página" title={`${value.host}${value.path}`}
      onFocus={() => {setOpen(true); setQuery('');}} onBlur={() => setTimeout(() => setOpen(false), 140)}
      onChange={event => {setQuery(event.target.value); setOpen(true);}}
      onKeyDown={event => {
        if (event.key === 'ArrowDown') {event.preventDefault(); setActive(index => Math.min(found.length - 1, index + 1));}
        else if (event.key === 'ArrowUp') {event.preventDefault(); setActive(index => Math.max(0, index - 1));}
        else if (event.key === 'Enter' && open && found[active]) {event.preventDefault(); choose(found[active]);}
        else if (event.key === 'Escape') {setOpen(false); event.currentTarget.blur();}
      }}/>
    {open && <ul id={listId} role="listbox" aria-label="Páginas com cliques">
      {found.map((item, index) => <li key={pageKey(item)} role="option" aria-selected={pageKey(item) === pageKey(value)}>
        <button type="button" tabIndex={-1} className={index === active ? 'is-active' : ''} onMouseDown={event => event.preventDefault()} onClick={() => choose(item)}>
          <span className="rs-path">{pageName(item.path)}</span><small>{number(item.views)} views · {number(item.clicks)} cliques</small>
        </button>
      </li>)}
      {!found.length && <li className="rs-heatmap__picker-empty">Nenhuma página com esse endereço.</li>}
    </ul>}
  </div>;
}

// Classic heat scale: cold blue, green, yellow, hot red.
const PALETTE = (() => {
  if (typeof document === 'undefined') return null;
  const canvas = document.createElement('canvas');
  canvas.width = 256; canvas.height = 1;
  const context = canvas.getContext('2d');
  if (!context) return null;
  const gradient = context.createLinearGradient(0, 0, 256, 0);
  [[0, '#2563eb'], [0.35, '#06b6d4'], [0.55, '#22c55e'], [0.75, '#facc15'], [1, '#ef4444']].forEach(([stop, color]) => gradient.addColorStop(stop, color));
  context.fillStyle = gradient;
  context.fillRect(0, 0, 256, 1);
  return context.getImageData(0, 0, 256, 1).data;
})();

/** Smooth click heat over the capture: one soft spot per grid cell, summed, then coloured by the heat scale. */
function HeatCanvas({heat, width, height, intensity}) {
  const ref = useRef(null);
  useEffect(() => {
    const canvas = ref.current;
    const context = canvas?.getContext('2d', {willReadFrequently: true});
    if (!context || !PALETTE) return;
    const W = 480, H = Math.max(1, Math.min(4800, Math.round(W * height / width)));
    canvas.width = W; canvas.height = H;
    context.clearRect(0, 0, W, H);
    const cellW = W / heat.columns, cellH = H / heat.rows;
    const radius = Math.max(cellW, cellH) * 1.6;
    const gain = 0.35 + intensity * 1.3;
    heat.points.forEach(([x, y, value]) => {
      const cx = (x + 0.5) * cellW, cy = (y + 0.5) * cellH;
      const gradient = context.createRadialGradient(cx, cy, 0, cx, cy, radius);
      gradient.addColorStop(0, `rgba(0,0,0,${Math.min(1, value / heat.peak * gain)})`);
      gradient.addColorStop(1, 'rgba(0,0,0,0)');
      context.fillStyle = gradient;
      context.fillRect(cx - radius, cy - radius, radius * 2, radius * 2);
    });
    const image = context.getImageData(0, 0, W, H);
    const pixels = image.data;
    for (let index = 3; index < pixels.length; index += 4) {
      const alpha = pixels[index];
      if (!alpha) continue;
      const offset = alpha * 4;
      pixels[index - 3] = PALETTE[offset]; pixels[index - 2] = PALETTE[offset + 1]; pixels[index - 1] = PALETTE[offset + 2];
      pixels[index] = Math.min(210, 40 + alpha);
    }
    context.putImageData(image, 0, 0);
  }, [heat, width, height, intensity]);
  return <canvas ref={ref} className="rs-heatmap__canvas" aria-hidden="true"/>;
}

/** The capture framed as a browser window, with the click heat or the scroll bands on top. */
function CaptureStage({page, device, mode, intensity, detail, canEdit, client, csrf, costTokens}) {
  const {state, starting, capture, ready} = usePageCapture({siteId: page.site_id, path: page.path, device, client, csrf});
  const body = state.body;
  const address = `https://${page.host}${page.path}`;
  const cost = costTokens ? `${costTokens.toLocaleString('pt-BR')} tokens` : '';
  const captureButton = label => <ReportsActionButton color={ready ? 'secondary' : 'primary'} size="sm" disabled={starting} onClick={capture}
    title={cost ? `A captura custa ${cost}` : undefined} iconLeading={RefreshCw01}>{label}{cost && !ready ? ` · ${cost}` : ''}</ReportsActionButton>;
  const summary = detail?.summary || page;
  return <figure className={`rs-heatmap__frame rs-heatmap__frame--${device}`}>
    <figcaption className="rs-heatmap__chrome">
      <span className="rs-heatmap__address" title={address}>{address}</span>
      <a className="rs-heatmap__open" href={address} target="_blank" rel="noopener noreferrer" aria-label="Abrir a página em outra aba"><LinkExternal01 size={14} aria-hidden="true"/></a>
      {ready && <span className="rs-heatmap__captured">Última captura {friendlyAgo((body.captured_at || 0) * 1000)}</span>}
      {ready && canEdit && body.available !== false && body.status !== 'capturing' && captureButton('Atualizar captura')}
    </figcaption>
    {state.error && <div className="reports-error" role="alert">{state.error}</div>}
    {state.loading && <div className="rs-heatmap__placeholder" role="status">Verificando captura…</div>}
    {body && !ready && <div className="rs-heatmap__placeholder">
      <strong>{body.status === 'capturing' ? 'Capturando a página…' : body.status === 'failed' ? 'A captura falhou' : 'Sem captura desta página'}</strong>
      <p>{body.status === 'capturing' ? 'Isso leva cerca de um minuto.' : body.status === 'failed' ? (body.message || 'Tente de novo.') : 'Capture a página para ver o calor sobre ela.'}</p>
      {body.status !== 'capturing' && (!body.available ? <p className="rs-heatmap__muted">Captura indisponível neste ambiente (Firecrawl não configurado).</p>
        : canEdit ? captureButton('Capturar a página') : <p className="rs-heatmap__muted">Peça a alguém com permissão de edição para capturar a página.</p>)}
    </div>}
    {ready && <>
      {body.status === 'failed' && <p className="page-detail-warning" role="note">{body.message} Mostrando a captura anterior.</p>}
      <div className="rs-heatmap__stage" style={{aspectRatio: `${body.width} / ${body.height}`}}>
        <img src={body.image_url} alt={`Captura da página ${page.path} no ${device === 'mobile' ? 'celular' : 'computador'}`}/>
        {mode === 'clicks' && detail?.heat?.total > 0 && <HeatCanvas heat={detail.heat} width={body.width} height={body.height} intensity={intensity}/>}
        {mode === 'scroll' && <div className="page-detail-overlay page-detail-overlay--bands" aria-hidden="true" style={{'--intensity': 0.35 + intensity * 0.6}}>{SCROLL_BANDS.map(([key, label]) =>
          <i key={key} style={{'--heat': (summary[key] ?? 0) / 100}} data-empty={summary[key] ? undefined : ''}><b>{label} · {share(summary[key])}</b></i>)}</div>}
      </div>
      {mode === 'clicks' && detail && <p className="rs-heatmap__muted">{detail.heat.total
        ? `${number(detail.heat.total)} de ${number(detail.summary.clicks)} cliques têm posição na página inteira e aparecem no calor.`
        : 'Ainda não há cliques com posição na página inteira para sobrepor.'} Se a página mudou depois da captura, o calor pode não coincidir com o desenho.</p>}
    </>}
  </figure>;
}

function Bar({value}) {
  return <i className="rs-heatmap__bar"><b style={{width: `${Math.max(0, Math.min(100, value || 0))}%`}}/></i>;
}

/** Side panel: most clicked elements or zones, scroll reach, device split and the plain-language reading. */
function SidePanel({detail, onDevice, detailHref}) {
  const [panel, setPanel] = useState('elements');
  if (!detail) return <aside className="rs-heatmap__side" aria-busy="true"><div className="reports-loading" role="status">Carregando os números da página…</div></aside>;
  const {elements, zones, devices, insights, summary} = detail;
  return <aside className="rs-heatmap__side" aria-label="Resumo da página">
    <ReportsTabs className="rs-heatmap__side-tabs" label="Detalhe dos cliques" value={panel} onChange={setPanel} items={PANELS}/>
    {panel === 'elements' ? <section>
      <h3>Elementos mais clicados</h3>
      {elements.items.length ? <table className="rs-heatmap__table">
        <thead><tr><th scope="col">Elemento</th><th scope="col">Cliques</th><th scope="col">% dos cliques</th></tr></thead>
        <tbody>{elements.items.slice(0, 5).map((item, index) => <tr key={`${item.element_id || ''}${item.label}${item.kind || ''}`}>
          <th scope="row"><span className="rs-heatmap__rank">{index + 1}</span><span className="rs-heatmap__element" title={item.label}>{item.label}{item.kind_label && <small>{item.kind_label}</small>}</span></th>
          <td>{number(item.clicks)}</td><td>{share(item.share)}</td>
        </tr>)}</tbody>
      </table> : <p className="rs-heatmap__muted">Os cliques desta página ainda não têm nome. Eles passam a ter quando os visitantes carregarem a Super Tag atualizada.</p>}
      {elements.items.length > 0 && elements.unnamed_clicks > 0 && <p className="rs-heatmap__muted">{share(elements.unnamed_share)} dos cliques ainda não têm nome (tag antiga em cache).</p>}
      <AppLink className="rs-heatmap__link" href={detailHref}>Ver todos os cliques <ArrowRight size={14} aria-hidden="true"/></AppLink>
    </section> : <section>
      <h3>Cliques por zona da página</h3>
      <ul className="rs-heatmap__bars">{zones.map(zone => <li key={zone.range}>
        <span>{zone.label} <small>{zone.range}</small></span><Bar value={zone.share}/><strong>{share(zone.share)}</strong>
      </li>)}</ul>
      <p className="rs-heatmap__muted">Zonas são quartos da altura da página; só entram cliques com posição na página inteira.</p>
    </section>}
    <section>
      <h3>Mapa de rolagem</h3>
      <ul className="rs-heatmap__bars">{SCROLL_STEPS.map(([key, label]) => <li key={key}>
        <span>{label}</span><Bar value={summary[key]}/><strong>{share(summary[key])}</strong>
      </li>)}</ul>
      {summary.scroll_25 != null && <p className="rs-heatmap__note"><InfoCircle size={14} aria-hidden="true"/>{share(summary.scroll_25)} das pessoas rolaram até 25% da página.</p>}
    </section>
    <section>
      <h3>Dispositivos</h3>
      <ul className="rs-heatmap__bars rs-heatmap__bars--devices">{devices.map(item => {
        const target = item.device === 'desktop' ? 'desktop' : 'mobile';
        return <li key={item.device}><button type="button" onClick={() => onDevice(target)} title={`Ver o heatmap no ${target === 'desktop' ? 'computador' : 'celular'}`}>
          <span>{item.label}</span><strong>{share(item.share)}</strong><Bar value={item.share}/>
        </button></li>;
      })}</ul>
      <p className="rs-heatmap__muted">Parcela das visualizações da página. No heatmap, Celular inclui tablets.</p>
    </section>
    <section>
      <h3>Insights</h3>
      {insights.length ? <ul className="rs-heatmap__insights">{insights.map(text => <li key={text}>{text}</li>)}</ul>
        : <p className="rs-heatmap__muted">Com {number(summary.clicks)} cliques ainda não dá para tirar conclusões seguras sobre esta página.</p>}
    </section>
  </aside>;
}

/** Site & Jornada → Heatmap: one page of the site in the header, one device at a time, the heat over the capture and its reading. */
export function Heatmap({data}) {
  const {period, scope} = useReportsContext();
  const [device, setDevice] = useState('desktop');
  const [mode, setMode] = useState('clicks');
  const [intensity, setIntensity] = useState(0.6);
  const [chosen, setChosen] = useState('');
  const [state, retry] = useApi(apiUrl('/journey/heatmap-pages', {start_date: period.start, end_date: period.end, device, site_id: scope.site}));
  const pages = state.body?.device === device ? state.body.pages : [];
  const page = pages.find(item => pageKey(item) === chosen) || pages[0];
  const [detailState] = useApi(page ? apiUrl('/journey/heatmap-detail', {start_date: period.start, end_date: period.end, device, site_id: page.site_id, path: page.path}) : null);
  const detail = detailState.body?.device === device && detailState.body.page?.path === page?.path ? detailState.body : null;
  const option = DEVICES.find(item => item.id === device);
  const totals = detail?.summary || page;
  return <Section className="rs-heatmap" title="Heatmap" description="Veja onde as pessoas clicam e até onde rolam nas suas páginas.">
    <Async state={state.body?.device === device || state.error ? state : {...state, body: null, loading: true}} onRetry={retry} rows={4}
      isEmpty={body => !body.pages.length}
      empty={<EmptyState title={`Sem páginas com visitas e cliques no ${option.label.toLowerCase()}`}
        description="Só entram páginas que tiveram visualizações e cliques neste dispositivo no período. Mude o período, o site ou o dispositivo."/>}>
      {() => <>
        <div className="rs-heatmap__controls">
          <div className="rs-heatmap__control rs-heatmap__control--page">
            <span className="rs-heatmap__label">Página</span>
            <PagePicker pages={pages} value={page} onChange={setChosen}/>
            <AppLink className="rs-heatmap__link" href={reportUrl('pages', {site_id: page.site_id, path: page.path})}>Ver detalhes da página <ArrowRight size={14} aria-hidden="true"/></AppLink>
          </div>
          <dl className="rs-heatmap__kpis">
            <div><dd>{number(totals.views)}</dd><dt>visualizações</dt></div>
            <div><dd>{number(totals.clicks)}</dd><dt>cliques</dt></div>
          </dl>
          <div className="rs-heatmap__control"><span className="rs-heatmap__label">Dispositivo</span><ReportsTabs label="Dispositivo" value={device} onChange={setDevice} items={DEVICES}/></div>
          <div className="rs-heatmap__control"><span className="rs-heatmap__label">Tipo de mapa</span><ReportsTabs label="Tipo de mapa" value={mode} onChange={setMode} items={LAYERS}/></div>
          <label className="rs-heatmap__control rs-heatmap__intensity"><span className="rs-heatmap__label">Intensidade</span>
            <input type="range" min="0" max="1" step="0.05" value={intensity} aria-label="Intensidade do calor" onChange={event => setIntensity(Number(event.target.value))}/>
            <span className="rs-heatmap__scale" aria-hidden="true"><span>Baixa</span><span>Alta</span></span>
          </label>
        </div>
        <div className="rs-heatmap__layout">
          <CaptureStage key={`${pageKey(page)}:${device}`} page={page} device={device} mode={mode} intensity={intensity} detail={detail}
            canEdit={data.client.role !== 'viewer'} client={data.client.client_id} csrf={data.csrf} costTokens={state.body.cost_tokens}/>
          <SidePanel detail={detail} onDevice={setDevice} detailHref={reportUrl('pages', {site_id: page.site_id, path: page.path})}/>
        </div>
      </>}
    </Async>
  </Section>;
}
