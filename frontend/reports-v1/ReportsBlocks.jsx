// Untitled building blocks shared by the Reports screens built only from the kit (inside .untitled-scope).
import React from 'react';
import {Button} from '../cadu-design-system/untitled-kit/button.tsx';

export const TH = 'border-b border-secondary bg-secondary px-6 py-3 text-left text-xs font-semibold whitespace-nowrap text-tertiary';
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
    <div className={flush ? '' : 'px-6 py-5'}>{children}</div>
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
