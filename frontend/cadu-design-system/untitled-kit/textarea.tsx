// Adapted from Untitled UI React v8 base/textarea/textarea.tsx for React 18.
import React from 'react';
import type {TextAreaProps as AriaTextAreaProps, TextFieldProps as AriaTextFieldProps} from 'react-aria-components';
import {Label as AriaLabel, TextArea as AriaTextArea, TextField as AriaTextField} from 'react-aria-components';
import {cx} from './utils/cx';

type WorkspaceTextareaProps = Omit<AriaTextAreaProps, 'name' | 'value' | 'defaultValue' | 'onChange' | 'className'> &
  Pick<AriaTextFieldProps, 'name' | 'value' | 'defaultValue' | 'onChange' | 'isDisabled' | 'isRequired'> & {
    label:string;
    hint?:string;
    className?:string;
  };

export function Textarea({label, hint, className, name, value, defaultValue, onChange, isDisabled, isRequired, ...props}: WorkspaceTextareaProps) {
  return <AriaTextField name={name} value={value} defaultValue={defaultValue} onChange={onChange} isDisabled={isDisabled} isRequired={isRequired} validationBehavior="native" className={cx('cadu-untitled-textarea group flex w-full min-w-0 flex-col gap-1.5', className)}>
    <AriaLabel data-label="true" className="text-sm font-medium text-secondary">{label}{isRequired && <span className="ml-0.5 text-brand-tertiary" aria-hidden="true">*</span>}</AriaLabel>
    <AriaTextArea {...props} required={isRequired} disabled={isDisabled} data-cadu-untitled-textarea="" className="min-h-20 w-full resize-y rounded-lg bg-primary px-3 py-2 text-sm text-primary shadow-xs ring-1 ring-primary ring-inset outline-hidden transition-shadow duration-100 ease-linear focus-visible:ring-2 focus-visible:ring-brand placeholder:text-placeholder"/>
    {hint && <span className="text-xs text-tertiary">{hint}</span>}
  </AriaTextField>;
}
