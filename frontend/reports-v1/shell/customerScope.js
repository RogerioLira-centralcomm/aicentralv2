import {navigate} from './routes.js';

// The client (advertiser) filter lives in ?customer=, the same key the Clientes e contas page uses.
export const ALL_CUSTOMERS = 'all';
export const NO_CUSTOMER = 'none';

export const readCustomer = () => new URLSearchParams(location.search).get('customer') || ALL_CUSTOMERS;

export function writeCustomer(value) {
  if (value && value !== ALL_CUSTOMERS && value !== NO_CUSTOMER) saveCustomer(value);
  const url = new URL(location.href);
  if (value === ALL_CUSTOMERS || !value) url.searchParams.delete('customer'); else url.searchParams.set('customer', value);
  navigate(`${url.pathname}${url.search}${url.hash}`, {replace: true});
}

const SAVED_KEY = 'reports-customer';
export const readSavedCustomer = () => {try {return localStorage.getItem(SAVED_KEY) || '';} catch {return '';}};
export const saveCustomer = value => {try {localStorage.setItem(SAVED_KEY, value);} catch {/* preference is optional */}};

/** Query string that keeps the chosen client when moving between pages ('' when viewing all). */
export const customerSearch = () => {const value = readCustomer(); return value === ALL_CUSTOMERS ? '' : `?customer=${encodeURIComponent(value)}`;};

/** The chosen client's id for API calls ('' when viewing all or "sem cliente": the API only narrows to a real client). */
export const customerParam = () => {const value = readCustomer(); return /^\d+$/.test(value) ? value : '';};

/** Key under which a client's choices (source, campaign, site) are remembered: one memory per advertiser. */
export const scopeMemoryKey = clientId => `${clientId}:${customerParam() || 'all'}`;
