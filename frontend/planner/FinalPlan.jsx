import React, {useEffect, useState} from 'react';
import {CaduButton} from '../cadu-design-system/components/CaduButton.jsx';
import {CaduBadge} from '../cadu-design-system/components/CaduBadge.jsx';
import {CaduEmptyState} from '../cadu-design-system/components/CaduEmptyState.jsx';
import {CaduTextAreaField} from '../cadu-design-system/components/CaduField.jsx';
import {Icon} from '../cadu-design-system/components/Icon.jsx';
import {Illustration} from './Illustration.jsx';
import {PlannerHeader} from './PlannerHeader.jsx';
import {upperFirst} from './api.js';
import {PlannerPanel} from './PlannerUi.jsx';
import {ShareControl} from './ShareControl.jsx';
import {useConfirm} from './useConfirm.jsx';

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
export function FinalPlanDocument({document, editable = false, edited = [], busyKey = '', onSave, anchors = false}) {
  const [editing, setEditing] = useState('');
  const sections = (document?.sections || []).filter(section => editable || section.body || section.rows?.length);
  return <div className="final-plan">
    {sections.map(section => <section key={section.key} id={anchors ? `final-${section.key}` : undefined} className={`final-plan__section${section.key === 'resumo' ? ' is-summary' : ''}`}>
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

export const finalPlanUrl = (urls, planId) => `${urls.plans}/${encodeURIComponent(planId)}/final`;

const BUILD_STEPS = [
  'Lendo o plano e o briefing',
  'Conferindo verba, canais e audiências',
  'Escrevendo a folha-resumo',
  'Montando o desdobramento completo',
  'Validando cada número com o plano',
];

/** Full-screen state while the Cadu writes the final plan: the only thing on screen until it is done. */
export function FinalPlanBuilding() {
  const [step, setStep] = useState(0);
  useEffect(() => {
    const timer = window.setInterval(() => setStep(index => Math.min(index + 1, BUILD_STEPS.length - 1)), 6000);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { window.clearInterval(timer); document.body.style.overflow = overflow; };
  }, []);
  return <div className="final-building" role="status" aria-live="polite">
    <div className="final-building__card">
      <Illustration slot="plan-building" busy className="final-building__art"/>
      <h1>O Cadu está montando o plano final</h1>
      <p>Ele junta o que você definiu no plano, confere cada número e escreve o documento. Mantenha esta página aberta.</p>
      <ol className="final-building__steps">{BUILD_STEPS.map((label, index) =>
        <li key={label} className={index < step ? 'is-done' : index === step ? 'is-active' : ''} aria-current={index === step ? 'step' : undefined}>
          <span aria-hidden="true">{index < step ? <Icon name="check" size={12}/> : null}</span>{label}</li>)}</ol>
      <div className="final-building__bar" aria-hidden="true"><i/></div>
    </div>
  </div>;
}

/** Everything the final plan can do, shared by the compact block in the plan and by the page itself. */
export function useFinalPlan({boot, request, plan, notify}) {
  const [state, setState] = useState(null);
  const [busy, setBusy] = useState('');
  const [confirm, confirmDialog] = useConfirm();
  const planId = plan.id;
  const updatedAt = plan.updated_at;

  useEffect(() => {
    let current = true;
    request(`/plans/${planId}/final-plan`).then(data => { if (current) setState(data.final_plan || {available: false}); }).catch(() => { if (current) setState({available: false}); });
    return () => { current = false; };
  }, [request, planId, updatedAt]);

  const run = async (key, action) => {
    setBusy(key);
    try { return await action(); } catch (error) { notify({tone: 'error', message: error.message}); return false; } finally { setBusy(''); }
  };
  // Confirm first, then mark busy: the "writing" screen must not show while the person is still deciding.
  const generate = async () => {
    const estimate = await request(`/plans/${planId}/final-plan/estimate`).catch(() => ({}));
    const tokens = Number(estimate.estimated_tokens || 0);
    if (!await confirm({title: 'Gerar o plano final?', confirmLabel: 'Gerar plano final',
      description: `O Cadu escreve o plano final a partir dos dados do plano${tokens ? ` (até cerca de ${tokens.toLocaleString('pt-BR')} tokens)` : ''}, usando créditos. Você paga pelo consumo real.`})) return false;
    let overwrite = false;
    const edited = state?.edited_sections || [];
    if (edited.length) overwrite = await confirm({title: 'Substituir as seções que você editou?', confirmLabel: 'Substituir pelo texto novo', cancelLabel: 'Manter minhas edições',
      description: `Você editou ${edited.length} ${edited.length === 1 ? 'seção' : 'seções'}. Mantendo, o Cadu atualiza só o restante.`});
    return run('generate', async () => {
      const data = await request(`/plans/${planId}/final-plan`, {method: 'POST', body: JSON.stringify({overwrite_edited: overwrite})});
      setState(data.final_plan);
      notify({message: `Plano final gerado (versão ${data.final_plan?.version}).`});
      return true;
    });
  };
  const saveSection = (section, body) => run(section, async () => {
    const data = await request(`/plans/${planId}/final-plan/sections/${section}`, {method: 'PUT', body: JSON.stringify({body, expected_version: state?.version})});
    setState(data.final_plan);
    notify({message: 'Seção salva como nova versão.'});
    return true;
  });
  const publicUrl = token => new URL(`/planos/public/final/${token}`, boot.urls.home).href;
  const toggleShare = (enabled, rotate = false) => run('share', async () => {
    const data = await request(`/plans/${planId}/final-plan/share`, {method: 'POST', body: JSON.stringify({enabled, rotate})});
    setState(data.final_plan);
    notify({message: !enabled ? 'Link público desativado.' : rotate ? 'Novo link criado. O anterior não funciona mais.' : 'Link público ativado.'});
  });
  const addToProject = async () => {
    if (!await confirm({title: 'Adicionar ao projeto?', confirmLabel: 'Adicionar ao projeto',
      description: 'A versão atual do plano final entra no conhecimento do projeto. A indexação usa créditos proporcionais ao texto.'})) return;
    await run('project', async () => {
      const data = await request(`/plans/${planId}/final-plan/project`, {method: 'POST', body: JSON.stringify({})});
      setState(data.final_plan);
      notify({message: 'Plano final adicionado ao projeto.'});
    });
  };
  const canProject = String(plan.project_ref || '').startsWith('ci:');
  return {state, busy, generate, saveSection, toggleShare, addToProject, publicUrl, canProject, confirmDialog,
    exists: Boolean(state?.exists), unavailable: state?.available === false, loading: state === null};
}

const firstSentence = text => {
  const plain = String(text || '').replace(/\*\*/g, '').replace(/\n+/g, ' ').trim();
  return plain.length > 220 ? `${plain.slice(0, 217).trimEnd()}…` : plain;
};

/** Compact block at the end of the plan: where the final plan stands and the way to its own page. */
export function FinalPlanPanel({boot, request, plan, notify}) {
  const fp = useFinalPlan({boot, request, plan, notify});
  const {state, busy, exists} = fp;
  if (fp.unavailable) return null;
  const url = finalPlanUrl(boot.urls, plan.id);
  const thesis = exists ? firstSentence(((state.document?.sections || []).find(section => section.key === 'resumo')?.body || '').replace(/^\*\*Tese\.\*\*\s*/, '')) : '';
  const generate = async () => { if (await fp.generate()) window.location.assign(url); };
  return <PlannerPanel className="planner-block final-plan-panel" title="Plano final"
    description="O documento que fecha o plano: folha-resumo e desdobramento completo, escrito pelo Cadu a partir do que está no plano."
    actions={exists ? <span className="planner-muted">Versão {state.version} · {day(state.created_at)}</span> : null}>
    {busy === 'generate' && <FinalPlanBuilding/>}
    {exists && fp.state.stale && <div className="final-plan__stale" role="status"><Icon name="alert" size={16}/>
      O plano mudou depois desta versão. Gere de novo para atualizar o documento.</div>}
    {thesis && <p className="final-plan-panel__thesis">{thesis}</p>}
    {!exists && <p className="planner-muted">{fp.loading ? 'Carregando…' : 'Ainda não há plano final. Quanto mais completo o plano (briefing, canais, verba), melhor o documento; o que faltar vira “Para alinharmos”, nunca é inventado.'}</p>}
    <div className="final-plan__toolbar">
      {exists
        ? <><CaduButton href={url}>Abrir plano final</CaduButton>
          <CaduButton variant="secondary" loading={busy === 'generate'} onClick={generate}>Gerar nova versão</CaduButton></>
        : <CaduButton loading={busy === 'generate'} disabled={fp.loading} onClick={generate}>Gerar plano final</CaduButton>}
    </div>
    {fp.confirmDialog}
  </PlannerPanel>;
}

/** The final plan as its own page: the end of the plan, presented as a document. */
export function PlanFinalPage({boot, request, plan, notify}) {
  const fp = useFinalPlan({boot, request, plan, notify});
  const {state, busy, exists} = fp;
  const planUrl = `${boot.urls.plans}/${encodeURIComponent(plan.id)}`;
  const title = upperFirst(plan.title);
  const sections = exists ? (state.document?.sections || []).filter(section => section.body || section.rows?.length) : [];
  const description = [plan.advertiser_name, plan.campaign_name !== plan.title && plan.campaign_name].filter(Boolean).join(' · ');
  const actions = exists ? <>
    <ShareControl title="Compartilhar o plano final" description="Gere um link aberto para o time ou o cliente. Ele mostra sempre a versão atual do plano final."
      url={state.share_token ? fp.publicUrl(state.share_token) : ''} enabled={state.share_enabled} busy={busy === 'share'} canRotate onToggle={fp.toggleShare}/>
    <CaduButton variant="secondary" loading={busy === 'project'} disabled={!fp.canProject}
      title={fp.canProject ? undefined : 'Vincule o plano a um projeto do Cadu'} onClick={fp.addToProject}>
      {state.project_source_id ? 'Adicionar de novo ao projeto' : 'Adicionar ao projeto'}</CaduButton>
    <CaduButton loading={busy === 'generate'} onClick={fp.generate}>Gerar nova versão</CaduButton>
  </> : null;
  return <>
    {busy === 'generate' && <FinalPlanBuilding/>}
    <PlannerHeader crumbs={[['Planos', boot.urls.plans], [title, planUrl]]} title="Plano final" actions={actions}
      meta={exists ? <CaduBadge tone={state.stale ? 'warning' : 'success'}>{state.stale ? 'Desatualizado' : `Versão ${state.version}`}</CaduBadge> : null}/>
    {fp.unavailable && <CaduEmptyState title="Plano final indisponível" description="Este ambiente ainda não habilitou o plano final."/>}
    {!fp.unavailable && fp.loading && <p className="planner-muted">Carregando…</p>}
    {!fp.unavailable && !fp.loading && !exists && <section className="final-hero">
      <Illustration slot="plan-building"/>
      <h2>O plano final ainda não foi gerado</h2>
      <p>O Cadu reúne direção, canais, verba e audiências em um documento pronto para apresentar. O que faltar vira “Para alinharmos”, nunca é inventado.</p>
      <div className="final-plan__toolbar"><CaduButton onClick={fp.generate}>Gerar plano final</CaduButton><CaduButton variant="secondary" href={planUrl}>Voltar ao plano</CaduButton></div>
    </section>}
    {exists && <div className="final-page">
      <nav className="final-page__index" aria-label="Seções do plano final"><ol>{sections.map(section =>
        <li key={section.key}><a href={`#final-${section.key}`}>{section.title}</a></li>)}</ol></nav>
      <article className="final-page__paper">
        <header className="final-page__head">
          <span className="final-page__eyebrow">Plano final · Versão {state.version} · {day(state.created_at)}</span>
          <h2>{title}</h2>
          {description && <p>{description}</p>}
        </header>
        {state.stale && <div className="final-plan__stale" role="status"><Icon name="alert" size={16}/>
          O plano mudou depois desta versão. Gere de novo para atualizar o documento.</div>}
        <FinalPlanDocument document={state.document} editable edited={state.edited_sections || []} busyKey={busy} onSave={fp.saveSection} anchors/>
      </article>
    </div>}
    {fp.confirmDialog}
  </>;
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
