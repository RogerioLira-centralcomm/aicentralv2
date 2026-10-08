import React, {useEffect, useMemo, useRef, useState} from 'react';
import {CaduButton} from '../cadu-design-system/components/CaduButton.jsx';
import {CaduTextAreaField} from '../cadu-design-system/components/CaduField.jsx';
import {CaduInput} from '../cadu-design-system/components/CaduInput.jsx';
import {Icon} from '../cadu-design-system/components/Icon.jsx';
import {contextQuery} from './api.js';
import {BrandProfileDialog} from './BrandProfileDialog.jsx';

const ART = '/static/images/planner/illustrations/';
export const RADAR_DRAFT_KEY = 'planner.radar.draft';

/** Cada ideia vira um pedido completo; é o jeito mais rápido de pedir bem (tema + recorte). */
export const IDEAS = [
  ['Datas e sazonalidade', who => `datas comerciais, eventos e sazonalidade das próximas semanas que abrem espaço para ${who}`],
  ['Concorrentes', who => `lançamentos, campanhas e movimentos recentes dos concorrentes de ${who}`],
  ['Tendências e buscas em alta', who => `assuntos e buscas em alta ligados ao setor de ${who}`],
  ['Regulação e governo', who => `mudanças de regra, decisões de governo e reguladores que afetam ${who}`],
  ['Reputação e imprensa', who => `o que a imprensa e o público estão falando sobre ${who}`],
  ['Notícias da praça', who => `fatos locais recentes que dão gancho para ${who}`],
];
const PLACES = ['Brasil', 'São Paulo', 'Rio de Janeiro', 'Belo Horizonte', 'Capitais', 'Sul', 'Nordeste'];
const RECENCY = [[7, 'Últimos 7 dias', 'O que acabou de acontecer.'], [30, 'Últimos 30 dias', 'O equilíbrio para a maioria das campanhas.'], [60, 'Últimos 60 dias', 'Para temas que andam devagar.']];
export const FREQUENCIES = [[1, '1 vez por dia', 'às 8h'], [2, '2 vezes por dia', 'às 8h e 17h'], [3, '3 vezes por dia', 'às 8h, 13h e 18h']];
const STEPS = [
  {key: 'marca', label: 'Marca', art: 'radar-1-marca.webp', title: 'De quem é este radar?', text: 'O Radar usa o perfil da marca: público, concorrentes e posicionamento.'},
  {key: 'conceito', label: 'Conceito', art: 'radar-2-tema.webp', title: 'Sobre qual conceito você quer ouvir o buzz?', text: 'Escreva o tema, produto ou campanha. O Radar mostra o que está em alta e os ângulos para a marca falar dele.'},
  {key: 'praca', label: 'Onde e quando', art: 'radar-3-praca-janela.webp', title: 'Onde e em que janela?', text: 'A praça traz o buzz do lugar. A janela diz o quão recente o assunto precisa ser.'},
  {key: 'revisao', label: 'Revisão', art: 'radar-5-revisao.webp', title: 'Pronto para procurar?', text: 'Confira o resumo. Se quiser, o Radar repete a busca sozinho e avisa quando houver novidade.'},
];
const BENEFITS = [['pulse', 'O que está em buzz agora'], ['plugin', 'Ângulos prontos para o cliente'], ['check', 'Só fonte recente e com link']];
const GAP_FIELDS = [['competitors', 'Concorrentes'], ['target_audience', 'Público-alvo'], ['positioning', 'Posicionamento']];

const empty = {brand_ref: '', project_ref: '', focus: '', places: '', recency_days: 30, watch: false, frequency: 1};
const readDraft = () => { try { return {...empty, ...JSON.parse(window.sessionStorage.getItem(RADAR_DRAFT_KEY) || '{}')}; } catch { return empty; } };

/**
 * "Novo radar": o conceito e a marca, uma pergunta por vez. Todo passo é opcional, o rascunho
 * sobrevive a um recarregamento e o custo aparece antes de começar.
 */
export function RadarWizard({boot, request, busy, onSubmit, context}) {
  const [step, setStep] = useState(0);
  const [reached, setReached] = useState(0);
  const [visited, setVisited] = useState(() => new Set([0]));
  const [data, setData] = useState(() => {
    const draft = readDraft();
    return {...draft, brand_ref: draft.brand_ref || context?.brand_ref || '', project_ref: draft.project_ref || context?.project_ref || ''};
  });
  const [known, setKnown] = useState({loading: false, brand: null, project: null});
  const [estimate, setEstimate] = useState(null);
  const [profileOpen, setProfileOpen] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const panel = useRef(null);
  const set = (key, value) => setData(current => ({...current, [key]: value}));
  const brands = boot.contextBar?.brands || [];
  const allProjects = boot.contextBar?.projects || [];
  const brand = brands.find(item => item.ref === data.brand_ref);
  const projects = useMemo(() => {
    const related = allProjects.filter(item => (item.related_refs || []).includes(data.brand_ref));
    return data.brand_ref ? related : [];
  }, [allProjects, data.brand_ref]);
  const project = allProjects.find(item => item.ref === data.project_ref);
  const who = brand?.name || project?.name || 'a marca';

  useEffect(() => { try { window.sessionStorage.setItem(RADAR_DRAFT_KEY, JSON.stringify(data)); } catch { /* the draft just is not kept */ } }, [data]);
  useEffect(() => { panel.current?.querySelector('input, textarea, button.wiz-option')?.focus?.({preventScroll: true}); }, [step]);
  useEffect(() => { request('/radar/estimate').then(setEstimate).catch(() => {}); }, [request]);
  useEffect(() => {
    if (!data.brand_ref && !data.project_ref) { setKnown({loading: false, brand: null, project: null}); return undefined; }
    let current = true;
    setKnown(value => ({...value, loading: true}));
    request(`/context?${contextQuery({brand_ref: data.brand_ref, project_ref: data.project_ref})}`)
      .then(result => { if (current) setKnown({loading: false, brand: result.context?.brand || null, project: result.context?.project || null}); })
      .catch(() => { if (current) setKnown({loading: false, brand: null, project: null}); });
    return () => { current = false; };
  }, [data.brand_ref, data.project_ref, request, refresh]);

  const go = next => { const bounded = Math.max(0, Math.min(STEPS.length - 1, next)); setStep(bounded); setReached(current => Math.max(current, bounded)); setVisited(current => new Set(current).add(bounded)); };
  const last = step === STEPS.length - 1;
  const submit = event => {
    event?.preventDefault();
    if (!last) { go(step + 1); return; }
    onSubmit({focus: data.focus.trim(), brand_ref: data.brand_ref || null, project_ref: data.project_ref || null,
      params: {places: data.places, recency_days: data.recency_days}, watch: data.watch ? {frequency: data.frequency} : null});
  };
  const empty_ = !data.focus.trim() && !data.brand_ref && !data.project_ref;
  const filled = new Set((known.brand?.fields || []).map(item => item.key));
  const gaps = GAP_FIELDS.filter(([key]) => data.brand_ref && !known.loading && !filled.has(key));
  const current = STEPS[step];
  const summary = [['Marca', [brand?.name, project?.name].filter(Boolean).join(' · ')], ['Conceito', data.focus.trim()],
    ['Praça', data.places], ['Janela', `últimos ${data.recency_days} dias`]].filter(([, value]) => value);

  return <section className="wizard wizard--radar" aria-label="Novo radar">
    <header className="wizard__bar">
      <span className="wizard__title">Novo radar<em>Beta</em></span>
      <nav className="wizard__links" aria-label="Voltar"><a href={boot.urls.radar}><Icon name="pulse" size={16}/>Voltar ao Radar</a></nav>
    </header>
    <aside className="wizard__art">
      {/* A lista do que já foi criado mora na vitrine do Radar; aqui a coluna é sempre a ilustração do passo. */}
      <div className="wizard__intro">
        <span className="wizard__eyebrow">Do buzz ao ângulo</span>
        <h1>Radar<em>Beta</em></h1>
        <p>Diga o conceito. O Radar mostra o que está em alta agora e os ângulos para a marca falar dele.</p>
        <ul>{BENEFITS.map(([icon, text]) => <li key={text}><Icon name={icon} size={20}/>{text}</li>)}</ul>
      </div>
      {STEPS.map((item, index) => <img key={item.key} className={`wizard__scene${index === step ? ' is-current' : ''}`} src={ART + item.art} alt="" loading={index === 0 ? 'eager' : 'lazy'}/>)}
    </aside>
    <main className="wizard__main">
      <ol className="wizard__progress" aria-label="Progresso">
        <li className="wizard__count">{step + 1} de {STEPS.length}</li>
        {STEPS.map((item, index) => <li key={item.key}><button type="button" aria-label={`Ir para ${item.label}`} disabled={index > reached}
          className={index === step || visited.has(index) ? 'is-done' : index <= reached ? 'is-seen' : ''} onClick={() => go(index)}/></li>)}
      </ol>
      <form ref={panel} className="wizard__panel" onSubmit={submit}>
        <h2>{current.title}</h2>
        <p className="wizard__lead">{current.text}</p>

        {step === 0 && <>
          <div className="wizard__options wizard__options--scroll" role="radiogroup" aria-label="Marca">
            {brands.map(item => <button key={item.ref} type="button" role="radio" aria-checked={data.brand_ref === item.ref}
              className={`wiz-option${data.brand_ref === item.ref ? ' is-chosen' : ''}`}
              onClick={() => { setData(value => ({...value, brand_ref: item.ref, project_ref: ''})); go(1); }}>
              <span className="wiz-option__icon">{item.logo_url ? <img src={item.logo_url} alt="" width="26" height="26" style={{objectFit: 'contain'}}/> : <Icon name="library" size={22}/>}</span>
              <span><strong>{item.name}</strong></span><Icon name={data.brand_ref === item.ref ? 'check' : 'chevron'} size={18}/></button>)}
            <button type="button" role="radio" aria-checked={!data.brand_ref} className={`wiz-option${!data.brand_ref ? ' is-chosen' : ''}`}
              onClick={() => { setData(value => ({...value, brand_ref: '', project_ref: ''})); go(1); }}>
              <span className="wiz-option__icon"><Icon name="search" size={22}/></span>
              <span><strong>Sem marca</strong><small>Pesquisar só o conceito que você escrever.</small></span>
              <Icon name={!data.brand_ref ? 'check' : 'chevron'} size={18}/></button>
          </div>
        </>}

        {step === 1 && <>
          {brand && <div className="wizard__brand-strip">
            <p className="wizard__known" aria-live="polite">
              {known.loading ? 'Lendo o perfil da marca…' : gaps.length > 0
                ? <><b>{brand.name}</b>: faltam no perfil {gaps.map(([, label]) => label.toLowerCase()).join(' e ')}. O Radar funciona sem, mas acerta mais com eles.</>
                : <><b>{brand.name}</b>: o perfil tem o que o Radar usa.</>}
              {!known.loading && <button type="button" className="wizard__link" onClick={() => setProfileOpen(true)}>{gaps.length > 0 ? 'Completar perfil' : 'Atualizar perfil'}</button>}
            </p>
            {projects.length > 0 && <div className="wizard__chips" aria-label="Projeto">
              {projects.map(item => <button key={item.ref} type="button" className={data.project_ref === item.ref ? 'is-on' : ''}
                onClick={() => set('project_ref', data.project_ref === item.ref ? '' : item.ref)}>{item.name}</button>)}
            </div>}
          </div>}
          <CaduTextAreaField aria-label="Conceito" rows={3} value={data.focus} onChange={event => set('focus', event.target.value)} maxLength="240"
            placeholder={`Ex.: consumo consciente de energia no fim do ano, para ${who}`}/>
          <div className="wizard__chips" aria-label="Ideias para começar">
            {IDEAS.map(([label, text]) => <button key={label} type="button" onClick={() => set('focus', text(who))}>{label}</button>)}
          </div>
        </>}

        {step === 2 && <>
          <CaduInput label="Praça" value={data.places} onChange={event => set('places', event.target.value)} placeholder="Ex.: Brasil, SP, BH" maxLength="120"/>
          <div className="wizard__chips" aria-label="Sugestões de praça">{PLACES.map(place => <button key={place} type="button"
            onClick={() => set('places', data.places.includes(place) ? data.places : [data.places, place].filter(Boolean).join(', '))}>{place}</button>)}</div>
          <div className="wizard__options" role="radiogroup" aria-label="Janela">
            {RECENCY.map(([days, label, text]) => <button key={days} type="button" role="radio" aria-checked={data.recency_days === days}
              className={`wiz-option${data.recency_days === days ? ' is-chosen' : ''}`} onClick={() => set('recency_days', days)}>
              <span className="wiz-option__icon"><Icon name="calendar" size={22}/></span><span><strong>{label}</strong><small>{text}</small></span>
              <Icon name={data.recency_days === days ? 'check' : 'chevron'} size={18}/></button>)}
          </div>
        </>}

        {step === 3 && <>
          {summary.length > 0 ? <dl className="wizard__summary">{summary.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
            : <p className="wizard__lead">Nada preenchido ainda. Escolha uma marca ou escreva um tema para o Radar procurar.</p>}
          <button type="button" role="switch" aria-checked={data.watch} className={`wiz-option${data.watch ? ' is-chosen' : ''}`} onClick={() => set('watch', !data.watch)}>
            <span className="wiz-option__icon"><Icon name="pulse" size={22}/></span>
            <span><strong>Me avise quando houver novidade</strong><small>O Radar repete esta busca sozinho e fica em &quot;Meus radares&quot;.</small></span>
            <Icon name={data.watch ? 'check' : 'plus'} size={18}/></button>
          {data.watch && <div className="wizard__chips" role="radiogroup" aria-label="Frequência">
            {FREQUENCIES.map(([value, label, hours]) => <button key={value} type="button" role="radio" aria-checked={data.frequency === value} className={data.frequency === value ? 'is-on' : ''}
              onClick={() => set('frequency', value)}>{label} <small>({hours})</small></button>)}
          </div>}
          <p className="wizard__cost"><Icon name="analysis" size={14}/>
            Cada busca reserva até {estimate ? Number(estimate.estimated_tokens).toLocaleString('pt-BR') : '…'} tokens e cobra só o que usar.
            {data.watch && ' Cada repetição do radar é cobrada do seu saldo da mesma forma.'}</p>
        </>}

        <div className="wizard__nav">
          <CaduButton variant="secondary" disabled={step === 0} onClick={() => go(step - 1)}><Icon name="chevron" size={16} className="wizard__back"/>Voltar</CaduButton>
          <CaduButton type="submit" loading={busy} disabled={last && empty_}>{last ? <><Icon name="search" size={16}/>Buscar oportunidades</> : <>Continuar<Icon name="chevron" size={16}/></>}</CaduButton>
        </div>
        <p className="wizard__skip">
          {!last && <button type="button" onClick={() => go(STEPS.length - 1)}>Pular e revisar</button>}
        </p>
      </form>
      <ol className="wizard__steps">{STEPS.map((item, index) => <li key={item.key} className={index === step ? 'is-current' : ''}>
        <button type="button" disabled={index > reached} onClick={() => go(index)}><b>{index + 1}</b>{item.label}</button></li>)}</ol>
    </main>
    {profileOpen && brand && <BrandProfileDialog request={request} brand={brand} onClose={() => setProfileOpen(false)} onSaved={() => setRefresh(value => value + 1)}/>}
  </section>;
}
