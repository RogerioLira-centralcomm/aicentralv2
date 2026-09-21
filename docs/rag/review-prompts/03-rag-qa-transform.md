# Prompt 3 — transformação em perguntas e respostas para RAG

Converta o documento revisado em unidades de recuperação independentes. Cada resposta deve resolver uma pergunta concreta sem depender de contexto invisível.

## Regras

- uma intenção principal por pergunta;
- resposta entre 60 e 220 palavras, salvo fórmula ou tabela necessária;
- incluir definição, aplicação, condição e limitação quando aplicável;
- manter termos em português e sinônimos técnicos em inglês entre parênteses;
- preservar citações e links relevantes;
- não criar perguntas cujo conteúdo não esteja no documento revisado;
- criar perguntas de definição, comparação, escolha de método, aplicação, diagnóstico e risco;
- marcar perguntas que exigem dados do cliente como `needs_context`;
- evitar respostas genéricas como “depende” sem explicar de que depende.

## Formato de saída

```json
{
  "document_name": "...",
  "version": "v1.0.0",
  "items": [
    {
      "id": "slug-estavel",
      "question": "...",
      "answer": "...",
      "category": "definition|comparison|method|application|diagnosis|risk",
      "keywords": ["..."],
      "needs_context": false,
      "sources": [{"title": "...", "url": "..."}]
    }
  ]
}
```

## Controle de qualidade

- cada item deve ser compreensível isoladamente;
- nenhuma resposta deve conter fonte inexistente;
- fórmulas devem declarar unidade e denominador;
- métricas de plataforma não devem ser apresentadas como resultado causal;
- recomendações devem declarar premissas e limitações;
- duplicatas semânticas devem ser fundidas.

## Documento revisado

`{{REVISED_DOCUMENT}}`
