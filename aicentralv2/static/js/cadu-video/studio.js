import {deliveryOptions,downloadExport,beginDownload,updateDownload,clearDownload} from './delivery.js';
import {bindComposition,paintComposition,paintCompositionCanvas,syncCompositionPlayback,exportComposition} from './composition.js';
import {showProcessing,updateProcessing} from '../media-progress.js';
import {bindJobCenter,resetJobCenter} from './job-center.js';
import {bindTextLayers,paintTextLayers,paintTextPreview} from './text-layers.js';
import {bindMediaEditor} from './media-editor.js';
import { bindSeedancePanel, paintSeedancePanel } from "./seedance-panel.js";
import { bindAgentPanel, paintAgentPanel } from "./agent-panel.js";
import { bindWorkspace, paintTimelinePosition } from "./workspace.js";
import { state, upsertWorkspaceSpend } from './state.js';
import { get, post, studioApi } from './api.js?v=2';
import { csrf } from '../trocr/animate-utils.js';
import { escapeHtml, newId } from './utils.js';

const base = studioApi;
export const defaultEdit = () => ({layers:[],start:0,end:0,speed:1,original_volume:1,sound_id:'',sound_volume:.35,sound_offset:0,fade_in:0,fade_out:0,loop:false,video_fade_in:0,video_fade_out:0,grayscale:false,flip:false});
const fields = {mcStudioOriginal:'original_volume',mcStudioVolume:'sound_volume',mcStudioOffset:'sound_offset',mcStudioFadeIn:'fade_in',mcStudioFadeOut:'fade_out',mcStudioTrimStart:'start',mcStudioTrimEnd:'end',mcStudioSpeed:'speed',mcStudioLoop:'loop',mcStudioVideoFadeIn:'video_fade_in',mcStudioVideoFadeOut:'video_fade_out',mcStudioGrayscale:'grayscale',mcStudioFlip:'flip'};
const $ = id => document.getElementById(id);
let sounds = [], brand = '', dirty, repaint, undo = [], redo = [], baseline = '', restoring = false;
let soundPlayer = new Audio(), pollTimer, frame, exporting = false, soundRequest = 0;
const time = value => `${Math.floor((value || 0)/60)}:${String(Math.floor((value || 0)%60)).padStart(2,'0')}`;
const snapshot = () => JSON.stringify({name:state.name,scenes:state.scenes,script:state.script,audio:state.audio,motion:state.motion,generationMode:state.generationMode,duration:state.duration,quality:state.quality,aspectRatio:state.aspectRatio,aspectExplicit:state.aspectExplicit,seed:state.seed,edit:state.edit,composition:state.composition});

export function resetClipHistory() { undo=[]; redo=[]; baseline=snapshot(); updateHistory(); }

export function recordStudioChange() {
  if (restoring || !baseline) return;
  const next = snapshot();
  if (next === baseline) return;
  undo.push(baseline); if (undo.length > 50) undo.shift();
  redo = []; baseline = next;
  updateHistory();
}
function updateHistory() { if ($('mcStudioUndo')) $('mcStudioUndo').disabled = !undo.length; if ($('mcStudioRedo')) $('mcStudioRedo').disabled = !redo.length; }
function restoreHistory(from, to) {
  if (!from.length) return;
  to.push(snapshot()); restoring = true;
  Object.assign(state, JSON.parse(from.pop()));
  baseline = snapshot();
  if (!state.scenes.some(s => s.id === state.selectedSceneId)) state.selectedSceneId = state.scenes[0]?.id || '';
  dirty(); repaint(); restoring = false; updateHistory();
}

export function bindStudio(markDirty, paintAll) {
  dirty = markDirty; repaint = paintAll;
  state.edit ||= defaultEdit();
  bindWorkspace(state, markDirty, paintStudio);
  bindJobCenter();
  bindMediaEditor(markDirty, paintAll, loadSounds);
  bindTextLayers(markDirty);
  bindComposition(markDirty,paintAll);
  bindSeedancePanel(state, markDirty, paintStudio);
  bindAgentPanel(state, markDirty, paintAll);
  $('mcStudioUndo')?.addEventListener('click', () => restoreHistory(undo,redo));
  $('mcStudioRedo')?.addEventListener('click', () => restoreHistory(redo,undo));
  document.addEventListener('keydown', event => {
    if (!(event.ctrlKey || event.metaKey) || event.key.toLowerCase() !== 'z' || event.target.closest('input,textarea,[contenteditable]')) return;
    event.preventDefault(); event.shiftKey ? restoreHistory(redo,undo) : restoreHistory(undo,redo);
  });
  for (const [id,key] of Object.entries(fields)) {
    const input = $(id);
    input?.addEventListener('input', () => {
      const value = input.type === 'checkbox' ? input.checked : Math.min(Number(input.max),Math.max(Number(input.min),Number(input.value) || 0));
      state.edit[key] = value;
      paintStudio(); syncSound(true);
    });
    input?.addEventListener('change', () => { dirty(); });
  }
  $('mcStudioRemoveSound')?.addEventListener('click', () => { state.edit.sound_id='';soundPlayer.pause();dirty();paintStudio(); });
  $('mcStudioSoundFile')?.addEventListener('change', uploadSound);
  $('mcStudioSoundList')?.addEventListener('click', event => {
    const button = event.target.closest('[data-sound]');
    if (!button) return;
    if(state.composition?.enabled){
      const row=sounds.find(item=>item.id===button.dataset.sound);if(row)document.dispatchEvent(new CustomEvent('cadu:composition-sound',{detail:row}));return;
    }
    state.edit.sound_id = button.dataset.sound; state.panelTab='audio';
    document.querySelectorAll('#mcStudioSoundList audio').forEach(audio => audio.pause());
    dirty(); repaint(); syncSound(true);
  });
  $('mcStudioSoundList')?.addEventListener('play', event => {
    $('mcSwapVideo')?.pause(); soundPlayer.pause();
    document.querySelectorAll('#mcStudioSoundList audio').forEach(audio => {if(audio !== event.target) audio.pause();});
  }, true);
  $('mcStudioExportFormat')?.addEventListener('change',event=>{if(event.target.value&&event.target.value!=='__progress'){const format=event.target.value;clearDownload();event.target.value=format;exportEdit();}});
  $('mcStudioPlay')?.addEventListener('click', () => {
    const video=$('mcSwapVideo'); if (!video?.src) return;
    if (video.paused) {
      state.previewMode='clip'; repaint();
      if(state.composition?.enabled){video.play().catch(()=>status("Não foi possível reproduzir."));return;}
      const end=state.edit.end || video.duration;
      if (video.currentTime < state.edit.start || video.currentTime >= end) video.currentTime=state.edit.start;
      video.play().catch(() => status('Não foi possível reproduzir este clipe.'));
    } else video.pause();
  });
  $('mcStudioSeek')?.addEventListener('input', event => {
    const video=$('mcSwapVideo'); if(video && Number.isFinite(video.duration)) {video.currentTime=Number(event.target.value);syncSound(true);}
  });
  const video=$('mcSwapVideo');
  for (const name of ['loadedmetadata','durationchange','timeupdate','seeked','pause','play','ended']) video?.addEventListener(name, () => {
    if(name==='play') { document.querySelectorAll('#mcStudioSoundList audio').forEach(a=>a.pause()); cancelAnimationFrame(frame); tick(); }
    if(name==='pause'||name==='ended') {cancelAnimationFrame(frame);soundPlayer.pause();}
    if(name==='seeked') { syncSound(true);paintVisual(); }
    if(name==='play' && video.currentTime<state.edit.start) video.currentTime=state.edit.start;
    if(name==='loadedmetadata') { video.loop=false;video.volume=state.edit.original_volume;video.playbackRate=state.edit.speed||1;paintVisual(); }
    paintPlayback();
  });
  document.addEventListener('cadu:studio-paint', paintStudio);
  window.addEventListener('pagehide', () => {soundPlayer.pause();cancelAnimationFrame(frame);clearTimeout(pollTimer);});
}

export async function resetStudio() {
  clearDownload();
  if (!state.activeClipId) document.dispatchEvent(new Event("cadu:clip-cleared"));
  brand=state.clientId; sounds=[];state.sounds=[]; undo=[];redo=[];baseline=snapshot();updateHistory();
  soundPlayer.pause();soundPlayer.removeAttribute('src');soundPlayer.load();
  cancelAnimationFrame(frame);clearTimeout(pollTimer); exporting=false;
  if($('mcStudioExportStatus')) $('mcStudioExportStatus').hidden=true;
  await Promise.allSettled([loadSounds(),resetJobCenter()]);
  const pending=sessionStorage.getItem(`cadu-export:${brand}`);
  if(pending) {exporting=true;beginDownload(pending,brand);pollExport(pending,brand);}
}
async function loadSounds() {
  if(!brand) {paintStudio();return;}
  const client=brand, request=++soundRequest;
  try {
    const data=await get(`${base}/sounds?client_id=${encodeURIComponent(client)}`);
    if(client!==brand || request!==soundRequest)return;
    sounds=data.items || [];state.sounds=sounds; $('mcStudioSoundStatus').textContent='';paintStudio();
  } catch(error) {if(client===brand)$('mcStudioSoundStatus').textContent=error.message;}
}
async function uploadSound(event) {
  const file=event.target.files?.[0]; event.target.value=''; if(!file)return;
  if(!brand) {$('mcStudioSoundStatus').textContent='Escolha uma marca.';return;}
  if(file.size>25*1024*1024) {$('mcStudioSoundStatus').textContent='Envie um áudio de até 25 MB.';return;}
  const client=brand, form=new FormData();form.append('client_id',client);form.append('file',file);form.append('category',$('mcStudioSoundCategory').value);
  $('mcStudioSoundFile').disabled=true; $('mcStudioSoundStatus').textContent='Enviando e preparando áudio…';
  try {
    const response=await fetch(`${base}/sounds`,{method:'POST',credentials:'same-origin',headers:{'X-Trocr-CSRF-Token':csrf()},body:form});
    const data=await response.json();if(!response.ok || data.success===false)throw new Error(data.error || 'Falha no envio.');
    if(client===brand)await loadSounds();
  }catch(error){if(client===brand)$('mcStudioSoundStatus').textContent=error.message;}
  finally{$('mcStudioSoundFile').disabled=false;}
}

let soundListKey='';
export function paintStudio() {
  if(!$('mcStudioSounds'))return;
  paintComposition();
  paintTextLayers();
  paintSeedancePanel();
  paintAgentPanel();
  state.edit ||= defaultEdit();
  $('mcStudioSounds').hidden=state.libTab!=='sound';
  const rows=sounds.filter(row => row.name.toLocaleLowerCase().includes((state.search||'').toLocaleLowerCase()));
  const key=JSON.stringify([brand,rows,state.edit.sound_id]);
  if(key!==soundListKey) {
    soundListKey=key;
  $('mcStudioSoundList').innerHTML=rows.map(row=>`<article class="mc-studio-sound"><strong>${escapeHtml(row.name)}</strong><small>${({music:'Música',effect:'Efeito',ambient:'Ambiente',voice:'Locução'})[row.category] || 'Áudio'} · ${row.duration < 1 ? `${Math.round(row.duration*1000)} ms` : `${row.duration.toFixed(1)} s`}</small>${row.license ? `<small>${escapeHtml(row.author)} · ${escapeHtml(row.license)} · <a href="${escapeHtml(row.source_url)}" target="_blank" rel="noopener">Origem e licença</a></small>` : ""}<audio controls preload="none" src="${escapeHtml(row.url)}"></audio><button type="button" class="mc-cadu-video-ghost" data-sound="${escapeHtml(row.id)}">${row.id===state.edit.sound_id?'Trilha selecionada':'Adicionar à edição'}</button></article>`).join('') || '<p class="mc-cadu-video-hint">Nenhum som encontrado. Envie música, efeito, ambiente ou locução.</p>';
  }
  for(const [id,key] of Object.entries(fields)) if($(id)&&document.activeElement!==$(id)) {
    if($(id).type==='checkbox')$(id).checked=state.edit[key];else $(id).value=state.edit[key];
  }
  $('mcStudioOriginalValue').value=`${Math.round(state.edit.original_volume*100)}%`;
  $('mcStudioVolumeValue').value=`${Math.round(state.edit.sound_volume*100)}%`;
  if($('mcStudioSpeedValue')) $('mcStudioSpeedValue').value=`${Number(state.edit.speed||1).toFixed(2).replace(/\.00$/,'')}×`;
  const selected=sounds.find(row=>row.id===state.edit.sound_id);
  const waveform=$('mcStudioWaveform');
  if(waveform && waveform.dataset.sound!==String(selected?.id||'')){
    waveform.dataset.sound=selected?.id||'';
    const values=selected?.waveform || [];
    waveform.innerHTML=values.map((v,i)=>`<path d="M${i*600/values.length} ${14-Math.min(1,Math.max(0,v))*13}v${Math.min(1,Math.max(0,v))*26}" stroke="currentColor" stroke-width="2"/>`).join('');
  }
  const category={music:'Música',effect:'Efeitos',ambient:'Ambiente',voice:'Locução'}[selected?.category] || 'Áudio';
  $('mcStudioTrackLabel').textContent=selected?.name || (state.edit.sound_id ? 'Áudio indisponível' : 'Nenhuma trilha adicional');
  if($('mcStudioAudioTrackName')) $('mcStudioAudioTrackName').textContent=category;
  const audioParts=[];
  if(state.audio.enabled===false) audioParts.push('Sem áudio');
  else {
    if(state.audio.ambience) audioParts.push('Ambiente');
    if(state.audio.narration_mode==='guided') audioParts.push('Narração nativa');
    if(state.audio.narration_mode==='voiceover') audioParts.push('Locução exata');
    if(state.audio.music_enabled) audioParts.push('Música');
  }
  $('mcStudioGenerationAudio').textContent=audioParts.join(' + ') || 'Sem áudio';
  $('mcStudioRemoveSound').disabled=!state.edit.sound_id;
  $('mcStudioExportFormat').disabled=(state.composition?.enabled?!state.composition.items.length:!state.activeClipId) || exporting || $('mcStudioExportFormat').dataset.busy==='1';
  if(state.libTab==='sound')$('mcVideoLibHint').textContent='Sons enviados e 100 efeitos públicos CC0 do Kenney.';
  if(state.previewMode!=='clip')$('mcSwapVideo')?.pause();
  paintVisual();
  paintPlayback();
}
function paintVisual() {
  if(state.composition?.enabled){paintCompositionCanvas();return;}
  paintTextPreview();
  const video=$('mcSwapVideo');if(!video)return;
  video.style.filter=state.edit.grayscale?'grayscale(1)':'';
  video.style.transform=state.edit.flip?'scaleX(-1)':'';
  video.playbackRate=state.edit.speed||1;
  video.volume=state.edit.original_volume;
  const start=state.edit.start, end=Math.min(state.edit.end || video.duration,video.duration);
  const speed=state.edit.speed||1;
  const length=(end-start)/speed, elapsed=Math.max(0,video.currentTime-start)/speed;
  const fi=Math.min(state.edit.video_fade_in,length), fo=Math.min(state.edit.video_fade_out,length);
  const opacity=(fi?Math.min(1,elapsed/fi):1)*(fo?Math.min(1,Math.max(0,end-video.currentTime)/speed/fo):1);
  video.style.opacity=Number.isFinite(opacity)?opacity:1;
}
function paintPlayback() {
  paintTimelinePosition();
  const video=$('mcSwapVideo'), ready=video && Number.isFinite(video.duration) && video.duration>0 && Boolean(video.getAttribute('src'));
  $('mcStudioPlay').disabled=!ready;$('mcStudioSeek').disabled=!ready;
  $('mcStudioPlay').textContent=video?.paused?'Reproduzir clipe':'Pausar';
  if(ready){$('mcStudioSeek').max=video.duration;$('mcStudioSeek').value=video.currentTime;$('mcStudioTime').value=`${time(video.currentTime)} / ${time(video.duration)}`;}
  else $('mcStudioTime').value='0:00 / 0:00';
}
function tick(){paintVisual();syncSound();paintTimelinePosition();if(!$('mcSwapVideo')?.paused)frame=requestAnimationFrame(tick);}
function syncSound(force=false){
  const video=$('mcSwapVideo');if(!video)return;
  if(syncCompositionPlayback()){soundPlayer.pause();return;}
  video.volume=state.edit.original_volume;
  const end=Math.min(state.edit.end || video.duration,video.duration), start=state.edit.start;
  if(!video.paused && video.currentTime>=end){video.pause();video.currentTime=start;return;}
  const row=sounds.find(row=>row.id===state.edit.sound_id);
  if(!row || video.paused || video.hidden){soundPlayer.pause();return;}
  if(soundPlayer.getAttribute('src')!==row.url){soundPlayer.src=row.url;soundPlayer.preload='metadata';force=true;}
  const elapsed=Math.max(0,video.currentTime-start)/(state.edit.speed||1), length=(end-start)/(state.edit.speed||1);
  let at=state.edit.sound_offset+elapsed;
  if(state.edit.loop) at%=row.duration;
  if(at>=row.duration){soundPlayer.pause();return;}
  const fi=Math.min(state.edit.fade_in,length), fo=Math.min(state.edit.fade_out,length);
  const fadeIn=fi?Math.min(1,elapsed/fi):1;
  const fadeOut=fo?Math.min(1,Math.max(0,length-elapsed)/fo):1;
  soundPlayer.volume=Math.min(1,state.edit.sound_volume*fadeIn*fadeOut);
  if(force||Math.abs(soundPlayer.currentTime-at)>.2)soundPlayer.currentTime=at;
  if(soundPlayer.paused)soundPlayer.play().catch(()=>{});
}
function status(text, url=''){
  const node=$('mcStudioExportStatus');node.hidden=false;node.textContent=text;
  if(url){const a=document.createElement('a');a.href=url;a.textContent='Baixar MP4';node.appendChild(a);}
}
async function exportEdit(){
  if(state.composition?.enabled){await exportComposition(false);return;}
  if(exporting || !state.activeClipId)return;
  const video=$('mcSwapVideo'), end=state.edit.end || video?.duration;
  if(!Number.isFinite(end)||end<=state.edit.start){status('Defina um intervalo de corte válido.');return;}
  const client=brand, id=newId().replaceAll('-',''),delivery=deliveryOptions();
  beginDownload(id,client,delivery.format);
  exporting=true;paintStudio();status('Preparando exportação com corte e mixagem…');

  sessionStorage.setItem(`cadu-export:${client}`,id);
  try{
    await post(`${base}/exports`,{client_id:client,clip_id:state.activeClipId,edit:{...state.edit,output_ratio:state.aspectRatio},request_id:id,delivery});
    updateProcessing({job_id:`export:${id}`,kind:"export",status:"queued",background_supported:true,message:"Edição salva. Aguardando processamento."});
    if(client===brand)pollExport(id,client);
  }catch(error){updateDownload({id,status:'failed'});sessionStorage.removeItem(`cadu-export:${client}`);if(client===brand){exporting=false;paintStudio();status(error.message);updateProcessing({job_id:`export:${id}`,status:'failed',error:error.message});}}
}
async function pollExport(id,client){
  if(client!==brand)return;
  try{
    const result=await get(`${base}/exports/${id}?client_id=${encodeURIComponent(client)}`);
    if(client!==brand)return;
    updateDownload(result);
    updateProcessing({...result,job_id:`export:${id}`,kind:"export",auto_download:true,stage:result.status,message:result.status==="ready"?"Exportação pronta.":"Renderizando sua edição…",version:result.status==="ready"?{video_url:`${base}/exports/${id}/content?client_id=${encodeURIComponent(client)}&format=mp4&inline=1`}:undefined});
    if(result.status==='ready'||result.status==='failed'){
      exporting=false;sessionStorage.removeItem(`cadu-export:${client}`);paintStudio();
      upsertWorkspaceSpend({id:`edit:${id}`,kind:'edit',label:'Exportação da edição',amount_tokens:0,amount_brl:0,amount_usd:0,status:result.status==='ready'?'confirmed':'failed',created_at:new Date().toISOString()});
      dirty();
      if(result.status==='ready')downloadExport(result,client);
      status(result.status==='ready'?`Download iniciado: ${result.filename||'criativo'}.`:result.error);return;
    }
    status('Exportando corte e mixagem. Você pode continuar editando.');
  }catch(error){if(client===brand)status(`Não foi possível acompanhar a exportação: ${error.message}`);}
  if(client===brand)pollTimer=setTimeout(()=>pollExport(id,client),4000);
}
