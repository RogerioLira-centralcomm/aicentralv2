import React from 'react';
import {CaduSelectField} from '../cadu-design-system/components/CaduField.jsx';

/** Reports select: the shared Cadu select fed by <option> children. */
export function ReportsNativeSelect({className = '', ...props}) {
  return <CaduSelectField {...props} className={`reports-ui-select ${className}`.trim()}/>;
}
