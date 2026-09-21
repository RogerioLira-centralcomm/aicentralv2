import React, {useState} from 'react';
import {CaduDock} from './CaduDock';
import {WorkspaceAccountMenu} from './WorkspaceFeedback';
import {VisualIdentity} from './VisualIdentity';
import {CaduDialog} from './CaduDialog';
import {openWorkspaceDetail} from '../workspaceNavigation';

const assetLabels = {logo: 'Logo', reference: 'Referência', creative: 'Peça criativa', background: 'Fundo', support: 'Apoio visual', icon: 'Ícone', cta_style: 'Estilo de CTA'};
const reviewStatus = {ready: 'Pronto para aprovação', review: 'Requer revisão'};
const assetUrl = (template, id) => String(template || '').replace('__ASSET_ID__', encodeURIComponent(id));

function Hidden({name, value}) { return <input type="hidden" name={name} value={value || ''}/>; }

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
      <label>Tom de voz<textarea name="tone_of_voice" rows="3" maxLength="4000" defaultValue={profile.toneOfVoice}/></label>
      <label>Público prioritário<textarea name="target_audience" rows="3" maxLength="4000" defaultValue={profile.targetAudience}/></label>
      <label>Posicionamento<textarea name="positioning" rows="3" maxLength="4000" defaultValue={profile.positioning}/></label>
      <label>Valores <small>Um por linha</small><textarea name="brand_values" rows="4" defaultValue={(profile.brandValues || []).join('\n')}/></label>
      <footer><button type="button" onClick={onClose}>Cancelar</button><button className="is-primary">Salvar identidade</button></footer>
    </form>
  </BrandDialog>;
}

function LinkProjectsDialog({brand, projects, csrfToken, onClose}) {
  return <BrandDialog title={`Vincular ${brand.name}`} detail="Escolha um projeto para manter esta identidade disponível no contexto de trabalho." onClose={onClose}>
    <div className="cadu-ds-brand-project-picker">{projects.length ? projects.map(project => <form method="post" action={project.linkUrl} key={project.id}><Hidden name="_csrf" value={csrfToken}/><input type="hidden" name="add_brand_id" value={brand.id}/><button type="submit"><span><b>{project.name}</b><small>{project.description || 'Sem contexto inicial'}</small></span><i aria-hidden="true">+</i></button></form>) : <p className="cadu-ds-brand-empty">Nenhum projeto ativo disponível.</p>}</div>
  </BrandDialog>;
}

function AuditDialog({brand, urls, csrfToken, onClose}) {
  return <BrandDialog title="Analisar marca" detail="O Cadu organiza evidências oficiais e prepara uma proposta para revisão humana." onClose={onClose}>
    <form className="cadu-ds-brand-form" method="post" encType="multipart/form-data" action={urls.audit}>
      <Hidden name="_csrf" value={csrfToken}/>
      <label>Site oficial<input type="url" name="website_url" required maxLength="2000" placeholder="https://" defaultValue={brand.websiteUrl}/></label>
      <label>Referências opcionais<input type="file" name="images" accept="image/*" multiple/><small>Até quatro imagens oficiais da marca.</small></label>
      <label className="cadu-ds-brand-check"><input type="checkbox" name="include_project_sources" value="true"/> Adicionar páginas oficiais ao projeto vinculado após aprovação.</label>
      <footer><button type="button" onClick={onClose}>Cancelar</button><button className="is-primary">Iniciar análise</button></footer>
    </form>
  </BrandDialog>;
}

function ReviewDialog({brand, onClose}) {
  const reviews = brand.reviewPack?.reviews || [];
  return <BrandDialog title={`Pareceres de ${brand.name}`} detail="Compare as leituras antes de aprovar qualquer atualização na identidade." onClose={onClose} className="cadu-ds-brand-review-dialog">
    <div className="cadu-ds-brand-reviews">{reviews.length ? reviews.map((review, index) => <article key={`${review.title || 'review'}-${index}`}><header><div><small>{review.title || 'Parecer'}</small><b>{reviewStatus[review.status] || 'Leitura disponível'}</b></div><span>{Math.round((Number(review.confidence) || 0) * 100)}% de confiança</span></header><p>{review.summary || 'O parecer não retornou um resumo utilizável.'}</p>{review.findings?.length > 0 && <div><strong>Conclusões</strong><ul>{review.findings.map(item => <li key={item}>{item}</li>)}</ul></div>}{review.concerns?.length > 0 && <div className="is-concern"><strong>Verificar antes de aprovar</strong><ul>{review.concerns.map(item => <li key={item}>{item}</li>)}</ul></div>}</article>) : <p className="cadu-ds-brand-empty">Ainda não há pareceres para esta marca.</p>}</div>
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
  return <article className="cadu-ds-brand-asset"><div className="cadu-ds-brand-asset__preview">{asset.displayUrl ? <img src={asset.displayUrl} alt={label} loading="lazy"/> : <span aria-hidden="true">◇</span>}</div><div className="cadu-ds-brand-asset__copy"><b>{label}{asset.isPrimary ? ' · principal' : ''}</b><small>{asset.metadata?.low_resolution ? 'Rascunho interno' : asset.mimeType || asset.sourceKind || 'Arquivo de marca'}</small><em className={`is-${asset.status}`}>{asset.status === 'approved' ? 'Aprovado' : asset.status === 'pending' ? 'Em revisão' : asset.status || 'Registrado'}</em></div>{canManageBrand && action && <form method="post" action={action}><Hidden name="_csrf" value={csrfToken}/><button type="submit">{asset.role === 'logo' ? 'Definir principal' : 'Usar como logo'}</button></form>}{canManageBrand && <form method="post" action={assetUrl(urls.deleteAssetBase, asset.id)} onSubmit={event => { if (!window.confirm('Apagar este ativo?')) event.preventDefault(); }}><Hidden name="_csrf" value={csrfToken}/><button type="submit" className="is-danger" aria-label={`Apagar ${label}`}>Apagar</button></form>}</article>;
}

function AssetSection({brand, urls, csrfToken, canManageBrand}) {
  return <section className="cadu-ds-brand-section cadu-ds-brand-assets"><header><div><p>Biblioteca visual</p><h2>Ativos da marca</h2><span>Logos, referências e peças que ajudam o time a criar com consistência.</span></div><span className="cadu-ds-brand-count">{brand.assets.length} arquivo{brand.assets.length === 1 ? '' : 's'}</span></header>{canManageBrand && <form className="cadu-ds-brand-upload" method="post" encType="multipart/form-data" action={urls.uploadAssets}><Hidden name="_csrf" value={csrfToken}/><label>Tipo<select name="role" defaultValue="reference"><option value="logo">Logo principal</option><option value="reference">Referência visual</option><option value="creative">Peça criativa</option><option value="background">Fundo</option><option value="support">Apoio visual</option><option value="icon">Ícone</option></select></label><label className="cadu-ds-brand-upload__files">Adicionar arquivos<input type="file" name="images" accept="image/*" multiple required/></label><button className="is-primary">Enviar ativos</button></form>}<div className="cadu-ds-brand-asset-list">{brand.assets.length ? brand.assets.map(asset => <BrandAssetCard asset={asset} brand={brand} urls={urls} csrfToken={csrfToken} canManageBrand={canManageBrand} key={asset.id}/>) : <p className="cadu-ds-brand-empty">Nenhum ativo registrado. Comece pelo logo ou por uma referência oficial.</p>}</div></section>;
}

function reviewCopy(brand) {
  const status = brand.reviewPack?.status;
  if (status === 'pending_approval') return ['Proposta pronta para decisão', 'A proposta reuniu evidências, estratégia e direção criativa. Revise antes de usá-la no trabalho.'];
  if (status === 'approved') return ['Identidade aprovada', 'Esta versão já orienta projetos e conversas vinculados à marca.'];
  if (status === 'queued' || status === 'running') return ['Análise em andamento', brand.reviewPack?.message || 'A proposta está sendo preparada em segundo plano.'];
  if (status === 'failed') return ['Análise precisa ser repetida', brand.reviewPack?.error || 'A proposta não foi concluída.'];
  return ['Análise ainda não iniciada', brand.websiteUrl ? 'Use o site e os ativos da marca para criar uma primeira proposta de identidade.' : 'Adicione o site oficial ou uma referência visual para criar uma primeira proposta de identidade.'];
}

export function WorkspaceBrand({bootstrap}) {
  const brand = bootstrap.brand || {};
  const urls = bootstrap.brandLinks || {};
  const [dialog, setDialog] = useState(() => new URLSearchParams(window.location.search).get('audit') === 'start' ? 'audit' : '');
  const [accountOpen, setAccountOpen] = useState(false);
  const dockItems = bootstrap.dock?.items?.length ? bootstrap.dock.items : [...(bootstrap.brands || []), ...(bootstrap.projects || [])];
  const [reviewTitle, reviewDescription] = reviewCopy(brand);
  const canEdit = Boolean(bootstrap.canManageBrand);
  const profile = brand.profile || {};
  const colors = profile.colorPalette || [];
  const fonts = profile.fonts || [];
  const linkedProjects = brand.linkedProjects || [];
  const status = brand.reviewPack?.status || '';
  const notStarted = !status || status === 'not_started';
  const openConversation = () => window.location.assign(urls.conversation);
  const projectDetail = project => openWorkspaceDetail({href: project.href});
  return <div className="cadu-ds-home-shell cadu-ds-brand-shell">
    <main className="cadu-ds-home-main">
      <div className="cadu-ds-home-workarea cadu-ds-brand-workarea">
        <CaduDock bootstrap={bootstrap} logo={bootstrap.caduMark} homeUrl={bootstrap.urls.home} userName={bootstrap.user?.name} userAvatar={bootstrap.user?.avatar} userInitials={bootstrap.user?.name?.slice(0, 2).toUpperCase()} accountOpen={accountOpen} accountMenu={<WorkspaceAccountMenu open={accountOpen} onClose={() => setAccountOpen(false)} user={bootstrap.user} links={bootstrap.urls} projects={bootstrap.projects || []} brands={bootstrap.brands || []} usagePercent={bootstrap.usagePercent} onManageShortcuts={() => window.location.assign(`${bootstrap.urls.home}#atalhos`)}/>} onOpenAccount={() => setAccountOpen(current => !current)} brands={bootstrap.brands || []} resources={bootstrap.projects || []} shortcutItems={dockItems} usagePercent={bootstrap.usagePercent} onNewConversation={() => window.location.assign(bootstrap.urls.newConversation)} onOpenBrand={openWorkspaceDetail} onOpenResource={openWorkspaceDetail} onOpenUsage={() => setAccountOpen(true)}/>
        <section className="cadu-ds-brand-content">
          <a className="cadu-ds-brand-back" href={bootstrap.urls.brands}>← Marcas</a>
          <header className="cadu-ds-brand-hero"><div className="cadu-ds-brand-hero__identity"><VisualIdentity src={brand.logoUrl} initials={brand.initials || brand.name} label={brand.name} color={brand.primaryColor}/></div><div className="cadu-ds-brand-hero__copy"><p>{brand.sector || 'Identidade de marca'}</p><h1>{brand.name}</h1><span>{profile.brandSummary || profile.positioning || 'Uma identidade para orientar projetos, conversas e criações.'}</span><div className="cadu-ds-brand-hero__meta"><b>{brand.readiness?.score || 0}%</b><small>prontidão</small>{brand.websiteUrl && <a href={brand.websiteUrl} target="_blank" rel="noreferrer">Site oficial</a>}</div></div><div className="cadu-ds-brand-hero__actions"><button type="button" className="is-primary" onClick={openConversation}>Conversar sobre a marca</button>{canEdit && <button type="button" onClick={() => setDialog('identity')}>Editar identidade</button>}{canEdit && status === 'approved' && <form method="post" action={urls.generateHero}><Hidden name="_csrf" value={bootstrap.csrf}/><button type="submit">Criar hero</button></form>}<details><summary>Mais ações</summary><div><button type="button" onClick={() => setDialog('link')}>Vincular projeto</button><a href={urls.createImage}>Criar imagem</a><a href={urls.createVideo}>Criar vídeo</a><a href={urls.createPlan}>Criar plano</a><a href={urls.system}>Sistema avançado</a>{canEdit && <button type="button" className="is-danger" onClick={() => setDialog('delete')}>Apagar marca</button>}</div></details></div></header>
          <section className={`cadu-ds-brand-review cadu-ds-brand-review--${status || 'idle'}`}><div><p>Próximo passo</p><h2>{reviewTitle}</h2><span>{reviewDescription}</span>{status === 'queued' || status === 'running' ? <small>O processamento continua mesmo se você sair desta página.</small> : null}</div><div>{brand.reviewPack?.reviews?.length > 0 && <button type="button" onClick={() => setDialog('reviews')}>Ver {brand.reviewPack.reviews.length} pareceres</button>}{status === 'pending_approval' && canEdit && <form method="post" action={urls.approve}><Hidden name="_csrf" value={bootstrap.csrf}/><button className="is-primary">Aprovar síntese</button></form>}{status === 'failed' && canEdit && <form method="post" action={urls.retry}><Hidden name="_csrf" value={bootstrap.csrf}/><button>Tentar novamente</button></form>}{notStarted && canEdit && <button className="is-primary" type="button" onClick={() => setDialog('audit')}>Iniciar análise</button>}</div></section>
          <div className="cadu-ds-brand-grid"><section className="cadu-ds-brand-section"><header><div><p>Essência da marca</p><h2>Direção para o trabalho</h2></div>{canEdit && <button type="button" onClick={() => setDialog('identity')}>Editar</button>}</header><div className="cadu-ds-brand-reading"><article><small>Tom de voz</small><b>{profile.toneOfVoice || 'A definir'}</b></article><article><small>Público prioritário</small><b>{profile.targetAudience || 'A definir'}</b></article><article><small>Posicionamento</small><b>{profile.positioning || 'A definir'}</b></article><article><small>Valores</small><b>{profile.brandValues?.length ? profile.brandValues.join(' · ') : 'A definir'}</b></article></div></section><aside className="cadu-ds-brand-next"><p>Prontidão da identidade</p><h2>{brand.readiness?.missing?.length ? 'Fortaleça a base antes da próxima entrega' : 'A marca está pronta para orientar criações'}</h2>{brand.readiness?.missing?.length ? <ul>{brand.readiness.missing.map(item => <li key={item}>{item}</li>)}</ul> : <span>Use o Cadu, o Planner ou o Studio com esta identidade.</span>}{notStarted && canEdit && <button type="button" onClick={() => setDialog('audit')}>Preparar análise</button>}</aside></div>
          <section className="cadu-ds-brand-section cadu-ds-brand-tokens"><header><div><p>Sistema de sinais</p><h2>Cores e tipografia</h2><span>O que já está definido fica visível antes de qualquer criação.</span></div><span className="cadu-ds-brand-count">{colors.length} cores · {fonts.length} famílias</span></header><div className="cadu-ds-brand-token-columns"><div><h3>Paleta</h3>{colors.length ? colors.map((color, index) => { const item = typeof color === 'object' ? color : {hex: color}; return <div className="cadu-ds-brand-token" key={`${item.hex || 'color'}-${index}`}><i style={{background: item.hex || '#dcece6'}}/><b>{item.hex || '—'}</b><span>{item.role || item.name || 'Cor da marca'}</span></div>; }) : <p className="cadu-ds-brand-empty">Nenhuma cor aprovada ainda.</p>}</div><div><h3>Mix tipográfico</h3>{fonts.length ? fonts.map((font, index) => { const item = typeof font === 'object' ? font : {family: font}; return <div className="cadu-ds-brand-token" key={`${item.family || 'font'}-${index}`}><b>{item.role || 'texto'}</b><span>{item.family || item.classification || 'A definir'}</span><small>{item.classification || 'Família aprovada'}</small></div>; }) : <p className="cadu-ds-brand-empty">Defina as famílias usadas pela marca.</p>}</div></div></section>
          <AssetSection brand={brand} urls={urls} csrfToken={bootstrap.csrf} canManageBrand={canEdit}/>
          <div className="cadu-ds-brand-lower-grid"><section className="cadu-ds-brand-section"><header><div><p>Contexto compartilhado</p><h2>Projetos que usam esta marca</h2></div><button type="button" onClick={() => setDialog('link')}>Vincular</button></header><div className="cadu-ds-brand-project-list">{linkedProjects.length ? linkedProjects.map(project => <button type="button" key={project.id} onClick={() => projectDetail(project)}><VisualIdentity src={project.logoUrl} initials={project.initials || project.name} label={project.name} color={project.color}/><span><b>{project.name}</b><small>{project.sources} fontes prontas</small></span><i>›</i></button>) : <p className="cadu-ds-brand-empty">Esta marca ainda não está vinculada a um projeto.</p>}</div></section><section className="cadu-ds-brand-section"><header><div><p>Auditoria</p><h2>Evidências reunidas</h2></div>{canEdit && <button type="button" onClick={() => setDialog('audit')}>{brand.analysisMetadata?.pagesAnalyzed ? 'Reanalisar' : 'Analisar'}</button>}</header><div className="cadu-ds-brand-evidence"><div><b>{brand.analysisMetadata?.pagesAnalyzed || 0}</b><span>páginas</span></div><div><b>{brand.analysisMetadata?.assetsFound || 0}</b><span>ativos encontrados</span></div><div><b>{brand.analysisMetadata?.visualEvidenceCount || 0}</b><span>evidências visuais</span></div></div>{brand.analysisMetadata?.sources?.length > 0 && <details><summary>Fontes consultadas</summary><ul>{brand.analysisMetadata.sources.map(source => <li key={source}><a href={source} target="_blank" rel="noreferrer">{source}</a></li>)}</ul></details>}</section></div>
        </section>
      </div>
    </main>
    {dialog === 'identity' && <IdentityDialog brand={brand} urls={urls} csrfToken={bootstrap.csrf} onClose={() => setDialog('')}/>} {dialog === 'link' && <LinkProjectsDialog brand={brand} projects={bootstrap.availableProjects || []} csrfToken={bootstrap.csrf} onClose={() => setDialog('')}/>} {dialog === 'audit' && <AuditDialog brand={brand} urls={urls} csrfToken={bootstrap.csrf} onClose={() => setDialog('')}/>} {dialog === 'reviews' && <ReviewDialog brand={brand} onClose={() => setDialog('')}/>} {dialog === 'delete' && <DeleteBrandDialog brand={brand} linkedProjects={linkedProjects} urls={urls} csrfToken={bootstrap.csrf} onClose={() => setDialog('')}/>}
  </div>;
}
