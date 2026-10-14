import React, {useEffect, useMemo, useRef, useState} from 'react';
import {CaduButton} from '../cadu-design-system/components/CaduButton.jsx';
import {CaduTextAreaField} from '../cadu-design-system/components/CaduField.jsx';
import {CaduInput} from '../cadu-design-system/components/CaduInput.jsx';
import {Icon} from '../cadu-design-system/components/Icon.jsx';
import {contextQuery} from './api.js';

const ART = '/static/images/planner/illustrations/';
export const DRAFT_KEY = 'planner.wizard.draft';

// Four common goals; each maps to the objective the plan stores. Nothing is mandatory.
const GOALS = [
  {id: 'awareness', icon: 'pulse', title: 'Gerar awareness', text: 'Fazer a marca ser lembrada por mais gente.', objective: 'awareness'},
  {id: 'lancamento', icon: 'plugin', title: 'Lançar um produto', text: 'Impacto alto e burburinho para um lançamento.', objective: 'consideracao'},
  {id: 'vendas', icon: 'check', title: 'Gerar leads e vendas', text: 'Foco em ação e conversão.', objective: 'vendas'},
  {id: 'sazonal', icon: 'calendar', title: 'Campanha sazonal', text: 'Datas comemorativas e picos de venda.', objective: 'awareness'},
];
const PLACES = ['Brasil', 'São Paulo', 'Rio de Janeiro', 'Belo Horizonte', 'Capitais', 'Sul', 'Nordeste'];
const AUDIENCES = ['Mães', 'Jovens 18–24', 'Executivos', 'Gamers', 'Viajantes', 'Classe A e B'];
const STEPS = [
  {key: 'marca', label: 'Marca', art: 'planejar-objetivo.webp', title: 'Para quem é este plano?', text: 'Escolha a marca e, se houver, o projeto. O Cadu usa o perfil deles para planejar.'},
  {key: 'objetivo', label: 'Objetivo', art: 'planejar-objetivo.webp', title: 'Qual é o objetivo da sua campanha?', text: 'Escolha o principal objetivo para começarmos o seu plano.'},
  {key: 'verba', label: 'Verba e período', art: 'planejar-verba.webp', title: 'Quanto e quando?', text: 'Uma ideia basta. A verba e as datas ajustam os canais sugeridos.'},
  {key: 'praca', label: 'Praça', art: 'planejar-praca.webp', title: 'Onde a campanha deve aparecer?', text: 'Cidades, estados ou o Brasil todo.'},
  {key: 'audiencia', label: 'Audiência', art: 'planejar-audiencia.webp', title: 'Quem você quer alcançar?', text: 'Descreva o público. Depois você escolhe as audiências do catálogo.'},
  {key: 'revisao', label: 'Revisão', art: 'planejar-revisao.webp', title: 'Tudo certo para começar?', text: 'Dê um nome ao plano e confira o resumo.'},
];
const BENEFITS = [['plan', 'Planos sob medida para o seu objetivo'], ['pulse', 'Sugestões de canais, audiências e formatos'], ['users', 'Mais agilidade e melhores resultados']];

const empty = {goal: '', custom: '', budget: '', period: '', geography: '', audience: '', title: '', advertiser: ''};
const readDraft = () => { try { return {...empty, ...JSON.parse(window.sessionStorage.getItem(DRAFT_KEY) || '{}')}; } catch { return empty; } };
// O rascunho guarda a barra do topo em que nasceu: se ela mudou desde então, vale a escolha nova da barra.
const initialData = (selection, brands, projects) => {
  const draft = readDraft();
  const seed = contextQuery(selection);
  const own = draft.seed === seed;
  const brand_ref = own ? draft.brand_ref : selection?.brand_ref;
  const project_ref = own ? draft.project_ref : selection?.project_ref;
  return {...draft, seed, brand_ref: brands.some(item => item.ref === brand_ref) ? brand_ref : '',
    project_ref: projects.some(item => item.ref === project_ref) ? project_ref : ''};
};

/**
 * "Planejar": the plan brief, one question at a time. It starts with who the plan
 * is for (brand and project), so the brief is read against the right profile.
 * Every step is optional; the draft survives a reload and the full form stays one click away.
 */
export function PlanWizard({request, contextBar, selection, busy, onSubmit, onFullForm}) {
  const brands = contextBar?.brands || [];
  const allProjects = contextBar?.projects || [];
  const steps = brands.length || allProjects.length ? STEPS : STEPS.slice(1);
  const [step, setStep] = useState(0);
  const [reached, setReached] = useState(0);
  const [visited, setVisited] = useState(() => new Set([0]));
  const [data, setData] = useState(() => initialData(selection, brands, allProjects));
  const [known, setKnown] = useState(null);
  const panel = useRef(null);
  const set = (key, value) => setData(current => ({...current, [key]: value}));
  const brand = brands.find(item => item.ref === data.brand_ref);
  const project = allProjects.find(item => item.ref === data.project_ref);
  // Com marca, só os projetos ligados a ela; sem marca, qualquer projeto do cliente.
  const projects = useMemo(() => brand ? allProjects.filter(item => (item.related_refs || []).includes(brand.ref)) : allProjects, [allProjects, brand]);
  const suggestions = known?.suggestions || {};

  useEffect(() => { try { window.sessionStorage.setItem(DRAFT_KEY, JSON.stringify(data)); } catch { /* the draft just is not kept */ } }, [data]);
  useEffect(() => { panel.current?.querySelector('input, textarea, button.wiz-option')?.focus?.({preventScroll: true}); }, [step]);
  useEffect(() => {
    const query = contextQuery({brand_ref: brand?.ref || '', project_ref: project?.ref || ''});
    if (!query) { setKnown(null); return undefined; }
    let current = true;
    request(`/context?${query}`).then(result => { if (current) setKnown(result.context || null); }).catch(() => { if (current) setKnown(null); });
    return () => { current = false; };
  }, [request, brand?.ref, project?.ref]);

  // Trocar de marca troca o anunciante sugerido, a menos que a pessoa já tenha escrito outro.
  const pickBrand = ref => setData(current => {
    const before = brands.find(item => item.ref === current.brand_ref)?.name || '';
    const after = brands.find(item => item.ref === ref)?.name || '';
    const keepProject = allProjects.find(item => item.ref === current.project_ref && (!ref || (item.related_refs || []).includes(ref)));
    return {...current, brand_ref: ref, project_ref: keepProject ? current.project_ref : '',
      advertiser: !current.advertiser || current.advertiser === before ? after : current.advertiser};
  });

  const goal = GOALS.find(item => item.id === data.goal);
  const suggestedTitle = useMemo(() => [goal?.title, data.period].filter(Boolean).join(' · ') || suggestions.campaign_name || '', [goal, data.period, suggestions.campaign_name]);
  const go = next => { const bounded = Math.max(0, Math.min(steps.length - 1, next)); setStep(bounded); setReached(current => Math.max(current, bounded)); setVisited(current => new Set(current).add(bounded)); };
  const last = step === steps.length - 1;

  const submit = event => {
    event?.preventDefault();
    if (!last) { go(step + 1); return; }
    const title = (data.title || suggestedTitle || 'Novo planejamento').trim();
    const notes = [goal && `Objetivo: ${goal.title}.`, data.custom && `Objetivo (texto livre): ${data.custom}`, data.audience && `Público: ${data.audience}`].filter(Boolean).join('\n');
    onSubmit({title, objective: goal?.objective || '', advertiser_name: data.advertiser || suggestions.advertiser_name || brand?.name || '', campaign_name: title,
      brand_ref: brand?.ref || null, project_ref: project?.ref || null,
      briefing: {budget: data.budget, period: data.period, geography: data.geography, notes}});
  };

  const current = steps[step];
  const forWhom = [brand?.name, project?.name].filter(Boolean).join(' · ');
  const summary = [['Para', forWhom], ['Objetivo', goal?.title || data.custom], ['Verba', data.budget], ['Período', data.period], ['Praça', data.geography], ['Público', data.audience]].filter(([, value]) => value);

  return <section className="wizard" aria-label="Novo plano">
    <aside className="wizard__art">
      {/* Os planos já criados moram na página de Planos; aqui a coluna é sempre a ilustração do passo. */}
      <div className="wizard__intro">
        <span className="wizard__eyebrow">Do brief ao resultado</span>
        <h1>Planejar<em>Beta</em></h1>
        <p>Conte sua ideia, trace um objetivo e deixe o restante com o Cadu.</p>
        <ul>{BENEFITS.map(([icon, text]) => <li key={text}><Icon name={icon} size={20}/>{text}</li>)}</ul>
      </div>
      {steps.map((item, index) => <img key={item.key} className={`wizard__scene${index === step ? ' is-current' : ''}`} src={ART + item.art} alt="" loading={index === 0 ? 'eager' : 'lazy'}/>)}
    </aside>
    <main className="wizard__main">
      {current.key !== 'marca' && steps[0].key === 'marca' && <p className="wizard__context" role="status">
        <span>Criando para</span><b>{forWhom || 'nenhuma marca'}</b>
        <button type="button" className="wizard__link" onClick={() => go(0)}>Trocar</button>
      </p>}
      <ol className="wizard__progress" aria-label="Progresso">
        <li className="wizard__count">{step + 1} de {steps.length}</li>
        {steps.map((item, index) => <li key={item.key}><button type="button" aria-label={`Ir para ${item.label}`} disabled={index > reached}
          className={index === step || visited.has(index) ? 'is-done' : index <= reached ? 'is-seen' : ''} onClick={() => go(index)}/></li>)}
      </ol>
      <form ref={panel} className="wizard__panel" onSubmit={submit}>
        <h2>{current.title}</h2>
        <p className="wizard__lead">{current.text}</p>

        {current.key === 'marca' && <>
          {brands.length > 0 && <div className="wizard__options wizard__options--scroll" role="radiogroup" aria-label="Marca">
            {brands.map(item => <button key={item.ref} type="button" role="radio" aria-checked={data.brand_ref === item.ref}
              className={`wiz-option${data.brand_ref === item.ref ? ' is-chosen' : ''}`} onClick={() => pickBrand(item.ref)}>
              <span className="wiz-option__icon">{item.logo_url ? <img src={item.logo_url} alt="" width="26" height="26" style={{objectFit: 'contain'}}/> : <Icon name="library" size={22}/>}</span>
              <span><strong>{item.name}</strong></span><Icon name={data.brand_ref === item.ref ? 'check' : 'chevron'} size={18}/></button>)}
            <button type="button" role="radio" aria-checked={!data.brand_ref} className={`wiz-option${!data.brand_ref ? ' is-chosen' : ''}`} onClick={() => pickBrand('')}>
              <span className="wiz-option__icon"><Icon name="plan" size={22}/></span>
              <span><strong>Sem marca</strong><small>Planejar só com o que você escrever no brief.</small></span>
              <Icon name={!data.brand_ref ? 'check' : 'chevron'} size={18}/></button>
          </div>}
          {projects.length > 0 && <>
            <p className="wizard__label">Projeto <small>(opcional)</small></p>
            <div className="wizard__chips" aria-label="Projeto">{projects.map(item => <button key={item.ref} type="button" aria-pressed={data.project_ref === item.ref}
              className={data.project_ref === item.ref ? 'is-on' : ''} onClick={() => set('project_ref', data.project_ref === item.ref ? '' : item.ref)}>{item.name}</button>)}</div>
          </>}
        </>}
        {current.key === 'objetivo' && <>
          <div className="wizard__options" role="radiogroup" aria-label="Objetivo">{GOALS.map(item => <button key={item.id} type="button" role="radio" aria-checked={data.goal === item.id}
            className={`wiz-option${data.goal === item.id ? ' is-chosen' : ''}`} onClick={() => { set('goal', item.id); }}>
            <span className="wiz-option__icon"><Icon name={item.icon} size={22}/></span>
            <span><strong>{item.title}</strong><small>{item.text}</small></span>
            <Icon name={data.goal === item.id ? 'check' : 'chevron'} size={18}/></button>)}</div>
          <CaduInput label="ou escreva um objetivo personalizado" value={data.custom} onChange={event => set('custom', event.target.value)} placeholder="Digite seu objetivo…" maxLength="180"/>
        </>}
        {current.key === 'verba' && <div className="wizard__fields">
          <CaduInput label="Verba disponível" inputMode="decimal" value={data.budget} onChange={event => set('budget', event.target.value)} placeholder="Ex.: R$ 50.000" maxLength="80"/>
          <CaduInput label="Período" value={data.period} onChange={event => set('period', event.target.value)} placeholder="Ex.: mai a jul de 2027" maxLength="120"/>
        </div>}
        {current.key === 'praca' && <>
          <CaduInput label="Praça" value={data.geography} onChange={event => set('geography', event.target.value)} placeholder="Ex.: Brasil, SP, BH" maxLength="120"/>
          <div className="wizard__chips" aria-label="Sugestões">{PLACES.map(place => <button key={place} type="button" onClick={() => set('geography', data.geography.includes(place) ? data.geography : [data.geography, place].filter(Boolean).join(', '))}>{place}</button>)}</div>
        </>}
        {current.key === 'audiencia' && <>
          <CaduTextAreaField aria-label="Público" rows={4} value={data.audience} onChange={event => set('audience', event.target.value)}
            placeholder="Ex.: mães de crianças até 6 anos, classe B, grandes capitais." maxLength="400"/>
          <div className="wizard__chips" aria-label="Sugestões">{AUDIENCES.map(item => <button key={item} type="button" onClick={() => set('audience', data.audience.includes(item) ? data.audience : [data.audience, item].filter(Boolean).join(', '))}>{item}</button>)}</div>
        </>}
        {current.key === 'revisao' && <>
          <CaduInput label="Nome do plano" value={data.title} onChange={event => set('title', event.target.value)} placeholder={suggestedTitle || 'Ex.: Lançamento de verão'} maxLength="180"/>
          <CaduInput label="Anunciante" value={data.advertiser} onChange={event => set('advertiser', event.target.value)} placeholder={suggestions.advertiser_name || brand?.name || 'Marca ou anunciante'} maxLength="180"/>
          {summary.length > 0 ? <dl className="wizard__summary">{summary.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
            : <p className="wizard__lead">Nada preenchido ainda. Você pode criar assim e completar o brief no plano.</p>}
        </>}

        <div className="wizard__nav">
          <CaduButton variant="secondary" disabled={step === 0} onClick={() => go(step - 1)}><Icon name="chevron" size={16} className="wizard__back"/>Voltar</CaduButton>
          <CaduButton type="submit" loading={busy}>{last ? 'Criar planejamento' : 'Continuar'}<Icon name="chevron" size={16}/></CaduButton>
        </div>
        <p className="wizard__skip">
          {!last && <button type="button" onClick={() => go(steps.length - 1)}>Pular e revisar</button>}
          <button type="button" onClick={onFullForm}>Prefiro o formulário completo</button>
        </p>
      </form>
    </main>
  </section>;
}
