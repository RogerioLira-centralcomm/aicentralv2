// Adapted from Untitled UI React v8 application/sidebar-navigations (simple) using the free base primitives only.
import React, {createContext, useContext} from 'react';
import type {ComponentProps, ReactNode} from 'react';
import {cx} from './utils/cx';

const CollapsedContext = createContext(false);

const itemClasses = 'group relative flex w-full min-w-0 cursor-pointer items-center gap-3 rounded-md border-0 bg-transparent px-3 py-2 text-left text-sm font-semibold text-secondary no-underline outline-focus-ring transition duration-100 ease-linear select-none hover:bg-primary_hover hover:text-secondary_hover focus-visible:outline-2 focus-visible:outline-offset-2 max-[1024px]:w-auto max-[1024px]:flex-none max-[1024px]:rounded-none max-[1024px]:px-2.5 max-[1024px]:min-h-11';
const iconClasses = 'flex size-5 shrink-0 items-center justify-center text-fg-quaternary group-hover:text-fg-quaternary_hover [&>svg]:size-5 max-[1024px]:hidden';

type ItemProps = {icon?: ReactNode; label: string; badge?: number; current?: boolean; collapsed?: boolean};

function ItemContent({icon, label, badge, collapsed}: ItemProps) {
  return <>
    {icon && <span className={iconClasses} aria-hidden="true">{icon}</span>}
    <span className={cx('min-w-0 flex-1 truncate', collapsed && 'sr-only')}>{label}</span>
    {!collapsed && badge ? <span className="shrink-0 rounded-full bg-primary px-2 py-0.5 text-xs font-medium text-secondary ring-1 ring-primary ring-inset max-[1024px]:hidden">{badge}</span> : null}
  </>;
}

export function SidebarNavProvider({collapsed = false, children}: {collapsed?: boolean; children: ReactNode}) {
  return <CollapsedContext.Provider value={collapsed}>{children}</CollapsedContext.Provider>;
}

export function SidebarNav({label, children}: {label?: string; children: ReactNode}) {
  return <nav aria-label={label} className="grid gap-0.5 max-[1024px]:flex max-[1024px]:gap-0.5 max-[1024px]:overflow-x-auto max-[1024px]:px-3">{children}</nav>;
}

export function SidebarNavLink({icon, label, badge, current, href, ...rest}: ItemProps & Omit<ComponentProps<'a'>, 'children'>) {
  const collapsed = useContext(CollapsedContext);
  return <a href={href} aria-current={current ? 'page' : undefined} aria-label={collapsed ? label : undefined} title={collapsed ? label : undefined}
    className={cx(itemClasses, collapsed && 'justify-center px-2', current && 'is-active bg-primary_hover text-secondary_hover [&_span]:text-secondary_hover')} {...rest}>
    <ItemContent icon={icon} label={label} badge={badge} collapsed={collapsed}/>
  </a>;
}

export function SidebarNavButton({icon, label, destructive, ...rest}: Omit<ItemProps, 'badge' | 'current'> & {destructive?: boolean} & Omit<ComponentProps<'button'>, 'children'>) {
  return <button type="button" className={cx(itemClasses, destructive && 'text-error-primary hover:text-error-primary')} {...rest}>
    <ItemContent icon={icon} label={label}/>
  </button>;
}

/** Heading plus items below the main list; hidden when the sidebar is collapsed or turns into top tabs. */
export function SidebarNavGroup({title, children}: {title?: string; children: ReactNode}) {
  const collapsed = useContext(CollapsedContext);
  if (collapsed) return null;
  return <div className="mt-4 grid gap-0.5 border-t border-secondary pt-4 max-[1024px]:hidden">
    {title && <span className="mb-1 px-3 text-xs font-semibold text-quaternary">{title}</span>}
    {children}
  </div>;
}

/** Expandable group of secondary actions (native details, keyboard accessible). */
export function SidebarNavMenu({icon, label, children}: {icon?: ReactNode; label: string; children: ReactNode}) {
  return <details className="group/menu min-w-0">
    <summary className={cx(itemClasses, 'list-none [&::-webkit-details-marker]:hidden')}>
      <ItemContent icon={icon} label={label}/>
      <span className="shrink-0 text-fg-quaternary transition group-open/menu:rotate-180" aria-hidden="true">⌄</span>
    </summary>
    <div className="grid gap-0.5 pt-0.5 pl-8 [&_a]:py-1.5 [&_a]:font-medium [&_button]:py-1.5 [&_button]:font-medium">{children}</div>
  </details>;
}
