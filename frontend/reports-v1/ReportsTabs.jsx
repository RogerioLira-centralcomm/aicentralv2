import React from 'react';
import {ReportsActionButton} from './ReportsActionButton.jsx';

export function ReportsTabs({items, value, onChange, label, className = ''}) {
  const available = items.filter(item => !item.disabled);
  const onKeyDown = event => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    if (!available.length) return;
    event.preventDefault();
    const index = available.findIndex(item => item.id === value);
    const next = event.key === 'Home' ? 0 : event.key === 'End' ? available.length - 1
      : (index + (event.key === 'ArrowRight' ? 1 : -1) + available.length) % available.length;
    const item = available[next];
    if (!item) return;
    onChange(item.id);
    event.currentTarget.querySelector(`[data-report-tab="${item.id}"]`)?.focus();
  };
  return <div className={className} role="tablist" aria-label={label} onKeyDown={onKeyDown}>
    {items.map(item => <ReportsActionButton
      key={item.id}
      type="button"
      role="tab"
      data-report-tab={item.id}
      aria-selected={value === item.id}
      aria-disabled={item.disabled || undefined}
      tabIndex={value === item.id ? 0 : -1}
      className={value === item.id ? 'is-active' : ''}
      onClick={() => {if (!item.disabled) onChange(item.id);}}
    >{item.label}{item.count !== undefined && item.count !== '' && <small>{item.count}</small>}</ReportsActionButton>)}
  </div>;
}
