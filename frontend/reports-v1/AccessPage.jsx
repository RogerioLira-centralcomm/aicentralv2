import React, {useEffect, useState} from 'react';
import {Plus, SearchLg} from '@untitledui/icons';
import {Button} from '../cadu-design-system/untitled-kit/button.tsx';
import {Badge} from '../cadu-design-system/untitled-kit/badges.tsx';
import {ReportsDrawer} from './ReportsDrawer.jsx';
import {ReportsFieldInput} from './ReportsFieldInput.jsx';
import {ReportsNativeSelect} from './ReportsNativeSelect.jsx';
import {ReportsConfirmDialog} from './ReportsConfirmDialog.jsx';
import {Alert, Card, DrawerActions, EmptyNote, TD, TH} from './ReportsBlocks.jsx';
import {json} from './reportsCommon.jsx';

const ROLES = {
  viewer: ['Visualização', 'Consulta relatórios, fluxos e dados, sem alterar nada.', 'gray'],
  member: ['Operação', 'Cadastra contas e campanhas, importa arquivos e edita fluxos.', 'brand'],
  admin: ['Administração de dados', 'Tudo da operação, mais clientes e acessos.', 'purple'],
};
const initials = name => String(name || '?').split(/\s+/).filter(Boolean).slice(0, 2).map(part => part[0]).join('').toUpperCase();

/** Who can see and operate this client's Reports data. */
export function AccessPage({data, save, busy}) {
  const [users, setUsers] = useState([]);
  const [open, setOpen] = useState(false);
  const [revokeUser, setRevokeUser] = useState(null);
  const [userId, setUserId] = useState('');
  const [role, setRole] = useState('viewer');
  const [exclusive, setExclusive] = useState(false);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const reload = () => json(`/connect/api/v2/reports/access`).then(value => setUsers(value.users || []));
  useEffect(() => {reload().catch(failure => setError(failure.message));}, [data.client.client_id]);
  const start = (user = null) => {
    setError(''); setUserId(user ? String(user.id) : ''); setRole(user?.role && !user.revoked_at ? user.role : 'viewer'); setExclusive(Boolean(user?.reports_only)); setOpen(true);
  };
  const choose = value => {
    const selected = users.find(item => String(item.id) === value);
    setUserId(value); setRole(selected?.role && !selected.revoked_at ? selected.role : 'viewer'); setExclusive(Boolean(selected?.reports_only));
  };
  const grant = async event => {
    event.preventDefault();
    try {await save('/access', {user_id: Number(userId), role, exclusive}, false); await reload(); setError(''); setOpen(false);}
    catch (failure) {setError(failure.message);}
  };
  const revoke = async user => {
    try {await save(`/access/${user.id}/revoke`, {}, false); await reload(); setError(''); setRevokeUser(null);}
    catch (failure) {setError(failure.message);}
  };
  const active = users.filter(user => user.role && !user.revoked_at);
  const needle = query.trim().toLocaleLowerCase('pt-BR');
  const visible = active.filter(user => `${user.name} ${user.email || ''}`.toLocaleLowerCase('pt-BR').includes(needle));
  const editing = users.find(item => String(item.id) === userId);

  return <div className="untitled-scope flex flex-col gap-6">
    {error && !open && <Alert>{error}</Alert>}
    <Card flush title="Pessoas com acesso" badge={<Badge type="pill-color" size="sm" color="gray">{active.length}</Badge>}
      description="Acesso à conta principal do Reports deste cliente. Compartilhamentos de um site ou fluxo são feitos no próprio recurso."
      actions={<Button size="md" color="primary" iconLeading={Plus} onPress={() => start()}>Conceder acesso</Button>}>
      {active.length > 8 && <div className="border-b border-secondary px-6 py-3"><div className="max-w-80"><ReportsFieldInput size="sm" type="search" aria-label="Buscar pessoa" placeholder="Nome ou e-mail" value={query} onChange={event => setQuery(event.target.value)}
        leading={<SearchLg size={16} aria-hidden="true" className="ml-3 shrink-0 text-fg-quaternary"/>}/></div></div>}
      {visible.length ? <div className="overflow-x-auto"><table className="w-full min-w-[680px]">
        <thead><tr><th className={TH}>Pessoa</th><th className={TH}>Papel</th><th className={TH}>Alcance</th><th className={TH}><span className="sr-only">Ações</span></th></tr></thead>
        <tbody>{visible.map(user => {
          const [label, , color] = ROLES[user.role] || [user.role, '', 'gray'];
          return <tr key={user.id} className="hover:bg-primary_hover">
            <td className={TD}><div className="flex items-center gap-3">
              <span aria-hidden="true" className="flex size-9 shrink-0 items-center justify-center rounded-full bg-tertiary text-xs font-semibold text-tertiary">{initials(user.name)}</span>
              <div className="min-w-0"><p className="truncate font-medium text-primary">{user.name}</p><p className="truncate text-xs text-tertiary">{user.email}</p></div>
            </div></td>
            <td className={TD}><Badge type="pill-color" size="sm" color={color}>{label}</Badge></td>
            <td className={TD}>{user.access_scope === 'shared' ? 'Recursos compartilhados' : 'Conta principal'}{user.reports_only && <p className="text-xs text-tertiary">Somente Reports</p>}</td>
            <td className={`${TD} text-right whitespace-nowrap`}>
              <Button size="sm" color="link-gray" onPress={() => start(user)}>Alterar papel</Button>
              <span className="mx-3 text-quaternary" aria-hidden="true">·</span>
              <Button size="sm" color="link-destructive" isDisabled={busy} onPress={() => setRevokeUser(user)}>Revogar</Button>
            </td>
          </tr>;
        })}</tbody>
      </table></div> : <EmptyNote title={active.length ? 'Ninguém corresponde à busca' : 'Nenhum acesso concedido'}>{active.length ? 'Tente outro nome ou e-mail.' : 'Conceda acesso para alguém consultar ou operar os dados deste cliente.'}</EmptyNote>}
    </Card>

    <ReportsDrawer open={open} onOpenChange={setOpen} onDiscard={() => {setUserId(''); setRole('viewer'); setExclusive(false); setError('');}}
      title={editing?.role && !editing.revoked_at ? 'Alterar papel' : 'Conceder acesso'} context={data.client.client_name} description="O papel vale para todos os dados deste cliente no Reports.">
      <form className="untitled-scope flex flex-col gap-6" onSubmit={grant}>
        {error && <Alert>{error}</Alert>}
        <ReportsNativeSelect label="Pessoa" required value={userId} onChange={event => choose(event.target.value)}>
          <option value="">Selecione</option>{users.map(user => <option key={user.id} value={user.id}>{user.name} · {user.email}</option>)}
        </ReportsNativeSelect>
        <fieldset className="flex flex-col gap-2">
          <legend className="mb-2 text-sm font-medium text-secondary">Papel</legend>
          {Object.entries(ROLES).map(([value, [label, description]]) => <label key={value} className={`flex cursor-pointer items-start gap-3 rounded-lg p-4 ring-inset ${role === value ? 'bg-brand-primary ring-2 ring-brand' : 'ring-1 ring-secondary hover:bg-primary_hover'}`}>
            <input type="radio" name="role" className="mt-0.5 size-4 accent-brand-600" checked={role === value} onChange={() => setRole(value)}/>
            <span><span className="block text-sm font-semibold text-primary">{label}</span><span className="block text-sm text-tertiary">{description}</span></span>
          </label>)}
        </fieldset>
        <DrawerActions onCancel={() => setOpen(false)} busy={busy} label="Salvar acesso" disabled={!userId}/>
      </form>
    </ReportsDrawer>
    <ReportsConfirmDialog open={Boolean(revokeUser)} title="Revogar acesso" description={revokeUser ? `Remover o acesso de ${revokeUser.name} a este cliente no Reports?` : ''} confirmLabel="Revogar acesso" busy={busy} onCancel={() => setRevokeUser(null)} onConfirm={() => revoke(revokeUser)}/>
  </div>;
}
