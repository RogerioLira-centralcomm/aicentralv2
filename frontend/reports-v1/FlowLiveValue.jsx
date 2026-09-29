import React, {useEffect, useRef, useState} from 'react';

export function FlowLiveValue({value, decimals = false}) {
  const available = value !== null && value !== undefined && Number.isFinite(Number(value));
  const target = Number.isFinite(Number(value)) ? Number(value) : 0;
  const previous = useRef(target);
  const [display, setDisplay] = useState(target);
  const [changed, setChanged] = useState(false);
  useEffect(() => {
    const from = previous.current;
    previous.current = target;
    if (from === target) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      setDisplay(target);
      return;
    }
    setChanged(true);
    let frame;
    const started = performance.now();
    const tick = now => {
      const progress = Math.min(1, (now - started) / 650);
      setDisplay(from + (target - from) * (1 - (1 - progress) ** 3));
      if (progress < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    const timer = window.setTimeout(() => setChanged(false), 1100);
    return () => {cancelAnimationFrame(frame);window.clearTimeout(timer);};
  }, [target]);
  const format = number => new Intl.NumberFormat('pt-BR', {maximumFractionDigits: decimals ? 1 : 0}).format(number);
  if (!available) return <span aria-label="Indisponível">—</span>;
  return <span className={`reports-live-value${changed ? ' is-updated' : ''}`} aria-label={format(target)}><span aria-hidden="true">{format(display)}</span></span>;
}
