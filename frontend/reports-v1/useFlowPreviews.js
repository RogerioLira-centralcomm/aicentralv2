import {useCallback,useEffect,useState} from 'react';

export function useFlowPreviews({flowId,clientId,csrf,canCapture=false,revision}={}) {
  const url=flowId&&clientId?`/connect/api/v1/reports/flow/flows/${flowId}/previews?client_id=${clientId}${revision?`&revision=${revision}`:''}`:null;
  const [state,setState]=useState({url:null,items:{},available:true});
  const [refresh,setRefresh]=useState(0);
  const [regenerate,setRegenerate]=useState(null);
  const capture=useCallback(id=>{setRegenerate(id);setRefresh(n=>n+1);},[]);
  useEffect(()=>{
    if(!url)return;
    let disposed=false,timer,pending=false;
    const controller=new AbortController();
    let requested=regenerate;
    const poll=async()=>{
      if(pending||disposed||document.hidden)return;
      pending=true;
      try {
        const response=await fetch(url,{method:canCapture?'POST':'GET',credentials:'same-origin',signal:controller.signal,headers:canCapture?{'Content-Type':'application/json','X-CSRF-Token':csrf}:{},...(canCapture?{body:JSON.stringify(requested?{node_id:requested}:{})}:{})});
        const result=await response.json();
        if(!response.ok)throw new Error(result.message||'Captura indisponível');
        requested=null;
        if(!disposed)setState({url,items:result.items||{},available:result.available!==false});
        if(!disposed&&result.available!==false)timer=setTimeout(poll,Object.values(result.items||{}).some(item=>['missing','capturing'].includes(item.status))?5000:30000);
      }catch(error){if(!disposed&&!controller.signal.aborted){setState(old=>({...old,url,error:error.message||'Não foi possível consultar as capturas.'}));timer=setTimeout(poll,30000);}}
      finally{pending=false;}
    };
    const visible=()=>{clearTimeout(timer);if(!document.hidden)poll();};
    poll();document.addEventListener('visibilitychange',visible);
    return()=>{disposed=true;clearTimeout(timer);controller.abort();document.removeEventListener('visibilitychange',visible);};
  },[url,canCapture,csrf,refresh]);
  return {...(state.url===url?state:{items:{},available:true}),regenerate:capture};
}
