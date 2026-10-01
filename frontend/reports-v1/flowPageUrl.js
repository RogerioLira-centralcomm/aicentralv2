// A page is its URL. The document keeps host and path (what the collector matches); people see and type one URL.
export function parsePageUrl(input) {
  const text=String(input||'').trim();
  if(!text)return {empty:true};
  if(text.startsWith('/')){
    if(text.startsWith('//'))return {error:'Cole a URL completa da página.'};
    return {host:'',path:`/${text.split('#')[0].split('?')[0].replace(/^\/+/,'')}`};
  }
  let url;
  try{url=new URL(/^[a-z][a-z0-9+.-]*:\/\//i.test(text)?text:`https://${text}`);}catch{return {error:'Não parece uma URL. Exemplo: https://www.site.com.br/oferta'};}
  if(!['http:','https:'].includes(url.protocol)||!url.hostname.includes('.')&&url.hostname!=='localhost')return {error:'Use uma URL com domínio. Exemplo: https://www.site.com.br/oferta'};
  return {host:url.hostname.toLowerCase().replace(/\.$/,''),path:url.pathname||'/'};
}

/** The address as shown to people: the full URL when the host is known, otherwise the path. */
export function pageUrl(node) {
  if(!node?.path)return '';
  return node.host?`https://${node.host}${node.path==='/'?'':node.path}`:node.path;
}

/** Host of the first page that has one, to suggest the site when the plan is connected. */
export function suggestedHost(config) {
  return (config?.nodes||[]).find(node=>node.host)?.host||'';
}
