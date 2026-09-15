import {paintLivePreview,previewTime,seekLivePreview,schedule} from './live-preview.js';
import {keyframeEditor,bindKeyframes} from './keyframes.js';
import {mediaTask} from './media-tasks.js';
import {state} from './state.js';
import {get,post} from './api.js';
import {escapeHtml as esc,newId} from './utils.js';
import {showProcessing,updateProcessing,notify} from '../media-progress.js';
const $=id=>document.getElementById(id),base='/parametros/api/format-lab/studio';
let dirty,refresh,signature='',dragId='',rendering=false;
export const emptyComposition=()=>({enabled:false,items:[],audio:[],captions:[],selected:'',resolution:720,fps:30,preview_url:'',preview_valid:false});
const comp=()=>state.composition ||= emptyComposition();
const fingerprint=()=>JSON.stringify({items:comp().items,audio:comp().audio,captions:comp().captions,resolution:comp().resolution,fps:comp().fps,ratio:state.aspectRatio,layers:state.edit?.layers||[]});
const item=()=>comp().items.find(row=>row.id===comp().selected);
const asset=row=>(row?.kind==='image'?state.library:state.clips).find(source=>source.id===row?.asset_id);
const length=row=>row.kind==='image'?row.duration:Math.max(.1,((row.out||asset(row)?.duration||4)-row.in)/row.speed);
export function compositionDuration(){return comp().items.reduce((total,row,index)=>total+length(row)-(index&&comp().items[index-1].transition!=='cut'?Math.min(comp().items[index-1].transition_duration,length(row)/2,length(comp().items[index-1])/2):0),0);}
function changed(){comp().preview_valid=false;dirty();paintComposition();paintCompositionCanvas();}
export function bindComposition(commit,paint){
  dirty=commit;refresh=paint;
  bindKeyframes($('mcCompositionControls'),()=>item(),changed,row=>Math.max(0,previewTime()-(schedule(comp().items).find(r=>r.row.id===row.id)?.start||0)));
  $('mcCompositionMode')?.addEventListener('click',()=>{comp().enabled=!comp().enabled;dirty();refresh();paintComposition();});
  $('mcCompositionAdd')?.addEventListener('click',()=>{
    const value=$('mcCompositionAsset').value;const kind=value.startsWith('image:')?'image':'video',id=value.slice(kind.length+1);
    const source=(kind==='image'?state.library:state.clips).find(row=>row.id===id);if(!source||comp().items.length>=30)return;
    const row={id:newId(),asset_id:id,kind,in:0,out:Number(source.duration)||0,duration:4,speed:1,volume:1,fit:'contain',motion:'none',transition:'cut',transition_duration:.4};
    comp().items.push(row);comp().selected=row.id;comp().enabled=true;changed();refresh();seekLivePreview(schedule(comp().items).find(r=>r.row.id===row.id)?.start||0);
  });
  $('mcCompositionTracks')?.addEventListener('click',event=>{
    const button=event.target.closest('[data-composition-item]');if(!button)return;
    comp().selected=button.dataset.compositionItem;comp().preview_valid=false;paintComposition();paintCompositionCanvas();seekLivePreview(schedule(comp().items).find(r=>r.row.id===comp().selected)?.start||0);
  });
  $('mcCompositionTracks')?.addEventListener('dragstart',event=>{dragId=event.target.closest('[data-composition-item]')?.dataset.compositionItem||'';});
  $('mcCompositionTracks')?.addEventListener('dragover',event=>event.preventDefault());
  $('mcCompositionTracks')?.addEventListener('drop',event=>{
    event.preventDefault();const target=event.target.closest('[data-composition-item]')?.dataset.compositionItem;
    const from=comp().items.findIndex(row=>row.id===dragId),to=comp().items.findIndex(row=>row.id===target);
    if(from>=0&&to>=0){const [row]=comp().items.splice(from,1);comp().items.splice(to,0,row);changed();}
  });
  $('mcCompositionControls')?.addEventListener('change',event=>{
    const input=event.target,row=item(),key=input.dataset.composeKey;if(!row||!key)return;
    row[key]=input.type==='number'?Math.min(Number(input.max),Math.max(Number(input.min),Number(input.value)||0)):input.value;changed();
  });
  $('mcCompositionControls')?.addEventListener('click',event=>{
    const action=event.target.dataset.composeAction,row=item();if(!action||!row)return;
    const index=comp().items.indexOf(row);
    if(action==='delete'){comp().items.splice(index,1);comp().selected=comp().items[Math.min(index,comp().items.length-1)]?.id||'';}
    if(action==='duplicate'&&comp().items.length<30){const copy={...row,id:newId()};comp().items.splice(index+1,0,copy);comp().selected=copy.id;}
    if(action==='split'&&comp().items.length<30){
      const copy={...row,id:newId()};
      if(row.kind==='image'){if(row.duration<.4)return;row.duration/=2;copy.duration=row.duration;}
      else{const end=row.out||asset(row)?.duration,at=comp().preview_valid?$('mcSwapVideo').currentTime:row.in+Math.max(0,previewTime()-(schedule(comp().items).find(r=>r.row.id===row.id)?.start||0))*row.speed;if(!(at>row.in+.1&&at<end-.1)){notify('Posicione a reprodução dentro do clipe para dividir.');return;}row.out=at;copy.in=at;copy.out=end;}
      row.transition='cut';comp().items.splice(index+1,0,copy);comp().selected=copy.id;
    }
    if(action==='before'&&index>0){comp().items.splice(index,1);comp().items.splice(index-1,0,row);}
    if(action==='after'&&index<comp().items.length-1){comp().items.splice(index,1);comp().items.splice(index+1,0,row);}
    changed();
  });
  document.addEventListener('cadu:composition-sound',event=>{
    if(comp().audio.length>=8){notify('A montagem aceita até oito faixas adicionais.');return;}
    const row=event.detail;comp().audio.push({sound_id:row.id,name:row.name,start:0,in:0,duration:Math.min(row.duration||10,compositionDuration()||10),volume:.35,muted:false,fade_in:0,fade_out:0,loop:false});changed();
  });
  $('mcCompositionAudio')?.addEventListener('change',event=>{
    const input=event.target,row=comp().audio[Number(input.dataset.audioIndex)],key=input.dataset.audioKey;if(!row||!key)return;
    row[key]=input.type==='checkbox'?input.checked:Math.min(Number(input.max),Math.max(Number(input.min),Number(input.value)||0));changed();
  });
  $('mcCompositionAudio')?.addEventListener('click',event=>{const index=event.target.dataset.audioRemove;if(index!==undefined){comp().audio.splice(Number(index),1);changed();}});
  $('mcCompositionResolution')?.addEventListener('change',event=>{comp().resolution=Number(event.target.value);changed();});
  $('mcCompositionFps')?.addEventListener('change',event=>{comp().fps=Number(event.target.value);changed();});
  $('mcCompositionPreview')?.addEventListener('click',()=>exportComposition(true));
  $('mcCompositionCaptionFile')?.addEventListener('change',async event=>{
    const file=event.target.files?.[0];event.target.value='';if(!file)return;
    if(file.size>1024*1024){notify('Envie um SRT de até 1 MB.');return;}
    try{comp().captions=parseSrt(await file.text());changed();}catch(error){notify(error.message);}
  });
  $('mcCompositionCaptions')?.addEventListener('change',event=>{const input=event.target,row=comp().captions[Number(input.dataset.caption)],key=input.dataset.captionKey;if(!row||!key)return;row[key]=key==='text'?input.value:Number(input.value);changed();});
  $('mcCompositionTranscribe')?.addEventListener('click',async event=>{
    if(!comp().items.length){notify('Adicione imagens e vídeos antes de transcrever.');return;}
    const button=event.currentTarget,client=state.clientId,before=fingerprint();button.disabled=true;
    try{
      const result=await mediaTask('transcribe',{client_id:client,composition:{...structuredClone(comp()),ratio:state.aspectRatio}},{overlay:true,title:'Transcrevendo áudio da montagem'});
      if(client!==state.clientId)return;
      if(before!==fingerprint()){notify('A montagem mudou durante a transcrição. As legendas estão salvas em Renderizações; gere novamente para os novos tempos.');return;}
      comp().captions=result.captions;changed();notify(result.captions.length?'Legendas geradas. Revise os nomes e a pontuação.':'Nenhuma fala reconhecida neste áudio.');
    }catch(error){notify(error.message);}finally{button.disabled=false;}
  });
  $('mcCompositionCaptions')?.addEventListener('click',event=>{const index=event.target.dataset.captionRemove;if(index!==undefined){comp().captions.splice(Number(index),1);changed();}});
  $('mcCompositionCaptionAdd')?.addEventListener('click',()=>{if(comp().captions.length<500){comp().captions.push({start:0,end:3,text:'Nova legenda'});changed();}});
  $('mcCompositionCaptionDownload')?.addEventListener('click',()=>{
    const url=URL.createObjectURL(new Blob([toSrt(comp().captions)],{type:'application/x-subrip;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='legendas.srt';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  });
}
function number(key,label,value,min,max,step='.1',extra=''){return `<label>${label}<input type="number" min="${min}" max="${max}" step="${step}" value="${Number(value)||0}" ${extra||`data-compose-key="${key}"`}></label>`;}
export function paintComposition(){
  if(!$('mcCompositionTracks'))return;
  const c=comp(),row=item();if(c.preview_valid&&c.preview_signature!==fingerprint())c.preview_valid=false;$('mcCompositionMode').setAttribute('aria-pressed',String(c.enabled));$('mcCompositionMode').textContent=c.enabled?'Montagem ativa':'Montar sequência';
  $('mcSwap').classList.toggle('is-composition',c.enabled);$('mcCompositionTracks').hidden=!c.enabled;
  const selectedAsset=$('mcCompositionAsset').value;
  $('mcCompositionAsset').innerHTML=[...state.clips.map(row=>`<option value="video:${esc(row.id)}">Vídeo · ${esc(row.name)}</option>`),...state.library.filter(row=>!row.broken).map(row=>`<option value="image:${esc(row.id)}">Imagem · ${esc(row.name)}</option>`)].join('');
  if([...$('mcCompositionAsset').options].some(option=>option.value===selectedAsset))$('mcCompositionAsset').value=selectedAsset;
  const key=JSON.stringify([c,state.aspectRatio,state.clips.map(r=>r.id),state.library.map(r=>r.id)]);if(key===signature)return;signature=key;
  $('mcCompositionDuration').textContent=`${compositionDuration().toFixed(1)}s · ${c.items.length} itens${c.preview_valid?' · Prévia atualizada':' · Prévia instantânea'}`;
  $('mcCompositionTracks').innerHTML=`<div class="mc-composition-lane">${c.items.map((row,i)=>{const source=asset(row);return `<button type="button" draggable="true" class="${row.id===c.selected?'is-selected':''}" data-composition-item="${esc(row.id)}" style="flex-grow:${length(row)}"><img src="${esc(source?.thumb_url||source?.poster_url||source?.image_url||'')}" alt=""><strong>${i+1}. ${esc(source?.name||'Mídia indisponível')}</strong><small>${length(row).toFixed(1)}s · ${esc(row.transition)}</small></button>`;}).join('')}</div>${c.audio.map((track,i)=>`<div class="mc-composition-audio-lane" style="opacity:${track.muted ? .45 : 1}"><span>♫ ${i+1} · ${esc(track.name||'Áudio')} · ${track.start}s → ${(track.start+track.duration).toFixed(1)}s ${track.muted?'· Mudo':''}</span></div>`).join('')}${c.captions.length?`<div class="mc-composition-caption-lane">CC · ${c.captions.length} legendas editáveis</div>`:''}`;
  const select=(key,label,values)=>`<label>${label}<select data-compose-key="${key}">${values.map(([value,text])=>`<option value="${value}" ${row?.[key]===value?'selected':''}>${text}</option>`).join('')}</select></label>`;
  $('mcCompositionControls').innerHTML=row?`<h4>${esc(asset(row)?.name||'Item selecionado')}</h4><div class="mc-studio-pair">${row.kind==='image'?number('duration','Duração (s)',row.duration,.2,300):number('in','Entrada (s)',row.in,0,300)+number('out','Saída (s)',row.out,0,300)+number('speed','Velocidade',row.speed,.25,4,'.25')}${number('volume','Volume original',row.volume,0,1,'.05')}</div>${select('fit','Enquadramento',[['contain','Caber sem cortar'],['cover','Preencher com corte central']])}${row.kind==='image'?select('motion','Animação da imagem',[['none','Fixa'],['zoom','Zoom suave']]):''}${select('transition','Próxima cena',[['cut','Corte'],['fade','Dissolver'],['fadeblack','Passar pelo preto'],['slideleft','Deslizar'],['wipeleft','Revelar']])}${number('transition_duration','Duração da transição',row.transition_duration,.1,2)}${keyframeEditor(row.keyframes)}<div class="mc-composition-actions">${[['split','Dividir'],['duplicate','Duplicar'],['before','Antes'],['after','Depois'],['delete','Excluir']].map(([a,t])=>`<button type="button" data-compose-action="${a}">${t}</button>`).join('')}</div>`:'<p>Adicione e selecione uma mídia na sequência.</p>';
  $('mcCompositionAudio').innerHTML=c.audio.map((track,i)=>`<fieldset><legend>${esc(track.name||`Áudio ${i+1}`)}</legend><div class="mc-studio-pair">${[['start','Posição (s)',600],['in','Cortar início (s)',600],['duration','Duração (s)',600],['volume','Volume',1],['fade_in','Fade in (s)',10],['fade_out','Fade out (s)',10]].map(([key,label,max])=>number(key,label,track[key],0,max,'.1',`data-audio-index="${i}" data-audio-key="${key}"`)).join('')}</div><label><input type="checkbox" data-audio-index="${i}" data-audio-key="muted" ${track.muted?'checked':''}> Mutar faixa</label><label><input type="checkbox" data-audio-index="${i}" data-audio-key="loop" ${track.loop?'checked':''}> Repetir</label><button type="button" data-audio-remove="${i}">Remover faixa</button></fieldset>`).join('');
  $('mcCompositionCaptions').innerHTML=c.captions.map((row,i)=>`<div class="mc-composition-caption"><input aria-label="Início da legenda ${i+1}" type="number" min="0" max="600" step=".1" value="${row.start}" data-caption="${i}" data-caption-key="start"><input aria-label="Fim da legenda ${i+1}" type="number" min="0" max="600" step=".1" value="${row.end}" data-caption="${i}" data-caption-key="end"><textarea aria-label="Legenda ${i+1}" maxlength="300" data-caption="${i}" data-caption-key="text">${esc(row.text)}</textarea><button type="button" data-caption-remove="${i}" aria-label="Excluir legenda ${i+1}">Excluir</button></div>`).join('');
  $('mcCompositionResolution').value=c.resolution;$('mcCompositionFps').value=c.fps;
}
export function paintCompositionCanvas(){
  const c=comp();if(paintLivePreview())return true;if(!c.enabled)return false;
  const row=item(),source=asset(row),video=$('mcSwapVideo'),still=$('mcVideoStill');
  const url=c.preview_valid&&c.preview_url?c.preview_url:row?.kind==='video'?source?.video_url:'';
  if(url){
    if(video.getAttribute('src')!==url){video.pause();video.src=url;video.load();}
    video.hidden=false;still.hidden=true;$('mcVideoEmpty').hidden=true;
    video.playbackRate=c.preview_valid?1:row?.speed||1;video.volume=c.preview_valid?1:row?.volume??1;
    video.style.filter='';video.style.transform='';video.style.opacity=1;
  }else{video.pause();video.hidden=true;still.hidden=!source;still.src=source?.image_url||source?.thumb_url||'';$('mcVideoEmpty').hidden=Boolean(source);}
  $('mcVideoStageMeta').textContent=c.preview_valid?'Prévia da montagem':source?.name||'Monte sua sequência';
  return true;
}
export function syncCompositionPlayback(){
  if(!comp().enabled)return false;
  const video=$('mcSwapVideo'),row=item();
  if(!comp().preview_valid&&row?.kind==='video'&&!video.paused){const end=row.out||video.duration;if(video.currentTime<row.in)video.currentTime=row.in;if(video.currentTime>=end){video.pause();video.currentTime=row.in;}}
  return true;
}
export async function exportComposition(preview=false){
  const c=comp();if(rendering||!c.items.length)return;
  if(c.captions.some(row=>!Number.isFinite(row.start)||!Number.isFinite(row.end)||row.end<=row.start)){notify('Corrija o início e o fim das legendas antes de renderizar.');return;}
  const client=state.clientId,id=newId().replaceAll('-',''),snapshot=fingerprint();
  const composition={...structuredClone(c),ratio:state.aspectRatio,layers:structuredClone(state.edit.layers||[])};
  rendering=true;showProcessing({job_id:`export:${id}`,kind:'export',title:preview?'Preparando prévia':'Renderizando montagem',background_supported:false,status:'queued',message:'Salvando a sequência…',preview_images:c.items.map(row=>asset(row)?.thumb_url||asset(row)?.poster_url||asset(row)?.image_url).filter(Boolean),plan:{aspect_ratio:state.aspectRatio,duration:compositionDuration()},ui_stages:[{id:'queued',label:'Na fila'},{id:'rendering',label:'Compondo cenas, áudio e legendas'},{id:'ready',label:'Pronto'}]});
  try{
    await post(`${base}/composition/exports`,{client_id:client,request_id:id,composition});
    updateProcessing({job_id:`export:${id}`,status:'queued',background_supported:true});
    const poll=async()=>{
      if(client!==state.clientId){rendering=false;return;}
      try{
        const result=await get(`${base}/exports/${id}?client_id=${encodeURIComponent(client)}`),url=`${base}/exports/${id}/content?client_id=${encodeURIComponent(client)}`;
        updateProcessing({...result,job_id:`export:${id}`,kind:'export',stage:result.status,version:result.status==='ready'?{video_url:url}:undefined,message:result.status==='ready'?'Montagem concluída.':'Renderizando sequência…'});
        if(['ready','failed'].includes(result.status)){
          rendering=false;
          if(result.status==='ready'&&snapshot===fingerprint()){comp().preview_url=url;comp().preview_valid=true;comp().preview_signature=snapshot;dirty();paintComposition();paintCompositionCanvas();}
          return;
        }
      }catch(error){notify(`Acompanhamento interrompido: ${error.message}. Consulte Renderizações.`);rendering=false;return;}
      setTimeout(poll,3000);
    };poll();
  }catch(error){rendering=false;updateProcessing({job_id:`export:${id}`,status:'failed',error:error.message});}
}
export function parseSrt(text){
  const time=value=>{const [h,m,s]=value.replace(',','.').split(':').map(Number);return h*3600+m*60+s;};
  const rows=String(text).replace(/^\uFEFF/,'').replace(/\r/g,'').trim().split(/\n\s*\n/).map(block=>{
    const lines=block.split('\n'),index=lines.findIndex(line=>line.includes('-->'));if(index<0)return null;
    const parts=lines[index].match(/(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,.]\d{3})/);if(!parts)return null;
    return {start:time(parts[1]),end:time(parts[2]),text:lines.slice(index+1).join('\n').slice(0,300)};
  }).filter(row=>row&&row.end>row.start&&row.start>=0&&row.end<=600);
  if(!rows.length||rows.length>500)throw new Error('Use um SRT válido, com até 500 legendas e duração de até 10 minutos.');return rows;
}
export function toSrt(rows){const stamp=value=>{const ms=Math.round(value*1000);return `${String(Math.floor(ms/3600000)).padStart(2,'0')}:${String(Math.floor(ms/60000)%60).padStart(2,'0')}:${String(Math.floor(ms/1000)%60).padStart(2,'0')},${String(ms%1000).padStart(3,'0')}`;};return rows.map((row,i)=>`${i+1}\n${stamp(row.start)} --> ${stamp(row.end)}\n${row.text}`).join('\n\n');}
