import React, {useState} from 'react';
import {CaduButton} from '../cadu-design-system/components/CaduButton.jsx';
import {CaduBadge} from '../cadu-design-system/components/CaduBadge.jsx';
import {CaduDialog} from '../cadu-design-system/components/CaduDialog.jsx';
import {CaduEmptyState} from '../cadu-design-system/components/CaduEmptyState.jsx';
import {CaduSelectField, CaduTextAreaField} from '../cadu-design-system/components/CaduField.jsx';
import {CaduInput} from '../cadu-design-system/components/CaduInput.jsx';
import {Icon} from '../cadu-design-system/components/Icon.jsx';
import {AddItemsDialog} from './AddItemsDialog.jsx';
import {MediaBalance} from './MediaBalance.jsx';
import {FinalReviewDialog, TimeSaved} from './PlanReview.jsx';
import {LogoTile, PlannerPanel} from './PlannerUi.jsx';
import {CaduPanel, SectionRail} from './PlanWorkbench.jsx';
import {MODULE_LABELS, OBJECTIVES, moduleUrl, objectiveLabel} from './api.js';
import {PlannerHeader} from './PlannerHeader.jsx';
import {planStatusLabel, planStatusTone} from './PlansPages.jsx';

const BRIEFING_FIELDS = [['advertiser_name', 'Anunciante'], ['campaign_name', 'Campanha'], ['budget', 'Investimento'], ['period', 'Período'], ['geography', 'Praça'], ['kpis', 'KPIs']];
const QUOTE_SCOPES = [['full_operation', 'Operação completa'], ['media_inventory', 'Inventário de mídia'], ['specific_channels', 'Canais específicos']];
const QUOTE_STATUS = {requested: 'Solicitada', in_review: 'Em análise', needs_information: 'Precisa de informações', proposal_available: 'Proposta disponível', approved: 'Aprovada', closed: 'Encerrada'};
const ADD_MODULES = ['canais', 'audiencias', 'formatos', 'interativos', 'portais', 'places'];
// Which page block holds each workbench section.
const SECTION_BLOCK = {briefing: 'direcao', objetivo: 'direcao', pracas: 'direcao', audiencias: 'composicao',
  canais: 'composicao', formatos: 'composicao', verba: 'distribuicao', criativos: 'criativos'};
const KIND_ORDER = ['audiencias', 'canais', 'formatos', 'interativos', 'portais', 'places'];

function addUrl(urls, module, planId) {
  const url = new URL(moduleUrl(urls, module), window.location.origin);
  url.searchParams.set('plan', planId);
  return url.pathname + url.search;
}

function QuoteDialog({onClose, onSubmit, busy}) {
  return <CaduDialog className="planner-dialog" closeOnBackdrop onClose={onClose}>{({titleId}) => <form onSubmit={onSubmit}>
    <header><h2 id={titleId}>Solicitar proposta</h2><CaduButton variant="tertiary" size="sm" aria-label="Fechar" onClick={onClose}><Icon name="close" size={18}/></CaduButton></header>
    <p>O plano é congelado como versão e enviado ao time comercial. Os valores são definidos na proposta.</p>
    <CaduSelectField label="Escopo" name="scope" required options={[{value: '', label: 'Escolha o escopo'}, ...QUOTE_SCOPES.map(([value, label]) => ({value, label}))]}/>
    <CaduTextAreaField label="Mensagem para o time comercial" name="message" rows={4} maxLength={2000} placeholder="Prazos, restrições ou dúvidas sobre o plano."/>
    <footer><CaduButton variant="secondary" onClick={onClose}>Cancelar</CaduButton><CaduButton type="submit" loading={busy}>Enviar pedido</CaduButton></footer>
  </form>}</CaduDialog>;
}

export function PlanDetail({boot, request, plan, setPlan, selection, notify}) {
  const toggle = selection.toggle;
  const [quoteOpen, setQuoteOpen] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [reviewOpen, setReviewOpen] = useState(false);
  const [busy, setBusy] = useState('');
  const overview = plan?.workbench_overview;
  const [active, setActive] = useState(overview?.next || 'briefing');
  if (!plan) return <CaduEmptyState title="Plano indisponível" description="Ele pode ter sido removido ou você não tem acesso."/>;

  const briefing = plan.briefing || {};
  const items = plan.items || [];
  const readiness = plan.readiness || {checks: []};
  const lastQuote = (plan.quote_requests || [])[0];
  const pending = (readiness.checks || []).filter(check => !check.complete).length;
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
  const reopen = () => run('status', async () => {
    const data = await request(`/plans/${plan.id}/status`, {method: 'PUT', body: JSON.stringify({status: 'draft'})});
    setPlan(data.plan);
  });
  const finalize = async () => {
    setBusy('status');
    try {
      const data = await request(`/plans/${plan.id}/status`, {method: 'PUT', body: JSON.stringify({status: 'ready'})});
      setPlan(data.plan);
      return true;
    } catch (error) {
      notify({tone: 'error', message: error.message});
      return false;
    } finally {
      setBusy('');
    }
  };
  const saveBriefing = event => {
    event.preventDefault();
    const fields = Object.fromEntries(new FormData(event.currentTarget));
    run('briefing', async () => {
      const data = await request(`/plans/${plan.id}`, {method: 'PUT', body: JSON.stringify({briefing: fields, advertiser_name: fields.advertiser_name, campaign_name: fields.campaign_name})});
      if (data.plan) setPlan(data.plan);
      notify({message: 'Direção salva.'});
    });
  };
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
  const selectSection = key => {
    setActive(key);
    document.getElementById(`bloco-${SECTION_BLOCK[key]}`)?.scrollIntoView({behavior: 'smooth', block: 'start'});
  };
  const goTo = key => { setReviewOpen(false); selectSection(key); };
  const grouped = KIND_ORDER.map(kind => [kind, items.filter(item => item.kind === kind)]).filter(([, list]) => list.length);

  return <>
    <PlannerHeader crumbs={[['Planos', boot.urls.plans]]} title={plan.title}
      description={[plan.advertiser_name, plan.objective && objectiveLabel(plan.objective), briefing.period, briefing.geography].filter(Boolean).join(' · ') || 'Defina a direção da campanha para começar.'}
      meta={<><CaduBadge tone={planStatusTone(plan)}>{planStatusLabel(plan)}</CaduBadge>{lastQuote && <CaduBadge tone="brand">Proposta: {QUOTE_STATUS[lastQuote.status] || lastQuote.status}</CaduBadge>}
        {plan.status === 'ready' && <TimeSaved estimate={plan.time_saved} className="is-inline" compact/>}</>}
      actions={<>
        <CaduButton variant="secondary" loading={busy === 'share'} onClick={share}><Icon name="link" size={16}/>Copiar link</CaduButton>
        <CaduButton variant="secondary" disabled={!readiness.ready} title={readiness.ready ? undefined : 'Complete o checklist para pedir proposta'}
          onClick={() => setQuoteOpen(true)}>Solicitar proposta</CaduButton>
        {plan.status === 'ready'
          ? <CaduButton variant="secondary" loading={busy === 'status'} onClick={reopen}>Reabrir plano</CaduButton>
          : <CaduButton onClick={() => setReviewOpen(true)} title={pending ? `Faltam ${pending} ${pending === 1 ? 'item' : 'itens'} do checklist` : undefined}>Revisar e finalizar</CaduButton>}
      </>}/>
    <div className="planner-workbench">
      <SectionRail overview={overview} active={active} onSelect={selectSection}/>
      <div className="planner-workbench__main">
        <PlannerPanel className={`planner-block${SECTION_BLOCK[active] === 'direcao' ? ' is-active' : ''}`} title="Direção da campanha" description="Briefing, objetivo, KPIs e praças que orientam as escolhas de mídia.">
          <span id="bloco-direcao" className="planner-anchor"/>
          <form key={String(plan.updated_at)} className="planner-fields" onSubmit={saveBriefing}>
            <CaduSelectField label="Objetivo" name="objective" defaultValue={briefing.objective ?? plan.objective ?? ''} options={OBJECTIVES.map(([value, label]) => ({value, label}))}/>
            {BRIEFING_FIELDS.map(([name, label]) => <CaduInput key={name} label={label} name={name} defaultValue={plan[name] || briefing[name] || ''}/>)}
            <CaduTextAreaField className="is-wide" label="Notas" name="notes" rows={3} defaultValue={briefing.notes || ''}/>
            <div className="planner-fields__actions"><CaduButton type="submit" variant="secondary" loading={busy === 'briefing'}>Salvar direção</CaduButton></div>
          </form>
        </PlannerPanel>
        <PlannerPanel className={`planner-block${SECTION_BLOCK[active] === 'composicao' ? ' is-active' : ''}`} title="Composição" description={`${items.length} ${items.length === 1 ? 'referência' : 'referências'} no plano`}>
          <span id="bloco-composicao" className="planner-anchor"/>
          {grouped.length ? grouped.map(([kind, list]) => <div key={kind} className="planner-composition">
            <h3>{MODULE_LABELS[kind] || kind}<small>{list.length}</small></h3>
            <ul className="planner-items">{list.map(item => <li key={`${item.kind}:${item.resource_id}`}>
              <LogoTile src={item.logo} name={item.snapshot?.name} size="sm"/>
              <span><a href={`${moduleUrl(boot.urls, item.kind)}/${encodeURIComponent(item.resource_id)}`}><strong>{item.snapshot?.name || item.resource_id}</strong></a>
                <small>{[item.snapshot?.category, item.snapshot?.audience].filter(value => value && String(value).length <= 40).join(' · ')}</small></span>
              <CaduButton variant="tertiary" size="sm" onClick={() => toggle(item.kind, item.resource_id)}>Remover</CaduButton>
            </li>)}</ul>
          </div>) : <p className="planner-muted">Ainda não há referências neste plano. Explore as vitrines; o que você adicionar entra direto aqui.</p>}
          <div className="planner-add">
            <CaduButton variant="secondary" onClick={() => setAddOpen(true)}><Icon name="plus" size={16}/>Adicionar itens</CaduButton>
            <span className="planner-muted">ou explore as vitrines:</span>
            <div className="planner-add-links">{ADD_MODULES.map(module => <a key={module} href={addUrl(boot.urls, module, plan.id)}>{MODULE_LABELS[module]}</a>)}</div>
          </div>
        </PlannerPanel>
        <PlannerPanel className={`planner-block${SECTION_BLOCK[active] === 'distribuicao' ? ' is-active' : ''}`} title="Balanceamento de mídia"
          description="Escolha como dividir a verba, ajuste as fatias e veja a diferença antes de aplicar.">
          <span id="bloco-distribuicao" className="planner-anchor"/>
          <MediaBalance request={request} plan={plan} setPlan={setPlan} notify={notify} onEditDirection={() => selectSection('briefing')}/>
        </PlannerPanel>
        <PlannerPanel className={`planner-block${SECTION_BLOCK[active] === 'criativos' ? ' is-active' : ''}`} title="Sistema criativo" description="Big idea, mensagens por etapa e a matriz de peças por canal.">
          <span id="bloco-criativos" className="planner-anchor"/>
          <p className="planner-muted">O Cadu vai montar a matriz criativa com você a partir dos canais e formatos escolhidos, pronta para seguir ao Studio.</p>
        </PlannerPanel>
      </div>
      <div className="planner-workbench__side">
        <CaduPanel boot={boot} request={request} plan={plan} setPlan={setPlan} notify={notify} active={active}/>
        <PlannerPanel title={readiness.ready ? 'Pronto para revisão' : 'Checklist do plano'}>
          <ul className="planner-checklist">{(readiness.checks || []).map(check => <li key={check.label} className={check.complete ? 'is-complete' : ''}>
            <span aria-hidden="true">{check.complete ? <Icon name="check" size={14}/> : null}</span>{check.label}
          </li>)}</ul>
        </PlannerPanel>
      </div>
    </div>
    {quoteOpen && <QuoteDialog busy={busy === 'quote'} onClose={() => setQuoteOpen(false)} onSubmit={submitQuote}/>}
    {addOpen && <AddItemsDialog request={request} selection={selection} onClose={() => setAddOpen(false)}/>}
    {reviewOpen && <FinalReviewDialog plan={plan} busy={busy === 'status'} onClose={() => setReviewOpen(false)} onFinalize={finalize}
      onGoTo={goTo} onAddItems={() => { setReviewOpen(false); setAddOpen(true); }}/>}
  </>;
}
