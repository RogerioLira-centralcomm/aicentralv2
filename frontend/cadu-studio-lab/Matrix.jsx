import React, {useMemo, useState} from 'react';
import {MaskThumb, MOCKUP_MODE_LABEL, maskFor} from './Mockups';
import {Badge, FAILURE_LABEL, ROLE_LABEL, ScorePill, StatusBadge, Thumb, seconds, usd} from './ui';

export const ratioCss = ratio => {
  const [w, h] = String(ratio || '1:1').split(':').map(Number);
  return w && h ? `${w} / ${h}` : '1 / 1';
};

export function groupRuns(runs) {
  const groups = {};
  for (const run of runs) (groups[`${run.scenario_key}|${run.model_key}`] ||= []).push(run);
  for (const key of Object.keys(groups)) groups[key].sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''));
  return groups;
}

export function modelStats(runs, modelKey) {
  const own = runs.filter(run => run.model_key === modelKey && run.status === 'succeeded');
  const scores = own.map(run => run.typesafe?.scores?.overall).filter(value => value != null);
  const latencies = own.map(run => run.latency_ms).filter(Boolean);
  const failures = {};
  for (const run of own) {
    const failure = run.typesafe?.primary_failure;
    if (failure && failure !== 'none') failures[failure] = (failures[failure] || 0) + 1;
  }
  return {
    n: own.length,
    failed: runs.filter(run => run.model_key === modelKey && ['failed', 'blocked'].includes(run.status)).length,
    score: scores.length ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length) : null,
    latency: latencies.length ? latencies.reduce((a, b) => a + b, 0) / latencies.length : null,
    cost: own.reduce((sum, run) => sum + (run.actual_cost_usd || 0), 0),
    topFailure: Object.entries(failures).sort((a, b) => b[1] - a[1])[0],
  };
}

/** Matrix rows: one per scenario, one per format for multi-format scenarios, plus ad-hoc experiments. */
export function buildRows(state) {
  const formats = Object.fromEntries((state.formats || []).map(item => [item.key, item]));
  const known = new Set();
  const groups = [];
  const order = [...new Set(state.scenarios.map(item => item.group))].sort().reverse();
  for (const group of order) {
    const rows = [];
    for (const scenario of state.scenarios.filter(item => item.group === group)) {
      const list = scenario.formats?.length ? scenario.formats : [null];
      list.forEach((formatKey, index) => {
        const key = formatKey ? `${scenario.key}@${formatKey}` : scenario.key;
        known.add(key);
        rows.push({key, scenario, format: formatKey ? formats[formatKey] : null, formatKey, first: index === 0, span: list.length,
          ratio: formatKey ? formats[formatKey]?.ratio : scenario.aspect_ratio});
      });
    }
    groups.push({label: group, rows});
  }
  const adHoc = {};
  for (const run of state.runs) {
    if (known.has(run.scenario_key)) continue;
    adHoc[run.scenario_key] ||= {key: run.scenario_key, title: run.experiment_title, task: run.task, brand_id: run.brand_id,
      formatKey: run.format_key, ratio: run.aspect_ratio, created: run.created_at};
  }
  const extra = Object.values(adHoc).sort((a, b) => (b.created || '').localeCompare(a.created || '')).map(item => ({
    key: item.key, adHoc: item, format: item.formatKey ? formats[item.formatKey] : null, formatKey: item.formatKey, first: true, span: 1, ratio: item.ratio,
  }));
  if (extra.length) groups.unshift({label: 'Testes da tela e reformatações', rows: extra});
  return groups;
}

function ScenarioHead({row, brand, references, notesCount, onRun, busy, mask}) {
  const {scenario, format} = row;
  if (row.adHoc) return <div className="lab-matrix__scenario">
    <div className="lab-matrix__title"><Badge kind={row.adHoc.task === 'edit' ? 'is-edit' : 'is-generate'}>{row.adHoc.task === 'edit' ? 'Editar' : 'Gerar'}</Badge><strong>{row.adHoc.title}</strong></div>
    <small className="lab-muted">{brand?.name || 'Sem marca'} · {format?.label || row.ratio}</small>
  </div>;
  if (!row.first) return <div className="lab-matrix__scenario is-sub">
    <span className="lab-format-chip">↳ {format?.label}</span>
    {mask && <MaskThumb mask={mask} size={46}/>}
    <button type="button" className="lab-btn is-ghost is-small" onClick={() => onRun(row.formatKey)} disabled={busy}>Gerar faltantes</button>
  </div>;
  const inputs = scenario.references.map(ref => ({...ref, stored: references.find(item => item.source === 'brand_asset' && item.source_ref === String(ref.asset_id))}));
  const copy = Object.values(scenario.brief?.copy || {});
  return <div className="lab-matrix__scenario">
    <div className="lab-matrix__title">
      <Badge kind={scenario.task === 'edit' ? 'is-edit' : 'is-generate'}>{scenario.task === 'edit' ? 'Editar' : 'Gerar'}</Badge>
      <strong>{scenario.title}</strong>
    </div>
    <small className="lab-muted">{brand?.name || 'Sem marca'} · {format ? `${row.span} formato(s)` : scenario.aspect_ratio}{scenario.logo_mode === 'native' ? ' · logo nativo' : ''}</small>
    {format && <span className="lab-format-chip">{format.label}</span>}
    {scenario.pipeline === 'studio' && <span className="lab-format-chip is-studio">Studio · {MOCKUP_MODE_LABEL[scenario.mockup?.mode || 'none']}</span>}
    {mask && <MaskThumb mask={mask} size={52}/>}
    <p className="lab-matrix__variable">{scenario.variable}</p>
    {copy.length > 0 && <p className="lab-matrix__copy">“{copy.slice(0, 3).join(' · ')}”</p>}
    <div className="lab-matrix__inputs">
      {inputs.length ? inputs.map(ref => <figure key={ref.asset_id} title={`${ROLE_LABEL[ref.role]} · ${ref.label}`}>
        {ref.stored ? <img src={ref.stored.thumb_url} alt={ref.label}/> : <span className="lab-matrix__placeholder"/>}
        <figcaption>{ROLE_LABEL[ref.role]}</figcaption>
      </figure>) : <p className="lab-muted lab-tiny lab-matrix__noinput">Sem imagens: marca e briefing em texto.</p>}
    </div>
    <div className="lab-matrix__actions">
      <button type="button" className="lab-btn is-small" onClick={() => onRun(null)} disabled={busy || scenario.reserved}>
        {scenario.reserved ? 'Reservado' : row.span > 1 ? 'Gerar faltantes (todos)' : 'Gerar faltantes'}</button>
      <small className="lab-muted">{notesCount ? `${notesCount} anotação(ões)` : ''}</small>
    </div>
  </div>;
}

function Cell({runs, ratio, blind, onOpen}) {
  const run = runs?.[0];
  if (!run) return <div className="lab-matrix__cell is-empty"><Thumb ratio={ratio}/><div className="lab-cell__meta"><span className="lab-muted">Não gerado</span></div></div>;
  const score = run.typesafe?.scores?.overall;
  const failure = run.typesafe?.primary_failure;
  const cropped = run.request_summary?.cropped_to_format;
  return <div className={`lab-matrix__cell is-${run.status}`}>
    <Thumb src={run.thumb_url} ratio={ratio} status={run.status} alt={blind ? 'Geração' : `${run.model_key}`} onClick={() => onOpen(run)}>
      {run.status !== 'succeeded' && <span className="lab-thumb__status"><StatusBadge status={run.status}/></span>}
      {runs.length > 1 && <span className="lab-thumb__attempts" title="Gerações deste modelo nesta linha">×{runs.length}</span>}
      {cropped && <span className="lab-thumb__tag" title={`Recortado de ${cropped.from.join('×')}`}>recorte</span>}
    </Thumb>
    <div className="lab-cell__meta">
      <ScorePill score={score}/>
      <span>{seconds(run.latency_ms)}</span>
      <span>{usd(run.actual_cost_usd ?? run.estimated_cost_usd)}</span>
    </div>
    <small className={`lab-cell__failure${failure && failure !== 'none' ? '' : ' is-quiet'}`}>
      {run.status === 'succeeded' ? (failure ? FAILURE_LABEL[failure] || failure : 'Avaliando…') : (run.error?.message || '').slice(0, 60)}
    </small>
  </div>;
}

export default function Matrix({state, blind, onOpen, onRunScenario, busyScenario}) {
  const runGroups = useMemo(() => groupRuns(state.runs), [state.runs]);
  const rowGroups = useMemo(() => buildRows(state), [state]);
  // Groups with something queued or running stay open; idle ones fold away (the first idle group stays open when nothing is active).
  // A group the person opened or closed by hand keeps that choice.
  const [manual, setManual] = useState({});
  // Retired models keep their history in the other tabs but leave the live matrix.
  const models = state.models.filter(model => !model.capabilities?.retired);
  const brandsById = Object.fromEntries(state.brands.map(brand => [brand.id, brand]));
  const columns = `minmax(210px, 1.3fr) repeat(${models.length}, minmax(118px, 1fr))`;
  const activeLabels = new Set(rowGroups.filter(group => group.rows.some(row => models.some(model => runGroups[`${row.key}|${model.model_key}`]?.some(run => ['queued', 'running'].includes(run.status))))).map(group => group.label));
  const isOpen = label => manual[label] ?? (activeLabels.size ? activeLabels.has(label) : label === rowGroups[0]?.label);
  const toggle = label => setManual(current => ({...current, [label]: !isOpen(label)}));
  const missingFor = (rowKey) => models.filter(model => !runGroups[`${rowKey}|${model.model_key}`]?.some(run => run.status === 'succeeded'));
  return <div className="lab-matrix" role="table" aria-label="Cenários por modelo">
    <div className="lab-matrix__row is-head" role="row" style={{gridTemplateColumns: columns}}>
      <div className="lab-matrix__corner" role="columnheader"><strong>Cenário</strong><small className="lab-muted">o que varia e por quê</small></div>
      {models.map((model, index) => <div key={model.model_key} className="lab-matrix__model" role="columnheader">
        <strong>{blind ? `Modelo ${String.fromCharCode(65 + index)}` : model.label}</strong>
        {!blind && <small>{model.provider === 'openai_direct' ? 'OpenAI direto' : 'OpenRouter'} · {model.capabilities.max_references} ref.</small>}
        {model.status !== 'available' && <Badge kind="is-failed">Indisponível</Badge>}
      </div>)}
    </div>
    {rowGroups.map(group => <React.Fragment key={group.label}>
      <button type="button" className="lab-matrix__group" aria-expanded={isOpen(group.label)} onClick={() => toggle(group.label)}>
        <span aria-hidden="true">{isOpen(group.label) ? '▾' : '▸'}</span> {group.label} <small className="lab-muted">{group.rows.length} linha(s)</small>
      </button>
      {isOpen(group.label) && group.rows.map(row => {
        const scenarioKey = row.scenario?.key;
        return <div key={row.key} className={`lab-matrix__row${row.scenario?.reserved ? ' is-reserved' : ''}${row.first ? '' : ' is-sub'}`} role="row" style={{gridTemplateColumns: columns}}>
          <ScenarioHead row={row} brand={brandsById[row.scenario?.brand_id ?? row.adHoc?.brand_id]} references={state.references}
            notesCount={scenarioKey ? state.notes.filter(note => note.scope === 'scenario' && note.scope_key === scenarioKey).length : 0}
            busy={busyScenario === row.key || busyScenario === scenarioKey}
            mask={row.scenario?.pipeline === 'studio' && row.scenario.mockup?.mode !== 'none' ? maskFor(state.mockups, row.formatKey, row.scenario.mockup?.family) : null}
            onRun={formatKey => row.scenario && onRunScenario(row.scenario, formatKey, formatKey ? missingFor(`${scenarioKey}@${formatKey}`) : models)}/>
          {models.map(model => <Cell key={model.model_key} runs={runGroups[`${row.key}|${model.model_key}`]}
            ratio={ratioCss(row.ratio)} blind={blind} onOpen={onOpen}/>)}
        </div>;
      })}
    </React.Fragment>)}
    <div className="lab-matrix__row is-foot" role="row" style={{gridTemplateColumns: columns}}>
      <div className="lab-matrix__corner"><strong>Resumo</strong><small className="lab-muted">média só com n mostrado</small></div>
      {models.map(model => {
        const stats = modelStats(state.runs, model.model_key);
        return <div key={model.model_key} className="lab-matrix__stats">
          <div><ScorePill score={stats.score}/><small>n={stats.n}{stats.n < 10 ? ' · amostra pequena' : ''}</small></div>
          <span>{seconds(stats.latency)} médio</span>
          <span>{usd(stats.cost)} total</span>
          <small className="lab-muted">{stats.topFailure ? `${FAILURE_LABEL[stats.topFailure[0]]} ×${stats.topFailure[1]}` : 'sem falha recorrente'}{stats.failed ? ` · ${stats.failed} erro(s)` : ''}</small>
        </div>;
      })}
    </div>
  </div>;
}
