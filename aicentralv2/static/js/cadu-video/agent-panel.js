import { post } from './api.js';
import { syncAudioMode, workspaceSpendTotals } from './state.js';

const $ = id => document.getElementById(id);
let state, changed, repaint, plan = null, running = false;

export function bindAgentPanel(project, markDirty, paintAll) {
  state = project;
  changed = markDirty;
  repaint = paintAll;
  $('mcStudioAgentForm')?.addEventListener('submit', requestPlan);
  $('mcStudioAgentApply')?.addEventListener('click', applyPlan);
  document.querySelectorAll('[data-agent-prompt]').forEach(button => button.addEventListener('click', () => {
    $('mcStudioAgentPrompt').value = button.dataset.agentPrompt || '';
    $('mcStudioAgentPrompt').focus();
  }));
}

async function requestPlan(event) {
  event.preventDefault();
  const message = $('mcStudioAgentPrompt')?.value.trim();
  if (!message || running || !state.clientId) return;
  running = true;
  plan = null;
  paintAgentPanel();
  try {
    const selected = state.scenes.find(item => item.id === state.selectedSceneId);
    const clip = state.clips.find(item => item.id === state.activeClipId || item.job_id === state.activeClipId);
    plan = await post('/parametros/api/format-lab/studio/agent/plan', {
      client_id: state.clientId,
      message,
      context: {
        generation_mode: state.generationMode,
        duration: state.duration,
        audio_mode: state.audio.mode,
        selected_scene: selected ? {id:selected.id, name:selected.name, aspect_ratio:selected.aspect_ratio} : {},
        scene_count: state.scenes.length,
        has_clip: Boolean(state.activeClipId),
        clip: clip ? {id:clip.id, name:clip.name, duration:clip.duration, has_audio:clip.has_audio} : {},
        edit: {...state.edit},
      },
    });
  } catch (error) {
    plan = {error:error.message};
  } finally {
    running = false;
    paintAgentPanel();
  }
}

function applyPlan() {
  if (!plan?.patch) return;
  if (plan.patch.edit && !state.activeClipId) return;
  const patch = plan.patch;
  if (patch.generation_mode) state.generationMode = patch.generation_mode;
  if (patch.duration) state.duration = patch.duration;
  if (patch.aspect_ratio) state.aspectRatio = patch.aspect_ratio;
  if (patch.quality) state.quality = patch.quality;
  if (Object.prototype.hasOwnProperty.call(patch, 'seed')) state.seed = patch.seed;
  if (patch.audio) syncAudioMode(Object.assign(state.audio, patch.audio));
  if (patch.motion) Object.assign(state.motion, patch.motion);
  if (patch.edit) Object.assign(state.edit, patch.edit);
  plan = {...plan, applied:true};
  changed();
  repaint();
  paintAgentPanel();
}

export function paintAgentPanel() {
  const status = $('mcStudioAgentStatus');
  const result = $('mcStudioAgentPlan');
  const apply = $('mcStudioAgentApply');
  const submit = $('mcStudioAgentSubmit');
  if (!status || !result) return;
  paintWorkspaceSpend();
  const clip = state?.clips?.find(item => item.id === state.activeClipId || item.job_id === state.activeClipId);
  if ($('mcStudioAgentTarget')) $('mcStudioAgentTarget').textContent = clip
    ? `Editando agora · ${clip.name || 'Clipe'} · ${formatDuration(clip.duration)}`
    : 'Projeto de geração · nenhum clipe aberto';
  submit.disabled = running || !state?.clientId;
  status.textContent = running
    ? (state.activeClipId ? 'Analisando o clipe aberto e a timeline…' : 'Organizando o pedido…')
    : plan?.error || (plan?.applied
      ? (plan.patch?.edit ? 'Edição aplicada à prévia. Exporte quando estiver satisfeito.' : 'Ajustes aplicados. Revise o projeto antes de gerar.')
      : 'O agente prepara mudanças para sua revisão.');
  status.classList.toggle('is-error', Boolean(plan?.error));
  result.replaceChildren();
  result.hidden = !plan?.patch;
  apply.hidden = !plan?.patch;
  const needsClip = Boolean(plan?.patch?.edit && !state.activeClipId);
  apply.disabled = Boolean(plan?.applied || needsClip);
  apply.textContent = plan?.applied ? 'Alterações aplicadas' : needsClip ? 'Abra um clipe para aplicar' : plan?.patch?.edit ? 'Aplicar ao clipe' : 'Aplicar ao projeto';
  if (!plan?.patch) return;
  const title = document.createElement('strong');
  title.textContent = plan.summary || 'Plano do agente';
  result.append(title);
  const list = document.createElement('ol');
  (plan.steps || []).forEach(step => {
    const item = document.createElement('li'); item.textContent = step; list.append(item);
  });
  result.append(list);
  const impact = document.createElement('p');
  impact.className = 'mc-studio-agent-impact';
  impact.textContent = plan.patch.edit && !plan.requires_generation
    ? 'Edição local: custo de IA R$ 0,00. A exportação será registrada no workspace.'
    : plan.requires_generation
      ? 'A geração só será contabilizada após você revisar, gerar e o processamento concluir.'
      : 'Nenhuma geração será iniciada ao aplicar este plano.';
  result.append(impact);
  if (plan.warnings?.length) {
    const warnings = document.createElement('div'); warnings.className = 'mc-studio-agent-warnings';
    plan.warnings.forEach(text => { const item=document.createElement('p'); item.textContent=text; warnings.append(item); });
    result.append(warnings);
  }
  const meta = document.createElement('small');
  meta.textContent = plan.skill === 'seedance-2-5-image-to-video'
    ? 'Skill ativa: Seedance 2.5 · imagem para vídeo · 720p'
    : 'Plano validado pelo Studio';
  result.append(meta);
}

function paintWorkspaceSpend() {
  if (!state) return;
  const totals = workspaceSpendTotals();
  if ($('mcStudioSpendConfirmed')) $('mcStudioSpendConfirmed').textContent = money(totals.confirmed_brl);
  if ($('mcStudioSpendPending')) $('mcStudioSpendPending').textContent = money(totals.pending_brl);
  if ($('mcStudioSpendMeta')) $('mcStudioSpendMeta').textContent = totals.confirmed_count
    ? `${totals.confirmed_count} ${totals.confirmed_count === 1 ? 'operação concluída' : 'operações concluídas'} neste workspace.`
    : 'Nenhuma operação contabilizada.';
  const list = $('mcStudioSpendEvents');
  if (!list) return;
  list.replaceChildren();
  totals.events.slice().reverse().slice(0, 12).forEach(event => {
    const item = document.createElement('li');
    const label = document.createElement('span'); label.textContent = event.label;
    const value = document.createElement('strong'); value.textContent = event.status === 'failed' ? 'Falhou' : money(event.amount_brl);
    item.append(label, value);
    item.dataset.status = event.status;
    list.append(item);
  });
  if (!list.childElementCount) {
    const empty = document.createElement('li'); empty.textContent = 'O histórico aparecerá após gerar ou exportar.'; list.append(empty);
  }
}

function money(value) {
  return Number(value || 0).toLocaleString('pt-BR', {style:'currency', currency:'BRL'});
}

function formatDuration(value) {
  const seconds = Number(value || 0);
  return seconds > 0 ? `${seconds.toFixed(seconds % 1 ? 1 : 0)}s` : 'duração indisponível';
}
