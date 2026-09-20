import React, {useMemo, useRef, useState} from 'react';
import {VisualIdentity} from './VisualIdentity';
import {CaduDialog} from './CaduDialog';
import {csrf, request} from '../../conversations-v2/lib/api';

const WIDGETS = [
  {id: 'resume', label: 'Retomar trabalho'},
  {id: 'next', label: 'Próxima atenção'},
  {id: 'projects', label: 'Projetos ativos'},
  {id: 'brands', label: 'Marcas fixadas'},
  {id: 'activity', label: 'Atividade recente'},
  {id: 'usage', label: 'Uso e créditos'},
];

const DEFAULT_ORDER = WIDGETS.map(item => item.id);
const COLLAPSED_STORAGE_KEY = 'cadu:home:collapsed-widgets';

function readPreferences(saved = {}) {
  const order = Array.isArray(saved.order) ? saved.order.filter(id => WIDGETS.some(item => item.id === id)) : [];
  const visible = Array.isArray(saved.visible) ? saved.visible.filter(id => WIDGETS.some(item => item.id === id)) : DEFAULT_ORDER;
  return {order: [...new Set([...order, ...DEFAULT_ORDER])], visible: [...new Set(visible)]};
}

function readCollapsedWidgets() {
  try {
    const saved = JSON.parse(window.localStorage.getItem(COLLAPSED_STORAGE_KEY) || '[]');
    return Array.isArray(saved) ? saved.filter(id => WIDGETS.some(item => item.id === id)) : [];
  } catch (_) { return []; }
}

function Widget({id, title, action, children, className = '', collapsed = false, onToggle, onDragStart, onDragOver, onDrop, onDragEnd}) {
  const startDrag = event => {
    if (event.target.closest('button,a')) { event.preventDefault(); return; }
    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('text/plain', id);
    onDragStart?.(id);
  };
  return <section className={`cadu-ds-home-widget cadu-ds-home-widget--${id} ${collapsed ? 'is-collapsed' : ''} ${className}`.trim()} data-widget={id} aria-labelledby={`home-widget-${id}`} onDragOver={onDragOver} onDrop={onDrop} onDragEnd={onDragEnd}>
    <header draggable onDragStart={startDrag}><div><span className="cadu-ds-home-widget__eyebrow">Workspace</span><h2 id={`home-widget-${id}`}>{title}</h2></div><div className="cadu-ds-home-widget__header-actions">{action}<button type="button" className="cadu-ds-home-widget__collapse" onClick={() => onToggle?.(id)} aria-expanded={!collapsed} aria-controls={`home-widget-content-${id}`} aria-label={`${collapsed ? 'Expandir' : 'Minimizar'} ${title}`}>{collapsed ? '+' : '−'}</button></div></header>
    {!collapsed && <div id={`home-widget-content-${id}`} className="cadu-ds-home-widget__content">{children}</div>}
  </section>;
}

function WidgetSettings({order, visible, saveState, onToggle, onMove, onReset, onClose}) {
  return <CaduDialog className="cadu-ds-home-widget-settings" label="Personalização da Home" closeOnBackdrop onClose={onClose}>
    <div className="cadu-ds-home-widget-settings__panel">
      <header><div><span>Personalização</span><h2 id="home-widget-settings-title">Organize sua Home</h2><p>Mostre o que ajuda seu trabalho agora. Você pode mudar isso quando quiser.</p></div><button type="button" onClick={onClose} aria-label="Fechar personalização">×</button></header>
      <div className="cadu-ds-home-widget-settings__list">{order.map((id, index) => { const item = WIDGETS.find(widget => widget.id === id); return <div key={id}><label><input type="checkbox" checked={visible.includes(id)} onChange={() => onToggle(id)}/><span>{item.label}</span></label><div><button type="button" disabled={index === 0} onClick={() => onMove(id, -1)} aria-label={`Mover ${item.label} para cima`}>↑</button><button type="button" disabled={index === order.length - 1} onClick={() => onMove(id, 1)} aria-label={`Mover ${item.label} para baixo`}>↓</button></div></div>; })}</div>
      <footer><span className={`cadu-ds-home-widget-settings__status is-${saveState}`}>{saveState === 'saving' ? 'Salvando…' : saveState === 'saved' ? 'Salvo na sua conta' : saveState === 'error' ? 'Não foi possível salvar' : 'Preferência da conta'}</span><button type="button" onClick={onReset}>Restaurar padrão</button><button type="button" className="is-primary" onClick={onClose}>Concluir</button></footer>
    </div>
  </CaduDialog>;
}

export function WorkspaceHomeWidgets({home = {}, projects = [], brands = [], links = {}, onOpen, onPrompt, onOpenActivity, onFeedback}) {
  const preferences = useMemo(() => readPreferences(home.preferences), [home.preferences]);
  const [order, setOrder] = useState(preferences.order);
  const [visible, setVisible] = useState(preferences.visible);
  const [collapsed, setCollapsed] = useState(readCollapsedWidgets);
  const [draggedId, setDraggedId] = useState('');
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [saveState, setSaveState] = useState('idle');
  const orderRef = useRef(order);
  const visibleRef = useRef(visible);
  const saveTimer = useRef(null);
  const persist = (nextOrder, nextVisible) => {
    orderRef.current = nextOrder;
    visibleRef.current = nextVisible;
    setOrder(nextOrder);
    setVisible(nextVisible);
    window.clearTimeout(saveTimer.current);
    setSaveState('saving');
    saveTimer.current = window.setTimeout(async () => {
      try {
        await request(links.homePreferences || '/workspace/api/home/preferences', {method: 'PUT', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf()}, body: JSON.stringify({order: nextOrder, visible: nextVisible})});
        setSaveState('saved');
      } catch (_) {
        setSaveState('error');
        onFeedback?.('Não foi possível salvar a organização da Home.');
      }
    }, 220);
  };
  const move = (id, direction) => { const index = orderRef.current.indexOf(id); const next = index + direction; if (index < 0 || next < 0 || next >= orderRef.current.length) return; const values = [...orderRef.current]; [values[index], values[next]] = [values[next], values[index]]; persist(values, visibleRef.current); };
  const toggle = id => { const values = visibleRef.current.includes(id) ? visibleRef.current.filter(value => value !== id) : [...visibleRef.current, id]; persist(orderRef.current, values); };
  const reset = () => { persist(DEFAULT_ORDER, DEFAULT_ORDER); onFeedback?.('Layout padrão restaurado e salvo na sua conta.'); };
  const toggleCollapsed = id => setCollapsed(current => {
    const next = current.includes(id) ? current.filter(value => value !== id) : [...current, id];
    try { window.localStorage.setItem(COLLAPSED_STORAGE_KEY, JSON.stringify(next)); } catch (_) { /* local preference is optional */ }
    return next;
  });
  const startDrag = id => setDraggedId(id);
  const dropWidget = (event, targetId) => {
    event.preventDefault();
    const sourceId = draggedId || event.dataTransfer?.getData('text/plain');
    if (!sourceId || sourceId === targetId) { setDraggedId(''); return; }
    const from = orderRef.current.indexOf(sourceId);
    const to = orderRef.current.indexOf(targetId);
    if (from < 0 || to < 0) { setDraggedId(''); return; }
    const next = [...orderRef.current];
    next.splice(to, 0, next.splice(from, 1)[0]);
    persist(next, visibleRef.current);
    setDraggedId('');
  };
  const widgetProps = id => ({
    collapsed: collapsed.includes(id),
    onToggle: toggleCollapsed,
    onDragStart: startDrag,
    onDragOver: event => event.preventDefault(),
    onDrop: event => dropWidget(event, id),
    onDragEnd: () => setDraggedId(''),
    className: draggedId === id ? 'is-dragging' : '',
  });
  const resume = home.resumeCards || [];
  const decisions = home.decisions || [];
  const activity = home.activity || [];
  const renderWidget = id => {
    if (id === 'resume') return <Widget key={id} id={id} title="Retomar trabalho" action={resume.length > 3 ? <button type="button" className="cadu-ds-home-widget__action" onClick={onOpenActivity}>Ver tudo</button> : null} {...widgetProps(id)}>{resume.length ? <div className="cadu-ds-home-widget-list">{resume.slice(0, 3).map(item => <button key={item.id} type="button" onClick={() => onOpen?.(item)}><span className="cadu-ds-home-widget-list__identity">{item.previewUrl ? <VisualIdentity src={item.previewUrl} initials="" label="" color={item.visualColor}/> : (item.kind || 'T').slice(0, 1)}</span><span><b>{item.title}</b><small>{item.context || item.status || 'Continuar trabalho'}</small></span><i aria-hidden="true">›</i></button>)}</div> : <EmptyWidget text="Suas conversas e projetos recentes aparecerão aqui."/>}</Widget>;
    if (id === 'next') return <Widget key={id} id={id} title="Próxima atenção" {...widgetProps(id)}>{decisions.length ? <div className="cadu-ds-home-widget-list">{decisions.slice(0, 3).map(item => <button key={item.id} type="button" onClick={() => onOpen?.(item)}><span className="cadu-ds-home-widget-list__signal">!</span><span><b>{item.title}</b><small>{item.context || item.detail || 'Decisão pendente'}</small></span><i aria-hidden="true">›</i></button>)}</div> : <EmptyWidget text="Nenhuma decisão pendente foi sinalizada nos seus contextos." actionLabel="Pedir uma leitura" onAction={() => onPrompt?.('Faça uma leitura dos projetos ativos e destaque o que precisa de uma decisão agora.')}/>}</Widget>;
    if (id === 'projects') return <Widget key={id} id={id} title="Projetos ativos" action={<a className="cadu-ds-home-widget__action" href={links.projects}>Ver projetos</a>} {...widgetProps(id)}>{projects.length ? <div className="cadu-ds-home-widget-list">{projects.slice(0, 4).map(project => <button key={project.id} type="button" onClick={() => onOpen?.(project)}><span className="cadu-ds-home-widget-list__identity"><VisualIdentity src={project.previewUrl} initials={project.visualInitials} label={project.name} color={project.visualColor}/></span><span><b>{project.name}</b><small>{project.brandName || 'Projeto em andamento'}</small></span><i aria-hidden="true">›</i></button>)}</div> : <EmptyWidget text="Crie um projeto para dar ao Cadu um contexto de trabalho." actionLabel="Criar projeto" href={links.projects}/>}</Widget>;
    if (id === 'brands') return <Widget key={id} id={id} title="Marcas fixadas" action={<a className="cadu-ds-home-widget__action" href={links.brands}>Ver marcas</a>} {...widgetProps(id)}>{brands.length ? <div className="cadu-ds-home-brand-grid">{brands.slice(0, 6).map(brand => <button key={brand.id} type="button" onClick={() => onOpen?.(brand)}><VisualIdentity src={brand.logoUrl} initials={brand.visualInitials} label={brand.name} color={brand.visualColor}/><span>{brand.name}</span></button>)}</div> : <EmptyWidget text="As marcas com identidade visual aparecem aqui para acesso rápido." href={links.brands} actionLabel="Ver marcas"/>}</Widget>;
    if (id === 'activity') return <Widget key={id} id={id} title="Atividade recente" {...widgetProps(id)}>{activity.length ? <div className="cadu-ds-home-activity-list">{activity.slice(0, 4).map(item => <button key={item.id} type="button" onClick={() => onOpen?.(item)}><span className="cadu-ds-home-activity-list__dot"/><span><b>{item.title}</b><small>{item.context || item.time || item.status}</small></span></button>)}</div> : <EmptyWidget text="As atualizações dos seus projetos aparecerão aqui."/>}</Widget>;
    if (id === 'usage') return <Widget key={id} id={id} title="Uso e créditos" action={<a className="cadu-ds-home-widget__action" href={links.usage}>Ver uso</a>} {...widgetProps(id)}><div className="cadu-ds-home-usage"><div className="cadu-ds-home-usage__ring" style={{'--cadu-usage': `${Math.max(0, Math.min(100, Number(home.usagePercent) || 0)) * 3.6}deg`}}><strong>{new Intl.NumberFormat('pt-BR', {maximumFractionDigits: 1}).format(Number(home.usagePercent) || 0)}%</strong></div><div><b>Consumo deste período</b><p>Use o histórico completo para acompanhar limites e saldo.</p></div></div></Widget>;
    return null;
  };
  return <section className="cadu-ds-home-widgets" aria-label="Visão geral do Workspace">
    <header className="cadu-ds-home-widgets__header"><div><span className="cadu-ds-home-widgets__eyebrow">Seu ritmo de trabalho</span><h2>Continue de onde faz sentido</h2></div><button type="button" className="cadu-ds-home-widgets__customize" onClick={() => setSettingsOpen(true)}>Personalizar Home</button></header>
    <div className="cadu-ds-home-widgets__grid">{order.filter(id => visible.includes(id)).map(renderWidget)}</div>
    {!visible.length && <EmptyWidget text="Escolha os blocos que deseja acompanhar nesta Home." actionLabel="Personalizar Home" onAction={() => setSettingsOpen(true)}/>}
    {settingsOpen && <WidgetSettings order={order} visible={visible} saveState={saveState} onToggle={toggle} onMove={move} onReset={reset} onClose={() => { setSettingsOpen(false); if (saveState === 'saved') onFeedback?.('Preferências da Home salvas na sua conta.'); }}/>}
  </section>;
}

function EmptyWidget({text, actionLabel, onAction, href}) {
  return <div className="cadu-ds-home-widget-empty"><p>{text}</p>{actionLabel && (href ? <a href={href}>{actionLabel}</a> : <button type="button" onClick={onAction}>{actionLabel}</button>)}</div>;
}
