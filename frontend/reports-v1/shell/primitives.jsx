import React, {useMemo, useState} from 'react';
import {AlertCircle, ArrowDown, ArrowUp, RefreshCw01} from '@untitledui/icons';
import {Table} from '../../cadu-design-system/untitled-kit/table.tsx';
import {cx} from '../../cadu-design-system/untitled-kit/utils/cx';
import {ReportsActionButton} from '../ReportsActionButton.jsx';
import {navigateOnClick} from './routes.js';

/** One row of numbers separated by dividers — a summary strip, not a card per metric. */
export function MetricGroup({items, label = 'Resumo', changeLabel = 'vs período anterior'}) {
  return <section className="rs-metrics" aria-label={label} style={{'--rs-metric-count': items.length}}>
    {items.map(item => <div key={item.label} className="rs-metric">
      <span className="rs-metric__label">{item.label}</span>
      <strong className="rs-metric__value">{item.value ?? '—'}</strong>
      {item.change != null && Number.isFinite(item.change)
        ? <small className={`rs-metric__change ${(item.change >= 0) !== Boolean(item.inverse) ? 'is-up' : 'is-down'}`}>{item.change >= 0 ? <ArrowUp size={12} aria-hidden="true"/> : <ArrowDown size={12} aria-hidden="true"/>}{Math.abs(item.change).toLocaleString('pt-BR', {maximumFractionDigits: 1})}%<span> {changeLabel}</span></small>
        : item.detail ? <small className="rs-metric__detail">{item.detail}</small> : null}
    </div>)}
  </section>;
}

/** Titled block of a page: h2 at 16px, optional subtitle and one action on the right. */
export function Section({title, description, action, children, className = '', id}) {
  return <section className={`rs-section ${className}`} aria-labelledby={id ? `${id}-title` : undefined}>
    {(title || action) && <header className="rs-section__head">
      <div>{title && <h2 id={id ? `${id}-title` : undefined}>{title}</h2>}{description && <p>{description}</p>}</div>
      {action}
    </header>}
    {children}
  </section>;
}

/** Internal link that navigates without reloading the app. */
export function AppLink({href, children, className}) {
  return <a href={href} className={className} onClick={event => navigateOnClick(event, href)}>{children}</a>;
}

/**
 * Analytic table: sortable headers, numbers aligned right, optional row link.
 * columns: [{key, label, numeric, render(row), sort(row)}]
 */
/** Untitled UI table: React Aria sorting and keyboard navigation, 44px rows for dense media reports. */
export function DataTable({columns, rows, rowKey = (row, index) => index, empty, initialSort, label, limit}) {
  const [sort, setSort] = useState(initialSort || null);
  const sorted = useMemo(() => {
    if (!sort) return rows;
    const column = columns.find(item => item.key === sort.key);
    const value = row => column?.sort ? column.sort(row) : row[sort.key];
    return [...rows].sort((a, b) => {
      const left = value(a), right = value(b);
      const order = typeof left === 'number' && typeof right === 'number' ? left - right : String(left ?? '').localeCompare(String(right ?? ''), 'pt-BR');
      return sort.dir === 'asc' ? order : -order;
    });
  }, [rows, sort, columns]);
  if (!rows.length) return empty || null;
  const visible = limit ? sorted.slice(0, limit) : sorted;
  // A new column starts in its natural order: numbers from the largest, text from A.
  const changeSort = descriptor => {
    const key = String(descriptor.column);
    setSort(current => current?.key === key
      ? {key, dir: current.dir === 'asc' ? 'desc' : 'asc'}
      : {key, dir: columns.find(item => item.key === key)?.numeric ? 'desc' : 'asc'});
  };
  const align = column => column.numeric ? 'text-right tabular-nums' : '';
  return <div className="rs-table-wrap">
    <Table aria-label={label} size="sm" sortDescriptor={sort ? {column: sort.key, direction: sort.dir === 'asc' ? 'ascending' : 'descending'} : undefined} onSortChange={changeSort}>
      <Table.Header>{columns.map((column, index) => <Table.Head key={column.key} id={column.key} isRowHeader={index === 0} allowsSorting={column.sortable !== false}
        label={typeof column.label === 'string' ? column.label : undefined} className={cx('px-4 first:pl-6 last:pr-6', column.numeric && '[&>div]:justify-end')}>
        {typeof column.label === 'string' ? null : <span className="text-xs font-semibold whitespace-nowrap text-quaternary">{column.label}</span>}
      </Table.Head>)}</Table.Header>
      <Table.Body>{visible.map((row, index) => <Table.Row key={rowKey(row, index)} id={`${index}`} className="h-11">
        {columns.map((column, cell) => <Table.Cell key={column.key} className={cx('px-4 py-2.5 first:pl-6 last:pr-6', cell === 0 && 'font-medium text-primary', align(column))}>
          {column.render ? column.render(row) : row[column.key] ?? '—'}
        </Table.Cell>)}
      </Table.Row>)}</Table.Body>
    </Table>
  </div>;
}

export function LoadingState({rows = 3, label = 'Carregando…'}) {
  return <div className="rs-skeleton" role="status" aria-label={label}>{Array.from({length: rows}, (_, index) => <span key={index}/>)}</div>;
}

/** Says what would be here, why it is empty and what to do next. */
export function EmptyState({title, description, action}) {
  return <div className="rs-empty"><strong>{title}</strong>{description && <p>{description}</p>}{action}</div>;
}

export function ErrorState({message, onRetry}) {
  return <div className="rs-error" role="alert"><AlertCircle size={18} aria-hidden="true"/><div><strong>Não foi possível carregar estes dados</strong><p>{message}</p></div>
    {onRetry && <ReportsActionButton color="secondary" size="sm" onClick={onRetry}><RefreshCw01 size={16} aria-hidden="true"/>Tentar novamente</ReportsActionButton>}</div>;
}

/** Loading, error and empty in one place, so every block of a hub behaves the same way. */
export function Async({state, onRetry, empty, isEmpty, rows, children}) {
  if (state.error) return <ErrorState message={state.error} onRetry={onRetry}/>;
  if (state.loading && !state.body) return <LoadingState rows={rows}/>;
  if (!state.body) return null;
  if (isEmpty?.(state.body)) return empty || null;
  return children(state.body);
}
