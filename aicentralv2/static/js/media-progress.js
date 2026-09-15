/* Shared, accessible processing surface for Studio and Trocar. */
const escape=value=>String(value??'').replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const terminal=status=>['ready','failed','cancelled','expired'].includes(status);
let dialog,active=null,started=0,frameTimer,focusBefore,known=new Map();
function ensure(){
  if(dialog)return;
  const link=document.createElement('link');link.rel='stylesheet';link.href='/static/css/media-progress.css';document.head.appendChild(link);
  dialog=document.createElement('dialog');dialog.id='caduProcessing';dialog.className='cadu-processing';dialog.setAttribute('aria-labelledby','caduProcessingTitle');
  dialog.innerHTML=`<header><span>Cadu Media Studio</span><button type="button" data-close aria-label="Fechar acompanhamento">Continuar editando ×</button></header><main id="caduProcessingBody"></main><footer><span id="caduProcessingNotice"></span><button type="button" data-history>Ver renderizações</button></footer>`;
  document.body.appendChild(dialog);
  dialog.addEventListener('click',event=>{
    if(event.target.closest('[data-close]'))dialog.close();
    if(event.target.closest('[data-history]'))document.dispatchEvent(new Event('cadu:show-jobs'));
    if(event.target.closest('[data-open-result]')&&active?.version){dialog.close();document.dispatchEvent(new CustomEvent('cadu:job-open',{detail:active}));}
    const task=event.target.closest('[data-task-captions]');if(task)document.dispatchEvent(new CustomEvent('cadu:task-captions',{detail:task.dataset.taskCaptions}));
    const row=event.target.closest('[data-job-id]');if(row)document.dispatchEvent(new CustomEvent('cadu:show-job',{detail:row.dataset.jobId}));
  });
  dialog.addEventListener('close',()=>{focusBefore?.focus?.();});
  frameTimer=setInterval(()=>{
    if(!dialog.open)return;
    const elapsed=document.getElementById('caduProcessingElapsed');
    if(elapsed)elapsed.textContent=`${Math.floor((Date.now()-started)/1000)}s decorridos`;
    const pictures=[...dialog.querySelectorAll('.cadu-processing-frames img')];
    if(pictures.length)pictures.forEach((image,i)=>image.classList.toggle('is-current',i===Math.floor(Date.now()/2800)%pictures.length));
  },1000);
  window.addEventListener('pagehide',()=>clearInterval(frameTimer));
}
function open(){ensure();if(!dialog.open){focusBefore=document.activeElement;dialog.showModal();}}
export function followingJob(id){return Boolean(dialog?.open && active?.job_id===id);}
export function showProcessing(job={}){
  ensure();active=job;started=job.created_at?(typeof job.created_at==='number'?job.created_at*1000:new Date(job.created_at).getTime()):Date.now();
  paint(job);open();
}
function paint(job){
  const done=job.status==='ready',failed=['failed','cancelled','expired'].includes(job.status);
  const images=(job.preview_images||[]).filter(url=>typeof url==='string'&&url.startsWith('/')&&!url.startsWith('//')).slice(0,12);
  const stages=job.ui_stages||[{id:'prepare',label:'Preparando imagens'},{id:'submit',label:'Enviando ao modelo'},{id:'queue',label:'Na fila'},{id:'generate',label:'Gerando vídeo'},{id:'validate',label:'Validando resultado'}];
  const index=stages.findIndex(row=>row.id===job.stage);
  document.getElementById('caduProcessingBody').innerHTML=`<section class="cadu-processing-preview">${done&&job.version?.video_url?`<video controls playsinline preload="metadata" src="${escape(job.version.video_url)}"></video>`:`<div class="cadu-processing-frames">${images.map((url,i)=>`<img class="${i===0?'is-current':''}" src="${escape(url)}" alt="Cena ${i+1}">`).join('')||'<span class="cadu-processing-placeholder">Seu vídeo está sendo preparado</span>'}</div>`}<span class="cadu-processing-format">${escape(job.plan?.piece_ratio||job.plan?.aspect_ratio||'')} ${job.plan?.duration?`· ${escape(job.plan.duration)}s`:''}</span></section><section class="cadu-processing-detail"><h1 id="caduProcessingTitle">${done?'Seu vídeo está pronto':failed?'Precisamos revisar esta etapa':escape(job.title||'Criando vídeo')}</h1><p role="status">${escape(job.error||job.message||'Preparando o projeto para envio…')}</p>${!terminal(job.status)?'<div class="cadu-processing-loader" role="progressbar" aria-label="Processamento em andamento"></div>':''}<small id="caduProcessingElapsed"></small><ol>${stages.map((row,i)=>`<li class="${done||i<index?'is-done':i===index?'is-active':''}"><span>${done||i<index?'✓':i+1}</span>${escape(row.label)}</li>`).join('')}</ol>${done?(job.kind==='export'?`<p>${job.auto_download===false?'Prévia disponível no editor.':'O download foi iniciado automaticamente.'}</p>${job.public_url?`<a class="cadu-processing-primary" href="${escape(job.public_url)}" target="_blank" rel="noopener">Abrir página pública</a>`:''}`:'<button type="button" class="cadu-processing-primary" data-open-result>Abrir na edição</button>'):''}${failed?'<p>O projeto foi preservado. Nenhuma nova geração será enviada automaticamente.</p>':''}</section>`;
  document.getElementById('caduProcessingNotice').textContent=terminal(job.status)?'Resultado disponível no histórico da marca.':job.job_id&&job.background_supported!==false?'O trabalho foi salvo no servidor. Você pode fechar esta página.':'Aguarde a confirmação do envio antes de fechar esta página.';
}
export function updateProcessing(job){
  ensure();const previous=known.get(job.job_id);known.set(job.job_id,job.status);
  if(active?.job_id===job.job_id || (!active?.job_id && dialog.open && job.job_id && job.adopt_pending)){
    active={...active,...job};paint(active);
  }
  if(previous&&!terminal(previous)&&terminal(job.status)){
    const message=job.status==='ready'?'Seu vídeo ficou pronto.':'O processamento precisa de atenção.';
    if(!followingJob(job.job_id))notify(message,()=>showProcessing(job));
    if(document.hidden&&globalThis.Notification?.permission==='granted')new Notification('Cadu Media Studio',{body:message});
  }
}
export function showJobs(items=[],exports=[],client='',tasks=[]){
  ensure();active=null;
  const buttons=items.map(job=>`<button type="button" class="cadu-processing-job" data-job-id="${escape(job.job_id)}"><span>${job.status==='ready'?'✓':'◷'}</span><strong>${escape(job.plan?.piece_ratio||job.plan?.aspect_ratio||'Vídeo')} · ${escape(job.plan?.duration||'')}s</strong><small>${escape(job.message||job.status)}</small></button>`).join('');
  const renders=exports.map(row=>`<article class="cadu-processing-job"><strong>${escape(row.filename||'Exportação da edição')}</strong><small>${escape(({ready:'Pronta',queued:'Na fila',rendering:'Renderizando',failed:'Falhou'})[row.status]||row.status)}</small>${row.status==='ready'?`<a href="/parametros/api/format-lab/studio/exports/${escape(row.id)}/content?client_id=${encodeURIComponent(client)}">Baixar ${escape((row.format||'mp4').toUpperCase())}</a>`:''}</article>`).join('');
  document.getElementById('caduProcessingBody').innerHTML=`<section class="cadu-processing-history"><h1 id="caduProcessingTitle">Renderizações</h1><p>Gerações e exportações salvas nesta marca.</p>${buttons+renders+tasks.map(row=>`<article class="cadu-processing-job"><strong>${escape(({import:'Importação de vídeo',inspect:'Quadros e áudio',extract:'Extração de áudio',transcribe:'Transcrição'})[row.kind]||'Mídia')}</strong><small>${escape(row.error||({ready:'Pronto',failed:'Falhou',queued:'Na fila',processing:'Processando'})[row.status]||row.status)}</small>${row.status==='ready'&&row.kind==='transcribe'?`<button type="button" data-task-captions="${escape(row.id)}">Baixar SRT</button>`:''}</article>`).join('')||'<p>Nenhum processamento encontrado.</p>'}</section>`;
  document.getElementById('caduProcessingNotice').textContent='Você pode sair e consultar os resultados quando voltar.';open();
}
export function notify(message,action){
  ensure();document.getElementById('caduProcessingToast')?.remove();
  const toast=document.createElement('aside');toast.id='caduProcessingToast';toast.setAttribute('role','status');
  const text=document.createElement('span');text.textContent=message;toast.appendChild(text);
  if(action){const button=document.createElement('button');button.textContent='Ver resultado';button.onclick=()=>{toast.remove();action();};toast.appendChild(button);}
  const close=document.createElement('button');close.textContent='×';close.setAttribute('aria-label','Dispensar notificação');close.onclick=()=>toast.remove();toast.appendChild(close);document.body.appendChild(toast);
}
document.addEventListener('trocr:animate-progress',event=>updateProcessing(event.detail));
