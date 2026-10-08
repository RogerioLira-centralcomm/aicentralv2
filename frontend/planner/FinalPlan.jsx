import React, {useEffect, useState} from 'react';
import {CaduButton} from '../cadu-design-system/components/CaduButton.jsx';
import {CaduBadge} from '../cadu-design-system/components/CaduBadge.jsx';
import {CaduEmptyState} from '../cadu-design-system/components/CaduEmptyState.jsx';
import {CaduTextAreaField} from '../cadu-design-system/components/CaduField.jsx';
import {Icon} from '../cadu-design-system/components/Icon.jsx';
import {IllustratedWait} from './Illustration.jsx';
import {PlannerPanel} from './PlannerUi.jsx';

const money = value => Number(value) ? Number(value).toLocaleString('pt-BR', {style: 'currency', currency: 'BRL', maximumFractionDigits: 0}) : 'a definir';
const pct = value => Number(value) ? `${Number(value).toLocaleString('pt-BR', {maximumFractionDigits: 1})}%` : 'a definir';
const day = value => value ? new Date(value).toLocaleDateString('pt-BR', {day: '2-digit', month: 'short', year: 'numeric'}).replace('.', '') : '';

/** Inline markdown subset (**bold**, [link](https://…)) as React nodes: no raw HTML ever reaches the page. */
function inline(text) {
  const parts = [];
  const pattern = /\*\*([^*]+)\*\*|\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g;
  let last = 0;
  for (const match of String(text).matchAll(pattern)) {
    if (match.index > last) parts.push(text.slice(last, match.index));
    parts.push(match[1] ? <strong key={match.index}>{match[1]}</strong>
      : <a key={match.index} href={match[3]} target="_blank" rel="noreferrer noopener">{match[2]}</a>);
    last = match.index + match[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

export function MarkdownText({text}) {
  const blocks = String(text || '').split(/\n{2,}/).map(block => block.trim()).filter(Boolean);
  return <>{blocks.map((block, index) => {
    const lines = block.split('\n');
    if (lines.every(line => /^\s*[-*]\s+/.test(line))) {
      return <ul key={index}>{lines.map((line, i) => <li key={i}>{inline(line.replace(/^\s*[-*]\s+/, ''))}</li>)}</ul>;
    }
    return <p key={index}>{lines.map((line, i) => <React.Fragment key={i}>{i > 0 && <br/>}{inline(line)}</React.Fragment>)}</p>;
  })}</>;
}

function MixTable({rows}) {
  if (!rows?.length) return null;
  return <div className="final-plan__table"><table>
    <thead><tr><th>Canal</th><th>%</th><th>R$</th><th>Papel</th><th>Justificativa</th></tr></thead>
    <tbody>{rows.map(row => <tr key={row.canal}><td><strong>{row.canal}</strong></td><td>{pct(row.percentual)}</td>
      <td>{money(row.investimento)}</td><td>{row.papel}</td><td>{row.justificativa}</td></tr>)}</tbody>
  </table></div>;
}

/** The document itself: summary sheet on top, then the body. Shared by the Planner and the public link. */
export function FinalPlanDocument({document, editable = false, edited = [], busyKey = '', onSave}) {
  const [editing, setEditing] = useState('');
  const sections = (document?.sections || []).filter(section => editable || section.body || section.rows?.length);
  return <div className="final-plan">
    {sections.map(section => <section key={section.key} className={`final-plan__section${section.key === 'resumo' ? ' is-summary' : ''}`}>
      <header>
        <h3>{section.title}</h3>
        {edited.includes(section.key) && <CaduBadge tone="neutral">Editada por você</CaduBadge>}
        {editable && editing !== section.key && <CaduButton variant="tertiary" size="sm" onClick={() => setEditing(section.key)}>Editar</CaduButton>}
      </header>
      {section.key === 'mix' && <MixTable rows={section.rows}/>}
      {editing === section.key
        ? <form onSubmit={async event => {
          event.preventDefault();
          const body = new FormData(event.currentTarget).get('body');
          if (await onSave(section.key, body)) setEditing('');
        }}>
          <CaduTextAreaField label={`Texto de ${section.title}`} name="body" rows={8} maxLength={12000} defaultValue={section.body || ''}/>
          <p className="planner-muted">Use **negrito** e linhas começando com “- ” para listas. Salvar cria uma versão nova.</p>
          <footer className="final-plan__actions">
            <CaduButton variant="secondary" size="sm" onClick={() => setEditing('')}>Cancelar</CaduButton>
            <CaduButton type="submit" size="sm" loading={busyKey === section.key}>Salvar seção</CaduButton>
          </footer>
        </form>
        : section.body ? <MarkdownText text={section.body}/> : (editable && section.key !== 'mix' && <p className="planner-muted">Seção vazia.</p>)}
    </section>)}
    <p className="planner-muted final-plan__note">{document?.note || 'Valores sujeitos a cotação.'}</p>
  </div>;
}

/** 'Plano final' block in the plan page: generate with a credit estimate, edit by section, share, add to project. */
export function FinalPlanPanel({boot, request, plan, notify}) {
  const [state, setState] = useState(null);
  const [busy, setBusy] = useState('');
  const planId = plan.id;
  const updatedAt = plan.updated_at;

  useEffect(() => {
    let current = true;
    request(`/plans/${planId}/final-plan`).then(data => { if (current) setState(data.final_plan || null); }).catch(() => {});
    return () => { current = false; };
  }, [request, planId, updatedAt]);

  const run = async (key, action) => {
    setBusy(key);
    try { return await action(); } catch (error) { notify({tone: 'error', message: error.message}); return false; } finally { setBusy(''); }
  };
  const generate = () => run('generate', async () => {
    const estimate = await request(`/plans/${planId}/final-plan/estimate`).catch(() => ({}));
    const tokens = Number(estimate.estimated_tokens || 0);
    if (!window.confirm(`O Cadu escreve o plano final a partir dos dados do plano${tokens ? ` (até cerca de ${tokens.toLocaleString('pt-BR')} tokens)` : ''}, usando créditos. Você paga pelo consumo real. Continuar?`)) return;
    let overwrite = false;
    const edited = state?.edited_sections || [];
    if (edited.length) overwrite = window.confirm(`Você editou ${edited.length} ${edited.length === 1 ? 'seção' : 'seções'}. OK para substituir pelo texto novo do Cadu; Cancelar para manter as suas edições.`);
    const data = await request(`/plans/${planId}/final-plan`, {method: 'POST', body: JSON.stringify({overwrite_edited: overwrite})});
    setState(data.final_plan);
    notify({message: `Plano final gerado (versão ${data.final_plan?.version}).`});
  });
  const saveSection = (section, body) => run(section, async () => {
    const data = await request(`/plans/${planId}/final-plan/sections/${section}`, {method: 'PUT', body: JSON.stringify({body, expected_version: state?.version})});
    setState(data.final_plan);
    notify({message: 'Seção salva como nova versão.'});
    return true;
  });
  const publicUrl = token => new URL(`/planos/public/final/${token}`, boot.urls.home).href;
  const toggleShare = enabled => run('share', async () => {
    const data = await request(`/plans/${planId}/final-plan/share`, {method: 'POST', body: JSON.stringify({enabled})});
    setState(data.final_plan);
    if (enabled && data.final_plan?.share_token) {
      await navigator.clipboard?.writeText(publicUrl(data.final_plan.share_token));
      notify({message: 'Link público ativado e copiado. Quem tiver o link vê a versão atual, sem login.'});
    } else notify({message: 'Link público desativado.'});
  });
  const copyLink = () => run('copy', async () => {
    await navigator.clipboard?.writeText(publicUrl(state.share_token));
    notify({message: 'Link copiado.'});
  });
  const addToProject = () => run('project', async () => {
    if (!window.confirm('Adicionar a versão atual do plano final ao conhecimento do projeto? A indexação usa créditos proporcionais ao texto.')) return;
    const data = await request(`/plans/${planId}/final-plan/project`, {method: 'POST', body: JSON.stringify({})});
    setState(data.final_plan);
    notify({message: 'Plano final adicionado ao projeto.'});
  });

  if (state && state.available === false) return null;
  const exists = Boolean(state?.exists);
  return <PlannerPanel className="planner-block final-plan-panel" title="Plano final"
    description="O documento do plano: folha-resumo e desdobramento completo, escrito pelo Cadu a partir do que está no plano."
    actions={exists ? <span className="planner-muted">Versão {state.version} · {day(state.created_at)}</span> : null}>
    {busy === 'generate' && <IllustratedWait slot="plan-building" title="O Cadu está escrevendo o plano final"
      description="Lendo o plano, montando a tese e conferindo cada número com o que você registrou."/>}
    {exists && state.stale && <div className="final-plan__stale" role="status"><Icon name="alert" size={16}/>
      O plano mudou depois desta versão. Gere de novo para atualizar o documento.</div>}
    <div className="final-plan__toolbar">
      <CaduButton loading={busy === 'generate'} onClick={generate}>{exists ? 'Gerar nova versão' : 'Gerar plano final'}</CaduButton>
      {exists && (state.share_enabled
        ? <><CaduButton variant="secondary" loading={busy === 'copy'} onClick={copyLink}><Icon name="link" size={16}/>Copiar link</CaduButton>
          <CaduButton variant="tertiary" loading={busy === 'share'} onClick={() => toggleShare(false)}>Desativar link</CaduButton></>
        : <CaduButton variant="secondary" loading={busy === 'share'} onClick={() => toggleShare(true)}><Icon name="link" size={16}/>Ativar link público</CaduButton>)}
      {exists && <CaduButton variant="secondary" loading={busy === 'project'} disabled={!String(plan.project_ref || '').startsWith('ci:')}
        title={String(plan.project_ref || '').startsWith('ci:') ? undefined : 'Vincule o plano a um projeto do Cadu'} onClick={addToProject}>
        {state.project_source_id ? 'Adicionar de novo ao projeto' : 'Adicionar ao projeto'}</CaduButton>}
    </div>
    {exists
      ? <FinalPlanDocument document={state.document} editable edited={state.edited_sections || []} busyKey={busy} onSave={saveSection}/>
      : <p className="planner-muted">Ainda não há plano final. Quanto mais completo o plano (briefing, canais, verba), melhor o documento; o que faltar vira “Para alinharmos”, nunca é inventado.</p>}
  </PlannerPanel>;
}

/** Open link: the current version, read-only, without internal data. */
export function PublicFinalPlan({document}) {
  if (!document) return <CaduEmptyState title="Plano indisponível" description="O link pode ter sido desativado."/>;
  return <article className="planner-public planner-public--v2">
    <header className="planner-public__brand"><img src="/static/images/cadu/products/planner-icon.png" alt="" width="24" height="24"/><span>Plano final compartilhado pelo Cadu Planner</span>
      {document.updated_at && <small>Atualizado em {day(document.updated_at)}</small>}</header>
    <div className="pp-head"><h1>{document.title}</h1>{document.advertiser_name && <p>{document.advertiser_name}</p>}</div>
    <FinalPlanDocument document={document}/>
  </article>;
}
