// Friendly Portuguese dates for the Reports screens: short months, no ISO strings, and "hoje"/"ontem" when they apply.
const MONTHS = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'];
const ZONE = 'America/Sao_Paulo';

const parts = iso => {
  const [year, month, day] = String(iso).slice(0, 10).split('-').map(Number);
  return {year, month, day};
};

export const isoDate = date => new Intl.DateTimeFormat('en-CA', {timeZone: ZONE, year: 'numeric', month: '2-digit', day: '2-digit'}).format(date);
export const todayIso = () => isoDate(new Date());
export const addDays = (iso, amount) => {
  const {year, month, day} = parts(iso);
  const date = new Date(Date.UTC(year, month - 1, day + amount));
  return date.toISOString().slice(0, 10);
};

/** "2 set 2026" */
export const formatDay = iso => {
  if (!iso) return '—';
  const {year, month, day} = parts(iso);
  return `${day} ${MONTHS[month - 1]} ${year}`;
};

/** "2 set" — compact axis labels. */
export const dayLabel = iso => formatDay(iso).replace(/ \d{4}$/, '');

/** "1–30 set 2026", "2 set – 1 out 2026" or, across years, both years. */
export function formatRange(start, end) {
  if (!start || !end) return '—';
  const a = parts(start), b = parts(end);
  if (a.year !== b.year) return `${formatDay(start)} – ${formatDay(end)}`;
  if (a.month !== b.month) return `${a.day} ${MONTHS[a.month - 1]} – ${b.day} ${MONTHS[b.month - 1]} ${b.year}`;
  if (a.day === b.day) return `${a.day} ${MONTHS[a.month - 1]} ${a.year}`;
  return `${a.day}–${b.day} ${MONTHS[b.month - 1]} ${b.year}`;
}

/** "hoje às 19:26", "ontem às 08:05", "18 ago" or "18 ago 2025". */
export function friendlyDateTime(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  const day = isoDate(date), today = todayIso();
  const time = new Intl.DateTimeFormat('pt-BR', {timeZone: ZONE, hour: '2-digit', minute: '2-digit'}).format(date);
  if (day === today) return `hoje às ${time}`;
  if (day === addDays(today, -1)) return `ontem às ${time}`;
  const {year, month, day: dayOfMonth} = parts(day);
  return `${dayOfMonth} ${MONTHS[month - 1]}${year === parts(today).year ? '' : ` ${year}`}`;
}

/** "agora há pouco", "há 12 min", "há 3 h" or a date, for "last event" style hints. */
export function friendlyAgo(value) {
  if (!value) return '—';
  const seconds = Math.max(0, Math.round((Date.now() - new Date(value).getTime()) / 1000));
  if (seconds < 90) return 'agora há pouco';
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `há ${minutes} min`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `há ${hours} h`;
  return friendlyDateTime(value);
}

export const PRESETS = [
  {id: '7', label: 'Últimos 7 dias', range: () => ({start: addDays(todayIso(), -6), end: todayIso()})},
  {id: '14', label: 'Últimos 14 dias', range: () => ({start: addDays(todayIso(), -13), end: todayIso()})},
  {id: '30', label: 'Últimos 30 dias', range: () => ({start: addDays(todayIso(), -29), end: todayIso()})},
  {id: '90', label: 'Últimos 90 dias', range: () => ({start: addDays(todayIso(), -89), end: todayIso()})},
  {id: 'month', label: 'Este mês', range: () => ({start: `${todayIso().slice(0, 8)}01`, end: todayIso()})},
  {id: 'last-month', label: 'Mês passado', range: () => {
    const first = `${todayIso().slice(0, 8)}01`;
    const end = addDays(first, -1);
    return {start: `${end.slice(0, 8)}01`, end};
  }},
];

export const matchPreset = (start, end) => PRESETS.find(item => {const range = item.range(); return range.start === start && range.end === end;})?.id || '';
