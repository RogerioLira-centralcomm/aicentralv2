import React,{useMemo,useState} from 'react';
import {SearchLg, Plus, MarkerPin01} from '@untitledui/icons';
import {ReportsActionButton as Button} from './ReportsActionButton.jsx';
import {catalogSections} from './flowCatalogModel.js';
import {plural} from './flowFeedback.js';
import {FlowSuggestionReview} from './FlowSuggestionReview.jsx';

const labels={entry:'Entrada',institutional:'Institucional',offer:'Oferta',content:'Conteúdo',intent:'Intenção',form:'Formulário',conversion:'Confirmação',checkout:'Finalização de compra',legal:'Página legal',error:'Erro',none:'Sem função sugerida'};

export function FlowCatalog({items=[],nodes=[],onAdd,onAddGroup,onLocate,onLinkTranslation,disabled,onClassify,suggestions={},classifying,onAcceptSuggestion}) {
  const [query,setQuery]=useState(''),[filter,setFilter]=useState('all'),[selected,setSelected]=useState([]),[preview,setPreview]=useState(null),[shown,setShown]=useState(100),[translationPage,setTranslationPage]=useState(null);
  const rows=useMemo(()=>items.map(page=>({...page,node:nodes.find(node=>node.discoveryPageId===String(page.id)||(node.path===page.path_prefix&&node.type==='page'&&(!node.host||node.host===page.page_host)))})).filter(page=>`${page.title_clean} ${page.path_prefix} ${page.locale||''}`.toLocaleLowerCase().includes(query.toLocaleLowerCase())&&(filter==='all'||filter==='mapped'&&page.node||page.role===filter)),[items,nodes,query,filter]);
  const visible=rows.slice(0,shown);
  const sections=useMemo(()=>catalogSections(visible),[visible]);
  const selectedPages=items.filter(page=>selected.includes(String(page.id)));
  const translationsFor=page=>page.translation_key?items.filter(item=>item.translation_key===page.translation_key&&item.page_host===page.page_host):[];
  const pageRow=page=><div className="flow-catalog-row" key={page.canonical_url}>
    <input type="checkbox" aria-label={`Selecionar ${page.title_clean}`} checked={selected.includes(String(page.id))} onChange={event=>setSelected(ids=>event.target.checked?[...ids,String(page.id)]:ids.filter(id=>id!==String(page.id)))}/>
    <span className="flow-catalog-row__text"><strong tabIndex={0}>{page.title_clean}</strong><small>{page.path_prefix} · {(page.locale||'pt').toUpperCase()}</small><span role="tooltip" className="flow-catalog-tooltip">{page.title}<br/>{page.canonical_url}</span></span>
    <Button color="tertiary" disabled={disabled} aria-label={page.node?'Localizar nó':'Adicionar página'} onClick={()=>page.node?onLocate(page.node.id):onAdd(page)}>{page.node?<MarkerPin01 size={16}/>:<Plus size={16}/>}</Button>
    {onClassify&&<details><summary aria-label="Revisar função e Tipo de página">⋯</summary><Button disabled={disabled||Boolean(classifying)} onClick={()=>onClassify(page)}>{classifying===String(page.id)?'Analisando…':'Sugerir função e Tipo de página com IA'}</Button><small>Consome 1 análise · limite de 50 por cliente/24 h.</small>{suggestions[page.id]&&<FlowSuggestionReview key={suggestions[page.id].suggestion_id} page={page} review={suggestions[page.id]} disabled={disabled} onApply={onAcceptSuggestion}/>}</details>}
    {translationsFor(page).length>1&&<Button color="tertiary" disabled={disabled} onClick={()=>setPreview(translationsFor(page))}>Reunir traduções</Button>}
    {onLinkTranslation&&<details onToggle={event=>setTranslationPage(event.currentTarget.open?page.id:null)}><summary aria-label={`Vincular tradução de ${page.title_clean}`}>Vincular tradução</summary>{translationPage===page.id&&<label>Vincular tradução…<select defaultValue="" onChange={event=>{const target=items.find(item=>String(item.id)===event.target.value);if(target){onLinkTranslation(page,target);event.target.value='';}}}><option value="">Selecione uma página</option>{items.filter(item=>item.id!==page.id&&item.locale!==page.locale).map(item=><option key={item.id} value={item.id}>{item.title_clean} · {(item.locale||'pt').toUpperCase()}</option>)}</select></label>}</details>}
  </div>;
  return <div className="flow-catalog">
    <label className="flow-catalog-search"><SearchLg size={16}/><input aria-label="Buscar páginas" placeholder="Buscar título, caminho ou idioma" value={query} onChange={event=>{setQuery(event.target.value);setShown(100);}}/></label>
    <div className="flow-catalog-filters">{[['all','Todas'],['mapped','No fluxo'],['conversion','Confirmação'],['intent','Intenção'],['none','Sem função sugerida']].map(([id,label])=><button key={id} aria-pressed={filter===id} onClick={()=>{setFilter(id);setShown(100);}}>{label}</button>)}</div>
    <small>{plural(items.length,'página','páginas')} · {items.filter(page=>page.role!=='none').length} com função sugerida por regras</small>
    {selectedPages.length>1&&<Button disabled={disabled} onClick={()=>setPreview(selectedPages)}>{`Agrupar ${plural(selectedPages.length,'página','páginas')}`}</Button>}
    {preview&&<section className="flow-catalog-group-preview" aria-label="Confirmar grupo"><strong>Agrupar páginas selecionadas?</strong><ul>{preview.map(page=><li key={page.id}>{page.title_clean} · {page.path_prefix}</li>)}</ul><div><Button disabled={disabled} onClick={()=>{onAddGroup(preview);setSelected([]);setPreview(null);}}>Agrupar</Button><Button onClick={()=>setPreview(null)}>Cancelar</Button></div></section>}
    {sections.groups.map(group=><details key={group.id} open><summary>{group.pattern} · {plural(group.pages.length,'página','páginas')} · {[...group.locales].sort().map(locale=>locale.toUpperCase()).join(' · ')}</summary><Button disabled={disabled} onClick={()=>setPreview(group.pages)}>Agrupar no fluxo</Button>{group.pages.map(pageRow)}</details>)}
    {sections.loose.map(([role,pages])=><details key={role} open><summary>{labels[role]||'Outro'} · {pages.length}</summary>{pages.map(pageRow)}</details>)}
    {shown<rows.length&&<Button onClick={()=>setShown(count=>count+100)}>Mostrar mais páginas</Button>}
    {!rows.length&&<p>{items.length?'Nenhuma página corresponde aos filtros.':'Nenhuma página verificada nesta análise.'}</p>}
  </div>;
}
