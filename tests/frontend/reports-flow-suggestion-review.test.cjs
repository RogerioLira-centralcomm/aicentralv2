const assert=require('node:assert/strict');
const {test}=require('node:test');

test('ordena alternativas de cada pergunta sem misturar as distribuições',async()=>{
  const {suggestionAlternatives}=await import('../../frontend/reports-v1/flowSuggestionReviewModel.mjs');
  const result=suggestionAlternatives({unknown:.15,service:.7,home:.1,other:.05},
    {unknown:'Sem evidência suficiente',service:'Serviço',home:'Home',other:'Outro'});
  assert.equal(result,'Serviço 70% · Sem evidência suficiente 15% · Home 10%');
});
