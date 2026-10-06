import React, {useCallback, useEffect, useMemo, useState} from 'react';
import {CaduBadge} from '../cadu-design-system/components/CaduBadge.jsx';
import {CaduButton} from '../cadu-design-system/components/CaduButton.jsx';
import {Icon} from '../cadu-design-system/components/Icon.jsx';
import {Illustration} from './Illustration.jsx';
import {PlannerHeader} from './PlannerHeader.jsx';
import {FREQUENCIES} from './RadarWizard.jsx';

const WATCH_STATUS = {ativo: ['Ativo', 'success'], pausado: ['Pausado', 'neutral'], sem_credito: ['Sem créditos', 'warning']};
const RUN_STATUS = {done: ['Concluída', 'success'], running: ['Em andamento', 'brand'], failed: ['Falhou', 'neutral'], queued: ['Na fila', 'neutral'], cancelled: ['Cancelada', 'neutral']};
const tokens = value => Number(value || 0).toLocaleString('pt-BR');
const when = value => value ? new Date(value).toLocaleString('pt-BR', {day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit'}) : '—';
const frequencyLabel = value => FREQUENCIES.find(([id]) => id === value)?.slice(1).join(' ') || '';

/**
 * "Meus radares": os radares ativos (buscas que se repetem sozinhas) e o histórico de consultas.
 * Fica separada do "Novo radar" de propósito: aqui só se lê e se gerencia, ali se cria.
 */
export function RadarListPage({boot, request, notify}) {
  const enabled = Boolean(boot.features?.radar);
  const [watches, setWatches] = useState(null);
  const [runs, setRuns] = useState(null);
  const [busy, setBusy] = useState('');
  const names = useMemo(() => Object.fromEntries([...(boot.contextBar?.brands || []), ...(boot.contextBar?.projects || [])].map(item => [item.ref, item.name])), [boot.contextBar]);

  const load = useCallback(async () => {
    const [watchData, runData] = await Promise.all([request('/radar/watches'), request('/radar/runs?limit=40')]);
    setWatches(watchData.watches || []);
    setRuns(runData.runs || []);
  }, [request]);
  useEffect(() => { if (enabled) load().catch(error => { setWatches([]); setRuns([]); notify({tone: 'error', message: error.message}); }); }, [enabled, load, notify]);
  // Uma consulta em andamento atualiza sozinha.
  useEffect(() => {
    if (!(runs || []).some(run => run.status === 'running')) return undefined;
    const timer = window.setTimeout(() => load().catch(() => {}), 4000);
    return () => window.clearTimeout(timer);
  }, [runs, load]);

  const act = async (watch, action) => {
    setBusy(watch.id);
    try {
      if (action === 'delete') {
        if (!window.confirm(`Apagar o radar "${watch.name}"? As consultas já feitas continuam no histórico.`)) return;
        await request(`/radar/watches/${watch.id}`, {method: 'DELETE'});
      } else {
        await request(`/radar/watches/${watch.id}`, {method: 'PATCH', body: JSON.stringify({status: action})});
      }
      await load();
    } catch (error) {
      notify({tone: 'error', message: error.message});
    } finally {
      setBusy('');
    }
  };

  const header = <PlannerHeader title="Meus radares" description="Os radares que rodam sozinhos e as buscas que você já fez."
    meta={!enabled && <CaduBadge tone="brand">Em breve</CaduBadge>}
    actions={enabled && <CaduButton href={boot.urls.radar}><Icon name="plus" size={16}/>Novo radar</CaduButton>}/>;
  if (!enabled) return header;
  const loading = watches === null || runs === null;

  return <>
    {header}
    <section className="radar-list" aria-labelledby="radar-watches-title">
      <h2 id="radar-watches-title">Radares ativos<span>{(watches || []).filter(watch => watch.status === 'ativo').length}</span></h2>
      {loading ? <p className="planner-muted">Carregando…</p> : watches.length === 0 ? <div className="radar-empty-result">
        <Illustration slot="radar-empty"/>
        <div><strong>Você ainda não tem radares ativos.</strong>
          <p className="planner-muted">Monte uma busca em &quot;Novo radar&quot; e ligue &quot;Me avise quando houver novidade&quot;. O Radar repete a busca de 1 a 3 vezes por dia.</p>
          <CaduButton size="sm" href={boot.urls.radar}>Criar o primeiro radar</CaduButton></div>
      </div> : <ul className="radar-watches">
        {watches.map(watch => {
          const status = WATCH_STATUS[watch.status] || WATCH_STATUS.ativo;
          return <li key={watch.id} className={`radar-watch is-${watch.status}`}>
            <div className="radar-watch__main">
              <strong>{watch.name}</strong>
              <small>{[names[watch.brand_ref], names[watch.project_ref]].filter(Boolean).join(' · ') || 'Sem marca'} · {frequencyLabel(watch.frequency)}</small>
              <small>Última busca: {when(watch.last_run_at)}{watch.status === 'ativo' && <> · Próxima: {when(watch.next_run_at)}</>} · {watch.runs} {watch.runs === 1 ? 'consulta' : 'consultas'}</small>
              {watch.status === 'sem_credito' && <small className="is-warning">Os créditos acabaram. Recarregue e retome o radar.</small>}
            </div>
            <CaduBadge tone={status[1]}>{status[0]}</CaduBadge>
            <span className="radar-watch__actions">
              {watch.status === 'ativo'
                ? <CaduButton size="sm" variant="secondary" loading={busy === watch.id} onClick={() => act(watch, 'pausado')}>Pausar</CaduButton>
                : <CaduButton size="sm" variant="secondary" loading={busy === watch.id} onClick={() => act(watch, 'ativo')}>Retomar</CaduButton>}
              <CaduButton size="sm" variant="tertiary" disabled={busy === watch.id} onClick={() => act(watch, 'delete')}>Apagar</CaduButton>
            </span>
          </li>;
        })}
      </ul>}
    </section>

    <section className="radar-list" aria-labelledby="radar-runs-title">
      <h2 id="radar-runs-title">Consultas realizadas<span>{(runs || []).length}</span></h2>
      {loading ? null : runs.length === 0 ? <p className="planner-muted">Nenhuma consulta ainda. As buscas que você fizer aparecem aqui, com o que acharam e o que custaram.</p> : <div className="radar-runs" role="table" aria-label="Consultas realizadas">
        <div className="radar-runs__head" role="row"><span>Quando</span><span>Tema</span><span>Resultado</span><span>Custo</span><span/></div>
        {runs.map(run => {
          const status = RUN_STATUS[run.status] || RUN_STATUS.done;
          const subject = run.focus || [names[run.brand_ref], names[run.project_ref]].filter(Boolean).join(' · ') || 'Busca sem tema';
          return <a key={run.id} className="radar-runs__row" role="row" href={`${boot.urls.radar}?run=${encodeURIComponent(run.id)}`}>
            <span>{when(run.created_at)}<small>{run.trigger === 'agendado' ? 'Radar ativo' : 'Manual'}</small></span>
            <span><b title={subject}>{subject}</b><small>{names[run.brand_ref] || ''}</small></span>
            <span><CaduBadge tone={status[1]}>{status[0]}</CaduBadge>
              {run.status === 'done' && <small>{Number(run.opportunities)} {Number(run.opportunities) === 1 ? 'ângulo' : 'ângulos'}</small>}</span>
            <span>{tokens(run.tokens)}<small>tokens</small></span>
            <Icon name="chevron" size={16}/>
          </a>;
        })}
      </div>}
    </section>
  </>;
}
