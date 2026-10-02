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

// The session already knows the client, but sending it explicitly keeps two tabs on different clients consistent.
let activeClient = '';
export const setActiveClient = id => {activeClient = id ? String(id) : '';};

export const apiUrl = (path, params = {}) => {
  const query = new URLSearchParams();
  if (activeClient) query.set('client_id', activeClient);
  Object.entries(params).forEach(([key, value]) => {if (value != null && value !== '') query.set(key, String(value));});
  return `/connect/api/v2/reports${path}${query.size ? `?${query}` : ''}`;
};
