import {FLOW_STAGES,stageFor,stageAtX,stageX,funnelEdges,isReturnEdge,FLOW_STAGE_WIDTH,FLOW_GRID} from './flowStages.js';
import {edgeMetricLabel} from './flowMetricLabels.js';
import {flowRoleLabel,flowRoleSourceLabel,flowStageLabel} from './flowUiLabels.js';
import {useFlowPreviews} from './useFlowPreviews.js';
import {RefreshCw01, Copy01, Trash01, LayoutGrid01, LayersTwo01} from '@untitledui/icons';
import React, {useEffect, useCallback, useMemo, useRef, useState} from 'react';
import {ReactFlow, useReactFlow, useUpdateNodeInternals, Background, BackgroundVariant, BaseEdge, EdgeLabelRenderer, Handle, MarkerType, MiniMap, Controls, ControlButton, NodeToolbar, NodeResizer, useViewport, Position, ReactFlowProvider, getBezierPath} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import {flowBlockFor} from './flowBlockRegistry.js';
import {NODE_STATUS_LABELS,hasRealPath,isPlanned,nodeStatus} from './flowLifecycle.js';
import {FLOW_PLATFORMS, FlowPlatformLogo} from './FlowPlatformLogo.jsx';
import './flow-canvas.css';
import {FlowEdgeActivity} from './FlowEdgeActivity.jsx';
import {ungroupNodes,syncGroups} from './flowGroups.js';
import {ReportsActionButton} from './ReportsActionButton.jsx';


function nodeMetric(journey,node){
  const metric=journey?.nodes?.find(item=>item.id===node.id);
  if(!metric||metric.sessions==null)return metric;
  if(metric.exits!=null)return metric;
  const outgoing=(journey.edges||[]).filter(edge=>edge.from===node.id&&edge.sessions!=null);
  const exits=outgoing.length||node.type==='conversion'?Math.max(0,metric.sessions-outgoing.reduce((sum,edge)=>sum+Number(edge.sessions||0),0)):null;
  return {...metric,exits,exitsEstimated:exits!=null};
}

function JourneySummary({config,journey}) {
  if(journey?.status!=='ready'||!journey.nodes?.length)return null;
  const rows=config.nodes.map(node=>({node,metric:nodeMetric(journey,node)})).filter(row=>row.metric?.sessions!=null);
  const arrived=rows.filter(row=>row.node.type==='source').reduce((sum,row)=>sum+row.metric.sessions,0);
  const converted=rows.filter(row=>row.node.type==='conversion').reduce((sum,row)=>sum+row.metric.sessions,0);
  const exits=rows.filter(row=>!['source','conversion'].includes(row.node.type));
  const left=exits.reduce((sum,row)=>sum+(row.metric.exits||0),0);
  const top=exits.slice().sort((a,b)=>(b.metric.exits||0)-(a.metric.exits||0))[0];
  if(!arrived&&!converted)return null;
  if(config.site_kind==='institucional'){
    const engagement=journey.engagement||{};
    return <div className="flow-journey-summary" role="status"><span><b>{number(arrived)}</b> chegaram</span>{engagement.pages_per_session!=null&&<span><b>{engagement.pages_per_session.toLocaleString('pt-BR',{maximumFractionDigits:1})}</b> páginas por visita</span>}{engagement.avg_active_ms!=null&&<span><b>{duration(engagement.avg_active_ms)}</b> ativos por página</span>}<span><b>{number(left)}</b> saíram</span>{top&&top.metric.exits>0&&<span>Maior saída: <b>{top.node.title}</b> ({number(top.metric.exits)})</span>}</div>;
  }
  const rate=arrived?Math.round(converted/arrived*100):null;
  return <div className="flow-journey-summary" role="status"><span><b>{number(arrived)}</b> chegaram</span><span><b>{number(converted)}</b> converteram{rate!=null&&` · ${rate}%`}</span><span><b>{number(left)}</b> saíram sem converter</span>{top&&top.metric.exits>0&&<span>Maior saída: <b>{top.node.title}</b> ({number(top.metric.exits)})</span>}</div>;
}

function FitLoadedGraph({enabled}) {
  // Fit once every visible node has real dimensions; React Flow's own fitView can run before cards are measured.
  const api=useReactFlow();
  const fitted=useRef(false);
  useEffect(()=>{
    if(!enabled||fitted.current)return;
    let attempts=0;
    const timer=setInterval(()=>{
      const visible=api.getNodes().filter(node=>!node.hidden);
      const ready=visible.length&&visible.every(node=>api.getInternalNode(node.id)?.measured?.width);
      if(ready||++attempts>40){clearInterval(timer);if(visible.length){api.fitView({padding:.12,maxZoom:1});fitted.current=true;}}
    },50);
    return()=>clearInterval(timer);
  },[enabled,api]);
  return null;
}

function FlowLanes({nodes}){
  // Lanes follow where each stage's nodes actually are; they label the reading order, they do not constrain it.
  const {x,y,zoom}=useViewport();
  const lanes=FLOW_STAGES.map(stage=>{const members=nodes.filter(node=>!node.groupId&&stageFor(node)===stage.id);if(!members.length)return null;const xs=members.map(node=>Number(node.x)||0);return {stage,left:Math.min(...xs)-20,right:Math.max(...xs)+252,top:Math.min(...members.map(node=>Number(node.y)||0))};}).filter(Boolean);
  return <div className="flow-lanes" aria-hidden="true">{lanes.map(lane=><div key={lane.stage.id} style={{left:x+lane.left*zoom,width:(lane.right-lane.left)*zoom}}><span style={{top:Math.max(8,y+(lane.top-34)*zoom)}}>{lane.stage.label}</span></div>)}</div>;
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
  const [hovered,setHovered]=useState(false);
  const block=flowBlockFor(node);
  const Icon=block.icon;
  const isPage=['page','form','error'].includes(node.type)||block.shape==='page';
  const capture=isPage&&zoom>=.4&&preview?.url&&brokenImage!==preview.url;
  const platform=node.type==='source'&&FLOW_PLATFORMS[block.source||node.source];
  const path=hasRealPath(node)?node.path:'';
  const planned=isPlanned(node);
  return <div onMouseEnter={()=>setHovered(true)} onMouseLeave={()=>setHovered(false)} className={`fnode is-tone-${block.tone} is-type-${node.type}${planned?' is-planned':''}${zoom<.55?' is-compact':''}${selected?' is-selected':''}`}>
    <NodeHandles/>
    <NodeToolbar className="flow-node-hover" isVisible={hovered&&!selected&&zoom>=.55} position={Position.Bottom}><strong>{node.title}</strong>{path&&<small>{node.host}{path}</small>}<small>Etapa: {flowStageLabel(node)} · Função: {flowRoleLabel(node.role)} · {flowRoleSourceLabel(node.role_source)}</small>{node.evidence&&<p>{node.evidence}</p>}{data.paths?.map(item=><small key={item.id}>{item.label} · {number(item.sessions)} sessões</small>)}</NodeToolbar>
    <NodeToolbar isVisible={selected&&!readOnly} position={Position.Top}><ReportsActionButton aria-label="Duplicar nó" onClick={()=>onDuplicate(node.id)}><Copy01 size={16}/></ReportsActionButton><ReportsActionButton aria-label="Remover do fluxo" onClick={()=>onRemove(node.id)}><Trash01 size={16}/></ReportsActionButton>{isPage&&canCapture&&<ReportsActionButton aria-label={preview?.status==='ready'?'Atualizar captura':'Solicitar captura'} onClick={()=>onRegenerate(node.id)}><RefreshCw01 size={16}/></ReportsActionButton>}</NodeToolbar>
    {capture&&<img className="fnode__capture" src={preview.canvas_url||preview.url} alt="" loading="lazy" decoding="async" onLoad={()=>updateInternals(id)} onError={()=>setBrokenImage(preview.url)}/>}
    <div className="fnode__head"><span className="fnode__icon">{platform?<FlowPlatformLogo platform={block.source||node.source}/>:<Icon size={16}/>}</span><span className="fnode__kind">{KIND_LABELS[node.type]||'Etapa'}</span>{planned&&<span className="fnode__status">{NODE_STATUS_LABELS[nodeStatus(node)]}</span>}{block.trackable&&!planned&&!path&&node.type!=='event'&&node.type!=='conversion'&&<span className="fnode__warn" title="Configure a URL real deste nó" aria-label="Configure a URL real deste nó">!</span>}</div>
    <NodeLabel node={node} selected={selected} readOnly={readOnly} onChange={onLabelChange}/>
    {path?<small className="fnode__path">{path}</small>:planned&&node.spec?.suggested_path&&<small className="fnode__path is-suggested">{node.spec.suggested_path}</small>}
    {node.type==='source'&&node.segment?.name&&<small className="fnode__segment">{node.segment.name}</small>}
    {node.type==='source'&&PAID_UTM[block.source||node.source]&&<small className="fnode__path">utm_source={PAID_UTM[block.source||node.source]}</small>}
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

const nodeTypes = {exitSink:ExitSinkNode,groupFrame:GroupNode,visual:MemoShapeNode,circle:MemoShapeNode,diamond:MemoShapeNode,page:MemoShapeNode,note:React.memo(NoteNode)};

function FlowEdge({id,sourceX,sourceY,targetX,targetY,sourcePosition,targetPosition,markerEnd,markerStart,style,data,label,selected}) {
  const [hovered,setHovered]=useState(false);
  const [path,labelX,labelY]=getBezierPath({sourceX,sourceY,targetX,targetY,sourcePosition,targetPosition,curvature:.35});
  return <><BaseEdge id={id} path={path} markerEnd={markerEnd} markerStart={markerStart} style={style}/><FlowEdgeActivity path={path} operational={data.operational} transitionId={data.transitionId} ready={data.liveReady} scope={data.liveScope}/><path d={path} fill="none" stroke="transparent" strokeWidth="20" onMouseEnter={()=>setHovered(true)} onMouseLeave={()=>setHovered(false)}/><EdgeLabelRenderer><div className={`flow-edge-actions nodrag nopan${hovered||selected||data.hasMetric?' is-visible':''}${data.forecast?' is-forecast':''}`} style={{transform:`translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`}} onMouseEnter={()=>setHovered(true)} onMouseLeave={()=>setHovered(false)}><span onClick={()=>data.onInspect?.(id)}>{label}</span>{!data.readOnly&&<><button type="button" aria-label="Inserir nó nesta Conexão" onClick={()=>data.onInsert(id)}>+</button><button type="button" aria-label="Remover conexão" onClick={()=>data.onRemove(id)}>×</button></>}</div></EdgeLabelRenderer></>;
}

const edgeTypes={flow:FlowEdge};

function FlowCanvasInner({onNavigationModeChange,ghostEdges=[],ghostNodes=[],config,setConfig,selectedNodeId,setSelectedNodeId,onSelectedIdsChange=()=>{},onAddNode,onInsertEdge,onDuplicateSelection,readOnly,simulatedPath=[],journey=null,snapToGrid,onReady=()=>{},onZoomChange=()=>{},onSelectedEdge,onOrganize,live=null,liveScope='',operational=false,fitOnMount=false,onGestureStart=()=>{},onGestureEnd=()=>{},previewContext,inspectorOpen=false,forecast=null} ) {
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
  const onLabelChange=useCallback((id,title)=>setConfig(current=>({...current,nodes:current.nodes.map(node=>node.id===id?{...node,title,manuallyEdited:true}:node)})),[setConfig]);
  // Every journey ends in one of two ways: it converts or it leaves. Conversion flows show both by default;
  // institutional flows show where visits end. Without data the end is drawn as part of the plan.
  const conversionFlow=config.site_kind!=='institucional'&&(config.nodes||[]).some(node=>node.type==='conversion');
  const exitsVisible=showExits??conversionFlow;
  const exitOverlay=useMemo(()=>{
    if(!exitsVisible||!(config.nodes||[]).length)return null;
    const engagement=config.site_kind==='institucional';
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
  },[exitsVisible,journey,config.nodes,config.edges,config.site_kind]);
  const journeyArrived=useMemo(()=>{if(!journey?.nodes)return 0;const byId=new Map((config.nodes||[]).map(node=>[node.id,node]));const fromSources=journey.nodes.filter(item=>byId.get(item.id)?.type==='source').reduce((sum,item)=>sum+Number(item.sessions||0),0);return fromSources||Number(journey.funnel?.entries||0);},[journey,config.nodes]);
  const nodes=useMemo(()=>{
    const groups=config.groups||[];
    const parents=groups.map(group=>({id:group.id,type:'groupFrame',position:{x:group.bounds.x,y:group.bounds.y},style:{width:expandedGroups.has(group.id)?group.bounds.width:180,height:expandedGroups.has(group.id)?group.bounds.height:130},data:{group,metric:journey?.group_nodes?.find(n=>n.id===group.id),collapsed:!expandedGroups.has(group.id),toggle:()=>setExpandedGroups(current=>{const next=new Set(current);next.has(group.id)?next.delete(group.id):next.add(group.id);return next;}),readOnly:readOnly||fullNavigation,ungroup:id=>setConfig(current=>ungroupNodes(current,id)),resize:(id,size)=>setConfig(current=>({...current,groups:current.groups.map(g=>g.id===id?{...g,bounds:{x:size.x,y:size.y,width:size.width,height:size.height}}:g)}))},draggable:!readOnly&&!fullNavigation&&!config.nodes.some(n=>group.memberIds.includes(n.id)&&n.locked),selectable:true}));
    const items=(config.nodes||[]).map(node=>{
      const parent=groups.find(g=>g.id===node.groupId);
      return {id:node.id,hidden:Boolean(parent&&!expandedGroups.has(parent.id)),measured:measurements[node.id],type:flowBlockFor(node).shape,parentId:parent?.id,extent:parent?'parent':undefined,
        className:simulatedPath.includes(node.id)?'is-simulated':'',position:{x:(Number.isFinite(Number(node.x))&&node.x!==''&&node.x!=null?Number(node.x):stageX(stageFor(node)))-(parent?.bounds.x||0),y:(Number(node.y)||0)-(parent?.bounds.y||0)},
        data:{node,forecastSessions:forecast&&node.type!=='note'?forecast.nodes[node.id]??null:null,paths:journey?.edges?.filter(e=>(e.from===node.id||e.to===node.id)&&e.sessions>0).sort((a,b)=>b.sessions-a.sessions).slice(0,3).map(e=>({id:e.id,sessions:e.sessions,label:`${e.to===node.id?'De':'Para'} ${config.nodes.find(n=>n.id===(e.to===node.id?e.from:e.to))?.title||'nó'}`})),preview:{...previews.items[node.id],message:previews.error||previews.items[node.id]?.message,unavailable:!previews.available},onRegenerate:previews.regenerate,canCapture:previewContext?.canCapture&&previews.available,readOnly:readOnly||fullNavigation,onLabelChange,onDuplicate:onDuplicateSelection,onRemove:id=>setConfig(current=>syncGroups({...current,nodes:current.nodes.filter(n=>n.id!==id),edges:current.edges.filter(e=>e.from!==id&&e.to!==id)})),metric:nodeMetric(journey,node),arrived:journeyArrived},draggable:!readOnly&&!fullNavigation&&!node.locked,selectable:true,selected:selectedIds.length?selectedIds.includes(node.id):node.id===selectedNodeId};
    });return [...parents,...items,...ghostNodes.map(node=>({id:`ghost:${node.id}`,type:flowBlockFor(node).shape,position:{x:node.x,y:node.y},className:"flow-ghost-node",data:{node,readOnly:true},draggable:false,selectable:false}))];
  },[config,ghostNodes,expandedGroups,readOnly,onLabelChange,selectedNodeId,selectedIds,simulatedPath,journey,onDuplicateSelection,setConfig,measurements,fullNavigation,previews.items,previews.regenerate,previews.available,previews.error,previewContext?.canCapture,journeyArrived]);
  const removeEdge=useCallback(id=>setConfig(current=>({...current,edges:current.edges.filter(edge=>edge.id!==id)})),[setConfig]);
  const edges=useMemo(()=>{
    const memberGroup=new Map((config.groups||[]).filter(g=>!expandedGroups.has(g.id)).flatMap(g=>g.memberIds.map(id=>[id,g.id])));
    const renderedPairs=new Set();
    const maxEdgeSessions=Math.max(1,...(journey?.edges||[]).map(item=>Number(item.sessions||0)));
    const projected={...config,nodes:[...config.nodes,...(config.groups||[]).map(g=>({id:g.id,stage:stageFor(config.nodes.find(n=>g.memberIds.includes(n.id))||{})}))],edges:config.edges.map(e=>({...e,from:memberGroup.get(e.from)||e.from,to:memberGroup.get(e.to)||e.to})).filter(e=>{const key=`${e.from}:${e.to}`;if(e.from===e.to||renderedPairs.has(key))return false;renderedPairs.add(key);return true;})};
    const stageNodes=new Map(projected.nodes.map(node=>[node.id,node]));
    const authored=funnelEdges(projected,{full:fullNavigation,returns:showReturns}).map(edge=>{const returning=isReturnEdge(edge,stageNodes);const related=!selectedNodeId||edge.from===selectedNodeId||edge.to===selectedNodeId;const planned=edge.variant==='planned'||edge.kind==='site_link';const simulated=simulatedPath.some((id,index)=>id===edge.from&&simulatedPath[index+1]===edge.to);const metric=memberGroup.has((config.edges||[]).find(e=>e.id===edge.id)?.from)||memberGroup.has((config.edges||[]).find(e=>e.id===edge.id)?.to)?(expandedGroups.size?null:journey?.group_edges?.find(item=>item.from===edge.from&&item.to===edge.to)):journey?.edges?.find(item=>item.id===edge.id);const color=simulated?'var(--color-fg-success-primary)':returning?'var(--color-fg-warning-primary)':planned?'var(--color-fg-quaternary)':'var(--color-fg-brand-primary)';return {reconnectable:!readOnly&&!fullNavigation&&!memberGroup.has((config.edges||[]).find(e=>e.id===edge.id)?.from)&&!memberGroup.has((config.edges||[]).find(e=>e.id===edge.id)?.to),id:edge.id,source:edge.from,target:edge.to,label:metric?edgeMetricLabel(metric):forecast&&forecast.edges[edge.id]?forecastEdgeLabel(forecast.edges[edge.id]):returning?'Retorno':edge.label==='Próximo'?undefined:edge.label,sourceHandle:returning?'left-out':edge.from_port||'right-out',targetHandle:returning?'right-in':edge.to_port||'left-in',type:'flow',animated:simulated,style:{strokeWidth:(metric?1.5+7*Math.sqrt(Math.max(0,Number(metric.sessions||0))/maxEdgeSessions):simulated?3:2)+(selectedNodeId&&related?1:0),opacity:related?1:.25,stroke:color,strokeDasharray:returning&&!simulated?'3 5':planned&&!simulated?'6 6':undefined},markerEnd:{type:MarkerType.ArrowClosed,color,width:14,height:14,markerUnits:'userSpaceOnUse'},ariaLabel:returning?'Retorno para uma Etapa anterior':undefined,data:{readOnly:readOnly||fullNavigation||memberGroup.has((config.edges||[]).find(e=>e.id===edge.id)?.from)||memberGroup.has((config.edges||[]).find(e=>e.id===edge.id)?.to),onRemove:removeEdge,onInsert:onInsertEdge,hasMetric:Boolean(metric)||Boolean(forecast&&forecast.edges[edge.id]),forecast:Boolean(!metric&&forecast&&forecast.edges[edge.id]),aggregate:memberGroup.has((config.edges||[]).find(e=>e.id===edge.id)?.from)||memberGroup.has((config.edges||[]).find(e=>e.id===edge.id)?.to),onInspect:(memberGroup.has((config.edges||[]).find(e=>e.id===edge.id)?.from)||memberGroup.has((config.edges||[]).find(e=>e.id===edge.id)?.to))?undefined:onSelectedEdge,liveReady:live?.status==='ready',liveScope,transitionId:live?.transitions?.[edge.id],operational:operational&&Date.now()-Date.parse(live?.edge_activity?.[edge.id])<90000&&edge.variant!=='planned'&&edge.kind!=='site_link'}};});
    authored.push(...ghostEdges.map(e=>({id:`ghost:${e.id}`,source:`ghost:${e.from}`,target:`ghost:${e.to}`,sourceHandle:'right-out',targetHandle:'left-in',type:'flow',style:{stroke:'var(--color-fg-brand-primary)',strokeWidth:1.5,strokeDasharray:'5 5',opacity:.4},data:{readOnly:true}})));
    if(!fullNavigation||!journey?.suggestions?.length)return authored;
    const ids=new Set((config.nodes||[]).map(node=>node.id));
    const suggestions=journey.suggestions.filter(item=>ids.has(item.from)&&ids.has(item.to)).map(item=>({id:`suggested:${item.from}:${item.to}`,source:item.from,target:item.to,type:'flow',label:`Sugerido · ${Number(item.sessions).toLocaleString('pt-BR')}`,style:{strokeWidth:2,stroke:'var(--color-fg-quaternary)',strokeDasharray:'3 6'},markerEnd:{type:MarkerType.ArrowClosed,color:'var(--color-fg-quaternary)'},data:{readOnly:true}}));
    return [...authored,...suggestions];
  },[ghostEdges,config.edges,config.nodes,config.groups,expandedGroups,fullNavigation,showReturns,readOnly,removeEdge,onInsertEdge,simulatedPath,journey,live,liveScope,operational,onSelectedEdge,selectedNodeId]);
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
    if(readOnly||fullNavigation)return;
    const positions=changes.filter(c=>c.type==='position'&&c.position);
    if(positions.length){for(const change of positions)pendingPositions.current.set(change.id,change.position);setDragPositions(Object.fromEntries(pendingPositions.current));}
    const moved=new Map();
    const removed=new Set(changes.filter(c=>c.type==='remove').map(c=>c.id));
    if(!moved.size&&!removed.size)return;
    setConfig(current=>{
      const groups=(current.groups||[]).filter(g=>!removed.has(g.id)).map(g=>({...g,bounds:{...g.bounds,...moved.get(g.id)}}));
      return syncGroups({...current,groups,nodes:current.nodes.filter(n=>!removed.has(n.id)).map(node=>{
        const oldParent=(current.groups||[]).find(g=>g.id===node.groupId),parent=groups.find(g=>g.id===node.groupId),move=moved.get(node.id),groupMoved=Boolean(parent&&moved.has(parent.id));
        const x=move?move.x+(parent?.bounds.x||0):Number(node.x)+(parent&&oldParent?parent.bounds.x-oldParent.bounds.x:0);
        const y=move?move.y+(parent?.bounds.y||0):Number(node.y)+(parent&&oldParent?parent.bounds.y-oldParent.bounds.y:0);
        return {...node,...(groupMoved?{manuallyEdited:true}:{}),...(move?{manuallyEdited:true,stage:node.type==='source'?'source':stageAtX(x)}:{}),groupId:parent?.id,x:Math.max(0,Math.min(10000,Math.round(x))),y:Math.max(0,Math.min(10000,Math.round(y)))};
      }),edges:current.edges.filter(e=>!removed.has(e.from)&&!removed.has(e.to))});
    });
  },[setConfig,readOnly,fullNavigation,selectedNodeId,onSelectedIdsChange,setSelectedNodeId]);
  const commitDrag=useCallback(()=>{
    const moved=new Map(pendingPositions.current),removed=new Set();
    if(moved.size){
    setConfig(current=>{
      const groups=(current.groups||[]).filter(g=>!removed.has(g.id)).map(g=>({...g,bounds:{...g.bounds,...moved.get(g.id)}}));
      return syncGroups({...current,groups,nodes:current.nodes.filter(n=>!removed.has(n.id)).map(node=>{
        const oldParent=(current.groups||[]).find(g=>g.id===node.groupId),parent=groups.find(g=>g.id===node.groupId),move=moved.get(node.id),groupMoved=Boolean(parent&&moved.has(parent.id));
        const x=move?move.x+(parent?.bounds.x||0):Number(node.x)+(parent&&oldParent?parent.bounds.x-oldParent.bounds.x:0);
        const y=move?move.y+(parent?.bounds.y||0):Number(node.y)+(parent&&oldParent?parent.bounds.y-oldParent.bounds.y:0);
        return {...node,...(groupMoved?{manuallyEdited:true}:{}),...(move?{manuallyEdited:true,stage:node.type==='source'?'source':stageAtX(x)}:{}),groupId:parent?.id,x:Math.max(0,Math.min(10000,Math.round(x))),y:Math.max(0,Math.min(10000,Math.round(y)))};
      }),edges:current.edges.filter(e=>!removed.has(e.from)&&!removed.has(e.to))});
    });
    }
    pendingPositions.current.clear();setDragPositions({});onGestureEnd();
  },[setConfig,onGestureEnd]);
  const onEdgesChange=useCallback(changes=>{const removed=new Set(changes.filter(change=>change.type==='remove').map(change=>change.id));if(removed.size)setConfig(current=>({...current,edges:current.edges.filter(edge=>!removed.has(edge.id))}));},[setConfig]);
  const onConnect=useCallback(connection=>{if(readOnly||fullNavigation||!connection.source||!connection.target||connection.source===connection.target||connection.target.startsWith('__')||connection.source.startsWith('__'))return;setConfig(current=>{if(current.edges.some(edge=>edge.from===connection.source&&edge.to===connection.target)||current.edges.length>=300)return current;const sourceNode=current.nodes.find(node=>node.id===connection.source);return {...current,edges:[...current.edges,{id:crypto.randomUUID(),from:connection.source,to:connection.target,from_port:connection.sourceHandle||'right-out',to_port:connection.targetHandle||'left-in',variant:sourceNode?.type==='source'?'planned':'direct',label:'Próximo'}]};});},[readOnly,fullNavigation,setConfig]);
  const onDrop=useCallback(event=>{event.preventDefault();if(readOnly||fullNavigation||!instance)return;try{const item=JSON.parse(event.dataTransfer.getData('application/x-cadu-flow-node'));onAddNode(item,instance.screenToFlowPosition({x:event.clientX,y:event.clientY}));}catch(_){/* A drag from outside the palette is ignored. */}},[instance,onAddNode,readOnly,fullNavigation]);
  const insertConnected=item=>{if(!quickAdd||!instance)return;onAddNode(item,instance.screenToFlowPosition(quickAdd.screen),quickAdd.source);setQuickAdd(null);};
  return <>{config.nodes.length>0&&<div className="flow-view-policy"><details className="flow-view-menu"><summary>Exibir{(fullNavigation||showReturns)&&<span className="flow-view-menu__dot" aria-label="Filtros ativos"/>}</summary><div role="group" aria-label="Opções de exibição"><label><input type="checkbox" checked={fullNavigation} onChange={event=>setFullNavigation(event.target.checked)}/>Navegação completa{!fullNavigation&&config.edges.length>edges.length&&<small>{config.edges.length-edges.length} conexões ocultas</small>}</label><label><input type="checkbox" checked={showReturns} onChange={event=>setShowReturns(event.target.checked)}/>Retornos a etapas anteriores</label><label><input type="checkbox" checked={exitsVisible} onChange={event=>setShowExits(event.target.checked)}/>{config.site_kind==='institucional'?'Saídas do site':'Saiu sem converter'}<small>{journey?.status==='ready'?'Páginas onde 20% ou mais encerram a visita':'Último passo antes da conversão'}</small></label><p>Linhas mais grossas levam mais sessões. Tracejado cinza: conexão planejada. Laranja: retorno. “Sem dados” é diferente de zero observado.</p>{simulatedPath.length>0&&<strong>Simulação fictícia</strong>}</div></details></div>}<JourneySummary config={config} journey={journey}/><ReactFlow nodes={[...nodes.map(node=>dragPositions[node.id]?{...node,position:dragPositions[node.id]}:node),...(exitOverlay?[exitOverlay.node]:[])]} edges={exitOverlay?[...edges,...exitOverlay.edges]:edges} onlyRenderVisibleElements={nodes.length>=80} nodeTypes={nodeTypes} edgeTypes={edgeTypes} onNodesChange={onNodesChange} onNodeDragStart={onGestureStart} onNodeDragStop={commitDrag} onSelectionDragStart={onGestureStart} onSelectionDragStop={commitDrag} onEdgesChange={readOnly||fullNavigation?undefined:onEdgesChange} onEdgeClick={(_,edge)=>{if(!edge.data?.aggregate)onSelectedEdge?.(edge.id);}} onReconnect={(old,connection)=>{if(readOnly||fullNavigation||old.data?.aggregate||!connection.source||!connection.target||connection.source===connection.target||!config.nodes.some(n=>n.id===connection.source)||!config.nodes.some(n=>n.id===connection.target))return;setConfig(current=>current.edges.some(e=>e.id!==old.id&&e.from===connection.source&&e.to===connection.target)?current:{...current,edges:current.edges.map(e=>e.id===old.id?{...e,origin:'manual',from:connection.source,to:connection.target,from_port:connection.sourceHandle||'right-out',to_port:connection.targetHandle||'left-in'}:e)});}} edgesReconnectable={!readOnly&&!fullNavigation} onConnect={onConnect} onConnectEnd={(event,state)=>{if(readOnly||fullNavigation||state.isValid||!state.fromNode)return;setQuickAdd({source:state.fromNode.id,screen:{x:event.clientX,y:event.clientY}});}} onNodeClick={(_,node)=>setSelectedNodeId(node.id)} onNodeContextMenu={(event,node)=>{event.preventDefault();setSelectedNodeId(node.id);setContextMenu({x:event.clientX,y:event.clientY,id:node.id});}} onPaneContextMenu={event=>{event.preventDefault();setContextMenu({x:event.clientX,y:event.clientY,id:null});}} onPaneClick={()=>{setSelectedNodeId('');selectionRef.current='';setSelectedIds([]);onSelectedIdsChange([]);setQuickAdd(null);setContextMenu(null);}} onInit={flow=>{setInstance(flow);onReady({...flow,toggleReturns:()=>setShowReturns(v=>!v),toggleNavigation:()=>setFullNavigation(v=>!v)});}} onMoveEnd={(_,viewport)=>onZoomChange(viewport.zoom)} onDragOver={event=>event.preventDefault()} onDrop={onDrop} nodesDraggable={!readOnly&&!fullNavigation} nodesConnectable={!readOnly&&!fullNavigation} elementsSelectable={true} selectionOnDrag={!readOnly} panOnDrag={readOnly?true:[1,2]} multiSelectionKeyCode="Shift" minZoom={0.1} maxZoom={2} defaultViewport={{x:80,y:80,zoom:1}} snapToGrid={snapToGrid&&!altPressed} snapGrid={[FLOW_GRID,FLOW_GRID]} fitView={fitOnMount} fitViewOptions={{padding:.2,maxZoom:1}} deleteKeyCode={readOnly||fullNavigation?null:['Backspace','Delete']} attributionPosition="bottom-right"><Controls fitViewOptions={{padding:.2,maxZoom:1}} showInteractive={false} position="bottom-left">{onOrganize&&<ControlButton aria-label="Organizar fluxo" onClick={onOrganize}><LayoutGrid01 size={16}/></ControlButton>}<ControlButton aria-label="Alternar minimapa" onClick={()=>setShowMiniMap(v=>!v)}><LayersTwo01 size={16}/></ControlButton></Controls><FitLoadedGraph enabled={fitOnMount}/>{config.layoutMode!=='free'&&config.nodes.some(n=>n.stage)&&<FlowLanes nodes={config.nodes}/>}<Background variant={BackgroundVariant.Dots} gap={FLOW_GRID} size={1} color="var(--color-border-secondary)"/>{showMiniMap&&config.nodes.length>0&&<MiniMap position="bottom-right" aria-label="Minimapa do fluxo" style={{width:150,height:95,right:inspectorOpen?380:18,bottom:52}} pannable zoomable nodeColor={n=>({source:"#6172f3",entry:"#1570ef",exploration:"#06aed4",intent:"#f79009",conversion:"#17b26a",support:"#98a2b3"}[stageFor(n.data.node||{})])}/>}</ReactFlow>{quickAdd&&<div className="flow-quick-add" style={{left:Math.min(quickAdd.screen.x,window.innerWidth-180),top:Math.min(quickAdd.screen.y,window.innerHeight-160)}} role="dialog" aria-label="Adicionar nó conectado"><strong>Adicionar nó</strong>{[{type:'page',label:'Página'},{type:'form',label:'Formulário'},{type:'conversion',label:'Conversão'}].map(item=><button key={item.type} type="button" onClick={()=>insertConnected(item)}>{item.label}</button>)}<button type="button" onClick={()=>setQuickAdd(null)}>Cancelar</button></div>}{contextMenu&&<div className="flow-quick-add" style={{left:Math.min(contextMenu.x,window.innerWidth-180),top:Math.min(contextMenu.y,window.innerHeight-160)}} role="menu" aria-label="Ações do canvas">{contextMenu.id&&<><button type="button" role="menuitem" disabled={readOnly||fullNavigation} onClick={()=>{onDuplicateSelection(contextMenu.id);setContextMenu(null);}}>Duplicar nó</button><button type="button" role="menuitem" disabled={readOnly||fullNavigation} onClick={()=>{const id=contextMenu.id;setConfig(current=>syncGroups({...current,nodes:current.nodes.filter(node=>node.id!==id),edges:current.edges.filter(edge=>edge.from!==id&&edge.to!==id)}));setContextMenu(null);}}>Remover do fluxo</button></>}<button type="button" role="menuitem" onClick={()=>{instance?.fitView({padding:.15,duration:200});setContextMenu(null);}}>Ajustar à tela</button></div>}</>;
}

export function FlowCanvas(props) {
  return <div className="reports-flow-canvas flow-react-canvas" role="region" aria-label="Mapa visual do fluxo"><ReactFlowProvider><FlowCanvasInner {...props}/></ReactFlowProvider></div>;
}
