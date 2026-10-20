import React, {useEffect, useRef, useState} from 'react';

/** Textos do site chegam com entidades HTML ("&quot;"). DOMParser decodifica sem executar nada. */
export function decode(text) {
  const raw = String(text ?? '');
  if (!raw.includes('&')) return raw;
  return new DOMParser().parseFromString(raw, 'text/html').documentElement.textContent || raw;
}

export const digits = value => String(value || '').replace(/\D/g, '');

export function whatsappUrl(phone, text = '') {
  let number = digits(phone);
  if (!number) return '';
  if (number.length <= 11) number = `55${number}`;
  return `https://wa.me/${number}${text ? `?text=${encodeURIComponent(text)}` : ''}`;
}

/** Busca de pessoas no LinkedIn já filtrada (o executivo conecta manualmente: sem automação na conta). */
export function linkedinSearchUrl(...termos) {
  const keywords = termos.map(t => decode(t || '').trim()).filter(Boolean).join(' ');
  return `https://www.linkedin.com/search/results/people/?keywords=${encodeURIComponent(keywords)}&origin=GLOBAL_SEARCH_HEADER`;
}

/** Data local (aaaa-mm-dd): toISOString() é UTC e vira o dia às 21h no Brasil. */
export function todayLocal() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
}

export function formatDate(value) {
  if (!value) return '—';
  const iso = /^\d{4}-\d{2}-\d{2}/.test(value) ? value : null;
  if (!iso) return value; // a API de atividades já devolve dd/mm/aaaa hh:mm
  const [y, m, d] = iso.slice(0, 10).split('-');
  const time = value.length > 10 ? ` ${value.slice(11, 16)}` : '';
  return `${d}/${m}/${y}${time}`;
}

export function Icon({name, className = ''}) {
  return <i className={`fa-solid fa-${name} lv3-icon ${className}`} aria-hidden="true"/>;
}

export function Button({variant = 'secondary', size = 'md', icon, children, className = '', ...props}) {
  return (
    <button type="button" className={`lv3-btn lv3-btn--${variant} lv3-btn--${size} ${className}`} {...props}>
      {icon && <Icon name={icon}/>}
      {children && <span>{children}</span>}
    </button>
  );
}

export function Chip({tone = 'neutral', children}) {
  return <span className={`lv3-chip lv3-chip--${tone}`}>{children}</span>;
}

export const potencialTone = value => ({alto: 'success', medio: 'warning', baixo: 'neutral'}[value] || 'neutral');

export function Field({label, children, wide = false}) {
  return (
    <label className={`lv3-field ${wide ? 'lv3-field--wide' : ''}`}>
      <span className="lv3-field__label">{label}</span>
      {children}
    </label>
  );
}

export function Modal({title, onClose, children, footer, width = 520}) {
  const ref = useRef(null);
  useEffect(() => {
    const onKey = event => { if (event.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    ref.current?.querySelector('input, select, textarea, button')?.focus();
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);
  return (
    <div className="lv3-modal" role="presentation" onMouseDown={event => { if (event.target === event.currentTarget) onClose(); }}>
      <div className="lv3-modal__card" role="dialog" aria-modal="true" aria-label={title} ref={ref} style={{maxWidth: width}}>
        <header className="lv3-modal__head">
          <h2>{title}</h2>
          <button type="button" className="lv3-iconbtn" onClick={onClose} aria-label="Fechar"><Icon name="xmark"/></button>
        </header>
        <div className="lv3-modal__body">{children}</div>
        {footer && <footer className="lv3-modal__foot">{footer}</footer>}
      </div>
    </div>
  );
}

export function Empty({icon = 'inbox', title, children}) {
  return (
    <div className="lv3-empty">
      <Icon name={icon}/>
      <strong>{title}</strong>
      {children && <p>{children}</p>}
    </div>
  );
}

export function Toasts({items, onDismiss}) {
  return (
    <div className="lv3-toasts" role="status" aria-live="polite">
      {items.map(item => (
        <div key={item.id} className={`lv3-toast lv3-toast--${item.tone}`}>
          <Icon name={item.tone === 'error' ? 'circle-exclamation' : 'circle-check'}/>
          <span>{item.text}</span>
          <button type="button" className="lv3-iconbtn" onClick={() => onDismiss(item.id)} aria-label="Fechar aviso"><Icon name="xmark"/></button>
        </div>
      ))}
    </div>
  );
}

// ─── Markdown simples (texto da IA) ───────────────────────────────────
// Monta elementos React (nunca innerHTML): **negrito**, listas com "-", "•" ou "1.", títulos "#"
// e citações [n] viram links para as fontes. O resto fica como texto.
function inline(text, fontes, keyBase) {
  return String(text).split(/(\*\*[^*]+\*\*|\[\d+\])/g).filter(Boolean).map((part, i) => {
    const key = `${keyBase}-${i}`;
    if (/^\*\*[^*]+\*\*$/.test(part)) return <strong key={key}>{part.slice(2, -2)}</strong>;
    const cite = part.match(/^\[(\d+)\]$/);
    if (cite) {
      const url = fontes?.[Number(cite[1]) - 1];
      return url ? <sup key={key}><a href={url} target="_blank" rel="noopener noreferrer">{cite[1]}</a></sup> : <sup key={key}>{cite[1]}</sup>;
    }
    return part.replace(/\*\*/g, '');
  });
}

export function Markdown({text, fontes, className = ''}) {
  const blocks = [];
  let list = null;
  String(text || '').split('\n').forEach((raw, i) => {
    const line = raw.trim();
    const bullet = line.match(/^(?:[-•*]|\d+[.)])\s+(.*)$/);
    if (bullet) {
      const ordered = /^\d/.test(line);
      if (!list || list.ordered !== ordered) { list = {ordered, items: []}; blocks.push(list); }
      list.items.push(inline(bullet[1], fontes, `li${i}`));
      return;
    }
    list = null;
    if (!line) return;
    const heading = line.match(/^#{1,6}\s+(.*)$/);
    blocks.push(heading ? {heading: inline(heading[1], fontes, `h${i}`)} : {p: inline(line, fontes, `p${i}`)});
  });
  return (
    <div className={`lv3-md ${className}`}>
      {blocks.map((b, i) => {
        if (b.items) {
          const Tag = b.ordered ? 'ol' : 'ul';
          return <Tag key={i}>{b.items.map((item, j) => <li key={j}>{item}</li>)}</Tag>;
        }
        if (b.heading) return <h5 key={i}>{b.heading}</h5>;
        return <p key={i}>{b.p}</p>;
      })}
    </div>
  );
}

/** Rascunho no Gmail já preenchido (o executivo revisa e envia da própria conta). */
export function gmailUrl(to, subject, body) {
  return `https://mail.google.com/mail/?view=cm&fs=1&to=${encodeURIComponent(to || '')}&su=${encodeURIComponent(subject || '')}&body=${encodeURIComponent(body || '')}`;
}

/** "GABRIELA MARTINS" → "Gabriela Martins" (só quando o texto vem todo em maiúsculas). */
export function prettyName(text) {
  const value = decode(text || '').trim();
  if (!value || value !== value.toUpperCase() || !/[A-ZÀ-Ý]/.test(value)) return value;
  return value.toLowerCase().replace(/(^|[\s-])(\p{L})/gu, (_, sep, ch) => sep + ch.toUpperCase())
    .replace(/\b(De|Da|Do|Das|Dos|E)\b/g, w => w.toLowerCase());
}

/** Menu suspenso de ações (fecha com clique fora ou Esc). `trigger="icon"` usa um botão de ícone discreto. */
export function MoreMenu({items, disabled, icon = 'ellipsis', label = 'Mais ações', trigger = 'button'}) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    if (!open) return undefined;
    const close = event => { if (event.type === 'keydown' ? event.key === 'Escape' : !ref.current?.contains(event.target)) setOpen(false); };
    document.addEventListener('mousedown', close);
    document.addEventListener('keydown', close);
    return () => { document.removeEventListener('mousedown', close); document.removeEventListener('keydown', close); };
  }, [open]);
  if (!items.length) return null;
  return (
    <div className="lv3-menu" ref={ref}>
      {trigger === 'icon' ? (
        <button type="button" className={`lv3-iconbtn ${open ? 'is-open' : ''}`} onClick={() => setOpen(o => !o)} disabled={disabled}
          aria-label={label} aria-expanded={open} title={label}><Icon name={icon}/></button>
      ) : (
        <Button size="sm" icon={icon} onClick={() => setOpen(o => !o)} disabled={disabled} aria-label={label} aria-expanded={open} title={label}/>
      )}
      {open && (
        <div className="lv3-menu__list" role="menu">
          {items.map(item => (
            <button key={item.label} type="button" role="menuitem" className={`lv3-menu__item ${item.danger ? 'is-danger' : ''}`}
              onClick={() => { setOpen(false); item.onClick(); }}>
              <Icon name={item.icon}/><span>{item.label}{item.hint && <small>{item.hint}</small>}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
