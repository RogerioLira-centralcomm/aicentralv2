// Adapted from Untitled UI React v8 application/tabs/tabs.tsx.
import React from 'react';
import type {Key, ReactNode} from 'react';
import {Tab as AriaTab, TabList as AriaTabList, TabPanel as AriaTabPanel, Tabs as AriaTabs} from 'react-aria-components';
import {cx} from './utils/cx';

type ViewTabsProps = {
  items: readonly (readonly [string, string])[];
  selectedKey:string;
  onSelectionChange:(key:Key)=>void;
  label:string;
  trailing?:ReactNode;
  children:ReactNode;
};

export function ViewTabs({items, selectedKey, onSelectionChange, label, trailing, children}:ViewTabsProps) {
  return <AriaTabs selectedKey={selectedKey} onSelectionChange={onSelectionChange} className="cadu-untitled-tabs min-w-0">
    <div className="cadu-ds-project-explorer__toolbar">
      <AriaTabList aria-label={label} className="cadu-untitled-tab-list flex gap-1 rounded-lg bg-secondary_alt p-1 ring-1 ring-secondary ring-inset">
        {items.map(([id, title]) => <AriaTab id={id} key={id} className={state => cx('rounded-lg px-2.5 py-2 text-sm font-semibold text-secondary outline-focus-ring transition', state.isSelected && 'is-active bg-primary text-brand-secondary shadow-xs', state.isFocusVisible && 'outline-2 -outline-offset-2')}>{title}</AriaTab>)}
      </AriaTabList>
      {trailing}
    </div>
    <AriaTabPanel id={selectedKey} className="min-w-0 outline-focus-ring focus-visible:outline-2 focus-visible:outline-offset-2">{children}</AriaTabPanel>
  </AriaTabs>;
}
