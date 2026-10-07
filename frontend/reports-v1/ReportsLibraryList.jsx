import React, {useEffect, useState} from 'react';
import {Menu, MenuItem, MenuTrigger, Popover} from 'react-aria-components';
import {Calendar, ChevronLeft, ChevronRight, DotsHorizontal, Grid01, List, Plus, SearchLg, Star01} from '@untitledui/icons';
import {Button} from '../cadu-design-system/untitled-kit/button.tsx';
import {Badge, BadgeWithDot} from '../cadu-design-system/untitled-kit/badges.tsx';
import {ReportsFieldInput} from './ReportsFieldInput.jsx';
import {ReportsNativeSelect} from './ReportsNativeSelect.jsx';
import {EmptyNote, TD, TH} from './ReportsBlocks.jsx';
import {platformName} from './shell/media.jsx';

const KINDS = [['all', 'Todos'], ['pinned', 'Principais'], ['published', 'Publicados'], ['draft', 'Rascunhos']];
const PAGE = 12;
const VIEW_KEY = 'reports-library-view';
const longDate = new Intl.DateTimeFormat('pt-BR', {day: '2-digit', month: 'short', year: 'numeric'});
export const CREATE_EVENT = 'reports:create-report';
const readView = () => {try {return localStorage.getItem(VIEW_KEY) === 'list' ? 'list' : 'grid';} catch {return 'grid';}};

/** Miniatura decorativa pelo foco do relatório: barras (campanha), curva (fluxo) ou linhas de texto (independente). */
function Thumb({scope}) {
  return <div className="flex h-20 w-28 shrink-0 items-end justify-center overflow-hidden rounded-lg bg-brand-primary px-3 pb-3 text-fg-brand-primary" aria-hidden="true">
    <svg viewBox="0 0 96 56" className="h-full w-full">
      {scope === 'campaign' && [[6, 34], [26, 26], [46, 16], [66, 4]].map(([x, y], index) => <rect key={x} x={x} y={y} width="14" height={56 - y} rx="2" fill="currentColor" opacity={0.35 + index * 0.2}/>)}
      {scope === 'flow' && <><path d="M2 46 C 20 46, 22 22, 40 26 S 66 44, 94 8" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round"/><path d="M2 46 C 20 46, 22 22, 40 26 S 66 44, 94 8 V56 H2Z" fill="currentColor" opacity=".12"/></>}
      {scope === 'none' && [[6, 70], [18, 88], [30, 56], [42, 80], [54, 64]].map(([y, width], index) => <rect key={y} x="4" y={y - 2} width={width} height="6" rx="3" fill="currentColor" opacity={index === 0 ? 0.85 : 0.35}/>)}
    </svg>
  </div>;
}

/** Situação do relatório: publicado tem link público ativo; o resto é rascunho. */
function Status({item}) {
  return <BadgeWithDot type="pill-color" size="sm" color={item.published ? 'success' : 'warning'}>{item.published ? 'Publicado' : 'Rascunho'}</BadgeWithDot>;
}

function Actions({item, onOpen, onPin, canEdit}) {
  return <MenuTrigger>
    <Button size="sm" color="tertiary" iconLeading={DotsHorizontal} aria-label={`Ações de ${item.campaign_name}`} className="relative z-10"/>
    <Popover placement="bottom end" className="untitled-scope min-w-48 overflow-hidden rounded-lg bg-primary py-1 shadow-lg ring-1 ring-secondary outline-hidden">
      <Menu className="outline-hidden" onAction={key => key === 'open' ? onOpen(item.id) : onPin(item)}>
        <MenuItem id="open" className="cursor-pointer px-3 py-2 text-sm font-medium text-secondary outline-hidden data-focused:bg-primary_hover">Abrir</MenuItem>
        {canEdit && <MenuItem id="pin" className="cursor-pointer px-3 py-2 text-sm font-medium text-secondary outline-hidden data-focused:bg-primary_hover">{item.pinned ? 'Tirar dos principais' : 'Marcar como principal'}</MenuItem>}
      </Menu>
    </Popover>
  </MenuTrigger>;
}

/** Biblioteca de relatórios: abas por situação, busca, filtro por campanha ou fluxo, grade ou lista e paginação. */
export function ReportsLibraryList({data, save, onOpen}) {
  const [query, setQuery] = useState('');
  const [campaign, setCampaign] = useState('');
  const [kind, setKind] = useState('all');
  const [view, setView] = useState(readView);
  const [page, setPage] = useState(0);
  const canEdit = data.client.role !== 'viewer';
  useEffect(() => {try {localStorage.setItem(VIEW_KEY, view);} catch {/* só não lembra a escolha */}}, [view]);
  useEffect(() => setPage(0), [query, campaign, kind]);

  const term = query.trim().toLocaleLowerCase();
  const campaignOf = item => data.campaigns.find(entry => String(entry.id) === String(item.media_campaign_id));
  const scopeOf = item => item.flow_id ? 'flow' : item.media_campaign_id ? 'campaign' : 'none';
  const describe = item => {
    const entry = campaignOf(item);
    const account = (data.accounts || []).find(row => String(row.id) === String(entry?.account_id ?? item.account_id));
    const customer = (data.customers || []).find(row => String(row.id) === String(entry?.customer_id ?? account?.customer_id));
    const scope = scopeOf(item);
    const origin = scope === 'flow' ? `Fluxo · ${item.flow_name || 'sem nome'}` : scope === 'campaign' ? [account ? platformName(account.platform) : null, customer?.name || entry?.name].filter(Boolean).join(' · ') || 'Campanha' : 'Independente';
    const fallback = scope === 'flow' ? 'Jornada do fluxo com a mídia das campanhas que levam tráfego a ele.' : scope === 'campaign' ? `Resultado de mídia da campanha ${entry?.name || 'vinculada'}.` : 'Relatório sem vínculo, com as evidências que você montar.';
    return {scope, origin, summary: item.summary?.trim() || fallback};
  };
  const visible = data.reports.filter(item => (!term || `${item.campaign_name} ${item.flow_name || ''} ${campaignOf(item)?.name || ''} ${item.summary || ''}`.toLocaleLowerCase().includes(term))
    && (!campaign || (campaign === 'none' ? !item.media_campaign_id && !item.flow_id : campaign.startsWith('flow:') ? item.flow_id === campaign.slice(5) : String(item.media_campaign_id) === campaign))
    && (kind === 'all' || (kind === 'pinned' ? item.pinned : (kind === 'published') === Boolean(item.published))));
  const counts = {all: data.reports.length, pinned: data.reports.filter(item => item.pinned).length, published: data.reports.filter(item => item.published).length, draft: data.reports.filter(item => !item.published).length};
  const flows = [...new Map(data.reports.filter(item => item.flow_id).map(item => [item.flow_id, item.flow_name])).entries()];
  const pages = Math.max(1, Math.ceil(visible.length / PAGE));
  const current = Math.min(page, pages - 1);
  const shown = visible.slice(current * PAGE, current * PAGE + PAGE);
  const pin = item => save(`/workspaces/${item.id}/pin`, {pinned: !item.pinned}).catch(() => {/* o aviso da página mostra a falha */});
  const version = item => `v${item.revision}${item.published && item.published_revision && item.revision > item.published_revision ? ` · publicada v${item.published_revision}` : ''}`;

  return <div className="flex flex-col gap-5">
    <div className="flex flex-wrap items-center gap-3">
      <div className="flex flex-wrap gap-2" role="group" aria-label="Situação">{KINDS.map(([key, label]) => <button type="button" key={key} aria-pressed={kind === key} onClick={() => setKind(key)}
        className={`inline-flex h-9 items-center gap-2 rounded-lg px-3 text-sm font-medium ring-1 ring-inset transition duration-100 ${kind === key ? 'bg-brand-primary text-brand-secondary ring-brand' : 'bg-primary text-secondary ring-primary hover:bg-primary_hover'}`}>
        {label}<Badge type="pill-color" size="sm" color={kind === key ? 'brand' : 'gray'}>{counts[key]}</Badge></button>)}</div>
      <div className="ml-auto flex flex-wrap items-center gap-3">
        <div className="w-60 max-sm:w-full"><ReportsFieldInput size="sm" type="search" aria-label="Buscar relatórios" placeholder="Buscar relatórios" value={query} onChange={event => setQuery(event.target.value)}
          leading={<SearchLg size={16} aria-hidden="true" className="ml-3 shrink-0 text-fg-quaternary"/>}/></div>
        <div className="w-64 max-sm:w-full"><ReportsNativeSelect size="sm" aria-label="Campanha ou fluxo" value={campaign} onChange={event => setCampaign(event.target.value)}>
          <option value="">Todas as campanhas e fluxos</option><option value="none">Sem campanha nem fluxo</option>
          {flows.map(([id, name]) => <option key={id} value={`flow:${id}`}>Fluxo · {name}</option>)}
          {data.campaigns.filter(item => data.reports.some(report => String(report.media_campaign_id) === String(item.id))).map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
        </ReportsNativeSelect></div>
        <div className="inline-flex overflow-hidden rounded-lg ring-1 ring-primary ring-inset" role="group" aria-label="Visualização">
          {[['grid', Grid01, 'Grade'], ['list', List, 'Lista']].map(([key, Icon, label]) => <button type="button" key={key} aria-pressed={view === key} aria-label={label} title={label} onClick={() => setView(key)}
            className={`inline-flex size-9 items-center justify-center ${view === key ? 'bg-secondary text-fg-secondary' : 'bg-primary text-fg-quaternary hover:bg-primary_hover'}`}><Icon size={18} aria-hidden="true"/></button>)}
        </div>
      </div>
    </div>

    {!visible.length ? <div className="rounded-xl bg-primary shadow-xs ring-1 ring-secondary"><EmptyNote title={data.reports.length ? 'Nada corresponde aos filtros' : 'Nenhum relatório ainda'}>{data.reports.length ? 'Ajuste a busca, a situação ou a campanha.' : 'Crie um relatório por campanha, por fluxo ou independente.'}</EmptyNote></div>
      : view === 'grid' ? <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{shown.map(item => {
        const info = describe(item);
        return <li key={item.id} className="group relative flex flex-col gap-4 rounded-xl bg-primary p-5 shadow-xs ring-1 ring-secondary transition duration-100 ring-inset hover:ring-primary hover:shadow-md">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2"><Status item={item}/>{item.pinned && <span className="inline-flex items-center gap-1 text-xs font-medium text-tertiary"><Star01 size={14} aria-hidden="true" className="text-fg-warning-secondary"/>Principal</span>}</div>
            <Actions item={item} onOpen={onOpen} onPin={pin} canEdit={canEdit}/>
          </div>
          <div className="flex items-start gap-4">
            <div className="min-w-0 flex-1">
              <h3 className="line-clamp-2 text-lg font-semibold text-primary"><button type="button" onClick={() => onOpen(item.id)} className="text-left outline-hidden after:absolute after:inset-0 after:rounded-xl focus-visible:after:ring-2 focus-visible:after:ring-brand">{item.campaign_name}</button></h3>
              <p className="mt-0.5 truncate text-sm font-medium text-secondary">{info.origin}</p>
              <p className="mt-2 line-clamp-2 text-sm text-tertiary">{info.summary}</p>
            </div>
            <Thumb scope={info.scope}/>
          </div>
          <div className="mt-auto flex items-center justify-between gap-2 border-t border-secondary pt-3 text-sm text-tertiary">
            <span className="inline-flex min-w-0 items-center gap-1.5"><Calendar size={16} aria-hidden="true" className="shrink-0 text-fg-quaternary"/><span className="truncate">Atualizado em {longDate.format(new Date(item.updated_at))}</span></span>
            <span className="shrink-0 font-medium whitespace-nowrap text-secondary" title={version(item)}>v{item.revision}</span>
          </div>
        </li>;
      })}</ul>
      : <div className="overflow-x-auto rounded-xl bg-primary shadow-xs ring-1 ring-secondary"><table className="w-full min-w-[760px] border-collapse">
        <thead><tr><th className={TH}>Relatório</th><th className={TH}>Situação</th><th className={TH}>Versão</th><th className={TH}>Atualizado em</th><th className={TH}><span className="sr-only">Ações</span></th></tr></thead>
        <tbody>{shown.map(item => {
          const info = describe(item);
          return <tr key={item.id} className="hover:bg-primary_hover">
            <td className={TD}><button type="button" onClick={() => onOpen(item.id)} className="block max-w-md text-left">
              <span className="flex items-center gap-1.5 font-semibold text-primary">{item.pinned && <Star01 size={14} aria-label="Principal" className="text-fg-warning-secondary"/>}{item.campaign_name}</span>
              <span className="block truncate text-tertiary">{info.origin}</span></button></td>
            <td className={TD}><Status item={item}/></td>
            <td className={TD}>{version(item)}</td>
            <td className={`${TD} whitespace-nowrap`}>{longDate.format(new Date(item.updated_at))}</td>
            <td className={`${TD} w-12 text-right`}><Actions item={item} onOpen={onOpen} onPin={pin} canEdit={canEdit}/></td>
          </tr>;
        })}</tbody>
      </table></div>}

    {visible.length > 0 && <div className="flex flex-wrap items-center justify-between gap-3">
      <p className="text-sm text-tertiary" role="status">Mostrando {shown.length} de {visible.length} {visible.length === 1 ? 'relatório' : 'relatórios'}</p>
      {pages > 1 && <nav className="flex items-center gap-1" aria-label="Páginas">
        <Button size="sm" color="secondary" iconLeading={ChevronLeft} aria-label="Página anterior" isDisabled={current === 0} onPress={() => setPage(current - 1)}/>
        {Array.from({length: pages}, (_, index) => <button type="button" key={index} aria-current={index === current ? 'page' : undefined} onClick={() => setPage(index)}
          className={`size-9 rounded-lg text-sm font-semibold ${index === current ? 'bg-brand-primary text-brand-secondary ring-1 ring-brand ring-inset' : 'text-tertiary hover:bg-primary_hover'}`}>{index + 1}</button>)}
        <Button size="sm" color="secondary" iconLeading={ChevronRight} aria-label="Próxima página" isDisabled={current === pages - 1} onPress={() => setPage(current + 1)}/>
      </nav>}
    </div>}
  </div>;
}

/** Botão do cabeçalho da página: a biblioteca abre o assistente de criação ao ouvir o evento. */
export function NewReportButton() {
  return <Button size="md" color="primary" iconLeading={Plus} onPress={() => dispatchEvent(new Event(CREATE_EVENT))}>Novo relatório</Button>;
}
