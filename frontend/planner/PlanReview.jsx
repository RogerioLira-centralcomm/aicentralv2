import React, {useState} from 'react';
import {CaduButton} from '../cadu-design-system/components/CaduButton.jsx';
import {CaduDialog} from '../cadu-design-system/components/CaduDialog.jsx';
import {Icon} from '../cadu-design-system/components/Icon.jsx';
import {MODULE_LABELS, objectiveLabel} from './api.js';
import {Illustration} from './Illustration.jsx';
import {LogoTile} from './PlannerUi.jsx';

const KIND_ORDER = ['canais', 'audiencias', 'formatos', 'interativos', 'portais', 'places'];

/** Tempo poupado, discreto: uma linha com a conta no título para quem quiser ver. */
export function TimeSaved({estimate, className = '', compact = false}) {
  if (!estimate?.minutes) return null;
  const detail = [...estimate.lines.map(line => `${line.label}${line.count > 1 ? ` (${line.count}×)` : ''}: ${line.minutes} min`), estimate.note].join('\n');
  return <span className={`time-saved ${className}`} title={detail}>
    <Illustration slot="time-saved" className="time-saved__mark"/>
    {compact ? `${estimate.label} poupadas` : `Cerca de ${estimate.label} poupadas com o Cadu`}
  </span>;
}

function Row({label, value, done, onFix}) {
  return <li className={done ? 'is-done' : ''}>
    <span className="review-row__mark" aria-hidden="true">{done ? <Icon name="check" size={12}/> : null}</span>
    <span className="review-row__label">{label}</span>
    <span className="review-row__value">{value || (onFix ? '' : '—')}
      {!done && onFix && <button type="button" className="bal-link" onClick={onFix}>{value ? 'Ajustar' : 'Completar'}</button>}</span>
  </li>;
}

/**
 * Revisão antes do plano final: o usuário vê direção, composição e
 * balanceamento lado a lado, corrige o que falta e só então finaliza.
 */
export function FinalReviewDialog({plan, busy, onClose, onFinalize, onGoTo, onAddItems}) {
  const [finished, setFinished] = useState(plan.status === 'ready');
  const briefing = plan.briefing || {};
  const items = plan.items || [];
  const balance = plan.workbench?.balance;
  const channels = items.filter(item => item.kind === 'canais');
  const pending = (plan.readiness?.checks || []).filter(check => !check.complete);
  const finalize = async () => { if (await onFinalize()) setFinished(true); };

  return <CaduDialog className="planner-dialog planner-dialog--wide review" closeOnBackdrop onClose={onClose}>{({titleId}) => <>
    <header><h2 id={titleId}>{finished ? 'Plano finalizado' : 'Revisar antes de finalizar'}</h2>
      <CaduButton variant="tertiary" size="sm" aria-label="Fechar" onClick={onClose}><Icon name="close" size={18}/></CaduButton></header>
    <div className="review__intro"><Illustration slot="review"/>
      <p>{finished ? 'O plano está pronto para compartilhar ou pedir proposta. Você pode reabrir quando quiser.'
        : 'Confira cada parte. O que estiver incompleto leva você direto ao ponto para ajustar.'}</p></div>

    <section className="review__block" aria-labelledby="review-direcao">
      <h3 id="review-direcao">Direção</h3>
      <ul className="review-rows">
        <Row label="Objetivo" value={plan.objective && objectiveLabel(plan.objective)} done={Boolean(plan.objective)} onFix={() => onGoTo('briefing')}/>
        <Row label="Investimento" value={briefing.budget} done={Boolean(briefing.budget)} onFix={() => onGoTo('verba')}/>
        <Row label="Período" value={briefing.period} done={Boolean(briefing.period)} onFix={() => onGoTo('briefing')}/>
        <Row label="Praças" value={briefing.geography} done={Boolean(briefing.geography)} onFix={() => onGoTo('pracas')}/>
        <Row label="KPIs" value={briefing.kpis} done={Boolean(briefing.kpis)} onFix={() => onGoTo('objetivo')}/>
      </ul>
    </section>

    <section className="review__block" aria-labelledby="review-composicao">
      <h3 id="review-composicao">Composição<button type="button" className="bal-link" onClick={onAddItems}><Icon name="plus" size={14}/>Adicionar itens</button></h3>
      <ul className="review-kinds">{KIND_ORDER.map(kind => [kind, items.filter(item => item.kind === kind)]).filter(([, list]) => list.length).map(([kind, list]) => <li key={kind}>
        <span>{MODULE_LABELS[kind]}<b>{list.length}</b></span>
        <span className="review-kinds__logos">{list.slice(0, 8).map(item => <LogoTile key={item.resource_id} src={item.logo} name={item.snapshot?.name} size="xs"/>)}
          {list.length > 8 && <small>+{list.length - 8}</small>}</span>
      </li>)}</ul>
      {!items.length && <p className="planner-muted">Nenhum item ainda.</p>}
    </section>

    <section className="review__block" aria-labelledby="review-balanco">
      <h3 id="review-balanco">Balanceamento</h3>
      <ul className="review-rows">
        <Row label="Estratégia adotada" value={balance?.strategy} done={Boolean(balance?.method)} onFix={channels.length ? () => onGoTo('verba') : null}/>
        <Row label="Canais com verba" value={channels.length ? `${(plan.allocations || []).length} de ${channels.length}` : ''}
          done={channels.length > 0 && (plan.allocations || []).length >= channels.length} onFix={() => onGoTo('verba')}/>
      </ul>
    </section>

    {!finished && pending.length > 0 && <p className="review__pending"><Icon name="alert" size={14}/>
      Faltam {pending.length} {pending.length === 1 ? 'item' : 'itens'}: {pending.map(item => item.label.toLowerCase()).join('; ')}.</p>}

    <footer>
      {finished ? <TimeSaved estimate={plan.time_saved}/> : <span/>}
      {finished ? <CaduButton onClick={onClose}>Concluir</CaduButton>
        : <CaduButton loading={busy} disabled={pending.length > 0} onClick={finalize}>Finalizar plano</CaduButton>}
    </footer>
  </>}</CaduDialog>;
}
