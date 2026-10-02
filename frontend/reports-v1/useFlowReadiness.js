import {useEffect,useState} from 'react';
export function useFlowReadiness(flowId,clientId){
 const [state,setState]=useState(null);const key=`${clientId}:${flowId}`;
 useEffect(()=>{if(!flowId)return;let disposed=false,timer,controller;const poll=async()=>{controller=new AbortController();const timeout=setTimeout(()=>controller.abort(),10000);try{const response=await fetch(`/connect/api/v2/reports/flow/flows/${flowId}/readiness`,{signal:controller.signal});if(!response.ok)throw new Error();const value=await response.json();if(!disposed)setState({key,ready:value.tracking_ready});}catch{if(!disposed)setState({key,ready:undefined});}finally{clearTimeout(timeout);if(!disposed)timer=setTimeout(poll,30000);}};poll();return()=>{disposed=true;clearTimeout(timer);controller?.abort();};},[key,flowId,clientId]);
 return state?.key===key?state.ready:undefined;
}
