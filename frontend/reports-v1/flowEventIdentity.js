const kinds={page:'page_view',form:'form_submit',event:'custom_event',conversion:'conversion',whatsapp:'whatsapp_click',error:'error_view'};
export function eventMatchesNode(event,node,host='') {
  return event.page_path===node.path && (!node.host&&!host||event.page_host===(node.host||host))
    && event.event_kind===kinds[node.type]
    && (!['event','conversion'].includes(node.type)||!node.event_name||event.event_name===node.event_name);
}
export function uniqueFlowEvents(events=[]) {
  const unique=new Map();
  for(const event of events){const key=[event.page_host||'',event.page_path,event.event_kind,event.event_name||''].join('\u0000');
    const prior=unique.get(key);unique.set(key,{...event,total:Number(event.total||0)+Number(prior?.total||0)});}
  return [...unique.values()];
}
