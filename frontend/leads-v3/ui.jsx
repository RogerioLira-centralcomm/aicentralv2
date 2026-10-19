import React, {useEffect, useRef} from 'react';

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
