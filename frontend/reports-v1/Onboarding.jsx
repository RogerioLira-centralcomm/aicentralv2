import React, {useEffect, useMemo, useState} from 'react';
import {ArrowRight, Check, ChevronLeft, ChevronRight} from '@untitledui/icons';
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

/** Cada capítulo: o que a área faz, por que importa e (quando há) a ação que já deixa o ambiente pronto. */
const CHAPTERS = [
  {key: 'boas-vindas', label: 'Boas-vindas', art: 'onb-1-boas-vindas.webp', title: 'Bem-vindo ao Reports',
    text: 'Aqui você vê o que o anúncio, o site e o resultado fazem juntos. Em 8 passos você conhece cada área e já deixa o ambiente pronto.',
    points: ['Leva cerca de 5 minutos.', 'Dá para pular e voltar quando quiser.', 'Nada é criado sem você confirmar.']},
  {key: 'clientes', label: 'Clientes', art: 'onb-2-clientes.webp', title: 'Clientes e contas', action: 'client',
    text: 'Cada cliente reúne marcas, contas de mídia, campanhas e sites. O seletor na barra lateral troca o cliente de toda a análise.',
    points: ['O logo vem da marca do Workspace, quando há.', 'A Visão geral, a Mídia e o Site mostram sempre um cliente.', 'Em Clientes e contas você organiza tudo em hierarquia.']},
  {key: 'midia', label: 'Mídia', art: 'onb-3-midia.webp', title: 'Mídia', link: ['media', 'Abrir Mídia'],
    text: 'Investimento, cliques, custo por conversão e resultado por campanha, sempre contra o período anterior de mesma duração.',
    points: ['Compare períodos e plataformas.', 'Filtre por fonte de dados e por campanha.', 'Veja criativos e o que está em execução.']},
  {key: 'jornada', label: 'Site & Jornada', art: 'onb-4-jornada.webp', title: 'Site & Jornada', action: 'site',
    text: 'O que as pessoas fazem depois do clique: páginas, canais, navegação, conversões e o caminho de cada visitante, medidos pela Super Tag.',
    points: ['A Super Tag mede visitas, formulários e conversões.', 'Fluxos ligam anúncio, página, formulário e conversão.', 'O heatmap mostra onde as pessoas clicam.']},
  {key: 'relatorios', label: 'Relatórios', art: 'onb-5-relatorios.webp', title: 'Relatórios', link: ['reports', 'Abrir Relatórios'],
    text: 'Análises salvas e entregáveis prontos para distribuir ao cliente, com os números do período que você escolher.',
    points: ['Monte uma vez e reaproveite.', 'Compartilhe por link.', 'Agentes ajudam a revisar o que está fora do normal.']},
  {key: 'alertas', label: 'Alertas', art: 'onb-6-alertas.webp', title: 'Alertas', link: ['alerts', 'Ver alertas'],
    text: 'O Reports vigia o site e as importações e avisa quando algo sai do trilho, com responsável e histórico.',
    points: ['Assuma, silencie ou resolva cada alerta.', 'Avisos por e-mail, se você ligar.', 'Alertas resolvidos ficam no histórico.']},
  {key: 'fontes', label: 'Fontes de dados', art: 'onb-7-fontes.webp', title: 'Fontes de dados', action: 'google',
    text: 'De onde vêm os números: Google Ads por script, conversões do CRM por webhook, o site pela Super Tag e arquivos importados.',
    points: ['Cada fonte tem a própria chave e dá para revogar.', 'O estado mostra quando foi o último envio.', 'O Google Ads é só leitura, a menos que você ligue as Ações.']},
  {key: 'pronto', label: 'Pronto', art: 'onb-8-pronto.webp', title: 'Seu ambiente', final: true,
    text: 'Este é o estado do ambiente agora. O que ainda falta tem um atalho para resolver em poucos cliques.', points: []},
];

/** Imagem do capítulo; se o arquivo ainda não existe, um bloco de marca mantém o espaço. */
function Scene({chapter, index}) {
  const [broken, setBroken] = useState(false);
  useEffect(() => setBroken(false), [chapter.key]);
  if (broken) return <div className="ob-scene ob-scene--empty" aria-hidden="true"><span>{index + 1}</span></div>;
  return <div className="ob-scene" aria-hidden="true"><img key={chapter.key} src={ART + chapter.art} alt="" onError={() => setBroken(true)}/></div>;
}

/** Tela "Conhecer o Reports": um capítulo por área, cada um com a ação que já prepara o ambiente. */
export function Onboarding({data, save, busy, reload}) {
  const [index, setIndex] = useState(() => Math.min(readSaved().at ?? 0, CHAPTERS.length - 1));
  const [seen, setSeen] = useState(() => new Set(readSaved().seen || [0]));
  const [open, setOpen] = useState('');
  const [sites] = useApi(apiUrl('/supertag/sites'));
  const [keys, retryKeys] = useApi(apiUrl('/ingest-keys'));
  const [map] = useApi(apiUrl('/workspace/map'));
  const chapter = CHAPTERS[index];
  const canManageClients = Boolean(data.can_manage_clients);
  const canEdit = data.client.role !== 'viewer';

  useEffect(() => {writeSaved({at: index, seen: [...seen]});}, [index, seen]);
  const go = next => {const bounded = Math.max(0, Math.min(CHAPTERS.length - 1, next)); setIndex(bounded); setSeen(current => new Set(current).add(bounded));};
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

  const linked = new Set(Object.values(map.body?.customer_brands || {}).flat().map(brand => brand.ref));
  const freeBrands = map.body?.available ? (map.body.brands || []).filter(brand => !linked.has(brand.ref)) : [];
  const send = (path, method, payload = {}) => json(`/connect/api/v2/reports${path}`, {method, headers: {'Content-Type': 'application/json', 'X-CSRF-Token': data.csrf}, body: JSON.stringify({...payload})});
  const close = () => setOpen('');
  const href = path => `${APP_BASE}/${path}`;
  const action = chapter.action ? ACTIONS[chapter.action] : null;

  return <div className="untitled-scope ob">
    <nav className="ob-steps" aria-label="Capítulos">
      <ol>{CHAPTERS.map((item, position) => <li key={item.key}>
        <button type="button" className={`${position === index ? 'is-current' : ''}${seen.has(position) && position !== index ? ' is-seen' : ''}`} aria-current={position === index ? 'step' : undefined} onClick={() => go(position)}>
          <b>{seen.has(position) && position !== index ? <Check size={12} aria-hidden="true"/> : position + 1}</b><span>{item.label}</span></button></li>)}</ol>
    </nav>

    <section className="ob-card" aria-label={chapter.title}>
      <Scene chapter={chapter} index={index}/>
      <div className="ob-body">
        <p className="ob-count">{index + 1} de {CHAPTERS.length}</p>
        <h2>{chapter.title}</h2>
        <p className="ob-text">{chapter.text}</p>
        {chapter.points.length > 0 && <ul className="ob-points">{chapter.points.map(point => <li key={point}><Check size={16} aria-hidden="true"/>{point}</li>)}</ul>}

        {action && <div className="ob-action">
          <div className="ob-action__state"><BadgeWithDot type="pill-color" size="sm" color={action.done ? 'success' : 'gray'}>{action.done ? 'Feito' : 'Falta fazer'}</BadgeWithDot><span>{action.text}</span></div>
          {action.allowed ? <Button size="md" color={action.done ? 'secondary' : 'primary'} onPress={() => setOpen(chapter.action)}>{action.label}</Button> : <p className="ob-muted">{action.blocked}</p>}
        </div>}
        {chapter.link && <a className="ob-link" href={href(chapter.link[0])} onClick={event => navigateOnClick(event, href(chapter.link[0]))}>{chapter.link[1]}<ArrowRight size={16} aria-hidden="true"/></a>}

        {chapter.final && <>
          <p className="ob-progress" role="status">{doneCount} de {checklist.length} etapas prontas</p>
          <ul className="ob-checklist">{checklist.map(([label, item, key]) => <li key={label} className={item.done ? 'is-done' : ''}>
            <span className="ob-checklist__mark" aria-hidden="true">{item.done ? <Check size={14}/> : ''}</span>
            <span className="ob-checklist__text"><strong>{label}</strong><small>{item.text}</small></span>
            {!item.done && ((key === 'client' && canManageClients) || (key !== 'client' && canEdit)) && <Button size="sm" color="secondary" onPress={() => setOpen(key)}>Resolver</Button>}</li>)}</ul>
          <div className="ob-final"><Button size="md" color="primary" href={reportUrl('overview')}>Ir para a Visão geral</Button>
            <Button size="md" color="tertiary" onPress={() => {setSeen(new Set([0])); go(0);}}>Rever o passeio</Button></div>
        </>}

        <div className="ob-nav">
          <Button size="md" color="secondary" iconLeading={ChevronLeft} isDisabled={index === 0} onPress={() => go(index - 1)}>Anterior</Button>
          {index < CHAPTERS.length - 1 && <Button size="md" color="primary" iconTrailing={ChevronRight} onPress={() => go(index + 1)}>{index === 0 ? 'Começar' : 'Próximo'}</Button>}
        </div>
      </div>
    </section>

    {open === 'client' && <NewClientWizard freeBrands={freeBrands} save={save} send={send} reload={reload} onDone={async () => {await reload(); close();}} onClose={close}/>}
    {open === 'google' && <ConnectGoogleAdsWizard data={data} save={save} busy={busy} reload={async () => {await reload(); retryKeys();}} onClose={close}/>}
    {open === 'site' && <NewSiteWizard data={data} onClose={close}/>}
  </div>;
}
