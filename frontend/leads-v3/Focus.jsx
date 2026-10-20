import React, {useState} from 'react';
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
        !bare && <p className="lv3-muted">Defina canais e conteúdos de topo e meio de funil: a IA usa isso para personalizar cada mensagem.</p>
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
      <Button size="sm" variant="ghost" icon="pen" onClick={start}>{vazio ? 'Definir foco' : 'Editar foco'}</Button>
    </div>
  );
}

/** Contexto de mercado gerado por busca na web (com fontes). */
export function MarketContext({api, lead, notify, onChanged, bare = false}) {
  const [busy, setBusy] = useState(false);
  const [aberto, setAberto] = useState(false);
  const ctx = typeof lead.contexto_mercado === 'string' ? parseFoco(lead.contexto_mercado) : (lead.contexto_mercado || null);
  const gerar = async () => {
    setBusy(true);
    try { await api.marketContext(lead.id); notify('Contexto de mercado atualizado.'); onChanged(); }
    catch (error) { notify(error.message, 'error'); } finally { setBusy(false); }
  };
  return (
    <div className="lv3-context">
      {ctx?.texto ? (
        <>
          {/* Sem rolagem própria (o painel já rola): recolhido mostra o começo, "Ver tudo" abre o resto. */}
          <Markdown text={ctx.texto} fontes={ctx.fontes} className={`lv3-context__text ${aberto ? '' : 'is-collapsed'}`}/>
          <button type="button" className="lv3-link" onClick={() => setAberto(a => !a)}>{aberto ? 'Recolher' : 'Ver tudo'}</button>
          {ctx.fontes?.length > 0 && (
            <ol className="lv3-context__sources">
              {ctx.fontes.map((url, i) => {
                let host = url; try { host = new URL(url).hostname.replace(/^www\./, ''); } catch { /* mantém a url */ }
                return <li key={url}><a href={url} target="_blank" rel="noopener noreferrer">[{i + 1}] {host}</a></li>;
              })}
            </ol>
          )}
          <p className="lv3-muted">Gerado em {formatDate(ctx.gerado_em)} por busca na web. Confira as fontes antes de citar.</p>
        </>
      ) : (
        !bare && <p className="lv3-muted">Notícias, campanhas e tendências recentes da empresa e do setor, com fontes, para personalizar a abordagem.</p>
      )}
      <Button size="sm" variant={ctx?.texto ? 'ghost' : 'secondary'} icon="magnifying-glass-chart" onClick={gerar} disabled={busy}>
        {busy ? 'Pesquisando…' : ctx?.texto ? 'Atualizar contexto' : 'Pesquisar contexto de mercado'}
      </Button>
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
