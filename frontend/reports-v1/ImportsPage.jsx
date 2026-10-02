import React, {useEffect, useRef, useState} from 'react';
import {ArrowLeft, FileCheck02, Stars02, UploadCloud02, XClose} from '@untitledui/icons';
import {Button} from '../cadu-design-system/untitled-kit/button.tsx';
import {Badge, BadgeWithDot} from '../cadu-design-system/untitled-kit/badges.tsx';
import {Callout, Card, DrawerActions, EmptyNote, TD, TH} from './ReportsBlocks.jsx';
import {ReportsDrawer} from './ReportsDrawer.jsx';
import {ReportsFieldInput} from './ReportsFieldInput.jsx';
import {ReportsNativeSelect} from './ReportsNativeSelect.jsx';
import {ReportsTabs} from './ReportsTabs.jsx';
import {json, shortDate} from './reportsCommon.jsx';

const API = '/connect/api/v2/reports';
const FILE_STATUS = {parsed: ['Lido', 'brand'], needs_review: ['Revisão necessária', 'warning'], awaiting_extraction: ['Aguardando leitura', 'brand'],
  applied: ['Aplicado', 'success'], pending: ['Processando', 'gray'], failed: ['Falhou', 'error'], conflict: ['Com divergências', 'warning']};
const UPDATE_KIND = {first: 'Primeiros dados', incremental: 'Novos dias', revision: 'Revisão de valores', duplicate: 'Reenvio idêntico', campaign_missing: 'Campanha ausente'};
const UPDATE_KIND_LONG = {first: 'primeiros dados da campanha', incremental: 'novos dias de dados', revision: 'valores diferentes para uma data já recebida', duplicate: 'reenvio com os mesmos valores', campaign_missing: 'campanha ainda sem associação'};
const IDENTITY = [['platform', 'Plataforma'], ['external_account_id', 'ID da conta'], ['account_name', 'Nome da conta'], ['external_campaign_id', 'ID da campanha'], ['campaign_name', 'Nome da campanha']];
const METRICS = [['currency', 'Moeda'], ['impressions', 'Impressões'], ['clicks', 'Cliques'], ['cost', 'Custo'], ['conversions', 'Conversões'], ['conversion_value', 'Valor das conversões']];
const MAP_FIELDS = [['platform', 'Plataforma'], ['account_id', 'ID da conta'], ['account_name', 'Nome da conta'], ['campaign_id', 'ID da campanha'], ['campaign_name', 'Nome da campanha'], ['date', 'Data'],
  ['currency', 'Moeda'], ['impressions', 'Impressões'], ['clicks', 'Cliques'], ['cost', 'Custo'], ['conversions', 'Conversões'], ['conversion_value', 'Valor das conversões']];
const number = value => value === null || value === undefined || value === '' ? '—' : Number(value).toLocaleString('pt-BR');



function Status({map, value}) {
  const [label, color] = map[value] || [value || '—', 'gray'];
  return <BadgeWithDot type="pill-color" size="sm" color={color}>{label}</BadgeWithDot>;
}

function Progress({done, total}) {
  if (!total) return <span className="text-sm text-quaternary">—</span>;
  const share = total ? Math.round(done * 100 / total) : 0;
  return <div className="flex min-w-32 items-center gap-3">
    <span className="h-2 flex-1 overflow-hidden rounded-full bg-quaternary"><span className="block h-full rounded-full bg-brand-solid" style={{width: `${share}%`}}/></span>
    <span className="text-xs font-medium text-secondary tabular-nums">{number(done)}/{number(total)}</span>
  </div>;
}



/** Media files (exports and prints): upload, review row by row, then resolve conflicts between files. */
export function ImportsPage({data, reloadBootstrap, focusLibrary = false}) {
  const [view, setView] = useState(focusLibrary ? 'metrics' : 'files');
  const [items, setItems] = useState([]);
  const [customMetrics, setCustomMetrics] = useState([]);
  const [rangeSnapshots, setRangeSnapshots] = useState([]);
  const [conflicts, setConflicts] = useState([]);
  const [ready, setReady] = useState(true);
  const [detail, setDetail] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [note, setNote] = useState('');
  const activeClientRef = useRef(String(data.client.client_id));
  activeClientRef.current = String(data.client.client_id);
  const canEdit = data.client.role !== 'viewer';
  const query = `client_id=${data.client.client_id}`;

  const refresh = async () => {
    const clientId = String(data.client.client_id);
    const [body, pending, ranges] = await Promise.all([
      json(`${API}/imports?client_id=${clientId}`), json(`${API}/import-conflicts?client_id=${clientId}`), json(`${API}/import-ranges?client_id=${clientId}`),
    ]);
    if (activeClientRef.current !== clientId) return;
    setReady(body.ready); setItems(body.imports || []);
    setCustomMetrics(body.custom_metrics || ranges.custom_metrics || []);
    setConflicts(pending.conflicts || []); setRangeSnapshots(ranges.snapshots || []);
  };
  useEffect(() => {
    setItems([]); setCustomMetrics([]); setRangeSnapshots([]); setConflicts([]); setDetail(null);
    setBusy(false); setError(''); setNote(''); setView(focusLibrary ? 'metrics' : 'files');
    refresh().catch(failure => {if (activeClientRef.current === String(data.client.client_id)) setError(failure.message);});
  }, [data.client.client_id]);
  useEffect(() => {if (focusLibrary) setView('metrics');}, [focusLibrary]);

  const open = async id => {
    const clientId = String(data.client.client_id);
    try {
      const result = await json(`${API}/imports/${id}?client_id=${clientId}`);
      if (activeClientRef.current !== clientId) return;
      setDetail(result); setView('files'); setError('');
    } catch (failure) {if (activeClientRef.current === clientId) setError(failure.message);}
  };
  const run = async action => {
    setBusy(true); setError('');
    try {await action();} catch (failure) {setError(failure.message);} finally {setBusy(false);}
  };
  const afterChange = async () => {if (detail) await open(detail.import_file.id); await refresh(); await reloadBootstrap();};

  const tabs = [
    {id: 'files', label: 'Arquivos', count: items.length || undefined},
    {id: 'conflicts', label: 'Divergências', count: conflicts.length || undefined},
    {id: 'ranges', label: 'Períodos importados', count: rangeSnapshots.length || undefined},
    {id: 'metrics', label: 'Métricas personalizadas', count: customMetrics.length || undefined},
  ];
  return <div className="untitled-scope flex flex-col gap-6">
    <ReportsTabs label="Importações" items={tabs} value={view} onChange={value => {setView(value); setDetail(null);}}/>
    {error && <p role="alert" className="rounded-lg bg-error-primary px-4 py-3 text-sm text-error-primary ring-1 ring-error_subtle">{error}</p>}
    {note && <p role="status" className="rounded-lg bg-success-primary px-4 py-3 text-sm text-success-primary ring-1 ring-secondary">{note}</p>}
    {view === 'files' && !detail && <>
      <UploadCard data={data} ready={ready} canEdit={canEdit} busy={busy} run={run} onUploaded={async result => {
        setNote(result.duplicate ? 'Este arquivo já foi importado para este cliente.' : `${number(result.applied_count || 0)} de ${number(result.row_count || 0)} linhas prontas para reconciliação.`);
        await refresh(); await open(result.import_id); await reloadBootstrap();
      }}/>
      <FilesTable items={items} onOpen={open}/>
    </>}
    {view === 'files' && detail && <FileDetail detail={detail} data={data} canEdit={canEdit} busy={busy} run={run} setBusy={setBusy} setError={setError} onBack={() => setDetail(null)} onChanged={afterChange}
      onExtract={() => run(async () => {await json(`${API}/imports/${detail.import_file.id}/extract?${query}`, {method: 'POST', headers: {'X-CSRF-Token': data.csrf}}); await open(detail.import_file.id); await refresh();})}/>}
    {view === 'conflicts' && <Conflicts conflicts={conflicts} data={data} canEdit={canEdit} busy={busy} run={run} onResolved={async () => {await refresh(); await reloadBootstrap();}}/>}
    {view === 'ranges' && <Ranges snapshots={rangeSnapshots} onOpen={open}/>}
    {view === 'metrics' && <CustomMetrics metrics={customMetrics}/>}
  </div>;
}

function UploadCard({data, ready, canEdit, busy, run, onUploaded}) {
  const [file, setFile] = useState(null);
  const [platform, setPlatform] = useState('');
  const [currency, setCurrency] = useState('');
  const [dateOrder, setDateOrder] = useState('auto');
  const [drag, setDrag] = useState(false);
  const [invalid, setInvalid] = useState('');
  const input = useRef(null);
  const accept = selected => {
    if (!selected) return;
    if (!/\.(csv|xlsx|png|jpe?g|webp)$/i.test(selected.name || '')) {setFile(null); setInvalid('Escolha um arquivo CSV, XLSX, PNG, JPG ou WEBP.'); if (input.current) input.current.value = ''; return;}
    setInvalid(''); setFile(selected);
  };
  const clear = () => {setFile(null); if (input.current) input.current.value = '';};
  const submit = event => {
    event.preventDefault();
    if (!file) return;
    run(async () => {
      const payload = new FormData(); payload.append('file', file);
      if (platform) payload.append('platform_hint', platform);
      if (currency) payload.append('currency_hint', currency.toUpperCase());
      payload.append('date_order', dateOrder);
      const result = await json(`${API}/imports?client_id=${data.client.client_id}`, {method: 'POST', headers: {'X-CSRF-Token': data.csrf}, body: payload});
      clear();
      await onUploaded(result);
    });
  };
  return <Card title="Importar dados de mídia" description="Exportações CSV/XLSX ou prints da plataforma. Nada entra nos relatórios antes da sua revisão.">
    {!ready ? <Callout tone="error" title="Importações indisponíveis">A migração de importações precisa ser aplicada neste ambiente.</Callout>
      : !canEdit ? <p className="text-sm text-tertiary">Seu acesso permite consultar as importações, sem enviar arquivos.</p>
      : <form className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]" onSubmit={submit}>
        <label onDragEnter={event => {event.preventDefault(); setDrag(true);}} onDragOver={event => {event.preventDefault(); setDrag(true);}}
          onDragLeave={event => {if (!event.currentTarget.contains(event.relatedTarget)) setDrag(false);}} onDrop={event => {event.preventDefault(); setDrag(false); accept(event.dataTransfer.files?.[0]);}}
          className={`flex min-h-36 cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border px-6 py-4 text-center transition duration-100 ${drag ? 'border-brand bg-brand-primary' : 'border-secondary bg-primary hover:bg-primary_hover'}`}>
          <input ref={input} type="file" className="sr-only" accept=".csv,.xlsx,.png,.jpg,.jpeg,.webp" onChange={event => accept(event.target.files?.[0])}/>
          <span className="flex size-10 items-center justify-center rounded-lg bg-primary shadow-xs ring-1 ring-secondary">{file ? <FileCheck02 size={20} className="text-fg-brand-primary"/> : <UploadCloud02 size={20} className="text-fg-quaternary"/>}</span>
          {file ? <span className="flex max-w-full items-center gap-2 text-sm font-semibold text-primary"><span className="truncate">{file.name}</span>
            <button type="button" aria-label="Remover arquivo" onClick={event => {event.preventDefault(); clear();}} className="rounded p-0.5 text-fg-quaternary hover:bg-primary_hover"><XClose size={16}/></button></span>
            : <span className="text-sm"><span className="font-semibold text-brand-secondary">Clique para escolher</span> <span className="text-tertiary">ou arraste o arquivo</span></span>}
          <span className="text-xs text-tertiary">{file ? `${Math.max(1, Math.round(file.size / 1024)).toLocaleString('pt-BR')} KB` : 'CSV, XLSX, PNG, JPG ou WEBP · um arquivo por vez'}</span>
          {invalid && <span role="alert" className="text-xs text-error-primary">{invalid}</span>}
        </label>
        <div className="flex flex-col gap-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <ReportsFieldInput label="Plataforma" hint="Se não estiver no arquivo." value={platform} onChange={event => setPlatform(event.target.value)} placeholder="Ex.: Meta Ads"/>
            <ReportsFieldInput label="Moeda" hint="Se houver valores." maxLength={3} value={currency} onChange={event => setCurrency(event.target.value)} placeholder="BRL"/>
          </div>
          <ReportsNativeSelect label="Datas com barras" value={dateOrder} onChange={event => setDateOrder(event.target.value)}>
            <option value="auto">Detectar e pedir revisão quando ambíguas</option><option value="dmy">Dia/mês/ano</option><option value="mdy">Mês/dia/ano</option>
          </ReportsNativeSelect>
          <div className="mt-auto flex justify-end"><Button type="submit" size="md" color="primary" isDisabled={busy || !file} isLoading={busy}>Enviar e analisar</Button></div>
        </div>
      </form>}
  </Card>;
}

function FilesTable({items, onOpen}) {
  return <Card flush title="Arquivos recebidos" badge={<Badge type="pill-color" size="sm" color="gray">{items.length}</Badge>} description="Abra um arquivo para revisar linhas, mapear colunas ou conferir um print.">
    {items.length ? <div className="overflow-x-auto"><table className="w-full min-w-[640px]">
      <thead><tr><th className={TH}>Arquivo</th><th className={TH}>Estado</th><th className={TH}>Linhas aplicadas</th><th className={TH}>Recebido</th><th className={TH}><span className="sr-only">Ações</span></th></tr></thead>
      <tbody>{items.map(item => <tr key={item.id} className="hover:bg-primary_hover">
        <td className={TD}><p className="font-medium text-primary">{item.original_name}</p><p className="text-xs text-tertiary">{item.file_kind === 'image' ? 'Print' : (item.file_kind || 'arquivo').toUpperCase()}</p></td>
        <td className={TD}><Status map={FILE_STATUS} value={item.status}/></td>
        <td className={TD}><Progress done={item.applied_count} total={item.row_count}/></td>
        <td className={`${TD} whitespace-nowrap`}>{shortDate(item.created_at)}</td>
        <td className={`${TD} text-right`}><Button size="sm" color="secondary" onPress={() => onOpen(item.id)}>Revisar</Button></td>
      </tr>)}</tbody>
    </table></div> : <EmptyNote title="Nenhum arquivo ainda">Envie a primeira exportação ou print acima.</EmptyNote>}
  </Card>;
}

function FileDetail({detail, data, canEdit, busy, run, setBusy, setError, onBack, onChanged, onExtract}) {
  const [row, setRow] = useState(null);
  const [mapping, setMapping] = useState(false);
  const [scope, setScope] = useState(null);
  const file = detail.import_file;
  const image = file.file_kind === 'image';
  const pending = file.applied_count < file.row_count;
  return <>
    <div><Button size="sm" color="link-gray" iconLeading={ArrowLeft} onPress={onBack}>Arquivos</Button></div>
    <section className="rounded-xl bg-primary px-6 py-5 shadow-xs ring-1 ring-secondary">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2"><h2 className="truncate text-xl font-semibold text-primary">{file.original_name}</h2><Status map={FILE_STATUS} value={file.status}/></div>
          <p className="mt-0.5 text-sm text-tertiary">{image ? 'Print' : (file.file_kind || 'Arquivo').toUpperCase()}{file.platform_hint ? ` · ${file.platform_hint}` : ''}{image ? '' : ` · ${number(file.row_count)} ${file.row_count === 1 ? 'linha' : 'linhas'}`}</p>
        </div>
        {canEdit && <div className="flex shrink-0 gap-3">
          {!image && pending && <Button size="md" color="secondary" onPress={() => setMapping(true)}>Mapear colunas</Button>}
          {image && !detail.visual && <Button size="md" color="primary" iconLeading={Stars02} isDisabled={busy} isLoading={busy} onPress={onExtract}>Ler print com IA</Button>}
        </div>}
      </div>
      {!image && <div className="mt-4 max-w-sm"><Progress done={file.applied_count} total={file.row_count}/></div>}
      {(detail.column_maps || []).length > 0 && <ul className="mt-4 flex flex-col gap-1 border-t border-secondary pt-3">
        {detail.column_maps.map((item, index) => <li key={index} className="text-xs text-tertiary">Mapa aplicado em {shortDate(item.created_at)} · {number(item.applied_rows)} linhas reconhecidas · {item.note}</li>)}
      </ul>}
    </section>
    {image ? <PrintReview detail={detail} data={data} canEdit={canEdit} onCheck={setScope}/> : <RowsTable detail={detail} canEdit={canEdit} onReview={setRow}/>}
    <RowDrawer row={row} detail={detail} data={data} busy={busy} run={run} onClose={() => setRow(null)} onSaved={onChanged}/>
    <ColumnMappingDrawer open={mapping} detail={detail} data={data} busy={busy} setBusy={setBusy} setError={setError} onClose={() => setMapping(false)} onSaved={onChanged}/>
    <PrintDrawer scope={scope} detail={detail} data={data} busy={busy} run={run} onClose={() => setScope(null)} onSaved={onChanged}/>
  </>;
}

function RowsTable({detail, canEdit, onReview}) {
  const review = detail.rows.filter(row => row.status === 'needs_review').length;
  return <>
    <Card flush title="Linhas do arquivo" badge={review ? <Badge type="pill-color" size="sm" color="warning">{review} para revisar</Badge> : null} description="Até 100 linhas, com pendências primeiro.">
      {detail.rows.length ? <div className="overflow-x-auto"><table className="w-full min-w-[860px]">
        <thead><tr><th className={TH}>Linha</th><th className={TH}>Conta e campanha</th><th className={TH}>Atualização</th><th className={TH}>Data</th><th className={TH}>Estado</th><th className={TH}><span className="sr-only">Ações</span></th></tr></thead>
        <tbody>{detail.rows.map(row => {
          const parsed = row.parsed || {};
          const needs = row.status === 'needs_review';
          return <tr key={row.id} className={needs ? 'bg-warning-primary/40' : 'hover:bg-primary_hover'}>
            <td className={`${TD} whitespace-nowrap font-mono text-xs`}>{row.sheet_name} · {row.source_row}</td>
            <td className={TD}><p className="font-medium text-primary">{parsed.campaign_name || parsed.external_campaign_id || '—'}</p><p className="text-xs text-tertiary">{[parsed.platform, parsed.account_name || parsed.external_account_id].filter(Boolean).join(' · ') || 'Conta não identificada'}</p></td>
            <td className={TD}>{UPDATE_KIND[parsed.update_kind] || 'Análise pendente'}</td>
            <td className={`${TD} whitespace-nowrap`}>{row.metric_date ? shortDate(row.metric_date) : '—'}</td>
            <td className={TD}>
              <BadgeWithDot type="pill-color" size="sm" color={needs ? 'warning' : 'success'}>{needs ? 'Revisar' : row.decision_note ? 'Confirmada' : 'Incluída'}</BadgeWithDot>
              {(row.reason || row.decision_note) && <p className="mt-1 max-w-72 text-xs text-tertiary">{row.reason || row.decision_note}</p>}
            </td>
            <td className={`${TD} text-right`}>{needs && canEdit && <Button size="sm" color="secondary" onPress={() => onReview(row)}>Revisar</Button>}</td>
          </tr>;
        })}</tbody>
      </table></div> : <EmptyNote title="Nenhuma linha lida">Confira o formato do arquivo ou mapeie as colunas.</EmptyNote>}
    </Card>
    {(detail.custom_values || []).length > 0 && <Card title="Métricas personalizadas deste arquivo" description="Campos adicionais preservados como chave e valor.">
      <ul className="flex flex-col gap-2">{detail.custom_values.map((metric, index) => <li key={`${metric.import_row_id}:${metric.metric_key}:${index}`} className="text-sm text-secondary">
        <span className="font-medium text-primary">{metric.metric_label}</span> <span className="font-mono text-xs text-tertiary">{metric.metric_key}</span> · {metric.campaign_name}: <span className="font-semibold tabular-nums">{number(metric.value_numeric)}</span> {metric.currency || metric.unit}
        {Object.values(metric.dimensions || {}).map(dimension => ` · ${dimension.label}: ${dimension.value}`).join('')}
      </li>)}</ul>
    </Card>}
  </>;
}

function PrintReview({detail, data, canEdit, onCheck}) {
  const scopes = detail.visual?.result?.scopes || [];
  return <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
    <section className="overflow-hidden rounded-xl bg-primary shadow-xs ring-1 ring-secondary lg:sticky lg:top-4">
      <img className="block w-full" src={`${API}/imports/${detail.import_file.id}/image?client_id=${data.client.client_id}`} alt={`Print enviado: ${detail.import_file.original_name}`}/>
    </section>
    <div className="flex flex-col gap-4">
      {!detail.visual ? <Callout title="Print recebido">A leitura com IA consome créditos Cadu e só sugere valores com evidência. Nada é confirmado sem a sua conferência.</Callout>
        : <>
          <p className="text-sm text-tertiary">Leitura sugerida por {detail.visual.model}. Confira cada bloco com o print antes de confirmar.</p>
          {!scopes.length && <Callout tone="warning" title="Nada legível">Envie uma imagem mais nítida ou um export CSV/XLSX.</Callout>}
          {scopes.map((scope, index) => {
            const daily = scope.granularity === 'day' && scope.period_start && scope.period_start === scope.period_end;
            const range = scope.granularity === 'range' || Boolean(scope.period_start && scope.period_end && scope.period_start !== scope.period_end);
            const confirmed = detail.rows.some(row => row.sheet_name === 'Print' && row.source_row === index + 1);
            const snapshot = (detail.range_snapshots || []).find(item => item.scope_index === index);
            return <section key={index} className="rounded-xl bg-primary px-5 py-4 shadow-xs ring-1 ring-secondary">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-xs font-medium text-tertiary">Bloco {index + 1} · {scope.platform || 'Plataforma não identificada'}</p>
                  <h3 className="truncate text-md font-semibold text-primary">{scope.campaign_name || scope.campaign_id || 'Campanha sem identificação'}</h3>
                  <p className="text-xs text-tertiary">{scope.account_name || scope.account_id || 'Conta não identificada'} · {scope.period_start ? `${shortDate(scope.period_start)}${scope.period_end && scope.period_end !== scope.period_start ? ` a ${shortDate(scope.period_end)}` : ''}` : 'Período não identificado'}{scope.currency ? ` · ${scope.currency}` : ''}</p>
                </div>
                {confirmed || snapshot ? <BadgeWithDot type="pill-color" size="sm" color="success">Confirmado</BadgeWithDot> : null}
              </div>
              {scope.metrics?.length ? <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-3">{scope.metrics.map((metric, metricIndex) => <div key={metricIndex}>
                <dt className="text-xs text-tertiary">{metric.label}</dt><dd className="text-sm font-semibold text-primary tabular-nums">{metric.raw_value} <span className="text-xs font-normal text-tertiary">{metric.unit}</span></dd>
              </div>)}</dl> : <p className="mt-3 text-sm text-tertiary">Sem métricas legíveis neste bloco.</p>}
              {scope.evidence && <p className="mt-3 text-xs text-quaternary">Evidência: {scope.evidence}</p>}
              <div className="mt-3 flex justify-end">
                {snapshot ? <p className="text-xs text-tertiary">Intervalo {shortDate(snapshot.period_start)} a {shortDate(snapshot.period_end)} confirmado. {snapshot.note}</p>
                  : confirmed ? <p className="text-xs text-tertiary">Dia incluído nas observações.</p>
                  : (daily || range) ? canEdit && <Button size="sm" color="secondary" onPress={() => onCheck({scope, index, daily})}>{daily ? 'Conferir dia' : 'Conferir total do intervalo'}</Button>
                  : <p className="text-xs text-tertiary">Período indefinido: fica como evidência até as datas serem identificadas.</p>}
              </div>
            </section>;
          })}
          {(detail.visual.result.questions || []).map((question, index) => <Callout key={index} tone="brand">{question}</Callout>)}
        </>}
    </div>
  </div>;
}

function FieldGrid({fields, draft, setDraft}) {
  return <div className="grid gap-4 sm:grid-cols-2">{fields.map(([key, label]) => <ReportsFieldInput key={key} label={label} value={draft[key] || ''} onChange={event => setDraft({...draft, [key]: event.target.value})}
    className={/_id$|date|period/.test(key) ? 'font-mono' : undefined}/>)}</div>;
}

function FormSection({title, children}) {
  return <fieldset className="flex flex-col gap-4"><legend className="mb-3 text-sm font-semibold text-primary">{title}</legend>{children}</fieldset>;
}

function RowDrawer({row, detail, data, busy, run, onClose, onSaved}) {
  const [draft, setDraft] = useState({});
  useEffect(() => {if (row) setDraft({...row.parsed, metric_date: row.parsed.metric_date || '', ...row.parsed.metrics, create_campaign: row.parsed.campaign_match?.state === 'missing', note: ''});}, [row]);
  const missing = draft.campaign_match?.state === 'missing';
  const submit = event => {
    event.preventDefault();
    run(async () => {
      const payload = Object.fromEntries([...IDENTITY, ['metric_date'], ...METRICS, ['note']].map(([key]) => [key, String(draft[key] || '')]));
      payload.create_campaign = Boolean(draft.create_campaign);
      await json(`${API}/imports/${detail.import_file.id}/rows/${row.id}/resolve?client_id=${data.client.client_id}`, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': data.csrf}, body: JSON.stringify(payload)});
      onClose(); await onSaved();
    });
  };
  return <ReportsDrawer size="lg" open={Boolean(row)} onOpenChange={value => {if (!value) onClose();}} title="Revisar linha" context={row ? `${row.sheet_name} · linha ${row.source_row}` : ''}
    description={draft.update_kind ? `Identificada como ${UPDATE_KIND_LONG[draft.update_kind]}.` : 'Confira os valores com o export original.'}>
    <form className="untitled-scope flex flex-col gap-6" onSubmit={submit}>
      {missing && <Callout tone="warning" title="Campanha não encontrada">
        Não localizamos {draft.campaign_name} ({draft.platform} · conta {draft.external_account_id} · campanha {draft.external_campaign_id}).
        {!draft.campaign_match?.account_id && ' Se a conta ainda não existir, os campos abaixo criam o vínculo.'}
        <label className="mt-3 flex items-center gap-2 font-medium text-primary"><input type="checkbox" className="size-4 accent-brand-600" checked={Boolean(draft.create_campaign)} onChange={event => setDraft({...draft, create_campaign: event.target.checked})}/>Criar a campanha e associar esta linha</label>
      </Callout>}
      <FormSection title="Identificação"><FieldGrid fields={[...IDENTITY, ['metric_date', 'Data (AAAA-MM-DD)']]} draft={draft} setDraft={setDraft}/></FormSection>
      <FormSection title="Métricas"><FieldGrid fields={METRICS} draft={draft} setDraft={setDraft}/></FormSection>
      <ReportsFieldInput label="Justificativa" required maxLength={1000} value={draft.note || ''} onChange={event => setDraft({...draft, note: event.target.value})} placeholder="Ex.: data e conta conferidas no export original"/>
      <DrawerActions onCancel={onClose} busy={busy} label="Confirmar linha" disabled={missing && !draft.create_campaign}/>
    </form>
  </ReportsDrawer>;
}

function ColumnMappingDrawer({open, detail, data, busy, setBusy, setError, onClose, onSaved}) {
  const [mapping, setMapping] = useState({});
  const [localSuggestion, setLocalSuggestion] = useState(null);
  const [platformHint, setPlatformHint] = useState(detail.import_file.platform_hint || '');
  const [currencyHint, setCurrencyHint] = useState('');
  const [dateOrder, setDateOrder] = useState('auto');
  const [note, setNote] = useState('');
  const evidenceKey = `${detail.import_file.id}:${detail.column_evidence_fingerprint || ''}`;
  const evidenceKeyRef = useRef(evidenceKey);
  evidenceKeyRef.current = evidenceKey;
  const suggestions = localSuggestion?.key === evidenceKey ? localSuggestion.value : detail.column_suggestions || null;
  const suggest = async () => {
    const requestedKey = evidenceKey;
    setBusy(true); setError('');
    try {
      const value = await json(`${API}/imports/${detail.import_file.id}/suggest-columns?client_id=${data.client.client_id}`, {method: 'POST', headers: {'X-CSRF-Token': data.csrf}});
      if (requestedKey === evidenceKeyRef.current && value.suggestion?.result?.evidence_fingerprint === detail.column_evidence_fingerprint) setLocalSuggestion({key: requestedKey, value: value.suggestion});
    } catch (failure) {setError(failure.message);} finally {setBusy(false);}
  };
  const submit = async event => {
    event.preventDefault(); setBusy(true); setError('');
    try {
      const chosen = Object.fromEntries(Object.entries(mapping).filter(([, header]) => header));
      await json(`${API}/imports/${detail.import_file.id}/map-columns?client_id=${data.client.client_id}`, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': data.csrf},
        body: JSON.stringify({mapping: chosen, platform_hint: platformHint, currency_hint: currencyHint, date_order: dateOrder, note})});
      onClose(); await onSaved();
    } catch (failure) {setError(failure.message);} finally {setBusy(false);}
  };
  return <ReportsDrawer size="lg" open={open} onOpenChange={value => {if (!value) onClose();}} title="Mapear colunas" context={detail.import_file.original_name}
    description={`${detail.headers.length} cabeçalhos detectados. O mapa vale para as linhas pendentes; o arquivo original fica preservado.`}>
    <form className="untitled-scope flex flex-col gap-6" onSubmit={submit}>
      {suggestions ? <Callout tone="brand" title="Sugestões do TypeSafe">
        <p>Concentração entre alternativas, não garantia de acerto. Nada é aplicado sem você confirmar.</p>
        {suggestions.result.suggestions.length ? <ul className="mt-3 flex flex-col gap-2">{suggestions.result.suggestions.map((item, index) => <li key={`${item.header}:${index}`} className="flex flex-wrap items-center justify-between gap-2">
          <span><span className="font-medium text-primary">{item.header}</span> → {MAP_FIELDS.find(([key]) => key === item.field)?.[1] || 'Sem correspondência'} <span className="text-xs text-tertiary">· {Math.round(item.confidence * 100)}%</span></span>
          {item.field !== 'none' && <Button size="sm" color="link-color" onPress={() => setMapping({...mapping, [item.field]: item.header})}>Usar</Button>}
        </li>)}</ul> : <p className="mt-2">Nenhum cabeçalho desconhecido.</p>}
        {suggestions.result.omitted_count > 0 && <p className="mt-2">{suggestions.result.omitted_count} cabeçalhos ficaram de fora; mapeie manualmente.</p>}
      </Callout> : <div className="flex items-center justify-between gap-3 rounded-lg bg-secondary_subtle p-4 ring-1 ring-secondary ring-inset">
        <p className="text-sm text-secondary">Deixe o TypeSafe sugerir o mapa a partir dos cabeçalhos.</p>
        <Button size="sm" color="secondary" iconLeading={Stars02} isDisabled={busy} onPress={suggest}>Sugerir</Button>
      </div>}
      <FormSection title="Colunas"><div className="grid gap-4 sm:grid-cols-2">{MAP_FIELDS.map(([key, label]) => <ReportsNativeSelect key={key} label={label} value={mapping[key] || ''} onChange={event => setMapping({...mapping, [key]: event.target.value})}>
        <option value="">Leitura automática</option>{detail.headers.map(header => <option key={header} value={header}>{header}</option>)}
      </ReportsNativeSelect>)}</div></FormSection>
      <FormSection title="Quando faltar no arquivo"><div className="grid gap-4 sm:grid-cols-3">
        <ReportsFieldInput label="Plataforma" value={platformHint} onChange={event => setPlatformHint(event.target.value)} placeholder="Meta Ads"/>
        <ReportsFieldInput label="Moeda" maxLength={3} value={currencyHint} onChange={event => setCurrencyHint(event.target.value)} placeholder="BRL"/>
        <ReportsNativeSelect label="Formato de data" value={dateOrder} onChange={event => setDateOrder(event.target.value)}><option value="auto">Detectar</option><option value="dmy">Dia/mês/ano</option><option value="mdy">Mês/dia/ano</option></ReportsNativeSelect>
      </div></FormSection>
      <ReportsFieldInput label="Justificativa" required maxLength={1000} value={note} onChange={event => setNote(event.target.value)} placeholder="Ex.: cabeçalhos do export conferidos"/>
      <DrawerActions onCancel={onClose} busy={busy} label="Aplicar às linhas pendentes"/>
    </form>
  </ReportsDrawer>;
}

const METRIC_ALIASES = {impressions: 'impressions', impressoes: 'impressions', clicks: 'clicks', cliques: 'clicks', cost: 'cost', spend: 'cost', gasto: 'cost', custo: 'cost',
  conversions: 'conversions', conversoes: 'conversions', 'conversion value': 'conversion_value', 'valor de conversao': 'conversion_value'};

function PrintDrawer({scope: active, detail, data, busy, run, onClose, onSaved}) {
  const [draft, setDraft] = useState({});
  const [createCampaign, setCreateCampaign] = useState(false);
  const [match, setMatch] = useState(null);
  useEffect(() => {
    if (!active) return;
    const {scope} = active;
    const metrics = {};
    for (const metric of scope.metrics || []) {
      const key = METRIC_ALIASES[metric.label.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').trim()];
      if (key) metrics[key] = metric.raw_value;
    }
    setDraft({platform: scope.platform || '', external_account_id: scope.account_id || '', account_name: scope.account_name || '', external_campaign_id: scope.campaign_id || '',
      campaign_name: scope.campaign_name || '', metric_date: scope.period_start || '', period_start: scope.period_start || '', period_end: scope.period_end || '',
      currency: scope.currency || '', impressions: '', clicks: '', cost: '', conversions: '', conversion_value: '', ...metrics, note: ''});
    setCreateCampaign(false); setMatch(null);
  }, [active]);
  useEffect(() => {
    let live = true;
    if (!active || !draft.platform || !draft.external_account_id || !draft.external_campaign_id) {setMatch(null); return () => {live = false;};}
    const params = new URLSearchParams({client_id: String(data.client.client_id), platform: draft.platform, account_id: draft.external_account_id, campaign_id: draft.external_campaign_id});
    fetch(`${API}/imports/${detail.import_file.id}/campaign-match?${params}`, {credentials: 'same-origin'})
      .then(response => response.ok ? response.json() : Promise.reject(new Error('Falha ao verificar campanha')))
      .then(value => {if (live) {setMatch(value.match); setCreateCampaign(value.match?.state === 'missing');}})
      .catch(() => {if (live) setMatch({state: 'unmatched'});});
    return () => {live = false;};
  }, [active, draft.platform, draft.external_account_id, draft.external_campaign_id, data.client.client_id]);
  const daily = active?.daily;
  const submit = event => {
    event.preventDefault();
    run(async () => {
      const {metric_date, period_start, period_end, ...shared} = draft;
      const payload = daily ? {...shared, metric_date, create_campaign: createCampaign} : {...shared, period_start, period_end, create_campaign: createCampaign};
      await json(`${API}/imports/${detail.import_file.id}/visual/${active.index}/${daily ? 'confirm' : 'range'}?client_id=${data.client.client_id}`,
        {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': data.csrf}, body: JSON.stringify(payload)});
      onClose(); await onSaved();
    });
  };
  return <ReportsDrawer size="lg" open={Boolean(active)} onOpenChange={value => {if (!value) onClose();}} title={daily ? 'Conferir dia' : 'Conferir total do intervalo'} context={active ? `Bloco ${active.index + 1}` : ''}
    description="A associação é conferida por plataforma, conta e ID da campanha antes de gravar.">
    <form className="untitled-scope flex flex-col gap-6" onSubmit={submit}>
      <FormSection title="Identificação"><FieldGrid fields={[...IDENTITY, ...(daily ? [['metric_date', 'Data (AAAA-MM-DD)']] : [['period_start', 'Início (AAAA-MM-DD)'], ['period_end', 'Fim (AAAA-MM-DD)']])]} draft={draft} setDraft={setDraft}/></FormSection>
      {match?.state === 'matched' && <Callout title="Campanha encontrada">{match.campaign_name} · {match.account_name}</Callout>}
      {match?.state === 'missing' && <Callout tone="warning" title="Campanha não encontrada">Não localizamos {draft.campaign_name} na conta informada.
        <label className="mt-3 flex items-center gap-2 font-medium text-primary"><input type="checkbox" className="size-4 accent-brand-600" checked={createCampaign} onChange={event => setCreateCampaign(event.target.checked)}/>Criar a campanha e guardar os dados do print</label></Callout>}
      {match?.state === 'unmatched' && <Callout tone="error">{match.reason || 'Complete plataforma, ID da conta e ID da campanha para validar a associação.'}</Callout>}
      <FormSection title="Métricas"><FieldGrid fields={METRICS} draft={draft} setDraft={setDraft}/></FormSection>
      <ReportsFieldInput label="Justificativa" required maxLength={1000} value={draft.note || ''} onChange={event => setDraft({...draft, note: event.target.value})} placeholder="Conferi números, IDs e período no print"/>
      <DrawerActions onCancel={onClose} busy={busy} label={daily ? 'Confirmar dia' : 'Confirmar intervalo'} disabled={!match || match.state === 'unmatched' || (match.state === 'missing' && !createCampaign)}/>
    </form>
  </ReportsDrawer>;
}

function Conflicts({conflicts, data, canEdit, busy, run, onResolved}) {
  const [choices, setChoices] = useState({});
  const [reasons, setReasons] = useState({});
  if (!conflicts.length) return <Card><EmptyNote title="Nenhuma divergência">Quando dois arquivos trouxerem valores diferentes para o mesmo dia, a escolha aparece aqui.</EmptyNote></Card>;
  return <div className="flex flex-col gap-4">
    <p className="text-sm text-tertiary">Arquivos diferentes trouxeram valores distintos para o mesmo dia e métrica. Escolha o valor certo; o histórico fica preservado.</p>
    {conflicts.map(conflict => {
      const key = `${conflict.campaign_id}:${conflict.metric_date}:${conflict.metric_key}`;
      const chosen = String(choices[key] || conflict.candidates[0]?.id || '');
      const submit = event => {
        event.preventDefault();
        run(async () => {
          await json(`${API}/import-conflicts/${conflict.campaign_id}/${conflict.metric_date}/${conflict.metric_key}/resolve?client_id=${data.client.client_id}`,
            {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': data.csrf}, body: JSON.stringify({observation_id: choices[key] || conflict.candidates[0]?.id, note: reasons[key] || ''})});
          await onResolved();
          setChoices(current => {const next = {...current}; delete next[key]; return next;});
          setReasons(current => {const next = {...current}; delete next[key]; return next;});
        });
      };
      return <section key={key} className="rounded-xl bg-primary px-6 py-5 shadow-xs ring-1 ring-secondary">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0"><h3 className="text-md font-semibold text-primary">{conflict.campaign_name}</h3><p className="text-sm text-tertiary">{conflict.platform} · {conflict.account_name}</p></div>
          <div className="flex items-center gap-2"><Badge type="color" size="sm" color="gray">{shortDate(conflict.metric_date)}</Badge><Badge type="color" size="sm" color="gray"><span className="font-mono">{conflict.metric_key}</span></Badge><Badge type="pill-color" size="sm" color="warning">{conflict.version_count} valores</Badge></div>
        </div>
        <form className="mt-4 flex flex-col gap-4" onSubmit={submit}>
          <div role="radiogroup" aria-label="Valor correto" className="flex flex-col gap-2">
            {conflict.candidates.map(candidate => {
              const on = chosen === String(candidate.id);
              return <label key={candidate.id} className={`flex cursor-pointer items-center gap-3 rounded-lg px-4 py-3 ring-1 ring-inset ${on ? 'bg-brand-primary ring-brand' : 'ring-secondary hover:bg-primary_hover'} ${canEdit ? '' : 'pointer-events-none'}`}>
                {canEdit && <input type="radio" className="size-4 accent-brand-600" name={key} checked={on} onChange={() => setChoices({...choices, [key]: candidate.id})}/>}
                <span className="min-w-28 text-md font-semibold text-primary tabular-nums">{number(candidate.value_numeric)} <span className="text-xs font-normal text-tertiary">{candidate.currency || ''}</span></span>
                <span className="min-w-0 flex-1 truncate text-sm text-secondary">{candidate.original_name}{Object.values(candidate.dimensions || {}).map(dimension => ` · ${dimension.label}: ${dimension.value}`).join('')}</span>
                <span className="text-xs whitespace-nowrap text-tertiary">{shortDate(candidate.created_at)}</span>
              </label>;
            })}
          </div>
          {canEdit && <div className="flex flex-wrap items-end gap-3">
            <div className="min-w-64 flex-1"><ReportsFieldInput label="Justificativa" required maxLength={1000} value={reasons[key] || ''} onChange={event => setReasons({...reasons, [key]: event.target.value})} placeholder="Ex.: export mais recente conferido na plataforma"/></div>
            <Button type="submit" size="md" color="primary" isDisabled={busy || !conflict.candidates.length}>Confirmar valor</Button>
          </div>}
        </form>
      </section>;
    })}
  </div>;
}

function Ranges({snapshots, onOpen}) {
  return <Card flush title="Períodos importados" description="Totais de intervalo confirmados em prints. Ficam separados das métricas diárias e não são somados a elas.">
    {snapshots.length ? <div className="overflow-x-auto"><table className="w-full min-w-[760px]">
      <thead><tr><th className={TH}>Campanha</th><th className={TH}>Período</th><th className={TH}>Métricas do intervalo</th><th className={TH}>Origem</th><th className={TH}><span className="sr-only">Ações</span></th></tr></thead>
      <tbody>{snapshots.map(snapshot => <tr key={snapshot.id} className="hover:bg-primary_hover">
        <td className={TD}><p className="font-medium text-primary">{snapshot.campaign_name}</p><p className="text-xs text-tertiary">{snapshot.platform} · {snapshot.account_name}</p></td>
        <td className={`${TD} whitespace-nowrap`}>{shortDate(snapshot.period_start)} a {shortDate(snapshot.period_end)}</td>
        <td className={TD}><div className="flex flex-wrap gap-1.5">{snapshot.metrics.map(metric => <Badge key={metric.metric_key} type="color" size="sm" color="gray">{metric.metric_key}: {number(metric.value_numeric)} {metric.currency || metric.unit}</Badge>)}</div></td>
        <td className={`${TD} max-w-56 truncate`}>{snapshot.original_name}</td>
        <td className={`${TD} text-right`}><Button size="sm" color="secondary" onPress={() => onOpen(snapshot.import_id)}>Abrir print</Button></td>
      </tr>)}</tbody>
    </table></div> : <EmptyNote title="Nenhum período importado">Totais de período confirmados em prints aparecem aqui.</EmptyNote>}
  </Card>;
}

function CustomMetrics({metrics}) {
  return <Card flush title="Métricas personalizadas" badge={<Badge type="pill-color" size="sm" color="gray">{metrics.length}</Badge>} description="Campos adicionais dos canais, guardados com dimensão, unidade e arquivo de origem.">
    {metrics.length ? <div id="reports-data-library" className="overflow-x-auto"><table className="w-full min-w-[860px]">
      <thead><tr><th className={TH}>Canal</th><th className={TH}>Métrica</th><th className={TH}>Dimensão</th><th className={TH}>Data</th><th className={`${TH} text-right`}>Último valor</th><th className={`${TH} text-right`}>Observações</th></tr></thead>
      <tbody>{metrics.map((metric, index) => <tr key={`${metric.campaign_id}:${metric.channel}:${metric.metric_key}:${metric.metric_date}:${index}`} className="hover:bg-primary_hover">
        <td className={TD}>{metric.channel}</td>
        <td className={TD}><p className="font-medium text-primary">{metric.metric_label}</p><p className="font-mono text-xs text-tertiary">{metric.metric_key}</p></td>
        <td className={TD}>{Object.values(metric.dimensions || {}).map(dimension => `${dimension.label}: ${dimension.value}`).join(' · ') || '—'}</td>
        <td className={`${TD} whitespace-nowrap`}>{shortDate(metric.metric_date)}</td>
        <td className={`${TD} text-right font-semibold text-primary tabular-nums`}>{number(metric.latest_value)} <span className="text-xs font-normal text-tertiary">{metric.currency || metric.unit}</span></td>
        <td className={`${TD} text-right tabular-nums`}>{number(metric.observations)}</td>
      </tr>)}</tbody>
    </table></div> : <EmptyNote title="Nenhuma métrica personalizada">Campos numéricos extras dos exports aparecem aqui como chave e valor.</EmptyNote>}
  </Card>;
}
