import React from 'react';
import {Textarea} from '../untitled-kit/textarea';

export function CaduTextarea({disabled, required, ...props}) {
  return <Textarea disabled={disabled} required={required} {...props}/>;
}
