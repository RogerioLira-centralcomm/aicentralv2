// Adapted from Untitled UI React v8 base/select/select-native.tsx for the Workspace skin.
import React, {useId} from 'react';
import type {SelectHTMLAttributes} from 'react';
import {ChevronDown} from '@untitledui/icons';
import {cx} from './utils/cx';

type NativeSelectProps = Omit<SelectHTMLAttributes<HTMLSelectElement>, 'size'> & {
  label?: string;
  hint?: string;
  options: {label:string; value:string; disabled?:boolean}[];
  size?: 'sm' | 'md' | 'lg';
  selectClassName?: string;
};

export function NativeSelect({label, hint, options, className, selectClassName, size = 'md', id: providedId, ...props}: NativeSelectProps) {
  const generatedId = useId();
  const id = providedId || `cadu-select-${generatedId}`;
  const hintId = `${id}-hint`;
  return <div className={cx('cadu-untitled-select w-full min-w-0', className)}>
    {label && <label data-label="true" htmlFor={id} className="mb-1.5 block text-sm font-medium text-secondary">{label}</label>}
    <div className="relative grid w-full items-center">
      <select {...props} id={id} aria-describedby={hint ? hintId : props['aria-describedby']} data-cadu-untitled-select="" className={cx('appearance-none w-full rounded-lg border-0 bg-primary font-medium text-primary shadow-xs ring-1 ring-primary ring-inset outline-hidden transition duration-100 ease-linear focus-visible:ring-2 focus-visible:ring-brand disabled:cursor-not-allowed disabled:opacity-50', size === 'lg' ? 'h-11 pl-3.5 pr-10 text-md' : size === 'sm' ? 'h-9 pl-3 pr-9 text-sm' : 'h-10 pl-3 pr-9 text-sm', selectClassName)}>
        {options.map(option => <option key={option.value} value={option.value} disabled={option.disabled}>{option.label}</option>)}
      </select>
      <ChevronDown aria-hidden="true" className={cx('pointer-events-none absolute right-3 size-4 text-fg-quaternary', size === 'lg' && 'size-5')}/>
    </div>
    {hint && <p id={hintId} className="mt-2 text-xs text-tertiary">{hint}</p>}
  </div>;
}
