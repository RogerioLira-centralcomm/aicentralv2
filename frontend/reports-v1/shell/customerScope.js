import {navigate} from './routes.js';

// The client (advertiser) filter lives in ?customer=, the same key the Clientes e contas page uses.
export const ALL_CUSTOMERS = 'all';
export const NO_CUSTOMER = 'none';

export const readCustomer = () => new URLSearchParams(location.search).get('customer') || ALL_CUSTOMERS;

export function writeCustomer(value) {
  const url = new URL(location.href);
  if (value === ALL_CUSTOMERS || !value) url.searchParams.delete('customer'); else url.searchParams.set('customer', value);
  navigate(`${url.pathname}${url.search}${url.hash}`, {replace: true});
}
