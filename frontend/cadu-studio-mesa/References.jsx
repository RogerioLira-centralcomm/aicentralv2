import React, {useRef, useState} from 'react';
import {Ico} from './Glyph.jsx';

export const MAX_REFERENCES = 2;
const ratio = (w, h) => (Number(w) || 1) / (Number(h) || 1);
const sameShape = (item, format) => format && item.width && item.height && Math.abs(Math.log(ratio(item.width, item.height) / ratio(format.width, format.height))) < 0.06;
// Máscaras de composição são de anúncio: só fazem sentido em séries de anúncio e post, e no formato da peça.
const COMPOSITION_TYPES = new Set(['anuncio', 'post']);

/**
 * Referências flutuantes. Respeitam a linha de trabalho da mesa: o formato da peça-alvo (selecionada ou da série
 * que vai nascer) e o tipo da série. Quando o alvo muda, as escolhas que não servem mais saem sozinhas.
 */
export function References({shelf, loading, target, picked, setPicked, onUpload, open, setOpen}) {
  const [tab, setTab] = useState('marca');
  const [broken, setBroken] = useState(() => new Set()); // arquivo que não carrega some da lista
  const file = useRef(null);
  const {format, type, multi} = target;
  const allowComposition = COMPOSITION_TYPES.has(type) && !multi;
  const masks = allowComposition ? (shelf.masks || []).filter(item => sameShape(item, format)) : [];
  const brand = (shelf.items || []).filter(item => item.source_type === 'brand' || String(item.id || '').startsWith('brand:'));
  const mine = (shelf.items || []).filter(item => !brand.includes(item) && (item.asset_url || item.url));
  const ok = item => !broken.has(item.id);
  const lists = {composicao: masks.filter(ok), marca: brand.filter(ok), enviadas: mine.filter(ok)};
  const tabs = [['marca', 'Marca', lists.marca.length], ['enviadas', 'Enviadas', lists.enviadas.length], ...(allowComposition ? [['composicao', 'Composição', lists.composicao.length]] : [])];
  const current = tabs.some(([key]) => key === tab) ? tab : 'marca';
  const urlOf = item => item.url || item.asset_url;
  const isPicked = item => picked.some(entry => entry.id === item.id);
  const toggle = item => setPicked(list => isPicked(item) ? list.filter(entry => entry.id !== item.id)
    : [...list, {id: item.id, url: urlOf(item), role: item.role === 'composition' ? 'composition' : 'reference', source: current === 'composicao' ? 'global' : current === 'marca' ? 'project' : 'user',
      label: item.label || item.title || 'Referência', width: item.width, height: item.height}].slice(-MAX_REFERENCES));

  if (!open) return <button type="button" className="mq-refs-tab" onClick={() => setOpen(true)}>Referências{picked.length ? ` · ${picked.length}` : ''}</button>;
  return <section className="mq-panel mq-panel--col mq-refs" aria-label="Referências">
    <header><strong>Referências</strong><small>{format ? (multi ? 'Vários formatos' : `${format.label}`) : 'Escolha uma peça ou tipo'}</small>
      <button type="button" className="mq-icon" onClick={() => setOpen(false)} aria-label="Recolher referências"><Ico name="close" size={16}/></button></header>
    <nav className="mq-refs__tabs">{tabs.map(([key, label, count]) => <button key={key} type="button" className={current === key ? 'is-on' : ''} onClick={() => setTab(key)}>{label}<em>{count}</em></button>)}</nav>
    {loading ? <p className="mq-refs__note">Carregando…</p>
      : lists[current].length ? <div className="mq-refs__grid">{lists[current].slice(0, 30).map(item => <button key={item.id} type="button" className={isPicked(item) ? 'is-on' : ''} onClick={() => toggle(item)} title={item.label || item.title}>
          <img src={urlOf(item)} alt="" loading="lazy" onError={() => setBroken(current => new Set(current).add(item.id))}/>{isPicked(item) && <i>✓</i>}</button>)}</div>
      : <p className="mq-refs__note">{current === 'composicao' ? 'Nenhuma composição para este formato.' : current === 'marca' ? 'A marca não tem imagens de referência.' : 'Envie imagens para usar como referência.'}</p>}
    <footer>
      <span>{picked.length}/{MAX_REFERENCES} na próxima ação{!allowComposition && type ? ' · composições só em anúncio e post' : ''}</span>
      <input ref={file} type="file" accept="image/*" multiple hidden onChange={event => { const files = event.target.files; event.target.value = ''; if (files?.length) { onUpload(files); setTab('enviadas'); } }}/>
      <button type="button" className="mq-btn" onClick={() => file.current?.click()}>Enviar</button>
    </footer>
  </section>;
}

/** Remove escolhas que não servem para o novo alvo (composição de outro formato ou fora de anúncio/post). */
export function pruneForTarget(picked, target) {
  return picked.filter(item => item.role !== 'composition' || (COMPOSITION_TYPES.has(target.type) && !target.multi && sameShape(item, target.format)));
}
