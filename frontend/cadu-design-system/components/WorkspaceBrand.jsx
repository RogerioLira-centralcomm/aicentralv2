import React, {useEffect, useRef, useState} from 'react';
import './WorkspaceBrand.css';
import {CaduDock} from './CaduDock';
import {WorkspaceAccountMenu} from './WorkspaceFeedback';
import {VisualIdentity} from './VisualIdentity';
import {CaduDialog} from './CaduDialog';
import {openWorkspaceDetail} from '../workspaceNavigation';
import {WorkspaceMobileChrome} from './WorkspaceMobileChrome';
import {useWorkspaceViewport} from '../hooks/useWorkspaceViewport';
import {BrandCompletion, EntityContextRail, EntityNavigator} from './WorkspaceEntityPortal';

const assetLabels = {logo: 'Logo', reference: 'Referência', creative: 'Peça criativa', background: 'Fundo', support: 'Apoio visual', icon: 'Ícone', cta_style: 'Estilo de CTA'};
const reviewStatus = {ready: 'Pronto para aprovação', review: 'Requer revisão'};
const assetUrl = (template, id) => String(template || '').replace('__ASSET_ID__', encodeURIComponent(id));

function Hidden({name, value}) { return <input type="hidden" name={name} value={value || ''}/>; }
const campaignProjectUrl = (template, id) => String(template || '').replace('__CAMPAIGN_ID__', encodeURIComponent(id));

function BrandState({type, brand, canEdit, onAudit, onIdentity}) {
  const processing = type === 'processing';
  const failed = type === 'failed';
  return <section className={`cadu-ds-brand-state cadu-ds-brand-state--${type}`} id={processing ? 'analise' : 'estado-marca'} aria-live={processing ? 'polite' : undefined}>
    <div className="cadu-ds-brand-state__visual" aria-hidden="true" />
    <div className="cadu-ds-brand-state__copy">
      <p>{processing ? 'Auditoria em andamento' : failed ? 'Não foi possível concluir a análise' : 'Informações insuficientes'}</p>
      <h2>{processing ? <>Estamos organizando os sinais de {brand.name}</> : failed ? 'Corrija a fonte antes de tentar novamente' : 'Ainda não há informações suficientes sobre esta marca'}</h2>
      <span>{processing ? 'O site, os links oficiais e as referências estão sendo processados. Quando houver evidências suficientes, o dossiê aparecerá nesta página.' : failed ? brand.reviewPack?.error || 'A fonte principal não pôde ser confirmada. Revise o endereço e inicie uma nova auditoria.' : 'Adicione o site oficial, a logo ou referências confiáveis para identificar posicionamento, público e sistema visual.'}</span>
      {processing ? <small>Você pode sair desta página. O processamento continua em segundo plano.</small> : <div className="cadu-ds-brand-state__actions">{canEdit && <button type="button" className="is-primary" onClick={onAudit}>Preparar análise</button>}{canEdit && <button type="button" onClick={onIdentity}>Adicionar informações</button>}</div>}
    </div>
  </section>;
}

function FilledReading({items, emptyLabel = 'Adicione contexto para orientar as próximas decisões.'}) {
  const filled = items.filter(item => item.value && (!Array.isArray(item.value) || item.value.length));
  return filled.length ? <div className="cadu-ds-brand-reading cadu-ds-brand-reading--direction">{filled.map(item => { const parts = asList(item.value).map(value => String(value).trim()).filter(Boolean); const isLong = parts.length > 1 || parts[0]?.length > 180; return <article key={item.label} className={isLong ? 'is-long' : ''}><small>{item.label}</small>{parts.length > 1 ? <div className="cadu-ds-brand-readable-copy">{parts.map((part, index) => <p key={`${item.label}-${index}`}>{part}</p>)}</div> : <b>{parts[0]}</b>}</article>; })}</div> : <div className="cadu-ds-brand-reading-empty">{emptyLabel}</div>;
}

function BrandDialog({title, detail, onClose, children, className = ''}) {
  return <CaduDialog className={`cadu-ds-brand-dialog ${className}`} label={title} onClose={onClose}>
    <header><div><h2>{title}</h2>{detail && <p>{detail}</p>}</div><button type="button" onClick={onClose} aria-label="Fechar">×</button></header>
    {children}
  </CaduDialog>;
}

function IdentityDialog({brand, urls, csrfToken, onClose}) {
  return <BrandDialog title="Dados administrativos" detail="A identidade visual vem da análise da marca. Alterações de direção devem acontecer em conversa com o Cadu e ferramentas conectadas." onClose={onClose}>
    <form className="cadu-ds-brand-form" method="post" action={urls.updateIdentity}>
      <Hidden name="_csrf" value={csrfToken}/>
      <label>Nome da marca<input name="name" required minLength="2" maxLength="150" defaultValue={brand.name}/></label>
      <label>Site oficial<input name="website_url" type="url" maxLength="2000" placeholder="https://" defaultValue={brand.websiteUrl}/></label>
      <small className="cadu-ds-brand-form__note">Cores, tipografia, logo e direção não são editadas manualmente. Elas são extraídas das fontes, revisadas e aprovadas.</small>
      <footer><button type="button" onClick={() => window.location.assign(urls.conversation)}>Atualizar em conversa</button><button type="button" onClick={onClose}>Cancelar</button><button className="is-primary">Salvar metadados</button></footer>
    </form>
  </BrandDialog>;
}

function LinkProjectsDialog({brand, projects, csrfToken, onClose}) {
  return <BrandDialog title={`Vincular ${brand.name}`} detail="Escolha um projeto para manter esta identidade disponível no contexto de trabalho." onClose={onClose}>
    <div className="cadu-ds-brand-project-picker">{projects.length ? projects.map(project => <form method="post" action={project.linkUrl} key={project.id}><Hidden name="_csrf" value={csrfToken}/><input type="hidden" name="add_brand_id" value={brand.id}/><button type="submit"><span><b>{project.name}</b><small>{project.description || 'Sem contexto inicial'}</small></span><i aria-hidden="true">+</i></button></form>) : <p className="cadu-ds-brand-empty">Nenhum projeto ativo disponível.</p>}</div>
  </BrandDialog>;
}

function CreateBrandProjectDialog({brand, action, csrfToken, onClose}) {
  return <BrandDialog title={`Novo projeto para ${brand.name}`} detail="O projeto será criado já conectado à base desta marca." onClose={onClose}>
    <form className="cadu-ds-project-form" method="post" action={action}>
      <Hidden name="_csrf" value={csrfToken}/><Hidden name="brand_id" value={brand.id}/>
      <label>Nome<input name="name" required minLength="2" maxLength="150" autoFocus/></label>
      <label>Contexto inicial<textarea name="description" rows="3" maxLength="4000"/></label>
      <label>Orientações para o Cadu<textarea name="instructions" rows="4" maxLength="12000"/></label>
      <footer><button type="button" onClick={onClose}>Cancelar</button><button className="is-primary">Criar projeto</button></footer>
    </form>
  </BrandDialog>;
}

function BrandAuditUploads() {
  const picker = useRef(null);
  const logoInput = useRef(null);
  const referencesInput = useRef(null);
  const [files, setFiles] = useState([]);
  const [logoIndex, setLogoIndex] = useState(0);
  const [active, setActive] = useState(false);
  useEffect(() => () => files.forEach(item => URL.revokeObjectURL(item.preview)), [files]);
  const syncInputs = (selected, primaryIndex) => {
    if (!selected.length || !logoInput.current || !referencesInput.current) return 0;
    const safeIndex = Math.min(primaryIndex, selected.length - 1);
    const logoTransfer = new DataTransfer();
    const referenceTransfer = new DataTransfer();
    selected.forEach((file, index) => (index === safeIndex ? logoTransfer : referenceTransfer).items.add(file));
    logoInput.current.files = logoTransfer.files;
    referencesInput.current.files = referenceTransfer.files;
    setLogoIndex(safeIndex);
    return safeIndex;
  };
  const distribute = (items, primaryIndex = 0) => {
    const selected = Array.from(items || []).filter(file => file.type.startsWith('image/')).slice(0, 4);
    if (!selected.length) return;
    syncInputs(selected, primaryIndex);
    setFiles(selected.map(file => ({file, preview:URL.createObjectURL(file)})));
  };
  const chooseLogo = index => {
    syncInputs(files.map(item => item.file), index);
  };
  return <div className="cadu-ds-brand-audit-uploads">
    <input ref={picker} type="file" accept="image/*" multiple hidden onChange={event => { distribute(event.target.files); event.target.value = ''; }}/>
    <input ref={logoInput} name="logo_image" type="file" accept="image/*" hidden aria-hidden="true" tabIndex="-1"/>
    <input ref={referencesInput} name="images" type="file" accept="image/*" multiple hidden aria-hidden="true" tabIndex="-1"/>
    <button type="button" className={`cadu-ds-brand-audit-uploads__picker${active ? ' is-active' : ''}`} onClick={() => picker.current?.click()} onDragEnter={event => { event.preventDefault(); setActive(true); }} onDragOver={event => event.preventDefault()} onDragLeave={event => { if (event.currentTarget === event.target) setActive(false); }} onDrop={event => { event.preventDefault(); setActive(false); distribute(event.dataTransfer.files); }}>
      <strong>{files.length ? `${files.length} imagem${files.length === 1 ? '' : 's'} pronta${files.length === 1 ? '' : 's'}` : 'Adicionar imagens'}</strong>
      <span>Clique ou solte aqui · logo e até três referências</span>
    </button>
    {files.length > 0 && <div className="cadu-ds-brand-audit-uploads__files" aria-label="Imagens adicionadas">{files.map((item, index) => <button type="button" key={`${item.file.name}-${item.file.lastModified}`} className={index === logoIndex ? 'is-logo' : ''} aria-label={`${item.file.name}: usar como logo`} aria-pressed={index === logoIndex} onClick={() => chooseLogo(index)}><img src={item.preview} alt=""/><span>{index === logoIndex ? 'Logo' : 'Referência'}</span><small title={item.file.name}>{item.file.name}</small></button>)}</div>}
  </div>;
}

function BrandAuditSources({initialAdditional = [], initialExcluded = []}) {
  const [additional, setAdditional] = useState(initialAdditional);
  const [excluded, setExcluded] = useState(initialExcluded);
  const [value, setValue] = useState('');
  const [exclude, setExclude] = useState(false);
  const [error, setError] = useState('');
  const add = () => {
    const raw = value.trim();
    if (!raw) return;
    let url;
    try { url = new URL(/^https?:\/\//i.test(raw) ? raw : `https://${raw}`); } catch (_) { setError('Informe um endereço válido.'); return; }
    if (!['http:', 'https:'].includes(url.protocol)) { setError('Use um endereço http ou https.'); return; }
    const normalized = url.toString();
    const target = exclude ? excluded : additional;
    if (target.includes(normalized)) { setError('Esta fonte já foi adicionada.'); return; }
    (exclude ? setExcluded : setAdditional)(items => [...items, normalized].slice(0, 12));
    setValue(''); setError('');
  };
  const sourceLabel = source => { try { return new URL(source).hostname.replace(/^www\./, ''); } catch (_) { return source; } };
  return <details className="cadu-ds-brand-audit-sources">
    <Hidden name="source_preferences_present" value="true"/>
    <summary>Adicionar fonte específica</summary>
    <div className="cadu-ds-brand-audit-sources__form">
      <label>Endereço<input type="url" value={value} placeholder="https://" onChange={event => { setValue(event.target.value); setError(''); }} onKeyDown={event => { if (event.key === 'Enter') { event.preventDefault(); add(); } }}/></label>
      <label className="cadu-ds-brand-audit-sources__exclude"><input type="checkbox" checked={exclude} onChange={event => setExclude(event.target.checked)}/> Ignorar esta fonte</label>
      <button type="button" onClick={add}>Adicionar</button>
      {error && <small role="alert">{error}</small>}
    </div>
    {additional.length > 0 && <div className="cadu-ds-brand-audit-source-list"><strong>Referências informadas</strong>{additional.map(source => <span key={source}><Hidden name="additional_sources" value={source}/><b title={source}>{sourceLabel(source)}</b><button type="button" onClick={() => setAdditional(items => items.filter(item => item !== source))} aria-label={`Remover ${source}`}>×</button></span>)}</div>}
    {excluded.length > 0 && <div className="cadu-ds-brand-audit-source-list is-excluded"><strong>Fontes ignoradas</strong>{excluded.map(source => <span key={source}><Hidden name="excluded_sources" value={source}/><b title={source}>{sourceLabel(source)}</b><button type="button" onClick={() => setExcluded(items => items.filter(item => item !== source))} aria-label={`Remover exclusão de ${source}`}>×</button></span>)}</div>}
  </details>;
}

function AuditDialog({brand, urls, csrfToken, creditAvailable = 0, onClose}) {
  const [mode, setMode] = useState(() => Number(brand.readiness?.score || 0) < 85 && Number(creditAvailable || 0) > 0 ? 'deep' : 'complete');
  const [showAllAssets, setShowAllAssets] = useState(false);
  const existingSocialLinks = brand.auditInput?.socialLinks || brand.analysisMetadata?.socialLinks || [];
  const existingAdditionalSources = brand.auditInput?.additionalSources || brand.reviewPack?.input?.additional_sources || [];
  const existingExcludedSources = brand.auditInput?.excludedSources || brand.reviewPack?.input?.excluded_sources || [];
  const reusableAssets = (brand.assets || []).filter(asset => asset.reusable);
  const assetPreviewLimit = mode === 'deep' ? 12 : 8;
  const visibleAssets = showAllAssets ? reusableAssets : reusableAssets.slice(0, assetPreviewLimit);
  const hasPrimaryAsset = reusableAssets.some(asset => asset.isPrimary);
  const hasDeepCredit = Number(creditAvailable || 0) > 0;
  const estimates = mode === 'deep' ? {tokens: 'até 150 mil créditos', time: '6–12 min'} : {tokens: 'até 75 mil créditos', time: '3–8 min'};
  let officialSite = brand.websiteUrl || '';
  try { officialSite = new URL(officialSite).hostname.replace(/^www\./, ''); } catch (_) { /* Keep the available label. */ }
  return <BrandDialog title="Atualizar análise da marca" detail="Sua identidade atual permanece protegida até você aprovar a nova análise." onClose={onClose} className="cadu-ds-brand-audit-dialog">
    <form className="cadu-ds-brand-form" method="post" encType="multipart/form-data" action={urls.audit}>
      <Hidden name="_csrf" value={csrfToken}/>
      <Hidden name="social_links" value={existingSocialLinks.join('\n')}/>
      <div className="cadu-ds-brand-audit-dialog__columns">
        <section className="cadu-ds-brand-audit-dialog__column" aria-labelledby="audit-sources-title"><header><strong id="audit-sources-title">Fontes atuais</strong><span>O Cadu encontra os links oficiais.</span></header>{brand.websiteUrl ? <><Hidden name="website_url" value={brand.websiteUrl}/><div className="cadu-ds-brand-audit-site"><small>Site oficial</small><b>{officialSite}</b></div></> : <label>Site oficial<input type="url" name="website_url" maxLength="2000" placeholder="https://"/></label>}<BrandAuditSources initialAdditional={existingAdditionalSources} initialExcluded={existingExcludedSources}/>{reusableAssets.length > 0 ? <div className="cadu-ds-brand-audit-existing"><Hidden name="existing_assets_present" value="true"/><strong>Ativos disponíveis</strong><div>{visibleAssets.map((asset, index) => <label key={asset.id}><input type="checkbox" name="existing_asset_ids" value={asset.id} defaultChecked={asset.isPrimary || asset.role !== 'logo' || (!hasPrimaryAsset && index === 0)}/><img src={asset.displayUrl} alt=""/><small>{asset.metadata?.label || assetLabels[asset.role] || 'Ativo'}</small></label>)}</div>{!showAllAssets && reusableAssets.length > assetPreviewLimit && <button type="button" className="cadu-ds-brand-audit-existing__more" onClick={() => setShowAllAssets(true)}>Ver todos os {reusableAssets.length} ativos</button>}</div> : <p className="cadu-ds-brand-audit-empty">Nenhum ativo salvo. Você pode adicionar imagens ao lado.</p>}</section>
        <section className="cadu-ds-brand-audit-dialog__column" aria-labelledby="audit-files-title"><header><strong id="audit-files-title">Novos arquivos</strong><span>Use somente o que deseja analisar agora.</span></header><BrandAuditUploads/></section>
        <aside className="cadu-ds-brand-audit-dialog__column cadu-ds-brand-audit-dialog__scope" aria-labelledby="audit-mode-title"><header><strong id="audit-mode-title">Tipo de análise</strong><span>Escolha o alcance desta atualização.</span></header><label className={mode === 'complete' ? 'is-selected' : ''}><span><input type="radio" name="analysis_mode" value="complete" checked={mode === 'complete'} onChange={() => setMode('complete')}/><b>Completa</b><em>3–8 min</em></span><small>Identidade, oferta, público e direção visual.</small></label><label className={`${mode === 'deep' ? 'is-selected ' : ''}${!hasDeepCredit ? 'is-disabled' : ''}`}><span><input type="radio" name="analysis_mode" value="deep" checked={mode === 'deep'} disabled={!hasDeepCredit} onChange={() => setMode('deep')}/><b>Profunda</b><em>6–12 min</em></span><small>{hasDeepCredit ? 'Mercado, concorrência e campanhas.' : 'Disponível quando houver saldo de créditos.'}</small></label><div className="cadu-ds-brand-audit-dialog__estimate"><small>Consumo máximo</small><strong>{estimates.tokens}</strong></div></aside>
      </div>
      <div className="cadu-ds-brand-audit-dialog__footer"><label className="cadu-ds-brand-check"><input type="checkbox" name="confirmed_cost" value="true" required/> Confirmo o consumo de {estimates.tokens}.</label><footer><button type="button" onClick={onClose}>Cancelar</button><button className="is-primary">Atualizar análise</button></footer></div>
    </form>
  </BrandDialog>;
}

function AuditScreenshot({metadata = {}}) {
  if (!metadata.screenshot) return null;
  const colors = (metadata.screenshotColorPalette || metadata.cssColorEvidence || []).slice(0, 6);
  return <section className="cadu-ds-brand-section cadu-ds-brand-screenshot"><header><div><p>Leitura visual</p><h2>Captura renderizada da marca</h2><span>Screenshot oficial usado junto com OCR, CSS e logo para validar a identidade.</span></div></header><figure><img src={metadata.screenshot} alt="Captura renderizada do site oficial da marca" loading="lazy"/><figcaption><span>{metadata.screenshotOcr ? `OCR: ${metadata.screenshotOcr}` : 'OCR não identificou texto legível nesta captura.'}</span>{colors.length > 0 && <div aria-label="Cores extraídas da captura">{colors.map(color => <i key={color.hex} title={`${color.hex} · ${color.occurrences || color.confidence || ''}`} style={{backgroundColor: color.hex}}/> )}</div>}</figcaption></figure></section>;
}

function ReviewDialog({brand, urls, csrfToken, canEdit, onClose}) {
  const reviews = brand.reviewPack?.reviews || [];
  const review = reviews.find(item => item.id === 'central' || /central/i.test(item.title || '')) || reviews[reviews.length - 1];
  const fieldLabels = {brand_summary:'Resumo',target_audience:'Público',tone_of_voice:'Tom de voz',creative_guidelines:'Direção criativa',products_services:'Produtos e serviços',differentiators:'Diferenciais',proof_points:'Provas',color_palette:'Paleta',fonts:'Tipografia',visual_motifs:'Motivos visuais',contacts:'Contatos',addresses:'Endereços',competitors:'Concorrentes',campaigns:'Campanhas',personas:'Personas',logo_url:'Logo'};
  const blocked = new Set((review?.blocked_fields || []).map(item => String(item).split(':', 1)[0]));
  const proposedFields = Object.entries(brand.reviewPack?.analysis || {}).filter(([key, value]) => fieldLabels[key] && value != null && value !== '' && (!Array.isArray(value) || value.length));
  return <BrandDialog title={`Síntese da análise de ${brand.name}`} detail="Uma leitura consolidada para orientar a próxima decisão." onClose={onClose} className="cadu-ds-brand-review-dialog">
    <div className="cadu-ds-brand-reviews">{review ? <article><header><div><small>Decisão central</small><b>{reviewStatus[review.status] || 'Leitura disponível'}</b></div><span>{Math.round((Number(review.confidence) || 0) * 100)}% de confiança</span></header><p>{review.summary || 'A análise não retornou uma síntese utilizável.'}</p>{review.findings?.length > 0 && <div><strong>O que foi comprovado</strong><ul>{review.findings.slice(0, 6).map(item => <li key={item}>{item}</li>)}</ul></div>}{review.concerns?.length > 0 && <div className="is-concern"><strong>O que ainda precisa de revisão</strong><ul>{review.concerns.slice(0, 6).map(item => <li key={item}>{item}</li>)}</ul></div>}</article> : <p className="cadu-ds-brand-empty">Ainda não há uma síntese disponível para esta marca.</p>}</div>
    {canEdit && proposedFields.length > 0 ? <form method="post" action={urls.approve} className="cadu-ds-brand-field-approval"><Hidden name="_csrf" value={csrfToken}/><strong>Escolha o que entra na identidade atual</strong><div>{proposedFields.map(([key]) => <label key={key}><input type="checkbox" name="approved_fields" value={key} defaultChecked={!blocked.has(key)}/><span>{fieldLabels[key]}</span>{blocked.has(key) && <small>revisar</small>}</label>)}</div><footer><button type="button" onClick={onClose}>Cancelar</button><button className="is-primary">Aprovar campos selecionados</button></footer></form> : <footer><button type="button" onClick={onClose}>Fechar</button></footer>}
  </BrandDialog>;
}

function DeleteBrandDialog({brand, linkedProjects, urls, csrfToken, onClose}) {
  const [confirmation, setConfirmation] = useState('');
  const normalizedConfirmation = value => String(value || '').trim().replace(/\s+/g, ' ').toLocaleLowerCase('pt-BR');
  const matches = normalizedConfirmation(confirmation) === normalizedConfirmation(brand.name);
  return <BrandDialog title={`Apagar ${brand.name}`} detail="Esta ação remove a marca e desativa os projetos vinculados. Não poderá ser desfeita." onClose={onClose} className="cadu-ds-brand-delete-dialog">
    <div className="cadu-ds-brand-delete-warning"><strong>Você está prestes a apagar:</strong><b>{brand.name}</b>{linkedProjects.length ? <><span>Projetos vinculados que também serão removidos:</span><ul>{linkedProjects.map(project => <li key={project.id}>{project.name}</li>)}</ul></> : <span>Não há projetos vinculados a esta marca.</span>}</div>
    <form className="cadu-ds-brand-form" method="post" action={urls.deleteBrand} onSubmit={event => { if (!matches) event.preventDefault(); }}>
      <Hidden name="_csrf" value={csrfToken}/><label>Digite o nome da marca para confirmar <small>maiúsculas e minúsculas não fazem diferença</small><input name="confirmation_name" value={confirmation} onChange={event => setConfirmation(event.target.value)} autoComplete="off" required/></label>
      <footer><button type="button" onClick={onClose}>Cancelar</button><button className="is-danger" disabled={!matches}>Apagar definitivamente</button></footer>
    </form>
  </BrandDialog>;
}

function BrandAssetCard({asset, brand, urls, csrfToken, canManageBrand}) {
  const label = asset.metadata?.label || assetLabels[asset.role] || asset.role || 'Ativo';
  const action = asset.role === 'logo' && asset.status === 'approved' && !asset.isPrimary ? assetUrl(urls.setPrimaryBase, asset.id) : asset.status === 'approved' && !asset.isPrimary ? assetUrl(urls.promoteLogoBase, asset.id) : '';
  return <article className="cadu-ds-brand-asset"><div className="cadu-ds-brand-asset__preview">{asset.displayUrl ? <img src={asset.displayUrl} alt={label} loading="lazy"/> : <span aria-hidden="true">◇</span>}</div><div className="cadu-ds-brand-asset__copy"><b>{label}{asset.isPrimary ? ' · principal' : ''}</b><small>{asset.metadata?.low_resolution ? 'Rascunho interno' : asset.mimeType || asset.sourceKind || 'Arquivo de marca'}</small><em className={`is-${asset.status}`}>{asset.status === 'approved' ? 'Aprovado' : asset.status === 'pending' ? 'Em revisão' : asset.status || 'Registrado'}</em></div>{canManageBrand && action && <form method="post" action={action}><Hidden name="_csrf" value={csrfToken}/><button type="submit">{asset.role === 'logo' ? 'Definir principal' : 'Usar como logo'}</button></form>}{canManageBrand && <form method="post" action={assetUrl(urls.deleteAssetBase, asset.id)}><Hidden name="_csrf" value={csrfToken}/><button type="submit" className="is-danger" aria-label={`Apagar ${label}`}>Apagar</button></form>}</article>;
}

function BrandAssetDrop({name, onFilesChange, maxFiles = 8}) {
  const input = useRef(null);
  const [active, setActive] = useState(false);
  const [files, setFiles] = useState([]);
  const assign = values => {
    const selected = Array.from(values || []).filter(file => file.type.startsWith('image/')).slice(0, maxFiles);
    if (!selected.length || !input.current) return;
    const transfer = new DataTransfer();
    selected.forEach(file => transfer.items.add(file));
    input.current.files = transfer.files;
    setFiles(selected.map(file => ({file, preview: URL.createObjectURL(file)})));
    onFilesChange?.(selected);
  };
  return <div className={`cadu-ds-brand-file-drop${active ? ' is-active' : ''}`} onDragEnter={event => { event.preventDefault(); setActive(true); }} onDragOver={event => event.preventDefault()} onDragLeave={event => { if (event.currentTarget === event.target) setActive(false); }} onDrop={event => { event.preventDefault(); setActive(false); assign(event.dataTransfer.files); }}>
    <input ref={input} name={name} type="file" accept="image/*" multiple={maxFiles > 1} hidden aria-hidden="true" tabIndex="-1"/>
    <strong>{files.length ? `${files.length} imagem${files.length === 1 ? '' : 's'} preparada${files.length === 1 ? '' : 's'}` : 'Solte as imagens aqui'}</strong>
    {files.length ? <div className="cadu-ds-brand-file-drop__thumbs">{files.map(({file, preview}) => <figure key={`${file.name}-${file.lastModified}`}><img src={preview} alt={`Prévia de ${file.name}`}/><figcaption>{file.name}</figcaption></figure>)}</div> : <small>Logo principal · horizontal · vertical · símbolo · versões claro e escuro</small>}
  </div>;
}

function AssetSection({brand, urls, csrfToken, canManageBrand}) {
  const [ready, setReady] = useState(false);
  const assets = (brand.assets || []).filter(asset => asset.displayUrl);
  const [filter, setFilter] = useState('all');
  const roles = [...new Set(assets.map(asset => asset.role))];
  const visibleAssets = filter === 'all' ? assets : assets.filter(asset => asset.role === filter);
  const [selectedId, setSelectedId] = useState(() => assets[0]?.id || '');
  const selected = visibleAssets.find(asset => asset.id === selectedId) || visibleAssets[0];
  const selectedLabel = selected ? selected.metadata?.label || assetLabels[selected.role] || selected.role || 'Ativo' : '';
  const assetDetail = asset => {
    const metadata = asset.metadata || {};
    const dimensions = metadata.width && metadata.height ? `${metadata.width} × ${metadata.height}` : metadata.dimensions;
    const size = metadata.sizeLabel || metadata.fileSizeLabel || metadata.file_size_label;
    return [asset.mimeType || asset.sourceKind || 'Imagem', dimensions, size].filter(Boolean).join(' · ');
  };
  const selectedAction = selected?.role === 'logo' && selected?.status === 'approved' && !selected?.isPrimary ? assetUrl(urls.setPrimaryBase, selected.id) : selected?.status === 'approved' && !selected?.isPrimary ? assetUrl(urls.promoteLogoBase, selected.id) : '';
  return <section className="cadu-ds-brand-section cadu-ds-brand-assets" id="biblioteca"><header><div><p>Biblioteca visual</p><h2>Ativos da marca</h2><span>Selecione uma peça para inspecionar; imagens e vídeos continuam sendo editados no Studio.</span></div><span className="cadu-ds-brand-count">{assets.length} arquivo{assets.length === 1 ? '' : 's'}</span></header>{assets.length ? <><nav className="cadu-ds-brand-library__filters" aria-label="Filtrar ativos"><button type="button" className={filter === 'all' ? 'is-active' : ''} onClick={() => setFilter('all')}>Todos</button>{roles.map(role => <button type="button" className={filter === role ? 'is-active' : ''} key={role} onClick={() => setFilter(role)}>{assetLabels[role] || role}</button>)}</nav><div className="cadu-ds-brand-library"><div className="cadu-ds-brand-library__stage">{selected && <><img src={selected.displayUrl} alt={selectedLabel}/><footer><span><b>{selectedLabel}{selected.isPrimary ? ' · principal' : ''}</b><small>{assetDetail(selected)}</small></span><div className="cadu-ds-brand-library__actions"><a href={selected.displayUrl} target="_blank" rel="noreferrer">Abrir original</a>{canManageBrand && selectedAction && <form method="post" action={selectedAction}><Hidden name="_csrf" value={csrfToken}/><button type="submit">{selected.role === 'logo' ? 'Definir principal' : 'Usar como logo'}</button></form>}{canManageBrand && !selected.isPrimary && <form method="post" action={assetUrl(urls.deleteAssetBase, selected.id)} onSubmit={event => { if (!window.confirm(`Apagar ${selectedLabel}?`)) event.preventDefault(); }}><Hidden name="_csrf" value={csrfToken}/><button type="submit" className="is-danger">Apagar</button></form>}</div></footer></>}</div><aside aria-label="Itens da biblioteca">{visibleAssets.map(asset => { const label = asset.metadata?.label || assetLabels[asset.role] || asset.role || 'Ativo'; return <button type="button" className={asset.id === selected?.id ? 'is-active' : ''} key={asset.id} onClick={() => setSelectedId(asset.id)}><img src={asset.displayUrl} alt="" loading="lazy"/><span><b>{label}{asset.isPrimary ? ' · principal' : ''}</b><small>{assetDetail(asset)}</small></span></button>; })}</aside></div></> : <p className="cadu-ds-brand-empty">Nenhum ativo utilizável ainda. Comece pelo logo ou por uma referência oficial.</p>}{canManageBrand && <details className="cadu-ds-brand-library__upload"><summary>Adicionar à biblioteca</summary><form className="cadu-ds-brand-upload" method="post" encType="multipart/form-data" action={urls.uploadAssets}><Hidden name="_csrf" value={csrfToken}/><label>Tipo<select name="role" defaultValue="reference"><option value="logo">Logo principal</option><option value="reference">Referência visual</option><option value="creative">Peça criativa</option><option value="background">Fundo</option><option value="support">Apoio visual</option><option value="icon">Ícone</option></select></label><BrandAssetDrop name="images" onFilesChange={files => setReady(files.length > 0)}/><button className="is-primary" disabled={!ready}>Enviar ativos</button></form></details>}</section>;
}

function reviewCopy(brand) {
  const status = brand.reviewPack?.status;
  const flags = brand.analysisMetadata?.qualityFlags || [];
  if (flags.length) return ['Análise com cobertura insuficiente', `Antes de aprovar, complete: ${flags.join(' · ')}.`];
  if (status === 'pending_approval') return ['Proposta pronta para decisão', 'A proposta reuniu evidências, estratégia e direção criativa. Revise antes de usá-la no trabalho.'];
  if (status === 'approved') return ['Identidade aprovada', 'Esta versão já orienta projetos e conversas vinculados à marca.'];
  if (status === 'queued' || status === 'running') { const mode = brand.reviewPack?.input?.analysis_mode === 'deep' ? 'profunda' : 'completa'; const time = mode === 'profunda' ? '6–12 minutos' : '3–8 minutos'; return ['Análise em andamento', `${brand.reviewPack?.message || 'Coleta e revisão em segundo plano.'} Estimativa total: ${time}. Você receberá um e-mail ao finalizar e o resultado aparecerá nesta página.`]; }
  if (status === 'failed') return ['Análise precisa ser repetida', brand.reviewPack?.error || 'A proposta não foi concluída.'];
  return ['Análise ainda não iniciada', brand.websiteUrl ? 'Use o site e os ativos da marca para criar uma primeira proposta de identidade.' : 'Adicione o site oficial ou uma referência visual para criar uma primeira proposta de identidade.'];
}

function AuditHistory({history}) {
  if (!history?.length) return null;
  const label = mode => mode === 'deep' ? 'Análise profunda' : 'Análise completa';
  const date = value => value ? new Intl.DateTimeFormat('pt-BR', {dateStyle: 'medium'}).format(new Date(value)) : 'Data indisponível';
  const status = value => value === 'failed' ? 'Não concluída' : value === 'queued' ? 'Na fila' : value === 'running' ? 'Em andamento' : 'Revisada';
  return <section className="cadu-ds-brand-audit-history" id="auditoria" aria-label="Auditorias realizadas"><header><div><p>Rastreabilidade</p><h2>Auditorias realizadas</h2><span>Histórico operacional de fontes, coleta, custo estimado e revisão.</span></div></header><div className="cadu-ds-brand-audit-table"><table><thead><tr><th>Data</th><th>Modalidade</th><th>Estado</th><th>Fontes</th><th>Revisões</th><th>Consumo</th><th><span className="sr-only">Detalhes</span></th></tr></thead><tbody>{history.map(item => { const collected = item.collected_data || {}; const costs = item.costs || {}; const effort = item.human_effort || {}; const tokens = Number(costs.provider_tokens || costs.estimated_tokens || 0); return <tr key={item.job_id || item.created_at}><td>{date(item.created_at)}</td><td>{label(item.analysis_mode)}</td><td><span className={`is-${item.status || 'reviewed'}`}>{status(item.status)}</span></td><td>{item.sources?.length || 0}</td><td>{item.reviews?.length || 0}</td><td>{tokens ? tokens.toLocaleString('pt-BR') : '—'}</td><td><details><summary>Ver</summary><div><dl><div><dt>Dados coletados</dt><dd>{collected.fields?.length ? collected.fields.join(' · ') : item.status === 'failed' ? 'Não concluídos' : 'Em processamento'}</dd></div><div><dt>Coerência</dt><dd>{collected.coherence === 'reviewed' ? 'Revisada por agentes' : collected.coherence === 'needs_review' ? 'Requer revisão humana' : 'Em processamento'}</dd></div><div><dt>Esforço equivalente</dt><dd>{effort.estimated_person_hours ? `${effort.estimated_person_hours} h de pesquisa e consolidação` : 'A calcular'}</dd></div></dl>{item.sources?.length ? <ul>{item.sources.slice(0, 12).map((source, index) => <li key={`${source.url}-${index}`}><a href={source.url} target="_blank" rel="noreferrer">{source.title || source.url}</a></li>)}</ul> : null}</div></details></td></tr>; })}</tbody></table></div></section>;
}

function AuditCompletionSummary({brand, audit, onDone}) {
  if (!audit) return null;
  const collected = audit.collected_data || {};
  const costs = audit.costs || {};
  const effort = audit.human_effort || {};
  const fields = Array.isArray(collected.fields) ? collected.fields.length : 0;
  const tokens = Number(costs.provider_tokens || costs.estimated_tokens || 0);
  const brl = Number(costs.actual_cost_brl || 0);
  return <section className="cadu-ds-brand-audit-complete" aria-label="Resumo da auditoria concluída">
    <div><span>Auditoria concluída</span><h2>A base inicial de {brand.name} está pronta para consulta</h2><p>A pesquisa foi organizada em uma versão rastreável. Revise os dados antes de ampliar o uso nos projetos.</p></div>
    <dl><div><dt>Tempo equivalente</dt><dd>{Number(effort.estimated_person_hours || 0) || 4} h</dd></div><div><dt>Revisões</dt><dd>{audit.reviews?.length || 0}</dd></div><div><dt>Dados estruturados</dt><dd>{fields}</dd></div><div><dt>Fontes</dt><dd>{audit.sources?.length || 0}</dd></div></dl>
    <footer><span>{tokens ? `${tokens.toLocaleString('pt-BR')} tokens processados` : 'Consumo sendo consolidado'}{brl > 0 ? ` · custo operacional aproximado de ${brl.toLocaleString('pt-BR', {style:'currency', currency:'BRL'})}` : ''}</span><button type="button" onClick={onDone}>Explorar os dados</button></footer>
  </section>;
}

function CampaignSection({campaigns, urls, csrfToken, canManageBrand}) {
  if (!campaigns.length) return null;
  const labels = {institutional: 'Institucional', social: 'Redes sociais', paid_media: 'Mídia e anúncios'};
  return <section className="cadu-ds-brand-section cadu-ds-brand-campaigns" id="campanhas"><header><div><p>Da análise para a execução</p><h2>Campanhas que viram projetos</h2><span>Escolha uma oportunidade para abrir um projeto já vinculado à marca e ao contexto aprovado.</span></div></header><div className="cadu-ds-brand-reading">{campaigns.map(campaign => <article key={campaign.id}><small>{labels[campaign.type] || 'Campanha'} · {campaign.status === 'observed' ? 'observada' : campaign.status === 'project_created' ? 'projeto criado' : 'oportunidade'}</small><b>{campaign.name}</b><span>{campaign.objective || campaign.rationale || 'Definir objetivo no projeto.'}</span>{campaign.channels?.length ? <small>{campaign.channels.join(' · ')}</small> : null}{campaign.status === 'project_created' ? <small>Já transformada em projeto.</small> : canManageBrand && <form method="post" action={campaignProjectUrl(urls.createCampaignProjectBase, campaign.id)}><Hidden name="_csrf" value={csrfToken}/><button type="submit">Transformar em projeto</button></form>}</article>)}</div></section>;
}

function CopyButton({value, label = 'Copiar'}) {
  const [done, setDone] = useState(false);
  const copy = async () => { try { await navigator.clipboard.writeText(String(value || '')); setDone(true); setTimeout(() => setDone(false), 1400); } catch (_) {} };
  return <button type="button" className="cadu-ds-brand-copy" onClick={copy}>{done ? 'Copiado' : label}</button>;
}

function BrandSignalRail({brand, fonts, colors, projects, onProject, verified}) {
  const fontUrl = family => `https://fonts.google.com/?query=${encodeURIComponent(family)}`;
  return <aside className="cadu-ds-brand-next cadu-ds-brand-signal-rail"><section className="cadu-ds-brand-signal-rail__tokens"><header><p>Sistema visual</p><h3>Cores e tipografia</h3><span className={`cadu-ds-brand-origin${verified ? ' is-verified' : ''}`}>{verified ? 'Identidade aprovada' : 'Dados ainda não verificados'}</span></header>{colors.length ? <div className="cadu-ds-brand-signal-rail__colors">{colors.slice(0, 6).map((color, index) => { const item = typeof color === 'object' ? color : {hex: color}; return item.hex ? <div key={`${item.hex}-${index}`}><i style={{background:item.hex}}/><span><b>{item.hex}</b><small>{item.role || item.name || 'Cor da marca'}</small></span><CopyButton value={item.hex} label="Copiar"/></div> : null; })}</div> : null}{fonts.length ? <div className="cadu-ds-brand-signal-rail__fonts">{fonts.slice(0, 4).map((font, index) => { const item = typeof font === 'object' ? font : {family: font}; const family = item.family || item.classification; return family ? <a key={`${family}-${index}`} href={fontUrl(family)} target="_blank" rel="noreferrer"><span><small>{item.role || 'tipografia'}</small><b>{family}</b></span><i aria-hidden="true">↗</i></a> : null; })}</div> : null}</section><section className="cadu-ds-brand-signal-rail__projects"><header><p>Projetos da marca</p><h3>{projects.length ? `${projects.length} vinculado${projects.length === 1 ? '' : 's'}` : 'Nenhum projeto vinculado'}</h3></header>{projects.length ? <nav aria-label={`Projetos que usam ${brand.name}`}>{projects.map(project => <button type="button" key={project.id} onClick={() => onProject(project)}><VisualIdentity src={project.logoUrl} initials={project.initials || project.name} label={project.name} color={project.color}/><span><b>{project.name}</b><small>{project.sources} fontes prontas</small></span><i aria-hidden="true">›</i></button>)}</nav> : <p className="cadu-ds-brand-rail-empty">Vincule a marca quando ela fizer parte do contexto de um projeto.</p>}</section></aside>;
}

const asList = value => Array.isArray(value) ? value : value ? [value] : [];

function ListBlock({title, items}) {
  const list = asList(items);
  if (!list.length) return null;
  const hidden = new Set(['source_url', 'url', 'confidence']);
  const fieldNames = {needs:'Necessidades',context:'Contexto',rationale:'Justificativa',evidence:'Evidência',excerpt:'Trecho',relationship:'Relação',market:'Mercado',barriers:'Barreiras',channels:'Canais',status:'Status',role:'Papel',usage:'Uso',family:'Família'};
  return <section className="cadu-ds-brand-data-block"><h3>{title}</h3><ul>{list.map((item, index) => {
    if (typeof item === 'string') { const parts = item.length > 240 ? item.match(/[^.!?]+[.!?]+|[^.!?]+$/g)?.map(part => part.trim()).filter(Boolean) || [item] : [item]; return <li key={`${title}-${index}`} className={parts.length > 1 ? 'is-long' : ''}>{parts.length > 1 ? <div className="cadu-ds-brand-readable-copy">{parts.map((part, partIndex) => <p key={`${title}-${index}-${partIndex}`}>{part}</p>)}</div> : <b>{item}</b>}</li>; }
    const label = item.name || item.value || item.address || item.title || item.primary || item.family || 'Dado registrado';
    const details = Object.entries(item).filter(([key, value]) => !hidden.has(key) && value != null && value !== '' && value !== label).map(([key, value]) => [fieldNames[key] || key.replaceAll('_', ' '), Array.isArray(value) ? value.join(', ') : typeof value === 'object' ? Object.values(value).filter(Boolean).join(' / ') : String(value)]);
    return <li key={`${title}-${index}`}><b>{label}</b>{details.map(([key, value]) => <small key={key}><strong>{key}:</strong> {value}</small>)}{Number.isFinite(Number(item.confidence)) && <small><strong>Confiança:</strong> {Math.round(Number(item.confidence) * 100)}%</small>}{item.source_url && <a href={item.source_url} target="_blank" rel="noreferrer">Abrir fonte</a>}</li>;
  })}</ul></section>;
}

function BrandKit({brand, profile}) {
  const publicLink = `${window.location.origin}${brand.detailUrl || ''}`;
  return <section className="cadu-ds-brand-kit" aria-label="Kit de contexto da marca"><header><div><p>Pronto para usar</p><h2>Contexto para conversas e artefatos</h2></div></header><div className="cadu-ds-brand-kit__grid"><article><small>Logo principal</small>{brand.logoUrl ? <img src={brand.logoUrl} alt={`Logo ${brand.name}`}/> : <b>Logo ainda não disponível</b>}<CopyButton value={brand.logoUrl} label="Copiar link do logo"/></article><article><small>Site oficial</small><a href={brand.websiteUrl} target="_blank" rel="noreferrer">{brand.websiteUrl || 'Não informado'}</a><CopyButton value={brand.websiteUrl} label="Copiar site"/></article><article><small>Link da marca no Workspace</small><span>{publicLink}</span><CopyButton value={publicLink} label="Copiar link"/></article><article><small>Paleta aprovada</small><div className="cadu-ds-brand-kit__colors">{(profile.colorPalette || []).slice(0, 6).map((color, index) => <button type="button" key={`${color.hex}-${index}`} title={`Copiar ${color.hex}`} onClick={() => navigator.clipboard?.writeText(color.hex)} style={{background: color.hex}}><span>{color.hex}</span></button>)}</div><small>Clique em uma cor para copiar.</small></article></div></section>;
}

function AuditAtlas({profile, metadata}) {
  const sources = metadata.sources || [];
  const socialRecords = asList(metadata.socialLinks).map(value => typeof value === 'string' ? {label: 'Canal oficial', value, source_url: value} : value);
  const records = [...asList(profile.contacts), ...asList(profile.addresses), ...asList(profile.digitalPolicies), ...socialRecords];
  return <><section className="cadu-ds-brand-atlas" id="inteligencia"><header><div><p>Base de decisão</p><h2>Marca, mercado e execução</h2><span>Todos os dados aprovados da auditoria, separados por uso e com a proveniência preservada.</span></div></header><div className="cadu-ds-brand-atlas__columns"><div><ListBlock title="Produtos e serviços" items={profile.productsServices}/><ListBlock title="Diferenciais confirmados" items={profile.differentiators}/><ListBlock title="Provas e sinais" items={profile.proofPoints}/><ListBlock title="Concorrentes e alternativas" items={profile.competitors}/><ListBlock title="Oportunidades de campanha" items={profile.campaignOpportunities}/></div><div><ListBlock title="Segmentos de audiência" items={profile.audienceSegments}/><ListBlock title="Personas e decisores" items={profile.personas}/><ListBlock title="Públicos e ângulos de anúncio" items={profile.adSegments}/><ListBlock title="Direção criativa" items={profile.creativeGuidelines}/><ListBlock title="Elementos visuais recorrentes" items={profile.visualMotifs}/><ListBlock title="Obrigatório preservar" items={profile.mandatoryElements}/><ListBlock title="Evitar" items={profile.forbiddenElements}/></div></div></section>{records.length ? <section className="cadu-ds-brand-section cadu-ds-brand-records"><header><div><p>Presença pública</p><h2>Contatos, endereços, políticas e canais</h2></div></header><div className="cadu-ds-brand-table">{records.map((record, index) => <article key={`${record.source_url || record.value}-${index}`}><div><b>{record.label || record.title || record.type || 'Registro público'}</b><span>{record.value || record.address || record.excerpt || 'Detalhe disponível na fonte'}</span></div>{record.source_url && <a href={record.source_url} target="_blank" rel="noreferrer">Fonte</a>}</article>)}</div></section> : null}<section className="cadu-ds-brand-section cadu-ds-brand-sources" id="fontes"><header><div><p>Rastreabilidade</p><h2>Fontes usadas na auditoria</h2></div></header><div className="cadu-ds-brand-table">{sources.length ? sources.map((source, index) => <article key={`${source}-${index}`}><div><b>Fonte pública {index + 1}</b><span>{source}</span></div><a href={source} target="_blank" rel="noreferrer">Abrir</a></article>) : <p className="cadu-ds-brand-empty">A auditoria ainda não registrou fontes públicas.</p>}</div></section></>;
}

function BrandDossierSections({profile}) {
  const archetype = profile.archetype && profile.archetype.primary ? [`${profile.archetype.primary}${profile.archetype.secondary ? ` / ${profile.archetype.secondary}` : ''}: ${profile.archetype.rationale || 'Leitura de personalidade da marca.'}`] : [];
  const sections = [
    ['Fundamentos', [...asList(profile.brandValues), ...archetype]],
    ['Tipografia confirmada', asList(profile.fonts)],
  ].filter(([, items]) => items.length);
  if (!sections.length) return null;
  return <section className="cadu-ds-brand-section"><header><div><p>Dossiê da marca</p><h2>Informações completas para trabalhar</h2><span>Conteúdo organizado por decisão, sem expor operações internas da auditoria.</span></div></header><div className="cadu-ds-brand-atlas__columns">{sections.map(([title, items]) => <ListBlock key={title} title={title} items={items}/>)}</div></section>;
}

export function WorkspaceBrand({bootstrap}) {
  const {isMobile} = useWorkspaceViewport();
  const brand = bootstrap.brand || {};
  const urls = bootstrap.brandLinks || {};
  const [dialog, setDialog] = useState(() => new URLSearchParams(window.location.search).get('audit') === 'start' ? 'audit' : '');
  const [accountOpen, setAccountOpen] = useState(false);
  const dockItems = bootstrap.dock?.items || [];
  const [reviewTitle, reviewDescription] = reviewCopy(brand);
  const canEdit = Boolean(bootstrap.canManageBrand);
  const profile = brand.profile || {};
  const colors = profile.colorPalette || [];
  const productPalettes = profile.productPalettes || {};
  const fonts = profile.fonts || [];
  const linkedProjects = brand.linkedProjects || [];
  const auditHistory = brand.auditHistory || [];
  const campaigns = profile.campaigns || [];
  const status = brand.reviewPack?.status || '';
  const canShowSynthesis = ['pending_approval', 'approved'].includes(status) && brand.reviewPack?.reviews?.length > 0;
  const notStarted = !status || status === 'not_started';
  const isProcessing = status === 'queued' || status === 'running';
  const completedAudit = auditHistory.find(item => ['pending_approval', 'approved'].includes(item.status));
  const completionKey = completedAudit ? `cadu-brand-audit-summary:${brand.id}:${completedAudit.job_id}` : '';
  const [showAuditCompletion, setShowAuditCompletion] = useState(() => Boolean(completedAudit && !window.localStorage.getItem(completionKey)));
  const finishAuditSummary = () => {
    if (completionKey) window.localStorage.setItem(completionKey, new Date().toISOString());
    setShowAuditCompletion(false);
    window.requestAnimationFrame(() => document.getElementById('direcao')?.scrollIntoView({behavior:'smooth', block:'start'}));
  };
  useEffect(() => {
    if (!isProcessing) return undefined;
    const refresh = window.setInterval(async () => {
      if (document.visibilityState !== 'visible' || !urls.auditStatus) return;
      try {
        const response = await fetch(urls.auditStatus, {credentials:'same-origin', headers:{Accept:'application/json'}});
        if (!response.ok) return;
        const current = await response.json();
        if (!['queued', 'running'].includes(current.status)) window.location.reload();
      } catch (_) { /* The next interval retries without interrupting the page. */ }
    }, 6000);
    return () => window.clearInterval(refresh);
  }, [isProcessing, urls.auditStatus]);
  const hasStrategicData = Boolean(profile.brandSummary || profile.positioning || profile.targetAudience || profile.toneOfVoice || profile.creativeGuidelines || colors.length || fonts.length || asList(profile.productsServices).length || asList(profile.differentiators).length);
  const lifecycle = status === 'approved' ? 'approved' : status === 'pending_approval' ? 'pending_approval' : isProcessing ? 'audit_processing' : status === 'failed' ? 'audit_failed' : hasStrategicData ? 'data_available_unverified' : 'insufficient_information';
  const showDossier = ['approved', 'pending_approval', 'data_available_unverified'].includes(lifecycle);
  const verified = lifecycle === 'approved';
  const atlasHasContent = Boolean(asList(profile.productsServices).length || asList(profile.differentiators).length || asList(profile.proofPoints).length || asList(profile.competitors).length || asList(profile.campaignOpportunities).length || asList(profile.audienceSegments).length || asList(profile.personas).length || asList(profile.adSegments).length || asList(profile.visualMotifs).length || asList(profile.mandatoryElements).length || asList(profile.forbiddenElements).length || asList(profile.contacts).length || asList(profile.addresses).length || asList(profile.digitalPolicies).length || asList(brand.analysisMetadata?.sources).length);
  const openConversation = () => window.location.assign(urls.conversation);
  const readinessScore = Number(brand.readiness?.score || 0);
  const brandNav = [
    {id:'marca-visao', label:'Visão geral', icon:'home'},
    ...(isProcessing ? [{id:'analise', label:'Análise em andamento', icon:'pulse'}] : []),
    ...(!isProcessing ? [{id:'completar', label:'Cobertura da marca', icon:'pulse'}] : []),
    ...(!isProcessing && showDossier ? [
      {id:'direcao', label:'Direção da marca', icon:'compose'},
      ...(atlasHasContent ? [{id:'inteligencia', label:'Todos os dados', icon:'pulse'}, {id:'fontes', label:'Fontes', icon:'external', count:(brand.analysisMetadata?.sources || []).length}] : []),
      ...(campaigns.length ? [{id:'campanhas', label:'Campanhas', icon:'folder', count:campaigns.length}] : []),
      ...(auditHistory.length ? [{id:'auditoria', label:'Auditorias', icon:'history', count:auditHistory.length}] : []),
    ] : []),
    {id:'biblioteca', label:'Biblioteca', icon:'file', count:(brand.assets || []).length},
  ];
  const sourceLabel = (record, index) => {
    const href = record.url || record;
    try {
      const url = new URL(href);
      const hostname = url.hostname.replace(/^www\./, '');
      const recorded = String(record.title || '').trim();
      const page = decodeURIComponent(url.pathname).split('/').filter(Boolean).at(-1)?.replace(/[-_]/g, ' ');
      if (index === 0) return 'Site oficial';
      if (recorded && !recorded.toLocaleLowerCase('pt-BR').includes(hostname.toLocaleLowerCase('pt-BR'))) return recorded;
      if (page?.toLocaleLowerCase('pt-BR') === 'about') return 'Sobre a marca';
      return page ? page.replace(/\b\w/g, letter => letter.toUpperCase()) : hostname;
    } catch (_) {
      return index === 0 ? 'Site oficial' : record.title || 'Fonte pública';
    }
  };
  const sourceDetail = href => { try { const url = new URL(href); return url.pathname && url.pathname !== '/' ? decodeURIComponent(url.pathname).replace(/\/$/, '').split('/').filter(Boolean).at(-1)?.replace(/[-_]/g, ' ') : url.hostname; } catch (_) { return href; } };
  const brandRailGroups = [
    {title:'Fontes públicas', items:[{url:brand.websiteUrl,title:'Site oficial'}, ...(brand.analysisMetadata?.sourceRecords || [])].filter(item => item.url).filter((item, index, all) => all.findIndex(other => other.url === item.url) === index).map((record, index) => ({id:record.url, title:sourceLabel(record, index), detail:sourceDetail(record.url), origin:index === 0 ? 'Site informado pela marca' : 'Fonte usada na auditoria', href:record.url, external:true, icon:'external'}))},
    {title:'Projetos da marca', items:linkedProjects.map(item => ({...item, title:item.name, detail:`${item.sources || 0} fontes prontas`}))},
  ];
  return <div className={`cadu-ds-home-shell cadu-ds-brand-shell is-${lifecycle}`}>
    <main className="cadu-ds-home-main">
      <div className="cadu-ds-home-workarea cadu-ds-brand-workarea">
        {isMobile ? <WorkspaceMobileChrome eyebrow="Marca" title={brand.name || 'Marca'} links={bootstrap.urls} contextItems={linkedProjects.map(item => ({...item, detail:'Projeto relacionado'}))}/> : <CaduDock bootstrap={bootstrap} logo={bootstrap.caduMark} homeUrl={bootstrap.urls.home} userName={bootstrap.user?.name} userAvatar={bootstrap.user?.avatar} userInitials={bootstrap.user?.name?.slice(0, 2).toUpperCase()} accountOpen={accountOpen} accountMenu={<WorkspaceAccountMenu open={accountOpen} onClose={() => setAccountOpen(false)} user={bootstrap.user} links={bootstrap.urls} projects={bootstrap.projects || []} brands={bootstrap.brands || []} usagePercent={bootstrap.usagePercent} onManageShortcuts={() => window.location.assign(`${bootstrap.urls.home}#atalhos`)}/>} onOpenAccount={() => setAccountOpen(current => !current)} brands={bootstrap.brands || []} resources={bootstrap.projects || []} shortcutItems={dockItems} usagePercent={bootstrap.usagePercent} onNewConversation={() => window.location.assign(bootstrap.urls.newConversation)} onOpenBrand={openWorkspaceDetail} onOpenResource={openWorkspaceDetail} onOpenUsage={() => setAccountOpen(true)}/>}
        <div className="cadu-ds-entity-portal cadu-ds-entity-portal--brand">
        <EntityNavigator label={brand.name || 'Marca'} items={brandNav} identity={<span><small>Marca</small><b>{brand.name}</b></span>}>
          {!isProcessing && <>
            <span>Gestão</span>
            {verified && <button type="button" className="is-primary" onClick={openConversation}>Conversar sobre a marca</button>}
            {status === 'pending_approval' && canEdit && <form method="post" action={urls.approve}><Hidden name="_csrf" value={bootstrap.csrf}/><button className="is-primary">Aprovar análise</button></form>}
            {canEdit && <button type="button" onClick={() => setDialog('identity')}>Editar dados</button>}
            {canEdit && <button type="button" onClick={() => setDialog('audit')}>{status ? 'Atualizar auditoria' : 'Preparar auditoria'}</button>}
            {canEdit && auditHistory.length > 0 && urls.reevaluate && <form method="post" action={urls.reevaluate}><Hidden name="_csrf" value={bootstrap.csrf}/><button type="submit">Reavaliar dados salvos</button></form>}
          </>}
        </EntityNavigator>
        <section className="cadu-ds-brand-content">
          <a className="cadu-ds-brand-back" href={bootstrap.urls.brands}>← Marcas</a>
          <header className="cadu-ds-brand-hero" id="marca-visao"><div className="cadu-ds-brand-hero__copy"><p>{brand.sector || 'Identidade de marca'}</p><h1>{brand.name}</h1>{!isProcessing && (profile.brandSummary || profile.positioning) && <span>{profile.brandSummary || profile.positioning}</span>}<div className="cadu-ds-brand-hero__meta"><span className={`cadu-ds-brand-status is-${lifecycle}`}>{lifecycle === 'approved' ? 'Aprovada' : lifecycle === 'pending_approval' ? 'Revisão pendente' : lifecycle === 'audit_processing' ? 'Em análise' : lifecycle === 'audit_failed' ? 'Análise não concluída' : lifecycle === 'data_available_unverified' ? 'Dados não verificados' : 'Sem auditoria'}</span>{brand.websiteUrl && <a href={brand.websiteUrl} target="_blank" rel="noreferrer">Site oficial</a>}</div></div></header>
          {!isProcessing && <BrandCompletion score={readinessScore} missing={brand.readiness?.missing || []} breakdown={brand.readiness?.breakdown || []} processing={false} onAudit={() => setDialog('audit')} onEdit={() => setDialog('identity')}/>}
          {showDossier && lifecycle !== 'data_available_unverified' && <section className={`cadu-ds-brand-review cadu-ds-brand-review--${status || 'idle'}`}><div><p>Estado da base</p><h2>{reviewTitle}</h2><span>{reviewDescription}</span>{canShowSynthesis && <button type="button" onClick={() => setDialog('reviews')}>Consultar síntese da análise</button>}</div></section>}
          {showDossier && showAuditCompletion && <AuditCompletionSummary brand={brand} audit={completedAudit} onDone={finishAuditSummary}/>}
          {!showDossier && <BrandState
            type={isProcessing ? 'processing' : lifecycle === 'audit_failed' ? 'failed' : 'new'}
            brand={brand}
            canEdit={canEdit}
            onAudit={() => setDialog('audit')}
            onIdentity={() => setDialog('identity')}
          />}
          {showDossier ? <><header className="cadu-ds-brand-data-viewer__header"><span>Base completa da marca</span><h2>Informações organizadas para consulta e gestão</h2><p>Navegue pelas seções ao lado. A página reúne somente dados disponíveis para uso, com fontes e histórico preservados.</p></header><div className="cadu-ds-brand-layout cadu-ds-brand-data-viewer">
            <div className="cadu-ds-brand-layout__main">
              <section className="cadu-ds-brand-section cadu-ds-brand-direction" id="direcao"><header><div><p>Direção da marca</p><h2>O que deve orientar cada entrega</h2><span>Uma síntese operacional do que a marca comunica, para quem e com quais diferenciais.</span></div><button type="button" onClick={openConversation}>Atualizar com o Cadu</button></header><div className="cadu-ds-brand-direction__lead"><small>Essência da marca</small><p>{profile.brandSummary || profile.positioning}</p></div><FilledReading items={[{label:'Público', value:profile.targetAudience},{label:'Oferta', value:profile.productsServices},{label:'Tom', value:profile.toneOfVoice},{label:'Diferenciais', value:profile.differentiators},{label:'Direção criativa', value:profile.creativeGuidelines}]}/></section>
              <CampaignSection campaigns={campaigns} urls={urls} csrfToken={bootstrap.csrf} canManageBrand={canEdit}/>
              {atlasHasContent && <AuditAtlas profile={profile} metadata={brand.analysisMetadata || {}}/>}
              <AuditScreenshot metadata={brand.analysisMetadata || {}}/>
              <BrandDossierSections profile={profile}/>
              <AssetSection brand={brand} urls={urls} csrfToken={bootstrap.csrf} canManageBrand={canEdit}/>
              <AuditHistory history={auditHistory}/>
            </div>
          </div></> : <><AssetSection brand={brand} urls={urls} csrfToken={bootstrap.csrf} canManageBrand={canEdit && !isProcessing}/>{!isProcessing && <AuditHistory history={auditHistory}/>}</>}
        </section>
        {!isProcessing && <EntityContextRail title="Gestão da marca" groups={showDossier ? brandRailGroups : []}><div className="cadu-ds-entity-rail__readiness"><span>Base da marca</span><strong>{readinessScore}%</strong><small>{verified ? 'identidade aprovada' : 'em preparação'}</small></div>{verified && <><a className="cadu-ds-entity-rail__studio" href={urls.createImage}>Criar imagem no Studio</a><a className="cadu-ds-entity-rail__studio" href={urls.createVideo}>Criar vídeo no Studio</a></>}<button type="button" className="cadu-ds-entity-rail__action" onClick={() => setDialog('link')}>Criar ou vincular projeto</button>{canEdit && <button type="button" className="cadu-ds-entity-rail__danger" onClick={() => setDialog('delete')}>Apagar marca</button>}</EntityContextRail>}
        </div>
      </div>
    </main>
    {dialog === 'identity' && <IdentityDialog brand={brand} urls={urls} csrfToken={bootstrap.csrf} onClose={() => setDialog('')}/>}
    {dialog === 'link' && <LinkProjectsDialog brand={brand} projects={bootstrap.availableProjects || []} csrfToken={bootstrap.csrf} onClose={() => setDialog('')}/>}
    {dialog === 'project-create' && <CreateBrandProjectDialog brand={brand} action={urls.createProject} csrfToken={bootstrap.csrf} onClose={() => setDialog('')}/>}
    {dialog === 'audit' && <AuditDialog brand={brand} urls={urls} csrfToken={bootstrap.csrf} creditAvailable={bootstrap.credit?.available} onClose={() => setDialog('')}/>}
    {dialog === 'reviews' && <ReviewDialog brand={brand} urls={urls} csrfToken={bootstrap.csrf} canEdit={canEdit} onClose={() => setDialog('')}/>}
    {dialog === 'delete' && <DeleteBrandDialog brand={brand} linkedProjects={linkedProjects} urls={urls} csrfToken={bootstrap.csrf} onClose={() => setDialog('')}/>}
  </div>;
}
