// The one thing a flow needs next, derived from what the list already loads. View is where the action happens.
export function flowNextAction(flow) {
  const nodes=flow?.config?.nodes||[];
  if(flow?.revoked_at)return {label:'Reativar a tag do site',view:'edit',tone:'warning'};
  // A plan without a site is complete as a plan; measurement is a later choice.
  if(flow?.allowed_host==='')return {label:nodes.length?'Revisar o plano':'Montar o plano',view:'edit',tone:nodes.length?'neutral':'brand'};
  if(!nodes.length)return {label:'Testar conversão',view:'edit',tone:'brand'};
  if(!nodes.some(node=>node.type==='source'))return {label:'Adicionar a origem do tráfego',view:'edit',tone:'brand'};
  // Institutional sites are read by engagement; they do not need a conversion step.
  if(flow.config?.site_kind!=='institucional'&&!nodes.some(node=>node.type==='conversion'))return {label:'Definir a conversão',view:'edit',tone:'warning'};
  if(flow.status!=='published')return {label:'Revisar e publicar',view:'edit',tone:'brand'};
  if(flow.monitor_enabled&&['offline','degraded'].includes(flow.monitor_status))return {label:'Verificar a coleta',view:'monitor',tone:'warning'};
  return {label:'Acompanhar jornada',view:'monitor',tone:'neutral'};
}
