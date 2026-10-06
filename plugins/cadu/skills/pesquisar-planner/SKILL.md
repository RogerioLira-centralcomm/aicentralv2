---
name: pesquisar-planner
description: Consulta o catálogo do Planner do Cadu (audiências, canais, formatos, formatos interativos, portais e Places) e a inteligência de mercado, mostrando cada item com imagem e logo. Use para enriquecer pesquisas, anotações e planejamentos sem a pessoa abrir o Cadu.
---

# Pesquisar no Planner

O Cadu é fonte de dados e de inteligência de mercado para o trabalho da pessoa. A consulta é somente leitura e não consome créditos.

1. Escolha o tipo em `planner.search_catalog`: `audiencias`, `canais`, `formatos`, `interativos`, `portais` ou `places`. Use `query` com o tema (ex.: "executivos", "aeroporto") e, se precisar, `limit`.
2. **Mostre os itens de forma visual.** Cada registro traz `card`, um markdown pronto com imagem, logo, nome, dados-chave e o link "Abrir no Cadu". Cole os cards na resposta, em vez de resumir em lista de texto. Se não houver imagem, mostre o texto e o link.
3. Para aprofundar um item, use `planner.get_catalog_item` com o `kind` e o `id` do resultado (para Places, o `slug`). A ficha traz imagens, logo, formatos e canais relacionados, audiências parecidas e o card pronto; mostre o card e use os dados no texto.
4. Combine com texto e mercado: use `insights.research_market` e `web.search` para contexto de mercado e relacione o que o catálogo mostra com o objetivo da pessoa.
5. Para o plano de mídia da pessoa, use `planner.list_plans`, `planner.get_brief` e `planner.get_media_plan`.
6. Se a pessoa quiser guardar o resultado, ofereça salvar como nota no projeto (`projects.create_note`) e mostre o que será salvo antes de gravar.

## Regras
- Os dados do catálogo são referência. Não invente valores, preços ou alcances que o resultado não trouxe, e diga quando o catálogo não tem o item.
- O MCP não expõe valores comerciais. Se a pessoa pedir preço ou investimento, diga que isso está no Cadu e passe o link do item.
