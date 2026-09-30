import React,{useEffect,useState} from 'react';
import {FlowMonitorWorkspace} from './FlowMonitorWorkspace.jsx';
import {ReportsPageHeader} from './PageChrome.jsx';
import {ReportsActionButton as Button} from './ReportsActionButton.jsx';
export function SharedReports({data}){
 const [flows,setFlows]=useState([]),[sites,setSites]=useState([]),[selected,setSelected]=useState(null),[error,setError]=useState('');
 useEffect(()=>{const controller=new AbortController();fetch(`/connect/api/v2/reports/shared/resources?client_id=${data.client.client_id}`,{signal:controller.signal}).then(async r=>{if(!r.ok)throw new Error('Não foi possível consultar seus acessos.');return r.json();}).then(r=>{setFlows(r.flows);setSites(r.sites||[]);}).catch(e=>{if(e.name!=='AbortError')setError(e.message);});return()=>controller.abort();},[data.client.client_id]);
 const header=<ReportsPageHeader clients={data.clients} client={data.client} titleOverride="Compartilhados com você" descriptionOverride={data.client.client_name}/>;
 if(selected)return <>{header}<FlowMonitorWorkspace key={selected.id} flow={selected} client={data.client} csrf={data.csrf} filters={{period:'30'}} baseConfig={selected.config} onBack={()=>setSelected(null)}/></>;
 return <div data-cadu-skin="reports">{header}<main className="reports-content">{error&&<p role="alert">{error}</p>}{sites.map(s=><p key={s.id}><strong>{s.label}</strong> · {s.allowed_host} · {s.events_30d} eventos nos últimos 30 dias</p>)}{flows.map(f=><p key={f.id}>{f.name} <Button onClick={()=>setSelected(f)}>Monitorar</Button></p>)}{!flows.length&&!error&&<p>Nenhum fluxo compartilhado disponível.</p>}</main></div>;
}
