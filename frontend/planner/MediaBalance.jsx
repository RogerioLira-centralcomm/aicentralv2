import React, {useEffect, useMemo, useRef, useState} from 'react';
import {CaduBadge} from '../cadu-design-system/components/CaduBadge.jsx';
import {CaduButton} from '../cadu-design-system/components/CaduButton.jsx';
import {CaduInput} from '../cadu-design-system/components/CaduInput.jsx';
import {Icon} from '../cadu-design-system/components/Icon.jsx';
import {IllustratedWait} from './Illustration.jsx';
import {LogoTile} from './PlannerUi.jsx';

const money = value => value == null ? '—' : `R$ ${Math.round(value).toLocaleString('pt-BR')}`;
const OBJECTIVE_LABEL = {reconhecimento: 'lembrança de marca', consideracao: 'consideração', leads: 'geração de leads',
  vendas: 'vendas', trafego: 'tráfego'};

function Delta({now, before}) {
  if (before == null || Math.round(before) === Math.round(now)) return null;
  const diff = Math.round(now - before);
  return <small className={`bal-delta ${diff > 0 ? 'is-up' : 'is-down'}`} title={`Hoje no plano: ${Math.round(before)}%`}>
    {diff > 0 ? '+' : ''}{diff} p.p.</small>;
}

/** Barra empilhada dos grupos de mídia: a forma do mix numa linha. */
function GroupBar({groups}) {
  const visible = groups.filter(group => group.pct > 0);
  return <div className="bal-groups">
    <div className="bal-groups__bar" role="img" aria-label={visible.map(group => `${group.label} ${group.pct}%`).join(', ')}>
      {visible.map((group, index) => <i key={group.group} style={{width: `${group.pct}%`}} className={`bal-tone-${index % 6}`}/>)}
    </div>
    <ul className="bal-groups__legend">{visible.map((group, index) => <li key={group.group}>
      <i className={`bal-tone-${index % 6}`} aria-hidden="true"/>{group.label}<b>{group.pct}%</b></li>)}</ul>
  </div>;
}

function Calendar({calendar, channels}) {
  if (!calendar) return null;
  return <div className="bal-calendar">
    <h3 className="pd-subtitle">Mês a mês{calendar.progressive && <CaduBadge tone="brand">Mix evolui ao longo do voo</CaduBadge>}</h3>
    {calendar.progressive && <p className="planner-muted">Os primeiros meses puxam para alcance e lembrança; os últimos, para o objetivo do plano.</p>}
    <div className="bal-calendar__scroll"><table>
      <thead><tr><th scope="col">Canal</th>{calendar.months.map(month => <th key={month.key} scope="col">{month.label}</th>)}</tr></thead>
      {/* Follow the table's order: numeric-looking object keys would reorder themselves. */}
      <tbody>{channels.filter(channel => calendar.cells[channel.resource_id]).map(channel => <tr key={channel.resource_id}>
        <th scope="row"><span className="bal-calendar__channel"><LogoTile src={channel.logo} name={channel.name} size="xs"/>{channel.name}</span></th>
        {calendar.cells[channel.resource_id].map(cell => <td key={cell.month}><b>{money(cell.value)}</b><small>{cell.pct}%</small></td>)}
      </tr>)}</tbody>
      <tfoot><tr><th scope="row">Total do mês</th>{calendar.totals.map(total => <td key={total.month}><b>{money(total.value)}</b></td>)}</tr></tfoot>
    </table></div>
  </div>;
}

/**
 * Balanceamento de mídia: o motor do SmartPlanner propõe, o usuário escolhe o
 * método, ajusta fatias à mão e vê a diferença para o que já está no plano
 * antes de aplicar.
 */
export function MediaBalance({request, plan, setPlan, notify, onEditDirection}) {
  const applied = plan.workbench?.balance || null;
  const [method, setMethod] = useState(applied?.method || '');
  const [manual, setManual] = useState(null);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const channelCount = (plan.items || []).filter(item => item.kind === 'canais').length;
  const timer = useRef(null);

  const query = useMemo(() => {
    const params = new URLSearchParams();
    if (manual) {
      params.set('method', 'manual');
      Object.entries(manual).forEach(([key, value]) => params.set(`w.${key}`, String(value || 0)));
    } else if (method) params.set('method', method);
    return params.toString();
  }, [method, manual]);

  useEffect(() => {
    let current = true;
    window.clearTimeout(timer.current);
    // Fatias manuais recalculam depois que a pessoa para de digitar.
    timer.current = window.setTimeout(() => {
      setLoading(true);
      request(`/plans/${plan.id}/balance?${query}`)
        .then(result => { if (current) { setData(result.balance); if (!method) setMethod(result.balance.method); } })
        .catch(error => { if (current) notify({tone: 'error', message: error.message}); })
        .finally(() => { if (current) setLoading(false); });
    }, manual ? 450 : 0);
    return () => { current = false; window.clearTimeout(timer.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [request, plan.id, plan.updated_at, channelCount, query]);

  if (!channelCount) return <p className="planner-muted">Escolha ao menos um canal para balancear a verba.</p>;
  if (!data) return <IllustratedWait slot="balance" title="Balanceando a verba" description="Distribuindo o investimento pelos canais do plano."/>;

  const editing = Boolean(manual);
  const manualTotal = editing ? Object.values(manual).reduce((sum, value) => sum + (Number(value) || 0), 0) : 100;
  const startManual = (key, value) => {
    const base = manual || Object.fromEntries(data.channels.map(channel => [channel.resource_id, channel.pct]));
    setManual({...base, [key]: value});
  };
  const pick = id => { setManual(null); setMethod(id); };
  // Keeps the proportions the user typed and closes 100% (largest remainder).
  const closeTo100 = () => {
    const entries = Object.entries(manual).map(([key, value]) => [key, Math.max(0, Number(value) || 0)]);
    const sum = entries.reduce((total, [, value]) => total + value, 0) || 1;
    const exact = entries.map(([key, value]) => [key, value * 100 / sum]);
    const floors = Object.fromEntries(exact.map(([key, value]) => [key, Math.floor(value)]));
    let rest = 100 - Object.values(floors).reduce((total, value) => total + value, 0);
    [...exact].sort((a, b) => (b[1] % 1) - (a[1] % 1)).forEach(([key]) => { if (rest > 0) { floors[key] += 1; rest -= 1; } });
    setManual(floors);
  };
  const apply = async () => {
    setSaving(true);
    try {
      const body = editing ? {method: 'manual', weights: manual} : {method: data.method};
      const result = await request(`/plans/${plan.id}/balance`, {method: 'POST', body: JSON.stringify(body)});
      setPlan(result.plan);
      setManual(null);
      if (editing) setMethod('manual');
      notify({message: 'Balanceamento aplicado ao plano.'});
    } catch (error) {
      notify({tone: 'error', message: error.message});
    } finally {
      setSaving(false);
    }
  };
  const isApplied = applied && applied.method === data.method && !editing
    && data.channels.every(channel => channel.current_pct != null && Math.round(channel.current_pct) === channel.pct);
  const strategy = editing ? {label: 'Manual do executivo', summary: 'Você definiu a fatia de cada canal.'} : data.strategy;

  return <div className={`bal${loading ? ' is-loading' : ''}`} aria-busy={loading}>
    <dl className="bal-summary">
      <div><dt>Investimento</dt><dd>{data.budget.value ? money(data.budget.value)
        : <button type="button" className="bal-link" onClick={onEditDirection}>Definir investimento</button>}</dd></div>
      <div><dt>Período</dt><dd>{data.period.parsed ? `${data.period.months.length} ${data.period.months.length === 1 ? 'mês' : 'meses'}`
        : <button type="button" className="bal-link" onClick={onEditDirection}>{data.period.label ? 'Ajustar período' : 'Definir período'}</button>}</dd>
        {data.period.label && <small>{data.period.label}</small>}</div>
      <div><dt>Estratégia adotada</dt><dd>{strategy.label}</dd><small>{isApplied ? 'Aplicada ao plano' : 'Ainda não aplicada'}</small></div>
    </dl>

    <fieldset className="bal-methods">
      <legend>Como dividir a verba{data.objective && <span> · objetivo: {OBJECTIVE_LABEL[data.objective] || data.objective}</span>}</legend>
      <div className="bal-methods__grid">{data.methods.filter(item => item.id !== 'manual').map(item => {
        const selected = !editing && data.method === item.id;
        return <label key={item.id} className={`bal-method${selected ? ' is-selected' : ''}`}>
          <input type="radio" name="balance-method" value={item.id} checked={selected} onChange={() => pick(item.id)}/>
          <span className="bal-method__head"><strong>{item.label}</strong>{item.primary && <CaduBadge tone="brand">Recomendado</CaduBadge>}</span>
          <small>{item.summary}</small>
        </label>;
      })}</div>
      <p className="bal-methods__when"><Icon name="analysis" size={14}/>{editing ? 'Você está ajustando as fatias à mão. A soma precisa fechar 100%.' : data.strategy.when}</p>
    </fieldset>

    <GroupBar groups={data.groups}/>

    <div className="bal-table" role="table" aria-label="Distribuição por canal">
      <div className="bal-row bal-row--head" role="row">
        <span role="columnheader">Canal e papel</span><span role="columnheader">Indicadores</span>
        <span role="columnheader" className="is-num">Fatia</span><span role="columnheader" className="is-num">Investimento</span>
      </div>
      {data.channels.map(channel => {
        const warning = data.warnings.find(item => item.resource_id === channel.resource_id);
        return <div key={channel.resource_id} role="row" className={`bal-row${warning ? ' has-warning' : ''}`}>
          <span role="cell" className="bal-row__channel"><LogoTile src={channel.logo} name={channel.name} color={channel.color}/>
            <span><strong>{channel.name}</strong><small>{channel.group_label} · {channel.role}</small></span></span>
          <span role="cell" className="bal-row__kpis">{channel.kpis.map(kpi => <i key={kpi}>{kpi}</i>)}</span>
          <span role="cell" className="is-num bal-row__pct">
            <CaduInput size="sm" inputMode="numeric" aria-label={`Fatia de ${channel.name} em %`}
              value={editing ? String(manual[channel.resource_id] ?? '') : String(channel.pct)}
              onChange={event => startManual(channel.resource_id, event.target.value.replace(/[^\d]/g, '').slice(0, 3))}/>
            <Delta now={channel.pct} before={channel.current_pct}/>
          </span>
          <span role="cell" className="is-num"><b>{money(channel.investment)}</b>
            {channel.minimum ? <small>mín. {money(channel.minimum)}</small> : null}</span>
        </div>;
      })}
      <div className="bal-row bal-row--foot" role="row">
        <span role="cell">Total</span><span role="cell"/>
        <span role="cell" className={`is-num${manualTotal !== 100 ? ' is-off' : ''}`}>{manualTotal}%</span>
        <span role="cell" className="is-num"><b>{money(data.budget.value)}</b></span>
      </div>
    </div>

    {data.warnings.length > 0 && <ul className="bal-warnings">{data.warnings.map(item => <li key={item.text} className={`is-${item.level}`}>
      <Icon name={item.level === 'attention' ? 'alert' : 'analysis'} size={14}/>{item.text}</li>)}</ul>}

    <Calendar calendar={data.calendar} channels={data.channels}/>

    <footer className="bal-actions">
      {editing && <CaduButton variant="tertiary" onClick={() => setManual(null)}>Descartar ajustes</CaduButton>}
      {editing && manualTotal !== 100 && <CaduButton variant="secondary" onClick={closeTo100}>Fechar em 100%</CaduButton>}
      <CaduButton loading={saving} disabled={loading || (editing && manualTotal !== 100) || isApplied} onClick={apply}>
        {isApplied ? 'Balanceamento aplicado' : 'Aplicar ao plano'}</CaduButton>
    </footer>
  </div>;
}
