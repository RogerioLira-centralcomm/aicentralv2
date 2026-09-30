import React, {useId} from 'react';
import {XClose} from '@untitledui/icons';
import {Button} from '../untitled-kit/button';

/** Header, scrollable body and footer shared by drawers and side panels. Focus is owned by the enclosing dialog. */
export function CaduPanel({title, description, context, icon: Icon = null, onClose, closeLabel, children, footer, className = '', as: Element = 'aside'}) {
  const titleId = useId();
  return <Element className={`cadu-ds-panel ${className}`.trim()} aria-labelledby={titleId}>
    <header className="cadu-ds-panel__header">
      <div className="cadu-ds-panel__top">
        {Icon ? <span className="cadu-ds-panel__icon"><Icon size={20} aria-hidden="true"/></span> : <span/>}
        {onClose && <Button type="button" color="tertiary" size="sm" aria-label={closeLabel || `Fechar ${title}`} onPress={onClose}><XClose size={20} aria-hidden="true"/></Button>}
      </div>
      {context && <small>{context}</small>}
      <h2 id={titleId}>{title}</h2>
      {description && <p>{description}</p>}
    </header>
    <div className="cadu-ds-panel__body">{children}</div>
    {footer && <footer className="cadu-ds-panel__footer">{footer}</footer>}
  </Element>;
}
