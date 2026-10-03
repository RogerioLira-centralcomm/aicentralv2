import React from 'react';
import {addDays, dayLabel, toIsoDay} from '../friendlyDates.js';
import {Chart} from './media.jsx';
import {AppLink} from './primitives.jsx';
import './trend.css';

/** Every day of the window, in order, with the matching value (0 when nothing happened that day). */
export function daySeries(start, end, rows, field) {
  const values = new Map((rows || []).map(row => [toIsoDay(row.date), row[field]]));
  const out = [];
  for (let day = start; day <= end; day = addDays(day, 1)) out.push({date: day, value: values.has(day) ? Number(values.get(day) || 0) : 0});
  return out;
}

/** One small daily chart: the period as an area, the previous period dashed when there is something to compare. */
export function TrendCard({title, total, points, previous, format, href}) {
  const labels = points.map(item => dayLabel(item.date));
  const series = [{name: 'Período', data: points.map(item => item.value)}];
  const comparable = previous?.length === points.length && previous.some(value => value);
  if (comparable) series.push({name: 'Anterior', data: previous});
  return <article className="rs-trend">
    <header><h3>{title}</h3>{href ? <AppLink className="rs-trend__total" href={href}>{total}</AppLink> : <span className="rs-trend__total">{total}</span>}</header>
    <Chart type="area" height={150} labels={labels} series={series} dash={comparable ? [0, 4] : undefined} colors={['#175cd3', '#98a2b3']} format={format} legend={false}/>
  </article>;
}

/** Breakdown card that sits in the grid next to the charts (e.g. investment by channel). */
export function TrendAside({title, action, children}) {
  return <article className="rs-trend"><header><h3>{title}</h3>{action}</header>{children}</article>;
}

/**
 * "Tendência diária": daily cards of campaigns (and site, on the overview), three per row, with a shared key.
 * `charts` are TrendCard props with a `key`; `children` are extra cards appended to the grid.
 */
export function TrendGrid({title = 'Tendência diária', description, charts, children, columns = 3}) {
  if (!charts.length && !children) return null;
  return <section className="rs-trends" aria-label={`${title} no período`}>
    <header className="rs-trends__head"><div><h2>{title}</h2>{description && <p>{description}</p>}</div>
      <span><i className="rs-trend-key"/>Período <i className="rs-trend-key is-previous"/>Período anterior</span></header>
    <div className="rs-trends__grid" style={{'--rs-trend-columns': columns}}>{charts.map(item => <TrendCard key={item.key} {...item}/>)}{children}</div>
  </section>;
}
