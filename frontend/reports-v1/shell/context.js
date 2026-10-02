// Global Reports context: the active client and one analysis period shared by every analytic screen.
import {createContext, useContext} from 'react';
import {PRESETS, addDays, matchPreset, todayIso} from '../friendlyDates.js';

export const ReportsContext = createContext({period: null, setPeriod: () => {}, switchClient: () => {}});
export const useReportsContext = () => useContext(ReportsContext);

const ISO = /^\d{4}-\d{2}-\d{2}$/;
const DEFAULT_PRESET = '30';

/** Period from the address bar: ?period=30, ?start_date=&end_date= or the older ?days=N. */
export function readPeriod(search = location.search) {
  const query = new URLSearchParams(search);
  const start = query.get('start_date'), end = query.get('end_date');
  if (ISO.test(start || '') && ISO.test(end || '') && start <= end && end <= todayIso()) return {start, end};
  const days = Number(query.get('days'));
  const preset = PRESETS.find(item => item.id === (query.get('period') || '')) ||
    (days > 0 && days <= 365 ? null : PRESETS.find(item => item.id === DEFAULT_PRESET));
  if (preset) return preset.range();
  return {start: addDays(todayIso(), -(days - 1)), end: todayIso()};
}

/** Keeps the period in the URL so reloads, back/forward and shared links show the same window. */
export function writePeriod(range) {
  const url = new URL(location.href);
  ['days', 'period', 'start_date', 'end_date'].forEach(key => url.searchParams.delete(key));
  const preset = matchPreset(range.start, range.end);
  if (preset && preset !== DEFAULT_PRESET) url.searchParams.set('period', preset);
  else if (!preset) {url.searchParams.set('start_date', range.start); url.searchParams.set('end_date', range.end);}
  history.replaceState(history.state, '', `${url.pathname}${url.search}${url.hash}`);
}

export const periodDays = ({start, end}) => Math.max(1, Math.round((Date.parse(`${end}T12:00:00Z`) - Date.parse(`${start}T12:00:00Z`)) / 86400000) + 1);

/** Older endpoints accept only 7/30/90 in `days`; the exact window travels in start/end dates. */
export const periodBucket = range => {const days = periodDays(range); return days <= 7 ? '7' : days <= 30 ? '30' : '90';};

/** The legacy `filters` shape (period/startDate/endDate) that older screens still read. */
export const periodFilters = range => ({period: periodBucket(range), startDate: range.start, endDate: range.end});
