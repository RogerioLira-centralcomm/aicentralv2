import {ReportsPanelShell} from './ReportsPanelShell.jsx';
import {FlowLiveAudience} from './FlowLiveAudience.jsx';
import {FlowSolutionSwitcher,FlowNavbarAccount} from './FlowNavbarAccount.jsx';
import React,{useEffect,useMemo,useRef,useState} from 'react';
import {FlowCanvas} from './FlowCanvas.jsx';
import {ReportsActionButton as Button} from './ReportsActionButton.jsx';
import {ReportsFieldInput} from './ReportsFieldInput.jsx';
import {ReportsNativeSelect} from './ReportsNativeSelect.jsx';
import {usePanelLayout} from './usePanelLayout.js';
import {useFlowPolling} from './useFlowPolling.js';
import {flowBlockFor} from './flowBlockRegistry.js';
import {fitGroups} from './flowGroups.js';
import {layoutFlow} from './flowLayout.js';
import {SearchLg,ArrowLeft,FilterLines,RefreshCw01,XClose} from '@untitledui/icons';
import './flow-monitor-workspace.css';
const value=n=>n==null?'Não disponível':Number(n).toLocaleString('pt-BR');

export function FlowMonitorWorkspace({flow,client,csrf,versions=[],filters,baseConfig,onEdit,onBack,headerActions}) {
  const [days,setDays]=useState(()=>{const value=Number(new URLSearchParams(location.search).get('days'))||Number(filters.period);return [7,30,90].includes(value)?value:30;});
  const [revision,setRevision]=useState(new URLSearchParams(location.search).get('revision')||'');
  const [customDates,setCustomDates]=useState(Boolean(filters.startDate&&filters.endDate));
  const [paused,setPaused]=useState(false);
  const [explorer,setExplorer]=useState(false);
  const [audience,setAudience]=useState(false);
  const [audienceFilter,setAudienceFilter]=useState('all');
  const [selection,setSelection]=useState(null);
  const [query,setQuery]=useState('');
  const [positions,setPositions]=useState(null);
  const [notice,setNotice]=useState('');
  const [layer,setLayer]=useState('volume');
  const [list,setList]=useState(window.innerWidth<768);
  usePanelLayout(explorer,Boolean(selection)||audience,setExplorer,setSelection);
  const canvas=useRef(null);
  const request=useRef(0);
  const params=new URLSearchParams({client_id:client.client_id,days:String(days)});
  if(revision)params.set('revision',revision);
  for(const [name,key] of [['account_id','account'],['campaign_id','campaign'],['platform','platform']])if(filters[key])params.set(name,filters[key]);
  if(customDates&&filters.startDate&&filters.endDate){params.set('start_date',filters.startDate);params.set('end_date',filters.endDate);}
  const journey=useFlowPolling(`/connect/api/v2/reports/flow/flows/${flow.id}/journey?${params}`,{interval:60000,enabled:!paused});
  const live=useFlowPolling(`/connect/api/v2/reports/flow/flows/${flow.id}/live?client_id=${client.client_id}&identity=${audienceFilter}`,{enabled:!paused});
  const historical=Boolean(revision&&Number(revision)!==Number(live.data?.revision??flow.published_revision));
  const config=journey.data?.config||baseConfig||{nodes:[],edges:[]};
  const graphKey=JSON.stringify([flow.id,journey.data?.revision,config.nodes?.map(n=>[n.id,n.x,n.y]),config.edges]);
  const keyRef=useRef(graphKey);keyRef.current=graphKey;
  const document=useMemo(()=>fitGroups({...config,nodes:(config.nodes||[]).map(node=>({...node,...(positions?.key===graphKey?positions.map[node.id]:null)}))}),[config,positions,graphKey]);
  const ready=journey.data?.status==='ready'&&!journey.error;
  const compatible=journey.data?.revision!=null&&String(journey.data.revision)===String(live.data?.revision);
  const liveReady=ready&&compatible&&live.fresh&&!historical&&!paused&&!live.error&&live.data?.status==='ready';
  useEffect(()=>{if(!revision&&live.fresh&&journey.data?.revision!=null&&!compatible)journey.retry();},[revision,live.fresh,live.data?.revision,journey.data?.revision,compatible,journey.retry]);
  const operational=liveReady&&live.data?.tracking_health?.status==='healthy';
  const metrics=useMemo(()=>ready?{...journey.data,nodes:journey.data.nodes.map(n=>({...n,sessions:journey.data.collection?.status==='no_data'?null:n.sessions,events:journey.data.collection?.status==='no_data'?null:n.events,presence:liveReady?live.data?.node_presence?.[n.id]:null}))}:null,[ready,journey.data,liveReady,live.data]);
  const displayMetrics=useMemo(()=>metrics&&layer!=='volume'?{...metrics,edges:[]}:metrics,[metrics,layer]);
  const node=selection?.type==='node'?document.nodes.find(n=>n.id===selection.id):null;
  const edge=selection?.type==='edge'?document.edges.find(e=>e.id===selection.id):null;
  const metric=node?metrics?.nodes.find(n=>n.id===node.id):edge?metrics?.edges.find(e=>e.id===edge.id):null;
  const select=selection=>{setAudience(false);setSelection(selection);if(window.innerWidth<1440)setExplorer(false);};
  const organize=async()=>{
    const id=++request.current,key=graphKey;setNotice('Organizando…');
    try {const nodes=await layoutFlow(config);if(id!==request.current||key!==keyRef.current)return;setPositions({key,map:Object.fromEntries(nodes.map(n=>[n.id,{x:n.x,y:n.y}]))});setNotice('Organizado · publicação preservada');}
    catch(error){setNotice(`Não foi possível organizar: ${error.message}`);}
  };
  useEffect(()=>{setPositions(null);setSelection(null);},[flow.id,revision]);
  useEffect(()=>{
    const url=new URL(location.href);if(revision)url.searchParams.set('revision',revision);else url.searchParams.delete('revision');url.searchParams.set('days',String(days));history.replaceState(null,'',url);
  },[revision,days]);
  const filtered=document.nodes.filter(n=>`${n.title} ${n.path||''}`.toLowerCase().includes(query.toLowerCase()));
  const scope=journey.data?.scope;
  const collection=journey.data?.collection;
  const periodLabel=scope?.from&&scope?.to?`${new Date(scope.from).toLocaleDateString('pt-BR',{timeZone:journey.data?.timezone||'America/Sao_Paulo'})} a ${new Date(Date.parse(scope.to)-1000).toLocaleDateString('pt-BR',{timeZone:journey.data?.timezone||'America/Sao_Paulo'})}`:customDates?`${filters.startDate} a ${filters.endDate}`:`Últimos ${days} dias`;
  return <section className="flow-monitor-workspace">
    <header className="flow-workspace-header"><div className="flow-workspace-identity"><Button color="tertiary" size="sm" aria-label="Voltar aos fluxos" onClick={onBack}><ArrowLeft size={18}/></Button><FlowSolutionSwitcher/><span>{flow.name}</span></div><nav aria-label="Modo do fluxo">{onEdit&&<Button color="tertiary" size="sm" onClick={onEdit}>{client.role==='viewer'?'Ver fluxo':'Editar'}</Button>}<Button color="secondary" size="sm" aria-current="page" onClick={()=>{}}>Monitorar</Button></nav><div className="flow-workspace-header-actions">{headerActions}<ReportsNativeSelect aria-label="Período" value={customDates?'custom':days} onChange={e=>{setCustomDates(false);setDays(Number(e.target.value));}}>{customDates&&<option value="custom">Período personalizado</option>}{[7,30,90].map(d=><option key={d} value={d}>Últimos {d} dias</option>)}</ReportsNativeSelect><Button color="tertiary" size="sm" onClick={()=>setPaused(v=>!v)}>{paused?'Retomar':'Pausar'}</Button><FlowNavbarAccount/></div></header>
    <div className="flow-monitor-scope" role="status">Publicação v{journey.data?.revision||flow.published_revision||'—'} · {periodLabel} · fuso {journey.data?.timezone||'America/Sao_Paulo'} · {collection?.source||'Super Tag deste fluxo'} · {collection?.status==='no_data'?'Sem eventos no período':collection?.last_event_at?`Último evento: ${new Date(collection.last_event_at).toLocaleString('pt-BR')}`:'Última coleta indisponível'}{collection?.coverage_percent!=null&&` · ${collection.coverage_percent}% dos eventos associados a nós`}</div>
    <div className="flow-monitor-summary"><div><small>Sessões de entrada</small><strong>{value(ready&&collection?.status!=='no_data'?journey.data.funnel?.entries:null)}</strong></div><div><small>Sessões com conversão</small><strong>{value(ready&&collection?.status!=='no_data'?journey.data.funnel?.conversions:null)}</strong></div><div><small>Taxa do funil</small><strong>{ready&&collection?.status!=='no_data'&&journey.data.funnel?.rate!=null?`${journey.data.funnel.rate}%`:'Não disponível'}</strong></div><div><small>{paused?'Última consulta':'Agora'} · todas as publicações</small><strong>{value(liveReady?live.data?.active_sessions:null)} <small>sessões</small></strong></div><span role="status">{paused?'Atualização pausada':live.error?'Atualização com falha':live.data?.status==='capacity_exceeded'?'Volume acima do limite ao vivo':historical?'Publicação histórica':operational?'● Coleta operacional':'Aguardando sinais'}<small>{live.updatedAt?`${paused?'Última consulta':'Consulta'} · ${live.updatedAt.toLocaleTimeString('pt-BR')}`:'Aguardando consulta'}</small></span></div>
    <div className="flow-monitor-body"><nav className="flow-workspace-rail" aria-label="Ferramentas do mapa"><Button color="tertiary" size="sm" aria-label="Explorar etapas" aria-pressed={explorer} onClick={()=>{setExplorer(v=>!v);if(window.innerWidth<1440)setSelection(null);}}><SearchLg size={18}/></Button><Button color="tertiary" size="sm" aria-label="Alternar lista de etapas" aria-pressed={list} onClick={()=>setList(v=>!v)}><FilterLines size={18}/></Button><Button color="tertiary" size="sm" aria-label="Usuários online e navegação" aria-pressed={audience} onClick={()=>{setAudience(v=>!v);setSelection(null);setExplorer(false);}}>◎</Button><Button color="tertiary" size="sm" aria-label="Atualizar métricas" onClick={()=>{journey.retry();live.retry();}}><RefreshCw01 size={18}/></Button></nav>
    <div className={`flow-monitor-stage${explorer?' has-explorer':''}${selection||audience?' has-inspector':''}`}>
      {(journey.error||live.error)&&<div className="flow-workspace-notice" role="alert">{journey.error||live.error} <Button color="link-color" size="sm" onClick={()=>{journey.retry();live.retry();}}>Tentar novamente</Button></div>}
      {!journey.data&&!journey.error&&<div className="flow-workspace-notice" role="status">Carregando publicação e métricas…</div>}
      {journey.data?.status==='unavailable'&&<div className="flow-workspace-notice">Publique este fluxo para começar a medir. {onEdit&&<Button color="link-color" size="sm" onClick={onEdit}>Abrir fluxo</Button>}</div>}
      {list?<div className="flow-monitor-list">{filtered.map(n=><Button color="secondary" key={n.id} onClick={()=>select({type:'node',id:n.id})}>{n.title} · {n.path||'Etapa visual'} · {value(metrics?.nodes.find(m=>m.id===n.id)?.sessions)} sessões</Button>)}</div>:<FlowCanvas previewContext={{flowId:flow.id,clientId:client.client_id,csrf,canCapture:client.role!=='viewer',revision:journey.data?.revision||flow.published_revision}} key={`${flow.id}:${revision}`} config={document} readOnly setConfig={()=>{}} selectedNodeId={node?.id||''} setSelectedNodeId={id=>select(id?{type:'node',id}:null)} onSelectedEdge={id=>select({type:'edge',id})} onReady={instance=>{canvas.current=instance;}} fitOnMount journey={displayMetrics} live={liveReady?live.data:null} liveScope={`${flow.id}:${live.data?.revision??''}`} operational={operational} onOrganize={organize}/>}
      {explorer&&<ReportsPanelShell className="flow-workspace-panel is-explorer" title="Explorar fluxo" closeLabel="Fechar explorador" onClose={()=>setExplorer(false)}><ReportsFieldInput aria-label="Buscar etapa" placeholder="Buscar nome ou URL" value={query} onChange={e=>setQuery(e.target.value)}/><div className="flow-panel-scroll">{filtered.map(n=><Button key={n.id} color="tertiary" size="sm" onClick={()=>{select({type:'node',id:n.id});canvas.current?.fitView({nodes:[{id:n.id}],maxZoom:1,duration:200,padding:.5});}}>{n.title}<small>{n.path||flowBlockFor(n).category}</small></Button>)}</div></ReportsPanelShell>}
      {audience&&<FlowLiveAudience snapshot={live.data} ready={liveReady} filter={audienceFilter} onFilterChange={setAudienceFilter} onClose={()=>setAudience(false)}/>}
      {selection&&<ReportsPanelShell className="flow-workspace-panel is-inspector" title={node?.title||'Passagem observada'} closeLabel="Fechar detalhes" onClose={()=>setSelection(null)}><div className="flow-panel-scroll">{node&&<><small>{flowBlockFor(node).category}</small><p>{node.path?`${node.host||flow.allowed_host}${node.path}`:'Etapa visual · não medida'}</p></>}<strong className="flow-detail-number">{value(edge&&metric?.observation?metric.observation.sessions:metric?.sessions)}</strong><p>Sessões no período</p>{edge&&<><p>{document.nodes.find(n=>n.id===edge.from)?.title} → {document.nodes.find(n=>n.id===edge.to)?.title}</p><strong>{(metric?.observation||metric)?.rate==null?'Taxa não disponível':`${(metric?.observation||metric).rate}% de avanço`}</strong><p>{metric?.observation?.status==='no_data'?'Nenhum evento foi recebido neste período.':metric?.observation?.status==='unmeasured'?'Esta conexão não tem uma origem e um destino medidos.':metric?.observation?.status==='no_origin'?'A origem não teve sessões no período.':'Passagem direta entre os dois nós.'}</p><p>Base: {value(metric?.observation?.denominator??metrics?.nodes.find(n=>n.id===edge.from)?.sessions)} sessões na origem.</p></>}{node&&<p>{metric?.events==null?'Eventos não disponíveis':`${value(metric.events)} eventos`}</p>}<p>Publicação v{journey.data?.revision||flow.published_revision} · {periodLabel} · {journey.data?.timezone||'America/Sao_Paulo'} · {collection?.source||'Super Tag deste fluxo'}</p><p>Movimento verde: passagem observada nos últimos 90 segundos. Pulso azul: nova passagem observada. Nenhuma bolinha representa uma pessoa.</p></div></ReportsPanelShell>}
      <footer className="flow-monitor-legend"><ReportsNativeSelect aria-label="Camada" value={layer} onChange={e=>setLayer(e.target.value)}><option value="volume">Volume e taxa</option><option value="presence">Presença agora</option></ReportsNativeSelect><ReportsNativeSelect aria-label="Publicação" value={revision} onChange={e=>setRevision(e.target.value)}><option value="">Publicação atual</option>{versions.map(v=><option key={v.revision} value={v.revision}>Publicação v{v.revision}</option>)}</ReportsNativeSelect><span>{notice||'Azul: Conexão do fluxo · cinza tracejado: planejada · laranja tracejado: Retorno'}</span><a href={`/connect/app/supertag?client_id=${encodeURIComponent(client.client_id)}`}>Estado da Super Tag</a></footer>
    </div></div>
  </section>;
}
