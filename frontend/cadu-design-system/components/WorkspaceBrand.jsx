import React, {useRef, useState} from 'react';
import {CaduDock} from './CaduDock';
import {WorkspaceAccountMenu} from './WorkspaceFeedback';
import {VisualIdentity} from './VisualIdentity';
import {CaduDialog} from './CaduDialog';
import {openWorkspaceDetail} from '../workspaceNavigation';
import {WorkspaceMobileChrome} from './WorkspaceMobileChrome';
import {useWorkspaceViewport} from '../hooks/useWorkspaceViewport';

const assetLabels = {logo: 'Logo', reference: 'Referência', creative: 'Peça criativa', background: 'Fundo', support: 'Apoio visual', icon: 'Ícone', cta_style: 'Estilo de CTA'};
const reviewStatus = {ready: 'Pronto para aprovação', review: 'Requer revisão'};
const assetUrl = (template, id) => String(template || '').replace('__ASSET_ID__', encodeURIComponent(id));

function Hidden({name, value}) { return <input type="hidden" name={name} value={value || ''}/>; }
const campaignProjectUrl = (template, id) => String(template || '').replace('__CAMPAIGN_ID__', encodeURIComponent(id));

function BrandState({type, brand, canEdit, onAudit, onIdentity}) {
  const processing = type === 'processing';
  return <section className={`cadu-ds-brand-state cadu-ds-brand-state--${type}`} aria-live={processing ? 'polite' : undefined}>
    <div className="cadu-ds-brand-state__visual" aria-hidden="true" />
    <div className="cadu-ds-brand-state__copy">
      <p>{processing ? 'Análise da marca' : 'Novo espaço de marca'}</p>
      <h2>{processing ? <>Estamos organizando os sinais de {brand.name}</> : 'A identidade da marca começa aqui'}</h2>
      <span>{processing ? 'O site, os links oficiais e as referências estão sendo processados. Quando houver evidências suficientes, o dossiê aparecerá nesta página.' : 'Este espaço ainda está começando. Adicione o site, uma logo ou referências para o Cadu preparar um primeiro contexto para o seu time.'}</span>
      {processing ? <small>Você pode sair desta página. O processamento continua em segundo plano e avisaremos por e-mail quando terminar.</small> : <div className="cadu-ds-brand-state__actions">{canEdit && <button type="button" className="is-primary" onClick={onAudit}>Preparar análise</button>}{canEdit && <button type="button" onClick={onIdentity}>Adicionar informações</button>}</div>}
    </div>
  </section>;
}

function FilledReading({items, emptyLabel = 'Adicione contexto para orientar as próximas decisões.'}) {
  const filled = items.filter(item => item.value);
  return filled.length ? <div className="cadu-ds-brand-reading cadu-ds-brand-reading--direction">{filled.map(item => <article key={item.label}><small>{item.label}</small><b>{item.value}</b></article>)}</div> : <div className="cadu-ds-brand-reading-empty">{emptyLabel}</div>;
}

function BrandDialog({title, detail, onClose, children, className = ''}) {
  return <CaduDialog className={`cadu-ds-brand-dialog ${className}`} label={title} onClose={onClose}>
    <header><div><h2>{title}</h2>{detail && <p>{detail}</p>}</div><button type="button" onClick={onClose} aria-label="Fechar">×</button></header>
    {children}
  </CaduDialog>;
}

function IdentityDialog({brand, urls, csrfToken, onClose}) {
  const profile = brand.profile || {};
  return <BrandDialog title="Editar identidade" detail="Atualize os sinais que devem orientar conversas, projetos e criações." onClose={onClose}>
    <form className="cadu-ds-brand-form" method="post" action={urls.updateIdentity}>
      <Hidden name="_csrf" value={csrfToken}/>
      <div className="cadu-ds-brand-form__grid"><label>Nome<input name="name" required minLength="2" maxLength="150" defaultValue={brand.name}/></label><label>Setor<input name="sector" maxLength="80" defaultValue={brand.sector}/></label></div>
      <label>Site oficial<input name="website_url" type="url" maxLength="2000" placeholder="https://" defaultValue={brand.websiteUrl}/></label>
      <div className="cadu-ds-brand-form__grid"><label>Cor principal<input name="primary_color" type="color" defaultValue={brand.primaryColor || '#176b5e'}/></label><label>Cor secundária<input name="secondary_color" type="color" defaultValue={brand.secondaryColor || '#dcece6'}/></label></div>
      <label>Essência da marca<textarea name="brand_summary" rows="3" maxLength="4000" placeholder="O que a marca resolve e por que importa agora" defaultValue={profile.brandSummary}/></label>
      <label>Posicionamento<textarea name="positioning" rows="3" maxLength="4000" placeholder="O espaço competitivo que a marca quer ocupar" defaultValue={profile.positioning}/></label>
      <label>Público e contexto<textarea name="target_audience" rows="3" maxLength="4000" defaultValue={profile.targetAudience}/></label>
      <label>Oferta prioritária <small>Um item por linha</small><textarea name="products_services" rows="4" defaultValue={(profile.productsServices || []).join('\n')}/></label>
      <label>Diferenciais verificáveis <small>Um por linha</small><textarea name="differentiators" rows="4" defaultValue={(profile.differentiators || []).join('\n')}/></label>
      <label>Provas e sinais <small>Um por linha</small><textarea name="proof_points" rows="4" defaultValue={(profile.proofPoints || []).join('\n')}/></label>
      <label>Tom e linguagem<textarea name="tone_of_voice" rows="3" maxLength="4000" defaultValue={profile.toneOfVoice}/></label>
      <label>Direção criativa<textarea name="creative_guidelines" rows="3" maxLength="4000" defaultValue={profile.creativeGuidelines}/></label>
      <label>Elementos visuais <small>Um por linha</small><textarea name="visual_motifs" rows="3" defaultValue={(profile.visualMotifs || []).join('\n')}/></label>
      <label>Elementos obrigatórios <small>Um por linha</small><textarea name="mandatory_elements" rows="3" defaultValue={(profile.mandatoryElements || []).join('\n')}/></label>
      <label>Elementos a evitar <small>Um por linha</small><textarea name="forbidden_elements" rows="3" defaultValue={(profile.forbiddenElements || []).join('\n')}/></label>
      <footer><button type="button" onClick={onClose}>Cancelar</button><button className="is-primary">Salvar identidade</button></footer>
    </form>
  </BrandDialog>;
}

function LinkProjectsDialog({brand, projects, csrfToken, onClose}) {
  return <BrandDialog title={`Vincular ${brand.name}`} detail="Escolha um projeto para manter esta identidade disponível no contexto de trabalho." onClose={onClose}>
    <div className="cadu-ds-brand-project-picker">{projects.length ? projects.map(project => <form method="post" action={project.linkUrl} key={project.id}><Hidden name="_csrf" value={csrfToken}/><input type="hidden" name="add_brand_id" value={brand.id}/><button type="submit"><span><b>{project.name}</b><small>{project.description || 'Sem contexto inicial'}</small></span><i aria-hidden="true">+</i></button></form>) : <p className="cadu-ds-brand-empty">Nenhum projeto ativo disponível.</p>}</div>
  </BrandDialog>;
}

function AuditDialog({brand, urls, csrfToken, creditAvailable = 0, onClose}) {
  const [mode, setMode] = useState('complete');
  const existingSocialLinks = brand.auditInput?.socialLinks || brand.analysisMetadata?.socialLinks || [];
  const hasDeepCredit = Number(creditAvailable || 0) > 0;
  const estimates = mode === 'deep' ? {pages: 'até 40', evidence: 'até 180', tokens: 'até 150 mil', time: '6–12 min', steps:['Coletar site, redes e ativos oficiais','Extrair identidade, público, presença e mercado em módulos','Validar OCR, visuais, políticas, concorrência e campanhas','Consolidar uma síntese final com evidências e lacunas']} : {pages: 'até 24', evidence: 'até 120', tokens: 'até 75 mil', time: '3–8 min', steps:['Coletar site, redes e ativos oficiais','Extrair identidade/oferta, público e presença em módulos','Validar visual e normalizar apenas evidências comprovadas','Consolidar uma síntese final para decisão']};
  return <BrandDialog title="Atualizar análise da marca" detail="A identidade atual permanece protegida até você revisar e aprovar uma nova versão." onClose={onClose} className="cadu-ds-brand-audit-dialog">
    <form className="cadu-ds-brand-form" method="post" encType="multipart/form-data" action={urls.audit}>
      <Hidden name="_csrf" value={csrfToken}/>
      <div className="cadu-ds-brand-audit-dialog__columns"><div>
        <label>Site oficial<input type="url" name="website_url" required maxLength="2000" placeholder="https://" defaultValue={brand.websiteUrl}/></label>
        <label>Links oficiais<textarea name="social_links" rows="3" defaultValue={existingSocialLinks.join('\n')} placeholder="https://instagram.com/sua-marca&#10;https://www.linkedin.com/company/sua-marca" /></label>
        <label>Anexos visuais<BrandAssetDrop name="images"/></label>
      </div><aside className="cadu-ds-brand-audit-dialog__scope"><strong>Profundidade da análise</strong><label><span><input type="radio" name="analysis_mode" value="complete" checked={mode === 'complete'} onChange={() => setMode('complete')}/><b>Completa</b></span><small>Identidade, oferta, público, site, redes e direção visual essencial.</small></label><label className={!hasDeepCredit ? 'is-disabled' : ''}><span><input type="radio" name="analysis_mode" value="deep" checked={mode === 'deep'} disabled={!hasDeepCredit} onChange={() => setMode('deep')}/><b>Profunda</b></span><small>{hasDeepCredit ? 'Inclui presença pública, mercado, concorrência e campanhas.' : 'Disponível quando houver saldo de créditos. Faça upgrade ou compre créditos para liberar.'}</small></label><div className="cadu-ds-brand-audit-dialog__estimate"><strong>Estimativa desta execução</strong><p>{estimates.pages} páginas · {estimates.evidence} evidências · {estimates.tokens} créditos · {estimates.time}</p></div></aside></div>
      <label className="cadu-ds-brand-check"><input type="checkbox" name="include_project_sources" value="true"/> Adicionar as páginas oficiais ao projeto vinculado após aprovação.</label>
      <label className="cadu-ds-brand-check"><input type="checkbox" name="confirmed_cost" value="true" required/> Autorizo o consumo estimado de créditos desta análise.</label>
      <footer><button type="button" onClick={onClose}>Cancelar</button><button className="is-primary">Atualizar análise {mode === 'deep' ? 'profunda' : 'completa'}</button></footer>
    </form>
  </BrandDialog>;
}

function AuditScreenshot({metadata = {}}) {
  if (!metadata.screenshot) return null;
  const colors = (metadata.screenshotColorPalette || metadata.cssColorEvidence || []).slice(0, 6);
  return <section className="cadu-ds-brand-section cadu-ds-brand-screenshot"><header><div><p>Leitura visual</p><h2>Captura renderizada da marca</h2><span>Screenshot oficial usado junto com OCR, CSS e logo para validar a identidade.</span></div></header><figure><img src={metadata.screenshot} alt="Captura renderizada do site oficial da marca" loading="lazy"/><figcaption><span>{metadata.screenshotOcr ? `OCR: ${metadata.screenshotOcr}` : 'OCR não identificou texto legível nesta captura.'}</span>{colors.length > 0 && <div aria-label="Cores extraídas da captura">{colors.map(color => <i key={color.hex} title={`${color.hex} · ${color.occurrences || color.confidence || ''}`} style={{backgroundColor: color.hex}}/> )}</div>}</figcaption></figure></section>;
}

function ReviewDialog({brand, onClose}) {
  const reviews = brand.reviewPack?.reviews || [];
  const review = reviews.find(item => item.id === 'central' || /central/i.test(item.title || '')) || reviews[reviews.length - 1];
  return <BrandDialog title={`Síntese da análise de ${brand.name}`} detail="Uma leitura consolidada para orientar a próxima decisão." onClose={onClose} className="cadu-ds-brand-review-dialog">
    <div className="cadu-ds-brand-reviews">{review ? <article><header><div><small>Decisão central</small><b>{reviewStatus[review.status] || 'Leitura disponível'}</b></div><span>{Math.round((Number(review.confidence) || 0) * 100)}% de confiança</span></header><p>{review.summary || 'A análise não retornou uma síntese utilizável.'}</p>{review.findings?.length > 0 && <div><strong>O que foi comprovado</strong><ul>{review.findings.slice(0, 6).map(item => <li key={item}>{item}</li>)}</ul></div>}{review.concerns?.length > 0 && <div className="is-concern"><strong>O que ainda precisa de revisão</strong><ul>{review.concerns.slice(0, 6).map(item => <li key={item}>{item}</li>)}</ul></div>}</article> : <p className="cadu-ds-brand-empty">Ainda não há uma síntese disponível para esta marca.</p>}</div>
    <footer><button type="button" onClick={onClose}>Fechar</button></footer>
  </BrandDialog>;
}

function DeleteBrandDialog({brand, linkedProjects, urls, csrfToken, onClose}) {
  const [confirmation, setConfirmation] = useState('');
  const matches = confirmation.trim() === String(brand.name || '').trim();
  return <BrandDialog title={`Apagar ${brand.name}`} detail="Esta ação remove a marca e desativa os projetos vinculados. Não poderá ser desfeita." onClose={onClose} className="cadu-ds-brand-delete-dialog">
    <div className="cadu-ds-brand-delete-warning"><strong>Você está prestes a apagar:</strong><b>{brand.name}</b>{linkedProjects.length ? <><span>Projetos vinculados que também serão removidos:</span><ul>{linkedProjects.map(project => <li key={project.id}>{project.name}</li>)}</ul></> : <span>Não há projetos vinculados a esta marca.</span>}</div>
    <form className="cadu-ds-brand-form" method="post" action={urls.deleteBrand} onSubmit={event => { if (!matches) event.preventDefault(); }}>
      <Hidden name="_csrf" value={csrfToken}/><label>Digite o nome da marca para confirmar<input name="confirmation_name" value={confirmation} onChange={event => setConfirmation(event.target.value)} autoComplete="off" required/></label>
      <footer><button type="button" onClick={onClose}>Cancelar</button><button className="is-danger" disabled={!matches}>Apagar definitivamente</button></footer>
    </form>
  </BrandDialog>;
}

function BrandAssetCard({asset, brand, urls, csrfToken, canManageBrand}) {
  const label = asset.metadata?.label || assetLabels[asset.role] || asset.role || 'Ativo';
  const action = asset.role === 'logo' && asset.status === 'approved' && !asset.isPrimary ? assetUrl(urls.setPrimaryBase, asset.id) : asset.status === 'approved' && !asset.isPrimary ? assetUrl(urls.promoteLogoBase, asset.id) : '';
  return <article className="cadu-ds-brand-asset"><div className="cadu-ds-brand-asset__preview">{asset.displayUrl ? <img src={asset.displayUrl} alt={label} loading="lazy"/> : <span aria-hidden="true">◇</span>}</div><div className="cadu-ds-brand-asset__copy"><b>{label}{asset.isPrimary ? ' · principal' : ''}</b><small>{asset.metadata?.low_resolution ? 'Rascunho interno' : asset.mimeType || asset.sourceKind || 'Arquivo de marca'}</small><em className={`is-${asset.status}`}>{asset.status === 'approved' ? 'Aprovado' : asset.status === 'pending' ? 'Em revisão' : asset.status || 'Registrado'}</em></div>{canManageBrand && action && <form method="post" action={action}><Hidden name="_csrf" value={csrfToken}/><button type="submit">{asset.role === 'logo' ? 'Definir principal' : 'Usar como logo'}</button></form>}{canManageBrand && <form method="post" action={assetUrl(urls.deleteAssetBase, asset.id)}><Hidden name="_csrf" value={csrfToken}/><button type="submit" className="is-danger" aria-label={`Apagar ${label}`}>Apagar</button></form>}</article>;
}

function BrandAssetDrop({name, onFilesChange}) {
  const input = useRef(null);
  const [active, setActive] = useState(false);
  const [files, setFiles] = useState([]);
  const assign = values => {
    const selected = Array.from(values || []).filter(file => file.type.startsWith('image/')).slice(0, 8);
    if (!selected.length || !input.current) return;
    const transfer = new DataTransfer();
    selected.forEach(file => transfer.items.add(file));
    input.current.files = transfer.files;
    setFiles(selected.map(file => ({file, preview: URL.createObjectURL(file)})));
    onFilesChange?.(selected);
  };
  return <div className={`cadu-ds-brand-file-drop${active ? ' is-active' : ''}`} onDragEnter={event => { event.preventDefault(); setActive(true); }} onDragOver={event => event.preventDefault()} onDragLeave={event => { if (event.currentTarget === event.target) setActive(false); }} onDrop={event => { event.preventDefault(); setActive(false); assign(event.dataTransfer.files); }}>
    <input ref={input} name={name} type="file" accept="image/*" multiple hidden aria-hidden="true" tabIndex="-1"/>
    <strong>{files.length ? `${files.length} imagem${files.length === 1 ? '' : 's'} preparada${files.length === 1 ? '' : 's'}` : 'Solte as imagens aqui'}</strong>
    {files.length ? <div className="cadu-ds-brand-file-drop__thumbs">{files.map(({file, preview}) => <figure key={`${file.name}-${file.lastModified}`}><img src={preview} alt={`Prévia de ${file.name}`}/><figcaption>{file.name}</figcaption></figure>)}</div> : <small>Logo principal · horizontal · vertical · símbolo · versões claro e escuro</small>}
  </div>;
}

function AssetSection({brand, urls, csrfToken, canManageBrand}) {
  const [ready, setReady] = useState(false);
  const assets = (brand.assets || []).filter(asset => asset.displayUrl);
  return <section className="cadu-ds-brand-section cadu-ds-brand-assets"><header><div><p>Biblioteca visual</p><h2>Ativos da marca</h2><span>Logos, referências e peças que ajudam o time a criar com consistência.</span></div><span className="cadu-ds-brand-count">{assets.length} arquivo{assets.length === 1 ? '' : 's'}</span></header>{canManageBrand && <form className="cadu-ds-brand-upload" method="post" encType="multipart/form-data" action={urls.uploadAssets}><Hidden name="_csrf" value={csrfToken}/><label>Tipo<select name="role" defaultValue="reference"><option value="logo">Logo principal</option><option value="reference">Referência visual</option><option value="creative">Peça criativa</option><option value="background">Fundo</option><option value="support">Apoio visual</option><option value="icon">Ícone</option></select></label><BrandAssetDrop name="images" onFilesChange={files => setReady(files.length > 0)}/><button className="is-primary" disabled={!ready}>Enviar ativos</button></form>}<div className="cadu-ds-brand-asset-list">{assets.length ? assets.map(asset => <BrandAssetCard asset={asset} brand={brand} urls={urls} csrfToken={csrfToken} canManageBrand={canManageBrand} key={asset.id}/>) : <p className="cadu-ds-brand-empty">Nenhum ativo utilizável ainda. Comece pelo logo ou por uma referência oficial.</p>}</div></section>;
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
  return <section className="cadu-ds-brand-audit-history" aria-label="Auditorias realizadas"><header><div><p>Rastreabilidade</p><h2>Auditorias realizadas</h2><span>Histórico operacional de fontes, coleta, custo estimado e revisão.</span></div></header><div>{history.map(item => { const collected = item.collected_data || {}; const costs = item.costs || {}; const effort = item.human_effort || {}; return <details key={item.job_id || item.created_at}><summary><span>{label(item.analysis_mode)}</span><b>{date(item.created_at)}</b><small>{item.status === 'failed' ? 'não concluída' : item.status === 'queued' ? 'na fila' : 'revisada'}</small></summary><dl><div><dt>Dados coletados</dt><dd>{collected.fields?.length ? collected.fields.join(' · ') : 'Em processamento'}</dd></div><div><dt>Coerência</dt><dd>{collected.coherence === 'reviewed' ? 'revisada por agentes' : collected.coherence === 'needs_review' ? 'requer revisão humana' : 'em processamento'}</dd></div><div><dt>Custo Cadu</dt><dd>{costs.provider_tokens || costs.estimated_tokens ? `${Number(costs.provider_tokens || costs.estimated_tokens).toLocaleString('pt-BR')} tokens` : 'estimativa pendente'}</dd></div><div><dt>Esforço equivalente</dt><dd>{effort.estimated_person_hours ? `${effort.estimated_person_hours} h de pesquisa e consolidação` : 'a calcular'}</dd></div></dl>{item.sources?.length ? <div className="cadu-ds-brand-audit-history__sources"><b>Fontes e links pesquisados</b><ul>{item.sources.slice(0, 12).map((source, index) => <li key={`${source.url}-${index}`}><a href={source.url} target="_blank" rel="noreferrer">{source.title || source.url}</a></li>)}</ul></div> : null}{item.reviews?.length ? <small>{item.reviews.length} agentes atuaram em pesquisa, extração e revisão.</small> : null}</details>; })}</div></section>;
}

function CampaignSection({campaigns, urls, csrfToken, canManageBrand}) {
  if (!campaigns.length) return null;
  const labels = {institutional: 'Institucional', social: 'Redes sociais', paid_media: 'Mídia e anúncios'};
  return <section className="cadu-ds-brand-section cadu-ds-brand-campaigns"><header><div><p>Oportunidades da auditoria</p><h2>Campanhas para desenvolver</h2><span>Cada oportunidade é independente da identidade da marca e só vira projeto por ação explícita.</span></div></header><div className="cadu-ds-brand-reading">{campaigns.map(campaign => <article key={campaign.id}><small>{labels[campaign.type] || 'Campanha'} · {campaign.status === 'observed' ? 'observada' : campaign.status === 'project_created' ? 'projeto criado' : 'sugestão 2026'}</small><b>{campaign.name}</b><span>{campaign.objective || campaign.rationale || 'Definir objetivo no projeto.'}</span>{campaign.channels?.length ? <small>{campaign.channels.join(' · ')}</small> : null}{campaign.status === 'project_created' ? <small>Já transformada em projeto.</small> : canManageBrand && <form method="post" action={campaignProjectUrl(urls.createCampaignProjectBase, campaign.id)}><Hidden name="_csrf" value={csrfToken}/><button type="submit">Criar projeto desta campanha</button></form>}</article>)}</div></section>;
}

function CopyButton({value, label = 'Copiar'}) {
  const [done, setDone] = useState(false);
  const copy = async () => { try { await navigator.clipboard.writeText(String(value || '')); setDone(true); setTimeout(() => setDone(false), 1400); } catch (_) {} };
  return <button type="button" className="cadu-ds-brand-copy" onClick={copy}>{done ? 'Copiado' : label}</button>;
}

function BrandSignalRail({brand, profile, fonts, colors, canEdit, onAudit, notStarted, projects, onProject}) {
  const fontUrl = family => `https://fonts.google.com/?query=${encodeURIComponent(family)}`;
  const missing = brand.readiness?.missing || [];
  return <aside className="cadu-ds-brand-next cadu-ds-brand-signal-rail"><p>Prontidão da identidade</p><b className="cadu-ds-brand-signal-rail__score">{brand.readiness?.score || 0}%</b><h2>{missing.length ? 'Fortaleça a base antes da próxima entrega' : 'Base pronta para orientar entregas'}</h2>{missing.length ? <ul>{missing.map(item => <li key={item}>{item}</li>)}</ul> : <span>Projetos, conversas, Planner e Studio já recebem este contexto.</span>}{notStarted && canEdit && <button type="button" onClick={onAudit}>Preparar análise</button>}<section className="cadu-ds-brand-signal-rail__projects"><header><p>Projetos da marca</p><h3>{projects.length ? `${projects.length} em contexto` : 'Nenhum projeto vinculado'}</h3></header>{projects.length ? <nav aria-label={`Projetos que usam ${brand.name}`}>{projects.map(project => <button type="button" key={project.id} onClick={() => onProject(project)}><VisualIdentity src={project.logoUrl} initials={project.initials || project.name} label={project.name} color={project.color}/><span><b>{project.name}</b><small>{project.sources} fontes prontas</small></span><i aria-hidden="true">›</i></button>)}</nav> : <p className="cadu-ds-brand-rail-empty">Vincule esta marca a um projeto para navegar entre contexto e entrega.</p>}</section><section className="cadu-ds-brand-signal-rail__tokens"><header><p>Sistema de sinais</p><h3>Cores e tipografia</h3></header>{colors.length ? <div className="cadu-ds-brand-signal-rail__colors">{colors.slice(0, 6).map((color, index) => { const item = typeof color === 'object' ? color : {hex: color}; return <div key={`${item.hex}-${index}`}><i style={{background: item.hex || '#dcece6'}}/><span><b>{item.hex || '—'}</b><small>{item.role || item.name || 'Cor da marca'}</small></span><CopyButton value={item.hex} label="Copiar"/></div>; })}</div> : <p className="cadu-ds-brand-empty">A paleta aparece após a leitura da logo ou a definição manual.</p>}{fonts.length ? <div className="cadu-ds-brand-signal-rail__fonts">{fonts.slice(0, 4).map((font, index) => { const item = typeof font === 'object' ? font : {family: font}; const family = item.family || item.classification; return family ? <a key={`${family}-${index}`} href={fontUrl(family)} target="_blank" rel="noreferrer"><span><small>{item.role || 'tipografia'}</small><b>{family}</b></span><i aria-hidden="true">↗</i></a> : null; })}</div> : <p className="cadu-ds-brand-empty">As famílias aprovadas aparecerão aqui.</p>}<small className="cadu-ds-brand-signal-rail__note">Google Fonts é uma consulta: confirme disponibilidade e licença antes do uso.</small></section></aside>;
}

const asList = value => Array.isArray(value) ? value : value ? [value] : [];

function ListBlock({title, items}) {
  const list = asList(items);
  if (!list.length) return null;
  return <section className="cadu-ds-brand-data-block"><h3>{title}</h3><ul>{list.map((item, index) => <li key={`${title}-${index}`}>{typeof item === 'string' ? item : item.name || item.value || item.address || item.title}</li>)}</ul></section>;
}

function BrandKit({brand, profile}) {
  const publicLink = `${window.location.origin}${brand.detailUrl || ''}`;
  return <section className="cadu-ds-brand-kit" aria-label="Kit de contexto da marca"><header><div><p>Pronto para usar</p><h2>Contexto para conversas e artefatos</h2></div></header><div className="cadu-ds-brand-kit__grid"><article><small>Logo principal</small>{brand.logoUrl ? <img src={brand.logoUrl} alt={`Logo ${brand.name}`}/> : <b>Logo ainda não disponível</b>}<CopyButton value={brand.logoUrl} label="Copiar link do logo"/></article><article><small>Site oficial</small><a href={brand.websiteUrl} target="_blank" rel="noreferrer">{brand.websiteUrl || 'Não informado'}</a><CopyButton value={brand.websiteUrl} label="Copiar site"/></article><article><small>Link da marca no Workspace</small><span>{publicLink}</span><CopyButton value={publicLink} label="Copiar link"/></article><article><small>Paleta aprovada</small><div className="cadu-ds-brand-kit__colors">{(profile.colorPalette || []).slice(0, 6).map((color, index) => <button type="button" key={`${color.hex}-${index}`} title={`Copiar ${color.hex}`} onClick={() => navigator.clipboard?.writeText(color.hex)} style={{background: color.hex}}><span>{color.hex}</span></button>)}</div><small>Clique em uma cor para copiar.</small></article></div></section>;
}

function AuditAtlas({profile, metadata}) {
  const sources = metadata.sources || [];
  const socialRecords = asList(metadata.socialLinks).map(value => typeof value === 'string' ? {label: 'Canal oficial', value, source_url: value} : value);
  const records = [...asList(profile.contacts), ...asList(profile.addresses), ...asList(profile.digitalPolicies), ...socialRecords];
  return <><section className="cadu-ds-brand-atlas"><header><div><p>Base de decisão</p><h2>Marca, mercado e execução</h2><span>Todos os dados aprovados da auditoria, separados por uso e com a proveniência preservada.</span></div></header><div className="cadu-ds-brand-atlas__columns"><div><ListBlock title="Produtos e serviços" items={profile.productsServices}/><ListBlock title="Diferenciais confirmados" items={profile.differentiators}/><ListBlock title="Provas e sinais" items={profile.proofPoints}/><ListBlock title="Concorrentes e alternativas" items={profile.competitors}/><ListBlock title="Oportunidades de campanha" items={profile.campaignOpportunities}/></div><div><ListBlock title="Segmentos de audiência" items={profile.audienceSegments}/><ListBlock title="Personas e decisores" items={profile.personas}/><ListBlock title="Públicos e ângulos de anúncio" items={profile.adSegments}/><ListBlock title="Direção criativa" items={profile.creativeGuidelines}/><ListBlock title="Elementos visuais recorrentes" items={profile.visualMotifs}/><ListBlock title="Obrigatório preservar" items={profile.mandatoryElements}/><ListBlock title="Evitar" items={profile.forbiddenElements}/></div></div></section>{records.length ? <section className="cadu-ds-brand-section cadu-ds-brand-records"><header><div><p>Presença pública</p><h2>Contatos, endereços, políticas e canais</h2></div></header><div className="cadu-ds-brand-table">{records.map((record, index) => <article key={`${record.source_url || record.value}-${index}`}><div><b>{record.label || record.title || record.type || 'Registro público'}</b><span>{record.value || record.address || record.excerpt || 'Detalhe disponível na fonte'}</span></div>{record.source_url && <a href={record.source_url} target="_blank" rel="noreferrer">Fonte</a>}</article>)}</div></section> : null}<section className="cadu-ds-brand-section cadu-ds-brand-sources"><header><div><p>Rastreabilidade</p><h2>Fontes usadas na auditoria</h2></div></header><div className="cadu-ds-brand-table">{sources.length ? sources.map((source, index) => <article key={`${source}-${index}`}><div><b>Fonte pública {index + 1}</b><span>{source}</span></div><a href={source} target="_blank" rel="noreferrer">Abrir</a></article>) : <p className="cadu-ds-brand-empty">A auditoria ainda não registrou fontes públicas.</p>}</div></section></>;
}

export function WorkspaceBrand({bootstrap}) {
  const {isMobile} = useWorkspaceViewport();
  const brand = bootstrap.brand || {};
  const urls = bootstrap.brandLinks || {};
  const [dialog, setDialog] = useState(() => new URLSearchParams(window.location.search).get('audit') === 'start' ? 'audit' : '');
  const [accountOpen, setAccountOpen] = useState(false);
  const dockItems = bootstrap.dock?.items?.length ? bootstrap.dock.items : [...(bootstrap.brands || []), ...(bootstrap.projects || [])];
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
  const hasBrandSubstance = Boolean(brand.websiteUrl || brand.logoUrl || profile.brandSummary || profile.positioning || profile.targetAudience || colors.length || fonts.length || linkedProjects.length || brand.analysisMetadata?.pagesAnalyzed || brand.assets?.length || auditHistory.length);
  const isNewBrand = notStarted && !hasBrandSubstance;
  const openConversation = () => window.location.assign(urls.conversation);
  const projectDetail = project => openWorkspaceDetail({href: project.href});
  return <div className={`cadu-ds-home-shell cadu-ds-brand-shell${isProcessing ? ' is-processing' : ''}${isNewBrand ? ' is-new-brand' : ''}`}>
    <main className="cadu-ds-home-main">
      <div className="cadu-ds-home-workarea cadu-ds-brand-workarea">
        {isMobile ? <WorkspaceMobileChrome eyebrow="Marca" title={brand.name || 'Marca'} links={bootstrap.urls} contextItems={linkedProjects.map(item => ({...item, detail:'Projeto relacionado'}))}/> : <CaduDock bootstrap={bootstrap} logo={bootstrap.caduMark} homeUrl={bootstrap.urls.home} userName={bootstrap.user?.name} userAvatar={bootstrap.user?.avatar} userInitials={bootstrap.user?.name?.slice(0, 2).toUpperCase()} accountOpen={accountOpen} accountMenu={<WorkspaceAccountMenu open={accountOpen} onClose={() => setAccountOpen(false)} user={bootstrap.user} links={bootstrap.urls} projects={bootstrap.projects || []} brands={bootstrap.brands || []} usagePercent={bootstrap.usagePercent} onManageShortcuts={() => window.location.assign(`${bootstrap.urls.home}#atalhos`)}/>} onOpenAccount={() => setAccountOpen(current => !current)} brands={bootstrap.brands || []} resources={bootstrap.projects || []} shortcutItems={dockItems} usagePercent={bootstrap.usagePercent} onNewConversation={() => window.location.assign(bootstrap.urls.newConversation)} onOpenBrand={openWorkspaceDetail} onOpenResource={openWorkspaceDetail} onOpenUsage={() => setAccountOpen(true)}/>}
        <section className="cadu-ds-brand-content">
          <a className="cadu-ds-brand-back" href={bootstrap.urls.brands}>← Marcas</a>
          <header className="cadu-ds-brand-hero"><div className="cadu-ds-brand-hero__identity"><VisualIdentity src={brand.logoUrl} initials={brand.initials || brand.name} label={brand.name} color={brand.primaryColor} imageTreatment="brand"/></div><div className="cadu-ds-brand-hero__copy"><p>{brand.sector || 'Identidade de marca'}</p><h1>{brand.name}</h1>{(profile.brandSummary || profile.positioning) && <span>{profile.brandSummary || profile.positioning}</span>}<div className="cadu-ds-brand-hero__meta"><b>{brand.readiness?.score || 0}%</b><small>prontidão</small>{brand.websiteUrl && <a href={brand.websiteUrl} target="_blank" rel="noreferrer">Site oficial</a>}</div></div><div className="cadu-ds-brand-hero__actions"><button type="button" className="is-primary" onClick={openConversation}>Conversar sobre a marca</button>{canEdit && <button type="button" onClick={() => setDialog('identity')}>Editar identidade</button>}<details><summary>Mais ações</summary><div><button type="button" onClick={() => setDialog('link')}>Vincular projeto</button><a href={urls.createImage}>Criar imagem</a><a href={urls.createVideo}>Criar vídeo</a><a href={urls.createPlan}>Criar plano</a><a href={urls.system}>Sistema avançado</a>{canEdit && <button type="button" className="is-danger" onClick={() => setDialog('delete')}>Apagar marca</button>}</div></details></div></header>
          <section className={`cadu-ds-brand-review cadu-ds-brand-review--${status || 'idle'}`}><div><p>Próximo passo</p><h2>{reviewTitle}</h2><span>{reviewDescription}</span>{status === 'queued' || status === 'running' ? <small>Você pode sair desta página: o processamento continua no backend. Ao finalizar, enviaremos um e-mail e atualizaremos este dossiê com fontes, custos e decisão.</small> : null}</div><div>{canShowSynthesis && <button type="button" onClick={() => setDialog('reviews')}>Ver síntese da análise</button>}{status === 'pending_approval' && canEdit && <form method="post" action={urls.approve}><Hidden name="_csrf" value={bootstrap.csrf}/><button className="is-primary">Aprovar síntese</button></form>}{status === 'failed' && canEdit && <form method="post" action={urls.retry}><Hidden name="_csrf" value={bootstrap.csrf}/><button>Tentar novamente</button></form>}{notStarted && canEdit && <button className="is-primary" type="button" onClick={() => setDialog('audit')}>Iniciar análise</button>}</div></section>
          {(isProcessing || isNewBrand) && <BrandState type={isProcessing ? 'processing' : 'new'} brand={brand} canEdit={canEdit} onAudit={() => setDialog('audit')} onIdentity={() => setDialog('identity')}/>}
          <div className="cadu-ds-brand-layout">
            <div className="cadu-ds-brand-layout__main">
              <section className="cadu-ds-brand-section cadu-ds-brand-direction"><header><div><p>Direção de trabalho</p><h2>O que deve guiar cada entrega</h2><span>Uma síntese operacional do que a marca precisa comunicar, para quem e com quais provas.</span></div>{canEdit && <button type="button" onClick={() => setDialog('identity')}>Editar direção</button>}</header><div className="cadu-ds-brand-direction__lead"><small>Essência da marca</small><p>{profile.brandSummary || profile.positioning || 'Adicione uma orientação para dar direção às próximas entregas.'}</p></div><FilledReading items={[{label:'Posicionamento', value:profile.positioning},{label:'Público e contexto', value:profile.targetAudience},{label:'Oferta prioritária', value:asList(profile.productsServices).join(' · ')},{label:'Tom e linguagem', value:profile.toneOfVoice},{label:'Diferenciais', value:asList(profile.differentiators).join(' · ')},{label:'Direção criativa', value:profile.creativeGuidelines}]}/></section>
              <BrandKit brand={brand} profile={profile}/>
              <AuditAtlas profile={profile} metadata={brand.analysisMetadata || {}}/>
              <AuditScreenshot metadata={brand.analysisMetadata || {}}/>
              <CampaignSection campaigns={campaigns} urls={urls} csrfToken={bootstrap.csrf} canManageBrand={canEdit}/>
              <AssetSection brand={brand} urls={urls} csrfToken={bootstrap.csrf} canManageBrand={canEdit}/>
              <div className="cadu-ds-brand-lower-grid"><section className="cadu-ds-brand-section"><header><div><p>Contexto compartilhado</p><h2>Projetos que usam esta marca</h2></div><button type="button" onClick={() => setDialog('link')}>Vincular</button></header><div className="cadu-ds-brand-project-list">{linkedProjects.length ? linkedProjects.map(project => <button type="button" key={project.id} onClick={() => projectDetail(project)}><VisualIdentity src={project.logoUrl} initials={project.initials || project.name} label={project.name} color={project.color}/><span><b>{project.name}</b><small>{project.sources} fontes prontas</small></span><i>›</i></button>) : <p className="cadu-ds-brand-empty">Esta marca ainda não está vinculada a um projeto.</p>}</div></section><section className="cadu-ds-brand-section"><header><div><p>Auditoria</p><h2>Evidências reunidas</h2></div>{canEdit && <button type="button" onClick={() => setDialog('audit')}>{brand.analysisMetadata?.pagesAnalyzed ? 'Reanalisar' : 'Analisar'}</button>}</header><div className="cadu-ds-brand-evidence"><div><b>{brand.analysisMetadata?.pagesAnalyzed || 0}</b><span>páginas</span></div><div><b>{brand.analysisMetadata?.assetsFound || 0}</b><span>ativos encontrados</span></div><div><b>{brand.analysisMetadata?.visualEvidenceCount || 0}</b><span>evidências visuais</span></div></div>{brand.analysisMetadata?.sources?.length > 0 && <details><summary>Fontes consultadas</summary><ul>{brand.analysisMetadata.sources.map(source => <li key={source}><a href={source} target="_blank" rel="noreferrer">{source}</a></li>)}</ul></details>}</section></div>
              <AuditHistory history={auditHistory}/>
            </div>
            <BrandSignalRail brand={brand} profile={profile} fonts={fonts} colors={colors} canEdit={canEdit} onAudit={() => setDialog('audit')} notStarted={notStarted} projects={linkedProjects} onProject={projectDetail}/>
          </div>
        </section>
      </div>
    </main>
    {dialog === 'identity' && <IdentityDialog brand={brand} urls={urls} csrfToken={bootstrap.csrf} onClose={() => setDialog('')}/>} {dialog === 'link' && <LinkProjectsDialog brand={brand} projects={bootstrap.availableProjects || []} csrfToken={bootstrap.csrf} onClose={() => setDialog('')}/>} {dialog === 'audit' && <AuditDialog brand={brand} urls={urls} csrfToken={bootstrap.csrf} creditAvailable={bootstrap.credit?.available} onClose={() => setDialog('')}/>} {dialog === 'reviews' && <ReviewDialog brand={brand} onClose={() => setDialog('')}/>} {dialog === 'delete' && <DeleteBrandDialog brand={brand} linkedProjects={linkedProjects} urls={urls} csrfToken={bootstrap.csrf} onClose={() => setDialog('')}/>}
  </div>;
}
