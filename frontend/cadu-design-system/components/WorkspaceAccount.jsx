import React, {useState} from 'react';
import {CaduDock} from './CaduDock';
import {WorkspaceNavbar} from './WorkspaceNavbar';
import {WorkspaceAccountMenu} from './WorkspaceFeedback';
import {workspaceSolutionItems} from '../workspaceSolutions';

const labels = {perfil: 'Perfil', equipe: 'Equipe', planos: 'Plano', creditos: 'Uso', faturamento: 'Faturamento'};
const descriptions = {perfil: 'Como você aparece para o time.', equipe: 'Quem move a operação da agência.', planos: 'Capacidade para o ritmo da agência.', creditos: 'O que a equipe consumiu.', faturamento: 'Histórico financeiro da operação.'};
const number = value => new Intl.NumberFormat('pt-BR').format(Number(value) || 0);
const money = value => new Intl.NumberFormat('pt-BR', {style: 'currency', currency: 'BRL'}).format(Number(value) || 0);
const parseDate = value => {
  if (!value) return '—';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
};
const civilDate = value => {
  const parsed = parseDate(value);
  return parsed ? new Intl.DateTimeFormat('pt-BR', {timeZone: 'UTC'}).format(parsed) : value ? String(value) : '—';
};
const dateTime = value => {
  const parsed = parseDate(value);
  return parsed ? new Intl.DateTimeFormat('pt-BR', {dateStyle: 'short', timeStyle: 'short'}).format(parsed) : value ? String(value) : '—';
};
const eventTypes = {invite: 'Convite', welcome: 'Boas-vindas', launch_bonus: 'Bônus inicial', password_reset: 'Redefinição', password_changed: 'Senha alterada'};
const deliveryStatuses = {sent: 'Enviado', delivered: 'Entregue', opened: 'Aberto', clicked: 'Clicado', deferred: 'Adiado', failed: 'Falhou'};
const invoiceStatuses = {paid: 'Paga', overdue: 'Em atraso', pending: 'Pendente'};

function Hidden({name, value}) { return <input type="hidden" name={name} value={value || ''}/>; }
function Metric({label, value, detail, children}) { return <article><span>{label}</span><strong>{value}</strong>{detail && <p>{detail}</p>}{children}</article>; }
function DataTable({columns, rows, empty = 'Nenhum registro disponível.'}) {
  return <div className="cadu-ds-account-table"><table><thead><tr>{columns.map(column => <th key={column}>{column}</th>)}</tr></thead><tbody>{rows.length ? rows : <tr><td colSpan={columns.length}>{empty}</td></tr>}</tbody></table></div>;
}

function Profile({bootstrap}) {
  const account = bootstrap.account;
  const person = account.current_user || {};
  return <div className="cadu-ds-account-stack">
    <section className="cadu-ds-account-lead"><div><span>Seu lugar na operação</span><h2>Perfil de {person.nome_completo || bootstrap.user.name}</h2><p>Esses dados identificam você em conversas, decisões e convites.</p></div></section>
    <form className="cadu-ds-account-form" method="post" action={bootstrap.endpoints.updateProfile}><Hidden name="_csrf" value={bootstrap.csrf}/><Hidden name="avatar_badge" value={person.cadu_avatar_badge || bootstrap.user.avatarBadge}/><label>Nome completo<input name="name" defaultValue={person.nome_completo || bootstrap.user.name} required/></label><label>E-mail<input defaultValue={person.email || bootstrap.user.email} disabled/></label><label>Telefone<input name="phone" defaultValue={person.telefone || ''}/></label><footer><span>Seu e-mail é gerenciado pela identidade de acesso.</span><button>Salvar perfil</button></footer></form>
    <section className="cadu-ds-account-section"><header><div><span>Comunicação da conta</span><h2>E-mails disparados por página</h2></div><small>{account.email_catalog?.length || 0} modelos ativos</small></header><DataTable columns={['Página', 'Ação', 'Destinatário', 'Assunto', 'Disparo']} rows={(account.email_catalog || []).map((email, index) => <tr key={email.template || index}><td><b>{email.page}</b></td><td>{email.action}</td><td>{email.recipient}</td><td>{email.subject}<small>{email.template}</small></td><td>{email.timing}</td></tr>)}/></section>
    <section className="cadu-ds-account-section"><header><div><span>Histórico de envio</span><h2>E-mails da equipe</h2></div><small>{account.email_events?.length || 0} registros</small></header><DataTable columns={['Atualização', 'Destinatário', 'Tipo', 'Assunto', 'Status']} empty="Os próximos envios da conta aparecerão aqui." rows={(account.email_events || []).map((event, index) => <tr key={event.id || index}><td>{dateTime(event.last_event_at || event.created_at)}</td><td>{event.recipient_email}</td><td>{eventTypes[event.event_type] || event.event_type}</td><td>{event.subject}</td><td><b>{deliveryStatuses[event.status] || event.status}</b></td></tr>)}/></section>
  </div>;
}

function Team({bootstrap}) {
  const {account, endpoints, csrf, admin} = bootstrap;
  const org = account.organization || {};
  const pendingInvites = (account.invites || []).filter(item => item.status === 'pending');
  const confirmAction = event => { if (!window.confirm('Confirma esta alteração de acesso?')) event.preventDefault(); };
  return <div className="cadu-ds-account-stack">
    {admin && <section className="cadu-ds-account-section"><header><div><span>Nova pessoa</span><h2>Convidar para a equipe</h2></div></header><form className="cadu-ds-account-inline-form" method="post" action={endpoints.invite}><Hidden name="_csrf" value={csrf}/><label>E-mail<input type="email" name="email" required/></label><label>Acesso<select name="role"><option value="member">Membro</option><option value="admin">Administrador</option></select></label><button>Enviar convite</button></form></section>}
    {admin && <section className="cadu-ds-account-section"><header><div><span>Dados da equipe</span><h2>Base da agência</h2></div></header><form className="cadu-ds-account-form" method="post" action={endpoints.updateOrganization}><Hidden name="_csrf" value={csrf}/><label>Nome da equipe<input name="trade_name" defaultValue={org.nome_fantasia || ''} required/></label><label>Razão social<input name="legal_name" defaultValue={org.razao_social || ''}/></label><label>CPF ou CNPJ<input name="document" defaultValue={org.cnpj || ''}/></label><label>CEP<input name="postal_code" defaultValue={org.cep || ''}/></label><label>Logradouro<input name="street" defaultValue={org.logradouro || ''}/></label><label>Número<input name="number" defaultValue={org.numero || ''}/></label><label>Complemento<input name="complement" defaultValue={org.complemento || ''}/></label><label>Bairro<input name="district" defaultValue={org.bairro || ''}/></label><label>Cidade<input name="city" defaultValue={org.cidade || ''}/></label><label>Estado<select name="state" defaultValue={org.estado_sigla || ''}><option value="">Não informado</option>{(account.states || []).map(state => <option key={state.sigla} value={state.sigla}>{state.sigla} — {state.descricao}</option>)}</select></label><footer><span>Registro canônico usado em projetos, plano e faturamento.</span><button>Salvar dados</button></footer></form></section>}
    <section className="cadu-ds-account-section"><header><div><span>Núcleo da agência</span><h2>Pessoas da equipe</h2></div><small>{account.people?.length || 0} pessoas</small></header><p className="cadu-ds-account-section-copy">Projetos, marcas, plano e créditos são compartilhados por esta equipe.</p><div className="cadu-ds-account-list">{(account.people || []).length ? account.people.map(person => <article key={person.id_contato_cliente}><i>{(person.nome_completo || '?').slice(0, 1).toUpperCase()}</i><div><b>{person.nome_completo}</b><small>{person.email} · {person.cargo || person.setor || 'Equipe da agência'}</small></div><em>{person.status ? 'Ativo' : 'Inativo'}</em>{admin && String(person.id_contato_cliente) !== String(bootstrap.user.id) && <div className="cadu-ds-account-row-actions"><form method="post" action={`${endpoints.memberBase}/${person.id_contato_cliente}/papel`}><Hidden name="_csrf" value={csrf}/><select name="role" defaultValue={['admin', 'superadmin'].includes(person.user_type) ? 'admin' : person.user_type || 'client'}><option value="client">Membro</option><option value="admin">Administrador</option><option value="readonly">Somente leitura</option></select><button>Salvar</button></form><form method="post" action={`${endpoints.memberBase}/${person.id_contato_cliente}/status`} onSubmit={confirmAction}><Hidden name="_csrf" value={csrf}/><button className="is-danger">{person.status ? 'Desativar' : 'Reativar'}</button></form></div>}</article>) : <p className="cadu-ds-account-empty">Convide a primeira pessoa para começar a trabalhar em conjunto.</p>}</div></section>
    <section className="cadu-ds-account-section"><header><div><span>Acesso pendente</span><h2>Convites em aberto</h2></div></header><div className="cadu-ds-account-list">{pendingInvites.length ? pendingInvites.map(invite => <article key={invite.id}><i>@</i><div><b>{invite.email}</b><small>{invite.role === 'admin' ? 'Administrador' : 'Membro'} · expira {civilDate(invite.expires_at)}</small></div><em>Pendente</em>{admin && <div className="cadu-ds-account-row-actions"><form method="post" action={`${endpoints.inviteBase}/${invite.id}/reenviar`}><Hidden name="_csrf" value={csrf}/><button>Reenviar</button></form><form method="post" action={`${endpoints.inviteBase}/${invite.id}/cancelar`} onSubmit={confirmAction}><Hidden name="_csrf" value={csrf}/><button className="is-danger">Cancelar</button></form></div>}</article>) : <p className="cadu-ds-account-empty">Nenhum convite pendente.</p>}</div></section>
  </div>;
}

function Plan({account, urls}) {
  const insight = account.insights || {};
  return <div className="cadu-ds-account-stack"><section className="cadu-ds-account-story"><span>Capacidade compartilhada</span><h2>{account.plan?.plan_definition_name || account.plan?.plan_type || 'Plano não configurado'}</h2><p>Uma leitura prática da capacidade disponível para a equipe continuar nos projetos.</p></section><section className="cadu-ds-account-metrics"><Metric label="Tokens neste ciclo" value={`${number(insight.tokens?.used)} de ${number(insight.tokens?.limit)}`}><progress value={insight.tokens?.percentage || 0} max="100"/><a href={urls.usage}>Ver uso</a></Metric><Metric label="Pessoas ativas" value={number(insight.users?.used)} detail={`${number(insight.users?.available)} acessos disponíveis`}><a href={urls.team}>Gerenciar equipe</a></Metric><Metric label="Vigência" value={insight.validity?.end || '—'} detail="Consulte o atendimento para mudanças contratuais."/></section></div>;
}

function Usage({account}) {
  const available = account.credit?.available ?? account.position?.available ?? 0;
  return <div className="cadu-ds-account-stack"><section className="cadu-ds-account-story"><span>Saldo compartilhado</span><h2>{number(available)} créditos disponíveis</h2><p>Saldo consultado antes de cada execução e debitado quando a ferramenta conclui o trabalho.</p></section><section className="cadu-ds-account-metrics"><Metric label="Lotes ativos" value={number(account.purchases?.length)}/><Metric label="Execuções recentes" value={number(account.movements?.length)} detail={`últimas ${number(account.movements?.length)} execuções confirmadas`}/><Metric label="Consumo confirmado" value={number((account.movements || []).reduce((total, item) => total + Number(item.amount || 0), 0))}/></section><section className="cadu-ds-account-section"><header><div><span>Consumo confirmado</span><h2>Atividade recente da equipe</h2></div></header><DataTable columns={['Execução', 'Data', 'Referência', 'Créditos']} empty="Quando a equipe usar uma ferramenta Cadu, o consumo confirmado aparecerá aqui." rows={(account.movements || []).map((item, index) => <tr key={item.id || index}><td><b>{item.reason || 'Execução Cadu'}</b></td><td>{dateTime(item.created_at)}</td><td>{item.reference || '—'}</td><td>−{number(item.amount)}</td></tr>)}/></section><section className="cadu-ds-account-section"><header><div><span>Saldo por lote</span><h2>Créditos disponíveis</h2></div></header><DataTable columns={['Pacote', 'Vencimento', 'Disponível', 'Total']} empty="Não há lotes ativos no momento." rows={(account.purchases || []).map((lot, index) => <tr key={lot.id || index}><td><b>{lot.package_name}</b></td><td>{lot.expires_at ? civilDate(lot.expires_at) : 'Sem vencimento'}</td><td>{number(lot.available)}</td><td>{number(lot.credits)}</td></tr>)}/></section></div>;
}

function Billing({account}) {
  const summary = account.summary || {};
  return <div className="cadu-ds-account-stack"><section className="cadu-ds-account-metrics"><Metric label="Em aberto" value={money(summary.open_total)} detail={`${number(summary.open_count)} faturas`}/><Metric label="Pagas" value={number(summary.paid_count)} detail="no histórico disponível"/><Metric label="Em atraso" value={number(summary.overdue_count)} detail={summary.overdue_count ? 'Requer atenção' : 'Nenhuma pendência vencida'}/></section><section className="cadu-ds-account-section"><header><div><span>Financeiro</span><h2>Histórico de faturas</h2></div></header><DataTable columns={['Fatura', 'Referência', 'Vencimento', 'Status', 'Valor', 'Documento']} empty="Quando houver cobrança registrada, ela aparecerá aqui." rows={(account.invoices || []).map((invoice, index) => <tr key={invoice.id || index}><td><b>{invoice.number}</b></td><td>{invoice.reference || '—'}</td><td>{civilDate(invoice.due_date)}</td><td>{invoiceStatuses[invoice.status_normalized] || invoice.status_normalized}</td><td>{money(invoice.total)}</td><td>{invoice.pdf_safe_url ? <a href={invoice.pdf_safe_url} target="_blank" rel="noreferrer">Abrir PDF</a> : '—'}</td></tr>)}/></section></div>;
}

export function WorkspaceAccount({bootstrap}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const section = bootstrap.section;
  const solutions = workspaceSolutionItems(bootstrap);
  const navigation = Object.entries(labels).map(([id, title]) => ({id, kind: 'account', title, href: bootstrap.urls[id], active: id === section}));
  const org = bootstrap.account.organization || {};
  const content = section === 'perfil' ? <Profile bootstrap={bootstrap}/> : section === 'equipe' ? <Team bootstrap={bootstrap}/> : section === 'planos' ? <Plan account={bootstrap.account} urls={bootstrap.urls}/> : section === 'creditos' ? <Usage account={bootstrap.account}/> : <Billing account={bootstrap.account}/>;
  return <div className="cadu-ds-home-shell cadu-ds-account-shell"><main className="cadu-ds-home-main"><WorkspaceNavbar logo={bootstrap.caduMark} solutions={solutions} user={bootstrap.user} onOpenAccount={() => setMenuOpen(true)}><strong>Conta</strong><span aria-hidden="true">/</span><b>{labels[section]}</b></WorkspaceNavbar><div className="cadu-ds-home-workarea"><CaduDock shortcutItems={navigation} usagePercent={bootstrap.usagePercent} userAvatar={bootstrap.user.avatar} userInitials={bootstrap.user.name?.slice(0, 2).toUpperCase()} onNewConversation={() => window.location.assign(bootstrap.urls.newConversation)} onOpenResource={item => window.location.assign(item.href)} onOpenUsage={() => setMenuOpen(true)}/><section className="cadu-ds-account-content"><header className="cadu-ds-account-hero"><div><p>Conta da agência</p><h1>{org.nome_fantasia || 'Sua equipe'}</h1><span>{descriptions[section]}</span></div><dl><div><dt>Pessoas</dt><dd>{number(bootstrap.account.people?.length)}</dd></div><div><dt>Plano</dt><dd>{bootstrap.account.plan?.plan_definition_name || bootstrap.account.plan?.plan_type || '—'}</dd></div><div><dt>Saldo</dt><dd>{number(bootstrap.account.position?.available)}</dd></div></dl></header><nav className="cadu-ds-account-tabs" aria-label="Conta">{Object.entries(labels).map(([id, label]) => <a key={id} href={bootstrap.urls[id]} aria-current={id === section ? 'page' : undefined}>{label}</a>)}</nav>{content}</section></div></main><WorkspaceAccountMenu open={menuOpen} onClose={() => setMenuOpen(false)} user={bootstrap.user} links={bootstrap.urls} onManageShortcuts={() => window.location.assign(`${bootstrap.urls.home}#atalhos`)}/></div>;
}
