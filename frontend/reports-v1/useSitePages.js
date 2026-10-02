import {useCallback, useEffect, useRef, useState} from 'react';
import {json} from './reportsCommon.jsx';

const base='/connect/api/v2/reports/flow/site-pages';

/** Search the page catalog of the client's domains; real titles of the visible results are fetched once and cached server-side. */
export function useSitePages({clientId,csrf,host='',query='',enabled=true,debounce=220}) {
  const [state,setState]=useState({hosts:[],host:'',pages:[],notice:'',loading:false,pageCount:0,truncated:false});
  const asked=useRef(new Set());
  useEffect(()=>{
    if(!enabled||!clientId)return undefined;
    let current=true;
    setState(previous=>({...previous,loading:true}));
    const timer=setTimeout(()=>{
      json(`${base}?${host?`host=${encodeURIComponent(host)}&`:''}q=${encodeURIComponent(query.trim())}`)
        .then(result=>{if(current)setState({hosts:result.hosts||[],host:result.host||'',pages:result.pages||[],notice:result.notice||'',loading:false,pageCount:result.page_count||0,truncated:Boolean(result.truncated)});})
        .catch(failure=>{if(current)setState(previous=>({...previous,loading:false,notice:failure.message||'Não foi possível buscar as páginas.'}));});
    },debounce);
    return()=>{current=false;clearTimeout(timer);};
  },[clientId,host,query,enabled,debounce]);
  const {pages,host:activeHost}=state;
  useEffect(()=>{
    if(!enabled||!activeHost||!csrf)return undefined;
    const missing=pages.filter(page=>!page.title&&!asked.current.has(`${page.host}${page.path}`)).slice(0,8);
    if(!missing.length)return undefined;
    missing.forEach(page=>asked.current.add(`${page.host}${page.path}`));
    let current=true;
    json(`${base}/titles`,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify({host:activeHost,paths:missing.map(page=>page.path)})})
      .then(result=>{if(!current)return;const byPath=new Map((result.pages||[]).map(page=>[page.path,page]));
        setState(previous=>({...previous,pages:previous.pages.map(page=>byPath.get(page.path)?.title?{...page,title:byPath.get(page.path).title}:page)}));})
      .catch(()=>{});
    return()=>{current=false;};
  },[pages,activeHost,enabled,clientId,csrf]);
  const refresh=useCallback(()=>json(`${base}/refresh`,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify({host:activeHost})}),[clientId,csrf,activeHost]);
  return {...state,refresh};
}

export const pageLabel=page=>page.title||page.name;
