import {ReportsNativeSelect} from './ReportsNativeSelect.jsx';
import React,{useState} from 'react';
import {ReportsActionButton as Button} from './ReportsActionButton.jsx';
import {suggestionAlternatives} from './flowSuggestionReviewModel.mjs';

const roleLabels={entry:'Página de entrada',intermediate:'Página intermediária',form:'Formulário',conversion:'Página de confirmação',error:'Página de erro',none:'Sem evidência suficiente'};
const typeLabels={home:'Home',service:'Serviço',institutional:'Institucional',contact:'Contato',case:'Case',content:'Conteúdo',other:'Outro',unknown:'Sem evidência suficiente'};

export function FlowSuggestionReview({page,review,onApply,disabled}) {
  const suggestion=review.suggestion;
  const [role,setRole]=useState(roleLabels[suggestion.role]&&suggestion.role!=='none'?suggestion.role:'intermediate');
  const [pageType,setPageType]=useState(typeLabels[suggestion.page_type]?suggestion.page_type:'unknown');
  return <div className="flow-suggestion-review">
    <p>Revise as duas escolhas antes de {page.node?'atualizar o nó':'adicionar a página'}.</p>
    <label>Função na jornada<ReportsNativeSelect size="sm" value={role} onChange={event=>setRole(event.target.value)}>{Object.entries(roleLabels).filter(([value])=>value!=='none').map(([value,label])=><option key={value} value={value}>{label}</option>)}</ReportsNativeSelect></label>
    <small>Alternativas de função: {suggestionAlternatives(suggestion.probabilities,roleLabels)||'dados indisponíveis'}.</small>
    <label>Tipo de página<ReportsNativeSelect size="sm" value={pageType} onChange={event=>setPageType(event.target.value)}><option value="unknown">Não definir agora</option>{Object.entries(typeLabels).filter(([value])=>value!=='unknown').map(([value,label])=><option key={value} value={value}>{label}</option>)}</ReportsNativeSelect></label>
    <small>Alternativas de Tipo de página: {suggestionAlternatives(suggestion.page_type_probabilities,typeLabels)||'dados indisponíveis'}.</small>
    {pageType==='unknown'&&<small>Faltam evidências para definir o Tipo de página. Você pode escolher depois no inspector.</small>}
    <small>Os percentuais mostram a distribuição da análise, não a chance de acerto. A confirmação de uma página não comprova uma conversão.</small>
    <Button disabled={disabled} onClick={()=>onApply(page,review,{role,pageType})}>Confirmar escolhas e {page.node?'atualizar nó':'adicionar página'}</Button>
  </div>;
}
