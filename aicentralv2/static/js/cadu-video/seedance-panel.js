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
    for(const [name,values] of [['mcVideoDuration',data.durations.map(String)],['mcVideoAudio',data.audio_modes],['mcVideoMotion',data.motion_presets]]){
      document.querySelectorAll(`input[name="${name}"]`).forEach(input=>{input.disabled=!values.includes(input.value);input.closest('label').hidden=input.disabled;});
    }
    [...$('mcVideoAspect').options].forEach(option=>{option.disabled=!data.ratios.includes(option.value);});
    paintSeedancePanel();
  }catch(error){$('mcStudioModel').textContent='Modelo não consultado';$('mcStudioCapabilities').textContent=error.message;$('mcStudioCapabilitiesRetry').hidden=false;}
}
export function paintSeedancePanel(){
  if(!state||!$('mcStudioGenerationSummary'))return;
  if(document.activeElement!==$('mcStudioSeed'))$('mcStudioSeed').value=state.seed??'';
  const resolution=capabilities?.qualities?.[state.quality];
  $('mcStudioGenerationSummary').textContent=[`${state.duration}s`,state.aspectRatio,resolution,state.audio.mode==='silence'?'Sem áudio':'Com áudio'].filter(Boolean).join(' · ');
}
