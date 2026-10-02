import React, {useEffect, useState} from 'react';
import {FORMAT_LABELS, FORMATS} from '../shared';
import {StudioModal} from './StudioModal';

const formatTokens = value => {
  const tokens = Math.max(0, Math.round(Number(value) || 0));
  return tokens >= 1000 ? `~${(tokens / 1000).toLocaleString('pt-BR', {maximumFractionDigits: 1})} mil tokens` : `~${tokens.toLocaleString('pt-BR')} tokens`;
};

// Desdobrar: one piece per chosen format, generated from the base one at a time.
export function ExpandDialog({asset, sourceFormat = '', onClose, onQueue, onQuote}) {
  const [formats, setFormats] = useState(() => new Set(FORMATS.filter(item => item !== sourceFormat)));
  const [queued, setQueued] = useState(false);
  const [estimate, setEstimate] = useState(null);
  const chosen = FORMATS.filter(item => formats.has(item));
  const toggle = value => setFormats(current => { const next = new Set(current); next.has(value) ? next.delete(value) : next.add(value); return next; });
  useEffect(() => {
    let active = true;
    setEstimate(null);
    if (!chosen.length) return undefined;
    onQuote({formats: chosen}).then(value => { if (active) setEstimate(value); }).catch(() => { if (active) setEstimate(false); });
    return () => { active = false; };
  }, [chosen.join('|'), onQuote]);
  const prepare = async () => { if (!chosen.length || queued) return; setQueued(true); onClose(); try { await onQueue({formats: chosen}); } finally { setQueued(false); } };
  const pieces = `${chosen.length} ${chosen.length === 1 ? 'peça' : 'peças'}`;
  const estimateLabel = !chosen.length ? 'Escolha ao menos um formato.' : estimate === null ? 'Calculando custo…' : estimate === false ? 'Não foi possível calcular o custo.' : `${pieces} · ${formatTokens(estimate)}`;
  return <StudioModal title="Desdobrar formatos" onClose={onClose}><div className="se-expand-dialog">
    <div className="se-expand-base">{asset && <img src={asset.url} alt="Peça base"/>}<div><strong>Peça-base{sourceFormat ? ` · ${FORMAT_LABELS[sourceFormat] || sourceFormat}` : ''}</strong><span>Cada formato vira uma peça, recomposta a partir desta: mesmos textos, logo e cores, layout ajustado à nova proporção.</span></div></div>
    <div><h3>Formatos</h3><div className="se-format-options">{FORMATS.map(item => <button type="button" key={item} className={formats.has(item) ? 'is-active' : ''} aria-pressed={formats.has(item)} onClick={() => toggle(item)}>{FORMAT_LABELS[item] || item}</button>)}</div></div>
    <footer><span>{estimateLabel}</span><button type="button" disabled={!chosen.length || queued || estimate === null || estimate === false} onClick={prepare}>{queued ? 'Preparando…' : `Gerar ${pieces}`}</button></footer>
  </div></StudioModal>;
}
