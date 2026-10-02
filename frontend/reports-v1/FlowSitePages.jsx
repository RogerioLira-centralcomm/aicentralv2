import React,{useState} from 'react';
import {ReportsActionButton as Button} from './ReportsActionButton.jsx';
import {ReportsFieldInput} from './ReportsFieldInput.jsx';
import {ReportsNativeSelect} from './ReportsNativeSelect.jsx';
import {pageLabel,useSitePages} from './useSitePages.js';

/** Search the pages of the client's site and add several to the map at once; names come from the address until real titles load. */
export function FlowSitePages({clientId,csrf,nodes,readOnly,onAdd,onAdded,onLocate}) {
  const [host,setHost]=useState('');
  const [query,setQuery]=useState('');
  const [picked,setPicked]=useState(()=>new Set());
  const catalog=useSitePages({clientId,csrf,host,query});
  const inMap=new Map(nodes.filter(node=>node.path).map(node=>[`${node.host||catalog.host}${node.path}`,node]));
  const toggle=key=>setPicked(current=>{const next=new Set(current);next.has(key)?next.delete(key):next.add(key);return next;});
  const add=()=>{
    const pages=catalog.pages.filter(page=>picked.has(`${page.host}${page.path}`)&&!inMap.has(`${page.host}${page.path}`));
    pages.forEach(page=>onAdd({title:pageLabel(page).slice(0,60),path:page.path,host:page.host}));
    setPicked(new Set());
    onAdded?.();
  };
  const count=[...picked].filter(key=>!inMap.has(key)).length;
  return <div className="flow-site-pages">
    {catalog.hosts.length>1&&<ReportsNativeSelect aria-label="Domínio" value={catalog.host} onChange={event=>{setHost(event.target.value);setPicked(new Set());}}>{catalog.hosts.map(item=><option key={item} value={item}>{item}</option>)}</ReportsNativeSelect>}
    {catalog.hosts.length===1&&<small className="flow-site-pages__host">{catalog.host}{catalog.pageCount?` · ${catalog.pageCount.toLocaleString('pt-BR')} páginas`:''}</small>}
    <ReportsFieldInput type="search" aria-label="Buscar páginas" placeholder="Buscar pelo nome ou endereço" value={query} onChange={event=>setQuery(event.target.value)}/>
    {catalog.notice&&<small className="flow-site-pages__notice">{catalog.notice}</small>}
    <ul className="flow-site-pages__list" aria-label="Páginas do site">
      {catalog.pages.map(page=>{const key=`${page.host}${page.path}`,existing=inMap.get(key);
        return <li key={key} className={existing?'is-mapped':''}>
          <label><input type="checkbox" disabled={readOnly||Boolean(existing)} checked={Boolean(existing)||picked.has(key)} onChange={()=>toggle(key)}/>
            <span><strong>{pageLabel(page)}</strong><small>{page.path}</small></span></label>
          {existing&&<Button color="link-color" size="sm" className="flow-site-pages__locate" onClick={()=>onLocate(existing.id)}>No mapa</Button>}
        </li>;})}
      {!catalog.pages.length&&<li className="flow-site-pages__empty">{catalog.loading?'Buscando…':catalog.hosts.length?'Nenhuma página encontrada.':'Cole a URL da página no inspetor.'}</li>}
    </ul>
    {catalog.truncated&&<small>Mostrando parte do sitemap; refine a busca.</small>}
    {!readOnly&&<div className="flow-site-pages__bar"><Button color="primary" disabled={!count} onClick={add}>{count?`Adicionar ${count} ao mapa`:'Marque as páginas'}</Button></div>}
  </div>;
}
