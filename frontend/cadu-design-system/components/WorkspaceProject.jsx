import React, {useEffect, useRef, useState} from 'react';
import {CaduDock} from './CaduDock';
import {VisualIdentity} from './VisualIdentity';
import {WorkspaceAccountMenu} from './WorkspaceFeedback';
import {CaduDialog} from './CaduDialog';
import {openWorkspaceDetail} from '../workspaceNavigation';
import {csrf, request} from '../../conversations-v2/lib/api';
import {WorkspaceMobileChrome} from './WorkspaceMobileChrome';
import {useWorkspaceViewport} from '../hooks/useWorkspaceViewport';
import {EntityContextRail, EntityNavigator} from './WorkspaceEntityPortal';
import {WorkspaceNotificationCenter} from './WorkspaceNotificationCenter';
import {dockProviderLogo} from '../dockExternal.mjs';

function ProjectIcon({name}) {
  const paths = {
    context: <><path d="M5 4h14v16H5z"/><path d="M8 8h8M8 12h8M8 16h5"/></>,
    source: <><path d="M5 3h10l4 4v14H5z"/><path d="M15 3v5h5M8 12h8M8 16h6"/></>,
    delivery: <><path d="M5 4h14v16H5z"/><path d="m8 13 3 3 5-6"/></>,
    spark: <><path d="m12 3 1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/></>,
    conversation: <><path d="M5 5h14v10H9l-4 4z"/><path d="M8 9h8M8 12h5"/></>,
    artifact: <><path d="M6 3h9l3 3v15H6z"/><path d="M15 3v4h4M9 11h6M9 15h6"/></>,
    file: <><path d="M6 3h9l3 3v15H6z"/><path d="M15 3v4h4M9 12h6M9 16h4"/></>,
    pdf: <><path d="M6 3h9l3 3v15H6z"/><path d="M15 3v4h4M8 15h2a1.5 1.5 0 0 0 0-3H8v6M13 12h1.5a2 2 0 0 1 0 4H13z"/></>,
    image: <><rect x="4" y="5" width="16" height="14" rx="2"/><circle cx="9" cy="10" r="1.3"/><path d="m5 17 4-4 3 3 2-2 5 4"/></>,
    html: <><path d="m8 7-4 5 4 5M16 7l4 5-4 5M14 4l-4 16"/></>,
    text: <><path d="M5 4h14v16H5z"/><path d="M8 8h8M8 12h8M8 16h5"/></>,
    plan: <><path d="M5 4h14v16H5z"/><path d="M8 8h8M8 12h5M8 16h7"/><path d="M8 2v4M16 2v4"/></>,
    analysis: <><circle cx="10.5" cy="10.5" r="5.5"/><path d="m15 15 4 4M8 10.5h5M10.5 8v5"/></>,
    link: <><path d="M10 13a5 5 0 0 0 7.1 0l2.1-2.1a5 5 0 0 0-7.1-7.1L10 5.9M14 11a5 5 0 0 0-7.1 0l-2.1 2.1a5 5 0 0 0 7.1 7.1L14 18.1"/></>,
  };
  return <svg className="cadu-ds-project-icon" viewBox="0 0 24 24" aria-hidden="true">{paths[name] || paths.context}</svg>;
}

function ProjectLinkImage({src}) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [src]);
  return src && !failed ? <img src={src} alt="" loading="lazy" onError={() => setFailed(true)}/> : <ProjectIcon name="link"/>;
}

function normalizeProjectSearch(value) {
  return String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('pt-BR');
}

function writeDockResourcePayload(event, resource, projectId) {
  const target = new URL(window.location.href);
  target.searchParams.set('resource', resource.id);
  const payload = {
    id: `resource:${resource.id}`, type: 'resource', kind: 'resource', resourceRef: String(resource.id),
    projectRef: `ci:${projectId}`, title: resource.title || 'Recurso', resourceType: resource.resourceType || resource.kind || 'resource',
    previewUrl: /^https:\/\//i.test(resource.locator || '') ? resource.locator : '', href: `${target.pathname}${target.search}`,
  };
  const serialized = JSON.stringify(payload);
  event.dataTransfer.effectAllowed = 'copy';
  event.dataTransfer.setData('application/x-cadu-item', serialized);
  event.dataTransfer.setData('text/plain', serialized);
}

function ProjectDialog({title, detail, onClose, children}) {
  return <CaduDialog className="cadu-ds-project-dialog" label={title} onClose={onClose}>
    <header className="cadu-ds-project-dialog__header"><div><h2>{title}</h2>{detail && <p>{detail}</p>}</div><button type="button" onClick={onClose} aria-label="Fechar">×</button></header>
    {children}
  </CaduDialog>;
}

function ProjectTitle({name}) {
  const titleRef = useRef(null);
  const [fontSize, setFontSize] = useState(34);
  useEffect(() => {
    const node = titleRef.current;
    if (!node) return undefined;
    const fit = () => {
      const width = node.clientWidth;
      if (!width) return;
      const style = window.getComputedStyle(node);
      const canvas = document.createElement('canvas');
      const context = canvas.getContext('2d');
      let nextSize = 34;
      if (context) {
        for (; nextSize > 17; nextSize -= 1) {
          context.font = `${style.fontWeight} ${nextSize}px ${style.fontFamily}`;
          if (context.measureText(name || '').width <= width) break;
        }
      }
      setFontSize(current => current === nextSize ? current : nextSize);
    };
    fit();
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(fit);
    observer?.observe(node);
    window.addEventListener('resize', fit);
    return () => { observer?.disconnect(); window.removeEventListener('resize', fit); };
  }, [name]);
  return <h1 ref={titleRef} style={{fontSize}}>{name}</h1>;
}

function SharingDialog({project, urls, csrfToken, onClose, onSaved}) {
  const [visibility, setVisibility] = useState(project.sharing?.visibility || 'private');
  const [team, setTeam] = useState([]);
  const [loadingTeam, setLoadingTeam] = useState(true);
  const [members, setMembers] = useState((project.sharing?.members || []).map(item => String(item.id)));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => { setLoadingTeam(true); fetch(urls.sharing, {credentials: 'same-origin'}).then(response => response.ok ? response.json() : Promise.reject(new Error('Não foi possível carregar a equipe.'))).then(value => setTeam(value.team || [])).catch(loadError => setError(loadError.message)).finally(() => setLoadingTeam(false)); }, [urls.sharing]);
  const toggle = id => setMembers(current => current.includes(String(id)) ? current.filter(item => item !== String(id)) : [...current, String(id)]);
  const save = async event => { event.preventDefault(); setBusy(true); setError(''); try { const response = await fetch(urls.sharing, {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken, Accept: 'application/json'}, body: JSON.stringify({visibility, members: members.map(user_id => ({user_id: Number(user_id), role: 'member'}))})}); const value = await response.json(); if (!response.ok) throw new Error(value.error || 'Não foi possível salvar o acesso.'); onSaved?.({visibility: value.visibility, members: value.members || []}); onClose?.(); } catch (saveError) { setError(saveError.message); setBusy(false); } };
  return <ProjectDialog title="Gerenciar acesso" detail="Escolha quem pode acessar este projeto." onClose={onClose}><form className="cadu-ds-project-form" aria-busy={busy || loadingTeam} onSubmit={save}><label>Visibilidade<select disabled={busy} value={visibility} onChange={event => setVisibility(event.target.value)}><option value="private">Privado</option><option value="team">Toda a equipe</option><option value="restricted">Pessoas específicas</option></select></label>{visibility === 'restricted' && <fieldset className="cadu-ds-sharing-people"><legend>Pessoas com acesso</legend>{loadingTeam ? <p>Carregando equipe…</p> : team.length ? team.map(person => <label key={person.id}><input type="checkbox" disabled={busy} checked={members.includes(String(person.id))} onChange={() => toggle(person.id)}/><span>{person.name}<small>{person.email}</small></span></label>) : <p>Nenhuma pessoa ativa disponível.</p>}</fieldset>}{error && <p className="cadu-ds-project-upload-error" role="alert">{error}</p>}<footer><button type="button" disabled={busy} onClick={onClose}>Cancelar</button><button className="is-primary" disabled={busy || loadingTeam}>{busy ? 'Salvando…' : 'Salvar acesso'}</button></footer></form></ProjectDialog>;
}

function ProjectManagementDialog({project, projects, urls, csrfToken, mode, initialTargetId = '', onClose}) {
  const [targetId, setTargetId] = useState(initialTargetId);
  const [confirmation, setConfirmation] = useState('');
  const isMerge = mode === 'merge';
  const targets = (projects || []).filter(item => {
    const id = String(item.projectRef || item.id || '').replace(/^ci:/, '');
    return id && id !== String(project.id);
  });
  const confirmed = isMerge ? Boolean(targetId) : confirmation.trim().toLocaleLowerCase('pt-BR') === String(project.name || '').trim().toLocaleLowerCase('pt-BR');
  return <ProjectDialog title={isMerge ? 'Mesclar com outro projeto' : 'Excluir projeto'} detail={isMerge ? 'Todo o histórico deste projeto será transferido para o projeto escolhido.' : 'O projeto deixará de aparecer no Workspace. Esta ação exige confirmação.'} onClose={onClose}>
    <form className="cadu-ds-project-form cadu-ds-project-management-form" method="post" action={isMerge ? urls.merge : urls.deleteProject}>
      <input type="hidden" name="_csrf" value={csrfToken}/>
      {isMerge ? <>
        <label>Projeto de destino<select name="target_project_id" required value={targetId} onChange={event => setTargetId(event.target.value)}><option value="">Escolher projeto</option>{targets.map(item => { const id = String(item.projectRef || item.id || '').replace(/^ci:/, ''); return <option key={id} value={id}>{item.title || item.name || 'Projeto'}</option>; })}</select></label>
        <p className="cadu-ds-project-management-form__notice"><b>{project.name}</b> será marcado como mesclado. Fontes, conversas, entregas e vínculos passam para o destino.</p>
        {!targets.length && <p className="cadu-ds-project-upload-error" role="alert">Não há outro projeto ativo disponível para receber os dados.</p>}
      </> : <>
        <p className="cadu-ds-project-management-form__notice">Fontes e histórico ficam preservados internamente, mas o projeto não poderá mais ser acessado.</p>
        <label>Digite <b>{project.name}</b> para confirmar<input name="confirmation_name" autoComplete="off" value={confirmation} onChange={event => setConfirmation(event.target.value)}/></label>
      </>}
      <footer><button type="button" onClick={onClose}>Cancelar</button><button className="is-danger" disabled={!confirmed}>{isMerge ? 'Mesclar projetos' : 'Excluir projeto'}</button></footer>
    </form>
  </ProjectDialog>;
}

const PROJECT_CONTEXT_SOURCE_LABELS = {
  conversation: 'Conversa',
  confirmed_project_reset: 'Substituição confirmada',
  workspace_api: 'API do Workspace',
  workspace_form: 'Edição no Workspace',
  workspace: 'Workspace',
  mcp: 'MCP',
};

function contextHistoryDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return new Intl.DateTimeFormat('pt-BR', {dateStyle:'short', timeStyle:'short'}).format(date);
}

function contextHistoryField(value) {
  const removed = String(value || '').startsWith('-');
  const key = String(value || '').replace(/^-/, '');
  const labels = {name:'Nome', description:'Direção', audience:'Público', tone_of_voice:'Tom de voz', positioning:'Posicionamento', instructions:'Orientações'};
  const label = labels[key] || key.replace(/_/g, ' ').replace(/^./, character => character.toLocaleUpperCase('pt-BR'));
  return removed ? `${label} removido` : label;
}

function IdentityDialog({project, urls, csrfToken, onClose}) {
  const [customFields, setCustomFields] = useState(() => Object.entries(project.customFields || {}).map(([key, item]) => ({
    key, label:item?.label || key.replace(/_/g, ' '), type:item?.type || (Array.isArray(item?.value) ? 'list' : 'text'),
    value:Array.isArray(item?.value) ? item.value.join('\n') : String(item?.value ?? ''),
  })));
  const addField = () => setCustomFields(current => [...current, {key:`campo_${crypto.randomUUID().slice(0, 8)}`, label:'', type:'text', value:''}]);
  const updateField = (key, patch) => setCustomFields(current => current.map(item => item.key === key ? {...item, ...patch} : item));
  const removeField = key => setCustomFields(current => current.filter(item => item.key !== key));
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyItems, setHistoryItems] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState('');
  const toggleHistory = async () => {
    if (historyOpen) { setHistoryOpen(false); return; }
    setHistoryOpen(true);
    if (historyItems.length || historyLoading || !urls.directionHistory) return;
    setHistoryLoading(true);
    setHistoryError('');
    try {
      const response = await fetch(urls.directionHistory, {credentials:'same-origin', headers:{Accept:'application/json'}});
      const value = await response.json();
      if (!response.ok) throw new Error(value.error || 'Não foi possível carregar o histórico.');
      setHistoryItems(Array.isArray(value.items) ? value.items : []);
    } catch (error) {
      setHistoryError(error.message || 'Não foi possível carregar o histórico.');
    } finally {
      setHistoryLoading(false);
    }
  };
  const serialized = JSON.stringify(Object.fromEntries(customFields.filter(item => item.label.trim()).map(item => [item.key, {
    label:item.label.trim(), type:item.type, value:item.type === 'list' ? item.value.split('\n').map(value => value.trim()).filter(Boolean) : item.value.trim(),
  }])));
  return <ProjectDialog title="Editar contexto" detail="Registre apenas o que deve orientar conversas, planos e criações." onClose={onClose}>
    <form className="cadu-ds-project-form" method="post" action={urls.updateContext}>
      <input type="hidden" name="_csrf" value={csrfToken}/>
      <input type="hidden" name="expected_revision" value={project.contextRevision || 1}/>
      <input type="hidden" name="custom_fields_json" value={serialized}/>
      <label>Nome do projeto<input name="name" required minLength="2" maxLength="150" defaultValue={project.name}/></label>
      <label>Direção do trabalho<textarea name="description" rows="3" maxLength="4000" defaultValue={project.description}/></label>
      <div className="cadu-ds-project-form__grid"><label>Público<textarea name="audience" rows="3" maxLength="4000" defaultValue={project.identity?.publico}/></label><label>Tom de voz<textarea name="tone_of_voice" rows="3" maxLength="4000" defaultValue={project.identity?.tom_de_voz}/></label></div>
      <label>Posicionamento<textarea name="positioning" rows="3" maxLength="4000" defaultValue={project.identity?.posicionamento}/></label>
      <label>Orientações para o Cadu<textarea name="instructions" rows="5" maxLength="12000" defaultValue={project.instructions}/></label>
      <section className="cadu-ds-project-form__custom" aria-labelledby="project-custom-fields-title"><header><div><b id="project-custom-fields-title">Itens personalizados</b><small>Dados próprios deste projeto também entram no contexto das conversas.</small></div><button type="button" onClick={addField}>Adicionar item</button></header>{customFields.length ? <div>{customFields.map(field => <article key={field.key}><label>Nome do item<input value={field.label} maxLength="120" placeholder="Ex.: Orçamento mensal" onChange={event => updateField(field.key, {label:event.target.value})}/></label><label>Tipo<select value={field.type} onChange={event => updateField(field.key, {type:event.target.value})}><option value="text">Texto</option><option value="list">Lista</option><option value="number">Número</option><option value="currency">Moeda</option><option value="date">Data</option><option value="url">Link</option></select></label><label>Conteúdo<textarea rows="3" maxLength="12000" value={field.value} placeholder={field.type === 'list' ? 'Um item por linha' : 'Informação que deve orientar o projeto'} onChange={event => updateField(field.key, {value:event.target.value})}/></label><button type="button" onClick={() => removeField(field.key)} aria-label={`Remover ${field.label || 'item personalizado'}`}>Remover</button></article>)}</div> : <p>Nenhum item personalizado. Adicione objetivos, orçamento, canais, restrições ou qualquer dado específico deste trabalho.</p>}</section>
      {urls.directionHistory && <section className="cadu-ds-project-form__history" aria-labelledby="project-context-history-title"><header><div><b id="project-context-history-title">Histórico da direção</b><small>Acompanhe quando e por onde o contexto foi alterado.</small></div><button type="button" aria-expanded={historyOpen} onClick={toggleHistory}>{historyOpen ? 'Ocultar histórico' : 'Ver histórico'}</button></header>{historyOpen && <div className="cadu-ds-project-form__history-body">{historyLoading ? <p role="status">Carregando histórico…</p> : historyError ? <p className="is-error" role="alert">{historyError}</p> : historyItems.length ? <ol>{historyItems.map(item => <li key={`${item.revision}-${item.created_at}`}><div><b>Revisão {item.revision}</b><small>{PROJECT_CONTEXT_SOURCE_LABELS[item.source] || item.source || 'Atualização'}{contextHistoryDate(item.created_at) ? ` · ${contextHistoryDate(item.created_at)}` : ''}</small></div><p>{(item.changed_fields || []).map(contextHistoryField).join(', ') || 'Contexto atualizado'}</p></li>)}</ol> : <p>Nenhuma alteração registrada ainda.</p>}</div>}</section>}
      <label>Cor de referência<input name="color" type="color" defaultValue={project.color}/></label>
      <footer><button type="button" onClick={onClose}>Cancelar</button><button className="is-primary">Salvar contexto</button></footer>
    </form>
  </ProjectDialog>;
}

const TRIAGE_CATEGORIES = [['brief', 'Briefing'], ['research', 'Pesquisa'], ['media_plan', 'Plano de mídia'], ['report', 'Relatório'], ['brand_asset', 'Ativo de marca'], ['reference', 'Referência'], ['contract', 'Contrato'], ['spreadsheet', 'Planilha'], ['other', 'Outro']];

function sourceErrorMessage(error, fallback) {
  const message = String(error?.message || error || '').trim();
  if (!message || /temporariamente indisponível|service unavailable|\b503\b/i.test(message)) {
    return `${fallback} O serviço de fontes está indisponível agora; tente novamente em instantes.`;
  }
  return message;
}

function brandTokens(brand) {
  const result = [];
  const add = (item, fallbackRole) => {
    const value = typeof item === 'string' ? item.trim() : String(item?.hex || '').trim();
    if (!value || result.some(token => token.value.toLowerCase() === value.toLowerCase())) return;
    result.push({value, label: typeof item === 'object' ? item.name || item.role || fallbackRole : fallbackRole});
  };
  (Array.isArray(brand?.profile?.colorPalette) ? brand.profile.colorPalette : []).forEach(item => add(item, 'Cor da marca'));
  add(brand?.color, 'Principal');
  add(brand?.secondaryColor, 'Secundária');
  return result.slice(0, 5);
}

function brandFonts(brand) {
  return (Array.isArray(brand?.profile?.fonts) ? brand.profile.fonts : [])
    .map(item => typeof item === 'string' ? {family: item, role: 'Fonte'} : {family: item?.family || item?.classification || '', role: item?.role || 'Fonte'})
    .filter(item => item.family)
    .slice(0, 4);
}

function BrandPickerDialog({brands, currentBrandId, urls, csrfToken, canManageBrand, onClose, onCreate}) {
  return <ProjectDialog title="Definir marca do projeto" detail="Escolha a identidade que deve orientar as conversas, fontes e entregas deste projeto." onClose={onClose}>
    <div className="cadu-ds-project-brand-picker">
      {brands.length ? brands.map(brand => <form method="post" action={urls.updateBrands} key={brand.id}>
        <input type="hidden" name="_csrf" value={csrfToken}/><input type="hidden" name="brand_ids" value={brand.id}/>
        <button type="submit" className={String(brand.id) === String(currentBrandId) ? 'is-selected' : ''}><VisualIdentity src={brand.logoUrl} initials={brand.visualInitials || brand.name} label={brand.name} color={brand.visualColor} variant={brand.visualVariant}/><span><b>{brand.name}</b><small>{brand.description || 'Abrir esta identidade no projeto'}</small></span><i aria-hidden="true">{String(brand.id) === String(currentBrandId) ? 'Atual' : 'Usar'}</i></button>
      </form>) : <p className="cadu-ds-project-empty-copy">Ainda não há marcas cadastradas nesta agência.</p>}
    </div>
    <footer className="cadu-ds-project-dialog__footer"><a href={urls.brands}>Ver marcas</a>{canManageBrand && <button type="button" className="is-primary" onClick={onCreate}>Criar e auditar marca</button>}</footer>
  </ProjectDialog>;
}

function BrandFileDrop({label, hint, name, multiple = false}) {
  const input = useRef(null);
  const [active, setActive] = useState(false);
  const [files, setFiles] = useState([]);
  const assign = values => {
    const selected = Array.from(values || []).slice(0, multiple ? 8 : 1);
    if (!selected.length || !input.current) return;
    const transfer = new DataTransfer();
    selected.forEach(file => transfer.items.add(file));
    input.current.files = transfer.files;
    setFiles(selected);
  };
  return <div className={`cadu-ds-brand-file-drop${active ? ' is-active' : ''}`} onDragEnter={event => { event.preventDefault(); setActive(true); }} onDragOver={event => event.preventDefault()} onDragLeave={event => { if (event.currentTarget === event.target) setActive(false); }} onDrop={event => { event.preventDefault(); setActive(false); assign(event.dataTransfer?.files); }}>
    <input ref={input} name={name} type="file" accept="image/*" multiple={multiple} hidden aria-hidden="true" tabIndex="-1" onChange={event => assign(event.target.files)}/>
    <div role="status"><strong>{files.length ? `${files.length} arquivo${files.length > 1 ? 's' : ''} preparado${files.length > 1 ? 's' : ''}` : label}</strong><small>{files.length ? files.map(file => file.name).join(', ') : hint}</small></div>
  </div>;
}

function ImportBrandDialog({urls, csrfToken, onClose}) {
  return <ProjectDialog title="Criar e auditar marca" detail="A nova marca será vinculada a este projeto e seguirá para uma auditoria com revisão humana." onClose={onClose}>
    <form className="cadu-ds-project-form" method="post" encType="multipart/form-data" action={urls.importBrand}>
      <input type="hidden" name="_csrf" value={csrfToken}/>
      <p className="cadu-ds-project-form__intro">Informe o site oficial e, se tiver, envie o logo e referências. A análise não aprova nada sozinha: ela prepara evidências para você revisar.</p>
      <label>Nome da marca<input name="brand_name" required minLength="2" maxLength="150" placeholder="Ex.: Uhuru"/></label>
      <label>Site oficial<input name="website_url" type="url" required maxLength="2000" placeholder="https://exemplo.com"/></label>
      <label>Logo principal <small>Opcional</small><BrandFileDrop name="logo" label="Solte o logo aqui" hint="Imagem principal da marca"/></label>
      <label>Referências visuais <small>Opcional · até 8 arquivos</small><BrandFileDrop name="images" multiple label="Solte referências aqui" hint="Imagens oficiais da marca"/></label>
      <footer><button type="button" onClick={onClose}>Cancelar</button><button className="is-primary">Criar e iniciar auditoria</button></footer>
    </form>
  </ProjectDialog>;
}

function ProjectBrandCard({brand, urls, canEdit, canManageBrand, onDialog}) {
  const colors = brandTokens(brand);
  const fonts = brandFonts(brand);
  const hasBrand = Boolean(brand?.id);
  const identityCount = [Boolean(brand?.logoUrl), colors.length > 0, fonts.length > 0].filter(Boolean).length;
  return <section className={`cadu-ds-project-brand-feature ${hasBrand ? 'has-brand' : 'is-unassigned'}`} aria-labelledby="project-brand-feature-title">
    <header><div><h2 id="project-brand-feature-title">{hasBrand ? 'A marca que orienta este trabalho' : 'Defina a marca deste projeto'}</h2></div>{hasBrand && <span className="cadu-ds-project-brand-feature__status">{identityCount === 3 ? 'Completa' : 'Parcial'}</span>}</header>
    {hasBrand ? <div className="cadu-ds-project-brand-feature__body">
      <a className="cadu-ds-project-brand-feature__identity" href={brand.href}><VisualIdentity src={brand.logoUrl} initials={brand.initials || brand.name} label={brand.name} color={brand.color} variant={brand.visualVariant}/><span><b>{brand.name}</b></span></a>
      <div className="cadu-ds-project-brand-feature__tokens">{colors.length > 0 && <div><b>Cores</b><span className="cadu-ds-project-brand-feature__swatches">{colors.map(token => <i key={token.value} title={`${token.label}: ${token.value}`} style={{background: token.value}}/> )}</span></div>}{fonts.length > 0 && <div><b>Tipografia</b><span className="cadu-ds-project-brand-feature__fonts">{fonts.map(font => <span key={`${font.role}-${font.family}`}><strong>{font.family}</strong><small>{font.role}</small></span>)}</span></div>}</div>
      <div className="cadu-ds-project-brand-feature__actions"><a href={brand.href}>{identityCount === 3 ? 'Identidade' : 'Definir identidade'}</a>{canEdit && <button type="button" onClick={() => onDialog('brand-picker')}>Trocar marca</button>}{canManageBrand && brand.auditHref && <a href={brand.auditHref}>Auditar</a>}</div>
    </div> : <div className="cadu-ds-project-brand-feature__empty"><div className="cadu-ds-project-brand-feature__empty-mark"><ProjectIcon name="spark"/></div><div><h3>Nenhuma marca vinculada</h3><p>Escolha uma marca existente ou crie uma nova já com auditoria ligada a este projeto.</p></div><div className="cadu-ds-project-brand-feature__actions">{canEdit && <button type="button" className="is-primary" onClick={() => onDialog('brand-picker')}>Definir marca</button>}{canManageBrand && <button type="button" onClick={() => onDialog('brand-import')}>Criar e auditar marca</button>}</div></div>}
  </section>;
}

function NoteDialog({urls, csrfToken, onClose}) {
  return <ProjectDialog title="Adicionar nota" onClose={onClose}>
    <form className="cadu-ds-project-form cadu-ds-project-note-form" method="post" action={urls.createNote}>
      <input type="hidden" name="_csrf" value={csrfToken}/>
      <label>Título<input autoFocus name="title" required minLength="2" maxLength="180"/></label>
      <label>Nota<textarea name="content" required minLength="20" maxLength="50000" rows="6"/></label>
      <footer><button type="button" onClick={onClose}>Cancelar</button><button className="is-primary">Salvar nota</button></footer>
    </form>
  </ProjectDialog>;
}

function SourceUploadDialog({urls, csrfToken, canEdit, pendingFiles = [], droppedFiles, onDropConsumed, onClose}) {
  const fileInput = useRef(null);
  const [triage, setTriage] = useState(() => pendingFiles.filter(file => file.requiresReview).map(file => ({source_id: file.id, name: file.title, mime: file.mime, processing: 'metadata_only', text_preview: '', can_index: file.canIndex, confirm_url: file.confirmUrl, purpose: 'project_attachment', category: file.category || 'other'})));
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState('');
  const [draftFiles, setDraftFiles] = useState([]);
  const uploadFiles = async (incoming) => {
    const selected = Array.from(incoming || []).filter(Boolean);
    if (!selected.length || busy) return;
    setError('');
    setDraftFiles(current => [...current, ...selected.map(file => ({
      id: `${file.name}-${file.size}-${file.lastModified}-${Math.random().toString(36).slice(2)}`,
      file, name: file.name, mime: file.type || 'Arquivo', category: 'other',
      purpose: 'knowledge_source', can_index: true,
    }))]);
  };
  const uploadDraftFile = async item => {
    if (busy) return;
    setBusy(true); setError('');
    try {
      const body = new FormData(); body.append('_csrf', csrfToken); body.append('file', item.file);
      const response = await fetch(urls.uploadSource, {method: 'POST', credentials: 'same-origin', headers: {'Accept': 'application/json', 'X-CSRF-Token': csrfToken, 'X-Cadu-Triage': '1'}, body});
      const value = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(value.error || 'Não foi possível preparar este arquivo.');
      setDraftFiles(current => current.filter(entry => entry.id !== item.id));
      setTriage(current => [...current, {...value, ...item, source_id:value.source_id, confirm_url:value.confirm_url, can_index:value.can_index}]);
    } catch (uploadError) { setError(sourceErrorMessage(uploadError, 'Não foi possível preparar o arquivo.')); setBusy(false); }
    finally { setBusy(false); }
  };
  const saveTriageDecision = async (item) => {
    setBusy(true); setError('');
    try {
      const response = await fetch(item.confirm_url || item.confirmUrl, {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'Accept': 'application/json', 'X-CSRF-Token': csrfToken}, body: JSON.stringify({purpose: item.purpose, category: item.category})});
      const value = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(value.error || 'Não foi possível confirmar este arquivo.');
      setTriage(current => current.filter(entry => entry.source_id !== item.source_id));
      setDraftFiles(current => current.filter(entry => entry.id !== item.id));
      window.setTimeout(() => window.location.reload(), 250);
    } catch (confirmError) { setError(sourceErrorMessage(confirmError, 'Não foi possível confirmar o arquivo.')); }
    finally { setBusy(false); }
  };
  const updateTriage = (sourceId, key, value) => setTriage(current => current.map(item => item.source_id === sourceId ? {...item, [key]: value} : item));
  const onDrop = event => { event.preventDefault(); setDragging(false); uploadFiles(event.dataTransfer.files); };
  useEffect(() => {
    if (!droppedFiles?.length) return;
    uploadFiles(droppedFiles);
    onDropConsumed?.();
  }, [droppedFiles]);
  return <ProjectDialog title="Adicionar fonte" onClose={onClose}>
    {canEdit && <><input ref={fileInput} type="file" multiple hidden onChange={event => { uploadFiles(event.target.files); event.target.value = ''; }}/><div className={`cadu-ds-project-upload-drop${dragging ? ' is-dragging' : ''}`} onDragEnter={event => {event.preventDefault(); setDragging(true);}} onDragOver={event => event.preventDefault()} onDragLeave={event => {if (event.currentTarget === event.target) setDragging(false);}} onDrop={onDrop}><span className="cadu-ds-project-upload-drop__icon"><ProjectIcon name="source"/></span><b>{busy ? 'Preparando…' : 'Solte arquivos aqui'}</b><button type="button" disabled={busy} onClick={() => fileInput.current?.click()}>Selecionar arquivos</button></div></>}
    {error && <p className="cadu-ds-project-upload-error" role="alert">{error}</p>}
    {!!draftFiles.length && <section className="cadu-ds-project-triage" aria-label="Preparar arquivos"><header><b>Arquivos selecionados</b><span>{draftFiles.length}</span></header>{draftFiles.map(item => <article key={item.id}><div className="cadu-ds-project-triage__file"><ProjectIcon name="source"/><span><b>{item.name}</b><small>{item.mime}</small></span></div><label className="cadu-ds-project-triage__category">Categoria<select value={item.category} onChange={event => setDraftFiles(current => current.map(entry => entry.id === item.id ? {...entry, category:event.target.value} : entry))}>{TRIAGE_CATEGORIES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><button type="button" className="is-primary" disabled={busy} onClick={() => uploadDraftFile(item)}>{busy ? 'Preparando…' : 'Preparar para revisar'}</button></article>)}</section>}
    {!!triage.length && <section className="cadu-ds-project-triage" aria-label="Confirmar arquivos no projeto"><header><b>Confirmar destino</b><span>{triage.length}</span></header>{triage.map(item => <article key={item.source_id}><div className="cadu-ds-project-triage__file"><ProjectIcon name="source"/><span><b>{item.name}</b><small>{item.mime}</small></span></div><label className="cadu-ds-project-triage__category">Categoria<select value={item.category} onChange={event => updateTriage(item.source_id, 'category', event.target.value)}>{TRIAGE_CATEGORIES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><div className="cadu-ds-project-triage__purpose"><label><input type="radio" name={`purpose-${item.source_id}`} checked={item.purpose === 'project_attachment'} onChange={() => updateTriage(item.source_id, 'purpose', 'project_attachment')}/> Salvar como anexo</label><label className={!item.can_index ? 'is-disabled' : ''}><input type="radio" name={`purpose-${item.source_id}`} disabled={!item.can_index} checked={item.purpose === 'knowledge_source'} onChange={() => updateTriage(item.source_id, 'purpose', 'knowledge_source')}/> Indexar como fonte</label></div><button type="button" className="is-primary" disabled={busy || (item.purpose === 'knowledge_source' && !item.can_index)} onClick={() => saveTriageDecision(item)}>{busy ? 'Salvando…' : 'Adicionar ao projeto'}</button></article>)}</section>}
  </ProjectDialog>;
}

function LinkDialog({urls, csrfToken, onClose}) {
  return <ProjectDialog title="Adicionar link" onClose={onClose}>
    <form className="cadu-ds-project-form cadu-ds-project-link-form" method="post" action={urls.createLink}><input type="hidden" name="_csrf" value={csrfToken}/><label>URL<input autoFocus name="url" type="url" required maxLength="2000" placeholder="https://exemplo.com"/></label><label>Nome <small>opcional</small><input name="title" maxLength="180" placeholder="Nome do link"/></label><footer><button type="button" onClick={onClose}>Cancelar</button><button className="is-primary">Salvar link</button></footer></form>
  </ProjectDialog>;
}

function ResourceDialog({resource, onClose}) {
  const externalUrl = /^https:\/\//i.test(resource.locator || '') ? resource.locator : '';
  const isImage = resource.resourceType === 'image' && externalUrl;
  return <ProjectDialog title={resource.title} detail="Recurso conectado ao projeto" onClose={onClose}>
    <div className="cadu-ds-project-resource-inspector">
      {isImage && <img src={externalUrl} alt=""/>}
      <dl><div><dt>Tipo</dt><dd>{resource.kind || 'Recurso'}</dd></div><div><dt>Status</dt><dd>{resource.status || 'Disponível'}</dd></div>{resource.mime && <div><dt>Formato</dt><dd>{resource.mime}</dd></div>}</dl>
      {externalUrl ? <a className="is-primary" href={externalUrl} target="_blank" rel="noreferrer">Abrir recurso</a> : <p>Este recurso está organizado neste projeto. A prévia ou edição será aberta quando o sistema de origem disponibilizar um destino próprio.</p>}
    </div>
  </ProjectDialog>;
}

function sourceStatus(status) {
  return ({completed: 'Pronta para consulta', indexed: 'Pronta para consulta', ready: 'Pronta para consulta', indexing: 'Indexando', running: 'Indexando', queued: 'Na fila', pending: 'Na fila', error: 'Falha na indexação', failed: 'Falha na indexação', paused: 'Somente anexo', saved: 'Salvo sem indexar'})[status] || 'Fonte do projeto';
}

function projectLinkTitle(item = {}) {
  const title = String(item.title || item.name || '').trim();
  const provider = String(item.provider || '').trim();
  if (title && !['atalho', provider.toLocaleLowerCase('pt-BR')].includes(title.toLocaleLowerCase('pt-BR'))) return title;
  try { return new URL(item.url).hostname.replace(/^www\./i, '') || 'Link do projeto'; } catch (_) { return title || 'Link do projeto'; }
}

function deliveryStatus(item) {
  return item.status ? item.status.replace(/_/g, ' ') : 'Disponível';
}

function artifactIconName(kind) {
  return ({conversation: 'conversation', artifact: 'artifact', html: 'html', text: 'text', file: 'file', pdf: 'pdf', image: 'image', plan: 'plan', analysis: 'analysis'})[kind] || 'artifact';
}

function ProjectMemorySection({project, reviewBase, csrfToken, canEdit}) {
  const [confirmed, setConfirmed] = useState(project.memory || []);
  const [proposals, setProposals] = useState(project.memoryProposals || []);
  const [busyId, setBusyId] = useState('');
  const [error, setError] = useState('');
  const review = async (item, action) => {
    if (!reviewBase || !project.canReviewMemory || !canEdit) return;
    setBusyId(item.id); setError('');
    try {
      const data = await request(`${reviewBase}/${encodeURIComponent(item.id)}/revisao`, {
        method:'POST', headers:{'Content-Type':'application/json','X-CSRF-Token':csrfToken},
        body:JSON.stringify({action}),
      });
      setProposals(current => current.filter(candidate => candidate.id !== item.id));
      if (data.memory?.status === 'confirmed') setConfirmed(current => [data.memory, ...current]);
    } catch (reviewError) { setError(reviewError.message || 'Não foi possível revisar a memória.'); }
    finally { setBusyId(''); }
  };
  return <section className="cadu-ds-project-memory" aria-label="Memória do projeto">
    <header><h2>Memória do projeto</h2><p>Decisões confirmadas orientam as próximas conversas. Revise as propostas antes de usá-las como contexto.</p></header>
    {!!proposals.length && <div className="cadu-ds-project-memory__group"><h3>Para revisar</h3>{proposals.map(item => <article key={item.id}><small>{item.kind.replaceAll('_', ' ')}</small><p>{item.summary}</p>{project.canReviewMemory && canEdit && <div><button type="button" disabled={!!busyId} onClick={() => review(item, 'confirm')}>Confirmar</button><button type="button" disabled={!!busyId} onClick={() => review(item, 'dismiss')}>Descartar</button></div>}</article>)}</div>}
    {!!confirmed.length && <div className="cadu-ds-project-memory__group"><h3>Confirmadas</h3>{confirmed.map(item => <article key={item.id}><small>{item.kind.replaceAll('_', ' ')}</small><p>{item.summary}</p></article>)}</div>}
    {!proposals.length && !confirmed.length && <p className="cadu-ds-project-memory__empty">Ainda não há decisões revisadas neste projeto. As conversas anteriores podem ser consultadas na busca do Cadu.</p>}
    {error && <p role="alert" className="cadu-ds-project-memory__error">{error}</p>}
  </section>;
}

function ProjectContinuitySection({project, onStartConversation}) {
  const conversations = Array.isArray(project.conversations) ? project.conversations : [];
  const [showAllConversations, setShowAllConversations] = useState(false);
  const renderItem = entry => entry.href ? <a className="cadu-ds-project-continuity__item" href={entry.href} key={entry.id}>
    <span className={`cadu-ds-project-continuity__icon is-${entry.kind || 'artifact'}`}><ProjectIcon name={entry.kind === 'conversation' ? 'conversation' : artifactIconName(entry.kind)}/></span>
    <span className="cadu-ds-project-continuity__copy"><b>{entry.title}</b><small>{entry.detail}</small></span><i aria-hidden="true">›</i>
  </a> : <div className="cadu-ds-project-continuity__item" key={entry.id}>
    <span className={`cadu-ds-project-continuity__icon is-${entry.kind || 'artifact'}`}><ProjectIcon name={artifactIconName(entry.kind)}/></span>
    <span className="cadu-ds-project-continuity__copy"><b>{entry.title}</b><small>{entry.detail}</small></span>
  </div>;
  return <section className="cadu-ds-project-continuity" aria-label="Conversas do projeto">
    <div className="cadu-ds-project-continuity__columns is-single"><article>{conversations.length ? <>{(showAllConversations ? conversations : conversations.slice(0, 8)).map(renderItem)}{conversations.length > 8 && <button type="button" className="cadu-ds-project-continuity__more" onClick={() => setShowAllConversations(current => !current)}>{showAllConversations ? 'Mostrar menos' : `Ver todas as ${conversations.length} conversas`}</button>}</> : <div className="cadu-ds-project-empty has-illustration"><ProjectStateIllustration name="activity-empty" alt="Uma conversa pronta para iniciar o trabalho do projeto"/><div><h3>Comece pelo que precisa resolver</h3><p>As conversas deste projeto ficam reunidas aqui para você retomar decisões e continuar o trabalho.</p><button type="button" onClick={onStartConversation}>Nova conversa no projeto</button></div></div>}</article></div>
  </section>;
}

function ProjectIndexingSection({files = [], onReview, onAddLink}) {
  const indexed = files.filter(item => item.status === 'completed').length;
  const processing = files.filter(item => ['indexing', 'queued'].includes(item.status)).length;
  const attention = files.filter(item => ['error', 'failed'].includes(item.status)).length;
  return <section className="cadu-ds-project-indexing" id="indexacao">
    <header><div><span>{files.length ? `${files.length} fonte${files.length === 1 ? '' : 's'} no projeto` : 'Nenhuma fonte adicionada'}</span><small>Arquivos do projeto e estado da indexação.</small></div><div className="cadu-ds-project-indexing__actions"><button type="button" className="is-primary" onClick={onReview}>Adicionar arquivos</button><button type="button" onClick={onAddLink}>Adicionar link</button></div></header>
    {!!files.length && <div className="cadu-ds-project-indexing__summary"><span><b>{indexed}</b><small>prontas</small></span><span><b>{processing}</b><small>processando</small></span><span className={attention ? 'has-attention' : ''}><b>{attention}</b><small>requerem atenção</small></span><span><b>{Math.max(0, files.length - indexed - processing - attention)}</b><small>preservadas</small></span></div>}
    {!files.length && <div className="cadu-ds-project-state"><ProjectStateIllustration name="library-empty" alt="Arquivos e referências organizados em uma biblioteca"/><div><h3>Adicione material ao projeto</h3><p>Você escolhe depois o que deve ser indexado na base do Cadu.</p></div></div>}
    {processing > 0 && <div className="cadu-ds-project-state is-processing"><ProjectStateIllustration name="indexing-processing" alt="Documentos atravessando etapas de indexação"/><div><h3>Organizando o conhecimento</h3><p>{processing} fonte{processing === 1 ? ' está sendo preparada' : 's estão sendo preparadas'}.</p></div></div>}
    {!!files.length && <section className="cadu-ds-project-indexing__sources" aria-label="Fontes do projeto"><h2>Fontes</h2><ul>{files.map(file => { const category = TRIAGE_CATEGORIES.find(([key]) => key === file.category)?.[1] || 'Outro'; const status = file.requiresReview ? 'Aguardando revisão' : sourceStatus(file.status); const needsAttention = file.requiresReview || ['error','failed'].includes(file.status); return <li key={file.id} className={needsAttention ? 'has-attention' : ''}><span className="cadu-ds-project-indexing__file"><ProjectIcon name="source"/><span><span>{file.title || 'Arquivo sem nome'}</span><small>{category}</small></span></span><span className="cadu-ds-project-indexing__status">{status}</span>{needsAttention && <button type="button" onClick={onReview}>Revisar</button>}</li>; })}</ul></section>}
  </section>;
}

function ProjectStateIllustration({name, alt}) {
  return <img className="cadu-ds-project-state__illustration" src={`/static/images/cadu/project-states/${name}.png`} alt={alt} loading="lazy"/>;
}

function ProjectEditorialOverview({project, onEdit, canEdit}) {
  const customChapters = Object.entries(project.customFields || {}).map(([key, item]) => ({
    title:item?.label || key.replace(/_/g, ' '),
    text:Array.isArray(item?.value) ? item.value.join('\n') : item?.value,
    custom:true,
  }));
  const chapters = [
    {title: 'Público', text: project.identity?.publico},
    {title: 'Posicionamento', text: project.identity?.posicionamento},
    {title: 'Tom de voz', text: project.identity?.tom_de_voz},
    ...customChapters,
  ].filter(chapter => String(chapter.text || '').trim());
  const description = String(project.description || '').trim();
  const hasDirection = Boolean(description || chapters.length);
  const renderDirectionText = text => String(text || '').split(/\n\s*\n/).filter(Boolean).map((paragraph, index) => {
    const match = paragraph.trim().match(/^(.+?[.!?])(?:\s+)(.+)$/s);
    return <p key={`${index}-${paragraph.slice(0, 20)}`}>{match ? <><strong>{match[1]}</strong> {match[2]}</> : paragraph}</p>;
  });
  return <section className={`cadu-ds-project-editorial${hasDirection ? '' : ' is-empty'}`} id="direcao" aria-labelledby="project-editorial-title">
    <header><span>Direção do trabalho</span><h2 id="project-editorial-title">{hasDirection ? 'Direção do projeto' : 'Direção ainda não definida'}</h2>{description && <div className="cadu-ds-project-editorial__lead">{renderDirectionText(description)}</div>}</header>
    {chapters.length ? <div className="cadu-ds-project-editorial__chapters">{chapters.map((chapter, index) => <section key={`${chapter.title}-${index}`} className={chapter.custom ? 'is-custom' : ''}><h3>{chapter.title}</h3><div>{renderDirectionText(chapter.text)}</div></section>)}</div> : <p className="cadu-ds-project-editorial__empty">Adicione objetivo, público, posicionamento, tom de voz ou itens próprios deste projeto.</p>}
    <footer><span>{project.brand?.name ? `Identidade vinculada: ${project.brand.name}` : 'Marca ainda não vinculada'}</span>{canEdit && <button type="button" onClick={onEdit}>Editar direção</button>}</footer>
  </section>;
}

const SOURCE_ROLES = {brief:'Define o problema e os critérios do trabalho', research:'Sustenta decisões com pesquisa e evidências', media_plan:'Orienta canais, investimento e calendário', report:'Registra resultados e aprendizados', brand_asset:'Preserva a identidade da marca', reference:'Serve como referência para comparação', contract:'Registra limites e compromissos', spreadsheet:'Fornece dados estruturados para análise', other:'Complementa o contexto do projeto'};

function conversationPromptUrl(base, prompt) {
  try { const target = new URL(base, window.location.origin); target.searchParams.set('prompt', prompt); target.searchParams.set('auto_send', '1'); return `${target.pathname}${target.search}`; } catch (_) { return base; }
}

const EXPLORER_VIEWS = [['visual','Visual'], ['list','Lista'], ['time','Tempo']];
const itemDate = item => item.occurredAt || item.createdAt || item.updatedAt || item.created_at || item.updated_at || '';
const validDate = item => { const value = new Date(itemDate(item)); return Number.isNaN(value.getTime()) ? null : value; };
const dayKey = item => validDate(item)?.toISOString().slice(0, 10) || 'undated';
const dayLabel = item => { const date = validDate(item); return date ? new Intl.DateTimeFormat('pt-BR', {weekday:'long', day:'2-digit', month:'long'}).format(date) : 'Sem data registrada'; };
const itemTime = item => { const date = validDate(item); return date ? new Intl.DateTimeFormat('pt-BR', {hour:'2-digit', minute:'2-digit'}).format(date) : ''; };

const normalizeTask = item => ({...item, startsAt:item.startsAt || item.starts_at, dueAt:item.dueAt || item.due_at,
  completedAt:item.completedAt || item.completed_at, sourceProvider:item.sourceProvider || item.source_provider || 'cadu',
  assignee:item.assignee || {id:String(item.assignee_id || ''), name:item.assignee_name || ''},
  creator:item.creator || {id:String(item.created_by || ''), name:item.creator_name || ''},
  resourceRefs:item.resourceRefs || item.resource_refs || item.metadata?.resource_refs || [],
  evidence:item.evidence || item.metadata?.evidence || '', userInstruction:item.userInstruction || item.metadata?.user_instruction || ''});
const localDateTime = value => value ? new Date(new Date(value).getTime() - new Date(value).getTimezoneOffset()*60000).toISOString().slice(0,16) : '';
const isCanonicalResourceId = value => /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(String(value || ''));

function ProjectTasksSection({project, urls, csrfToken, canEdit}) {
  const [tasks, setTasks] = useState(() => (project.tasks || []).map(normalizeTask));
  const [showComposer, setShowComposer] = useState(false);
  const [draft, setDraft] = useState({title:'', starts_at:'', due_at:'', priority:'normal'});
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('open');
  const [editingId, setEditingId] = useState('');
  const [editDraft, setEditDraft] = useState(null);
  const [team, setTeam] = useState([]);
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const externalTasks = (project.links || []).filter(item => item.projectItemKind === 'task').map(item => ({...item, sourceProvider:item.provider || 'external', externalUrl:item.url, startsAt:item.occurredAt || '', dueAt:item.dueAt || ''}));
  const resourcesById = new Map((project.resources || []).map(item => [String(item.id), item]));
  const canonicalResources = (project.resources || []).filter(item => isCanonicalResourceId(item.id));
  const resourceHref = resource => { const target = new URL(window.location.href); target.searchParams.set('resource', resource.id); return `${target.pathname}${target.search}`; };
  const allTasks = [...tasks, ...externalTasks];
  const filteredTasks = allTasks.filter(task => {
    const statusMatches = statusFilter === 'all' || (statusFilter === 'open' ? task.status !== 'done' : task.status === statusFilter);
    const text = `${task.title || ''} ${task.description || ''} ${task.assignee?.name || ''}`.toLocaleLowerCase('pt-BR');
    return statusMatches && (!query.trim() || text.includes(query.trim().toLocaleLowerCase('pt-BR')));
  });
  useEffect(() => {
    if (!editingId || team.length || !urls.sharing) return;
    fetch(urls.sharing, {credentials:'same-origin', headers:{Accept:'application/json'}}).then(response => response.ok ? response.json() : Promise.reject()).then(value => setTeam(value.team || [])).catch(() => {});
  }, [editingId, team.length, urls.sharing]);
  const createTask = async event => {
    event.preventDefault(); setBusy(true); setError('');
    try {
      const payload = {...draft, starts_at:draft.starts_at ? new Date(draft.starts_at).toISOString() : '', due_at:draft.due_at ? new Date(draft.due_at).toISOString() : ''};
      const value = await request(urls.tasks, {method:'POST', headers:{'Content-Type':'application/json','X-CSRF-Token':csrfToken}, body:JSON.stringify(payload)});
      setTasks(current => [...current, normalizeTask(value.task)]); setDraft({title:'', starts_at:'', due_at:'', priority:'normal'});
    } catch (taskError) { setError(taskError.message); } finally { setBusy(false); }
  };
  const updateStatus = async (task, status) => {
    if (task.sourceProvider !== 'cadu') return;
    setBusy(true); setError('');
    try {
      const value = await request(`${urls.tasks}/${encodeURIComponent(task.id)}`, {method:'PATCH', headers:{'Content-Type':'application/json','X-CSRF-Token':csrfToken}, body:JSON.stringify({status})});
      setTasks(current => current.map(item => item.id === task.id ? normalizeTask(value.task) : item));
    } catch (taskError) { setError(taskError.message); } finally { setBusy(false); }
  };
  const beginEdit = task => {
    if (task.sourceProvider !== 'cadu') return;
    setEditingId(task.id); setNotice('');
    setEditDraft({title:task.title || '', description:task.description || '', status:task.status || 'todo', priority:task.priority || 'normal', starts_at:localDateTime(task.startsAt), due_at:localDateTime(task.dueAt), assignee_id:task.assignee?.id || '', evidence:task.evidence || '', resource_refs:task.resourceRefs || [], user_instruction:task.userInstruction || ''});
  };
  const saveEdit = async event => {
    event.preventDefault(); if (!editDraft || !editingId) return;
    setBusy(true); setError(''); setNotice('Salvando alterações…');
    try {
      const payload = {...editDraft, starts_at:editDraft.starts_at ? new Date(editDraft.starts_at).toISOString() : '', due_at:editDraft.due_at ? new Date(editDraft.due_at).toISOString() : '', assignee_id:editDraft.assignee_id || null};
      const value = await request(`${urls.tasks}/${encodeURIComponent(editingId)}`, {method:'PATCH', headers:{'Content-Type':'application/json','X-CSRF-Token':csrfToken}, body:JSON.stringify(payload)});
      setTasks(current => current.map(item => item.id === editingId ? normalizeTask(value.task) : item));
      setEditingId(''); setEditDraft(null); setNotice('Tarefa atualizada'); window.setTimeout(() => setNotice(''), 1800);
    } catch (taskError) { setError(taskError.message); setNotice(''); } finally { setBusy(false); }
  };
  return <section className={`cadu-ds-project-tasks${allTasks.length ? ' has-tasks' : ' is-empty'}`} id="tarefas">
    {!allTasks.length && project.tasksAvailable && <div className="cadu-ds-project-task-empty"><ProjectStateIllustration name="tasks-empty" alt="Fontes do projeto se transformando em tarefas relacionadas"/><div><h3>Transforme contexto em próximos passos</h3><p>O Cadu analisa o projeto, relaciona as fontes e propõe uma lista para sua revisão.</p></div>{canEdit && <div><button type="button" className="is-primary" onClick={() => window.location.assign(conversationPromptUrl(urls.conversation, 'Analise todo o contexto disponível deste projeto e proponha a primeira lista de tarefas. Para cada tarefa, explique a evidência e relacione as fontes canônicas do projeto que a sustentam. Use responsável e prazo somente quando estiverem confirmados. Mostre a lista para minha revisão, aceite minhas alterações e só depois da minha confirmação use projects.create_initial_task_list para criar a lista.'))}>Criar com o Cadu</button><button type="button" onClick={() => setShowComposer(true)}>Adicionar tarefa</button></div>}</div>}
    {canEdit && project.tasksAvailable && showComposer && <form className="cadu-ds-project-task-form" onSubmit={createTask}><input autoFocus={!allTasks.length} value={draft.title} onChange={event => setDraft(current => ({...current,title:event.target.value}))} placeholder="O que precisa ser feito?" required minLength="2" maxLength="180"/><label><span>Início</span><input type="datetime-local" value={draft.starts_at} onChange={event => setDraft(current => ({...current,starts_at:event.target.value}))}/></label><label><span>Prazo</span><input type="datetime-local" value={draft.due_at} onChange={event => setDraft(current => ({...current,due_at:event.target.value}))}/></label><select value={draft.priority} onChange={event => setDraft(current => ({...current,priority:event.target.value}))} aria-label="Prioridade"><option value="low">Baixa</option><option value="normal">Normal</option><option value="high">Alta</option></select><button className="is-primary" disabled={busy}>{busy ? 'Adicionando…' : 'Adicionar tarefa'}</button></form>}
    {!project.tasksAvailable && !allTasks.length && <div className="cadu-ds-project-task-empty is-unavailable"><ProjectStateIllustration name="tasks-empty" alt="Tarefas aguardando disponibilidade no projeto"/><div><h3>Organize os próximos passos</h3><p>A criação e o acompanhamento de tarefas ainda não estão habilitados neste ambiente. Você já pode planejar as ações em uma conversa com o Cadu.</p></div><div><button type="button" className="is-primary" onClick={() => window.location.assign(conversationPromptUrl(urls.conversation, 'Analise o contexto disponível deste projeto e ajude a organizar os próximos passos. Proponha tarefas com evidências e fontes, sem inventar responsáveis, prazos ou recursos.'))}>Planejar em conversa</button></div></div>}
    {allTasks.length > 0 && <div className="cadu-ds-project-task-toolbar"><div role="group" aria-label="Filtrar tarefas">{[['open','Abertas'],['todo','A fazer'],['in_progress','Em andamento'],['blocked','Bloqueadas'],['done','Concluídas'],['all','Todas']].map(([value,label]) => <button type="button" key={value} className={statusFilter === value ? 'is-active' : ''} onClick={() => setStatusFilter(value)}>{label}</button>)}</div><input type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Buscar tarefas" aria-label="Buscar tarefas"/>{canEdit && <button type="button" onClick={() => setShowComposer(value => !value)}>{showComposer ? 'Fechar criação' : 'Nova tarefa'}</button>}</div>}
    {notice && <p className="cadu-ds-project-task-notice" role="status">{notice}</p>}
    {error && <p className="cadu-ds-project-task-error" role="alert">{error}</p>}
    {filteredTasks.some(task => task.resourceRefs?.length) && <div className="cadu-ds-project-task-sources"><strong>Fontes dos próximos passos</strong>{filteredTasks.filter(task => task.resourceRefs?.length).map(task => <span key={`sources:${task.id}`}><b>{task.title}</b>{task.resourceRefs.map(ref => resourcesById.get(String(ref))).filter(Boolean).map(resource => <a key={resource.id} href={resourceHref(resource)}>{resource.title}</a>)}{task.evidence && <small>{task.evidence}</small>}</span>)}</div>}
    {allTasks.length > 0 && <div className="cadu-ds-project-task-layout"><div className="cadu-ds-project-task-list">{filteredTasks.map(task => <article key={`${task.sourceProvider}:${task.id}`} className={`is-${task.status || 'external'}${editingId === task.id ? ' is-editing' : ''}`}><button type="button" disabled={busy || task.sourceProvider !== 'cadu'} onClick={() => updateStatus(task, task.status === 'done' ? 'todo' : 'done')} aria-label={task.status === 'done' ? 'Reabrir tarefa' : 'Concluir tarefa'}>{task.status === 'done' ? '✓' : ''}</button><button type="button" className="cadu-ds-project-task-list__open" onClick={() => beginEdit(task)}><span><b>{task.title}</b><small>{task.assignee?.name || (task.sourceProvider === 'cadu' ? 'Sem responsável' : task.sourceProvider)}{task.dueAt ? ` · prazo ${new Intl.DateTimeFormat('pt-BR').format(new Date(task.dueAt))}` : ''}{task.resourceRefs?.length ? ` · ${task.resourceRefs.length} fonte${task.resourceRefs.length === 1 ? '' : 's'}` : ''}</small>{task.evidence && <em>{task.evidence}</em>}</span></button>{task.externalUrl && <a href={task.externalUrl} target="_blank" rel="noreferrer">Abrir</a>}{editingId === task.id && editDraft && <form className="cadu-ds-project-task-editor" onSubmit={saveEdit}><label>Título<input required minLength="2" maxLength="180" value={editDraft.title} onChange={event => setEditDraft(current => ({...current,title:event.target.value}))}/></label><label>Descrição<textarea rows="3" maxLength="4000" value={editDraft.description} onChange={event => setEditDraft(current => ({...current,description:event.target.value}))}/></label><div><label>Estado<select value={editDraft.status} onChange={event => setEditDraft(current => ({...current,status:event.target.value}))}><option value="todo">A fazer</option><option value="in_progress">Em andamento</option><option value="blocked">Bloqueada</option><option value="done">Concluída</option></select></label><label>Prioridade<select value={editDraft.priority} onChange={event => setEditDraft(current => ({...current,priority:event.target.value}))}><option value="low">Baixa</option><option value="normal">Normal</option><option value="high">Alta</option></select></label><label>Responsável<select value={editDraft.assignee_id} onChange={event => setEditDraft(current => ({...current,assignee_id:event.target.value}))}><option value="">Sem responsável</option>{team.filter(person => person.status !== false).map(person => <option key={person.id} value={person.id}>{person.name}</option>)}</select></label></div><div><label>Início<input type="datetime-local" value={editDraft.starts_at} onChange={event => setEditDraft(current => ({...current,starts_at:event.target.value}))}/></label><label>Prazo<input type="datetime-local" value={editDraft.due_at} onChange={event => setEditDraft(current => ({...current,due_at:event.target.value}))}/></label></div><label>Evidência<textarea rows="2" maxLength="2000" value={editDraft.evidence} onChange={event => setEditDraft(current => ({...current,evidence:event.target.value}))} placeholder="O que no contexto do projeto sustenta esta tarefa?"/></label>{canonicalResources.length > 0 && <fieldset className="cadu-ds-project-task-editor__sources"><legend>Fontes relacionadas <small>até 20</small></legend>{canonicalResources.map(resource => { const selected = editDraft.resource_refs.includes(resource.id); return <label key={resource.id}><input type="checkbox" checked={selected} disabled={!selected && editDraft.resource_refs.length >= 20} onChange={() => setEditDraft(current => ({...current,resource_refs:selected ? current.resource_refs.filter(id => id !== resource.id) : [...current.resource_refs, resource.id]}))}/><span><b>{resource.title}</b><small>{resource.kind || resource.resourceType || 'Fonte do projeto'}</small></span></label>; })}</fieldset>}<footer><button type="button" onClick={() => { setEditingId(''); setEditDraft(null); }}>Cancelar</button><button className="is-primary" disabled={busy}>{busy ? 'Salvando…' : 'Salvar alterações'}</button></footer></form>}</article>)}{!filteredTasks.length && <p className="cadu-ds-project-task-filter-empty">Nenhuma tarefa corresponde a este filtro.</p>}</div></div>}
  </section>;
}

function SourceActor({actor, compact = false}) {
  if (!actor?.name && !actor?.avatar) return null;
  const initials = String(actor.name || '').split(/\s+/).slice(0, 2).map(part => part[0]).join('').toUpperCase();
  return <span className={`cadu-ds-project-explorer__actor${compact ? ' is-compact' : ''}`}>{actor.avatar ? <img src={actor.avatar} alt=""/> : <i>{initials || 'U'}</i>}{!compact && <small>{actor.name}</small>}</span>;
}

function SourcePreview({item}) {
  const isExternal = ['reference', 'activity', 'task'].includes(item.sourceType);
  const image = isExternal ? dockProviderLogo(item.href || item.url) || item.iconUrl : item.previewUrl || (/^image\//i.test(item.mime || '') ? item.href : '');
  return <span className={`cadu-ds-project-explorer__preview is-${item.sourceType}`}>{isExternal ? <ProjectLinkImage src={image}/> : image ? <img src={image} alt="" loading="lazy"/> : <ProjectIcon name={item.sourceType === 'creation' ? 'image' : item.sourceType === 'summary' ? 'text' : 'source'}/>}<small>{isExternal ? item.sourceType === 'activity' ? 'ATIV.' : item.sourceType === 'task' ? 'TAREFA' : 'REF.' : (item.mime || item.kind || item.sourceType || 'ITEM').split('/').pop().slice(0, 8).toUpperCase()}</small></span>;
}

function SourceActions({item, conversationUrl, onManage, onInspect, onEditContext}) {
  const contextItem = item.sourceType === 'context';
  const editContext = onEditContext || item.editContext;
  const askUrl = conversationPromptUrl(conversationUrl, contextItem
    ? `Considere o campo "${item.title}" da direção deste projeto, cujo valor atual é "${item.detail}". Ajude-me a revisar ou aprimorar esse dado sem alterá-lo até eu confirmar.`
    : `Use a fonte "${item.title}" deste projeto para responder minha próxima dúvida. Primeiro resuma o papel dela no projeto e indique se a indexação está pronta.`);
  return <span className="cadu-ds-project-explorer__actions"><button type="button" onClick={() => onInspect?.(item)}>Detalhes</button><a href={askUrl}>Perguntar</a>{contextItem ? editContext && <button type="button" onClick={editContext}>Editar direção</button> : ['file','reference','activity','task'].includes(item.sourceType) && <button type="button" onClick={onManage}>{item.requiresReview ? 'Definir e indexar' : 'Alterar papel'}</button>}{item.href && <a href={item.href}>Abrir</a>}</span>;
}

function ProjectSourceExplorer({project, conversationUrl, activityHref, onManage, onAddNote, onAddLink, onEditContext, canEdit, currentUser}) {
  const preferenceKey = `cadu-project-explorer:${project.id || 'project'}`;
  const [view, setView] = useState(() => { try { const saved = localStorage.getItem(preferenceKey); return saved === 'activity' ? 'visual' : saved || 'visual'; } catch (_) { return 'visual'; } });
  const [query, setQuery] = useState('');
  const [type, setType] = useState('all');
  const [selected, setSelected] = useState(null);
  useEffect(() => { try { localStorage.setItem(preferenceKey, view); } catch (_) {} }, [preferenceKey, view]);
  const withActor = item => item.actor || (item.createdBy && String(item.createdBy) === String(currentUser?.id) ? {name:currentUser.name, avatar:currentUser.avatar} : null);
  const items = [
    ...(project.contextItems || []).map(item => ({...item, title:item.label, detail:item.display_value,
      id:item.id, sourceType:'context', role:'brief', status:'completed', updatedAt:item.updated_at,
      editContext:canEdit ? onEditContext : undefined})),
    ...(project.files || []).map(item => ({...item, actor:withActor(item), sourceType:'file', role:item.category || 'other'})),
    ...(project.links || []).filter(item => !['activity','task'].includes(item.projectItemKind)).map(item => ({...item, id:`link:${item.id}`, title:projectLinkTitle(item), href:item.url,
      sourceType:'reference', role:item.category || 'reference', status:'completed'})),
    ...(project.artifacts || []).map(item => ({...item, id:`artifact:${item.id}`, sourceType:'summary', role:'report', status:item.status || 'completed'})),
    ...(project.deliveries || []).map(item => ({...item, id:`delivery:${item.id}`, sourceType:/imagem|vídeo|criativo/i.test(item.kind || '') ? 'creation' : 'summary', role:'report', status:item.status || 'completed'})),
  ].sort((a, b) => (validDate(b)?.getTime() || 0) - (validDate(a)?.getTime() || 0));
  const normalizedQuery = normalizeProjectSearch(query.trim());
  const visibleItems = items.filter(item => (type === 'all' || item.sourceType === type) && (!normalizedQuery || normalizeProjectSearch(`${item.title || ''} ${item.detail || ''} ${SOURCE_ROLES[item.role] || ''}`).includes(normalizedQuery)));
  const groups = visibleItems.reduce((result, item) => { const key = dayKey(item); (result[key] ||= []).push(item); return result; }, {});
  const dates = Array.from({length:7}, (_, index) => { const date = new Date(); date.setDate(date.getDate() - (6 - index)); return date; });
  const lanes = [['context','Direção'], ['file','Arquivos'], ['reference','Referências'], ['creation','Criações'], ['summary','Resumos e entregas']];
  const visualItem = item => <article key={item.id} className={`cadu-ds-project-explorer__visual-item${selected?.id === item.id ? ' is-selected' : ''}`}><SourcePreview item={item}/><div><small>{item.sourceType === 'context' ? 'Direção' : TRIAGE_CATEGORIES.find(option => option[0] === item.role)?.[1] || item.kind || 'Conteúdo'}</small><h3>{item.title || 'Item sem título'}</h3><p>{item.sourceType === 'context' ? item.detail : SOURCE_ROLES[item.role] || item.detail || SOURCE_ROLES.other}</p><footer><span>{item.sourceType === 'context' ? `Revisão ${item.revision}` : `${itemTime(item)}${item.status && ` · ${sourceStatus(item.status)}`}`}</span><SourceActions item={item} conversationUrl={conversationUrl} onManage={onManage} onEditContext={canEdit ? onEditContext : undefined} onInspect={setSelected}/></footer></div></article>;
  return <section className="cadu-ds-project-explorer" id="fontes"><header className="cadu-ds-project-explorer__header"><span>{items.length ? `${items.length} item${items.length === 1 ? '' : 's'} no projeto` : 'Biblioteca vazia'}</span><div><a href={activityHref}>Atividade</a>{canEdit && <button type="button" onClick={onAddNote}>Adicionar nota</button>}{canEdit && <button type="button" onClick={onAddLink}>Adicionar link</button>}{canEdit && <button type="button" className="is-primary" onClick={onManage}>Adicionar fonte</button>}</div></header>
    <div className="cadu-ds-project-explorer__toolbar"><nav aria-label="Visualização do projeto">{EXPLORER_VIEWS.map(([id,label]) => <button type="button" key={id} className={view === id ? 'is-active' : ''} onClick={() => setView(id)}>{label}</button>)}</nav><div className="cadu-ds-project-explorer__filters"><input type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Buscar no projeto" aria-label="Buscar na direção, arquivos e referências"/><select value={type} onChange={event => setType(event.target.value)} aria-label="Filtrar por tipo"><option value="all">Todos os tipos</option><option value="context">Direção</option><option value="file">Arquivos</option><option value="reference">Referências</option><option value="creation">Criações</option><option value="summary">Resumos e entregas</option></select><span>{visibleItems.length}/{items.length}</span></div></div>
    {!items.length ? <div className="cadu-ds-project-explorer__empty"><ProjectStateIllustration name="library-empty" alt="Biblioteca pronta para receber fontes do projeto"/><h3>Adicione a primeira fonte</h3><div>{canEdit && <><button type="button" onClick={onManage}>Arquivo</button><button type="button" onClick={onAddNote}>Nota</button><button type="button" onClick={onAddLink}>Link</button></>}</div></div> : !visibleItems.length ? <div className="cadu-ds-project-explorer__empty"><h3>Nenhum resultado</h3><p>Altere a busca ou o tipo de conteúdo.</p><button type="button" onClick={() => { setQuery(''); setType('all'); }}>Limpar filtros</button></div> : view === 'time' ? <div className="cadu-ds-project-explorer__time"><header><span>Grupo</span>{dates.map(date => <time key={date.toISOString()}>{new Intl.DateTimeFormat('pt-BR',{weekday:'short'}).format(date)}<b>{date.getDate()}</b></time>)}</header>{lanes.filter(([laneType]) => type === 'all' || type === laneType).map(([laneType,label]) => <div className="cadu-ds-project-explorer__lane" key={laneType}><b>{label}</b>{dates.map(date => { const key = date.toISOString().slice(0,10); const matched = visibleItems.filter(item => item.sourceType === laneType && dayKey(item) === key); return <span key={key}>{matched.slice(0,3).map(item => <button type="button" title={item.title} key={item.id} onClick={() => setSelected(item)}><ProjectIcon name={laneType === 'creation' ? 'image' : laneType === 'reference' ? 'spark' : laneType === 'summary' ? 'text' : 'source'}/></button>)}</span>; })}</div>)}</div> : <div className={`cadu-ds-project-explorer__groups is-${view}`}>{Object.entries(groups).map(([key, dayItems]) => { const actors = dayItems.map(item => item.actor).filter((actor, index, all) => actor?.name && all.findIndex(entry => entry?.name === actor.name) === index); return <section key={key}><header><div><h3>{dayLabel(dayItems[0])}</h3><span>{dayItems.length} item{dayItems.length === 1 ? '' : 's'}</span></div>{actors.length > 0 && <div className="cadu-ds-project-explorer__actors" aria-label="Pessoas que contribuíram neste dia">{actors.slice(0,3).map(actor => <SourceActor key={actor.name} actor={actor} compact/>)}{actors.length > 3 && <small>+{actors.length - 3}</small>}</div>}</header>{view === 'visual' ? <div className="cadu-ds-project-explorer__visual">{dayItems.map(visualItem)}</div> : <div className={`cadu-ds-project-explorer__rows is-${view}`}>{dayItems.map((item, index) => <article key={item.id}><time>{itemTime(item)}</time><SourcePreview item={item}/><span><b>{item.title || 'Item sem título'}</b><small>{SOURCE_ROLES[item.role] || item.detail || 'Conteúdo do projeto'}</small></span>{view === 'list' && <em>{sourceStatus(item.status || 'completed')}</em>}{item.actor?.name && (index === 0 || dayItems[index - 1]?.actor?.name !== item.actor.name) && <SourceActor actor={item.actor}/>}<SourceActions item={item} conversationUrl={conversationUrl} onManage={onManage} onInspect={setSelected}/></article>)}</div>}</section>; })}</div>}
    {selected && <aside className="cadu-ds-project-explorer__inspector" aria-label={`Detalhes de ${selected.title}`}><button type="button" onClick={() => setSelected(null)} aria-label="Fechar detalhes">×</button><SourcePreview item={selected}/><div><small>{selected.sourceType === 'context' ? 'Direção do projeto' : selected.sourceType === 'file' ? selected.mime : selected.kind || selected.sourceType}</small><h3>{selected.title}</h3><p>{selected.sourceType === 'context' ? selected.detail : SOURCE_ROLES[selected.role] || selected.detail || SOURCE_ROLES.other}</p><dl>{selected.sourceType === 'context' ? <><div><dt>Tipo</dt><dd>{selected.field_kind === 'custom' ? 'Item personalizado' : 'Campo padrão'}</dd></div><div><dt>Revisão</dt><dd>{selected.revision}</dd></div></> : <><div><dt>Papel</dt><dd>{TRIAGE_CATEGORIES.find(option => option[0] === selected.role)?.[1] || 'Outro'}</dd></div><div><dt>Indexação</dt><dd>{sourceStatus(selected.status || 'completed')}</dd></div>{itemDate(selected) && <div><dt>Adicionado</dt><dd>{dayLabel(selected)}</dd></div>}</>}</dl><SourceActor actor={selected.actor}/><SourceActions item={selected} conversationUrl={conversationUrl} onManage={onManage} onEditContext={onEditContext}/></div></aside>}
  </section>;
}

function ProjectPageIntro({title, detail, action}) {
  return <header className="cadu-ds-project-page-intro"><div><h1>{title}</h1><p>{detail}</p></div>{action}</header>;
}

function ProjectActivityPage({project}) {
  const activity = project.activity || [];
  return <section className="cadu-ds-project-activity-page"><ProjectPageIntro title="Atividade" detail="Mudanças e contribuições deste projeto."/>{activity.length ? <div className="cadu-ds-project-activity-feed">{activity.map(item => <article key={item.id}><i aria-hidden="true"/><div><b>{item.title}</b><p>{item.detail}</p><small>{item.actor?.name || item.origin || 'Projeto'}{item.occurredAt ? ` · ${new Intl.DateTimeFormat('pt-BR',{dateStyle:'medium',timeStyle:'short'}).format(new Date(item.occurredAt))}` : ''}</small></div>{item.resourceUrl && <a href={item.resourceUrl}>Abrir</a>}</article>)}</div> : <div className="cadu-ds-project-quiet-empty"><ProjectStateIllustration name="activity-empty" alt="Linha do tempo aguardando as primeiras atividades do projeto"/><h2>A atividade começa aqui</h2><p>Mudanças em tarefas, fontes e entregas aparecerão neste espaço.</p></div>}</section>;
}

function ProjectDeliveriesPage({project, onStartConversation}) {
  const items = [...(project.artifacts || []), ...(project.deliveries || [])];
  return <section><ProjectPageIntro title="Artefatos e entregas" detail="Tudo o que foi produzido neste projeto." action={<button type="button" className="is-primary" onClick={onStartConversation}>Criar no projeto</button>}/>{items.length ? <div className="cadu-ds-project-delivery-list">{items.map(item => <a key={item.id} href={item.href || '#'}><ProjectIcon name={artifactIconName(item.kind)}/><span><b>{item.title}</b><small>{item.detail || item.status || item.kind}</small></span><i>›</i></a>)}</div> : <div className="cadu-ds-project-quiet-empty"><ProjectStateIllustration name="deliveries-empty" alt="Área preparada para receber artefatos e entregas"/><h2>Nenhuma entrega ainda</h2><p>Crie com o Cadu e salve o resultado no projeto.</p><button type="button" onClick={onStartConversation}>Começar uma conversa</button></div>}</section>;
}

function ProjectViewsPage({onStartConversation}) {
  return <section><ProjectPageIntro title="Visualizações" detail="Leituras dos dados conectados ao projeto."/><div className="cadu-ds-project-quiet-empty"><ProjectStateIllustration name="views-empty" alt="Blocos de dados formando uma visualização do projeto"/><h2>Crie uma visualização</h2><p>Descreva a leitura de prazos, campanhas ou resultados que você precisa.</p><button type="button" onClick={onStartConversation}>Descrever visualização</button></div></section>;
}

export function WorkspaceProject({bootstrap}) {
  const {isMobile} = useWorkspaceViewport();
  const [linkIcons, setLinkIcons] = useState({});
  const project = {...(bootstrap.project || {}), links:(bootstrap.project?.links || []).map(link => ({...link, ...(linkIcons[String(link.id)] || {})}))};
  const actionParams = new URLSearchParams(window.location.search);
  const requestedAction = actionParams.get('acao');
  const initialMergeTarget = actionParams.get('destino') || '';
  const canEdit = project.status !== 'arquivado';
  const [dialog, setDialog] = useState(() => !canEdit ? '' : requestedAction === 'mesclar' ? 'merge' : requestedAction === 'excluir' ? 'delete-project' : '');
  const [dropActive, setDropActive] = useState(false);
  const [dropQueue, setDropQueue] = useState([]);
  const dragDepth = useRef(0);
  const [resourceId, setResourceId] = useState(() => new URLSearchParams(window.location.search).get('resource') || '');
  const [accountOpen, setAccountOpen] = useState(false);
  const [sharing, setSharing] = useState(project.sharing || {});
  const [projectLinksPinned, setProjectLinksPinned] = useState(() => project.links || []);
  const [linkOrderStatus, setLinkOrderStatus] = useState('');
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [remoteNotifications, setRemoteNotifications] = useState([]);
  const initialDockItems = bootstrap.dock?.items || [];
  const [dockItems, setDockItems] = useState(initialDockItems);
  const missing = project.health?.missing || [];
  const isNewProject = missing.length >= 3 && !(project.files?.length || project.deliveries?.length || project.memory?.length || project.links?.length);
  const projectLinks = bootstrap.projectLinks || {};
  const projectView = bootstrap.projectView || 'overview';
  useEffect(() => {
    if (!project.id) return undefined;
    const pending = (bootstrap.project?.links || []).filter(link => !dockProviderLogo(link.url) && !link.iconUrl && (!link.iconStatus || ['queued','running','generating','failed'].includes(link.iconStatus)));
    let active = true;
    const token = bootstrap.csrf || csrf();
    const requestMissing = async () => {
      for (const link of pending) {
        if (!active) return;
        setLinkIcons(current => ({...current, [String(link.id)]:{iconStatus:'queued'}}));
        try {
          const response = await fetch(`/projetos/${encodeURIComponent(project.id)}/atalhos/${encodeURIComponent(link.id)}/icone`, {
            method:'POST', credentials:'same-origin', headers:{'X-CSRF-Token':token, Accept:'application/json'},
          });
          if (!response.ok) throw new Error('icon unavailable');
          const result = await response.json();
          if (active && result.status === 'ready') setLinkIcons(current => ({...current, [String(link.id)]:{iconUrl:result.icon_url, iconStatus:'ready'}}));
          else if (active && result.status === 'failed') setLinkIcons(current => ({...current, [String(link.id)]:{iconStatus:'failed'}}));
          else if (active && result.status) setLinkIcons(current => ({...current, [String(link.id)]:{iconStatus:result.status}}));
        } catch (_) {
          if (active) setLinkIcons(current => ({...current, [String(link.id)]:{iconStatus:'failed'}}));
        }
      }
    };
    requestMissing();
    const timer = window.setInterval(requestMissing, 300000);
    return () => { active = false; window.clearInterval(timer); };
  }, [project.id, bootstrap.project?.links, bootstrap.csrf]);
  useEffect(() => {
    if (!project.id || !project.links?.some(link => ['queued','running','generating'].includes(link.iconStatus))) return undefined;
    let active = true;
    const refresh = async () => {
      try {
        const response = await fetch(`/projetos/${encodeURIComponent(project.id)}/atalhos/icones`, {credentials:'same-origin', headers:{Accept:'application/json'}});
        if (!response.ok) return;
        const data = await response.json();
        if (active) setLinkIcons(current => {
          const next = {...current};
          for (const icon of data.icons || []) if (icon.iconStatus) next[String(icon.id)] = {iconUrl:icon.iconUrl, iconStatus:icon.iconStatus};
          return next;
        });
      } catch (_) { /* Neutral link icons stay visible during a temporary outage. */ }
    };
    const timer = window.setInterval(refresh, 4000);
    refresh();
    return () => { active = false; window.clearInterval(timer); };
  }, [project.id, project.links?.some(link => ['queued','running','generating'].includes(link.iconStatus))]);
  const startConversation = () => window.location.assign(projectLinks.conversation);
  const reorderProjectLinks = async next => {
    const before = projectLinksPinned;
    setProjectLinksPinned(next);
    setLinkOrderStatus('Salvando ordem…');
    try {
      await request(projectLinks.orderLinks, {method:'POST', headers:{'Content-Type':'application/json','X-CSRF-Token':bootstrap.csrf || csrf()}, body:JSON.stringify({ids:next.map(item => item.id)})});
      setLinkOrderStatus('Ordem salva');
      window.setTimeout(() => setLinkOrderStatus(''), 1800);
    } catch (orderError) {
      setProjectLinksPinned(before);
      setLinkOrderStatus(orderError.message || 'Não foi possível salvar a ordem.');
    }
  };
  const selectedResource = (project.resources || []).find(item => String(item.id) === String(resourceId));
  const hasFiles = event => Array.from(event.dataTransfer?.types || []).includes('Files');
  const handleDragEnter = event => {
    if (!hasFiles(event)) return;
    event.preventDefault();
    dragDepth.current += 1;
    setDropActive(true);
  };
  const handleDragOver = event => {
    if (!hasFiles(event)) return;
    event.preventDefault();
    if (event.dataTransfer) event.dataTransfer.dropEffect = 'copy';
  };
  const handleDragLeave = event => {
    if (!hasFiles(event)) return;
    event.preventDefault();
    dragDepth.current = Math.max(0, dragDepth.current - 1);
    if (dragDepth.current === 0) setDropActive(false);
  };
  const handleFileDrop = event => {
    if (!hasFiles(event)) return;
    event.preventDefault();
    dragDepth.current = 0;
    setDropActive(false);
    const files = Array.from(event.dataTransfer?.files || []);
    if (files.length) {
      setDropQueue(files);
      setDialog('source-upload');
    }
  };
  useEffect(() => {
    const strip = document.querySelector('.cadu-ds-project-resource-strip');
    if (!strip) return undefined;
    const buttons = Array.from(strip.querySelectorAll('button'));
    buttons.forEach(button => { button.draggable = true; });
    const handleDragStart = event => {
      const title = event.target.closest('button')?.textContent?.trim();
      const resource = (project.resources || []).find(item => item.title === title);
      if (resource) writeDockResourcePayload(event, resource, project.id);
    };
    strip.addEventListener('dragstart', handleDragStart);
    return () => strip.removeEventListener('dragstart', handleDragStart);
  }, [project.id, project.resources]);
  useEffect(() => {
    if (!projectLinks.notifications) return undefined;
    const controller = new AbortController();
    const target = new URL(projectLinks.notifications, window.location.origin);
    target.searchParams.set('project_ref', `ci:${project.id}`);
    fetch(`${target.pathname}${target.search}`, {credentials:'same-origin', signal:controller.signal, headers:{Accept:'application/json'}})
      .then(response => response.ok ? response.json() : Promise.reject(new Error('notifications unavailable')))
      .then(value => setRemoteNotifications(value.items || []))
      .catch(() => {});
    return () => controller.abort();
  }, [project.id, projectLinks.notifications]);
  const addDockResource = async payload => {
    if (!payload?.resourceRef || dockItems.some(item => item.resourceRef === payload.resourceRef && item.shortcutId)) return;
    try {
      const endpoint = bootstrap.endpoints?.dockShortcuts || '/workspace/api/dock/shortcuts';
      const data = await request(endpoint, {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'X-CSRF-Token': bootstrap.csrf || csrf()},
        body: JSON.stringify({shortcut_type: 'resource', target_ref: payload.resourceRef, project_ref: payload.projectRef, metadata: {title: payload.title, resource_type: payload.resourceType}}),
      });
      setDockItems(items => [...items, {...payload, shortcutId: data.shortcut?.id, pinned: true}]);
    } catch (_) {
      // The dock remains usable if a resource shortcut cannot be saved.
    }
  };
  const sectionLinks = projectLinks.sections || {};
  const projectNav = [
    {id:'overview', label:'Visão geral', icon:'home', href:sectionLinks.overview},
    {id:'direction', label:'Direção', icon:'compose', href:sectionLinks.direction},
    {id:'tasks', label:'Tarefas', icon:'plan', href:sectionLinks.tasks, count:(project.tasks || []).filter(item => item.status !== 'done').length},
    {id:'activity', label:'Atividade', icon:'pulse', href:sectionLinks.activity},
    {id:'library', label:'Biblioteca', icon:'file', href:sectionLinks.library},
    {id:'indexing', label:'Indexação', icon:'history', href:sectionLinks.indexing, count:(project.files || []).filter(item => ['error','failed'].includes(item.status)).length},
    {id:'conversations', label:'Conversas', icon:'conversation', href:sectionLinks.conversations},
    {id:'deliveries', label:'Artefatos e entregas', icon:'external', href:sectionLinks.deliveries},
    {id:'views', label:'Visualizações', icon:'analysis', href:sectionLinks.views},
  ];
  const derivedNotifications = [
    ...(project.files || []).filter(item => item.requiresReview || ['error', 'failed'].includes(item.status)).map(item => ({id:`source:${item.id}`, kind:item.requiresReview ? 'approval' : 'attention', title:item.requiresReview ? `Defina o papel de ${item.title}` : `Revise ${item.title}`, detail:item.requiresReview ? 'A fonte foi preparada e aguarda sua decisão para entrar na base.' : 'A indexação não foi concluída.', context:project.name, action:'sources'})),
    ...(project.activity || []).slice(0, 6).map((item, index) => ({id:`activity:${index}:${item.title}`, kind:'complete', title:item.title, detail:item.detail, context:project.name, action:'activity'})),
  ];
  const notifications = [...remoteNotifications, ...derivedNotifications.filter(item => !remoteNotifications.some(remote => remote.sourceId && String(remote.sourceId) === String(item.id).replace(/^source:/, '')))];
  const actionableNotifications = notifications.filter(item => ['approval','attention','failure'].includes(item.kind) && !['read','resolved','archived'].includes(item.status));
  const openNotification = async item => {
    setNotificationsOpen(false);
    if (item.id && projectLinks.notifications && /^[0-9a-f-]{36}$/i.test(String(item.id))) {
      fetch(`${projectLinks.notifications}/${item.id}/read`, {method:'POST', credentials:'same-origin', headers:{Accept:'application/json','X-CSRF-Token':bootstrap.csrf || csrf()}}).catch(() => {});
      setRemoteNotifications(current => current.map(entry => entry.id === item.id ? {...entry, status:entry.status === 'unread' ? 'read' : entry.status} : entry));
    }
    if (item.action === 'sources' || item.sourceId) setDialog('source-upload');
    else if (item.conversationId) window.location.assign(`${projectLinks.conversation}${projectLinks.conversation.includes('?') ? '&' : '?'}conversation_id=${encodeURIComponent(item.conversationId)}`);
    else document.querySelector('#atividade')?.scrollIntoView({behavior:'smooth'});
  };
  return <div className={`cadu-ds-home-shell cadu-ds-project-shell is-editorial${isNewProject ? ' is-new-project' : ''}`}>
    <main className="cadu-ds-home-main">
      <div className="cadu-ds-home-workarea cadu-ds-project-workarea" onDragEnter={handleDragEnter} onDragOver={handleDragOver} onDragLeave={handleDragLeave} onDrop={handleFileDrop}>
        {dropActive && <div className="cadu-ds-project-page-drop" role="status" aria-live="polite"><div className="cadu-ds-project-page-drop__card"><span className="cadu-ds-project-page-drop__icon"><ProjectIcon name="source"/></span><strong>Solte para adicionar ao projeto</strong><span>O arquivo será preservado e revisado antes de entrar na base do Cadu.</span></div></div>}
        {isMobile ? <WorkspaceMobileChrome eyebrow="Projeto" title={project.name || 'Projeto'} links={bootstrap.urls} contextItems={(project.resources || []).map(item => ({...item, detail:item.type || 'Conteúdo do projeto'}))}/> : <CaduDock bootstrap={bootstrap} logo={bootstrap.caduMark} homeUrl={bootstrap.urls.home} userName={bootstrap.user?.name} userAvatar={bootstrap.user?.avatar} userInitials={bootstrap.user?.name?.slice(0, 2).toUpperCase()} accountOpen={accountOpen} accountMenu={<WorkspaceAccountMenu open={accountOpen} onClose={() => setAccountOpen(false)} user={bootstrap.user} links={bootstrap.urls} projects={bootstrap.projects || []} brands={bootstrap.brands || []} usagePercent={bootstrap.usagePercent} onManageShortcuts={() => window.location.assign(`${bootstrap.urls.home}#atalhos`)}/>} onOpenAccount={() => setAccountOpen(current => !current)} brands={bootstrap.brands || []} resources={bootstrap.projects || []} shortcutItems={dockItems.map(item => ({...item, active: (item.kind === 'project' && String(item.projectRef || '') === `ci:${project.id}`) || (item.kind === 'brand' && String(item.brandRef || '') === `studio:${project.brand?.id || ''}`)}))} onDropItem={addDockResource} usagePercent={bootstrap.usagePercent} onNewConversation={startConversation} onOpenBrand={openWorkspaceDetail} onOpenResource={openWorkspaceDetail} onOpenUsage={() => setAccountOpen(true)}/>}<div className="cadu-ds-entity-portal cadu-ds-entity-portal--project">
        <EntityNavigator label={project.name || 'Projeto'} items={projectNav} activeId={projectView} identity={<span><small>Projeto</small><b title={project.name}>{project.name}</b></span>}>
          <span>Trabalhar no projeto</span>
          <button type="button" className="is-primary" onClick={startConversation}><ProjectIcon name="compose"/> Conversar no projeto</button>
          {canEdit && <button type="button" onClick={() => setDialog('identity')}><ProjectIcon name="text"/> Editar contexto</button>}
          {canEdit && <details className="cadu-ds-entity-nav__source-menu"><summary><ProjectIcon name="source"/> Adicionar ao projeto</summary><div><button type="button" onClick={() => setDialog('source-upload')}>Adicionar fonte</button><button type="button" onClick={() => setDialog('note')}>Adicionar nota</button><button type="button" onClick={() => setDialog('link')}>Adicionar link</button></div></details>}
          <details className="cadu-ds-entity-nav__source-menu"><summary>Mais ações</summary><div>{bootstrap.canManageSharing && <button type="button" onClick={() => setDialog('sharing')}>Gerenciar acesso</button>}<a href={projectLinks.createPlan}>Criar plano de mídia</a><a href={projectLinks.createImage}>Criar imagem</a><a href={projectLinks.createVideo}>Criar vídeo</a>{canEdit && <form method="post" action={projectLinks.toggleStatus}><input type="hidden" name="_csrf" value={bootstrap.csrf}/><button type="submit">{project.status === 'arquivado' ? 'Reativar projeto' : 'Arquivar projeto'}</button></form>}{bootstrap.canManageProjects && <><button type="button" onClick={() => setDialog('merge')}>Mesclar com outro projeto</button><button type="button" className="is-danger" onClick={() => setDialog('delete-project')}>Excluir projeto</button></>}</div></details>
        </EntityNavigator>
        <section className="cadu-ds-project-content" data-project-view={projectView}>
        {projectView === 'overview' && <><header className="cadu-ds-project-hero cadu-ds-entity-detail-header"><div className="cadu-ds-project-hero__copy"><p>{project.status === 'arquivado' ? 'Arquivado' : 'Em andamento'}</p><ProjectTitle name={project.name}/><div className="cadu-ds-project-hero__meta">{project.brand?.name && <a href={project.brand.href}>{project.brand.name}</a>}{(project.tasks || []).length > 0 && <a href={sectionLinks.tasks}>{(project.tasks || []).filter(item => item.status !== 'done').length} tarefas abertas</a>}</div></div>{actionableNotifications.length > 0 && <button type="button" className="cadu-ds-project-hero__attention" onClick={() => setNotificationsOpen(true)}>{actionableNotifications.length} atenç{actionableNotifications.length === 1 ? 'ão' : 'ões'}</button>}</header><ProjectEditorialOverview project={project} canEdit={canEdit} onEdit={() => setDialog('identity')}/>{(project.tasks || []).length > 0 && <div className="cadu-ds-project-overview-link"><span><b>{(project.tasks || []).filter(item => item.status !== 'done').length} tarefas abertas</b><small>Veja responsáveis, prazos e próximos passos.</small></span><a href={sectionLinks.tasks}>Abrir tarefas</a></div>}</>}
        {projectView === 'direction' && <><ProjectPageIntro title="Direção" detail="Contexto para conversas e entregas."/><ProjectEditorialOverview project={project} canEdit={canEdit} onEdit={() => setDialog('identity')}/></>}
        {projectView === 'tasks' && <><ProjectPageIntro title="Tarefas" detail="Ações do Cadu e da equipe."/><ProjectTasksSection project={project} urls={projectLinks} csrfToken={bootstrap.csrf} canEdit={canEdit}/></>}
        {projectView === 'activity' && <ProjectActivityPage project={project}/>}
        {projectView === 'library' && <><ProjectPageIntro title="Biblioteca" detail="Arquivos, links e notas."/><ProjectSourceExplorer project={project} conversationUrl={projectLinks.conversation} activityHref={sectionLinks.activity} currentUser={bootstrap.user} canEdit={canEdit} onManage={() => setDialog('source-upload')} onAddNote={() => setDialog('note')} onAddLink={() => setDialog('link')} onEditContext={() => setDialog('identity')}/></>}
        {projectView === 'indexing' && <><ProjectPageIntro title="Indexação" detail="Fontes e estado da indexação."/><ProjectIndexingSection files={project.files || []} onReview={() => setDialog('source-upload')} onAddLink={() => setDialog('link')}/></>}
        {projectView === 'conversations' && <><ProjectPageIntro title="Conversas" detail="Histórico deste projeto." action={<button type="button" className="is-primary" onClick={startConversation}>Nova conversa</button>}/><ProjectMemorySection project={project} reviewBase={projectLinks.reviewMemoryBase} csrfToken={bootstrap.csrf || csrf()} canEdit={canEdit}/><ProjectContinuitySection project={project} onStartConversation={startConversation}/></>}
        {projectView === 'deliveries' && <ProjectDeliveriesPage project={project} onStartConversation={startConversation}/>}
        {projectView === 'views' && <ProjectViewsPage onStartConversation={startConversation}/>}
        {project.status === 'arquivado' && <aside className="cadu-ds-project-notice"><b>Este projeto está arquivado.</b><span>O contexto permanece disponível para consulta. Para reativar, use Mais ações.</span></aside>}
        </section>
        <EntityContextRail title="Projeto agora" primaryGroup={{title:'Links do projeto', items:projectLinksPinned.map(item => ({...item, title:projectLinkTitle(item), href:item.url, external:true, detail:''})), maxVisible:10, moreHref:sectionLinks.library, moreLabel:'Ver todos os links', prominent:true, onReorder:canEdit ? reorderProjectLinks : undefined}}><div id="marca"><ProjectBrandCard brand={project.brand} urls={projectLinks} canEdit={canEdit} canManageBrand={bootstrap.canManageBrand} onDialog={setDialog}/></div>{linkOrderStatus && <p className={`cadu-ds-entity-rail__feedback${/não|falh|erro/i.test(linkOrderStatus) ? ' is-error' : ''}`} role={/não|falh|erro/i.test(linkOrderStatus) ? 'alert' : 'status'}>{linkOrderStatus}</p>}<div className="cadu-ds-entity-rail__index"><span>Indexação</span><strong>{(project.files || []).filter(item => item.status === 'completed').length}/{(project.files || []).length}</strong><small>fontes prontas</small><a href={sectionLinks.indexing}>Ver detalhes</a></div></EntityContextRail>
        </div>
      </div>
    </main>
    {dialog === 'sharing' && <SharingDialog project={{...project, sharing}} urls={projectLinks} csrfToken={bootstrap.csrf} onSaved={setSharing} onClose={() => setDialog('')} />}
    {(dialog === 'merge' || dialog === 'delete-project') && <ProjectManagementDialog
      project={project} projects={bootstrap.projects || []} urls={projectLinks}
      csrfToken={bootstrap.csrf} mode={dialog === 'merge' ? 'merge' : 'delete'}
      initialTargetId={initialMergeTarget} onClose={() => setDialog('')}
    />}
    {notificationsOpen && <WorkspaceNotificationCenter items={notifications} onClose={() => setNotificationsOpen(false)} onOpenItem={openNotification}/>} {canEdit && dialog === 'identity' && <IdentityDialog project={project} urls={projectLinks} csrfToken={bootstrap.csrf} onClose={() => setDialog('')}/>} {dialog === 'brand-picker' && <BrandPickerDialog brands={bootstrap.brands || []} currentBrandId={project.brand?.id} urls={projectLinks} csrfToken={bootstrap.csrf} canManageBrand={bootstrap.canManageBrand} onCreate={() => setDialog('brand-import')} onClose={() => setDialog('')}/>} {dialog === 'brand-import' && <ImportBrandDialog urls={projectLinks} csrfToken={bootstrap.csrf} onClose={() => setDialog('')}/>} {canEdit && dialog === 'note' && <NoteDialog urls={projectLinks} csrfToken={bootstrap.csrf} onClose={() => setDialog('')}/>} {dialog === 'source-upload' && <SourceUploadDialog urls={projectLinks} csrfToken={bootstrap.csrf} canEdit={canEdit} pendingFiles={(project.files || []).filter(file => file.requiresReview)} droppedFiles={dropQueue} onDropConsumed={() => setDropQueue([])} onClose={() => setDialog('')}/>} {dialog === 'link' && <LinkDialog urls={projectLinks} csrfToken={bootstrap.csrf} onClose={() => setDialog('')}/>} {selectedResource && <ResourceDialog resource={selectedResource} onClose={() => setResourceId('')}/>}</div>;
}
