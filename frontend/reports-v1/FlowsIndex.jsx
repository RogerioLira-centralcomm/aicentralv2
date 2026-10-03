import {Edit01, BarChart01} from '@untitledui/icons';
import {useReportsContext} from './shell/context.js';
import {DataTable, EmptyState, Section} from './shell/primitives.jsx';
import {CaduTabs} from '../cadu-design-system/components/CaduTabs.jsx';
import React, {useEffect, useRef, useState} from 'react';
import {ReportsActionButton} from './ReportsActionButton.jsx';
import {ReportsDrawer} from './ReportsDrawer.jsx';
import {ReportsFieldInput} from './ReportsFieldInput.jsx';
import {ReportsNativeSelect} from './ReportsNativeSelect.jsx';
import {plural} from './flowFeedback.js';
import {flowNextAction} from './flowNextAction.js';
import {flowBlockRegistry} from './flowBlockRegistry.js';
import {FLOW_STRATEGIES, buildPathConfig, buildStrategyConfig, defaultStrategyChannels, instantiateTemplate, readPathSeed} from './flowStrategies.js';
import {FlowTemplateGallery} from './FlowTemplateGallery.jsx';
import {Empty, flowEditorUrl, json, reportUrl} from './reportsCommon.jsx';
import {friendlyAgo, friendlyDateTime} from './friendlyDates.js';
import {COLLECTION_DAYS, flowCollection, flowItemCount, flowResults, formatRate} from './flowCollection.js';
import './flows-index.css';

/** Flow list and creation: the entry screen of Fluxos. Owns its own form state; the editor never reads it. */
export function FlowsIndex({data, flows, supertagSites, save, busy}) {
  const {scope}=useReportsContext();
  const [flowHost, setFlowHost] = useState(()=>new URLSearchParams(location.search).get('site_host')||'');
  const [flowCreateOpen,setFlowCreateOpen]=useState(()=>Boolean(new URLSearchParams(location.search).get('site_host')));
  const [flowTagFilter,setFlowTagFilter]=useState('');
  const [indexView,setIndexView]=useState(()=>new URLSearchParams(location.search).get('modelos')==='1'?'models':'flows');
  const [flowSiteCheck, setFlowSiteCheck] = useState(null);
  const [flowSiteChecking, setFlowSiteChecking] = useState(false);
  const [flowSiteKind,setFlowSiteKind]=useState('');
  const [flowCustomerId,setFlowCustomerId]=useState('');
  const [flowCampaignId,setFlowCampaignId]=useState('');
  const [flowName, setFlowName] = useState('');
  // "Criar fluxo a partir deste caminho" (Site & Jornada → Navegação) arrives with ?site_host=&caminho=[...].
  const [pathSeed]=useState(()=>readPathSeed(location.search));
  const [flowStart,setFlowStart]=useState(()=>pathSeed.length?'path':'strategy');
  const [strategyId,setStrategyId]=useState('');
  const [strategyChannels,setStrategyChannels]=useState([]);
  const [teamTemplates,setTeamTemplates]=useState([]);
  const loadTeamTemplates=()=>json(`/connect/api/v2/reports/flow/templates`).then(result=>setTeamTemplates(result.templates||[])).catch(()=>setTeamTemplates([]));
  useEffect(()=>{loadTeamTemplates();},[data.client.client_id]);
  const teamTemplate=strategyId.startsWith('team:')?teamTemplates.find(item=>`team:${item.id}`===strategyId):null;
  const strategy=FLOW_STRATEGIES.find(item=>item.id===strategyId);
  const chooseStrategy=item=>{setStrategyId(item.id);setStrategyChannels(defaultStrategyChannels(item));};
  const startFromTemplate=item=>{setFlowStart('strategy');chooseStrategy(item);setFlowCreateOpen(true);};
  const startFromTeamTemplate=item=>{setFlowStart('strategy');setStrategyId(`team:${item.id}`);setStrategyChannels([]);setFlowCreateOpen(true);};
  const deleteTeamTemplate=async item=>{if(!window.confirm(`Excluir o modelo “${item.name}”? Os fluxos criados a partir dele continuam iguais.`))return;try{await save(`/flow/templates/${item.id}`,{},false,'DELETE');await loadTeamTemplates();}catch(failure){setLocalError(failure.message);}};
  const toggleChannel=kind=>setStrategyChannels(current=>current.includes(kind)?current.filter(item=>item!==kind):[...current,kind]);
  const fromStrategy=flowStart==='strategy';
  const fromPath=flowStart==='path'&&pathSeed.length>0;
  const strategyReady=!fromStrategy||Boolean(teamTemplate)||(strategy&&strategyChannels.length>0);
  const planWithoutSite=fromStrategy&&!flowHost.trim();
  const [localError,setLocalError]=useState('');
  const superTagForFlow = flowItem => supertagSites.find(site => {
    const allowed = String(site.allowed_host || '').toLowerCase().replace(/^www\./, '');
    const target = String(flowItem?.allowed_host || '').toLowerCase().replace(/^www\./, '');
    return target === allowed || target.endsWith(`.${allowed}`);
  });
  const openFlow = (item, view) => {if(view==='edit'){const url=new URL(flowEditorUrl(item.id),location.origin);url.searchParams.set('modo','editar');location.assign(url);}else location.assign(reportUrl(`flows/${item.id}/monitor`));};
  const flowTags=item=>Array.isArray(item.config?.tags)?item.config.tags:[];
  const allTags=[...new Set(flows.flatMap(flowTags))].sort((a,b)=>a.localeCompare(b,'pt-BR'));
  const normalizeHost=value=>String(value||'').toLowerCase().replace(/^www\./,'');
  const scopedHost=normalizeHost(supertagSites.find(site=>String(site.id)===scope.site)?.allowed_host);
  const visibleFlows=flows.filter(item=>(!flowTagFilter||flowTags(item).includes(flowTagFilter))&&(!scopedHost||normalizeHost(item.allowed_host)===scopedHost));
  const publishedFlows=visibleFlows.filter(item=>item.status==='published');
  const draftFlows=visibleFlows.filter(item=>item.status!=='published');
  const flowIdentity=item=><><strong title={item.flow_code}>{item.name}</strong><small className="rs-cell-sub">{[plural(flowItemCount(item),'item','itens'),item.allowed_host||'sem site · plano',item.campaign_names,...flowTags(item)].filter(Boolean).join(' · ')}</small></>;
  const flowIconActions=(item,monitor)=><>
    <ReportsActionButton color="tertiary" size="sm" tooltip="Editar fluxo" aria-label={`Editar ${item.name}`} onClick={()=>openFlow(item,'edit')}><Edit01 size={16} aria-hidden="true"/></ReportsActionButton>
    {monitor&&<ReportsActionButton color="tertiary" size="sm" tooltip="Monitorar fluxo" aria-label={`Monitorar ${item.name}`} onClick={()=>openFlow(item,'monitor')}><BarChart01 size={16} aria-hidden="true"/></ReportsActionButton>}
  </>;
  const monitorLabel=item=>item.monitor_enabled?({online:'Online',degraded:'Com falhas',offline:'Offline',checking:'Verificando',unknown:'Aguardando checagem'})[item.monitor_status]||'Ativo':'';
  const flowUpdatedLabel=value=>friendlyDateTime(value);
  const flowCreateHint=!strategyReady?'Escolha uma estratégia e ao menos um canal.':planWithoutSite?'O plano será criado sem site. Conecte o site quando for medir.':!flowHost.trim()?'Informe a URL do site e valide o domínio.':!flowSiteCheck?'Valide o domínio para continuar.':flowSiteCheck.error?'Corrija o domínio para continuar.':superTagForFlow({allowed_host:flowSiteCheck.host})?'A Super Tag deste domínio já existe e será reutilizada.':'A Super Tag será criada automaticamente para este domínio.';
  const siteCheckSequence=useRef(0);
  const checkFlowSite = async () => {const url=flowHost.trim();if(!url)return;const sequence=++siteCheckSequence.current;setFlowSiteChecking(true);setFlowSiteCheck(null);setLocalError('');try{const result=await json(`/connect/api/v2/reports/supertag/site-check?url=${encodeURIComponent(url)}`);if(sequence===siteCheckSequence.current)setFlowSiteCheck({...result,verifiedUrl:url});}catch(failure){if(sequence===siteCheckSequence.current)setFlowSiteCheck({error:failure.message});}finally{if(sequence===siteCheckSequence.current)setFlowSiteChecking(false);}};
  const newFlow = async event => {event.preventDefault(); try {if(!planWithoutSite&&(!flowSiteCheck||flowSiteCheck.error||flowSiteCheck.verifiedUrl!==flowHost.trim()))throw new Error('Verifique o domínio atual antes de criar o fluxo.');if(fromStrategy&&!strategyReady)throw new Error('Escolha uma estratégia e ao menos um canal.');const name=flowName||(fromStrategy?(teamTemplate||strategy).name:fromPath?`Caminho ${pathSeed[0]} → ${pathSeed[pathSeed.length-1]}`.slice(0,120):flowSiteCheck.title||flowSiteCheck.host);const config=fromStrategy?(teamTemplate?instantiateTemplate(teamTemplate.config):buildStrategyConfig(strategy,strategyChannels)):fromPath?{...buildPathConfig(pathSeed,flowSiteCheck.host),...(flowSiteKind?{site_kind:flowSiteKind}:{})}:{nodes:[],edges:[],...(flowSiteKind?{site_kind:flowSiteKind}:{})};const result = await save('/flow/flows', planWithoutSite?{name, plan_only:true, customer_id:flowCustomerId||null,campaign_id:flowCampaignId||null,config}:{name, allowed_host: flowSiteCheck.host, customer_id:flowCustomerId||null,campaign_id:flowCampaignId||null,config}, false);location.assign(flowEditorUrl(result.flow.id,fromStrategy||fromPath?{}:{testar:1}));} catch (failure) {setLocalError(failure.message);}};
  return <>
    {localError&&<div className="reports-error" role="alert">{localError}</div>}
    <section className="reports-flow-index">
      <CaduTabs className="reports-flow-index__views" label="Fluxos e modelos" value={indexView} onChange={setIndexView} items={[{id:'flows',label:'Fluxos',count:flows.length},{id:'models',label:'Modelos',count:FLOW_STRATEGIES.length}]}/>
      {indexView==='models'?<FlowTemplateGallery canCreate={data.client.role!=='viewer'} onUse={startFromTemplate} teamTemplates={teamTemplates} onUseTeam={startFromTeamTemplate} onDeleteTeam={deleteTeamTemplate}/>:<>
      <div className="reports-flow-index__tools">
        {allTags.length>0&&<ReportsNativeSelect aria-label="Etiqueta" value={flowTagFilter} onChange={event=>setFlowTagFilter(event.target.value)}><option value="">Todas as etiquetas</option>{allTags.map(tag=><option key={tag} value={tag}>{tag}</option>)}</ReportsNativeSelect>}
        <span className="reports-flow-index__count">{plural(visibleFlows.length,'fluxo','fluxos')}</span>
        {data.client.role!=='viewer'&&<ReportsActionButton color="primary" className="reports-flow-index__new" onClick={()=>setFlowCreateOpen(true)}>Novo fluxo</ReportsActionButton>}
      </div>
      <div className="rs-stack">
        <Section title="Publicados" description="Fluxos medindo agora, com coleta, entradas e conversão dos últimos dias">
          <DataTable label="Fluxos publicados" rows={publishedFlows} rowKey={row=>row.id} initialSort={{key:'updated',dir:'desc'}}
            empty={<EmptyState title={flows.length?'Nenhum fluxo publicado neste site':'Nenhum fluxo ainda'} description={flows.length?'Publique um rascunho para começar a medir.':'Comece por um modelo pronto ou crie um fluxo do zero.'}/>}
            columns={[
              {key:'name',label:'Fluxo',render:row=><>{flowIdentity(row)}</>},
              {key:'collection',label:'Coleta',sort:row=>flowCollection(row).label,render:row=>{const collection=flowCollection(row);const parts=[collection.lastEventAt&&`último evento ${friendlyAgo(collection.lastEventAt)}`,monitorLabel(row)].filter(Boolean);return <><span className={`reports-collection is-${collection.tone}`} title={collection.hint}>{collection.label}</span><small className="rs-cell-sub">{parts.join(' · ')||'\u00a0'}</small></>;}},
              {key:'entries',label:'Entradas',numeric:true,sort:row=>flowResults(row).entries,render:row=>{const results=flowResults(row);return results.hasData?<><strong>{results.entries.toLocaleString('pt-BR')}</strong><small className="rs-cell-sub">últimos {COLLECTION_DAYS} dias</small></>:'—';}},
              {key:'conversions',label:'Conversão',numeric:true,sort:row=>flowResults(row).conversions,render:row=>{const results=flowResults(row);return results.hasData?<><strong>{results.conversions.toLocaleString('pt-BR')}</strong><small className="rs-cell-sub">{formatRate(results.rate)} das entradas</small></>:'—';}},
              {key:'updated',label:'Atualizado',sort:row=>String(row.updated_at||''),render:row=><><strong>{flowUpdatedLabel(row.updated_at)}</strong><small className="rs-cell-sub">{friendlyAgo(row.updated_at)}</small></>},
              {key:'actions',label:<span className="reports-sr-only">Ações</span>,sortable:false,render:row=><span className="reports-flow-table__actions">{flowIconActions(row,true)}</span>},
            ]}/>
        </Section>
        {draftFlows.length>0&&<Section title="Rascunhos e arquivados" description="Planos e fluxos ainda sem medição, esperando a sua revisão">
          <DataTable label="Rascunhos e arquivados" rows={draftFlows} rowKey={row=>row.id} initialSort={{key:'updated',dir:'desc'}} columns={[
            {key:'name',label:'Fluxo',render:row=>flowIdentity(row)},
            {key:'next',label:'Próxima ação',sortable:false,render:row=>{const next=flowNextAction(row);return <button type="button" className={`reports-flow-next is-${next.tone}`} onClick={()=>openFlow(row,next.view)}>{next.label}</button>;}},
            {key:'updated',label:'Atualizado',sort:row=>String(row.updated_at||''),render:row=><><strong>{flowUpdatedLabel(row.updated_at)}</strong><small className="rs-cell-sub">{friendlyAgo(row.updated_at)}</small></>},
            {key:'actions',label:<span className="reports-sr-only">Ações</span>,sortable:false,render:row=><span className="reports-flow-table__actions">{flowIconActions(row,false)}</span>},
          ]}/>
        </Section>}
      </div></>}
    </section>
    <ReportsDrawer open={flowCreateOpen} onOpenChange={setFlowCreateOpen} onDiscard={()=>{setFlowName('');setFlowCustomerId('');setFlowCampaignId('');}} title="Novo fluxo" description="Comece por uma estratégia pronta ou pelo teste da página inicial do site." context={data.client.client_name}>
      {localError&&<div className="reports-error" role="alert">{localError}</div>}
      {data.client.role!=='viewer'?<form className="reports-form reports-flow-new" onSubmit={newFlow}>
        <fieldset className="reports-flow-start"><legend>Ponto de partida</legend>
          <label className="reports-flow-start__option"><input type="radio" name="flow-start" value="strategy" checked={fromStrategy} onChange={()=>setFlowStart('strategy')}/><span><strong>Estratégia pronta</strong><small>Um plano completo por objetivo, com os passos a criar. Não exige páginas no ar.</small></span></label>
          {pathSeed.length>0&&<label className="reports-flow-start__option"><input type="radio" name="flow-start" value="path" checked={fromPath} onChange={()=>setFlowStart('path')}/><span><strong>Caminho observado</strong><small>{pathSeed.join(' → ')}</small></span></label>}
          <label className="reports-flow-start__option"><input type="radio" name="flow-start" value="probe" checked={flowStart==='probe'} onChange={()=>setFlowStart('probe')}/><span><strong>Testar a página inicial</strong><small>Lê o site e propõe o caminho a partir do que já existe.</small></span></label>
        </fieldset>
        {fromStrategy&&<section className="reports-flow-strategies" aria-label="Estratégias">
          <div className="reports-flow-strategies__list" role="radiogroup" aria-label="Estratégia">{teamTemplates.map(item=><button key={item.id} type="button" role="radio" aria-checked={`team:${item.id}`===strategyId} className={`reports-flow-strategy is-team${`team:${item.id}`===strategyId?' is-selected':''}`} onClick={()=>{setStrategyId(`team:${item.id}`);setStrategyChannels([]);}}><strong>{item.name}</strong><small>{[item.sector,'Modelo do time'].filter(Boolean).join(' · ')}</small>{item.description&&<span>{item.description}</span>}</button>)}{FLOW_STRATEGIES.map(item=><button key={item.id} type="button" role="radio" aria-checked={item.id===strategyId} className={`reports-flow-strategy${item.id===strategyId?' is-selected':''}`} onClick={()=>chooseStrategy(item)}><strong>{item.name}</strong><small>{item.objective}</small><span>{item.summary}</span></button>)}</div>
          {teamTemplate&&<p className="reports-flow-team-note">{(teamTemplate.config.nodes||[]).length} passos do modelo do time. Canais, públicos, briefs e taxas vêm do modelo; endereços, prazos, verba e aprovações começam vazios.</p>}
          {strategy&&<fieldset className="reports-flow-strategy__channels"><legend>Canais deste plano</legend>{strategy.channels.map(([kind])=><label key={kind}><input type="checkbox" checked={strategyChannels.includes(kind)} onChange={()=>toggleChannel(kind)}/>{flowBlockRegistry[kind]?.label||kind}</label>)}<small>{strategy.steps.length} passos planejados, cada um com a especificação do que precisa ser criado.</small></fieldset>}
        </section>}
        <div className="reports-flow-new__domain"><label>URL do site{fromStrategy&&<small>Opcional: um plano pode nascer sem site.</small>}<ReportsFieldInput required={!fromStrategy} type="url" value={flowHost} onChange={event=>{siteCheckSequence.current++;setFlowHost(event.target.value);setFlowSiteCheck(null);setFlowSiteChecking(false);}} placeholder="https://www.exemplo.com.br"/></label><ReportsActionButton color="secondary" disabled={!flowHost.trim()||flowSiteChecking} onClick={checkFlowSite}>{flowSiteChecking?'Verificando…':'Validar domínio'}</ReportsActionButton></div>
        {flowSiteCheck&&<div className={`reports-flow-site-check${flowSiteCheck.error?' has-error':''}`} role={flowSiteCheck.error?'alert':'status'}>{flowSiteCheck.error?<p>{flowSiteCheck.error}</p>:<><strong>{flowSiteCheck.title||flowSiteCheck.host}</strong><small>{flowSiteCheck.host} · HTTP {flowSiteCheck.status}</small></>}</div>}
        <label>Nome do fluxo<ReportsFieldInput maxLength="120" value={flowName} onChange={event=>setFlowName(event.target.value)} placeholder={(fromStrategy&&(teamTemplate||strategy)?.name)||flowSiteCheck?.title||'Ex.: Campanha de aquisição 2026'}/></label>
        {!fromStrategy&&<label>Tipo de site<ReportsNativeSelect value={flowSiteKind} onChange={event=>setFlowSiteKind(event.target.value)}><option value="">Descobrir no teste da página inicial</option><option value="landing">Landing page · passos dentro da página</option><option value="institucional">Institucional · menu e contato</option><option value="multipagina">Muitas páginas · conteúdo e leads</option><option value="ecommerce">E-commerce · produto, carrinho e compra</option></ReportsNativeSelect><small>Define como o caminho até a conversão é montado. Você pode mudar depois.</small></label>}
        <details className="reports-flow-new__optional"><summary>Associações <small>Opcional</small></summary>
          <label>Cliente / anunciante<ReportsNativeSelect value={flowCustomerId} onChange={event=>{setFlowCustomerId(event.target.value);setFlowCampaignId('');}}><option value="">Sem anunciante</option>{(data.customers||[]).filter(item=>item.status==='active').map(item=><option key={item.id} value={item.id}>{item.name}</option>)}</ReportsNativeSelect></label>
          <label>Campanha<ReportsNativeSelect value={flowCampaignId} onChange={event=>setFlowCampaignId(event.target.value)}><option value="">Sem campanha</option>{(data.campaigns||[]).filter(item=>!flowCustomerId||String(item.customer_id)===flowCustomerId).map(item=><option key={item.id} value={item.id}>{item.name}</option>)}</ReportsNativeSelect></label>
        </details>
        <div className="reports-flow-new__actions"><p id="flow-create-hint">{flowCreateHint}</p><ReportsActionButton type="submit" color="primary" disabled={busy||flowSiteChecking||(!planWithoutSite&&(!flowSiteCheck||Boolean(flowSiteCheck.error)))||!strategyReady} aria-describedby="flow-create-hint">{fromStrategy?'Criar plano':'Criar fluxo'}</ReportsActionButton></div>
      </form>:<Empty message="Seu acesso permite acompanhar fluxos existentes."/>}
    </ReportsDrawer>
  </>;
}
