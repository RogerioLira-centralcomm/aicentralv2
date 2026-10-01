import {ReportsPanelShell} from './ReportsPanelShell.jsx';
import {useFlowReadiness} from './useFlowReadiness.js';
import {FlowBlueprintNotice} from './FlowBlueprintNotice.jsx';
import {useFlowDocument} from './useFlowDocument.js';
import {FlowStudioAssist} from './FlowStudioAssist.jsx';
import {FlowBlueprint} from './FlowBlueprint.jsx';
import {FlowConversionProbe} from './FlowConversionProbe.jsx';
import {flowNextAction} from './flowNextAction.js';
import {FlowCatalog} from './FlowCatalog.jsx';
import {Lightbulb02, FlipBackward, FlipForward, Plus, LayoutGrid01, CheckDone01} from '@untitledui/icons';
import {FlowSolutionSwitcher} from './FlowNavbarAccount.jsx';
import React, {useEffect, useMemo, useRef, useState} from 'react';
import {FlowLiveValue} from './FlowLiveValue.jsx';
import {Button as UntitledButton} from '../cadu-design-system/untitled-kit/button.tsx';
import {Dialog, Modal, ModalOverlay} from 'react-aria-components';
import {ReportsActionButton} from './ReportsActionButton.jsx';
import {ReportsFieldInput} from './ReportsFieldInput.jsx';
import {ReportsNativeSelect} from './ReportsNativeSelect.jsx';
import {ReportsDrawer} from './ReportsDrawer.jsx';
import {usePanelLayout} from './usePanelLayout.js';
import {groupNodes, syncGroups, fitGroups} from './flowGroups.js';
import {uniqueFlowEvents} from './flowEventIdentity.js';
import {FlowCanvas} from './FlowCanvas.jsx';
import {FlowMonitorWorkspace} from './FlowMonitorWorkspace.jsx';
import {FlowInspector} from './FlowInspector.jsx';
import {FlowPublicationDialog, flowChangeSummary} from './FlowPublicationDialog.jsx';
import {FlowSimulator} from './FlowSimulator.jsx';
import {FlowJourneyPanel} from './FlowJourneyPanel.jsx';
import {FlowToast} from './FlowToast.jsx';
import {plural, savedAgo, publishBlocked} from './flowFeedback.js';
import {flowValidation} from './flowValidation.js';
import {downloadFlowPng, downloadFlowSvg} from './flowExport.js';
import {flowBlockFor, flowPaletteGroups} from './flowBlockRegistry.js';
import {FLOW_PLATFORMS, FlowPlatformLogo} from './FlowPlatformLogo.jsx';
import {layoutFlow} from './flowLayout.js';
import {FLOW_STAGES, placeNodeInStage, stageAtX, stageX} from './flowStages.js';
import {useFlowHistory} from './useFlowHistory.js';
import {SearchLg} from '@untitledui/icons';
import {flowEditorId, reportUrl, flowEditorUrl, shortDate, integer, decimal, json, Empty, FLOW_CHANNELS, Kpi} from './reportsCommon.jsx';

const FLOW_CARD_WIDTH = 248;
const FLOW_CARD_HEIGHT = 184;
const FLOW_GRID_SIZE = 20;


export function Flow(props) {
  useEffect(() => {const query=new URLSearchParams(location.search);if(!flowEditorId()&&query.get('flow_view')==='edit'&&query.get('flow_id'))location.replace(flowEditorUrl(query.get('flow_id'),props.data.client.client_id));}, [props.data.client.client_id]);
  const [supported, setSupported] = useState(() => window.matchMedia('(min-width: 768px)').matches);
  const [linkCopied, setLinkCopied] = useState(false);
  useEffect(() => {
    const query = window.matchMedia('(min-width: 768px)');
    const update = () => setSupported(query.matches);
    query.addEventListener('change', update);
    return () => query.removeEventListener('change', update);
  }, []);
  const requiresEditorCanvas=Boolean(flowEditorId())&&!/\/monitor\/?$/.test(location.pathname);
  return <>{!supported&&requiresEditorCanvas&&<section className="reports-flow-device-message"><h2>Abra este fluxo em um tablet ou computador.</h2><p>A mesa de fluxos precisa de uma tela maior para organizar etapas e conexões. Se estiver em um computador, amplie a janela.</p><button type="button" onClick={async()=>{try{await navigator.clipboard.writeText(location.href);setLinkCopied(true);}catch(_){setLinkCopied(false);}}}>{linkCopied?'Link copiado':'Copiar link'}</button><a href={reportUrl('overview')}>Voltar ao Reports</a></section>}{(supported||!requiresEditorCanvas)&&<div><FlowDesktop key={props.data.client.client_id} {...props}/></div>}</>;
}

function FlowDesktop({data, save, busy, filters, refreshRevision}) {
  const workspaceV2=Boolean(data.features?.flows_workspace_v2);
  const flowView = flowEditorId() ? (/\/monitor\/?$/.test(location.pathname)?'monitor':'edit') : new URLSearchParams(location.search).get('flow_view')==='monitor' ? 'monitor' : 'create';
  const [flow, setFlow] = useState({tags: [], steps: [], flows: [], tests: [], tag_urls: {}, activity: [], online: 0, conversions: 0, confirmed: [], supertag_sites: []});
  const [discovery, setDiscovery] = useState({run:null,pages:[]});
  useEffect(() => {
    document.body.classList.toggle('reports-flow-editor-active', flowView === 'edit');
    return () => document.body.classList.remove('reports-flow-editor-active');
  }, [flowView]);
  const [discoveryBusy, setDiscoveryBusy] = useState(false);
  const [flowSuggestions, setFlowSuggestions] = useState(null);
  const [selectedSuggestions, setSelectedSuggestions] = useState([]);
  const [selectedFlowId, setSelectedFlowId] = useState(() => flowEditorId() || new URLSearchParams(location.search).get('flow_id') || '');
  const [flowName, setFlowName] = useState('');
  const [blueprintOpen,setBlueprintOpen]=useState(false);
  const [probeOpen,setProbeOpen]=useState(false);
  // A newly created flow opens with the conversion test ready; the test itself only runs on the user's click.
  useEffect(()=>{const params=new URLSearchParams(location.search);if(params.get('testar')!=='1')return;setProbeOpen(true);params.delete('testar');history.replaceState(history.state,'',`${location.pathname}${params.toString()?`?${params}`:''}`);},[]);
  const [blueprintPreview,setBlueprintPreview]=useState({nodes:[],edges:[]});
  const [navigationOnly,setNavigationOnly]=useState(false);
  const [suggestionToggle,setSuggestionToggle]=useState(0);
  const [flowHost, setFlowHost] = useState(()=>new URLSearchParams(location.search).get('site_host')||'');
  const [flowCreateOpen,setFlowCreateOpen]=useState(()=>Boolean(new URLSearchParams(location.search).get('site_host')));
  const [flowQuery,setFlowQuery]=useState('');
  const [flowStatusFilter,setFlowStatusFilter]=useState('all');
  const [flowSiteCheck, setFlowSiteCheck] = useState(null);
  const [flowSiteChecking, setFlowSiteChecking] = useState(false);
  const [saveFailure,setSaveFailure]=useState(null);
  const [flowConfig, setFlowConfig] = useFlowDocument({nodes: [], edges: []});
  const flowInitializedRef = useRef('');
  const editorSavingRef = useRef(false);
  const revisionRef = useRef(null);
  const savedSnapshotRef = useRef('');
  const savePromiseRef = useRef(null);
  const flowHistory = useFlowHistory(flowConfig, setFlowConfig);
  const liveEditorRef = useRef(null);
  const [versionMessage, setVersionMessage] = useState('');
  const [lastSavedAt,setLastSavedAt]=useState(null);
  const [statusClock,setStatusClock]=useState(Date.now());
  const [remoteRevision,setRemoteRevision]=useState(null);
  useEffect(()=>{const timer=window.setInterval(()=>setStatusClock(Date.now()),30000);return()=>window.clearInterval(timer);},[]);
  const [monitorVersions,setMonitorVersions] = useState([]);
  const [analysisSelection,setAnalysisSelection] = useState({flowId:'',revision:''});
  const analysisRevision = analysisSelection.flowId===selectedFlowId ? analysisSelection.revision : '';
  const [commandBusy,setCommandBusy] = useState(false);
  const commandLock = useRef(false);
  const startCommand = () => {if(commandLock.current)return false;commandLock.current=true;setCommandBusy(true);return true;};
  const endCommand = () => {commandLock.current=false;setCommandBusy(false);};
  const [versions, setVersions] = useState(null);
  const [versionComparison,setVersionComparison]=useState(null);
  const [paletteQuery, setPaletteQuery] = useState('');
  const [pageSuggestions, setPageSuggestions] = useState({});
  const [suggestingPage, setSuggestingPage] = useState('');
  const [editorSaveState, setEditorSaveState] = useState('saved');
  const [draftConflict, setDraftConflict] = useState(false);
  const [selectedNodeId, setSelectedNodeId] = useState('');
  const [canvasZoom, setCanvasZoom] = useState(1);
  const [paletteOpen, setPaletteOpen] = useState(()=>window.innerWidth>=1180);
  const [paletteMode, setPaletteMode] = useState('site');
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const panelLayout=usePanelLayout(paletteOpen,inspectorOpen,setPaletteOpen,setInspectorOpen);
  const canvasFlowRef = useRef(null);
  const [selectedNodeIds, setSelectedNodeIds] = useState([]);
  const copiedNodesRef = useRef(null);
  useEffect(()=>{if(selectedNodeId){setPaletteOpen(false);setInspectorOpen(true);const timer=setTimeout(()=>canvasFlowRef.current?.fitView({nodes:[{id:selectedNodeId}],padding:.65,maxZoom:1,duration:160}),40);return()=>clearTimeout(timer);}},[selectedNodeId]);
  const changeZoom = value => {
    const next=Math.max(.25,Math.min(2,Math.round(value*100)/100));
    setCanvasZoom(next);
    canvasFlowRef.current?.zoomTo(next,{duration:180});
  };
  const fitCanvas = () => {
    canvasFlowRef.current?.fitView({padding:.15,duration:220,maxZoom:1});
  };
  const [monitorBusy, setMonitorBusy] = useState(false);
  const [snapToGrid, setSnapToGrid] = useState(true);
  const [flowLayoutNote, setFlowLayoutNote] = useState('');
  const [simulation, setSimulation] = useState(null);
  const [publicationOpen,setPublicationOpen]=useState(false);
  const [publicationNote,setPublicationNote]=useState('');
  const [publishedConfig,setPublishedConfig]=useState(null);
  const [publicationBusy,setPublicationBusy]=useState(false);
  const [validationOpen,setValidationOpen]=useState(false);
  const [editorMode,setEditorMode]=useState('edit');
  const [simulatedPath,setSimulatedPath]=useState([]);
  const [journeyDays,setJourneyDays]=useState(30);
  const [journeyData,setJourneyData]=useState(null);
  const [journeyLoading,setJourneyLoading]=useState(false);
  const [journeyError,setJourneyError]=useState('');
  const [flowSiteKind,setFlowSiteKind]=useState('');
  const [flowCustomerId,setFlowCustomerId]=useState('');
  const [flowCampaignId,setFlowCampaignId]=useState('');
  const [copyState, setCopyState] = useState('');
  const [localError, setLocalError] = useState('');
  const [monitorInterval, setMonitorInterval] = useState(15);
  const [liveUpdatedAt, setLiveUpdatedAt] = useState(null);
  const [liveFailure, setLiveFailure] = useState(false);
  const requestSequence = useRef(0);
  const liveScope = `${data.client.client_id}:${selectedFlowId}:${flowView}:${filters.period}:${filters.startDate}:${filters.endDate}:${filters.platform}:${filters.account}:${filters.campaign}:${analysisRevision}`;
  const liveScopeRef = useRef(liveScope);
  liveScopeRef.current = liveScope;
  const reload = () => {
    const sequence = ++requestSequence.current;
    const scope = liveScope;
    const params = new URLSearchParams({client_id: String(data.client.client_id), days: filters.period,
      start_date: filters.startDate, end_date: filters.endDate, view:workspaceV2&&flowView==='monitor'?'edit':flowView});
    if (selectedFlowId) params.set('flow_id', selectedFlowId);
    if(flowView==='monitor'&&analysisRevision)params.set('revision',analysisRevision);
    if (filters.platform) params.set('platform', filters.platform);
    if (filters.account) params.set('account_id', filters.account);
    if (filters.campaign) params.set('campaign_id', filters.campaign);
    return json(`/connect/api/v2/reports/flow?${params}`).then(result => {
      if(sequence !== requestSequence.current || scope !== liveScopeRef.current) return;
      setFlow(result);setLiveUpdatedAt(new Date());setLiveFailure(false);return result;
    }).catch(failure => {
      if(sequence === requestSequence.current && scope === liveScopeRef.current) setLiveFailure(true);
      throw failure;
    });
  };
  useEffect(()=>{
    if(flowView!=='monitor'||!selectedFlowId)return;
    let cancelled=false;
    json(`/connect/api/v2/reports/flow/flows/${selectedFlowId}/versions?client_id=${data.client.client_id}`)
      .then(result=>{if(!cancelled)setMonitorVersions(result.versions);})
      .catch(()=>{if(!cancelled)setMonitorVersions([]);});
    return()=>{cancelled=true;};
  },[selectedFlowId,flowView,data.client.client_id,refreshRevision]);
  const loadDiscoveries = async flowId => {
    if (!flowId) {setDiscovery({run:null,pages:[]});return;}
    const result=await json(`/connect/api/v2/reports/flow/flows/${flowId}/discoveries?client_id=${data.client.client_id}`);
    if(liveEditorRef.current?.id===flowId)setDiscovery(result);
  };
  useEffect(() => {reload().catch(failure => setLocalError(failure.message));}, [data.client.client_id, filters.period, filters.startDate, filters.endDate, filters.platform, filters.account, filters.campaign, selectedFlowId,flowView,refreshRevision,analysisRevision]);
  useEffect(() => {if(flowView!=='edit')return;loadDiscoveries(selectedFlowId).catch(failure => setLocalError(failure.message));}, [selectedFlowId,data.client.client_id]);
  useEffect(() => {const found = flow.flows.find(item => item.id === selectedFlowId); if (found && flowInitializedRef.current !== selectedFlowId) {setFlowName(found.name); setFlowHost(found.allowed_host); setFlowConfig(found.config || {nodes: [], edges: []});flowHistory.reset(found.config || {nodes:[],edges:[]});copiedNodesRef.current=null; revisionRef.current=found.draft_revision;savedSnapshotRef.current=JSON.stringify({name:found.name,config:found.config||{nodes:[],edges:[]}});flowInitializedRef.current=selectedFlowId;setVersions(null);setVersionComparison(null);setPageSuggestions({});setVersionMessage('');}}, [selectedFlowId, flow.flows]);
  useEffect(() => {const found=flow.flows.find(item=>item.id===selectedFlowId);if(found)setMonitorInterval(Number(found.monitor_interval_minutes)||15);}, [selectedFlowId,flow.flows]);
  useEffect(() => {
    if(flowView !== 'monitor' || !selectedFlowId || workspaceV2) return;
    let stopped = false, pending = false, timer;
    const poll = async () => {
      window.clearTimeout(timer);
      if(stopped || pending || document.hidden) return;
      pending = true;
      try {await reload();} catch (_) { /* Keep the last snapshot and show stale state. */ }
      finally {pending=false;if(!stopped&&!document.hidden)timer=window.setTimeout(poll,15000);}
    };
    const visibility = () => {window.clearTimeout(timer);if(!document.hidden)poll();};
    timer=window.setTimeout(poll,15000);
    document.addEventListener('visibilitychange',visibility);
    return()=>{stopped=true;window.clearTimeout(timer);document.removeEventListener('visibilitychange',visibility);};
  }, [liveScope]);
  const chooseFlow = id => {if(commandLock.current)return;setSelectedFlowId(id);const url=new URL(location.href);if(id)url.searchParams.set('flow_id',id);else url.searchParams.delete('flow_id');history.replaceState(null,'',url);};
  const openFlow = (item, view) => {if(view==='edit')location.assign(flowEditorUrl(item.id,data.client.client_id));else location.assign(reportUrl(`flows/${item.id}/monitor`,{client_id:data.client.client_id}));};
  const siteCheckSequence=useRef(0);
  const checkFlowSite = async () => {const url=flowHost.trim();if(!url)return;const sequence=++siteCheckSequence.current;setFlowSiteChecking(true);setFlowSiteCheck(null);setLocalError('');try{const result=await json(`/connect/api/v2/reports/supertag/site-check?client_id=${data.client.client_id}&url=${encodeURIComponent(url)}`);if(sequence===siteCheckSequence.current)setFlowSiteCheck({...result,verifiedUrl:url});}catch(failure){if(sequence===siteCheckSequence.current)setFlowSiteCheck({error:failure.message});}finally{if(sequence===siteCheckSequence.current)setFlowSiteChecking(false);}};
  const newFlow = async event => {event.preventDefault(); try {if(!flowSiteCheck||flowSiteCheck.error||flowSiteCheck.verifiedUrl!==flowHost.trim())throw new Error('Verifique o domínio atual antes de criar o fluxo.');const name=flowName||flowSiteCheck.title||flowSiteCheck.host;const result = await save('/flow/flows', {name, allowed_host: flowSiteCheck.host, customer_id:flowCustomerId||null,campaign_id:flowCampaignId||null,config:{nodes:[],edges:[],...(flowSiteKind?{site_kind:flowSiteKind}:{})}}, false);location.assign(`${flowEditorUrl(result.flow.id,data.client.client_id)}&testar=1`);} catch (failure) {setLocalError(failure.message);}};
  const addNode = (type, options = {}, point = null, connectedFrom = '') => {const existing=flowConfig.nodes.find(n=>n.type===type&&options.path&&n.path===options.path&&(n.event_name||'')===(options.event_name||''));if(existing){setSelectedNodeId(existing.id);canvasFlowRef.current?.fitView({nodes:[{id:existing.id}],padding:.6,duration:200});return;}if(flowConfig.nodes.length>=200){setLocalError('O fluxo aceita até 200 nós. Crie outro fluxo para continuar.');return;}const defaults={source:'Origem de tráfego',page:'Página / URL',form:'Formulário',event:'Evento',conversion:'Conversão',whatsapp:'Clique WhatsApp',error:'Página de erro'};const index=flowConfig.nodes.length;const title=options.title||options.label||defaults[type]||type;const nodeId=crypto.randomUUID();const node={id:nodeId,type,stage:type==='source'?'source':point?stageAtX(point.x):type==='conversion'?'conversion':type==='form'?'intent':type==='error'?'support':'exploration',pageType:['page','form','conversion','error'].includes(type)?'other':undefined,origin:'manual',kind:options.kind||flowBlockFor({type}).kind,title,data:{label:title,url:''},path:options.path&&options.path.startsWith('/')?options.path:['page','form','event','conversion','whatsapp','error'].includes(type)?`/configurar-${nodeId.slice(0,8)}`:'',event_name:type==='event'?(options.event_name||''):undefined,source:type==='source'?(options.source||'google'):undefined,x:stageX(type==='source'?'source':point?stageAtX(point.x):type==='conversion'?'conversion':type==='form'?'intent':type==='error'?'support':'exploration'),y:point?Math.max(0,snap(point.y)):100+Math.floor(index/3)*(FLOW_CARD_HEIGHT+48),fields:type==='form'?[{name:'nome',label:'Nome',required:true},{name:'email',label:'E-mail',required:true}]:[]};node.data.url=node.path;setFlowConfig(current=>({...current,schema_version:2,nodes:[...current.nodes,node],edges:connectedFrom?[...current.edges,{id:crypto.randomUUID(),from:connectedFrom,to:node.id,variant:'direct',label:'Próximo'}]:current.edges}));setSelectedNodeId(node.id);};
  const insertOnEdge = edgeId => {if(flowConfig.nodes.length>=200){setLocalError('O fluxo aceita até 200 nós.');return;}const edge=flowConfig.edges.find(item=>item.id===edgeId);if(!edge)return;const from=flowConfig.nodes.find(item=>item.id===edge.from),to=flowConfig.nodes.find(item=>item.id===edge.to);if(!from||!to)return;const id=crypto.randomUUID();const node={id,type:'condition',kind:'logic.condition',title:'Novo nó',data:{label:'Novo nó',url:''},x:snap((Number(from.x)+Number(to.x))/2),y:snap((Number(from.y)+Number(to.y))/2)};setFlowConfig(current=>({...current,schema_version:2,nodes:[...current.nodes,node],edges:current.edges.flatMap(item=>item.id===edgeId?[{...item,id:crypto.randomUUID(),to:id},{...item,id:crypto.randomUUID(),from:id}]:[item])}));setSelectedNodeId(id);setInspectorOpen(true);};
  const copySelection=()=>{const ids=new Set(selectedNodeIds.length?selectedNodeIds:[selectedNodeId]);const nodes=flowConfig.nodes.filter(node=>ids.has(node.id));if(!nodes.length)return;copiedNodesRef.current={nodes,edges:flowConfig.edges.filter(edge=>ids.has(edge.from)&&ids.has(edge.to))};};
  const pasteSelection=()=>{const copied=copiedNodesRef.current;if(!copied?.nodes.length||readOnly)return;if(flowConfig.nodes.length+copied.nodes.length>200){setLocalError('A cópia excede o limite de 200 etapas deste fluxo.');return;}const ids=new Map(copied.nodes.map(node=>[node.id,crypto.randomUUID()]));const suffix=Math.random().toString(36).slice(2,7);const nodes=copied.nodes.map(node=>({...node,id:ids.get(node.id),title:`${node.title} (cópia)`,x:Math.min(9950,Number(node.x)+48),y:Math.min(9950,Number(node.y)+48),path:node.path?`/nova-etapa-${suffix}-${ids.get(node.id).slice(0,4)}`:node.path,event_name:node.event_name?`${node.event_name.slice(0,65)}_copy_${suffix}`:node.event_name,discoveryPageId:undefined,stepId:undefined}));const edges=copied.edges.map(edge=>({...edge,id:crypto.randomUUID(),from:ids.get(edge.from),to:ids.get(edge.to)}));setFlowConfig(current=>({...current,nodes:[...current.nodes,...nodes],edges:[...current.edges,...edges]}));setSelectedNodeIds(nodes.map(node=>node.id));setSelectedNodeId(nodes[0].id);};
  const duplicateSelection=id=>{if(id){const node=flowConfig.nodes.find(item=>item.id===id);if(node)copiedNodesRef.current={nodes:[node],edges:[]};}else copySelection();pasteSelection();};
  const startPaletteDrag = (event, item) => {event.dataTransfer.effectAllowed='copy';event.dataTransfer.setData('application/x-cadu-flow-node',JSON.stringify(item));};
  const clickPaletteNode = item => addNode(item.type,item);
  const updateNode = (key,value) => setFlowConfig(current=>{const next={...current,nodes:current.nodes.map(node=>node.id===selectedNodeId?key==='stage'?{...placeNodeInStage(node,value),manuallyEdited:true}:key==='pageType'?{...node,pageType:value,pageTypeStatus:'confirmed',manuallyEdited:true}:{...node,[key]:value,manuallyEdited:true}:node)};if(key==='pageGroup'&&!value.trim())return syncGroups({...next,groups:(next.groups||[]).map(g=>({...g,memberIds:g.memberIds.filter(id=>id!==selectedNodeId)}))});const target=key==='pageGroup'&&(current.groups||[]).find(g=>g.name===value);return target?groupNodes(next,[...new Set([...target.memberIds,selectedNodeId])],target.name,target.id):next;});
  const snap = value => snapToGrid ? Math.round(value/FLOW_GRID_SIZE)*FLOW_GRID_SIZE : value;
  const autoArrange = async (mode='stages') => {
    if(!flowConfig.nodes.length)return;
    try {
      const documentAtStart=JSON.stringify(flowConfig);
      const flowIdAtStart=selectedFlowId;
      const nodes=await layoutFlow(flowConfig,{mode:typeof mode==='string'?mode:'stages'});
      if(liveEditorRef.current?.id!==flowIdAtStart||JSON.stringify(liveEditorRef.current?.config)!==documentAtStart){
        setFlowLayoutNote('O fluxo mudou durante a organização. Organize novamente.');return;
      }
      const positions=new Map(nodes.map(node=>[node.id,{x:node.x,y:node.y,stage:node.stage}]));
      setFlowConfig(current=>fitGroups({...current,layoutMode:typeof mode==='string'?mode:'stages',nodes:current.nodes.map(node=>({...node,...positions.get(node.id),manuallyEdited:true}))}));
      setTimeout(()=>canvasFlowRef.current?.fitView({padding:.2,maxZoom:1,duration:200}),100);
      setFlowLayoutNote('Etapas organizadas da esquerda para a direita.');
    } catch (failure) {
      setFlowLayoutNote(`Não foi possível organizar: ${failure.message}`);
    }
  };
  const autoConnect = () => {
    const nodes=[...flowConfig.nodes].sort((a,b)=>a.x-b.x||a.y-b.y);
    if(nodes.length<2)return;
    const edges=[...flowConfig.edges];let added=0;
    const reaches=(start,target)=>{const seen=new Set(),pending=[start];while(pending.length){const current=pending.pop();if(current===target)return true;if(seen.has(current))continue;seen.add(current);edges.filter(edge=>edge.from===current).forEach(edge=>pending.push(edge.to));}return false;};
    nodes.slice(0,-1).forEach((node,index)=>{const next=nodes[index+1];if(edges.some(edge=>edge.from===node.id&&edge.to===next.id))return;if(reaches(next.id,node.id))return;edges.push({id:crypto.randomUUID(),from:node.id,to:next.id,label:'Próximo'});added++;});
    setFlowConfig(current=>({...current,edges}));
    setFlowLayoutNote(added?`${added} conexão${added===1?'':'ões'} adicionada${added===1?'':'s'} na ordem visual. Revise o caminho antes de publicar.`:'Não havia conexões seguras a adicionar. Revise a posição dos blocos ou as ramificações existentes.');
  };
  const addJourneySuggestion = suggestion => {
    const ids=new Set(flowConfig.nodes.map(node=>node.id));
    if(!ids.has(suggestion.from)||!ids.has(suggestion.to)){
      setJourneyError('Este caminho pertence à publicação atual, mas suas etapas já mudaram no rascunho. Revise antes de adicioná-lo.');return;
    }
    setFlowConfig(current=>current.edges.some(edge=>edge.from===suggestion.from&&edge.to===suggestion.to)?current:{...current,edges:[...current.edges,{id:crypto.randomUUID(),from:suggestion.from,to:suggestion.to,variant:'planned',label:'Caminho observado'}]});
    setEditorMode('edit');setFlowLayoutNote('Caminho observado adicionado ao rascunho. Revise antes de publicar.');
  };
  liveEditorRef.current = {id:selectedFlowId,name:flowName,config:flowConfig};
  const saveFlow = async () => {
    while (savePromiseRef.current) {
      const previous = await savePromiseRef.current;
      if (!previous) return false;
    }
    const snapshot = {...liveEditorRef.current};
    if (!snapshot.id || !revisionRef.current) return false;
    const serialized = JSON.stringify({name:snapshot.name,config:snapshot.config});
    if (serialized === savedSnapshotRef.current) return revisionRef.current;
    editorSavingRef.current=true;setEditorSaveState('saving');setLocalError('');setSaveFailure(null);
    const pending = (async()=>{
      try {
        const result=await save(`/flow/flows/${snapshot.id}`,{name:snapshot.name,config:syncGroups(snapshot.config),expected_revision:revisionRef.current},false,'PATCH');
        revisionRef.current=result.flow.draft_revision;
        savedSnapshotRef.current=serialized;
        setFlow(current=>({...current,flows:current.flows.map(item=>item.id===snapshot.id?{...item,...result.flow}:item)}));
        setEditorSaveState('saved');setLastSavedAt(Date.now());
        return result.flow.draft_revision;
      } catch(failure){setSaveFailure(failure.details||null);setEditorSaveState('error');if(failure.details?.node_ids?.length){setSelectedNodeIds(failure.details.node_ids);setSelectedNodeId(failure.details.node_ids[0]);setInspectorOpen(true);}setLocalError(failure.message);if(failure.status===409){setDraftConflict(true);json(`/connect/api/v2/reports/flow?client_id=${data.client.client_id}&flow_id=${snapshot.id}&view=edit`).then(result=>setRemoteRevision(result.flows.find(item=>item.id===snapshot.id)?.draft_revision??null)).catch(()=>{});}return false;}
      finally{editorSavingRef.current=false;}
    })();
    savePromiseRef.current=pending;
    try{return await pending;}finally{if(savePromiseRef.current===pending)savePromiseRef.current=null;}
  };
  const resolveDraftConflict = async overwrite => {
    const snapshot = {...liveEditorRef.current};
    try {
      const result = await json(`/connect/api/v2/reports/flow?client_id=${data.client.client_id}&flow_id=${selectedFlowId}&view=edit`);
      const latest = result.flows.find(item=>item.id===selectedFlowId);
      if(!latest)throw new Error('O fluxo não está mais disponível para este cliente.');
      if(overwrite){
        const saved = await save(`/flow/flows/${selectedFlowId}`,{name:snapshot.name,config:syncGroups(snapshot.config),expected_revision:latest.draft_revision},false,'PATCH');
        adoptDraft(saved.flow);
      }else{
        adoptDraft(latest);
        flowHistory.reset(latest.config);
      }
      setDraftConflict(false);setRemoteRevision(null);setEditorSaveState('saved');setLastSavedAt(Date.now());setLocalError('');
    }catch(failure){setLocalError(failure.message);if(failure.status!==409)setDraftConflict(false);}
  };
  const leaveEditor = async () => {
    if(draftConflict)return;
    if(editorDirty && !await saveFlow())return;
    location.assign(reportUrl('flows',{client_id:data.client.client_id}));
  };
  const openPublication = async () => {
    if(!selectedFlowId||publicationBusy||publishBlocked(validationIssues))return;
    setPublishedConfig(null);setPublicationNote('');
    if(selectedFlow?.published_revision)try{
      const result=await json(`/connect/api/v2/reports/flow/flows/${selectedFlowId}/versions/${selectedFlow.published_revision}?client_id=${data.client.client_id}`);
      setPublishedConfig(result.version.config);
    }catch(failure){setLocalError(`Não foi possível comparar com a publicação atual: ${failure.message}`);return;}
    setPublicationOpen(true);
  };
  const publishFlow = async () => {
    if(!selectedFlowId||publicationBusy||publishBlocked(validationIssues))return;
    setPublicationBusy(true);
    try {
      const config={...flowConfig,settings:{...(flowConfig.settings||{}),publication_note:publicationNote.trim()}};
      liveEditorRef.current={...liveEditorRef.current,config};setFlowConfig(config);
      const revision=await saveFlow();if(!revision)return;
      const result=await save(`/flow/flows/${selectedFlowId}/publish`,{expected_revision:revision},false);
      setPublicationOpen(false);await reload();setVersionMessage(`Versão ${result.flow.published_revision} publicada. Aguardando os próximos eventos reais.`);
    }catch(failure){if(failure.status===422&&failure.details?.items){setValidationOpen(true);setPublicationOpen(false);setLocalError('Resolva as pendências bloqueantes antes de publicar.');}else setLocalError(failure.message);}finally{setPublicationBusy(false);}
  };
  const loadVersions = async () => {try{const result=await json(`/connect/api/v2/reports/flow/flows/${selectedFlowId}/versions?client_id=${data.client.client_id}`);setVersions(result.versions);}catch(failure){setLocalError(failure.message);}};
  const compareVersion = async revision => {try{const result=await json(`/connect/api/v2/reports/flow/flows/${selectedFlowId}/versions/${revision}?client_id=${data.client.client_id}`);setVersionComparison({revision,...flowChangeSummary(result.version.config,flowConfig)});}catch(failure){setLocalError(failure.message);}};
  const restoreVersion = async revision => {
    if(!window.confirm('Restaurar esta versão como rascunho? A publicação atual continuará ativa.')||!startCommand())return;
    try{
      if(!await saveFlow())return;
      const result=await save(`/flow/flows/${selectedFlowId}/versions/${revision}/restore`,{expected_revision:revisionRef.current},false);
      adoptDraft(result.flow);setVersionMessage('Versão restaurada como rascunho. Revise antes de publicar.');
    }catch(failure){setLocalError(failure.message);}finally{endCommand();}
  };
  const adoptDraft = draft => {
    revisionRef.current=draft.draft_revision;
    savedSnapshotRef.current=JSON.stringify({name:draft.name,config:draft.config});
    setFlowName(draft.name);setFlowConfig(draft.config);
    setFlow(current=>({...current,flows:current.flows.map(item=>item.id===draft.id?{...item,...draft}:item)}));
  };
  const configureMonitor = async enabled => {if(!selectedFlowId)return;try{await save(`/flow/flows/${selectedFlowId}/monitor`,{enabled,interval_minutes:monitorInterval},false,'PATCH');await reload();}catch(failure){setLocalError(failure.message);}};
  const checkMonitorNow = async () => {if(!selectedFlowId||monitorBusy)return;setMonitorBusy(true);setLocalError('');try{await save(`/flow/flows/${selectedFlowId}/monitor/check`,{},false);await reload();}catch(failure){setLocalError(failure.message);}finally{setMonitorBusy(false);}};
  const discoverSite = async () => {
    if(!selectedFlowId||discoveryBusy||!startCommand())return;
    const current=flow.flows.find(item=>item.id===selectedFlowId);
    if(!current){endCommand();return;}
    setDiscoveryBusy(true);setLocalError('');
    try{
      if(!await saveFlow())return;
      // One bounded batch per click. More pages are fetched only when the user asks again.
      const previous=discovery.run;
      const resume=previous?.status==='partial'&&Number(previous.pending_count)>0;
      const result=await save(`/flow/flows/${selectedFlowId}/discover`,{
        root_url:`https://${current.allowed_host}`,assemble:true,expected_revision:revisionRef.current,
        ...(resume?{run_id:previous.id}:{})},false);
      const run=result.run;
      setFlowSuggestions({flowId:selectedFlowId,runId:run.id,items:result.suggestions||[]});
      setSelectedSuggestions([]);
      if(result.flow)adoptDraft(result.flow);
      await loadDiscoveries(selectedFlowId);
      if(run.status==='failed'){setLocalError('Não encontramos páginas acessíveis. Confira o domínio e o sitemap.');return;}
      setFlowLayoutNote(result.limit?.reached?`${run.page_count} páginas mapeadas · limite de ${result.limit.cap} atingido`:`${run.page_count} páginas analisadas · grupos por seção · conexões por links do site`);
      if(result.omitted_pages)setLocalError('O rascunho atingiu 200 blocos. As demais páginas ficam na lista de descoberta.');
    }catch(failure){setLocalError(failure.message);}
    finally{setDiscoveryBusy(false);endCommand();}
  };
  const createSuggestedFlows = async keys => {
    if(!keys.length||!startCommand())return;
    try{
      if(!await saveFlow())return;
      const result=await save(`/flow/flows/${selectedFlowId}/discovery-flows`,{
        run_id:flowSuggestions.runId,groups:keys,expected_revision:revisionRef.current},false);
      setFlowSuggestions(null);await reload();
      setVersionMessage(`${plural(result.flows.length,'fluxo criado','fluxos criados')} como rascunho.`);
    }catch(failure){setLocalError(failure.message);}finally{endCommand();}
  };
  const linkTranslation = async (page,target) => {
    if(!startCommand())return;
    try{
      await save(`/flow/flows/${selectedFlowId}/translations`,{page_id:String(page.id),translation_page_id:String(target.id)},false);
      await loadDiscoveries(selectedFlowId);
      setVersionMessage(`Tradução de “${page.title_clean}” vinculada a “${target.title_clean}”.`);
    }catch(failure){setLocalError(failure.message);}finally{endCommand();}
  };
  const chooseDiscoveredPage = async (page,selection,campaignId,suggestion,pageTypeSelection) => {
    if(!startCommand())return;
    if(campaignId===undefined){const node=flowConfig.nodes.find(item=>item.discoveryPageId===String(page.id));campaignId=node&&Object.prototype.hasOwnProperty.call(node,'campaign_id')?node.campaign_id:page.campaign_id||null;}
    try{
      if(!await saveFlow())return;
      if(suggestion && suggestion.base_revision!==revisionRef.current)throw new Error('O rascunho mudou. Solicite uma nova sugestão.');
      setDiscoveryBusy(true);setLocalError('');
      const result=await save(`/flow/flows/${selectedFlowId}/discoveries/${page.id}/select`,{selection,campaign_id:selection==='ignore'?null:campaignId,expected_revision:revisionRef.current,...(suggestion?{suggestion_id:suggestion.suggestion_id,page_type_selection:pageTypeSelection}:{})},false);
      adoptDraft(result.flow);await loadDiscoveries(selectedFlowId);
    }catch(failure){setLocalError(failure.message);}finally{setDiscoveryBusy(false);endCommand();}
  };
  const suggestPageRole = async page => {
    if(!await saveFlow())return;
    const requestedFlow=selectedFlowId;
    setSuggestingPage(String(page.id));
    try{const result=await save(`/flow/flows/${requestedFlow}/discoveries/${page.id}/suggest`,{},false);
      if(liveEditorRef.current.id===requestedFlow)setPageSuggestions(current=>({...current,[page.id]:result}));
    }catch(failure){setLocalError(failure.message);}finally{setSuggestingPage('');}
  };
  const copy = async value => {try {await navigator.clipboard.writeText(value); setCopyState('Copiado'); window.setTimeout(() => setCopyState(''), 1800);} catch (_) {setCopyState('Não foi possível copiar');}};
  const superTagForFlow = flowItem => flow.supertag_sites?.find(site => {
    const allowed = String(site.allowed_host || '').toLowerCase().replace(/^www\./, '');
    const target = String(flowItem?.allowed_host || '').toLowerCase().replace(/^www\./, '');
    return target === allowed || target.endsWith(`.${allowed}`);
  });
  const snippet = flowItem => {
    const site = superTagForFlow(flowItem);
    if (!site) return '';
    return site.snippet || '';
  };
  const flowFallbackSnippet = flowItem => flowItem?.public_key && flowItem?.flow_code && !flowItem?.revoked_at
    ? `<script async src="${location.origin}/v2/flow.js?client=${encodeURIComponent(data.client.client_id)}" data-cadu-key="${flowItem.public_key}" data-cadu-client="${data.client.client_id}" data-cadu-flow="${flowItem.flow_code}"></script>`
    : '';
  const selectedFlow = flow.flows.find(item => item.id === selectedFlowId);
  const trackingReady=useFlowReadiness(selectedFlowId,data.client.client_id);
  useEffect(()=>{
    if((editorMode!=='journey'&&(flowView!=='monitor'||workspaceV2))||!selectedFlowId)return;
    let cancelled=false;setJourneyLoading(true);setJourneyError('');
    json(`/connect/api/v2/reports/flow/flows/${selectedFlowId}/journey?client_id=${data.client.client_id}&days=${journeyDays}`)
      .then(result=>{if(!cancelled)setJourneyData(result);})
      .catch(failure=>{if(!cancelled)setJourneyError(failure.message);})
      .finally(()=>{if(!cancelled)setJourneyLoading(false);});
    return()=>{cancelled=true;};
  },[editorMode,flowView,selectedFlowId,journeyDays,selectedFlow?.published_revision,data.client.client_id]);
  const validationIssues = useMemo(()=>[...flowValidation(flowConfig,selectedFlow?.allowed_host),...(trackingReady===false?[{severity:'warning',code:'tracking_not_ready',message:'Super Tag sem eventos recebidos nas últimas 24 horas.',consequence:'As métricas do fluxo podem ficar sem dados até a coleta voltar.',action:'check_supertag'}]:trackingReady===undefined?[{severity:'warning',code:'tracking_unknown',message:'Coleta ainda não verificada.',consequence:'As métricas do fluxo podem ficar sem dados até a instalação ser confirmada.',action:'check_supertag'}]:[])],[flowConfig,selectedFlow?.allowed_host,trackingReady]);
  const blockingIssues=validationIssues.filter(issue=>issue.severity==='error'||issue.severity==='bloqueante');
  const focusIssue=issue=>{
    if(issue.action==='add_conversion'){addNode('conversion');setValidationOpen(false);return;}
    if(issue.action==='confirm_goal'){setBlueprintOpen(true);setValidationOpen(false);return;}
    if(issue.action==='check_supertag'){location.assign(reportUrl('supertag'));return;}
    const edge=flowConfig.edges.find(item=>item.id===issue.edgeId);
    const ids=edge?[edge.from,edge.to]:issue.nodeId?[issue.nodeId]:[];
    if(ids.length){setSelectedNodeId(issue.nodeId||ids[0]);setInspectorOpen(true);canvasFlowRef.current?.fitView({nodes:ids.map(id=>({id})),padding:.65,maxZoom:1,duration:220});}
    setValidationOpen(false);
  };
  const issueActionLabel=issue=>({add_conversion:'Adicionar nó de Conversão',confirm_goal:'Revisar objetivo',check_supertag:'Verificar Super Tag',review_return:'Localizar Retorno',connect_node:'Conectar nó',connect_to_conversion:'Conectar à Conversão',configure_url:'Configurar URL',configure_event:'Configurar evento',review_duplicate:'Revisar URL'})[issue.action]||'Localizar no fluxo';
  const readOnly = data.client.role === 'viewer' || commandBusy || navigationOnly;
  const editorDirty = Boolean(selectedFlow && JSON.stringify({name:flowName,config:flowConfig}) !== savedSnapshotRef.current);
  useEffect(() => {
    if (flowView!=='edit' || flowHistory.isInteracting || !selectedFlowId || !selectedFlow || readOnly || !editorDirty || editorSaveState==='error' || draftConflict) return;
    const timer=window.setTimeout(()=>saveFlow(),1000);
    return()=>window.clearTimeout(timer);
  },[selectedFlowId,selectedFlow?.draft_revision,flowName,flowConfig,editorDirty,readOnly,editorSaveState,draftConflict,flowHistory.isInteracting,flowView]);
  useEffect(()=>{
    if(flowView!=='edit')return;
    const shortcut=event=>{
      if(event.key==='Escape'&&!event.defaultPrevented&&!event.target.closest('input,textarea,select,[role="dialog"]')){event.preventDefault();if(validationOpen)setValidationOpen(false);else if(inspectorOpen){setInspectorOpen(false);setSelectedNodeId('');}else if(paletteOpen)setPaletteOpen(false);else if(editorMode!=='edit')setEditorMode('edit');return;}
      if(editorMode!=='edit')return;
      if(event.target.closest('input,textarea,select,[contenteditable="true"],[role="dialog"]'))return;
      const mod=event.metaKey||event.ctrlKey;
      const key=event.key.toLowerCase();
      const movement={arrowleft:[-12,0],arrowright:[12,0],arrowup:[0,-12],arrowdown:[0,12]}[key];
      if(movement&&!mod&&!readOnly&&(selectedNodeIds.length||selectedNodeId)){
        event.preventDefault();
        const ids=new Set(selectedNodeIds.length?selectedNodeIds:[selectedNodeId]);
        setFlowConfig(current=>({...current,nodes:current.nodes.map(node=>ids.has(node.id)&&!node.locked?movement[0]?(node.type==='source'?node:{...placeNodeInStage(node,FLOW_STAGES[Math.max(1,Math.min(FLOW_STAGES.length-1,FLOW_STAGES.findIndex(stage=>stage.id===node.stage)+(movement[0]>0?1:-1)))].id),manuallyEdited:true}):{...node,manuallyEdited:true,y:Math.max(0,Math.min(10000,Number(node.y)+movement[1]))}:node)}));
        return;
      }
      if(mod&&key==='z'&&!readOnly){event.preventDefault();if(event.shiftKey)flowHistory.redo();else flowHistory.undo();}
      else if(mod&&key==='c'&&!readOnly){copySelection();}
      else if(mod&&key==='v'&&!readOnly&&copiedNodesRef.current){event.preventDefault();pasteSelection();}
      else if(mod&&key==='d'&&!readOnly){event.preventDefault();duplicateSelection();}
      else if(key==='b'&&!mod){event.preventDefault();setPaletteOpen(value=>!value);}
      else if(event.shiftKey&&event.key==='1'){event.preventDefault();fitCanvas();}
      else if(mod&&(key==='+'||key==='=')){event.preventDefault();changeZoom(canvasZoom+.1);}
      else if(mod&&key==='-'){event.preventDefault();changeZoom(canvasZoom-.1);}
    };
    window.addEventListener('keydown',shortcut);
    return()=>window.removeEventListener('keydown',shortcut);
  },[flowView,editorMode,flowHistory.undo,flowHistory.redo,canvasZoom,readOnly,selectedNodeIds,selectedNodeId,flowConfig,draftConflict,paletteOpen,inspectorOpen,validationOpen]);
  useEffect(()=>{const protect=event=>{const current=liveEditorRef.current;if(flowView==='edit'&&selectedFlowId&&revisionRef.current&&current&&JSON.stringify({name:current.name,config:current.config})!==savedSnapshotRef.current){event.preventDefault();event.returnValue='';}};window.addEventListener('beforeunload',protect);return()=>window.removeEventListener('beforeunload',protect);},[flowView,selectedFlowId]);
  const scannedIntegrations = discovery.platform_integrations || [];
  const channelOrigins = FLOW_CHANNELS.map(channel => {
    const aliases = channel.aliases.map(value => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase());
    const events = (flow.events || []).filter(item => {
      const source = String(item.source_label || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
      return aliases.some(alias => source.includes(alias));
    });
    const detected = scannedIntegrations.filter(item => item.platform === channel.id);
    return {channel, total: events.reduce((sum, item) => sum + Number(item.total || 0), 0),
      sources: events.map(item => item.source_label), tags: detected.filter(item => item.signal === 'tracker'),
      links: detected.filter(item => item.signal === 'site_link')};
  });
  const addCatalogGroup=pages=>{
    setFlowConfig(current=>{
      const ids=[];const nodes=[...current.nodes];
      for(const page of pages){let node=nodes.find(n=>n.path===page.path_prefix&&(n.host||flowHost)===page.page_host&&n.type==='page');if(!node){if(nodes.length>=200)break;const stage=page.stage==='source'?'entry':page.stage||'exploration';node={id:crypto.randomUUID(),type:'page',title:page.title_clean,path:page.path_prefix,host:page.page_host,stage,pageType:'other',role:page.role,origin:'manual',discoveryPageId:String(page.id),x:stageX(stage),y:100+ids.length*240};nodes.push(node);}ids.push(node.id);}
      if(ids.length<2)return current;
      const translations=pages.length>1&&pages.every(page=>page.translation_key&&page.translation_key===pages[0].translation_key);
      return groupNodes({...current,nodes},ids,translations?`Traduções: ${pages[0].title_clean}`:pages[0]?.template_pattern||'Páginas');
    });
  };
  const mappedSitePages = flowConfig.nodes.filter(node => node.discoveryPageId).length;
  const visibleFlows=(flow.flows||[]).filter(item=>(flowStatusFilter==='all'||(flowStatusFilter==='published'?item.status==='published':item.status!=='published'))&&`${item.name} ${item.allowed_host}`.toLocaleLowerCase('pt-BR').includes(flowQuery.trim().toLocaleLowerCase('pt-BR')));
  const flowMonitorLabel=item=>item.monitor_enabled?({online:'Online',degraded:'Com falhas',offline:'Offline',checking:'Verificando',unknown:'Aguardando checagem'})[item.monitor_status]||'Ativo':'Não ativado';
  const flowUpdatedLabel=value=>{const date=new Date(value);return Number.isNaN(date.getTime())?'—':date.toLocaleDateString('pt-BR',{day:'2-digit',month:'short',year:'numeric'});};
  const flowCreateHint=!flowHost.trim()?'Informe a URL do site e valide o domínio.':!flowSiteCheck?'Valide o domínio para continuar.':flowSiteCheck.error?'Corrija o domínio para continuar.':superTagForFlow({allowed_host:flowSiteCheck.host})?'A Super Tag deste domínio já existe e será reutilizada.':'A Super Tag será criada automaticamente para este domínio.';
  if(workspaceV2&&flowView==='monitor'&&selectedFlow)return <FlowMonitorWorkspace csrf={data.csrf} flow={selectedFlow} client={data.client} versions={monitorVersions} filters={filters} baseConfig={selectedFlow.config} onEdit={()=>location.assign(flowEditorUrl(selectedFlowId,data.client.client_id))} onBack={()=>location.assign(reportUrl('flows',{client_id:data.client.client_id}))}/>;
  return <>
    {flowView==='monitor'&&<a className="reports-flow-return" href={reportUrl('flows',{client_id:data.client.client_id})}>← Voltar aos fluxos</a>}
    {localError&&flowView!=='edit'&&<div className="reports-error" role="alert">{localError}</div>}
    <FlowToast message={versionMessage} onDismiss={()=>setVersionMessage('')}/>
    <FlowToast message={flowLayoutNote} onDismiss={()=>setFlowLayoutNote('')}/>
    {draftConflict&&<ModalOverlay className="cadu-ds-overlay cadu-ds-overlay--center" isOpen isDismissable={false}><Modal className="cadu-ds-confirm"><Dialog aria-label="Conflito no rascunho" className="cadu-ds-confirm__dialog flow-publication-dialog"><h2>Este fluxo mudou em outra aba</h2><p>As alterações desta aba continuam aqui. Revisão local: r{revisionRef.current}. {remoteRevision==null?'Consultando a revisão mais recente…':`Revisão mais recente: r${remoteRevision}.`} Escolha qual versão manter antes de continuar a editar.</p><div className="cadu-ds-confirm__actions"><UntitledButton color="secondary" size="sm" isDisabled={busy} onPress={()=>resolveDraftConflict(false)}>Recarregar versão recente</UntitledButton><UntitledButton color="primary" size="sm" isDisabled={busy} onPress={()=>resolveDraftConflict(true)}>Substituir com minhas alterações</UntitledButton></div></Dialog></Modal></ModalOverlay>}
    {flowView==='edit'&&validationOpen&&<section className="reports-flow-validation" aria-label="Pendências do fluxo"><div><strong>{validationIssues.length?`${blockingIssues.length} bloqueantes · ${validationIssues.length-blockingIssues.length} avisos`:'Fluxo pronto para publicar'}</strong><button type="button" onClick={()=>setValidationOpen(false)} aria-label="Fechar pendências">×</button></div>{validationIssues.length?<>{[['Pendências que impedem publicar',blockingIssues],['Avisos de leitura e coleta',validationIssues.filter(item=>item.severity==='warning')]].map(([heading,items])=>items.length>0&&<div key={heading}><h3>{heading}</h3><ul>{items.map((issue,index)=><li className={`is-${issue.severity}`} key={`${issue.code}:${issue.nodeId||issue.edgeId||index}`}><span>{issue.message}</span><small>{issue.consequence}</small><button type="button" onClick={()=>focusIssue(issue)}>{issueActionLabel(issue)}</button></li>)}</ul></div>)}</>:<p>Nenhuma pendência encontrada nesta revisão.</p>}</section>}
    <FlowPublicationDialog open={publicationOpen} name={flowName} host={selectedFlow?.allowed_host} revision={revisionRef.current} config={flowConfig} previous={publishedConfig} issues={validationIssues} note={publicationNote} onNoteChange={setPublicationNote} busy={publicationBusy} onClose={()=>setPublicationOpen(false)} onPublish={publishFlow}/>
    {versions&&<section className="reports-flow-history"><h3>Versões publicadas</h3><button type="button" onClick={()=>{setVersions(null);setVersionComparison(null);}}>Fechar histórico</button>{versionComparison&&<p role="status">v{versionComparison.revision} → rascunho: etapas +{versionComparison.nodes.added} / −{versionComparison.nodes.removed} / {versionComparison.nodes.updated} alteradas; conexões +{versionComparison.edges.added} / −{versionComparison.edges.removed} / {versionComparison.edges.updated} alteradas.</p>}{versions.length?versions.map(item=><div key={item.revision}><span>Versão {item.revision} — {item.name}</span><button type="button" onClick={()=>compareVersion(item.revision)}>Comparar com rascunho</button><button type="button" disabled={readOnly||busy} onClick={()=>restoreVersion(item.revision)}>Restaurar como rascunho</button></div>):<p>Nenhuma versão publicada.</p>}</section>}
    {flowView==='create'&&<section className="reports-flow-index">
      <div className="reports-flow-index__tools">
        <ReportsFieldInput type="search" aria-label="Buscar fluxo" placeholder="Buscar por nome ou domínio" value={flowQuery} onChange={event=>setFlowQuery(event.target.value)}/>
        <ReportsNativeSelect aria-label="Estado do fluxo" value={flowStatusFilter} onChange={event=>setFlowStatusFilter(event.target.value)}><option value="all">Todos os estados</option><option value="published">Publicados</option><option value="draft">Rascunhos</option></ReportsNativeSelect>
        <span className="reports-flow-index__count">{plural(visibleFlows.length,'fluxo','fluxos')}</span>
        {data.client.role!=='viewer'&&<ReportsActionButton color="primary" className="reports-flow-index__new" onClick={()=>setFlowCreateOpen(true)}>Novo fluxo</ReportsActionButton>}
      </div>
      <article className="reports-panel reports-flow-index__panel">
        {visibleFlows.length?<div className="reports-table-wrap"><table className="reports-flow-table"><thead><tr><th>Fluxo</th><th>Estado</th><th>Coleta</th><th>Próxima ação</th><th>Atualizado</th><th><span className="reports-sr-only">Ações</span></th></tr></thead><tbody>{visibleFlows.map(item=>{const next=flowNextAction(item);return <tr key={item.id}>
          <td><strong>{item.name}</strong><small>{item.allowed_host}{item.campaign_names?` · ${item.campaign_names}`:''}</small></td>
          <td><span className={`reports-status-badge is-${item.status==='published'?'published':'draft'}`} title={item.flow_code}>{item.status==='published'?'Publicado':'Rascunho'}</span></td>
          <td>{flowMonitorLabel(item)}</td>
          <td><button type="button" className={`reports-flow-next is-${next.tone}`} onClick={()=>openFlow(item,next.view)}>{next.label}</button></td>
          <td>{flowUpdatedLabel(item.updated_at)}</td>
          <td className="reports-flow-table__actions"><ReportsActionButton color="tertiary" onClick={()=>openFlow(item,'edit')}>Editar</ReportsActionButton>{item.status==='published'&&<ReportsActionButton color="tertiary" onClick={()=>openFlow(item,'monitor')}>Monitorar</ReportsActionButton>}</td>
        </tr>;})}</tbody></table></div>:<Empty message={(flow.flows||[]).length?'Nenhum fluxo corresponde à busca.':'Nenhum fluxo ainda. Crie o primeiro para mapear a jornada de um site.'}/>}
      </article>
    </section>}
    {flowView==='create'&&<ReportsDrawer open={flowCreateOpen} onOpenChange={setFlowCreateOpen} onDiscard={()=>{setFlowName('');setFlowCustomerId('');setFlowCampaignId('');}} title="Novo fluxo" description="Defina o site e o ponto de partida da jornada." context={data.client.client_name}>
      {localError&&<div className="reports-error" role="alert">{localError}</div>}
      {data.client.role!=='viewer'?<form className="reports-form reports-flow-new" onSubmit={newFlow}>
        <div className="reports-flow-new__domain"><label>URL do site<ReportsFieldInput required type="url" value={flowHost} onChange={event=>{siteCheckSequence.current++;setFlowHost(event.target.value);setFlowSiteCheck(null);setFlowSiteChecking(false);}} placeholder="https://www.exemplo.com.br"/></label><ReportsActionButton color="secondary" disabled={!flowHost.trim()||flowSiteChecking} onClick={checkFlowSite}>{flowSiteChecking?'Verificando…':'Validar domínio'}</ReportsActionButton></div>
        {flowSiteCheck&&<div className={`reports-flow-site-check${flowSiteCheck.error?' has-error':''}`} role={flowSiteCheck.error?'alert':'status'}>{flowSiteCheck.error?<p>{flowSiteCheck.error}</p>:<><strong>{flowSiteCheck.title||flowSiteCheck.host}</strong><small>{flowSiteCheck.host} · HTTP {flowSiteCheck.status}</small></>}</div>}
        <label>Nome do fluxo<ReportsFieldInput maxLength="120" value={flowName} onChange={event=>setFlowName(event.target.value)} placeholder={flowSiteCheck?.title||'Ex.: Campanha de aquisição 2026'}/></label>
        <label>Tipo de site<ReportsNativeSelect value={flowSiteKind} onChange={event=>setFlowSiteKind(event.target.value)}><option value="">Descobrir no teste da página inicial</option><option value="landing">Landing page · passos dentro da página</option><option value="institucional">Institucional · menu e contato</option><option value="multipagina">Muitas páginas · conteúdo e leads</option><option value="ecommerce">E-commerce · produto, carrinho e compra</option></ReportsNativeSelect><small>Define como o caminho até a conversão é montado. Você pode mudar depois.</small></label>
        <details className="reports-flow-new__optional"><summary>Associações <small>Opcional</small></summary>
          <label>Cliente / anunciante<ReportsNativeSelect value={flowCustomerId} onChange={event=>{setFlowCustomerId(event.target.value);setFlowCampaignId('');}}><option value="">Sem anunciante</option>{(data.customers||[]).filter(item=>item.status==='active').map(item=><option key={item.id} value={item.id}>{item.name}</option>)}</ReportsNativeSelect></label>
          <label>Campanha<ReportsNativeSelect value={flowCampaignId} onChange={event=>setFlowCampaignId(event.target.value)}><option value="">Sem campanha</option>{(data.campaigns||[]).filter(item=>!flowCustomerId||String(item.customer_id)===flowCustomerId).map(item=><option key={item.id} value={item.id}>{item.name}</option>)}</ReportsNativeSelect></label>
        </details>
        <div className="reports-flow-new__actions"><p id="flow-create-hint">{flowCreateHint}</p><ReportsActionButton type="submit" color="primary" disabled={busy||flowSiteChecking||!flowSiteCheck||Boolean(flowSiteCheck.error)} aria-describedby="flow-create-hint">Criar fluxo</ReportsActionButton></div>
      </form>:<Empty message="Seu acesso permite acompanhar fluxos existentes."/>}
    </ReportsDrawer>}
    {flowView==='edit'&&(selectedFlow?<>
      <section className={`reports-panel reports-flow-builder is-${editorMode}${workspaceV2?' is-workspace-v2':''}`} {...(commandBusy?{inert:'','aria-busy':true}:{})}>
        <header className="reports-flow-topbar reports-flow-editor-topbar">
          <div className="reports-flow-editor-identity"><FlowSolutionSwitcher/><a href={reportUrl('flows',{client_id:data.client.client_id})} aria-label="Voltar aos fluxos" onClick={event=>{event.preventDefault();leaveEditor();}}>← Fluxos</a><span aria-hidden="true">/</span><input aria-label="Nome do fluxo" value={flowName} readOnly={readOnly} onChange={event=>setFlowName(event.target.value)} maxLength="120"/><small>{selectedFlow?.status==='published'?`Publicado v${selectedFlow.published_revision}`:'Rascunho'}</small><details className={`reports-flow-save-state is-${editorSaveState}`}><summary role="status">{editorSaveState==='error'?'Falha ao salvar':editorSaveState==='saving'?'Salvando…':editorDirty?'Alterações pendentes':selectedFlow?.status==='published'&&Number(selectedFlow.draft_revision)>Number(selectedFlow.published_revision)?'Alterações não publicadas':savedAgo(lastSavedAt,statusClock)}</summary><div>{localError||'Rascunho salvo'}<small>Revisão do rascunho: {revisionRef.current}</small>{saveFailure?.request_id&&<small>Referência: {saveFailure.request_id}</small>}{saveFailure?.node_ids?.map(id=><ReportsActionButton key={id} onClick={()=>{setSelectedNodeId(id);canvasFlowRef.current?.fitView({nodes:[{id}],padding:.6});}}>Localizar {flowConfig.nodes.find(n=>n.id===id)?.title||'nó'}</ReportsActionButton>)}{localError&&<ReportsActionButton onClick={saveFlow}>Tentar salvar novamente</ReportsActionButton>}</div></details></div>
          <div className="reports-flow-editor-modes" role="group" aria-label="Modo do fluxo"><button type="button" aria-current={editorMode==='edit'?'page':undefined} onClick={()=>{setEditorMode('edit');setSimulatedPath([]);}}>Editar</button><button type="button" aria-current={editorMode==='journey'?'page':undefined} onClick={()=>workspaceV2?openFlow(selectedFlow,'monitor'):setEditorMode('journey')} disabled={selectedFlow?.status!=='published'} title={selectedFlow?.status!=='published'?'Publique o fluxo para acompanhar a jornada':undefined}>Monitorar</button></div>
          <div className="reports-flow-actions"><ReportsActionButton aria-label="Desfazer" title="Desfazer (⌘Z)" onClick={flowHistory.undo} disabled={!flowHistory.canUndo||readOnly}><FlipBackward size={16}/></ReportsActionButton><ReportsActionButton aria-label="Refazer" title="Refazer (⌘⇧Z)" onClick={flowHistory.redo} disabled={!flowHistory.canRedo||readOnly}><FlipForward size={16}/></ReportsActionButton>{snippet(selectedFlow)?<ReportsActionButton onClick={()=>copy(snippet(selectedFlow))}>Copiar Super Tag</ReportsActionButton>:null}<ReportsActionButton className="reports-flow-issues-button" aria-label={`${validationIssues.length} problemas ou avisos no fluxo`} onClick={()=>setValidationOpen(value=>!value)}>{validationIssues.length?plural(validationIssues.length,'pendência','pendências'):'Pronto'}</ReportsActionButton><ReportsActionButton color="primary" className="reports-flow-publish" onClick={openPublication} disabled={!selectedFlowId||busy||!flowConfig.nodes.length||readOnly||blockingIssues.length>0} aria-describedby={blockingIssues.length?'flow-publish-blocked':undefined}>{selectedFlow?.status==='published'?'Publicar alterações':'Publicar'}</ReportsActionButton>{blockingIssues.length>0&&<button type="button" id="flow-publish-blocked" className="reports-flow-publish-hint" aria-label={`Resolva ${plural(blockingIssues.length,'pendência bloqueante','pendências bloqueantes')} para publicar`} title={`Resolva ${plural(blockingIssues.length,'pendência bloqueante','pendências bloqueantes')} para publicar`} onClick={()=>setValidationOpen(true)}>{`Ver ${plural(blockingIssues.length,'bloqueio','bloqueios')}`}</button>}<details className="reports-flow-extra-actions"><summary aria-label="Mais ações">⋯</summary><div><ReportsActionButton onClick={()=>setEditorMode('simulate')} disabled={!flowConfig.nodes.length}>Simular</ReportsActionButton><ReportsActionButton onClick={()=>autoArrange('free')}>Organizar livre</ReportsActionButton><ReportsActionButton onClick={loadVersions}>Histórico</ReportsActionButton><ReportsActionButton onClick={()=>downloadFlowSvg(flowConfig,flowName||'fluxo')}>Exportar SVG</ReportsActionButton><ReportsActionButton onClick={()=>downloadFlowPng(flowConfig,flowName||'fluxo').catch(failure=>setLocalError(failure.message))}>Exportar PNG</ReportsActionButton>{!snippet(selectedFlow)&&<ReportsActionButton onClick={()=>selectedFlow?.revoked_at?location.assign(reportUrl('supertag')):copy(flowFallbackSnippet(selectedFlow))} disabled={(!flowFallbackSnippet(selectedFlow)&&!selectedFlow?.revoked_at)||data.client.role==='viewer'}>{selectedFlow?.revoked_at?'Conectar Super Tag':'Copiar snippet'}</ReportsActionButton>}</div></details></div>
        </header>
        {flowSuggestions?.flowId===selectedFlowId&&flowSuggestions.items.length>0&&!discoveryBusy&&<section className="reports-panel" aria-label="Outros fluxos identificados">
          <h3>Deseja criar os outros fluxos identificados?</h3>
          <p>As páginas principais já estão no rascunho. Escolha as landing pages e outras seções que deseja organizar em fluxos separados.</p>
          {flowSuggestions.items.map(item=><label key={item.id} style={{display:'block',padding:'8px 0'}}><input type="checkbox" checked={selectedSuggestions.includes(item.id)} disabled={readOnly} onChange={event=>setSelectedSuggestions(current=>event.target.checked?[...current,item.id]:current.filter(id=>id!==item.id))}/>{' '}{item.name} · {item.page_count} páginas</label>)}
          <div className="reports-form-actions"><ReportsActionButton disabled={readOnly||!selectedSuggestions.length} onClick={()=>createSuggestedFlows(selectedSuggestions)}>Criar selecionados</ReportsActionButton><ReportsActionButton disabled={readOnly} onClick={()=>createSuggestedFlows(flowSuggestions.items.map(item=>item.id))}>Criar todos</ReportsActionButton><ReportsActionButton disabled={readOnly} onClick={()=>setFlowSuggestions(null)}>Agora não</ReportsActionButton></div>
        </section>}

        <div className="reports-editor-controls" role="toolbar" aria-label="Visualização do editor">
          <div className="reports-flow-palette-switch"><ReportsActionButton aria-label="Montar a partir do site" title="Montar a partir do site" disabled={readOnly} onClick={()=>setBlueprintOpen(true)}><Plus size={18}/></ReportsActionButton><ReportsActionButton aria-pressed={paletteOpen&&paletteMode==='site'} onClick={()=>{setPaletteMode('site');if(paletteMode==='site'&&paletteOpen)setPaletteOpen(false);else panelLayout.openExplorer();}}><SearchLg size={18}/><span className="reports-sr-only">Explorar páginas</span></ReportsActionButton><ReportsActionButton aria-pressed={paletteOpen&&paletteMode==='blocks'} onClick={()=>{setPaletteMode('blocks');if(paletteMode==='blocks'&&paletteOpen)setPaletteOpen(false);else panelLayout.openExplorer();}}><Plus size={18}/><span className="reports-sr-only">Adicionar nós</span></ReportsActionButton></div>
          <div className="reports-zoom-controls"><ReportsActionButton aria-label="Diminuir zoom" disabled={canvasZoom<=.25} onClick={()=>changeZoom(canvasZoom-.1)}>−</ReportsActionButton><ReportsActionButton aria-label="Restaurar zoom a 100%" onClick={()=>changeZoom(1)}>{Math.round(canvasZoom*100)}%</ReportsActionButton><ReportsActionButton aria-label="Aumentar zoom" disabled={canvasZoom>=2} onClick={()=>changeZoom(canvasZoom+.1)}>+</ReportsActionButton><ReportsActionButton onClick={fitCanvas}>Ajustar à tela</ReportsActionButton><ReportsActionButton onClick={autoArrange} disabled={readOnly||!flowConfig.nodes.length} title="Organizar etapas da esquerda para a direita">Organizar fluxo</ReportsActionButton></div>
          <ReportsActionButton title="Sugestões" aria-label="Sugestões" onClick={()=>setSuggestionToggle(v=>v+1)}><Lightbulb02 size={18}/></ReportsActionButton><ReportsActionButton title="Organizar por etapas" aria-label="Organizar por etapas" onClick={()=>autoArrange()} disabled={readOnly}><LayoutGrid01 size={18}/></ReportsActionButton><ReportsActionButton title="Revisar fluxo" aria-label="Revisar fluxo" onClick={()=>setValidationOpen(v=>!v)}><CheckDone01 size={18}/></ReportsActionButton><ReportsActionButton disabled={readOnly||selectedNodeIds.length<2} onClick={()=>setFlowConfig(current=>groupNodes(current,selectedNodeIds))} title="Agrupar seleção" aria-label="Agrupar seleção"><LayoutGrid01 size={16}/></ReportsActionButton><details className="reports-editor-tools"><summary>Ferramentas</summary><div><ReportsActionButton onClick={()=>setSnapToGrid(value=>!value)} aria-pressed={snapToGrid}>{snapToGrid?'Desativar grade':'Ativar grade'}</ReportsActionButton><ReportsActionButton onClick={autoConnect} disabled={readOnly||flowConfig.nodes.length<2}>Conectar sequência</ReportsActionButton></div></details>
        </div>
        <div className={`reports-flow-designer reports-flow-designer--compact${paletteOpen?' has-palette':''}${inspectorOpen?' has-inspector':''}`}><ReportsPanelShell className="reports-node-palette" title={paletteMode==='site'?'Explorar site':'Nós do fluxo'} description={paletteMode==='site'?'Páginas verificadas do domínio':'Arraste ou selecione um nó'} closeLabel="Fechar explorador" onClose={workspaceV2?()=>setPaletteOpen(false):undefined}>{paletteMode==='site'?<><div className="reports-palette-group reports-discovered-palette"><div className="reports-discovered-head"><strong>Páginas do site</strong><button type="button" disabled={discoveryBusy||busy||readOnly||(discovery.run?.status==='partial'&&!Number(discovery.run?.pending_count))} onClick={discoverSite} title="Mapear páginas verificadas do domínio. Cada clique analisa um lote limitado.">{discoveryBusy?'Mapeando…':discovery.run?.status==='partial'&&Number(discovery.run.pending_count)>0?'Mapear mais páginas':discovery.run?'Atualizar mapa':'Mapear site'}</button></div><p className="reports-discovered-summary" title="Inclui só páginas HTML verificadas; redirecionamentos e erros não entram na contagem.">{discoveryBusy?'Analisando páginas…':discovery.run?.status==='failed'?'A análise falhou. Confira o domínio e tente novamente.':discovery.run?`${plural(discovery.summary?.validas??discovery.catalog?.length??0,'página verificada','páginas verificadas')} · ${discovery.summary?.no_fluxo??mappedSitePages} no fluxo`:'Analise o domínio e o sitemap para usar páginas reais neste fluxo.'}</p>{discovery.run&&<small className="reports-discovered-limit">{discovery.run.status==='partial'?`Análise parcial · limite de ${discovery.limit?.cap||100} páginas por mapeamento`:`Limite de ${discovery.limit?.cap||100} páginas por mapeamento`}</small>}<FlowCatalog onLinkTranslation={readOnly?undefined:linkTranslation} onClassify={suggestPageRole} suggestions={pageSuggestions} classifying={suggestingPage} onAcceptSuggestion={(page,suggestion,decision)=>chooseDiscoveredPage(page,decision.role,undefined,suggestion,decision.pageType)} onAddGroup={addCatalogGroup} items={discovery.catalog||[]} nodes={flowConfig.nodes} disabled={readOnly||discoveryBusy} onLocate={id=>{setSelectedNodeId(id);canvasFlowRef.current?.fitView({nodes:[{id}],duration:200,padding:.6});}} onAdd={page=>chooseDiscoveredPage(page,page.role==='entry'?'entry':['form','conversion','error'].includes(page.role)?page.role:'intermediate')}/></div></>:<><div className="reports-palette-heading"><strong>Nós do fluxo</strong><small>Arraste para o canvas ou selecione</small></div><ReportsFieldInput type="search" aria-label="Buscar nós" placeholder="Buscar nós…" value={paletteQuery} onChange={event=>setPaletteQuery(event.target.value)}/>{flowPaletteGroups.map(([heading,items])=><div className="reports-palette-group" id={heading==='Eventos'?'reports-palette-events':undefined} key={heading}><strong>{heading}</strong>{heading==='Eventos'&&<><small>Use eventos recebidos pela Super Tag. Nome e URL precisam corresponder ao site conectado.</small>{uniqueFlowEvents(flow.events).filter(event=>event.event_kind==='custom_event'&&/^[A-Za-z][A-Za-z0-9_]{0,79}$/.test(event.event_name||'')&&/^\/[^?#]*$/.test(event.page_path||'')).map(event=><button type="button" className="reports-observed-event" key={`${event.event_name}:${event.page_path}`} disabled={readOnly} onClick={()=>addNode('event',{kind:'event.custom',title:event.event_name,path:event.page_path,event_name:event.event_name})}><span className="reports-palette-icon">◉</span><span>{event.event_name}<small>{event.page_path} · {integer(event.total)} eventos</small></span></button>)}</>}{heading==='Segmentação e CRM'&&<small>Nós visuais. Confirmações do CRM chegam por webhook nas Integrações deste cliente; API para CRM próprio em breve.</small>}{items.filter(item=>item.label.toLowerCase().includes(paletteQuery.toLowerCase())).map((item,index)=><button type="button" key={`${item.type}:${item.source||''}:${index}`} draggable={!readOnly} disabled={readOnly} onDragStart={event=>startPaletteDrag(event,item)} onClick={()=>clickPaletteNode(item)}><span className="reports-palette-icon">{item.source&&FLOW_PLATFORMS[item.source]?<FlowPlatformLogo platform={item.source}/>:<item.icon size={18}/>}</span>{item.label}</button>)}</div>)}</>}</ReportsPanelShell>
          <FlowStudioAssist onShowReturns={()=>canvasFlowRef.current?.toggleReturns?.()} onAddPage={page=>!readOnly&&chooseDiscoveredPage(page,page.role==='entry'?'entry':['form','conversion','error'].includes(page.role)?page.role:'intermediate')} suggestionToggle={suggestionToggle} config={flowConfig} catalog={discovery.catalog||[]} onChange={readOnly?()=>{}:setFlowConfig} onLocate={id=>{setSelectedNodeId(id);canvasFlowRef.current?.fitView({nodes:[{id}],padding:.6,duration:200});}} onOrganize={readOnly?undefined:autoArrange} onBuild={readOnly?undefined:()=>{setProbeOpen(false);setBlueprintOpen(true);}} onProbe={readOnly?undefined:()=>{setBlueprintOpen(false);setProbeOpen(true);}}/>
          {!blueprintOpen&&<FlowBlueprintNotice key={`${data.client.client_id}:${selectedFlowId}`} flowId={selectedFlowId} clientId={data.client.client_id} onOpen={()=>setBlueprintOpen(true)}/>}
          {probeOpen&&<FlowConversionProbe key={`probe:${selectedFlowId}`} flowId={selectedFlowId} clientId={data.client.client_id} csrf={data.csrf} domain={selectedFlow.allowed_host} config={flowConfig} onPreview={setBlueprintPreview} onApply={next=>{if(readOnly)throw new Error('Volte à edição para aplicar o caminho.');setFlowConfig(syncGroups(next));}} onClose={()=>{setProbeOpen(false);setBlueprintPreview({nodes:[],edges:[]});}}/>}
          {blueprintOpen&&<FlowBlueprint key={`${data.client.client_id}:${selectedFlowId}`} flowId={selectedFlowId} clientId={data.client.client_id} csrf={data.csrf} domain={selectedFlow.allowed_host} config={flowConfig} onPreview={setBlueprintPreview} onApply={next=>{if(readOnly)throw new Error('Volte à edição para aplicar a proposta.');setFlowConfig(syncGroups(next));}} onClose={()=>{setBlueprintOpen(false);setBlueprintPreview({nodes:[],edges:[]});}}/>}
          {flowConfig.nodes.length===0&&!probeOpen&&!blueprintOpen&&<div className="reports-flow-empty-guide" role="status"><strong>Comece pela página inicial</strong><p>O teste lê {selectedFlow.allowed_host}, encontra formulários e pixels e propõe o caminho até a conversão. Nada é enviado nem capturado.</p><div><ReportsActionButton color="primary" disabled={readOnly} onClick={()=>setProbeOpen(true)}>Testar conversão</ReportsActionButton><ReportsActionButton color="tertiary" onClick={()=>{setPaletteMode('site');panelLayout.openExplorer();}}>Explorar páginas</ReportsActionButton></div></div>}
          <FlowCanvas inspectorOpen={inspectorOpen} onNavigationModeChange={setNavigationOnly} ghostNodes={blueprintPreview.nodes} ghostEdges={blueprintPreview.edges} previewContext={{flowId:selectedFlowId,clientId:data.client.client_id,csrf:data.csrf,canCapture:!readOnly,revision:editorMode==='journey'?journeyData?.revision:null}} config={editorMode==='journey'&&journeyData?.config?journeyData.config:flowConfig} journey={editorMode==='journey'?journeyData:null} setConfig={setFlowConfig} selectedNodeId={selectedNodeId} setSelectedNodeId={setSelectedNodeId} onAddNode={(item,point,source)=>addNode(item.type,item,point,source)} onGestureStart={flowHistory.begin} onGestureEnd={flowHistory.end} onInsertEdge={insertOnEdge} onSelectedIdsChange={setSelectedNodeIds} onDuplicateSelection={duplicateSelection} readOnly={readOnly||editorMode!=='edit'} simulatedPath={simulatedPath} snapToGrid={snapToGrid} fitOnMount={workspaceV2} onOrganize={readOnly?undefined:autoArrange} onReady={instance=>{canvasFlowRef.current=instance;}} onZoomChange={setCanvasZoom}/>

          {inspectorOpen&&<FlowInspector nodes={flowConfig.nodes} onConnect={(from,to)=>setFlowConfig(current=>current.edges.some(edge=>edge.from===from&&edge.to===to)?current:{...current,edges:[...current.edges,{id:crypto.randomUUID(),from,to,variant:'direct',label:'Próximo'}]})} onCreateGroup={name=>setFlowConfig(current=>groupNodes(current,[selectedNodeId],name))} groups={[...new Set((flowConfig.groups||[]).map(g=>g.name))]} integrationsUrl={reportUrl('monitor',{client_id:data.client.client_id})} node={(editorMode==='journey'&&journeyData?.config?journeyData.config:flowConfig).nodes.find(item=>item.id===selectedNodeId)} activity={flow.events} onGestureStart={flowHistory.begin} onGestureEnd={flowHistory.end} journeyMetric={editorMode==='journey'?journeyData?.nodes?.find(item=>item.id===selectedNodeId):null} readOnly={readOnly||editorMode!=='edit'} onChange={updateNode} onClose={()=>setInspectorOpen(false)} onRemove={()=>{setFlowConfig(current=>({...current,nodes:current.nodes.filter(item=>item.id!==selectedNodeId),edges:current.edges.filter(edge=>edge.from!==selectedNodeId&&edge.to!==selectedNodeId)}));setSelectedNodeId('');setInspectorOpen(false);}}/>}
        </div>
        {editorMode==='simulate'&&<FlowSimulator config={flowConfig} onPathChange={setSimulatedPath} onClose={()=>{setEditorMode('edit');setSimulatedPath([]);}}/>}
        {editorMode==='journey'&&<FlowJourneyPanel journey={journeyData} days={journeyDays} onDaysChange={setJourneyDays} onAddSuggestion={addJourneySuggestion} onClose={()=>setEditorMode('edit')} loading={journeyLoading} error={journeyError}/> }
      </section>
    </>:<section className="reports-panel"><Empty message="Crie um fluxo ou selecione um existente na área Criar."/></section>)}
    {flowView==='monitor'&&(selectedFlow?<>
      <div className="reports-flow-topbar reports-monitor-toolbar"><div><h3>Jornada do site institucional</h3><p>Páginas visitadas, tempo ativo e avanço para formulário ou conversão · {selectedFlow?.flow_code} · {selectedFlow?.allowed_host}. Investimento e entrega de mídia ficam em Monitor.</p></div><select aria-label="Site monitorado" value={selectedFlowId} onChange={event=>chooseFlow(event.target.value)}>{flow.flows.map(item=><option key={item.id} value={item.id}>{item.flow_code} · {item.name}</option>)}</select></div>
      <article className={`reports-panel reports-page-monitor${monitorBusy?' is-monitor-checking':''}`} aria-busy={monitorBusy}><div className="reports-panel-head"><div><h3>Disponibilidade das páginas</h3><p>Verificações HTTP/HTTPS feitas pelo servidor Python nas páginas configuradas neste fluxo.</p></div><span className={`reports-monitor-status is-${monitorBusy?'checking':selectedFlow.monitor_status||'unknown'}`}><i/>{monitorBusy?'Verificando…':({online:'Online',degraded:'Com falhas',offline:'Offline',checking:'Verificando',unknown:'Sem checagem'})[selectedFlow.monitor_status||'unknown']}</span></div><div className="reports-monitor-controls"><label>Verificar a cada<select value={monitorInterval} disabled={busy||monitorBusy||data.client.role==='viewer'} onChange={event=>setMonitorInterval(Number(event.target.value))}><option value={5}>5 minutos</option><option value={15}>15 minutos</option><option value={30}>30 minutos</option><option value={60}>1 hora</option></select></label><span>{selectedFlow.monitor_checked_at?`Última verificação: ${shortDate(selectedFlow.monitor_checked_at)}`:'Ainda não verificado'}</span><div><button type="button" disabled={busy||monitorBusy||selectedFlow.status!=='published'||data.client.role==='viewer'} onClick={checkMonitorNow}>{monitorBusy?'Verificando…':'Verificar agora'}</button><button type="button" className={selectedFlow.monitor_enabled?'reports-monitor-enabled':''} disabled={busy||monitorBusy||selectedFlow.status!=='published'||data.client.role==='viewer'} onClick={()=>configureMonitor(!selectedFlow.monitor_enabled)}>{selectedFlow.monitor_enabled?'Desativar monitoramento':'Ativar monitoramento'}</button></div></div>{selectedFlow.status!=='published'&&<p className="reports-info">Publique o fluxo para ativar verificações automáticas.</p>}{flow.monitor_checks?.length?<div className="reports-monitor-pages">{flow.monitor_checks[0].pages.map((page,index)=><div className={`reports-monitor-page${monitorBusy?' is-checking':''}`} key={`${page.host}:${page.path}:${index}`}><span className={`reports-monitor-dot is-${monitorBusy?'checking':page.status}`}/><strong>{page.label}</strong><small>{page.host}{page.path}</small><b>{page.http_status||'—'}</b><em>{monitorBusy?'Checagem em andamento':page.detail}</em></div>)}</div>:<Empty message={monitorBusy?'Consultando as páginas do domínio…':'Execute uma verificação para registrar a disponibilidade das páginas deste fluxo.'}/>}<small className="reports-monitor-note">O monitor valida resposta HTTP e redirecionamentos dentro do domínio permitido. Capturas de tela e comparação visual ficam para uma etapa futura.</small></article>
      {flow.monitor_checks?.length>1&&<article className="reports-panel reports-monitor-history"><div className="reports-panel-head"><h3>Verificações recentes</h3><span>Últimas {flow.monitor_checks.length}</span></div>{flow.monitor_checks.slice(0,8).map(check=><div className="reports-monitor-history-row" key={check.id}><span className={`reports-monitor-status is-${check.status}`}><i/>{({online:'Online',degraded:'Com falhas',offline:'Offline'})[check.status]||check.status}</span><small>{shortDate(check.checked_at)}</small><small>{check.duration_ms} ms</small><small>{check.pages.filter(page=>page.status==='online').length}/{check.pages.length} páginas disponíveis</small></div>)}</article>}
      <section className="reports-grid reports-grid--four"><Kpi label="Sessões ativas" value={<FlowLiveValue key={liveScope} value={flow.online}/>} detail="Última atividade em até 90 s · todas as origens"/><Kpi label="Visitas às páginas" value={<FlowLiveValue key={liveScope} value={flow.activity.reduce((sum,item)=>sum+Number(item.views||0),0)}/>} detail={filters.startDate&&filters.endDate?`${filters.startDate} a ${filters.endDate}`:`Últimos ${flow.period_days||30} dias`}/><Kpi label="Conversões no site" value={<FlowLiveValue key={liveScope} value={flow.conversions}/>} detail="Eventos observados pela tag"/><Kpi label="Tempo ativo médio" value={flow.event_summary?.avg_active_seconds==null?'—':`${decimal(flow.event_summary.avg_active_seconds)} s`} detail={`${integer(flow.event_summary?.page_leave_count||0)} saídas medidas`}/></section>
      <p className="reports-info" role="status">{flow.live?.status==='ready'?<>Presença atual na publicação · todas as origens. <FlowLiveValue value={flow.live.sessions_on_conversion_pages}/> sessões em páginas de conversão; isso não confirma preenchimento ou compra em andamento.</>:flow.live?.status==='capacity_exceeded'?'Presença indisponível: volume recente acima do limite desta consulta. Os totais históricos permanecem disponíveis.':'Presença atual indisponível nesta versão. Selecione a publicação atual.'}</p>
      <label className="reports-flow-version-picker">Versão das métricas <select value={analysisRevision} onChange={event=>setAnalysisSelection({flowId:selectedFlowId,revision:event.target.value})}><option value="">Publicação atual</option>{monitorVersions.map(item=><option key={item.revision} value={String(item.revision)}>v{item.revision} · {item.name}</option>)}</select><small>Eventos antigos sem versão não entram nestes contadores. Conversões confirmadas no CRM usam o período geral.</small></label><div className="reports-flow-live-status" role="status"><span className={liveFailure?'is-warning':flow.tracking_health?.status==='healthy'?'is-healthy':'is-warning'}>{liveFailure?'Atualização indisponível · mostrando últimos dados':flow.tracking_health?.reason||'Aguardando sinais da tag'}</span><span>Atualização por consulta · 15 s{liveUpdatedAt?` · última às ${liveUpdatedAt.toLocaleTimeString('pt-BR')}`:''}</span></div>
      <article className="reports-panel reports-span-three reports-monitor-mesa">
        <div className="reports-panel-head"><div><h3>Jornada medida{journeyData?.revision!=null?` · v${journeyData.revision}`:''}</h3><p>De onde chegam, por onde passam, onde saem e quantos convertem. Linhas mais grossas levam mais sessões.</p></div><ReportsNativeSelect aria-label="Período da jornada" value={journeyDays} onChange={event=>setJourneyDays(Number(event.target.value))}>{[7,30,90].map(days=><option key={days} value={days}>Últimos {days} dias</option>)}</ReportsNativeSelect></div>
        {journeyError?<p className="reports-error" role="alert">{journeyError}</p>:journeyLoading&&!journeyData?<p className="reports-info" role="status">Carregando a jornada…</p>:journeyData?.status!=='ready'?<p className="reports-info">Publique o fluxo para medir a jornada desta versão.</p>:<div className="reports-monitor-mesa__canvas"><FlowCanvas key={`${selectedFlowId}:${journeyData.revision}:${journeyDays}`} readOnly config={journeyData.config} setConfig={()=>{}} journey={journeyData} selectedNodeId="" setSelectedNodeId={()=>{}} fitOnMount previewContext={{}} onAddNode={()=>{}} onInsertEdge={()=>{}} onDuplicateSelection={()=>{}}/></div>}
      </article>
      <section className="reports-grid reports-grid--three"><article className="reports-panel reports-span-three"><div className="reports-panel-head"><div><h3>Páginas que receberam tráfego</h3><p>Período selecionado · ordenadas por visitas; destaque automático de entradas, formulários, conversões e erros.</p></div><span>{integer((flow.site_pages||[]).length)} páginas</span></div>{flow.site_pages?.length?<div className="reports-table-wrap"><table><thead><tr><th>Página</th><th>Classificação</th><th>Visitas / sessões</th><th>Tempo ativo médio</th><th>Enviaram formulário</th><th>Chegaram à conversão</th><th>Origem</th></tr></thead><tbody>{flow.site_pages.slice(0,50).map(page=>{const kinds=[page.entry_sessions>0?'Entrada':null,page.is_form_page?'Formulário':null,page.is_conversion_page?'Conversão':null,page.is_error_page||Number(page.error_views)>0?'Erro':null].filter(Boolean);return <tr key={`${page.page_host}:${page.page_path}`}><td><strong>{page.page_path}</strong><small>{page.page_host}</small></td><td>{kinds.length?kinds.map(kind=><span key={kind} className={`reports-page-kind is-${kind==='Erro'?'error':kind==='Conversão'?'conversion':kind==='Formulário'?'form':'entry'}`}>{kind}</span>):'Página visitada'}{Number(page.error_views)>0&&<small>{integer(page.error_views)} ocorrências de erro</small>}</td><td>{integer(page.views)} · {integer(page.sessions)}</td><td>{Number(page.measured_visits)>0?`${decimal(page.avg_seconds)} s`:'Aguardando saídas medidas'}<small>{integer(page.measured_visits)} visitas medidas</small></td><td>{integer(page.sessions_to_form)} sessões</td><td>{integer(page.sessions_to_conversion)} sessões</td><td>{(page.sources||[]).slice(0,3).join(' · ')||'Direto / sem UTM'}</td></tr>;})}</tbody></table></div>:<Empty message="Ainda não há visitas no período. A tag passa a preencher esta tabela depois da instalação."/>}</article></section>
      <section className="reports-grid reports-grid--three"><article className="reports-panel reports-span-two"><div className="reports-panel-head"><h3>Rotas entre páginas</h3><span>Sequência observada na sessão</span></div>{flow.page_transitions?.length?<div className="reports-table-wrap"><table><thead><tr><th>De</th><th>Para</th><th>Sessões</th><th>Destino</th></tr></thead><tbody>{flow.page_transitions.slice(0,20).map((route,index)=>{const next=(flow.site_pages||[]).find(page=>page.page_host===route.next_host&&page.page_path===route.next_path);return <tr key={`${route.page_host}:${route.page_path}:${route.next_host}:${route.next_path}:${index}`}><td>{route.page_path}<small>{route.page_host}</small></td><td>{route.next_path}<small>{route.next_host}</small></td><td>{integer(route.sessions)}</td><td>{next?.is_conversion_page?'Conversão':next?.is_form_page?'Formulário':next?.is_error_page?'Erro':'Continuação'}</td></tr>;})}</tbody></table></div>:<Empty message="As rotas entre páginas aparecem quando uma sessão visita mais de uma URL com a tag."/>}</article><article className="reports-panel"><div className="reports-panel-head"><h3>Entrada e páginas-chave</h3><span>Escolhidas pelo usuário</span></div>{flow.steps.filter(step=>step.is_entry||['form','conversion','error'].includes(step.step_kind)).length?<div className="reports-origin-list">{flow.steps.filter(step=>step.is_entry||['form','conversion','error'].includes(step.step_kind)).map(step=><div className="reports-origin-row" key={step.id}><span className={`reports-page-kind is-${step.step_kind==='conversion'?'conversion':step.step_kind==='error'?'error':step.step_kind==='form'?'form':'entry'}`}>{step.is_entry?'Entrada':{form:'Formulário',conversion:'Conversão',error:'Erro'}[step.step_kind]||'Página-chave'}<small>{step.name} · {step.page_host||selectedFlow.allowed_host}{step.path_prefix}</small></span><b>{integer(step.reached)}</b></div>)}</div>:<Empty message="No editor, marque páginas de entrada, formulário, conversão ou erro para destacá-las."/>}</article></section>
      <section className="reports-grid reports-grid--three"><article className="reports-panel reports-span-two"><div className="reports-panel-head"><h3>Páginas mapeadas no site</h3><span>{flow.steps.length} páginas · {flow.period_days||30} dias</span></div>{flow.steps.length?flow.tags.map(tag=>{const stages=flow.steps.filter(step=>step.tag_id===tag.id);return stages.length?<div className="reports-flow-group" key={tag.id}><strong>{tag.label}</strong><div className="reports-flow-rail">{stages.map((step,index)=>{const prev=stages[index-1];const rate=prev?.reached?Math.round(Number(step.progressed)/Number(prev.reached)*100):null;return <article className={`reports-flow-node${step.step_kind==='conversion'?' is-conversion':''}`} key={step.id}><small>{step.is_entry?'Entrada':step.step_kind==='conversion'?'Conversão':step.step_kind==='error'?'Erro':`Página ${index+1}`}</small><strong>{step.name}</strong><span>{step.page_host?`${step.page_host} · `:''}{step.path_prefix}</span>{step.campaign_name&&<small>Campanha: {step.campaign_name}</small>}<b>{integer(step.reached)} sessões</b><em>{index?`${integer(step.progressed)} avançaram${rate===null?'':` · ${rate}%`}`:'Ponto inicial'}</em></article>;})}</div></div>:null;}):<Empty message="Ainda não há páginas mapeadas. Abra Editar para conectar páginas e conversões."/>}</article>
        <article className="reports-panel"><div className="reports-panel-head"><h3>Origens de mercado</h3><span>UTM / referência</span></div><div className="reports-origin-list">{channelOrigins.map(({channel,total,sources})=><div className="reports-origin-row" key={channel.id}><FlowPlatformLogo platform={channel.id}/><span>{channel.label}<small>{sources.slice(0,2).join(' · ')||'Sem origem observada'}</small></span><b>{integer(total)}</b></div>)}</div></article></section>
      <section className="reports-grid reports-grid--three"><article className="reports-panel"><div className="reports-panel-head"><h3>Conversões confirmadas</h3><a className="reports-inline-link" href={reportUrl('monitor')}>Integrações ↗</a></div><p>Página de conversão é observada pela tag; confirmação de lead, qualificação e venda vem do CRM.</p><div className="reports-confirmed-grid">{[['lead','Leads'],['qualified_lead','Qualificados'],['sale','Vendas']].map(([kind,label])=><Kpi key={kind} label={label} value={integer(flow.confirmed.find(item=>item.conversion_kind===kind)?.total)} detail={`${flow.period_days||30} dias · CRM`}/>)}</div></article><article className="reports-panel reports-span-two"><div className="reports-panel-head"><h3>Páginas e atividade</h3><button className="reports-text-button" type="button" onClick={()=>reload().catch(failure=>setLocalError(failure.message))}>Atualizar</button></div>{flow.activity.length?<div className="reports-table-wrap"><table><thead><tr><th>Página</th><th>Visitas</th><th>Visitantes</th><th>Online</th><th>Formulários</th><th>Cliques</th><th>Conversões</th></tr></thead><tbody>{flow.activity.map(item=><tr key={`${item.tag_id}:${item.page_path}`}><td>{item.page_path}</td><td>{integer(item.views)}</td><td>{integer(item.visitors)}</td><td>{item.online==null?'—':integer(item.online)}</td><td>{integer(item.form_submissions)}</td><td>{integer(item.clicks)}</td><td>{integer(item.conversions)}</td></tr>)}</tbody></table></div>:<Empty message="As páginas visitadas aparecerão após a instalação do snippet."/>}</article></section>
    </>:<section className="reports-panel"><Empty message="Selecione um fluxo para acompanhar o funil."/></section>)}
    {simulation&&<p className="reports-success">Teste fictício: {simulation.events.length} eventos · {simulation.flow_code}. Nenhum evento real foi enviado.</p>}
    {copyState&&<p className="reports-info" role="status">{copyState}</p>}
  </>;
}

