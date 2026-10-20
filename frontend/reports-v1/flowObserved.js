// What the Super Tag observed and the draft does not draw yet: origins without a node, passages between drawn steps
// and pages that show up in conversions. Pure helpers, so the editor panel and the tests read the same rules.
import {stageX} from './flowStages.js';
import {findFreeSlot} from './flowDrag.js';
import {originKind} from './flowOrigins.js';

const NODE_PLATFORMS={facebook:'meta',instagram:'meta',dv360:'google',organic_search:'organic',organic_social:'social',communication:'email',google_search:'google'};
const PAGE_TYPES=['page','form','conversion','error'];
const OBSERVED_LABEL='Caminho observado';

export const normPath=path=>(String(path||'/').toLowerCase().replace(/\/+$/,'')||'/');
const normHost=host=>String(host||'').toLowerCase().replace(/^www\./,'').replace(/\.$/,'');
/** A page's identity, as the server keys it (reports_flow_conversions.page_key): the path on the flow's own domain, host + path on another. */
export const pageKey=(path,host,siteHost)=>{const own=normHost(siteHost),other=normHost(host);return other&&other!==own?`${other}${normPath(path)}`:normPath(path);};
/** The platform a drawn origin stands for, as the server reads it (reports_flow_metrics.node_platform). */
export const platformOf=node=>{const value=node.source||String(node.kind||'').split('.')[1]||'';return NODE_PLATFORMS[value]||value;};
const edgeKey=(from,to)=>`${from}>${to}`;

/** Drawn page steps of the draft by pageKey; a page of another of the client's domains keeps that domain apart. */
export function pagesByPath(config,siteHost){
  const map=new Map();
  for(const node of config.nodes||[]){if(!PAGE_TYPES.includes(node.type)||!node.path)continue;const key=pageKey(node.path,node.host,siteHost);if(!map.has(key))map.set(key,node);}
  return map;
}
const stepKey=step=>step.key||normPath(step.path);

/**
 * Origins the visitors came from that no origin of the draft stands for, with the drawn pages they land on.
 * A platform already drawn is left out even when some of its sessions were not claimed (a UTM that matches none of
 * the drawn ones): adding a second node of that channel is a decision the source picker asks about.
 */
export function undrawnOrigins(journey,config){
  const drawn=new Set((config.nodes||[]).filter(node=>node.type==='source').map(platformOf));
  const ids=new Set((config.nodes||[]).map(node=>node.id));
  const byPlatform=new Map();
  for(const item of journey?.origin_landings||[]){
    if(item.drawn||drawn.has(item.platform))continue;
    const entry=byPlatform.get(item.platform)||{platform:item.platform,label:String(item.label||item.platform).replace(/ · sem origem identificada$/,''),sessions:0,landings:[]};
    entry.sessions+=Number(item.sessions)||0;
    if(ids.has(item.node_id))entry.landings.push({node_id:item.node_id,sessions:Number(item.sessions)||0});
    byPlatform.set(item.platform,entry);
  }
  return [...byPlatform.values()].map(entry=>({...entry,landings:entry.landings.sort((a,b)=>b.sessions-a.sessions)})).sort((a,b)=>b.sessions-a.sessions);
}

/** Adds one origin node per observed platform, wired to the drawn pages its visitors landed on. */
export function addObservedOrigins(config,origins){
  const sources=(config.nodes||[]).filter(node=>node.type==='source');
  let nodes=[...(config.nodes||[])],edges=[...(config.edges||[])];
  const x=sources.length?Math.min(...sources.map(node=>Number(node.x)||0)):stageX('source');
  let y=sources.length?Math.max(...sources.map(node=>Number(node.y)||0))+140:100;
  const added=[];
  for(const origin of origins){
    const id=crypto.randomUUID();
    const node={id,type:'source',kind:originKind(origin.platform),source:origin.platform,title:origin.label,stage:'source',origin:'manual',...findFreeSlot(nodes,{x,y},{height:110})};
    nodes=[...nodes,node];y=node.y+140;added.push(id);
    for(const landing of origin.landings)edges.push({id:crypto.randomUUID(),from:id,to:landing.node_id,variant:'planned',label:'Origem observada',origin:'manual'});
  }
  return {config:{...config,schema_version:3,nodes,edges},added};
}

/** Whether a step of the draft leads to a conversion step by its drawn connections. */
export function reachesGoal(config,id){
  const byId=new Map((config.nodes||[]).map(node=>[node.id,node]));
  const next=new Map();
  for(const edge of config.edges||[])next.set(edge.from,[...(next.get(edge.from)||[]),edge.to]);
  const seen=new Set([id]),queue=[id];
  while(queue.length){const current=queue.shift();if(byId.get(current)?.type==='conversion')return true;for(const target of next.get(current)||[])if(!seen.has(target)){seen.add(target);queue.push(target);}}
  return false;
}

export const goalNodes=config=>(config.nodes||[]).filter(node=>node.type==='conversion');

// Page steps of a journey mapped onto the draft: a step is drawn when the draft has a page at its address.
function draftSteps(journey,drafted){
  return (journey.steps||[]).filter(step=>step.kind==='page'&&step.path).map(step=>({...step,draft:drafted.get(stepKey(step))||null}));
}

/**
 * How conversions pass through an off-flow page: the drawn step usually right before it, the drawn step it leads
 * to, and the undrawn pages between them on the most common way. That stretch is what "create the path" adds.
 */
export function observedPageDetail(journeys,key,config,siteHost){
  const drafted=pagesByPath(config,siteHost),target=key.startsWith('/')?normPath(key):key;
  const segments=new Map();let conversions=0;
  for(const journey of journeys||[]){
    const steps=draftSteps(journey,drafted);
    const index=steps.findIndex(step=>stepKey(step)===target);
    if(index<0)continue;
    conversions+=1;
    let start=index;while(start>0&&!steps[start-1].draft)start-=1;
    let end=index;while(end<steps.length-1&&!steps[end+1].draft)end+=1;
    const before=start>0?steps[start-1].draft.id:null,after=end<steps.length-1?steps[end+1].draft.id:null;
    const pages=steps.slice(start,end+1).filter(step=>!step.draft);
    const way=[before,...pages.map(stepKey),after].join('>');
    const entry=segments.get(way)||{before,after,pages:pages.map(step=>({path:normPath(step.path),host:step.host||null,key:stepKey(step),title:step.title})),conversions:0};
    entry.conversions+=1;segments.set(way,entry);
  }
  const ways=[...segments.values()].sort((a,b)=>b.conversions-a.conversions);
  return {key:target,conversions,ways,best:ways[0]||null};
}

/** Conversions that went from one drawn step straight to another, as the journeys list shows them. */
export function observedPassageDetail(journeys,from,to,config,siteHost){
  const byId=new Map((config.nodes||[]).map(node=>[node.id,node]));
  const keyOf=node=>node?pageKey(node.path,node.host,siteHost):null;
  const fromPath=keyOf(byId.get(from)),toPath=keyOf(byId.get(to));
  let conversions=0;
  for(const journey of journeys||[]){
    const paths=(journey.steps||[]).filter(step=>step.kind==='page').map(stepKey);
    if(paths.some((path,index)=>path===fromPath&&paths[index+1]===toPath))conversions+=1;
  }
  return {conversions,reaches_goal:reachesGoal(config,to)};
}

/**
 * Creates the undrawn pages of an observed way as planned steps, chained from the drawn step before them to the
 * drawn step after them (or to `goalId` when the way has no drawn step after it). Pages already drawn are reused.
 */
export function addObservedChain(config,{before,pages,after,goalId},siteHost){
  const drafted=pagesByPath(config,siteHost);
  let nodes=[...(config.nodes||[])],edges=[...(config.edges||[])];
  const existing=new Set(edges.map(edge=>edgeKey(edge.from,edge.to)));
  const anchor=nodes.find(node=>node.id===before)||null;
  let x=anchor?Number(anchor.x)+300:stageX('exploration'),y=anchor?Number(anchor.y)+160:100;
  const chain=[];const created=[];
  for(const page of pages){
    const key=pageKey(page.path,page.host,siteHost);
    const drawn=drafted.get(key);
    if(drawn){chain.push(drawn.id);continue;}
    const node={id:crypto.randomUUID(),type:'page',kind:'page.generic',title:page.title||page.path,stage:'exploration',origin:'manual',path:page.path,...(page.host?{host:page.host}:{}),pageType:'other',...findFreeSlot(nodes,{x,y})};
    nodes=[...nodes,node];drafted.set(key,node);chain.push(node.id);created.push(node.id);x=node.x+300;y=node.y;
  }
  const end=after||goalId||null;
  const ids=[before,...chain,end].filter(Boolean);
  for(let index=0;index<ids.length-1;index++){
    const [from,to]=[ids[index],ids[index+1]];
    if(from===to||existing.has(edgeKey(from,to)))continue;
    existing.add(edgeKey(from,to));
    edges.push({id:crypto.randomUUID(),from,to,variant:'planned',label:OBSERVED_LABEL});
  }
  return {config:{...config,schema_version:3,nodes,edges},created};
}

/** Adds the observed passage and, when its destination leads nowhere, a planned link from it to the goal. */
export function addObservedPassage(config,{from,to,goalId}){
  const existing=new Set((config.edges||[]).map(edge=>edgeKey(edge.from,edge.to)));
  const edges=[...(config.edges||[])];
  if(!existing.has(edgeKey(from,to)))edges.push({id:crypto.randomUUID(),from,to,variant:'planned',label:OBSERVED_LABEL});
  const next={...config,edges};
  if(goalId&&!reachesGoal(next,to)&&!existing.has(edgeKey(to,goalId)))edges.push({id:crypto.randomUUID(),from:to,to:goalId,variant:'planned',label:'Até o objetivo'});
  return {...next,edges};
}
