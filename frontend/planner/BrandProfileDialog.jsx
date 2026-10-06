import React, {useState} from 'react';
import {CaduButton} from '../cadu-design-system/components/CaduButton.jsx';
import {CaduTextAreaField} from '../cadu-design-system/components/CaduField.jsx';
import {Icon} from '../cadu-design-system/components/Icon.jsx';
import {Illustration} from './Illustration.jsx';

const LABELS = {competitors: 'concorrentes', positioning: 'posicionamento', target_audience: 'público-alvo'};

/**
 * Fluxo separado: completar (ou atualizar) o perfil da marca. O Radar pesquisa e PROPÕE; nada é salvo sem
 * aprovação e o que a marca já tem é mantido: concorrentes novos entram na lista e texto preenchido só é trocado
 * se o usuário pedir.
 */
export function BrandProfileDialog({request, brand, onClose, onSaved}) {
  const [phase, setPhase] = useState('intro');
  const [error, setError] = useState('');
  const [proposal, setProposal] = useState(null);
  const [picked, setPicked] = useState({});
  const [text, setText] = useState({positioning: '', target_audience: ''});
  const [replace, setReplace] = useState({positioning: false, target_audience: false});
  const [saved, setSaved] = useState(null);

  const research = async () => {
    setPhase('working'); setError('');
    try {
      const data = (await request('/radar/brand-profile/research', {method: 'POST', body: JSON.stringify({brand_ref: brand.ref})})).proposal;
      setProposal(data);
      setPicked(Object.fromEntries(data.competitors.filter(item => item.is_new).map(item => [item.name, true])));
      setText({positioning: data.positioning, target_audience: data.target_audience});
      setReplace({positioning: false, target_audience: false});
      setPhase('review');
    } catch (failure) {
      setError(failure.message); setPhase('error');
    }
  };
  const save = async () => {
    setPhase('saving');
    try {
      const body = {brand_ref: brand.ref, competitors: proposal.competitors.filter(item => picked[item.name]).map(({name, description}) => ({name, description})),
        positioning: text.positioning, target_audience: text.target_audience, replace, sources: proposal.sources};
      setSaved(await request('/radar/brand-profile', {method: 'POST', body: JSON.stringify(body)}));
      setPhase('done');
    } catch (failure) {
      setError(failure.message); setPhase('error');
    }
  };

  const existing = proposal?.existing || {};
  const hasText = key => Boolean(existing[key]);
  const chosen = Object.values(picked).filter(Boolean).length;
  // Texto vazio no perfil entra direto; texto já preenchido só entra se o usuário marcar "trocar".
  const writes = chosen > 0 || ['positioning', 'target_audience'].some(key => text[key].trim() && (!hasText(key) || replace[key]));

  return <div className="bp-overlay" role="dialog" aria-modal="true" aria-label={`Completar o perfil de ${brand.name}`}>
    <div className="bp-dialog">
      <header><h2>{phase === 'done' ? 'Perfil atualizado' : `Completar o perfil de ${brand.name}`}</h2>
        <button type="button" className="bp-close" aria-label="Fechar" onClick={onClose}><Icon name="close" size={18}/></button></header>

      {phase === 'intro' && <>
        <p>O Radar pesquisa na web os <b>concorrentes</b>, o <b>posicionamento</b> e o <b>público</b> de {brand.name} e mostra uma proposta.
          Nada é salvo sem a sua aprovação, e o que a marca já tem no perfil é mantido: o que for novo é acrescentado.</p>
        <p className="planner-muted">A pesquisa usa poucos tokens do seu saldo.</p>
        <footer><CaduButton variant="secondary" onClick={onClose}>Agora não</CaduButton><CaduButton onClick={research}><Icon name="search" size={16}/>Pesquisar agora</CaduButton></footer>
      </>}

      {(phase === 'working' || phase === 'saving') && <div className="bp-working" role="status" aria-live="polite">
        <Illustration slot="radar-scan" busy/><strong>{phase === 'working' ? 'Pesquisando na web…' : 'Salvando no perfil…'}</strong>
        <p className="planner-muted">{phase === 'working' ? `Buscando concorrentes e posicionamento de ${brand.name}.` : 'Somando ao que já existe.'}</p></div>}

      {phase === 'review' && proposal && <>
        <section>
          <h3>Concorrentes</h3>
          {proposal.competitors.length === 0 ? <p className="planner-muted">Não encontramos concorrentes com fonte.</p> : <ul className="bp-list">
            {proposal.competitors.map(item => <li key={item.name}>
              <label><input type="checkbox" checked={Boolean(picked[item.name])} disabled={!item.is_new}
                onChange={event => setPicked(current => ({...current, [item.name]: event.target.checked}))}/>
                <span><b>{item.name}{!item.is_new && <i className="bp-tag">já no perfil</i>}</b>{item.description && <small>{item.description}</small>}</span></label>
            </li>)}</ul>}
          {existing.competitors?.length > 0 && <p className="planner-muted bp-kept">Já no perfil: {existing.competitors.join(', ')}.</p>}
        </section>
        {[['positioning', 'Posicionamento'], ['target_audience', 'Público-alvo']].map(([key, label]) => <section key={key}>
          <h3>{label}</h3>
          {hasText(key) && <p className="bp-kept"><b>Hoje no perfil:</b> {existing[key]}</p>}
          <CaduTextAreaField aria-label={label} rows={3} maxLength="600" value={text[key]} placeholder="Sem proposta para este campo."
            onChange={event => setText(current => ({...current, [key]: event.target.value}))}/>
          {hasText(key) && text[key].trim() && <label className="bp-replace"><input type="checkbox" checked={replace[key]}
            onChange={event => setReplace(current => ({...current, [key]: event.target.checked}))}/> Trocar o texto atual por este</label>}
        </section>)}
        {proposal.sources.length > 0 && <p className="planner-muted bp-sources">Fontes: {proposal.sources.map(url => <a key={url} href={url} target="_blank" rel="noreferrer noopener">{url.replace(/^https?:\/\/(www\.)?/, '').split('/')[0]}</a>)}</p>}
        <footer><CaduButton variant="secondary" onClick={onClose}>Cancelar</CaduButton>
          <CaduButton onClick={save} disabled={!writes}>Salvar no perfil da marca</CaduButton></footer>
      </>}

      {phase === 'done' && saved && <>
        <p>{saved.changed.length ? <>Acrescentamos ao perfil de {brand.name}: <b>{saved.changed.map(key => LABELS[key]).join(', ')}</b>. O que já existia foi mantido.</> : 'Nada mudou: tudo o que foi proposto já estava no perfil.'}</p>
        {saved.gaps.length > 0 && <p className="planner-muted">Ainda faltam: {saved.gaps.map(item => item.label).join(', ')}.</p>}
        <footer><CaduButton onClick={() => { onSaved?.(saved); onClose(); }}>Voltar ao radar</CaduButton></footer>
      </>}

      {phase === 'error' && <>
        <p className="radar-run__error">{error || 'Não foi possível concluir.'}</p>
        <footer><CaduButton variant="secondary" onClick={onClose}>Fechar</CaduButton><CaduButton onClick={proposal ? save : research}>Tentar de novo</CaduButton></footer>
      </>}
    </div>
  </div>;
}
