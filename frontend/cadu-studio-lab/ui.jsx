import React, {useState} from 'react';

export function createApi(bootstrap) {
  const root = bootstrap.apiRoot || '/lab/api';
  async function request(path, {method = 'GET', body, form} = {}) {
    const headers = {Accept: 'application/json'};
    if (method !== 'GET') headers['X-Trocr-CSRF-Token'] = bootstrap.csrf || '';
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    const response = await fetch(root + path, {method, headers, credentials: 'same-origin',
      body: form || (body !== undefined ? JSON.stringify(body) : undefined)});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || `Erro ${response.status}`);
    return data;
  }
  return {
    get: path => request(path),
    post: (path, body) => request(path, {method: 'POST', body}),
    patch: (path, body) => request(path, {method: 'PATCH', body}),
    upload: (path, form) => request(path, {method: 'POST', form}),
  };
}

export const ROLES = [
  ['BASE', 'Base (editar)'], ['COMPOSITION', 'Composição'], ['PRODUCT', 'Produto'], ['PERSON', 'Pessoa'],
  ['STYLE', 'Estilo'], ['LOGO', 'Logo'], ['OTHER', 'Outra'],
];
export const ROLE_LABEL = Object.fromEntries(ROLES);
export const STATUS_LABEL = {queued: 'Na fila', running: 'Gerando', succeeded: 'Pronta', failed: 'Falhou', blocked: 'Bloqueada', skipped: 'Pulada'};
export const FAILURE_LABEL = {
  none: 'Sem falha', text_rendering: 'Texto', reference_ignored: 'Referência ignorada', identity_changed: 'Identidade mudou',
  logo_redrawn: 'Logo redesenhado', palette_off: 'Paleta fora', extra_elements: 'Elementos extras',
  edit_overreach: 'Edição invadiu', composition: 'Composição', prompt_lost_info: 'Prompt perdeu info (adaptador)',
};
export const READINESS_LABEL = {ready: 'Pronta', partial: 'Parcial', needs_audit: 'Precisa de auditoria'};

const number = (value, digits) => Number(value).toLocaleString('pt-BR', {minimumFractionDigits: digits, maximumFractionDigits: digits});
export const usd = value => value == null ? '—' : `US$ ${number(value, value < 0.1 ? 3 : 2)}`;
export const seconds = ms => ms == null ? '—' : `${number(ms / 1000, 1)} s`;
export const percent = value => value == null ? '—' : `${Math.round(value * 100)}%`;
export const tone = score => score == null ? 'is-muted' : score >= 80 ? 'is-ok' : score >= 60 ? 'is-warn' : 'is-bad';

export function Badge({children, kind = '', title}) {
  return <span className={`lab-badge ${kind}`} title={title}>{children}</span>;
}

export function StatusBadge({status}) {
  return <Badge kind={`is-${status}`}>{STATUS_LABEL[status] || status}</Badge>;
}

export function ScorePill({score, label = 'Nota'}) {
  return <span className={`lab-score ${tone(score)}`} title={`${label} TypeSafe (0–100)`}>{score == null ? '—' : score}</span>;
}

export function Thumb({src, alt = '', ratio = '1 / 1', status, onClick, children}) {
  const Tag = onClick ? 'button' : 'div';
  return <Tag type={onClick ? 'button' : undefined} className={`lab-thumb${onClick ? ' is-action' : ''}`} style={{aspectRatio: ratio}} onClick={onClick}>
    {src ? <img src={src} alt={alt} loading="lazy"/> : <span className="lab-thumb__empty">{status === 'running' || status === 'queued' ? <i className="lab-spinner" aria-hidden="true"/> : '—'}</span>}
    {children}
  </Tag>;
}

export function CopyUrl({url, label = 'URL pública'}) {
  const [copied, setCopied] = useState(false);
  if (!url) return null;
  const copy = async () => {
    try { await navigator.clipboard.writeText(url); setCopied(true); setTimeout(() => setCopied(false), 1400); } catch (_error) { /* clipboard blocked */ }
  };
  return <div className="lab-url">
    <small>{label}</small>
    <a href={url} target="_blank" rel="noreferrer">{url}</a>
    <button type="button" className="lab-btn is-ghost is-small" onClick={copy}>{copied ? 'Copiada' : 'Copiar'}</button>
  </div>;
}

export function Swatches({colors = [], size = 'md'}) {
  return <span className={`lab-swatches is-${size}`}>
    {colors.map(color => <i key={color.hex || color} style={{background: color.hex || color}} title={color.name ? `${color.name} ${color.hex}` : (color.hex || color)}/>)}
  </span>;
}

export function Notes({notes = [], scope, scopeKey, api, onSaved, placeholder = 'Anotar observação…'}) {
  const [body, setBody] = useState('');
  const [busy, setBusy] = useState(false);
  const own = notes.filter(note => note.scope === scope && String(note.scope_key) === String(scopeKey));
  const save = async event => {
    event.preventDefault();
    if (!body.trim()) return;
    setBusy(true);
    try { const data = await api.post('/notes', {scope, scope_key: scopeKey, body}); setBody(''); onSaved?.(data.notes); }
    finally { setBusy(false); }
  };
  return <div className="lab-notes">
    {own.length ? <ul>{own.map(note => <li key={note.id}><p>{note.body}</p><small>{note.author_name || 'Equipe'} · {new Date(note.created_at).toLocaleString('pt-BR', {dateStyle: 'short', timeStyle: 'short'})}</small></li>)}</ul>
      : <p className="lab-muted">Sem anotações.</p>}
    <form onSubmit={save}>
      <textarea rows={2} value={body} placeholder={placeholder} onChange={event => setBody(event.target.value)} aria-label="Nova anotação"/>
      <button type="submit" className="lab-btn is-small" disabled={busy || !body.trim()}>Anotar</button>
    </form>
  </div>;
}

export function Section({title, aside, children, className = ''}) {
  return <section className={`lab-section ${className}`}>
    <header><h2>{title}</h2>{aside}</header>
    {children}
  </section>;
}
