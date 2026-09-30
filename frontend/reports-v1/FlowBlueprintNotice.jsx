import React,{useEffect,useState} from 'react';
import {ReportsActionButton} from './ReportsActionButton.jsx';
export function FlowBlueprintNotice({flowId,clientId,onOpen}){
 const [message,setMessage]=useState('');
 useEffect(()=>{let disposed=false,timer,controller;const key=`reports-blueprint:${clientId}:${flowId}`;
 const poll=async()=>{let job;try{job=JSON.parse(sessionStorage.getItem(key)||'null');}catch{return;}
 if(!job?.job_id)return;controller=new AbortController();const timeout=setTimeout(()=>controller.abort(),10000);
 try{const response=await fetch(`/connect/api/v2/reports/flow/blueprint-jobs/${job.job_id}?client_id=${clientId}`,{signal:controller.signal});if(!response.ok)return;const state=await response.json();if(disposed)return;if(state.status==='ready'){setMessage('Proposta pronta para revisar');return;}if(state.status==='failed'){setMessage('A montagem precisa de atenção');return;}if(state.status==='cancelled')return;
 }catch{/* Retry only while this flow remains open. */}finally{clearTimeout(timeout);}
 if(!disposed)timer=setTimeout(poll,5000);};poll();return()=>{disposed=true;clearTimeout(timer);controller?.abort();};},[clientId,flowId]);
 return message?<div className="flow-blueprint-notice" role="status"><ReportsActionButton onClick={onOpen}>{message}</ReportsActionButton></div>:null;
}
