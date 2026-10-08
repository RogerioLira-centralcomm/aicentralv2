import React, {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {CaduBadge} from '../cadu-design-system/components/CaduBadge.jsx';
import {Icon} from '../cadu-design-system/components/Icon.jsx';
import {PlannerHeader} from './PlannerHeader.jsx';
import {RadarDetail} from './RadarDetail.jsx';
import {PENDING_STEPS, RunChain} from './RadarRun.jsx';
import {RadarHub} from './RadarHub.jsx';
import {RADAR_DRAFT_KEY, RadarWizard} from './RadarWizard.jsx';

export function RadarPage({boot, request, notify, context}) {
  const enabled = Boolean(boot.features?.radar);
  const runId = new URLSearchParams(window.location.search).get('run');
  const creating = new URLSearchParams(window.location.search).get('novo') === '1';
  const [run, setRun] = useState(null);
  const [loading, setLoading] = useState(Boolean(runId));
  const [starting, setStarting] = useState(false);
  const [pending, setPending] = useState({focus: ''});
  const [planning, setPlanning] = useState('');
  const poll = useRef(null);
  const names = useMemo(() => Object.fromEntries([...(boot.contextBar?.brands || []), ...(boot.contextBar?.projects || [])].map(item => [item.ref, item.name])), [boot.contextBar]);

  const load = useCallback(async id => {
    const data = await request(`/radar/runs/${id}`);
    setRun(data.run || null);
    return data.run;
  }, [request]);

  useEffect(() => {
    if (!enabled || !runId) return;
    load(runId).catch(() => notify({tone: 'error', message: 'Não encontramos esta busca.'})).finally(() => setLoading(false));
  }, [enabled, runId, load, notify]);

  useEffect(() => {
    window.clearTimeout(poll.current);
    if (run?.status === 'running') poll.current = window.setTimeout(() => load(run.id).catch(() => {}), 2000);
    return () => window.clearTimeout(poll.current);
  }, [run, load]);

  // O botão Voltar do navegador sai de ?run= e volta para o wizard.
  useEffect(() => {
    const back = () => { if (!new URLSearchParams(window.location.search).get('run')) setRun(null); };
    window.addEventListener('popstate', back);
    return () => window.removeEventListener('popstate', back);
  }, []);

  const start = async fields => {
    setPending({focus: fields.focus});
    setStarting(true);
    try {
      const {watch, ...body} = fields;
      const data = await request('/radar/runs', {method: 'POST', body: JSON.stringify(body)});
      let watchError = '';
      if (watch) {
        // O radar ativo é um extra: se falhar, a busca já começou e o aviso diz o que faltou.
        try { await request('/radar/watches', {method: 'POST', body: JSON.stringify({...body, frequency: watch.frequency})}); }
        catch (error) { watchError = error.message; }
      }
      try { window.sessionStorage.removeItem(RADAR_DRAFT_KEY); } catch { /* the draft is only a convenience */ }
      window.history.pushState({}, '', `${boot.urls.radar}?run=${encodeURIComponent(data.run.id)}`);
      setRun(data.run);
      if (watchError) notify({tone: 'error', message: `A busca começou, mas o radar ativo não foi criado: ${watchError}`});
      else if (watch) notify({tone: 'success', message: 'Radar ativo criado. Ele aparece em Meus radares.'});
    } catch (error) {
      notify({tone: 'error', message: error.message});
    } finally {
      setStarting(false);
    }
  };
  const createPlan = async item => {
    setPlanning(item.id);
    try {
      const data = await request(`/radar/opportunities/${item.id}/plan`, {method: 'POST', body: JSON.stringify({})});
      window.location.assign(`${boot.urls.plans}/${encodeURIComponent(data.plan.id)}`);
    } catch (error) {
      notify({tone: 'error', message: error.message});
      setPlanning('');
    }
  };

  if (!enabled) {
    return <PlannerHeader title="Radar" description="O que está em buzz agora e os ângulos para falar de um conceito."
      meta={<CaduBadge tone="brand">Em breve</CaduBadge>}/>;
  }
  if (!runId && !run && !creating) return <RadarHub boot={boot} request={request} notify={notify}/>;
  if (!runId && !run) {
    // Ao clicar em buscar a animação entra na hora, sem esperar a resposta; se falhar, o wizard volta com o rascunho.
    return <>
      <div hidden={starting}><RadarWizard boot={boot} request={request} busy={starting} onSubmit={start} context={context}/></div>
      {starting && <>
        <PlannerHeader title="Radar" description="O que está em buzz agora e os ângulos para falar de um conceito."/>
        <RunChain run={{status: 'running', focus: pending.focus, tokens: 0, steps: PENDING_STEPS}}/>
      </>}
    </>;
  }
  if (loading && !run) return <PlannerHeader title="Radar" description="Carregando a busca…"/>;

  if (!run) return null;
  return <RadarDetail boot={boot} run={run} names={names} onPlan={createPlan} planning={planning}/>;
}

/** Compact Radar block for the Planner home. */
export function RadarTeaser({boot}) {
  return <a className="planner-radar-teaser" href={boot.urls.radar}>
    <span className="planner-discover__icon" aria-hidden="true"><Icon name="pulse" size={18}/></span>
    <strong>Radar</strong>
    {boot.features?.radar ? <Icon name="chevron" size={16}/> : <CaduBadge tone="brand">Em breve</CaduBadge>}
    <small>O que está em buzz agora e os ângulos para falar de um conceito. Cada ângulo abre um planejamento.</small>
  </a>;
}
