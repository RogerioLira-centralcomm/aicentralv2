import React, {useEffect, useState} from 'react';
import './WorkspaceEntityPortal.css';
import {Icon} from './Icon';

export function EntityNavigator({label, items = [], context, children, identity}) {
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
    {identity && <div className="cadu-ds-entity-nav__identity">{identity}</div>}
    {!identity && <span className="cadu-ds-entity-nav__label">{label}</span>}
    <nav>{items.map(item => { const target = item.target || item.id; return <a key={item.id} href={`#${target}`} className={activeId === target ? 'is-active' : ''} aria-current={activeId === target ? 'location' : undefined}><Icon name={item.icon || 'file'} size={14}/><span>{item.label}</span>{Number.isFinite(item.count) && <small>{item.count}</small>}</a>; })}</nav>
    {context && <div className="cadu-ds-entity-nav__context">{context}</div>}
    {children && <div className="cadu-ds-entity-nav__actions">{children}</div>}
  </aside>;
}

function RailGroup({title, items = []}) {
  const [expanded, setExpanded] = useState(false);
  if (!items.length) return null;
  const visible = expanded ? items : items.slice(0, 5);
  return <section className="cadu-ds-entity-rail__group"><header><h3>{title}</h3><span>{items.length}</span></header><div>{visible.map((item, index) => {
    const content = <>{item.previewUrl ? <img src={item.previewUrl} alt="" loading="lazy"/> : item.icon ? <Icon name={item.icon} size={15}/> : null}<span><b>{item.title || item.name || `Item ${index + 1}`}</b>{item.detail && <small>{item.detail}</small>}{item.origin && <em>{item.origin}</em>}</span>{item.href && <i aria-hidden="true">↗</i>}</>;
    return item.href ? <a key={item.id || item.href || index} className={item.previewUrl ? 'has-preview' : ''} href={item.href} target={item.external ? '_blank' : undefined} rel={item.external ? 'noreferrer' : undefined}>{content}</a> : <div key={item.id || index} className={item.previewUrl ? 'has-preview' : ''}>{content}</div>;
  })}</div>{items.length > 5 && <button type="button" className="cadu-ds-entity-rail__expand" aria-expanded={expanded} onClick={() => setExpanded(value => !value)}>{expanded ? 'Mostrar menos' : `Ver todos (${items.length})`}</button>}</section>;
}

export function EntityContextRail({title = 'Em destaque', action, groups = [], children}) {
  return <aside className="cadu-ds-entity-rail" aria-label={title}><header className="cadu-ds-entity-rail__header"><span>{title}</span>{action}</header>{children}{groups.map(group => <RailGroup key={group.title} {...group}/>)}</aside>;
}

const DOCUMENT_TEMPLATES = {
  campaign: [['Briefing de campanha', 'brief', 'Objetivo, público, proposta, mensagem, canais, período, investimento, entregas e critérios de sucesso.'], ['Plano de campanha', 'document', 'Fases, dependências, canais, produção, medição, decisões e responsáveis confirmados.'], ['Relatório de resultados', 'document', 'Objetivos, resultados observados, fontes dos números, leitura crítica e recomendações.']],
  event: [['Plano do evento', 'document', 'Formato, data, local, público, programação, produção, acessibilidade, divulgação e contingências.'], ['Plano de divulgação', 'document', 'Mensagens, canais, calendário, convites, parceiros e métricas.'], ['Registro pós-evento', 'document', 'Participação, evidências, resultados, aprendizados e próximos passos.']],
  launch: [['Plano de lançamento', 'document', 'Produto ou marca, público, proposta, mensagens, marcos, canais, riscos e critérios de sucesso.'], ['Mensagens-chave', 'document', 'Promessa, provas disponíveis, objeções, tom, versões por público e usos proibidos.'], ['Cronograma de lançamento', 'document', 'Marcos, dependências, responsáveis confirmados e decisões pendentes.']],
  content: [['Direção editorial', 'document', 'Públicos, temas, objetivos, canais, tom, formatos, frequência e critérios de qualidade.'], ['Calendário de conteúdo', 'document', 'Pautas, canais, datas confirmadas, dependências e estado de cada peça.'], ['Relatório editorial', 'document', 'Publicações, desempenho observado, aprendizados e ajustes.']],
  research: [['Plano de pesquisa', 'research', 'Decisão a apoiar, perguntas, método, fontes, limites e critérios de evidência.'], ['Síntese de evidências', 'research', 'Achados com fonte, data, divergências, lacunas e grau de confiança.'], ['Recomendações', 'document', 'Alternativas, critérios de escolha, riscos e próximos passos.']],
  general: [['Documento de direção', 'document', 'Resultado esperado, contexto, público, escopo, restrições, entregas e critérios de sucesso.'], ['Plano de trabalho', 'document', 'Etapas, dependências, responsáveis confirmados, riscos e decisões.'], ['Registro de decisões', 'document', 'Decisão, motivo, evidência, responsável e data quando confirmados.']],
};

function projectPurpose(project = {}) {
  const explicit = String(project.purpose || project.projectType || '').toLowerCase();
  if (DOCUMENT_TEMPLATES[explicit]) return explicit;
  const subject = `${project.name || ''} ${project.description || ''}`.toLocaleLowerCase('pt-BR');
  if (/evento|congresso|feira|webinar|workshop/.test(subject)) return 'event';
  if (/lançamento|lancamento|estreia/.test(subject)) return 'launch';
  if (/campanha|mídia paga|midia paga|anúncios|anuncios/.test(subject)) return 'campaign';
  if (/editorial|conteúdo recorrente|conteudo recorrente|redes sociais/.test(subject)) return 'content';
  if (/pesquisa|diagnóstico|diagnostico|estudo/.test(subject)) return 'research';
  return 'general';
}

function promptUrl(base, prompt, artifactId) {
  try {
    const target = new URL(base, window.location.origin);
    target.searchParams.set('prompt', prompt);
    if (artifactId) { target.searchParams.set('surface', 'artifact'); target.searchParams.set('artifact_id', artifactId); }
    return `${target.pathname}${target.search}`;
  } catch (_) { return base; }
}

export function ProjectDataStarter({conversationUrl, project, onContext, onSources, onLink}) {
  const templates = DOCUMENT_TEMPLATES[projectPurpose(project)];
  return <section className="cadu-ds-project-starter" id="entrada"><header><span>Comece pela base</span><h2>Construa os dados do projeto</h2><p>Adicione material existente ou desenvolva um documento em conversa. Revise cada versão antes de finalizar e vincular ao projeto.</p></header><div className="cadu-ds-project-starter__paths"><button type="button" onClick={onContext}><Icon name="compose" size={16}/><span><b>Definir contexto</b><small>Objetivo, público, direção e instruções.</small></span></button><button type="button" onClick={onSources}><Icon name="file" size={16}/><span><b>Enviar arquivos</b><small>PDF, planilha, texto, imagem, áudio ou relatório.</small></span></button><button type="button" onClick={onLink}><Icon name="external" size={16}/><span><b>Adicionar links</b><small>Sites, dashboards e referências públicas.</small></span></button></div><div className="cadu-ds-project-starter__generators"><span>Documentos para este projeto</span>{templates.map(([label, type, sections]) => {
    const existing = (project?.artifacts || []).find(item => item.type === type && String(item.title || '').toLocaleLowerCase('pt-BR').includes(label.toLocaleLowerCase('pt-BR')));
    const prompt = existing ? `Quero editar "${existing.title}" neste projeto. Leia a versão mais recente do artefato aberto, incluindo alterações feitas manualmente no editor. Preserve fatos e seções que não pedi para mudar; pergunte qual alteração devo fazer agora. A cada revisão, atualize o mesmo documento e mantenha o histórico de versões.` : `Quero criar "${label}" para o projeto "${project?.name || 'atual'}". Use o contexto e as fontes disponíveis, sem inventar fatos. Estruture o documento com: ${sections} Diferencie o que está confirmado de hipóteses e lacunas relevantes. Primeiro trabalhe comigo na conversa; quando houver conteúdo suficiente, crie um artefato editável com título específico. Não salve como fonte do projeto até eu confirmar a versão final.`;
    return <a key={label} href={promptUrl(conversationUrl, prompt, existing?.artifactId)}><b>{label}</b><small>{existing ? 'Continuar edição' : 'Criar em conversa'}</small></a>;
  })}</div></section>;
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
