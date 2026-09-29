// Adapted from Untitled UI React v8 base/input/input.tsx and base/input/label.tsx.
// The application uses React 18, so this entry keeps refs on React Aria's Input.
import React from 'react';
import type {Ref} from 'react';
import type {InputProps as AriaInputProps, TextFieldProps as AriaTextFieldProps} from 'react-aria-components';
import {Input as AriaInput, Label as AriaLabel, TextField as AriaTextField} from 'react-aria-components';
import {cx} from './utils/cx';

type WorkspaceInputProps = Omit<AriaInputProps, 'name' | 'value' | 'defaultValue' | 'onChange' | 'className' | 'size'> &
  Pick<AriaTextFieldProps, 'name' | 'value' | 'defaultValue' | 'onChange' | 'isDisabled' | 'isRequired'> & {
    label: string;
    description?: string;
    error?: string;
    className?: string;
    inputClassName?: string;
    inputRef?: Ref<HTMLInputElement>;
  };

export function Input({label, description, error, className, inputClassName, inputRef, isDisabled, isRequired, name, defaultValue, value, onChange, ...inputProps}: WorkspaceInputProps) {
  return <AriaTextField name={name} defaultValue={defaultValue} value={value} onChange={onChange} isDisabled={isDisabled} isRequired={isRequired} validationBehavior="native" className={cx('cadu-untitled-field group flex w-full min-w-0 flex-col gap-1.5', className)}>
    <AriaLabel data-label="true" className="text-sm font-medium text-secondary">{label}{isRequired && <span className="ml-0.5 text-brand-tertiary" aria-hidden="true">*</span>}</AriaLabel>
    <span className="cadu-untitled-field__control group relative flex min-h-10 w-full min-w-0 items-center rounded-lg bg-primary shadow-xs ring-1 ring-primary ring-inset transition-shadow duration-100 ease-linear focus-within:ring-2 focus-within:ring-brand">
      <AriaInput {...inputProps} ref={inputRef} disabled={isDisabled} required={isRequired} className={cx('m-0 w-full min-w-0 bg-transparent px-3 py-2 text-sm text-primary outline-hidden placeholder:text-placeholder', inputClassName)} />
    </span>
    {description && <span className="text-xs text-tertiary">{description}</span>}
    {error && <span className="text-xs text-error-primary" role="alert">{error}</span>}
  </AriaTextField>;
}
