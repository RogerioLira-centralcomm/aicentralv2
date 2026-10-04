import React, {useCallback, useEffect, useMemo, useState} from 'react';
import StudioNavbar from '../cadu-studio-ui/StudioNavbar';
import Matrix from './Matrix';
import LiveQueue from './LiveQueue';
import NewTest, {EMPTY_FORM} from './NewTest';
import {ModelsView, ParametersView, ProposalsView, ReferencesView, ScenariosNotes} from './Panels';
import RunDetail from './RunDetail';
import {MockupsView} from './Mockups';
import {createApi, seconds, usd} from './ui';

const TABS = [['matrix', 'Matriz ao vivo'], ['new', 'Novo teste'], ['mockups', 'Mockups'], ['references', 'Peças e referências'], ['models', 'Modelos'], ['params', 'Parâmetros vs Studio'], ['scenarios', 'Cenários'], ['proposals', 'Recomendações']];

function readTab() {
  try { return localStorage.getItem('cadu-lab-tab') || 'matrix'; } catch (_error) { return 'matrix'; }
}

export default function LabApp({bootstrap}) {
  const api = useMemo(() => createApi(bootstrap), [bootstrap]);
  const [state, setState] = useState(null);
  const [error, setError] = useState('');
  const [tab, setTabState] = useState(readTab);
  const [blind, setBlind] = useState(false);
  const [openRunId, setOpenRunId] = useState(null);
  const [busyScenario, setBusyScenario] = useState('');
  const [seed, setSeed] = useState(null);
  const setTab = value => { setTabState(value); try { localStorage.setItem('cadu-lab-tab', value); } catch (_error) { /* private mode */ } };

  const load = useCallback(async () => {
    try { setState(await api.get('/state')); setError(''); } catch (exc) { setError(exc.message); }
  }, [api]);
  const refreshRuns = useCallback(async () => {
    try { const data = await api.get('/runs'); setState(current => current ? {...current, runs: data.runs} : current); } catch (_error) { /* next tick */ }
  }, [api]);
  useEffect(() => { load(); }, [load]);
  const active = state?.runs.some(run => ['queued', 'running'].includes(run.status));
  const evaluating = state?.runs.some(run => run.status === 'succeeded' && !run.typesafe);
  useEffect(() => {
    const timer = setInterval(refreshRuns, active || evaluating ? 4000 : 20000);
    return () => clearInterval(timer);
  }, [active, evaluating, refreshRuns]);

  if (!state) return <div className="lab-shell"><StudioNavbar active="lab" links={bootstrap.links} user={bootstrap.user}/>
    <main className="lab-main"><p className="lab-muted">{error || 'Carregando o Lab…'}</p></main></div>;

  const runs = state.runs;
  const done = runs.filter(run => run.status === 'succeeded');
  const spent = done.reduce((sum, run) => sum + (run.actual_cost_usd || 0), 0);
  const latencies = done.map(run => run.latency_ms).filter(Boolean);
  const openRun = runs.find(run => run.run_id === openRunId);
  const setNotes = notes => setState(current => ({...current, notes}));
  const updateRun = run => setState(current => ({...current, runs: current.runs.map(item => item.run_id === run.run_id ? run : item)}));

  const runScenario = async (scenario, formatKey, models) => {
    const busyKey = formatKey ? `${scenario.key}@${formatKey}` : scenario.key;
    setBusyScenario(busyKey); setError('');
    try {
      const data = await api.post(`/scenarios/${scenario.key}/run`, {models: models.map(model => model.model_key), format_key: formatKey || undefined});
      if (!data.run_ids.length) setError(`“${scenario.title}” já tem geração concluída em todos os modelos.`);
      await load();
    } catch (exc) { setError(exc.message); } finally { setBusyScenario(''); }
  };
  const seedBrief = ref => {
    const anatomy = ref.anatomy || {};
    const people = (anatomy.people || []).map(person => [person.description, person.pose, person.gaze].filter(Boolean).join(' — '));
    setSeed({...EMPTY_FORM, brand_id: ref.brand_id || '', title: `Inspirado em ${ref.label}`,
      brief: {...EMPTY_FORM.brief, archetype: (state.archetypes || []).some(item => item.key === anatomy.archetype) ? anatomy.archetype : '',
        copy: anatomy.copy || {}, casting: people, devices: anatomy.devices || [], source_ref_id: ref.ref_id},
      references: [{ref_id: ref.ref_id, role: 'COMPOSITION', label: ref.label}]});
    setTab('new');
  };
  const useMockup = mask => {
    const labFormat = (state.formats || []).find(item => item.key === mask.format || (mask.format === 'youtube-16x9' && item.key === 'wide-16x9'));
    setSeed({...EMPTY_FORM, pipeline: 'studio', formats: [labFormat?.key || EMPTY_FORM.formats[0]], mockup: {mode: 'image', family: mask.family, id: mask.id}});
    setTab('new');
  };
  const cancelQueue = async () => {
    try { await api.post('/runs/cancel', {}); await load(); } catch (exc) { setError(exc.message); }
  };
  const regenerate = async run => {
    try { await api.post(`/experiments/${run.experiment_id}/runs`, {models: [run.model_key]}); setOpenRunId(null); await refreshRuns(); }
    catch (exc) { setError(exc.message); }
  };

  return <div className="lab-shell">
    <StudioNavbar active="lab" links={bootstrap.links} user={bootstrap.user}/>
    <main className="lab-main">
      <header className="lab-hero">
        <div>
          <p className="lab-eyebrow">Experimental · só para a equipe</p>
          <h1>Lab de modelos de imagem</h1>
          <p className="lab-muted">Mesmo pedido, mesma marca auditada, uma geração por vez em cada modelo. Custo, tempo e avaliação TypeSafe de cada uma; nada vai para produção sem revisão.</p>
        </div>
        <dl className="lab-kpis">
          <div><dt>Gerações</dt><dd>{done.length}<small>/{runs.length}</small></dd></div>
          <div><dt>Gasto</dt><dd>{usd(spent)}</dd></div>
          <div><dt>Tempo médio</dt><dd>{seconds(latencies.length ? latencies.reduce((a, b) => a + b, 0) / latencies.length : null)}</dd></div>
          <div><dt>Modelos</dt><dd>{state.models.filter(model => !model.capabilities?.retired).length}</dd></div>
        </dl>
      </header>
      <nav className="lab-tabs" role="tablist" aria-label="Seções do Lab">
        {TABS.map(([key, label]) => <button key={key} type="button" role="tab" aria-selected={tab === key} onClick={() => setTab(key)}>
          {label}
        </button>)}
        <span className="lab-tabs__spacer"/>
        {active && <span className="lab-live"><i className="lab-spinner" aria-hidden="true"/> gerando…</span>}
        <label className="lab-check"><input type="checkbox" checked={blind} onChange={event => setBlind(event.target.checked)}/> Avaliação cega</label>
      </nav>
      {error && <p className="lab-alert" role="alert">{error}</p>}
      {tab === 'matrix' && <LiveQueue runs={runs} models={state.models} formats={state.formats || []} blind={blind} onOpen={run => setOpenRunId(run.run_id)} onCancel={cancelQueue}/>}
      {tab === 'matrix' && <Matrix state={state} blind={blind} onOpen={run => setOpenRunId(run.run_id)} onRunScenario={runScenario} busyScenario={busyScenario}/>}
      {tab === 'new' && <NewTest state={state} api={api} seed={seed} onCreated={data => { load(); if (data?.run_ids) { setSeed(null); setTab('matrix'); } }}/>}
      {tab === 'mockups' && <MockupsView state={state} onUse={useMockup}/>}
      {tab === 'models' && <ModelsView state={state} api={api} onNotes={setNotes}/>}
      {tab === 'params' && <ParametersView state={state}/>}
      {tab === 'scenarios' && <ScenariosNotes state={state} api={api} onNotes={setNotes}/>}
      {tab === 'references' && <ReferencesView state={state} api={api} onChanged={load} onSeedBrief={seedBrief}/>}
      {tab === 'proposals' && <ProposalsView state={state}/>}
    </main>
    {openRun && <RunDetail run={openRun} models={state.models} state={state} api={api} blind={blind}
      onClose={() => setOpenRunId(null)} onUpdated={updateRun} onNotes={setNotes} onRegenerate={regenerate}/>}
  </div>;
}
