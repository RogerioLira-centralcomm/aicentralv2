import React, {useState} from 'react';
import {AlertTriangle, ArrowUpRight, CheckCircle, ChevronRight, Code01, Copy01, Download01, GitBranch01, SearchLg, Send01, ShieldTick, BarChart01, Plus, RefreshCw01, Users01} from '@untitledui/icons';
import {ReportsActionButton} from './ReportsActionButton.jsx';
import {ReportsFieldInput} from './ReportsFieldInput.jsx';
import {ReportsTabs} from './ReportsTabs.jsx';
import {ReportsRelationships} from './ReportsRelationships.jsx';
import {integer, reportUrl} from './reportsCommon.jsx';

const EVENT_LABELS = {
  page_view: 'Visualização de página', page_leave: 'Saída de página', click: 'Clique', whatsapp_click: 'Clique no WhatsApp',
  form_submit: 'Envio de formulário', visibility: 'Elemento visível', scroll_depth: 'Rolagem', custom_event: 'Evento personalizado',
  conversion: 'Conversão', heartbeat: 'Tempo ativo',
};

export function relativeTime(value) {
  if (!value) return null;
  const seconds = Math.max(0, Math.round((Date.now() - new Date(value).getTime()) / 1000));
  if (seconds < 90) return 'agora há pouco';
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `há ${minutes} min`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `há ${hours} h`;
  return `há ${Math.round(hours / 24)} dias`;
}

const longDate = value => value ? new Date(value).toLocaleDateString('pt-BR', {day: 'numeric', month: 'short', year: 'numeric'}) : '—';

/** One word for where a site stands, shared by the list, the header and the install checks. */
export function siteState(site) {
  if (site.revoked_at) return {tone: 'error', label: 'Revogada'};
  if (!site.enabled) return {tone: 'gray', label: 'Desativada'};
  if (Number(site.events_30d) > 0) return {tone: 'success', label: 'Coleta ativa'};
  if (site.last_event_at) return {tone: 'warning', label: 'Coleta sem eventos recentes'};
  return {tone: 'gray', label: 'Nunca recebeu eventos'};
}

export function StatusBadge({tone = 'gray', children}) {
  return <span className={`st-badge st-badge--${tone}`}><i aria-hidden="true"/>{children}</span>;
}

export function SiteSidebar({sites, loading, query, onQuery, selectedId, clientId, onAdd, canAdd, renderFavicon}) {
  const visible = sites.filter(site => `${site.label} ${site.allowed_host}`.toLowerCase().includes(query.toLowerCase()));
  const groups = [
    {id: 'active', label: 'Coleta ativa', items: visible.filter(site => siteState(site).tone === 'success')},
    {id: 'other', label: 'Precisam de atenção', items: visible.filter(site => siteState(site).tone !== 'success')},
  ].filter(group => group.items.length);
  const showLabels = groups.length > 1;
  return <aside className="st-sites" aria-label="Sites de medição">
    <header><div><h2>Sites</h2><p>{sites.length} {sites.length === 1 ? 'site conectado' : 'sites conectados'}</p></div></header>
    <label className="st-search"><ReportsFieldInput leading={<SearchLg size={16} aria-hidden="true" className="ml-3 shrink-0 text-fg-quaternary"/>} aria-label="Buscar site" placeholder="Buscar site…" value={query} onChange={event => onQuery(event.target.value)}/></label>
    <nav aria-label="Lista de sites">
      {loading && <p className="st-muted" role="status">Carregando sites…</p>}
      {!loading && groups.map(group => <div className="st-group" key={group.id}>
        {showLabels && <h3>{group.label}</h3>}
        {group.items.map(site => {
          const state = siteState(site);
          const active = site.id === selectedId;
          return <a key={site.id} className={`st-site${active ? ' is-active' : ''}`} href={reportUrl('supertag', {client_id: clientId}, site.id)} aria-current={active ? 'page' : undefined}>
            <span className="st-avatar">{renderFavicon(site)}</span>
            <span className="st-site__text"><strong>{site.allowed_host}</strong><small className={`st-dot st-dot--${state.tone}`}><i aria-hidden="true"/>{state.label}</small></span>
            <span className="st-site__count" title="Eventos nos últimos 30 dias">{integer(site.events_30d || 0)}</span>
          </a>;
        })}
      </div>)}
      {!loading && sites.length > 0 && !visible.length && <p className="st-muted">Nenhum site corresponde à busca.</p>}
    </nav>
    {canAdd && <ReportsActionButton className="st-add" color="secondary" iconLeading={Plus} onClick={onAdd}>Adicionar site</ReportsActionButton>}
  </aside>;
}

export function SiteSummary({site, flowsCount, hasEvents, renderFavicon}) {
  const state = siteState(site);
  const events = Number(site.events_30d || 0);
  const last = site.last_event_at;
  const metrics = [
    {label: 'Eventos · 30 dias', value: integer(events), hint: hasEvents ? 'Eventos aceitos pelo coletor' : 'Nenhum evento consentido'},
    {label: 'Último evento', value: last ? relativeTime(last) : 'Nenhum ainda', hint: last ? longDate(last) : 'Aguardando a primeira visita'},
    {label: 'Fluxos vinculados', value: flowsCount == null ? '—' : integer(flowsCount), hint: 'Usam os dados deste site'},
    {label: 'Instalação', value: hasEvents ? 'Verificada' : 'Pendente', hint: hasEvents ? 'Confirmada pelos eventos' : 'Verifique o código no site'},
  ];
  return <header className="st-summary">
    <div className="st-summary__top">
      <div className="st-summary__identity"><span className="st-avatar st-avatar--lg">{renderFavicon(site)}</span>
        <div><div className="st-summary__title"><h2>{site.allowed_host}</h2><StatusBadge tone={state.tone}>{state.label}</StatusBadge></div><p>{site.label}</p></div></div>
      <div className="st-summary__actions"><ReportsActionButton color="secondary" iconTrailing={ArrowUpRight} href={`https://${site.allowed_host}`} target="_blank" rel="noopener noreferrer">Visitar site</ReportsActionButton></div>
    </div>
    <dl className="st-summary__metrics">{metrics.map(item => <div key={item.label}><dt>{item.label}</dt><dd>{item.value}</dd><small>{item.hint}</small></div>)}</dl>
  </header>;
}

function checkRows({site, verify, hasEvents}) {
  const events = Number(site.events_30d || 0);
  let code = {tone: 'warning', label: 'Verificação pendente'};
  if (hasEvents) code = {tone: 'success', label: 'Confirmado pelos eventos'};
  else if (verify?.tag_in_html) code = {tone: 'success', label: 'Encontrado no site'};
  else if (verify && !verify.reachable) code = {tone: 'error', label: 'O site não respondeu'};
  else if (verify?.gtm_detected) code = {tone: 'warning', label: 'GTM detectado · confirme no contêiner'};
  else if (verify) code = {tone: 'error', label: 'Não encontrado no HTML'};
  const consent = hasEvents ? {tone: 'success', label: 'Coleta autorizada'} : {tone: 'error', label: 'Sem evidência recente'};
  const receiving = hasEvents ? {tone: 'success', label: `${integer(events)} eventos`} : {tone: 'error', label: 'Nenhum evento no período'};
  return [
    {id: 'code', icon: Code01, title: 'Código instalado', hint: hasEvents ? 'O código está implementado no site.' : 'Verifique se o código da Super Tag está presente no seu site.', ...code, doneTitle: 'Instalado', doneHint: 'Código implementado no site'},
    {id: 'consent', icon: ShieldTick, title: 'Consentimento', hint: 'Confirme se o consentimento de cookies está sendo coletado corretamente.', ...consent, doneTitle: 'Consentimento ativo', doneHint: 'Coleta autorizada pelos usuários'},
    {id: 'receiving', icon: BarChart01, title: 'Recebimento', hint: 'Aguarde a chegada dos eventos após a validação dos itens acima.', ...receiving, doneTitle: 'Eventos recebidos', doneHint: 'Dados sendo coletados normalmente'},
  ];
}

/** Two stages of the same panel: a stepper once data flows, a verification checklist before that. */
export function InstallStatus({site, hasEvents, verify, verifying, onVerify, onCopy, onGuide}) {
  const rows = checkRows({site, verify, hasEvents});
  if (hasEvents) return <section className="st-card st-stages" aria-label="Status da instalação">
    <h3>Status da instalação</h3>
    <ol>{rows.map(row => <li key={row.id}><span className="st-stage-mark"><CheckCircle size={20} aria-hidden="true"/></span><strong>{row.doneTitle}</strong><small>{row.doneHint}</small></li>)}</ol>
  </section>;
  return <section className="st-card st-verify" aria-label="Verificação da instalação">
    <header><span className="st-verify__alert"><AlertTriangle size={22} aria-hidden="true"/></span><div><h3>Coleta precisa de verificação</h3><p>Nenhum evento consentido foi recebido neste período. Isso não confirma falha na instalação.</p></div></header>
    <ul>{rows.map(row => <li key={row.id}><span className="st-verify__icon"><row.icon size={20} aria-hidden="true"/></span><div><strong>{row.title}</strong><small>{row.hint}</small></div><StatusBadge tone={row.tone}>{row.label}</StatusBadge></li>)}</ul>
    <footer>
      <ReportsActionButton color="primary" iconLeading={RefreshCw01} onClick={onVerify} disabled={verifying}>{verifying ? 'Verificando…' : 'Verificar instalação'}</ReportsActionButton>
      <ReportsActionButton color="secondary" iconLeading={Copy01} onClick={onCopy}>Copiar código</ReportsActionButton>
      <ReportsActionButton color="link-color" iconTrailing={ChevronRight} onClick={onGuide}>Ver como instalar</ReportsActionButton>
    </footer>
    {verify && !verify.tag_in_html && verify.reachable && <p className="st-verify__note">Se a tag foi instalada pelo Google Tag Manager, ela não aparece no HTML. Abra o site com o modo Visualizar do GTM para confirmar.</p>}
  </section>;
}

export function InstallGuide() {
  const [method, setMethod] = useState('html');
  return <section className="st-card st-guide"><header><div><h3>Onde instalar</h3><p>Uma vez só, em todas as páginas do site.</p></div></header>
    <div className="st-segmented" role="group" aria-label="Forma de instalação">{[['html', 'No site'], ['gtm', 'Google Tag Manager'], ['cms', 'WordPress']].map(([id, label]) => <button key={id} type="button" className={method === id ? 'is-active' : ''} aria-pressed={method === id} onClick={() => setMethod(id)}>{label}</button>)}</div>
    {method === 'html' && <ol><li>Abra o modelo (layout) que todas as páginas compartilham, normalmente o arquivo do cabeçalho.</li><li>Cole o código dentro de <code>&lt;head&gt;</code>, antes de <code>&lt;/head&gt;</code>. Não coloque no rodapé nem em páginas avulsas.</li><li>Publique o site e abra uma página. A tag aparece na aba Rede do navegador como <code>supertag.js</code>.</li></ol>}
    {method === 'gtm' && <ol><li>No Google Tag Manager, crie uma tag do tipo <strong>HTML personalizado</strong> e cole o código inteiro, com as marcas <code>&lt;script&gt;</code>.</li><li>Em <strong>Acionamento</strong>, escolha <strong>Initialization – All Pages</strong>. Assim a tag carrega antes das outras e não perde a primeira visita.</li><li>Em <strong>Configurações de consentimento</strong>, deixe <strong>Nenhum consentimento adicional necessário</strong>. A Super Tag espera a decisão do visitante por conta própria.</li><li>Use <strong>Visualizar</strong> para testar e depois <strong>Enviar</strong> para publicar o contêiner.</li></ol>}
    {method === 'cms' && <ol><li><strong>WordPress:</strong> use um plugin de cabeçalho e rodapé (como o WPCode) e cole o código na área <strong>Header</strong>.</li><li><strong>Wix, Webflow, Shopify e similares:</strong> procure <strong>Código personalizado</strong> nas configurações do site, aplique a todas as páginas e posicione em <strong>Head</strong>.</li><li>Se você já usa o GTM nesse site, prefira a instalação pelo GTM.</li></ol>}
    <p className="st-guide__warn">Instale a Super Tag uma única vez. No site e também no GTM, as visitas são contadas em dobro.</p>
  </section>;
}

export function InstallCard({site, onCopy, onDownload, onEmail}) {
  return <section className="st-card st-install"><header><div><h3>Instalação da Super Tag</h3><p>Copie o código e cole em <code>&lt;head&gt;</code> do seu site.</p></div></header>
    <div className="st-code"><code>{site.snippet}</code><button type="button" aria-label="Copiar código" onClick={onCopy}><Copy01 size={16} aria-hidden="true"/></button></div>
    <div className="st-install__actions">
      <ReportsActionButton color="primary" iconLeading={Copy01} onClick={onCopy}>Copiar código</ReportsActionButton>
      <ReportsActionButton color="secondary" iconLeading={Download01} onClick={onDownload}>Baixar arquivo</ReportsActionButton>
      <ReportsActionButton color="secondary" iconLeading={Send01} onClick={onEmail}>Enviar instruções</ReportsActionButton>
    </div>
    <small>O código não inclui credenciais secretas.</small>
  </section>;
}

export function RecentEvents({summary}) {
  const rows = [...(summary || [])].sort((a, b) => Number(b.total) - Number(a.total));
  const total = rows.reduce((sum, row) => sum + Number(row.total), 0);
  return <section className="st-card st-events"><header><div><h3>Eventos recentes</h3></div><span>Últimos 30 dias</span></header>
    {rows.length ? <table className="cadu-table"><thead><tr><th>Evento</th><th className="is-numeric">Total</th></tr></thead><tbody>
      {rows.map(row => <tr key={row.event_kind}><td><strong>{EVENT_LABELS[row.event_kind] || row.event_kind}</strong><code className="block font-mono text-xs font-normal text-tertiary">{row.event_kind}</code></td><td className="is-numeric">{integer(row.total)}</td></tr>)}
      <tr className="bg-secondary font-semibold"><td>Total de eventos</td><td className="is-numeric text-primary">{integer(total)}</td></tr></tbody></table>
      : <p className="st-muted">Os eventos aparecem aqui depois do consentimento e da primeira visita.</p>}
  </section>;
}

export function LinkedFlows({flows, site, clientId}) {
  const host = value => String(value || '').replace(/^www\./, '');
  const linked = flows.filter(item => host(item.allowed_host) === host(site.allowed_host));
  return <section className="st-card st-flows"><header><div><h3>Fluxos vinculados</h3><p>Fluxos que usam os dados deste site.</p></div><span>{linked.length} {linked.length === 1 ? 'fluxo' : 'fluxos'}</span></header>
    {linked.length ? <table className="cadu-table"><thead><tr><th>Fluxo</th><th>Status</th><th>Atualizado</th><th/></tr></thead><tbody>
      {linked.map(item => <tr key={item.id}>
        <td><span className="st-flow-name"><GitBranch01 size={18} aria-hidden="true"/><strong>{item.name}</strong></span></td>
        <td><StatusBadge tone={item.status === 'published' ? 'success' : 'gray'}>{item.status === 'published' ? 'Publicado' : 'Rascunho'}</StatusBadge></td>
        <td className="whitespace-nowrap">{longDate(item.updated_at)}</td>
        <td className="text-right whitespace-nowrap"><ReportsActionButton color="secondary" iconTrailing={ArrowUpRight} href={reportUrl('flow', {client_id: clientId, flow_id: item.id, flow_view: item.status === 'published' ? 'monitor' : 'edit'})}>Abrir</ReportsActionButton></td>
      </tr>)}</tbody></table>
      : <p className="st-muted">Nenhum fluxo usa este site ainda.</p>}
    <footer><ReportsActionButton color="link-color" iconTrailing={ChevronRight} href={reportUrl('flow', {client_id: clientId, site_host: site.allowed_host, flow_view: 'create'})}>Criar fluxo neste site</ReportsActionButton></footer>
  </section>;
}

export function AccessCard({data, site}) {
  return <section className="st-card st-access"><header><span className="st-verify__icon"><Users01 size={20} aria-hidden="true"/></span><div><h3>Acesso ao monitoramento</h3><p>Gerencie quem pode ver os dados deste site na plataforma.</p></div></header>
    <ReportsRelationships data={data} kind="site" id={site.id} name={site.label}/>
  </section>;
}
