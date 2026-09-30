// Adapted from Untitled UI React v8 base/textarea/textarea.tsx. Native events, optional label.
import React, {useId} from 'react';
import type {TextareaHTMLAttributes} from 'react';
import {cx} from './utils/cx';

export type TextareaProps = Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, 'className'> & {
  label?: string;
  hint?: string;
  error?: string;
  className?: string;
  isDisabled?: boolean;
  isRequired?: boolean;
};

export function Textarea({label, hint, error, className, isDisabled, isRequired, disabled, required, id: providedId, ...props}: TextareaProps) {
  const generatedId = useId();
  const id = providedId || `cadu-textarea-${generatedId}`;
  const describedBy = [hint ? `${id}-hint` : '', error ? `${id}-error` : '', props['aria-describedby'] || ''].filter(Boolean).join(' ') || undefined;
  const isRequiredField = required ?? isRequired;
  const isDisabledField = disabled ?? isDisabled;
  return <div className={cx('cadu-untitled-textarea group flex w-full min-w-0 flex-col gap-1.5', className)}>
    {label && <label data-label="true" htmlFor={id} className="text-sm font-medium text-secondary">{label}{isRequiredField && <span className="ml-0.5 text-brand-tertiary" aria-hidden="true">*</span>}</label>}
    <textarea {...props} id={id} required={isRequiredField} disabled={isDisabledField} aria-invalid={error ? true : props['aria-invalid']} aria-describedby={describedBy} data-cadu-untitled-textarea="" className="min-h-20 w-full resize-y appearance-none rounded-lg border-0 bg-primary px-3 py-2 text-sm text-primary shadow-xs ring-1 ring-primary ring-inset outline-hidden transition-shadow duration-100 ease-linear focus-visible:ring-2 focus-visible:ring-brand placeholder:text-placeholder disabled:cursor-not-allowed disabled:opacity-60" />
    {hint && <span id={`${id}-hint`} className="text-xs text-tertiary">{hint}</span>}
    {error && <span id={`${id}-error`} className="text-xs text-error-primary" role="alert">{error}</span>}
  </div>;
}
