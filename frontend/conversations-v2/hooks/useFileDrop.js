import {useCallback, useEffect, useRef, useState} from 'react';

function carriesFiles(event) {
  return Array.from(event.dataTransfer?.types || []).includes('Files');
}

export function useFileDrop(onFiles) {
  const [dropActive, setDropActive] = useState(false);
  const dragDepth = useRef(0);

  const closeFileDrop = useCallback(() => {
    dragDepth.current = 0;
    setDropActive(false);
  }, []);

  useEffect(() => {
    window.addEventListener('drop', closeFileDrop, true);
    window.addEventListener('dragend', closeFileDrop, true);
    window.addEventListener('blur', closeFileDrop);
    return () => {
      window.removeEventListener('drop', closeFileDrop, true);
      window.removeEventListener('dragend', closeFileDrop, true);
      window.removeEventListener('blur', closeFileDrop);
    };
  }, [closeFileDrop]);

  const handleDragEnter = useCallback(event => {
    if (!carriesFiles(event)) return;
    event.preventDefault();
    dragDepth.current += 1;
    setDropActive(true);
  }, []);

  const handleDragOver = useCallback(event => {
    if (carriesFiles(event)) event.preventDefault();
  }, []);

  const handleDragLeave = useCallback(event => {
    event.preventDefault();
    dragDepth.current = Math.max(0, dragDepth.current - 1);
    if (!dragDepth.current) setDropActive(false);
  }, []);

  const handleDrop = useCallback(event => {
    event.preventDefault();
    const files = Array.from(event.dataTransfer?.files || []);
    closeFileDrop();
    if (files.length) onFiles(files);
  }, [closeFileDrop, onFiles]);

  return {dropActive, handleDragEnter, handleDragOver, handleDragLeave, handleDrop};
}
