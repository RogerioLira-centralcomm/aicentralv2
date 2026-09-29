import React, {useEffect, useRef, useState} from 'react';

/** A snapshot is a baseline; only a newly observed transition pulses. */
export function FlowLiveEdge({transitionId, ready, className = '', ...props}) {
  const previous = useRef(null);
  const initialized = useRef(false);
  const [pulse, setPulse] = useState(false);
  useEffect(() => {
    setPulse(false);
    if (!ready) {initialized.current=false;return;}
    if (!initialized.current) {
      previous.current=transitionId || null;initialized.current=true;return;
    }
    if (!transitionId || (previous.current && BigInt(transitionId)<=BigInt(previous.current))) return;
    previous.current=transitionId;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    setPulse(true);
    const timer=setTimeout(()=>setPulse(false),1800);
    return()=>clearTimeout(timer);
  }, [transitionId,ready]);
  return <path {...props} className={`${className}${pulse?' is-new-transition':''}`}/>;
}
