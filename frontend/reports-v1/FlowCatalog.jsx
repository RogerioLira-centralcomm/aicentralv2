import {ReportsNativeSelect} from './ReportsNativeSelect.jsx';
import {ReportsFieldInput} from './ReportsFieldInput.jsx';
import {CaduTooltip} from '../cadu-design-system/components/CaduTooltip.jsx';
import React,{useMemo,useState} from 'react';
import {SearchLg, Plus, MarkerPin01, ChevronRight, ChevronLeft} from '@untitledui/icons';
import {ReportsActionButton as Button} from './ReportsActionButton.jsx';
import {CATALOG_GROUP_ADD_LIMIT,CATALOG_PAGE_SIZE,catalogSections,pageWindow} from './flowCatalogModel.js';
import {plural} from './flowFeedback.js';
import {FlowSuggestionReview} from './FlowSuggestionReview.jsx';

const labels={entry:'Entrada',institutional:'Institucional',offer:'Oferta',content:'Conteúdo',intent:'Intenção',form:'Formulário',conversion:'Confirmação',checkout:'Finalização de compra',legal:'Página legal',error:'Erro',none:'Sem função sugerida'};
const FILTERS=[['all','Todas'],['mapped','No fluxo'],['conversion','Confirmação'],['intent','Intenção'],['none','Sem função']];

/** Site explorer: groups first, pages ten at a time, one open section. Never a flat list of every link. */
export function FlowCatalog({items=[],nodes=[],onAdd,onAddGroup,onLocate,onLinkTranslation,disabled,onClassify,suggestions={},classifying,onAcceptSuggestion}) {
  const [query,setQuery]=useState(''),[filter,setFilter]=useState('all'),[open,setOpen]=useState(null),[pages,setPages]=useState({}),[preview,setPreview]=useState(null),[menu,setMenu]=useState(null);
  const rows=useMemo(()=>{
    const needle=query.trim().toLocaleLowerCase();
    return items.map(page=>({...page,node:nodes.find(node=>node.discoveryPageId===String(page.id)||(node.path===page.path_prefix&&node.type==='page'&&(!node.host||node.host===page.page_host)))}))
      .filter(page=>(!needle||`${page.title_clean} ${page.path_prefix} ${page.locale||''}`.toLocaleLowerCase().includes(needle))&&(filter==='all'||(filter==='mapped'?page.node:page.role===filter)));
  },[items,nodes,query,filter]);
  const sections=useMemo(()=>catalogSections(rows),[rows]);
  const translationsFor=page=>page.translation_key?items.filter(item=>item.translation_key===page.translation_key&&item.page_host===page.page_host):[];
  const searching=Boolean(query.trim())||filter!=='all';
  const setPage=(key,value)=>setPages(current=>({...current,[key]:value}));
  const toggle=key=>{setOpen(current=>current===key?null:key);setMenu(null);};

  const pageRow=page=><li className="flow-catalog-row" key={page.canonical_url}>
    <span className="flow-catalog-row__text"><CaduTooltip placement="right" label={<>{page.title}<br/>{page.canonical_url}</>}><strong tabIndex={0}>{page.title_clean}</strong></CaduTooltip><small>{page.path_prefix} · {(page.locale||'pt').toUpperCase()}</small></span>
    <Button color="tertiary" size="sm" disabled={disabled} aria-label={page.node?'Localizar nó':'Adicionar página'} onClick={()=>page.node?onLocate(page.node.id):onAdd(page)}>{page.node?<MarkerPin01 size={16}/>:<Plus size={16}/>}</Button>
    <Button color="tertiary" size="sm" aria-label={`Mais ações para ${page.title_clean}`} aria-expanded={menu===page.id} onClick={()=>setMenu(current=>current===page.id?null:page.id)}>⋯</Button>
    {menu===page.id&&<div className="flow-catalog-row__menu">
      {translationsFor(page).length>1&&<Button color="tertiary" size="sm" disabled={disabled} onClick={()=>setPreview({title:'Reunir traduções',pages:translationsFor(page)})}>Reunir traduções</Button>}
      {onClassify&&<><Button color="tertiary" size="sm" disabled={disabled||Boolean(classifying)} onClick={()=>onClassify(page)}>{classifying===String(page.id)?'Analisando…':'Sugerir função com IA'}</Button><small>Consome 1 análise · limite de 50 por cliente/24 h.</small>{suggestions[page.id]&&<FlowSuggestionReview key={suggestions[page.id].suggestion_id} page={page} review={suggestions[page.id]} disabled={disabled} onApply={onAcceptSuggestion}/>}</>}
      {onLinkTranslation&&<label>Vincular tradução<ReportsNativeSelect size="sm" defaultValue="" onChange={event=>{const target=items.find(item=>String(item.id)===event.target.value);if(target){onLinkTranslation(page,target);event.target.value='';}}}><option value="">Selecione uma página</option>{items.filter(item=>item.id!==page.id&&item.locale!==page.locale).map(item=><option key={item.id} value={item.id}>{item.title_clean} · {(item.locale||'pt').toUpperCase()}</option>)}</ReportsNativeSelect></label>}
    </div>}
  </li>;

  const pager=(key,total)=>{
    const view=pageWindow(total,pages[key]||0);
    if(total<=CATALOG_PAGE_SIZE)return null;
    return <div className="flow-catalog-pager" role="group" aria-label="Paginação">
      <Button color="tertiary" size="sm" aria-label="Página anterior" disabled={view.page===0} onClick={()=>setPage(key,view.page-1)}><ChevronLeft size={16}/></Button>
      <span>{view.from}–{view.end} de {total}</span>
      <Button color="tertiary" size="sm" aria-label="Próxima página" disabled={view.page===view.last} onClick={()=>setPage(key,view.page+1)}><ChevronRight size={16}/></Button>
    </div>;
  };
  const list=(key,pagesOfSection)=>{
    const view=pageWindow(pagesOfSection.length,pages[key]||0);
    return <div className="flow-catalog-section__body"><ul>{pagesOfSection.slice(view.start,view.end).map(pageRow)}</ul>{pager(key,pagesOfSection.length)}</div>;
  };
  const section=({key,title,detail,pagesOfSection,groupable})=><li className="flow-catalog-section" key={key}>
    <div className="flow-catalog-section__head">
      <button type="button" aria-expanded={open===key||searching} onClick={()=>toggle(key)}><ChevronRight size={14} aria-hidden="true"/><span><strong>{title}</strong><small>{detail}</small></span></button>
      {groupable&&<Button color="tertiary" size="sm" disabled={disabled} aria-label="Agrupar no fluxo" title="Adicionar este grupo ao fluxo" onClick={()=>setPreview({title:'Agrupar no fluxo',pages:pagesOfSection})}>Agrupar</Button>}
    </div>
    {(open===key||searching)&&list(key,pagesOfSection)}
  </li>;

  return <div className="flow-catalog">
    <label className="flow-catalog-search"><ReportsFieldInput leading={<SearchLg size={16} aria-hidden="true" className="ml-3 shrink-0 text-fg-quaternary"/>} size="sm" aria-label="Buscar páginas" placeholder="Buscar título, caminho ou idioma" value={query} onChange={event=>{setQuery(event.target.value);setPages({});}}/></label>
    <div className="flow-catalog-filters">{FILTERS.map(([id,label])=><button key={id} type="button" aria-pressed={filter===id} onClick={()=>{setFilter(id);setPages({});}}>{label}</button>)}</div>
    <small className="flow-catalog-count">{plural(rows.length,'página','páginas')}{sections.groups.length>0&&` · ${plural(sections.groups.length,'grupo','grupos')}`}</small>
    {preview&&<section className="flow-catalog-group-preview" aria-label="Confirmar grupo">
      <strong>{preview.title}: {plural(Math.min(preview.pages.length,CATALOG_GROUP_ADD_LIMIT),'página','páginas')}?</strong>
      <ul>{preview.pages.slice(0,CATALOG_GROUP_ADD_LIMIT).map(page=><li key={page.id}>{page.title_clean} · {page.path_prefix}</li>)}</ul>
      {preview.pages.length>CATALOG_GROUP_ADD_LIMIT&&<small>{preview.pages.length-CATALOG_GROUP_ADD_LIMIT} páginas ficam de fora; o fluxo aceita até {CATALOG_GROUP_ADD_LIMIT} por grupo.</small>}
      <div><Button size="sm" disabled={disabled} onClick={()=>{onAddGroup(preview.pages.slice(0,CATALOG_GROUP_ADD_LIMIT));setPreview(null);}}>Confirmar</Button><Button size="sm" color="secondary" onClick={()=>setPreview(null)}>Cancelar</Button></div>
    </section>}
    <ul className="flow-catalog-sections">
      {sections.groups.map(group=>section({key:`g:${group.id}`,title:group.pattern,detail:`${plural(group.pages.length,'página','páginas')} · ${group.kind==='template'?'mesmo modelo':'mesma pasta'} · ${[...group.locales].sort().map(locale=>locale.toUpperCase()).join(' · ')}`,pagesOfSection:group.pages,groupable:true}))}
      {sections.loose.map(([role,pagesOfRole])=>section({key:`r:${role}`,title:labels[role]||'Outro',detail:plural(pagesOfRole.length,'página','páginas'),pagesOfSection:pagesOfRole,groupable:false}))}
    </ul>
    {!rows.length&&<p className="flow-catalog-empty">{items.length?'Nenhuma página corresponde aos filtros.':'Nenhuma página verificada nesta análise.'}</p>}
  </div>;
}
