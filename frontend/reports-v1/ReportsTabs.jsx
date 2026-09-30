import React from 'react';
import {CaduTabs} from '../cadu-design-system/components/CaduTabs.jsx';

export function ReportsTabs({className = '', ...props}) {
  return <CaduTabs {...props} className={`reports-tabs ${className}`.trim()}/>;
}
