import {useCallback, useEffect, useState} from 'react';

/** Serialized, bounded requests; stale responses never restore live indicators. */
export function useFlowPolling(url,{enabled=true,interval=15000}={}) {
  const [state,setState]=useState({url:null,data:null,error:null,updatedAt:null});
  const [retry,setRetry]=useState(0);
  const [fresh,setFresh]=useState(false);
  const retryNow=useCallback(()=>setRetry(n=>n+1),[]);
  useEffect(()=>{
    setFresh(false);
    if(!url||!enabled)return;
    let disposed=false,pending=false,timer,expiry,failures=0,cursor=null,controller;
    const poll=async()=>{
      clearTimeout(timer);
      if(disposed||pending||document.hidden)return;
      pending=true;
      controller=new AbortController();
      let timedOut=false;
      const timeout=setTimeout(()=>{timedOut=true;controller.abort();},12000);
      try {
        const target=new URL(url,location.origin);
        if(cursor&&target.pathname.endsWith('/live'))target.searchParams.set('since',cursor);
        const response=await fetch(target,{signal:controller.signal,credentials:'same-origin',headers:{Accept:'application/json'}});
        let result;
        try {result=await response.json();} catch(error) {
          if(controller.signal.aborted)throw error;
          throw new Error(response.ok?'Resposta inválida do servidor.':`Falha HTTP ${response.status}. Tente novamente.`);
        }
        if(!response.ok)throw new Error(result.message||result.error||`Falha HTTP ${response.status}`);
        failures=0;cursor=result.next_cursor||cursor;
        if(!disposed){
          setFresh(!document.hidden);clearTimeout(expiry);
          expiry=setTimeout(()=>setFresh(false),Math.max(30000,interval*2));
          setState({url,data:result,error:null,updatedAt:new Date()});
        }
      } catch(error) {
        if(!disposed){
          setFresh(false);
          if(!document.hidden){failures++;setState(old=>({...old,url,data:old.url===url?old.data:null,error:timedOut?'A consulta demorou mais que o esperado. Tentando novamente…':error.message}));}
        }
      } finally {
        clearTimeout(timeout);pending=false;
        if(!disposed&&!document.hidden&&interval)timer=setTimeout(poll,Math.min(60000,interval*2**Math.max(0,failures-1)));
      }
    };
    const visibility=()=>{setFresh(false);clearTimeout(timer);if(document.hidden)controller?.abort();else poll();};
    poll();document.addEventListener('visibilitychange',visibility);
    return()=>{disposed=true;clearTimeout(timer);clearTimeout(expiry);controller?.abort();document.removeEventListener('visibilitychange',visibility);};
  },[url,enabled,interval,retry]);
  return {...(state.url===url?state:{data:null,error:null,updatedAt:null}),fresh:enabled&&state.url===url&&fresh,retry:retryNow};
}
