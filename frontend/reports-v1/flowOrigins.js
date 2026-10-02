import {stageX} from './flowStages.js';

const KINDS={direct:'traffic.direct',organic:'traffic.organic_search',social:'traffic.organic_social',referral:'traffic.referral',campaign:'traffic.referral',
  google:'traffic.google_search',meta:'traffic.meta',tiktok:'traffic.tiktok',linkedin:'traffic.linkedin',youtube:'traffic.youtube',
  email:'communication.email',whatsapp:'communication.whatsapp',sms:'communication.sms'};

export const originKind=platform=>KINDS[platform]||'traffic.referral';

/**
 * The plan only draws the origins someone thought of; visitors also arrive direct, from other sites or from
 * campaigns nobody drew. The monitor adds those as read-only source nodes so the map shows every arrival.
 * Synthetic ids are `origin:<platform>` and `origin:<platform>:<node>`; the live feed uses the same edge ids.
 */
export function withUnmappedOrigins(journey) {
  const config=journey?.config;
  const landings=(journey?.origin_landings||[]).filter(item=>!item.drawn&&(config?.nodes||[]).some(node=>node.id===item.node_id));
  if(!config||!landings.length)return journey;
  const sources=config.nodes.filter(node=>node.type==='source');
  const x=sources.length?Math.min(...sources.map(node=>Number(node.x)||0)):stageX('source');
  // One card height plus a gap below the lowest drawn origin, so unclaimed traffic never covers it.
  const step=240;
  let y=sources.length?Math.max(...sources.map(node=>Number(node.y)||0))+step:100;
  const totals={};
  for(const item of landings)totals[item.platform]=(totals[item.platform]||0)+item.sessions;
  const nodes=[],metrics=[];
  for(const platform of Object.keys(totals)){
    const label=landings.find(item=>item.platform===platform).label;
    nodes.push({id:`origin:${platform}`,type:'source',kind:KINDS[platform]||'traffic.referral',title:label,stage:'source',x,y,locked:true,synthetic:true});
    metrics.push({id:`origin:${platform}`,sessions:totals[platform],events:null,estimated_from:'origin'});
    y+=step;
  }
  const edges=landings.map(item=>({id:`origin:${item.platform}:${item.node_id}`,from:`origin:${item.platform}`,to:item.node_id,variant:'direct',synthetic:true}));
  const edgeMetrics=landings.map(item=>{const rate=Math.round(1000*item.sessions/totals[item.platform])/10;
    return {id:`origin:${item.platform}:${item.node_id}`,from:`origin:${item.platform}`,to:item.node_id,sessions:item.sessions,rate,observation:{status:'measured',sessions:item.sessions,rate,denominator:totals[item.platform]}};});
  return {...journey,config:{...config,nodes:[...config.nodes,...nodes],edges:[...(config.edges||[]),...edges]},
    nodes:[...(journey.nodes||[]),...metrics],edges:[...(journey.edges||[]),...edgeMetrics]};
}

const SOURCE_STEP=120;
const isPageNode=node=>node.type==='page'&&!node.synthetic;

/** The page visitors land on first: marked as entry, the root path, or the only page the flow has. */
export function entryPageOf(config) {
  const pages=(config.nodes||[]).filter(isPageNode);
  return pages.find(node=>node.isEntry)||pages.find(node=>node.path==='/')||pages.find(node=>node.stage==='entry')||(pages.length===1?pages[0]:null)||null;
}

/**
 * Origins that nobody wired go to the entry page by themselves, and the origins sit together beside it.
 * Only runs on what was just added (`previousIds`), so an edge the person removed on purpose is never redrawn.
 */
export function wireNewNodes(config,previousIds) {
  const nodes=config.nodes||[];
  const added=nodes.filter(node=>!previousIds.has(node.id));
  if(!added.some(node=>node.type==='source'||isPageNode(node)))return {config,wired:0};
  const entry=entryPageOf(config);
  if(!entry)return {config,wired:0};
  const hasOut=new Set((config.edges||[]).map(edge=>edge.from));
  const loose=nodes.filter(node=>node.type==='source'&&!node.synthetic&&!hasOut.has(node.id));
  if(!loose.length)return {config,wired:0};
  const edges=[...(config.edges||[]),...loose.map(source=>({id:crypto.randomUUID(),from:source.id,to:entry.id,from_port:'right-out',to_port:'left-in',variant:'planned',label:'Próximo',origin:'auto'}))];
  // Stack the origins into one tidy column centred on the entry page; hand-placed ones stay where they are.
  const column=nodes.filter(node=>node.type==='source'&&!node.synthetic&&!node.manuallyEdited&&!node.locked);
  const centre=Number(entry.y)||0;
  const top=centre-((column.length-1)*SOURCE_STEP)/2;
  const place=new Map(column.map((node,index)=>[node.id,Math.round((top+index*SOURCE_STEP)/20)*20]));
  return {config:{...config,edges,nodes:nodes.map(node=>place.has(node.id)?{...node,y:place.get(node.id)}:node)},wired:loose.length};
}
