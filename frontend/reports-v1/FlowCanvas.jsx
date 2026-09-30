import React, {useCallback, useMemo, useRef, useState} from 'react';
import {ReactFlow, Background, BackgroundVariant, BaseEdge, EdgeLabelRenderer, Handle, MarkerType, MiniMap, Position, ReactFlowProvider, getBezierPath} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import {flowBlockFor} from './flowBlockRegistry.js';
import './flow-canvas.css';


function NodeLabel({node, selected, readOnly, onChange}) {
  const [editing,setEditing]=useState(false);
  const [draft,setDraft]=useState(node.title||'');
  const inputRef=useRef(null);
  const begin=()=>{if(readOnly)return;setDraft(node.title||'');setEditing(true);requestAnimationFrame(()=>inputRef.current?.select());};
  const finish=save=>{if(save)onChange(node.id,(draft.trim()||node.type).slice(0,120));setEditing(false);};
  return <div className="flow-shape-label" onDoubleClick={begin} onKeyDown={event=>{if(!editing&&(event.key==='Enter'||event.key==='F2')){event.preventDefault();begin();}}}>
    {editing?<input ref={inputRef} className="nodrag" aria-label="Editar nome da etapa" value={draft} onChange={event=>setDraft(event.target.value)} onBlur={()=>finish(true)} onKeyDown={event=>{if(event.key==='Enter'){event.preventDefault();finish(true);}if(event.key==='Escape'){event.stopPropagation();finish(false);}}}/> : <span tabIndex={selected&&!readOnly?0:-1} aria-label={`${node.title||node.type}. Pressione Enter para renomear`}>{node.title||node.type}</span>}
  </div>;
}

function NodeHandles() {
  return <><Handle id="left-in" type="target" position={Position.Left}/><Handle id="top-in" type="target" position={Position.Top}/><Handle id="right-out" type="source" position={Position.Right}/><Handle id="bottom-out" type="source" position={Position.Bottom}/></>;
}

function ShapeNode({data,selected,shape}) {
  const {node,readOnly,onLabelChange}=data;
  const block=flowBlockFor(node);
  const Icon=block.icon;
  return <div className={`flow-shape-node is-${shape}${selected?' is-selected':''}${node.type==='conversion'?' is-success':''}${node.type==='error'?' is-error':''}`}>
    <NodeLabel node={node} selected={selected} readOnly={readOnly} onChange={onLabelChange}/>
    <div className="flow-shape-body" aria-hidden="true">{shape==='page'?<div className="flow-page-preview"><div className="flow-page-preview__bar"><i/><i/><i/></div><div className="flow-page-preview__image"/><div className="flow-page-preview__line"/><div className="flow-page-preview__line is-short"/></div>:<Icon size={22}/>}</div>
    {node.path&&node.path!=='/'&&<small>{node.path}</small>}
    {block.trackable&&!node.path&&<span className="flow-shape-warning" title="Configure a URL desta etapa">!</span>}
    <NodeHandles/>
  </div>;
}

const nodeTypes = {
  circle:props=><ShapeNode {...props} shape="circle"/>,
  diamond:props=><ShapeNode {...props} shape="diamond"/>,
  page:props=><ShapeNode {...props} shape="page"/>,
};

function FlowEdge({id,sourceX,sourceY,targetX,targetY,sourcePosition,targetPosition,markerEnd,style,data,label,selected}) {
  const [hovered,setHovered]=useState(false);
  const [path,labelX,labelY]=getBezierPath({sourceX,sourceY,targetX,targetY,sourcePosition,targetPosition});
  return <><BaseEdge id={id} path={path} markerEnd={markerEnd} style={style}/><path d={path} fill="none" stroke="transparent" strokeWidth="20" onMouseEnter={()=>setHovered(true)} onMouseLeave={()=>setHovered(false)}/><EdgeLabelRenderer><div className={`flow-edge-actions nodrag nopan${hovered||selected?' is-visible':''}`} style={{transform:`translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`}} onMouseEnter={()=>setHovered(true)} onMouseLeave={()=>setHovered(false)}><span>{label}</span>{!data.readOnly&&<><button type="button" aria-label="Inserir etapa nesta conexão" onClick={()=>data.onInsert(id)}>+</button><button type="button" aria-label="Remover conexão" onClick={()=>data.onRemove(id)}>×</button></>}</div></EdgeLabelRenderer></>;
}

const edgeTypes={flow:FlowEdge};

function FlowCanvasInner({config,setConfig,selectedNodeId,setSelectedNodeId,onSelectedIdsChange,onAddNode,onInsertEdge,onDuplicateSelection,readOnly,snapToGrid,onReady,onZoomChange}) {
  const [instance,setInstance]=useState(null);
  const [selectedIds,setSelectedIds]=useState([]);
  const [showMiniMap,setShowMiniMap]=useState(false);
  const [quickAdd,setQuickAdd]=useState(null);
  const [contextMenu,setContextMenu]=useState(null);
  const onLabelChange=useCallback((id,title)=>setConfig(current=>({...current,nodes:current.nodes.map(node=>node.id===id?{...node,title}:node)})),[setConfig]);
  const nodes=useMemo(()=>(config.nodes||[]).map(node=>({id:node.id,type:flowBlockFor(node).shape,position:{x:Number(node.x)||0,y:Number(node.y)||0},data:{node,readOnly,onLabelChange},draggable:!readOnly,selectable:true,selected:selectedIds.length?selectedIds.includes(node.id):node.id===selectedNodeId})),[config.nodes,readOnly,onLabelChange,selectedNodeId,selectedIds]);
  const removeEdge=useCallback(id=>setConfig(current=>({...current,edges:current.edges.filter(edge=>edge.id!==id)})),[setConfig]);
  const edges=useMemo(()=>(config.edges||[]).map(edge=>{const planned=edge.variant==='planned'||edge.kind==='site_link';const color=planned?'var(--color-fg-quaternary)':'var(--color-fg-brand-primary)';return {id:edge.id,source:edge.from,target:edge.to,label:edge.label==='Próximo'?undefined:edge.label,sourceHandle:edge.from_port||'right-out',targetHandle:edge.to_port||'left-in',type:'flow',style:{strokeWidth:2,stroke:color,strokeDasharray:planned?'6 6':undefined},markerEnd:{type:MarkerType.ArrowClosed,color},data:{readOnly,onRemove:removeEdge,onInsert:onInsertEdge}};}),[config.edges,readOnly,removeEdge,onInsertEdge]);
  const onNodesChange=useCallback(changes=>{const moved=changes.filter(change=>change.type==='position'&&change.position);const removed=new Set(changes.filter(change=>change.type==='remove').map(change=>change.id));if(moved.length||removed.size)setConfig(current=>({...current,nodes:current.nodes.filter(node=>!removed.has(node.id)).map(node=>{const change=moved.find(item=>item.id===node.id);return change?{...node,x:Math.max(0,Math.round(change.position.x)),y:Math.max(0,Math.round(change.position.y))}:node;}),edges:removed.size?current.edges.filter(edge=>!removed.has(edge.from)&&!removed.has(edge.to)):current.edges}));},[setConfig]);
  const onEdgesChange=useCallback(changes=>{const removed=new Set(changes.filter(change=>change.type==='remove').map(change=>change.id));if(removed.size)setConfig(current=>({...current,edges:current.edges.filter(edge=>!removed.has(edge.id))}));},[setConfig]);
  const onConnect=useCallback(connection=>{if(readOnly||!connection.source||!connection.target||connection.source===connection.target)return;setConfig(current=>{if(current.edges.some(edge=>edge.from===connection.source&&edge.to===connection.target)||current.edges.length>=300)return current;const sourceNode=current.nodes.find(node=>node.id===connection.source);return {...current,edges:[...current.edges,{id:crypto.randomUUID(),from:connection.source,to:connection.target,from_port:connection.sourceHandle||'right-out',to_port:connection.targetHandle||'left-in',variant:sourceNode?.type==='source'?'planned':'direct',label:'Próximo'}]};});},[readOnly,setConfig]);
  const onDrop=useCallback(event=>{event.preventDefault();if(readOnly||!instance)return;try{const item=JSON.parse(event.dataTransfer.getData('application/x-cadu-flow-node'));onAddNode(item,instance.screenToFlowPosition({x:event.clientX,y:event.clientY}));}catch(_){/* A drag from outside the palette is ignored. */}},[instance,onAddNode,readOnly]);
  const insertConnected=item=>{if(!quickAdd||!instance)return;onAddNode(item,instance.screenToFlowPosition(quickAdd.screen),quickAdd.source);setQuickAdd(null);};
  return <><ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} edgeTypes={edgeTypes} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onConnect={onConnect} onConnectEnd={(event,state)=>{if(readOnly||state.isValid||!state.fromNode)return;setQuickAdd({source:state.fromNode.id,screen:{x:event.clientX,y:event.clientY}});}} onSelectionChange={({nodes:items})=>{const ids=items.map(item=>item.id);setSelectedIds(previous=>previous.join('|')===ids.join('|')?previous:ids);onSelectedIdsChange(ids);if(ids.length===1)setSelectedNodeId(ids[0]);}} onNodeClick={(_,node)=>setSelectedNodeId(node.id)} onNodeContextMenu={(event,node)=>{event.preventDefault();setSelectedNodeId(node.id);setContextMenu({x:event.clientX,y:event.clientY,id:node.id});}} onPaneContextMenu={event=>{event.preventDefault();setContextMenu({x:event.clientX,y:event.clientY,id:null});}} onPaneClick={()=>{setSelectedNodeId('');setQuickAdd(null);setContextMenu(null);}} onInit={flow=>{setInstance(flow);onReady(flow);}} onMoveEnd={(_,viewport)=>onZoomChange(viewport.zoom)} onDragOver={event=>event.preventDefault()} onDrop={onDrop} nodesDraggable={!readOnly} nodesConnectable={!readOnly} elementsSelectable={true} selectionOnDrag panOnDrag={[1,2]} multiSelectionKeyCode="Shift" minZoom={0.1} maxZoom={2} defaultViewport={{x:80,y:80,zoom:1}} snapToGrid={snapToGrid} snapGrid={[12,12]} fitView={false} deleteKeyCode={readOnly?null:['Backspace','Delete']} attributionPosition="bottom-right"><Background variant={BackgroundVariant.Lines} gap={24} size={1} color="var(--color-border-secondary)"/>{showMiniMap&&<MiniMap pannable zoomable nodeColor="var(--color-bg-brand-solid)"/>}</ReactFlow><button type="button" className="flow-minimap-toggle" aria-pressed={showMiniMap} onClick={()=>setShowMiniMap(value=>!value)}>{showMiniMap?'Ocultar mapa':'Minimapa'}</button>{quickAdd&&<div className="flow-quick-add" style={{left:Math.min(quickAdd.screen.x,window.innerWidth-180),top:Math.min(quickAdd.screen.y,window.innerHeight-160)}} role="dialog" aria-label="Adicionar etapa conectada"><strong>Adicionar etapa</strong>{[{type:'page',label:'Página'},{type:'form',label:'Formulário'},{type:'conversion',label:'Conversão'}].map(item=><button key={item.type} type="button" onClick={()=>insertConnected(item)}>{item.label}</button>)}<button type="button" onClick={()=>setQuickAdd(null)}>Cancelar</button></div>}{contextMenu&&<div className="flow-quick-add" style={{left:Math.min(contextMenu.x,window.innerWidth-180),top:Math.min(contextMenu.y,window.innerHeight-160)}} role="menu" aria-label="Ações do canvas">{contextMenu.id&&<><button type="button" role="menuitem" disabled={readOnly} onClick={()=>{onDuplicateSelection(contextMenu.id);setContextMenu(null);}}>Duplicar etapa</button><button type="button" role="menuitem" disabled={readOnly} onClick={()=>{const id=contextMenu.id;setConfig(current=>({...current,nodes:current.nodes.filter(node=>node.id!==id),edges:current.edges.filter(edge=>edge.from!==id&&edge.to!==id)}));setContextMenu(null);}}>Excluir etapa</button></>}<button type="button" role="menuitem" onClick={()=>{instance?.fitView({padding:.15,duration:200});setContextMenu(null);}}>Ajustar à tela</button></div>}</>;
}

export function FlowCanvas(props) {
  return <div className="reports-flow-canvas flow-react-canvas" role="region" aria-label="Mapa visual do fluxo"><ReactFlowProvider><FlowCanvasInner {...props}/></ReactFlowProvider></div>;
}
