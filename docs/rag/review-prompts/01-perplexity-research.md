# Prompt 1 — pesquisa e auditoria de fontes

Você é o pesquisador responsável por preparar conhecimento global de marketing e mídia para um sistema RAG. Trabalhe somente com fontes públicas verificáveis.

## Instrução

Analise o documento abaixo e faça uma pesquisa complementar. Para cada afirmação técnica importante:

1. verifique se está correta;
2. encontre a fonte primária ou a melhor fonte institucional disponível;
3. registre URL, título, autor ou instituição, data e trecho ou evidência resumida;
4. identifique país, mercado, período e limitações;
5. marque a afirmação como `confirmed`, `needs_context`, `contradicted` ou `unsupported`;
6. sugira termos, métodos ou exemplos que estejam faltando.

Não invente estatísticas, autores, fórmulas, benchmarks ou links. Diferencie documentação de plataforma, literatura acadêmica, padrão setorial e opinião de consultoria. Não transforme recomendação em fato.

## Formato de saída

```json
{
  "document_name": "...",
  "research_summary": "...",
  "claims": [
    {
      "claim": "...",
      "status": "confirmed|needs_context|contradicted|unsupported",
      "correction": "...",
      "sources": [{"title": "...", "url": "...", "publisher": "...", "date": "..."}]
    }
  ],
  "missing_topics": ["..."],
  "recommended_additions": ["..."],
  "conflicts": ["..."]
}
```

## Documento para pesquisar

`{{DOCUMENT}}`
