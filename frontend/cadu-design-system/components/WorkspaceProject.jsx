import React, {useEffect, useState} from 'react';
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
    <header><div><h2>{title}</h2>{detail && <p>{detail}</p>}</div><button type="button" onClick={onClose} aria-label="Fechar">×</button></header>
    {children}
  </CaduDialog>;
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

const TRIAGE_CATEGORIES = [['brief', 'Briefing'], ['research', 'Pesquisa'], ['media_plan', 'Plano de mídia'], ['report', 'Relatório'], ['brand_asset', 'Ativo de marca'], ['reference', 'Referência'], ['contract', 'Contrato'], ['spreadsheet', 'Planilha'], ['other', 'Outro']];

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
    } catch (uploadError) { setError(uploadError.message || 'Não foi possível preparar o arquivo.'); }
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
    } catch (confirmError) { setError(confirmError.message || 'Não foi possível confirmar este arquivo.'); }
    finally { setBusy(false); }
  };
  const updateTriage = (sourceId, key, value) => setTriage(current => current.map(item => item.source_id === sourceId ? {...item, [key]: value} : item));
  const onDrop = (event) => { event.preventDefault(); setDragging(false); uploadFiles(event.dataTransfer.files); };
  useEffect(() => {
    if (!droppedFiles?.length) return;
    uploadFiles(droppedFiles);
    onDropConsumed?.();
  }, [droppedFiles]);
  return <ProjectDialog title="Fontes e arquivos" detail="O Cadu consulta estas fontes nas conversas do projeto." onClose={onClose}>
    {canEdit && <div className="cadu-ds-project-source-actions">
      <details><summary>Adicionar nota ou briefing</summary><form className="cadu-ds-project-form" method="post" action={urls.createNote}><input type="hidden" name="_csrf" value={csrfToken}/><label>Título<input name="title" required minLength="2" maxLength="180"/></label><label>Conteúdo<textarea name="content" required minLength="20" maxLength="50000" rows="5"/></label><button className="is-primary">Adicionar e indexar</button></form></details>
      <details open><summary>Enviar ou soltar arquivos</summary><div className={`cadu-ds-project-upload-drop ${dragging ? 'is-dragging' : ''}`} onDragEnter={(event) => {event.preventDefault(); setDragging(true);}} onDragOver={(event) => event.preventDefault()} onDragLeave={(event) => {if (event.currentTarget === event.target) setDragging(false);}} onDrop={onDrop}><input id="cadu-project-file-picker" name="file" type="file" multiple hidden onChange={(event) => {uploadFiles(event.target.files); event.target.value = '';}}/><label htmlFor="cadu-project-file-picker"><b>{busy ? 'Preparando arquivo…' : 'Solte aqui ou escolha arquivos'}</b><span>Imagens, PDFs, documentos, planilhas, apresentações, design, vídeo, áudio e outros anexos.</span></label></div><p className="cadu-ds-project-upload-note">O arquivo é preservado primeiro. OCR e classificação aparecem abaixo para você decidir se entra na base de conhecimento.</p></details>
      <details><summary>Importar página pública</summary><form className="cadu-ds-project-form" method="post" action={urls.importUrl}><input type="hidden" name="_csrf" value={csrfToken}/><label>URL<input name="url" type="url" required maxLength="2000" placeholder="https://exemplo.com/pagina"/></label><button className="is-primary">Importar página</button></form></details>
    </div>}
    {error && <p className="cadu-ds-project-upload-error" role="alert">{error}</p>}
    {!!triage.length && <section className="cadu-ds-project-triage" aria-label="Revisar arquivos preparados"><header><b>Revisar antes de indexar</b><span>{triage.length} arquivo{triage.length === 1 ? '' : 's'} aguardando decisão</span></header>{triage.map(item => <article key={item.source_id}><div className="cadu-ds-project-triage__file"><ProjectIcon name="source"/><span><b>{item.name}</b><small>{item.mime} · {item.processing === 'ocr' ? 'OCR aplicado' : item.processing === 'text_extraction' ? 'Texto extraído' : 'Metadados preservados'}</small></span></div>{item.text_preview && <p className="cadu-ds-project-triage__preview">{item.text_preview}</p>}<label className="cadu-ds-project-triage__category">Categoria<select value={item.category} onChange={(event) => updateTriage(item.source_id, 'category', event.target.value)}>{TRIAGE_CATEGORIES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><div className="cadu-ds-project-triage__purpose"><label><input type="radio" name={`purpose-${item.source_id}`} checked={item.purpose === 'project_attachment'} onChange={() => updateTriage(item.source_id, 'purpose', 'project_attachment')}/> Manter como anexo</label><label className={!item.can_index ? 'is-disabled' : ''}><input type="radio" name={`purpose-${item.source_id}`} disabled={!item.can_index} checked={item.purpose === 'knowledge_source'} onChange={() => updateTriage(item.source_id, 'purpose', 'knowledge_source')}/> Indexar na base {item.can_index ? '' : '(sem texto suficiente)'}</label></div><button type="button" className="is-primary" disabled={busy} onClick={() => confirm(item)}>Confirmar decisão</button></article>)}</section>}
    <div className="cadu-ds-project-modal-list">{files.map(file => <div key={file.id}><ProjectIcon name="source"/><span><b>{file.title}</b><small>{file.mime} · {sourceStatus(file.status)}{file.category && ` · ${file.category.replace(/_/g, ' ')}`}</small></span></div>)}{!files.length && !triage.length && <p>Ainda não há fontes neste projeto.</p>}</div>
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

export function WorkspaceProject({bootstrap}) {
  const project = bootstrap.project || {};
  const [dialog, setDialog] = useState('');
  const [dropActive, setDropActive] = useState(false);
  const [dropQueue, setDropQueue] = useState([]);
  const [resourceId, setResourceId] = useState(() => new URLSearchParams(window.location.search).get('resource') || '');
  const [accountOpen, setAccountOpen] = useState(false);
  const initialDockItems = bootstrap.dock?.items?.length ? bootstrap.dock.items : [...(bootstrap.brands || []), ...(bootstrap.projects || [])];
  const [dockItems, setDockItems] = useState(initialDockItems);
  const canEdit = project.status !== 'arquivado';
  const missing = project.health?.missing || [];
  const projectLinks = bootstrap.projectLinks || {};
  const startConversation = () => window.location.assign(projectLinks.conversation);
  const selectedResource = (project.resources || []).find(item => String(item.id) === String(resourceId));
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
  return <div className="cadu-ds-home-shell cadu-ds-project-shell">
    <main className="cadu-ds-home-main">
      <div className="cadu-ds-home-workarea cadu-ds-project-workarea" onDragEnter={(event) => {if (event.dataTransfer?.types?.includes('Files')) {event.preventDefault(); setDropActive(true);}}} onDragOver={(event) => {if (event.dataTransfer?.types?.includes('Files')) event.preventDefault();}} onDragLeave={() => setDropActive(false)} onDrop={(event) => {if (event.dataTransfer?.files?.length) {event.preventDefault(); setDropActive(false); setDropQueue(Array.from(event.dataTransfer.files)); setDialog('sources');}}}>
        {dropActive && <div className="cadu-ds-project-page-drop" aria-hidden="true"><strong>Solte para anexar ao projeto</strong><span>O arquivo será preservado e revisado antes da indexação.</span></div>}
        <CaduDock bootstrap={bootstrap} logo={bootstrap.caduMark} homeUrl={bootstrap.urls.home} userName={bootstrap.user?.name} userAvatar={bootstrap.user?.avatar} userInitials={bootstrap.user?.name?.slice(0, 2).toUpperCase()} accountOpen={accountOpen} accountMenu={<WorkspaceAccountMenu open={accountOpen} onClose={() => setAccountOpen(false)} user={bootstrap.user} links={bootstrap.urls} projects={bootstrap.projects || []} brands={bootstrap.brands || []} usagePercent={bootstrap.usagePercent} onManageShortcuts={() => window.location.assign(`${bootstrap.urls.home}#atalhos`)}/>} onOpenAccount={() => setAccountOpen(current => !current)} brands={bootstrap.brands || []} resources={bootstrap.projects || []} shortcutItems={dockItems.map(item => ({...item, active: (item.kind === 'project' && String(item.projectRef || '') === `ci:${project.id}`) || (item.kind === 'brand' && String(item.brandRef || '') === `studio:${project.brand?.id || ''}`)}))} onDropItem={addDockResource} usagePercent={bootstrap.usagePercent} onNewConversation={startConversation} onOpenBrand={openWorkspaceDetail} onOpenResource={openWorkspaceDetail} onOpenUsage={() => setAccountOpen(true)}/>
        <section className="cadu-ds-project-content">
        <header className="cadu-ds-project-hero"><div className="cadu-ds-project-hero__identity"><VisualIdentity src={project.brand?.logoUrl} initials={project.brand?.initials || project.name} label={project.brand?.name || project.name} color={project.brand?.color || project.color}/></div><div><p>{project.status === 'arquivado' ? 'Projeto arquivado' : 'Projeto em andamento'}</p><h1>{project.name}</h1>{project.brand?.name && <a href={project.brand.href}>{project.brand.name}</a>}<span>{project.description || 'Organize a direção, as fontes e as decisões que vão sustentar este trabalho.'}</span></div><div className="cadu-ds-project-hero__actions"><button type="button" className="is-primary" onClick={startConversation}>Conversar no projeto</button><details><summary>Criar</summary><div><a href={projectLinks.createPlan}>Plano de mídia</a><a href={projectLinks.createImage}>Imagem</a><a href={projectLinks.createVideo}>Vídeo</a></div></details></div></header>
        {project.status === 'arquivado' && <aside className="cadu-ds-project-notice"><b>Este projeto está arquivado.</b><span>O contexto permanece disponível para consulta.</span><form method="post" action={projectLinks.toggleStatus}><input type="hidden" name="_csrf" value={bootstrap.csrf}/><button>Reativar projeto</button></form></aside>}
        <section className="cadu-ds-project-signals" aria-label="Panorama do projeto"><div><b>{project.files?.length || 0}</b><span>fontes</span></div><div><b>{project.deliveries?.length || 0}</b><span>entregas</span></div><div><b>{project.memory?.length || 0}</b><span>decisões</span></div><div><b>{Math.max(0, 4 - missing.length)} / 4</b><span>base preparada</span></div></section>
        <div className="cadu-ds-project-grid">
          <article className="cadu-ds-project-context"><header><div><p>Direção do trabalho</p><h2>O que deve permanecer consistente</h2></div>{canEdit && <button type="button" onClick={() => setDialog('identity')}>Editar contexto</button>}</header><p className="cadu-ds-project-context__lead">{project.description || 'Ainda não há uma direção registrada. Comece pelo resultado esperado para dar uma base às próximas decisões.'}</p><dl><div><dt>Público</dt><dd>{project.identity?.publico || 'A definir'}</dd></div><div><dt>Tom de voz</dt><dd>{project.identity?.tom_de_voz || 'A definir'}</dd></div><div><dt>Posicionamento</dt><dd>{project.identity?.posicionamento || 'A definir'}</dd></div></dl>{project.instructions && <aside><b>Orientações para o Cadu</b><p>{project.instructions}</p></aside>}</article>
          <aside className="cadu-ds-project-next"><p>Próximo passo</p><h2>{missing.length ? 'Fortaleça a base antes da próxima entrega' : 'A base do projeto está pronta para avançar'}</h2>{missing.length ? <ul>{missing.map(item => <li key={item}>{item.charAt(0).toUpperCase() + item.slice(1)}</li>)}</ul> : <span>Use a conversa, o Planner ou o Studio com este contexto.</span>}<button type="button" onClick={() => setDialog(missing.includes('fontes') ? 'sources' : 'identity')}>{missing.includes('fontes') ? 'Adicionar fontes' : 'Revisar contexto'}</button></aside>
        </div>
        <section className="cadu-ds-project-library"><header><div><p>Biblioteca do projeto</p><h2>Fontes, entregas e recursos em um só lugar</h2></div>{canEdit && <button type="button" onClick={() => setDialog('sources')}>Gerenciar fontes</button>}</header><div className="cadu-ds-project-library__columns"><article><div className="cadu-ds-project-section-title"><ProjectIcon name="source"/><h3>Fontes e referências</h3></div>{project.files?.slice(0, 5).map(file => <div className="cadu-ds-project-row" key={file.id}><span><b>{file.title}</b><small>{file.mime}</small></span><em className={`is-${file.status}`}>{sourceStatus(file.status)}</em></div>)}{!project.files?.length && <div className="cadu-ds-project-empty"><p>Nenhuma fonte foi adicionada.</p>{canEdit && <button type="button" onClick={() => setDialog('sources')}>Adicionar a primeira fonte</button>}</div>}</article><article><div className="cadu-ds-project-section-title"><ProjectIcon name="delivery"/><h3>Entregas</h3></div>{project.deliveries?.slice(0, 5).map(item => item.href ? <a className="cadu-ds-project-row cadu-ds-project-row--link" href={item.href} key={item.id}><span><b>{item.title}</b><small>{item.kind}</small></span><em>{deliveryStatus(item)}</em></a> : <div className="cadu-ds-project-row" key={item.id}><span><b>{item.title}</b><small>{item.kind}</small></span><em>{deliveryStatus(item)}</em></div>)}{!project.deliveries?.length && <div className="cadu-ds-project-empty"><p>As próximas criações e planos aparecerão aqui.</p><button type="button" onClick={startConversation}>Criar primeira entrega</button></div>}</article></div>{project.resources?.length > 0 && <div className="cadu-ds-project-resource-strip"><b>{project.resources.length} recursos conectados</b>{project.resources.slice(0, 4).map(item => <button type="button" key={item.id} onClick={() => setResourceId(item.id)}>{item.title}</button>)}</div>}</section>
        <section className="cadu-ds-project-memory"><article><header><div><p>Memória do projeto</p><h2>O que já foi confirmado</h2></div></header>{project.memory?.slice(0, 4).map(item => <div key={item.id}><b>{item.kind.replace(/_/g, ' ')}</b><p>{item.summary}</p></div>)}{!project.memory?.length && <p className="cadu-ds-project-empty-copy">Sínteses confirmadas nas conversas aparecerão aqui.</p>}</article><article><header><div><p>Atalhos e atividade</p><h2>Onde o trabalho continua</h2></div>{canEdit && <button type="button" onClick={() => setDialog('link')}>Adicionar atalho</button>}</header><div className="cadu-ds-project-link-list">{project.links?.slice(0, 4).map(item => <a href={item.url} target="_blank" rel="noreferrer" key={item.id}><b>{item.title}</b><small>{item.provider || item.url.replace(/^https?:\/\//, '')}</small></a>)}{!project.links?.length && <p className="cadu-ds-project-empty-copy">Conecte a pasta, o quadro ou a ferramenta usada pelo time.</p>}</div>{project.activity?.slice(0, 3).map(item => <div className="cadu-ds-project-activity" key={item.id}><span/><p><b>{item.title}</b><small>{item.detail}</small></p></div>)}</article></section>
        {canEdit && <form className="cadu-ds-project-archive" method="post" action={projectLinks.toggleStatus}><input type="hidden" name="_csrf" value={bootstrap.csrf}/><button>Arquivar projeto</button></form>}
        </section>
      </div>
    </main>
    {dialog === 'identity' && <IdentityDialog project={project} urls={projectLinks} csrfToken={bootstrap.csrf} onClose={() => setDialog('')}/>} {dialog === 'sources' && <SourcesDialog urls={projectLinks} csrfToken={bootstrap.csrf} canEdit={canEdit} files={project.files || []} droppedFiles={dropQueue} onDropConsumed={() => setDropQueue([])} onClose={() => setDialog('')}/>} {dialog === 'link' && <LinkDialog urls={projectLinks} csrfToken={bootstrap.csrf} onClose={() => setDialog('')}/>} {selectedResource && <ResourceDialog resource={selectedResource} onClose={() => setResourceId('')}/>}
  </div>;
}
