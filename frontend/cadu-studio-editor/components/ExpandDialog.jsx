import React, {useEffect, useRef, useState} from 'react';
import {FORMATS} from '../shared';
import {StudioModal} from './StudioModal';

export function ExpandDialog({asset, onClose, onQueue, onQuote}) {
  const [count, setCount] = useState(4);
  const [formats, setFormats] = useState(new Set(['4:5', '1:1']));
  const [queued, setQueued] = useState(false);
  const [estimate, setEstimate] = useState(null);
  const toggle = value => setFormats(current => { const next = new Set(current); next.has(value) ? next.delete(value) : next.add(value); return next; });
  useEffect(() => { let active = true; setEstimate(null); onQuote({count, formats: [...formats]}).then(value => { if (active) setEstimate(value); }).catch(() => { if (active) setEstimate(false); }); return () => { active = false; }; }, [count, formats, onQuote]);
  const prepare = async () => { if (!formats.size || queued) return; setQueued(true); try { await onQueue({count, formats: [...formats]}); onClose(); } finally { setQueued(false); } };
  const estimateLabel = estimate === null ? 'Calculando estimativa…' : estimate === false ? 'Não foi possível calcular a estimativa.' : `${Number(estimate).toLocaleString('pt-BR')} créditos estimados para ${count} peças.`;
  return <StudioModal title="Desdobrar formatos" onClose={onClose}><div className="se-expand-dialog"><div className="se-expand-base">{asset && <img src={asset.url} alt="Peça base"/>}<div><strong>Peça-base</strong><span>Esta versão será usada como referência em todas as saídas.</span></div></div><div><h3>Formatos</h3><div className="se-format-options">{FORMATS.map(item => <button type="button" key={item} className={formats.has(item) ? 'is-active' : ''} onClick={() => toggle(item)}>{item}</button>)}</div></div><div className="se-expand-quantity"><span>Quantidade de peças</span><button type="button" onClick={() => setCount(value => Math.max(1, value - 1))}>−</button><strong>{count}</strong><button type="button" onClick={() => setCount(value => Math.min(30, value + 1))}>+</button><small>Uma geração por vez, sempre a partir da peça-base.</small></div><footer><span>{estimateLabel}</span><button type="button" disabled={!formats.size || queued || estimate === null || estimate === false} onClick={prepare}>{queued ? 'Preparando…' : 'Preparar fila'}</button></footer></div></StudioModal>;
}
