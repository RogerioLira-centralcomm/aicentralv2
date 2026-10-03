import React, {useEffect, useState} from 'react';
import {BookmarkCheck, Plus, Trash01} from '@untitledui/icons';
import {Button} from '../cadu-design-system/untitled-kit/button.tsx';
import {ReportsFieldInput} from './ReportsFieldInput.jsx';
import {ReportsNativeSelect} from './ReportsNativeSelect.jsx';
import {json} from './reportsCommon.jsx';
import {UNITS, VARIABLES, formatMetric, formulaError, metricResult} from './reportMetrics.js';

const API = '/connect/api/v2/reports';
const blank = () => ({id: `m-${Date.now().toString(36)}`, name: '', kind: 'formula', formula: '', unit: 'count', direction: 'higher', target: '', definition: ''});

/** Custom metrics of one report: formula over the period's numbers or a reviewed manual value; can be saved to the client's catalogue. */
export function ReportMetricsEditor({metrics, onChange, values, disabled, save, csrf}) {
  const [catalog, setCatalog] = useState(null);
  const [savedName, setSavedName] = useState('');
  const loadCatalog = () => json(`${API}/custom-metrics`).then(setCatalog).catch(() => setCatalog({ready: false, metrics: []}));
  useEffect(() => {loadCatalog();}, []);
  const set = (index, patch) => onChange(metrics.map((metric, at) => at === index ? {...metric, ...patch} : metric));
  const fromCatalog = id => {
    const item = catalog.metrics.find(metric => String(metric.id) === id);
    if (item) onChange([...metrics, {...blank(), name: item.name, kind: item.kind, formula: item.formula || '', unit: item.unit, direction: item.direction, target: item.target ?? '', definition: item.definition}]);
  };
  const toCatalog = async metric => {
    try {await save('/custom-metrics', {metric}, false); setSavedName(metric.name); setTimeout(() => setSavedName(''), 2500); loadCatalog();} catch { /* banner shows it */ }
  };
  const unused = (catalog?.metrics || []).filter(item => !metrics.some(metric => metric.name.toLowerCase() === item.name.toLowerCase()));
  return <div className="flex flex-col gap-3 px-2">
    {metrics.map((metric, index) => {
      const problem = metric.kind === 'formula' ? formulaError(metric.formula) : metric.value === '' || metric.value == null ? 'Informe o valor.' : '';
      const result = problem ? null : metricResult(metric, values);
      const target = metric.target === '' || metric.target == null ? null : Number(String(metric.target).replace(',', '.'));
      const met = result != null && target != null ? (metric.direction === 'lower' ? result <= target : result >= target) : null;
      return <div key={metric.id} className="flex flex-col gap-3 rounded-lg p-3 ring-1 ring-secondary ring-inset">
        <div className="flex flex-wrap items-start gap-3">
          <div className="min-w-48 flex-1"><ReportsFieldInput label="Nome" size="sm" disabled={disabled} maxLength={80} value={metric.name} onChange={event => set(index, {name: event.target.value})} placeholder="Ex.: Custo por lead do fluxo"/></div>
          <div className="w-36"><ReportsNativeSelect label="Origem" size="sm" disabled={disabled} value={metric.kind} onChange={event => set(index, {kind: event.target.value})}><option value="formula">Fórmula</option><option value="manual">Valor manual</option></ReportsNativeSelect></div>
          <div className="w-40"><ReportsNativeSelect label="Unidade" size="sm" disabled={disabled} value={metric.unit} onChange={event => set(index, {unit: event.target.value})}>{UNITS.map(([key, label]) => <option key={key} value={key}>{label}</option>)}</ReportsNativeSelect></div>
          <div className="text-right"><span className="block text-xs text-tertiary">Agora</span><strong className="text-lg text-primary tabular-nums">{formatMetric(result, metric.unit)}</strong>
            {met != null && <span className={`block text-xs ${met ? 'text-success-primary' : 'text-error-primary'}`}>{met ? 'Meta atingida' : 'Fora da meta'}</span>}</div>
        </div>
        {metric.kind === 'formula'
          ? <ReportsFieldInput label="Fórmula" size="sm" disabled={disabled} maxLength={200} value={metric.formula} onChange={event => set(index, {formula: event.target.value})}
              placeholder="custo / conversoes_fluxo" hint={problem || `Variáveis: ${Object.keys(VARIABLES).join(', ')}. Use + - * / e parênteses.`}/>
          : <div className="grid gap-3 sm:grid-cols-2">
              <ReportsFieldInput label="Valor" size="sm" inputMode="decimal" disabled={disabled} value={metric.value ?? ''} onChange={event => set(index, {value: event.target.value})} hint={problem || undefined}/>
              <ReportsFieldInput label="Evidência" size="sm" disabled={disabled} maxLength={300} value={metric.evidence || ''} onChange={event => set(index, {evidence: event.target.value})} placeholder="De onde vem o número"/>
            </div>}
        <div className="grid gap-3 sm:grid-cols-[1fr_160px_2fr]">
          <ReportsFieldInput label="Meta" size="sm" inputMode="decimal" disabled={disabled} value={metric.target ?? ''} onChange={event => set(index, {target: event.target.value})} placeholder="Opcional"/>
          <ReportsNativeSelect label="Melhor quando" size="sm" disabled={disabled} value={metric.direction} onChange={event => set(index, {direction: event.target.value})}><option value="higher">Maior</option><option value="lower">Menor</option></ReportsNativeSelect>
          <ReportsFieldInput label="Definição" size="sm" disabled={disabled} maxLength={300} value={metric.definition || ''} onChange={event => set(index, {definition: event.target.value})} placeholder="Aparece no link para o cliente"/>
        </div>
        {!disabled && <div className="flex flex-wrap gap-2">
          {catalog?.ready && metric.kind === 'formula' && <Button size="sm" color="secondary" iconLeading={BookmarkCheck} isDisabled={Boolean(problem) || !metric.name.trim()} onPress={() => toCatalog(metric)}>{savedName === metric.name ? 'Salva no catálogo' : 'Salvar no catálogo do cliente'}</Button>}
          <Button size="sm" color="tertiary-destructive" iconLeading={Trash01} onPress={() => onChange(metrics.filter((_, at) => at !== index))}>Remover</Button>
        </div>}
      </div>;
    })}
    {!disabled && <div className="flex flex-wrap items-end gap-2">
      <Button size="sm" color="secondary" iconLeading={Plus} isDisabled={metrics.length >= 20} onPress={() => onChange([...metrics, blank()])}>Nova métrica</Button>
      {unused.length > 0 && <div className="w-64"><ReportsNativeSelect size="sm" aria-label="Usar do catálogo" value="" onChange={event => fromCatalog(event.target.value)}>
        <option value="">Usar do catálogo do cliente…</option>{unused.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
      </ReportsNativeSelect></div>}
    </div>}
    {!metrics.length && <p className="text-sm text-tertiary">Nenhuma métrica. Crie uma fórmula sobre os números do período (ex.: custo ÷ conversões do fluxo) ou informe um valor revisado.</p>}
  </div>;
}
