import React, {forwardRef, useImperativeHandle, useRef, useState} from 'react';

function bounds(points, width, height) {
  if (!points.length) return null;
  const xs = points.map(point => point.x);
  const ys = points.map(point => point.y);
  const left = Math.max(0, Math.min(...xs));
  const top = Math.max(0, Math.min(...ys));
  const right = Math.min(width, Math.max(...xs));
  const bottom = Math.min(height, Math.max(...ys));
  return [Math.round(left), Math.round(top), Math.max(1, Math.round(right - left)), Math.max(1, Math.round(bottom - top))];
}

export const MaskCanvas = forwardRef(function MaskCanvas({active, width = 1600, height = 900, onChange}, ref) {
  const canvas = useRef(null);
  const points = useRef([]);
  const [drawing, setDrawing] = useState(false);
  const paint = () => {
    const element = canvas.current;
    if (!element) return;
    const context = element.getContext('2d');
    context.clearRect(0, 0, element.width, element.height);
    if (!points.current.length) return;
    // The exported PNG is intentionally a binary mask: transparent/black outside,
    // white inside. The backend can therefore pass it to any image model without
    // interpreting presentation colours from the Studio UI.
    context.strokeStyle = 'rgba(255,255,255,.98)';
    context.lineWidth = 42;
    context.lineJoin = 'round';
    context.lineCap = 'round';
    context.beginPath();
    points.current.forEach((point, index) => index ? context.lineTo(point.x, point.y) : context.moveTo(point.x, point.y));
    context.stroke();
  };
  const exportMask = () => {
    const element = canvas.current;
    if (!element || !points.current.length) return null;
    return {dataUrl: element.toDataURL('image/png'), bounds: bounds(points.current, element.width, element.height), width, height};
  };
  useImperativeHandle(ref, () => ({
    clear() { points.current = []; paint(); onChange(null); },
    exportMask,
  }), [onChange, width, height]);
  const localPoint = event => {
    const rect = event.currentTarget.getBoundingClientRect();
    return {x: ((event.clientX - rect.left) / rect.width) * width, y: ((event.clientY - rect.top) / rect.height) * height};
  };
  const finish = () => { if (!drawing) return; setDrawing(false); onChange(exportMask()); };
  return <canvas ref={canvas} width={width} height={height} className={`se-mask-canvas ${active ? 'is-active' : ''}`} onPointerDown={event => { if (!active) return; event.currentTarget.setPointerCapture?.(event.pointerId); points.current.push(localPoint(event)); setDrawing(true); paint(); }} onPointerMove={event => { if (!active || !drawing) return; points.current.push(localPoint(event)); paint(); }} onPointerUp={finish} onPointerCancel={finish} aria-label={active ? 'Desenhe a região que será editada' : undefined}/>;
});
