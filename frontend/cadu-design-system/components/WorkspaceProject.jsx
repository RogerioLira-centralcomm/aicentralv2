import React, {useEffect, useRef, useState} from 'react';
import {CaduDock} from './CaduDock';
import {VisualIdentity} from './VisualIdentity';
import {WorkspaceAccountMenu} from './WorkspaceFeedback';
import {CaduDialog} from './CaduDialog';
import {openWorkspaceDetail} from '../workspaceNavigation';
import {csrf, request} from '../../conversations-v2/lib/api';

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
  };
  return <svg className="cadu-ds-project-icon" viewBox="0 0 24 24" aria-hidden="true">{paths[name] || paths.context}</svg>;
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
    <header className="cadu-ds-project-dialog__header"><div><p className="cadu-ds-project-dialog__eyebrow">Projeto</p><h2>{title}</h2>{detail && <p>{detail}</p>}</div><button type="button" onClick={onClose} aria-label="Fechar">×</button></header>
    {children}
  </CaduDialog>;
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

function IdentityDialog({project, urls, csrfToken, onClose}) {
  return <ProjectDialog title="Editar contexto" detail="Registre apenas o que deve orientar conversas, planos e criações." onClose={onClose}>
    <form className="cadu-ds-project-form" method="post" action={urls.updateContext}>
      <input type="hidden" name="_csrf" value={csrfToken}/>
      <label>Nome do projeto<input name="name" required minLength="2" maxLength="150" defaultValue={project.name}/></label>
      <label>Direção do trabalho<textarea name="description" rows="3" maxLength="4000" defaultValue={project.description}/></label>
      <div className="cadu-ds-project-form__grid"><label>Público<textarea name="audience" rows="3" maxLength="4000" defaultValue={project.identity?.publico}/></label><label>Tom de voz<textarea name="tone_of_voice" rows="3" maxLength="4000" defaultValue={project.identity?.tom_de_voz}/></label></div>
      <label>Posicionamento<textarea name="positioning" rows="3" maxLength="4000" defaultValue={project.identity?.posicionamento}/></label>
      <label>Orientações para o Cadu<textarea name="instructions" rows="5" maxLength="12000" defaultValue={project.instructions}/></label>
      <label>Cor de referência<input name="color" type="color" defaultValue={project.color}/></label>
      <footer><button type="button" onClick={onClose}>Cancelar</button><button className="is-primary">Salvar contexto</button></footer>
    </form>
  </ProjectDialog>;
}

function ProjectDataIndex({project, onOpenResource}) {
  const groups = [
    {key: 'artifacts', label: 'Ativos e entregas', icon: 'delivery', items: [...(project.artifacts || []), ...(project.deliveries || [])].map(item => ({...item, detail: item.detail || item.kind || item.status, href: item.href}))},
    {key: 'sources', label: 'Fontes indexadas', icon: 'source', items: (project.files || []).map(item => ({...item, detail: `${item.mime || 'Arquivo'} · ${item.status || 'preservado'}`, href: item.href}))},
    {key: 'links', label: 'Links e plataformas', icon: 'link', items: (project.links || []).map(item => ({...item, detail: item.provider || item.url, href: item.url, external: true}))},
    {key: 'resources', label: 'Recursos conectados', icon: 'spark', items: (project.resources || []).map(item => ({...item, detail: item.kind || item.resourceType || item.status, resource: true}))},
    {key: 'memory', label: 'Resumos e decisões', icon: 'context', items: (project.memory || []).map(item => ({...item, title: item.kind?.replace(/_/g, ' ') || 'Resumo', detail: item.summary}))},
    {key: 'conversations', label: 'Reuniões e conversas', icon: 'conversation', items: (project.conversations || []).map(item => ({...item, detail: item.updatedAt || item.project_ref}))},
  ].map(group => ({...group, items: group.items.filter(item => item.title || item.name || item.summary)})).filter(group => group.items.length);
  return <section className="cadu-ds-project-data-index" aria-label="Índice de dados do projeto">
    <header><div><p>Índice do projeto</p><h2>O trabalho reunido por tipo de dado</h2></div><span>{groups.reduce((total, group) => total + group.items.length, 0)} itens conectados</span></header>
    <div className="cadu-ds-project-data-index__grid">{groups.map(group => <article key={group.key}><header><ProjectIcon name={group.icon}/><div><h3>{group.label}</h3><small>{group.items.length} item{group.items.length === 1 ? '' : 's'}</small></div></header><div>{group.items.slice(0, 8).map(item => { const content = <><span><b>{item.title || item.name || 'Item sem título'}</b><small>{item.detail || 'Disponível no projeto'}</small></span><em>›</em></>; if (item.resource) return <button type="button" key={item.id} onClick={() => onOpenResource?.(item)}>{content}</button>; if (item.href) return <a key={item.id} href={item.href} target={item.external ? '_blank' : undefined} rel={item.external ? 'noreferrer' : undefined}>{content}</a>; return <div key={item.id}>{content}</div>; })}</div></article>)}</div>
    {!groups.length && <p className="cadu-ds-project-data-index__empty">Adicione fontes, links ou uma conversa para formar o índice deste projeto.</p>}
  </section>;
}

const TRIAGE_CATEGORIES = [['brief', 'Briefing'], ['research', 'Pesquisa'], ['media_plan', 'Plano de mídia'], ['report', 'Relatório'], ['brand_asset', 'Ativo de marca'], ['reference', 'Referência'], ['contract', 'Contrato'], ['spreadsheet', 'Planilha'], ['other', 'Outro']];

function SourceSection({title, detail, open = false, children}) {
  return <details className="cadu-ds-project-source-section" open={open}>
    <summary><span><b>{title}</b><small>{detail}</small></span><i aria-hidden="true">⌄</i></summary>
    <div className="cadu-ds-project-source-section__body">{children}</div>
  </details>;
}

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
        <button type="submit" className={String(brand.id) === String(currentBrandId) ? 'is-selected' : ''}><VisualIdentity src={brand.logoUrl} initials={brand.visualInitials || brand.name} label={brand.name} color={brand.visualColor || '#176b5e'} variant={brand.visualVariant}/><span><b>{brand.name}</b><small>{brand.description || 'Abrir esta identidade no projeto'}</small></span><i aria-hidden="true">{String(brand.id) === String(currentBrandId) ? 'Atual' : 'Usar'}</i></button>
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
    <header><div><p>Identidade do projeto</p><h2 id="project-brand-feature-title">{hasBrand ? 'A marca que orienta este trabalho' : 'Defina a marca deste projeto'}</h2><span>{hasBrand ? 'Logo, cores e tipografia ficam visíveis antes da próxima criação.' : 'Uma marca dá ao Cadu referências para responder e criar com consistência.'}</span></div>{hasBrand && <span className="cadu-ds-project-brand-feature__status">{identityCount === 3 ? 'Identidade definida' : 'Identidade parcial'}</span>}</header>
    {hasBrand ? <div className="cadu-ds-project-brand-feature__body">
      <a className="cadu-ds-project-brand-feature__identity" href={brand.href}><VisualIdentity src={brand.logoUrl} initials={brand.initials || brand.name} label={brand.name} color={brand.color || '#176b5e'} variant={brand.visualVariant}/><span><b>{brand.name}</b><small>{identityCount === 3 ? 'Sistema visual disponível' : 'Complete a identidade no detalhe da marca'}</small></span></a>
      <div className="cadu-ds-project-brand-feature__tokens"><div><b>Cores</b>{colors.length ? <span className="cadu-ds-project-brand-feature__swatches">{colors.map(token => <i key={token.value} title={`${token.label}: ${token.value}`} style={{background: token.value}}/> )}</span> : <small>A definir</small>}</div><div><b>Tipografia</b>{fonts.length ? <span className="cadu-ds-project-brand-feature__fonts">{fonts.map(font => <span key={`${font.role}-${font.family}`}><strong>{font.family}</strong><small>{font.role}</small></span>)}</span> : <small>A definir</small>}</div></div>
      <div className="cadu-ds-project-brand-feature__actions"><a href={brand.href}>{identityCount === 3 ? 'Ver detalhe da marca' : 'Definir identidade'}</a>{canEdit && <button type="button" onClick={() => onDialog('brand-picker')}>Trocar marca</button>}{canManageBrand && brand.auditHref && <a href={brand.auditHref}>Auditar marca</a>}</div>
    </div> : <div className="cadu-ds-project-brand-feature__empty"><div className="cadu-ds-project-brand-feature__empty-mark"><ProjectIcon name="spark"/></div><div><h3>Nenhuma marca vinculada</h3><p>Escolha uma marca existente ou crie uma nova já com auditoria ligada a este projeto.</p></div><div className="cadu-ds-project-brand-feature__actions">{canEdit && <button type="button" className="is-primary" onClick={() => onDialog('brand-picker')}>Definir marca</button>}{canManageBrand && <button type="button" onClick={() => onDialog('brand-import')}>Criar e auditar marca</button>}</div></div>}
  </section>;
}

function SourcesDialog({urls, csrfToken, canEdit, files, droppedFiles, onDropConsumed, onClose}) {
  const [triage, setTriage] = useState(() => files.filter(file => file.requiresReview).map(file => ({source_id: file.id, name: file.title, mime: file.mime, processing: 'metadata_only', text_preview: '', can_index: file.canIndex, confirm_url: file.confirmUrl, purpose: 'project_attachment', category: file.category || 'other'})));
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState('');
  const uploadFiles = async (incoming) => {
    const selected = Array.from(incoming || []).filter(Boolean);
    if (!selected.length || busy) return;
    setBusy(true); setError('');
    try {
      const prepared = [];
      for (const file of selected) {
        const body = new FormData(); body.append('_csrf', csrfToken); body.append('file', file);
        const response = await fetch(urls.uploadSource, {method: 'POST', credentials: 'same-origin', headers: {'Accept': 'application/json', 'X-CSRF-Token': csrfToken, 'X-Cadu-Triage': '1'}, body});
        const value = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(value.error || 'Não foi possível preparar este arquivo.');
        prepared.push({...value, purpose: 'project_attachment', category: value.classification?.category || 'other'});
      }
      setTriage(current => [...current, ...prepared]);
    } catch (uploadError) { setError(sourceErrorMessage(uploadError, 'Não foi possível preparar o arquivo.')); }
    finally { setBusy(false); }
  };
  const confirm = async (item) => {
    setBusy(true); setError('');
    try {
      const response = await fetch(item.confirm_url || item.confirmUrl, {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'Accept': 'application/json', 'X-CSRF-Token': csrfToken}, body: JSON.stringify({purpose: item.purpose, category: item.category})});
      const value = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(value.error || 'Não foi possível confirmar este arquivo.');
      setTriage(current => current.filter(entry => entry.source_id !== item.source_id));
      window.setTimeout(() => window.location.reload(), 250);
    } catch (confirmError) { setError(sourceErrorMessage(confirmError, 'Não foi possível confirmar este arquivo.')); }
    finally { setBusy(false); }
  };
  const updateTriage = (sourceId, key, value) => setTriage(current => current.map(item => item.source_id === sourceId ? {...item, [key]: value} : item));
  const onDrop = (event) => { event.preventDefault(); setDragging(false); uploadFiles(event.dataTransfer.files); };
  useEffect(() => {
    if (!droppedFiles?.length) return;
    uploadFiles(droppedFiles);
    onDropConsumed?.();
  }, [droppedFiles]);
  return <ProjectDialog title="Fontes e arquivos" detail="Traga contexto para o projeto e revise cada item antes de colocá-lo na base do Cadu." onClose={onClose}>
    {canEdit && <div className="cadu-ds-project-source-actions">
      <SourceSection title="Adicionar nota ou briefing" detail="Registre uma orientação sem enviar arquivo."><form className="cadu-ds-project-form" method="post" action={urls.createNote}><input type="hidden" name="_csrf" value={csrfToken}/><label>Título<input name="title" required minLength="2" maxLength="180"/></label><label>Conteúdo<textarea name="content" required minLength="20" maxLength="50000" rows="5"/></label><button className="is-primary">Adicionar nota</button></form></SourceSection>
      <SourceSection title="Enviar arquivos" detail="Preserve primeiro; decida depois se entram na base do Cadu." open><div className={`cadu-ds-project-upload-drop ${dragging ? 'is-dragging' : ''}`} onDragEnter={(event) => {event.preventDefault(); setDragging(true);}} onDragOver={(event) => event.preventDefault()} onDragLeave={(event) => {if (event.currentTarget === event.target) setDragging(false);}} onDrop={onDrop}><span className="cadu-ds-project-upload-drop__icon"><ProjectIcon name="source"/></span><b>{busy ? 'Preparando arquivos…' : 'Solte arquivos aqui'}</b><span>PDF, documento, planilha, imagem, áudio ou vídeo</span></div><p className="cadu-ds-project-upload-note">O arquivo fica preservado primeiro. O Cadu mostra a leitura e a classificação abaixo para você decidir entre anexo ou fonte de conhecimento.</p></SourceSection>
      <SourceSection title="Importar página pública" detail="Adicione uma URL para manter como referência do projeto."><form className="cadu-ds-project-form" method="post" action={urls.importUrl}><input type="hidden" name="_csrf" value={csrfToken}/><label>URL pública<input name="url" type="url" required maxLength="2000" placeholder="https://exemplo.com/pagina"/></label><button className="is-primary">Importar página</button></form></SourceSection>
    </div>}
    {error && <p className="cadu-ds-project-upload-error" role="alert">{error}</p>}
    {!!triage.length && <section className="cadu-ds-project-triage" aria-label="Revisar arquivos preparados"><header><b>Revisar antes de indexar</b><span>{triage.length} arquivo{triage.length === 1 ? '' : 's'} aguardando decisão</span></header>{triage.map(item => <article key={item.source_id}><div className="cadu-ds-project-triage__file"><ProjectIcon name="source"/><span><b>{item.name}</b><small>{item.mime} · {item.processing === 'ocr' ? 'OCR aplicado' : item.processing === 'text_extraction' ? 'Texto extraído' : 'Metadados preservados'}</small></span></div>{item.text_preview && <p className="cadu-ds-project-triage__preview">{item.text_preview}</p>}<label className="cadu-ds-project-triage__category">Categoria<select value={item.category} onChange={(event) => updateTriage(item.source_id, 'category', event.target.value)}>{TRIAGE_CATEGORIES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><div className="cadu-ds-project-triage__purpose"><label><input type="radio" name={`purpose-${item.source_id}`} checked={item.purpose === 'project_attachment'} onChange={() => updateTriage(item.source_id, 'purpose', 'project_attachment')}/> Manter como anexo</label><label className={!item.can_index ? 'is-disabled' : ''}><input type="radio" name={`purpose-${item.source_id}`} disabled={!item.can_index} checked={item.purpose === 'knowledge_source'} onChange={() => updateTriage(item.source_id, 'purpose', 'knowledge_source')}/> Indexar na base {item.can_index ? '' : '(sem texto suficiente)'}</label></div><button type="button" className="is-primary" disabled={busy} onClick={() => confirm(item)}>Confirmar decisão</button></article>)}</section>}
    <div className="cadu-ds-project-modal-list">{files.length > 0 && <h3>Fontes já adicionadas</h3>}{files.map(file => <div key={file.id}><ProjectIcon name="source"/><span><b>{file.title}</b><small>{file.mime} · {sourceStatus(file.status)}{file.category && ` · ${file.category.replace(/_/g, ' ')}`}</small></span></div>)}{!files.length && !triage.length && <p>Nenhuma fonte foi adicionada ainda.</p>}</div>
  </ProjectDialog>;
}

function LinkDialog({urls, csrfToken, onClose}) {
  return <ProjectDialog title="Adicionar atalho" detail="Cole um link de Drive, Miro, ClickUp ou outra ferramenta do projeto." onClose={onClose}>
    <form className="cadu-ds-project-form" method="post" action={urls.createLink}><input type="hidden" name="_csrf" value={csrfToken}/><label>Link<input name="url" type="url" required maxLength="2000" placeholder="https://…"/></label><label>Nome do atalho <small>Opcional</small><input name="title" maxLength="180" placeholder="Ex.: Pasta de referências"/></label><footer><button type="button" onClick={onClose}>Cancelar</button><button className="is-primary">Salvar atalho</button></footer></form>
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
  return ({completed: 'Pronta para consulta', indexing: 'Indexando', queued: 'Na fila', error: 'Requer atenção', paused: 'Somente anexo'})[status] || 'Fonte do projeto';
}

function deliveryStatus(item) {
  return item.status ? item.status.replace(/_/g, ' ') : 'Disponível';
}

function artifactIconName(kind) {
  return ({conversation: 'conversation', artifact: 'artifact', html: 'html', text: 'text', file: 'file', pdf: 'pdf', image: 'image', plan: 'plan', analysis: 'analysis'})[kind] || 'artifact';
}

function ProjectContinuitySection({project, onStartConversation}) {
  const conversations = Array.isArray(project.conversations) ? project.conversations : [];
  const artifacts = Array.isArray(project.artifacts) ? project.artifacts : [];
  const [showAllConversations, setShowAllConversations] = useState(false);
  const [showAllArtifacts, setShowAllArtifacts] = useState(false);
  const renderItem = entry => entry.href ? <a className="cadu-ds-project-continuity__item" href={entry.href} key={entry.id}>
    <span className={`cadu-ds-project-continuity__icon is-${entry.kind || 'artifact'}`}><ProjectIcon name={entry.kind === 'conversation' ? 'conversation' : artifactIconName(entry.kind)}/></span>
    <span className="cadu-ds-project-continuity__copy"><b>{entry.title}</b><small>{entry.detail}</small></span><i aria-hidden="true">›</i>
  </a> : <div className="cadu-ds-project-continuity__item" key={entry.id}>
    <span className={`cadu-ds-project-continuity__icon is-${entry.kind || 'artifact'}`}><ProjectIcon name={artifactIconName(entry.kind)}/></span>
    <span className="cadu-ds-project-continuity__copy"><b>{entry.title}</b><small>{entry.detail}</small></span>
  </div>;
  return <section className="cadu-ds-project-continuity" aria-labelledby="project-continuity-title">
    <header><div><p>Continuidade do projeto</p><h2 id="project-continuity-title">Conversas e artefatos salvos</h2><span>Retome uma conversa ou encontre o material que já foi produzido para este contexto.</span></div></header>
    <div className="cadu-ds-project-continuity__columns">
      <article><div className="cadu-ds-project-section-title"><ProjectIcon name="conversation"/><h3>Conversas do projeto</h3><em>{conversations.length}</em></div>{conversations.length ? <>{(showAllConversations ? conversations : conversations.slice(0, 8)).map(renderItem)}{conversations.length > 8 && <button type="button" className="cadu-ds-project-continuity__more" onClick={() => setShowAllConversations(current => !current)}>{showAllConversations ? 'Mostrar menos' : `Ver todas as ${conversations.length} conversas`}</button>}</> : <div className="cadu-ds-project-empty"><p>As conversas iniciadas neste projeto aparecerão aqui.</p><button type="button" onClick={onStartConversation}>Começar uma conversa</button></div>}</article>
      <article><div className="cadu-ds-project-section-title"><ProjectIcon name="artifact"/><h3>Artefatos salvos</h3><em>{artifacts.length}</em></div>{artifacts.length ? <>{(showAllArtifacts ? artifacts : artifacts.slice(0, 12)).map(renderItem)}{artifacts.length > 12 && <button type="button" className="cadu-ds-project-continuity__more" onClick={() => setShowAllArtifacts(current => !current)}>{showAllArtifacts ? 'Mostrar menos' : `Ver todos os ${artifacts.length} artefatos`}</button>}</> : <div className="cadu-ds-project-empty"><p>HTML, textos, arquivos, PDFs e imagens salvos aparecerão aqui.</p><button type="button" onClick={onStartConversation}>Criar no projeto</button></div>}</article>
    </div>
  </section>;
}

export function WorkspaceProject({bootstrap}) {
  const project = bootstrap.project || {};
  const [dialog, setDialog] = useState('');
  const [dropActive, setDropActive] = useState(false);
  const [dropQueue, setDropQueue] = useState([]);
  const dragDepth = useRef(0);
  const [resourceId, setResourceId] = useState(() => new URLSearchParams(window.location.search).get('resource') || '');
  const [accountOpen, setAccountOpen] = useState(false);
  const [sharing, setSharing] = useState(project.sharing || {});
  const initialDockItems = bootstrap.dock?.items?.length ? bootstrap.dock.items : [...(bootstrap.brands || []), ...(bootstrap.projects || [])];
  const [dockItems, setDockItems] = useState(initialDockItems);
  const canEdit = project.status !== 'arquivado';
  const missing = project.health?.missing || [];
  const isNewProject = missing.length >= 3 && !(project.files?.length || project.deliveries?.length || project.memory?.length || project.links?.length);
  const projectLinks = bootstrap.projectLinks || {};
  const startConversation = () => window.location.assign(projectLinks.conversation);
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
      setDialog('sources');
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
  return <div className={`cadu-ds-home-shell cadu-ds-project-shell${isNewProject ? ' is-new-project' : ''}`}>
    <main className="cadu-ds-home-main">
      <div className="cadu-ds-home-workarea cadu-ds-project-workarea" onDragEnter={handleDragEnter} onDragOver={handleDragOver} onDragLeave={handleDragLeave} onDrop={handleFileDrop}>
        {dropActive && <div className="cadu-ds-project-page-drop" role="status" aria-live="polite"><div className="cadu-ds-project-page-drop__card"><span className="cadu-ds-project-page-drop__icon"><ProjectIcon name="source"/></span><strong>Solte para adicionar ao projeto</strong><span>O arquivo será preservado e revisado antes de entrar na base do Cadu.</span></div></div>}
        <CaduDock bootstrap={bootstrap} logo={bootstrap.caduMark} homeUrl={bootstrap.urls.home} userName={bootstrap.user?.name} userAvatar={bootstrap.user?.avatar} userInitials={bootstrap.user?.name?.slice(0, 2).toUpperCase()} accountOpen={accountOpen} accountMenu={<WorkspaceAccountMenu open={accountOpen} onClose={() => setAccountOpen(false)} user={bootstrap.user} links={bootstrap.urls} projects={bootstrap.projects || []} brands={bootstrap.brands || []} usagePercent={bootstrap.usagePercent} onManageShortcuts={() => window.location.assign(`${bootstrap.urls.home}#atalhos`)}/>} onOpenAccount={() => setAccountOpen(current => !current)} brands={bootstrap.brands || []} resources={bootstrap.projects || []} shortcutItems={dockItems.map(item => ({...item, active: (item.kind === 'project' && String(item.projectRef || '') === `ci:${project.id}`) || (item.kind === 'brand' && String(item.brandRef || '') === `studio:${project.brand?.id || ''}`)}))} onDropItem={addDockResource} usagePercent={bootstrap.usagePercent} onNewConversation={startConversation} onOpenBrand={openWorkspaceDetail} onOpenResource={openWorkspaceDetail} onOpenUsage={() => setAccountOpen(true)}/>
        <section className="cadu-ds-project-content">
        <header className="cadu-ds-project-hero"><div className="cadu-ds-project-hero__identity"><VisualIdentity src={project.brand?.logoUrl} initials={project.brand?.initials || project.name} label={project.brand?.name || project.name} color={project.brand?.color || project.color}/></div><div><p>{project.status === 'arquivado' ? 'Projeto arquivado' : 'Projeto em andamento'}</p><h1>{project.name}</h1>{project.brand?.name && <a href={project.brand.href}>{project.brand.name}</a>}<span>{project.description || 'Organize a direção, as fontes e as decisões que vão sustentar este trabalho.'}</span></div><div className="cadu-ds-project-hero__actions"><button type="button" className="is-primary" onClick={startConversation}>Conversar no projeto</button><details><summary>Criar</summary><div><a href={projectLinks.createPlan}>Plano de mídia</a><a href={projectLinks.createImage}>Imagem</a><a href={projectLinks.createVideo}>Vídeo</a></div></details></div></header>
        {isNewProject && <section className="cadu-ds-project-state"><div className="cadu-ds-project-state__visual" aria-hidden="true"/><div><p>Projeto começando</p><h2>Vamos reunir o contexto deste trabalho</h2><span>Adicione links, arquivos ou uma orientação inicial. Assim o Cadu consegue responder e criar com mais precisão para o seu time.</span><div><button type="button" className="is-primary" onClick={() => setDialog('sources')}>Adicionar fontes</button><button type="button" onClick={() => setDialog('identity')}>Definir contexto</button></div></div></section>}
        <section className="cadu-ds-project-sharing" aria-label="Acesso ao projeto"><div><p>Acesso do projeto</p><h2>{sharing.visibility === 'team' ? 'Toda a equipe' : sharing.visibility === 'restricted' ? 'Pessoas específicas' : 'Privado'}</h2><span>{sharing.members?.length ? `${sharing.members.length} pessoa${sharing.members.length === 1 ? '' : 's'} com acesso direto` : 'Acesso restrito'}</span></div><div className="cadu-ds-project-sharing__members">{(sharing.members || []).slice(0, 4).map(member => <span key={member.id} title={`${member.name} · ${member.role}`}>{member.name.slice(0, 1).toUpperCase()}</span>)}{sharing.members?.length > 4 && <em>+{sharing.members.length - 4}</em>}</div>{bootstrap.canManageSharing && <button type="button" className="cadu-ds-project-sharing__manage" onClick={() => setDialog('sharing')}>Gerenciar acesso</button>}</section>
        <ProjectBrandCard brand={project.brand} urls={projectLinks} canEdit={canEdit} canManageBrand={bootstrap.canManageBrand} onDialog={setDialog}/>
        <ProjectDataIndex project={project} onOpenResource={item => setResourceId(item.id)}/>
        {project.status === 'arquivado' && <aside className="cadu-ds-project-notice"><b>Este projeto está arquivado.</b><span>O contexto permanece disponível para consulta.</span><form method="post" action={projectLinks.toggleStatus}><input type="hidden" name="_csrf" value={bootstrap.csrf}/><button>Reativar projeto</button></form></aside>}
        <section className="cadu-ds-project-signals" aria-label="Panorama do projeto"><div><b>{project.files?.length || 0}</b><span>fontes</span></div><div><b>{project.deliveries?.length || 0}</b><span>entregas</span></div><div><b>{project.memory?.length || 0}</b><span>decisões</span></div><div><b>{Math.max(0, 4 - missing.length)} / 4</b><span>base preparada</span></div></section>
        <div className="cadu-ds-project-grid">
          <article className="cadu-ds-project-context"><header><div><p>Direção do trabalho</p><h2>O que deve permanecer consistente</h2></div>{canEdit && <button type="button" onClick={() => setDialog('identity')}>Editar contexto</button>}</header><p className="cadu-ds-project-context__lead">{project.description || 'Adicione uma orientação para dar base às próximas decisões.'}</p>{(() => { const items = [{label:'Público', value:project.identity?.publico}, {label:'Tom de voz', value:project.identity?.tom_de_voz}, {label:'Posicionamento', value:project.identity?.posicionamento}].filter(item => item.value); return items.length ? <dl>{items.map(item => <div key={item.label}><dt>{item.label}</dt><dd>{item.value}</dd></div>)}</dl> : <p className="cadu-ds-project-context-empty">O contexto ganha forma conforme você adiciona briefing, fontes e decisões.</p>; })()}{project.instructions && <aside><b>Orientações para o Cadu</b><p>{project.instructions}</p></aside>}</article>
          <aside className="cadu-ds-project-next"><p>Próximo passo</p><h2>{missing.length ? 'Fortaleça a base antes da próxima entrega' : 'A base do projeto está pronta para avançar'}</h2>{missing.length ? <ul>{missing.map(item => <li key={item}>{item.charAt(0).toUpperCase() + item.slice(1)}</li>)}</ul> : <span>Use a conversa, o Planner ou o Studio com este contexto.</span>}<button type="button" onClick={() => setDialog(missing.includes('fontes') ? 'sources' : 'identity')}>{missing.includes('fontes') ? 'Adicionar fontes' : 'Revisar contexto'}</button></aside>
        </div>
        <ProjectContinuitySection project={project} onStartConversation={startConversation}/>
        <section className="cadu-ds-project-library"><header><div><p>Biblioteca do projeto</p><h2>Entregas e recursos em um só lugar</h2></div>{canEdit && <button type="button" onClick={() => setDialog('sources')}>Gerenciar fontes</button>}</header><div className="cadu-ds-project-library__columns"><article><div className="cadu-ds-project-section-title"><ProjectIcon name="source"/><h3>Fontes e arquivos</h3></div><div className="cadu-ds-project-library-summary"><b>{project.files?.length || 0} fontes preservadas</b><p>Os detalhes de HTML, textos, PDFs, imagens e outros arquivos ficam na seção de artefatos acima.</p>{canEdit && <button type="button" onClick={() => setDialog('sources')}>Gerenciar fontes</button>}</div></article><article><div className="cadu-ds-project-section-title"><ProjectIcon name="delivery"/><h3>Entregas</h3></div>{project.deliveries?.slice(0, 5).map(item => item.href ? <a className="cadu-ds-project-row cadu-ds-project-row--link" href={item.href} key={item.id}><span><b>{item.title}</b><small>{item.kind}</small></span><em>{deliveryStatus(item)}</em></a> : <div className="cadu-ds-project-row" key={item.id}><span><b>{item.title}</b><small>{item.kind}</small></span><em>{deliveryStatus(item)}</em></div>)}{!project.deliveries?.length && <div className="cadu-ds-project-empty"><p>As próximas criações e planos aparecerão aqui.</p><button type="button" onClick={startConversation}>Criar primeira entrega</button></div>}</article></div>{project.resources?.length > 0 && <div className="cadu-ds-project-resource-strip"><b>{project.resources.length} recursos conectados</b>{project.resources.slice(0, 4).map(item => <button type="button" key={item.id} onClick={() => setResourceId(item.id)}>{item.title}</button>)}</div>}</section>
        <section className="cadu-ds-project-memory"><article><header><div><p>Memória do projeto</p><h2>O que já foi confirmado</h2></div></header>{project.memory?.slice(0, 4).map(item => <div key={item.id}><b>{item.kind.replace(/_/g, ' ')}</b><p>{item.summary}</p></div>)}{!project.memory?.length && <p className="cadu-ds-project-empty-copy">Sínteses confirmadas nas conversas aparecerão aqui.</p>}</article><article><header><div><p>Atalhos e atividade</p><h2>Onde o trabalho continua</h2></div>{canEdit && <button type="button" onClick={() => setDialog('link')}>Adicionar atalho</button>}</header><div className="cadu-ds-project-link-list">{project.links?.slice(0, 4).map(item => <a href={item.url} target="_blank" rel="noreferrer" key={item.id}><b>{item.title}</b><small>{item.provider || item.url.replace(/^https?:\/\//, '')}</small></a>)}{!project.links?.length && <p className="cadu-ds-project-empty-copy">Conecte a pasta, o quadro ou a ferramenta usada pelo time.</p>}</div>{project.activity?.slice(0, 3).map(item => <div className="cadu-ds-project-activity" key={item.id}><span/><p><b>{item.title}</b><small>{item.detail}</small></p></div>)}</article></section>
        {canEdit && <form className="cadu-ds-project-archive" method="post" action={projectLinks.toggleStatus}><input type="hidden" name="_csrf" value={bootstrap.csrf}/><button>Arquivar projeto</button></form>}
        </section>
      </div>
    </main>
    {dialog === 'sharing' && <SharingDialog project={{...project, sharing}} urls={projectLinks} csrfToken={bootstrap.csrf} onSaved={setSharing} onClose={() => setDialog('')} />}
    {dialog === 'identity' && <IdentityDialog project={project} urls={projectLinks} csrfToken={bootstrap.csrf} onClose={() => setDialog('')}/>} {dialog === 'brand-picker' && <BrandPickerDialog brands={bootstrap.brands || []} currentBrandId={project.brand?.id} urls={projectLinks} csrfToken={bootstrap.csrf} canManageBrand={bootstrap.canManageBrand} onCreate={() => setDialog('brand-import')} onClose={() => setDialog('')}/>} {dialog === 'brand-import' && <ImportBrandDialog urls={projectLinks} csrfToken={bootstrap.csrf} onClose={() => setDialog('')}/>} {dialog === 'sources' && <SourcesDialog urls={projectLinks} csrfToken={bootstrap.csrf} canEdit={canEdit} files={project.files || []} droppedFiles={dropQueue} onDropConsumed={() => setDropQueue([])} onClose={() => setDialog('')}/>} {dialog === 'link' && <LinkDialog urls={projectLinks} csrfToken={bootstrap.csrf} onClose={() => setDialog('')}/>} {selectedResource && <ResourceDialog resource={selectedResource} onClose={() => setResourceId('')}/>}
  </div>;
}
