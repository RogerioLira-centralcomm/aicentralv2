import React, {useCallback, useEffect, useState} from 'react';
import {Button, Field, Icon, Markdown, formatDate} from './ui.jsx';

export const CANAIS = [
  {value: 'email', label: 'E-mail', icon: 'envelope'},
  {value: 'whatsapp', label: 'WhatsApp', icon: 'comment'},
  {value: 'linkedin', label: 'LinkedIn', icon: 'user-group'},
  {value: 'telefone', label: 'Telefone', icon: 'phone'},
  {value: 'evento', label: 'Evento', icon: 'calendar'},
];
const MARCOS = [
  ['', 'Sem marco'], ['primeira_conversa', '1ª conversa'], ['reuniao', 'Reunião'], ['apresentacao', 'Apresentação'],
  ['proposta', 'Proposta'], ['fechamento', 'Fechamento'],
];
const ROLES = [['marketing', 'Marketing'], ['midia', 'Mídia'], ['criacao', 'Criação'], ['diretoria', 'Diretoria']];

const parseFoco = value => {
  if (!value) return {};
  if (typeof value === 'string') { try { return JSON.parse(value) || {}; } catch { return {}; } }
  return value;
};

/** Foco da empresa: canais preferidos e conteúdos de topo e meio de funil (alimentam as mensagens da IA). */
export function FocusEditor({api, lead, notify, onChanged, compact = false, bare = false}) {
  const foco = parseFoco(lead.foco_conteudo);
  const canais = lead.canais_foco || [];
  const [form, setForm] = useState(null);
  const [busy, setBusy] = useState(false);
  const vazio = !canais.length && !foco.topo && !foco.meio && !foco.tom && !foco.evitar;

  const start = () => setForm({canais: [...canais], topo: foco.topo || '', meio: foco.meio || '', tom: foco.tom || '', evitar: foco.evitar || ''});
  // A IA propõe a partir da pauta; o executivo revisa no formulário antes de salvar.
  const sugerir = async () => {
    setBusy(true);
    try {
      const s = await api.suggestFocus(lead.id);
      setForm({canais: [...canais], topo: s.topo || '', meio: s.meio || '', tom: s.tom || '', evitar: s.evitar || ''});
    } catch (error) { notify(error.message, 'error'); } finally { setBusy(false); }
  };
  const toggle = value => setForm(f => ({...f, canais: f.canais.includes(value) ? f.canais.filter(c => c !== value) : [...f.canais, value]}));
  const save = async event => {
    event.preventDefault();
    setBusy(true);
    try {
      await api.updateCompany(lead.id, {canais_foco: form.canais, foco_conteudo: {topo: form.topo, meio: form.meio, tom: form.tom, evitar: form.evitar}});
      notify('Foco da empresa salvo.');
      setForm(null);
      onChanged();
    } catch (error) { notify(error.message, 'error'); } finally { setBusy(false); }
  };

  if (form) {
    return (
      <form className="lv3-focus lv3-focus--edit" onSubmit={save}>
        <div className="lv3-focus__channels" role="group" aria-label="Canais preferidos">
          {CANAIS.map(c => (
            <button key={c.value} type="button" aria-pressed={form.canais.includes(c.value)} className={`lv3-toggle ${form.canais.includes(c.value) ? 'is-on' : ''}`} onClick={() => toggle(c.value)}>
              <Icon name={c.icon}/>{c.label}
            </button>
          ))}
        </div>
        <Field label="Conteúdos de TOPO de funil (gerar interesse)" wide>
          <textarea className="lv3-input lv3-textarea" rows={2} value={form.topo} onChange={e => setForm(f => ({...f, topo: e.target.value}))}
            placeholder="Ex.: estudo de audiência do setor, tendências de mídia em mineração, ideias de campanha para ESG"/>
        </Field>
        <Field label="Conteúdos de MEIO de funil (aprofundar)" wide>
          <textarea className="lv3-input lv3-textarea" rows={2} value={form.meio} onChange={e => setForm(f => ({...f, meio: e.target.value}))}
            placeholder="Ex.: case de mídia programática B2B, diagnóstico de presença digital, convite para workshop"/>
        </Field>
        <div className="lv3-form__grid">
          <Field label="Tom"><input className="lv3-input" value={form.tom} onChange={e => setForm(f => ({...f, tom: e.target.value}))} placeholder="Consultivo, direto"/></Field>
          <Field label="Evitar"><input className="lv3-input" value={form.evitar} onChange={e => setForm(f => ({...f, evitar: e.target.value}))} placeholder="Falar de preço, concorrente X"/></Field>
        </div>
        <div className="lv3-form__actions">
          <Button onClick={() => setForm(null)} disabled={busy}>Cancelar</Button>
          <Button variant="primary" type="submit" disabled={busy}>{busy ? 'Salvando…' : 'Salvar foco'}</Button>
        </div>
      </form>
    );
  }

  return (
    <div className={`lv3-focus ${compact ? 'lv3-focus--compact' : ''}`}>
      {vazio ? (
        !bare && <p className="lv3-muted">Temas de topo e meio de funil e o tom com essas pessoas. A IA sugere a partir da pauta pesquisada.</p>
      ) : (
        <>
          {canais.length > 0 && (
            <div className="lv3-focus__channels">
              {canais.map(v => { const c = CANAIS.find(x => x.value === v); return c ? <span key={v} className="lv3-toggle is-on is-static"><Icon name={c.icon}/>{c.label}</span> : null; })}
            </div>
          )}
          <dl className="lv3-focus__list">
            {foco.topo && <><dt><span className="lv3-funnel lv3-funnel--topo">Topo</span></dt><dd>{foco.topo}</dd></>}
            {foco.meio && <><dt><span className="lv3-funnel lv3-funnel--meio">Meio</span></dt><dd>{foco.meio}</dd></>}
            {foco.tom && <><dt>Tom</dt><dd>{foco.tom}</dd></>}
            {foco.evitar && <><dt>Evitar</dt><dd>{foco.evitar}</dd></>}
          </dl>
        </>
      )}
      <div className="lv3-focus__tools">
        <Button size="sm" variant="ghost" icon="wand-magic-sparkles" onClick={sugerir} disabled={busy}>{busy ? 'Sugerindo…' : 'Sugerir com IA'}</Button>
        <Button size="sm" variant="ghost" icon="pen" onClick={start} disabled={busy}>{vazio ? 'Definir à mão' : 'Editar foco'}</Button>
      </div>
    </div>
  );
}

const TIPOS_GANCHO = {empresa: 'Empresa', campanha: 'Campanha', concorrente: 'Concorrente', setor: 'Dado do setor',
  lideranca: 'Liderança', tendencia: 'Tendência'};

const host = url => { try { return new URL(url).hostname.replace(/^www\./, ''); } catch { return url; } };

/** Um gancho da pauta: fato, número, ângulo e fonte; o executivo escolhe ou descarta. */
function HookCard({gancho, onStatus, busy}) {
  const escolhido = gancho.status === 'escolhido';
  return (
    <li className={`lv3-hook ${escolhido ? 'is-chosen' : ''} ${gancho.status === 'descartado' ? 'is-discarded' : ''}`}>
      <div className="lv3-hook__tags">
        <span className={`lv3-funnel lv3-funnel--${gancho.etapa}`}>{gancho.etapa}</span>
        <span className="lv3-hook__type">{TIPOS_GANCHO[gancho.tipo] || gancho.tipo}</span>
        {gancho.numero && <span className="lv3-hook__number">{gancho.numero}</span>}
        {gancho.usos > 0 && <span className="lv3-hook__used">usado {gancho.usos}x</span>}
      </div>
      <p className="lv3-hook__fact">{gancho.fato}</p>
      {gancho.angulo && <p className="lv3-hook__angle">{gancho.angulo}</p>}
      <div className="lv3-hook__foot">
        {gancho.fonte_url
          ? <a href={gancho.fonte_url} target="_blank" rel="noopener noreferrer">{gancho.fonte_nome || host(gancho.fonte_url)}{gancho.data_fato ? ` · ${gancho.data_fato}` : ''}</a>
          : <span className="lv3-muted">sem fonte</span>}
        <span className="lv3-hook__actions">
          {gancho.status === 'descartado' ? (
            <button type="button" className="lv3-link lv3-link--muted" disabled={busy} onClick={() => onStatus(gancho, 'sugerido')}>Restaurar</button>
          ) : (
            <>
              <button type="button" className={`lv3-iconbtn ${escolhido ? 'is-on' : ''}`} title={escolhido ? 'Tirar dos escolhidos' : 'Usar nas mensagens'} aria-pressed={escolhido}
                disabled={busy} onClick={() => onStatus(gancho, escolhido ? 'sugerido' : 'escolhido')}><Icon name="star"/></button>
              <button type="button" className="lv3-iconbtn lv3-iconbtn--danger" title="Descartar" disabled={busy} onClick={() => onStatus(gancho, 'descartado')}><Icon name="xmark"/></button>
            </>
          )}
        </span>
      </div>
    </li>
  );
}

/** Gancho escrito pelo executivo (algo que ele leu ou ouviu), com fonte. */
function HookForm({api, leadId, notify, onSaved, onCancel}) {
  const [form, setForm] = useState({fato: '', fonte_url: '', etapa: 'topo', tipo: 'empresa'});
  const [busy, setBusy] = useState(false);
  const save = async event => {
    event.preventDefault();
    setBusy(true);
    try { await api.createHook(leadId, form); notify('Gancho adicionado.'); onSaved(); }
    catch (error) { notify(error.message, 'error'); } finally { setBusy(false); }
  };
  return (
    <form className="lv3-hookform" onSubmit={save}>
      <Field label="Fato (com número, se tiver)" wide>
        <textarea className="lv3-input lv3-textarea" rows={2} required value={form.fato} onChange={e => setForm(f => ({...f, fato: e.target.value}))}
          placeholder="Ex.: a marca abriu 40 lojas no Nordeste em 2026"/>
      </Field>
      <Field label="Fonte (link)" wide><input className="lv3-input" type="url" value={form.fonte_url} onChange={e => setForm(f => ({...f, fonte_url: e.target.value}))} placeholder="https://"/></Field>
      <div className="lv3-form__grid">
        <Field label="Etapa">
          <select className="lv3-select" value={form.etapa} onChange={e => setForm(f => ({...f, etapa: e.target.value}))}>
            <option value="topo">Topo</option><option value="meio">Meio</option>
          </select>
        </Field>
        <Field label="Tipo">
          <select className="lv3-select" value={form.tipo} onChange={e => setForm(f => ({...f, tipo: e.target.value}))}>
            {Object.entries(TIPOS_GANCHO).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </Field>
      </div>
      <div className="lv3-form__actions">
        <Button onClick={onCancel} disabled={busy}>Cancelar</Button>
        <Button variant="primary" type="submit" disabled={busy}>{busy ? 'Salvando…' : 'Adicionar gancho'}</Button>
      </div>
    </form>
  );
}

/** Pauta da empresa: resumo do momento e ganchos com fonte (pesquisa na web) para puxar conversa. */
export function MarketContext({api, lead, notify, onChanged, bare = false}) {
  const [busy, setBusy] = useState('');
  const [aberto, setAberto] = useState(false);
  const [ganchos, setGanchos] = useState(null);
  const [novo, setNovo] = useState(false);
  const [verDescartados, setVerDescartados] = useState(false);
  const ctx = typeof lead.contexto_mercado === 'string' ? parseFoco(lead.contexto_mercado) : (lead.contexto_mercado || null);

  const carregar = useCallback(async () => {
    try { setGanchos(await api.hooks(lead.id)); } catch { setGanchos([]); }
  }, [api, lead.id]);
  useEffect(() => { carregar(); }, [carregar]);

  const pesquisar = async () => {
    setBusy('pesquisa');
    try {
      const r = await api.marketContext(lead.id);
      notify(r.ganchos_novos ? `Pauta atualizada: ${r.ganchos_novos} ganchos com fonte.` : 'Pesquisa feita, mas sem ganchos com fonte. Tente de novo ou adicione à mão.');
      await carregar();
      onChanged();
    } catch (error) { notify(error.message, 'error'); } finally { setBusy(''); }
  };
  const mudarStatus = async (gancho, status) => {
    setBusy(`g${gancho.id}`);
    try { await api.updateHook(gancho.id, {status}); await carregar(); onChanged(); }
    catch (error) { notify(error.message, 'error'); } finally { setBusy(''); }
  };

  const ativos = (ganchos || []).filter(g => g.status !== 'descartado');
  const descartados = (ganchos || []).filter(g => g.status === 'descartado');
  const temAlgo = ctx?.texto || ativos.length > 0;
  return (
    <div className="lv3-context">
      {ctx?.texto && (
        <>
          <Markdown text={ctx.texto} fontes={ctx.fontes} className={`lv3-context__text ${aberto ? '' : 'is-collapsed'}`}/>
          {ctx.texto.length > 280 && <button type="button" className="lv3-link" onClick={() => setAberto(a => !a)}>{aberto ? 'Recolher' : 'Ver tudo'}</button>}
        </>
      )}
      {ativos.length > 0 && (
        <>
          <p className="lv3-muted">Marque com a estrela os ganchos que quer usar. Cada mensagem usa um, sem repetir com a mesma pessoa.</p>
          <ul className="lv3-hooks">
            {ativos.map(g => <HookCard key={g.id} gancho={g} onStatus={mudarStatus} busy={!!busy}/>)}
          </ul>
        </>
      )}
      {descartados.length > 0 && (
        <>
          <button type="button" className="lv3-link lv3-link--muted" onClick={() => setVerDescartados(v => !v)}>
            {verDescartados ? 'Esconder descartados' : `${descartados.length} descartado${descartados.length > 1 ? 's' : ''}`}
          </button>
          {verDescartados && <ul className="lv3-hooks">{descartados.map(g => <HookCard key={g.id} gancho={g} onStatus={mudarStatus} busy={!!busy}/>)}</ul>}
        </>
      )}
      {!temAlgo && !bare && (
        <p className="lv3-muted">Fatos reais e recentes da empresa, dos concorrentes e do setor, com fonte, para puxar conversa sobre mídia e marketing.</p>
      )}
      {ctx?.gerado_em && <p className="lv3-muted">Pesquisado em {formatDate(ctx.gerado_em)}. Confira a fonte antes de citar.</p>}
      {novo && <HookForm api={api} leadId={lead.id} notify={notify} onSaved={() => { setNovo(false); carregar(); onChanged(); }} onCancel={() => setNovo(false)}/>}
      <div className="lv3-focus__tools">
        <Button size="sm" variant={temAlgo ? 'ghost' : 'secondary'} icon="magnifying-glass-chart" onClick={pesquisar} disabled={!!busy}>
          {busy === 'pesquisa' ? 'Pesquisando na web…' : temAlgo ? 'Atualizar pauta' : 'Pesquisar pauta'}
        </Button>
        {!novo && <Button size="sm" variant="ghost" icon="plus" onClick={() => setNovo(true)} disabled={!!busy}>Gancho à mão</Button>}
      </div>
    </div>
  );
}

/** Alvo da conta no Golden Circle: objetivo, valor, prazo, próximo marco e cobertura dos papéis. */
export function GoldenTarget({api, conta, contacts, notify, onChanged}) {
  const [form, setForm] = useState(null);
  const [busy, setBusy] = useState(false);
  const papeis = conta.papeis_alvo?.length ? conta.papeis_alvo : ROLES.map(r => r[0]);
  const coberto = p => contacts.some(c => c.papel === p);
  const save = async event => {
    event.preventDefault();
    setBusy(true);
    try {
      await api.updateGolden(conta.id, {meta: form.meta, valor_alvo: form.valor_alvo, prazo: form.prazo || null, proximo_marco: form.proximo_marco || null, papeis_alvo: form.papeis_alvo});
      notify('Alvo da conta salvo.');
      setForm(null);
      onChanged();
    } catch (error) { notify(error.message, 'error'); } finally { setBusy(false); }
  };

  if (form) {
    return (
      <form className="lv3-target lv3-target--edit" onSubmit={save}>
        <Field label="Objetivo no trimestre" wide>
          <textarea className="lv3-input lv3-textarea" rows={2} value={form.meta} onChange={e => setForm(f => ({...f, meta: e.target.value}))} placeholder="Ex.: entrar no plano de mídia 2027 com programática e CTV"/>
        </Field>
        <div className="lv3-form__grid">
          <Field label="Valor-alvo (R$)"><input className="lv3-input" inputMode="decimal" value={form.valor_alvo} onChange={e => setForm(f => ({...f, valor_alvo: e.target.value}))}/></Field>
          <Field label="Prazo"><input className="lv3-input" type="date" value={form.prazo} onChange={e => setForm(f => ({...f, prazo: e.target.value}))}/></Field>
          <Field label="Próximo marco">
            <select className="lv3-select" value={form.proximo_marco} onChange={e => setForm(f => ({...f, proximo_marco: e.target.value}))}>
              {MARCOS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </Field>
        </div>
        <div className="lv3-focus__channels" role="group" aria-label="Papéis a cobrir">
          {ROLES.map(([v, l]) => (
            <button key={v} type="button" aria-pressed={form.papeis_alvo.includes(v)} className={`lv3-toggle ${form.papeis_alvo.includes(v) ? 'is-on' : ''}`}
              onClick={() => setForm(f => ({...f, papeis_alvo: f.papeis_alvo.includes(v) ? f.papeis_alvo.filter(x => x !== v) : [...f.papeis_alvo, v]}))}>{l}</button>
          ))}
        </div>
        <div className="lv3-form__actions">
          <Button onClick={() => setForm(null)} disabled={busy}>Cancelar</Button>
          <Button variant="primary" type="submit" disabled={busy}>{busy ? 'Salvando…' : 'Salvar alvo'}</Button>
        </div>
      </form>
    );
  }

  const marco = MARCOS.find(([v]) => v === (conta.proximo_marco || ''))?.[1];
  return (
    <div className="lv3-target">
      <p className="lv3-target__goal">{conta.meta || <span className="lv3-muted">Sem objetivo definido para o trimestre.</span>}</p>
      <dl className="lv3-target__facts">
        <div><dt>Valor-alvo</dt><dd>{conta.valor_alvo != null ? Number(conta.valor_alvo).toLocaleString('pt-BR', {style: 'currency', currency: 'BRL', maximumFractionDigits: 0}) : '—'}</dd></div>
        <div><dt>Prazo</dt><dd>{conta.prazo ? formatDate(conta.prazo) : `fim de ${conta.trimestre.replace('-', ' ')}`}</dd></div>
        <div><dt>Próximo marco</dt><dd>{conta.proximo_marco ? marco : '—'}</dd></div>
      </dl>
      <div className="lv3-roles">
        {papeis.map(p => <span key={p} className={`lv3-role ${coberto(p) ? 'is-on' : ''}`}>{ROLES.find(r => r[0] === p)?.[1] || p}</span>)}
      </div>
      <Button size="sm" variant="ghost" icon="pen" onClick={() => setForm({meta: conta.meta || '', valor_alvo: conta.valor_alvo ?? '', prazo: conta.prazo || '', proximo_marco: conta.proximo_marco || '', papeis_alvo: [...papeis]})}>Editar alvo</Button>
    </div>
  );
}
