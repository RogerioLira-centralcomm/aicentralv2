import React, {useState} from 'react';

/** One meaning per stroke. The canvas tags every connection with one of these kinds. */
export function edgeLegendKind({simulated, returning, planned, measured, monitoring}) {
  if (simulated) return 'simulated';
  if (returning) return 'return';
  // Traffic measured on a planned link (an origin, a site link) is a real path now.
  if (measured) return 'measured';
  if (planned) return 'planned';
  return monitoring ? 'unmeasured' : 'drawn';
}

const STROKES = {
  measured: {label: 'Caminho medido', stroke: 'var(--color-fg-brand-primary)', width: 4},
  drawn: {label: 'Conexão do fluxo', stroke: 'var(--color-fg-brand-primary)', width: 2},
  unmeasured: {label: 'Sem passagens no período', stroke: 'var(--color-fg-quaternary)', width: 1.5},
  planned: {label: 'Planejada ou link do site', stroke: 'var(--color-fg-quaternary)', width: 2, dash: '6 6'},
  return: {label: 'Retorno a uma etapa anterior', stroke: 'var(--color-fg-warning-primary)', width: 2, dash: '3 5'},
  exit: {label: 'Saída sem converter', stroke: 'var(--color-fg-warning-primary)', width: 2, dash: '4 6'},
  suggested: {label: 'Sugerido pela navegação real', stroke: 'var(--color-fg-quaternary)', width: 2, dash: '3 6'},
  simulated: {label: 'Caminho da simulação', stroke: 'var(--color-fg-success-primary)', width: 3},
};
const SIGNALS = {
  traffic: {label: 'Tráfego no caminho', fill: 'var(--color-bg-primary)', stroke: 'var(--color-fg-brand-primary)'},
  operational: {label: 'Passagem nos últimos 90 s', fill: 'var(--color-fg-success-primary)'},
  pulse: {label: 'Nova passagem', fill: 'var(--color-fg-brand-primary)'},
};
const ORDER = ['measured', 'drawn', 'unmeasured', 'planned', 'return', 'exit', 'suggested', 'simulated'];
const number = value => Number(value).toLocaleString('pt-BR');

function Stroke({stroke, width, dash}) {
  return <svg width="36" height="12" viewBox="0 0 36 12" aria-hidden="true"><line x1="2" y1="6" x2="28" y2="6" stroke={stroke} strokeWidth={width} strokeDasharray={dash} strokeLinecap="round"/><path d="M28 2 L34 6 L28 10 Z" fill={stroke}/></svg>;
}

/** Legend of the strokes on screen. Only kinds present are listed; choosing one highlights just those connections. */
export function FlowEdgeLegend({kinds, scale, focus, onFocus, inspectorOpen}) {
  const [open, setOpen] = useState(() => {try {return localStorage.getItem('reports-flow-legend') !== 'closed';} catch (_) {return true;}});
  const toggle = () => setOpen(current => {try {localStorage.setItem('reports-flow-legend', current ? 'closed' : 'open');} catch (_) {/* not remembered */} return !current;});
  const strokes = ORDER.filter(kind => kinds.has(kind));
  const signals = Object.keys(SIGNALS).filter(kind => kinds.has(kind));
  if (!strokes.length && !signals.length) return null;
  return <div className={`flow-edge-legend nodrag nopan${open ? '' : ' is-closed'}${inspectorOpen ? ' has-inspector' : ''}`} role="region" aria-label="Legenda dos traços">
    <button type="button" className="flow-edge-legend__toggle" aria-expanded={open} onClick={toggle}>Legenda{focus ? ' · filtrando' : ''}</button>
    {open && <>
      <ul>{strokes.map(kind => {const item = STROKES[kind]; const active = focus === kind;
        return <li key={kind}><button type="button" aria-pressed={active} className={active ? 'is-active' : focus ? 'is-muted' : ''} title={active ? 'Mostrar todos os traços' : 'Destacar só este tipo de traço'} onClick={() => onFocus(active ? '' : kind)}><Stroke {...item}/><span>{item.label}</span></button>
          {kind === 'measured' && scale && <small className="flow-edge-legend__scale"><Stroke stroke={item.stroke} width={1.5}/>{number(scale.min)}<Stroke stroke={item.stroke} width={8.5}/>{number(scale.max)} sessões</small>}</li>;})}
        {signals.map(kind => <li key={kind} className="is-signal"><svg width="36" height="12" viewBox="0 0 36 12" aria-hidden="true"><line x1="2" y1="6" x2="34" y2="6" stroke="var(--color-border-secondary)" strokeWidth="2"/><circle cx="18" cy="6" r="4" fill={SIGNALS[kind].fill} stroke={SIGNALS[kind].stroke} strokeWidth="1.5"/></svg><span>{SIGNALS[kind].label}</span></li>)}
      </ul>
      {focus && <button type="button" className="flow-edge-legend__clear" onClick={() => onFocus('')}>Mostrar todos</button>}
    </>}
  </div>;
}
