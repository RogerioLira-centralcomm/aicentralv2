import React from 'react';

const W = 200, H = 130;

/** Minimapa: peças como blocos e o retângulo da visão atual; clicar leva a câmera até o ponto. */
export function Minimap({scene, camera, viewport, onJump}) {
  const box = scene.bounds;
  const scale = Math.min(W / Math.max(box.w, 1), H / Math.max(box.h, 1)) * 0.9;
  const ox = (W - box.w * scale) / 2 - box.x * scale, oy = (H - box.h * scale) / 2 - box.y * scale;
  const view = {x: -camera.x / camera.z, y: -camera.y / camera.z, w: viewport.w / camera.z, h: viewport.h / camera.z};
  const jump = event => {
    const rect = event.currentTarget.getBoundingClientRect();
    onJump((event.clientX - rect.left - ox) / scale, (event.clientY - rect.top - oy) / scale);
  };
  return <svg className="mq-minimap" width={W} height={H} onPointerDown={jump} role="img" aria-label="Minimapa da mesa">
    {scene.bands.map(band => <rect key={band.series.id} x={ox + band.x * scale} y={oy + band.y * scale} width={band.w * scale} height={band.h * scale} className="mq-minimap__band"/>)}
    {scene.nodes.map(node => <rect key={node.id} x={ox + node.x * scale} y={oy + node.y * scale} width={Math.max(1.5, node.w * scale)} height={Math.max(1.5, node.h * scale)} className={node.star ? 'mq-minimap__star' : 'mq-minimap__node'}/>)}
    <rect x={ox + view.x * scale} y={oy + view.y * scale} width={view.w * scale} height={view.h * scale} className="mq-minimap__view"/>
  </svg>;
}
