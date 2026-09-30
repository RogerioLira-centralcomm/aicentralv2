import React,{useId} from 'react';
import {XClose,LayersTwo01} from '@untitledui/icons';
import {Button} from './untitled-kit/src/components/base/buttons/button.tsx';

/** Shared visual structure; modal focus is owned by the enclosing React Aria Dialog. */
export function ReportsPanelShell({title,description,context,icon:Icon=LayersTwo01,onClose,closeLabel,children,footer,className='',as:Element='aside'}) {
  const titleId=useId();
  return <Element className={`reports-panel-shell ${className}`} aria-labelledby={titleId}>
    <header className="reports-panel-shell__header">
      <div className="reports-panel-shell__top"><span className="reports-panel-shell__icon"><Icon size={20} aria-hidden="true"/></span>{onClose&&<Button type="button" color="tertiary" size="sm" aria-label={closeLabel||`Fechar ${title}`} onPress={onClose}><XClose size={20}/></Button>}</div>
      {context&&<small>{context}</small>}<h2 id={titleId}>{title}</h2>{description&&<p>{description}</p>}
    </header>
    <div className="reports-panel-shell__body">{children}</div>
    {footer&&<footer className="reports-panel-shell__footer">{footer}</footer>}
  </Element>;
}
