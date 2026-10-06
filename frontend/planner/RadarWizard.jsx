import React, {useEffect, useMemo, useRef, useState} from 'react';
import {CaduButton} from '../cadu-design-system/components/CaduButton.jsx';
import {CaduTextAreaField} from '../cadu-design-system/components/CaduField.jsx';
import {CaduInput} from '../cadu-design-system/components/CaduInput.jsx';
import {Icon} from '../cadu-design-system/components/Icon.jsx';
import {contextQuery} from './api.js';

const ART = '/static/images/planner/illustrations/';
export const RADAR_DRAFT_KEY = 'planner.radar.draft';

export const LENSES = [
  ['Sazonalidade e datas', 'calendar'], ['Concorrência', 'users'], ['Tendências e cultura', 'pulse'],
  ['Regulação', 'check'], ['Lançamentos do setor', 'plugin'], ['Reputação', 'analysis'],
];
/** Cada ideia vira um pedido completo; é o jeito mais rápido de pedir bem (tema + recorte). */
export const IDEAS = [
  ['Datas e sazonalidade', who => `datas comerciais, eventos e sazonalidade das próximas semanas que abrem espaço para ${who}`],
  ['Concorrentes', who => `lançamentos, campanhas e movimentos recentes dos concorrentes de ${who}`],
  ['Tendências e buscas em alta', who => `assuntos e buscas em alta ligados ao setor de ${who}`],
  ['Regulação e governo', who => `mudanças de regra, decisões de governo e reguladores que afetam ${who}`],
  ['Reputação e imprensa', who => `o que a imprensa e o público estão falando sobre ${who}`],
  ['Notícias da praça', who => `fatos locais recentes que dão gancho para ${who}`],
];
const OBJECTIVES = [['ambos', 'Conteúdo e mídia'], ['conteudo', 'Só conteúdo'], ['midia', 'Só mídia']];
const PLACES = ['Brasil', 'São Paulo', 'Rio de Janeiro', 'Belo Horizonte', 'Capitais', 'Sul', 'Nordeste'];
const RECENCY = [[7, 'Últimos 7 dias', 'O que acabou de acontecer.'], [30, 'Últimos 30 dias', 'O equilíbrio para a maioria das campanhas.'], [60, 'Últimos 60 dias', 'Para temas que andam devagar.']];
export const FREQUENCIES = [[1, '1 vez por dia', 'às 8h'], [2, '2 vezes por dia', 'às 8h e 17h'], [3, '3 vezes por dia', 'às 8h, 13h e 18h']];
const STEPS = [
  {key: 'marca', label: 'Marca', art: 'radar-1-marca.webp', title: 'De quem é este radar?', text: 'O Radar usa o perfil da marca: público, concorrentes e posicionamento.'},
  {key: 'tema', label: 'Tema', art: 'radar-2-tema.webp', title: 'O que você quer encontrar?', text: 'Escreva o tema ou parta de uma ideia. Uma pergunta por radar rende oportunidades mais certeiras.'},
  {key: 'praca', label: 'Onde e quando', art: 'radar-3-praca-janela.webp', title: 'Onde e em que janela?', text: 'A praça traz a imprensa local para a busca. A janela diz o quão recente o fato precisa ser.'},
  {key: 'fontes', label: 'Fontes', art: 'radar-4-fontes.webp', title: 'Onde o Radar deve olhar?', text: 'Tudo vem ligado. Desligue o que não faz sentido para este tema.'},
  {key: 'revisao', label: 'Revisão', art: 'radar-5-revisao.webp', title: 'Pronto para procurar?', text: 'Confira o resumo. Se quiser, o Radar repete a busca sozinho e avisa quando houver novidade.'},
];
const BENEFITS = [['search', 'Fatos recentes com fonte e data'], ['check', 'Cada oportunidade conferida na web'], ['pulse', 'Notas editorial, paga e por praça']];
const GAP_FIELDS = [['competitors', 'Concorrentes'], ['target_audience', 'Público-alvo'], ['positioning', 'Posicionamento']];

const empty = {brand_ref: '', project_ref: '', focus: '', lenses: [], objective: 'ambos', places: '', recency_days: 30,
  press: true, trends: true, watch: false, frequency: 1};
const readDraft = () => { try { return {...empty, ...JSON.parse(window.sessionStorage.getItem(RADAR_DRAFT_KEY) || '{}')}; } catch { return empty; } };
const toggle = (list, item, max = 3) => list.includes(item) ? list.filter(value => value !== item) : [...list, item].slice(-max);

/**
 * "Novo radar": a busca montada uma pergunta por vez. Todo passo é opcional, o rascunho
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
  }, [data.brand_ref, data.project_ref, request]);

  const go = next => { const bounded = Math.max(0, Math.min(STEPS.length - 1, next)); setStep(bounded); setReached(current => Math.max(current, bounded)); setVisited(current => new Set(current).add(bounded)); };
  const last = step === STEPS.length - 1;
  const submit = event => {
    event?.preventDefault();
    if (!last) { go(step + 1); return; }
    onSubmit({focus: data.focus.trim(), brand_ref: data.brand_ref || null, project_ref: data.project_ref || null,
      params: {lenses: data.lenses, places: data.places, recency_days: data.recency_days, objective: data.objective,
        sources: {press: data.press, trends: data.trends}},
      watch: data.watch ? {frequency: data.frequency} : null});
  };
  const empty_ = !data.focus.trim() && !data.brand_ref && !data.project_ref;
  const filled = new Set((known.brand?.fields || []).map(item => item.key));
  const gaps = GAP_FIELDS.filter(([key]) => data.brand_ref && !known.loading && !filled.has(key));
  const current = STEPS[step];
  const summary = [
    ['Marca', [brand?.name, project?.name].filter(Boolean).join(' · ')], ['Tema', data.focus.trim()],
    ['Lentes', data.lenses.join(', ')], ['Praça', data.places], ['Janela', `últimos ${data.recency_days} dias`],
    ['Fontes', ['busca aberta', data.press && 'imprensa', data.trends && 'buscas em alta', 'conferência na web'].filter(Boolean).join(', ')],
  ].filter(([, value]) => value);

  return <div className="wizard wizard--radar" role="dialog" aria-modal="true" aria-label="Novo radar">
    <header className="wizard__bar">
      <a className="wizard__brand" href={boot.urls.home}><img src="/static/images/cadu/products/planner-icon.png" alt=""/>Planner</a>
      <span className="wizard__title">Radar<em>Beta</em></span>
      <a className="wizard__exit" href={boot.urls.radars}><Icon name="close" size={16}/>Sair</a>
    </header>
    <aside className="wizard__art" aria-hidden="true">
      <div className="wizard__intro">
        <span className="wizard__eyebrow">Do sinal à oportunidade</span>
        <h1>Radar<em>Beta</em></h1>
        <p>Diga o que procurar. O Radar traz fatos recentes, confere cada um e mostra onde agir.</p>
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
              onClick={() => setData(value => ({...value, brand_ref: item.ref, project_ref: ''}))}>
              <span className="wiz-option__icon">{item.logo_url ? <img src={item.logo_url} alt="" width="26" height="26" style={{objectFit: 'contain'}}/> : <Icon name="library" size={22}/>}</span>
              <span><strong>{item.name}</strong></span><Icon name={data.brand_ref === item.ref ? 'check' : 'chevron'} size={18}/></button>)}
            <button type="button" role="radio" aria-checked={!data.brand_ref} className={`wiz-option${!data.brand_ref ? ' is-chosen' : ''}`}
              onClick={() => setData(value => ({...value, brand_ref: '', project_ref: ''}))}>
              <span className="wiz-option__icon"><Icon name="search" size={22}/></span>
              <span><strong>Sem marca</strong><small>Pesquisar só o tema que você escrever.</small></span>
              <Icon name={!data.brand_ref ? 'check' : 'chevron'} size={18}/></button>
          </div>
          {projects.length > 0 && <div className="wizard__chips" aria-label="Projeto">
            {projects.map(item => <button key={item.ref} type="button" className={data.project_ref === item.ref ? 'is-on' : ''}
              onClick={() => set('project_ref', data.project_ref === item.ref ? '' : item.ref)}>{item.name}</button>)}
          </div>}
          {data.brand_ref && <p className="wizard__known" aria-live="polite">
            {known.loading ? 'Lendo o perfil da marca…' : <>
              {(known.brand?.fields || []).length > 0 && <span><b>O Radar já sabe:</b> {known.brand.fields.slice(0, 5).map(item => item.label).join(' · ')}.</span>}
              {gaps.length > 0 && <span className="is-gap"> Faltam no perfil: {gaps.map(([, label]) => label).join(', ')}. O Radar funciona sem, mas acerta mais com eles.</span>}
            </>}</p>}
        </>}

        {step === 1 && <>
          <CaduTextAreaField aria-label="Tema" rows={3} value={data.focus} onChange={event => set('focus', event.target.value)} maxLength="240"
            placeholder={`Ex.: volta às aulas e crédito estudantil no Sudeste para ${who}`}/>
          <div className="wizard__chips" aria-label="Ideias de busca">
            {IDEAS.map(([label, text]) => <button key={label} type="button" onClick={() => set('focus', text(who))}>{label}</button>)}
          </div>
          <p className="wizard__label">Lentes <small>(até 3, opcional)</small></p>
          <div className="wizard__chips" role="group" aria-label="Lentes">
            {LENSES.map(([label, icon]) => <button key={label} type="button" aria-pressed={data.lenses.includes(label)} className={data.lenses.includes(label) ? 'is-on' : ''}
              onClick={() => set('lenses', toggle(data.lenses, label))}><Icon name={icon} size={14}/>{label}</button>)}
          </div>
          <p className="wizard__label">O que fazer com o achado</p>
          <div className="wizard__chips" role="radiogroup" aria-label="Objetivo">
            {OBJECTIVES.map(([id, label]) => <button key={id} type="button" role="radio" aria-checked={data.objective === id} className={data.objective === id ? 'is-on' : ''}
              onClick={() => set('objective', id)}>{label}</button>)}
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

        {step === 3 && <div className="wizard__options">
          <div className="wiz-option is-chosen is-fixed"><span className="wiz-option__icon"><Icon name="search" size={22}/></span>
            <span><strong>Busca aberta</strong><small>O Perplexity procura o que está acontecendo no tema. Sempre ligada.</small></span><Icon name="check" size={18}/></div>
          <button type="button" role="switch" aria-checked={data.press} className={`wiz-option${data.press ? ' is-chosen' : ''}`} onClick={() => set('press', !data.press)}>
            <span className="wiz-option__icon"><Icon name="library" size={22}/></span>
            <span><strong>Imprensa conhecida</strong><small>Só reportagens de veículos nacionais, de mercado e da sua praça.</small></span><Icon name={data.press ? 'check' : 'plus'} size={18}/></button>
          <button type="button" role="switch" aria-checked={data.trends} className={`wiz-option${data.trends ? ' is-chosen' : ''}`} onClick={() => set('trends', !data.trends)}>
            <span className="wiz-option__icon"><Icon name="pulse" size={22}/></span>
            <span><strong>Buscas e assuntos em alta</strong><small>O que cresceu nos últimos dias ligado ao tema.</small></span><Icon name={data.trends ? 'check' : 'plus'} size={18}/></button>
          <div className="wiz-option is-chosen is-fixed"><span className="wiz-option__icon"><Icon name="check" size={22}/></span>
            <span><strong>Conferência na web</strong><small>Um segundo modelo pesquisa fora das fontes e tenta provar que cada oportunidade está errada. Sempre ligada.</small></span><Icon name="check" size={18}/></div>
        </div>}

        {step === 4 && <>
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
          <a href={boot.urls.radars}>Ver meus radares</a>
        </p>
      </form>
      <ol className="wizard__steps">{STEPS.map((item, index) => <li key={item.key} className={index === step ? 'is-current' : ''}>
        <button type="button" disabled={index > reached} onClick={() => go(index)}><b>{index + 1}</b>{item.label}</button></li>)}</ol>
    </main>
  </div>;
}
