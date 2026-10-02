import React,{useMemo,useState} from 'react';
import {ReportsPanelShell} from './ReportsPanelShell.jsx';
import {ReportsActionButton as Button} from './ReportsActionButton.jsx';
import {ReportsFieldInput} from './ReportsFieldInput.jsx';
import {stageX} from './flowStages.js';
import {utmSlug} from './flowSourceIdentity.js';
import {originKind} from './flowOrigins.js';

// Channels a flow can start from without a registered campaign. Kinds match flowBlockRegistry.
const CHANNELS=[
  {key:'organic',group:'essential',kind:'traffic.organic_search',source:'organic',title:'Busca orgânica'},
  {key:'social',group:'essential',kind:'traffic.organic_social',source:'social',title:'Redes sociais'},
  {key:'direct',group:'essential',kind:'traffic.direct',source:'direct',title:'Acesso direto'},
  {key:'google',group:'paid',kind:'traffic.google_search',source:'google',title:'Google Ads'},
  {key:'meta',group:'paid',kind:'traffic.meta',source:'meta',title:'Meta Ads'},
  {key:'tiktok',group:'paid',kind:'traffic.tiktok',source:'tiktok',title:'TikTok Ads'},
  {key:'linkedin',group:'paid',kind:'traffic.linkedin',source:'linkedin',title:'LinkedIn Ads'},
  {key:'youtube',group:'paid',kind:'traffic.youtube',source:'youtube',title:'YouTube Ads'},
  {key:'email',group:'other',kind:'communication.email',source:'email',title:'E-mail'},
  {key:'whatsapp',group:'other',kind:'communication.whatsapp',source:'whatsapp',title:'WhatsApp'},
  {key:'sms',group:'other',kind:'communication.sms',source:'sms',title:'SMS'},
  {key:'referral',group:'other',kind:'traffic.referral',source:'referral',title:'Referência de outros sites'},
];
const GROUPS=[['essential','Origens naturais de toda marca'],['paid','Mídia paga'],['other','Comunicação e outros']];
const CAMPAIGN_PLATFORMS={google_ads:['traffic.google_search','google'],meta_ads:['traffic.meta','meta'],microsoft_ads:['traffic.referral','referral']};

/** Start a flow from where visitors come from: the client's campaigns or a traffic channel. */
export function FlowSourcePicker({config,campaigns=[],detected=[],onApply,onClose}) {
  const [query,setQuery]=useState('');
  const existing=useMemo(()=>new Set(config.nodes.filter(node=>node.type==='source').map(node=>node.campaign_id?`c:${node.campaign_id}`:`s:${node.source}`)),[config.nodes]);
  // Organic search, social and direct reach every brand: they start selected until the map has them.
  const [picked,setPicked]=useState(()=>new Set(CHANNELS.filter(item=>item.group==='essential'&&!existing.has(`s:${item.source}`)).map(item=>`s:${item.source}`)));
  // Traffic the Super Tag sees from origins nobody drew; adding one gives it its own dimension instead of the shared bucket.
  const found=useMemo(()=>{const seen=new Map();for(const item of detected){if(item.drawn||CHANNELS.some(channel=>channel.source===item.platform)&&existing.has(`s:${item.platform}`))continue;const entry=seen.get(item.platform)||{platform:item.platform,label:item.label||item.platform,sessions:0};entry.sessions+=Number(item.sessions)||0;seen.set(item.platform,entry);}return [...seen.values()].sort((a,b)=>b.sessions-a.sessions);},[detected,existing]);
  const visibleCampaigns=campaigns.filter(item=>item.status!=='removed'&&`${item.name} ${item.account_name||''}`.toLowerCase().includes(query.trim().toLowerCase())).slice(0,40);
  const toggle=key=>setPicked(current=>{const next=new Set(current);next.has(key)?next.delete(key):next.add(key);return next;});
  const apply=()=>{
    const sources=[...picked].map(key=>{
      if(key.startsWith('c:')){const campaign=campaigns.find(item=>`c:${item.id}`===key);const [kind,source]=CAMPAIGN_PLATFORMS[campaign.platform]||['traffic.referral','referral'];return {kind,source,title:campaign.name,campaign_id:campaign.id,media:{utm:{campaign:utmSlug(campaign.name)}}};}
      if(key.startsWith('d:')){const origin=found.find(item=>`d:${item.platform}`===key);return {kind:originKind(origin.platform),source:origin.platform,title:origin.label};}
      const channel=CHANNELS.find(item=>`s:${item.source}`===key);return {kind:channel.kind,source:channel.source,title:channel.title};
    });
    const count=config.nodes.filter(node=>node.type==='source').length;
    const nodes=sources.map((item,index)=>({id:crypto.randomUUID(),type:'source',stage:'source',origin:'manual',x:stageX('source'),y:100+(count+index)*120,...item}));
    onApply({...config,nodes:[...config.nodes,...nodes]});
    onClose();
  };
  // A client campaign enters once; a channel can repeat, and the map then asks how to tell the two apart.
  const row=(key,title,detail)=>{
    const inFlow=existing.has(key);const channel=key.startsWith('s:');
    return <label key={key} className="flow-source-picker__row"><input type="checkbox" disabled={inFlow} checked={inFlow||picked.has(key)} onChange={()=>toggle(key)}/><span><b>{title}</b>{detail&&<small>{detail}</small>}</span>
      {inFlow&&<small>já no fluxo</small>}
      {inFlow&&channel&&<button type="button" className="flow-source-picker__again" aria-pressed={picked.has(key)} onClick={event=>{event.preventDefault();toggle(key);}}>{picked.has(key)?'Outro será adicionado':'+ outro'}</button>}</label>;
  };
  return <ReportsPanelShell compact className="flow-blueprint-panel flow-source-picker" title="Origens do tráfego" onClose={onClose}
    footer={<Button color="primary" disabled={!picked.size} onClick={apply}>{picked.size?`Adicionar ${picked.size} ${picked.size===1?'origem':'origens'}`:'Escolha as origens'}</Button>}>
    {campaigns.length>0&&<section className="flow-probe-block"><h3>Campanhas do cliente</h3>
      {campaigns.length>8&&<ReportsFieldInput type="search" aria-label="Buscar campanha" placeholder="Buscar campanha" value={query} onChange={event=>setQuery(event.target.value)}/>}
      {visibleCampaigns.map(item=>row(`c:${item.id}`,item.name,[item.account_name,item.status==='active'?'ativa':item.status].filter(Boolean).join(' · ')))}</section>}
    {GROUPS.map(([group,label])=><section key={group} className="flow-probe-block"><h3>{label}</h3>{CHANNELS.filter(item=>item.group===group).map(item=>row(`s:${item.source}`,item.title))}</section>)}
    {found.length>0&&<section className="flow-probe-block"><h3>Detectadas no tráfego</h3><p className="flow-source-picker__hint">Visitas que chegaram de origens fora do mapa. Adicione para separar cada uma em vez de ficarem juntas.</p>{found.map(item=>row(`d:${item.platform}`,item.label,`${item.sessions.toLocaleString('pt-BR')} sessões no período`))}</section>}
  </ReportsPanelShell>;
}
