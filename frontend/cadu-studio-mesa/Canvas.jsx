import React, {useCallback, useEffect, useImperativeHandle, useRef, useState, forwardRef} from 'react';

const MIN_Z = 0.05, MAX_Z = 3;
const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

/**
 * Canvas infinito: só desenha o que está na tela; o nível de detalhe muda com o zoom.
 * Arrastar o fundo move; Shift+arrastar faz seleção em laço; espaço+arrastar move mesmo sobre as peças.
 */
export const Canvas = forwardRef(function Canvas({scene, camera, setCamera, selected, fresh, onSelect, onLasso, onOpen, onPin}, ref) {
  const host = useRef(null);
  const [size, setSize] = useState({w: 1, h: 1});
  const [lasso, setLasso] = useState(null);
  const [space, setSpace] = useState(false);
  const drag = useRef(null);

  useEffect(() => {
    const node = host.current;
    const observer = new ResizeObserver(([entry]) => setSize({w: entry.contentRect.width, h: entry.contentRect.height}));
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const down = event => { if (event.code === 'Space' && !/INPUT|TEXTAREA/.test(document.activeElement?.tagName)) { setSpace(true); event.preventDefault(); } };
    const up = event => { if (event.code === 'Space') setSpace(false); };
    window.addEventListener('keydown', down); window.addEventListener('keyup', up);
    return () => { window.removeEventListener('keydown', down); window.removeEventListener('keyup', up); };
  }, []);

  // Área livre do HUD: painel da esquerda, barra do topo e chat embaixo não cobrem o que foi enquadrado.
  const fit = useCallback((box, pad = 40) => {
    if (!box || !size.w) return;
    const wide = size.w > 900;
    const inset = {left: wide ? 316 : 16, right: wide ? 24 : 16, top: 72, bottom: wide ? 170 : 230};
    const w = size.w - inset.left - inset.right - pad * 2, h = size.h - inset.top - inset.bottom - pad * 2;
    const z = clamp(Math.min(w / Math.max(box.w, 1), h / Math.max(box.h, 1)), MIN_Z, 1.2);
    setCamera({z, x: inset.left + pad + w / 2 - (box.x + box.w / 2) * z, y: inset.top + pad + h / 2 - (box.y + box.h / 2) * z});
  }, [size, setCamera]);

  const zoomAt = useCallback((factor, cx = size.w / 2, cy = size.h / 2) => {
    setCamera(cam => {
      const z = clamp(cam.z * factor, MIN_Z, MAX_Z);
      return {z, x: cx - (cx - cam.x) * (z / cam.z), y: cy - (cy - cam.y) * (z / cam.z)};
    });
  }, [size, setCamera]);

  useImperativeHandle(ref, () => ({fit, zoomAt, size, centerOn: (x, y) => setCamera(cam => ({...cam, x: size.w / 2 - x * cam.z, y: size.h / 2 - y * cam.z}))}), [fit, zoomAt, size, setCamera]);

  // Rolagem com Ctrl/⌘ (ou pinça no trackpad) dá zoom no cursor; rolagem simples move.
  useEffect(() => {
    const node = host.current;
    const wheel = event => {
      event.preventDefault();
      const rect = node.getBoundingClientRect();
      if (event.ctrlKey || event.metaKey) zoomAt(Math.exp(-event.deltaY * 0.0022), event.clientX - rect.left, event.clientY - rect.top);
      else setCamera(cam => ({...cam, x: cam.x - event.deltaX, y: cam.y - event.deltaY}));
    };
    node.addEventListener('wheel', wheel, {passive: false});
    return () => node.removeEventListener('wheel', wheel);
  }, [zoomAt, setCamera]);

  const toWorld = (clientX, clientY) => {
    const rect = host.current.getBoundingClientRect();
    return {x: (clientX - rect.left - camera.x) / camera.z, y: (clientY - rect.top - camera.y) / camera.z};
  };

  const onPointerDown = event => {
    if (event.button !== 0 && event.button !== 1) return;
    const card = event.target.closest('[data-node]');
    if (card && !space && event.button === 0) {
      const id = card.dataset.node;
      onSelect(id, event.shiftKey || event.metaKey);
      if (card.dataset.star === '1') drag.current = {mode: 'piece', piece: card.dataset.piece, start: toWorld(event.clientX, event.clientY), moved: false, origin: {x: Number(card.dataset.x), y: Number(card.dataset.y)}};
      host.current.setPointerCapture(event.pointerId);
      return;
    }
    if (event.shiftKey && !space && event.button === 0) {
      const start = toWorld(event.clientX, event.clientY);
      drag.current = {mode: 'lasso', start};
      setLasso({x: start.x, y: start.y, w: 0, h: 0});
    } else {
      drag.current = {mode: 'pan', sx: event.clientX, sy: event.clientY, cam: camera, moved: false};
    }
    host.current.setPointerCapture(event.pointerId);
  };
  const onPointerMove = event => {
    const state = drag.current;
    if (!state) return;
    if (state.mode === 'pan') {
      const dx = event.clientX - state.sx, dy = event.clientY - state.sy;
      if (Math.abs(dx) + Math.abs(dy) > 3) state.moved = true;
      setCamera({...state.cam, x: state.cam.x + dx, y: state.cam.y + dy});
    } else if (state.mode === 'lasso') {
      const at = toWorld(event.clientX, event.clientY);
      setLasso({x: Math.min(at.x, state.start.x), y: Math.min(at.y, state.start.y), w: Math.abs(at.x - state.start.x), h: Math.abs(at.y - state.start.y)});
    } else if (state.mode === 'piece') {
      const at = toWorld(event.clientX, event.clientY);
      const dx = at.x - state.start.x, dy = at.y - state.start.y;
      if (Math.abs(dx) + Math.abs(dy) > 6 / camera.z) state.moved = true;
      if (state.moved) state.pin = {x: Math.round(state.origin.x + dx), y: Math.round(state.origin.y + dy)};
      if (state.moved) onPin(state.piece, state.pin, true);
    }
  };
  const onPointerUp = event => {
    const state = drag.current;
    drag.current = null;
    if (!state) return;
    if (state.mode === 'pan' && !state.moved && event.target === host.current.firstChild) onSelect(null, false);
    if (state.mode === 'lasso' && lasso) {
      const hits = scene.nodes.filter(node => node.kind === 'version' && node.x < lasso.x + lasso.w && node.x + node.w > lasso.x && node.y < lasso.y + lasso.h && node.y + node.h > lasso.y).map(node => node.id);
      onLasso(hits, event.shiftKey);
      setLasso(null);
    }
    if (state.mode === 'piece' && state.moved) onPin(state.piece, state.pin, false);
  };

  const view = {x: -camera.x / camera.z, y: -camera.y / camera.z, w: size.w / camera.z, h: size.h / camera.z};
  const margin = 400 / camera.z;
  const visible = node => node.x < view.x + view.w + margin && node.x + node.w > view.x - margin && node.y < view.y + view.h + margin && node.y + node.h > view.y - margin;
  const detail = camera.z < 0.3 ? 'far' : camera.z < 0.7 ? 'mid' : 'near';

  // Rótulos em tamanho de tela: crescem no mundo quando o zoom diminui, até um limite.
  const inv = Math.min(2.2, Math.max(1, 1 / camera.z)), invHead = Math.min(1.9, Math.max(1, 1 / camera.z));
  return <div ref={host} className={`mq-canvas is-${detail}${space ? ' is-grab' : ''}`} style={{'--inv': inv, '--inv-head': invHead}} onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={onPointerUp}>
    <div className="mq-canvas__bg" style={{backgroundPosition: `${camera.x}px ${camera.y}px`, backgroundSize: `${24 * camera.z}px ${24 * camera.z}px`}}/>
    <div className="mq-world" style={{transform: `translate(${camera.x}px, ${camera.y}px) scale(${camera.z})`}}>
      <svg className="mq-links" style={{left: scene.bounds.x - 2000, top: scene.bounds.y - 2000}} width={scene.bounds.w + 4000} height={scene.bounds.h + 4000}>
        {scene.links.map((link, index) => {
          const ox = scene.bounds.x - 2000, oy = scene.bounds.y - 2000;
          const x1 = link.from.x + link.from.w - ox, y1 = link.from.y + 40 - oy, x2 = link.to.x - ox, y2 = link.to.y + 40 - oy;
          return <path key={index} d={`M${x1},${y1} C${x1 + 30},${y1} ${x2 - 30},${y2} ${x2},${y2}`} className={`mq-link is-${link.kind}`}/>;
        })}
      </svg>
      {scene.bands.filter(visible).map(band => <div key={band.series.id} className="mq-band" style={{left: band.x, top: band.y, width: band.w, height: band.h}}>
        <header><strong>{band.series.title}</strong><span>{band.series.pieces.length} {band.series.pieces.length === 1 ? 'peça' : 'peças'}</span></header>
      </div>)}
      {scene.nodes.filter(visible).map(node => <Node key={node.id} node={node} detail={detail} selected={selected.has(node.id)} fresh={fresh.has(node.id)} onOpen={onOpen}/>)}
      {lasso && <div className="mq-lasso" style={{left: lasso.x, top: lasso.y, width: lasso.w, height: lasso.h}}/>}
    </div>
  </div>;
});

function Node({node, detail, selected, fresh, onOpen}) {
  const {version, piece} = node;
  const label = node.star ? piece.title : null;
  const style = {left: node.x, top: node.y, width: node.w, height: node.h};
  if (node.kind === 'empty') return <div className="mq-node is-empty" style={style}><span>Aguardando</span></div>;
  const status = version.status;
  return <div className={`mq-node${node.star ? ' is-star' : ' is-version'}${selected ? ' is-selected' : ''}${fresh ? ' is-fresh' : ''} is-${status}`} style={style}
    data-node={node.id} data-piece={piece.id} data-star={node.star ? '1' : '0'} data-x={node.x} data-y={node.y}
    onDoubleClick={() => onOpen(node.id)}>
    {node.star && detail !== 'far' && <div className="mq-node__label" title={`${label} · ${piece.format?.label || ''}`}><span>{node.series.anchor === version.id ? '⚓' : '★'}</span><strong>{label}</strong>{detail === 'near' && <em>{piece.format?.label}</em>}</div>}
    {!node.star && detail === 'near' && <div className="mq-node__label is-small"><em>v{piece.versions.indexOf(version) + 1}{version.action ? ` · ${ACTION_LABEL[version.action] || ''}` : ''}</em></div>}
    {version.published && detail !== 'far' && <span className="mq-node__badge" title="Na biblioteca da marca">✓ Marca</span>}
    {status === 'ready' && <img src={version.url} alt={piece.title} loading="lazy" draggable={false} decoding="async"/>}
    {status === 'pending' && <div className="mq-node__wait"><i/><span>{detail === 'far' ? '' : 'Gerando…'}</span></div>}
    {status === 'error' && <div className="mq-node__error" title={version.error}>{detail === 'far' ? '!' : version.error || 'Falhou'}</div>}
  </div>;
}

export const ACTION_LABEL = {create: 'criada', adjust: 'ajuste', variation: 'variação', adapt: 'adaptação'};
