import React, {useState} from 'react';
import {CaduButton} from '../cadu-design-system/components/CaduButton.jsx';
import {CaduBadge} from '../cadu-design-system/components/CaduBadge.jsx';
import {CaduEmptyState} from '../cadu-design-system/components/CaduEmptyState.jsx';
import {CaduPageHeader} from '../cadu-design-system/components/CaduPageHeader.jsx';
import {CaduSelectField, CaduTextAreaField} from '../cadu-design-system/components/CaduField.jsx';
import {CaduInput} from '../cadu-design-system/components/CaduInput.jsx';
import {Icon} from '../cadu-design-system/components/Icon.jsx';
import {PlannerPanel} from './PlannerUi.jsx';
import {OBJECTIVES, moduleUrl, newPlanUrl, objectiveLabel} from './api.js';

export const planStatusLabel = plan => plan.status_label || {draft: 'Rascunho', ready: 'Pronto para revisão'}[plan.status] || 'Em andamento';
export const planStatusTone = plan => plan.status === 'ready' ? 'success' : 'neutral';

const DISCOVER = [
  ['canais', 'share', 'Onde a campanha aparece: social, busca, vídeo e áudio.'],
  ['audiencias', 'users', 'Públicos com tamanho estimado e contexto de uso.'],
  ['formatos', 'table', 'Especificações e finalidade de cada peça.'],
  ['interativos', 'plugin', 'Formatos com interação para engajar.'],
  ['portais', 'library', 'Veículos editoriais com audiência pública verificável.'],
  ['places', 'browser', 'Pontos físicos e circulação para mídia em lugares.'],
];
const DISCOVER_LABELS = {canais: 'Canais', audiencias: 'Audiências', formatos: 'Formatos', interativos: 'Interativos', portais: 'Portais', places: 'Places'};

function PlanRow({plan, urls}) {
  return <a className="planner-plan-row" href={`${urls.plans}/${encodeURIComponent(plan.id)}`}>
    <span className="planner-plan-row__icon" aria-hidden="true"><Icon name="plan" size={18}/></span>
    <span className="planner-plan-row__copy"><strong>{plan.title}</strong><small>{objectiveLabel(plan.objective)} · {Number(plan.item_count || 0)} {Number(plan.item_count) === 1 ? 'escolha' : 'escolhas'}</small></span>
    <CaduBadge tone={planStatusTone(plan)}>{planStatusLabel(plan)}</CaduBadge>
  </a>;
}

export function PlanList({plans, urls, emptyAction = true}) {
  if (!plans.length) {
    return <PlannerPanel className="planner-panel--flush"><CaduEmptyState title="Nenhum plano ainda" description="Comece pelo objetivo e pelo investimento. As escolhas de mídia vêm depois." action={emptyAction ? <CaduButton href={newPlanUrl(urls)}>Criar o primeiro plano</CaduButton> : null}/></PlannerPanel>;
  }
  return <div className="planner-list">{plans.map(plan => <PlanRow key={plan.id} plan={plan} urls={urls}/>)}</div>;
}

export function PlannerHome({boot, plans}) {
  const urls = boot.urls;
  const latest = plans[0];
  return <>
    <CaduPageHeader title="Planejamento de mídia" description="Reúna objetivo, investimento, público e mix em um plano claro para revisar." actions={<CaduButton href={newPlanUrl(urls)}>Novo plano</CaduButton>}/>
    {latest && <section className="planner-resume" aria-label="Plano em andamento">
      <div className="planner-resume__copy">
        <span className="planner-section-label">Continue de onde parou</span>
        <h2>{latest.title}</h2>
        <p>{latest.next_step || 'Revise a composição e a distribuição do investimento.'}</p>
        {Number(latest.progress_total) > 0 && <div className="planner-progress" aria-label={`Checklist ${latest.progress_percent}% concluído`}>
          <i><b style={{width: `${Math.max(0, Math.min(100, Number(latest.progress_percent)))}%`}}/></i>
          <small>{latest.progress_complete ?? 0} de {latest.progress_total ?? 0} etapas{latest.updated_label ? ` · ${latest.updated_label}` : ''}</small>
        </div>}
      </div>
      <CaduButton href={`${urls.plans}/${encodeURIComponent(latest.id)}`}>Continuar plano</CaduButton>
    </section>}
    <section className="planner-section">
      <header className="planner-section__header"><h2>Planos recentes</h2>{plans.length > 0 && <a href={urls.plans}>Ver todos</a>}</header>
      <PlanList plans={plans.slice(0, 5)} urls={urls}/>
    </section>
    <section className="planner-section">
      <header className="planner-section__header"><h2>Descobrir referências</h2></header>
      <div className="planner-discover">{DISCOVER.map(([module, icon, text]) => <a key={module} href={moduleUrl(urls, module)}>
        <span className="planner-discover__icon" aria-hidden="true"><Icon name={icon} size={18}/></span>
        <strong>{DISCOVER_LABELS[module]}</strong><small>{text}</small>
      </a>)}</div>
    </section>
  </>;
}

export function PlansPage({boot, plans}) {
  return <>
    <CaduPageHeader title="Planos de mídia" description="Retome uma recomendação ou comece uma campanha." actions={<CaduButton href={newPlanUrl(boot.urls)}>Novo plano</CaduButton>}/>
    <PlanList plans={plans} urls={boot.urls}/>
  </>;
}

export function PlanCreatePage({boot, request, notify}) {
  const [busy, setBusy] = useState(false);
  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    try {
      const briefing = Object.fromEntries(new FormData(event.currentTarget));
      const data = await request('/plans', {method: 'POST', body: JSON.stringify({...briefing, briefing})});
      window.location.assign(`${boot.urls.plans}/${encodeURIComponent(data.plan.id)}`);
    } catch (error) {
      notify({tone: 'error', message: error.message});
      setBusy(false);
    }
  }
  return <>
    <CaduPageHeader back={{href: boot.urls.plans, label: 'Planos de mídia'}} title="Novo plano" description="Defina o contexto inicial. O mix de mídia vem na próxima etapa."/>
    <div className="planner-split">
      <form className="planner-form" onSubmit={submit}>
        <PlannerPanel title="Campanha" description="Organiza o plano e liga a recomendação ao trabalho certo.">
          <div className="planner-fields">
            <CaduInput className="is-wide" label="Nome do plano" name="title" required minLength="2" maxLength="180" placeholder="Ex.: Lançamento de verão" autoFocus/>
            <CaduInput label="Anunciante" name="advertiser_name" placeholder="Marca ou anunciante"/>
            <CaduInput label="Campanha" name="campaign_name" placeholder="Se já tiver nome"/>
          </div>
        </PlannerPanel>
        <PlannerPanel title="Objetivo e investimento">
          <div className="planner-fields">
            <CaduSelectField label="Objetivo" name="objective" options={OBJECTIVES.map(([value, label]) => ({value, label}))}/>
            <CaduInput label="Investimento" name="budget" inputMode="decimal" placeholder="Ex.: R$ 50.000"/>
            <CaduInput label="Período" name="period" placeholder="Ex.: maio a julho de 2026"/>
            <CaduInput label="Praça" name="geography" placeholder="Ex.: Brasil ou cidades atendidas"/>
            <CaduInput className="is-wide" label="KPIs" name="kpis" placeholder="Ex.: alcance, leads ou vendas"/>
          </div>
        </PlannerPanel>
        <PlannerPanel title="Notas para o planejamento">
          <CaduTextAreaField label="Informações importantes" name="notes" rows={4} placeholder="Restrições, datas ou observações que ajudem a estruturar o plano."/>
        </PlannerPanel>
        <footer className="planner-form__footer">
          <CaduButton variant="secondary" href={boot.urls.plans}>Cancelar</CaduButton>
          <CaduButton type="submit" loading={busy}>Criar plano</CaduButton>
        </footer>
      </form>
      <aside className="planner-aside">
        <h2>Depois de criar</h2>
        <p>Você escolhe canais, audiências, formatos e portais e distribui o investimento entre os canais.</p>
        <ul><li>O rascunho fica salvo para continuar depois.</li><li>Campos em branco podem ser preenchidos mais tarde.</li></ul>
      </aside>
    </div>
  </>;
}
