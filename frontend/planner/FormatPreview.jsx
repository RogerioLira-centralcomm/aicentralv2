import React from 'react';
import {Icon} from '../cadu-design-system/components/Icon.jsx';

/** "300x250", "1.920 × 1.080 px", "9:16" → {width, height}; anything else → null. */
export function parseSize(value) {
  const text = String(value || '').toLowerCase().replace(/\./g, '');
  const pixels = text.match(/(\d{2,5})\s*(?:x|×|por)\s*(\d{2,5})/);
  if (pixels) return {width: Number(pixels[1]), height: Number(pixels[2]), ratio: false};
  const ratio = text.match(/(\d{1,2})\s*:\s*(\d{1,2})/);
  if (ratio && Number(ratio[1]) && Number(ratio[2])) return {width: Number(ratio[1]), height: Number(ratio[2]), ratio: true};
  return null;
}

const BOX = {width: 220, height: 140};

/**
 * The format drawn to scale with its width and height marked, so a size reads
 * at a glance. It comes from the registered dimensions alone; a format without
 * a readable size shows a plain icon, never a broken image.
 */
export function FormatPreview({dimensions, name = '', type = '', compact = false}) {
  const size = parseSize(dimensions);
  if (!size) return <span className="fmt-preview is-empty" role="img" aria-label={`${name}: sem medida cadastrada`}><Icon name={/[aá]udio|podcast/i.test(`${name} ${type}`) ? 'audio' : 'table'} size={22}/></span>;
  const gutter = 26;
  const scale = Math.min((BOX.width - 80) / size.width, (BOX.height - gutter * 2) / size.height);
  const width = Math.max(10, size.width * scale);
  const height = Math.max(10, size.height * scale);
  const x = (BOX.width - width) / 2;
  const y = (BOX.height - height) / 2;
  const label = size.ratio ? `${size.width}:${size.height}` : null;
  return <svg className={`fmt-preview${compact ? ' is-compact' : ''}`} viewBox={`0 0 ${BOX.width} ${BOX.height}`} role="img"
    aria-label={`${name} ${size.ratio ? `proporção ${label}` : `${size.width} por ${size.height} pixels`}`.trim()}>
    <rect className="fmt-preview__piece" x={x} y={y} width={width} height={height} rx="3"/>
    <line className="fmt-preview__dim" x1={x} x2={x + width} y1={y - 7} y2={y - 7}/>
    <line className="fmt-preview__dim" x1={x + width + 8} x2={x + width + 8} y1={y} y2={y + height}/>
    <text className="fmt-preview__text" x={BOX.width / 2} y={Math.max(12, y - 12)} textAnchor="middle">{size.ratio ? label : `${size.width} px`}</text>
    {!size.ratio && <text className="fmt-preview__text" x={Math.min(BOX.width - 2, x + width + 12)} y={BOX.height / 2 + 3} textAnchor="start">{size.height}</text>}
  </svg>;
}
