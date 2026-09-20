import React, {useState} from 'react';
import {CaduDock} from './CaduDock';
import {WorkspaceAccountMenu} from './WorkspaceFeedback';
import {WorkspaceContextSidebar} from './WorkspaceContextSidebar';
import {VisualIdentity} from './VisualIdentity';
import {openWorkspaceDetail} from '../workspaceNavigation';

const labels = {agencia: 'Agência', equipe: 'Equipe', faturamento: 'Faturamento', integracoes: 'Integrações', planos: 'Plano', perfil: 'Perfil', uso: 'Uso', creditos: 'Créditos'};
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

function Agency({bootstrap}) {
  const {account, endpoints, csrf, admin, urls} = bootstrap;
  const org = account.organization || {};
  const context = account.agency_context || {};
  const projects = context.projects || [];
  const brands = context.brands || [];
  return <div className="cadu-ds-account-stack">
    <section className="cadu-ds-account-lead"><div><span>Contexto compartilhado</span><h2>O trabalho da agência</h2><p>Projetos, marcas e pessoas conectadas em um mesmo espaço de trabalho.</p></div></section>
    {admin ? <form className="cadu-ds-account-form" method="post" action={endpoints.updateOrganization}><Hidden name="_csrf" value={csrf}/><label>Nome da agência<input name="trade_name" defaultValue={org.nome_fantasia || ''} required/></label><label>Razão social<input name="legal_name" defaultValue={org.razao_social || ''}/></label><label>CPF ou CNPJ<input name="document" defaultValue={org.cnpj || ''}/></label><label>CEP<input name="postal_code" defaultValue={org.cep || ''}/></label><label>Logradouro<input name="street" defaultValue={org.logradouro || ''}/></label><label>Número<input name="number" defaultValue={org.numero || ''}/></label><label>Complemento<input name="complement" defaultValue={org.complemento || ''}/></label><label>Bairro<input name="district" defaultValue={org.bairro || ''}/></label><label>Cidade<input name="city" defaultValue={org.cidade || ''}/></label><label>Estado<select name="state" defaultValue={org.estado_sigla || ''}><option value="">Não informado</option>{(account.states || []).map(state => <option key={state.sigla} value={state.sigla}>{state.sigla} — {state.descricao}</option>)}</select></label><footer><span>Esse nome aparece no Workspace e nos contextos da equipe.</span><button>Salvar dados da agência</button></footer></form> : <section className="cadu-ds-account-section"><header><div><span>Identidade da agência</span><h2>{org.nome_fantasia || 'Sua equipe'}</h2></div></header><p className="cadu-ds-account-section-copy">Somente administradores podem alterar os dados da agência. Fale com uma pessoa administradora se precisar ajustar o nome.</p></section>}
    <section className="cadu-ds-account-metrics"><Metric label="Pessoas" value={number(account.people?.length)} detail="com acesso a esta agência"><a href={urls.team}>Gerenciar equipe</a></Metric><Metric label="Projetos" value={number(projects.length)} detail="contextos ativos"><a href={urls.projects}>Ver projetos</a></Metric><Metric label="Marcas" value={number(brands.length)} detail="identidades disponíveis"><a href={urls.brands}>Ver marcas</a></Metric></section>
    <section className="cadu-ds-account-section"><header><div><span>Contextos de trabalho</span><h2>Projetos da agência</h2></div><a href={urls.projects}>Ver todos</a></header><div className="cadu-ds-account-list">{projects.length ? projects.slice(0, 6).map(project => <a href={project.href} key={project.id}><VisualIdentity initials={project.name} label={project.name} color="#176b5e"/><div><b>{project.name}</b><small>{project.brandName || 'Sem marca'} · {number(project.sources)} fontes</small></div><em>{project.status === 'arquivado' ? 'Arquivado' : 'Ativo'}</em></a>) : <p className="cadu-ds-account-empty">Crie o primeiro projeto para formar o contexto da agência.</p>}</div></section>
    <section className="cadu-ds-account-section"><header><div><span>Núcleo da agência</span><h2>Pessoas e marcas</h2></div><a href={urls.team}>Ver equipe</a></header><div className="cadu-ds-account-list">{(account.people || []).slice(0, 5).map(person => <article key={person.id_contato_cliente}><i>{(person.nome_completo || '?').slice(0, 1).toUpperCase()}</i><div><b>{person.nome_completo}</b><small>{person.email} · {person.cargo || person.setor || 'Equipe da agência'}</small></div><em>{person.status ? 'Ativo' : 'Inativo'}</em></article>)}{!account.people?.length && <p className="cadu-ds-account-empty">Convide pessoas para trabalhar nos mesmos contextos.</p>}</div>{brands.length > 0 && <p className="cadu-ds-account-section-copy">{brands.slice(0, 5).map(item => item.name).join(' · ')}{brands.length > 5 ? ' · …' : ''}</p>}</section>
  </div>;
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
  const pendingInvites = (account.invites || []).filter(item => item.status === 'pending');
  const confirmAction = event => { if (!window.confirm('Confirma esta alteração de acesso?')) event.preventDefault(); };
  return <div className="cadu-ds-account-stack">
    {admin && <section className="cadu-ds-account-section"><header><div><span>Nova pessoa</span><h2>Convidar para a equipe</h2></div></header><form className="cadu-ds-account-inline-form" method="post" action={endpoints.invite}><Hidden name="_csrf" value={csrf}/><label>E-mail<input type="email" name="email" required/></label><label>Acesso<select name="role"><option value="member">Membro</option><option value="admin">Administrador</option></select></label><button>Enviar convite</button></form></section>}
    <section className="cadu-ds-account-section"><header><div><span>Núcleo da agência</span><h2>Pessoas da equipe</h2></div><small>{account.people?.length || 0} pessoas</small></header><p className="cadu-ds-account-section-copy">Projetos, marcas, plano e créditos são compartilhados por esta equipe.</p><div className="cadu-ds-account-list">{(account.people || []).length ? account.people.map(person => <article key={person.id_contato_cliente}><i>{(person.nome_completo || '?').slice(0, 1).toUpperCase()}</i><div><b>{person.nome_completo}</b><small>{person.email} · {person.cargo || person.setor || 'Equipe da agência'}</small></div><em>{person.status ? 'Ativo' : 'Inativo'}</em>{admin && String(person.id_contato_cliente) !== String(bootstrap.user.id) && <div className="cadu-ds-account-row-actions"><form method="post" action={`${endpoints.memberBase}/${person.id_contato_cliente}/papel`}><Hidden name="_csrf" value={csrf}/><select name="role" defaultValue={['admin', 'superadmin'].includes(person.user_type) ? 'admin' : person.user_type || 'client'}><option value="client">Membro</option><option value="admin">Administrador</option><option value="readonly">Somente leitura</option></select><button>Salvar</button></form><form method="post" action={`${endpoints.memberBase}/${person.id_contato_cliente}/status`} onSubmit={confirmAction}><Hidden name="_csrf" value={csrf}/><button className="is-danger">{person.status ? 'Desativar' : 'Reativar'}</button></form></div>}</article>) : <p className="cadu-ds-account-empty">Convide a primeira pessoa para começar a trabalhar em conjunto.</p>}</div></section>
    <section className="cadu-ds-account-section"><header><div><span>Acesso pendente</span><h2>Convites em aberto</h2></div></header><div className="cadu-ds-account-list">{pendingInvites.length ? pendingInvites.map(invite => <article key={invite.id}><i>@</i><div><b>{invite.email}</b><small>{invite.role === 'admin' ? 'Administrador' : 'Membro'} · expira {civilDate(invite.expires_at)}</small></div><em>Pendente</em>{admin && <div className="cadu-ds-account-row-actions"><form method="post" action={`${endpoints.inviteBase}/${invite.id}/reenviar`}><Hidden name="_csrf" value={csrf}/><button>Reenviar</button></form><form method="post" action={`${endpoints.inviteBase}/${invite.id}/cancelar`} onSubmit={confirmAction}><Hidden name="_csrf" value={csrf}/><button className="is-danger">Cancelar</button></form></div>}</article>) : <p className="cadu-ds-account-empty">Nenhum convite pendente.</p>}</div></section>
  </div>;
}

function Plan({account, urls}) {
  const insight = account.insights || {};
  const currentPlan = account.plan?.plan_definition_name || account.plan?.plan_type || 'Plano atual';
  const options = account.plan_options || [];
  const cards = options.length ? options : [{plan_name: currentPlan, max_users: insight.users?.available || insight.users?.used, tokens_monthly_limit: insight.tokens?.limit, is_current: true}];
  return <div className="cadu-ds-account-stack"><section className="cadu-ds-account-story"><span>Plano da agência</span><h2>Escolha o ritmo que sua operação precisa</h2><p>Compare capacidade, equipe e suporte para decidir o próximo passo. O plano atual aparece destacado.</p></section><section className="cadu-ds-plan-current"><div><span>Plano atual</span><strong>{currentPlan}</strong><p>{number(insight.users?.used)} pessoas ativas · {number(insight.tokens?.limit)} tokens mensais</p></div><a href={urls.usage}>Ver uso</a></section><section className="cadu-ds-plan-grid">{cards.map((option, index) => { const name = option.plan_name || option.plan_definition_name || option.plan_type || `Plano ${index + 1}`; const isCurrent = option.is_current || name === currentPlan; return <article className={isCurrent ? 'is-current' : ''} key={option.id || name}><span>{isCurrent ? 'Plano atual' : index === 0 ? 'Comece por aqui' : 'Para crescer'}</span><h3>{name}</h3><p>{number(option.tokens_monthly_limit || option.pd_tokens_monthly_limit || 0)} tokens mensais e até {number(option.max_users || option.pd_max_users || 0)} pessoas.</p><ul><li>Contexto compartilhado da equipe</li><li>Projetos e marcas organizados</li><li>Uso acompanhado por período</li></ul><a href={isCurrent ? urls.usage : urls.team}>{isCurrent ? 'Acompanhar plano' : 'Falar com o time'}</a></article>; })}</section></div>;
}

function Usage({account}) {
  const insight = account.insights || {};
  return <div className="cadu-ds-account-stack"><section className="cadu-ds-account-story"><span>Uso da equipe</span><h2>Entenda como o saldo está sendo consumido</h2><p>Veja o movimento recente e acompanhe o ciclo atual antes de decidir novos créditos.</p></section><section className="cadu-ds-account-metrics"><Metric label="Tokens neste ciclo" value={`${number(insight.tokens?.used)} de ${number(insight.tokens?.limit)}`}><progress value={insight.tokens?.percentage || 0} max="100"/></Metric><Metric label="Execuções recentes" value={number(account.movements?.length)} detail="registros confirmados"/><Metric label="Consumo confirmado" value={number((account.movements || []).reduce((total, item) => total + Number(item.amount || 0), 0))} detail="tokens debitados"/></section><section className="cadu-ds-account-section"><header><div><span>Consumo confirmado</span><h2>Atividade recente da equipe</h2></div></header><DataTable columns={['Execução', 'Data', 'Referência', 'Créditos']} empty="Quando a equipe usar uma ferramenta Cadu, o consumo confirmado aparecerá aqui." rows={(account.movements || []).map((item, index) => <tr key={item.id || index}><td><b>{item.reason || 'Execução Cadu'}</b></td><td>{dateTime(item.created_at)}</td><td>{item.reference || '—'}</td><td>−{number(item.amount)}</td></tr>)}/></section></div>;
}

function Credits({account}) {
  const available = account.credit?.available ?? account.position?.available ?? 0;
  return <div className="cadu-ds-account-stack"><section className="cadu-ds-account-story"><span>Saldo disponível</span><h2>{number(available)} créditos para a equipe</h2><p>Créditos são compartilhados entre as pessoas da agência e debitados quando uma ferramenta conclui o trabalho.</p></section><section className="cadu-ds-account-metrics"><Metric label="Créditos disponíveis" value={number(available)}/><Metric label="Lotes ativos" value={number(account.purchases?.length)} detail="com validade acompanhada"/><Metric label="Último consumo" value={number(account.movements?.[0]?.amount)} detail={account.movements?.[0]?.reason || 'Nenhum consumo registrado'}/></section><section className="cadu-ds-account-section"><header><div><span>Saldo por lote</span><h2>Créditos disponíveis</h2></div></header><DataTable columns={['Pacote', 'Vencimento', 'Disponível', 'Total']} empty="Não há lotes ativos no momento." rows={(account.purchases || []).map((lot, index) => <tr key={lot.id || index}><td><b>{lot.package_name}</b></td><td>{lot.expires_at ? civilDate(lot.expires_at) : 'Sem vencimento'}</td><td>{number(lot.available)}</td><td>{number(lot.credits)}</td></tr>)}/></section></div>;
}

function Billing({account}) {
  const summary = account.summary || {};
  return <div className="cadu-ds-account-stack"><section className="cadu-ds-account-metrics"><Metric label="Em aberto" value={money(summary.open_total)} detail={`${number(summary.open_count)} faturas`}/><Metric label="Pagas" value={number(summary.paid_count)} detail="no histórico disponível"/><Metric label="Em atraso" value={number(summary.overdue_count)} detail={summary.overdue_count ? 'Requer atenção' : 'Nenhuma pendência vencida'}/></section><section className="cadu-ds-account-section"><header><div><span>Financeiro</span><h2>Histórico de faturas</h2></div></header><DataTable columns={['Fatura', 'Referência', 'Vencimento', 'Status', 'Valor', 'Documento']} empty="Quando houver cobrança registrada, ela aparecerá aqui." rows={(account.invoices || []).map((invoice, index) => <tr key={invoice.id || index}><td><b>{invoice.number}</b></td><td>{invoice.reference || '—'}</td><td>{civilDate(invoice.due_date)}</td><td>{invoiceStatuses[invoice.status_normalized] || invoice.status_normalized}</td><td>{money(invoice.total)}</td><td>{invoice.pdf_safe_url ? <a href={invoice.pdf_safe_url} target="_blank" rel="noreferrer">Abrir PDF</a> : '—'}</td></tr>)}/></section></div>;
}

export function WorkspaceAccount({bootstrap}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const section = bootstrap.section;
  const org = bootstrap.account.organization || {};
  const menuProjects = bootstrap.projects || bootstrap.account.agency_context?.projects || [];
  const menuBrands = bootstrap.brands || bootstrap.account.agency_context?.brands || [];
  const content = section === 'agencia' ? <Agency bootstrap={bootstrap}/> : section === 'perfil' ? <Profile bootstrap={bootstrap}/> : section === 'equipe' ? <Team bootstrap={bootstrap}/> : section === 'planos' ? <Plan account={bootstrap.account} urls={bootstrap.urls}/> : section === 'uso' ? <Usage account={bootstrap.account}/> : section === 'creditos' ? <Credits account={bootstrap.account}/> : <Billing account={bootstrap.account}/>;
  const usagePercent = bootstrap.usagePercent ?? bootstrap.account.position?.usage_percentage ?? 0;
  return <div className="cadu-ds-home-shell cadu-ds-account-shell"><main className="cadu-ds-home-main"><div className="cadu-ds-home-workarea"><CaduDock bootstrap={bootstrap} logo={bootstrap.caduMark} homeUrl={bootstrap.urls.home} userName={bootstrap.user.name} userAvatar={bootstrap.user.avatar} userInitials={bootstrap.user.name?.slice(0, 2).toUpperCase()} accountOpen={menuOpen} accountMenu={<WorkspaceAccountMenu open={menuOpen} onClose={() => setMenuOpen(false)} user={bootstrap.user} links={bootstrap.urls} projects={menuProjects} brands={menuBrands} usagePercent={usagePercent} onManageShortcuts={() => window.location.assign(`${bootstrap.urls.home}#atalhos`)}/>} onOpenAccount={() => setMenuOpen(current => !current)} shortcutItems={bootstrap.dock?.items || []} usagePercent={usagePercent} onNewConversation={() => window.location.assign(bootstrap.urls.newConversation)} onOpenBrand={openWorkspaceDetail} onOpenResource={openWorkspaceDetail} onOpenUsage={() => setMenuOpen(true)}/><WorkspaceContextSidebar mode="account" active={section} links={bootstrap.urls} agencyName={org.nome_fantasia || 'Sua equipe'}/><section className="cadu-ds-account-content"><nav className="cadu-ds-account-tabs" aria-label="Conta">{Object.entries(labels).map(([id, label]) => <a key={id} href={bootstrap.urls[id]} aria-current={id === section ? 'page' : undefined}>{label}</a>)}</nav>{content}</section></div></main></div>;
}
