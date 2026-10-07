import React, {useEffect, useMemo, useState} from 'react';
import {Menu, MenuItem, MenuTrigger, Popover} from 'react-aria-components';
import {ArrowDown, ArrowUp, Clock, Stars02, ChevronLeft, ChevronRight, DotsHorizontal, Grid01, List, Plus, SearchLg, Star01} from '@untitledui/icons';
import {Button} from '../cadu-design-system/untitled-kit/button.tsx';
import {Badge, BadgeWithDot} from '../cadu-design-system/untitled-kit/badges.tsx';
import {ReportsFieldInput} from './ReportsFieldInput.jsx';
import {ReportsNativeSelect} from './ReportsNativeSelect.jsx';
import {Alert, DrawerActions, EmptyNote, TD, TH} from './ReportsBlocks.jsx';
import {ReportsDrawer} from './ReportsDrawer.jsx';
import {ReportsTextArea} from './ReportsTextArea.jsx';
import {json} from './reportsCommon.jsx';
import {platformName} from './shell/media.jsx';
import {FlowPlatformLogo} from './FlowPlatformLogo.jsx';
import {apiUrl, useApi} from './shell/useApi.js';

const KINDS = [['all', 'Todos'], ['pinned', 'Principais'], ['published', 'Publicados'], ['draft', 'Rascunhos']];
const PAGE = 12;
const VIEW_KEY = 'reports-library-view';
const longDate = new Intl.DateTimeFormat('pt-BR', {day: '2-digit', month: 'short', year: 'numeric'});
const dayLabel = new Intl.DateTimeFormat('pt-BR', {day: '2-digit', month: 'short', timeZone: 'UTC'});
const relative = new Intl.RelativeTimeFormat('pt-BR', {numeric: 'auto'});
const count = value => Number(value || 0).toLocaleString('pt-BR', {maximumFractionDigits: 1});
const METRIC = {conversions: ['conversão', 'conversões'], clicks: ['clique', 'cliques']};
/** "há 2 dias" até um mês; depois a data. */
const updatedLabel = value => {
  const days = Math.round((new Date(value) - Date.now()) / 86400000);
  return days > -31 ? `Atualizado ${relative.format(days, 'day')}` : `Atualizado em ${longDate.format(new Date(value))}`;
};
export const CREATE_EVENT = 'reports:create-report';
const readView = () => {try {return localStorage.getItem(VIEW_KEY) === 'list' ? 'list' : 'grid';} catch {return 'grid';}};

// No celular a capa vai em cima do card, em 2:1; a partir de 640 px vira a coluna da esquerda.
const COVER_BOX = 'aspect-[2/1] rounded-lg sm:aspect-auto sm:h-full sm:min-h-36';

/** Capa do card: o criativo mais recente da campanha no Studio; sem criativo, uma ilustração pelo foco do relatório. */
function Cover({preview, scope, loading}) {
  if (loading) return <div className={`${COVER_BOX} animate-pulse bg-secondary`} aria-hidden="true"/>;
  if (preview?.cover_url) return <div className={`${COVER_BOX} relative overflow-hidden bg-secondary`} aria-hidden="true">
    <img src={preview.cover_url} alt="" loading="lazy" className="absolute inset-0 size-full object-cover transition duration-300 group-hover:scale-105"/></div>;
  return <div className={`${COVER_BOX} flex items-end justify-center overflow-hidden bg-brand-primary px-4 pb-5 text-fg-brand-primary`} aria-hidden="true">
    <svg viewBox="0 0 96 56" className="w-full max-w-28">
      {scope === 'campaign' && [[6, 34], [26, 26], [46, 16], [66, 4]].map(([x, y], index) => <rect key={x} x={x} y={y} width="14" height={56 - y} rx="2" fill="currentColor" opacity={0.35 + index * 0.2}/>)}
      {scope === 'flow' && <><path d="M2 46 C 20 46, 22 22, 40 26 S 66 44, 94 8" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round"/><path d="M2 46 C 20 46, 22 22, 40 26 S 66 44, 94 8 V56 H2Z" fill="currentColor" opacity=".12"/></>}
      {scope === 'none' && [[6, 70], [18, 88], [30, 56], [42, 80], [54, 64]].map(([y, width], index) => <rect key={y} x="4" y={y - 2} width={width} height="6" rx="3" fill="currentColor" opacity={index === 0 ? 0.85 : 0.35}/>)}
    </svg>
  </div>;
}

function Logos({platforms}) {
  if (!platforms?.length) return <span/>;
  return <ul className="flex items-center gap-1" aria-label={`Plataformas: ${platforms.map(platformName).join(', ')}`}>
    {platforms.slice(0, 4).map(item => <li key={item} title={platformName(item)} className="flex size-6 items-center justify-center overflow-hidden rounded-md bg-primary ring-1 ring-secondary [&_img]:size-3.5 [&_svg]:h-3 [&_svg]:w-4"><FlowPlatformLogo platform={item}/></li>)}
    {platforms.length > 4 && <li className="text-xs font-medium text-tertiary">+{platforms.length - 4}</li>}
  </ul>;
}

/** Série diária do relatório: passar o mouse (ou o dedo) mostra o dia e o valor. */
function Spark({preview, compact = false}) {
  const [hover, setHover] = useState(null);
  const series = preview?.series || [];
  if (!series.length) return compact ? <span className="text-xs text-quaternary">—</span> : null;
  const [one, many] = METRIC[preview.metric] || ['', ''];
  const width = 120, height = compact ? 24 : 36;
  const top = Math.max(...series.map(point => point.value), 1);
  const x = index => series.length === 1 ? width / 2 : index * width / (series.length - 1);
  const y = value => height - 2 - (value / top) * (height - 4);
  const line = series.map((point, index) => `${index ? 'L' : 'M'}${x(index).toFixed(1)} ${y(point.value).toFixed(1)}`).join(' ');
  const change = preview.previous ? (preview.total - preview.previous) * 100 / preview.previous : null;
  const point = hover == null ? null : series[hover];
  const pick = event => {
    const box = event.currentTarget.getBoundingClientRect();
    setHover(Math.max(0, Math.min(series.length - 1, Math.round((event.clientX - box.left) / box.width * (series.length - 1)))));
  };
  const chart = <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" className={`block w-full text-fg-brand-primary ${compact ? 'h-6' : 'h-9'}`}
    onPointerMove={compact ? undefined : pick} onPointerLeave={() => setHover(null)} role="img"
    aria-label={`${count(preview.total)} ${preview.total === 1 ? one : many} nos últimos ${series.length} dias do período`}>
    <path d={`${line} L${width} ${height} L0 ${height}Z`} fill="currentColor" opacity=".1"/>
    <path d={line} fill="none" stroke="currentColor" strokeWidth="1.75" vectorEffect="non-scaling-stroke" strokeLinejoin="round"/>
    {point && <><line x1={x(hover)} x2={x(hover)} y1="0" y2={height} stroke="currentColor" strokeWidth="1" opacity=".35" vectorEffect="non-scaling-stroke"/>
      <circle cx={x(hover)} cy={y(point.value)} r="2.5" fill="currentColor"/></>}
  </svg>;
  if (compact) return <div className="w-28">{chart}</div>;
  return <div className="relative z-10">
    <div className="flex items-baseline justify-between gap-2 text-sm">
      <span className="font-semibold text-primary tabular-nums">{point ? `${count(point.value)} ${point.value === 1 ? one : many}` : `${count(preview.total)} ${preview.total === 1 ? one : many}`}</span>
      {point ? <span className="text-xs text-tertiary">{dayLabel.format(new Date(point.date))}</span>
        : change != null && Number.isFinite(change) && <span className={`inline-flex items-center gap-0.5 text-xs font-medium ${change >= 0 ? 'text-success-primary' : 'text-error-primary'}`} title="Contra o período anterior de mesma duração">
          {change >= 0 ? <ArrowUp size={12} aria-hidden="true"/> : <ArrowDown size={12} aria-hidden="true"/>}{count(Math.abs(change))}%</span>}
    </div>
    {chart}
  </div>;
}

/** Situação do relatório: publicado tem link público ativo; o resto é rascunho. */
function Status({item}) {
  return <BadgeWithDot type="pill-color" size="sm" color={item.published ? 'success' : 'warning'}>{item.published ? 'Publicado' : 'Rascunho'}</BadgeWithDot>;
}

function Actions({item, onOpen, onPin, onCover, hasCover, canEdit}) {
  return <MenuTrigger>
    <Button size="sm" color="tertiary" iconLeading={DotsHorizontal} aria-label={`Ações de ${item.campaign_name}`} className="relative z-10"/>
    <Popover placement="bottom end" className="untitled-scope min-w-48 overflow-hidden rounded-lg bg-primary py-1 shadow-lg ring-1 ring-secondary outline-hidden">
      <Menu className="outline-hidden" onAction={key => key === 'open' ? onOpen(item.id) : key === 'cover' ? onCover(item) : onPin(item)}>
        <MenuItem id="open" className="cursor-pointer px-3 py-2 text-sm font-medium text-secondary outline-hidden data-focused:bg-primary_hover">Abrir</MenuItem>
        {canEdit && <MenuItem id="pin" className="cursor-pointer px-3 py-2 text-sm font-medium text-secondary outline-hidden data-focused:bg-primary_hover">{item.pinned ? 'Tirar dos principais' : 'Marcar como principal'}</MenuItem>}
        {canEdit && onCover && <MenuItem id="cover" className="flex cursor-pointer items-center gap-2 px-3 py-2 text-sm font-medium text-secondary outline-hidden data-focused:bg-primary_hover"><Stars02 size={16} aria-hidden="true" className="text-fg-brand-primary"/>{hasCover ? 'Nova capa com o Studio' : 'Gerar capa com o Studio'}</MenuItem>}
      </Menu>
    </Popover>
  </MenuTrigger>;
}

/** Capa pelo Studio: prompt pronto a partir do relatório, estimativa de créditos e geração só depois de confirmar o custo. */
function CoverDrawer({report, data, onClose, onDone}) {
  const [brief, setBrief] = useState(null);
  const [prompt, setPrompt] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  // Um identificador por abertura: repetir o envio (rede instável, clique duplo) não gera nem cobra de novo.
  const [requestId, setRequestId] = useState('');
  useEffect(() => {
    if (!report) return;
    setBrief(null); setPrompt(''); setError(''); setRequestId(crypto.randomUUID());
    json(`/connect/api/v2/reports/workspaces/${report.id}/cover`).then(value => {setBrief(value); setPrompt(value.prompt);}).catch(failure => setError(failure.message));
  }, [report?.id]);
  const estimate = brief?.estimate ? `~${Number(brief.estimate).toLocaleString('pt-BR')} créditos` : 'créditos do Studio';
  const submit = async event => {
    event.preventDefault();
    setBusy(true); setError('');
    try {
      const result = await json(`/connect/api/v2/reports/workspaces/${report.id}/cover`, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': data.csrf},
        body: JSON.stringify({prompt, request_id: requestId, confirmed_cost: true})});
      onDone(result);
    } catch (failure) {
      setError(failure.message);
      // Resposta definitiva (saldo, pedido inválido): a próxima tentativa é um pedido novo. Sem resposta (rede, tempo
      // esgotado) o identificador fica: a geração pode ter terminado e repetir não pode cobrar de novo.
      if (failure.status >= 400 && failure.status < 500) setRequestId(crypto.randomUUID());
    } finally {setBusy(false);}
  };
  return <ReportsDrawer open={Boolean(report)} onOpenChange={value => {if (!value && !busy) onClose();}} title="Capa com o Studio" description="O Studio cria uma imagem para o card a partir deste relatório." context={report?.campaign_name}>
    <form className="untitled-scope flex flex-col gap-5" onSubmit={submit}>
      {error && <Alert>{error}</Alert>}
      <ReportsTextArea label="Pedido para o Studio" rows={9} maxLength={4000} value={prompt} onChange={event => {setPrompt(event.target.value); if (error) setRequestId(crypto.randomUUID());}} isDisabled={!brief || busy}
        hint="Montado com o tema, o foco e as plataformas do relatório. Os números não entram na imagem: o card mostra os reais."/>
      <div className="rounded-lg bg-secondary px-4 py-3 text-sm text-secondary ring-1 ring-secondary ring-inset">
        <p className="font-semibold text-primary">Custo estimado: {estimate}</p>
        <p className="mt-1 text-tertiary">A cobrança usa o consumo real do Studio e pode variar um pouco. Imagem recusada pelo revisor automático não é cobrada.</p>
      </div>
      {busy && <p role="status" className="text-sm text-tertiary">Gerando no Studio. Pode levar até um minuto.</p>}
      <DrawerActions onCancel={onClose} busy={busy} disabled={!brief || prompt.trim().length < 3} label={`Gerar capa (${estimate})`}/>
    </form>
  </ReportsDrawer>;
}

/** Biblioteca de relatórios: abas por situação, busca, filtro por campanha ou fluxo, grade ou lista e paginação. */
export function ReportsLibraryList({data, save, onOpen}) {
  const [query, setQuery] = useState('');
  const [campaign, setCampaign] = useState('');
  const [kind, setKind] = useState('all');
  const [view, setView] = useState(readView);
  const [page, setPage] = useState(0);
  const canEdit = data.client.role !== 'viewer';
  const [previewState, retryPreviews] = useApi(apiUrl('/workspaces/previews'));
  const [coverFor, setCoverFor] = useState(null);
  const [coverNote, setCoverNote] = useState('');
  const previews = useMemo(() => new Map((previewState.body?.previews || []).map(item => [item.id, item])), [previewState.body]);
  const loadingPreviews = previewState.loading && !previewState.body;
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
      <div className="flex max-w-full gap-2 overflow-x-auto [scrollbar-width:none] sm:flex-wrap" role="group" aria-label="Situação">{KINDS.map(([key, label]) => <button type="button" key={key} aria-pressed={kind === key} onClick={() => setKind(key)}
        className={`inline-flex h-9 shrink-0 items-center gap-2 rounded-lg px-3 text-sm font-medium ring-1 ring-inset transition duration-100 ${kind === key ? 'bg-brand-primary text-brand-secondary ring-brand' : 'bg-primary text-secondary ring-primary hover:bg-primary_hover'}`}>
        {label}<Badge type="pill-color" size="sm" color={kind === key ? 'brand' : 'gray'}>{counts[key]}</Badge></button>)}</div>
      <div className="ml-auto flex flex-wrap items-center gap-3 max-sm:ml-0 max-sm:w-full">
        <div className="w-60 max-sm:w-full"><ReportsFieldInput size="sm" type="search" aria-label="Buscar relatórios" placeholder="Buscar relatórios" value={query} onChange={event => setQuery(event.target.value)}
          leading={<SearchLg size={16} aria-hidden="true" className="ml-3 shrink-0 text-fg-quaternary"/>}/></div>
        <div className="w-64 max-sm:w-auto max-sm:min-w-0 max-sm:flex-1"><ReportsNativeSelect size="sm" aria-label="Campanha ou fluxo" value={campaign} onChange={event => setCampaign(event.target.value)}>
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
        const preview = previews.get(item.id);
        return <li key={item.id} className="group relative grid grid-cols-1 gap-x-4 gap-y-3 sm:grid-cols-[minmax(0,40%)_minmax(0,1fr)] rounded-xl bg-primary p-3 shadow-xs ring-1 ring-secondary transition duration-150 ring-inset hover:-translate-y-0.5 hover:shadow-lg hover:ring-primary">
          <Cover preview={preview} scope={info.scope} loading={loadingPreviews}/>
          <div className="flex min-w-0 flex-col gap-1.5 py-1 pr-1">
            <div className="flex min-h-8 items-center justify-between gap-2"><Logos platforms={preview?.platforms}/><Actions item={item} onOpen={onOpen} onPin={pin} onCover={setCoverFor} hasCover={Boolean(preview?.cover_url)} canEdit={canEdit}/></div>
            <h3 className="line-clamp-2 text-md font-semibold text-primary"><button type="button" onClick={() => onOpen(item.id)} className="text-left outline-hidden after:absolute after:inset-0 after:rounded-xl focus-visible:after:ring-2 focus-visible:after:ring-brand">{item.campaign_name}</button></h3>
            <p className="truncate text-sm text-secondary">{info.origin}</p>
            <p className="line-clamp-2 text-sm text-tertiary">{info.summary}</p>
            <div className="mt-auto pt-1"><Spark preview={preview}/></div>
          </div>
          <div className="flex items-center gap-2 border-t sm:col-span-2 border-secondary px-1 pt-3 text-sm text-tertiary">
            <Status item={item}/>
            {item.pinned && <Star01 size={16} aria-label="Principal" className="shrink-0 text-fg-warning-secondary"/>}
            <span className="inline-flex min-w-0 items-center gap-1"><Clock size={14} aria-hidden="true" className="shrink-0 text-fg-quaternary"/><span className="truncate" title={longDate.format(new Date(item.updated_at))}>{updatedLabel(item.updated_at)}</span></span>
            <span className="ml-auto shrink-0 rounded-md px-1.5 text-xs font-medium whitespace-nowrap text-secondary ring-1 ring-secondary ring-inset" title={version(item)}>v{item.revision}</span>
          </div>
        </li>;
      })}</ul>
      : <div className="overflow-x-auto rounded-xl bg-primary shadow-xs ring-1 ring-secondary"><table className="w-full min-w-[900px] border-collapse">
        <thead><tr><th className={TH}>Relatório</th><th className={TH}>Plataformas</th><th className={TH}>Tendência</th><th className={TH}>Situação</th><th className={TH}>Versão</th><th className={TH}>Atualizado em</th><th className={TH}><span className="sr-only">Ações</span></th></tr></thead>
        <tbody>{shown.map(item => {
          const info = describe(item);
          return <tr key={item.id} className="hover:bg-primary_hover">
            <td className={TD}><button type="button" onClick={() => onOpen(item.id)} className="block max-w-md text-left">
              <span className="flex items-center gap-1.5 font-semibold text-primary">{item.pinned && <Star01 size={14} aria-label="Principal" className="text-fg-warning-secondary"/>}{item.campaign_name}</span>
              <span className="block truncate text-tertiary">{info.origin}</span></button></td>
            <td className={TD}><Logos platforms={previews.get(item.id)?.platforms}/></td>
            <td className={TD}><Spark preview={previews.get(item.id)} compact/></td>
            <td className={TD}><Status item={item}/></td>
            <td className={TD}>{version(item)}</td>
            <td className={`${TD} whitespace-nowrap`}>{longDate.format(new Date(item.updated_at))}</td>
            <td className={`${TD} w-12 text-right`}><Actions item={item} onOpen={onOpen} onPin={pin} onCover={setCoverFor} hasCover={Boolean(previews.get(item.id)?.cover_url)} canEdit={canEdit}/></td>
          </tr>;
        })}</tbody>
      </table></div>}

    {coverNote && <p role="status" className="rounded-lg bg-success-primary px-4 py-3 text-sm text-success-primary ring-1 ring-secondary ring-inset">{coverNote}</p>}
    <CoverDrawer report={coverFor} data={data} onClose={() => setCoverFor(null)} onDone={result => {
      setCoverFor(null); retryPreviews();
      setCoverNote(`Capa criada no Studio${result.charged_credits ? `: ${Number(result.charged_credits).toLocaleString('pt-BR')} créditos cobrados` : ''}.`);
    }}/>
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
