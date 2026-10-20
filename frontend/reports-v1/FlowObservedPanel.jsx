import React,{useMemo,useState} from 'react';
import {ReportsPanelShell} from './ReportsPanelShell.jsx';
import {ReportsActionButton as Button} from './ReportsActionButton.jsx';
import {useFlowResource} from './FlowJourneyPanel.jsx';
import {addObservedChain, addObservedOrigins, addObservedPassage, goalNodes, normPath, observedPageDetail, observedPassageDetail, pagesByPath, reachesGoal, undrawnOrigins} from './flowObserved.js';

const count=value=>Number(value||0).toLocaleString('pt-BR');
const sessions=value=>`${count(value)} ${Number(value)===1?'sessão':'sessões'}`;
const POSITIONS={start:'no início da visita',middle:'no meio da visita',eve:'logo antes da conversão',only:'sozinha na visita'};

/**
 * While editing a published flow: what the Super Tag saw that the draft does not draw. An alert on the board opens
 * the list; each item opens its detail, where it becomes origins, steps or a whole way to the goal in the draft.
 * Reads the published period (all publications, current drawing); the draft can differ, so every item is checked
 * against the draft before it is offered.
 */
export function FlowObserved({flowId,days,journey,config,readOnly,onChange,onSelectNode,onNotify}){
  const [open,setOpen]=useState(false);
  const [detail,setDetail]=useState(null);
  const ready=journey?.status==='ready';
  const conversions=useFlowResource(flowId,'conversions',days,Boolean(flowId&&ready));
  const influence=useFlowResource(flowId,'influence',days,Boolean(flowId&&ready));
  const journeys=conversions.data?.journeys||[];
  const byId=useMemo(()=>new Map((config.nodes||[]).map(node=>[node.id,node])),[config.nodes]);
  const origins=useMemo(()=>ready?undrawnOrigins(journey,config):[],[ready,journey,config]);
  const passages=useMemo(()=>{
    if(!ready)return [];
    const drawn=new Set((config.edges||[]).map(edge=>`${edge.from}>${edge.to}`));
    return (journey.suggestions||[]).filter(item=>byId.has(item.from)&&byId.has(item.to)&&!drawn.has(`${item.from}>${item.to}`));
  },[ready,journey,config.edges,byId]);
  const pages=useMemo(()=>{
    const drafted=pagesByPath(config);
    return (influence.data?.off_flow||[]).filter(row=>!drafted.has(normPath(row.path)));
  },[influence.data,config]);
  const goals=goalNodes(config);
  const total=origins.length+passages.length+pages.length;
  if(!flowId||!ready||!total)return null;
  const apply=(next,message,select)=>{if(readOnly)return;onChange(next);onNotify?.(message);setDetail(null);if(select)onSelectNode?.(select);};
  const title=id=>byId.get(id)?.title||'Etapa';
  const addAllOrigins=list=>{const {config:next,added}=addObservedOrigins(config,list);apply(next,`${added.length} ${added.length===1?'origem adicionada':'origens adicionadas'} ao rascunho, ligadas às páginas onde os visitantes chegaram. Revise antes de publicar.`,added[0]);};

  const summary=[origins.length&&`${origins.length} ${origins.length===1?'origem':'origens'} de tráfego sem nó`,
    passages.length&&`${passages.length} ${passages.length===1?'caminho':'caminhos'} fora do desenho`,
    pages.length&&`${pages.length} ${pages.length===1?'página':'páginas'} nas conversões`].filter(Boolean).join(' · ');

  let body;
  if(detail?.type==='origin'){
    const origin=origins.find(item=>item.platform===detail.platform);
    const converted=journeys.filter(journey=>Object.values(journey.origin||{}).includes(detail.platform)).length;
    body=origin?<section className="flow-observed__detail">
      <h3>{origin.label}</h3>
      <p>{sessions(origin.sessions)} no período chegaram desta origem, e nenhuma origem do rascunho a representa.{converted?` Ela aparece em ${count(converted)} ${converted===1?'conversão':'conversões'} (primeiro contato, último contato ou na própria visita).`:''}</p>
      {origin.landings.length>0?<><strong>Onde chegaram</strong><ul>{origin.landings.map(item=><li key={item.node_id}>{title(item.node_id)} · {sessions(item.sessions)}</li>)}</ul></>:<p>As páginas onde chegaram não estão mais no rascunho: a origem entra sem ligação.</p>}
      <Button color="primary" disabled={readOnly} onClick={()=>addAllOrigins([origin])}>Adicionar esta origem</Button>
    </section>:null;
  }else if(detail?.type==='passage'){
    const facts=observedPassageDetail(journeys,detail.from,detail.to,config);
    const goal=goals[0];
    body=<section className="flow-observed__detail">
      <h3>{title(detail.from)} → {title(detail.to)}</h3>
      <p>{sessions(detail.sessions)} {Number(detail.sessions)===1?'passou':'passaram'} direto de uma etapa para a outra, sem uma ligação desenhada.{conversions.data?facts.conversions?` ${count(facts.conversions)} ${facts.conversions===1?'conversão passou':'conversões passaram'} por aqui.`:' Nenhuma conversão do período passou por aqui.':''}</p>
      <p>{facts.reaches_goal?`${title(detail.to)} já leva ao objetivo pelo desenho.`:goal?`${title(detail.to)} ainda não leva ao objetivo: a ligação também cria um passo planejado até ${goal.title||'a conversão'}.`:'O rascunho não tem uma etapa de conversão para ligar.'}</p>
      <Button color="primary" disabled={readOnly} onClick={()=>apply(addObservedPassage(config,{from:detail.from,to:detail.to,goalId:goal?.id}),'Caminho observado adicionado ao rascunho. Revise antes de publicar.',detail.to)}>{facts.reaches_goal||!goal?'Adicionar a ligação':'Adicionar a ligação até o objetivo'}</Button>
    </section>;
  }else if(detail?.type==='page'){
    const row=pages.find(item=>item.path===detail.path);
    const facts=observedPageDetail(journeys,detail.path,config);
    const goal=goals[0];
    // The page itself keeps the name the site catalog gives it; the journey only knows the address.
    const best=facts.best&&{...facts.best,pages:facts.best.pages.map(page=>page.path===row?.path?{...page,title:row.title}:page)};
    const way=best?[best.before?title(best.before):'Início da visita',...best.pages.map(page=>page.title),best.after?title(best.after):goal?.title||'Conversão']:[];
    body=row?<section className="flow-observed__detail">
      <h3>{row.title}</h3><small>{row.path}</small>
      <p>{[row.assisted&&`${count(row.assisted)} ${row.assisted===1?'conversão':'conversões'} passaram por ela na mesma visita`,row.assisted_prior&&`${count(row.assisted_prior)} em uma visita anterior`].filter(Boolean).join(' · ')}.{row.position?` Costuma aparecer ${POSITIONS[row.position]}.`:''}{row.rate_with!=null?` ${row.rate_with}% de quem a viu converteu (sem ela: ${row.rate_without}%).`:''}</p>
      {best?<><strong>Caminho mais comum ({count(best.conversions)} de {count(facts.conversions)})</strong><p className="flow-journey-panel__steps">{way.map((label,index)=><span key={index} className={index>0&&index<=best.pages.length?'is-off-flow':''}>{label}</span>)}</p>
        {facts.ways.length>1&&<small>Outros {facts.ways.length-1} caminhos passam por ela.</small>}</>:<p>{conversions.loading?'Lendo as conversões…':'Ela só aparece em visitas anteriores das conversões: entra no rascunho como etapa solta.'}</p>}
      <div className="flow-observed__actions">
        {best&&<Button color="primary" disabled={readOnly} onClick={()=>{const {config:next,created}=addObservedChain(config,{...best,goalId:goal?.id});apply(next,`${created.length} ${created.length===1?'etapa criada':'etapas criadas'} no caminho até ${best.after?title(best.after):goal?.title||'o objetivo'}. Revise antes de publicar.`,created[0]);}}>{best.pages.length>1?`Criar o caminho (${best.pages.length} páginas) até o objetivo`:'Criar a etapa no caminho até o objetivo'}</Button>}
        <Button disabled={readOnly} onClick={()=>{const {config:next,created}=addObservedChain(config,{before:best?.before||null,pages:[{path:row.path,title:row.title}],after:null,goalId:null});apply(next,'Página adicionada ao rascunho. Ligue-a às próximas etapas antes de publicar.',created[0]);}}>Só adicionar a página</Button>
      </div>
    </section>:null;
  }
  return <>
    <div className="flow-observed-notice" role="status"><Button onClick={()=>{setOpen(value=>!value);setDetail(null);}} aria-expanded={open}>⚠ Observado no site: {summary}</Button></div>
    {open&&<ReportsPanelShell compact className="flow-blueprint-panel flow-observed" title={detail?'Detalhe observado':'Observado no site'} onClose={()=>{setOpen(false);setDetail(null);}}>
      {readOnly&&<p className="flow-observed__hint">Volte à edição para trazer estes itens para o rascunho.</p>}
      {detail?<><Button size="sm" onClick={()=>setDetail(null)}>← Voltar à lista</Button>{body}</>:<>
        <p className="flow-observed__hint">Dados de {days} dias da publicação, de todas as versões. Cada item abre o que foi visto e como trazê-lo para o rascunho.</p>
        {origins.length>0&&<section className="flow-observed__group"><header><h3>Origens de tráfego sem nó</h3><Button size="sm" color="primary" disabled={readOnly} onClick={()=>addAllOrigins(origins)}>Adicionar todas ({origins.length})</Button></header>
          <ul>{origins.map(item=><li key={item.platform}><button type="button" className="flow-observed__item" onClick={()=>setDetail({type:'origin',platform:item.platform})}><b>{item.label}</b><small>{sessions(item.sessions)} · chega em {item.landings.length?item.landings.slice(0,2).map(landing=>title(landing.node_id)).join(', '):'páginas fora do rascunho'}</small></button></li>)}</ul></section>}
        {passages.length>0&&<section className="flow-observed__group"><header><h3>Caminhos observados fora do desenho</h3></header>
          <ul>{passages.map(item=><li key={`${item.from}>${item.to}`}><button type="button" className="flow-observed__item is-alert" onClick={()=>setDetail({type:'passage',...item})}><b>{title(item.from)} → {title(item.to)}</b><small>{sessions(item.sessions)}{reachesGoal(config,item.to)?'':' · não leva ao objetivo'}</small></button></li>)}</ul></section>}
        {pages.length>0&&<section className="flow-observed__group"><header><h3>Páginas fora do desenho nas conversões</h3></header>
          <ul>{pages.map(row=><li key={row.path}><button type="button" className="flow-observed__item is-alert" onClick={()=>setDetail({type:'page',path:row.path})}><b>{row.title}</b><small>{row.path} · {count(row.assisted+row.assisted_prior)} {row.assisted+row.assisted_prior===1?'conversão':'conversões'}</small></button></li>)}</ul></section>}
        <small className="flow-observed__hint">É associação observada, não prova de causa.</small>
      </>}
    </ReportsPanelShell>}
  </>;
}
