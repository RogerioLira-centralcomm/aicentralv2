import React, {useState} from 'react';
import {modelStats} from './Matrix';
import {Upload} from './NewTest';
import {Badge, CopyUrl, FAILURE_LABEL, Notes, ROLE_LABEL, ScorePill, Section, Swatches, Thumb, seconds, usd} from './ui';

function price(pricing = []) {
  const out = pricing.filter(row => row.billable === 'output_image');
  if (!out.length) return 'sem preço no catálogo';
  return out.map(row => row.unit === 'token' ? `US$ ${(row.cost_usd * 1e6).toFixed(0)}/M tokens de saída`
    : `US$ ${row.cost_usd}${row.variant ? ` (${row.variant})` : ''}/${row.unit === 'image' ? 'imagem' : row.unit}`).join(' · ');
}

export function ModelsView({state, api, onNotes}) {
  return <div className="lab-models">
    {state.models.map(model => {
      const caps = model.capabilities || {};
      const stats = modelStats(state.runs, model.model_key);
      const proposals = state.proposals.filter(item => item.model_key === model.model_key);
      return <article key={model.model_key} className="lab-model">
        <header>
          <div><h3>{model.label}</h3><small className="lab-mono">{model.provider_model_id}</small></div>
          <Badge kind={model.status === 'available' ? 'is-succeeded' : 'is-failed'}>{model.status === 'available' ? 'Disponível' : 'Indisponível'}</Badge>
        </header>
        <div className="lab-model__stats">
          <div><small>Nota média</small><ScorePill score={stats.score}/></div>
          <div><small>Gerações</small><strong>{stats.n}</strong></div>
          <div><small>Tempo médio</small><strong>{seconds(stats.latency)}</strong></div>
          <div><small>Gasto</small><strong>{usd(stats.cost)}</strong></div>
        </div>
        <dl className="lab-model__caps">
          <dt>Rota</dt><dd>{model.provider === 'openai_direct' ? 'OpenAI direto' : `OpenRouter → ${(caps.providers || []).join(', ') || '—'}`}</dd>
          <dt>Referências</dt><dd>até {caps.max_references ?? '—'}</dd>
          <dt>Formatos</dt><dd>{(caps.aspect_ratios || []).filter(item => item !== 'auto').join(' · ') || '—'}</dd>
          <dt>Custo</dt><dd>{price(caps.pricing)}</dd>
          <dt>Controle</dt><dd>{caps.qualities?.length ? `quality ${caps.qualities.join('/')}` : caps.resolutions?.length ? `resolution ${caps.resolutions.join('/')}` : 'preço fixo'}{caps.supports_seed ? ' · seed' : ''}</dd>
          <dt>Passthrough</dt><dd>{(caps.passthrough || []).join(', ') || '—'}</dd>
          <dt>Perfil</dt><dd>v{model.profile_version} · prompt em {model.prompt_profile.language} · até {model.prompt_profile.max_chars} car. · logo {model.reference_policy.logo === 'composer_overlay' ? 'pelo Composer' : 'nativo'}</dd>
        </dl>
        <div className="lab-model__notes">
          <h4>Anotações do manifesto</h4>
          <ul>{(model.notes || []).map(note => <li key={note}>{note}</li>)}</ul>
          {stats.topFailure && <p className="lab-muted">Falha mais frequente: {FAILURE_LABEL[stats.topFailure[0]]} ({stats.topFailure[1]}×)</p>}
          {proposals.length > 0 && <>
            <h4>Ajustes propostos</h4>
            <ul>{proposals.map(item => <li key={item.id}><Badge kind="is-warn">{FAILURE_LABEL[item.failure] || item.failure}</Badge> {item.rationale} <small className="lab-muted">({item.evidence} evidência(s))</small></li>)}</ul>
          </>}
          <h4>Anotações da equipe</h4>
          <Notes notes={state.notes} scope="model" scopeKey={model.model_key} api={api} onSaved={onNotes} placeholder={`O que aprendemos sobre ${model.label}?`}/>
        </div>
      </article>;
    })}
  </div>;
}

export function ScenariosNotes({state, api, onNotes}) {
  return <div className="lab-scenarios">
    {state.scenarios.map(item => <article key={item.key} className={`lab-scenario${item.reserved ? ' is-reserved' : ''}`}>
      <header><Badge kind={item.task === 'edit' ? 'is-edit' : 'is-generate'}>{item.task === 'edit' ? 'Editar' : 'Gerar'}</Badge><h3>{item.title}</h3></header>
      <p><small className="lab-muted">Variável</small><br/>{item.variable}</p>
      <p><small className="lab-muted">Hipótese</small><br/>{item.hypothesis}</p>
      <Notes notes={state.notes} scope="scenario" scopeKey={item.key} api={api} onSaved={onNotes} placeholder="Conclusão ou dúvida sobre este teste"/>
    </article>)}
  </div>;
}

function Anatomy({anatomy, archetypes}) {
  const kind = archetypes.find(item => item.key === anatomy.archetype);
  const copy = Object.entries(anatomy.copy || {});
  return <div className="lab-anatomy">
    <p><Badge kind="is-generate">{kind?.label || anatomy.archetype}</Badge> <span className="lab-muted">{anatomy.format}</span></p>
    {anatomy.hero && <p><small className="lab-muted">Herói</small> <strong>{anatomy.hero.element}</strong> — {anatomy.hero.why_it_dominates}</p>}
    {copy.length > 0 && <ul className="lab-anatomy__copy">{copy.map(([key, value]) => <li key={key}><small>{key}</small> “{value}”</li>)}</ul>}
    {(anatomy.people || []).length > 0 && <p><small className="lab-muted">Elenco</small> {anatomy.people.map(person => person.description).join(' | ')}</p>}
    {(anatomy.devices || []).length > 0 && <p><small className="lab-muted">Kit</small> {anatomy.devices.join(' · ')}</p>}
    {anatomy.palette_roles && <p><small className="lab-muted">Cores</small> <Swatches colors={Object.values(anatomy.palette_roles).filter(Boolean)}/></p>}
    {(anatomy.what_works || []).length > 0 && <><small className="lab-muted">O que funciona</small><ul>{anatomy.what_works.map(item => <li key={item}>{item}</li>)}</ul></>}
    {(anatomy.risks || []).length > 0 && <><small className="lab-muted">O que a IA tende a errar</small><ul className="is-warn">{anatomy.risks.map(item => <li key={item}>{item}</li>)}</ul></>}
  </div>;
}

function ReformatForm({reference, state, api, onDone}) {
  const [formats, setFormats] = useState(['story-9x16', 'wide-16x9']);
  const [models, setModels] = useState(() => state.models.filter(model => model.status === 'available').map(model => model.model_key));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const toggle = (list, setList, key) => setList(list.includes(key) ? list.filter(item => item !== key) : [...list, key]);
  const send = async () => {
    setBusy(true); setError('');
    try { await api.post(`/references/${reference.ref_id}/reformat`, {formats, models}); onDone(); }
    catch (exc) { setError(exc.message); } finally { setBusy(false); }
  };
  return <div className="lab-reformat">
    <small className="lab-label">Formatos</small>
    <div className="lab-chips">{state.formats.map(item => <label key={item.key} className={`lab-chip-check${formats.includes(item.key) ? ' is-on' : ''}`}>
      <input type="checkbox" checked={formats.includes(item.key)} onChange={() => toggle(formats, setFormats, item.key)}/>{item.label}</label>)}</div>
    <small className="lab-label">Modelos</small>
    <div className="lab-chips">{state.models.filter(model => model.capabilities.max_references > 0).map(model => <label key={model.model_key} className={`lab-chip-check${models.includes(model.model_key) ? ' is-on' : ''}`}>
      <input type="checkbox" checked={models.includes(model.model_key)} onChange={() => toggle(models, setModels, model.model_key)}/>{model.label}</label>)}</div>
    <button type="button" className="lab-btn is-small" disabled={busy || !formats.length || !models.length} onClick={send}>
      {busy ? 'Enfileirando…' : `Desdobrar (${formats.length * models.length} gerações)`}</button>
    {error && <p className="lab-alert">{error}</p>}
  </div>;
}

export function ReferencesView({state, api, onChanged, onSeedBrief}) {
  const brands = Object.fromEntries(state.brands.map(brand => [brand.id, brand.name]));
  const [busy, setBusy] = useState(null);
  const [open, setOpen] = useState(null);
  const [error, setError] = useState('');
  const analyze = async ref => {
    setBusy(ref.ref_id); setError('');
    try { await api.post(`/references/${ref.ref_id}/anatomy`, {}); await onChanged(); setOpen({id: ref.ref_id, mode: 'anatomy'}); }
    catch (exc) { setError(exc.message); } finally { setBusy(null); }
  };
  const benchmarks = state.references.filter(ref => ref.is_benchmark);
  const others = state.references.filter(ref => !ref.is_benchmark);
  const card = ref => <article key={ref.ref_id} className={`lab-ref is-card${open?.id === ref.ref_id ? ' is-open' : ''}`}>
    <Thumb src={ref.thumb_url} alt={ref.label} ratio={ref.width && ref.height ? `${ref.width} / ${ref.height}` : '1 / 1'}>
      <span className="lab-thumb__tag">{ref.is_benchmark ? 'peça real' : ROLE_LABEL[ref.role]}</span></Thumb>
    <strong title={ref.label}>{ref.label}</strong>
    <small className="lab-muted">{brands[ref.brand_id] || 'Sem marca'} · {ref.source === 'brand_asset' ? `asset ${ref.source_ref}` : ref.source}{ref.has_person ? ' · pessoa' : ''} · {ref.width}×{ref.height}</small>
    <div className="lab-row">
      <button type="button" className="lab-btn is-ghost is-small" disabled={busy === ref.ref_id} onClick={() => ref.anatomy ? setOpen(open?.id === ref.ref_id && open.mode === 'anatomy' ? null : {id: ref.ref_id, mode: 'anatomy'}) : analyze(ref)}>
        {busy === ref.ref_id ? 'Analisando…' : ref.anatomy ? 'Anatomia' : 'Analisar anatomia'}</button>
      <button type="button" className="lab-btn is-ghost is-small" onClick={() => setOpen(open?.id === ref.ref_id && open.mode === 'reformat' ? null : {id: ref.ref_id, mode: 'reformat'})}>Desdobrar</button>
      {ref.anatomy && <button type="button" className="lab-btn is-ghost is-small" onClick={() => onSeedBrief(ref)}>Usar como briefing</button>}
    </div>
    {open?.id === ref.ref_id && open.mode === 'anatomy' && ref.anatomy && <Anatomy anatomy={ref.anatomy} archetypes={state.archetypes || []}/>}
    {open?.id === ref.ref_id && open.mode === 'reformat' && <ReformatForm reference={ref} state={state} api={api} onDone={() => { setOpen(null); onChanged(); }}/>}
    <CopyUrl url={ref.public_url}/>
  </article>;
  return <div className="lab-references">
    <Section title="Peças reais para aprender" aside={<small className="lab-muted">suba anúncios de referência: o Lab decompõe a anatomia e usa como briefing, referência ou base de desdobramento</small>}>
      <Upload api={api} defaultRole="COMPOSITION" compact onUploaded={async ref => { await onChanged(); analyze(ref); }}/>
      {error && <p className="lab-alert">{error}</p>}
      <div className="lab-gallery is-references">{benchmarks.map(card)}{!benchmarks.length && <p className="lab-muted">Nenhuma peça real analisada ainda.</p>}</div>
    </Section>
    <Section title={`Referências dos testes (${others.length})`}>
      <div className="lab-gallery is-references">{others.map(card)}</div>
    </Section>
  </div>;
}

export function ProposalsView({state}) {
  if (!state.proposals.length) return <p className="lab-muted">Nenhuma proposta ainda. Elas surgem quando o TypeSafe aponta a mesma falha com confiança ≥ 50%.</p>;
  const models = Object.fromEntries(state.models.map(model => [model.model_key, model.label]));
  return <table className="lab-table">
    <thead><tr><th>Modelo</th><th>Falha</th><th>Mudança no manifesto</th><th>Por quê</th><th>Evidências</th><th>Status</th></tr></thead>
    <tbody>{state.proposals.map(item => <tr key={item.id}>
      <td>{models[item.model_key] || item.model_key} <small className="lab-muted">v{item.from_version}</small></td>
      <td>{FAILURE_LABEL[item.failure] || item.failure}</td>
      <td className="lab-mono lab-tiny">{JSON.stringify(item.change)}</td>
      <td>{item.rationale}</td>
      <td>{item.evidence} <small className="lab-muted">#{(item.evidence_run_ids || []).join(', #')}</small></td>
      <td><Badge kind="is-warn">{item.status === 'pending_review' ? 'Aguarda revisão' : item.status}</Badge></td>
    </tr>)}</tbody>
  </table>;
}

const STUDIO_MODEL = 'gpt-image-2';
const STUDIO_REFS = 3;
const TIERS = [['draft', 'Econômica'], ['standard', 'Padrão'], ['high', 'Alta']];

function sentParams(model, tier) {
  const caps = model.capabilities || {};
  const mapped = model.quality_map?.[tier] || {};
  const parts = [];
  if (model.provider === 'openai_direct') return mapped.quality ? `quality ${mapped.quality}` : 'sem controle';
  if (caps.qualities?.length && mapped.quality) parts.push(`quality ${mapped.quality}`);
  if (caps.resolutions?.length && mapped.resolution) parts.push(`resolution ${mapped.resolution}`);
  return parts.join(' · ') || 'sem controle (preço fixo)';
}

function differences(model) {
  const caps = model.capabilities || {};
  const items = [];
  if (model.status !== 'available') return [['bad', 'Indisponível no catálogo']];
  if (model.provider === 'openrouter') items.push(['warn', 'Rota diferente: o Studio chama a OpenAI direto; OpenRouter é só a reserva']);
  if (model.provider === 'openrouter') items.push(['warn', 'Sem tamanho exato: usa a proporção mais próxima e recorta (o Studio pede o tamanho final)']);
  const refs = caps.max_references ?? 0;
  if (refs < 1) items.push(['bad', 'Não aceita imagem de referência: máscara e referências viram texto']);
  else if (refs < STUDIO_REFS) items.push(['warn', `Aceita ${refs} referência(s); o Studio manda até ${STUDIO_REFS} (máscara + 2). O excesso vira texto ou é descartado`]);
  if (!Object.keys(model.quality_map?.standard || {}).length) items.push(['warn', 'Sem controle de qualidade: "Padrão" e "Alta" geram igual']);
  if ((model.prompt_profile?.max_chars || 0) < 3800) items.push(['warn', `Prompt limitado a ${model.prompt_profile.max_chars} car.; o Studio envia mais, então o texto é reduzido`]);
  if (model.reference_policy?.logo !== 'composer_overlay') items.push(['warn', 'Logo enviado ao modelo; o Studio aplica o logo depois']);
  if (!items.length) items.push(['ok', model.provider_model_id === STUDIO_MODEL ? 'Igual ao Studio' : 'Só o modelo muda; parâmetros iguais ao Studio']);
  return items;
}

export function ParametersView({state}) {
  return <div className="lab-params">
    <p className="lab-muted">Uma linha por modelo: o que o Lab envia comparado ao que o Studio envia hoje. Só valem para decidir produção os testes em “Pipeline do Studio”, e as diferenças em amarelo ou vermelho precisam ser aceitas antes de trocar o modelo do Studio.</p>
    <table className="lab-table">
      <thead><tr><th>Modelo</th><th>Rota</th>{TIERS.map(([, label]) => <th key={label}>{label}</th>)}<th>Tamanho</th><th>Referências</th><th>Prompt</th><th>Diferenças em relação ao Studio</th></tr></thead>
      <tbody>
        <tr>
          <td><strong>Studio hoje</strong><br/><small className="lab-mono">{STUDIO_MODEL}</small></td>
          <td>OpenAI direto</td><td>quality low · 1K</td><td>quality medium · 1K</td><td>quality high · 2K</td>
          <td>exato (ex.: 1536×864)</td><td>até {STUDIO_REFS} (máscara + 2)</td><td>até 3800 car.</td>
          <td><small className="lab-muted">Referência da comparação</small></td>
        </tr>
        {state.models.map(model => {
          const caps = model.capabilities || {};
          return <tr key={model.model_key}>
            <td><strong>{model.label}</strong><br/><small className="lab-mono">{model.provider_model_id}</small></td>
            <td>{model.provider === 'openai_direct' ? 'OpenAI direto' : `OpenRouter${caps.providers?.length ? ` → ${caps.providers.join(', ')}` : ''}`}</td>
            {TIERS.map(([tier]) => <td key={tier}>{sentParams(model, tier)}</td>)}
            <td>{model.provider === 'openai_direct' ? 'exato' : `proporção: ${(caps.aspect_ratios || []).filter(item => item !== 'auto').length} opções, recorte no fim`}</td>
            <td>{caps.max_references ?? '—'}</td>
            <td>até {model.prompt_profile?.max_chars} car.</td>
            <td><ul className="lab-diff">{differences(model).map(([kind, text]) => <li key={text}><Badge kind={kind === 'ok' ? 'is-succeeded' : kind === 'bad' ? 'is-failed' : 'is-warn'}>{kind === 'ok' ? 'ok' : kind === 'bad' ? 'bloqueia' : 'difere'}</Badge> {text}</li>)}</ul></td>
          </tr>;
        })}
      </tbody>
    </table>
  </div>;
}
