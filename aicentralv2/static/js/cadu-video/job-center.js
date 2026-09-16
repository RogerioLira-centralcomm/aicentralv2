import {toSrt} from './composition.js';
import {enablePush} from './push.js';
import {get,studioApi} from './api.js?v=2';
import {state} from './state.js';
import {showJobs,showProcessing,updateProcessing,notify} from '../media-progress.js';
let jobs=[],exports=[],tasks=[],timer,request=0,brand='',initialized=false;
export function bindJobCenter(){
  if(initialized)return;initialized=true;
  document.getElementById('mcStudioJobs')?.addEventListener('click',()=>{showJobs(jobs,exports,brand,tasks);refresh();});
  document.addEventListener('cadu:show-jobs',()=>showJobs(jobs,exports,brand,tasks));
  document.addEventListener('cadu:show-job',event=>{
    const job=jobs.find(row=>row.job_id===event.detail);if(job){history.replaceState(null,'',`#render=${encodeURIComponent(job.job_id)}`);showProcessing(job);}
  });
  document.getElementById('mcStudioNotify')?.addEventListener('click',enablePush);
  document.addEventListener('cadu:task-captions',event=>{const row=tasks.find(r=>r.id===event.detail);if(!row?.result?.captions)return;const url=URL.createObjectURL(new Blob([toSrt(row.result.captions)],{type:'application/x-subrip'}));const link=document.createElement('a');link.href=url;link.download='legendas.srt';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
  window.addEventListener('pagehide',()=>clearTimeout(timer));
}
export async function resetJobCenter(){
  clearTimeout(timer);request++;brand=state.clientId;jobs=[];exports=[];tasks=[];
  if(brand)await refresh(true);
}
async function refresh(initial=false){
  const ticket=++request,client=brand;
  try{
    const result=await get(`${studioApi}/jobs?client_id=${encodeURIComponent(client)}`);
    if(ticket!==request||brand!==client||state.clientId!==client)return;
    jobs=result.items||[];exports=result.exports||[];tasks=result.tasks||[];
    for(const job of jobs)updateProcessing(job);
    const count=jobs.filter(row=>!['ready','failed','cancelled','expired'].includes(row.status)).length+exports.filter(row=>['queued','rendering'].includes(row.status)).length;
    const button=document.getElementById('mcStudioJobs');if(button)button.textContent=`Renderizações${count?` (${count})`:''}`;
    if(initial){
      const selected=new URLSearchParams(location.hash.slice(1)).get('render');
      const target=jobs.find(row=>row.job_id===selected);if(target)showProcessing(target);else if(selected)showJobs(jobs,exports,brand,tasks);
      const pending=jobs.find(row=>!['ready','failed','cancelled','expired'].includes(row.status));
      if(pending)document.dispatchEvent(new CustomEvent('cadu:resume-job',{detail:pending}));
    }
  }catch(error){
    if(initial)document.getElementById('mcStudioJobs')?.setAttribute('title',`Histórico indisponível: ${error.message}`);
  }finally{
    if(ticket===request&&brand===client)timer=setTimeout(()=>refresh(),10000);
  }
}
