import React from 'react';
import {Dropdown} from '../untitled-kit/dropdown';
import {CaduButton} from './CaduButton';

/** Menu de ações no kit Untitled: botão gatilho + itens. Cada item chama `onAction`. */
export function CaduActionMenu({label, ariaLabel, items, variant = 'secondary'}) {
  const visible = items.filter(Boolean);
  return <Dropdown.Root>
    <CaduButton variant={variant} aria-label={ariaLabel || label}>{label} ▾</CaduButton>
    <Dropdown.Popover>
      <Dropdown.Menu onAction={key => visible.find(item => item.id === key)?.onAction?.()}>
        {visible.map(item => <React.Fragment key={item.id}>
          {item.separatorBefore && <Dropdown.Separator/>}
          <Dropdown.Item id={item.id} textValue={item.label} destructive={item.destructive}>{item.label}</Dropdown.Item>
        </React.Fragment>)}
      </Dropdown.Menu>
    </Dropdown.Popover>
  </Dropdown.Root>;
}
