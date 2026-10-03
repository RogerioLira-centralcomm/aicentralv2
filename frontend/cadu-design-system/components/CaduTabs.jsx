import React, {useEffect, useRef} from 'react';
import {Button} from '../untitled-kit/button';

/** Tab list with roving focus: arrows, Home and End move between enabled tabs. */
export function CaduTabs({items, value, onChange, label, className = ''}) {
  const available = items.filter(item => !item.disabled);
  const list = useRef(null);
  // react-aria's Button drops `role`, so the tablist would hold plain buttons that assistive tech cannot read as tabs.
  useEffect(() => {list.current?.querySelectorAll('[data-cadu-tab]').forEach(tab => tab.setAttribute('role', 'tab'));});
  const onKeyDown = event => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key) || !available.length) return;
    event.preventDefault();
    const index = available.findIndex(item => item.id === value);
    const next = event.key === 'Home' ? 0 : event.key === 'End' ? available.length - 1
      : (index + (event.key === 'ArrowRight' ? 1 : -1) + available.length) % available.length;
    const item = available[next];
    if (!item) return;
    onChange(item.id);
    event.currentTarget.querySelector(`[data-cadu-tab="${item.id}"]`)?.focus();
  };
  return <div ref={list} className={`cadu-ds-tabs ${className}`.trim()} role="tablist" aria-label={label} onKeyDown={onKeyDown}>
    {items.map(item => <Button key={item.id} type="button" color="tertiary" size="sm" isDisabled={item.disabled} role="tab" data-cadu-tab={item.id}
      aria-selected={value === item.id} tabIndex={value === item.id ? 0 : -1} className={value === item.id ? 'is-active' : ''}
      onPress={() => { if (!item.disabled) onChange(item.id); }}>{item.label}{item.count !== undefined && item.count !== '' && <small>{item.count}</small>}</Button>)}
  </div>;
}
