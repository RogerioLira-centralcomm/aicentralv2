import React from 'react';
import {Section} from '../../shell/primitives.jsx';
import {number} from '../shared.jsx';
import './tech-panel.css';

const DEVICE_LABELS = {mobile: 'Celular', tablet: 'Tablet', desktop: 'Computador', unknown: 'Não identificado'};
const PALETTE = ['#175cd3', '#53b1fd', '#12b76a', '#f79009', '#7a5af8', '#98a2b3'];
const pct = (value, digits = 0) => `${Number(value).toLocaleString('pt-BR', {maximumFractionDigits: digits})}%`;

/** Screen width (CSS px) to a named band; the band says more than "1536×864". */
const SCREEN_BANDS = [
  {id: 'phone', label: 'Celular', hint: 'até 767 px', max: 768},
  {id: 'tablet', label: 'Tablet', hint: '768–1023 px', max: 1024},
  {id: 'laptop', label: 'Notebook', hint: '1024–1439 px', max: 1440},
  {id: 'desktop', label: 'Monitor', hint: '1440–1919 px', max: 1920},
  {id: 'large', label: 'Tela grande', hint: '1920 px ou mais', max: Infinity},
];

/** Groups "1920×1080" style rows into the bands above, keeping sessions, conversions and the most common size of each. */
export function screenBands(rows = []) {
  const bands = SCREEN_BANDS.map(band => ({...band, sessions: 0, converted: 0, top: null}));
  for (const row of rows) {
    const width = Number(String(row.value).split('×')[0]);
    if (!Number.isFinite(width)) continue;
    const band = bands.find(item => width < item.max);
    band.sessions += row.sessions;
    band.converted += row.converted_sessions || 0;
    if (!band.top || row.sessions > band.top.sessions) band.top = row;
  }
  const total = bands.reduce((sum, band) => sum + band.sessions, 0);
  return bands.map(band => ({...band, share: total ? band.sessions * 100 / total : 0})).filter(band => band.sessions > 0);
}

/** Share of the whole as a ring with the total in the middle. */
export function Donut({items, total, label}) {
  const radius = 42, circumference = 2 * Math.PI * radius;
  let offset = 0;
  return <figure className="rs-tech__donut">
    <svg viewBox="0 0 120 120" role="img" aria-label={label}>
      <circle cx="60" cy="60" r={radius} fill="none" stroke="var(--color-bg-tertiary, #eaecf0)" strokeWidth="16"/>
      {items.map((item, index) => {
        const length = total ? item.sessions / total * circumference : 0;
        const segment = <circle key={item.key} cx="60" cy="60" r={radius} fill="none" stroke={PALETTE[index % PALETTE.length]} strokeWidth="16"
          strokeDasharray={`${Math.max(0, length - 1.5)} ${circumference}`} strokeDashoffset={-offset} transform="rotate(-90 60 60)"><title>{`${item.label}: ${pct(total ? item.sessions * 100 / total : 0)}`}</title></circle>;
        offset += length;
        return segment;
      })}
      <text x="60" y="58" textAnchor="middle" className="rs-tech__donut-total">{number(total)}</text>
      <text x="60" y="73" textAnchor="middle" className="rs-tech__donut-caption">sessões</text>
    </svg>
    <figcaption><ul>{items.map((item, index) => <li key={item.key}><i style={{background: PALETTE[index % PALETTE.length]}}/><span>{item.label}</span><strong>{pct(total ? item.sessions * 100 / total : 0)}</strong></li>)}</ul></figcaption>
  </figure>;
}

/** Ranked bars: volume as length, conversion as a badge once the base is large enough to mean something. */
export function RankBars({rows, minimum, limit = 6}) {
  const shown = rows.slice(0, limit);
  const rest = rows.slice(limit).reduce((sum, row) => sum + row.sessions, 0);
  const peak = Math.max(1, ...shown.map(row => row.sessions));
  return <ul className="rs-tech__bars">
    {shown.map((row, index) => <li key={row.value}>
      <span className="rs-tech__chip" style={{background: PALETTE[index % PALETTE.length]}} aria-hidden="true">{String(row.value).slice(0, 1).toUpperCase()}</span>
      <span className="rs-tech__name">{row.value}</span>
      <i className="rs-tech__track"><b style={{width: `${Math.max(3, row.sessions * 100 / peak)}%`, background: PALETTE[index % PALETTE.length]}}/></i>
      <strong>{pct(row.share)}</strong>
      <em className={row.conversion_rate != null && row.conversion_rate > 0 ? 'is-converting' : ''} title={row.conversion_rate == null ? `Base pequena: a taxa aparece a partir de ${minimum} sessões.` : `${number(row.converted_sessions)} de ${number(row.sessions)} sessões converteram`}>
        {row.conversion_rate == null ? '—' : pct(row.conversion_rate, 1)}</em>
    </li>)}
    {rest > 0 && <li className="rs-tech__rest"><span className="rs-tech__name">Outros</span><strong>{number(rest)} sessões</strong></li>}
  </ul>;
}

/** One stacked bar of screen sizes, with the most common exact size under each band. */
export function ScreenSizes({rows}) {
  const bands = screenBands(rows);
  if (!bands.length) return <p className="rs-muted">Sem dados de tela.</p>;
  return <div className="rs-tech__screens">
    <div className="rs-tech__stack" role="img" aria-label={`Faixas de tela: ${bands.map(band => `${band.label} ${pct(band.share)}`).join(', ')}`}>
      {bands.map((band, index) => <span key={band.id} style={{flexGrow: Math.max(band.share, 2), background: PALETTE[index % PALETTE.length]}} title={`${band.label}: ${pct(band.share)}`}>{band.share >= 9 ? pct(band.share) : ''}</span>)}
    </div>
    <ul className="rs-tech__bands">
      {bands.map((band, index) => <li key={band.id}><i style={{background: PALETTE[index % PALETTE.length]}}/>
        <span><strong>{band.label}</strong><small>{band.hint}</small></span>
        <span className="rs-tech__band-top">{band.top ? <>mais comum <b>{band.top.value}</b></> : null}</span>
        <strong>{pct(band.share)}</strong></li>)}
    </ul>
  </div>;
}

/** Plain-language reading of the three rankings: what dominates, and what converts best on a base that counts. */
function insights(tech, devices, minimum) {
  const lines = [];
  const device = [...devices].sort((a, b) => b.sessions - a.sessions)[0];
  const deviceTotal = devices.reduce((sum, item) => sum + item.sessions, 0);
  if (device && deviceTotal) lines.push(`${DEVICE_LABELS[device.device] || device.device} concentra ${pct(device.sessions * 100 / deviceTotal)} das sessões.`);
  const browser = tech.browser?.[0];
  if (browser) lines.push(`${browser.value} é o navegador principal (${pct(browser.share)}).`);
  const best = [...(tech.browser || []), ...(tech.os || [])].filter(row => row.conversion_rate != null && row.converted_sessions > 0).sort((a, b) => b.conversion_rate - a.conversion_rate)[0];
  if (best) lines.push(`Melhor conversão: ${best.value} (${pct(best.conversion_rate, 1)}).`);
  return lines;
}

/** Visual panel for device, browser, system and screen size: shares as shapes, not a table. */
export function TechPanel({tech, devices, minimum, title = 'Tecnologia dos visitantes'}) {
  const deviceItems = devices.map(item => ({key: item.device, label: DEVICE_LABELS[item.device] || item.device, sessions: item.sessions}));
  const deviceTotal = deviceItems.reduce((sum, item) => sum + item.sessions, 0);
  const lines = insights(tech, devices, minimum);
  const hasTech = tech.sessions > 0;
  return <Section title={title} description={hasTech ? `Aparelho, navegador, sistema e tela de ${number(tech.sessions)} sessões (${pct(tech.coverage)} do total)` : 'Aparelho, navegador, sistema e tela'}>
    {!hasTech && !deviceTotal ? <p className="rs-muted">Ainda sem dados. A coleta começa quando o site passa a carregar a Super Tag atualizada; visitas anteriores não trazem essas informações.</p> : <div className="rs-tech">
      {lines.length > 0 && <ul className="rs-tech__insights">{lines.map(line => <li key={line}>{line}</li>)}</ul>}
      <div className="rs-tech__grid">
        {deviceTotal > 0 && <article className="rs-tech__card"><h3>Dispositivos</h3><Donut items={deviceItems} total={deviceTotal} label="Sessões por tipo de aparelho"/></article>}
        {tech.browser?.length > 0 && <article className="rs-tech__card"><h3>Navegadores <small>parte · conversão</small></h3><RankBars rows={tech.browser} minimum={minimum}/></article>}
        {tech.os?.length > 0 && <article className="rs-tech__card"><h3>Sistemas <small>parte · conversão</small></h3><RankBars rows={tech.os} minimum={minimum}/></article>}
      </div>
      {tech.resolution?.length > 0 && <article className="rs-tech__card rs-tech__card--wide"><h3>Tamanhos de tela</h3><ScreenSizes rows={tech.resolution}/></article>}
      {hasTech && tech.coverage < 100 && <p className="rs-muted rs-tech__note">Sessões anteriores à atualização da Super Tag não entram em navegador, sistema e tela.</p>}
    </div>}
  </Section>;
}
