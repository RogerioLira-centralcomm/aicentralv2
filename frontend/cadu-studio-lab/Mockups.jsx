import React, {useMemo, useState} from 'react';
import {Badge, Section} from './ui';

const LAB_TO_MASK_FORMAT = {'wide-16x9': 'youtube-16x9'};
export const MOCKUP_MODES = [
  ['image', 'Como imagem', 'O mockup vai ao modelo como referência de composição, como o Studio faz hoje.'],
  ['text', 'Só em texto', 'As mesmas zonas descritas em palavras, para modelos que não aceitam referência.'],
  ['none', 'Sem mockup', 'O modelo compõe o layout sozinho: linha de base para medir o ganho.'],
];
export const MOCKUP_MODE_LABEL = {image: 'mockup como imagem', text: 'mockup só em texto', none: 'sem mockup'};
const LOGO_LABEL = {'bottom-right': 'logo embaixo à direita', 'top-left': 'logo em cima à esquerda', none: 'sem logo'};

/** Same choice the server makes: the family asked for, preferring a mask with logo and CTA. */
export function maskFor(mockups, labFormat, family) {
  const format = LAB_TO_MASK_FORMAT[labFormat] || labFormat;
  const options = (mockups?.masks || []).filter(mask => mask.format === format);
  if (!options.length) return null;
  const same = family ? options.filter(mask => mask.family === family) : [];
  const pool = same.length ? same : options;
  return pool.find(mask => mask.logo !== 'none' && mask.cta) || pool[0];
}

export function MaskThumb({mask, size = 96, onClick, selected}) {
  const ratio = mask.width / mask.height;
  const style = ratio >= 1 ? {width: size * 1.4, aspectRatio: `${mask.width} / ${mask.height}`} : {height: size * 1.25, aspectRatio: `${mask.width} / ${mask.height}`};
  const Tag = onClick ? 'button' : 'div';
  return <Tag type={onClick ? 'button' : undefined} className={`lab-mask${selected ? ' is-on' : ''}${onClick ? ' is-action' : ''}`} onClick={onClick}
    title={`${mask.family_label} · ${LOGO_LABEL[mask.logo]}${mask.cta ? ' · com CTA' : ' · sem CTA'}`}>
    <img src={mask.url} alt={`Mockup ${mask.family_label}`} loading="lazy" style={style}/>
  </Tag>;
}

/** Pipeline + mockup choice of a test: raw model call, or the Studio's own pipeline with the mockup as an optional variable. */
export function PipelinePicker({state, form, set}) {
  const mockups = state.mockups;
  const mockup = form.mockup || {mode: 'image', family: '', id: ''};
  const setMockup = patch => set({mockup: {...mockup, ...patch}});
  const studio = form.pipeline === 'studio';
  const families = useMemo(() => {
    const keys = new Set((mockups?.masks || []).filter(mask => form.formats.some(format => (LAB_TO_MASK_FORMAT[format] || format) === mask.format)).map(mask => mask.family));
    return (mockups?.families || []).filter(item => keys.has(item.key));
  }, [mockups, form.formats]);
  const previews = form.formats.map(format => ({format, mask: maskFor(mockups, format, mockup.family)})).filter(item => item.mask);
  return <div className="lab-form">
    <div className="is-wide">
      <small className="lab-label">Pipeline</small>
      <div className="lab-segmented" role="group" aria-label="Pipeline">
        <button type="button" aria-pressed={!studio} onClick={() => set({pipeline: 'raw'})}>Modelo direto</button>
        <button type="button" aria-pressed={studio} onClick={() => set({pipeline: 'studio'})} disabled={form.task === 'edit'}>Pipeline do Studio</button>
      </div>
      <p className="lab-muted lab-tiny">{studio
        ? 'Usa o código do Studio sem alterá-lo: diretor, mockup, logo aplicado depois e ajuste ao formato. Só o modelo de imagem muda.'
        : 'Chama o modelo com o briefing do Lab, sem o diretor nem o mockup do Studio. Serve de comparação.'}
      {form.task === 'edit' ? ' Reformatar pelo pipeline do Studio ainda não está no Lab.' : ''}</p>
    </div>
    {studio && <>
      <div className="is-wide">
        <small className="lab-label">Mockup de composição (opcional por teste)</small>
        <div className="lab-segmented" role="group" aria-label="Modo do mockup">
          {MOCKUP_MODES.map(([key, label, hint]) => <button key={key} type="button" title={hint} aria-pressed={mockup.mode === key} onClick={() => setMockup({mode: key})}>{label}</button>)}
        </div>
        <p className="lab-muted lab-tiny">{MOCKUP_MODES.find(([key]) => key === mockup.mode)?.[2]} Modelos que não aceitam a imagem usam o texto automaticamente e o plano mostra isso.</p>
      </div>
      {mockup.mode !== 'none' && <>
        <label>Família de layout<select value={mockup.family || ''} onChange={event => setMockup({family: event.target.value, id: ''})}>
          <option value="">Padrão (foto com texto na base)</option>
          {families.map(item => <option key={item.key} value={item.key}>{item.label}</option>)}
        </select></label>
        <div className="is-wide lab-mask-row">
          {previews.map(({format, mask}) => <figure key={format}>
            <MaskThumb mask={mask} size={84}/>
            <figcaption>{state.formats?.find(item => item.key === format)?.label || format}<small>{mask.family_label}</small></figcaption>
          </figure>)}
          {!previews.length && <p className="lab-muted">Nenhum mockup do Studio para os formatos escolhidos.</p>}
        </div>
      </>}
    </>}
  </div>;
}

/** The Studio's composition masks, format by format, ready to be used as a test variable. */
export function MockupsView({state, onUse}) {
  const mockups = state.mockups || {masks: [], families: [], formats: []};
  const [format, setFormat] = useState(mockups.formats[0]?.key || '');
  const groups = [['social', 'Social'], ['iab', 'Display (IAB)']];
  const masks = mockups.masks.filter(mask => mask.format === format);
  const current = mockups.formats.find(item => item.key === format);
  const familyText = Object.fromEntries(mockups.families.map(item => [item.key, item.description]));
  return <div className="lab-mockups">
    <Section title="Mockups do Studio" aside={<small className="lab-muted">{mockups.masks.length} composições em {mockups.formats.length} formatos</small>}>
      <p className="lab-muted">São as máscaras de composição que o Studio manda ao modelo: bloco hachurado é o assunto, barras pretas são o título, a pílula é o CTA e o retângulo tracejado é o espaço do logo. A mesma máscara vira também um texto de zonas em porcentagem, que é o plano B para os modelos que não aceitam imagem de referência.</p>
      {groups.map(([key, label]) => <div key={key} className="lab-mockups__formats">
        <small className="lab-label">{label}</small>
        <div className="lab-chips">{mockups.formats.filter(item => item.group === key).map(item => <button key={item.key} type="button"
          className={`lab-chip-check${format === item.key ? ' is-on' : ''}`} aria-pressed={format === item.key} onClick={() => setFormat(item.key)}>
          {item.label}<small>{item.width}×{item.height}</small></button>)}</div>
      </div>)}
    </Section>
    <Section title={`${current?.label || ''} · ${masks.length} mockup(s)`}>
      <div className="lab-mask-grid">
        {masks.map(mask => <article key={mask.id} className="lab-mask-card">
          <MaskThumb mask={mask} size={170}/>
          <div>
            <strong>{mask.family_label}</strong>
            <small className="lab-muted">{familyText[mask.family]}</small>
            <div className="lab-chips">
              <Badge kind="is-muted">{LOGO_LABEL[mask.logo]}</Badge>
              <Badge kind="is-muted">{mask.cta ? 'com CTA' : 'sem CTA'}</Badge>
              <Badge kind="is-muted">{mask.zones.length} zonas</Badge>
            </div>
            <button type="button" className="lab-btn is-small" onClick={() => onUse(mask)}>Testar este mockup</button>
          </div>
        </article>)}
      </div>
    </Section>
  </div>;
}
