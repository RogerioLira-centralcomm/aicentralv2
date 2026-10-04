import {apiUrl, useApi} from './useApi.js';

/** Logo of each customer (advertiser) that has a Workspace brand linked: {customerId: url}. Empty while loading or when the Workspace is not connected. */
export function useCustomerLogos(clientId) {
  const [state] = useApi(clientId ? apiUrl('/workspace/map') : null);
  const map = state.body?.available ? state.body : null;
  const logos = {};
  Object.entries(map?.customer_brands || {}).forEach(([id, linked]) => {
    const brand = linked.map(link => map.brands.find(item => item.ref === link.ref)).find(item => item?.logo_url);
    if (brand) logos[id] = brand.logo_url;
  });
  return logos;
}
