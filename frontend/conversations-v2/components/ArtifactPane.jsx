import React, {useEffect, useMemo, useRef, useState} from 'react';
import {Icon} from '../lib/icons';
import {csrf, request, safeUrl} from '../lib/api';
import {CaduDialog} from '../../cadu-design-system/components/CaduDialog';

const labels = {
  brief: 'Briefing', document: 'Documento', note: 'Nota', executive_summary: 'Resumo executivo',
  media_plan: 'Plano de mídia', scenario: 'Cenário', research: 'Pesquisa', project_map: 'Mapa do projeto',
  html: 'Página interativa', image: 'Imagem', spreadsheet: 'Planilha', report: 'Relatório',
  resource: 'Arquivo', brand_identity: 'Marca', project_profile: 'Projeto', meeting_summary: 'Resumo de reunião', meeting_agenda: 'Pauta',
  link_reader: 'Referência',
  library: 'Biblioteca',
};

function comparableLines(content) {
  const html = String(content?.html || '');
  if (html) return html.split(/<\/(?:p|li|h[1-6]|blockquote|div)>/i)
    .map(part => part.replace(/<[^>]*>/g, ' ').replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/\s+/g, ' ').trim())
    .filter(Boolean);
  return Object.entries(content || {}).filter(([key]) => !['title', '_provenance'].includes(key))
    .map(([key, value]) => `${key}: ${typeof value === 'string' ? value : JSON.stringify(value)}`);
}

function versionChanges(before, after) {
  const oldLines = comparableLines(before), newLines = comparableLines(after);
  const oldSet = new Set(oldLines), newSet = new Set(newLines);
  return {removed: oldLines.filter(line => !newSet.has(line)).slice(0, 12), added: newLines.filter(line => !oldSet.has(line)).slice(0, 12)};
}

function LibraryArtifact({artifact, onOpenResource}) {
  const groups = Array.isArray(artifact.content?.groups) ? artifact.content.groups : [];
  const drag = (event, item) => {
    event.dataTransfer.effectAllowed = 'copy';
    event.dataTransfer.setData('application/x-cadu-item', JSON.stringify({...item, type: 'resource', resourceRef: item.id}));
  };
  return <div className="cv-library-artifact">
    {groups.map(group => <section key={group.id} className={`cv-library-strip is-${group.id}`}>
      <header><h3>{group.title}</h3><span>{group.items.length}</span></header>
      <div className={group.layout === 'list' ? 'is-list' : 'is-carousel'}>
        {group.items.map(item => <button key={item.id || item.url} type="button" draggable onDragStart={event => drag(event, item)} onClick={() => onOpenResource?.(item)} title={item.title}>
          {item.preview ? <img src={safeUrl(item.preview)} alt="" loading="lazy"/> : <Icon name={item.kind === 'link' ? 'link' : 'file'} size={17}/>}<span>{item.title}</span>{item.detail && <small>{item.detail}</small>}
        </button>)}
      </div>
    </section>)}
    {!groups.some(group => group.items.length) && <p className="cv-library-empty">Os materiais do projeto aparecerão aqui.</p>}
  </div>;
}

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
    <EditableTextarea className="cv-artifact-summary" value={content.summary || ''} onChange={value => onChange({...content, summary: value})} placeholder="Resumo do trabalho" aria-label="Resumo da entrega"/>
    <div className="cv-mt-7 cv-grid cv-gap-1">{(content.fields || []).map((field, index) => <label key={`${field.key}-${index}`} className="cv-block cv-border-t cv-border-white/[.07] cv-py-5">
      <span className="cv-mb-2 cv-block cv-text-xs cv-font-semibold cv-text-[#78918d]">{field.key || `Seção ${index + 1}`}</span>
      <EditableTextarea value={field.value || ''} onChange={value => updateField(index, value)} aria-label={field.key || `Seção ${index + 1}`}/>
    </label>)}</div>
  </article>;
}

const meetingSectionAliases = {
  participantes: ['participantes', 'presentes', 'pessoas'],
  contexto: ['contexto', 'objetivo', 'assunto'],
  decisoes: ['decisões', 'decisoes', 'decisões tomadas'],
  encaminhamentos: ['encaminhamentos', 'próximos passos', 'proximos passos', 'ações', 'acoes'],
  pendencias: ['pendências', 'pendencias', 'pontos em aberto'],
};

function meetingFieldKind(key = '') {
  const normalized = String(key).trim().toLocaleLowerCase('pt-BR');
  return Object.entries(meetingSectionAliases).find(([, aliases]) => aliases.includes(normalized))?.[0] || 'other';
}

function MeetingSummaryArtifact({artifact, onChange}) {
  const content = artifact.content || {};
  const fields = Array.isArray(content.fields) ? content.fields : [];
  const updateSummary = summary => onChange({...content, summary});
  const updateField = (index, value) => onChange({...content, fields: fields.map((field, fieldIndex) => fieldIndex === index ? {...field, value} : field)});
  return <article className="cv-meeting-summary cv-mx-auto cv-w-full cv-max-w-[820px]">
    <header className="cv-meeting-summary__intro">
      <span><Icon name="calendar" size={15}/>Registro da reunião</span>
      <EditableTextarea value={content.summary || ''} onChange={updateSummary} placeholder="Escreva uma síntese objetiva da reunião." aria-label="Síntese da reunião"/>
    </header>
    <div className="cv-meeting-summary__sections">
      {fields.map((field, index) => {
        const kind = meetingFieldKind(field.key);
        return <section key={`${field.key}-${index}`} className={`cv-meeting-summary__section is-${kind}`}>
          <h3>{field.key || `Seção ${index + 1}`}</h3>
          <EditableTextarea value={field.value || ''} onChange={value => updateField(index, value)} placeholder="Adicione as informações confirmadas." aria-label={field.key || `Seção ${index + 1}`}/>
        </section>;
      })}
      {!fields.length && <p className="cv-meeting-summary__empty">O resumo ainda não possui decisões, responsáveis ou próximos passos registrados.</p>}
    </div>
  </article>;
}

function escapeHtml(value) {
  return String(value || '').replace(/[&<>"']/g, char => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[char]));
}

function documentHtml(content) {
  if (content.html) {
    const raw = String(content.html);
    const clean = raw.trim();
    if (clean.startsWith('{') || clean.startsWith('"{')) {
      try {
        let decoded = JSON.parse(clean);
        if (typeof decoded === 'string') decoded = JSON.parse(decoded);
        const visible = decoded?.text?.content || decoded?.answer;
        if (typeof visible === 'string' && visible.trim()) {
          return visible.trim().split(/\n\s*\n/).map(part => `<p>${escapeHtml(part).replace(/\n/g, '<br/>')}</p>`).join('');
        }
        return '<p><br/></p>';
      } catch (_) {
        // An incomplete protocol envelope must not become editable content.
        if (/^\s*["']?\s*\{\s*"(?:text|ui|answer|artifact_patch)"/i.test(clean)) return '<p><br/></p>';
      }
    }
    return raw;
  }
  const sections = [];
  if (content.summary) sections.push(`<p>${escapeHtml(content.summary)}</p>`);
  (content.fields || []).forEach(field => {
    if (field?.key) sections.push(`<h2>${escapeHtml(field.key)}</h2>`);
    if (field?.value) sections.push(`<p>${escapeHtml(field.value).replace(/\n/g, '<br/>')}</p>`);
  });
  return sections.join('') || '<p><br/></p>';
}

function downloadTextArtifact(artifact, format) {
  const html = artifact.type === 'html' ? htmlDocument(artifact.content || {}, artifact.title) : documentHtml(artifact.content || {});
  const plain = new DOMParser().parseFromString(html, 'text/html').body.textContent?.trim() || '';
  const title = String(artifact.title || 'documento').normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9_-]+/gi, '-').replace(/^-+|-+$/g, '').toLowerCase() || 'documento';
  const markdown = artifact.type === 'html' ? `# ${artifact.title || 'Documento'}\n\n${plain}` : `# ${artifact.title || 'Documento'}\n\n${plain}`;
  const data = format === 'html' ? html : format === 'md' ? markdown : plain;
  const blob = new Blob([data], {type: format === 'html' ? 'text/html;charset=utf-8' : 'text/plain;charset=utf-8'});
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a'); link.href = url; link.download = `${title}.${format}`; link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function cleanDocumentHtml(html) {
  const doc = new DOMParser().parseFromString(String(html || ''), 'text/html');
  const allowed = new Set(['P', 'BR', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'STRONG', 'B', 'EM', 'I', 'U', 'S', 'BLOCKQUOTE', 'UL', 'OL', 'LI', 'A', 'IMG', 'TABLE', 'THEAD', 'TBODY', 'TFOOT', 'TR', 'TH', 'TD', 'DIV', 'SPAN', 'PRE', 'CODE', 'HR', 'SUP', 'SUB']);
  const discard = new Set(['SCRIPT', 'STYLE', 'IFRAME', 'OBJECT', 'EMBED', 'FORM', 'META', 'LINK', 'SVG', 'MATH', 'TEMPLATE', 'INPUT', 'BUTTON', 'TEXTAREA', 'SELECT', 'VIDEO', 'AUDIO']);
  const visit = node => {
    for (const child of Array.from(node.children)) {
      if (discard.has(child.tagName)) { child.remove(); continue; }
      visit(child);
      if (!allowed.has(child.tagName)) { child.replaceWith(...Array.from(child.childNodes)); continue; }
      for (const attribute of Array.from(child.attributes)) child.removeAttribute(attribute.name);
    }
  };
  // Keep only document formatting and safe links/images, never executable markup.
  const links = Array.from(doc.body.querySelectorAll('a')).map(node => [node, node.getAttribute('href')]);
  const images = Array.from(doc.body.querySelectorAll('img')).map(node => [node, node.getAttribute('src'), node.getAttribute('alt')]);
  visit(doc.body);
  for (const [node, raw] of links) {
    if (!node.isConnected) continue;
    const url = safeUrl(raw);
    if (url) { node.setAttribute('href', url); node.setAttribute('rel', 'noopener noreferrer'); node.setAttribute('target', '_blank'); }
  }
  for (const [node, raw, alt] of images) {
    if (!node.isConnected) continue;
    const imageData = /^data:image\/(?:png|jpeg|webp|gif);base64,[a-z0-9+/=]+$/i.test(raw || '');
    const url = imageData ? raw : safeUrl(raw);
    if (url) node.setAttribute('src', url);
    if (alt) node.setAttribute('alt', alt);
  }
  return doc.body.innerHTML;
}

function RichDocumentArtifact({artifact, onChange, editing = false}) {
  const content = artifact.content || {};
  const canvas = useRef(null);
  const urlInput = useRef(null);
  const [urlRequest, setUrlRequest] = useState(null);
  const html = useMemo(() => cleanDocumentHtml(documentHtml(content)), [content]);
  const reading = useMemo(() => {
    const doc = new DOMParser().parseFromString(html, 'text/html');
    const sections = Array.from(doc.body.querySelectorAll('h1,h2,h3')).map((node, index) => {
      const id = `cadu-section-${index}`;
      node.id = id;
      return {id, title: node.textContent?.trim() || `Seção ${index + 1}`, level: node.tagName};
    });
    return {html: doc.body.innerHTML, sections};
  }, [html]);
  useEffect(() => {
    if (!canvas.current || canvas.current.innerHTML === html) return;
    if (document.activeElement !== canvas.current) canvas.current.innerHTML = html;
  }, [artifact.id, html]);
  const emit = () => onChange({...content, html: cleanDocumentHtml(canvas.current?.innerHTML || '')});
  const command = (name, value = null) => {
    canvas.current?.focus();
    document.execCommand(name, false, value);
    emit();
  };
  const applyUrl = event => {
    event.preventDefault();
    const url = safeUrl(new FormData(event.currentTarget).get('url'));
    if (!url) return;
    command(urlRequest === 'image' ? 'insertImage' : 'createLink', url);
    setUrlRequest(null);
  };
  const pasteIntoDocument = event => {
    const image = Array.from(event.clipboardData?.items || []).find(item => item.type.startsWith('image/'));
    if (!image) {
      const pastedHtml = event.clipboardData?.getData('text/html');
      if (pastedHtml) {
        event.preventDefault();
        command('insertHTML', cleanDocumentHtml(pastedHtml));
      }
      return;
    }
    const file = image.getAsFile();
    if (!file) return;
    event.preventDefault();
    const reader = new FileReader();
    reader.onload = () => command('insertImage', String(reader.result || ''));
    reader.readAsDataURL(file);
  };
  const addTable = () => {
    command('insertHTML', '<table><thead><tr><th>Item</th><th>Valor</th><th>Observação</th></tr></thead><tbody><tr><td>Exemplo</td><td>—</td><td>Edite este campo</td></tr><tr><td>Outro item</td><td>—</td><td>Edite este campo</td></tr></tbody></table><p><br></p>');
  };
  if (!editing) return <div className="cv-artifact-reading">
    {reading.sections.length > 1 && <nav className="cv-artifact-reading__toc" aria-label="Seções do documento"><strong>Neste material</strong>{reading.sections.map(section => <a key={section.id} className={section.level === 'H3' ? 'is-nested' : ''} href={`#${section.id}`}>{section.title}</a>)}</nav>}
    <article className="cv-rich-document cv-rich-document--reading cv-mx-auto cv-w-full cv-max-w-[860px] cv-px-6 cv-py-5 md:cv-px-8 md:cv-py-6"><div className="cv-rich-document__canvas" dangerouslySetInnerHTML={{__html: reading.html}}/></article>
  </div>;
  return <article className="cv-rich-document cv-mx-auto cv-w-full cv-max-w-[860px] cv-px-6 cv-py-5 md:cv-px-8 md:cv-py-6">
    <div className="cv-rich-document__toolbar" role="toolbar" aria-label="Formatação do documento" onMouseDown={event => event.preventDefault()}>
      <button type="button" onClick={() => command('undo')} aria-label="Desfazer última edição" title="Desfazer"><Icon name="undo" size={16}/></button>
      <button type="button" onClick={() => command('redo')} aria-label="Refazer edição" title="Refazer"><Icon name="redo" size={16}/></button>
      <button type="button" onClick={() => command('bold')} aria-label="Negrito"><b>B</b></button>
      <button type="button" onClick={() => command('italic')} aria-label="Itálico"><i>I</i></button>
      <button type="button" onClick={() => command('formatBlock', 'h2')} aria-label="Título de seção">H2</button>
      <button type="button" onClick={() => command('formatBlock', 'blockquote')} aria-label="Citação" title="Citação"><Icon name="quote" size={16}/></button>
      <button type="button" onClick={() => command('insertUnorderedList')} aria-label="Lista" title="Lista"><Icon name="list" size={16}/></button>
      <button type="button" onClick={() => setUrlRequest('link')} aria-label="Adicionar link" title="Adicionar link"><Icon name="link" size={16}/></button>
      <button type="button" onClick={addTable} aria-label="Inserir tabela" title="Inserir tabela"><Icon name="table" size={16}/></button>
      <button type="button" onClick={() => setUrlRequest('image')} aria-label="Adicionar imagem" title="Adicionar imagem"><Icon name="image" size={16}/></button>
    </div>
    <div ref={canvas} className="cv-rich-document__canvas" contentEditable suppressContentEditableWarning onInput={emit} onBlur={emit} onPaste={pasteIntoDocument} dangerouslySetInnerHTML={{__html: html}} role="textbox" aria-label="Texto do documento"/>
    <p className="cv-rich-document__hint">Cole textos, links e imagens diretamente · salvamento automático</p>
    {urlRequest && <CaduDialog label={urlRequest === 'image' ? 'Adicionar imagem' : 'Adicionar link'} initialFocusRef={urlInput} onClose={() => setUrlRequest(null)} className="cv-dialog cv-artifact-url-dialog">
      <form onSubmit={applyUrl}>
        <header><div><h2>{urlRequest === 'image' ? 'Adicionar imagem' : 'Adicionar link'}</h2><p>Cole um endereço HTTPS válido.</p></div><button type="button" onClick={() => setUrlRequest(null)} aria-label="Fechar"><Icon name="close" size={18}/></button></header>
        <label>Endereço<input ref={urlInput} name="url" type="url" inputMode="url" required pattern="https://.*" placeholder="https://" autoComplete="url"/></label>
        <footer><button type="button" onClick={() => setUrlRequest(null)}>Cancelar</button><button type="submit" className="is-primary">Adicionar</button></footer>
      </form>
    </CaduDialog>}
  </article>;
}

function HtmlArtifact({artifact}) {
  const content = artifact.content || {};
  if (!String(content.html || '').trim()) {
    const malformed = /^\s*(?:```(?:json)?\s*)?\{\s*"(?:text|ui|answer|artifact_patch)"/i.test(String(content.summary || ''));
    return <div className="cv-artifact-loading is-failed" role="alert"><strong>{malformed ? 'A geração retornou um formato inválido' : 'Esta página não possui conteúdo'}</strong><span>{malformed ? 'O sistema preservou a versão para diagnóstico, mas ela não pode ser renderizada. Peça ao Cadu para regenerar o HTML completo.' : 'O HTML desta versão não foi gerado. Peça ao Cadu para criar novamente o dashboard.'}</span></div>;
  }
  return <iframe title={artifact.title || 'Página interativa'} sandbox="allow-scripts" referrerPolicy="no-referrer" srcDoc={htmlDocument(content, artifact.title)} className="cv-h-full cv-w-full cv-border-0 cv-bg-white"/>;
}

function imageSource(artifact) {
  const content = artifact?.content || {};
  return safeUrl(content.url || content.image_url || content.src);
}

function imageFileName(artifact) {
  const content = artifact?.content || {};
  const explicit = content.filename || content.file_name || artifact?.filename;
  if (explicit) return String(explicit);
  const title = String(artifact?.title || content.title || '').trim();
  if (title && !/^ativo da marca$/i.test(title)) return title;
  const src = imageSource(artifact);
  if (src) {
    try {
      const pathname = new URL(src, window.location.origin).pathname;
      const candidate = decodeURIComponent(pathname.split('/').filter(Boolean).pop() || '');
      if (candidate) return candidate;
    } catch (_) { /* A URL já foi validada por safeUrl. */ }
  }
  return 'imagem.png';
}

function imageStudioLink(artifact, studioEditorUrl, projectRef, mode = 'select', prompt = '') {
  const content = artifact.content || {};
  const src = imageSource(artifact);
  if (!src || !studioEditorUrl) return '';
  const url = new URL(studioEditorUrl, window.location.origin);
  url.searchParams.set('source_url', src);
  url.searchParams.set('source_title', imageFileName(artifact) || content.alt || 'Imagem de referência');
  url.searchParams.set('editor_mode', mode);
  if (prompt) url.searchParams.set('instruction', prompt);
  const projectId = String(projectRef || '').replace(/^ci:/, '');
  if (projectId) url.searchParams.set('project_id', projectId);
  return url.href;
}

function ImageArtifact({artifact, onMetadata}) {
  const content = artifact.content || {};
  const src = imageSource(artifact);
  useEffect(() => {
    const knownBytes = Number(content.file_size || content.size || artifact.file_size || artifact.size || 0);
    onMetadata?.({
      width: Number(content.width || artifact.width || 0),
      height: Number(content.height || artifact.height || 0),
      bytes: knownBytes,
      mime: content.mime_type || content.content_type || artifact.mime_type || '',
    });
    if (!src || knownBytes) return undefined;
    const controller = new AbortController();
    fetch(src, {method: 'HEAD', credentials: 'same-origin', signal: controller.signal}).then(response => {
      if (!response.ok) return;
      onMetadata?.({bytes: Number(response.headers.get('content-length') || 0), mime: response.headers.get('content-type') || ''});
    }).catch(() => {});
    return () => controller.abort();
  }, [artifact.file_size, artifact.height, artifact.size, artifact.width, content.content_type, content.file_size, content.height, content.mime_type, content.size, content.width, onMetadata, src]);
  const reportMetadata = event => onMetadata?.({
    width: event.currentTarget.naturalWidth,
    height: event.currentTarget.naturalHeight,
    bytes: Number(content.file_size || content.size || artifact.file_size || artifact.size || 0),
    mime: content.mime_type || content.content_type || artifact.mime_type || '',
  });
  return <div className="cv-image-artifact">
    {src ? <figure><img src={src} alt={content.alt || imageFileName(artifact)} onLoad={reportMetadata}/></figure> : <p>A imagem ainda não está disponível.</p>}
  </div>;
}

function formatFileSize(bytes) {
  const value = Number(bytes || 0);
  if (!value) return 'Não informado';
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${Math.round(value / 1024)} KB`;
  return `${(value / (1024 * 1024)).toLocaleString('pt-BR', {maximumFractionDigits: 1})} MB`;
}

function compactArtifactTitle(artifact) {
  const title = artifact?.type === 'image' ? imageFileName(artifact) : String(artifact?.title || 'Entrega').trim();
  const words = title.split(/\s+/).filter(Boolean);
  return words.length > 3 ? `${words.slice(0, 3).join(' ')}…` : title;
}

function artifactTabIcon(artifact) {
  const content = artifact?.content || {};
  const haystack = `${artifact?.title || ''} ${content.provider || ''} ${content.url || content.editor_url || ''}`.toLowerCase();
  if (haystack.includes('drive.google.com') || haystack.includes('google drive')) return 'drive';
  if (artifact?.type === 'image') return 'image';
  if (artifact?.type === 'html') return 'browser';
  if (artifact?.type === 'link_reader' || /^https?:/i.test(content.url || '')) return 'link';
  return 'file';
}

function artifactBrowserUrl(artifact, publishedUrl = '') {
  const content = artifact?.content || {};
  return safeUrl(
    publishedUrl
    || artifact?.published_url
    || artifact?.public_url
    || content.published_url
    || content.public_url
    || content.editor_url
    || content.download_url
    || content.url
    || content.image_url
    || content.src,
  );
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
  const project = safeUrl(content.project_href);
  const createCopy = async () => {
    if (!editableCopy || creating) return;
    setCreating(true); setError('');
    try {
      const data = await request(editableCopy, {method: 'POST', headers: {'X-CSRF-Token': csrf()}});
      setCreated(data.document || null);
    } catch (reason) { setError(reason.message); }
    finally { setCreating(false); }
  };
  return <article className="cv-link-reader cv-mx-auto cv-flex cv-h-full cv-w-full cv-max-w-[720px] cv-flex-col cv-justify-center cv-p-8 md:cv-p-12">
    <span className="cv-grid cv-h-11 cv-w-11 cv-place-items-center cv-rounded-xl cv-bg-teal/10 cv-text-teal"><Icon name="file" size={20}/></span>
    <h3 className="cv-mb-0 cv-mt-5 cv-text-xl cv-font-semibold cv-tracking-[-.02em]">{artifact.title}</h3>
    <p className="cv-mb-0 cv-mt-2 cv-text-sm cv-leading-6 cv-text-[#819b97]">{content.detail || `${content.kind || 'Arquivo'} conectado a esta conversa.`}</p>
    <div className="cv-mt-6 cv-flex cv-flex-wrap cv-gap-2">
      {editor && <a href={editor} target="_blank" rel="noreferrer" className="cv-rounded-lg cv-bg-teal cv-px-4 cv-py-2.5 cv-text-xs cv-font-semibold cv-text-[#052522] cv-no-underline">{created ? 'Abrir documento editável' : 'Abrir arquivo'}</a>}
      {!created && editableCopy && <button type="button" onClick={createCopy} disabled={creating} className="cv-rounded-lg cv-border cv-border-white/10 cv-bg-transparent cv-px-4 cv-py-2.5 cv-text-xs cv-font-semibold disabled:cv-opacity-50">{creating ? 'Preparando…' : 'Criar versão editável'}</button>}
      {download && download !== editor && <a href={download} className="cv-rounded-lg cv-border cv-border-white/10 cv-px-4 cv-py-2.5 cv-text-xs cv-font-semibold cv-text-[#c4d5d2] cv-no-underline">Baixar</a>}
      {!editor && !editableCopy && !download && project && <a href={project} className="cv-rounded-lg cv-bg-teal cv-px-4 cv-py-2.5 cv-text-xs cv-font-semibold cv-text-[#052522] cv-no-underline">{content.project_link_label || 'Ver no projeto'}</a>}
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
  const isPublic = content.access_type === 'public' || /p[uú]blico/i.test(String(content.kind || content.access_mode || '')) || (!isGoogle && Boolean(url));
  let embedded = isPublic ? url : '';
  if (/youtu\.be|youtube\.com/i.test(domain)) {
    try {
      const parsed = new URL(url);
      const videoId = domain === 'youtu.be' ? parsed.pathname.slice(1) : parsed.searchParams.get('v');
      if (videoId) embedded = `https://www.youtube-nocookie.com/embed/${encodeURIComponent(videoId)}`;
    } catch (_) {}
  }
  if (/docs\.google\.com/i.test(domain)) {
    embedded = url.replace(/\/(edit|view)(?:\?.*)?$/i, '/preview');
  }
  if (/drive\.google\.com/i.test(domain)) {
    const file = url.match(/\/file\/d\/([^/]+)/i);
    const folder = url.match(/\/(?:drive\/)?folders\/([^/?]+)/i);
    if (file) embedded = `https://drive.google.com/file/d/${encodeURIComponent(file[1])}/preview`;
    else if (folder) embedded = `https://drive.google.com/embeddedfolderview?id=${encodeURIComponent(folder[1])}#list`;
  }
  if (embedded) return <article className="cv-link-embed cv-flex cv-h-full cv-min-h-0 cv-w-full cv-flex-col">
    <header className="cv-link-embed__bar">
      <span><Icon name="external" size={15}/><b>{artifact.title || domain}</b><small>{domain}</small></span>
      <div>{!isGoogle && !isMeeting && <button type="button" onClick={() => onRequestSummary?.(url)}>Resumir</button>}<button type="button" onClick={() => onSaveReference?.(url)}>Salvar referência</button><a href={url} target="_blank" rel="noreferrer">Abrir fora</a></div>
    </header>
    <iframe title={artifact.title || domain || 'Link público'} src={embedded} sandbox="allow-scripts allow-forms allow-popups allow-popups-to-escape-sandbox" referrerPolicy="strict-origin-when-cross-origin" className="cv-link-embed__frame"/>
    <footer>Se o site bloquear a visualização incorporada, use “Abrir fora”.</footer>
  </article>;
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
    <p className="cv-mb-0 cv-mt-4 cv-text-xs cv-leading-5 cv-text-[#71908b]">{isGoogle ? 'Você pode guardar o link mesmo sem integração. Para conteúdo privado, o Google poderá solicitar acesso.' : 'O conteúdo só será extraído depois de escolher “Abrir e resumir”.'}</p>
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

function ProjectProfileArtifact({artifact}) {
  const content = artifact.content || {};
  const missing = [
    !content.description && 'Adicionar uma descrição curta do propósito e do resultado esperado.',
    !content.instructions && 'Registrar orientações, limites e critérios para o trabalho.',
    !content.brands?.length && 'Vincular uma marca quando decisões precisarem herdar sua identidade.',
  ].filter(Boolean);
  const visibility = {private: 'Privado', team: 'Equipe', restricted: 'Acesso definido'}[content.visibility] || content.visibility || 'Privado';
  const date = value => value ? new Intl.DateTimeFormat('pt-BR', {dateStyle: 'medium'}).format(new Date(value)) : '';
  return <article className="cv-project-profile cv-mx-auto cv-w-full cv-max-w-[760px] cv-p-8 md:cv-p-12">
    <header className="cv-project-profile__header"><span style={{background: content.color || '#176b5e'}}><Icon name="folder" size={20}/></span><div><p>Projeto ativo no chat</p><h3>{content.name || artifact.title}</h3><small>{content.status === 'ativo' ? 'Em andamento' : content.status} · {visibility}</small></div></header>
    <p className="cv-project-profile__description">{content.description || 'Este projeto ainda não tem uma descrição. Defina em poucas linhas o que será realizado, para quem e qual resultado deve orientar as decisões.'}</p>
    <section className="cv-project-profile__stats" aria-label="Metadados do projeto"><div><b>{content.file_count || 0}</b><span>arquivos</span></div><div><b>{content.conversation_count || 0}</b><span>conversas</span></div><div><b>{content.brands?.length || 0}</b><span>marcas vinculadas</span></div></section>
    {content.instructions && <section className="cv-project-profile__section"><h4>Como trabalhar neste projeto</h4><p>{content.instructions}</p></section>}
    {!!content.brands?.length && <section className="cv-project-profile__section"><h4>Contexto de marca</h4><div className="cv-project-profile__brands">{content.brands.map(brand => <span key={brand.ref}>{brand.name}</span>)}</div></section>}
    {!!missing.length && <section className="cv-project-profile__next"><h4>Para deixar o contexto mais útil</h4>{missing.map(item => <p key={item}>{item}</p>)}</section>}
    <footer className="cv-project-profile__meta">{date(content.created_at) && <span>Criado em {date(content.created_at)}</span>}{date(content.updated_at) && <span>Atualizado em {date(content.updated_at)}</span>}</footer>
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

export function ArtifactPane({artifact, mobile = false, tabs = [], activeTabKey = '', onSelectTab, onCloseTab, onCloseOtherTabs, onCloseAllTabs, dirty, saving, publishing, publishedUrl, side = 'right', onSideChange, onChange, onTitleChange, projectRef, projects = [], studioEditorUrl, onSaveToProject, onAttachToProject, onMoveToProject, onPublish, onCopyPublishedUrl, onUnpublish, onClose, onSave, onLoadVersions, versions, onRestoreVersion, onRequestSummary, onSaveReference, onRequestMeetingPlan, onOrganizeImage, onOpenResource}) {
  const dialog = useRef(null);
  const closeTimer = useRef(null);
  const [loadingVersions, setLoadingVersions] = useState(false);
  const [comparison, setComparison] = useState(null);
  const [comparingVersion, setComparingVersion] = useState(null);
  const [closing, setClosing] = useState(false);
  const [lightTheme, setLightTheme] = useState(false);
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleDraft, setTitleDraft] = useState('');
  const [imageMetadata, setImageMetadata] = useState(null);
  const [organizingImage, setOrganizingImage] = useState(false);
  const [tabMenu, setTabMenu] = useState(null);
  const [editingDocument, setEditingDocument] = useState(false);
  const [sourceFormat, setSourceFormat] = useState('md');
  const type = artifact?.type || 'document';
  const indexable = artifact?.capabilities?.indexable ?? !['html', 'project_map', 'link_reader'].includes(type);
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
    if (artifact.pending) return <div className="cv-artifact-loading" role="status" aria-live="polite"><i/><strong>Preparando a entrega</strong><span>O conteúdo aparecerá aqui quando estiver pronto.</span></div>;
    if (artifact.failed) return <div className="cv-artifact-loading is-failed" role="status"><strong>A entrega não foi concluída</strong><span>{artifact.error}</span></div>;
    if (type === 'html') return <HtmlArtifact artifact={artifact}/>;
    if (type === 'project_map') return <ProjectMap artifact={artifact} onChange={onChange}/>;
    if (type === 'image') return <ImageArtifact artifact={artifact} onMetadata={next => setImageMetadata(current => ({...(current || {}), ...next}))}/>;
    if (type === 'resource') return <ResourceArtifact artifact={artifact}/>;
    if (type === 'link_reader') return <LinkReaderArtifact artifact={artifact} onRequestSummary={onRequestSummary} onSaveReference={onSaveReference} onRequestMeetingPlan={onRequestMeetingPlan}/>;
    if (type === 'brand_identity') return <BrandIdentityArtifact artifact={artifact}/>;
    if (type === 'project_profile') return <ProjectProfileArtifact artifact={artifact}/>;
    if (type === 'library') return <LibraryArtifact artifact={artifact} onOpenResource={onOpenResource}/>;
    return textArtifact
      ? <RichDocumentArtifact artifact={artifact} onChange={onChange} editing={editingDocument}/>
      : <StructuredArtifact artifact={artifact} onChange={onChange}/>;
  }, [artifact, type, textArtifact, editingDocument, onChange, onTitleChange, onRequestSummary, onSaveReference, onRequestMeetingPlan, onOpenResource]);
  useEffect(() => {
    setClosing(false);
    setEditingTitle(false);
    setEditingDocument(false);
    let preferred = 'md';
    try {
      preferred = window.sessionStorage.getItem('cadu:next-file-format') || 'md';
      if (artifact?.id) window.sessionStorage.removeItem('cadu:next-file-format');
    } catch (_) { /* Storage may be unavailable. */ }
    setSourceFormat(artifact?.type === 'html' ? 'html' : preferred === 'txt' ? 'txt' : 'md');
    setTitleDraft(type === 'image' ? imageFileName(artifact) : (artifact?.title || artifact?.content?.title || 'Trabalho em andamento'));
    setImageMetadata(null);
    setOrganizingImage(false);
    if (dialog.current?.open) dialog.current.close();
    return () => window.clearTimeout(closeTimer.current);
  }, [artifact?.id, artifact?.tabKey]);
  useEffect(() => {
    if (!tabMenu) return undefined;
    const closeMenu = event => {
      if (event.type === 'keydown' && event.key !== 'Escape') return;
      setTabMenu(null);
    };
    window.addEventListener('pointerdown', closeMenu);
    window.addEventListener('keydown', closeMenu);
    return () => {
      window.removeEventListener('pointerdown', closeMenu);
      window.removeEventListener('keydown', closeMenu);
    };
  }, [tabMenu]);
  const displayTitle = type === 'image' ? imageFileName(artifact) : (artifact.title || artifact.content?.title || 'Trabalho em andamento');
  const publicLink = type === 'html' && artifact.id && artifact.status === 'published'
    ? publishedUrl || `${window.location.origin}/public/cadu/artifacts/${encodeURIComponent(artifact.id)}` : '';
  const commitTitle = () => {
    const next = titleDraft.trim();
    if (next && next !== displayTitle) onTitleChange?.(next);
    setEditingTitle(false);
  };
  const src = type === 'image' ? imageSource(artifact) : '';
  const imageEditUrl = type === 'image' ? imageStudioLink(artifact, studioEditorUrl, projectRef) : '';
  const organizeImage = async () => {
    if (organizingImage || !onOrganizeImage) return;
    setOrganizingImage(true);
    try { await onOrganizeImage(artifact); }
    finally { setOrganizingImage(false); }
  };
  const requestClose = () => {
    setClosing(true);
    window.clearTimeout(closeTimer.current);
    closeTimer.current = window.setTimeout(onClose, 180);
  };
  const openVersions = async () => {
    setLoadingVersions(true);
    setComparison(null);
    dialog.current?.showModal();
    await onLoadVersions();
    setLoadingVersions(false);
  };
  const compareVersion = async version => {
    setComparingVersion(version);
    try {
      const data = await request(`/workspace/api/v2/artifacts/${encodeURIComponent(artifact.id)}/versions/${version}`);
      setComparison({version, ...versionChanges(data.version?.content, artifact.content)});
    } catch (error) { setComparison({version, error: error.message || 'Não foi possível comparar as versões.'}); }
    finally { setComparingVersion(null); }
  };
  if (!artifact) return null;
  return <aside className={`cv-artifact-panel cv-artifact-overlay cv-artifact-panel--${side} cv-relative cv-flex cv-h-full cv-flex-none cv-flex-col cv-border-l cv-border-white/[.08] cv-bg-panel ${lightTheme && textArtifact ? 'is-light' : ''} ${closing ? 'cv-is-closing' : ''}`} aria-label="Entrega">
    {tabs.length > 0 && <nav className="cv-artifact-tabs" aria-label="Entregas abertas">{tabs.map(item => {
      const key = String(item.tabKey || item.id || '');
      const itemTitle = item.type === 'image' ? imageFileName(item) : (item.title || 'Entrega');
      return <div key={key} className={key === activeTabKey ? 'is-active' : ''} onContextMenu={event => { event.preventDefault(); setTabMenu({item, key, x: Math.min(event.clientX, window.innerWidth - 218), y: Math.min(event.clientY, window.innerHeight - 190)}); }}><button type="button" onClick={() => onSelectTab?.(item)} title={itemTitle}>{item.pending ? <i/> : <Icon name={artifactTabIcon(item)} size={13}/>}<span>{compactArtifactTitle(item)}</span></button><button type="button" onClick={() => onCloseTab?.(key)} aria-label={`Fechar ${itemTitle}`}>×</button></div>;
    })}</nav>}
    {tabMenu && <div className="cv-artifact-tab-menu" style={{left: tabMenu.x, top: tabMenu.y}} role="menu" onPointerDown={event => event.stopPropagation()}>
      <button type="button" role="menuitem" onClick={() => { onCloseTab?.(tabMenu.key); setTabMenu(null); }}>Fechar aba</button>
      <button type="button" role="menuitem" disabled={tabs.length < 2} onClick={() => { onCloseOtherTabs?.(tabMenu.key); setTabMenu(null); }}>Fechar outras abas</button>
      <button type="button" role="menuitem" onClick={() => { onCloseAllTabs?.(); setTabMenu(null); }}>Fechar todas</button>
      {artifactBrowserUrl(tabMenu.item, tabMenu.key === activeTabKey ? publishedUrl : '') && <a role="menuitem" href={artifactBrowserUrl(tabMenu.item, tabMenu.key === activeTabKey ? publishedUrl : '')} target="_blank" rel="noreferrer"><Icon name="external" size={13}/>Abrir no navegador</a>}
      {tabMenu.item.type === 'html' && tabMenu.item.status !== 'published' && tabMenu.key === activeTabKey && <button type="button" role="menuitem" disabled={publishing || saving} onClick={() => { onPublish?.(); setTabMenu(null); }}><Icon name="external" size={13}/>Publicar</button>}
    </div>}
    <header className="cv-flex cv-h-[52px] cv-flex-none cv-items-center cv-gap-2 cv-border-b cv-border-white/[.07] cv-px-4">
      <div className="cv-min-w-0 cv-flex-1">{type !== 'image' && <span className="cv-flex cv-items-center cv-gap-2 cv-text-[11px] cv-font-medium cv-text-[#759a95]">{labels[type] || 'Entrega'}{dirty && <i className="cv-h-1.5 cv-w-1.5 cv-rounded-full cv-bg-[#e3a45f]" title="Alterações não salvas"/>}</span>}{type === 'image' || textArtifact ? editingTitle ? <input autoFocus className="cv-artifact-title-input" value={titleDraft} onChange={event => setTitleDraft(event.target.value)} onBlur={commitTitle} onKeyDown={event => { if (event.key === 'Enter') commitTitle(); if (event.key === 'Escape') setEditingTitle(false); }} aria-label={type === 'image' ? 'Nome do arquivo' : 'Título do documento'}/> : <button type="button" className="cv-artifact-title-button" onClick={() => { setTitleDraft(displayTitle); setEditingTitle(true); }} title="Clique para editar o título">{displayTitle}{dirty && <i className="cv-artifact-title-dirty" title="Alterações não salvas"/>}</button> : <h2 className="cv-m-0 cv-mt-1 cv-overflow-hidden cv-text-ellipsis cv-whitespace-nowrap cv-text-[15px] cv-font-semibold">{displayTitle}</h2>}</div>
      {type === 'html' && artifact.id && <button type="button" onClick={publicLink ? onCopyPublishedUrl : onPublish} disabled={publishing || saving} className="cv-artifact-publish">{publishing ? 'Publicando…' : saving ? 'Salvando…' : publicLink ? 'Copiar link' : 'Publicar'}</button>}
      {textArtifact && !artifact.pending && !artifact.failed && <button type="button" className="cv-artifact-edit-mode" onClick={() => setEditingDocument(value => !value)}>{editingDocument ? 'Visualizar' : 'Editar'}</button>}
      {!artifact.pending && !artifact.failed && <details className="cv-artifact-more">
        <summary aria-label="Mais ações da entrega">Ações <span aria-hidden="true">⌄</span></summary>
        <div>
          {type === 'image' && imageEditUrl && <a href={imageEditUrl} target="_blank" rel="noreferrer" className="is-primary">Editar no Studio</a>}
          {type === 'image' && src && <button type="button" disabled={organizingImage} onClick={organizeImage}>{organizingImage ? 'Analisando imagem…' : 'Analisar e organizar arquivo'}</button>}
          {type === 'image' && imageEditUrl && <a href={imageStudioLink(artifact, studioEditorUrl, projectRef, 'mask', 'Altere somente a região que eu marcar, preservando todo o restante da imagem.')} target="_blank" rel="noreferrer">Marcar uma área</a>}
          {type === 'image' && imageEditUrl && <a href={imageStudioLink(artifact, studioEditorUrl, projectRef, 'crop', 'Recorte e reenquadre a imagem mantendo o elemento principal em destaque.')} target="_blank" rel="noreferrer">Recortar e reenquadrar</a>}
          {type === 'image' && imageEditUrl && <a href={imageStudioLink(artifact, studioEditorUrl, projectRef, 'select', 'Remova o fundo desta imagem e preserve as bordas do elemento principal com acabamento limpo.')} target="_blank" rel="noreferrer">Remover fundo</a>}
          {type === 'image' && imageEditUrl && <a href={imageStudioLink(artifact, studioEditorUrl, projectRef, 'format', 'Adapte esta imagem para um novo formato sem perder o conteúdo principal.')} target="_blank" rel="noreferrer">Alterar formato</a>}
          {type === 'image' && imageEditUrl && <a href={imageStudioLink(artifact, studioEditorUrl, projectRef, 'select', 'Otimize esta imagem para uso digital, reduzindo o peso sem perda visual perceptível.')} target="_blank" rel="noreferrer">Otimizar para web</a>}
          {type === 'image' && src && <a href={src} target="_blank" rel="noreferrer">Abrir original</a>}
          {type === 'image' && src && <a href={src} download>Baixar arquivo</a>}
          {textArtifact && <button type="button" onClick={toggleTheme}>{lightTheme ? 'Usar tema escuro' : 'Usar tema claro'}</button>}
          {(textArtifact || type === 'html') && artifact.id && <div role="group" aria-label="Baixar arquivo"><button type="button" onClick={() => downloadTextArtifact(artifact, 'md')}>Baixar .md</button><button type="button" onClick={() => downloadTextArtifact(artifact, 'txt')}>Baixar .txt</button><button type="button" onClick={() => downloadTextArtifact(artifact, 'html')}>Baixar .html</button></div>}
          {artifact.id && onMoveToProject && <label className="cv-artifact-project-picker">Mover material<select value={artifact.project_ref || ''} disabled={saving} onChange={event => onMoveToProject(event.target.value)}><option value="">Espaço pessoal</option>{projects.map(item => { const ref = item.projectRef || item.ref || item.id; return <option key={ref} value={ref}>{item.name || item.title || ref}</option>; })}</select></label>}
          {publicLink && <button type="button" onClick={onUnpublish} disabled={publishing || saving}>Despublicar</button>}
          <button type="button" onClick={() => onSideChange?.(side === 'right' ? 'left' : 'right')}>{side === 'right' ? 'Mover para a esquerda' : 'Mover para a direita'}</button>
          {artifact.id && <button type="button" onClick={openVersions}><Icon name="history" size={14}/>Ver versões <small>v{artifact.current_version || 1}</small></button>}
        </div>
      </details>}
      <button type="button" onClick={requestClose} className={`cv-artifact-return cv-grid cv-h-8 cv-place-items-center cv-rounded-lg cv-border-0 cv-bg-transparent cv-text-mist hover:cv-bg-white/[.05] ${mobile ? 'is-mobile' : 'cv-w-8'}`} aria-label={mobile ? 'Voltar à conversa' : 'Fechar entrega'}><Icon name={mobile ? 'chevron' : 'close'} size={17}/>{mobile && <span>Conversa</span>}</button>
    </header>
    {artifact.current_version > 1 && artifact.change_summary && !artifact.pending && <div className="cv-flex cv-items-center cv-gap-3 cv-border-b cv-border-white/[.07] cv-bg-[#173a35] cv-px-4 cv-py-2 cv-text-xs" role="status"><strong className="cv-whitespace-nowrap cv-text-[#9ee1cd]">Versão {artifact.current_version}</strong><span className="cv-min-w-0 cv-flex-1 cv-truncate cv-text-[#d4e8e0]" title={artifact.change_summary}>{artifact.change_summary.replace(/^Cadu:\s*/, '')}</span><button type="button" onClick={openVersions} className="cv-whitespace-nowrap cv-border-0 cv-bg-transparent cv-text-[#9ee1cd] cv-underline">Ver versões</button></div>}
    <div className="cv-scroll cv-min-h-0 cv-flex-1 cv-overflow-auto">{contentView}</div>
    {!artifact.pending && type === 'image' && <footer className="cv-image-metadata" aria-label="Informações da imagem"><dl><div><dt>Dimensões</dt><dd>{imageMetadata?.width && imageMetadata?.height ? `${imageMetadata.width} × ${imageMetadata.height} px` : 'Carregando…'}</dd></div><div><dt>Resolução</dt><dd>{imageMetadata?.width && imageMetadata?.height ? `${((imageMetadata.width * imageMetadata.height) / 1000000).toLocaleString('pt-BR', {maximumFractionDigits: 1})} MP` : '—'}</dd></div><div><dt>Arquivo</dt><dd>{formatFileSize(imageMetadata?.bytes)}</dd></div></dl></footer>}
    {publicLink && <div className="cv-artifact-public-link"><span>Link publicado</span><input aria-label="Link publicado" readOnly value={publicLink} onFocus={event => event.target.select()}/><a href={publicLink} target="_blank" rel="noreferrer">Abrir</a></div>}
    {!artifact.pending && artifact.id && type !== 'image' && <footer className="cv-artifact-actions"><span>{saving ? 'Indexando…' : dirty ? 'Alterações pendentes' : artifact.status === 'active' && artifact.project_ref ? 'Versão indexada no projeto' : artifact.project_ref ? 'Salva no projeto' : 'Rascunho salvo automaticamente'}</span><div>{projectRef && type !== 'link_reader' && indexable && <><label className="cv-text-xs">Formato da fonte <select value={sourceFormat} disabled={saving} onChange={event => setSourceFormat(event.target.value)}><option value={type === 'html' ? 'html' : 'md'}>{type === 'html' ? '.html' : '.md'}</option>{type !== 'html' && <option value="txt">.txt</option>}</select></label><button type="button" onClick={() => onSaveToProject(sourceFormat)} disabled={saving} className="cv-artifact-actions__project">{artifact.status === 'active' && artifact.project_ref ? 'Atualizar fonte do projeto' : 'Finalizar e indexar no projeto'}</button></>}{projectRef && type !== 'link_reader' && !indexable && !artifact.project_ref && <button type="button" onClick={onAttachToProject} disabled={saving} className="cv-artifact-actions__project">Salvar no projeto</button>}{dirty && <button type="button" onClick={onSave} disabled={saving} className="cv-artifact-actions__save">Salvar agora</button>}</div></footer>}
    <dialog ref={dialog} className="cv-dialog cv-w-[min(540px,calc(100vw-32px))] cv-p-0">
      <section><header className="cv-flex cv-items-center cv-justify-between cv-border-b cv-border-white/10 cv-p-5"><div><h2 className="cv-m-0 cv-text-base">Versões</h2><p className="cv-mb-0 cv-mt-1 cv-text-xs cv-text-mist">Restaure uma revisão anterior.</p></div><button type="button" onClick={() => dialog.current?.close()} className="cv-grid cv-h-8 cv-w-8 cv-place-items-center cv-rounded-lg cv-border-0 cv-bg-transparent"><Icon name="close" size={16}/></button></header>
        <div className="cv-scroll cv-max-h-[55vh] cv-overflow-y-auto cv-p-3">{loadingVersions ? <p className="cv-p-3 cv-text-sm cv-text-mist">Carregando…</p> : versions.length ? versions.map(item => <article key={item.version} className="cv-flex cv-items-center cv-gap-4 cv-rounded-xl cv-p-3 hover:cv-bg-white/[.04]"><div className="cv-min-w-0 cv-flex-1"><strong className="cv-block cv-text-sm">Versão {item.version}</strong><small className="cv-mt-1 cv-block cv-overflow-hidden cv-text-ellipsis cv-whitespace-nowrap cv-text-xs cv-text-mist">{item.change_summary || 'Revisão da entrega'}</small></div><button type="button" disabled={Number(item.version) === Number(artifact.current_version) || comparingVersion !== null} onClick={() => compareVersion(item.version)} className="cv-rounded-lg cv-border cv-border-white/10 cv-bg-transparent cv-px-3 cv-py-2 cv-text-xs disabled:cv-opacity-35">{comparingVersion === item.version ? 'Comparando…' : 'Comparar'}</button><button type="button" disabled={Number(item.version) === Number(artifact.current_version)} onClick={async () => { await onRestoreVersion(item.version); dialog.current?.close(); }} className="cv-rounded-lg cv-border cv-border-white/10 cv-bg-transparent cv-px-3 cv-py-2 cv-text-xs disabled:cv-opacity-35">{Number(item.version) === Number(artifact.current_version) ? 'Atual' : 'Restaurar'}</button></article>) : <p className="cv-p-3 cv-text-sm cv-text-mist">Nenhuma versão disponível.</p>}{comparison && <section className="cv-m-3 cv-rounded-xl cv-border cv-border-white/10 cv-p-4" aria-live="polite"><h3 className="cv-m-0 cv-text-sm">Versão {comparison.version} → atual</h3>{comparison.error ? <p className="cv-text-xs cv-text-mist">{comparison.error}</p> : <div className="cv-mt-3 cv-grid cv-gap-4 md:cv-grid-cols-2"><div><strong className="cv-text-xs cv-text-[#e8b4a9]">Trechos removidos ou substituídos</strong>{comparison.removed.length ? comparison.removed.map((line, index) => <p key={index} className="cv-mb-0 cv-mt-2 cv-text-xs cv-text-mist">{line}</p>) : <p className="cv-text-xs cv-text-mist">Nenhum trecho textual removido.</p>}</div><div><strong className="cv-text-xs cv-text-[#9ee1cd]">Trechos adicionados ou revisados</strong>{comparison.added.length ? comparison.added.map((line, index) => <p key={index} className="cv-mb-0 cv-mt-2 cv-text-xs cv-text-mist">{line}</p>) : <p className="cv-text-xs cv-text-mist">Nenhum trecho textual adicionado.</p>}</div></div>}</section>}</div>
      </section>
    </dialog>
  </aside>;
}
