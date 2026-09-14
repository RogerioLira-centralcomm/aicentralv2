import { get } from './api.js';
const $=id=>document.getElementById(id);
let state, commit, capabilities=null;
export function bindSeedancePanel(project, changed, refresh){
  state=project;commit=changed;
  $('mcStudioSeed')?.addEventListener('input',event=>{
    state.seed=event.target.value===''?null:Math.floor(Math.min(2147483647,Math.max(0,Number(event.target.value)||0)));
    commit();paintSeedancePanel();
  });
  $('mcStudioCapabilitiesRetry')?.addEventListener('click',loadCapabilities);
  loadCapabilities();
}
async function loadCapabilities(){
  $('mcStudioCapabilities').textContent='Consultando parâmetros disponíveis…';
  $('mcStudioCapabilitiesRetry').hidden=true;
  try{
    const data=await get('/parametros/api/format-lab/studio/capabilities');
    if(!data.model||!Array.isArray(data.durations)||!data.qualities)throw new Error('Parâmetros indisponíveis.');
    capabilities=data;
    $('mcStudioModel').textContent=data.model;
    $('mcStudioCapabilities').textContent='Parâmetros conectados à configuração do servidor.';
    for(const [name,values] of [['mcVideoDuration',data.durations.map(String)],['mcVideoMotion',data.motion_presets]]){
      document.querySelectorAll(`input[name="${name}"]`).forEach(input=>{input.disabled=!values.includes(input.value);input.closest('label').hidden=input.disabled;});
    }
    [...$('mcVideoAspect').options].forEach(option=>{option.disabled=!data.ratios.includes(option.value);});
    paintSeedancePanel();
  }catch(error){$('mcStudioModel').textContent='Modelo não consultado';$('mcStudioCapabilities').textContent=error.message;$('mcStudioCapabilitiesRetry').hidden=false;}
}
export function paintSeedancePanel(){
  if(!state||!$('mcStudioGenerationSummary'))return;
  const single=state.generationMode==='single_image';
  const skill=capabilities?.skills?.single_image;
  if($('mcStudioSourceHint')) $('mcStudioSourceHint').textContent=single
    ? 'A imagem é enquadrada no formato escolhido antes de gerar o vídeo em 720p.'
    : 'O storyboard usa duas ou mais cenas para orientar a geração.';
  if($('mcStudioQualityField')) $('mcStudioQualityField').hidden=single;
  if($('mcStudioSeedDetails')) $('mcStudioSeedDetails').hidden=single;
  if(document.activeElement!==$('mcStudioSeed'))$('mcStudioSeed').value=state.seed??'';
  const resolution=single?(skill?.resolution||'720p'):capabilities?.qualities?.[state.quality];
  const ratio=state.aspectRatio;
  const hasAudio=state.audio.enabled!==false&&(state.audio.ambience||state.audio.music_enabled||state.audio.narration_mode==='guided'||state.audio.narration_mode==='voiceover');
  $('mcStudioGenerationSummary').textContent=[single?'Uma imagem':'Storyboard',`${state.duration}s`,ratio,resolution,hasAudio?'Com áudio':'Sem áudio'].filter(Boolean).join(' · ');
}
