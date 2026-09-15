import {state} from './state.js';
export function deliveryOptions(preview=false){
  const brand=document.getElementById('mcCaduBarClient')?.selectedOptions?.[0]?.textContent?.trim()||`marca_${state.clientId}`;
  return {format:preview?'mp4':document.getElementById('mcStudioExportFormat')?.value||'mp4',brand,creative:document.getElementById('mcVideoName')?.value.trim()||state.name||'criativo'};
}
export function downloadExport(result,client){
  if(result.status!=='ready')return;
  const key=`cadu-downloaded:${result.id}`;if(sessionStorage.getItem(key))return;
  const url=result.download_url||`/parametros/api/format-lab/studio/exports/${result.id}/content?client_id=${encodeURIComponent(client)}`;
  const anchor=document.createElement('a');anchor.href=url;anchor.download=result.filename||'';anchor.hidden=true;
  document.body.appendChild(anchor);anchor.click();anchor.remove();sessionStorage.setItem(key,'1');
}

let progress=null,timer,resetTimer;
const phases={queued:'Na fila',rendering:'Preparando',ready:'Download iniciado',failed:'Falhou'};
function renderProgress(){
  const select=document.getElementById('mcStudioExportFormat');if(!select||!progress)return;
  const host=select.closest('.mc-studio-export-format');
  if(!host.querySelector('.mc-download-spinner')){const spinner=document.createElement('span');spinner.className='mc-download-spinner';spinner.setAttribute('aria-hidden','true');host.appendChild(spinner);}
  let option=select.querySelector('[data-download-progress]');if(!option){option=new Option('','__progress');option.dataset.downloadProgress='';select.prepend(option);}
  const seconds=Math.max(0,Math.floor((Date.now()-progress.started)/1000)),clock=`${String(Math.floor(seconds/60)).padStart(2,'0')}:${String(seconds%60).padStart(2,'0')}`;
  const busy=!['ready','failed'].includes(progress.status),label=phases[progress.status]||'Preparando';
  option.textContent=`${label} ${progress.format.toUpperCase()} · ${clock}`;select.value='__progress';select.disabled=busy;
  select.setAttribute('aria-busy',String(busy));select.title=`${label}. ${clock} decorridos. O download começa automaticamente quando o arquivo fica pronto.`;
  host.classList.toggle('is-downloading',busy);host.classList.toggle('is-download-ready',progress.status==='ready');host.classList.toggle('is-download-failed',progress.status==='failed');
  if(busy)select.dataset.busy='1';else delete select.dataset.busy;
}
export function beginDownload(id,client,format='mp4'){
  clearInterval(timer);clearTimeout(resetTimer);
  let saved;try{saved=JSON.parse(sessionStorage.getItem(`cadu-download-ui:${client}`)||'null');}catch{}
  progress=saved?.id===id?saved:{id,client,format,started:Date.now(),status:'queued'};
  progress.status='queued';sessionStorage.setItem(`cadu-download-ui:${client}`,JSON.stringify(progress));renderProgress();timer=setInterval(renderProgress,1000);
}
export function updateDownload(result){
  if(!progress||progress.id!==result.id)return;
  progress.status=result.status;sessionStorage.setItem(`cadu-download-ui:${progress.client}`,JSON.stringify(progress));renderProgress();
  if(['ready','failed'].includes(result.status)){clearInterval(timer);sessionStorage.removeItem(`cadu-download-ui:${progress.client}`);resetTimer=setTimeout(clearDownload,5000);}
}
export function clearDownload(){
  clearInterval(timer);clearTimeout(resetTimer);progress=null;
  const select=document.getElementById('mcStudioExportFormat');if(!select)return;
  select.querySelector('[data-download-progress]')?.remove();select.value='';select.removeAttribute('aria-busy');select.removeAttribute('title');delete select.dataset.busy;
  select.closest('.mc-studio-export-format')?.classList.remove('is-downloading','is-download-ready','is-download-failed');
  document.dispatchEvent(new Event('cadu:studio-paint'));
}
window.addEventListener('pagehide',()=>{clearInterval(timer);clearTimeout(resetTimer);});
