import React,{useMemo} from 'react';
import {pageHealth,byPriority} from './flowMonitorHealth.js';
import {FLOW_STAGES,stageFor} from './flowStages.js';
import {ReportsNativeSelect} from './ReportsNativeSelect.jsx';
import {reportUrl,shortDate,integer} from './reportsCommon.jsx';

const STATUS={online:'Online',degraded:'Com falhas',offline:'Fora do ar',checking:'Verificando'};
const TYPE={source:'Origem',page:'Página',form:'Formulário',event:'Evento',conversion:'Conversão',whatsapp:'WhatsApp',error:'Erro',condition:'Condição'};
const ms=value=>value==null?'—':value>=1000?`${(value/1000).toLocaleString('pt-BR',{maximumFractionDigits:1})} s`:`${value} ms`;
const percent=(part,whole)=>whole>0&&part!=null?`${Math.round(1000*part/whole)/10}%`.replace('.',','):'—';

/** Top-of-page warning when a page has failed enough checks in a row for the alert center to open an alert. */
export function FlowFailureBanner({checks,alertsUrl=reportUrl('alerts')}) {
  const down=useMemo(()=>pageHealth(checks).filter(row=>row.confirmedDown||row.status!=='online'),[checks]);
  if(!down.length)return null;
  const confirmed=down.filter(row=>row.confirmedDown);
  return <section className={`flow-failure-banner is-${confirmed.length?'error':'warning'}`} role="alert">
    <div><strong>{confirmed.length?`${confirmed.length} ${confirmed.length===1?'página fora do ar':'páginas fora do ar'}`:`${down.length} ${down.length===1?'página falhou':'páginas falharam'} na última verificação`}</strong>
      <ul>{down.slice(0,4).map(row=><li key={row.key}><b>{row.label}</b> · {row.host}{row.path} · {row.http?`HTTP ${row.http}`:row.detail}{row.failing>1?` · ${row.failing} falhas seguidas`:''}</li>)}{down.length>4&&<li>e mais {down.length-4}</li>}</ul>
      <small>{confirmed.length?'Alerta aberto na central de Alertas.':'Com a próxima falha seguida, um alerta é aberto na central de Alertas.'}</small></div>
    <a href={alertsUrl}>Ver alertas</a>
  </section>;
}

/** Availability per page: status, address, HTTP, response time, uptime over recent checks and consecutive failures. */
export function FlowPageHealthTable({checks,busy}) {
  const rows=useMemo(()=>pageHealth(checks).sort(byPriority),[checks]);
  if(!rows.length)return null;
  return <div className="reports-table-wrap"><table className={`cadu-table flow-health-table${busy?' is-checking':''}`}><thead><tr>
    <th>Status</th><th>Página</th><th>HTTP</th><th>Resposta</th><th>Média</th><th>Disponibilidade</th><th>Falhas seguidas</th><th>Última falha</th><th>Detalhe</th></tr></thead>
    <tbody>{rows.map(row=><tr key={row.key} className={row.confirmedDown?'is-down':''}>
      <td><span className={`reports-monitor-status is-${busy?'checking':row.status}`}><i/>{busy?'Verificando…':STATUS[row.status]||row.status}</span></td>
      <td><strong>{row.label}</strong><small>{row.host}{row.path}</small></td>
      <td>{row.http||'—'}</td><td>{ms(row.responseMs)}</td><td>{ms(row.averageMs)}</td>
      <td>{row.uptime==null?'—':`${String(row.uptime).replace('.',',')}%`}<small>{row.readings} {row.readings===1?'verificação':'verificações'}</small></td>
      <td>{row.failing||'—'}</td><td>{row.lastFailureAt?shortDate(row.lastFailureAt):'Sem falhas'}</td><td>{row.detail}</td></tr>)}</tbody></table></div>;
}

/** The journey as numbers: one row per step, from where visitors arrive to where they leave. No map. */
export function FlowJourneyNumbers({journey,days,onDaysChange,loading,error}) {
  const rows=useMemo(()=>{
    if(journey?.status!=='ready')return [];
    const metrics=new Map((journey.nodes||[]).map(item=>[item.id,item]));
    const order=id=>FLOW_STAGES.findIndex(stage=>stage.id===id);
    const arrived=(journey.config?.nodes||[]).filter(node=>node.type==='source').reduce((sum,node)=>sum+Number(metrics.get(node.id)?.sessions||0),0);
    return (journey.config?.nodes||[]).filter(node=>node.type!=='note').map(node=>{
      const metric=metrics.get(node.id)||{};
      const outgoing=(journey.edges||[]).filter(edge=>edge.from===node.id&&edge.sessions!=null);
      const exits=metric.exits!=null?metric.exits:outgoing.length||node.type==='conversion'?Math.max(0,Number(metric.sessions||0)-outgoing.reduce((sum,edge)=>sum+Number(edge.sessions||0),0)):null;
      return {node,stage:stageFor(node),sessions:metric.sessions,exits,activeMs:metric.avg_active_ms,arrived};
    }).filter(row=>row.node.type!=='source'&&(row.sessions!=null||row.node.type!=='condition')).sort((a,b)=>order(a.stage)-order(b.stage)||(b.sessions||0)-(a.sessions||0));
  },[journey]);
  const stageLabel=id=>FLOW_STAGES.find(stage=>stage.id===id)?.label||'';
  return <article className="reports-panel reports-span-three flow-journey-numbers">
    <div className="reports-panel-head"><div><h3>Jornada em números{journey?.revision!=null?` · v${journey.revision}`:''}</h3><p>Por etapa: sessões, saídas e tempo ativo. O desenho do fluxo fica no editor.</p></div>
      <ReportsNativeSelect aria-label="Período da jornada" value={days} onChange={event=>onDaysChange(Number(event.target.value))}>{[7,30,90].map(value=><option key={value} value={value}>Últimos {value} dias</option>)}</ReportsNativeSelect></div>
    {error?<p className="reports-error" role="alert">{error}</p>:loading&&!journey?<p className="reports-info" role="status">Carregando a jornada…</p>:journey?.status!=='ready'?<p className="reports-info">Publique o fluxo para medir a jornada desta versão.</p>
      :<div className="reports-table-wrap"><table className="cadu-table"><thead><tr><th>Etapa</th><th>Tipo</th><th>Sessões</th><th>% de quem chegou</th><th>Saídas</th><th>Taxa de saída</th><th>Tempo ativo</th></tr></thead>
        <tbody>{rows.map(row=><tr key={row.node.id}><td><strong>{row.node.title||'Sem nome'}</strong><small>{[stageLabel(row.stage),row.node.path].filter(Boolean).join(' · ')}</small></td>
          <td>{TYPE[row.node.type]||row.node.type}</td><td>{row.sessions==null?'—':integer(row.sessions)}</td><td>{row.node.type==='source'?'—':percent(row.sessions,row.arrived)}</td>
          <td>{row.exits==null?'—':integer(row.exits)}</td><td>{percent(row.exits,row.sessions)}</td><td>{row.activeMs==null?'—':ms(Math.round(row.activeMs))}</td></tr>)}</tbody></table></div>}
  </article>;
}
