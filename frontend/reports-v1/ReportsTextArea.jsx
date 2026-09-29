import React from 'react';
import {TextAreaBase} from './untitled-kit/src/components/base/textarea/textarea.tsx';

export function ReportsTextArea({className = '', ...props}) {
  return <TextAreaBase {...props} size="sm" className={`reports-ui-textarea ${className}`.trim()} />;
}
