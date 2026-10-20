import {flowGoal,goalById,isEngagementFlow} from './flowGoals.js';
import {stageFor,stageX,funnelEdges,isReturnEdge,FLOW_GRID,alignToGrid} from './flowStages.js';
import {applyDrag,edgePorts} from './flowDrag.js';
import {FlowEdgeLegend,edgeLegendKind} from './FlowEdgeLegend.jsx';
import {edgeMetricLabel} from './flowMetricLabels.js';
import {flowRoleLabel,flowRoleSourceLabel,flowStageLabel} from './flowUiLabels.js';
import {useFlowPreviews} from './useFlowPreviews.js';
import {RefreshCw01, Copy01, Trash01, LayoutGrid01, LayersTwo01, Route, Plus} from '@untitledui/icons';
import React, {useEffect, useCallback, useMemo, useRef, useState} from 'react';
import {ReactFlow, useReactFlow, useStore, useUpdateNodeInternals, Background, BackgroundVariant, BaseEdge, EdgeLabelRenderer, Handle, MarkerType, MiniMap, Controls, ControlButton, NodeToolbar, NodeResizer, useViewport, Position, ReactFlowProvider, getBezierPath, getSmoothStepPath} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import {flowBlockFor} from './flowBlockRegistry.js';
import {NODE_STATUS_LABELS,hasRealPath,isPlanned,nodeStatus} from './flowLifecycle.js';
import {FLOW_PLATFORMS, FlowPlatformLogo} from './FlowPlatformLogo.jsx';
import './flow-canvas.css';
import {fitToVisibleArea} from './flowViewport.js';
import {isSearchSource, searchEnginesOf} from './flowValidation.js';
import {searchEngineLabel} from './flowSourceIdentity.js';
import {FlowEdgeActivity} from './FlowEdgeActivity.jsx';
import {ungroupNodes,syncGroups} from './flowGroups.js';
import {ReportsActionButton} from './ReportsActionButton.jsx';
import {UsageScore} from './FlowPagesTab.jsx';


function nodeMetric(journey,node){
  const metric=journey?.nodes?.find(item=>item.id===node.id);
  if(!metric||metric.sessions==null)return metric;
  if(metric.exits!=null)return metric;
  const outgoing=(journey.edges||[]).filter(edge=>edge.from===node.id&&edge.sessions!=null);
  const exits=outgoing.length||node.type==='conversion'?Math.max(0,metric.sessions-outgoing.reduce((sum,edge)=>sum+Number(edge.sessions||0),0)):null;
  return {...metric,exits,exitsEstimated:exits!=null};
}

// Who is on a page right now, from the live feed; zero stays hidden so quiet pages do not shout.
function livePresence(metric,live,id){const n=live?.node_presence?.[id];return metric&&n>0?{...metric,presence:n}:metric;}

function JourneySummary({config,journey}) {
  if(journey?.status!=='ready'||!journey.nodes?.length)return null;
  const rows=config.nodes.map(node=>({node,metric:nodeMetric(journey,node)})).filter(row=>row.metric?.sessions!=null);
  // The server's outcome counts each session once (a session on two conversion nodes is one conversion); the sums
  // over nodes remain only for older responses.
  const outcome=journey.outcome;
  const arrived=outcome?outcome.sessions:rows.filter(row=>row.node.type==='source').reduce((sum,row)=>sum+row.metric.sessions,0);
  const converted=outcome?outcome.converted:rows.filter(row=>row.node.type==='conversion').reduce((sum,row)=>sum+row.metric.sessions,0);
  const exits=rows.filter(row=>!['source','conversion'].includes(row.node.type));
  const left=outcome?Math.max(0,outcome.sessions-outcome.converted):exits.reduce((sum,row)=>sum+(row.metric.exits||0),0);
  const top=exits.slice().sort((a,b)=>(b.metric.exits||0)-(a.metric.exits||0))[0];
  if(!arrived&&!converted)return null;
  if(isEngagementFlow(config)){
    const engagement=journey.engagement||{};const goal=flowGoal(config);
    const pages=engagement.pages_per_session!=null&&<span key="pages"><b>{engagement.pages_per_session.toLocaleString('pt-BR',{maximumFractionDigits:1})}</b> páginas por visita</span>;
    const time=engagement.avg_active_ms!=null&&<span key="time"><b>{duration(engagement.avg_active_ms)}</b> ativos por página</span>;
    const reached=<span key="arrived"><b>{number(arrived)}</b> chegaram</span>;
    const sources=rows.filter(row=>row.node.type==='source').sort((a,b)=>b.metric.sessions-a.metric.sessions);
    const topSource=sources[0]&&sources[0].metric.sessions>0&&<span key="source">Maior origem: <b>{sources[0].node.title}</b> ({number(sources[0].metric.sessions)})</span>;
    const leaving=<span key="left"><b>{number(left)}</b> saíram</span>;
    const topExit=top&&top.metric.exits>0&&<span key="exit">Maior saída: <b>{top.node.title}</b> ({number(top.metric.exits)})</span>;
    const order={time:[time,reached,pages,leaving],reach:[reached,topSource,pages,leaving],navigation:[reached,pages,leaving,topExit]}[goal]||[reached,pages,time,leaving,topExit];
    return <div className="flow-journey-summary" role="status" aria-label={`Objetivo: ${goalById(goal).label}`}>{order.filter(Boolean)}</div>;
  }
  const rate=outcome?outcome.rate:arrived?Math.round(converted/arrived*100):null;
  return <div className="flow-journey-summary" role="status"><span><b>{number(arrived)}</b> chegaram</span><span><b>{number(converted)}</b> converteram{rate!=null&&` · ${rate}%`}</span><span><b>{number(left)}</b> saíram sem converter</span>{top&&top.metric.exits>0&&<span>Maior saída: <b>{top.node.title}</b> ({number(top.metric.exits)})</span>}</div>;
}

// A busy map opens zoomed out, so the whole journey reads at a glance instead of filling the screen with a few cards.
function monitorZoom(count){return count>=10?.6:count>=7?.75:.9;}
function FitLoadedGraph({enabled,fitKey='',monitor=false}) {
  // Fit once every visible node has real dimensions; React Flow's own fitView can run before cards are measured
  // and does not know which part of the canvas the side panels cover. Until the user pans or zooms, the map is
  // re-centered when late data or page captures change its size in the first seconds after opening.
  const api=useReactFlow();
  const fitted=useRef(null);
  const touched=useRef(false);
  const fittedAt=useRef(0);
  const footprint=useStore(state=>{let size=0,count=0;state.nodeLookup.forEach(node=>{if(node.hidden)return;count+=1;size+=Math.round((node.measured?.width||0)+(node.measured?.height||0));});return `${count}:${size}`;});
  const fit=useCallback(visible=>{
    if(monitor)api.fitView({padding:.22,maxZoom:monitorZoom(visible.length)});
    else if(!fitToVisibleArea(api,{nodes:visible}))api.fitView({padding:.12,maxZoom:1.5});
  },[api,monitor]);
  useEffect(()=>{
    const canvas=document.querySelector('.reports-flow-canvas');
    const mark=()=>{touched.current=true;};
    canvas?.addEventListener('wheel',mark,{passive:true});canvas?.addEventListener('pointerdown',mark);
    return()=>{canvas?.removeEventListener('wheel',mark);canvas?.removeEventListener('pointerdown',mark);};
  },[]);
  useEffect(()=>{touched.current=false;},[fitKey]);
  useEffect(()=>{
    if(!enabled)return undefined;
    if(fitted.current===fitKey&&(touched.current||Date.now()-fittedAt.current>5000))return undefined;
    let attempts=0;
    const timer=setInterval(()=>{
      const visible=api.getNodes().filter(node=>!node.hidden);
      const ready=visible.length&&visible.every(node=>api.getInternalNode(node.id)?.measured?.width);
      if(ready||(visible.length&&++attempts>40)){clearInterval(timer);fit(visible);if(fitted.current!==fitKey)fittedAt.current=Date.now();fitted.current=fitKey;}
      else if(!visible.length&&++attempts>300)clearInterval(timer);
    },fitted.current===fitKey?200:50);
    return()=>clearInterval(timer);
  },[enabled,api,fitKey,fit,footprint]);
  return null;
}

function NodeLabel({node, selected, readOnly, onChange}) {
  const [editing,setEditing]=useState(false);
  const [draft,setDraft]=useState(node.title||'');
  const inputRef=useRef(null);
  const begin=()=>{if(readOnly)return;setDraft(node.title||'');setEditing(true);requestAnimationFrame(()=>inputRef.current?.select());};
  const finish=save=>{if(save)onChange(node.id,(draft.trim()||node.title||node.type).slice(0,60));setEditing(false);};
  return <div className="flow-shape-label" onDoubleClick={begin} onKeyDown={event=>{if(!editing&&(event.key==='Enter'||event.key==='F2')){event.preventDefault();begin();}}}>
    {editing?<input ref={inputRef} className="nodrag" aria-label="Editar nome do nó" value={draft} onChange={event=>setDraft(event.target.value)} onBlur={()=>finish(true)} onKeyDown={event=>{if(event.key==='Enter'){event.preventDefault();finish(true);}if(event.key==='Escape'){event.stopPropagation();finish(false);}}}/> : <span tabIndex={selected&&!readOnly?0:-1} aria-label={`${node.title||node.type}. Pressione Enter para renomear`}>{node.title||node.type}</span>}
  </div>;
}

function NodeHandles() {
  return <>
    <Handle id="left-in" type="target" position={Position.Left}/>
    <Handle id="right-out" type="source" position={Position.Right}/>
    <Handle className="is-aux" id="right-in" type="target" position={Position.Right}/>
    <Handle className="is-aux" id="left-out" type="source" position={Position.Left}/>
    <Handle className="is-aux" id="top-in" type="target" position={Position.Top}/>
    <Handle className="is-aux" id="bottom-out" type="source" position={Position.Bottom}/>
    <Handle className="is-aux" id="bottom-in" type="target" position={Position.Bottom}/>
  </>;
}

const KIND_LABELS={source:'Origem do tráfego',page:'Página',form:'Formulário',event:'Evento na página',conversion:'Conversão',whatsapp:'WhatsApp',error:'Erro',segment:'Segmento',condition:'Condição',delay:'Espera',webhook:'Webhook'};
const number=value=>Number(value).toLocaleString('pt-BR');
const duration=ms=>{const seconds=Math.round(Number(ms)/1000);return seconds<60?`${seconds}s`:`${Math.floor(seconds/60)}min ${String(seconds%60).padStart(2,'0')}s`;};

const PAID_UTM={google:'google',youtube:'youtube',meta:'facebook',facebook:'facebook',instagram:'instagram',tiktok:'tiktok',linkedin:'linkedin',dv360:'dv360',email:'email',sms:'sms'};

const forecastNumber=value=>Math.round(value).toLocaleString('pt-BR');
const forecastEdgeLabel=item=>item.rate==null?'Sem taxa':`${item.rate.toLocaleString('pt-BR',{maximumFractionDigits:1})}% · ~${forecastNumber(item.sessions)}`;

function NodeMetrics({node,metric,arrived}) {
  if(!metric)return null;
  if(metric.sessions==null)return <div className="fnode__metrics"><small>{node.type==='source'?'Sem vínculo com a medição':'Sem medição neste período'}</small></div>;
  const exits=metric.exits;
  const share=metric.sessions>0&&exits!=null?Math.round(exits/metric.sessions*100):null;
  const rate=arrived>0&&['form','conversion'].includes(node.type)?Math.round(metric.sessions/arrived*1000)/10:null;
  return <div className="fnode__metrics"><b>{number(metric.sessions)}</b><span>sessões</span>{rate!=null&&<strong className="fnode__rate" title="Sessões nesta etapa sobre o total que chegou ao fluxo">{rate.toLocaleString('pt-BR')}% do tráfego</strong>}{metric.presence!=null&&<em>{metric.presence} agora</em>}{metric.avg_active_ms!=null&&['page','form','error'].includes(node.type)&&<small className="fnode__time" title="Tempo ativo médio na página">{duration(metric.avg_active_ms)} na página</small>}
    {share!=null&&!['conversion','source'].includes(node.type)&&<div className="fnode__exit" title={`${number(exits)} sessões terminaram a visita nesta etapa${metric.exitsEstimated?' (estimado pelas conexões desenhadas)':''}`}><i style={{width:`${Math.min(100,share)}%`}}/><small>{exits>0?`${number(exits)} saíram aqui · ${share}%${metric.exitsEstimated?' (est.)':''}`:'Ninguém saiu aqui'}</small></div>}</div>;
}

function ShapeNode({id,data,selected}) {
  const updateInternals=useUpdateNodeInternals();
  useEffect(()=>{updateInternals(id);},[id,data.node.title,data.metric?.sessions,updateInternals]);
  const {node,readOnly,onLabelChange,metric,onDuplicate,onRemove,preview,onRegenerate,canCapture}=data;
  const {zoom}=useViewport();
  const [brokenImage,setBrokenImage]=useState(null);
  const [brokenIcon,setBrokenIcon]=useState(false);
  const [hovered,setHovered]=useState(false);
  const block=flowBlockFor(node);
  const Icon=block.icon;
  const isPage=['page','form','error'].includes(node.type)||block.shape==='page';
  const capture=isPage&&zoom>=.4&&preview?.url&&brokenImage!==preview.url;
  const platform=node.type==='source'&&FLOW_PLATFORMS[block.source||node.source];
  const siteHost=(node.host||data.faviconHost||'').replace(/^https?:\/\//,'');
  const favicon=isPage&&siteHost?`https://www.google.com/s2/favicons?domain=${encodeURIComponent(siteHost)}&sz=32`:'';
  const path=hasRealPath(node)?node.path:'';
  const planned=isPlanned(node);
  return <div onMouseEnter={()=>setHovered(true)} onMouseLeave={()=>setHovered(false)} className={`fnode is-tone-${block.tone} is-type-${node.type}${planned?' is-planned':''}${zoom<.55?' is-compact':''}${selected?' is-selected':''}${data.dimmed?' is-dimmed':''}`}>
    <NodeHandles/>
    {zoom>=.55&&<div className="fnode__badge" aria-hidden="true">{data.step!=null&&<b>{data.step}</b>}<span>{flowStageLabel(node)}</span></div>}
    {data.onAppend&&<button type="button" className="fnode__append nodrag nopan" aria-label={`Adicionar etapa depois de ${node.title||'este nó'}`} title="Adicionar a próxima etapa, já conectada" onClick={event=>{event.stopPropagation();data.onAppend(node.id,event.currentTarget.getBoundingClientRect());}}><Plus size={14}/></button>}
    <NodeToolbar className="flow-node-hover" isVisible={hovered&&!selected&&zoom>=.55} position={Position.Bottom}><strong>{node.title}</strong>{path&&<small>{node.host}{path}</small>}<small>Etapa: {flowStageLabel(node)} · Função: {flowRoleLabel(node.role)} · {flowRoleSourceLabel(node.role_source)}</small>{node.evidence&&<p>{node.evidence}</p>}{data.paths?.map(item=><small key={item.id}>{item.label} · {number(item.sessions)} sessões</small>)}</NodeToolbar>
    <NodeToolbar isVisible={selected&&!readOnly} position={Position.Top}><ReportsActionButton aria-label="Duplicar nó" onClick={()=>onDuplicate(node.id)}><Copy01 size={16}/></ReportsActionButton><ReportsActionButton aria-label="Remover do fluxo" onClick={()=>onRemove(node.id)}><Trash01 size={16}/></ReportsActionButton>{isPage&&canCapture&&<ReportsActionButton aria-label={preview?.status==='ready'?'Atualizar captura':'Solicitar captura'} onClick={()=>onRegenerate(node.id)}><RefreshCw01 size={16}/></ReportsActionButton>}</NodeToolbar>
    {isPage&&!capture&&<div className="fnode__capture is-placeholder" aria-hidden="true"><i/><i/><i/><b/></div>}
    {capture&&<img className="fnode__capture" src={preview.canvas_url||preview.url} alt="" loading="lazy" decoding="async" onLoad={()=>updateInternals(id)} onError={()=>setBrokenImage(preview.url)}/>}
    <div className="fnode__head"><span className="fnode__icon">{platform?<FlowPlatformLogo platform={block.source||node.source}/>:favicon&&!brokenIcon?<img className="fnode__favicon" src={favicon} alt="" width="16" height="16" loading="lazy" onError={()=>setBrokenIcon(true)}/>:<Icon size={16}/>}</span><span className="fnode__kind">{KIND_LABELS[node.type]||'Etapa'}</span>{data.usage&&!metric&&(data.usage.score!=null||data.usage.status==='idle')&&<span className="fnode__usage"><UsageScore row={data.usage} compact/></span>}{planned&&<span className="fnode__status">{NODE_STATUS_LABELS[nodeStatus(node)]}</span>}{block.trackable&&!planned&&!path&&node.type!=='event'&&node.type!=='conversion'&&<span className="fnode__warn" title="Configure a URL real deste nó" aria-label="Configure a URL real deste nó">!</span>}</div>
    <NodeLabel node={node} selected={selected} readOnly={readOnly} onChange={onLabelChange}/>
    {path?<small className="fnode__path">{data.externalHost?`${data.externalHost}${path==='/'?'':path}`:path}</small>:planned&&node.spec?.suggested_path&&<small className="fnode__path is-suggested">{node.spec.suggested_path}</small>}
    {node.type==='source'&&node.segment?.name&&<small className="fnode__segment">{node.segment.name}</small>}
    {node.type==='source'&&!node.synthetic&&!isSearchSource(node)&&(node.media?.utm?.source||PAID_UTM[block.source||node.source])&&<small className="fnode__path" title="Como as visitas desta origem são reconhecidas">utm_source={node.media?.utm?.source||PAID_UTM[block.source||node.source]}{node.media?.utm?.campaign&&` · utm_campaign=${node.media.utm.campaign}`}</small>}
    {isSearchSource(node)&&(!node.synthetic||metric?.search_engines?.length)&&<span className="fnode__engines">{metric?.search_engines?.length?metric.search_engines.map(item=><em key={item.engine}>{item.label} <b>{Number(item.sessions).toLocaleString('pt-BR')}</b></em>):searchEnginesOf(node).map(engine=><em key={engine}>{engine==='*'?'Todos os buscadores':searchEngineLabel(engine)}</em>)}</span>}
    <NodeMetrics node={node} metric={metric} arrived={data.arrived}/>
    {data.forecastSessions!=null&&!metric&&<div className="fnode__forecast" title="Pessoas previstas neste passo no cenário escolhido"><b>~{forecastNumber(data.forecastSessions)}</b><span>{node.type==='conversion'?'conversões previstas':node.type==='source'?'visitas previstas':'pessoas previstas'}</span></div>}
  </div>;
}

function GroupNode({id,data,selected}) {
  const update=useUpdateNodeInternals();
  useEffect(()=>{update(id);},[id,data.collapsed,update]);
  if(data.collapsed)return <div className="flow-group-stack" onDoubleClick={data.toggle}><strong>{data.group.name}</strong><small>{data.group.memberIds.length} páginas</small>{data.metric&&<small>{Number(data.metric.sessions).toLocaleString('pt-BR')} sessões únicas</small>}<NodeHandles/><button className="nodrag" onClick={data.toggle}>Ver páginas</button>{!data.readOnly&&<button className="nodrag" onClick={()=>data.ungroup(id)}>Separar páginas</button>}</div>;
  return <div className="flow-group-node"><NodeResizer isVisible={selected&&!data.readOnly} minWidth={220} minHeight={180} onResizeEnd={(_,size)=>data.resize(id,size)}/><strong>{data.group.name}</strong><small>{data.group.memberIds.length} nós</small><button className="nodrag" onClick={data.toggle}>Recolher</button><NodeToolbar isVisible={selected&&!data.readOnly}><ReportsActionButton onClick={()=>data.ungroup(id)}>Desagrupar</ReportsActionButton></NodeToolbar></div>;
}

function ExitSinkNode({data}) {
  const title=data.engagement?'Saiu do site':'Saiu sem converter';
  return <div className="fnode is-type-exit"><Handle id="top-in" type="target" position={Position.Top}/><Handle id="left-in" type="target" position={Position.Left}/><div className="fnode__head"><span className="fnode__icon">↘</span><span className="fnode__kind">Fim da visita</span></div><div className="flow-shape-label"><span>{title}</span></div>{data.total==null?<small className="fnode__note">Quem não chega ao fim sai por aqui. Os números aparecem com dados publicados.</small>:<div className="fnode__metrics"><b>{number(data.total)}</b><span>sessões</span></div>}</div>;
}

const MemoShapeNode=React.memo(ShapeNode);
function NoteNode({id,data,selected}) {
  const updateInternals=useUpdateNodeInternals();
  const {node,readOnly,onLabelChange,onDuplicate,onRemove}=data;
  const checklist=node.checklist||[];
  useEffect(()=>{updateInternals(id);},[id,node.title,node.description,checklist.length,updateInternals]);
  const done=checklist.filter(item=>item.done).length;
  return <div className={`fnote${selected?' is-selected':''}`}>
    <NodeHandles/>
    <NodeToolbar isVisible={selected&&!readOnly} position={Position.Top}><ReportsActionButton aria-label="Duplicar nota" onClick={()=>onDuplicate(node.id)}><Copy01 size={16}/></ReportsActionButton><ReportsActionButton aria-label="Remover nota" onClick={()=>onRemove(node.id)}><Trash01 size={16}/></ReportsActionButton></NodeToolbar>
    <div className="fnote__head"><span>Nota</span>{checklist.length>0&&<small>{done}/{checklist.length}</small>}</div>
    <NodeLabel node={node} selected={selected} readOnly={readOnly} onChange={onLabelChange}/>
    {node.description&&<p className="fnote__text">{node.description}</p>}
    {checklist.length>0&&<ul className="fnote__checklist">{checklist.slice(0,6).map((item,index)=><li key={index} className={item.done?'is-done':''}><span aria-hidden="true">{item.done?'☑':'☐'}</span>{item.text}</li>)}{checklist.length>6&&<li className="fnote__more">+{checklist.length-6} itens</li>}</ul>}
  </div>;
}

const QUICK_ADD_TYPES=[{type:'page',label:'Página'},{type:'form',label:'Formulário'},{type:'event',label:'Evento na página'},{type:'whatsapp',label:'WhatsApp'},{type:'conversion',label:'Conversão'}];

// Current zoom as a percentage; a click returns to 100% around the centre of the view.
function ZoomReadout(){
  const {zoom}=useViewport();const api=useReactFlow();
  return <ControlButton className="flow-zoom-readout" aria-label={`Zoom ${Math.round(zoom*100)}%. Voltar para 100%`} title="Voltar para 100%" onClick={()=>api.zoomTo(1,{duration:180})}>{Math.round(zoom*100)}%</ControlButton>;
}

const nodeTypes = {exitSink:ExitSinkNode,groupFrame:GroupNode,visual:MemoShapeNode,circle:MemoShapeNode,diamond:MemoShapeNode,page:MemoShapeNode,note:React.memo(NoteNode)};

// Several connections leaving (or reaching) the same side fan out instead of sharing one point.
const sideShift=(position,offset)=>position===Position.Left||position===Position.Right?[0,offset]:[offset,0];
function FlowEdge({id,sourceX,sourceY,targetX,targetY,sourcePosition,targetPosition,markerEnd,markerStart,style,data={},label,selected}) {
  const [hovered,setHovered]=useState(false);
  const [sdx,sdy]=sideShift(sourcePosition,data.sourceOffset||0),[tdx,tdy]=sideShift(targetPosition,data.targetOffset||0);
  const args={sourceX:sourceX+sdx,sourceY:sourceY+sdy,targetX:targetX+tdx,targetY:targetY+tdy,sourcePosition,targetPosition};
  const [path,labelX,labelY]=data.routing==='orthogonal'?getSmoothStepPath({...args,borderRadius:14,offset:28}):getBezierPath({...args,curvature:.35});
  return <><BaseEdge id={id} path={path} markerEnd={markerEnd} markerStart={markerStart} style={style}/><FlowEdgeActivity path={path} flow={data.flowIntensity} operational={data.operational} transitionId={data.transitionId} ready={data.liveReady} scope={data.liveScope}/><path d={path} fill="none" stroke="transparent" strokeWidth="20" onMouseEnter={()=>setHovered(true)} onMouseLeave={()=>setHovered(false)}/>{(label||!data.readOnly)&&<EdgeLabelRenderer><div className={`flow-edge-actions nodrag nopan${hovered||selected||data.hasMetric?' is-visible':''}${data.forecast?' is-forecast':''}${data.muted?' is-muted':''}`} style={{transform:`translate(-50%, -50%) translate(${labelX}px, ${labelY+(data.labelOffset||0)}px)`}} onMouseEnter={()=>setHovered(true)} onMouseLeave={()=>setHovered(false)}>{label&&<span onClick={()=>data.onInspect?.(id)}>{label}</span>}{!data.readOnly&&<><button type="button" aria-label="Inserir etapa nesta conexão" title="Inserir etapa nesta conexão" onClick={event=>data.onInsert(id,event.currentTarget.getBoundingClientRect())}>+</button><button type="button" aria-label="Remover conexão" title="Remover conexão" onClick={()=>data.onRemove(id)}>×</button></>}</div></EdgeLabelRenderer>}</>;
}

const edgeTypes={flow:FlowEdge};

function FlowCanvasInner({onNavigationModeChange,ghostEdges=[],ghostNodes=[],config,setConfig,selectedNodeId,setSelectedNodeId,onSelectedIdsChange=()=>{},onAddNode,onInsertEdge,onDuplicateSelection,readOnly,simulatedPath=[],journey=null,snapToGrid,onReady=()=>{},onZoomChange=()=>{},onSelectedEdge,onOrganize,live=null,liveScope='',operational=false,siteHost='',fitOnMount=false,fitKey='',fitMonitor=false,onGestureStart=()=>{},onGestureEnd=()=>{},previewContext,inspectorOpen=false,forecast=null,allowArrange=false,usage=null} ) {
  const previews=useFlowPreviews(previewContext);
  const [fullNavigation,setFullNavigation]=useState(false);
  useEffect(()=>{onNavigationModeChange?.(fullNavigation);},[fullNavigation,onNavigationModeChange]);
  const [showReturns,setShowReturns]=useState(false);
  const [showExits,setShowExits]=useState(null);
  const [dragPositions,setDragPositions]=useState({});
  const pendingPositions=useRef(new Map());
  const [altPressed,setAltPressed]=useState(false);
  useEffect(()=>{const down=e=>setAltPressed(e.altKey),up=()=>setAltPressed(false);window.addEventListener('keydown',down);window.addEventListener('keyup',down);window.addEventListener('blur',up);return()=>{window.removeEventListener('keydown',down);window.removeEventListener('keyup',down);window.removeEventListener('blur',up);};},[]);
  const [instance,setInstance]=useState(null);
  const [measurements,setMeasurements]=useState({});
  const [selectedIds,setSelectedIds]=useState([]);
  const selectionRef=useRef('');
  const [expandedGroups,setExpandedGroups]=useState(new Set());
  const [showMiniMap,setShowMiniMap]=useState(true);
  const [quickAdd,setQuickAdd]=useState(null);
  const [contextMenu,setContextMenu]=useState(null);
  // Arranging the cards is allowed while reading (monitor) when the screen owns the positions, never the publication.
  const canMove=(!readOnly||allowArrange)&&!fullNavigation;
  const [routing,setRouting]=useState(()=>{try{return localStorage.getItem('reports-flow-routing')==='orthogonal'?'orthogonal':'curved';}catch(_){return 'curved';}});
  const toggleRouting=()=>setRouting(current=>{const next=current==='orthogonal'?'curved':'orthogonal';try{localStorage.setItem('reports-flow-routing',next);}catch(_){/* the choice just isn't remembered */}return next;});
  const [legendFocus,setLegendFocus]=useState('');
  const insertOnEdgeAt=useCallback((id,rect)=>setQuickAdd({edgeId:id,screen:{x:rect.left,y:rect.bottom+6}}),[]);
  const appendAfter=useCallback((id,rect)=>setQuickAdd({source:id,append:true,screen:{x:rect.right+8,y:rect.top}}),[]);
  // Reading order: steps are numbered from the entry points along the drawn connections, like a recipe.
  const stepNumbers=useMemo(()=>{
    const nodes=(config.nodes||[]).filter(node=>node.type!=='note'),ids=new Set(nodes.map(node=>node.id));
    const out=new Map(),incoming=new Map(nodes.map(node=>[node.id,0]));
    (config.edges||[]).forEach(edge=>{if(!ids.has(edge.from)||!ids.has(edge.to)||edge.from===edge.to)return;out.set(edge.from,[...(out.get(edge.from)||[]),edge.to]);incoming.set(edge.to,(incoming.get(edge.to)||0)+1);});
    const byPlace=(a,b)=>(Number(a.x)||0)-(Number(b.x)||0)||(Number(a.y)||0)-(Number(b.y)||0);
    const byId=new Map(nodes.map(node=>[node.id,node]));
    const queue=nodes.filter(node=>!incoming.get(node.id)).sort(byPlace).map(node=>node.id);
    const numbers=new Map();let next=1;
    while(queue.length||numbers.size<nodes.length){
      if(!queue.length){const rest=nodes.filter(node=>!numbers.has(node.id)).sort(byPlace);if(!rest.length)break;queue.push(rest[0].id);}
      const id=queue.shift();if(numbers.has(id))continue;numbers.set(id,next++);
      (out.get(id)||[]).map(target=>byId.get(target)).filter(Boolean).sort(byPlace).forEach(target=>{if(!numbers.has(target.id))queue.push(target.id);});
    }
    return numbers;
  },[config.nodes,config.edges]);
  const applySelection=useCallback(ids=>{selectionRef.current=ids.join('|');setSelectedIds(ids);onSelectedIdsChange(ids);},[onSelectedIdsChange]);
  useEffect(()=>{if(selectionRef.current&&!selectionRef.current.split('|').includes(selectedNodeId))applySelection(selectedNodeId?[selectedNodeId]:[]);},[selectedNodeId,applySelection]);
  useEffect(()=>{
    if(readOnly||fullNavigation)return undefined;
    const selectAll=event=>{
      if(!(event.metaKey||event.ctrlKey)||event.key.toLowerCase()!=='a'||event.target.closest?.('input,textarea,select,[contenteditable="true"]'))return;
      event.preventDefault();
      const groups=config.groups||[];
      const collapsed=new Set(groups.filter(g=>!expandedGroups.has(g.id)).map(g=>g.id));
      // Members of a frame travel with it; selecting them too would move them twice.
      applySelection([...groups.map(g=>g.id),...(config.nodes||[]).filter(n=>!n.locked&&!n.groupId&&!collapsed.has(n.groupId)).map(n=>n.id)]);
    };
    window.addEventListener('keydown',selectAll);
    return()=>window.removeEventListener('keydown',selectAll);
  },[config.nodes,config.groups,expandedGroups,readOnly,fullNavigation,applySelection]);
  const onLabelChange=useCallback((id,title)=>setConfig(current=>({...current,nodes:current.nodes.map(node=>node.id===id?{...node,title,manuallyEdited:true}:node)})),[setConfig]);
  // Every journey ends in one of two ways: it converts or it leaves. Conversion flows show both by default;
  // institutional flows show where visits end. Without data the end is drawn as part of the plan.
  const conversionFlow=!isEngagementFlow(config)&&(config.nodes||[]).some(node=>node.type==='conversion');
  const exitsVisible=showExits??conversionFlow;
  const exitOverlay=useMemo(()=>{
    if(!exitsVisible||!(config.nodes||[]).length)return null;
    const engagement=isEngagementFlow(config);
    const candidates=(config.nodes||[]).filter(node=>!node.groupId&&!['source','conversion'].includes(node.type));
    let rows;
    if(journey?.status==='ready'){
      rows=candidates.map(node=>({node,metric:nodeMetric(journey,node)})).filter(row=>row.metric?.exits>0&&row.metric.sessions>0&&row.metric.exits/row.metric.sessions>=.2);
    }else{
      const conversions=new Set(config.nodes.filter(node=>node.type==='conversion').map(node=>node.id));
      const beforeGoal=new Set(config.edges.filter(edge=>conversions.has(edge.to)).map(edge=>edge.from));
      rows=candidates.filter(node=>beforeGoal.has(node.id)).map(node=>({node,metric:null}));
    }
    if(!rows.length)return null;
    const measured=rows.every(row=>row.metric);
    const total=measured?rows.reduce((sum,row)=>sum+row.metric.exits,0):null,max=measured?Math.max(...rows.map(row=>row.metric.exits)):1;
    // Conversion flows place the exit beside the goal: the outcome column reads converted / left.
    const goal=engagement?null:config.nodes.find(node=>node.type==='conversion'&&!node.groupId);
    const x=goal?Number(goal.x)||0:rows.reduce((sum,row)=>sum+(Number(row.node.x)||0),0)/rows.length;
    const y=goal?(Number(goal.y)||0)+220:Math.max(...(config.nodes||[]).map(node=>Number(node.y)||0))+300;
    return {node:{id:'__exit',type:'exitSink',position:{x,y},data:{total,engagement},draggable:false,selectable:false,connectable:false},
      edges:rows.map(row=>({id:`exit:${row.node.id}`,source:row.node.id,target:'__exit',sourceHandle:goal?'right-out':'bottom-out',targetHandle:goal?'left-in':'top-in',type:'flow',style:{stroke:'var(--color-fg-warning-primary)',strokeWidth:measured?1+4*Math.sqrt(row.metric.exits/max):1.5,strokeDasharray:'4 6',opacity:measured?.75:.5},data:{readOnly:true}}))};
  },[exitsVisible,journey,config.nodes,config.edges,config.site_kind,config.goal]);
  const journeyArrived=useMemo(()=>{if(!journey?.nodes)return 0;const byId=new Map((config.nodes||[]).map(node=>[node.id,node]));const fromSources=journey.nodes.filter(item=>byId.get(item.id)?.type==='source').reduce((sum,item)=>sum+Number(item.sessions||0),0);return fromSources||Number(journey.funnel?.entries||0);},[journey,config.nodes]);
  const nodes=useMemo(()=>{
    const groups=config.groups||[];
    const parents=groups.map(group=>({id:group.id,type:'groupFrame',position:{x:group.bounds.x,y:group.bounds.y},style:{width:expandedGroups.has(group.id)?group.bounds.width:180,height:expandedGroups.has(group.id)?group.bounds.height:130},data:{group,metric:journey?.group_nodes?.find(n=>n.id===group.id),collapsed:!expandedGroups.has(group.id),toggle:()=>setExpandedGroups(current=>{const next=new Set(current);next.has(group.id)?next.delete(group.id):next.add(group.id);return next;}),readOnly:readOnly||fullNavigation,ungroup:id=>setConfig(current=>ungroupNodes(current,id)),resize:(id,size)=>setConfig(current=>({...current,groups:current.groups.map(g=>g.id===id?{...g,bounds:{x:alignToGrid(size.x),y:alignToGrid(size.y),width:Math.max(FLOW_GRID*5,alignToGrid(size.width)),height:Math.max(FLOW_GRID*5,alignToGrid(size.height))}}:g)}))},draggable:canMove,selectable:true,selected:selectedIds.includes(group.id)}));
    const hostVotes={};(config.nodes||[]).forEach(node=>{if(node.host)hostVotes[node.host]=(hostVotes[node.host]||0)+1;});
    const primaryHost=Object.entries(hostVotes).sort((a,b)=>b[1]-a[1])[0]?.[0]||'';
    const hasOut=new Set((config.edges||[]).map(edge=>edge.from));
    const neighbours=selectedNodeId&&selectedIds.length<=1?new Set([selectedNodeId,...(config.edges||[]).flatMap(edge=>edge.from===selectedNodeId?[edge.to]:edge.to===selectedNodeId?[edge.from]:[])]):null;
    const items=(config.nodes||[]).map(node=>{
      const parent=groups.find(g=>g.id===node.groupId);
      const canAppend=!readOnly&&!fullNavigation&&!hasOut.has(node.id)&&!['note','conversion','error'].includes(node.type)&&!(parent&&!expandedGroups.has(parent.id));
      return {id:node.id,hidden:Boolean(parent&&!expandedGroups.has(parent.id)),measured:measurements[node.id],type:flowBlockFor(node).shape,parentId:parent?.id,extent:parent?'parent':undefined,
        className:simulatedPath.includes(node.id)?'is-simulated':'',position:{x:(Number.isFinite(Number(node.x))&&node.x!==''&&node.x!=null?Number(node.x):stageX(stageFor(node)))-(parent?.bounds.x||0),y:(Number(node.y)||0)-(parent?.bounds.y||0)},
        data:{node,usage:usage?.[node.id]||null,step:stepNumbers.get(node.id),dimmed:Boolean(neighbours&&!neighbours.has(node.id)),onAppend:canAppend?appendAfter:undefined,faviconHost:primaryHost||siteHost,externalHost:node.host&&node.host!==primaryHost?node.host:'',forecastSessions:forecast&&node.type!=='note'?forecast.nodes[node.id]??null:null,paths:journey?.edges?.filter(e=>(e.from===node.id||e.to===node.id)&&e.sessions>0).sort((a,b)=>b.sessions-a.sessions).slice(0,3).map(e=>({id:e.id,sessions:e.sessions,label:`${e.to===node.id?'De':'Para'} ${config.nodes.find(n=>n.id===(e.to===node.id?e.from:e.to))?.title||'nó'}`})),preview:{...previews.items[node.id],message:previews.error||previews.items[node.id]?.message,unavailable:!previews.available},onRegenerate:previews.regenerate,canCapture:previewContext?.canCapture&&previews.available,readOnly:readOnly||fullNavigation,onLabelChange,onDuplicate:onDuplicateSelection,onRemove:id=>setConfig(current=>syncGroups({...current,nodes:current.nodes.filter(n=>n.id!==id),edges:current.edges.filter(e=>e.from!==id&&e.to!==id)})),metric:livePresence(nodeMetric(journey,node),live,node.id),arrived:journeyArrived},draggable:canMove&&!node.locked,selectable:true,selected:selectedIds.length?selectedIds.includes(node.id):node.id===selectedNodeId};
    });return [...parents,...items,...ghostNodes.map(node=>({id:`ghost:${node.id}`,type:flowBlockFor(node).shape,position:{x:node.x,y:node.y},className:"flow-ghost-node",data:{node,readOnly:true},draggable:false,selectable:false}))];
  },[usage,stepNumbers,appendAfter,canMove,config,ghostNodes,expandedGroups,readOnly,onLabelChange,selectedNodeId,selectedIds,simulatedPath,journey,onDuplicateSelection,setConfig,live,siteHost,measurements,fullNavigation,previews.items,previews.regenerate,previews.available,previews.error,previewContext?.canCapture,journeyArrived]);
  const removeEdge=useCallback(id=>setConfig(current=>({...current,edges:current.edges.filter(edge=>edge.id!==id)})),[setConfig]);
  const edges=useMemo(()=>{
    const memberGroup=new Map((config.groups||[]).filter(g=>!expandedGroups.has(g.id)).flatMap(g=>g.memberIds.map(id=>[id,g.id])));
    const renderedPairs=new Set();
    const maxEdgeSessions=Math.max(1,...(journey?.edges||[]).map(item=>Number(item.sessions||0)));
    const projected={...config,nodes:[...config.nodes,...(config.groups||[]).map(g=>({id:g.id,stage:stageFor(config.nodes.find(n=>g.memberIds.includes(n.id))||{})}))],edges:config.edges.map(e=>({...e,from:memberGroup.get(e.from)||e.from,to:memberGroup.get(e.to)||e.to})).filter(e=>{const key=`${e.from}:${e.to}`;if(e.from===e.to||renderedPairs.has(key))return false;renderedPairs.add(key);return true;})};
    const stageNodes=new Map(projected.nodes.map(node=>[node.id,node]));
    const originals=new Map((config.edges||[]).map(e=>[e.id,e]));
    // Where each end really sits on the board (a collapsed frame stands in for its members) decides the sides.
    const placed=new Map((config.nodes||[]).map(n=>{const live=dragPositions[n.id];const parent=(config.groups||[]).find(g=>g.id===n.groupId);return [n.id,live?{...n,x:live.x+(parent?.bounds.x||0),y:live.y+(parent?.bounds.y||0)}:n];}));
    (config.groups||[]).forEach(g=>{if(!expandedGroups.has(g.id))placed.set(g.id,{x:g.bounds.x,y:g.bounds.y,width:180,height:130});});
    const authored=funnelEdges(projected,{full:fullNavigation,returns:showReturns}).map(edge=>{
      const original=originals.get(edge.id);
      const aggregate=memberGroup.has(original?.from)||memberGroup.has(original?.to);
      const returning=isReturnEdge(edge,stageNodes);
      const related=!selectedNodeId||edge.from===selectedNodeId||edge.to===selectedNodeId;
      const planned=edge.variant==='planned'||edge.kind==='site_link';
      const simulated=simulatedPath.some((id,index)=>id===edge.from&&simulatedPath[index+1]===edge.to);
      const metric=aggregate?(expandedGroups.size?null:journey?.group_edges?.find(item=>item.from===edge.from&&item.to===edge.to)):journey?.edges?.find(item=>item.id===edge.id);
      const measured=Boolean(metric&&Number(metric.sessions)>0);
      const legend=edgeLegendKind({simulated,returning,planned,measured,monitoring:Boolean(journey?.edges?.length)});
      const muted=Boolean(legendFocus&&legendFocus!==legend);
      const color=simulated?'var(--color-fg-success-primary)':returning?'var(--color-fg-warning-primary)':legend==='planned'||legend==='unmeasured'?'var(--color-fg-quaternary)':'var(--color-fg-brand-primary)';
      const width=(measured?1.5+7*Math.sqrt(Number(metric.sessions)/maxEdgeSessions):simulated?3:legend==='unmeasured'?1.5:2)+(selectedNodeId&&related?1:0);
      const forecastItem=!metric&&forecast?.edges?.[edge.id];
      return {reconnectable:!readOnly&&!fullNavigation&&!aggregate,id:edge.id,source:edge.from,target:edge.to,
        label:metric?edgeMetricLabel(metric):forecastItem?forecastEdgeLabel(forecastItem):returning?'Retorno':edge.label==='Próximo'?undefined:edge.label,
        ...edgePorts(edge,placed.get(edge.from),placed.get(edge.to),{returning}),type:'flow',animated:simulated,
        style:{strokeWidth:width,opacity:muted?.12:related?1:.25,stroke:color,strokeDasharray:returning&&!simulated?'3 5':legend==='planned'?'6 6':undefined},
        markerEnd:{type:MarkerType.ArrowClosed,color,width:14,height:14,markerUnits:'userSpaceOnUse'},ariaLabel:returning?'Retorno para uma etapa anterior':undefined,
        data:{legend,muted,routing,readOnly:readOnly||fullNavigation||aggregate,onRemove:removeEdge,onInsert:insertOnEdgeAt,hasMetric:Boolean(metric)||Boolean(forecastItem),forecast:Boolean(forecastItem),aggregate,onInspect:aggregate?undefined:onSelectedEdge,
          flowIntensity:journey&&measured&&!returning&&!muted?Math.sqrt(Number(metric.sessions)/maxEdgeSessions):0,liveReady:live?.status==='ready',liveScope,transitionId:live?.transitions?.[edge.id]??live?.origin_transitions?.[edge.id],
          operational:operational&&!muted&&Date.now()-Date.parse(live?.edge_activity?.[edge.id])<90000&&edge.variant!=='planned'&&edge.kind!=='site_link'}};
    });
    authored.push(...ghostEdges.map(e=>({id:`ghost:${e.id}`,source:`ghost:${e.from}`,target:`ghost:${e.to}`,sourceHandle:'right-out',targetHandle:'left-in',type:'flow',style:{stroke:'var(--color-fg-brand-primary)',strokeWidth:1.5,strokeDasharray:'5 5',opacity:.4},data:{readOnly:true,routing}})));
    if(fullNavigation&&journey?.suggestions?.length){
      const ids=new Set((config.nodes||[]).map(node=>node.id));
      authored.push(...journey.suggestions.filter(item=>ids.has(item.from)&&ids.has(item.to)).map(item=>{const muted=Boolean(legendFocus&&legendFocus!=='suggested');return {id:`suggested:${item.from}:${item.to}`,source:item.from,target:item.to,...edgePorts({},placed.get(item.from),placed.get(item.to)),type:'flow',label:`Sugerido · ${Number(item.sessions).toLocaleString('pt-BR')}`,style:{strokeWidth:2,stroke:'var(--color-fg-quaternary)',strokeDasharray:'3 6',opacity:muted?.12:1},markerEnd:{type:MarkerType.ArrowClosed,color:'var(--color-fg-quaternary)'},data:{readOnly:true,legend:'suggested',muted,routing}};}));
    }
    // Fan out connections that share a side so each one stays readable, ordered by where the other end is.
    const fan=(key,handle,other,field)=>{const buckets=new Map();authored.forEach(e=>{const id=`${e[key]}:${e[handle]}`;buckets.set(id,[...(buckets.get(id)||[]),e]);});
      buckets.forEach(list=>{if(list.length<2)return;const vertical=/top|bottom/.test(list[0][handle]||'');const at=e=>{const n=placed.get(e[other]);return vertical?Number(n?.x)||0:Number(n?.y)||0;};list.sort((a,b)=>at(a)-at(b));const step=Math.min(12,48/(list.length-1));list.forEach((e,i)=>{e.data={...e.data,[field]:(i-(list.length-1)/2)*step};});});};
    fan('source','sourceHandle','target','sourceOffset');fan('target','targetHandle','source','targetOffset');
    // Labels whose midpoints land on top of each other are nudged apart.
    const spots=[];
    authored.forEach(e=>{if(!e.label)return;const a=placed.get(e.source),b=placed.get(e.target);if(!a||!b)return;const mx=((Number(a.x)||0)+(Number(b.x)||0))/2,my=((Number(a.y)||0)+(Number(b.y)||0))/2;let offset=0;while(spots.some(p=>Math.abs(p.x-mx)<90&&Math.abs(p.y-(my+offset))<26)&&offset<130)offset+=26;spots.push({x:mx,y:my+offset});if(offset)e.data={...e.data,labelOffset:offset};});
    return authored;
  },[ghostEdges,config.edges,config.nodes,config.groups,expandedGroups,fullNavigation,showReturns,readOnly,removeEdge,insertOnEdgeAt,simulatedPath,journey,live,liveScope,operational,onSelectedEdge,selectedNodeId,forecast,routing,legendFocus,dragPositions]);
  const legendItems=useMemo(()=>{
    const kinds=new Set(edges.map(edge=>edge.data?.legend).filter(Boolean));
    if(exitOverlay)kinds.add('exit');
    if(edges.some(edge=>edge.data?.flowIntensity>0))kinds.add('traffic');
    if(edges.some(edge=>edge.data?.operational))kinds.add('operational');
    if(live?.status==='ready'&&journey)kinds.add('pulse');
    const volumes=(journey?.edges||[]).map(item=>Number(item.sessions||0)).filter(value=>value>0);
    return {kinds,scale:volumes.length?{min:Math.min(...volumes),max:Math.max(...volumes)}:null};
  },[edges,exitOverlay,live?.status,journey]);
  const onNodesChange=useCallback(changes=>{
    const dimensions=changes.filter(c=>c.type==='dimensions'&&c.dimensions);
    if(dimensions.length)setMeasurements(current=>{const next={...current};let changed=false;for(const c of dimensions){if(current[c.id]?.width!==c.dimensions.width||current[c.id]?.height!==c.dimensions.height){next[c.id]=c.dimensions;changed=true;}}return changed?next:current;});
    // The highlighted set is owned here, so selection changes from the canvas (Shift+click, marquee) must be applied.
    const selects=changes.filter(c=>c.type==='select');
    if(selects.length){
      const base=new Set(selectionRef.current?selectionRef.current.split('|').filter(Boolean):selectedNodeId?[selectedNodeId]:[]);
      for(const change of selects){if(change.selected)base.add(change.id);else base.delete(change.id);}
      const ids=[...base];
      selectionRef.current=ids.join('|');
      setSelectedIds(previous=>previous.join('|')===selectionRef.current?previous:ids);
      onSelectedIdsChange(ids);
      if(ids.length===1)setSelectedNodeId(ids[0]);
    }
    if(!canMove)return;
    // Positions stay local while the pointer moves; the document changes once, when the drag ends.
    const positions=changes.filter(c=>c.type==='position'&&c.position);
    if(positions.length){for(const change of positions)pendingPositions.current.set(change.id,change.position);setDragPositions(Object.fromEntries(pendingPositions.current));}
    if(readOnly)return;
    const removed=new Set(changes.filter(c=>c.type==='remove').map(c=>c.id));
    if(!removed.size)return;
    setConfig(current=>syncGroups({...current,groups:(current.groups||[]).filter(g=>!removed.has(g.id)),nodes:current.nodes.filter(n=>!removed.has(n.id)),edges:current.edges.filter(e=>!removed.has(e.from)&&!removed.has(e.to))}));
  },[setConfig,readOnly,canMove,selectedNodeId,onSelectedIdsChange,setSelectedNodeId]);
  const commitDrag=useCallback(()=>{
    const raw=new Map(pendingPositions.current);
    // Moving a card is purely spatial: stage, connections and their visibility never depend on where it lands.
    if(raw.size)setConfig(current=>syncGroups(applyDrag(current,raw,{grid:FLOW_GRID,snap:snapToGrid&&!altPressed})));
    pendingPositions.current.clear();setDragPositions({});onGestureEnd();
  },[setConfig,onGestureEnd,snapToGrid,altPressed]);
  const onEdgesChange=useCallback(changes=>{const removed=new Set(changes.filter(change=>change.type==='remove').map(change=>change.id));if(removed.size)setConfig(current=>({...current,edges:current.edges.filter(edge=>!removed.has(edge.id))}));},[setConfig]);
  const onConnect=useCallback(connection=>{if(readOnly||fullNavigation||!connection.source||!connection.target||connection.source===connection.target||connection.target.startsWith('__')||connection.source.startsWith('__'))return;setConfig(current=>{if(current.edges.some(edge=>edge.from===connection.source&&edge.to===connection.target)||current.edges.length>=300)return current;const sourceNode=current.nodes.find(node=>node.id===connection.source);return {...current,edges:[...current.edges,{id:crypto.randomUUID(),origin:'manual',from:connection.source,to:connection.target,from_port:connection.sourceHandle||'right-out',to_port:connection.targetHandle||'left-in',variant:sourceNode?.type==='source'?'planned':'direct',label:'Próximo'}]};});},[readOnly,fullNavigation,setConfig]);
  const onDrop=useCallback(event=>{event.preventDefault();if(readOnly||fullNavigation||!instance)return;try{const item=JSON.parse(event.dataTransfer.getData('application/x-cadu-flow-node'));onAddNode(item,instance.screenToFlowPosition({x:event.clientX,y:event.clientY}));}catch(_){/* A drag from outside the palette is ignored. */}},[instance,onAddNode,readOnly,fullNavigation]);
  const insertConnected=item=>{
    if(!quickAdd||!instance)return;
    if(quickAdd.edgeId)onInsertEdge?.(quickAdd.edgeId,item);
    // "+" after a card lets the editor find a free spot beside it; a connection dropped on the board lands under the cursor.
    else onAddNode(item,quickAdd.append?null:instance.screenToFlowPosition(quickAdd.screen),quickAdd.source);
    setQuickAdd(null);
  };
  return <><JourneySummary config={config} journey={journey}/><ReactFlow nodes={[...nodes.map(node=>dragPositions[node.id]?{...node,position:dragPositions[node.id]}:node),...(exitOverlay?[exitOverlay.node]:[])]} edges={exitOverlay?[...edges,...exitOverlay.edges.map(edge=>({...edge,data:{...edge.data,legend:'exit',routing},style:{...edge.style,opacity:legendFocus&&legendFocus!=='exit'?.12:edge.style.opacity}}))]:edges} onlyRenderVisibleElements={nodes.length>=80} nodeTypes={nodeTypes} edgeTypes={edgeTypes} onNodesChange={onNodesChange} onNodeDragStart={onGestureStart} onNodeDragStop={commitDrag} onSelectionDragStart={onGestureStart} onSelectionDragStop={commitDrag} onEdgesChange={readOnly||fullNavigation?undefined:onEdgesChange} onEdgeClick={(_,edge)=>{if(!edge.data?.aggregate)onSelectedEdge?.(edge.id);}} onReconnect={(old,connection)=>{if(readOnly||fullNavigation||old.data?.aggregate||!connection.source||!connection.target||connection.source===connection.target||!config.nodes.some(n=>n.id===connection.source)||!config.nodes.some(n=>n.id===connection.target))return;setConfig(current=>current.edges.some(e=>e.id!==old.id&&e.from===connection.source&&e.to===connection.target)?current:{...current,edges:current.edges.map(e=>e.id===old.id?{...e,origin:'manual',from:connection.source,to:connection.target,from_port:connection.sourceHandle||'right-out',to_port:connection.targetHandle||'left-in'}:e)});}} edgesReconnectable={!readOnly&&!fullNavigation} onConnect={onConnect} onConnectEnd={(event,state)=>{if(readOnly||fullNavigation||state.isValid||!state.fromNode)return;setQuickAdd({source:state.fromNode.id,screen:{x:event.clientX,y:event.clientY}});}} onNodeClick={(_,node)=>setSelectedNodeId(node.id)} onNodeContextMenu={(event,node)=>{event.preventDefault();setSelectedNodeId(node.id);setContextMenu({x:event.clientX,y:event.clientY,id:node.id});}} onPaneContextMenu={event=>{event.preventDefault();setContextMenu({x:event.clientX,y:event.clientY,id:null});}} onPaneClick={()=>{setSelectedNodeId('');selectionRef.current='';setSelectedIds([]);onSelectedIdsChange([]);setQuickAdd(null);setContextMenu(null);}} onInit={flow=>{setInstance(flow);onReady({...flow,toggleReturns:()=>setShowReturns(v=>!v),showReturns:()=>setShowReturns(true),toggleNavigation:()=>setFullNavigation(v=>!v)});}} onMoveEnd={(_,viewport)=>onZoomChange(viewport.zoom)} onDragOver={event=>event.preventDefault()} onDrop={onDrop} nodesDraggable={canMove} nodesConnectable={!readOnly&&!fullNavigation} elementsSelectable={true} selectionOnDrag={!readOnly} panOnDrag={readOnly?true:[1,2]} panOnScroll panOnScrollMode="free" zoomOnPinch zoomOnDoubleClick={false} multiSelectionKeyCode="Shift" minZoom={0.1} maxZoom={2} defaultViewport={{x:80,y:80,zoom:1}} snapToGrid={snapToGrid&&!altPressed} snapGrid={[FLOW_GRID,FLOW_GRID]} deleteKeyCode={readOnly||fullNavigation?null:['Backspace','Delete']} attributionPosition="bottom-right"><Controls fitViewOptions={{padding:.2,maxZoom:1}} showInteractive={false} position="bottom-left">{onOrganize&&<ControlButton aria-label="Organizar fluxo" title="Organizar fluxo" onClick={onOrganize}><LayoutGrid01 size={16}/></ControlButton>}<ControlButton aria-label="Alternar minimapa" title="Mostrar ou ocultar minimapa" onClick={()=>setShowMiniMap(v=>!v)}><LayersTwo01 size={16}/></ControlButton><ControlButton aria-label={routing==='orthogonal'?'Usar traços curvos':'Usar traços em ângulo reto'} title={routing==='orthogonal'?'Traços curvos':'Traços em ângulo reto'} aria-pressed={routing==='orthogonal'} onClick={toggleRouting}><Route size={16}/></ControlButton><ZoomReadout/></Controls><FlowEdgeLegend kinds={legendItems.kinds} scale={legendItems.scale} focus={legendFocus} onFocus={setLegendFocus} inspectorOpen={inspectorOpen}/><FitLoadedGraph enabled={fitOnMount} fitKey={fitKey} monitor={fitMonitor}/><Background variant={BackgroundVariant.Dots} gap={FLOW_GRID} size={1} color="var(--color-border-secondary)"/>{showMiniMap&&config.nodes.length>0&&<MiniMap position="bottom-right" aria-label="Minimapa do fluxo" style={{width:150,height:95,right:inspectorOpen?380:18,bottom:52}} pannable zoomable nodeColor={n=>({source:"#6172f3",entry:"#1570ef",exploration:"#06aed4",intent:"#f79009",conversion:"#17b26a",support:"#98a2b3"}[stageFor(n.data.node||{})])}/>}</ReactFlow>{quickAdd&&<div className="flow-quick-add" style={{left:Math.min(quickAdd.screen.x,window.innerWidth-180),top:Math.min(quickAdd.screen.y,window.innerHeight-160)}} role="dialog" aria-label={quickAdd.edgeId?'Inserir etapa na conexão':'Adicionar etapa conectada'}><strong>{quickAdd.edgeId?'Inserir etapa':'Próxima etapa'}</strong>{QUICK_ADD_TYPES.map(item=><button key={item.type} type="button" onClick={()=>insertConnected(item)}>{item.label}</button>)}<button type="button" onClick={()=>setQuickAdd(null)}>Cancelar</button></div>}{contextMenu&&<div className="flow-quick-add" style={{left:Math.min(contextMenu.x,window.innerWidth-180),top:Math.min(contextMenu.y,window.innerHeight-160)}} role="menu" aria-label="Ações do canvas">{contextMenu.id&&<><button type="button" role="menuitem" disabled={readOnly||fullNavigation} onClick={()=>{onDuplicateSelection(contextMenu.id);setContextMenu(null);}}>Duplicar nó</button><button type="button" role="menuitem" disabled={readOnly||fullNavigation} onClick={()=>{const id=contextMenu.id;setConfig(current=>syncGroups({...current,nodes:current.nodes.filter(node=>node.id!==id),edges:current.edges.filter(edge=>edge.from!==id&&edge.to!==id)}));setContextMenu(null);}}>Remover do fluxo</button>{!readOnly&&!fullNavigation&&<button type="button" role="menuitem" onClick={()=>{setQuickAdd({source:contextMenu.id,append:true,screen:{x:contextMenu.x,y:contextMenu.y}});setContextMenu(null);}}>Adicionar etapa depois</button>}</>}<button type="button" role="menuitem" onClick={()=>{if(!fitToVisibleArea(instance,{duration:200}))instance?.fitView({padding:.15,duration:200});setContextMenu(null);}}>Ajustar à tela</button></div>}</>;
}

export function FlowCanvas(props) {
  return <div className="reports-flow-canvas flow-react-canvas" role="region" aria-label="Mapa visual do fluxo"><ReactFlowProvider><FlowCanvasInner {...props}/></ReactFlowProvider></div>;
}
