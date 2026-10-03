import React, {useEffect, useState} from 'react';
import {PipelinePicker, MOCKUP_MODE_LABEL} from './Mockups';
import {Badge, READINESS_LABEL, ROLES, ROLE_LABEL, Section, Swatches, Thumb, usd} from './ui';

const COPY_FIELDS = [
  ['kicker', 'Kicker / apresentador', 'GOVERNO DE MINAS APRESENTA'],
  ['headline', 'Headline', 'Viagem com até'],
  ['highlight', 'Herói (número ou palavra)', '60% OFF'],
  ['support', 'Apoio', 'Ofertas em passagens, hotéis e pacotes.'],
  ['cta', 'CTA', 'SAIBA MAIS'],
  ['seal', 'Selo', 'Oferta por tempo limitado!'],
  ['tagline', 'Tagline / assinatura', 'Onde tem você, tem o trabalho da Assembleia.'],
  ['legal', 'Legal / rodapé', 'Ouvidoria: 0800 940 5832'],
];
export const EMPTY_FORM = {
  scenario_key: '', title: '', task: 'generate', brand_id: '', aspect_ratio: '1:1', quality: 'standard', objective: 'paid social ad',
  instruction: '', must_include_text: [], preserve: [], alter: '', logo_mode: 'composer', payload_policy: 'verified_and_probable', references: [],
  brief: {archetype: '', audience: '', offer: '', copy: {}, casting: [], devices: []}, formats: ['feed-1x1'],
  pipeline: 'studio', mockup: {mode: 'image', family: '', id: ''},
};
const FIELD_STATUS = {verified: 'is-succeeded', probable: 'is-warn', partial: 'is-warn', needs_review: 'is-warn'};
const lines = value => String(value || '').split('\n').map(item => item.trim()).filter(Boolean);

function BrandPanel({brand, onImport, importing}) {
  const [role, setRole] = useState('PRODUCT');
  const readiness = brand.readiness;
  const fieldEntries = Object.entries(brand.fields || {}).filter(([, item]) => item.status !== 'not_applicable');
  return <div className="lab-brand">
    <div className={`lab-brand__verdict is-${readiness.level}`}>
      <Badge kind={`is-${readiness.level}`}>{READINESS_LABEL[readiness.level]}</Badge>
      <strong>{readiness.score}/100</strong>
      <p>{readiness.summary}</p>
    </div>
    <ul className="lab-checks is-grid">
      {readiness.checks.map(check => <li key={check.key} className={check.ok ? 'is-ok' : check.required ? 'is-bad' : 'is-muted'}>
        {check.ok ? '✓' : check.required ? '✕' : '○'} {check.label}{check.detail ? <small> · {check.detail}</small> : null}
      </li>)}
    </ul>
    <div className="lab-brand__identity">
      {brand.logo_url && <img className="lab-brand__logo" src={brand.logo_url} alt={`Logo ${brand.name}`}/>}
      <div>
        <Swatches colors={brand.palette} size="lg"/>
        <small className="lab-muted">{brand.palette.map(color => `${color.hex}${color.name ? ` ${color.name}` : ''}`).join(' · ') || 'sem paleta'}</small>
        <small className="lab-muted">{brand.fonts.map(font => font.family).join(', ') || 'sem fontes auditadas'}</small>
      </div>
    </div>
    {brand.text?.brand_summary && <p className="lab-brand__summary">{brand.text.brand_summary}</p>}
    <details className="lab-brand__fields">
      <summary>Campos da auditoria ({fieldEntries.length})</summary>
      <div className="lab-chips">{fieldEntries.map(([name, item]) => <Badge key={name} kind={FIELD_STATUS[item.status] || 'is-muted'}
        title={item.confidence != null ? `confiança ${item.confidence}` : ''}>{name} · {item.status}</Badge>)}</div>
    </details>
    {brand.assets.length > 0 && <div className="lab-brand__assets">
      <div className="lab-row is-between"><small>Imagens aprovadas da marca: clique para usar como</small>
        <select value={role} onChange={event => setRole(event.target.value)} aria-label="Papel da imagem">
          {ROLES.map(([key, label]) => <option key={key} value={key}>{label}</option>)}
        </select></div>
      <div className="lab-gallery is-small">
        {brand.assets.map(asset => <Thumb key={asset.asset_id} src={asset.url} alt={`Asset ${asset.asset_id}`}
          onClick={() => onImport(asset, role)} status={importing === asset.asset_id ? 'running' : undefined}>
          <span className="lab-thumb__tag">{asset.role}</span>
        </Thumb>)}
      </div>
    </div>}
  </div>;
}

export function Upload({api, brandId, onUploaded, defaultRole = 'PERSON', compact = false}) {
  const [file, setFile] = useState(null);
  const [role, setRole] = useState(defaultRole);
  const [label, setLabel] = useState('');
  const [person, setPerson] = useState(false);
  const [consent, setConsent] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const send = async event => {
    event.preventDefault();
    if (!file) return;
    const form = new FormData();
    form.append('file', file); form.append('role', role); form.append('label', label || file.name);
    if (brandId) form.append('brand_id', brandId);
    if (person) form.append('has_person', '1');
    if (consent) form.append('consent', '1');
    setError(''); setBusy(true);
    try { const data = await api.upload('/references', form); onUploaded(data.reference, role); setFile(null); setLabel(''); event.target.reset(); }
    catch (exc) { setError(exc.message); } finally { setBusy(false); }
  };
  return <form className={`lab-upload${compact ? ' is-compact' : ''}`} onSubmit={send}>
    <input type="file" accept="image/png,image/jpeg,image/webp" onChange={event => setFile(event.target.files?.[0] || null)} aria-label="Imagem"/>
    <select value={role} onChange={event => setRole(event.target.value)} aria-label="Papel">{ROLES.map(([key, text]) => <option key={key} value={key}>{text}</option>)}</select>
    <input value={label} placeholder="Rótulo (ex.: TIM Pré story 29GB)" onChange={event => setLabel(event.target.value)} aria-label="Rótulo"/>
    <label className="lab-check"><input type="checkbox" checked={person} onChange={event => setPerson(event.target.checked)}/> Tem pessoa</label>
    {person && <label className="lab-check"><input type="checkbox" checked={consent} onChange={event => setConsent(event.target.checked)}/> Há autorização de uso da imagem</label>}
    <button type="submit" className="lab-btn is-small" disabled={busy || !file || (person && !consent)}>{busy ? 'Enviando…' : 'Enviar'}</button>
    {error && <p className="lab-alert">{error}</p>}
  </form>;
}

function ArchetypePicker({archetypes, value, onChange}) {
  return <div className="lab-archetypes" role="radiogroup" aria-label="Arquétipo de layout">
    {archetypes.map(item => <button key={item.key} type="button" role="radio" aria-checked={value === item.key}
      className={`lab-archetype${value === item.key ? ' is-on' : ''}`} onClick={() => onChange(value === item.key ? '' : item.key)}>
      <strong>{item.label}</strong>
      <small>{item.when}</small>
      <em>aprendido de {item.learned_from}</em>
    </button>)}
  </div>;
}

export default function NewTest({state, api, onCreated, seed}) {
  const [form, setForm] = useState(seed || EMPTY_FORM);
  const [brand, setBrand] = useState(null);
  const [idea, setIdea] = useState('');
  const [rationale, setRationale] = useState('');
  const [models, setModels] = useState(() => state.models.filter(model => model.status === 'available').map(model => model.model_key));
  const [preview, setPreview] = useState(null);
  const [director, setDirector] = useState('');
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const refsById = Object.fromEntries(state.references.map(ref => [ref.ref_id, ref]));
  const set = patch => { setForm(current => ({...current, ...patch})); setPreview(null); };
  const setBrief = patch => set({brief: {...form.brief, ...patch}});
  const setCopy = (key, value) => setBrief({copy: {...form.brief.copy, [key]: value}});

  useEffect(() => { if (seed) { setForm({...EMPTY_FORM, ...seed}); setPreview(null); setDirector(''); } }, [seed]);
  useEffect(() => {
    if (!form.brand_id) { setBrand(null); return undefined; }
    let alive = true;
    api.get(`/brands/${form.brand_id}`).then(data => { if (alive) setBrand(data.brand); }).catch(exc => setError(exc.message));
    return () => { alive = false; };
  }, [form.brand_id]); // eslint-disable-line react-hooks/exhaustive-deps

  const loadScenario = async key => {
    if (!key) { setForm(EMPTY_FORM); return; }
    const scenario = state.scenarios.find(item => item.key === key);
    setBusy('scenario'); setError('');
    try {
      const data = await api.post(`/scenarios/${key}/prepare`, {});
      setForm({...EMPTY_FORM, ...data.form, scenario_key: '', brief: {...EMPTY_FORM.brief, ...(scenario?.brief || {})},
        formats: scenario?.formats || EMPTY_FORM.formats, title: `${scenario?.title || ''} (variação)`});
      setDirector(''); setPreview(null); onCreated?.(null);
    } catch (exc) { setError(exc.message); } finally { setBusy(''); }
  };
  const writeBrief = async () => {
    setBusy('brief'); setError(''); setRationale('');
    try {
      const data = await api.post('/brief', {idea, brand_id: form.brand_id || undefined, objective: form.objective, archetype: form.brief.archetype,
        format_key: form.formats[0], payload_policy: form.payload_policy, ref_id: form.brief.source_ref_id});
      const brief = data.brief;
      setForm(current => ({...current, objective: brief.objective || current.objective,
        brief: {...current.brief, archetype: brief.archetype, audience: brief.audience || '', offer: brief.offer || '', copy: brief.copy || {},
          casting: brief.casting || [], devices: brief.devices || []}}));
      setRationale(brief.rationale || ''); setPreview(null); setDirector('');
    } catch (exc) { setError(exc.message); } finally { setBusy(''); }
  };
  const addReference = (ref, role) => set({references: [...form.references.filter(item => item.ref_id !== ref.ref_id), {ref_id: ref.ref_id, role, label: ref.label}]});
  const importAsset = async (asset, role) => {
    setBusy(`asset-${asset.asset_id}`);
    try { const data = await api.post('/references/import', {asset_id: asset.asset_id, role, label: `${brand?.name || ''} ${ROLE_LABEL[role]}`.trim()}); addReference(data.reference, role); onCreated?.(null); }
    catch (exc) { setError(exc.message); } finally { setBusy(''); }
  };
  const toggleFormat = key => set({formats: form.formats.includes(key) ? form.formats.filter(item => item !== key) : [...form.formats, key]});
  const hasBrief = Boolean(form.brief.archetype || Object.values(form.brief.copy || {}).some(Boolean) || form.task === 'edit');
  const studio = form.pipeline === 'studio' && form.task === 'generate';
  const payload = () => ({...form, pipeline: studio ? 'studio' : 'raw', brief: {...form.brief, format_key: form.formats[0]},
    mockup: {...form.mockup, id: form.formats.length === 1 ? form.mockup.id : ''},
    director_prompt: studio ? undefined : (director || undefined), models, instruction: form.instruction || idea});
  const runPreview = async () => {
    setBusy('preview'); setError('');
    try { const data = await api.post('/preview', payload()); setPreview(data); if (!director) setDirector(data.spec.director_prompt); }
    catch (exc) { setError(exc.message); } finally { setBusy(''); }
  };
  const create = async () => {
    setBusy('create'); setError('');
    try {
      // The edited director prompt was written for the first format; other formats get their own diagram.
      const body = {...payload(), director_prompt: form.formats.length > 1 ? undefined : (director || undefined)};
      const data = await api.post('/experiments', body); onCreated?.(data);
    } catch (exc) { setError(exc.message); } finally { setBusy(''); }
  };
  const total = (preview?.plans || []).reduce((sum, item) => sum + (item.estimate.usd || 0), 0) * Math.max(1, form.formats.length);
  const ready = (form.instruction || idea || hasBrief) && models.length && form.formats.length;

  return <div className="lab-new">
    <Section title="1 · Ideia, marca e formatos" aside={<select value="" onChange={event => loadScenario(event.target.value)} aria-label="Partir de um cenário" disabled={busy === 'scenario'}>
      <option value="">Partir de um cenário…</option>
      {state.scenarios.filter(item => !item.reserved).map(item => <option key={item.key} value={item.key}>{item.group.split(' ')[0]} · {item.title}</option>)}
    </select>}>
      <div className="lab-form">
        <div className="lab-segmented" role="group" aria-label="Tarefa">
          <button type="button" aria-pressed={form.task === 'generate'} onClick={() => set({task: 'generate', pipeline: 'studio'})}>Criar anúncio</button>
          <button type="button" aria-pressed={form.task === 'edit'} onClick={() => set({task: 'edit', logo_mode: 'none', pipeline: 'raw'})}>Reformatar / editar peça</button>
        </div>
        <label>Marca<select value={form.brand_id || ''} onChange={event => set({brand_id: event.target.value ? Number(event.target.value) : ''})}>
          <option value="">Sem marca</option>
          {state.brands.map(item => <option key={item.id} value={item.id}>{item.name} · {item.verified_fields} verificados · {item.audits} auditoria(s)</option>)}
        </select></label>
        <label>Título do teste<input value={form.title} onChange={event => set({title: event.target.value})} placeholder="Ex.: Cemig WhatsApp · recorte"/></label>
        <label>Objetivo<input value={form.objective} onChange={event => set({objective: event.target.value})} placeholder="anúncio de oferta, institucional…"/></label>
        <label>Qualidade<select value={form.quality} onChange={event => set({quality: event.target.value})}>
          <option value="draft">Rascunho</option><option value="standard">Padrão</option><option value="high">Alta</option></select></label>
        <div className="is-wide">
          <small className="lab-label">Formatos (um teste por formato, mesma direção)</small>
          <div className="lab-chips">{(state.formats || []).map(item => <label key={item.key} className={`lab-chip-check${form.formats.includes(item.key) ? ' is-on' : ''}`}>
            <input type="checkbox" checked={form.formats.includes(item.key)} onChange={() => toggleFormat(item.key)}/>{item.label}<small>{item.ratio}</small>
          </label>)}</div>
        </div>
        {form.task === 'generate' && <label className="is-wide">Ideia (pode ser solta; o redator transforma em briefing)
          <textarea rows={2} value={idea} onChange={event => setIdea(event.target.value)} placeholder="Ex.: divulgar o atendimento da Cemig pelo WhatsApp para quem não quer ligar para a central"/>
        </label>}
        {form.task === 'edit' && <>
          <label className="is-wide">O que muda além do formato (opcional)<textarea rows={2} value={form.alter} onChange={event => set({alter: event.target.value})}/></label>
          <label className="is-wide">O que preservar (um por linha)<textarea rows={2} value={form.preserve.join('\n')} onChange={event => set({preserve: lines(event.target.value)})}/></label>
        </>}
      </div>
    </Section>

    {brand && <Section title={`2 · Marca: ${brand.name}`}><BrandPanel brand={brand} onImport={importAsset} importing={busy.startsWith('asset-') ? Number(busy.slice(6)) : null}/></Section>}

    <Section title="Pipeline e mockup" aside={<small className="lab-muted">cada peça do Studio é uma variável: ligue ou desligue por teste</small>}>
      <PipelinePicker state={state} form={form} set={set}/>
    </Section>

    {form.task === 'generate' && <Section title="3 · Briefing estruturado" aside={<button type="button" className="lab-btn" onClick={writeBrief} disabled={busy === 'brief' || (!idea && !form.brief.source_ref_id)}>
      {busy === 'brief' ? 'Escrevendo…' : 'Escrever briefing com IA'}</button>}>
      {rationale && <p className="lab-suggestion"><small>Redator</small><br/>{rationale}</p>}
      <small className="lab-label">Arquétipo de layout (aprendido de peças reais)</small>
      <ArchetypePicker archetypes={state.archetypes || []} value={form.brief.archetype} onChange={archetype => setBrief({archetype})}/>
      <div className="lab-form lab-copy-grid">
        {COPY_FIELDS.map(([key, label, placeholder]) => <label key={key}>{label}
          <input value={form.brief.copy?.[key] || ''} placeholder={placeholder} onChange={event => setCopy(key, event.target.value)}/>
        </label>)}
        <label className="is-wide">Público<input value={form.brief.audience || ''} onChange={event => setBrief({audience: event.target.value})} placeholder="Quem é e do que precisa"/></label>
        <label className="is-wide">Oferta / fato comercial<input value={form.brief.offer || ''} onChange={event => setBrief({offer: event.target.value})} placeholder="Só fatos reais: preço, taxa, prazo, condição"/></label>
        <label className="is-wide">Elenco (uma pessoa por linha: idade, profissão, ação, figurino, expressão, olhar)
          <textarea rows={3} value={(form.brief.casting || []).join('\n')} onChange={event => setBrief({casting: lines(event.target.value)})}/></label>
        <label className="is-wide">Kit gráfico (um por linha)
          <textarea rows={2} value={(form.brief.devices || []).join('\n')} onChange={event => setBrief({devices: lines(event.target.value)})}/></label>
        <label>Logo<select value={form.logo_mode} onChange={event => set({logo_mode: event.target.value})}>
          <option value="composer">Aplicado depois (Composer)</option><option value="native">Enviado ao modelo</option><option value="none">Sem logo</option></select></label>
        <label>Marca no prompt<select value={form.payload_policy} onChange={event => set({payload_policy: event.target.value})}>
          <option value="verified_only">Só campos verificados</option><option value="verified_and_probable">Verificados + prováveis</option><option value="all">Tudo da auditoria</option></select></label>
      </div>
    </Section>}

    <Section title={form.task === 'edit' ? '3 · Peça base e referências' : '4 · Referências'} aside={<small className="lab-muted">a mesma imagem nunca entra duas vezes</small>}>
      <div className="lab-gallery">
        {form.references.map(item => {
          const ref = refsById[item.ref_id];
          return <div key={item.ref_id} className="lab-ref">
            <Thumb src={ref?.thumb_url} alt={item.label}/>
            <select value={item.role} aria-label="Papel" onChange={event => set({references: form.references.map(other => other.ref_id === item.ref_id ? {...other, role: event.target.value} : other)})}>
              {ROLES.map(([key, label]) => <option key={key} value={key}>{label}</option>)}
            </select>
            <small title={item.label}>{item.label}{ref?.has_person ? ' · pessoa' : ''}</small>
            <button type="button" className="lab-btn is-ghost is-small" onClick={() => set({references: form.references.filter(other => other.ref_id !== item.ref_id)})}>Remover</button>
          </div>;
        })}
        {!form.references.length && <p className="lab-muted">{form.task === 'edit' ? 'Escolha a peça base (papel Base) na biblioteca ou envie uma.' : 'Sem referências: o modelo trabalha só com o briefing e a marca.'}</p>}
      </div>
      <Upload api={api} brandId={form.brand_id} defaultRole={form.task === 'edit' ? 'BASE' : 'PERSON'} onUploaded={(ref, role) => { addReference(ref, role); onCreated?.(null); }}/>
      {state.references.length > 0 && <details className="lab-library">
        <summary>Biblioteca do Lab ({state.references.length})</summary>
        <div className="lab-gallery is-small">{state.references.map(ref => <Thumb key={ref.ref_id} src={ref.thumb_url} alt={ref.label}
          onClick={() => addReference(ref, form.task === 'edit' ? 'BASE' : ref.role)}>
          <span className="lab-thumb__tag">{ref.is_benchmark ? 'peça real' : ROLE_LABEL[ref.role]}</span></Thumb>)}</div>
      </details>}
    </Section>

    <Section title="Modelos, plano e custo">
      <div className="lab-model-picks">{state.models.map(model => <label key={model.model_key} className={`lab-check is-card${model.status !== 'available' ? ' is-disabled' : ''}`}>
        <input type="checkbox" disabled={model.status !== 'available'} checked={models.includes(model.model_key)}
          onChange={event => { setPreview(null); setModels(current => event.target.checked ? [...current, model.model_key] : current.filter(key => key !== model.model_key)); }}/>
        <span><strong>{model.label}</strong><small>{model.capabilities.max_references} ref. · {model.provider === 'openai_direct' ? 'direto' : 'OpenRouter'}</small></span>
      </label>)}</div>
      <div className="lab-row">
        <button type="button" className="lab-btn is-ghost" onClick={runPreview} disabled={busy === 'preview' || !ready}>Ver plano e custo</button>
        <button type="button" className="lab-btn" onClick={create} disabled={busy === 'create' || !preview}>
          Gerar um a um ({models.length} modelo(s) × {form.formats.length} formato(s))</button>
        {preview && <span className="lab-muted">estimado {usd(total)}{preview.plans.some(item => item.estimate.variable) ? ' · variável por token' : ''}</span>}
      </div>
      {error && <p className="lab-alert">{error}</p>}
      {preview && studio && <div className="lab-director"><small className="lab-label">Briefing que o diretor do Studio recebe (a direção é gerada na primeira execução e congelada para todos os modelos)</small>
        <pre>{preview.spec.director_prompt}</pre></div>}
      {preview && !studio && <>
        <label className="lab-director">Director Prompt de {state.formats?.find(item => item.key === form.formats[0])?.label || form.formats[0]} (editável; com vários formatos, cada um recebe o próprio diagrama)
          <textarea rows={12} value={director} onChange={event => { setDirector(event.target.value); }}/>
        </label>
      </>}
      {preview && <>
        <div className="lab-plans">{preview.plans.map(item => {
          const model = state.models.find(other => other.model_key === item.model_key);
          return <article key={item.model_key} className={`lab-plan-card${item.plan.blocked ? ' is-blocked' : ''}`}>
            <header><strong>{model?.label}</strong><span>{usd(item.estimate.usd)}{item.estimate.variable ? '*' : ''}</span></header>
            <p>{item.plan.blocked || item.plan.summary}</p>
            {item.plan.mockup && <p className={item.plan.mockup.degraded ? 'lab-plan-mockup is-warn' : 'lab-plan-mockup'}>
              Mockup: {MOCKUP_MODE_LABEL[item.plan.mockup.effective]}{item.plan.mockup.degraded ? ' (o modelo não aceita a imagem; vai em texto)' : ''}</p>}
            <ul>
              {item.plan.sent.map(ref => <li key={`s${ref.ref_id}`}>Imagem {ref.order}: {ROLE_LABEL[ref.role]}</li>)}
              {item.plan.converted_to_text.map(ref => <li key={`t${ref.ref_id}`} className="is-warn">{ROLE_LABEL[ref.role]} → texto</li>)}
              {item.plan.post_processed.map(ref => <li key={`p${ref.role}${ref.ref_id}`}>{ref.role === 'FORMAT' ? ref.label : `${ROLE_LABEL[ref.role]} → Composer`}</li>)}
              {item.plan.dropped.map(ref => <li key={`d${ref.ref_id}`} className="is-bad">{ROLE_LABEL[ref.role]} descartada</li>)}
              {item.plan.parameters.transformed.map(change => <li key={change.param} className="is-warn">{change.param}: {change.from} → {change.to}</li>)}
            </ul>
            <details><summary>Prompt do modelo ({item.model_prompt.length} car.)</summary><pre>{item.model_prompt}</pre></details>
          </article>;
        })}</div>
      </>}
    </Section>
  </div>;
}
