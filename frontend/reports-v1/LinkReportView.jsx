import React, {useEffect, useMemo, useRef, useState} from 'react';
import {ChevronDown, Copy01, Expand01, LinkExternal01, Minimize01, SearchLg, XClose} from '@untitledui/icons';
import {Badge} from '../cadu-design-system/untitled-kit/badges.tsx';
import {KindIcon, LINK_KIND_META} from './linkKinds.jsx';

/**
 * The detailed Link Tester report (same structure the public page renders): score gauge, clickable indicators,
 * module bars, a section index that follows the scroll, collapsible sections, filterable checks and screenshots.
 */
const TONE = {ok: '#12b76a', warn: '#f79009', bad: '#f04438', info: '#3974bd', muted: '#98a2b3', skip: '#98a2b3'};
const BADGE = {ok: 'success', warn: 'warning', bad: 'error', info: 'blue', muted: 'gray', skip: 'gray'};
const Dot = ({tone, size = 9}) => <span aria-hidden="true" className="inline-block shrink-0 rounded-full" style={{width: size, height: size, background: TONE[tone] || TONE.muted}}/>;
const fullDate = value => value ? new Date(value).toLocaleString('pt-BR', {dateStyle: 'medium', timeStyle: 'short'}) : '';

function Gauge({score, tone}) {
  const [shown, setShown] = useState(0);
  useEffect(() => {const frame = requestAnimationFrame(() => setShown(score || 0)); return () => cancelAnimationFrame(frame);}, [score]);
  const length = 2 * Math.PI * 52;
  return <div className="relative size-28 shrink-0" role="img" aria-label={`Nota ${score ?? 0} de 100`}>
    <svg viewBox="0 0 120 120" className="size-full -rotate-90"><circle cx="60" cy="60" r="52" fill="none" stroke="var(--color-bg-quaternary, #e4eaf2)" strokeWidth="10"/>
      <circle cx="60" cy="60" r="52" fill="none" stroke={TONE[tone]} strokeWidth="10" strokeLinecap="round" strokeDasharray={`${length * shown / 100} ${length}`} style={{transition: 'stroke-dasharray 900ms ease-out'}}/></svg>
    <div className="absolute inset-0 flex flex-col items-center justify-center"><span className="text-3xl font-semibold text-primary tabular-nums">{score ?? '–'}</span><span className="text-xs text-tertiary">de 100</span></div>
  </div>;
}

function Bar({label, value, max = 100, tone, detail}) {
  const pct = Math.max(0, Math.min(100, Math.round((value || 0) * 100 / (max || 100))));
  return <div className="text-sm">
    <div className="flex justify-between gap-2"><span className="text-secondary">{label}</span><span className="font-semibold text-primary tabular-nums">{value ?? '–'}{max === 100 ? '' : `/${max}`}</span></div>
    <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-quaternary"><div className="h-2 rounded-full" style={{width: `${pct}%`, background: TONE[tone] || TONE.info, transition: 'width 700ms ease-out'}}/></div>
    {detail && <p className="mt-1 text-xs text-tertiary">{detail}</p>}
  </div>;
}

function Checks({items}) {
  const [onlyProblems, setOnlyProblems] = useState(false);
  const [query, setQuery] = useState('');
  const problems = items.filter(item => item.status === 'bad' || item.status === 'warn').length;
  const visible = items.filter(item => (!onlyProblems || item.status === 'bad' || item.status === 'warn')
    && (!query || `${item.title} ${item.detail || ''} ${item.group || ''}`.toLowerCase().includes(query.toLowerCase())));
  return <div>
    {items.length > 6 && <div className="mb-2 flex flex-wrap items-center gap-2">
      {[[false, `Todas (${items.length})`], [true, `Só problemas (${problems})`]].map(([value, label]) => <button key={label} type="button" aria-pressed={onlyProblems === value} onClick={() => setOnlyProblems(value)}
        className={`rounded-full px-3 py-1 text-xs font-semibold ring-1 ring-inset ${onlyProblems === value ? 'bg-primary-solid text-white ring-transparent' : 'text-tertiary ring-secondary hover:text-secondary'}`}>{label}</button>)}
      <label className="relative ml-auto w-52 max-w-full"><span className="sr-only">Filtrar checagens</span><SearchLg size={14} aria-hidden="true" className="pointer-events-none absolute top-1/2 left-2.5 -translate-y-1/2 text-fg-quaternary"/>
        <input type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Filtrar" style={{paddingLeft: 28, paddingRight: 8}} className="h-8 w-full rounded-lg bg-primary text-xs text-primary ring-1 ring-primary outline-none ring-inset focus:ring-2 focus:ring-brand"/></label>
    </div>}
    <ul className="flex flex-col divide-y divide-secondary">{visible.map((item, index) => <li key={index} className="flex gap-3 py-3">
      <span className="mt-1.5"><Dot tone={item.status}/></span>
      <div className="min-w-0 text-sm"><p className="font-medium text-primary">{item.title}{item.group && <span className="ml-1 text-xs font-normal text-tertiary">· {item.group}</span>}</p>
        {item.detail && <p className="mt-0.5 text-secondary">{item.detail}</p>}{item.fix && <p className="mt-1 text-brand-secondary">→ {item.fix}</p>}</div>
    </li>)}</ul>
    {!visible.length && <p className="py-3 text-sm text-tertiary">Nada com esse filtro.</p>}
  </div>;
}

function Block({block}) {
  const title = block.title && <h4 className="mb-2 text-xs font-semibold tracking-wide text-tertiary uppercase">{block.title}</h4>;
  if (block.type === 'kv') return <div>{title}<dl className="divide-y divide-secondary">{block.rows.map((row, index) => <div key={index} className="grid gap-x-4 py-2 text-sm sm:grid-cols-[minmax(10rem,35%)_1fr]">
    <dt className="text-tertiary">{row.label}</dt><dd className={`min-w-0 break-words text-primary ${row.mono ? 'font-mono text-xs' : ''}`}>{row.tone ? <Badge type="pill-color" size="sm" color={BADGE[row.tone] || 'gray'}>{String(row.value)}</Badge> : String(row.value)}</dd></div>)}</dl></div>;
  if (block.type === 'chips') return <div>{title}<div className="flex flex-wrap gap-1.5">{block.items.map((chip, index) => <span key={index} title={chip.detail || ''}
    className="inline-flex flex-col rounded-lg px-2.5 py-1 text-xs font-semibold" style={{background: `${TONE[chip.tone] || TONE.muted}1a`, color: chip.tone === 'muted' ? '#667085' : TONE[chip.tone]}}>{chip.label}{chip.detail && <small className="font-medium opacity-80">{chip.detail}</small>}</span>)}</div></div>;
  if (block.type === 'checks') return <div>{title}<Checks items={block.items}/></div>;
  if (block.type === 'list') return <div>{title}<ul className="flex flex-col gap-1.5">{block.items.map((item, index) => <li key={index} className="flex gap-2.5 text-sm text-secondary"><span className="mt-1.5"><Dot tone={item.tone}/></span>{item.text}</li>)}</ul></div>;
  if (block.type === 'table') return <div>{title}<div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr>{block.columns.map(column => <th key={column} className="border-b border-secondary py-2 pr-3 text-left text-xs font-semibold text-tertiary">{column}</th>)}</tr></thead>
    <tbody className="divide-y divide-secondary">{block.rows.map((row, index) => <tr key={index}>{row.map((cell, cellIndex) => <td key={cellIndex} className={`py-2 pr-3 align-top break-words ${cellIndex === 0 ? 'font-medium text-primary' : 'text-secondary'}`}>{cell}</td>)}</tr>)}</tbody></table></div></div>;
  if (block.type === 'chain') return <div>{title}<ol className="relative ml-2 border-l-2 border-dashed border-secondary pl-4">{block.steps.map((step, index) => {
    const tone = (step.status || 0) >= 400 ? 'bad' : (step.status || 0) >= 300 ? 'warn' : 'ok';
    return <li key={index} className="relative py-1.5 text-sm"><span className="absolute top-3 -left-[23px] size-3 rounded-full ring-2 ring-white" style={{background: TONE[tone]}}/>
      <Badge type="color" size="sm" color={BADGE[tone]}>{step.status || '–'}</Badge> <span className="font-mono text-xs break-all text-secondary">{step.url}</span></li>;
  })}</ol></div>;
  if (block.type === 'bars') return <div>{title}<div className="grid gap-3 sm:grid-cols-2">{block.items.map((item, index) => <Bar key={index} {...item}/>)}</div></div>;
  if (block.type === 'text') return <p className="text-sm leading-6 text-secondary">{block.text}</p>;
  return null;
}

function Screenshots({shots}) {
  const [device, setDevice] = useState(shots.desktop ? 'desktop' : 'mobile');
  const [zoom, setZoom] = useState(false);
  const src = shots[device];
  if (!shots.desktop && !shots.mobile) return <p className="text-sm text-tertiary">{shots.note || 'Esta análise não tem print guardado.'}</p>;
  return <div>
    <div className="mb-3 flex items-center gap-1 rounded-lg bg-secondary_subtle p-0.5 ring-1 ring-secondary ring-inset" style={{width: 'fit-content'}}>
      {[['desktop', 'Desktop'], ['mobile', 'Celular']].filter(([key]) => shots[key]).map(([key, label]) => <button key={key} type="button" aria-pressed={device === key} onClick={() => setDevice(key)}
        className={`rounded-md px-3 py-1 text-sm font-medium ${device === key ? 'bg-primary text-primary shadow-xs' : 'text-tertiary'}`}>{label}</button>)}
    </div>
    <button type="button" onClick={() => setZoom(true)} className="block cursor-zoom-in" aria-label="Ampliar print">
      <img src={src} alt={`Print da página (${device === 'mobile' ? 'celular' : 'desktop'})`} className={`rounded-lg ring-1 ring-secondary ${device === 'mobile' ? 'max-w-72' : 'w-full'}`}/>
    </button>
    {zoom && <div role="dialog" aria-modal="true" aria-label="Print ampliado" className="fixed inset-0 z-50 flex items-start justify-center overflow-auto bg-black/70 p-6" onClick={() => setZoom(false)}>
      <button type="button" aria-label="Fechar" className="fixed top-4 right-4 rounded-full bg-white p-2 shadow" onClick={() => setZoom(false)}><XClose size={18}/></button>
      <img src={src} alt="" className="max-w-full rounded-lg"/>
    </div>}
  </div>;
}

export function LinkReportView({report, actions}) {
  const h = report.header;
  const kind = LINK_KIND_META[h.kind] ? h.kind : 'media';
  const sections = report.sections || [];
  const ids = useMemo(() => ['resultado', ...(report.screenshots?.desktop || report.screenshots?.mobile ? ['print'] : []), ...sections.map(section => section.id)], [report]);
  const [open, setOpen] = useState(() => new Set(sections.filter((section, index) => index < 4 || ['bad', 'warn'].includes(section.tone)).map(section => section.id)));
  const [active, setActive] = useState('resultado');
  const [copied, setCopied] = useState(false);
  const container = useRef(null);
  useEffect(() => {
    const observer = new IntersectionObserver(entries => {
      const visible = entries.filter(entry => entry.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
      if (visible) setActive(visible.target.id.replace(/^lt-/, ''));
    }, {rootMargin: '-80px 0px -60% 0px'});
    ids.forEach(id => {const element = document.getElementById(`lt-${id}`); if (element) observer.observe(element);});
    return () => observer.disconnect();
  }, [ids]);
  const go = id => {setOpen(value => new Set(value).add(id)); requestAnimationFrame(() => document.getElementById(`lt-${id}`)?.scrollIntoView({behavior: 'smooth', block: 'start'}));};
  const toggle = id => setOpen(value => {const next = new Set(value); next.has(id) ? next.delete(id) : next.add(id); return next;});
  const allOpen = sections.every(section => open.has(section.id));
  const copyUrl = async () => {try {await navigator.clipboard.writeText(h.url); setCopied(true); setTimeout(() => setCopied(false), 1400);} catch (_) { /* Clipboard may be denied. */ }};
  const toneOf = id => id === 'resultado' ? h.tone : id === 'print' ? 'info' : sections.find(section => section.id === id)?.tone || 'info';
  const titleOf = id => id === 'resultado' ? 'Resultado' : id === 'print' ? 'Print da página' : sections.find(section => section.id === id)?.title;

  return <div ref={container} className="grid items-start gap-6 xl:grid-cols-[13rem_minmax(0,1fr)]">
    {/* Wide screens keep a sticky index; narrower ones use the section map below the result (no sideways scrolling). */}
    <nav aria-label="Seções do relatório" className="hidden xl:sticky xl:top-4 xl:flex xl:flex-col xl:gap-1">
      {ids.map(id => <button key={id} type="button" onClick={() => go(id)} aria-current={active === id ? 'true' : undefined}
        className={`flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-sm ${active === id ? 'bg-primary font-semibold text-primary shadow-xs ring-1 ring-secondary' : 'text-tertiary hover:text-secondary'}`}>
        <Dot tone={toneOf(id)}/>{titleOf(id)}</button>)}
      <button type="button" onClick={() => setOpen(allOpen ? new Set() : new Set(sections.map(section => section.id)))} className="mt-2 flex items-center gap-1.5 px-2.5 text-xs font-semibold text-tertiary hover:text-secondary">
        {allOpen ? <Minimize01 size={14}/> : <Expand01 size={14}/>}{allOpen ? 'Recolher tudo' : 'Expandir tudo'}</button>
    </nav>

    <div className="flex min-w-0 flex-col gap-4">
      <section id="lt-resultado" className="scroll-mt-4 overflow-hidden rounded-2xl bg-primary shadow-xs ring-1 ring-secondary">
        <img src={`/static/images/reports/illustrations/link-tester/lt-hero-${kind}.webp`} alt="" className="h-36 w-full object-cover" style={{objectPosition: 'center 45%'}}/>
        <div className="flex flex-wrap items-center gap-6 px-6 py-5">
          <Gauge score={h.score} tone={h.tone}/>
          <div className="min-w-[15rem] flex-1">
            <div className="flex flex-wrap items-center gap-2"><KindIcon kind={kind} size={30}/>
              <span className="text-xs font-bold tracking-wider uppercase" style={{color: LINK_KIND_META[kind].color}}>{h.type_label || LINK_KIND_META[kind].label}</span>
              {h.source === 'cadu_php' && <Badge type="color" size="sm" color="warning">Cadu anterior</Badge>}</div>
            <h1 className="mt-2 text-2xl font-semibold text-primary">{h.status_label}</h1>
            <div className="mt-1 flex items-center gap-1.5"><p className="min-w-0 truncate font-mono text-xs text-tertiary" title={h.url}>{h.url}</p>
              <button type="button" onClick={copyUrl} aria-label="Copiar URL" className="shrink-0 rounded p-1 text-fg-quaternary hover:text-secondary"><Copy01 size={14}/></button>
              <a href={h.url} target="_blank" rel="noreferrer noopener" aria-label="Abrir a página" className="shrink-0 rounded p-1 text-fg-quaternary hover:text-secondary"><LinkExternal01 size={14}/></a>
              {copied && <span className="text-xs text-tertiary">Copiada</span>}</div>
            {h.summary && <p className="mt-2 text-sm text-secondary">{h.summary}</p>}
            <p className="mt-2 text-xs text-tertiary">{h.author ? <>Testado por <strong className="font-medium text-secondary">{h.author}</strong> · </> : null}{fullDate(h.created_at)}</p>
          </div>
          {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
        </div>
        {report.indicators?.length > 0 && <div className="grid grid-cols-2 gap-2.5 px-6 pb-5 sm:grid-cols-3 xl:grid-cols-6">{report.indicators.map(item => <button key={item.key} type="button" onClick={() => go(item.target)}
          className="rounded-xl bg-secondary_subtle p-3 text-left ring-1 ring-secondary transition hover:-translate-y-0.5 hover:ring-2 hover:ring-[var(--color-border-brand)] ring-inset">
          <span className="flex items-center gap-1.5 text-xs text-tertiary"><Dot tone={item.tone}/>{item.label}</span><strong className="mt-1 block truncate text-base text-primary">{item.value}</strong></button>)}</div>}
        {report.modules?.length > 0 && <div className="grid gap-x-8 gap-y-4 border-t border-secondary px-6 py-5 sm:grid-cols-2 xl:grid-cols-3">{report.modules.map(item => <Bar key={item.key} label={item.label} value={item.score} tone={(item.score || 0) >= 80 ? 'ok' : (item.score || 0) >= 50 ? 'warn' : 'bad'} detail={item.detail}/>)}</div>}
        {h.highlights?.length > 0 && <div className="border-t border-secondary px-6 py-5"><h2 className="text-sm font-semibold text-primary">Resultado preliminar</h2>
          <ul className="mt-2 flex flex-col gap-1.5">{h.highlights.map((item, index) => <li key={index} className="flex gap-2.5 text-sm text-secondary"><span className="mt-1.5"><Dot tone={item.tone === 'bad' ? 'bad' : item.tone === 'warn' ? 'warn' : 'ok'}/></span>{item.text}</li>)}</ul></div>}
      </section>

      {report.overview?.items?.length > 0 && <section aria-label="Mapa das seções" className="rounded-2xl bg-primary p-5 shadow-xs ring-1 ring-secondary">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-base font-semibold text-primary">{report.overview.problems ? `${report.overview.problems} de ${report.overview.total} seções pedem atenção` : `As ${report.overview.total} seções estão em ordem`}</h2>
          <button type="button" onClick={() => setOpen(allOpen ? new Set() : new Set(sections.map(section => section.id)))} className="flex items-center gap-1.5 text-xs font-semibold text-tertiary hover:text-secondary xl:hidden">
            {allOpen ? <Minimize01 size={14}/> : <Expand01 size={14}/>}{allOpen ? 'Recolher tudo' : 'Expandir tudo'}</button>
        </div>
        <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-3">{report.overview.items.map(item => <button key={item.id} type="button" onClick={() => go(item.id)}
          className="flex items-start gap-2.5 rounded-xl p-3 text-left ring-1 ring-secondary transition ring-inset hover:-translate-y-0.5 hover:ring-2"
          style={{background: ['bad', 'warn'].includes(item.tone) ? `${TONE[item.tone]}12` : undefined}}>
          <span className="mt-1.5"><Dot tone={item.tone}/></span>
          <span className="min-w-0 flex-1"><span className="block text-sm font-semibold text-primary">{item.title}</span>
            {(item.summary || item.issues > 0) && <span className="block truncate text-xs text-tertiary">{item.issues > 0 ? `${item.issues} a corrigir` : item.summary}</span>}</span>
        </button>)}</div>
      </section>}

      {(report.screenshots?.desktop || report.screenshots?.mobile) && <section id="lt-print" className="scroll-mt-4 rounded-2xl bg-primary p-6 shadow-xs ring-1 ring-secondary">
        <h2 className="mb-3 text-base font-semibold text-primary">Print da página</h2><Screenshots shots={report.screenshots}/></section>}

      {sections.map(section => {
        const expanded = open.has(section.id);
        return <section key={section.id} id={`lt-${section.id}`} className="scroll-mt-4 rounded-2xl bg-primary shadow-xs ring-1 ring-secondary">
          <button type="button" aria-expanded={expanded} onClick={() => toggle(section.id)} className="flex w-full items-center gap-3 px-6 py-4 text-left">
            <Dot tone={section.tone || 'info'} size={10}/><span className="min-w-0 flex-1"><span className="block text-base font-semibold text-primary">{section.title}</span>
              {section.summary && <span className="block text-xs text-tertiary">{section.summary}</span>}</span>
            <ChevronDown size={18} className={`shrink-0 text-fg-quaternary transition-transform ${expanded ? 'rotate-180' : ''}`}/>
          </button>
          {expanded && <div className="grid gap-5 px-6 pb-6">{section.blocks.map((block, index) => <Block key={index} block={block}/>)}</div>}
        </section>;
      })}
    </div>
  </div>;
}
