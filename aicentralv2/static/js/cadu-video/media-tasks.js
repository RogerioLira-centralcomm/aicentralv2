import {get,post} from './api.js';
import {showProcessing,updateProcessing} from '../media-progress.js';
const base='/parametros/api/format-lab/studio';
export async function awaitMediaTask(row,client,{overlay=false,title='Preparando mídia',signal}={}){
  if(!row?.kind)return row; // Compatibility with cached inspections and older servers.
  const id=`task:${row.id}`;
  if(overlay)showProcessing({job_id:id,title,background_supported:true,status:row.status,message:'O processamento continua no servidor.',ui_stages:[{id:'queued',label:'Na fila'},{id:'processing',label:title},{id:'ready',label:'Pronto'}]});
  while(!['ready','failed'].includes(row.status)){
    if(signal?.aborted)throw new DOMException('Aborted','AbortError');
    await new Promise(resolve=>setTimeout(resolve,1200));
    row=await get(`${base}/tasks/${row.id}?client_id=${encodeURIComponent(client)}`);
    if(overlay)updateProcessing({...row,job_id:id,stage:row.status});
  }
  if(row.status==='failed')throw new Error(row.error||'Falha no processamento.');
  return row.result;
}
export async function mediaTask(kind,data,options={}){
  const row=await post(`${base}/tasks`,{...data,kind});
  return awaitMediaTask(row,data.client_id,options);
}
