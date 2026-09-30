import {FLOW_STAGES,stageFor,stageAtX,stageX,funnelEdges,FLOW_STAGE_WIDTH} from './flowStages.js';
import {useFlowPreviews} from './useFlowPreviews.js';
import {RefreshCw01, Copy01, Trash01, LayoutGrid01, LayersTwo01} from '@untitledui/icons';
import React, {useEffect, useCallback, useMemo, useRef, useState} from 'react';
import {ReactFlow, useNodesInitialized, useReactFlow, useUpdateNodeInternals, Background, BackgroundVariant, BaseEdge, EdgeLabelRenderer, Handle, MarkerType, MiniMap, Controls, ControlButton, NodeToolbar, NodeResizer, useViewport, Position, ReactFlowProvider, getSmoothStepPath} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import {flowBlockFor} from './flowBlockRegistry.js';
import {FLOW_PLATFORMS, FlowPlatformLogo} from './FlowPlatformLogo.jsx';
import './flow-canvas.css';
import {FlowEdgeActivity} from './FlowEdgeActivity.jsx';
import {ungroupNodes,syncGroups} from './flowGroups.js';
import {ReportsActionButton} from './ReportsActionButton.jsx';


function FitLoadedGraph({enabled}) {
  const initialized=useNodesInitialized();
  const api=useReactFlow();
  const fitted=useRef(false);
  useEffect(()=>{
    if(!enabled||!initialized||fitted.current)return;
    const timer=setTimeout(()=>{const visible=api.getNodes().filter(n=>!n.hidden);if(!visible.length||visible.some(n=>!n.measured?.width))return;api.fitView({padding:.2,maxZoom:1});fitted.current=true;},100);
    return()=>clearTimeout(timer);
  },[enabled,initialized,api]);
  return null;
}

function FlowLanes(){
  const {x,zoom}=useViewport();
  return <div className="flow-lanes" aria-hidden="true">{FLOW_STAGES.map((stage,index)=><div key={stage.id} style={{left:x+(48+index*FLOW_STAGE_WIDTH)*zoom,width:FLOW_STAGE_WIDTH*zoom}}><span>{stage.label}</span></div>)}</div>;
}

function NodeLabel({node, selected, readOnly, onChange}) {
  const [editing,setEditing]=useState(false);
  const [draft,setDraft]=useState(node.title||'');
  const inputRef=useRef(null);
  const begin=()=>{if(readOnly)return;setDraft(node.title||'');setEditing(true);requestAnimationFrame(()=>inputRef.current?.select());};
  const finish=save=>{if(save)onChange(node.id,(draft.trim()||node.title||node.type).slice(0,60));setEditing(false);};
  return <div className="flow-shape-label" onDoubleClick={begin} onKeyDown={event=>{if(!editing&&(event.key==='Enter'||event.key==='F2')){event.preventDefault();begin();}}}>
    {editing?<input ref={inputRef} className="nodrag" aria-label="Editar nome da etapa" value={draft} onChange={event=>setDraft(event.target.value)} onBlur={()=>finish(true)} onKeyDown={event=>{if(event.key==='Enter'){event.preventDefault();finish(true);}if(event.key==='Escape'){event.stopPropagation();finish(false);}}}/> : <span tabIndex={selected&&!readOnly?0:-1} aria-label={`${node.title||node.type}. Pressione Enter para renomear`}>{node.title||node.type}</span>}
  </div>;
}

function NodeHandles() {
  return <><Handle id="left-in" type="target" position={Position.Left}/><Handle id="top-in" type="target" position={Position.Top}/><Handle id="right-out" type="source" position={Position.Right}/><Handle id="bottom-out" type="source" position={Position.Bottom}/></>;
}

function ShapeNode({id,data,selected,shape}) {
  const updateInternals=useUpdateNodeInternals();
  useEffect(()=>{updateInternals(id);},[id,data.node.title,shape,updateInternals]);
  const {node,readOnly,onLabelChange,metric,onDuplicate,onRemove,preview,onRegenerate,canCapture}=data;
  const {zoom}=useViewport();
  const [brokenImage,setBrokenImage]=useState(null);
  const [hovered,setHovered]=useState(false);
  const block=flowBlockFor(node);
  const Icon=block.icon;
  return <div onMouseEnter={()=>setHovered(true)} onMouseLeave={()=>setHovered(false)} title={`${node.title||node.type}\n${node.host||''}${node.path||''}\n${node.role||stageFor(node)} · ${node.role_source||'usuário'}${node.evidence?`\n${node.evidence}`:''}`} className={`flow-shape-node is-${shape} is-tone-${block.tone}${zoom<.65?' is-compact-zoom':''}${selected?' is-selected':''}`}>
    <NodeToolbar className="flow-node-hover" isVisible={hovered&&!selected} position={Position.Bottom}><strong>{node.title}</strong><small>{node.host}{node.path}</small><small>{node.role||stageFor(node)} · {node.role_source||'usuário'}</small>{node.evidence&&<p>{node.evidence}</p>}{metric&&<small>{metric.sessions==null?'Sessões não disponíveis':`${metric.sessions} sessões no período`}</small>}{data.paths?.map(path=><small key={path.id}>{path.label} · {path.sessions} sessões</small>)}</NodeToolbar>
    <NodeToolbar isVisible={selected&&!readOnly} position={Position.Top}><ReportsActionButton aria-label="Duplicar etapa" title="Duplicar etapa" onClick={()=>onDuplicate(node.id)}><Copy01 size={16}/></ReportsActionButton><ReportsActionButton aria-label="Excluir etapa" title="Excluir etapa" onClick={()=>onRemove(node.id)}><Trash01 size={16}/></ReportsActionButton>{shape==='page'&&canCapture&&<ReportsActionButton aria-label="Atualizar captura da página" title="Atualizar captura da página" onClick={()=>onRegenerate(node.id)}><RefreshCw01 size={16}/></ReportsActionButton>}</NodeToolbar><NodeLabel node={node} selected={selected} readOnly={readOnly} onChange={onLabelChange}/>
    <div className="flow-shape-body">{shape==='page'&&zoom>=.4&&preview?.url&&brokenImage!==preview.url?<img className="flow-page-capture" src={preview.canvas_url||preview.url} alt="" loading="lazy" decoding="async" onLoad={()=>updateInternals(id)} onError={()=>setBrokenImage(preview.url)}/>:shape==='page'?<div className={`flow-page-preview is-${block.preview||'generic'}`}><div className="flow-page-preview__bar"><i/><i/><i/></div><div className="flow-page-preview__image"/><div className="flow-page-preview__line"/><div className="flow-page-preview__line is-short"/></div>:node.type==='source'&&FLOW_PLATFORMS[block.source||node.source]?<FlowPlatformLogo platform={block.source||node.source}/>:<Icon size={22}/>}<NodeHandles/></div>
    {node.path&&!node.path.startsWith('/configurar-')&&<small>{node.path}</small>}
    {block.trackable&&(!node.path||node.path.startsWith('/configurar-'))&&<span className="flow-shape-warning" title="Configure a URL real desta etapa">!</span>}
    {metric&&<span className="flow-journey-count">{metric.sessions==null?(node.type==='source'?'Sem vínculo':'Não disponível'):`${Number(metric.sessions).toLocaleString('pt-BR')} sessões`}</span>}{metric?.presence!=null&&<small className="flow-presence">{metric.presence} sessões agora</small>}{shape==='visual'&&<small>Etapa visual · não medida</small>}
  </div>;
}

function GroupNode({id,data,selected}) {
  const update=useUpdateNodeInternals();
  useEffect(()=>{update(id);},[id,data.collapsed,update]);
  if(data.collapsed)return <div className="flow-group-stack" onDoubleClick={data.toggle}><strong>{data.group.name}</strong><small>{data.group.memberIds.length} páginas</small>{data.metric&&<small>{Number(data.metric.sessions).toLocaleString('pt-BR')} sessões únicas</small>}<NodeHandles/><button className="nodrag" onClick={data.toggle}>Ver páginas</button>{!data.readOnly&&<button className="nodrag" onClick={()=>data.ungroup(id)}>Separar páginas</button>}</div>;
  return <div className="flow-group-node"><NodeResizer isVisible={selected&&!data.readOnly} minWidth={220} minHeight={180} onResizeEnd={(_,size)=>data.resize(id,size)}/><strong>{data.group.name}</strong><small>{data.group.memberIds.length} etapas</small><button className="nodrag" onClick={data.toggle}>Recolher</button><NodeToolbar isVisible={selected&&!data.readOnly}><ReportsActionButton onClick={()=>data.ungroup(id)}>Desagrupar</ReportsActionButton></NodeToolbar></div>;
}

const MemoShapeNode=React.memo(ShapeNode);
const nodeTypes = {
  groupFrame:GroupNode,
  visual:props=><MemoShapeNode {...props} shape="visual"/>,
  circle:props=><MemoShapeNode {...props} shape="circle"/>,
  diamond:props=><MemoShapeNode {...props} shape="diamond"/>,
  page:props=><MemoShapeNode {...props} shape="page"/>,
};

function FlowEdge({id,sourceX,sourceY,targetX,targetY,sourcePosition,targetPosition,markerEnd,markerStart,style,data,label,selected}) {
  const [hovered,setHovered]=useState(false);
  const [path,labelX,labelY]=getSmoothStepPath({sourceX,sourceY,targetX,targetY,sourcePosition,targetPosition});
  return <><BaseEdge id={id} path={path} markerEnd={markerEnd} markerStart={markerStart} style={style}/><FlowEdgeActivity path={path} operational={data.operational} transitionId={data.transitionId} ready={data.liveReady} scope={data.liveScope}/><path d={path} fill="none" stroke="transparent" strokeWidth="20" onMouseEnter={()=>setHovered(true)} onMouseLeave={()=>setHovered(false)}/><EdgeLabelRenderer><div className={`flow-edge-actions nodrag nopan${hovered||selected||data.hasMetric?' is-visible':''}`} style={{transform:`translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`}} onMouseEnter={()=>setHovered(true)} onMouseLeave={()=>setHovered(false)}><span onClick={()=>data.onInspect?.(id)}>{label}</span>{!data.readOnly&&<><button type="button" aria-label="Inserir etapa nesta conexão" onClick={()=>data.onInsert(id)}>+</button><button type="button" aria-label="Remover conexão" onClick={()=>data.onRemove(id)}>×</button></>}</div></EdgeLabelRenderer></>;
}

const edgeTypes={flow:FlowEdge};

function FlowCanvasInner({onNavigationModeChange,ghostEdges=[],ghostNodes=[],config,setConfig,selectedNodeId,setSelectedNodeId,onSelectedIdsChange=()=>{},onAddNode,onInsertEdge,onDuplicateSelection,readOnly,simulatedPath=[],journey=null,snapToGrid,onReady=()=>{},onZoomChange=()=>{},onSelectedEdge,onOrganize,live=null,liveScope='',operational=false,fitOnMount=false,onGestureStart=()=>{},onGestureEnd=()=>{},previewContext} ) {
  const previews=useFlowPreviews(previewContext);
  const [fullNavigation,setFullNavigation]=useState(false);
  useEffect(()=>{onNavigationModeChange?.(fullNavigation);},[fullNavigation,onNavigationModeChange]);
  const [showReturns,setShowReturns]=useState(false);
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
  const nodes=useMemo(()=>{
    const groups=config.groups||[];
    const parents=groups.map(group=>({id:group.id,type:'groupFrame',position:{x:group.bounds.x,y:group.bounds.y},style:{width:expandedGroups.has(group.id)?group.bounds.width:180,height:expandedGroups.has(group.id)?group.bounds.height:130},data:{group,metric:journey?.group_nodes?.find(n=>n.id===group.id),collapsed:!expandedGroups.has(group.id),toggle:()=>setExpandedGroups(current=>{const next=new Set(current);next.has(group.id)?next.delete(group.id):next.add(group.id);return next;}),readOnly:readOnly||fullNavigation,ungroup:id=>setConfig(current=>ungroupNodes(current,id)),resize:(id,size)=>setConfig(current=>({...current,groups:current.groups.map(g=>g.id===id?{...g,bounds:{x:size.x,y:size.y,width:size.width,height:size.height}}:g)}))},draggable:!readOnly&&!fullNavigation&&!config.nodes.some(n=>group.memberIds.includes(n.id)&&n.locked),selectable:true}));
    const items=(config.nodes||[]).map(node=>{
      const parent=groups.find(g=>g.id===node.groupId);
      return {id:node.id,hidden:Boolean(parent&&!expandedGroups.has(parent.id)),measured:measurements[node.id],type:flowBlockFor(node).shape,parentId:parent?.id,extent:parent?'parent':undefined,
        className:simulatedPath.includes(node.id)?'is-simulated':'',position:{x:(node.stage&&!parent?stageX(stageFor(node)):(Number(node.x)||0))-(parent?.bounds.x||0),y:(Number(node.y)||0)-(parent?.bounds.y||0)},
        data:{node,paths:journey?.edges?.filter(e=>(e.from===node.id||e.to===node.id)&&e.sessions>0).sort((a,b)=>b.sessions-a.sessions).slice(0,3).map(e=>({id:e.id,sessions:e.sessions,label:`${e.to===node.id?'De':'Para'} ${config.nodes.find(n=>n.id===(e.to===node.id?e.from:e.to))?.title||'etapa'}`})),preview:{...previews.items[node.id],message:previews.error||previews.items[node.id]?.message,unavailable:!previews.available},onRegenerate:previews.regenerate,canCapture:previewContext?.canCapture&&previews.available,readOnly:readOnly||fullNavigation,onLabelChange,onDuplicate:onDuplicateSelection,onRemove:id=>setConfig(current=>syncGroups({...current,nodes:current.nodes.filter(n=>n.id!==id),edges:current.edges.filter(e=>e.from!==id&&e.to!==id)})),metric:journey?.nodes?.find(item=>item.id===node.id)},draggable:!readOnly&&!fullNavigation&&!node.locked,selectable:true,selected:selectedIds.length?selectedIds.includes(node.id):node.id===selectedNodeId};
    });return [...parents,...items,...ghostNodes.map(node=>({id:`ghost:${node.id}`,type:flowBlockFor(node).shape,position:{x:node.x,y:node.y},className:"flow-ghost-node",data:{node,readOnly:true},draggable:false,selectable:false}))];
  },[config,ghostNodes,expandedGroups,readOnly,onLabelChange,selectedNodeId,selectedIds,simulatedPath,journey,onDuplicateSelection,setConfig,measurements,fullNavigation,previews.items,previews.regenerate,previews.available,previews.error,previewContext?.canCapture]);
  const removeEdge=useCallback(id=>setConfig(current=>({...current,edges:current.edges.filter(edge=>edge.id!==id)})),[setConfig]);
  const edges=useMemo(()=>{
    const memberGroup=new Map((config.groups||[]).filter(g=>!expandedGroups.has(g.id)).flatMap(g=>g.memberIds.map(id=>[id,g.id])));
    const renderedPairs=new Set();
    const projected={...config,nodes:[...config.nodes,...(config.groups||[]).map(g=>({id:g.id,stage:stageFor(config.nodes.find(n=>g.memberIds.includes(n.id))||{})}))],edges:config.edges.map(e=>({...e,from:memberGroup.get(e.from)||e.from,to:memberGroup.get(e.to)||e.to})).filter(e=>{const key=`${e.from}:${e.to}`;if(e.from===e.to||renderedPairs.has(key))return false;renderedPairs.add(key);return true;})};
    const authored=funnelEdges(projected,{full:fullNavigation,returns:showReturns,metrics:journey?.edges}).map(edge=>{const planned=edge.variant==='planned'||edge.kind==='site_link';const simulated=simulatedPath.some((id,index)=>id===edge.from&&simulatedPath[index+1]===edge.to);const metric=memberGroup.has((config.edges||[]).find(e=>e.id===edge.id)?.from)||memberGroup.has((config.edges||[]).find(e=>e.id===edge.id)?.to)?(expandedGroups.size?null:journey?.group_edges?.find(item=>item.from===edge.from&&item.to===edge.to)):journey?.edges?.find(item=>item.id===edge.id);const color=simulated?'var(--color-fg-success-primary)':planned?'var(--color-fg-quaternary)':'var(--color-fg-brand-primary)';return {reconnectable:!readOnly&&!fullNavigation&&!memberGroup.has((config.edges||[]).find(e=>e.id===edge.id)?.from)&&!memberGroup.has((config.edges||[]).find(e=>e.id===edge.id)?.to),id:edge.id,source:edge.from,target:edge.to,label:metric?`${metric.sessions==null?'Não disponível':Number(metric.sessions).toLocaleString('pt-BR')} · ${metric.rate==null?'Taxa indisponível':`${metric.rate}%`}`:edge.label==='Próximo'?undefined:edge.label,sourceHandle:edge.from_port||'right-out',targetHandle:edge.to_port||'left-in',type:'flow',animated:simulated,style:{strokeWidth:metric?Math.min(5,1.5+Math.log10(Number(metric.sessions||0)+1)):simulated?3:2,stroke:color,strokeDasharray:planned&&!simulated?'6 6':undefined},markerEnd:{type:MarkerType.ArrowClosed,color},markerStart:edge.reverseId?{type:MarkerType.ArrowClosed,color}:undefined,data:{readOnly:readOnly||fullNavigation||memberGroup.has((config.edges||[]).find(e=>e.id===edge.id)?.from)||memberGroup.has((config.edges||[]).find(e=>e.id===edge.id)?.to),onRemove:removeEdge,onInsert:onInsertEdge,hasMetric:Boolean(metric),aggregate:memberGroup.has((config.edges||[]).find(e=>e.id===edge.id)?.from)||memberGroup.has((config.edges||[]).find(e=>e.id===edge.id)?.to),onInspect:(memberGroup.has((config.edges||[]).find(e=>e.id===edge.id)?.from)||memberGroup.has((config.edges||[]).find(e=>e.id===edge.id)?.to))?undefined:onSelectedEdge,liveReady:live?.status==='ready',liveScope,transitionId:live?.transitions?.[edge.id],operational:operational&&Date.now()-Date.parse(live?.edge_activity?.[edge.id])<90000&&edge.variant!=='planned'&&edge.kind!=='site_link'}};});
    authored.push(...ghostEdges.map(e=>({id:`ghost:${e.id}`,source:`ghost:${e.from}`,target:`ghost:${e.to}`,sourceHandle:'right-out',targetHandle:'left-in',type:'flow',style:{stroke:'var(--color-fg-brand-primary)',strokeWidth:1.5,strokeDasharray:'5 5',opacity:.4},data:{readOnly:true}})));
    if(!fullNavigation||!journey?.suggestions?.length)return authored;
    const ids=new Set((config.nodes||[]).map(node=>node.id));
    const suggestions=journey.suggestions.filter(item=>ids.has(item.from)&&ids.has(item.to)).map(item=>({id:`suggested:${item.from}:${item.to}`,source:item.from,target:item.to,type:'flow',label:`Sugerido · ${Number(item.sessions).toLocaleString('pt-BR')}`,style:{strokeWidth:2,stroke:'var(--color-fg-quaternary)',strokeDasharray:'3 6'},markerEnd:{type:MarkerType.ArrowClosed,color:'var(--color-fg-quaternary)'},data:{readOnly:true}}));
    return [...authored,...suggestions];
  },[ghostEdges,config.edges,config.nodes,config.groups,expandedGroups,fullNavigation,showReturns,readOnly,removeEdge,onInsertEdge,simulatedPath,journey,live,liveScope,operational,onSelectedEdge]);
  const onNodesChange=useCallback(changes=>{
    const dimensions=changes.filter(c=>c.type==='dimensions'&&c.dimensions);
    if(dimensions.length)setMeasurements(current=>{const next={...current};let changed=false;for(const c of dimensions){if(current[c.id]?.width!==c.dimensions.width||current[c.id]?.height!==c.dimensions.height){next[c.id]=c.dimensions;changed=true;}}return changed?next:current;});
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
        return {...node,...(groupMoved?{manuallyEdited:true}:{}),...(move?{manuallyEdited:true,stage:node.type==='source'?'source':stageAtX(x)}:{}),groupId:parent?.id,x:move?stageX(node.type==='source'?'source':stageAtX(x)):Math.max(0,Math.min(10000,Math.round(x))),y:Math.max(0,Math.min(10000,Math.round(y)))};
      }),edges:current.edges.filter(e=>!removed.has(e.from)&&!removed.has(e.to))});
    });
  },[setConfig,readOnly,fullNavigation]);
  const commitDrag=useCallback(()=>{
    const moved=new Map(pendingPositions.current),removed=new Set();
    if(moved.size){
    setConfig(current=>{
      const groups=(current.groups||[]).filter(g=>!removed.has(g.id)).map(g=>({...g,bounds:{...g.bounds,...moved.get(g.id)}}));
      return syncGroups({...current,groups,nodes:current.nodes.filter(n=>!removed.has(n.id)).map(node=>{
        const oldParent=(current.groups||[]).find(g=>g.id===node.groupId),parent=groups.find(g=>g.id===node.groupId),move=moved.get(node.id),groupMoved=Boolean(parent&&moved.has(parent.id));
        const x=move?move.x+(parent?.bounds.x||0):Number(node.x)+(parent&&oldParent?parent.bounds.x-oldParent.bounds.x:0);
        const y=move?move.y+(parent?.bounds.y||0):Number(node.y)+(parent&&oldParent?parent.bounds.y-oldParent.bounds.y:0);
        return {...node,...(groupMoved?{manuallyEdited:true}:{}),...(move?{manuallyEdited:true,stage:node.type==='source'?'source':stageAtX(x)}:{}),groupId:parent?.id,x:move?stageX(node.type==='source'?'source':stageAtX(x)):Math.max(0,Math.min(10000,Math.round(x))),y:Math.max(0,Math.min(10000,Math.round(y)))};
      }),edges:current.edges.filter(e=>!removed.has(e.from)&&!removed.has(e.to))});
    });
    }
    pendingPositions.current.clear();setDragPositions({});onGestureEnd();
  },[setConfig,onGestureEnd]);
  const onEdgesChange=useCallback(changes=>{const removed=new Set(changes.filter(change=>change.type==='remove').map(change=>change.id));if(removed.size)setConfig(current=>({...current,edges:current.edges.filter(edge=>!removed.has(edge.id))}));},[setConfig]);
  const onConnect=useCallback(connection=>{if(readOnly||fullNavigation||!connection.source||!connection.target||connection.source===connection.target)return;setConfig(current=>{if(current.edges.some(edge=>edge.from===connection.source&&edge.to===connection.target)||current.edges.length>=300)return current;const sourceNode=current.nodes.find(node=>node.id===connection.source);return {...current,edges:[...current.edges,{id:crypto.randomUUID(),from:connection.source,to:connection.target,from_port:connection.sourceHandle||'right-out',to_port:connection.targetHandle||'left-in',variant:sourceNode?.type==='source'?'planned':'direct',label:'Próximo'}]};});},[readOnly,fullNavigation,setConfig]);
  const onDrop=useCallback(event=>{event.preventDefault();if(readOnly||fullNavigation||!instance)return;try{const item=JSON.parse(event.dataTransfer.getData('application/x-cadu-flow-node'));onAddNode(item,instance.screenToFlowPosition({x:event.clientX,y:event.clientY}));}catch(_){/* A drag from outside the palette is ignored. */}},[instance,onAddNode,readOnly,fullNavigation]);
  const insertConnected=item=>{if(!quickAdd||!instance)return;onAddNode(item,instance.screenToFlowPosition(quickAdd.screen),quickAdd.source);setQuickAdd(null);};
  return <><div className="flow-view-policy">{!fullNavigation&&config.edges.length>edges.length&&<small title="Conexões preservadas na navegação completa">+{config.edges.length-edges.length} ocultas</small>}<button type="button" aria-pressed={!fullNavigation} onClick={()=>setFullNavigation(false)}>Funil</button><button type="button" aria-pressed={fullNavigation} onClick={()=>setFullNavigation(true)}>Navegação completa</button><label><input type="checkbox" checked={showReturns} onChange={e=>setShowReturns(e.target.checked)}/>Mostrar retornos</label></div><ReactFlow nodes={nodes.map(node=>dragPositions[node.id]?{...node,position:dragPositions[node.id]}:node)} edges={edges} onlyRenderVisibleElements={nodes.length>=80} nodeTypes={nodeTypes} edgeTypes={edgeTypes} onNodesChange={onNodesChange} onNodeDragStart={onGestureStart} onNodeDragStop={commitDrag} onSelectionDragStart={onGestureStart} onSelectionDragStop={commitDrag} onEdgesChange={readOnly||fullNavigation?undefined:onEdgesChange} onEdgeClick={(_,edge)=>{if(!edge.data?.aggregate)onSelectedEdge?.(edge.id);}} onReconnect={(old,connection)=>{if(readOnly||fullNavigation||old.data?.aggregate||!connection.source||!connection.target||connection.source===connection.target||!config.nodes.some(n=>n.id===connection.source)||!config.nodes.some(n=>n.id===connection.target))return;setConfig(current=>current.edges.some(e=>e.id!==old.id&&e.from===connection.source&&e.to===connection.target)?current:{...current,edges:current.edges.map(e=>e.id===old.id?{...e,origin:'manual',from:connection.source,to:connection.target,from_port:connection.sourceHandle||'right-out',to_port:connection.targetHandle||'left-in'}:e)});}} edgesReconnectable={!readOnly&&!fullNavigation} onConnect={onConnect} onConnectEnd={(event,state)=>{if(readOnly||fullNavigation||state.isValid||!state.fromNode)return;setQuickAdd({source:state.fromNode.id,screen:{x:event.clientX,y:event.clientY}});}} onSelectionChange={({nodes:items})=>{const ids=items.map(item=>item.id);const key=ids.join('|');if(selectionRef.current===key)return;selectionRef.current=key;setSelectedIds(previous=>previous.join('|')===ids.join('|')?previous:ids);onSelectedIdsChange(ids);if(ids.length===1)setSelectedNodeId(ids[0]);}} onNodeClick={(_,node)=>setSelectedNodeId(node.id)} onNodeContextMenu={(event,node)=>{event.preventDefault();setSelectedNodeId(node.id);setContextMenu({x:event.clientX,y:event.clientY,id:node.id});}} onPaneContextMenu={event=>{event.preventDefault();setContextMenu({x:event.clientX,y:event.clientY,id:null});}} onPaneClick={()=>{setSelectedNodeId('');setQuickAdd(null);setContextMenu(null);}} onInit={flow=>{setInstance(flow);onReady({...flow,toggleReturns:()=>setShowReturns(v=>!v),toggleNavigation:()=>setFullNavigation(v=>!v)});}} onMoveEnd={(_,viewport)=>onZoomChange(viewport.zoom)} onDragOver={event=>event.preventDefault()} onDrop={onDrop} nodesDraggable={!readOnly&&!fullNavigation} nodesConnectable={!readOnly&&!fullNavigation} elementsSelectable={true} selectionOnDrag={!readOnly} panOnDrag={readOnly?true:[1,2]} multiSelectionKeyCode="Shift" minZoom={0.1} maxZoom={2} defaultViewport={{x:80,y:80,zoom:1}} snapToGrid={snapToGrid&&!altPressed} snapGrid={[12,12]} fitView={fitOnMount} fitViewOptions={{padding:.2,maxZoom:1}} deleteKeyCode={readOnly||fullNavigation?null:['Backspace','Delete']} attributionPosition="bottom-right"><Controls fitViewOptions={{padding:.2,maxZoom:1}} showInteractive={false} position="bottom-left">{onOrganize&&<ControlButton title="Organizar da esquerda para a direita" aria-label="Organizar fluxo" onClick={onOrganize}><LayoutGrid01 size={16}/></ControlButton>}<ControlButton title="Alternar minimapa" aria-label="Alternar minimapa" onClick={()=>setShowMiniMap(v=>!v)}><LayersTwo01 size={16}/></ControlButton></Controls><FitLoadedGraph enabled={fitOnMount}/>{config.layoutMode!=='free'&&config.nodes.some(n=>n.stage)&&<FlowLanes/>}<Background variant={BackgroundVariant.Dots} gap={24} size={1} color="var(--color-border-secondary)"/>{showMiniMap&&<MiniMap style={{width:150,height:95}} pannable zoomable nodeColor={n=>({source:"#6172f3",entry:"#1570ef",exploration:"#06aed4",intent:"#f79009",conversion:"#17b26a",support:"#98a2b3"}[stageFor(n.data.node||{})])}/>}</ReactFlow>{quickAdd&&<div className="flow-quick-add" style={{left:Math.min(quickAdd.screen.x,window.innerWidth-180),top:Math.min(quickAdd.screen.y,window.innerHeight-160)}} role="dialog" aria-label="Adicionar etapa conectada"><strong>Adicionar etapa</strong>{[{type:'page',label:'Página'},{type:'form',label:'Formulário'},{type:'conversion',label:'Conversão'}].map(item=><button key={item.type} type="button" onClick={()=>insertConnected(item)}>{item.label}</button>)}<button type="button" onClick={()=>setQuickAdd(null)}>Cancelar</button></div>}{contextMenu&&<div className="flow-quick-add" style={{left:Math.min(contextMenu.x,window.innerWidth-180),top:Math.min(contextMenu.y,window.innerHeight-160)}} role="menu" aria-label="Ações do canvas">{contextMenu.id&&<><button type="button" role="menuitem" disabled={readOnly||fullNavigation} onClick={()=>{onDuplicateSelection(contextMenu.id);setContextMenu(null);}}>Duplicar etapa</button><button type="button" role="menuitem" disabled={readOnly||fullNavigation} onClick={()=>{const id=contextMenu.id;setConfig(current=>syncGroups({...current,nodes:current.nodes.filter(node=>node.id!==id),edges:current.edges.filter(edge=>edge.from!==id&&edge.to!==id)}));setContextMenu(null);}}>Excluir etapa</button></>}<button type="button" role="menuitem" onClick={()=>{instance?.fitView({padding:.15,duration:200});setContextMenu(null);}}>Ajustar à tela</button></div>}</>;
}

export function FlowCanvas(props) {
  return <div className="reports-flow-canvas flow-react-canvas" role="region" aria-label="Mapa visual do fluxo"><ReactFlowProvider><FlowCanvasInner {...props}/></ReactFlowProvider></div>;
}
