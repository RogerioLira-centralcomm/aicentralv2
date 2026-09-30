import {useEffect, useState} from 'react';

/** One request at a time, hidden-tab pause, cancellation and bounded backoff. */
export function useFlowPolling(url,{enabled=true,interval=15000}={}) {
  const [state,setState]=useState({url:null,data:null,error:null,updatedAt:null});
  const [retry,setRetry]=useState(0);
  useEffect(()=>{
    if(!url||!enabled)return;
    let disposed=false,pending=false,timer,failures=0,cursor=null;
    const controller=new AbortController();
    const poll=async()=>{
      clearTimeout(timer);if(disposed||pending||document.hidden)return;pending=true;
      try {
        const target=new URL(url,location.origin);if(cursor&&target.pathname.endsWith('/live'))target.searchParams.set('since',cursor);
        const response=await fetch(target,{signal:controller.signal,credentials:'same-origin',headers:{Accept:'application/json'}});
        const result=await response.json();
        if(!response.ok)throw new Error(result.message||result.error||`Falha HTTP ${response.status}`);
        failures=0;cursor=result.next_cursor||cursor;if(!disposed)setState({url,data:result,error:null,updatedAt:new Date()});
      } catch(error) {
        if(!disposed){failures++;setState(old=>({...old,url,data:old.url===url?old.data:null,error:error.message}));}
      } finally {
        pending=false;if(!disposed&&!document.hidden&&interval)timer=setTimeout(poll,Math.min(60000,interval*2**Math.max(0,failures-1)));
      }
    };
    const visibility=()=>{clearTimeout(timer);if(!document.hidden)poll();};
    poll();document.addEventListener('visibilitychange',visibility);
    return()=>{disposed=true;clearTimeout(timer);controller.abort();document.removeEventListener('visibilitychange',visibility);};
  },[url,enabled,interval,retry]);
  return {...(state.url===url?state:{data:null,error:null,updatedAt:null}),retry:()=>setRetry(n=>n+1)};
}
