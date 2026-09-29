import React, {useEffect, useState} from 'react';
import {CaduDock} from './CaduDock';
import {WorkspaceAccountMenu} from './WorkspaceFeedback';
import {WorkspaceContextSidebar} from './WorkspaceContextSidebar';
import {VisualIdentity} from './VisualIdentity';
import {workspaceUserPhoto} from '../workspaceIdentity.mjs';
import {openWorkspaceDetail} from '../workspaceNavigation';
import {WorkspaceMobileChrome} from './WorkspaceMobileChrome';
import {CaduButton} from './CaduButton';
import {CaduInput} from './CaduInput';
import {CaduSelect} from './CaduSelect';
import {useWorkspaceViewport} from '../hooks/useWorkspaceViewport';

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
const groupCommercialActivity = movements => Object.values((movements || []).reduce((groups, item) => {
  const day = civilDate(item.created_at);
  const tool = String(item.reason || 'Uso do Cadu').replace(/^Ferramenta:\s*/i, '').split(' · ')[0].replace(/\bclient_id\b\s*[:=#]?\s*\d*/gi, '').trim() || 'Uso do Cadu';
  const key = `${day}::${tool}`;
  const current = groups[key] || {id:key, created_at:item.created_at, reason:tool, amount:0, executions:0};
  current.amount += Number(item.amount || 0);
  current.executions += 1;
  current.reference = `${current.executions} ${current.executions === 1 ? 'execução' : 'execuções'}`;
  groups[key] = current;
  return groups;
}, {})).sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)));
const eventTypes = {invite: 'Convite', welcome: 'Boas-vindas', launch_bonus: 'Bônus inicial', password_reset: 'Redefinição', password_changed: 'Senha alterada'};
const deliveryStatuses = {sent: 'Enviado', delivered: 'Entregue', opened: 'Aberto', clicked: 'Clicado', deferred: 'Adiado', failed: 'Falhou'};
const invoiceStatuses = {paid: 'Paga', overdue: 'Em atraso', pending: 'Pendente'};

function Hidden({name, value}) { return <input type="hidden" name={name} value={value || ''}/>; }
function Metric({label, value, detail, children}) { return <article><span>{label}</span><strong>{value}</strong>{detail && <p>{detail}</p>}{children}</article>; }
function PurchaseModal({bootstrap}) {
  const [order, setOrder] = useState(null); const [billing, setBilling] = useState('prepaid'); const [note, setNote] = useState(''); const [state, setState] = useState('');
  useEffect(() => { const open = event => { setOrder(event.detail); setBilling('prepaid'); setNote(''); setState(''); }; window.addEventListener('cadu-open-purchase', open); return () => window.removeEventListener('cadu-open-purchase', open); }, []);
  if (!order) return null;
  const confirm = async () => { setState('Liberando créditos…'); try { const response = await fetch(bootstrap.endpoints.creditRequest, {method:'POST', credentials:'same-origin', headers:{'Content-Type':'application/json','X-CSRF-Token':bootstrap.csrf}, body:JSON.stringify({tokens:order.tokens || 0, price:order.price || 0, package_name:order.name, billing_mode:billing, note})}); const data = await response.json(); setState(data.message || data.error || 'Não foi possível concluir.'); if (data.success) setTimeout(() => window.location.reload(), 1400); } catch { setState('Não foi possível concluir o pedido.'); } };
  return <div className="cadu-ds-purchase-modal" role="dialog" aria-modal="true" aria-labelledby="cadu-purchase-title"><div className="cadu-ds-purchase-modal__card"><button className="cadu-ds-purchase-modal__close" type="button" onClick={() => setOrder(null)} aria-label="Fechar">×</button><span>Compra de créditos</span><h2 id="cadu-purchase-title">Confirmar {order.kind === 'plan' ? 'plano' : 'pacote'}</h2><div className="cadu-ds-purchase-modal__summary"><strong>{order.name}</strong><b>{order.price ? money(order.price) + (order.kind === 'plan' ? ' / mês' : '') : 'Valor não disponível'}</b>{order.tokens ? <small>{number(order.tokens)} créditos</small> : null}</div><label>Forma de cobrança<select value={billing} onChange={event => setBilling(event.target.value)}><option value="prepaid">Pagamento antecipado</option><option value="postpaid">Pós-pago / faturamento financeiro</option></select></label><label>Observação<textarea rows="3" value={note} onChange={event => setNote(event.target.value)} placeholder="Ex.: iniciar no próximo ciclo…"/></label><p className="cadu-ds-purchase-modal__hint">Ao confirmar, os créditos entram imediatamente no saldo compartilhado do seu time. O financeiro recebe a notificação para registrar a cobrança.</p><footer><button type="button" onClick={() => setOrder(null)}>Voltar</button><button type="button" className="is-primary" onClick={confirm}>Confirmar compra</button></footer>{state && <p className="cadu-ds-account-notice" role="status">{state}</p>}</div></div>;
}
function AccountPageHeader({eyebrow, title, description, image, initials}) {
  return <header className="cadu-ds-account-page-header"><VisualIdentity src={image} initials={initials || title} label={title} color="#176b5e"/><div><p className="cadu-ds-page-eyebrow">{eyebrow}</p><h1>{title}</h1><p className="cadu-ds-page-description">{description}</p></div></header>;
}
function CreditSummary({available, lots, lastMovement}) {
  return <section className="cadu-ds-credit-summary" aria-label="Resumo de créditos">
    <div className="cadu-ds-credit-summary__balance"><span>Saldo disponível</span><strong>{number(available)}</strong><p>Créditos compartilhados entre as pessoas e ferramentas desta equipe.</p></div>
    <dl><div><dt>Lotes ativos</dt><dd>{number(lots)}</dd></div><div><dt>Último consumo</dt><dd>{lastMovement ? `${number(lastMovement.amount)} créditos` : 'Nenhum'}</dd><small>{lastMovement?.reason || 'Ainda não há consumo registrado.'}</small></div></dl>
  </section>;
}
function DataTable({columns, rows, empty = 'Nenhum registro disponível.'}) {
  const displayColumn = column => ({Execução:'Ferramenta', Data:'Dia'}[column] || column);
  return <div className="cadu-ds-account-table"><table><thead><tr>{columns.map(column => <th key={column}>{displayColumn(column)}</th>)}</tr></thead><tbody>{rows.length ? rows : <tr><td colSpan={columns.length}>{empty}</td></tr>}</tbody></table></div>;
}

function Agency({bootstrap}) {
  const {account, endpoints, csrf, admin, urls} = bootstrap;
  const org = account.organization || {};
  const context = account.agency_context || {};
  const projects = context.projects || [];
  const brands = context.brands || [];
  const projectsByBrand = brands.map(brand => ({...brand, projects: projects.filter(project => project.brandName === brand.name)})).concat(projects.filter(project => !project.brandName || !brands.some(brand => brand.name === project.brandName)).length ? [{id:'without-brand', name:'Sem marca', projects:projects.filter(project => !project.brandName || !brands.some(brand => brand.name === project.brandName))}] : []);
  return <div className="cadu-ds-account-stack">
    <AccountPageHeader eyebrow="Agência" title={org.nome_fantasia || 'O trabalho do cliente'} description="Projetos, marcas e pessoas no mesmo espaço de gestão." initials={org.nome_fantasia || org.razao_social || 'AG'}/>
    {admin ? <form className="cadu-ds-account-form" method="post" action={endpoints.updateOrganization}><Hidden name="_csrf" value={csrf}/><CaduInput label="Nome da agência" name="trade_name" defaultValue={org.nome_fantasia || ''} required/><CaduInput label="Razão social" name="legal_name" defaultValue={org.razao_social || ''}/><CaduInput label="CPF ou CNPJ" name="document" defaultValue={org.cnpj || ''}/><CaduInput label="CEP" name="postal_code" defaultValue={org.cep || ''}/><CaduInput label="Logradouro" name="street" defaultValue={org.logradouro || ''}/><CaduInput label="Número" name="number" defaultValue={org.numero || ''}/><CaduInput label="Complemento" name="complement" defaultValue={org.complemento || ''}/><CaduInput label="Bairro" name="district" defaultValue={org.bairro || ''}/><CaduInput label="Cidade" name="city" defaultValue={org.cidade || ''}/><CaduSelect label="Estado" name="state" defaultValue={org.estado_sigla || ''} options={[{value:'', label:'Não informado'}, ...(account.states || []).map(state => ({value:state.sigla, label:`${state.sigla} — ${state.descricao}`}))]}/><footer><span>Esse nome aparece no Workspace e nos contextos da equipe.</span><CaduButton type="submit">Salvar dados da agência</CaduButton></footer></form> : <section className="cadu-ds-account-section"><header><div><span>Identidade da agência</span><h2>{org.nome_fantasia || 'Sua equipe'}</h2></div></header><p className="cadu-ds-account-section-copy">Somente administradores podem alterar os dados da agência. Fale com uma pessoa administradora se precisar ajustar o nome.</p></section>}
    <section className="cadu-ds-account-metrics"><Metric label="Pessoas" value={number(account.people?.length)} detail="com acesso ao Workspace"><a href={urls.team}>Gerenciar equipe</a></Metric><Metric label="Projetos" value={number(projects.length)} detail="contextos ativos"><a href={urls.projects}>Ver projetos</a></Metric><Metric label="Marcas" value={number(brands.length)} detail="identidades disponíveis"><a href={urls.brands}>Ver marcas</a></Metric></section>
    <section className="cadu-ds-account-section"><header><div><span>Contextos de trabalho</span><h2>Marcas e projetos</h2></div><a href={urls.projects}>Ver projetos</a></header><p className="cadu-ds-account-section-copy">Cada marca reúne os projetos que usam sua identidade e contexto. Projetos sem marca ficam separados.</p><div className="cadu-ds-brand-project-groups">{projectsByBrand.length ? projectsByBrand.map(group => <article key={group.id}><header><VisualIdentity src={group.logoUrl} initials={group.name} label={group.name} color={group.visualColor || '#176b5e'}/><div><b>{group.name}</b><small>{number(group.projects.length)} projeto{group.projects.length === 1 ? '' : 's'}</small></div><a href={group.href || urls.brands}>Abrir marca</a></header><div className="cadu-ds-account-list">{group.projects.length ? group.projects.slice(0, 6).map(project => <a href={project.href} key={project.id}><VisualIdentity src={project.logoUrl} initials={project.name} label={project.name} color={project.visualColor || '#176b5e'}/><div><b>{project.name}</b><small>{number(project.sources)} fontes</small></div><em>{project.status === 'arquivado' ? 'Arquivado' : 'Ativo'}</em></a>) : <p className="cadu-ds-account-empty">Nenhum projeto vinculado a esta marca.</p>}</div></article>) : <p className="cadu-ds-account-empty">Crie o primeiro projeto para formar o contexto do time.</p>}</div></section>
    <section className="cadu-ds-account-section cadu-ds-account-people"><header><div><span>Pessoas e permissões</span><h2>Pessoas da agência</h2></div><a href={urls.team}>Gerenciar equipe</a></header><p className="cadu-ds-account-section-copy">Pessoas são administradas separadamente dos projetos e das marcas.</p><div className="cadu-ds-account-list">{(account.people || []).length ? account.people.map(person => <article key={person.id_contato_cliente}><i>{(person.nome_completo || '?').slice(0, 1).toUpperCase()}</i><div><b>{person.nome_completo}</b><small>{person.email} · {person.cargo || person.setor || 'Pessoa do time'}</small></div><em>{person.status ? 'Ativo' : 'Inativo'}</em></article>) : <p className="cadu-ds-account-empty">Convide pessoas para trabalhar nos mesmos contextos.</p>}</div></section>
  </div>;
}

function Profile({bootstrap}) {
  const account = bootstrap.account;
  const person = account.current_user || {};
  return <div className="cadu-ds-account-stack">
    <AccountPageHeader eyebrow="Perfil" title={person.nome_completo || bootstrap.user.name} description="Sua identidade em conversas, decisões e convites." image={workspaceUserPhoto(bootstrap.user)} initials={person.nome_completo || bootstrap.user.name}/>
    <form className="cadu-ds-account-form" method="post" action={bootstrap.endpoints.updateProfile}><Hidden name="_csrf" value={bootstrap.csrf}/><Hidden name="avatar_badge" value={person.cadu_avatar_badge || bootstrap.user.avatarBadge}/><CaduInput label="Nome completo" name="name" defaultValue={person.nome_completo || bootstrap.user.name} required/><CaduInput label="E-mail" defaultValue={person.email || bootstrap.user.email} disabled/><CaduInput label="Telefone" name="phone" defaultValue={person.telefone || ''}/><footer><span>Seu e-mail é gerenciado pela identidade de acesso.</span><CaduButton type="submit">Salvar perfil</CaduButton></footer></form>
    <section className="cadu-ds-account-section"><header><div><span>Comunicação da conta</span><h2>E-mails disparados por página</h2></div><small>{account.email_catalog?.length || 0} modelos ativos</small></header><DataTable columns={['Página', 'Ação', 'Destinatário', 'Assunto', 'Disparo']} rows={(account.email_catalog || []).map((email, index) => <tr key={email.template || index}><td><b>{email.page}</b></td><td>{email.action}</td><td>{email.recipient}</td><td>{email.subject}<small>{email.template}</small></td><td>{email.timing}</td></tr>)}/></section>
    <section className="cadu-ds-account-section"><header><div><span>Histórico de envio</span><h2>E-mails da equipe</h2></div><small>{account.email_events?.length || 0} registros</small></header><DataTable columns={['Atualização', 'Destinatário', 'Tipo', 'Assunto', 'Status']} empty="Os próximos envios da conta aparecerão aqui." rows={(account.email_events || []).map((event, index) => <tr key={event.id || index}><td>{dateTime(event.last_event_at || event.created_at)}</td><td>{event.recipient_email}</td><td>{eventTypes[event.event_type] || event.event_type}</td><td>{event.subject}</td><td><b>{deliveryStatuses[event.status] || event.status}</b></td></tr>)}/></section>
  </div>;
}

function Team({bootstrap}) {
  const {account, endpoints, csrf, admin} = bootstrap;
  const confirmAction = event => {
    event.preventDefault();
    if (window.confirm('Confirma a alteração de acesso desta pessoa?')) event.currentTarget.submit();
  };
  const pendingInvites = (account.invites || []).filter(item => item.status === 'pending');
  return <div className="cadu-ds-account-stack">
    <AccountPageHeader eyebrow="Equipe" title="Pessoas e acessos" description="Convites e permissões da agência." initials={account.organization?.nome_fantasia || 'EQ'}/>
    {admin && <section className="cadu-ds-account-section"><header><div><span>Nova pessoa</span><h2>Convidar para a equipe</h2></div></header><form className="cadu-ds-account-inline-form" method="post" action={endpoints.invite}><Hidden name="_csrf" value={csrf}/><CaduInput label="E-mail" type="email" name="email" required/><CaduSelect label="Acesso" name="role" options={[{value:'member',label:'Membro'},{value:'admin',label:'Administrador'}]}/><CaduButton type="submit">Enviar convite</CaduButton></form></section>}
    <section className="cadu-ds-account-section"><header><div><span>Núcleo da agência</span><h2>Pessoas da equipe</h2></div><small>{account.people?.length || 0} pessoas</small></header><p className="cadu-ds-account-section-copy">Projetos, marcas, plano e créditos são compartilhados por esta equipe.</p><div className="cadu-ds-account-list">{(account.people || []).length ? account.people.map(person => <article key={person.id_contato_cliente}><i>{(person.nome_completo || '?').slice(0, 1).toUpperCase()}</i><div><b>{person.nome_completo}</b><small>{person.email} · {person.cargo || person.setor || 'Equipe da agência'}</small></div><em>{person.status ? 'Ativo' : 'Inativo'}</em>{admin && String(person.id_contato_cliente) !== String(bootstrap.user.id) && <div className="cadu-ds-account-row-actions"><form method="post" action={`${endpoints.memberBase}/${person.id_contato_cliente}/papel`}><Hidden name="_csrf" value={csrf}/><select name="role" defaultValue={['admin', 'superadmin'].includes(person.user_type) ? 'admin' : person.user_type || 'client'}><option value="client">Membro</option><option value="admin">Administrador</option><option value="readonly">Somente leitura</option></select><CaduButton type="submit" size="xs">Salvar</CaduButton></form><form method="post" action={`${endpoints.memberBase}/${person.id_contato_cliente}/status`} onSubmit={confirmAction}><Hidden name="_csrf" value={csrf}/><CaduButton type="submit" size="xs" variant={person.status ? 'danger' : 'secondary'}>{person.status ? 'Desativar' : 'Reativar'}</CaduButton></form></div>}</article>) : <p className="cadu-ds-account-empty">Convide a primeira pessoa para começar a trabalhar em conjunto.</p>}</div></section>
    <section className="cadu-ds-account-section"><header><div><span>Acessos aguardando resposta</span><h2>Convites enviados</h2></div></header><div className="cadu-ds-account-list">{pendingInvites.length ? pendingInvites.map(invite => { const expired = Boolean(invite.expires_at && new Date(invite.expires_at).getTime() < Date.now()); return <article key={invite.id}><i>@</i><div><b>{invite.email}</b><small>{invite.role === 'admin' ? 'Administrador' : 'Membro'} · {expired ? 'expirou em' : 'expira em'} {civilDate(invite.expires_at)}</small></div><em>{expired ? 'Expirado' : 'Pendente'}</em>{admin && <div className="cadu-ds-account-row-actions"><form method="post" action={`${endpoints.inviteBase}/${invite.id}/reenviar`}><Hidden name="_csrf" value={csrf}/><CaduButton type="submit" size="xs" variant="secondary">Reenviar</CaduButton></form><form method="post" action={`${endpoints.inviteBase}/${invite.id}/cancelar`}><Hidden name="_csrf" value={csrf}/><CaduButton type="submit" size="xs" variant="danger">Cancelar</CaduButton></form></div>}</article>; }) : <p className="cadu-ds-account-empty">Nenhum convite aguardando resposta.</p>}</div></section>
  </div>;
}

function Plan({account, urls}) {
  const currentPlan = account.plan?.plan_definition_name || account.plan?.plan_type || '';
  const options = account.plan_options || [];
  const currentKey = String(account.plan?.id_plan_definition || currentPlan).toLocaleLowerCase('pt-BR');
  const getName = option => option.plan_name || option.plan_definition_name || option.plan_type || 'Plano';
  const isCurrent = option => String(option.id || getName(option)).toLocaleLowerCase('pt-BR') === currentKey || getName(option).toLocaleLowerCase('pt-BR') === currentKey;
  const formatStorage = value => {
    const bytes = Number(value) || 0;
    if (!bytes) return '—';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
    return `${new Intl.NumberFormat('pt-BR', {maximumFractionDigits:1}).format(bytes / (1024 ** index))} ${units[index]}`;
  };
  const plans = options.map(option => {
    const type = String(option.plan_type || option.slug || '').toLocaleLowerCase('pt-BR');
    return {...option, name:getName(option), price:Number(option.price_monthly ?? option.monthly_price ?? option.price ?? 0), current:isCurrent(option), checkout:['pro','enterprise'].includes(type)};
  });
  const featureRows = [
    {label:'Tokens por mês', value:plan => Number(plan.tokens_monthly_limit ?? plan.pd_tokens_monthly_limit) > 0 ? `${number(plan.tokens_monthly_limit ?? plan.pd_tokens_monthly_limit)} tokens` : '—'},
    {label:'Créditos de imagem', value:plan => Number(plan.limit_image_generation ?? plan.image_credits_monthly) > 0 ? number(plan.limit_image_generation ?? plan.image_credits_monthly) : '—'},
    {label:'Pessoas na equipe', value:plan => Number(plan.max_users ?? plan.pd_max_users) > 0 ? number(plan.max_users ?? plan.pd_max_users) : '—'},
    {label:'Armazenamento', value:plan => formatStorage(plan.storage_bytes_limit ?? plan.pd_storage_bytes_limit)},
  ];
  return <div className="cadu-ds-account-stack cadu-ds-pricing-page">
    <header className="cadu-ds-pricing-heading"><span className="cadu-ds-page-eyebrow">Planos</span><h1>Planos para sua equipe</h1><p>Compare recursos e valores mensais para escolher a opção adequada.</p></header>
    {currentPlan && <div className="cadu-ds-pricing-current"><span>Seu plano atual</span><strong>{currentPlan}</strong><a href={urls.usage}>Acompanhar uso</a></div>}
    {plans.length ? <>
      <section className="cadu-ds-pricing-cards" aria-label="Planos disponíveis">{plans.map(plan => <article className={`cadu-ds-pricing-card${plan.current ? ' is-current' : ''}`} key={plan.id || plan.name}>
        {plan.current && <span className="cadu-ds-pricing-badge">Seu plano</span>}
        <h2>{plan.name}</h2><p className="cadu-ds-pricing-description">{plan.description || 'Recursos para sua equipe trabalhar com o Cadu.'}</p>
        <div className="cadu-ds-pricing-price"><strong>{plan.price > 0 ? money(plan.price) : 'Grátis'}</strong>{plan.price > 0 && <span>/ mês</span>}</div>
        <ul><li>{Number(plan.tokens_monthly_limit || 0) > 0 ? `${number(plan.tokens_monthly_limit)} tokens por mês` : 'Limite de tokens não informado'}</li><li>{Number(plan.limit_image_generation || plan.image_credits_monthly || 0) > 0 ? `${number(plan.limit_image_generation || plan.image_credits_monthly)} créditos de imagem` : 'Créditos de imagem não informados'}</li><li>{Number(plan.max_users || 0) > 0 ? `Até ${number(plan.max_users)} pessoas` : 'Limite de equipe não informado'}</li></ul>
        {plan.current ? <span className="cadu-ds-pricing-action is-selected">Plano atual</span> : plan.checkout ? <a className="cadu-ds-pricing-action" href="/assinatura/checkout">Ver contratação</a> : <span className="cadu-ds-pricing-action is-unavailable">Consulte a equipe</span>}
      </article>)}</section>
      <section className="cadu-ds-pricing-comparison"><header><span>Compare os planos</span><h2>Recursos incluídos</h2></header><div className="cadu-ds-account-table"><table><thead><tr><th>Recursos</th>{plans.map(plan => <th key={plan.id || plan.name}>{plan.name}</th>)}</tr></thead><tbody><tr><th scope="row">Preço mensal</th>{plans.map(plan => <td key={plan.id || plan.name}>{plan.price > 0 ? money(plan.price) : 'Grátis'}</td>)}</tr>{featureRows.map(row => <tr key={row.label}><th scope="row">{row.label}</th>{plans.map(plan => <td key={plan.id || plan.name}>{row.value(plan)}</td>)}</tr>)}</tbody></table></div></section>
    </> : <section className="cadu-ds-pricing-empty"><h2>Nenhum plano disponível agora</h2><p>As opções de assinatura ainda não foram publicadas para esta conta.</p></section>}
  </div>;
}

function Usage({account, image}) {
  const insight = account.insights || {};
  const movements = groupCommercialActivity(account.movements);
  const additions = account.credit_additions || [];
  const space = account.space || {};
  const mb = (Number(space.bytes_used || 0) / 1048576).toFixed(2);
  return <div className="cadu-ds-account-stack"><AccountPageHeader eyebrow="Uso do seu time" title="Consumo e espaço" description="Acompanhe as interações, os créditos utilizados e o espaço ocupado pela equipe."/><section className="cadu-ds-account-metrics"><Metric label="Tokens neste ciclo" value={`${number(insight.tokens?.used)} de ${number(insight.tokens?.limit)}`}><progress value={insight.tokens?.percentage || 0} max="100"/></Metric><Metric label="Interações recentes" value={number(movements.length)} detail="ferramentas e execuções agrupadas"/><Metric label="Espaço usado" value={`${mb} MB`} detail="arquivos da equipe"/></section><section className="cadu-ds-account-section"><header><div><span>Espaço do time</span><h2>Projetos, marcas e arquivos</h2></div><small>Projetos e marcas ilimitados</small></header><DataTable columns={['Recurso', 'Quantidade / uso', 'Regra']} rows={[<tr key="projects"><td><b>Projetos</b></td><td>{number(space.projects)}</td><td>Ilimitados</td></tr>,<tr key="brands"><td><b>Marcas</b></td><td>{number(account.agency_context?.brands?.length)}</td><td>Ilimitadas</td></tr>,<tr key="files"><td><b>Arquivos indexados</b></td><td>{number(space.files)} · {mb} MB</td><td>Indexação automática; espaço medido por equipe</td></tr>,<tr key="conversations"><td><b>Conversas e ações de IA</b></td><td>{number(movements.length)} interações agrupadas</td><td>Consomem créditos quando usam IA</td></tr>,<tr key="tokens"><td><b>Conteúdo processado</b></td><td>{number(space.indexed_tokens)}</td><td>Volume de texto preparado para uso pelo Cadu</td></tr>]}/></section><section className="cadu-ds-account-section"><header><div><span>Entradas de saldo</span><h2>Créditos adicionados</h2></div><small>{number(additions.length)} lotes registrados</small></header><DataTable columns={['Origem', 'Data', 'Referência', 'Créditos']} empty="Nenhum saldo foi adicionado ainda." rows={additions.map((item, index) => <tr key={item.id || index}><td><b>{item.reason}</b></td><td>{dateTime(item.created_at)}</td><td>{item.reference || '—'}</td><td>+{number(item.amount)}</td></tr>)}/></section><section className="cadu-ds-account-section"><header><div><span>Interações do time</span><h2>Atividade recente</h2></div><small>Uso de ferramentas Cadu</small></header><DataTable columns={['Execução', 'Data', 'Referência', 'Créditos']} empty="Ainda não há consumo de IA confirmado." rows={movements.map((item, index) => <tr key={item.id || index}><td><b>{item.reason || 'Execução Cadu'}</b></td><td>{dateTime(item.created_at)}</td><td>{item.reference || '—'}</td><td>−{number(item.amount)}</td></tr>)}/></section></div>;
}

function Credits({account, bootstrap}) {
  const available = account.credit?.available ?? account.position?.available ?? 0;
  const packages = [{tokens:100000, price:49, label:'Extra Essencial', description:'Reforço pontual para uma operação em andamento.'},{tokens:500000, price:179, label:'Extra Equipe', description:'Mais margem para planejamento, auditoria e produção.'},{tokens:1000000, price:299, label:'Extra Agência', description:'Volume para múltiplos projetos e clientes.'}];
  const choosePackage = pack => window.dispatchEvent(new CustomEvent('cadu-open-purchase', {detail:{kind:'package', name:pack.label, tokens:pack.tokens, price:pack.price}}));
  return <div className="cadu-ds-account-stack"><AccountPageHeader eyebrow="Quando você precisar" title="Créditos acompanham o seu uso" description="Escolha um pacote, confirme a compra e libere o saldo para o seu time na hora. O financeiro recebe a notificação para cuidar da cobrança."/><CreditSummary available={available} lots={account.purchases?.length} lastMovement={account.movements?.[0]}/><section className="cadu-ds-account-section cadu-ds-credit-packages"><header><div><span>Saldo extra para o seu time</span><h2>Pacotes de créditos</h2></div><small>Liberação imediata</small></header><p className="cadu-ds-account-section-copy">Os créditos são compartilhados entre as pessoas da equipe e usados quando o Cadu conversa, pesquisa, indexa arquivos ou cria entregas com IA.</p><DataTable columns={['Pacote', 'Volume', 'Indicado para', 'Preço']} rows={packages.map(pack => <tr key={pack.tokens}><td><b>{pack.label}</b></td><td>{number(pack.tokens)} créditos</td><td>{pack.description}</td><td>{money(pack.price)}</td></tr>)}/><div className="cadu-ds-credit-package-grid">{packages.map(pack => <article key={pack.tokens}><span>{pack.label}</span><strong>{number(pack.tokens)} créditos</strong><b>{money(pack.price)}</b><p>{pack.description}</p><small>Saldo liberado imediatamente após a confirmação.</small><CaduButton type="button" onClick={() => choosePackage(pack)}>Comprar pacote</CaduButton></article>)}</div></section><section className="cadu-ds-account-section cadu-ds-credit-usage-guide"><header><div><span>Como os créditos entram no trabalho</span><h2>Use conforme a operação pede</h2></div><small>Volume compartilhado</small></header><p className="cadu-ds-account-section-copy">Projetos, marcas e arquivos continuam disponíveis. Os créditos entram quando o Cadu processa contexto, conversa, pesquisa, indexa ou cria uma entrega.</p></section><section className="cadu-ds-account-section"><header><div><span>Seu histórico</span><h2>Saldo por lote</h2></div></header><DataTable columns={['Pacote', 'Vencimento', 'Disponível', 'Total']} empty="Ainda não há créditos extras. Isso é normal: você pode começar usando o acesso gratuito." rows={(account.purchases || []).map((lot, index) => <tr key={lot.id || index}><td><b>{lot.package_name}</b></td><td>{lot.expires_at ? civilDate(lot.expires_at) : 'Sem vencimento'}</td><td>{number(lot.available)}</td><td>{number(lot.credits)}</td></tr>)}/></section></div>;
}

function Integrations({bootstrap}) {
  const data = bootstrap.account.integrations || {};
  const google = data.google || {};
  const connection = google.connection;
  const [message, setMessage] = useState('');
  const post = async (url, body) => {
    setMessage('Atualizando…');
    try {
      const response = await fetch(url, {method:'POST', credentials:'same-origin', headers:{'Content-Type':'application/json','X-CSRF-Token':bootstrap.csrf}, body:JSON.stringify(body || {})});
      const result = await response.json();
      setMessage(result.message || result.error || (response.ok ? 'Atualizado.' : 'Não foi possível atualizar.'));
      if (response.ok) setTimeout(() => window.location.reload(), 900);
    } catch { setMessage('Não foi possível concluir agora.'); }
  };
  const linkResource = (event, resourceId) => {
    event.preventDefault();
    const projectRef = new FormData(event.currentTarget).get('project_ref');
    if (!projectRef) return setMessage('Escolha um projeto.');
    post(`${bootstrap.endpoints.googleResourceBase}/${resourceId}/link`, {project_ref:projectRef});
  };
  const fetchMeetArtifact = artifactId => post(`${bootstrap.endpoints.googleMeetArtifactBase}/${artifactId}/fetch`);
  const status = connection?.status === 'connected' ? 'Conectado' : connection ? 'Requer atenção' : 'Não conectado';
  const connectionHealthy = connection?.status === 'connected';
  const connectors = [...(data.priority_connectors || []), ...(data.coming_soon_connectors || [])];
  return <div className="cadu-ds-account-stack cadu-ds-integrations">
    <AccountPageHeader eyebrow="Integrações" title="Fontes conectadas ao trabalho" description="Arquivos, reuniões, relatórios e agentes disponíveis para os projetos." image={bootstrap.caduMark}/>
    <section className="cadu-ds-integration-hero" id="google-workspace"><div><span>Google Workspace · {bootstrap.account?.organization?.nome_fantasia || bootstrap.contextName || 'Cliente atual'}</span><h2>{connection?.google_email || 'Conecte sua conta Google'}</h2><p>{connection?.google_domain || 'Cada pessoa autoriza a própria conta neste cliente. Arquivos e reuniões disponíveis para a equipe aparecem como fontes escolhidas.'}</p></div><em className={connectionHealthy ? 'is-connected' : connection ? 'needs-attention' : ''}>{status}</em><div className="cadu-ds-integration-actions">{connection ? <><CaduButton type="button" variant="secondary" onClick={() => post(bootstrap.endpoints.googleSync)}>Atualizar dados</CaduButton><a href={google.connect_url}>Trocar conta</a><CaduButton type="button" variant="danger" onClick={() => post(bootstrap.endpoints.googleDisconnect)}>Desconectar minha conta</CaduButton></> : <a className="is-primary" href={google.connect_url}>Conectar minha conta</a>}</div></section>
    {message && <p className="cadu-ds-account-notice" role="status">{message}</p>}
    <section className="cadu-ds-account-section"><header><div><span>Serviços autorizados</span><h2>O que pode entrar nos projetos</h2></div><small>{number(google.summary?.enabled_count)} ativos</small></header><div className="cadu-ds-integration-services">{(google.services || []).map(service => <article key={service.key}><i>{service.name?.slice(0, 2).toUpperCase()}</i><div><b>{service.name}</b><small>{service.description}</small></div><em>{service.status_label}</em></article>)}</div></section>
    <section className="cadu-ds-account-section"><header><div><span>Google Workspace</span><h2>Pessoas que conectaram neste cliente</h2></div><small>{number(google.authorizations?.length)} contas</small></header><div className="cadu-ds-integration-services">{(google.authorizations || []).map(authorization => <article key={authorization.id}><i>{String(authorization.user_name || authorization.user_email || '?').slice(0, 2).toUpperCase()}</i><div><b>{authorization.user_name || authorization.user_email || 'Pessoa da equipe'}</b><small>{authorization.google_email}{authorization.last_sync_at ? ` · atualizada ${dateTime(authorization.last_sync_at)}` : ''}</small></div><em>{authorization.status === 'connected' ? 'Conectada' : 'Requer atenção'}</em></article>)}{!(google.authorizations || []).length && <p className="cadu-ds-account-empty">Ainda não há contas Google conectadas neste cliente.</p>}</div></section>
    <section className="cadu-ds-account-section"><header><div><span>Contas autorizadas</span><h2>Dados disponíveis para este cliente</h2></div><small>{number(data.connected_count)} ativas</small></header><div className="cadu-ds-integration-services">{(data.accounts || []).map(account => <article key={account.id || `${account.provider}-${account.external_account_id || account.name}`}><i>{(account.provider_label || account.provider || 'IN').slice(0, 2).toUpperCase()}</i><div><b>{account.name || account.provider_label}</b><small>{account.provider_label || 'Integração'}{account.last_synced_at ? ` · atualizada ${dateTime(account.last_synced_at)}` : ''}</small></div><em>{['active','connected','ready'].includes(account.status) ? 'Ativa' : account.status || 'Pendente'}</em></article>)}{!(data.accounts || []).length && <p className="cadu-ds-account-empty">Nenhuma conta de mídia ou relatório foi autorizada ainda.</p>}</div></section>
    {connection && <section className="cadu-ds-account-section"><header><div><span>Conteúdo disponível</span><h2>Arquivos e reuniões</h2></div><small>{number((google.resources || []).length + (google.meet_artifacts || []).length)} itens</small></header><div className="cadu-ds-integration-resources">{(google.resources || []).slice(0, 24).map(resource => <article key={resource.id}><VisualIdentity src={resource.presentation?.thumbnail_url} initials={resource.name} label={resource.name} color="#176b5e"/><div><b>{resource.name}</b><small>{resource.presentation?.product || 'Google Workspace'} · {resource.presentation?.kind || 'Arquivo'}{resource.external_url && <> · <a href={resource.external_url} target="_blank" rel="noreferrer">Abrir</a></>}</small></div><form onSubmit={event => linkResource(event, resource.id)}><select name="project_ref" aria-label={`Projeto para ${resource.name}`}><option value="">Escolher projeto</option>{(google.projects || []).map(project => <option key={project.id} value={`ci:${project.id}`}>{project.name}</option>)}</select><CaduButton type="submit" size="xs">Adicionar</CaduButton></form></article>)}{!(google.resources || []).length && <p className="cadu-ds-account-empty">Nenhum arquivo encontrado. Atualize a conexão para procurar novamente.</p>}</div></section>}
    {connection && (google.meet_artifacts || []).length > 0 && <section className="cadu-ds-account-section"><header><div><span>Google Meet</span><h2>Reuniões encontradas</h2></div><small>{number(google.meet_artifacts.length)} registros</small></header><div className="cadu-ds-integration-resources">{google.meet_artifacts.slice(0, 24).map(artifact => <article key={artifact.id}><VisualIdentity initials="ME" label={artifact.title || artifact.external_name || 'Reunião'} color="#176b5e"/><div><b>{artifact.title || artifact.external_name || 'Reunião'}</b><small>{artifact.artifact_type || 'Registro'}{artifact.conference_record ? ` · ${artifact.conference_record}` : ''}</small></div><div className="cadu-ds-integration-resource-actions">{artifact.artifact_type === 'transcript' && !artifact.content ? <CaduButton type="button" variant="secondary" onClick={() => fetchMeetArtifact(artifact.id)}>Preparar para revisão</CaduButton> : <em>{artifact.content ? 'Pronta para revisão' : 'Informações disponíveis'}</em>}{artifact.resource_id && <form onSubmit={event => linkResource(event, artifact.resource_id)}><select name="project_ref" aria-label={`Projeto para ${artifact.title || artifact.external_name || 'reunião'}`}><option value="">Vincular ao projeto</option>{(google.projects || []).map(project => <option key={project.id} value={`ci:${project.id}`}>{project.name}</option>)}</select><CaduButton type="submit" size="xs">Vincular</CaduButton></form>}</div></article>)}</div></section>}
    <section className="cadu-ds-account-section"><header><div><span>Ecossistema</span><h2>Conexões do cliente</h2></div><a href={`${bootstrap.urls.solutions.connect}#conectores`}>Ver todas no Connect</a></header><div className="cadu-ds-connector-grid">{connectors.map(connector => <article key={connector.key || connector.name}><i>{connector.name.slice(0, 2).toUpperCase()}</i><span>{connector.scope}</span><h3>{connector.name}</h3><p>{connector.summary}</p>{connector.implemented && connector.key === 'google_drive' ? <a href="#google-workspace">Abrir conexão</a> : <em>Em breve</em>}</article>)}</div><a className="cadu-ds-agent-connect" href={bootstrap.endpoints.agentConnect}>Conectar agentes e MCPs publicáveis →</a></section>
  </div>;
}

function Billing({account, image}) {
  const summary = account.summary || {};
  return <div className="cadu-ds-account-stack"><AccountPageHeader eyebrow="Financeiro da equipe" title="Faturamento" description="Consulte faturas, valores e status de cobrança em um só lugar."/><section className="cadu-ds-account-metrics"><Metric label="Em aberto" value={money(summary.open_total)} detail={`${number(summary.open_count)} faturas`}/><Metric label="Pagas" value={number(summary.paid_count)} detail="no histórico disponível"/><Metric label="Em atraso" value={number(summary.overdue_count)} detail={summary.overdue_count ? 'Requer atenção' : 'Nenhuma pendência vencida'}/></section><section className="cadu-ds-account-section"><header><div><span>Financeiro</span><h2>Histórico de faturas</h2></div></header><DataTable columns={['Fatura', 'Referência', 'Vencimento', 'Status', 'Valor', 'Documento']} empty="Quando houver cobrança registrada, ela aparecerá aqui." rows={(account.invoices || []).map((invoice, index) => <tr key={invoice.id || index}><td><b>{invoice.number}</b></td><td>{invoice.reference || '—'}</td><td>{civilDate(invoice.due_date)}</td><td>{invoiceStatuses[invoice.status_normalized] || invoice.status_normalized}</td><td>{money(invoice.total)}</td><td>{invoice.pdf_safe_url ? <a href={invoice.pdf_safe_url} target="_blank" rel="noreferrer">Abrir PDF</a> : '—'}</td></tr>)}/></section></div>;
}

export function WorkspaceAccount({bootstrap}) {
  const {isMobile} = useWorkspaceViewport();
  const [menuOpen, setMenuOpen] = useState(false);
  const section = bootstrap.section;
  const menuProjects = bootstrap.projects || bootstrap.account.agency_context?.projects || [];
  const menuBrands = bootstrap.brands || bootstrap.account.agency_context?.brands || [];
  const content = section === 'agencia' ? <Agency bootstrap={bootstrap}/> : section === 'perfil' ? <Profile bootstrap={bootstrap}/> : section === 'equipe' ? <Team bootstrap={bootstrap}/> : section === 'integracoes' ? <Integrations bootstrap={bootstrap}/> : section === 'planos' ? <Plan account={bootstrap.account} urls={bootstrap.urls}/> : section === 'uso' ? <Usage account={bootstrap.account} image={bootstrap.caduMark}/> : section === 'creditos' ? <Credits account={bootstrap.account} bootstrap={bootstrap}/> : <Billing account={bootstrap.account} image={bootstrap.caduMark}/>;
  const usagePercent = bootstrap.usagePercent ?? bootstrap.account.position?.usage_percentage ?? 0;
  return <div className="cadu-ds-home-shell cadu-ds-account-shell"><main className="cadu-ds-home-main"><div className="cadu-ds-home-workarea">{isMobile ? <WorkspaceMobileChrome eyebrow="Conta" title={labels[section] || 'Conta'} links={bootstrap.urls}/> : <CaduDock bootstrap={bootstrap} logo={bootstrap.caduMark} homeUrl={bootstrap.urls.home} userName={bootstrap.user.name} userAvatar={bootstrap.user.avatar} userInitials={bootstrap.user.name?.slice(0, 2).toUpperCase()} accountOpen={menuOpen} accountMenu={<WorkspaceAccountMenu open={menuOpen} onClose={() => setMenuOpen(false)} user={bootstrap.user} links={bootstrap.urls} projects={menuProjects} brands={menuBrands} usagePercent={usagePercent} onManageShortcuts={() => window.location.assign(`${bootstrap.urls.home}#atalhos`)}/>} onOpenAccount={() => setMenuOpen(current => !current)} shortcutItems={bootstrap.dock?.items || []} usagePercent={usagePercent} onNewConversation={() => window.location.assign(bootstrap.urls.newConversation)} onOpenBrand={openWorkspaceDetail} onOpenResource={openWorkspaceDetail} onOpenUsage={() => setMenuOpen(true)}/>} {!isMobile && <WorkspaceContextSidebar mode="account" active={section} links={bootstrap.urls}/>}<section className="cadu-ds-account-content"><nav className="cadu-ds-account-tabs" aria-label="Conta">{Object.entries(labels).map(([id, label]) => <a key={id} href={bootstrap.urls[id]} aria-current={id === section ? 'page' : undefined}>{label}</a>)}</nav>{content}</section></div></main><PurchaseModal bootstrap={bootstrap}/></div>;
}
