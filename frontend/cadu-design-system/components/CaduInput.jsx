import React from 'react';
import {Input} from '../untitled-kit/input';

export const CaduInput = React.forwardRef(function CaduInput({label, description, error, disabled, required, ...props}, ref) {
  return <Input label={label} description={description} error={error} isDisabled={disabled} isRequired={required} inputRef={ref} data-cadu-untitled-input="" {...props}/>;
});
