import React, {useState} from 'react';
import {ReportsActionButton} from '../../ReportsActionButton.jsx';
import {ReportsDrawer} from '../../ReportsDrawer.jsx';
import {ReportsFieldInput} from '../../ReportsFieldInput.jsx';
import {ReportsNativeSelect} from '../../ReportsNativeSelect.jsx';
import {ReportsTextArea} from '../../ReportsTextArea.jsx';
import {json} from '../../reportsCommon.jsx';
import {friendlyDateTime} from '../../friendlyDates.js';
import {apiUrl, useApi} from '../../shell/useApi.js';
import {EmptyState, Section} from '../../shell/primitives.jsx';
import {number} from '../shared.jsx';

export const OBJECTIVES = [['', 'Sem objetivo definido'], ['leads', 'Gerar leads'], ['sales', 'Vendas'], ['traffic', 'Tráfego para o site'], ['awareness', 'Alcance e reconhecimento'], ['app', 'Instalações de app']];
const BIDDING = {MAXIMIZE_CONVERSIONS: 'Maximizar conversões', MAXIMIZE_CONVERSION_VALUE: 'Maximizar valor', TARGET_CPA: 'CPA desejado', TARGET_ROAS: 'ROAS desejado', MANUAL_CPC: 'CPC manual', TARGET_SPEND: 'Maximizar cliques', TARGET_IMPRESSION_SHARE: 'Parcela de impressões'};

/** Month pace against the ceiling: spent so far, projection at the current pace, and the ceiling mark. */
export function PacingBar({campaign, money}) {
  const cap = Number(campaign.goal?.monthly_budget_cap || 0);
  const pacing = campaign.pacing || {};
  if (!cap) return <span className="rs-muted-sm">{pacing.mtd_cost ? `${money(pacing.mtd_cost)} no mês` : '—'}</span>;
  const spent = Math.min(100, pacing.mtd_cost * 100 / cap);
  const projected = Math.min(100, pacing.projected_cost * 100 / cap);
  const tone = pacing.mtd_cost >= cap ? 'error' : pacing.projected_cost > cap * 1.03 ? 'warning' : 'success';
  return <span className="ga-pace" title={`Gasto no mês ${money(pacing.mtd_cost)} · projeção ${money(pacing.projected_cost)} · teto ${money(cap)}`}>
    <i><b className={`is-${tone}`} style={{width: `${spent}%`}}/><em style={{left: `${projected}%`}}/></i>
    <small>{money(pacing.mtd_cost)} de {money(cap)} · projeção {money(pacing.projected_cost)}</small>
  </span>;
}

/** Goals of the month at a glance: only campaigns that have a goal. */
export function GoalsSection({campaigns, money, onEdit}) {
  const withGoal = campaigns.filter(item => item.goal);
  return <Section title="Metas do mês" description="Ritmo de gasto e resultado contra o que foi combinado para cada campanha">
    {!withGoal.length ? <EmptyState title="Nenhuma meta definida" description="Defina teto de orçamento, período e objetivo (CPA, ROAS ou conversões) nas campanhas para receber próximos passos de ritmo e meta."
      action={campaigns[0]?.campaign_id ? <ReportsActionButton color="secondary" size="sm" onClick={() => onEdit(campaigns[0])}>Definir a primeira meta</ReportsActionButton> : null}/>
      : <ul className="ga-goals">{withGoal.map(campaign => {
        const goal = campaign.goal;
        const cpa = campaign.conversions ? campaign.cost / campaign.conversions : null;
        return <li key={`${campaign.account_id}:${campaign.campaign_external_id}`}>
          <div className="ga-goals__name"><strong>{campaign.campaign_name}</strong><small>{OBJECTIVES.find(([key]) => key === (goal.objective || ''))?.[1]}{goal.flight_end ? ` · até ${goal.flight_end.split('-').reverse().join('/')}` : ''}</small></div>
          <PacingBar campaign={campaign} money={money}/>
          <dl className="ga-goals__targets">
            {goal.target_cpa != null && <div><dt>CPA</dt><dd className={cpa && cpa > goal.target_cpa * 1.2 ? 'ga-strong' : ''}>{cpa ? money(cpa) : '—'} <span>meta {money(goal.target_cpa)}</span></dd></div>}
            {goal.target_roas != null && <div><dt>ROAS</dt><dd>{campaign.roas != null ? campaign.roas.toLocaleString('pt-BR') : '—'} <span>meta {Number(goal.target_roas).toLocaleString('pt-BR')}</span></dd></div>}
            {goal.target_conversions_month != null && <div><dt>Conversões no mês</dt><dd className={campaign.pacing.projected_conversions < goal.target_conversions_month * 0.9 ? 'ga-strong' : ''}>{number(campaign.pacing.mtd_conversions)} <span>projeção {number(campaign.pacing.projected_conversions)} de {number(goal.target_conversions_month)}</span></dd></div>}
          </dl>
          <ReportsActionButton color="link-color" size="sm" className="rs-link-button" onClick={() => onEdit(campaign)}>Editar meta</ReportsActionButton>
        </li>;
      })}</ul>}
  </Section>;
}

const FIELDS = ['objective', 'monthly_budget_cap', 'total_budget_cap', 'flight_start', 'flight_end', 'target_cpa', 'target_roas', 'target_conversions_month', 'notes'];

/** Goal of one campaign plus what Google Ads has configured and how it changed. */
export function GoalDrawer({campaign, data, money, onClose, onSaved}) {
  const [form, setForm] = useState(() => Object.fromEntries(FIELDS.map(key => [key, campaign?.goal?.[key] ?? ''])));
  const [state, setState] = useState({saving: false, error: ''});
  const [history] = useApi(campaign ? apiUrl(`/google-ads/campaigns/${campaign.account_id}/${encodeURIComponent(campaign.campaign_external_id)}/history`) : '');
  const set = key => event => setForm(current => ({...current, [key]: event.target.value}));
  const viewer = data.client.role === 'viewer';
  const save = async event => {
    event.preventDefault();
    setState({saving: true, error: ''});
    try {
      await json(`/connect/api/v2/reports/google-ads/goals/${campaign.campaign_id}`, {method: 'PUT', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': data.csrf},
        body: JSON.stringify({...form, client_id: data.client.client_id})});
      onSaved();
    } catch (failure) {setState({saving: false, error: failure.message});}
  };
  if (!campaign) return null;
  const pacing = campaign.pacing || {};
  return <ReportsDrawer className="rs-drawer" open onOpenChange={open => {if (!open) onClose();}} title={campaign.campaign_name} description="Meta da campanha e configuração no Google Ads">
    <div className="rs-stack rs-drawer-body">
      <dl className="ga-facts">
        <div><dt>Estratégia no Google Ads</dt><dd>{BIDDING[campaign.bidding_strategy_type] || campaign.bidding_strategy_type || '—'}</dd></div>
        <div><dt>Orçamento diário</dt><dd>{campaign.budget != null ? money(campaign.budget) : '—'}</dd></div>
        <div><dt>CPA desejado no Google</dt><dd>{campaign.target_cpa ? money(campaign.target_cpa) : '—'}</dd></div>
        <div><dt>ROAS desejado no Google</dt><dd>{campaign.target_roas ? campaign.target_roas.toLocaleString('pt-BR') : '—'}</dd></div>
        <div><dt>Gasto no mês</dt><dd>{money(pacing.mtd_cost)} · média {money(pacing.daily_avg)}/dia</dd></div>
        <div><dt>Projeção do mês</dt><dd>{money(pacing.projected_cost)} · {pacing.days_left} dias restantes</dd></div>
      </dl>
      {!campaign.campaign_id ? <p className="rs-muted">Esta campanha ainda não foi registrada no Reports; ela aparece aqui depois da próxima coleta de métricas.</p> :
        <form className="ga-goal-form" onSubmit={save}>
          <label className="rs-field"><span>Objetivo</span><ReportsNativeSelect value={form.objective} onChange={set('objective')} disabled={viewer}>{OBJECTIVES.map(([key, label]) => <option key={key} value={key}>{label}</option>)}</ReportsNativeSelect></label>
          <div className="rs-field-row">
            <label className="rs-field"><span>Teto mensal (R$)</span><ReportsFieldInput inputMode="decimal" value={form.monthly_budget_cap} onChange={set('monthly_budget_cap')} placeholder="Ex.: 3000" disabled={viewer}/></label>
            <label className="rs-field"><span>Teto total da campanha (R$)</span><ReportsFieldInput inputMode="decimal" value={form.total_budget_cap} onChange={set('total_budget_cap')} placeholder="Opcional" disabled={viewer}/></label>
          </div>
          <div className="rs-field-row">
            <label className="rs-field"><span>Início</span><ReportsFieldInput type="date" value={form.flight_start} onChange={set('flight_start')} disabled={viewer}/></label>
            <label className="rs-field"><span>Fim</span><ReportsFieldInput type="date" value={form.flight_end} onChange={set('flight_end')} disabled={viewer}/></label>
          </div>
          <div className="rs-field-row ga-three">
            <label className="rs-field"><span>CPA meta (R$)</span><ReportsFieldInput inputMode="decimal" value={form.target_cpa} onChange={set('target_cpa')} disabled={viewer}/></label>
            <label className="rs-field"><span>ROAS meta</span><ReportsFieldInput inputMode="decimal" value={form.target_roas} onChange={set('target_roas')} placeholder="Ex.: 4" disabled={viewer}/></label>
            <label className="rs-field"><span>Conversões/mês</span><ReportsFieldInput inputMode="numeric" value={form.target_conversions_month} onChange={set('target_conversions_month')} disabled={viewer}/></label>
          </div>
          <label className="rs-field"><span>Observações</span><ReportsTextArea rows={3} maxLength={1000} value={form.notes} onChange={set('notes')} placeholder="Combinado com o cliente, sazonalidade, restrições…" disabled={viewer}/></label>
          {state.error && <p className="rs-error-inline" role="alert">{state.error}</p>}
          {!viewer && <div className="rs-actions"><ReportsActionButton type="submit" color="primary" disabled={state.saving}>{state.saving ? 'Salvando…' : 'Salvar meta'}</ReportsActionButton><ReportsActionButton color="secondary" onClick={onClose}>Cancelar</ReportsActionButton></div>}
        </form>}
      <Section title="Histórico no Google Ads" description="Mudanças de status, lance, orçamento e metas observadas pelo script">
        {!history.body ? <p className="rs-muted">Carregando…</p> : !history.body.history.length ? <p className="rs-muted">{history.body.ready ? 'Nenhuma mudança registrada ainda; o histórico começa na primeira coleta com o script 2.1.' : 'Aplique a migração de histórico para registrar mudanças.'}</p>
          : <ol className="ga-history">{history.body.history.map((row, index) => <li key={index}><time>{friendlyDateTime(row.observed_at)}</time>
            <span>{[row.status && `status ${row.status.toLowerCase()}`, row.budget != null && `orçamento ${money(row.budget)}/dia`, row.bidding_strategy_type && (BIDDING[row.bidding_strategy_type] || row.bidding_strategy_type), row.target_cpa && `CPA desejado ${money(row.target_cpa)}`, row.target_roas && `ROAS desejado ${row.target_roas}`].filter(Boolean).join(' · ')}</span></li>)}</ol>}
      </Section>
    </div>
  </ReportsDrawer>;
}
