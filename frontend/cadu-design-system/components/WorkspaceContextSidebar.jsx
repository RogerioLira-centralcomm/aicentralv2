import React, {useEffect, useMemo, useState} from 'react';
import {Icon} from './Icon';

const HOME_ITEMS = [
  {id: 'home', label: 'Início', key: 'home', icon: 'home'},
  {id: 'projects', label: 'Projetos', key: 'projects', icon: 'folder'},
  {id: 'brands', label: 'Marcas', key: 'brands', icon: 'brand'},
  {id: 'recent', label: 'Arquivos recentes', key: 'docs', icon: 'file'},
];

const ACCOUNT_ITEMS = [
  {id: 'agencia', label: 'Agência', key: 'agencia', icon: 'home'},
  {id: 'perfil', label: 'Perfil', key: 'perfil', icon: 'brand'},
  {id: 'equipe', label: 'Equipe', key: 'equipe', icon: 'folder'},
  {id: 'planos', label: 'Plano', key: 'planos', icon: 'pulse'},
  {id: 'creditos', label: 'Uso e créditos', key: 'creditos', icon: 'history'},
  {id: 'faturamento', label: 'Faturamento', key: 'faturamento', icon: 'file'},
];

function readCollapsed(mode) {
  try { return window.localStorage.getItem(`cadu:sidebar:${mode}`) === 'collapsed'; } catch (_) { return false; }
}

export function WorkspaceContextSidebar({mode = 'home', links = {}, active = 'home', resources = []}) {
  const [collapsed, setCollapsed] = useState(() => readCollapsed(mode));
  const items = mode === 'account' ? ACCOUNT_ITEMS : HOME_ITEMS;
  const recentFiles = useMemo(() => resources.filter(item => item?.href || item?.url).slice(0, 3), [resources]);

  useEffect(() => {
    try { window.localStorage.setItem(`cadu:sidebar:${mode}`, collapsed ? 'collapsed' : 'open'); } catch (_) { /* local preference is optional */ }
  }, [collapsed, mode]);

  return <aside className={`cadu-ds-context-sidebar ${collapsed ? 'is-collapsed' : ''}`} aria-label={mode === 'account' ? 'Navegação da conta' : 'Navegação do Workspace'}>
    <header className="cadu-ds-context-sidebar__header">
      <div className="cadu-ds-context-sidebar__heading"><span>Workspace</span><strong>{mode === 'account' ? 'Conta' : 'Atalhos de trabalho'}</strong></div>
      <button type="button" className="cadu-ds-context-sidebar__toggle" onClick={() => setCollapsed(value => !value)} aria-label={collapsed ? 'Expandir navegação' : 'Recolher navegação'} aria-expanded={!collapsed}>{collapsed ? '›' : '‹'}</button>
    </header>
    <nav className="cadu-ds-context-sidebar__nav" aria-label={mode === 'account' ? 'Seções da conta' : 'Seções do Workspace'}>
      {items.map(item => { const href = links[item.key]; if (!href) return null; return <a key={item.id} href={href} className={active === item.id ? 'is-active' : ''} aria-current={active === item.id ? 'page' : undefined} title={collapsed ? item.label : undefined}><Icon name={item.icon} size={16}/><span>{item.label}</span></a>; })}
    </nav>
    {mode === 'home' && <section className="cadu-ds-context-sidebar__recent" aria-label="Arquivos recentes">
      <div className="cadu-ds-context-sidebar__section-label"><span>Arquivos recentes</span>{links.docs && <a href={links.docs} title="Abrir todos os arquivos">Ver todos</a>}</div>
      {recentFiles.length ? recentFiles.map(item => <a key={item.id || item.resourceRef} href={item.href || item.url} title={item.title || item.name}><Icon name="file" size={14}/><span><b>{item.title || item.name || 'Arquivo'}</b><small>{item.projectName || item.project_name || 'Workspace'}</small></span></a>) : <p>Nenhum arquivo recente.</p>}
    </section>}
    <footer className="cadu-ds-context-sidebar__footer"><span>{mode === 'account' ? 'Configurações da conta' : 'Acesso rápido'}</span></footer>
  </aside>;
}
