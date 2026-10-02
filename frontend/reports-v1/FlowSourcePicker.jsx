import React,{useMemo,useState} from 'react';
import {ReportsPanelShell} from './ReportsPanelShell.jsx';
import {ReportsActionButton as Button} from './ReportsActionButton.jsx';
import {ReportsFieldInput} from './ReportsFieldInput.jsx';
import {stageX} from './flowStages.js';
import {utmSlug} from './flowSourceIdentity.js';

// Channels a flow can start from without a registered campaign. Kinds match flowBlockRegistry.
const CHANNELS=[
  {key:'google',kind:'traffic.google_search',source:'google',title:'Google Ads'},
  {key:'meta',kind:'traffic.meta',source:'meta',title:'Meta Ads'},
  {key:'organic',kind:'traffic.organic_search',source:'organic',title:'Busca orgânica'},
  {key:'social',kind:'traffic.organic_social',source:'social',title:'Redes sociais'},
  {key:'email',kind:'communication.email',source:'email',title:'E-mail'},
  {key:'direct',kind:'traffic.direct',source:'direct',title:'Acesso direto'},
];
const CAMPAIGN_PLATFORMS={google_ads:['traffic.google_search','google'],meta_ads:['traffic.meta','meta'],microsoft_ads:['traffic.referral','referral']};

/** Start a flow from where visitors come from: the client's campaigns or a traffic channel. */
export function FlowSourcePicker({config,campaigns=[],onApply,onClose}) {
  const [query,setQuery]=useState('');
  const [picked,setPicked]=useState(()=>new Set());
  const existing=useMemo(()=>new Set(config.nodes.filter(node=>node.type==='source').map(node=>node.campaign_id?`c:${node.campaign_id}`:`s:${node.source}`)),[config.nodes]);
  const visibleCampaigns=campaigns.filter(item=>item.status!=='removed'&&`${item.name} ${item.account_name||''}`.toLowerCase().includes(query.trim().toLowerCase())).slice(0,40);
  const toggle=key=>setPicked(current=>{const next=new Set(current);next.has(key)?next.delete(key):next.add(key);return next;});
  const apply=()=>{
    const sources=[...picked].map(key=>{
      if(key.startsWith('c:')){const campaign=campaigns.find(item=>`c:${item.id}`===key);const [kind,source]=CAMPAIGN_PLATFORMS[campaign.platform]||['traffic.referral','referral'];return {kind,source,title:campaign.name,campaign_id:campaign.id,media:{utm:{campaign:utmSlug(campaign.name)}}};}
      const channel=CHANNELS.find(item=>`s:${item.source}`===key);return {kind:channel.kind,source:channel.source,title:channel.title};
    });
    const count=config.nodes.filter(node=>node.type==='source').length;
    const nodes=sources.map((item,index)=>({id:crypto.randomUUID(),type:'source',stage:'source',origin:'manual',x:stageX('source'),y:100+(count+index)*160,...item}));
    onApply({...config,nodes:[...config.nodes,...nodes]});
    onClose();
  };
  // A client campaign enters once; a channel can repeat, and the map then asks how to tell the two apart.
  const row=(key,title,detail)=>{const locked=key.startsWith('c:')&&existing.has(key);return <label key={key} className="flow-source-picker__row"><input type="checkbox" disabled={locked} checked={locked||picked.has(key)} onChange={()=>toggle(key)}/><span><b>{title}</b>{detail&&<small>{detail}</small>}</span>{existing.has(key)&&<small>no fluxo</small>}</label>;};
  return <ReportsPanelShell compact className="flow-blueprint-panel flow-source-picker" title="Campanhas do cliente" onClose={onClose}
    footer={<Button color="primary" disabled={!picked.size} onClick={apply}>{picked.size?`Adicionar ${picked.size} ${picked.size===1?'origem':'origens'}`:'Escolha as origens'}</Button>}>
    {campaigns.length>0&&<section className="flow-probe-block"><h3>Campanhas do cliente</h3>
      {campaigns.length>8&&<ReportsFieldInput type="search" aria-label="Buscar campanha" placeholder="Buscar campanha" value={query} onChange={event=>setQuery(event.target.value)}/>}
      {visibleCampaigns.map(item=>row(`c:${item.id}`,item.name,[item.account_name,item.status==='active'?'ativa':item.status].filter(Boolean).join(' · ')))}</section>}
    <section className="flow-probe-block"><h3>Canais</h3>{CHANNELS.map(item=>row(`s:${item.source}`,item.title))}</section>
  </ReportsPanelShell>;
}
