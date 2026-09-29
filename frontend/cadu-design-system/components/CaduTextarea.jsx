import React from 'react';
import {Textarea} from '../untitled-kit/textarea';

export function CaduTextarea({disabled, required, ...props}) {
  return <Textarea isDisabled={disabled} isRequired={required} {...props}/>;
}
