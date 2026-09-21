# Pipeline de revisão dos documentos do RAG

Status: `ready_for_external_run` · Versão: `v1.0.0`

## Ordem obrigatória

1. Pesquisa e auditoria de fontes com Perplexity ou ferramenta equivalente.
2. Revisão crítica e expansão no OpenRouter com o modelo aprovado para revisão.
3. Conversão em perguntas e respostas atômicas para recuperação no RAG.
4. Revisão humana de fontes, fatos, escopo e risco.
5. Publicação somente após mudança de `draft_review_pending` para `approved`.

## Variáveis de entrada

- `DOCUMENT`: conteúdo integral de um dos quatro documentos.
- `DOCUMENT_NAME`: nome do documento.
- `SOURCE_POLICY`: fontes oficiais, acadêmicas e setoriais; nenhuma fonte inventada.
- `TARGET_LANGUAGE`: pt-BR.
- `VERSION`: v1.0.0.

Não enviar chaves, cookies, dados de cliente ou fontes privadas para provedores externos.
