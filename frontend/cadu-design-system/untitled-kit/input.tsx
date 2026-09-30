// Adapted from Untitled UI React v8 base/input/input.tsx and base/input/label.tsx.
// Single input for every product: native events, optional label, hint and error.
import React, {useId} from 'react';
import type {InputHTMLAttributes, ReactNode, Ref} from 'react';
import {cx} from './utils/cx';

export type InputProps = Omit<InputHTMLAttributes<HTMLInputElement>, 'size' | 'className'> & {
  label?: string;
  description?: string;
  hint?: string;
  error?: string;
  size?: 'sm' | 'md';
  className?: string;
  wrapperClassName?: string;
  inputClassName?: string;
  inputRef?: Ref<HTMLInputElement>;
  isDisabled?: boolean;
  isRequired?: boolean;
  leading?: ReactNode;
};

export function Input({label, description, hint, error, size = 'md', className, wrapperClassName, inputClassName, inputRef, isDisabled, isRequired, disabled, required, id: providedId, leading, ...inputProps}: InputProps) {
  const generatedId = useId();
  const id = providedId || `cadu-input-${generatedId}`;
  const helper = hint || description;
  const describedBy = [helper ? `${id}-hint` : '', error ? `${id}-error` : '', inputProps['aria-describedby'] || ''].filter(Boolean).join(' ') || undefined;
  const isRequiredField = required ?? isRequired;
  const isDisabledField = disabled ?? isDisabled;
  return <div className={cx('cadu-untitled-field group flex w-full min-w-0 flex-col gap-1.5', className)}>
    {label && <label data-label="true" htmlFor={id} className="text-sm font-medium text-secondary">{label}{isRequiredField && <span className="ml-0.5 text-brand-tertiary" aria-hidden="true">*</span>}</label>}
    <span className={cx('cadu-untitled-field__control group relative flex w-full min-w-0 items-center rounded-lg bg-primary shadow-xs ring-1 ring-primary ring-inset transition-shadow duration-100 ease-linear focus-within:ring-2 focus-within:ring-brand', size === 'sm' ? 'min-h-9' : 'min-h-10', isDisabledField && 'opacity-60', wrapperClassName)}>
      {leading}
      <input {...inputProps} id={id} ref={inputRef} disabled={isDisabledField} required={isRequiredField} aria-invalid={error ? true : inputProps['aria-invalid']} aria-describedby={describedBy} className={cx('m-0 w-full min-w-0 appearance-none border-0 bg-transparent px-3 py-2 text-sm text-primary outline-hidden placeholder:text-placeholder disabled:cursor-not-allowed', inputClassName)} />
    </span>
    {helper && <span id={`${id}-hint`} className="text-xs text-tertiary">{helper}</span>}
    {error && <span id={`${id}-error`} className="text-xs text-error-primary" role="alert">{error}</span>}
  </div>;
}
