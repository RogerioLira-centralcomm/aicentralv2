import {useCallback, useEffect, useState} from 'react';
import {ARTIFACT_SIDE_COOKIE, artifactKey, readCookie, writeCookie} from '../lib/browser.mjs';

export function useArtifactWorkspace(artifact) {
  const [artifactTabs, setArtifactTabs] = useState([]);
  const [artifactSide, setArtifactSide] = useState(() => readCookie(ARTIFACT_SIDE_COOKIE) === 'left' ? 'left' : 'right');

  useEffect(() => {
    if (!artifact?.id) return;
    const saved = readCookie(`${ARTIFACT_SIDE_COOKIE}:${artifact.id}`) || readCookie(ARTIFACT_SIDE_COOKIE);
    setArtifactSide(saved === 'left' ? 'left' : 'right');
  }, [artifact?.id]);

  useEffect(() => {
    const key = artifactKey(artifact);
    if (!key) return;
    setArtifactTabs(items => {
      const existing = items.findIndex(item => artifactKey(item) === key);
      return existing >= 0
        ? items.map((item, index) => index === existing ? artifact : item)
        : [...items, artifact];
    });
  }, [artifact]);

  const changeArtifactSide = useCallback(side => {
    const next = side === 'left' ? 'left' : 'right';
    setArtifactSide(next);
    writeCookie(ARTIFACT_SIDE_COOKIE, next);
    if (artifact?.id) writeCookie(`${ARTIFACT_SIDE_COOKIE}:${artifact.id}`, next);
  }, [artifact?.id]);

  return {artifactTabs, setArtifactTabs, artifactSide, changeArtifactSide};
}
