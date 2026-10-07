import React, {useEffect, useMemo, useRef, useState} from 'react';
import {ArrowRight, Bell01, Building02, Check, ChevronLeft, ChevronRight, Clock, ClockRewind, Cursor02, Data, FileCheck02, FolderShield, Key01, LineChartUp01, Lock01, Mail01, Monitor02, RefreshCw01, Route, Share07, Stars02, Target04, Users01, Zap} from '@untitledui/icons';
import {Button} from '../cadu-design-system/untitled-kit/button.tsx';
import {BadgeWithDot} from '../cadu-design-system/untitled-kit/badges.tsx';
import {NewClientWizard} from './NewClientWizard.jsx';
import {ConnectGoogleAdsWizard} from './ConnectGoogleAdsWizard.jsx';
import {NewSiteWizard} from './NewSiteWizard.jsx';
import {json, reportUrl} from './reportsCommon.jsx';
import {APP_BASE, navigateOnClick} from './shell/routes.js';
import {apiUrl, useApi} from './shell/useApi.js';
import './onboarding.css';

const ART = '/static/images/reports/illustrations/';
const SAVED = 'reports-onboarding';
const readSaved = () => {try {return JSON.parse(localStorage.getItem(SAVED) || '{}');} catch {return {};}};
const writeSaved = value => {try {localStorage.setItem(SAVED, JSON.stringify(value));} catch {/* o passeio só não lembra onde parou */}};

/** Cada capítulo: o que a área faz, três destaques e (quando há) a ação que já deixa o ambiente pronto. A frase vai sobre a cena, como texto da tela. */
const CHAPTERS = [
  {key: 'boas-vindas', focus: 28, label: 'Boas-vindas', art: 'onb-1-boas-vindas.webp', title: 'Boas-vindas ao Reports', quote: 'Dados conectam decisões a resultados.',
    text: 'Aqui você vê o que o anúncio, o site e o resultado fazem juntos. Em 8 passos você conhece cada área e já deixa o ambiente pronto.',
    points: [[Clock, 'Leva cerca de 5 minutos', 'Objetivo e direto, sem enrolação.'], [Zap, 'Dá para pular e voltar', 'Faça no seu ritmo, quando quiser.'], [Check, 'Nada é criado sem você confirmar', 'Você mantém o controle sempre.']]},
  {key: 'clientes', focus: 35, label: 'Clientes', art: 'onb-2-clientes.webp', title: 'Clientes e contas', action: 'client', quote: 'Cada número no cliente certo.',
    text: 'Cada cliente reúne marcas, contas de mídia, campanhas e sites. O seletor na barra lateral troca o cliente de toda a análise.',
    points: [[Building02, 'Logo automático', 'Vem da marca do Workspace, quando houver.'], [Users01, 'Um cliente por vez', 'Visão geral, Mídia e Site mostram sempre o cliente escolhido.'], [FolderShield, 'Tudo em hierarquia', 'Organize clientes, marcas e contas em Clientes e contas.']]},
  {key: 'midia', focus: 38, label: 'Mídia', art: 'onb-3-midia.webp', title: 'Mídia', link: ['media', 'Abrir Mídia'], quote: 'Investimento só faz sentido ao lado do resultado.',
    text: 'Investimento, cliques, custo por conversão e resultado por campanha, sempre comparados ao período anterior de mesma duração.',
    points: [[LineChartUp01, 'Compare períodos e plataformas', 'Veja o que melhorou e o que caiu.'], [Target04, 'Filtre por fonte e campanha', 'Vá do total ao detalhe em um clique.'], [Monitor02, 'Veja os criativos', 'Saiba o que está no ar agora.']]},
  {key: 'jornada', focus: 22, label: 'Site & Jornada', art: 'onb-4-jornada.webp', title: 'Site & Jornada', action: 'site', quote: 'O clique é só o começo da jornada.',
    text: 'O que as pessoas fazem depois do clique: páginas, canais, navegação, conversões e o caminho de cada visitante, medidos pela Super Tag.',
    points: [[Data, 'Super Tag', 'Mede visitas, formulários e conversões.'], [Route, 'Fluxos de ponta a ponta', 'Ligam anúncio, página, formulário e conversão.'], [Cursor02, 'Mapa de calor', 'Mostra onde as pessoas clicam.']]},
  {key: 'relatorios', focus: 32, label: 'Relatórios', art: 'onb-5-relatorios.webp', title: 'Relatórios', link: ['reports', 'Abrir Relatórios'], quote: 'Monte uma vez, entregue sempre.',
    text: 'Análises salvas e entregáveis prontos para o cliente, com os números do período que você escolher.',
    points: [[FileCheck02, 'Monte uma vez', 'Reaproveite a mesma análise em qualquer período.'], [Share07, 'Compartilhe por link', 'Envie o link direto ao cliente.'], [Stars02, 'Revisão com agente', 'Um agente aponta o que está fora do padrão.']]},
  {key: 'alertas', focus: 40, label: 'Alertas', art: 'onb-6-alertas.webp', title: 'Alertas', link: ['alerts', 'Ver alertas'], quote: 'Problema visto cedo é problema pequeno.',
    text: 'O Reports vigia o site e as importações e avisa quando algo foge do esperado, com responsável e histórico.',
    points: [[Bell01, 'Assuma, silencie ou resolva', 'Cada alerta tem um responsável.'], [Mail01, 'Aviso por e-mail', 'Ative quando quiser receber.'], [ClockRewind, 'Histórico guardado', 'Alertas resolvidos continuam disponíveis para consulta.']]},
  {key: 'fontes', focus: 42, label: 'Fontes de dados', art: 'onb-7-fontes.webp', title: 'Fontes de dados', action: 'google', quote: 'Número confiável começa na fonte certa.',
    text: 'De onde vêm os números: Google Ads por script, conversões do CRM por webhook, o site pela Super Tag e arquivos importados.',
    points: [[Key01, 'Uma chave por fonte', 'Dá para revogar a qualquer momento.'], [RefreshCw01, 'Último envio à vista', 'O estado mostra quando cada fonte mandou dados.'], [Lock01, 'Google Ads só leitura', 'Nada muda na conta, a menos que você ative as Ações.']]},
  {key: 'pronto', focus: 60, label: 'Pronto', art: 'onb-8-pronto.webp', final: true, quote: 'Tudo no lugar para começar.', points: []},
];

/** Ações no cabeçalho da página: tempo estimado e saída do passeio. */
export function OnboardingHeaderActions() {
  return <>
    <span className="ob-time"><Clock size={16} aria-hidden="true"/>~ 5 minutos</span>
    <Button size="md" color="secondary" href={reportUrl('overview')}>Sair do passeio</Button>
  </>;
}

/** Cena do capítulo com a frase por cima; se o arquivo ainda não existe, um bloco de marca mantém o espaço. */
function Scene({chapter, index}) {
  const [broken, setBroken] = useState(false);
  useEffect(() => setBroken(false), [chapter.key]);
  return <figure className={`ob-scene${broken ? ' ob-scene--empty' : ''}`}>
    {broken ? <span aria-hidden="true">{index + 1}</span>
      : <img key={chapter.key} src={ART + chapter.art} alt="" style={{objectPosition: `${chapter.focus ?? 30}% 50%`}} onError={() => setBroken(true)}/>}
    <figcaption key={chapter.key}>“{chapter.quote}”</figcaption>
  </figure>;
}

/** Tela "Conhecer o Reports": um capítulo por área, cada um com a ação que já prepara o ambiente. */
export function Onboarding({data, save, busy, reload}) {
  const [index, setIndex] = useState(() => Math.min(readSaved().at ?? 0, CHAPTERS.length - 1));
  const [open, setOpen] = useState('');
  const [sites] = useApi(apiUrl('/supertag/sites'));
  const [keys, retryKeys] = useApi(apiUrl('/ingest-keys'));
  const [map] = useApi(apiUrl('/workspace/map'));
  const chapter = CHAPTERS[index];
  const last = index === CHAPTERS.length - 1;
  const canManageClients = Boolean(data.can_manage_clients);
  const canEdit = data.client.role !== 'viewer';

  useEffect(() => {writeSaved({at: index});}, [index]);
  // Em telas estreitas a barra de passos rola; o passo atual fica sempre à vista.
  // Rola só a barra, na horizontal: scrollIntoView também moveria a página até os passos.
  const stepsRef = useRef(null);
  useEffect(() => {
    const list = stepsRef.current, current = list?.querySelector('.is-current');
    if (!list || !current || list.scrollWidth <= list.clientWidth) return;
    const left = current.offsetLeft, right = left + current.offsetWidth;
    if (left < list.scrollLeft) list.scrollLeft = left - 8;
    else if (right > list.scrollLeft + list.clientWidth) list.scrollLeft = right - list.clientWidth + 8;
  }, [index]);
  const go = next => setIndex(Math.max(0, Math.min(CHAPTERS.length - 1, next)));
  useEffect(() => {
    const onKey = event => {
      if (open || ['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName)) return;
      if (event.key === 'ArrowRight') go(index + 1); else if (event.key === 'ArrowLeft') go(index - 1);
    };
    addEventListener('keydown', onKey);
    return () => removeEventListener('keydown', onKey);
  }, [index, open]);

  const customers = (data.customers || []).filter(item => item.status !== 'archived');
  const activeKeys = (keys.body?.keys || []).filter(item => !item.revoked_at);
  const liveSites = (sites.body?.sites || []).filter(item => !item.revoked_at);
  const status = useMemo(() => ({
    client: {done: customers.length > 0, text: customers.length ? `${customers.length} cliente${customers.length === 1 ? '' : 's'}` : 'Nenhum cliente ainda'},
    account: {done: (data.accounts || []).length > 0, text: (data.accounts || []).length ? `${data.accounts.length} conta${data.accounts.length === 1 ? '' : 's'} de mídia` : 'Nenhuma conta de mídia'},
    google: {done: activeKeys.length > 0, text: activeKeys.some(item => item.last_used_at) ? 'Recebendo dados' : activeKeys.length ? 'Conectado, aguardando o primeiro envio' : 'Nenhuma fonte conectada'},
    campaign: {done: (data.campaigns || []).length > 0, text: (data.campaigns || []).length ? `${data.campaigns.length} campanha${data.campaigns.length === 1 ? '' : 's'}` : 'Nenhuma campanha cadastrada'},
    site: {done: liveSites.length > 0, text: liveSites.some(item => Number(item.events_30d) > 0) ? 'Coletando visitas' : liveSites.length ? 'Site criado, aguardando visitas' : 'Nenhum site conectado'},
  }), [data.customers, data.accounts, data.campaigns, keys.body, sites.body]);
  const ACTIONS = {
    client: {done: status.client.done && status.account.done, text: status.client.text + (status.account.done ? ' · ' + status.account.text : ''), label: status.client.done ? 'Adicionar outro cliente' : 'Criar cliente e conta', allowed: canManageClients, blocked: 'Só administradores criam clientes.'},
    google: {done: status.google.done, text: status.google.text, label: status.google.done ? 'Conectar outra conta' : 'Conectar o Google Ads', allowed: canEdit, blocked: 'Seu acesso é só de leitura.'},
    site: {done: status.site.done, text: status.site.text, label: status.site.done ? 'Adicionar outro site' : 'Adicionar site, fluxo e Super Tag', allowed: canEdit, blocked: 'Seu acesso é só de leitura.'},
  };
  const checklist = [
    ['Cliente cadastrado', status.client, 'client'], ['Conta de mídia', status.account, 'client'], ['Fonte do Google Ads', status.google, 'google'],
    ['Campanha cadastrada', status.campaign, 'google'], ['Site com Super Tag', status.site, 'site'],
  ];
  const doneCount = checklist.filter(item => item[1].done).length;
  const allDone = doneCount === checklist.length;
  const title = chapter.final ? (allDone ? 'Tudo pronto' : 'Quase lá') : chapter.title;
  const text = chapter.final ? (allDone ? 'Cliente, fontes e site estão conectados. Agora é só analisar.' : 'Este é o estado do ambiente agora. O que ainda falta tem um atalho para resolver em poucos cliques.') : chapter.text;

  const linked = new Set(Object.values(map.body?.customer_brands || {}).flat().map(brand => brand.ref));
  const freeBrands = map.body?.available ? (map.body.brands || []).filter(brand => !linked.has(brand.ref)) : [];
  const send = (path, method, payload = {}) => json(`/connect/api/v2/reports${path}`, {method, headers: {'Content-Type': 'application/json', 'X-CSRF-Token': data.csrf}, body: JSON.stringify({...payload})});
  const close = () => setOpen('');
  const href = path => `${APP_BASE}/${path}`;
  const action = chapter.action ? ACTIONS[chapter.action] : null;
  // Uma ação pendente é o destaque do capítulo; seguir em frente vira secundário.
  const actionFirst = Boolean(action && action.allowed && !action.done);

  return <div className="untitled-scope ob">
    <section className="ob-card" aria-label={title}>
      <Scene chapter={chapter} index={index}/>
      <div className="ob-body">
        <div className="ob-top">
          <p className="ob-count">{index + 1} de {CHAPTERS.length}</p>
          <div className="ob-arrows">
            <button type="button" aria-label="Passo anterior" disabled={index === 0} onClick={() => go(index - 1)}><ChevronLeft size={20} aria-hidden="true"/></button>
            <button type="button" aria-label="Próximo passo" disabled={last} onClick={() => go(index + 1)}><ChevronRight size={20} aria-hidden="true"/></button>
          </div>
        </div>
        <h2 key={chapter.key}>{title}</h2>
        <p className="ob-text">{text}</p>
        {chapter.points.length > 0 && <ul className="ob-points">{chapter.points.map(([Icon, label, detail]) => <li key={label}>
          <span className="ob-points__icon" aria-hidden="true"><Icon size={22}/></span>
          <span><strong>{label}</strong><small>{detail}</small></span></li>)}</ul>}

        {action && <div className="ob-action">
          <div className="ob-action__state"><BadgeWithDot type="pill-color" size="sm" color={action.done ? 'success' : 'gray'}>{action.done ? 'Feito' : 'Falta fazer'}</BadgeWithDot><span>{action.text}</span></div>
          {action.allowed ? <Button size="md" color={action.done ? 'secondary' : 'primary'} onPress={() => setOpen(chapter.action)}>{action.label}</Button> : <p className="ob-muted">{action.blocked}</p>}
        </div>}

        {chapter.final && <>
          <p className="ob-progress" role="status">{doneCount} de {checklist.length} etapas prontas</p>
          <ul className="ob-checklist">{checklist.map(([label, item, key]) => <li key={label} className={item.done ? 'is-done' : ''}>
            <span className="ob-checklist__mark" aria-hidden="true">{item.done ? <Check size={14}/> : ''}</span>
            <span className="ob-checklist__text"><strong>{label}</strong><small>{item.text}</small></span>
            {!item.done && ((key === 'client' && canManageClients) || (key !== 'client' && canEdit)) && <Button size="sm" color="secondary" onPress={() => setOpen(key)}>Resolver</Button>}</li>)}</ul>
        </>}

        <div className="ob-cta">
          {last ? <>
            <Button size="lg" color="primary" iconTrailing={ChevronRight} href={reportUrl('overview')}>Ir para a Visão geral</Button>
            <button type="button" className="ob-link" onClick={() => go(0)}>Rever o passeio</button>
          </> : <>
            <Button size="lg" color={actionFirst ? 'secondary' : 'primary'} iconTrailing={ChevronRight} onPress={() => go(index + 1)}>{index === 0 ? 'Começar agora' : 'Continuar'}</Button>
            {chapter.link && <a className="ob-link" href={href(chapter.link[0])} onClick={event => navigateOnClick(event, href(chapter.link[0]))}>{chapter.link[1]}<ArrowRight size={16} aria-hidden="true"/></a>}
          </>}
        </div>
      </div>
    </section>

    <nav className="ob-steps" aria-label="Passos do passeio">
      <ol ref={stepsRef}>{CHAPTERS.map((item, position) => <li key={item.key} className={position < index ? 'is-past' : ''}>
        <button type="button" className={position === index ? 'is-current' : ''} aria-current={position === index ? 'step' : undefined} onClick={() => go(position)}>
          <b>{position + 1}</b><span>{item.label}</span></button></li>)}</ol>
    </nav>

    {open === 'client' && <NewClientWizard freeBrands={freeBrands} save={save} send={send} reload={reload} onDone={async () => {await reload(); close();}} onClose={close}/>}
    {open === 'google' && <ConnectGoogleAdsWizard data={data} save={save} busy={busy} reload={async () => {await reload(); retryKeys();}} onClose={close}/>}
    {open === 'site' && <NewSiteWizard data={data} onClose={close}/>}
  </div>;
}
