import React,{useEffect,useId,useState} from 'react';
import {ReportsFieldInput} from './ReportsFieldInput.jsx';
import {ReportsNativeSelect} from './ReportsNativeSelect.jsx';
import {pageUrl,parsePageUrl} from './flowPageUrl.js';
import {pageLabel,useSitePages} from './useSitePages.js';

const OTHER='__other__';

/** The address of a page: the client's domain is already chosen, so people search a page or, for another domain, paste a URL. */
export function FlowPagePicker({node,readOnly,clientId,csrf,hosts=[],notice='',defaultHost='',planned,onPick,onUrl}) {
  const [domain,setDomain]=useState(null);
  const [query,setQuery]=useState('');
  const [open,setOpen]=useState(false);
  const [active,setActive]=useState(0);
  const [urlDraft,setUrlDraft]=useState(null);
  const [urlError,setUrlError]=useState('');
  const listId=useId();
  const initial=domain??(node.host?(hosts.includes(node.host)?node.host:OTHER):(defaultHost&&hosts.includes(defaultHost)?defaultHost:hosts[0]||OTHER));
  const external=initial===OTHER||!hosts.length;
  const search=useSitePages({clientId,csrf,host:external?'':initial,query,enabled:!external&&open});
  useEffect(()=>{setActive(0);},[query,search.pages.length]);
  const choose=page=>{onPick({host:page.host,path:page.path,name:pageLabel(page)});setQuery('');setOpen(false);};
  const commitUrl=value=>{
    const parsed=parsePageUrl(value);
    if(parsed.error){setUrlError(parsed.error);return;}
    setUrlError('');
    onUrl(parsed);
  };
  const current=pageUrl(node);
  if(external)return <div className="flow-page-picker">
    {hosts.length>0&&<label>Domínio<ReportsNativeSelect disabled={readOnly} value={OTHER} onChange={event=>{setDomain(event.target.value);}}>{hosts.map(host=><option key={host} value={host}>{host}</option>)}<option value={OTHER}>Outro domínio…</option></ReportsNativeSelect></label>}
    <label>{planned?'URL prevista (opcional)':'URL da página'}<ReportsFieldInput disabled={readOnly} inputMode="url" value={urlDraft??current} placeholder="https://www.outrosite.com.br/pagina" aria-invalid={urlError?'true':undefined}
      onFocus={()=>setUrlDraft(current)} onBlur={()=>{if(urlDraft!==null)commitUrl(urlDraft);setUrlDraft(null);}} onChange={event=>{setUrlDraft(event.target.value);setUrlError('');}}
      onKeyDown={event=>{if(event.key==='Enter'){event.preventDefault();commitUrl(event.currentTarget.value);setUrlDraft(null);}}}/>
      {urlError&&<small className="is-error" role="alert">{urlError}</small>}
      {!hosts.length&&notice&&<small>{notice}</small>}</label>
  </div>;
  return <div className="flow-page-picker">
    <label>Domínio<ReportsNativeSelect disabled={readOnly} value={initial} onChange={event=>{setDomain(event.target.value);setQuery('');}}>{hosts.map(host=><option key={host} value={host}>{host}</option>)}<option value={OTHER}>Outro domínio…</option></ReportsNativeSelect></label>
    <div className="flow-page-picker__search">
      <label>{planned?'Página prevista (opcional)':'Página'}<ReportsFieldInput disabled={readOnly} role="combobox" aria-expanded={open} aria-controls={listId} aria-autocomplete="list" autoComplete="off"
        value={open?query:(node.path&&(node.host||initial)===initial?node.path:'')} placeholder="Buscar pelo nome ou endereço" onFocus={()=>{setOpen(true);setQuery('');}}
        onBlur={()=>setTimeout(()=>setOpen(false),140)} onChange={event=>{setQuery(event.target.value);setOpen(true);}}
        onKeyDown={event=>{
          if(event.key==='ArrowDown'){event.preventDefault();setActive(value=>Math.min(search.pages.length-1,value+1));}
          else if(event.key==='ArrowUp'){event.preventDefault();setActive(value=>Math.max(0,value-1));}
          else if(event.key==='Enter'&&open&&search.pages[active]){event.preventDefault();choose(search.pages[active]);}
          else if(event.key==='Escape'){setOpen(false);}
        }}/></label>
      {open&&<ul className="flow-page-picker__list" id={listId} role="listbox" aria-label="Páginas do site">
        {search.pages.map((page,index)=><li key={page.path} role="option" aria-selected={index===active}><button type="button" tabIndex={-1} className={index===active?'is-active':''} onMouseDown={event=>event.preventDefault()} onClick={()=>choose(page)}><strong>{pageLabel(page)}</strong><small>{page.path}</small></button></li>)}
        {!search.pages.length&&<li className="flow-page-picker__empty">{search.loading?'Buscando…':search.notice||'Nenhuma página encontrada. Mude a busca ou use outro domínio.'}</li>}
      </ul>}
    </div>
    {search.truncated&&open&&<small>Mostrando parte do sitemap; refine a busca.</small>}
  </div>;
}
