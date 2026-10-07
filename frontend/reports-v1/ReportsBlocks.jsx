// Untitled building blocks shared by the Reports screens built only from the kit (inside .untitled-scope).
import React, {useState} from 'react';
import {Button} from '../cadu-design-system/untitled-kit/button.tsx';

export const TH = 'relative border-b border-secondary bg-secondary px-6 py-3 text-left text-xs font-semibold whitespace-nowrap text-tertiary';
export const TD = 'border-b border-secondary px-6 py-3 align-middle text-sm text-secondary';

/** Card with a header (title, badge, supporting text, actions); `flush` lets a table run edge to edge. */
export function Card({title, badge, description, actions, children, flush = false}) {
  return <section className="overflow-hidden rounded-xl bg-primary shadow-xs ring-1 ring-secondary">
    {title && <header className="flex flex-wrap items-start justify-between gap-4 border-b border-secondary px-6 py-5">
      <div className="min-w-60 flex-1">
        <div className="flex items-center gap-2"><h2 className="text-lg font-semibold text-primary">{title}</h2>{badge}</div>
        {description && <p className="mt-0.5 text-sm text-tertiary">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap gap-3">{actions}</div>}
    </header>}
    {children != null && children !== false && <div className={flush ? '' : 'px-6 py-5'}>{children}</div>}
  </section>;
}

export function EmptyNote({title, children}) {
  return <div className="px-6 py-10 text-center"><p className="text-md font-semibold text-primary">{title}</p>{children && <p className="mx-auto mt-1 max-w-md text-sm text-tertiary">{children}</p>}</div>;
}

const CALLOUT_TONES = {gray: 'bg-secondary_subtle', warning: 'bg-warning-primary', error: 'bg-error-primary', brand: 'bg-brand-primary', success: 'bg-success-primary'};
export function Callout({tone = 'gray', title, children}) {
  return <div className={`rounded-lg p-4 ring-1 ring-secondary ring-inset ${CALLOUT_TONES[tone]}`}>
    {title && <p className="text-sm font-semibold text-primary">{title}</p>}
    <div className={title ? 'mt-1 text-sm text-secondary' : 'text-sm text-secondary'}>{children}</div>
  </div>;
}

export function Alert({tone = 'error', children}) {
  const tones = {error: 'bg-error-primary text-error-primary', success: 'bg-success-primary text-success-primary'};
  return <p role={tone === 'error' ? 'alert' : 'status'} className={`rounded-lg px-4 py-3 text-sm ring-1 ring-secondary ring-inset ${tones[tone]}`}>{children}</p>;
}

export function DrawerActions({onCancel, busy, label, disabled}) {
  return <div className="flex justify-end gap-3 border-t border-secondary pt-4">
    <Button type="button" size="md" color="secondary" onPress={onCancel}>Cancelar</Button>
    <Button type="submit" size="md" color="primary" isDisabled={busy || disabled} isLoading={busy}>{label}</Button>
  </div>;
}

/** Native date input with the kit field look (the kit Input skips native-only types). */
export function DateField({label, hideLabel = false, className = '', ...props}) {
  return <label className={`flex flex-col gap-1.5 text-sm font-medium text-secondary ${className}`.trim()}>
    <span className={hideLabel ? 'sr-only' : ''}>{label}</span>
    <input type="date" {...props} className="h-10 w-full min-w-0 rounded-lg bg-primary px-3 text-sm text-primary shadow-xs ring-1 ring-primary ring-inset outline-hidden focus:ring-2 focus:ring-brand disabled:opacity-60"/>
  </label>;
}

/** Strip of headline numbers: label, value and an optional supporting line. */
export function Stats({items}) {
  return <dl className={`grid gap-px overflow-hidden rounded-xl bg-border-secondary shadow-xs ring-1 ring-secondary sm:grid-cols-2 ${items.length > 3 ? 'lg:grid-cols-4' : 'lg:grid-cols-3'}`}>
    {items.map(([label, value, detail]) => <div key={label} className="min-w-0 bg-primary px-5 py-4">
      <dt className="text-sm font-medium text-tertiary">{label}</dt>
      <dd className="mt-1 truncate text-display-xs font-semibold text-primary tabular-nums" title={String(value)}>{value}</dd>
      {detail && <p className="mt-1 line-clamp-2 text-xs text-tertiary">{detail}</p>}
    </div>)}
  </dl>;
}

/** Table from [label, render, align] columns; long lists show `page` rows at a time. */
export function DataTable({columns, rows, rowKey, minWidth = 720, page = 50, dense = false}) {
  const [limit, setLimit] = useState(page);
  const shown = rows.slice(0, limit);
  // Dense tables (many numeric columns) tighten the gutters between cells, keeping the 24px card edges.
  const pad = (className, index) => dense ? className.replace('px-6', index === 0 ? 'pl-6 pr-3' : index === columns.length - 1 ? 'pl-3 pr-6' : 'px-3') : className;
  return <>
    <div className="overflow-x-auto"><table className="w-full" style={{minWidth}}>
      <thead><tr>{columns.map(([label, , align], index) => <th key={label || index} className={`${pad(TH, index)} ${align === 'right' ? 'text-right' : ''}`}>{label}</th>)}</tr></thead>
      <tbody>{shown.map((row, rowIndex) => <tr key={rowKey(row, rowIndex)} className="hover:bg-primary_hover">
        {columns.map(([label, render, align], index) => <td key={label || index} className={`${pad(TD, index)} ${align === 'right' ? 'text-right tabular-nums' : ''}`}>{render(row)}</td>)}
      </tr>)}</tbody>
    </table></div>
    {rows.length > limit && <div className="flex items-center justify-between gap-3 px-6 py-3">
      <span className="text-xs text-tertiary">{shown.length.toLocaleString('pt-BR')} de {rows.length.toLocaleString('pt-BR')} linhas</span>
      <Button size="sm" color="secondary" onPress={() => setLimit(limit + page)}>Mostrar mais {Math.min(page, rows.length - limit)}</Button>
    </div>}
  </>;
}
