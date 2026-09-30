import React, {useCallback, useMemo, useRef, useState} from 'react';
import {ReactFlow, Background, BackgroundVariant, BaseEdge, EdgeLabelRenderer, Handle, MarkerType, MiniMap, Controls, ControlButton, NodeToolbar, NodeResizer, useViewport, Position, ReactFlowProvider, getBezierPath} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import {flowBlockFor} from './flowBlockRegistry.js';
import {FLOW_PLATFORMS, FlowPlatformLogo} from './FlowPlatformLogo.jsx';
import './flow-canvas.css';
import {FlowEdgeActivity} from './FlowEdgeActivity.jsx';
import {ungroupNodes,syncGroups} from './flowGroups.js';
import {ReportsActionButton} from './ReportsActionButton.jsx';


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

function ShapeNode({data,selected,shape}) {
  const {node,readOnly,onLabelChange,metric,onDuplicate,onRemove}=data;
  const {zoom}=useViewport();
  const block=flowBlockFor(node);
  const Icon=block.icon;
  return <div className={`flow-shape-node is-${shape} is-tone-${block.tone}${zoom<.65?' is-compact-zoom':''}${selected?' is-selected':''}`}>
    <NodeToolbar isVisible={selected&&!readOnly} position={Position.Top}><ReportsActionButton onClick={()=>onDuplicate(node.id)}>Duplicar</ReportsActionButton><ReportsActionButton onClick={()=>onRemove(node.id)}>Excluir</ReportsActionButton></NodeToolbar><NodeLabel node={node} selected={selected} readOnly={readOnly} onChange={onLabelChange}/>
    <div className="flow-shape-body" aria-hidden="true">{shape==='page'?<div className={`flow-page-preview is-${block.preview||'generic'}`}><div className="flow-page-preview__bar"><i/><i/><i/></div><div className="flow-page-preview__image"/><div className="flow-page-preview__line"/><div className="flow-page-preview__line is-short"/></div>:node.type==='source'&&FLOW_PLATFORMS[block.source||node.source]?<FlowPlatformLogo platform={block.source||node.source}/>:<Icon size={22}/>}</div>
    {node.path&&!node.path.startsWith('/configurar-')&&<small>{node.path}</small>}
    {block.trackable&&(!node.path||node.path.startsWith('/configurar-'))&&<span className="flow-shape-warning" title="Configure a URL real desta etapa">!</span>}
    {metric&&<span className="flow-journey-count">{metric.sessions==null?(node.type==='source'?'Sem vínculo':'Não disponível'):`${Number(metric.sessions).toLocaleString('pt-BR')} sessões`}</span>}{metric?.presence!=null&&<small className="flow-presence">{metric.presence} sessões agora</small>}{shape==='page'&&<small className="flow-preview-caption">Prévia ilustrativa</small>}{shape==='visual'&&<small>Etapa visual · não medida</small>}
    <NodeHandles/>
  </div>;
}

function GroupNode({id,data,selected}) {
  return <div className="flow-group-node"><NodeResizer isVisible={selected&&!data.readOnly} minWidth={220} minHeight={180} onResizeEnd={(_,size)=>data.resize(id,size)}/><strong>{data.group.name}</strong><small>{data.group.memberIds.length} etapas</small><NodeToolbar isVisible={selected&&!data.readOnly}><ReportsActionButton onClick={()=>data.ungroup(id)}>Desagrupar</ReportsActionButton></NodeToolbar></div>;
}

const nodeTypes = {
  groupFrame:GroupNode,
  visual:props=><ShapeNode {...props} shape="visual"/>,
  circle:props=><ShapeNode {...props} shape="circle"/>,
  diamond:props=><ShapeNode {...props} shape="diamond"/>,
  page:props=><ShapeNode {...props} shape="page"/>,
};

function FlowEdge({id,sourceX,sourceY,targetX,targetY,sourcePosition,targetPosition,markerEnd,style,data,label,selected}) {
  const [hovered,setHovered]=useState(false);
  const [path,labelX,labelY]=getBezierPath({sourceX,sourceY,targetX,targetY,sourcePosition,targetPosition});
  return <><BaseEdge id={id} path={path} markerEnd={markerEnd} style={style}/><FlowEdgeActivity path={path} operational={data.operational} transitionId={data.transitionId} ready={data.liveReady} scope={data.liveScope}/><path d={path} fill="none" stroke="transparent" strokeWidth="20" onMouseEnter={()=>setHovered(true)} onMouseLeave={()=>setHovered(false)}/><EdgeLabelRenderer><div className={`flow-edge-actions nodrag nopan${hovered||selected||data.hasMetric?' is-visible':''}`} style={{transform:`translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`}} onMouseEnter={()=>setHovered(true)} onMouseLeave={()=>setHovered(false)}><span onClick={()=>data.onInspect?.(id)}>{label}</span>{!data.readOnly&&<><button type="button" aria-label="Inserir etapa nesta conexão" onClick={()=>data.onInsert(id)}>+</button><button type="button" aria-label="Remover conexão" onClick={()=>data.onRemove(id)}>×</button></>}</div></EdgeLabelRenderer></>;
}

const edgeTypes={flow:FlowEdge};

function FlowCanvasInner({config,setConfig,selectedNodeId,setSelectedNodeId,onSelectedIdsChange=()=>{},onAddNode,onInsertEdge,onDuplicateSelection,readOnly,simulatedPath=[],journey=null,snapToGrid,onReady=()=>{},onZoomChange=()=>{},onSelectedEdge,onOrganize,live=null,liveScope='',operational=false,fitOnMount=false,onGestureStart=()=>{},onGestureEnd=()=>{}}) {
  const [instance,setInstance]=useState(null);
  const [measurements,setMeasurements]=useState({});
  const [selectedIds,setSelectedIds]=useState([]);
  const [showMiniMap,setShowMiniMap]=useState(true);
  const [quickAdd,setQuickAdd]=useState(null);
  const [contextMenu,setContextMenu]=useState(null);
  const onLabelChange=useCallback((id,title)=>setConfig(current=>({...current,nodes:current.nodes.map(node=>node.id===id?{...node,title}:node)})),[setConfig]);
  const nodes=useMemo(()=>{
    const groups=config.groups||[];
    const parents=groups.map(group=>({id:group.id,type:'groupFrame',position:{x:group.bounds.x,y:group.bounds.y},style:{width:group.bounds.width,height:group.bounds.height},data:{group,readOnly,ungroup:id=>setConfig(current=>ungroupNodes(current,id)),resize:(id,size)=>setConfig(current=>({...current,groups:current.groups.map(g=>g.id===id?{...g,bounds:{x:size.x,y:size.y,width:size.width,height:size.height}}:g)}))},draggable:!readOnly,selectable:true}));
    const items=(config.nodes||[]).map(node=>{
      const parent=groups.find(g=>g.id===node.groupId);
      return {id:node.id,measured:measurements[node.id],type:flowBlockFor(node).shape,parentId:parent?.id,extent:parent?'parent':undefined,
        className:simulatedPath.includes(node.id)?'is-simulated':'',position:{x:(Number(node.x)||0)-(parent?.bounds.x||0),y:(Number(node.y)||0)-(parent?.bounds.y||0)},
        data:{node,readOnly,onLabelChange,onDuplicate:onDuplicateSelection,onRemove:id=>setConfig(current=>syncGroups({...current,nodes:current.nodes.filter(n=>n.id!==id),edges:current.edges.filter(e=>e.from!==id&&e.to!==id)})),metric:journey?.nodes?.find(item=>item.id===node.id)},draggable:!readOnly,selectable:true,selected:selectedIds.length?selectedIds.includes(node.id):node.id===selectedNodeId};
    });return [...parents,...items];
  },[config,readOnly,onLabelChange,selectedNodeId,selectedIds,simulatedPath,journey,onDuplicateSelection,setConfig,measurements]);
  const removeEdge=useCallback(id=>setConfig(current=>({...current,edges:current.edges.filter(edge=>edge.id!==id)})),[setConfig]);
  const edges=useMemo(()=>{
    const authored=(config.edges||[]).map(edge=>{const planned=edge.variant==='planned'||edge.kind==='site_link';const simulated=simulatedPath.some((id,index)=>id===edge.from&&simulatedPath[index+1]===edge.to);const metric=journey?.edges?.find(item=>item.id===edge.id);const color=simulated?'var(--color-fg-success-primary)':planned?'var(--color-fg-quaternary)':'var(--color-fg-brand-primary)';return {id:edge.id,source:edge.from,target:edge.to,label:metric?`${metric.sessions==null?'Não disponível':Number(metric.sessions).toLocaleString('pt-BR')} · ${metric.rate==null?'Taxa indisponível':`${metric.rate}%`}`:edge.label==='Próximo'?undefined:edge.label,sourceHandle:edge.from_port||'right-out',targetHandle:edge.to_port||'left-in',type:'flow',animated:simulated,style:{strokeWidth:metric?Math.min(5,1.5+Math.log10(Number(metric.sessions||0)+1)):simulated?3:2,stroke:color,strokeDasharray:planned&&!simulated?'6 6':undefined},markerEnd:{type:MarkerType.ArrowClosed,color},data:{readOnly,onRemove:removeEdge,onInsert:onInsertEdge,hasMetric:Boolean(metric),onInspect:onSelectedEdge,liveReady:live?.status==='ready',liveScope,transitionId:live?.transitions?.[edge.id],operational:operational&&edge.variant!=='planned'&&edge.kind!=='site_link'}};});
    if(!journey?.suggestions?.length)return authored;
    const ids=new Set((config.nodes||[]).map(node=>node.id));
    const suggestions=journey.suggestions.filter(item=>ids.has(item.from)&&ids.has(item.to)).map(item=>({id:`suggested:${item.from}:${item.to}`,source:item.from,target:item.to,type:'flow',label:`Sugerido · ${Number(item.sessions).toLocaleString('pt-BR')}`,style:{strokeWidth:2,stroke:'var(--color-fg-quaternary)',strokeDasharray:'3 6'},markerEnd:{type:MarkerType.ArrowClosed,color:'var(--color-fg-quaternary)'},data:{readOnly:true}}));
    return [...authored,...suggestions];
  },[config.edges,config.nodes,readOnly,removeEdge,onInsertEdge,simulatedPath,journey,live,liveScope,operational,onSelectedEdge]);
  const onNodesChange=useCallback(changes=>{
    const dimensions=changes.filter(c=>c.type==='dimensions'&&c.dimensions);
    if(dimensions.length)setMeasurements(current=>{const next={...current};let changed=false;for(const c of dimensions){if(current[c.id]?.width!==c.dimensions.width||current[c.id]?.height!==c.dimensions.height){next[c.id]=c.dimensions;changed=true;}}return changed?next:current;});
    if(readOnly)return;
    const moved=new Map(changes.filter(c=>c.type==='position'&&c.position).map(c=>[c.id,c.position]));
    const removed=new Set(changes.filter(c=>c.type==='remove').map(c=>c.id));
    if(!moved.size&&!removed.size)return;
    setConfig(current=>{
      const groups=(current.groups||[]).filter(g=>!removed.has(g.id)).map(g=>({...g,bounds:{...g.bounds,...moved.get(g.id)}}));
      return syncGroups({...current,groups,nodes:current.nodes.filter(n=>!removed.has(n.id)).map(node=>{
        const oldParent=(current.groups||[]).find(g=>g.id===node.groupId),parent=groups.find(g=>g.id===node.groupId),move=moved.get(node.id);
        const x=move?move.x+(parent?.bounds.x||0):Number(node.x)+(parent&&oldParent?parent.bounds.x-oldParent.bounds.x:0);
        const y=move?move.y+(parent?.bounds.y||0):Number(node.y)+(parent&&oldParent?parent.bounds.y-oldParent.bounds.y:0);
        return {...node,groupId:parent?.id,x:Math.max(0,Math.min(10000,Math.round(x))),y:Math.max(0,Math.min(10000,Math.round(y)))};
      }),edges:current.edges.filter(e=>!removed.has(e.from)&&!removed.has(e.to))});
    });
  },[setConfig,readOnly]);
  const onEdgesChange=useCallback(changes=>{const removed=new Set(changes.filter(change=>change.type==='remove').map(change=>change.id));if(removed.size)setConfig(current=>({...current,edges:current.edges.filter(edge=>!removed.has(edge.id))}));},[setConfig]);
  const onConnect=useCallback(connection=>{if(readOnly||!connection.source||!connection.target||connection.source===connection.target)return;setConfig(current=>{if(current.edges.some(edge=>edge.from===connection.source&&edge.to===connection.target)||current.edges.length>=300)return current;const sourceNode=current.nodes.find(node=>node.id===connection.source);return {...current,edges:[...current.edges,{id:crypto.randomUUID(),from:connection.source,to:connection.target,from_port:connection.sourceHandle||'right-out',to_port:connection.targetHandle||'left-in',variant:sourceNode?.type==='source'?'planned':'direct',label:'Próximo'}]};});},[readOnly,setConfig]);
  const onDrop=useCallback(event=>{event.preventDefault();if(readOnly||!instance)return;try{const item=JSON.parse(event.dataTransfer.getData('application/x-cadu-flow-node'));onAddNode(item,instance.screenToFlowPosition({x:event.clientX,y:event.clientY}));}catch(_){/* A drag from outside the palette is ignored. */}},[instance,onAddNode,readOnly]);
  const insertConnected=item=>{if(!quickAdd||!instance)return;onAddNode(item,instance.screenToFlowPosition(quickAdd.screen),quickAdd.source);setQuickAdd(null);};
  return <><ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} edgeTypes={edgeTypes} onNodesChange={onNodesChange} onNodeDragStart={onGestureStart} onNodeDragStop={onGestureEnd} onEdgesChange={readOnly?undefined:onEdgesChange} onEdgeClick={(_,edge)=>onSelectedEdge?.(edge.id)} onReconnect={(old,connection)=>{if(readOnly||!connection.source||!connection.target||connection.source===connection.target)return;setConfig(current=>current.edges.some(e=>e.id!==old.id&&e.from===connection.source&&e.to===connection.target)?current:{...current,edges:current.edges.map(e=>e.id===old.id?{...e,from:connection.source,to:connection.target,from_port:connection.sourceHandle,to_port:connection.targetHandle}:e)});}} edgesReconnectable={!readOnly} onConnect={onConnect} onConnectEnd={(event,state)=>{if(readOnly||state.isValid||!state.fromNode)return;setQuickAdd({source:state.fromNode.id,screen:{x:event.clientX,y:event.clientY}});}} onSelectionChange={({nodes:items})=>{const ids=items.map(item=>item.id);setSelectedIds(previous=>previous.join('|')===ids.join('|')?previous:ids);onSelectedIdsChange(ids);if(ids.length===1)setSelectedNodeId(ids[0]);}} onNodeClick={(_,node)=>setSelectedNodeId(node.id)} onNodeContextMenu={(event,node)=>{event.preventDefault();setSelectedNodeId(node.id);setContextMenu({x:event.clientX,y:event.clientY,id:node.id});}} onPaneContextMenu={event=>{event.preventDefault();setContextMenu({x:event.clientX,y:event.clientY,id:null});}} onPaneClick={()=>{setSelectedNodeId('');setQuickAdd(null);setContextMenu(null);}} onInit={flow=>{setInstance(flow);onReady(flow);}} onMoveEnd={(_,viewport)=>onZoomChange(viewport.zoom)} onDragOver={event=>event.preventDefault()} onDrop={onDrop} nodesDraggable={!readOnly} nodesConnectable={!readOnly} elementsSelectable={true} selectionOnDrag={!readOnly} panOnDrag={readOnly?true:[1,2]} multiSelectionKeyCode="Shift" minZoom={0.1} maxZoom={2} defaultViewport={{x:80,y:80,zoom:1}} snapToGrid={snapToGrid} snapGrid={[12,12]} fitView={fitOnMount} fitViewOptions={{padding:.2,maxZoom:1}} deleteKeyCode={readOnly?null:['Backspace','Delete']} attributionPosition="bottom-right"><Controls showInteractive={false} position="bottom-left">{onOrganize&&<ControlButton title="Organizar da esquerda para a direita" aria-label="Organizar fluxo" onClick={onOrganize}>⇥</ControlButton>}</Controls><Background variant={BackgroundVariant.Dots} gap={24} size={1} color="var(--color-border-secondary)"/>{showMiniMap&&<MiniMap pannable zoomable nodeColor="var(--color-bg-brand-solid)"/>}</ReactFlow><button type="button" className="flow-minimap-toggle" aria-pressed={showMiniMap} onClick={()=>setShowMiniMap(value=>!value)}>{showMiniMap?'Ocultar mapa':'Minimapa'}</button>{quickAdd&&<div className="flow-quick-add" style={{left:Math.min(quickAdd.screen.x,window.innerWidth-180),top:Math.min(quickAdd.screen.y,window.innerHeight-160)}} role="dialog" aria-label="Adicionar etapa conectada"><strong>Adicionar etapa</strong>{[{type:'page',label:'Página'},{type:'form',label:'Formulário'},{type:'conversion',label:'Conversão'}].map(item=><button key={item.type} type="button" onClick={()=>insertConnected(item)}>{item.label}</button>)}<button type="button" onClick={()=>setQuickAdd(null)}>Cancelar</button></div>}{contextMenu&&<div className="flow-quick-add" style={{left:Math.min(contextMenu.x,window.innerWidth-180),top:Math.min(contextMenu.y,window.innerHeight-160)}} role="menu" aria-label="Ações do canvas">{contextMenu.id&&<><button type="button" role="menuitem" disabled={readOnly} onClick={()=>{onDuplicateSelection(contextMenu.id);setContextMenu(null);}}>Duplicar etapa</button><button type="button" role="menuitem" disabled={readOnly} onClick={()=>{const id=contextMenu.id;setConfig(current=>({...current,nodes:current.nodes.filter(node=>node.id!==id),edges:current.edges.filter(edge=>edge.from!==id&&edge.to!==id)}));setContextMenu(null);}}>Excluir etapa</button></>}<button type="button" role="menuitem" onClick={()=>{instance?.fitView({padding:.15,duration:200});setContextMenu(null);}}>Ajustar à tela</button></div>}</>;
}

export function FlowCanvas(props) {
  return <div className="reports-flow-canvas flow-react-canvas" role="region" aria-label="Mapa visual do fluxo"><ReactFlowProvider><FlowCanvasInner {...props}/></ReactFlowProvider></div>;
}
