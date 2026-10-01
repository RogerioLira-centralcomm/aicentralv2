import React, {useEffect, useMemo, useState} from 'react';
import {ReportsPanelShell} from './ReportsPanelShell.jsx';
import {ReportsActionButton as Button} from './ReportsActionButton.jsx';
import {ReportsFieldInput} from './ReportsFieldInput.jsx';
import {buildProductionSheet, productionSheetCsv, productionSheetHtml} from './flowProductionSheet.js';
import {FLOW_STRATEGIES} from './flowStrategies.js';
import {json} from './reportsCommon.jsx';

export const MAX_FLOW_TAGS = 12;
export const normalizeFlowTag = value => value.replace(/\s+/g, ' ').trim().slice(0, 40);

const download = (content, type, filename) => {
  const url = URL.createObjectURL(new Blob([content], {type}));
  const link = Object.assign(document.createElement('a'), {href: url, download: filename});
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
};
const fileName = name => (name || 'fluxo').normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9]+/gi, '-').replace(/^-|-$/g, '').toLowerCase() || 'fluxo';

/** The plan as a deliverable: labels for the team and the production sheet of what must be built. */
export function FlowPlanPanel({config, name, host, readOnly, onChange, onSelectNode, onClose, versionsUrl = '', versionsKey = 0, onSaveTemplate}) {
  const sheet = useMemo(() => buildProductionSheet(config), [config]);
  const [draftTag, setDraftTag] = useState('');
  const [versions, setVersions] = useState(null);
  const [template, setTemplate] = useState({name: '', sector: '', description: ''});
  const [templateState, setTemplateState] = useState('');
  const saveTemplate = async event => {
    event.preventDefault();
    setTemplateState('saving');
    try {await onSaveTemplate({...template, name: template.name.trim() || name}); setTemplateState('saved'); setTemplate({name: '', sector: '', description: ''});}
    catch (failure) {setTemplateState(failure.message || 'Não foi possível salvar o modelo.');}
  };
  useEffect(() => {
    if (!versionsUrl) return undefined;
    let current = true;
    json(versionsUrl).then(result => {if (current) setVersions(result.ready === false ? null : result.versions || []);}).catch(() => {if (current) setVersions(null);});
    return () => {current = false;};
  }, [versionsUrl, versionsKey]);
  const tags = config.tags || [];
  const strategy = FLOW_STRATEGIES.find(item => item.id === config.strategy_id);
  const addTag = () => {
    const tag = normalizeFlowTag(draftTag);
    if (!tag || tags.some(item => item.toLocaleLowerCase('pt-BR') === tag.toLocaleLowerCase('pt-BR')) || tags.length >= MAX_FLOW_TAGS) {setDraftTag(''); return;}
    onChange({...config, tags: [...tags, tag]});
    setDraftTag('');
  };
  const percent = sheet.progress.total ? Math.round(sheet.progress.done / sheet.progress.total * 100) : 0;
  return <ReportsPanelShell compact className="flow-blueprint-panel flow-plan-panel" title="Plano e produção" onClose={onClose}
    footer={<div className="flow-plan-panel__exports">
      <Button color="secondary" disabled={!sheet.sections.length} onClick={() => download(productionSheetCsv(sheet), 'text/csv;charset=utf-8', `folha-de-producao-${fileName(name)}.csv`)}>Exportar CSV</Button>
      <Button color="secondary" disabled={!sheet.sections.length} onClick={() => download(productionSheetHtml(sheet, {name, host}), 'text/html;charset=utf-8', `folha-de-producao-${fileName(name)}.html`)}>Baixar para imprimir</Button>
    </div>}>
    <section className="flow-plan-panel__progress" aria-label="Progresso da produção">
      <div><strong>{sheet.progress.done} de {sheet.progress.total}</strong><span>passos prontos para medir</span></div>
      <div className="flow-plan-panel__bar" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent} aria-label="Passos prontos"><span style={{width: `${percent}%`}}/></div>
      {sheet.openChecklist > 0 && <small>{sheet.openChecklist} {sheet.openChecklist === 1 ? 'item aberto' : 'itens abertos'} nos checklists da mesa.</small>}
    </section>
    <section className="flow-plan-panel__tags" aria-label="Etiquetas do fluxo">
      <h3>Etiquetas</h3>
      <div className="flow-plan-panel__chips">{tags.map(tag => <span key={tag} className="flow-plan-panel__chip">{tag}{!readOnly && <button type="button" aria-label={`Remover etiqueta ${tag}`} onClick={() => onChange({...config, tags: tags.filter(item => item !== tag)})}>×</button>}</span>)}{!tags.length && <small>Use etiquetas para encontrar planos por objetivo, canal ou equipe.</small>}</div>
      {!readOnly && tags.length < MAX_FLOW_TAGS && <form className="flow-plan-panel__tag-form" onSubmit={event => {event.preventDefault(); addTag();}}>
        <ReportsFieldInput aria-label="Nova etiqueta" placeholder="Ex.: Black Friday, Leads, Equipe A" maxLength="40" value={draftTag} onChange={event => setDraftTag(event.target.value)}/>
        <Button type="submit" color="secondary" disabled={!normalizeFlowTag(draftTag)}>Adicionar</Button>
      </form>}
    </section>
    {versions && <section className="flow-plan-panel__versions" aria-label="Versões do plano">
      <h3>Versões do plano <small>{versions.length}</small></h3>
      {versions.length ? <ol>{versions.map(version => <li key={version.revision}><strong>v{version.revision}</strong><span>{new Date(version.created_at).toLocaleString('pt-BR', {day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit'})}</span>{version.note && <small>{version.note}</small>}</li>)}</ol>
        : <small>Use Publicar › Publicar plano para congelar uma versão para aprovação, sem ligar a medição.</small>}
    </section>}
    {!readOnly && onSaveTemplate && <details className="flow-plan-panel__template">
      <summary>Salvar como modelo do time</summary>
      <form onSubmit={saveTemplate}>
        <p>O modelo leva o desenho, os públicos, os briefs, os criativos e as taxas. Endereços, responsáveis, prazos, verba e aprovações ficam de fora.</p>
        <ReportsFieldInput aria-label="Nome do modelo" placeholder={name || 'Nome do modelo'} maxLength="120" value={template.name} onChange={event => setTemplate(current => ({...current, name: event.target.value}))}/>
        <ReportsFieldInput aria-label="Setor" placeholder="Setor (ex.: Imobiliário)" maxLength="40" value={template.sector} onChange={event => setTemplate(current => ({...current, sector: event.target.value}))}/>
        <ReportsFieldInput aria-label="Quando usar" placeholder="Quando usar este modelo" maxLength="500" value={template.description} onChange={event => setTemplate(current => ({...current, description: event.target.value}))}/>
        <Button type="submit" color="secondary" disabled={templateState === 'saving' || !config.nodes.length}>{templateState === 'saving' ? 'Salvando…' : 'Salvar modelo'}</Button>
        {templateState === 'saved' && <small role="status">Modelo salvo. Ele aparece em Fluxos › Modelos › Do time.</small>}
        {templateState && !['saving', 'saved'].includes(templateState) && <small role="alert" className="is-error">{templateState}</small>}
      </form>
    </details>}
    {sheet.sections.length ? sheet.sections.map(section => <section key={section.id} className="flow-plan-panel__section" aria-label={section.label}>
      <h3>{section.label} <small>{section.items.length}</small></h3>
      <ul>{section.items.map(item => <li key={item.id}>
        <button type="button" className={`flow-plan-item${item.done ? ' is-done' : ''}`} onClick={() => onSelectNode(item.id)}>
          <span className="flow-plan-item__head"><strong>{item.title}</strong>{item.statusLabel && <em>{item.statusLabel}</em>}</span>
          <small>{[item.kind, item.spec.owner, item.spec.due_date && new Date(`${item.spec.due_date}T12:00:00`).toLocaleDateString('pt-BR')].filter(Boolean).join(' · ')}</small>
          {item.missing.length > 0 && <span className="flow-plan-item__missing">{item.section === 'note' ? 'Aberto' : 'Falta'}: {item.missing.join(', ')}</span>}
        </button>
      </li>)}</ul>
    </section>) : <p>Adicione passos ao desenho para montar a folha de produção.</p>}
  </ReportsPanelShell>;
}
