import React, {useRef, useState} from 'react';
import {ReportsActionButton} from './ReportsActionButton.jsx';
import {ReportsDrawer} from './ReportsDrawer.jsx';
import {ReportsFieldInput} from './ReportsFieldInput.jsx';
import {ReportsNativeSelect} from './ReportsNativeSelect.jsx';
import {plural} from './flowFeedback.js';
import {flowNextAction} from './flowNextAction.js';
import {flowBlockRegistry} from './flowBlockRegistry.js';
import {FLOW_STRATEGIES, buildStrategyConfig, defaultStrategyChannels} from './flowStrategies.js';
import {Empty, flowEditorUrl, json, reportUrl} from './reportsCommon.jsx';

/** Flow list and creation: the entry screen of Fluxos. Owns its own form state; the editor never reads it. */
export function FlowsIndex({data, flows, supertagSites, save, busy}) {
  const [flowHost, setFlowHost] = useState(()=>new URLSearchParams(location.search).get('site_host')||'');
  const [flowCreateOpen,setFlowCreateOpen]=useState(()=>Boolean(new URLSearchParams(location.search).get('site_host')));
  const [flowQuery,setFlowQuery]=useState('');
  const [flowStatusFilter,setFlowStatusFilter]=useState('all');
  const [flowTagFilter,setFlowTagFilter]=useState('');
  const [flowSiteCheck, setFlowSiteCheck] = useState(null);
  const [flowSiteChecking, setFlowSiteChecking] = useState(false);
  const [flowSiteKind,setFlowSiteKind]=useState('');
  const [flowCustomerId,setFlowCustomerId]=useState('');
  const [flowCampaignId,setFlowCampaignId]=useState('');
  const [flowName, setFlowName] = useState('');
  const [flowStart,setFlowStart]=useState('strategy');
  const [strategyId,setStrategyId]=useState('');
  const [strategyChannels,setStrategyChannels]=useState([]);
  const strategy=FLOW_STRATEGIES.find(item=>item.id===strategyId);
  const chooseStrategy=item=>{setStrategyId(item.id);setStrategyChannels(defaultStrategyChannels(item));};
  const toggleChannel=kind=>setStrategyChannels(current=>current.includes(kind)?current.filter(item=>item!==kind):[...current,kind]);
  const fromStrategy=flowStart==='strategy';
  const strategyReady=!fromStrategy||(strategy&&strategyChannels.length>0);
  const [localError,setLocalError]=useState('');
  const superTagForFlow = flowItem => supertagSites.find(site => {
    const allowed = String(site.allowed_host || '').toLowerCase().replace(/^www\./, '');
    const target = String(flowItem?.allowed_host || '').toLowerCase().replace(/^www\./, '');
    return target === allowed || target.endsWith(`.${allowed}`);
  });
  const openFlow = (item, view) => {if(view==='edit')location.assign(flowEditorUrl(item.id,data.client.client_id));else location.assign(reportUrl(`flows/${item.id}/monitor`,{client_id:data.client.client_id}));};
  const flowTags=item=>Array.isArray(item.config?.tags)?item.config.tags:[];
  const allTags=[...new Set(flows.flatMap(flowTags))].sort((a,b)=>a.localeCompare(b,'pt-BR'));
  const visibleFlows=flows.filter(item=>(!flowTagFilter||flowTags(item).includes(flowTagFilter))&&(flowStatusFilter==='all'||(flowStatusFilter==='published'?item.status==='published':item.status!=='published'))&&`${item.name} ${item.allowed_host}`.toLocaleLowerCase('pt-BR').includes(flowQuery.trim().toLocaleLowerCase('pt-BR')));
  const flowMonitorLabel=item=>item.monitor_enabled?({online:'Online',degraded:'Com falhas',offline:'Offline',checking:'Verificando',unknown:'Aguardando checagem'})[item.monitor_status]||'Ativo':'Não ativado';
  const flowUpdatedLabel=value=>{const date=new Date(value);return Number.isNaN(date.getTime())?'—':date.toLocaleDateString('pt-BR',{day:'2-digit',month:'short',year:'numeric'});};
  const flowCreateHint=!strategyReady?'Escolha uma estratégia e ao menos um canal.':!flowHost.trim()?'Informe a URL do site e valide o domínio.':!flowSiteCheck?'Valide o domínio para continuar.':flowSiteCheck.error?'Corrija o domínio para continuar.':superTagForFlow({allowed_host:flowSiteCheck.host})?'A Super Tag deste domínio já existe e será reutilizada.':'A Super Tag será criada automaticamente para este domínio.';
  const siteCheckSequence=useRef(0);
  const checkFlowSite = async () => {const url=flowHost.trim();if(!url)return;const sequence=++siteCheckSequence.current;setFlowSiteChecking(true);setFlowSiteCheck(null);setLocalError('');try{const result=await json(`/connect/api/v2/reports/supertag/site-check?client_id=${data.client.client_id}&url=${encodeURIComponent(url)}`);if(sequence===siteCheckSequence.current)setFlowSiteCheck({...result,verifiedUrl:url});}catch(failure){if(sequence===siteCheckSequence.current)setFlowSiteCheck({error:failure.message});}finally{if(sequence===siteCheckSequence.current)setFlowSiteChecking(false);}};
  const newFlow = async event => {event.preventDefault(); try {if(!flowSiteCheck||flowSiteCheck.error||flowSiteCheck.verifiedUrl!==flowHost.trim())throw new Error('Verifique o domínio atual antes de criar o fluxo.');if(fromStrategy&&!strategyReady)throw new Error('Escolha uma estratégia e ao menos um canal.');const name=flowName||(fromStrategy?strategy.name:flowSiteCheck.title||flowSiteCheck.host);const config=fromStrategy?buildStrategyConfig(strategy,strategyChannels):{nodes:[],edges:[],...(flowSiteKind?{site_kind:flowSiteKind}:{})};const result = await save('/flow/flows', {name, allowed_host: flowSiteCheck.host, customer_id:flowCustomerId||null,campaign_id:flowCampaignId||null,config}, false);location.assign(fromStrategy?flowEditorUrl(result.flow.id,data.client.client_id):`${flowEditorUrl(result.flow.id,data.client.client_id)}&testar=1`);} catch (failure) {setLocalError(failure.message);}};
  return <>
    {localError&&<div className="reports-error" role="alert">{localError}</div>}
    <section className="reports-flow-index">
      <div className="reports-flow-index__tools">
        <ReportsFieldInput type="search" aria-label="Buscar fluxo" placeholder="Buscar por nome ou domínio" value={flowQuery} onChange={event=>setFlowQuery(event.target.value)}/>
        <ReportsNativeSelect aria-label="Estado do fluxo" value={flowStatusFilter} onChange={event=>setFlowStatusFilter(event.target.value)}><option value="all">Todos os estados</option><option value="published">Publicados</option><option value="draft">Rascunhos</option></ReportsNativeSelect>
        {allTags.length>0&&<ReportsNativeSelect aria-label="Etiqueta" value={flowTagFilter} onChange={event=>setFlowTagFilter(event.target.value)}><option value="">Todas as etiquetas</option>{allTags.map(tag=><option key={tag} value={tag}>{tag}</option>)}</ReportsNativeSelect>}
        <span className="reports-flow-index__count">{plural(visibleFlows.length,'fluxo','fluxos')}</span>
        {data.client.role!=='viewer'&&<ReportsActionButton color="primary" className="reports-flow-index__new" onClick={()=>setFlowCreateOpen(true)}>Novo fluxo</ReportsActionButton>}
      </div>
      <article className="reports-panel reports-flow-index__panel">
        {visibleFlows.length?<div className="reports-table-wrap"><table className="reports-flow-table"><thead><tr><th>Fluxo</th><th>Estado</th><th>Coleta</th><th>Próxima ação</th><th>Atualizado</th><th><span className="reports-sr-only">Ações</span></th></tr></thead><tbody>{visibleFlows.map(item=>{const next=flowNextAction(item);return <tr key={item.id}>
          <td><strong>{item.name}</strong><small>{item.allowed_host}{item.campaign_names?` · ${item.campaign_names}`:''}</small>{flowTags(item).length>0&&<span className="reports-flow-tags">{flowTags(item).map(tag=><span key={tag}>{tag}</span>)}</span>}</td>
          <td><span className={`reports-status-badge is-${item.status==='published'?'published':'draft'}`} title={item.flow_code}>{item.status==='published'?'Publicado':'Rascunho'}</span></td>
          <td>{flowMonitorLabel(item)}</td>
          <td><button type="button" className={`reports-flow-next is-${next.tone}`} onClick={()=>openFlow(item,next.view)}>{next.label}</button></td>
          <td>{flowUpdatedLabel(item.updated_at)}</td>
          <td className="reports-flow-table__actions"><ReportsActionButton color="tertiary" onClick={()=>openFlow(item,'edit')}>Editar</ReportsActionButton>{item.status==='published'&&<ReportsActionButton color="tertiary" onClick={()=>openFlow(item,'monitor')}>Monitorar</ReportsActionButton>}</td>
        </tr>;})}</tbody></table></div>:<Empty message={flows.length?'Nenhum fluxo corresponde à busca.':'Nenhum fluxo ainda. Crie o primeiro para mapear a jornada de um site.'}/>}
      </article>
    </section>
    <ReportsDrawer open={flowCreateOpen} onOpenChange={setFlowCreateOpen} onDiscard={()=>{setFlowName('');setFlowCustomerId('');setFlowCampaignId('');}} title="Novo fluxo" description="Comece por uma estratégia pronta ou pelo teste da página inicial do site." context={data.client.client_name}>
      {localError&&<div className="reports-error" role="alert">{localError}</div>}
      {data.client.role!=='viewer'?<form className="reports-form reports-flow-new" onSubmit={newFlow}>
        <fieldset className="reports-flow-start"><legend>Ponto de partida</legend>
          <label className="reports-flow-start__option"><input type="radio" name="flow-start" value="strategy" checked={fromStrategy} onChange={()=>setFlowStart('strategy')}/><span><strong>Estratégia pronta</strong><small>Um plano completo por objetivo, com os passos a criar. Não exige páginas no ar.</small></span></label>
          <label className="reports-flow-start__option"><input type="radio" name="flow-start" value="probe" checked={!fromStrategy} onChange={()=>setFlowStart('probe')}/><span><strong>Testar a página inicial</strong><small>Lê o site e propõe o caminho a partir do que já existe.</small></span></label>
        </fieldset>
        {fromStrategy&&<section className="reports-flow-strategies" aria-label="Estratégias">
          <div className="reports-flow-strategies__list" role="radiogroup" aria-label="Estratégia">{FLOW_STRATEGIES.map(item=><button key={item.id} type="button" role="radio" aria-checked={item.id===strategyId} className={`reports-flow-strategy${item.id===strategyId?' is-selected':''}`} onClick={()=>chooseStrategy(item)}><strong>{item.name}</strong><small>{item.objective}</small><span>{item.summary}</span></button>)}</div>
          {strategy&&<fieldset className="reports-flow-strategy__channels"><legend>Canais deste plano</legend>{strategy.channels.map(([kind])=><label key={kind}><input type="checkbox" checked={strategyChannels.includes(kind)} onChange={()=>toggleChannel(kind)}/>{flowBlockRegistry[kind]?.label||kind}</label>)}<small>{strategy.steps.length} passos planejados, cada um com a especificação do que precisa ser criado.</small></fieldset>}
        </section>}
        <div className="reports-flow-new__domain"><label>URL do site<ReportsFieldInput required type="url" value={flowHost} onChange={event=>{siteCheckSequence.current++;setFlowHost(event.target.value);setFlowSiteCheck(null);setFlowSiteChecking(false);}} placeholder="https://www.exemplo.com.br"/></label><ReportsActionButton color="secondary" disabled={!flowHost.trim()||flowSiteChecking} onClick={checkFlowSite}>{flowSiteChecking?'Verificando…':'Validar domínio'}</ReportsActionButton></div>
        {flowSiteCheck&&<div className={`reports-flow-site-check${flowSiteCheck.error?' has-error':''}`} role={flowSiteCheck.error?'alert':'status'}>{flowSiteCheck.error?<p>{flowSiteCheck.error}</p>:<><strong>{flowSiteCheck.title||flowSiteCheck.host}</strong><small>{flowSiteCheck.host} · HTTP {flowSiteCheck.status}</small></>}</div>}
        <label>Nome do fluxo<ReportsFieldInput maxLength="120" value={flowName} onChange={event=>setFlowName(event.target.value)} placeholder={(fromStrategy&&strategy?.name)||flowSiteCheck?.title||'Ex.: Campanha de aquisição 2026'}/></label>
        {!fromStrategy&&<label>Tipo de site<ReportsNativeSelect value={flowSiteKind} onChange={event=>setFlowSiteKind(event.target.value)}><option value="">Descobrir no teste da página inicial</option><option value="landing">Landing page · passos dentro da página</option><option value="institucional">Institucional · menu e contato</option><option value="multipagina">Muitas páginas · conteúdo e leads</option><option value="ecommerce">E-commerce · produto, carrinho e compra</option></ReportsNativeSelect><small>Define como o caminho até a conversão é montado. Você pode mudar depois.</small></label>}
        <details className="reports-flow-new__optional"><summary>Associações <small>Opcional</small></summary>
          <label>Cliente / anunciante<ReportsNativeSelect value={flowCustomerId} onChange={event=>{setFlowCustomerId(event.target.value);setFlowCampaignId('');}}><option value="">Sem anunciante</option>{(data.customers||[]).filter(item=>item.status==='active').map(item=><option key={item.id} value={item.id}>{item.name}</option>)}</ReportsNativeSelect></label>
          <label>Campanha<ReportsNativeSelect value={flowCampaignId} onChange={event=>setFlowCampaignId(event.target.value)}><option value="">Sem campanha</option>{(data.campaigns||[]).filter(item=>!flowCustomerId||String(item.customer_id)===flowCustomerId).map(item=><option key={item.id} value={item.id}>{item.name}</option>)}</ReportsNativeSelect></label>
        </details>
        <div className="reports-flow-new__actions"><p id="flow-create-hint">{flowCreateHint}</p><ReportsActionButton type="submit" color="primary" disabled={busy||flowSiteChecking||!flowSiteCheck||Boolean(flowSiteCheck.error)||!strategyReady} aria-describedby="flow-create-hint">{fromStrategy?'Criar plano':'Criar fluxo'}</ReportsActionButton></div>
      </form>:<Empty message="Seu acesso permite acompanhar fluxos existentes."/>}
    </ReportsDrawer>
  </>;
}
