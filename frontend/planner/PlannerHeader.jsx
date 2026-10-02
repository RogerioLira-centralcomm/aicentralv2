import React, {createContext, useContext, useState} from 'react';
import {Icon} from '../cadu-design-system/components/Icon.jsx';
import {saveContext} from './api.js';

/** Shell data every page header needs: the context selector and the active plan. */
export const PlannerChrome = createContext({contextNode: null, activePlan: null, urls: {}});

/**
 * Brand and project from the Workspace, kept in the header (as in Reports) so the
 * planning context changes without leaving the page or spending a row of screen.
 */
export function ContextSelector({boot, notify, onChange}) {
  const bar = boot.contextBar;
  const [selection, setSelection] = useState({brand_ref: bar?.brand_ref || '', project_ref: bar?.project_ref || ''});
  const [saving, setSaving] = useState(false);
  if (!bar || (!bar.brands.length && !bar.projects.length)) return null;

  // Projects linked to the chosen brand come first; the rest stay available.
  const linked = selection.brand_ref ? bar.projects.filter(item => item.related_refs.includes(selection.brand_ref)) : [];
  const projects = [...linked, ...bar.projects.filter(item => !linked.includes(item))];

  const change = async (field, value) => {
    const next = {...selection, [field]: value};
    if (field === 'brand_ref' && next.project_ref) {
      const project = bar.projects.find(item => item.ref === next.project_ref);
      if (value && project?.related_refs.length && !project.related_refs.includes(value)) next.project_ref = '';
    }
    setSelection(next);
    setSaving(true);
    try {
      await saveContext(boot.csrf, {brand_ref: next.brand_ref || null, project_ref: next.project_ref || null});
      onChange?.(next);
    } catch (error) {
      notify?.({tone: 'error', message: error.message});
    } finally {
      setSaving(false);
    }
  };

  return <div className="ph-context" aria-label="Contexto do planejamento" aria-busy={saving}>
    {bar.brands.length > 0 && <label className="ph-context__field"><Icon name="brand" size={16}/>
      <span className="planner-sr-only">Marca</span>
      <select value={selection.brand_ref} disabled={saving} onChange={event => change('brand_ref', event.target.value)}>
        <option value="">Todas as marcas</option>
        {bar.brands.map(item => <option key={item.ref} value={item.ref}>{item.name}</option>)}
      </select></label>}
    {bar.projects.length > 0 && <label className="ph-context__field"><Icon name="folder" size={16}/>
      <span className="planner-sr-only">Projeto</span>
      <select value={selection.project_ref} disabled={saving} onChange={event => change('project_ref', event.target.value)}>
        <option value="">Sem projeto</option>
        {projects.map(item => <option key={item.ref} value={item.ref}>{item.name}</option>)}
      </select></label>}
  </div>;
}

/** Shows where catalog choices land; links back to that plan. */
export function ActivePlanChip() {
  const {activePlan, urls} = useContext(PlannerChrome);
  if (!activePlan) return null;
  return <a className="ph-plan" href={`${urls.plans}/${encodeURIComponent(activePlan.id)}`} title="As escolhas desta página entram neste plano">
    <Icon name="plan" size={14}/><span>No plano <strong>{activePlan.title}</strong></span>
  </a>;
}

/**
 * The one title of every Planner screen (inner blocks use h2/h3). Compact and
 * sticky: crumbs only on third-level pages, one line of context, actions and
 * the brand/project selector on the same row.
 */
export function PlannerHeader({title, description, crumbs, back, meta, actions, leading = null, withContext = false}) {
  const {contextNode} = useContext(PlannerChrome);
  const trail = crumbs || (back ? [[back.label, back.href]] : null);
  return <header className="ph">
    {leading && <span className="ph__leading">{leading}</span>}
    <div className="ph__copy">
      {trail?.length > 0 && <ol className="ph__crumbs" aria-label="Você está em">{trail.map(([label, href]) => <li key={label}>
        {href ? <a href={href}>{label}</a> : <span>{label}</span>}<span aria-hidden="true">/</span>
      </li>)}</ol>}
      <div className="ph__title"><h1 title={typeof title === 'string' ? title : undefined}>{title}</h1>{meta}</div>
      {description && <p>{description}</p>}
    </div>
    {(actions || (withContext && contextNode)) && <div className="ph__actions">
      {withContext && contextNode}
      {actions}
    </div>}
  </header>;
}
