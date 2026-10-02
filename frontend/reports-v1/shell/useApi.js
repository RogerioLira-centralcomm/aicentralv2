import {useCallback, useEffect, useRef, useState} from 'react';
import {json} from '../reportsCommon.jsx';

/** GET with independent loading/error, a retry function, and stale responses dropped when the URL changes. */
export function useApi(url) {
  const [state, setState] = useState({loading: Boolean(url), error: '', body: null});
  const [revision, setRevision] = useState(0);
  const request = useRef(0);
  useEffect(() => {
    if (!url) {setState({loading: false, error: '', body: null}); return undefined;}
    const current = ++request.current;
    setState(previous => ({...previous, loading: true, error: ''}));
    json(url).then(body => {if (current === request.current) setState({loading: false, error: '', body});})
      .catch(failure => {if (current === request.current) setState({loading: false, error: failure.message, body: null});});
    return () => {request.current += 1;};
  }, [url, revision]);
  const retry = useCallback(() => setRevision(value => value + 1), []);
  return [state, retry];
}

// The API reads the client from the session. The session is shared by every tab, so a tab that switches client
// tells the others, which reload on the new client instead of reading or writing it while showing the old one.
let activeClient = '';
let clientChannel = null;
try {
  clientChannel = new BroadcastChannel('cadu-reports-client');
  clientChannel.onmessage = event => {if (activeClient && String(event.data) !== activeClient) location.reload();};
} catch {clientChannel = null;}
export const setActiveClient = id => {
  const next = id ? String(id) : '';
  if (next && next !== activeClient) clientChannel?.postMessage(next);
  activeClient = next;
};

export const apiUrl = (path, params = {}) => {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {if (value != null && value !== '') query.set(key, String(value));});
  return `/connect/api/v2/reports${path}${query.size ? `?${query}` : ''}`;
};
