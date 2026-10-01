import React, {useState} from 'react';
import {CaduButton} from '../cadu-design-system/components/CaduButton.jsx';
import {CaduBadge} from '../cadu-design-system/components/CaduBadge.jsx';
import {CaduDialog} from '../cadu-design-system/components/CaduDialog.jsx';
import {CaduEmptyState} from '../cadu-design-system/components/CaduEmptyState.jsx';
import {CaduPageHeader} from '../cadu-design-system/components/CaduPageHeader.jsx';
import {CaduSelectField, CaduTextAreaField} from '../cadu-design-system/components/CaduField.jsx';
import {CaduInput} from '../cadu-design-system/components/CaduInput.jsx';
import {Icon} from '../cadu-design-system/components/Icon.jsx';
import {PlannerPanel} from './PlannerUi.jsx';
import {MODULE_LABELS, OBJECTIVES, moduleUrl} from './api.js';
import {planStatusLabel, planStatusTone} from './PlansPages.jsx';

const BRIEFING_FIELDS = [['advertiser_name', 'Anunciante'], ['campaign_name', 'Campanha'], ['budget', 'Investimento'], ['period', 'Período'], ['geography', 'Praça'], ['kpis', 'KPIs']];
const QUOTE_SCOPES = [['full_operation', 'Operação completa'], ['media_inventory', 'Inventário de mídia'], ['specific_channels', 'Canais específicos']];
const QUOTE_STATUS = {requested: 'Solicitada', in_review: 'Em análise', needs_information: 'Precisa de informações', proposal_available: 'Proposta disponível', approved: 'Aprovada', closed: 'Encerrada'};
const ADD_MODULES = ['canais', 'audiencias', 'formatos', 'interativos', 'portais', 'places'];

function QuoteDialog({onClose, onSubmit, busy}) {
  return <CaduDialog className="planner-dialog" closeOnBackdrop onClose={onClose}>{({titleId}) => <form onSubmit={onSubmit}>
    <header><h2 id={titleId}>Solicitar proposta</h2><button type="button" onClick={onClose} aria-label="Fechar">×</button></header>
    <p>O plano é congelado como versão e enviado ao time comercial. Os valores são definidos na proposta.</p>
    <CaduSelectField label="Escopo" name="scope" required options={[{value: '', label: 'Escolha o escopo'}, ...QUOTE_SCOPES.map(([value, label]) => ({value, label}))]}/>
    <CaduTextAreaField label="Mensagem para o time comercial" name="message" rows={4} maxLength={2000} placeholder="Prazos, restrições ou dúvidas sobre o plano."/>
    <footer><CaduButton variant="secondary" onClick={onClose}>Cancelar</CaduButton><CaduButton type="submit" loading={busy}>Enviar pedido</CaduButton></footer>
  </form>}</CaduDialog>;
}

export function PlanDetail({boot, request, plan, setPlan, toggle, notify}) {
  const [allocationDraft, setAllocationDraft] = useState({});
  const [quoteOpen, setQuoteOpen] = useState(false);
  const [busy, setBusy] = useState('');
  if (!plan) return <CaduEmptyState title="Plano indisponível" description="Ele pode ter sido removido ou você não tem acesso."/>;

  const briefing = plan.briefing || {};
  const items = plan.items || [];
  const channels = items.filter(item => item.kind === 'canais');
  const readiness = plan.readiness || {checks: []};
  const lastQuote = (plan.quote_requests || [])[0];
  const run = async (key, action) => {
    setBusy(key);
    try { await action(); } catch (error) { notify({tone: 'error', message: error.message}); } finally { setBusy(''); }
  };

  const share = () => run('share', async () => {
    const data = await request(`/plans/${plan.id}/share`, {method: 'POST', body: JSON.stringify({enabled: true})});
    const token = data.plan?.share_token;
    if (!token) return notify({message: 'Link público do plano criado.'});
    await navigator.clipboard?.writeText(new URL(`/planos/public/${token}`, boot.urls.home).href);
    notify({message: 'Link público copiado.'});
  });
  const toggleStatus = () => run('status', async () => {
    const data = await request(`/plans/${plan.id}/status`, {method: 'PUT', body: JSON.stringify({status: plan.status === 'ready' ? 'draft' : 'ready'})});
    setPlan(data.plan);
  });
  const saveBriefing = event => {
    event.preventDefault();
    const fields = Object.fromEntries(new FormData(event.currentTarget));
    run('briefing', async () => {
      const data = await request(`/plans/${plan.id}`, {method: 'PUT', body: JSON.stringify({briefing: fields, advertiser_name: fields.advertiser_name, campaign_name: fields.campaign_name})});
      if (data.plan) setPlan(data.plan);
      notify({message: 'Direção salva.'});
    });
  };
  const saveAllocations = () => run('allocations', async () => {
    const allocations = channels.map(item => {
      const key = String(item.resource_id);
      return {resource_id: key, ...(plan.allocation_by_channel?.[key] || {}), ...(allocationDraft[key] || {})};
    });
    const data = await request(`/plans/${plan.id}/allocations`, {method: 'PUT', body: JSON.stringify({allocations})});
    setPlan(data.plan);
    setAllocationDraft({});
    notify({message: 'Distribuição salva.'});
  });
  const submitQuote = event => {
    event.preventDefault();
    const fields = Object.fromEntries(new FormData(event.currentTarget));
    run('quote', async () => {
      const data = await request(`/plans/${plan.id}/quote-requests`, {method: 'POST', body: JSON.stringify(fields)});
      setPlan(data.plan);
      setQuoteOpen(false);
      notify({message: 'Pedido enviado ao time comercial.'});
    });
  };
  const draftValue = (key, field) => allocationDraft[key]?.[field] ?? plan.allocation_by_channel?.[key]?.[field] ?? '';
  const setDraft = (key, field, value) => setAllocationDraft(current => ({...current, [key]: {...current[key], [field]: value}}));

  return <>
    <CaduPageHeader
      back={{href: boot.urls.plans, label: 'Planos de mídia'}}
      title={plan.title}
      description={[plan.advertiser_name || 'Campanha em definição', plan.campaign_name].filter(Boolean).join(' · ')}
      meta={<><CaduBadge tone={planStatusTone(plan)}>{planStatusLabel(plan)}</CaduBadge>{lastQuote && <CaduBadge tone="brand">Proposta: {QUOTE_STATUS[lastQuote.status] || lastQuote.status}</CaduBadge>}</>}
      actions={<>
        <CaduButton variant="secondary" loading={busy === 'share'} onClick={share}>Publicar plano</CaduButton>
        {readiness.ready && <CaduButton variant="secondary" onClick={() => setQuoteOpen(true)}>Solicitar proposta</CaduButton>}
        <CaduButton loading={busy === 'status'} onClick={toggleStatus}>{plan.status === 'ready' ? 'Reabrir' : 'Marcar pronto'}</CaduButton>
      </>}
    />
    <div className="planner-detail">
      <PlannerPanel title="Direção da campanha" description="O que orienta as escolhas de mídia.">
        <form className="planner-fields" onSubmit={saveBriefing}>
          <CaduSelectField label="Objetivo" name="objective" defaultValue={briefing.objective ?? plan.objective ?? ''} options={OBJECTIVES.map(([value, label]) => ({value, label}))}/>
          {BRIEFING_FIELDS.map(([name, label]) => <CaduInput key={name} label={label} name={name} defaultValue={plan[name] || briefing[name] || ''}/>)}
          <CaduTextAreaField className="is-wide" label="Notas" name="notes" rows={3} defaultValue={briefing.notes || ''}/>
          <div className="planner-fields__actions"><CaduButton type="submit" variant="secondary" loading={busy === 'briefing'}>Salvar direção</CaduButton></div>
        </form>
      </PlannerPanel>
      <div className="planner-detail__side">
        <PlannerPanel title={readiness.ready ? 'Pronto para revisão' : 'Checklist do plano'}>
          <ul className="planner-checklist">{(readiness.checks || []).map(check => <li key={check.label} className={check.complete ? 'is-complete' : ''}>
            <span aria-hidden="true">{check.complete ? <Icon name="check" size={14}/> : null}</span>{check.label}
          </li>)}</ul>
        </PlannerPanel>
        <PlannerPanel title="Composição" description={`${items.length} ${items.length === 1 ? 'referência' : 'referências'} no plano`}>
          {items.length ? <ul className="planner-items">{items.map(item => <li key={`${item.kind}:${item.resource_id}`}>
            <span><strong>{item.snapshot?.name || item.resource_id}</strong><small>{MODULE_LABELS[item.kind] || item.kind}</small></span>
            <CaduButton variant="link" size="sm" onClick={() => toggle(item.kind, item.resource_id)}>Remover</CaduButton>
          </li>)}</ul> : <p className="planner-muted">Ainda não há referências neste plano.</p>}
          <div className="planner-add-links">{ADD_MODULES.map(module => <a key={module} href={moduleUrl(boot.urls, module)}><Icon name="plus" size={14}/>{MODULE_LABELS[module]}</a>)}</div>
        </PlannerPanel>
        {channels.length > 0 && <PlannerPanel title="Distribuição do investimento" description="Valor e participação de cada canal escolhido.">
          <div className="planner-allocation">{channels.map(item => {
            const key = String(item.resource_id);
            const name = item.snapshot?.name || key;
            return <div className="planner-allocation__row" key={key}>
              <strong>{name}</strong>
              <CaduInput size="sm" aria-label={`Investimento em ${name}`} inputMode="decimal" placeholder="Investimento" value={draftValue(key, 'investment')} onChange={event => setDraft(key, 'investment', event.target.value)}/>
              <CaduInput size="sm" aria-label={`Participação de ${name}`} inputMode="decimal" placeholder="% do plano" value={draftValue(key, 'weight')} onChange={event => setDraft(key, 'weight', event.target.value)}/>
            </div>;
          })}</div>
          <CaduButton variant="secondary" loading={busy === 'allocations'} onClick={saveAllocations}>Salvar distribuição</CaduButton>
        </PlannerPanel>}
      </div>
    </div>
    {quoteOpen && <QuoteDialog busy={busy === 'quote'} onClose={() => setQuoteOpen(false)} onSubmit={submitQuote}/>}
  </>;
}
