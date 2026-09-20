import React, {useEffect} from 'react';

export function StudioModal({title, children, onClose}) {
  useEffect(() => {
    const close = event => { if (event.key === 'Escape') onClose(); };
    window.addEventListener('keydown', close);
    return () => window.removeEventListener('keydown', close);
  }, [onClose]);
  return <div className="se-modal-backdrop" onMouseDown={event => { if (event.target === event.currentTarget) onClose(); }}><section className="se-modal" role="dialog" aria-modal="true" aria-labelledby="studio-modal-title"><header><h2 id="studio-modal-title">{title}</h2><button type="button" onClick={onClose} aria-label="Fechar">×</button></header>{children}</section></div>;
}
