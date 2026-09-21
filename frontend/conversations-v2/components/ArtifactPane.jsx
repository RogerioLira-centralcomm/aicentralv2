import React, {useEffect, useMemo, useRef, useState} from 'react';
import {Icon} from '../lib/icons';
import {csrf, request, safeUrl} from '../lib/api';

const labels = {
  brief: 'Briefing', document: 'Documento', note: 'Nota', executive_summary: 'Resumo executivo',
  media_plan: 'Plano de mídia', scenario: 'Cenário', research: 'Pesquisa', project_map: 'Mapa do projeto',
  html: 'Página interativa', image: 'Imagem', spreadsheet: 'Planilha', report: 'Relatório',
  resource: 'Arquivo', brand_identity: 'Marca', meeting_summary: 'Resumo de reunião', meeting_agenda: 'Pauta',
  link_reader: 'Referência',
};

function EditableTextarea({value, onChange, className = '', ...props}) {
  const ref = useRef(null);
  useEffect(() => {
    if (!ref.current) return;
    ref.current.style.height = '0px';
    ref.current.style.height = `${Math.max(52, ref.current.scrollHeight)}px`;
  }, [value]);
  return <textarea ref={ref} className={className} value={value} onChange={event => onChange(event.target.value)} {...props}/>;
}

function htmlDocument(content, artifactTitle = '') {
  const css = String(content.css || '').replace(/<\/style/gi, '<\\/style');
  const javascript = String(content.js || '').replace(/<\/script/gi, '<\\/script');
  const origin = window.location.origin;
  const logo = safeUrl(content.logo_url);
  const color = value => /^#[0-9a-f]{3,8}$/i.test(String(value || '').trim()) ? String(value).trim() : '';
  const theme = [color(content.primary_color) && `--cadu-brand-primary:${color(content.primary_color)}`, color(content.secondary_color) && `--cadu-brand-secondary:${color(content.secondary_color)}`].filter(Boolean).join(';');
  const favicon = logo ? `<link rel="icon" href="${escapeHtml(logo)}">` : '';
  const artifactStylesheet = `${origin}/static/css/tailwind/artifact.css`;
  const body = String(content.html || '');
  const brandName = escapeHtml(content.title || artifactTitle || 'Cadu');
  const brandHeader = logo && !/<img\b/i.test(body) ? `<header data-cadu-brand-header class="mx-auto flex w-full max-w-6xl items-center gap-3 border-b border-slate-200 px-6 py-4" style="border-bottom-color:var(--cadu-brand-primary,#176b5e)"><img src="${escapeHtml(logo)}" alt="" class="h-8 w-auto object-contain"><span class="text-sm font-semibold text-slate-700">${brandName}</span></header>` : '';
  return `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">${favicon}<link rel="stylesheet" href="${artifactStylesheet}"><meta http-equiv="Content-Security-Policy" content="sandbox allow-scripts; default-src 'none'; img-src https: data: blob: ${origin}; style-src 'self' 'unsafe-inline' ${origin}; font-src https: data: ${origin}; script-src 'unsafe-inline'; connect-src 'none'; media-src https: data: blob: ${origin}; form-action 'none'; base-uri 'none'"><style>:root{${theme}}html,body{margin:0;min-height:100%;background:#fff}${css}</style></head><body>${brandHeader}${body}<script>${javascript}<\/script></body></html>`;
}

function StructuredArtifact({artifact, onChange}) {
  const content = artifact.content || {};
  const updateField = (index, value) => onChange({...content, fields: (content.fields || []).map((field, fieldIndex) => fieldIndex === index ? {...field, value} : field)});
  return <article className="cv-artifact-editor cv-mx-auto cv-w-full cv-max-w-[780px] cv-p-6 md:cv-p-10">
    <EditableTextarea className="cv-artifact-summary" value={content.summary || ''} onChange={value => onChange({...content, summary: value})} placeholder="Resumo do trabalho" aria-label="Resumo do artefato"/>
    <div className="cv-mt-7 cv-grid cv-gap-1">{(content.fields || []).map((field, index) => <label key={`${field.key}-${index}`} className="cv-block cv-border-t cv-border-white/[.07] cv-py-5">
      <span className="cv-mb-2 cv-block cv-text-xs cv-font-semibold cv-text-[#78918d]">{field.key || `Seção ${index + 1}`}</span>
      <EditableTextarea value={field.value || ''} onChange={value => updateField(index, value)} aria-label={field.key || `Seção ${index + 1}`}/>
    </label>)}</div>
  </article>;
}

function escapeHtml(value) {
  return String(value || '').replace(/[&<>"']/g, char => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[char]));
}

function documentHtml(content) {
  if (content.html) return String(content.html);
  const sections = [];
  if (content.summary) sections.push(`<p>${escapeHtml(content.summary)}</p>`);
  (content.fields || []).forEach(field => {
    if (field?.key) sections.push(`<h2>${escapeHtml(field.key)}</h2>`);
    if (field?.value) sections.push(`<p>${escapeHtml(field.value).replace(/\n/g, '<br/>')}</p>`);
  });
  return sections.join('') || '<p><br/></p>';
}

function RichDocumentArtifact({artifact, onChange, onTitleChange}) {
  const content = artifact.content || {};
  const canvas = useRef(null);
  const html = documentHtml(content);
  useEffect(() => {
    if (!canvas.current || canvas.current.innerHTML === html) return;
    if (document.activeElement !== canvas.current) canvas.current.innerHTML = html;
  }, [artifact.id, html]);
  const emit = () => onChange({...content, html: canvas.current?.innerHTML || ''});
  const command = (name, value = null) => {
    canvas.current?.focus();
    document.execCommand(name, false, value);
    emit();
  };
  const addImage = () => {
    const url = window.prompt('Cole o endereço HTTPS da imagem');
    if (!url || !safeUrl(url)) return;
    command('insertImage', safeUrl(url));
  };
  const addTable = () => {
    command('insertHTML', '<table><thead><tr><th>Item</th><th>Valor</th><th>Observação</th></tr></thead><tbody><tr><td>Exemplo</td><td>—</td><td>Edite este campo</td></tr><tr><td>Outro item</td><td>—</td><td>Edite este campo</td></tr></tbody></table><p><br></p>');
  };
  const selectedTable = () => window.getSelection()?.anchorNode?.parentElement?.closest('table');
  const addTableRow = () => {
    const table = selectedTable();
    if (!table) return;
    const columns = table.rows[0]?.cells.length || 1;
    const row = table.tBodies[0]?.insertRow() || table.insertRow();
    for (let index = 0; index < columns; index += 1) row.insertCell().textContent = '—';
    emit();
  };
  const addTableColumn = () => {
    const table = selectedTable();
    if (!table) return;
    Array.from(table.rows).forEach(row => row.insertCell().textContent = '—');
    emit();
  };
  const removeTableRow = () => {
    const cell = window.getSelection()?.anchorNode?.parentElement?.closest('td,th');
    const table = cell?.closest('table');
    if (!cell || !table || table.rows.length <= 2) return;
    cell.parentElement.remove();
    emit();
  };
  const removeTableColumn = () => {
    const cell = window.getSelection()?.anchorNode?.parentElement?.closest('td,th');
    const table = cell?.closest('table');
    if (!cell || !table || table.rows[0].cells.length <= 1) return;
    const index = cell.cellIndex;
    Array.from(table.rows).forEach(row => row.deleteCell(index));
    emit();
  };
  return <article className="cv-rich-document cv-mx-auto cv-w-full cv-max-w-[820px] cv-p-6 md:cv-p-10">
    <input className="cv-rich-document__title" value={artifact.title || content.title || ''} onChange={event => onTitleChange?.(event.target.value)} placeholder="Título do documento" aria-label="Título do documento"/>
    <input className="cv-rich-document__summary" value={content.summary || ''} onChange={event => onChange({...content, summary: event.target.value})} placeholder="Uma linha para orientar a leitura (opcional)" aria-label="Resumo do documento"/>
    <div className="cv-rich-document__toolbar" role="toolbar" aria-label="Formatação do documento" onMouseDown={event => event.preventDefault()}>
      <button type="button" onClick={() => command('undo')} aria-label="Desfazer última edição">↶</button>
      <button type="button" onClick={() => command('redo')} aria-label="Refazer edição">↷</button>
      <button type="button" onClick={() => command('bold')} aria-label="Negrito"><b>B</b></button>
      <button type="button" onClick={() => command('italic')} aria-label="Itálico"><i>I</i></button>
      <button type="button" onClick={() => command('formatBlock', 'h2')} aria-label="Título de seção">H2</button>
      <button type="button" onClick={() => command('formatBlock', 'blockquote')} aria-label="Citação">“</button>
      <button type="button" onClick={() => command('insertUnorderedList')} aria-label="Lista">•</button>
      <button type="button" onClick={addTable} aria-label="Inserir tabela">Tabela</button>
      <button type="button" onClick={addTableRow} aria-label="Adicionar linha à tabela">Linha +</button>
      <button type="button" onClick={addTableColumn} aria-label="Adicionar coluna à tabela">Coluna +</button>
      <button type="button" onClick={removeTableRow} aria-label="Remover linha da tabela">Linha −</button>
      <button type="button" onClick={removeTableColumn} aria-label="Remover coluna da tabela">Coluna −</button>
      <button type="button" onClick={addImage} aria-label="Adicionar imagem">Imagem</button>
    </div>
    <div ref={canvas} className="cv-rich-document__canvas" contentEditable suppressContentEditableWarning onInput={emit} onBlur={emit} dangerouslySetInnerHTML={{__html: html}} role="textbox" aria-label="Texto do documento"/>
    <p className="cv-rich-document__hint">Editor visual · texto e imagens inline · o rascunho é salvo automaticamente</p>
  </article>;
}

function HtmlArtifact({artifact}) {
  return <iframe title={artifact.title || 'Página interativa'} sandbox="allow-scripts" referrerPolicy="no-referrer" srcDoc={htmlDocument(artifact.content || {}, artifact.title)} className="cv-h-full cv-w-full cv-border-0 cv-bg-white"/>;
}

function ImageArtifact({artifact}) {
  const content = artifact.content || {};
  const src = safeUrl(content.url || content.image_url || content.src);
  return <div className="cv-flex cv-h-full cv-flex-col cv-items-center cv-justify-center cv-gap-4 cv-bg-[#071012] cv-p-6">{src ? <img src={src} alt={content.alt || artifact.title || 'Imagem gerada'} className="cv-max-h-[calc(100%-54px)] cv-max-w-full cv-rounded-xl cv-object-contain"/> : <p className="cv-text-sm cv-text-mist">A imagem ainda não está disponível.</p>}{src && <div className="cv-flex cv-flex-wrap cv-justify-center cv-gap-2"><a href={src} target="_blank" rel="noreferrer" className="cv-rounded-lg cv-bg-teal cv-px-4 cv-py-2 cv-text-xs cv-font-semibold cv-text-[#052522] cv-no-underline">Abrir original</a><a href={src} download className="cv-rounded-lg cv-border cv-border-white/15 cv-bg-white/[.06] cv-px-4 cv-py-2 cv-text-xs cv-font-semibold cv-text-[#d9e7e4] cv-no-underline">Baixar</a></div>}</div>;
}

function ResourceArtifact({artifact}) {
  const content = artifact.content || {};
  const [creating, setCreating] = useState(false);
  const [created, setCreated] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => { setCreating(false); setCreated(null); setError(''); }, [artifact.title, content.editable_copy_url]);
  const editor = safeUrl(created?.editor_url || content.editor_url || content.url);
  const download = safeUrl(content.download_url);
  const editableCopy = safeUrl(content.editable_copy_url);
  const createCopy = async () => {
    if (!editableCopy || creating) return;
    setCreating(true); setError('');
    try {
      const data = await request(editableCopy, {method: 'POST', headers: {'X-CSRF-Token': csrf()}});
      setCreated(data.document || null);
    } catch (reason) { setError(reason.message); }
    finally { setCreating(false); }
  };
  return <article className="cv-mx-auto cv-flex cv-h-full cv-w-full cv-max-w-[720px] cv-flex-col cv-justify-center cv-p-8 md:cv-p-12">
    <span className="cv-grid cv-h-11 cv-w-11 cv-place-items-center cv-rounded-xl cv-bg-teal/10 cv-text-teal"><Icon name="file" size={20}/></span>
    <h3 className="cv-mb-0 cv-mt-5 cv-text-xl cv-font-semibold cv-tracking-[-.02em]">{artifact.title}</h3>
    <p className="cv-mb-0 cv-mt-2 cv-text-sm cv-leading-6 cv-text-[#819b97]">{content.detail || `${content.kind || 'Arquivo'} conectado a esta conversa.`}</p>
    <div className="cv-mt-6 cv-flex cv-flex-wrap cv-gap-2">
      {editor && <a href={editor} target="_blank" rel="noreferrer" className="cv-rounded-lg cv-bg-teal cv-px-4 cv-py-2.5 cv-text-xs cv-font-semibold cv-text-[#052522] cv-no-underline">{created ? 'Abrir documento editável' : 'Abrir arquivo'}</a>}
      {!created && editableCopy && <button type="button" onClick={createCopy} disabled={creating} className="cv-rounded-lg cv-border cv-border-white/10 cv-bg-transparent cv-px-4 cv-py-2.5 cv-text-xs cv-font-semibold disabled:cv-opacity-50">{creating ? 'Preparando…' : 'Criar versão editável'}</button>}
      {download && download !== editor && <a href={download} className="cv-rounded-lg cv-border cv-border-white/10 cv-px-4 cv-py-2.5 cv-text-xs cv-font-semibold cv-text-[#c4d5d2] cv-no-underline">Baixar</a>}
    </div>
    {created && <p className="cv-mb-0 cv-mt-4 cv-text-xs cv-text-teal" role="status">Versão editável criada no Workspace.</p>}
    {error && <p className="cv-mb-0 cv-mt-4 cv-text-xs cv-leading-5 cv-text-[#ff9ca1]" role="alert">{error}</p>}
    {!editor && !editableCopy && !download && <p className="cv-mb-0 cv-mt-5 cv-text-xs cv-text-[#819b97]">Este arquivo está disponível apenas como referência nesta conversa.</p>}
  </article>;
}

function LinkReaderArtifact({artifact, onRequestSummary, onSaveReference, onRequestMeetingPlan}) {
  const content = artifact.content || {};
  const url = safeUrl(content.url);
  let domain = '';
  try { domain = url ? new URL(url).hostname.replace(/^www\./, '') : ''; } catch (_) {}
  const isGoogle = /(^|\.)google\.com$|googleusercontent\.com$/i.test(domain);
  const isMeeting = /meet\.google\.com|calendar\.google\.com/i.test(domain) || /meet|calendar|reuni[aã]o/i.test(String(content.kind || content.provider || ''));
  const access = content.access_mode || (isGoogle ? 'referência Google' : 'link público');
  return <article className="cv-mx-auto cv-flex cv-h-full cv-w-full cv-max-w-[720px] cv-flex-col cv-justify-center cv-p-8 md:cv-p-12">
    <span className="cv-grid cv-h-11 cv-w-11 cv-place-items-center cv-rounded-xl cv-bg-teal/10 cv-text-teal"><Icon name="external" size={20}/></span>
    <span className="cv-mt-5 cv-text-xs cv-font-semibold cv-text-[#78cfc3]">{access}</span>
    <h3 className="cv-mb-0 cv-mt-2 cv-text-xl cv-font-semibold cv-tracking-[-.02em]">{artifact.title || 'Link externo'}</h3>
    <p className="cv-mb-0 cv-mt-2 cv-text-sm cv-leading-6 cv-text-[#819b97]">{domain || 'Endereço externo'}{content.detail ? ` · ${content.detail}` : ''}</p>
    {content.thumbnail && <img src={safeUrl(content.thumbnail)} alt="" className="cv-mt-6 cv-max-h-52 cv-w-full cv-rounded-xl cv-object-cover"/>}
    {isMeeting && <section className="cv-meeting-note cv-mt-6"><strong className="cv-block cv-text-sm">Reunião no projeto</strong><p className="cv-mb-0 cv-mt-1 cv-text-xs cv-leading-5 cv-text-[#99b4af]">Organize pauta, decisões e próximos passos. A participação automática em chamadas não é iniciada por este fluxo.</p></section>}
    <div className="cv-mt-6 cv-grid cv-gap-2">
      {url && <a href={url} target="_blank" rel="noreferrer" className="cv-rounded-lg cv-bg-teal cv-px-4 cv-py-2.5 cv-text-center cv-text-xs cv-font-semibold cv-text-[#052522] cv-no-underline">Abrir endereço original</a>}
      {url && <button type="button" onClick={() => onSaveReference?.(url)} className="cv-rounded-lg cv-border cv-border-white/10 cv-bg-transparent cv-px-4 cv-py-2.5 cv-text-xs cv-font-semibold">Salvar como referência</button>}
      {isMeeting && url && <button type="button" onClick={() => onRequestMeetingPlan?.(url)} className="cv-rounded-lg cv-border cv-border-white/10 cv-bg-transparent cv-px-4 cv-py-2.5 cv-text-xs cv-font-semibold">Preparar reunião</button>}
      {!isGoogle && !isMeeting && url && <button type="button" onClick={() => onRequestSummary?.(url)} className="cv-rounded-lg cv-border cv-border-white/10 cv-bg-transparent cv-px-4 cv-py-2.5 cv-text-xs cv-font-semibold">Abrir e resumir</button>}
    </div>
    <p className="cv-mb-0 cv-mt-4 cv-text-xs cv-leading-5 cv-text-[#71908b]">{isGoogle ? 'Este link permanece como referência. O conteúdo só é acessado pela integração autorizada.' : 'O conteúdo só será extraído depois de escolher “Abrir e resumir”.'}</p>
  </article>;
}

function tokenValue(value) {
  if (typeof value === 'string') return {value, label: value};
  if (!value || typeof value !== 'object') return null;
  const token = value.hex || value.value || value.color || value.family || value.name;
  if (!token) return null;
  return {value: String(token), label: value.role || value.usage || value.name || String(token)};
}

function BrandIdentityArtifact({artifact}) {
  const content = artifact.content || {};
  const logo = safeUrl(content.logo_url);
  const details = (content.details || []).filter(detail => detail?.value && !/^Ainda não definido\.?$/i.test(String(detail.value).trim()));
  const colors = (content.colors || []).map(tokenValue).filter(Boolean);
  const fonts = (content.fonts || []).map(tokenValue).filter(Boolean);
  const hasIdentitySignals = Boolean(logo || content.colors?.length);
  const auditLabel = content.audit_status ? 'Refazer auditoria da marca' : 'Reavaliar auditoria da marca';
  return <article className="cv-brand-identity cv-mx-auto cv-w-full cv-max-w-[720px] cv-p-8 md:cv-p-12">
    <div className="cv-brand-identity__actions"><span>Ações da marca</span><div>{content.website_url && <a href={safeUrl(content.website_url)} target="_blank" rel="noreferrer">Site</a>}{content.audit_url && <a href={safeUrl(content.audit_url)}>{auditLabel}</a>}</div></div>
    <header className="cv-brand-identity__header cv-flex cv-items-center cv-gap-4"><span className="cv-grid cv-h-16 cv-w-16 cv-place-items-center cv-overflow-hidden cv-rounded-2xl cv-bg-white cv-p-1">{logo ? <img src={logo} alt="" className="cv-h-full cv-w-full cv-object-contain"/> : <b className="cv-text-xl cv-text-[#174c45]">{String(content.name || 'M').slice(0, 1)}</b>}</span><div><p className="cv-m-0 cv-text-xs cv-font-medium cv-text-[#8fbab4]">Marca ativa no chat</p><h3 className="cv-m-0 cv-mt-1 cv-text-xl cv-font-semibold">{content.name || artifact.title}</h3>{content.website_url && <a href={safeUrl(content.website_url)} target="_blank" rel="noreferrer" className="cv-brand-identity__website">{content.website_url}</a>}</div></header>
    <p className="cv-mb-0 cv-mt-7 cv-text-sm cv-leading-6 cv-text-[#d2e1de]">{content.summary}</p>
    <div className="cv-brand-identity__stats cv-mt-7" aria-label="Resumo da identidade">
      <div><b>{content.projects?.length || 0}</b><span>projetos vinculados</span></div>
      <div><b>{content.asset_count || 0}</b><span>ativos aprovados</span></div>
      <div><b>{content.colors?.length || 0}</b><span>cores registradas</span></div>
    </div>
    {!!colors.length && <section className="cv-mt-8"><h4 className="cv-m-0 cv-text-xs cv-font-semibold cv-text-[#8da6a1]">Cores</h4><div className="cv-mt-3 cv-flex cv-flex-wrap cv-gap-2">{colors.map((color, index) => <span key={`${color.value}-${index}`} className="cv-flex cv-items-center cv-gap-2 cv-rounded-lg cv-bg-white/[.05] cv-p-2 cv-text-[11px] cv-text-[#bbceca]" title={color.label}><i className="cv-h-5 cv-w-5 cv-rounded-md cv-border cv-border-white/15" style={{background: color.value}}/>{color.value}</span>)}</div></section>}
    {!!fonts.length && <section className="cv-mt-7"><h4 className="cv-m-0 cv-text-xs cv-font-semibold cv-text-[#9ab3ae]">Tipografia</h4><div className="cv-mt-3 cv-flex cv-flex-wrap cv-gap-2">{fonts.map((font, index) => <span key={`${font.value}-${index}`} className="cv-rounded-lg cv-bg-white/[.06] cv-px-3 cv-py-2 cv-text-xs cv-text-[#dbe8e5]"><b>{font.value}</b>{font.label !== font.value && <small className="cv-ml-2 cv-text-[#91aaa5]">{font.label}</small>}</span>)}</div></section>}
    {!hasIdentitySignals && <section className="cv-mt-8 cv-rounded-2xl cv-border cv-border-[#2c5552] cv-bg-[#102325] cv-p-5"><p className="cv-m-0 cv-text-xs cv-font-semibold cv-uppercase cv-tracking-[.08em] cv-text-[#79cfc3]">Identidade incompleta</p><h4 className="cv-mb-0 cv-mt-2 cv-text-base cv-font-semibold cv-text-[#e1efec]">Ainda faltam referências para orientar a marca</h4><p className="cv-mb-0 cv-mt-2 cv-text-sm cv-leading-6 cv-text-[#a9c0bc]">Não há logo, cores ou diretrizes suficientes neste momento. Refaça a auditoria para atualizar a identidade antes de usar este contexto em uma conversa.</p>{content.audit_url && <a href={content.audit_url} className="cv-mt-4 cv-inline-flex cv-items-center cv-rounded-xl cv-bg-teal cv-px-4 cv-py-2.5 cv-text-xs cv-font-semibold cv-text-[#052522] cv-no-underline hover:cv-bg-[#72e0d2]">{auditLabel}</a>}</section>}
    {!!details.length && <dl className="cv-brand-identity__details cv-mt-8 cv-grid cv-gap-4">{details.map(detail => <div key={detail.label} className="cv-border-t cv-border-white/[.08] cv-pt-4"><dt className="cv-text-[11px] cv-font-semibold cv-text-[#8fbab4]">{detail.label}</dt><dd className="cv-m-0 cv-mt-1 cv-text-sm cv-leading-6 cv-text-[#dce9e6]">{detail.value}</dd></div>)}</dl>}
    {!!content.projects?.length && <section className="cv-brand-identity__projects cv-mt-8"><h4>Projetos que herdam este contexto</h4><div>{content.projects.map(project => <span key={project.ref}>{project.name}</span>)}</div></section>}
  </article>;
}

function ProjectMap({artifact, onChange}) {
  const content = artifact.content || {};
  const [zoom, setZoom] = useState(Number(content.layout?.zoom || 1));
  const groups = content.groups || [];
  const resources = content.resources || [];
  const move = (resourceId, groupId) => onChange({
    ...content,
    resources: resources.map(item => item.id === resourceId ? {...item, group_id: groupId} : item),
    groups: groups.map(group => ({...group, resource_ids: [...(group.resource_ids || []).filter(id => id !== resourceId), ...(group.id === groupId ? [resourceId] : [])]})),
  });
  const height = Math.max(680, ...groups.map(group => Number(group.y || 0) + Number(group.height || 160) + 60));
  return <div className="cv-relative cv-h-full cv-overflow-hidden">
    <div className="cv-scroll cv-h-full cv-overflow-auto cv-bg-[radial-gradient(circle_at_1px_1px,rgba(148,184,179,.12)_1px,transparent_0)] cv-bg-[length:22px_22px] cv-p-6">
      <div className="cv-map-scene" style={{height, transform: `scale(${zoom})`}}>{groups.map(group => <section key={group.id} className="cv-map-group" style={{left: group.x || 48, top: group.y || 48, width: group.width || 310, minHeight: group.height || 150}}>
        <header className="cv-flex cv-items-center cv-justify-between cv-border-b cv-border-white/[.07] cv-px-4 cv-py-3"><strong className="cv-text-xs cv-font-semibold">{group.title}</strong><span className="cv-text-[10px] cv-text-[#76908c]">{resources.filter(item => item.group_id === group.id).length}</span></header>
        <div className="cv-grid cv-gap-1 cv-p-2">{resources.filter(item => item.group_id === group.id).map(resource => <details key={resource.id} className="cv-rounded-xl cv-bg-white/[.035] cv-p-3">
          <summary className="cv-cursor-pointer cv-list-none"><span className="cv-block cv-text-[10px] cv-uppercase cv-tracking-wider cv-text-[#71928d]">{resource.type || 'Arquivo'}</span><strong className="cv-mt-1 cv-block cv-text-xs cv-font-medium">{resource.title}</strong></summary>
          <div className="cv-mt-3 cv-border-t cv-border-white/[.07] cv-pt-3">
            <label className="cv-block cv-text-[10px] cv-text-[#78918d]">Mover para<select value={resource.group_id} onChange={event => move(resource.id, event.target.value)} className="cv-mt-1 cv-block cv-h-8 cv-w-full cv-rounded-lg cv-border-0 cv-bg-[#1c3033] cv-px-2 cv-text-[11px]">{groups.map(option => <option key={option.id} value={option.id}>{option.title}</option>)}</select></label>
            <div className="cv-mt-3 cv-flex cv-gap-2">{safeUrl(resource.editor_url) && <a href={safeUrl(resource.editor_url)} target="_blank" rel="noreferrer" className="cv-flex cv-items-center cv-gap-1 cv-text-[11px] cv-text-[#65d8cb] cv-no-underline"><Icon name="external" size={13}/>Editar</a>}{safeUrl(resource.download_url) && <a href={safeUrl(resource.download_url)} className="cv-flex cv-items-center cv-gap-1 cv-text-[11px] cv-text-[#a6bbb7] cv-no-underline"><Icon name="download" size={13}/>Baixar</a>}</div>
          </div>
        </details>)}</div>
      </section>)}</div>
    </div>
    <div className="cv-absolute cv-bottom-4 cv-right-4 cv-flex cv-items-center cv-gap-1 cv-rounded-xl cv-border cv-border-white/10 cv-bg-[#132326]/90 cv-p-1 cv-backdrop-blur"><button type="button" onClick={() => setZoom(value => Math.max(.62, value - .1))} className="cv-h-8 cv-w-8 cv-rounded-lg cv-border-0 cv-bg-transparent">−</button><button type="button" onClick={() => setZoom(1)} className="cv-h-8 cv-min-w-12 cv-rounded-lg cv-border-0 cv-bg-transparent cv-text-[10px]">{Math.round(zoom * 100)}%</button><button type="button" onClick={() => setZoom(value => Math.min(1.35, value + .1))} className="cv-h-8 cv-w-8 cv-rounded-lg cv-border-0 cv-bg-transparent">+</button></div>
  </div>;
}

export function ArtifactPane({artifact, dirty, saving, publishing, publishedUrl, side = 'right', onSideChange, onChange, onTitleChange, projectRef, onSaveToProject, onPublish, onUnpublish, onClose, onSave, onLoadVersions, versions, onRestoreVersion, onRequestSummary, onSaveReference, onRequestMeetingPlan}) {
  const dialog = useRef(null);
  const closeTimer = useRef(null);
  const [loadingVersions, setLoadingVersions] = useState(false);
  const [closing, setClosing] = useState(false);
  const [lightTheme, setLightTheme] = useState(false);
  const type = artifact?.type || 'document';
  const textArtifact = type === 'document' || type === 'brief' || type === 'note' || type === 'executive_summary' || type === 'media_plan' || type === 'scenario' || type === 'research' || type === 'meeting_summary' || type === 'meeting_agenda';
  useEffect(() => {
    const match = document.cookie.match(/(?:^|; )cadu-artifact-theme=([^;]+)/);
    setLightTheme(match?.[1] === 'light');
  }, []);
  const toggleTheme = () => {
    const next = !lightTheme;
    setLightTheme(next);
    document.cookie = `cadu-artifact-theme=${next ? 'light' : 'dark'}; Max-Age=31536000; Path=/; SameSite=Lax`;
  };
  const contentView = useMemo(() => {
    if (!artifact) return null;
    if (type === 'html') return <HtmlArtifact artifact={artifact}/>;
    if (type === 'project_map') return <ProjectMap artifact={artifact} onChange={onChange}/>;
    if (type === 'image') return <ImageArtifact artifact={artifact}/>;
    if (type === 'resource') return <ResourceArtifact artifact={artifact}/>;
    if (type === 'link_reader') return <LinkReaderArtifact artifact={artifact} onRequestSummary={onRequestSummary} onSaveReference={onSaveReference} onRequestMeetingPlan={onRequestMeetingPlan}/>;
    if (type === 'brand_identity') return <BrandIdentityArtifact artifact={artifact}/>;
    return type === 'document'
      ? <RichDocumentArtifact artifact={artifact} onChange={onChange} onTitleChange={onTitleChange}/>
      : <StructuredArtifact artifact={artifact} onChange={onChange}/>;
  }, [artifact, type, onChange, onTitleChange, onRequestSummary, onSaveReference, onRequestMeetingPlan]);
  useEffect(() => {
    setClosing(false);
    if (dialog.current?.open) dialog.current.close();
    return () => window.clearTimeout(closeTimer.current);
  }, [artifact?.id]);
  const requestClose = () => {
    setClosing(true);
    window.clearTimeout(closeTimer.current);
    closeTimer.current = window.setTimeout(onClose, 180);
  };
  const openVersions = async () => {
    setLoadingVersions(true);
    dialog.current?.showModal();
    await onLoadVersions();
    setLoadingVersions(false);
  };
  if (!artifact) return null;
  return <aside className={`cv-artifact-panel cv-artifact-overlay cv-artifact-panel--${side} cv-relative cv-flex cv-h-full cv-flex-none cv-flex-col cv-border-l cv-border-white/[.08] cv-bg-panel ${lightTheme && textArtifact ? 'is-light' : ''} ${closing ? 'cv-is-closing' : ''}`} aria-label="Artefato">
    <header className="cv-flex cv-h-[68px] cv-flex-none cv-items-center cv-gap-4 cv-border-b cv-border-white/[.07] cv-px-5">
      <div className="cv-min-w-0 cv-flex-1"><span className="cv-flex cv-items-center cv-gap-2 cv-text-[11px] cv-font-medium cv-text-[#759a95]">{labels[type] || 'Artefato'}{dirty && <i className="cv-h-1.5 cv-w-1.5 cv-rounded-full cv-bg-[#e3a45f]" title="Alterações não salvas"/>}</span><h2 className="cv-m-0 cv-mt-1 cv-overflow-hidden cv-text-ellipsis cv-whitespace-nowrap cv-text-[15px] cv-font-semibold">{artifact.title || artifact.content?.title || 'Trabalho em andamento'}</h2></div>
      {type === 'html' && artifact.id && <button type="button" onClick={artifact.status === 'published' && onUnpublish ? onUnpublish : onPublish} disabled={publishing || saving} className="cv-artifact-publish">{publishing ? artifact.status === 'published' ? 'Retirando…' : 'Publicando…' : saving ? 'Salvando…' : artifact.status === 'published' ? 'Despublicar' : publishedUrl ? 'Copiar URL' : 'Publicar'}</button>}
      {textArtifact && <button type="button" onClick={toggleTheme} className="cv-artifact-theme-toggle" aria-pressed={lightTheme} title={lightTheme ? 'Usar tema escuro' : 'Usar tema claro'}>{lightTheme ? 'Escuro' : 'Claro'}</button>}
      <button type="button" onClick={() => onSideChange?.(side === 'right' ? 'left' : 'right')} className="cv-artifact-side-toggle" title={side === 'right' ? 'Mover artefato para a esquerda' : 'Mover artefato para a direita'} aria-label={side === 'right' ? 'Mover artefato para a esquerda' : 'Mover artefato para a direita'}>{side === 'right' ? '←' : '→'}</button>
      {artifact.id && <button type="button" onClick={openVersions} className="cv-flex cv-h-8 cv-items-center cv-gap-1.5 cv-rounded-lg cv-border-0 cv-bg-white/[.05] cv-px-2.5 cv-text-[11px] cv-text-[#a8bfbb] hover:cv-bg-white/[.08]" title="Histórico de versões"><Icon name="history" size={14}/>v{artifact.current_version || 1}</button>}
      <button type="button" onClick={requestClose} className="cv-grid cv-h-8 cv-w-8 cv-place-items-center cv-rounded-lg cv-border-0 cv-bg-transparent cv-text-mist hover:cv-bg-white/[.05]" aria-label="Fechar artefato"><Icon name="close" size={17}/></button>
    </header>
    <div className="cv-scroll cv-min-h-0 cv-flex-1 cv-overflow-auto">{contentView}</div>
    {artifact.id && <footer className="cv-artifact-actions"><span>{dirty ? 'Salvando rascunho automaticamente' : artifact.project_ref ? 'Salvo no projeto' : 'Mantido no espaço pessoal'}</span><div>{projectRef && !artifact.project_ref && <button type="button" onClick={onSaveToProject} disabled={saving} className="cv-artifact-actions__project">Adicionar ao projeto</button>}{dirty && <button type="button" onClick={onSave} disabled={saving} className="cv-artifact-actions__save">{saving ? 'Salvando…' : 'Salvar agora'}</button>}</div></footer>}
    <dialog ref={dialog} className="cv-dialog cv-w-[min(540px,calc(100vw-32px))] cv-p-0">
      <section><header className="cv-flex cv-items-center cv-justify-between cv-border-b cv-border-white/10 cv-p-5"><div><h2 className="cv-m-0 cv-text-base">Versões</h2><p className="cv-mb-0 cv-mt-1 cv-text-xs cv-text-mist">Restaure uma revisão anterior.</p></div><button type="button" onClick={() => dialog.current?.close()} className="cv-grid cv-h-8 cv-w-8 cv-place-items-center cv-rounded-lg cv-border-0 cv-bg-transparent"><Icon name="close" size={16}/></button></header>
        <div className="cv-scroll cv-max-h-[55vh] cv-overflow-y-auto cv-p-3">{loadingVersions ? <p className="cv-p-3 cv-text-sm cv-text-mist">Carregando…</p> : versions.length ? versions.map(item => <article key={item.version} className="cv-flex cv-items-center cv-gap-4 cv-rounded-xl cv-p-3 hover:cv-bg-white/[.04]"><div className="cv-min-w-0 cv-flex-1"><strong className="cv-block cv-text-sm">Versão {item.version}</strong><small className="cv-mt-1 cv-block cv-overflow-hidden cv-text-ellipsis cv-whitespace-nowrap cv-text-xs cv-text-mist">{item.change_summary || 'Revisão do artefato'}</small></div><button type="button" disabled={Number(item.version) === Number(artifact.current_version)} onClick={async () => { await onRestoreVersion(item.version); dialog.current?.close(); }} className="cv-rounded-lg cv-border cv-border-white/10 cv-bg-transparent cv-px-3 cv-py-2 cv-text-xs disabled:cv-opacity-35">{Number(item.version) === Number(artifact.current_version) ? 'Atual' : 'Restaurar'}</button></article>) : <p className="cv-p-3 cv-text-sm cv-text-mist">Nenhuma versão disponível.</p>}</div>
      </section>
    </dialog>
  </aside>;
}
