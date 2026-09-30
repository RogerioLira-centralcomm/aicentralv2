import React from 'react';
import {InputBase} from '../cadu-design-system/untitled-kit/input-base.tsx';

const NATIVE_TYPES = new Set(['checkbox', 'radio', 'file', 'color', 'hidden', 'range', 'date', 'datetime-local', 'time', 'month', 'week']);

/** Keeps existing form events while using the official Untitled UI input base. */
export function ReportsFieldInput({type = 'text', required, disabled, className, ...rest}) {
  if (NATIVE_TYPES.has(type)) {
    return <input {...rest} type={type} required={required} disabled={disabled} className={className} />;
  }
  return <InputBase
    {...rest}
    type={type}
    isRequired={required}
    isDisabled={disabled}
    disabled={disabled}
    size="sm"
    wrapperClassName="reports-ui-field"
    inputClassName={className}
  />;
}
