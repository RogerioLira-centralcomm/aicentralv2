import React, {useEffect, useState} from 'react';
import {Button} from '../cadu-design-system/untitled-kit/button.tsx';
import {json} from './reportsCommon.jsx';

const count=value=>Number(value||0).toLocaleString('pt-BR');
const POSITIONS={start:'no início',middle:'no meio',eve:'logo antes da conversão',only:'única página'};
const TABS=[['summary','Resumo'],['conversions','Conversões'],['pages','Páginas fora']];

// Conversions and page influence load only when their tab opens, for the same period as the map.
export function useFlowResource(flowId,resource,days,enabled){
  const [state,setState]=useState({data:null,error:'',loading:false});
  useEffect(()=>{
    if(!enabled||!flowId)return;
    let cancelled=false;setState({data:null,error:'',loading:true});
    json(`/connect/api/v2/reports/flow/flows/${flowId}/${resource}?days=${days}`)
      .then(data=>{if(!cancelled)setState({data,error:'',loading:false});})
      .catch(failure=>{if(!cancelled)setState({data:null,error:failure.message,loading:false});});
    return()=>{cancelled=true;};
  },[flowId,resource,days,enabled]);
  return state;
}

function Origin({origin,labels}){
  const label=id=>labels?.[id]||id;
  const parts=[`Sessão: ${label(origin.session)}`];
  if(origin.first!==origin.session)parts.unshift(`1º contato: ${label(origin.first)}`);
  if(origin.last_non_direct!==origin.first&&origin.last_non_direct!==origin.session&&origin.last_non_direct!=='direct')parts.splice(1,0,`último não direto: ${label(origin.last_non_direct)}`);
  return <small className="flow-journey-panel__origin">{parts.join(' · ')}</small>;
}

function Conversions({state}){
  const {data,error,loading}=state;
  if(loading)return <p>Carregando conversões…</p>;
  if(error)return <p role="alert">{error}</p>;
  if(!data)return null;
  if(data.status==='no_goal')return <p>Este fluxo não tem um nó de conversão com endereço. Adicione um para ver o caminho de cada conversão.</p>;
  if(data.status!=='ready')return <p>Publique o fluxo para acompanhar as conversões.</p>;
  if(!data.journeys.length)return <p>Nenhuma conversão neste período.</p>;
  const {coverage}=data;
  return <div className="flow-journey-panel__section">
    <p>{count(coverage.conversions)} conversões{coverage.complete?'':' (as mais recentes)'} · {count(coverage.identified)} com visitante identificado, que mostram visitas anteriores.</p>
    {data.top_paths.length>0&&<div className="flow-journey-panel__group"><strong>Caminhos mais comuns</strong><ul>{data.top_paths.map(path=><li key={path.steps.join('>')}><span>{path.steps.join(' → ')}</span><b>{count(path.conversions)}</b></li>)}</ul></div>}
    <ol className="flow-journey-panel__journeys">{data.journeys.map(journey=><li key={journey.id}>
      <div><strong>{new Date(journey.converted_at).toLocaleString('pt-BR',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'})}</strong> <small>{journey.goal.title}</small></div>
      <Origin origin={journey.origin} labels={data.origin_labels}/>
      {journey.prior_sessions.length>0&&<small>Antes: {journey.prior_sessions.map(visit=>`${data.origin_labels?.[visit.platform]||visit.platform} (${visit.pages.join(', ')})`).join(' · ')}</small>}
      <p className="flow-journey-panel__steps">{journey.steps.map((step,index)=><span key={index} className={step.off_flow?'is-off-flow':step.goal?'is-goal':''} title={step.path||''}>{step.kind==='form'?'Formulário':step.kind==='whatsapp'?'WhatsApp':step.title}{step.seconds?` · ${step.seconds}s`:''}</span>)}</p>
    </li>)}</ol>
    <small>Tracejado: página fora do desenho. {data.notes?.[3]}</small>
  </div>;
}

function Pages({state,onAddPage}){
  const {data,error,loading}=state;
  if(loading)return <p>Carregando páginas…</p>;
  if(error)return <p role="alert">{error}</p>;
  if(!data)return null;
  if(data.status==='no_goal')return <p>Este fluxo não tem um nó de conversão com endereço.</p>;
  if(data.status!=='ready')return <p>Publique o fluxo para acompanhar as páginas.</p>;
  const rate=row=>row.rate_with==null?null:`${row.rate_with}% de quem viu converteu (sem ela: ${row.rate_without}%)`;
  return <div className="flow-journey-panel__section">
    <p>{count(data.conversions)} conversões e {count(data.sessions)} sessões no período.{!data.compare_rates&&' Poucas conversões para comparar taxas: os números abaixo são contagens.'}</p>
    <div className="flow-journey-panel__group"><strong>Influenciam e não estão no fluxo</strong>{data.off_flow.length?<ul>{data.off_flow.map(row=><li key={row.key||row.path}><span><b>{row.title}</b> <small>{row.host?`${row.host}${row.path}`:row.path}</small><br/><small>{[row.assisted&&`${count(row.assisted)} conversões na mesma visita`,row.assisted_prior&&`${count(row.assisted_prior)} em visita anterior`].filter(Boolean).join(' · ')}{row.position?` · costuma aparecer ${POSITIONS[row.position]}`:''}{rate(row)?` · ${rate(row)}`:''}</small></span>{onAddPage&&<Button size="xs" color="secondary" onPress={()=>onAddPage(row)}>Adicionar ao rascunho</Button>}</li>)}</ul>:<small>Nenhuma página fora do desenho apareceu em {data.thresholds.min_assisted} ou mais conversões.</small>}</div>
    {data.unused.length>0&&<div className="flow-journey-panel__group"><strong>Páginas do fluxo que nenhuma conversão usou</strong><ul>{data.unused.map(row=><li key={row.node_id}><span>{row.title} <small>{row.host?`${row.host}${row.path}`:row.path} · {count(row.sessions)} sessões</small></span></li>)}</ul></div>}
    <small>{data.notes?.[3]}</small>
  </div>;
}

export function FlowJourneyPanel({flowId,journey,days,onDaysChange,onAddSuggestion,onAddPage,onClose,loading,error}) {
  const [tab,setTab]=useState('summary');
  const conversions=useFlowResource(flowId,'conversions',days,tab==='conversions');
  const pages=useFlowResource(flowId,'influence',days,tab==='pages');
  const suggestions=journey?.suggestions||[];
  const byId=Object.fromEntries((journey?.config?.nodes||[]).map(node=>[node.id,node.title]));
  const {outcome,funnel}=journey||{};
  return <section className="flow-journey-panel" aria-label="Jornada observada"><div className="flow-journey-panel__head"><div><strong>Jornada observada</strong><small>{journey?.scope?.metrics==='publication'?`Só a publicação v${journey.revision}`:`Todas as publicações do período · desenho v${journey?.revision??'—'}`}</small></div><Button size="sm" color="tertiary" onPress={onClose}>Fechar</Button></div>
    <div className="flow-journey-panel__filters">{[7,30,90].map(period=><Button key={period} size="sm" color={period===days?'secondary':'tertiary'} onPress={()=>onDaysChange(period)}>{period} dias</Button>)}</div>
    {flowId&&<div className="flow-journey-panel__tabs" role="group" aria-label="Seções da jornada">{TABS.map(([id,label])=><Button key={id} aria-pressed={tab===id} size="sm" color={tab===id?'secondary':'tertiary'} onPress={()=>setTab(id)}>{label}</Button>)}</div>}
    {tab==='conversions'?<Conversions state={conversions}/>:tab==='pages'?<Pages state={pages} onAddPage={onAddPage}/>:
    loading?<p>Carregando eventos da Super Tag…</p>:error?<p role="alert">{error}</p>:journey?.status!=='ready'?<p>Publique o fluxo e mantenha a instalação ativa para acompanhar a jornada.</p>:journey.collection?.status==='no_data'?<p>Sem eventos recebidos neste período. Confira a Super Tag antes de interpretar taxas e volumes.</p>:<>
      <p><strong>{outcome?.rate==null?'—':`${outcome.rate}%`}</strong> de conversão · {count(outcome?.converted)} de {count(outcome?.sessions)} sessões que chegaram ao fluxo. A partir da entrada: {funnel?.rate==null?'—':`${funnel.rate}%`} ({count(funnel?.conversions)} de {count(funnel?.entries)} que entraram por uma etapa de entrada).</p>
      <p>Cada nó mostra sessões únicas; cada seta mostra passagem direta entre etapas.{journey.scope?.metrics!=='publication'&&(journey.scope?.publications?.length||0)>1&&` Inclui ${journey.scope.publications.length} publicações, lidas com o desenho atual.`}{flowId&&outcome?.converted>0&&<> <Button size="xs" color="link-color" onPress={()=>setTab('conversions')}>Ver o caminho das {count(outcome.converted)} conversões</Button></>}</p>
      <div className="flow-journey-panel__suggestions"><strong>Caminhos observados fora do desenho</strong>{suggestions.length?<ul>{suggestions.slice(0,5).map(item=><li key={`${item.from}:${item.to}`}><span>{byId[item.from]||item.from} → {byId[item.to]||item.to} · {item.sessions.toLocaleString('pt-BR')} sessões</span><Button size="xs" color="secondary" onPress={()=>onAddSuggestion(item)}>Adicionar ao rascunho</Button></li>)}</ul>:<small>Nenhum caminho adicional entre etapas desenhadas.</small>}{flowId&&<Button size="xs" color="link-color" onPress={()=>setTab('pages')}>Páginas fora do desenho nas conversões</Button>}</div></>}
  </section>;
}
