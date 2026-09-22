import React, {useEffect, useState} from 'react';
import './WorkspaceEntityPortal.css';
import {Icon} from './Icon';

export function EntityNavigator({label, items = [], context, children}) {
  const [activeId, setActiveId] = useState(() => items[0]?.target || items[0]?.id || '');
  useEffect(() => {
    const sections = items.map(item => document.getElementById(item.target || item.id)).filter(Boolean);
    if (!sections.length || typeof IntersectionObserver === 'undefined') return undefined;
    const observer = new IntersectionObserver(entries => {
      const visible = entries.filter(entry => entry.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio);
      if (visible[0]?.target?.id) setActiveId(visible[0].target.id);
    }, {rootMargin: '-12% 0px -70% 0px', threshold: [0, .12, .35]});
    sections.forEach(section => observer.observe(section));
    return () => observer.disconnect();
  }, [items]);
  return <aside className="cadu-ds-entity-nav" aria-label={`Navegação de ${label}`}>
    <span className="cadu-ds-entity-nav__label">{label}</span>
    <nav>{items.map(item => { const target = item.target || item.id; return <a key={item.id} href={`#${target}`} className={activeId === target ? 'is-active' : ''} aria-current={activeId === target ? 'location' : undefined}><Icon name={item.icon || 'file'} size={14}/><span>{item.label}</span>{Number.isFinite(item.count) && <small>{item.count}</small>}</a>; })}</nav>
    {context && <div className="cadu-ds-entity-nav__context">{context}</div>}
    {children && <div className="cadu-ds-entity-nav__actions">{children}</div>}
  </aside>;
}

function RailGroup({title, items = [], empty = 'Nenhum item disponível.'}) {
  return <section className="cadu-ds-entity-rail__group"><header><h3>{title}</h3><span>{items.length}</span></header>{items.length ? <div>{items.slice(0, 5).map((item, index) => {
    const content = <><span>{item.title || item.name || `Item ${index + 1}`}</span>{item.detail && <small>{item.detail}</small>}</>;
    return item.href ? <a key={item.id || item.href || index} href={item.href} target={item.external ? '_blank' : undefined} rel={item.external ? 'noreferrer' : undefined}>{content}</a> : <div key={item.id || index}>{content}</div>;
  })}</div> : <p>{empty}</p>}</section>;
}

export function EntityContextRail({title = 'Em destaque', action, groups = [], children}) {
  return <aside className="cadu-ds-entity-rail" aria-label={title}><header className="cadu-ds-entity-rail__header"><span>{title}</span>{action}</header>{children}{groups.map(group => <RailGroup key={group.title} {...group}/>)}</aside>;
}

const GENERATORS = [
  ['Briefing', 'Crie um briefing estruturado para este projeto com objetivo, público, contexto, restrições, entregas e critérios de sucesso. Salve o resultado como fonte editável do projeto.'],
  ['Plano inicial', 'Crie um plano inicial estruturado para este projeto com etapas, responsáveis sugeridos, dependências, riscos e próximos passos. Salve como artefato editável e fonte do projeto.'],
  ['Resumo executivo', 'Crie um resumo executivo do projeto a partir do contexto disponível. Sinalize claramente as lacunas e salve o texto como fonte editável.'],
  ['Mapa de dados', 'Mapeie quais dados, arquivos, links e decisões este projeto precisa receber. Organize o resultado como checklist estruturado e editável.'],
];

function promptUrl(base, prompt) {
  try {
    const target = new URL(base, window.location.origin);
    target.searchParams.set('prompt', prompt);
    target.searchParams.set('auto_send', '1');
    return `${target.pathname}${target.search}`;
  } catch (_) { return base; }
}

export function ProjectDataStarter({conversationUrl, onContext, onSources, onLink}) {
  return <section className="cadu-ds-project-starter" id="entrada"><header><span>Comece pela base</span><h2>Construa os dados do projeto</h2><p>Adicione material existente ou peça ao Cadu para gerar uma primeira versão estruturada. Cada resultado pode ser revisado como artefato antes de entrar nas fontes.</p></header><div className="cadu-ds-project-starter__paths"><button type="button" onClick={onContext}><Icon name="compose" size={16}/><span><b>Definir contexto</b><small>Objetivo, público, direção e instruções.</small></span></button><button type="button" onClick={onSources}><Icon name="file" size={16}/><span><b>Enviar arquivos</b><small>PDF, planilha, texto, imagem ou relatório.</small></span></button><button type="button" onClick={onLink}><Icon name="external" size={16}/><span><b>Adicionar links</b><small>Sites, dashboards e referências públicas.</small></span></button></div><div className="cadu-ds-project-starter__generators"><span>Geradores para começar</span>{GENERATORS.map(([label, prompt]) => <a key={label} href={promptUrl(conversationUrl, prompt)}><b>{label}</b><small>Gerar com o Cadu</small></a>)}</div></section>;
}

export function BrandCompletion({score = 0, missing = [], breakdown = [], processing = false, onAudit, onEdit}) {
  const normalized = Math.max(0, Math.min(100, Number(score) || 0));
  const ready = normalized >= 80;
  return <section className={`cadu-ds-brand-completion${ready ? ' is-ready' : ''}`} id="completar">
    <div className="cadu-ds-brand-completion__score"><strong>{normalized}%</strong><span>{ready ? 'base utilizável' : 'cobertura da marca'}</span></div>
    <div className="cadu-ds-brand-completion__body"><span>{ready ? 'Cobertura consolidada' : 'Próximo ganho de qualidade'}</span><h2>{ready ? 'A marca já orienta projetos e criação' : 'Complete os sinais que ainda fazem diferença'}</h2><p>{missing.length ? `Priorize: ${missing.slice(0, 3).join(', ')}.` : 'A auditoria preserva as lacunas sem bloquear os dados comprovados.'}</p>{breakdown.length > 0 && <div className="cadu-ds-brand-completion__map" aria-label="Cobertura por dimensão">{breakdown.map(item => { const pct = Math.max(0, Math.min(100, Math.round((Number(item.score) || 0) * 100 / Math.max(1, Number(item.max) || 1)))); return <div key={item.id}><span><b>{item.label}</b><small>{item.score}/{item.max}</small></span><i><em style={{width:`${pct}%`}}/></i></div>; })}</div>}</div>
    <div className="cadu-ds-brand-completion__actions"><button type="button" className="is-primary" disabled={processing} onClick={onAudit}>{processing ? 'Análise em andamento' : ready ? 'Atualizar análise' : 'Executar análise completa'}</button><button type="button" onClick={onEdit}>Editar dados</button></div>
  </section>;
}
