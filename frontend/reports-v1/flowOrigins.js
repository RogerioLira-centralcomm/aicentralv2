import {stageX} from './flowStages.js';

const KINDS={direct:'traffic.direct',organic:'traffic.organic_search',social:'traffic.organic_social',referral:'traffic.referral',campaign:'traffic.referral',
  google:'traffic.google_search',meta:'traffic.meta',tiktok:'traffic.tiktok',linkedin:'traffic.linkedin',youtube:'traffic.youtube',
  email:'communication.email',whatsapp:'communication.whatsapp',sms:'communication.sms'};

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
  let y=sources.length?Math.max(...sources.map(node=>Number(node.y)||0))+150:100;
  const totals={};
  for(const item of landings)totals[item.platform]=(totals[item.platform]||0)+item.sessions;
  const nodes=[],metrics=[];
  for(const platform of Object.keys(totals)){
    const label=landings.find(item=>item.platform===platform).label;
    nodes.push({id:`origin:${platform}`,type:'source',kind:KINDS[platform]||'traffic.referral',title:label,stage:'source',x,y,locked:true,synthetic:true});
    metrics.push({id:`origin:${platform}`,sessions:totals[platform],events:null,estimated_from:'origin'});
    y+=150;
  }
  const edges=landings.map(item=>({id:`origin:${item.platform}:${item.node_id}`,from:`origin:${item.platform}`,to:item.node_id,variant:'direct',synthetic:true}));
  const edgeMetrics=landings.map(item=>{const rate=Math.round(1000*item.sessions/totals[item.platform])/10;
    return {id:`origin:${item.platform}:${item.node_id}`,from:`origin:${item.platform}`,to:item.node_id,sessions:item.sessions,rate,observation:{status:'measured',sessions:item.sessions,rate,denominator:totals[item.platform]}};});
  return {...journey,config:{...config,nodes:[...config.nodes,...nodes],edges:[...(config.edges||[]),...edges]},
    nodes:[...(journey.nodes||[]),...metrics],edges:[...(journey.edges||[]),...edgeMetrics]};
}
