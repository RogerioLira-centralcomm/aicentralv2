import React, {useEffect, useState} from 'react';
import {WorkspaceContextSidebar} from './WorkspaceContextSidebar';
import {EntityNavigator} from './WorkspaceEntityPortal';
import {Icon} from './Icon';
import {VisualIdentity} from './VisualIdentity';
import {workspaceUserPhoto} from '../workspaceIdentity.mjs';
import {WorkspaceMobileChrome} from './WorkspaceMobileChrome';
import {CaduButton} from './CaduButton';
import {CaduModal} from './CaduModal';
import {CaduTextarea} from './CaduTextarea';
import {CaduInput} from './CaduInput';
import {CaduSelect} from './CaduSelect';
import {CaduConfirmDialog} from './CaduConfirmDialog';
import {useWorkspaceViewport} from '../hooks/useWorkspaceViewport';
import {AgentConnect} from './WorkspaceAgents';
import '../account-pages.css';

const labels = {agencia: 'Agência', equipe: 'Equipe', faturamento: 'Faturamento', integracoes: 'Integrações', planos: 'Plano', perfil: 'Perfil', uso: 'Uso', creditos: 'Tokens'};
const accountIcons = {agencia: 'home', equipe: 'users', faturamento: 'file', integracoes: 'plugin', planos: 'plan', perfil: 'brand', uso: 'analysis', creditos: 'history'};
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
const invoiceStatuses = {paid: 'Paga', overdue: 'Em atraso', pending: 'Pendente', sent: 'Enviada'};
const requestStatuses = {approved: 'Tokens liberados · aguardando lançamento', pending: 'Aguardando confirmação', rejected: 'Recusada'};
const plural = (count, one, many) => Math.abs(Number(count) || 0) === 1 ? one : many;
const tokens = value => `${number(value)} ${plural(value, 'token', 'tokens')}`;
const newIdempotencyKey = () => (globalThis.crypto?.randomUUID ? globalThis.crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`);

function Hidden({name, value}) { return <input type="hidden" name={name} value={value || ''}/>; }
function Metric({label, value, detail, children}) { return <article><span>{label}</span><strong>{value}</strong>{detail && <p>{detail}</p>}{children}</article>; }
function PurchaseModal({bootstrap}) {
  const [order, setOrder] = useState(null); const [billing, setBilling] = useState('prepaid'); const [note, setNote] = useState(''); const [state, setState] = useState(''); const [busy, setBusy] = useState(false); const [done, setDone] = useState(false);
  useEffect(() => { const open = event => { setOrder({...event.detail, key:newIdempotencyKey()}); setBilling('prepaid'); setNote(''); setState(''); setBusy(false); setDone(false); }; window.addEventListener('cadu-open-purchase', open); return () => window.removeEventListener('cadu-open-purchase', open); }, []);
  if (!order) return null;
  const confirm = async () => {
    if (busy || done) return;
    setBusy(true); setState('Registrando o pedido…');
    try {
      const response = await fetch(bootstrap.endpoints.creditRequest, {method:'POST', credentials:'same-origin', headers:{'Content-Type':'application/json','X-CSRF-Token':bootstrap.csrf}, body:JSON.stringify({package_slug:order.slug, package_name:order.name, billing_mode:billing, note, idempotency_key:order.key})});
      const data = await response.json();
      setState(data.message || data.error || 'Não foi possível concluir.');
      if (data.success) { setDone(true); setTimeout(() => window.location.reload(), 1400); } else setBusy(false);
    } catch { setState('Não foi possível concluir o pedido.'); setBusy(false); }
  };
  return <CaduModal className="cadu-ds-purchase-modal__card" titleId="cadu-purchase-title" onClose={() => setOrder(null)}><CaduButton className="cadu-ds-purchase-modal__close" variant="tertiary" size="xs" onClick={() => setOrder(null)} aria-label="Fechar">×</CaduButton><span>Tokens extras</span><h2 id="cadu-purchase-title">Confirmar pacote</h2><div className="cadu-ds-purchase-modal__summary"><strong>{order.name}</strong><b>{money(order.price)}</b><small>{tokens(order.tokens)} · não expiram</small></div><CaduSelect label="Forma de cobrança" value={billing} onChange={event => setBilling(event.target.value)} options={[{value:'prepaid',label:'Pagamento antecipado'},{value:'postpaid',label:'Pós-pago / faturamento financeiro'}]}/><CaduTextarea label="Observação" rows="3" value={note} onChange={event => setNote(event.target.value)} placeholder="Ex.: centro de custo, pedido de compra…"/><p className="cadu-ds-purchase-modal__hint">Os tokens entram na hora no saldo da equipe. O financeiro recebe o pedido e lança a cobrança manualmente; ela aparece em Faturamento.</p><footer><CaduButton variant="secondary" type="button" onClick={() => setOrder(null)}>Voltar</CaduButton><CaduButton type="button" onClick={confirm} loading={busy && !done} disabled={busy || done}>Confirmar compra</CaduButton></footer>{state && <p className="cadu-ds-account-notice" role="status">{state}</p>}</CaduModal>;
}
function AccountPageHeader({title, description, image, initials, photo = false, identity = false}) {
  // The section name is already the active item of the Conta sidebar; the header carries only the subject.
  return <header className="cadu-ds-account-page-header">{(photo || identity) && <VisualIdentity src={image} initials={initials || title} label={title} color="#176b5e" className={photo ? 'is-photo' : ''}/>}<div><h1>{title}</h1><p className="cadu-ds-page-description">{description}</p></div></header>;
}
function CreditSummary({usage, lastInteraction}) {
  const allowance = usage?.allowance || {}; const extras = usage?.extras || {};
  return <section className="cadu-ds-credit-summary" aria-label="Resumo de tokens">
    <div className="cadu-ds-credit-summary__balance"><span>Tokens extras disponíveis</span><strong>{number(extras.available)}</strong><p>{extras.lots ? `${number(extras.lots)} ${plural(extras.lots, 'pacote ativo', 'pacotes ativos')} · extras não expiram` : 'Nenhum pacote extra ativo.'}</p></div>
    <dl><div><dt>Franquia do plano</dt><dd>{allowance.active ? number(allowance.available) : allowance.granted ? number(allowance.granted) : 'Sem franquia'}</dd><small>{allowance.active ? 'disponíveis no ciclo' : allowance.granted ? 'tokens por mês' : ''}{usage?.cycle?.renews_on ? ` · renova em ${civilDate(usage.cycle.renews_on)}` : ''}</small></div><div><dt>Último consumo</dt><dd>{lastInteraction ? tokens(lastInteraction.tokens) : 'Nenhum'}</dd><small>{lastInteraction ? `${lastInteraction.tool} · ${dateTime(lastInteraction.created_at)}` : 'Ainda não há consumo registrado.'}</small></div></dl>
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
    <AccountPageHeader title={org.nome_fantasia || 'O trabalho do cliente'} description="Projetos, marcas e pessoas no mesmo espaço de gestão." identity initials={org.nome_fantasia || org.razao_social || 'AG'}/>
    {admin ? <form className="cadu-ds-account-form" method="post" action={endpoints.updateOrganization}><Hidden name="_csrf" value={csrf}/><CaduInput label="Nome da agência" name="trade_name" defaultValue={org.nome_fantasia || ''} required/><CaduInput label="Razão social" name="legal_name" defaultValue={org.razao_social || ''}/><CaduInput label="CPF ou CNPJ" name="document" defaultValue={org.cnpj || ''}/><CaduInput label="CEP" name="postal_code" defaultValue={org.cep || ''}/><CaduInput label="Logradouro" name="street" defaultValue={org.logradouro || ''}/><CaduInput label="Número" name="number" defaultValue={org.numero || ''}/><CaduInput label="Complemento" name="complement" defaultValue={org.complemento || ''}/><CaduInput label="Bairro" name="district" defaultValue={org.bairro || ''}/><CaduInput label="Cidade" name="city" defaultValue={org.cidade || ''}/><CaduSelect label="Estado" name="state" defaultValue={org.estado_sigla || ''} options={[{value:'', label:'Não informado'}, ...(account.states || []).map(state => ({value:state.sigla, label:`${state.sigla} — ${state.descricao}`}))]}/><footer><span>Esse nome aparece no Workspace e nos contextos da equipe.</span><CaduButton type="submit">Salvar dados da agência</CaduButton></footer></form> : <section className="cadu-ds-account-section"><header><div><h2>{org.nome_fantasia || 'Sua equipe'}</h2></div></header><p className="cadu-ds-account-section-copy">Somente administradores podem alterar os dados da agência. Fale com uma pessoa administradora se precisar ajustar o nome.</p></section>}
    <section className="cadu-ds-account-metrics"><Metric label="Pessoas" value={number(account.people?.length)} detail="com acesso ao Workspace"><a href={urls.team}>Gerenciar equipe</a></Metric><Metric label="Projetos" value={number(projects.length)} detail="contextos ativos"><a href={urls.projects}>Ver projetos</a></Metric><Metric label="Marcas" value={number(brands.length)} detail="identidades disponíveis"><a href={urls.brands}>Ver marcas</a></Metric></section>
    <section className="cadu-ds-account-section"><header><div><h2>Marcas e projetos</h2></div><a href={urls.projects}>Ver projetos</a></header><p className="cadu-ds-account-section-copy">Cada marca reúne os projetos que usam sua identidade e contexto. Projetos sem marca ficam separados.</p><div className="cadu-ds-brand-project-groups">{projectsByBrand.length ? projectsByBrand.map(group => <article key={group.id}><header><VisualIdentity src={group.logoUrl} initials={group.name} label={group.name} color={group.visualColor || '#176b5e'}/><div><b>{group.name}</b><small>{number(group.projects.length)} projeto{group.projects.length === 1 ? '' : 's'}</small></div><a href={group.href || urls.brands}>Abrir marca</a></header><div className="cadu-ds-account-list">{group.projects.length ? group.projects.slice(0, 6).map(project => <a href={project.href} key={project.id}><VisualIdentity src={project.logoUrl} initials={project.name} label={project.name} color={project.visualColor || '#176b5e'}/><div><b>{project.name}</b><small>{number(project.sources)} fontes</small></div><em>{project.status === 'arquivado' ? 'Arquivado' : 'Ativo'}</em></a>) : <p className="cadu-ds-account-empty">Nenhum projeto vinculado a esta marca.</p>}</div></article>) : <p className="cadu-ds-account-empty">Crie o primeiro projeto para formar o contexto do time.</p>}</div></section>
    <section className="cadu-ds-account-section cadu-ds-account-people"><header><div><h2>Pessoas da agência</h2></div><a href={urls.team}>Gerenciar equipe</a></header><p className="cadu-ds-account-section-copy">Pessoas são administradas separadamente dos projetos e das marcas.</p><div className="cadu-ds-account-list">{(account.people || []).length ? account.people.map(person => <article key={person.id_contato_cliente}><i>{(person.nome_completo || '?').slice(0, 1).toUpperCase()}</i><div><b>{person.nome_completo}</b><small>{person.email} · {person.cargo || person.setor || 'Pessoa do time'}</small></div><em>{person.status ? 'Ativo' : 'Inativo'}</em></article>) : <p className="cadu-ds-account-empty">Convide pessoas para trabalhar nos mesmos contextos.</p>}</div></section>
  </div>;
}

function Profile({bootstrap}) {
  const account = bootstrap.account;
  const person = account.current_user || {};
  return <div className="cadu-ds-account-stack">
    <AccountPageHeader title={person.nome_completo || bootstrap.user.name} description="Sua identidade em conversas, decisões e convites." photo image={workspaceUserPhoto(bootstrap.user)} initials={person.nome_completo || bootstrap.user.name}/>
    <form className="cadu-ds-account-form" method="post" action={bootstrap.endpoints.updateProfile}><Hidden name="_csrf" value={bootstrap.csrf}/><Hidden name="avatar_badge" value={person.cadu_avatar_badge || bootstrap.user.avatarBadge}/><CaduInput label="Nome completo" name="name" defaultValue={person.nome_completo || bootstrap.user.name} required/><CaduInput label="E-mail" defaultValue={person.email || bootstrap.user.email} disabled/><CaduInput label="Telefone" name="phone" defaultValue={person.telefone || ''}/><footer><span>Seu e-mail é gerenciado pela identidade de acesso.</span><CaduButton type="submit">Salvar perfil</CaduButton></footer></form>
  </div>;
}

function Team({bootstrap}) {
  const {account, endpoints, csrf, admin} = bootstrap;
  const [pendingForm, setPendingForm] = useState(null);
  const confirmAction = event => {
    event.preventDefault();
    setPendingForm(event.currentTarget);
  };
  const pendingInvites = (account.invites || []).filter(item => item.status === 'pending');
  return <div className="cadu-ds-account-stack">
    <AccountPageHeader title="Pessoas e acessos" description="Convites e permissões da agência."/>
    {admin && <section className="cadu-ds-account-section"><header><div><h2>Convidar para a equipe</h2></div></header><form className="cadu-ds-account-inline-form" method="post" action={endpoints.invite}><Hidden name="_csrf" value={csrf}/><CaduInput label="E-mail" type="email" name="email" required/><CaduSelect label="Acesso" name="role" options={[{value:'member',label:'Membro'},{value:'admin',label:'Administrador'}]}/><CaduButton type="submit">Enviar convite</CaduButton></form></section>}
    <section className="cadu-ds-account-section"><header><div><h2>Pessoas da equipe</h2></div><small>{number(account.people?.length)} {plural(account.people?.length, 'pessoa', 'pessoas')}</small></header><p className="cadu-ds-account-section-copy">Projetos, marcas, plano e tokens são compartilhados por esta equipe.</p><div className="cadu-ds-account-list">{(account.people || []).length ? account.people.map(person => <article key={person.id_contato_cliente}><i>{(person.nome_completo || '?').slice(0, 1).toUpperCase()}</i><div><b>{person.nome_completo}</b><small>{person.email} · {person.cargo || person.setor || 'Equipe da agência'}</small></div><em>{person.status ? 'Ativo' : 'Inativo'}</em>{admin && String(person.id_contato_cliente) !== String(bootstrap.user.id) && <div className="cadu-ds-account-row-actions"><form method="post" action={`${endpoints.memberBase}/${person.id_contato_cliente}/papel`}><Hidden name="_csrf" value={csrf}/><CaduSelect size="sm" aria-label={`Acesso de ${person.nome_completo}`} name="role" defaultValue={['admin', 'superadmin'].includes(person.user_type) ? 'admin' : person.user_type || 'client'} options={[{value:'client',label:'Membro'},{value:'admin',label:'Administrador'},{value:'readonly',label:'Somente leitura'}]}/><CaduButton type="submit" size="xs">Salvar</CaduButton></form><form method="post" action={`${endpoints.memberBase}/${person.id_contato_cliente}/status`} onSubmit={confirmAction}><Hidden name="_csrf" value={csrf}/><CaduButton type="submit" size="xs" variant={person.status ? 'danger' : 'secondary'}>{person.status ? 'Desativar' : 'Reativar'}</CaduButton></form></div>}</article>) : <p className="cadu-ds-account-empty">Convide a primeira pessoa para começar a trabalhar em conjunto.</p>}</div></section>
    <section className="cadu-ds-account-section"><header><div><h2>Convites enviados</h2></div></header><div className="cadu-ds-account-list">{pendingInvites.length ? pendingInvites.map(invite => { const expired = Boolean(invite.expires_at && new Date(invite.expires_at).getTime() < Date.now()); return <article key={invite.id}><i>@</i><div><b>{invite.email}</b><small>{invite.role === 'admin' ? 'Administrador' : 'Membro'} · {expired ? 'expirou em' : 'expira em'} {civilDate(invite.expires_at)}</small></div><em>{expired ? 'Expirado' : 'Pendente'}</em>{admin && <div className="cadu-ds-account-row-actions"><form method="post" action={`${endpoints.inviteBase}/${invite.id}/reenviar`}><Hidden name="_csrf" value={csrf}/><CaduButton type="submit" size="xs" variant="secondary">Reenviar</CaduButton></form><form method="post" action={`${endpoints.inviteBase}/${invite.id}/cancelar`}><Hidden name="_csrf" value={csrf}/><CaduButton type="submit" size="xs" variant="danger">Cancelar</CaduButton></form></div>}</article>; }) : <p className="cadu-ds-account-empty">Nenhum convite aguardando resposta.</p>}</div></section>
    <CaduConfirmDialog open={!!pendingForm} title="Alterar acesso" description="Confirma a alteração de acesso desta pessoa?" confirmLabel="Confirmar" tone="danger" onCancel={() => setPendingForm(null)} onConfirm={() => { const form = pendingForm; setPendingForm(null); form?.submit(); }}/>
  </div>;
}

const PLAN_FAQ = [
  ['O que é a franquia do plano?', 'É a quantidade de tokens incluída na mensalidade. Ela é liberada automaticamente no início de cada ciclo e é usada antes dos tokens extras.'],
  ['O que acontece com os tokens da franquia que não usei?', 'Como num plano de celular, a sobra da franquia expira quando a franquia do ciclo seguinte é liberada.'],
  ['Os tokens extras expiram?', 'Não. Pacotes extras ficam no saldo até serem usados e entram depois da franquia do plano.'],
  ['Quantas pessoas podem usar?', 'Todos os planos têm pessoas ilimitadas. Projetos e marcas também são ilimitados.'],
];
function Plan({account, urls}) {
  const plans = account.plans || [];
  const packages = account.packages || [];
  const storage = account.storage_packages || [];
  const current = plans.find(plan => plan.current);
  const usage = account.insights?.tokens || {};
  const contact = 'mailto:financeiro@centralcomm.media?subject=' + encodeURIComponent('Plano Cadu');
  const price = plan => plan.price_monthly == null ? 'Consulte' : Number(plan.price_monthly) > 0 ? money(plan.price_monthly) : 'Grátis';
  const allowance = plan => plan.tokens_monthly ? `${tokens(plan.tokens_monthly)} / mês` : 'Consulte';
  const storageLabel = plan => plan.storage_gb ? `${number(plan.storage_gb)} GB` : 'Consulte';
  const cta = plan => plan.current ? <CaduButton variant="secondary" disabled>Plano atual</CaduButton> : plan.cta === 'checkout' ? <CaduButton href="/assinatura/checkout">Contratar</CaduButton> : <CaduButton variant={plan.highlight ? 'primary' : 'secondary'} href={`${contact}%20${encodeURIComponent(plan.name)}`}>Falar com a equipe</CaduButton>;
  const choosePackage = pack => window.dispatchEvent(new CustomEvent('cadu-open-purchase', {detail:{slug:pack.slug, name:pack.name, tokens:pack.tokens, price:pack.price_brl}}));
  return <div className="cadu-ds-account-stack cadu-ds-pricing-page">
    <AccountPageHeader title="Planos do Cadu" description={current ? `Seu plano atual é ${current.name}. Todos os planos têm pessoas ilimitadas; a franquia de tokens renova a cada ciclo.` : 'Todos os planos têm pessoas ilimitadas; a franquia de tokens renova a cada ciclo.'}/>
    {current && <section className="cadu-ds-account-metrics"><Metric label="Plano atual" value={current.name} detail={price(current) + (Number(current.price_monthly) > 0 ? ' / mês' : '')}/><Metric label="Franquia do ciclo" value={usage.limit ? number(usage.used) : 'Consulte'} detail={usage.limit ? `de ${tokens(usage.limit)} usados neste ciclo` : 'franquia ainda não definida'}>{usage.limit ? <progress value={usage.percentage || 0} max="100"/> : null}</Metric><Metric label="Pessoas" value="Ilimitadas" detail="sem custo por pessoa"/></section>}
    {plans.length ? <>
      <section className="cadu-ds-pricing-cards" style={{'--plan-count': plans.length}} aria-label="Planos disponíveis">{plans.map(plan => <article className={`cadu-ds-pricing-card${plan.current ? ' is-current' : ''}${plan.highlight ? ' is-highlight' : ''}`} key={plan.slug || plan.name}>
        {plan.current ? <span className="cadu-ds-pricing-badge">Seu plano</span> : plan.highlight ? <span className="cadu-ds-pricing-badge">Mais escolhido</span> : <span className="cadu-ds-pricing-badge is-empty" aria-hidden="true"/>}
        <h2>{plan.name}</h2>{plan.tagline && <p className="cadu-ds-pricing-description">{plan.tagline}</p>}
        <div className="cadu-ds-pricing-price"><strong>{price(plan)}</strong>{Number(plan.price_monthly) > 0 && <span>/ mês</span>}</div>
        <ul><li>{plan.tokens_monthly ? `${tokens(plan.tokens_monthly)} por mês` : 'Franquia de tokens: consulte'}</li><li>Pessoas ilimitadas</li><li>{plan.storage_gb ? `${number(plan.storage_gb)} GB de armazenamento` : 'Armazenamento: consulte'}</li>{(plan.features || []).map(feature => <li key={feature}>{feature}</li>)}</ul>
        <div className="cadu-ds-pricing-cta">{cta(plan)}</div>
      </article>)}</section>
      <section className="cadu-ds-account-section cadu-ds-pricing-comparison"><header><div><h2>Comparativo</h2></div></header><div className="cadu-ds-account-table"><table><thead><tr><th scope="col">Incluído</th>{plans.map(plan => <th scope="col" key={plan.slug || plan.name}>{plan.name}</th>)}</tr></thead><tbody>
        <tr><th scope="row">Preço mensal</th>{plans.map(plan => <td key={plan.slug}>{price(plan)}</td>)}</tr>
        <tr><th scope="row">Franquia de tokens</th>{plans.map(plan => <td key={plan.slug}>{allowance(plan)}</td>)}</tr>
        <tr><th scope="row">Pessoas</th>{plans.map(plan => <td key={plan.slug}>Ilimitadas</td>)}</tr>
        <tr><th scope="row">Armazenamento incluído</th>{plans.map(plan => <td key={plan.slug}>{storageLabel(plan)}</td>)}</tr>
        <tr><th scope="row">Projetos e marcas</th>{plans.map(plan => <td key={plan.slug}>Ilimitados</td>)}</tr>
      </tbody></table></div></section>
    </> : <section className="cadu-ds-account-section"><header><div><h2>Planos em preparação</h2></div></header><p className="cadu-ds-account-empty">Os planos ainda não foram publicados para esta conta. <a href={contact}>Fale com a equipe</a> para conhecer as opções.</p></section>}
    <section className="cadu-ds-account-section"><header><div><h2>Tokens extras</h2></div><small>Não expiram</small></header><p className="cadu-ds-account-section-copy">Quando a franquia do ciclo acabar, o Cadu continua usando os tokens extras da equipe.</p>{packages.length ? <PackageTable packages={packages} onChoose={choosePackage}/> : <p className="cadu-ds-account-empty">Nenhum pacote disponível agora. Fale com a equipe.</p>}</section>
    <section className="cadu-ds-account-section"><header><div><h2>Armazenamento extra</h2></div></header>{storage.length ? <DataTable columns={['Pacote', 'Espaço', 'Preço']} rows={storage.map(item => <tr key={item.slug}><td><b>{item.name}</b></td><td>{number(item.gb)} GB</td><td>{item.price_brl ? money(item.price_brl) + ' / mês' : 'Consulte'}</td></tr>)}/> : <p className="cadu-ds-account-empty">Precisa de mais espaço para arquivos? <a href={contact}>Consulte a equipe</a> sobre GB adicionais.</p>}</section>
    <section className="cadu-ds-account-section cadu-ds-pricing-faq"><header><div><h2>Perguntas frequentes</h2></div></header><dl>{PLAN_FAQ.map(([question, answer]) => <div key={question}><dt>{question}</dt><dd>{answer}</dd></div>)}</dl></section>
  </div>;
}
function PackageTable({packages, onChoose}) {
  return <DataTable columns={['Pacote', 'Volume', 'Indicado para', 'Preço', '']} rows={packages.map(pack => <tr key={pack.slug}><td><b>{pack.name}</b></td><td>{tokens(pack.tokens)}</td><td>{pack.description || '—'}</td><td>{money(pack.price_brl)}</td><td className="cadu-ds-account-table__action"><CaduButton size="sm" type="button" onClick={() => onChoose(pack)}>Comprar</CaduButton></td></tr>)}/>;
}

function Usage({account}) {
  const usage = account.usage || {};
  const allowance = usage.allowance || {}; const extras = usage.extras || {};
  const interactions = account.interactions || [];
  const space = account.space || {};
  const mb = new Intl.NumberFormat('pt-BR', {maximumFractionDigits:1}).format(Number(space.bytes_used || 0) / 1048576);
  const renews = usage.cycle?.renews_on ? civilDate(usage.cycle.renews_on) : null;
  return <div className="cadu-ds-account-stack"><AccountPageHeader title="Consumo e espaço" description="Tokens usados neste ciclo, saldo extra e espaço ocupado pela equipe."/>
    <section className="cadu-ds-usage-blocks" aria-label="Saldo de tokens">
      <article className="cadu-ds-account-section"><header><div><h2>Franquia do plano</h2></div>{renews && <small>Renova em {renews}</small>}</header><div className="cadu-ds-usage-block">{allowance.granted ? <><strong>{number(allowance.used)} <span>de {tokens(allowance.granted)}</span></strong><progress value={allowance.percentage || 0} max="100" aria-label="Uso da franquia"/><p>{allowance.active ? `${tokens(allowance.available)} disponíveis neste ciclo. A sobra expira na renovação.` : 'Consumo do ciclo comparado à franquia do plano. A liberação automática da franquia ainda não está ativa nesta conta; o consumo é debitado do saldo de tokens.'}</p></> : <><strong>{tokens(usage.cycle_tokens)} <span>neste ciclo</span></strong><p>Seu plano não tem franquia mensal configurada.</p></>}</div></article>
      <article className="cadu-ds-account-section"><header><div><h2>Tokens extras</h2></div><small>Não expiram</small></header><div className="cadu-ds-usage-block"><strong>{number(extras.available)} <span>{plural(extras.available, 'token disponível', 'tokens disponíveis')}</span></strong><p>{extras.lots ? `${number(extras.lots)} ${plural(extras.lots, 'pacote ativo', 'pacotes ativos')}. Usados depois da franquia do plano.` : 'Nenhum pacote extra ativo.'}</p></div></article>
    </section>
    <section className="cadu-ds-account-section"><header><div><h2>Consumo por ferramenta</h2></div><small>Ciclo atual</small></header><DataTable columns={['Ferramenta', 'Interações', 'Tokens']} empty="Ainda não há consumo neste ciclo." rows={(usage.by_tool || []).map(item => <tr key={item.tool}><td><b>{item.tool}</b></td><td>{number(item.interactions)}</td><td>{number(item.tokens)}</td></tr>)}/></section>
    <section className="cadu-ds-account-section"><header><div><h2>Último consumo</h2></div><small>Agrupado por interação</small></header><DataTable columns={['Ferramenta', 'Quando', 'Etapas', 'Tokens']} empty="Ainda não há consumo de IA registrado." rows={interactions.map((item, index) => <tr key={`${item.created_at}-${index}`}><td><b>{item.tool}</b></td><td>{dateTime(item.created_at)}</td><td>{number(item.steps)}</td><td>{number(item.tokens)}</td></tr>)}/></section>
    <section className="cadu-ds-account-section"><header><div><h2>Projetos, marcas e arquivos</h2></div><small>Projetos e marcas ilimitados</small></header><DataTable columns={['Recurso', 'Quantidade / uso', 'Regra']} rows={[<tr key="projects"><td><b>Projetos</b></td><td>{number(space.projects)}</td><td>Ilimitados</td></tr>,<tr key="brands"><td><b>Marcas</b></td><td>{number(account.agency_context?.brands?.length)}</td><td>Ilimitadas</td></tr>,<tr key="files"><td><b>Arquivos indexados</b></td><td>{number(space.files)} · {mb} MB</td><td>Espaço medido por equipe</td></tr>]}/></section>
  </div>;
}

function Credits({account}) {
  const packages = account.packages || [];
  const lots = account.purchases || [];
  const requests = account.credit_requests || [];
  const choosePackage = pack => window.dispatchEvent(new CustomEvent('cadu-open-purchase', {detail:{slug:pack.slug, name:pack.name, tokens:pack.tokens, price:pack.price_brl}}));
  return <div className="cadu-ds-account-stack"><AccountPageHeader title="Tokens da equipe" description="A franquia do plano é usada primeiro. Quando precisar de mais, compre tokens extras: entram na hora e não expiram."/>
    <CreditSummary usage={account.usage} lastInteraction={account.interactions?.[0]}/>
    <section className="cadu-ds-account-section"><header><div><h2>Comprar tokens extras</h2></div><small>Liberação imediata</small></header><p className="cadu-ds-account-section-copy">Qualquer pessoa da equipe pode comprar. O financeiro recebe o pedido e lança a cobrança.</p>{packages.length ? <PackageTable packages={packages} onChoose={choosePackage}/> : <p className="cadu-ds-account-empty">Nenhum pacote disponível agora.</p>}</section>
    <section className="cadu-ds-account-section"><header><div><h2>Saldo por lote</h2></div></header><DataTable columns={['Origem', 'Vencimento', 'Disponível', 'Total']} empty="Você está usando a franquia do plano. Compre um pacote quando precisar de mais." rows={lots.map((lot, index) => <tr key={lot.id || index}><td><b>{lot.package_name}</b></td><td>{lot.expires_at ? civilDate(lot.expires_at) : 'Não expira'}</td><td>{number(lot.available)}</td><td>{number(lot.credits)}</td></tr>)}/></section>
    {requests.length > 0 && <section className="cadu-ds-account-section"><header><div><h2>Pedidos recentes</h2></div></header><RequestTable requests={requests.slice(0, 5)}/></section>}
  </div>;
}
function RequestTable({requests}) {
  return <DataTable columns={['Pedido', 'Pacote', 'Data', 'Cobrança', 'Valor', 'Situação']} rows={requests.map(item => <tr key={item.id}><td><b>#{item.id}</b></td><td>{item.package_name} · {tokens(item.tokens_amount)}</td><td>{civilDate(item.created_at)}</td><td>{item.billing_mode === 'postpaid' ? 'Pós-pago' : 'Antecipado'}</td><td>{money(item.price_brl)}</td><td>{requestStatuses[item.status] || item.status}</td></tr>)}/>;
}

function Integrations({bootstrap}) {
  const data = bootstrap.account.integrations || {};
  const google = data.google || {};
  const connection = google.connection;
  const googleOn = google.enabled === true;
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
    <AccountPageHeader title="Fontes conectadas ao trabalho" description="Arquivos, reuniões, relatórios e agentes disponíveis para os projetos."/>
    {googleOn && <>
    <section className="cadu-ds-integration-hero" id="google-workspace"><div><span>Google Workspace · {bootstrap.account?.organization?.nome_fantasia || bootstrap.contextName || 'Cliente atual'}</span><h2>{connection?.google_email || 'Conecte sua conta Google'}</h2><p>{connection?.google_domain || 'Cada pessoa autoriza a própria conta neste cliente. Arquivos e reuniões disponíveis para a equipe aparecem como fontes escolhidas.'}</p></div><em className={connectionHealthy ? 'is-connected' : connection ? 'needs-attention' : ''}>{status}</em><div className="cadu-ds-integration-actions">{connection ? <><CaduButton type="button" variant="secondary" onClick={() => post(bootstrap.endpoints.googleSync)}>Atualizar dados</CaduButton><a href={google.connect_url}>Trocar conta</a><CaduButton type="button" variant="danger" onClick={() => post(bootstrap.endpoints.googleDisconnect)}>Desconectar minha conta</CaduButton></> : <a className="is-primary" href={google.connect_url}>Conectar minha conta</a>}</div></section>
    {message && <p className="cadu-ds-account-notice" role="status">{message}</p>}
    <section className="cadu-ds-account-section"><header><div><h2>O que pode entrar nos projetos</h2></div><small>{number(google.summary?.enabled_count)} ativos</small></header><div className="cadu-ds-integration-services">{(google.services || []).map(service => <article key={service.key}><i>{service.name?.slice(0, 2).toUpperCase()}</i><div><b>{service.name}</b><small>{service.description}</small></div><em>{service.status_label}</em></article>)}</div></section>
    <section className="cadu-ds-account-section"><header><div><h2>Pessoas que conectaram neste cliente</h2></div><small>{number(google.authorizations?.length)} contas</small></header><div className="cadu-ds-integration-services">{(google.authorizations || []).map(authorization => <article key={authorization.id}><i>{String(authorization.user_name || authorization.user_email || '?').slice(0, 2).toUpperCase()}</i><div><b>{authorization.user_name || authorization.user_email || 'Pessoa da equipe'}</b><small>{authorization.google_email}{authorization.last_sync_at ? ` · atualizada ${dateTime(authorization.last_sync_at)}` : ''}</small></div><em>{authorization.status === 'connected' ? 'Conectada' : 'Requer atenção'}</em></article>)}{!(google.authorizations || []).length && <p className="cadu-ds-account-empty">Ainda não há contas Google conectadas neste cliente.</p>}</div></section>
    </>}
    <section className="cadu-ds-account-section"><header><div><h2>Dados disponíveis para este cliente</h2></div><small>{number(data.connected_count)} ativas</small></header><div className="cadu-ds-integration-services">{(data.accounts || []).map(account => <article key={account.id || `${account.provider}-${account.external_account_id || account.name}`}><i>{(account.provider_label || account.provider || 'IN').slice(0, 2).toUpperCase()}</i><div><b>{account.name || account.provider_label}</b><small>{account.provider_label || 'Integração'}{account.last_synced_at ? ` · atualizada ${dateTime(account.last_synced_at)}` : ''}</small></div><em>{['active','connected','ready'].includes(account.status) ? 'Ativa' : account.status || 'Pendente'}</em></article>)}{!(data.accounts || []).length && <p className="cadu-ds-account-empty">Nenhuma conta de mídia ou relatório foi autorizada ainda.</p>}</div></section>
    {googleOn && connection && <section className="cadu-ds-account-section"><header><div><h2>Arquivos e reuniões</h2></div><small>{number((google.resources || []).length + (google.meet_artifacts || []).length)} itens</small></header><div className="cadu-ds-integration-resources">{(google.resources || []).slice(0, 24).map(resource => <article key={resource.id}><VisualIdentity src={resource.presentation?.thumbnail_url} initials={resource.name} label={resource.name} color="#176b5e"/><div><b>{resource.name}</b><small>{resource.presentation?.product || 'Google Workspace'} · {resource.presentation?.kind || 'Arquivo'}{resource.external_url && <> · <a href={resource.external_url} target="_blank" rel="noreferrer">Abrir</a></>}</small></div><form onSubmit={event => linkResource(event, resource.id)}><CaduSelect size="sm" name="project_ref" aria-label={`Projeto para ${resource.name}`} options={[{value:'',label:'Escolher projeto'}, ...(google.projects || []).map(project => ({value:`ci:${project.id}`, label:project.name}))]}/><CaduButton type="submit" size="xs">Adicionar</CaduButton></form></article>)}{!(google.resources || []).length && <p className="cadu-ds-account-empty">Nenhum arquivo encontrado. Atualize a conexão para procurar novamente.</p>}</div></section>}
    {googleOn && connection && (google.meet_artifacts || []).length > 0 && <section className="cadu-ds-account-section"><header><div><h2>Reuniões encontradas</h2></div><small>{number(google.meet_artifacts.length)} registros</small></header><div className="cadu-ds-integration-resources">{google.meet_artifacts.slice(0, 24).map(artifact => <article key={artifact.id}><VisualIdentity initials="ME" label={artifact.title || artifact.external_name || 'Reunião'} color="#176b5e"/><div><b>{artifact.title || artifact.external_name || 'Reunião'}</b><small>{artifact.artifact_type || 'Registro'}{artifact.conference_record ? ` · ${artifact.conference_record}` : ''}</small></div><div className="cadu-ds-integration-resource-actions">{artifact.artifact_type === 'transcript' && !artifact.content ? <CaduButton type="button" variant="secondary" onClick={() => fetchMeetArtifact(artifact.id)}>Preparar para revisão</CaduButton> : <em>{artifact.content ? 'Pronta para revisão' : 'Informações disponíveis'}</em>}{artifact.resource_id && <form onSubmit={event => linkResource(event, artifact.resource_id)}><CaduSelect size="sm" name="project_ref" aria-label={`Projeto para ${artifact.title || artifact.external_name || 'reunião'}`} options={[{value:'',label:'Vincular ao projeto'}, ...(google.projects || []).map(project => ({value:`ci:${project.id}`, label:project.name}))]}/><CaduButton type="submit" size="xs">Vincular</CaduButton></form>}</div></article>)}</div></section>}
    <section className="cadu-ds-account-section"><header><div><h2>Conexões do cliente</h2></div><a href={`${bootstrap.urls.solutions.connect}#conectores`}>Ver todas no Connect</a></header><div className="cadu-ds-connector-grid">{connectors.map(connector => <article key={connector.key || connector.name}><i>{connector.name.slice(0, 2).toUpperCase()}</i><span>{connector.scope}</span><h3>{connector.name}</h3><p>{connector.summary}</p>{googleOn && connector.implemented && connector.key === 'google_drive' ? <a href="#google-workspace">Abrir conexão</a> : <em>Em breve</em>}</article>)}</div></section>
    <AgentConnect bootstrap={bootstrap}/>
  </div>;
}

function Billing({account}) {
  const summary = account.summary || {};
  const requests = account.credit_requests || [];
  return <div className="cadu-ds-account-stack"><AccountPageHeader title="Faturamento" description="Faturas lançadas pelo financeiro e solicitações de pacotes de tokens."/>
    <section className="cadu-ds-account-section"><header><div><h2>Como funciona a cobrança</h2></div></header><p className="cadu-ds-account-section-copy cadu-ds-billing-note">Ainda não há cobrança automática. Quando alguém da equipe compra tokens extras, os tokens são liberados na hora e o pedido vai para o financeiro, que lança a fatura manualmente. A fatura aparece no histórico abaixo depois desse lançamento. Dúvidas: <a href="mailto:financeiro@centralcomm.media">financeiro@centralcomm.media</a>.</p></section>
    <section className="cadu-ds-account-metrics"><Metric label="Em aberto" value={money(summary.open_total)} detail={`${number(summary.open_count)} ${plural(summary.open_count, 'fatura', 'faturas')}`}/><Metric label="Pagas" value={number(summary.paid_count)} detail="no histórico disponível"/><Metric label="Solicitações de pacote" value={number(requests.length)} detail="aguardando ou já lançadas pelo financeiro"/></section>
    <section className="cadu-ds-account-section"><header><div><h2>Solicitações de pacote</h2></div><small>Não são faturas</small></header><RequestTableOrEmpty requests={requests}/></section>
    <section className="cadu-ds-account-section"><header><div><h2>Histórico de faturas</h2></div></header><DataTable columns={['Fatura', 'Referência', 'Vencimento', 'Status', 'Valor', 'Documento']} empty="Nenhuma fatura lançada ainda. Elas aparecem aqui quando o financeiro registra a cobrança." rows={(account.invoices || []).map((invoice, index) => <tr key={invoice.id || index}><td><b>{invoice.number}</b></td><td>{invoice.reference || '—'}</td><td>{civilDate(invoice.due_date)}</td><td>{invoiceStatuses[invoice.status_normalized] || invoice.status_normalized}</td><td>{money(invoice.total)}</td><td>{invoice.pdf_safe_url ? <a href={invoice.pdf_safe_url} target="_blank" rel="noreferrer">Abrir PDF</a> : '—'}</td></tr>)}/></section>
  </div>;
}
function RequestTableOrEmpty({requests}) {
  return requests.length ? <RequestTable requests={requests}/> : <p className="cadu-ds-account-empty">Nenhuma solicitação de pacote. Compras feitas em Tokens aparecem aqui.</p>;
}

export function WorkspaceAccount({bootstrap}) {
  const {isMobile} = useWorkspaceViewport();
  const section = bootstrap.section;
  const content = section === 'agencia' ? <Agency bootstrap={bootstrap}/> : section === 'perfil' ? <Profile bootstrap={bootstrap}/> : section === 'equipe' ? <Team bootstrap={bootstrap}/> : section === 'integracoes' ? <Integrations bootstrap={bootstrap}/> : section === 'planos' ? <Plan account={bootstrap.account} urls={bootstrap.urls}/> : section === 'uso' ? <Usage account={bootstrap.account}/> : section === 'creditos' ? <Credits account={bootstrap.account}/> : <Billing account={bootstrap.account}/>;
  const order = ['perfil', 'agencia', 'equipe', 'integracoes', 'planos', 'uso', 'creditos', 'faturamento'];
  const navItems = [...order.filter(id => bootstrap.urls[id]).map(id => ({id, label: labels[id], icon: accountIcons[id], href: bootstrap.urls[id]})),
    ...(bootstrap.urls.observability ? [{id: 'observabilidade', label: 'Observabilidade do Cadu', icon: 'analysis', href: bootstrap.urls.observability}] : [])];
  const agencyName = bootstrap.contextName || 'Conta';
  // Same structure as Project detail: closed Workspace rail plus the section's own sidebar, open.
  return <div className="cadu-ds-home-shell cadu-ds-account-shell"><main className="cadu-ds-home-main"><div className="cadu-ds-home-workarea cadu-ds-account-workarea">
    {isMobile ? <WorkspaceMobileChrome eyebrow="Conta" title={labels[section] || 'Conta'} links={bootstrap.urls} logo={bootstrap.caduMark} solutionIcons={bootstrap.solutionIcons} accountItems={navItems.map(item => ({...item, name: item.label, active: item.id === section}))}/> : <WorkspaceContextSidebar mode="home" rail bootstrap={bootstrap} active="conta" links={bootstrap.urls}/>}
    <div className="cadu-ds-entity-portal cadu-ds-entity-portal--account">
      {!isMobile && <EntityNavigator label="Conta" items={navItems} activeId={section} identity={<span><b title={agencyName}>Conta</b></span>}/>}
      <section className="cadu-ds-account-content">{content}</section>
    </div>
  </div></main><PurchaseModal bootstrap={bootstrap}/></div>;
}
