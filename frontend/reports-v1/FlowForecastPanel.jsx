import React, {useMemo, useState} from 'react';
import {ReportsPanelShell} from './ReportsPanelShell.jsx';
import {ReportsFieldInput} from './ReportsFieldInput.jsx';
import {FORECAST_SCENARIOS, forecastRate, forecastScenarios} from './flowForecast.js';

const count = value => value == null ? '—' : Math.round(value).toLocaleString('pt-BR');
const money = value => value == null ? '—' : value.toLocaleString('pt-BR', {style: 'currency', currency: 'BRL', maximumFractionDigits: value < 100 ? 2 : 0});
const percent = value => value == null ? '—' : `${value.toLocaleString('pt-BR', {maximumFractionDigits: 1})}%`;
const ratio = value => value == null ? '—' : `${value.toLocaleString('pt-BR', {maximumFractionDigits: 2})}×`;
const ROWS = [
  ['visits', 'Visitas', count], ['results', 'Resultados', count], ['conversionRate', 'Taxa de conversão', percent],
  ['cost', 'Investimento', money], ['revenue', 'Receita', money], ['costPerResult', 'Custo por resultado', money], ['roas', 'Retorno (ROAS)', ratio],
];
const parse = value => {const text = String(value).trim().replace(/\./g, '').replace(',', '.'); if (!text) return ''; const parsed = Number(text); return Number.isFinite(parsed) ? parsed : '';};

function NumberField({label, value, suffix, max, readOnly, onChange}) {
  const caption = suffix ? `${label} (${suffix})` : label;
  const [draft, setDraft] = useState(null);
  const shown = draft ?? (value == null ? '' : String(value).replace('.', ','));
  return <label className="flow-forecast-field"><span>{caption}</span>
    <ReportsFieldInput disabled={readOnly} inputMode="decimal" value={shown} placeholder="0" aria-label={caption}
      onFocus={() => setDraft(shown)} onBlur={() => setDraft(null)}
      onChange={event => {setDraft(event.target.value); const next = parse(event.target.value); onChange(next === '' ? '' : Math.min(max ?? Infinity, Math.max(0, next)));}}/>
  </label>;
}

/** Plan numbers before investing: visits and cost per origin, rates per connection, value per conversion. */
export function FlowForecastPanel({config, scenario, onScenarioChange, readOnly, onChange, onClose}) {
  const scenarios = useMemo(() => forecastScenarios(config), [config]);
  const active = scenarios[scenario];
  const nodes = (config.nodes || []).filter(node => node.type !== 'note');
  const byId = new Map(nodes.map(node => [node.id, node]));
  const sources = nodes.filter(node => node.type === 'source');
  const conversions = nodes.filter(node => node.type === 'conversion');
  const returns = new Set(active.returns);
  const edges = (config.edges || []).filter(edge => byId.has(edge.from) && byId.has(edge.to) && !returns.has(edge.id));
  const setNode = (id, field, value) => onChange({...config, nodes: config.nodes.map(node => node.id === id
    ? {...node, forecast: Object.fromEntries(Object.entries({...(node.forecast || {}), [field]: value}).filter(([, item]) => item !== ''))} : node)});
  const setRate = (id, value) => onChange({...config, edges: config.edges.map(edge => edge.id === id
    ? (value === '' ? Object.fromEntries(Object.entries(edge).filter(([key]) => key !== 'forecast')) : {...edge, forecast: {rate: value}}) : edge)});
  return <ReportsPanelShell compact className="flow-blueprint-panel flow-forecast-panel" title="Previsão" onClose={onClose}>
    <div className="flow-forecast-scenarios" role="radiogroup" aria-label="Cenário exibido na mesa">{FORECAST_SCENARIOS.map(item =>
      <button key={item.id} type="button" role="radio" aria-checked={item.id === scenario} className={item.id === scenario ? 'is-selected' : ''} onClick={() => onScenarioChange(item.id)}>{item.label}</button>)}</div>
    <table className="flow-forecast-table"><thead><tr><th scope="col"><span className="reports-sr-only">Indicador</span></th>{FORECAST_SCENARIOS.map(item => <th key={item.id} scope="col" className={item.id === scenario ? 'is-selected' : ''}>{item.label}</th>)}</tr></thead>
      <tbody>{ROWS.map(([key, label, format]) => <tr key={key}><th scope="row">{label}</th>{FORECAST_SCENARIOS.map(item => <td key={item.id} className={item.id === scenario ? 'is-selected' : ''}>{format(scenarios[item.id].totals[key])}</td>)}</tr>)}</tbody></table>
    {(active.missingRates.length > 0 || active.overAllocated.length > 0) && <div className="flow-forecast-warnings" role="status">
      {active.missingRates.length > 0 && <p>{active.missingRates.length} {active.missingRates.length === 1 ? 'conexão sem taxa não leva' : 'conexões sem taxa não levam'} ninguém adiante.</p>}
      {active.overAllocated.map(id => <p key={id}>As saídas de {byId.get(id)?.title || 'um passo'} somam mais de 100%.</p>)}
    </div>}
    <section className="flow-forecast-group" aria-label="Origens"><h3>Origens</h3>{sources.length ? sources.map(node => <div key={node.id} className="flow-forecast-row">
      <strong>{node.title}</strong>
      <NumberField label="Visitas" value={node.forecast?.visits} readOnly={readOnly} max={1e9} onChange={value => setNode(node.id, 'visits', value)}/>
      <NumberField label="Investimento" suffix="R$" value={node.forecast?.cost} readOnly={readOnly} max={1e12} onChange={value => setNode(node.id, 'cost', value)}/>
    </div>) : <p>Adicione uma origem de tráfego para começar a previsão.</p>}</section>
    <section className="flow-forecast-group" aria-label="Conexões"><h3>Taxas entre passos</h3>{edges.map(edge => <div key={edge.id} className="flow-forecast-row is-edge">
      <strong>{byId.get(edge.from).title} <span aria-hidden="true">→</span> {byId.get(edge.to).title}</strong>
      <NumberField label="Taxa" suffix="%" value={forecastRate(edge)} readOnly={readOnly} max={100} onChange={value => setRate(edge.id, value)}/>
      <small>{active.edges[edge.id]?.rate == null ? 'Sem taxa' : `~${count(active.edges[edge.id].sessions)} pessoas no cenário ${FORECAST_SCENARIOS.find(item => item.id === scenario).label.toLowerCase()}`}</small>
    </div>)}</section>
    <section className="flow-forecast-group" aria-label="Conversões"><h3>Valor por conversão</h3>{conversions.length ? conversions.map(node => <div key={node.id} className="flow-forecast-row">
      <strong>{node.title}</strong>
      <NumberField label="Valor" suffix="R$" value={node.forecast?.value} readOnly={readOnly} max={1e9} onChange={value => setNode(node.id, 'value', value)}/>
    </div>) : <p>Adicione uma conversão para calcular receita e custo por resultado.</p>}</section>
  </ReportsPanelShell>;
}
