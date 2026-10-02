import React, {useEffect, useState} from 'react';
import {CaduBadge} from '../cadu-design-system/components/CaduBadge.jsx';
import {CaduButton} from '../cadu-design-system/components/CaduButton.jsx';
import {Icon} from '../cadu-design-system/components/Icon.jsx';
import {IllustratedWait} from './Illustration.jsx';
import {PlannerPanel} from './PlannerUi.jsx';

export const SECTION_STATES = {
  vazia: {label: 'A definir', tone: 'neutral'},
  proposta: {label: 'Proposta do Cadu', tone: 'brand'},
  aceita: {label: 'Aceita', tone: 'success'},
  editada: {label: 'Sua versão', tone: 'success'},
  travada: {label: 'Travada', tone: 'neutral'},
};

/** Plan sections in build order, with who shaped each one. */
export function SectionRail({overview, active, onSelect}) {
  if (!overview) return null;
  return <nav className="planner-rail" aria-label="Seções do plano">
    <div className="planner-progress"><i><b style={{width: `${overview.percent}%`}}/></i>
      <small>{overview.done} de {overview.total} seções definidas</small></div>
    <ol>{overview.sections.map(section => {
      const state = SECTION_STATES[section.state] || SECTION_STATES.vazia;
      return <li key={section.key}>
        <button type="button" className={`planner-rail__item is-${section.state}${active === section.key ? ' is-active' : ''}`}
          aria-current={active === section.key ? 'step' : undefined} onClick={() => onSelect(section.key)}>
          <span className="planner-rail__dot" aria-hidden="true">{['aceita', 'editada'].includes(section.state) ? <Icon name="check" size={8}/> : null}</span>
          <span className="planner-rail__copy"><strong>{section.label}</strong><small>{state.label}</small></span>
        </button>
      </li>;
    })}</ol>
  </nav>;
}

const FIELD_LABELS = {
  objective: 'Objetivo', kpis: 'KPIs', geography: 'Praças', budget: 'Investimento', period: 'Período', notes: 'Notas',
  add: 'Itens do catálogo', roles: 'Papel por canal', scenarios: 'Cenários de verba', big_idea: 'Big idea', messages: 'Mensagens', matrix: 'Matriz criativa',
};
const fieldValue = value => Array.isArray(value)
  ? value.map(item => (item && typeof item === 'object') ? (item.name || item.label || item.resource_id || JSON.stringify(item)) : item).join(', ')
  : (value && typeof value === 'object') ? JSON.stringify(value) : String(value);

function ProposalCard({proposal, label, busy, onDecide}) {
  const fields = Object.keys(proposal.payload || {});
  return <div className="planner-proposal">
    <span className="planner-section-label">Proposta para {label || proposal.section}</span>
    {proposal.rationale && <p>{proposal.rationale}</p>}
    {(proposal.questions || []).length > 0 && <ul className="planner-proposal__questions">{proposal.questions.map(question => <li key={question}>{question}</li>)}</ul>}
    {fields.length > 0 && <dl className="planner-facts">{fields.map(field => <div key={field}><dt>{FIELD_LABELS[field] || field}</dt><dd>{fieldValue(proposal.payload[field])}</dd></div>)}</dl>}
    <footer>
      <CaduButton size="sm" loading={busy} onClick={() => onDecide(proposal, 'accepted')}>Aceitar</CaduButton>
      <CaduButton size="sm" variant="secondary" disabled={busy} onClick={() => onDecide(proposal, 'rejected')}>Recusar</CaduButton>
    </footer>
  </div>;
}

/**
 * The Cadu panel: today it reviews the briefing and lists pending proposals.
 * Section-by-section proposals arrive with the co-building engine (feature flag).
 */
export function CaduPanel({boot, request, plan, setPlan, notify, active}) {
  const [state, setState] = useState({proposals: [], events: [], cobuild: false});
  const [busy, setBusy] = useState('');
  const planId = plan.id;
  const revision = plan.revision;

  useEffect(() => {
    let current = true;
    request(`/plans/${planId}/workbench`).then(data => {
      if (current) setState({proposals: (data.proposals || []).filter(item => item.status === 'pending'), events: data.events || [], cobuild: Boolean(data.cobuild_enabled)});
    }).catch(() => {});
    return () => { current = false; };
  }, [request, planId, revision]);

  const run = async (key, action) => {
    setBusy(key);
    try { await action(); } catch (error) { notify({tone: 'error', message: error.message}); } finally { setBusy(''); }
  };
  const decide = (proposal, decision) => run(proposal.id, async () => {
    const data = await request(`/plans/${planId}/proposals/${proposal.id}/decision`, {method: 'POST',
      body: JSON.stringify({decision, expected_revision: plan.revision})});
    setPlan(data.plan);
    notify({message: decision === 'rejected' ? 'Proposta recusada.' : 'Proposta aplicada ao plano.'});
  });
  const reviewBriefing = () => run('review', async () => {
    // Three review passes spend credits: say so before starting.
    const estimate = await request(`/plans/${planId}/briefing-review/estimate`).catch(() => ({}));
    const tokens = Number(estimate.estimated_tokens || 0);
    if (!window.confirm(`O Cadu revisa o briefing em ${estimate.passes || 3} passagens${tokens ? ` (cerca de ${tokens.toLocaleString('pt-BR')} tokens)` : ''}, usando créditos. Continuar?`)) return;
    const data = await request(`/plans/${planId}/briefing-review`, {method: 'POST', body: JSON.stringify({})});
    if (data.plan) setPlan(data.plan);
    notify({message: 'Briefing revisado pelo Cadu. Confira os campos atualizados.'});
  });
  const propose = () => run('propose', async () => {
    await request(`/plans/${planId}/sections/${active}/propose`, {method: 'POST', body: JSON.stringify({})});
  });

  const visible = state.proposals.filter(item => !active || item.section === active);
  const labels = Object.fromEntries((plan.workbench_overview?.sections || []).map(section => [section.key, section.label]));
  return <PlannerPanel className="planner-cadu" title="Montar com o Cadu"
    description="O Cadu propõe uma seção de cada vez e explica o porquê. Você aceita, ajusta ou recusa.">
    {busy === 'review' && <IllustratedWait slot="plan-building" title="O Cadu está revisando o briefing"
      description="Três passagens: ler o contexto, reorganizar e aplicar a versão revisada."/>}
    {visible.map(proposal => <ProposalCard key={proposal.id} proposal={proposal} label={labels[proposal.section]} busy={busy === proposal.id} onDecide={decide}/>)}
    {!visible.length && <p className="planner-muted">{state.cobuild
      ? 'Nenhuma proposta pendente nesta seção.'
      : 'Em breve o Cadu vai propor praças, audiências, canais com papel e cenários de verba junto com você.'}</p>}
    <div className="planner-cadu__actions">
      {active === 'briefing' && <CaduButton size="sm" variant="secondary" loading={busy === 'review'} onClick={reviewBriefing}>
        <Icon name="compose" size={14}/>Revisar briefing com o Cadu</CaduButton>}
      {state.cobuild && active && <CaduButton size="sm" loading={busy === 'propose'} onClick={propose}>Pedir proposta</CaduButton>}
    </div>
    {plan.source && plan.source !== 'manual' && <CaduBadge tone="brand">{plan.source === 'radar' ? 'Nasceu no Radar' : 'Nasceu no SmartPlanner'}</CaduBadge>}
  </PlannerPanel>;
}
