import React, {useEffect, useState} from 'react';
import {CaduButton} from '../cadu-design-system/components/CaduButton.jsx';
import {CaduBadge} from '../cadu-design-system/components/CaduBadge.jsx';
import {CaduEmptyState} from '../cadu-design-system/components/CaduEmptyState.jsx';
import {CaduSelectField, CaduTextAreaField} from '../cadu-design-system/components/CaduField.jsx';
import {CaduInput} from '../cadu-design-system/components/CaduInput.jsx';
import {Icon} from '../cadu-design-system/components/Icon.jsx';
import {PlannerPanel} from './PlannerUi.jsx';
import {OBJECTIVES, contextQuery, moduleUrl, newPlanUrl, objectiveLabel} from './api.js';
import {RadarTeaser} from './Radar.jsx';
import {PlannerHeader} from './PlannerHeader.jsx';
import {DRAFT_KEY, PlanWizard} from './PlanWizard.jsx';

export const planStatusLabel = plan => plan.status_label || {draft: 'Rascunho', ready: 'Pronto para revisão'}[plan.status] || 'Em andamento';
export const planStatusTone = plan => plan.status === 'ready' ? 'success' : 'neutral';

const DISCOVER = [
  ['canais', 'share', 'Canais', 'Social, busca, vídeo, áudio e mídia exterior.'],
  ['audiencias', 'users', 'Audiências', 'Públicos com tamanho e contexto de uso.'],
  ['formatos', 'table', 'Formatos', 'Especificações e finalidade de cada peça.'],
  ['interativos', 'plugin', 'Interativos', 'Formatos com interação para engajar.'],
  ['portais', 'library', 'Portais', 'Veículos com audiência pública verificável.'],
  ['places', 'browser', 'Places', 'Pontos físicos e circulação.'],
];
const STATUS_FILTERS = [['', 'Todos'], ['draft', 'Rascunhos'], ['ready', 'Prontos']];

export function relativeDate(value) {
  const date = value ? new Date(value) : null;
  if (!date || Number.isNaN(date.getTime())) return '—';
  const days = Math.floor((Date.now() - date.getTime()) / 86400000);
  if (days <= 0) return 'Hoje';
  if (days === 1) return 'Ontem';
  if (days < 7) return `Há ${days} dias`;
  return date.toLocaleDateString('pt-BR', {day: '2-digit', month: 'short', year: days > 300 ? 'numeric' : undefined});
}

const planHref = (urls, plan) => `${urls.plans}/${encodeURIComponent(plan.id)}`;

/** Plans as a table: name, who it is for, objective, size, status and last change. */
export function PlanTable({plans, urls, compact = false}) {
  return <div className="pl-table" role="table" aria-label="Planos de mídia">
    <div className="pl-table__row pl-table__head" role="row">
      <span role="columnheader">Plano</span>
      {!compact && <span role="columnheader">Anunciante</span>}
      <span role="columnheader">Objetivo</span>
      <span role="columnheader" className="is-num">Itens</span>
      <span role="columnheader">Status</span>
      <span role="columnheader">Atualizado</span>
    </div>
    {plans.map(plan => <a key={plan.id} className="pl-table__row" role="row" href={planHref(urls, plan)}>
      <span role="cell" className="pl-table__name"><strong>{plan.title}</strong>{plan.campaign_name && plan.campaign_name !== plan.title && <small>{plan.campaign_name}</small>}</span>
      {!compact && <span role="cell">{plan.advertiser_name || '—'}</span>}
      <span role="cell">{plan.objective ? objectiveLabel(plan.objective) : '—'}</span>
      <span role="cell" className="is-num">{Number(plan.item_count || 0)}</span>
      <span role="cell"><CaduBadge tone={planStatusTone(plan)}>{planStatusLabel(plan)}</CaduBadge></span>
      <span role="cell" className="pl-table__muted">{relativeDate(plan.updated_at)}</span>
    </a>)}
  </div>;
}

function FirstPlan({urls}) {
  return <section className="pl-first">
    <div>
      <span className="planner-section-label">Planejamento com o Cadu</span>
      <h2>Monte o primeiro plano junto com o Cadu</h2>
      <p>Você traz o contexto; o Cadu propõe praças, audiências, canais e verba, uma seção por vez, e você decide.</p>
      <CaduButton size="md" href={newPlanUrl(urls)}>Começar um planejamento</CaduButton>
    </div>
    <ol className="pl-first__steps">
      <li><strong>Contexto</strong><small>Marca, projeto, objetivo e o que já se sabe.</small></li>
      <li><strong>Seção por seção</strong><small>O Cadu propõe e explica; você aceita, ajusta ou recusa.</small></li>
      <li><strong>Plano pronto para proposta</strong><small>Composição, distribuição e envio ao time comercial.</small></li>
    </ol>
  </section>;
}

export function PlannerHome({boot, plans}) {
  const urls = boot.urls;
  const latest = plans[0];
  return <>
    <PlannerHeader title="Planejamento de mídia" withContext
      actions={<CaduButton href={newPlanUrl(urls)}><Icon name="plus" size={16}/>Novo planejamento</CaduButton>}/>
    <div className="pl-home">
      <div className="pl-home__main">
        {latest ? <section className="planner-resume" aria-label="Plano em andamento">
          <div className="planner-resume__copy">
            <span className="planner-section-label">Continue de onde parou</span>
            <h2>{latest.title}</h2>
            <p>Próximo passo: {latest.next_step || 'revisar a composição e a distribuição do investimento'}.</p>
            {Number(latest.progress_total) > 0 && <div className="planner-progress" aria-label={`Checklist ${latest.progress_percent}% concluído`}>
              <i><b style={{width: `${Math.max(0, Math.min(100, Number(latest.progress_percent)))}%`}}/></i>
              <small>{latest.progress_complete ?? 0} de {latest.progress_total ?? 0} etapas{latest.updated_label ? ` · ${latest.updated_label}` : ''}</small>
            </div>}
          </div>
          <CaduButton size="md" href={planHref(urls, latest)}>Continuar</CaduButton>
        </section> : <FirstPlan urls={urls}/>}
        {plans.length > 0 && <section className="planner-section">
          <header className="planner-section__header"><h2>Planos recentes</h2><a href={urls.plans}>Ver todos ({plans.length})</a></header>
          <PlanTable plans={plans.slice(0, 6)} urls={urls} compact/>
        </section>}
      </div>
      <aside className="pl-home__side">
        <RadarTeaser boot={boot}/>
        <section className="pl-discover" aria-label="Descobrir referências">
          <h2>Descobrir</h2>
          {DISCOVER.map(([module, icon, label, text]) => <a key={module} href={moduleUrl(urls, module)}>
            <span className="planner-discover__icon" aria-hidden="true"><Icon name={icon} size={16}/></span>
            <span><strong>{label}</strong><small>{text}</small></span>
          </a>)}
        </section>
      </aside>
    </div>
  </>;
}

export function PlansPage({boot, plans}) {
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('');
  const term = query.trim().toLowerCase();
  const visible = plans.filter(plan => (!status || plan.status === status)
    && (!term || [plan.title, plan.campaign_name, plan.advertiser_name].some(value => String(value || '').toLowerCase().includes(term))));
  const action = <CaduButton href={newPlanUrl(boot.urls)}><Icon name="plus" size={16}/>Novo planejamento</CaduButton>;
  if (!plans.length) return <><PlannerHeader title="Planos" withContext actions={action}/><FirstPlan urls={boot.urls}/></>;
  return <>
    <PlannerHeader title="Planos" description={`${plans.length} ${plans.length === 1 ? 'plano' : 'planos'} neste cliente`} withContext actions={action}/>
    <div className="planner-toolbar">
      <CaduInput className="planner-toolbar__search" aria-label="Buscar planos" type="search" value={query} placeholder="Buscar por plano, campanha ou anunciante"
        leading={<span className="planner-toolbar__search-icon" aria-hidden="true"><Icon name="search" size={16}/></span>} onChange={event => setQuery(event.target.value)}/>
      <CaduSelectField size="md" className="planner-toolbar__category" aria-label="Status" value={status} onChange={event => setStatus(event.target.value)}
        options={STATUS_FILTERS.map(([value, label]) => ({value, label: value ? label : 'Todos os status'}))}/>
      <span className="planner-toolbar__count" aria-live="polite">{visible.length} de {plans.length}</span>
    </div>
    {visible.length ? <PlanTable plans={visible} urls={boot.urls}/>
      : <PlannerPanel className="planner-panel--flush"><CaduEmptyState title="Nenhum plano encontrado" description="Ajuste a busca ou o filtro de status."/></PlannerPanel>}
  </>;
}

/** Brand and project context from the Workspace, used to pre-fill a new plan. */
function useWorkspaceContext(request, selection) {
  const [state, setState] = useState({loading: false, context: null});
  const query = contextQuery(selection);
  useEffect(() => {
    if (!query) { setState({loading: false, context: null}); return undefined; }
    let current = true;
    setState(previous => ({...previous, loading: true}));
    request(`/context?${query}`).then(data => { if (current) setState({loading: false, context: data.context}); })
      .catch(() => { if (current) setState({loading: false, context: null}); });
    return () => { current = false; };
  }, [request, query]);
  return state;
}

function ContextSummary({context}) {
  const sources = [context?.brand && ['Marca', context.brand], context?.project && ['Projeto', context.project]].filter(Boolean);
  if (!sources.length) return <div className="planner-aside__block">
    <h2>Comece pelo contexto</h2>
    <p>Escolha marca e projeto no topo da página. O Cadu usa público, posicionamento e a direção do projeto como ponto de partida.</p>
  </div>;
  return <>{sources.map(([label, source]) => <div key={label} className="planner-aside__block">
    <span className="planner-section-label">{label}</span>
    <h2>{source.name}</h2>
    <dl>{(source.fields || []).slice(0, 5).map(field => <div key={field.key}><dt>{field.label}</dt>
      <dd>{Array.isArray(field.value) ? field.value.join(', ') : field.value}</dd></div>)}</dl>
  </div>)}</>;
}

export function PlanCreatePage({boot, request, notify, selection}) {
  const [busy, setBusy] = useState(false);
  const {context} = useWorkspaceContext(request, selection);
  const suggestions = context?.suggestions || {};
  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    try {
      const briefing = Object.fromEntries(new FormData(event.currentTarget));
      const data = await request('/plans', {method: 'POST', body: JSON.stringify({
        ...briefing, briefing,
        brand_ref: selection?.brand_ref || null, project_ref: selection?.project_ref || null,
      })});
      window.location.assign(`${boot.urls.plans}/${encodeURIComponent(data.plan.id)}`);
    } catch (error) {
      notify({tone: 'error', message: error.message});
      setBusy(false);
    }
  }
  const [fullForm, setFullForm] = useState(() => new URLSearchParams(window.location.search).get('modo') === 'formulario');
  async function createFromWizard(fields) {
    setBusy(true);
    try {
      const data = await request('/plans', {method: 'POST', body: JSON.stringify({...fields,
        brand_ref: selection?.brand_ref || null, project_ref: selection?.project_ref || null})});
      try { window.sessionStorage.removeItem(DRAFT_KEY); } catch { /* the draft is only a convenience */ }
      window.location.assign(`${boot.urls.plans}/${encodeURIComponent(data.plan.id)}`);
    } catch (error) {
      notify({tone: 'error', message: error.message});
      setBusy(false);
    }
  }
  if (!fullForm) return <PlanWizard urls={boot.urls} suggestions={suggestions} busy={busy} onSubmit={createFromWizard} onFullForm={() => setFullForm(true)}/>;
  // Remount the form when the context arrives so its suggestions become the defaults.
  const formKey = [context?.brand?.ref, context?.project?.ref].join('|');
  return <>
    <PlannerHeader crumbs={[['Planos', boot.urls.plans]]} title="Novo planejamento" withContext
      description="Comece pelo que você já sabe. O Cadu monta o resto com você."
      actions={<><CaduButton variant="secondary" href={boot.urls.plans}>Cancelar</CaduButton>
        <CaduButton type="submit" form="planner-new" loading={busy}>Começar planejamento</CaduButton></>}/>
    <div className="planner-split">
      <form id="planner-new" key={formKey} className="planner-form" onSubmit={submit}>
        <PlannerPanel title="Campanha">
          <div className="planner-fields">
            <CaduInput className="is-wide" label="Nome do plano" name="title" required minLength="2" maxLength="180" placeholder="Ex.: Lançamento de verão" autoFocus
              defaultValue={suggestions.campaign_name || ''}/>
            <CaduInput label="Anunciante" name="advertiser_name" placeholder="Marca ou anunciante" defaultValue={suggestions.advertiser_name || ''}/>
            <CaduInput label="Campanha" name="campaign_name" placeholder="Se já tiver nome" defaultValue={suggestions.campaign_name || ''}/>
          </div>
        </PlannerPanel>
        <PlannerPanel title="Objetivo, verba e praça" description="Pode deixar em branco. O Cadu ajuda a definir.">
          <div className="planner-fields planner-fields--3">
            <CaduSelectField label="Objetivo" name="objective" options={OBJECTIVES.map(([value, label]) => ({value, label}))}/>
            <CaduInput label="Investimento" name="budget" inputMode="decimal" placeholder="Ex.: R$ 50.000"/>
            <CaduInput label="Período" name="period" placeholder="Ex.: mai a jul de 2027"/>
            <CaduInput label="Praça" name="geography" placeholder="Ex.: Brasil, SP, BH"/>
            <CaduInput className="is-span-2" label="KPIs" name="kpis" placeholder="Ex.: alcance, leads ou vendas"/>
          </div>
        </PlannerPanel>
        <PlannerPanel title="O que o Cadu precisa saber">
          <CaduTextAreaField aria-label="Notas para o planejamento" name="notes" rows={5} defaultValue={suggestions.notes || ''}
            placeholder="Restrições, datas, concorrentes, aprendizados de campanhas anteriores."/>
        </PlannerPanel>
      </form>
      <aside className="planner-aside">
        <ContextSummary context={context}/>
        <div className="planner-aside__block">
          <h2>Como continua</h2>
          <ul><li>O plano é dividido em seções: praças, audiências, canais, formatos, verba e criativos.</li>
            <li>Em cada seção o Cadu propõe e explica. Você aceita, ajusta ou recusa.</li>
            <li>O rascunho fica salvo para continuar depois.</li></ul>
        </div>
      </aside>
    </div>
  </>;
}
