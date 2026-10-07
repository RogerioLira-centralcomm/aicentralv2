import React from 'react';
import {EntityPicker} from './EntityPicker.jsx';
import {ALL_CUSTOMERS, NO_CUSTOMER, readCustomer, writeCustomer} from './customerScope.js';
import {useCustomerLogos} from './useCustomerLogos.js';
import {useReportsContext} from './context.js';

/**
 * Client chooser under the product logo: one styled select whose avatar is the brand logo when there is one.
 * Screens that analyse a single client (`needsCustomer`) have no "all" option; settings and data sources keep it.
 * With several accounts (tenants) a second, smaller select above switches the account.
 */
export function SidebarClient({clients = [], customers = [], client, needsCustomer, collapsed, campaigns = [], accounts = []}) {
  const {switchClient} = useReportsContext();
  const logos = useCustomerLogos(customers.length ? client?.client_id : null);
  const count = (list, id) => list.filter(entry => entry.customer_id === id).length;
  const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;
  const items = customers.filter(item => item.status !== 'archived').map(item => ({id: item.id, name: item.name, logo: logos[String(item.id)],
    meta: `${plural(count(accounts, item.id), 'conta', 'contas')} · ${plural(count(campaigns, item.id), 'campanha', 'campanhas')}`}));
  const requested = readCustomer();
  const value = items.some(item => String(item.id) === requested) ? requested : requested === NO_CUSTOMER && !needsCustomer ? NO_CUSTOMER : needsCustomer && items[0] ? String(items[0].id) : ALL_CUSTOMERS;
  if (!items.length && clients.length < 2) return null;
  return <div className="rs-sidebar-client">
    {clients.length > 1 && !collapsed && <EntityPicker label="Conta" value={client?.client_id ?? ''} items={clients.map(item => ({id: item.id, name: item.name}))} onChange={switchClient} block compact placement="bottom start"/>}
    {items.length > 0 && <EntityPicker label="Cliente" value={value} items={items} onChange={writeCustomer} block compact={collapsed} placement="bottom start"
      {...(needsCustomer ? {} : {allLabel: 'Todos os clientes', allValue: ALL_CUSTOMERS, extra: [{id: NO_CUSTOMER, name: 'Sem cliente'}]})}/>}
  </div>;
}
