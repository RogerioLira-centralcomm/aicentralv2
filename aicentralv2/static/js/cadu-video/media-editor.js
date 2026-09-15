import {mediaTask,awaitMediaTask} from './media-tasks.js';
import {state} from './state.js';
import {post} from './api.js';
import {csrf} from '../trocr/animate-utils.js';
const base='/parametros/api/format-lab/studio';
const $=id=>document.getElementById(id);
let request=0, info=null, volume=1, musicVolume=.35;
function peaks(id, values=[]) {
  const node=$(id); if(!node)return;
  node.innerHTML=values.map((value,i)=>`<path d="M${i*600/values.length} ${14-value*13}v${value*26}" stroke="currentColor" stroke-width="2"/>`).join('');
}
export function bindMediaEditor(dirty,paint,reloadSounds) {
  document.addEventListener("cadu:clip-cleared",()=>{
    request++;info=null;
    $("mcStudioFilmstrip").replaceChildren();peaks("mcStudioOriginalWaveform");
    $("mcStudioOriginalLabel").textContent="Abra um vídeo para analisar o áudio";
    $("mcStudioExtractAudio").disabled=true;$("mcStudioMuteOriginal").disabled=true;
  });
  function mute(key){
    if(state.edit[key]>0){if(key==='original_volume')volume=state.edit[key];else musicVolume=state.edit[key];state.edit[key]=0;}
    else state.edit[key]=key==='original_volume'?volume:musicVolume;
    dirty();paint();paintMute();
  }
  function paintMute(){
    for(const [key,id] of [['original_volume','mcStudioMuteOriginal'],['sound_volume','mcStudioMuteSound']]){
      const off=state.edit[key]===0;$(id).textContent=off?'Ativar':'Mutar';$(id).setAttribute('aria-pressed',String(off));
    }
    $('mcStudioMuteSound').disabled=!state.edit.sound_id;
  }
  $('mcStudioMuteOriginal')?.addEventListener('click',()=>mute('original_volume'));
  $('mcStudioMuteSound')?.addEventListener('click',()=>mute('sound_volume'));
  document.addEventListener('cadu:studio-paint',paintMute);
  document.addEventListener('cadu:clip-selected',async()=>{
    const ticket=++request,client=state.clientId,clip=state.activeClipId;
    info=null;$('mcStudioOriginalLabel').textContent='Analisando áudio original…';
    $('mcStudioExtractAudio').disabled=true;$('mcStudioMuteOriginal').disabled=true;
    $('mcStudioFilmstrip').replaceChildren();peaks('mcStudioOriginalWaveform');
    try {
      const result=await mediaTask('inspect',{client_id:client,clip_id:clip});
      if(ticket!==request || client!==state.clientId || clip!==state.activeClipId)return;
      info=result;
      const clipRow=state.clips.find(row=>row.id===clip||row.job_id===clip);
      if(clipRow){clipRow.waveform=result.waveform||[];clipRow.waveform_levels=result.waveform_levels||null;clipRow.frames=result.frames||[];}
      $('mcStudioOriginalLabel').textContent=result.has_audio?'Áudio original do vídeo':'Vídeo sem faixa de áudio';
      $('mcStudioExtractAudio').disabled=!result.has_audio;$('mcStudioMuteOriginal').disabled=!result.has_audio;
      peaks('mcStudioOriginalWaveform',result.waveform);
      $('mcStudioFilmstrip').replaceChildren(...result.frames.map(frame=>{
        const image=document.createElement('img');image.src=frame.url;image.alt=`Quadro em ${frame.time.toFixed(1)}s`;image.loading='lazy';return image;
      }));
      paintMute();paint();
    }catch(error){if(ticket===request && client===state.clientId)$('mcStudioOriginalLabel').textContent=`Análise indisponível: ${error.message}`;}
  });
  $('mcStudioExtractAudio')?.addEventListener('click',async()=>{
    if(!info?.has_audio)return;
    const client=state.clientId, clip=state.activeClipId;
    $('mcStudioExtractAudio').disabled=true;
    try{
      await mediaTask('extract',{client_id:client,clip_id:clip},{overlay:true,title:'Extraindo áudio'});
      if(client!==state.clientId)return;
      await reloadSounds();state.libTab='sound';paint();
      $('mcStudioOriginalLabel').textContent='Áudio extraído. Disponível em Sons.';
    }catch(error){$('mcStudioOriginalLabel').textContent=error.message;}
    finally{$('mcStudioExtractAudio').disabled=clip!==state.activeClipId || !info?.has_audio;}
  });
  $('mcStudioVideoFile')?.addEventListener('change',async event=>{
    const file=event.target.files?.[0];event.target.value='';if(!file)return;
    const client=state.clientId;
    const status=$('mcStudioExportStatus');status.hidden=false;
    if(!client){status.textContent='Escolha uma marca.';return;}
    if(file.size>150*1024*1024){status.textContent='Envie um vídeo de até 150 MB.';return;}
    event.target.disabled=true;status.textContent='Enviando vídeo e preparando quadros e áudio…';
    const form=new FormData();form.append('file',file);form.append('client_id',client);form.append('kind','import');
    form.append('autocut',JSON.stringify({enabled:$('mcImportAutoCut')?.checked===true,mode:$('mcImportCutMode')?.value,max_cuts:Number($('mcImportCutLimit')?.value)||30,transition:$('mcImportTransition')?.value}));
    try{
      const started=Date.now();
      const result=await new Promise((resolve,reject)=>{
        const xhr=new XMLHttpRequest();xhr.open('POST',`${base}/tasks`);xhr.setRequestHeader('X-Trocr-CSRF-Token',csrf());xhr.responseType='json';
        xhr.upload.onprogress=e=>{status.textContent=`Enviando vídeo${e.lengthComputable?' · '+Math.round(e.loaded/e.total*100)+'%':''} · ${Math.floor((Date.now()-started)/1000)}s. Mantenha a página aberta até concluir o envio.`;};
        xhr.onerror=()=>reject(new Error('Envio interrompido. Tente novamente.'));
        xhr.onload=()=>xhr.status>=200&&xhr.status<300&&xhr.response?.success!==false?resolve(xhr.response):reject(new Error(xhr.response?.error||'Falha ao importar vídeo.'));
        xhr.send(form);
      });
      const ready=await awaitMediaTask(result.data||result,client,{overlay:true,title:'Preparando vídeo e quadros'});
      if(client!==state.clientId)return;
      document.dispatchEvent(new CustomEvent('cadu:clip-imported',{detail:ready}));
      status.textContent=ready.autocut_warning || (ready.autocut ? `${ready.autocut.cuts.length} cortes preparados · ${ready.autocut.removed_duration.toFixed(1)}s removidos. Revise a montagem e restaure cortes quando necessário.` : 'Vídeo pronto. Arraste as bordas na timeline para cortar; ajuste áudio, velocidade e fades em Editar.');
    }catch(error){if(client===state.clientId)status.textContent=error.message;}
    finally{event.target.disabled=false;}
  });
}
